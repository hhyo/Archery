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
   Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA */

/* Some general useful functions */

#include "my_global.h"                          /* NO_EMBEDDED_ACCESS_CHECKS */
#include "sql_priv.h"
#include "unireg.h"                    // REQUIRED: for other includes
#include "table.h"
#include "key.h"                                // find_ref_key
#include "sql_table.h"                          // build_table_filename,
                                                // primary_key_name
#include "sql_trigger.h"
#include "sql_parse.h"                          // free_items
#include "strfunc.h"                            // unhex_type2
#include "sql_partition.h"       // mysql_unpack_partition,
                                 // fix_partition_func, partition_info
#include "sql_acl.h"             // *_ACL, acl_getroot_no_password
#include "sql_base.h"            // release_table_share
#include "sql_derived.h"
#include <m_ctype.h>
#include "my_md5.h"
#include "my_bit.h"
#include "sql_view.h"

/* INFORMATION_SCHEMA name */
LEX_STRING INFORMATION_SCHEMA_NAME= {C_STRING_WITH_LEN("information_schema")};

/* PERFORMANCE_SCHEMA name */
LEX_STRING PERFORMANCE_SCHEMA_DB_NAME= {C_STRING_WITH_LEN("performance_schema")};

/* MYSQL_SCHEMA name */
LEX_STRING MYSQL_SCHEMA_NAME= {C_STRING_WITH_LEN("mysql")};

/* GENERAL_LOG name */
LEX_STRING GENERAL_LOG_NAME= {C_STRING_WITH_LEN("general_log")};

/* SLOW_LOG name */
LEX_STRING SLOW_LOG_NAME= {C_STRING_WITH_LEN("slow_log")};

/* RLI_INFO name */
LEX_STRING RLI_INFO_NAME= {C_STRING_WITH_LEN("slave_relay_log_info")};

/* MI_INFO name */
LEX_STRING MI_INFO_NAME= {C_STRING_WITH_LEN("slave_master_info")};

/* WORKER_INFO name */
LEX_STRING WORKER_INFO_NAME= {C_STRING_WITH_LEN("slave_worker_info")};

	/* Functions defined in this file */

inline bool is_system_table_name(const char *name, uint length);


/**************************************************************************
  Object_creation_ctx implementation.
**************************************************************************/

Object_creation_ctx *Object_creation_ctx::set_n_backup(THD *thd)
{
  Object_creation_ctx *backup_ctx;
  DBUG_ENTER("Object_creation_ctx::set_n_backup");

  backup_ctx= create_backup_ctx(thd);
  change_env(thd);

  DBUG_RETURN(backup_ctx);
}

void Object_creation_ctx::restore_env(THD *thd, Object_creation_ctx *backup_ctx)
{
  if (!backup_ctx)
    return;

  backup_ctx->change_env(thd);

  delete backup_ctx;
}

/**************************************************************************
  Default_object_creation_ctx implementation.
**************************************************************************/

Default_object_creation_ctx::Default_object_creation_ctx(THD *thd)
  : m_client_cs(thd->variables.character_set_client),
    m_connection_cl(thd->variables.collation_connection)
{ }

Default_object_creation_ctx::Default_object_creation_ctx(
  const CHARSET_INFO *client_cs, const CHARSET_INFO *connection_cl)
  : m_client_cs(client_cs),
    m_connection_cl(connection_cl)
{ }

Object_creation_ctx *
Default_object_creation_ctx::create_backup_ctx(THD *thd) const
{
  return new Default_object_creation_ctx(thd);
}

void Default_object_creation_ctx::change_env(THD *thd) const
{
  thd->variables.character_set_client= m_client_cs;
  thd->variables.collation_connection= m_connection_cl;

  thd->update_charset();
}

/**************************************************************************
  View_creation_ctx implementation.
**************************************************************************/

View_creation_ctx *View_creation_ctx::create(THD *thd)
{
  View_creation_ctx *ctx= new (thd->mem_root) View_creation_ctx(thd);

  return ctx;
}

/*************************************************************************/

