/*
   Copyright (c) 2002, 2013, Oracle and/or its affiliates. All rights reserved.

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

#include "sql_priv.h"
#include "unireg.h"
#include "sql_base.h"                           // close_thread_tables
#include "sql_parse.h"                          // parse_sql
#include "key.h"                                // key_copy
#include "sql_show.h"             // append_definer, append_identifier
#include "sql_db.h" // get_default_db_collation, mysql_opt_change_db,
                    // mysql_change_db, check_db_dir_existence,
                    // load_db_opt_by_name
#include "sql_table.h"                          // write_bin_log
#include "sql_acl.h"                       // SUPER_ACL
#include "sp_head.h"
#include "sp.h"

#include <my_user.h>

static bool
create_string(THD *thd, String *buf,
	      enum_sp_type sp_type,
	      const char *db, ulong dblen,
	      const char *name, ulong namelen,
	      const char *params, ulong paramslen,
	      const char *returns, ulong returnslen,
	      const char *body, ulong bodylen,
	      st_sp_chistics *chistics,
              const LEX_STRING *definer_user,
              const LEX_STRING *definer_host,
              sql_mode_t sql_mode);

static int
db_load_routine(THD *thd, enum_sp_type type, sp_name *name, sp_head **sphp,
                sql_mode_t sql_mode, const char *params, const char *returns,
                const char *body, st_sp_chistics &chistics,
                const char *definer, longlong created, longlong modified,
                Stored_program_creation_ctx *creation_ctx);

static const
TABLE_FIELD_TYPE proc_table_fields[MYSQL_PROC_FIELD_COUNT] =
{
  {
    { C_STRING_WITH_LEN("db") },
    { C_STRING_WITH_LEN("char(64)") },
    { C_STRING_WITH_LEN("utf8") }
  },
  {
    { C_STRING_WITH_LEN("name") },
    { C_STRING_WITH_LEN("char(64)") },
    { C_STRING_WITH_LEN("utf8") }
  },
  {
    { C_STRING_WITH_LEN("type") },
    { C_STRING_WITH_LEN("enum('FUNCTION','PROCEDURE')") },
    { NULL, 0 }
  },
  {
    { C_STRING_WITH_LEN("specific_name") },
    { C_STRING_WITH_LEN("char(64)") },
    { C_STRING_WITH_LEN("utf8") }
  },
  {
    { C_STRING_WITH_LEN("language") },
    { C_STRING_WITH_LEN("enum('SQL')") },
    { NULL, 0 }
  },
  {
    { C_STRING_WITH_LEN("sql_data_access") },
    { C_STRING_WITH_LEN("enum('CONTAINS_SQL','NO_SQL','READS_SQL_DATA','MODIFIES_SQL_DATA')") },
    { NULL, 0 }
  },
  {
    { C_STRING_WITH_LEN("is_deterministic") },
    { C_STRING_WITH_LEN("enum('YES','NO')") },
    { NULL, 0 }
  },
  {
    { C_STRING_WITH_LEN("security_type") },
    { C_STRING_WITH_LEN("enum('INVOKER','DEFINER')") },
    { NULL, 0 }
  },
  {
    { C_STRING_WITH_LEN("param_list") },
    { C_STRING_WITH_LEN("blob") },
    { NULL, 0 }
  },

  {
    { C_STRING_WITH_LEN("returns") },
    { C_STRING_WITH_LEN("longblob") },
    { NULL, 0 }
  },
  {
    { C_STRING_WITH_LEN("body") },
    { C_STRING_WITH_LEN("longblob") },
    { NULL, 0 }
  },
  {
    { C_STRING_WITH_LEN("definer") },
    { C_STRING_WITH_LEN("char(77)") },
    { C_STRING_WITH_LEN("utf8") }
  },
  {
    { C_STRING_WITH_LEN("created") },
    { C_STRING_WITH_LEN("timestamp") },
    { NULL, 0 }
  },
  {
    { C_STRING_WITH_LEN("modified") },
    { C_STRING_WITH_LEN("timestamp") },
    { NULL, 0 }
  },
  {
    { C_STRING_WITH_LEN("sql_mode") },
    { C_STRING_WITH_LEN("set('REAL_AS_FLOAT','PIPES_AS_CONCAT','ANSI_QUOTES',"
    "'IGNORE_SPACE','NOT_USED','ONLY_FULL_GROUP_BY','NO_UNSIGNED_SUBTRACTION',"
    "'NO_DIR_IN_CREATE','POSTGRESQL','ORACLE','MSSQL','DB2','MAXDB',"
    "'NO_KEY_OPTIONS','NO_TABLE_OPTIONS','NO_FIELD_OPTIONS','MYSQL323','MYSQL40',"
    "'ANSI','NO_AUTO_VALUE_ON_ZERO','NO_BACKSLASH_ESCAPES','STRICT_TRANS_TABLES',"
    "'STRICT_ALL_TABLES','NO_ZERO_IN_DATE','NO_ZERO_DATE','INVALID_DATES',"
    "'ERROR_FOR_DIVISION_BY_ZERO','TRADITIONAL','NO_AUTO_CREATE_USER',"
    "'HIGH_NOT_PRECEDENCE','NO_ENGINE_SUBSTITUTION','PAD_CHAR_TO_FULL_LENGTH')") },
    { NULL, 0 }
  },
  {
    { C_STRING_WITH_LEN("comment") },
    { C_STRING_WITH_LEN("text") },
    { C_STRING_WITH_LEN("utf8") }
  },
  {
    { C_STRING_WITH_LEN("character_set_client") },
    { C_STRING_WITH_LEN("char(32)") },
    { C_STRING_WITH_LEN("utf8") }
  },
  {
    { C_STRING_WITH_LEN("collation_connection") },
    { C_STRING_WITH_LEN("char(32)") },
    { C_STRING_WITH_LEN("utf8") }
  },
  {
    { C_STRING_WITH_LEN("db_collation") },
    { C_STRING_WITH_LEN("char(32)") },
    { C_STRING_WITH_LEN("utf8") }
  },
  {
    { C_STRING_WITH_LEN("body_utf8") },
    { C_STRING_WITH_LEN("longblob") },
    { NULL, 0 }
  }
};

static const TABLE_FIELD_DEF
  proc_table_def= {MYSQL_PROC_FIELD_COUNT, proc_table_fields};

/*************************************************************************/

