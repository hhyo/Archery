/* Copyright (c) 2000, 2014, Oracle and/or its affiliates. All rights reserved.
   Copyright (c) 2009, 2013, Monty Program Ab
   Copyright (C) 2012 Percona Inc.

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


/**
  @file

  @brief
  logging of commands

  @todo
    Abort logging when we get an error in reading or writing log files
*/

#include "my_global.h"                          /* NO_EMBEDDED_ACCESS_CHECKS */
#include "sql_priv.h"
#include "log.h"
#include "sql_base.h"                           // open_log_table
#include "sql_delete.h"                         // mysql_truncate
#include "sql_parse.h"                          // command_name
#include "sql_time.h"           // calc_time_from_sec, my_time_compare
#include "sql_acl.h"            // SUPER_ACL
#include "mysql/service_my_plugin_log.h"
#include "sp_head.h"

#include <my_dir.h>
#include <stdarg.h>
#include <m_ctype.h>				// For test_if_number

#ifdef _WIN32
#include "message.h"
#endif

using std::min;
using std::max;

#include "sql_show.h"
#include "mysqld.h"

/* max size of the log message */
#define MAX_LOG_BUFFER_SIZE 1024
#define MAX_TIME_SIZE 32

#define MAX_USER_HOST_SIZE 512

static
const TABLE_FIELD_TYPE general_log_table_fields[GLT_FIELD_COUNT] =
{
  {
    { C_STRING_WITH_LEN("event_time") },
    { C_STRING_WITH_LEN("timestamp") },
    { NULL, 0 }
  },
  {
    { C_STRING_WITH_LEN("user_host") },
    { C_STRING_WITH_LEN("mediumtext") },
    { C_STRING_WITH_LEN("utf8") }
  },
  {
    { C_STRING_WITH_LEN("thread_id") },
    { C_STRING_WITH_LEN("bigint(21) unsigned") },
    { NULL, 0 }
  },
  {
    { C_STRING_WITH_LEN("server_id") },
    { C_STRING_WITH_LEN("int(10) unsigned") },
    { NULL, 0 }
  },
  {
    { C_STRING_WITH_LEN("command_type") },
    { C_STRING_WITH_LEN("varchar(64)") },
    { C_STRING_WITH_LEN("utf8") }
  },
  {
    { C_STRING_WITH_LEN("argument") },
    { C_STRING_WITH_LEN("mediumtext") },
    { C_STRING_WITH_LEN("utf8") }
  }
};

LOGGER logger;

static bool test_if_number(const char *str,
			   ulong *res, bool allow_wildcards);

/**
   purge logs, master and slave sides both, related error code
   convertor.
   Called from @c purge_error_message(), @c MYSQL_BIN_LOG::reset_logs()

   @param  res  an internal to purging routines error code 

   @return the user level error code ER_*
*/
uint purge_log_get_error_code(int res)
{
  uint errcode= 0;

  switch (res)  {
  case 0: break;
  case LOG_INFO_EOF:	errcode= ER_UNKNOWN_TARGET_BINLOG; break;
  case LOG_INFO_IO:	errcode= ER_IO_ERR_LOG_INDEX_READ; break;
  case LOG_INFO_INVALID:errcode= ER_BINLOG_PURGE_PROHIBITED; break;
  case LOG_INFO_SEEK:	errcode= ER_FSEEK_FAIL; break;
  case LOG_INFO_MEM:	errcode= ER_OUT_OF_RESOURCES; break;
  case LOG_INFO_FATAL:	errcode= ER_BINLOG_PURGE_FATAL_ERR; break;
  case LOG_INFO_IN_USE: errcode= ER_LOG_IN_USE; break;
  case LOG_INFO_EMFILE: errcode= ER_BINLOG_PURGE_EMFILE; break;
  default:		errcode= ER_LOG_PURGE_UNKNOWN_ERR; break;
  }

  return errcode;
}

/**
  Silence all errors and warnings reported when performing a write
  to a log table.
  Errors and warnings are not reported to the client or SQL exception
  handlers, so that the presence of logging does not interfere and affect
  the logic of an application.
*/
class Silence_log_table_errors : public Internal_error_handler
{
  char m_message[MYSQL_ERRMSG_SIZE];
public:
  Silence_log_table_errors()
  {
    m_message[0]= '\0';
  }

  virtual ~Silence_log_table_errors() {}

  virtual bool handle_condition(THD *thd,
                                uint sql_errno,
                                const char* sql_state,
                                Sql_condition::enum_warning_level level,
                                const char* msg,
                                Sql_condition ** cond_hdl);
  const char *message() const { return m_message; }
};

bool
Silence_log_table_errors::handle_condition(THD *,
                                           uint,
                                           const char*,
                                           Sql_condition::enum_warning_level,
                                           const char* msg,
                                           Sql_condition ** cond_hdl)
{
  *cond_hdl= NULL;
  strmake(m_message, msg, sizeof(m_message)-1);
  return TRUE;
}

sql_print_message_func sql_print_message_handlers[3] =
{
  sql_print_information,
  sql_print_warning,
  sql_print_error
};

