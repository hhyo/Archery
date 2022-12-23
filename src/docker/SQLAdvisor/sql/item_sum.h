#ifndef ITEM_SUM_INCLUDED
#define ITEM_SUM_INCLUDED

/* Copyright (c) 2000, 2014, Oracle and/or its affiliates. All rights reserved. reserved.
   reserved.

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


/* classes for sum functions */

#include <my_tree.h>
#include "sql_udf.h"                            /* udf_handler */

class Item_sum;
class Aggregator_distinct;
class Aggregator_simple;

/**
  The abstract base class for the Aggregator_* classes.
  It implements the data collection functions (setup/add/clear)
  as either pass-through to the real functionality or
  as collectors into an Unique (for distinct) structure.

  Note that update_field/reset_field are not in that
  class, because they're simply not called when
  GROUP BY/DISTINCT can be handled with help of index on grouped 
  fields (quick_group = 0);
*/

class Aggregator : public Sql_alloc
{
  friend class Item_sum;
  friend class Item_sum_sum;
  friend class Item_sum_count;
  friend class Item_sum_avg;

  /* 
    All members are protected as this class is not usable outside of an 
    Item_sum descendant.
  */
protected:
  /* the aggregate function class to act on */
  Item_sum *item_sum;

public:
  Aggregator (Item_sum *arg): item_sum(arg) {}
  virtual ~Aggregator () {}                   /* Keep gcc happy */

  enum Aggregator_type { SIMPLE_AGGREGATOR, DISTINCT_AGGREGATOR }; 
  virtual Aggregator_type Aggrtype() = 0;
};


class st_select_lex;

