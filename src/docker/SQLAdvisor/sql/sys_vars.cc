/* Copyright (c) 2009, 2014, Oracle and/or its affiliates. All rights reserved.

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

/**
  @file
  Definitions of all server's session or global variables.

  How to add new variables:

  1. copy one of the existing variables, and edit the declaration.
  2. if you need special behavior on assignment or additional checks
     use ON_CHECK and ON_UPDATE callbacks.
  3. *Don't* add new Sys_var classes or uncle Occam will come
     with his razor to haunt you at nights

  Note - all storage engine variables (for example myisam_whatever)
  should go into the corresponding storage engine sources
  (for example in storage/myisam/ha_myisam.cc) !
*/

#include "my_global.h"                          /* NO_EMBEDDED_ACCESS_CHECKS */
#include "sql_priv.h"
#include "sql_class.h"                          // set_var.h: THD
#include "sys_vars.h"
#include "mysql_com.h"

#include <thr_alarm.h>
#include "mysqld.h"
#include "sql_time.h"                       // known_date_time_formats
#include "sql_acl.h" // SUPER_ACL,
                     // mysql_user_table_is_in_short_password_format
                     // disconnect_on_expired_password
#include "derror.h"  // read_texts
#include "sql_base.h"                           // close_cached_tables
#include "sql_show.h"                           // opt_ignore_db_dirs
#include "my_aes.h" // my_aes_opmode_names

#ifdef WITH_PERFSCHEMA_STORAGE_ENGINE
#include "../storage/perfschema/pfs_server.h"
#endif /* WITH_PERFSCHEMA_STORAGE_ENGINE */

TYPELIB bool_typelib={ array_elements(bool_values)-1, "", bool_values, 0 };

#define MAX_CONNECTIONS 100000

/*
  This forward declaration is needed because including sql_base.h
  causes further includes.  [TODO] Eliminate this forward declaration
  and include a file with the prototype instead.
*/
extern void close_thread_tables(THD *thd);

/*
  The rule for this file: everything should be 'static'. When a sys_var
  variable or a function from this file is - in very rare cases - needed
  elsewhere it should be explicitly declared 'export' here to show that it's
  not a mistakenly forgotten 'static' keyword.
*/
#define export /* not static */


static Sys_var_charptr Sys_basedir(
       "basedir", "Path to installation directory. All paths are "
       "usually resolved relative to this",
       READ_ONLY GLOBAL_VAR(mysql_home_ptr), CMD_LINE(REQUIRED_ARG, 'b'),
       IN_FS_CHARSET, DEFAULT(0));

static Sys_var_charptr Sys_my_bind_addr(
       "bind_address", "IP address to bind to.",
       READ_ONLY GLOBAL_VAR(my_bind_addr_str), CMD_LINE(REQUIRED_ARG),
       IN_FS_CHARSET, DEFAULT(MY_BIND_ALL_ADDRESSES));

static bool check_has_super(sys_var *self, THD *thd, set_var *var)
{
  DBUG_ASSERT(self->scope() != sys_var::GLOBAL);// don't abuse check_has_super()
#ifndef NO_EMBEDDED_ACCESS_CHECKS
  if (!(thd->security_ctx->master_access & SUPER_ACL))
  {
    my_error(ER_SPECIFIC_ACCESS_DENIED_ERROR, MYF(0), "SUPER");
    return true;
  }
#endif
  return false;
}

static Sys_var_test_flag Sys_core_file(
       "core_file", "write a core-file on crashes", TEST_CORE_ON_SIGNAL);

static Sys_var_ulong Sys_bulk_insert_buff_size(
       "bulk_insert_buffer_size", "Size of tree cache used in bulk "
       "insert optimisation. Note that this is a limit per thread!",
       SESSION_VAR(bulk_insert_buff_size), CMD_LINE(REQUIRED_ARG),
       VALID_RANGE(0, ULONG_MAX), DEFAULT(8192*1024), BLOCK_SIZE(1));

static Sys_var_charptr Sys_character_sets_dir(
       "character_sets_dir", "Directory where character sets are",
       READ_ONLY GLOBAL_VAR(charsets_dir), CMD_LINE(REQUIRED_ARG),
       IN_FS_CHARSET, DEFAULT(0));

static bool check_not_null(sys_var *self, THD *thd, set_var *var)
{
  return var->value && var->value->is_null();
}
static bool check_charset(sys_var *self, THD *thd, set_var *var)
{
  if (!var->value)
    return false;

  char buff[STRING_BUFFER_USUAL_SIZE];
  if (var->value->result_type() == STRING_RESULT)
  {
    String str(buff, sizeof(buff), system_charset_info), *res;
    if (!(res= var->value->val_str(&str)))
      var->save_result.ptr= NULL;
    else
    {
      ErrConvString err(res); /* Get utf8 '\0' terminated string */
      if (!(var->save_result.ptr= get_charset_by_csname(err.ptr(),
                                                         MY_CS_PRIMARY,
                                                         MYF(0))) &&
          !(var->save_result.ptr= get_old_charset_by_name(err.ptr())))
      {
        my_error(ER_UNKNOWN_CHARACTER_SET, MYF(0), err.ptr());
        return true;
      }
    }
  }
  else // INT_RESULT
  {
    int csno= (int)var->value->val_int();
    if (!(var->save_result.ptr= get_charset(csno, MYF(0))))
    {
      my_error(ER_UNKNOWN_CHARACTER_SET, MYF(0), llstr(csno, buff));
      return true;
    }
  }
  return false;
}
static bool check_charset_not_null(sys_var *self, THD *thd, set_var *var)
{
  return check_charset(self, thd, var) || check_not_null(self, thd, var);
}
static Sys_var_struct Sys_character_set_system(
       "character_set_system", "The character set used by the server "
       "for storing identifiers",
       READ_ONLY GLOBAL_VAR(system_charset_info), NO_CMD_LINE,
       offsetof(CHARSET_INFO, csname), DEFAULT(0));

static Sys_var_struct Sys_character_set_server(
       "character_set_server", "The default character set",
       SESSION_VAR(collation_server), NO_CMD_LINE,
       offsetof(CHARSET_INFO, csname), DEFAULT(&default_charset_info),
       NO_MUTEX_GUARD, IN_BINLOG, ON_CHECK(check_charset_not_null));

static bool check_charset_db(sys_var *self, THD *thd, set_var *var)
{
  if (check_charset_not_null(self, thd, var))
    return true;
  if (!var->value) // = DEFAULT
    var->save_result.ptr= thd->db_charset;
  return false;
}
static Sys_var_struct Sys_character_set_database(
       "character_set_database",
       " The character set used by the default database",
       SESSION_VAR(collation_database), NO_CMD_LINE,
       offsetof(CHARSET_INFO, csname), DEFAULT(&default_charset_info),
       NO_MUTEX_GUARD, IN_BINLOG, ON_CHECK(check_charset_db));

static bool check_cs_client(sys_var *self, THD *thd, set_var *var)
{
  if (check_charset_not_null(self, thd, var))
    return true;

  // Currently, UCS-2 cannot be used as a client character set
  if (((CHARSET_INFO *)(var->save_result.ptr))->mbminlen > 1)
    return true;

  return false;
}
static bool fix_thd_charset(sys_var *self, THD *thd, enum_var_type type)
{
  if (type == OPT_SESSION)
    thd->update_charset();
  return false;
}
static Sys_var_struct Sys_character_set_client(
       "character_set_client", "The character set for statements "
       "that arrive from the client",
       SESSION_VAR(character_set_client), NO_CMD_LINE,
       offsetof(CHARSET_INFO, csname), DEFAULT(&default_charset_info),
       NO_MUTEX_GUARD, IN_BINLOG, ON_CHECK(check_cs_client),
       ON_UPDATE(fix_thd_charset));

