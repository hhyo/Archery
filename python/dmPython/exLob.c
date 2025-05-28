/******************************************************
file:
    exLob.c
purpose:
    defines for DM LOB variables handing external to dmPython
interface:
    {}
history:
    Date        Who         RefDoc      Memo
    2015-6-9    shenning                Created
*******************************************************/

#include "var_pub.h"
#include "py_Dameng.h"
#include "Error.h"

//-----------------------------------------------------------------------------
// Declaration of external LOB variable functions.
//-----------------------------------------------------------------------------
static void exLobVar_Free(dm_ExternalLobVar*);
static PyObject *exLobVar_Size(dm_ExternalLobVar*);
static PyObject *exLobVar_Read(dm_ExternalLobVar*, PyObject*,
    PyObject*);
static PyObject *exLobVar_Write(dm_ExternalLobVar*, PyObject*,
    PyObject*);
static PyObject *exLobVar_Truncate(dm_ExternalLobVar*, PyObject*,
    PyObject*);
static PyObject *exLobVar_Reduce(dm_ExternalLobVar*);


//-----------------------------------------------------------------------------
// declaration of methods for Python type "ExternalLOBVar"
//-----------------------------------------------------------------------------
static PyMethodDef g_ExternalLobVarMethods[] = {
    { "size", (PyCFunction) exLobVar_Size, METH_NOARGS },        
    { "read", (PyCFunction) exLobVar_Read,  METH_VARARGS  | METH_KEYWORDS },
    { "write", (PyCFunction) exLobVar_Write, METH_VARARGS  | METH_KEYWORDS },
    { "truncate", (PyCFunction) exLobVar_Truncate, METH_VARARGS  | METH_KEYWORDS },        
    { "__reduce__", (PyCFunction) exLobVar_Reduce, METH_NOARGS },
    { NULL, NULL }
};


//-----------------------------------------------------------------------------
// Python type declaration
//-----------------------------------------------------------------------------
PyTypeObject g_exLobVarType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.LOB",                     // tp_name
    sizeof(dm_ExternalLobVar),          // tp_basicsize
    0,                                  // tp_itemsize
    (destructor) exLobVar_Free,         // tp_dealloc
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
    (reprfunc) exLobVar_Str,            // tp_str
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
    g_ExternalLobVarMethods,            // tp_methods
    0,                                  // tp_members
    0,                                  // tp_getset
    0,                                  // tp_base
    0,                                  // tp_dict
    0,                                  // tp_descr_get
    0,                                  // tp_descr_set
    0,                                  // tp_dictoffset
    0,                                  // tp_init
    0,                                  // tp_alloc
    0,                                  // tp_new
    0,                                  // tp_free
    0,                                  // tp_is_gc
    0                                   // tp_bases
};


//-----------------------------------------------------------------------------
// ExternalLobVar_New()
//   Create a new external LOB variable.
//-----------------------------------------------------------------------------
PyObject*
ExternalLobVar_New(
    dm_LobVar*      var,    // variable to encapsulate
    unsigned        pos     // position in array to encapsulate
)                       
{
    dm_ExternalLobVar *self;

    self = (dm_ExternalLobVar*)g_exLobVarType.tp_alloc(&g_exLobVarType, 0);
    if (!self)
        return NULL;

    self->pos = pos;
    self->internalFetchNum = var->internalFetchNum;

    Py_INCREF(var);
    self->lobVar = var;

    return (PyObject*) self;
}


//-----------------------------------------------------------------------------
// ExternalLobVar_Free()
//   Free an external LOB variable.
//-----------------------------------------------------------------------------
static
void 
exLobVar_Free(
    dm_ExternalLobVar*     self    // variable to free
)           
{
    Py_CLEAR(self->lobVar);
    Py_TYPE(self)->tp_free((PyObject*) self);
}


