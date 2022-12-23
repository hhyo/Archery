/* Copyright (c) 2002, 2014, Oracle and/or its affiliates. All rights reserved.

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

#ifndef _SP_HEAD_H_
#define _SP_HEAD_H_

/*
  It is necessary to include set_var.h instead of item.h because there
  are dependencies on include order for set_var.h and item.h. This
  will be resolved later.
*/
#include "my_global.h"                          /* NO_EMBEDDED_ACCESS_CHECKS */
#include "sql_class.h"                          // THD, set_var.h: THD
#include "set_var.h"                            // Item
#include "sp_pcontext.h"                        // sp_pcontext

/**
  @defgroup Stored_Routines Stored Routines
  @ingroup Runtime_Environment
  @{
*/

class sp_instr;
class sp_branch_instr;
class sp_lex_branch_instr;

///////////////////////////////////////////////////////////////////////////

/**
  sp_printable defines an interface which should be implemented if a class wants
  report some internal information about its state.
*/
class sp_printable
{
public:
  virtual void print(String *str) = 0;

  virtual ~sp_printable()
  { }
};

///////////////////////////////////////////////////////////////////////////

/**
  Stored_program_creation_ctx -- base class for creation context of stored
  programs (stored routines, triggers, events).
*/

class Stored_program_creation_ctx : public Default_object_creation_ctx
{
public:
  const CHARSET_INFO *get_db_cl()
  {
    return m_db_cl;
  }

public:
  virtual Stored_program_creation_ctx *clone(MEM_ROOT *mem_root) = 0;

protected:
  Stored_program_creation_ctx(THD *thd)
    : Default_object_creation_ctx(thd),
      m_db_cl(thd->variables.collation_database)
  { }

  Stored_program_creation_ctx(const CHARSET_INFO *client_cs,
                              const CHARSET_INFO *connection_cl,
                              const CHARSET_INFO *db_cl)
    : Default_object_creation_ctx(client_cs, connection_cl),
      m_db_cl(db_cl)
  { }

protected:
  virtual void change_env(THD *thd) const
  {
    thd->variables.collation_database= m_db_cl;

    Default_object_creation_ctx::change_env(thd);
  }

protected:
  /**
    db_cl stores the value of the database collation. Both character set
    and collation attributes are used.

    Database collation is included into the context because it defines the
    default collation for stored-program variables.
  */
  const CHARSET_INFO *m_db_cl;
};

///////////////////////////////////////////////////////////////////////////

class sp_name : public Sql_alloc
{
public:

  LEX_STRING m_db;
  LEX_STRING m_name;
  LEX_STRING m_qname;
  bool       m_explicit_name;                   /**< Prepend the db name? */

  sp_name(LEX_STRING db, LEX_STRING name, bool use_explicit_name)
    : m_db(db), m_name(name), m_explicit_name(use_explicit_name)
  {
    m_qname.str= 0;
    m_qname.length= 0;
  }

  /** Create temporary sp_name object from MDL key. */
  sp_name(char *qname_buff);

  // Init. the qualified name from the db and name.
  void init_qname(THD *thd);	// thd for memroot allocation
};

///////////////////////////////////////////////////////////////////////////

/**
  sp_parser_data provides a scope for attributes used at the SP-parsing
  stage only.
*/
class sp_parser_data
{
private:
  struct Backpatch_info
  {
    sp_label *label;
    sp_branch_instr *instr;
  };

public:
  sp_parser_data() :
    m_expr_start_ptr(NULL),
    m_current_stmt_start_ptr(NULL),
    m_option_start_ptr(NULL),
    m_param_start_ptr(NULL),
    m_param_end_ptr(NULL),
    m_body_start_ptr(NULL),
    m_cont_level(0),
    m_saved_memroot(NULL),
    m_saved_free_list(NULL)
  { }

  ///////////////////////////////////////////////////////////////////////

  /**
    Start parsing a stored program body statement.

    This method switches THD::mem_root and THD::free_list in order to parse
    SP-body. The current values are kept to be restored after the body
    statement is parsed.

    @param thd  Thread context.
    @param sp   Stored Program being parsed.
  */
  void start_parsing_sp_body(THD *thd, sp_head *sp);

