/*
   Copyright (c) 2000, 2014, Oracle and/or its affiliates. All rights reserved.

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; version 2 of the License.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA
*/

/* drop and alter of tables */

#include "sql_priv.h"
#include "unireg.h"
#include "sql_table.h"
#include "sql_rename.h" // do_rename
#include "sql_base.h"   // open_table_uncached, lock_table_names
#include "strfunc.h"    // find_type2, find_set
#include "sql_view.h" // view_checksum 
#include "sql_truncate.h"                       // regenerate_locked_table 
#include "sql_partition.h"                      // mem_alloc_error,
                                                // generate_partition_syntax,
                                                // partition_info
                                                // NOT_A_PARTITION_ID
#include "sql_db.h"                             // load_db_opt_by_name
#include "sql_time.h"                  // make_truncated_value_warning
#include "records.h"             // init_read_record, end_read_record
#include "sql_handler.h"               // mysql_ha_rm_tables
#include "discover.h"                  // readfrm
#include "my_pthread.h"                // pthread_mutex_t
#include <hash.h>
#include <my_dir.h>
#include "sp_head.h"
#include "sp.h"
#include "sql_trigger.h"
#include "sql_parse.h"
#include "sql_show.h"
#include <mysql/psi/mysql_table.h>
#include "mysql.h"			// in_bootstrap & opt_noacl

#ifdef __WIN__
#include <io.h>
#endif

#include <algorithm>
using std::max;
using std::min;

const char *primary_key_name="PRIMARY";

#ifdef USE_SYMDIR
bool symdir_warning_emitted= false;
#endif


static bool prepare_blob_field(THD *thd, Create_field *sql_field);
static void sp_prepare_create_field(THD *thd, Create_field *sql_field);



/**
  @brief Helper function for explain_filename
  @param thd          Thread handle
  @param to_p         Explained name in system_charset_info
  @param end_p        End of the to_p buffer
  @param name         Name to be converted
  @param name_len     Length of the name, in bytes
*/
static char* add_identifier(THD* thd, char *to_p, const char * end_p,
                            const char* name, uint name_len)
{
  uint res;
  uint errors;
  const char *conv_name;
  char tmp_name[FN_REFLEN];
  char conv_string[FN_REFLEN];
  int quote;

  DBUG_ENTER("add_identifier");
  if (!name[name_len])
    conv_name= name;
  else
  {
    strnmov(tmp_name, name, name_len);
    tmp_name[name_len]= 0;
    conv_name= tmp_name;
  }
  res= strconvert(&my_charset_filename, conv_name, system_charset_info,
                  conv_string, FN_REFLEN, &errors);
  if (!res || errors)
  {
    DBUG_PRINT("error", ("strconvert of '%s' failed with %u (errors: %u)", conv_name, res, errors));
    conv_name= name;
  }
  else
  {
    DBUG_PRINT("info", ("conv '%s' -> '%s'", conv_name, conv_string));
    conv_name= conv_string;
  }

  quote = thd ? get_quote_char_for_identifier(thd, conv_name, res - 1) : '"';

  if (quote != EOF && (end_p - to_p > 2))
  {
    *(to_p++)= (char) quote;
    while (*conv_name && (end_p - to_p - 1) > 0)
    {
      uint length= my_mbcharlen(system_charset_info, *conv_name);
      if (!length)
        length= 1;
      if (length == 1 && *conv_name == (char) quote)
      { 
        if ((end_p - to_p) < 3)
          break;
        *(to_p++)= (char) quote;
        *(to_p++)= *(conv_name++);
      }
      else if (((long) length) < (end_p - to_p))
      {
        to_p= strnmov(to_p, conv_name, length);
        conv_name+= length;
      }
      else
        break;                               /* string already filled */
    }
    if (end_p > to_p) {
      *(to_p++)= (char) quote;
      if (end_p > to_p)
	*to_p= 0; /* terminate by NUL, but do not include it in the count */
    }
  }
  else
    to_p= strnmov(to_p, conv_name, end_p - to_p);
  DBUG_RETURN(to_p);
}


/**
  @brief Explain a path name by split it to database, table etc.
  
  @details Break down the path name to its logic parts
  (database, table, partition, subpartition).
  filename_to_tablename cannot be used on partitions, due to the #P# part.
  There can be up to 6 '#', #P# for partition, #SP# for subpartition
  and #TMP# or #REN# for temporary or renamed partitions.
  This should be used when something should be presented to a user in a
  diagnostic, error etc. when it would be useful to know what a particular
  file [and directory] means. Such as SHOW ENGINE STATUS, error messages etc.

  Examples:

    t1#P#p1                 table t1 partition p1
    t1#P#p1#SP#sp1          table t1 partition p1 subpartition sp1
    t1#P#p1#SP#sp1#TMP#     table t1 partition p1 subpartition sp1 temporary
    t1#P#p1#SP#sp1#REN#     table t1 partition p1 subpartition sp1 renamed

   @param      thd          Thread handle
   @param      from         Path name in my_charset_filename
                            Null terminated in my_charset_filename, normalized
                            to use '/' as directory separation character.
   @param      to           Explained name in system_charset_info
   @param      to_length    Size of to buffer
   @param      explain_mode Requested output format.
                            EXPLAIN_ALL_VERBOSE ->
                            [Database `db`, ]Table `tbl`[,[ Temporary| Renamed]
                            Partition `p` [, Subpartition `sp`]]
                            EXPLAIN_PARTITIONS_VERBOSE -> `db`.`tbl`
                            [[ Temporary| Renamed] Partition `p`
                            [, Subpartition `sp`]]
                            EXPLAIN_PARTITIONS_AS_COMMENT -> `db`.`tbl` |*
                            [,[ Temporary| Renamed] Partition `p`
                            [, Subpartition `sp`]] *|
                            (| is really a /, and it is all in one line)

   @retval     Length of returned string
*/

