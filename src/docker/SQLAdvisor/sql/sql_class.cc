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
   Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA
*/


/*****************************************************************************
**
** This file implements classes defined in sql_class.h
** Especially the classes to handle a result from a select
**
*****************************************************************************/

#include "my_global.h"                          /* NO_EMBEDDED_ACCESS_CHECKS */
#include "sql_priv.h"
#include "unireg.h"                    // REQUIRED: for other includes
#include "sql_class.h"
#include "sql_base.h"                           // close_thread_tables
#include "sql_time.h"                         // date_time_format_copy
#include "sql_handler.h"                      // mysql_ha_cleanup
#include <my_bitmap.h>
#include <m_ctype.h>
#include <sys/stat.h>
#include <thr_alarm.h>
#ifdef	__WIN__
#include <io.h>
#endif
#include <mysys_err.h>
#include <limits.h>

#include "sql_parse.h"                          // is_update_query
#include "sql_callback.h"
#include "mysqld.h"

#include <mysql/psi/mysql_statement.h>

using std::min;
using std::max;
/*
  The following is used to initialise Table_ident with a internal
  table name
*/
char internal_table_name[2]= "*";
char empty_c_string[1]= {0};    /* used for not defined db */

LEX_STRING EMPTY_STR= { (char *) "", 0 };
LEX_STRING NULL_STR=  { NULL, 0 };

const char * const THD::DEFAULT_WHERE= "field list";

/****************************************************************************
** User variables
****************************************************************************/

extern "C" uchar *get_var_key(user_var_entry *entry, size_t *length,
                              my_bool not_used __attribute__((unused)))
{
  *length= entry->entry_name.length();
  return (uchar*) entry->entry_name.ptr();
}

extern "C" void free_user_var(user_var_entry *entry)
{
  entry->destroy();
}

bool Key_part_spec::operator==(const Key_part_spec& other) const
{
  return length == other.length &&
         !my_strcasecmp(system_charset_info, field_name.str,
                        other.field_name.str);
}

/**
  Construct an (almost) deep copy of this key. Only those
  elements that are known to never change are not copied.
  If out of memory, a partial copy is returned and an error is set
  in THD.
*/

Key::Key(const Key &rhs, MEM_ROOT *mem_root)
  :type(rhs.type),
  key_create_info(rhs.key_create_info),
  columns(rhs.columns, mem_root),
  name(rhs.name),
  generated(rhs.generated)
{
  list_copy_and_replace_each_value(columns, mem_root);
}

/**
  Construct an (almost) deep copy of this foreign key. Only those
  elements that are known to never change are not copied.
  If out of memory, a partial copy is returned and an error is set
  in THD.
*/

Foreign_key::Foreign_key(const Foreign_key &rhs, MEM_ROOT *mem_root)
  :Key(rhs, mem_root),
  ref_db(rhs.ref_db),
  ref_table(rhs.ref_table),
  ref_columns(rhs.ref_columns, mem_root),
  delete_opt(rhs.delete_opt),
  update_opt(rhs.update_opt),
  match_opt(rhs.match_opt)
{
  list_copy_and_replace_each_value(ref_columns, mem_root);
}

/*
  Test if a foreign key (= generated key) is a prefix of the given key
  (ignoring key name, key type and order of columns)

  NOTES:
    This is only used to test if an index for a FOREIGN KEY exists

  IMPLEMENTATION
    We only compare field names

  RETURN
    0	Generated key is a prefix of other key
    1	Not equal
*/

bool foreign_key_prefix(Key *a, Key *b)
{
  /* Ensure that 'a' is the generated key */
  if (a->generated)
  {
    if (b->generated && a->columns.elements > b->columns.elements)
      swap_variables(Key*, a, b);               // Put shorter key in 'a'
  }
  else
  {
    if (!b->generated)
      return TRUE;                              // No foreign key
    swap_variables(Key*, a, b);                 // Put generated key in 'a'
  }

  /* Test if 'a' is a prefix of 'b' */
  if (a->columns.elements > b->columns.elements)
    return TRUE;                                // Can't be prefix

  List_iterator<Key_part_spec> col_it1(a->columns);
  List_iterator<Key_part_spec> col_it2(b->columns);
  const Key_part_spec *col1, *col2;

#ifdef ENABLE_WHEN_INNODB_CAN_HANDLE_SWAPED_FOREIGN_KEY_COLUMNS
  while ((col1= col_it1++))
  {
    bool found= 0;
    col_it2.rewind();
    while ((col2= col_it2++))
    {
      if (*col1 == *col2)
      {
        found= TRUE;
	break;
      }
    }
    if (!found)
      return TRUE;                              // Error
  }
  return FALSE;                                 // Is prefix
#else
  while ((col1= col_it1++))
  {
    col2= col_it2++;
    if (!(*col1 == *col2))
      return TRUE;
  }
  return FALSE;                                 // Is prefix
#endif
}


/****************************************************************************
** Thread specific functions
****************************************************************************/
/**
  Set the state on connection to killed

  @param thd               THD object
*/
void thd_set_killed(THD *thd)
{
  thd->killed= THD::KILL_CONNECTION;
}

/**
  Clear errors from the previous THD

  @param thd              THD object
*/
void thd_clear_errors(THD *thd)
{
  my_errno= 0;
  thd->mysys_var->abort= 0;
}

/**
  Set thread stack in THD object

  @param thd              Thread object
  @param stack_start      Start of stack to set in THD object
*/
void thd_set_thread_stack(THD *thd, char *stack_start)
{
  thd->thread_stack= stack_start;
}
/**
  Close the socket used by this connection

  @param thd                THD object
*/
void thd_close_connection(THD *thd)
{
  if (thd->net.vio)
    vio_shutdown(thd->net.vio, SHUT_RDWR);
}

/**
  Check if there is buffered data on the socket representing the connection

  @param thd                  THD object
*/
int thd_connection_has_data(THD *thd)
{
  Vio *vio= thd->net.vio;
  return vio->has_data(vio);
}

/**
  Set reading/writing on socket, used by SHOW PROCESSLIST

  @param thd                       THD object
  @param val                       Value to set it to (0 or 1)
*/
void thd_set_net_read_write(THD *thd, uint val)
{
  thd->net.reading_or_writing= val;
}

/**
  Get reading/writing on socket from THD object
  @param thd                       THD object

  @retval               net.reading_or_writing value for thread on THD.
*/
uint thd_get_net_read_write(THD *thd)
{
  return thd->net.reading_or_writing;
}

/**
  Set reference to mysys variable in THD object

  @param thd             THD object
  @param mysys_var       Reference to set
*/
void thd_set_mysys_var(THD *thd, st_my_thread_var *mysys_var)
{
  thd->set_mysys_var(mysys_var);
}

/**
  Get socket file descriptor for this connection

  @param thd            THD object

  @retval               Socket of the connection
*/
my_socket thd_get_fd(THD *thd)
{
  return mysql_socket_getfd(thd->net.vio->mysql_socket);
}

/**
  Set thread specific environment required for thd cleanup in thread pool.

  @param thd            THD object

  @retval               1 if thread-specific enviroment could be set else 0
*/
int thd_store_globals(THD* thd)
{
  return thd->store_globals();
}


extern "C"
int thd_in_lock_tables(const THD *thd)
{
  return MY_TEST(thd->in_lock_tables);
}


extern "C"
int thd_tablespace_op(const THD *thd)
{
  return MY_TEST(thd->tablespace_op);
}


extern "C"
const char *set_thd_proc_info(void *thd_arg, const char *info,
                              const char *calling_function,
                              const char *calling_file,
                              const unsigned int calling_line)
{
  PSI_stage_info old_stage;
  PSI_stage_info new_stage;

  old_stage.m_key= 0;
  old_stage.m_name= info;

  set_thd_stage_info(thd_arg, & old_stage, & new_stage,
                     calling_function, calling_file, calling_line);

  return new_stage.m_name;
}