static Sys_var_struct Sys_character_set_connection(
       "character_set_connection", "The character set used for "
       "literals that do not have a character set introducer and for "
       "number-to-string conversion",
       SESSION_VAR(collation_connection), NO_CMD_LINE,
       offsetof(CHARSET_INFO, csname), DEFAULT(&default_charset_info),
       NO_MUTEX_GUARD, IN_BINLOG, ON_CHECK(check_charset_not_null),
       ON_UPDATE(fix_thd_charset));

static Sys_var_struct Sys_character_set_results(
       "character_set_results", "The character set used for returning "
       "query results to the client",
       SESSION_VAR(character_set_results), NO_CMD_LINE,
       offsetof(CHARSET_INFO, csname), DEFAULT(&default_charset_info),
       NO_MUTEX_GUARD, NOT_IN_BINLOG, ON_CHECK(check_charset));

static Sys_var_struct Sys_character_set_filesystem(
       "character_set_filesystem", "The filesystem character set",
       SESSION_VAR(character_set_filesystem), NO_CMD_LINE,
       offsetof(CHARSET_INFO, csname), DEFAULT(&character_set_filesystem),
       NO_MUTEX_GUARD, NOT_IN_BINLOG, ON_CHECK(check_charset_not_null),
       ON_UPDATE(fix_thd_charset));

static const char *completion_type_names[]= {"NO_CHAIN", "CHAIN", "RELEASE", 0};
static Sys_var_enum Sys_completion_type(
       "completion_type", "The transaction completion type, one of "
       "NO_CHAIN, CHAIN, RELEASE",
       SESSION_VAR(completion_type), CMD_LINE(REQUIRED_ARG),
       completion_type_names, DEFAULT(0));

static bool check_collation_not_null(sys_var *self, THD *thd, set_var *var)
{
  if (!var->value)
    return false;

  char buff[STRING_BUFFER_USUAL_SIZE];
  if (var->value->result_type() == STRING_RESULT)
  {
    String str(buff, sizeof(buff), system_charset_info), *res;
    if (!(res= var->value->val_str(&str)))
      var->save_result.ptr= NULL;
    else
    {
      ErrConvString err(res); /* Get utf8 '\0'-terminated string */
      if (!(var->save_result.ptr= get_charset_by_name(err.ptr(), MYF(0))))
      {
        my_error(ER_UNKNOWN_COLLATION, MYF(0), err.ptr());
        return true;
      }
    }
  }
  else // INT_RESULT
  {
    int csno= (int)var->value->val_int();
    if (!(var->save_result.ptr= get_charset(csno, MYF(0))))
    {
      my_error(ER_UNKNOWN_COLLATION, MYF(0), llstr(csno, buff));
      return true;
    }
  }
  return check_not_null(self, thd, var);
}
static Sys_var_struct Sys_collation_connection(
       "collation_connection", "The collation of the connection "
       "character set",
       SESSION_VAR(collation_connection), NO_CMD_LINE,
       offsetof(CHARSET_INFO, name), DEFAULT(&default_charset_info),
       NO_MUTEX_GUARD, IN_BINLOG, ON_CHECK(check_collation_not_null),
       ON_UPDATE(fix_thd_charset));

static bool check_collation_db(sys_var *self, THD *thd, set_var *var)
{
  if (check_collation_not_null(self, thd, var))
    return true;
  if (!var->value) // = DEFAULT
    var->save_result.ptr= thd->db_charset;
  return false;
}
static Sys_var_struct Sys_collation_database(
       "collation_database", "The collation of the database "
       "character set",
       SESSION_VAR(collation_database), NO_CMD_LINE,
       offsetof(CHARSET_INFO, name), DEFAULT(&default_charset_info),
       NO_MUTEX_GUARD, IN_BINLOG, ON_CHECK(check_collation_db));

static Sys_var_struct Sys_collation_server(
       "collation_server", "The server default collation",
       SESSION_VAR(collation_server), NO_CMD_LINE,
       offsetof(CHARSET_INFO, name), DEFAULT(&default_charset_info),
       NO_MUTEX_GUARD, IN_BINLOG, ON_CHECK(check_collation_not_null));

#ifndef DBUG_OFF
static Sys_var_dbug Sys_dbug(
       "debug", "Debug log", sys_var::SESSION,
       CMD_LINE(OPT_ARG, '#'), DEFAULT(""), NO_MUTEX_GUARD, NOT_IN_BINLOG,
       ON_CHECK(check_has_super));
#endif

static Sys_var_charptr Sys_language(
       "lc_messages_dir", "Directory where error messages are",
       READ_ONLY GLOBAL_VAR(lc_messages_dir_ptr), 
       CMD_LINE(REQUIRED_ARG, OPT_LC_MESSAGES_DIRECTORY),
       IN_FS_CHARSET, DEFAULT(0));

static Sys_var_ulong Sys_log_warnings(
       "log_warnings",
       "Log some not critical warnings to the log file",
       GLOBAL_VAR(log_warnings),
       CMD_LINE(OPT_ARG, 'W'),
       VALID_RANGE(0, ULONG_MAX), DEFAULT(1), BLOCK_SIZE(1));

static Sys_var_mybool Sys_lower_case_file_system(
       "lower_case_file_system",
       "Case sensitivity of file names on the file system where the "
       "data directory is located",
       READ_ONLY GLOBAL_VAR(lower_case_file_system), NO_CMD_LINE,
       DEFAULT(FALSE));

static Sys_var_uint Sys_lower_case_table_names(
       "lower_case_table_names",
       "If set to 1 table names are stored in lowercase on disk and table "
       "names will be case-insensitive.  Should be set to 2 if you are using "
       "a case insensitive file system",
       READ_ONLY GLOBAL_VAR(lower_case_table_names),
       CMD_LINE(OPT_ARG, OPT_LOWER_CASE_TABLE_NAMES),
       VALID_RANGE(0, 2),
#ifdef FN_NO_CASE_SENSE
    DEFAULT(1),
#else
    DEFAULT(0),
#endif
       BLOCK_SIZE(1));


static Sys_var_mybool Sys_new_mode(
       "new", "Use very new possible \"unsafe\" functions",
       SESSION_VAR(new_mode), CMD_LINE(OPT_ARG, 'n'), DEFAULT(FALSE));

static Sys_var_mybool Sys_old_mode(
       "old", "Use compatible behavior",
       READ_ONLY GLOBAL_VAR(old_mode), CMD_LINE(OPT_ARG), DEFAULT(FALSE));

static Sys_var_uint Sys_old_passwords(
       "old_passwords",
       "Determine which hash algorithm to use when generating passwords using "
       "the PASSWORD() function",
       SESSION_VAR(old_passwords), CMD_LINE(REQUIRED_ARG),
       VALID_RANGE(0, 2), DEFAULT(0), BLOCK_SIZE(1));

static const char *log_warnings_suppress_name[]= { "1592", NullS };
static Sys_var_set Sys_log_warnings_suppress(
       "log_warnings_suppress",
       "disable logging of enumerated warnings: "
       "1592: unsafe statements for binary logging; "
       "possible values : [1592]",
       GLOBAL_VAR(opt_log_warnings_suppress), CMD_LINE(REQUIRED_ARG),
       log_warnings_suppress_name, DEFAULT(0));


static Sys_var_external_user Sys_external_user(
       "external_user", "The external user account used when logging in",
       IN_SYSTEM_CHARSET);



static bool fix_thd_mem_root(sys_var *self, THD *thd, enum_var_type type)
{
  if (type != OPT_GLOBAL)
    reset_root_defaults(thd->mem_root,
                        thd->variables.query_alloc_block_size,
                        thd->variables.query_prealloc_size);
  return false;
}
static Sys_var_ulong Sys_query_alloc_block_size(
       "query_alloc_block_size",
       "Allocation block size for query parsing and execution",
       SESSION_VAR(query_alloc_block_size), CMD_LINE(REQUIRED_ARG),
       VALID_RANGE(1024, ULONG_MAX), DEFAULT(QUERY_ALLOC_BLOCK_SIZE),
       BLOCK_SIZE(1024), NO_MUTEX_GUARD, NOT_IN_BINLOG, ON_CHECK(0),
       ON_UPDATE(fix_thd_mem_root));

