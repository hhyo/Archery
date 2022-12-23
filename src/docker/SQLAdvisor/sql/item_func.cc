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

/**
  @file

  @brief
  This file defines all numerical functions
*/

#include "my_global.h"                          /* NO_EMBEDDED_ACCESS_CHECKS */
#include "sql_priv.h"
/*
  It is necessary to include set_var.h instead of item.h because there
  are dependencies on include order for set_var.h and item.h. This
  will be resolved later.
*/
#include "sql_class.h"                          // set_var.h: THD
#include "set_var.h"
#include "sql_show.h"                           // append_identifier
#include "strfunc.h"                            // find_type
#include "sql_parse.h"                          // is_update_query
#include "sql_acl.h"                            // EXECUTE_ACL
#include "mysqld.h"                             // LOCK_uuid_generator
#include "sql_time.h"
#include <m_ctype.h>
#include <hash.h>
#include <time.h>
#include <ft_global.h>
#include <my_bit.h>

#include "sp_head.h"
#include "sp.h"
#include "set_var.h"
#include <mysql/plugin.h>

using std::min;
using std::max;

bool check_reserved_words(LEX_STRING *name)
{
  if (!my_strcasecmp(system_charset_info, name->str, "GLOBAL") ||
      !my_strcasecmp(system_charset_info, name->str, "LOCAL") ||
      !my_strcasecmp(system_charset_info, name->str, "SESSION"))
    return TRUE;
  return FALSE;
}

/**
   Test if the sum of arguments overflows the ulonglong range.
*/
static inline bool test_if_sum_overflows_ull(ulonglong arg1, ulonglong arg2)
{
  return ULONGLONG_MAX - arg1 < arg2;
}

void Item_func::set_arguments(List<Item> &list)
{
  allowed_arg_cols= 1;
  arg_count=list.elements;
  args= tmp_arg;                                // If 2 arguments
  if (arg_count <= 2 || (args=(Item**) sql_alloc(sizeof(Item*)*arg_count)))
  {
    List_iterator_fast<Item> li(list);
    Item *item;
    Item **save_args= args;

    while ((item=li++))
    {
      *(save_args++)= item;
      with_sum_func|=item->with_sum_func;
    }
  }
  list.empty();					// Fields are used
}

Item_func::Item_func(List<Item> &list)
  :allowed_arg_cols(1)
{
  set_arguments(list);
}

Item_func::Item_func(THD *thd, Item_func *item)
  :const_item_cache(0),
   allowed_arg_cols(item->allowed_arg_cols),
   used_tables_cache(item->used_tables_cache),
   not_null_tables_cache(item->not_null_tables_cache),
   arg_count(item->arg_count)
{
  if (arg_count)
  {
    if (arg_count <=2)
      args= tmp_arg;
    else
    {
      if (!(args=(Item**) thd->alloc(sizeof(Item*)*arg_count)))
	return;
    }
    memcpy((char*) args, (char*) item->args, sizeof(Item*)*arg_count);
  }
}

bool Item_func::walk(Item_processor processor, bool walk_subquery,
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

table_map Item_func::used_tables() const
{
  return used_tables_cache;
}


table_map Item_func::not_null_tables() const
{
  return not_null_tables_cache;
}


void Item_func::print(String *str, enum_query_type query_type)
{
  str->append(func_name());
  str->append('(');
  print_args(str, 0, query_type);
  str->append(')');
}


void Item_func::print_args(String *str, uint from, enum_query_type query_type)
{
  for (uint i=from ; i < arg_count ; i++)
  {
    if (i != from)
      str->append(',');
    args[i]->print(str, query_type);
  }
}


void Item_func::print_op(String *str, enum_query_type query_type)
{
  str->append('(');
  for (uint i=0 ; i < arg_count-1 ; i++)
  {
    args[i]->print(str, query_type);
    str->append(' ');
    str->append(func_name());
    str->append(' ');
  }
  args[arg_count-1]->print(str, query_type);
  str->append(')');
}

my_decimal *Item_func::val_decimal(my_decimal *decimal_value)
{
  DBUG_ASSERT(fixed);
  longlong nr= val_int();
  if (null_value)
    return 0; /* purecov: inspected */
  int2my_decimal(E_DEC_FATAL_ERROR, nr, unsigned_flag, decimal_value);
  return decimal_value;
}


String *Item_real_func::val_str(String *str)
{
  DBUG_ASSERT(fixed == 1);
  double nr= val_real();
  if (null_value)
    return 0; /* purecov: inspected */
  str->set_real(nr, decimals, collation.collation);
  return str;
}


my_decimal *Item_real_func::val_decimal(my_decimal *decimal_value)
{
  DBUG_ASSERT(fixed);
  double nr= val_real();
  if (null_value)
    return 0; /* purecov: inspected */
  double2my_decimal(E_DEC_FATAL_ERROR, nr, decimal_value);
  return decimal_value;
}

void Item_func::signal_divide_by_null()
{
  THD *thd= current_thd;
  if (thd->variables.sql_mode & MODE_ERROR_FOR_DIVISION_BY_ZERO)
    push_warning(thd, Sql_condition::WARN_LEVEL_WARN, ER_DIVISION_BY_ZERO,
                 ER(ER_DIVISION_BY_ZERO));
  null_value= 1;
}


double Item_int_func::val_real()
{
  DBUG_ASSERT(fixed == 1);

  return unsigned_flag ? (double) ((ulonglong) val_int()) : (double) val_int();
}


String *Item_int_func::val_str(String *str)
{
  DBUG_ASSERT(fixed == 1);
  longlong nr=val_int();
  if (null_value)
    return 0;
  str->set_int(nr, unsigned_flag, collation.collation);
  return str;
}


String *Item_func_numhybrid::val_str(String *str)
{
  return NULL;
}


double Item_func_numhybrid::val_real()
{
  return 0.0;
}


longlong Item_func_numhybrid::val_int()
{
  return 0;
}


my_decimal *Item_func_numhybrid::val_decimal(my_decimal *decimal_value)
{
  return 0;
}

void Item_func_signed::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("cast("));
  args[0]->print(str, query_type);
  str->append(STRING_WITH_LEN(" as signed)"));

}

longlong Item_func_signed::val_int()
{
  return 0;
}



void Item_func_unsigned::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("cast("));
  args[0]->print(str, query_type);
  str->append(STRING_WITH_LEN(" as unsigned)"));

}


longlong Item_func_unsigned::val_int()
{
  return 0;
}