/**
  Stored_routine_creation_ctx -- creation context of stored routines
  (stored procedures and functions).
*/

class Stored_routine_creation_ctx : public Stored_program_creation_ctx,
                                    public Sql_alloc
{
public:
  static Stored_routine_creation_ctx *
  load_from_db(THD *thd, const sp_name *name, TABLE *proc_tbl);

public:
  virtual Stored_program_creation_ctx *clone(MEM_ROOT *mem_root)
  {
    return new (mem_root) Stored_routine_creation_ctx(m_client_cs,
                                                      m_connection_cl,
                                                      m_db_cl);
  }

protected:
  virtual Object_creation_ctx *create_backup_ctx(THD *thd) const
  {
    DBUG_ENTER("Stored_routine_creation_ctx::create_backup_ctx");
    DBUG_RETURN(new Stored_routine_creation_ctx(thd));
  }

private:
  Stored_routine_creation_ctx(THD *thd)
    : Stored_program_creation_ctx(thd)
  { }

  Stored_routine_creation_ctx(const CHARSET_INFO *client_cs,
                              const CHARSET_INFO *connection_cl,
                              const CHARSET_INFO *db_cl)
    : Stored_program_creation_ctx(client_cs, connection_cl, db_cl)
  { }
};

/**
  Start parsing of a stored program.

  This function encapsulates all the steps necessary to initialize sp_head to
  start parsing SP.

  Every successful call of sp_start_parsing() must finish with
  sp_finish_parsing().

  @param thd      Thread context.
  @param sp_type  The stored program type
  @param sp_name  The stored progam name

  @return properly initialized sp_head-instance in case of success, or NULL is
  case of out-of-memory error.
*/
sp_head *sp_start_parsing(THD *thd,
                          enum_sp_type sp_type,
                          sp_name *sp_name)
{
  // The order is important:
  // 1. new sp_head()

  sp_head *sp= new sp_head(sp_type);

  if (!sp)
    return NULL;

  // 2. start_parsing_sp_body()

  sp->m_parser_data.start_parsing_sp_body(thd, sp);

  // 3. finish initialization.

  sp->m_root_parsing_ctx= new (thd->mem_root) sp_pcontext();

  if (!sp->m_root_parsing_ctx)
    return NULL;

  thd->lex->set_sp_current_parsing_ctx(sp->m_root_parsing_ctx);

  // 4. set name.

  sp->init_sp_name(thd, sp_name);

  return sp;
}