extern "C"
void set_thd_stage_info(void *opaque_thd,
                        const PSI_stage_info *new_stage,
                        PSI_stage_info *old_stage,
                        const char *calling_func,
                        const char *calling_file,
                        const unsigned int calling_line)
{
  THD *thd= (THD*) opaque_thd;
  if (thd == NULL)
    thd= current_thd;

  thd->enter_stage(new_stage, old_stage, calling_func, calling_file, calling_line);
}

void THD::enter_stage(const PSI_stage_info *new_stage,
                      PSI_stage_info *old_stage,
                      const char *calling_func,
                      const char *calling_file,
                      const unsigned int calling_line)
{
  DBUG_PRINT("THD::enter_stage", ("%s:%d", calling_file, calling_line));

  if (old_stage != NULL)
  {
    old_stage->m_key= m_current_stage_key;
    old_stage->m_name= proc_info;
  }

  if (new_stage != NULL)
  {
    const char *msg= new_stage->m_name;

    m_current_stage_key= new_stage->m_key;
    proc_info= msg;

    MYSQL_SET_STAGE(m_current_stage_key, calling_file, calling_line);
  }
  return;
}

extern "C"
long long thd_test_options(const THD *thd, long long test_options)
{
  return thd->variables.option_bits & test_options;
}

extern "C"
int thd_sql_command(const THD *thd)
{
  return (int) thd->lex->sql_command;
}

extern "C"
int thd_tx_isolation(const THD *thd)
{
  return (int) thd->tx_isolation;
}

extern "C"
int thd_tx_is_read_only(const THD *thd)
{
  return (int) thd->tx_read_only;
}

extern "C"
void thd_inc_row_count(THD *thd)
{
  thd->get_stmt_da()->inc_current_row_for_warning();
}

extern "C"
unsigned long thd_log_slow_verbosity(const THD *thd)
{
  return (unsigned long) thd->variables.log_slow_verbosity;
}


/* extend for kill session of idle transaction from engine */
extern "C"
int thd_command(const THD* thd)
{
  return (int) thd->get_command();
}

/**
  Implementation of Drop_table_error_handler::handle_condition().
  The reason in having this implementation is to silence technical low-level
  warnings during DROP TABLE operation. Currently we don't want to expose
  the following warnings during DROP TABLE:
    - Some of table files are missed or invalid (the table is going to be
      deleted anyway, so why bother that something was missed);
    - A trigger associated with the table does not have DEFINER (One of the
      MySQL specifics now is that triggers are loaded for the table being
      dropped. So, we may have a warning that trigger does not have DEFINER
      attribute during DROP TABLE operation).

  @return TRUE if the condition is handled.
*/
bool Drop_table_error_handler::handle_condition(THD *thd,
                                                uint sql_errno,
                                                const char* sqlstate,
                                                Sql_condition::enum_warning_level level,
                                                const char* msg,
                                                Sql_condition ** cond_hdl)
{
  *cond_hdl= NULL;
  return ((sql_errno == EE_DELETE && my_errno == ENOENT) ||
          sql_errno == ER_TRG_NO_DEFINER);
}


THD::THD(bool enable_plugins)
   :Statement(&main_lex, &main_mem_root, STMT_CONVENTIONAL_EXECUTION,
              /* statement id */ 0),
   in_sub_stmt(0),
   fill_status_recursion_level(0),
   order_deterministic(false),
   table_map_for_update(0),
   arg_of_last_insert_id_function(FALSE),
   first_successful_insert_id_in_prev_stmt(0),
   first_successful_insert_id_in_prev_stmt_for_binlog(0),
   first_successful_insert_id_in_cur_stmt(0),
   stmt_depends_on_first_successful_insert_id_in_prev_stmt(FALSE),
   m_statement_psi(NULL),
   m_idle_psi(NULL),
   m_server_idle(false),
   is_fatal_error(0),
   transaction_rollback_request(0),
   is_fatal_sub_stmt_error(0),
   rand_used(0),
   time_zone_used(0),
   in_lock_tables(0),
   bootstrap(0),
   derived_tables_processing(FALSE),
   m_parser_state(NULL),
#if defined(ENABLED_DEBUG_SYNC)
   debug_sync_control(0),
#endif /* defined(ENABLED_DEBUG_SYNC) */
   m_enable_plugins(enable_plugins),
   main_da(0, false),
   m_stmt_da(&main_da)
{
  ulong tmp;

  /*
    Pass nominal parameters to init_alloc_root only to ensure that
    the destructor works OK in case of an error. The main_mem_root
    will be re-initialized in init_for_queries().
  */
  init_sql_alloc(&main_mem_root, ALLOC_ROOT_MIN_BLOCK_SIZE, 0);
  stmt_arena= this;
  thread_stack= 0;
  skip_wait_timeout= false;
  extra_port= 0;
  catalog= (char*)"std"; // the only catalog we have for now
  main_security_ctx.init();
  security_ctx= &main_security_ctx;
  no_errors= 0;
  password= 0;
  query_start_used= query_start_usec_used= 0;
  killed= NOT_KILLED;
  col_access=0;
  is_slave_error= thread_specific_used= FALSE;
  tmp_table=0;
  cuted_fields= 0L;
  limit_found_rows= 0;
  m_row_count_func= -1;
  statement_id_counter= 0UL;
  // Must be reset to handle error with THD's created for init of mysqld
  lex->current_select= 0;
  user_time.tv_sec= 0;
  user_time.tv_usec= 0;
  start_time.tv_sec= 0;
  start_time.tv_usec= 0;
  start_utime= prior_thr_create_utime= 0L;
  utime_after_lock= 0L;
  slave_thread = 0;
  memset(&variables, 0, sizeof(variables));
  thread_id= 0;
  one_shot_set= 0;
  query_id= 0;
  query_name_consts= 0;
  db_charset= global_system_variables.collation_database;
  mysys_var=0;
  commit_error= CE_NONE;
  durability_property= HA_REGULAR_DURABILITY;
  busy_time=            0;
  cpu_time=             0;
  bytes_received=       0;
  bytes_sent=           0;
  binlog_bytes_written= 0;
  updated_row_count=    0;
  sent_row_count_2=     0;
#ifndef DBUG_OFF
  dbug_sentry=THD_SENTRY_MAGIC;
#endif
  net.vio=0;
  client_capabilities= 0;                       // minimalistic client
  system_thread= NON_SYSTEM_THREAD;
  cleanup_done= abort_on_warning= 0;
  m_release_resources_done= false;
#ifdef SIGNAL_WITH_VIO_SHUTDOWN
  active_vio = 0;
#endif
  mysql_mutex_init(key_LOCK_thd_data, &LOCK_thd_data, MY_MUTEX_INIT_FAST);

  /* Variables with default values */
  proc_info="login";
  where= THD::DEFAULT_WHERE;
  set_command(COM_CONNECT);
  *scramble= '\0';

  init();

  m_user_connect= NULL;
  my_hash_init(&user_vars, system_charset_info, USER_VARS_HASH_SIZE, 0, 0,
               (my_hash_get_key) get_var_key,
               (my_hash_free_key) free_user_var, 0);

  tablespace_op=FALSE;
  tmp= sql_rnd_with_mutex();
  randominit(&rand, tmp + (ulong) &rand, tmp);
  substitute_null_with_insert_id = FALSE;
  thr_lock_info_init(&lock_info); /* safety: will be reset after start */

  m_internal_handler= NULL;
  memset(&invoker_user, 0, sizeof(invoker_user));
  memset(&invoker_host, 0, sizeof(invoker_host));
#ifndef DBUG_OFF
  gis_debug= 0;
#endif

  timer= timer_cache= NULL;
}


