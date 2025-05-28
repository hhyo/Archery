/** cx_Dameng.cpp : 定义 DLL 的初始化例程。 **/
//
#include "py_Dameng.h"
#include <datetime.h>
#include "Error.h"
#include "DPI.h"
#include "var_pub.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "trc.h"
#ifdef WIN32
#include <Windows.h>
#endif

#if PY_MAJOR_VERSION >= 3
    #include <moduleobject.h>
#endif

// define macro for adding type objects
#define ADD_TYPE_OBJECT(name, type) \
	Py_INCREF(type); \
	if (PyModule_AddObject(module, name, (PyObject*) type) < 0) \
	return NULL;

// define macros for making types ready
#define MAKE_TYPE_READY(type) \
	if (PyType_Ready(type) < 0) \
	return NULL;

#define MAKE_dmVar_TYPE_READY(type) \
    (type)->tp_base = &g_BaseVarType;  \
    MAKE_TYPE_READY(type)

// define base exception
#if PY_MAJOR_VERSION >= 3
#define BASE_EXCEPTION    NULL
#define TYPE_ERROR        "expecting string or bytes object"
#else
#define BASE_EXCEPTION    PyExc_StandardError
#define TYPE_ERROR        "expecting string, unicode or buffer object"
#endif

#ifdef WIN32
#define DIR_CHAR            '\\'
#else
#define DIR_CHAR             '/'
#endif

#define MAX_PATH_LEN        256
#define MAX_LINE_LENGTH     100
typedef sdbyte               pathname_t[MAX_PATH_LEN + 1];

PyObject *g_WarningException = NULL;
PyObject *g_ErrorException = NULL;
PyObject *g_InterfaceErrorException = NULL;
PyObject *g_DatabaseErrorException = NULL;
PyObject *g_DataErrorException = NULL;
PyObject *g_OperationalErrorException = NULL;
PyObject *g_IntegrityErrorException = NULL;
PyObject *g_InternalErrorException = NULL;
PyObject *g_ProgrammingErrorException = NULL;
PyObject *g_NotSupportedErrorException = NULL;
PyTypeObject* g_decimal_type = NULL;

//-----------------------------------------------------------------------------
// SetException()
//   Create an exception and set it in the provided dictionary.
//-----------------------------------------------------------------------------
static 
sdint2
SetException(
    PyObject*       module,                   // module object
    PyObject**      exception,               // exception to create
    char*           name,                         // name of the exception
    PyObject*       baseException
)            // exception to base exception on
{
    char buffer[100];

    sprintf(buffer, "dmPython.%s", name);
    *exception = PyErr_NewException(buffer, baseException, NULL);
    if (!*exception)
        return -1;
    return PyModule_AddObject(module, name, *exception);
}

/* Parse arg tuple that can contain an optional float-or-None value;
   format needs to be "|O:name".
   Returns non-zero on success (parallels PyArg_ParseTuple).
*/

static void
error_time_t_overflow(void)
{
    PyErr_SetString(PyExc_OverflowError,
                    "timestamp out of range for platform time_t");
}

static 
int
parse_time_t_args(
    PyObject*       args, 
    char*           format, 
    time_t*         pwhen
)
{
    PyObject*       ot = NULL;        

    if (!PyArg_ParseTuple(args, format, &ot))
        return -1;

    if (ot == NULL || ot == Py_None) 
    {
        *pwhen  = time(NULL);

        return 0;
    }

    if (PyFloat_Check(ot)) 
    {        
        double  d;
        double  intpart;
        double  err;

        d       = PyFloat_AsDouble(ot);
        (void)modf(d, &intpart);

        *pwhen  = (time_t)intpart;
        err     = intpart - (double)(*pwhen);
        if (err <= -1.0 || err >= 1.0) 
        {            
            error_time_t_overflow();
            return -1;
        }

        return 0;
    }
    
    {
#if defined(HAVE_LONG_LONG) && SIZEOF_TIME_T == SIZEOF_LONG_LONG
        PY_LONG_LONG val;
        val = PyLong_AsLongLong(ot);
#else
        long val;
        assert(sizeof(time_t) <= sizeof(long));
        val = PyLong_AsLong(ot);
#endif      
        if (val == -1 && PyErr_Occurred())
        {
            if (PyErr_ExceptionMatches(PyExc_OverflowError))
                error_time_t_overflow();

            return -1;
        }        

        *pwhen  = (time_t)val;
    }

    return 0;
}

