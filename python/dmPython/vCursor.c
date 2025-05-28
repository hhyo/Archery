/******************************************************
file:
    vCursor.c
purpose:
    python type define for DM Cursor variables in dmPython.
interface:
    {}
history:
    Date        Who         RefDoc      Memo
    2015-6-11   shenning                Created
*******************************************************/

#include "var_pub.h"
#include "py_Dameng.h"
#include "Error.h"

//-----------------------------------------------------------------------------
// Declaration of cursor variable functions.
//-----------------------------------------------------------------------------
static int vCursor_Initialize(dm_CursorVar*, dm_Cursor*);
static void vCursor_Finalize(dm_CursorVar*);
static int vCursor_SetValue(dm_CursorVar*, unsigned, PyObject*);
static PyObject *vCursor_GetValue(dm_CursorVar*, unsigned);
static int vCursor_BindObjectValue(dm_CursorVar*, unsigned, dhobj, udint4);
static PyObject* CursorVar_GetValues(dm_CursorVar*);


static PyMethodDef g_CursorVarMethods[] = {
    { "getvalue",       (PyCFunction)CursorVar_GetValues,     METH_NOARGS},
    {NULL }
};

//-----------------------------------------------------------------------------
// Python type declarations
//-----------------------------------------------------------------------------
PyTypeObject g_CursorVarType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.CURSOR",                  // tp_name
    sizeof(dm_CursorVar),               // tp_basicsize
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
    0,                                   // tp_doc
    0,                                  // tp_traverse
    0,                                  // tp_clear
    0,                                  // tp_richcompare
    0,                                  // tp_weaklistoffset
    0,                                  // tp_iter
    0,                                  // tp_iternext
    g_CursorVarMethods,                  // tp_methods
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
// variable type declarations
//-----------------------------------------------------------------------------
dm_VarType vt_Cursor = {
    (InitializeProc) vCursor_Initialize,
    (FinalizeProc) vCursor_Finalize,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) vCursor_SetValue,
    (GetValueProc) vCursor_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)vCursor_BindObjectValue,
    &g_CursorVarType,                   // Python type
    DSQL_C_RSET,                        // cType    
    sizeof(dhstmt),                     // element length
    0,                                  // is character data
    0,                                  // is variable length
    0,                                  // can be copied
    0                                   // can be in array
};


//-----------------------------------------------------------------------------
// CursorVar_Initialize()
//   Initialize the variable.
//-----------------------------------------------------------------------------
static 
int 
vCursor_Initialize(
    dm_CursorVar*   var,        // variable to initialize
    dm_Cursor*      cursor      // cursor created by
)                 
{
    dm_Cursor*      tempCursor;
    udint4          i;

    Py_INCREF(cursor->connection);
    var->connection = cursor->connection;
    
    var->cursors    = PyList_New(var->allocatedElements);
    if (!var->cursors)
        return -1;
    for (i = 0; i < var->allocatedElements; i++) 
    {
        tempCursor  = (dm_Cursor*) Connection_NewCursor_Inner(var->connection, NULL);
        if (!tempCursor) 
        {
            Py_DECREF(var);
            return -1;
        }
        
        PyList_SET_ITEM(var->cursors, i, (PyObject*) tempCursor);
        var->data[i] = tempCursor->handle;
    }

    return 0;
}


//-----------------------------------------------------------------------------
// CursorVar_Finalize()
//   Prepare for variable destruction.
//-----------------------------------------------------------------------------
static 
void 
vCursor_Finalize(
    dm_CursorVar*  var // variable to free
)
{
    Py_CLEAR(var->connection);
    Py_CLEAR(var->cursors);
}


//-----------------------------------------------------------------------------
// CursorVar_SetValue()
//   Set the value of the variable.
//-----------------------------------------------------------------------------
static 
int 
vCursor_SetValue(
    dm_CursorVar*       var,    // variable to set value for
    unsigned            pos,    // array position to set
    PyObject*           value   // value to set
)                    
{
    dm_Cursor *cursor;

    if (!PyObject_IsInstance(value, (PyObject*) &g_CursorType)) 
    {
        PyErr_SetString(PyExc_TypeError, "expecting cursor");
        return -1;
    }

    cursor  = (dm_Cursor *) value;
    if (!cursor->isOpen)
    {
        PyErr_SetString(PyExc_TypeError, "expecting cursor openned");
        return -1;
    }

    Py_XDECREF(PyList_GET_ITEM(var->cursors, pos));
    
    Py_INCREF(value);
    PyList_SET_ITEM(var->cursors, pos, value);    

    var->data[pos]          = cursor->handle;
    cursor->statementType   = -1;

    var->indicator[pos]     = sizeof(dhstmt);
    var->actualLength[pos]  = sizeof(dhstmt);


    return 0;
}


//-----------------------------------------------------------------------------
// CursorVar_GetValue()
//   Set the value of the variable.
//-----------------------------------------------------------------------------
static 
PyObject*
vCursor_GetValue(
    dm_CursorVar*   var,    // variable to set value for
    unsigned        pos     // array position to set
)                       
{
    PyObject*       cursor;

    cursor = PyList_GET_ITEM(var->cursors, pos);
    ((dm_Cursor*) cursor)->statementType = -1;

    Py_INCREF(cursor);
    return cursor;
}

static 
int 
vCursor_BindObjectValue(
    dm_CursorVar*       var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
)
{
    DPIRETURN       rt = DSQL_SUCCESS;

    rt      = dpi_set_obj_val(hobj, val_nth, var->type->cType, (dpointer)var->data[pos], var->indicator[pos]);
    if (Environment_CheckForError(var->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "vCursor_BindObjectValue():dpi_set_obj_val") < 0)
    {
        return -1;
    }

    return 0;
}

static
PyObject*
CursorVar_GetValues(
    dm_CursorVar* var
)
{
    PyObject* cursor;

    cursor = PyList_GET_ITEM(var->cursors, 0);

    if(cursor == NULL)
        return NULL;
    ((dm_Cursor*)cursor)->statementType = -1;

    return PyObject_CallMethod((PyObject*)cursor, "fetchall", NULL);
}