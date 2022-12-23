#ifndef ITEM_TIMEFUNC_INCLUDED
#define ITEM_TIMEFUNC_INCLUDED

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


/* Function items used by mysql */

#include <algorithm>

class MY_LOCALE;

class Item_func_period_add :public Item_int_func
{
public:
  Item_func_period_add(Item *a,Item *b) :Item_int_func(a,b) {}
  longlong val_int();
  const char *func_name() const { return "period_add"; }
};


class Item_func_period_diff :public Item_int_func
{
public:
  Item_func_period_diff(Item *a,Item *b) :Item_int_func(a,b) {}
  longlong val_int();
  const char *func_name() const { return "period_diff"; }

};


class Item_func_to_days :public Item_int_func
{
public:
  Item_func_to_days(Item *a) :Item_int_func(a) {}
  longlong val_int();
  const char *func_name() const { return "to_days"; }

  enum_monotonicity_info get_monotonicity_info() const;
  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_date_args();
  }
};


class Item_func_to_seconds :public Item_int_func
{
public:
  Item_func_to_seconds(Item *a) :Item_int_func(a) {}
  longlong val_int();
  const char *func_name() const { return "to_seconds"; }

  enum_monotonicity_info get_monotonicity_info() const;
  bool check_partition_func_processor(uchar *bool_arg) { return FALSE;}

  bool intro_version(uchar *int_arg)
  {
    using std::max;
    int *input_version= (int*)int_arg;
    /* This function was introduced in 5.5 */
    int output_version= max(*input_version, 50500);
    *input_version= output_version;
    return 0;
  }

  /* Only meaningful with date part and optional time part */
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_date_args();
  }
};


class Item_func_dayofmonth :public Item_int_func
{
public:
  Item_func_dayofmonth(Item *a) :Item_int_func(a) {}
  longlong val_int();
  const char *func_name() const { return "dayofmonth"; }

  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_date_args();
  }
};


/**
  TS-TODO: This should probably have Item_int_func as parent class.
*/
class Item_func_month :public Item_func
{
public:
  Item_func_month(Item *a) :Item_func(a) { collation.set_numeric(); }
  longlong val_int();
  double val_real()
  { DBUG_ASSERT(fixed == 1); return (double) Item_func_month::val_int(); }
  String *val_str(String *str) 
  {
    longlong nr= val_int();
    if (null_value)
      return 0;
    str->set(nr, collation.collation);
    return str;
  }
  const char *func_name() const { return "month"; }
  enum Item_result result_type () const { return INT_RESULT; }

  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_date_args();
  }
};


class Item_func_monthname :public Item_str_func
{
  MY_LOCALE *locale;
public:
  Item_func_monthname(Item *a) :Item_str_func(a) {}
  const char *func_name() const { return "monthname"; }
  String *val_str(String *str);

  bool check_partition_func_processor(uchar *int_arg) {return TRUE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_date_args();
  }
};


class Item_func_dayofyear :public Item_int_func
{
public:
  Item_func_dayofyear(Item *a) :Item_int_func(a) {}
  longlong val_int();
  const char *func_name() const { return "dayofyear"; }

  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_date_args();
  }
};


class Item_func_hour :public Item_int_func
{
public:
  Item_func_hour(Item *a) :Item_int_func(a) {}
  longlong val_int();
  const char *func_name() const { return "hour"; }

  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_time_args();
  }
};


class Item_func_minute :public Item_int_func
{
public:
  Item_func_minute(Item *a) :Item_int_func(a) {}
  longlong val_int();
  const char *func_name() const { return "minute"; }

  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_time_args();
  }
};


class Item_func_quarter :public Item_int_func
{
public:
  Item_func_quarter(Item *a) :Item_int_func(a) {}
  longlong val_int();
  const char *func_name() const { return "quarter"; }

  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_date_args();
  }
};