/**
  Create the name of the log specified.

  This method forms a new path + file name for the
  log specified in @c name.

  @param[IN] buff    Location for building new string.
  @param[IN] name    Name of the log file.
  @param[IN] log_ext The extension for the log (e.g. .log).

  @returns Pointer to new string containing the name.
*/
char *make_log_name(char *buff, const char *name, const char* log_ext)
{
  strmake(buff, name, FN_REFLEN-5);
  return fn_format(buff, buff, mysql_real_data_home, log_ext,
                   MYF(MY_UNPACK_FILENAME|MY_REPLACE_EXT));
}


/* log event handlers */


bool Log_to_file_event_handler::
  log_error(enum loglevel level, const char *format,
            va_list args)
{
  return vprint_msg_to_log(level, format, args);
}


void Log_to_file_event_handler::init_pthread_objects()
{
  mysql_log.init_pthread_objects();
}

/**
   Wrapper around MYSQL_LOG::write() for general log. We need it since we
   want all log event handlers to have the same signature.
*/

bool Log_to_file_event_handler::
  log_general(THD *thd, time_t event_time, const char *user_host,
              uint user_host_len, my_thread_id thread_id,
              const char *command_type, uint command_type_len,
              const char *sql_text, uint sql_text_len,
              const CHARSET_INFO *client_cs)
{
  Silence_log_table_errors error_handler;
  thd->push_internal_handler(&error_handler);
  bool retval= mysql_log.write(event_time, user_host, user_host_len,
                               thread_id, command_type, command_type_len,
                               sql_text, sql_text_len);
  thd->pop_internal_handler();
  return retval;
}


bool Log_to_file_event_handler::init()
{
  if (!is_initialized)
  {
    if (opt_log)
      mysql_log.open_query_log(opt_logname);

    is_initialized= TRUE;
  }

  return FALSE;
}


void Log_to_file_event_handler::cleanup()
{
  mysql_log.cleanup();
}

void Log_to_file_event_handler::flush()
{
  /* reopen log files */
  if (opt_log)
    mysql_log.reopen_file();
}

/*
  Log error with all enabled log event handlers

  SYNOPSIS
    error_log_print()

    level             The level of the error significance: NOTE,
                      WARNING or ERROR.
    format            format string for the error message
    args              list of arguments for the format string

  RETURN
    FALSE - OK
    TRUE - error occured
*/

bool LOGGER::error_log_print(enum loglevel level, const char *format,
                             va_list args)
{
  bool error= FALSE;
  Log_event_handler **current_handler;

  /* currently we don't need locking here as there is no error_log table */
  for (current_handler= error_log_handler_list ; *current_handler ;)
    error= (*current_handler++)->log_error(level, format, args) || error;

  return error;
}


void LOGGER::cleanup_base()
{
  DBUG_ASSERT(inited == 1);
  mysql_rwlock_destroy(&LOCK_logger);
  if (file_log_handler)
    file_log_handler->cleanup();
}


void LOGGER::cleanup_end()
{
  DBUG_ASSERT(inited == 1);
  if (file_log_handler)
  {
    delete file_log_handler;
    file_log_handler=NULL;
  }
  inited= 0;
}


/**
  Perform basic log initialization: create file-based log handler and
  init error log.
*/
void LOGGER::init_base()
{
  DBUG_ASSERT(inited == 0);
  inited= 1;

  /*
    Here we create file log handler. We don't do it for the table log handler
    here as it cannot be created so early. The reason is THD initialization,
    which depends on the system variables (parsed later).
  */
  if (!file_log_handler)
    file_log_handler= new Log_to_file_event_handler;

  /* by default we use traditional error log */
  init_error_log(LOG_FILE);

  file_log_handler->init_pthread_objects();
  mysql_rwlock_init(key_rwlock_LOCK_logger, &LOCK_logger);
}


bool LOGGER::flush_logs(THD *thd)
{
  int rc= 0;

  /*
    Now we lock logger, as nobody should be able to use logging routines while
    log tables are closed
  */
  logger.lock_exclusive();

  /* reopen log files */
  file_log_handler->flush();

  /* end of log flush */
  logger.unlock();
  return rc;
}

/**
  Close and reopen the general log (with locks).

  @returns FALSE.
*/
bool LOGGER::flush_general_log()
{
  /*
    Now we lock logger, as nobody should be able to use logging routines while
    log tables are closed
  */
  logger.lock_exclusive();

  /* Reopen general log file */
  if (opt_log)
    file_log_handler->get_mysql_log()->reopen_file();

  /* End of log flush */
  logger.unlock();

  return 0;
}


bool LOGGER::general_log_write(THD *thd, enum enum_server_command command,
                               const char *query, uint query_length)
{
  bool error= FALSE;
  Log_event_handler **current_handler= general_log_handler_list;
  char user_host_buff[MAX_USER_HOST_SIZE + 1];
  uint user_host_len= 0;
  time_t current_time;

  DBUG_ASSERT(thd);

  lock_shared();
  if (!opt_log)
  {
    unlock();
    return 0;
  }
  user_host_len= make_user_name(thd, user_host_buff);

  current_time= my_time(0);

  while (*current_handler)
    error|= (*current_handler++)->
      log_general(thd, current_time, user_host_buff,
                  user_host_len, thd->thread_id,
                  command_name[(uint) command].str,
                  command_name[(uint) command].length,
                  query, query_length,
                  thd->variables.character_set_client) || error;
  unlock();

  return error;
}