static 
int
pylocaltime(
    time_t*         timep, 
    struct tm*      result)
{
    struct tm *local;

    assert (timep != NULL);
    local = localtime(timep);
    if (local == NULL) {
        /* unconvertible time */
#ifdef EINVAL
        if (errno == 0)
            errno = EINVAL;
#endif
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }
    *result = *local;
    return 0;
}

//-----------------------------------------------------------------------------
//DateFromTicks(ticks)
//   This function constructs an object holding a date value
//        from the given ticks value (number of seconds since the
//        epoch; see the documentation of the standard Python time
//        module for details).
//-----------------------------------------------------------------------------
static
PyObject*
dmDateFromTicks(
    PyObject*       module,
    PyObject*       args
)
{
    return PyDate_FromTimestamp(args);
}

//-----------------------------------------------------------------------------
//TimeFromTicks(ticks)
//   This function constructs an object holding a time value
//   from the given ticks value (number of seconds since the
//   epoch; see the documentation of the standard Python time
//   module for details).
//-----------------------------------------------------------------------------
static
PyObject*
dmTimeFromTicks(
    PyObject*       module,
    PyObject*       args
)
{    
    time_t when;
    struct tm fields;

    if (parse_time_t_args(args, "|O:localtime", &when) < 0)
        return NULL;

    if (pylocaltime(&when, &fields) < 0)
        return NULL;     

    return PyTime_FromTime(fields.tm_hour, fields.tm_min, fields.tm_sec, 0);
}

//-----------------------------------------------------------------------------
//TimestampFromTicks(ticks)
//   This function constructs an object holding a time stamp value
//   from the given ticks value (number of seconds since the
//   epoch; see the documentation of the standard Python time
//   module for details).
//-----------------------------------------------------------------------------
static
PyObject*
dmTimestampFromTicks(
    PyObject*       module,
    PyObject*       args
)
{    
    time_t when;
    struct tm fields;

    if (parse_time_t_args(args, "|O:localtime", &when) < 0)
        return NULL;

    if (pylocaltime(&when, &fields) < 0)
        return NULL;     

    return PyDateTime_FromDateAndTime(fields.tm_year + 1900, fields.tm_mon + 1, fields.tm_mday, fields.tm_hour, fields.tm_min, fields.tm_sec, 0);
}

static
PyObject*
dmStringFromBytes(
    PyObject*       module,
    PyObject*       args
)
{
    PyObject*       bsObject = NULL;
    Py_ssize_t      len;

    if (!PyArg_ParseTuple(args, "O", &bsObject))
        return NULL;

    if (!PyBytes_Check(bsObject))
    {
        PyErr_SetString(PyExc_TypeError,
            "expect a Bytes Object");
        return NULL;
    }

    len     = PyBytes_GET_SIZE(bsObject);

    return exLobVar_BytesToString(bsObject, len);
}