static Sys_var_ulong Sys_query_prealloc_size(
       "query_prealloc_size",
       "Persistent buffer for query parsing and execution",
       SESSION_VAR(query_prealloc_size), CMD_LINE(REQUIRED_ARG),
       VALID_RANGE(QUERY_ALLOC_PREALLOC_SIZE, ULONG_MAX),
       DEFAULT(QUERY_ALLOC_PREALLOC_SIZE),
       BLOCK_SIZE(1024), NO_MUTEX_GUARD, NOT_IN_BINLOG, ON_CHECK(0),
       ON_UPDATE(fix_thd_mem_root));

#ifdef HAVE_SMEM
static Sys_var_mybool Sys_shared_memory(
       "shared_memory", "Enable the shared memory",
       READ_ONLY GLOBAL_VAR(opt_enable_shared_memory), CMD_LINE(OPT_ARG),
       DEFAULT(FALSE));

static Sys_var_charptr Sys_shared_memory_base_name(
       "shared_memory_base_name", "Base name of shared memory",
       READ_ONLY GLOBAL_VAR(shared_memory_base_name), CMD_LINE(REQUIRED_ARG),
       IN_FS_CHARSET, DEFAULT(0));
#endif

static Sys_var_mybool Sys_skip_name_resolve(
       "skip_name_resolve",
       "Don't resolve hostnames. All hostnames are IP's or 'localhost'.",
       READ_ONLY GLOBAL_VAR(opt_skip_name_resolve),
       CMD_LINE(OPT_ARG, OPT_SKIP_RESOLVE),
       DEFAULT(FALSE));

static Sys_var_mybool Sys_skip_show_database(
       "skip_show_database", "Don't allow 'SHOW DATABASE' commands",
       READ_ONLY GLOBAL_VAR(opt_skip_show_db), CMD_LINE(OPT_ARG),
       DEFAULT(FALSE));

static Sys_var_charptr Sys_socket(
       "socket", "Socket file to use for connection",
       READ_ONLY GLOBAL_VAR(mysqld_unix_port), CMD_LINE(REQUIRED_ARG),
       IN_FS_CHARSET, DEFAULT(0));


static Sys_var_ulong Sys_thread_stack(
       "thread_stack", "The stack size for each thread",
       READ_ONLY GLOBAL_VAR(my_thread_stack_size), CMD_LINE(REQUIRED_ARG),
       VALID_RANGE(128*1024, ULONG_MAX), DEFAULT(DEFAULT_THREAD_STACK),
       BLOCK_SIZE(1024));

static Sys_var_charptr Sys_tmpdir(
       "tmpdir", "Path for temporary files. Several paths may "
       "be specified, separated by a "
#if defined(__WIN__)
       "semicolon (;)"
#else
       "colon (:)"
#endif
       ", in this case they are used in a round-robin fashion",
       READ_ONLY GLOBAL_VAR(opt_mysql_tmpdir), CMD_LINE(REQUIRED_ARG, 't'),
       IN_FS_CHARSET, DEFAULT(0));


void sql_mode_deprecation_warnings(sql_mode_t sql_mode)
{
  /**
    If sql_mode is set throught the client, the deprecation warning should
    go to the client connection. If it is used as server startup option,
    it will go the error-log if the deprecated sql_modes are used.
  */
  THD *thd= current_thd;
  if (sql_mode & MODE_ERROR_FOR_DIVISION_BY_ZERO)
    WARN_DEPRECATED_NO_REPLACEMENT(thd, "ERROR_FOR_DIVISION_BY_ZERO");

  if (sql_mode & MODE_NO_ZERO_DATE)
    WARN_DEPRECATED_NO_REPLACEMENT(thd, "NO_ZERO_DATE");

  if (sql_mode & MODE_NO_ZERO_IN_DATE)
    WARN_DEPRECATED_NO_REPLACEMENT(thd, "NO_ZERO_IN_DATE");
}

export sql_mode_t expand_sql_mode(sql_mode_t sql_mode)
{
  sql_mode_deprecation_warnings(sql_mode);
  if (sql_mode & MODE_ANSI)
  {
    /*
      Note that we dont set
      MODE_NO_KEY_OPTIONS | MODE_NO_TABLE_OPTIONS | MODE_NO_FIELD_OPTIONS
      to allow one to get full use of MySQL in this mode.

      MODE_ONLY_FULL_GROUP_BY was removed from ANSI mode because it is
      currently overly restrictive (see BUG#8510).
    */
    sql_mode|= (MODE_REAL_AS_FLOAT | MODE_PIPES_AS_CONCAT | MODE_ANSI_QUOTES |
                MODE_IGNORE_SPACE);
  }
  if (sql_mode & MODE_ORACLE)
    sql_mode|= (MODE_PIPES_AS_CONCAT | MODE_ANSI_QUOTES |
                MODE_IGNORE_SPACE |
                MODE_NO_KEY_OPTIONS | MODE_NO_TABLE_OPTIONS |
                MODE_NO_FIELD_OPTIONS | MODE_NO_AUTO_CREATE_USER);
  if (sql_mode & MODE_MSSQL)
    sql_mode|= (MODE_PIPES_AS_CONCAT | MODE_ANSI_QUOTES |
                MODE_IGNORE_SPACE |
                MODE_NO_KEY_OPTIONS | MODE_NO_TABLE_OPTIONS |
                MODE_NO_FIELD_OPTIONS);
  if (sql_mode & MODE_POSTGRESQL)
    sql_mode|= (MODE_PIPES_AS_CONCAT | MODE_ANSI_QUOTES |
                MODE_IGNORE_SPACE |
                MODE_NO_KEY_OPTIONS | MODE_NO_TABLE_OPTIONS |
                MODE_NO_FIELD_OPTIONS);
  if (sql_mode & MODE_DB2)
    sql_mode|= (MODE_PIPES_AS_CONCAT | MODE_ANSI_QUOTES |
                MODE_IGNORE_SPACE |
                MODE_NO_KEY_OPTIONS | MODE_NO_TABLE_OPTIONS |
                MODE_NO_FIELD_OPTIONS);
  if (sql_mode & MODE_MAXDB)
    sql_mode|= (MODE_PIPES_AS_CONCAT | MODE_ANSI_QUOTES |
                MODE_IGNORE_SPACE |
                MODE_NO_KEY_OPTIONS | MODE_NO_TABLE_OPTIONS |
                MODE_NO_FIELD_OPTIONS | MODE_NO_AUTO_CREATE_USER);
  if (sql_mode & MODE_MYSQL40)
    sql_mode|= MODE_HIGH_NOT_PRECEDENCE;
  if (sql_mode & MODE_MYSQL323)
    sql_mode|= MODE_HIGH_NOT_PRECEDENCE;
  if (sql_mode & MODE_TRADITIONAL)
    sql_mode|= (MODE_STRICT_TRANS_TABLES | MODE_STRICT_ALL_TABLES |
                MODE_NO_ZERO_IN_DATE | MODE_NO_ZERO_DATE |
                MODE_ERROR_FOR_DIVISION_BY_ZERO | MODE_NO_AUTO_CREATE_USER |
                MODE_NO_ENGINE_SUBSTITUTION);
  return sql_mode;
}
static bool check_sql_mode(sys_var *self, THD *thd, set_var *var)
{
  var->save_result.ulonglong_value=
    expand_sql_mode(var->save_result.ulonglong_value);
  return false;
}
static bool fix_sql_mode(sys_var *self, THD *thd, enum_var_type type)
{
  if (type != OPT_GLOBAL)
  {
    /* Update thd->server_status */
    if (thd->variables.sql_mode & MODE_NO_BACKSLASH_ESCAPES)
      thd->server_status|= SERVER_STATUS_NO_BACKSLASH_ESCAPES;
    else
      thd->server_status&= ~SERVER_STATUS_NO_BACKSLASH_ESCAPES;
  }
  return false;
}
/*
  WARNING: When adding new SQL modes don't forget to update the
  tables definitions that stores it's value (ie: mysql.event, mysql.proc)
*/
static const char *sql_mode_names[]=
{
  "REAL_AS_FLOAT", "PIPES_AS_CONCAT", "ANSI_QUOTES", "IGNORE_SPACE", ",",
  "ONLY_FULL_GROUP_BY", "NO_UNSIGNED_SUBTRACTION", "NO_DIR_IN_CREATE",
  "POSTGRESQL", "ORACLE", "MSSQL", "DB2", "MAXDB", "NO_KEY_OPTIONS",
  "NO_TABLE_OPTIONS", "NO_FIELD_OPTIONS", "MYSQL323", "MYSQL40", "ANSI",
  "NO_AUTO_VALUE_ON_ZERO", "NO_BACKSLASH_ESCAPES", "STRICT_TRANS_TABLES",
  "STRICT_ALL_TABLES", "NO_ZERO_IN_DATE", "NO_ZERO_DATE",
  "ALLOW_INVALID_DATES", "ERROR_FOR_DIVISION_BY_ZERO", "TRADITIONAL",
  "NO_AUTO_CREATE_USER", "HIGH_NOT_PRECEDENCE", "NO_ENGINE_SUBSTITUTION",
  "PAD_CHAR_TO_FULL_LENGTH",
  0
};
export bool sql_mode_string_representation(THD *thd, sql_mode_t sql_mode,
                                           LEX_STRING *ls)
{
  set_to_string(thd, ls, sql_mode, sql_mode_names);
  return ls->str == 0;
}
/*
  sql_mode should *not* be IN_BINLOG: even though it is written to the binlog,
  the slave ignores the MODE_NO_DIR_IN_CREATE variable, so slave's value
  differs from master's (see log_event.cc: Query_log_event::do_apply_event()).
*/
static Sys_var_set Sys_sql_mode(
       "sql_mode",
       "Syntax: sql-mode=mode[,mode[,mode...]]. See the manual for the "
       "complete list of valid sql modes",
       SESSION_VAR(sql_mode), CMD_LINE(REQUIRED_ARG),
       sql_mode_names, DEFAULT(MODE_NO_ENGINE_SUBSTITUTION), NO_MUTEX_GUARD,
       NOT_IN_BINLOG, ON_CHECK(check_sql_mode), ON_UPDATE(fix_sql_mode));

