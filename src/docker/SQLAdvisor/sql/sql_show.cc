/* Copyright (c) 2000, 2014, Oracle and/or its affiliates. All rights reserved.

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


/* Function with list databases, tables or fields */

#include "my_global.h"                          /* NO_EMBEDDED_ACCESS_CHECKS */
#include "sql_priv.h"
#include "unireg.h"
#include "sql_acl.h"                        // fill_schema_*_privileges
#include "sql_base.h"                       // close_tables_for_reopen
#include "sql_show.h"
#include "sql_table.h"                        // filename_to_tablename,
                                              // primary_key_name,
                                              // build_table_filename
#include "sql_view.h"                           // mysql_frm_type
#include "sql_parse.h"             // check_access, check_table_access
#include "sql_partition.h"         // partition_element
#include "sql_derived.h"           // mysql_derived_prepare,
                                   // mysql_handle_derived,
#include "sql_db.h"     // check_db_dir_existence, load_db_opt_by_name
#include "sql_time.h"   // interval_type_to_name
#include "sql_acl.h"     // TABLE_ACLS, check_grant, DB_ACLS, acl_get,
                         // check_grant_db
#include "sp.h"
#include "sp_head.h"
#include "sp_pcontext.h"
#include "set_var.h"
#include "sql_trigger.h"
#include "sql_derived.h"
#include "sql_partition.h"
#include <my_dir.h>
#include "global_threads.h"

#include <algorithm>
using std::max;
using std::min;

#define STR_OR_NIL(S) ((S) ? (S) : "<nil>")

enum enum_i_s_events_fields
{
  ISE_EVENT_CATALOG= 0,
  ISE_EVENT_SCHEMA,
  ISE_EVENT_NAME,
  ISE_DEFINER,
  ISE_TIME_ZONE,
  ISE_EVENT_BODY,
  ISE_EVENT_DEFINITION,
  ISE_EVENT_TYPE,
  ISE_EXECUTE_AT,
  ISE_INTERVAL_VALUE,
  ISE_INTERVAL_FIELD,
  ISE_SQL_MODE,
  ISE_STARTS,
  ISE_ENDS,
  ISE_STATUS,
  ISE_ON_COMPLETION,
  ISE_CREATED,
  ISE_LAST_ALTERED,
  ISE_LAST_EXECUTED,
  ISE_EVENT_COMMENT,
  ISE_ORIGINATOR,
  ISE_CLIENT_CS,
  ISE_CONNECTION_CL,
  ISE_DB_CL
};


/***************************************************************************
 List all privileges supported
***************************************************************************/

struct show_privileges_st {
  const char *privilege;
  const char *context;
  const char *comment;
};

static struct show_privileges_st sys_privileges[]=
{
  {"Alter", "Tables",  "To alter the table"},
  {"Alter routine", "Functions,Procedures",  "To alter or drop stored functions/procedures"},
  {"Create", "Databases,Tables,Indexes",  "To create new databases and tables"},
  {"Create routine","Databases","To use CREATE FUNCTION/PROCEDURE"},
  {"Create temporary tables","Databases","To use CREATE TEMPORARY TABLE"},
  {"Create view", "Tables",  "To create new views"},
  {"Create user", "Server Admin",  "To create new users"},
  {"Delete", "Tables",  "To delete existing rows"},
  {"Drop", "Databases,Tables", "To drop databases, tables, and views"},
#ifdef HAVE_EVENT_SCHEDULER
  {"Event","Server Admin","To create, alter, drop and execute events"},
#endif
  {"Execute", "Functions,Procedures", "To execute stored routines"},
  {"File", "File access on server",   "To read and write files on the server"},
  {"Grant option",  "Databases,Tables,Functions,Procedures", "To give to other users those privileges you possess"},
  {"Index", "Tables",  "To create or drop indexes"},
  {"Insert", "Tables",  "To insert data into tables"},
  {"Lock tables","Databases","To use LOCK TABLES (together with SELECT privilege)"},
  {"Process", "Server Admin", "To view the plain text of currently executing queries"},
  {"Proxy", "Server Admin", "To make proxy user possible"},
  {"References", "Databases,Tables", "To have references on tables"},
  {"Reload", "Server Admin", "To reload or refresh tables, logs and privileges"},
  {"Replication client","Server Admin","To ask where the slave or master servers are"},
  {"Replication slave","Server Admin","To read binary log events from the master"},
  {"Select", "Tables",  "To retrieve rows from table"},
  {"Show databases","Server Admin","To see all databases with SHOW DATABASES"},
  {"Show view","Tables","To see views with SHOW CREATE VIEW"},
  {"Shutdown","Server Admin", "To shut down the server"},
  {"Super","Server Admin","To use KILL thread, SET GLOBAL, CHANGE MASTER, etc."},
  {"Trigger","Tables", "To use triggers"},
  {"Create tablespace", "Server Admin", "To create/alter/drop tablespaces"},
  {"Update", "Tables",  "To update existing rows"},
  {"Usage","Server Admin","No privileges - allow connect only"},
  {NullS, NullS, NullS}
};



/** Hash of LEX_STRINGs used to search for ignored db directories. */
static HASH ignore_db_dirs_hash;

/** 
  An array of LEX_STRING pointers to collect the options at 
  option parsing time.
*/
static DYNAMIC_ARRAY ignore_db_dirs_array;

/**
  A value for the read only system variable to show a list of
  ignored directories.
*/
char *opt_ignore_db_dirs= NULL;


/**
  Sets up the data structures for collection of directories at option
  processing time.
  We need to collect the directories in an array first, because
  we need the character sets initialized before setting up the hash.

  @return state
  @retval TRUE  failed
  @retval FALSE success
*/

bool
ignore_db_dirs_init()
{
  return my_init_dynamic_array(&ignore_db_dirs_array, sizeof(LEX_STRING *),
                               0, 0);
}


/**
  Retrieves the key (the string itself) from the LEX_STRING hash members.

  Needed by hash_init().

  @param     data         the data element from the hash
  @param out len_ret      Placeholder to return the length of the key
  @param                  unused
  @return                 a pointer to the key
*/

static uchar *
db_dirs_hash_get_key(const uchar *data, size_t *len_ret,
                     my_bool __attribute__((unused)))
{
  LEX_STRING *e= (LEX_STRING *) data;

  *len_ret= e->length;
  return (uchar *) e->str;
}


/**
  Wrap a directory name into a LEX_STRING and push it to the array.

  Called at option processing time for each --ignore-db-dir option.

  @param    path  the name of the directory to push
  @return state
  @retval TRUE  failed
  @retval FALSE success
*/

bool
push_ignored_db_dir(char *path)
{
  LEX_STRING *new_elt;
  char *new_elt_buffer;
  size_t path_len= strlen(path);

  if (!path_len || path_len >= FN_REFLEN)
    return true;

  // No need to normalize, it's only a directory name, not a path.
  if (!my_multi_malloc(0,
                       &new_elt, sizeof(LEX_STRING),
                       &new_elt_buffer, path_len + 1,
                       NullS))
    return true;
  new_elt->str= new_elt_buffer;
  memcpy(new_elt_buffer, path, path_len);
  new_elt_buffer[path_len]= 0;
  new_elt->length= path_len;
  return insert_dynamic(&ignore_db_dirs_array, &new_elt);
}


/**
  Clean up the directory ignore options accumulated so far.

  Called at option processing time for each --ignore-db-dir option
  with an empty argument.
*/

void
ignore_db_dirs_reset()
{
  LEX_STRING **elt;
  while (NULL!= (elt= (LEX_STRING **) pop_dynamic(&ignore_db_dirs_array)))
    if (elt && *elt)
      my_free(*elt);
}


/**
  Free the directory ignore option variables.

  Called at server shutdown.
*/

void
ignore_db_dirs_free()
{
  if (opt_ignore_db_dirs)
  {
    my_free(opt_ignore_db_dirs);
    opt_ignore_db_dirs= NULL;
  }
  ignore_db_dirs_reset();
  delete_dynamic(&ignore_db_dirs_array);
  my_hash_free(&ignore_db_dirs_hash);
}


/**
  Initialize the ignore db directories hash and status variable from
  the options collected in the array.

  Called when option processing is over and the server's in-memory 
  structures are fully initialized.

  @return state
  @retval TRUE  failed
  @retval FALSE success
*/

bool
ignore_db_dirs_process_additions()
{
  ulong i;
  size_t len;
  char *ptr;
  LEX_STRING *dir;

  DBUG_ASSERT(opt_ignore_db_dirs == NULL);

  if (my_hash_init(&ignore_db_dirs_hash, 
                   lower_case_table_names ?
                     character_set_filesystem : &my_charset_bin,
                   0, 0, 0, db_dirs_hash_get_key,
                   my_free,
                   HASH_UNIQUE))
    return true;

  /* len starts from 1 because of the terminating zero. */
  len= 1;
  for (i= 0; i < ignore_db_dirs_array.elements; i++)
  {
    get_dynamic(&ignore_db_dirs_array, (uchar *) &dir, i);
    len+= dir->length + 1;                      // +1 for the comma
  }

  /* No delimiter for the last directory. */
  if (len > 1)
    len--;

  /* +1 the terminating zero */
  ptr= opt_ignore_db_dirs= (char *) my_malloc(len + 1, MYF(0));
  if (!ptr)
    return true;

  /* Make sure we have an empty string to start with. */
  *ptr= 0;

  for (i= 0; i < ignore_db_dirs_array.elements; i++)
  {
    get_dynamic(&ignore_db_dirs_array, (uchar *) &dir, i);
    if (my_hash_insert(&ignore_db_dirs_hash, (uchar *) dir))
      return true;
    ptr= strnmov(ptr, dir->str, dir->length);
    if (i + 1 < ignore_db_dirs_array.elements)
      ptr= strmov(ptr, ",");

    /*
      Set the transferred array element to NULL to avoid double free
      in case of error.
    */
    dir= NULL;
    set_dynamic(&ignore_db_dirs_array, (uchar *) &dir, i);
  }

  /* make sure the string is terminated */
  DBUG_ASSERT(ptr - opt_ignore_db_dirs <= (ptrdiff_t) len);
  *ptr= 0;

  /* 
    It's OK to empty the array here as the allocated elements are
    referenced through the hash now.
  */
  reset_dynamic(&ignore_db_dirs_array);

  return false;
}

