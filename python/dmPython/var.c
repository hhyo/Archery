/******************************************************
file:
    Variable.c
purpose:
    python type define for all DM Variables in dmPython
interface:
    {}
history:
    Date        Who         RefDoc      Memo
    2015-6-4    shenning                Created
*******************************************************/

#include "var_pub.h"
#include "Error.h"
#include "py_Dameng.h"
#include <datetime.h>

//-----------------------------------------------------------------------------
// Declaration of common variable functions.
//-----------------------------------------------------------------------------
static void dmVar_Free(dm_Var *);
static PyObject *dmVar_Repr(dm_Var *);
static PyObject *dmVar_ExternalCopy(dm_Var *, PyObject *);
static PyObject *dmVar_ExternalSetValue(dm_Var *, PyObject *);
static PyObject *dmVar_ExternalGetValue(dm_Var *, PyObject *, PyObject *);


//-----------------------------------------------------------------------------
// declaration of members for variables
//-----------------------------------------------------------------------------
static PyMemberDef g_VariableMembers[] = {
    { "bufferSize",     T_INT, offsetof(dm_Var, bufferSize),          READONLY },    
    { "numElements",    T_INT, offsetof(dm_Var, allocatedElements),   READONLY },    
    { "size",           T_INT, offsetof(dm_Var, size),                READONLY },
    { "maxlength",      T_INT, offsetof(dm_Var, bufferSize),          READONLY },
    { "allocelems",     T_INT, offsetof(dm_Var, allocatedElements),   READONLY },
    { NULL }
};


//-----------------------------------------------------------------------------
// declaration of methods for variables
//-----------------------------------------------------------------------------
static PyMethodDef g_VariableMethods[] = {
    { "copy",       (PyCFunction) dmVar_ExternalCopy,        METH_VARARGS },
    { "setvalue",   (PyCFunction) dmVar_ExternalSetValue,    METH_VARARGS },
    { "getvalue",   (PyCFunction) dmVar_ExternalGetValue,    METH_VARARGS  | METH_KEYWORDS },
    { NULL }
};

//-----------------------------------------------------------------------------
// The base variable type,be the base for all other variables
//-----------------------------------------------------------------------------
PyTypeObject g_BaseVarType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython._BASEVARTYPE",           // tp_name
    sizeof(dm_Var),                     // tp_basicsize
    0,                                  // tp_itemsize
    (destructor) dmVar_Free,            // tp_dealloc
    0,                                  // tp_print
    0,                                  // tp_getattr
    0,                                  // tp_setattr
    0,                                  // tp_compare
    (reprfunc) dmVar_Repr,              // tp_repr
    0,                                  // tp_as_number
    0,                                  // tp_as_sequence
    0,                                  // tp_as_mapping
    0,                                  // tp_hash
    0,                                  // tp_call
    0,                                  // tp_str
    0,                                  // tp_getattro
    0,                                  // tp_setattro
    0,                                  // tp_as_buffer
    Py_TPFLAGS_DEFAULT,                 // tp_flags
    0,                                  // tp_doc
    0,                                  // tp_traverse
    0,                                  // tp_clear
    0,                                  // tp_richcompare
    0,                                  // tp_weaklistoffset
    0,                                  // tp_iter
    0,                                  // tp_iternext
    g_VariableMethods,                  // tp_methods
    g_VariableMembers                   // tp_members
};

//-----------------------------------------------------------------------------
// dmVar_AllocateData()
//   Allocate the data for the variable.
//-----------------------------------------------------------------------------
static 
int 
dmVar_AllocateData(
    dm_Var*       self  /* variable to allocate data for */
)                 
{
#if defined(HAVE_LONG_LONG)
    unsigned PY_LONG_LONG   dataLength;
#else
    unsigned long           dataLength;
#endif

    /* set the buffer size for the variable */
    if (self->type->getBufferSizeProc)
        self->bufferSize = (*self->type->getBufferSizeProc)(self);
    else self->bufferSize = self->size;

    /* allocate the data as long as it is small enough */
#if defined(HAVE_LONG_LONG)
    dataLength = (unsigned PY_LONG_LONG) self->allocatedElements * (unsigned PY_LONG_LONG) self->bufferSize;
#else
    dataLength = (unsigned long) self->allocatedElements * (unsigned long) self->bufferSize;
#endif

    self->data = PyMem_Malloc((size_t) dataLength);
    if (self->data == NULL) 
    {
        PyErr_NoMemory();
        return -1;
    }

    return 0;
}


//-----------------------------------------------------------------------------
// dmVar_New()
//   Allocate a new variable.
//-----------------------------------------------------------------------------
dm_Var*
dmVar_New(
    dm_Cursor*          cursor,         /* cursor to associate variable with */
    udint4              numElements,    /* number of elements to allocate */
    dm_VarType*         type,           /* variable type */
    sdint4              size            /* used only for variable length types */
)                           
{
    dm_Var*             self;
    udint4              i;
    dm_Connection*      conn = cursor->connection;

    // attempt to allocate the object
    self = (dm_Var*) type->pythonType->tp_alloc(type->pythonType, 0);
    if (self == NULL)
    {
        return NULL;
    }

    // perform basic initialization
    Py_INCREF(conn);
    self->connection        = conn;
    //Py_INCREF(cursor->connection->environment);
    self->environment       = conn->environment;
    self->boundCursorHandle = NULL;
    self->boundPos          = 0;
    self->paramdesc         = NULL;  
    self->coldesc           = NULL;
    if (numElements < 1)
    {
        self->allocatedElements = 1;
    }
    else
    {
        self->allocatedElements = numElements;
    }
    self->actualElements        = 0;
    self->internalFetchNum      = 0;
    self->isArray               = 0;
    self->isAllocatedInternally = 1;
    self->type                  = type;
    self->indicator             = NULL;
    self->actualLength          = NULL;
    self->data                  = NULL;    

    // set the maximum length of the variable, ensure that a minimum of
    // 2 bytes is allocated to ensure that the array size check works
    self->size                  = type->size;
    if (type->isVariableLength && size >= 0) 
    {
        self->size              = size;
    }

    // allocate the data for the variable
    if (dmVar_AllocateData(self) < 0) 
    {
        Py_DECREF(self);
        return NULL;
    }

    // allocate the indicator for the variable
    self->indicator     = PyMem_Malloc(self->allocatedElements * sizeof(slength));
    if (self->indicator == NULL) 
    {
        PyErr_NoMemory();
        Py_DECREF(self);
        return NULL;
    }    

    // allocate the actual length for the variable
    self->actualLength  = PyMem_Malloc(self->allocatedElements * sizeof(slength));
    if (self->actualLength == NULL) 
    {
        PyErr_NoMemory();
        Py_DECREF(self);
        return NULL;
    }    

    // ensure that all variable values start out NULL
    for (i = 0; i < self->allocatedElements; i++)
    {
        self->indicator[i]      = DSQL_NULL_DATA;
        self->actualLength[i]   = DSQL_NULL_DATA;
    }

    // perform extended initialization
    if (self->type->initializeProc != NULL) 
    {
        if ((*self->type->initializeProc)(self, cursor) < 0) 
        {
            Py_DECREF(self);
            return NULL;
        }
    }

    return self;
}

