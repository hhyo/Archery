/* Copyright (c) 2000, 2014, Oracle and/or its affiliates. All rights
   reserved.

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

#ifndef SQL_CLASS_INCLUDED
#define SQL_CLASS_INCLUDED

/* Classes in mysql */

#include "my_global.h"                          /* NO_EMBEDDED_ACCESS_CHECKS */
#ifdef MYSQL_SERVER
#include "unireg.h"                    // REQUIRED: for other includes
#endif
#include "sql_const.h"
#include <mysql/plugin_audit.h>
#include "log.h"
#include "sql_locale.h"                         /* my_locale_st */
#include "violite.h"              /* vio_is_connected */
#include "thr_lock.h"             /* thr_lock_type, THR_LOCK_DATA,
                                     THR_LOCK_INFO */

#include <mysql/psi/mysql_stage.h>
#include <mysql/psi/mysql_statement.h>
#include <mysql/psi/mysql_idle.h>
#include <mysql_com_server.h>
#include "sql_data_change.h"
#include "item.h"


#define FLAGSTR(V,F) ((V)&(F)?#F" ":"")


#define PROFILE_NONE         (uint)0
#define PROFILE_CPU          (uint)(1<<0)
#define PROFILE_MEMORY       (uint)(1<<1)
#define PROFILE_BLOCK_IO     (uint)(1<<2)
#define PROFILE_CONTEXT      (uint)(1<<3)
#define PROFILE_PAGE_FAULTS  (uint)(1<<4)
#define PROFILE_IPC          (uint)(1<<5)
#define PROFILE_SWAPS        (uint)(1<<6)
#define PROFILE_SOURCE       (uint)(1<<16)
#define PROFILE_ALL          (uint)(~0)


/**
  The meat of thd_proc_info(THD*, char*), a macro that packs the last
  three calling-info parameters.
*/
extern "C"
const char *set_thd_proc_info(void *thd_arg, const char *info,
                              const char *calling_func,
                              const char *calling_file,
                              const unsigned int calling_line);

#define thd_proc_info(thd, msg) \
  set_thd_proc_info(thd, msg, __func__, __FILE__, __LINE__)

extern "C"
void set_thd_stage_info(void *thd,
                        const PSI_stage_info *new_stage,
                        PSI_stage_info *old_stage,
                        const char *calling_func,
                        const char *calling_file,
                        const unsigned int calling_line);
                        
#define THD_STAGE_INFO(thd, stage) \
  (thd)->enter_stage(& stage, NULL, __func__, __FILE__, __LINE__)

class Reprepare_observer;

class Query_log_event;
class Load_log_event;
class Parser_state;
class Rows_log_event;
class Sroutine_hash_entry;
class user_var_entry;

struct st_thd_timer;

enum enum_ha_read_modes { RFIRST, RNEXT, RPREV, RLAST, RKEY, RNEXT_SAME };

enum enum_delay_key_write { DELAY_KEY_WRITE_NONE, DELAY_KEY_WRITE_ON,
			    DELAY_KEY_WRITE_ALL };
enum enum_slow_query_log_use_global_control {
  SLOG_UG_LOG_SLOW_FILTER, SLOG_UG_LOG_SLOW_RATE_LIMIT
  , SLOG_UG_LOG_SLOW_VERBOSITY, SLOG_UG_LONG_QUERY_TIME
  , SLOG_UG_MIN_EXAMINED_ROW_LIMIT, SLOG_UG_ALL
};
enum enum_log_slow_verbosity { 
  SLOG_V_MICROTIME, SLOG_V_QUERY_PLAN, SLOG_V_INNODB, 
  SLOG_V_PROFILING, SLOG_V_PROFILING_USE_GETRUSAGE,
  SLOG_V_MINIMAL, SLOG_V_STANDARD, SLOG_V_FULL
};
enum enum_slow_query_log_timestamp_precision {
  SLOG_SECOND, SLOG_MICROSECOND
};
enum enum_slow_query_log_rate_type {
  SLOG_RT_SESSION, SLOG_RT_QUERY
};
#define QPLAN_NONE            0
#define QPLAN_QC_NO           (1 << 0)
#define QPLAN_FULL_SCAN       (1 << 1)
#define QPLAN_FULL_JOIN       (1 << 2)
#define QPLAN_TMP_TABLE       (1 << 3)
#define QPLAN_TMP_DISK        (1 << 4)
#define QPLAN_FILESORT        (1 << 5)
#define QPLAN_FILESORT_DISK   (1 << 6)
#define QPLAN_QC              (1 << 7)
enum enum_log_slow_filter {
  SLOG_F_QC_NO, SLOG_F_FULL_SCAN, SLOG_F_FULL_JOIN,
  SLOG_F_TMP_TABLE, SLOG_F_TMP_DISK, SLOG_F_FILESORT,
  SLOG_F_FILESORT_DISK
};
#define SLOG_SLOW_RATE_LIMIT_MAX	1000
enum enum_log_warnings_suppress { log_warnings_suppress_1592 };
enum enum_slave_exec_mode { SLAVE_EXEC_MODE_STRICT,
                            SLAVE_EXEC_MODE_IDEMPOTENT,
                            SLAVE_EXEC_MODE_LAST_BIT };
enum enum_slave_type_conversions { SLAVE_TYPE_CONVERSIONS_ALL_LOSSY,
                                   SLAVE_TYPE_CONVERSIONS_ALL_NON_LOSSY,
                                   SLAVE_TYPE_CONVERSIONS_ALL_UNSIGNED,
                                   SLAVE_TYPE_CONVERSIONS_ALL_SIGNED};
enum enum_slave_rows_search_algorithms { SLAVE_ROWS_TABLE_SCAN = (1U << 0),
                                         SLAVE_ROWS_INDEX_SCAN = (1U << 1),
                                         SLAVE_ROWS_HASH_SCAN  = (1U << 2)};

enum enum_tx_isolation { ISO_READ_UNCOMMITTED, ISO_READ_COMMITTED,
  ISO_REPEATABLE_READ, ISO_SERIALIZABLE};

enum enum_mark_columns
{ MARK_COLUMNS_NONE, MARK_COLUMNS_READ, MARK_COLUMNS_WRITE};
enum enum_filetype { FILETYPE_CSV, FILETYPE_XML };

/* Bits for different SQL modes modes (including ANSI mode) */
#define MODE_REAL_AS_FLOAT              1
#define MODE_PIPES_AS_CONCAT            2
#define MODE_ANSI_QUOTES                4
#define MODE_IGNORE_SPACE               8
#define MODE_NOT_USED                   16
#define MODE_ONLY_FULL_GROUP_BY         32
#define MODE_NO_UNSIGNED_SUBTRACTION    64
#define MODE_NO_DIR_IN_CREATE           128
#define MODE_POSTGRESQL                 256
#define MODE_ORACLE                     512
#define MODE_MSSQL                      1024
#define MODE_DB2                        2048
#define MODE_MAXDB                      4096
#define MODE_NO_KEY_OPTIONS             8192
#define MODE_NO_TABLE_OPTIONS           16384
#define MODE_NO_FIELD_OPTIONS           32768
#define MODE_MYSQL323                   65536L
#define MODE_MYSQL40                    (MODE_MYSQL323*2)
#define MODE_ANSI                       (MODE_MYSQL40*2)
#define MODE_NO_AUTO_VALUE_ON_ZERO      (MODE_ANSI*2)
#define MODE_NO_BACKSLASH_ESCAPES       (MODE_NO_AUTO_VALUE_ON_ZERO*2)
#define MODE_STRICT_TRANS_TABLES        (MODE_NO_BACKSLASH_ESCAPES*2)
#define MODE_STRICT_ALL_TABLES          (MODE_STRICT_TRANS_TABLES*2)
#define MODE_NO_ZERO_IN_DATE            (MODE_STRICT_ALL_TABLES*2)
#define MODE_NO_ZERO_DATE               (MODE_NO_ZERO_IN_DATE*2)
#define MODE_INVALID_DATES              (MODE_NO_ZERO_DATE*2)
#define MODE_ERROR_FOR_DIVISION_BY_ZERO (MODE_INVALID_DATES*2)
#define MODE_TRADITIONAL                (MODE_ERROR_FOR_DIVISION_BY_ZERO*2)
#define MODE_NO_AUTO_CREATE_USER        (MODE_TRADITIONAL*2)
#define MODE_HIGH_NOT_PRECEDENCE        (MODE_NO_AUTO_CREATE_USER*2)
#define MODE_NO_ENGINE_SUBSTITUTION     (MODE_HIGH_NOT_PRECEDENCE*2)
#define MODE_PAD_CHAR_TO_FULL_LENGTH    (ULL(1) << 31)

extern char internal_table_name[2];
extern char empty_c_string[1];
extern LEX_STRING EMPTY_STR;
extern LEX_STRING NULL_STR;
extern MYSQL_PLUGIN_IMPORT const char **errmesg;

extern bool volatile shutdown_in_progress;

extern "C" LEX_STRING * thd_query_string (MYSQL_THD thd);
extern "C" char **thd_query(MYSQL_THD thd);

/**
  @class CSET_STRING
  @brief Character set armed LEX_STRING
*/
class CSET_STRING
{
private:
  LEX_STRING string;
  const CHARSET_INFO *cs;
public:
  CSET_STRING() : cs(&my_charset_bin)
  {
    string.str= NULL;
    string.length= 0;
  }
  CSET_STRING(char *str_arg, size_t length_arg, const CHARSET_INFO *cs_arg) :
  cs(cs_arg)
  {
    DBUG_ASSERT(cs_arg != NULL);
    string.str= str_arg;
    string.length= length_arg;
  }

  inline char *str() const { return string.str; }
  inline size_t length() const { return string.length; }
  const CHARSET_INFO *charset() const { return cs; }

  friend LEX_STRING * thd_query_string (MYSQL_THD thd);
  friend char **thd_query(MYSQL_THD thd);
};


#define TC_LOG_PAGE_SIZE   8192
#define TC_LOG_MIN_SIZE    (3*TC_LOG_PAGE_SIZE)

#define TC_HEURISTIC_RECOVER_COMMIT   1
#define TC_HEURISTIC_RECOVER_ROLLBACK 2
extern ulong tc_heuristic_recover;

typedef struct st_user_var_events
{
  user_var_entry *user_var_event;
  char *value;
  ulong length;
  Item_result type;
  uint charset_number;
  bool unsigned_flag;
} BINLOG_USER_VAR_EVENT;


class Key_part_spec :public Sql_alloc {
public:
  LEX_STRING field_name;
  uint length;
  Key_part_spec(const LEX_STRING &name, uint len)
    : field_name(name), length(len)
  {}
  Key_part_spec(const char *name, const size_t name_len, uint len)
    : length(len)
  { field_name.str= (char *)name; field_name.length= name_len; }
  bool operator==(const Key_part_spec& other) const;
  /**
    Construct a copy of this Key_part_spec. field_name is copied
    by-pointer as it is known to never change. At the same time
    'length' may be reset in mysql_prepare_create_table, and this
    is why we supply it with a copy.

    @return If out of memory, 0 is returned and an error is set in
    THD.
  */
  Key_part_spec *clone(MEM_ROOT *mem_root) const
  { return new (mem_root) Key_part_spec(*this); }
};


class Alter_drop :public Sql_alloc {
public:
  enum drop_type {KEY, COLUMN, FOREIGN_KEY };
  const char *name;
  enum drop_type type;
  Alter_drop(enum drop_type par_type,const char *par_name)
    :name(par_name), type(par_type)
  {
    DBUG_ASSERT(par_name != NULL);
  }
  /**
    Used to make a clone of this object for ALTER/CREATE TABLE
    @sa comment for Key_part_spec::clone
  */
  Alter_drop *clone(MEM_ROOT *mem_root) const
    { return new (mem_root) Alter_drop(*this); }
};


class Alter_column :public Sql_alloc {
public:
  const char *name;
  Item *def;
  Alter_column(const char *par_name,Item *literal)
    :name(par_name), def(literal) {}
  /**
    Used to make a clone of this object for ALTER/CREATE TABLE
    @sa comment for Key_part_spec::clone
  */
  Alter_column *clone(MEM_ROOT *mem_root) const
    { return new (mem_root) Alter_column(*this); }
};


class Key :public Sql_alloc {
public:
  enum Keytype { PRIMARY= 0, UNIQUE= 1, MULTIPLE= 2, FULLTEXT= 4, SPATIAL= 8,
                 FOREIGN_KEY= 16, CLUSTERING= 32 };
  enum Keytype type;
  KEY_CREATE_INFO key_create_info;
  List<Key_part_spec> columns;
  LEX_STRING name;
  bool generated;

  Key(enum Keytype type_par, const LEX_STRING &name_arg,
      KEY_CREATE_INFO *key_info_arg,
      bool generated_arg, List<Key_part_spec> &cols)
    :type(type_par), key_create_info(*key_info_arg), columns(cols),
    name(name_arg), generated(generated_arg)
  {}
  Key(enum Keytype type_par, const char *name_arg, size_t name_len_arg,
      KEY_CREATE_INFO *key_info_arg, bool generated_arg,
      List<Key_part_spec> &cols)
    :type(type_par), key_create_info(*key_info_arg), columns(cols),
    generated(generated_arg)
  {
    name.str= (char *)name_arg;
    name.length= name_len_arg;
  }
  Key(const Key &rhs, MEM_ROOT *mem_root);
  virtual ~Key() {}
  /* Equality comparison of keys (ignoring name) */
  friend bool foreign_key_prefix(Key *a, Key *b);
  /**
    Used to make a clone of this object for ALTER/CREATE TABLE
    @sa comment for Key_part_spec::clone
  */
  virtual Key *clone(MEM_ROOT *mem_root) const
    { return new (mem_root) Key(*this, mem_root); }
};

class Table_ident;

class Foreign_key: public Key {
public:
  enum fk_match_opt { FK_MATCH_UNDEF, FK_MATCH_FULL,
		      FK_MATCH_PARTIAL, FK_MATCH_SIMPLE};
  enum fk_option { FK_OPTION_UNDEF, FK_OPTION_RESTRICT, FK_OPTION_CASCADE,
		   FK_OPTION_SET_NULL, FK_OPTION_NO_ACTION, FK_OPTION_DEFAULT};

  LEX_STRING ref_db;
  LEX_STRING ref_table;
  List<Key_part_spec> ref_columns;
  uint delete_opt, update_opt, match_opt;
  Foreign_key(const LEX_STRING &name_arg, List<Key_part_spec> &cols,
	      const LEX_STRING &ref_db_arg, const LEX_STRING &ref_table_arg,
              List<Key_part_spec> &ref_cols,
	      uint delete_opt_arg, uint update_opt_arg, uint match_opt_arg)
    :Key(FOREIGN_KEY, name_arg, &default_key_create_info, 0, cols),
    ref_db(ref_db_arg), ref_table(ref_table_arg), ref_columns(ref_cols),
    delete_opt(delete_opt_arg), update_opt(update_opt_arg),
    match_opt(match_opt_arg)
  {
    // We don't check for duplicate FKs.
    key_create_info.check_for_duplicate_indexes= false;
  }
  Foreign_key(const Foreign_key &rhs, MEM_ROOT *mem_root);
  /**
    Used to make a clone of this object for ALTER/CREATE TABLE
    @sa comment for Key_part_spec::clone
  */
  virtual Key *clone(MEM_ROOT *mem_root) const
  { return new (mem_root) Foreign_key(*this, mem_root); }
};

typedef struct st_mysql_lock
{
  uint table_count,lock_count;
  THR_LOCK_DATA **locks;
} MYSQL_LOCK;


class LEX_COLUMN : public Sql_alloc
{
public:
  String column;
  uint rights;
  LEX_COLUMN (const String& x,const  uint& y ): column (x),rights (y) {}
};

class MY_LOCALE;

/**
  Query_cache_tls -- query cache thread local data.
*/