  /**
    Finish parsing of a stored program body statement.

    This method switches THD::mem_root and THD::free_list back when SP-body
    parsing is completed.

    @param thd  Thread context.
  */
  void finish_parsing_sp_body(THD *thd)
  {
    /*
      In some cases the parser detects a syntax error and calls
      LEX::cleanup_lex_after_parse_error() method only after finishing parsing
      the whole routine. In such a situation sp_head::restore_thd_mem_root() will
      be called twice - the first time as part of normal parsing process and the
      second time by cleanup_lex_after_parse_error().

      To avoid ruining active arena/mem_root state in this case we skip
      restoration of old arena/mem_root if this method has been already called for
      this routine.
    */
    if (!is_parsing_sp_body())
      return;

    thd->free_items();
    thd->mem_root= m_saved_memroot;
    thd->free_list= m_saved_free_list;

    m_saved_memroot= NULL;
    m_saved_free_list= NULL;
  }

  /**
    @retval true if SP-body statement is being parsed.
    @retval false otherwise.
  */
  bool is_parsing_sp_body() const
  { return m_saved_memroot != NULL; }

  ///////////////////////////////////////////////////////////////////////

  void process_new_sp_instr(THD *thd, sp_instr *i);

  ///////////////////////////////////////////////////////////////////////

  /**
    Retrieve expression start pointer in the query string.

    This function is named 'pop' to highlight that it changes the internal
    state, and two subsequent calls may not return same value.

    @note It's true only in the debug mode, but this check is very useful in
    the parser to ensure we "pop" every "pushed" pointer, because we have
    lots of branches, and it's pretty easy to forget something somewhere.
  */
  const char *pop_expr_start_ptr()
  {
#ifndef DBUG_OFF
    DBUG_ASSERT(m_expr_start_ptr);
    const char *p= m_expr_start_ptr;
    m_expr_start_ptr= NULL;
    return p;
#else
    return m_expr_start_ptr;
#endif
  }

  /**
    Remember expression start pointer in the query string.

    This function is named 'push' to highlight that the pointer must be
    retrieved (pop) later.

    @sa the note for pop_expr_start_ptr().
  */
  void push_expr_start_ptr(const char *expr_start_ptr)
  {
    DBUG_ASSERT(!m_expr_start_ptr);
    m_expr_start_ptr= expr_start_ptr;
  }

  ///////////////////////////////////////////////////////////////////////

  const char *get_current_stmt_start_ptr() const
  { return m_current_stmt_start_ptr; }

  void set_current_stmt_start_ptr(const char *stmt_start_ptr)
  { m_current_stmt_start_ptr= stmt_start_ptr; }

  ///////////////////////////////////////////////////////////////////////

  const char *get_option_start_ptr() const
  { return m_option_start_ptr; }

  void set_option_start_ptr(const char *option_start_ptr)
  { m_option_start_ptr= option_start_ptr; }

  ///////////////////////////////////////////////////////////////////////

  const char *get_parameter_start_ptr() const
  { return m_param_start_ptr; }

  void set_parameter_start_ptr(const char *ptr)
  { m_param_start_ptr= ptr; }

  const char *get_parameter_end_ptr() const
  { return m_param_end_ptr; }

  void set_parameter_end_ptr(const char *ptr)
  { m_param_end_ptr= ptr; }

  ///////////////////////////////////////////////////////////////////////

  const char *get_body_start_ptr() const
  { return m_body_start_ptr; }

  void set_body_start_ptr(const char *ptr)
  { m_body_start_ptr= ptr; }

  ///////////////////////////////////////////////////////////////////////

  void push_lex(LEX *lex)
  { m_lex_stack.push_front(lex); }

  LEX *pop_lex()
  { return m_lex_stack.pop(); }

  ///////////////////////////////////////////////////////////////////////
  // Backpatch-list operations.
  ///////////////////////////////////////////////////////////////////////

  /**
    Put the instruction on the backpatch list, associated with the label.

    @param i      The SP-instruction.
    @param label  The label.

    @return Error flag.
  */
  bool add_backpatch_entry(sp_branch_instr *i, sp_label *label);

  /**
    Update all instruction with the given label in the backpatch list
    to the given instruction pointer.

    @param label  The label.
    @param dest   The instruction pointer.
  */
  void do_backpatch(sp_label *label, uint dest);

  ///////////////////////////////////////////////////////////////////////
  // Backpatch operations for supporting CONTINUE handlers.
  ///////////////////////////////////////////////////////////////////////

