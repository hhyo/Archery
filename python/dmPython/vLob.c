/******************************************************
file:
    vLob.c
purpose:
    python type define for DM LOB variables in dmPython.just be used to col description
interface:
    {}
history:
    Date        Who         RefDoc      Memo
    2015-6-9    shenning                Created
*******************************************************/

#include "Buffer.h"
#include "Error.h"
#include "var_pub.h"

//-----------------------------------------------------------------------------
// Declaration of LOB variable functions.
//-----------------------------------------------------------------------------
static int vLob_Initialize(dm_LobVar*, dm_Cursor*);
static void vLob_Finalize(dm_LobVar*);
static int vLob_SetValue(dm_LobVar*, unsigned, PyObject*);
static PyObject *vLob_GetValue(dm_LobVar*, unsigned);
static int vLob_BindObjectValue(dm_LobVar*, unsigned, dhobj, udint4);
static int vLob_PreDefine(dm_LobVar*, dhdesc, sdint2);

//-----------------------------------------------------------------------------
// Python type for CLOB declarations
//-----------------------------------------------------------------------------
PyTypeObject g_CLobVarType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.CLOB",                    // tp_name
    sizeof(dm_LobVar),                  // tp_basicsize
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
// Python type for BLOB declarations
//-----------------------------------------------------------------------------
PyTypeObject g_BLobVarType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.BLOB",                    // tp_name
    sizeof(dm_LobVar),                  // tp_basicsize
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
dm_VarType vt_CLOB = {
    (InitializeProc) vLob_Initialize,
    (FinalizeProc) vLob_Finalize,
    (PreDefineProc) vLob_PreDefine,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) vLob_SetValue,
    (GetValueProc) vLob_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)vLob_BindObjectValue,
    &g_CLobVarType,                     // Python type
    DSQL_C_LOB_HANDLE,                  // cType    
    sizeof(dhloblctr),                  // element length
    1,                                  // is character data
    0,                                  // is variable length
    0,                                  // can be copied
    0                                   // can be in array
};


dm_VarType vt_BLOB = {
    (InitializeProc) vLob_Initialize,
    (FinalizeProc) vLob_Finalize,
    (PreDefineProc) vLob_PreDefine,
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) vLob_SetValue,
    (GetValueProc) vLob_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)vLob_BindObjectValue,
    &g_BLobVarType,                     // Python type
    DSQL_C_LOB_HANDLE,                  // cType    
    sizeof(dhloblctr),                  // element length
    0,                                  // is character data
    0,                                  // is variable length
    0,                                  // can be copied
    0                                   // can be in array
};


//-----------------------------------------------------------------------------
// LobVar_Initialize()
//   Initialize the variable.
//-----------------------------------------------------------------------------
static 
int 
vLob_Initialize(
    dm_LobVar*      var,        // variable to initialize
    dm_Cursor*      cursor      // cursor created by
)                 
{
    udint4          i;

    // initialize members
    Py_INCREF(cursor->connection);
    var->connection = cursor->connection;    

    var->exLobs     = PyList_New(var->allocatedElements);
    if (!var->exLobs)
        return -1;

    // initialize the LOB locators
    for (i = 0; i < var->allocatedElements; i++) 
    {
        var->data[i]    = NULL;
    }

    return 0;
}

//-----------------------------------------------------------------------------
// LobVar_Finalize()
//   Prepare for variable destruction.
//-----------------------------------------------------------------------------
static 
void 
vLob_Finalize(
    dm_LobVar*     var // variable to free
)
{
    udint4                  i;
    dm_ExternalLobVar*     exLob;

    for (i = 0; i < var->allocatedElements; i++) 
    {
        if (var->exLobs != NULL)
            exLob   = (dm_ExternalLobVar*)PyList_GET_ITEM(var->exLobs, i);
        else
            exLob   = NULL;

        /** 通过exLob赋值的LOB句柄不预释放 **/
        if (var->data[i] != NULL && exLob == NULL && var->connection->hcon != NULL)
        {            
            dpi_free_lob_locator(var->data[i]);
        }
        var->data[i]    = NULL;
    }
    
    Py_CLEAR(var->exLobs);
    Py_CLEAR(var->connection);
}