struct Query_cache_block;

struct Query_cache_tls
{
  /*
    'first_query_block' should be accessed only via query cache
    functions and methods to maintain proper locking.
  */
  Query_cache_block *first_query_block;
  void set_first_query_block(Query_cache_block *first_query_block_arg)
  {
    first_query_block= first_query_block_arg;
  }

  Query_cache_tls() :first_query_block(NULL) {}
};

/* SIGNAL / RESIGNAL / GET DIAGNOSTICS */

/**
  This enumeration list all the condition item names of a condition in the
  SQL condition area.
*/
typedef enum enum_diag_condition_item_name
{
  /*
    Conditions that can be set by the user (SIGNAL/RESIGNAL),
    and by the server implementation.
  */

  DIAG_CLASS_ORIGIN= 0,
  FIRST_DIAG_SET_PROPERTY= DIAG_CLASS_ORIGIN,
  DIAG_SUBCLASS_ORIGIN= 1,
  DIAG_CONSTRAINT_CATALOG= 2,
  DIAG_CONSTRAINT_SCHEMA= 3,
  DIAG_CONSTRAINT_NAME= 4,
  DIAG_CATALOG_NAME= 5,
  DIAG_SCHEMA_NAME= 6,
  DIAG_TABLE_NAME= 7,
  DIAG_COLUMN_NAME= 8,
  DIAG_CURSOR_NAME= 9,
  DIAG_MESSAGE_TEXT= 10,
  DIAG_MYSQL_ERRNO= 11,
  LAST_DIAG_SET_PROPERTY= DIAG_MYSQL_ERRNO
} Diag_condition_item_name;

/**
  Name of each diagnostic condition item.
  This array is indexed by Diag_condition_item_name.
*/
extern const LEX_STRING Diag_condition_item_names[];


/*
  The following are for the interface with the .frm file
*/

#define FIELDFLAG_DECIMAL		1
#define FIELDFLAG_BINARY		1	// Shares same flag
#define FIELDFLAG_NUMBER		2
#define FIELDFLAG_ZEROFILL		4
#define FIELDFLAG_PACK			120	// Bits used for packing
#define FIELDFLAG_INTERVAL		256     // mangled with decimals!
#define FIELDFLAG_BITFIELD		512	// mangled with decimals!
#define FIELDFLAG_BLOB			1024	// mangled with decimals!
#define FIELDFLAG_GEOM			2048    // mangled with decimals!

#define FIELDFLAG_TREAT_BIT_AS_CHAR     4096    /* use Field_bit_as_char */

#define FIELDFLAG_LEFT_FULLSCREEN	8192
#define FIELDFLAG_RIGHT_FULLSCREEN	16384
#define FIELDFLAG_FORMAT_NUMBER		16384	// predit: ###,,## in output
#define FIELDFLAG_NO_DEFAULT		16384   /* sql */
#define FIELDFLAG_SUM			((uint) 32768)// predit: +#fieldflag
#define FIELDFLAG_MAYBE_NULL		((uint) 32768)// sql
#define FIELDFLAG_HEX_ESCAPE		((uint) 0x10000)
#define FIELDFLAG_PACK_SHIFT		3
#define FIELDFLAG_DEC_SHIFT		8
#define FIELDFLAG_MAX_DEC		31
#define FIELDFLAG_NUM_SCREEN_TYPE	0x7F01
#define FIELDFLAG_ALFA_SCREEN_TYPE	0x7800

#include "sql_lex.h"				/* Must be here */

class Delayed_insert;
class select_result;
class Time_zone;

#define THD_SENTRY_MAGIC 0xfeedd1ff
#define THD_SENTRY_GONE  0xdeadbeef

#define THD_CHECK_SENTRY(thd) DBUG_ASSERT(thd->dbug_sentry == THD_SENTRY_MAGIC)

typedef ulonglong sql_mode_t;


typedef struct system_variables
{
  
  ulonglong max_heap_table_size;
  ulonglong tmp_table_size;
  ulonglong long_query_time;
  my_bool end_markers_in_json;
  /* A bitmap for switching optimizations on/off */
  ulonglong optimizer_switch;
  sql_mode_t sql_mode; ///< which non-standard SQL behaviour should be enabled
  ulonglong option_bits; ///< OPTION_xxx constants, e.g. OPTION_PROFILING
  ha_rows select_limit;
  ha_rows max_join_size;
  ulong bulk_insert_buff_size;
  ulong max_allowed_packet;
  ulong max_error_count;
  ulong net_buffer_length;
  ulong net_interactive_timeout;
  ulong net_read_timeout;
  ulong net_retry_count;
  ulong net_wait_timeout;
  ulong net_write_timeout;
  ulong default_week_format;
  
  ulong range_alloc_block_size;
  ulong query_alloc_block_size;
  ulong query_prealloc_size;
  
  my_bool sql_log_bin;
  ulong completion_type;
  ulong query_cache_type;
  ulong tx_isolation;
  ulong updatable_views_with_limit;
  ulong my_aes_mode;

  /**
    In slave thread we need to know in behalf of which
    thread the query is being run to replicate temp tables properly
  */
  my_thread_id pseudo_thread_id;
  /**
    Default transaction access mode. READ ONLY (true) or READ WRITE (false).
  */
  my_bool tx_read_only;
  my_bool low_priority_updates;
  my_bool new_mode;
  my_bool query_cache_wlock_invalidate;
  my_bool engine_condition_pushdown;
  my_bool keep_files_on_create;

  my_bool online_alter_index;

  uint old_passwords;
  my_bool big_tables;

  /* Only charset part of these variables is sensible */
  const CHARSET_INFO *character_set_filesystem;
  const CHARSET_INFO *character_set_client;
  const CHARSET_INFO *character_set_results;

  /* Both charset and collation parts of these variables are important */
  const CHARSET_INFO  *collation_server;
  const CHARSET_INFO  *collation_database;
  const CHARSET_INFO  *collation_connection;

  /* Error messages */
  MY_LOCALE *lc_messages;
  /* Locale Support */
  MY_LOCALE *lc_time_names;
  /*
    TIMESTAMP fields are by default created with DEFAULT clauses
    implicitly without users request. This flag when set, disables
    implicit default values and expect users to provide explicit
    default clause. i.e., when set columns are defined as NULL,
    instead of NOT NULL by default.
  */
  my_bool explicit_defaults_for_timestamp;

  my_bool sysdate_is_now;
  my_bool binlog_rows_query_log_events;

#ifndef DBUG_OFF
  ulonglong query_exec_time;
  double    query_exec_time_double;
  ulong     query_exec_id;
#endif
  ulong log_slow_rate_limit;
  ulonglong log_slow_filter;
  ulonglong log_slow_verbosity;

  ulong      innodb_io_reads;
  ulonglong  innodb_io_read;
  ulong      innodb_io_reads_wait_timer;
  ulong      innodb_lock_que_wait_timer;
  ulong      innodb_innodb_que_wait_timer;
  ulong      innodb_page_access;

  double long_query_time_double;

  my_bool pseudo_slave_mode;

  ulong max_statement_time;

  my_bool expand_fast_index_creation;
} SV;


void mark_transaction_to_rollback(THD *thd, bool all);


/**
  Get collation by name, send error to client on failure.
  @param name     Collation name
  @param name_cs  Character set of the name string
  @return
  @retval         NULL on error
  @retval         Pointter to CHARSET_INFO with the given name on success
*/
inline CHARSET_INFO *
mysqld_collation_get_by_name(const char *name,
                             CHARSET_INFO *name_cs= system_charset_info)
{
  CHARSET_INFO *cs;
  MY_CHARSET_LOADER loader;
  my_charset_loader_init_mysys(&loader);
  if (!(cs= my_collation_get_by_name(&loader, name, MYF(0))))
  {
    ErrConvString err(name, name_cs);
    my_error(ER_UNKNOWN_COLLATION, MYF(0), err.ptr());
    if (loader.error[0])
      push_warning_printf(current_thd,
                          Sql_condition::WARN_LEVEL_WARN,
                          ER_UNKNOWN_COLLATION, "%s", loader.error);
  }
  return cs;
}


#ifdef MYSQL_SERVER

/* The following macro is to make init of Query_arena simpler */
#ifndef DBUG_OFF
#define INIT_ARENA_DBUG_INFO is_backup_arena= 0; is_reprepared= FALSE;
#else
#define INIT_ARENA_DBUG_INFO
#endif

class Query_arena
{
public:
  /*
    List of items created in the parser for this query. Every item puts
    itself to the list on creation (see Item::Item() for details))
  */
  Item *free_list;
  MEM_ROOT *mem_root;                   // Pointer to current memroot
#ifndef DBUG_OFF
  bool is_backup_arena; /* True if this arena is used for backup. */
  bool is_reprepared;
#endif
  /*
    The states relfects three diffrent life cycles for three
    different types of statements:
    Prepared statement: STMT_INITIALIZED -> STMT_PREPARED -> STMT_EXECUTED.
    Stored procedure:   STMT_INITIALIZED_FOR_SP -> STMT_EXECUTED.
    Other statements:   STMT_CONVENTIONAL_EXECUTION never changes.
  */
  enum enum_state
  {
    STMT_INITIALIZED= 0, STMT_INITIALIZED_FOR_SP= 1, STMT_PREPARED= 2,
    STMT_CONVENTIONAL_EXECUTION= 3, STMT_EXECUTED= 4, STMT_ERROR= -1
  };

  enum_state state;

  /* We build without RTTI, so dynamic_cast can't be used. */
  enum Type
  {
    STATEMENT, PREPARED_STATEMENT, STORED_PROCEDURE
  };

  Query_arena(MEM_ROOT *mem_root_arg, enum enum_state state_arg) :
    free_list(0), mem_root(mem_root_arg), state(state_arg)
  { INIT_ARENA_DBUG_INFO; }
  /*
    This constructor is used only when Query_arena is created as
    backup storage for another instance of Query_arena.
  */
  Query_arena() { INIT_ARENA_DBUG_INFO; }

  virtual Type type() const;
  virtual ~Query_arena() {};

  inline bool is_stmt_prepare() const { return state == STMT_INITIALIZED; }
  inline bool is_stmt_prepare_or_first_sp_execute() const
  { return (int)state < (int)STMT_PREPARED; }
  inline bool is_stmt_prepare_or_first_stmt_execute() const
  { return (int)state <= (int)STMT_PREPARED; }
  inline bool is_conventional() const
  { return state == STMT_CONVENTIONAL_EXECUTION; }

  inline void* alloc(size_t size) { return alloc_root(mem_root,size); }
  inline void* calloc(size_t size)
  {
    void *ptr;
    if ((ptr=alloc_root(mem_root,size)))
      memset(ptr, 0, size);
    return ptr;
  }
  inline char *strdup(const char *str)
  { return strdup_root(mem_root,str); }
  inline char *strmake(const char *str, size_t size)
  { return strmake_root(mem_root,str,size); }
  inline void *memdup(const void *str, size_t size)
  { return memdup_root(mem_root,str,size); }
  inline void *memdup_w_gap(const void *str, size_t size, uint gap)
  {
    void *ptr;
    if ((ptr= alloc_root(mem_root,size+gap)))
      memcpy(ptr,str,size);
    return ptr;
  }

  void set_query_arena(Query_arena *set);

  void free_items();
  /* Close the active state associated with execution of this statement */
  virtual void cleanup_stmt();
};


class Server_side_cursor;

/**
  @class Statement
  @brief State of a single command executed against this connection.

  One connection can contain a lot of simultaneously running statements,
  some of which could be:
   - prepared, that is, contain placeholders,
   - opened as cursors. We maintain 1 to 1 relationship between
     statement and cursor - if user wants to create another cursor for his
     query, we create another statement for it. 
  To perform some action with statement we reset THD part to the state  of
  that statement, do the action, and then save back modified state from THD
  to the statement. It will be changed in near future, and Statement will
  be used explicitly.
*/

class Statement: public Query_arena
{
  Statement(const Statement &rhs);              /* not implemented: */
  Statement &operator=(const Statement &rhs);   /* non-copyable */
public:
  /*
    Uniquely identifies each statement object in thread scope; change during
    statement lifetime. FIXME: must be const
  */
   ulong id;

  /*
    MARK_COLUMNS_NONE:  Means mark_used_colums is not set and no indicator to
                        handler of fields used is set
    MARK_COLUMNS_READ:  Means a bit in read set is set to inform handler
	                that the field is to be read. If field list contains
                        duplicates, then thd->dup_field is set to point
                        to the last found duplicate.
    MARK_COLUMNS_WRITE: Means a bit is set in write set to inform handler
			that it needs to update this field in write_row
                        and update_row.
  */
  enum enum_mark_columns mark_used_columns;

  LEX_STRING name; /* name for named prepared statements */
  LEX *lex;                                     // parse tree descriptor
  /*
    Points to the query associated with this statement. It's const, but
    we need to declare it char * because all table handlers are written
    in C and need to point to it.

    Note that if we set query = NULL, we must at the same time set
    query_length = 0, and protect the whole operation with
    LOCK_thd_data mutex. To avoid crashes in races, if we do not
    know that thd->query cannot change at the moment, we should print
    thd->query like this:
      (1) reserve the LOCK_thd_data mutex;
      (2) print or copy the value of query and query_length
      (3) release LOCK_thd_data mutex.
    This printing is needed at least in SHOW PROCESSLIST and SHOW
    ENGINE INNODB STATUS.
  */
  CSET_STRING query_string;

  /*
    In some cases, we may want to modify the query (i.e. replace
    passwords with their hashes before logging the statement etc.).

    In case the query was rewritten, the original query will live in
    query_string, while the rewritten query lives in rewritten_query.
    If rewritten_query is empty, query_string should be logged.
    If rewritten_query is non-empty, the rewritten query it contains
    should be used in logs (general log, slow query log, binary log).

    Currently, password obfuscation is the only rewriting we do; more
    may follow at a later date, both pre- and post parsing of the query.
    Rewriting of binloggable statements must preserve all pertinent
    information.
  */
  String      rewritten_query;

  inline char *query() const { return query_string.str(); }
  inline uint32 query_length() const { return query_string.length(); }
  const CHARSET_INFO *query_charset() const { return query_string.charset(); }
  void set_query_inner(const CSET_STRING &string_arg)
  {
    query_string= string_arg;
  }
  void set_query_inner(char *query_arg, uint32 query_length_arg,
                       const CHARSET_INFO *cs_arg)
  {
    set_query_inner(CSET_STRING(query_arg, query_length_arg, cs_arg));
  }
  void reset_query_inner()
  {
    set_query_inner(CSET_STRING());
  }
  /**
    Name of the current (default) database.

    If there is the current (default) database, "db" contains its name. If
    there is no current (default) database, "db" is NULL and "db_length" is
    0. In other words, "db", "db_length" must either be NULL, or contain a
    valid database name.

    @note this attribute is set and alloced by the slave SQL thread (for
    the THD of that thread); that thread is (and must remain, for now) the
    only responsible for freeing this member.
  */

  char *db;
  size_t db_length;

public:

  /* This constructor is called for backup statements */
  Statement() {}

  Statement(LEX *lex_arg, MEM_ROOT *mem_root_arg,
            enum_state state_arg, ulong id_arg);
  virtual ~Statement();

  /* Assign execution context (note: not all members) of given stmt to self */
  virtual void set_statement(Statement *stmt);
  void set_n_backup_statement(Statement *stmt, Statement *backup);
  void restore_backup_statement(Statement *stmt, Statement *backup);
  /* return class type */
  virtual Type type() const;
};


/**
  Container for all statements created/used in a connection.
  Statements in Statement_map have unique Statement::id (guaranteed by id
  assignment in Statement::Statement)
  Non-empty statement names are unique too: attempt to insert a new statement
  with duplicate name causes older statement to be deleted

  Statements are auto-deleted when they are removed from the map and when the
  map is deleted.
*/

