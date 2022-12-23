/* Copyright (c) 2000, 2014, Oracle and/or its affiliates. All rights reserved.
   rights reserved.

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

  @brief
  Sum functions (COUNT, MIN...)
*/

#include "sql_priv.h"
#include "sql_class.h"
#include "sql_resolver.h"                  // setup_order, fix_inner_refs

using std::min;
using std::max;

/**
  Calculate the affordable RAM limit for structures like TREE or Unique
  used in Item_sum_*
*/

ulonglong Item_sum::ram_limitation(THD *thd)
{
  return min(thd->variables.tmp_table_size,
      thd->variables.max_heap_table_size);
}


/**
  Check constraints imposed on a usage of a set function.

    The method verifies whether context conditions imposed on a usage
    of any set function are met for this occurrence.
    It checks whether the set function occurs in the position where it
    can be aggregated and, when it happens to occur in argument of another
    set function, the method checks that these two functions are aggregated in
    different subqueries.
    If the context conditions are not met the method reports an error.
    If the set function is aggregated in some outer subquery the method
    adds it to the chain of items for such set functions that is attached
    to the the st_select_lex structure for this subquery.

    A number of designated members of the object are used to check the
    conditions. They are specified in the comment before the Item_sum
    class declaration.
    Additionally a bitmap variable called allow_sum_func is employed.
    It is included into the thd->lex structure.
    The bitmap contains 1 at n-th position if the set function happens
    to occur under a construct of the n-th level subquery where usage
    of set functions are allowed (i.e either in the SELECT list or
    in the HAVING clause of the corresponding subquery)
    Consider the query:
    @code
       SELECT SUM(t1.b) FROM t1 GROUP BY t1.a
         HAVING t1.a IN (SELECT t2.c FROM t2 WHERE AVG(t1.b) > 20) AND
                t1.a > (SELECT MIN(t2.d) FROM t2);
    @endcode
    allow_sum_func will contain: 
    - for SUM(t1.b) - 1 at the first position 
    - for AVG(t1.b) - 1 at the first position, 0 at the second position
    - for MIN(t2.d) - 1 at the first position, 1 at the second position.

  @param thd  reference to the thread context info
  @param ref  location of the pointer to this item in the embedding expression

  @note
    This function is to be called for any item created for a set function
    object when the traversal of trees built for expressions used in the query
    is performed at the phase of context analysis. This function is to
    be invoked at the ascent of this traversal.

  @retval
    TRUE   if an error is reported
  @retval
    FALSE  otherwise
*/
 