static Sys_var_ulong Sys_max_statement_time(
       "max_statement_time",
       "Kill any statement that takes over the specified number of milliseconds",
       SESSION_VAR(max_statement_time), CMD_LINE(REQUIRED_ARG),
       VALID_RANGE(0, ULONG_MAX), DEFAULT(0), BLOCK_SIZE(1));

#if defined(HAVE_OPENSSL) && !defined(EMBEDDED_LIBRARY)
#define SSL_OPT(X) CMD_LINE(REQUIRED_ARG,X)
#else
#define SSL_OPT(X) NO_CMD_LINE
#endif

static Sys_var_charptr Sys_ssl_ca(
       "ssl_ca",
       "CA file in PEM format (check OpenSSL docs, implies --ssl)",
       READ_ONLY GLOBAL_VAR(opt_ssl_ca), SSL_OPT(OPT_SSL_CA),
       IN_FS_CHARSET, DEFAULT(0));

static Sys_var_charptr Sys_ssl_capath(
       "ssl_capath",
       "CA directory (check OpenSSL docs, implies --ssl)",
       READ_ONLY GLOBAL_VAR(opt_ssl_capath), SSL_OPT(OPT_SSL_CAPATH),
       IN_FS_CHARSET, DEFAULT(0));

static Sys_var_charptr Sys_ssl_cert(
       "ssl_cert", "X509 cert in PEM format (implies --ssl)",
       READ_ONLY GLOBAL_VAR(opt_ssl_cert), SSL_OPT(OPT_SSL_CERT),
       IN_FS_CHARSET, DEFAULT(0));

static Sys_var_charptr Sys_ssl_cipher(
       "ssl_cipher", "SSL cipher to use (implies --ssl)",
       READ_ONLY GLOBAL_VAR(opt_ssl_cipher), SSL_OPT(OPT_SSL_CIPHER),
       IN_FS_CHARSET, DEFAULT(0));

static Sys_var_charptr Sys_ssl_key(
       "ssl_key", "X509 key in PEM format (implies --ssl)",
       READ_ONLY GLOBAL_VAR(opt_ssl_key), SSL_OPT(OPT_SSL_KEY),
       IN_FS_CHARSET, DEFAULT(0));

static Sys_var_charptr Sys_ssl_crl(
       "ssl_crl",
       "CRL file in PEM format (check OpenSSL docs, implies --ssl)",
       READ_ONLY GLOBAL_VAR(opt_ssl_crl), SSL_OPT(OPT_SSL_CRL),
       IN_FS_CHARSET, DEFAULT(0));

static Sys_var_charptr Sys_ssl_crlpath(
       "ssl_crlpath",
       "CRL directory (check OpenSSL docs, implies --ssl)",
       READ_ONLY GLOBAL_VAR(opt_ssl_crlpath), SSL_OPT(OPT_SSL_CRLPATH),
       IN_FS_CHARSET, DEFAULT(0));


// why ENUM and not BOOL ?
static const char *updatable_views_with_limit_names[]= {"NO", "YES", 0};
static Sys_var_enum Sys_updatable_views_with_limit(
       "updatable_views_with_limit",
       "YES = Don't issue an error message (warning only) if a VIEW without "
       "presence of a key of the underlying table is used in queries with a "
       "LIMIT clause for updating. NO = Prohibit update of a VIEW, which "
       "does not contain a key of the underlying table and the query uses "
       "a LIMIT clause (usually get from GUI tools)",
       SESSION_VAR(updatable_views_with_limit), CMD_LINE(REQUIRED_ARG),
       updatable_views_with_limit_names, DEFAULT(TRUE));

static Sys_var_mybool Sys_sync_frm(
       "sync_frm", "Sync .frm files to disk on creation",
       GLOBAL_VAR(opt_sync_frm), CMD_LINE(OPT_ARG),
       DEFAULT(TRUE));

static char *system_time_zone_ptr;
static Sys_var_charptr Sys_system_time_zone(
       "system_time_zone", "The server system time zone",
       READ_ONLY GLOBAL_VAR(system_time_zone_ptr), NO_CMD_LINE,
       IN_FS_CHARSET, DEFAULT(system_time_zone));


#ifdef _WIN32
static bool fix_tp_min_threads(sys_var *, THD *, enum_var_type)
{
  tp_set_min_threads(threadpool_min_threads);
  return false;
}
#endif

/**
  Can't change the tx_read_only state if we are already in a
  transaction.
*/

static bool check_tx_read_only(sys_var *self, THD *thd, set_var *var)
{
  if (var->type == OPT_DEFAULT && thd->in_active_multi_stmt_transaction())
  {
    DBUG_ASSERT(thd->in_multi_stmt_transaction_mode());
    my_error(ER_CANT_CHANGE_TX_CHARACTERISTICS, MYF(0));
    return true;
  }
  return false;
}


bool Sys_var_tx_read_only::session_update(THD *thd, set_var *var)
{
  if (var->type == OPT_SESSION && Sys_var_mybool::session_update(thd, var))
    return true;
  if (var->type == OPT_DEFAULT || !thd->in_active_multi_stmt_transaction())
  {
    // @see Sys_var_tx_isolation::session_update() above for the rules.
    thd->tx_read_only= var->save_result.ulonglong_value;
  }
  return false;
}


