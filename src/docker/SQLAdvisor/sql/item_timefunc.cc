/*
   Copyright (c) 2000, 2013, Oracle and/or its affiliates. All rights reserved.

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
  This file defines all time functions

  @todo
    Move month and days to language files
*/

#include "sql_priv.h"
/*
  It is necessary to include set_var.h instead of item.h because there
  are dependencies on include order for set_var.h and item.h. This
  will be resolved later.
*/
#include "sql_class.h"                          // set_var.h: THD
#include "set_var.h"
#include "sql_locale.h"          // MY_LOCALE my_locale_en_US
#include "strfunc.h"             // check_word
#include "sql_time.h"            // make_truncated_value_warning,
                                 // make_time, get_date_from_daynr,
                                 // calc_weekday, calc_week,
                                 // convert_month_to_period,
                                 // convert_period_to_month,
                                 // TIME_to_timestamp, make_date,
                                 // calc_time_diff,
                                 // calc_time_from_sec,
                                 // known_date_time_format,
                                 // get_date_time_format_str
#include "sql_class.h"           // THD
#include <m_ctype.h>
#include <time.h>

using std::min;
using std::max;

/** Day number for Dec 31st, 9999. */
#define MAX_DAY_NUMBER 3652424L


/**
  Check and adjust a time value with a warning.

  @param ltime    Time variable.
  @param decimals Precision. 
  @retval         True on error, false of success.
*/
static void
adjust_time_range_with_warn(MYSQL_TIME *ltime, uint8 decimals)
{
  /* Fatally bad value should not come here */
  if (check_time_range_quick(ltime))
  {
    int warning= 0;
    make_truncated_value_warning(ErrConvString(ltime, decimals),
                                 MYSQL_TIMESTAMP_TIME);
    adjust_time_range(ltime, &warning);
  }
}


/*
  Convert seconds to MYSQL_TIME value with overflow checking.

  SYNOPSIS:
    sec_to_time()
    seconds          number of seconds
    ltime            output MYSQL_TIME value

  DESCRIPTION
    If the 'seconds' argument is inside MYSQL_TIME data range, convert it to a
    corresponding value.
    Otherwise, truncate the resulting value to the nearest endpoint.
    Note: Truncation in this context means setting the result to the MAX/MIN
          value of TIME type if value is outside the allowed range.
          If the number of decimals exceeds what is supported, the value
          is rounded to the supported number of decimals.

  RETURN
    1                if the value was truncated during conversion
    0                otherwise
*/

static bool sec_to_time(lldiv_t seconds, MYSQL_TIME *ltime)
{
  int warning= 0;

  set_zero_time(ltime, MYSQL_TIMESTAMP_TIME);
  
  if (seconds.quot < 0 || seconds.rem < 0)
  {
    ltime->neg= 1;
    seconds.quot= -seconds.quot;
    seconds.rem= -seconds.rem;
  }
  
  if (seconds.quot > TIME_MAX_VALUE_SECONDS)
  {
    set_max_hhmmss(ltime);
    return true;
  }

  ltime->hour= (uint) (seconds.quot / 3600);
  uint sec= (uint) (seconds.quot % 3600);
  ltime->minute= sec / 60;
  ltime->second= sec % 60;
  time_add_nanoseconds_with_round(ltime, seconds.rem, &warning);
  
  adjust_time_range(ltime, &warning);

  return warning ? true : false;
}


/*
  Date formats corresponding to compound %r and %T conversion specifiers

  Note: We should init at least first element of "positions" array
        (first member) or hpux11 compiler will die horribly.
*/
static DATE_TIME_FORMAT time_ampm_format= {{0}, '\0', 0,
                                           {(char *)"%I:%i:%S %p", 11}};
static DATE_TIME_FORMAT time_24hrs_format= {{0}, '\0', 0,
                                            {(char *)"%H:%i:%S", 8}};

/**
  Extract datetime value to MYSQL_TIME struct from string value
  according to format string.

  @param format		date/time format specification
  @param val			String to decode
  @param length		Length of string
  @param l_time		Store result here
  @param cached_timestamp_type  It uses to get an appropriate warning
                                in the case when the value is truncated.
  @param sub_pattern_end    if non-zero then we are parsing string which
                            should correspond compound specifier (like %T or
                            %r) and this parameter is pointer to place where
                            pointer to end of string matching this specifier
                            should be stored.

  @note
    Possibility to parse strings matching to patterns equivalent to compound
    specifiers is mainly intended for use from inside of this function in
    order to understand %T and %r conversion specifiers, so number of
    conversion specifiers that can be used in such sub-patterns is limited.
    Also most of checks are skipped in this case.

  @note
    If one adds new format specifiers to this function he should also
    consider adding them to Item_func_str_to_date::fix_from_format().

  @retval
    0	ok
  @retval
    1	error
*/

