#ifndef TABLE_INCLUDED
#define TABLE_INCLUDED

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

#include "my_global.h"                          /* NO_EMBEDDED_ACCESS_CHECKS */
#include "sql_plist.h"
#include "sql_alloc.h"

#ifndef MYSQL_CLIENT

#include "hash.h"                               /* HASH */
#include "handler.h"                /* row_type, ha_choice, handler */
#include "mysql_com.h"              /* enum_field_types */
#include "thr_lock.h"                  /* thr_lock_type */
#include "parse_file.h"
#include "table_id.h"
#include "mysqld.h"

/* Structs that defines the TABLE */

class Item;				/* Needed by ORDER */
class Item_subselect;
class Item_field;
class GRANT_TABLE;
class st_select_lex_unit;
class st_select_lex;
class partition_info;
class COND_EQUAL;
class Security_context;
struct TABLE_LIST;
class Field_temporal_with_date_and_time;

struct INDEX_FIELD;
struct JOIN_CONDITION;

/*
  Used to identify NESTED_JOIN structures within a join (applicable to
  structures representing outer joins that have not been simplified away).
*/
typedef ulonglong nested_join_map;


#define tmp_file_prefix "#sql"			/**< Prefix for tmp tables */
#define tmp_file_prefix_length 4
#define TMP_TABLE_KEY_EXTRA 8

/**
  Enumerate possible types of a table from re-execution
  standpoint.
  TABLE_LIST class has a member of this type.
  At prepared statement prepare, this member is assigned a value
  as of the current state of the database. Before (re-)execution
  of a prepared statement, we check that the value recorded at
  prepare matches the type of the object we obtained from the
  table definition cache.

  @sa check_and_update_table_version()
  @sa Execute_observer
  @sa Prepared_statement::reprepare()
*/

enum enum_table_ref_type
{
  /** Initial value set by the parser */
  TABLE_REF_NULL= 0,
  TABLE_REF_VIEW,
  TABLE_REF_BASE_TABLE,
  TABLE_REF_I_S_TABLE,
  TABLE_REF_TMP_TABLE
};

/**
 Enumerate possible status of a identifier name while determining
 its validity
*/
enum enum_ident_name_check
{
  IDENT_NAME_OK,
  IDENT_NAME_WRONG,
  IDENT_NAME_TOO_LONG
};

/*************************************************************************/

/**
 Object_creation_ctx -- interface for creation context of database objects
 (views, stored routines, events, triggers). Creation context -- is a set
 of attributes, that should be fixed at the creation time and then be used
 each time the object is parsed or executed.
*/

class Object_creation_ctx
{
public:
  Object_creation_ctx *set_n_backup(THD *thd);

  void restore_env(THD *thd, Object_creation_ctx *backup_ctx);

protected:
  Object_creation_ctx() {}
  virtual Object_creation_ctx *create_backup_ctx(THD *thd) const = 0;

  virtual void change_env(THD *thd) const = 0;

public:
  virtual ~Object_creation_ctx()
  { }
};

/*************************************************************************/

/**
 Default_object_creation_ctx -- default implementation of
 Object_creation_ctx.
*/

class Default_object_creation_ctx : public Object_creation_ctx
{
public:
  const CHARSET_INFO *get_client_cs()
  {
    return m_client_cs;
  }

  const CHARSET_INFO *get_connection_cl()
  {
    return m_connection_cl;
  }

protected:
  Default_object_creation_ctx(THD *thd);

  Default_object_creation_ctx(const CHARSET_INFO *client_cs,
                              const CHARSET_INFO *connection_cl);

protected:
  virtual Object_creation_ctx *create_backup_ctx(THD *thd) const;

  virtual void change_env(THD *thd) const;

protected:
  /**
    client_cs stores the value of character_set_client session variable.
    The only character set attribute is used.

    Client character set is included into query context, because we save
    query in the original character set, which is client character set. So,
    in order to parse the query properly we have to switch client character
    set on parsing.
  */
  const CHARSET_INFO *m_client_cs;

  /**
    connection_cl stores the value of collation_connection session
    variable. Both character set and collation attributes are used.

    Connection collation is included into query context, becase it defines
    the character set and collation of text literals in internal
    representation of query (item-objects).
  */
  const CHARSET_INFO *m_connection_cl;
};


/**
 View_creation_ctx -- creation context of view objects.
*/

class View_creation_ctx : public Default_object_creation_ctx,
                          public Sql_alloc
{
public:
  static View_creation_ctx *create(THD *thd);

  static View_creation_ctx *create(THD *thd,
                                   TABLE_LIST *view);

private:
  View_creation_ctx(THD *thd)
    : Default_object_creation_ctx(thd)
  { }
};

/*************************************************************************/

/** Order clause list element */

