/*
   Copyright (c) 2002, 2014, Oracle and/or its affiliates. All rights reserved.

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

#include "my_global.h"         // NO_EMBEDDED_ACCESS_CHECKS
#include "sql_priv.h"
#include "unireg.h"
#include "sql_prepare.h"
#include "probes_mysql.h"
#include "sql_show.h"          // append_identifier
#include "sql_db.h"            // mysql_opt_change_db, mysql_change_db
#include "sql_table.h"         // prepare_create_field
#include "sql_acl.h"           // *_ACL
#include "sql_array.h"         // Dynamic_array

#include "sp_head.h"
#include "sp_instr.h"
#include "sp.h"
#include "sp_pcontext.h"
#include "set_var.h"
#include "sql_parse.h"         // cleanup_items
#include "sql_base.h"          // close_thread_tables
#include "global_threads.h"

#include <my_user.h>           // parse_user

/**
  SP_TABLE represents all instances of one table in an optimized multi-set of
  tables used by a stored program.
*/
struct SP_TABLE
{
  /*
    Multi-set key:
      db_name\0table_name\0alias\0 - for normal tables
      db_name\0table_name\0        - for temporary tables
    Note that in both cases we don't take last '\0' into account when
    we count length of key.
  */
  LEX_STRING qname;
  uint db_length, table_name_length;
  bool temp;               /* true if corresponds to a temporary table */
  thr_lock_type lock_type; /* lock type used for prelocking */
  uint lock_count;
  uint query_lock_count;
  uint8 trg_event_map;
};


///////////////////////////////////////////////////////////////////////////
// Static function implementations.
///////////////////////////////////////////////////////////////////////////


uchar *sp_table_key(const uchar *ptr, size_t *plen, my_bool first)
{
  SP_TABLE *tab= (SP_TABLE *)ptr;
  *plen= tab->qname.length;
  return (uchar *)tab->qname.str;
}



///////////////////////////////////////////////////////////////////////////
// sp_name implementation.
///////////////////////////////////////////////////////////////////////////

/**
  Init the qualified name from the db and name.
*/
void sp_name::init_qname(THD *thd)
{
  const uint dot= !!m_db.length;
  /* m_qname format: [database + dot] + name + '\0' */
  m_qname.length= m_db.length + dot + m_name.length;
  if (!(m_qname.str= (char*) thd->alloc(m_qname.length + 1)))
    return;
  sprintf(m_qname.str, "%.*s%.*s%.*s",
          (int) m_db.length, (m_db.length ? m_db.str : ""),
          dot, ".",
          (int) m_name.length, m_name.str);
}

///////////////////////////////////////////////////////////////////////////
// sp_head implementation.
///////////////////////////////////////////////////////////////////////////

void *sp_head::operator new(size_t size) throw()
{
  MEM_ROOT own_root;

  init_sql_alloc(&own_root, MEM_ROOT_BLOCK_SIZE, MEM_ROOT_PREALLOC);

  sp_head *sp= (sp_head *) alloc_root(&own_root, size);
  if (!sp)
    return NULL;

  sp->main_mem_root= own_root;
  DBUG_PRINT("info", ("mem_root 0x%lx", (ulong) &sp->mem_root));
  return sp;
}

void sp_head::operator delete(void *ptr, size_t size) throw()
{
  if (!ptr)
    return;

  sp_head *sp= (sp_head *) ptr;

  /* Make a copy of main_mem_root as free_root will free the sp */
  MEM_ROOT own_root= sp->main_mem_root;
  DBUG_PRINT("info", ("mem_root 0x%lx moved to 0x%lx",
                      (ulong) &sp->mem_root, (ulong) &own_root));
  free_root(&own_root, MYF(0));
}


