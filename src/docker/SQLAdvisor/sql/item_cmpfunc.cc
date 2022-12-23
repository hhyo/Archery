/* Copyright (c) 2000, 2013, Oracle and/or its affiliates. All rights reserved.

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
  This file defines all compare functions
*/

#include "sql_priv.h"
#include <m_ctype.h>
#include "sql_parse.h"                          // check_stack_overrun
#include "sql_time.h"                  // make_truncated_value_warning

#include <algorithm>
using std::min;
using std::max;

/*
  Compare row signature of two expressions

  SYNOPSIS:
    cmp_row_type()
    item1          the first expression
    item2         the second expression

  DESCRIPTION
    The function checks that two expressions have compatible row signatures
    i.e. that the number of columns they return are the same and that if they
    are both row expressions then each component from the first expression has 
    a row signature compatible with the signature of the corresponding component
    of the second expression.

  RETURN VALUES
    1  type incompatibility has been detected
    0  otherwise
*/

static int cmp_row_type(Item* item1, Item* item2)
{
  uint n= item1->cols();
  if (item2->check_cols(n))
    return 1;
  for (uint i=0; i<n; i++)
  {
    if (item2->element_index(i)->check_cols(item1->element_index(i)->cols()) ||
        (item1->element_index(i)->result_type() == ROW_RESULT &&
         cmp_row_type(item1->element_index(i), item2->element_index(i))))
      return 1;
  }
  return 0;
}



Item_bool_func2* Eq_creator::create(Item *a, Item *b) const
{
  return new Item_func_eq(a, b);
}


Item_bool_func2* Ne_creator::create(Item *a, Item *b) const
{
  return new Item_func_ne(a, b);
}


Item_bool_func2* Gt_creator::create(Item *a, Item *b) const
{
  return new Item_func_gt(a, b);
}


Item_bool_func2* Lt_creator::create(Item *a, Item *b) const
{
  return new Item_func_lt(a, b);
}


Item_bool_func2* Ge_creator::create(Item *a, Item *b) const
{
  return new Item_func_ge(a, b);
}


Item_bool_func2* Le_creator::create(Item *a, Item *b) const
{
  return new Item_func_le(a, b);
}
/*
  We put any NOT expression into parenthesis to avoid
  possible problems with internal view representations where
  any '!' is converted to NOT. It may cause a problem if
  '!' is used in an expression together with other operators
  whose precedence is lower than the precedence of '!' yet
  higher than the precedence of NOT.
*/

void Item_func_not::print(String *str, enum_query_type query_type)
{
  str->append('(');
  Item_func::print(str, query_type);
  str->append(')');
}

void Item_func_not_all::print(String *str, enum_query_type query_type)
{
  if (show)
    Item_func::print(str, query_type);
  else
    args[0]->print(str, query_type);
}

/**
  Parse date provided in a string to a MYSQL_TIME.

  @param[in]   thd        Thread handle
  @param[in]   str        A string to convert
  @param[in]   warn_type  Type of the timestamp for issuing the warning
  @param[in]   warn_name  Field name for issuing the warning
  @param[out]  l_time     The MYSQL_TIME objects is initialized.

  Parses a date provided in the string str into a MYSQL_TIME object. If the
  string contains an incorrect date or doesn't correspond to a date at all
  then a warning is issued. The warn_type and the warn_name arguments are used
  as the name and the type of the field when issuing the warning. If any input
  was discarded (trailing or non-timestamp-y characters), return value will be
  TRUE.

  @return Status flag
  @retval FALSE Success.
  @retval True Indicates failure.
*/

bool get_mysql_time_from_str(THD *thd, String *str, timestamp_type warn_type, 
                             const char *warn_name, MYSQL_TIME *l_time)
{
  bool value;
  MYSQL_TIME_STATUS status;

  if (!str_to_datetime(str, l_time,
                      (TIME_FUZZY_DATE | MODE_INVALID_DATES |
                       (thd->variables.sql_mode &
                       (MODE_NO_ZERO_IN_DATE | MODE_NO_ZERO_DATE))), &status) &&
      (l_time->time_type == MYSQL_TIMESTAMP_DATETIME || 
       l_time->time_type == MYSQL_TIMESTAMP_DATE))
    /*
      Do not return yet, we may still want to throw a "trailing garbage"
      warning.
    */
    value= FALSE;
  else
  {
    value= TRUE;
    status.warnings= MYSQL_TIME_WARN_TRUNCATED;  /* force warning */
  }

  if (status.warnings > 0)
    make_truncated_value_warning(thd, Sql_condition::WARN_LEVEL_WARN,
                                 ErrConvString(str), warn_type, warn_name);

  return value;
}


/**
  @brief Convert date provided in a string
  to its packed temporal int representation.

  @param[in]   thd        thread handle
  @param[in]   str        a string to convert
  @param[in]   warn_type  type of the timestamp for issuing the warning
  @param[in]   warn_name  field name for issuing the warning
  @param[out]  error_arg  could not extract a DATE or DATETIME

  @details Convert date provided in the string str to the int
    representation.  If the string contains wrong date or doesn't
    contain it at all then a warning is issued.  The warn_type and
    the warn_name arguments are used as the name and the type of the
    field when issuing the warning.

  @return
    converted value. 0 on error and on zero-dates -- check 'failure'
*/
static ulonglong get_date_from_str(THD *thd, String *str, 
                                   timestamp_type warn_type, 
                                   const char *warn_name, bool *error_arg)
{
  MYSQL_TIME l_time;
  *error_arg= get_mysql_time_from_str(thd, str, warn_type, warn_name, &l_time);

  if (*error_arg)
    return 0;
  return TIME_to_longlong_datetime_packed(&l_time);
}