bool LOGGER::general_log_print(THD *thd, enum enum_server_command command,
                               const char *format, va_list args)
{
  uint message_buff_len= 0;
  char message_buff[MAX_LOG_BUFFER_SIZE];

  /* prepare message */
  if (format)
    message_buff_len= my_vsnprintf(message_buff, sizeof(message_buff),
                                   format, args);
  else
    message_buff[0]= '\0';

  /* Print the message to the buffer if we want to log this kind of commands */
  if (! logger.log_command(thd, command))
    return FALSE;

  return general_log_write(thd, command, message_buff, message_buff_len);
}

void LOGGER::init_error_log(uint error_log_printer)
{
  if (error_log_printer & LOG_NONE)
  {
    error_log_handler_list[0]= 0;
    return;
  }

  switch (error_log_printer) {
  case LOG_FILE:
    error_log_handler_list[0]= file_log_handler;
    error_log_handler_list[1]= 0;
    break;
    /* these two are disabled for now */
  case LOG_TABLE:
    DBUG_ASSERT(0);
    break;
  case LOG_TABLE|LOG_FILE:
    DBUG_ASSERT(0);
    break;
  }
}

void LOGGER::init_general_log(uint general_log_printer)
{
  if (general_log_printer & LOG_NONE)
  {
    general_log_handler_list[0]= 0;
    return;
  }

  switch (general_log_printer) {
  case LOG_FILE:
    general_log_handler_list[0]= file_log_handler;
    general_log_handler_list[1]= 0;
    break;
  case LOG_TABLE:
    general_log_handler_list[0]= 0;
    break;
  case LOG_TABLE|LOG_FILE:
    general_log_handler_list[0]= file_log_handler;
    general_log_handler_list[1]= 0;
    break;
  }
}


bool LOGGER::activate_log_handler(THD* thd, uint log_type)
{
  MYSQL_QUERY_LOG *file_log;
  bool res= FALSE;
  lock_exclusive();
  switch (log_type) {
  case QUERY_LOG_GENERAL:
    if (!opt_log)
    {
      file_log= file_log_handler->get_mysql_log();

      file_log->open_query_log(opt_logname);
        init_general_log(log_output_options);
        opt_log= TRUE;
    }
    break;
  default:
    DBUG_ASSERT(0);
  }
  unlock();
  return res;
}


void LOGGER::deactivate_log_handler(THD *thd, uint log_type)
{
  my_bool *tmp_opt= 0;
  MYSQL_LOG *file_log= NULL;

  switch (log_type) {
  case QUERY_LOG_GENERAL:
    tmp_opt= &opt_log;
    file_log= file_log_handler->get_mysql_log();
    break;
  default:
    MY_ASSERT_UNREACHABLE();
  }

  if (!(*tmp_opt))
    return;

  lock_exclusive();
  file_log->close(0);
  *tmp_opt= FALSE;
  unlock();
}


/* the parameters are unused for the log tables */
bool Log_to_csv_event_handler::init()
{
  return 0;
}

int LOGGER::set_handlers(uint error_log_printer,
                         uint general_log_printer)
{
  /* error log table is not supported yet */
  DBUG_ASSERT(error_log_printer < LOG_TABLE);

  lock_exclusive();

  if ((general_log_printer & LOG_TABLE) &&
      !is_log_tables_initialized)
  {
    general_log_printer= (general_log_printer & ~LOG_TABLE) | LOG_FILE;

    sql_print_error("Failed to initialize log tables. "
                    "Falling back to the old-fashioned logs");
  }

  init_error_log(error_log_printer);
  init_general_log(general_log_printer);

  unlock();

  return 0;
}

#ifdef _WIN32
static int eventSource = 0;

static void setup_windows_event_source()
{
  HKEY    hRegKey= NULL;
  DWORD   dwError= 0;
  TCHAR   szPath[MAX_PATH];
  DWORD dwTypes;

  if (eventSource)               // Ensure that we are only called once
    return;
  eventSource= 1;

  // Create the event source registry key
  dwError= RegCreateKey(HKEY_LOCAL_MACHINE,
                          "SYSTEM\\CurrentControlSet\\Services\\EventLog\\Application\\MySQL", 
                          &hRegKey);

  /* Name of the PE module that contains the message resource */
  GetModuleFileName(NULL, szPath, MAX_PATH);

  /* Register EventMessageFile */
  dwError = RegSetValueEx(hRegKey, "EventMessageFile", 0, REG_EXPAND_SZ,
                          (PBYTE) szPath, (DWORD) (strlen(szPath) + 1));

  /* Register supported event types */
  dwTypes= (EVENTLOG_ERROR_TYPE | EVENTLOG_WARNING_TYPE |
            EVENTLOG_INFORMATION_TYPE);
  dwError= RegSetValueEx(hRegKey, "TypesSupported", 0, REG_DWORD,
                         (LPBYTE) &dwTypes, sizeof dwTypes);

  RegCloseKey(hRegKey);
}

#endif /* _WIN32 */