/**
  Class Item_sum is the base class used for special expressions that SQL calls
  'set functions'. These expressions are formed with the help of aggregate
  functions such as SUM, MAX, GROUP_CONCAT etc.

 GENERAL NOTES

  A set function cannot be used in certain positions where expressions are
  accepted. There are some quite explicable restrictions for the usage of 
  set functions.

  In the query:
    SELECT AVG(b) FROM t1 WHERE SUM(b) > 20 GROUP by a
  the usage of the set function AVG(b) is legal, while the usage of SUM(b)
  is illegal. A WHERE condition must contain expressions that can be 
  evaluated for each row of the table. Yet the expression SUM(b) can be
  evaluated only for each group of rows with the same value of column a.
  In the query:
    SELECT AVG(b) FROM t1 WHERE c > 30 GROUP BY a HAVING SUM(b) > 20
  both set function expressions AVG(b) and SUM(b) are legal.

  We can say that in a query without nested selects an occurrence of a
  set function in an expression of the SELECT list or/and in the HAVING
  clause is legal, while in the WHERE clause it's illegal.

  The general rule to detect whether a set function is legal in a query with
  nested subqueries is much more complicated.

  Consider the the following query:
    SELECT t1.a FROM t1 GROUP BY t1.a
      HAVING t1.a > ALL (SELECT t2.c FROM t2 WHERE SUM(t1.b) < t2.c).
  The set function SUM(b) is used here in the WHERE clause of the subquery.
  Nevertheless it is legal since it is under the HAVING clause of the query
  to which this function relates. The expression SUM(t1.b) is evaluated
  for each group defined in the main query, not for groups of the subquery.

  The problem of finding the query where to aggregate a particular
  set function is not so simple as it seems to be.

  In the query: 
    SELECT t1.a FROM t1 GROUP BY t1.a
     HAVING t1.a > ALL(SELECT t2.c FROM t2 GROUP BY t2.c
                         HAVING SUM(t1.a) < t2.c)
  the set function can be evaluated for both outer and inner selects.
  If we evaluate SUM(t1.a) for the outer query then we get the value of t1.a
  multiplied by the cardinality of a group in table t1. In this case 
  in each correlated subquery SUM(t1.a) is used as a constant. But we also
  can evaluate SUM(t1.a) for the inner query. In this case t1.a will be a
  constant for each correlated subquery and summation is performed
  for each group of table t2.
  (Here it makes sense to remind that the query
    SELECT c FROM t GROUP BY a HAVING SUM(1) < a 
  is quite legal in our SQL).

  So depending on what query we assign the set function to we
  can get different result sets.

  The general rule to detect the query where a set function is to be
  evaluated can be formulated as follows.
  Consider a set function S(E) where E is an expression with occurrences
  of column references C1, ..., CN. Resolve these column references against
  subqueries that contain the set function S(E). Let Q be the innermost
  subquery of those subqueries. (It should be noted here that S(E)
  in no way can be evaluated in the subquery embedding the subquery Q,
  otherwise S(E) would refer to at least one unbound column reference)
  If S(E) is used in a construct of Q where set functions are allowed then
  we evaluate S(E) in Q.
  Otherwise we look for a innermost subquery containing S(E) of those where
  usage of S(E) is allowed.

  Let's demonstrate how this rule is applied to the following queries.

  1. SELECT t1.a FROM t1 GROUP BY t1.a
       HAVING t1.a > ALL(SELECT t2.b FROM t2 GROUP BY t2.b
                           HAVING t2.b > ALL(SELECT t3.c FROM t3 GROUP BY t3.c
                                                HAVING SUM(t1.a+t2.b) < t3.c))
  For this query the set function SUM(t1.a+t2.b) depends on t1.a and t2.b
  with t1.a defined in the outermost query, and t2.b defined for its
  subquery. The set function is in the HAVING clause of the subquery and can
  be evaluated in this subquery.

  2. SELECT t1.a FROM t1 GROUP BY t1.a
       HAVING t1.a > ALL(SELECT t2.b FROM t2
                           WHERE t2.b > ALL (SELECT t3.c FROM t3 GROUP BY t3.c
                                               HAVING SUM(t1.a+t2.b) < t3.c))
  Here the set function SUM(t1.a+t2.b)is in the WHERE clause of the second
  subquery - the most upper subquery where t1.a and t2.b are defined.
  If we evaluate the function in this subquery we violate the context rules.
  So we evaluate the function in the third subquery (over table t3) where it
  is used under the HAVING clause.

  3. SELECT t1.a FROM t1 GROUP BY t1.a
       HAVING t1.a > ALL(SELECT t2.b FROM t2
                           WHERE t2.b > ALL (SELECT t3.c FROM t3 
                                               WHERE SUM(t1.a+t2.b) < t3.c))
  In this query evaluation of SUM(t1.a+t2.b) is not legal neither in the second
  nor in the third subqueries. So this query is invalid.

  Mostly set functions cannot be nested. In the query
    SELECT t1.a from t1 GROUP BY t1.a HAVING AVG(SUM(t1.b)) > 20
  the expression SUM(b) is not acceptable, though it is under a HAVING clause.
  Yet it is acceptable in the query:
    SELECT t.1 FROM t1 GROUP BY t1.a HAVING SUM(t1.b) > 20.

  An argument of a set function does not have to be a reference to a table
  column as we saw it in examples above. This can be a more complex expression
    SELECT t1.a FROM t1 GROUP BY t1.a HAVING SUM(t1.b+1) > 20.
  The expression SUM(t1.b+1) has a very clear semantics in this context:
  we sum up the values of t1.b+1 where t1.b varies for all values within a
  group of rows that contain the same t1.a value.

  A set function for an outer query yields a constant within a subquery. So
  the semantics of the query
    SELECT t1.a FROM t1 GROUP BY t1.a
      HAVING t1.a IN (SELECT t2.c FROM t2 GROUP BY t2.c
                        HAVING AVG(t2.c+SUM(t1.b)) > 20)
  is still clear. For a group of the rows with the same t1.a values we
  calculate the value of SUM(t1.b). This value 's' is substituted in the
  the subquery:
    SELECT t2.c FROM t2 GROUP BY t2.c HAVING AVG(t2.c+s)
  than returns some result set.

  By the same reason the following query with a subquery 
    SELECT t1.a FROM t1 GROUP BY t1.a
      HAVING t1.a IN (SELECT t2.c FROM t2 GROUP BY t2.c
                        HAVING AVG(SUM(t1.b)) > 20)
  is also acceptable.

 IMPLEMENTATION NOTES

  Three methods were added to the class to check the constraints specified
  in the previous section. These methods utilize several new members.

  The field 'nest_level' contains the number of the level for the subquery
  containing the set function. The main SELECT is of level 0, its subqueries
  are of levels 1, the subqueries of the latter are of level 2 and so on.

  The field 'aggr_level' is to contain the nest level of the subquery
  where the set function is aggregated.

  The field 'max_arg_level' is for the maximun of the nest levels of the
  unbound column references occurred in the set function. A column reference
  is unbound  within a set function if it is not bound by any subquery
  used as a subexpression in this function. A column reference is bound by
  a subquery if it is a reference to the column by which the aggregation
  of some set function that is used in the subquery is calculated.
  For the set function used in the query
    SELECT t1.a FROM t1 GROUP BY t1.a
      HAVING t1.a > ALL(SELECT t2.b FROM t2 GROUP BY t2.b
                          HAVING t2.b > ALL(SELECT t3.c FROM t3 GROUP BY t3.c
                                              HAVING SUM(t1.a+t2.b) < t3.c))
  the value of max_arg_level is equal to 1 since t1.a is bound in the main
  query, and t2.b is bound by the first subquery whose nest level is 1.
  Obviously a set function cannot be aggregated in the subquery whose
  nest level is less than max_arg_level. (Yet it can be aggregated in the
  subqueries whose nest level is greater than max_arg_level.)
  In the query
    SELECT t.a FROM t1 HAVING AVG(t1.a+(SELECT MIN(t2.c) FROM t2))
  the value of the max_arg_level for the AVG set function is 0 since
  the reference t2.c is bound in the subquery.

  The field 'max_sum_func_level' is to contain the maximum of the
  nest levels of the set functions that are used as subexpressions of
  the arguments of the given set function, but not aggregated in any
  subquery within this set function. A nested set function s1 can be
  used within set function s0 only if s1.max_sum_func_level <
  s0.max_sum_func_level. Set function s1 is considered as nested
  for set function s0 if s1 is not calculated in any subquery
  within s0.

  A set function that is used as a subexpression in an argument of another
  set function refers to the latter via the field 'in_sum_func'.

  The condition imposed on the usage of set functions are checked when
  we traverse query subexpressions with the help of the recursive method
  fix_fields. When we apply this method to an object of the class
  Item_sum, first, on the descent, we call the method init_sum_func_check
  that initialize members used at checking. Then, on the ascent, we
  call the method check_sum_func that validates the set function usage
  and reports an error if it is illegal.
  The method register_sum_func serves to link the items for the set functions
  that are aggregated in the embedding (sub)queries. Circular chains of such
  functions are attached to the corresponding st_select_lex structures
  through the field inner_sum_func_list.

  Exploiting the fact that the members mentioned above are used in one
  recursive function we could have allocated them on the thread stack.
  Yet we don't do it now.
  
  We assume that the nesting level of subquries does not exceed 127.
  TODO: to catch queries where the limit is exceeded to make the
  code clean here.  
    
*/

