#ifndef ITEM_SUBSELECT_INCLUDED
#define ITEM_SUBSELECT_INCLUDED

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

/* subselect Item */

class st_select_lex;
class st_select_lex_unit;
class JOIN;
class select_result_interceptor;
class subselect_engine;
class subselect_hash_sj_engine;
class Item_bool_func2;
class Cached_item;
class Comp_creator;

typedef class st_select_lex SELECT_LEX;

/**
  Convenience typedef used in this file, and further used by any files
  including this file.
*/
typedef Comp_creator* (*chooser_compare_func_creator)(bool invert);

/* base class for subselects */

class Item_subselect :public Item_result_field
{
private:
  bool value_assigned; /* value already assigned to subselect */
  /**
      Whether or not execution of this subselect has been traced by
      optimizer tracing already. If optimizer trace option
      REPEATED_SUBSELECT is disabled, this is used to disable tracing
      after the first one.
  */
  bool traced_before;
public:
  /* 
    Used inside Item_subselect::fix_fields() according to this scenario:
      > Item_subselect::fix_fields
        > engine->prepare
          > child_join->prepare
            (Here we realize we need to do the rewrite and set
             substitution= some new Item, eg. Item_in_optimizer )
          < child_join->prepare
        < engine->prepare
        *ref= substitution;
      < Item_subselect::fix_fields
  */
  Item *substitution;
public:
  /* unit of subquery */
  st_select_lex_unit *unit;
  /**
     If !=INT_MIN: this Item is in the condition attached to the JOIN_TAB
     having this index in the parent JOIN.
  */
  int in_cond_of_tab;

protected:
  /* cache of used external tables */
  table_map used_tables_cache;
  /* allowed number of columns (1 for single value subqueries) */
  uint max_columns;
  /* where subquery is placed */
  enum_parsing_place parsing_place;
  /* work with 'substitution' */
  bool have_to_be_excluded;
  /* cache of constant state */
  bool const_item_cache;

public:

  enum trans_res {RES_OK, RES_REDUCE, RES_ERROR};
  enum subs_type {UNKNOWN_SUBS, SINGLEROW_SUBS,
		  EXISTS_SUBS, IN_SUBS, ALL_SUBS, ANY_SUBS};

  Item_subselect();

  virtual subs_type substype() { return UNKNOWN_SUBS; }

  /*
    We need this method, because some compilers do not allow 'this'
    pointer in constructor initialization list, but we need to pass a pointer
    to subselect Item class to select_result_interceptor's constructor.
  */
  virtual void init (st_select_lex *select_lex,
		     select_result_interceptor *result);
  longlong val_int() {return 0;}
  double val_real() {return 0.0;}
  String *val_str(String*) {return NULL;}
  my_decimal *val_decimal(my_decimal *) {return NULL;}
  bool val_bool() {return false;}

  ~Item_subselect();
  virtual void reset()
  {
    null_value= 1;
  }
  bool assigned() const { return value_assigned; }
  void assigned(bool a) { value_assigned= a; }
  enum Type type() const;
  bool is_null()
  {
    return null_value;
  }
  table_map used_tables() const;
  table_map not_null_tables() const { return 0; }
  bool const_item() const;
  virtual void print(String *str, enum_query_type query_type);

  enum_parsing_place place() { return parsing_place; }
  bool walk_join_condition(List<TABLE_LIST> *tables, Item_processor processor,
                           bool walk_subquery, uchar *argument);
  bool walk_body(Item_processor processor, bool walk_subquery, uchar *arg);
  bool walk(Item_processor processor, bool walk_subquery, uchar *arg);
  virtual bool explain_subquery_checker(uchar **arg);

  const char *func_name() const { DBUG_ASSERT(0); return "subselect"; }

  friend class select_result_interceptor;
  friend class Item_in_optimizer;;
};

/* single value subselect */

class Item_cache;
class Item_singlerow_subselect :public Item_subselect
{
protected:
  Item_cache *value, **row;
public:
  Item_singlerow_subselect(st_select_lex *select_lex);
  Item_singlerow_subselect() :
    Item_subselect(), value(0), row (0) {}

  subs_type substype() { return SINGLEROW_SUBS; }

  double val_real();
  longlong val_int ();
  String *val_str (String *);
  my_decimal *val_decimal(my_decimal *);
  bool val_bool();

  Item* element_index(uint i) { return reinterpret_cast<Item*>(row[i]); }
  Item** addr(uint i) { return (Item**)row + i; }
  bool null_inside();

  /**
    This method is used to implement a special case of semantic tree
    rewriting, mandated by a SQL:2003 exception in the specification.
    The only caller of this method is handle_sql2003_note184_exception(),
    see the code there for more details.
    Note that this method breaks the object internal integrity, by
    removing it's association with the corresponding SELECT_LEX,
    making this object orphan from the parse tree.
    No other method, beside the destructor, should be called on this
    object, as it is now invalid.
    @return the SELECT_LEX structure that was given in the constructor.
  */
  st_select_lex* invalidate_and_restore_select_lex();

  friend class select_singlerow_subselect;
};