void
dmVar_Finalize(
    dm_Var*       self
)
{
    if (self->type->finalizeProc != NULL)
    {
        (*self->type->finalizeProc)(self);
    }
}


//-----------------------------------------------------------------------------
// dmVar_Free()
//   Free an existing variable.
//-----------------------------------------------------------------------------
static 
void 
dmVar_Free(
    dm_Var*       self    // variable to free
)
{
    if (self->isAllocatedInternally) 
    {
        if (self->type->finalizeProc != NULL)
        {
            (*self->type->finalizeProc)(self);
        }

        if (self->indicator != NULL)
        {
            PyMem_Free(self->indicator);
            self->indicator     = NULL;
        }

        if (self->actualLength != NULL)
        {
            PyMem_Free(self->actualLength);
            self->actualLength   = NULL;
        }

        if (self->data != NULL)
        {
            PyMem_Free(self->data);
            self->data          = NULL;
        } 

        Py_CLEAR(self->connection);

        self->isAllocatedInternally = 0;
    }

    //Py_CLEAR(self->environment);    
    Py_TYPE(self)->tp_free((PyObject*) self);
}

//-----------------------------------------------------------------------------
// dmVar_InternalBind()
//   Allocate a variable and bind it to the given statement.
//-----------------------------------------------------------------------------
static 
int
dmVar_InternalBind(
    dm_Var*       var // variable to bind        
)
{
    DPIRETURN       rt = DSQL_SUCCESS; 
    DmParamDesc*    paramdesc;
    dpointer        data_ptr;
    int             iparam;
    int             row;

    paramdesc   = var->paramdesc;

    // perform the bind
    if (var->isArray) 
    {
        /*TODO*/
    } 
    else 
    {
        /** 若为游标类型，则绑定类型均调整为输入输出 **/
        if (Py_TYPE(var) == &g_CursorVarType)
        {
            paramdesc->param_type   = DSQL_PARAM_INPUT_OUTPUT;

            //游标类型，绑定参数不允许为DSQL_NULL_DATA
            for (iparam = 0; iparam < var->allocatedElements; iparam++)
            {
                var->indicator[iparam]      = sizeof(dhstmt);
                var->actualLength[iparam]   = sizeof(dhstmt);
            }
        }

        data_ptr        = (dpointer)var->data;
        //如果为输出参数，并且设置了流式输出属性，则绑定参数为流式输出类型
        if(paramdesc->param_type == DSQL_PARAM_OUTPUT && var->output_stream == 1)
        {
            rt = dpi_bind_param2(var->boundCursorHandle, var->boundPos, DSQL_PARAM_OUTPUT_STREAM, var->type->cType,
                paramdesc->sql_type, paramdesc->prec, paramdesc->scale,
                var->boundPos, var->bufferSize, var->indicator, var->actualLength);
        }
        else
        {
            if(paramdesc->sql_type == DSQL_VARCHAR)
            {
                //考虑到绑定多行的情况，需要检查每一行的最大长度
                for(row = 0; row < var->allocatedElements; row++)
                { 
                    if(var->actualLength[row] > 8188 )
                    { 
                        paramdesc->sql_type = DSQL_CLOB;
                        break;
                    }
                }
            }
            rt = dpi_bind_param2(var->boundCursorHandle, var->boundPos, paramdesc->param_type, var->type->cType, 
                paramdesc->sql_type, paramdesc->prec, paramdesc->scale, 
                data_ptr, var->bufferSize, var->indicator, var->actualLength);
        }
    }
    if (Environment_CheckForError(var->environment, var->boundCursorHandle, DSQL_HANDLE_STMT, rt, 
        "dmVar_InternalBind(): dpi_get_desc_field") < 0) 
    {
        Py_DECREF(var);
        return -1;
    }

    return 0;
}

//-----------------------------------------------------------------------------
// dmVar_Resize()
//   Resize the variable.
//-----------------------------------------------------------------------------
int 
dmVar_Resize(
    dm_Var*         self,   // variable to resize
    unsigned        size    // new size to use
)
{
    udint4          origBufferSize;
    udint4          i;
    char*           origData;

    // allocate the data for the new array
    origData        = self->data;
    origBufferSize  = self->bufferSize;
    self->size      = size;
    if (dmVar_AllocateData(self) < 0)
        return -1;

    // copy the data from the original array to the new array
    for (i = 0; i < self->allocatedElements; i++)
    {
        memcpy( (char*) self->data + self->bufferSize * i,
                (void*) ( (char*) origData + origBufferSize * i ),
                origBufferSize);
    }
    PyMem_Free(origData);

    // force rebinding
    if (self->boundPos > 0) 
    {
        if (dmVar_InternalBind(self) < 0)
            return -1;
    }

    return 0;
}