/**
   An Internal_error_handler that suppresses errors regarding views'
   underlying tables that occur during privilege checking within SHOW CREATE
   VIEW commands. This happens in the cases when

   - A view's underlying table (e.g. referenced in its SELECT list) does not
     exist. There should not be an error as no attempt was made to access it
     per se.

   - Access is denied for some table, column, function or stored procedure
     such as mentioned above. This error gets raised automatically, since we
     can't untangle its access checking from that of the view itself.
 */
class Show_create_error_handler : public Internal_error_handler {
  
  TABLE_LIST *m_top_view;
  bool m_handling;
  Security_context *m_sctx;

  char m_view_access_denied_message[MYSQL_ERRMSG_SIZE];
  char *m_view_access_denied_message_ptr;

public:

  /**
     Creates a new Show_create_error_handler for the particular security
     context and view. 

     @thd Thread context, used for security context information if needed.
     @top_view The view. We do not verify at this point that top_view is in
     fact a view since, alas, these things do not stay constant.
  */
  explicit Show_create_error_handler(THD *thd, TABLE_LIST *top_view) : 
    m_top_view(top_view), m_handling(FALSE),
    m_view_access_denied_message_ptr(NULL) 
  {
    
    m_sctx = MY_TEST(m_top_view->security_ctx) ?
      m_top_view->security_ctx : thd->security_ctx;
  }

  /**
     Lazy instantiation of 'view access denied' message. The purpose of the
     Show_create_error_handler is to hide details of underlying tables for
     which we have no privileges behind ER_VIEW_INVALID messages. But this
     obviously does not apply if we lack privileges on the view itself.
     Unfortunately the information about for which table privilege checking
     failed is not available at this point. The only way for us to check is by
     reconstructing the actual error message and see if it's the same.
  */
  char* get_view_access_denied_message() 
  {
    if (!m_view_access_denied_message_ptr)
    {
      m_view_access_denied_message_ptr= m_view_access_denied_message;
      my_snprintf(m_view_access_denied_message, MYSQL_ERRMSG_SIZE,
                  ER(ER_TABLEACCESS_DENIED_ERROR), "SHOW VIEW",
                  m_sctx->priv_user,
                  m_sctx->host_or_ip, m_top_view->get_table_name());
    }
    return m_view_access_denied_message_ptr;
  }

  bool handle_condition(THD *thd, uint sql_errno, const char * /* sqlstate */,
                        Sql_condition::enum_warning_level level,
                        const char *message, Sql_condition ** /* cond_hdl */)
  {
    /*
       The handler does not handle the errors raised by itself.
       At this point we know if top_view is really a view.
    */
    if (m_handling || !m_top_view->view)
      return FALSE;

    m_handling= TRUE;

    bool is_handled;

    switch (sql_errno)
    {
    case ER_TABLEACCESS_DENIED_ERROR:
      if (!strcmp(get_view_access_denied_message(), message))
      {
        /* Access to top view is not granted, don't interfere. */
        is_handled= FALSE;
        break;
      }
    case ER_COLUMNACCESS_DENIED_ERROR:
    case ER_VIEW_NO_EXPLAIN: /* Error was anonymized, ignore all the same. */
    case ER_PROCACCESS_DENIED_ERROR:
      is_handled= TRUE;
      break;

    case ER_NO_SUCH_TABLE:
      /* Established behavior: warn if underlying tables are missing. */
      push_warning_printf(thd, Sql_condition::WARN_LEVEL_WARN, 
                          ER_VIEW_INVALID,
                          ER(ER_VIEW_INVALID),
                          m_top_view->get_db_name(),
                          m_top_view->get_table_name());
      is_handled= TRUE;
      break;

    case ER_SP_DOES_NOT_EXIST:
      /* Established behavior: warn if underlying functions are missing. */
      push_warning_printf(thd, Sql_condition::WARN_LEVEL_WARN, 
                          ER_VIEW_INVALID,
                          ER(ER_VIEW_INVALID),
                          m_top_view->get_db_name(),
                          m_top_view->get_table_name());
      is_handled= TRUE;
      break;
    default:
      is_handled= FALSE;
    }

    m_handling= FALSE;
    return is_handled;
  }
};

/*
  Go through all character combinations and ensure that sql_lex.cc can
  parse it as an identifier.

  SYNOPSIS
  require_quotes()
  name			attribute name
  name_length		length of name

  RETURN
    #	Pointer to conflicting character
    0	No conflicting character
*/

static const char *require_quotes(const char *name, uint name_length)
{
  uint length;
  bool pure_digit= TRUE;
  const char *end= name + name_length;

  for (; name < end ; name++)
  {
    uchar chr= (uchar) *name;
    length= my_mbcharlen(system_charset_info, chr);
    if (length == 1 && !system_charset_info->ident_map[chr])
      return name;
    if (length == 1 && (chr < '0' || chr > '9'))
      pure_digit= FALSE;
  }
  if (pure_digit)
    return name;
  return 0;
}


/*
  Quote the given identifier if needed and append it to the target string.
  If the given identifier is empty, it will be quoted.

  SYNOPSIS
  append_identifier()
  thd                   thread handler
  packet                target string
  name                  the identifier to be appended
  name_length           length of the appending identifier
*/

void
append_identifier(THD *thd, String *packet, const char *name, uint length)
{
  const char *name_end;
  char quote_char;
  int q;
  q= thd ? get_quote_char_for_identifier(thd, name, length) : '`';

  if (q == EOF)
  {
    packet->append(name, length, packet->charset());
    return;
  }

  /*
    The identifier must be quoted as it includes a quote character or
   it's a keyword
  */

  (void) packet->reserve(length*2 + 2);
  quote_char= (char) q;
  packet->append(&quote_char, 1, system_charset_info);

  for (name_end= name+length ; name < name_end ; name+= length)
  {
    uchar chr= (uchar) *name;
    length= my_mbcharlen(system_charset_info, chr);
    /*
      my_mbcharlen can return 0 on a wrong multibyte
      sequence. It is possible when upgrading from 4.0,
      and identifier contains some accented characters.
      The manual says it does not work. So we'll just
      change length to 1 not to hang in the endless loop.
    */
    if (!length)
      length= 1;
    if (length == 1 && chr == (uchar) quote_char)
      packet->append(&quote_char, 1, system_charset_info);
    packet->append(name, length, system_charset_info);
  }
  packet->append(&quote_char, 1, system_charset_info);
}


/*
  Get the quote character for displaying an identifier.

  SYNOPSIS
    get_quote_char_for_identifier()
    thd		Thread handler
    name	name to quote
    length	length of name

  IMPLEMENTATION
    Force quoting in the following cases:
      - name is empty (for one, it is possible when we use this function for
        quoting user and host names for DEFINER clause);
      - name is a keyword;
      - name includes a special character;
    Otherwise identifier is quoted only if the option OPTION_QUOTE_SHOW_CREATE
    is set.

  RETURN
    EOF	  No quote character is needed
    #	  Quote character
*/

int get_quote_char_for_identifier(THD *thd, const char *name, uint length)
{
  if (length &&
      !is_keyword(name,length) &&
      !require_quotes(name, length) &&
      !(thd->variables.option_bits & OPTION_QUOTE_SHOW_CREATE))
    return EOF;
  if (thd->variables.sql_mode & MODE_ANSI_QUOTES)
    return '"';
  return '`';
}


/****************************************************************************
  Return info about all processes
  returns for each thread: thread id, user, host, db, command, info,
  rows_sent, rows_examined
****************************************************************************/

class thread_info
{
public:
  static void *operator new(size_t size)
  {
    return (void*) sql_alloc((uint) size);
  }
  static void operator delete(void *ptr __attribute__((unused)),
                              size_t size __attribute__((unused)))
  { TRASH(ptr, size); }

  ulong thread_id;
  time_t start_time;
  uint   command;
  const char *user,*host,*db,*proc_info,*state_info;
  CSET_STRING query_string;
  ulonglong rows_sent, rows_examined;
};

// For sorting by thread_id.
class thread_info_compare :
  public std::binary_function<const thread_info*, const thread_info*, bool>
{
public:
  bool operator() (const thread_info* p1, const thread_info* p2)
  {
    return p1->thread_id < p2->thread_id;
  }
};

/* This is only used internally, but we need it here as a forward reference */
extern ST_SCHEMA_TABLE schema_tables[];

/**
  Condition pushdown used for INFORMATION_SCHEMA / SHOW queries.
  This structure is to implement an optimization when
  accessing data dictionary data in the INFORMATION_SCHEMA
  or SHOW commands.
  When the query contain a TABLE_SCHEMA or TABLE_NAME clause,
  narrow the search for data based on the constraints given.
*/
typedef struct st_lookup_field_values
{
  /**
    Value of a TABLE_SCHEMA clause.
    Note that this value length may exceed @c NAME_LEN.
    @sa wild_db_value
  */
  LEX_STRING db_value;
  /**
    Value of a TABLE_NAME clause.
    Note that this value length may exceed @c NAME_LEN.
    @sa wild_table_value
  */
  LEX_STRING table_value;
  /**
    True when @c db_value is a LIKE clause,
    false when @c db_value is an '=' clause.
  */
  bool wild_db_value;
  /**
    True when @c table_value is a LIKE clause,
    false when @c table_value is an '=' clause.
  */
  bool wild_table_value;
} LOOKUP_FIELD_VALUES;

struct st_add_schema_table 
{
  List<LEX_STRING> *files;
  const char *wild;
};

