/* Copyright (c) 2002, 2012, Oracle and/or its affiliates. All rights reserved.

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

#ifndef _SP_H_
#define _SP_H_

#include "sql_string.h"                         // LEX_STRING
#include "sp_head.h"                            // enum_sp_type


class Open_tables_backup;
class Open_tables_state;
class Query_arena;
class Query_tables_list;
class Sroutine_hash_entry;
class THD;
class sp_cache;
struct st_sp_chistics;
struct LEX;
struct TABLE;
struct TABLE_LIST;
typedef struct st_hash HASH;
template <typename T> class SQL_I_List;


/* Tells what SP_DEFAULT_ACCESS should be mapped to */
#define SP_DEFAULT_ACCESS_MAPPING SP_CONTAINS_SQL

// Return codes from sp_create_*, sp_drop_*, and sp_show_*:
#define SP_OK                 0
#define SP_KEY_NOT_FOUND     -1
#define SP_OPEN_TABLE_FAILED -2
#define SP_WRITE_ROW_FAILED  -3
#define SP_DELETE_ROW_FAILED -4
#define SP_GET_FIELD_FAILED  -5
#define SP_PARSE_ERROR       -6
#define SP_INTERNAL_ERROR    -7
#define SP_NO_DB_ERROR       -8
#define SP_BAD_IDENTIFIER    -9
#define SP_BODY_TOO_LONG    -10
#define SP_FLD_STORE_FAILED -11

/* DB storage of Stored PROCEDUREs and FUNCTIONs */
enum
{
  MYSQL_PROC_FIELD_DB = 0,
  MYSQL_PROC_FIELD_NAME,
  MYSQL_PROC_MYSQL_TYPE,
  MYSQL_PROC_FIELD_SPECIFIC_NAME,
  MYSQL_PROC_FIELD_LANGUAGE,
  MYSQL_PROC_FIELD_ACCESS,
  MYSQL_PROC_FIELD_DETERMINISTIC,
  MYSQL_PROC_FIELD_SECURITY_TYPE,
  MYSQL_PROC_FIELD_PARAM_LIST,
  MYSQL_PROC_FIELD_RETURNS,
  MYSQL_PROC_FIELD_BODY,
  MYSQL_PROC_FIELD_DEFINER,
  MYSQL_PROC_FIELD_CREATED,
  MYSQL_PROC_FIELD_MODIFIED,
  MYSQL_PROC_FIELD_SQL_MODE,
  MYSQL_PROC_FIELD_COMMENT,
  MYSQL_PROC_FIELD_CHARACTER_SET_CLIENT,
  MYSQL_PROC_FIELD_COLLATION_CONNECTION,
  MYSQL_PROC_FIELD_DB_COLLATION,
  MYSQL_PROC_FIELD_BODY_UTF8,
  MYSQL_PROC_FIELD_COUNT
};

/**
  Structure that represents element in the set of stored routines
  used by statement or routine.
*/

class Sroutine_hash_entry
{
public:
  /**
    Next element in list linking all routines in set. See also comments
    for LEX::sroutine/sroutine_list and sp_head::m_sroutines.
  */
  Sroutine_hash_entry *next;
  /**
    Uppermost view which directly or indirectly uses this routine.
    0 if routine is not used in view. Note that it also can be 0 if
    statement uses routine both via view and directly.
  */
  TABLE_LIST *belong_to_view;
  /**
    This is for prepared statement validation purposes.
    A statement looks up and pre-loads all its stored functions
    at prepare. Later on, if a function is gone from the cache,
    execute may fail.
    Remember the version of sp_head at prepare to be able to
    invalidate the prepared statement at execute if it
    changes.
  */
  ulong m_sp_cache_version;
};


///////////////////////////////////////////////////////////////////////////

sp_head *sp_start_parsing(THD *thd,
                          enum_sp_type sp_type,
                          sp_name *sp_name);

void sp_finish_parsing(THD *thd);

///////////////////////////////////////////////////////////////////////////

Item_result sp_map_result_type(enum enum_field_types type);
Item::Type sp_map_item_type(enum enum_field_types type);
uint sp_get_flags_for_command(LEX *lex);

bool sp_check_name(LEX_STRING *ident);

TABLE_LIST *sp_add_to_query_tables(THD *thd, LEX *lex,
                                   const char *db, const char *name);

///////////////////////////////////////////////////////////////////////////

#endif /* _SP_H_ */