/**
  Find a unique filename for 'filename.#'.

  Set '#' to the number next to the maximum found in the most
  recent log file extension.

  This function will return nonzero if: (i) the generated name
  exceeds FN_REFLEN; (ii) if the number of extensions is exhausted;
  or (iii) some other error happened while examining the filesystem.

  @return
    nonzero if not possible to get unique filename.
*/

static int find_uniq_filename(char *name, ulong *next)
{
  uint                  i;
  char                  buff[FN_REFLEN], ext_buf[FN_REFLEN];
  struct st_my_dir     *dir_info;
  reg1 struct fileinfo *file_info;
  ulong                 max_found= 0, number= 0;
  size_t		buf_length, length;
  char			*start, *end;
  int                   error= 0;
  DBUG_ENTER("find_uniq_filename");

  *next= 0;
  length= dirname_part(buff, name, &buf_length);
  start=  name + length;
  end=    strend(start);

  *end='.';
  length= (size_t) (end - start + 1);

  if ((DBUG_EVALUATE_IF("error_unique_log_filename", 1, 
      !(dir_info= my_dir(buff,MYF(MY_DONT_SORT))))))
  {						// This shouldn't happen
    strmov(end,".1");				// use name+1
    DBUG_RETURN(1);
  }
  file_info= dir_info->dir_entry;
  for (i= dir_info->number_off_files ; i-- ; file_info++)
  {
    if (memcmp(file_info->name, start, length) == 0 &&
	test_if_number(file_info->name+length, &number,0))
    {
      set_if_bigger(max_found,(ulong) number);
    }
  }
  my_dirend(dir_info);

  /* check if reached the maximum possible extension number */
  if (max_found == MAX_LOG_UNIQUE_FN_EXT)
  {
    sql_print_error("Log filename extension number exhausted: %06lu. \
Please fix this by archiving old logs and \
updating the index files.", max_found);
    error= 1;
    goto end;
  }

  *next= max_found + 1;
  if (sprintf(ext_buf, "%06lu", *next) < 0)
  {
    error= 1;
    goto end;
  }
  *end++='.';

  /* 
    Check if the generated extension size + the file name exceeds the
    buffer size used. If one did not check this, then the filename might be
    truncated, resulting in error.
   */
  if (((strlen(ext_buf) + (end - name)) >= FN_REFLEN))
  {
    sql_print_error("Log filename too large: %s%s (%zu). \
Please fix this by archiving old logs and updating the \
index files.", name, ext_buf, (strlen(ext_buf) + (end - name)));
    error= 1;
    goto end;
  }

  if (sprintf(end, "%06lu", *next)<0)
  {
    error= 1;
    goto end;
  }

  /* print warning if reaching the end of available extensions. */
  if ((*next > (MAX_LOG_UNIQUE_FN_EXT - LOG_WARN_UNIQUE_FN_EXT_LEFT)))
    sql_print_warning("Next log extension: %lu. \
Remaining log filename extensions: %lu. \
Please consider archiving some logs.", *next, (MAX_LOG_UNIQUE_FN_EXT - *next));

end:
  DBUG_RETURN(error);
}


void MYSQL_LOG::init(enum_log_type log_type_arg,
                     enum cache_type io_cache_type_arg)
{
  DBUG_ENTER("MYSQL_LOG::init");
  log_type= log_type_arg;
  io_cache_type= io_cache_type_arg;
  DBUG_PRINT("info",("log_type: %d", log_type));
  DBUG_VOID_RETURN;
}


bool MYSQL_LOG::init_and_set_log_file_name(const char *log_name,
                                           const char *new_name,
                                           enum_log_type log_type_arg,
                                           enum cache_type io_cache_type_arg,
                                           bool unique)
{
  init(log_type_arg, io_cache_type_arg);

  if (new_name && !strmov(log_file_name, new_name))
    return TRUE;
  else if (!new_name && generate_new_name(log_file_name, log_name, unique))
    return TRUE;

  return FALSE;
}


/*
  Open a (new) log file.

  SYNOPSIS
    open()

    log_name            The name of the log to open
    log_type_arg        The type of the log. E.g. LOG_NORMAL
    new_name            The new name for the logfile. This is only needed
                        when the method is used to open the binlog file.
    io_cache_type_arg   The type of the IO_CACHE to use for this log file

  DESCRIPTION
    Open the logfile, init IO_CACHE and write startup messages
    (in case of general and slow query logs).

  RETURN VALUES
    0   ok
    1   error
*/