void THD::push_internal_handler(Internal_error_handler *handler)
{
  if (m_internal_handler)
  {
    handler->m_prev_internal_handler= m_internal_handler;
    m_internal_handler= handler;
  }
  else
  {
    m_internal_handler= handler;
  }
}

bool THD::handle_condition(uint sql_errno,
                           const char* sqlstate,
                           Sql_condition::enum_warning_level level,
                           const char* msg,
                           Sql_condition ** cond_hdl)
{
  last_errno= sql_errno;

  if (!m_internal_handler)
  {
    *cond_hdl= NULL;
    return FALSE;
  }

  for (Internal_error_handler *error_handler= m_internal_handler;
       error_handler;
       error_handler= error_handler->m_prev_internal_handler)
  {
    if (error_handler->handle_condition(this, sql_errno, sqlstate, level, msg,
					cond_hdl))
    {
      return TRUE;
    }
  }

  return FALSE;
}


Internal_error_handler *THD::pop_internal_handler()
{
  DBUG_ASSERT(m_internal_handler != NULL);
  Internal_error_handler *popped_handler= m_internal_handler;
  m_internal_handler= m_internal_handler->m_prev_internal_handler;
  return popped_handler;
}


void THD::raise_error(uint sql_errno)
{
  const char* msg= ER(sql_errno);
  (void) raise_condition(sql_errno,
                         NULL,
                         Sql_condition::WARN_LEVEL_ERROR,
                         msg);
}

void THD::raise_error_printf(uint sql_errno, ...)
{
  va_list args;
  char ebuff[MYSQL_ERRMSG_SIZE];
  DBUG_ENTER("THD::raise_error_printf");
  DBUG_PRINT("my", ("nr: %d  errno: %d", sql_errno, errno));
  const char* format= ER(sql_errno);
  va_start(args, sql_errno);
  my_vsnprintf(ebuff, sizeof(ebuff), format, args);
  va_end(args);
  (void) raise_condition(sql_errno,
                         NULL,
                         Sql_condition::WARN_LEVEL_ERROR,
                         ebuff);
  DBUG_VOID_RETURN;
}

void THD::raise_warning(uint sql_errno)
{
  const char* msg= ER(sql_errno);
  (void) raise_condition(sql_errno,
                         NULL,
                         Sql_condition::WARN_LEVEL_WARN,
                         msg);
}

void THD::raise_warning_printf(uint sql_errno, ...)
{
  va_list args;
  char    ebuff[MYSQL_ERRMSG_SIZE];
  DBUG_ENTER("THD::raise_warning_printf");
  DBUG_PRINT("enter", ("warning: %u", sql_errno));
  const char* format= ER(sql_errno);
  va_start(args, sql_errno);
  my_vsnprintf(ebuff, sizeof(ebuff), format, args);
  va_end(args);
  (void) raise_condition(sql_errno,
                         NULL,
                         Sql_condition::WARN_LEVEL_WARN,
                         ebuff);
  DBUG_VOID_RETURN;
}

void THD::raise_note(uint sql_errno)
{
  DBUG_ENTER("THD::raise_note");
  DBUG_PRINT("enter", ("code: %d", sql_errno));
  if (!(variables.option_bits & OPTION_SQL_NOTES))
    DBUG_VOID_RETURN;
  const char* msg= ER(sql_errno);
  (void) raise_condition(sql_errno,
                         NULL,
                         Sql_condition::WARN_LEVEL_NOTE,
                         msg);
  DBUG_VOID_RETURN;
}

void THD::raise_note_printf(uint sql_errno, ...)
{
  va_list args;
  char    ebuff[MYSQL_ERRMSG_SIZE];
  DBUG_ENTER("THD::raise_note_printf");
  DBUG_PRINT("enter",("code: %u", sql_errno));
  if (!(variables.option_bits & OPTION_SQL_NOTES))
    DBUG_VOID_RETURN;
  const char* format= ER(sql_errno);
  va_start(args, sql_errno);
  my_vsnprintf(ebuff, sizeof(ebuff), format, args);
  va_end(args);
  (void) raise_condition(sql_errno,
                         NULL,
                         Sql_condition::WARN_LEVEL_NOTE,
                         ebuff);
  DBUG_VOID_RETURN;
}


struct timeval THD::query_start_timeval_trunc(uint decimals)
{
  struct timeval tv;
  tv.tv_sec= start_time.tv_sec;
  query_start_used= 1;
  if (decimals)
  {
    tv.tv_usec= start_time.tv_usec;
    my_timeval_trunc(&tv, decimals);
    query_start_usec_used= 1;
  }
  else
  {
    tv.tv_usec= 0;
  }
  return tv;
}


Sql_condition* THD::raise_condition(uint sql_errno,
                                    const char* sqlstate,
                                    Sql_condition::enum_warning_level level,
                                    const char* msg)
{
  Diagnostics_area *da= get_stmt_da();
  Sql_condition *cond= NULL;
  DBUG_ENTER("THD::raise_condition");

  if (!(variables.option_bits & OPTION_SQL_NOTES) &&
      (level == Sql_condition::WARN_LEVEL_NOTE))
    DBUG_RETURN(NULL);

  da->opt_clear_warning_info(query_id);

  /*
    TODO: replace by DBUG_ASSERT(sql_errno != 0) once all bugs similar to
    Bug#36768 are fixed: a SQL condition must have a real (!=0) error number
    so that it can be caught by handlers.
  */
  if (sql_errno == 0)
    sql_errno= ER_UNKNOWN_ERROR;
  if (msg == NULL)
    msg= ER(sql_errno);
  if (sqlstate == NULL)
   sqlstate= mysql_errno_to_sqlstate(sql_errno);

  if ((level == Sql_condition::WARN_LEVEL_WARN) &&
      really_abort_on_warning())
  {
    /*
      FIXME:
      push_warning and strict SQL_MODE case.
    */
    level= Sql_condition::WARN_LEVEL_ERROR;
    killed= THD::KILL_BAD_DATA;
  }

  switch (level)
  {
  case Sql_condition::WARN_LEVEL_NOTE:
  case Sql_condition::WARN_LEVEL_WARN:
    got_warning= 1;
    break;
  case Sql_condition::WARN_LEVEL_ERROR:
    break;
  default:
    DBUG_ASSERT(FALSE);
  }

  if (handle_condition(sql_errno, sqlstate, level, msg, &cond))
    DBUG_RETURN(cond);

  if (level == Sql_condition::WARN_LEVEL_ERROR)
  {
    is_slave_error=  1; // needed to catch query errors during replication

    /*
      thd->lex->current_select == 0 if lex structure is not inited
      (not query command (COM_QUERY))
    */
    if (lex->current_select &&
        lex->current_select->no_error && !is_fatal_error)
    {
      DBUG_PRINT("error",
                 ("Error converted to warning: current_select: no_error %d  "
                  "fatal_error: %d",
                  (lex->current_select ?
                   lex->current_select->no_error : 0),
                  (int) is_fatal_error));
    }
    else
    {
      if (!da->is_error())
      {
        set_row_count_func(-1);
        da->set_error_status(sql_errno, msg, sqlstate, cond);
      }
    }
  }

  /* 
     Avoid pushing a condition for fatal out of memory errors as this will 
     require memory allocation and therefore might fail. Non fatal out of 
     memory errors can occur if raised by SIGNAL/RESIGNAL statement.
  */
  if (!(is_fatal_error && (sql_errno == EE_OUTOFMEMORY ||
                           sql_errno == ER_OUTOFMEMORY)))
  {
    cond= da->push_warning(this, sql_errno, sqlstate, level, msg);
  }
  DBUG_RETURN(cond);
}

extern "C"
void *thd_alloc(MYSQL_THD thd, unsigned int size)
{
  return thd->alloc(size);
}

