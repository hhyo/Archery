/* Copyright (c) 2000, 2014, Oracle and/or its affiliates. All rights reserved.

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

#define MYSQL_LEX 1
#include "my_global.h"
#include "sql_priv.h"
#include "unireg.h"                    // REQUIRED: for other includes
#include "sql_parse.h"        // sql_kill, *_precheck, *_prepare
#include "sql_base.h"         // find_temporary_table
#include "sql_show.h"         // mysqld_list_*, mysqld_show_*,
                              // calc_sum_of_all_status
#include "mysqld.h"
#include "sql_locale.h"                         // my_locale_en_US
#include "sql_view.h"         // mysql_create_view, mysql_drop_view
#include "sql_delete.h"       // mysql_delete
#include "sql_insert.h"       // mysql_insert
#include "sql_update.h"       // mysql_update, mysql_multi_update
#include "sql_partition.h"    // struct partition_info
#include "sql_db.h"           // mysql_change_db, mysql_create_db,
                              // mysql_rm_db, mysql_upgrade_db,
                              // mysql_alter_db,
                              // check_db_dir_existence,
                              // my_dbopt_cleanup
#include "sql_table.h"        // mysql_create_like_table,
                              // mysql_create_table,
                              // mysql_alter_table,
                              // mysql_backup_table,
                              // mysql_restore_table
#include "sql_reload.h"       // reload_acl_and_cache
#include "sql_admin.h"        // mysql_assign_to_keycache
#include "sql_rename.h"       // mysql_rename_table
#include "sql_tablespace.h"   // mysql_alter_tablespace
#include "sql_acl.h"          // *_ACL, check_grant, is_acl_user,
                              // has_any_table_level_privileges,
                              // mysql_drop_user, mysql_rename_user,
                              // check_grant_routine,
                              // mysql_routine_grant,
                              // mysql_show_grants,
                              // sp_grant_privileges, ...
#include "sql_test.h"         // mysql_print_status
#include "sql_load.h"         // mysql_load
#include "sql_servers.h"      // create_servers, alter_servers,
                              // drop_servers, servers_reload
#include "sql_handler.h"      // mysql_ha_open, mysql_ha_close,
                              // mysql_ha_read
#include "sql_do.h"           // mysql_do
#include "sql_help.h"         // mysqld_help
#include <m_ctype.h>
#include <my_dir.h>

#include "sp_head.h"
#include "sp_instr.h"
#include "sp.h"
#include "sql_trigger.h"
#include "sql_prepare.h"
#include "probes_mysql.h"
#include "set_var.h"
#include "mysql/psi/mysql_statement.h"
#include "sql_bootstrap.h"
#include "opt_explain.h"
#include "sql_rewrite.h"
#include "global_threads.h"
#include "sql_analyse.h"

#include <algorithm>
using std::max;
using std::min;

#include "sql_timer.h"        // thd_timer_set, thd_timer_reset

#define FLAGSTR(V,F) ((V)&(F)?#F" ":"")

/**
  @defgroup Runtime_Environment Runtime Environment
  @{
*/

/* Used in error handling only */
#define SP_TYPE_STRING(LP) \
  ((LP)->sphead->m_type == SP_TYPE_FUNCTION ? "FUNCTION" : "PROCEDURE")
#define SP_COM_STRING(LP) \
  ((LP)->sql_command == SQLCOM_CREATE_SPFUNCTION || \
   (LP)->sql_command == SQLCOM_ALTER_FUNCTION || \
   (LP)->sql_command == SQLCOM_SHOW_CREATE_FUNC || \
   (LP)->sql_command == SQLCOM_DROP_FUNCTION ? \
   "FUNCTION" : "PROCEDURE")

// Uses the THD to update the global stats by user name and client IP
void update_global_user_stats(THD* thd, bool create_user, time_t now);

const char *any_db="*any*";	// Special symbol for check_access

const LEX_STRING command_name[]={
  { C_STRING_WITH_LEN("Sleep") },
  { C_STRING_WITH_LEN("Quit") },
  { C_STRING_WITH_LEN("Init DB") },
  { C_STRING_WITH_LEN("Query") },
  { C_STRING_WITH_LEN("Field List") },
  { C_STRING_WITH_LEN("Create DB") },
  { C_STRING_WITH_LEN("Drop DB") },
  { C_STRING_WITH_LEN("Refresh") },
  { C_STRING_WITH_LEN("Shutdown") },
  { C_STRING_WITH_LEN("Statistics") },
  { C_STRING_WITH_LEN("Processlist") },
  { C_STRING_WITH_LEN("Connect") },
  { C_STRING_WITH_LEN("Kill") },
  { C_STRING_WITH_LEN("Debug") },
  { C_STRING_WITH_LEN("Ping") },
  { C_STRING_WITH_LEN("Time") },
  { C_STRING_WITH_LEN("Delayed insert") },
  { C_STRING_WITH_LEN("Change user") },
  { C_STRING_WITH_LEN("Binlog Dump") },
  { C_STRING_WITH_LEN("Table Dump") },
  { C_STRING_WITH_LEN("Connect Out") },
  { C_STRING_WITH_LEN("Register Slave") },
  { C_STRING_WITH_LEN("Prepare") },
  { C_STRING_WITH_LEN("Execute") },
  { C_STRING_WITH_LEN("Long Data") },
  { C_STRING_WITH_LEN("Close stmt") },
  { C_STRING_WITH_LEN("Reset stmt") },
  { C_STRING_WITH_LEN("Set option") },
  { C_STRING_WITH_LEN("Fetch") },
  { C_STRING_WITH_LEN("Daemon") },
  { C_STRING_WITH_LEN("Binlog Dump GTID") },
  { C_STRING_WITH_LEN("Error") }  // Last command number
};

const char *xa_state_names[]={
  "NON-EXISTING", "ACTIVE", "IDLE", "PREPARED", "ROLLBACK ONLY"
};


/**
  Mark all commands that somehow changes a table.

  This is used to check number of updates / hour.

  sql_command is actually set to SQLCOM_END sometimes
  so we need the +1 to include it in the array.

  See COMMAND_FLAG_xxx for different type of commands
     2  - query that returns meaningful ROW_COUNT() -
          a number of modified rows
*/

uint sql_command_flags[SQLCOM_END+1];
uint server_command_flags[COM_END+1];

