#ifndef SQL_PARTITION_INCLUDED
#define SQL_PARTITION_INCLUDED

/* Copyright (c) 2006, 2014, Oracle and/or its affiliates. All rights reserved.

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; version 2 of the License.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA */

#include "sql_list.h"                           /* List */
#include "table.h"                              /* TABLE_LIST */

class Alter_info;
class String;
class handler;
struct TABLE_LIST;
typedef struct st_bitmap MY_BITMAP;
typedef struct st_ha_create_information HA_CREATE_INFO;
typedef struct st_key KEY;
typedef struct st_key_range key_range;

/* Flags for partition handlers */
#define HA_CAN_PARTITION       (1 << 0) /* Partition support */
#define HA_CAN_UPDATE_PARTITION_KEY (1 << 1)
#define HA_CAN_PARTITION_UNIQUE (1 << 2)
/* If the engine will use auto partitioning even when not defined. */
#define HA_USE_AUTO_PARTITION (1 << 3)

#define NORMAL_PART_NAME 0
#define TEMP_PART_NAME 1
#define RENAMED_PART_NAME 2

typedef struct st_lock_param_type
{
  TABLE_LIST *table_list;
  ulonglong copied;
  ulonglong deleted;
  THD *thd;
  HA_CREATE_INFO *create_info;
  Alter_info *alter_info;
  KEY *key_info_buffer;
  const char *db;
  const char *table_name;
  uchar *pack_frm_data;
  uint key_count;
  uint db_options;
  size_t pack_frm_len;
  partition_info *part_info;
} ALTER_PARTITION_PARAM_TYPE;

typedef struct {
  longlong list_value;
  uint32 partition_id;
} LIST_PART_ENTRY;

typedef struct {
  uint32 start_part;
  uint32 end_part;
} part_id_range;

struct st_partition_iter;
#define NOT_A_PARTITION_ID UINT_MAX32

bool is_partition_in_list(char *part_name, List<char> list_part_names);
char *are_partitions_in_table(partition_info *new_part_info,
                              partition_info *old_part_info);
int get_parts_for_update(const uchar *old_data, uchar *new_data,
                         const uchar *rec0, partition_info *part_info,
                         uint32 *old_part_id, uint32 *new_part_id,
                         longlong *func_value);
int get_part_for_delete(const uchar *buf, const uchar *rec0,
                        partition_info *part_info, uint32 *part_id);
void set_linear_hash_mask(partition_info *part_info, uint num_parts);
int get_cs_converted_part_value_from_string(THD *thd,
                                            Item *item,
                                            String *input_str,
                                            String *output_str,
                                            const CHARSET_INFO *cs,
                                            bool use_hex);
bool make_used_partitions_str(partition_info *part_info,
                              List<const char> *parts);
uint32 get_list_array_idx_for_endpoint(partition_info *part_info,
                                       bool left_endpoint,
                                       bool include_endpoint);
uint32 get_partition_id_range_for_endpoint(partition_info *part_info,
                                           bool left_endpoint,
                                           bool include_endpoint);
Item* convert_charset_partition_constant(Item *item, const CHARSET_INFO *cs);
void mem_alloc_error(size_t size);
void truncate_partition_filename(char *path);

/*
  A "Get next" function for partition iterator.

  SYNOPSIS
    partition_iter_func()
      part_iter  Partition iterator, you call only "iter.get_next(&iter)"

  DESCRIPTION
    Depending on whether partitions or sub-partitions are iterated, the
    function returns next subpartition id/partition number. The sequence of
    returned numbers is not ordered and may contain duplicates.

    When the end of sequence is reached, NOT_A_PARTITION_ID is returned, and 
    the iterator resets itself (so next get_next() call will start to 
    enumerate the set all over again).

  RETURN 
    NOT_A_PARTITION_ID if there are no more partitions.
    [sub]partition_id  of the next partition
*/

typedef uint32 (*partition_iter_func)(st_partition_iter* part_iter);


/*
  Partition set iterator. Used to enumerate a set of [sub]partitions
  obtained in partition interval analysis (see get_partitions_in_range_iter).

  For the user, the only meaningful field is get_next, which may be used as
  follows:
             part_iterator.get_next(&part_iterator);
  
  Initialization is done by any of the following calls:
    - get_partitions_in_range_iter-type function call
    - init_single_partition_iterator()
    - init_all_partitions_iterator()
  Cleanup is not needed.
*/

typedef struct st_partition_iter
{
  partition_iter_func get_next;
  /* 
    Valid for "Interval mapping" in LIST partitioning: if true, let the
    iterator also produce id of the partition that contains NULL value.
  */
  bool ret_null_part, ret_null_part_orig;
  struct st_part_num_range
  {
    uint32 start;
    uint32 cur;
    uint32 end;
  };

  struct st_field_value_range
  {
    longlong start;
    longlong cur;
    longlong end;
  };

  union
  {
    struct st_part_num_range     part_nums;
    struct st_field_value_range  field_vals;
  };
  partition_info *part_info;
} PARTITION_ITERATOR;


/*
  Get an iterator for set of partitions that match given field-space interval

  SYNOPSIS
    get_partitions_in_range_iter()
      part_info            Partitioning info
      is_subpart
      store_length_array   Length of fields packed in opt_range_key format
      min_val              Left edge,  field value in opt_range_key format
      max_val              Right edge, field value in opt_range_key format
      min_len              Length of minimum value
      max_len              Length of maximum value
      flags                Some combination of NEAR_MIN, NEAR_MAX, NO_MIN_RANGE,
                           NO_MAX_RANGE
      part_iter            Iterator structure to be initialized

  DESCRIPTION
    Functions with this signature are used to perform "Partitioning Interval
    Analysis". This analysis is applicable for any type of [sub]partitioning 
    by some function of a single fieldX. The idea is as follows:
    Given an interval "const1 <=? fieldX <=? const2", find a set of partitions
    that may contain records with value of fieldX within the given interval.

    The min_val, max_val and flags parameters specify the interval.
    The set of partitions is returned by initializing an iterator in *part_iter

  NOTES
    There are currently three functions of this type:
     - get_part_iter_for_interval_via_walking
     - get_part_iter_for_interval_cols_via_map
     - get_part_iter_for_interval_via_mapping

  RETURN 
    0 - No matching partitions, iterator not initialized
    1 - Some partitions would match, iterator intialized for traversing them
   -1 - All partitions would match, iterator not initialized
*/

typedef int (*get_partitions_in_range_iter)(partition_info *part_info,
                                            bool is_subpart,
                                            uint32 *store_length_array,
                                            uchar *min_val, uchar *max_val,
                                            uint min_len, uint max_len,
                                            uint flags,
                                            PARTITION_ITERATOR *part_iter);

#ifdef WITH_PARTITION_STORAGE_ENGINE
char *generate_partition_syntax(partition_info *part_info,
                                uint *buf_length, bool use_sql_alloc,
                                bool show_partition_options,
                                HA_CREATE_INFO *create_info,
                                Alter_info *alter_info,
                                const char *current_comment_start);
#endif

void create_partition_name(char *out, const char *in1,
                           const char *in2, uint name_variant,
                           bool translate);
void create_subpartition_name(char *out, const char *in1,
                              const char *in2, const char *in3,
                              uint name_variant);

void set_key_field_ptr(KEY *key_info, const uchar *new_buf,
                       const uchar *old_buf);

extern const LEX_STRING partition_keywords[];


#include "partition_info.h"

#endif /* SQL_PARTITION_INCLUDED */