View_creation_ctx * View_creation_ctx::create(THD *thd,
                                              TABLE_LIST *view)
{
  View_creation_ctx *ctx= new (thd->mem_root) View_creation_ctx(thd);

  /* Throw a warning if there is NULL cs name. */

  if (!view->view_client_cs_name.str ||
      !view->view_connection_cl_name.str)
  {
    push_warning_printf(thd, Sql_condition::WARN_LEVEL_NOTE,
                        ER_VIEW_NO_CREATION_CTX,
                        ER(ER_VIEW_NO_CREATION_CTX),
                        (const char *) view->db,
                        (const char *) view->table_name);

    ctx->m_client_cs= system_charset_info;
    ctx->m_connection_cl= system_charset_info;

    return ctx;
  }

  /* Resolve cs names. Throw a warning if there is unknown cs name. */

  bool invalid_creation_ctx;

  invalid_creation_ctx= resolve_charset(view->view_client_cs_name.str,
                                        system_charset_info,
                                        &ctx->m_client_cs);

  invalid_creation_ctx= resolve_collation(view->view_connection_cl_name.str,
                                          system_charset_info,
                                          &ctx->m_connection_cl) ||
                        invalid_creation_ctx;

  if (invalid_creation_ctx)
  {
    sql_print_warning("View '%s'.'%s': there is unknown charset/collation "
                      "names (client: '%s'; connection: '%s').",
                      (const char *) view->db,
                      (const char *) view->table_name,
                      (const char *) view->view_client_cs_name.str,
                      (const char *) view->view_connection_cl_name.str);

    push_warning_printf(thd, Sql_condition::WARN_LEVEL_NOTE,
                        ER_VIEW_INVALID_CREATION_CTX,
                        ER(ER_VIEW_INVALID_CREATION_CTX),
                        (const char *) view->db,
                        (const char *) view->table_name);
  }

  return ctx;
}

/*************************************************************************/

/*
  Returns pointer to '.frm' extension of the file name.

  SYNOPSIS
    fn_rext()
    name       file name

  DESCRIPTION
    Checks file name part starting with the rightmost '.' character,
    and returns it if it is equal to '.frm'. 

  TODO
    It is a good idea to get rid of this function modifying the code
    to garantee that the functions presently calling fn_rext() always
    get arguments in the same format: either with '.frm' or without '.frm'.

  RETURN VALUES
    Pointer to the '.frm' extension. If there is no extension,
    or extension is not '.frm', pointer at the end of file name.
*/

char *fn_rext(char *name)
{
  char *res= strrchr(name, '.');
  if (res && !strcmp(res, reg_ext))
    return res;
  return name + strlen(name);
}

TABLE_CATEGORY get_table_category(const LEX_STRING *db, const LEX_STRING *name)
{
  DBUG_ASSERT(db != NULL);
  DBUG_ASSERT(name != NULL);

  if (is_infoschema_db(db->str, db->length))
    return TABLE_CATEGORY_INFORMATION;

  if ((db->length == PERFORMANCE_SCHEMA_DB_NAME.length) &&
      (my_strcasecmp(system_charset_info,
                     PERFORMANCE_SCHEMA_DB_NAME.str,
                     db->str) == 0))
    return TABLE_CATEGORY_PERFORMANCE;

  if ((db->length == MYSQL_SCHEMA_NAME.length) &&
      (my_strcasecmp(system_charset_info,
                     MYSQL_SCHEMA_NAME.str,
                     db->str) == 0))
  {
    if (is_system_table_name(name->str, name->length))
      return TABLE_CATEGORY_SYSTEM;

    if ((name->length == GENERAL_LOG_NAME.length) &&
        (my_strcasecmp(system_charset_info,
                       GENERAL_LOG_NAME.str,
                       name->str) == 0))
      return TABLE_CATEGORY_LOG;

    if ((name->length == SLOW_LOG_NAME.length) &&
        (my_strcasecmp(system_charset_info,
                       SLOW_LOG_NAME.str,
                       name->str) == 0))
      return TABLE_CATEGORY_LOG;

    if ((name->length == RLI_INFO_NAME.length) &&
        (my_strcasecmp(system_charset_info,
                      RLI_INFO_NAME.str,
                      name->str) == 0))
      return TABLE_CATEGORY_RPL_INFO;

    if ((name->length == MI_INFO_NAME.length) &&
        (my_strcasecmp(system_charset_info,
                      MI_INFO_NAME.str,
                      name->str) == 0))
      return TABLE_CATEGORY_RPL_INFO;

    if ((name->length == WORKER_INFO_NAME.length) &&
        (my_strcasecmp(system_charset_info,
                      WORKER_INFO_NAME.str,
                      name->str) == 0))
      return TABLE_CATEGORY_RPL_INFO;
  }

  return TABLE_CATEGORY_USER;
}