class Item_func_second :public Item_int_func
{
public:
  Item_func_second(Item *a) :Item_int_func(a) {}
  longlong val_int();
  const char *func_name() const { return "second"; }

  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_time_args();
  }
};


class Item_func_week :public Item_int_func
{
public:
  Item_func_week(Item *a,Item *b) :Item_int_func(a,b) {}
  longlong val_int();
  const char *func_name() const { return "week"; }
};

class Item_func_yearweek :public Item_int_func
{
public:
  Item_func_yearweek(Item *a,Item *b) :Item_int_func(a,b) {}
  longlong val_int();
  const char *func_name() const { return "yearweek"; }

  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_date_args();
  }
};


class Item_func_year :public Item_int_func
{
public:
  Item_func_year(Item *a) :Item_int_func(a) {}
  longlong val_int();
  const char *func_name() const { return "year"; }
  enum_monotonicity_info get_monotonicity_info() const;

  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_date_args();
  }
};


/**
  TS-TODO: This should probably have Item_int_func as parent class.
*/
class Item_func_weekday :public Item_func
{
  bool odbc_type;
public:
  Item_func_weekday(Item *a,bool type_arg)
    :Item_func(a), odbc_type(type_arg) { collation.set_numeric(); }
  longlong val_int();
  double val_real() { DBUG_ASSERT(fixed == 1); return (double) val_int(); }
  String *val_str(String *str)
  {
    DBUG_ASSERT(fixed == 1);
    str->set(val_int(), &my_charset_bin);
    return null_value ? 0 : str;
  }
  const char *func_name() const
  {
     return (odbc_type ? "dayofweek" : "weekday");
  }
  enum Item_result result_type () const { return INT_RESULT; }

  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_date_args();
  }
};

/**
  TS-TODO: Item_func_dayname should be derived from Item_str_func.
  In the current implementation funny things can happen:
  select dayname(now())+1 -> 4
*/
class Item_func_dayname :public Item_func_weekday
{
  MY_LOCALE *locale;
 public:
  Item_func_dayname(Item *a) :Item_func_weekday(a,0) {}
  const char *func_name() const { return "dayname"; }
  String *val_str(String *str);
  enum Item_result result_type () const { return STRING_RESULT; }
  bool check_partition_func_processor(uchar *int_arg) {return TRUE;}
};


/*
  Abstract class for functions returning "struct timeval".
*/
class Item_timeval_func :public Item_func
{
public:
  Item_timeval_func() :Item_func() { }
  Item_timeval_func(Item *a) :Item_func(a) { }
  /**
    Return timestamp in "struct timeval" format.
    @param OUT tm The value is store here.
    @retval false On success
    @retval true  On error
  */
  virtual bool val_timeval(struct timeval *tm)= 0;
  longlong val_int() {return 0;}
  double val_real() {return 0.0;}
  String *val_str(String *str) {return NULL;}
  my_decimal *val_decimal(my_decimal *decimal_value) {return NULL;}
  enum Item_result result_type() const
  {
    return decimals ? DECIMAL_RESULT : INT_RESULT;
  }
};


class Item_func_unix_timestamp :public Item_timeval_func
{
public:
  Item_func_unix_timestamp() :Item_timeval_func() {}
  Item_func_unix_timestamp(Item *a) :Item_timeval_func(a) {}
  const char *func_name() const { return "unix_timestamp"; }
  enum_monotonicity_info get_monotonicity_info() const;
  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  /*
    UNIX_TIMESTAMP() depends on the current timezone
    (and thus may not be used as a partitioning function)
    when its argument is NOT of the TIMESTAMP type.
  */
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_timestamp_args();
  }
  bool val_timeval(struct timeval *tm) {return false;}
};


class Item_func_time_to_sec :public Item_int_func
{
public:
  Item_func_time_to_sec(Item *item) :Item_int_func(item) {}
  longlong val_int() {return 0;}
  const char *func_name() const { return "time_to_sec"; }
  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_time_args();
  }
};


