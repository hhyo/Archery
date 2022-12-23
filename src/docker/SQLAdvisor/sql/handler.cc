/* Copyright (c) 2000, 2014, Oracle and/or its affiliates. All rights reserved.

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; version 2 of the License.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software Foundation,
   Inc., 51 Franklin Street, Suite 500, Boston, MA 02110-1335 USA */

/** @file handler.cc

    @brief
  Handler-calling-functions
*/

#include "sql_priv.h"
#include "unireg.h"
#include "key.h"     // key_copy, key_unpack, key_cmp_if_same, key_cmp
#include "sql_table.h"                   // build_table_filename
#include "sql_parse.h"                          // check_stack_overrun
#include "sql_acl.h"            // SUPER_ACL
#include "sql_base.h"           // free_io_cache
#include "discover.h"           // writefrm
#include <errno.h>
#include "probes_mysql.h"
#include <mysql/psi/mysql_table.h>
#include <my_bit.h>
#include <list>
#include "global_threads.h"

using std::min;
using std::max;
using std::list;

// This is a temporary backporting fix.
#ifndef HAVE_LOG2
/*
  This will be slightly slower and perhaps a tiny bit less accurate than
  doing it the IEEE754 way but log2() should be available on C99 systems.
*/
inline double log2(double x)
{
  return (log(x) / M_LN2);
}
#endif


#define BITMAP_STACKBUF_SIZE (128/8)

KEY_CREATE_INFO default_key_create_info=
  { HA_KEY_ALG_UNDEF, 0, {NullS, 0}, {NullS, 0}, true };

/* number of entries in handlertons[] */
ulong total_ha= 0;
/* number of storage engines (from handlertons[]) that support 2pc */
ulong total_ha_2pc= 0;
/* size of savepoint storage area (see ha_init) */
ulong savepoint_alloc_size= 0;

const char *ha_row_type[] = {
  "", "FIXED", "DYNAMIC", "COMPRESSED", "REDUNDANT", "COMPACT",
  /* Reserved to be "PAGE" in future versions */ "?",
  "TOKUDB_UNCOMPRESSED", "TOKUDB_ZLIB", "TOKUDB_QUICKLZ", "TOKUDB_LZMA",
  "TOKUDB_FAST", "TOKUDB_SMALL",
  "?","?","?"
};

const char *tx_isolation_names[] =
{ "READ-UNCOMMITTED", "READ-COMMITTED", "REPEATABLE-READ", "SERIALIZABLE",
  NullS};
TYPELIB tx_isolation_typelib= {array_elements(tx_isolation_names)-1,"",
			       tx_isolation_names, NULL};

#ifndef DBUG_OFF

