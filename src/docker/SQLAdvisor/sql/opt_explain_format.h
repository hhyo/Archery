/* Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.

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


#ifndef OPT_EXPLAIN_FORMAT_INCLUDED
#define OPT_EXPLAIN_FORMAT_INCLUDED

/** @file "EXPLAIN FORMAT=<format> <command>" 
*/


#include "sql_class.h"

struct st_join_table;


/**
  Names for different query parse tree parts
*/

enum Explain_context_enum
{
  CTX_NONE= 0, ///< Empty value
  CTX_MESSAGE, ///< "No tables used" messages etc.
  CTX_TABLE, ///< for single-table UPDATE/DELETE
  CTX_SELECT_LIST, ///< SELECT (subquery), (subquery)...
  CTX_UPDATE_VALUE_LIST, ///< UPDATE ... SET field=(subquery)...
  CTX_JOIN,
  CTX_JOIN_TAB,
  CTX_MATERIALIZATION,
  CTX_DUPLICATES_WEEDOUT,
  CTX_DERIVED, ///< "Derived" subquery
  CTX_WHERE, ///< Subquery in WHERE clause item tree
  CTX_HAVING, ///< Subquery in HAVING clause item tree
  CTX_ORDER_BY, ///< ORDER BY clause execution context
  CTX_GROUP_BY, ///< GROUP BY clause execution context
  CTX_SIMPLE_ORDER_BY, ///< ORDER BY clause execution context
  CTX_SIMPLE_GROUP_BY, ///< GROUP BY clause execution context
  CTX_DISTINCT, ///< DISTINCT clause execution context
  CTX_SIMPLE_DISTINCT, ///< DISTINCT clause execution context
  CTX_BUFFER_RESULT, ///< see SQL_BUFFER_RESULT in the manual
  CTX_ORDER_BY_SQ, ///< Subquery in ORDER BY clause item tree
  CTX_GROUP_BY_SQ, ///< Subquery in GROUP BY clause item tree
  CTX_OPTIMIZED_AWAY_SUBQUERY, ///< Subquery executed once during optimization
  CTX_UNION,
  CTX_UNION_RESULT, ///< Pseudo-table context for UNION result
  CTX_QUERY_SPEC ///< Inner SELECTs of UNION expression
};


/**
  Types of traditional "extra" column parts and property names for hierarchical

  The traditional_extra_tags[] and json_extra_tags[] arrays must be in sync
  with this enum.
*/
enum Extra_tag
{
  ET_none,
  ET_USING_TEMPORARY,
  ET_USING_FILESORT,
  ET_USING_INDEX_CONDITION,
  ET_USING,
  ET_RANGE_CHECKED_FOR_EACH_RECORD,
  ET_USING_WHERE_WITH_PUSHED_CONDITION,
  ET_USING_WHERE,
  ET_NOT_EXISTS,
  ET_USING_MRR,
  ET_USING_INDEX,
  ET_FULL_SCAN_ON_NULL_KEY,
  ET_SKIP_OPEN_TABLE,
  ET_OPEN_FRM_ONLY,
  ET_OPEN_FULL_TABLE,
  ET_SCANNED_DATABASES,
  ET_USING_INDEX_FOR_GROUP_BY,
  ET_DISTINCT,
  ET_LOOSESCAN,
  ET_START_TEMPORARY,
  ET_END_TEMPORARY,
  ET_FIRST_MATCH,
  ET_MATERIALIZE,
  ET_START_MATERIALIZE,
  ET_END_MATERIALIZE,
  ET_SCAN,
  ET_USING_JOIN_BUFFER,
  ET_CONST_ROW_NOT_FOUND,
  ET_UNIQUE_ROW_NOT_FOUND,
  ET_IMPOSSIBLE_ON_CONDITION,
  ET_PUSHED_JOIN,
  //------------------------------------
  ET_total
};


/**
  Emulate lazy computation
*/
class Lazy: public Sql_alloc
{
public:
  virtual ~Lazy() {}