void init_update_queries(void)
{
  /* Initialize the server command flags array. */
  memset(server_command_flags, 0, sizeof(server_command_flags));

  server_command_flags[COM_STATISTICS]= CF_SKIP_QUESTIONS;
  server_command_flags[COM_PING]=       CF_SKIP_QUESTIONS;
  server_command_flags[COM_STMT_PREPARE]= CF_SKIP_QUESTIONS;
  server_command_flags[COM_STMT_CLOSE]=   CF_SKIP_QUESTIONS;
  server_command_flags[COM_STMT_RESET]=   CF_SKIP_QUESTIONS;

  /* Initialize the sql command flags array. */
  memset(sql_command_flags, 0, sizeof(sql_command_flags));

  /*
    In general, DDL statements do not generate row events and do not go
    through a cache before being written to the binary log. However, the
    CREATE TABLE...SELECT is an exception because it may generate row
    events. For that reason,  the SQLCOM_CREATE_TABLE  which represents
    a CREATE TABLE, including the CREATE TABLE...SELECT, has the
    CF_CAN_GENERATE_ROW_EVENTS flag. The distinction between a regular
    CREATE TABLE and the CREATE TABLE...SELECT is made in other parts of
    the code, in particular in the Query_log_event's constructor.
  */
  sql_command_flags[SQLCOM_CREATE_TABLE]=   CF_CHANGES_DATA | CF_REEXECUTION_FRAGILE |
                                            CF_AUTO_COMMIT_TRANS |
                                            CF_CAN_GENERATE_ROW_EVENTS;
  sql_command_flags[SQLCOM_CREATE_INDEX]=   CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_ALTER_TABLE]=    CF_CHANGES_DATA | CF_WRITE_LOGS_COMMAND |
                                            CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_TRUNCATE]=       CF_CHANGES_DATA | CF_WRITE_LOGS_COMMAND |
                                            CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_DROP_TABLE]=     CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_LOAD]=           CF_CHANGES_DATA | CF_REEXECUTION_FRAGILE |
                                            CF_CAN_GENERATE_ROW_EVENTS;
  sql_command_flags[SQLCOM_CREATE_DB]=      CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_DROP_DB]=        CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_ALTER_DB_UPGRADE]= CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_ALTER_DB]=       CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_RENAME_TABLE]=   CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_DROP_INDEX]=     CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_CREATE_VIEW]=    CF_CHANGES_DATA | CF_REEXECUTION_FRAGILE |
                                            CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_DROP_VIEW]=      CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_CREATE_TRIGGER]= CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_DROP_TRIGGER]=   CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_CREATE_EVENT]=   CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_ALTER_EVENT]=    CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_DROP_EVENT]=     CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;

  sql_command_flags[SQLCOM_UPDATE]=	    CF_CHANGES_DATA | CF_REEXECUTION_FRAGILE |
                                            CF_CAN_GENERATE_ROW_EVENTS |
                                            CF_OPTIMIZER_TRACE |
                                            CF_CAN_BE_EXPLAINED;
  sql_command_flags[SQLCOM_UPDATE_MULTI]=   CF_CHANGES_DATA | CF_REEXECUTION_FRAGILE |
                                            CF_CAN_GENERATE_ROW_EVENTS |
                                            CF_OPTIMIZER_TRACE |
                                            CF_CAN_BE_EXPLAINED;
  // This is INSERT VALUES(...), can be VALUES(stored_func()) so we trace it
  sql_command_flags[SQLCOM_INSERT]=	    CF_CHANGES_DATA | CF_REEXECUTION_FRAGILE |
                                            CF_CAN_GENERATE_ROW_EVENTS |
                                            CF_OPTIMIZER_TRACE |
                                            CF_CAN_BE_EXPLAINED;
  sql_command_flags[SQLCOM_INSERT_SELECT]=  CF_CHANGES_DATA | CF_REEXECUTION_FRAGILE |
                                            CF_CAN_GENERATE_ROW_EVENTS |
                                            CF_OPTIMIZER_TRACE |
                                            CF_CAN_BE_EXPLAINED;
  sql_command_flags[SQLCOM_DELETE]=         CF_CHANGES_DATA | CF_REEXECUTION_FRAGILE |
                                            CF_CAN_GENERATE_ROW_EVENTS |
                                            CF_OPTIMIZER_TRACE |
                                            CF_CAN_BE_EXPLAINED;
  sql_command_flags[SQLCOM_DELETE_MULTI]=   CF_CHANGES_DATA | CF_REEXECUTION_FRAGILE |
                                            CF_CAN_GENERATE_ROW_EVENTS |
                                            CF_OPTIMIZER_TRACE |
                                            CF_CAN_BE_EXPLAINED;
  sql_command_flags[SQLCOM_REPLACE]=        CF_CHANGES_DATA | CF_REEXECUTION_FRAGILE |
                                            CF_CAN_GENERATE_ROW_EVENTS |
                                            CF_OPTIMIZER_TRACE |
                                            CF_CAN_BE_EXPLAINED;
  sql_command_flags[SQLCOM_REPLACE_SELECT]= CF_CHANGES_DATA | CF_REEXECUTION_FRAGILE |
                                            CF_CAN_GENERATE_ROW_EVENTS |
                                            CF_OPTIMIZER_TRACE |
                                            CF_CAN_BE_EXPLAINED;
  sql_command_flags[SQLCOM_SELECT]=         CF_REEXECUTION_FRAGILE |
                                            CF_CAN_GENERATE_ROW_EVENTS |
                                            CF_OPTIMIZER_TRACE |
                                            CF_CAN_BE_EXPLAINED;
  // (1) so that subquery is traced when doing "SET @var = (subquery)"
  /*
    @todo SQLCOM_SET_OPTION should have CF_CAN_GENERATE_ROW_EVENTS
    set, because it may invoke a stored function that generates row
    events. /Sven
  */
  sql_command_flags[SQLCOM_SET_OPTION]=     CF_REEXECUTION_FRAGILE |
                                            CF_AUTO_COMMIT_TRANS |
                                            CF_CAN_GENERATE_ROW_EVENTS |
                                            CF_OPTIMIZER_TRACE; // (1)
  // (1) so that subquery is traced when doing "DO @var := (subquery)"
  sql_command_flags[SQLCOM_DO]=             CF_REEXECUTION_FRAGILE |
                                            CF_CAN_GENERATE_ROW_EVENTS |
                                            CF_OPTIMIZER_TRACE; // (1)

  sql_command_flags[SQLCOM_SHOW_STATUS_PROC]= CF_STATUS_COMMAND | CF_REEXECUTION_FRAGILE;
  sql_command_flags[SQLCOM_SHOW_STATUS]=      CF_STATUS_COMMAND | CF_REEXECUTION_FRAGILE;
  sql_command_flags[SQLCOM_SHOW_DATABASES]=   CF_STATUS_COMMAND | CF_REEXECUTION_FRAGILE;
  sql_command_flags[SQLCOM_SHOW_TRIGGERS]=    CF_STATUS_COMMAND | CF_REEXECUTION_FRAGILE;
  sql_command_flags[SQLCOM_SHOW_EVENTS]=      CF_STATUS_COMMAND | CF_REEXECUTION_FRAGILE;
  sql_command_flags[SQLCOM_SHOW_OPEN_TABLES]= CF_STATUS_COMMAND | CF_REEXECUTION_FRAGILE;
  sql_command_flags[SQLCOM_SHOW_PLUGINS]=     CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_FIELDS]=      CF_STATUS_COMMAND | CF_REEXECUTION_FRAGILE;
  sql_command_flags[SQLCOM_SHOW_KEYS]=        CF_STATUS_COMMAND | CF_REEXECUTION_FRAGILE;
  sql_command_flags[SQLCOM_SHOW_VARIABLES]=   CF_STATUS_COMMAND | CF_REEXECUTION_FRAGILE;
  sql_command_flags[SQLCOM_SHOW_CHARSETS]=    CF_STATUS_COMMAND | CF_REEXECUTION_FRAGILE;
  sql_command_flags[SQLCOM_SHOW_COLLATIONS]=  CF_STATUS_COMMAND | CF_REEXECUTION_FRAGILE;
  sql_command_flags[SQLCOM_SHOW_BINLOGS]=     CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_SLAVE_HOSTS]= CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_BINLOG_EVENTS]= CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_STORAGE_ENGINES]= CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_PRIVILEGES]=  CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_WARNS]=       CF_STATUS_COMMAND | CF_DIAGNOSTIC_STMT;
  sql_command_flags[SQLCOM_SHOW_ERRORS]=      CF_STATUS_COMMAND | CF_DIAGNOSTIC_STMT;
  sql_command_flags[SQLCOM_SHOW_ENGINE_STATUS]= CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_ENGINE_MUTEX]= CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_ENGINE_LOGS]= CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_PROCESSLIST]= CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_GRANTS]=      CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_CREATE_DB]=   CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_CREATE]=  CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_MASTER_STAT]= CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_SLAVE_STAT]=  CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_SLAVE_NOLOCK_STAT]=  CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_CREATE_PROC]= CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_CREATE_FUNC]= CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_CREATE_TRIGGER]=  CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_STATUS_FUNC]= CF_STATUS_COMMAND | CF_REEXECUTION_FRAGILE;
  sql_command_flags[SQLCOM_SHOW_PROC_CODE]=   CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_FUNC_CODE]=   CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_CREATE_EVENT]= CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_PROFILES]=    CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_SHOW_PROFILE]=     CF_STATUS_COMMAND;
  sql_command_flags[SQLCOM_BINLOG_BASE64_EVENT]= CF_STATUS_COMMAND |
                                                 CF_CAN_GENERATE_ROW_EVENTS;

   sql_command_flags[SQLCOM_SHOW_TABLES]=       (CF_STATUS_COMMAND |
                                                 CF_SHOW_TABLE_COMMAND |
                                                 CF_REEXECUTION_FRAGILE);
  sql_command_flags[SQLCOM_SHOW_TABLE_STATUS]= (CF_STATUS_COMMAND |
                                                CF_SHOW_TABLE_COMMAND |
                                                CF_REEXECUTION_FRAGILE);

  sql_command_flags[SQLCOM_CREATE_USER]=       CF_CHANGES_DATA;
  sql_command_flags[SQLCOM_RENAME_USER]=       CF_CHANGES_DATA;
  sql_command_flags[SQLCOM_DROP_USER]=         CF_CHANGES_DATA;
  sql_command_flags[SQLCOM_ALTER_USER]=        CF_CHANGES_DATA;
  sql_command_flags[SQLCOM_GRANT]=             CF_CHANGES_DATA;
  sql_command_flags[SQLCOM_REVOKE]=            CF_CHANGES_DATA;
  sql_command_flags[SQLCOM_REVOKE_ALL]=        CF_CHANGES_DATA;
  sql_command_flags[SQLCOM_OPTIMIZE]=          CF_CHANGES_DATA;
  sql_command_flags[SQLCOM_CREATE_FUNCTION]=   CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_CREATE_PROCEDURE]=  CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_CREATE_SPFUNCTION]= CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_DROP_PROCEDURE]=    CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_DROP_FUNCTION]=     CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_ALTER_PROCEDURE]=   CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_ALTER_FUNCTION]=    CF_CHANGES_DATA | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_INSTALL_PLUGIN]=    CF_CHANGES_DATA;
  sql_command_flags[SQLCOM_UNINSTALL_PLUGIN]=  CF_CHANGES_DATA;

  /* Does not change the contents of the diagnostics area. */
  sql_command_flags[SQLCOM_GET_DIAGNOSTICS]= CF_DIAGNOSTIC_STMT;

  /*
    (1): without it, in "CALL some_proc((subq))", subquery would not be
    traced.
  */
  sql_command_flags[SQLCOM_CALL]=      CF_REEXECUTION_FRAGILE |
                                       CF_CAN_GENERATE_ROW_EVENTS |
                                       CF_OPTIMIZER_TRACE; // (1)
  sql_command_flags[SQLCOM_EXECUTE]=   CF_CAN_GENERATE_ROW_EVENTS;

  /*
    The following admin table operations are allowed
    on log tables.
  */
  sql_command_flags[SQLCOM_REPAIR]=    CF_WRITE_LOGS_COMMAND | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_OPTIMIZE]|= CF_WRITE_LOGS_COMMAND | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_ANALYZE]=   CF_WRITE_LOGS_COMMAND | CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_CHECK]=     CF_WRITE_LOGS_COMMAND | CF_AUTO_COMMIT_TRANS;

  sql_command_flags[SQLCOM_CREATE_USER]|=       CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_DROP_USER]|=         CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_RENAME_USER]|=       CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_ALTER_USER]|=        CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_REVOKE]|=            CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_REVOKE_ALL]|=        CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_GRANT]|=             CF_AUTO_COMMIT_TRANS;

  sql_command_flags[SQLCOM_ASSIGN_TO_KEYCACHE]= CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_PRELOAD_KEYS]=       CF_AUTO_COMMIT_TRANS;

  sql_command_flags[SQLCOM_FLUSH]=              CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_RESET]=              CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_CREATE_SERVER]=      CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_ALTER_SERVER]=       CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_DROP_SERVER]=        CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_CHANGE_MASTER]=      CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_SLAVE_START]=        CF_AUTO_COMMIT_TRANS;
  sql_command_flags[SQLCOM_SLAVE_STOP]=         CF_AUTO_COMMIT_TRANS;

  /*
    The following statements can deal with temporary tables,
    so temporary tables should be pre-opened for those statements to
    simplify privilege checking.

    There are other statements that deal with temporary tables and open
    them, but which are not listed here. The thing is that the order of
    pre-opening temporary tables for those statements is somewhat custom.
  */
  sql_command_flags[SQLCOM_CREATE_TABLE]|=    CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_DROP_TABLE]|=      CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_CREATE_INDEX]|=    CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_ALTER_TABLE]|=     CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_TRUNCATE]|=        CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_LOAD]|=            CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_DROP_INDEX]|=      CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_UPDATE]|=          CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_UPDATE_MULTI]|=    CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_INSERT_SELECT]|=   CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_DELETE]|=          CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_DELETE_MULTI]|=    CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_REPLACE_SELECT]|=  CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_SELECT]|=          CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_SET_OPTION]|=      CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_DO]|=              CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_CALL]|=            CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_CHECKSUM]|=        CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_ANALYZE]|=         CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_CHECK]|=           CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_OPTIMIZE]|=        CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_REPAIR]|=          CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_PRELOAD_KEYS]|=    CF_PREOPEN_TMP_TABLES;
  sql_command_flags[SQLCOM_ASSIGN_TO_KEYCACHE]|= CF_PREOPEN_TMP_TABLES;

  /*
    DDL statements that should start with closing opened handlers.

    We use this flag only for statements for which open HANDLERs
    have to be closed before emporary tables are pre-opened.
  */
  sql_command_flags[SQLCOM_CREATE_TABLE]|=    CF_HA_CLOSE;
  sql_command_flags[SQLCOM_DROP_TABLE]|=      CF_HA_CLOSE;
  sql_command_flags[SQLCOM_ALTER_TABLE]|=     CF_HA_CLOSE;
  sql_command_flags[SQLCOM_TRUNCATE]|=        CF_HA_CLOSE;
  sql_command_flags[SQLCOM_REPAIR]|=          CF_HA_CLOSE;
  sql_command_flags[SQLCOM_OPTIMIZE]|=        CF_HA_CLOSE;
  sql_command_flags[SQLCOM_ANALYZE]|=         CF_HA_CLOSE;
  sql_command_flags[SQLCOM_CHECK]|=           CF_HA_CLOSE;
  sql_command_flags[SQLCOM_CREATE_INDEX]|=    CF_HA_CLOSE;
  sql_command_flags[SQLCOM_DROP_INDEX]|=      CF_HA_CLOSE;
  sql_command_flags[SQLCOM_PRELOAD_KEYS]|=    CF_HA_CLOSE;
  sql_command_flags[SQLCOM_ASSIGN_TO_KEYCACHE]|=  CF_HA_CLOSE;

  /*
    Mark statements that always are disallowed in read-only
    transactions. Note that according to the SQL standard,
    even temporary table DDL should be disallowed.
  */
  sql_command_flags[SQLCOM_CREATE_TABLE]|=     CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_ALTER_TABLE]|=      CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_DROP_TABLE]|=       CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_RENAME_TABLE]|=     CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_CREATE_INDEX]|=     CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_DROP_INDEX]|=       CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_CREATE_DB]|=        CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_DROP_DB]|=          CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_ALTER_DB_UPGRADE]|= CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_ALTER_DB]|=         CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_CREATE_VIEW]|=      CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_DROP_VIEW]|=        CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_CREATE_TRIGGER]|=   CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_DROP_TRIGGER]|=     CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_CREATE_EVENT]|=     CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_ALTER_EVENT]|=      CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_DROP_EVENT]|=       CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_CREATE_USER]|=      CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_RENAME_USER]|=      CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_ALTER_USER]|=       CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_DROP_USER]|=        CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_CREATE_SERVER]|=    CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_ALTER_SERVER]|=     CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_DROP_SERVER]|=      CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_CREATE_FUNCTION]|=  CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_CREATE_PROCEDURE]|= CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_CREATE_SPFUNCTION]|=CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_DROP_PROCEDURE]|=   CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_DROP_FUNCTION]|=    CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_ALTER_PROCEDURE]|=  CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_ALTER_FUNCTION]|=   CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_TRUNCATE]|=         CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_ALTER_TABLESPACE]|= CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_REPAIR]|=           CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_OPTIMIZE]|=         CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_GRANT]|=            CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_REVOKE]|=           CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_REVOKE_ALL]|=       CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_INSTALL_PLUGIN]|=   CF_DISALLOW_IN_RO_TRANS;
  sql_command_flags[SQLCOM_UNINSTALL_PLUGIN]|= CF_DISALLOW_IN_RO_TRANS;
}