const char *ha_legacy_type_name(legacy_db_type legacy_type)
{
  switch (legacy_type)
  {
  case DB_TYPE_UNKNOWN:
    return "DB_TYPE_UNKNOWN";
  case DB_TYPE_DIAB_ISAM:
    return "DB_TYPE_DIAB_ISAM";
  case DB_TYPE_HASH:
    return "DB_TYPE_HASH";
  case DB_TYPE_MISAM:
    return "DB_TYPE_MISAM";
  case DB_TYPE_PISAM:
    return "DB_TYPE_PISAM";
  case DB_TYPE_RMS_ISAM:
    return "DB_TYPE_RMS_ISAM";
  case DB_TYPE_HEAP:
    return "DB_TYPE_HEAP";
  case DB_TYPE_ISAM:
    return "DB_TYPE_ISAM";
  case DB_TYPE_MRG_ISAM:
    return "DB_TYPE_MRG_ISAM";
  case DB_TYPE_MYISAM:
    return "DB_TYPE_MYISAM";
  case DB_TYPE_MRG_MYISAM:
    return "DB_TYPE_MRG_MYISAM";
  case DB_TYPE_BERKELEY_DB:
    return "DB_TYPE_BERKELEY_DB";
  case DB_TYPE_INNODB:
    return "DB_TYPE_INNODB";
  case DB_TYPE_GEMINI:
    return "DB_TYPE_GEMINI";
  case DB_TYPE_NDBCLUSTER:
    return "DB_TYPE_NDBCLUSTER";
  case DB_TYPE_EXAMPLE_DB:
    return "DB_TYPE_EXAMPLE_DB";
  case DB_TYPE_ARCHIVE_DB:
    return "DB_TYPE_ARCHIVE_DB";
  case DB_TYPE_CSV_DB:
    return "DB_TYPE_CSV_DB";
  case DB_TYPE_FEDERATED_DB:
    return "DB_TYPE_FEDERATED_DB";
  case DB_TYPE_BLACKHOLE_DB:
    return "DB_TYPE_BLACKHOLE_DB";
  case DB_TYPE_PARTITION_DB:
    return "DB_TYPE_PARTITION_DB";
  case DB_TYPE_BINLOG:
    return "DB_TYPE_BINLOG";
  case DB_TYPE_SOLID:
    return "DB_TYPE_SOLID";
  case DB_TYPE_PBXT:
    return "DB_TYPE_PBXT";
  case DB_TYPE_TABLE_FUNCTION:
    return "DB_TYPE_TABLE_FUNCTION";
  case DB_TYPE_MEMCACHE:
    return "DB_TYPE_MEMCACHE";
  case DB_TYPE_FALCON:
    return "DB_TYPE_FALCON";
  case DB_TYPE_MARIA:
    return "DB_TYPE_MARIA";
  case DB_TYPE_PERFORMANCE_SCHEMA:
    return "DB_TYPE_PERFORMANCE_SCHEMA";
  default:
    return "DB_TYPE_DYNAMIC";
  }
}
#endif

/**
  Database name that hold most of mysqld system tables.
  Current code assumes that, there exists only some
  specific "database name" designated as system database.
*/
const char* mysqld_system_database= "mysql";

/**
  Structure used by SE during check for system table.
  This structure is passed to each SE handlerton and the status (OUT param)
  is collected.
*/
struct st_sys_tbl_chk_params
{
  const char *db;                             // IN param
  const char *table_name;                     // IN param
  bool is_sql_layer_system_table;             // IN param
  legacy_db_type db_type;                     // IN param

  enum enum_sys_tbl_chk_status
  {
    // db.table_name is not a supported system table.
    NOT_KNOWN_SYSTEM_TABLE,
    /*
      db.table_name is a system table,
      but may not be supported by SE.
    */
    KNOWN_SYSTEM_TABLE,
    /*
      db.table_name is a system table,
      and is supported by SE.
    */
    SUPPORTED_SYSTEM_TABLE
  } status;                                    // OUT param
};




static const char **handler_errmsgs;

C_MODE_START
static const char **get_handler_errmsgs()
{
  return handler_errmsgs;
}
C_MODE_END


/**
  Register handler error messages for use with my_error().

  @retval
    0           OK
  @retval
    !=0         Error
*/