/**
  Trigger_error_handler is intended to intercept and silence SQL conditions
  that might happen during trigger loading for SHOW statements.
  The potential SQL conditions are:

    - ER_PARSE_ERROR -- this error is thrown if a trigger definition file
      is damaged or contains invalid CREATE TRIGGER statement. That should
      not happen in normal life.

    - ER_TRG_NO_DEFINER -- this warning is thrown when we're loading a
      trigger created/imported in/from the version of MySQL, which does not
      support trigger definers.

    - ER_TRG_NO_CREATION_CTX -- this warning is thrown when we're loading a
      trigger created/imported in/from the version of MySQL, which does not
      support trigger creation contexts.
*/

class Trigger_error_handler : public Internal_error_handler
{
public:
  bool handle_condition(THD *thd,
                        uint sql_errno,
                        const char* sqlstate,
                        Sql_condition::enum_warning_level level,
                        const char* msg,
                        Sql_condition ** cond_hdl)
  {
    if (sql_errno == ER_PARSE_ERROR ||
        sql_errno == ER_TRG_NO_DEFINER ||
        sql_errno == ER_TRG_NO_CREATION_CTX)
      return true;

    return false;
  }
};


/*
  Find schema_tables elment by name

  SYNOPSIS
    find_schema_table()
    thd                 thread handler
    table_name          table name

  RETURN
    0	table not found
    #   pointer to 'schema_tables' element
*/

ST_SCHEMA_TABLE *find_schema_table(THD *thd, const char* table_name)
{
  ST_SCHEMA_TABLE *schema_table= schema_tables;
  DBUG_ENTER("find_schema_table");

  for (; schema_table->table_name; schema_table++)
  {
    if (!my_strcasecmp(system_charset_info,
                       schema_table->table_name,
                       table_name))
      DBUG_RETURN(schema_table);
  }

  DBUG_RETURN(NULL);
}


ST_SCHEMA_TABLE *get_schema_table(enum enum_schema_tables schema_table_idx)
{
  return &schema_tables[schema_table_idx];
}

/*
  For old SHOW compatibility. It is used when
  old SHOW doesn't have generated column names
  Make list of fields for SHOW

  SYNOPSIS
    make_old_format()
    thd			thread handler
    schema_table        pointer to 'schema_tables' element

  RETURN
   1	error
   0	success
*/

int make_old_format(THD *thd, ST_SCHEMA_TABLE *schema_table)
{
  ST_FIELD_INFO *field_info= schema_table->fields_info;
  Name_resolution_context *context= &thd->lex->select_lex.context;
  for (; field_info->field_name; field_info++)
  {
    if (field_info->old_name)
    {
      Item_field *field= new Item_field(context,
                                        NullS, NullS, field_info->field_name);
      if (field)
      {
        field->item_name.copy(field_info->old_name);
        if (add_item_to_list(thd, field))
          return 1;
      }
    }
  }
  return 0;
}


int make_schemata_old_format(THD *thd, ST_SCHEMA_TABLE *schema_table)
{
  char tmp[128];
  LEX *lex= thd->lex;
  SELECT_LEX *sel= lex->current_select;
  Name_resolution_context *context= &sel->context;

  if (!sel->item_list.elements)
  {
    ST_FIELD_INFO *field_info= &schema_table->fields_info[1];
    String buffer(tmp,sizeof(tmp), system_charset_info);
    Item_field *field= new Item_field(context,
                                      NullS, NullS, field_info->field_name);
    if (!field || add_item_to_list(thd, field))
      return 1;
    buffer.length(0);
    buffer.append(field_info->old_name);
    if (lex->wild && lex->wild->ptr())
    {
      buffer.append(STRING_WITH_LEN(" ("));
      buffer.append(lex->wild->ptr());
      buffer.append(')');
    }
    field->item_name.copy(buffer.ptr(), buffer.length(), system_charset_info);
  }
  return 0;
}


int make_table_names_old_format(THD *thd, ST_SCHEMA_TABLE *schema_table)
{
  char tmp[128];
  String buffer(tmp,sizeof(tmp), thd->charset());
  LEX *lex= thd->lex;
  Name_resolution_context *context= &lex->select_lex.context;

  ST_FIELD_INFO *field_info= &schema_table->fields_info[2];
  buffer.length(0);
  buffer.append(field_info->old_name);
  buffer.append(lex->select_lex.db);
  if (lex->wild && lex->wild->ptr())
  {
    buffer.append(STRING_WITH_LEN(" ("));
    buffer.append(lex->wild->ptr());
    buffer.append(')');
  }
  Item_field *field= new Item_field(context,
                                    NullS, NullS, field_info->field_name);
  if (add_item_to_list(thd, field))
    return 1;
  field->item_name.copy(buffer.ptr(), buffer.length(), system_charset_info);
  if (thd->lex->verbose)
  {
    field->item_name.copy(buffer.ptr(), buffer.length(), system_charset_info);
    field_info= &schema_table->fields_info[3];
    field= new Item_field(context, NullS, NullS, field_info->field_name);
    if (add_item_to_list(thd, field))
      return 1;
    field->item_name.copy(field_info->old_name);
  }
  return 0;
}


int make_columns_old_format(THD *thd, ST_SCHEMA_TABLE *schema_table)
{
  int fields_arr[]= {IS_COLUMNS_COLUMN_NAME,
                     IS_COLUMNS_COLUMN_TYPE,
                     IS_COLUMNS_COLLATION_NAME,
                     IS_COLUMNS_IS_NULLABLE,
                     IS_COLUMNS_COLUMN_KEY,
                     IS_COLUMNS_COLUMN_DEFAULT,
                     IS_COLUMNS_EXTRA,
                     IS_COLUMNS_PRIVILEGES,
                     IS_COLUMNS_COLUMN_COMMENT,
                     -1};
  int *field_num= fields_arr;
  ST_FIELD_INFO *field_info;
  Name_resolution_context *context= &thd->lex->select_lex.context;

  for (; *field_num >= 0; field_num++)
  {
    field_info= &schema_table->fields_info[*field_num];
    if (!thd->lex->verbose && (*field_num == IS_COLUMNS_COLLATION_NAME ||
                               *field_num == IS_COLUMNS_PRIVILEGES     ||
                               *field_num == IS_COLUMNS_COLUMN_COMMENT))
      continue;
    Item_field *field= new Item_field(context,
                                      NullS, NullS, field_info->field_name);
    if (field)
    {
      field->item_name.copy(field_info->old_name);
      if (add_item_to_list(thd, field))
        return 1;
    }
  }
  return 0;
}


int make_character_sets_old_format(THD *thd, ST_SCHEMA_TABLE *schema_table)
{
  int fields_arr[]= {0, 2, 1, 3, -1};
  int *field_num= fields_arr;
  ST_FIELD_INFO *field_info;
  Name_resolution_context *context= &thd->lex->select_lex.context;

  for (; *field_num >= 0; field_num++)
  {
    field_info= &schema_table->fields_info[*field_num];
    Item_field *field= new Item_field(context,
                                      NullS, NullS, field_info->field_name);
    if (field)
    {
      field->item_name.copy(field_info->old_name);
      if (add_item_to_list(thd, field))
        return 1;
    }
  }
  return 0;
}