bool MYSQL_LOG::open(
#ifdef HAVE_PSI_INTERFACE
                     PSI_file_key log_file_key,
#endif
                     const char *log_name, enum_log_type log_type_arg,
                     const char *new_name, enum cache_type io_cache_type_arg,
                     bool unique)
{
  char buff[FN_REFLEN];
  MY_STAT f_stat;
  File file= -1;
  my_off_t pos= 0;
  int open_flags= O_CREAT | O_BINARY;
  DBUG_ENTER("MYSQL_LOG::open");
  DBUG_PRINT("enter", ("log_type: %d", (int) log_type_arg));

  write_error= 0;

  if (!(name= my_strdup(log_name, MYF(MY_WME))))
  {
    name= (char *)log_name; // for the error message
    goto err;
  }

  if (init_and_set_log_file_name(name, new_name,
                                 log_type_arg, io_cache_type_arg, unique) ||
      DBUG_EVALUATE_IF("fault_injection_init_name", log_type == LOG_BIN, 0))
    goto err;

  /* File is regular writable file */
  if (my_stat(log_file_name, &f_stat, MYF(0)) && !MY_S_ISREG(f_stat.st_mode))
    goto err;

  if (io_cache_type == SEQ_READ_APPEND)
    open_flags |= O_RDWR | O_APPEND;
  else
    open_flags |= O_WRONLY | (log_type == LOG_BIN ? 0 : O_APPEND);

  db[0]= 0;

#ifdef HAVE_PSI_INTERFACE
  /* Keep the key for reopen */
  m_log_file_key= log_file_key;
#endif

  if ((file= mysql_file_open(log_file_key,
                             log_file_name, open_flags,
                             MYF(MY_WME | ME_WAITTANG))) < 0)
    goto err;

  if ((pos= mysql_file_tell(file, MYF(MY_WME))) == MY_FILEPOS_ERROR)
  {
    if (my_errno == ESPIPE)
      pos= 0;
    else
      goto err;
  }

  if (init_io_cache(&log_file, file, IO_SIZE, io_cache_type, pos, 0,
                    MYF(MY_WME | MY_NABP |
                        ((log_type == LOG_BIN) ? MY_WAIT_IF_FULL : 0))))
    goto err;

  if (log_type == LOG_NORMAL)
  {
    char *end;
    int len=my_snprintf(buff, sizeof(buff), "%s, Version: %s (%s). "
#ifdef EMBEDDED_LIBRARY
                        "embedded library\n",
                        my_progname, server_version, MYSQL_COMPILATION_COMMENT
#elif _WIN32
			"started with:\nTCP Port: %d, Named Pipe: %s\n",
                        my_progname, server_version, MYSQL_COMPILATION_COMMENT,
                        mysqld_port, mysqld_unix_port
#else
			"started with:\n=\n",
                        my_progname, server_version, MYSQL_COMPILATION_COMMENT
#endif
                       );
    end= strnmov(buff + len, "Time                 Id Command    Argument\n",
                 sizeof(buff) - len);
    if (my_b_write(&log_file, (uchar*) buff, (uint) (end-buff)) ||
	flush_io_cache(&log_file))
      goto err;
  }

  log_state= LOG_OPENED;
  DBUG_RETURN(0);

err:
  if (log_type == LOG_BIN)
  {
    THD *thd= current_thd;
    /*
      On fatal error when code enters here we should forcefully clear the
      previous errors so that a new critical error message can be pushed
      to the client side.
     */
    thd->clear_error();
    my_error(ER_BINLOG_LOGGING_IMPOSSIBLE, MYF(0), "Either disk is full or "
             "file system is read only while opening the binlog. Aborting the "
             "server");
    _exit(EXIT_FAILURE);
  }
  else
    sql_print_error("Could not open %s for logging (error %d). "
                    "Turning logging off for the whole duration "
                    "of the MySQL server process. To turn it on "
                    "again: fix the cause, shutdown the MySQL "
                    "server and restart it.",
                    name, errno);
  if (file >= 0)
    mysql_file_close(file, MYF(0));
  end_io_cache(&log_file);
  my_free(name);
  name= NULL;
  log_state= LOG_CLOSED;
  DBUG_RETURN(1);
}

MYSQL_LOG::MYSQL_LOG()
  : name(0), write_error(FALSE), inited(FALSE), log_type(LOG_UNKNOWN),
    log_state(LOG_CLOSED),
    cur_log_ext(-1)
#ifdef HAVE_PSI_INTERFACE
    , m_key_LOCK_log(key_LOG_LOCK_log)
#endif
{
  /*
    We don't want to initialize LOCK_Log here as such initialization depends on
    safe_mutex (when using safe_mutex) which depends on MY_INIT(), which is
    called only in main(). Doing initialization here would make it happen
    before main().
  */
  memset(&log_file, 0, sizeof(log_file));
}

void MYSQL_LOG::init_pthread_objects()
{
  DBUG_ASSERT(inited == 0);
  inited= 1;
  mysql_mutex_init(m_key_LOCK_log, &LOCK_log, MY_MUTEX_INIT_SLOW);
}

/*
  Close the log file

  SYNOPSIS
    close()
    exiting     Bitmask. For the slow and general logs the only used bit is
                LOG_CLOSE_TO_BE_OPENED. This is used if we intend to call
                open at once after close.

  NOTES
    One can do an open on the object at once after doing a close.
    The internal structures are not freed until cleanup() is called
*/

void MYSQL_LOG::close(uint exiting)
{					// One can't set log_type here!
  DBUG_ENTER("MYSQL_LOG::close");
  DBUG_PRINT("enter",("exiting: %d", (int) exiting));
  if (log_state == LOG_OPENED)
  {
    end_io_cache(&log_file);

    if (mysql_file_sync(log_file.file, MYF(MY_WME)) && ! write_error)
    {
      char errbuf[MYSYS_STRERROR_SIZE];
      write_error= 1;
      sql_print_error(ER_DEFAULT(ER_ERROR_ON_WRITE), name, errno,
                      my_strerror(errbuf, sizeof(errbuf), errno));
    }

    if (mysql_file_close(log_file.file, MYF(MY_WME)) && ! write_error)
    {
      char errbuf[MYSYS_STRERROR_SIZE];
      write_error= 1;
      sql_print_error(ER_DEFAULT(ER_ERROR_ON_WRITE), name, errno,
                      my_strerror(errbuf, sizeof(errbuf), errno));
    }
  }

  log_state= (exiting & LOG_CLOSE_TO_BE_OPENED) ? LOG_TO_BE_OPENED : LOG_CLOSED;
  my_free(name);
  name= NULL;
  DBUG_VOID_RETURN;
}