extern "C"
void *thd_calloc(MYSQL_THD thd, unsigned int size)
{
  return thd->calloc(size);
}

extern "C"
char *thd_strdup(MYSQL_THD thd, const char *str)
{
  return thd->strdup(str);
}

extern "C"
char *thd_strmake(MYSQL_THD thd, const char *str, unsigned int size)
{
  return thd->strmake(str, size);
}

extern "C"
LEX_STRING *thd_make_lex_string(THD *thd, LEX_STRING *lex_str,
                                const char *str, unsigned int size,
                                int allocate_lex_string)
{
  return thd->make_lex_string(lex_str, str, size,
                              (bool) allocate_lex_string);
}

extern "C"
void *thd_memdup(MYSQL_THD thd, const void* str, unsigned int size)
{
  return thd->memdup(str, size);
}

#ifdef _WIN32
extern "C"   THD *_current_thd_noinline(void)
{
  return my_pthread_getspecific_ptr(THD*,THR_THD);
}
#endif
/*
  Init common variables that has to be reset on start and on change_user
*/

void THD::init(void)
{
  plugin_thdvar_init(this, m_enable_plugins);
  /*
    variables= global_system_variables above has reset
    variables.pseudo_thread_id to 0. We need to correct it here to
    avoid temporary tables replication failure.
  */
  variables.pseudo_thread_id= thread_id;
  server_status= SERVER_STATUS_AUTOCOMMIT;
  if (variables.sql_mode & MODE_NO_BACKSLASH_ESCAPES)
    server_status|= SERVER_STATUS_NO_BACKSLASH_ESCAPES;

  update_lock_default= (variables.low_priority_updates ?
			TL_WRITE_LOW_PRIORITY :
			TL_WRITE);
  tx_isolation= (enum_tx_isolation) variables.tx_isolation;
  tx_read_only= variables.tx_read_only;
  update_charset();

  reset_stats();

  clear_slow_extended();
}

// Resets stats in a THD.
void THD::reset_stats(void)
{
  current_connect_time=    time(NULL);
  last_global_update_time= current_connect_time;
  reset_diff_stats();
}

// Resets the 'diff' stats, which are used to update global stats.
void THD::reset_diff_stats(void)
{
  diff_total_busy_time=            0;
  diff_total_cpu_time=             0;
  diff_total_bytes_received=       0;
  diff_total_bytes_sent=           0;
  diff_total_binlog_bytes_written= 0;
  diff_total_sent_rows=            0;
  diff_total_updated_rows=         0;
  diff_total_read_rows=            0;
  diff_select_commands=            0;
  diff_update_commands=            0;
  diff_other_commands=             0;
  diff_commit_trans=               0;
  diff_rollback_trans=             0;
  diff_denied_connections=         0;
  diff_lost_connections=           0;
  diff_access_denied_errors=       0;
  diff_empty_queries=              0;
}

// Updates 'diff' stats of a THD.
void THD::update_stats(bool ran_command)
{
  diff_total_busy_time+=            busy_time;
  diff_total_cpu_time+=             cpu_time;
  diff_total_bytes_received+=       bytes_received;
  diff_total_bytes_sent+=           bytes_sent;
  diff_total_binlog_bytes_written+= binlog_bytes_written;
  diff_total_sent_rows+=            sent_row_count_2;
  diff_total_updated_rows+=         updated_row_count;
  // diff_total_read_rows is updated in handler.cc.

  if (ran_command)
  {
    // The replication thread has the COM_CONNECT command.
    DBUG_ASSERT(get_command() != COM_SLEEP);
    if ((get_command() == COM_QUERY || get_command() == COM_CONNECT) &&
        (lex->sql_command >= 0 && lex->sql_command < SQLCOM_END)) {
      // A SQL query.
      if (lex->sql_command == SQLCOM_SELECT)
      {
        diff_select_commands++;
        if (!sent_row_count_2)
          diff_empty_queries++;
      }
      else if (!sql_command_flags[lex->sql_command] & CF_STATUS_COMMAND)
      {
        // 'SHOW ' commands become SQLCOM_SELECT.
        diff_other_commands++;
        // 'SHOW ' commands shouldn't inflate total sent row count.
        diff_total_sent_rows-= sent_row_count_2;
      } else if (is_update_query(lex->sql_command)) {
        diff_update_commands++;
      } else {
        diff_other_commands++;
      }
    }
  }
  // diff_commit_trans is updated in handler.cc.
  // diff_rollback_trans is updated in handler.cc.
  // diff_denied_connections is updated in sql_parse.cc.
  // diff_lost_connections is updated in sql_parse.cc.
  // diff_access_denied_errors is updated in sql_parse.cc.

  /* reset counters to zero to avoid double-counting since values
     are already store in diff_total_*.
  */

  busy_time=            0;
  cpu_time=             0;
  bytes_received=       0;
  bytes_sent=           0;
  binlog_bytes_written= 0;
  updated_row_count=    0;
  sent_row_count_2=     0;
}

/*
  Do what's needed when one invokes change user.
  Also used during THD::release_resources, i.e. prior to THD destruction.
*/
void THD::cleanup(void)
{
  DBUG_ENTER("THD::cleanup");
  DBUG_ASSERT(cleanup_done == 0);

  killed= KILL_CONNECTION;

  DBUG_ASSERT(open_tables == NULL);

  cleanup_done=1;
  DBUG_VOID_RETURN;
}


/**
  Release most resources, prior to THD destruction.
 */
void THD::release_resources()
{
  DBUG_ASSERT(m_release_resources_done == false);


  if (!cleanup_done)
    cleanup();


  m_release_resources_done= true;
}


THD::~THD()
{
  THD_CHECK_SENTRY(this);
  DBUG_ENTER("~THD()");
  DBUG_PRINT("info", ("THD dtor, this %p", this));

  if (!m_release_resources_done)
    release_resources();

  DBUG_ASSERT(timer == NULL);

  DBUG_PRINT("info", ("freeing security context"));
  my_free(db);
  db= NULL;
#ifndef DBUG_OFF
  dbug_sentry= THD_SENTRY_GONE;
#endif

  free_root(&main_mem_root, MYF(0));
  DBUG_VOID_RETURN;
}

/*
  Remember the location of thread info, the structure needed for
  sql_alloc() and the structure for the net buffer
*/

bool THD::store_globals()
{
  /*
    Assert that thread_stack is initialized: it's necessary to be able
    to track stack overrun.
  */
  DBUG_ASSERT(thread_stack);

  if (my_pthread_setspecific_ptr(THR_THD,  this) ||
      my_pthread_setspecific_ptr(THR_MALLOC, &mem_root))
    return 1;
  /*
    mysys_var is concurrently readable by a killer thread.
    It is protected by LOCK_thd_data, it is not needed to lock while the
    pointer is changing from NULL not non-NULL. If the kill thread reads
    NULL it doesn't refer to anything, but if it is non-NULL we need to
    ensure that the thread doesn't proceed to assign another thread to
    have the mysys_var reference (which in fact refers to the worker
    threads local storage with key THR_KEY_mysys. 
  */
  mysys_var=my_thread_var;
  DBUG_PRINT("debug", ("mysys_var: 0x%llx", (ulonglong) mysys_var));
  /*
    Let mysqld define the thread id (not mysys)
    This allows us to move THD to different threads if needed.
  */
  mysys_var->id= thread_id;
  real_id= pthread_self();                      // For debugging
  return 0;
}

/*
  Remove the thread specific info (THD and mem_root pointer) stored during
  store_global call for this thread.
*/
bool THD::restore_globals()
{
  /*
    Assert that thread_stack is initialized: it's necessary to be able
    to track stack overrun.
  */
  DBUG_ASSERT(thread_stack);
  
  /* Undocking the thread specific data. */
  my_pthread_setspecific_ptr(THR_THD, NULL);
  my_pthread_setspecific_ptr(THR_MALLOC, NULL);
  
  return 0;
}