//-----------------------------------------------------------------------------
// exLobVar_Verify()
//   Verify that the external LOB var is still valid.
//-----------------------------------------------------------------------------
static
int 
exLobVar_Verify(
    dm_ExternalLobVar*     var  // variable to verify
)
{
    dm_LobVar*         lobVar = var->lobVar;
    /** 连接断开，lob句柄无效；cursor关闭，lob句柄操作可能会报错，此处增加校验 **/
    if (lobVar != NULL && lobVar->connection->isConnected <= 0)
    {
        PyErr_SetString(PyExc_ValueError, 
            "The related cursor or connection is closed");
        return -1;
    }

    if (var->internalFetchNum != lobVar->internalFetchNum) {
        PyErr_SetString(g_ProgrammingErrorException,
            "LOB variable no longer valid after subsequent fetch");
        return -1;
    }

    return 0;
}


//-----------------------------------------------------------------------------
// exLobVar_InternalRead()
//   Return the size of the LOB variable for internal comsumption.
//-----------------------------------------------------------------------------
static 
int 
exLobVar_InternalRead(
    dm_ExternalLobVar*  var,        // variable to return the size of
    char*               buffer,     // buffer in which to put data
    slength             bufferSize, // size of buffer
    slength*            length,     // length of data (IN/OUT)
    ulength             offset      // offset
)
{
    DPIRETURN       rt = DSQL_SUCCESS;
    slength         data_to_read;
    slength         data_get = 0;
    sdint2          cType;

    data_to_read    = *length;    

    if (var->lobVar->type == &vt_BLOB)
        cType       = DSQL_C_BINARY;
    else
        cType       = DSQL_C_NCHAR;

    Py_BEGIN_ALLOW_THREADS        
        rt  = dpi_lob_read(var->lobVar->data[var->pos], offset, cType, data_to_read, (dpointer)buffer, bufferSize, &data_get);
    Py_END_ALLOW_THREADS
        if (Environment_CheckForError(var->lobVar->environment, var->lobVar->data[var->pos], DSQL_HANDLE_LOB_LOCATOR, rt, 
            "exLobVar_InternalRead():dpi_lob_read") < 0)
        {
            return -1;
        }            

    *length     = data_get;

    return 0;
}


//-----------------------------------------------------------------------------
// exLobVar_InternalSize()
//   Return the size of the LOB variable for internal comsumption.
//-----------------------------------------------------------------------------
static 
int 
exLobVar_InternalSize(
    dm_ExternalLobVar*     var // variable to return the size of
)
{
    DPIRETURN   rt = DSQL_SUCCESS;
    slength     length;

    Py_BEGIN_ALLOW_THREADS
        rt  = dpi_lob_get_length(var->lobVar->data[var->pos], &length);
    Py_END_ALLOW_THREADS
        if (Environment_CheckForError(var->lobVar->environment, var->lobVar->data[var->pos], DSQL_HANDLE_LOB_LOCATOR, rt, 
            "exLobVar_InternalSize():dpi_lob_get_length") < 0)
        {
            return -1;
        }        

    return length;
}

/************************************************************************
purpose:
    exLobVar_Value()
    Return a portion (or all) of the data in the external LOB variable.
************************************************************************/
static 
PyObject*
exLobVar_Value(
    dm_ExternalLobVar*  var,            /*IN:variable to return the size of*/
    int                 offset,         /*IN:offset into LOB*/
    slength*            amount          /*IN/OUT:amount to read from LOB(IN/OUT)*/
)
{
    slength         length;
    slength         bufferSize;
    PyObject*       result;
    char*           buffer;

    // modify the arguments
    if (offset <= 0)
        offset  = 1;

    if ((*amount) < 0) 
    {
        (*amount)   = exLobVar_InternalSize(var);
        if (*amount < 0)
            return NULL;

        (*amount)  = (*amount) - offset + 1;
        if ((*amount) <= 0)
            (*amount)   = 1;
    }
    length          = (*amount);
    if (var->lobVar->type == &vt_CLOB)
        bufferSize  = ((*amount) * var->lobVar->environment->maxBytesPerCharacter + 1); /** 预留字符串结尾符位置 **/
    else
        bufferSize  = (*amount);

    // create a string for retrieving the value
    buffer = (char*) PyMem_Malloc(bufferSize);
    if (!buffer)
        return PyErr_NoMemory();

    memset(buffer, 0, bufferSize);
    if (exLobVar_InternalRead(var, buffer, bufferSize, &length, offset) < 0) 
    {
            PyMem_Free(buffer);
            return NULL;
    }

    // return the result
    if (var->lobVar->type == &vt_CLOB) 
    {        
        //result = dmString_FromEncodedString(buffer, strlen(buffer), var->lobVar->environment->encoding);
        //Create a Unicode object by decoding size bytes of the encoded string s.
        result = PyUnicode_Decode(buffer, strlen(buffer), var->lobVar->environment->encoding, NULL);
    }
    else 
    {
        result = PyBytes_FromStringAndSize(buffer, length);
    }
    PyMem_Free(buffer);

    *amount     = length;

    return result;
}