String *Item_decimal_typecast::val_str(String *str)
{
  my_decimal tmp_buf, *tmp= val_decimal(&tmp_buf);
  if (null_value)
    return NULL;
  my_decimal2string(E_DEC_FATAL_ERROR, tmp, 0, 0, 0, str);
  return str;
}


double Item_decimal_typecast::val_real()
{
  my_decimal tmp_buf, *tmp= val_decimal(&tmp_buf);
  double res;
  if (null_value)
    return 0.0;
  my_decimal2double(E_DEC_FATAL_ERROR, tmp, &res);
  return res;
}


longlong Item_decimal_typecast::val_int()
{
  my_decimal tmp_buf, *tmp= val_decimal(&tmp_buf);
  longlong res;
  if (null_value)
    return 0;
  my_decimal2int(E_DEC_FATAL_ERROR, tmp, unsigned_flag, &res);
  return res;
}


my_decimal *Item_decimal_typecast::val_decimal(my_decimal *dec)
{
  my_decimal tmp_buf, *tmp= args[0]->val_decimal(&tmp_buf);
  bool sign;
  uint precision;

  if ((null_value= args[0]->null_value))
    return NULL;
  my_decimal_round(E_DEC_FATAL_ERROR, tmp, decimals, FALSE, dec);
  sign= dec->sign();
  if (unsigned_flag)
  {
    if (sign)
    {
      my_decimal_set_zero(dec);
      goto err;
    }
  }
  precision= my_decimal_length_to_precision(max_length,
                                            decimals, unsigned_flag);
  if (precision - decimals < (uint) my_decimal_intg(dec))
  {
    max_my_decimal(dec, precision, decimals);
    dec->sign(sign);
    goto err;
  }
  return dec;

err:
  push_warning_printf(current_thd, Sql_condition::WARN_LEVEL_WARN,
                      ER_WARN_DATA_OUT_OF_RANGE,
                      ER(ER_WARN_DATA_OUT_OF_RANGE),
                      item_name.ptr(), 1L);
  return dec;
}


void Item_decimal_typecast::print(String *str, enum_query_type query_type)
{
  char len_buf[20*3 + 1];
  char *end;

  uint precision= my_decimal_length_to_precision(max_length, decimals,
                                                 unsigned_flag);
  str->append(STRING_WITH_LEN("cast("));
  args[0]->print(str, query_type);
  str->append(STRING_WITH_LEN(" as decimal("));

  end=int10_to_str(precision, len_buf,10);
  str->append(len_buf, (uint32) (end - len_buf));

  str->append(',');

  end=int10_to_str(decimals, len_buf,10);
  str->append(len_buf, (uint32) (end - len_buf));

  str->append(')');
  str->append(')');
}


/* Integer division */
longlong Item_func_int_div::val_int()
{
  DBUG_ASSERT(fixed == 1);

  /*
    Perform division using DECIMAL math if either of the operands has a
    non-integer type
  */
  if (args[0]->result_type() != INT_RESULT ||
      args[1]->result_type() != INT_RESULT)
  {
    my_decimal tmp;
    my_decimal *val0p= args[0]->val_decimal(&tmp);
    if ((null_value= args[0]->null_value))
      return 0;
    my_decimal val0= *val0p;

    my_decimal *val1p= args[1]->val_decimal(&tmp);
    if ((null_value= args[1]->null_value))
      return 0;
    my_decimal val1= *val1p;

    int err;
    if ((err= my_decimal_div(E_DEC_FATAL_ERROR & ~E_DEC_DIV_ZERO, &tmp,
                             &val0, &val1, 0)) > 3)
    {
      if (err == E_DEC_DIV_ZERO)
        signal_divide_by_null();
      return 0;
    }

    my_decimal truncated;
    const bool do_truncate= true;
    if (my_decimal_round(E_DEC_FATAL_ERROR, &tmp, 0, do_truncate, &truncated))
      DBUG_ASSERT(false);

    longlong res;
    if (my_decimal2int(E_DEC_FATAL_ERROR, &truncated, unsigned_flag, &res) &
        E_DEC_OVERFLOW)
      raise_integer_overflow();
    return res;
  }
  
  longlong val0=args[0]->val_int();
  longlong val1=args[1]->val_int();
  bool val0_negative, val1_negative, res_negative;
  ulonglong uval0, uval1, res;
  if ((null_value= (args[0]->null_value || args[1]->null_value)))
    return 0;
  if (val1 == 0)
  {
    signal_divide_by_null();
    return 0;
  }

  val0_negative= !args[0]->unsigned_flag && val0 < 0;
  val1_negative= !args[1]->unsigned_flag && val1 < 0;
  res_negative= val0_negative != val1_negative;
  uval0= (ulonglong) (val0_negative ? -val0 : val0);
  uval1= (ulonglong) (val1_negative ? -val1 : val1);
  res= uval0 / uval1;
  if (res_negative)
  {
    if (res > (ulonglong) LONGLONG_MAX)
      return raise_integer_overflow();
    res= (ulonglong) (-(longlong) res);
  }
  return check_integer_overflow(res, !res_negative);
}


/** Gateway to natural LOG function. */
double Item_func_ln::val_real()
{
  DBUG_ASSERT(fixed == 1);
  double value= args[0]->val_real();
  if ((null_value= args[0]->null_value))
    return 0.0;
  if (value <= 0.0)
  {
    signal_divide_by_null();
    return 0.0;
  }
  return log(value);
}

/** 
  Extended but so slower LOG function.

  We have to check if all values are > zero and first one is not one
  as these are the cases then result is not a number.
*/ 
double Item_func_log::val_real()
{
  DBUG_ASSERT(fixed == 1);
  double value= args[0]->val_real();
  if ((null_value= args[0]->null_value))
    return 0.0;
  if (value <= 0.0)
  {
    signal_divide_by_null();
    return 0.0;
  }
  if (arg_count == 2)
  {
    double value2= args[1]->val_real();
    if ((null_value= args[1]->null_value))
      return 0.0;
    if (value2 <= 0.0 || value == 1.0)
    {
      signal_divide_by_null();
      return 0.0;
    }
    return log(value2) / log(value);
  }
  return log(value);
}

double Item_func_log2::val_real()
{
  DBUG_ASSERT(fixed == 1);
  double value= args[0]->val_real();

  if ((null_value=args[0]->null_value))
    return 0.0;
  if (value <= 0.0)
  {
    signal_divide_by_null();
    return 0.0;
  }
  return log(value) / M_LN2;
}

double Item_func_log10::val_real()
{
  DBUG_ASSERT(fixed == 1);
  double value= args[0]->val_real();
  if ((null_value= args[0]->null_value))
    return 0.0;
  if (value <= 0.0)
  {
    signal_divide_by_null();
    return 0.0;
  }
  return log10(value);
}