sp_head::sp_head(enum_sp_type type)
 :Query_arena(&main_mem_root, STMT_INITIALIZED_FOR_SP),
  m_type(type),
  m_flags(0),
  m_chistics(NULL),
  m_sql_mode(0),
  m_explicit_name(false),
  m_created(0),
  m_modified(0),
  m_recursion_level(0),
  m_next_cached_sp(NULL),
  m_first_instance(NULL),
  m_first_free_instance(NULL),
  m_last_cached_sp(NULL),
  m_trg_list(NULL),
  m_root_parsing_ctx(NULL),
  m_sp_cache_version(0),
  m_creation_ctx(NULL),
  unsafe_flags(0)
{
  m_first_instance= this;
  m_first_free_instance= this;
  m_last_cached_sp= this;

  m_return_field_def.charset = NULL;

  /*
    FIXME: the only use case when name is NULL is events, and it should
    be rewritten soon. Remove the else part and replace 'if' with
    an assert when this is done.
  */

  m_db= NULL_STR;
  m_name= NULL_STR;
  m_qname= NULL_STR;

  m_params= NULL_STR;

  m_defstr= NULL_STR;
  m_body= NULL_STR;
  m_body_utf8= NULL_STR;

  my_hash_init(&m_sptabs, system_charset_info, 0, 0, 0, sp_table_key, 0, 0);
}


void sp_head::init_sp_name(THD *thd, sp_name *spname)
{
  /* Must be initialized in the parser. */

  DBUG_ASSERT(spname && spname->m_db.str && spname->m_db.length);

  /* We have to copy strings to get them into the right memroot. */

  m_db.length= spname->m_db.length;
  m_db.str= strmake_root(thd->mem_root, spname->m_db.str, spname->m_db.length);

  m_name.length= spname->m_name.length;
  m_name.str= strmake_root(thd->mem_root, spname->m_name.str,
                           spname->m_name.length);

  m_explicit_name= spname->m_explicit_name;

  if (spname->m_qname.length == 0)
    spname->init_qname(thd);

  m_qname.length= spname->m_qname.length;
  m_qname.str= (char*) memdup_root(thd->mem_root,
                                   spname->m_qname.str,
                                   spname->m_qname.length + 1);
}


void sp_head::set_body_start(THD *thd, const char *begin_ptr)
{
  m_parser_data.set_body_start_ptr(begin_ptr);

  thd->m_parser_state->m_lip.body_utf8_start(thd, begin_ptr);
}


void sp_head::set_body_end(THD *thd)
{
  Lex_input_stream *lip= & thd->m_parser_state->m_lip; /* shortcut */
  const char *end_ptr= lip->get_cpp_ptr(); /* shortcut */

  /* Make the string of parameters. */

  {
    const char *p_start= m_parser_data.get_parameter_start_ptr();
    const char *p_end= m_parser_data.get_parameter_end_ptr();

    if (p_start && p_end)
    {
      m_params.length= p_end - p_start;
      m_params.str= thd->strmake(p_start, m_params.length);
    }
  }

  /* Remember end pointer for further dumping of whole statement. */

  thd->lex->stmt_definition_end= end_ptr;

  /* Make the string of body (in the original character set). */

  m_body.length= end_ptr - m_parser_data.get_body_start_ptr();
  m_body.str= thd->strmake(m_parser_data.get_body_start_ptr(), m_body.length);
  trim_whitespace(thd->charset(), & m_body);

  /* Make the string of UTF-body. */

  lip->body_utf8_append(end_ptr);

  m_body_utf8.length= lip->get_body_utf8_length();
  m_body_utf8.str= thd->strmake(lip->get_body_utf8_str(), m_body_utf8.length);
  trim_whitespace(thd->charset(), & m_body_utf8);

  /*
    Make the string of whole stored-program-definition query (in the
    original character set).
  */

  m_defstr.length= end_ptr - lip->get_cpp_buf();
  m_defstr.str= thd->strmake(lip->get_cpp_buf(), m_defstr.length);
  trim_whitespace(thd->charset(), & m_defstr);
}