int ha_init_errors(void)
{
#define SETMSG(nr, msg) handler_errmsgs[(nr) - HA_ERR_FIRST]= (msg)

  /* Allocate a pointer array for the error message strings. */
  /* Zerofill it to avoid uninitialized gaps. */
  if (! (handler_errmsgs= (const char**) my_malloc(HA_ERR_ERRORS * sizeof(char*),
                                                   MYF(MY_WME | MY_ZEROFILL))))
    return 1;

  /* Set the dedicated error messages. */
  SETMSG(HA_ERR_KEY_NOT_FOUND,          ER_DEFAULT(ER_KEY_NOT_FOUND));
  SETMSG(HA_ERR_FOUND_DUPP_KEY,         ER_DEFAULT(ER_DUP_KEY));
  SETMSG(HA_ERR_RECORD_CHANGED,         "Update wich is recoverable");
  SETMSG(HA_ERR_WRONG_INDEX,            "Wrong index given to function");
  SETMSG(HA_ERR_CRASHED,                ER_DEFAULT(ER_NOT_KEYFILE));
  SETMSG(HA_ERR_WRONG_IN_RECORD,        ER_DEFAULT(ER_CRASHED_ON_USAGE));
  SETMSG(HA_ERR_OUT_OF_MEM,             "Table handler out of memory");
  SETMSG(HA_ERR_NOT_A_TABLE,            "Incorrect file format '%.64s'");
  SETMSG(HA_ERR_WRONG_COMMAND,          "Command not supported");
  SETMSG(HA_ERR_OLD_FILE,               ER_DEFAULT(ER_OLD_KEYFILE));
  SETMSG(HA_ERR_NO_ACTIVE_RECORD,       "No record read in update");
  SETMSG(HA_ERR_RECORD_DELETED,         "Intern record deleted");
  SETMSG(HA_ERR_RECORD_FILE_FULL,       ER_DEFAULT(ER_RECORD_FILE_FULL));
  SETMSG(HA_ERR_INDEX_FILE_FULL,        "No more room in index file '%.64s'");
  SETMSG(HA_ERR_END_OF_FILE,            "End in next/prev/first/last");
  SETMSG(HA_ERR_UNSUPPORTED,            ER_DEFAULT(ER_ILLEGAL_HA));
  SETMSG(HA_ERR_TO_BIG_ROW,             "Too big row");
  SETMSG(HA_WRONG_CREATE_OPTION,        "Wrong create option");
  SETMSG(HA_ERR_FOUND_DUPP_UNIQUE,      ER_DEFAULT(ER_DUP_UNIQUE));
  SETMSG(HA_ERR_UNKNOWN_CHARSET,        "Can't open charset");
  SETMSG(HA_ERR_WRONG_MRG_TABLE_DEF,    ER_DEFAULT(ER_WRONG_MRG_TABLE));
  SETMSG(HA_ERR_CRASHED_ON_REPAIR,      ER_DEFAULT(ER_CRASHED_ON_REPAIR));
  SETMSG(HA_ERR_CRASHED_ON_USAGE,       ER_DEFAULT(ER_CRASHED_ON_USAGE));
  SETMSG(HA_ERR_LOCK_WAIT_TIMEOUT,      ER_DEFAULT(ER_LOCK_WAIT_TIMEOUT));
  SETMSG(HA_ERR_LOCK_TABLE_FULL,        ER_DEFAULT(ER_LOCK_TABLE_FULL));
  SETMSG(HA_ERR_READ_ONLY_TRANSACTION,  ER_DEFAULT(ER_READ_ONLY_TRANSACTION));
  SETMSG(HA_ERR_LOCK_DEADLOCK,          ER_DEFAULT(ER_LOCK_DEADLOCK));
  SETMSG(HA_ERR_CANNOT_ADD_FOREIGN,     ER_DEFAULT(ER_CANNOT_ADD_FOREIGN));
  SETMSG(HA_ERR_NO_REFERENCED_ROW,      ER_DEFAULT(ER_NO_REFERENCED_ROW_2));
  SETMSG(HA_ERR_ROW_IS_REFERENCED,      ER_DEFAULT(ER_ROW_IS_REFERENCED_2));
  SETMSG(HA_ERR_NO_SAVEPOINT,           "No savepoint with that name");
  SETMSG(HA_ERR_NON_UNIQUE_BLOCK_SIZE,  "Non unique key block size");
  SETMSG(HA_ERR_NO_SUCH_TABLE,          "No such table: '%.64s'");
  SETMSG(HA_ERR_TABLE_EXIST,            ER_DEFAULT(ER_TABLE_EXISTS_ERROR));
  SETMSG(HA_ERR_NO_CONNECTION,          "Could not connect to storage engine");
  SETMSG(HA_ERR_TABLE_DEF_CHANGED,      ER_DEFAULT(ER_TABLE_DEF_CHANGED));
  SETMSG(HA_ERR_FOREIGN_DUPLICATE_KEY,  "FK constraint would lead to duplicate key");
  SETMSG(HA_ERR_TABLE_NEEDS_UPGRADE,    ER_DEFAULT(ER_TABLE_NEEDS_UPGRADE));
  SETMSG(HA_ERR_TABLE_READONLY,         ER_DEFAULT(ER_OPEN_AS_READONLY));
  SETMSG(HA_ERR_AUTOINC_READ_FAILED,    ER_DEFAULT(ER_AUTOINC_READ_FAILED));
  SETMSG(HA_ERR_AUTOINC_ERANGE,         ER_DEFAULT(ER_WARN_DATA_OUT_OF_RANGE));
  SETMSG(HA_ERR_TOO_MANY_CONCURRENT_TRXS, ER_DEFAULT(ER_TOO_MANY_CONCURRENT_TRXS));
  SETMSG(HA_ERR_INDEX_COL_TOO_LONG,     ER_DEFAULT(ER_INDEX_COLUMN_TOO_LONG));
  SETMSG(HA_ERR_INDEX_CORRUPT,          ER_DEFAULT(ER_INDEX_CORRUPT));
  SETMSG(HA_FTS_INVALID_DOCID,          "Invalid InnoDB FTS Doc ID");
  SETMSG(HA_ERR_TABLE_IN_FK_CHECK,	ER_DEFAULT(ER_TABLE_IN_FK_CHECK));
  SETMSG(HA_ERR_TABLESPACE_EXISTS,      "Tablespace already exists");
  SETMSG(HA_ERR_FTS_EXCEED_RESULT_CACHE_LIMIT,  "FTS query exceeds result cache limit");
  SETMSG(HA_ERR_TEMP_FILE_WRITE_FAILURE,	ER_DEFAULT(ER_TEMP_FILE_WRITE_FAILURE));
  SETMSG(HA_ERR_INNODB_FORCED_RECOVERY,	ER_DEFAULT(ER_INNODB_FORCED_RECOVERY));
  SETMSG(HA_ERR_FTS_TOO_MANY_WORDS_IN_PHRASE,  "Too many words in a FTS phrase or proximity search");
  /* Register the error messages for use with my_error(). */
  return my_error_register(get_handler_errmsgs, HA_ERR_FIRST, HA_ERR_LAST);
}