//-----------------------------------------------------------------------------
//   Declaration of methods supported by this module
//-----------------------------------------------------------------------------
static PyMethodDef g_ModuleMethods[] = {    
    { "DateFromTicks",      (PyCFunction)dmDateFromTicks,   METH_VARARGS,   "This function constructs an object holding a date value \n"
                                                                            "from the given ticks value (number of seconds since the \n"
                                                                            "epoch; see the documentation of the standard Python time \n"
                                                                            "module for details"},
    { "TimeFromTicks",      (PyCFunction)dmTimeFromTicks,   METH_VARARGS,   "This function constructs an object holding a time value \n"
                                                                            "from the given ticks value (number of seconds since the \n"
                                                                            "epoch; see the documentation of the standard Python time \n"
                                                                            "module for details"},
    { "TimestampFromTicks", (PyCFunction)dmTimestampFromTicks,   METH_VARARGS,   "This function constructs an object holding a time stamp value \n"
                                                                            "from the given ticks value (number of seconds since the \n"
                                                                            "epoch; see the documentation of the standard Python time \n"
                                                                            "module for details"},    
    { "StringFromBytes",    (PyCFunction)dmStringFromBytes,   METH_VARARGS,   "This function constructs an object holding a string value \n"
                                                                            "from the given bytes value"},    

	{ NULL }
};

#if PY_MAJOR_VERSION >= 3

//-----------------------------------------------------------------------------
//   Declaration of module definition for Python 3.x.
//-----------------------------------------------------------------------------
static struct PyModuleDef g_ModuleDef = {
	PyModuleDef_HEAD_INIT,
	"dmPython",
	NULL,
	-1,
	g_ModuleMethods,                       // methods
	NULL,                                  // m_reload
	NULL,                                  // traverse
	NULL,                                  // clear
	NULL                                   // free
};
#endif


static
sdint2
import_types()
{
	PyObject *pdt = NULL, *decimalmod = NULL;

	pdt = PyImport_ImportModule("datetime");
	if (!pdt)
		return -1;

	PyDateTime_IMPORT;

    dmVar_Import();

	Cursor_Data_init();
	decimalmod = PyImport_ImportModule("decimal");
	if (!decimalmod)
	{
		PyErr_SetString(PyExc_RuntimeError, "Unable to import decimal");
		return -1;
	}

	g_decimal_type  = (PyTypeObject*)PyObject_GetAttrString(decimalmod, "Decimal");
	Py_DECREF(decimalmod);

	if (g_decimal_type == 0)
	{
		PyErr_SetString(PyExc_RuntimeError, "Unable to import decimal.Decimal.");
		return -1;
	}

	return 0;
}