typedef struct st_order {
  struct st_order *next;
  Item   **item;                        /* Point at item in select fields */
  Item   *item_ptr;                     /* Storage for initial item */
  int    counter;                       /* position in SELECT list, correct
                                           only if counter_used is true */
  enum enum_order {
    ORDER_NOT_RELEVANT,
    ORDER_ASC,
    ORDER_DESC
  };

  enum_order direction;                 /* Requested direction of ordering */
  bool   in_field_list;                 /* true if in select field list */
  bool   counter_used;                  /* parameter was counter of columns */
  /**
     Tells whether this ORDER element was referenced with an alias or with an
     expression, in the query:
     SELECT a AS foo GROUP BY foo: true.
     SELECT a AS foo GROUP BY a: false.
  */
  bool   used_alias;
  char   *buff;                         /* If tmp-table group */
  table_map used, depend_map;
} ORDER;

enum tmp_table_type
{
  NO_TMP_TABLE, NON_TRANSACTIONAL_TMP_TABLE, TRANSACTIONAL_TMP_TABLE,
  INTERNAL_TMP_TABLE, SYSTEM_TMP_TABLE
};
enum release_type { RELEASE_NORMAL, RELEASE_WAIT_FOR_DROP };

class Field_blob;
class Table_triggers_list;

/**
  Category of table found in the table share.
*/
enum enum_table_category
{
  /**
    Unknown value.
  */
  TABLE_UNKNOWN_CATEGORY=0,

  /**
    Temporary table.
    The table is visible only in the session.
    Therefore,
    - FLUSH TABLES WITH READ LOCK
    - SET GLOBAL READ_ONLY = ON
    do not apply to this table.
    Note that LOCK TABLE t FOR READ/WRITE
    can be used on temporary tables.
    Temporary tables are not part of the table cache.
  */
  TABLE_CATEGORY_TEMPORARY=1,

  /**
    User table.
    These tables do honor:
    - LOCK TABLE t FOR READ/WRITE
    - FLUSH TABLES WITH READ LOCK
    - SET GLOBAL READ_ONLY = ON
    User tables are cached in the table cache.
  */
  TABLE_CATEGORY_USER=2,

  /**
    System table, maintained by the server.
    These tables do honor:
    - LOCK TABLE t FOR READ/WRITE
    - FLUSH TABLES WITH READ LOCK
    - SET GLOBAL READ_ONLY = ON
    Typically, writes to system tables are performed by
    the server implementation, not explicitly be a user.
    System tables are cached in the table cache.
  */
  TABLE_CATEGORY_SYSTEM=3,

  /**
    Information schema tables.
    These tables are an interface provided by the system
    to inspect the system metadata.
    These tables do *not* honor:
    - LOCK TABLE t FOR READ/WRITE
    - FLUSH TABLES WITH READ LOCK
    - SET GLOBAL READ_ONLY = ON
    as there is no point in locking explicitly
    an INFORMATION_SCHEMA table.
    Nothing is directly written to information schema tables.
    Note that this value is not used currently,
    since information schema tables are not shared,
    but implemented as session specific temporary tables.
  */
  /*
    TODO: Fixing the performance issues of I_S will lead
    to I_S tables in the table cache, which should use
    this table type.
  */
  TABLE_CATEGORY_INFORMATION=4,

  /**
    Log tables.
    These tables are an interface provided by the system
    to inspect the system logs.
    These tables do *not* honor:
    - LOCK TABLE t FOR READ/WRITE
    - FLUSH TABLES WITH READ LOCK
    - SET GLOBAL READ_ONLY = ON
    as there is no point in locking explicitly
    a LOG table.
    An example of LOG tables are:
    - mysql.slow_log
    - mysql.general_log,
    which *are* updated even when there is either
    a GLOBAL READ LOCK or a GLOBAL READ_ONLY in effect.
    User queries do not write directly to these tables
    (there are exceptions for log tables).
    The server implementation perform writes.
    Log tables are cached in the table cache.
  */
  TABLE_CATEGORY_LOG=5,

  /**
    Performance schema tables.
    These tables are an interface provided by the system
    to inspect the system performance data.
    These tables do *not* honor:
    - LOCK TABLE t FOR READ/WRITE
    - FLUSH TABLES WITH READ LOCK
    - SET GLOBAL READ_ONLY = ON
    as there is no point in locking explicitly
    a PERFORMANCE_SCHEMA table.
    An example of PERFORMANCE_SCHEMA tables are:
    - performance_schema.*
    which *are* updated (but not using the handler interface)
    even when there is either
    a GLOBAL READ LOCK or a GLOBAL READ_ONLY in effect.
    User queries do not write directly to these tables
    (there are exceptions for SETUP_* tables).
    The server implementation perform writes.
    Performance tables are cached in the table cache.
  */
  TABLE_CATEGORY_PERFORMANCE=6,