/** This is called only once. */

void MYSQL_LOG::cleanup()
{
  DBUG_ENTER("cleanup");
  if (inited)
  {
    inited= 0;
    mysql_mutex_destroy(&LOCK_log);
    close(0);
  }
  DBUG_VOID_RETURN;
}


int MYSQL_LOG::generate_new_name(char *new_name, const char *log_name,
                                 bool unique)
{
  fn_format(new_name, log_name, mysql_data_home, "", 4);
  if (unique)
  {
    if (!fn_ext(log_name)[0])
    {
      if (find_uniq_filename(new_name, &cur_log_ext))
      {
        my_printf_error(ER_NO_UNIQUE_LOGFILE, ER(ER_NO_UNIQUE_LOGFILE),
                        MYF(ME_FATALERROR), log_name);
	sql_print_error(ER(ER_NO_UNIQUE_LOGFILE), log_name);
	return 1;
      }
    }
  }
  return 0;
}


int MYSQL_LOG::purge_up_to(ulong to_ext, const char *log_name)
{
  char buff[FN_REFLEN];
  int error= 0;

  DBUG_ENTER("MYSQL_LOG::purge_up_to");

  do {
    snprintf(buff, sizeof(buff), "%s.%06lu", name, to_ext);
    if ((error= unlink(buff)))
    {
      if (my_errno == ENOENT)
        error= 0;
      break;
    }
    --to_ext;
  } while (to_ext > 0);

  DBUG_RETURN(error);
}

/*
  Reopen the log file

  SYNOPSIS
    reopen_file()

  DESCRIPTION
    Reopen the log file. The method is used during FLUSH LOGS
    and locks LOCK_log mutex
*/


void MYSQL_QUERY_LOG::reopen_file()
{
  char *save_name;

  DBUG_ENTER("MYSQL_LOG::reopen_file");
  if (!is_open())
  {
    DBUG_PRINT("info",("log is closed"));
    DBUG_VOID_RETURN;
  }

  mysql_mutex_lock(&LOCK_log);

  save_name= name;
  name= 0;				// Don't free name
  close(LOG_CLOSE_TO_BE_OPENED);

  /*
     Note that at this point, log_state != LOG_CLOSED (important for is_open()).
  */

  open(
#ifdef HAVE_PSI_INTERFACE
       m_log_file_key,
#endif
       save_name, log_type, 0, io_cache_type, false);
  my_free(save_name);

  mysql_mutex_unlock(&LOCK_log);

  DBUG_VOID_RETURN;
}


/*
  Write a command to traditional general log file

  SYNOPSIS
    write()

    event_time        command start timestamp
    user_host         the pointer to the string with user@host info
    user_host_len     length of the user_host string. this is computed once
                      and passed to all general log  event handlers
    thread_id         Id of the thread, issued a query
    command_type      the type of the command being logged
    command_type_len  the length of the string above
    sql_text          the very text of the query being executed
    sql_text_len      the length of sql_text string

  DESCRIPTION

   Log given command to to normal (not rotable) log file

  RETURN
    FASE - OK
    TRUE - error occured
*/

bool MYSQL_QUERY_LOG::write(time_t event_time, const char *user_host,
                            uint user_host_len, my_thread_id thread_id,
                            const char *command_type, uint command_type_len,
                            const char *sql_text, uint sql_text_len)
{
  char buff[32];
  uint length= 0;
  char local_time_buff[MAX_TIME_SIZE];
  struct tm start;
  uint time_buff_len= 0;

  mysql_mutex_lock(&LOCK_log);

  /* Test if someone closed between the is_open test and lock */
  if (is_open())
  {
    /* for testing output of timestamp and thread id */
    DBUG_EXECUTE_IF("reset_log_last_time", last_time= 0;);

    /* Note that my_b_write() assumes it knows the length for this */
      if (event_time != last_time)
      {
        last_time= event_time;

        localtime_r(&event_time, &start);

        time_buff_len= my_snprintf(local_time_buff, MAX_TIME_SIZE,
                                   "%02d%02d%02d %2d:%02d:%02d\t",
                                   start.tm_year % 100, start.tm_mon + 1,
                                   start.tm_mday, start.tm_hour,
                                   start.tm_min, start.tm_sec);

        if (my_b_write(&log_file, (uchar*) local_time_buff, time_buff_len))
          goto err;
      }
      else
        if (my_b_write(&log_file, (uchar*) "\t\t" ,2) < 0)
          goto err;

    length= my_snprintf(buff, 32, "%5lu ", thread_id);

    if (my_b_write(&log_file, (uchar*) buff, length))
      goto err;

    if (my_b_write(&log_file, (uchar*) command_type, command_type_len))
      goto err;

    if (my_b_write(&log_file, (uchar*) "\t", 1))
      goto err;

    /* sql_text */
    if (my_b_write(&log_file, (uchar*) sql_text, sql_text_len))
      goto err;

    if (my_b_write(&log_file, (uchar*) "\n", 1) ||
        flush_io_cache(&log_file))
      goto err;
  }

  mysql_mutex_unlock(&LOCK_log);
  return FALSE;
err:

  if (!write_error)
  {
    char errbuf[MYSYS_STRERROR_SIZE];
    write_error= 1;
    sql_print_error(ER(ER_ERROR_ON_WRITE), name, errno,
                    my_strerror(errbuf, sizeof(errbuf), errno));
  }
  mysql_mutex_unlock(&LOCK_log);
  return TRUE;
}

