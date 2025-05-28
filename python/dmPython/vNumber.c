/******************************************************
file:
    vNumber.c
purpose:
    python type define for DM number variables in dmPython
    include: 
             byte/tinyint/smallint/int/integer/bigint
             float/double/double precision
             real
             numeric/number/decimal/dec

interface:
    {}
history:
    Date        Who         RefDoc      Memo
    2015-6-10   wmm                     Created
*******************************************************/

#include "var_pub.h"
#include "Error.h"
#include "py_Dameng.h"
#include "Buffer.h"
#include "Error.h"

//-----------------------------------------------------------------------------
// Declaration of number variable functions.
//-----------------------------------------------------------------------------
static int NumberVar_SetValue(dm_NumberVar*, unsigned, PyObject*);
static PyObject *NumberVar_GetValue(dm_NumberVar*, unsigned);
static int NumberVar_BindObjectValue(dm_NumberVar*, unsigned, dhobj, udint4);

static int DoubleVar_SetValue(dm_DoubleVar*, unsigned, PyObject*);
static PyObject *DoubleVar_GetValue(dm_DoubleVar*, unsigned);
static int DoubleVar_BindObjectValue(dm_DoubleVar*, unsigned, dhobj, udint4);

static int FloatVar_SetValue(dm_FloatVar*, unsigned, PyObject*);
static PyObject *FloatVar_GetValue(dm_FloatVar*, unsigned);
static int FloatVar_BindObjectValue(dm_FloatVar*, unsigned, dhobj, udint4);

static int NumberStrVar_SetValue(dm_NumberStrVar*, unsigned, PyObject*);
static PyObject *NumberStrVar_GetValue(dm_NumberStrVar*, unsigned);
static int NumberStrVar_BindObjectValue(dm_NumberStrVar*, unsigned, dhobj, udint4);

static int BigintVar_SetValue(dm_BigintVar*, unsigned, PyObject*);
static PyObject *BigintVar_GetValue(dm_BigintVar*, unsigned);
static int BigintVar_BindObjectValue(dm_BigintVar*, unsigned, dhobj, udint4);

static int Base64Var_SetValue(dm_Base64Var*, unsigned, PyObject*);
static PyObject *Base64Var_GetValue(dm_Base64Var*, unsigned);
static int Base64Var_BindObjectValue(dm_Base64Var*, unsigned, dhobj, udint4);

//-----------------------------------------------------------------------------
// Python type declaration
//-----------------------------------------------------------------------------
PyTypeObject g_NumberType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.NUMBER",                  // tp_name
    sizeof(dm_NumberVar),               // tp_basicsize
    0,                                  // tp_itemsize
    0,                                  // tp_dealloc
    0,                                  // tp_print
    0,                                  // tp_getattr
    0,                                  // tp_setattr
    0,                                  // tp_compare
    0,                                  // tp_repr
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
    0                                   // tp_doc
};

PyTypeObject g_BigintType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.BIGINT",                  // tp_name
    sizeof(dm_BigintVar),               // tp_basicsize
    0,                                  // tp_itemsize
    0,                                  // tp_dealloc
    0,                                  // tp_print
    0,                                  // tp_getattr
    0,                                  // tp_setattr
    0,                                  // tp_compare
    0,                                  // tp_repr
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
    0                                   // tp_doc
};

PyTypeObject g_RowIdType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.ROWID",                   // tp_name
    sizeof(dm_Base64Var),               // tp_basicsize
    0,                                  // tp_itemsize
    0,                                  // tp_dealloc
    0,                                  // tp_print
    0,                                  // tp_getattr
    0,                                  // tp_setattr
    0,                                  // tp_compare
    0,                                  // tp_repr
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
    0                                   // tp_doc
};

PyTypeObject g_BooleanType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.BOOLEAN",                 // tp_name
    sizeof(dm_NumberVar),               // tp_basicsize
    0,                                  // tp_itemsize
    0,                                  // tp_dealloc
    0,                                  // tp_print
    0,                                  // tp_getattr
    0,                                  // tp_setattr
    0,                                  // tp_compare
    0,                                  // tp_repr
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
    0                                   // tp_doc
};

PyTypeObject g_DoubleType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.DOUBLE",                  // tp_name
    sizeof(dm_DoubleVar),               // tp_basicsize
    0,                                  // tp_itemsize
    0,                                  // tp_dealloc
    0,                                  // tp_print
    0,                                  // tp_getattr
    0,                                  // tp_setattr
    0,                                  // tp_compare
    0,                                  // tp_repr
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
    0                                   // tp_doc
};

