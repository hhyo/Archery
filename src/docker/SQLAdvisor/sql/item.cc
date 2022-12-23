/*
   Copyright (c) 2000, 2014, Oracle and/or its affiliates. All rights reserved.

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


#include "my_global.h"                          /* NO_EMBEDDED_ACCESS_CHECKS */
#include "sql_priv.h"
#include "unireg.h"                    // REQUIRED: for other includes
#include <mysql.h>
#include <m_ctype.h>
#include "my_dir.h"
#include "sp_head.h"                  // sp_prepare_func_item
#include "sp.h"                       // sp_map_item_type
#include "sql_trigger.h"
#include "sql_show.h"                           // append_identifier
#include "sql_view.h"                           // VIEW_ANY_SQL
#include "sql_time.h"                  // str_to_datetime_with_warn,
                                       // make_truncated_value_warning
#include "sql_acl.h"                   // get_column_grant,
                                       // SELECT_ACL, UPDATE_ACL,
                                       // INSERT_ACL,
                                       // check_grant_column
#include "sql_base.h"                  // enum_resolution_type,
                                       // REPORT_EXCEPT_NOT_FOUND,
                                       // find_item_in_list,
                                       // RESOLVED_AGAINST_ALIAS, ...
#include "sql_test.h"                  // print_where

using std::min;
using std::max;

const String my_null_string("NULL", 4, default_charset_info);

/*****************************************************************************
** Item functions
*****************************************************************************/

/**
  Init all special items.
*/

void item_init(void)
{
  item_func_sleep_init();
  uuid_short_init();
}



/**
  @todo
    Make this functions class dependent
*/

bool Item::val_bool()
{
  switch(result_type()) {
  case INT_RESULT:
    return val_int() != 0;
  case DECIMAL_RESULT:
  {
    my_decimal decimal_value;
    my_decimal *val= val_decimal(&decimal_value);
    if (val)
      return !my_decimal_is_zero(val);
    return 0;
  }
  case REAL_RESULT:
  case STRING_RESULT:
    return val_real() != 0.0;
  case ROW_RESULT:
  default:
    DBUG_ASSERT(0);
    return 0;                                   // Wrong (but safe)
  }
}


/*
  For the items which don't have its own fast val_str_ascii()
  implementation we provide a generic slower version,
  which converts from the Item character set to ASCII.
  For better performance conversion happens only in 
  case of a "tricky" Item character set (e.g. UCS2).
  Normally conversion does not happen.
*/
String *Item::val_str_ascii(String *str)
{
  if (!(collation.collation->state & MY_CS_NONASCII))
    return val_str(str);
  
  DBUG_ASSERT(str != &str_value);
  
  uint errors;
  String *res= val_str(&str_value);
  if (!res)
    return 0;
  
  if ((null_value= str->copy(res->ptr(), res->length(),
                             collation.collation, &my_charset_latin1,
                             &errors)))
    return 0;
  
  return str;
}


String *Item::val_string_from_real(String *str)
{
  double nr= val_real();
  if (null_value)
    return 0;					/* purecov: inspected */
  str->set_real(nr,decimals, &my_charset_bin);
  return str;
}


String *Item::val_string_from_int(String *str)
{
  longlong nr= val_int();
  if (null_value)
    return 0;
  str->set_int(nr, unsigned_flag, &my_charset_bin);
  return str;
}


String *Item::val_string_from_decimal(String *str)
{
  my_decimal dec_buf, *dec= val_decimal(&dec_buf);
  if (null_value)
    return 0;
  my_decimal_round(E_DEC_FATAL_ERROR, dec, decimals, FALSE, &dec_buf);
  my_decimal2string(E_DEC_FATAL_ERROR, &dec_buf, 0, 0, 0, str);
  return str;
}


my_decimal *Item::val_decimal_from_real(my_decimal *decimal_value)
{
  double nr= val_real();
  if (null_value)
    return 0;
  double2my_decimal(E_DEC_FATAL_ERROR, nr, decimal_value);
  return (decimal_value);
}


my_decimal *Item::val_decimal_from_int(my_decimal *decimal_value)
{
  longlong nr= val_int();
  if (null_value)
    return 0;
  int2my_decimal(E_DEC_FATAL_ERROR, nr, unsigned_flag, decimal_value);
  return decimal_value;
}


my_decimal *Item::val_decimal_from_string(my_decimal *decimal_value)
{
  String *res;

  if (!(res= val_str(&str_value)))
    return NULL;

  if (str2my_decimal(E_DEC_FATAL_ERROR & ~E_DEC_BAD_NUM,
                     res->ptr(), res->length(), res->charset(),
                     decimal_value) & E_DEC_BAD_NUM)
  {
    ErrConvString err(res);
    push_warning_printf(current_thd, Sql_condition::WARN_LEVEL_WARN,
                        ER_TRUNCATED_WRONG_VALUE,
                        ER(ER_TRUNCATED_WRONG_VALUE), "DECIMAL",
                        err.ptr());
  }
  return decimal_value;
}

double Item::val_real_from_decimal()
{
  /* Note that fix_fields may not be called for Item_avg_field items */
  double result;
  my_decimal value_buff, *dec_val= val_decimal(&value_buff);
  if (null_value)
    return 0.0;
  my_decimal2double(E_DEC_FATAL_ERROR, dec_val, &result);
  return result;
}


longlong Item::val_int_from_decimal()
{
  /* Note that fix_fields may not be called for Item_avg_field items */
  longlong result;
  my_decimal value, *dec_val= val_decimal(&value);
  if (null_value)
    return 0;
  my_decimal2int(E_DEC_FATAL_ERROR, dec_val, unsigned_flag, &result);
  return result;
}

Item::Item():
  is_expensive_cache(-1), rsize(0),
  marker(0), fixed(0),
  collation(&my_charset_bin, DERIVATION_COERCIBLE),
  runtime_item(false), with_subselect(false),
  with_stored_program(false), tables_locked_cache(false)
{
  maybe_null=null_value=with_sum_func=unsigned_flag=0;
  decimals= 0; max_length= 0;
  cmp_context= (Item_result)-1;

  /* Put item in free list so that we can free all items at end */
  THD *thd= current_thd;
  next= thd->free_list;
  thd->free_list= this;
  /*
    Item constructor can be called during execution other then SQL_COM
    command => we should check thd->lex->current_select on zero (thd->lex
    can be uninitialised)
  */
  if (thd->lex->current_select)
  {
    enum_parsing_place place= 
      thd->lex->current_select->parsing_place;
    if (place == SELECT_LIST ||
	place == IN_HAVING)
      thd->lex->current_select->select_n_having_items++;
  }
}

/**
  Constructor used by Item_field, Item_ref & aggregate (sum)
  functions.

  Used for duplicating lists in processing queries with temporary
  tables.
*/
Item::Item(THD *thd, Item *item):
  is_expensive_cache(-1),
  rsize(0),
  str_value(item->str_value),
  item_name(item->item_name),
  orig_name(item->orig_name),
  max_length(item->max_length),
  marker(item->marker),
  decimals(item->decimals),
  maybe_null(item->maybe_null),
  null_value(item->null_value),
  unsigned_flag(item->unsigned_flag),
  with_sum_func(item->with_sum_func),
  fixed(item->fixed),
  collation(item->collation),
  cmp_context(item->cmp_context),
  runtime_item(false),
  with_subselect(item->has_subquery()),
  with_stored_program(item->with_stored_program),
  tables_locked_cache(item->tables_locked_cache)
{
  next= thd->free_list;				// Put in free list
  thd->free_list= this;
}


uint Item::decimal_precision() const
{
  Item_result restype= result_type();

  if ((restype == DECIMAL_RESULT) || (restype == INT_RESULT))
  {
    uint prec= 
      my_decimal_length_to_precision(max_char_length(), decimals,
                                     unsigned_flag);
    return min<uint>(prec, DECIMAL_MAX_PRECISION);
  }
  switch (field_type())
  {
    case MYSQL_TYPE_TIME:
      return decimals + TIME_INT_DIGITS;
    case MYSQL_TYPE_DATETIME:
    case MYSQL_TYPE_TIMESTAMP:
      return decimals + DATETIME_INT_DIGITS;
    case MYSQL_TYPE_DATE:
      return decimals + DATE_INT_DIGITS;
    default:
      break;
  }
  return min<uint>(max_char_length(), DECIMAL_MAX_PRECISION);
}


void Item::print_item_w_name(String *str, enum_query_type query_type)
{
  print(str, query_type);

  if (item_name.is_set())
  {
    THD *thd= current_thd;
    str->append(STRING_WITH_LEN(" AS "));
    append_identifier(thd, str, item_name);
  }
}


/**
   @details
   "SELECT (subq) GROUP BY (same_subq)" confuses ONLY_FULL_GROUP_BY (it does
   not see that both subqueries are the same, raises an error).
   To avoid hitting this problem, if the original query was:
   "SELECT expression AS x GROUP BY x", we print "GROUP BY x", not
   "GROUP BY expression". Same for ORDER BY.
   This has practical importance for views created as
   "CREATE VIEW v SELECT (subq) AS x GROUP BY x"
   (print_order() is used to write the view's definition in the frm file).
   We make one exception: if the view is merge-able, its ORDER clause will be
   merged into the parent query's. If an identifier in the merged ORDER clause
   is allowed to be either an alias or an expression of the view's underlying
   tables, resolution is difficult: it may be to be found in the underlying
   tables of the view, or in the SELECT list of the view; unlike other ORDER
   elements directly originating from the parent query.
   To avoid this problem, if the view is merge-able, we print the
   expression. This does not cause problems with only_full_group_by, because a
   merge-able view never has GROUP BY. @see mysql_register_view().
*/
void Item::print_for_order(String *str,
                           enum_query_type query_type,
                           bool used_alias)
{
  if (used_alias)
  {
    DBUG_ASSERT(item_name.is_set());
    // In the clause, user has referenced expression using an alias; we use it
    append_identifier(current_thd, str, item_name);
  }
  else
    print(str,query_type);
}