class Statement_map
{
public:
  Statement_map();

  int insert(THD *thd, Statement *statement);

  Statement *find_by_name(LEX_STRING *name)
  {
    Statement *stmt;
    stmt= (Statement*)my_hash_search(&names_hash, (uchar*)name->str,
                                     name->length);
    return stmt;
  }

  Statement *find(ulong id)
  {
    if (last_found_statement == 0 || id != last_found_statement->id)
    {
      Statement *stmt;
      stmt= (Statement *) my_hash_search(&st_hash, (uchar *) &id, sizeof(id));
      if (stmt && stmt->name.str)
        return NULL;
      last_found_statement= stmt;
    }
    return last_found_statement;
  }
  /*
    Close all cursors of this connection that use tables of a storage
    engine that has transaction-specific state and therefore can not
    survive COMMIT or ROLLBACK. Currently all but MyISAM cursors are closed.
    CURRENTLY NOT IMPLEMENTED!
  */
  void close_transient_cursors();
  void erase(Statement *statement);
  /* Erase all statements (calls Statement destructor) */
  void reset();
  ~Statement_map();
private:
  HASH st_hash;
  HASH names_hash;
  Statement *last_found_statement;
};

/**
  @class Security_context
  @brief A set of THD members describing the current authenticated user.
*/

class Security_context {
private:

String host;
String ip;
String external_user;
public:
  Security_context() {}                       /* Remove gcc warning */
  /*
    host - host of the client
    user - user of the client, set to NULL until the user has been read from
    the connection
    priv_user - The user privilege we are using. May be "" for anonymous user.
    ip - client IP
  */
  char   *user;
  char   priv_user[USERNAME_LENGTH];
  char   proxy_user[USERNAME_LENGTH + MAX_HOSTNAME + 5];
  /* The host privilege we are using */
  char   priv_host[MAX_HOSTNAME];
  /* points to host if host is available, otherwise points to ip */
  const char *host_or_ip;
  ulong master_access;                 /* Global privileges from mysql.user */
  ulong db_access;                     /* Privileges for current db */
  /*
    This flag is set according to connecting user's context and not the
    effective user.
  */
  bool password_expired;               /* password expiration flag */

  void init();
  void destroy();
  void skip_grants();
  inline char *priv_host_name()
  {
    return (*priv_host ? priv_host : (char *)"%");
  }

  bool set_user(char *user_arg);
  String *get_host();
  String *get_ip();
  String *get_external_user();
  void set_host(const char *p);
  void set_ip(const char *p);
  void set_external_user(const char *p);
  void set_host(const char *str, size_t len);
  bool user_matches(Security_context *);
};


/**
  @class Log_throttle
  @brief Base class for rate-limiting a log (slow query log etc.)
*/

class Log_throttle
{
  /**
    When will/did current window end?
  */
  ulonglong window_end;

  /**
    Log no more than rate lines of a given type per window_size
    (e.g. per minute, usually LOG_THROTTLE_WINDOW_SIZE).
  */
  const ulong window_size;

  /**
   There have been this many lines of this type in this window,
   including those that we suppressed. (We don't simply stop
   counting once we reach the threshold as we'll write a summary
   of the suppressed lines later.)
  */
  ulong count;

protected:
  /**
    Template for the summary line. Should contain %lu as the only
    conversion specification.
  */
  const char *summary_template;

  /**
    Start a new window.
  */
  void new_window(ulonglong now);

  /**
    Increase count of logs we're handling.

    @param rate  Limit on records to be logged during the throttling window.

    @retval true -  log rate limit is exceeded, so record should be supressed.
    @retval false - log rate limit is not exceeded, record should be logged.
  */
  bool inc_log_count(ulong rate) { return (++count > rate); }

  /**
    Check whether we're still in the current window. (If not, the caller
    will want to print a summary (if the logging of any lines was suppressed),
    and start a new window.)
  */
  bool in_window(ulonglong now) const { return (now < window_end); };

  /**
    Prepare a summary of suppressed lines for logging.
    This function returns the number of queries that were qualified for
    inclusion in the log, but were not printed because of the rate-limiting.
    The summary will contain this count as well as the respective totals for
    lock and execution time.
    This function assumes that the caller already holds the necessary locks.

    @param rate  Limit on records logged during the throttling window.
  */
  ulong prepare_summary(ulong rate);

  /**
    @param window_usecs  ... in this many micro-seconds
    @param msg           use this template containing %lu as only non-literal
  */
  Log_throttle(ulong window_usecs, const char *msg)
              : window_end(0), window_size(window_usecs),
                count(0), summary_template(msg)
  {}

public:
  /**
    We're rate-limiting messages per minute; 60,000,000 microsecs = 60s
    Debugging is less tedious with a window in the region of 5000000
  */
  static const ulong LOG_THROTTLE_WINDOW_SIZE= 60000000;
};


/**
  @class Slow_log_throttle
  @brief Used for rate-limiting the slow query log.
*/

class Slow_log_throttle : public Log_throttle
{
private:
  /**
    We're using our own (empty) security context during summary generation.
    That way, the aggregate value of the suppressed queries isn't printed
    with a specific user's name (i.e. the user who sent a query when or
    after the time-window closes), as that would be misleading.
  */
  Security_context aggregate_sctx;

  /**
    Total of the execution times of queries in this time-window for which
    we suppressed logging. For use in summary printing.
  */
  ulonglong total_exec_time;

  /**
    Total of the lock times of queries in this time-window for which
    we suppressed logging. For use in summary printing.
  */
  ulonglong total_lock_time;

  /**
    A reference to the threshold ("no more than n log lines per ...").
    References a (system-?) variable in the server.
  */
  ulong *rate;

  /**
    The routine we call to actually log a line (i.e. our summary).
    The signature miraculously coincides with slow_log_print().
  */
  bool (*log_summary)(THD *, const char *, uint);

  /**
    Slow_log_throttle is shared between THDs.
  */
  mysql_mutex_t *LOCK_log_throttle;

  /**
    Start a new window.
  */
  void new_window(ulonglong now);

  /**
    Actually print the prepared summary to log.
  */
  void print_summary(THD *thd, ulong suppressed,
                     ulonglong print_lock_time,
                     ulonglong print_exec_time);

public:

  /**
    @param threshold     suppress after this many queries ...
    @param window_usecs  ... in this many micro-seconds
    @param logger        call this function to log a single line (our summary)
    @param msg           use this template containing %lu as only non-literal
  */
  Slow_log_throttle(ulong *threshold, mysql_mutex_t *lock, ulong window_usecs,
                    bool (*logger)(THD *, const char *, uint),
                    const char *msg);

  /**
    Prepare and print a summary of suppressed lines to log.
    (For now, slow query log.)
    The summary states the number of queries that were qualified for
    inclusion in the log, but were not printed because of the rate-limiting,
    and their respective totals for lock and execution time.
    This wrapper for prepare_summary() and print_summary() handles the
    locking/unlocking.

    @param thd                 The THD that tries to log the statement.
    @retval false              Logging was not supressed, no summary needed.
    @retval true               Logging was supressed; a summary was printed.
  */
  bool flush(THD *thd);

  /**
    Top-level function.
    @param thd                 The THD that tries to log the statement.
    @param eligible            Is the statement of the type we might suppress?
    @retval true               Logging should be supressed.
    @retval false              Logging should not be supressed.
  */
  bool log(THD *thd, bool eligible);
};


/**
  @class Slow_log_throttle
  @brief Used for rate-limiting a error logs.
*/

class Error_log_throttle : public Log_throttle
{
private:
  /**
    The routine we call to actually log a line (i.e. our summary).
  */
  void (*log_summary)(const char *, ...);

  /**
    Actually print the prepared summary to log.
  */
  void print_summary(ulong suppressed)
  {
    (*log_summary)(summary_template, suppressed);
  }

public:
  /**
    @param window_usecs  ... in this many micro-seconds
    @param logger        call this function to log a single line (our summary)
    @param msg           use this template containing %lu as only non-literal
  */
  Error_log_throttle(ulong window_usecs,
                     void (*logger)(const char*, ...),
                     const char *msg)
  : Log_throttle(window_usecs, msg), log_summary(logger)
  {}

  /**
    Prepare and print a summary of suppressed lines to log.
    (For now, slow query log.)
    The summary states the number of queries that were qualified for
    inclusion in the log, but were not printed because of the rate-limiting.

    @param thd                 The THD that tries to log the statement.
    @retval false              Logging was not supressed, no summary needed.
    @retval true               Logging was supressed; a summary was printed.
  */
  bool flush(THD *thd);

  /**
    Top-level function.
    @param thd                 The THD that tries to log the statement.
    @retval true               Logging should be supressed.
    @retval false              Logging should not be supressed.
  */
  bool log(THD *thd);
};



/**
  A registry for item tree transformations performed during
  query optimization. We register only those changes which require
  a rollback to re-execute a prepared statement or stored procedure
  yet another time.
*/

struct Item_change_record: public ilink<Item_change_record>
{
  Item **place;
  Item *old_value;
};

typedef I_List<Item_change_record> Item_change_list;

/**
  @class Sub_statement_state
  @brief Used to save context when executing a function or trigger
*/

/* Defines used for Sub_statement_state::in_sub_stmt */

#define SUB_STMT_TRIGGER 1
#define SUB_STMT_FUNCTION 2


class Sub_statement_state
{
public:
  ulonglong option_bits;
  ulonglong first_successful_insert_id_in_prev_stmt;
  ulonglong first_successful_insert_id_in_cur_stmt, insert_id_for_cur_row;
  Discrete_interval auto_inc_interval_for_cur_row;
  Discrete_intervals_list auto_inc_intervals_forced;
  ulonglong limit_found_rows;
  ha_rows    cuted_fields, sent_row_count, examined_row_count;
  ulong client_capabilities;
  uint in_sub_stmt;
  bool last_insert_id_used;
};


/* Flags for the THD::system_thread variable */
enum enum_thread_type
{
  NON_SYSTEM_THREAD= 0,
  SYSTEM_THREAD_DELAYED_INSERT= 1,
  SYSTEM_THREAD_SLAVE_IO= 2,
  SYSTEM_THREAD_SLAVE_SQL= 4,
  SYSTEM_THREAD_NDBCLUSTER_BINLOG= 8,
  SYSTEM_THREAD_EVENT_SCHEDULER= 16,
  SYSTEM_THREAD_EVENT_WORKER= 32,
  SYSTEM_THREAD_INFO_REPOSITORY= 64,
  SYSTEM_THREAD_SLAVE_WORKER= 128
};

inline char const *
show_system_thread(enum_thread_type thread)
{
#define RETURN_NAME_AS_STRING(NAME) case (NAME): return #NAME
  switch (thread) {
    static char buf[64];
    RETURN_NAME_AS_STRING(NON_SYSTEM_THREAD);
    RETURN_NAME_AS_STRING(SYSTEM_THREAD_DELAYED_INSERT);
    RETURN_NAME_AS_STRING(SYSTEM_THREAD_SLAVE_IO);
    RETURN_NAME_AS_STRING(SYSTEM_THREAD_SLAVE_SQL);
    RETURN_NAME_AS_STRING(SYSTEM_THREAD_NDBCLUSTER_BINLOG);
    RETURN_NAME_AS_STRING(SYSTEM_THREAD_EVENT_SCHEDULER);
    RETURN_NAME_AS_STRING(SYSTEM_THREAD_EVENT_WORKER);
    RETURN_NAME_AS_STRING(SYSTEM_THREAD_INFO_REPOSITORY);
    RETURN_NAME_AS_STRING(SYSTEM_THREAD_SLAVE_WORKER);
  default:
    sprintf(buf, "<UNKNOWN SYSTEM THREAD: %d>", thread);
    return buf;
  }
#undef RETURN_NAME_AS_STRING
}

/**
  This class represents the interface for internal error handlers.
  Internal error handlers are exception handlers used by the server
  implementation.
*/
class Internal_error_handler
{
protected:
  Internal_error_handler() :
    m_prev_internal_handler(NULL)
  {}

  virtual ~Internal_error_handler() {}

public:
  /**
    Handle a sql condition.
    This method can be implemented by a subclass to achieve any of the
    following:
    - mask a warning/error internally, prevent exposing it to the user,
    - mask a warning/error and throw another one instead.
    When this method returns true, the sql condition is considered
    'handled', and will not be propagated to upper layers.
    It is the responsability of the code installing an internal handler
    to then check for trapped conditions, and implement logic to recover
    from the anticipated conditions trapped during runtime.

    This mechanism is similar to C++ try/throw/catch:
    - 'try' correspond to <code>THD::push_internal_handler()</code>,
    - 'throw' correspond to <code>my_error()</code>,
    which invokes <code>my_message_sql()</code>,
    - 'catch' correspond to checking how/if an internal handler was invoked,
    before removing it from the exception stack with
    <code>THD::pop_internal_handler()</code>.

    @param thd the calling thread
    @param cond the condition raised.
    @return true if the condition is handled
  */
  virtual bool handle_condition(THD *thd,
                                uint sql_errno,
                                const char* sqlstate,
                                Sql_condition::enum_warning_level level,
                                const char* msg,
                                Sql_condition ** cond_hdl) = 0;

private:
  Internal_error_handler *m_prev_internal_handler;
  friend class THD;
};


/**
  Implements the trivial error handler which cancels all error states
  and prevents an SQLSTATE to be set.
*/

class Dummy_error_handler : public Internal_error_handler
{
public:
  bool handle_condition(THD *thd,
                        uint sql_errno,
                        const char* sqlstate,
                        Sql_condition::enum_warning_level level,
                        const char* msg,
                        Sql_condition ** cond_hdl)
  {
    /* Ignore error */
    return TRUE;
  }
};


/**
  This class is an internal error handler implementation for
  DROP TABLE statements. The thing is that there may be warnings during
  execution of these statements, which should not be exposed to the user.
  This class is intended to silence such warnings.
*/

class Drop_table_error_handler : public Internal_error_handler
{
public:
  Drop_table_error_handler() {}

public:
  bool handle_condition(THD *thd,
                        uint sql_errno,
                        const char* sqlstate,
                        Sql_condition::enum_warning_level level,
                        const char* msg,
                        Sql_condition ** cond_hdl);

private:
};

extern "C" void my_message_sql(uint error, const char *str, myf MyFlags);


/*
  Convert microseconds since epoch to timeval.
  @param     micro_time  Microseconds.
  @param OUT tm          A timeval variable to write to.
*/
static inline void
my_micro_time_to_timeval(ulonglong micro_time, struct timeval *tm)
{
  tm->tv_sec=  (long) (micro_time / 1000000);
  tm->tv_usec= (long) (micro_time % 1000000);
}

typedef struct
{
  struct timeval start_time;
  ulonglong start_utime;
} QUERY_START_TIME_INFO;

/**
  @class THD
  For each client connection we create a separate thread with THD serving as
  a thread/connection descriptor
*/

class THD : public Statement
{
private:
  inline bool is_stmt_prepare() const
  { DBUG_ASSERT(0); return Statement::is_stmt_prepare(); }

  inline bool is_stmt_prepare_or_first_sp_execute() const
  { DBUG_ASSERT(0); return Statement::is_stmt_prepare_or_first_sp_execute(); }

  inline bool is_stmt_prepare_or_first_stmt_execute() const
  { DBUG_ASSERT(0); return Statement::is_stmt_prepare_or_first_stmt_execute(); }

  inline bool is_conventional() const
  { DBUG_ASSERT(0); return Statement::is_conventional(); }

public:
  void reset_for_next_command();
  /*
    Constant for THD::where initialization in the beginning of every query.

    It's needed because we do not save/restore THD::where normally during
    primary (non subselect) query execution.
  */
  static const char * const DEFAULT_WHERE;