  /**
    Start a new backpatch level for the SP-instruction requiring continue
    destination. If the SP-instruction is NULL, the level is just increased.

    @note Only subclasses of sp_lex_branch_instr need backpatching of
    continue destinations (and no other classes do):
      - sp_instr_jump_if_not
      - sp_instr_set_case_expr
      - sp_instr_jump_case_when

    That's why the methods below accept sp_lex_branch_instr to make this
    relationship clear. And these two functions are the only places where
    set_cont_dest() is used, so set_cont_dest() is also a member of
    sp_lex_branch_instr.

    @todo These functions should probably be declared in a separate
    interface class, but currently we try to minimize the sp_instr
    hierarchy.

    @return false always.
  */
  bool new_cont_backpatch()
  {
    ++m_cont_level;
    return false;
  }

  /**
    Add a SP-instruction to the current level.

    @param i    The SP-instruction.

    @return Error flag.
  */
  bool add_cont_backpatch_entry(sp_lex_branch_instr *i);

  /**
    Backpatch (and pop) the current level to the given instruction pointer.

    @param dest The instruction pointer.
  */
  void do_cont_backpatch(uint dest);

private:
  /// Start of the expression query string (any but SET-expression).
  const char *m_expr_start_ptr;

  /// Start of the current statement's query string.
  const char *m_current_stmt_start_ptr;

  /// Start of the SET-expression query string.
  const char *m_option_start_ptr;

  /**
    Stack of LEX-objects. It's needed to handle processing of
    sub-statements.
  */
  List<LEX> m_lex_stack;

  /**
    Position in the CREATE PROCEDURE- or CREATE FUNCTION-statement's query
    string corresponding to the start of parameter declarations (stored
    procedure or stored function parameters).
  */
  const char *m_param_start_ptr;

  /**
    Position in the CREATE PROCEDURE- or CREATE FUNCTION-statement's query
    string corresponding to the end of parameter declarations (stored
    procedure or stored function parameters).
  */
  const char *m_param_end_ptr;

  /**
    Position in the CREATE-/ALTER-stored-program statement's query string
    corresponding to the start of the first SQL-statement.
  */
  const char *m_body_start_ptr;

  /// Instructions needing backpatching
  List<Backpatch_info> m_backpatch;

  /**
    We need a special list for backpatching of instructions with a continue
    destination (in the case of a continue handler catching an error in
    the test), since it would otherwise interfere with the normal backpatch
    mechanism - e.g. jump_if_not instructions have two different destinations
    which are to be patched differently.
    Since these occur in a more restricted way (always the same "level" in
    the code), we don't need the label.
  */
  List<sp_lex_branch_instr> m_cont_backpatch;

  /// The current continue backpatch level
  uint m_cont_level;

  /**********************************************************************
    The following attributes are used to store THD values during parsing
    of stored program body.

    @sa start_parsing_sp_body()
    @sa finish_parsing_sp_body()
  **********************************************************************/

  /// THD's memroot.
  MEM_ROOT *m_saved_memroot;

  /// THD's free-list.
  Item *m_saved_free_list;
};

///////////////////////////////////////////////////////////////////////////

/**
  sp_head represents one instance of a stored program. It might be of any type
  (stored procedure, function, trigger, event).
*/
class sp_head : private Query_arena
{
public:
  /** Possible values of m_flags */
  enum {
    HAS_RETURN= 1,              // For FUNCTIONs only: is set if has RETURN
    MULTI_RESULTS= 8,           // Is set if a procedure with SELECT(s)
    CONTAINS_DYNAMIC_SQL= 16,   // Is set if a procedure with PREPARE/EXECUTE
    IS_INVOKED= 32,             // Is set if this sp_head is being used
    HAS_SET_AUTOCOMMIT_STMT= 64,// Is set if a procedure with 'set autocommit'
    /* Is set if a procedure with COMMIT (implicit or explicit) | ROLLBACK */
    HAS_COMMIT_OR_ROLLBACK= 128,
    LOG_SLOW_STATEMENTS= 256,   // Used by events
    LOG_GENERAL_LOG= 512,        // Used by events
    HAS_SQLCOM_RESET= 1024,
    HAS_SQLCOM_FLUSH= 2048,

    /**
      Marks routines that directly (i.e. not by calling other routines)
      change tables. Note that this flag is set automatically based on
      type of statements used in the stored routine and is different
      from routine characteristic provided by user in a form of CONTAINS
      SQL, READS SQL DATA, MODIFIES SQL DATA clauses. The latter are
      accepted by parser but pretty much ignored after that.
      We don't rely on them:
      a) for compatibility reasons.
      b) because in CONTAINS SQL case they don't provide enough
      information anyway.
     */
    MODIFIES_DATA= 4096
  };

public:
  /************************************************************************
    Public attributes.
  ************************************************************************/