class Item_sum :public Item_result_field
{
  friend class Aggregator_distinct;
  friend class Aggregator_simple;

protected:
  /**
    Aggregator class instance. Not set initially. Allocated only after
    it is determined if the incoming data are already distinct.
  */
  Aggregator *aggr;

private:
  /**
    Used in making ROLLUP. Set for the ROLLUP copies of the original
    Item_sum and passed to create_tmp_field() to cause it to work
    over the temp table buffer that is referenced by
    Item_result_field::result_field.
  */
  bool force_copy_fields;

  /**
    Indicates how the aggregate function was specified by the parser :
    1 if it was written as AGGREGATE(DISTINCT),
    0 if it was AGGREGATE()
  */
  bool with_distinct;

public:

  bool has_force_copy_fields() const { return force_copy_fields; }
  bool has_with_distinct()     const { return with_distinct; }

  enum Sumfunctype
  { COUNT_FUNC, COUNT_DISTINCT_FUNC, SUM_FUNC, SUM_DISTINCT_FUNC, AVG_FUNC,
    AVG_DISTINCT_FUNC, MIN_FUNC, MAX_FUNC, STD_FUNC,
    VARIANCE_FUNC, SUM_BIT_FUNC, UDF_SUM_FUNC, GROUP_CONCAT_FUNC
  };

  Item **ref_by; /* pointer to a ref to the object used to register it */
  Item_sum *next; /* next in the circular chain of registered objects  */
  Item_sum *in_sum_func;  /* embedding set function if any */ 
  st_select_lex * aggr_sel; /* select where the function is aggregated       */ 
  int8 nest_level;        /* number of the nesting level of the set function */
  int8 aggr_level;        /* nesting level of the aggregating subquery       */
  int8 max_arg_level;     /* max level of unbound column references          */
  int8 max_sum_func_level;/* max level of aggregation for embedded functions */
  bool quick_group;			/* If incremental update of fields */
  /*
    This list is used by the check for mixing non aggregated fields and
    sum functions in the ONLY_FULL_GROUP_BY_MODE. We save all outer fields
    directly or indirectly used under this function it as it's unclear
    at the moment of fixing outer field whether it's aggregated or not.
  */
  List<Item_field> outer_fields;

protected:  
  uint arg_count;
  Item **args, *tmp_args[2];
  /* 
    Copy of the arguments list to hold the original set of arguments.
    Used in EXPLAIN EXTENDED instead of the current argument list because 
    the current argument list can be altered by usage of temporary tables.
  */
  Item **orig_args, *tmp_orig_args[2];
  table_map used_tables_cache;
  bool forced_const;
  static ulonglong ram_limitation(THD *thd);

public:  

  void mark_as_sum_func();
  Item_sum() :next(NULL), quick_group(1), arg_count(0), forced_const(FALSE)
  {
    mark_as_sum_func();
    init_aggregator();
  }
  Item_sum(Item *a) :next(NULL), quick_group(1), arg_count(1), args(tmp_args),
    orig_args(tmp_orig_args), forced_const(FALSE)
  {
    args[0]=a;
    mark_as_sum_func();
    init_aggregator();
  }
  Item_sum( Item *a, Item *b ) :next(NULL), quick_group(1), arg_count(2), args(tmp_args),
    orig_args(tmp_orig_args), forced_const(FALSE)
  {
    args[0]=a; args[1]=b;
    mark_as_sum_func();
    init_aggregator();
  }
  Item_sum(List<Item> &list);
  //Copy constructor, need to perform subselects with temporary tables
  Item_sum(THD *thd, Item_sum *item);
  enum Type type() const { return SUM_FUNC_ITEM; }
  virtual enum Sumfunctype sum_func () const=0;

  virtual bool keep_field_type(void) const { return 0; }
  table_map used_tables() const { return used_tables_cache; }
  bool is_null() { return null_value; }
  void make_const () 
  { 
    used_tables_cache= 0; 
    forced_const= TRUE; 
  }
  virtual bool const_item() const { return forced_const; }
  virtual void print(String *str, enum_query_type query_type);