bool sqlcom_can_generate_row_events(const THD *thd)
{
  return (sql_command_flags[thd->lex->sql_command] &
          CF_CAN_GENERATE_ROW_EVENTS);
}
 
bool is_update_query(enum enum_sql_command command)
{
  DBUG_ASSERT(command >= 0 && command <= SQLCOM_END);
  return (sql_command_flags[command] & CF_CHANGES_DATA) != 0;
}


bool is_explainable_query(enum enum_sql_command command)
{
  DBUG_ASSERT(command >= 0 && command <= SQLCOM_END);
  return (sql_command_flags[command] & CF_CAN_BE_EXPLAINED) != 0;
}

/**
  Check if a sql command is allowed to write to log tables.
  @param command The SQL command
  @return true if writing is allowed
*/
bool is_log_table_write_query(enum enum_sql_command command)
{
  DBUG_ASSERT(command >= 0 && command <= SQLCOM_END);
  return (sql_command_flags[command] & CF_WRITE_LOGS_COMMAND) != 0;
}

void execute_init_command(THD *thd, LEX_STRING *init_command,
                          mysql_rwlock_t *var_lock)
{
  Vio* save_vio;
  ulong save_client_capabilities;

  mysql_rwlock_rdlock(var_lock);
  if (!init_command->length)
  {
    mysql_rwlock_unlock(var_lock);
    return;
  }

  /*
    copy the value under a lock, and release the lock.
    init_command has to be executed without a lock held,
    as it may try to change itself
  */
  size_t len= init_command->length;
  char *buf= thd->strmake(init_command->str, len);
  mysql_rwlock_unlock(var_lock);

  save_client_capabilities= thd->client_capabilities;
  thd->client_capabilities|= CLIENT_MULTI_QUERIES;
  /*
    We don't need return result of execution to client side.
    To forbid this we should set thd->net.vio to 0.
  */
  save_vio= thd->net.vio;
  thd->net.vio= 0;
  dispatch_command(COM_QUERY, thd, buf, len);
  thd->client_capabilities= save_client_capabilities;
  thd->net.vio= save_vio;
}

/* This works because items are allocated with sql_alloc() */

void free_items(Item *item)
{
  Item *next;
  DBUG_ENTER("free_items");
  for (; item ; item=next)
  {
    next=item->next;
    item->delete_self();
  }
  DBUG_VOID_RETURN;
}

/**
  Perform one connection-level (COM_XXXX) command.

  @param command         type of command to perform
  @param thd             connection handle
  @param packet          data for the command, packet is always null-terminated
  @param packet_length   length of packet + 1 (to show that data is
                         null-terminated) except for COM_SLEEP, where it
                         can be zero.

  @todo
    set thd->lex->sql_command to SQLCOM_END here.
  @todo
    The following has to be changed to an 8 byte integer

  @retval
    0   ok
  @retval
    1   request of thread shutdown, i. e. if command is
        COM_QUIT/COM_SHUTDOWN
*/
bool dispatch_command(enum enum_server_command command, THD *thd,
		      char* packet, uint packet_length)
{
  bool error= 0;
  DBUG_ENTER("dispatch_command");
  DBUG_PRINT("info",("packet: '%*.s'; command: %d", packet_length, packet, command));

  DBUG_EXECUTE_IF("crash_dispatch_command_before",
                  { DBUG_PRINT("crash_dispatch_command_before", ("now"));
                    DBUG_ABORT(); });

  /* DTRACE instrumentation, begin */
  MYSQL_COMMAND_START(thd->thread_id, command,
                      &thd->security_ctx->priv_user[0],
                      (char *) thd->security_ctx->host_or_ip);

  thd->set_command(command);

  thd->clear_slow_extended();
  thd->lex->sql_command= SQLCOM_END; /* to avoid confusing VIEW detectors */
  thd->set_time();
  if (!thd->is_valid_time())
  {
    /*
     If the time has got past 2038 we need to shut this server down
     We do this by making sure every command is a shutdown and we 
     have enough privileges to shut the server down

     TODO: remove this when we have full 64 bit my_time_t support
    */
    thd->security_ctx->master_access|= SHUTDOWN_ACL;
    command= COM_SHUTDOWN;
  }

  /**
    Clear the set of flags that are expected to be cleared at the
    beginning of each command.
  */
  thd->server_status&= ~SERVER_STATUS_CLEAR_SET;

  /**
    Enforce password expiration for all RPC commands, except the
    following:

    COM_QUERY does a more fine-grained check later.
    COM_STMT_CLOSE and COM_STMT_SEND_LONG_DATA don't return anything.
    COM_PING only discloses information that the server is running,
       and that's available through other means.
    COM_QUIT should work even for expired statements.
  */
  if (unlikely(thd->security_ctx->password_expired &&
               command != COM_QUERY &&
               command != COM_STMT_CLOSE &&
               command != COM_STMT_SEND_LONG_DATA &&
               command != COM_PING &&
               command != COM_QUIT))
  {
    my_error(ER_MUST_CHANGE_PASSWORD, MYF(0));
    goto done;
  }

  switch (command) {
  case COM_INIT_DB:
  case COM_CHANGE_USER:
  case COM_STMT_EXECUTE:
  case COM_STMT_FETCH:
  case COM_STMT_SEND_LONG_DATA:
  case COM_STMT_PREPARE:
  case COM_STMT_CLOSE:
  case COM_STMT_RESET: {
	    my_message(ER_UNKNOWN_COM_ERROR, ER(ER_UNKNOWN_COM_ERROR), MYF(0));
	    break;
  }
  case COM_QUERY:
  {
    if (alloc_query(thd, packet, packet_length))
      break;					// fatal error is set
    MYSQL_QUERY_START(thd->query(), thd->thread_id,
                      (char *) (thd->db ? thd->db : ""),
                      &thd->security_ctx->priv_user[0],
                      (char *) thd->security_ctx->host_or_ip);
    char *packet_end= thd->query() + thd->query_length();

    DBUG_PRINT("query",("%-.4096s",thd->query()));

    MYSQL_SET_STATEMENT_TEXT(thd->m_statement_psi, thd->query(), thd->query_length());

    Parser_state parser_state;
    if (parser_state.init(thd, thd->query(), thd->query_length()))
      break;

    mysql_parse(thd, thd->query(), thd->query_length(), &parser_state);

//    while (!thd->killed && (parser_state.m_lip.found_semicolon != NULL) &&
//           ! thd->is_error())
    while (FALSE)
    {
      /*
        Multiple queries exits, execute them individually
      */
      char *beginning_of_next_stmt= (char*) parser_state.m_lip.found_semicolon;

      /* Finalize server status flags after executing a statement. */
      thd->update_server_status();

      ulong length= (ulong)(packet_end - beginning_of_next_stmt);


      /* Remove garbage at start of query */
      while (length > 0 && my_isspace(thd->charset(), *beginning_of_next_stmt))
      {
        beginning_of_next_stmt++;
        length--;
      }

/* PSI end */
      MYSQL_END_STATEMENT(thd->m_statement_psi, thd->get_stmt_da());

/* DTRACE end */
      if (MYSQL_QUERY_DONE_ENABLED())
      {
        MYSQL_QUERY_DONE(thd->is_error());
      }

      MYSQL_SET_STATEMENT_TEXT(thd->m_statement_psi, beginning_of_next_stmt, length);

      thd->set_query_and_id(beginning_of_next_stmt, length,
                            thd->charset(), 0);
      /*
        Count each statement from the client.
      */
      thd->set_time(); /* Reset the query start time. */
      parser_state.reset(beginning_of_next_stmt, length);
      /* TODO: set thd->lex->sql_command to SQLCOM_END here */
      mysql_parse(thd, beginning_of_next_stmt, length, &parser_state);
    }

    DBUG_PRINT("info",("query ready"));
    break;
  }
  case COM_FIELD_LIST:				// This isn't actually needed
  case COM_REFRESH:
  case COM_SHUTDOWN:
  case COM_STATISTICS:
  case COM_PING:
  case COM_PROCESS_INFO:
  case COM_DEBUG:
  case COM_SLEEP:
  case COM_CONNECT:				// Impossible here
  case COM_TIME:				// Impossible from client
  case COM_DELAYED_INSERT:
  case COM_END:
  default:
    my_message(ER_UNKNOWN_COM_ERROR, ER(ER_UNKNOWN_COM_ERROR), MYF(0));
    break;
  }

done:

  /* Finalize server status flags after executing a command. */
  thd->update_server_status();

  if (thd->killed == THD::KILL_QUERY ||
      thd->killed == THD::KILL_TIMEOUT ||
      thd->killed == THD::KILL_BAD_DATA)
  {
    thd->killed= THD::NOT_KILLED;
    thd->mysys_var->abort= 0;
  }

  thd->reset_query();
  thd->set_command(COM_SLEEP);

  /* Performance Schema Interface instrumentation, end */
  MYSQL_END_STATEMENT(thd->m_statement_psi, thd->get_stmt_da());

  /* DTRACE instrumentation, end */
  if (MYSQL_QUERY_DONE_ENABLED() || MYSQL_COMMAND_DONE_ENABLED())
  {
    int res __attribute__((unused));
    res= (int) thd->is_error();
    if (command == COM_QUERY)
    {
      MYSQL_QUERY_DONE(res);
    }
    MYSQL_COMMAND_DONE(res);
  }

  DBUG_RETURN(error);
}