  NET	  net;				// client connection descriptor
  /** Aditional network instrumentation for the server only. */
  NET_SERVER m_net_server_extension;
  HASH    user_vars;			// hash for user variables
  String  convert_buffer;               // buffer for charset conversions
  struct  rand_struct rand;		// used for authentication
  struct  system_variables variables;	// Changeable local variables
  THR_LOCK_INFO lock_info;              // Locking info of this thread
  /**
    Protects THD data accessed from other threads:
    - thd->query and thd->query_length (used by SHOW ENGINE
      INNODB STATUS and SHOW PROCESSLIST
    - thd->mysys_var (used by KILL statement and shutdown).
    Is locked when THD is deleted.
  */
  mysql_mutex_t LOCK_thd_data;
  /*
    A pointer to the stack frame of handle_one_connection(),
    which is called first in the thread for handling a client
  */
  char	  *thread_stack;

  /**
    Currently selected catalog.
  */
  char *catalog;

  /**
    @note
    Some members of THD (currently 'Statement::db',
    'catalog' and 'query')  are set and alloced by the slave SQL thread
    (for the THD of that thread); that thread is (and must remain, for now)
    the only responsible for freeing these 3 members. If you add members
    here, and you add code to set them in replication, don't forget to
    free_them_and_set_them_to_0 in replication properly. For details see
    the 'err:' label of the handle_slave_sql() in sql/slave.cc.

    @see handle_slave_sql
  */

  Security_context main_security_ctx;
  Security_context *security_ctx;

  /*
    Points to info-string that we show in SHOW PROCESSLIST
    You are supposed to update thd->proc_info only if you have coded
    a time-consuming piece that MySQL can get stuck in for a long time.

    Set it using the  thd_proc_info(THD *thread, const char *message)
    macro/function.

    This member is accessed and assigned without any synchronization.
    Therefore, it may point only to constant (statically
    allocated) strings, which memory won't go away over time.
  */
  const char *proc_info;

private:
  unsigned int m_current_stage_key;

public:
  void enter_stage(const PSI_stage_info *stage,
                   PSI_stage_info *old_stage,
                   const char *calling_func,
                   const char *calling_file,
                   const unsigned int calling_line);

  const char *get_proc_info() const
  { return proc_info; }

  /*
    Used in error messages to tell user in what part of MySQL we found an
    error. E. g. when where= "having clause", if fix_fields() fails, user
    will know that the error was in having clause.
  */
  const char *where;

  ulong client_capabilities;		/* What the client supports */

#ifndef DBUG_OFF
  uint dbug_sentry; // watch out for memory corruption
#endif
  struct st_my_thread_var *mysys_var;

private:
  /**
    Type of current query: COM_STMT_PREPARE, COM_QUERY, etc.
    Set from first byte of the packet in do_command()
  */
  enum enum_server_command m_command;

public:
  struct timeval start_time;
  struct timeval user_time;
  // track down slow pthread_create
  ulonglong  prior_thr_create_utime, thr_create_utime;
  ulonglong  start_utime, utime_after_lock, utime_after_query;

  thr_lock_type update_lock_default;
  Delayed_insert *di;

  /*** Following variables used in slow_extended.patch ***/
  /*
    Variable bytes_send_old saves value of thd->status_var.bytes_sent
    before query execution.
  */
  ulonglong  bytes_sent_old;
  /*
    Query can generate several errors/warnings during execution
    (see THD::handle_condition comment in sql_class.h)
    Variable last_errno contains the last error/warning acquired during
    query execution.
  */
  uint       last_errno;
  /*** The variables above used in slow_extended.patch ***/

  /*** Following methods used in slow_extended.patch ***/
  void clear_slow_extended();
  void reset_sub_statement_state_slow_extended(Sub_statement_state *backup);
  void restore_sub_statement_state_slow_extended(const Sub_statement_state *backup);
  /*** The methods above used in slow_extended.patch ***/

  /* <> 0 if we are inside of trigger or stored function. */
  uint in_sub_stmt;

  /* Do not set socket timeouts for wait_timeout (used with threadpool) */
  bool skip_wait_timeout;

  /** 
    Used by fill_status() to avoid acquiring LOCK_status mutex twice
    when this function is called recursively (e.g. queries 
    that contains SELECT on I_S.GLOBAL_STATUS with subquery on the 
    same I_S table).
    Incremented each time fill_status() function is entered and 
    decremented each time before it returns from the function.
  */
  uint fill_status_recursion_level;

  bool order_deterministic;


#ifndef MYSQL_CLIENT

  /** Tells whether the given optimizer_switch flag is on */
  inline bool optimizer_switch_flag(ulonglong flag) const
  {
    return (variables.optimizer_switch & flag);
  }

  /** Timer object. */
  struct st_thd_timer *timer, *timer_cache;


public:
  void issue_unsafe_warnings();

#endif /* MYSQL_CLIENT */

public:

#ifndef __WIN__
  sigset_t signals;
#endif
#ifdef SIGNAL_WITH_VIO_SHUTDOWN
  Vio* active_vio;
#endif
  /*
    This is to track items changed during execution of a prepared
    statement/stored procedure. It's created by
    register_item_tree_change() in memory root of THD, and freed in
    rollback_item_tree_changes(). For conventional execution it's always
    empty.
  */
  Item_change_list change_list;

  /*
    A permanent memory area of the statement. For conventional
    execution, the parsed tree and execution runtime reside in the same
    memory root. In this case stmt_arena points to THD. In case of
    a prepared statement or a stored procedure statement, thd->mem_root
    conventionally points to runtime memory, and thd->stmt_arena
    points to the memory of the PS/SP, where the parsed tree of the
    statement resides. Whenever you need to perform a permanent
    transformation of a parsed tree, you should allocate new memory in
    stmt_arena, to allow correct re-execution of PS/SP.
    Note: in the parser, stmt_arena == thd, even for PS/SP.
  */
  Query_arena *stmt_arena;

  /*
    map for tables that will be updated for a multi-table update query
    statement, for other query statements, this will be zero.
  */
  table_map table_map_for_update;

  /* Tells if LAST_INSERT_ID(#) was called for the current statement */
  bool arg_of_last_insert_id_function;
  /*
    ALL OVER THIS FILE, "insert_id" means "*automatically generated* value for
    insertion into an auto_increment column".
  */
  /*
    This is the first autogenerated insert id which was *successfully*
    inserted by the previous statement (exactly, if the previous statement
    didn't successfully insert an autogenerated insert id, then it's the one
    of the statement before, etc).
    It can also be set by SET LAST_INSERT_ID=# or SELECT LAST_INSERT_ID(#).
    It is returned by LAST_INSERT_ID().
  */
  ulonglong  first_successful_insert_id_in_prev_stmt;
  /*
    Variant of the above, used for storing in statement-based binlog. The
    difference is that the one above can change as the execution of a stored
    function progresses, while the one below is set once and then does not
    change (which is the value which statement-based binlog needs).
  */
  ulonglong  first_successful_insert_id_in_prev_stmt_for_binlog;
  /*
    This is the first autogenerated insert id which was *successfully*
    inserted by the current statement. It is maintained only to set
    first_successful_insert_id_in_prev_stmt when statement ends.
  */
  ulonglong  first_successful_insert_id_in_cur_stmt;
  /*
    We follow this logic:
    - when stmt starts, first_successful_insert_id_in_prev_stmt contains the
    first insert id successfully inserted by the previous stmt.
    - as stmt makes progress, handler::insert_id_for_cur_row changes;
    every time get_auto_increment() is called,
    auto_inc_intervals_in_cur_stmt_for_binlog is augmented with the
    reserved interval (if statement-based binlogging).
    - at first successful insertion of an autogenerated value,
    first_successful_insert_id_in_cur_stmt is set to
    handler::insert_id_for_cur_row.
    - when stmt goes to binlog,
    auto_inc_intervals_in_cur_stmt_for_binlog is binlogged if
    non-empty.
    - when stmt ends, first_successful_insert_id_in_prev_stmt is set to
    first_successful_insert_id_in_cur_stmt.
  */
  /*
    stmt_depends_on_first_successful_insert_id_in_prev_stmt is set when
    LAST_INSERT_ID() is used by a statement.
    If it is set, first_successful_insert_id_in_prev_stmt_for_binlog will be
    stored in the statement-based binlog.
    This variable is CUMULATIVE along the execution of a stored function or
    trigger: if one substatement sets it to 1 it will stay 1 until the
    function/trigger ends, thus making sure that
    first_successful_insert_id_in_prev_stmt_for_binlog does not change anymore
    and is propagated to the caller for binlogging.
  */
  bool       stmt_depends_on_first_successful_insert_id_in_prev_stmt;
  /*
    List of auto_increment intervals reserved by the thread so far, for
    storage in the statement-based binlog.
    Note that its minimum is not first_successful_insert_id_in_cur_stmt:
    assuming a table with an autoinc column, and this happens:
    INSERT INTO ... VALUES(3);
    SET INSERT_ID=3; INSERT IGNORE ... VALUES (NULL);
    then the latter INSERT will insert no rows
    (first_successful_insert_id_in_cur_stmt == 0), but storing "INSERT_ID=3"
    in the binlog is still needed; the list's minimum will contain 3.
    This variable is cumulative: if several statements are written to binlog
    as one (stored functions or triggers are used) this list is the
    concatenation of all intervals reserved by all statements.
  */
  Discrete_intervals_list auto_inc_intervals_in_cur_stmt_for_binlog;
  /* Used by replication and SET INSERT_ID */
  Discrete_intervals_list auto_inc_intervals_forced;
  /*
    There is BUG#19630 where statement-based replication of stored
    functions/triggers with two auto_increment columns breaks.
    We however ensure that it works when there is 0 or 1 auto_increment
    column; our rules are
    a) on master, while executing a top statement involving substatements,
    first top- or sub- statement to generate auto_increment values wins the
    exclusive right to see its values be written to binlog (the write
    will be done by the statement or its caller), and the losers won't see
    their values be written to binlog.
    b) on slave, while replicating a top statement involving substatements,
    first top- or sub- statement to need to read auto_increment values from
    the master's binlog wins the exclusive right to read them (so the losers
    won't read their values from binlog but instead generate on their own).
    a) implies that we mustn't backup/restore
    auto_inc_intervals_in_cur_stmt_for_binlog.
    b) implies that we mustn't backup/restore auto_inc_intervals_forced.

    If there are more than 1 auto_increment columns, then intervals for
    different columns may mix into the
    auto_inc_intervals_in_cur_stmt_for_binlog list, which is logically wrong,
    but there is no point in preventing this mixing by preventing intervals
    from the secondly inserted column to come into the list, as such
    prevention would be wrong too.
    What will happen in the case of
    INSERT INTO t1 (auto_inc) VALUES(NULL);
    where t1 has a trigger which inserts into an auto_inc column of t2, is
    that in binlog we'll store the interval of t1 and the interval of t2 (when
    we store intervals, soon), then in slave, t1 will use both intervals, t2
    will use none; if t1 inserts the same number of rows as on master,
    normally the 2nd interval will not be used by t1, which is fine. t2's
    values will be wrong if t2's internal auto_increment counter is different
    from what it was on master (which is likely). In 5.1, in mixed binlogging
    mode, row-based binlogging is used for such cases where two
    auto_increment columns are inserted.
  */
  inline void record_first_successful_insert_id_in_cur_stmt(ulonglong id_arg)
  {
    if (first_successful_insert_id_in_cur_stmt == 0)
      first_successful_insert_id_in_cur_stmt= id_arg;
  }
  inline ulonglong read_first_successful_insert_id_in_prev_stmt(void)
  {
    if (!stmt_depends_on_first_successful_insert_id_in_prev_stmt)
    {
      /* It's the first time we read it */
      first_successful_insert_id_in_prev_stmt_for_binlog=
        first_successful_insert_id_in_prev_stmt;
      stmt_depends_on_first_successful_insert_id_in_prev_stmt= 1;
    }
    return first_successful_insert_id_in_prev_stmt;
  }
  /*
    Used by Intvar_log_event::do_apply_event() and by "SET INSERT_ID=#"
    (mysqlbinlog). We'll soon add a variant which can take many intervals in
    argument.
  */
  inline void force_one_auto_inc_interval(ulonglong next_id)
  {
    auto_inc_intervals_forced.empty(); // in case of multiple SET INSERT_ID
    auto_inc_intervals_forced.append(next_id, ULONGLONG_MAX, 0);
  }

  ulonglong  limit_found_rows;

private:
  /**
    Stores the result of ROW_COUNT() function.

    ROW_COUNT() function is a MySQL extention, but we try to keep it
    similar to ROW_COUNT member of the GET DIAGNOSTICS stack of the SQL
    standard (see SQL99, part 2, search for ROW_COUNT). It's value is
    implementation defined for anything except INSERT, DELETE, UPDATE.

    ROW_COUNT is assigned according to the following rules:

      - In my_ok():
        - for DML statements: to the number of affected rows;
        - for DDL statements: to 0.

      - In my_eof(): to -1 to indicate that there was a result set.

        We derive this semantics from the JDBC specification, where int
        java.sql.Statement.getUpdateCount() is defined to (sic) "return the
        current result as an update count; if the result is a ResultSet
        object or there are no more results, -1 is returned".

      - In my_error(): to -1 to be compatible with the MySQL C API and
        MySQL ODBC driver.

      - For SIGNAL statements: to 0 per WL#2110 specification (see also
        sql_signal.cc comment). Zero is used since that's the "default"
        value of ROW_COUNT in the diagnostics area.
  */

  longlong m_row_count_func;    /* For the ROW_COUNT() function */

public:
  inline longlong get_row_count_func() const
  {
    return m_row_count_func;
  }

  inline void set_row_count_func(longlong row_count_func)
  {
    m_row_count_func= row_count_func;
  }

  ha_rows    cuted_fields;

private:
  /**
    Number of rows we actually sent to the client, including "synthetic"
    rows in ROLLUP etc.
  */
  ha_rows m_sent_row_count;

  /**
    Number of rows read and/or evaluated for a statement. Used for
    slow log reporting.

    An examined row is defined as a row that is read and/or evaluated
    according to a statement condition, including in
    create_sort_index(). Rows may be counted more than once, e.g., a
    statement including ORDER BY could possibly evaluate the row in
    filesort() before reading it for e.g. update.
  */
  ha_rows m_examined_row_count;

private:
  USER_CONN *m_user_connect;

public:
  void set_user_connect(USER_CONN *uc);
  const USER_CONN* get_user_connect()
  { return m_user_connect; }

  void increment_user_connections_counter();
  void decrement_user_connections_counter();

  void increment_con_per_hour_counter();

  void increment_updates_counter();

  void increment_questions_counter();

  void time_out_user_resource_limits();

public:
  ha_rows get_sent_row_count() const
  { return m_sent_row_count; }

  ha_rows get_examined_row_count() const
  { return m_examined_row_count; }

  void set_sent_row_count(ha_rows count);
  void set_examined_row_count(ha_rows count);

  void inc_sent_row_count(ha_rows count);
  void inc_examined_row_count(ha_rows count);

  void inc_status_created_tmp_disk_tables();
  void inc_status_created_tmp_files();
  void inc_status_created_tmp_tables();
  void inc_status_select_full_join();
  void inc_status_select_full_range_join();
  void inc_status_select_range();
  void inc_status_select_range_check();
  void inc_status_select_scan();
  void inc_status_sort_merge_passes();
  void inc_status_sort_range();
  void inc_status_sort_rows(ha_rows count);
  void inc_status_sort_scan();
  void set_status_no_index_used();
  void set_status_no_good_index_used();

  const CHARSET_INFO *db_charset;