PyTypeObject g_FloatType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.REAL",                    // tp_name
    sizeof(dm_FloatVar),                // tp_basicsize
    0,                                  // tp_itemsize
    0,                                  // tp_dealloc
    0,                                  // tp_print
    0,                                  // tp_getattr
    0,                                  // tp_setattr
    0,                                  // tp_compare
    0,                                  // tp_repr
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
    0                                   // tp_doc
};


PyTypeObject g_NumberStrType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.DECIMAL",                 // tp_name
    sizeof(dm_NumberStrVar),            // tp_basicsize
    0,                                  // tp_itemsize
    0,                                  // tp_dealloc
    0,                                  // tp_print
    0,                                  // tp_getattr
    0,                                  // tp_setattr
    0,                                  // tp_compare
    0,                                  // tp_repr
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
    0                                   // tp_doc
};

//-----------------------------------------------------------------------------
// variable type declarations
//-----------------------------------------------------------------------------
dm_VarType vt_Float = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) FloatVar_SetValue,
    (GetValueProc) FloatVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)FloatVar_BindObjectValue,
    &g_FloatType,                       // Python type
    DSQL_C_NCHAR,                       // c type
    64,                                 // element length
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};

dm_VarType vt_Double = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) DoubleVar_SetValue,
    (GetValueProc) DoubleVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)DoubleVar_BindObjectValue,
    &g_DoubleType,                      // Python type
    DSQL_C_DOUBLE,                      // c type
    sizeof(double),                     // element length
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};

dm_VarType vt_Bigint = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) BigintVar_SetValue,
    (GetValueProc) BigintVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc) BigintVar_BindObjectValue,
    &g_BigintType,                      // Python type
    DSQL_C_NCHAR,                       // C type
    32,                                 // element length，精度为19
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};


dm_VarType vt_Integer = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) NumberVar_SetValue,
    (GetValueProc) NumberVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc) NumberVar_BindObjectValue,
    &g_NumberType,                      // Python type
    DSQL_C_SLONG,                       // C type
    sizeof(sdint4),                       // element length
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};

/*
dm_VarType vt_LongInteger = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) NumberVar_SetValue,
    (GetValueProc) NumberVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)NumberVar_BindObjectValue,
    &g_NumberType,                      // Python type
    DSQL_C_SBIGINT,                     // c type
    sizeof(sdint8),                     // element length
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};*/

dm_VarType vt_RowId = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) Base64Var_SetValue,
    (GetValueProc) Base64Var_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc) Base64Var_BindObjectValue,
    &g_RowIdType,                      // Python type
    DSQL_C_NCHAR,                       // C type
    32,                                 // element length
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};

dm_VarType vt_TinyInteger = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) NumberVar_SetValue,
    (GetValueProc) NumberVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)NumberVar_BindObjectValue,
    &g_NumberType,                      // Python type
    DSQL_C_SLONG,                       // C type
    sizeof(sdint4),                     // element length
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};

dm_VarType vt_SmallInteger = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) NumberVar_SetValue,
    (GetValueProc) NumberVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)NumberVar_BindObjectValue,
    &g_NumberType,                      // Python type
    DSQL_C_SLONG,                       // C type
    sizeof(sdint4),                     // element length
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};

dm_VarType vt_NumberAsString = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) NumberStrVar_SetValue,
    (GetValueProc) NumberStrVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)NumberVar_BindObjectValue,
    &g_NumberStrType,                   // Python type
    DSQL_C_NCHAR,                       // C type，decimal类型以字符串形式写入
    256,                                 // element length，预留256字节空间
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};


dm_VarType vt_Boolean = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) NumberVar_SetValue,
    (GetValueProc) NumberVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)NumberStrVar_BindObjectValue,
    &g_BooleanType,                     // Python type
    DSQL_C_SLONG,                       // C type
    sizeof(sdint4),                     // element length
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};

//-----------------------------------------------------------------------------
// NumberVar_SetValueFromBoolean()
//   Set the value of the variable from a Python boolean.
//-----------------------------------------------------------------------------
static 
int 
NumberVar_SetValueFromBoolean(
    dm_NumberVar*   var,                    // variable to set value for
    unsigned        pos,                    // array position to set
    PyObject*       value                   // value to set
)                    
{
    char            integerValue;

    integerValue    = (value == Py_True);
    var->data[pos]  = integerValue;

    var->actualLength[pos]  = var->type->size;
    var->indicator[pos]     = var->type->size;

    return 0;
}