  /**
    Replication Information Tables.
    These tables are used to store replication information.
    These tables do *not* honor:
    - LOCK TABLE t FOR READ/WRITE
    - FLUSH TABLES WITH READ LOCK
    - SET GLOBAL READ_ONLY = ON
    as there is no point in locking explicitly
    a Replication Information table.
    An example of replication tables are:
    - mysql.slave_master_info
    - mysql.slave_relay_log_info,
    which *are* updated even when there is either
    a GLOBAL READ LOCK or a GLOBAL READ_ONLY in effect.
    User queries do not write directly to these tables.
    Replication tables are cached in the table cache.
  */
  TABLE_CATEGORY_RPL_INFO=7
};
typedef enum enum_table_category TABLE_CATEGORY;

TABLE_CATEGORY get_table_category(const LEX_STRING *db,
                                  const LEX_STRING *name);


extern ulong refresh_version;

typedef struct st_table_field_type
{
  LEX_STRING name;
  LEX_STRING type;
  LEX_STRING cset;
} TABLE_FIELD_TYPE;


typedef struct st_table_field_def
{
  uint count;
  const TABLE_FIELD_TYPE *field;
} TABLE_FIELD_DEF;


/* Information for one open table */
enum index_hint_type
{
  INDEX_HINT_IGNORE,
  INDEX_HINT_USE,
  INDEX_HINT_FORCE
};

enum enum_schema_table_state
{ 
  NOT_PROCESSED= 0,
  PROCESSED_BY_CREATE_SORT_INDEX,
  PROCESSED_BY_JOIN_EXEC
};

typedef struct st_foreign_key_info
{
  LEX_STRING *foreign_id;
  LEX_STRING *foreign_db;
  LEX_STRING *foreign_table;
  LEX_STRING *referenced_db;
  LEX_STRING *referenced_table;
  LEX_STRING *update_method;
  LEX_STRING *delete_method;
  LEX_STRING *referenced_key_name;
  List<LEX_STRING> foreign_fields;
  List<LEX_STRING> referenced_fields;
} FOREIGN_KEY_INFO;

#define MY_I_S_MAYBE_NULL 1
#define MY_I_S_UNSIGNED   2


#define SKIP_OPEN_TABLE 0                // do not open table
#define OPEN_FRM_ONLY   1                // open FRM file only
#define OPEN_FULL_TABLE 2                // open FRM,MYD, MYI files

typedef struct st_field_info
{
  /** 
      This is used as column name. 
  */
  const char* field_name;
  /**
     For string-type columns, this is the maximum number of
     characters. Otherwise, it is the 'display-length' for the column.
  */
  uint field_length;
  /**
     This denotes data type for the column. For the most part, there seems to
     be one entry in the enum for each SQL data type, although there seem to
     be a number of additional entries in the enum.
  */
  enum enum_field_types field_type;
  int value;
  /**
     This is used to set column attributes. By default, columns are @c NOT
     @c NULL and @c SIGNED, and you can deviate from the default
     by setting the appopriate flags. You can use either one of the flags
     @c MY_I_S_MAYBE_NULL and @cMY_I_S_UNSIGNED or
     combine them using the bitwise or operator @c |. Both flags are
     defined in table.h.
   */
  uint field_flags;        // Field atributes(maybe_null, signed, unsigned etc.)
  const char* old_name;
  /**
     This should be one of @c SKIP_OPEN_TABLE,
     @c OPEN_FRM_ONLY or @c OPEN_FULL_TABLE.
  */
  uint open_method;
} ST_FIELD_INFO;


struct TABLE_LIST;

typedef struct st_schema_table
{
  const char* table_name;
  ST_FIELD_INFO *fields_info;
  int idx_field1, idx_field2;
  bool hidden;
  uint i_s_requested_object;  /* the object we need to open(TABLE | VIEW) */
} ST_SCHEMA_TABLE;


#define JOIN_TYPE_LEFT	1
#define JOIN_TYPE_RIGHT	2

enum enum_derived_type {
  VIEW_ALGORITHM_UNDEFINED = 0,
  VIEW_ALGORITHM_TMPTABLE,
  VIEW_ALGORITHM_MERGE,
  DERIVED_ALGORITHM_TMPTABLE
};

#define VIEW_SUID_INVOKER               0
#define VIEW_SUID_DEFINER               1
#define VIEW_SUID_DEFAULT               2

/* view WITH CHECK OPTION parameter options */
#define VIEW_CHECK_NONE       0
#define VIEW_CHECK_LOCAL      1
#define VIEW_CHECK_CASCADED   2

/* result of view WITH CHECK OPTION parameter check */
#define VIEW_CHECK_OK         0
#define VIEW_CHECK_ERROR      1
#define VIEW_CHECK_SKIP       2

/** The threshold size a blob field buffer before it is freed */
#define MAX_TDC_BLOB_SIZE 65536

class select_union;

struct Field_translator
{
  Item *item;
  const char *name;
};


/*
  Column reference of a NATURAL/USING join. Since column references in
  joins can be both from views and stored tables, may point to either a
  Field (for tables), or a Field_translator (for views).
*/