static Sys_var_tx_read_only Sys_tx_read_only(
       "tx_read_only", "Set default transaction access mode to read only.",
       SESSION_VAR(tx_read_only), NO_CMD_LINE, DEFAULT(0),
       NO_MUTEX_GUARD, NOT_IN_BINLOG, ON_CHECK(check_tx_read_only));

static Sys_var_ulonglong Sys_tmp_table_size(
       "tmp_table_size",
       "If an internal in-memory temporary table exceeds this size, MySQL "
       "will automatically convert it to an on-disk MyISAM table",
       SESSION_VAR(tmp_table_size), CMD_LINE(REQUIRED_ARG),
       VALID_RANGE(1024, (ulonglong)~(intptr)0), DEFAULT(16*1024*1024),
       BLOCK_SIZE(1));

static Sys_var_mybool Sys_timed_mutexes(
       "timed_mutexes",
       "Specify whether to time mutexes. Deprecated, has no effect.",
       GLOBAL_VAR(timed_mutexes), CMD_LINE(OPT_ARG), DEFAULT(0),
       NO_MUTEX_GUARD, NOT_IN_BINLOG, ON_CHECK(NULL), ON_UPDATE(NULL),
       DEPRECATED(""));

static char *server_version_ptr;
static Sys_var_charptr Sys_version(
       "version", "Server version",
       READ_ONLY GLOBAL_VAR(server_version_ptr), NO_CMD_LINE,
       IN_SYSTEM_CHARSET, DEFAULT(server_version));

static char *server_version_comment_ptr;
static Sys_var_charptr Sys_version_comment(
       "version_comment", "version_comment",
       READ_ONLY GLOBAL_VAR(server_version_comment_ptr), NO_CMD_LINE,
       IN_SYSTEM_CHARSET, DEFAULT(MYSQL_COMPILATION_COMMENT));

static char *server_version_compile_machine_ptr;
static Sys_var_charptr Sys_version_compile_machine(
       "version_compile_machine", "version_compile_machine",
       READ_ONLY GLOBAL_VAR(server_version_compile_machine_ptr), NO_CMD_LINE,
       IN_SYSTEM_CHARSET, DEFAULT(MACHINE_TYPE));

static char *server_version_compile_os_ptr;
static Sys_var_charptr Sys_version_compile_os(
       "version_compile_os", "version_compile_os",
       READ_ONLY GLOBAL_VAR(server_version_compile_os_ptr), NO_CMD_LINE,
       IN_SYSTEM_CHARSET, DEFAULT(SYSTEM_TYPE));

static Sys_var_ulong Sys_net_wait_timeout(
       "wait_timeout",
       "The number of seconds the server waits for activity on a "
       "connection before closing it",
       SESSION_VAR(net_wait_timeout), CMD_LINE(REQUIRED_ARG),
       VALID_RANGE(1, IF_WIN(INT_MAX32/1000, LONG_TIMEOUT)),
       DEFAULT(NET_WAIT_TIMEOUT), BLOCK_SIZE(1));

/**
 "time_format" "date_format" "datetime_format"

  the following three variables are unused, and the source of confusion
  (bug reports like "I've changed date_format, but date format hasn't changed.
  I've made them read-only, to alleviate the situation somewhat.

  @todo make them NO_CMD_LINE ?
*/
static Sys_var_charptr Sys_date_format(
       "date_format", "The DATE format (ignored)",
       READ_ONLY GLOBAL_VAR(global_date_format.format.str),
       CMD_LINE(REQUIRED_ARG), IN_SYSTEM_CHARSET,
       DEFAULT(known_date_time_formats[ISO_FORMAT].date_format),
       NO_MUTEX_GUARD, NOT_IN_BINLOG, ON_CHECK(0), ON_UPDATE(0),
       DEPRECATED(""));

static Sys_var_charptr Sys_datetime_format(
       "datetime_format", "The DATETIME format (ignored)",
       READ_ONLY GLOBAL_VAR(global_datetime_format.format.str),
       CMD_LINE(REQUIRED_ARG), IN_SYSTEM_CHARSET,
       DEFAULT(known_date_time_formats[ISO_FORMAT].datetime_format),
       NO_MUTEX_GUARD, NOT_IN_BINLOG, ON_CHECK(0), ON_UPDATE(0),
       DEPRECATED(""));

static Sys_var_charptr Sys_time_format(
       "time_format", "The TIME format (ignored)",
       READ_ONLY GLOBAL_VAR(global_time_format.format.str),
       CMD_LINE(REQUIRED_ARG), IN_SYSTEM_CHARSET,
       DEFAULT(known_date_time_formats[ISO_FORMAT].time_format),
       NO_MUTEX_GUARD, NOT_IN_BINLOG, ON_CHECK(0), ON_UPDATE(0),
       DEPRECATED(""));

static Sys_var_mybool Sys_big_tables(
       "big_tables", "Allow big result sets by saving all "
       "temporary sets on file (Solves most 'table full' errors)",
       SESSION_VAR(big_tables), CMD_LINE(OPT_ARG), DEFAULT(FALSE));

static Sys_var_bit Sys_big_selects(
       "sql_big_selects", "sql_big_selects",
       SESSION_VAR(option_bits), NO_CMD_LINE, OPTION_BIG_SELECTS,
       DEFAULT(FALSE));

static Sys_var_bit Sys_log_off(
       "sql_log_off", "sql_log_off",
       SESSION_VAR(option_bits), NO_CMD_LINE, OPTION_LOG_OFF,
       DEFAULT(FALSE), NO_MUTEX_GUARD, NOT_IN_BINLOG, ON_CHECK(check_has_super));

/**
  This function sets the session variable thd->variables.sql_log_bin 
  to reflect changes to @@session.sql_log_bin.

  @param[IN] self   A pointer to the sys_var, i.e. Sys_log_binlog.
  @param[IN] type   The type either session or global.

  @return @c FALSE.
*/
static bool fix_sql_log_bin_after_update(sys_var *self, THD *thd,
                                         enum_var_type type)
{
  DBUG_ASSERT(type == OPT_SESSION);

  if (thd->variables.sql_log_bin)
    thd->variables.option_bits |= OPTION_BIN_LOG;
  else
    thd->variables.option_bits &= ~OPTION_BIN_LOG;

  return FALSE;
}

/**
  This function checks if the sql_log_bin can be changed,
  what is possible if:
    - the user is a super user;
    - the set is not called from within a function/trigger;
    - there is no on-going transaction.

  @param[IN] self   A pointer to the sys_var, i.e. Sys_log_binlog.
  @param[IN] var    A pointer to the set_var created by the parser.

  @return @c FALSE if the change is allowed, otherwise @c TRUE.
*/
static bool check_sql_log_bin(sys_var *self, THD *thd, set_var *var)
{
  if (check_has_super(self, thd, var))
    return TRUE;

  if (var->type == OPT_GLOBAL)
    return TRUE;

  /* If in a stored function/trigger, it's too late to change sql_log_bin. */
  if (thd->in_sub_stmt)
  {
    my_error(ER_STORED_FUNCTION_PREVENTS_SWITCH_SQL_LOG_BIN, MYF(0));
    return TRUE;
  }
  /* Make the session variable 'sql_log_bin' read-only inside a transaction. */
  if (thd->in_active_multi_stmt_transaction())
  {
    my_error(ER_INSIDE_TRANSACTION_PREVENTS_SWITCH_SQL_LOG_BIN, MYF(0));
    return TRUE;
  }

  return FALSE;
}

static Sys_var_mybool Sys_log_binlog(
       "sql_log_bin", "Controls whether logging to the binary log is done",
       SESSION_VAR(sql_log_bin), NO_CMD_LINE, DEFAULT(TRUE),
       NO_MUTEX_GUARD, NOT_IN_BINLOG, ON_CHECK(check_sql_log_bin),
       ON_UPDATE(fix_sql_log_bin_after_update));