static bool extract_date_time(DATE_TIME_FORMAT *format,
			      const char *val, uint length, MYSQL_TIME *l_time,
                              timestamp_type cached_timestamp_type,
                              const char **sub_pattern_end,
                              const char *date_time_type)
{
  int weekday= 0, yearday= 0, daypart= 0;
  int week_number= -1;
  int error= 0;
  int  strict_week_number_year= -1;
  int frac_part;
  bool usa_time= 0;
  bool UNINIT_VAR(sunday_first_n_first_week_non_iso);
  bool UNINIT_VAR(strict_week_number);
  bool UNINIT_VAR(strict_week_number_year_type);
  const char *val_begin= val;
  const char *val_end= val + length;
  const char *ptr= format->format.str;
  const char *end= ptr + format->format.length;
  const CHARSET_INFO *cs= &my_charset_bin;
  DBUG_ENTER("extract_date_time");

  if (!sub_pattern_end)
    memset(l_time, 0, sizeof(*l_time));

  for (; ptr != end && val != val_end; ptr++)
  {
    /* Skip pre-space between each argument */
    if ((val+= cs->cset->scan(cs, val, val_end, MY_SEQ_SPACES)) >= val_end)
      break;

    if (*ptr == '%' && ptr+1 != end)
    {
      int val_len;
      char *tmp;

      error= 0;

      val_len= (uint) (val_end - val);
      switch (*++ptr) {
	/* Year */
      case 'Y':
	tmp= (char*) val + MY_MIN(4, val_len);
	l_time->year= (int) my_strtoll10(val, &tmp, &error);
        if ((int) (tmp-val) <= 2)
          l_time->year= year_2000_handling(l_time->year);
	val= tmp;
	break;
      case 'y':
	tmp= (char*) val + MY_MIN(2, val_len);
	l_time->year= (int) my_strtoll10(val, &tmp, &error);
	val= tmp;
        l_time->year= year_2000_handling(l_time->year);
	break;

	/* Month */
      case 'm':
      case 'c':
	tmp= (char*) val + MY_MIN(2, val_len);
	l_time->month= (int) my_strtoll10(val, &tmp, &error);
	val= tmp;
	break;
      case 'M':
	if ((l_time->month= check_word(my_locale_en_US.month_names,
				       val, val_end, &val)) <= 0)
	  goto err;
	break;
      case 'b':
	if ((l_time->month= check_word(my_locale_en_US.ab_month_names,
				       val, val_end, &val)) <= 0)
	  goto err;
	break;
	/* Day */
      case 'd':
      case 'e':
	tmp= (char*) val + MY_MIN(2, val_len);
	l_time->day= (int) my_strtoll10(val, &tmp, &error);
	val= tmp;
	break;
      case 'D':
	tmp= (char*) val + MY_MIN(2, val_len);
	l_time->day= (int) my_strtoll10(val, &tmp, &error);
	/* Skip 'st, 'nd, 'th .. */
	val= tmp + MY_MIN((int) (val_end-tmp), 2);
	break;

	/* Hour */
      case 'h':
      case 'I':
      case 'l':
	usa_time= 1;
	/* fall through */
      case 'k':
      case 'H':
	tmp= (char*) val + MY_MIN(2, val_len);
	l_time->hour= (int) my_strtoll10(val, &tmp, &error);
	val= tmp;
	break;

	/* Minute */
      case 'i':
	tmp= (char*) val + MY_MIN(2, val_len);
	l_time->minute= (int) my_strtoll10(val, &tmp, &error);
	val= tmp;
	break;

	/* Second */
      case 's':
      case 'S':
	tmp= (char*) val + MY_MIN(2, val_len);
	l_time->second= (int) my_strtoll10(val, &tmp, &error);
	val= tmp;
	break;

	/* Second part */
      case 'f':
	tmp= (char*) val_end;
	if (tmp - val > 6)
	  tmp= (char*) val + 6;
	l_time->second_part= (int) my_strtoll10(val, &tmp, &error);
	frac_part= 6 - (int) (tmp - val);
	if (frac_part > 0)
	  l_time->second_part*= (ulong) log_10_int[frac_part];
	val= tmp;
	break;

	/* AM / PM */
      case 'p':
	if (val_len < 2 || ! usa_time)
	  goto err;
	if (!my_strnncoll(&my_charset_latin1,
			  (const uchar *) val, 2, 
			  (const uchar *) "PM", 2))
	  daypart= 12;
	else if (my_strnncoll(&my_charset_latin1,
			      (const uchar *) val, 2, 
			      (const uchar *) "AM", 2))
	  goto err;
	val+= 2;
	break;

	/* Exotic things */
      case 'W':
	if ((weekday= check_word(my_locale_en_US.day_names, val, val_end, &val)) <= 0)
	  goto err;
	break;
      case 'a':
	if ((weekday= check_word(my_locale_en_US.ab_day_names, val, val_end, &val)) <= 0)
	  goto err;
	break;
      case 'w':
	tmp= (char*) val + 1;
	if ((weekday= (int) my_strtoll10(val, &tmp, &error)) < 0 ||
	    weekday >= 7)
	  goto err;
        /* We should use the same 1 - 7 scale for %w as for %W */
        if (!weekday)
          weekday= 7;
	val= tmp;
	break;
      case 'j':
	tmp= (char*) val + MY_MIN(val_len, 3);
	yearday= (int) my_strtoll10(val, &tmp, &error);
	val= tmp;
	break;

        /* Week numbers */
      case 'V':
      case 'U':
      case 'v':
      case 'u':
        sunday_first_n_first_week_non_iso= (*ptr=='U' || *ptr== 'V');
        strict_week_number= (*ptr=='V' || *ptr=='v');
	tmp= (char*) val + MY_MIN(val_len, 2);
	if ((week_number= (int) my_strtoll10(val, &tmp, &error)) < 0 ||
            (strict_week_number && !week_number) ||
            week_number > 53)
          goto err;
	val= tmp;
	break;

        /* Year used with 'strict' %V and %v week numbers */
      case 'X':
      case 'x':
        strict_week_number_year_type= (*ptr=='X');
        tmp= (char*) val + MY_MIN(4, val_len);
        strict_week_number_year= (int) my_strtoll10(val, &tmp, &error);
        val= tmp;
        break;

        /* Time in AM/PM notation */
      case 'r':
        /*
          We can't just set error here, as we don't want to generate two
          warnings in case of errors
        */
        if (extract_date_time(&time_ampm_format, val,
                              (uint)(val_end - val), l_time,
                              cached_timestamp_type, &val, "time"))
          DBUG_RETURN(1);
        break;

        /* Time in 24-hour notation */
      case 'T':
        if (extract_date_time(&time_24hrs_format, val,
                              (uint)(val_end - val), l_time,
                              cached_timestamp_type, &val, "time"))
          DBUG_RETURN(1);
        break;

        /* Conversion specifiers that match classes of characters */
      case '.':
	while (my_ispunct(cs, *val) && val != val_end)
	  val++;
	break;
      case '@':
	while (my_isalpha(cs, *val) && val != val_end)
	  val++;
	break;
      case '#':
	while (my_isdigit(cs, *val) && val != val_end)
	  val++;
	break;
      default:
	goto err;
      }
      if (error)				// Error from my_strtoll10
	goto err;
    }
    else if (!my_isspace(cs, *ptr))
    {
      if (*val != *ptr)
	goto err;
      val++;
    }
  }
  if (usa_time)
  {
    if (l_time->hour > 12 || l_time->hour < 1)
      goto err;
    l_time->hour= l_time->hour%12+daypart;
  }

  /*
    If we are recursively called for parsing string matching compound
    specifiers we are already done.
  */
  if (sub_pattern_end)
  {
    *sub_pattern_end= val;
    DBUG_RETURN(0);
  }

  if (yearday > 0)
  {
    uint days;
    days= calc_daynr(l_time->year,1,1) +  yearday - 1;
    if (days <= 0 || days > MAX_DAY_NUMBER)
      goto err;
    get_date_from_daynr(days,&l_time->year,&l_time->month,&l_time->day);
  }

  if (week_number >= 0 && weekday)
  {
    int days;
    uint weekday_b;

    /*
      %V,%v require %X,%x resprectively,
      %U,%u should be used with %Y and not %X or %x
    */
    if ((strict_week_number &&
        (strict_week_number_year < 0 ||
         strict_week_number_year_type != sunday_first_n_first_week_non_iso)) ||
        (!strict_week_number && strict_week_number_year >= 0))
      goto err;

    /* Number of days since year 0 till 1st Jan of this year */
    days= calc_daynr((strict_week_number ? strict_week_number_year :
                                           l_time->year),
                     1, 1);
    /* Which day of week is 1st Jan of this year */
    weekday_b= calc_weekday(days, sunday_first_n_first_week_non_iso);

    /*
      Below we are going to sum:
      1) number of days since year 0 till 1st day of 1st week of this year
      2) number of days between 1st week and our week
      3) and position of our day in the week
    */
    if (sunday_first_n_first_week_non_iso)
    {
      days+= ((weekday_b == 0) ? 0 : 7) - weekday_b +
             (week_number - 1) * 7 +
             weekday % 7;
    }
    else
    {
      days+= ((weekday_b <= 3) ? 0 : 7) - weekday_b +
             (week_number - 1) * 7 +
             (weekday - 1);
    }

    if (days <= 0 || days > MAX_DAY_NUMBER)
      goto err;
    get_date_from_daynr(days,&l_time->year,&l_time->month,&l_time->day);
  }

  if (l_time->month > 12 || l_time->day > 31 || l_time->hour > 23 || 
      l_time->minute > 59 || l_time->second > 59)
    goto err;

  if (val != val_end)
  {
    do
    {
      if (!my_isspace(&my_charset_latin1,*val))
      {
        // TS-TODO: extract_date_time is not UCS2 safe
        make_truncated_value_warning(ErrConvString(val_begin, length),
                                     cached_timestamp_type);
	break;
      }
    } while (++val != val_end);
  }
  DBUG_RETURN(0);

err:
  {
    char buff[128];
    strmake(buff, val_begin, min<size_t>(length, sizeof(buff)-1));
    push_warning_printf(current_thd, Sql_condition::WARN_LEVEL_WARN,
                        ER_WRONG_VALUE_FOR_TYPE, ER(ER_WRONG_VALUE_FOR_TYPE),
                        date_time_type, buff, "str_to_date");
  }
  DBUG_RETURN(1);
}