double Item_func_exp::val_real()
{
  DBUG_ASSERT(fixed == 1);
  double value= args[0]->val_real();
  if ((null_value=args[0]->null_value))
    return 0.0; /* purecov: inspected */
  return check_float_overflow(exp(value));
}

double Item_func_sqrt::val_real()
{
  DBUG_ASSERT(fixed == 1);
  double value= args[0]->val_real();
  if ((null_value=(args[0]->null_value || value < 0)))
    return 0.0; /* purecov: inspected */
  return sqrt(value);
}

double Item_func_pow::val_real()
{
  DBUG_ASSERT(fixed == 1);
  double value= args[0]->val_real();
  double val2= args[1]->val_real();
  if ((null_value=(args[0]->null_value || args[1]->null_value)))
    return 0.0; /* purecov: inspected */
  return check_float_overflow(pow(value,val2));
}

// Trigonometric functions

double Item_func_acos::val_real()
{
  DBUG_ASSERT(fixed == 1);
  // the volatile's for BUG #2338 to calm optimizer down (because of gcc's bug)
  volatile double value= args[0]->val_real();
  if ((null_value=(args[0]->null_value || (value < -1.0 || value > 1.0))))
    return 0.0;
  return acos(value);
}

double Item_func_asin::val_real()
{
  DBUG_ASSERT(fixed == 1);
  // the volatile's for BUG #2338 to calm optimizer down (because of gcc's bug)
  volatile double value= args[0]->val_real();
  if ((null_value=(args[0]->null_value || (value < -1.0 || value > 1.0))))
    return 0.0;
  return asin(value);
}

double Item_func_atan::val_real()
{
  DBUG_ASSERT(fixed == 1);
  double value= args[0]->val_real();
  if ((null_value=args[0]->null_value))
    return 0.0;
  if (arg_count == 2)
  {
    double val2= args[1]->val_real();
    if ((null_value=args[1]->null_value))
      return 0.0;
    return check_float_overflow(atan2(value,val2));
  }
  return atan(value);
}

double Item_func_cos::val_real()
{
  DBUG_ASSERT(fixed == 1);
  double value= args[0]->val_real();
  if ((null_value=args[0]->null_value))
    return 0.0;
  return cos(value);
}

double Item_func_sin::val_real()
{
  DBUG_ASSERT(fixed == 1);
  double value= args[0]->val_real();
  if ((null_value=args[0]->null_value))
    return 0.0;
  return sin(value);
}

double Item_func_tan::val_real()
{
  DBUG_ASSERT(fixed == 1);
  double value= args[0]->val_real();
  if ((null_value=args[0]->null_value))
    return 0.0;
  return check_float_overflow(tan(value));
}


double Item_func_cot::val_real()
{
  DBUG_ASSERT(fixed == 1);
  double value= args[0]->val_real();
  if ((null_value=args[0]->null_value))
    return 0.0;
  return check_float_overflow(1.0 / tan(value));
}


// Shift-functions, same as << and >> in C/C++


longlong Item_func_shift_left::val_int()
{
  DBUG_ASSERT(fixed == 1);
  uint shift;
  ulonglong res= ((ulonglong) args[0]->val_int() <<
		  (shift=(uint) args[1]->val_int()));
  if (args[0]->null_value || args[1]->null_value)
  {
    null_value=1;
    return 0;
  }
  null_value=0;
  return (shift < sizeof(longlong)*8 ? (longlong) res : LL(0));
}

longlong Item_func_shift_right::val_int()
{
  DBUG_ASSERT(fixed == 1);
  uint shift;
  ulonglong res= (ulonglong) args[0]->val_int() >>
    (shift=(uint) args[1]->val_int());
  if (args[0]->null_value || args[1]->null_value)
  {
    null_value=1;
    return 0;
  }
  null_value=0;
  return (shift < sizeof(longlong)*8 ? (longlong) res : LL(0));
}


longlong Item_func_bit_neg::val_int()
{
  DBUG_ASSERT(fixed == 1);
  ulonglong res= (ulonglong) args[0]->val_int();
  if ((null_value=args[0]->null_value))
    return 0;
  return ~res;
}

double my_double_round(double value, longlong dec, bool dec_unsigned,
                       bool truncate)
{
  double tmp;
  bool dec_negative= (dec < 0) && !dec_unsigned;
  ulonglong abs_dec= dec_negative ? -dec : dec;
  /*
    tmp2 is here to avoid return the value with 80 bit precision
    This will fix that the test round(0.1,1) = round(0.1,1) is true
    Tagging with volatile is no guarantee, it may still be optimized away...
  */
  volatile double tmp2;

  tmp=(abs_dec < array_elements(log_10) ?
       log_10[abs_dec] : pow(10.0,(double) abs_dec));

  // Pre-compute these, to avoid optimizing away e.g. 'floor(v/tmp) * tmp'.
  volatile double value_div_tmp= value / tmp;
  volatile double value_mul_tmp= value * tmp;

  if (dec_negative && my_isinf(tmp))
    tmp2= 0.0;
  else if (!dec_negative && my_isinf(value_mul_tmp))
    tmp2= value;
  else if (truncate)
  {
    if (value >= 0.0)
      tmp2= dec < 0 ? floor(value_div_tmp) * tmp : floor(value_mul_tmp) / tmp;
    else
      tmp2= dec < 0 ? ceil(value_div_tmp) * tmp : ceil(value_mul_tmp) / tmp;
  }
  else
    tmp2=dec < 0 ? rint(value_div_tmp) * tmp : rint(value_mul_tmp) / tmp;

  return tmp2;
}

void Item_func_locate::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("locate("));
  args[1]->print(str, query_type);
  str->append(',');
  args[0]->print(str, query_type);
  if (arg_count == 3)
  {
    str->append(',');
    args[2]->print(str, query_type);
  }
  str->append(')');
}

/****************************************************************************
** Functions to handle dynamic loadable functions
** Original source by: Alexis Mikhailov <root@medinf.chuvashia.su>
** Rewritten by monty.
****************************************************************************/

#ifdef HAVE_DLOPEN