/**
  Return TRUE if a table name matches one of the system table names.
  Currently these are:

  help_category, help_keyword, help_relation, help_topic,
  proc, event
  time_zone, time_zone_leap_second, time_zone_name, time_zone_transition,
  time_zone_transition_type

  This function trades accuracy for speed, so may return false
  positives. Presumably mysql.* database is for internal purposes only
  and should not contain user tables.
*/

inline bool is_system_table_name(const char *name, uint length)
{
  CHARSET_INFO *ci= system_charset_info;

  return (
           /* mysql.proc table */
           (length == 4 &&
             my_tolower(ci, name[0]) == 'p' && 
             my_tolower(ci, name[1]) == 'r' &&
             my_tolower(ci, name[2]) == 'o' &&
             my_tolower(ci, name[3]) == 'c') ||

           (length > 4 &&
             (
               /* one of mysql.help* tables */
               (my_tolower(ci, name[0]) == 'h' &&
                 my_tolower(ci, name[1]) == 'e' &&
                 my_tolower(ci, name[2]) == 'l' &&
                 my_tolower(ci, name[3]) == 'p') ||

               /* one of mysql.time_zone* tables */
               (my_tolower(ci, name[0]) == 't' &&
                 my_tolower(ci, name[1]) == 'i' &&
                 my_tolower(ci, name[2]) == 'm' &&
                 my_tolower(ci, name[3]) == 'e') ||

               /* mysql.event table */
               (my_tolower(ci, name[0]) == 'e' &&
                 my_tolower(ci, name[1]) == 'v' &&
                 my_tolower(ci, name[2]) == 'e' &&
                 my_tolower(ci, name[3]) == 'n' &&
                 my_tolower(ci, name[4]) == 't')
             )
           )
         );
}
	/* Add a new form to a form file */

ulong make_new_entry(File file, uchar *fileinfo, TYPELIB *formnames,
		     const char *newname)
{
  uint i,bufflength,maxlength,n_length,length,names;
  ulong endpos,newpos;
  uchar buff[IO_SIZE];
  uchar *pos;
  DBUG_ENTER("make_new_entry");

  length=(uint) strlen(newname)+1;
  n_length=uint2korr(fileinfo+4);
  maxlength=uint2korr(fileinfo+6);
  names=uint2korr(fileinfo+8);
  newpos=uint4korr(fileinfo+10);

  if (64+length+n_length+(names+1)*4 > maxlength)
  {						/* Expand file */
    newpos+=IO_SIZE;
    int4store(fileinfo+10,newpos);
    /* Copy from file-end */
    endpos= (ulong) mysql_file_seek(file, 0L, MY_SEEK_END, MYF(0));
    bufflength= (uint) (endpos & (IO_SIZE-1));	/* IO_SIZE is a power of 2 */

    while (endpos > maxlength)
    {
      mysql_file_seek(file, (ulong) (endpos-bufflength), MY_SEEK_SET, MYF(0));
      if (mysql_file_read(file, buff, bufflength, MYF(MY_NABP+MY_WME)))
	DBUG_RETURN(0L);
      mysql_file_seek(file, (ulong) (endpos-bufflength+IO_SIZE), MY_SEEK_SET,
                      MYF(0));
      if ((mysql_file_write(file, buff, bufflength, MYF(MY_NABP+MY_WME))))
	DBUG_RETURN(0);
      endpos-=bufflength; bufflength=IO_SIZE;
    }
    memset(buff, 0, IO_SIZE);			/* Null new block */
    mysql_file_seek(file, (ulong) maxlength, MY_SEEK_SET, MYF(0));
    if (mysql_file_write(file, buff, bufflength, MYF(MY_NABP+MY_WME)))
	DBUG_RETURN(0L);
    maxlength+=IO_SIZE;				/* Fix old ref */
    int2store(fileinfo+6,maxlength);
    for (i=names, pos= (uchar*) *formnames->type_names+n_length-1; i-- ;
	 pos+=4)
    {
      endpos=uint4korr(pos)+IO_SIZE;
      int4store(pos,endpos);
    }
  }

  if (n_length == 1 )
  {						/* First name */
    length++;
    (void) strxmov((char*) buff,"/",newname,"/",NullS);
  }
  else
    (void) strxmov((char*) buff,newname,"/",NullS); /* purecov: inspected */
  mysql_file_seek(file, 63L+(ulong) n_length, MY_SEEK_SET, MYF(0));
  if (mysql_file_write(file, buff, (size_t) length+1, MYF(MY_NABP+MY_WME)) ||
      (names && mysql_file_write(file,
                                 (uchar*) (*formnames->type_names+n_length-1),
                                 names*4, MYF(MY_NABP+MY_WME))) ||
      mysql_file_write(file, fileinfo+10, 4, MYF(MY_NABP+MY_WME)))
    DBUG_RETURN(0L); /* purecov: inspected */

  int2store(fileinfo+8,names+1);
  int2store(fileinfo+4,n_length+length);
  (void) mysql_file_chsize(file, newpos, 0, MYF(MY_WME));/* Append file with '\0' */
  DBUG_RETURN(newpos);
} /* make_new_entry */