/**
  rename item (used for views, cleanup() return original name).

  @param new_name	new name of item;
*/

void Item::rename(char *new_name)
{
  /*
    we can compare pointers to names here, because if name was not changed,
    pointer will be same
  */
  if (!orig_name.is_set() && new_name != item_name.ptr())
    orig_name= item_name;
  item_name.set(new_name);
}




Item_ident::Item_ident(Name_resolution_context *context_arg,
                       const char *db_name_arg,const char *table_name_arg,
		       const char *field_name_arg)
  :orig_db_name(db_name_arg), orig_table_name(table_name_arg),
   orig_field_name(field_name_arg), context(context_arg),
   db_name(db_name_arg), table_name(table_name_arg),
   field_name(field_name_arg),
   alias_name_used(FALSE), cached_field_index(NO_CACHED_FIELD_INDEX),
   cached_table(0), depended_from(0)
{
  item_name.set(field_name_arg);
}


/**
  Constructor used by Item_field & Item_*_ref (see Item comment)
*/

Item_ident::Item_ident(THD *thd, Item_ident *item)
  :Item(thd, item),
   orig_db_name(item->orig_db_name),
   orig_table_name(item->orig_table_name), 
   orig_field_name(item->orig_field_name),
   context(item->context),
   db_name(item->db_name),
   table_name(item->table_name),
   field_name(item->field_name),
   alias_name_used(item->alias_name_used),
   cached_field_index(item->cached_field_index),
   cached_table(item->cached_table),
   depended_from(item->depended_from)
{}


bool Item::check_cols(uint c)
{
  if (c != 1)
  {
    my_error(ER_OPERAND_COLUMNS, MYF(0), c);
    return 1;
  }
  return 0;
}


const Name_string null_name_string(NULL, 0);


void Name_string::copy(const char *str, size_t length, const CHARSET_INFO *cs)
{
  if (!length)
  {
    /* Empty string, used by AS or internal function like last_insert_id() */
    set(str ? "" : NULL, 0);
    return;
  }
  if (cs->ctype)
  {
    /*
      This will probably need a better implementation in the future:
      a function in CHARSET_INFO structure.
    */
    while (length && !my_isgraph(cs, *str))
    {						// Fix problem with yacc
      length--;
      str++;
    }
  }
  if (!my_charset_same(cs, system_charset_info))
  {
    size_t res_length;
    char *tmp= sql_strmake_with_convert(str, length, cs, MAX_ALIAS_NAME,
                                        system_charset_info, &res_length);
    set(tmp, tmp ? res_length : 0);
  }
  else
  {
    size_t len= min<size_t>(length, MAX_ALIAS_NAME);
    char *tmp= sql_strmake(str, len);
    set(tmp, tmp ? len : 0);
  }
}


void Item_name_string::copy(const char *str_arg, size_t length_arg,
                            const CHARSET_INFO *cs_arg,
                            bool is_autogenerated_arg)
{
  m_is_autogenerated= is_autogenerated_arg;
  copy(str_arg, length_arg, cs_arg);
  if (length_arg > length() && !is_autogenerated())
  {
    ErrConvString tmp(str_arg, static_cast<uint>(length_arg), cs_arg);
    if (length() == 0)
      push_warning_printf(current_thd, Sql_condition::WARN_LEVEL_WARN,
                          ER_NAME_BECOMES_EMPTY, ER(ER_NAME_BECOMES_EMPTY),
                          tmp.ptr());
    else
      push_warning_printf(current_thd, Sql_condition::WARN_LEVEL_WARN,
                          ER_REMOVED_SPACES, ER(ER_REMOVED_SPACES),
                          tmp.ptr());
  }
}

const CHARSET_INFO *Item::default_charset()
{
  return current_thd->variables.collation_connection;
}


/*****************************************************************************
  Item_sp_variable methods
*****************************************************************************/

Item_sp_variable::Item_sp_variable(const Name_string sp_var_name)
  :m_thd(0), m_name(sp_var_name)
#ifndef DBUG_OFF
   , m_sp(0)
#endif
{
}


double Item_sp_variable::val_real()
{
  DBUG_ASSERT(fixed);
  Item *it= this_item();
  double ret= it->val_real();
  null_value= it->null_value;
  return ret;
}


longlong Item_sp_variable::val_int()
{
  DBUG_ASSERT(fixed);
  Item *it= this_item();
  longlong ret= it->val_int();
  null_value= it->null_value;
  return ret;
}


String *Item_sp_variable::val_str(String *sp)
{
  DBUG_ASSERT(fixed);
  Item *it= this_item();
  String *res= it->val_str(sp);

  null_value= it->null_value;

  if (!res)
    return NULL;

  /*
    This way we mark returned value of val_str as const,
    so that various functions (e.g. CONCAT) won't try to
    modify the value of the Item. Analogous mechanism is
    implemented for Item_param.
    Without this trick Item_splocal could be changed as a
    side-effect of expression computation. Here is an example
    of what happens without it: suppose x is varchar local
    variable in a SP with initial value 'ab' Then
      select concat(x,'c');
    would change x's value to 'abc', as Item_func_concat::val_str()
    would use x's internal buffer to compute the result.
    This is intended behaviour of Item_func_concat. Comments to
    Item_param class contain some more details on the topic.
  */

  if (res != &str_value)
    str_value.set(res->ptr(), res->length(), res->charset());
  else
    res->mark_as_const();

  return &str_value;
}


my_decimal *Item_sp_variable::val_decimal(my_decimal *decimal_value)
{
  DBUG_ASSERT(fixed);
  Item *it= this_item();
  my_decimal *val= it->val_decimal(decimal_value);
  null_value= it->null_value;
  return val;
}



bool Item_sp_variable::is_null()
{
  return this_item()->is_null();
}


/**
  Convert temporal real types as retuned by field->real_type()
  to field type as returned by field->type().

  @param real_type  Real type.
  @retval           Field type.
*/
inline enum_field_types real_type_to_type(enum_field_types real_type)
{
    switch (real_type)
    {
        case MYSQL_TYPE_TIME2:
            return MYSQL_TYPE_TIME;
        case MYSQL_TYPE_DATETIME2:
            return MYSQL_TYPE_DATETIME;
        case MYSQL_TYPE_TIMESTAMP2:
            return MYSQL_TYPE_TIMESTAMP;
        case MYSQL_TYPE_NEWDATE:
            return MYSQL_TYPE_DATE;
            /* Note: NEWDECIMAL is a type, not only a real_type */
        default: return real_type;
    }
}

/*****************************************************************************
  Item_splocal methods
*****************************************************************************/

Item_splocal::Item_splocal(const Name_string sp_var_name,
                           uint sp_var_idx,
                           enum_field_types sp_var_type,
                           uint pos_in_q, uint len_in_q)
  :Item_sp_variable(sp_var_name),
   m_var_idx(sp_var_idx),
   limit_clause_param(FALSE),
   pos_in_query(pos_in_q), len_in_query(len_in_q)
{
  maybe_null= TRUE;

  sp_var_type= real_type_to_type(sp_var_type);
  m_type= sp_map_item_type(sp_var_type);
  m_field_type= sp_var_type;
  m_result_type= sp_map_result_type(sp_var_type);
}

void Item_splocal::print(String *str, enum_query_type)
{
  str->reserve(m_name.length() + 8);
  str->append(m_name);
  str->append('@');
  str->qs_append(m_var_idx);
}



/*****************************************************************************
  Item_case_expr methods
*****************************************************************************/

Item_case_expr::Item_case_expr(uint case_expr_id)
  :Item_sp_variable(Name_string(C_STRING_WITH_LEN("case_expr"))),
   m_case_expr_id(case_expr_id)
{
}

void Item_case_expr::print(String *str, enum_query_type)
{
  if (str->reserve(MAX_INT_WIDTH + sizeof("case_expr@")))
    return;                                    /* purecov: inspected */
  (void) str->append(STRING_WITH_LEN("case_expr@"));
  str->qs_append(m_case_expr_id);
}


/*****************************************************************************
  Item_name_const methods
*****************************************************************************/

double Item_name_const::val_real()
{
  DBUG_ASSERT(fixed);
  double ret= value_item->val_real();
  null_value= value_item->null_value;
  return ret;
}


longlong Item_name_const::val_int()
{
  DBUG_ASSERT(fixed);
  longlong ret= value_item->val_int();
  null_value= value_item->null_value;
  return ret;
}


String *Item_name_const::val_str(String *sp)
{
  DBUG_ASSERT(fixed);
  String *ret= value_item->val_str(sp);
  null_value= value_item->null_value;
  return ret;
}


my_decimal *Item_name_const::val_decimal(my_decimal *decimal_value)
{
  DBUG_ASSERT(fixed);
  my_decimal *val= value_item->val_decimal(decimal_value);
  null_value= value_item->null_value;
  return val;
}


bool Item_name_const::is_null()
{
  return value_item->is_null();
}


