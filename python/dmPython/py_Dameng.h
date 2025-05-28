#ifndef _PY_DAMENG_H
#define _PY_DAMENG_H

#ifdef __cplusplus
extern "C" { 			/* Assume C declarations for C++   */
#endif  /* __cplusplus */

#ifndef PY_SSIZE_T_CLEAN
#define PY_SSIZE_T_CLEAN
#endif

#include <Python.h>
#include <structmember.h>

//-----------------------------------------------------------------------------
// maximum number of characters/bytes applicable to strings/binaries
//-----------------------------------------------------------------------------
#define MAX_STRING_CHARS                4094
#define MAX_BINARY_BYTES                8188

#define STRINGIFY(x)                    #x
#define TOSTRING(x)                     STRINGIFY(x)

/** 需同setup.py中保持一致 **/
#ifndef BUILD_VERSION
#define BUILD_VERSION                   2.5.22
#endif

#ifndef BUILD_VERSION_MAJOR
#define BUILD_VERSION_MAJOR             2
#endif

#ifndef BUILD_VERSION_MIN
#define BUILD_VERSION_MIN               2
#endif

#define BUILD_VERSION_STRING            TOSTRING(BUILD_VERSION)

/** 常量定义 **/
#define SHUTDOWN_ABORT                  "ABORT"
#define SHUTDOWN_IMMEDIATE              "IMMEDIATE"
#define SHUTDOWN_TRANSACTIONAL          "TRANSACTIONAL"
#define SHUTDOWN_NORMAL                 "NORMAL"
#define SHUTDOWN_DEFAULT                SHUTDOWN_NORMAL

#define DEBUG_CLOSE                     0
#define DEBUG_OPEN                      1
#define DEBUG_SWITCH                    2
#define DEBUG_SIMPLE                    3

#define TUPLE_CURSOR                    0
#define DICT_CURSOR                     1

#define PY_SQL_MAX_LEN                  (0x8000)


// PY_LONG_LONG was called LONG_LONG before Python 2.3
#ifndef PY_LONG_LONG
#define PY_LONG_LONG LONG_LONG
#endif

// define Py_ssize_t for versions before Python 2.5
#if PY_VERSION_HEX < 0x02050000
typedef int Py_ssize_t;
#define PY_SSIZE_T_MAX INT_MAX
#define PY_SSIZE_T_MIN INT_MIN
#endif

// define T_BOOL for versions before Python 2.5
#ifndef T_BOOL
#define T_BOOL                  T_INT
#endif

// define Py_TYPE for versions before Python 2.6
#ifndef Py_TYPE
#define Py_TYPE(ob)             (((PyObject*)(ob))->ob_type)
#endif

// define PyVarObject_HEAD_INIT for versions before Python 2.6
#ifndef PyVarObject_HEAD_INIT
#define PyVarObject_HEAD_INIT(type, size) \
        PyObject_HEAD_INIT(type) size,
#endif

// define PyInt_* macros for Python 3.x
#ifndef PyInt_Check
#define PyInt_Check             PyLong_Check
#define PyInt_FromLong          PyLong_FromLong
#define PyInt_AsLong            PyLong_AsLong
#define PyInt_Type              PyLong_Type
#endif

//-----------------------------------------------------------------------------
// Globals
//-----------------------------------------------------------------------------
extern PyObject *g_WarningException;
extern PyObject *g_ErrorException;
extern PyObject *g_InterfaceErrorException;
extern PyObject *g_DatabaseErrorException;
extern PyObject *g_DataErrorException;
extern PyObject *g_OperationalErrorException;
extern PyObject *g_IntegrityErrorException;
extern PyObject *g_InternalErrorException;
extern PyObject *g_ProgrammingErrorException;
extern PyObject *g_NotSupportedErrorException;
extern PyTypeObject* g_decimal_type;

extern PyTypeObject g_ConnectionType;
extern PyTypeObject g_CursorType;
extern PyTypeObject RowType;
extern PyTypeObject g_BaseVarType;
extern PyTypeObject g_IntervalVarType;
extern PyTypeObject g_YMIntervalVarType;
extern PyTypeObject g_CLobVarType;
extern PyTypeObject g_BLobVarType;
extern PyTypeObject g_exLobVarType;
extern PyTypeObject g_BFileVarType;
extern PyTypeObject g_exBFileVarType;
extern PyTypeObject g_LongBinaryVarType;
extern PyTypeObject g_LongStringVarType;
extern PyTypeObject g_CursorVarType;
extern PyTypeObject g_DateType;
extern PyTypeObject g_TimeType;
extern PyTypeObject g_TimestampType;
extern PyTypeObject g_ObjectVarType;
extern PyTypeObject g_ObjectAttributeType;
extern PyTypeObject g_ExternalObjectVarType;
extern PyTypeObject g_ObjectTypeType;
extern PyTypeObject g_StringType;
extern PyTypeObject g_FixedCharType;
extern PyTypeObject g_BinaryType;
extern PyTypeObject g_FixedBinaryType;

#if PY_MAJOR_VERSION < 3
extern PyTypeObject g_UnicodeStrType;
extern PyTypeObject g_FixedUnicodeCharType;
#endif

extern PyTypeObject g_NumberType;
extern PyTypeObject g_DoubleType;
extern PyTypeObject g_FloatType;
extern PyTypeObject g_BooleanType;
extern PyTypeObject g_NumberStrType;
extern PyTypeObject g_TimeTZType;
extern PyTypeObject g_TimestampTZType;
extern PyTypeObject g_BigintType;
extern PyTypeObject g_RowIdType;

// use the bytes methods in dmPython and define them as the equivalent string
// type methods as is done in Python 2.6
#ifndef PyBytes_Check
#define PyBytes_Type                PyString_Type
#define PyBytes_AS_STRING           PyString_AS_STRING
#define PyBytes_GET_SIZE            PyString_GET_SIZE
#define PyBytes_Check               PyString_Check
#define PyBytes_Format              PyString_Format
#define PyBytes_FromString          PyString_FromString
#define PyBytes_FromStringAndSize   PyString_FromStringAndSize
#endif

// define string type and methods
#if PY_MAJOR_VERSION >= 3
#define dmString_FromAscii(str) \
	PyUnicode_DecodeASCII(str, strlen(str), NULL)
#define dmString_FromEncodedString(buffer, numBytes, encoding) \
	PyUnicode_Decode(buffer, numBytes, encoding, NULL)
#else
#define dmString_FromAscii(str) \
	PyBytes_FromString(str)
#define dmString_FromEncodedString(buffer, numBytes, encoding) \
	PyBytes_FromStringAndSize(buffer, numBytes)
#endif

// define types and methods for strings and binary data
#if PY_MAJOR_VERSION >= 3
    #define py_Binary_Type               PyBytes_Type
    #define py_Binary_Check              PyBytes_Check
    #define py_String_Type               &PyUnicode_Type
    #define py_String_Format             PyUnicode_Format
    #define py_String_FromFormat         PyUnicode_FromFormat
    #define py_String_FromFormatV        PyUnicode_FromFormatV
    #define py_String_Check              PyUnicode_Check
    #define py_String_asString           PyUnicode_AsUTF8    
    #define TEXT_T                       Py_UNICODE   
#if PY_MINOR_VERSION > 11
    #define py_String_GetSize            PyUnicode_GET_LENGTH
#else
    #define py_String_GetSize            PyUnicode_GET_SIZE
#endif  
#else
    #define py_Binary_Type               PyBuffer_Type
    #define py_Binary_Check              PyBuffer_Check
    #define py_String_Type               &PyBytes_Type
    #define py_String_Format             PyBytes_Format
    #define py_String_FromFormat         PyString_FromFormat
    #define py_String_FromFormatV        PyString_FromFormatV
    #define py_String_Check              PyBytes_Check 
    #define py_String_GetSize            PyBytes_GET_SIZE
    #define py_String_asString           PyString_AsString
    #define TEXT_T                       char
#endif

//-----------------------------------------------------------------------------
// GetModuleAndName()
//   Return the module and name for the type.
//-----------------------------------------------------------------------------
static int GetModuleAndName(
							PyTypeObject *type,                 // type to get module/name for
							PyObject **module,                  // name of module
							PyObject **name)                    // name of type
{
	*module = PyObject_GetAttrString( (PyObject*) type, "__module__");
	if (!*module)
		return -1;
	*name = PyObject_GetAttrString( (PyObject*) type, "__name__");
	if (!*name) {
		Py_DECREF(*module);
		return -1;
	}
	return 0;
}

static
int 
PyDecimal_Check(
	PyObject*   p
)
{
	if (Py_TYPE(p) == (PyTypeObject*)g_decimal_type)
		return 1;
	else
		return 0;
}

int
DmIntNumber_AsInt(
    PyObject*       nobj,
    char*           pname
);

#endif	// _PY_DAMENG_H