class Natural_join_column: public Sql_alloc
{
public:
  Field_translator *view_field;  /* Column reference of merge view. */
  Item_field       *table_field; /* Column reference of table or temp view. */
  TABLE_LIST *table_ref; /* Original base table/view reference. */
  /*
    True if a common join column of two NATURAL/USING join operands. Notice
    that when we have a hierarchy of nested NATURAL/USING joins, a column can
    be common at some level of nesting but it may not be common at higher
    levels of nesting. Thus this flag may change depending on at which level
    we are looking at some column.
  */
  bool is_common;
public:
  Natural_join_column(Field_translator *field_param, TABLE_LIST *tab);
  Natural_join_column(Item_field *field_param, TABLE_LIST *tab);
  const char *name();
  Item *create_item(THD *thd);
  const char *table_name();
  const char *db_name();
};


/**
   Type of table which can be open for an element of table list.
*/

enum enum_open_type
{
  OT_TEMPORARY_OR_BASE= 0, OT_TEMPORARY_ONLY, OT_BASE_ONLY
};

/*
  Data dictionary API.
*/

enum frm_type_enum
{
  FRMTYPE_ERROR= 0,
  FRMTYPE_TABLE,
  FRMTYPE_VIEW
};

class Index_hint;
class Item_exists_subselect;


/*
  Table reference in the FROM clause.

  These table references can be of several types that correspond to
  different SQL elements. Below we list all types of TABLE_LISTs with
  the necessary conditions to determine when a TABLE_LIST instance
  belongs to a certain type.

  1) table (TABLE_LIST::view == NULL)
     - base table
       (TABLE_LIST::derived == NULL)
     - subquery - TABLE_LIST::table is a temp table
       (TABLE_LIST::derived != NULL)
     - information schema table
       (TABLE_LIST::schema_table != NULL)
       NOTICE: for schema tables TABLE_LIST::field_translation may be != NULL
  2) view (TABLE_LIST::view != NULL)
     - merge    (TABLE_LIST::effective_algorithm == VIEW_ALGORITHM_MERGE)
           also (TABLE_LIST::field_translation != NULL)
     - tmptable (TABLE_LIST::effective_algorithm == VIEW_ALGORITHM_TMPTABLE)
           also (TABLE_LIST::field_translation == NULL)
  3) nested table reference (TABLE_LIST::nested_join != NULL)
     - table sequence - e.g. (t1, t2, t3)
       TODO: how to distinguish from a JOIN?
     - general JOIN
       TODO: how to distinguish from a table sequence?
     - NATURAL JOIN
       (TABLE_LIST::natural_join != NULL)
       - JOIN ... USING
         (TABLE_LIST::join_using_fields != NULL)
     - semi-join
       ;
*/

struct Name_resolution_context;
struct LEX;
struct TABLE_LIST
{
  TABLE_LIST() {}                          /* Remove gcc warning */

  /**
    Prepare TABLE_LIST that consists of one table instance to use in
    simple_open_and_lock_tables
  */
  inline void init_one_table(const char *db_name_arg,
                             size_t db_length_arg,
                             const char *table_name_arg,
                             size_t table_name_length_arg,
                             const char *alias_arg,
                             enum thr_lock_type lock_type_arg)
  {
    memset(this, 0, sizeof(*this));
    db= (char*) db_name_arg;
    db_length= db_length_arg;
    table_name= (char*) table_name_arg;
    table_name_length= table_name_length_arg;
    alias= (char*) alias_arg;
    lock_type= lock_type_arg;
  }

  /// Create a TABLE_LIST object representing a nested join
  static TABLE_LIST *new_nested_join(MEM_ROOT *allocator,
                                     const char *alias,
                                     TABLE_LIST *embedding,
                                     List<TABLE_LIST> *belongs_to,
                                     class st_select_lex *select);

  /*
    List of tables local to a subquery or the top-level SELECT (used by
    SQL_I_List). Considers views as leaves (unlike 'next_leaf' below).
    Created at parse time in st_select_lex::add_table_to_list() ->
    table_list.link_in_list().
  */
  TABLE_LIST *next_local;
  /* link in a global list of all queries tables */
  TABLE_LIST *next_global, **prev_global;
  char		*db, *alias, *table_name, *schema_table_name;
  char          *option;                /* Used by cache index  */
  /**
     Context which should be used to resolve identifiers contained in the ON
     condition of the embedding join nest.
     @todo When name resolution contexts are created after parsing, we should
     be able to store this in the embedding join nest instead.
  */
  Name_resolution_context *context_of_embedding;

private:
  Item		*m_join_cond;           /* Used with outer join */
public:


  INDEX_FIELD     *index_field_head; /* ???*/
  bool             is_table_driverd; /* 新增字段，用来表示表是不是驱动表*/
  List<JOIN_CONDITION> join_condition;

  Item         **join_cond_ref() { return &m_join_cond; }
  Item          *join_cond() const { return m_join_cond; }
  Item          *set_join_cond(Item *val)
                 { return m_join_cond= val; }
  /*
    The structure of the join condition presented in the member above
    can be changed during certain optimizations. This member
    contains a snapshot of AND-OR structure of the join condition
    made after permanent transformations of the parse tree, and is
    used to restore the join condition before every reexecution of a prepared
    statement or stored procedure.
  */
  Item          *prep_join_cond;

