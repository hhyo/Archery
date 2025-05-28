//-----------------------------------------------------------------------------
// File:            DPIext.h
//
// Copyright:       Copyright (c) DM Corporation          
//
// Contents:        This is the include for applications using the DM SQL Extensions
//
// Comments:
//
//-----------------------------------------------------------------------------
#ifndef _DPIEXT_H
#define _DPIEXT_H

#ifndef _DPI_H
#include "DPI.h"
#endif

#ifdef __cplusplus
extern "C" {                         /* Assume C declarations for C++ */
#endif  /* __cplusplus */

/* env attribute and con attribute*/
#define DSQL_ATTR_LOCAL_CODE                12345
#define DSQL_ATTR_LANG_ID                   12346
#define DSQL_ATTR_CONNECTION_POOLING        12347
#define DSQL_ATTR_TIME_ZONE                 12348
#define DSQL_ATTR_CON_CACHE_SZ              12349
#define DSQL_ATTR_DEC2DOUB_CNVT             12350
#define DSQL_ATTR_CHAR_CHECK                12351
#define DSQL_ATTR_CHAR_TRUNC                12352
#define DSQL_ATTR_FNUM2CHAR_MODE            12353

/*DSQL_ATTR_FNUM2CHAR_MODE options*/
#define DSQL_FNUM2CHAR_MODE_0               0
#define DSQL_FNUM2CHAR_MODE_1               1

/* values for DSQL_ATTR_LOCAL_CODE */
#define  PG_UTF8                            1
#define  PG_GBK                             2
#define  PG_BIG5                            3
#define  PG_ISO_8859_9                      4
#define  PG_EUC_JP                          5
#define  PG_EUC_KR                          6
#define  PG_KOI8R                           7
#define  PG_ISO_8859_1                      8
#define  PG_SQL_ASCII                       9
#define  PG_GB18030                         10
#define  PG_ISO_8859_11                     11
    
/* values for DSQL_ATTR_LANG_ID */
#define LANGUAGE_CN                         0
#define LANGUAGE_EN                         1
#define LANGUAGE_CNT_HK                     2

/* default value*/
#define DSQL_DEAFAULT_TCPIP_PORT            5236

/* connection attributes */
#define DSQL_ATTR_ACCESS_MODE               101
#define DSQL_ATTR_AUTOCOMMIT                102
#define DSQL_ATTR_CONNECTION_TIMEOUT        113
#define DSQL_ATTR_LOGIN_TIMEOUT             103
#define DSQL_ATTR_PACKET_SIZE               112
#define DSQL_ATTR_TRACE                     104
#define DSQL_ATTR_TRACEFILE                 105
#define DSQL_ATTR_TXN_ISOLATION             108
#define DSQL_ATTR_CURRENT_CATALOG           109
#define DSQL_ATTR_CONNECTION_DEAD           1209
#define DSQL_ATTR_LOGIN_PORT                12350
#define DSQL_ATTR_STR_CASE_SENSITIVE        12351
#define DSQL_ATTR_LOGIN_USER                12352
#define DSQL_ATTR_MAX_ROW_SIZE              12353
#define DSQL_ATTR_CURRENT_SCHEMA            12354
#define DSQL_ATTR_INSTANCE_NAME             12355
#define DSQL_ATTR_LOGIN_SERVER              12356
#define DSQL_ATTR_SERVER_CODE               12349
#define DSQL_ATTR_APP_NAME                  12357
#define DSQL_ATTR_COMPRESS_MSG              12358
#define DSQL_ATTR_USE_STMT_POOL             12359
#define DSQL_ATTR_SERVER_MODE               12360
#define DSQL_ATTR_SERVER_VERSION            12400
#define DSQL_ATTR_SSL_PATH                  12401
#define DSQL_ATTR_SSL_PWD                   12402
#define DSQL_ATTR_MPP_LOGIN                 12403
#define DSQL_ATTR_TRX_STATE                 12404
//ukey-begin
#define DSQL_ATTR_UKEY_NAME                 12405
#define DSQL_ATTR_UKEY_PIN                  12406
//ukey-end
#define DSQL_ATTR_CLIENT_VERSION            12407
#define DSQL_ATTR_RWSEPARATE                12408
#define DSQL_ATTR_RWSEPARATE_PERCENT        12409
#define DSQL_ATTR_CURSOR_ROLLBACK_BEHAVIOR  12410
#define DSQL_ATTR_UDP_FLAG                  12411
#define DSQL_ATTR_OSAUTH_TYPE               12412
#define DSQL_ATTR_INET_TYPE                 12413
#define DSQL_ATTR_DDL_AUTOCOMMIT            12414
#define DSQL_ATTR_LOGIN_CERTIFICATE         12415
#define DSQL_ATTR_LAST_LOGIN_IP             12416
#define DSQL_ATTR_LAST_LOGIN_DT             12417
#define DSQL_ATTR_FAILED_LOGIN_ATTEMPT      12418
#define DSQL_ATTR_PASSWORD_GRACE_TIME       12419
#define DSQL_ATTR_PASSWORD_LIFE_REMAINING   12420
#define DSQL_ATTR_LICENSE_SERIAL            12421
#define DSQL_ATTR_SPACE_TRUNC               12422
#define DSQL_ATTR_ORA_DATE_FMT              12423       //oracle_date_fmt info
#define DSQL_ATTR_COMPATIBLE_MODE           12424
#define DSQL_ATTR_TCNAME_LOWER              12425
#define DSQL_ATTR_SHAKE_CRYPTO              12426
#define DSQL_ATTR_QUOTE_REPLACE             12427
#define DSQL_ATTR_FE_MODE                   12428
#define DSQL_ATTR_PROXY_CLIENT              12429
#define DSQL_ATTR_NLS_NUMERIC_CHARACTERS    12430       // NLS_NUMERIC_CHARACTERS
#define DSQL_ATTR_DM_SVC_PATH               12431

/* DSQL_ATTR_COMPATIBLE_MODE options*/
#define DSQL_COMPATIBLE_MODE_DM             0UL
#define DSQL_COMPATIBLE_MODE_ORA            1UL

/* DSQL_ACCESS_MODE options */
#define DSQL_MODE_READ_WRITE                (0UL)
#define DSQL_MODE_READ_ONLY                 (1UL)
#define DSQL_MODE_DEFAULT                   DSQL_MODE_READ_WRITE

/* DSQL_AUTOCOMMIT options */
#define DSQL_AUTOCOMMIT_OFF                 0UL
#define DSQL_AUTOCOMMIT_ON                  1UL
#define DSQL_AUTOCOMMIT_DEFAULT             DSQL_AUTOCOMMIT_ON

#define DSQL_UDP_SINGLE                     1UL
#define DSQL_UDP_MULTI                      2UL
#define DSQL_UDP_DEFAULT                    DSQL_UDP_MULTI

#define DSQL_INET_TCP                       0UL
#define DSQL_INET_UDP                       1UL
#define DSQL_INET_IPC                       2UL
#define DSQL_INET_RDMA                      3UL
#define DSQL_INET_UNIXSOCKET                4UL    //UNIXSOCKET
#define DSQL_INET_DEFAULT                   DSQL_INET_TCP

#define DSQL_RWSEPARATE_OFF                 0UL
#define DSQL_RWSEPARATE_ON                  1UL
#define DSQL_RWSEPARATE_ON2                 4UL
#define DSQL_RWSEPARAT_DEFAULT              DSQL_RWSEPARATE_OFF

/* DSQL_OPT_TRACE options */
#define DSQL_OPT_TRACE_OFF                  0UL
#define DSQL_OPT_TRACE_ON                   1UL
#define DSQL_OPT_TRACE_DEFAULT              DSQL_OPT_TRACE_OFF
#define DSQL_OPT_TRACE_FILE_DEFAULT         "\\DPI.LOG"

/*DSQL_MPP_LOGIN options*/
#define DSQL_MPP_LOGIN_GLOBAL               0
#define DSQL_MPP_LOGIN_LOCAL                1
#define DSQL_MPP_LOGIN_DEFAULT              DSQL_MPP_LOGIN_GLOBAL

/*DSQL_TRX_STATE options*/
#define DSQL_TRX_COMPLETE                   0
#define DSQL_TRX_ACTIVE                     1

/*DSQL_ATTR_CURSOR_ROLLBACK_BEHAVIOR option*/
#define DSQL_CB_CLOSE                       1
#define DSQL_CB_PRESERVE                    2
#define DSQL_CB_DEFALUT                     DSQL_CB_PRESERVE

/* values for DSQL_ATTR_CONNECTION_DEAD */
#define DSQL_CD_TRUE                        1L      /* Connection is closed/dead */
#define DSQL_CD_FALSE                       0L      /* Connection is open/available */

/*DSQL_ATTR_OSAUTH_TYPE option*/
#define DSQL_OSAUTH_OFF                     0
#define DSQL_OSAUTH_DBA                     1
#define DSQL_OSAUTH_SSO                     2
#define DSQL_OSAUTH_AUDITOR                 3
#define DSQL_OSAUTH_AUTOMATCH               4
#define DSQL_OSAUTH_USERS                   5
#define DSQL_OSAUTH_DEFAULT                 DSQL_OSAUTH_OFF

/* values for DSQL_ATTR_LICENSE_SERIAL */
#define DSQL_PERSONAL_SERIES                1
#define DSQL_STANDARD_SERIES                2
#define DSQL_ENTERPRISE_SERIES              3
#define DSQL_CLOUD_SERIES                   4
#define DSQL_SECURITY_SERIES                5
#define DSQL_TRUSTED_SERIES                 6
#define DSQL_DEVELOP_SERIES                 7

/* statement attributes */
#define DSQL_ATTR_ASYNC_ENABLE              4
#define DSQL_ATTR_CONCURRENCY               7
#define DSQL_ATTR_CURSOR_TYPE               6
#define	DSQL_ATTR_ENABLE_AUTO_IPD           15
#define DSQL_ATTR_FETCH_BOOKMARK_PTR        16
#define DSQL_ATTR_KEYSET_SIZE               8
#define DSQL_ATTR_MAX_LENGTH                3
#define DSQL_ATTR_MAX_ROWS                  1
#define DSQL_ATTR_NOSCAN                    2
#define DSQL_ATTR_PARAM_BIND_OFFSET_PTR     17
#define	DSQL_ATTR_PARAM_BIND_TYPE           18
#define DSQL_ATTR_PARAM_OPERATION_PTR       19
#define DSQL_ATTR_PARAM_STATUS_PTR          20
#define	DSQL_ATTR_PARAMS_PROCESSED_PTR      21
#define	DSQL_ATTR_PARAMSET_SIZE             22
#define DSQL_ATTR_QUERY_TIMEOUT             0
#define DSQL_ATTR_RETRIEVE_DATA             11
#define DSQL_ATTR_ROW_BIND_OFFSET_PTR       23
#define	DSQL_ATTR_ROW_BIND_TYPE             5
#define DSQL_ATTR_ROW_NUMBER                14      /*GetStmtAttr*/
#define DSQL_ATTR_ROW_OPERATION_PTR         24
#define	DSQL_ATTR_ROW_STATUS_PTR            25
#define	DSQL_ATTR_ROWS_FETCHED_PTR          26
#define DSQL_ATTR_ROW_ARRAY_SIZE            27
#define DSQL_ATTR_SIMULATE_CURSOR           10
#define DSQL_ATTR_USE_BOOKMARKS             12
#define DSQL_ATTR_ROWSET_SIZE               9

/* COMPLEX TYPE ATTRIBUTE*/
#define DSQL_ATTR_OBJ_TYPE                  1
#define DSQL_ATTR_OBJ_PREC                  2
#define DSQL_ATTR_OBJ_SCALE                 3
#define DSQL_ATTR_OBJ_DESC                  4
#define DSQL_ATTR_OBJ_FIELD_COUNT           5
#define DSQL_ATTR_OBJ_NAME                  6
#define DSQL_ATTR_OBJ_SCHAME                7
#define DSQL_ATTR_OBJ_KEY_TYPE              8    // get index table key_type

/* COMPLEX OBJ ATTRIBUTE*/
#define DSQL_ATTR_OBJ_VAL_COUNT             1

/* the value of DSQL_ATTR_PARAM_BIND_TYPE */
#define DSQL_PARAM_BIND_BY_COLUMN           0UL
#define DSQL_PARAM_BIND_TYPE_DEFAULT        DSQL_PARAM_BIND_BY_COLUMN

/* DSQL_BIND_TYPE options */
#define DSQL_BIND_BY_COLUMN             0UL
#define DSQL_BIND_TYPE_DEFAULT          SQL_BIND_BY_COLUMN  /* Default value */

/* DSQL_CONCURRENCY options */
#define DSQL_CONCUR_READ_ONLY            1
#define DSQL_CONCUR_LOCK                 2
#define DSQL_CONCUR_ROWVER               3
#define DSQL_CONCUR_VALUES               4
#define DSQL_CONCUR_DEFAULT              DSQL_CONCUR_READ_ONLY /* Default value */

/* DSQL_CURSOR_TYPE options */
#define DSQL_CURSOR_FORWARD_ONLY         0UL
#define DSQL_CURSOR_KEYSET_DRIVEN        1UL
#define DSQL_CURSOR_DYNAMIC              2UL
#define DSQL_CURSOR_STATIC               3UL
#define DSQL_CURSOR_TYPE_DEFAULT         DSQL_CURSOR_FORWARD_ONLY /* Default value */

/* DSQL_RETRIEVE_DATA options */
#define DSQL_RD_OFF                      0UL
#define DSQL_RD_ON                       1UL
#define DSQL_RD_DEFAULT                  DSQL_RD_ON

#define DSQL_NOSCAN_OFF                  0UL
#define DSQL_NOSCAN_ON                   1UL
#define DSQL_NOSCAN_DEFAULT              DSQL_NOSCAN_OFF

/* DSQL_USE_BOOKMARKS options */
#define DSQL_UB_OFF                     0UL
#define DSQL_UB_ON                      01UL
#define DSQL_UB_VARIABLE                2UL
#define DSQL_UB_DEFAULT                 DSQL_UB_OFF

/* extended descriptor field */
#define DSQL_DESC_ARRAY_SIZE                    20
#define DSQL_DESC_ARRAY_STATUS_PTR              21
#define DSQL_DESC_AUTO_UNIQUE_VALUE             DSQL_COLUMN_AUTO_INCREMENT
#define DSQL_DESC_BASE_COLUMN_NAME              22
#define DSQL_DESC_BASE_TABLE_NAME               23
#define DSQL_DESC_BIND_OFFSET_PTR               24
#define DSQL_DESC_BIND_TYPE                     25
#define DSQL_DESC_CASE_SENSITIVE                DSQL_COLUMN_CASE_SENSITIVE
#define DSQL_DESC_CATALOG_NAME                  DSQL_COLUMN_QUALIFIER_NAME
#define DSQL_DESC_CONCISE_TYPE                  DSQL_COLUMN_TYPE
#define DSQL_DESC_DATETIME_INTERVAL_PRECISION   26
#define DSQL_DESC_DISPLAY_SIZE                  DSQL_COLUMN_DISPLAY_SIZE
#define DSQL_DESC_FIXED_PREC_SCALE              DSQL_COLUMN_MONEY
#define DSQL_DESC_LABEL                         DSQL_COLUMN_LABEL
#define DSQL_DESC_LITERAL_PREFIX                27
#define DSQL_DESC_LITERAL_SUFFIX                28
#define DSQL_DESC_LOCAL_TYPE_NAME               29
#define	DSQL_DESC_MAXIMUM_SCALE                 30
#define DSQL_DESC_MINIMUM_SCALE                 31
#define DSQL_DESC_NUM_PREC_RADIX                32
#define DSQL_DESC_PARAMETER_TYPE                33          //the server in out type
#define DSQL_DESC_ROWS_PROCESSED_PTR            34
#define DSQL_DESC_ROWVER                        35
#define DSQL_DESC_SCHEMA_NAME                   DSQL_COLUMN_OWNER_NAME
#define DSQL_DESC_SEARCHABLE                    DSQL_COLUMN_SEARCHABLE
#define DSQL_DESC_TYPE_NAME                     DSQL_COLUMN_TYPE_NAME
#define DSQL_DESC_TABLE_NAME                    DSQL_COLUMN_TABLE_NAME
#define DSQL_DESC_UNSIGNED                      DSQL_COLUMN_UNSIGNED
#define DSQL_DESC_UPDATABLE                     DSQL_COLUMN_UPDATABLE
#define DSQL_DESC_DATETIME_FORMAT               1000
#define DSQL_DESC_OBJ_DESCRIPTOR                10001
#define DSQL_DESC_CHARSET                       10002
#define DSQL_DESC_BIND_PARAMETER_TYPE           10003       //the bind in out type,in default
#define DSQL_DESC_IND_BIND_TYPE                 10004
#define DSQL_DESC_OBJ_CLASSID                   10005
#define DSQL_DESC_FENC                          10006
#define DSQL_DESC_PARAM_AFFECT_ROWS_PTR         10007
#define DSQL_DESC_CHAR_FLAG                     10008
#define DSQL_DESC_CHAR_SIZE                     10009
#define DSQL_DESC_DATETIME_TZ_FORMAT            10010
#define DSQL_DESC_PARAM_ROWS_IS_NULL_PTR        10011

#define DSQL_DESC_OBJ_DESCRIPTOR2               30001

#define DSQL_DT                         50
#define DSQL_INTERVAL                   51
/* DSQL date/time type subcodes */
#define DSQL_CODE_DATE                  1
#define DSQL_CODE_TIME                  2
#define DSQL_CODE_TIMESTAMP             3
/* DSQL interval type subcodes */
#define DSQL_CODE_YEAR                  1
#define DSQL_CODE_MONTH                 2
#define DSQL_CODE_DAY                   3
#define DSQL_CODE_HOUR                  4
#define DSQL_CODE_MINUTE                5
#define DSQL_CODE_SECOND                6
#define DSQL_CODE_YEAR_TO_MONTH         7
#define DSQL_CODE_DAY_TO_HOUR           8
#define DSQL_CODE_DAY_TO_MINUTE         9
#define DSQL_CODE_DAY_TO_SECOND         10
#define DSQL_CODE_HOUR_TO_MINUTE        11
#define DSQL_CODE_HOUR_TO_SECOND        12
#define DSQL_CODE_MINUTE_TO_SECOND      13

/* define for SQL_DIAG_ROW_NUMBER and SQL_DIAG_COLUMN_NUMBER */
#define DSQL_NO_ROW_NUMBER                      (-1)
#define DSQL_NO_COLUMN_NUMBER                   (-1)
#define DSQL_ROW_NUMBER_UNKNOWN                 (-2)
#define DSQL_COLUMN_NUMBER_UNKNOWN              (-2)

#define DSQL_LEN_DATA_AT_EXEC_OFFSET  (-100)
#define DSQL_LEN_DATA_AT_EXEC(length) (-(length)+DSQL_LEN_DATA_AT_EXEC_OFFSET)

/* dpi_col_attr defines */
#define DSQL_COLUMN_COUNT                0
#define DSQL_COLUMN_NAME                 1
#define DSQL_COLUMN_TYPE                 2
#define DSQL_COLUMN_LENGTH               3
#define DSQL_COLUMN_PRECISION            4
#define DSQL_COLUMN_SCALE                5
#define DSQL_COLUMN_DISPLAY_SIZE         6
#define DSQL_COLUMN_NULLABLE             7
#define DSQL_COLUMN_UNSIGNED             8
#define DSQL_COLUMN_MONEY                9
#define DSQL_COLUMN_UPDATABLE            10
#define DSQL_COLUMN_AUTO_INCREMENT       11
#define DSQL_COLUMN_CASE_SENSITIVE       12
#define DSQL_COLUMN_SEARCHABLE           13
#define DSQL_COLUMN_TYPE_NAME            14
#define DSQL_COLUMN_TABLE_NAME           15
#define DSQL_COLUMN_OWNER_NAME           16
#define DSQL_COLUMN_QUALIFIER_NAME       17
#define DSQL_COLUMN_LABEL                18
#define DSQL_COLATT_OPT_MAX              DSQL_COLUMN_LABEL

/* dpi_col_attr subdefines for DSQL_COLUMN_UPDATABLE */
#define DSQL_ATTR_READONLY               0
#define DSQL_ATTR_WRITE                  1
#define DSQL_ATTR_READWRITE_UNKNOWN      2

/* Operations in dpi_set_pos */
#define DSQL_POSITION                   0
#define DSQL_REFRESH                    1
#define DSQL_UPDATE                     2
#define DSQL_DELETE                     3

/* Operations in dpi_bulk_operation */
#define DSQL_ADD                        4
#define DSQL_SETPOS_MAX_OPTION_VALUE    DSQL_ADD

#define DSQL_UPDATE_BY_BOOKMARK         5
#define DSQL_DELETE_BY_BOOKMARK         6
#define DSQL_FETCH_BY_BOOKMARK          7

/* Lock options in dpi_set_pos */
#define DSQL_LOCK_NO_CHANGE             0
#define DSQL_LOCK_EXCLUSIVE             1
#define DSQL_LOCK_UNLOCK                2

#define DSQL_SETPOS_MAX_LOCK_VALUE      DSQL_LOCK_UNLOCK

#define DSQL_ROW_SUCCESS                0
#define DSQL_ROW_DELETED                1
#define DSQL_ROW_UPDATED                2
#define DSQL_ROW_NOROW                  3
#define DSQL_ROW_ADDED                  4
#define DSQL_ROW_ERROR                  5
#define DSQL_ROW_SUCCESS_WITH_INFO      6

/*Row operation values*/
#define DSQL_ROW_PROCEED                0
#define DSQL_ROW_IGNORE                 1

/* value for DSQL_DESC_ARRAY_STATUS_PTR */
#define DSQL_PARAM_SUCCESS              0
#define DSQL_PARAM_SUCCESS_WITH_INFO    6
#define DSQL_PARAM_ERROR                5
#define DSQL_PARAM_UNUSED               7
#define DSQL_PARAM_DIAG_UNAVAILABLE     1

#define DSQL_PARAM_PROCEED              0
#define DSQL_PARAM_IGNORE               1

/* Defines for dpi_bind_param */
#define DSQL_PARAM_TYPE_UNKNOWN             0
#define DSQL_PARAM_INPUT                    1
#define DSQL_PARAM_INPUT_OUTPUT             2
#define DSQL_PARAM_OUTPUT                   4
#define DSQL_PARAM_INPUT_OUTPUT_STREAM      8
#define DSQL_PARAM_OUTPUT_STREAM            16

#ifdef __cplusplus
}                                     /* End of extern "C" { */
#endif  /* __cplusplus */

#endif /* _DPIEXT_H */