  /**
    Deferred evaluation of encapsulated expression

    @param [out] ret    Return string value

    @retval false       Success
    @retval true        Failure (OOM)
  */
  virtual bool eval(String *ret)= 0;
};

/**
  Base class for all EXPLAIN context descriptor classes

  In structured EXPLAIN implementation Explain_context is a base class for
  notes of an intermediate tree.
*/
struct Explain_context : Sql_alloc
{
  Explain_context_enum type; ///< type tag

  explicit Explain_context(Explain_context_enum type_arg) : type(type_arg) {}
};


namespace opt_explain_json_namespace // for forward declaration of "context"
{
  class context;
}

/**
  Helper class for table property buffering

  For traditional EXPLAIN this structure contains cached data for a single
  output row.

  For hierarchical EXPLAIN this structure contains property values for a single
  CTX_TABLE/CTX_JOIN_TAB context node of the intermediate tree.
*/

class qep_row : public Sql_alloc
{
private:
  /* Don't copy this structure */
  explicit qep_row(const qep_row &x); // undefined
  qep_row &operator=(const qep_row &x); // undefined

public:
  /**
    A wrapper for numeric table properties

    For traditional EXPLAIN this structure contains a value of one cell of the
    output row (excluding textual column values - see mem_root_str, and
    "Extra" column - see the col_extra list).

    For hierarchical EXPLAIN this structure contains a numeric property value
    for a single CTX_TABLE/CTX_JOIN_TAB context node of the intermediate tree.
  */
  template<typename T>
  struct column
  {
  private:
    bool nil; ///< true if the column contains NULL
  public:
    T value;

  public:
    column() { cleanup(); }
    bool is_empty() const { return nil; }
    void cleanup() { nil= true; }
    void set(T value_arg) { value= value_arg; nil= false; }
    T get() const { DBUG_ASSERT(!nil); return value; }
  };

  /**
    Helper class to keep string data in MEM_ROOT before passing to Item_string

    Since Item_string constructors doesn't copy input string parameter data 
    in the most cases, those input strings must have the same lifetime as
    Item_string objects, i.e. lifetime of MEM_ROOT.
    This class allocates input parameters for Item_string objects in MEM_ROOT.

    @note Call to is_empty() is necessary before the access to "str" and
          "length" fields, since is_empty() may trigger an evaluation of
          an associated expression that updates these fields.
  */
  struct mem_root_str
  {
    const char *str;
    size_t length;
    Lazy *deferred; //< encapsulated expression to evaluate it later (on demand)
    
    mem_root_str() { cleanup(); }
    void cleanup()
    {
      str= NULL;
      length= 0;
      deferred= NULL;
    }
    bool is_empty()
    {
      if (deferred)
      {
        StringBuffer<128> buff(system_charset_info);
        if (deferred->eval(&buff) || set(buff))
        {
          DBUG_ASSERT(!"OOM!");
          return true; // ignore OOM
        }
        deferred= NULL; // prevent double evaluation, if any
      }
      return str == NULL;
    }
    bool set(const char *str_arg)
    {
      return set(str_arg, strlen(str_arg));
    }
    bool set(const String &s)
    {
      return set(s.ptr(), s.length());
    }
    /**
      Make a copy of the string in MEM_ROOT
      
      @param str_arg    string to copy
      @param length_arg input string length

      @return false if success, true if error
    */
    bool set(const char *str_arg, size_t length_arg)
    {
      deferred= NULL;
      if (!(str= strndup_root(current_thd->mem_root, str_arg, length_arg)))
        return true; /* purecov: inspected */
      length= length_arg;
      return false;
    }
    /**
      Save expression for further evaluation

      @param x  Expression
    */
    void set(Lazy *x)
    {
      deferred= x;
      str= NULL;
      length= 0;
    }
    /**
      Make a copy of string constant

      Variant of set() usable when the str_arg argument lives longer
      than the mem_root_str instance.
    */
    void set_const(const char *str_arg)
    {
      return set_const(str_arg, strlen(str_arg));
    }
    void set_const(const char *str_arg, size_t length_arg)
    {
      deferred= NULL;
      str= str_arg;
      length= length_arg;
    }