/*
  Read query from packet and store in thd->query.
  Used in COM_QUERY and COM_STMT_PREPARE.

    Sets the following THD variables:
  - query
  - query_length

  @retval
    FALSE ok
  @retval
    TRUE  error;  In this case thd->fatal_error is set
*/

bool alloc_query(THD *thd, const char *packet, uint packet_length)
{
  char *query;
  /* Remove garbage at start and end of query */
  while (packet_length > 0 && my_isspace(thd->charset(), packet[0]))
  {
    packet++;
    packet_length--;
  }
  const char *pos= packet + packet_length;     // Point at end null
  while (packet_length > 0 &&
	 (pos[-1] == ';' || my_isspace(thd->charset() ,pos[-1])))
  {
    pos--;
    packet_length--;
  }
  /* We must allocate some extra memory for query cache 

    The query buffer layout is:
       buffer :==
            <statement>   The input statement(s)
            '\0'          Terminating null char  (1 byte)
            <length>      Length of following current database name (size_t)
            <db_name>     Name of current database
            <flags>       Flags struct
  */
  if (! (query= (char*) thd->memdup_w_gap(packet,
                                          packet_length,
                                          1 + sizeof(size_t) + thd->db_length)))
      return TRUE;
  query[packet_length]= '\0';
  /*
    Space to hold the name of the current database is allocated.  We
    also store this length, in case current database is changed during
    execution.  We might need to reallocate the 'query' buffer
  */
  char *len_pos = (query + packet_length + 1);
  memcpy(len_pos, (char *) &thd->db_length, sizeof(size_t));
    
  thd->set_query(query, packet_length);
  thd->rewritten_query.free();                 // free here lest PS break

  /* Reclaim some memory */
  thd->convert_buffer.shrink(thd->variables.net_buffer_length);

  return FALSE;
}

/****************************************************************************
	Check stack size; Send error if there isn't enough stack to continue
****************************************************************************/


#if STACK_DIRECTION < 0
#define used_stack(A,B) (long) (A - B)
#else
#define used_stack(A,B) (long) (B - A)
#endif

#ifndef DBUG_OFF
long max_stack_used;
#endif

/**
  @note
  Note: The 'buf' parameter is necessary, even if it is unused here.
  - fix_fields functions has a "dummy" buffer large enough for the
    corresponding exec. (Thus we only have to check in fix_fields.)
  - Passing to check_stack_overrun() prevents the compiler from removing it.
*/
bool check_stack_overrun(THD *thd, long margin,
			 uchar *buf __attribute__((unused)))
{
  long stack_used;
  DBUG_ASSERT(thd == current_thd);
  if ((stack_used=used_stack(thd->thread_stack,(char*) &stack_used)) >=
      (long) (my_thread_stack_size - margin))
  {
    /*
      Do not use stack for the message buffer to ensure correct
      behaviour in cases we have close to no stack left.
    */
    char* ebuff= new (std::nothrow) char[MYSQL_ERRMSG_SIZE];
    if (ebuff) {
      my_snprintf(ebuff, MYSQL_ERRMSG_SIZE, ER(ER_STACK_OVERRUN_NEED_MORE),
                  stack_used, my_thread_stack_size, margin);
      my_message(ER_STACK_OVERRUN_NEED_MORE, ebuff, MYF(ME_FATALERROR));
      delete [] ebuff;
    }
    return 1;
  }
#ifndef DBUG_OFF
  max_stack_used= max(max_stack_used, stack_used);
#endif
  return 0;
}


#define MY_YACC_INIT 1000			// Start with big alloc
#define MY_YACC_MAX  32000			// Because of 'short'

bool my_yyoverflow(short **yyss, YYSTYPE **yyvs, ulong *yystacksize)
{
  Yacc_state *state= & current_thd->m_parser_state->m_yacc;
  ulong old_info=0;
  DBUG_ASSERT(state);
  if ((uint) *yystacksize >= MY_YACC_MAX)
    return 1;
  if (!state->yacc_yyvs)
    old_info= *yystacksize;
  *yystacksize= set_zone((*yystacksize)*2,MY_YACC_INIT,MY_YACC_MAX);
  if (!(state->yacc_yyvs= (uchar*)
        my_realloc(state->yacc_yyvs,
                   *yystacksize*sizeof(**yyvs),
                   MYF(MY_ALLOW_ZERO_PTR | MY_FREE_ON_ERROR))) ||
      !(state->yacc_yyss= (uchar*)
        my_realloc(state->yacc_yyss,
                   *yystacksize*sizeof(**yyss),
                   MYF(MY_ALLOW_ZERO_PTR | MY_FREE_ON_ERROR))))
    return 1;
  if (old_info)
  {
    /*
      Only copy the old stack on the first call to my_yyoverflow(),
      when replacing a static stack (YYINITDEPTH) by a dynamic stack.
      For subsequent calls, my_realloc already did preserve the old stack.
    */
    memcpy(state->yacc_yyss, *yyss, old_info*sizeof(**yyss));
    memcpy(state->yacc_yyvs, *yyvs, old_info*sizeof(**yyvs));
  }
  *yyss= (short*) state->yacc_yyss;
  *yyvs= (YYSTYPE*) state->yacc_yyvs;
  return 0;
}


/**
  Reset the part of THD responsible for the state of command
  processing.

  This needs to be called before execution of every statement
  (prepared or conventional).  It is not called by substatements of
  routines.

  @todo Remove mysql_reset_thd_for_next_command and only use the
  member function.

  @todo Call it after we use THD for queries, not before.
*/
void mysql_reset_thd_for_next_command(THD *thd)
{
  thd->reset_for_next_command();
}

void THD::reset_for_next_command()
{
  // TODO: Why on earth is this here?! We should probably fix this
  // function and move it to the proper file. /Matz
  THD *thd= this;
  DBUG_ENTER("mysql_reset_thd_for_next_command");
  DBUG_ASSERT(! thd->in_sub_stmt);
  thd->free_list= 0;
  thd->select_number= 1;
  /*
    Those two lines below are theoretically unneeded as
    THD::cleanup_after_query() should take care of this already.
  */
  thd->auto_inc_intervals_in_cur_stmt_for_binlog.empty();
  thd->stmt_depends_on_first_successful_insert_id_in_prev_stmt= 0;

  thd->query_start_used= thd->query_start_usec_used= 0;
  thd->is_fatal_error= thd->time_zone_used= 0;
  /*
    Clear the status flag that are expected to be cleared at the
    beginning of each SQL statement.
  */
  thd->server_status&= ~SERVER_STATUS_CLEAR_SET;

  DBUG_ASSERT(thd->security_ctx== &thd->main_security_ctx);
  thd->thread_specific_used= FALSE;

  thd->clear_error();
  thd->get_stmt_da()->reset_diagnostics_area();
  thd->get_stmt_da()->reset_for_next_command();
  thd->rand_used= 0;

  thd->clear_slow_extended();

  thd->commit_error= THD::CE_NONE;
  thd->durability_property= HA_REGULAR_DURABILITY;

  DBUG_VOID_RETURN;
}


/**
  Resets the lex->current_select object.
  @note It is assumed that lex->current_select != NULL

  This function is a wrapper around select_lex->init_select() with an added
  check for the special situation when using INTO OUTFILE and LOAD DATA.
*/

void
mysql_init_select(LEX *lex)
{
  SELECT_LEX *select_lex= lex->current_select;
  select_lex->init_select();
  lex->wild= 0;
  if (select_lex == &lex->select_lex)
  {
    DBUG_ASSERT(lex->result == 0);
    lex->exchange= 0;
  }
}


/**
  Used to allocate a new SELECT_LEX object on the current thd mem_root and
  link it into the relevant lists.

  This function is always followed by mysql_init_select.

  @see mysql_init_select

  @retval TRUE An error occurred
  @retval FALSE The new SELECT_LEX was successfully allocated.
*/

bool
mysql_new_select(LEX *lex, bool move_down)
{
  SELECT_LEX *select_lex;
  THD *thd= lex->thd;
  Name_resolution_context *outer_context= lex->current_context();
  DBUG_ENTER("mysql_new_select");

  if (!(select_lex= new (thd->mem_root) SELECT_LEX()))
    DBUG_RETURN(1);
  select_lex->select_number= ++thd->select_number;
  select_lex->parent_lex= lex; /* Used in init_query. */
  select_lex->init_query();
  select_lex->init_select();
  lex->nest_level++;
  if (lex->nest_level > (int) MAX_SELECT_NESTING)
  {
    my_error(ER_TOO_HIGH_LEVEL_OF_NESTING_FOR_SELECT, MYF(0));
    DBUG_RETURN(1);
  }
  select_lex->nest_level= lex->nest_level;
  if (move_down)
  {
    SELECT_LEX_UNIT *unit;
    lex->subqueries= TRUE;
    /* first select_lex of subselect or derived table */
    if (!(unit= new (thd->mem_root) SELECT_LEX_UNIT()))
      DBUG_RETURN(1);

    unit->init_query();
    unit->init_select();
    unit->thd= thd;
    unit->include_down(lex->current_select);
    unit->link_next= 0;
    unit->link_prev= 0;
    select_lex->include_down(unit);
    /*
      By default we assume that it is usual subselect and we have outer name
      resolution context, if no we will assign it to 0 later
    */
    if (select_lex->outer_select()->parsing_place == IN_ON)
      /*
        This subquery is part of an ON clause, so we need to link the
        name resolution context for this subquery with the ON context.

        @todo outer_context is not the same as
        &select_lex->outer_select()->context in one case:
        (SELECT 1 as a) UNION (SELECT 2) ORDER BY (SELECT a);
        When we create the select_lex for the subquery in ORDER BY,
        1) outer_context is the context of the second SELECT of the
        UNION
        2) &select_lex->outer_select() is the fake select_lex, which context
        is the one of the first SELECT of the UNION (see
        st_select_lex_unit::add_fake_select_lex()).
        2) is the correct context, per the documentation. 1) is not, and using
        it leads to a resolving error for the query above.
        We should fix 1) and then use it unconditionally here.
      */
      select_lex->context.outer_context= outer_context;
    else
      select_lex->context.outer_context= &select_lex->outer_select()->context;
  }
  else
  {
    if (lex->current_select->order_list.first && !lex->current_select->braces)
    {
      my_error(ER_WRONG_USAGE, MYF(0), "UNION", "ORDER BY");
      DBUG_RETURN(1);
    }
    select_lex->include_neighbour(lex->current_select);
    SELECT_LEX_UNIT *unit= select_lex->master_unit();                              
    if (!unit->fake_select_lex && unit->add_fake_select_lex(lex->thd))
      DBUG_RETURN(1);
    select_lex->context.outer_context= 
                unit->first_select()->context.outer_context;
  }

  select_lex->master_unit()->global_parameters= select_lex;
  select_lex->include_global((st_select_lex_node**)&lex->all_selects_list);
  lex->current_select= select_lex;
  /*
    in subquery is SELECT query and we allow resolution of names in SELECT
    list
  */
  select_lex->context.resolve_in_select_list= TRUE;
  DBUG_RETURN(0);
}