#if PY_MAJOR_VERSION < 3
//-----------------------------------------------------------------------------
// NumberVar_SetValueFromInteger()
//   Set the value of the variable from a Python integer.
//-----------------------------------------------------------------------------
static 
int 
NumberVar_SetValueFromInteger(
    dm_NumberVar*   var,                    // variable to set value for
    unsigned        pos,                    // array position to set
    PyObject*       value                   // value to set
)                    
{
    long            integerValue;

    integerValue 	= PyInt_AS_LONG(value);
    var->data[pos] 	= integerValue;

    var->actualLength[pos]  = var->type->size;
    var->indicator[pos]     = var->type->size;

    return 0;
}

#endif

#if PY_MAJOR_VERSION >= 3
//-----------------------------------------------------------------------------
// NumberVar_SetValueFromFloat()
//   Set the value of the variable from a Python Float.
//-----------------------------------------------------------------------------
static
int
NumberVar_SetValueFromFloat(
    dm_NumberVar*  var,                    // variable to set value for
    unsigned       pos,                    // array position to set
    PyObject*      value                   // value to set
)
{
    double            floatValue;

    floatValue = PyFloat_AS_DOUBLE(value);
    var->data[pos] = floatValue;

    var->actualLength[pos] = var->type->size;
    var->indicator[pos] = var->type->size;

    return 0;
}
#endif

//-----------------------------------------------------------------------------
// NumberVar_SetValueFromLong()
//   Set the value of the variable from a Python long.
//-----------------------------------------------------------------------------
static 
int 
NumberVar_SetValueFromLong(
    dm_NumberVar*   var,                // variable to set value for
    unsigned        pos,                // array position to set
    PyObject*       value               // value to set
)                    
{
    long            longValue;

    /* 数据溢出等转换错误 */
    longValue   = PyLong_AsLong(value);
    if (PyErr_Occurred())
    {
        return -1;
    }
    
    var->data[pos]          = longValue;

    var->actualLength[pos]  = var->type->size;
    var->indicator[pos]     = var->type->size;

    return 0;
}


//-----------------------------------------------------------------------------
// NumberVar_GetFormatAndTextFromDecimal()
//   Return the text to use for the Decimal object.
//-----------------------------------------------------------------------------
static 
int 
NumberVar_GetFormatAndTextFromDecimal(
    PyObject*   tupleValue,               // decimal as_tuple() value
    PyObject**  textObj                   // text string for conversion
)
{   
    long        numDigits; 
    long        scale; 
    char        str_scale[256];
    long        sign;
    long        length;
    char*       textPtr;
    char*       textValue;
    PyObject*   digits;
    long        digit;
    int         i;
    
    // acquire basic information from the value tuple
#if PY_MAJOR_VERSION >= 3
    sign = PyLong_AsLong(PyTuple_GET_ITEM(tupleValue, 0));
#else
    sign = PyInt_AsLong(PyTuple_GET_ITEM(tupleValue, 0));
#endif
    
    if (PyErr_Occurred())
        return -1;

    digits = PyTuple_GET_ITEM(tupleValue, 1);

    if (PyErr_Occurred())
        return -1;

#if PY_MAJOR_VERSION >= 3 
    scale = PyLong_AsLong(PyTuple_GET_ITEM(tupleValue, 2));
#else
    scale = PyInt_AsLong(PyTuple_GET_ITEM(tupleValue, 2));
#endif

    if (PyErr_Occurred())
        return -1;

    /* decimal类型指数最大值为128 */
    if (abs(scale) > 128)
    {
        PyErr_SetString(g_ErrorException, "data overflow");
        return -1;
    }

    numDigits   = PyTuple_GET_SIZE(digits);

    // allocate memory for the string and format to use in conversion
    length      = numDigits + abs(scale) + 3;
    textValue   = PyMem_Malloc(length);

    textPtr     = textValue;

    memset(textPtr, 0, length);

    if (!textPtr) 
    {
        PyErr_NoMemory();
        return -1;
    }

    /* 符号位 */
    if (sign)
        *textPtr++ = '-';

    /* digits是tuple结构，需要取出每位数字 */
    for (i = 0; i < numDigits; i++)
    {
#if PY_MAJOR_VERSION >= 3
        digit = PyLong_AsLong(PyTuple_GetItem(digits, i));
#else
        digit = PyInt_AsLong(PyTuple_GetItem(digits, i));
#endif
        if (PyErr_Occurred()) 
        {
            PyMem_Free(textPtr);
            return -1;
        }

        *textPtr++ = '0' + (char)digit;
    }

    /* 指数位 */
    sprintf(str_scale, "%s%ld", "E", scale);
    strcat(textValue, str_scale);
    
    *textObj = dmString_FromAscii(textValue);

    PyMem_Free(textValue);
    
    if (!*textObj) 
    {
        return -1;
    }

    return 0;
}