/** 增加相关操作常量 **/
static
void
module_add_oper_const(
    PyObject*       module
)
{
    /** shutdown相关 **/
    PyModule_AddStringConstant(module, "SHUTDOWN_DEFAULT", SHUTDOWN_DEFAULT);
    PyModule_AddStringConstant(module, "SHUTDOWN_ABORT", SHUTDOWN_ABORT);
    PyModule_AddStringConstant(module, "SHUTDOWN_IMMEDIATE", SHUTDOWN_IMMEDIATE);
    PyModule_AddStringConstant(module, "SHUTDOWN_TRANSACTIONAL", SHUTDOWN_TRANSACTIONAL);  
    PyModule_AddStringConstant(module, "SHUTDOWN_NORMAL", SHUTDOWN_NORMAL);

    /** debug相关 **/
    PyModule_AddIntConstant(module, "DEBUG_CLOSE", DEBUG_CLOSE);
    PyModule_AddIntConstant(module, "DEBUG_OPEN", DEBUG_OPEN);
    PyModule_AddIntConstant(module, "DEBUG_SWITCH", DEBUG_SWITCH);
    PyModule_AddIntConstant(module, "DEBUG_SIMPLE", DEBUG_SIMPLE);

    /** 隔离级相关 **/
    PyModule_AddIntConstant(module, "ISO_LEVEL_READ_DEFAULT", ISO_LEVEL_READ_COMMITTED);
    PyModule_AddIntConstant(module, "ISO_LEVEL_READ_UNCOMMITTED", ISO_LEVEL_READ_UNCOMMITTED);    
    PyModule_AddIntConstant(module, "ISO_LEVEL_READ_COMMITTED", ISO_LEVEL_READ_COMMITTED);
    PyModule_AddIntConstant(module, "ISO_LEVEL_REPEATABLE_READ", ISO_LEVEL_REPEATABLE_READ);
    PyModule_AddIntConstant(module, "ISO_LEVEL_SERIALIZABLE", ISO_LEVEL_SERIALIZABLE);

    /** access_mode相关 **/
    PyModule_AddIntConstant(module, "DSQL_MODE_READ_ONLY", DSQL_MODE_READ_ONLY);
    PyModule_AddIntConstant(module, "DSQL_MODE_READ_WRITE", DSQL_MODE_READ_WRITE);

    /** autocommit相关 **/
    PyModule_AddIntConstant(module, "DSQL_AUTOCOMMIT_ON", DSQL_AUTOCOMMIT_ON);
    PyModule_AddIntConstant(module, "DSQL_AUTOCOMMIT_OFF", DSQL_AUTOCOMMIT_OFF);

    /** 编码方式相关 **/
    PyModule_AddIntConstant(module, "PG_UTF8", PG_UTF8);
    PyModule_AddIntConstant(module, "PG_GBK", PG_GBK);
    PyModule_AddIntConstant(module, "PG_BIG5", PG_BIG5);
    PyModule_AddIntConstant(module, "PG_ISO_8859_9", PG_ISO_8859_9);
    PyModule_AddIntConstant(module, "PG_EUC_JP", PG_EUC_JP);
    PyModule_AddIntConstant(module, "PG_EUC_KR", PG_EUC_KR);
    PyModule_AddIntConstant(module, "PG_KOI8R", PG_KOI8R);
    PyModule_AddIntConstant(module, "PG_ISO_8859_1", PG_ISO_8859_1);
    PyModule_AddIntConstant(module, "PG_SQL_ASCII", PG_SQL_ASCII);
    PyModule_AddIntConstant(module, "PG_GB18030", PG_GB18030);
    PyModule_AddIntConstant(module, "PG_ISO_8859_11", PG_ISO_8859_11);

    /** 语言类型 **/
    PyModule_AddIntConstant(module, "LANGUAGE_CN", LANGUAGE_CN);
    PyModule_AddIntConstant(module, "LANGUAGE_EN", LANGUAGE_EN);
#ifdef LANGUAGE_CNT_HK
    PyModule_AddIntConstant(module, "LANGUAGE_CNT_HK", LANGUAGE_CNT_HK); //繁体中文
#endif

    /** TRUE/FALSE **/
    PyModule_AddIntConstant(module, "DSQL_TRUE", DSQL_TRUE);
    PyModule_AddIntConstant(module, "DSQL_FALSE", DSQL_FALSE);

    /** RWSEPERATE相关 **/
    PyModule_AddIntConstant(module, "DSQL_RWSEPARATE_ON", DSQL_RWSEPARATE_ON);
    PyModule_AddIntConstant(module, "DSQL_RWSEPARATE_OFF", DSQL_RWSEPARATE_OFF);

    /** trx_state相关 **/
    PyModule_AddIntConstant(module, "DSQL_TRX_ACTIVE", DSQL_TRX_ACTIVE);
    PyModule_AddIntConstant(module, "DSQL_TRX_COMPLETE", DSQL_TRX_COMPLETE);
    
    /** mpp登陆方式相关 **/
    PyModule_AddIntConstant(module, "DSQL_MPP_LOGIN_GLOBAL", DSQL_MPP_LOGIN_GLOBAL);
    PyModule_AddIntConstant(module, "DSQL_MPP_LOGIN_LOCAL", DSQL_MPP_LOGIN_LOCAL);

    /** 回滚后游标状态相关 **/
    PyModule_AddIntConstant(module, "DSQL_CB_CLOSE", DSQL_CB_CLOSE);
    PyModule_AddIntConstant(module, "DSQL_CB_PRESERVE", DSQL_CB_PRESERVE);

    /* CURSOR类型 */
    PyModule_AddIntConstant(module, "TupleCursor", TUPLE_CURSOR);
    PyModule_AddIntConstant(module, "DictCursor", DICT_CURSOR);

    
}

