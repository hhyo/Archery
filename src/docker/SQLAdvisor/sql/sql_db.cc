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


/* create and drop of databases */

#include "my_global.h"                          /* NO_EMBEDDED_ACCESS_CHECKS */
#include "sql_priv.h"
#include "unireg.h"
#include "sql_db.h"
#include "sql_table.h"                   // build_table_filename,
                                         // filename_to_tablename
#include "sql_rename.h"                  // mysql_rename_tables
#include "sql_acl.h"                     // SELECT_ACL, DB_ACLS,
                                         // acl_get, check_grant_db
#include "sql_base.h"                    // lock_table_names, tdc_remove_table
#include "sql_handler.h"                 // mysql_ha_rm_tables
#include <mysys_err.h>
#include "sp.h"
#include <my_dir.h>
#include <m_ctype.h>
#include "log.h"
#ifdef __WIN__
#include <direct.h>
#endif

#define MAX_DROP_TABLE_Q_LEN      1024


/* Database options hash */
static HASH dboptions;
static my_bool dboptions_init= 0;
static mysql_rwlock_t LOCK_dboptions;

/* Structure for database options */
typedef struct my_dbopt_st
{
  char *name;			/* Database name                  */
  uint name_length;		/* Database length name           */
  const CHARSET_INFO *charset;	/* Database default character set */
} my_dbopt_t;


/*
  Function we use in the creation of our hash to get key.
*/

extern "C" uchar* dboptions_get_key(my_dbopt_t *opt, size_t *length,
                                    my_bool not_used);

uchar* dboptions_get_key(my_dbopt_t *opt, size_t *length,
                         my_bool not_used __attribute__((unused)))
{
  *length= opt->name_length;
  return (uchar*) opt->name;
}



/*
  Function to free dboptions hash element
*/

extern "C" void free_dbopt(void *dbopt);

void free_dbopt(void *dbopt)
{
  my_free(dbopt);
}

#ifdef HAVE_PSI_INTERFACE
static PSI_rwlock_key key_rwlock_LOCK_dboptions;

static PSI_rwlock_info all_database_names_rwlocks[]=
{
  { &key_rwlock_LOCK_dboptions, "LOCK_dboptions", PSI_FLAG_GLOBAL}
};

static void init_database_names_psi_keys(void)
{
  const char* category= "sql";
  int count;

  count= array_elements(all_database_names_rwlocks);
  mysql_rwlock_register(category, all_database_names_rwlocks, count);
}
#endif

/**
  Initialize database option cache.

  @note Must be called before any other database function is called.

  @retval  0	ok
  @retval  1	Fatal error
*/

bool my_dboptions_cache_init(void)
{
#ifdef HAVE_PSI_INTERFACE
  init_database_names_psi_keys();
#endif

  bool error= 0;
  mysql_rwlock_init(key_rwlock_LOCK_dboptions, &LOCK_dboptions);
  if (!dboptions_init)
  {
    dboptions_init= 1;
    error= my_hash_init(&dboptions, lower_case_table_names ?
                        &my_charset_bin : system_charset_info,
                        32, 0, 0, (my_hash_get_key) dboptions_get_key,
                        free_dbopt,0);
  }
  return error;
}



/**
  Free database option hash and locked databases hash.
*/

void my_dboptions_cache_free(void)
{
  if (dboptions_init)
  {
    dboptions_init= 0;
    my_hash_free(&dboptions);
    mysql_rwlock_destroy(&LOCK_dboptions);
  }
}


/**
  Cleanup cached options.
*/

void my_dbopt_cleanup(void)
{
  mysql_rwlock_wrlock(&LOCK_dboptions);
  my_hash_free(&dboptions);
  my_hash_init(&dboptions, lower_case_table_names ? 
               &my_charset_bin : system_charset_info,
               32, 0, 0, (my_hash_get_key) dboptions_get_key,
               free_dbopt,0);
  mysql_rwlock_unlock(&LOCK_dboptions);
}