    static char *strndup_root(MEM_ROOT *root, const char *str, size_t len)
    {
      if (len == 0 || str == NULL)
        return const_cast<char *>("");
      if (str[len - 1] == 0)
        return static_cast<char *>(memdup_root(root, str, len));

      char *ret= static_cast<char*>(alloc_root(root, len + 1));
      if (ret != NULL)
      {
        memcpy(ret, str, len);
        ret[len]= 0;
      }
      return ret;
    }
  };

  /**
    Part of traditional "extra" column or related hierarchical property
  */
  struct extra: public Sql_alloc
  {
    /**
      A property name or a constant text head of the "extra" column part
    */
    const Extra_tag tag;
    /**
      Property value or a variable tail of the "extra" column part

      If data == NULL, hierarchical formatter outputs a boolean property
      value of "true".
    */
    const char *const data;

    explicit extra(Extra_tag tag_arg, const char *data_arg= NULL)
    : tag(tag_arg), data(data_arg)
    {}
  };

  /*
    Next "col_*" fields are intended to be filling by "explain_*()" functions.

    NOTE: NULL value or mem_root_str.is_empty()==true means that Item_null object
          will be pushed into "items" list instead.
  */
  column<uint> col_id; ///< "id" column: seq. number of SELECT withing the query
  column<SELECT_LEX::type_enum> col_select_type; ///< "select_type" column
  mem_root_str col_table_name; ///< "table" to which the row of output refers
  List<const char> col_partitions; ///< "partitions" column
  mem_root_str col_join_type; ///< "type" column, see join_type_str array
  List<const char> col_possible_keys; ///< "possible_keys": comma-separated list
  mem_root_str col_key; ///< "key" column: index that is actually decided to use
  mem_root_str col_key_len; ///< "key_length" column: length of the "key" above
  List<const char> col_ref; ///< "ref":columns/constants which are compared to "key"
  column<longlong> col_rows; ///< "rows": estimated number of examined table rows
  column<float>    col_filtered; ///< "filtered": % of rows filtered by condition
  List<extra> col_extra; ///< "extra" column (traditional) or property list

  // non-TRADITIONAL stuff:
  mem_root_str col_message; ///< replaces "Extra" column if not empty
  mem_root_str col_attached_condition; ///< former "Using where"

  /* For structured EXPLAIN in CTX_JOIN_TAB context: */
  uint query_block_id; ///< query block id for materialized subqueries

  /**
    List of "derived" subquery trees
  */
  List<opt_explain_json_namespace::context> derived_from;

  List<const char> col_key_parts; ///< used parts of the key

  bool is_dependent;
  bool is_cacheable;
  bool using_temporary;
  bool is_materialized_from_subquery;
  bool is_update; //< UPDATE modified this table
  bool is_delete; //< DELETE modified this table

  qep_row() :
    query_block_id(0),
    is_dependent(false),
    is_cacheable(true),
    using_temporary(false),
    is_materialized_from_subquery(false),
    is_update(false),
    is_delete(false)
  {}

  virtual ~qep_row() {}

  void cleanup()
  {
    col_id.cleanup();
    col_table_name.cleanup();
    col_partitions.empty();
    col_join_type.cleanup();
    col_possible_keys.empty();
    col_key.cleanup();
    col_key_len.cleanup();
    col_ref.empty();
    col_rows.cleanup();
    col_filtered.cleanup();
    col_extra.empty();
    col_message.cleanup();
    col_attached_condition.cleanup();
    col_key_parts.empty();

    /*
      Not needed (we call cleanup() for structured EXPLAIN only,
      just for the consistency).
    */
    query_block_id= 0;
    derived_from.empty();
    is_dependent= false;
    is_cacheable= true;
    using_temporary= false;
    is_materialized_from_subquery= false;
    is_update= false;
    is_delete= false;
  }