uint explain_filename(THD* thd,
		      const char *from,
                      char *to,
                      uint to_length,
                      enum_explain_filename_mode explain_mode)
{
  char *to_p= to;
  char *end_p= to_p + to_length;
  const char *db_name= NULL;
  int  db_name_len= 0;
  const char *table_name;
  int  table_name_len= 0;
  const char *part_name= NULL;
  int  part_name_len= 0;
  const char *subpart_name= NULL;
  int  subpart_name_len= 0;
  enum enum_part_name_type {NORMAL, TEMP, RENAMED} part_type= NORMAL;

  const char *tmp_p;
  DBUG_ENTER("explain_filename");
  DBUG_PRINT("enter", ("from '%s'", from));
  tmp_p= from;
  table_name= from;
  /*
    If '/' then take last directory part as database.
    '/' is the directory separator, not FN_LIB_CHAR
  */
  while ((tmp_p= strchr(tmp_p, '/')))
  {
    db_name= table_name;
    /* calculate the length */
    db_name_len= tmp_p - db_name;
    tmp_p++;
    table_name= tmp_p;
  }
  tmp_p= table_name;
  /* Look if there are partition tokens in the table name. */
  while ((tmp_p= strchr(tmp_p, '#')))
  {
    tmp_p++;
    switch (tmp_p[0]) {
    case 'P':
    case 'p':
      if (tmp_p[1] == '#')
      {
        part_name= tmp_p + 2;
        tmp_p+= 2;
      }
      break;
    case 'S':
    case 's':
      if ((tmp_p[1] == 'P' || tmp_p[1] == 'p') && tmp_p[2] == '#')
      {
        part_name_len= tmp_p - part_name - 1;
        subpart_name= tmp_p + 3;
        tmp_p+= 3;
      }
      break;
    case 'T':
    case 't':
      if ((tmp_p[1] == 'M' || tmp_p[1] == 'm') &&
          (tmp_p[2] == 'P' || tmp_p[2] == 'p') &&
          tmp_p[3] == '#' && !tmp_p[4])
      {
        part_type= TEMP;
        tmp_p+= 4;
      }
      break;
    case 'R':
    case 'r':
      if ((tmp_p[1] == 'E' || tmp_p[1] == 'e') &&
          (tmp_p[2] == 'N' || tmp_p[2] == 'n') &&
          tmp_p[3] == '#' && !tmp_p[4])
      {
        part_type= RENAMED;
        tmp_p+= 4;
      }
      break;
    default:
      /* Not partition name part. */
      ;
    }
  }
  if (part_name)
  {
    table_name_len= part_name - table_name - 3;
    if (subpart_name)
      subpart_name_len= strlen(subpart_name);
    else
      part_name_len= strlen(part_name);
    if (part_type != NORMAL)
    {
      if (subpart_name)
        subpart_name_len-= 5;
      else
        part_name_len-= 5;
    }
  }
  else
    table_name_len= strlen(table_name);
  if (db_name)
  {
    if (explain_mode == EXPLAIN_ALL_VERBOSE)
    {
      to_p= strnmov(to_p, ER_THD_OR_DEFAULT(thd, ER_DATABASE_NAME),
                                            end_p - to_p);
      *(to_p++)= ' ';
      to_p= add_identifier(thd, to_p, end_p, db_name, db_name_len);
      to_p= strnmov(to_p, ", ", end_p - to_p);
    }
    else
    {
      to_p= add_identifier(thd, to_p, end_p, db_name, db_name_len);
      to_p= strnmov(to_p, ".", end_p - to_p);
    }
  }
  if (explain_mode == EXPLAIN_ALL_VERBOSE)
  {
    to_p= strnmov(to_p, ER_THD_OR_DEFAULT(thd, ER_TABLE_NAME), end_p - to_p);
    *(to_p++)= ' ';
    to_p= add_identifier(thd, to_p, end_p, table_name, table_name_len);
  }
  else
    to_p= add_identifier(thd, to_p, end_p, table_name, table_name_len);
  if (part_name)
  {
    if (explain_mode == EXPLAIN_PARTITIONS_AS_COMMENT)
      to_p= strnmov(to_p, " /* ", end_p - to_p);
    else if (explain_mode == EXPLAIN_PARTITIONS_VERBOSE)
      to_p= strnmov(to_p, " ", end_p - to_p);
    else
      to_p= strnmov(to_p, ", ", end_p - to_p);
    if (part_type != NORMAL)
    {
      if (part_type == TEMP)
        to_p= strnmov(to_p, ER_THD_OR_DEFAULT(thd, ER_TEMPORARY_NAME),
                      end_p - to_p);
      else
        to_p= strnmov(to_p, ER_THD_OR_DEFAULT(thd, ER_RENAMED_NAME),
                      end_p - to_p);
      to_p= strnmov(to_p, " ", end_p - to_p);
    }
    to_p= strnmov(to_p, ER_THD_OR_DEFAULT(thd, ER_PARTITION_NAME),
                  end_p - to_p);
    *(to_p++)= ' ';
    to_p= add_identifier(thd, to_p, end_p, part_name, part_name_len);
    if (subpart_name)
    {
      to_p= strnmov(to_p, ", ", end_p - to_p);
      to_p= strnmov(to_p, ER_THD_OR_DEFAULT(thd, ER_SUBPARTITION_NAME),
                    end_p - to_p);
      *(to_p++)= ' ';
      to_p= add_identifier(thd, to_p, end_p, subpart_name, subpart_name_len);
    }
    if (explain_mode == EXPLAIN_PARTITIONS_AS_COMMENT)
      to_p= strnmov(to_p, " */", end_p - to_p);
  }
  DBUG_PRINT("exit", ("to '%s'", to));
  DBUG_RETURN(to_p - to);
}


/*
  Translate a file name to a table name (WL #1324).

  SYNOPSIS
    filename_to_tablename()
      from                      The file name in my_charset_filename.
      to                OUT     The table name in system_charset_info.
      to_length                 The size of the table name buffer.

  RETURN
    Table name length.
*/

uint filename_to_tablename(const char *from, char *to, uint to_length
#ifndef DBUG_OFF
                           , bool stay_quiet
#endif /* DBUG_OFF */
                           )
{
  uint errors;
  size_t res;
  DBUG_ENTER("filename_to_tablename");
  DBUG_PRINT("enter", ("from '%s'", from));

  if (strlen(from) >= tmp_file_prefix_length &&
      !memcmp(from, tmp_file_prefix, tmp_file_prefix_length))
  {
    /* Temporary table name. */
    res= (strnmov(to, from, to_length) - to);
  }
  else
  {
    res= strconvert(&my_charset_filename, from,
                    system_charset_info,  to, to_length, &errors);
    if (errors) // Old 5.0 name
    {
      res= (strxnmov(to, to_length, MYSQL50_TABLE_NAME_PREFIX,  from, NullS) -
            to);
#ifndef DBUG_OFF
      if (!stay_quiet) {
#endif /* DBUG_OFF */
        sql_print_error("Invalid (old?) table or database name '%s'", from);
#ifndef DBUG_OFF
      }
#endif /* DBUG_OFF */
      /*
        TODO: add a stored procedure for fix table and database names,
        and mention its name in error log.
      */
    }
  }

  DBUG_PRINT("exit", ("to '%s'", to));
  DBUG_RETURN(res);
}


/**
  Check if given string begins with "#mysql50#" prefix
  
  @param   name          string to check cut 
  
  @retval
    FALSE  no prefix found
  @retval
    TRUE   prefix found
*/

bool check_mysql50_prefix(const char *name)
{
  return (name[0] == '#' && 
         !strncmp(name, MYSQL50_TABLE_NAME_PREFIX,
                  MYSQL50_TABLE_NAME_PREFIX_LENGTH));
}


/**
  Check if given string begins with "#mysql50#" prefix, cut it if so.
  
  @param   from          string to check and cut 
  @param   to[out]       buffer for result string
  @param   to_length     its size
  
  @retval
    0      no prefix found
  @retval
    non-0  result string length
*/

uint check_n_cut_mysql50_prefix(const char *from, char *to, uint to_length)
{
  if (check_mysql50_prefix(from))
    return (uint) (strmake(to, from + MYSQL50_TABLE_NAME_PREFIX_LENGTH,
                           to_length - 1) - to);
  return 0;
}


/*
  Translate a table name to a file name (WL #1324).

  SYNOPSIS
    tablename_to_filename()
      from                      The table name in system_charset_info.
      to                OUT     The file name in my_charset_filename.
      to_length                 The size of the file name buffer.

  RETURN
    File name length.
*/

uint tablename_to_filename(const char *from, char *to, uint to_length)
{
  uint errors, length;
  DBUG_ENTER("tablename_to_filename");
  DBUG_PRINT("enter", ("from '%s'", from));

  if ((length= check_n_cut_mysql50_prefix(from, to, to_length)))
  {
    /*
      Check if the name supplied is a valid mysql 5.0 name and 
      make the name a zero length string if it's not.
      Note that just returning zero length is not enough : 
      a lot of places don't check the return value and expect 
      a zero terminated string.
    */  
    if (check_table_name(to, length, TRUE) != IDENT_NAME_OK)
    {
      to[0]= 0;
      length= 0;
    }
    DBUG_RETURN(length);
  }
  length= strconvert(system_charset_info, from,
                     &my_charset_filename, to, to_length, &errors);
  if (check_if_legal_tablename(to) &&
      length + 4 < to_length)
  {
    memcpy(to + length, "@@@", 4);
    length+= 3;
  }
  DBUG_PRINT("exit", ("to '%s'", to));
  DBUG_RETURN(length);
}