//-----------------------------------------------------------------------------
// dmVar_Check()
//   Returns a boolean indicating if the object is a variable.
//-----------------------------------------------------------------------------
int 
dmVar_Check(
    PyObject*       object  // Python object to check
)                   
{   
    return (Py_TYPE(object) == &g_IntervalVarType ||
            Py_TYPE(object) == &g_YMIntervalVarType ||
            Py_TYPE(object) == &g_BLobVarType ||
            Py_TYPE(object) == &g_CLobVarType ||
            Py_TYPE(object) == &g_LongStringVarType ||
            Py_TYPE(object) == &g_LongBinaryVarType ||
			Py_TYPE(object) == &g_DateType ||
            Py_TYPE(object) == &g_TimeType ||
			Py_TYPE(object) == &g_TimestampType ||
			Py_TYPE(object) == &g_CursorVarType ||
            Py_TYPE(object) == &g_StringType ||
            Py_TYPE(object) == &g_FixedCharType ||
#if PY_MAJOR_VERSION < 3
            Py_TYPE(object) == &g_UnicodeStrType ||
            Py_TYPE(object) == &g_FixedUnicodeCharType ||
#endif
            Py_TYPE(object) == &g_BinaryType ||
            Py_TYPE(object) == &g_FixedBinaryType ||
            Py_TYPE(object) == &g_NumberType ||
            Py_TYPE(object) == &g_DoubleType ||
            Py_TYPE(object) == &g_FloatType ||
            Py_TYPE(object) == &g_BooleanType ||
            Py_TYPE(object) == &g_NumberStrType ||
            Py_TYPE(object) == &g_ObjectVarType ||
            Py_TYPE(object) == &g_TimeTZType ||
            Py_TYPE(object) == &g_TimestampTZType ||
            Py_TYPE(object) == &g_BigintType ||
            Py_TYPE(object) == &g_RowIdType ||
            Py_TYPE(object) == &g_BFileVarType
            );

}


//-----------------------------------------------------------------------------
// dmVar_TypeByPythonType()
//   Return a variable type given a Python type object or NULL if the Python
// type does not have a corresponding variable type.
//-----------------------------------------------------------------------------
dm_VarType*
dmVar_TypeByPythonType(
    dm_Cursor*      cursor,         // cursor variable created for
    PyObject*       type            // Python type
)
{
    if (type == (PyObject*) &g_StringType)
        return &vt_String;
    if (type == (PyObject*) py_String_Type)
        return &vt_String;
    if (type == (PyObject*) &g_FixedCharType)
        return &vt_FixedChar;

#if PY_MAJOR_VERSION < 3
    if (type == (PyObject*) &g_UnicodeStrType)
        return &vt_UnicodeString;
    if (type == (PyObject*) &PyUnicode_Type)
        return &vt_UnicodeString;
    if (type == (PyObject*) &g_FixedUnicodeCharType)
        return &vt_FixedUnicodeChar;
#endif

    if (type == (PyObject*) &g_BinaryType)
        return &vt_Binary;
    if (type == (PyObject*) &py_Binary_Type)
        return &vt_Binary;

    if (type == (PyObject*) &g_LongStringVarType)
        return &vt_LongString;
    if (type == (PyObject*) &g_LongBinaryVarType)
        return &vt_LongBinary;

    if (type == (PyObject*) &g_BLobVarType)
        return &vt_BLOB;
    if (type == (PyObject*) &g_CLobVarType)
        return &vt_CLOB;

    if (type == (PyObject*) &g_NumberType)
    {
        if (cursor->numbersAsStrings)
            return &vt_NumberAsString;

        return &vt_Float;
    }
    if (type == (PyObject*) &g_NumberStrType)
        return &vt_NumberAsString;
    if (type == (PyObject*) &PyFloat_Type)
        return &vt_Float;
#if PY_MAJOR_VERSION < 3
    if (type == (PyObject*) &PyInt_Type)
        return &vt_Integer;
#endif
    if (type == (PyObject*) &PyLong_Type)
        return &vt_Bigint;
    if (type == (PyObject*) &PyBool_Type)
        return &vt_Boolean;
    if (type == (PyObject*) &g_RowIdType)
        return &vt_Bigint;
    
    //dmPython.BIGING
    if (type == (PyObject*) &g_BigintType)
        return &vt_Bigint;
    
    //dmPython.BOOLEAN
    if (type == (PyObject*) &g_BooleanType)
        return &vt_Boolean;

    //dmPython.REAL
    if (type == (PyObject*) &g_FloatType)
        return &vt_Float;

    if (type == (PyObject*) &g_TimestampType)
        return &vt_Timestamp;
    if (type == (PyObject*) PyDateTimeAPI->DateType)
        return &vt_Date;
    if (type == (PyObject*) PyDateTimeAPI->DateTimeType)
        return &vt_Timestamp;

    //dmPython.DATE
    if (type == (PyObject*) &g_DateType)
        return &vt_Date;

    //decimal.Decimal
    if (type == (PyObject*) g_decimal_type)
        return &vt_NumberAsString;

    if (type == (PyObject*) &g_IntervalVarType)
        return &vt_Interval;
    if (type == (PyObject*) PyDateTimeAPI->DeltaType)
        return &vt_Interval;    
    if (type == (PyObject*) &g_YMIntervalVarType)
        return &vt_YMInterval;

    if (type == (PyObject*) &g_CursorVarType)
        return &vt_Cursor;
    if (type == (PyObject*) &g_ObjectVarType)
        return &vt_Object;

    PyErr_SetString(g_NotSupportedErrorException,
        "dmVar_TypeByPythonType(): unhandled data type");
    return NULL;    
}