/**
  Abstract class for functions returning TIME, DATE, DATETIME types
  whose data type is known at constructor time.
*/
class Item_temporal_func :public Item_func
{
protected:
  bool check_precision();
public:
  Item_temporal_func() :Item_func() {}
  Item_temporal_func(Item *a) :Item_func(a) {}
  Item_temporal_func(Item *a, Item *b) :Item_func(a, b) {}
  Item_temporal_func(Item *a, Item *b, Item *c) :Item_func(a, b, c) {}
  enum Item_result result_type () const
  {
    return STRING_RESULT;
  }
  CHARSET_INFO *charset_for_protocol() const
  {
    return &my_charset_bin;
  }
  uint time_precision()
  {
    DBUG_ASSERT(fixed);
    return decimals;
  }
};


/**
  Abstract class for functions returning TIME, DATE, DATETIME or string values,
  whose data type depends on parameters and is set at fix_field time.
*/
class Item_temporal_hybrid_func :public Item_str_func
{
protected:
  enum_field_types cached_field_type; // TIME, DATE, DATETIME or STRING
  String ascii_buf; // Conversion buffer

public:
  Item_temporal_hybrid_func(Item *a, Item *b) :Item_str_func(a, b)
  { }
  enum Item_result result_type () const { return STRING_RESULT; }
  enum_field_types field_type() const { return cached_field_type; }
  const CHARSET_INFO *charset_for_protocol() const
  {
    /*
      Can return TIME, DATE, DATETIME or VARCHAR depending on arguments.
      Send using "binary" when TIME, DATE or DATETIME,
      or using collation.collation when VARCHAR
      (which is fixed from @collation_connection in fix_length_and_dec).
    */
    DBUG_ASSERT(fixed == 1);
    return cached_field_type == MYSQL_TYPE_STRING ?
                                collation.collation : &my_charset_bin;
  }

  longlong val_int() { return 0; }
  double val_real() { return 0.0; }
  my_decimal *val_decimal(my_decimal *decimal_value) { return NULL; }

  /**
  Return string value in ASCII character set.
*/
  String *val_str_ascii(String *str)
  {
    return NULL;
  }
  /**
    Return string value in @@character_set_connection.
  */
  String *val_str(String *str)
  {
    return NULL;
  }
};


/*
  This can't be a Item_str_func, because the val_real() functions are special
*/

/**
  Abstract class for functions returning DATE values.
*/
class Item_date_func :public Item_temporal_func
{
public:
  Item_date_func() :Item_temporal_func()
  { }
  Item_date_func(Item *a) :Item_temporal_func(a)
  { }
  Item_date_func(Item *a, Item *b) :Item_temporal_func(a, b)
  { }
  enum_field_types field_type() const { return MYSQL_TYPE_DATE; }
  String *val_str(String *str)
  {
    return NULL;
  }
  longlong val_int()
  {  
    return 0;
  }
  double val_real() { return (double) val_int(); }
  const char *func_name() const { return "date"; }
  my_decimal *val_decimal(my_decimal *decimal_value)
  {
    return 0;
  }
};


/**
  Abstract class for functions returning DATETIME values.
*/
class Item_datetime_func :public Item_temporal_func
{
public:
  Item_datetime_func() :Item_temporal_func()
  { }
  Item_datetime_func(Item *a) :Item_temporal_func(a)
  { }
  Item_datetime_func(Item *a,Item *b) :Item_temporal_func(a,b)
  { }
  Item_datetime_func(Item *a,Item *b, Item *c) :Item_temporal_func(a,b,c)
  { }
  enum_field_types field_type() const { return MYSQL_TYPE_DATETIME; }
  double val_real() { return 0.0; }
  String *val_str(String *str)
  {
    return NULL;
  }
  longlong val_int()
  {
    return 0;
  }
  my_decimal *val_decimal(my_decimal *decimal_value)
  {
    return  NULL;
  }
};