#ifdef TRANS_LOG_MGM_EXAMPLE_CODE
/*
  Example of transaction log management functions based on assumption that logs
  placed into a directory
*/
#include <my_dir.h>
#include <my_sys.h>
int example_of_iterator_using_for_logs_cleanup(handlerton *hton)
{
  void *buffer;
  int res= 1;
  struct handler_iterator iterator;
  struct handler_log_file_data data;

  if (!hton->create_iterator)
    return 1; /* iterator creator is not supported */

  if ((*hton->create_iterator)(hton, HA_TRANSACTLOG_ITERATOR, &iterator) !=
      HA_ITERATOR_OK)
  {
    /* error during creation of log iterator or iterator is not supported */
    return 1;
  }
  while((*iterator.next)(&iterator, (void*)&data) == 0)
  {
    printf("%s\n", data.filename.str);
    if (data.status == HA_LOG_STATUS_FREE &&
        mysql_file_delete(INSTRUMENT_ME,
                          data.filename.str, MYF(MY_WME)))
      goto err;
  }
  res= 0;
err:
  (*iterator.destroy)(&iterator);
  return res;
}


/*
  Here we should get info from handler where it save logs but here is
  just example, so we use constant.
  IMHO FN_ROOTDIR ("/") is safe enough for example, because nobody has
  rights on it except root and it consist of directories only at lest for
  *nix (sorry, can't find windows-safe solution here, but it is only example).
*/
#define fl_dir FN_ROOTDIR