  /// Stored program type.
  enum_sp_type m_type;

  /// Stored program flags.
  uint m_flags;

  /**
  Definition of the RETURN-field (from the RETURNS-clause).
  It's used (and valid) for stored functions only.
*/
  Create_field m_return_field_def;

  /// Attributes used during the parsing stage only.
  sp_parser_data m_parser_data;

  /// Stored program characteristics.
  st_sp_chistics *m_chistics;

  /**
    The value of sql_mode system variable at the CREATE-time.

    It should be stored along with the character sets in the
    Stored_program_creation_ctx.
  */
  sql_mode_t m_sql_mode;

  /// Fully qualified name (<db name>.<sp name>).
  LEX_STRING m_qname;

  bool m_explicit_name;         ///< Prepend the db name? */

  LEX_STRING m_db;
  LEX_STRING m_name;
  LEX_STRING m_params;
  LEX_STRING m_body;
  LEX_STRING m_body_utf8;
  LEX_STRING m_defstr;
  LEX_STRING m_definer_user;
  LEX_STRING m_definer_host;

  longlong m_created;
  longlong m_modified;

  /// Recursion level of the current SP instance. The levels are numbered from 0.
  ulong m_recursion_level;

  /**
    A list of diferent recursion level instances for the same procedure.
    For every recursion level we have a sp_head instance. This instances
    connected in the list. The list ordered by increasing recursion level
    (m_recursion_level).
  */
  sp_head *m_next_cached_sp;

  /// Pointer to the first element of the above list
  sp_head *m_first_instance;

  /**
    Pointer to the first free (non-INVOKED) routine in the list of
    cached instances for this SP. This pointer is set only for the first
    SP in the list of instances (see above m_first_cached_sp pointer).
    The pointer equal to 0 if we have no free instances.
    For non-first instance value of this pointer meaningless (point to itself);
  */
  sp_head *m_first_free_instance;

  /**
    Pointer to the last element in the list of instances of the SP.
    For non-first instance value of this pointer meaningless (point to itself);
  */
  sp_head *m_last_cached_sp;

  /**
    Set containing names of stored routines used by this routine.
    Note that unlike elements of similar set for statement elements of this
    set are not linked in one list. Because of this we are able save memory
    by using for this set same objects that are used in 'sroutines' sets
    for statements of which this stored routine consists.
  */
  HASH m_sroutines;


  /////////////////////////////////////////////////////////////////////////
  // Trigger-specific public attributes.
  /////////////////////////////////////////////////////////////////////////

  /**
    List of item (Item_trigger_field objects)'s lists representing fields
    in old/new version of row in trigger. We use this list for checking
    whether all such fields are valid or not at trigger creation time and
    for binding these fields to TABLE object at table open (although for
    latter pointer to table being opened is probably enough).
  */
  SQL_I_List<SQL_I_List<Item_trigger_field> > m_list_of_trig_fields_item_lists;
  /**
    List of all the Item_trigger_field items created while parsing
    sp instruction. After parsing, in add_instr method this list
    is moved to per instruction Item_trigger_field list
    "sp_lex_instr::m_trig_field_list".
  */
  SQL_I_List<Item_trigger_field> m_cur_instr_trig_field_items;

  /// Trigger characteristics.
  st_trg_chistics m_trg_chistics;

  /// The Table_triggers_list instance, where this trigger belongs to.
  class Table_triggers_list *m_trg_list;

public:
  static void *operator new(size_t size) throw ();
  static void operator delete(void *ptr, size_t size) throw ();

  ~sp_head();

  /// Is this routine being executed?
  bool is_invoked() const
  { return m_flags & IS_INVOKED; }

  /**
    Get the value of the SP cache version, as remembered
    when the routine was inserted into the cache.
  */
  ulong sp_cache_version() const
  { return m_sp_cache_version; }

  /// Set the value of the SP cache version.
  void set_sp_cache_version(ulong sp_cache_version)
  { m_sp_cache_version= sp_cache_version; }

  Stored_program_creation_ctx *get_creation_ctx()
  { return m_creation_ctx; }

