/******************************************************
file:
    vlong.h
purpose:
    python type define for DM Long variables in dmPython,used to transfor data.
interface:
    {}
history:
    Date        Who         RefDoc      Memo
    2015-6-10    shenning                Created
*******************************************************/

#include "var_pub.h"
#include "Buffer.h"
#include "py_Dameng.h"
#include "Error.h"

//-----------------------------------------------------------------------------
// declaration of long variable functions.
//-----------------------------------------------------------------------------
static int vLong_SetValue(dm_LongVar*, unsigned, PyObject*);
static PyObject *vLong_GetValue(dm_LongVar*, unsigned);
static int vLong_BindObjectValue(dm_LongVar*, unsigned, dhobj, udint4);
static int vLong_Initialize(dm_LongVar* var,dm_Cursor* cursor);  
static void vLong_Finalize(dm_LongVar* var);


//-----------------------------------------------------------------------------
// Python type declarations
//-----------------------------------------------------------------------------
PyTypeObject g_LongStringVarType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.LONG_STRING",             // tp_name
    sizeof(dm_LongVar),                 // tp_basicsize
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


PyTypeObject g_LongBinaryVarType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.LONG_BINARY",             // tp_name
    sizeof(dm_LongVar),                 // tp_basicsize
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
dm_VarType vt_LongString = {
    (InitializeProc) vLong_Initialize,
    (FinalizeProc) vLong_Finalize,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) vLong_SetValue,
    (GetValueProc) vLong_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)vLong_BindObjectValue,
    &g_LongStringVarType,               // Python type
    DSQL_C_NCHAR,                       // cType    
    sizeof(sdint8),                     // element length (default,记录地址)
    1,                                  // is character data
    1,                                  // is variable length
    1,                                  // can be copied
    0                                   // can be in array
};


dm_VarType vt_LongBinary = {
    (InitializeProc) vLong_Initialize,
    (FinalizeProc) vLong_Finalize,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) vLong_SetValue,
    (GetValueProc) vLong_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)vLong_BindObjectValue,
    &g_LongBinaryVarType,               // Python type
    DSQL_C_BINARY,                      // cType    
    sizeof(sdint8),                     // element length (default，记录地址)
    0,                                  // is character data
    1,                                  // is variable length
    1,                                  // can be copied
    0                                   // can be in array
};


//-----------------------------------------------------------------------------
// LongVar_SetValue()
//   Set the value of the variable.
//-----------------------------------------------------------------------------
static 
int 
vLong_SetValue(
    dm_LongVar*     var,    // variable to set value for
    unsigned        pos,    // array position to set
    PyObject*       value   // value to set
)
{
    dm_Buffer       buffer;
    char*           data_ptr;

    // get the buffer data and size for binding
    if (dmBuffer_FromObject(&buffer, value, var->environment->encoding) < 0)
        return -1;

    /* 若内容为0，则不进行拷贝，直接返回 */
    if (buffer.size <= 0)
    {
        dmBuffer_Clear(&buffer);

        var->indicator[pos]     = DSQL_DATA_AT_EXEC;
        var->actualLength[pos]  = 0;

        return 0;
    }

    /* 申请内存空间，用于存在buffer中转换的值 */
    data_ptr        = PyMem_Malloc(buffer.size);
    if (data_ptr == NULL)
    {
        dmBuffer_Clear(&buffer);

        return -1;
    }

    /* copy变量内存，并记录指针 */
    memcpy(data_ptr, buffer.ptr, buffer.size);
    ((sdint8*)var->data)[pos]    = (sdint8)(int3264)data_ptr;

    dmBuffer_Clear(&buffer);

    // set indicator DSQL_DATA_AT_EXEC
    var->indicator[pos]     = DSQL_DATA_AT_EXEC;
    var->actualLength[pos]  = buffer.size;

    return 0;
}