/**
  Create a select to return the same output as 'SELECT @@var_name'.

  Used for SHOW COUNT(*) [ WARNINGS | ERROR].

  This will crash with a core dump if the variable doesn't exists.

  @param var_name		Variable name
*/

void create_select_for_variable(const char *var_name)
{
  THD *thd;
  LEX *lex;
  LEX_STRING tmp, null_lex_string;
  Item *var;
  char buff[MAX_SYS_VAR_LENGTH*2+4+8], *end;
  DBUG_ENTER("create_select_for_variable");

  thd= current_thd;
  lex= thd->lex;
  mysql_init_select(lex);
  lex->sql_command= SQLCOM_SELECT;
  tmp.str= (char*) var_name;
  tmp.length=strlen(var_name);
  memset(&null_lex_string, 0, sizeof(null_lex_string));
  /*
    We set the name of Item to @@session.var_name because that then is used
    as the column name in the output.
  */
  if ((var= get_system_var(thd, OPT_SESSION, tmp, null_lex_string)))
  {
    end= strxmov(buff, "@@session.", var_name, NullS);
    var->item_name.copy(buff, end - buff);
    add_item_to_list(thd, var);
  }
  DBUG_VOID_RETURN;
}


void mysql_init_multi_delete(LEX *lex)
{
  lex->sql_command=  SQLCOM_DELETE_MULTI;
  mysql_init_select(lex);
  lex->select_lex.select_limit= 0;
  lex->unit.select_limit_cnt= HA_POS_ERROR;
  lex->select_lex.table_list.save_and_clear(&lex->auxiliary_table_list);
  lex->query_tables= 0;
  lex->query_tables_last= &lex->query_tables;
}


/*
  When you modify mysql_parse(), you may need to mofify
  mysql_test_parse_for_slave() in this same file.
*/

/**
  Parse a query.

  @param       thd     Current thread
  @param       rawbuf  Begining of the query text
  @param       length  Length of the query text
  @param[out]  found_semicolon For multi queries, position of the character of
                               the next query in the query text.
*/

void mysql_parse(THD *thd, char *rawbuf, uint length,
                 Parser_state *parser_state)
{
  int error __attribute__((unused));
  DBUG_ENTER("mysql_parse");

  DBUG_EXECUTE_IF("parser_debug", turn_parser_debug_on(););

  /*
    Warning.
    The purpose of query_cache_send_result_to_client() is to lookup the
    query in the query cache first, to avoid parsing and executing it.
    So, the natural implementation would be to:
    - first, call query_cache_send_result_to_client,
    - second, if caching failed, initialise the lexical and syntactic parser.
    The problem is that the query cache depends on a clean initialization
    of (among others) lex->safe_to_cache_query and thd->server_status,
    which are reset respectively in
    - lex_start()
    - mysql_reset_thd_for_next_command()
    So, initializing the lexical analyser *before* using the query cache
    is required for the cache to work properly.
    FIXME: cleanup the dependencies in the code to simplify this.
  */
  lex_start(thd);
  mysql_reset_thd_for_next_command(thd);

  //if (query_cache_send_result_to_client(thd, rawbuf, length) <= 0)
  {
    LEX *lex= thd->lex;

    bool err= parse_sql(thd, parser_state, NULL);

    const char *found_semicolon= parser_state->m_lip.found_semicolon;

    if (!err)
    {
      {
	if (! thd->is_error())
	{
          /*
            Binlog logs a string starting from thd->query and having length
            thd->query_length; so we set thd->query_length correctly (to not
            log several statements in one event, when we executed only first).
            We set it to not see the ';' (otherwise it would get into binlog
            and Query_log_event::print() would give ';;' output).
            This also helps display only the current query in SHOW
            PROCESSLIST.
            Note that we don't need LOCK_thread_count to modify query_length.
          */
          if (found_semicolon && (ulong) (found_semicolon - thd->query()))
            thd->set_query_inner(thd->query(),
                                 (uint32) (found_semicolon -
                                           thd->query() - 1),
                                 thd->charset());
          /* Actually execute the query */
          if (found_semicolon)
          {
            lex->safe_to_cache_query= 0;
            thd->server_status|= SERVER_MORE_RESULTS_EXISTS;
          }
          lex->set_trg_event_type_for_tables();
        }
      }
    }

//    thd->end_statement();
//    thd->cleanup_after_query();
//    DBUG_ASSERT(thd->change_list.is_empty());
  }

  DBUG_VOID_RETURN;
}



/**
  Store field definition for create.

  @return
    Return 0 if ok
*/

bool add_field_to_list(THD *thd, LEX_STRING *field_name, enum_field_types type,
		       char *length, char *decimals,
		       uint type_modifier,
		       Item *default_value, Item *on_update_value,
                       LEX_STRING *comment,
		       char *change,
                       List<String> *interval_list, const CHARSET_INFO *cs,
		       uint uint_geom_type)
{
  register Create_field *new_field;
  LEX  *lex= thd->lex;
  uint8 datetime_precision= decimals ? atoi(decimals) : 0;
  DBUG_ENTER("add_field_to_list");

  if (check_string_char_length(field_name, "", NAME_CHAR_LEN,
                               system_charset_info, 1))
  {
    my_error(ER_TOO_LONG_IDENT, MYF(0), field_name->str); /* purecov: inspected */
    DBUG_RETURN(1);				/* purecov: inspected */
  }
  if (type_modifier & PRI_KEY_FLAG)
  {
    Key *key;
    lex->col_list.push_back(new Key_part_spec(*field_name, 0));
    key= new Key(Key::PRIMARY, null_lex_str,
                      &default_key_create_info,
                      0, lex->col_list);
    lex->alter_info.key_list.push_back(key);
    lex->col_list.empty();
  }
  if (type_modifier & (UNIQUE_FLAG | UNIQUE_KEY_FLAG | CLUSTERING_FLAG))
  {
    Key::Keytype keytype;
    if (type_modifier & (UNIQUE_FLAG | UNIQUE_KEY_FLAG))
      keytype= Key::UNIQUE;
    else
      keytype= Key::MULTIPLE;
    if (type_modifier & CLUSTERING_FLAG)
      keytype= (enum Key::Keytype)(keytype | Key::CLUSTERING);
    DBUG_ASSERT(keytype != Key::MULTIPLE);

    lex->col_list.push_back(new Key_part_spec(*field_name, 0));
    Key *key= new Key(keytype, null_lex_str, &default_key_create_info, 0,
                      lex->col_list);
    lex->alter_info.key_list.push_back(key);
    lex->col_list.empty();
  }

  if (default_value)
  {
    /* 
      Default value should be literal => basic constants =>
      no need fix_fields()

      We allow only CURRENT_TIMESTAMP as function default for the TIMESTAMP or
      DATETIME types.
    */
    if (default_value->type() == Item::FUNC_ITEM && 
        (static_cast<Item_func*>(default_value)->functype() !=
         Item_func::NOW_FUNC ||
         (!real_type_with_now_as_default(type)) ||
         default_value->decimals != datetime_precision))
    {
      my_error(ER_INVALID_DEFAULT, MYF(0), field_name->str);
      DBUG_RETURN(1);
    }
    else if (default_value->type() == Item::NULL_ITEM)
    {
      default_value= 0;
      if ((type_modifier & (NOT_NULL_FLAG | AUTO_INCREMENT_FLAG)) ==
	  NOT_NULL_FLAG)
      {
	my_error(ER_INVALID_DEFAULT, MYF(0), field_name->str);
	DBUG_RETURN(1);
      }
    }
    else if (type_modifier & AUTO_INCREMENT_FLAG)
    {
      my_error(ER_INVALID_DEFAULT, MYF(0), field_name->str);
      DBUG_RETURN(1);
    }
  }

  if (on_update_value &&
      (!real_type_with_now_on_update(type) ||
       on_update_value->decimals != datetime_precision))
  {
    my_error(ER_INVALID_ON_UPDATE, MYF(0), field_name->str);
    DBUG_RETURN(1);
  }

  if (!(new_field= new Create_field()) ||
      new_field->init(thd, field_name->str, type, length, decimals, type_modifier,
                      default_value, on_update_value, comment, change,
                      interval_list, cs, uint_geom_type))
    DBUG_RETURN(1);

  lex->alter_info.create_list.push_back(new_field);
  lex->last_field=new_field;
  DBUG_RETURN(0);
}


/** Store position for column in ALTER TABLE .. ADD column. */

void store_position_for_column(const char *name)
{
  current_thd->lex->last_field->after=(char*) (name);
}


/**
  save order by and tables in own lists.
*/

bool add_to_list(THD *thd, SQL_I_List<ORDER> &list, Item *item,bool asc)
{
  ORDER *order;
  DBUG_ENTER("add_to_list");
  if (!(order = (ORDER *) thd->alloc(sizeof(ORDER))))
    DBUG_RETURN(1);
  order->item_ptr= item;
  order->item= &order->item_ptr;
  order->direction= (asc ? ORDER::ORDER_ASC : ORDER::ORDER_DESC);
  order->used_alias= false;
  order->used=0;
  order->counter_used= 0;
  list.link_in_list(order, &order->next);
  DBUG_RETURN(0);
}


/**
  Add a table to list of used tables.

  @param table		Table to add
  @param alias		alias for table (or null if no alias)
  @param table_options	A set of the following bits:
                         - TL_OPTION_UPDATING : Table will be updated
                         - TL_OPTION_FORCE_INDEX : Force usage of index
                         - TL_OPTION_ALIAS : an alias in multi table DELETE
  @param lock_type	How table should be locked
  @param mdl_type       Type of metadata lock to acquire on the table.
  @param use_index	List of indexed used in USE INDEX
  @param ignore_index	List of indexed used in IGNORE INDEX

  @retval
      0		Error
  @retval
    \#	Pointer to TABLE_LIST element added to the total table list
*/