bool Item_sum::check_sum_func(THD *thd, Item **ref)
{
  bool invalid= FALSE;
  nesting_map allow_sum_func= thd->lex->allow_sum_func;
  /*  
    The value of max_arg_level is updated if an argument of the set function
    contains a column reference resolved  against a subquery whose level is
    greater than the current value of max_arg_level.
    max_arg_level cannot be greater than nest level.
    nest level is always >= 0  
  */
  if (nest_level == max_arg_level)
  {
    /*
      The function must be aggregated in the current subquery, 
      If it is there under a construct where it is not allowed 
      we report an error. 
    */ 
    invalid= !(allow_sum_func & ((nesting_map)1 << max_arg_level));
  }
  else if (max_arg_level >= 0 ||
           !(allow_sum_func & ((nesting_map)1 << nest_level)))
  {
    /*
      The set function can be aggregated only in outer subqueries.
      Try to find a subquery where it can be aggregated;
      If we fail to find such a subquery report an error.
    */
    if (register_sum_func(thd, ref))
      return TRUE;
    invalid= aggr_level < 0 &&
             !(allow_sum_func & ((nesting_map)1 << nest_level));
    if (!invalid && thd->variables.sql_mode & MODE_ANSI)
      invalid= aggr_level < 0 && max_arg_level < nest_level;
  }
  if (!invalid && aggr_level < 0)
  {
    aggr_level= nest_level;
    aggr_sel= thd->lex->current_select;
  }
  /*
    By this moment we either found a subquery where the set function is
    to be aggregated  and assigned a value that is  >= 0 to aggr_level,
    or set the value of 'invalid' to TRUE to report later an error. 
  */
  /* 
    Additionally we have to check whether possible nested set functions
    are acceptable here: they are not, if the level of aggregation of
    some of them is less than aggr_level.
  */
  if (!invalid) 
    invalid= aggr_level <= max_sum_func_level;
  if (invalid)  
  {
    my_message(ER_INVALID_GROUP_FUNC_USE, ER(ER_INVALID_GROUP_FUNC_USE),
               MYF(0));
    return TRUE;
  }

  if (in_sum_func)
  {
    /*
      If the set function is nested adjust the value of
      max_sum_func_level for the nesting set function.
      We take into account only enclosed set functions that are to be 
      aggregated on the same level or above of the nest level of 
      the enclosing set function.
      But we must always pass up the max_sum_func_level because it is
      the maximum nested level of all directly and indirectly enclosed
      set functions. We must do that even for set functions that are
      aggregated inside of their enclosing set function's nest level
      because the enclosing function may contain another enclosing
      function that is to be aggregated outside or on the same level
      as its parent's nest level.
    */
    if (in_sum_func->nest_level >= aggr_level)
      set_if_bigger(in_sum_func->max_sum_func_level, aggr_level);
    set_if_bigger(in_sum_func->max_sum_func_level, max_sum_func_level);
  }

  /*
    Check that non-aggregated fields and sum functions aren't mixed in the
    same select in the ONLY_FULL_GROUP_BY mode.
  */
  if (outer_fields.elements)
  {
    Item_field *field;
    /*
      Here we compare the nesting level of the select to which an outer field
      belongs to with the aggregation level of the sum function. All fields in
      the outer_fields list are checked.

      If the nesting level is equal to the aggregation level then the field is
        aggregated by this sum function.
      If the nesting level is less than the aggregation level then the field
        belongs to an outer select. In this case if there is an embedding sum
        function add current field to functions outer_fields list. If there is
        no embedding function then the current field treated as non aggregated
        and the select it belongs to is marked accordingly.
      If the nesting level is greater than the aggregation level then it means
        that this field was added by an inner sum function.
        Consider an example:

          select avg ( <-- we are here, checking outer.f1
            select (
              select sum(outer.f1 + inner.f1) from inner
            ) from outer)
          from most_outer;

        In this case we check that no aggregate functions are used in the
        select the field belongs to. If there are some then an error is
        raised.
    */
    List_iterator<Item_field> of(outer_fields);
    while ((field= of++))
    {
      SELECT_LEX *sel= field->cached_table->select_lex;
      if (sel->nest_level < aggr_level)
      {
        if (in_sum_func)
        {
          /*
            Let upper function decide whether this field is a non
            aggregated one.
          */
          in_sum_func->outer_fields.push_back(field);
        }
        else
          sel->set_non_agg_field_used(true);
      }
      if (sel->nest_level > aggr_level &&
          (sel->agg_func_used()) &&
          !sel->group_list.elements)
      {
        my_message(ER_MIX_OF_GROUP_FUNC_AND_FIELDS,
                   ER(ER_MIX_OF_GROUP_FUNC_AND_FIELDS), MYF(0));
        return TRUE;
      }
    }
  }
  aggr_sel->set_agg_func_used(true);
  thd->lex->in_sum_func= in_sum_func;
  return FALSE;
}

/**
  Attach a set function to the subquery where it must be aggregated.

    The function looks for an outer subquery where the set function must be
    aggregated. If it finds such a subquery then aggr_level is set to
    the nest level of this subquery and the item for the set function
    is added to the list of set functions used in nested subqueries
    inner_sum_func_list defined for each subquery. When the item is placed 
    there the field 'ref_by' is set to ref.

  @note
    Now we 'register' only set functions that are aggregated in outer
    subqueries. Actually it makes sense to link all set function for
    a subquery in one chain. It would simplify the process of 'splitting'
    for set functions.

  @param thd  reference to the thread context info
  @param ref  location of the pointer to this item in the embedding expression

  @retval
    FALSE  if the executes without failures (currently always)
  @retval
    TRUE   otherwise
*/  