Item_name_const::Item_name_const(Item *name_arg, Item *val):
    value_item(val), name_item(name_arg)
{
  /*
    The value argument to NAME_CONST can only be a literal 
    constant.   Some extra tests are needed to support
    a collation specificer and to handle negative values
  */
    
  if (!(valid_args= name_item->basic_const_item() &&
                    (value_item->basic_const_item() ||
                     ((value_item->type() == FUNC_ITEM) &&
                      ((((Item_func *) value_item)->functype() ==
                         Item_func::COLLATE_FUNC) ||
                      ((((Item_func *) value_item)->functype() ==
                         Item_func::NEG_FUNC) &&
                      (((Item_func *) value_item)->key_item()->basic_const_item())))))))
    my_error(ER_WRONG_ARGUMENTS, MYF(0), "NAME_CONST");
  Item::maybe_null= TRUE;
}


Item::Type Item_name_const::type() const
{
  /*
    As 
    1. one can try to create the Item_name_const passing non-constant 
    arguments, although it's incorrect and 
    2. the type() method can be called before the fix_fields() to get
    type information for a further type cast, e.g. 
    if (item->type() == FIELD_ITEM) 
      ((Item_field *) item)->... 
    we return NULL_ITEM in the case to avoid wrong casting.

    valid_args guarantees value_item->basic_const_item(); if type is
    FUNC_ITEM, then we have a fudged item_func_neg() on our hands
    and return the underlying type.
    For Item_func_set_collation()
    e.g. NAME_CONST('name', 'value' COLLATE collation) we return its
    'value' argument type. 
  */
  if (!valid_args)
    return NULL_ITEM;
  Item::Type value_type= value_item->type();
  if (value_type == FUNC_ITEM)
  {
    /* 
      The second argument of NAME_CONST('name', 'value') must be 
      a simple constant item or a NEG_FUNC/COLLATE_FUNC.
    */
    DBUG_ASSERT(((Item_func *) value_item)->functype() == 
                Item_func::NEG_FUNC ||
                ((Item_func *) value_item)->functype() == 
                Item_func::COLLATE_FUNC);
    return ((Item_func *) value_item)->key_item()->type();            
  }
  return value_type;
}


void Item_name_const::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("NAME_CONST("));
  name_item->print(str, query_type);
  str->append(',');
  value_item->print(str, query_type);
  str->append(')');
}


static bool
left_is_superset(DTCollation *left, DTCollation *right)
{
  /* Allow convert to Unicode */
  if (left->collation->state & MY_CS_UNICODE &&
      (left->derivation < right->derivation ||
       (left->derivation == right->derivation &&
        (!(right->collation->state & MY_CS_UNICODE) ||
         /* The code below makes 4-byte utf8 a superset over 3-byte utf8 */
         (left->collation->state & MY_CS_UNICODE_SUPPLEMENT &&
          !(right->collation->state & MY_CS_UNICODE_SUPPLEMENT) &&
          left->collation->mbmaxlen > right->collation->mbmaxlen &&
          left->collation->mbminlen == right->collation->mbminlen)))))
    return TRUE;
  /* Allow convert from ASCII */
  if (right->repertoire == MY_REPERTOIRE_ASCII &&
      (left->derivation < right->derivation ||
       (left->derivation == right->derivation &&
        !(left->repertoire == MY_REPERTOIRE_ASCII))))
    return TRUE;
  /* Disallow conversion otherwise */
  return FALSE;
}

/**
  Aggregate two collations together taking
  into account their coercibility (aka derivation):.

  0 == DERIVATION_EXPLICIT  - an explicitly written COLLATE clause @n
  1 == DERIVATION_NONE      - a mix of two different collations @n
  2 == DERIVATION_IMPLICIT  - a column @n
  3 == DERIVATION_COERCIBLE - a string constant.

  The most important rules are:
  -# If collations are the same:
  chose this collation, and the strongest derivation.
  -# If collations are different:
  - Character sets may differ, but only if conversion without
  data loss is possible. The caller provides flags whether
  character set conversion attempts should be done. If no
  flags are substituted, then the character sets must be the same.
  Currently processed flags are:
  MY_COLL_ALLOW_SUPERSET_CONV  - allow conversion to a superset
  MY_COLL_ALLOW_COERCIBLE_CONV - allow conversion of a coercible value
  - two EXPLICIT collations produce an error, e.g. this is wrong:
  CONCAT(expr1 collate latin1_swedish_ci, expr2 collate latin1_german_ci)
  - the side with smaller derivation value wins,
  i.e. a column is stronger than a string constant,
  an explicit COLLATE clause is stronger than a column.
  - if derivations are the same, we have DERIVATION_NONE,
  we'll wait for an explicit COLLATE clause which possibly can
  come from another argument later: for example, this is valid,
  but we don't know yet when collecting the first two arguments:
     @code
       CONCAT(latin1_swedish_ci_column,
              latin1_german1_ci_column,
              expr COLLATE latin1_german2_ci)
  @endcode
*/

bool DTCollation::aggregate(DTCollation &dt, uint flags)
{
  if (!my_charset_same(collation, dt.collation))
  {
    /*
       We do allow to use binary strings (like BLOBS)
       together with character strings.
       Binaries have more precedence than a character
       string of the same derivation.
    */
    if (collation == &my_charset_bin)
    {
      if (derivation <= dt.derivation)
	; // Do nothing
      else
      {
	set(dt);
      }
    }
    else if (dt.collation == &my_charset_bin)
    {
      if (dt.derivation <= derivation)
      {
        set(dt);
      }
    }
    else if ((flags & MY_COLL_ALLOW_SUPERSET_CONV) &&
             left_is_superset(this, &dt))
    {
      // Do nothing
    }
    else if ((flags & MY_COLL_ALLOW_SUPERSET_CONV) &&
             left_is_superset(&dt, this))
    {
      set(dt);
    }
    else if ((flags & MY_COLL_ALLOW_COERCIBLE_CONV) &&
             derivation < dt.derivation &&
             dt.derivation >= DERIVATION_SYSCONST)
    {
      // Do nothing;
    }
    else if ((flags & MY_COLL_ALLOW_COERCIBLE_CONV) &&
             dt.derivation < derivation &&
             derivation >= DERIVATION_SYSCONST)
    {
      set(dt);
    }
    else
    {
      // Cannot apply conversion
      set(&my_charset_bin, DERIVATION_NONE,
          (dt.repertoire|repertoire));
      return 1;
    }
  }
  else if (derivation < dt.derivation)
  {
    // Do nothing
  }
  else if (dt.derivation < derivation)
  {
    set(dt);
  }
  else
  {
    if (collation == dt.collation)
    {
      // Do nothing
    }
    else
    {
      if (derivation == DERIVATION_EXPLICIT)
      {
        set(0, DERIVATION_NONE, 0);
        return 1;
      }
      if (collation->state & MY_CS_BINSORT)
        return 0;
      if (dt.collation->state & MY_CS_BINSORT)
      {
        set(dt);
        return 0;
      }
      const CHARSET_INFO *bin= get_charset_by_csname(collation->csname,
                                                     MY_CS_BINSORT,MYF(0));
      set(bin, DERIVATION_NONE);
    }
  }
  repertoire|= dt.repertoire;
  return 0;
}

/******************************/
static
void my_coll_agg_error(DTCollation &c1, DTCollation &c2, const char *fname)
{
  my_error(ER_CANT_AGGREGATE_2COLLATIONS,MYF(0),
           c1.collation->name,c1.derivation_name(),
           c2.collation->name,c2.derivation_name(),
           fname);
}


static
void my_coll_agg_error(DTCollation &c1, DTCollation &c2, DTCollation &c3,
                       const char *fname)
{
  my_error(ER_CANT_AGGREGATE_3COLLATIONS,MYF(0),
  	   c1.collation->name,c1.derivation_name(),
	   c2.collation->name,c2.derivation_name(),
	   c3.collation->name,c3.derivation_name(),
	   fname);
}


static
void my_coll_agg_error(Item** args, uint count, const char *fname,
                       int item_sep)
{
  if (count == 2)
    my_coll_agg_error(args[0]->collation, args[item_sep]->collation, fname);
  else if (count == 3)
    my_coll_agg_error(args[0]->collation, args[item_sep]->collation,
                      args[2*item_sep]->collation, fname);
  else
    my_error(ER_CANT_AGGREGATE_NCOLLATIONS,MYF(0),fname);
}


bool agg_item_collations(DTCollation &c, const char *fname,
                         Item **av, uint count, uint flags, int item_sep)
{
  uint i;
  Item **arg;
  bool unknown_cs= 0;

  c.set(av[0]->collation);
  for (i= 1, arg= &av[item_sep]; i < count; i++, arg++)
  {
    if (c.aggregate((*arg)->collation, flags))
    {
      if (c.derivation == DERIVATION_NONE &&
          c.collation == &my_charset_bin)
      {
        unknown_cs= 1;
        continue;
      }
      my_coll_agg_error(av, count, fname, item_sep);
      return TRUE;
    }
  }

  if (unknown_cs &&
      c.derivation != DERIVATION_EXPLICIT)
  {
    my_coll_agg_error(av, count, fname, item_sep);
    return TRUE;
  }

  if ((flags & MY_COLL_DISALLOW_NONE) &&
      c.derivation == DERIVATION_NONE)
  {
    my_coll_agg_error(av, count, fname, item_sep);
    return TRUE;
  }

  /* If all arguments where numbers, reset to @@collation_connection */
  if (flags & MY_COLL_ALLOW_NUMERIC_CONV &&
      c.derivation == DERIVATION_NUMERIC)
    c.set(Item::default_charset(), DERIVATION_COERCIBLE, MY_REPERTOIRE_NUMERIC);

  return FALSE;
}