/*
  Retrieves correct DATETIME value from given item.

  SYNOPSIS
    get_datetime_value()
    thd                 thread handle
    item_arg   [in/out] item to retrieve DATETIME value from
    cache_arg  [in/out] pointer to place to store the caching item to
    warn_item  [in]     item for issuing the conversion warning
    is_null    [out]    TRUE <=> the item_arg is null

  DESCRIPTION
    Retrieves the correct DATETIME value from given item for comparison by the
    compare_datetime() function.
    If item's result can be compared as longlong then its int value is used
    and its string value is used otherwise. Strings are always parsed and
    converted to int values by the get_date_from_str() function.
    This allows us to compare correctly string dates with missed insignificant
    zeros. If an item is a constant one then its value is cached and it isn't
    get parsed again. An Item_cache_int object is used for caching values. It
    seamlessly substitutes the original item.  The cache item is marked as
    non-constant to prevent re-caching it again.  In order to compare
    correctly DATE and DATETIME items the result of the former are treated as
    a DATETIME with zero time (00:00:00).

  RETURN
    obtained value
*/


longlong
get_datetime_value(THD *thd, Item ***item_arg, Item **cache_arg,
                   Item *warn_item, bool *is_null)
{
  longlong value= 0;
  String buf, *str= 0;
  Item *item= **item_arg;

  if (item->is_temporal())
  {
//    value= item->val_date_temporal();
    *is_null= item->null_value;
  }
  else
  {
    str= item->val_str(&buf);
    *is_null= item->null_value;
  }
  if (*is_null)
    return ~(ulonglong) 0;
  /*
    Convert strings to the integer DATE/DATETIME representation.
    Even if both dates provided in strings we can't compare them directly as
    strings as there is no warranty that they are correct and do not miss
    some insignificant zeros.
  */
  if (str)
  {
    bool error;
    enum_field_types f_type= warn_item->field_type();
    timestamp_type t_type= f_type ==
      MYSQL_TYPE_DATE ? MYSQL_TIMESTAMP_DATE : MYSQL_TIMESTAMP_DATETIME;
    value= (longlong) get_date_from_str(thd, str, t_type, warn_item->item_name.ptr(), &error);
    /*
      If str did not contain a valid date according to the current
      SQL_MODE, get_date_from_str() has already thrown a warning,
      and we don't want to throw NULL on invalid date (see 5.2.6
      "SQL modes" in the manual), so we're done here.
    */
  }
  return value;
}


/*
  Compare items values as dates.

  SYNOPSIS
    Arg_comparator::compare_datetime()

  DESCRIPTION
    Compare items values as DATE/DATETIME for both EQUAL_FUNC and from other
    comparison functions. The correct DATETIME values are obtained
    with help of the get_datetime_value() function.

  RETURN
    If is_nulls_eq is TRUE:
       1    if items are equal or both are null
       0    otherwise
    If is_nulls_eq is FALSE:
      -1   a < b or at least one item is null
       0   a == b
       1   a > b
    See the table:
    is_nulls_eq | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
    a_is_null   | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 |
    b_is_null   | 1 | 1 | 0 | 0 | 1 | 1 | 0 | 0 |
    result      | 1 | 0 | 0 |0/1|-1 |-1 |-1 |-1/0/1|
*/

int Arg_comparator::compare_datetime()
{
  bool a_is_null, b_is_null;
  longlong a_value, b_value;

  /* Get DATE/DATETIME/TIME value of the 'a' item. */
  a_value= (*get_value_a_func)(thd, &a, &a_cache, *b, &a_is_null);
  if (!is_nulls_eq && a_is_null)
  {
    if (set_null)
      owner->null_value= 1;
    return -1;
  }

  /* Get DATE/DATETIME/TIME value of the 'b' item. */
  b_value= (*get_value_b_func)(thd, &b, &b_cache, *a, &b_is_null);
  if (a_is_null || b_is_null)
  {
    if (set_null)
      owner->null_value= is_nulls_eq ? 0 : 1;
    return is_nulls_eq ? (a_is_null == b_is_null) : -1;
  }

  /* Here we have two not-NULL values. */
  if (set_null)
    owner->null_value= 0;

  /* Compare values. */
  if (is_nulls_eq)
    return (a_value == b_value);
  return a_value < b_value ? -1 : (a_value > b_value ? 1 : 0);
}


int Arg_comparator::compare_string()
{
  String *res1,*res2;
  if ((res1= (*a)->val_str(&value1)))
  {
    if ((res2= (*b)->val_str(&value2)))
    {
      if (set_null)
        owner->null_value= 0;
      return sortcmp(res1,res2,cmp_collation.collation);
    }
  }
  if (set_null)
    owner->null_value= 1;
  return -1;
}


/**
  Compare strings byte by byte. End spaces are also compared.

  @retval
    <0  *a < *b
  @retval
     0  *b == *b
  @retval
    >0  *a > *b
*/