/*
  @brief Creates path to a file: mysql_data_dir/db/table.ext

  @param buff                   Where to write result in my_charset_filename.
                                This may be the same as table_name.
  @param bufflen                buff size
  @param db                     Database name in system_charset_info.
  @param table_name             Table name in system_charset_info.
  @param ext                    File extension.
  @param flags                  FN_FROM_IS_TMP or FN_TO_IS_TMP or FN_IS_TMP
                                table_name is temporary, do not change.
  @param was_truncated          points to location that will be
                                set to true if path was truncated,
                                to false otherwise.

  @note
    Uses database and table name, and extension to create
    a file name in mysql_data_dir. Database and table
    names are converted from system_charset_info into "fscs".
    Unless flags indicate a temporary table name.
    'db' is always converted.
    'ext' is not converted.

    The conversion suppression is required for ALTER TABLE. This
    statement creates intermediate tables. These are regular
    (non-temporary) tables with a temporary name. Their path names must
    be derivable from the table name. So we cannot use
    build_tmptable_filename() for them.

  @return
    path length
*/

uint build_table_filename(char *buff, size_t bufflen, const char *db,
                          const char *table_name, const char *ext,
                          uint flags, bool *was_truncated)
{
  char tbbuff[FN_REFLEN], dbbuff[FN_REFLEN];
  uint tab_len, db_len;
  DBUG_ENTER("build_table_filename");
  DBUG_PRINT("enter", ("db: '%s'  table_name: '%s'  ext: '%s'  flags: %x",
                       db, table_name, ext, flags));

  if (flags & FN_IS_TMP) // FN_FROM_IS_TMP | FN_TO_IS_TMP
    tab_len= strnmov(tbbuff, table_name, sizeof(tbbuff)) - tbbuff;
  else
    tab_len= tablename_to_filename(table_name, tbbuff, sizeof(tbbuff));

  db_len= tablename_to_filename(db, dbbuff, sizeof(dbbuff));

  char *end = buff + bufflen;
  /* Don't add FN_ROOTDIR if mysql_data_home already includes it */
  char *pos = strnmov(buff, mysql_data_home, bufflen);
  size_t rootdir_len= strlen(FN_ROOTDIR);
  if (pos - rootdir_len >= buff &&
      memcmp(pos - rootdir_len, FN_ROOTDIR, rootdir_len) != 0)
    pos= strnmov(pos, FN_ROOTDIR, end - pos);
  else
      rootdir_len= 0;
  pos= strxnmov(pos, end - pos, dbbuff, FN_ROOTDIR, NullS);
#ifdef USE_SYMDIR
  if (!(flags & SKIP_SYMDIR_ACCESS))
  {
    my_bool is_symdir;

    unpack_dirname(buff, buff, &is_symdir);
    /*
      Lack of synchronization for access to symdir_warning_emitted is OK
      as in the worst case it might result in a few extra warnings
      printed to error log.
    */
    if (is_symdir && !symdir_warning_emitted)
    {
      symdir_warning_emitted= true;
      sql_print_warning("Symbolic links based on .sym files are deprecated. "
                        "Please use native Windows symbolic links instead "
                        "(see MKLINK command).");
    }
    pos= strend(buff);
  }
#endif
  pos= strxnmov(pos, end - pos, tbbuff, ext, NullS);

  /**
    Mark OUT param if path gets truncated.
    Most of functions which invoke this function are sure that the
    path will not be truncated. In case some functions are not sure,
    we can use 'was_truncated' OUTPARAM
  */
  *was_truncated= false;
  if (pos == end &&
      (bufflen < mysql_data_home_len + rootdir_len + db_len +
                 strlen(FN_ROOTDIR) + tab_len + strlen(ext)))
    *was_truncated= true;

  DBUG_PRINT("exit", ("buff: '%s'", buff));
  DBUG_RETURN(pos - buff);
}


/**
  Create path to a temporary table mysql_tmpdir/#sql1234_12_1
  (i.e. to its .FRM file but without an extension).

  @param thd      The thread handle.
  @param buff     Where to write result in my_charset_filename.
  @param bufflen  buff size

  @note
    Uses current_pid, thread_id, and tmp_table counter to create
    a file name in mysql_tmpdir.

  @return Path length.
*/

uint build_tmptable_filename(THD* thd, char *buff, size_t bufflen)
{
  DBUG_ENTER("build_tmptable_filename");

  char *p= strnmov(buff, mysql_tmpdir, bufflen);
  my_snprintf(p, bufflen - (p - buff), "/%s%lx_%lx_%x",
              tmp_file_prefix, current_pid,
              thd->thread_id, thd->tmp_table++);

  if (lower_case_table_names)
  {
    /* Convert all except tmpdir to lower case */
    my_casedn_str(files_charset_info, p);
  }

  size_t length= unpack_filename(buff, buff);
  DBUG_PRINT("exit", ("buff: '%s'", buff));
  DBUG_RETURN(length);
}

/*
  Check TYPELIB (set or enum) for duplicates

  SYNOPSIS
    check_duplicates_in_interval()
    set_or_name   "SET" or "ENUM" string for warning message
    name	  name of the checked column
    typelib	  list of values for the column
    dup_val_count  returns count of duplicate elements

  DESCRIPTION
    This function prints an warning for each value in list
    which has some duplicates on its right

  RETURN VALUES
    0             ok
    1             Error
*/

bool check_duplicates_in_interval(const char *set_or_name,
                                  const char *name, TYPELIB *typelib,
                                  const CHARSET_INFO *cs, uint *dup_val_count)
{
  TYPELIB tmp= *typelib;
  const char **cur_value= typelib->type_names;
  unsigned int *cur_length= typelib->type_lengths;
  *dup_val_count= 0;  
  
  for ( ; tmp.count > 1; cur_value++, cur_length++)
  {
    tmp.type_names++;
    tmp.type_lengths++;
    tmp.count--;
    if (find_type2(&tmp, (const char*)*cur_value, *cur_length, cs))
    {
      THD *thd= current_thd;
      ErrConvString err(*cur_value, *cur_length, cs);
      if (current_thd->is_strict_mode())
      {
        my_error(ER_DUPLICATED_VALUE_IN_TYPE, MYF(0),
                 name, err.ptr(), set_or_name);
        return 1;
      }
      push_warning_printf(thd,Sql_condition::WARN_LEVEL_NOTE,
                          ER_DUPLICATED_VALUE_IN_TYPE,
                          ER(ER_DUPLICATED_VALUE_IN_TYPE),
                          name, err.ptr(), set_or_name);
      (*dup_val_count)++;
    }
  }
  return 0;
}


/*
  Check TYPELIB (set or enum) max and total lengths

  SYNOPSIS
    calculate_interval_lengths()
    cs            charset+collation pair of the interval
    typelib       list of values for the column
    max_length    length of the longest item
    tot_length    sum of the item lengths

  DESCRIPTION
    After this function call:
    - ENUM uses max_length
    - SET uses tot_length.

  RETURN VALUES
    void
*/
static void calculate_interval_lengths(const CHARSET_INFO *cs,
                                       TYPELIB *interval,
                                       uint32 *max_length,
                                       uint32 *tot_length)
{
  const char **pos;
  uint *len;
  *max_length= *tot_length= 0;
  for (pos= interval->type_names, len= interval->type_lengths;
       *pos ; pos++, len++)
  {
    size_t length= cs->cset->numchars(cs, *pos, *pos + *len);
    *tot_length+= length;
    set_if_bigger(*max_length, (uint32)length);
  }
}