/**
  Abstract class for functions returning TIME values.
*/
class Item_time_func :public Item_temporal_func
{
public:
  Item_time_func() :Item_temporal_func() {}
  Item_time_func(Item *a) :Item_temporal_func(a) {}
  Item_time_func(Item *a,Item *b) :Item_temporal_func(a,b) {}
  Item_time_func(Item *a, Item *b, Item *c) :Item_temporal_func(a, b ,c) {}
  enum_field_types field_type() const { return MYSQL_TYPE_TIME; }

  double val_real() { return 0; }
  my_decimal *val_decimal(my_decimal *decimal_value)
  {
    return NULL;
  }
  longlong val_int()
  {
    return NULL;
  }
  String *val_str(String *str)
  {
    return NULL;
  }
};


/**
  Cache for MYSQL_TIME value with various representations.

  - MYSQL_TIME representation (time) is initialized during set_XXX().
  - Packed representation (time_packed) is also initialized during set_XXX().
  - String representation (string_buff) is not initialized during set_XXX();
    it's initialized only if val_str() or cptr() are called.
*/
class MYSQL_TIME_cache
{
  MYSQL_TIME time;                              ///< MYSQL_TIME representation
  longlong time_packed;                         ///< packed representation
  char string_buff[MAX_DATE_STRING_REP_LENGTH]; ///< string representation
  uint string_length;                           ///< length of string
  uint8 dec;                                    ///< Number of decimals
  /**
    Cache string representation from the cached MYSQL_TIME representation.
    If string representation has already been cached, then nothing happens.
  */
  void cache_string();
  /**
    Reset string representation.
  */
  void reset_string()
  {
    string_length= 0;
    string_buff[0]= '\0';
  }
  /**
    Reset all members.
  */
  void reset()
  {
    time.time_type= MYSQL_TIMESTAMP_NONE;
    time_packed= 0;
    reset_string();
    dec= 0;
  }
  /**
    Store MYSQL_TIME representation into the given MYSQL_TIME variable.
  */
  void get_TIME(MYSQL_TIME *ltime) const
  {
    DBUG_ASSERT(time.time_type != MYSQL_TIMESTAMP_NONE);
    *ltime= time;
  }
public:

  MYSQL_TIME_cache()
  {
    reset();
  }
  /**
    Set time and time_packed from a DATE value.
  */
  void set_date(MYSQL_TIME *ltime);
  /**
    Set time and time_packed from a TIME value.
  */
  void set_time(MYSQL_TIME *ltime, uint8 dec_arg);
  /**
    Set time and time_packed from a DATETIME value.
  */
  void set_datetime(MYSQL_TIME *ltime, uint8 dec_arg);
  /**
    Return number of decimal digits.
  */
  uint8 decimals() const
  {
    DBUG_ASSERT(time.time_type != MYSQL_TIMESTAMP_NONE);
    return dec;
  }

  /**
    Return packed representation.
  */
  longlong val_packed() const
  {
    DBUG_ASSERT(time.time_type != MYSQL_TIMESTAMP_NONE);
    return time_packed;
  }
  /**
  Store MYSQL_TIME representation into the given date/datetime variable
  checking date flags.
*/
  bool get_date(MYSQL_TIME *ltime, uint fuzzyflags) const;
  /**
    Store MYSQL_TIME representation into the given time variable.
  */
  bool get_time(MYSQL_TIME *ltime) const
  {
    get_TIME(ltime);
    return false;
  }
  /**
    Return pointer to MYSQL_TIME representation.
  */
  MYSQL_TIME *get_TIME_ptr()
  {
    DBUG_ASSERT(time.time_type != MYSQL_TIMESTAMP_NONE);
    return &time;
  }
  /**
    Store string representation into String.
  */
  String *val_str(String *str);
  /**
    Return C string representation.
  */
  const char *cptr();
};