TYPELIB *typelib(MEM_ROOT *mem_root, List<String> &strings)
{
  TYPELIB *result= (TYPELIB*) alloc_root(mem_root, sizeof(TYPELIB));
  if (!result)
    return 0;
  result->count=strings.elements;
  result->name="";
  uint nbytes= (sizeof(char*) + sizeof(uint)) * (result->count + 1);
  if (!(result->type_names= (const char**) alloc_root(mem_root, nbytes)))
    return 0;
  result->type_lengths= (uint*) (result->type_names + result->count + 1);
  List_iterator<String> it(strings);
  String *tmp;
  for (uint i=0; (tmp=it++) ; i++)
  {
    result->type_names[i]= tmp->ptr();
    result->type_lengths[i]= tmp->length();
  }
  result->type_names[result->count]= 0;		// End marker
  result->type_lengths[result->count]= 0;
  return result;
}


	/* Check that the integer is in the internal */

int set_zone(register int nr, int min_zone, int max_zone)
{
  if (nr<=min_zone)
    return (min_zone);
  if (nr>=max_zone)
    return (max_zone);
  return (nr);
} /* set_zone */

	/* Adjust number to next larger disk buffer */

ulong next_io_size(register ulong pos)
{
  reg2 ulong offset;
  if ((offset= pos & (IO_SIZE-1)))
    return pos-offset+IO_SIZE;
  return pos;
} /* next_io_size */


/*
  Store an SQL quoted string.

  SYNOPSIS  
    append_unescaped()
    res		result String
    pos		string to be quoted
    length	it's length

  NOTE
    This function works correctly with utf8 or single-byte charset strings.
    May fail with some multibyte charsets though.
*/

void append_unescaped(String *res, const char *pos, uint length)
{
  const char *end= pos+length;
  res->append('\'');

  for (; pos != end ; pos++)
  {
#if defined(USE_MB) && MYSQL_VERSION_ID < 40100
    uint mblen;
    if (use_mb(default_charset_info) &&
        (mblen= my_ismbchar(default_charset_info, pos, end)))
    {
      res->append(pos, mblen);
      pos+= mblen;
      continue;
    }
#endif

    switch (*pos) {
    case 0:				/* Must be escaped for 'mysql' */
      res->append('\\');
      res->append('0');
      break;
    case '\n':				/* Must be escaped for logs */
      res->append('\\');
      res->append('n');
      break;
    case '\r':
      res->append('\\');		/* This gives better readability */
      res->append('r');
      break;
    case '\\':
      res->append('\\');		/* Because of the sql syntax */
      res->append('\\');
      break;
    case '\'':
      res->append('\'');		/* Because of the sql syntax */
      res->append('\'');
      break;
    default:
      res->append(*pos);
      break;
    }
  }
  res->append('\'');
}