bool Item_sum::register_sum_func(THD *thd, Item **ref)
{
  nesting_map allow_sum_func= thd->lex->allow_sum_func;

  // Find the outer-most query block where this function can be aggregated.

  for (SELECT_LEX *sl= thd->lex->current_select->outer_select();
       sl && sl->nest_level >= max_arg_level;
       sl= sl->outer_select())
  {
    if (allow_sum_func & ((nesting_map)1 << sl->nest_level))
    {
      aggr_level= sl->nest_level;
      aggr_sel= sl;
    }
    /*
      Cannot go above level zero. This might be possible in 5.6 because the
      nest_level of the query blocks of a view are not adjusted when the view
      is attached to the outer query. However, 5.7 adjusts nest_level
      correctly, so this code is only necessary in 5.6.
    */
    if (sl->nest_level == 0)
      break;
  }

  if (aggr_level >= 0)
  {
    ref_by= ref;
    /* Add the object to the list of registered objects assigned to aggr_sel */
    if (!aggr_sel->inner_sum_func_list)
      next= this;
    else
    {
      next= aggr_sel->inner_sum_func_list->next;
      aggr_sel->inner_sum_func_list->next= this;
    }
    aggr_sel->inner_sum_func_list= this;
    aggr_sel->with_sum_func= true;

    /* 
      Mark Item_subselect(s) as containing aggregate function all the way up
      to aggregate function's calculation context.
      Note that we must not mark the Item of calculation context itself
      because with_sum_func on the calculation context st_select_lex is
      already set above.

      with_sum_func being set for an Item means that this Item refers 
      (somewhere in it, e.g. one of its arguments if it's a function) directly
      or through intermediate items to an aggregate function that is calculated
      in a context "outside" of the Item (e.g. in the current or outer select).

      with_sum_func being set for an st_select_lex means that this query block
      has aggregate functions directly referenced (i.e. not through a subquery).
    */
    for (SELECT_LEX *sl= thd->lex->current_select; 
         sl && sl != aggr_sel && sl->master_unit()->item;
         sl= sl->outer_select())
      sl->master_unit()->item->with_sum_func= true;
  }
  thd->lex->current_select->mark_as_dependent(aggr_sel);
  return false;
}


Item_sum::Item_sum(List<Item> &list) :next(NULL), arg_count(list.elements), 
  forced_const(FALSE)
{
  if ((args=(Item**) sql_alloc(sizeof(Item*)*arg_count)))
  {
    uint i=0;
    List_iterator_fast<Item> li(list);
    Item *item;

    while ((item=li++))
    {
      args[i++]= item;
    }
  }
  if (!(orig_args= (Item **) sql_alloc(sizeof(Item *) * arg_count)))
  {
    args= NULL;
  }
  mark_as_sum_func();
  init_aggregator();
  list.empty();					// Fields are used
}


/**
  Constructor used in processing select with temporary tebles.
*/

Item_sum::Item_sum(THD *thd, Item_sum *item):
  next(NULL),
  aggr_sel(item->aggr_sel),
  nest_level(item->nest_level), aggr_level(item->aggr_level),
  quick_group(item->quick_group),
  arg_count(item->arg_count), orig_args(NULL),
  used_tables_cache(item->used_tables_cache),
  forced_const(item->forced_const) 
{
  if (arg_count <= 2)
  {
    args=tmp_args;
    orig_args=tmp_orig_args;
  }
  else
  {
    if (!(args= (Item**) thd->alloc(sizeof(Item*)*arg_count)))
      return;
    if (!(orig_args= (Item**) thd->alloc(sizeof(Item*)*arg_count)))
      return;
  }
  memcpy(args, item->args, sizeof(Item*)*arg_count);
  memcpy(orig_args, item->orig_args, sizeof(Item*)*arg_count);
  init_aggregator();
  with_distinct= item->with_distinct;
  if (item->aggr)
    set_aggregator(item->aggr->Aggrtype());
}


void Item_sum::mark_as_sum_func()
{
  SELECT_LEX *cur_select= current_thd->lex->current_select;
  cur_select->n_sum_items++;
  cur_select->with_sum_func= 1;
  with_sum_func= 1;
}


void Item_sum::print(String *str, enum_query_type query_type)
{
  /* orig_args is not filled with valid values until fix_fields() */
  Item **pargs= fixed ? orig_args : args;
  str->append(func_name());
  for (uint i=0 ; i < arg_count ; i++)
  {
    if (i)
      str->append(',');
    pargs[i]->print(str, query_type);
  }
  str->append(')');
}

bool Item_sum::walk (Item_processor processor, bool walk_subquery,
                     uchar *argument)
{
  if (arg_count)
  {
    Item **arg,**arg_end;
    for (arg= args, arg_end= args+arg_count; arg != arg_end; arg++)
    {
      if ((*arg)->walk(processor, walk_subquery, argument))
	return 1;
    }
  }
  return (this->*processor)(argument);
}

Item *Item_sum::set_arg(uint i, THD *thd, Item *new_val) 
{
  thd->change_item_tree(args + i, new_val);
  return new_val;
}