/**
  DATE'2010-01-01'
*/
class Item_date_literal :public Item_date_func
{
  MYSQL_TIME_cache cached_time;
public:
  /**
    Constructor for Item_date_literal.
    @param ltime  DATE value.
  */
  Item_date_literal(MYSQL_TIME *ltime) :Item_date_func()
  {
    cached_time.set_date(ltime);
    fixed= 1;
  }
  const char *func_name() const { return "date_literal"; }
  void print(String *str, enum_query_type query_type);
  bool check_partition_func_processor(uchar *int_arg)
  {
    return FALSE;
  }
  bool basic_const_item() const { return true; }
  bool const_item() const { return true; }
  table_map used_tables() const { return (table_map) 0L; }
  table_map not_null_tables() const { return used_tables(); }
};


/**
  TIME'10:10:10'
*/
class Item_time_literal :public Item_time_func
{
  MYSQL_TIME_cache cached_time;
public:
  /**
    Constructor for Item_time_literal.
    @param ltime    TIME value.
    @param dec_arg  number of fractional digits in ltime.
  */
  Item_time_literal(MYSQL_TIME *ltime, uint dec_arg) :Item_time_func()
  {
    decimals= MY_MIN(dec_arg, DATETIME_MAX_DECIMALS);
    cached_time.set_time(ltime, decimals);
  }
  const char *func_name() const { return "time_literal"; }
  void print(String *str, enum_query_type query_type);
  String *val_str(String *str)
  {
    DBUG_ASSERT(fixed);
    return cached_time.val_str(str);
  }
  bool check_partition_func_processor(uchar *int_arg)
  {
    return FALSE;
  }
  bool basic_const_item() const { return true; }
  bool const_item() const { return true; }
  table_map used_tables() const { return (table_map) 0L; }
  table_map not_null_tables() const { return used_tables(); }
};


/**
  TIMESTAMP'2001-01-01 10:20:30'
*/
class Item_datetime_literal :public Item_datetime_func
{
  MYSQL_TIME_cache cached_time;
public:
  /**
    Constructor for Item_datetime_literal.
    @param ltime    DATETIME value.
    @param dec_arg  number of fractional digits in ltime.
  */
  Item_datetime_literal(MYSQL_TIME *ltime, uint dec_arg) :Item_datetime_func()
  {
    decimals= MY_MIN(dec_arg, DATETIME_MAX_DECIMALS);
    cached_time.set_datetime(ltime, decimals);
    fix_length_and_dec();
    fixed= 1;
  }
  const char *func_name() const { return "datetime_literal"; }
  void print(String *str, enum_query_type query_type);
  String *val_str(String *str)
  {
    DBUG_ASSERT(fixed);
    return cached_time.val_str(str);
  }
  void fix_length_and_dec()
  {
    fix_length_and_dec_and_charset_datetime(MAX_DATETIME_WIDTH, decimals);
  }
  bool check_partition_func_processor(uchar *int_arg)
  {
    return FALSE;
  }
  bool basic_const_item() const { return true; }
  bool const_item() const { return true; }
  table_map used_tables() const { return (table_map) 0L; }
  table_map not_null_tables() const { return used_tables(); }
};


/* Abstract CURTIME function. Children should define what time zone is used */

class Item_func_curtime :public Item_time_func
{
  MYSQL_TIME_cache cached_time; // Initialized in fix_length_and_dec
public:
  /**
    Constructor for Item_func_curtime.
    @param dec_arg  Number of fractional digits.
  */
  Item_func_curtime(uint8 dec_arg) :Item_time_func() { decimals= dec_arg; }
//  String *val_str(String *str)
//  {
//    return NULL;
// }
};


class Item_func_curtime_local :public Item_func_curtime
{
public:
  Item_func_curtime_local(uint8 dec_arg) :Item_func_curtime(dec_arg) {}
  const char *func_name() const { return "curtime"; }
};