//-----------------------------------------------------------------------------
// vLob_PreDefine()
//   Performs additional steps required for defining objects.
//-----------------------------------------------------------------------------
static int vLob_PreDefine(
    dm_LobVar*      var,            // variable to set up    
    dhdesc          hdesc_col,
    sdint2          pos              // position in define list，1-based
)
{
    DPIRETURN       rt;
    udint4          i;

    // initialize the LOB locators
    for (i = 0; i < var->allocatedElements; i++) 
    {
        rt      = dpi_alloc_lob_locator2(var->connection->hcon, (dhloblctr*)&var->data[i]);
        if (Environment_CheckForError(var->environment, var->connection->hcon, DSQL_HANDLE_LOB_LOCATOR, rt,
            "vLob_PreDefine():dpi_alloc_lob_locator2") < 0)
        {
            return -1;
        }
    }

    return 0;
}

//-----------------------------------------------------------------------------
// LobVar_Write()
//   Write data to the LOB variable.
//-----------------------------------------------------------------------------
int 
vLobVar_Write(
    dm_LobVar*      var,        // variable to perform write against
    unsigned        position,   // position to perform write against
    PyObject*       dataObj,    // data object to write into LOB
    udint4          start_pos,  // offset into variable
    udint4*         amount      // amount to write
)
{
    dm_Buffer       buffer;
    DPIRETURN       rt = DSQL_SUCCESS;
    sdint2          ctype;

    // verify the data type
    if (dmBuffer_FromObject(&buffer, dataObj, var->environment->encoding) < 0)
        return -1;
    *amount     = (udint4)buffer.size;       

    // nothing to do if no data to write
    if (*amount == 0) 
    {
        dmBuffer_Clear(&buffer);
        return 0;
    }  

    if (Py_TYPE(var) == &g_BLobVarType)
        ctype   = DSQL_C_BINARY;
    else
        ctype   = DSQL_C_NCHAR;

    Py_BEGIN_ALLOW_THREADS
        rt  = dpi_lob_write(var->data[position], start_pos, ctype, (dpointer)(char*)buffer.ptr, *amount, amount);
    Py_END_ALLOW_THREADS
        dmBuffer_Clear(&buffer);
    if (Environment_CheckForError(var->environment, var->data[position], DSQL_HANDLE_LOB_LOCATOR, rt, 
        "vLobVar_Write():dpi_lob_write") < 0)
    {
        return -1;
    }
    
    return 0;
}

//-----------------------------------------------------------------------------
// vLob_SetValue()
//   Set the value of the variable.
//-----------------------------------------------------------------------------
static 
int 
vLob_SetValue(
    dm_LobVar*          var,    // variable to set value for
    unsigned            pos,    // array position to set
    PyObject*           value   // value to set
)                    
{
    dm_ExternalLobVar* exlob;

    if (!PyObject_IsInstance(value, (PyObject*) &g_exLobVarType)) 
    {
        PyErr_SetString(PyExc_TypeError, "expecting a Lob Object");
        return -1;
    }   

    exlob       = (dm_ExternalLobVar*)value;

    Py_XDECREF(PyList_GET_ITEM(var->exLobs, pos));
    
    Py_INCREF(value);
    PyList_SET_ITEM(var->exLobs, pos, value);    

    var->data[pos]          = exlob->lobVar->data[exlob->pos];
    var->indicator[pos]     = sizeof(dhloblctr);
    var->actualLength[pos]  = sizeof(dhloblctr);

    return 0;
}

//-----------------------------------------------------------------------------
// LobVar_GetValue()
//   Returns the value stored at the given array position.
//-----------------------------------------------------------------------------
static 
PyObject*
vLob_GetValue(
    dm_LobVar*  var,        // variable to determine value for
    unsigned    pos         // array position
)                  
{

    dm_ExternalLobVar* lob_val;
    PyObject*           ret;

    lob_val             = ExternalLobVar_New(var, pos);

    if (lob_val->lobVar->type == &vt_CLOB)
    {
        ret             = exLobVar_Str(lob_val);
    }
    else
    {
        ret             = exLobVar_Bytes(lob_val);
    }
    
    

    Py_DECREF(var);
    //Py_DECREF(lob_val);

    return ret;
}

static 
int 
vLob_BindObjectValue(
    dm_LobVar*          var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
)
{
    DPIRETURN       rt;

    rt      = dpi_set_obj_val(hobj, val_nth, var->type->cType, (dpointer)&var->data[pos], var->indicator[pos]);
    if (Environment_CheckForError(var->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "vCursor_BindObjectValue():dpi_set_obj_val") < 0)
    {
        return -1;
    }

    return 0;
}