/**
  Check if database name is valid

  @param org_name             Name of database and length
  @param preserve_lettercase  Preserve lettercase if true

  @note If lower_case_table_names is true and preserve_lettercase
  is false then database is converted to lower case

  @retval  IDENT_NAME_OK        Identifier name is Ok (Success)
  @retval  IDENT_NAME_WRONG     Identifier name is Wrong (ER_WRONG_TABLE_NAME)
  @retval  IDENT_NAME_TOO_LONG  Identifier name is too long if it is greater
                                than 64 characters (ER_TOO_LONG_IDENT)

  @note In case of IDENT_NAME_WRONG and IDENT_NAME_TOO_LONG, this
  function reports an error (my_error)
*/

enum_ident_name_check check_and_convert_db_name(LEX_STRING *org_name,
                                                bool preserve_lettercase)
{
  char *name= org_name->str;
  uint name_length= org_name->length;
  bool check_for_path_chars;
  enum_ident_name_check ident_check_status;

  if (!name_length || name_length > NAME_LEN)
  {
    my_error(ER_WRONG_DB_NAME, MYF(0), org_name->str);
    return IDENT_NAME_WRONG;
  }

  if ((check_for_path_chars= check_mysql50_prefix(name)))
  {
    name+= MYSQL50_TABLE_NAME_PREFIX_LENGTH;
    name_length-= MYSQL50_TABLE_NAME_PREFIX_LENGTH;
  }

  if (!preserve_lettercase && lower_case_table_names && name != any_db)
    my_casedn_str(files_charset_info, name);

  ident_check_status= check_table_name(name, name_length, check_for_path_chars);
  if (ident_check_status == IDENT_NAME_WRONG)
    my_error(ER_WRONG_DB_NAME, MYF(0), org_name->str);
  else if (ident_check_status == IDENT_NAME_TOO_LONG)
    my_error(ER_TOO_LONG_IDENT, MYF(0), org_name->str);
  return ident_check_status;
}


/**
  Function to check if table name is valid or not. If it is invalid,
  return appropriate error in each case to the caller.

  @param name                  Table name
  @param length                Length of table name
  @param check_for_path_chars  Check if the table name contains path chars

  @retval  IDENT_NAME_OK        Identifier name is Ok (Success)
  @retval  IDENT_NAME_WRONG     Identifier name is Wrong (ER_WRONG_TABLE_NAME)
  @retval  IDENT_NAME_TOO_LONG  Identifier name is too long if it is greater
                                than 64 characters (ER_TOO_LONG_IDENT)

  @note Reporting error to the user is the responsiblity of the caller.
*/

enum_ident_name_check check_table_name(const char *name, size_t length,
                                       bool check_for_path_chars)
{
  // name length in symbols
  size_t name_length= 0;
  const char *end= name+length;
  if (!length || length > NAME_LEN)
    return IDENT_NAME_WRONG;
#if defined(USE_MB) && defined(USE_MB_IDENT)
  bool last_char_is_space= FALSE;
#else
  if (name[length-1]==' ')
    return IDENT_NAME_WRONG;
#endif

  while (name != end)
  {
#if defined(USE_MB) && defined(USE_MB_IDENT)
    last_char_is_space= my_isspace(system_charset_info, *name);
    if (use_mb(system_charset_info))
    {
      int len=my_ismbchar(system_charset_info, name, end);
      if (len)
      {
        name += len;
        name_length++;
        continue;
      }
    }
#endif
    if (check_for_path_chars &&
        (*name == '/' || *name == '\\' || *name == '~' || *name == FN_EXTCHAR))
      return IDENT_NAME_WRONG;
    name++;
    name_length++;
  }
#if defined(USE_MB) && defined(USE_MB_IDENT)
  if (last_char_is_space)
   return IDENT_NAME_WRONG;
  else if (name_length > NAME_CHAR_LEN)
   return IDENT_NAME_TOO_LONG;
#endif
  return IDENT_NAME_OK;
}


bool check_column_name(const char *name)
{
  // name length in symbols
  size_t name_length= 0;
  bool last_char_is_space= TRUE;

  while (*name)
  {
#if defined(USE_MB) && defined(USE_MB_IDENT)
    last_char_is_space= my_isspace(system_charset_info, *name);
    if (use_mb(system_charset_info))
    {
      int len=my_ismbchar(system_charset_info, name, 
                          name+system_charset_info->mbmaxlen);
      if (len)
      {
        name += len;
        name_length++;
        continue;
      }
    }
#else
    last_char_is_space= *name==' ';
#endif
    if (*name == NAMES_SEP_CHAR)
      return 1;
    name++;
    name_length++;
  }
  /* Error if empty or too long column name */
  return last_char_is_space || (name_length > NAME_CHAR_LEN);
}