class Item_func_curtime_utc :public Item_func_curtime
{
public:
  Item_func_curtime_utc(uint8 dec_arg) :Item_func_curtime(dec_arg) {}
  const char *func_name() const { return "utc_time"; }
};


/* Abstract CURDATE function. See also Item_func_curtime. */

class Item_func_curdate :public Item_date_func
{
  MYSQL_TIME_cache cached_time; // Initialized in fix_length_and_dec
public:
  Item_func_curdate() :Item_date_func() {}

  String *val_str(String *str)
  {
    DBUG_ASSERT(fixed == 1);
    return cached_time.val_str(&str_value);
  }
};


class Item_func_curdate_local :public Item_func_curdate
{
public:
  Item_func_curdate_local() :Item_func_curdate() {}
  const char *func_name() const { return "curdate"; }
};


class Item_func_curdate_utc :public Item_func_curdate
{
public:
  Item_func_curdate_utc() :Item_func_curdate() {}
  const char *func_name() const { return "utc_date"; }
};


/* Abstract CURRENT_TIMESTAMP function. See also Item_func_curtime */

class Item_func_now :public Item_datetime_func {
  MYSQL_TIME_cache cached_time;

public:
  /**
    Constructor for Item_func_now.
    @param dec_arg  Number of fractional digits.
  */
  Item_func_now(uint8 dec_arg) : Item_datetime_func() { decimals = dec_arg; }
};


class Item_func_now_local :public Item_func_now
{
public:

  Item_func_now_local(uint8 dec_arg) :Item_func_now(dec_arg) {}
  const char *func_name() const { return "now"; }
  virtual enum Functype functype() const { return NOW_FUNC; }
};


class Item_func_now_utc :public Item_func_now
{
public:
  Item_func_now_utc(uint8 dec_arg) :Item_func_now(dec_arg) {}
  const char *func_name() const { return "utc_timestamp"; }
};


/*
  This is like NOW(), but always uses the real current time, not the
  query_start(). This matches the Oracle behavior.
*/
class Item_func_sysdate_local :public Item_datetime_func
{
public:
  Item_func_sysdate_local(uint8 dec_arg) :
    Item_datetime_func() { decimals= dec_arg; }
  bool const_item() const { return 0; }
  const char *func_name() const { return "sysdate"; }
  /**
    This function is non-deterministic and hence depends on the 'RAND' pseudo-table.

    @retval Always RAND_TABLE_BIT
  */
  table_map get_initial_pseudo_tables() const { return RAND_TABLE_BIT; }
};


class Item_func_from_days :public Item_date_func
{
public:
  Item_func_from_days(Item *a) :Item_date_func(a) {}
  const char *func_name() const { return "from_days"; }
  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return has_date_args() || has_time_args();
  }
};


class Item_func_date_format :public Item_str_func
{
  int fixed_length;
  const bool is_time_format;
  String value;
public:
  Item_func_date_format(Item *a,Item *b,bool is_time_format_arg)
    :Item_str_func(a,b),is_time_format(is_time_format_arg) {}
  String *val_str(String *str) {return 0;}
  const char *func_name() const
    { return is_time_format ? "time_format" : "date_format"; }
};


class Item_func_from_unixtime :public Item_datetime_func
{
  THD *thd;
 public:
  Item_func_from_unixtime(Item *a) :Item_datetime_func(a) {}
  const char *func_name() const { return "from_unixtime"; }
};


/* 
  We need Time_zone class declaration for storing pointers in
  Item_func_convert_tz.
*/
class Time_zone;