int MYSQL_QUERY_LOG::rotate(ulong max_size, bool *need_purge)
{
  int error;
  DBUG_ENTER("MYSQL_QUERY_LOG::rotate");

  *need_purge= false;
  if (my_b_tell(&log_file) > max_size)
  {
    if ((error= new_file()))
      DBUG_RETURN(error);

    *need_purge= true;
  }

  DBUG_RETURN(0);
}

int MYSQL_QUERY_LOG::new_file()
{
  int error= 0, close_on_error= FALSE;
  char new_name[FN_REFLEN], *old_name;

  DBUG_ENTER("MYSQL_QUERY_LOG::new_file");
  if (!is_open())
  {
    DBUG_PRINT("info",("log is closed"));
    DBUG_RETURN(error);
  }

  mysql_mutex_assert_owner(&LOCK_log);

  if (cur_log_ext == (ulong)-1)
  {
    strcpy(new_name, name);
    if ((error= generate_new_name(new_name, name, true)))
      goto end;
  }
  else
  {
    if (cur_log_ext == MAX_LOG_UNIQUE_FN_EXT)
    {
      error= 1;
      goto end;
    }
    snprintf(new_name, sizeof(new_name), "%s.%06lu", name, ++cur_log_ext);
  }

  /*
    close will try to free name and zero name pointer,
    We saving current name value and zeroing the pointer to
    prvent it.
  */
  old_name= name;
  name= NULL;
  close(LOG_CLOSE_TO_BE_OPENED);
  name= old_name;

  error= open(
#ifdef HAVE_PSI_INTERFACE
                key_file_query_log,
#endif
                name,
                LOG_NORMAL, new_name, WRITE_CACHE, false);

  my_free(old_name);

end:

  if (error && close_on_error /* rotate or reopen failed */)
  {
    sql_print_error("Could not open %s for logging (error %d). "
                     "Turning logging off for the whole duration "
                     "of the MySQL server process. To turn it on "
                     "again: fix the cause, shutdown the MySQL "
                     "server and restart it.", 
                     new_name, errno);
  }

  DBUG_RETURN(error);
}


/**
  @todo
  The following should be using fn_format();  We just need to
  first change fn_format() to cut the file name if it's too long.
*/
const char *MYSQL_LOG::generate_name(const char *log_name,
                                      const char *suffix,
                                      bool strip_ext, char *buff)
{
  if (!log_name || !log_name[0])
  {
    strmake(buff, pidfile_name, FN_REFLEN - strlen(suffix) - 1);
    return (const char *)
      fn_format(buff, buff, "", suffix, MYF(MY_REPLACE_EXT|MY_REPLACE_DIR));
  }
  // get rid of extension if the log is binary to avoid problems
  if (strip_ext)
  {
    char *p= fn_ext(log_name);
    uint length= (uint) (p - log_name);
    strmake(buff, log_name, min<size_t>(length, FN_REFLEN-1));
    return (const char*)buff;
  }
  return log_name;
}


int error_log_print(enum loglevel level, const char *format,
                    va_list args)
{
  return logger.error_log_print(level, format, args);
}


bool LOGGER::log_command(THD *thd, enum enum_server_command command)
{
  /*
    Log command if we have at least one log event handler enabled and want
    to log this king of commands
  */
  if (*general_log_handler_list && (what_to_log & (1L << (uint) command)))
  {
    if ((thd->variables.option_bits & OPTION_LOG_OFF))
    {
      /* No logging */
      return FALSE;
    }

    return TRUE;
  }

  return FALSE;
}


bool general_log_print(THD *thd, enum enum_server_command command,
                       const char *format, ...)
{
  va_list args;
  uint error= 0;

  va_start(args, format);
  error= logger.general_log_print(thd, command, format, args);
  va_end(args);

  return error;
}

bool general_log_write(THD *thd, enum enum_server_command command,
                       const char *query, uint query_length)
{
  /* Write the message to the log if we want to log this king of commands */
  if (logger.log_command(thd, command))
    return logger.general_log_write(thd, command, query, query_length);

  return FALSE;
}

/**
  Check if a string is a valid number.

  @param str			String to test
  @param res			Store value here
  @param allow_wildcards	Set to 1 if we should ignore '%' and '_'

  @note
    For the moment the allow_wildcards argument is not used
    Should be move to some other file.

  @retval
    1	String is a number
  @retval
    0	String is not a number
*/