/**
  Create a TABLE_LIST object representing a nested join

  @param allocator  Mem root allocator that object is created from.
  @param alias      Name of nested join object
  @param embedding  Pointer to embedding join nest (or NULL if top-most)
  @param belongs_to List of tables this nest belongs to (never NULL).
  @param select     The query block that this join nest belongs within.

  @returns Pointer to created join nest object, or NULL if error.
*/

TABLE_LIST *TABLE_LIST::new_nested_join(MEM_ROOT *allocator,
                            const char *alias,
                            TABLE_LIST *embedding,
                            List<TABLE_LIST> *belongs_to,
                            class st_select_lex *select)
{
  DBUG_ASSERT(belongs_to && select);

  TABLE_LIST *const join_nest=
    (TABLE_LIST *) alloc_root(allocator, ALIGN_SIZE(sizeof(TABLE_LIST))+
                                                    sizeof(NESTED_JOIN));
  if (join_nest == NULL)
    return NULL;

  memset(join_nest, 0, ALIGN_SIZE(sizeof(TABLE_LIST)) + sizeof(NESTED_JOIN));
  join_nest->nested_join=
    (NESTED_JOIN *) ((uchar *)join_nest + ALIGN_SIZE(sizeof(TABLE_LIST)));

  join_nest->db= (char *)"";
  join_nest->db_length= 0;
  join_nest->table_name= (char *)"";
  join_nest->table_name_length= 0;
  join_nest->alias= (char *)alias;
  
  join_nest->embedding= embedding;
  join_nest->join_list= belongs_to;
  join_nest->select_lex= select;

  join_nest->nested_join->join_list.empty();

  return join_nest;
}

/*
  setup fields of placeholder of merged VIEW

  SYNOPSIS
    TABLE_LIST::setup_underlying()
    thd		    - thread handler

  DESCRIPTION
    It is:
    - preparing translation table for view columns
    If there are underlying view(s) procedure first will be called for them.

  RETURN
    FALSE - OK
    TRUE  - error
*/

bool TABLE_LIST::setup_underlying(THD *thd)
{
  DBUG_ENTER("TABLE_LIST::setup_underlying");

  if (!field_translation && merge_underlying_list)
  {
    Field_translator *transl;
    SELECT_LEX *select= &view->select_lex;
    Item *item;
    TABLE_LIST *tbl;
    List_iterator_fast<Item> it(select->item_list);
    uint field_count= 0;

    if (check_stack_overrun(thd, STACK_MIN_SIZE, (uchar*) &field_count))
    {
      DBUG_RETURN(TRUE);
    }

    for (tbl= merge_underlying_list; tbl; tbl= tbl->next_local)
    {
      if (tbl->merge_underlying_list &&
          tbl->setup_underlying(thd))
      {
        DBUG_RETURN(TRUE);
      }
    }

    /* Create view fields translation table */

    if (!(transl=
          (Field_translator*)(thd->stmt_arena->
                              alloc(select->item_list.elements *
                                    sizeof(Field_translator)))))
    {
      DBUG_RETURN(TRUE);
    }

    while ((item= it++))
    {
      transl[field_count].name= item->item_name.ptr();
      transl[field_count++].item= item;
    }
    field_translation= transl;
    field_translation_end= transl + field_count;
    /* TODO: use hash for big number of fields */

    /* full text function moving to current select */
    if (view->select_lex.ftfunc_list->elements)
    {
      Item_func_match *ifm;
      SELECT_LEX *current_select= thd->lex->current_select;
      List_iterator_fast<Item_func_match>
        li(*(view->select_lex.ftfunc_list));
      while ((ifm= li++))
        current_select->ftfunc_list->push_front(ifm);
    }
  }
  DBUG_RETURN(FALSE);
}