//-----------------------------------------------------------------------------
// dmVar_TypeByValue()
//   Return a variable type given a Python object or NULL if the Python
// object does not have a corresponding variable type.
//-----------------------------------------------------------------------------
dm_VarType*
dmVar_TypeByValue(
    PyObject*       value,              // Python type
    udint4*         size               // size to use (OUT)
)              
{    
    char                buffer[200];
    int                 result;
    long                data;
    udint8              size2 = 0;          //参数数据长度
    
    /** 输入为None，则使用vt_string **/
    if (value == Py_None) 
    {
        *size = 1;
        return &vt_String;
    }    

    if (PyDelta_Check(value))
        return &vt_Interval;

    if (py_String_Check(value))
    {
        //获取参数长度
        size2   = py_String_GetSize(value);
        if (size2 > INT_MAX)
        {
            goto fun_end;
        }

        *size   = size2;

        if (*size > MAX_STRING_CHARS)
            return &vt_LongString;

        return &vt_String;
    }

    if (PyBool_Check(value))
        return &vt_Boolean;

#if PY_MAJOR_VERSION >= 3
    if (PyBytes_Check(value))
    {
        //bug584776：插入数据10G，超过了INT类型最大值，导致溢出为一个小于2G的值，从而大字段插入成功，与预期报错不符
        //用udint8先获取绑定参数长度，若超过INT_MAX最大值，则报错，否则再赋值给输出参数
        size2   = PyBytes_GET_SIZE(value);
        if (size2 > INT_MAX)
        {
            goto fun_end;
        }

        *size   = size2;

        if (*size > MAX_BINARY_BYTES)
            return &vt_LongBinary;

        return &vt_Binary;
    }
#else
    if (PyUnicode_Check(value))
    {
        //获取参数长度
        size2   = PyUnicode_GET_SIZE(value);
        if (size2 > INT_MAX)
        {
            goto fun_end;
        }

        *size   = size2;

        if (*size > MAX_STRING_CHARS)
            return &vt_LongString;

        return &vt_UnicodeString;
    }

    if (PyInt_Check(value))
    {
        data = PyInt_AS_LONG(value);
        if (data >= INT_MIN && data <= INT_MAX)
        {
            return &vt_Integer;
        }
        else
        {
            return &vt_Bigint;
        }
    }
#endif

	if (PyDate_CheckExact(value))
        return &vt_Date;

    if (PyDateTime_Check(value))
        return &vt_Timestamp;

    if (PyTime_Check(value))
        return &vt_Time;

    //除bigint外，其他全映射到vt_Integer
    if (PyLong_Check(value))
    {
        /* 超过long范围，映射到bigint */
        data = PyLong_AsLong(value);
        if (data == -1 && PyErr_Occurred())
        {
            PyErr_Clear();
            return &vt_Bigint;
        }

        /* 超过INT_MAX的最大值，也认为是BIGINT，LINUXpyLong_asLong的上限是LONG_MAX(bigint的上限) */
        if (data > INT_MAX || data < INT_MIN)
        {
            return &vt_Bigint;
        }
        
        return &vt_Integer;
    }

    //python只有double类型，对于输入值只对应到vt_Double, vt_Float是对应float类型的，这里不管
    if (PyFloat_Check(value))
        return &vt_Double;

    if (PyDecimal_Check(value))
        return &vt_NumberAsString;

    result = PyObject_IsInstance(value, (PyObject*) &g_CursorType);
    if (result < 0)
        return NULL;
    if (result)
        return &vt_Cursor;

    result = PyObject_IsInstance(value, (PyObject*)&g_CursorVarType);
    if (result < 0)
        return NULL;
    if (result)
        return &vt_Cursor;

    result = PyObject_IsInstance(value, (PyObject*) &g_ExternalObjectVarType);
    if (result < 0)
        return NULL;
    if (result)
    {
        dm_ExternalObjectVar*  ex = (dm_ExternalObjectVar*)value;

        switch (ex->objectType->sql_type)
        {
        case DSQL_CLASS:
            return &vt_Object;

        case DSQL_RECORD:
            return &vt_Record;

        case DSQL_ARRAY:
            return &vt_Array;

        default:
            return &vt_SArray;
        }        
    }

    result  = PyObject_IsInstance(value, (PyObject*)&g_exLobVarType);
    if (result < 0)
        return NULL;
    if (result)
    {
        dm_ExternalLobVar*     exlob = (dm_ExternalLobVar*)value;

        if (exlob->lobVar->type->isCharacterData)
            return &vt_CLOB;

        return &vt_BLOB;
    }

    result  = PyObject_IsInstance(value, (PyObject*)&g_exBFileVarType);
    if (result < 0)
        return NULL;
    if (result)
    {
        return &vt_BFILE;
    }

    //dmPython.BIGINT
    result  = PyObject_IsInstance(value, (PyObject*)&g_BigintType);
    if (result < 0)
        return NULL;
    if (result)
    {
        return &vt_Bigint;
    }

    //dmPython.STRING
    result  = PyObject_IsInstance(value, (PyObject*)&g_StringType);
    if (result < 0)
        return NULL;
    if (result)
    {
        return &vt_String;
    }
    
    //dmPython.BOOLEAN
    result  = PyObject_IsInstance(value, (PyObject*)&g_BooleanType);
    if (result < 0)
        return NULL;
    if (result)
    {
        return &vt_Boolean;
    }

    //dmPython.BINARY
    result  = PyObject_IsInstance(value, (PyObject*)&g_BinaryType);
    if (result < 0)
        return NULL;
    if (result)
    {
        return &vt_Binary;
    }

    //dmPython.DATE
    result  = PyObject_IsInstance(value, (PyObject*)&g_DateType);
    if (result < 0)
        return NULL;
    if (result)
    {
        return &vt_Date;
    }

    //dmPython.TIMESTAMP
    result  = PyObject_IsInstance(value, (PyObject*)&g_TimestampType);
    if (result < 0)
        return NULL;
    if (result)
    {
        return &vt_Timestamp;
    }

    //dmPython.INTERVAL
    result  = PyObject_IsInstance(value, (PyObject*)&g_IntervalVarType);
    if (result < 0)
        return NULL;
    if (result)
    {
        return &vt_Interval;
    }

    //dmPython.REAL
    result  = PyObject_IsInstance(value, (PyObject*)&g_FloatType);
    if (result < 0)
        return NULL;
    if (result)
    {
        return &vt_Float;
    }

    //dmPython.DECIMAL
    result  = PyObject_IsInstance(value, (PyObject*)&g_NumberStrType);
    if (result < 0)
        return NULL;
    if (result)
    {
        return &vt_NumberAsString;
    }

fun_end:

    if (size2 > INT_MAX)
    {
        //参数长度超过INT_MAX大小，则报错返回
        sprintf(buffer, "dmVar_TypeByValue(): invalid date len %lld", size2);
        PyErr_SetString(g_NotSupportedErrorException, buffer);
    }
    else
    {
        sprintf(buffer, "dmVar_TypeByValue(): unhandled data type %.*s", 150,
            Py_TYPE(value)->tp_name);
        PyErr_SetString(g_NotSupportedErrorException, buffer);
    }
	
    return NULL;
}