/*
  Cleanup after query.

  SYNOPSIS
    THD::cleanup_after_query()

  DESCRIPTION
    This function is used to reset thread data to its default state.

  NOTE
    This function is not suitable for setting thread data to some
    non-default values, as there is only one replication thread, so
    different master threads may overwrite data of each other on
    slave.
*/

void THD::cleanup_after_query()
{
  /*
    Reset rand_used so that detection of calls to rand() will save random 
    seeds if needed by the slave.

    Do not reset rand_used if inside a stored function or trigger because 
    only the call to these operations is logged. Thus only the calling 
    statement needs to detect rand() calls made by its substatements. These
    substatements must not set rand_used to 0 because it would remove the
    detection of rand() by the calling statement. 
  */
  if (!in_sub_stmt) /* stored functions and triggers are a special case */
  {
    /* Forget those values, for next binlogger: */
    stmt_depends_on_first_successful_insert_id_in_prev_stmt= 0;
    auto_inc_intervals_in_cur_stmt_for_binlog.empty();
    rand_used= 0;
  }

  if (first_successful_insert_id_in_cur_stmt > 0)
  {
    /* set what LAST_INSERT_ID() will return */
    first_successful_insert_id_in_prev_stmt= 
      first_successful_insert_id_in_cur_stmt;
    first_successful_insert_id_in_cur_stmt= 0;
    substitute_null_with_insert_id= TRUE;
  }
  arg_of_last_insert_id_function= 0;
  /* Free Items that were created during this execution */
  free_items();
  /* Reset where. */
  where= THD::DEFAULT_WHERE;
  /* reset table map for multi-table update */
  table_map_for_update= 0;
  /* reset replication info structure */
  if (lex && lex->mi.repl_ignore_server_ids.buffer) 
  {
    delete_dynamic(&lex->mi.repl_ignore_server_ids);
  }
}


LEX_STRING *
make_lex_string_root(MEM_ROOT *mem_root,
                     LEX_STRING *lex_str, const char* str, uint length,
                     bool allocate_lex_string)
{
  if (allocate_lex_string)
    if (!(lex_str= (LEX_STRING *)alloc_root(mem_root, sizeof(LEX_STRING))))
      return 0;
  if (!(lex_str->str= strmake_root(mem_root, str, length)))
    return 0;
  lex_str->length= length;
  return lex_str;
}

/**
  Create a LEX_STRING in this connection.

  @param lex_str  pointer to LEX_STRING object to be initialized
  @param str      initializer to be copied into lex_str
  @param length   length of str, in bytes
  @param allocate_lex_string  if TRUE, allocate new LEX_STRING object,
                              instead of using lex_str value
  @return  NULL on failure, or pointer to the LEX_STRING object
*/
LEX_STRING *THD::make_lex_string(LEX_STRING *lex_str,
                                 const char* str, uint length,
                                 bool allocate_lex_string)
{
  return make_lex_string_root (mem_root, lex_str, str,
                               length, allocate_lex_string);
}


/*
  Convert a string to another character set

  SYNOPSIS
    convert_string()
    to				Store new allocated string here
    to_cs			New character set for allocated string
    from			String to convert
    from_length			Length of string to convert
    from_cs			Original character set

  NOTES
    to will be 0-terminated to make it easy to pass to system funcs

  RETURN
    0	ok
    1	End of memory.
        In this case to->str will point to 0 and to->length will be 0.
*/

bool THD::convert_string(LEX_STRING *to, const CHARSET_INFO *to_cs,
			 const char *from, uint from_length,
			 const CHARSET_INFO *from_cs)
{
  DBUG_ENTER("convert_string");
  size_t new_length= to_cs->mbmaxlen * from_length;
  uint dummy_errors;
  if (!(to->str= (char*) alloc(new_length+1)))
  {
    to->length= 0;				// Safety fix
    DBUG_RETURN(1);				// EOM
  }
  to->length= copy_and_convert((char*) to->str, new_length, to_cs,
			       from, from_length, from_cs, &dummy_errors);
  to->str[to->length]=0;			// Safety
  DBUG_RETURN(0);
}


/*
  Convert string from source character set to target character set inplace.

  SYNOPSIS
    THD::convert_string

  DESCRIPTION
    Convert string using convert_buffer - buffer for character set 
    conversion shared between all protocols.

  RETURN
    0   ok
   !0   out of memory
*/

bool THD::convert_string(String *s, const CHARSET_INFO *from_cs,
                         const CHARSET_INFO *to_cs)
{
  uint dummy_errors;
  if (convert_buffer.copy(s->ptr(), s->length(), from_cs, to_cs, &dummy_errors))
    return TRUE;
  /* If convert_buffer >> s copying is more efficient long term */
  if (convert_buffer.alloced_length() >= convert_buffer.length() * 2 ||
      !s->is_alloced())
  {
    return s->copy(convert_buffer);
  }
  s->swap(convert_buffer);
  return FALSE;
}


/*
  Update some cache variables when character set changes
*/

void THD::update_charset()
{
  uint32 not_used;
  charset_is_system_charset=
    !String::needs_conversion(0,
                              variables.character_set_client,
                              system_charset_info,
                              &not_used);
  charset_is_collation_connection= 
    !String::needs_conversion(0,
                              variables.character_set_client,
                              variables.collation_connection,
                              &not_used);
  charset_is_character_set_filesystem= 
    !String::needs_conversion(0,
                              variables.character_set_client,
                              variables.character_set_filesystem,
                              &not_used);
}

/*
  Register an item tree tree transformation, performed by the query
  optimizer. We need a pointer to runtime_memroot because it may be !=
  thd->mem_root (due to possible set_n_backup_active_arena called for thd).
*/

void THD::nocheck_register_item_tree_change(Item **place, Item *old_value,
                                            MEM_ROOT *runtime_memroot)
{
  Item_change_record *change;
  /*
    Now we use one node per change, which adds some memory overhead,
    but still is rather fast as we use alloc_root for allocations.
    A list of item tree changes of an average query should be short.
  */
  void *change_mem= alloc_root(runtime_memroot, sizeof(*change));
  if (change_mem == 0)
  {
    /*
      OOM, thd->fatal_error() is called by the error handler of the
      memroot. Just return.
    */
    return;
  }
  change= new (change_mem) Item_change_record;
  change->place= place;
  change->old_value= old_value;
  change_list.push_front(change);
}


void THD::change_item_tree_place(Item **old_ref, Item **new_ref)
{
  I_List_iterator<Item_change_record> it(change_list);
  Item_change_record *change;
  while ((change= it++))
  {
    if (change->place == old_ref)
    {
      DBUG_PRINT("info", ("change_item_tree_place old_ref %p new_ref %p",
                          old_ref, new_ref));
      change->place= new_ref;
      break;
    }
  }
}


void THD::rollback_item_tree_changes()
{
  I_List_iterator<Item_change_record> it(change_list);
  Item_change_record *change;
  DBUG_ENTER("rollback_item_tree_changes");

  while ((change= it++))
  {
    DBUG_PRINT("info",
               ("rollback_item_tree_changes "
                "place %p curr_value %p old_value %p",
                change->place, *change->place, change->old_value));
    *change->place= change->old_value;
  }
  /* We can forget about changes memory: it's allocated in runtime memroot */
  change_list.empty();
  DBUG_VOID_RETURN;
}


/*****************************************************************************
** Functions to provide a interface to select results
*****************************************************************************/

select_result::select_result():
  estimated_rowcount(0)
{
  thd=current_thd;
}

void select_result::send_error(uint errcode,const char *err)
{
  my_message(errcode, err, MYF(0));
}


void select_result::cleanup()
{
  /* do nothing */
}