/**
  Finish parsing of a stored program.

  This is a counterpart of sp_start_parsing().

  @param thd  Thread context.
*/
void sp_finish_parsing(THD *thd)
{
  sp_head *sp= thd->lex->sphead;

  DBUG_ASSERT(sp);

  sp->set_body_end(thd);

  sp->m_parser_data.finish_parsing_sp_body(thd);
}


/// @return Item_result code corresponding to the RETURN-field type code.
Item_result sp_map_result_type(enum enum_field_types type)
{
  switch (type) {
  case MYSQL_TYPE_BIT:
  case MYSQL_TYPE_TINY:
  case MYSQL_TYPE_SHORT:
  case MYSQL_TYPE_LONG:
  case MYSQL_TYPE_LONGLONG:
  case MYSQL_TYPE_INT24:
    return INT_RESULT;
  case MYSQL_TYPE_DECIMAL:
  case MYSQL_TYPE_NEWDECIMAL:
    return DECIMAL_RESULT;
  case MYSQL_TYPE_FLOAT:
  case MYSQL_TYPE_DOUBLE:
    return REAL_RESULT;
  default:
    return STRING_RESULT;
  }
}


/// @return Item::Type code corresponding to the RETURN-field type code.
Item::Type sp_map_item_type(enum enum_field_types type)
{
  switch (type) {
  case MYSQL_TYPE_BIT:
  case MYSQL_TYPE_TINY:
  case MYSQL_TYPE_SHORT:
  case MYSQL_TYPE_LONG:
  case MYSQL_TYPE_LONGLONG:
  case MYSQL_TYPE_INT24:
    return Item::INT_ITEM;
  case MYSQL_TYPE_DECIMAL:
  case MYSQL_TYPE_NEWDECIMAL:
    return Item::DECIMAL_ITEM;
  case MYSQL_TYPE_FLOAT:
  case MYSQL_TYPE_DOUBLE:
    return Item::REAL_ITEM;
  default:
    return Item::STRING_ITEM;
  }
}