  virtual void make_unique() { force_copy_fields= TRUE; }
  bool walk(Item_processor processor, bool walk_subquery, uchar *argument);
  bool check_sum_func(THD *thd, Item **ref);
  bool register_sum_func(THD *thd, Item **ref);
  st_select_lex *depended_from() 
    { return (nest_level == aggr_level ? 0 : aggr_sel); }

  double val_real() {return 0.0;}
  longlong val_int() {return 0;}
  my_decimal *val_decimal(my_decimal *) {return NULL;}
  String *val_str(String *) {return NULL;}

  Item *get_arg(uint i) { return args[i]; }
  Item *set_arg(uint i, THD *thd, Item *new_val);
  uint get_arg_count() const { return arg_count; }

  /* Initialization of distinct related members */
  void init_aggregator()
  {
    aggr= NULL;
    with_distinct= FALSE;
    force_copy_fields= FALSE;
  }

  /* stores the declared DISTINCT flag (from the parser) */
  void set_distinct(bool distinct)
  {
    with_distinct= distinct;
    quick_group= with_distinct ? 0 : 1;
  }

  /*
    Set the type of aggregation : DISTINCT or not.

    May be called multiple times.
  */

  int set_aggregator(Aggregator::Aggregator_type aggregator);

  virtual bool setup(THD *thd) { return false; }
};



/**
 The distinct aggregator. 
 Implements AGGFN (DISTINCT ..)
 Collects all the data into an Unique (similarly to what Item_sum_distinct 
 does currently) and then (if applicable) iterates over the list of 
 unique values and pumps them back into its object
*/

class Aggregator_distinct : public Aggregator
{
  friend class Item_sum_sum;


  enum Const_distinct{
    NOT_CONST= 0,
    /**
      Set to true if the result is known to be always NULL.
      If set deactivates creation and usage of the temporary table (in the
      'table' member) and the Unique instance (in the 'tree' member) as well as
      the calculation of the final value on the first call to
      Item_[sum|avg|count]::val_xxx().
     */
    CONST_NULL,
    /**
      Set to true if count distinct is on only const items. Distinct on a const
      value will always be the constant itself. And count distinct of the same
      would always be 1. Similar to CONST_NULL, it avoids creation of temporary
      table and the Unique instance.
     */
    CONST_NOT_NULL
  } const_distinct;

  /**
    When feeding back the data in endup() from Unique/temp table back to
    Item_sum::add() methods we must read the data from Unique (and not
    recalculate the functions that are given as arguments to the aggregate
    function.
    This flag is to tell the arg_*() methods to take the data from the Unique
    instead of calling the relevant val_..() method.
  */
  bool use_distinct_values;

public:
  Aggregator_distinct (Item_sum *sum) :
    Aggregator(sum),
    const_distinct(NOT_CONST), use_distinct_values(false) {}
  virtual ~Aggregator_distinct ();
  Aggregator_type Aggrtype() { return DISTINCT_AGGREGATOR; }
};


/**
  The pass-through aggregator. 
  Implements AGGFN (DISTINCT ..) by knowing it gets distinct data on input. 
  So it just pumps them back to the Item_sum descendant class.
*/
class Aggregator_simple : public Aggregator
{
public:

  Aggregator_simple (Item_sum *sum) :
    Aggregator(sum) {}
  Aggregator_type Aggrtype() { return Aggregator::SIMPLE_AGGREGATOR; }

  bool setup(THD * thd) { return item_sum->setup(thd); }
};


class Item_sum_num :public Item_sum
{
protected:
  /*
   val_xxx() functions may be called several times during the execution of a 
   query. Derived classes that require extensive calculation in val_xxx()
   maintain cache of aggregate value. This variable governs the validity of 
   that cache.
  */
  bool is_evaluated;
public:
  Item_sum_num() :Item_sum(),is_evaluated(FALSE) {}
  Item_sum_num(Item *item_par) 
    :Item_sum(item_par), is_evaluated(FALSE) {}
  Item_sum_num(Item *a, Item* b) :Item_sum(a,b),is_evaluated(FALSE) {}
  Item_sum_num(List<Item> &list) 
    :Item_sum(list), is_evaluated(FALSE) {}
  Item_sum_num(THD *thd, Item_sum_num *item) 
    :Item_sum(thd, item),is_evaluated(item->is_evaluated) {}
};


class Item_sum_int :public Item_sum_num
{
public:
  Item_sum_int(Item *item_par) :Item_sum_num(item_par) {}
  Item_sum_int(List<Item> &list) :Item_sum_num(list) {}
  Item_sum_int(THD *thd, Item_sum_int *item) :Item_sum_num(thd, item) {}
  enum Item_result result_type () const { return INT_RESULT; }
};