/*
  Find database options in the hash.
  
  DESCRIPTION
    Search a database options in the hash, usings its path.
    Fills "create" on success.
  
  RETURN VALUES
    0 on success.
    1 on error.
*/

static my_bool get_dbopt(const char *dbname, HA_CREATE_INFO *create)
{
  my_dbopt_t *opt;
  uint length;
  my_bool error= 1;
  
  length= (uint) strlen(dbname);
  
  mysql_rwlock_rdlock(&LOCK_dboptions);
  if ((opt= (my_dbopt_t*) my_hash_search(&dboptions, (uchar*) dbname, length)))
  {
    create->default_table_charset= opt->charset;
    error= 0;
  }
  mysql_rwlock_unlock(&LOCK_dboptions);
  return error;
}


/*
  Writes database options into the hash.
  
  DESCRIPTION
    Inserts database options into the hash, or updates
    options if they are already in the hash.
  
  RETURN VALUES
    0 on success.
    1 on error.
*/

static my_bool put_dbopt(const char *dbname, HA_CREATE_INFO *create)
{
  my_dbopt_t *opt;
  uint length;
  my_bool error= 0;
  DBUG_ENTER("put_dbopt");

  length= (uint) strlen(dbname);
  
  mysql_rwlock_wrlock(&LOCK_dboptions);
  if (!(opt= (my_dbopt_t*) my_hash_search(&dboptions, (uchar*) dbname,
                                          length)))
  { 
    /* Options are not in the hash, insert them */
    char *tmp_name;
    if (!my_multi_malloc(MYF(MY_WME | MY_ZEROFILL),
                         &opt, (uint) sizeof(*opt), &tmp_name, (uint) length+1,
                         NullS))
    {
      error= 1;
      goto end;
    }
    
    opt->name= tmp_name;
    strmov(opt->name, dbname);
    opt->name_length= length;
    
    if ((error= my_hash_insert(&dboptions, (uchar*) opt)))
    {
      my_free(opt);
      goto end;
    }
  }

  /* Update / write options in hash */
  opt->charset= create->default_table_charset;

end:
  mysql_rwlock_unlock(&LOCK_dboptions);
  DBUG_RETURN(error);
}


/*
  Deletes database options from the hash.
*/

static void del_dbopt(const char *path)
{
  my_dbopt_t *opt;
  mysql_rwlock_wrlock(&LOCK_dboptions);
  if ((opt= (my_dbopt_t *)my_hash_search(&dboptions, (const uchar*) path,
                                         strlen(path))))
    my_hash_delete(&dboptions, (uchar*) opt);
  mysql_rwlock_unlock(&LOCK_dboptions);
}

/*
  Load database options file

  load_db_opt()
  path		Path for option file
  create	Where to store the read options

  DESCRIPTION

  RETURN VALUES
  0	File found
  1	No database file or could not open it

*/