//-----------------------------------------------------------------------------
// NumberVar_SetValueFromDecimal()
//   Set the value of the variable from a Python decimal.Decimal object.
//-----------------------------------------------------------------------------

static 
int 
NumberVar_SetValueFromDecimal(
    dm_NumberStrVar*    var,                    // variable to set value for
    unsigned            pos,                    // array position to set
    PyObject*           value                   // value to set
)                    
{
    PyObject *textValue, *tupleValue;
    dm_Buffer textBuffer;

    tupleValue = PyObject_CallMethod(value, "as_tuple", NULL);
    if (!tupleValue)
        return -1;

    if (NumberVar_GetFormatAndTextFromDecimal(tupleValue, &textValue) < 0) 
    {
        Py_DECREF(tupleValue);
        return -1;
    }

    Py_DECREF(tupleValue);

    if (dmBuffer_FromObject(&textBuffer, textValue, var->environment->encoding) < 0)
        return -1;

    // ensure that the buffer is large enough
    if (textBuffer.size > (Py_ssize_t)var->bufferSize) 
    {
        if (dmVar_Resize((dm_Var*)var, textBuffer.numCharacters) < 0) 
        {
            dmBuffer_Clear(&textBuffer);
            return -1;
        }
    }

    memcpy(var->data + pos * var->bufferSize, textBuffer.ptr, textBuffer.size);

    var->actualLength[pos]  = textBuffer.size;
    var->indicator[pos]     = textBuffer.size;

    dmBuffer_Clear(&textBuffer);

    Py_DECREF(textValue);
    
    return 0;
}


//-----------------------------------------------------------------------------
// NumberVar_SetValue()
//   Set the value of the variable.
//-----------------------------------------------------------------------------
static 
int 
NumberVar_SetValue(
    dm_NumberVar*   var,            // variable to set value for
    unsigned        pos,            // array position to set
    PyObject*       value           // value to set
)                    
{
    if (PyBool_Check(value))
        return NumberVar_SetValueFromBoolean(var, pos, value);

#if PY_MAJOR_VERSION < 3    
    if (PyInt_Check(value))
        return NumberVar_SetValueFromInteger(var, pos, value);
#endif

#if PY_MAJOR_VERSION >= 3 
    if (PyFloat_Check(value))
        return NumberVar_SetValueFromFloat(var, pos, value);
#endif

    if (PyLong_Check(value))
        return NumberVar_SetValueFromLong(var, pos, value);

    PyErr_SetString(g_ErrorException, "expecting numeric data");
    
    return -1;
}

static 
int 
NumberStrVar_SetValue(
    dm_NumberStrVar*    var,            // variable to set value for
    unsigned            pos,            // array position to set
    PyObject*           value           // value to set
)                    
{   
    if (PyDecimal_Check(value))
    {
        return NumberVar_SetValueFromDecimal(var, pos, value);
    }

    PyErr_SetString(g_ErrorException, "expecting decimal data");
    
    return -1;
}

static 
int 
DoubleVar_SetValue(
    dm_DoubleVar*       var, 
    unsigned            pos, 
    PyObject*           value
)
{
    double doubleValue;

    doubleValue = PyFloat_AS_DOUBLE(value);
    var->data[pos] = doubleValue;

    var->actualLength[pos]  = sizeof(double);
    var->indicator[pos]     = sizeof(double);
    
    return 0;
}

static 
int 
FloatVar_SetValue(
    dm_FloatVar*        var, 
    unsigned            pos, 
    PyObject*           value
)
{
    PyObject*           StrValue;
    dm_Buffer           StrBuffer;

    StrValue = PyObject_Str(value);
    if (StrValue == NULL)
    {
        return -1;
    }

    if (dmBuffer_FromObject(&StrBuffer, StrValue, var->environment->encoding) < 0)
        return -1;

    memcpy(var->data + pos * var->bufferSize, StrBuffer.ptr, StrBuffer.size);

    var->actualLength[pos]  = StrBuffer.size;
    var->indicator[pos]     = StrBuffer.size;

    dmBuffer_Clear(&StrBuffer);
    Py_DECREF(StrValue);

    return 0;
}