static 
int 
vLong_BindObjectValue(
    dm_LongVar*         var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
)
{
    DPIRETURN       rt = DSQL_SUCCESS;
    sdbyte*         ptr;
    slength         data_len;


    // copy the string to the buffer
    ptr                 = (sdbyte*)(int3264)(((sdint8*)var->data)[pos]);
    data_len            = var->actualLength[pos];    

    rt      = dpi_set_obj_val(hobj, val_nth, var->type->cType, (dpointer)ptr, data_len);
    if (Environment_CheckForError(var->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "vLong_BindObjectValue():dpi_set_obj_val") < 0)
    {
        return -1;
    }

    return 0;
}


//-----------------------------------------------------------------------------
// LongVar_GetValue()
//   Returns the value stored at the given array position.
//-----------------------------------------------------------------------------
static 
PyObject*
vLong_GetValue(
    dm_LongVar*     var,    // variable to determine value for
    unsigned        pos     // array position
)                       
{
    char*       ptr;
    slength     size;

    ptr     = (char*)(int3264)(((sdint8*)var->data)[pos]);
    size    = var->actualLength[pos];    

    if (var->type == &vt_LongBinary)
        return PyBytes_FromStringAndSize(ptr, size);

    return dmString_FromEncodedString(ptr, size, var->environment->encoding);
}
int
vLong_PutData(
    dm_LongVar*     self,    // variable to get buffer size
    udint4          arrayPos    // array position
)
{
    DPIRETURN       rt = DSQL_SUCCESS;    
    udint4          data_len;
    slength         put_len;
    char*           ptr;

    Py_BEGIN_ALLOW_THREADS
        rt = dpi_param_data(self->boundCursorHandle, NULL);
    Py_END_ALLOW_THREADS
    /* 若为0，则直接返回，说明不需要绑定值 */
    if (rt == DSQL_SUCCESS)
        return 0;

    /* 返回失败，但不是DSQL_NEED_DATA，则报错 */
    if (rt != DSQL_NEED_DATA && 
        Environment_CheckForError(self->environment, self->boundCursorHandle, DSQL_HANDLE_STMT, rt, 
        "vLong_PutData():dpi_param_data") < 0)
    {
        fprintf(stdout, "vLong_PutData 1: after dpi_param_data, arrayPos is %d", arrayPos);
        return -1;
    }

    /* 取待设置参数值地址 */
    ptr         = (char*)(int3264)((sdint8*)self->data)[arrayPos];
    data_len    = (udint4)self->actualLength[arrayPos];

    /* 空串时，数据长度为0，也是需要put data */
    while (data_len >= 0)
    {
//         if (data_len > MAX_BINARY_BYTES)
//             put_len = MAX_BINARY_BYTES;
//         else
        put_len = data_len;

        //fprintf(stdout, "vLong_PutData: before dpi_put_data, arrayPos is %d, rt is %d, data_len %d, put_len %d\n", arrayPos, rt, data_len, put_len);
        Py_BEGIN_ALLOW_THREADS
            rt = dpi_put_data(self->boundCursorHandle, (dpointer)ptr, put_len);
        Py_END_ALLOW_THREADS
        if (rt != DSQL_SUCCESS && Environment_CheckForError(self->environment, self->boundCursorHandle, DSQL_HANDLE_STMT, rt, 
            "vLong_PutBinaryData():dpi_put_data") < 0)
        {
            return -1;
        }

        ptr         += put_len;
        data_len    -= put_len;

        /* 提前判断剩余长度为0则跳出循环，防止空串长度为0，进来时导致死循环 */
        if (data_len == 0)
        {
            break;
        }
    }       

    return 0;
}


static
int
vLong_Initialize(
    dm_LongVar*     var,
    dm_Cursor*      cursor
)
{
    udint4          i;    

    // initialize the data address
    for (i = 0; i < var->allocatedElements; i++) 
    {
        ((sdint8*)var->data)[i]    = 0;
    }

    return 0;
}

static
void
vLong_Finalize(
    dm_LongVar*    var
)
{
    udint4                  i;

    for (i = 0; i < var->allocatedElements; i++) 
    {
        /** 释放申请的缓存地址 **/
        if (((sdint8*)var->data)[i] != 0)
        {            
            PyMem_FREE((char*)(int3264)((sdint8*)var->data)[i]);
        }

        ((sdint8*)var->data)[i]     = 0;
    }    
}