//-----------------------------------------------------------------------------
// dmVar_TypeBySQLType()
//   Return a variable type given an SQL type or NULL if the SQL type does not have a corresponding variable type.
//-----------------------------------------------------------------------------
dm_VarType*
dmVar_TypeBySQLType (
    udint2      sqlType,             // SQL type, SQL_XXX
    int         value_flag           // 仅LOB类型有效，用于判断是取LOB对象还是取LOB对象中的值
)
{
    char buffer[100];

    switch (sqlType)
    {
    case DSQL_INTERVAL_DAY:
    case DSQL_INTERVAL_HOUR:
    case DSQL_INTERVAL_MINUTE:
    case DSQL_INTERVAL_SECOND:
    case DSQL_INTERVAL_DAY_TO_HOUR:
    case DSQL_INTERVAL_DAY_TO_MINUTE:
    case DSQL_INTERVAL_DAY_TO_SECOND:
    case DSQL_INTERVAL_HOUR_TO_MINUTE:
    case DSQL_INTERVAL_HOUR_TO_SECOND:
    case DSQL_INTERVAL_MINUTE_TO_SECOND:
        return &vt_Interval;   

    case DSQL_INTERVAL_YEAR:
    case DSQL_INTERVAL_MONTH:
    case DSQL_INTERVAL_YEAR_TO_MONTH:
        return &vt_YMInterval;

    case DSQL_BLOB:
        if (value_flag)
            return &vt_LongBinary;

        return &vt_BLOB;

    case DSQL_CLOB:
        if (value_flag)
            return &vt_LongString;

        return &vt_CLOB;
		
    case DSQL_DATE:
        return &vt_Date;

    case DSQL_TIME:
        return &vt_Time;

    case DSQL_TIMESTAMP:
        return &vt_Timestamp;
		
	case DSQL_RSET:
        return &vt_Cursor;

    case DSQL_CHAR:
        return &vt_FixedChar;

    case DSQL_VARCHAR:
        return &vt_String;

    case DSQL_BINARY:
        return &vt_FixedBinary;

    case DSQL_VARBINARY:
        return &vt_Binary;

    case DSQL_ARRAY:
        return &vt_Array;

    case DSQL_SARRAY:
        return &vt_SArray;

    case DSQL_CLASS:
        return &vt_Object;

    case DSQL_RECORD:
        return &vt_Record;

	/* 下面三种都按照integer类型处理 */
    case DSQL_INT:
    case DSQL_TINYINT:
    case DSQL_SMALLINT:
        return &vt_Integer;
#ifdef DSQL_ROWID
	case DSQL_ROWID:
		return &vt_RowId;
#endif
    case DSQL_BIGINT:
        return &vt_Bigint; //vt_RowId

    case DSQL_DOUBLE:
        return &vt_Double;

    case DSQL_FLOAT:
        return &vt_Float;

    case DSQL_DEC:
        return &vt_NumberAsString;

    case DSQL_BIT:
        return &vt_Boolean;

    case DSQL_TIME_TZ:
        return &vt_TimeTZ;

    case DSQL_TIMESTAMP_TZ:
        return &vt_TimestampTZ;

    case DSQL_BFILE:
        return &vt_BFILE;
		
    default:
        break;
    }

    sprintf(buffer, "dmVar_TypeBySQLType: unhandled data type %d",
            sqlType);
    PyErr_SetString(g_NotSupportedErrorException, buffer);
    return NULL;
}

//-----------------------------------------------------------------------------
// dmVar_DefaultNewByValue()
//   Default method for determining the type of variable to use for the data.
//-----------------------------------------------------------------------------
static 
dm_Var*
dmVar_DefaultNewByValue(
    dm_Cursor*      cursor,             // cursor to associate variable with
    PyObject*       value,              // Python value to associate
    unsigned        numElements,         // number of elements to allocate
    unsigned        ipos                /*参数绑定序号1-based*/
)               
{
    dm_VarType*   varType;
    dm_VarType*   varType_tmp;
    dm_Var*       var;
    sdint4              size = -1;       

    /* value 为none,且为输出或者输入输出参数，则根据参数描述sqltype，获取变量类型 */
    if (value == Py_None &&
        (cursor->bindParamDesc[ipos - 1].param_type == DSQL_PARAM_INPUT_OUTPUT ||
         cursor->bindParamDesc[ipos - 1].param_type == DSQL_PARAM_OUTPUT))
    {
        varType = dmVar_TypeBySQLType(cursor->bindParamDesc[ipos - 1].sql_type, 0);
    }
    else
    {        
        varType = dmVar_TypeByValue(value, &size);

        if (cursor->bindParamDesc[ipos - 1].param_type == DSQL_PARAM_INPUT_OUTPUT ||
            cursor->bindParamDesc[ipos - 1].param_type == DSQL_PARAM_OUTPUT )
        {
            varType_tmp = dmVar_TypeBySQLType(cursor->bindParamDesc[ipos - 1].sql_type, 1);    
            if (varType == &vt_String || varType == &vt_Binary)
            {
                if (varType == varType_tmp ||
                    varType_tmp == &vt_LongString ||varType_tmp == &vt_LongBinary)
                {
                    varType = varType_tmp;
                    size    = -1;
                }                
            }            
        }
    }

    if (!varType)
    {
        return NULL;
    }

    var = dmVar_New(cursor, numElements, varType, size);
    if (!var)
    {
        return NULL;
    }

    /** 若为复合类型，则需先生成句柄对象 **/
    if (var->type->pythonType == &g_ObjectVarType)
    {
        if (ObjectVar_GetParamDescAndObjHandles((dm_ObjectVar*)var, cursor->hdesc_param, ipos) < 0)
            return NULL;
    }


    return var;
}