/**
  Hide errors which show view underlying table information. 
  There are currently two mechanisms at work that handle errors for views,
  this one and a more general mechanism based on an Internal_error_handler,
  see Show_create_error_handler. The latter handles errors encountered during
  execution of SHOW CREATE VIEW, while the machanism using this method is
  handles SELECT from views. The two methods should not clash.

  @param[in,out]  thd     thread handler

  @pre This method can be called only if there is an error.
*/

void TABLE_LIST::hide_view_error(THD *thd)
{
  if (thd->killed || thd->get_internal_handler())
    return;
  /* Hide "Unknown column" or "Unknown function" error */
  DBUG_ASSERT(thd->is_error());

  switch (thd->get_stmt_da()->sql_errno()) {
    case ER_BAD_FIELD_ERROR:
    case ER_SP_DOES_NOT_EXIST:
    case ER_FUNC_INEXISTENT_NAME_COLLISION:
    case ER_PROCACCESS_DENIED_ERROR:
    case ER_COLUMNACCESS_DENIED_ERROR:
    case ER_TABLEACCESS_DENIED_ERROR:
    case ER_TABLE_NOT_LOCKED:
    case ER_NO_SUCH_TABLE:
    {
      TABLE_LIST *top= top_table();
      thd->clear_error();
      my_error(ER_VIEW_INVALID, MYF(0),
               top->view_db.str, top->view_name.str);
      break;
    }

    case ER_NO_DEFAULT_FOR_FIELD:
    {
      TABLE_LIST *top= top_table();
      thd->clear_error();
      // TODO: make correct error message
      my_error(ER_NO_DEFAULT_FOR_VIEW_FIELD, MYF(0),
               top->view_db.str, top->view_name.str);
      break;
    }
  }
}




/*
  Test if this is a leaf with respect to name resolution.

  SYNOPSIS
    TABLE_LIST::is_leaf_for_name_resolution()

  DESCRIPTION
    A table reference is a leaf with respect to name resolution if
    it is either a leaf node in a nested join tree (table, view,
    schema table, subquery), or an inner node that represents a
    NATURAL/USING join, or a nested join with materialized join
    columns.

  RETURN
    TRUE if a leaf, FALSE otherwise.
*/
bool TABLE_LIST::is_leaf_for_name_resolution()
{
  return (view || is_natural_join || is_join_columns_complete ||
          !nested_join);
}


/*
  Retrieve the first (left-most) leaf in a nested join tree with
  respect to name resolution.

  SYNOPSIS
    TABLE_LIST::first_leaf_for_name_resolution()

  DESCRIPTION
    Given that 'this' is a nested table reference, recursively walk
    down the left-most children of 'this' until we reach a leaf
    table reference with respect to name resolution.

  IMPLEMENTATION
    The left-most child of a nested table reference is the last element
    in the list of children because the children are inserted in
    reverse order.

  RETURN
    If 'this' is a nested table reference - the left-most child of
      the tree rooted in 'this',
    else return 'this'
*/

TABLE_LIST *TABLE_LIST::first_leaf_for_name_resolution()
{
  TABLE_LIST *cur_table_ref;
  NESTED_JOIN *cur_nested_join;
  LINT_INIT(cur_table_ref);

  if (is_leaf_for_name_resolution())
    return this;
  DBUG_ASSERT(nested_join);

  for (cur_nested_join= nested_join;
       cur_nested_join;
       cur_nested_join= cur_table_ref->nested_join)
  {
    List_iterator_fast<TABLE_LIST> it(cur_nested_join->join_list);
    cur_table_ref= it++;
    /*
      If the current nested join is a RIGHT JOIN, the operands in
      'join_list' are in reverse order, thus the first operand is
      already at the front of the list. Otherwise the first operand
      is in the end of the list of join operands.
    */
    if (!(cur_table_ref->outer_join & JOIN_TYPE_RIGHT))
    {
      TABLE_LIST *next;
      while ((next= it++))
        cur_table_ref= next;
    }
    if (cur_table_ref->is_leaf_for_name_resolution())
      break;
  }
  return cur_table_ref;
}