  /**
    Remember a subquery's unit

    JOIN_TAB inside a JOIN, a table in a join-less query (single-table
    UPDATE/DELETE) or a table that's optimized out may have a WHERE
    condition. We create the Explain_context of such a JOIN_TAB or
    table when the Explain_context objects of its in-WHERE subqueries
    don't exist.
    This function collects unit pointers of WHERE subqueries that are
    associated with the current JOIN_TAB or table. Then we can match these
    units with units of newly-created Explain_context objects of WHERE
    subqueries.

    @param subquery     WHERE clause subquery's unit
  */
  virtual void register_where_subquery(SELECT_LEX_UNIT *subquery) {}
};


/**
  Argument for Item::explain_subquery_checker()

  Just a tuple of (destination, type) to pass as a single argument.
  See a commentary for Item_subselect::explain_subquery_checker
*/

struct Explain_subquery_marker
{
  class qep_row *destination; ///< hosting TABLE/JOIN_TAB
  Explain_context_enum type; ///< CTX_WHERE/CTX_HAVING/CTX_ORDER_BY/CTX_GROUP_BY

  Explain_subquery_marker(qep_row *destination_arg,
                          Explain_context_enum type_arg)
  : destination(destination_arg), type(type_arg)
  {}
};

/**
  Enumeration of ORDER BY, GROUP BY and DISTINCT clauses for array indexing

  See Explain_format_flags::sorts
*/
enum Explain_sort_clause
{
  ESC_none          = 0,
  ESC_ORDER_BY      = 1,
  ESC_GROUP_BY      = 2,
  ESC_DISTINCT      = 3,
  ESC_BUFFER_RESULT = 4,
//-----------------
  ESC_MAX
};

/**
  Bit flags to explain GROUP BY, ORDER BY and DISTINCT clauses
*/
enum Explain_sort_property
{
  ESP_none           = 0,
  ESP_EXISTS         = 1 << 0, //< Original query has this clause
  ESP_IS_SIMPLE      = 1 << 1, //< Clause is effective for single JOIN_TAB only
  ESP_USING_FILESORT = 1 << 2, //< Clause causes a filesort
  ESP_USING_TMPTABLE = 1 << 3, //< Clause creates an intermediate table
  ESP_DUPS_REMOVAL   = 1 << 4, //< Duplicate removal for DISTINCT
  ESP_CHECKED        = 1 << 5  //< Properties were already checked
};


class Explain_format_flags
{
  /**
    Bitmasks of Explain_sort_property flags for Explain_sort_clause clauses
  */
  uint8 sorts[ESC_MAX];

public:
  Explain_format_flags() { memset(sorts, 0, sizeof(sorts)); }

  /**
    Set property bit flag for the clause
  */
  void set(Explain_sort_clause clause, Explain_sort_property property)
  {
    sorts[clause]|= property | ESP_EXISTS;
  }

  void set(Explain_format_flags &flags)
  {
    memcpy(sorts, flags.sorts, sizeof(sorts));
  }

  /**
    Clear property bit flag for the clause
  */
  void reset(Explain_sort_clause clause, Explain_sort_property property)
  {
    sorts[clause]&= ~property;
  }

  /**
    Return true if property is set for the clause
  */
  bool get(Explain_sort_clause clause, Explain_sort_property property) const
  {
    return (sorts[clause] & property) || (sorts[clause] & ESP_CHECKED);
  }

  /**
    Return true if any of clauses has this property set
  */
  bool any(Explain_sort_property property) const
  {
    for (size_t i= ESC_none + 1; i <= ESC_MAX - 1; i++)
    {
      if (sorts[i] & property || sorts[i] & ESP_CHECKED)
        return true;
    }
    return false;
  }
};


/**
  Base class for structured and hierarchical EXPLAIN output formatters
*/

class Explain_format : public Sql_alloc
{
private:
  /* Don't copy Explain_format values */
  Explain_format(Explain_format &); // undefined
  Explain_format &operator=(Explain_format &); // undefined

public:
  select_result *output; ///< output resulting data there

public:
  Explain_format() : output(NULL) {}
  virtual ~Explain_format() {}
};

#endif//OPT_EXPLAIN_FORMAT_INCLUDED