Item_field::Item_field(Name_resolution_context *context_arg,
                       const char *db_arg,const char *table_name_arg,
                       const char *field_name_arg)
  :Item_ident(context_arg, db_arg,table_name_arg,field_name_arg),
   item_equal(0), no_const_subst(0),
   have_privileges(0), any_privileges(0)
{
  SELECT_LEX *select= current_thd->lex->current_select;
  collation.set(DERIVATION_IMPLICIT);
  if (select && select->parsing_place != IN_HAVING)
      select->select_n_where_fields++;
}

/**
  Constructor need to process subselect with temporary tables (see Item)
*/

Item_field::Item_field(THD *thd, Item_field *item)
  :Item_ident(thd, item),
   item_equal(item->item_equal),
   no_const_subst(item->no_const_subst),
   have_privileges(item->have_privileges),
   any_privileges(item->any_privileges)
{
  collation.set(DERIVATION_IMPLICIT);
}


const char *Item_ident::full_name() const
{
  char *tmp;
  if (!table_name || !field_name)
    return field_name ? field_name : item_name.is_set() ? item_name.ptr() : "tmp_field";
  if (db_name && db_name[0])
  {
    tmp=(char*) sql_alloc((uint) strlen(db_name)+(uint) strlen(table_name)+
			  (uint) strlen(field_name)+3);
    strxmov(tmp,db_name,".",table_name,".",field_name,NullS);
  }
  else
  {
    if (table_name[0])
    {
      tmp= (char*) sql_alloc((uint) strlen(table_name) +
			     (uint) strlen(field_name) + 2);
      strxmov(tmp, table_name, ".", field_name, NullS);
    }
    else
      tmp= (char*) field_name;
  }
  return tmp;
}

void Item_ident::print(String *str, enum_query_type query_type)
{
  THD *thd= current_thd;
  char d_name_buff[MAX_ALIAS_NAME], t_name_buff[MAX_ALIAS_NAME];
  const char *d_name= db_name, *t_name= table_name;
  if (lower_case_table_names== 1 ||
      (lower_case_table_names == 2 && !alias_name_used))
  {
    if (table_name && table_name[0])
    {
      strmov(t_name_buff, table_name);
      my_casedn_str(files_charset_info, t_name_buff);
      t_name= t_name_buff;
    }
    if (db_name && db_name[0])
    {
      strmov(d_name_buff, db_name);
      my_casedn_str(files_charset_info, d_name_buff);
      d_name= d_name_buff;
    }
  }

  if (!table_name || !field_name || !field_name[0])
  {
    const char *nm= (field_name && field_name[0]) ?
                      field_name : item_name.is_set() ? item_name.ptr() : "tmp_field";
    append_identifier(thd, str, nm, (uint) strlen(nm));
    return;
  }
  if (db_name && db_name[0] && !alias_name_used)
  {
    if (!(cached_table && cached_table->belong_to_view &&
          cached_table->belong_to_view->compact_view_format))
    {
      const size_t d_name_len= strlen(d_name);
      if (!((query_type & QT_NO_DEFAULT_DB) &&
            db_is_default_db(d_name, d_name_len, thd)))
      {
        append_identifier(thd, str, d_name, (uint)d_name_len);
        str->append('.');
      }
    }
    append_identifier(thd, str, t_name, (uint)strlen(t_name));
    str->append('.');
    append_identifier(thd, str, field_name, (uint)strlen(field_name));
  }
  else
  {
    if (table_name[0])
    {
      append_identifier(thd, str, t_name, (uint) strlen(t_name));
      str->append('.');
      append_identifier(thd, str, field_name, (uint) strlen(field_name));
    }
    else
      append_identifier(thd, str, field_name, (uint) strlen(field_name));
  }
}

/**
  Create an item from a string we KNOW points to a valid longlong.
  str_arg does not necessary has to be a \\0 terminated string.
  This is always 'signed'. Unsigned values are created with Item_uint()
*/
Item_int::Item_int(const char *str_arg, uint length)
{
  char *end_ptr= (char*) str_arg + length;
  int error;
  value= my_strtoll10(str_arg, &end_ptr, &error);
  max_length= (uint) (end_ptr - str_arg);
  item_name.copy(str_arg, max_length);
  fixed= 1;
}


my_decimal *Item_int::val_decimal(my_decimal *decimal_value)
{
  int2my_decimal(E_DEC_FATAL_ERROR, value, unsigned_flag, decimal_value);
  return decimal_value;
}

String *Item_int::val_str(String *str)
{
  // following assert is redundant, because fixed=1 assigned in constructor
  DBUG_ASSERT(fixed == 1);
  str->set_int(value, unsigned_flag, collation.collation);
  return str;
}

void Item_int::print(String *str, enum_query_type query_type)
{
  // my_charset_bin is good enough for numbers
  str_value.set_int(value, unsigned_flag, &my_charset_bin);
  str->append(str_value);
}


String *Item_uint::val_str(String *str)
{
  // following assert is redundant, because fixed=1 assigned in constructor
  DBUG_ASSERT(fixed == 1);
  str->set((ulonglong) value, collation.collation);
  return str;
}


void Item_uint::print(String *str, enum_query_type query_type)
{
  // latin1 is good enough for numbers
  str_value.set((ulonglong) value, default_charset());
  str->append(str_value);
}


Item_decimal::Item_decimal(const char *str_arg, uint length,
                           const CHARSET_INFO *charset)
{
  str2my_decimal(E_DEC_FATAL_ERROR, str_arg, length, charset, &decimal_value);
  item_name.set(str_arg);
  decimals= (uint8) decimal_value.frac;
  fixed= 1;
  max_length= my_decimal_precision_to_length_no_truncation(decimal_value.intg +
                                                           decimals,
                                                           decimals,
                                                           unsigned_flag);
}

Item_decimal::Item_decimal(longlong val, bool unsig)
{
  int2my_decimal(E_DEC_FATAL_ERROR, val, unsig, &decimal_value);
  decimals= (uint8) decimal_value.frac;
  fixed= 1;
  max_length= my_decimal_precision_to_length_no_truncation(decimal_value.intg +
                                                           decimals,
                                                           decimals,
                                                           unsigned_flag);
}


Item_decimal::Item_decimal(double val, int precision, int scale)
{
  double2my_decimal(E_DEC_FATAL_ERROR, val, &decimal_value);
  decimals= (uint8) decimal_value.frac;
  fixed= 1;
  max_length= my_decimal_precision_to_length_no_truncation(decimal_value.intg +
                                                           decimals,
                                                           decimals,
                                                           unsigned_flag);
}


Item_decimal::Item_decimal(const Name_string &name_arg,
                           const my_decimal *val_arg,
                           uint decimal_par, uint length)
{
  my_decimal2decimal(val_arg, &decimal_value);
  item_name= name_arg;
  decimals= (uint8) decimal_par;
  max_length= length;
  fixed= 1;
}


Item_decimal::Item_decimal(my_decimal *value_par)
{
  my_decimal2decimal(value_par, &decimal_value);
  decimals= (uint8) decimal_value.frac;
  fixed= 1;
  max_length= my_decimal_precision_to_length_no_truncation(decimal_value.intg +
                                                           decimals,
                                                           decimals,
                                                           unsigned_flag);
}


Item_decimal::Item_decimal(const uchar *bin, int precision, int scale)
{
  binary2my_decimal(E_DEC_FATAL_ERROR, bin,
                    &decimal_value, precision, scale);
  decimals= (uint8) decimal_value.frac;
  fixed= 1;
  max_length= my_decimal_precision_to_length_no_truncation(precision, decimals,
                                                           unsigned_flag);
}


longlong Item_decimal::val_int()
{
  longlong result;
  my_decimal2int(E_DEC_FATAL_ERROR, &decimal_value, unsigned_flag, &result);
  return result;
}

double Item_decimal::val_real()
{
  double result;
  my_decimal2double(E_DEC_FATAL_ERROR, &decimal_value, &result);
  return result;
}

String *Item_decimal::val_str(String *result)
{
  result->set_charset(&my_charset_numeric);
  my_decimal2string(E_DEC_FATAL_ERROR, &decimal_value, 0, 0, 0, result);
  return result;
}

void Item_decimal::print(String *str, enum_query_type query_type)
{
  my_decimal2string(E_DEC_FATAL_ERROR, &decimal_value, 0, 0, 0, &str_value);
  str->append(str_value);
}



String *Item_float::val_str(String *str)
{
  // following assert is redundant, because fixed=1 assigned in constructor
  DBUG_ASSERT(fixed == 1);
  str->set_real(value,decimals,&my_charset_bin);
  return str;
}


my_decimal *Item_float::val_decimal(my_decimal *decimal_value)
{
  // following assert is redundant, because fixed=1 assigned in constructor
  DBUG_ASSERT(fixed == 1);
  double2my_decimal(E_DEC_FATAL_ERROR, value, decimal_value);
  return (decimal_value);
}