TABLE_LIST *st_select_lex::add_table_to_list(THD *thd,
					     Table_ident *table,
					     LEX_STRING *alias,
					     ulong table_options,
					     List<Index_hint> *index_hints_arg,
                                             List<String> *partition_names,
                                             LEX_STRING *option)
{
  register TABLE_LIST *ptr;
  TABLE_LIST *previous_table_ref; /* The table preceding the current one. */
  char *alias_str;
  LEX *lex= thd->lex;
  DBUG_ENTER("add_table_to_list");
  LINT_INIT(previous_table_ref);

  if (!table)
    DBUG_RETURN(0);				// End of memory
  alias_str= alias ? alias->str : table->table.str;
  if (!MY_TEST(table_options & TL_OPTION_ALIAS))
  {
    enum_ident_name_check ident_check_status=
      check_table_name(table->table.str, table->table.length, FALSE);
    if (ident_check_status == IDENT_NAME_WRONG)
    {
      my_error(ER_WRONG_TABLE_NAME, MYF(0), table->table.str);
      DBUG_RETURN(0);
    }
    else if (ident_check_status == IDENT_NAME_TOO_LONG)
    {
      my_error(ER_TOO_LONG_IDENT, MYF(0), table->table.str);
      DBUG_RETURN(0);
    }
  }
  if (table->is_derived_table() == FALSE && table->db.str &&
      (check_and_convert_db_name(&table->db, FALSE) != IDENT_NAME_OK))
    DBUG_RETURN(0);

  if (!alias)					/* Alias is case sensitive */
  {
    if (table->sel)
    {
      my_message(ER_DERIVED_MUST_HAVE_ALIAS,
                 ER(ER_DERIVED_MUST_HAVE_ALIAS), MYF(0));
      DBUG_RETURN(0);
    }
    if (!(alias_str= (char*) thd->memdup(alias_str,table->table.length+1)))
      DBUG_RETURN(0);
  }
  if (!(ptr = (TABLE_LIST *) thd->calloc(sizeof(TABLE_LIST))))
    DBUG_RETURN(0);				/* purecov: inspected */
  if (table->db.str)
  {
    ptr->is_fqtn= TRUE;
    ptr->db= table->db.str;
    ptr->db_length= table->db.length;
  }
  else if (lex->copy_db_to(&ptr->db, &ptr->db_length))
    DBUG_RETURN(0);
  else
    ptr->is_fqtn= FALSE;

  ptr->alias= alias_str;
  ptr->is_alias= alias ? TRUE : FALSE;
  if (lower_case_table_names && table->table.length)
    table->table.length= my_casedn_str(files_charset_info, table->table.str);
  ptr->table_name=table->table.str;
  ptr->table_name_length=table->table.length;
  ptr->updating=    MY_TEST(table_options & TL_OPTION_UPDATING);
  /* TODO: remove TL_OPTION_FORCE_INDEX as it looks like it's not used */
  ptr->force_index= MY_TEST(table_options & TL_OPTION_FORCE_INDEX);
  ptr->ignore_leaves= MY_TEST(table_options & TL_OPTION_IGNORE_LEAVES);
  ptr->derived=	    table->sel;
  if (!ptr->derived && is_infoschema_db(ptr->db, ptr->db_length))
  {
    ST_SCHEMA_TABLE *schema_table;
    if (ptr->updating &&
        /* Special cases which are processed by commands itself */
        lex->sql_command != SQLCOM_CHECK &&
        lex->sql_command != SQLCOM_CHECKSUM)
    {
      my_error(ER_DBACCESS_DENIED_ERROR, MYF(0),
               thd->security_ctx->priv_user,
               thd->security_ctx->priv_host,
               INFORMATION_SCHEMA_NAME.str);
      DBUG_RETURN(0);
    }
    schema_table= find_schema_table(thd, ptr->table_name);
    if (!schema_table ||
        (schema_table->hidden && 
         ((sql_command_flags[lex->sql_command] & CF_STATUS_COMMAND) == 0 || 
          /*
            this check is used for show columns|keys from I_S hidden table
          */
          lex->sql_command == SQLCOM_SHOW_FIELDS ||
          lex->sql_command == SQLCOM_SHOW_KEYS)))
    {
      my_error(ER_UNKNOWN_TABLE, MYF(0),
               ptr->table_name, INFORMATION_SCHEMA_NAME.str);
      DBUG_RETURN(0);
    }
    ptr->schema_table_name= ptr->table_name;
    ptr->schema_table= schema_table;
  }
  ptr->select_lex=  lex->current_select;
  ptr->cacheable_table= 1;
  ptr->index_hints= index_hints_arg;
  ptr->option= option ? option->str : 0;
  /* check that used name is unique */
  /* Store the table reference preceding the current one. */
  if (table_list.elements > 0)
  {
    /*
      table_list.next points to the last inserted TABLE_LIST->next_local'
      element
      We don't use the offsetof() macro here to avoid warnings from gcc
    */
    previous_table_ref= (TABLE_LIST*) ((char*) table_list.next -
                                       ((char*) &(ptr->next_local) -
                                        (char*) ptr));
    /*
      Set next_name_resolution_table of the previous table reference to point
      to the current table reference. In effect the list
      TABLE_LIST::next_name_resolution_table coincides with
      TABLE_LIST::next_local. Later this may be changed in
      store_top_level_join_columns() for NATURAL/USING joins.
    */
    previous_table_ref->next_name_resolution_table= ptr;
  }

  /*
    Link the current table reference in a local list (list for current select).
    Notice that as a side effect here we set the next_local field of the
    previous table reference to 'ptr'. Here we also add one element to the
    list 'table_list'.
  */
  table_list.link_in_list(ptr, &ptr->next_local);
  ptr->next_name_resolution_table= NULL;
#ifdef WITH_PARTITION_STORAGE_ENGINE
  ptr->partition_names= partition_names;
#endif /* WITH_PARTITION_STORAGE_ENGINE */
  /* Link table in global list (all used tables) */
  lex->add_to_query_tables(ptr);

  if (table->is_derived_table())
  {
    ptr->effective_algorithm= DERIVED_ALGORITHM_TMPTABLE;
  }
  DBUG_RETURN(ptr);
}


/**
  Initialize a new table list for a nested join.

    The function initializes a structure of the TABLE_LIST type
    for a nested join. It sets up its nested join list as empty.
    The created structure is added to the front of the current
    join list in the st_select_lex object. Then the function
    changes the current nest level for joins to refer to the newly
    created empty list after having saved the info on the old level
    in the initialized structure.

  @param thd         current thread

  @retval
    0   if success
  @retval
    1   otherwise
*/

bool st_select_lex::init_nested_join(THD *thd)
{
  DBUG_ENTER("init_nested_join");

  TABLE_LIST *const ptr=
    TABLE_LIST::new_nested_join(thd->mem_root, "(nested_join)",
                                embedding, join_list, this);
  if (ptr == NULL)
    DBUG_RETURN(true);

  join_list->push_front(ptr);
  embedding= ptr;
  join_list= &ptr->nested_join->join_list;

  DBUG_RETURN(false);
}


/**
  End a nested join table list.

    The function returns to the previous join nest level.
    If the current level contains only one member, the function
    moves it one level up, eliminating the nest.

  @param thd         current thread

  @return
    - Pointer to TABLE_LIST element added to the total table list, if success
    - 0, otherwise
*/

TABLE_LIST *st_select_lex::end_nested_join(THD *thd)
{
  TABLE_LIST *ptr;
  NESTED_JOIN *nested_join;
  DBUG_ENTER("end_nested_join");

  DBUG_ASSERT(embedding);
  ptr= embedding;
  join_list= ptr->join_list;
  embedding= ptr->embedding;
  nested_join= ptr->nested_join;
  if (nested_join->join_list.elements == 1)
  {
    TABLE_LIST *embedded= nested_join->join_list.head();
    join_list->pop();
    embedded->join_list= join_list;
    embedded->embedding= embedding;
    join_list->push_front(embedded);
    ptr= embedded;
  }
  else if (nested_join->join_list.elements == 0)
  {
    join_list->pop();
    ptr= 0;                                     // return value
  }
  DBUG_RETURN(ptr);
}


/**
  Nest last join operation.

    The function nest last join operation as if it was enclosed in braces.

  @param thd         current thread

  @retval
    0  Error
  @retval
    \#  Pointer to TABLE_LIST element created for the new nested join
*/

TABLE_LIST *st_select_lex::nest_last_join(THD *thd)
{
  DBUG_ENTER("nest_last_join");

  TABLE_LIST *const ptr=
    TABLE_LIST::new_nested_join(thd->mem_root, "(nest_last_join)",
                                embedding, join_list, this);
  if (ptr == NULL)
    DBUG_RETURN(NULL);

  List<TABLE_LIST> *const embedded_list= &ptr->nested_join->join_list;

  for (uint i=0; i < 2; i++)
  {
    TABLE_LIST *table= join_list->pop();
    table->join_list= embedded_list;
    table->embedding= ptr;
    embedded_list->push_back(table);
    if (table->natural_join)
    {
      ptr->is_natural_join= TRUE;
      /*
        If this is a JOIN ... USING, move the list of joined fields to the
        table reference that describes the join.
      */
      if (prev_join_using)
        ptr->join_using_fields= prev_join_using;
    }
  }
  join_list->push_front(ptr);

  DBUG_RETURN(ptr);
}


/**
  Add a table to the current join list.

    The function puts a table in front of the current join list
    of st_select_lex object.
    Thus, joined tables are put into this list in the reverse order
    (the most outer join operation follows first).

  @param table       the table to add

  @return
    None
*/

void st_select_lex::add_joined_table(TABLE_LIST *table)
{
  DBUG_ENTER("add_joined_table");
  join_list->push_front(table);
  table->join_list= join_list;
  table->embedding= embedding;
  DBUG_VOID_RETURN;
}


/**
  Convert a right join into equivalent left join.

    The function takes the current join list t[0],t[1] ... and
    effectively converts it into the list t[1],t[0] ...
    Although the outer_join flag for the new nested table contains
    JOIN_TYPE_RIGHT, it will be handled as the inner table of a left join
    operation.

  EXAMPLES
  @verbatim
    SELECT * FROM t1 RIGHT JOIN t2 ON on_expr =>
      SELECT * FROM t2 LEFT JOIN t1 ON on_expr

    SELECT * FROM t1,t2 RIGHT JOIN t3 ON on_expr =>
      SELECT * FROM t1,t3 LEFT JOIN t2 ON on_expr

    SELECT * FROM t1,t2 RIGHT JOIN (t3,t4) ON on_expr =>
      SELECT * FROM t1,(t3,t4) LEFT JOIN t2 ON on_expr

    SELECT * FROM t1 LEFT JOIN t2 ON on_expr1 RIGHT JOIN t3  ON on_expr2 =>
      SELECT * FROM t3 LEFT JOIN (t1 LEFT JOIN t2 ON on_expr2) ON on_expr1
   @endverbatim

  @param thd         current thread

  @return
    - Pointer to the table representing the inner table, if success
    - 0, otherwise
*/

TABLE_LIST *st_select_lex::convert_right_join()
{
  TABLE_LIST *tab2= join_list->pop();
  TABLE_LIST *tab1= join_list->pop();
  DBUG_ENTER("convert_right_join");

  join_list->push_front(tab2);
  join_list->push_front(tab1);
  tab1->outer_join|= JOIN_TYPE_RIGHT;

  DBUG_RETURN(tab1);
}


/**
  Create a fake SELECT_LEX for a unit.

    The method create a fake SELECT_LEX object for a unit.
    This object is created for any union construct containing a union
    operation and also for any single select union construct of the form
    @verbatim
    (SELECT ... ORDER BY order_list [LIMIT n]) ORDER BY ... 
    @endvarbatim
    or of the form
    @varbatim
    (SELECT ... ORDER BY LIMIT n) ORDER BY ...
    @endvarbatim
  
  @param thd_arg		   thread handle

  @note
    The object is used to retrieve rows from the temporary table
    where the result on the union is obtained.

  @retval
    1     on failure to create the object
  @retval
    0     on success
*/