enum_field_types get_blob_type_from_length(ulong length)
{
  enum_field_types type;
  if (length < 256)
    type= MYSQL_TYPE_TINY_BLOB;
  else if (length < 65536)
    type= MYSQL_TYPE_BLOB;
  else if (length < 256L*256L*256L)
    type= MYSQL_TYPE_MEDIUM_BLOB;
  else
    type= MYSQL_TYPE_LONG_BLOB;
  return type;
}


/*
  Make a field from the .frm file info
*/

uint32 calc_pack_length(enum_field_types type,uint32 length)
{
  switch (type) {
    case MYSQL_TYPE_VAR_STRING:
    case MYSQL_TYPE_STRING:
    case MYSQL_TYPE_DECIMAL:     return (length);
    case MYSQL_TYPE_VARCHAR:     return (length + (length < 256 ? 1: 2));
    case MYSQL_TYPE_YEAR:
    case MYSQL_TYPE_TINY	: return 1;
    case MYSQL_TYPE_SHORT : return 2;
    case MYSQL_TYPE_INT24:
    case MYSQL_TYPE_NEWDATE: return 3;
    case MYSQL_TYPE_TIME: return 3;
    case MYSQL_TYPE_TIME2:
      return length > MAX_TIME_WIDTH ?
             my_time_binary_length(length - MAX_TIME_WIDTH - 1) : 3;
    case MYSQL_TYPE_TIMESTAMP: return 4;
    case MYSQL_TYPE_TIMESTAMP2:
      return length > MAX_DATETIME_WIDTH ?
             my_timestamp_binary_length(length - MAX_DATETIME_WIDTH - 1) : 4;
    case MYSQL_TYPE_DATE:
    case MYSQL_TYPE_LONG	: return 4;
    case MYSQL_TYPE_FLOAT : return sizeof(float);
    case MYSQL_TYPE_DOUBLE: return sizeof(double);
    case MYSQL_TYPE_DATETIME: return 8;
    case MYSQL_TYPE_DATETIME2:
      return length > MAX_DATETIME_WIDTH ?
             my_datetime_binary_length(length - MAX_DATETIME_WIDTH - 1) : 5;
    case MYSQL_TYPE_LONGLONG: return 8;	/* Don't crash if no longlong */
    case MYSQL_TYPE_NULL	: return 0;
    case MYSQL_TYPE_TINY_BLOB:	return 1+portable_sizeof_char_ptr;
    case MYSQL_TYPE_BLOB:		return 2+portable_sizeof_char_ptr;
    case MYSQL_TYPE_MEDIUM_BLOB:	return 3+portable_sizeof_char_ptr;
    case MYSQL_TYPE_LONG_BLOB:	return 4+portable_sizeof_char_ptr;
    case MYSQL_TYPE_GEOMETRY:	return 4+portable_sizeof_char_ptr;
    case MYSQL_TYPE_SET:
    case MYSQL_TYPE_ENUM:
    case MYSQL_TYPE_NEWDECIMAL:
      abort(); return 0;                          // This shouldn't happen
    case MYSQL_TYPE_BIT: return length / 8;
    default:
      return 0;
  }
}

#define MTYP_TYPENR(type) (type & 127)	/* Remove bits from type */

#define f_is_dec(x)		((x) & FIELDFLAG_DECIMAL)
#define f_is_num(x)		((x) & FIELDFLAG_NUMBER)
#define f_is_zerofill(x)	((x) & FIELDFLAG_ZEROFILL)
#define f_is_packed(x)		((x) & FIELDFLAG_PACK)
#define f_packtype(x)		(((x) >> FIELDFLAG_PACK_SHIFT) & 15)
#define f_decimals(x)		((uint8) (((x) >> FIELDFLAG_DEC_SHIFT) & FIELDFLAG_MAX_DEC))
#define f_is_alpha(x)		(!f_is_num(x))
#define f_is_binary(x)          ((x) & FIELDFLAG_BINARY) // 4.0- compatibility
#define f_is_enum(x)            (((x) & (FIELDFLAG_INTERVAL | FIELDFLAG_NUMBER)) == FIELDFLAG_INTERVAL)
#define f_is_bitfield(x)        (((x) & (FIELDFLAG_BITFIELD | FIELDFLAG_NUMBER)) == FIELDFLAG_BITFIELD)
#define f_is_blob(x)		(((x) & (FIELDFLAG_BLOB | FIELDFLAG_NUMBER)) == FIELDFLAG_BLOB)
#define f_is_geom(x)		(((x) & (FIELDFLAG_GEOM | FIELDFLAG_NUMBER)) == FIELDFLAG_GEOM)
#define f_is_equ(x)		((x) & (1+2+FIELDFLAG_PACK+31*256))
#define f_settype(x)		(((int) x) << FIELDFLAG_PACK_SHIFT)
#define f_maybe_null(x)		(x & FIELDFLAG_MAYBE_NULL)
#define f_no_default(x)		(x & FIELDFLAG_NO_DEFAULT)
#define f_bit_as_char(x)        ((x) & FIELDFLAG_TREAT_BIT_AS_CHAR)
#define f_is_hex_escape(x)      ((x) & FIELDFLAG_HEX_ESCAPE)

uint pack_length_to_packflag(uint type)
{
  switch (type) {
    case 1: return f_settype((uint) MYSQL_TYPE_TINY);
    case 2: return f_settype((uint) MYSQL_TYPE_SHORT);
    case 3: return f_settype((uint) MYSQL_TYPE_INT24);
    case 4: return f_settype((uint) MYSQL_TYPE_LONG);
    case 8: return f_settype((uint) MYSQL_TYPE_LONGLONG);
  }
  return 0;					// This shouldn't happen
}


