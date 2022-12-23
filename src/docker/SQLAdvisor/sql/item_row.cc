/* Copyright (c) 2002, 2013, Oracle and/or its affiliates. All rights reserved.

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

#include "sql_priv.h"
/*
  It is necessary to include set_var.h instead of item.h because there
  are dependencies on include order for set_var.h and item.h. This
  will be resolved later.
*/
#include "sql_class.h"                          // THD, set_var.h: THD
#include "set_var.h"

/**
  Row items used for comparing rows and IN operations on rows:

  @verbatim
  (a, b, c) > (10, 10, 30)
  (a, b, c) = (select c, d, e, from t1 where x=12)
  (a, b, c) IN ((1,2,2), (3,4,5), (6,7,8)
  (a, b, c) IN (select c, d, e, from t1)
  @endverbatim

  @todo
    think placing 2-3 component items in item (as it done for function
*/

Item_row::Item_row(List<Item> &arg):
  Item(), used_tables_cache(0), not_null_tables_cache(0),
  const_item_cache(1), with_null(0)
{

  //TODO: think placing 2-3 component items in item (as it done for function)
  if ((arg_count= arg.elements))
    items= (Item**) sql_alloc(sizeof(Item*)*arg_count);
  else
    items= 0;
  List_iterator<Item> li(arg);
  uint i= 0;
  Item *item;
  while ((item= li++))
  {
    items[i]= item;
    i++;    
  }
}

Item_row::Item_row(Item *head, List<Item> &tail):
  used_tables_cache(0), not_null_tables_cache(0),
  const_item_cache(1), with_null(0)
{

  //TODO: think placing 2-3 component items in item (as it done for function)
  arg_count= 1 + tail.elements;
  items= (Item**) sql_alloc(sizeof(Item*)*arg_count);
  if (items == NULL)
  {
    arg_count= 0;
    return; // OOM
  }
  items[0]= head;
  List_iterator<Item> li(tail);
  uint i= 1;
  Item *item;
  while ((item= li++))
  {
    items[i]= item;
    i++;    
  }
}

void Item_row::illegal_method_call(const char *method) {
  DBUG_ENTER("Item_row::illegal_method_call");
  DBUG_PRINT("error", ("!!! %s method was called for row item", method));
  DBUG_ASSERT(0);
  my_error(ER_OPERAND_COLUMNS, MYF(0), 1);
  DBUG_VOID_RETURN;
}

bool Item_row::check_cols(uint c)
{
  if (c != arg_count)
  {
    my_error(ER_OPERAND_COLUMNS, MYF(0), c);
    return 1;
  }
  return 0;
}

void Item_row::print(String *str, enum_query_type query_type)
{
  str->append('(');
  for (uint i= 0; i < arg_count; i++)
  {
    if (i)
      str->append(',');
    items[i]->print(str, query_type);
  }
  str->append(')');
}


bool Item_row::walk(Item_processor processor, bool walk_subquery, uchar *arg)
{
  for (uint i= 0; i < arg_count; i++)
  {
    if (items[i]->walk(processor, walk_subquery, arg))
      return 1;
  }
  return (this->*processor)(arg);
}


void Item_row::bring_value()
{
  for (uint i= 0; i < arg_count; i++)
    items[i]->bring_value();
}
