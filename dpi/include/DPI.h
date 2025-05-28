//-----------------------------------------------------------------------------
// File:            DPI.h
//
// Contents:        This is the the main include for DM API programing.
//
// Comments:        preconditions: NONE
//
//-----------------------------------------------------------------------------

#ifndef _DPI_H
#define _DPI_H

/*
* DPIVER  DPI version number (0x0101).
*/
#ifndef DPIVER
#define DPIVER 0x0101
#endif

#ifndef __DPITYPES
#include "DPItypes.h"
#endif

#ifdef __cplusplus
extern "C" {            /* Assume C declarations for C++   */
#endif  /* __cplusplus */

#if defined (_WINDOWS) || defined (WIN32)
#ifndef DllImport
#define DllImport   __declspec( dllimport )
#endif

#ifndef DllExport
#define DllExport   __declspec( dllexport )
#endif
#else
#define DllImport
#define DllExport
#endif

/* special length/indicator values */
#define DSQL_NULL_DATA                      (-1)
#define DSQL_DATA_AT_EXEC                   (-2)
#define DSQL_DEFAULT_PARAM                  (-5)
#define DSQL_COLUMN_IGNORE                  (-6)

/* return values from functions */
#define DSQL_SUCCESS                        0
#define DSQL_SUCCESS_WITH_INFO              1
#define DSQL_NO_DATA                        100
#define DSQL_ERROR                          (-1)
#define DSQL_INVALID_HANDLE                 (-2)

#define DSQL_STILL_EXECUTING                2
#define DSQL_NEED_DATA                      99
#define DSQL_PARAM_DATA_AVAILABLE           101

/* defines for diagnostics fields */
/* diagnose head field identifier */
#define DSQL_DIAG_NUMBER                    (1)
#define DSQL_DIAG_DYNAMIC_FUNCTION_CODE     (2)
#define DSQL_DIAG_ROW_COUNT                 (3)
#define DSQL_DIAG_PRINT_INFO                (4)
#define DSQL_DIAG_EXPLAIN                   (5)
#define DSQL_DIAG_ROWID                     (6)
#define DSQL_DIAG_EXECID                    (7)
#define DSQL_DIAG_SERVER_STAT               (8)

/* diagnose record field identifier*/
#define DSQL_DIAG_COLUMN_NUMBER             (101)
#define DSQL_DIAG_MESSAGE_TEXT              (102)
#define DSQL_DIAG_ERROR_CODE                (103)
#define DSQL_DIAG_ROW_NUMBER                (104)

//If dpi_row_count or diagnose cannot return exactly row count
#define DSQL_ROW_COUNT_UNKNOWN              (-99)

/* test for SQL_SUCCESS or SQL_SUCCESS_WITH_INFO */
#define DSQL_SUCCEEDED(rc)                  (((rc)&(~1))==0)

/* flags for null-terminated string */
#define DSQL_NTS                            (-3)
#define DSQL_NTSL                           (-3L)

/* handle type identifiers */
#define DSQL_HANDLE_ENV                     1
#define DSQL_HANDLE_DBC                     2
#define DSQL_HANDLE_STMT                    3
#define DSQL_HANDLE_DESC                    4
#define DSQL_HANDLE_LOB_LOCATOR             5
#define DSQL_HANDLE_OBJECT                  6
#define DSQL_HANDLE_OBJDESC                 7
#define DSQL_HANDLE_BFILE                   8

//DM C TYPE DEFINE
#define DSQL_C_TYPE_INVALID                 (-1000)
#define DSQL_C_NCHAR                        0           //with NULL terminate
#define DSQL_C_SSHORT                       1
#define DSQL_C_USHORT                       2
#define DSQL_C_SLONG                        3
#define DSQL_C_ULONG                        4
#define DSQL_C_FLOAT                        5
#define DSQL_C_DOUBLE                       6
#define DSQL_C_BIT                          7
#define DSQL_C_STINYINT                     8
#define DSQL_C_UTINYINT                     9
#define DSQL_C_SBIGINT                      10
#define DSQL_C_UBIGINT                      11
#define DSQL_C_BINARY                       12
#define DSQL_C_DATE                         13
#define DSQL_C_TIME                         14
#define DSQL_C_TIMESTAMP                    15
#define DSQL_C_NUMERIC                      16
#define DSQL_C_INTERVAL_YEAR                17
#define DSQL_C_INTERVAL_MONTH               18
#define DSQL_C_INTERVAL_DAY                 19
#define DSQL_C_INTERVAL_HOUR                20
#define DSQL_C_INTERVAL_MINUTE              21
#define DSQL_C_INTERVAL_SECOND              22
#define DSQL_C_INTERVAL_YEAR_TO_MONTH       23
#define DSQL_C_INTERVAL_DAY_TO_HOUR         24
#define DSQL_C_INTERVAL_DAY_TO_MINUTE       25
#define DSQL_C_INTERVAL_DAY_TO_SECOND       26
#define DSQL_C_INTERVAL_HOUR_TO_MINUTE      27
#define DSQL_C_INTERVAL_HOUR_TO_SECOND      28
#define DSQL_C_INTERVAL_MINUTE_TO_SECOND    29
#define DSQL_C_DEFAULT                      30
#define DSQL_C_CLASS                        31
#define DSQL_C_RECORD                       32
#define DSQL_C_ARRAY                        33
#define DSQL_C_SARRAY                       34
#define DSQL_C_LOB_HANDLE                   999
#define DSQL_C_RSET                         1000
#define DSQL_C_WCHAR                        1001
#define DSQL_C_BFILE                        1002
#define DSQL_C_CHAR                         1003        //without NULL terminate
#define DSQL_C_BOOLEAN                      DSQL_C_SLONG

#ifdef DM64
#define DSQL_C_BOOKMARK                     DSQL_C_UBIGINT
#else
#define DSQL_C_BOOKMARK                     DSQL_C_ULONG
#endif
#define DSQL_C_VARBOOKMARK                  DSQL_C_BINARY

#define DSQL_IS_CTYPE_INTERVAL(type)        (DSQL_C_INTERVAL_YEAR <= (type) && (type) <= DSQL_C_INTERVAL_MINUTE_TO_SECOND)
#define DSQL_IS_CTYPE_INTERVAL_YM(type)     (type == DSQL_C_INTERVAL_YEAR || type == DSQL_C_INTERVAL_MONTH || type == DSQL_C_INTERVAL_YEAR_TO_MONTH)
#define DSQL_IS_CTYPE_INTERVAL_DT(type)     (DSQL_IS_CTYPE_INTERVAL(type) && !DSQL_IS_TYPE_INTERVAL_YM(type))
#define DSQL_IS_CTYPE_DATETIME(type)        (DSQL_C_DATE <= type && type <= DSQL_C_TIMESTAMP)

//DM SERVER TYPE DEFINE
#define DSQL_CHAR                           1           /* CHAR     */
#define DSQL_VARCHAR                        2           /* VARCHAR  */
#define DSQL_BIT                            3           /* BIT STRING */
#define DSQL_TINYINT                        5           /* 1 byte INT */
#define DSQL_SMALLINT                       6           /* SMALL INTEGER, 2 bytes */
#define DSQL_INT                            7           /* INTEGER 4 bytes */
#define DSQL_BIGINT                         8           /* INTEGER 8 bytes */
#define DSQL_DEC                            9           /* DECIMAL */
#define DSQL_FLOAT                          10          /* FLOAT, SINGLE */
#define DSQL_DOUBLE                         11          /* DOUBLE */
#define DSQL_BLOB                           12          /* BINARY LARGE OBJECT */
#define DSQL_BOOLEAN                        13          /* BOOLEAN */
#define DSQL_DATE                           14          /* DATE*/
#define DSQL_TIME                           15          /* TIME*/
#define DSQL_TIMESTAMP                      16          /* DATE TIME */
#define DSQL_BINARY                         17          /* BINARY */
#define DSQL_VARBINARY                      18          /* VAR BINARY */
#define DSQL_CLOB                           19          /* TEXT */
#define DSQL_TIME_TZ                        22          /* TIME WITH TIME ZONE*/
#define DSQL_TIMESTAMP_TZ                   23          /* TIMESTAMP WITH TIME ZONE*/
#define DSQL_CLASS                          24
#define DSQL_RECORD                         25
#define DSQL_ARRAY                          26
#define DSQL_SARRAY                         27
#define DSQL_ROWID                          28          /* ROWID*/
#define DSQL_RSET                           119         /* RESULT SET*/
#define DSQL_BFILE                          1000        /* BFILE*/

#define DSQL_INTERVAL_TYPE_BASE             100
#define DSQL_INTERVAL_TYPE_END              112
#define DSQL_INTERVAL_YEAR                  DSQL_INTERVAL_TYPE_BASE
#define DSQL_INTERVAL_MONTH                 (DSQL_INTERVAL_TYPE_BASE + 1)
#define DSQL_INTERVAL_DAY                   (DSQL_INTERVAL_TYPE_BASE + 2)
#define DSQL_INTERVAL_HOUR                  (DSQL_INTERVAL_TYPE_BASE + 3)
#define DSQL_INTERVAL_MINUTE                (DSQL_INTERVAL_TYPE_BASE + 4)
#define DSQL_INTERVAL_SECOND                (DSQL_INTERVAL_TYPE_BASE + 5)
#define DSQL_INTERVAL_YEAR_TO_MONTH         (DSQL_INTERVAL_TYPE_BASE + 6)
#define DSQL_INTERVAL_DAY_TO_HOUR           (DSQL_INTERVAL_TYPE_BASE + 7)
#define DSQL_INTERVAL_DAY_TO_MINUTE         (DSQL_INTERVAL_TYPE_BASE + 8)
#define DSQL_INTERVAL_DAY_TO_SECOND         (DSQL_INTERVAL_TYPE_BASE + 9)
#define DSQL_INTERVAL_HOUR_TO_MINUTE        (DSQL_INTERVAL_TYPE_BASE + 10)
#define DSQL_INTERVAL_HOUR_TO_SECOND        (DSQL_INTERVAL_TYPE_BASE + 11)
#define DSQL_INTERVAL_MINUTE_TO_SECOND      (DSQL_INTERVAL_TYPE_BASE + 12)

#define DSQL_IS_TYPE_INTERVAL(type)         (DSQL_INTERVAL_TYPE_BASE <= (type) && (type) <= DSQL_INTERVAL_TYPE_END)
#define DSQL_IS_TYPE_INTERVAL_YM(type)      (type == DSQL_INTERVAL_YEAR || type == DSQL_INTERVAL_MONTH || type == DSQL_INTERVAL_YEAR_TO_MONTH)
#define DSQL_IS_TYPE_INTERVAL_DT(type)      (DSQL_IS_TYPE_INTERVAL(type) && !DSQL_IS_TYPE_INTERVAL_YM(type))
#define DSQL_IS_TYPE_DATETIME(type)         (DSQL_DATE <= type && type <= DSQL_TIMESTAMP)

//diagnose function code definition
#define DSQL_DIAG_FUNC_CODE_INVALID                     0
#define DSQL_DIAG_FUNC_CODE_SELECT                      1
#define DSQL_DIAG_FUNC_CODE_INSERT                      2
#define DSQL_DIAG_FUNC_CODE_DELETE                      3
#define DSQL_DIAG_FUNC_CODE_UPDATE                      4
#define DSQL_DIAG_FUNC_CODE_CREATE_DB                   5
#define DSQL_DIAG_FUNC_CODE_CREATE_TAB                  6
#define DSQL_DIAG_FUNC_CODE_DROP_TAB                    7
#define DSQL_DIAG_FUNC_CODE_CREATE_VIEW                 8
#define DSQL_DIAG_FUNC_CODE_DROP_VIEW                   9
#define DSQL_DIAG_FUNC_CODE_CREATE_INDEX                10
#define DSQL_DIAG_FUNC_CODE_DROP_INDEX                  11
#define DSQL_DIAG_FUNC_CODE_CREATE_USER                 12
#define DSQL_DIAG_FUNC_CODE_DROP_USER                   13
#define DSQL_DIAG_FUNC_CODE_CREATE_ROLE                 14
#define DSQL_DIAG_FUNC_CODE_DROP_ROLE                   15
#define DSQL_DIAG_FUNC_CODE_COMMIT                      16
#define DSQL_DIAG_FUNC_CODE_ROLLBACK                    17
#define DSQL_DIAG_FUNC_CODE_EXPLAIN                     18
#define DSQL_DIAG_FUNC_CODE_SET_TRX                     19
#define DSQL_DIAG_FUNC_CODE_SAVE_POINT                  20
#define DSQL_DIAG_FUNC_CODE_DROP                        21
#define DSQL_DIAG_FUNC_CODE_ALTER_DB                    22
#define DSQL_DIAG_FUNC_CODE_ALTER_USER                  23
#define DSQL_DIAG_FUNC_CODE_CREATE_FUNC                 24
#define DSQL_DIAG_FUNC_CODE_SET_CURRENT_DB              25
#define DSQL_DIAG_FUNC_CODE_GRANT                       26
#define DSQL_DIAG_FUNC_CODE_REVOKE                      27
#define DSQL_DIAG_FUNC_CODE_CALL                        28
#define DSQL_DIAG_FUNC_CODE_ALTER_TAB                   29
#define DSQL_DIAG_FUNC_CODE_CREATE_SCHEMA               30
#define DSQL_DIAG_FUNC_CODE_AUDIT                       31
#define DSQL_DIAG_FUNC_CODE_ALTER_TRIGGER               32
#define DSQL_DIAG_FUNC_CODE_SELECT_INTO                 33
#define DSQL_DIAG_FUNC_CODE_FETCH                       34
#define DSQL_DIAG_FUNC_CODE_CLOSE_CURSOR                35
#define DSQL_DIAG_FUNC_CODE_TRUNC_TAB                   36
#define DSQL_DIAG_FUNC_CODE_CREATE_SEQUENCE             37
#define DSQL_DIAG_FUNC_CODE_CREATE_LOGIN                38
#define DSQL_DIAG_FUNC_CODE_ALTER_LOGIN                 39
#define DSQL_DIAG_FUNC_CODE_CREATE_CONTEXT_INDEX        40
#define DSQL_DIAG_FUNC_CODE_DROP_CONTEXT_INDEX          41
#define DSQL_DIAG_FUNC_CODE_ALT_CONTER_INDEX            42
#define DSQL_DIAG_FUNC_CODE_CURSOR_DELETE               43
#define DSQL_DIAG_FUNC_CODE_CURSOR_UPDATE               44
#define DSQL_DIAG_FUNC_CODE_CREATE_LINK                 45
#define DSQL_DIAG_FUNC_CODE_LOCK_TAB                    46
#define DSQL_DIAG_FUNC_CODE_CREATE_POLICY               47
#define DSQL_DIAG_FUNC_CODE_ALTER_POLICY                48
#define DSQL_DIAG_FUNC_CODE_ALTER_USER_POLICY           49
#define DSQL_DIAG_FUNC_CODE_ALTER_TABLE_POLICY          50
#define DSQL_DIAG_FUNC_CODE_CREATE_RULE                 51
#define DSQL_DIAG_FUNC_CODE_CREATE_OPERATOR             52
#define DSQL_DIAG_FUNC_CODE_CREATE_ALERT                53
#define DSQL_DIAG_FUNC_CODE_CREATE_JOB                  54
#define DSQL_DIAG_FUNC_CODE_ALTER_OPERATOR              55
#define DSQL_DIAG_FUNC_CODE_ALTER_ALERT                 56
#define DSQL_DIAG_FUNC_CODE_ALTER_JOB                   57
#define DSQL_DIAG_FUNC_CODE_SET_IDENTINS                58
#define DSQL_DIAG_FUNC_CODE_BACKUP_DATABASE             59
#define DSQL_DIAG_FUNC_CODE_RESTORE_DATABASE            60
#define DSQL_DIAG_FUNC_CODE_CREATE_PACKAGE              61
#define DSQL_DIAG_FUNC_CODE_CREATE_PACKAGE_BODY         62
#define DSQL_DIAG_FUNC_CODE_CREATE_TYPE                 63
#define DSQL_DIAG_FUNC_CODE_CREATE_TYPE_BODY            64
#define DSQL_DIAG_FUNC_CODE_CREATE_SYNONYM              65
#define DSQL_DIAG_FUNC_CODE_CREATE_CRYPT                66
#define DSQL_DIAG_FUNC_CODE_ALTER_CRYPT                 67
#define DSQL_DIAG_FUNC_CODE_SET_CURRENT_SCHEMA          68
#define DSQL_DIAG_FUNC_CODE_MERGE                       69
#define DSQL_DIAG_FUNC_CODE_SET_TIME_ZONE               70
#define DSQL_DIAG_FUNC_CODE_CREATE_TABLESPACE           71
#define DSQL_DIAG_FUNC_CODE_ALTER_TABLESPACE            72
#define DSQL_DIAG_FUNC_CODE_COMMENT                     73
#define DSQL_DIAG_FUNC_CODE_ALTER_SESSION               74
#define DSQL_DIAG_FUNC_CODE_CREATE_DOMAIN               75
#define DSQL_DIAG_FUNC_CODE_CREATE_CHARSET              76
#define DSQL_DIAG_FUNC_CODE_CREATE_COLLATION            77
#define DSQL_DIAG_FUNC_CODE_CREATE_CONTEXT              78
#define DSQL_DIAG_FUNC_CODE_ALTER_INDEX                 79
#define DSQL_DIAG_FUNC_CODE_STAT_ON                     80
#define DSQL_DIAG_FUNC_CODE_CREATE_PROCEDURE            81
#define DSQL_DIAG_FUNC_CODE_ALT_SESS_TIMESTAMP_FMT      82
#define DSQL_DIAG_FUNC_CODE_ALT_SESS_TIMESTAMP_TZ_FMT   83
#define DSQL_DIAG_FUNC_CODE_ALT_SESS_TIME_FMT           84
#define DSQL_DIAG_FUNC_CODE_ALT_SESS_DATE_FMT           85
#define DSQL_DIAG_FUNC_CODE_ALT_SESS_TIME_TZ_FMT        86
#define DSQL_DIAG_FUNC_CODE_ALT_SESS_DATE_LANGUAGE      87
#define DSQL_DIAG_FUNC_CODE_CREATE_PROFILE              88
#define DSQL_DIAG_FUNC_CODE_ALTER_PROFILE               89
#define DSQL_DIAG_FUNC_CODE_DROP_PROFILE                90
#define DSQL_DIAG_FUNC_CODE_CREATE_DIRECTORY            91  /* create directory */
#define DSQL_DIAG_FUNC_CODE_BEGIN_TRAN                  92  /* begin transaction */
#define DSQL_DIAG_FUNC_CODE_CREATE_OPRT                 93  // create operator
#define DSQL_DIAG_FUNC_CODE_DROP_OPRT                   94  // drop operator
#define DSQL_DIAG_FUNC_CODE_CPART_GROUP                 95  // create partition group
#define DSQL_DIAG_FUNC_CODE_ALTER_FUNCTION              96  // alter function
#define DSQL_DIAG_FUNC_CODE_ALT_SESS_NUMERIC_CHARACTERS 97  // NLS_NUMERIC_CHARACTERS

/* internal representation of numeric data type */
#define DPI_MAX_NUMERIC_LEN     16
typedef struct dpi_numeric_struct dpi_numeric_t;
struct dpi_numeric_struct
{
    udbyte              precision;
    sdbyte              scale;
    udbyte              sign;   /* 1 if positive, 0 if negative */
    udbyte              val[DPI_MAX_NUMERIC_LEN];
};

typedef struct dpi_date_struct dpi_date_t;
struct dpi_date_struct
{
    sdint2              year;
    udint2              month;
    udint2              day;
};

typedef struct dpi_time_struct dpi_time_t;
struct dpi_time_struct
{
    udint2              hour;
    udint2              minute;
    udint2              second;
};

typedef struct dpi_timestamp_struct dpi_timestamp_t;
struct dpi_timestamp_struct
{
    sdint2              year;
    udint2              month;
    udint2              day;
    udint2              hour;
    udint2              minute;
    udint2              second;
    udint4              fraction;
};

typedef enum
{
    DSQL_IS_YEAR                = 1,
    DSQL_IS_MONTH               = 2,
    DSQL_IS_DAY                 = 3,
    DSQL_IS_HOUR                = 4,
    DSQL_IS_MINUTE              = 5,
    DSQL_IS_SECOND              = 6,
    DSQL_IS_YEAR_TO_MONTH       = 7,
    DSQL_IS_DAY_TO_HOUR         = 8,
    DSQL_IS_DAY_TO_MINUTE       = 9,
    DSQL_IS_DAY_TO_SECOND       = 10,
    DSQL_IS_HOUR_TO_MINUTE      = 11,
    DSQL_IS_HOUR_TO_SECOND      = 12,
    DSQL_IS_MINUTE_TO_SECOND    = 13
} DPIINTERVAL;

typedef struct dpi_year_month_struct dpi_year_month_t;
struct dpi_year_month_struct
{
    udint4              year;
    udint4              month;
};

typedef struct dpi_day_second_struct dpi_day_second_t;
struct dpi_day_second_struct
{
    udint4              day;
    udint4              hour;
    udint4              minute;
    udint4              second;
    udint4              fraction;
};

typedef struct dpi_interval_struct dpi_interval_t;
struct dpi_interval_struct
{
    DPIINTERVAL         interval_type;
    sdint2              interval_sign;      //1:- 0:+
    union {
        dpi_year_month_t    year_month;
        dpi_day_second_t    day_second;
    } intval;
};

/* environment attribute */
#define DSQL_ATTR_OUTPUT_NTS            10001

/* connection attributes */
#define DSQL_ATTR_AUTO_IPD              10001

/* statement attributes */
#define DSQL_ATTR_APP_ROW_DESC          10010
#define DSQL_ATTR_APP_PARAM_DESC        10011
#define DSQL_ATTR_IMP_ROW_DESC          10012
#define DSQL_ATTR_IMP_PARAM_DESC        10013
#define DSQL_ATTR_METADATA_ID           10014
#define DSQL_ATTR_CURSOR_SCROLLABLE     (-1)
#define DSQL_ATTR_CURSOR_SENSITIVITY    (-2)
#define DSQL_ATTR_SQL_CHARSET           (20000)
#define DSQL_ATTR_IGN_BP_ERR            (20001)
#define DSQL_ATTR_BP_MAX_ERRS           (20002)
#define DSQL_ATTR_ROW_IND_BIND_TYPE     (20003)
#define DSQL_ATTR_PARAM_IND_BIND_TYPE   (20004)
#define DSQL_ATTR_FETCH_PACKAGE_SIZE    (20005)
#define DSQL_ATTR_PARAM_AFFECT_ROWS_PTR (20006)

/* DSQL_ATTR_CURSOR_SCROLLABLE values */
#define DSQL_NONSCROLLABLE              0
#define DSQL_SCROLLABLE                 1

/* identifiers of fields in the SQL descriptor */
#define DSQL_DESC_COUNT                     1001
#define DSQL_DESC_TYPE                      1002
#define DSQL_DESC_LENGTH                    1003
#define DSQL_DESC_OCTET_LENGTH_PTR          1004
#define DSQL_DESC_PRECISION                 1005
#define DSQL_DESC_SCALE                     1006
#define DSQL_DESC_DATETIME_INTERVAL_CODE    1007
#define DSQL_DESC_NULLABLE                  1008
#define DSQL_DESC_INDICATOR_PTR             1009
#define DSQL_DESC_DATA_PTR                  1010
#define DSQL_DESC_NAME                      1011
#define DSQL_DESC_UNNAMED                   1012
#define DSQL_DESC_OCTET_LENGTH              1013
#define DSQL_DESC_ALLOC_TYPE                1099

/* Statement attribute values for cursor sensitivity */
#define DSQL_UNSPECIFIED                    0
#define DSQL_INSENSITIVE                    1
#define DSQL_SENSITIVE                      2

/* Default conversion code for dpi_bind_col(), dpi_bind_param() and dpi_get_data() */
#define DSQL_DEFAULT                        99

/* dpi_get_data() code indicating that the application row descriptor
 * specifies the data type
 */
#define DSQL_ARD_TYPE                       (-99)

#define DSQL_FALSE                          0
#define DSQL_TRUE                           1

/* values of NULLABLE field in descriptor */
#define DSQL_NO_NULLS                       0
#define DSQL_NULLABLE                       1

/* Values returned to show WHERE clause
 * supported
 */
#define DSQL_PRED_NONE                      0
#define DSQL_PRED_CHAR                      1
#define DSQL_PRED_BASIC                     2
#define DSQL_PRED_SEARCHABLE                3

/* values of UNNAMED field in descriptor */
#define DSQL_NAMED                          0
#define DSQL_UNNAMED                        1

/* values of ALLOC_TYPE field in descriptor */
#define DSQL_DESC_ALLOC_AUTO                1
#define DSQL_DESC_ALLOC_USER                2

/* Codes used for FetchOrientation in dpi_fetch_scroll()
*/
#define DSQL_FETCH_NEXT                     1
#define DSQL_FETCH_FIRST                    2

/* Other codes used for FetchOrientation in dpi_fetch_scroll() */
#define DSQL_FETCH_LAST                     3
#define DSQL_FETCH_PRIOR                    4
#define DSQL_FETCH_ABSOLUTE                 5
#define DSQL_FETCH_RELATIVE                 6
#define DSQL_FETCH_BOOKMARK                 8

/* dpi_end_tran() options */
#define DSQL_COMMIT                         0
#define DSQL_ROLLBACK                       1

/* null handles returned by dpi_alloc_handle() */
#define DSQL_NULL_HENV                      0
#define DSQL_NULL_HDBC                      0
#define DSQL_NULL_HSTMT                     0
#define DSQL_NULL_HDESC                     0
#define DSQL_NULL_HLOB                      0

/* null handle used in place of parent handle when allocating HENV */
#define DSQL_NULL_HANDLE                    0L


//#define ISO_LEVEL_INVALID           (-1)
#define ISO_LEVEL_READ_UNCOMMITTED          0
#define ISO_LEVEL_READ_COMMITTED            1
#define ISO_LEVEL_REPEATABLE_READ           2
#define ISO_LEVEL_SERIALIZABLE              3

/* Reserved values for UNIQUE argument of dpi_statistics() */
#define DSQL_INDEX_UNIQUE                   0

/* Values that may appear in the result set of dpi_specialcolumns() */
#define DSQL_SCOPE_CURROW                   0

/* Column types and scopes in dpi_specialcolumns().  */
#define DSQL_BEST_ROWID                     1
#define DSQL_ROWVER                         2

//DPI call interface
DllExport
DPIRETURN
dpi_module_init();

DllExport
DPIRETURN
dpi_module_deinit();

//handle function
DllExport
DPIRETURN
dpi_alloc_handle(
    sdint2          hndl_type,
    dhandle         hndl_in,
    dhandle*        hndl_out
);

DllExport
DPIRETURN
dpi_free_handle(
    sdint2          hndl_type,
    dhandle         hndl
);

DllExport
DPIRETURN
dpi_alloc_env(
    dhenv*          dpi_henv
);

DllExport
DPIRETURN
dpi_alloc_con(
    dhenv           dpi_henv,
    dhcon*          dpi_hcon
);

DllExport
DPIRETURN
dpi_alloc_stmt(
    dhcon           dpi_hcon,
    dhstmt*         dpi_hstmt
);

DllExport
DPIRETURN
dpi_alloc_desc(
    dhcon           dpi_hcon,
    dhdesc*         dpi_hdesc
);

DllExport
DPIRETURN
dpi_alloc_lob_locator(
    dhstmt          dpi_hstmt,
    dhloblctr*      dpi_loblctr
);

DllExport
DPIRETURN
dpi_alloc_lob_locator2(
    dhcon           dpi_hcon,
    dhloblctr*      dpi_loblctr
);

DllExport
DPIRETURN
dpi_alloc_bfile(
    dhcon           dpi_hcon,
    dhbfile*        dpi_loblctr
);

DllExport
DPIRETURN
dpi_free_env(
    dhenv           dpi_henv
);

DllExport
DPIRETURN
dpi_free_con(
    dhcon           dpi_hcon
);

DllExport
DPIRETURN
dpi_free_stmt(
    dhstmt          dpi_hstmt
);

DllExport
DPIRETURN
dpi_free_desc(
    dhdesc          dpi_hdesc
);

DllExport
DPIRETURN
dpi_free_lob_locator(
    dhloblctr       dpi_loblctr
);

DllExport
DPIRETURN
dpi_free_bfile(
    dhbfile         bfile_lctr
);

DllExport
DPIRETURN
dpi_set_env_attr(
    dhenv           dpi_henv,
    sdint4          attr_id,
    dpointer        val,
    sdint4          val_len
);

DllExport
DPIRETURN
dpi_set_con_attr(
    dhcon           dpi_hcon,
    sdint4          attr_id,
    dpointer        val,
    sdint4          val_len
);

DllExport
DPIRETURN
dpi_set_stmt_attr(
    dhstmt          dpi_hstmt,
    sdint4          attr_id,
    dpointer        val,
    sdint4          val_len
);

DllExport
DPIRETURN
dpi_get_env_attr(
    dhenv           dpi_henv,
    sdint4          attr_id,
    dpointer        val,
    sdint4          buf_len,
    sdint4*         val_len
);

DllExport
DPIRETURN
dpi_get_con_attr(
    dhcon           dpi_hcon,
    sdint4          attr_id,
    dpointer        val,
    sdint4          buf_len,
    sdint4*         val_len
);

DllExport
DPIRETURN
dpi_get_stmt_attr(
    dhstmt          dpi_hstmt,
    sdint4          attr_id,
    dpointer        val,
    sdint4          buf_len,
    sdint4*         val_len
);

//diagnose functions
DllExport
DPIRETURN
dpi_get_diag_rec(
    sdint2          hndl_type,
    dhandle         hndl,
    sdint2          rec_num,
    sdint4*         err_code,
    sdbyte*         err_msg,
    sdint2          buf_sz,
    sdint2*         msg_len
);

DllExport
DPIRETURN
dpi_get_diag_field(
    sdint2          hndl_type,
    dhandle         hndl,
    sdint2          rec_num,
    sdint2          diag_id,
    dpointer        diag_info,
    slength         buf_len,
    slength*        info_len
);

//connection functions
DllExport
DPIRETURN
dpi_login(
    dhcon           dpi_hcon,
    sdbyte*         svr,
    sdbyte*         user,
    sdbyte*         pwd
);

DllExport
DPIRETURN
dpi_logout(
    dhcon           dpi_hcon
);

DllExport
DPIRETURN
dpi_commit(
    dhcon           dpi_hcon
);

DllExport
DPIRETURN
dpi_rollback(
    dhcon           dpi_hcon
);

DllExport
DPIRETURN
dpi_end_tran(
    sdint2          hndl_type,      //in
    dhandle         hndl,           //in
    sdint2          type
);

DllExport
DPIRETURN
dpi_cancel(
    dhstmt          dpi_hstmt
);

//descripton functions
DllExport
DPIRETURN
dpi_copy_desc(
    dhdesc          src_desc,
    dhdesc          target_desc
);

DllExport
DPIRETURN
dpi_set_desc_rec(
    dhdesc          dpi_desc,
    udint2          rec_num,
    sdint2          type,
    sdint2          sub_type,
    slength         length,
    sdint2          prec,
    sdint2          scale,
    dpointer        data_ptr,
    slength*        str_len,
    slength*        ind_ptr
);

DllExport
DPIRETURN
dpi_set_desc_field(
    dhdesc          dpi_desc,
    udint2          rec_num,
    sdint2          field,
    dpointer        val,
    sdint4          val_len
);

DllExport
DPIRETURN
dpi_get_desc_rec(
    dhdesc          dpi_desc,
    udint2          rec_num,
    sdbyte*         name_buf,
    sdint2          name_buf_len,
    sdint2*         name_len,
    sdint2*         type,
    sdint2*         sub_type,
    slength*        length,
    sdint2*         prec,
    sdint2*         scale,
    sdint2*         nullable
);

DllExport
DPIRETURN
dpi_get_desc_field(
    dhdesc          dpi_desc,
    udint2          rec_num,
    sdint2          field,
    dpointer        val,
    sdint4          val_len,
    sdint4*         str_len
);

//statement function
//statement execution operation
DllExport
DPIRETURN
dpi_bind_param(
    dhstmt          dpi_hstmt,
    udint2          iparam,             //1-based index
    sdint2          param_type,
    sdint2          ctype,
    sdint2          dtype,
    ulength         precision,
    sdint2          scale,
    dpointer        buf,
    slength         buf_len,
    slength*        ind_ptr
);

DllExport
DPIRETURN
dpi_bind_param2(
    dhstmt          dpi_hstmt,
    udint2          iparam,             //1-based index
    sdint2          param_type,
    sdint2          ctype,
    sdint2          dtype,
    ulength         precision,
    sdint2          scale,
    dpointer        buf,
    slength         buf_len,
    slength*        ind_ptr,
    slength*        act_len_ptr
);

DllExport
DPIRETURN
dpi_desc_param(
    dhstmt          dpi_hstmt,
    udint2          iparam,         //1-based
    sdint2*         sql_type,
    ulength*        prec,
    sdint2*         scale,
    sdint2*         nullable
);

DllExport
DPIRETURN
dpi_exec(
    dhstmt          dpi_hstmt
);

DllExport
DPIRETURN
dpi_exec_direct(
    dhstmt          dpi_hstmt,
    sdbyte*         sql_txt
);

DllExport
DPIRETURN
dpi_exec_add_batch(
    dhstmt          dpi_hstmt
);

DllExport
DPIRETURN
dpi_exec_batch(
    dhstmt          dpi_hstmt
);

DllExport
DPIRETURN
dpi_unbind_params(
    dhstmt          dpi_hstmt
);

DllExport
DPIRETURN
dpi_unbind_columns(
    dhstmt          dpi_hstmt
);

DllExport
DPIRETURN
dpi_param_data(
    dhstmt          dpi_hstmt,
    dpointer*       val_ptr
);

DllExport
DPIRETURN
dpi_prepare(
    dhstmt          dpi_hstmt,
    sdbyte*         sql_txt
);

DllExport
DPIRETURN
dpi_put_data(
    dhstmt          dpi_hstmt,
    dpointer        val,
    slength         val_len
);

DllExport
DPIRETURN
dpi_number_params(
    dhstmt          dpi_stmt,
    udint2*         param_cnt
);

DllExport
DPIRETURN
dpi_set_cursor_name(
    dhstmt          dpi_hstmt,
    sdbyte*         name,
    sdint2          name_len
);

DllExport
DPIRETURN
dpi_get_cursor_name(
    dhstmt          dpi_hstmt,
    sdbyte*         name,
    sdint2          buf_len,
    sdint2          *name_len
);

//statement resultset operation
DllExport
DPIRETURN
dpi_close_cursor(
    dhstmt          dpi_hstmt
);

DllExport
DPIRETURN
dpi_bind_col(
    dhstmt          dpi_hstmt,
    udint2          icol,
    sdint2          ctype,
    dpointer        val,
    slength         buf_len,
    slength*        ind
);

DllExport
DPIRETURN
dpi_bind_col2(
    dhstmt          dpi_hstmt,
    udint2          icol,
    sdint2          ctype,
    dpointer        val,
    slength         buf_len,
    slength*        ind,
    slength*        act_len
);

DllExport
DPIRETURN
dpi_number_columns(
    dhstmt          dpi_stmt,
    sdint2*         col_cnt
);

DllExport
DPIRETURN
dpi_desc_column(
    dhstmt          dpi_hstmt,
    sdint2          icol,
    sdbyte*         name,
    sdint2          buf_len,
    sdint2*         name_len,
    sdint2*         sqltype,
    ulength*        col_sz,
    sdint2*         dec_digits,
    sdint2*         nullable
);

DllExport
DPIRETURN
dpi_col_attr(
    dhstmt          dpi_hstmt,
    udint2          icol,
    udint2          fld_id,
    dpointer        chr_attr,
    sdint2          buf_len,
    sdint2*         chr_attr_len,
    slength*        num_attr
);

DllExport
DPIRETURN
dpi_bulk_operation(
    dhstmt          dpi_hstmt,
    udint2          op
);

DllExport
DPIRETURN
dpi_fetch(
    dhstmt          dpi_hstmt,
    ulength*        row_num
);

DllExport
DPIRETURN
dpi_fetch_scroll(
    dhstmt          dpi_hstmt,
    sdint2          orient,
    slength         offset,
    ulength*        row_num
);

DllExport
DPIRETURN
dpi_get_data(
    dhstmt          dpi_hstmt,
    udint2          icol,
    sdint2          ctype,
    dpointer        val,
    slength         buf_len,
    slength*        val_len
);

DllExport
DPIRETURN
dpi_get_data2(
    dhstmt          dpi_hstmt,
    udint2          icol,
    sdint2          ctype,
    dpointer        val,
    slength         buf_len,
    slength*        val_len,
    slength*        act_len
);

DllExport
DPIRETURN
dpi_more_results(
    dhstmt          dpi_hstmt
);

DllExport
DPIRETURN
dpi_set_pos(
    dhstmt          dpi_hstmt,
    ulength         row_num,
    udint2          op,
    udint2          lock_type
);

DllExport
DPIRETURN
dpi_row_count(
    dhstmt          dpi_hstmt,
    sdint8*         row_num
);

DllExport
DPIRETURN
dpi_lob_get_length(
    dhloblctr       dpi_loblctr,
    slength*        len
);

DllExport
DPIRETURN
dpi_lob_get_length2(
    dhloblctr       dpi_loblctr,
    sdint8*         len
);

DllExport
DPIRETURN
dpi_lob_read(
    dhloblctr       dpi_loblctr,
    ulength         start_pos,
    sdint2          ctype,
    slength         data_to_read,
    dpointer        val_buf,
    slength         buf_len,
    slength*        data_get
);

DllExport
DPIRETURN
dpi_lob_read2(
    dhloblctr       dpi_loblctr,
    udint8          start_pos,
    sdint2          ctype,
    slength         data_to_read,
    dpointer        val_buf,
    slength         buf_len,
    slength*        data_get
);

DllExport
DPIRETURN
dpi_lob_read3(
    dhloblctr   dpi_loblctr,
    udint8      start_pos,
    sdint2      ctype,
    slength     data_to_read,
    dpointer    val_buf,
    slength     buf_len,
    slength*    data_get,
    slength*    data_get_bytes
);

DllExport
DPIRETURN
dpi_lob_write(
    dhloblctr       dpi_loblctr,
    ulength         start_pos,
    sdint2          ctype,
    dpointer        val,
    ulength         bytes_to_write,
    ulength*        data_writed
);

DllExport
DPIRETURN
dpi_lob_write2(
    dhloblctr       dpi_loblctr,
    udint8          start_pos,
    sdint2          ctype,
    dpointer        val,
    ulength         bytes_to_write,
    ulength*        data_writed
);

DllExport
DPIRETURN
dpi_lob_truncate(
    dhloblctr       dpi_loblctr,
    ulength         len,
    ulength*        data_len
);

DllExport
DPIRETURN
dpi_lob_truncate2(
    dhloblctr       dpi_loblctr,
    udint8          len,
    udint8*         data_len
);

//////complex object
DllExport
DPIRETURN
dpi_desc_obj(
    dhcon           dpi_con,
    sdbyte*         schema,
    sdbyte*         compobj_name,
    dhobjdesc*      obj_desc
);

DllExport
DPIRETURN
dpi_desc_obj2(
    dhcon           dpi_con,
    sdbyte*         schema,
    sdbyte*         pkg_name,
    sdbyte*         compobj_name,
    dhobjdesc*      obj_desc
);

DllExport
DPIRETURN
dpi_free_obj_desc(
    dhobjdesc       obj_desc
);

DllExport
DPIRETURN
dpi_alloc_obj(
    dhcon           dpi_con,
    dhobj*          object
);

DllExport
DPIRETURN
dpi_free_obj(
    dhobj           object
);

DllExport
DPIRETURN
dpi_get_obj_attr(
    dhobj           object,
    udint4          nth,
    udint2          attr_id,
    dpointer        buf,
    udint4          buf_len,
    slength*        len
);

DllExport
DPIRETURN
dpi_get_obj_desc_attr(
    dhobjdesc       obj_desc,
    udint4          nth,
    udint2          attr_id,
    dpointer        buf,
    udint4          buf_len,
    slength*        len
);

DllExport
DPIRETURN
dpi_bind_obj_desc(
    dhobj           object,
    dhobjdesc       desc
);

DllExport
DPIRETURN
dpi_unbind_obj_desc(
    dhobj           object
);

DllExport
DPIRETURN
dpi_set_obj_val(
    dhobj           object,
    udint4          nth,
    udint2          ctype,
    dpointer        val,
    slength         val_len
);

DllExport
DPIRETURN
dpi_set_indtab_node(
    dhobj                   object,
    udint2                  ktype,
    dpointer                key,
    slength                 key_len,
    udint2                  vtype,
    dpointer                val,
    slength                 val_len
);

DllExport
DPIRETURN
dpi_get_obj_val(
    dhobj           object,
    udint4          nth,
    udint2          ctype,
    dpointer        val,
    udint4          buf_len,
    slength*        val_len
);

////bfile
DllExport 
DPIRETURN
dpi_bfile_construct(
    dhbfile         bfile_lctr,
    udbyte*         dir_name,
    udbyte*         file_name
);

DllExport 
DPIRETURN
dpi_bfile_get_name(
    dhbfile         bfile_lctr,
    udbyte*         dir_buf,
    udint4          dir_buf_len,
    udint4*         dir_len,
    udbyte*         file_buf,
    udint4          file_buf_len,
    udint4*         file_len
);

DllExport DPIRETURN
dpi_bfile_read(
    dhbfile         dpi_bfile,
    udint8          start_pos,      //1 based:blob bytes clob chars
    sdint2          ctype,
    udint8          data_to_read,    //0:default blob bytes clob chars
    dpointer        val_buf,
    udint8          buf_len,
    udint8*         data_get        //blob:bytes_get clob:chars
);

//catalog functions
DllExport
DPIRETURN
dpi_tables(
    dhstmt          dpi_stmt,
    udbyte*         catalogname,
    sdint2          namelength1,
    udbyte*         schemaname,
    sdint2          namelength2,
    udbyte*         tablename,
    sdint2          namelength3,
    udbyte*         tabletype,
    sdint2          namelength4
);

DllExport
DPIRETURN
dpi_columns(
    dhstmt          dpi_stmt,
    udbyte*         catalogname,
    sdint2          namelength1,
    udbyte*         schemaname,
    sdint2          namelength2,
    udbyte*         tablename,
    sdint2          namelength3,
    udbyte*         columnname,
    sdint2          namelength4
);

DllExport
DPIRETURN
dpi_statistics(
    dhstmt          dpi_stmt,
    udbyte*         catalogname,
    sdint2          namelength1,
    udbyte*         schemaname,
    sdint2          namelength2,
    udbyte*         tablename,
    sdint2          namelength3,
    udint2          unique,
    udint2          reserved
);

DllExport
DPIRETURN
dpi_specialcolumns(
    dhstmt          dpi_stmt,
    udint2          identifiertype,
    udbyte*         catalogname,
    sdint2          namelength1,
    udbyte*         schemaname,
    sdint2          namelength2,
    udbyte*         tablename,
    sdint2          namelength3,
    udint2          scope,
    udint2          nullable
);

DllExport
DPIRETURN
dpi_primarykeys(
    dhstmt          dpi_stmt,
    udbyte*         catalogname,
    sdint2          namelength1,
    udbyte*         schemaname,
    sdint2          namelength2,
    udbyte*         tablename,
    sdint2          namelength3
);

DllExport
DPIRETURN
dpi_foreignkeys(
    dhstmt          dpi_stmt,
    udbyte*         szpkcatalogname,
    sdint2          cbpkcatalogname,
    udbyte*         szpkschemaname,
    sdint2          cbpkschemaname,
    udbyte*         szpktablename,
    sdint2          cbpktablename,
    udbyte*         szfkcatalogname,
    sdint2          cbfkcatalogname,
    udbyte*         szfkschemaname,
    sdint2          cbfkschemaname,
    udbyte*         szfktablename,
    sdint2          cbfktablename
);

DllExport
DPIRETURN
dpi_tableprivileges(
    dhstmt          dpi_stmt,
    udbyte*         catalogname,
    sdint2          namelength1,
    udbyte*         schemaname,
    sdint2          namelength2,
    udbyte*         tablename,
    sdint2          namelength3
);

DllExport
DPIRETURN
dpi_columnprivileges(
    dhstmt          dpi_stmt,
    udbyte*         catalogname,
    sdint2          namelength1,
    udbyte*         schemaname,
    sdint2          namelength2,
    udbyte*         tablename,
    sdint2          namelength3,
    udbyte*         columnname,
    sdint2          namelength4
);

DllExport
DPIRETURN
dpi_procedures(
    dhstmt          dpi_stmt,
    udbyte*         catalogname,
    sdint2          namelength1,
    udbyte*         schemaname,
    sdint2          namelength2,
    udbyte*         procname,
    sdint2          namelength3
);

DllExport
DPIRETURN
dpi_procedurecolumns(
   dhstmt           dpi_stmt,
   udbyte*          catalogname,
   sdint2           namelength1,
   udbyte*          schemaname,
   sdint2           namelength2,
   udbyte*          procname,
   sdint2           namelength3,
   udbyte*          columnname,
   sdint2           namelength4
);

DllExport
DPIRETURN
dpi_columns2(
    dhstmt          dpi_stmt,
    udbyte*         catalogname,
    sdint2          namelength1,
    udbyte*         schemaname,
    sdint2          namelength2,
    udbyte*         tablename,
    sdint2          namelength3,
    udbyte*         columnname,
    sdint2          namelength4
);

DllExport
DPIRETURN
dpi_specialcolumns2(
    dhstmt          dpi_stmt,
    udint2          identifiertype,
    udbyte*         catalogname,
    sdint2          namelength1,
    udbyte*         schemaname,
    sdint2          namelength2,
    udbyte*         tablename,
    sdint2          namelength3,
    udint2          scope,
    udint2          nullable
);

DllExport
DPIRETURN
dpi_procedurecolumns2(
    dhstmt           dpi_stmt,
    udbyte*          catalogname,
    sdint2           namelength1,
    udbyte*          schemaname,
    sdint2           namelength2,
    udbyte*          procname,
    sdint2           namelength3,
    udbyte*          columnname,
    sdint2           namelength4
);

DllExport
DPIRETURN
dpi_build_rowid(
    dhcon           dpi_con,
    sdint4          epno,
    sdint8          partno,
    udint8          real_rowid,
    sdbyte*         rowid_buf,
    udint4          rowid_buf_len,
    udint4*         rowid_len
);

DllExport
DPIRETURN
dpi_rowid_to_char(
    dhcon           dpi_con,
    sdbyte*         rowid,
    udint4          rowid_len,
    sdbyte*         dest_buf,
    udint4          dest_buf_len,
    udint4*         dest_len
);

DllExport
DPIRETURN
dpi_char_to_rowid(
    dhcon           dpi_con,
    sdbyte*         rowid_str,
    udint4          rowid_len,
    sdbyte*         dest_buf,
    udint4          dest_buf_len,
    udint4*         dest_len
);

#ifdef __cplusplus
}                                    /* End of extern "C" { */
#endif  /* __cplusplus */
#endif  /* #ifndef _DPI_H */