int Arg_comparator::compare_binary_string()
{
  String *res1,*res2;
  if ((res1= (*a)->val_str(&value1)))
  {
    if ((res2= (*b)->val_str(&value2)))
    {
      if (set_null)
        owner->null_value= 0;
      uint res1_length= res1->length();
      uint res2_length= res2->length();
      int cmp= memcmp(res1->ptr(), res2->ptr(), min(res1_length,res2_length));
      return cmp ? cmp : (int) (res1_length - res2_length);
    }
  }
  if (set_null)
    owner->null_value= 1;
  return -1;
}


/**
  Compare strings, but take into account that NULL == NULL.
*/


int Arg_comparator::compare_e_string()
{
  String *res1,*res2;
  res1= (*a)->val_str(&value1);
  res2= (*b)->val_str(&value2);
  if (!res1 || !res2)
    return MY_TEST(res1 == res2);
  return MY_TEST(sortcmp(res1, res2, cmp_collation.collation) == 0);
}


int Arg_comparator::compare_e_binary_string()
{
  String *res1,*res2;
  res1= (*a)->val_str(&value1);
  res2= (*b)->val_str(&value2);
  if (!res1 || !res2)
    return MY_TEST(res1 == res2);
  return MY_TEST(stringcmp(res1, res2) == 0);
}


int Arg_comparator::compare_real()
{
  /*
    Fix yet another manifestation of Bug#2338. 'Volatile' will instruct
    gcc to flush double values out of 80-bit Intel FPU registers before
    performing the comparison.
  */
  volatile double val1, val2;
  val1= (*a)->val_real();
  if (!(*a)->null_value)
  {
    val2= (*b)->val_real();
    if (!(*b)->null_value)
    {
      if (set_null)
        owner->null_value= 0;
      if (val1 < val2)	return -1;
      if (val1 == val2) return 0;
      return 1;
    }
  }
  if (set_null)
    owner->null_value= 1;
  return -1;
}

int Arg_comparator::compare_decimal()
{
  my_decimal decimal1;
  my_decimal *val1= (*a)->val_decimal(&decimal1);
  if (!(*a)->null_value)
  {
    my_decimal decimal2;
    my_decimal *val2= (*b)->val_decimal(&decimal2);
    if (!(*b)->null_value)
    {
      if (set_null)
        owner->null_value= 0;
      return my_decimal_cmp(val1, val2);
    }
  }
  if (set_null)
    owner->null_value= 1;
  return -1;
}

int Arg_comparator::compare_e_real()
{
  double val1= (*a)->val_real();
  double val2= (*b)->val_real();
  if ((*a)->null_value || (*b)->null_value)
    return MY_TEST((*a)->null_value && (*b)->null_value);
  return MY_TEST(val1 == val2);
}

int Arg_comparator::compare_e_decimal()
{
  my_decimal decimal1, decimal2;
  my_decimal *val1= (*a)->val_decimal(&decimal1);
  my_decimal *val2= (*b)->val_decimal(&decimal2);
  if ((*a)->null_value || (*b)->null_value)
    return MY_TEST((*a)->null_value && (*b)->null_value);
  return MY_TEST(my_decimal_cmp(val1, val2) == 0);
}


int Arg_comparator::compare_real_fixed()
{
  /*
    Fix yet another manifestation of Bug#2338. 'Volatile' will instruct
    gcc to flush double values out of 80-bit Intel FPU registers before
    performing the comparison.
  */
  volatile double val1, val2;
  val1= (*a)->val_real();
  if (!(*a)->null_value)
  {
    val2= (*b)->val_real();
    if (!(*b)->null_value)
    {
      if (set_null)
        owner->null_value= 0;
      if (val1 == val2 || fabs(val1 - val2) < precision)
        return 0;
      if (val1 < val2)
        return -1;
      return 1;
    }
  }
  if (set_null)
    owner->null_value= 1;
  return -1;
}


int Arg_comparator::compare_e_real_fixed()
{
  double val1= (*a)->val_real();
  double val2= (*b)->val_real();
  if ((*a)->null_value || (*b)->null_value)
    return MY_TEST((*a)->null_value && (*b)->null_value);
  return MY_TEST(val1 == val2 || fabs(val1 - val2) < precision);
}


int Arg_comparator::compare_int_signed()
{
  longlong val1= (*a)->val_int();
  if (!(*a)->null_value)
  {
    longlong val2= (*b)->val_int();
    if (!(*b)->null_value)
    {
      if (set_null)
        owner->null_value= 0;
      if (val1 < val2)	return -1;
      if (val1 == val2)   return 0;
      return 1;
    }
  }
  if (set_null)
    owner->null_value= 1;
  return -1;
}


/**
  Compare values as BIGINT UNSIGNED.
*/

int Arg_comparator::compare_int_unsigned()
{
  ulonglong val1= (*a)->val_int();
  if (!(*a)->null_value)
  {
    ulonglong val2= (*b)->val_int();
    if (!(*b)->null_value)
    {
      if (set_null)
        owner->null_value= 0;
      if (val1 < val2)	return -1;
      if (val1 == val2)   return 0;
      return 1;
    }
  }
  if (set_null)
    owner->null_value= 1;
  return -1;
}


/**
  Compare signed (*a) with unsigned (*B)
*/

int Arg_comparator::compare_int_signed_unsigned()
{
  longlong sval1= (*a)->val_int();
  if (!(*a)->null_value)
  {
    ulonglong uval2= (ulonglong)(*b)->val_int();
    if (!(*b)->null_value)
    {
      if (set_null)
        owner->null_value= 0;
      if (sval1 < 0 || (ulonglong)sval1 < uval2)
        return -1;
      if ((ulonglong)sval1 == uval2)
        return 0;
      return 1;
    }
  }
  if (set_null)
    owner->null_value= 1;
  return -1;
}