  void set_creation_ctx(Stored_program_creation_ctx *creation_ctx)
  { m_creation_ctx= creation_ctx->clone(mem_root); }

  /// Set the body-definition start position.
  void set_body_start(THD *thd, const char *begin_ptr);

  /// Set the statement-definition (body-definition) end position.
  void set_body_end(THD *thd);


  /**
    Add instruction to SP.

    @param thd    Thread context.
    @param instr  Instruction.

    @return Error status.
  */
  bool add_instr(THD *thd, sp_instr *instr);

  /**
    Returns true if any substatement in the routine directly
    (not through another routine) modifies data/changes table.

    @sa Comment for MODIFIES_DATA flag.
  */
  bool modifies_data() const
  { return m_flags & MODIFIES_DATA; }

  uint instructions()
  { return m_instructions.elements(); }

  sp_instr *last_instruction()
  { return *m_instructions.back(); }

  /**
    Reset LEX-object during parsing, before we parse a sub statement.

    @param thd  Thread context.

    @return Error status.
  */
  bool reset_lex(THD *thd);

  /**
    Restore LEX-object during parsing, after we have parsed a sub statement.

    @param thd  Thread context.

    @return Error status.
  */
  bool restore_lex(THD *thd);

  char *name(uint *lenp = 0) const
  {
    if (lenp)
      *lenp= (uint) m_name.length;
    return m_name.str;
  }

  char *create_string(THD *thd, ulong *lenp);

  void set_info(longlong created,
                longlong modified,
		st_sp_chistics *chistics,
                sql_mode_t sql_mode);

  void set_definer(const char *definer, uint definerlen);
  void set_definer(const LEX_STRING *user_name, const LEX_STRING *host_name);

  /**
    Helper used during flow analysis during code optimization.
    See the implementation of <code>opt_mark()</code>.
    @param ip the instruction to add to the leads list
    @param leads the list of remaining paths to explore in the graph that
    represents the code, during flow analysis.
  */
  void add_mark_lead(uint ip, List<sp_instr> *leads);

  /**
    Get SP-instruction at given index.

    NOTE: it is important to have *unsigned* int here, sometimes we get (-1)
    passed here, so it get's converted to MAX_INT, and the result of the
    function call is NULL.
  */
  sp_instr *get_instr(uint i)
  {
    return (i < (uint) m_instructions.elements()) ? m_instructions.at(i) : NULL;
  }

  /**
    Add tables used by routine to the table list.

      Converts multi-set of tables used by this routine to table list and adds
      this list to the end of table list specified by 'query_tables_last_ptr'.

      Elements of list will be allocated in PS memroot, so this list will be
      persistent between PS executions.

    @param[in] thd                        Thread context
    @param[in,out] query_tables_last_ptr  Pointer to the next_global member of
                                          last element of the list where tables
                                          will be added (or to its root).
    @param[in] belong_to_view             Uppermost view which uses this routine,
                                          NULL if none.

    @retval true  if some elements were added
    @retval false otherwise.
  */
  bool add_used_tables_to_table_list(THD *thd,
                                     TABLE_LIST ***query_tables_last_ptr,
                                     TABLE_LIST *belong_to_view);

  /**
    Check if this stored routine contains statements disallowed
    in a stored function or trigger, and set an appropriate error message
    if this is the case.
  */
  bool is_not_allowed_in_function(const char *where)
  {
    if (m_flags & CONTAINS_DYNAMIC_SQL)
      my_error(ER_STMT_NOT_ALLOWED_IN_SF_OR_TRG, MYF(0), "Dynamic SQL");
    else if (m_flags & MULTI_RESULTS)
      my_error(ER_SP_NO_RETSET, MYF(0), where);
    else if (m_flags & HAS_SET_AUTOCOMMIT_STMT)
      my_error(ER_SP_CANT_SET_AUTOCOMMIT, MYF(0));
    else if (m_flags & HAS_COMMIT_OR_ROLLBACK)
      my_error(ER_COMMIT_NOT_ALLOWED_IN_SF_OR_TRG, MYF(0));
    else if (m_flags & HAS_SQLCOM_RESET)
      my_error(ER_STMT_NOT_ALLOWED_IN_SF_OR_TRG, MYF(0), "RESET");
    else if (m_flags & HAS_SQLCOM_FLUSH)
      my_error(ER_STMT_NOT_ALLOWED_IN_SF_OR_TRG, MYF(0), "FLUSH");

    return MY_TEST(m_flags &
                   (CONTAINS_DYNAMIC_SQL|MULTI_RESULTS|HAS_SET_AUTOCOMMIT_STMT|
                    HAS_COMMIT_OR_ROLLBACK|HAS_SQLCOM_RESET|HAS_SQLCOM_FLUSH));
  }