ST_FIELD_INFO schema_fields_info[]=
{
  {"CATALOG_NAME", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"SCHEMA_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Database",
   SKIP_OPEN_TABLE},
  {"DEFAULT_CHARACTER_SET_NAME", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0, 0,
   SKIP_OPEN_TABLE},
  {"DEFAULT_COLLATION_NAME", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0, 0,
   SKIP_OPEN_TABLE},
  {"SQL_PATH", FN_REFLEN, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO tables_fields_info[]=
{
  {"TABLE_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLE_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Name",
   SKIP_OPEN_TABLE},
  {"TABLE_TYPE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"ENGINE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, "Engine", OPEN_FRM_ONLY},
  {"VERSION", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Version", OPEN_FRM_ONLY},
  {"ROW_FORMAT", 20, MYSQL_TYPE_STRING, 0, 1, "Row_format", OPEN_FULL_TABLE},
  {"TABLE_ROWS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Rows", OPEN_FULL_TABLE},
  {"AVG_ROW_LENGTH", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0, 
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Avg_row_length", OPEN_FULL_TABLE},
  {"DATA_LENGTH", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0, 
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Data_length", OPEN_FULL_TABLE},
  {"MAX_DATA_LENGTH", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Max_data_length", OPEN_FULL_TABLE},
  {"INDEX_LENGTH", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0, 
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Index_length", OPEN_FULL_TABLE},
  {"DATA_FREE", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Data_free", OPEN_FULL_TABLE},
  {"AUTO_INCREMENT", MY_INT64_NUM_DECIMAL_DIGITS , MYSQL_TYPE_LONGLONG, 0, 
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Auto_increment", OPEN_FULL_TABLE},
  {"CREATE_TIME", 0, MYSQL_TYPE_DATETIME, 0, 1, "Create_time", OPEN_FULL_TABLE},
  {"UPDATE_TIME", 0, MYSQL_TYPE_DATETIME, 0, 1, "Update_time", OPEN_FULL_TABLE},
  {"CHECK_TIME", 0, MYSQL_TYPE_DATETIME, 0, 1, "Check_time", OPEN_FULL_TABLE},
  {"TABLE_COLLATION", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 1, "Collation",
   OPEN_FRM_ONLY},
  {"CHECKSUM", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Checksum", OPEN_FULL_TABLE},
  {"CREATE_OPTIONS", 255, MYSQL_TYPE_STRING, 0, 1, "Create_options",
   OPEN_FRM_ONLY},
  {"TABLE_COMMENT", TABLE_COMMENT_MAXLEN, MYSQL_TYPE_STRING, 0, 0, 
   "Comment", OPEN_FRM_ONLY},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};

ST_FIELD_INFO temporary_table_fields_info[]=
{
  {"SESSION_ID", 4, MYSQL_TYPE_LONGLONG, 0, 0, "Session", SKIP_OPEN_TABLE},
  {"TABLE_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Db", SKIP_OPEN_TABLE},
  {"TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Temp_tables_in_", SKIP_OPEN_TABLE},
  {"ENGINE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Engine", OPEN_FRM_ONLY},
  {"NAME", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, "Name", SKIP_OPEN_TABLE},
  {"TABLE_ROWS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Rows", OPEN_FULL_TABLE},
  {"AVG_ROW_LENGTH", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0, 
   MY_I_S_UNSIGNED, "Avg Row", OPEN_FULL_TABLE},
  {"DATA_LENGTH", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0, 
   MY_I_S_UNSIGNED, "Data Length", OPEN_FULL_TABLE},
  {"INDEX_LENGTH", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0, 
   MY_I_S_UNSIGNED, "Index Size", OPEN_FULL_TABLE},
  {"CREATE_TIME", 0, MYSQL_TYPE_DATETIME, 0, 1, "Create Time", OPEN_FULL_TABLE},
  {"UPDATE_TIME", 0, MYSQL_TYPE_DATETIME, 0, 1, "Update Time", OPEN_FULL_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};

ST_FIELD_INFO columns_fields_info[]=
{
  {"TABLE_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"TABLE_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"COLUMN_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Field",
   OPEN_FRM_ONLY},
  {"ORDINAL_POSITION", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, 0, OPEN_FRM_ONLY},
  {"COLUMN_DEFAULT", MAX_FIELD_VARCHARLENGTH, MYSQL_TYPE_STRING, 0,
   1, "Default", OPEN_FRM_ONLY},
  {"IS_NULLABLE", 3, MYSQL_TYPE_STRING, 0, 0, "Null", OPEN_FRM_ONLY},
  {"DATA_TYPE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"CHARACTER_MAXIMUM_LENGTH", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, OPEN_FRM_ONLY},
  {"CHARACTER_OCTET_LENGTH", MY_INT64_NUM_DECIMAL_DIGITS , MYSQL_TYPE_LONGLONG,
   0, (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, OPEN_FRM_ONLY},
  {"NUMERIC_PRECISION", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, OPEN_FRM_ONLY},
  {"NUMERIC_SCALE", MY_INT64_NUM_DECIMAL_DIGITS , MYSQL_TYPE_LONGLONG,
   0, (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, OPEN_FRM_ONLY},
  {"DATETIME_PRECISION", MY_INT64_NUM_DECIMAL_DIGITS , MYSQL_TYPE_LONGLONG,
   0, (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, OPEN_FULL_TABLE},
  {"CHARACTER_SET_NAME", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 1, 0,
   OPEN_FRM_ONLY},
  {"COLLATION_NAME", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 1, "Collation",
   OPEN_FRM_ONLY},
  {"COLUMN_TYPE", 65535, MYSQL_TYPE_STRING, 0, 0, "Type", OPEN_FRM_ONLY},
  {"COLUMN_KEY", 3, MYSQL_TYPE_STRING, 0, 0, "Key", OPEN_FRM_ONLY},
  {"EXTRA", 30, MYSQL_TYPE_STRING, 0, 0, "Extra", OPEN_FRM_ONLY},
  {"PRIVILEGES", 80, MYSQL_TYPE_STRING, 0, 0, "Privileges", OPEN_FRM_ONLY},
  {"COLUMN_COMMENT", COLUMN_COMMENT_MAXLEN, MYSQL_TYPE_STRING, 0, 0, 
   "Comment", OPEN_FRM_ONLY},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO charsets_fields_info[]=
{
  {"CHARACTER_SET_NAME", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0, "Charset",
   SKIP_OPEN_TABLE},
  {"DEFAULT_COLLATE_NAME", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0,
   "Default collation", SKIP_OPEN_TABLE},
  {"DESCRIPTION", 60, MYSQL_TYPE_STRING, 0, 0, "Description",
   SKIP_OPEN_TABLE},
  {"MAXLEN", 3, MYSQL_TYPE_LONGLONG, 0, 0, "Maxlen", SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO collation_fields_info[]=
{
  {"COLLATION_NAME", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0, "Collation",
   SKIP_OPEN_TABLE},
  {"CHARACTER_SET_NAME", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0, "Charset",
   SKIP_OPEN_TABLE},
  {"ID", MY_INT32_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0, 0, "Id",
   SKIP_OPEN_TABLE},
  {"IS_DEFAULT", 3, MYSQL_TYPE_STRING, 0, 0, "Default", SKIP_OPEN_TABLE},
  {"IS_COMPILED", 3, MYSQL_TYPE_STRING, 0, 0, "Compiled", SKIP_OPEN_TABLE},
  {"SORTLEN", 3, MYSQL_TYPE_LONGLONG, 0, 0, "Sortlen", SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO engines_fields_info[]=
{
  {"ENGINE", 64, MYSQL_TYPE_STRING, 0, 0, "Engine", SKIP_OPEN_TABLE},
  {"SUPPORT", 8, MYSQL_TYPE_STRING, 0, 0, "Support", SKIP_OPEN_TABLE},
  {"COMMENT", 80, MYSQL_TYPE_STRING, 0, 0, "Comment", SKIP_OPEN_TABLE},
  {"TRANSACTIONS", 3, MYSQL_TYPE_STRING, 0, 1, "Transactions", SKIP_OPEN_TABLE},
  {"XA", 3, MYSQL_TYPE_STRING, 0, 1, "XA", SKIP_OPEN_TABLE},
  {"SAVEPOINTS", 3 ,MYSQL_TYPE_STRING, 0, 1, "Savepoints", SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO events_fields_info[]=
{
  {"EVENT_CATALOG", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"EVENT_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Db",
   SKIP_OPEN_TABLE},
  {"EVENT_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Name",
   SKIP_OPEN_TABLE},
  {"DEFINER", 77, MYSQL_TYPE_STRING, 0, 0, "Definer", SKIP_OPEN_TABLE},
  {"TIME_ZONE", 64, MYSQL_TYPE_STRING, 0, 0, "Time zone", SKIP_OPEN_TABLE},
  {"EVENT_BODY", 8, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"EVENT_DEFINITION", 65535, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"EVENT_TYPE", 9, MYSQL_TYPE_STRING, 0, 0, "Type", SKIP_OPEN_TABLE},
  {"EXECUTE_AT", 0, MYSQL_TYPE_DATETIME, 0, 1, "Execute at", SKIP_OPEN_TABLE},
  {"INTERVAL_VALUE", 256, MYSQL_TYPE_STRING, 0, 1, "Interval value",
   SKIP_OPEN_TABLE},
  {"INTERVAL_FIELD", 18, MYSQL_TYPE_STRING, 0, 1, "Interval field",
   SKIP_OPEN_TABLE},
  {"SQL_MODE", 32*256, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"STARTS", 0, MYSQL_TYPE_DATETIME, 0, 1, "Starts", SKIP_OPEN_TABLE},
  {"ENDS", 0, MYSQL_TYPE_DATETIME, 0, 1, "Ends", SKIP_OPEN_TABLE},
  {"STATUS", 18, MYSQL_TYPE_STRING, 0, 0, "Status", SKIP_OPEN_TABLE},
  {"ON_COMPLETION", 12, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"CREATED", 0, MYSQL_TYPE_DATETIME, 0, 0, 0, SKIP_OPEN_TABLE},
  {"LAST_ALTERED", 0, MYSQL_TYPE_DATETIME, 0, 0, 0, SKIP_OPEN_TABLE},
  {"LAST_EXECUTED", 0, MYSQL_TYPE_DATETIME, 0, 1, 0, SKIP_OPEN_TABLE},
  {"EVENT_COMMENT", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"ORIGINATOR", 10, MYSQL_TYPE_LONGLONG, 0, 0, "Originator", SKIP_OPEN_TABLE},
  {"CHARACTER_SET_CLIENT", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0,
   "character_set_client", SKIP_OPEN_TABLE},
  {"COLLATION_CONNECTION", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0,
   "collation_connection", SKIP_OPEN_TABLE},
  {"DATABASE_COLLATION", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0,
   "Database Collation", SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};



ST_FIELD_INFO coll_charset_app_fields_info[]=
{
  {"COLLATION_NAME", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0, 0,
   SKIP_OPEN_TABLE},
  {"CHARACTER_SET_NAME", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0, 0,
   SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO proc_fields_info[]=
{
  {"SPECIFIC_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"ROUTINE_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"ROUTINE_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Db",
   SKIP_OPEN_TABLE},
  {"ROUTINE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Name",
   SKIP_OPEN_TABLE},
  {"ROUTINE_TYPE", 9, MYSQL_TYPE_STRING, 0, 0, "Type", SKIP_OPEN_TABLE},
  {"DATA_TYPE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"CHARACTER_MAXIMUM_LENGTH", 21 , MYSQL_TYPE_LONG, 0, 1, 0, SKIP_OPEN_TABLE},
  {"CHARACTER_OCTET_LENGTH", 21 , MYSQL_TYPE_LONG, 0, 1, 0, SKIP_OPEN_TABLE},
  {"NUMERIC_PRECISION", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, SKIP_OPEN_TABLE},
  {"NUMERIC_SCALE", 21 , MYSQL_TYPE_LONG, 0, 1, 0, SKIP_OPEN_TABLE},
  {"DATETIME_PRECISION", MY_INT64_NUM_DECIMAL_DIGITS , MYSQL_TYPE_LONGLONG,
   0, (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, SKIP_OPEN_TABLE},
  {"CHARACTER_SET_NAME", 64, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {"COLLATION_NAME", 64, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {"DTD_IDENTIFIER", 65535, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {"ROUTINE_BODY", 8, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"ROUTINE_DEFINITION", 65535, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {"EXTERNAL_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {"EXTERNAL_LANGUAGE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0,
   SKIP_OPEN_TABLE},
  {"PARAMETER_STYLE", 8, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"IS_DETERMINISTIC", 3, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"SQL_DATA_ACCESS", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0,
   SKIP_OPEN_TABLE},
  {"SQL_PATH", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {"SECURITY_TYPE", 7, MYSQL_TYPE_STRING, 0, 0, "Security_type",
   SKIP_OPEN_TABLE},
  {"CREATED", 0, MYSQL_TYPE_DATETIME, 0, 0, "Created", SKIP_OPEN_TABLE},
  {"LAST_ALTERED", 0, MYSQL_TYPE_DATETIME, 0, 0, "Modified", SKIP_OPEN_TABLE},
  {"SQL_MODE", 32*256, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"ROUTINE_COMMENT", 65535, MYSQL_TYPE_STRING, 0, 0, "Comment",
   SKIP_OPEN_TABLE},
  {"DEFINER", 77, MYSQL_TYPE_STRING, 0, 0, "Definer", SKIP_OPEN_TABLE},
  {"CHARACTER_SET_CLIENT", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0,
   "character_set_client", SKIP_OPEN_TABLE},
  {"COLLATION_CONNECTION", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0,
   "collation_connection", SKIP_OPEN_TABLE},
  {"DATABASE_COLLATION", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0,
   "Database Collation", SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO stat_fields_info[]=
{
  {"TABLE_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"TABLE_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Table", OPEN_FRM_ONLY},
  {"NON_UNIQUE", 1, MYSQL_TYPE_LONGLONG, 0, 0, "Non_unique", OPEN_FRM_ONLY},
  {"INDEX_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"INDEX_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Key_name",
   OPEN_FRM_ONLY},
  {"SEQ_IN_INDEX", 2, MYSQL_TYPE_LONGLONG, 0, 0, "Seq_in_index", OPEN_FRM_ONLY},
  {"COLUMN_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Column_name",
   OPEN_FRM_ONLY},
  {"COLLATION", 1, MYSQL_TYPE_STRING, 0, 1, "Collation", OPEN_FRM_ONLY},
  {"CARDINALITY", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0, 1,
   "Cardinality", OPEN_FULL_TABLE},
  {"SUB_PART", 3, MYSQL_TYPE_LONGLONG, 0, 1, "Sub_part", OPEN_FRM_ONLY},
  {"PACKED", 10, MYSQL_TYPE_STRING, 0, 1, "Packed", OPEN_FRM_ONLY},
  {"NULLABLE", 3, MYSQL_TYPE_STRING, 0, 0, "Null", OPEN_FRM_ONLY},
  {"INDEX_TYPE", 16, MYSQL_TYPE_STRING, 0, 0, "Index_type", OPEN_FULL_TABLE},
  {"COMMENT", 16, MYSQL_TYPE_STRING, 0, 1, "Comment", OPEN_FRM_ONLY},
  {"INDEX_COMMENT", INDEX_COMMENT_MAXLEN, MYSQL_TYPE_STRING, 0, 0, 
   "Index_comment", OPEN_FRM_ONLY},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO view_fields_info[]=
{
  {"TABLE_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"TABLE_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"VIEW_DEFINITION", 65535, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"CHECK_OPTION", 8, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"IS_UPDATABLE", 3, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"DEFINER", 77, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"SECURITY_TYPE", 7, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"CHARACTER_SET_CLIENT", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FRM_ONLY},
  {"COLLATION_CONNECTION", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FRM_ONLY},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO user_privileges_fields_info[]=
{
  {"GRANTEE", 81, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLE_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"PRIVILEGE_TYPE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"IS_GRANTABLE", 3, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO schema_privileges_fields_info[]=
{
  {"GRANTEE", 81, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLE_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLE_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"PRIVILEGE_TYPE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"IS_GRANTABLE", 3, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO table_privileges_fields_info[]=
{
  {"GRANTEE", 81, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLE_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLE_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"PRIVILEGE_TYPE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"IS_GRANTABLE", 3, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO column_privileges_fields_info[]=
{
  {"GRANTEE", 81, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLE_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLE_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"COLUMN_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"PRIVILEGE_TYPE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"IS_GRANTABLE", 3, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO table_constraints_fields_info[]=
{
  {"CONSTRAINT_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"CONSTRAINT_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FULL_TABLE},
  {"CONSTRAINT_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FULL_TABLE},
  {"TABLE_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"CONSTRAINT_TYPE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FULL_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO key_column_usage_fields_info[]=
{
  {"CONSTRAINT_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"CONSTRAINT_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FULL_TABLE},
  {"CONSTRAINT_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FULL_TABLE},
  {"TABLE_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"TABLE_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"COLUMN_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"ORDINAL_POSITION", 10 ,MYSQL_TYPE_LONGLONG, 0, 0, 0, OPEN_FULL_TABLE},
  {"POSITION_IN_UNIQUE_CONSTRAINT", 10 ,MYSQL_TYPE_LONGLONG, 0, 1, 0,
   OPEN_FULL_TABLE},
  {"REFERENCED_TABLE_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0,
   OPEN_FULL_TABLE},
  {"REFERENCED_TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0,
   OPEN_FULL_TABLE},
  {"REFERENCED_COLUMN_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0,
   OPEN_FULL_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO table_names_fields_info[]=
{
  {"TABLE_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLE_SCHEMA",NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Tables_in_",
   SKIP_OPEN_TABLE},
  {"TABLE_TYPE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Table_type",
   OPEN_FRM_ONLY},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO open_tables_fields_info[]=
{
  {"Database", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Database",
   SKIP_OPEN_TABLE},
  {"Table",NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Table", SKIP_OPEN_TABLE},
  {"In_use", 1, MYSQL_TYPE_LONGLONG, 0, 0, "In_use", SKIP_OPEN_TABLE},
  {"Name_locked", 4, MYSQL_TYPE_LONGLONG, 0, 0, "Name_locked", SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO triggers_fields_info[]=
{
  {"TRIGGER_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"TRIGGER_SCHEMA",NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"TRIGGER_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Trigger",
   OPEN_FRM_ONLY},
  {"EVENT_MANIPULATION", 6, MYSQL_TYPE_STRING, 0, 0, "Event", OPEN_FRM_ONLY},
  {"EVENT_OBJECT_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FRM_ONLY},
  {"EVENT_OBJECT_SCHEMA",NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FRM_ONLY},
  {"EVENT_OBJECT_TABLE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Table",
   OPEN_FRM_ONLY},
  {"ACTION_ORDER", 4, MYSQL_TYPE_LONGLONG, 0, 0, 0, OPEN_FRM_ONLY},
  {"ACTION_CONDITION", 65535, MYSQL_TYPE_STRING, 0, 1, 0, OPEN_FRM_ONLY},
  {"ACTION_STATEMENT", 65535, MYSQL_TYPE_STRING, 0, 0, "Statement",
   OPEN_FRM_ONLY},
  {"ACTION_ORIENTATION", 9, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"ACTION_TIMING", 6, MYSQL_TYPE_STRING, 0, 0, "Timing", OPEN_FRM_ONLY},
  {"ACTION_REFERENCE_OLD_TABLE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0,
   OPEN_FRM_ONLY},
  {"ACTION_REFERENCE_NEW_TABLE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0,
   OPEN_FRM_ONLY},
  {"ACTION_REFERENCE_OLD_ROW", 3, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"ACTION_REFERENCE_NEW_ROW", 3, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FRM_ONLY},
  {"CREATED", 0, MYSQL_TYPE_DATETIME, 0, 1, "Created", OPEN_FRM_ONLY},
  {"SQL_MODE", 32*256, MYSQL_TYPE_STRING, 0, 0, "sql_mode", OPEN_FRM_ONLY},
  {"DEFINER", 77, MYSQL_TYPE_STRING, 0, 0, "Definer", OPEN_FRM_ONLY},
  {"CHARACTER_SET_CLIENT", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0,
   "character_set_client", OPEN_FRM_ONLY},
  {"COLLATION_CONNECTION", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0,
   "collation_connection", OPEN_FRM_ONLY},
  {"DATABASE_COLLATION", MY_CS_NAME_SIZE, MYSQL_TYPE_STRING, 0, 0,
   "Database Collation", OPEN_FRM_ONLY},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO partitions_fields_info[]=
{
  {"TABLE_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"TABLE_SCHEMA",NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"PARTITION_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0, OPEN_FULL_TABLE},
  {"SUBPARTITION_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0,
   OPEN_FULL_TABLE},
  {"PARTITION_ORDINAL_POSITION", 21 , MYSQL_TYPE_LONGLONG, 0,
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, OPEN_FULL_TABLE},
  {"SUBPARTITION_ORDINAL_POSITION", 21 , MYSQL_TYPE_LONGLONG, 0,
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, OPEN_FULL_TABLE},
  {"PARTITION_METHOD", 18, MYSQL_TYPE_STRING, 0, 1, 0, OPEN_FULL_TABLE},
  {"SUBPARTITION_METHOD", 12, MYSQL_TYPE_STRING, 0, 1, 0, OPEN_FULL_TABLE},
  {"PARTITION_EXPRESSION", 65535, MYSQL_TYPE_STRING, 0, 1, 0, OPEN_FULL_TABLE},
  {"SUBPARTITION_EXPRESSION", 65535, MYSQL_TYPE_STRING, 0, 1, 0,
   OPEN_FULL_TABLE},
  {"PARTITION_DESCRIPTION", 65535, MYSQL_TYPE_STRING, 0, 1, 0, OPEN_FULL_TABLE},
  {"TABLE_ROWS", 21 , MYSQL_TYPE_LONGLONG, 0, MY_I_S_UNSIGNED, 0,
   OPEN_FULL_TABLE},
  {"AVG_ROW_LENGTH", 21 , MYSQL_TYPE_LONGLONG, 0, MY_I_S_UNSIGNED, 0,
   OPEN_FULL_TABLE},
  {"DATA_LENGTH", 21 , MYSQL_TYPE_LONGLONG, 0, MY_I_S_UNSIGNED, 0,
   OPEN_FULL_TABLE},
  {"MAX_DATA_LENGTH", 21 , MYSQL_TYPE_LONGLONG, 0,
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, OPEN_FULL_TABLE},
  {"INDEX_LENGTH", 21 , MYSQL_TYPE_LONGLONG, 0, MY_I_S_UNSIGNED, 0,
   OPEN_FULL_TABLE},
  {"DATA_FREE", 21 , MYSQL_TYPE_LONGLONG, 0, MY_I_S_UNSIGNED, 0,
   OPEN_FULL_TABLE},
  {"CREATE_TIME", 0, MYSQL_TYPE_DATETIME, 0, 1, 0, OPEN_FULL_TABLE},
  {"UPDATE_TIME", 0, MYSQL_TYPE_DATETIME, 0, 1, 0, OPEN_FULL_TABLE},
  {"CHECK_TIME", 0, MYSQL_TYPE_DATETIME, 0, 1, 0, OPEN_FULL_TABLE},
  {"CHECKSUM", 21 , MYSQL_TYPE_LONGLONG, 0,
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, OPEN_FULL_TABLE},
  {"PARTITION_COMMENT", 80, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"NODEGROUP", 12 , MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"TABLESPACE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0,
   OPEN_FULL_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO variables_fields_info[]=
{
  {"VARIABLE_NAME", 64, MYSQL_TYPE_STRING, 0, 0, "Variable_name",
   SKIP_OPEN_TABLE},
  {"VARIABLE_VALUE", 1024, MYSQL_TYPE_STRING, 0, 1, "Value", SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO user_stats_fields_info[]=
{
  {"USER", USERNAME_LENGTH, MYSQL_TYPE_STRING, 0, 0, "User", SKIP_OPEN_TABLE},
  {"TOTAL_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Total_connections", SKIP_OPEN_TABLE},
  {"CONCURRENT_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, MY_I_S_UNSIGNED, "Concurrent_connections", SKIP_OPEN_TABLE},
  {"CONNECTED_TIME", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Connected_time", SKIP_OPEN_TABLE},
  {"BUSY_TIME", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Busy_time", SKIP_OPEN_TABLE},
  {"CPU_TIME", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Cpu_time", SKIP_OPEN_TABLE},
  {"BYTES_RECEIVED", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Bytes_received", SKIP_OPEN_TABLE},
  {"BYTES_SENT", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Bytes_sent", SKIP_OPEN_TABLE},
  {"BINLOG_BYTES_WRITTEN", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, MY_I_S_UNSIGNED, "Binlog_bytes_written", SKIP_OPEN_TABLE},
  {"ROWS_FETCHED", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Rows_fetched", SKIP_OPEN_TABLE},
  {"ROWS_UPDATED", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Rows_updated", SKIP_OPEN_TABLE},
  {"TABLE_ROWS_READ", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Table_rows_read", SKIP_OPEN_TABLE},
  {"SELECT_COMMANDS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Select_commands", SKIP_OPEN_TABLE},
  {"UPDATE_COMMANDS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Update_commands", SKIP_OPEN_TABLE},
  {"OTHER_COMMANDS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Other_commands", SKIP_OPEN_TABLE},
  {"COMMIT_TRANSACTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Commit_transactions", SKIP_OPEN_TABLE},
  {"ROLLBACK_TRANSACTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, MY_I_S_UNSIGNED, "Rollback_transactions", SKIP_OPEN_TABLE},
  {"DENIED_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Denied_connections", SKIP_OPEN_TABLE},
  {"LOST_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Lost_connections", SKIP_OPEN_TABLE},
  {"ACCESS_DENIED", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Access_denied", SKIP_OPEN_TABLE},
  {"EMPTY_QUERIES", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Empty_queries", SKIP_OPEN_TABLE},
  {"TOTAL_SSL_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, MY_I_S_UNSIGNED, "Total_ssl_connections", SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, 0}
};

ST_FIELD_INFO client_stats_fields_info[]=
{
  {"CLIENT", LIST_PROCESS_HOST_LEN, MYSQL_TYPE_STRING, 0, 0, "Client",
   SKIP_OPEN_TABLE},
  {"TOTAL_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Total_connections", SKIP_OPEN_TABLE},
  {"CONCURRENT_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, MY_I_S_UNSIGNED, "Concurrent_connections", SKIP_OPEN_TABLE},
  {"CONNECTED_TIME", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Connected_time", SKIP_OPEN_TABLE},
  {"BUSY_TIME", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Busy_time", SKIP_OPEN_TABLE},
  {"CPU_TIME", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Cpu_time", SKIP_OPEN_TABLE},
  {"BYTES_RECEIVED", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Bytes_received", SKIP_OPEN_TABLE},
  {"BYTES_SENT", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Bytes_sent", SKIP_OPEN_TABLE},
  {"BINLOG_BYTES_WRITTEN", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, MY_I_S_UNSIGNED, "Binlog_bytes_written", SKIP_OPEN_TABLE},
  {"ROWS_FETCHED", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Rows_fetched", SKIP_OPEN_TABLE},
  {"ROWS_UPDATED", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Rows_updated", SKIP_OPEN_TABLE},
  {"TABLE_ROWS_READ", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Table_rows_read", SKIP_OPEN_TABLE},
  {"SELECT_COMMANDS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Select_commands", SKIP_OPEN_TABLE},
  {"UPDATE_COMMANDS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Update_commands", SKIP_OPEN_TABLE},
  {"OTHER_COMMANDS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Other_commands", SKIP_OPEN_TABLE},
  {"COMMIT_TRANSACTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Commit_transactions", SKIP_OPEN_TABLE},
  {"ROLLBACK_TRANSACTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, MY_I_S_UNSIGNED, "Rollback_transactions", SKIP_OPEN_TABLE},
  {"DENIED_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Denied_connections", SKIP_OPEN_TABLE},
  {"LOST_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Lost_connections", SKIP_OPEN_TABLE},
  {"ACCESS_DENIED", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Access_denied", SKIP_OPEN_TABLE},
  {"EMPTY_QUERIES", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Empty_queries", SKIP_OPEN_TABLE},
  {"TOTAL_SSL_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, MY_I_S_UNSIGNED, "Total_ssl_connections", SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, 0}
};

ST_FIELD_INFO thread_stats_fields_info[]=
{
  {"THREAD_ID", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Thread_id", SKIP_OPEN_TABLE},
  {"TOTAL_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Total_connections", SKIP_OPEN_TABLE},
  {"CONCURRENT_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, MY_I_S_UNSIGNED, "Concurrent_connections", SKIP_OPEN_TABLE},
  {"CONNECTED_TIME", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Connected_time", SKIP_OPEN_TABLE},
  {"BUSY_TIME", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Busy_time", SKIP_OPEN_TABLE},
  {"CPU_TIME", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Cpu_time", SKIP_OPEN_TABLE},
  {"BYTES_RECEIVED", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Bytes_received", SKIP_OPEN_TABLE},
  {"BYTES_SENT", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Bytes_sent", SKIP_OPEN_TABLE},
  {"BINLOG_BYTES_WRITTEN", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Binlog_bytes_written", SKIP_OPEN_TABLE},
  {"ROWS_FETCHED", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Rows_fetched", SKIP_OPEN_TABLE},
  {"ROWS_UPDATED", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Rows_updated", SKIP_OPEN_TABLE},
  {"TABLE_ROWS_READ", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Table_rows_read", SKIP_OPEN_TABLE},
  {"SELECT_COMMANDS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Select_commands", SKIP_OPEN_TABLE},
  {"UPDATE_COMMANDS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Update_commands", SKIP_OPEN_TABLE},
  {"OTHER_COMMANDS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Other_commands", SKIP_OPEN_TABLE},
  {"COMMIT_TRANSACTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Commit_transactions", SKIP_OPEN_TABLE},
  {"ROLLBACK_TRANSACTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, MY_I_S_UNSIGNED, "Rollback_transactions", SKIP_OPEN_TABLE},
  {"DENIED_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Denied_connections", SKIP_OPEN_TABLE},
  {"LOST_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Lost_connections", SKIP_OPEN_TABLE},
  {"ACCESS_DENIED", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Access_denied", SKIP_OPEN_TABLE},
  {"EMPTY_QUERIES", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Empty_queries", SKIP_OPEN_TABLE},
  {"TOTAL_SSL_CONNECTIONS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, MY_I_S_UNSIGNED, "Total_ssl_connections", SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, 0}
};

ST_FIELD_INFO table_stats_fields_info[]=
{
  {"TABLE_SCHEMA", NAME_LEN, MYSQL_TYPE_STRING, 0, 0, "Table_schema",
   SKIP_OPEN_TABLE},
  {"TABLE_NAME", NAME_LEN, MYSQL_TYPE_STRING, 0, 0, "Table_name",
   SKIP_OPEN_TABLE},
  {"ROWS_READ", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Rows_read", SKIP_OPEN_TABLE},
  {"ROWS_CHANGED", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Rows_changed", SKIP_OPEN_TABLE},
  {"ROWS_CHANGED_X_INDEXES", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, MY_I_S_UNSIGNED, "Rows_changed_x_#indexes", SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, 0}
};

ST_FIELD_INFO index_stats_fields_info[]=
{
  {"TABLE_SCHEMA", NAME_LEN, MYSQL_TYPE_STRING, 0, 0, "Table_schema",
   SKIP_OPEN_TABLE},
  {"TABLE_NAME", NAME_LEN, MYSQL_TYPE_STRING, 0, 0, "Table_name",
   SKIP_OPEN_TABLE},
  {"INDEX_NAME", NAME_LEN, MYSQL_TYPE_STRING, 0, 0, "Index_name",
   SKIP_OPEN_TABLE},
  {"ROWS_READ", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Rows_read", SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, 0}
};



#define TIME_FLOAT_DIGITS 9
/** two vals encoded: (dec*100)+len */
#define TIME_I_S_DECIMAL_SIZE (TIME_FLOAT_DIGITS*100)+(TIME_FLOAT_DIGITS-3)

#define MAX_QUERY_LENGTH 300U
#define MAX_QUERY_HISTORY 101U

ST_FIELD_INFO query_profile_statistics_info[]=
{
    /* name, length, type, value, maybe_null, old_name, open_method */
    {"QUERY_ID", 20, MYSQL_TYPE_LONG, 0, false, "Query_id", SKIP_OPEN_TABLE},
    {"SEQ", 20, MYSQL_TYPE_LONG, 0, false, "Seq", SKIP_OPEN_TABLE},
    {"STATE", 30, MYSQL_TYPE_STRING, 0, false, "Status", SKIP_OPEN_TABLE},
    {"DURATION", TIME_I_S_DECIMAL_SIZE, MYSQL_TYPE_DECIMAL, 0, false, "Duration", SKIP_OPEN_TABLE},
    {"CPU_USER", TIME_I_S_DECIMAL_SIZE, MYSQL_TYPE_DECIMAL, 0, true, "CPU_user", SKIP_OPEN_TABLE},
                {"CPU_SYSTEM", TIME_I_S_DECIMAL_SIZE, MYSQL_TYPE_DECIMAL, 0, true, "CPU_system", SKIP_OPEN_TABLE},
                {"CONTEXT_VOLUNTARY", 20, MYSQL_TYPE_LONG, 0, true, "Context_voluntary", SKIP_OPEN_TABLE},
                {"CONTEXT_INVOLUNTARY", 20, MYSQL_TYPE_LONG, 0, true, "Context_involuntary", SKIP_OPEN_TABLE},
                {"BLOCK_OPS_IN", 20, MYSQL_TYPE_LONG, 0, true, "Block_ops_in", SKIP_OPEN_TABLE},
                {"BLOCK_OPS_OUT", 20, MYSQL_TYPE_LONG, 0, true, "Block_ops_out", SKIP_OPEN_TABLE},
                {"MESSAGES_SENT", 20, MYSQL_TYPE_LONG, 0, true, "Messages_sent", SKIP_OPEN_TABLE},
                {"MESSAGES_RECEIVED", 20, MYSQL_TYPE_LONG, 0, true, "Messages_received", SKIP_OPEN_TABLE},
                {"PAGE_FAULTS_MAJOR", 20, MYSQL_TYPE_LONG, 0, true, "Page_faults_major", SKIP_OPEN_TABLE},
                {"PAGE_FAULTS_MINOR", 20, MYSQL_TYPE_LONG, 0, true, "Page_faults_minor", SKIP_OPEN_TABLE},
                {"SWAPS", 20, MYSQL_TYPE_LONG, 0, true, "Swaps", SKIP_OPEN_TABLE},
                {"SOURCE_FUNCTION", 30, MYSQL_TYPE_STRING, 0, true, "Source_function", SKIP_OPEN_TABLE},
                {"SOURCE_FILE", 20, MYSQL_TYPE_STRING, 0, true, "Source_file", SKIP_OPEN_TABLE},
                {"SOURCE_LINE", 20, MYSQL_TYPE_LONG, 0, true, "Source_line", SKIP_OPEN_TABLE},
                {NULL, 0,  MYSQL_TYPE_STRING, 0, true, NULL, 0}
        };




ST_FIELD_INFO processlist_fields_info[]=
{
  {"ID", 21, MYSQL_TYPE_LONGLONG, 0, MY_I_S_UNSIGNED, "Id", SKIP_OPEN_TABLE},
  {"USER", 16, MYSQL_TYPE_STRING, 0, 0, "User", SKIP_OPEN_TABLE},
  {"HOST", LIST_PROCESS_HOST_LEN,  MYSQL_TYPE_STRING, 0, 0, "Host",
   SKIP_OPEN_TABLE},
  {"DB", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, "Db", SKIP_OPEN_TABLE},
  {"COMMAND", 16, MYSQL_TYPE_STRING, 0, 0, "Command", SKIP_OPEN_TABLE},
  {"TIME", 7, MYSQL_TYPE_LONG, 0, 0, "Time", SKIP_OPEN_TABLE},
  {"STATE", 64, MYSQL_TYPE_STRING, 0, 1, "State", SKIP_OPEN_TABLE},
  {"INFO", PROCESS_LIST_INFO_WIDTH, MYSQL_TYPE_STRING, 0, 1, "Info",
   SKIP_OPEN_TABLE},
  {"TIME_MS", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, 0, "Time_ms", SKIP_OPEN_TABLE},
  {"ROWS_SENT", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Rows_sent", SKIP_OPEN_TABLE},
  {"ROWS_EXAMINED", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_UNSIGNED, "Rows_examined", SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO plugin_fields_info[]=
{
  {"PLUGIN_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, "Name",
   SKIP_OPEN_TABLE},
  {"PLUGIN_VERSION", 20, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"PLUGIN_STATUS", 10, MYSQL_TYPE_STRING, 0, 0, "Status", SKIP_OPEN_TABLE},
  {"PLUGIN_TYPE", 80, MYSQL_TYPE_STRING, 0, 0, "Type", SKIP_OPEN_TABLE},
  {"PLUGIN_TYPE_VERSION", 20, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"PLUGIN_LIBRARY", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, "Library",
   SKIP_OPEN_TABLE},
  {"PLUGIN_LIBRARY_VERSION", 20, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {"PLUGIN_AUTHOR", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {"PLUGIN_DESCRIPTION", 65535, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {"PLUGIN_LICENSE", 80, MYSQL_TYPE_STRING, 0, 1, "License", SKIP_OPEN_TABLE},
  {"LOAD_OPTION", 64, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};

ST_FIELD_INFO files_fields_info[]=
{
  {"FILE_ID", 4, MYSQL_TYPE_LONGLONG, 0, 0, 0, SKIP_OPEN_TABLE},
  {"FILE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {"FILE_TYPE", 20, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLESPACE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0,
   SKIP_OPEN_TABLE},
  {"TABLE_CATALOG", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLE_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {"TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {"LOGFILE_GROUP_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0,
   SKIP_OPEN_TABLE},
  {"LOGFILE_GROUP_NUMBER", 4, MYSQL_TYPE_LONGLONG, 0, 1, 0, SKIP_OPEN_TABLE},
  {"ENGINE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"FULLTEXT_KEYS", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {"DELETED_ROWS", 4, MYSQL_TYPE_LONGLONG, 0, 1, 0, SKIP_OPEN_TABLE},
  {"UPDATE_COUNT", 4, MYSQL_TYPE_LONGLONG, 0, 1, 0, SKIP_OPEN_TABLE},
  {"FREE_EXTENTS", 4, MYSQL_TYPE_LONGLONG, 0, 1, 0, SKIP_OPEN_TABLE},
  {"TOTAL_EXTENTS", 4, MYSQL_TYPE_LONGLONG, 0, 1, 0, SKIP_OPEN_TABLE},
  {"EXTENT_SIZE", 4, MYSQL_TYPE_LONGLONG, 0, 0, 0, SKIP_OPEN_TABLE},
  {"INITIAL_SIZE", 21, MYSQL_TYPE_LONGLONG, 0,
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, SKIP_OPEN_TABLE},
  {"MAXIMUM_SIZE", 21, MYSQL_TYPE_LONGLONG, 0, 
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, SKIP_OPEN_TABLE},
  {"AUTOEXTEND_SIZE", 21, MYSQL_TYPE_LONGLONG, 0, 
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, SKIP_OPEN_TABLE},
  {"CREATION_TIME", 0, MYSQL_TYPE_DATETIME, 0, 1, 0, SKIP_OPEN_TABLE},
  {"LAST_UPDATE_TIME", 0, MYSQL_TYPE_DATETIME, 0, 1, 0, SKIP_OPEN_TABLE},
  {"LAST_ACCESS_TIME", 0, MYSQL_TYPE_DATETIME, 0, 1, 0, SKIP_OPEN_TABLE},
  {"RECOVER_TIME", 4, MYSQL_TYPE_LONGLONG, 0, 1, 0, SKIP_OPEN_TABLE},
  {"TRANSACTION_COUNTER", 4, MYSQL_TYPE_LONGLONG, 0, 1, 0, SKIP_OPEN_TABLE},
  {"VERSION", 21 , MYSQL_TYPE_LONGLONG, 0,
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Version", SKIP_OPEN_TABLE},
  {"ROW_FORMAT", 20, MYSQL_TYPE_STRING, 0, 1, "Row_format", SKIP_OPEN_TABLE},
  {"TABLE_ROWS", 21 , MYSQL_TYPE_LONGLONG, 0,
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Rows", SKIP_OPEN_TABLE},
  {"AVG_ROW_LENGTH", 21 , MYSQL_TYPE_LONGLONG, 0, 
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Avg_row_length", SKIP_OPEN_TABLE},
  {"DATA_LENGTH", 21 , MYSQL_TYPE_LONGLONG, 0, 
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Data_length", SKIP_OPEN_TABLE},
  {"MAX_DATA_LENGTH", 21 , MYSQL_TYPE_LONGLONG, 0, 
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Max_data_length", SKIP_OPEN_TABLE},
  {"INDEX_LENGTH", 21 , MYSQL_TYPE_LONGLONG, 0, 
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Index_length", SKIP_OPEN_TABLE},
  {"DATA_FREE", 21 , MYSQL_TYPE_LONGLONG, 0, 
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Data_free", SKIP_OPEN_TABLE},
  {"CREATE_TIME", 0, MYSQL_TYPE_DATETIME, 0, 1, "Create_time", SKIP_OPEN_TABLE},
  {"UPDATE_TIME", 0, MYSQL_TYPE_DATETIME, 0, 1, "Update_time", SKIP_OPEN_TABLE},
  {"CHECK_TIME", 0, MYSQL_TYPE_DATETIME, 0, 1, "Check_time", SKIP_OPEN_TABLE},
  {"CHECKSUM", 21 , MYSQL_TYPE_LONGLONG, 0, 
   (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), "Checksum", SKIP_OPEN_TABLE},
  {"STATUS", 20, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"EXTRA", 255, MYSQL_TYPE_STRING, 0, 1, 0, SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};

ST_FIELD_INFO referential_constraints_fields_info[]=
{
  {"CONSTRAINT_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"CONSTRAINT_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FULL_TABLE},
  {"CONSTRAINT_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FULL_TABLE},
  {"UNIQUE_CONSTRAINT_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FULL_TABLE},
  {"UNIQUE_CONSTRAINT_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FULL_TABLE},
  {"UNIQUE_CONSTRAINT_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0,
   MY_I_S_MAYBE_NULL, 0, OPEN_FULL_TABLE},
  {"MATCH_OPTION", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"UPDATE_RULE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"DELETE_RULE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"REFERENCED_TABLE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FULL_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


ST_FIELD_INFO parameters_fields_info[]=
{
  {"SPECIFIC_CATALOG", FN_REFLEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"SPECIFIC_SCHEMA", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0,
   OPEN_FULL_TABLE},
  {"SPECIFIC_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"ORDINAL_POSITION", 21 , MYSQL_TYPE_LONG, 0, 0, 0, OPEN_FULL_TABLE},
  {"PARAMETER_MODE", 5, MYSQL_TYPE_STRING, 0, 1, 0, OPEN_FULL_TABLE},
  {"PARAMETER_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 1, 0, OPEN_FULL_TABLE},
  {"DATA_TYPE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"CHARACTER_MAXIMUM_LENGTH", 21 , MYSQL_TYPE_LONG, 0, 1, 0, OPEN_FULL_TABLE},
  {"CHARACTER_OCTET_LENGTH", 21 , MYSQL_TYPE_LONG, 0, 1, 0, OPEN_FULL_TABLE},
  {"NUMERIC_PRECISION", MY_INT64_NUM_DECIMAL_DIGITS, MYSQL_TYPE_LONGLONG,
   0, (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, OPEN_FULL_TABLE},
  {"NUMERIC_SCALE", 21 , MYSQL_TYPE_LONG, 0, 1, 0, OPEN_FULL_TABLE},
  {"DATETIME_PRECISION", MY_INT64_NUM_DECIMAL_DIGITS , MYSQL_TYPE_LONGLONG,
   0, (MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED), 0, OPEN_FULL_TABLE},
  {"CHARACTER_SET_NAME", 64, MYSQL_TYPE_STRING, 0, 1, 0, OPEN_FULL_TABLE},
  {"COLLATION_NAME", 64, MYSQL_TYPE_STRING, 0, 1, 0, OPEN_FULL_TABLE},
  {"DTD_IDENTIFIER", 65535, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {"ROUTINE_TYPE", 9, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, OPEN_FULL_TABLE}
};


ST_FIELD_INFO tablespaces_fields_info[]=
{
  {"TABLESPACE_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0,
   SKIP_OPEN_TABLE},
  {"ENGINE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE},
  {"TABLESPACE_TYPE", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, MY_I_S_MAYBE_NULL,
   0, SKIP_OPEN_TABLE},
  {"LOGFILE_GROUP_NAME", NAME_CHAR_LEN, MYSQL_TYPE_STRING, 0, MY_I_S_MAYBE_NULL,
   0, SKIP_OPEN_TABLE},
  {"EXTENT_SIZE", 21, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED, 0, SKIP_OPEN_TABLE},
  {"AUTOEXTEND_SIZE", 21, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED, 0, SKIP_OPEN_TABLE},
  {"MAXIMUM_SIZE", 21, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED, 0, SKIP_OPEN_TABLE},
  {"NODEGROUP_ID", 21, MYSQL_TYPE_LONGLONG, 0,
   MY_I_S_MAYBE_NULL | MY_I_S_UNSIGNED, 0, SKIP_OPEN_TABLE},
  {"TABLESPACE_COMMENT", 2048, MYSQL_TYPE_STRING, 0, MY_I_S_MAYBE_NULL, 0,
   SKIP_OPEN_TABLE},
  {0, 0, MYSQL_TYPE_STRING, 0, 0, 0, SKIP_OPEN_TABLE}
};


/** For creating fields of information_schema.OPTIMIZER_TRACE */

ST_FIELD_INFO optimizer_trace_info[]=
        {
                /* name, length, type, value, maybe_null, old_name, open_method */
                {"QUERY", 65535, MYSQL_TYPE_STRING, 0, false, NULL, SKIP_OPEN_TABLE},
                {"TRACE", 65535, MYSQL_TYPE_STRING, 0, false, NULL, SKIP_OPEN_TABLE},
                {"MISSING_BYTES_BEYOND_MAX_MEM_SIZE", 20, MYSQL_TYPE_LONG,
                                                    0, false, NULL, SKIP_OPEN_TABLE},
                {"INSUFFICIENT_PRIVILEGES", 1, MYSQL_TYPE_TINY,
                                                    0, false, NULL, SKIP_OPEN_TABLE},
                {NULL, 0,  MYSQL_TYPE_STRING, 0, true, NULL, 0}
        };


/*
  Description of ST_FIELD_INFO in table.h

  Make sure that the order of schema_tables and enum_schema_tables are the same.

*/

ST_SCHEMA_TABLE schema_tables[]=
{
  {"CHARACTER_SETS", charsets_fields_info, -1, -1, 0, 0},
  {"CLIENT_STATISTICS", client_stats_fields_info, -1, -1, 0, 0},
  {"COLLATIONS", collation_fields_info, -1, -1, 0, 0},
  {"COLLATION_CHARACTER_SET_APPLICABILITY", coll_charset_app_fields_info, -1, -1, 0, 0},
  {"COLUMNS", columns_fields_info, 1, 2, 0,
   OPTIMIZE_I_S_TABLE|OPEN_VIEW_FULL},
  {"COLUMN_PRIVILEGES", column_privileges_fields_info, -1, -1, 0, 0},
  {"INDEX_STATISTICS", index_stats_fields_info, -1, -1, 0, 0},
  {"ENGINES", engines_fields_info, -1, -1, 0, 0},
#ifdef HAVE_EVENT_SCHEDULER
  {"EVENTS", events_fields_info, -1, -1, 0, 0},
#else // for alignment with enum_schema_tables
  {"EVENTS", events_fields_info, -1, -1, 0, 0},
#endif
  {"FILES", files_fields_info, -1, -1, 0, 0},
  {"GLOBAL_STATUS", variables_fields_info, 0, -1, 0, 0},
  {"GLOBAL_TEMPORARY_TABLES", temporary_table_fields_info, 2, 3, 0,
   OPEN_TABLE_ONLY|OPTIMIZE_I_S_TABLE},
  {"GLOBAL_VARIABLES", variables_fields_info, 0, -1, 0, 0},
  {"KEY_COLUMN_USAGE", key_column_usage_fields_info, 4, 5, 0,
   OPTIMIZE_I_S_TABLE|OPEN_TABLE_ONLY},
  {"OPEN_TABLES", open_tables_fields_info, -1, -1, 1, 0},
#ifdef OPTIMIZER_TRACE
  {"OPTIMIZER_TRACE", optimizer_trace_info, -1, -1, false, 0},
#else // for alignment with enum_schema_tables
  {"OPTIMIZER_TRACE", optimizer_trace_info, -1, -1, false, 0},
#endif
  {"PARAMETERS", parameters_fields_info, -1, -1, 0, 0},
  {"PARTITIONS", partitions_fields_info, 1, 2, 0,
   OPTIMIZE_I_S_TABLE|OPEN_TABLE_ONLY},
  {"PLUGINS", plugin_fields_info, -1, -1, 0, 0},
  {"PROCESSLIST", processlist_fields_info, -1, -1, 0, 0},
  {"PROFILING", query_profile_statistics_info, -1, -1, false, 0},
  {"REFERENTIAL_CONSTRAINTS", referential_constraints_fields_info,
   1, 9, 0, OPTIMIZE_I_S_TABLE|OPEN_TABLE_ONLY},
  {"ROUTINES", proc_fields_info, -1, -1, 0, 0},
  {"SCHEMATA", schema_fields_info, 1, -1, 0, 0},
  {"SCHEMA_PRIVILEGES", schema_privileges_fields_info, -1, -1, 0, 0},
  {"SESSION_STATUS", variables_fields_info, 0, -1, 0, 0},
  {"SESSION_VARIABLES", variables_fields_info, 0, -1, 0, 0},
  {"STATISTICS", stat_fields_info, 1, 2, 0,
   OPEN_TABLE_ONLY|OPTIMIZE_I_S_TABLE},
  {"STATUS", variables_fields_info, 0, -1, 1, 0},
  {"TABLES", tables_fields_info, 1, 2, 0,
   OPTIMIZE_I_S_TABLE},
  {"TABLESPACES", tablespaces_fields_info, -1, -1, 0, 0},
  {"TABLE_CONSTRAINTS", table_constraints_fields_info, 3, 4, 0,
   OPTIMIZE_I_S_TABLE|OPEN_TABLE_ONLY},
  {"TABLE_NAMES", table_names_fields_info, 1, 2, 1, 0},
  {"TABLE_PRIVILEGES", table_privileges_fields_info, -1, -1, 0, 0},
  {"TABLE_STATISTICS", table_stats_fields_info, -1, -1, 0, 0},
  {"TEMPORARY_TABLES", temporary_table_fields_info, 2, 3, 0,
   OPEN_TABLE_ONLY|OPTIMIZE_I_S_TABLE},
  {"THREAD_STATISTICS", thread_stats_fields_info, -1, -1, 0, 0},
  {"TRIGGERS", triggers_fields_info, 5, 6, 0,
   OPEN_TRIGGER_ONLY|OPTIMIZE_I_S_TABLE},
  {"USER_PRIVILEGES", user_privileges_fields_info, -1, -1, 0, 0},
  {"USER_STATISTICS", user_stats_fields_info, -1, -1, 0, 0},
  {"VARIABLES", variables_fields_info, 0, -1, 1, 0},
  {"VIEWS", view_fields_info, 1, 2, 0,
   OPEN_VIEW_ONLY|OPTIMIZE_I_S_TABLE},
  {0, 0, 0, 0, 0, 0}
};