class Item_sum_sum :public Item_sum_num
{
protected:
  Item_result hybrid_type;
  double sum;
  my_decimal dec_buffs[2];
  uint curr_dec_buff;

public:
  Item_sum_sum(Item *item_par, bool distinct) :Item_sum_num(item_par) 
  {
    set_distinct(distinct);
  }
  Item_sum_sum(THD *thd, Item_sum_sum *item);
  enum Sumfunctype sum_func () const 
  { 
    return has_with_distinct() ? SUM_DISTINCT_FUNC : SUM_FUNC; 
  }
  enum Item_result result_type () const { return hybrid_type; }
  const char *func_name() const 
  { 
    return has_with_distinct() ? "sum(distinct " : "sum("; 
  }
};


class Item_sum_count :public Item_sum_int
{
  longlong count;

  friend class Aggregator_distinct;

  public:
  Item_sum_count(Item *item_par)
    :Item_sum_int(item_par),count(0)
  {}

  /**
    Constructs an instance for COUNT(DISTINCT)

    @param list  a list of the arguments to the aggregate function

    This constructor is called by the parser only for COUNT (DISTINCT).
  */

  Item_sum_count(List<Item> &list)
    :Item_sum_int(list),count(0)
  {
    set_distinct(TRUE);
  }
  Item_sum_count(THD *thd, Item_sum_count *item)
    :Item_sum_int(thd, item), count(item->count)
  {}
  enum Sumfunctype sum_func () const 
  { 
    return has_with_distinct() ? COUNT_DISTINCT_FUNC : COUNT_FUNC; 
  }
  void make_const(longlong count_arg) 
  { 
    count=count_arg;
    Item_sum::make_const();
  }
  const char *func_name() const 
  { 
    return has_with_distinct() ? "count(distinct " : "count(";
  }
};


/* Item to get the value of a stored sum function */

class Item_sum_avg;

/**
  Common abstract class for:
    Item_avg_field
    Item_variance_field
*/
class Item_sum_num_field: public Item_result_field
{
protected:
  Item_result hybrid_type;
public:
  enum_field_types field_type() const
  {
    return hybrid_type == DECIMAL_RESULT ?
      MYSQL_TYPE_NEWDECIMAL : MYSQL_TYPE_DOUBLE;
  }
  enum Item_result result_type () const { return hybrid_type; }
};


class Item_avg_field :public Item_sum_num_field
{
public:
  uint f_precision, f_scale, dec_bin_size;
  uint prec_increment;
  enum Type type() const { return FIELD_AVG_ITEM; }
  const char *func_name() const { DBUG_ASSERT(0); return "avg_field"; }
};


class Item_sum_avg :public Item_sum_sum
{
public:
  ulonglong count;
  uint prec_increment;
  uint f_precision, f_scale, dec_bin_size;
  Item_sum_avg(Item *item_par, bool distinct) 
    :Item_sum_sum(item_par, distinct), count(0) 
  {}
  Item_sum_avg(THD *thd, Item_sum_avg *item)
    :Item_sum_sum(thd, item), count(item->count),
    prec_increment(item->prec_increment) {}

  enum Sumfunctype sum_func () const 
  {
    return has_with_distinct() ? AVG_DISTINCT_FUNC : AVG_FUNC;
  }
  const char *func_name() const 
  { 
    return has_with_distinct() ? "avg(distinct " : "avg("; 
  }
};

class Item_sum_variance;

class Item_variance_field :public Item_sum_num_field
{
protected:
  uint f_precision0, f_scale0;
  uint f_precision1, f_scale1;
  uint dec_bin_size0, dec_bin_size1;
  uint sample;
  uint prec_increment;
public:
  enum Type type() const {return FIELD_VARIANCE_ITEM; }
  double val_real();
  String *val_str(String *str)
  { return val_string_from_real(str); }
  my_decimal *val_decimal(my_decimal *dec_buf)
  { return val_decimal_from_real(dec_buf); }
  const char *func_name() const { DBUG_ASSERT(0); return "variance_field"; }
};


/*
  variance(a) =

  =  sum (ai - avg(a))^2 / count(a) )
  =  sum (ai^2 - 2*ai*avg(a) + avg(a)^2) / count(a)
  =  (sum(ai^2) - sum(2*ai*avg(a)) + sum(avg(a)^2))/count(a) = 
  =  (sum(ai^2) - 2*avg(a)*sum(a) + count(a)*avg(a)^2)/count(a) = 
  =  (sum(ai^2) - 2*sum(a)*sum(a)/count(a) + count(a)*sum(a)^2/count(a)^2 )/count(a) = 
  =  (sum(ai^2) - 2*sum(a)^2/count(a) + sum(a)^2/count(a) )/count(a) = 
  =  (sum(ai^2) - sum(a)^2/count(a))/count(a)

But, this falls prey to catastrophic cancellation.  Instead, use the recurrence formulas

  M_{1} = x_{1}, ~ M_{k} = M_{k-1} + (x_{k} - M_{k-1}) / k newline 
  S_{1} = 0, ~ S_{k} = S_{k-1} + (x_{k} - M_{k-1}) times (x_{k} - M_{k}) newline
  for 2 <= k <= n newline
  ital variance = S_{n} / (n-1)

*/