bool udf_handler::get_arguments()
{
  if (error)
    return 1;					// Got an error earlier
  char *to= num_buffer;
  uint str_count=0;
  for (uint i=0; i < f_args.arg_count; i++)
  {
    f_args.args[i]=0;
    switch (f_args.arg_type[i]) {
    case STRING_RESULT:
    case DECIMAL_RESULT:
      {
	String *res=args[i]->val_str(&buffers[str_count++]);
	if (!(args[i]->null_value))
	{
	  f_args.args[i]=    (char*) res->ptr();
	  f_args.lengths[i]= res->length();
	}
	else
	{
	  f_args.lengths[i]= 0;
	}
	break;
      }
    case INT_RESULT:
      *((longlong*) to) = args[i]->val_int();
      if (!args[i]->null_value)
      {
	f_args.args[i]=to;
	to+= ALIGN_SIZE(sizeof(longlong));
      }
      break;
    case REAL_RESULT:
      *((double*) to)= args[i]->val_real();
      if (!args[i]->null_value)
      {
	f_args.args[i]=to;
	to+= ALIGN_SIZE(sizeof(double));
      }
      break;
    case ROW_RESULT:
    default:
      // This case should never be chosen
      DBUG_ASSERT(0);
      break;
    }
  }
  return 0;
}

/**
  @return
    (String*)NULL in case of NULL values
*/
String *udf_handler::val_str(String *str,String *save_str)
{
  uchar is_null_tmp=0;
  ulong res_length;
  DBUG_ENTER("udf_handler::val_str");

  if (get_arguments())
    DBUG_RETURN(0);
  char * (*func)(UDF_INIT *, UDF_ARGS *, char *, ulong *, uchar *, uchar *)=
    (char* (*)(UDF_INIT *, UDF_ARGS *, char *, ulong *, uchar *, uchar *))
    u_d->func;

  if ((res_length=str->alloced_length()) < MAX_FIELD_WIDTH)
  {						// This happens VERY seldom
    if (str->alloc(MAX_FIELD_WIDTH))
    {
      error=1;
      DBUG_RETURN(0);
    }
  }
  char *res=func(&initid, &f_args, (char*) str->ptr(), &res_length,
		 &is_null_tmp, &error);
  DBUG_PRINT("info", ("udf func returned, res_length: %lu", res_length));
  if (is_null_tmp || !res || error)		// The !res is for safety
  {
    DBUG_PRINT("info", ("Null or error"));
    DBUG_RETURN(0);
  }
  if (res == str->ptr())
  {
    str->length(res_length);
    DBUG_PRINT("exit", ("str: %*.s", (int) str->length(), str->ptr()));
    DBUG_RETURN(str);
  }
  save_str->set(res, res_length, str->charset());
  DBUG_PRINT("exit", ("save_str: %s", save_str->ptr()));
  DBUG_RETURN(save_str);
}


/*
  For the moment, UDF functions are returning DECIMAL values as strings
*/

my_decimal *udf_handler::val_decimal(my_bool *null_value, my_decimal *dec_buf)
{
  char buf[DECIMAL_MAX_STR_LENGTH+1], *end;
  ulong res_length= DECIMAL_MAX_STR_LENGTH;

  if (get_arguments())
  {
    *null_value=1;
    return 0;
  }
  char *(*func)(UDF_INIT *, UDF_ARGS *, char *, ulong *, uchar *, uchar *)=
    (char* (*)(UDF_INIT *, UDF_ARGS *, char *, ulong *, uchar *, uchar *))
    u_d->func;

  char *res= func(&initid, &f_args, buf, &res_length, &is_null, &error);
  if (is_null || error)
  {
    *null_value= 1;
    return 0;
  }
  end= res+ res_length;
  str2my_decimal(E_DEC_FATAL_ERROR, res, dec_buf, &end);
  return dec_buf;
}


void Item_udf_func::print(String *str, enum_query_type query_type)
{
  str->append(func_name());
  str->append('(');
  for (uint i=0 ; i < arg_count ; i++)
  {
    if (i != 0)
      str->append(',');
    args[i]->print_item_w_name(str, query_type);
  }
  str->append(')');
}




double Item_func_udf_float::val_real()
{
  DBUG_ASSERT(fixed == 1);
  DBUG_ENTER("Item_func_udf_float::val");
  DBUG_PRINT("info",("result_type: %d  arg_count: %d",
		     args[0]->result_type(), arg_count));
  DBUG_RETURN(udf.val(&null_value));
}


String *Item_func_udf_float::val_str(String *str)
{
  DBUG_ASSERT(fixed == 1);
  double nr= val_real();
  if (null_value)
    return 0;					/* purecov: inspected */
  str->set_real(nr,decimals,&my_charset_bin);
  return str;
}


longlong Item_func_udf_int::val_int()
{
  DBUG_ASSERT(fixed == 1);
  DBUG_ENTER("Item_func_udf_int::val_int");
  DBUG_RETURN(udf.val_int(&null_value));
}


String *Item_func_udf_int::val_str(String *str)
{
  DBUG_ASSERT(fixed == 1);
  longlong nr=val_int();
  if (null_value)
    return 0;
  str->set_int(nr, unsigned_flag, &my_charset_bin);
  return str;
}


longlong Item_func_udf_decimal::val_int()
{
  my_decimal dec_buf, *dec= udf.val_decimal(&null_value, &dec_buf);
  longlong result;
  if (null_value)
    return 0;
  my_decimal2int(E_DEC_FATAL_ERROR, dec, unsigned_flag, &result);
  return result;
}


double Item_func_udf_decimal::val_real()
{
  my_decimal dec_buf, *dec= udf.val_decimal(&null_value, &dec_buf);
  double result;
  if (null_value)
    return 0.0;
  my_decimal2double(E_DEC_FATAL_ERROR, dec, &result);
  return result;
}


my_decimal *Item_func_udf_decimal::val_decimal(my_decimal *dec_buf)
{
  DBUG_ASSERT(fixed == 1);
  DBUG_ENTER("Item_func_udf_decimal::val_decimal");
  DBUG_PRINT("info",("result_type: %d  arg_count: %d",
                     args[0]->result_type(), arg_count));

  DBUG_RETURN(udf.val_decimal(&null_value, dec_buf));
}


String *Item_func_udf_decimal::val_str(String *str)
{
  my_decimal dec_buf, *dec= udf.val_decimal(&null_value, &dec_buf);
  if (null_value)
    return 0;
  if (str->length() < DECIMAL_MAX_STR_LENGTH)
    str->length(DECIMAL_MAX_STR_LENGTH);
  my_decimal_round(E_DEC_FATAL_ERROR, dec, decimals, FALSE, &dec_buf);
  my_decimal2string(E_DEC_FATAL_ERROR, &dec_buf, 0, 0, '0', str);
  return str;
}

/**
  @note
  This has to come last in the udf_handler methods, or C for AIX
  version 6.0.0.0 fails to compile with debugging enabled. (Yes, really.)
*/