//-----------------------------------------------------------------------------
// NumberVar_GetValue()
//   Returns the value stored at the given array position.
//-----------------------------------------------------------------------------
static 
PyObject*
NumberVar_GetValue(
    dm_NumberVar*   var,                // variable to determine value for
    unsigned        pos                 // array position
)                       
{
    if (var->type == &vt_Boolean)
        return PyBool_FromLong(var->data[pos]);

    return PyLong_FromLong(var->data[pos]);
}

static 
int 
NumberVar_BindObjectValue(
    dm_NumberVar*       var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
)
{
    DPIRETURN       rt = DSQL_SUCCESS;

    rt      = dpi_set_obj_val(hobj, val_nth, var->type->cType, (dpointer)&var->data[pos], var->indicator[pos]);
    if (Environment_CheckForError(var->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "vCursor_BindObjectValue():dpi_set_obj_val") < 0)
    {
        return -1;
    }

    return 0;
}

static 
PyObject*
NumberStrVar_GetValue(
    dm_NumberStrVar*    var,                // variable to determine value for
    unsigned            pos                 // array position
)                       
{
    PyObject*           stringObj;
    PyObject*           decObj = NULL;
    char*               data;
    char*               new_data;
    char*               str = NULL;

    data = var->data + pos * var->bufferSize;
    
    if (var->type == &vt_NumberAsString) 
    {
        str = strstr(data, ".");
        if(str == NULL && data != NULL && var->coldesc != NULL && var->coldesc->scale > 0)
        { 
            new_data = PyMem_Malloc(var->actualLength[pos] + 2);
            strcpy(new_data, data);
            strcat(new_data, ".0");
            stringObj = dmString_FromEncodedString(new_data, var->actualLength[pos] + 2, var->environment->encoding);
            PyMem_Free(new_data);
        }
        else
        {
            stringObj = dmString_FromEncodedString(data, var->actualLength[pos], var->environment->encoding);
        }

        if (!stringObj)
            return NULL;

        //decimal值调用python的方法，转换为decimal.Decimal对象
        decObj      = PyObject_CallFunctionObjArgs((PyObject*)g_decimal_type, stringObj, NULL);
        Py_DECREF(stringObj);

        return decObj;
    }

    PyErr_SetString(g_ErrorException, "expecting decimal data");
    return NULL;
}

static 
int 
NumberStrVar_BindObjectValue(
    dm_NumberStrVar*    var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
)
{
    DPIRETURN       rt = DSQL_SUCCESS;

    rt      = dpi_set_obj_val(hobj, val_nth, var->type->cType, (dpointer)((sdbyte*)var->data + var->bufferSize * pos), var->indicator[pos]);
    if (Environment_CheckForError(var->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "vCursor_BindObjectValue():dpi_set_obj_val") < 0)
    {
        return -1;
    }

    return 0;
}

static 
PyObject*
DoubleVar_GetValue(
    dm_DoubleVar*       var, 
    unsigned            pos
)
{
    double              value;

    value = var->data[pos];
    return PyFloat_FromDouble(value);
}

static 
int 
DoubleVar_BindObjectValue(
    dm_DoubleVar*       var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
)
{
    DPIRETURN       rt = DSQL_SUCCESS;

    rt      = dpi_set_obj_val(hobj, val_nth, var->type->cType, (dpointer)&var->data[pos], var->indicator[pos]);
    if (Environment_CheckForError(var->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "vCursor_BindObjectValue():dpi_set_obj_val") < 0)
    {
        return -1;
    }

    return 0;
}

static 
PyObject*
FloatVar_GetValue(
    dm_FloatVar*        var, 
    unsigned            pos
)
{
    PyObject*           stringObj;
    char*               data;

    data = var->data + pos * var->bufferSize;

    if (var->type == &vt_Float) 
    {
        stringObj = dmString_FromEncodedString(data, var->actualLength[pos], var->environment->encoding);

        if (!stringObj)
            return NULL;

#if PY_MAJOR_VERSION < 3
        return PyFloat_FromString(stringObj, NULL);
#else
        return PyFloat_FromString(stringObj);
#endif
    }

    PyErr_SetString(g_ErrorException, "expecting real data");
    return NULL;
}