/* used in static ALL/ANY optimization */
class select_max_min_finder_subselect;
class Item_maxmin_subselect :public Item_singlerow_subselect
{
protected:
  bool max;
  bool was_values;  // Set if we have found at least one row
public:
  Item_maxmin_subselect(THD *thd, Item_subselect *parent,
			st_select_lex *select_lex, bool max, bool ignore_nulls);
  virtual void print(String *str, enum_query_type query_type);
  bool any_value() { return was_values; }
  void register_value() { was_values= TRUE; }
  void reset_value_registration() { was_values= FALSE; }
};

/* exists subselect */

class Item_exists_subselect :public Item_subselect
{
protected:
  bool value; /* value of this item (boolean: exists/not-exists) */

public:
  /**
    The method chosen to execute the predicate, currently used for IN, =ANY
    and EXISTS predicates.
  */
  enum enum_exec_method {
    EXEC_UNSPECIFIED, ///< No execution method specified yet.
    EXEC_SEMI_JOIN,   ///< Predicate is converted to semi-join nest.
    /// IN was converted to correlated EXISTS, and this is a final decision.
    EXEC_EXISTS,
    /**
       Decision between EXEC_EXISTS and EXEC_MATERIALIZATION is not yet taken.
       IN was temporarily converted to correlated EXISTS.
       All descendants of Item_in_subselect must go through this method
       before they can reach EXEC_EXISTS.
    */
    EXEC_EXISTS_OR_MAT,
    /// Predicate executed via materialization, and this is a final decision.
    EXEC_MATERIALIZATION
  };
  enum_exec_method exec_method;
  /// Priority of this predicate in the convert-to-semi-join-nest process.
  int sj_convert_priority;
  /// True if this predicate is chosen for semi-join transformation
  bool sj_chosen;
  /**
    Used by subquery optimizations to keep track about where this subquery
    predicate is located, and whether it is a candidate for transformation.
      (TABLE_LIST*) 1   - the predicate is an AND-part of the WHERE
      join nest pointer - the predicate is an AND-part of ON expression
                          of a join nest
      NULL              - for all other locations. It also means that the
                          predicate is not a candidate for transformation.
    See also THD::emb_on_expr_nest.
  */
  TABLE_LIST *embedding_join_nest;

  Item_exists_subselect(st_select_lex *select_lex);
  Item_exists_subselect()
    :Item_subselect(), value(false), exec_method(EXEC_UNSPECIFIED),
     sj_convert_priority(0), sj_chosen(false), embedding_join_nest(NULL)
  {}
  virtual trans_res select_transformer(JOIN *join)
  {
    exec_method= EXEC_EXISTS;
    return RES_OK;
  }
  subs_type substype() { return EXISTS_SUBS; }
  virtual void reset() 
  {
    value= 0;
  }

  enum Item_result result_type() const { return INT_RESULT;}
  virtual void print(String *str, enum_query_type query_type);

  friend class select_exists_subselect;
  friend class subselect_indexsubquery_engine;
};


/**
  Representation of IN subquery predicates of the form
  "left_expr IN (SELECT ...)".

  @detail
  This class has: 
   - A "subquery execution engine" (as a subclass of Item_subselect) that allows
     it to evaluate subqueries. (and this class participates in execution by
     having was_null variable where part of execution result is stored.
   - Transformation methods (todo: more on this).

  This class is not used directly, it is "wrapped" into Item_in_optimizer
  which provides some small bits of subquery evaluation.
*/

class Item_in_subselect :public Item_exists_subselect
{
public:
  Item *left_expr;
protected:
  /*
    Cache of the left operand of the subquery predicate. Allocated in the
    runtime memory root, for each execution, thus need not be freed.
  */
  List<Cached_item> *left_expr_cache;
  bool left_expr_cache_filled; ///< Whether left_expr_cache holds a value
  /** The need for expr cache may be optimized away, @sa init_left_expr_cache. */
  bool need_expr_cache;
public:
  
  Item_func_not_all *upper_item; // point on NOT/NOP before ALL/SOME subquery

  /* 
    Location of the subquery predicate. It is either
     - pointer to join nest if the subquery predicate is in the ON expression
     - (TABLE_LIST*)1 if the predicate is in the WHERE.
  */
  TABLE_LIST *expr_join_nest;

  Item_in_subselect(Item * left_expr, st_select_lex *select_lex);
  Item_in_subselect()
    :Item_exists_subselect(), left_expr(NULL), left_expr_cache(NULL),
    left_expr_cache_filled(false), need_expr_cache(TRUE), upper_item(NULL)
  {}
  subs_type substype() { return IN_SUBS; }
  virtual void reset() 
  {
    value= 0;
  }
  bool walk(Item_processor processor, bool walk_subquery, uchar *arg);
  bool test_limit(st_select_lex_unit *unit);
  virtual void print(String *str, enum_query_type query_type);

  friend class Item_ref_null_helper;
  friend class Item_is_not_null_test;
  friend class Item_in_optimizer;
  friend class subselect_indexsubquery_engine;
  friend class subselect_hash_sj_engine;
};


/* ALL/ANY/SOME subselect */
class Item_allany_subselect :public Item_in_subselect
{
public:
  chooser_compare_func_creator func_creator;
  Comp_creator *func;
  bool all;

  Item_allany_subselect(Item * left_expr, chooser_compare_func_creator fc,
                        st_select_lex *select_lex, bool all);

  // only ALL subquery has upper not
  subs_type substype() { return all?ALL_SUBS:ANY_SUBS; }
  virtual void print(String *str, enum_query_type query_type);
};


#endif /* ITEM_SUBSELECT_INCLUDED */
