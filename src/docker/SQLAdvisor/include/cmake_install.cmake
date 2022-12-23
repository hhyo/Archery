# Install script for directory: /home/longxuegang/dba_public_scripts_tools/sqlparser/include

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

IF(NOT CMAKE_INSTALL_COMPONENT OR "${CMAKE_INSTALL_COMPONENT}" STREQUAL "Development")
  FILE(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include" TYPE FILE FILES
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_pthread.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_stacktrace.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/byte_order_generic_x86_64.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/password.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/sql_common.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_aes.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/waiting_threads.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/mysqld_ername.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/t_ctype.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/thr_alarm.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/ft_global.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/sql_state.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_atomic.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/byte_order_generic.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_tree.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_timer.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_sys.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_rdtsc.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_check_opt.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/sslopt-case.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_compare.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/decimal.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_xml.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/config.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_compiler.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/m_ctype.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/mysql.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_bitmap.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_rnd.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_byteorder.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/thr_lock.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/probes_mysql.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/queues.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/base64.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/typelib.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_bit.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_net.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/heap.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/errmsg.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_libwrap.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/myisampack.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/welcome_copyright_notice.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_murmur3.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/sha2.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/mysql_com.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/lf.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/mysqld_error.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_nosys.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_md5.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/sha1.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/mysql_version.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/violite.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/big_endian.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_global.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_getopt.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/byte_order_generic_x86.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_attribute.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_uctype.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_default.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/sslopt-vars.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/hash.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_user.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/sslopt-longopts.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_dir.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/mysys_err.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/service_versions.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/probes_mysql_nodtrace.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_base.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/mysql_time.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_dbug.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/crypt_genhash_impl.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/m_string.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_alarm.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_config.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_list.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/little_endian.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/mysql_embed.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/mysql_com_server.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_alloc.h"
    "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/my_time.h"
    )
ENDIF(NOT CMAKE_INSTALL_COMPONENT OR "${CMAKE_INSTALL_COMPONENT}" STREQUAL "Development")

IF(NOT CMAKE_INSTALL_COMPONENT OR "${CMAKE_INSTALL_COMPONENT}" STREQUAL "Development")
  FILE(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include/mysql" TYPE DIRECTORY FILES "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/mysql/" REGEX "/[^/]*\\.h$" REGEX "/psi\\_abi[^/]*$" EXCLUDE)
ENDIF(NOT CMAKE_INSTALL_COMPONENT OR "${CMAKE_INSTALL_COMPONENT}" STREQUAL "Development")

IF(NOT CMAKE_INSTALL_COMPONENT OR "${CMAKE_INSTALL_COMPONENT}" STREQUAL "Development")
  FILE(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include/atomic" TYPE DIRECTORY FILES "/home/longxuegang/dba_public_scripts_tools/sqlparser/include/atomic/" REGEX "/[^/]*\\.h$")
ENDIF(NOT CMAKE_INSTALL_COMPONENT OR "${CMAKE_INSTALL_COMPONENT}" STREQUAL "Development")

