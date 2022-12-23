/* Copyright (c) 2002, 2014, Oracle and/or its affiliates. All rights
   reserved.

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

/**
  @file

  @brief
  subselect Item

  @todo
    - add function from mysql_select that use JOIN* as parameter to JOIN
    methods (sql_select.h/sql_select.cc)
*/

#include "sql_priv.h"
/*
  It is necessary to include set_var.h instead of item.h because there
  are dependencies on include order for set_var.h and item.h. This
  will be resolved later.
*/
#include "sql_class.h"                          // set_var.h: THD
#include "set_var.h"
#include "sql_parse.h"                          // check_stack_overrun
#include "sql_derived.h"                        // mysql_derived_create, ...
#include "sql_test.h"
#include "opt_explain_format.h"

Item_subselect::Item_subselect():
  Item_result_field(), value_assigned(0), traced_before(false),
  substitution(NULL), in_cond_of_tab(INT_MIN),
  used_tables_cache(0), have_to_be_excluded(0), const_item_cache(1)
{
  with_subselect= 1;
  reset();
  /*
    Item value is NULL if select_result_interceptor didn't change this value
    (i.e. some rows will be found returned)
  */
  null_value= TRUE;
}


void Item_subselect::init(st_select_lex *select_lex,
			  select_result_interceptor *result)
{
  /*
    Please see Item_singlerow_subselect::invalidate_and_restore_select_lex(),
    which depends on alterations to the parse tree implemented here.
  */

  DBUG_ENTER("Item_subselect::init");
  DBUG_PRINT("enter", ("select_lex: 0x%lx", (long) select_lex));
  unit= select_lex->master_unit();

  if (unit->item)
  {
    parsing_place= unit->item->parsing_place;
    unit->item= this;
  }
  else
  {
    SELECT_LEX *outer_select= unit->outer_select();
    /*
      do not take into account expression inside aggregate functions because
      they can access original table fields
    */
    parsing_place= (outer_select->in_sum_expr ?
                    NO_MATTER :
                    outer_select->parsing_place);
  }
  {
    SELECT_LEX *upper= unit->outer_select();
    if (upper->parsing_place == IN_HAVING)
      upper->subquery_in_having= 1;
  }
  DBUG_VOID_RETURN;
}

Item_subselect::~Item_subselect()
{
}

/**
  Apply walk() processor to join conditions.

  JOINs may be nested. Walk nested joins recursively to apply the
  processor.
*/
bool Item_subselect::walk_join_condition(List<TABLE_LIST> *tables,
                                         Item_processor processor,
                                         bool walk_subquery,
                                         uchar *argument)
{
  TABLE_LIST *table;
  List_iterator<TABLE_LIST> li(*tables);

  while ((table= li++))
  {
    if (table->join_cond() &&
        table->join_cond()->walk(processor, walk_subquery, argument))
      return true;

    if (table->nested_join != NULL &&
        walk_join_condition(&table->nested_join->join_list, processor,
                            walk_subquery, argument))
      return true;
  }
  return false;
}


/**
  Workaround for bug in gcc 4.1. @See Item_in_subselect::walk()
*/
bool Item_subselect::walk_body(Item_processor processor, bool walk_subquery,
                               uchar *argument)
{
  if (walk_subquery)
  {
    for (SELECT_LEX *lex= unit->first_select(); lex; lex= lex->next_select())
    {
      List_iterator<Item> li(lex->item_list);
      Item *item;
      ORDER *order;

      while ((item=li++))
      {
        if (item->walk(processor, walk_subquery, argument))
          return true;
      }

      if (lex->join_list != NULL &&
          walk_join_condition(lex->join_list, processor, walk_subquery, argument))
        return true;

      if (lex->where && (lex->where)->walk(processor, walk_subquery, argument))
        return true;

      for (order= lex->group_list.first ; order; order= order->next)
      {
        if ((*order->item)->walk(processor, walk_subquery, argument))
          return true;
      }

      if (lex->having && (lex->having)->walk(processor, walk_subquery,
                                             argument))
        return true;

      for (order= lex->order_list.first ; order; order= order->next)
      {
        if ((*order->item)->walk(processor, walk_subquery, argument))
          return true;
      }
    }
  }
  return (this->*processor)(argument);
}

bool Item_subselect::walk(Item_processor processor, bool walk_subquery,
                          uchar *argument)
{
  return walk_body(processor, walk_subquery, argument);
}