int Item_sum::set_aggregator(Aggregator::Aggregator_type aggregator)
{
  /*
    Dependent subselects may be executed multiple times, making
    set_aggregator to be called multiple times. The aggregator type
    will be the same, but it needs to be reset so that it is
    reevaluated with the new dependent data.
    This function may also be called multiple times during query optimization.
    In this case, the type may change, so we delete the old aggregator,
    and create a new one.
  */
  if (aggr && aggregator == aggr->Aggrtype())
  {
    return FALSE;
  }

  delete aggr;
  switch (aggregator)
  {
  case Aggregator::DISTINCT_AGGREGATOR:
    aggr= new Aggregator_distinct(this);
    break;
  case Aggregator::SIMPLE_AGGREGATOR:
    aggr= new Aggregator_simple(this);
    break;
  };
  return aggr ? FALSE : TRUE;
}



Aggregator_distinct::~Aggregator_distinct()
{
}


/*
  Variance
*/


Item_sum_variance::Item_sum_variance(THD *thd, Item_sum_variance *item):
  Item_sum_num(thd, item), hybrid_type(item->hybrid_type),
    count(item->count), sample(item->sample),
    prec_increment(item->prec_increment)
{
  recurrence_m= item->recurrence_m;
  recurrence_s= item->recurrence_s;
}

/****************************************************************************
** Functions to handle dynamic loadable aggregates
** Original source by: Alexis Mikhailov <root@medinf.chuvashia.su>
** Adapted for UDAs by: Andreas F. Bobak <bobak@relog.ch>.
** Rewritten by: Monty.
****************************************************************************/

#ifdef HAVE_DLOPEN

void Item_udf_sum::print(String *str, enum_query_type query_type)
{
  str->append(func_name());
  str->append('(');
  for (uint i=0 ; i < arg_count ; i++)
  {
    if (i)
      str->append(',');
    args[i]->print(str, query_type);
  }
  str->append(')');
}

double Item_sum_udf_float::val_real()
{
  DBUG_ASSERT(fixed == 1);
  DBUG_ENTER("Item_sum_udf_float::val");
  DBUG_PRINT("info",("result_type: %d  arg_count: %d",
		     args[0]->result_type(), arg_count));
  DBUG_RETURN(udf.val(&null_value));
}


String *Item_sum_udf_float::val_str(String *str)
{
  return val_string_from_real(str);
}


my_decimal *Item_sum_udf_float::val_decimal(my_decimal *dec)
{
  return val_decimal_from_real(dec);
}


String *Item_sum_udf_decimal::val_str(String *str)
{
  return val_string_from_decimal(str);
}


double Item_sum_udf_decimal::val_real()
{
  return val_real_from_decimal();
}


longlong Item_sum_udf_decimal::val_int()
{
  return val_int_from_decimal();
}


my_decimal *Item_sum_udf_decimal::val_decimal(my_decimal *dec_buf)
{
  DBUG_ASSERT(fixed == 1);
  DBUG_ENTER("Item_func_udf_decimal::val_decimal");
  DBUG_PRINT("info",("result_type: %d  arg_count: %d",
                     args[0]->result_type(), arg_count));

  DBUG_RETURN(udf.val_decimal(&null_value, dec_buf));
}

longlong Item_sum_udf_int::val_int()
{
  DBUG_ASSERT(fixed == 1);
  DBUG_ENTER("Item_sum_udf_int::val_int");
  DBUG_PRINT("info",("result_type: %d  arg_count: %d",
		     args[0]->result_type(), arg_count));
  DBUG_RETURN(udf.val_int(&null_value));
}


String *Item_sum_udf_int::val_str(String *str)
{
  return val_string_from_int(str);
}

my_decimal *Item_sum_udf_int::val_decimal(my_decimal *dec)
{
  return val_decimal_from_int(dec);
}




my_decimal *Item_sum_udf_str::val_decimal(my_decimal *dec)
{
  return val_decimal_from_string(dec);
}

String *Item_sum_udf_str::val_str(String *str)
{
  DBUG_ASSERT(fixed == 1);
  DBUG_ENTER("Item_sum_udf_str::str");
  String *res=udf.val_str(str,&str_value);
  null_value = !res;
  DBUG_RETURN(res);
}

#endif /* HAVE_DLOPEN */


/*****************************************************************************
 GROUP_CONCAT function

 SQL SYNTAX:
  GROUP_CONCAT([DISTINCT] expr,... [ORDER BY col [ASC|DESC],...]
    [SEPARATOR str_const])

 concat of values from "group by" operation

 BUGS
   Blobs doesn't work with DISTINCT or ORDER BY
*****************************************************************************/