class Item_sum_variance : public Item_sum_num
{
public:
  Item_result hybrid_type;
  int cur_dec;
  double recurrence_m, recurrence_s;    /* Used in recurrence relation. */
  ulonglong count;
  uint f_precision0, f_scale0;
  uint f_precision1, f_scale1;
  uint dec_bin_size0, dec_bin_size1;
  uint sample;
  uint prec_increment;

  Item_sum_variance(Item *item_par, uint sample_arg) :Item_sum_num(item_par),
    hybrid_type(REAL_RESULT), count(0), sample(sample_arg)
    {}
  Item_sum_variance(THD *thd, Item_sum_variance *item);
  enum Sumfunctype sum_func () const { return VARIANCE_FUNC; }
  const char *func_name() const
    { return sample ? "var_samp(" : "variance("; }
  double val_real() {return 0.0;}
  enum Item_result result_type () const { return REAL_RESULT; }
};

class Item_sum_std;

class Item_std_field :public Item_variance_field
{
public:
  Item_std_field(Item_sum_std *item);
  enum Type type() const { return FIELD_STD_ITEM; }
  double val_real();
  my_decimal *val_decimal(my_decimal *);
  enum Item_result result_type () const { return REAL_RESULT; }
  enum_field_types field_type() const { return MYSQL_TYPE_DOUBLE;}
  const char *func_name() const { DBUG_ASSERT(0); return "std_field"; }
};

/*
   standard_deviation(a) = sqrt(variance(a))
*/

class Item_sum_std :public Item_sum_variance
{
  public:
  Item_sum_std(Item *item_par, uint sample_arg)
    :Item_sum_variance(item_par, sample_arg) {}
  Item_sum_std(THD *thd, Item_sum_std *item)
    :Item_sum_variance(thd, item)
    {}
  enum Sumfunctype sum_func () const { return STD_FUNC; }
  const char *func_name() const { return "std("; }
  enum Item_result result_type () const { return REAL_RESULT; }
  enum_field_types field_type() const { return MYSQL_TYPE_DOUBLE;}
};

// This class is a string or number function depending on num_func
class Arg_comparator;
class Item_sum_hybrid :public Item_sum
{
protected:
  Arg_comparator *cmp;
  Item_result hybrid_type;
  enum_field_types hybrid_field_type;
  int cmp_sign;
  bool was_values;  // Set if we have found at least one row (for max/min only)

  public:
  Item_sum_hybrid(Item *item_par,int sign)
    :Item_sum(item_par), cmp(0),
    hybrid_type(INT_RESULT), hybrid_field_type(MYSQL_TYPE_LONGLONG),
    cmp_sign(sign), was_values(TRUE)
  { collation.set(&my_charset_bin); }
  Item_sum_hybrid(THD *thd, Item_sum_hybrid *item)
    :Item_sum(thd, item),
    hybrid_type(item->hybrid_type), hybrid_field_type(item->hybrid_field_type),
    cmp_sign(item->cmp_sign), was_values(item->was_values)
  { }
  bool keep_field_type(void) const { return 1; }
  enum Item_result result_type () const { return hybrid_type; }
  enum enum_field_types field_type() const { return hybrid_field_type; }
  bool any_value() { return was_values; }
};


class Item_sum_min :public Item_sum_hybrid
{
public:
  Item_sum_min(Item *item_par) :Item_sum_hybrid(item_par,1) {}
  Item_sum_min(THD *thd, Item_sum_min *item) :Item_sum_hybrid(thd, item) {}
  enum Sumfunctype sum_func () const {return MIN_FUNC;}

  const char *func_name() const { return "min("; }
};


class Item_sum_max :public Item_sum_hybrid
{
public:
  Item_sum_max(Item *item_par) :Item_sum_hybrid(item_par,-1) {}
  Item_sum_max(THD *thd, Item_sum_max *item) :Item_sum_hybrid(thd, item) {}
  enum Sumfunctype sum_func () const {return MAX_FUNC;}

  const char *func_name() const { return "max("; }
};


class Item_sum_bit :public Item_sum_int
{
protected:
  ulonglong reset_bits,bits;

public:
  Item_sum_bit(Item *item_par,ulonglong reset_arg)
    :Item_sum_int(item_par),reset_bits(reset_arg),bits(reset_arg) {}
  Item_sum_bit(THD *thd, Item_sum_bit *item):
    Item_sum_int(thd, item), reset_bits(item->reset_bits), bits(item->bits) {}
  enum Sumfunctype sum_func () const {return SUM_BIT_FUNC;}
};


class Item_sum_or :public Item_sum_bit
{
public:
  Item_sum_or(Item *item_par) :Item_sum_bit(item_par,LL(0)) {}
  Item_sum_or(THD *thd, Item_sum_or *item) :Item_sum_bit(thd, item) {}
  const char *func_name() const { return "bit_or("; }
};


class Item_sum_and :public Item_sum_bit
{
  public:
  Item_sum_and(Item *item_par) :Item_sum_bit(item_par, ULONGLONG_MAX) {}
  Item_sum_and(THD *thd, Item_sum_and *item) :Item_sum_bit(thd, item) {}
  const char *func_name() const { return "bit_and("; }
};