/**
  @param lex LEX-object, representing an SQL-statement inside SP.

  @return a combination of:
    - sp_head::MULTI_RESULTS: added if the 'cmd' is a command that might
      result in multiple result sets being sent back.
    - sp_head::CONTAINS_DYNAMIC_SQL: added if 'cmd' is one of PREPARE,
      EXECUTE, DEALLOCATE.
*/
uint sp_get_flags_for_command(LEX *lex)
{
  uint flags;

  switch (lex->sql_command) {
  case SQLCOM_SELECT:
    if (lex->result)
    {
      flags= 0;                      /* This is a SELECT with INTO clause */
      break;
    }
    /* fallthrough */
  case SQLCOM_ANALYZE:
  case SQLCOM_OPTIMIZE:
  case SQLCOM_PRELOAD_KEYS:
  case SQLCOM_ASSIGN_TO_KEYCACHE:
  case SQLCOM_CHECKSUM:
  case SQLCOM_CHECK:
  case SQLCOM_HA_READ:
  case SQLCOM_SHOW_BINLOGS:
  case SQLCOM_SHOW_BINLOG_EVENTS:
  case SQLCOM_SHOW_RELAYLOG_EVENTS:
  case SQLCOM_SHOW_CHARSETS:
  case SQLCOM_SHOW_COLLATIONS:
  case SQLCOM_SHOW_CREATE:
  case SQLCOM_SHOW_CREATE_DB:
  case SQLCOM_SHOW_CREATE_FUNC:
  case SQLCOM_SHOW_CREATE_PROC:
  case SQLCOM_SHOW_CREATE_EVENT:
  case SQLCOM_SHOW_CREATE_TRIGGER:
  case SQLCOM_SHOW_DATABASES:
  case SQLCOM_SHOW_ERRORS:
  case SQLCOM_SHOW_FIELDS:
  case SQLCOM_SHOW_FUNC_CODE:
  case SQLCOM_SHOW_GRANTS:
  case SQLCOM_SHOW_ENGINE_STATUS:
  case SQLCOM_SHOW_ENGINE_LOGS:
  case SQLCOM_SHOW_ENGINE_MUTEX:
  case SQLCOM_SHOW_EVENTS:
  case SQLCOM_SHOW_KEYS:
  case SQLCOM_SHOW_MASTER_STAT:
  case SQLCOM_SHOW_OPEN_TABLES:
  case SQLCOM_SHOW_PRIVILEGES:
  case SQLCOM_SHOW_PROCESSLIST:
  case SQLCOM_SHOW_PROC_CODE:
  case SQLCOM_SHOW_SLAVE_HOSTS:
  case SQLCOM_SHOW_SLAVE_STAT:
  case SQLCOM_SHOW_STATUS:
  case SQLCOM_SHOW_STATUS_FUNC:
  case SQLCOM_SHOW_STATUS_PROC:
  case SQLCOM_SHOW_STORAGE_ENGINES:
  case SQLCOM_SHOW_TABLES:
  case SQLCOM_SHOW_TABLE_STATUS:
  case SQLCOM_SHOW_VARIABLES:
  case SQLCOM_SHOW_WARNS:
  case SQLCOM_REPAIR:
    flags= sp_head::MULTI_RESULTS;
    break;
  /*
    EXECUTE statement may return a result set, but doesn't have to.
    We can't, however, know it in advance, and therefore must add
    this statement here. This is ok, as is equivalent to a result-set
    statement within an IF condition.
  */
  case SQLCOM_EXECUTE:
    flags= sp_head::MULTI_RESULTS | sp_head::CONTAINS_DYNAMIC_SQL;
    break;
  case SQLCOM_PREPARE:
  case SQLCOM_DEALLOCATE_PREPARE:
    flags= sp_head::CONTAINS_DYNAMIC_SQL;
    break;
  case SQLCOM_CREATE_TABLE:
    if (lex->create_info.options & HA_LEX_CREATE_TMP_TABLE)
      flags= 0;
    else
      flags= sp_head::HAS_COMMIT_OR_ROLLBACK;
    break;
  case SQLCOM_DROP_TABLE:
    if (lex->drop_temporary)
      flags= 0;
    else
      flags= sp_head::HAS_COMMIT_OR_ROLLBACK;
    break;
  case SQLCOM_FLUSH:
    flags= sp_head::HAS_SQLCOM_FLUSH;
    break;
  case SQLCOM_RESET:
    flags= sp_head::HAS_SQLCOM_RESET;
    break;
  case SQLCOM_CREATE_INDEX:
  case SQLCOM_CREATE_DB:
  case SQLCOM_CREATE_VIEW:
  case SQLCOM_CREATE_TRIGGER:
  case SQLCOM_CREATE_USER:
  case SQLCOM_ALTER_TABLE:
  case SQLCOM_GRANT:
  case SQLCOM_REVOKE:
  case SQLCOM_BEGIN:
  case SQLCOM_RENAME_TABLE:
  case SQLCOM_RENAME_USER:
  case SQLCOM_DROP_INDEX:
  case SQLCOM_DROP_DB:
  case SQLCOM_REVOKE_ALL:
  case SQLCOM_DROP_USER:
  case SQLCOM_DROP_VIEW:
  case SQLCOM_DROP_TRIGGER:
  case SQLCOM_TRUNCATE:
  case SQLCOM_COMMIT:
  case SQLCOM_ROLLBACK:
  case SQLCOM_LOAD:
  case SQLCOM_LOCK_TABLES:
  case SQLCOM_CREATE_PROCEDURE:
  case SQLCOM_CREATE_SPFUNCTION:
  case SQLCOM_ALTER_PROCEDURE:
  case SQLCOM_ALTER_FUNCTION:
  case SQLCOM_DROP_PROCEDURE:
  case SQLCOM_DROP_FUNCTION:
  case SQLCOM_CREATE_EVENT:
  case SQLCOM_ALTER_EVENT:
  case SQLCOM_DROP_EVENT:
  case SQLCOM_INSTALL_PLUGIN:
  case SQLCOM_UNINSTALL_PLUGIN:
    flags= sp_head::HAS_COMMIT_OR_ROLLBACK;
    break;
  default:
    flags= lex->describe ? sp_head::MULTI_RESULTS : 0;
    break;
  }
  return flags;
}


/**
  Check that the name 'ident' is ok.  It's assumed to be an 'ident'
  from the parser, so we only have to check length and trailing spaces.
  The former is a standard requirement (and 'show status' assumes a
  non-empty name), the latter is a mysql:ism as trailing spaces are
  removed by get_field().

  @retval true    bad name
  @retval false   name is ok
*/

bool sp_check_name(LEX_STRING *ident)
{
  if (!ident || !ident->str || !ident->str[0] ||
      ident->str[ident->length-1] == ' ')
  {
    my_error(ER_SP_WRONG_NAME, MYF(0), ident->str);
    return true;
  }

  if (check_string_char_length(ident, "", NAME_CHAR_LEN,
                               system_charset_info, 1))
  {
    my_error(ER_TOO_LONG_IDENT, MYF(0), ident->str);
    return true;
  }

  return false;
}