sp_head::~sp_head()
{
  LEX *lex;
  sp_instr *i;

  // Parsing of SP-body must have been already finished.
  DBUG_ASSERT(!m_parser_data.is_parsing_sp_body());

  for (uint ip = 0 ; (i = get_instr(ip)) ; ip++)
    delete i;

  delete m_root_parsing_ctx;

  free_items();

  /*
    If we have non-empty LEX stack then we just came out of parser with
    error. Now we should delete all auxiliary LEXes and restore original
    THD::lex. It is safe to not update LEX::ptr because further query
    string parsing and execution will be stopped anyway.
  */
  while ((lex= (LEX *) m_parser_data.pop_lex()))
  {
    THD *thd= lex->thd;
    thd->lex->sphead= NULL;
    lex_end(thd->lex);
    delete thd->lex;
    thd->lex= lex;
  }

  my_hash_free(&m_sptabs);

  delete m_next_cached_sp;
}

bool sp_head::reset_lex(THD *thd)
{
  LEX *oldlex= thd->lex;

  LEX *sublex= new (thd->mem_root)st_lex_local;

  if (!sublex)
    return true;

  thd->lex= sublex;
  m_parser_data.push_lex(oldlex);

  /* Reset most stuff. */
  lex_start(thd);

  /* And keep the SP stuff too */
  sublex->sphead= oldlex->sphead;
  sublex->set_sp_current_parsing_ctx(oldlex->get_sp_current_parsing_ctx());
  sublex->sp_lex_in_use= FALSE;

  /* Reset type info. */

  sublex->charset= NULL;
  sublex->length= NULL;
  sublex->dec= NULL;
  sublex->interval_list.empty();
  sublex->type= 0;

  /* Reset part of parser state which needs this. */
  thd->m_parser_state->m_yacc.reset_before_substatement();

  return false;
}


bool sp_head::restore_lex(THD *thd)
{
  LEX *sublex= thd->lex;

  sublex->set_trg_event_type_for_tables();

  LEX *oldlex= (LEX *) m_parser_data.pop_lex();

  if (!oldlex)
    return false; // Nothing to restore

  /* If this substatement is unsafe, the entire routine is too. */
  DBUG_PRINT("info", ("lex->get_stmt_unsafe_flags: 0x%x",
                      thd->lex->get_stmt_unsafe_flags()));
  unsafe_flags|= sublex->get_stmt_unsafe_flags();

  /*
    Add routines which are used by statement to respective set for
    this routine.
  */
 // if (sp_update_sp_used_routines(&m_sroutines, &sublex->sroutines))
 //   return true;

  /* If this substatement is a update query, then mark MODIFIES_DATA */
  if (is_update_query(sublex->sql_command))
    m_flags|= MODIFIES_DATA;

  /*
    Merge tables used by this statement (but not by its functions or
    procedures) to multiset of tables used by this routine.
  */
  merge_table_list(thd, sublex->query_tables, sublex);

  if (!sublex->sp_lex_in_use)
  {
    sublex->sphead= NULL;
    lex_end(sublex);
    delete sublex;
  }

  thd->lex= oldlex;
  return false;
}



bool sp_head::add_instr(THD *thd, sp_instr *instr)
{
  m_parser_data.process_new_sp_instr(thd, instr);

  if (m_type == SP_TYPE_TRIGGER && m_cur_instr_trig_field_items.elements)
  {
    SQL_I_List<Item_trigger_field> *instr_trig_fld_list;
    /*
      Move all the Item_trigger_field from "sp_head::
      m_cur_instr_trig_field_items" to the per instruction Item_trigger_field
      list "sp_lex_instr::m_trig_field_list" and clear "sp_head::
      m_cur_instr_trig_field_items".
    */
    if ((instr_trig_fld_list= instr->get_instr_trig_field_list()) != NULL)
    {
      m_cur_instr_trig_field_items.save_and_clear(instr_trig_fld_list);
      m_list_of_trig_fields_item_lists.link_in_list(instr_trig_fld_list,
        &instr_trig_fld_list->first->next_trig_field_list);
    }
  }

  /*
    Memory root of every instruction is designated for permanent
    transformations (optimizations) made on the parsed tree during
    the first execution. It points to the memory root of the
    entire stored procedure, as their life span is equal.
  */
  instr->mem_root= get_persistent_mem_root();

  return m_instructions.append(instr);
}