  /** Current statement instrumentation. */
  PSI_statement_locker *m_statement_psi;
#ifdef HAVE_PSI_STATEMENT_INTERFACE
  /** Current statement instrumentation state. */
  PSI_statement_locker_state m_statement_state;
#endif /* HAVE_PSI_STATEMENT_INTERFACE */
  /** Idle instrumentation. */
  PSI_idle_locker *m_idle_psi;
#ifdef HAVE_PSI_IDLE_INTERFACE
  /** Idle instrumentation state. */
  PSI_idle_locker_state m_idle_state;
#endif /* HAVE_PSI_IDLE_INTERFACE */
  /** True if the server code is IDLE for this connection. */
  bool m_server_idle;

  /*
    Id of current query. Statement can be reused to execute several queries
    query_id is global in context of the whole MySQL server.
    ID is automatically generated from mutex-protected counter.
    It's used in handler code for various purposes: to check which columns
    from table are necessary for this select, to check if it's necessary to
    update auto-updatable fields (like auto_increment and timestamp).
  */
  query_id_t query_id;
  ulong      col_access;

  /* Statement id is thread-wide. This counter is used to generate ids */
  ulong      statement_id_counter;
  ulong	     rand_saved_seed1, rand_saved_seed2;
  pthread_t  real_id;                           /* For debugging */
  my_thread_id  thread_id;
  uint	     tmp_table;
  uint	     server_status,open_options;
  enum enum_thread_type system_thread;
  uint       select_number;             //number of select (used for EXPLAIN)
  /*
    Current or next transaction isolation level.
    When a connection is established, the value is taken from
    @@session.tx_isolation (default transaction isolation for
    the session), which is in turn taken from @@global.tx_isolation
    (the global value).
    If there is no transaction started, this variable
    holds the value of the next transaction's isolation level.
    When a transaction starts, the value stored in this variable
    becomes "actual".
    At transaction commit or rollback, we assign this variable
    again from @@session.tx_isolation.
    The only statement that can otherwise change the value
    of this variable is SET TRANSACTION ISOLATION LEVEL.
    Its purpose is to effect the isolation level of the next
    transaction in this session. When this statement is executed,
    the value in this variable is changed. However, since
    this statement is only allowed when there is no active
    transaction, this assignment (naturally) only affects the
    upcoming transaction.
    At the end of the current active transaction the value is
    be reset again from @@session.tx_isolation, as described
    above.
  */
  enum_tx_isolation tx_isolation;
  /*
    Current or next transaction access mode.
    See comment above regarding tx_isolation.
  */
  bool              tx_read_only;
  ha_rows    updated_row_count;
  ha_rows    sent_row_count_2; /* for userstat */

  DYNAMIC_ARRAY user_var_events;        /* For user variables replication */
  MEM_ROOT      *user_var_events_alloc; /* Allocate above array elements here */


  /*
    Error code from committing or rolling back the transaction.
  */
  enum Commit_error
  {
    CE_NONE= 0,
    CE_FLUSH_ERROR,
    CE_COMMIT_ERROR,
    CE_ERROR_COUNT
  } commit_error;

  /*
    Define durability properties that engines may check to
    improve performance.
  */
  enum durability_properties durability_property;

  /*
    If checking this in conjunction with a wait condition, please
    include a check after enter_cond() if you want to avoid a race
    condition. For details see the implementation of awake(),
    especially the "broadcast" part.
  */
  enum killed_state
  {
    NOT_KILLED=0,
    KILL_BAD_DATA=1,
    KILL_CONNECTION=ER_SERVER_SHUTDOWN,
    KILL_QUERY=ER_QUERY_INTERRUPTED,
    KILL_TIMEOUT=ER_QUERY_TIMEOUT,
    KILLED_NO_VALUE      /* means neither of the states */
  };
  killed_state volatile killed;

  /* scramble - random string sent to client on handshake */
  char	     scramble[SCRAMBLE_LENGTH+1];

  /// @todo: slave_thread is completely redundant, we should use 'system_thread' instead /sven
  bool       slave_thread, one_shot_set;
  bool       extra_port;                        /* If extra connection */

  bool	     no_errors;
  uchar      password;
  /**
    Set to TRUE if execution of the current compound statement
    can not continue. In particular, disables activation of
    CONTINUE or EXIT handlers of stored routines.
    Reset in the end of processing of the current user request, in
    @see mysql_reset_thd_for_next_command().
  */
  bool is_fatal_error;
  /**
    Set by a storage engine to request the entire
    transaction (that possibly spans multiple engines) to
    rollback. Reset in ha_rollback.
  */
  bool       transaction_rollback_request;
  /**
    TRUE if we are in a sub-statement and the current error can
    not be safely recovered until we left the sub-statement mode.
    In particular, disables activation of CONTINUE and EXIT
    handlers inside sub-statements. E.g. if it is a deadlock
    error and requires a transaction-wide rollback, this flag is
    raised (traditionally, MySQL first has to close all the reads
    via @see handler::ha_index_or_rnd_end() and only then perform
    the rollback).
    Reset to FALSE when we leave the sub-statement mode.
  */
  bool       is_fatal_sub_stmt_error;
  bool	     query_start_used, query_start_usec_used;
  bool       rand_used, time_zone_used;
  /* for IS NULL => = last_insert_id() fix in remove_eq_conds() */
  bool       substitute_null_with_insert_id;
  bool	     in_lock_tables;
  /**
    True if a slave error. Causes the slave to stop. Not the same
    as the statement execution error (is_error()), since
    a statement may be expected to return an error, e.g. because
    it returned an error on master, and this is OK on the slave.
  */
  bool       is_slave_error;
  bool       bootstrap;

  /**  is set if some thread specific value(s) used in a statement. */
  bool       thread_specific_used;
  /**  
    is set if a statement accesses a temporary table created through
    CREATE TEMPORARY TABLE. 
  */
  bool	     charset_is_system_charset, charset_is_collation_connection;
  bool       charset_is_character_set_filesystem;
  bool       enable_slow_log;   /* enable slow log for current statement */
  bool	     abort_on_warning;
  bool 	     got_warning;       /* Set on call to push_warning() */
  /* set during loop of derived table processing */
  bool       derived_tables_processing;
  my_bool    tablespace_op;	/* This is TRUE in DISCARD/IMPORT TABLESPACE */


  /** number of name_const() substitutions, see sp_head.cc:subst_spvars() */
  uint       query_name_consts;

  /*
    Used to update global user stats.  The global user stats are updated
    occasionally with the 'diff' variables.  After the update, the 'diff'
    variables are reset to 0.
  */
  // Time when the current thread connected to MySQL.
  time_t current_connect_time;
  // Last time when THD stats were updated in global_user_stats.
  time_t last_global_update_time;
  // Busy (non-idle) time for just one command.
  double busy_time;
  // Busy time not updated in global_user_stats yet.
  double diff_total_busy_time;
  // Cpu (non-idle) time for just one thread.
  double cpu_time;
  // Cpu time not updated in global_user_stats yet.
  double diff_total_cpu_time;
  /* bytes counting */
  ulonglong bytes_received;
  ulonglong diff_total_bytes_received;
  ulonglong bytes_sent;
  ulonglong diff_total_bytes_sent;
  ulonglong binlog_bytes_written;
  ulonglong diff_total_binlog_bytes_written;

  // Number of rows not reflected in global_user_stats yet.
  ha_rows diff_total_sent_rows, diff_total_updated_rows, diff_total_read_rows;
  // Number of commands not reflected in global_user_stats yet.
  ulonglong diff_select_commands, diff_update_commands, diff_other_commands;
  // Number of transactions not reflected in global_user_stats yet.
  ulonglong diff_commit_trans, diff_rollback_trans;
  // Number of connection errors not reflected in global_user_stats yet.
  ulonglong diff_denied_connections, diff_lost_connections;
  // Number of db access denied, not reflected in global_user_stats yet.
  ulonglong diff_access_denied_errors;
  // Number of queries that return 0 rows
  ulonglong diff_empty_queries;

  // Per account query delay in miliseconds. When not 0, sleep this number of
  // milliseconds before every SQL command.
  ulonglong query_delay_millis;

  /* Used by the sys_var class to store temporary values */
  union
  {
    my_bool   my_bool_value;
    long      long_value;
    ulong     ulong_value;
    ulonglong ulonglong_value;
    double    double_value;
  } sys_var_tmp;

  /**
    Internal parser state.
    Note that since the parser is not re-entrant, we keep only one parser
    state here. This member is valid only when executing code during parsing.
  */
  Parser_state *m_parser_state;

#ifdef WITH_PARTITION_STORAGE_ENGINE
  partition_info *work_part_info;
#endif

#ifndef EMBEDDED_LIBRARY
  /**
    Array of active audit plugins which have been used by this THD.
    This list is later iterated to invoke release_thd() on those
    plugins.
  */
  DYNAMIC_ARRAY audit_class_plugins;
  /**
    Array of bits indicating which audit classes have already been
    added to the list of audit plugins which are currently in use.
  */
  unsigned long audit_class_mask[MYSQL_AUDIT_CLASS_MASK_SIZE];
#endif

#if defined(ENABLED_DEBUG_SYNC)
  /* Debug Sync facility. See debug_sync.cc. */
  struct st_debug_sync_control *debug_sync_control;
#endif /* defined(ENABLED_DEBUG_SYNC) */

  // We don't want to load/unload plugins for unit tests.
  bool m_enable_plugins;

  THD(bool enable_plugins= true);

  /*
    The THD dtor is effectively split in two:
      THD::release_resources() and ~THD().

    We want to minimize the time we hold LOCK_thread_count,
    so when destroying a global thread, do:

    thd->release_resources()
    remove_global_thread(thd);
    delete thd;
   */
  ~THD();

  void release_resources();
  bool release_resources_done() const { return m_release_resources_done; }

private:
  bool m_release_resources_done;
  bool cleanup_done;
  void cleanup(void);

public:
  void init(void);
  void reset_stats(void);
  void reset_diff_stats(void);
  // ran_command is true when this is called immediately after a
  // command has been run.
  void update_stats(bool ran_command);
  void change_user(void);
  void cleanup_after_query();
  bool store_globals();
  bool restore_globals();
#ifdef SIGNAL_WITH_VIO_SHUTDOWN
  inline void set_active_vio(Vio* vio)
  {
    mysql_mutex_lock(&LOCK_thd_data);
    active_vio = vio;
    vio_set_thread_id(vio, pthread_self());
    mysql_mutex_unlock(&LOCK_thd_data);
  }
  inline void clear_active_vio()
  {
    mysql_mutex_lock(&LOCK_thd_data);
    active_vio = 0;
    mysql_mutex_unlock(&LOCK_thd_data);
  }
  void shutdown_active_vio();
#endif
  void awake(THD::killed_state state_to_set);

  /** Disconnect the associated communication endpoint. */
  void disconnect();

  // Begin implementation of MDL_context_owner interface.

  inline void
  enter_cond(mysql_cond_t *cond, mysql_mutex_t* mutex,
             const PSI_stage_info *stage, PSI_stage_info *old_stage,
             const char *src_function, const char *src_file,
             int src_line)
  {
    DBUG_ENTER("THD::enter_cond");
    mysql_mutex_assert_owner(mutex);
    DBUG_PRINT("debug", ("thd: 0x%llx, mysys_var: 0x%llx, current_mutex: 0x%llx -> 0x%llx",
                         (ulonglong) this,
                         (ulonglong) mysys_var,
                         (ulonglong) mysys_var->current_mutex,
                         (ulonglong) mutex));
    mysys_var->current_mutex = mutex;
    mysys_var->current_cond = cond;
    enter_stage(stage, old_stage, src_function, src_file, src_line);
    DBUG_VOID_RETURN;
  }
  inline void exit_cond(const PSI_stage_info *stage,
                        const char *src_function, const char *src_file,
                        int src_line)
  {
    DBUG_ENTER("THD::exit_cond");
    /*
      Putting the mutex unlock in thd->exit_cond() ensures that
      mysys_var->current_mutex is always unlocked _before_ mysys_var->mutex is
      locked (if that would not be the case, you'll get a deadlock if someone
      does a THD::awake() on you).
    */
    DBUG_PRINT("debug", ("thd: 0x%llx, mysys_var: 0x%llx, current_mutex: 0x%llx -> 0x%llx",
                         (ulonglong) this,
                         (ulonglong) mysys_var,
                         (ulonglong) mysys_var->current_mutex,
                         0ULL));
    mysql_mutex_unlock(mysys_var->current_mutex);
    mysql_mutex_lock(&mysys_var->mutex);
    mysys_var->current_mutex = 0;
    mysys_var->current_cond = 0;
    enter_stage(stage, NULL, src_function, src_file, src_line);
    mysql_mutex_unlock(&mysys_var->mutex);
    DBUG_VOID_RETURN;
  }

  virtual int is_killed() { return killed; }
  virtual bool is_timedout() const { return killed == KILL_TIMEOUT; }
  virtual THD* get_thd() { return this; }


  // End implementation of MDL_context_owner interface.

  inline sql_mode_t datetime_flags() const
  {
    return variables.sql_mode &
      (MODE_NO_ZERO_IN_DATE | MODE_NO_ZERO_DATE | MODE_INVALID_DATES);
  }
  inline bool is_strict_mode() const
  {
    return MY_TEST(variables.sql_mode & (MODE_STRICT_TRANS_TABLES |
                                         MODE_STRICT_ALL_TABLES));
  }
  inline time_t query_start()
  {
    query_start_used= 1;
    return start_time.tv_sec;
  }
  inline long query_start_usec()
  {
    query_start_usec_used= 1;
    return start_time.tv_usec;
  }
  inline timeval query_start_timeval()
  {
    query_start_used= query_start_usec_used= true;
    return start_time;
  }
  timeval query_start_timeval_trunc(uint decimals);
  inline void set_time()
  {
    start_utime= utime_after_lock= my_micro_time();
    if (user_time.tv_sec || user_time.tv_usec)
    {
      start_time= user_time;
    }
    else
      my_micro_time_to_timeval(start_utime, &start_time);

#ifdef HAVE_PSI_THREAD_INTERFACE
    PSI_THREAD_CALL(set_thread_start_time)(start_time.tv_sec);
#endif
  }
  inline void set_current_time()
  {
    my_micro_time_to_timeval(my_micro_time(), &start_time);
#ifdef HAVE_PSI_THREAD_INTERFACE
    PSI_THREAD_CALL(set_thread_start_time)(start_time.tv_sec);
#endif
  }
  inline void set_time(const struct timeval *t)
  {
    start_time= user_time= *t;
    start_utime= utime_after_lock= my_micro_time();
#ifdef HAVE_PSI_THREAD_INTERFACE
    PSI_THREAD_CALL(set_thread_start_time)(start_time.tv_sec);
#endif
  }
  void get_time(QUERY_START_TIME_INFO *time_info)
  {
    time_info->start_time= start_time;
    time_info->start_utime= start_utime;
  }
  void set_time(QUERY_START_TIME_INFO *time_info)
  {
    start_time= time_info->start_time;
    start_utime= time_info->start_utime;
  }
  /*TODO: this will be obsolete when we have support for 64 bit my_time_t */
  inline bool	is_valid_time() 
  { 
    return (IS_TIME_T_VALID_FOR_TIMESTAMP(start_time.tv_sec));
  }
  void set_time_after_lock()
  {
    utime_after_lock= my_micro_time();
    MYSQL_SET_STATEMENT_LOCK_TIME(m_statement_psi, (utime_after_lock - start_utime));
  }
  ulonglong current_utime()  { return my_micro_time(); }
  /**
   Update server status after execution of a top level statement.

   Currently only checks if a query was slow, and assigns
   the status accordingly.
   Evaluate the current time, and if it exceeds the long-query-time
   setting, mark the query as slow.
  */
  void update_server_status()
  {
    utime_after_query= current_utime();
    if (utime_after_query > utime_after_lock + variables.long_query_time)
      server_status|= SERVER_QUERY_WAS_SLOW;
  }
  inline ulonglong found_rows(void)
  {
    return limit_found_rows;
  }
  /**
    Returns TRUE if session is in a multi-statement transaction mode.

    OPTION_NOT_AUTOCOMMIT: When autocommit is off, a multi-statement
    transaction is implicitly started on the first statement after a
    previous transaction has been ended.

    OPTION_BEGIN: Regardless of the autocommit status, a multi-statement
    transaction can be explicitly started with the statements "START
    TRANSACTION", "BEGIN [WORK]", "[COMMIT | ROLLBACK] AND CHAIN", etc.

    Note: this doesn't tell you whether a transaction is active.
    A session can be in multi-statement transaction mode, and yet
    have no active transaction, e.g., in case of:
    set @@autocommit=0;
    set @a= 3;                                     <-- these statements don't
    set transaction isolation level serializable;  <-- start an active
    flush tables;                                  <-- transaction

    I.e. for the above scenario this function returns TRUE, even
    though no active transaction has begun.
    @sa in_active_multi_stmt_transaction()
  */
  inline bool in_multi_stmt_transaction_mode() const
  {
    return variables.option_bits & (OPTION_NOT_AUTOCOMMIT | OPTION_BEGIN);
  }
  /**
    TRUE if the session is in a multi-statement transaction mode
    (@sa in_multi_stmt_transaction_mode()) *and* there is an
    active transaction, i.e. there is an explicit start of a
    transaction with BEGIN statement, or implicit with a
    statement that uses a transactional engine.

    For example, these scenarios don't start an active transaction
    (even though the server is in multi-statement transaction mode):

    set @@autocommit=0;
    select * from nontrans_table;
    set @var=TRUE;
    flush tables;

    Note, that even for a statement that starts a multi-statement
    transaction (i.e. select * from trans_table), this
    flag won't be set until we open the statement's tables
    and the engines register themselves for the transaction
    (see trans_register_ha()),
    hence this method is reliable to use only after
    open_tables() has completed.

    Why do we need a flag?
    ----------------------
    We need to maintain a (at first glance redundant)
    session flag, rather than looking at thd->transaction.all.ha_list
    because of explicit start of a transaction with BEGIN. 

    I.e. in case of
    BEGIN;
    select * from nontrans_t1; <-- in_active_multi_stmt_transaction() is true
  */
  inline bool in_active_multi_stmt_transaction() const
  {
    return server_status & SERVER_STATUS_IN_TRANS;
  }