/**
  Compare unsigned (*a) with signed (*B)
*/

int Arg_comparator::compare_int_unsigned_signed()
{
  ulonglong uval1= (ulonglong)(*a)->val_int();
  if (!(*a)->null_value)
  {
    longlong sval2= (*b)->val_int();
    if (!(*b)->null_value)
    {
      if (set_null)
        owner->null_value= 0;
      if (sval2 < 0)
        return 1;
      if (uval1 < (ulonglong)sval2)
        return -1;
      if (uval1 == (ulonglong)sval2)
        return 0;
      return 1;
    }
  }
  if (set_null)
    owner->null_value= 1;
  return -1;
}


int Arg_comparator::compare_e_int()
{
  longlong val1= (*a)->val_int();
  longlong val2= (*b)->val_int();
  if ((*a)->null_value || (*b)->null_value)
    return MY_TEST((*a)->null_value && (*b)->null_value);
  return MY_TEST(val1 == val2);
}

/**
  Compare unsigned *a with signed *b or signed *a with unsigned *b.
*/
int Arg_comparator::compare_e_int_diff_signedness()
{
  longlong val1= (*a)->val_int();
  longlong val2= (*b)->val_int();
  if ((*a)->null_value || (*b)->null_value)
    return MY_TEST((*a)->null_value && (*b)->null_value);
  return (val1 >= 0) && MY_TEST(val1 == val2);
}

int Arg_comparator::compare_row()
{
  int res= 0;
  bool was_null= 0;
  (*a)->bring_value();
  (*b)->bring_value();

  if ((*a)->null_value || (*b)->null_value)
  {
    owner->null_value= 1;
    return -1;
  }

  uint n= (*a)->cols();
  for (uint i= 0; i<n; i++)
  {
    res= comparators[i].compare();
    /* Aggregate functions don't need special null handling. */
    if (owner->null_value && owner->type() == Item::FUNC_ITEM)
    {
      // NULL was compared
      switch (((Item_func*)owner)->functype()) {
      case Item_func::NE_FUNC:
        break; // NE never aborts on NULL even if abort_on_null is set
      case Item_func::LT_FUNC:
      case Item_func::LE_FUNC:
      case Item_func::GT_FUNC:
      case Item_func::GE_FUNC:
        return -1; // <, <=, > and >= always fail on NULL
      default: // EQ_FUNC
        if (((Item_bool_func2*)owner)->abort_on_null)
          return -1; // We do not need correct NULL returning
      }
      was_null= 1;
      owner->null_value= 0;
      res= 0;  // continue comparison (maybe we will meet explicit difference)
    }
    else if (res)
      return res;
  }
  if (was_null)
  {
    /*
      There was NULL(s) in comparison in some parts, but there was no
      explicit difference in other parts, so we have to return NULL.
    */
    owner->null_value= 1;
    return -1;
  }
  return 0;
}


int Arg_comparator::compare_e_row()
{
  (*a)->bring_value();
  (*b)->bring_value();
  uint n= (*a)->cols();
  for (uint i= 0; i<n; i++)
  {
    if (!comparators[i].compare())
      return 0;
  }
  return 1;
}


void Item_func_truth::print(String *str, enum_query_type query_type)
{
  str->append('(');
  args[0]->print(str, query_type);
  str->append(STRING_WITH_LEN(" is "));
  if (! affirmative)
    str->append(STRING_WITH_LEN("not "));
  if (value)
    str->append(STRING_WITH_LEN("true"));
  else
    str->append(STRING_WITH_LEN("false"));
  str->append(')');
}



void Item_func_between::print(String *str, enum_query_type query_type)
{
  str->append('(');
  args[0]->print(str, query_type);
  if (negated)
    str->append(STRING_WITH_LEN(" not"));
  str->append(STRING_WITH_LEN(" between "));
  args[1]->print(str, query_type);
  str->append(STRING_WITH_LEN(" and "));
  args[2]->print(str, query_type);
  str->append(')');
}


uint Item_func_if::decimal_precision() const
{
  int arg1_prec= args[1]->decimal_int_part();
  int arg2_prec= args[2]->decimal_int_part();
  int precision=max(arg1_prec,arg2_prec) + decimals;
  return min<uint>(precision, DECIMAL_MAX_PRECISION);
}



bool
Item_func_nullif::is_null()
{
  return (null_value= (!cmp.compare() ? 1 : args[0]->null_value)); 
}


uint Item_func_case::decimal_precision() const
{
  int max_int_part=0;
  for (uint i=0 ; i < ncases ; i+=2)
    set_if_bigger(max_int_part, args[i+1]->decimal_int_part());

  if (else_expr_num != -1) 
    set_if_bigger(max_int_part, args[else_expr_num]->decimal_int_part());
  return min<uint>(max_int_part + decimals, DECIMAL_MAX_PRECISION);
}


/**
  @todo
    Fix this so that it prints the whole CASE expression
*/