//-----------------------------------------------------------------------------
// dmVar_NewByValue()
//   Allocate a new variable by looking at the type of the data.
//-----------------------------------------------------------------------------
dm_Var*
dmVar_NewByValue(
    dm_Cursor*      cursor,         // cursor to associate variable with
    PyObject*       value,          // Python value to associate
    unsigned        numElements,     // number of elements to allocate
    unsigned        ipos            /* 参数绑定序号1-based */
)               
{     
    return dmVar_DefaultNewByValue(cursor, value, numElements, ipos);
}


//-----------------------------------------------------------------------------
// dmVar_NewArrayByType()
//   Allocate a new PL/SQL array by looking at the Python data type.
//----------------------------------------------------------------------------


//-----------------------------------------------------------------------------
// dmVar_NewByType()
//   Allocate a new variable by looking at the Python data type.
//-----------------------------------------------------------------------------
dm_Var*
dmVar_NewByType(
    dm_Cursor*  cursor,         // cursor to associate variable with
    PyObject*   value,            // Python data type to associate
    unsigned    numElements        // number of elements to allocate
)
{
    dm_VarType*   varType;

#if PY_MAJOR_VERSION < 3
    int                 size;
#else
    long                size;
#endif

    // passing an integer is assumed to be a string
#if PY_MAJOR_VERSION < 3
    if (PyInt_Check(value)) 
    {
        size    = PyInt_AsLong(value);
#else
    if (PyLong_Check(value)) 
    {
        size    = PyLong_AsLong(value);    
#endif
        if (PyErr_Occurred())
            return NULL;

        if (size > MAX_STRING_CHARS)
            varType = &vt_LongString;
        else 
            varType = &vt_String;

        return dmVar_New(cursor, numElements, varType, size);
    }

    // handle directly bound variables
    if (dmVar_Check(value)) 
    {
        Py_INCREF(value);
        return (dm_Var*) value;
    }

    // everything else ought to be a Python type
    varType = dmVar_TypeByPythonType(cursor, value);
    if (varType == NULL)
    {
        return NULL;
    }

    return dmVar_New(cursor, numElements, varType, varType->size);
}

dm_Var*
dmVar_NewByVarType(
    dm_Cursor*          cursor,         // cursor to associate variable with
    dm_VarType*         varType,            // Python data type to associate
    unsigned            numElements,        // number of elements to allocate
    udint4              size            // buffer length to alloc
)
{
    udint4              alloc_size = varType->size;

    if ((sdint4)size > 0)
        alloc_size  = size;

    return dmVar_New(cursor, numElements, varType, alloc_size);
}

//-----------------------------------------------------------------------------
// dmVar_Define()
//   Allocate a variable and define it for the given statement.
//----------------------------------------------------------------------------- 
dm_Var*
dmVar_Define(
    dm_Cursor*      cursor,         // cursor in use
    dhdesc          hdesc_col,
    udint2          position,       // position in define list
    udint4          numElements,    // number of elements to create
    udint2          varchar_flag    // whether used DSQL_ATTR_NLS_NUMERIC_CHARACTERS
)               
{
    DPIRETURN           rt = DSQL_SUCCESS;
    dm_VarType*         varType;    
    dm_Var*             var;    
    udint4              size;
    slength		        dm_size = 0;
    DmColDesc*          coldesc;

    coldesc     = &cursor->bindColDesc[position - 1];
    dm_size     = coldesc->display_size;

    // determine data type
    varType     = dmVar_TypeBySQLType(coldesc->sql_type, 0);
    if (varType == NULL)
    {
        return NULL;
    }

    if (varchar_flag == 1)
    {
        if (coldesc->sql_type == DSQL_DEC || coldesc->sql_type == DSQL_FLOAT || coldesc->sql_type == DSQL_DOUBLE ||
            coldesc->sql_type == DSQL_TIME || coldesc->sql_type == DSQL_TIMESTAMP || coldesc->sql_type == DSQL_TIME_TZ ||
            coldesc->sql_type == DSQL_TIMESTAMP_TZ)
            varType = &vt_String;
    }

    // retrieve size of the parameter
    size        = varType->size;
    if (varType->isVariableLength) {
        
        // use the length from DM directly if available,otherwise, use the value set with the setoutputsize() parameter
        if (dm_size != 0)
        {
            size = dm_size;
        }
        else if (cursor->outputSize >= 0) 
        {
            if (cursor->outputSizeColumn < 0 || (int) position == cursor->outputSizeColumn)
            {
                size = cursor->outputSize;
            }
        }
    }

    // create a variable of the correct type
    var     = dmVar_New(cursor, numElements, varType, size);
    if (var == NULL)
    {
        return NULL;
    }

    // call the procedure to set values prior to define
    if (var->type->preDefineProc != NULL)
    {
        if ((*var->type->preDefineProc)(var, hdesc_col, position) < 0) 
        {
            Py_DECREF(var);
            return NULL;
        }
    }

    var->coldesc = &cursor->bindColDesc[position - 1];

    // perform the define
    rt      = dpi_bind_col2((cursor->handle), position, var->type->cType, (dpointer)var->data, var->bufferSize, var->indicator, var->actualLength);
    if (Environment_CheckForError(var->environment, cursor->handle, DSQL_HANDLE_STMT, rt, 
        "dmVar_Define(): dpi_bind_col2") < 0) 
    {
            Py_DECREF(var);
            return NULL;
    }    

    return var;
}


//-----------------------------------------------------------------------------
// dmVar_Bind()
//   Allocate a variable and bind it to the given statement.
//-----------------------------------------------------------------------------
int 
dmVar_Bind(
    dm_Var*        var,     // variable to bind
    dm_Cursor*     cursor,  // cursor to bind to    
    udint2          pos      // position to bind to, 1-based
)                            
{
    // nothing to do if already bound
    if (pos > 0 && pos == var->boundPos)
        return 0;

    // set the instance variables specific for binding
    var->boundPos           = pos;
    var->boundCursorHandle  = cursor->handle;
    var->paramdesc          = &cursor->bindParamDesc[pos - 1];
    var->output_stream      = cursor->output_stream;
    // perform the bind
    return dmVar_InternalBind(var);
}


//-----------------------------------------------------------------------------
// dmVar_GetSingleValue()
//   Return the value of the variable at the given position.
//-----------------------------------------------------------------------------
static 
PyObject*
dmVar_GetSingleValue(
    dm_Var*         var,        // variable to get the value for
    udint4          arrayPos    // array position
)                  
{    
    int isNull;

    // ensure we do not exceed the number of allocated elements
    if (arrayPos >= var->allocatedElements) {
        PyErr_SetString(PyExc_IndexError,
            "dmVar_GetSingleValue: array size exceeded");
        return NULL;
    }

    // check for a NULL value
    if (var->type->isNullProc != NULL)
    {
        isNull = (*var->type->isNullProc)(var, arrayPos);
    }
    else
    {
        isNull = (var->indicator[arrayPos] == DSQL_NULL_DATA);
    }
    if (isNull) 
    {
        Py_INCREF(Py_None);
        return Py_None;
    }    

    // calculate value to return
    return (*var->type->getValueProc)(var, arrayPos);        
}


//-----------------------------------------------------------------------------
// dmVar_GetArrayValue()
//   Return the value of the variable as an array.
//-----------------------------------------------------------------------------
static 
PyObject*
dmVar_GetArrayValue(
    dm_Var*         var,            // variable to get the value for
    udint4          numElements     // number of elements to include
)                    
{
    PyObject*       value;
    PyObject*       singleValue;
    udint4          i;

    value   = PyList_New(numElements);
    if (value == NULL)
    {
        if (!PyErr_Occurred())
        {
            PyErr_NoMemory();
        }

        return NULL;
    }

    for (i = 0; i < numElements; i++) 
    {
        singleValue = dmVar_GetSingleValue(var, i);
        if (!singleValue) 
        {
            Py_DECREF(value);
            return NULL;
        }

        PyList_SET_ITEM(value, i, singleValue);
    }

    return value;
}


//-----------------------------------------------------------------------------
// dmVar_GetValue()
//   Return the value of the variable.
//-----------------------------------------------------------------------------
PyObject*
dmVar_GetValue(
    dm_Var*         var,      // variable to get the value for
    udint4          arrayPos  // array position
)
{
    if (var->isArray)
        return dmVar_GetArrayValue(var, var->actualElements);

    return dmVar_GetSingleValue(var, arrayPos);
}


//-----------------------------------------------------------------------------
// dmVar_SetSingleValue()
//   Set a single value in the variable.
//-----------------------------------------------------------------------------
static 
int
dmVar_SetSingleValue(
    dm_Var*             var,        // variable to set value for
    udint4              arrayPos,   // array position
    PyObject*           value       // value to set
)                    
{        
    // ensure we do not exceed the number of allocated elements
    if (arrayPos >= var->allocatedElements)
    {
        PyErr_SetString(PyExc_IndexError,
            "dmVar_SetSingleValue: array size exceeded");

        return -1;
    }

    // check for a NULL value
    if (value == Py_None) 
    {
        if (Py_TYPE(var) == &g_CursorVarType)
        {
            var->indicator[arrayPos]    = sizeof(dhstmt);
            var->actualLength[arrayPos] = sizeof(dhstmt);
        }        
        else
        {            
            var->indicator[arrayPos] = DSQL_NULL_DATA;            
        }

        return 0;
    }    

    /*将value转换为var->data，并计算var->indicator[arrayPos]*/
    return (*var->type->setValueProc)(var, arrayPos, value);
}

//-----------------------------------------------------------------------------
// dmVar_SetValue()
//   Set the value of the variable.
//----------------------------------------------------------------------------- 
int 
dmVar_SetValue(
    dm_Var*         var,        // variable to set
    udint4          arrayPos,   // array position
    PyObject*       value       // value to set
)
{
    return dmVar_SetSingleValue(var, arrayPos, value);
}

int
dmVar_BindObjectValue(
    dm_Var*         var,
    udint4          arrayPos,
    dhobj           obj_hobj,
    udint4          value_nth
)
{    
    return (*var->type->bindObjectValueProc)(var, arrayPos, obj_hobj, value_nth);
}


//-----------------------------------------------------------------------------
// dmVar_ExternalCopy()
//   Copy the contents of the source variable to the destination variable.
//-----------------------------------------------------------------------------
static
PyObject*
dmVar_ExternalCopy(
    dm_Var*         targetVar,  // variable to set
    PyObject*       args        // arguments
)                     
{
    udint4          sourcePos;
    udint4          targetPos;
    dm_Var*         sourceVar;

    // parse arguments; verify that copy is possible
    if (!PyArg_ParseTuple(args, "Oii", &sourceVar, &sourcePos, &targetPos))
    {
        return NULL;
    }

    if (Py_TYPE(targetVar) != Py_TYPE(sourceVar)) 
    {
        PyErr_SetString(g_ProgrammingErrorException,
            "source and target variable type must match");
        return NULL;
    }

    if (!sourceVar->type->canBeCopied) 
    {
        PyErr_SetString(g_ProgrammingErrorException,
            "variable does not support copying");

        return NULL;
    }

    // ensure array positions are not violated
    if (sourcePos >= sourceVar->allocatedElements) 
    {
        PyErr_SetString(PyExc_IndexError,
            "dmVar_ExternalCopy: source array size exceeded");

        return NULL;
    }

    if (targetPos >= targetVar->allocatedElements) 
    {
        PyErr_SetString(PyExc_IndexError,
            "dmVar_ExternalCopy: target array size exceeded");

        return NULL;
    }

    // ensure target can support amount data from the source
    if (targetVar->bufferSize < sourceVar->bufferSize) 
    {
        PyErr_SetString(g_ProgrammingErrorException,
            "target variable has insufficient space to copy source data");

        return NULL;
    }

    // handle null case directly,otherwise, copy data
    if (sourceVar->indicator[sourcePos] == DSQL_NULL_DATA)
    {
        targetVar->indicator[targetPos] = DSQL_NULL_DATA;
    }
    else 
    {
        targetVar->indicator[targetPos] = DSQL_NULL_DATA;
        
        if (targetVar->actualLength)
            targetVar->actualLength[targetPos] =
            sourceVar->actualLength[sourcePos];
        
        memcpy((char*)targetVar->data + targetPos * targetVar->bufferSize,
               (char*)sourceVar->data + sourcePos * sourceVar->bufferSize,
               sourceVar->bufferSize);
    }

    Py_INCREF(Py_None);
    return Py_None;
}


//-----------------------------------------------------------------------------
// dmVar_ExternalSetValue()
//   Set the value of the variable at the given position.
//-----------------------------------------------------------------------------
static 
PyObject*
dmVar_ExternalSetValue(
    dm_Var*             var,        // variable to set
    PyObject*           args        // arguments
)                     
{
    PyObject*       value;
    udint4          pos;

    if (!PyArg_ParseTuple(args, "iO", &pos, &value))
    {
        return NULL;
    }

    if (dmVar_SetValue(var, pos, value) < 0)
    {
        return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}


//-----------------------------------------------------------------------------
// dmVar_ExternalGetValue()
//   Return the value of the variable at the given position.
//-----------------------------------------------------------------------------
static 
PyObject*
dmVar_ExternalGetValue(
    dm_Var*             var,        // variable to set
    PyObject*           args,       // arguments
    PyObject*           keywordArgs // keyword arguments
)
{
    static char *keywordList[] = { "pos", NULL };
    udint4 pos = 0;

    if (!PyArg_ParseTupleAndKeywords(args, keywordArgs, "|i", keywordList, &pos))
        return NULL;

    return dmVar_GetValue(var, pos);
}


//-----------------------------------------------------------------------------
// dmVar_Repr()
//   Return a string representation of the variable.
//-----------------------------------------------------------------------------
static 
PyObject*
dmVar_Repr(
    dm_Var*       var // variable to return the string for
)
{
    PyObject*   valueRepr;
    PyObject*   value;
    PyObject*   module;
    PyObject*   name;
    PyObject*   result;
    PyObject*   format;
    PyObject*   formatArgs;

    if (var->isArray)
    {
        value = dmVar_GetArrayValue(var, var->actualElements);
    }
    else if (var->allocatedElements == 1)
    {
        value = dmVar_GetSingleValue(var, 0);
    }
    else
    {
        value = dmVar_GetArrayValue(var, var->allocatedElements);
    }
    if (value == NULL)
        return NULL;

    valueRepr = PyObject_Repr(value);
    Py_DECREF(value);
    if (valueRepr == NULL)
        return NULL;

    format = dmString_FromAscii("<%s.%s with value %s>");
    if (!format) 
    {
        Py_DECREF(valueRepr);
        return NULL;
    }

    if (GetModuleAndName(Py_TYPE(var), &module, &name) < 0) 
    {
        Py_DECREF(valueRepr);
        Py_DECREF(format);

        return NULL;
    }

    formatArgs = PyTuple_Pack(3, module, name, valueRepr);
    Py_DECREF(module);
    Py_DECREF(name);
    Py_DECREF(valueRepr);

    if (!formatArgs) 
    {
        Py_DECREF(format);
        return NULL;
    }

    result = py_String_Format(format, formatArgs);
    Py_DECREF(format);
    Py_DECREF(formatArgs);

    return result;
}


//-----------------------------------------------------------------------------
// dmVar_IsNull()
//   Return 1 if all value in var is NULL.
//----------------------------------------------------------------------------- 
int
dmVar_IsNull(
    dm_Var*       var // variable to return the string for
)
{
    udint4          i;

    for (i = 0; i < var->actualElements; i ++)
    {
        if (var->indicator[i] != DSQL_NULL_DATA)
            return 0;
    }

    return 1;
}

//-----------------------------------------------------------------------------
// dmVar_Import()
//   import op for some variables
//----------------------------------------------------------------------------- 
void
dmVar_Import()
{
    PyDateTime_IMPORT;

    IntervalVar_import();

    DateVar_import();
}

//-----------------------------------------------------------------------------
// dmVar_PutDataAftExec()
//   import op for some variables
//----------------------------------------------------------------------------- 
int
dmVar_PutDataAftExec(
    dm_Var*         var,        // for variable to put data
    udint4          arrayPos    // array position
)
{
    /* 仅long string or long binary->DSQL_DATA_AT_EXEC */
    if (var->actualLength[arrayPos] == DSQL_NULL_DATA ||
        var->indicator[arrayPos] != DSQL_DATA_AT_EXEC)
    {
        return 0;
    }

    return vLong_PutData((dm_LongVar*)var, arrayPos);
}