udf_handler::~udf_handler()
{
  /* Everything should be properly cleaned up by this moment. */
  DBUG_ASSERT(not_original || !(initialized || buffers));
}

#else
bool udf_handler::get_arguments() { return 0; }
#endif /* HAVE_DLOPEN */


longlong Item_master_pos_wait::val_int()
{
  DBUG_ASSERT(fixed == 1);
  THD* thd = current_thd;
  String *log_name = args[0]->val_str(&value);
  int event_count= 0;

  null_value=0;
  if (thd->slave_thread || !log_name || !log_name->length())
  {
    null_value = 1;
    return 0;
  }
  return event_count;
}

longlong Item_master_gtid_set_wait::val_int()
{
  DBUG_ASSERT(fixed == 1);
  THD* thd = current_thd;
  String *gtid= args[0]->val_str(&value);
  int event_count= 0;

  null_value=0;
  return event_count;
}

/**
  Return 1 if both arguments are Gtid_sets and the first is a subset
  of the second.  Generate an error if any of the arguments is not a
  Gtid_set.
*/
longlong Item_func_gtid_subset::val_int()
{
  return 0;
}


/**
  Enables a session to wait on a condition until a timeout or a network
  disconnect occurs.

  @remark The connection is polled every m_interrupt_interval nanoseconds.
*/

class Interruptible_wait
{
  THD *m_thd;
  struct timespec m_abs_timeout;
  static const ulonglong m_interrupt_interval;

  public:
    Interruptible_wait(THD *thd)
    : m_thd(thd) {}

    ~Interruptible_wait() {}

  public:
    /**
      Set the absolute timeout.

      @param timeout The amount of time in nanoseconds to wait
    */
    void set_timeout(ulonglong timeout)
    {
      /*
        Calculate the absolute system time at the start so it can
        be controlled in slices. It relies on the fact that once
        the absolute time passes, the timed wait call will fail
        automatically with a timeout error.
      */
      set_timespec_nsec(m_abs_timeout, timeout);
    }

    /** The timed wait. */
    int wait(mysql_cond_t *, mysql_mutex_t *);
};


/** Time to wait before polling the connection status. */
const ulonglong Interruptible_wait::m_interrupt_interval= 5 * ULL(1000000000);


/**
  Wait for a given condition to be signaled.

  @param cond   The condition variable to wait on.
  @param mutex  The associated mutex.

  @remark The absolute timeout is preserved across calls.

  @retval return value from mysql_cond_timedwait
*/

int Interruptible_wait::wait(mysql_cond_t *cond, mysql_mutex_t *mutex)
{
  int error;
  struct timespec timeout;

  while (1)
  {
    /* Wait for a fixed interval. */
    set_timespec_nsec(timeout, m_interrupt_interval);

    /* But only if not past the absolute timeout. */
    if (cmp_timespec(timeout, m_abs_timeout) > 0)
      timeout= m_abs_timeout;

    error= mysql_cond_timedwait(cond, mutex, &timeout);
    if (error == ETIMEDOUT || error == ETIME)
    {
      /* Return error if timed out or connection is broken. */
      if (!cmp_timespec(timeout, m_abs_timeout) || !m_thd->is_connected())
        break;
    }
    /* Otherwise, propagate status to the caller. */
    else
      break;
  }

  return error;
}

/**
  When MDL detects a lock wait timeout, it pushes
  an error into the statement diagnostics area.
  For GET_LOCK(), lock wait timeout is not an error,
  but a special return value (0). NULL is returned in
  case of error.
  Capture and suppress lock wait timeout.
*/

class Lock_wait_timeout_handler: public Internal_error_handler
{
public:
  Lock_wait_timeout_handler() :m_lock_wait_timeout(false) {}

  bool m_lock_wait_timeout;

  bool handle_condition(THD * /* thd */, uint sql_errno,
                        const char * /* sqlstate */,
                        Sql_condition::enum_warning_level /* level */,
                        const char *message,
                        Sql_condition ** /* cond_hdl */);
};

bool
Lock_wait_timeout_handler::
handle_condition(THD * /* thd */, uint sql_errno,
                 const char * /* sqlstate */,
                 Sql_condition::enum_warning_level /* level */,
                 const char *message,
                 Sql_condition ** /* cond_hdl */)
{
  if (sql_errno == ER_LOCK_WAIT_TIMEOUT)
  {
    m_lock_wait_timeout= true;
    return true;                                /* condition handled */
  }
  if (sql_errno == ER_QUERY_INTERRUPTED)
  {
    /*
     * Do not push of ER_QUERY_INTERRUPTED into the diagnostics
     * stack. GET_LOCK() is expected to return NULL in this case.
     */
    return true;
  }
  return false;
}


/**
  Get a user level lock.

  @retval
    1    : Got lock
  @retval
    0    : Timeout
  @retval
    NULL : Error
*/

longlong Item_func_get_lock::val_int()
{
  return 0;
}


/**
  Release a user level lock.
  @return
    - 1 if lock released
    - 0 if lock wasn't held
    - (SQL) NULL if no such lock
*/

longlong Item_func_release_lock::val_int()
{
    return 0;
}


/**
  Check a user level lock.

  Sets null_value=TRUE on error.

  @retval
    1		Available
  @retval
    0		Already taken, or error
*/

longlong Item_func_is_free_lock::val_int()
{
  return 0;
}


longlong Item_func_is_used_lock::val_int()
{
  null_value= 0;
  return 0;
}


longlong Item_func_last_insert_id::val_int()
{
  THD *thd= current_thd;
  DBUG_ASSERT(fixed == 1);
  if (arg_count)
  {
    longlong value= args[0]->val_int();
    null_value= args[0]->null_value;
    /*
      LAST_INSERT_ID(X) must affect the client's mysql_insert_id() as
      documented in the manual. We don't want to touch
      first_successful_insert_id_in_cur_stmt because it would make
      LAST_INSERT_ID(X) take precedence over an generated auto_increment
      value for this row.
    */
    thd->arg_of_last_insert_id_function= TRUE;
    thd->first_successful_insert_id_in_prev_stmt= value;
    return value;
  }
  return
    static_cast<longlong>(thd->read_first_successful_insert_id_in_prev_stmt());
}


/* This function is just used to test speed of different functions */