bool st_select_lex_unit::add_fake_select_lex(THD *thd_arg)
{
  SELECT_LEX *first_sl= first_select();
  DBUG_ENTER("add_fake_select_lex");
  DBUG_ASSERT(!fake_select_lex);

  if (!(fake_select_lex= new (thd_arg->mem_root) SELECT_LEX()))
      DBUG_RETURN(1);
  fake_select_lex->include_standalone(this, 
                                      (SELECT_LEX_NODE**)&fake_select_lex);
  fake_select_lex->select_number= INT_MAX;
  fake_select_lex->parent_lex= thd_arg->lex; /* Used in init_query. */
  fake_select_lex->make_empty_select();
  fake_select_lex->linkage= GLOBAL_OPTIONS_TYPE;
  fake_select_lex->select_limit= 0;

  fake_select_lex->context.outer_context=first_sl->context.outer_context;
  /* allow item list resolving in fake select for ORDER BY */
  fake_select_lex->context.resolve_in_select_list= TRUE;
  fake_select_lex->context.select_lex= fake_select_lex;

  if (!is_union())
  {
    /* 
      This works only for 
      (SELECT ... ORDER BY list [LIMIT n]) ORDER BY order_list [LIMIT m],
      (SELECT ... LIMIT n) ORDER BY order_list [LIMIT m]
      just before the parser starts processing order_list
    */ 
    global_parameters= fake_select_lex;
    fake_select_lex->no_table_names_allowed= 1;
    thd_arg->lex->current_select= fake_select_lex;
  }
  thd_arg->lex->pop_context();
  DBUG_RETURN(0);
}


/**
  Push a new name resolution context for a JOIN ... ON clause to the
  context stack of a query block.

    Create a new name resolution context for a JOIN ... ON clause,
    set the first and last leaves of the list of table references
    to be used for name resolution, and push the newly created
    context to the stack of contexts of the query.

  @param thd       pointer to current thread
  @param left_op   left  operand of the JOIN
  @param right_op  rigth operand of the JOIN

  @todo Research if we should set the "outer_context" member of the new ON
  context.

  @retval
    FALSE  if all is OK
  @retval
    TRUE   if a memory allocation error occured
*/

bool
push_new_name_resolution_context(THD *thd,
                                 TABLE_LIST *left_op, TABLE_LIST *right_op)
{
  Name_resolution_context *on_context;
  if (!(on_context= new (thd->mem_root) Name_resolution_context))
    return TRUE;
  on_context->init();
  on_context->first_name_resolution_table=
    left_op->first_leaf_for_name_resolution();
  on_context->last_name_resolution_table=
    right_op->last_leaf_for_name_resolution();
  on_context->select_lex= thd->lex->current_select;
  // Save join nest's context in right_op, to find it later in view merging.
  DBUG_ASSERT(right_op->context_of_embedding == NULL);
  right_op->context_of_embedding= on_context;
  return thd->lex->push_context(on_context);
}


/**
  Add an ON condition to the second operand of a JOIN ... ON.

    Add an ON condition to the right operand of a JOIN ... ON clause.

  @param b     the second operand of a JOIN ... ON
  @param expr  the condition to be added to the ON clause
*/

void add_join_on(TABLE_LIST *b, Item *expr)
{
  if (expr)
  {
    if (!b->join_cond())
      b->set_join_cond(expr);
    else
    {
      /*
        If called from the parser, this happens if you have both a
        right and left join. If called later, it happens if we add more
        than one condition to the ON clause.
      */
      b->set_join_cond(new Item_cond_and(b->join_cond(), expr));
    }
    b->join_cond()->top_level_item();
  }
}


/**
  Mark that there is a NATURAL JOIN or JOIN ... USING between two
  tables.

    This function marks that table b should be joined with a either via
    a NATURAL JOIN or via JOIN ... USING. Both join types are special
    cases of each other, so we treat them together. The function
    setup_conds() creates a list of equal condition between all fields
    of the same name for NATURAL JOIN or the fields in 'using_fields'
    for JOIN ... USING. The list of equality conditions is stored
    either in b->join_cond(), or in JOIN::conds, depending on whether there
    was an outer join.

  EXAMPLE
  @verbatim
    SELECT * FROM t1 NATURAL LEFT JOIN t2
     <=>
    SELECT * FROM t1 LEFT JOIN t2 ON (t1.i=t2.i and t1.j=t2.j ... )

    SELECT * FROM t1 NATURAL JOIN t2 WHERE <some_cond>
     <=>
    SELECT * FROM t1, t2 WHERE (t1.i=t2.i and t1.j=t2.j and <some_cond>)

    SELECT * FROM t1 JOIN t2 USING(j) WHERE <some_cond>
     <=>
    SELECT * FROM t1, t2 WHERE (t1.j=t2.j and <some_cond>)
   @endverbatim

  @param a		  Left join argument
  @param b		  Right join argument
  @param using_fields    Field names from USING clause
*/

void add_join_natural(TABLE_LIST *a, TABLE_LIST *b, List<String> *using_fields,
                      SELECT_LEX *lex)
{
  b->natural_join= a;
  lex->prev_join_using= using_fields;
}

/** If pointer is not a null pointer, append filename to it. */

bool append_file_to_dir(THD *thd, const char **filename_ptr,
                        const char *table_name)
{
  char buff[FN_REFLEN],*ptr, *end;
  if (!*filename_ptr)
    return 0;					// nothing to do

  /* Check that the filename is not too long and it's a hard path */
  if (strlen(*filename_ptr)+strlen(table_name) >= FN_REFLEN-1 ||
      !test_if_hard_path(*filename_ptr))
  {
    my_error(ER_WRONG_TABLE_NAME, MYF(0), *filename_ptr);
    return 1;
  }
  /* Fix is using unix filename format on dos */
  strmov(buff,*filename_ptr);
  end=convert_dirname(buff, *filename_ptr, NullS);
  if (!(ptr= (char*) thd->alloc((size_t) (end-buff) + strlen(table_name)+1)))
    return 1;					// End of memory
  *filename_ptr=ptr;
  strxmov(ptr,buff,table_name,NullS);
  return 0;
}


/**
  Check if the select is a simple select (not an union).

  @retval
    0	ok
  @retval
    1	error	; In this case the error messege is sent to the client
*/

bool check_simple_select()
{
  THD *thd= current_thd;
  LEX *lex= thd->lex;
  if (lex->current_select != &lex->select_lex)
  {
    char command[80];
    Lex_input_stream *lip= & thd->m_parser_state->m_lip;
    strmake(command, lip->yylval->symbol.str,
	    min<size_t>(lip->yylval->symbol.length, sizeof(command)-1));
    my_error(ER_CANT_USE_OPTION_HERE, MYF(0), command);
    return 1;
  }
  return 0;
}


Comp_creator *comp_eq_creator(bool invert)
{
  return invert?(Comp_creator *)&ne_creator:(Comp_creator *)&eq_creator;
}


Comp_creator *comp_ge_creator(bool invert)
{
  return invert?(Comp_creator *)&lt_creator:(Comp_creator *)&ge_creator;
}


Comp_creator *comp_gt_creator(bool invert)
{
  return invert?(Comp_creator *)&le_creator:(Comp_creator *)&gt_creator;
}


Comp_creator *comp_le_creator(bool invert)
{
  return invert?(Comp_creator *)&gt_creator:(Comp_creator *)&le_creator;
}


Comp_creator *comp_lt_creator(bool invert)
{
  return invert?(Comp_creator *)&ge_creator:(Comp_creator *)&lt_creator;
}


Comp_creator *comp_ne_creator(bool invert)
{
  return invert?(Comp_creator *)&eq_creator:(Comp_creator *)&ne_creator;
}


/**
  Construct ALL/ANY/SOME subquery Item.

  @param left_expr   pointer to left expression
  @param cmp         compare function creator
  @param all         true if we create ALL subquery
  @param select_lex  pointer on parsed subquery structure

  @return
    constructed Item (or 0 if out of memory)
*/
Item * all_any_subquery_creator(Item *left_expr,
				chooser_compare_func_creator cmp,
				bool all,
				SELECT_LEX *select_lex)
{
  if ((cmp == &comp_eq_creator) && !all)       //  = ANY <=> IN
    return new Item_in_subselect(left_expr, select_lex);

  if ((cmp == &comp_ne_creator) && all)        // <> ALL <=> NOT IN
    return new Item_func_not(new Item_in_subselect(left_expr, select_lex));

  Item_allany_subselect *it=
    new Item_allany_subselect(left_expr, cmp, select_lex, all);
  if (all)
    return it->upper_item= new Item_func_not_all(it);	/* ALL */

  return it->upper_item= new Item_func_nop_all(it);      /* ANY/SOME */
}


/*
  Given a table in the source list, find a correspondent table in the
  table references list.

  @param lex Pointer to LEX representing multi-delete.
  @param src Source table to match.
  @param ref Table references list.

  @remark The source table list (tables listed before the FROM clause
  or tables listed in the FROM clause before the USING clause) may
  contain table names or aliases that must match unambiguously one,
  and only one, table in the target table list (table references list,
  after FROM/USING clause).

  @return Matching table, NULL otherwise.
*/

static TABLE_LIST *multi_delete_table_match(LEX *lex, TABLE_LIST *tbl,
                                            TABLE_LIST *tables)
{
  TABLE_LIST *match= NULL;
  DBUG_ENTER("multi_delete_table_match");

  for (TABLE_LIST *elem= tables; elem; elem= elem->next_local)
  {
    int cmp;

    if (tbl->is_fqtn && elem->is_alias)
      continue; /* no match */
    if (tbl->is_fqtn && elem->is_fqtn)
      cmp= my_strcasecmp(table_alias_charset, tbl->table_name, elem->table_name) ||
           strcmp(tbl->db, elem->db);
    else if (elem->is_alias)
      cmp= my_strcasecmp(table_alias_charset, tbl->alias, elem->alias);
    else
      cmp= my_strcasecmp(table_alias_charset, tbl->table_name, elem->table_name) ||
           strcmp(tbl->db, elem->db);

    if (cmp)
      continue;

    if (match)
    {
      my_error(ER_NONUNIQ_TABLE, MYF(0), elem->alias);
      DBUG_RETURN(NULL);
    }

    match= elem;
  }

  if (!match)
    my_error(ER_UNKNOWN_TABLE, MYF(0), tbl->table_name, "MULTI DELETE");

  DBUG_RETURN(match);
}



/**
  Link tables in auxilary table list of multi-delete with corresponding
  elements in main table list, and set proper locks for them.

  @param lex   pointer to LEX representing multi-delete

  @retval
    FALSE   success
  @retval
    TRUE    error
*/

