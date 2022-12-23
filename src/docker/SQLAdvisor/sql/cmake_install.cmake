# Install script for directory: /home/longxuegang/dba_public_scripts_tools/sqlparser/sql

# Set the install prefix
IF(NOT DEFINED CMAKE_INSTALL_PREFIX)
  SET(CMAKE_INSTALL_PREFIX "/usr/local/sqlparser")
ENDIF(NOT DEFINED CMAKE_INSTALL_PREFIX)
STRING(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
IF(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  IF(BUILD_TYPE)
    STRING(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  ELSE(BUILD_TYPE)
    SET(CMAKE_INSTALL_CONFIG_NAME "debug")
  ENDIF(BUILD_TYPE)
  MESSAGE(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
ENDIF(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)

# Set the component getting installed.
IF(NOT CMAKE_INSTALL_COMPONENT)
  IF(COMPONENT)
    MESSAGE(STATUS "Install component: \"${COMPONENT}\"")
    SET(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  ELSE(COMPONENT)
    SET(CMAKE_INSTALL_COMPONENT)
  ENDIF(COMPONENT)
ENDIF(NOT CMAKE_INSTALL_COMPONENT)

# Install shared libraries without execute permission?
IF(NOT DEFINED CMAKE_INSTALL_SO_NO_EXE)
  SET(CMAKE_INSTALL_SO_NO_EXE "0")
ENDIF(NOT DEFINED CMAKE_INSTALL_SO_NO_EXE)

IF(NOT CMAKE_INSTALL_COMPONENT OR "${CMAKE_INSTALL_COMPONENT}" STREQUAL "Server")
  FILE(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE SHARED_LIBRARY FILES "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/CMakeFiles/CMakeRelink.dir/libsqlparser-debug.so")
ENDIF(NOT CMAKE_INSTALL_COMPONENT OR "${CMAKE_INSTALL_COMPONENT}" STREQUAL "Server")

IF(NOT CMAKE_INSTALL_COMPONENT OR "${CMAKE_INSTALL_COMPONENT}" STREQUAL "Development")
  FILE(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include/sql" TYPE FILE FILES
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_partition_admin.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/opt_explain_format.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/strfunc.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/gstream.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/item_subselect.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sp_pcontext.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/unireg.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_rename.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_lex.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/custom_conf.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_data_change.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_alter.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_update.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_do.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/merge_sort.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/lex_symbol.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/mem_root_array.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/partition_info.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_view.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_error.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_hset.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_plugin_services.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/query_strip_comments.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/item_xmlfunc.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_resolver.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sp_instr.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/global_threads.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/item_strfunc.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_priv.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/string_service.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/item_geofunc.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_load.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/dynamic_ids.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sys_vars_shared.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/message.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_cmd.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/item.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_truncate.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/delayable_insert_operation.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_list.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/table.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/item_cmpfunc.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_sort.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_bootstrap.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/derror.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_array.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/records.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sp_head.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_profile.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_cursor.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/mysqld_suffix.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_reload.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/item_sum.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_db.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_insert.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_bitmap.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/handler.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/hash_filo.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/opt_explain_traditional.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/gcalc_slicescan.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/log.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/mysqld.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/opt_explain.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_parse_index.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/event_parse_data.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_admin.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sys_vars.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/partition_element.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_plugin.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/spatial.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/parse_file.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sp.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_parse.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_table.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/lex.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_callback.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/my_decimal.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_acl.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/item_create.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_show.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_rewrite.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/opt_explain_json.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_const.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_udf.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/thr_malloc.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/procedure.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/init.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_plist.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_help.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/nt_servc.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/table_id.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_class.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/lex_hash.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_get_diagnostics.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_alloc.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_handler.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/discover.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_test.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_delete.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/key.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_prepare.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_timer.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/structs.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/item_row.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_yacc.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_signal.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/item_inetfunc.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_trigger.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/item_func.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_tablespace.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_base.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_derived.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_locale.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/tzfile.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/set_var.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_partition.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/item_timefunc.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_crypt.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_time.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_string.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_servers.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/bounded_queue.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/sql_analyse.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/sql/client_settings.h"
    )
ENDIF(NOT CMAKE_INSTALL_COMPONENT OR "${CMAKE_INSTALL_COMPONENT}" STREQUAL "Development")

IF(NOT CMAKE_INSTALL_COMPONENT OR "${CMAKE_INSTALL_COMPONENT}" STREQUAL "DebugBinaries")
  IF("${CMAKE_INSTALL_CONFIG_NAME}" MATCHES "^([Rr][Ee][Ll][Ee][Aa][Ss][Ee]|[Rr][Ee][Ll][Ww][Ii][Tt][Hh][Dd][Ee][Bb][Ii][Nn][Ff][Oo])$")
    FILE(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/bin" TYPE FILE OPTIONAL PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE FILES "/home/longxuegang/dba_public_scripts_tools/debug/sql/libsqlparser-debug.so")
  ENDIF("${CMAKE_INSTALL_CONFIG_NAME}" MATCHES "^([Rr][Ee][Ll][Ee][Aa][Ss][Ee]|[Rr][Ee][Ll][Ww][Ii][Tt][Hh][Dd][Ee][Bb][Ii][Nn][Ff][Oo])$")
ENDIF(NOT CMAKE_INSTALL_COMPONENT OR "${CMAKE_INSTALL_COMPONENT}" STREQUAL "DebugBinaries")