static Sys_var_bit Sys_transaction_allow_batching(
       "transaction_allow_batching", "transaction_allow_batching",
       SESSION_ONLY(option_bits), NO_CMD_LINE, OPTION_ALLOW_BATCH,
       DEFAULT(FALSE));

static Sys_var_bit Sys_sql_warnings(
       "sql_warnings", "sql_warnings",
       SESSION_VAR(option_bits), NO_CMD_LINE, OPTION_WARNINGS,
       DEFAULT(FALSE));

static Sys_var_bit Sys_sql_notes(
       "sql_notes", "sql_notes",
       SESSION_VAR(option_bits), NO_CMD_LINE, OPTION_SQL_NOTES,
       DEFAULT(TRUE));

static Sys_var_bit Sys_auto_is_null(
       "sql_auto_is_null", "sql_auto_is_null",
       SESSION_VAR(option_bits), NO_CMD_LINE, OPTION_AUTO_IS_NULL,
       DEFAULT(FALSE), NO_MUTEX_GUARD, IN_BINLOG);

static Sys_var_bit Sys_safe_updates(
       "sql_safe_updates", "sql_safe_updates",
       SESSION_VAR(option_bits), NO_CMD_LINE, OPTION_SAFE_UPDATES,
       DEFAULT(FALSE));

static Sys_var_bit Sys_buffer_results(
       "sql_buffer_result", "sql_buffer_result",
       SESSION_VAR(option_bits), NO_CMD_LINE, OPTION_BUFFER_RESULT,
       DEFAULT(FALSE));

static Sys_var_bit Sys_quote_show_create(
       "sql_quote_show_create", "sql_quote_show_create",
       SESSION_VAR(option_bits), NO_CMD_LINE, OPTION_QUOTE_SHOW_CREATE,
       DEFAULT(TRUE));

static Sys_var_bit Sys_foreign_key_checks(
       "foreign_key_checks", "foreign_key_checks",
       SESSION_VAR(option_bits), NO_CMD_LINE,
       REVERSE(OPTION_NO_FOREIGN_KEY_CHECKS),
       DEFAULT(TRUE), NO_MUTEX_GUARD, IN_BINLOG);

static Sys_var_bit Sys_unique_checks(
       "unique_checks", "unique_checks",
       SESSION_VAR(option_bits), NO_CMD_LINE,
       REVERSE(OPTION_RELAXED_UNIQUE_CHECKS),
       DEFAULT(TRUE), NO_MUTEX_GUARD, IN_BINLOG);

static Sys_var_harows Sys_select_limit(
       "sql_select_limit",
       "The maximum number of rows to return from SELECT statements",
       SESSION_VAR(select_limit), NO_CMD_LINE,
       VALID_RANGE(0, HA_POS_ERROR), DEFAULT(HA_POS_ERROR), BLOCK_SIZE(1));

static bool update_timestamp(THD *thd, set_var *var)
{
  if (var->value)
  {
    double fl= floor(var->save_result.double_value); // Truncate integer part
    struct timeval tmp;
    tmp.tv_sec= (ulonglong) fl;
    /* Round nanoseconds to nearest microsecond */
    tmp.tv_usec= (ulonglong) rint((var->save_result.double_value - fl) * 1000000);
    thd->set_time(&tmp);
  }
  else // SET timestamp=DEFAULT
  {
    thd->user_time.tv_sec= 0;
    thd->user_time.tv_usec= 0;
  }
  return false;
}
static double read_timestamp(THD *thd)
{
  return (double) thd->start_time.tv_sec +
         (double) thd->start_time.tv_usec / 1000000;
}


static bool check_timestamp(sys_var *self, THD *thd, set_var *var)
{
  double val;

  if (!var->value)
    return FALSE;

  val= var->save_result.double_value;
  if (val != 0 &&          // this is how you set the default value
      (val < TIMESTAMP_MIN_VALUE || val > TIMESTAMP_MAX_VALUE))
  {
    ErrConvString prm(val);
    my_error(ER_WRONG_VALUE_FOR_VAR, MYF(0), "timestamp", prm.ptr());
    return TRUE;
  }
  return FALSE;
}


static Sys_var_session_special_double Sys_timestamp(
       "timestamp", "Set the time for this client",
       sys_var::ONLY_SESSION, NO_CMD_LINE,
       VALID_RANGE(0, 0), BLOCK_SIZE(1),
       NO_MUTEX_GUARD, IN_BINLOG, ON_CHECK(check_timestamp), 
       ON_UPDATE(update_timestamp), ON_READ(read_timestamp));

static bool update_last_insert_id(THD *thd, set_var *var)
{
  if (!var->value)
  {
    my_error(ER_NO_DEFAULT, MYF(0), var->var->name.str);
    return true;
  }
  thd->first_successful_insert_id_in_prev_stmt=
    var->save_result.ulonglong_value;
  return false;
}
static ulonglong read_last_insert_id(THD *thd)
{
  return (ulonglong) thd->read_first_successful_insert_id_in_prev_stmt();
}
static Sys_var_session_special Sys_last_insert_id(
       "last_insert_id", "The value to be returned from LAST_INSERT_ID()",
       sys_var::ONLY_SESSION, NO_CMD_LINE,
       VALID_RANGE(0, ULONGLONG_MAX), BLOCK_SIZE(1),
       NO_MUTEX_GUARD, IN_BINLOG, ON_CHECK(0),
       ON_UPDATE(update_last_insert_id), ON_READ(read_last_insert_id));

// alias for last_insert_id(), Sybase-style
static Sys_var_session_special Sys_identity(
       "identity", "Synonym for the last_insert_id variable",
       sys_var::ONLY_SESSION, NO_CMD_LINE,
       VALID_RANGE(0, ULONGLONG_MAX), BLOCK_SIZE(1),
       NO_MUTEX_GUARD, IN_BINLOG, ON_CHECK(0),
       ON_UPDATE(update_last_insert_id), ON_READ(read_last_insert_id));

/*
  insert_id should *not* be marked as written to the binlog (i.e., it
  should *not* be IN_BINLOG), because we want any statement that
  refers to insert_id explicitly to be unsafe.  (By "explicitly", we
  mean using @@session.insert_id, whereas insert_id is used
  "implicitly" when NULL value is inserted into an auto_increment
  column).

  We want statements referring explicitly to @@session.insert_id to be
  unsafe, because insert_id is modified internally by the slave sql
  thread when NULL values are inserted in an AUTO_INCREMENT column.
  This modification interfers with the value of the
  @@session.insert_id variable if @@session.insert_id is referred
  explicitly by an insert statement (as is seen by executing "SET
  @@session.insert_id=0; CREATE TABLE t (a INT, b INT KEY
  AUTO_INCREMENT); INSERT INTO t(a) VALUES (@@session.insert_id);" in
  statement-based logging mode: t will be different on master and
  slave).
*/
static bool update_insert_id(THD *thd, set_var *var)
{
  if (!var->value)
  {
    my_error(ER_NO_DEFAULT, MYF(0), var->var->name.str);
    return true;
  }
  thd->force_one_auto_inc_interval(var->save_result.ulonglong_value);
  return false;
}

static ulonglong read_insert_id(THD *thd)
{
  return thd->auto_inc_intervals_forced.minimum();
}
static Sys_var_session_special Sys_insert_id(
       "insert_id", "The value to be used by the following INSERT "
       "or ALTER TABLE statement when inserting an AUTO_INCREMENT value",
       sys_var::ONLY_SESSION, NO_CMD_LINE,
       VALID_RANGE(0, ULONGLONG_MAX), BLOCK_SIZE(1),
       NO_MUTEX_GUARD, NOT_IN_BINLOG, ON_CHECK(0),
       ON_UPDATE(update_insert_id), ON_READ(read_insert_id));