void Item_func_case::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("(case "));
  if (first_expr_num != -1)
  {
    args[first_expr_num]->print(str, query_type);
    str->append(' ');
  }
  for (uint i=0 ; i < ncases ; i+=2)
  {
    str->append(STRING_WITH_LEN("when "));
    args[i]->print(str, query_type);
    str->append(STRING_WITH_LEN(" then "));
    args[i+1]->print(str, query_type);
    str->append(' ');
  }
  if (else_expr_num != -1)
  {
    str->append(STRING_WITH_LEN("else "));
    args[else_expr_num]->print(str, query_type);
    str->append(' ');
  }
  str->append(STRING_WITH_LEN("end)"));
}

/****************************************************************************
 Classes and function for the IN operator
****************************************************************************/

/*
  Determine which of the signed longlong arguments is bigger

  SYNOPSIS
    cmp_longs()
      a_val     left argument
      b_val     right argument

  DESCRIPTION
    This function will compare two signed longlong arguments
    and will return -1, 0, or 1 if left argument is smaller than,
    equal to or greater than the right argument.

  RETURN VALUE
    -1          left argument is smaller than the right argument.
    0           left argument is equal to the right argument.
    1           left argument is greater than the right argument.
*/
static inline int cmp_longs (longlong a_val, longlong b_val)
{
  return a_val < b_val ? -1 : a_val == b_val ? 0 : 1;
}


/*
  Determine which of the unsigned longlong arguments is bigger

  SYNOPSIS
    cmp_ulongs()
      a_val     left argument
      b_val     right argument

  DESCRIPTION
    This function will compare two unsigned longlong arguments
    and will return -1, 0, or 1 if left argument is smaller than,
    equal to or greater than the right argument.

  RETURN VALUE
    -1          left argument is smaller than the right argument.
    0           left argument is equal to the right argument.
    1           left argument is greater than the right argument.
*/
static inline int cmp_ulongs (ulonglong a_val, ulonglong b_val)
{
  return a_val < b_val ? -1 : a_val == b_val ? 0 : 1;
}


/*
  Compare two integers in IN value list format (packed_longlong) 

  SYNOPSIS
    cmp_longlong()
      cmp_arg   an argument passed to the calling function (my_qsort2)
      a         left argument
      b         right argument

  DESCRIPTION
    This function will compare two integer arguments in the IN value list
    format and will return -1, 0, or 1 if left argument is smaller than,
    equal to or greater than the right argument.
    It's used in sorting the IN values list and finding an element in it.
    Depending on the signedness of the arguments cmp_longlong() will
    compare them as either signed (using cmp_longs()) or unsigned (using
    cmp_ulongs()).

  RETURN VALUE
    -1          left argument is smaller than the right argument.
    0           left argument is equal to the right argument.
    1           left argument is greater than the right argument.
*/
int cmp_longlong(void *cmp_arg, 
                 in_longlong::packed_longlong *a,
                 in_longlong::packed_longlong *b)
{
  if (a->unsigned_flag != b->unsigned_flag)
  { 
    /* 
      One of the args is unsigned and is too big to fit into the 
      positive signed range. Report no match.
    */  
    if ((a->unsigned_flag && ((ulonglong) a->val) > (ulonglong) LONGLONG_MAX) ||
        (b->unsigned_flag && ((ulonglong) b->val) > (ulonglong) LONGLONG_MAX))
      return a->unsigned_flag ? 1 : -1;
    /*
      Although the signedness differs both args can fit into the signed 
      positive range. Make them signed and compare as usual.
    */  
    return cmp_longs (a->val, b->val);
  }
  if (a->unsigned_flag)
    return cmp_ulongs ((ulonglong) a->val, (ulonglong) b->val);
  else
    return cmp_longs (a->val, b->val);
}



int in_vector::find(Item *item)
{
  uchar *result=get_value(item);
  if (!result || !used_count)
    return 0;				// Null value

  uint start,end;
  start=0; end=used_count-1;
  while (start != end)
  {
    uint mid=(start+end+1)/2;
    int res;
    if ((res=(*compare)(collation, base+mid*size, result)) == 0)
      return 1;
    if (res < 0)
      start=mid;
    else
      end=mid-1;
  }
  return (int) ((*compare)(collation, base+start*size, result) == 0);
}

in_string::in_string(uint elements,qsort2_cmp cmp_func,
                     const CHARSET_INFO *cs)
  :in_vector(elements, sizeof(String), cmp_func, cs),
   tmp(buff, sizeof(buff), &my_charset_bin)
{}

in_string::~in_string()
{
  if (base)
  {
    // base was allocated with help of sql_alloc => following is OK
    for (uint i=0 ; i < count ; i++)
      ((String*) base)[i].free();
  }
}



cmp_item_row::~cmp_item_row()
{
  DBUG_ENTER("~cmp_item_row");
  DBUG_PRINT("enter",("this: 0x%lx", (long) this));
  if (comparators)
  {
    for (uint i= 0; i < n; i++)
    {
      if (comparators[i])
	delete comparators[i];
    }
  }
  DBUG_VOID_RETURN;
}


void cmp_item_row::alloc_comparators()
{
  if (!comparators)
    comparators= (cmp_item **) current_thd->calloc(sizeof(cmp_item *)*n);
}

int cmp_item_row::cmp(Item *arg)
{
  arg->null_value= 0;
  if (arg->cols() != n)
  {
    my_error(ER_OPERAND_COLUMNS, MYF(0), n);
    return 1;
  }
  bool was_null= 0;
  arg->bring_value();
  for (uint i=0; i < n; i++)
  {
    if (comparators[i]->cmp(arg->element_index(i)))
    {
      if (!arg->element_index(i)->null_value)
	return 1;
      was_null= 1;
    }
  }
  return (arg->null_value= was_null);
}


