#ifndef SQL_SORT_INCLUDED
#define SQL_SORT_INCLUDED

/* Copyright (c) 2000, 2011, Oracle and/or its affiliates. All rights reserved.

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

#include "m_string.h"                           /* memset */
#include "my_global.h"                          /* uchar */
#include "my_base.h"                            /* ha_rows */
#include "my_sys.h"                             /* qsort2_cmp */

typedef struct st_buffpek BUFFPEK;
typedef struct st_queue QUEUE;
typedef struct st_sort_field SORT_FIELD;

/* Defines used by filesort and uniques */

#define MERGEBUFF		7
#define MERGEBUFF2		15


typedef struct st_buffpek {		/* Struktur om sorteringsbuffrarna */
  my_off_t file_pos;			/* Where we are in the sort file */
  uchar *base,*key;			/* key pointers */
  ha_rows count;			/* Number of rows in table */
  ulong mem_count;			/* numbers of keys in memory */
  ulong max_keys;			/* Max keys in buffert */
} BUFFPEK;

struct BUFFPEK_COMPARE_CONTEXT
{
  qsort_cmp2 key_compare;
  const void *key_compare_arg;
};

class Sort_param {
public:
  uint rec_length;            // Length of sorted records.
  uint sort_length;           // Length of sorted columns.
  uint ref_length;            // Length of record ref.
  uint addon_length;          // Length of added packed fields.
  uint res_length;            // Length of records in final sorted file/buffer.
  uint max_keys_per_buffer;   // Max keys / buffer.
  ha_rows max_rows;           // Select limit, or HA_POS_ERROR if unlimited.
  ha_rows examined_rows;      // Number of examined rows.
  SORT_FIELD *local_sortorder;
  SORT_FIELD *end;
  uchar *unique_buff;
  bool not_killable;
  char* tmp_buffer;
  // The fields below are used only by Unique class.
  qsort2_cmp compare;
  BUFFPEK_COMPARE_CONTEXT cmp_context;

  Sort_param()
  {
    memset(this, 0, sizeof(*this));
  }
};


int merge_many_buff(Sort_param *param, uchar *sort_buffer,
		    BUFFPEK *buffpek,
		    uint *maxbuffer, IO_CACHE *t_file);
uint read_to_buffer(IO_CACHE *fromfile,BUFFPEK *buffpek,
		    uint sort_length);
int merge_buffers(Sort_param *param,IO_CACHE *from_file,
                  IO_CACHE *to_file, uchar *sort_buffer,
                  BUFFPEK *lastbuff,BUFFPEK *Fb,
                  BUFFPEK *Tb,int flag);
void reuse_freed_buff(QUEUE *queue, BUFFPEK *reuse, uint key_length);

#endif /* SQL_SORT_INCLUDED */