  LEX_STRING *make_lex_string(LEX_STRING *lex_str,
                              const char* str, uint length,
                              bool allocate_lex_string);

  bool convert_string(LEX_STRING *to, const CHARSET_INFO *to_cs,
		      const char *from, uint from_length,
		      const CHARSET_INFO *from_cs);

  bool convert_string(String *s, const CHARSET_INFO *from_cs,
                      const CHARSET_INFO *to_cs);


  /**
    Clear the current error, if any.
    We do not clear is_fatal_error or is_fatal_sub_stmt_error since we
    assume this is never called if the fatal error is set.
    @todo: To silence an error, one should use Internal_error_handler
    mechanism. In future this function will be removed.
  */
  inline void clear_error()
  {
    DBUG_ENTER("clear_error");
    if (get_stmt_da()->is_error())
      get_stmt_da()->reset_diagnostics_area();
    is_slave_error= 0;
    DBUG_VOID_RETURN;
  }
#ifndef EMBEDDED_LIBRARY
  inline bool vio_ok() const { return net.vio != 0; }
  /** Return FALSE if connection to client is broken. */
  virtual bool is_connected()
  {
    /*
      All system threads (e.g., the slave IO thread) are connected but
      not using vio. So this function always returns true for all
      system threads.
    */
    return system_thread || (vio_ok() ? vio_is_connected(net.vio) : FALSE);
  }
#else
  inline bool vio_ok() const { return true; }
  virtual bool is_connected() { return true; }
#endif
  /**
    Mark the current error as fatal. Warning: this does not
    set any error, it sets a property of the error, so must be
    followed or prefixed with my_error().
  */
  inline void fatal_error()
  {
    DBUG_ASSERT(get_stmt_da()->is_error() || killed);
    is_fatal_error= 1;
    DBUG_PRINT("error",("Fatal error set"));
  }
  /**
    TRUE if there is an error in the error stack.

    Please use this method instead of direct access to
    net.report_error.

    If TRUE, the current (sub)-statement should be aborted.
    The main difference between this member and is_fatal_error
    is that a fatal error can not be handled by a stored
    procedure continue handler, whereas a normal error can.

    To raise this flag, use my_error().
  */
  inline bool is_error() const { return get_stmt_da()->is_error(); }

  /// Returns Diagnostics-area for the current statement.
  Diagnostics_area *get_stmt_da()
  { return m_stmt_da; }

  /// Returns Diagnostics-area for the current statement.
  const Diagnostics_area *get_stmt_da() const
  { return m_stmt_da; }

  /// Sets Diagnostics-area for the current statement.
  void set_stmt_da(Diagnostics_area *da)
  { m_stmt_da= da; }

public:
  inline const CHARSET_INFO *charset()
  { return variables.character_set_client; }
  void update_charset();

  void change_item_tree(Item **place, Item *new_value)
  {
    /* TODO: check for OOM condition here */
    if (!stmt_arena->is_conventional())
    {
      DBUG_PRINT("info",
                 ("change_item_tree place %p old_value %p new_value %p",
                  place, *place, new_value));
      if (new_value)
        new_value->set_runtime_created(); /* Note the change of item tree */
      nocheck_register_item_tree_change(place, *place, mem_root);
    }
    *place= new_value;
  }

/*
  Find and update change record of an underlying item.

  @param old_ref The old place of moved expression.
  @param new_ref The new place of moved expression.
  @details
  During permanent transformations, e.g. join flattening in simplify_joins,
  a condition could be moved from one place to another, e.g. from on_expr
  to WHERE condition. If the moved condition has replaced some other with
  change_item_tree() function, the change record will restore old value
  to the wrong place during rollback_item_tree_changes. This function goes
  through the list of change records, and replaces Item_change_record::place.
*/
  void change_item_tree_place(Item **old_ref, Item **new_ref);
  void nocheck_register_item_tree_change(Item **place, Item *old_value,
                                         MEM_ROOT *runtime_memroot);
  void rollback_item_tree_changes();

  /*
    Cleanup statement parse state (parse tree, lex) and execution
    state after execution of a non-prepared SQL statement.
  */
  void end_statement();
  inline int killed_errno() const
  {
    killed_state killed_val; /* to cache the volatile 'killed' */
    return (killed_val= killed) != KILL_BAD_DATA ? killed_val : 0;
  }
  inline void send_kill_message() const
  {
    int err= killed_errno();
    if (err && !get_stmt_da()->is_set())
    {
      if ((err == KILL_CONNECTION) && !shutdown_in_progress)
        err = KILL_QUERY;
      /*
        KILL is fatal because:
        - if a condition handler was allowed to trap and ignore a KILL, one
        could create routines which the DBA could not kill
        - INSERT/UPDATE IGNORE should fail: if KILL arrives during
        JOIN::optimize(), statement cannot possibly run as its caller expected
        => "OK" would be misleading the caller.
      */
      my_message(err, ER(err), MYF(ME_FATALERROR));
    }
  }

  /* return TRUE if we will abort query if we make a warning now */
  inline bool really_abort_on_warning()
  {
    return abort_on_warning;
  }

  void set_status_var_init();
  void set_n_backup_active_arena(Query_arena *set, Query_arena *backup);
  void restore_active_arena(Query_arena *set, Query_arena *backup);

  /**
    Set the current database; use deep copy of C-string.

    @param new_db     a pointer to the new database name.
    @param new_db_len length of the new database name.

    Initialize the current database from a NULL-terminated string with
    length. If we run out of memory, we free the current database and
    return TRUE.  This way the user will notice the error as there will be
    no current database selected (in addition to the error message set by
    malloc).

    @note This operation just sets {db, db_length}. Switching the current
    database usually involves other actions, like switching other database
    attributes including security context. In the future, this operation
    will be made private and more convenient interface will be provided.

    @return Operation status
      @retval FALSE Success
      @retval TRUE  Out-of-memory error
  */
  bool set_db(const char *new_db, size_t new_db_len)
  {
    bool result;
    /*
      Acquiring mutex LOCK_thd_data as we either free the memory allocated
      for the database and reallocating the memory for the new db or memcpy
      the new_db to the db.
    */
    mysql_mutex_lock(&LOCK_thd_data);
    /* Do not reallocate memory if current chunk is big enough. */
    if (db && new_db && db_length >= new_db_len)
      memcpy(db, new_db, new_db_len+1);
    else
    {
      my_free(db);
      if (new_db)
        db= my_strndup(new_db, new_db_len, MYF(MY_WME | ME_FATALERROR));
      else
        db= NULL;
    }
    db_length= db ? new_db_len : 0;
    mysql_mutex_unlock(&LOCK_thd_data);
    result= new_db && !db;
#ifdef HAVE_PSI_THREAD_INTERFACE
    if (result)
      PSI_THREAD_CALL(set_thread_db)(new_db, static_cast<int>(new_db_len));
#endif
    return result;
  }

  /**
    Set the current database; use shallow copy of C-string.

    @param new_db     a pointer to the new database name.
    @param new_db_len length of the new database name.

    @note This operation just sets {db, db_length}. Switching the current
    database usually involves other actions, like switching other database
    attributes including security context. In the future, this operation
    will be made private and more convenient interface will be provided.
  */
  void reset_db(char *new_db, size_t new_db_len)
  {
    db= new_db;
    db_length= new_db_len;
#ifdef HAVE_PSI_THREAD_INTERFACE
    PSI_THREAD_CALL(set_thread_db)(new_db, static_cast<int>(new_db_len));
#endif
  }
  /*
    Copy the current database to the argument. Use the current arena to
    allocate memory for a deep copy: current database may be freed after
    a statement is parsed but before it's executed.
  */
  bool copy_db_to(char **p_db, size_t *p_db_length)
  {
    if (db == NULL)
    {
      my_message(ER_NO_DB_ERROR, ER(ER_NO_DB_ERROR), MYF(0));
      return TRUE;
    }
    *p_db= strmake(db, db_length);
    *p_db_length= db_length;
    return FALSE;
  }

  /* Returns string as 'IP:port' for the client-side
     of the connnection represented
     by 'client' as displayed by SHOW PROCESSLIST.
     Allocates memory from the heap of
     this THD and that is not reclaimed
     immediately, so use sparingly. May return NULL.
  */
  char *get_client_host_port(THD *client);

public:
  inline Internal_error_handler *get_internal_handler()
  { return m_internal_handler; }

  /**
    Add an internal error handler to the thread execution context.
    @param handler the exception handler to add
  */
  void push_internal_handler(Internal_error_handler *handler);

private:
  /**
    Handle a sql condition.
    @param sql_errno the condition error number
    @param sqlstate the condition sqlstate
    @param level the condition level
    @param msg the condition message text
    @param[out] cond_hdl the sql condition raised, if any
    @return true if the condition is handled
  */
  bool handle_condition(uint sql_errno,
                        const char* sqlstate,
                        Sql_condition::enum_warning_level level,
                        const char* msg,
                        Sql_condition ** cond_hdl);

public:
  /**
    Remove the error handler last pushed.
  */
  Internal_error_handler *pop_internal_handler();

  /**
    Raise an exception condition.
    @param code the MYSQL_ERRNO error code of the error
  */
  void raise_error(uint code);

  /**
    Raise an exception condition, with a formatted message.
    @param code the MYSQL_ERRNO error code of the error
  */
  void raise_error_printf(uint code, ...);

  /**
    Raise a completion condition (warning).
    @param code the MYSQL_ERRNO error code of the warning
  */
  void raise_warning(uint code);

  /**
    Raise a completion condition (warning), with a formatted message.
    @param code the MYSQL_ERRNO error code of the warning
  */
  void raise_warning_printf(uint code, ...);

  /**
    Raise a completion condition (note), with a fixed message.
    @param code the MYSQL_ERRNO error code of the note
  */
  void raise_note(uint code);

  /**
    Raise an completion condition (note), with a formatted message.
    @param code the MYSQL_ERRNO error code of the note
  */
  void raise_note_printf(uint code, ...);

private:
  /*
    Only the implementation of the SIGNAL and RESIGNAL statements
    is permitted to raise SQL conditions in a generic way,
    or to raise them by bypassing handlers (RESIGNAL).
    To raise a SQL condition, the code should use the public
    raise_error() or raise_warning() methods provided by class THD.
  */
  friend class Sql_cmd_common_signal;
  friend class Sql_cmd_signal;
  friend class Sql_cmd_resignal;
  friend void push_warning(THD*, Sql_condition::enum_warning_level, uint, const char*);
  friend void my_message_sql(uint, const char *, myf);

  /**
    Raise a generic SQL condition.
    @param sql_errno the condition error number
    @param sqlstate the condition SQLSTATE
    @param level the condition level
    @param msg the condition message text
    @return The condition raised, or NULL
  */
  Sql_condition*
  raise_condition(uint sql_errno,
                  const char* sqlstate,
                  Sql_condition::enum_warning_level level,
                  const char* msg);

public:
  /** Overloaded to guard query/query_length fields */
  virtual void set_statement(Statement *stmt);

  void set_command(enum enum_server_command command);

  inline enum enum_server_command get_command() const
  { return m_command; }

  /**
    Assign a new value to thd->query and thd->query_id and mysys_var.
    Protected with LOCK_thd_data mutex.
  */
  void set_query(char *query_arg, uint32 query_length_arg,
                 const CHARSET_INFO *cs_arg)
  {
    set_query(CSET_STRING(query_arg, query_length_arg, cs_arg));
  }
  void set_query(char *query_arg, uint32 query_length_arg) /*Mutex protected*/
  {
    set_query(CSET_STRING(query_arg, query_length_arg, charset()));
  }
  void set_query(const CSET_STRING &str); /* Mutex protected */
  void reset_query()               /* Mutex protected */
  { set_query(CSET_STRING()); }
  void set_query_and_id(char *query_arg, uint32 query_length_arg,
                        const CHARSET_INFO *cs, query_id_t new_query_id);
  void set_query_id(query_id_t new_query_id);
  void set_mysys_var(struct st_my_thread_var *new_mysys_var);
  int decide_logging_format(TABLE_LIST *tables);
  /**
    is_dml_gtid_compatible() and is_ddl_gtid_compatible() check if the
    statement that is about to be processed will safely get a
    GTID. Currently, the following cases may lead to errors
    (e.g. duplicated GTIDs) and as such are forbidden:

     1. Statements that could possibly do DML in a non-transactional
        table;

     2. CREATE...SELECT statement;

     3. CREATE TEMPORARY TABLE or DROP TEMPORARY TABLE within a transaction

    The first condition has to be checked in decide_logging_format,
    because that's where we know if the table is transactional or not.
    The second and third conditions have to be checked in
    mysql_execute_command because (1) that prevents implicit commit
    from being executed if the statement fails; (2) DROP TEMPORARY
    TABLE does not invoke decide_logging_format.

    Later, we can relax the first condition as follows:
     - do not wrap non-transactional updates inside BEGIN ... COMMIT
       when writing them to the binary log.
     - allow non-transactional updates that are made outside of
       transactional context

    Moreover, we can drop the second condition if we fix BUG#11756034.

    @param transactional_table true if the statement updates some
    transactional table; false otherwise.

    @param non_transactional_table true if the statement updates some
    non-transactional table; false otherwise.

    @param non_transactional_tmp_tables true if row binlog format is
    used and all non-transactional tables are temporary.

    @retval true if the statement is compatible;
    @retval false if the statement is not compatible.
  */
  bool
  is_dml_gtid_compatible(bool transactional_table,
                         bool non_transactional_table,
                         bool non_transactional_tmp_tables) const;
  bool is_ddl_gtid_compatible() const;
  void get_definer(LEX_USER *definer);
  void set_invoker(const LEX_STRING *user, const LEX_STRING *host)
  {
    invoker_user= *user;
    invoker_host= *host;
  }
  LEX_STRING get_invoker_user() { return invoker_user; }
  LEX_STRING get_invoker_host() { return invoker_host; }
  bool has_invoker() { return invoker_user.length > 0; }

#ifndef DBUG_OFF
private:
  int gis_debug; // Storage for "SELECT ST_GIS_DEBUG(param);"
public:
  int get_gis_debug() { return gis_debug; }
  void set_gis_debug(int arg) { gis_debug= arg; }
#endif

private:

  /** The current internal error handler for this thread, or NULL. */
  Internal_error_handler *m_internal_handler;

  /**
    The lex to hold the parsed tree of conventional (non-prepared) queries.
    Whereas for prepared and stored procedure statements we use an own lex
    instance for each new query, for conventional statements we reuse
    the same lex. (@see mysql_parse for details).
  */
  LEX main_lex;
  /**
    This memory root is used for two purposes:
    - for conventional queries, to allocate structures stored in main_lex
    during parsing, and allocate runtime data (execution plan, etc.)
    during execution.
    - for prepared queries, only to allocate runtime data. The parsed
    tree itself is reused between executions and thus is stored elsewhere.
  */
  MEM_ROOT main_mem_root;
  Diagnostics_area main_da;
  Diagnostics_area *m_stmt_da;

  /**
    It points to the invoker in the Query_log_event.
    SQL thread use it as the default definer in CREATE/ALTER SP, SF, Event,
    TRIGGER or VIEW statements or current user in account management
    statements if it is not NULL.
   */
  LEX_STRING invoker_user;
  LEX_STRING invoker_host;
};

/* Returns string as 'IP' for the client-side of the connection represented by
   'client'. Does not allocate memory. May return "".
*/
const char *get_client_host(THD *client);

/**
  A simple holder for the Prepared Statement Query_arena instance in THD.
  The class utilizes RAII technique to not forget to restore the THD arena.
*/
class Prepared_stmt_arena_holder
{
public:
  /**
    Constructs a new object, activates the persistent arena if requested and if
    a prepared statement or a stored procedure statement is being executed.

    @param thd                    Thread context.
    @param activate_now_if_needed Attempt to activate the persistent arena in
                                  the constructor or not.
  */
  Prepared_stmt_arena_holder(THD *thd, bool activate_now_if_needed= true)
   :m_thd(thd),
    m_arena(NULL)
  {
    if (activate_now_if_needed &&
        !m_thd->stmt_arena->is_conventional() &&
        m_thd->mem_root != m_thd->stmt_arena->mem_root)
    {
      m_thd->set_n_backup_active_arena(m_thd->stmt_arena, &m_backup);
      m_arena= m_thd->stmt_arena;
    }
  }

  /**
    Deactivate the persistent arena (restore the previous arena) if it has
    been activated.
  */
  ~Prepared_stmt_arena_holder()
  {
    if (is_activated())
      m_thd->restore_active_arena(m_arena, &m_backup);
  }

  bool is_activated() const
  { return m_arena != NULL; }

private:
  /// The thread context to work with.
  THD *const m_thd;

  /// The arena set by this holder (by activate()).
  Query_arena *m_arena;

  /// The arena state to be restored.
  Query_arena m_backup;
};


/** A short cut for thd->get_stmt_da()->set_ok_status(). */

inline void
my_ok(THD *thd, ulonglong affected_rows= 0, ulonglong id= 0,
        const char *message= NULL)
{
  thd->set_row_count_func(affected_rows);
  thd->get_stmt_da()->set_ok_status(affected_rows, id, message);
}


/** A short cut for thd->get_stmt_da()->set_eof_status(). */

inline void
my_eof(THD *thd)
{
  thd->set_row_count_func(-1);
  thd->get_stmt_da()->set_eof_status(thd);
}