bool select_result::check_simple_select() const
{
  my_error(ER_SP_BAD_CURSOR_QUERY, MYF(0));
  return TRUE;
}


static const String default_line_term("\n",default_charset_info);
static const String default_escaped("\\",default_charset_info);
static const String default_field_term("\t",default_charset_info);
static const String default_xml_row_term("<row>", default_charset_info);
static const String my_empty_string("",default_charset_info);


sql_exchange::sql_exchange(char *name, bool flag,
                           enum enum_filetype filetype_arg)
  :file_name(name), opt_enclosed(0), dumpfile(flag), skip_lines(0)
{
  filetype= filetype_arg;
  field_term= &default_field_term;
  enclosed=   line_start= &my_empty_string;
  line_term=  filetype == FILETYPE_CSV ?
              &default_line_term : &default_xml_row_term;
  escaped=    &default_escaped;
  cs= NULL;
}

bool sql_exchange::escaped_given(void)
{
  return escaped != &default_escaped;
}


select_to_file::~select_to_file()
{
  if (file >= 0)
  {					// This only happens in case of error
    (void) end_io_cache(&cache);
    mysql_file_close(file, MYF(0));
    file= -1;
  }
}


/***************************************************************************
** Export of select to textfile
***************************************************************************/

select_export::~select_export()
{
}

select_subselect::select_subselect(Item_subselect *item_arg)
{
  item= item_arg;
}

Query_arena::Type Query_arena::type() const
{
  DBUG_ASSERT(0); /* Should never be called */
  return STATEMENT;
}


void Query_arena::free_items()
{
  Item *next;
  DBUG_ENTER("Query_arena::free_items");
  /* This works because items are allocated with sql_alloc() */
  for (; free_list; free_list= next)
  {
    next= free_list->next;
    free_list->delete_self();
  }
  /* Postcondition: free_list is 0 */
  DBUG_VOID_RETURN;
}


void Query_arena::set_query_arena(Query_arena *set)
{
  mem_root=  set->mem_root;
  free_list= set->free_list;
  state= set->state;
}


void Query_arena::cleanup_stmt()
{
  DBUG_ASSERT(! "Query_arena::cleanup_stmt() not implemented");
}

/*
  Statement functions
*/

Statement::Statement(LEX *lex_arg, MEM_ROOT *mem_root_arg,
                     enum_state state_arg, ulong id_arg)
  :Query_arena(mem_root_arg, state_arg),
  id(id_arg),
  mark_used_columns(MARK_COLUMNS_READ),
  lex(lex_arg),
  db(NULL),
  db_length(0)
{
  name.str= NULL;
}


Query_arena::Type Statement::type() const
{
  return STATEMENT;
}


void Statement::set_statement(Statement *stmt)
{
  id=             stmt->id;
  mark_used_columns=   stmt->mark_used_columns;
  lex=            stmt->lex;
  query_string=   stmt->query_string;
}


void
Statement::set_n_backup_statement(Statement *stmt, Statement *backup)
{
  DBUG_ENTER("Statement::set_n_backup_statement");
  backup->set_statement(this);
  set_statement(stmt);
  DBUG_VOID_RETURN;
}


void Statement::restore_backup_statement(Statement *stmt, Statement *backup)
{
  DBUG_ENTER("Statement::restore_backup_statement");
  stmt->set_statement(this);
  set_statement(backup);
  DBUG_VOID_RETURN;
}


void THD::end_statement()
{
  /* Cleanup SQL processing state to reuse this statement in next query. */
  lex_end(lex);
  delete lex->result;
  lex->result= 0;
  /* Note that free_list is freed in cleanup_after_query() */

  /*
    Don't free mem_root, as mem_root is freed in the end of dispatch_command
    (once for any command).
  */
}


void THD::set_n_backup_active_arena(Query_arena *set, Query_arena *backup)
{
  DBUG_ENTER("THD::set_n_backup_active_arena");
  DBUG_ASSERT(backup->is_backup_arena == FALSE);

  backup->set_query_arena(this);
  set_query_arena(set);
#ifndef DBUG_OFF
  backup->is_backup_arena= TRUE;
#endif
  DBUG_VOID_RETURN;
}


void THD::restore_active_arena(Query_arena *set, Query_arena *backup)
{
  DBUG_ENTER("THD::restore_active_arena");
  DBUG_ASSERT(backup->is_backup_arena);
  set->set_query_arena(this);
  set_query_arena(backup);
#ifndef DBUG_OFF
  backup->is_backup_arena= FALSE;
#endif
  DBUG_VOID_RETURN;
}

Statement::~Statement()
{
}

C_MODE_START

static uchar *
get_statement_id_as_hash_key(const uchar *record, size_t *key_length,
                             my_bool not_used __attribute__((unused)))
{
  const Statement *statement= (const Statement *) record; 
  *key_length= sizeof(statement->id);
  return (uchar *) &((const Statement *) statement)->id;
}

static void delete_statement_as_hash_key(void *key)
{
  delete (Statement *) key;
}

static uchar *get_stmt_name_hash_key(Statement *entry, size_t *length,
                                    my_bool not_used __attribute__((unused)))
{
  *length= entry->name.length;
  return (uchar*) entry->name.str;
}

C_MODE_END

Statement_map::Statement_map() :
  last_found_statement(0)
{
  enum
  {
    START_STMT_HASH_SIZE = 16,
    START_NAME_HASH_SIZE = 16
  };
  my_hash_init(&st_hash, &my_charset_bin, START_STMT_HASH_SIZE, 0, 0,
               get_statement_id_as_hash_key,
               delete_statement_as_hash_key, MYF(0));
  my_hash_init(&names_hash, system_charset_info, START_NAME_HASH_SIZE, 0, 0,
               (my_hash_get_key) get_stmt_name_hash_key,
               NULL,MYF(0));
}


/*
  Insert a new statement to the thread-local statement map.

  DESCRIPTION
    If there was an old statement with the same name, replace it with the
    new one. Otherwise, check if max_prepared_stmt_count is not reached yet,
    increase prepared_stmt_count, and insert the new statement. It's okay
    to delete an old statement and fail to insert the new one.

  POSTCONDITIONS
    All named prepared statements are also present in names_hash.
    Statement names in names_hash are unique.
    The statement is added only if prepared_stmt_count < max_prepard_stmt_count
    last_found_statement always points to a valid statement or is 0

  RETURN VALUE
    0  success
    1  error: out of resources or max_prepared_stmt_count limit has been
       reached. An error is sent to the client, the statement is deleted.
*/

int Statement_map::insert(THD *thd, Statement *statement)
{
  if (my_hash_insert(&st_hash, (uchar*) statement))
  {
    /*
      Delete is needed only in case of an insert failure. In all other
      cases hash_delete will also delete the statement.
    */
    delete statement;
    my_error(ER_OUT_OF_RESOURCES, MYF(0));
    goto err_st_hash;
  }
  if (statement->name.str && my_hash_insert(&names_hash, (uchar*) statement))
  {
    my_error(ER_OUT_OF_RESOURCES, MYF(0));
    goto err_names_hash;
  }

  last_found_statement= statement;
  return 0;

err_names_hash:
  my_hash_delete(&st_hash, (uchar*) statement);
err_st_hash:
  return 1;
}


void Statement_map::close_transient_cursors()
{
#ifdef TO_BE_IMPLEMENTED
  Statement *stmt;
  while ((stmt= transient_cursor_list.head()))
    stmt->close_cursor();                 /* deletes itself from the list */
#endif
}


void Statement_map::erase(Statement *statement)
{
  if (statement == last_found_statement)
    last_found_statement= 0;
  if (statement->name.str)
    my_hash_delete(&names_hash, (uchar *) statement);

  my_hash_delete(&st_hash, (uchar *) statement);
}