bool Create_field::init(THD *thd, const char *fld_name,
                        enum_field_types fld_type, const char *fld_length,
                        const char *fld_decimals, uint fld_type_modifier,
                        Item *fld_default_value, Item *fld_on_update_value,
                        LEX_STRING *fld_comment, const char *fld_change,
                        List<String> *fld_interval_list,
                        const CHARSET_INFO *fld_charset, uint fld_geom_type)
{
  uint sign_len, allowed_type_modifier= 0;
  ulong max_field_charlength= MAX_FIELD_CHARLENGTH;

  DBUG_ENTER("Create_field::init()");

  field_name= fld_name;
  flags= fld_type_modifier;
  charset= fld_charset;


  if (fld_default_value != NULL && fld_default_value->type() == Item::FUNC_ITEM)
  {
    // We have a function default for insertions.
    def= NULL;
  }
  else
  {
    // No function default for insertions. Either NULL or a constant.
    def= fld_default_value;
  }

  decimals= fld_decimals ? (uint)atoi(fld_decimals) : 0;
  if (is_temporal_real_type(fld_type))
  {
    flags|= BINARY_FLAG;
    charset= &my_charset_numeric;
    if (decimals > DATETIME_MAX_DECIMALS)
    {
      my_error(ER_TOO_BIG_PRECISION, MYF(0),
               decimals, fld_name, DATETIME_MAX_DECIMALS);
      DBUG_RETURN(TRUE);
    }
  }
  else if (decimals >= NOT_FIXED_DEC)
  {
    my_error(ER_TOO_BIG_SCALE, MYF(0), decimals, fld_name,
             static_cast<ulong>(NOT_FIXED_DEC - 1));
    DBUG_RETURN(TRUE);
  }

  sql_type= fld_type;
  length= 0;
  change= fld_change;
  interval= 0;
  pack_length= key_length= 0;
  geom_type= (geometry_type) fld_geom_type;
  interval_list.empty();

  comment= *fld_comment;
  /*
    Set NO_DEFAULT_VALUE_FLAG if this field doesn't have a default value and
    it is NOT NULL and not an AUTO_INCREMENT field.
  */
  if (!fld_default_value &&
      (fld_type_modifier & NOT_NULL_FLAG) &&
      !(fld_type_modifier & AUTO_INCREMENT_FLAG))
  {
    /*
      TIMESTAMP columns get implicit DEFAULT value when
      explicit_defaults_for_timestamp is not set.
    */
    if (thd->variables.explicit_defaults_for_timestamp ||
        !is_timestamp_type(fld_type))
    {
      flags|= NO_DEFAULT_VALUE_FLAG;
    }
  }

  if (fld_length != NULL)
  {
    errno= 0;
    length= strtoul(fld_length, NULL, 10);
    if ((errno != 0) || (length > MAX_FIELD_BLOBLENGTH))
    {
      my_error(ER_TOO_BIG_DISPLAYWIDTH, MYF(0), fld_name, MAX_FIELD_BLOBLENGTH);
      DBUG_RETURN(TRUE);
    }

    if (length == 0)
      fld_length= NULL; /* purecov: inspected */
  }

  sign_len= fld_type_modifier & UNSIGNED_FLAG ? 0 : 1;

  switch (fld_type) {
    case MYSQL_TYPE_TINY:
      if (!fld_length)
        length= MAX_TINYINT_WIDTH+sign_len;
          allowed_type_modifier= AUTO_INCREMENT_FLAG;
          break;
    case MYSQL_TYPE_SHORT:
      if (!fld_length)
        length= MAX_SMALLINT_WIDTH+sign_len;
          allowed_type_modifier= AUTO_INCREMENT_FLAG;
          break;
    case MYSQL_TYPE_INT24:
      if (!fld_length)
        length= MAX_MEDIUMINT_WIDTH+sign_len;
          allowed_type_modifier= AUTO_INCREMENT_FLAG;
          break;
    case MYSQL_TYPE_LONG:
      if (!fld_length)
        length= MAX_INT_WIDTH+sign_len;
          allowed_type_modifier= AUTO_INCREMENT_FLAG;
          break;
    case MYSQL_TYPE_LONGLONG:
      if (!fld_length)
        length= MAX_BIGINT_WIDTH;
          allowed_type_modifier= AUTO_INCREMENT_FLAG;
          break;
    case MYSQL_TYPE_NULL:
      break;
    case MYSQL_TYPE_NEWDECIMAL:
      my_decimal_trim(&length, &decimals);
          if (length > DECIMAL_MAX_PRECISION)
          {
            my_error(ER_TOO_BIG_PRECISION, MYF(0), static_cast<int>(length),
                     fld_name, static_cast<ulong>(DECIMAL_MAX_PRECISION));
            DBUG_RETURN(TRUE);
          }
          if (length < decimals)
          {
            my_error(ER_M_BIGGER_THAN_D, MYF(0), fld_name);
            DBUG_RETURN(TRUE);
          }
          length=
                  my_decimal_precision_to_length(length, decimals,
                                                 fld_type_modifier & UNSIGNED_FLAG);
          pack_length=
                  my_decimal_get_binary_size(length, decimals);
          break;
    case MYSQL_TYPE_VARCHAR:
      /*
        Long VARCHAR's are automaticly converted to blobs in mysql_prepare_table
        if they don't have a default value
      */
      max_field_charlength= MAX_FIELD_VARCHARLENGTH;
          break;
    case MYSQL_TYPE_STRING:
      break;
    case MYSQL_TYPE_BLOB:
    case MYSQL_TYPE_TINY_BLOB:
    case MYSQL_TYPE_LONG_BLOB:
    case MYSQL_TYPE_MEDIUM_BLOB:
    case MYSQL_TYPE_GEOMETRY:
      if (fld_default_value)
      {
        /* Allow empty as default value. */
        String str,*res;
        res= fld_default_value->val_str(&str);
        /*
          A default other than '' is always an error, and any non-NULL
          specified default is an error in strict mode.
        */
        if (res->length() || thd->is_strict_mode())
        {
          my_error(ER_BLOB_CANT_HAVE_DEFAULT, MYF(0),
                   fld_name); /* purecov: inspected */
          DBUG_RETURN(TRUE);
        }
        else
        {
          /*
            Otherwise a default of '' is just a warning.
          */
          push_warning_printf(thd, Sql_condition::WARN_LEVEL_WARN,
                              ER_BLOB_CANT_HAVE_DEFAULT,
                              ER(ER_BLOB_CANT_HAVE_DEFAULT),
                              fld_name);
        }
        def= 0;
      }
          flags|= BLOB_FLAG;
          break;
    case MYSQL_TYPE_YEAR:
      if (!fld_length || length != 2)
        length= 4; /* Default length */
          flags|= ZEROFILL_FLAG | UNSIGNED_FLAG;
          break;
    case MYSQL_TYPE_FLOAT:
      /* change FLOAT(precision) to FLOAT or DOUBLE */
      allowed_type_modifier= AUTO_INCREMENT_FLAG;
          if (fld_length && !fld_decimals)
          {
            uint tmp_length= length;
            if (tmp_length > PRECISION_FOR_DOUBLE)
            {
              my_error(ER_WRONG_FIELD_SPEC, MYF(0), fld_name);
              DBUG_RETURN(TRUE);
            }
            else if (tmp_length > PRECISION_FOR_FLOAT)
            {
              sql_type= MYSQL_TYPE_DOUBLE;
              length= MAX_DOUBLE_STR_LENGTH;
            }
            else
              length= MAX_FLOAT_STR_LENGTH;
            decimals= NOT_FIXED_DEC;
            break;
          }
          if (!fld_length && !fld_decimals)
          {
            length=  MAX_FLOAT_STR_LENGTH;
            decimals= NOT_FIXED_DEC;
          }
          if (length < decimals &&
              decimals != NOT_FIXED_DEC)
          {
            my_error(ER_M_BIGGER_THAN_D, MYF(0), fld_name);
            DBUG_RETURN(TRUE);
          }
          break;
    case MYSQL_TYPE_DOUBLE:
      allowed_type_modifier= AUTO_INCREMENT_FLAG;
          if (!fld_length && !fld_decimals)
          {
            length= DBL_DIG+7;
            decimals= NOT_FIXED_DEC;
          }
          if (length < decimals &&
              decimals != NOT_FIXED_DEC)
          {
            my_error(ER_M_BIGGER_THAN_D, MYF(0), fld_name);
            DBUG_RETURN(TRUE);
          }
          break;
    case MYSQL_TYPE_TIMESTAMP:
      /* Add flags for TIMESTAMP for 4.0 MYD and 4.0 InnoDB compatibility */
      flags|= ZEROFILL_FLAG | UNSIGNED_FLAG;
          /* Fall through */
    case MYSQL_TYPE_TIMESTAMP2:
      if (fld_length == NULL)
      {
        length= MAX_DATETIME_WIDTH + (decimals ? (1 + decimals) : 0);
      }
      else if (length != MAX_DATETIME_WIDTH)
      {
        /*
          We support only even TIMESTAMP lengths less or equal than 14
          and 19 as length of 4.1 compatible representation.  Silently
          shrink it to MAX_DATETIME_COMPRESSED_WIDTH.
        */
        DBUG_ASSERT(MAX_DATETIME_COMPRESSED_WIDTH < UINT_MAX);
        if (length != UINT_MAX)  /* avoid overflow; is safe because of min() */
          length= ((length+1)/2)*2;
        length= min<ulong>(length, MAX_DATETIME_COMPRESSED_WIDTH);
      }

          /*
            Since we silently rewrite down to MAX_DATETIME_COMPRESSED_WIDTH bytes,
            the parser should not raise errors unless bizzarely large.
           */
          max_field_charlength= UINT_MAX;

          break;
    case MYSQL_TYPE_DATE:
      /* Old date type. */
      sql_type= MYSQL_TYPE_NEWDATE;
          /* fall trough */
    case MYSQL_TYPE_NEWDATE:
      length= MAX_DATE_WIDTH;
          break;
    case MYSQL_TYPE_TIME:
    case MYSQL_TYPE_TIME2:
      length= MAX_TIME_WIDTH + (decimals ? (1 + decimals) : 0);
          break;
    case MYSQL_TYPE_DATETIME:
    case MYSQL_TYPE_DATETIME2:
      length= MAX_DATETIME_WIDTH + (decimals ? (1 + decimals) : 0);
          break;
    case MYSQL_TYPE_SET:
    {
      pack_length= get_set_pack_length(fld_interval_list->elements);

      List_iterator<String> it(*fld_interval_list);
      String *tmp;
      while ((tmp= it++))
        interval_list.push_back(tmp);
      /*
        Set fake length to 1 to pass the below conditions.
        Real length will be set in mysql_prepare_table()
        when we know the character set of the column
      */
      length= 1;
      break;
    }
    case MYSQL_TYPE_ENUM:
    {
      /* Should be safe. */
      pack_length= get_enum_pack_length(fld_interval_list->elements);

      List_iterator<String> it(*fld_interval_list);
      String *tmp;
      while ((tmp= it++))
        interval_list.push_back(tmp);
      length= 1; /* See comment for MYSQL_TYPE_SET above. */
      break;
    }
    case MYSQL_TYPE_VAR_STRING:
      DBUG_ASSERT(0);  /* Impossible. */
          break;
    case MYSQL_TYPE_BIT:
    {
      if (!fld_length)
        length= 1;
      if (length > MAX_BIT_FIELD_LENGTH)
      {
        my_error(ER_TOO_BIG_DISPLAYWIDTH, MYF(0), fld_name,
                 static_cast<ulong>(MAX_BIT_FIELD_LENGTH));
        DBUG_RETURN(TRUE);
      }
      pack_length= (length + 7) / 8;
      break;
    }
    case MYSQL_TYPE_DECIMAL:
      DBUG_ASSERT(0); /* Was obsolete */
  }
  /* Remember the value of length */
  char_length= length;

  if (!(flags & BLOB_FLAG) &&
      ((length > max_field_charlength && fld_type != MYSQL_TYPE_SET &&
        fld_type != MYSQL_TYPE_ENUM &&
        (fld_type != MYSQL_TYPE_VARCHAR || fld_default_value)) ||
       ((length == 0) &&
        fld_type != MYSQL_TYPE_STRING &&
        fld_type != MYSQL_TYPE_VARCHAR && fld_type != MYSQL_TYPE_GEOMETRY)))
  {
    my_error((fld_type == MYSQL_TYPE_VAR_STRING ||
              fld_type == MYSQL_TYPE_VARCHAR ||
              fld_type == MYSQL_TYPE_STRING) ?  ER_TOO_BIG_FIELDLENGTH :
             ER_TOO_BIG_DISPLAYWIDTH,
             MYF(0),
             fld_name, max_field_charlength); /* purecov: inspected */
    DBUG_RETURN(TRUE);
  }
  fld_type_modifier&= AUTO_INCREMENT_FLAG;
  if ((~allowed_type_modifier) & fld_type_modifier)
  {
    my_error(ER_WRONG_FIELD_SPEC, MYF(0), fld_name);
    DBUG_RETURN(TRUE);
  }

  DBUG_RETURN(FALSE); /* success */
}