/**
   @sa enum_query_type.
   For us to be able to print a query (in debugging, optimizer trace, EXPLAIN
   EXTENDED) without changing the query's result, this function must not
   modify the item's content. Not even a realloc() of str_value is permitted:
   Item_func_concat/repeat/encode::val_str() depend on the allocated length;
   a change of this length can influence results of CONCAT(), REPEAT(),
   ENCODE()...
*/
void Item_string::print(String *str, enum_query_type query_type)
{
  const bool print_introducer=
    !(query_type & QT_WITHOUT_INTRODUCERS) && is_cs_specified();
  if (print_introducer)
  {
    str->append('_');
    str->append(collation.collation->csname);
  }

  str->append('\'');

  if (query_type & QT_TO_SYSTEM_CHARSET)
  {
    if (print_introducer)
    {
      /*
        Because we wrote an introducer, we must print str_value in its
        charset, and the resulting bytes must not be changed until they
        reach the end client.
        But the caller is asking for system_charset_info, and may later
        convert into character_set_results. That means two conversions: we
        must ensure that they don't change our printed bytes.
        So we print str_value in the least common denominator of the three
        charsets involved: ASCII. Non-ASCII characters are printed as \xFF
        sequences (which is ASCII too). This way, our bytes will not be
        changed.
      */
      ErrConvString tmp(str_value.ptr(), str_value.length(), &my_charset_bin);
      str->append(tmp.ptr());
    }
    else
    {
      if (my_charset_same(str_value.charset(), system_charset_info))
        str_value.print(str); // already in system_charset_info
      else // need to convert
      {
        THD *thd= current_thd;
        LEX_STRING utf8_lex_str;

        thd->convert_string(&utf8_lex_str,
                            system_charset_info,
                            str_value.ptr(),
                            str_value.length(),
                            str_value.charset());

        String utf8_str(utf8_lex_str.str,
                        utf8_lex_str.length,
                        system_charset_info);

        utf8_str.print(str);
      }
    }
  }
  else
  {
    // Caller wants a result in the charset of str_value.
    str_value.print(str);
  }

  str->append('\'');
}


double 
double_from_string_with_check (const CHARSET_INFO *cs,
                               const char *cptr, char *end)
{
  int error;
  char *org_end;
  double tmp;

  org_end= end;
  tmp= my_strntod(cs, (char*) cptr, end - cptr, &end, &error);
  if (error || (end != org_end && !check_if_only_end_space(cs, end, org_end)))
  {
    ErrConvString err(cptr, org_end - cptr, cs);
    push_warning_printf(current_thd, Sql_condition::WARN_LEVEL_WARN,
                        ER_TRUNCATED_WRONG_VALUE,
                        ER(ER_TRUNCATED_WRONG_VALUE), "DOUBLE",
                        err.ptr());
  }
  return tmp;
}


double Item_string::val_real()
{
  DBUG_ASSERT(fixed == 1);
  return double_from_string_with_check (str_value.charset(), str_value.ptr(), 
                                        (char *) str_value.ptr() + str_value.length());
}


longlong 
longlong_from_string_with_check (const CHARSET_INFO *cs,
                                 const char *cptr, char *end)
{
  int err;
  longlong tmp;
  char *org_end= end;

  tmp= (*(cs->cset->strtoll10))(cs, cptr, &end, &err);
  /*
    TODO: Give error if we wanted a signed integer and we got an unsigned
    one
  */
  if (!current_thd->no_errors &&
      (err > 0 ||
       (end != org_end && !check_if_only_end_space(cs, end, org_end))))
  {
    ErrConvString err(cptr, cs);
    push_warning_printf(current_thd, Sql_condition::WARN_LEVEL_WARN,
                        ER_TRUNCATED_WRONG_VALUE,
                        ER(ER_TRUNCATED_WRONG_VALUE), "INTEGER",
                        err.ptr());
  }
  return tmp;
}


/**
  @todo
  Give error if we wanted a signed integer and we got an unsigned one
*/
longlong Item_string::val_int()
{
  DBUG_ASSERT(fixed == 1);
  return longlong_from_string_with_check(str_value.charset(), str_value.ptr(),
                             (char *) str_value.ptr()+ str_value.length());
}


my_decimal *Item_string::val_decimal(my_decimal *decimal_value)
{
  return val_decimal_from_string(decimal_value);
}

double Item_null::val_real()
{
  // following assert is redundant, because fixed=1 assigned in constructor
  DBUG_ASSERT(fixed == 1);
  null_value=1;
  return 0.0;
}
longlong Item_null::val_int()
{
  // following assert is redundant, because fixed=1 assigned in constructor
  DBUG_ASSERT(fixed == 1);
  null_value=1;
  return 0;
}
/* ARGSUSED */
String *Item_null::val_str(String *str)
{
  // following assert is redundant, because fixed=1 assigned in constructor
  DBUG_ASSERT(fixed == 1);
  null_value=1;
  return 0;
}

my_decimal *Item_null::val_decimal(my_decimal *decimal_value)
{
  return 0;
}

/*********************** Item_param related ******************************/

/** 
  Default function of Item_param::set_param_func, so in case
  of malformed packet the server won't SIGSEGV.
*/

static void
default_set_param_func(Item_param *param,
                       uchar **pos __attribute__((unused)),
                       ulong len __attribute__((unused)))
{
  param->set_null();
}


Item_param::Item_param(uint pos_in_query_arg) :
  state(NO_VALUE),
  item_result_type(STRING_RESULT),
  /* Don't pretend to be a literal unless value for this item is set. */
  item_type(PARAM_ITEM),
  param_type(MYSQL_TYPE_VARCHAR),
  pos_in_query(pos_in_query_arg),
  set_param_func(default_set_param_func),
  limit_clause_param(FALSE)
{
  item_name.set("?");
  /* 
    Since we can't say whenever this item can be NULL or cannot be NULL
    before mysql_stmt_execute(), so we assuming that it can be NULL until
    value is set.
  */
  maybe_null= 1;
  cnvitem= new Item_string("", 0, &my_charset_bin, DERIVATION_COERCIBLE);
  cnvstr.set(cnvbuf, sizeof(cnvbuf), &my_charset_bin);
}


void Item_param::set_null()
{
  DBUG_ENTER("Item_param::set_null");
  /* These are cleared after each execution by reset() method */
  null_value= 1;
  /* 
    Because of NULL and string values we need to set max_length for each new
    placeholder value: user can submit NULL for any placeholder type, and 
    string length can be different in each execution.
  */
  max_length= 0;
  decimals= 0;
  state= NULL_VALUE;
  item_type= Item::NULL_ITEM;
  DBUG_VOID_RETURN;
}

void Item_param::set_int(longlong i, uint32 max_length_arg)
{
  DBUG_ENTER("Item_param::set_int");
  value.integer= (longlong) i;
  state= INT_VALUE;
  max_length= max_length_arg;
  decimals= 0;
  maybe_null= 0;
  DBUG_VOID_RETURN;
}

void Item_param::set_double(double d)
{
  DBUG_ENTER("Item_param::set_double");
  value.real= d;
  state= REAL_VALUE;
  max_length= DBL_DIG + 8;
  decimals= NOT_FIXED_DEC;
  maybe_null= 0;
  DBUG_VOID_RETURN;
}


/**
  Set decimal parameter value from string.

  @param str      character string
  @param length   string length

  @note
    As we use character strings to send decimal values in
    binary protocol, we use str2my_decimal to convert it to
    internal decimal value.
*/

void Item_param::set_decimal(const char *str, ulong length)
{
  char *end;
  DBUG_ENTER("Item_param::set_decimal");

  end= (char*) str+length;
  str2my_decimal(E_DEC_FATAL_ERROR, str, &decimal_value, &end);
  state= DECIMAL_VALUE;
  decimals= decimal_value.frac;
  max_length=
    my_decimal_precision_to_length_no_truncation(decimal_value.precision(),
                                                 decimals, unsigned_flag);
  maybe_null= 0;
  DBUG_VOID_RETURN;
}

void Item_param::set_decimal(const my_decimal *dv)
{
  state= DECIMAL_VALUE;

  my_decimal2decimal(dv, &decimal_value);

  decimals= (uint8) decimal_value.frac;
  unsigned_flag= !decimal_value.sign();
  max_length= my_decimal_precision_to_length(decimal_value.intg + decimals,
                                             decimals, unsigned_flag);
}

/**
  Set parameter value from MYSQL_TIME value.

  @param tm              datetime value to set (time_type is ignored)
  @param type            type of datetime value
  @param max_length_arg  max length of datetime value as string

  @note
    If we value to be stored is not normalized, zero value will be stored
    instead and proper warning will be produced. This function relies on
    the fact that even wrong value sent over binary protocol fits into
    MAX_DATE_STRING_REP_LENGTH buffer.
*/
void Item_param::set_time(MYSQL_TIME *tm, timestamp_type time_type,
                          uint32 max_length_arg)
{ 
  DBUG_ENTER("Item_param::set_time");

  value.time= *tm;
  value.time.time_type= time_type;

  if (check_datetime_range(&value.time))
  {
    make_truncated_value_warning(ErrConvString(&value.time,
                                               MY_MIN(decimals,
                                                      DATETIME_MAX_DECIMALS)),
                                 time_type);
    set_zero_time(&value.time, MYSQL_TIMESTAMP_ERROR);
  }

  state= TIME_VALUE;
  maybe_null= 0;
  max_length= max_length_arg;
  decimals= 0;
  DBUG_VOID_RETURN;
}


bool Item_param::set_str(const char *str, ulong length)
{
  DBUG_ENTER("Item_param::set_str");
  /*
    Assign string with no conversion: data is converted only after it's
    been written to the binary log.
  */
  uint dummy_errors;
  if (str_value.copy(str, length, &my_charset_bin, &my_charset_bin,
                     &dummy_errors))
    DBUG_RETURN(TRUE);
  state= STRING_VALUE;
  max_length= length;
  maybe_null= 0;
  /* max_length and decimals are set after charset conversion */
  /* sic: str may be not null-terminated, don't add DBUG_PRINT here */
  DBUG_RETURN(FALSE);
}