  Item          *sj_on_expr;            /* Synthesized semijoin condition */
  /*
    (Valid only for semi-join nests) Bitmap of tables that are within the
    semi-join (this is different from bitmap of all nest's children because
    tables that were pulled out of the semi-join nest remain listed as
    nest's children).
  */
  table_map     sj_inner_tables;

  COND_EQUAL    *cond_equal;            /* Used with outer join */
  /*
    During parsing - left operand of NATURAL/USING join where 'this' is
    the right operand. After parsing (this->natural_join == this) iff
    'this' represents a NATURAL or USING join operation. Thus after
    parsing 'this' is a NATURAL/USING join iff (natural_join != NULL).
  */
  TABLE_LIST *natural_join;
  /*
    True if 'this' represents a nested join that is a NATURAL JOIN.
    For one of the operands of 'this', the member 'natural_join' points
    to the other operand of 'this'.
  */
  bool is_natural_join;
  /* Field names in a USING clause for JOIN ... USING. */
  List<String> *join_using_fields;
  /*
    Explicitly store the result columns of either a NATURAL/USING join or
    an operand of such a join.
  */
  List<Natural_join_column> *join_columns;
  /* TRUE if join_columns contains all columns of this table reference. */
  bool is_join_columns_complete;

  /*
    List of nodes in a nested join tree, that should be considered as
    leaves with respect to name resolution. The leaves are: views,
    top-most nodes representing NATURAL/USING joins, subqueries, and
    base tables. All of these TABLE_LIST instances contain a
    materialized list of columns. The list is local to a subquery.
  */
  TABLE_LIST *next_name_resolution_table;
  /* Index names in a "... JOIN ... USE/IGNORE INDEX ..." clause. */
  List<Index_hint> *index_hints;
  Table_id table_id; /* table id (from binlog) for opened table */
  /*
    select_result for derived table to pass it from table creation to table
    filling procedure
  */
  select_union  *derived_result;
  /*
    Reference from aux_tables to local list entry of main select of
    multi-delete statement:
    delete t1 from t2,t1 where t1.a<'B' and t2.b=t1.b;
    here it will be reference of first occurrence of t1 to second (as you
    can see this lists can't be merged)
  */
  TABLE_LIST	*correspondent_table;
  /**
     @brief Normally, this field is non-null for anonymous derived tables only.

     @details This field is set to non-null for 
     
     - Anonymous derived tables, In this case it points to the SELECT_LEX_UNIT
     representing the derived table. E.g. for a query
     
     @verbatim SELECT * FROM (SELECT a FROM t1) b @endverbatim
     
     For the @c TABLE_LIST representing the derived table @c b, @c derived
     points to the SELECT_LEX_UNIT representing the result of the query within
     parenteses.
     
     - Views. This is set for views with @verbatim ALGORITHM = TEMPTABLE
     @endverbatim by mysql_make_view().
     
     @note Inside views, a subquery in the @c FROM clause is not allowed.
     @note Do not use this field to separate views/base tables/anonymous
     derived tables. Use TABLE_LIST::is_anonymous_derived_table().
  */
  st_select_lex_unit *derived;		/* SELECT_LEX_UNIT of derived table */
  /*
    TRUE <=> all possible keys for a derived table were collected and
    could be re-used while statement re-execution.
  */
  bool derived_keys_ready;
  ST_SCHEMA_TABLE *schema_table;        /* Information_schema table */
  st_select_lex	*schema_select_lex;
  /*
    True when the view field translation table is used to convert
    schema table fields for backwards compatibility with SHOW command.
  */
  bool schema_table_reformed;
  /* link to select_lex where this table was used */
  st_select_lex	*select_lex;
  LEX *view;                    /* link on VIEW lex for merging */
  Field_translator *field_translation;	/* array of VIEW fields */
  /* pointer to element after last one in translation table above */
  Field_translator *field_translation_end;
  /*
    List (based on next_local) of underlying tables of this view. I.e. it
    does not include the tables of subqueries used in the view. Is set only
    for merged views.
  */
  TABLE_LIST	*merge_underlying_list;
  /*
    - 0 for base tables
    - in case of the view it is the list of all (not only underlying
    tables but also used in subquery ones) tables of the view.
  */
  List<TABLE_LIST> *view_tables;
  /* most upper view this table belongs to */
  TABLE_LIST	*belong_to_view;
  /*
    The view directly referencing this table
    (non-zero only for merged underlying tables of a view).
  */
  TABLE_LIST	*referencing_view;
  /* Ptr to parent MERGE table list item. See top comment in ha_myisammrg.cc */
  TABLE_LIST    *parent_l;
  /*
    Security  context (non-zero only for tables which belong
    to view with SQL SECURITY DEFINER)
  */
  Security_context *security_ctx;
  /*
    This view security context (non-zero only for views with
    SQL SECURITY DEFINER)
  */
  Security_context *view_sctx;
  /*
    List of all base tables local to a subquery including all view
    tables. Unlike 'next_local', this in this list views are *not*
    leaves. Created in setup_tables() -> make_leaves_list().
  */
  bool allowed_show;
  TABLE_LIST	*next_leaf;
  Item          *where;                 /* VIEW WHERE clause condition */
  Item          *check_option;          /* WITH CHECK OPTION condition */
  LEX_STRING	select_stmt;		/* text of (CREATE/SELECT) statement */
  LEX_STRING	md5;			/* md5 of query text */
  LEX_STRING	source;			/* source of CREATE VIEW */
  LEX_STRING	view_db;		/* saved view database */
  LEX_STRING	view_name;		/* saved view name */
  LEX_STRING	timestamp;		/* GMT time stamp of last operation */
  st_lex_user   definer;                /* definer of view */
  ulonglong	file_version;		/* version of file's field set */
  ulonglong     updatable_view;         /* VIEW can be updated */
  /** 
      @brief The declared algorithm, if this is a view.
      @details One of
      - VIEW_ALGORITHM_UNDEFINED
      - VIEW_ALGORITHM_TMPTABLE
      - VIEW_ALGORITHM_MERGE
      @to do Replace with an enum 
  */
  ulonglong	algorithm;
  ulonglong     view_suid;              /* view is suid (TRUE dy default) */
  ulonglong     with_check;             /* WITH CHECK OPTION */
  /*
    effective value of WITH CHECK OPTION (differ for temporary table
    algorithm)
  */
  uint8         effective_with_check;
  /** 
      @brief The view algorithm that is actually used, if this is a view.
      @details One of
      - VIEW_ALGORITHM_UNDEFINED
      - VIEW_ALGORITHM_TMPTABLE
      - VIEW_ALGORITHM_MERGE
      @to do Replace with an enum 
  */
  enum_derived_type effective_algorithm;
  /* data need by some engines in query cache*/
  ulonglong     engine_data;
  thr_lock_type lock_type;
  uint		outer_join;		/* Which join type */
  uint		shared;			/* Used in multi-upd */
  size_t        db_length;
  size_t        table_name_length;
  bool          updatable;		/* VIEW/TABLE can be updated now */
  bool		straight;		/* optimize with prev table */
  bool          updating;               /* for replicate-do/ignore table */
  bool		force_index;		/* prefer index over table scan */
  bool          ignore_leaves;          /* preload only non-leaf nodes */
  table_map     dep_tables;             /* tables the table depends on      */
  table_map     on_expr_dep_tables;     /* tables on expression depends on  */
  struct st_nested_join *nested_join;   /* if the element is a nested join  */
  TABLE_LIST *embedding;             /* nested join containing the table */
  List<TABLE_LIST> *join_list;/* join list the table belongs to   */
  bool		cacheable_table;	/* stop PS caching */
  /* used in multi-upd/views privilege check */
  bool		table_in_first_from_clause;
  /**
     Specifies which kind of table should be open for this element
     of table list.
  */
  enum enum_open_type open_type;
  /* TRUE if this merged view contain auto_increment field */
  bool          contain_auto_increment;
  bool          multitable_view;        /* TRUE iff this is multitable view */
  bool          compact_view_format;    /* Use compact format for SHOW CREATE VIEW */
  /* view where processed */
  bool          where_processed;
  /* TRUE <=> VIEW CHECK OPTION expression has been processed */
  bool          check_option_processed;
  /* FRMTYPE_ERROR if any type is acceptable */
  enum frm_type_enum required_type;
  char		timestamp_buffer[20];	/* buffer for timestamp (19+1) */
  /*
    This TABLE_LIST object is just placeholder for prelocking, it will be
    used for implicit LOCK TABLES only and won't be used in real statement.
  */
  bool          prelocking_placeholder;
  /**
     Indicates that if TABLE_LIST object corresponds to the table/view
     which requires special handling.
  */
  enum
  {
    /* Normal open. */
    OPEN_NORMAL= 0,
    /* Associate a table share only if the the table exists. */
    OPEN_IF_EXISTS,
    /*
      Associate a table share only if the the table exists.
      Also upgrade metadata lock to exclusive if table doesn't exist.
    */
    OPEN_FOR_CREATE,
    /* Don't associate a table share. */
    OPEN_STUB
  } open_strategy;
  bool          internal_tmp_table;
  /** TRUE if an alias for this table was specified in the SQL. */
  bool          is_alias;
  /** TRUE if the table is referred to in the statement using a fully
      qualified name (<db_name>.<table_name>).
  */
  bool          is_fqtn;