bool sp_head::merge_table_list(THD *thd,
                               TABLE_LIST *table,
                               LEX *lex_for_tmp_check)
{
  if (lex_for_tmp_check->sql_command == SQLCOM_DROP_TABLE &&
      lex_for_tmp_check->drop_temporary)
    return true;

  for (uint i= 0 ; i < m_sptabs.records ; i++)
  {
    SP_TABLE *tab= (SP_TABLE*) my_hash_element(&m_sptabs, i);
    tab->query_lock_count= 0;
  }

  for (; table ; table= table->next_global)
    if (!table->derived && !table->schema_table)
    {
      /*
        Structure of key for the multi-set is "db\0table\0alias\0".
        Since "alias" part can have arbitrary length we use String
        object to construct the key. By default String will use
        buffer allocated on stack with NAME_LEN bytes reserved for
        alias, since in most cases it is going to be smaller than
        NAME_LEN bytes.
      */
      char tname_buff[(NAME_LEN + 1) * 3];
      String tname(tname_buff, sizeof(tname_buff), &my_charset_bin);
      uint temp_table_key_length;

      tname.length(0);
      tname.append(table->db, table->db_length);
      tname.append('\0');
      tname.append(table->table_name, table->table_name_length);
      tname.append('\0');
      temp_table_key_length= tname.length();
      tname.append(table->alias);
      tname.append('\0');

      /*
        Upgrade the lock type because this table list will be used
        only in pre-locked mode, in which DELAYED inserts are always
        converted to normal inserts.
      */
      if (table->lock_type == TL_WRITE_DELAYED)
        table->lock_type= TL_WRITE;

      /*
        We ignore alias when we check if table was already marked as temporary
        (and therefore should not be prelocked). Otherwise we will erroneously
        treat table with same name but with different alias as non-temporary.
      */

      SP_TABLE *tab;

      if ((tab= (SP_TABLE*) my_hash_search(&m_sptabs, (uchar *)tname.ptr(),
                                           tname.length())) ||
          ((tab= (SP_TABLE*) my_hash_search(&m_sptabs, (uchar *)tname.ptr(),
                                            temp_table_key_length)) &&
           tab->temp))
      {
        if (tab->lock_type < table->lock_type)
          tab->lock_type= table->lock_type; // Use the table with the highest lock type
        tab->query_lock_count++;
        if (tab->query_lock_count > tab->lock_count)
          tab->lock_count++;
        tab->trg_event_map|= table->trg_event_map;
      }
      else
      {
        if (!(tab= (SP_TABLE *)thd->calloc(sizeof(SP_TABLE))))
          return false;
        if (lex_for_tmp_check->sql_command == SQLCOM_CREATE_TABLE &&
            lex_for_tmp_check->query_tables == table &&
            lex_for_tmp_check->create_info.options & HA_LEX_CREATE_TMP_TABLE)
        {
          tab->temp= true;
          tab->qname.length= temp_table_key_length;
        }
        else
          tab->qname.length= tname.length();
        tab->qname.str= (char*) thd->memdup(tname.ptr(), tab->qname.length);
        if (!tab->qname.str)
          return false;
        tab->table_name_length= table->table_name_length;
        tab->db_length= table->db_length;
        tab->lock_type= table->lock_type;
        tab->lock_count= tab->query_lock_count= 1;
        tab->trg_event_map= table->trg_event_map;
        if (my_hash_insert(&m_sptabs, (uchar *)tab))
          return false;
      }
    }
  return true;
}