//-----------------------------------------------------------------------------
// exLobVar_Size()
//   Return the size of the data in the LOB variable.
//-----------------------------------------------------------------------------
static
PyObject*
exLobVar_Size(
    dm_ExternalLobVar* var            // variable to return the size of    
)
{
    int length;

    if (exLobVar_Verify(var) < 0)
        return NULL;

    length = exLobVar_InternalSize(var);
    if (length < 0)
        return NULL;

#if PY_MAJOR_VERSION < 3
    return PyInt_FromLong(length);
#else
    return PyLong_FromLong(length);
#endif
}

//-----------------------------------------------------------------------------
// exLobVar_Read()
//   Return a portion (or all) of the data in the external LOB variable.
//-----------------------------------------------------------------------------
static
PyObject*
exLobVar_Read(
    dm_ExternalLobVar*  var,        // variable to return the size of
    PyObject*           args,       // arguments
    PyObject*           keywordArgs // keyword arguments
)              
{
    static char *keywordList[] = { "offset", "amount", NULL };
    int offset;
    slength amount;

    // offset and amount are expected, both optional
    offset = -1;
    amount = -1;
    if (!PyArg_ParseTupleAndKeywords(args, keywordArgs, "|ii", keywordList,
        &offset, &amount))
        return NULL;

    if (exLobVar_Verify(var) < 0)
        return NULL;

    return exLobVar_Value(var, offset, &amount);
}


//-----------------------------------------------------------------------------
// exLobVar_Str()
//   Return all of the data in the external LOB variable.
//-----------------------------------------------------------------------------
void 
exLobVar_binary_2_char(
    sdbyte      data,
    sdbyte*     chr
)
{
    udbyte  us;
    udbyte  us1;
    udbyte  us2;

    memcpy(&us,&data,sizeof(sdbyte));
    us1 = us/16;
    us2 = us%16;

    if (us1<=9)
        chr[0] = '0' + us1;
    if (us1>=10 && us1<=15)
        chr[0] = 'A' + us1 -10;

    if (us2<=9)
        chr[1] = '0' + us2;
    if (us2>=10 && us2<=15)
        chr[1] = 'A' + us2 -10;
}

PyObject*
exLobVar_BytesToString(
    PyObject*       bsObject,
    slength         len
)
{    
    sdbyte*         dst_buf = NULL;
    sdbyte*         src_buf = NULL;
    sdint4	        i, j;
    sdbyte	        chr[3];
    PyObject*       result;
        
    src_buf     = PyBytes_AS_STRING(bsObject);
    if (src_buf == NULL)
    {
        return NULL;
    }

    dst_buf     = (sdbyte*)PyMem_Malloc(len * 2 + 24);
    if (dst_buf == NULL)
    {
        PyErr_NoMemory();
        return NULL;
    }    

    strcpy(dst_buf, "0x");

    for (i = 0, j = 2; i < len; i++)
    {
        exLobVar_binary_2_char(src_buf[i], chr);

        dst_buf[j++] = chr[0];
        dst_buf[j++] = chr[1];
    }

    dst_buf[j]  = '\0';

    result      = dmString_FromAscii(dst_buf);
    PyMem_Free(dst_buf);

    return result;
}