  /* View creation context. */

  View_creation_ctx *view_creation_ctx;

  /*
    Attributes to save/load view creation context in/from frm-file.

    Ther are required only to be able to use existing parser to load
    view-definition file. As soon as the parser parsed the file, view
    creation context is initialized and the attributes become redundant.

    These attributes MUST NOT be used for any purposes but the parsing.
  */

  LEX_STRING view_client_cs_name;
  LEX_STRING view_connection_cl_name;

  /*
    View definition (SELECT-statement) in the UTF-form.
  */

  LEX_STRING view_body_utf8;

  /**
    Indicates what triggers we need to pre-load for this TABLE_LIST
    when opening an associated TABLE. This is filled after
    the parsed tree is created.
  */
  uint8 trg_event_map;
  /* TRUE <=> this table is a const one and was optimized away. */
  bool optimized_away;
  uint i_s_requested_object;
  bool has_db_lookup_value;
  bool has_table_lookup_value;
  uint table_open_method;
  enum enum_schema_table_state schema_table_state;

#ifdef WITH_PARTITION_STORAGE_ENGINE
  /* List to carry partition names from PARTITION (...) clause in statement */
  List<String> *partition_names;
#endif /* WITH_PARTITION_STORAGE_ENGINE */

  inline List<JOIN_CONDITION> * get_join_condition(){
	  if (join_condition.elements == 0){
		  join_condition.empty();
	  }
	  return &join_condition;
  }