/*
  This class represents CONVERT_TZ() function.
  The important fact about this function that it is handled in special way.
  When such function is met in expression time_zone system tables are added
  to global list of tables to open, so later those already opened and locked
  tables can be used during this function calculation for loading time zone
  descriptions.
*/
class Item_func_convert_tz :public Item_datetime_func
{
  /*
    If time zone parameters are constants we are caching objects that
    represent them (we use separate from_tz_cached/to_tz_cached members
    to indicate this fact, since NULL is legal value for from_tz/to_tz
    members.
  */
  bool from_tz_cached, to_tz_cached;
  Time_zone *from_tz, *to_tz;
 public:
  Item_func_convert_tz(Item *a, Item *b, Item *c):
    Item_datetime_func(a, b, c), from_tz_cached(0), to_tz_cached(0) {}
  const char *func_name() const { return "convert_tz"; }
};


class Item_func_sec_to_time :public Item_time_func
{
public:
  Item_func_sec_to_time(Item *item) :Item_time_func(item) {}

  const char *func_name() const { return "sec_to_time"; }
};


class Item_date_add_interval :public Item_temporal_hybrid_func
{
  String value;

public:
  const interval_type int_type; // keep it public
  const bool date_sub_interval; // keep it public
  Item_date_add_interval(Item *a,Item *b,interval_type type_arg,bool neg_arg)
    :Item_temporal_hybrid_func(a, b),
     int_type(type_arg), date_sub_interval(neg_arg) {}
  const char *func_name() const { return "date_add_interval"; }
  void print(String *str, enum_query_type query_type);
};


class Item_extract :public Item_int_func
{
  bool date_value;
 public:
  const interval_type int_type; // keep it public
  Item_extract(interval_type type_arg, Item *a)
    :Item_int_func(a), int_type(type_arg) {}
  longlong val_int() {return 0;}
  enum Functype functype() const { return EXTRACT_FUNC; }
  const char *func_name() const { return "extract"; }
  virtual void print(String *str, enum_query_type query_type);
  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    switch (int_type) {
    case INTERVAL_YEAR:
    case INTERVAL_YEAR_MONTH:
    case INTERVAL_QUARTER:
    case INTERVAL_MONTH:
    /* case INTERVAL_WEEK: Not allowed as partitioning function, bug#57071 */
    case INTERVAL_DAY:
      return !has_date_args();
    case INTERVAL_DAY_HOUR:
    case INTERVAL_DAY_MINUTE:
    case INTERVAL_DAY_SECOND:
    case INTERVAL_DAY_MICROSECOND:
      return !has_datetime_args();
    case INTERVAL_HOUR:
    case INTERVAL_HOUR_MINUTE:
    case INTERVAL_HOUR_SECOND:
    case INTERVAL_MINUTE:
    case INTERVAL_MINUTE_SECOND:
    case INTERVAL_SECOND:
    case INTERVAL_MICROSECOND:
    case INTERVAL_HOUR_MICROSECOND:
    case INTERVAL_MINUTE_MICROSECOND:
    case INTERVAL_SECOND_MICROSECOND:
      return !has_time_args();
    default:
      /*
        INTERVAL_LAST is only an end marker,
        INTERVAL_WEEK depends on default_week_format which is a session
        variable and cannot be used for partitioning. See bug#57071.
      */
      break;
    }
    return true;
  }
};


class Item_date_typecast :public Item_date_func
{
public:
  Item_date_typecast(Item *a) :Item_date_func(a) { maybe_null= 1; }
  void print(String *str, enum_query_type query_type);
  const char *func_name() const { return "cast_as_date"; }
  const char *cast_type() const { return "date"; }
};


class Item_time_typecast :public Item_time_func
{
  bool detect_precision_from_arg;
public:
  Item_time_typecast(Item *a): Item_time_func(a)
  {
    detect_precision_from_arg= true;
  }
  Item_time_typecast(Item *a, uint8 dec_arg): Item_time_func(a)
  {
    detect_precision_from_arg= false;
    decimals= dec_arg;
  }
  void print(String *str, enum_query_type query_type);
  const char *func_name() const { return "cast_as_time"; }
  const char *cast_type() const { return "time"; }
};