static bool test_if_number(register const char *str,
			   ulong *res, bool allow_wildcards)
{
  reg2 int flag;
  const char *start;
  DBUG_ENTER("test_if_number");

  flag=0; start=str;
  while (*str++ == ' ') ;
  if (*--str == '-' || *str == '+')
    str++;
  while (my_isdigit(files_charset_info,*str) ||
	 (allow_wildcards && (*str == wild_many || *str == wild_one)))
  {
    flag=1;
    str++;
  }
  if (*str == '.')
  {
    for (str++ ;
	 my_isdigit(files_charset_info,*str) ||
	   (allow_wildcards && (*str == wild_many || *str == wild_one)) ;
	 str++, flag=1) ;
  }
  if (*str != 0 || flag == 0)
    DBUG_RETURN(0);
  if (res)
    *res=atol(start);
  DBUG_RETURN(1);			/* Number ok */
} /* test_if_number */


void sql_perror(const char *message)
{
#ifdef HAVE_STRERROR
  sql_print_error("%s: %s",message, strerror(errno));
#else
  perror(message);
#endif
}


#ifdef _WIN32
static void print_buffer_to_nt_eventlog(enum loglevel level, char *buff,
                                        size_t length, size_t buffLen)
{
  HANDLE event;
  char   *buffptr= buff;
  DBUG_ENTER("print_buffer_to_nt_eventlog");

  /* Add ending CR/LF's to string, overwrite last chars if necessary */
  strmov(buffptr+min(length, buffLen-5), "\r\n\r\n");

  setup_windows_event_source();
  if ((event= RegisterEventSource(NULL,"MySQL")))
  {
    switch (level) {
      case ERROR_LEVEL:
        ReportEvent(event, EVENTLOG_ERROR_TYPE, 0, MSG_DEFAULT, NULL, 1, 0,
                    (LPCSTR*)&buffptr, NULL);
        break;
      case WARNING_LEVEL:
        ReportEvent(event, EVENTLOG_WARNING_TYPE, 0, MSG_DEFAULT, NULL, 1, 0,
                    (LPCSTR*) &buffptr, NULL);
        break;
      case INFORMATION_LEVEL:
        ReportEvent(event, EVENTLOG_INFORMATION_TYPE, 0, MSG_DEFAULT, NULL, 1,
                    0, (LPCSTR*) &buffptr, NULL);
        break;
    }
    DeregisterEventSource(event);
  }

  DBUG_VOID_RETURN;
}
#endif /* _WIN32 */


#ifndef EMBEDDED_LIBRARY
static void print_buffer_to_file(enum loglevel level, const char *buffer,
                                 size_t length)
{
  time_t skr;
  struct tm tm_tmp;
  struct tm *start;
  DBUG_ENTER("print_buffer_to_file");
  DBUG_PRINT("enter",("buffer: %s", buffer));

  mysql_mutex_lock(&LOCK_error_log);

  skr= my_time(0);
  localtime_r(&skr, &tm_tmp);
  start=&tm_tmp;

  fprintf(stderr, "%d-%02d-%02d %02d:%02d:%02d %lu [%s] %.*s\n",
          start->tm_year + 1900,
          start->tm_mon + 1,
          start->tm_mday,
          start->tm_hour,
          start->tm_min,
          start->tm_sec,
          current_pid,
          (level == ERROR_LEVEL ? "ERROR" : level == WARNING_LEVEL ?
           "Warning" : "Note"),
          (int) length, buffer);

  fflush(stderr);

  mysql_mutex_unlock(&LOCK_error_log);
  DBUG_VOID_RETURN;
}

/**
  Prints a printf style message to the error log and, under NT, to the
  Windows event log.

  This function prints the message into a buffer and then sends that buffer
  to other functions to write that message to other logging sources.

  @param level          The level of the msg significance
  @param format         Printf style format of message
  @param args           va_list list of arguments for the message

  @returns
    The function always returns 0. The return value is present in the
    signature to be compatible with other logging routines, which could
    return an error (e.g. logging to the log tables)
*/
int vprint_msg_to_log(enum loglevel level, const char *format, va_list args)
{
  char   buff[1024];
  size_t length;
  DBUG_ENTER("vprint_msg_to_log");

  length= my_vsnprintf(buff, sizeof(buff), format, args);
  print_buffer_to_file(level, buff, length);

#ifdef _WIN32
  print_buffer_to_nt_eventlog(level, buff, length, sizeof(buff));
#endif

  DBUG_RETURN(0);
}
#endif /* EMBEDDED_LIBRARY */


void sql_print_error(const char *format, ...) 
{
  va_list args;
  DBUG_ENTER("sql_print_error");

  va_start(args, format);
  error_log_print(ERROR_LEVEL, format, args);
  va_end(args);

  DBUG_VOID_RETURN;
}


void sql_print_warning(const char *format, ...) 
{
  va_list args;
  DBUG_ENTER("sql_print_warning");

  va_start(args, format);
  error_log_print(WARNING_LEVEL, format, args);
  va_end(args);

  DBUG_VOID_RETURN;
}


void sql_print_information(const char *format, ...) 
{
  va_list args;
  DBUG_ENTER("sql_print_information");

  va_start(args, format);
  error_log_print(INFORMATION_LEVEL, format, args);
  va_end(args);

  DBUG_VOID_RETURN;
}