/** @brief
  Dummy function to return log status should be replaced by function which
  really detect the log status and check that the file is a log of this
  handler.
*/
enum log_status fl_get_log_status(char *log)
{
  MY_STAT stat_buff;
  if (mysql_file_stat(INSTRUMENT_ME, log, &stat_buff, MYF(0)))
    return HA_LOG_STATUS_INUSE;
  return HA_LOG_STATUS_NOSUCHLOG;
}


struct fl_buff
{
  LEX_STRING *names;
  enum log_status *statuses;
  uint32 entries;
  uint32 current;
};


int fl_log_iterator_next(struct handler_iterator *iterator,
                          void *iterator_object)
{
  struct fl_buff *buff= (struct fl_buff *)iterator->buffer;
  struct handler_log_file_data *data=
    (struct handler_log_file_data *) iterator_object;
  if (buff->current >= buff->entries)
    return 1;
  data->filename= buff->names[buff->current];
  data->status= buff->statuses[buff->current];
  buff->current++;
  return 0;
}


void fl_log_iterator_destroy(struct handler_iterator *iterator)
{
  my_free(iterator->buffer);
}


/** @brief
  returns buffer, to be assigned in handler_iterator struct
*/
enum handler_create_iterator_result
fl_log_iterator_buffer_init(struct handler_iterator *iterator)
{
  MY_DIR *dirp;
  struct fl_buff *buff;
  char *name_ptr;
  uchar *ptr;
  FILEINFO *file;
  uint32 i;

  /* to be able to make my_free without crash in case of error */
  iterator->buffer= 0;

  if (!(dirp = my_dir(fl_dir, MYF(0))))
  {
    return HA_ITERATOR_ERROR;
  }
  if ((ptr= (uchar*)my_malloc(ALIGN_SIZE(sizeof(fl_buff)) +
                             ((ALIGN_SIZE(sizeof(LEX_STRING)) +
                               sizeof(enum log_status) +
                               + FN_REFLEN + 1) *
                              (uint) dirp->number_off_files),
                             MYF(0))) == 0)
  {
    return HA_ITERATOR_ERROR;
  }
  buff= (struct fl_buff *)ptr;
  buff->entries= buff->current= 0;
  ptr= ptr + (ALIGN_SIZE(sizeof(fl_buff)));
  buff->names= (LEX_STRING*) (ptr);
  ptr= ptr + ((ALIGN_SIZE(sizeof(LEX_STRING)) *
               (uint) dirp->number_off_files));
  buff->statuses= (enum log_status *)(ptr);
  name_ptr= (char *)(ptr + (sizeof(enum log_status) *
                            (uint) dirp->number_off_files));
  for (i=0 ; i < (uint) dirp->number_off_files  ; i++)
  {
    enum log_status st;
    file= dirp->dir_entry + i;
    if ((file->name[0] == '.' &&
         ((file->name[1] == '.' && file->name[2] == '\0') ||
            file->name[1] == '\0')))
      continue;
    if ((st= fl_get_log_status(file->name)) == HA_LOG_STATUS_NOSUCHLOG)
      continue;
    name_ptr= strxnmov(buff->names[buff->entries].str= name_ptr,
                       FN_REFLEN, fl_dir, file->name, NullS);
    buff->names[buff->entries].length= (name_ptr -
                                        buff->names[buff->entries].str);
    buff->statuses[buff->entries]= st;
    buff->entries++;
  }

  iterator->buffer= buff;
  iterator->next= &fl_log_iterator_next;
  iterator->destroy= &fl_log_iterator_destroy;
  return HA_ITERATOR_OK;
}


/* An example of a iterator creator */
enum handler_create_iterator_result
fl_create_iterator(enum handler_iterator_type type,
                   struct handler_iterator *iterator)
{
  switch(type) {
  case HA_TRANSACTLOG_ITERATOR:
    return fl_log_iterator_buffer_init(iterator);
  default:
    return HA_ITERATOR_UNSUPPORTED;
  }
}
#endif /*TRANS_LOG_MGM_EXAMPLE_CODE*/