  /*
    This method is intended for attributes of a routine which need
    to propagate upwards to the Query_tables_list of the caller (when
    a property of a sp_head needs to "taint" the calling statement).
  */
  void propagate_attributes(Query_tables_list *prelocking_ctx)
  {
    /*
      If this routine needs row-based binary logging, the entire top statement
      too (we cannot switch from statement-based to row-based only for this
      routine, as in statement-based the top-statement may be binlogged and
      the sub-statements not).
    */
    DBUG_PRINT("info", ("lex->get_stmt_unsafe_flags(): 0x%x",
                        prelocking_ctx->get_stmt_unsafe_flags()));
    DBUG_PRINT("info", ("sp_head(0x%p=%s)->unsafe_flags: 0x%x",
                        this, name(), unsafe_flags));
    prelocking_ctx->set_stmt_unsafe_flags(unsafe_flags);
  }

  /**
    @return root parsing context for this stored program.
  */
  sp_pcontext *get_root_parsing_context() const
  { return const_cast<sp_pcontext *> (m_root_parsing_ctx); }

  /**
    @return SP-persistent mem-root. Instructions and expressions are stored in
    its memory between executions.
  */
  MEM_ROOT *get_persistent_mem_root() const
  { return const_cast<MEM_ROOT *> (&main_mem_root); }

  /**
    @return currently used mem-root.
  */
  MEM_ROOT *get_current_mem_root() const
  { return const_cast<MEM_ROOT *> (mem_root); }

  /**
    Check if a user has access right to a SP.

    @param      thd          Thread context.
    @param[out] full_access  Set to 1 if the user has SELECT
                             to the 'mysql.proc' table or is
                             the owner of the stored program.

    @return Error status.
  */
  bool check_show_access(THD *thd, bool *full_access);

private:
  /// Use sp_start_parsing() to create instances of sp_head.
  sp_head(enum_sp_type type);

  /// SP-persistent memory root (for instructions and expressions).
  MEM_ROOT main_mem_root;

  /// Root parsing context (topmost BEGIN..END block) of this SP.
  sp_pcontext *m_root_parsing_ctx;

  /// The SP-instructions.
  Dynamic_array<sp_instr *> m_instructions;

  /**
    Multi-set representing optimized list of tables to be locked by this
    routine. Does not include tables which are used by invoked routines.

    @note
    For prelocking-free SPs this multiset is constructed too.
    We do so because the same instance of sp_head may be called both
    in prelocked mode and in non-prelocked mode.
  */
  HASH m_sptabs;

  /**
    Version of the stored routine cache at the moment when the
    routine was added to it. Is used only for functions and
    procedures, not used for triggers or events.  When sp_head is
    created, its version is 0. When it's added to the cache, the
    version is assigned the global value 'Cversion'.
    If later on Cversion is incremented, we know that the routine
    is obsolete and should not be used --
    sp_cache_flush_obsolete() will purge it.
  */
  ulong m_sp_cache_version;

  /// Snapshot of several system variables at CREATE-time.
  Stored_program_creation_ctx *m_creation_ctx;

  /// Flags of LEX::enum_binlog_stmt_unsafe.
  uint32 unsafe_flags;

private:
  /// Copy sp name from parser.
  void init_sp_name(THD *thd, sp_name *spname);


  /**
    Merge the list of tables used by some query into the multi-set of
    tables used by routine.

    @param thd                 Thread context.
    @param table               Table list.
    @param lex_for_tmp_check   LEX of the query for which we are merging
                               table list.

    @note
      This method will use LEX provided to check whenever we are creating
      temporary table and mark it as such in target multi-set.

    @return Error status.
  */
  bool merge_table_list(THD *thd, TABLE_LIST *table, LEX *lex_for_tmp_check);

  friend sp_head *sp_start_parsing(THD *, enum_sp_type, sp_name *);

  // Prevent use of copy constructor and assignment operator.
  sp_head(const sp_head &);
  void operator=(sp_head &);
};

///////////////////////////////////////////////////////////////////////////

/**
  @} (end of group Stored_Routines)
*/

#endif /* _SP_HEAD_H_ */