/**
  Create a formated date/time value in a string.
*/

bool make_date_time(DATE_TIME_FORMAT *format, MYSQL_TIME *l_time,
		    timestamp_type type, String *str)
{
  char intbuff[15];
  uint hours_i;
  uint weekday;
  ulong length;
  const char *ptr, *end;
  THD *thd= current_thd;
  MY_LOCALE *locale= thd->variables.lc_time_names;

  str->length(0);

  if (l_time->neg)
    str->append('-');
  
  end= (ptr= format->format.str) + format->format.length;
  for (; ptr != end ; ptr++)
  {
    if (*ptr != '%' || ptr+1 == end)
      str->append(*ptr);
    else
    {
      switch (*++ptr) {
      case 'M':
        if (!l_time->month)
          return 1;
        str->append(locale->month_names->type_names[l_time->month-1],
                    (uint) strlen(locale->month_names->type_names[l_time->month-1]),
                    system_charset_info);
        break;
      case 'b':
        if (!l_time->month)
          return 1;
        str->append(locale->ab_month_names->type_names[l_time->month-1],
                    (uint) strlen(locale->ab_month_names->type_names[l_time->month-1]),
                    system_charset_info);
        break;
      case 'W':
        if (type == MYSQL_TIMESTAMP_TIME || !(l_time->month || l_time->year))
          return 1;
        weekday= calc_weekday(calc_daynr(l_time->year,l_time->month,
                              l_time->day),0);
        str->append(locale->day_names->type_names[weekday],
                    (uint) strlen(locale->day_names->type_names[weekday]),
                    system_charset_info);
        break;
      case 'a':
        if (type == MYSQL_TIMESTAMP_TIME || !(l_time->month || l_time->year))
          return 1;
        weekday=calc_weekday(calc_daynr(l_time->year,l_time->month,
                             l_time->day),0);
        str->append(locale->ab_day_names->type_names[weekday],
                    (uint) strlen(locale->ab_day_names->type_names[weekday]),
                    system_charset_info);
        break;
      case 'D':
	if (type == MYSQL_TIMESTAMP_TIME)
	  return 1;
	length= (uint) (int10_to_str(l_time->day, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 1, '0');
	if (l_time->day >= 10 &&  l_time->day <= 19)
	  str->append(STRING_WITH_LEN("th"));
	else
	{
	  switch (l_time->day %10) {
	  case 1:
	    str->append(STRING_WITH_LEN("st"));
	    break;
	  case 2:
	    str->append(STRING_WITH_LEN("nd"));
	    break;
	  case 3:
	    str->append(STRING_WITH_LEN("rd"));
	    break;
	  default:
	    str->append(STRING_WITH_LEN("th"));
	    break;
	  }
	}
	break;
      case 'Y':
	length= (uint) (int10_to_str(l_time->year, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 4, '0');
	break;
      case 'y':
	length= (uint) (int10_to_str(l_time->year%100, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 2, '0');
	break;
      case 'm':
	length= (uint) (int10_to_str(l_time->month, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 2, '0');
	break;
      case 'c':
	length= (uint) (int10_to_str(l_time->month, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 1, '0');
	break;
      case 'd':
	length= (uint) (int10_to_str(l_time->day, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 2, '0');
	break;
      case 'e':
	length= (uint) (int10_to_str(l_time->day, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 1, '0');
	break;
      case 'f':
	length= (uint) (int10_to_str(l_time->second_part, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 6, '0');
	break;
      case 'H':
	length= (uint) (int10_to_str(l_time->hour, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 2, '0');
	break;
      case 'h':
      case 'I':
	hours_i= (l_time->hour%24 + 11)%12+1;
	length= (uint) (int10_to_str(hours_i, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 2, '0');
	break;
      case 'i':					/* minutes */
	length= (uint) (int10_to_str(l_time->minute, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 2, '0');
	break;
      case 'j':
	if (type == MYSQL_TIMESTAMP_TIME)
	  return 1;
	length= (uint) (int10_to_str(calc_daynr(l_time->year,l_time->month,
					l_time->day) - 
		     calc_daynr(l_time->year,1,1) + 1, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 3, '0');
	break;
      case 'k':
	length= (uint) (int10_to_str(l_time->hour, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 1, '0');
	break;
      case 'l':
	hours_i= (l_time->hour%24 + 11)%12+1;
	length= (uint) (int10_to_str(hours_i, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 1, '0');
	break;
      case 'p':
	hours_i= l_time->hour%24;
	str->append(hours_i < 12 ? "AM" : "PM",2);
	break;
      case 'r':
	length= sprintf(intbuff, ((l_time->hour % 24) < 12) ?
                        "%02d:%02d:%02d AM" : "%02d:%02d:%02d PM",
		        (l_time->hour+11)%12+1,
		        l_time->minute,
		        l_time->second);
	str->append(intbuff, length);
	break;
      case 'S':
      case 's':
	length= (uint) (int10_to_str(l_time->second, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 2, '0');
	break;
      case 'T':
	length= sprintf(intbuff,  "%02d:%02d:%02d",
                        l_time->hour, l_time->minute, l_time->second);
	str->append(intbuff, length);
	break;
      case 'U':
      case 'u':
      {
	uint year;
	if (type == MYSQL_TIMESTAMP_TIME)
	  return 1;
	length= (uint) (int10_to_str(calc_week(l_time,
				       (*ptr) == 'U' ?
				       WEEK_FIRST_WEEKDAY : WEEK_MONDAY_FIRST,
				       &year),
			     intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 2, '0');
      }
      break;
      case 'v':
      case 'V':
      {
	uint year;
	if (type == MYSQL_TIMESTAMP_TIME)
	  return 1;
	length= (uint) (int10_to_str(calc_week(l_time,
				       ((*ptr) == 'V' ?
					(WEEK_YEAR | WEEK_FIRST_WEEKDAY) :
					(WEEK_YEAR | WEEK_MONDAY_FIRST)),
				       &year),
			     intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 2, '0');
      }
      break;
      case 'x':
      case 'X':
      {
	uint year;
	if (type == MYSQL_TIMESTAMP_TIME)
	  return 1;
	(void) calc_week(l_time,
			 ((*ptr) == 'X' ?
			  WEEK_YEAR | WEEK_FIRST_WEEKDAY :
			  WEEK_YEAR | WEEK_MONDAY_FIRST),
			 &year);
	length= (uint) (int10_to_str(year, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 4, '0');
      }
      break;
      case 'w':
	if (type == MYSQL_TIMESTAMP_TIME || !(l_time->month || l_time->year))
	  return 1;
	weekday=calc_weekday(calc_daynr(l_time->year,l_time->month,
					l_time->day),1);
	length= (uint) (int10_to_str(weekday, intbuff, 10) - intbuff);
	str->append_with_prefill(intbuff, length, 1, '0');
	break;

      default:
	str->append(*ptr);
	break;
      }
    }
  }
  return 0;
}



void Item_date_literal::print(String *str, enum_query_type query_type)
{
  str->append("DATE'");
  str->append(cached_time.cptr());
  str->append('\'');
}



void Item_datetime_literal::print(String *str, enum_query_type query_type)
{
  str->append("TIMESTAMP'");
  str->append(cached_time.cptr());
  str->append('\'');
}


void Item_time_literal::print(String *str, enum_query_type query_type)
{
  str->append("TIME'");
  str->append(cached_time.cptr());
  str->append('\'');
}


longlong Item_func_period_add::val_int()
{
  DBUG_ASSERT(fixed == 1);
  ulong period=(ulong) args[0]->val_int();
  int months=(int) args[1]->val_int();

  if ((null_value=args[0]->null_value || args[1]->null_value) ||
      period == 0L)
    return 0; /* purecov: inspected */
  return (longlong)
    convert_month_to_period((uint) ((int) convert_period_to_month(period)+
				    months));
}


longlong Item_func_period_diff::val_int()
{
  DBUG_ASSERT(fixed == 1);
  ulong period1=(ulong) args[0]->val_int();
  ulong period2=(ulong) args[1]->val_int();

  if ((null_value=args[0]->null_value || args[1]->null_value))
    return 0; /* purecov: inspected */
  return (longlong) ((long) convert_period_to_month(period1)-
		     (long) convert_period_to_month(period2));
}



longlong Item_func_to_days::val_int()
{
  return (longlong) 0;
}


longlong Item_func_to_seconds::val_int()
{
  return 0;
}

/*
  Get information about this Item tree monotonicity

  SYNOPSIS
    Item_func_to_days::get_monotonicity_info()

  DESCRIPTION
  Get information about monotonicity of the function represented by this item
  tree.

  RETURN
    See enum_monotonicity_info.
*/

enum_monotonicity_info Item_func_to_days::get_monotonicity_info() const
{
  if (args[0]->type() == Item::FIELD_ITEM)
  {
    if (args[0]->field_type() == MYSQL_TYPE_DATE)
      return MONOTONIC_STRICT_INCREASING_NOT_NULL;
    if (args[0]->field_type() == MYSQL_TYPE_DATETIME)
      return MONOTONIC_INCREASING_NOT_NULL;
  }
  return NON_MONOTONIC;
}

enum_monotonicity_info Item_func_to_seconds::get_monotonicity_info() const
{
  if (args[0]->type() == Item::FIELD_ITEM)
  {
    if (args[0]->field_type() == MYSQL_TYPE_DATE ||
        args[0]->field_type() == MYSQL_TYPE_DATETIME)
      return MONOTONIC_STRICT_INCREASING_NOT_NULL;
  }
  return NON_MONOTONIC;
}


longlong Item_func_dayofyear::val_int()
{
    return 0;
}

longlong Item_func_dayofmonth::val_int()
{
  return 0;
}

longlong Item_func_month::val_int()
{
  return 0;
}


String* Item_func_monthname::val_str(String* str)
{
  return 0;
}


/**
  Returns the quarter of the year.
*/

longlong Item_func_quarter::val_int()
{
  return 0;
}

longlong Item_func_hour::val_int()
{
  return 0;
}

longlong Item_func_minute::val_int()
{
  return 0;
}

/**
  Returns the second in time_exp in the range of 0 - 59.
*/
longlong Item_func_second::val_int()
{
  return 0;
}


uint week_mode(uint mode)
{
  uint week_format= (mode & 7);
  if (!(week_format & WEEK_MONDAY_FIRST))
    week_format^= WEEK_FIRST_WEEKDAY;
  return week_format;
}

/**
 @verbatim
  The bits in week_format(for calc_week() function) has the following meaning:
   WEEK_MONDAY_FIRST (0)  If not set	Sunday is first day of week
      		   	  If set	Monday is first day of week
   WEEK_YEAR (1)	  If not set	Week is in range 0-53

   	Week 0 is returned for the the last week of the previous year (for
	a date at start of january) In this case one can get 53 for the
	first week of next year.  This flag ensures that the week is
	relevant for the given year. Note that this flag is only
	releveant if WEEK_JANUARY is not set.

			  If set	 Week is in range 1-53.

	In this case one may get week 53 for a date in January (when
	the week is that last week of previous year) and week 1 for a
	date in December.

  WEEK_FIRST_WEEKDAY (2)  If not set	Weeks are numbered according
			   		to ISO 8601:1988
			  If set	The week that contains the first
					'first-day-of-week' is week 1.
	
	ISO 8601:1988 means that if the week containing January 1 has
	four or more days in the new year, then it is week 1;
	Otherwise it is the last week of the previous year, and the
	next week is week 1.
 @endverbatim
*/

longlong Item_func_week::val_int()
{
    return 0;
}


longlong Item_func_yearweek::val_int()
{
    return 0;
}


longlong Item_func_weekday::val_int()
{
    return 0;
}



String* Item_func_dayname::val_str(String* str)
{
    return (String*) 0;
}


longlong Item_func_year::val_int()
{
  return 0 ;
}


/*
  Get information about this Item tree monotonicity

  SYNOPSIS
    Item_func_year::get_monotonicity_info()

  DESCRIPTION
  Get information about monotonicity of the function represented by this item
  tree.

  RETURN
    See enum_monotonicity_info.
*/

enum_monotonicity_info Item_func_year::get_monotonicity_info() const
{
  if (args[0]->type() == Item::FIELD_ITEM &&
      (args[0]->field_type() == MYSQL_TYPE_DATE ||
       args[0]->field_type() == MYSQL_TYPE_DATETIME))
    return MONOTONIC_INCREASING;
  return NON_MONOTONIC;
}



enum_monotonicity_info Item_func_unix_timestamp::get_monotonicity_info() const
{
  if (args[0]->type() == Item::FIELD_ITEM &&
      (args[0]->field_type() == MYSQL_TYPE_TIMESTAMP))
    return MONOTONIC_INCREASING;
  return NON_MONOTONIC;
}

void MYSQL_TIME_cache::set_time(MYSQL_TIME *ltime, uint8 dec_arg)
{
  DBUG_ASSERT(ltime->time_type == MYSQL_TIMESTAMP_TIME);
  time= *ltime;
  time_packed= TIME_to_longlong_time_packed(&time);
  dec= dec_arg;
  reset_string();
}


void MYSQL_TIME_cache::set_date(MYSQL_TIME *ltime)
{
  DBUG_ASSERT(ltime->time_type == MYSQL_TIMESTAMP_DATE);
  time= *ltime;
  time_packed= TIME_to_longlong_date_packed(&time);
  dec= 0;
  reset_string();
}


void MYSQL_TIME_cache::set_datetime(MYSQL_TIME *ltime, uint8 dec_arg)
{
  DBUG_ASSERT(ltime->time_type == MYSQL_TIMESTAMP_DATETIME);
  time= *ltime;
  time_packed= TIME_to_longlong_datetime_packed(&time);
  dec= dec_arg;
  reset_string();
}

void MYSQL_TIME_cache::cache_string()
{
  DBUG_ASSERT(time.time_type != MYSQL_TIMESTAMP_NONE);
  if (string_length == 0)
    string_length= my_TIME_to_str(&time, string_buff, decimals());
}


const char *MYSQL_TIME_cache::cptr()
{
  cache_string();
  return string_buff;
}


bool MYSQL_TIME_cache::get_date(MYSQL_TIME *ltime, uint fuzzydate) const
{
  int warnings;
  get_TIME(ltime);
  return check_date(ltime, non_zero_date(ltime), fuzzydate, &warnings);
}


String *MYSQL_TIME_cache::val_str(String *str)
{
  cache_string();
  str->set(string_buff, string_length, &my_charset_latin1);
  return str;
}
/*
   'interval_names' reflects the order of the enumeration interval_type.
   See item_timefunc.h
 */

static const char *interval_names[]=
{
  "year", "quarter", "month", "week", "day",  
  "hour", "minute", "second", "microsecond",
  "year_month", "day_hour", "day_minute", 
  "day_second", "hour_minute", "hour_second",
  "minute_second", "day_microsecond",
  "hour_microsecond", "minute_microsecond",
  "second_microsecond"
};

void Item_date_add_interval::print(String *str, enum_query_type query_type)
{
  str->append('(');
  args[0]->print(str, query_type);
  str->append(date_sub_interval?" - interval ":" + interval ");
  args[1]->print(str, query_type);
  str->append(' ');
  str->append(interval_names[int_type]);
  str->append(')');
}

void Item_extract::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("extract("));
  str->append(interval_names[int_type]);
  str->append(STRING_WITH_LEN(" from "));
  args[0]->print(str, query_type);
  str->append(')');
}


void Item_datetime_typecast::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("cast("));
  args[0]->print(str, query_type);
  str->append(STRING_WITH_LEN(" as "));
  str->append(cast_type());
  if (decimals)
    str->append_parenthesized(decimals);
  str->append(')');
}

void Item_time_typecast::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("cast("));
  args[0]->print(str, query_type);
  str->append(STRING_WITH_LEN(" as "));
  str->append(cast_type());
  if (decimals)
    str->append_parenthesized(decimals);
  str->append(')');
}



void Item_date_typecast::print(String *str, enum_query_type query_type)
{
  str->append(STRING_WITH_LEN("cast("));
  args[0]->print(str, query_type);
  str->append(STRING_WITH_LEN(" as "));
  str->append(cast_type());
  str->append(')');
}


void Item_func_add_time::print(String *str, enum_query_type query_type)
{
  if (is_date)
  {
    DBUG_ASSERT(sign > 0);
    str->append(STRING_WITH_LEN("timestamp("));
  }
  else
  {
    if (sign > 0)
      str->append(STRING_WITH_LEN("addtime("));
    else
      str->append(STRING_WITH_LEN("subtime("));
  }
  args[0]->print(str, query_type);
  str->append(',');
  args[1]->print(str, query_type);
  str->append(')');
}




void Item_func_timestamp_diff::print(String *str, enum_query_type query_type)
{
  str->append(func_name());
  str->append('(');

  switch (int_type) {
  case INTERVAL_YEAR:
    str->append(STRING_WITH_LEN("YEAR"));
    break;
  case INTERVAL_QUARTER:
    str->append(STRING_WITH_LEN("QUARTER"));
    break;
  case INTERVAL_MONTH:
    str->append(STRING_WITH_LEN("MONTH"));
    break;
  case INTERVAL_WEEK:          
    str->append(STRING_WITH_LEN("WEEK"));
    break;
  case INTERVAL_DAY:		
    str->append(STRING_WITH_LEN("DAY"));
    break;
  case INTERVAL_HOUR:
    str->append(STRING_WITH_LEN("HOUR"));
    break;
  case INTERVAL_MINUTE:		
    str->append(STRING_WITH_LEN("MINUTE"));
    break;
  case INTERVAL_SECOND:
    str->append(STRING_WITH_LEN("SECOND"));
    break;		
  case INTERVAL_MICROSECOND:
    str->append(STRING_WITH_LEN("SECOND_FRAC"));
    break;
  default:
    break;
  }

  for (uint i=0 ; i < 2 ; i++)
  {
    str->append(',');
    args[i]->print(str, query_type);
  }
  str->append(')');
}


String *Item_func_get_format::val_str_ascii(String *str)
{
  DBUG_ASSERT(fixed == 1);
  const char *format_name;
  KNOWN_DATE_TIME_FORMAT *format;
  String *val= args[0]->val_str_ascii(str);
  ulong val_len;

  if ((null_value= args[0]->null_value))
    return 0;    

  val_len= val->length();
  for (format= &known_date_time_formats[0];
       (format_name= format->format_name);
       format++)
  {
    uint format_name_len;
    format_name_len= (uint) strlen(format_name);
    if (val_len == format_name_len &&
	!my_strnncoll(&my_charset_latin1, 
		      (const uchar *) val->ptr(), val_len, 
		      (const uchar *) format_name, val_len))
    {
      const char *format_str= get_date_time_format_str(format, type);
      str->set(format_str, (uint) strlen(format_str), &my_charset_numeric);
      return str;
    }
  }

  null_value= 1;
  return 0;
}


void Item_func_get_format::print(String *str, enum_query_type query_type)
{
  str->append(func_name());
  str->append('(');

  switch (type) {
  case MYSQL_TIMESTAMP_DATE:
    str->append(STRING_WITH_LEN("DATE, "));
    break;
  case MYSQL_TIMESTAMP_DATETIME:
    str->append(STRING_WITH_LEN("DATETIME, "));
    break;
  case MYSQL_TIMESTAMP_TIME:
    str->append(STRING_WITH_LEN("TIME, "));
    break;
  default:
    DBUG_ASSERT(0);
  }
  args[0]->print(str, query_type);
  str->append(')');
}


/**
  Set type of datetime value (DATE/TIME/...) which will be produced
  according to format string.

  @param format   format string
  @param length   length of format string

  @note
    We don't process day format's characters('D', 'd', 'e') because day
    may be a member of all date/time types.

  @note
    Format specifiers supported by this function should be in sync with
    specifiers supported by extract_date_time() function.
*/
void Item_func_str_to_date::fix_from_format(const char *format, uint length)
{
  const char *time_part_frms= "HISThiklrs";
  const char *date_part_frms= "MVUXYWabcjmvuxyw";
  bool date_part_used= 0, time_part_used= 0, frac_second_used= 0;
  const char *val= format;
  const char *end= format + length;

  for (; val != end && val != end; val++)
  {
    if (*val == '%' && val + 1 != end)
    {
      val++;
      if (*val == 'f')
        frac_second_used= time_part_used= 1;
      else if (!time_part_used && strchr(time_part_frms, *val))
	time_part_used= 1;
      else if (!date_part_used && strchr(date_part_frms, *val))
	date_part_used= 1;
      if (date_part_used && frac_second_used)
      {
        /*
          frac_second_used implies time_part_used, and thus we already
          have all types of date-time components and can end our search.
        */
        cached_timestamp_type= MYSQL_TIMESTAMP_DATETIME;
        cached_field_type= MYSQL_TYPE_DATETIME; 
        fix_length_and_dec_and_charset_datetime(MAX_DATETIME_WIDTH,
                                                DATETIME_MAX_DECIMALS);
        return;
      }
    }
  }

  /* We don't have all three types of date-time components */
  if (frac_second_used) /* TIME with microseconds */
  {
    cached_timestamp_type= MYSQL_TIMESTAMP_TIME;
    cached_field_type= MYSQL_TYPE_TIME;
    fix_length_and_dec_and_charset_datetime(MAX_TIME_FULL_WIDTH,
                                            DATETIME_MAX_DECIMALS);
  }
  else if (time_part_used)
  {
    if (date_part_used) /* DATETIME, no microseconds */
    {
      cached_timestamp_type= MYSQL_TIMESTAMP_DATETIME;
      cached_field_type= MYSQL_TYPE_DATETIME; 
      fix_length_and_dec_and_charset_datetime(MAX_DATETIME_WIDTH, 0);
    }
    else /* TIME, no microseconds */
    {
      cached_timestamp_type= MYSQL_TIMESTAMP_TIME;
      cached_field_type= MYSQL_TYPE_TIME;
      fix_length_and_dec_and_charset_datetime(MAX_TIME_WIDTH, 0);
    }
  }
  else /* DATE */
  {
    cached_timestamp_type= MYSQL_TIMESTAMP_DATE;
    cached_field_type= MYSQL_TYPE_DATE; 
    fix_length_and_dec_and_charset_datetime(MAX_DATE_WIDTH, 0);
  }
}