/**
  Convert create_field::length from number of characters to number of bytes.
*/

void Create_field::create_length_to_internal_length(void)
{
  switch (sql_type) {
    case MYSQL_TYPE_TINY_BLOB:
    case MYSQL_TYPE_MEDIUM_BLOB:
    case MYSQL_TYPE_LONG_BLOB:
    case MYSQL_TYPE_BLOB:
    case MYSQL_TYPE_GEOMETRY:
    case MYSQL_TYPE_VAR_STRING:
    case MYSQL_TYPE_STRING:
    case MYSQL_TYPE_VARCHAR:
      length*= charset->mbmaxlen;
          key_length= length;
          pack_length= calc_pack_length(sql_type, length);
          break;
    case MYSQL_TYPE_ENUM:
    case MYSQL_TYPE_SET:
      /* Pack_length already calculated in sql_parse.cc */
      length*= charset->mbmaxlen;
          key_length= pack_length;
          break;
    case MYSQL_TYPE_BIT:
      if (f_bit_as_char(pack_flag))
      {
        key_length= pack_length= ((length + 7) & ~7) / 8;
      }
      else
      {
        pack_length= length / 8;
        /* We need one extra byte to store the bits we save among the null bits */
        key_length= pack_length + MY_TEST(length & 7);
      }
          break;
    case MYSQL_TYPE_NEWDECIMAL:
      key_length= pack_length=
              my_decimal_get_binary_size(my_decimal_length_to_precision(length,
                                                                        decimals,
                                                                        flags &
                                                                        UNSIGNED_FLAG),
                                         decimals);
          break;
    default:
      key_length= pack_length= calc_pack_length(sql_type, length);
          break;
  }
}


/*
  Prepare a create_table instance for packing

  SYNOPSIS
    prepare_create_field()
    sql_field     field to prepare for packing
    blob_columns  count for BLOBs
    table_flags   table flags

  DESCRIPTION
    This function prepares a Create_field instance.
    Fields such as pack_flag are valid after this call.

  RETURN VALUES
   0	ok
   1	Error
*/