static bool update_rand_seed1(THD *thd, set_var *var)
{
  if (!var->value)
  {
    my_error(ER_NO_DEFAULT, MYF(0), var->var->name.str);
    return true;
  }
  thd->rand.seed1= (ulong) var->save_result.ulonglong_value;
  return false;
}
static ulonglong read_rand_seed(THD *thd)
{
  return 0;
}
static Sys_var_session_special Sys_rand_seed1(
       "rand_seed1", "Sets the internal state of the RAND() "
       "generator for replication purposes",
       sys_var::ONLY_SESSION, NO_CMD_LINE,
       VALID_RANGE(0, ULONG_MAX), BLOCK_SIZE(1),
       NO_MUTEX_GUARD, IN_BINLOG, ON_CHECK(0),
       ON_UPDATE(update_rand_seed1), ON_READ(read_rand_seed));

static bool update_rand_seed2(THD *thd, set_var *var)
{
  if (!var->value)
  {
    my_error(ER_NO_DEFAULT, MYF(0), var->var->name.str);
    return true;
  }
  thd->rand.seed2= (ulong) var->save_result.ulonglong_value;
  return false;
}
static Sys_var_session_special Sys_rand_seed2(
       "rand_seed2", "Sets the internal state of the RAND() "
       "generator for replication purposes",
       sys_var::ONLY_SESSION, NO_CMD_LINE,
       VALID_RANGE(0, ULONG_MAX), BLOCK_SIZE(1),
       NO_MUTEX_GUARD, IN_BINLOG, ON_CHECK(0),
       ON_UPDATE(update_rand_seed2), ON_READ(read_rand_seed));

static ulonglong read_error_count(THD *thd)
{
  return thd->get_stmt_da()->error_count();
}
// this really belongs to the SHOW STATUS
static Sys_var_session_special Sys_error_count(
       "error_count", "The number of errors that resulted from the "
       "last statement that generated messages",
       READ_ONLY sys_var::ONLY_SESSION, NO_CMD_LINE,
       VALID_RANGE(0, ULONGLONG_MAX), BLOCK_SIZE(1), NO_MUTEX_GUARD,
       NOT_IN_BINLOG, ON_CHECK(0), ON_UPDATE(0), ON_READ(read_error_count));

static ulonglong read_warning_count(THD *thd)
{
  return thd->get_stmt_da()->warn_count();
}
// this really belongs to the SHOW STATUS
static Sys_var_session_special Sys_warning_count(
       "warning_count", "The number of errors, warnings, and notes "
       "that resulted from the last statement that generated messages",
       READ_ONLY sys_var::ONLY_SESSION, NO_CMD_LINE,
       VALID_RANGE(0, ULONGLONG_MAX), BLOCK_SIZE(1), NO_MUTEX_GUARD,
       NOT_IN_BINLOG, ON_CHECK(0), ON_UPDATE(0), ON_READ(read_warning_count));

static Sys_var_ulong Sys_default_week_format(
       "default_week_format",
       "The default week format used by WEEK() functions",
       SESSION_VAR(default_week_format), CMD_LINE(REQUIRED_ARG),
       VALID_RANGE(0, 7), DEFAULT(0), BLOCK_SIZE(1));

static char *glob_hostname_ptr;
static Sys_var_charptr Sys_hostname(
       "hostname", "Server host name",
       READ_ONLY GLOBAL_VAR(glob_hostname_ptr), NO_CMD_LINE,
       IN_FS_CHARSET, DEFAULT(glob_hostname));

static Sys_var_mybool Sys_keep_files_on_create(
       "keep_files_on_create",
       "Don't overwrite stale .MYD and .MYI even if no directory is specified",
       SESSION_VAR(keep_files_on_create), CMD_LINE(OPT_ARG),
       DEFAULT(FALSE));

static char *license;
static Sys_var_charptr Sys_license(
       "license", "The type of license the server has",
       READ_ONLY GLOBAL_VAR(license), NO_CMD_LINE, IN_SYSTEM_CHARSET,
       DEFAULT(STRINGIFY_ARG(LICENSE)));

static bool check_log_path(sys_var *self, THD *thd, set_var *var)
{
  if (!var->value)
    return false; // DEFAULT is ok

  if (!var->save_result.string_value.str)
    return true;

  if (var->save_result.string_value.length > FN_REFLEN)
  { // path is too long
    my_error(ER_PATH_LENGTH, MYF(0), self->name.str);
    return true;
  }

  char path[FN_REFLEN];
  size_t path_length= unpack_filename(path, var->save_result.string_value.str);

  if (!path_length)
    return true;

  if (!is_filename_allowed(var->save_result.string_value.str, 
                           var->save_result.string_value.length, TRUE))
  {
     my_error(ER_WRONG_VALUE_FOR_VAR, MYF(0), 
              self->name.str, var->save_result.string_value.str);
     return true;
  }

  MY_STAT f_stat;

  if (my_stat(path, &f_stat, MYF(0)))
  {
    if (!MY_S_ISREG(f_stat.st_mode) || !(f_stat.st_mode & MY_S_IWRITE))
      return true; // not a regular writable file
    return false;
  }

  (void) dirname_part(path, var->save_result.string_value.str, &path_length);

  if (var->save_result.string_value.length - path_length >= FN_LEN)
  { // filename is too long
      my_error(ER_PATH_LENGTH, MYF(0), self->name.str);
      return true;
  }

  if (!path_length) // no path is good path (remember, relative to datadir)
    return false;

  if (my_access(path, (F_OK|W_OK)))
    return true; // directory is not writable

  return false;
}
static bool fix_log(char** logname, const char* default_logname,
                    const char*ext, bool enabled, void (*reopen)(char*))
{
  if (!*logname) // SET ... = DEFAULT
  {
    char buff[FN_REFLEN];
    *logname= my_strdup(make_log_name(buff, default_logname, ext),
                        MYF(MY_FAE+MY_WME));
    if (!*logname)
      return true;
  }
  logger.lock_exclusive();
  mysql_mutex_unlock(&LOCK_global_system_variables);
  if (enabled)
    reopen(*logname);
  logger.unlock();
  mysql_mutex_lock(&LOCK_global_system_variables);
  return false;
}
static void reopen_general_log(char* name)
{
  logger.get_log_file_handler()->close(0);
  logger.get_log_file_handler()->open_query_log(name);
}
static bool fix_general_log_file(sys_var *self, THD *thd, enum_var_type type)
{
  return fix_log(&opt_logname, default_logfile_name, ".log", opt_log,
                 reopen_general_log);
}
static Sys_var_charptr Sys_general_log_path(
       "general_log_file", "Log connections and queries to given file",
       GLOBAL_VAR(opt_logname), CMD_LINE(REQUIRED_ARG),
       IN_FS_CHARSET, DEFAULT(0), NO_MUTEX_GUARD, NOT_IN_BINLOG,
       ON_CHECK(check_log_path), ON_UPDATE(fix_general_log_file));

static Sys_var_have Sys_have_compress(
       "have_compress", "have_compress",
       READ_ONLY GLOBAL_VAR(have_compress), NO_CMD_LINE);

static Sys_var_have Sys_have_crypt(
       "have_crypt", "have_crypt",
       READ_ONLY GLOBAL_VAR(have_crypt), NO_CMD_LINE);

static Sys_var_have Sys_have_dlopen(
       "have_dynamic_loading", "have_dynamic_loading",
       READ_ONLY GLOBAL_VAR(have_dlopen), NO_CMD_LINE);

static Sys_var_have Sys_have_geometry(
       "have_geometry", "have_geometry",
       READ_ONLY GLOBAL_VAR(have_geometry), NO_CMD_LINE);

static Sys_var_have Sys_have_openssl(
       "have_openssl", "have_openssl",
       READ_ONLY GLOBAL_VAR(have_ssl), NO_CMD_LINE);

static Sys_var_have Sys_have_profiling(
       "have_profiling", "have_profiling",
       READ_ONLY GLOBAL_VAR(have_profiling), NO_CMD_LINE, NO_MUTEX_GUARD,
       NOT_IN_BINLOG, ON_CHECK(0), ON_UPDATE(0), DEPRECATED(""));