  bool setup_underlying(THD *thd);
  void print(THD *thd, String *str, enum_query_type query_type);

  void hide_view_error(THD *thd);
  TABLE_LIST *first_leaf_for_name_resolution();
  TABLE_LIST *last_leaf_for_name_resolution();
  bool is_leaf_for_name_resolution();
  inline const TABLE_LIST *top_table() const
    { return belong_to_view ? belong_to_view : this; }

  inline TABLE_LIST *top_table()
  {
    return
      const_cast<TABLE_LIST*>(const_cast<const TABLE_LIST*>(this)->top_table());
  }

  /**
    @returns
      TRUE  this is a materializable derived table/view.
      FALSE otherwise.
  */
  inline bool uses_materialization() const
  {
    return (effective_algorithm == VIEW_ALGORITHM_TMPTABLE ||
            effective_algorithm == DERIVED_ALGORITHM_TMPTABLE);
  }
  inline bool is_view_or_derived() const
  {
    return (effective_algorithm != VIEW_ALGORITHM_UNDEFINED);
  }
  /**
    @returns true if materializable table contains one or zero rows.

    Returning true implies that the table is materialized during optimization,
    so it need not be optimized during execution.
  */
  bool materializable_is_const() const;

  void register_want_access(ulong want_access);
  bool prepare_security(THD *thd);
  /*
    Cleanup for re-execution in a prepared statement or a stored
    procedure.
  */
  void reinit_before_use(THD *thd);
  Item_subselect *containing_subselect();

  inline
  void set_table_ref_id(enum_table_ref_type table_ref_type_arg,
                        ulonglong table_ref_version_arg)
  {
    m_table_ref_type= table_ref_type_arg;
    m_table_ref_version= table_ref_version_arg;
  }

  /**
     @brief True if this TABLE_LIST represents an anonymous derived table,
     i.e.  the result of a subquery.
  */
  bool is_anonymous_derived_table() const { return derived && !view; }

  /// returns query block id for derived table, and zero if not derived.
  uint query_block_id() const;

  /**
     @brief Returns the name of the database that the referenced table belongs
     to.
  */
  char *get_db_name() const { return view != NULL ? view_db.str : db; }

  /**
     @brief Returns the name of the table that this TABLE_LIST represents.

     @details The unqualified table name or view name for a table or view,
     respectively.
   */
  char *get_table_name() const { return view != NULL ? view_name.str : table_name; }
  st_select_lex_unit *get_unit() const;

  /**
    @brief Returns the outer join nest that this TABLE_LIST belongs to, if any.

    @details There are two kinds of join nests, outer-join nests and semi-join 
    nests.  This function returns non-NULL in the following cases:
      @li 1. If this table/nest is embedded in a nest and this nest IS NOT a 
             semi-join nest.  (In other words, it is an outer-join nest.)
      @li 2. If this table/nest is embedded in a nest and this nest IS a 
             semi-join nest, but this semi-join nest is embedded in another 
             nest. (This other nest will be an outer-join nest, since all inner 
             joined nested semi-join nests have been merged in 
             @c simplify_joins() ).
    Note: This function assumes that @c simplify_joins() has been performed.
    Before that, join nests will be present for all types of join.

    @return outer join nest, or NULL if none.
   */
  TABLE_LIST *outer_join_nest() const
  {
    if (!embedding)
      return NULL;
    if (embedding->sj_on_expr)
      return embedding->embedding;
    return embedding;
  }

private:
  /** See comments for set_metadata_id() */
  enum enum_table_ref_type m_table_ref_type;
  /** See comments for TABLE_SHARE::get_table_ref_version() */
  ulonglong m_table_ref_version;
};


struct st_position;
  
class Item;

/*
  Iterator over the fields of a generic table reference.
*/