class Item_sum_xor :public Item_sum_bit
{
  public:
  Item_sum_xor(Item *item_par) :Item_sum_bit(item_par,LL(0)) {}
  Item_sum_xor(THD *thd, Item_sum_xor *item) :Item_sum_bit(thd, item) {}
  const char *func_name() const { return "bit_xor("; }
};


/*
  User defined aggregates
*/

#ifdef HAVE_DLOPEN

class Item_udf_sum : public Item_sum
{
protected:
  udf_handler udf;

public:
  Item_udf_sum(udf_func *udf_arg)
    :Item_sum(), udf(udf_arg)
  { quick_group=0; }
  Item_udf_sum(udf_func *udf_arg, List<Item> &list)
    :Item_sum(list), udf(udf_arg)
  { quick_group=0;}
  Item_udf_sum(THD *thd, Item_udf_sum *item)
    :Item_sum(thd, item), udf(item->udf)
  { udf.not_original= TRUE; }
  const char *func_name() const { return udf.name(); }
  enum Sumfunctype sum_func () const { return UDF_SUM_FUNC; }
  virtual void print(String *str, enum_query_type query_type);
};


class Item_sum_udf_float :public Item_udf_sum
{
 public:
  Item_sum_udf_float(udf_func *udf_arg)
    :Item_udf_sum(udf_arg) {}
  Item_sum_udf_float(udf_func *udf_arg, List<Item> &list)
    :Item_udf_sum(udf_arg, list) {}
  Item_sum_udf_float(THD *thd, Item_sum_udf_float *item)
    :Item_udf_sum(thd, item) {}
  longlong val_int()
  {
    DBUG_ASSERT(fixed == 1);
    return (longlong) rint(Item_sum_udf_float::val_real());
  }
  double val_real();
  String *val_str(String*str);
  my_decimal *val_decimal(my_decimal *);
};


class Item_sum_udf_int :public Item_udf_sum
{
public:
  Item_sum_udf_int(udf_func *udf_arg)
    :Item_udf_sum(udf_arg) {}
  Item_sum_udf_int(udf_func *udf_arg, List<Item> &list)
    :Item_udf_sum(udf_arg, list) {}
  Item_sum_udf_int(THD *thd, Item_sum_udf_int *item)
    :Item_udf_sum(thd, item) {}
  longlong val_int();
  double val_real()
    { DBUG_ASSERT(fixed == 1); return (double) Item_sum_udf_int::val_int(); }
  String *val_str(String*str);
  my_decimal *val_decimal(my_decimal *);
  enum Item_result result_type () const { return INT_RESULT; }
};


class Item_sum_udf_str :public Item_udf_sum
{
public:
  Item_sum_udf_str(udf_func *udf_arg)
    :Item_udf_sum(udf_arg) {}
  Item_sum_udf_str(udf_func *udf_arg, List<Item> &list)
    :Item_udf_sum(udf_arg,list) {}
  Item_sum_udf_str(THD *thd, Item_sum_udf_str *item)
    :Item_udf_sum(thd, item) {}
  String *val_str(String *);
  double val_real()
  {
    int err_not_used;
    char *end_not_used;
    String *res;
    res=val_str(&str_value);
    return res ? my_strntod(res->charset(),(char*) res->ptr(),res->length(),
			    &end_not_used, &err_not_used) : 0.0;
  }
  longlong val_int()
  {
    int err_not_used;
    char *end;
    String *res;
    const CHARSET_INFO *cs;

    if (!(res= val_str(&str_value)))
      return 0;                                 /* Null value */
    cs= res->charset();
    end= (char*) res->ptr()+res->length();
    return cs->cset->strtoll10(cs, res->ptr(), &end, &err_not_used);
  }
  my_decimal *val_decimal(my_decimal *dec);
  enum Item_result result_type () const { return STRING_RESULT; }
};


class Item_sum_udf_decimal :public Item_udf_sum
{
public:
  Item_sum_udf_decimal(udf_func *udf_arg)
    :Item_udf_sum(udf_arg) {}
  Item_sum_udf_decimal(udf_func *udf_arg, List<Item> &list)
    :Item_udf_sum(udf_arg, list) {}
  Item_sum_udf_decimal(THD *thd, Item_sum_udf_decimal *item)
    :Item_udf_sum(thd, item) {}
  String *val_str(String *);
  double val_real();
  longlong val_int();
  my_decimal *val_decimal(my_decimal *);
  enum Item_result result_type () const { return DECIMAL_RESULT; }
};

#else /* Dummy functions to get sql_yacc.cc compiled */

class Item_sum_udf_float :public Item_sum_num
{
 public:
  Item_sum_udf_float(udf_func *udf_arg)
    :Item_sum_num() {}
  Item_sum_udf_float(udf_func *udf_arg, List<Item> &list) :Item_sum_num() {}
  Item_sum_udf_float(THD *thd, Item_sum_udf_float *item)
    :Item_sum_num(thd, item) {}
  enum Sumfunctype sum_func () const { return UDF_SUM_FUNC; }
  double val_real() { DBUG_ASSERT(fixed == 1); return 0.0; }
  void clear() {}
  bool add() { return 0; }  
  void update_field() {}
};