longlong Item_func_benchmark::val_int()
{
  DBUG_ASSERT(fixed == 1);
  char buff[MAX_FIELD_WIDTH];
  String tmp(buff,sizeof(buff), &my_charset_bin);
  my_decimal tmp_decimal;
  THD *thd=current_thd;
  ulonglong loop_count;

  loop_count= (ulonglong) args[0]->val_int();

  if (args[0]->null_value ||
      (!args[0]->unsigned_flag && (((longlong) loop_count) < 0)))
  {
    if (!args[0]->null_value)
    {
      char buff[22];
      llstr(((longlong) loop_count), buff);
      push_warning_printf(current_thd, Sql_condition::WARN_LEVEL_WARN,
                          ER_WRONG_VALUE_FOR_TYPE, ER(ER_WRONG_VALUE_FOR_TYPE),
                          "count", buff, "benchmark");
    }

    null_value= 1;
    return 0;
  }

  null_value=0;
  for (ulonglong loop=0 ; loop < loop_count && !thd->killed; loop++)
  {
    switch (args[1]->result_type()) {
    case REAL_RESULT:
      (void) args[1]->val_real();
      break;
    case INT_RESULT:
      (void) args[1]->val_int();
      break;
    case STRING_RESULT:
      (void) args[1]->val_str(&tmp);
      break;
    case DECIMAL_RESULT:
      (void) args[1]->val_decimal(&tmp_decimal);
      break;
    case ROW_RESULT:
    default:
      // This case should never be chosen
      DBUG_ASSERT(0);
      return 0;
    }
  }
  return 0;
}


void Item_func_benchmark::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("benchmark("));
  args[0]->print(str, query_type);
  str->append(',');
  args[1]->print(str, query_type);
  str->append(')');
}


mysql_mutex_t LOCK_item_func_sleep;

#ifdef HAVE_PSI_INTERFACE
static PSI_mutex_key key_LOCK_item_func_sleep;

static PSI_mutex_info item_func_sleep_mutexes[]=
{
  { &key_LOCK_item_func_sleep, "LOCK_user_locks", PSI_FLAG_GLOBAL}
};


static void init_item_func_sleep_psi_keys(void)
{
  const char* category= "sql";
  int count;

  if (PSI_server == NULL)
    return;

  count= array_elements(item_func_sleep_mutexes);
  PSI_server->register_mutex(category, item_func_sleep_mutexes, count);
}
#endif

static bool item_func_sleep_inited= 0;


void item_func_sleep_init(void)
{
#ifdef HAVE_PSI_INTERFACE
  init_item_func_sleep_psi_keys();
#endif

  mysql_mutex_init(key_LOCK_item_func_sleep, &LOCK_item_func_sleep, MY_MUTEX_INIT_SLOW);
  item_func_sleep_inited= 1;
}


void item_func_sleep_free(void)
{
  if (item_func_sleep_inited)
  {
    item_func_sleep_inited= 0;
    mysql_mutex_destroy(&LOCK_item_func_sleep);
  }
}


/** This function is just used to create tests with time gaps. */

longlong Item_func_sleep::val_int()
{
  return 1; 		// Return 1 killed
}


static user_var_entry *get_variable(HASH *hash, const Name_string &name,
				    bool create_if_not_exists)
{
  user_var_entry *entry;

  if (!(entry = (user_var_entry*) my_hash_search(hash, (uchar*) name.ptr(),
                                                 name.length())) &&
      create_if_not_exists)
  {
    if (!my_hash_inited(hash))
      return 0;
    if (!(entry= user_var_entry::create(name)))
      return 0;
    if (my_hash_insert(hash,(uchar*) entry))
    {
      my_free(entry);
      return 0;
    }
  }
  return entry;
}

bool user_var_entry::realloc(uint length)
{
  if (length <= extra_size)
  {
    /* Enough space to store value in value struct */
    free_value();
    m_ptr= internal_buffer_ptr();
  }
  else
  {
    /* Allocate an external buffer */
    if (m_length != length)
    {
      if (m_ptr == internal_buffer_ptr())
        m_ptr= 0;
      if (!(m_ptr= (char*) my_realloc(m_ptr, length,
                                      MYF(MY_ALLOW_ZERO_PTR | MY_WME |
                                      ME_FATALERROR))))
        return true;
    }
  }
  return false;
}


/**
  Set value to user variable.
  @param ptr            pointer to buffer with new value
  @param length         length of new value
  @param type           type of new value

  @retval  false   on success
  @retval  true    on allocation error

*/
bool user_var_entry::store(void *from, uint length, Item_result type)
{
  // Store strings with end \0
  if (realloc(length + MY_TEST(type == STRING_RESULT)))
    return true;
  if (type == STRING_RESULT)
    m_ptr[length]= 0;     // Store end \0
  memmove(m_ptr, from, length);
  if (type == DECIMAL_RESULT)
    ((my_decimal*) m_ptr)->fix_buffer_pointer();
  m_length= length;
  m_type= type;
  return false;
}


/**
  Set value to user variable.

  @param ptr            pointer to buffer with new value
  @param length         length of new value
  @param type           type of new value
  @param cs             charset info for new value
  @param dv             derivation for new value
  @param unsigned_arg   indiates if a value of type INT_RESULT is unsigned

  @note Sets error and fatal error if allocation fails.

  @retval
    false   success
  @retval
    true    failure
*/

bool user_var_entry::store(void *ptr, uint length, Item_result type,
                           const CHARSET_INFO *cs, Derivation dv,
                           bool unsigned_arg)
{
  if (store(ptr, length, type))
    return true;
  collation.set(cs, dv);
  unsigned_flag= unsigned_arg;
  return false;
}

/** Get the value of a variable as a double. */

double user_var_entry::val_real(my_bool *null_value)
{
  if ((*null_value= (m_ptr == 0)))
    return 0.0;

  switch (m_type) {
  case REAL_RESULT:
    return *(double*) m_ptr;
  case INT_RESULT:
    return (double) *(longlong*) m_ptr;
  case DECIMAL_RESULT:
  {
    double result;
    my_decimal2double(E_DEC_FATAL_ERROR, (my_decimal *) m_ptr, &result);
    return result;
  }
  case STRING_RESULT:
    return my_atof(m_ptr);                    // This is null terminated
  case ROW_RESULT:
    DBUG_ASSERT(1);				// Impossible
    break;
  }
  return 0.0;					// Impossible
}


/** Get the value of a variable as an integer. */

longlong user_var_entry::val_int(my_bool *null_value) const
{
  if ((*null_value= (m_ptr == 0)))
    return LL(0);

  switch (m_type) {
  case REAL_RESULT:
    return (longlong) *(double*) m_ptr;
  case INT_RESULT:
    return *(longlong*) m_ptr;
  case DECIMAL_RESULT:
  {
    longlong result;
    my_decimal2int(E_DEC_FATAL_ERROR, (my_decimal *) m_ptr, 0, &result);
    return result;
  }
  case STRING_RESULT:
  {
    int error;
    return my_strtoll10(m_ptr, (char**) 0, &error);// String is null terminated
  }
  case ROW_RESULT:
    DBUG_ASSERT(1);				// Impossible
    break;
  }
  return LL(0);					// Impossible
}