static 
int 
FloatVar_BindObjectValue(
    dm_FloatVar*        var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
)
{
    DPIRETURN       rt = DSQL_SUCCESS;

    rt      = dpi_set_obj_val(hobj, val_nth, var->type->cType, (dpointer)&var->data[pos], var->indicator[pos]);
    if (Environment_CheckForError(var->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "vCursor_BindObjectValue():dpi_set_obj_val") < 0)
    {
        return -1;
    }

    return 0;
}

static 
int 
BigintVar_SetValue(
    dm_BigintVar*       var,            // variable to set value for
    unsigned            pos,            // array position to set
    PyObject*           value           // value to set
)                    
{   
    PyObject*           StrValue;
    dm_Buffer           StrBuffer;

    StrValue = PyObject_Str(value);
    if (StrValue == NULL)
    {
        return -1;
    }

    if (dmBuffer_FromObject(&StrBuffer, StrValue, var->environment->encoding) < 0)
        return -1;

    memset(var->data + pos * var->bufferSize, 0, var->bufferSize);
    memcpy(var->data + pos * var->bufferSize, StrBuffer.ptr, StrBuffer.size);

    var->actualLength[pos]  = StrBuffer.size;
    var->indicator[pos]     = StrBuffer.size;

    dmBuffer_Clear(&StrBuffer);
    Py_DECREF(StrValue);

    return 0;
}

static 
PyObject*
BigintVar_GetValue(
    dm_BigintVar*       var,                // variable to determine value for
    unsigned            pos                 // array position
)
{
    PyObject*           stringObj;
    char*               data;
    char*               end;

    data = var->data + pos * var->bufferSize;

    if (var->type == &vt_Bigint) 
    {
        /* int最大值2147483647 */
        /*if (var->actualLength[pos] >= 10)
        {
            stringObj = dmString_FromEncodedString(data, var->actualLength[pos], var->environment->encoding);

            if (!stringObj)
                return NULL;

            return stringObj;
        }*/

        //10进制方式转换
        stringObj = PyLong_FromString(data, &end, 10);

        if (!stringObj)
            return NULL;
        
        return stringObj;
    }

    PyErr_SetString(g_ErrorException, "expecting bigint data");
    return NULL;
}

static 
int 
BigintVar_BindObjectValue(
    dm_BigintVar*       var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
)
{
    DPIRETURN       rt = DSQL_SUCCESS;

    rt      = dpi_set_obj_val(hobj, val_nth, var->type->cType, (dpointer)((sdbyte*)var->data + var->bufferSize * pos), var->indicator[pos]);
    if (Environment_CheckForError(var->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "vCursor_BindObjectValue():dpi_set_obj_val") < 0)
    {
        return -1;
    }

    return 0;
}

static 
int 
Base64Var_SetValue(
    dm_Base64Var*       var,            // variable to set value for
    unsigned            pos,            // array position to set
    PyObject*           value           // value to set
)                    
{   
    PyObject*           StrValue;
    dm_Buffer           StrBuffer;

    StrValue = PyObject_Str(value);
    if (StrValue == NULL)
    {
        return -1;
    }

    if (dmBuffer_FromObject(&StrBuffer, StrValue, var->environment->encoding) < 0)
        return -1;

    memset(var->data + pos * var->bufferSize, 0, var->bufferSize);
    memcpy(var->data + pos * var->bufferSize, StrBuffer.ptr, StrBuffer.size);
	
    var->actualLength[pos]  = StrBuffer.size;
    var->indicator[pos]     = StrBuffer.size;

    dmBuffer_Clear(&StrBuffer);
    Py_DECREF(StrValue);

    return 0;
}

static 
PyObject*
Base64Var_GetValue(
    dm_Base64Var*       var,                // variable to determine value for
    unsigned            pos                 // array position
)
{
    PyObject*           stringObj;
    char*               data;

    data = var->data + pos * var->bufferSize;
	
    if (var->type == &vt_RowId) 
    {

		stringObj = Py_BuildValue("s#", data, 18);

        if (!stringObj)
            return NULL;
        return stringObj;
    }

    PyErr_SetString(g_ErrorException, "expecting base64 data");
    return NULL;
}

static 
int 
Base64Var_BindObjectValue(
    dm_Base64Var*       var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
)
{
    DPIRETURN       rt = DSQL_SUCCESS;

    rt      = dpi_set_obj_val(hobj, val_nth, var->type->cType, (dpointer)((sdbyte*)var->data + var->bufferSize * pos), var->indicator[pos]);
    if (Environment_CheckForError(var->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "vCursor_BindObjectValue():dpi_set_obj_val") < 0)
    {
        return -1;
    }

    return 0;
}