/**
  Mark a subquery unit with information provided

  A subquery may belong to WHERE, HAVING, ORDER BY or GROUP BY item trees.
  This "processor" qualifies subqueries by outer clause type.
  
  @note For the WHERE clause of the JOIN query this function also associates
        a related table with the unit.

  @param arg    Explain_subquery_marker structure

  @retval false

  @note We always return "false" as far as we don't want to dive deeper because
        we explain inner subqueries in their joins contexts.
*/

bool Item_subselect::explain_subquery_checker(uchar **arg)
{
  Explain_subquery_marker *m= 
    *reinterpret_cast<Explain_subquery_marker **>(arg);

  if (m->type == CTX_WHERE)
  {
    /*
      A subquery in the WHERE clause may be associated with a few JOIN_TABs
      simultaneously.
    */
    if (unit->explain_marker == CTX_NONE)
      unit->explain_marker= CTX_WHERE;
    else
      DBUG_ASSERT(unit->explain_marker == CTX_WHERE);
    m->destination->register_where_subquery(unit);
    return false;
  }

  if (m->type == CTX_HAVING && unit->explain_marker == CTX_WHERE)
  {
    /*
      This subquery was in SELECT list of outer subquery transformed
      with IN->EXISTS, so is referenced by WHERE and HAVING;
      see Item_in_subselect::single_value_in_to_exists_transformer()
    */
    return false;
  }

  if (unit->explain_marker == CTX_NONE)
    goto overwrite;

  if (unit->explain_marker == m->type)
    return false;

  /*
    GROUP BY subqueries may be listed in different item trees simultaneously:
     1) in GROUP BY items,
     2) in ORDER BY items and/or
     3) in SELECT list.
    If such a subquery in the SELECT list, we mark the subquery as if it
    belongs to SELECT list, otherwise we mark it as "GROUP BY" subquery.

    ORDER BY subqueries may be listed twice in SELECT list and ORDER BY list.
    In this case we mark such a subquery as "SELECT list" subquery.
  */
  if (unit->explain_marker == CTX_GROUP_BY_SQ && m->type == CTX_ORDER_BY_SQ)
    return false;
  if (unit->explain_marker == CTX_ORDER_BY_SQ && m->type == CTX_GROUP_BY_SQ)
    goto overwrite;

  if (unit->explain_marker == CTX_SELECT_LIST &&
      (m->type == CTX_ORDER_BY_SQ || m->type == CTX_GROUP_BY_SQ))
    return false;
  if ((unit->explain_marker == CTX_ORDER_BY_SQ ||
       unit->explain_marker == CTX_GROUP_BY_SQ) && m->type == CTX_SELECT_LIST)
    goto overwrite;

  DBUG_ASSERT(!"Unexpected combination of item trees!");
  return false;

overwrite:
  unit->explain_marker= m->type;
  return false;
}

bool Item_in_subselect::walk(Item_processor processor, bool walk_subquery,
                             uchar *argument)
{
  if (left_expr->walk(processor, walk_subquery, argument))
    return true;
  /*
    Cannot call "Item_subselect::walk(...)" because with gcc 4.1
    Item_in_subselect::walk() was incorrectly called instead.
    Using Item_subselect::walk_body() instead is a workaround.
  */
  return walk_body(processor, walk_subquery, argument);
}


Item::Type Item_subselect::type() const
{
  return SUBSELECT_ITEM;
}



table_map Item_subselect::used_tables() const
{
  return 0L;
}


bool Item_subselect::const_item() const
{
  if (unit->thd->lex->context_analysis_only)
    return false;
  /* Not constant until tables are locked. */
  if (!unit->thd->lex->is_query_tables_locked())
    return false;
  return const_item_cache;
}


void Item_subselect::print(String *str, enum_query_type query_type)
{
    str->append("(...)");
}


Item_singlerow_subselect::Item_singlerow_subselect(st_select_lex *select_lex)
  :Item_subselect(), value(0)
{
  DBUG_ENTER("Item_singlerow_subselect::Item_singlerow_subselect");
  init(select_lex, new select_singlerow_subselect(this));
  maybe_null= 1;
  max_columns= UINT_MAX;
  DBUG_VOID_RETURN;
}

st_select_lex *
Item_singlerow_subselect::invalidate_and_restore_select_lex()
{
  DBUG_ENTER("Item_singlerow_subselect::invalidate_and_restore_select_lex");
  st_select_lex *result= unit->first_select();

  DBUG_ASSERT(result);

  /*
    This code restore the parse tree in it's state before the execution of
    Item_singlerow_subselect::Item_singlerow_subselect(),
    and in particular decouples this object from the SELECT_LEX,
    so that the SELECT_LEX can be used with a different flavor
    or Item_subselect instead, as part of query rewriting.
  */
  unit->item= NULL;

  DBUG_RETURN(result);
}