bool Item_param::set_longdata(const char *str, ulong length)
{
  DBUG_ENTER("Item_param::set_longdata");

  /*
    If client character set is multibyte, end of long data packet
    may hit at the middle of a multibyte character.  Additionally,
    if binary log is open we must write long data value to the
    binary log in character set of client. This is why we can't
    convert long data to connection character set as it comes
    (here), and first have to concatenate all pieces together,
    write query to the binary log and only then perform conversion.
  */
  if (str_value.length() + length > current_thd->variables.max_allowed_packet)
  {
    my_message(ER_UNKNOWN_ERROR,
               "Parameter of prepared statement which is set through "
               "mysql_send_long_data() is longer than "
               "'max_allowed_packet' bytes",
               MYF(0));
    DBUG_RETURN(true);
  }

  if (str_value.append(str, length, &my_charset_bin))
    DBUG_RETURN(TRUE);
  state= LONG_DATA_VALUE;
  maybe_null= 0;

  DBUG_RETURN(FALSE);
}


/**
  Set parameter value from user variable value.

  @param thd   Current thread
  @param entry User variable structure (NULL means use NULL value)

  @retval
    0 OK
  @retval
    1 Out of memory
*/

bool Item_param::set_from_user_var(THD *thd, const user_var_entry *entry)
{
  DBUG_ENTER("Item_param::set_from_user_var");
  if (entry && entry->ptr())
  {
    item_result_type= entry->type();
    unsigned_flag= entry->unsigned_flag;
    if (limit_clause_param)
    {
      my_bool unused;
      set_int(entry->val_int(&unused), MY_INT64_NUM_DECIMAL_DIGITS);
      item_type= Item::INT_ITEM;
      DBUG_RETURN(!unsigned_flag && value.integer < 0 ? 1 : 0);
    }
    switch (item_result_type) {
    case REAL_RESULT:
      set_double(*(double*) entry->ptr());
      item_type= Item::REAL_ITEM;
      break;
    case INT_RESULT:
      set_int(*(longlong*) entry->ptr(), MY_INT64_NUM_DECIMAL_DIGITS);
      item_type= Item::INT_ITEM;
      break;
    case STRING_RESULT:
    {
      const CHARSET_INFO *fromcs= entry->collation.collation;
      const CHARSET_INFO *tocs= thd->variables.collation_connection;
      uint32 dummy_offset;

      value.cs_info.character_set_of_placeholder= fromcs;
      value.cs_info.character_set_client= thd->variables.character_set_client;
      /*
        Setup source and destination character sets so that they
        are different only if conversion is necessary: this will
        make later checks easier.
      */
      value.cs_info.final_character_set_of_str_value=
        String::needs_conversion(0, fromcs, tocs, &dummy_offset) ?
        tocs : fromcs;
      /*
        Exact value of max_length is not known unless data is converted to
        charset of connection, so we have to set it later.
      */
      item_type= Item::STRING_ITEM;

      if (set_str((const char *) entry->ptr(), entry->length()))
        DBUG_RETURN(1);
      break;
    }
    case DECIMAL_RESULT:
    {
      const my_decimal *ent_value= (const my_decimal *) entry->ptr();
      my_decimal2decimal(ent_value, &decimal_value);
      state= DECIMAL_VALUE;
      decimals= ent_value->frac;
      max_length=
        my_decimal_precision_to_length_no_truncation(ent_value->precision(),
                                                     decimals, unsigned_flag);
      item_type= Item::DECIMAL_ITEM;
      break;
    }
    default:
      DBUG_ASSERT(0);
      set_null();
    }
  }
  else
    set_null();

  DBUG_RETURN(0);
}

/**
  Resets parameter after execution.

  @note
    We clear null_value here instead of setting it in set_* methods,
    because we want more easily handle case for long data.
*/

void Item_param::reset()
{
  DBUG_ENTER("Item_param::reset");
  /* Shrink string buffer if it's bigger than max possible CHAR column */
  if (str_value.alloced_length() > MAX_CHAR_WIDTH)
    str_value.free();
  else
    str_value.length(0);
  str_value_ptr.length(0);
  /*
    We must prevent all charset conversions until data has been written
    to the binary log.
  */
  str_value.set_charset(&my_charset_bin);
  collation.set(&my_charset_bin, DERIVATION_COERCIBLE);
  state= NO_VALUE;
  maybe_null= 1;
  null_value= 0;
  /*
    Don't reset item_type to PARAM_ITEM: it's only needed to guard
    us from item optimizations at prepare stage, when item doesn't yet
    contain a literal of some kind.
    In all other cases when this object is accessed its value is
    set (this assumption is guarded by 'state' and
    DBUG_ASSERTS(state != NO_VALUE) in all Item_param::get_*
    methods).
  */
  DBUG_VOID_RETURN;
}


double Item_param::val_real()
{
  switch (state) {
  case REAL_VALUE:
    return value.real;
  case INT_VALUE:
    return (double) value.integer;
  case DECIMAL_VALUE:
  {
    double result;
    my_decimal2double(E_DEC_FATAL_ERROR, &decimal_value, &result);
    return result;
  }
  case STRING_VALUE:
  case LONG_DATA_VALUE:
  {
    int dummy_err;
    char *end_not_used;
    return my_strntod(str_value.charset(), (char*) str_value.ptr(),
                      str_value.length(), &end_not_used, &dummy_err);
  }
  case TIME_VALUE:
    /*
      This works for example when user says SELECT ?+0.0 and supplies
      time value for the placeholder.
    */
    return TIME_to_double(&value.time);
  case NULL_VALUE:
    return 0.0;
  default:
    DBUG_ASSERT(0);
  }
  return 0.0;
} 


longlong Item_param::val_int() 
{ 
  switch (state) {
  case REAL_VALUE:
    return (longlong) rint(value.real);
  case INT_VALUE:
    return value.integer;
  case DECIMAL_VALUE:
  {
    longlong i;
    my_decimal2int(E_DEC_FATAL_ERROR, &decimal_value, unsigned_flag, &i);
    return i;
  }
  case STRING_VALUE:
  case LONG_DATA_VALUE:
    {
      int dummy_err;
      return my_strntoll(str_value.charset(), str_value.ptr(),
                         str_value.length(), 10, (char**) 0, &dummy_err);
    }
  case TIME_VALUE:
    return (longlong) TIME_to_ulonglong_round(&value.time);
  case NULL_VALUE:
    return 0; 
  default:
    DBUG_ASSERT(0);
  }
  return 0;
}


my_decimal *Item_param::val_decimal(my_decimal *dec)
{
  switch (state) {
  case DECIMAL_VALUE:
    return &decimal_value;
  case REAL_VALUE:
    double2my_decimal(E_DEC_FATAL_ERROR, value.real, dec);
    return dec;
  case INT_VALUE:
    int2my_decimal(E_DEC_FATAL_ERROR, value.integer, unsigned_flag, dec);
    return dec;
  case STRING_VALUE:
  case LONG_DATA_VALUE:
    string2my_decimal(E_DEC_FATAL_ERROR, &str_value, dec);
    return dec;
  case TIME_VALUE:
    return date2my_decimal(&value.time, dec);
  case NULL_VALUE:
    return 0; 
  default:
    DBUG_ASSERT(0);
  }
  return 0;
}


String *Item_param::val_str(String* str) 
{ 
  switch (state) {
  case STRING_VALUE:
  case LONG_DATA_VALUE:
    return &str_value_ptr;
  case REAL_VALUE:
    str->set_real(value.real, NOT_FIXED_DEC, &my_charset_bin);
    return str;
  case INT_VALUE:
    str->set(value.integer, &my_charset_bin);
    return str;
  case DECIMAL_VALUE:
    if (my_decimal2string(E_DEC_FATAL_ERROR, &decimal_value,
                          0, 0, 0, str) <= 1)
      return str;
    return NULL;
  case TIME_VALUE:
  {
    if (str->reserve(MAX_DATE_STRING_REP_LENGTH))
      break;
    str->length((uint) my_TIME_to_str(&value.time, (char *) str->ptr(),
                                      MY_MIN(decimals, DATETIME_MAX_DECIMALS)));
    str->set_charset(&my_charset_bin);
    return str;
  }
  case NULL_VALUE:
    return NULL; 
  default:
    DBUG_ASSERT(0);
  }
  return str;
}


/**
  Transforms a string into "" or its expression in 0x... form.
*/

char *str_to_hex(char *to, const char *from, uint len)
{
    if (len)
    {
        *to++= '0';
        *to++= 'x';
        to= octet2hex(to, from, len);
    }
    else
        to= strmov(to, "\"\"");
    return to;                               // pointer to end 0 of 'to'
}


#ifndef MYSQL_CLIENT

/**
  Append a version of the 'from' string suitable for use in a query to
  the 'to' string.  To generate a correct escaping, the character set
  information in 'csinfo' is used.
*/