bool multi_delete_set_locks_and_link_aux_tables(LEX *lex)
{
  TABLE_LIST *tables= lex->select_lex.table_list.first;
  TABLE_LIST *target_tbl;
  DBUG_ENTER("multi_delete_set_locks_and_link_aux_tables");

  for (target_tbl= lex->auxiliary_table_list.first;
       target_tbl; target_tbl= target_tbl->next_local)
  {
    /* All tables in aux_tables must be found in FROM PART */
    TABLE_LIST *walk= multi_delete_table_match(lex, target_tbl, tables);
    if (!walk)
      DBUG_RETURN(TRUE);
    if (!walk->derived)
    {
      target_tbl->table_name= walk->table_name;
      target_tbl->table_name_length= walk->table_name_length;
    }
    walk->updating= target_tbl->updating;
    target_tbl->correspondent_table= walk;	// Remember corresponding table
  }
  DBUG_RETURN(FALSE);
}


/**
   Set proper open mode and table type for element representing target table
   of CREATE TABLE statement, also adjust statement table list if necessary.
*/

void create_table_set_open_action_and_adjust_tables(LEX *lex)
{
  TABLE_LIST *create_table= lex->query_tables;

  if (lex->create_info.options & HA_LEX_CREATE_TMP_TABLE)
    create_table->open_type= OT_TEMPORARY_ONLY;
  else
    create_table->open_type= OT_BASE_ONLY;

  if (!lex->select_lex.item_list.elements)
  {
    /*
      Avoid opening and locking target table for ordinary CREATE TABLE
      or CREATE TABLE LIKE for write (unlike in CREATE ... SELECT we
      won't do any insertions in it anyway). Not doing this causes
      problems when running CREATE TABLE IF NOT EXISTS for already
      existing log table.
    */
    create_table->lock_type= TL_READ;
  }
}


/**
  negate given expression.

  @param thd  thread handler
  @param expr expression for negation

  @return
    negated expression
*/

Item *negate_expression(THD *thd, Item *expr)
{
  Item *negated;
  if (expr->type() == Item::FUNC_ITEM &&
      ((Item_func *) expr)->functype() == Item_func::NOT_FUNC)
  {
    /* it is NOT(NOT( ... )) */
    Item *arg= ((Item_func *) expr)->arguments()[0];
    enum_parsing_place place= thd->lex->current_select->parsing_place;
    if (arg->is_bool_func() || place == IN_WHERE || place == IN_HAVING)
      return arg;
    /*
      if it is not boolean function then we have to emulate value of
      not(not(a)), it will be a != 0
    */
    return new Item_func_ne(arg, new Item_int_0());
  }

  if ((negated= expr->neg_transformer(thd)) != 0)
    return negated;
  return new Item_func_not(expr);
}

/**
  Set the specified definer to the default value, which is the
  current user in the thread.
 
  @param[in]  thd       thread handler
  @param[out] definer   definer
*/
 
void get_default_definer(THD *thd, LEX_USER *definer)
{
  const Security_context *sctx= thd->security_ctx;

  definer->user.str= (char *) sctx->priv_user;
  definer->user.length= strlen(definer->user.str);

  definer->host.str= (char *) sctx->priv_host;
  definer->host.length= strlen(definer->host.str);

  definer->password= null_lex_str;
  definer->plugin= empty_lex_str;
  definer->auth= empty_lex_str;
  definer->uses_identified_with_clause= false;
  definer->uses_identified_by_clause= false;
  definer->uses_authentication_string_clause= false;
  definer->uses_identified_by_password_clause= false;
}


/**
  Create default definer for the specified THD.

  @param[in] thd         thread handler

  @return
    - On success, return a valid pointer to the created and initialized
    LEX_USER, which contains definer information.
    - On error, return 0.
*/

LEX_USER *create_default_definer(THD *thd)
{
  LEX_USER *definer;

  if (! (definer= (LEX_USER*) thd->alloc(sizeof(LEX_USER))))
    return 0;

  thd->get_definer(definer);

  return definer;
}


/**
  Create definer with the given user and host names.

  @param[in] thd          thread handler
  @param[in] user_name    user name
  @param[in] host_name    host name

  @return
    - On success, return a valid pointer to the created and initialized
    LEX_USER, which contains definer information.
    - On error, return 0.
*/

LEX_USER *create_definer(THD *thd, LEX_STRING *user_name, LEX_STRING *host_name)
{
  LEX_USER *definer;

  /* Create and initialize. */

  if (! (definer= (LEX_USER*) thd->alloc(sizeof(LEX_USER))))
    return 0;

  definer->user= *user_name;
  definer->host= *host_name;
  definer->password.str= NULL;
  definer->password.length= 0;
  definer->uses_authentication_string_clause= false;
  definer->uses_identified_by_clause= false;
  definer->uses_identified_by_password_clause= false;
  definer->uses_identified_with_clause= false;
  return definer;
}


/**
  Retuns information about user or current user.

  @param[in] thd          thread handler
  @param[in] user         user

  @return
    - On success, return a valid pointer to initialized
    LEX_USER, which contains user information.
    - On error, return 0.
*/

LEX_USER *get_current_user(THD *thd, LEX_USER *user)
{
  if (!user->user.str)  // current_user
  {
    LEX_USER *default_definer= create_default_definer(thd);
    if (default_definer)
    {
      /*
        Inherit parser semantics from the statement in which the user parameter
        was used.
        This is needed because a st_lex_user is both used as a component in an
        AST and as a specifier for a particular user in the ACL subsystem.
      */
      default_definer->uses_authentication_string_clause=
        user->uses_authentication_string_clause;
      default_definer->uses_identified_by_clause=
        user->uses_identified_by_clause;
      default_definer->uses_identified_by_password_clause=
        user->uses_identified_by_password_clause;
      default_definer->uses_identified_with_clause=
        user->uses_identified_with_clause;
      default_definer->plugin.str= user->plugin.str;
      default_definer->plugin.length= user->plugin.length;
      default_definer->auth.str= user->auth.str;
      default_definer->auth.length= user->auth.length;
      return default_definer;
    }
  }

  return user;
}


/**
  Check that byte length of a string does not exceed some limit.

  @param str         string to be checked
  @param err_msg     error message to be displayed if the string is too long
  @param max_length  max length

  @retval
    FALSE   the passed string is not longer than max_length
  @retval
    TRUE    the passed string is longer than max_length

  NOTE
    The function is not used in existing code but can be useful later?
*/

bool check_string_byte_length(LEX_STRING *str, const char *err_msg,
                              uint max_byte_length)
{
  if (str->length <= max_byte_length)
    return FALSE;

  my_error(ER_WRONG_STRING_LENGTH, MYF(0), str->str, err_msg, max_byte_length);

  return TRUE;
}


/*
  Check that char length of a string does not exceed some limit.

  SYNOPSIS
  check_string_char_length()
      str              string to be checked
      err_msg          error message to be displayed if the string is too long
      max_char_length  max length in symbols
      cs               string charset

  RETURN
    FALSE   the passed string is not longer than max_char_length
    TRUE    the passed string is longer than max_char_length
*/


bool check_string_char_length(LEX_STRING *str, const char *err_msg,
                              uint max_char_length, const CHARSET_INFO *cs,
                              bool no_error)
{
  int well_formed_error;
  uint res= cs->cset->well_formed_len(cs, str->str, str->str + str->length,
                                      max_char_length, &well_formed_error);

  if (!well_formed_error &&  str->length == res)
    return FALSE;

  if (!no_error)
  {
    ErrConvString err(str->str, str->length, cs);
    my_error(ER_WRONG_STRING_LENGTH, MYF(0), err.ptr(), err_msg, max_char_length);
  }
  return TRUE;
}


/**
  Check that host name string is valid.

  @param[in] str string to be checked

  @return             Operation status
    @retval  FALSE    host name is ok
    @retval  TRUE     host name string is longer than max_length or
                      has invalid symbols
*/

bool check_host_name(LEX_STRING *str)
{
  const char *name= str->str;
  const char *end= str->str + str->length;
  if (check_string_byte_length(str, ER(ER_HOSTNAME), HOSTNAME_LENGTH))
    return TRUE;

  while (name != end)
  {
    if (*name == '@')
    {
      my_printf_error(ER_UNKNOWN_ERROR, 
                      "Malformed hostname (illegal symbol: '%c')", MYF(0),
                      *name);
      return TRUE;
    }
    name++;
  }
  return FALSE;
}


extern int MYSQLparse(class THD *thd); // from sql_yacc.cc


/**
  This is a wrapper of MYSQLparse(). All the code should call parse_sql()
  instead of MYSQLparse().

  @param thd Thread context.
  @param parser_state Parser state.
  @param creation_ctx Object creation context.

  @return Error status.
    @retval FALSE on success.
    @retval TRUE on parsing error.
*/

bool parse_sql(THD *thd,
               Parser_state *parser_state,
               Object_creation_ctx *creation_ctx)
{
  bool ret_value;
  DBUG_ASSERT(thd->m_parser_state == NULL);
  DBUG_ASSERT(thd->lex->m_sql_cmd == NULL);

  MYSQL_QUERY_PARSE_START(thd->query());
  /* Backup creation context. */

  Object_creation_ctx *backup_ctx= NULL;

  if (creation_ctx)
    backup_ctx= creation_ctx->set_n_backup(thd);

  /* Set parser state. */

  thd->m_parser_state= parser_state;

#ifdef HAVE_PSI_STATEMENT_DIGEST_INTERFACE
  /* Start Digest */
  thd->m_parser_state->m_lip.m_digest_psi= MYSQL_DIGEST_START(thd->m_statement_psi);
#endif

  /* Parse the query. */

  bool mysql_parse_status= MYSQLparse(thd) != 0;

  /*
    Check that if MYSQLparse() failed either thd->is_error() is set, or an
    internal error handler is set.

    The assert will not catch a situation where parsing fails without an
    error reported if an error handler exists. The problem is that the
    error handler might have intercepted the error, so thd->is_error() is
    not set. However, there is no way to be 100% sure here (the error
    handler might be for other errors than parsing one).
  */

  DBUG_ASSERT(!mysql_parse_status ||
              (mysql_parse_status && thd->is_error()) ||
              (mysql_parse_status && thd->get_internal_handler()));

  /* Reset parser state. */

  thd->m_parser_state= NULL;

  /* Restore creation context. */

  if (creation_ctx)
    creation_ctx->restore_env(thd, backup_ctx);

  /* That's it. */

  ret_value= mysql_parse_status || thd->is_fatal_error;
  MYSQL_QUERY_PARSE_DONE(ret_value);
  return ret_value;
}

/**
  @} (end of group Runtime_Environment)
*/



/**
  Check and merge "CHARACTER SET cs [ COLLATE cl ]" clause

  @param cs character set pointer.
  @param cl collation pointer.

  Check if collation "cl" is applicable to character set "cs".

  If "cl" is NULL (e.g. when COLLATE clause is not specified),
  then simply "cs" is returned.
  
  @return Error status.
    @retval NULL, if "cl" is not applicable to "cs".
    @retval pointer to merged CHARSET_INFO on success.
*/


const CHARSET_INFO*
merge_charset_and_collation(const CHARSET_INFO *cs, const CHARSET_INFO *cl)
{
  if (cl)
  {
    if (!my_charset_same(cs, cl))
    {
      my_error(ER_COLLATION_CHARSET_MISMATCH, MYF(0), cl->name, cs->csname);
      return NULL;
    }
    return cl;
  }
  return cs;
}
