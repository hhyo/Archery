# Copyright (c) 2006, 2014, Oracle and/or its affiliates. All rights reserved.
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

INCLUDE_DIRECTORIES(
  ${CMAKE_SOURCE_DIR}/include 
  ${CMAKE_SOURCE_DIR}/sql 
  ${CMAKE_SOURCE_DIR}/regex 
  ${ZLIB_INCLUDE_DIR}
  ${SSL_INCLUDE_DIRS}
  ${CMAKE_BINARY_DIR}/sql
)

SET(GEN_SOURCES
  ${CMAKE_CURRENT_BINARY_DIR}/sql_yacc.h 
  ${CMAKE_CURRENT_BINARY_DIR}/sql_yacc.cc
  ${CMAKE_CURRENT_BINARY_DIR}/lex_hash.h 
)

SET_SOURCE_FILES_PROPERTIES(${GEN_SOURCES} PROPERTIES GENERATED 1)

ADD_DEFINITIONS(-DMYSQL_SERVER -DHAVE_EVENT_SCHEDULER -DHAVE_POOL_OF_THREADS)
IF(SSL_DEFINES)
 ADD_DEFINITIONS(${SSL_DEFINES})
ENDIF()

SET(SQL_SHARED_SOURCES
  derror.cc

  handler.cc
  init.cc
  item.cc
  item_cmpfunc.cc 
  item_create.cc
  item_func.cc
  item_geofunc.cc
  item_row.cc 
  item_strfunc.cc
  item_subselect.cc
  item_sum.cc
  item_timefunc.cc 
  item_xmlfunc.cc 
  item_inetfunc.cc

  log.cc
  my_decimal.cc

  partition_info.cc
  password.c
  set_var.cc
  sp.cc
  sp_head.cc
  sql_crypt.cc
  sp_pcontext.cc
  sql_alloc_error_handler.cc
  sql_alter.cc
  sql_db.cc
  sql_error.cc
  sql_lex.cc
  sql_locale.cc
  sql_parse.cc
  sql_class.cc
  sql_list.cc
  sql_plugin.cc
  sql_show.cc
  sql_signal.cc
  sql_state.c
  sql_string.cc
  sql_table.cc
  sql_time.cc
  strfunc.cc
  sys_vars.cc
  table.cc
  thr_malloc.cc
)


SET(SQL_EXPORTED_SOURCES ${SQL_SHARED_SOURCES} PARENT_SCOPE)

SET(SQL_SOURCE
  ${GEN_SOURCES}
  ${MYSYS_LIBWRAP_SOURCE}
  ${SQL_SHARED_SOURCES}
  ../sql-common/my_time.c
  ../sql-common/pack.c
  #../sql-common/client.c
  #../sql-common/libmysql.c
  
  event_parse_data.cc
  mysqld.cc
  )

ADD_LIBRARY(sqlparser SHARED ${SQL_SOURCE})
ADD_DEPENDENCIES(sqlparser GenServerSource)
DTRACE_INSTRUMENT(sqlparser)
TARGET_LINK_LIBRARIES(sqlparser ${MYSQLD_STATIC_PLUGIN_LIBS} 
  mysys mysys_ssl strings regex   
  ${LIBWRAP} ${LIBCRYPT} ${LIBDL}
  ${SSL_LIBRARIES})

#
# On Windows platform we compile in the clinet-side Windows Native Authentication
# plugin which is used by the client connection code included in the server.
#
IF(WIN32)
  ADD_DEFINITIONS(-DAUTHENTICATION_WIN)
  TARGET_LINK_LIBRARIES(sqlparser auth_win_client)
ENDIF()

OPTION(DEBUG_EXTNAME "Build server as sqlparser-debug (debug builds only)" OFF)
MARK_AS_ADVANCED(DEBUG_EXTNAME)

IF(DEBUG_EXTNAME)
  SET_TARGET_PROPERTIES(sqlparser PROPERTIES DEBUG_OUTPUT_NAME "sqlparser-debug")
ENDIF()