/**
  Constructor of Item_func_group_concat.

  @param distinct_arg   distinct
  @param select_list    list of expression for show values
  @param order_list     list of sort columns
  @param separator_arg  string value of separator.
*/

Item_func_group_concat::
Item_func_group_concat(Name_resolution_context *context_arg,
                       bool distinct_arg, List<Item> *select_list,
                       const SQL_I_List<ORDER> &order_list,
                       String *separator_arg)
  :separator(separator_arg), tree(0),
   order(0), context(context_arg),
   arg_count_order(order_list.elements),
   arg_count_field(select_list->elements),
   row_count(0),
   distinct(distinct_arg),
   warning_for_row(FALSE),
   force_copy_fields(0), original(0)
{
  Item *item_select;
  Item **arg_ptr;

  quick_group= FALSE;
  arg_count= arg_count_field + arg_count_order;

  /*
    We need to allocate:
    args - arg_count_field+arg_count_order
           (for possible order items in temporare tables)
    order - arg_count_order
  */
  if (!(args= (Item**) sql_alloc(sizeof(Item*) * arg_count +
                                 sizeof(ORDER*)*arg_count_order)))
    return;

  if (!(orig_args= (Item **) sql_alloc(sizeof(Item *) * arg_count)))
  {
    args= NULL;
    return;
  }

  order= (ORDER**)(args + arg_count);

  /* fill args items of show and sort */
  List_iterator_fast<Item> li(*select_list);

  for (arg_ptr=args ; (item_select= li++) ; arg_ptr++)
    *arg_ptr= item_select;

  if (arg_count_order)
  {
    ORDER **order_ptr= order;
    for (ORDER *order_item= order_list.first;
         order_item != NULL;
         order_item= order_item->next)
    {
      (*order_ptr++)= order_item;
      *arg_ptr= *order_item->item;
      order_item->item= arg_ptr++;
    }
  }
  memcpy(orig_args, args, sizeof(Item*) * arg_count);
}


Item_func_group_concat::Item_func_group_concat(THD *thd,
                                               Item_func_group_concat *item)
  :Item_sum(thd, item),
  separator(item->separator),
  tree(item->tree),
  context(item->context),
  arg_count_order(item->arg_count_order),
  arg_count_field(item->arg_count_field),
  row_count(item->row_count),
  distinct(item->distinct),
  warning_for_row(item->warning_for_row),
  always_null(item->always_null),
  force_copy_fields(item->force_copy_fields),
  original(item)
{
  quick_group= item->quick_group;
  result.set_charset(collation.collation);

  /*
    Since the ORDER structures pointed to by the elements of the 'order' array
    may be modified in find_order_in_list() called from
    Item_func_group_concat::setup(), create a copy of those structures so that
    such modifications done in this object would not have any effect on the
    object being copied.
  */
  ORDER *tmp;
  if (!(order= (ORDER **) thd->alloc(sizeof(ORDER *) * arg_count_order +
                                     sizeof(ORDER) * arg_count_order)))
    return;
  tmp= (ORDER *)(order + arg_count_order);
  for (uint i= 0; i < arg_count_order; i++, tmp++)
  {
    /*
      Compiler generated copy constructor is used to
      to copy all the members of ORDER struct.
      It's also necessary to update ORDER::next pointer
      so that it points to new ORDER element.
    */
    new (tmp) st_order(*(item->order[i])); 
    tmp->next= (i + 1 == arg_count_order) ? NULL : (tmp + 1);
    order[i]= tmp;
  }
}


void Item_func_group_concat::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("group_concat("));
  if (distinct)
    str->append(STRING_WITH_LEN("distinct "));
  for (uint i= 0; i < arg_count_field; i++)
  {
    if (i)
      str->append(',');
    orig_args[i]->print(str, query_type);
  }
  if (arg_count_order)
  {
    str->append(STRING_WITH_LEN(" order by "));
    for (uint i= 0 ; i < arg_count_order ; i++)
    {
      if (i)
        str->append(',');
      orig_args[i + arg_count_field]->print(str, query_type);
      if (order[i]->direction == ORDER::ORDER_ASC)
        str->append(STRING_WITH_LEN(" ASC"));
      else
        str->append(STRING_WITH_LEN(" DESC"));
    }
  }
  str->append(STRING_WITH_LEN(" separator \'"));
  str->append(*separator);
  str->append(STRING_WITH_LEN("\')"));
}


Item_func_group_concat::~Item_func_group_concat()
{
}