bool sp_head::add_used_tables_to_table_list(THD *thd,
                                            TABLE_LIST ***query_tables_last_ptr,
                                            TABLE_LIST *belong_to_view)
{
  bool result= false;

  /*
    Use persistent arena for table list allocation to be PS/SP friendly.
    Note that we also have to copy database/table names and alias to PS/SP
    memory since current instance of sp_head object can pass away before
    next execution of PS/SP for which tables are added to prelocking list.
    This will be fixed by introducing of proper invalidation mechanism
    once new TDC is ready.
  */
  Prepared_stmt_arena_holder ps_arena_holder(thd);

  for (uint i= 0; i < m_sptabs.records; i++)
  {
    char *tab_buff, *key_buff;
    SP_TABLE *stab= (SP_TABLE*) my_hash_element(&m_sptabs, i);
    if (stab->temp)
      continue;

    if (!(tab_buff= (char *)thd->calloc(ALIGN_SIZE(sizeof(TABLE_LIST)) *
                                        stab->lock_count)) ||
        !(key_buff= (char*)thd->memdup(stab->qname.str,
                                       stab->qname.length)))
      return false;

    for (uint j= 0; j < stab->lock_count; j++)
    {
      TABLE_LIST *table= (TABLE_LIST *)tab_buff;

      table->db= key_buff;
      table->db_length= stab->db_length;
      table->table_name= table->db + table->db_length + 1;
      table->table_name_length= stab->table_name_length;
      table->alias= table->table_name + table->table_name_length + 1;
      table->lock_type= stab->lock_type;
      table->cacheable_table= 1;
      table->prelocking_placeholder= 1;
      table->belong_to_view= belong_to_view;
      table->trg_event_map= stab->trg_event_map;

      /* Everyting else should be zeroed */

      **query_tables_last_ptr= table;
      table->prev_global= *query_tables_last_ptr;
      *query_tables_last_ptr= &table->next_global;

      tab_buff+= ALIGN_SIZE(sizeof(TABLE_LIST));
      result= true;
    }
  }

  return result;
}


///////////////////////////////////////////////////////////////////////////
// sp_parser_data implementation.
///////////////////////////////////////////////////////////////////////////


void sp_parser_data::start_parsing_sp_body(THD *thd, sp_head *sp)
{
  m_saved_memroot= thd->mem_root;
  m_saved_free_list= thd->free_list;

  thd->mem_root= sp->get_persistent_mem_root();
  thd->free_list= NULL;
}


bool sp_parser_data::add_backpatch_entry(sp_branch_instr *i,
                                         sp_label *label)
{
  Backpatch_info *bp= (Backpatch_info *)sql_alloc(sizeof(Backpatch_info));

  if (!bp)
    return true;

  bp->label= label;
  bp->instr= i;
  return m_backpatch.push_front(bp);
}


void sp_parser_data::do_backpatch(sp_label *label, uint dest)
{
  Backpatch_info *bp;
  List_iterator_fast<Backpatch_info> li(m_backpatch);

  while ((bp= li++))
  {
    if (bp->label == label)
      bp->instr->backpatch(dest);
  }
}


bool sp_parser_data::add_cont_backpatch_entry(sp_lex_branch_instr *i)
{
  i->set_cont_dest(m_cont_level);
  return m_cont_backpatch.push_front(i);
}


void sp_parser_data::do_cont_backpatch(uint dest)
{
  sp_lex_branch_instr *i;

  while ((i= m_cont_backpatch.head()) && i->get_cont_dest() == m_cont_level)
  {
    i->set_cont_dest(dest);
    m_cont_backpatch.pop();
  }

  --m_cont_level;
}


void sp_parser_data::process_new_sp_instr(THD* thd, sp_instr *i)
{
  /*
    thd->free_list should be cleaned here because it's implicitly expected
    that that process_new_sp_instr() (called from sp_head::add_instr) is
    called as the last action after parsing the SP-instruction's SQL query.

    Thus, at this point thd->free_list contains all Item-objects, created for
    this SP-instruction.

    Next SP-instruction should start its own free-list from the scratch.
  */

  i->free_list= thd->free_list;

  thd->free_list= NULL;
}