IF(APPLE) 
  # Add CoreServices framework since some dloadable plugins may need it 
  FIND_LIBRARY(CORESERVICES NAMES CoreServices) 
  IF(CORESERVICES) 
    TARGET_LINK_LIBRARIES(sqlparser ${CORESERVICES}) 
  ENDIF() 
ENDIF() 

IF(NOT WITHOUT_DYNAMIC_PLUGINS)
  SET_TARGET_PROPERTIES(sqlparser PROPERTIES ENABLE_EXPORTS TRUE)
  GET_TARGET_PROPERTY(mysqld_link_flags sqlparser LINK_FLAGS)
  IF(NOT mysqld_link_flags)
    SET(mysqld_link_flags)
  ENDIF()
  IF (MINGW OR CYGWIN)
    SET_TARGET_PROPERTIES(sqlparser PROPERTIES LINK_FLAGS "${mysqld_link_flags} -Wl,--export-all-symbols")
  ENDIF()
  IF(MSVC)
    # Set module definition file. Also use non-incremental linker, 
    # incremental appears to crash from time to time,if used with /DEF option
    SET_TARGET_PROPERTIES(sqlparser PROPERTIES LINK_FLAGS "${mysqld_link_flags} /DEF:sqlparser.def /INCREMENTAL:NO")

    FOREACH (CORELIB sqlparser mysys strings)
      GET_TARGET_PROPERTY(LOC ${CORELIB} LOCATION)
      FILE(TO_NATIVE_PATH ${LOC} LOC)
      SET (LIB_LOCATIONS ${LIB_LOCATIONS} ${LOC}) 
    ENDFOREACH (CORELIB ${MYSQLD_CORE_LIBS})
    SET(_PLATFORM x86)
    IF(CMAKE_SIZEOF_VOID_P EQUAL 8)
      SET(_PLATFORM  x64)
    ENDIF()
    ADD_CUSTOM_COMMAND(TARGET sqlparser PRE_LINK
      COMMAND echo ${_PLATFORM} && cscript ARGS //nologo ${PROJECT_SOURCE_DIR}/win/create_def_file.js
                  ${_PLATFORM}  ${LIB_LOCATIONS} > sqlparser.def 
      WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
    ADD_DEPENDENCIES(sqlparser GenError)
  ENDIF()
ENDIF()

SET_TARGET_PROPERTIES(sqlparser PROPERTIES ENABLE_EXPORTS TRUE) 
TARGET_LINK_LIBRARIES(sqlparser mysys mysys_ssl)

# Provide plugins with minimal set of libraries
SET(INTERFACE_LIBS ${LIBRT})
IF(INTERFACE_LIBS)
 SET_TARGET_PROPERTIES(sqlparser PROPERTIES LINK_INTERFACE_LIBRARIES 
  "${INTERFACE_LIBS}")
ENDIF()

# On Solaris, some extra effort is required in order to get dtrace probes
# from static libraries
DTRACE_INSTRUMENT_STATIC_LIBS(sqlparser 
 "mysys;mysys_ssl;${MYSQLD_STATIC_PLUGIN_LIBS}")
 

SET(WITH_MYSQLD_LDFLAGS "" CACHE STRING "Additional linker flags for sqlparser")
MARK_AS_ADVANCED(WITH_MYSQLD_LDFLAGS)
IF(WITH_MYSQLD_LDFLAGS)
  GET_TARGET_PROPERTY(sqlparser LINK_FLAGS MYSQLD_LINK_FLAGS)
  IF(NOT MYSQLD_LINK_FLAGS)
    SET(MYSQLD_LINK_FLAGS) 
  ENDIF() 
  SET_TARGET_PROPERTIES(sqlparser PROPERTIES LINK_FLAGS 
     "${MYSQLD_LINK_FLAGS} ${WITH_MYSQLD_LDFLAGS}")
ENDIF()

MYSQL_INSTALL_TARGETS(sqlparser DESTINATION ${INSTALL_LIBDIR} COMPONENT Server)

file(GLOB SQL_HEADERS *.h)
INSTALL(FILES ${SQL_HEADERS} DESTINATION ${INSTALL_INCLUDEDIR}/sql COMPONENT Development)

IF(DEBUG_EXTNAME)
  INSTALL_DEBUG_TARGET(sqlparser 
    DESTINATION ${INSTALL_SBINDIR} 
    PDB_DESTINATION ${INSTALL_SBINDIR}
    SUFFIX "-debug")
ELSE()
  INSTALL_DEBUG_TARGET(sqlparser 
    DESTINATION ${INSTALL_SBINDIR} 
    PDB_DESTINATION ${INSTALL_SBINDIR}/debug
    RENAME sqlparser-debug)
ENDIF()

# Handle out-of-source build from source package with possibly broken 
# bison. Copy bison output to from source to build directory, if not already 
# there
IF (NOT ${CMAKE_CURRENT_SOURCE_DIR} STREQUAL ${CMAKE_CURRENT_BINARY_DIR})
  IF(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/sql_yacc.cc)
    IF(NOT EXISTS ${CMAKE_CURRENT_BINARY_DIR}/sql_yacc.cc)
      CONFIGURE_FILE(${CMAKE_CURRENT_SOURCE_DIR}/sql_yacc.cc 
        ${CMAKE_CURRENT_BINARY_DIR}/sql_yacc.cc COPYONLY)
      CONFIGURE_FILE(${CMAKE_CURRENT_SOURCE_DIR}/sql_yacc.h
        ${CMAKE_CURRENT_BINARY_DIR}/sql_yacc.h COPYONLY)
    ENDIF()
  ENDIF()
ENDIF()


INCLUDE(${CMAKE_SOURCE_DIR}/cmake/bison.cmake)
RUN_BISON(
  ${CMAKE_CURRENT_SOURCE_DIR}/sql_yacc.yy 
  ${CMAKE_CURRENT_BINARY_DIR}/sql_yacc.cc
  ${CMAKE_CURRENT_BINARY_DIR}/sql_yacc.h
)

# Gen_lex_hash
ADD_EXECUTABLE(gen_lex_hash gen_lex_hash.cc)

ADD_CUSTOM_COMMAND(
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/lex_hash.h
  COMMAND gen_lex_hash > lex_hash.h
  DEPENDS gen_lex_hash
)


ADD_CUSTOM_TARGET( 
        GenServerSource
        DEPENDS ${GEN_SOURCES}
)

#Need this only for embedded
SET_TARGET_PROPERTIES(GenServerSource PROPERTIES EXCLUDE_FROM_ALL TRUE)


FOREACH(tool glibtoolize libtoolize aclocal autoconf autoheader automake gtar 
 tar git)
 STRING(TOUPPER ${tool}  TOOL)
 FIND_PROGRAM(${TOOL}_EXECUTABLE ${tool} DOC "path to the executable")
 MARK_AS_ADVANCED(${TOOL}_EXECUTABLE)
ENDFOREACH()

CONFIGURE_FILE(
  ${CMAKE_SOURCE_DIR}/cmake/make_dist.cmake.in
  ${CMAKE_BINARY_DIR}/make_dist.cmake @ONLY)

ADD_CUSTOM_TARGET(dist 
  COMMAND ${CMAKE_COMMAND} -P ${CMAKE_BINARY_DIR}/make_dist.cmake
  DEPENDS ${CMAKE_BINARY_DIR}/sql/sql_yacc.cc ${CMAKE_BINARY_DIR}/sql/sql_yacc.h
  WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
)

ADD_CUSTOM_TARGET(distclean
  COMMAND ${CMAKE_COMMAND} -E echo  WARNING: distclean target is not functional
  COMMAND ${CMAKE_COMMAND} -E echo  Use 'git clean -fdx' instead
  VERBATIM
  )


ADD_CUSTOM_TARGET(show-dist-name
  COMMAND ${CMAKE_COMMAND} -E echo "${CPACK_PACKAGE_FILE_NAME}"
)