int cmp_item_row::compare(cmp_item *c)
{
  cmp_item_row *l_cmp= (cmp_item_row *) c;
  for (uint i=0; i < n; i++)
  {
    int res;
    if ((res= comparators[i]->compare(l_cmp->comparators[i])))
      return res;
  }
  return 0;
}

int cmp_item_datetime::cmp(Item *arg)
{
  bool is_null;
  Item **tmp_item= &arg;
  return value !=
    get_datetime_value(thd, &tmp_item, 0, warn_item, &is_null);
}


int cmp_item_datetime::compare(cmp_item *ci)
{
  cmp_item_datetime *l_cmp= (cmp_item_datetime *)ci;
  return (value < l_cmp->value) ? -1 : ((value == l_cmp->value) ? 0 : 1);
}

void Item_func_in::print(String *str, enum_query_type query_type)
{
  str->append('(');
  args[0]->print(str, query_type);
  if (negated)
    str->append(STRING_WITH_LEN(" not"));
  str->append(STRING_WITH_LEN(" in ("));
  print_args(str, 1, query_type);
  str->append(STRING_WITH_LEN("))"));
}


Item_cond::Item_cond(THD *thd, Item_cond *item)
  :Item_bool_func(thd, item),
   abort_on_null(item->abort_on_null)
{
  /*
    item->list will be copied by copy_andor_arguments() call
  */
}


bool Item_cond::walk(Item_processor processor, bool walk_subquery, uchar *arg)
{
  List_iterator_fast<Item> li(list);
  Item *item;
  while ((item= li++))
    if (item->walk(processor, walk_subquery, arg))
      return 1;
  return Item_func::walk(processor, walk_subquery, arg);
}


void Item_cond::traverse_cond(Cond_traverser traverser,
                              void *arg, traverse_order order)
{
  List_iterator<Item> li(list);
  Item *item;

  switch(order) {
  case(PREFIX):
    (*traverser)(this, arg);
    while ((item= li++))
    {
      item->traverse_cond(traverser, arg, order);
    }
    (*traverser)(NULL, arg);
    break;
  case(POSTFIX):
    while ((item= li++))
    {
      item->traverse_cond(traverser, arg, order);
    }
    (*traverser)(this, arg);
  }
}

void Item_cond::print(String *str, enum_query_type query_type)
{
  str->append('(');
  List_iterator_fast<Item> li(list);
  Item *item;
  if ((item=li++))
    item->print(str, query_type);
  while ((item=li++))
  {
    str->append(' ');
    str->append(func_name());
    str->append(' ');
    item->print(str, query_type);
  }
  str->append(')');
}


void Item_cond::neg_arguments(THD *thd)
{
  List_iterator<Item> li(list);
  Item *item;
  while ((item= li++))		/* Apply not transformation to the arguments */
  {
    Item *new_item= item->neg_transformer(thd);
    if (!new_item)
    {
      if (!(new_item= new Item_func_not(item)))
	return;					// Fatal OEM error
    }
    (void) li.replace(new_item);
  }
}


/**
  Create an AND expression from two expressions.

  @param a	expression or NULL
  @param b    	expression.
  @param org_item	Don't modify a if a == *org_item.
                        If a == NULL, org_item is set to point at b,
                        to ensure that future calls will not modify b.

  @note
    This will not modify item pointed to by org_item or b
    The idea is that one can call this in a loop and create and
    'and' over all items without modifying any of the original items.

  @retval
    NULL	Error
  @retval
    Item
*/

Item *and_expressions(Item *a, Item *b, Item **org_item)
{
  if (!a)
    return (*org_item= (Item*) b);
  if (a == *org_item)
  {
    Item_cond *res;
    if ((res= new Item_cond_and(a, (Item*) b)))
    {
      res->set_used_tables(a->used_tables() | b->used_tables());
      res->set_not_null_tables(a->not_null_tables() | b->not_null_tables());
    }
    return res;
  }
  if (((Item_cond_and*) a)->add((Item*) b))
    return 0;
  ((Item_cond_and*) a)->set_used_tables(a->used_tables() | b->used_tables());
  ((Item_cond_and*) a)->set_not_null_tables(a->not_null_tables() |
                                            b->not_null_tables());
  return a;
}

void Item_func_isnotnull::print(String *str, enum_query_type query_type)
{
  str->append('(');
  args[0]->print(str, query_type);
  str->append(STRING_WITH_LEN(" is not null)"));
}

#ifdef LIKE_CMP_TOUPPER
#define likeconv(cs,A) (uchar) (cs)->toupper(A)
#else
#define likeconv(cs,A) (uchar) (cs)->sort_order[(uchar) (A)]
#endif


/**
  Precomputation dependent only on pattern_len.
*/

