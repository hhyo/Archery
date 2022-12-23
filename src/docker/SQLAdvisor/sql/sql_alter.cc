/* Copyright (c) 2010, 2012, Oracle and/or its affiliates. All rights reserved.

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

#include "sql_parse.h"                       // check_access
#include "sql_table.h"                       // mysql_alter_table,
                                             // mysql_exchange_partition
#include "sql_base.h"                        // open_temporary_tables
#include "sql_alter.h"


Alter_info::Alter_info(const Alter_info &rhs, MEM_ROOT *mem_root)
  :drop_list(rhs.drop_list, mem_root),
  alter_list(rhs.alter_list, mem_root),
  key_list(rhs.key_list, mem_root),
  create_list(rhs.create_list, mem_root),
  delayed_key_list(rhs.delayed_key_list, mem_root),
  delayed_key_info(rhs.delayed_key_info),
  delayed_key_count(rhs.delayed_key_count),
  flags(rhs.flags),
  keys_onoff(rhs.keys_onoff),
  partition_names(rhs.partition_names, mem_root),
  num_parts(rhs.num_parts),
  requested_algorithm(rhs.requested_algorithm),
  requested_lock(rhs.requested_lock)
{
  /*
    Make deep copies of used objects.
    This is not a fully deep copy - clone() implementations
    of Alter_drop, Alter_column, Key, foreign_key, Key_part_spec
    do not copy string constants. At the same length the only
    reason we make a copy currently is that ALTER/CREATE TABLE
    code changes input Alter_info definitions, but string
    constants never change.
  */
  list_copy_and_replace_each_value(drop_list, mem_root);
  list_copy_and_replace_each_value(alter_list, mem_root);
  list_copy_and_replace_each_value(key_list, mem_root);
  list_copy_and_replace_each_value(create_list, mem_root);
  list_copy_and_replace_each_value(delayed_key_list, mem_root);
  /* partition_names are not deeply copied currently */
}


bool Alter_info::set_requested_algorithm(const LEX_STRING *str)
{
  // To avoid adding new keywords to the grammar, we match strings here.
  if (!my_strcasecmp(system_charset_info, str->str, "INPLACE"))
    requested_algorithm= ALTER_TABLE_ALGORITHM_INPLACE;
  else if (!my_strcasecmp(system_charset_info, str->str, "COPY"))
    requested_algorithm= ALTER_TABLE_ALGORITHM_COPY;
  else if (!my_strcasecmp(system_charset_info, str->str, "DEFAULT"))
    requested_algorithm= ALTER_TABLE_ALGORITHM_DEFAULT;
  else
    return true;
  return false;
}


bool Alter_info::set_requested_lock(const LEX_STRING *str)
{
  // To avoid adding new keywords to the grammar, we match strings here.
  if (!my_strcasecmp(system_charset_info, str->str, "NONE"))
    requested_lock= ALTER_TABLE_LOCK_NONE;
  else if (!my_strcasecmp(system_charset_info, str->str, "SHARED"))
    requested_lock= ALTER_TABLE_LOCK_SHARED;
  else if (!my_strcasecmp(system_charset_info, str->str, "EXCLUSIVE"))
    requested_lock= ALTER_TABLE_LOCK_EXCLUSIVE;
  else if (!my_strcasecmp(system_charset_info, str->str, "DEFAULT"))
    requested_lock= ALTER_TABLE_LOCK_DEFAULT;
  else
    return true;
  return false;
}