/**增加变量相关**/
static
PyObject*
module_add_var_obj(
    PyObject*       module
)
{    
    MAKE_dmVar_TYPE_READY(&g_IntervalVarType);
    ADD_TYPE_OBJECT("INTERVAL", &g_IntervalVarType);

    MAKE_dmVar_TYPE_READY(&g_YMIntervalVarType);
    ADD_TYPE_OBJECT("YEAR_MONTH_INTERVAL", &g_YMIntervalVarType);

    MAKE_dmVar_TYPE_READY(&g_BLobVarType);
    ADD_TYPE_OBJECT("BLOB", &g_BLobVarType);

    MAKE_dmVar_TYPE_READY(&g_CLobVarType);
    ADD_TYPE_OBJECT("CLOB", &g_CLobVarType);

    MAKE_TYPE_READY(&g_exLobVarType);
    ADD_TYPE_OBJECT("LOB", &g_exLobVarType);

    MAKE_dmVar_TYPE_READY(&g_BFileVarType);
    ADD_TYPE_OBJECT("BFILE", &g_BFileVarType);

    MAKE_TYPE_READY(&g_exBFileVarType);
    ADD_TYPE_OBJECT("exBFILE", &g_exBFileVarType);

    MAKE_dmVar_TYPE_READY(&g_LongBinaryVarType);
    ADD_TYPE_OBJECT("LONG_BINARY", &g_LongBinaryVarType);
    MAKE_dmVar_TYPE_READY(&g_LongStringVarType);
    ADD_TYPE_OBJECT("LONG_STRING", &g_LongStringVarType);

    MAKE_dmVar_TYPE_READY(&g_DateType);
    ADD_TYPE_OBJECT("DATE", &g_DateType);

    MAKE_dmVar_TYPE_READY(&g_TimeType);
    ADD_TYPE_OBJECT("TIME", &g_TimeType);

    MAKE_dmVar_TYPE_READY(&g_TimestampType);
    ADD_TYPE_OBJECT("TIMESTAMP", &g_TimestampType);

    MAKE_dmVar_TYPE_READY(&g_CursorVarType);
    ADD_TYPE_OBJECT("CURSOR", &g_CursorVarType);

    MAKE_dmVar_TYPE_READY(&g_StringType);
    ADD_TYPE_OBJECT("STRING", &g_StringType);

    MAKE_dmVar_TYPE_READY(&g_FixedCharType);
    ADD_TYPE_OBJECT("FIXED_STRING", &g_FixedCharType);

    MAKE_dmVar_TYPE_READY(&g_BinaryType);
    ADD_TYPE_OBJECT("BINARY", &g_BinaryType);

    MAKE_dmVar_TYPE_READY(&g_FixedBinaryType);
    ADD_TYPE_OBJECT("FIXED_BINARY", &g_FixedBinaryType);

#if PY_MAJOR_VERSION < 3
    MAKE_dmVar_TYPE_READY(&g_UnicodeStrType);
    ADD_TYPE_OBJECT("UNICODE_STRING", &g_UnicodeStrType);

    MAKE_dmVar_TYPE_READY(&g_FixedUnicodeCharType);
    ADD_TYPE_OBJECT("FIXED_UNICODE_STRING", &g_FixedUnicodeCharType);
#endif

    MAKE_TYPE_READY(&g_ExternalObjectVarType);    
    MAKE_TYPE_READY(&g_ObjectAttributeType);    
    MAKE_TYPE_READY(&g_ObjectTypeType);    

    ADD_TYPE_OBJECT("objectvar", &g_ExternalObjectVarType);

    MAKE_dmVar_TYPE_READY(&g_ObjectVarType);
    ADD_TYPE_OBJECT("OBJECTVAR", &g_ObjectVarType);

    MAKE_dmVar_TYPE_READY(&g_NumberType);
    ADD_TYPE_OBJECT("NUMBER", &g_NumberType);

    MAKE_dmVar_TYPE_READY(&g_DoubleType);
    ADD_TYPE_OBJECT("DOUBLE", &g_DoubleType);

    MAKE_dmVar_TYPE_READY(&g_FloatType);
    ADD_TYPE_OBJECT("REAL", &g_FloatType);

    MAKE_dmVar_TYPE_READY(&g_BooleanType);
    ADD_TYPE_OBJECT("BOOLEAN", &g_BooleanType);

    MAKE_dmVar_TYPE_READY(&g_NumberStrType);
    ADD_TYPE_OBJECT("DECIMAL", &g_NumberStrType);

    MAKE_dmVar_TYPE_READY(&g_TimeTZType);
    ADD_TYPE_OBJECT("TIME_WITH_TIMEZONE", &g_TimeTZType);

    MAKE_dmVar_TYPE_READY(&g_TimestampTZType);
    ADD_TYPE_OBJECT("TIMESTAMP_WITH_TIMEZONE", &g_TimestampTZType);
    
    MAKE_dmVar_TYPE_READY(&g_BigintType);
    ADD_TYPE_OBJECT("BIGINT", &g_BigintType);

    MAKE_dmVar_TYPE_READY(&g_RowIdType);
    ADD_TYPE_OBJECT("ROWID", &g_RowIdType);
    
    return NULL;
}