int
append_query_string(THD *thd, const CHARSET_INFO *csinfo,
                    String const *from, String *to)
{
    char *beg, *ptr;
    uint32 const orig_len= to->length();
    if (to->reserve(orig_len + from->length()*2+3))
        return 1;

    beg= to->c_ptr_quick() + to->length();
    ptr= beg;
    if (csinfo->escape_with_backslash_is_dangerous)
        ptr= str_to_hex(ptr, from->ptr(), from->length());
    else
    {
        *ptr++= '\'';
        if (!(thd->variables.sql_mode & MODE_NO_BACKSLASH_ESCAPES))
        {
            ptr+= escape_string_for_mysql(csinfo, ptr, 0,
                                          from->ptr(), from->length());
        }
        else
        {
            const char *frm_str= from->ptr();

            for (; frm_str < (from->ptr() + from->length()); frm_str++)
            {
                /* Using '' way to represent "'" */
                if (*frm_str == '\'')
                    *ptr++= *frm_str;

                *ptr++= *frm_str;
            }
        }

        *ptr++= '\'';
    }
    to->length(orig_len + ptr - beg);
    return 0;
}
#endif



/**
  Return Param item values in string format, for generating the dynamic 
  query used in update/binary logs.

  @todo
    - Change interface and implementation to fill log data in place
    and avoid one more memcpy/alloc between str and log string.
    - In case of error we need to notify replication
    that binary log contains wrong statement 
*/

const String *Item_param::query_val_str(THD *thd, String* str) const
{
  switch (state) {
  case INT_VALUE:
    str->set_int(value.integer, unsigned_flag, &my_charset_bin);
    break;
  case REAL_VALUE:
    str->set_real(value.real, NOT_FIXED_DEC, &my_charset_bin);
    break;
  case DECIMAL_VALUE:
    if (my_decimal2string(E_DEC_FATAL_ERROR, &decimal_value,
                          0, 0, 0, str) > 1)
      return &my_null_string;
    break;
  case TIME_VALUE:
    {
      char *buf, *ptr;
      str->length(0);
      /*
        TODO: in case of error we need to notify replication
        that binary log contains wrong statement 
      */
      if (str->reserve(MAX_DATE_STRING_REP_LENGTH+3))
        break; 

      /* Create date string inplace */
      buf= str->c_ptr_quick();
      ptr= buf;
      *ptr++= '\'';
      ptr+= (uint) my_TIME_to_str(&value.time, ptr,
                                  MY_MIN(decimals, DATETIME_MAX_DECIMALS));
      *ptr++= '\'';
      str->length((uint32) (ptr - buf));
      break;
    }
  case STRING_VALUE:
  case LONG_DATA_VALUE:
    {
      str->length(0);
      append_query_string(thd, value.cs_info.character_set_client, &str_value,
                          str);
      break;
    }
  case NULL_VALUE:
    return &my_null_string;
  default:
    DBUG_ASSERT(0);
  }
  return str;
}


/**
  Convert string from client character set to the character set of
  connection.
*/

bool Item_param::convert_str_value(THD *thd)
{
  bool rc= FALSE;
  if (state == STRING_VALUE || state == LONG_DATA_VALUE)
  {
    if (value.cs_info.final_character_set_of_str_value == NULL ||
        value.cs_info.character_set_of_placeholder == NULL)
      return true;
    /*
      Check is so simple because all charsets were set up properly
      in setup_one_conversion_function, where typecode of
      placeholder was also taken into account: the variables are different
      here only if conversion is really necessary.
    */
    if (value.cs_info.final_character_set_of_str_value !=
        value.cs_info.character_set_of_placeholder)
    {
      rc= thd->convert_string(&str_value,
                              value.cs_info.character_set_of_placeholder,
                              value.cs_info.final_character_set_of_str_value);
    }
    else
      str_value.set_charset(value.cs_info.final_character_set_of_str_value);
    /* Here str_value is guaranteed to be in final_character_set_of_str_value */

    max_length= str_value.numchars() * str_value.charset()->mbmaxlen;

    /* For the strings converted to numeric form within some functions */
    decimals= NOT_FIXED_DEC;
    /*
      str_value_ptr is returned from val_str(). It must be not alloced
      to prevent it's modification by val_str() invoker.
    */
    str_value_ptr.set(str_value.ptr(), str_value.length(),
                      str_value.charset());
    /* Synchronize item charset with value charset */
    collation.set(str_value.charset(), DERIVATION_COERCIBLE);
  }
  return rc;
}


bool Item_param::basic_const_item() const
{
  if (state == NO_VALUE || state == TIME_VALUE)
    return FALSE;
  return TRUE;
}

/* End of Item_param related */

void Item_param::print(String *str, enum_query_type query_type)
{
  if (state == NO_VALUE)
  {
    str->append('?');
  }
  else
  {
    char buffer[STRING_BUFFER_USUAL_SIZE];
    String tmp(buffer, sizeof(buffer), &my_charset_bin);
    const String *res;
    res= query_val_str(current_thd, &tmp);
    str->append(*res);
  }
}


/**
  Preserve the original parameter types and values
  when re-preparing a prepared statement.

  @details Copy parameter type information and conversion
  function pointers from a parameter of the old statement
  to the corresponding parameter of the new one.

  Move parameter values from the old parameters to the new
  one. We simply "exchange" the values, which allows
  to save on allocation and character set conversion in
  case a parameter is a string or a blob/clob.

  The old parameter gets the value of this one, which
  ensures that all memory of this parameter is freed
  correctly.

  @param[in]  src   parameter item of the original
                    prepared statement
*/

void
Item_param::set_param_type_and_swap_value(Item_param *src)
{
  unsigned_flag= src->unsigned_flag;
  param_type= src->param_type;
  set_param_func= src->set_param_func;
  item_type= src->item_type;
  item_result_type= src->item_result_type;

  collation.set(src->collation);
  maybe_null= src->maybe_null;
  null_value= src->null_value;
  max_length= src->max_length;
  decimals= src->decimals;
  state= src->state;
  value= src->value;

  decimal_value.swap(src->decimal_value);
  str_value.swap(src->str_value);
  str_value_ptr.swap(src->str_value_ptr);
}


enum_field_types Item::string_field_type() const
{
  enum_field_types f_type= MYSQL_TYPE_VAR_STRING;
  if (max_length >= 16777216)
    f_type= MYSQL_TYPE_LONG_BLOB;
  else if (max_length >= 65536)
    f_type= MYSQL_TYPE_MEDIUM_BLOB;
  return f_type;
}

enum_field_types Item::field_type() const
{
  switch (result_type()) {
  case STRING_RESULT:  return string_field_type();
  case INT_RESULT:     return MYSQL_TYPE_LONGLONG;
  case DECIMAL_RESULT: return MYSQL_TYPE_NEWDECIMAL;
  case REAL_RESULT:    return MYSQL_TYPE_DOUBLE;
  case ROW_RESULT:
  default:
    DBUG_ASSERT(0);
    return MYSQL_TYPE_VARCHAR;
  }
}


/**
  Verifies that the input string is well-formed according to its character set.
  @param send_error   If true, call my_error if string is not well-formed.

  Will truncate input string if it is not well-formed.

  @return
  If well-formed: input string.
  If not well-formed:
    if strict mode: NULL pointer and we set this Item's value to NULL
    if not strict mode: input string truncated up to last good character
 */
String *Item::check_well_formed_result(String *str, bool send_error)
{
  /* Check whether we got a well-formed string */
  const CHARSET_INFO *cs= str->charset();
  int well_formed_error;
  uint wlen= cs->cset->well_formed_len(cs,
                                       str->ptr(), str->ptr() + str->length(),
                                       str->length(), &well_formed_error);
  if (wlen < str->length())
  {
    THD *thd= current_thd;
    char hexbuf[7];
    uint diff= str->length() - wlen;
    set_if_smaller(diff, 3);
    octet2hex(hexbuf, str->ptr() + wlen, diff);
    if (send_error)
    {
      my_error(ER_INVALID_CHARACTER_STRING, MYF(0),
               cs->csname,  hexbuf);
      return 0;
    }
    if (thd->is_strict_mode())
    {
      null_value= 1;
      str= 0;
    }
    else
    {
      str->length(wlen);
    }
    push_warning_printf(thd, Sql_condition::WARN_LEVEL_WARN, ER_INVALID_CHARACTER_STRING,
                        ER(ER_INVALID_CHARACTER_STRING), cs->csname, hexbuf);
  }
  return str;
}

/**
  Check if it is OK to evaluate the item now.

  @return true if the item can be evaluated in the current statement state.
    @retval true  The item can be evaluated now.
    @retval false The item can not be evaluated now,
                  (i.e. depend on non locked table).

  @note Help function to avoid optimize or exec call during prepare phase.
*/

bool Item::can_be_evaluated_now() const
{
  DBUG_ENTER("Item::can_be_evaluated_now");

  if (tables_locked_cache)
    DBUG_RETURN(true);

  if (has_subquery() || has_stored_program())
    const_cast<Item*>(this)->tables_locked_cache=
                               current_thd->lex->is_query_tables_locked();
  else
    const_cast<Item*>(this)->tables_locked_cache= true;

  DBUG_RETURN(tables_locked_cache);
}

Item_num *Item_uint::neg()
{
  Item_decimal *item= new Item_decimal(value, 1);
  return item->neg();
}