static Sys_var_have Sys_have_backup_locks(
       "have_backup_locks", "have_backup_locks",
       READ_ONLY GLOBAL_VAR(have_backup_locks), NO_CMD_LINE);

static Sys_var_have Sys_have_snapshot_cloning(
       "have_snapshot_cloning", "have_snapshot_cloning",
       READ_ONLY GLOBAL_VAR(have_snapshot_cloning), NO_CMD_LINE);

static Sys_var_have Sys_have_query_cache(
       "have_query_cache", "have_query_cache",
       READ_ONLY GLOBAL_VAR(have_query_cache), NO_CMD_LINE);

static Sys_var_have Sys_have_rtree_keys(
       "have_rtree_keys", "have_rtree_keys",
       READ_ONLY GLOBAL_VAR(have_rtree_keys), NO_CMD_LINE);

static Sys_var_have Sys_have_ssl(
       "have_ssl", "have_ssl",
       READ_ONLY GLOBAL_VAR(have_ssl), NO_CMD_LINE);

static Sys_var_have Sys_have_symlink(
       "have_symlink", "have_symlink",
       READ_ONLY GLOBAL_VAR(have_symlink), NO_CMD_LINE);

static Sys_var_have Sys_have_statement_timeout(
       "have_statement_timeout", "have_statement_timeout",
       READ_ONLY GLOBAL_VAR(have_statement_timeout), NO_CMD_LINE);

static bool fix_log_state(sys_var *self, THD *thd, enum_var_type type);
static Sys_var_mybool Sys_general_log(
       "general_log", "Log connections and queries to a table or log file. "
       "Defaults logging to a file hostname.log or a table mysql.general_log"
       "if --log-output=TABLE is used",
       GLOBAL_VAR(opt_log), CMD_LINE(OPT_ARG),
       DEFAULT(FALSE), NO_MUTEX_GUARD, NOT_IN_BINLOG, ON_CHECK(0),
       ON_UPDATE(fix_log_state));

static bool fix_log_state(sys_var *self, THD *thd, enum_var_type type)
{
  bool res;
  my_bool *UNINIT_VAR(newvalptr), newval, UNINIT_VAR(oldval);
  uint UNINIT_VAR(log_type);

  if (self == &Sys_general_log)
  {
    newvalptr= &opt_log;
    oldval=    logger.get_log_file_handler()->is_open();
    log_type=  QUERY_LOG_GENERAL;
  }
  else
    DBUG_ASSERT(FALSE);

  newval= *newvalptr;
  if (oldval == newval)
    return false;

  *newvalptr= oldval; // [de]activate_log_handler works that way (sigh)

  mysql_mutex_unlock(&LOCK_global_system_variables);
  if (!newval)
  {
    logger.deactivate_log_handler(thd, log_type);
    res= false;
  }
  else
    res= logger.activate_log_handler(thd, log_type);
  mysql_mutex_lock(&LOCK_global_system_variables);
  return res;
}

static bool check_not_empty_set(sys_var *self, THD *thd, set_var *var)
{
  return var->save_result.ulonglong_value == 0;
}
static bool fix_log_output(sys_var *self, THD *thd, enum_var_type type)
{
  logger.lock_exclusive();
  logger.init_general_log(log_output_options);
  logger.unlock();
  return false;
}

static const char *log_output_names[] = { "NONE", "FILE", "TABLE", NULL};

static Sys_var_set Sys_log_output(
       "log_output", "Syntax: log-output=value[,value...], "
       "where \"value\" could be TABLE, FILE or NONE",
       GLOBAL_VAR(log_output_options), CMD_LINE(REQUIRED_ARG),
       log_output_names, DEFAULT(LOG_FILE), NO_MUTEX_GUARD, NOT_IN_BINLOG,
       ON_CHECK(check_not_empty_set), ON_UPDATE(fix_log_output));


static bool check_locale(sys_var *self, THD *thd, set_var *var)
{
  if (!var->value)
    return false;

  MY_LOCALE *locale;
  char buff[STRING_BUFFER_USUAL_SIZE];
  if (var->value->result_type() == INT_RESULT)
  {
    int lcno= (int)var->value->val_int();
    if (!(locale= my_locale_by_number(lcno)))
    {
      my_error(ER_UNKNOWN_LOCALE, MYF(0), llstr(lcno, buff));
      return true;
    }
    if (check_not_null(self, thd, var))
      return true;
  }
  else // STRING_RESULT
  {
    String str(buff, sizeof(buff), system_charset_info), *res;
    if (!(res=var->value->val_str(&str)))
      return true;
    else if (!(locale= my_locale_by_name(res->c_ptr_safe())))
    {
      ErrConvString err(res);
      my_error(ER_UNKNOWN_LOCALE, MYF(0), err.ptr());
      return true;
    }
  }

  var->save_result.ptr= locale;

  if (!locale->errmsgs->errmsgs)
  {
    mysql_mutex_lock(&LOCK_error_messages);
    if (!locale->errmsgs->errmsgs &&
        read_texts(ERRMSG_FILE, locale->errmsgs->language,
                   &locale->errmsgs->errmsgs,
                   ER_ERROR_LAST - ER_ERROR_FIRST + 1))
    {
      push_warning_printf(thd, Sql_condition::WARN_LEVEL_WARN, ER_UNKNOWN_ERROR,
                          "Can't process error message file for locale '%s'",
                          locale->name);
      mysql_mutex_unlock(&LOCK_error_messages);
      return true;
    }
    mysql_mutex_unlock(&LOCK_error_messages);
  }
  return false;
}
static Sys_var_struct Sys_lc_messages(
       "lc_messages", "Set the language used for the error messages",
       SESSION_VAR(lc_messages), NO_CMD_LINE,
       my_offsetof(MY_LOCALE, name), DEFAULT(&my_default_lc_messages),
       NO_MUTEX_GUARD, NOT_IN_BINLOG, ON_CHECK(check_locale));

static Sys_var_struct Sys_lc_time_names(
       "lc_time_names", "Set the language used for the month "
       "names and the days of the week",
       SESSION_VAR(lc_time_names), NO_CMD_LINE,
       my_offsetof(MY_LOCALE, name), DEFAULT(&my_default_lc_time_names),
       NO_MUTEX_GUARD, IN_BINLOG, ON_CHECK(check_locale));


static Sys_var_charptr Sys_ignore_db_dirs(
       "ignore_db_dirs",
       "The list of directories to ignore when collecting database lists",
       READ_ONLY GLOBAL_VAR(opt_ignore_db_dirs), 
       NO_CMD_LINE,
       IN_FS_CHARSET, DEFAULT(0));

/*
  This code is not being used but we will keep it as it may be
  useful if we decide to keeep enforce_gtid_consistency.
*/
#ifdef NON_DISABLED_GTID
static bool check_enforce_gtid_consistency(
  sys_var *self, THD *thd, set_var *var)
{
  DBUG_ENTER("check_enforce_gtid_consistency");

  my_error(ER_NOT_SUPPORTED_YET, MYF(0),
           "ENFORCE_GTID_CONSISTENCY");
  DBUG_RETURN(true);

  if (check_top_level_stmt_and_super(self, thd, var) ||
      check_outside_transaction(self, thd, var))
    DBUG_RETURN(true);
  if (gtid_mode >= 2 && var->value->val_int() == 0)
  {
    my_error(ER_GTID_MODE_2_OR_3_REQUIRES_ENFORCE_GTID_CONSISTENCY_ON, MYF(0));
    DBUG_RETURN(true);
  }
  DBUG_RETURN(false);
}
#endif


static Sys_var_enum Sys_block_encryption_mode(
  "block_encryption_mode", "mode for AES_ENCRYPT/AES_DECRYPT",
  SESSION_VAR(my_aes_mode), CMD_LINE(REQUIRED_ARG),
  my_aes_opmode_names, DEFAULT(my_aes_128_ecb));