Item_maxmin_subselect::Item_maxmin_subselect(THD *thd_param,
                                             Item_subselect *parent,
                                             st_select_lex *select_lex,
                                             bool max_arg,
                                             bool ignore_nulls)
  :Item_singlerow_subselect(), was_values(false)
{
  DBUG_ENTER("Item_maxmin_subselect::Item_maxmin_subselect");
  max= max_arg;
  init(select_lex, new select_max_min_finder_subselect(this, max_arg,
                                                       ignore_nulls));
  max_columns= 1;
  maybe_null= 1;
  max_columns= 1;

  DBUG_VOID_RETURN;
}
void Item_maxmin_subselect::print(String *str, enum_query_type query_type)
{
  str->append(max?"<max>":"<min>", 5);
  Item_singlerow_subselect::print(str, query_type);
}

bool Item_singlerow_subselect::null_inside()
{
  return 0;
}


double Item_singlerow_subselect::val_real()
{
    reset();
    return 0;
}

longlong Item_singlerow_subselect::val_int()
{
    reset();
    return 0;
}

String *Item_singlerow_subselect::val_str(String *str)
{
    reset();
    return 0;
}


my_decimal *Item_singlerow_subselect::val_decimal(my_decimal *decimal_value)
{
    reset();
    return 0;
}


bool Item_singlerow_subselect::val_bool()
{
    reset();
    return 0;
}


Item_exists_subselect::Item_exists_subselect(st_select_lex *select_lex):
  Item_subselect(), value(FALSE), exec_method(EXEC_UNSPECIFIED),
     sj_convert_priority(0), embedding_join_nest(NULL)
{
  DBUG_ENTER("Item_exists_subselect::Item_exists_subselect");
  init(select_lex, new select_exists_subselect(this));
  max_columns= UINT_MAX;
  null_value= FALSE; //can't be NULL
  maybe_null= 0; //can't be NULL
  DBUG_VOID_RETURN;
}


void Item_exists_subselect::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("exists"));
  Item_subselect::print(str, query_type);
}


bool Item_in_subselect::test_limit(st_select_lex_unit *unit_arg)
{
  if (unit_arg->fake_select_lex &&
      unit_arg->fake_select_lex->test_limit())
    return(1);

  SELECT_LEX *sl= unit_arg->first_select();
  for (; sl; sl= sl->next_select())
  {
    if (sl->test_limit())
      return(1);
  }
  return(0);
}

Item_in_subselect::Item_in_subselect(Item * left_exp,
				     st_select_lex *select_lex):
  Item_exists_subselect(), left_expr(left_exp), left_expr_cache(NULL),
  left_expr_cache_filled(false), need_expr_cache(TRUE),
  upper_item(NULL)
{
  DBUG_ENTER("Item_in_subselect::Item_in_subselect");
  init(select_lex, new select_exists_subselect(this));
  max_columns= UINT_MAX;
  maybe_null= 1;
  reset();
  //if test_limit will fail then error will be reported to client
  test_limit(select_lex->master_unit());
  DBUG_VOID_RETURN;
}

Item_allany_subselect::Item_allany_subselect(Item * left_exp,
                                             chooser_compare_func_creator fc,
					     st_select_lex *select_lex,
					     bool all_arg)
  :Item_in_subselect(), func_creator(fc), all(all_arg)
{
  DBUG_ENTER("Item_allany_subselect::Item_allany_subselect");
  left_expr= left_exp;
  func= func_creator(all_arg);
  init(select_lex, new select_exists_subselect(this));
  max_columns= 1;
  reset();
  //if test_limit will fail then error will be reported to client
  test_limit(select_lex->master_unit());
  DBUG_VOID_RETURN;
}

void Item_in_subselect::print(String *str, enum_query_type query_type)
{
  if (exec_method == EXEC_EXISTS_OR_MAT || exec_method == EXEC_EXISTS)
    str->append(STRING_WITH_LEN("<exists>"));
  else
  {
    left_expr->print(str, query_type);
    str->append(STRING_WITH_LEN(" in "));
  }
  Item_subselect::print(str, query_type);
}


void Item_allany_subselect::print(String *str, enum_query_type query_type)
{
  if (exec_method == EXEC_EXISTS_OR_MAT || exec_method == EXEC_EXISTS)
    str->append(STRING_WITH_LEN("<exists>"));
  else
  {
    left_expr->print(str, query_type);
    str->append(' ');
    str->append(func->symbol(all));
    str->append(all ? " all " : " any ", 5);
  }
  Item_subselect::print(str, query_type);
}