#define tmp_disable_binlog(A)       \
  {ulonglong tmp_disable_binlog__save_options= (A)->variables.option_bits; \
  (A)->variables.option_bits&= ~OPTION_BIN_LOG

#define reenable_binlog(A)   (A)->variables.option_bits= tmp_disable_binlog__save_options;}


LEX_STRING *
make_lex_string_root(MEM_ROOT *mem_root,
                     LEX_STRING *lex_str, const char* str, uint length,
                     bool allocate_lex_string);

/*
  Used to hold information about file and file structure in exchange
  via non-DB file (...INTO OUTFILE..., ...LOAD DATA...)
  XXX: We never call destructor for objects of this class.
*/

class sql_exchange :public Sql_alloc
{
public:
  enum enum_filetype filetype; /* load XML, Added by Arnold & Erik */
  char *file_name;
  const String *field_term, *enclosed, *line_term, *line_start, *escaped;
  bool opt_enclosed;
  bool dumpfile;
  ulong skip_lines;
  const CHARSET_INFO *cs;
  sql_exchange(char *name, bool dumpfile_flag,
               enum_filetype filetype_arg= FILETYPE_CSV);
  bool escaped_given(void);
};

/*
  This is used to get result from a select
*/

class JOIN;

class select_result :public Sql_alloc {
protected:
  THD *thd;
  SELECT_LEX_UNIT *unit;
public:
  /**
    Number of records estimated in this result.
    Valid only for materialized derived tables/views.
  */
  ha_rows estimated_rowcount;
  select_result();
  virtual ~select_result() {};
  virtual int prepare(List<Item> &list, SELECT_LEX_UNIT *u)
  {
    unit= u;
    return 0;
  }
  virtual int prepare2(void) { return 0; }
  /*
    Because of peculiarities of prepared statements protocol
    we need to know number of columns in the result set (if
    there is a result set) apart from sending columns metadata.
  */
  virtual uint field_count(List<Item> &fields) const
  { return fields.elements; }
  virtual bool initialize_tables (JOIN *join=0) { return 0; }
  virtual void send_error(uint errcode,const char *err);
  /**
    Check if this query returns a result set and therefore is allowed in
    cursors and set an error message if it is not the case.

    @retval FALSE     success
    @retval TRUE      error, an error message is set
  */
  virtual bool check_simple_select() const;
  /*
    Cleanup instance of this class for next execution of a prepared
    statement/stored procedure.
  */
  virtual void cleanup();
  void set_thd(THD *thd_arg) { thd= thd_arg; }

  /**
    If we execute EXPLAIN SELECT ... LIMIT (or any other EXPLAIN query)
    we have to ignore offset value sending EXPLAIN output rows since
    offset value belongs to the underlying query, not to the whole EXPLAIN.
  */
  void reset_offset_limit_cnt() { unit->offset_limit_cnt= 0; }

#ifdef EMBEDDED_LIBRARY
  virtual void begin_dataset() {}
#else
  void begin_dataset() {}
#endif
};


/*
  Base class for select_result descendands which intercept and
  transform result set rows. As the rows are not sent to the client,
  sending of result set metadata should be suppressed as well.
*/

class select_result_interceptor: public select_result
{
public:
  select_result_interceptor() {}              /* Remove gcc warning */
  uint field_count(List<Item> &fields) const { return 0; }
};


class select_send :public select_result {
  /**
    True if we have sent result set metadata to the client.
    In this case the client always expects us to end the result
    set with an eof or error packet
  */
  bool is_result_set_started;
public:
  select_send() :is_result_set_started(FALSE) {}
  virtual bool check_simple_select() const { return FALSE; }
};


class select_to_file :public select_result_interceptor {
protected:
  sql_exchange *exchange;
  File file;
  IO_CACHE cache;
  ha_rows row_count;
  char path[FN_REFLEN];

public:
  select_to_file(sql_exchange *ex) :exchange(ex), file(-1),row_count(0L)
  { path[0]=0; }
  ~select_to_file();
};


#define ESCAPE_CHARS "ntrb0ZN" // keep synchronous with READ_INFO::unescape


/*
 List of all possible characters of a numeric value text representation.
*/
#define NUMERIC_CHARS ".0123456789e+-"


class select_export :public select_to_file {
  uint field_term_length;
  int field_sep_char,escape_char,line_sep_char;
  int field_term_char; // first char of FIELDS TERMINATED BY or MAX_INT
  /*
    The is_ambiguous_field_sep field is true if a value of the field_sep_char
    field is one of the 'n', 't', 'r' etc characters
    (see the READ_INFO::unescape method and the ESCAPE_CHARS constant value).
  */
  bool is_ambiguous_field_sep;
  /*
     The is_ambiguous_field_term is true if field_sep_char contains the first
     char of the FIELDS TERMINATED BY (ENCLOSED BY is empty), and items can
     contain this character.
  */
  bool is_ambiguous_field_term;
  /*
    The is_unsafe_field_sep field is true if a value of the field_sep_char
    field is one of the '0'..'9', '+', '-', '.' and 'e' characters
    (see the NUMERIC_CHARS constant value).
  */
  bool is_unsafe_field_sep;
  bool fixed_row_size;
  const CHARSET_INFO *write_cs; // output charset
public:
  select_export(sql_exchange *ex) :select_to_file(ex) {}
  ~select_export();
};


class select_dump :public select_to_file {
public:
  select_dump(sql_exchange *ex) :select_to_file(ex) {}
};

/**
   @todo This class is declared in sql_class.h, but the members are defined in
   sql_insert.cc. It is very confusing that a class is defined in a file with
   a different name than the file where it is declared.
*/
class select_insert :public select_result_interceptor {
public:
  TABLE_LIST *table_list;
private:
  /**
     The columns of the table to be inserted into, *or* the columns of the
     table from which values are selected. For legacy reasons both are
     allowed.
   */
  List<Item> *fields;
protected:
  /// ha_start_bulk_insert has been called.
  bool bulk_insert_started;
public:
  ulonglong autoinc_value_of_last_inserted_row; // autogenerated or not
  COPY_INFO info;
  COPY_INFO update; ///< the UPDATE part of "info"
  bool insert_into_view;

  /**
     Creates a select_insert for routing a result set to an existing
     table.

     @param table_list_par   The table reference for the destination table.
     @param table_par        The destination table. May be NULL.
     @param target_columns   See details.
     @param target_or_source_columns See details.
     @param update_fields    The columns to be updated in case of duplicate
                             keys. May be NULL.
     @param update_values    The values to be assigned in case of duplicate
                             keys. May be NULL.
     @param duplicate        The policy for handling duplicates.
     @param ignore           How the insert operation is to handle certain
                             errors. See COPY_INFO.

     @todo This constructor takes 8 arguments, 6 of which are used to
     immediately construct a COPY_INFO object. Obviously the constructor
     should take the COPY_INFO object as argument instead. Also, some
     select_insert members initialized here are totally redundant, as they are
     found inside the COPY_INFO.

     The target_columns and target_or_source_columns arguments are set by
     callers as follows:
     @li if CREATE SELECT:
      - target_columns == NULL,
      - target_or_source_columns == expressions listed after SELECT, as in
          CREATE ... SELECT expressions
     @li if INSERT SELECT:
      target_columns
      == target_or_source_columns
      == columns listed between INSERT and SELECT, as in
          INSERT INTO t (columns) SELECT ...

     We set the manage_defaults argument of info's constructor as follows
     ([...] denotes something optional):
     @li If target_columns==NULL, the statement is
@verbatim
     CREATE TABLE a_table [(columns1)] SELECT expressions2
@endverbatim
     so 'info' must manage defaults of columns1.
     @li Otherwise it is:
@verbatim
     INSERT INTO a_table [(columns1)] SELECT ...
@verbatim
     target_columns is columns1, if not empty then 'info' must manage defaults
     of other columns than columns1.
  */
  select_insert(TABLE_LIST *table_list_par,
                List<Item> *target_columns,
                List<Item> *target_or_source_columns,
                List<Item> *update_fields,
                List<Item> *update_values,
                enum_duplicates duplic,
                bool ignore)
    :table_list(table_list_par),
     fields(target_or_source_columns),
     bulk_insert_started(false),
     autoinc_value_of_last_inserted_row(0),
     info(COPY_INFO::INSERT_OPERATION,
          target_columns,
          // manage_defaults
          (target_columns == NULL || target_columns->elements != 0),
          duplic,
          ignore),
     update(COPY_INFO::UPDATE_OPERATION,
            update_fields,
            update_values),
     insert_into_view(table_list_par && table_list_par->view != 0)
  {
    DBUG_ASSERT(target_or_source_columns != NULL);
    DBUG_ASSERT(target_columns == target_or_source_columns ||
                target_columns == NULL);
  }


public:
  ~select_insert();
  int prepare(List<Item> &list, SELECT_LEX_UNIT *u);
  virtual int prepare2(void);
  bool send_data(List<Item> &items);
  virtual void store_values(List<Item> &values);
  void send_error(uint errcode,const char *err);
  bool send_eof();
  virtual void abort_result_set();
  /* not implemented: select_insert is never re-used in prepared statements */
  void cleanup();
};


/**
   @todo This class inherits a class which is non-abstract. This is not in
   line with good programming practices and the inheritance should be broken
   up. Also, the class is declared in sql_class.h, but defined sql_insert.cc
   which is confusing.
*/
class select_create: public select_insert {
  ORDER *group;
  TABLE_LIST *create_table;
  HA_CREATE_INFO *create_info;
  TABLE_LIST *select_tables;
  Alter_info *alter_info;
  /* lock data for tmp table */
  MYSQL_LOCK *m_lock;
  /* m_lock or thd->extra_lock */
  MYSQL_LOCK **m_plock;
public:
  select_create (TABLE_LIST *table_arg,
		 HA_CREATE_INFO *create_info_par,
                 Alter_info *alter_info_arg,
		 List<Item> &select_fields,enum_duplicates duplic, bool ignore,
                 TABLE_LIST *select_tables_arg)
    :select_insert (NULL, // table_list_par
                    NULL, // target_columns
                    &select_fields,
                    NULL, // update_fields
                    NULL, // update_values
                    duplic,
                    ignore),
     create_table(table_arg),
     create_info(create_info_par),
     select_tables(select_tables_arg),
     alter_info(alter_info_arg),
     m_plock(NULL)
  {}
  int prepare(List<Item> &list, SELECT_LEX_UNIT *u);

  void store_values(List<Item> &values);
  void send_error(uint errcode,const char *err);
  bool send_eof();

  // Needed for access from local class MY_HOOKS in prepare(), since thd is proteted.
  const THD *get_thd(void) { return thd; }
  const HA_CREATE_INFO *get_create_info() { return create_info; };
  int prepare2(void);
};


/* Base subselect interface class */
class select_subselect :public select_result_interceptor
{
protected:
  Item_subselect *item;
public:
  select_subselect(Item_subselect *item);
};

/* Single value subselect interface class */
class select_singlerow_subselect :public select_subselect
{
public:
  select_singlerow_subselect(Item_subselect *item_arg)
    :select_subselect(item_arg)
  {}
};

/* used in independent ALL/ANY optimisation */
class select_max_min_finder_subselect :public select_subselect
{
  Item_cache *cache;
  bool (select_max_min_finder_subselect::*op)();
  bool fmax;
  /**
    If ignoring NULLs, comparisons will skip NULL values. If not
    ignoring NULLs, the first (if any) NULL value discovered will be
    returned as the maximum/minimum value.
  */
  bool ignore_nulls;
public:
  select_max_min_finder_subselect(Item_subselect *item_arg, bool mx,
                                  bool ignore_nulls)
    :select_subselect(item_arg), cache(0), fmax(mx), ignore_nulls(ignore_nulls)
  {}
};

/* EXISTS subselect interface class */
class select_exists_subselect :public select_subselect
{
public:
  select_exists_subselect(Item_subselect *item_arg)
    :select_subselect(item_arg){}
};


/* Structs used when sorting */

typedef struct st_sort_field {
  Item	*item;				/* Item if not sorting fields */
  uint	 length;			/* Length of sort field */
  uint   suffix_length;                 /* Length suffix (0-4) */
  Item_result result_type;		/* Type of item */
  bool reverse;				/* if descending sort */
  bool need_strxnfrm;			/* If we have to use strxnfrm() */
} SORT_FIELD;


typedef struct st_sort_buffer {
  uint index;					/* 0 or 1 */
  uint sort_orders;
  uint change_pos;				/* If sort-fields changed */
  char **buff;
  SORT_FIELD *sortorder;
} SORT_BUFFER;

/* Structure for db & table in sql_yacc */

class Table_ident :public Sql_alloc
{
public:
  LEX_STRING db;
  LEX_STRING table;
  SELECT_LEX_UNIT *sel;
  inline Table_ident(THD *thd, LEX_STRING db_arg, LEX_STRING table_arg,
		     bool force)
    :table(table_arg), sel((SELECT_LEX_UNIT *)0)
  {
    if (!force && (thd->client_capabilities & CLIENT_NO_SCHEMA))
      db.str=0;
    else
      db= db_arg;
  }
  inline Table_ident(LEX_STRING table_arg) 
    :table(table_arg), sel((SELECT_LEX_UNIT *)0)
  {
    db.str=0;
  }
  /*
    This constructor is used only for the case when we create a derived
    table. A derived table has no name and doesn't belong to any database.
    Later, if there was an alias specified for the table, it will be set
    by add_table_to_list.
  */
  inline Table_ident(SELECT_LEX_UNIT *s) : sel(s)
  {
    /* We must have a table name here as this is used with add_table_to_list */
    db.str= empty_c_string;                    /* a subject to casedn_str */
    db.length= 0;
    table.str= internal_table_name;
    table.length=1;
  }
  bool is_derived_table() const { return MY_TEST(sel); }
  inline void change_db(char *db_name)
  {
    db.str= db_name; db.length= (uint) strlen(db_name);
  }
};

// this is needed for user_vars hash
class user_var_entry
{
  static const size_t extra_size= sizeof(double);
  char *m_ptr;          // Value
  ulong m_length;       // Value length
  Item_result m_type;   // Value type

  void reset_value()
  { m_ptr= NULL; m_length= 0; }
  void set_value(char *value, ulong length)
  { m_ptr= value; m_length= length; }

  /**
    Position inside a user_var_entry where small values are stored:
    double values, longlong values and string values with length
    up to extra_size (should be 8 bytes on all platforms).
    String values with length longer than 8 are stored in a separate
    memory buffer, which is allocated when needed using the method realloc().
  */
  char *internal_buffer_ptr() const
  { return (char *) this + ALIGN_SIZE(sizeof(user_var_entry)); }

  /**
    Position inside a user_var_entry where a null-terminates array
    of characters representing the variable name is stored.
  */
  char *name_ptr() const
  { return internal_buffer_ptr() + extra_size; }

  /**
    Initialize m_ptr to the internal buffer (if the value is small enough),
    or allocate a separate buffer.
    @param length - length of the value to be stored.
  */
  bool realloc(uint length);

  /**
    Check if m_ptr point to an external buffer previously alloced by realloc().
    @retval true  - an external buffer is alloced.
    @retval false - m_ptr is null, or points to the internal buffer.
  */
  bool alloced()
  { return m_ptr && m_ptr != internal_buffer_ptr(); }

  /**
    Free the external value buffer, if it's allocated.
  */
  void free_value()
  {
    if (alloced())
      my_free(m_ptr);
  }

  /**
    Copy the array of characters from the given name into the internal
    name buffer and initialize entry_name to point to it.
  */
  void copy_name(const Simple_cstring &name)
  {
    name.strcpy(name_ptr());
    entry_name= Name_string(name_ptr(), name.length());
  }

  /**
    Initialize all members
    @param name - Name of the user_var_entry instance.
  */
  void init(const Simple_cstring &name)
  {
    copy_name(name);
    reset_value();
    update_query_id= 0;
    collation.set(NULL, DERIVATION_IMPLICIT, 0);
    unsigned_flag= 0;
    /*
      If we are here, we were called from a SET or a query which sets a
      variable. Imagine it is this:
      INSERT INTO t SELECT @a:=10, @a:=@a+1.
      Then when we have a Item_func_get_user_var (because of the @a+1) so we
      think we have to write the value of @a to the binlog. But before that,
      we have a Item_func_set_user_var to create @a (@a:=10), in this we mark
      the variable as "already logged" (line below) so that it won't be logged
      by Item_func_get_user_var (because that's not necessary).
    */
    used_query_id= current_thd->query_id;
    set_type(STRING_RESULT);
  }

  /**
    Store a value of the given type into a user_var_entry instance.
    @param from    Value
    @param length  Size of the value
    @param type    type
    @return
    @retval        false on success
    @retval        true on memory allocation error
  */
  bool store(void *from, uint length, Item_result type);

public:
  user_var_entry() {}                         /* Remove gcc warning */

  Simple_cstring entry_name;  // Variable name
  DTCollation collation;      // Collation with attributes
  query_id_t update_query_id, used_query_id;
  bool unsigned_flag;         // true if unsigned, false if signed

  /**
    Store a value of the given type and attributes (collation, sign)
    into a user_var_entry instance.
    @param from         Value
    @param length       Size of the value
    @param type         type
    @param cs           Character set and collation of the value
    @param dv           Collationd erivation of the value
    @param unsigned_arg Signess of the value
    @return
    @retval        false on success
    @retval        true on memory allocation error
  */
  bool store(void *from, uint length, Item_result type,
             const CHARSET_INFO *cs, Derivation dv, bool unsigned_arg);
  /**
    Set type of to the given value.
    @param type  Data type.
  */
  void set_type(Item_result type) { m_type= type; }
  /**
    Set value to NULL
    @param type  Data type.
  */

  void set_null_value(Item_result type)
  {
    free_value();
    reset_value();
    set_type(type);
  }

  /**
    Allocate and initialize a user variable instance.
    @param namec  Name of the variable.
    @return
    @retval  Address of the allocated and initialized user_var_entry instance.
    @retval  NULL on allocation error.
  */
  static user_var_entry *create(const Name_string &name)
  {
    user_var_entry *entry;
    uint size= ALIGN_SIZE(sizeof(user_var_entry)) +
               (name.length() + 1) + extra_size;
    if (!(entry= (user_var_entry*) my_malloc(size, MYF(MY_WME |
                                                       ME_FATALERROR))))
      return NULL;
    entry->init(name);
    return entry;
  }

  /**
    Free all memory used by a user_var_entry instance
    previously created by create().
  */
  void destroy()
  {
    free_value();  // Free the external value buffer
    my_free(this); // Free the instance itself
  }

  /* Routines to access the value and its type */
  const char *ptr() const { return m_ptr; }
  ulong length() const { return m_length; }
  Item_result type() const { return m_type; }
  /* Item-alike routines to access the value */
  double val_real(my_bool *null_value);
  longlong val_int(my_bool *null_value) const;
  String *val_str(my_bool *null_value, String *str, uint decimals);
  my_decimal *val_decimal(my_bool *null_value, my_decimal *result);
};


class multi_delete :public select_result_interceptor
{
  TABLE_LIST *delete_tables, *table_being_deleted;
  ha_rows deleted, found;
  uint num_of_tables;
  int error;
  bool do_delete;
  /* True if at least one table we delete from is transactional */
  bool transactional_tables;
  /* True if at least one table we delete from is not transactional */
  bool normal_tables;
  bool delete_while_scanning;
  /*
     error handling (rollback and binlogging) can happen in send_eof()
     so that afterward send_error() needs to find out that.
  */
  bool error_handled;

public:
  multi_delete(TABLE_LIST *dt, uint num_of_tables);
  ~multi_delete();
  int prepare(List<Item> &list, SELECT_LEX_UNIT *u);
  bool send_data(List<Item> &items);
  bool initialize_tables (JOIN *join);
  void send_error(uint errcode,const char *err);
  int do_deletes();
  bool send_eof();
  inline ha_rows num_deleted()
  {
    return deleted;
  }
  virtual void abort_result_set();
};


/**
   @todo This class is declared here but implemented in sql_update.cc, which
   is very confusing.
*/
class multi_update :public select_result_interceptor
{
  TABLE_LIST *all_tables; /* query/update command tables */
  TABLE_LIST *leaves;     /* list of leves of join table tree */
  TABLE_LIST *update_tables, *table_being_updated;
  ha_rows updated, found;
  List <Item> *fields, *values;
  List <Item> **fields_for_table, **values_for_table;
  uint table_count;
  enum enum_duplicates handle_duplicates;
  bool do_update, trans_safe;
  /* True if the update operation has made a change in a transactional table */
  bool transactional_tables;
  bool ignore;
  /* 
     error handling (rollback and binlogging) can happen in send_eof()
     so that afterward send_error() needs to find out that.
  */
  bool error_handled;

  /**
     Array of update operations, arranged per _updated_ table. For each
     _updated_ table in the multiple table update statement, a COPY_INFO
     pointer is present at the table's position in this array.

     The array is allocated and populated during multi_update::prepare(). The
     position that each table is assigned is also given here and is stored in
     the member TABLE::pos_in_table_list::shared. However, this is a publicly
     available field, so nothing can be trusted about its integrity.

     This member is NULL when the multi_update is created.

     @see multi_update::prepare
  */
  COPY_INFO **update_operations;

public:
  multi_update(TABLE_LIST *ut, TABLE_LIST *leaves_list,
	       List<Item> *fields, List<Item> *values,
	       enum_duplicates handle_duplicates, bool ignore);
  ~multi_update();
  int prepare(List<Item> &list, SELECT_LEX_UNIT *u);
  bool send_data(List<Item> &items);
  bool initialize_tables (JOIN *join);
  void send_error(uint errcode,const char *err);
  int  do_updates();
  bool send_eof();
  inline ha_rows num_found()
  {
    return found;
  }
  inline ha_rows num_updated()
  {
    return updated;
  }
};

class my_var : public Sql_alloc  {
public:
  LEX_STRING s;
#ifndef DBUG_OFF
  /*
    Routine to which this Item_splocal belongs. Used for checking if correct
    runtime context is used for variable handling.
  */
  sp_head *sp;
#endif
  bool local;
  uint offset;
  enum_field_types type;
  my_var (LEX_STRING& j, bool i, uint o, enum_field_types t)
    :s(j), local(i), offset(o), type(t)
  {}
  ~my_var() {}
};

class select_dumpvar :public select_result_interceptor {
  ha_rows row_count;
  Item_func_set_user_var **set_var_items;
public:
  List<my_var> var_list;
  select_dumpvar()  { var_list.empty(); row_count= 0;}
  ~select_dumpvar() {}
};

/* Bits in sql_command_flags */

#define CF_CHANGES_DATA           (1U << 0)
/* The 2nd bit is unused -- it used to be CF_HAS_ROW_COUNT. */
#define CF_STATUS_COMMAND         (1U << 2)
#define CF_SHOW_TABLE_COMMAND     (1U << 3)
#define CF_WRITE_LOGS_COMMAND     (1U << 4)
/**
  Must be set for SQL statements that may contain
  Item expressions and/or use joins and tables.
  Indicates that the parse tree of such statement may
  contain rule-based optimizations that depend on metadata
  (i.e. number of columns in a table), and consequently
  that the statement must be re-prepared whenever
  referenced metadata changes. Must not be set for
  statements that themselves change metadata, e.g. RENAME,
  ALTER and other DDL, since otherwise will trigger constant
  reprepare. Consequently, complex item expressions and
  joins are currently prohibited in these statements.
*/
#define CF_REEXECUTION_FRAGILE    (1U << 5)
/**
  Implicitly commit before the SQL statement is executed.

  Statements marked with this flag will cause any active
  transaction to end (commit) before proceeding with the
  command execution.

  This flag should be set for statements that probably can't
  be rolled back or that do not expect any previously metadata
  locked tables.
*/
#define CF_IMPLICIT_COMMIT_BEGIN  (1U << 6)
/**
  Implicitly commit after the SQL statement.

  Statements marked with this flag are automatically committed
  at the end of the statement.

  This flag should be set for statements that will implicitly
  open and take metadata locks on system tables that should not
  be carried for the whole duration of a active transaction.
*/
#define CF_IMPLICIT_COMMIT_END    (1U << 7)
/**
  CF_IMPLICIT_COMMIT_BEGIN and CF_IMPLICIT_COMMIT_END are used
  to ensure that the active transaction is implicitly committed
  before and after every DDL statement and any statement that
  modifies our currently non-transactional system tables.
*/
#define CF_AUTO_COMMIT_TRANS  (CF_IMPLICIT_COMMIT_BEGIN | CF_IMPLICIT_COMMIT_END)

/**
  Diagnostic statement.
  Diagnostic statements:
  - SHOW WARNING
  - SHOW ERROR
  - GET DIAGNOSTICS (WL#2111)
  do not modify the diagnostics area during execution.
*/
#define CF_DIAGNOSTIC_STMT        (1U << 8)

/**
  Identifies statements that may generate row events
  and that may end up in the binary log.
*/
#define CF_CAN_GENERATE_ROW_EVENTS (1U << 9)

/**
  Identifies statements which may deal with temporary tables and for which
  temporary tables should be pre-opened to simplify privilege checks.
*/
#define CF_PREOPEN_TMP_TABLES   (1U << 10)

/**
  Identifies statements for which open handlers should be closed in the
  beginning of the statement.
*/
#define CF_HA_CLOSE             (1U << 11)

/**
  Identifies statements that can be explained with EXPLAIN.
*/
#define CF_CAN_BE_EXPLAINED       (1U << 12)

/** Identifies statements which may generate an optimizer trace */
#define CF_OPTIMIZER_TRACE        (1U << 14)

/**
   Identifies statements that should always be disallowed in
   read only transactions.
*/
#define CF_DISALLOW_IN_RO_TRANS   (1U << 15)

/* Bits in server_command_flags */

/**
  Skip the increase of the global query id counter. Commonly set for
  commands that are stateless (won't cause any change on the server
  internal states). This is made obsolete as query id is incremented 
  for ping and statistics commands as well because of race condition 
  (Bug#58785).
*/
#define CF_SKIP_QUERY_ID        (1U << 0)

/**
  Skip the increase of the number of statements that clients have
  sent to the server. Commonly used for commands that will cause
  a statement to be executed but the statement might have not been
  sent by the user (ie: stored procedure).
*/
#define CF_SKIP_QUESTIONS       (1U << 1)

void mark_transaction_to_rollback(THD *thd, bool all);

/* Inline functions */

inline bool add_item_to_list(THD *thd, Item *item)
{
  return thd->lex->current_select->add_item_to_list(thd, item);
}

inline bool add_value_to_list(THD *thd, Item *value)
{
  return thd->lex->value_list.push_back(value);
}

inline bool add_order_to_list(THD *thd, Item *item, bool asc)
{
  return thd->lex->current_select->add_order_to_list(thd, item, asc);
}

inline bool add_gorder_to_list(THD *thd, Item *item, bool asc)
{
  return thd->lex->current_select->add_gorder_to_list(thd, item, asc);
}

inline bool add_group_to_list(THD *thd, Item *item, bool asc)
{
  return thd->lex->current_select->add_group_to_list(thd, item, asc);
}

#define MAX_USER_HOST_SIZE 512
static inline uint make_user_name(THD *thd, char *buf)
{
  Security_context *sctx= thd->security_ctx;
  return strxnmov(buf, MAX_USER_HOST_SIZE,
                  sctx->priv_user[0] ? sctx->priv_user : "", "[",
                  sctx->user ? sctx->user : "", "] @ ",
                  sctx->get_host()->length() ? sctx->get_host()->ptr() :
                  "", " [", sctx->get_ip()->length() ? sctx->get_ip()->ptr() :
                            "", "]", NullS) - buf;
}


extern pthread_attr_t *get_connection_attrib(void);

#endif /* MYSQL_SERVER */

#endif /* SQL_CLASS_INCLUDED */