int prepare_create_field(Create_field *sql_field, 
			 uint *blob_columns, 
			 longlong table_flags)
{
  unsigned int dup_val_count;
  DBUG_ENTER("prepare_field");

  /*
    This code came from mysql_prepare_create_table.
    Indent preserved to make patching easier
  */
  DBUG_ASSERT(sql_field->charset);

  switch (sql_field->sql_type) {
  case MYSQL_TYPE_BLOB:
  case MYSQL_TYPE_MEDIUM_BLOB:
  case MYSQL_TYPE_TINY_BLOB:
  case MYSQL_TYPE_LONG_BLOB:
    sql_field->pack_flag=FIELDFLAG_BLOB |
      pack_length_to_packflag(sql_field->pack_length -
                              portable_sizeof_char_ptr);
    if (sql_field->charset->state & MY_CS_BINSORT)
      sql_field->pack_flag|=FIELDFLAG_BINARY;
    sql_field->length=8;			// Unireg field length
    sql_field->unireg_check=BLOB_FIELD;
    (*blob_columns)++;
    break;
  case MYSQL_TYPE_GEOMETRY:
#ifdef HAVE_SPATIAL
    if (!(table_flags & HA_CAN_GEOMETRY))
    {
      my_printf_error(ER_CHECK_NOT_IMPLEMENTED, ER(ER_CHECK_NOT_IMPLEMENTED),
                      MYF(0), "GEOMETRY");
      DBUG_RETURN(1);
    }
    sql_field->pack_flag=FIELDFLAG_GEOM |
      pack_length_to_packflag(sql_field->pack_length -
                              portable_sizeof_char_ptr);
    if (sql_field->charset->state & MY_CS_BINSORT)
      sql_field->pack_flag|=FIELDFLAG_BINARY;
    sql_field->length=8;			// Unireg field length
    sql_field->unireg_check=BLOB_FIELD;
    (*blob_columns)++;
    break;
#else
    my_printf_error(ER_FEATURE_DISABLED,ER(ER_FEATURE_DISABLED), MYF(0),
                    sym_group_geom.name, sym_group_geom.needed_define);
    DBUG_RETURN(1);
#endif /*HAVE_SPATIAL*/
  case MYSQL_TYPE_VARCHAR:
#ifndef QQ_ALL_HANDLERS_SUPPORT_VARCHAR
    if (table_flags & HA_NO_VARCHAR)
    {
      /* convert VARCHAR to CHAR because handler is not yet up to date */
      sql_field->sql_type=    MYSQL_TYPE_VAR_STRING;
      sql_field->pack_length= calc_pack_length(sql_field->sql_type,
                                               (uint) sql_field->length);
      if ((sql_field->length / sql_field->charset->mbmaxlen) >
          MAX_FIELD_CHARLENGTH)
      {
        my_printf_error(ER_TOO_BIG_FIELDLENGTH, ER(ER_TOO_BIG_FIELDLENGTH),
                        MYF(0), sql_field->field_name,
                        static_cast<ulong>(MAX_FIELD_CHARLENGTH));
        DBUG_RETURN(1);
      }
    }
#endif
    /* fall through */
  case MYSQL_TYPE_STRING:
    sql_field->pack_flag=0;
    if (sql_field->charset->state & MY_CS_BINSORT)
      sql_field->pack_flag|=FIELDFLAG_BINARY;
    break;
  case MYSQL_TYPE_ENUM:
    sql_field->pack_flag=pack_length_to_packflag(sql_field->pack_length) |
      FIELDFLAG_INTERVAL;
    if (sql_field->charset->state & MY_CS_BINSORT)
      sql_field->pack_flag|=FIELDFLAG_BINARY;
    sql_field->unireg_check=INTERVAL_FIELD;
    if (check_duplicates_in_interval("ENUM",sql_field->field_name,
                                     sql_field->interval,
                                     sql_field->charset, &dup_val_count))
      DBUG_RETURN(1);
    break;
  case MYSQL_TYPE_SET:
    sql_field->pack_flag=pack_length_to_packflag(sql_field->pack_length) |
      FIELDFLAG_BITFIELD;
    if (sql_field->charset->state & MY_CS_BINSORT)
      sql_field->pack_flag|=FIELDFLAG_BINARY;
    sql_field->unireg_check=BIT_FIELD;
    if (check_duplicates_in_interval("SET",sql_field->field_name,
                                     sql_field->interval,
                                     sql_field->charset, &dup_val_count))
      DBUG_RETURN(1);
    /* Check that count of unique members is not more then 64 */
    if (sql_field->interval->count -  dup_val_count > sizeof(longlong)*8)
    {
       my_error(ER_TOO_BIG_SET, MYF(0), sql_field->field_name);
       DBUG_RETURN(1);
    }
    break;
  case MYSQL_TYPE_DATE:			// Rest of string types
  case MYSQL_TYPE_NEWDATE:
  case MYSQL_TYPE_TIME:
  case MYSQL_TYPE_DATETIME:
  case MYSQL_TYPE_TIME2:
  case MYSQL_TYPE_DATETIME2:
  case MYSQL_TYPE_NULL:
    sql_field->pack_flag=f_settype((uint) sql_field->sql_type);
    break;
  case MYSQL_TYPE_BIT:
    /* 
      We have sql_field->pack_flag already set here, see
      mysql_prepare_create_table().
    */
    break;
  case MYSQL_TYPE_NEWDECIMAL:
    sql_field->pack_flag=(FIELDFLAG_NUMBER |
                          (sql_field->flags & UNSIGNED_FLAG ? 0 :
                           FIELDFLAG_DECIMAL) |
                          (sql_field->flags & ZEROFILL_FLAG ?
                           FIELDFLAG_ZEROFILL : 0) |
                          (sql_field->decimals << FIELDFLAG_DEC_SHIFT));
    break;
  case MYSQL_TYPE_TIMESTAMP:
  case MYSQL_TYPE_TIMESTAMP2:
    /* fall-through */
  default:
    sql_field->pack_flag=(FIELDFLAG_NUMBER |
                          (sql_field->flags & UNSIGNED_FLAG ? 0 :
                           FIELDFLAG_DECIMAL) |
                          (sql_field->flags & ZEROFILL_FLAG ?
                           FIELDFLAG_ZEROFILL : 0) |
                          f_settype((uint) sql_field->sql_type) |
                          (sql_field->decimals << FIELDFLAG_DEC_SHIFT));
    break;
  }
  if (!(sql_field->flags & NOT_NULL_FLAG))
    sql_field->pack_flag|= FIELDFLAG_MAYBE_NULL;
  if (sql_field->flags & NO_DEFAULT_VALUE_FLAG)
    sql_field->pack_flag|= FIELDFLAG_NO_DEFAULT;
  DBUG_RETURN(0);
}


static TYPELIB *create_typelib(MEM_ROOT *mem_root,
                               Create_field *field_def,
                               List<String> *src)
{
  const CHARSET_INFO *cs= field_def->charset;

  if (!src->elements)
    return NULL;

  TYPELIB *result= (TYPELIB*) alloc_root(mem_root, sizeof(TYPELIB));
  result->count= src->elements;
  result->name= "";
  if (!(result->type_names=(const char **)
        alloc_root(mem_root,(sizeof(char *)+sizeof(int))*(result->count+1))))
    return NULL;
  result->type_lengths= (uint*)(result->type_names + result->count+1);
  List_iterator<String> it(*src);
  String conv;
  for (uint i=0; i < result->count; i++)
  {
    uint32 dummy;
    uint length;
    String *tmp= it++;

    if (String::needs_conversion(tmp->length(), tmp->charset(),
                                 cs, &dummy))
    {
      uint cnv_errs;
      conv.copy(tmp->ptr(), tmp->length(), tmp->charset(), cs, &cnv_errs);

      length= conv.length();
      result->type_names[i]= (char*) strmake_root(mem_root, conv.ptr(),
                                                  length);
    }
    else
    {
      length= tmp->length();
      result->type_names[i]= strmake_root(mem_root, tmp->ptr(), length);
    }

    // Strip trailing spaces.
    length= cs->cset->lengthsp(cs, result->type_names[i], length);
    result->type_lengths[i]= length;
    ((uchar *)result->type_names[i])[length]= '\0';
  }
  result->type_names[result->count]= 0;
  result->type_lengths[result->count]= 0;

  return result;
}


/**
  Prepare an instance of Create_field for field creation
  (fill all necessary attributes).

  @param[in]  thd          Thread handle
  @param[in]  sp           The current SP
  @param[in]  field_type   Field type
  @param[out] field_def    An instance of create_field to be filled

  @return Error status.
*/

bool fill_field_definition(THD *thd,
                           sp_head *sp,
                           enum enum_field_types field_type,
                           Create_field *field_def)
{
  LEX *lex= thd->lex;
  LEX_STRING cmt = { 0, 0 };
  uint unused1= 0;

  if (field_def->init(thd, (char*) "", field_type, lex->length, lex->dec,
                      lex->type, (Item*) 0, (Item*) 0, &cmt, 0,
                      &lex->interval_list,
                      lex->charset ? lex->charset :
                                     thd->variables.collation_database,
                      lex->uint_geom_type))
  {
    return true;
  }

  if (field_def->interval_list.elements)
  {
    field_def->interval= create_typelib(sp->get_current_mem_root(),
                                        field_def,
                                        &field_def->interval_list);
  }

  sp_prepare_create_field(thd, field_def);

  return prepare_create_field(field_def, &unused1, HA_CAN_GEOMETRY);
}