class Item_sum_udf_int :public Item_sum_num
{
public:
  Item_sum_udf_int(udf_func *udf_arg)
    :Item_sum_num() {}
  Item_sum_udf_int(udf_func *udf_arg, List<Item> &list) :Item_sum_num() {}
  Item_sum_udf_int(THD *thd, Item_sum_udf_int *item)
    :Item_sum_num(thd, item) {}
  enum Sumfunctype sum_func () const { return UDF_SUM_FUNC; }
  longlong val_int() { DBUG_ASSERT(fixed == 1); return 0; }
  double val_real() { DBUG_ASSERT(fixed == 1); return 0; }
  void clear() {}
  bool add() { return 0; }  
  void update_field() {}
};


class Item_sum_udf_decimal :public Item_sum_num
{
 public:
  Item_sum_udf_decimal(udf_func *udf_arg)
    :Item_sum_num() {}
  Item_sum_udf_decimal(udf_func *udf_arg, List<Item> &list)
    :Item_sum_num() {}
  Item_sum_udf_decimal(THD *thd, Item_sum_udf_float *item)
    :Item_sum_num(thd, item) {}
  enum Sumfunctype sum_func () const { return UDF_SUM_FUNC; }
  double val_real() { DBUG_ASSERT(fixed == 1); return 0.0; }
  my_decimal *val_decimal(my_decimal *) { DBUG_ASSERT(fixed == 1); return 0; }
  void clear() {}
  bool add() { return 0; }
  void update_field() {}
};


class Item_sum_udf_str :public Item_sum_num
{
public:
  Item_sum_udf_str(udf_func *udf_arg)
    :Item_sum_num() {}
  Item_sum_udf_str(udf_func *udf_arg, List<Item> &list)
    :Item_sum_num() {}
  Item_sum_udf_str(THD *thd, Item_sum_udf_str *item)
    :Item_sum_num(thd, item) {}
  String *val_str(String *)
    { DBUG_ASSERT(fixed == 1); null_value=1; return 0; }
  double val_real() { DBUG_ASSERT(fixed == 1); null_value=1; return 0.0; }
  longlong val_int() { DBUG_ASSERT(fixed == 1); null_value=1; return 0; }
  enum Item_result result_type () const { return STRING_RESULT; }
  void fix_length_and_dec() { maybe_null=1; max_length=0; }
  enum Sumfunctype sum_func () const { return UDF_SUM_FUNC; }
  void clear() {}
  bool add() { return 0; }  
  void update_field() {}
};

#endif /* HAVE_DLOPEN */

C_MODE_START
int group_concat_key_cmp_with_distinct(const void* arg, const void* key1,
                                       const void* key2);
int group_concat_key_cmp_with_order(const void* arg, const void* key1,
                                    const void* key2);
int dump_leaf_key(void* key_arg,
                  element_count count __attribute__((unused)),
                  void* item_arg);
C_MODE_END

class Item_func_group_concat : public Item_sum
{
  String result;
  String *separator;
  TREE tree_base;
  TREE *tree;

  /**
     If DISTINCT is used with this GROUP_CONCAT, this member is used to filter
     out duplicates. 
     @see Item_func_group_concat::setup
     @see Item_func_group_concat::add
     @see Item_func_group_concat::clear
   */
  ORDER **order;
  Name_resolution_context *context;
  /** The number of ORDER BY items. */
  uint arg_count_order;
  /** The number of selected items, aka the expr list. */
  uint arg_count_field;
  uint row_count;
  bool distinct;
  bool warning_for_row;
  bool always_null;
  bool force_copy_fields;
  bool no_appended;
  /*
    Following is 0 normal object and pointer to original one for copy
    (to correctly free resources)
  */
  Item_func_group_concat *original;

public:
  Item_func_group_concat(Name_resolution_context *context_arg,
                         bool is_distinct, List<Item> *is_select,
                         const SQL_I_List<ORDER> &is_order, String *is_separator);

  Item_func_group_concat(THD *thd, Item_func_group_concat *item);
  ~Item_func_group_concat();

  enum Sumfunctype sum_func () const {return GROUP_CONCAT_FUNC;}
  const char *func_name() const { return "group_concat"; }
  virtual Item_result result_type () const { return STRING_RESULT; }
  enum_field_types field_type() const
  {
    if (max_length/collation.collation->mbmaxlen > CONVERT_IF_BIGGER_TO_BLOB )
      return MYSQL_TYPE_BLOB;
    else
      return MYSQL_TYPE_VARCHAR;
  }
  double val_real() {return 0.0;}
  longlong val_int() {return 0;}
  my_decimal *val_decimal(my_decimal *decimal_value) {return NULL;}
  String* val_str(String* str) {return NULL;}
  virtual void print(String *str, enum_query_type query_type);
  virtual bool change_context_processor(uchar *cntx)
    { context= (Name_resolution_context *)cntx; return FALSE; }
};

#endif /* ITEM_SUM_INCLUDED */