/*********************************************
Purpose:
获取dm_svc.conf的路径，不存在返回空
**********************************************/
udbyte *
dmPython_get_svc_path(udbyte* real_path)
{
    udint4      path_len;
    pathname_t  path;
    udbyte*     svc_path = getenv("DM_SVC_PATH");

    //判断环境变量DM_SVC_PATH下是否存在dm_svc.conf
    if (svc_path != NULL && strlen(svc_path) != 0 && strlen(svc_path)< MAX_PATH_LEN + 1)
    {
        path_len = strlen(svc_path);
        if (svc_path[path_len - 1] == DIR_CHAR)
            sprintf(real_path, "%s%s", svc_path, "dm_svc.conf");
        else
            sprintf(real_path, "%s%c%s", svc_path, DIR_CHAR, "dm_svc.conf");
    }

    //如果不存在，则判断系统目录下是否存在dm_svc.conf
    if (*real_path == END ||
        access(real_path, 0) == -1)
    {
#ifdef WIN32
        GetSystemDirectory(path, MAX_PATH_LEN + 1);
#else
        strcpy(path,"/etc");
#endif

        sprintf(real_path, "%s%c%s", path, DIR_CHAR, "dm_svc.conf");
    }

    //文件不存在返回NULL
    if (access(real_path, 0) == -1)
        return NULL;

    return real_path;
}

/*********************************************
Purpose:
从dm_svc.conf读取dmpython_trace的值
**********************************************/
static
sdint2
dmPython_init_trace_mod()
{
    udbyte  path[MAX_PATH_LEN * 2 + 1] = { END };
    udbyte* path_ptr;
    FILE*   file;
    udbyte  line[MAX_LINE_LENGTH];
    udbyte  name[MAX_LINE_LENGTH];
    udbyte  value[MAX_LINE_LENGTH];
    udbyte* cleanname;
    udbyte* cleanvalue;

    //获取dm_svc.conf的路径
    path_ptr = dmPython_get_svc_path(path);
    if (path_ptr == NULL)
    {
        dmpython_trace_mod = DMPYTHON_TRACE_OFF;
        return 0;
    }
    //打开文件，无法打开就将不打开dmPython_trace
    file = fopen(path, "r");
    if (file == NULL )
    {
        dmpython_trace_mod = DMPYTHON_TRACE_OFF;
        return 0;
    }
    //读取DMPYTHON_TRACE的值
    while (fgets(line, sizeof(line), file))
    {
        if (sscanf(line, "%[^=]=(%[^)]", name, value) == 2)
        {
            cleanname = strtok(name, " ");
            cleanvalue = strtok(value, " ");
            if (strcmp(cleanname, "DMPYTHON_TRACE") == 0)
            {
                if (strcmp(cleanvalue, "1") == 0)
                {
                    dmpython_trace_mod = DMPYTHON_TRACE_ON;
                    fclose(file);
                    return 0;
                }
            }
        }
    }

    dmpython_trace_mod = DMPYTHON_TRACE_OFF;
    fclose(file);
    return 0;
}