void Item_func_like::turboBM_compute_suffixes(int *suff)
{
  const int   plm1 = pattern_len - 1;
  int            f = 0;
  int            g = plm1;
  int *const splm1 = suff + plm1;
  const CHARSET_INFO	*cs= cmp.cmp_collation.collation;

  *splm1 = pattern_len;

  if (!cs->sort_order)
  {
    int i;
    for (i = pattern_len - 2; i >= 0; i--)
    {
      int tmp = *(splm1 + i - f);
      if (g < i && tmp < i - g)
	suff[i] = tmp;
      else
      {
	if (i < g)
	  g = i; // g = min(i, g)
	f = i;
	while (g >= 0 && pattern[g] == pattern[g + plm1 - f])
	  g--;
	suff[i] = f - g;
      }
    }
  }
  else
  {
    int i;
    for (i = pattern_len - 2; 0 <= i; --i)
    {
      int tmp = *(splm1 + i - f);
      if (g < i && tmp < i - g)
	suff[i] = tmp;
      else
      {
	if (i < g)
	  g = i; // g = min(i, g)
	f = i;
	while (g >= 0 &&
	       likeconv(cs, pattern[g]) == likeconv(cs, pattern[g + plm1 - f]))
	  g--;
	suff[i] = f - g;
      }
    }
  }
}


/**
  Precomputation dependent only on pattern_len.
*/

void Item_func_like::turboBM_compute_good_suffix_shifts(int *suff)
{
  turboBM_compute_suffixes(suff);

  int *end = bmGs + pattern_len;
  int *k;
  for (k = bmGs; k < end; k++)
    *k = pattern_len;

  int tmp;
  int i;
  int j          = 0;
  const int plm1 = pattern_len - 1;
  for (i = plm1; i > -1; i--)
  {
    if (suff[i] == i + 1)
    {
      for (tmp = plm1 - i; j < tmp; j++)
      {
	int *tmp2 = bmGs + j;
	if (*tmp2 == pattern_len)
	  *tmp2 = tmp;
      }
    }
  }

  int *tmp2;
  for (tmp = plm1 - i; j < tmp; j++)
  {
    tmp2 = bmGs + j;
    if (*tmp2 == pattern_len)
      *tmp2 = tmp;
  }

  tmp2 = bmGs + plm1;
  for (i = 0; i <= pattern_len - 2; i++)
    *(tmp2 - suff[i]) = plm1 - i;
}


/**
   Precomputation dependent on pattern_len.
*/

void Item_func_like::turboBM_compute_bad_character_shifts()
{
  int *i;
  int *end = bmBc + alphabet_size;
  int j;
  const int plm1 = pattern_len - 1;
  const CHARSET_INFO	*cs= cmp.cmp_collation.collation;

  for (i = bmBc; i < end; i++)
    *i = pattern_len;

  if (!cs->sort_order)
  {
    for (j = 0; j < plm1; j++)
      bmBc[(uint) (uchar) pattern[j]] = plm1 - j;
  }
  else
  {
    for (j = 0; j < plm1; j++)
      bmBc[(uint) likeconv(cs,pattern[j])] = plm1 - j;
  }
}


/**
  Search for pattern in text.

  @return
    returns true/false for match/no match
*/

bool Item_func_like::turboBM_matches(const char* text, int text_len) const
{
  int bcShift;
  int turboShift;
  int shift = pattern_len;
  int j     = 0;
  int u     = 0;
  const CHARSET_INFO	*cs= cmp.cmp_collation.collation;

  const int plm1=  pattern_len - 1;
  const int tlmpl= text_len - pattern_len;

  /* Searching */
  if (!cs->sort_order)
  {
    while (j <= tlmpl)
    {
      int i= plm1;
      while (i >= 0 && pattern[i] == text[i + j])
      {
	i--;
	if (i == plm1 - shift)
	  i-= u;
      }
      if (i < 0)
	return 1;

      const int v = plm1 - i;
      turboShift = u - v;
      bcShift    = bmBc[(uint) (uchar) text[i + j]] - plm1 + i;
      shift      = max(turboShift, bcShift);
      shift      = max(shift, bmGs[i]);
      if (shift == bmGs[i])
	u = min(pattern_len - shift, v);
      else
      {
	if (turboShift < bcShift)
	  shift = max(shift, u + 1);
	u = 0;
      }
      j+= shift;
    }
    return 0;
  }
  else
  {
    while (j <= tlmpl)
    {
      int i = plm1;
      while (i >= 0 && likeconv(cs,pattern[i]) == likeconv(cs,text[i + j]))
      {
	i--;
	if (i == plm1 - shift)
	  i-= u;
      }
      if (i < 0)
	return 1;

      const int v = plm1 - i;
      turboShift = u - v;
      bcShift    = bmBc[(uint) likeconv(cs, text[i + j])] - plm1 + i;
      shift      = max(turboShift, bcShift);
      shift      = max(shift, bmGs[i]);
      if (shift == bmGs[i])
	u = min(pattern_len - shift, v);
      else
      {
	if (turboShift < bcShift)
	  shift = max(shift, u + 1);
	u = 0;
      }
      j+= shift;
    }
    return 0;
  }
}


/**
  Apply NOT transformation to the item and return a new one.


    Transform the item using next rules:
    @verbatim
       a AND b AND ...    -> NOT(a) OR NOT(b) OR ...
       a OR b OR ...      -> NOT(a) AND NOT(b) AND ...
       NOT(a)             -> a
       a = b              -> a != b
       a != b             -> a = b
       a < b              -> a >= b
       a >= b             -> a < b
       a > b              -> a <= b
       a <= b             -> a > b
       IS NULL(a)         -> IS NOT NULL(a)
       IS NOT NULL(a)     -> IS NULL(a)
    @endverbatim

  @param thd		thread handler

  @return
    New item or
    NULL if we cannot apply NOT transformation (see Item::neg_transformer()).
*/

Item *Item_func_not::neg_transformer(THD *thd)	/* NOT(x)  ->  x */
{
  return args[0];
}