void Statement_map::reset()
{
  my_hash_reset(&names_hash);
  my_hash_reset(&st_hash);
  last_found_statement= 0;
}


Statement_map::~Statement_map()
{
  /*
    We do not want to grab the global LOCK_prepared_stmt_count mutex here.
    reset() should already have been called to maintain prepared_stmt_count.
   */
  DBUG_ASSERT(st_hash.records == 0);

  my_hash_free(&names_hash);
  my_hash_free(&st_hash);
}


void Security_context::init()
{
  user= 0;
  ip.set("", 0, system_charset_info);
  host.set("", 0, system_charset_info);
  external_user.set("", 0, system_charset_info);
  host_or_ip= "connecting host";
  priv_user[0]= priv_host[0]= proxy_user[0]= '\0';
  master_access= 0;
#ifndef NO_EMBEDDED_ACCESS_CHECKS
  db_access= NO_ACCESS;
#endif
  password_expired= false; 
}

void Security_context::destroy()
{
  if (host.ptr() != my_localhost && host.length())
  {
    char *c= (char *) host.ptr();
    host.set("", 0, system_charset_info);
    my_free(c);
  }

  if (user && user != delayed_user)
  {
    my_free(user);
    user= NULL;
  }

  if (external_user.length())
  {
    char *c= (char *) external_user.ptr();
    external_user.set("", 0, system_charset_info);
    my_free(c);
  }

  if (ip.length())
  {
    char *c= (char *) ip.ptr();
    ip.set("", 0, system_charset_info);
    my_free(c);
  }

}


void Security_context::skip_grants()
{
  /* privileges for the user are unknown everything is allowed */
  host_or_ip= (char *)"";
  master_access= ~NO_ACCESS;
  *priv_user= *priv_host= '\0';
}


bool Security_context::set_user(char *user_arg)
{
  my_free(user);
  user= my_strdup(user_arg, MYF(0));
  return user == 0;
}

String *Security_context::get_host()
{
  return (&host);
}

String *Security_context::get_ip()
{
  return (&ip);
}

String *Security_context::get_external_user()
{
  return (&external_user);
}

void Security_context::set_host(const char *str)
{
  uint len= str ? strlen(str) :  0;
  host.set(str, len, system_charset_info);
}

void Security_context::set_ip(const char *str)
{
  uint len= str ? strlen(str) :  0;
  ip.set(str, len, system_charset_info);
}

void Security_context::set_external_user(const char *str)
{
  uint len= str ? strlen(str) :  0;
  external_user.set(str, len, system_charset_info);
}

void Security_context::set_host(const char * str, size_t len)
{
  host.set(str, len, system_charset_info);
  host.c_ptr_quick();
}

void Log_throttle::new_window(ulonglong now)
{
  count= 0;
  window_end= now + window_size;
}


void Slow_log_throttle::new_window(ulonglong now)
{
  Log_throttle::new_window(now);
  total_exec_time= 0;
  total_lock_time= 0;
}


Slow_log_throttle::Slow_log_throttle(ulong *threshold, mysql_mutex_t *lock,
                                     ulong window_usecs,
                                     bool (*logger)(THD *, const char *, uint),
                                     const char *msg)
  : Log_throttle(window_usecs, msg), total_exec_time(0), total_lock_time(0),
    rate(threshold), log_summary(logger), LOCK_log_throttle(lock)
{
  aggregate_sctx.init();
}


ulong Log_throttle::prepare_summary(ulong rate)
{
  ulong ret= 0;
  /*
    Previous throttling window is over or rate changed.
    Return the number of lines we throttled.
  */
  if (count > rate)
  {
    ret= count - rate;
    count= 0;                                 // prevent writing it again.
  }

  return ret;
}


void Slow_log_throttle::print_summary(THD *thd, ulong suppressed,
                                      ulonglong print_lock_time,
                                      ulonglong print_exec_time)
{
  /*
    We synthesize these values so the totals in the log will be
    correct (just in case somebody analyses them), even if the
    start/stop times won't be (as they're an aggregate which will
    usually mostly lie within [ window_end - window_size ; window_end ]
  */
  ulonglong save_start_utime=      thd->start_utime;
  ulonglong save_utime_after_lock= thd->utime_after_lock;

  char buf[128];

  snprintf(buf, sizeof(buf), summary_template, suppressed);

  mysql_mutex_lock(&thd->LOCK_thd_data);
  thd->start_utime=                thd->current_utime() - print_exec_time;
  thd->utime_after_lock=           thd->start_utime + print_lock_time;
  mysql_mutex_unlock(&thd->LOCK_thd_data);

  (*log_summary)(thd, buf, strlen(buf));

  mysql_mutex_lock(&thd->LOCK_thd_data);
  thd->start_utime     = save_start_utime;
  thd->utime_after_lock= save_utime_after_lock;
  mysql_mutex_unlock(&thd->LOCK_thd_data);
}


bool Slow_log_throttle::flush(THD *thd)
{
  // Write summary if we throttled.
  mysql_mutex_lock(LOCK_log_throttle);
  ulonglong print_lock_time=  total_lock_time;
  ulonglong print_exec_time=  total_exec_time;
  ulong     suppressed_count= prepare_summary(*rate);
  mysql_mutex_unlock(LOCK_log_throttle);
  if (suppressed_count > 0)
  {
    print_summary(thd, suppressed_count, print_lock_time, print_exec_time);
    return true;
  }
  return false;
}


bool Slow_log_throttle::log(THD *thd, bool eligible)
{
  bool  suppress_current= false;

  /*
    If throttling is enabled, we might have to write a summary even if
    the current query is not of the type we handle.
  */
  if (*rate > 0)
  {
    mysql_mutex_lock(LOCK_log_throttle);

    ulong     suppressed_count=   0;
    ulonglong print_lock_time=    total_lock_time;
    ulonglong print_exec_time=    total_exec_time;
    ulonglong end_utime_of_query= thd->current_utime();

    /*
      If the window has expired, we'll try to write a summary line.
      The subroutine will know whether we actually need to.
    */
    if (!in_window(end_utime_of_query))
    {
      suppressed_count= prepare_summary(*rate);
      // start new window only if this is the statement type we handle
      if (eligible)
        new_window(end_utime_of_query);
    }
    if (eligible && inc_log_count(*rate))
    {
      /*
        Current query's logging should be suppressed.
        Add its execution time and lock time to totals for the current window.
      */
      total_exec_time += (end_utime_of_query - thd->start_utime);
      total_lock_time += (thd->utime_after_lock - thd->start_utime);
      suppress_current= true;
    }

    mysql_mutex_unlock(LOCK_log_throttle);

    /*
      print_summary() is deferred until after we release the locks to
      avoid congestion. All variables we hand in are local to the caller,
      so things would even be safe if print_summary() hadn't finished by the
      time the next one comes around (60s later at the earliest for now).
      The current design will produce correct data, but does not guarantee
      order (there is a theoretical race condition here where the above
      new_window()/unlock() may enable a different thread to print a warning
      for the new window before the current thread gets to print_summary().
      If the requirements ever change, add a print_lock to the object that
      is held during print_summary(), AND that is briefly locked before
      returning from this function if(eligible && !suppress_current).
      This should ensure correct ordering of summaries with regard to any
      follow-up summaries as well as to any (non-suppressed) warnings (of
      the type we handle) from the next window.
    */
    if (suppressed_count > 0)
      print_summary(thd, suppressed_count, print_lock_time, print_exec_time);
  }

  return suppress_current;
}


bool Error_log_throttle::log(THD *thd)
{
  ulonglong end_utime_of_query= thd->current_utime();

  /*
    If the window has expired, we'll try to write a summary line.
    The subroutine will know whether we actually need to.
  */
  if (!in_window(end_utime_of_query))
  {
    ulong suppressed_count= prepare_summary(1);

    new_window(end_utime_of_query);

    if (suppressed_count > 0)
      print_summary(suppressed_count);
  }

  /*
    If this is a first error in the current window then do not suppress it.
  */
  return inc_log_count(1);
}