static uint nr_of_decimals(const char *str, const char *end)
{
  const char *decimal_point;

  /* Find position for '.' */
  for (;;)
  {
    if (str == end)
      return 0;
    if (*str == 'e' || *str == 'E')
      return NOT_FIXED_DEC;    
    if (*str++ == '.')
      break;
  }
  decimal_point= str;
  for ( ; str < end && my_isdigit(system_charset_info, *str) ; str++)
    ;
  if (str < end && (*str == 'e' || *str == 'E'))
    return NOT_FIXED_DEC;
  /*
    QQ:
    The number of decimal digist in fact should be (str - decimal_point - 1).
    But it seems the result of nr_of_decimals() is never used!

    In case of 'e' and 'E' nr_of_decimals returns NOT_FIXED_DEC.
    In case if there is no 'e' or 'E' parser code in sql_yacc.yy
    never calls Item_float::Item_float() - it creates Item_decimal instead.

    The only piece of code where we call Item_float::Item_float(str, len)
    without having 'e' or 'E' is item_xmlfunc.cc, but this Item_float
    never appears in metadata itself. Changing the code to return
    (str - decimal_point - 1) does not make any changes in the test results.

    This should be addressed somehow.
    Looks like a reminder from before real DECIMAL times.
  */
  return (uint) (str - decimal_point);
}


/**
  This function is only called during parsing:
  - when parsing SQL query from sql_yacc.yy
  - when parsing XPath query from item_xmlfunc.cc
  We will signal an error if value is not a true double value (overflow):
  eng: Illegal %s '%-.192s' value found during parsing

  Note: str_arg does not necessarily have to be a null terminated string,
  e.g. it is NOT when called from item_xmlfunc.cc or sql_yacc.yy.
*/

Item_float::Item_float(const char *str_arg, uint length)
{
  int error;
  char *end_not_used;
  value= my_strntod(&my_charset_bin, (char*) str_arg, length, &end_not_used,
                    &error);
  if (error)
  {
    char tmp[NAME_LEN + 1];
    my_snprintf(tmp, sizeof(tmp), "%.*s", length, str_arg);
    my_error(ER_ILLEGAL_VALUE_FOR_TYPE, MYF(0), "double", tmp);
  }
  presentation.copy(str_arg, length);
  item_name.copy(str_arg, length);
  decimals=(uint8) nr_of_decimals(str_arg, str_arg+length);
  max_length=length;
  fixed= 1;
}

void Item_float::print(String *str, enum_query_type query_type)
{
  if (presentation.ptr())
  {
    str->append(presentation.ptr());
    return;
  }
  char buffer[20];
  String num(buffer, sizeof(buffer), &my_charset_bin);
  num.set_real(value, decimals, &my_charset_bin);
  str->append(num);
}

inline uint char_val(char X)
{
  return (uint) (X >= '0' && X <= '9' ? X-'0' :
		 X >= 'A' && X <= 'Z' ? X-'A'+10 :
		 X-'a'+10);
}

Item_hex_string::Item_hex_string()
{
  hex_string_init("", 0);
}

Item_hex_string::Item_hex_string(const char *str, uint str_length)
{
  hex_string_init(str, str_length);
}

void Item_hex_string::hex_string_init(const char *str, uint str_length)
{
  max_length=(str_length+1)/2;
  char *ptr=(char*) sql_alloc(max_length+1);
  if (!ptr)
  {
    str_value.set("", 0, &my_charset_bin);
    return;
  }
  str_value.set(ptr,max_length,&my_charset_bin);
  char *end=ptr+max_length;
  if (max_length*2 != str_length)
    *ptr++=char_val(*str++);			// Not even, assume 0 prefix
  while (ptr != end)
  {
    *ptr++= (char) (char_val(str[0])*16+char_val(str[1]));
    str+=2;
  }
  *ptr=0;					// Keep purify happy
  collation.set(&my_charset_bin, DERIVATION_COERCIBLE);
  fixed= 1;
  unsigned_flag= 1;
}

longlong Item_hex_string::val_int()
{
  // following assert is redundant, because fixed=1 assigned in constructor
  DBUG_ASSERT(fixed == 1);
  char *end=(char*) str_value.ptr()+str_value.length(),
       *ptr= end - min<size_t>(str_value.length(), sizeof(longlong));

  ulonglong value=0;
  for (; ptr != end ; ptr++)
    value=(value << 8)+ (ulonglong) (uchar) *ptr;
  return (longlong) value;
}


my_decimal *Item_hex_string::val_decimal(my_decimal *decimal_value)
{
  // following assert is redundant, because fixed=1 assigned in constructor
  DBUG_ASSERT(fixed == 1);
  ulonglong value= (ulonglong)val_int();
  int2my_decimal(E_DEC_FATAL_ERROR, value, TRUE, decimal_value);
  return (decimal_value);
}




void Item_hex_string::print(String *str, enum_query_type query_type)
{
  char *end= (char*) str_value.ptr() + str_value.length(),
       *ptr= end - min<size_t>(str_value.length(), sizeof(longlong));
  str->append("0x");
  for (; ptr != end ; ptr++)
  {
    str->append(_dig_vec_lower[((uchar) *ptr) >> 4]);
    str->append(_dig_vec_lower[((uchar) *ptr) & 0x0F]);
  }
}

/*
  bin item.
  In string context this is a binary string.
  In number context this is a longlong value.
*/
  
Item_bin_string::Item_bin_string(const char *str, uint str_length)
{
  const char *end= str + str_length - 1;
  uchar bits= 0;
  uint power= 1;

  max_length= (str_length + 7) >> 3;
  char *ptr= (char*) sql_alloc(max_length + 1);
  if (!ptr)
    return;
  str_value.set(ptr, max_length, &my_charset_bin);

  if (max_length > 0)
  {
    ptr+= max_length - 1;
    ptr[1]= 0;                     // Set end null for string
    for (; end >= str; end--)
    {
      if (power == 256)
      {
        power= 1;
        *ptr--= bits;
        bits= 0;
      }
      if (*end == '1')
        bits|= power;
      power<<= 1;
    }
    *ptr= (char) bits;
  }
  else
    ptr[0]= 0;

  collation.set(&my_charset_bin, DERIVATION_COERCIBLE);
  fixed= 1;
}


void Item_field::print(String *str, enum_query_type query_type)
{
  Item_ident::print(str, query_type);
}

Item_ref::Item_ref(Name_resolution_context *context_arg,
                   Item **item, const char *table_name_arg,
                   const char *field_name_arg,
                   bool alias_name_used_arg)
  :Item_ident(context_arg, NullS, table_name_arg, field_name_arg),
  ref(item)
{
  alias_name_used= alias_name_used_arg;
  /*
    This constructor used to create some internals references over fixed items
  */
  if (ref && *ref && (*ref)->fixed)
    set_properties();
}



void Item_ref::set_properties()
{
  max_length= (*ref)->max_length;
  maybe_null= (*ref)->maybe_null;
  decimals=   (*ref)->decimals;
  collation.set((*ref)->collation);
  /*
    We have to remember if we refer to a sum function, to ensure that
    split_sum_func() doesn't try to change the reference.
  */
  with_sum_func= (*ref)->with_sum_func;
  unsigned_flag= (*ref)->unsigned_flag;
  fixed= 1;
  if (alias_name_used)
    return;
  if ((*ref)->type() == FIELD_ITEM)
    alias_name_used= ((Item_ident *) (*ref))->alias_name_used;
  else
    alias_name_used= TRUE; // it is not field, so it is was resolved by alias
}

void Item_ref::print(String *str, enum_query_type query_type)
{
  if (ref)
  {
    if ((*ref)->type() != Item::CACHE_ITEM && ref_type() != VIEW_REF &&
        !table_name && item_name.ptr() && alias_name_used)
    {
      THD *thd= current_thd;
      append_identifier(thd, str, (*ref)->real_item()->item_name);
    }
    else
      (*ref)->print(str, query_type);
  }
  else
    Item_ident::print(str, query_type);
}



double Item_ref::val_real()
{
  return 0.0;
}


longlong Item_ref::val_int()
{
  return 0;
}


bool Item_ref::val_bool()
{
  return false;
}


String *Item_ref::val_str(String* tmp)
{
  return NULL;
}




bool Item_ref::is_null()
{
  return true;
}

my_decimal *Item_ref::val_decimal(my_decimal *decimal_value)
{
  return NULL;
}

void Item_default_value::print(String *str, enum_query_type query_type)
{
  if (!arg)
  {
    str->append(STRING_WITH_LEN("default"));
    return;
  }
  str->append(STRING_WITH_LEN("default("));
  arg->print(str, query_type);
  str->append(')');
}


void Item_insert_value::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("values("));
  arg->print(str, query_type);
  str->append(')');
}


void Item_trigger_field::print(String *str, enum_query_type query_type)
{
  str->append((row_version == NEW_ROW) ? "NEW" : "OLD", 3);
  str->append('.');
  str->append(field_name);
}

Item_result item_cmp_type(Item_result a,Item_result b)
{
  if (a == STRING_RESULT && b == STRING_RESULT)
    return STRING_RESULT;
  if (a == INT_RESULT && b == INT_RESULT)
    return INT_RESULT;
  else if (a == ROW_RESULT || b == ROW_RESULT)
    return ROW_RESULT;
  if ((a == INT_RESULT || a == DECIMAL_RESULT) &&
      (b == INT_RESULT || b == DECIMAL_RESULT))
    return DECIMAL_RESULT;
  return REAL_RESULT;
}


/**
  Dummy error processor used by default by Name_resolution_context.

  @note
    do nothing
*/

void dummy_error_processor(THD *thd, void *data)
{}

/**
  Wrapper of hide_view_error call for Name_resolution_context error
  processor.

  @note
    hide view underlying tables details in error messages
*/

void view_error_processor(THD *thd, void *data)
{
  ((TABLE_LIST *)data)->hide_view_error(thd);
}
