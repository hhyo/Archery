/* Copyright (c) 2006, 2013, Oracle and/or its affiliates. All rights reserved.

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

/* Some general useful functions */

#include "sql_priv.h"
// Required to get server definitions for mysql/plugin.h right
#include "sql_plugin.h"
#include "sql_partition.h"                 // partition_info.h: LIST_PART_ENTRY
                                           // NOT_A_PARTITION_ID
#include "partition_info.h"
#include "sql_acl.h"                          // *_ACL
#include "table.h"                            // TABLE_LIST
#include "my_bitmap.h"                        // bitmap*
#include "sql_base.h"                         // fill_record

#ifdef WITH_PARTITION_STORAGE_ENGINE



/*
  Set fields related to partition expression
  SYNOPSIS
    set_part_expr()
    start_token               Start of partition function string
    item_ptr                  Pointer to item tree
    end_token                 End of partition function string
    is_subpart                Subpartition indicator
  RETURN VALUES
    TRUE                      Memory allocation error
    FALSE                     Success
*/

bool partition_info::set_part_expr(char *start_token, Item *item_ptr,
                                   char *end_token, bool is_subpart)
{
  uint expr_len= end_token - start_token;
  char *func_string= (char*) sql_memdup(start_token, expr_len);

  if (!func_string)
  {
    mem_alloc_error(expr_len);
    return TRUE;
  }
  if (is_subpart)
  {
    list_of_subpart_fields= FALSE;
    subpart_expr= item_ptr;
    subpart_func_string= func_string;
    subpart_func_len= expr_len;
  }
  else
  {
    list_of_part_fields= FALSE;
    part_expr= item_ptr;
    part_func_string= func_string;
    part_func_len= expr_len;
  }
  return FALSE;
}

 

/**
  Create a new column value in current list with maxvalue.

  @return Operation status
    @retval TRUE   Error
    @retval FALSE  Success

  @note Called from parser.
*/

bool partition_info::add_max_value()
{
  DBUG_ENTER("partition_info::add_max_value");

  part_column_list_val *col_val;
  if (!(col_val= add_column_value()))
  {
    DBUG_RETURN(TRUE);
  }
  col_val->max_value= TRUE;
  DBUG_RETURN(FALSE);
}


/**
  Create a new column value in current list.

  @return Pointer to a new part_column_list_val
    @retval  != 0  A part_column_list_val object which have been
                   inserted into its list
    @retval  NULL  Memory allocation failure
    
  @note Called from parser.
*/

part_column_list_val *partition_info::add_column_value()
{
  uint max_val= num_columns ? num_columns : MAX_REF_PARTS;
  DBUG_ENTER("add_column_value");
  DBUG_PRINT("enter", ("num_columns = %u, curr_list_object %u, max_val = %u",
                        num_columns, curr_list_object, max_val));
  if (curr_list_object < max_val)
  {
    curr_list_val->added_items++;
    DBUG_RETURN(&curr_list_val->col_val_array[curr_list_object++]);
  }
  if (!num_columns && part_type == LIST_PARTITION)
  {
    /*
      We're trying to add more than MAX_REF_PARTS, this can happen
      in ALTER TABLE using List partitions where the first partition
      uses VALUES IN (1,2,3...,17) where the number of fields in
      the list is more than MAX_REF_PARTS, in this case we know
      that the number of columns must be 1 and we thus reorganize
      into the structure used for 1 column. After this we call
      ourselves recursively which should always succeed.
    */
    if (!reorganize_into_single_field_col_val() && !init_column_part())
    {
      DBUG_RETURN(add_column_value());
    }
    DBUG_RETURN(NULL);
  }
  if (column_list)
  {
    my_error(ER_PARTITION_COLUMN_LIST_ERROR, MYF(0));
  }
  else
  {
    if (part_type == RANGE_PARTITION)
      my_error(ER_TOO_MANY_VALUES_ERROR, MYF(0), "RANGE");
    else
      my_error(ER_TOO_MANY_VALUES_ERROR, MYF(0), "LIST");
  }
  DBUG_RETURN(NULL);
}


/**
  Initialise part_elem_value object at setting of a new object.

  @param col_val  Column value object to be initialised
  @param item     Item object representing column value

  @return Operation status
    @retval TRUE   Failure
    @retval FALSE  Success

  @note Helper functions to functions called by parser.
*/

void partition_info::init_col_val(part_column_list_val *col_val, Item *item)
{
  DBUG_ENTER("partition_info::init_col_val");

  col_val->item_expression= item;
  col_val->null_value= item->null_value;
  if (item->result_type() == INT_RESULT)
  {
    /*
      This could be both column_list partitioning and function
      partitioning, but it doesn't hurt to set the function
      partitioning flags about unsignedness.
    */
    curr_list_val->value= item->val_int();
    curr_list_val->unsigned_flag= TRUE;
    if (!item->unsigned_flag &&
        curr_list_val->value < 0)
      curr_list_val->unsigned_flag= FALSE;
    if (!curr_list_val->unsigned_flag)
      curr_part_elem->signed_flag= TRUE;
  }
  col_val->part_info= NULL;
  DBUG_VOID_RETURN;
}


/**
  Add a column value in VALUES LESS THAN or VALUES IN.

  @param thd   Thread object
  @param item  Item object representing column value

  @return Operation status
    @retval TRUE   Failure
    @retval FALSE  Success

  @note Called from parser.
*/