/** Get the value of a variable as a string. */

String *user_var_entry::val_str(my_bool *null_value, String *str,
				uint decimals)
{
  if ((*null_value= (m_ptr == 0)))
    return (String*) 0;

  switch (m_type) {
  case REAL_RESULT:
    str->set_real(*(double*) m_ptr, decimals, collation.collation);
    break;
  case INT_RESULT:
    if (!unsigned_flag)
      str->set(*(longlong*) m_ptr, collation.collation);
    else
      str->set(*(ulonglong*) m_ptr, collation.collation);
    break;
  case DECIMAL_RESULT:
    str_set_decimal((my_decimal *) m_ptr, str, collation.collation);
    break;
  case STRING_RESULT:
    if (str->copy(m_ptr, m_length, collation.collation))
      str= 0;					// EOM error
  case ROW_RESULT:
    DBUG_ASSERT(1);				// Impossible
    break;
  }
  return(str);
}

/** Get the value of a variable as a decimal. */

my_decimal *user_var_entry::val_decimal(my_bool *null_value, my_decimal *val)
{
  if ((*null_value= (m_ptr == 0)))
    return 0;

  switch (m_type) {
  case REAL_RESULT:
    double2my_decimal(E_DEC_FATAL_ERROR, *(double*) m_ptr, val);
    break;
  case INT_RESULT:
    int2my_decimal(E_DEC_FATAL_ERROR, *(longlong*) m_ptr, 0, val);
    break;
  case DECIMAL_RESULT:
    my_decimal2decimal((my_decimal *) m_ptr, val);
    break;
  case STRING_RESULT:
    str2my_decimal(E_DEC_FATAL_ERROR, m_ptr, m_length,
                   collation.collation, val);
    break;
  case ROW_RESULT:
    DBUG_ASSERT(1);				// Impossible
    break;
  }
  return(val);
}

// just the assignment, for use in "SET @a:=5" type self-prints
void Item_func_set_user_var::print_assignment(String *str,
                                              enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("@"));
  str->append(name);
  str->append(STRING_WITH_LEN(":="));
  args[0]->print(str, query_type);
}

// parenthesize assignment for use in "EXPLAIN EXTENDED SELECT (@e:=80)+5"
void Item_func_set_user_var::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("("));
  print_assignment(str, query_type);
  str->append(STRING_WITH_LEN(")"));
}


String *
Item_func_get_user_var::val_str(String *str)
{
  DBUG_ASSERT(fixed == 1);
  DBUG_ENTER("Item_func_get_user_var::val_str");
  if (!var_entry)
    DBUG_RETURN((String*) 0);			// No such variable
  DBUG_RETURN(var_entry->val_str(&null_value, str, decimals));
}


double Item_func_get_user_var::val_real()
{
  DBUG_ASSERT(fixed == 1);
  if (!var_entry)
    return 0.0;					// No such variable
  return (var_entry->val_real(&null_value));
}


my_decimal *Item_func_get_user_var::val_decimal(my_decimal *dec)
{
  DBUG_ASSERT(fixed == 1);
  if (!var_entry)
    return 0;
  return var_entry->val_decimal(&null_value, dec);
}


longlong Item_func_get_user_var::val_int()
{
  DBUG_ASSERT(fixed == 1);
  if (!var_entry)
    return LL(0);				// No such variable
  return (var_entry->val_int(&null_value));
}


bool Item_func_get_user_var::const_item() const
{
  return (!var_entry || current_thd->query_id != var_entry->update_query_id);
}


enum Item_result Item_func_get_user_var::result_type() const
{
  return m_cached_result_type;
}


void Item_func_get_user_var::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("(@"));
  append_identifier(current_thd, str, name);
  str->append(')');
}

void Item_user_var_as_out_param::set_null_value(const CHARSET_INFO* cs)
{
  entry->set_null_value(STRING_RESULT);
}


void Item_user_var_as_out_param::set_value(const char *str, uint length,
                                           const CHARSET_INFO* cs)
{
  entry->store((void*) str, length, STRING_RESULT, cs,
               DERIVATION_IMPLICIT, 0 /* unsigned_arg */);
}


double Item_user_var_as_out_param::val_real()
{
  DBUG_ASSERT(0);
  return 0.0;
}


longlong Item_user_var_as_out_param::val_int()
{
  DBUG_ASSERT(0);
  return 0;
}


String* Item_user_var_as_out_param::val_str(String *str)
{
  DBUG_ASSERT(0);
  return 0;
}


my_decimal* Item_user_var_as_out_param::val_decimal(my_decimal *decimal_buffer)
{
  DBUG_ASSERT(0);
  return 0;
}


void Item_user_var_as_out_param::print(String *str, enum_query_type query_type)
{
  str->append('@');
  append_identifier(current_thd, str, name);
}


Item_func_get_system_var::
Item_func_get_system_var(sys_var *var_arg, enum_var_type var_type_arg,
                       LEX_STRING *component_arg, const char *name_arg,
                       size_t name_len_arg)
  :var(var_arg), var_type(var_type_arg), orig_var_type(var_type_arg),
  component(*component_arg), cache_present(0)
{
  /* copy() will allocate the name */
  item_name.copy(name_arg, (uint) name_len_arg);
}

void Item_func_get_system_var::print(String *str, enum_query_type query_type)
{
  str->append(item_name);
}


enum Item_result Item_func_get_system_var::result_type() const
{
  switch (var->show_type())
  {
    case SHOW_BOOL:
    case SHOW_MY_BOOL:
    case SHOW_INT:
    case SHOW_LONG:
    case SHOW_SIGNED_LONG:
    case SHOW_LONGLONG:
    case SHOW_HA_ROWS:
      return INT_RESULT;
    case SHOW_CHAR: 
    case SHOW_CHAR_PTR: 
    case SHOW_LEX_STRING:
      return STRING_RESULT;
    case SHOW_DOUBLE:
      return REAL_RESULT;
    default:
      my_error(ER_VAR_CANT_BE_READ, MYF(0), var->name.str);
      return STRING_RESULT;                   // keep the compiler happy
  }
}