/*
  Retrieve the last (right-most) leaf in a nested join tree with
  respect to name resolution.

  SYNOPSIS
    TABLE_LIST::last_leaf_for_name_resolution()

  DESCRIPTION
    Given that 'this' is a nested table reference, recursively walk
    down the right-most children of 'this' until we reach a leaf
    table reference with respect to name resolution.

  IMPLEMENTATION
    The right-most child of a nested table reference is the first
    element in the list of children because the children are inserted
    in reverse order.

  RETURN
    - If 'this' is a nested table reference - the right-most child of
      the tree rooted in 'this',
    - else - 'this'
*/

TABLE_LIST *TABLE_LIST::last_leaf_for_name_resolution()
{
  TABLE_LIST *cur_table_ref= this;
  NESTED_JOIN *cur_nested_join;

  if (is_leaf_for_name_resolution())
    return this;
  DBUG_ASSERT(nested_join);

  for (cur_nested_join= nested_join;
       cur_nested_join;
       cur_nested_join= cur_table_ref->nested_join)
  {
    cur_table_ref= cur_nested_join->join_list.head();
    /*
      If the current nested is a RIGHT JOIN, the operands in
      'join_list' are in reverse order, thus the last operand is in the
      end of the list.
    */
    if ((cur_table_ref->outer_join & JOIN_TYPE_RIGHT))
    {
      List_iterator_fast<TABLE_LIST> it(cur_nested_join->join_list);
      TABLE_LIST *next;
      cur_table_ref= it++;
      while ((next= it++))
        cur_table_ref= next;
    }
    if (cur_table_ref->is_leaf_for_name_resolution())
      break;
  }
  return cur_table_ref;
}


/*
  Register access mode which we need for underlying tables

  SYNOPSIS
    register_want_access()
    want_access          Acess which we require
*/

void TABLE_LIST::register_want_access(ulong want_access)
{
  /* Remove SHOW_VIEW_ACL, because it will be checked during making view */
  want_access&= ~SHOW_VIEW_ACL;
  for (TABLE_LIST *tbl= merge_underlying_list; tbl; tbl= tbl->next_local)
    tbl->register_want_access(want_access);
}



/*
  Prepare security context and load underlying tables priveleges for view

  SYNOPSIS
    TABLE_LIST::prepare_security()
    thd                  [in] thread handler

  RETURN
    FALSE  OK
    TRUE   Error
*/

bool TABLE_LIST::prepare_security(THD *thd)
{
  DBUG_ENTER("TABLE_LIST::prepare_security");
  DBUG_RETURN(FALSE);
}

/*
  Return subselect that contains the FROM list this table is taken from

  SYNOPSIS
    TABLE_LIST::containing_subselect()
 
  RETURN
    Subselect item for the subquery that contains the FROM list
    this table is taken from if there is any
    0 - otherwise

*/

Item_subselect *TABLE_LIST::containing_subselect()
{    
  return (select_lex ? select_lex->master_unit()->item : 0);
}

uint TABLE_LIST::query_block_id() const
{
  return derived ? derived->first_select()->select_number : 0;
}




///  @returns true if materializable table contains one or zero rows
bool TABLE_LIST::materializable_is_const() const
{
  DBUG_ASSERT(uses_materialization());
  return get_unit()->get_result()->estimated_rowcount <= 1;
}



/**
  @brief
  Return unit of this derived table/view

  @return reference to a unit  if it's a derived table/view.
  @return 0                    when it's not a derived table/view.
*/

st_select_lex_unit *TABLE_LIST::get_unit() const
{
  return (view ? &view->unit : derived);
}


/**
  Test if the order list consists of simple field expressions

  @param order                Linked list of ORDER BY arguments

  @return TRUE if @a order is empty or consist of simple field expressions
*/

bool is_simple_order(ORDER *order)
{
  for (ORDER *ord= order; ord; ord= ord->next)
  {
    if (ord->item[0]->real_item()->type() != Item::FIELD_ITEM)
      return FALSE;
  }
  return TRUE;
}


/*
  SYNOPSIS
    mem_alloc_error()
    size                Size of memory attempted to allocate
    None

  RETURN VALUES
    None

  DESCRIPTION
    A routine to use for all the many places in the code where memory
    allocation error can happen, a tremendous amount of them, needs
    simple routine that signals this error.
*/

void mem_alloc_error(size_t size)
{
    my_error(ER_OUTOFMEMORY, MYF(ME_FATALERROR),
             static_cast<int>(size));
}