class Item_datetime_typecast :public Item_datetime_func
{
  bool detect_precision_from_arg;
public:
  Item_datetime_typecast(Item *a) :Item_datetime_func(a)
  {
    detect_precision_from_arg= true;
  }
  Item_datetime_typecast(Item *a, uint8 dec_arg) :Item_datetime_func(a)
  {
    detect_precision_from_arg= false;
    decimals= dec_arg;
  }
  void print(String *str, enum_query_type query_type);
  const char *func_name() const { return "cast_as_datetime"; }
  const char *cast_type() const { return "datetime"; }
};


class Item_func_makedate :public Item_date_func
{
public:
  Item_func_makedate(Item *a, Item *b) :Item_date_func(a, b) { maybe_null= 1; }
  const char *func_name() const { return "makedate"; }
};


class Item_func_add_time :public Item_temporal_hybrid_func
{
  const bool is_date;
  int sign;
public:
  Item_func_add_time(Item *a, Item *b, bool type_arg, bool neg_arg)
    :Item_temporal_hybrid_func(a, b), is_date(type_arg)
  {
    sign= neg_arg ? -1 : 1;
  }
  void print(String *str, enum_query_type query_type);
  const char *func_name() const { return "add_time"; }
};


class Item_func_timediff :public Item_time_func
{
public:
  Item_func_timediff(Item *a, Item *b) :Item_time_func(a, b) {}
  const char *func_name() const { return "timediff"; }
};

class Item_func_maketime :public Item_time_func
{
public:
  Item_func_maketime(Item *a, Item *b, Item *c) :Item_time_func(a, b, c) 
  {
    maybe_null= TRUE;
  }
  const char *func_name() const { return "maketime"; }
};

class Item_func_microsecond :public Item_int_func
{
public:
  Item_func_microsecond(Item *a) :Item_int_func(a) {}
  longlong val_int() {return 0;}
  const char *func_name() const { return "microsecond"; }
  bool check_partition_func_processor(uchar *int_arg) {return FALSE;}
  bool check_valid_arguments_processor(uchar *int_arg)
  {
    return !has_time_args();
  }
};


class Item_func_timestamp_diff :public Item_int_func
{
  const interval_type int_type;
public:
  Item_func_timestamp_diff(Item *a,Item *b,interval_type type_arg)
    :Item_int_func(a,b), int_type(type_arg) {}
  const char *func_name() const { return "timestampdiff"; }
  longlong val_int() {return 0;}
  virtual void print(String *str, enum_query_type query_type);
};


enum date_time_format
{
  USA_FORMAT, JIS_FORMAT, ISO_FORMAT, EUR_FORMAT, INTERNAL_FORMAT
};

class Item_func_get_format :public Item_str_ascii_func
{
public:
  const timestamp_type type; // keep it public
  Item_func_get_format(timestamp_type type_arg, Item *a)
    :Item_str_ascii_func(a), type(type_arg)
  {}
  String *val_str_ascii(String *str);
  const char *func_name() const { return "get_format"; }
  virtual void print(String *str, enum_query_type query_type);
};


class Item_func_str_to_date :public Item_temporal_hybrid_func
{
  timestamp_type cached_timestamp_type;
  bool const_item;
  void fix_from_format(const char *format, uint length);
public:
  Item_func_str_to_date(Item *a, Item *b)
    :Item_temporal_hybrid_func(a, b), const_item(false)
  {}
  const char *func_name() const { return "str_to_date"; }
};


class Item_func_last_day :public Item_date_func
{
public:
  Item_func_last_day(Item *a) :Item_date_func(a) { maybe_null= 1; }
  const char *func_name() const { return "last_day"; }
};


/* Function prototypes */

bool make_date_time(DATE_TIME_FORMAT *format, MYSQL_TIME *l_time,
                    timestamp_type type, String *str);

#endif /* ITEM_TIMEFUNC_INCLUDED */