Item *Item_bool_rowready_func2::neg_transformer(THD *thd)
{
  Item *item= negated_item();
  return item;
}

/**
  XOR can be negated by negating one of the operands:

  NOT (a XOR b)  => (NOT a) XOR b
                 => a       XOR (NOT b)

  @param thd     Thread handle
  @return        New negated item
*/
Item *Item_func_xor::neg_transformer(THD *thd)
{
  Item *neg_operand;
  Item_func_xor *new_item;
  if ((neg_operand= args[0]->neg_transformer(thd)))
    // args[0] has neg_tranformer
    new_item= new(thd->mem_root) Item_func_xor(neg_operand, args[1]);
  else if ((neg_operand= args[1]->neg_transformer(thd)))
    // args[1] has neg_tranformer
    new_item= new(thd->mem_root) Item_func_xor(args[0], neg_operand);
  else
  {
    neg_operand= new(thd->mem_root) Item_func_not(args[0]);
    new_item= new(thd->mem_root) Item_func_xor(neg_operand, args[1]);
  }
  return new_item;
}


/**
  a IS NULL  ->  a IS NOT NULL.
*/
Item *Item_func_isnull::neg_transformer(THD *thd)
{
  Item *item= new Item_func_isnotnull(args[0]);
  return item;
}


/**
  a IS NOT NULL  ->  a IS NULL.
*/
Item *Item_func_isnotnull::neg_transformer(THD *thd)
{
  Item *item= new Item_func_isnull(args[0]);
  return item;
}


Item *Item_cond_and::neg_transformer(THD *thd)	/* NOT(a AND b AND ...)  -> */
					/* NOT a OR NOT b OR ... */
{
  neg_arguments(thd);
  Item *item= new Item_cond_or(list);
  return item;
}


Item *Item_cond_or::neg_transformer(THD *thd)	/* NOT(a OR b OR ...)  -> */
					/* NOT a AND NOT b AND ... */
{
  neg_arguments(thd);
  Item *item= new Item_cond_and(list);
  return item;
}


Item *Item_func_eq::negated_item()		/* a = b  ->  a != b */
{
  return new Item_func_ne(args[0], args[1]);
}


Item *Item_func_ne::negated_item()		/* a != b  ->  a = b */
{
  return new Item_func_eq(args[0], args[1]);
}


Item *Item_func_lt::negated_item()		/* a < b  ->  a >= b */
{
  return new Item_func_ge(args[0], args[1]);
}


Item *Item_func_ge::negated_item()		/* a >= b  ->  a < b */
{
  return new Item_func_lt(args[0], args[1]);
}


Item *Item_func_gt::negated_item()		/* a > b  ->  a <= b */
{
  return new Item_func_le(args[0], args[1]);
}


Item *Item_func_le::negated_item()		/* a <= b  ->  a > b */
{
  return new Item_func_gt(args[0], args[1]);
}

/**
  just fake method, should never be called.
*/
Item *Item_bool_rowready_func2::negated_item()
{
  DBUG_ASSERT(0);
  return 0;
}

Item_equal::Item_equal(Item_field *f1, Item_field *f2)
  : Item_bool_func(), const_item(0), eval_item(0), cond_false(0),
    compare_as_dates(FALSE)
{
  const_item_cache= 0;
  fields.push_back(f1);
  fields.push_back(f2);
}


Item_equal::Item_equal(Item_equal *item_equal)
  : Item_bool_func(), eval_item(0), cond_false(0)
{
  const_item_cache= 0;
  List_iterator_fast<Item_field> li(item_equal->fields);
  Item_field *item;
  while ((item= li++))
  {
    fields.push_back(item);
  }
  const_item= item_equal->const_item;
  compare_as_dates= item_equal->compare_as_dates;
  cond_false= item_equal->cond_false;
}



longlong Item_equal::val_int()
{
  return 1;
}

bool Item_equal::walk(Item_processor processor, bool walk_subquery, uchar *arg)
{
  List_iterator_fast<Item_field> it(fields);
  Item *item;
  while ((item= it++))
  {
    if (item->walk(processor, walk_subquery, arg))
      return 1;
  }
  return Item_func::walk(processor, walk_subquery, arg);
}


void Item_equal::print(String *str, enum_query_type query_type)
{
  str->append(func_name());
  str->append('(');
  List_iterator_fast<Item_field> it(fields);
  Item *item;
  if (const_item)
    const_item->print(str, query_type);
  else
  {
    item= it++;
    item->print(str, query_type);
  }
  while ((item= it++))
  {
    str->append(',');
    str->append(' ');
    item->print(str, query_type);
  }
  str->append(')');
}


void Item_func_trig_cond::print(String *str, enum_query_type query_type)
{
  /*
    Print:
    <if>(<property><(optional list of source tables)>, condition, TRUE)
    which means: if a certain property (<property>) is true, then return
    the value of <condition>, else return TRUE. If source tables are
    present, they are the owner of the property.
  */
  str->append(func_name());
  str->append("(");
  switch(trig_type)
  {
  case IS_NOT_NULL_COMPL:
    str->append("is_not_null_compl");
    break;
  case FOUND_MATCH:
    str->append("found_match");
    break;
  case OUTER_FIELD_IS_NOT_NULL:
    str->append("outer_field_is_not_null");
    break;
  default:
    DBUG_ASSERT(0);
  }
  str->append(", ");
  args[0]->print(str, query_type);
  str->append(", true)");
}