class Field_iterator: public Sql_alloc
{
public:
  Field_iterator() {}                         /* Remove gcc warning */
  virtual ~Field_iterator() {}
  virtual void set(TABLE_LIST *)= 0;
  virtual void next()= 0;
  virtual bool end_of_fields()= 0;              /* Return 1 at end of list */
  virtual const char *name()= 0;
  virtual Item *create_item(THD *)= 0;
};

/**
  Struct st_nested_join is used to represent how tables are connected through
  outer join operations and semi-join operations to form a query block.
  Out of the parser, inner joins are also represented by st_nested_join
  structs, but these are later flattened out by simplify_joins().
  Some outer join nests are also flattened, when it can be determined that
  they can be processed as inner joins instead of outer joins.
*/
typedef struct st_nested_join
{
  List<TABLE_LIST>  join_list;       /* list of elements in the nested join */
  table_map         used_tables;     /* bitmap of tables in the nested join */
  table_map         not_null_tables; /* tables that rejects nulls           */
  /**
    Used for pointing out the first table in the plan being covered by this
    join nest. It is used exclusively within make_outerjoin_info().
   */
  struct st_join_table *first_nested;
  /**
    Number of tables and outer join nests administered by this nested join
    object for the sake of cost analysis. Includes direct member tables as
    well as tables included through semi-join nests, but notice that semi-join
    nests themselves are not counted.
  */
  uint              nj_total;
  /**
    Used to count tables in the nested join in 2 isolated places:
    1. In make_outerjoin_info(). 
    2. check_interleaving_with_nj/backout_nj_state (these are called
       by the join optimizer. 
    Before each use the counters are zeroed by reset_nj_counters.
  */
  uint              nj_counter;
  /**
    Bit identifying this nested join. Only nested joins representing the
    outer join structure need this, other nests have bit set to zero.
  */
  nested_join_map   nj_map;
  /**
    Tables outside the semi-join that are used within the semi-join's
    ON condition (ie. the subquery WHERE clause and optional IN equalities).
  */
  table_map         sj_depends_on;
  /**
    Outer non-trivially correlated tables, a true subset of sj_depends_on
  */
  table_map         sj_corr_tables;
  /**
    Query block id if this struct is generated from a subquery transform.
  */
  uint query_block_id;
  /*
    Lists of trivially-correlated expressions from the outer and inner tables
    of the semi-join, respectively.
  */
  List<Item>        sj_outer_exprs, sj_inner_exprs;
} NESTED_JOIN;


typedef struct st_changed_table_list
{
  struct	st_changed_table_list *next;
  char		*key;
  uint32        key_length;
} CHANGED_TABLE_LIST;


typedef struct st_open_table_list{
  struct st_open_table_list *next;
  char	*db,*table;
  uint32 in_use,locked;
} OPEN_TABLE_LIST;

static inline void tmp_restore_column_map(MY_BITMAP *bitmap,
                                          my_bitmap_map *old)
{
  bitmap->bitmap= old;
}

static inline void dbug_tmp_restore_column_map(MY_BITMAP *bitmap,
                                               my_bitmap_map *old)
{
#ifndef DBUG_OFF
  tmp_restore_column_map(bitmap, old);
#endif
}

enum_ident_name_check check_and_convert_db_name(LEX_STRING *db,
                                                bool preserve_lettercase);
bool check_column_name(const char *name);
enum_ident_name_check check_table_name(const char *name, size_t length,
                                       bool check_for_path_chars);
int rename_file_ext(const char * from,const char * to,const char * ext);

int set_zone(int nr,int min_zone,int max_zone);
ulong get_form_pos(File file, uchar *head, TYPELIB *save_names);
ulong make_new_entry(File file,uchar *fileinfo,TYPELIB *formnames,
		     const char *newname);
ulong next_io_size(ulong pos);
void append_unescaped(String *res, const char *pos, uint length);
char *fn_rext(char *name);

/* performance schema */
extern LEX_STRING PERFORMANCE_SCHEMA_DB_NAME;

extern LEX_STRING GENERAL_LOG_NAME;
extern LEX_STRING SLOW_LOG_NAME;

/* information schema */
extern LEX_STRING INFORMATION_SCHEMA_NAME;
extern LEX_STRING MYSQL_SCHEMA_NAME;

/* replication's tables */
extern LEX_STRING RLI_INFO_NAME;
extern LEX_STRING MI_INFO_NAME;
extern LEX_STRING WORKER_INFO_NAME;

inline bool is_infoschema_db(const char *name, size_t len)
{
  return (INFORMATION_SCHEMA_NAME.length == len &&
          !my_strcasecmp(system_charset_info,
                         INFORMATION_SCHEMA_NAME.str, name));
}

inline bool is_infoschema_db(const char *name)
{
  return !my_strcasecmp(system_charset_info,
                        INFORMATION_SCHEMA_NAME.str, name);
}

TYPELIB *typelib(MEM_ROOT *mem_root, List<String> &strings);


bool is_simple_order(ORDER *order);

#endif /* MYSQL_CLIENT */

#endif /* TABLE_INCLUDED */