bool load_db_opt(THD *thd, const char *path, HA_CREATE_INFO *create)
{
  File file;
  char buf[256];
  DBUG_ENTER("load_db_opt");
  bool error=1;
  uint nbytes;

  memset(create, 0, sizeof(*create));
  create->default_table_charset= thd->variables.collation_server;

  /* Check if options for this database are already in the hash */
  if (!get_dbopt(path, create))
    DBUG_RETURN(0);

  /* Otherwise, load options from the .opt file */
  if ((file= mysql_file_open(key_file_dbopt,
                             path, O_RDONLY | O_SHARE, MYF(0))) < 0)
    goto err1;

  IO_CACHE cache;
  if (init_io_cache(&cache, file, IO_SIZE, READ_CACHE, 0, 0, MYF(0)))
    goto err2;

  while ((int) (nbytes= my_b_gets(&cache, (char*) buf, sizeof(buf))) > 0)
  {
    char *pos= buf+nbytes-1;
    /* Remove end space and control characters */
    while (pos > buf && !my_isgraph(&my_charset_latin1, pos[-1]))
      pos--;
    *pos=0;
    if ((pos= strchr(buf, '=')))
    {
      if (!strncmp(buf,"default-character-set", (pos-buf)))
      {
        /*
           Try character set name, and if it fails
           try collation name, probably it's an old
           4.1.0 db.opt file, which didn't have
           separate default-character-set and
           default-collation commands.
        */
        if (!(create->default_table_charset=
        get_charset_by_csname(pos+1, MY_CS_PRIMARY, MYF(0))) &&
            !(create->default_table_charset=
              get_charset_by_name(pos+1, MYF(0))))
        {
          sql_print_error("Error while loading database options: '%s':",path);
          sql_print_error(ER(ER_UNKNOWN_CHARACTER_SET),pos+1);
          create->default_table_charset= default_charset_info;
        }
      }
      else if (!strncmp(buf,"default-collation", (pos-buf)))
      {
        if (!(create->default_table_charset= get_charset_by_name(pos+1,
                                                           MYF(0))))
        {
          sql_print_error("Error while loading database options: '%s':",path);
          sql_print_error(ER(ER_UNKNOWN_COLLATION),pos+1);
          create->default_table_charset= default_charset_info;
        }
      }
    }
  }
  /*
    Put the loaded value into the hash.
    Note that another thread could've added the same
    entry to the hash after we called get_dbopt(),
    but it's not an error, as put_dbopt() takes this
    possibility into account.
  */
  error= put_dbopt(path, create);

  end_io_cache(&cache);
err2:
  mysql_file_close(file, MYF(0));
err1:
  DBUG_RETURN(error);
}


/*
  Retrieve database options by name. Load database options file or fetch from
  cache.

  SYNOPSIS
    load_db_opt_by_name()
    db_name         Database name
    db_create_info  Where to store the database options

  DESCRIPTION
    load_db_opt_by_name() is a shortcut for load_db_opt().

  NOTE
    Although load_db_opt_by_name() (and load_db_opt()) returns status of
    the operation, it is useless usually and should be ignored. The problem
    is that there are 1) system databases ("mysql") and 2) virtual
    databases ("information_schema"), which do not contain options file.
    So, load_db_opt[_by_name]() returns FALSE for these databases, but this
    is not an error.

    load_db_opt[_by_name]() clears db_create_info structure in any case, so
    even on failure it contains valid data. So, common use case is just
    call load_db_opt[_by_name]() without checking return value and use
    db_create_info right after that.

  RETURN VALUES (read NOTE!)
    FALSE   Success
    TRUE    Failed to retrieve options
*/

bool load_db_opt_by_name(THD *thd, const char *db_name,
                         HA_CREATE_INFO *db_create_info)
{
  char db_opt_path[FN_REFLEN + 1];

  /*
    Pass an empty file name, and the database options file name as extension
    to avoid table name to file name encoding.
  */
  (void) build_table_filename(db_opt_path, sizeof(db_opt_path) - 1,
                              db_name, "", MY_DB_OPT_FILE, 0);

  return load_db_opt(thd, db_opt_path, db_create_info);
}


/**
  Return default database collation.

  @param thd     Thread context.
  @param db_name Database name.

  @return CHARSET_INFO object. The operation always return valid character
    set, even if the database does not exist.
*/

const CHARSET_INFO *get_default_db_collation(THD *thd, const char *db_name)
{
  HA_CREATE_INFO db_info;

  if (thd->db != NULL && strcmp(db_name, thd->db) == 0)
    return thd->db_charset;

  load_db_opt_by_name(thd, db_name, &db_info);

  /*
    NOTE: even if load_db_opt_by_name() fails,
    db_info.default_table_charset contains valid character set
    (collation_server). We should not fail if load_db_opt_by_name() fails,
    because it is valid case. If a database has been created just by
    "mkdir", it does not contain db.opt file, but it is valid database.
  */

  return db_info.default_table_charset;
}