//-----------------------------------------------------------------------------
// Module_Initialize()
//   Initialization routine for the module.
//-----------------------------------------------------------------------------
static 
PyObject*
Module_Initialize(void)
{
	PyObject *module;	

#ifdef WITH_THREAD
	PyEval_InitThreads();
#endif

	// initialize module and retrieve the dictionary
#if PY_MAJOR_VERSION >= 3
	module = PyModule_Create(&g_ModuleDef);
#else
	module = Py_InitModule("dmPython", g_ModuleMethods);
#endif
	if (!module)
		return NULL;

	if (import_types() < 0)
		return NULL;
	
	
	MAKE_TYPE_READY(&g_ConnectionType);
	MAKE_TYPE_READY(&g_EnvironmentType);
	MAKE_TYPE_READY(&g_ErrorType);
	MAKE_TYPE_READY(&g_CursorType);
	MAKE_TYPE_READY(&RowType);

	// set up the types that are available
	ADD_TYPE_OBJECT("Connection", &g_ConnectionType);
	ADD_TYPE_OBJECT("Environment", &g_EnvironmentType);
	ADD_TYPE_OBJECT("Cursor", &g_CursorType);
    ADD_TYPE_OBJECT("DmError", &g_ErrorType);

	// the name "connect" is required by the DB API
	ADD_TYPE_OBJECT("connect", &g_ConnectionType);
    ADD_TYPE_OBJECT("Connect", &g_ConnectionType);

	// constant from api 2.0
	PyModule_AddStringConstant(module, "apilevel", "2.0");
	PyModule_AddIntConstant(module, "threadsafety", 1);
	PyModule_AddStringConstant(module, "paramstyle", "qmark");

    // add version and build time for easier support
    if (PyModule_AddStringConstant(module, "version",
        BUILD_VERSION_STRING) < 0)
        return NULL;
    if (PyModule_AddStringConstant(module, "buildtime",
        __DATE__ " " __TIME__) < 0)
        return NULL;

    /** 增加常量 **/
    module_add_oper_const(module);

    /** 增加变量相关 **/    
    module_add_var_obj(module);

    /** 初始化对象类型  **/
    /*
	// 和g_StringType等全局变量类型重名，先去掉
#if PY_MAJOR_VERSION < 3
    ADD_TYPE_OBJECT("STRING", &PyString_Type);
#else
    ADD_TYPE_OBJECT("STRING", &PyUnicode_Type);
#endif

    ADD_TYPE_OBJECT("BINARY", &py_Binary_Type);
    ADD_TYPE_OBJECT("Binary", &py_Binary_Type)

    ADD_TYPE_OBJECT("NUMBER", &PyFloat_Type);
    ADD_TYPE_OBJECT("ROWID", &PyLong_Type);
	*/

    Py_INCREF((PyObject*)PyDateTimeAPI->DateTimeType);
    PyModule_AddObject(module, "DATETIME", (PyObject*)PyDateTimeAPI->DateTimeType);    

    Py_INCREF((PyObject*)PyDateTimeAPI->DateTimeType);
    PyModule_AddObject(module, "Timestamp", (PyObject*)PyDateTimeAPI->DateTimeType);  

    Py_INCREF((PyObject*)PyDateTimeAPI->DateType);
    PyModule_AddObject(module, "Date", (PyObject*)PyDateTimeAPI->DateType);  

    Py_INCREF((PyObject*)PyDateTimeAPI->TimeType);
    PyModule_AddObject(module, "Time", (PyObject*)PyDateTimeAPI->TimeType);      


	// create exception object and add it to the dictionary
    if (SetException(module, &g_WarningException,
            "Warning", BASE_EXCEPTION) < 0)
        return NULL;
    if (SetException(module, &g_ErrorException,
            "Error", BASE_EXCEPTION) < 0)
        return NULL;
    if (SetException(module, &g_InterfaceErrorException,
            "InterfaceError", g_ErrorException) < 0)
        return NULL;
    if (SetException(module, &g_DatabaseErrorException,
            "DatabaseError", g_ErrorException) < 0)
        return NULL;
    if (SetException(module, &g_DataErrorException,
            "DataError", g_DatabaseErrorException) < 0)
        return NULL;
    if (SetException(module, &g_OperationalErrorException,
            "OperationalError", g_DatabaseErrorException) < 0)
        return NULL;
    if (SetException(module, &g_IntegrityErrorException,
            "IntegrityError", g_DatabaseErrorException) < 0)
        return NULL;
    if (SetException(module, &g_InternalErrorException,
            "InternalError", g_DatabaseErrorException) < 0)
        return NULL;
    if (SetException(module, &g_ProgrammingErrorException,
            "ProgrammingError", g_DatabaseErrorException) < 0)
        return NULL;
    if (SetException(module, &g_NotSupportedErrorException,
            "NotSupportedError", g_DatabaseErrorException) < 0)
        return NULL;	

    dmPython_init_trace_mod();

	return module;
}

