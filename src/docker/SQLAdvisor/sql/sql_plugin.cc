/*
   Copyright (c) 2005, 2014, Oracle and/or its affiliates. All rights reserved.

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; version 2 of the License.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software Foundation,
   51 Franklin Street, Suite 500, Boston, MA 02110-1335 USA */

#include "sql_priv.h"                         // SHOW_MY_BOOL
#include "unireg.h"
#include "my_global.h"                       // REQUIRED by m_string.h
#include "sql_class.h"                          // set_var.h: THD
#include "sys_vars_shared.h"
#include "sql_locale.h"
#include "sql_plugin.h"
#include "sql_parse.h"          // check_table_access
#include "sql_base.h"                           // close_mysql_tables
#include "key.h"                                // key_copy
#include "sql_show.h"           // remove_status_vars, add_status_vars
#include "strfunc.h"            // find_set
#include "sql_acl.h"                       // *_ACL
#include "records.h"          // init_read_record, end_read_record
#include <my_pthread.h>
#include <my_getopt.h>
#include <mysql/plugin_auth.h>
#include <mysql/plugin_validate_password.h>
#include "my_default.h"

#include <algorithm>

using std::min;
using std::max;

#define REPORT_TO_LOG  1
#define REPORT_TO_USER 2

/*
  hidden part of opaque value passed to variable check functions.
  Used to provide a object-like structure to non C++ consumers.
*/
struct st_item_value_holder : public st_mysql_value
{
  Item *item;
};


/*
  stored in bookmark_hash, this structure is never removed from the
  hash and is used to mark a single offset for a thd local variable
  even if plugins have been uninstalled and reinstalled, repeatedly.
  This structure is allocated from plugin_mem_root.

  The key format is as follows:
    1 byte         - variable type code
    name_len bytes - variable name
    '\0'           - end of key
*/
struct st_bookmark
{
  uint name_len;
  int offset;
  uint version;
  char key[1];
};


/*
  skeleton of a plugin variable - portion of structure common to all.
*/
struct st_mysql_sys_var
{
  MYSQL_PLUGIN_VAR_HEADER;
};


/****************************************************************************
  System Variables support
****************************************************************************/


sys_var *find_sys_var(THD *thd, const char *str, uint length)
{
  sys_var *var;
  DBUG_ENTER("find_sys_var");

  const my_bool *hidden= getopt_constraint_get_hidden_value(str, 0, FALSE);
  if (hidden && *hidden)
  {
    var= NULL;
    goto exit;
  }

  mysql_rwlock_rdlock(&LOCK_system_variables_hash);
  var= intern_find_sys_var(str, length);
  mysql_rwlock_unlock(&LOCK_system_variables_hash);

exit:
  if (!var)
    my_error(ER_UNKNOWN_SYSTEM_VARIABLE, MYF(0), (char*) str);
  DBUG_RETURN(var);
}


void plugin_thdvar_init(THD *thd, bool enable_plugins)
{
  DBUG_ENTER("plugin_thdvar_init");
  
  thd->variables= global_system_variables;
  
  DBUG_VOID_RETURN;
}