enum_field_types Item_func_get_system_var::field_type() const
{
  switch (var->show_type())
  {
    case SHOW_BOOL:
    case SHOW_MY_BOOL:
    case SHOW_INT:
    case SHOW_LONG:
    case SHOW_SIGNED_LONG:
    case SHOW_LONGLONG:
    case SHOW_HA_ROWS:
      return MYSQL_TYPE_LONGLONG;
    case SHOW_CHAR: 
    case SHOW_CHAR_PTR: 
    case SHOW_LEX_STRING:
      return MYSQL_TYPE_VARCHAR;
    case SHOW_DOUBLE:
      return MYSQL_TYPE_DOUBLE;
    default:
      my_error(ER_VAR_CANT_BE_READ, MYF(0), var->name.str);
      return MYSQL_TYPE_VARCHAR;              // keep the compiler happy
  }
}


/*
  Uses var, var_type, component, cache_present, used_query_id, thd,
  cached_llval, null_value, cached_null_value
*/
#define get_sys_var_safe(type) \
do { \
  type value; \
  mysql_mutex_lock(&LOCK_global_system_variables); \
  value= *(type*) var->value_ptr(thd, var_type, &component); \
  mysql_mutex_unlock(&LOCK_global_system_variables); \
  cache_present |= GET_SYS_VAR_CACHE_LONG; \
  used_query_id= thd->query_id; \
  cached_llval= null_value ? 0 : (longlong) value; \
  cached_null_value= null_value; \
  return cached_llval; \
} while (0)


longlong Item_func_get_system_var::val_int()
{
      return 0;                               // keep the compiler happy
}


String* Item_func_get_system_var::val_str(String* str)
{
  return NULL;
}


double Item_func_get_system_var::val_real()
{
    return 0;
}


double Item_func_match::val_real()
{
  return 0.0;
}

void Item_func_match::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("(match "));
  print_args(str, 1, query_type);
  str->append(STRING_WITH_LEN(" against ("));
  args[0]->print(str, query_type);
  if (flags & FT_BOOL)
    str->append(STRING_WITH_LEN(" in boolean mode"));
  else if (flags & FT_EXPAND)
    str->append(STRING_WITH_LEN(" with query expansion"));
  str->append(STRING_WITH_LEN("))"));
}

longlong Item_func_bit_xor::val_int()
{
  DBUG_ASSERT(fixed == 1);
  ulonglong arg1= (ulonglong) args[0]->val_int();
  ulonglong arg2= (ulonglong) args[1]->val_int();
  if ((null_value= (args[0]->null_value || args[1]->null_value)))
    return 0;
  return (longlong) (arg1 ^ arg2);
}


/***************************************************************************
  System variables
****************************************************************************/

/**
  Return value of an system variable base[.name] as a constant item.

  @param thd			Thread handler
  @param var_type		global / session
  @param name		        Name of base or system variable
  @param component		Component.

  @note
    If component.str = 0 then the variable name is in 'name'

  @return
    - 0  : error
    - #  : constant item
*/


Item *get_system_var(THD *thd, enum_var_type var_type, LEX_STRING name,
		     LEX_STRING component)
{
  sys_var *var;
  LEX_STRING *base_name, *component_name;

  if (component.str)
  {
    base_name= &component;
    component_name= &name;
  }
  else
  {
    base_name= &name;
    component_name= &component;			// Empty string
  }

  if (!(var= find_sys_var(thd, base_name->str, base_name->length)))
    return 0;
  if (component.str)
  {
    if (!var->is_struct())
    {
      my_error(ER_VARIABLE_IS_NOT_STRUCT, MYF(0), base_name->str);
      return 0;
    }
  }
  thd->lex->uncacheable(UNCACHEABLE_SIDEEFFECT);

  set_if_smaller(component_name->length, MAX_SYS_VAR_LENGTH);
  
  var->do_deprecated_warning(thd);

  return new Item_func_get_system_var(var, var_type, component_name,
                                      NULL, 0);
}


longlong Item_func_row_count::val_int()
{
  DBUG_ASSERT(fixed == 1);
  THD *thd= current_thd;

  return thd->get_row_count_func();
}




Item_func_sp::Item_func_sp(Name_resolution_context *context_arg, sp_name *name)
  :Item_func(), context(context_arg), m_name(name), m_sp(NULL)
{
  maybe_null= 1;
  m_name->init_qname(current_thd);
  with_stored_program= true;
}


Item_func_sp::Item_func_sp(Name_resolution_context *context_arg,
                           sp_name *name, List<Item> &list)
  :Item_func(list), context(context_arg), m_name(name), m_sp(NULL)
{
  maybe_null= 1;
  m_name->init_qname(current_thd);
  with_stored_program= true;
}




const char *
Item_func_sp::func_name() const
{
  THD *thd= current_thd;
  /* Calculate length to avoid reallocation of string for sure */
  uint len= (((m_name->m_explicit_name ? m_name->m_db.length : 0) +
              m_name->m_name.length)*2 + //characters*quoting
             2 +                         // ` and `
             (m_name->m_explicit_name ?
              3 : 0) +                   // '`', '`' and '.' for the db
             1 +                         // end of string
             ALIGN_SIZE(1));             // to avoid String reallocation
  String qname((char *)alloc_root(thd->mem_root, len), len,
               system_charset_info);

  qname.length(0);
  if (m_name->m_explicit_name)
  {
    append_identifier(thd, &qname, m_name->m_db.str, m_name->m_db.length);
    qname.append('.');
  }
  append_identifier(thd, &qname, m_name->m_name.str, m_name->m_name.length);
  return qname.ptr();
}


table_map Item_func_sp::get_initial_pseudo_tables() const
{
  return m_sp->m_chistics->detistic ? 0 : RAND_TABLE_BIT;
}


void my_missing_function_error(const LEX_STRING &token, const char *func_name)
{
  if (token.length && is_lex_native_function (&token))
    my_error(ER_FUNC_INEXISTENT_NAME_COLLISION, MYF(0), func_name);
  else
    my_error(ER_SP_DOES_NOT_EXIST, MYF(0), "FUNCTION", func_name);
}


/*
  uuid_short handling.

  The short uuid is defined as a longlong that contains the following bytes:

  Bytes  Comment
  1      Server_id & 255
  4      Startup time of server in seconds
  3      Incrementor

  This means that an uuid is guaranteed to be unique
  even in a replication environment if the following holds:

  - The last byte of the server id is unique
  - If you between two shutdown of the server don't get more than
    an average of 2^24 = 16M calls to uuid_short() per second.
*/

ulonglong uuid_value;

void uuid_short_init()
{
  uuid_value= 0;
}


longlong Item_func_uuid_short::val_int()
{
  ulonglong val;
  mysql_mutex_lock(&LOCK_uuid_generator);
  val= uuid_value++;
  mysql_mutex_unlock(&LOCK_uuid_generator);
  return (longlong) val;
}