PyObject*
exLobVar_Str(
    dm_ExternalLobVar* var  // variable to return the string for
)
{
    PyObject*   result;
    slength     amount = -1;

    if (exLobVar_Verify(var) < 0)
        return NULL;

    result  = exLobVar_Value(var, 1, &amount);
    if (result == NULL)
        return NULL;

    /** 不是Bytes类型，直接返回 **/
    if (!PyBytes_Check(result))
        return result;

    /** Bytes类型，转换为字符串后返回 **/
    return exLobVar_BytesToString(result, amount);
}

PyObject*
exLobVar_Bytes(
    dm_ExternalLobVar* var  // variable to return the string for
)
{
    PyObject*   result;
    slength     amount = -1;

    if (exLobVar_Verify(var) < 0)
        return NULL;

    result  = exLobVar_Value(var, 1, &amount);
    if (result == NULL)
        return NULL;

    return result;
}


//-----------------------------------------------------------------------------
// exLobVar_Write()
//   Write a value to the LOB variable; return the number of bytes written.
//-----------------------------------------------------------------------------
static 
PyObject*
exLobVar_Write(
    dm_ExternalLobVar*  var,            // variable to perform write against
    PyObject*           args,           // arguments
    PyObject*           keywordArgs     // keyword arguments
)
{
    static char*    keywordList[] = { "data", "offset", NULL };
    PyObject*       dataObj;
    udint4          amount;
    int             offset;

    // buffer and offset are expected, offset is optional
    offset = -1;
    if (!PyArg_ParseTupleAndKeywords(args, keywordArgs, "O|i", keywordList,
        &dataObj, &offset))
        return NULL;
    if (offset < 0)
        offset = 1;

    // perform the write, if possible
    if (exLobVar_Verify(var) < 0)
        return NULL;

    if (vLobVar_Write(var->lobVar, var->pos, dataObj, offset, &amount) < 0)
        return NULL;

    // return the result
#if PY_MAJOR_VERSION < 3
    return PyInt_FromLong(amount);
#else
    return PyLong_FromLong(amount);
#endif
}


//-----------------------------------------------------------------------------
// exLobVar_Trim()
//   Trim the LOB variable to the specified length.Return the real length after truncate
//-----------------------------------------------------------------------------
static 
PyObject*
exLobVar_Truncate(
    dm_ExternalLobVar*  var,          // variable to perform write against
    PyObject*           args,         // arguments
    PyObject*           keywordArgs   // keyword arguments
)
{
    static char*    keywordList[] = { "newSize", NULL };
    DPIRETURN       rt = DSQL_SUCCESS;
    Py_ssize_t      newSize;
    ulength         date_len;

    // buffer and offset are expected, offset is optional
    newSize = 0;
    if (!PyArg_ParseTupleAndKeywords(args, keywordArgs, "|i", keywordList,
        &newSize))
        return NULL;    

    /** 若newsize < 0，则报错 **/
    if (newSize < 0)
    {
        PyErr_SetString(g_ProgrammingErrorException, 
            "expect zero or a positive integer value.");
        return NULL;
    }

    // create a string for retrieving the value
    if (exLobVar_Verify(var) < 0)
        return NULL;
    
    Py_BEGIN_ALLOW_THREADS
        rt  = dpi_lob_truncate(var->lobVar->data[var->pos], (ulength)newSize, &date_len);
    Py_END_ALLOW_THREADS
        if (Environment_CheckForError(var->lobVar->environment, var->lobVar->data[var->pos], DSQL_HANDLE_LOB_LOCATOR, rt, 
            "exLobVar_Truncate():dpi_lob_truncate") < 0)
        {
            return NULL;
        }

    // return the result
#if PY_MAJOR_VERSION < 3
        return PyInt_FromLong(date_len);
#else
        return PyLong_FromLong(date_len);
#endif
}


//-----------------------------------------------------------------------------
// exLobVar_Reduce()
//   Method provided for pickling/unpickling of LOB variables.
//-----------------------------------------------------------------------------
static 
PyObject*
exLobVar_Reduce(
    dm_ExternalLobVar*     self     // variable to dump
)
{
    PyObject*       result;
    PyObject*       value;

    value = exLobVar_Str(self);
    if (!value)
        return NULL;

    result = Py_BuildValue("(O(O))", Py_TYPE(value), value);
    Py_DECREF(value);
    return result;
}