bool partition_info::add_column_list_value(THD *thd, Item *item)
{
  part_column_list_val *col_val;
  Name_resolution_context *context= &thd->lex->current_select->context;
  TABLE_LIST *save_list= context->table_list;
  const char *save_where= thd->where;
  DBUG_ENTER("partition_info::add_column_list_value");

  if (part_type == LIST_PARTITION &&
      num_columns == 1U)
  {
    if (init_column_part())
    {
      DBUG_RETURN(TRUE);
    }
  }

  context->table_list= 0;
  if (column_list)
    thd->where= "field list";
  else
    thd->where= "partition function";

  if (item->walk(&Item::check_partition_func_processor, 0,
                 NULL))
  {
    my_error(ER_PARTITION_FUNCTION_IS_NOT_ALLOWED, MYF(0));
    DBUG_RETURN(TRUE);
  }
  if (((context->table_list= save_list), FALSE) ||
      (!item->const_item()))
  {
    context->table_list= save_list;
    thd->where= save_where;
    my_error(ER_PARTITION_FUNCTION_IS_NOT_ALLOWED, MYF(0));
    DBUG_RETURN(TRUE);
  }
  thd->where= save_where;

  if (!(col_val= add_column_value()))
  {
    DBUG_RETURN(TRUE);
  }
  init_col_val(col_val, item);
  DBUG_RETURN(FALSE);
}


/**
  Initialize a new column for VALUES {LESS THAN|IN}.

  Initialize part_info object for receiving a set of column values
  for a partition, called when parser reaches VALUES LESS THAN or
  VALUES IN.

  @return Operation status
    @retval TRUE   Failure
    @retval FALSE  Success
*/

bool partition_info::init_column_part()
{
  partition_element *p_elem= curr_part_elem;
  part_column_list_val *col_val_array;
  part_elem_value *list_val;
  uint loc_num_columns;
  DBUG_ENTER("partition_info::init_column_part");

  if (!(list_val=
      (part_elem_value*)sql_calloc(sizeof(part_elem_value))) ||
       p_elem->list_val_list.push_back(list_val))
  {
    mem_alloc_error(sizeof(part_elem_value));
    DBUG_RETURN(TRUE);
  }
  if (num_columns)
    loc_num_columns= num_columns;
  else
    loc_num_columns= MAX_REF_PARTS;
  if (!(col_val_array=
        (part_column_list_val*)sql_calloc(loc_num_columns *
         sizeof(part_column_list_val))))
  {
    mem_alloc_error(loc_num_columns * sizeof(part_elem_value));
    DBUG_RETURN(TRUE);
  }
  list_val->col_val_array= col_val_array;
  list_val->added_items= 0;
  curr_list_val= list_val;
  curr_list_object= 0;
  DBUG_RETURN(FALSE);
}


/**
  Reorganize the preallocated buffer into a single field col list.

  @return Operation status
    @retval  true   Failure
    @retval  false  Success

  @note In the case of ALTER TABLE ADD/REORGANIZE PARTITION for LIST
  partitions we can specify list values as:
  VALUES IN (v1, v2,,,, v17) if we're using the first partitioning
  variant with a function or a column list partitioned table with
  one partition field. In this case the parser knows not the
  number of columns start with and allocates MAX_REF_PARTS in the
  array. If we try to allocate something beyond MAX_REF_PARTS we
  will call this function to reorganize into a structure with
  num_columns = 1. Also when the parser knows that we used LIST
  partitioning and we used a VALUES IN like above where number of
  values was smaller than MAX_REF_PARTS or equal, then we will
  reorganize after discovering this in the parser.
*/

bool partition_info::reorganize_into_single_field_col_val()
{
  part_column_list_val *col_val, *new_col_val;
  part_elem_value *val= curr_list_val;
  uint num_values= num_columns;
  uint i;
  DBUG_ENTER("partition_info::reorganize_into_single_field_col_val");
  DBUG_ASSERT(part_type == LIST_PARTITION);
  DBUG_ASSERT(!num_columns || num_columns == val->added_items);

  if (!num_values)
    num_values= val->added_items;
  num_columns= 1;
  val->added_items= 1U;
  col_val= &val->col_val_array[0];
  init_col_val(col_val, col_val->item_expression);
  for (i= 1; i < num_values; i++)
  {
    col_val= &val->col_val_array[i];
    if (init_column_part())
    {
      DBUG_RETURN(TRUE);
    }
    if (!(new_col_val= add_column_value()))
    {
      DBUG_RETURN(TRUE);
    }
    memcpy(new_col_val, col_val, sizeof(*col_val));
    init_col_val(new_col_val, col_val->item_expression);
  }
  curr_list_val= val;
  DBUG_RETURN(FALSE);
}





void partition_info::print_debug(const char *str, uint *value)
{
  DBUG_ENTER("print_debug");
  if (value)
    DBUG_PRINT("info", ("parser: %s, val = %u", str, *value));
  else
    DBUG_PRINT("info", ("parser: %s", str));
  DBUG_VOID_RETURN;
}
#else /* WITH_PARTITION_STORAGE_ENGINE */
 /*
   For builds without partitioning we need to define these functions
   since we they are called from the parser. The parser cannot
   remove code parts using ifdef, but the code parts cannot be called
   so we simply need to add empty functions to make the linker happy.
 */
part_column_list_val *partition_info::add_column_value()
{
  return NULL;
}

bool partition_info::set_part_expr(char *start_token, Item *item_ptr,
                                   char *end_token, bool is_subpart)
{
  (void)start_token;
  (void)item_ptr;
  (void)end_token;
  (void)is_subpart;
  return FALSE;
}

bool partition_info::reorganize_into_single_field_col_val()
{
  return 0;
}

bool partition_info::init_column_part()
{
  return FALSE;
}

bool partition_info::add_column_list_value(THD *thd, Item *item)
{
  return FALSE;
}

bool partition_info::add_max_value()
{
  return false;
}

void partition_info::print_debug(const char *str, uint *value)
{
}

#endif /* WITH_PARTITION_STORAGE_ENGINE */