bool Error_log_throttle::flush(THD *thd)
{
  // Write summary if we throttled.
  ulong     suppressed_count= prepare_summary(1);
  if (suppressed_count > 0)
  {
    print_summary(suppressed_count);
    return true;
  }
  return false;
}

/**
  Return the thread id of a user thread
  @param thd user thread
  @return thread id
*/
extern "C" unsigned long thd_get_thread_id(const MYSQL_THD thd)
{
  return((unsigned long)thd->thread_id);
}

enum_tx_isolation thd_get_trx_isolation(const MYSQL_THD thd)
{
	return thd->tx_isolation;
}

extern "C" const struct charset_info_st *thd_charset(MYSQL_THD thd)
{
  return(thd->charset());
}

/**
  OBSOLETE : there's no way to ensure the string is null terminated.
  Use thd_query_string instead()
*/
extern "C" char **thd_query(MYSQL_THD thd)
{
  return (&thd->query_string.string.str);
}

/**
  Get the current query string for the thread.

  @param The MySQL internal thread pointer
  @return query string and length. May be non-null-terminated.
*/
extern "C" LEX_STRING * thd_query_string (MYSQL_THD thd)
{
  return(&thd->query_string.string);
}

extern "C" bool thd_sqlcom_can_generate_row_events(const MYSQL_THD thd)
{
  return sqlcom_can_generate_row_events(thd);
}

extern "C" enum durability_properties thd_get_durability_property(const MYSQL_THD thd)
{
  enum durability_properties ret= HA_REGULAR_DURABILITY;
  
  if (thd != NULL)
    ret= thd->durability_property;

  return ret;
}


/**
  Is strict sql_mode set.
  Needed by InnoDB.
  @param thd	Thread object
  @return True if sql_mode has strict mode (all or trans).
    @retval true  sql_mode has strict mode (all or trans).
    @retval false sql_mode has not strict mode (all or trans).
*/
extern "C" bool thd_is_strict_mode(const MYSQL_THD thd)
{
  return thd->is_strict_mode();
}


void THD::clear_slow_extended()
{
  DBUG_ENTER("THD::clear_slow_extended");
  last_errno=                   0;
  DBUG_VOID_RETURN;
}

void THD::set_statement(Statement *stmt)
{
  mysql_mutex_lock(&LOCK_thd_data);
  Statement::set_statement(stmt);
  mysql_mutex_unlock(&LOCK_thd_data);
}

void THD::set_command(enum enum_server_command command)
{
  m_command= command;
#ifdef HAVE_PSI_THREAD_INTERFACE
  PSI_STATEMENT_CALL(set_thread_command)(m_command);
#endif
}


/** Assign a new value to thd->query.  */

void THD::set_query(const CSET_STRING &string_arg)
{
  mysql_mutex_lock(&LOCK_thd_data);
  set_query_inner(string_arg);
  mysql_mutex_unlock(&LOCK_thd_data);

#ifdef HAVE_PSI_THREAD_INTERFACE
  PSI_THREAD_CALL(set_thread_info)(query(), query_length());
#endif
}

/** Assign a new value to thd->query and thd->query_id.  */

void THD::set_query_and_id(char *query_arg, uint32 query_length_arg,
                           const CHARSET_INFO *cs,
                           query_id_t new_query_id)
{
  mysql_mutex_lock(&LOCK_thd_data);
  set_query_inner(query_arg, query_length_arg, cs);
  query_id= new_query_id;
  mysql_mutex_unlock(&LOCK_thd_data);
}

/** Assign a new value to thd->query_id.  */

void THD::set_query_id(query_id_t new_query_id)
{
  mysql_mutex_lock(&LOCK_thd_data);
#ifndef DBUG_OFF
  if (variables.query_exec_id != 0 &&
    lex->sql_command != SQLCOM_SET_OPTION)
  {
    new_query_id= variables.query_exec_id;
  }
#endif
  query_id= new_query_id;
  mysql_mutex_unlock(&LOCK_thd_data);
}

/** Assign a new value to thd->mysys_var.  */
void THD::set_mysys_var(struct st_my_thread_var *new_mysys_var)
{
  mysql_mutex_lock(&LOCK_thd_data);
  mysys_var= new_mysys_var;
  mysql_mutex_unlock(&LOCK_thd_data);
}

void THD::get_definer(LEX_USER *definer)
{
#if !defined(MYSQL_CLIENT) && defined(HAVE_REPLICATION)
  if (slave_thread && has_invoker())
  {
    definer->user = invoker_user;
    definer->host= invoker_host;
    definer->password.str= NULL;
    definer->password.length= 0;
    definer->plugin.str= (char *) "";
    definer->plugin.length= 0;
    definer->auth.str=  (char *) "";
    definer->auth.length= 0;
  }
  else
#endif
    get_default_definer(this, definer);
}


/**
  Mark transaction to rollback and mark error as fatal to a sub-statement.

  @param  thd   Thread handle
  @param  all   TRUE <=> rollback main transaction.
*/

void mark_transaction_to_rollback(THD *thd, bool all)
{
  if (thd)
  {
    thd->is_fatal_sub_stmt_error= TRUE;
    thd->transaction_rollback_request= all;
    /*
      Aborted transactions can not be IGNOREd.
      Switch off the IGNORE flag for the current
      SELECT_LEX. This should allow my_error()
      to report the error and abort the execution
      flow, even in presence
      of IGNORE clause.
    */
    if (thd->lex->current_select)
      thd->lex->current_select->no_error= FALSE;
  }
}
void THD::set_user_connect(USER_CONN *uc)
{
  DBUG_ENTER("THD::set_user_connect");

  m_user_connect= uc;

  DBUG_VOID_RETURN;
}

void THD::increment_user_connections_counter()
{
  DBUG_ENTER("THD::increment_user_connections_counter");

  m_user_connect->connections++;

  DBUG_VOID_RETURN;
}

void THD::decrement_user_connections_counter()
{
  DBUG_ENTER("THD::decrement_user_connections_counter");

  DBUG_ASSERT(m_user_connect->connections > 0);
  m_user_connect->connections--;

  DBUG_VOID_RETURN;
}

void THD::increment_con_per_hour_counter()
{
  DBUG_ENTER("THD::decrement_conn_per_hour_counter");

  m_user_connect->conn_per_hour++;

  DBUG_VOID_RETURN;
}

void THD::increment_updates_counter()
{
  DBUG_ENTER("THD::increment_updates_counter");

  m_user_connect->updates++;

  DBUG_VOID_RETURN;
}

void THD::increment_questions_counter()
{
  DBUG_ENTER("THD::increment_updates_counter");

  m_user_connect->questions++;

  DBUG_VOID_RETURN;
}

/*
  Reset per-hour user resource limits when it has been more than
  an hour since they were last checked

  SYNOPSIS:
    time_out_user_resource_limits()

  NOTE:
    This assumes that the LOCK_user_conn mutex has been acquired, so it is
    safe to test and modify members of the USER_CONN structure.
*/
void THD::time_out_user_resource_limits()
{
  mysql_mutex_assert_owner(&LOCK_user_conn);
  ulonglong check_time= start_utime;
  DBUG_ENTER("time_out_user_resource_limits");

  /* If more than a hour since last check, reset resource checking */
  if (check_time - m_user_connect->reset_utime >= LL(3600000000))
  {
    m_user_connect->questions=1;
    m_user_connect->updates=0;
    m_user_connect->conn_per_hour=0;
    m_user_connect->reset_utime= check_time;
  }

  DBUG_VOID_RETURN;
}