//-----------------------------------------------------------------------------
// Start routine for the module.
//-----------------------------------------------------------------------------
#if PY_MAJOR_VERSION >= 3
PyMODINIT_FUNC PyInit_dmPython(void)
{
	return Module_Initialize();
}
#else
PyMODINIT_FUNC initdmPython(void)
{
	Module_Initialize();
}
#endif

unsigned int                               /*dst的数据长度*/
aq_sprintf_inner(
    char*                  dst,            /*IN:目标缓冲区*/
    int                    dst_len,        /*IN:目标长度*/
    char*                  fmt,            /*IN:格式串*/
    ...                                    /*IN:格式串中的参数*/
)
{
    va_list         argptr;
    unsigned int    len;
    size_t          count;

    count = (size_t)dst_len;

    va_start(argptr, fmt);

#ifdef _WIN32
    //写入字符大于等于size时不加末尾0，大于size时返回-1
    len = _vsnprintf(dst, count, fmt, argptr);
#else
    //写入字符大于等于size时返回源串长度，否则返回写入长度，不含末尾0
    len = vsnprintf(dst, count, fmt, argptr);
#endif

    va_end(argptr);

    return len;
}

#ifdef _DEBUG
#define aq_sprintf(dst, dst_len, fmt, ...)          aq_sprintf_inner(dst, dst_len, fmt, ##__VA_ARGS__)
#else
#define aq_sprintf(dst, dst_len, fmt, ...)          sprintf((char*)dst, (const char*)fmt, ##__VA_ARGS__)
#endif 

int
DmIntNumber_AsInt(
    PyObject* nobj,
    char* pname
)
{
    long        value;
    char        buffer[200];
    int         flag = 0;

#if PY_MAJOR_VERSION < 3
    if (PyInt_Check(nobj))
        flag = 1;
#else
    if (PyLong_Check(nobj))
        flag = 1;
#endif

    if (nobj == NULL || !flag)
    {
        if (pname != NULL)
        {
            aq_sprintf(buffer, 200, "%s : expecting an Integer value.\n", pname);
            PyErr_SetString(PyExc_TypeError, buffer);
        }
        else
        {
            PyErr_SetString(PyExc_TypeError,
                "expecting an Integer value.");
        }

        return -1;
    }

    value = PyLong_AsUnsignedLong(nobj);
    if (PyErr_Occurred())
        return -1;

    if (value > INT_MAX || value < INT_MIN)
    {
        if (pname != NULL)
        {
            aq_sprintf(buffer, 200, "%s : value overflow.\n", pname);
            PyErr_SetString(PyExc_TypeError, buffer);
        }
        else
        {
            PyErr_SetString(PyExc_TypeError,
                "value overflow.");
        }

        return -1;
    }

    return value;
}