/*
  Get character set from field object generated by parser using
  default values when not set.

  SYNOPSIS
    get_sql_field_charset()
    sql_field                 The sql_field object
    create_info               Info generated by parser

  RETURN VALUES
    cs                        Character set
*/

const CHARSET_INFO* get_sql_field_charset(Create_field *sql_field,
                                          HA_CREATE_INFO *create_info)
{
  const CHARSET_INFO *cs= sql_field->charset;

  if (!cs)
    cs= create_info->default_table_charset;
  /*
    table_charset is set only in ALTER TABLE t1 CONVERT TO CHARACTER SET csname
    if we want change character set for all varchar/char columns.
    But the table charset must not affect the BLOB fields, so don't
    allow to change my_charset_bin to somethig else.
  */
  if (create_info->table_charset && cs != &my_charset_bin)
    cs= create_info->table_charset;
  return cs;
}


/**
   Modifies the first column definition whose SQL type is TIMESTAMP
   by adding the features DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP.

   @param column_definitions The list of column definitions, in the physical
                             order in which they appear in the table.
 */
void promote_first_timestamp_column(List<Create_field> *column_definitions)
{
  List_iterator<Create_field> it(*column_definitions);
  Create_field *column_definition;

  while ((column_definition= it++) != NULL)
  {
    if (column_definition->sql_type == MYSQL_TYPE_TIMESTAMP ||      // TIMESTAMP
        column_definition->sql_type == MYSQL_TYPE_TIMESTAMP2 || //  ms TIMESTAMP
        column_definition->unireg_check == TIMESTAMP_OLD_FIELD) // Legacy
    {
      if ((column_definition->flags & NOT_NULL_FLAG) != 0 && // NOT NULL,
          column_definition->def == NULL &&            // no constant default,
          column_definition->unireg_check == NONE) // no function default
      {
        DBUG_PRINT("info", ("First TIMESTAMP column '%s' was promoted to "
                            "DEFAULT CURRENT_TIMESTAMP ON UPDATE "
                            "CURRENT_TIMESTAMP",
                            column_definition->field_name
                            ));
        column_definition->unireg_check= TIMESTAMP_DNUN_FIELD;
      }
      return;
    }
  }
}

/**
  @brief check comment length of table, column, index and partition

  @details If comment length is more than the standard length
    truncate it and store the comment length upto the standard
    comment length size

  @param          thd             Thread handle
  @param          comment_str     Comment string
  @param[in,out]  comment_len     Comment length
  @param          max_len         Maximum allowed comment length
  @param          err_code        Error message
  @param          comment_name    Type of comment

  @return Operation status
    @retval       true            Error found
    @retval       false           On success
*/

bool validate_comment_length(THD *thd, const char *comment_str,
                             size_t *comment_len, uint max_len,
                             uint err_code, const char *comment_name)
{
  int length= 0;
  DBUG_ENTER("validate_comment_length");
  uint tmp_len= system_charset_info->cset->charpos(system_charset_info,
                                                   comment_str,
                                                   comment_str +
                                                   *comment_len,
                                                   max_len);
  if (tmp_len < *comment_len)
  {
    if (thd->is_strict_mode())
    {
      my_error(err_code, MYF(0),
               comment_name, static_cast<ulong>(max_len));
      DBUG_RETURN(true);
    }
    char warn_buff[MYSQL_ERRMSG_SIZE];
    length= my_snprintf(warn_buff, sizeof(warn_buff), ER(err_code),
                        comment_name, static_cast<ulong>(max_len));
    /* do not push duplicate warnings */
    if (!thd->get_stmt_da()->has_sql_condition(warn_buff, length)) 
      push_warning(thd, Sql_condition::WARN_LEVEL_WARN,
                   err_code, warn_buff);
    *comment_len= tmp_len;
  }
  DBUG_RETURN(false);
}

/*
  Extend long VARCHAR fields to blob & prepare field if it's a blob

  SYNOPSIS
    prepare_blob_field()
    sql_field		Field to check

  RETURN
    0	ok
    1	Error (sql_field can't be converted to blob)
        In this case the error is given
*/

static bool prepare_blob_field(THD *thd, Create_field *sql_field)
{
  DBUG_ENTER("prepare_blob_field");

  if (sql_field->length > MAX_FIELD_VARCHARLENGTH &&
      !(sql_field->flags & BLOB_FLAG))
  {
    /* Convert long VARCHAR columns to TEXT or BLOB */
    char warn_buff[MYSQL_ERRMSG_SIZE];

    if (sql_field->def || thd->is_strict_mode())
    {
      my_error(ER_TOO_BIG_FIELDLENGTH, MYF(0), sql_field->field_name,
               static_cast<ulong>(MAX_FIELD_VARCHARLENGTH /
                                  sql_field->charset->mbmaxlen));
      DBUG_RETURN(1);
    }
    sql_field->sql_type= MYSQL_TYPE_BLOB;
    sql_field->flags|= BLOB_FLAG;
    my_snprintf(warn_buff, sizeof(warn_buff), ER(ER_AUTO_CONVERT), sql_field->field_name,
            (sql_field->charset == &my_charset_bin) ? "VARBINARY" : "VARCHAR",
            (sql_field->charset == &my_charset_bin) ? "BLOB" : "TEXT");
    push_warning(thd, Sql_condition::WARN_LEVEL_NOTE, ER_AUTO_CONVERT,
                 warn_buff);
  }

  if ((sql_field->flags & BLOB_FLAG) && sql_field->length)
  {
    if (sql_field->sql_type == FIELD_TYPE_BLOB ||
        sql_field->sql_type == FIELD_TYPE_TINY_BLOB ||
        sql_field->sql_type == FIELD_TYPE_MEDIUM_BLOB)
    {
      /* The user has given a length to the blob column */
      sql_field->sql_type= get_blob_type_from_length(sql_field->length);
      sql_field->pack_length= calc_pack_length(sql_field->sql_type, 0);
    }
    sql_field->length= 0;
  }
  DBUG_RETURN(0);
}


/*
  Preparation of Create_field for SP function return values.
  Based on code used in the inner loop of mysql_prepare_create_table()
  above.

  SYNOPSIS
    sp_prepare_create_field()
    thd			Thread object
    sql_field		Field to prepare

  DESCRIPTION
    Prepares the field structures for field creation.

*/

static void sp_prepare_create_field(THD *thd, Create_field *sql_field)
{
  if (sql_field->sql_type == MYSQL_TYPE_SET ||
      sql_field->sql_type == MYSQL_TYPE_ENUM)
  {
    uint32 field_length, dummy;
    if (sql_field->sql_type == MYSQL_TYPE_SET)
    {
      calculate_interval_lengths(sql_field->charset,
                                 sql_field->interval, &dummy, 
                                 &field_length);
      sql_field->length= field_length + 
                         (sql_field->interval->count - 1);
    }
    else /* MYSQL_TYPE_ENUM */
    {
      calculate_interval_lengths(sql_field->charset,
                                 sql_field->interval,
                                 &field_length, &dummy);
      sql_field->length= field_length;
    }
    set_if_smaller(sql_field->length, MAX_FIELD_WIDTH-1);
  }

  if (sql_field->sql_type == MYSQL_TYPE_BIT)
  {
    sql_field->pack_flag= FIELDFLAG_NUMBER |
                          FIELDFLAG_TREAT_BIT_AS_CHAR;
  }
  sql_field->create_length_to_internal_length();
  DBUG_ASSERT(sql_field->def == 0);
  /* Can't go wrong as sql_field->def is not defined */
  (void) prepare_blob_field(thd, sql_field);
}
