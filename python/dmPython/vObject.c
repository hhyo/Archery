/******************************************************
file:
    vObject.c
purpose:
    python type define for DM OBJECT variables in dmPython,just used for data transforming.
interface:
    {}
history:
    Date        Who         RefDoc      Memo
    2015-6-11   shenning                Created
*******************************************************/

#include "var_pub.h"
#include "Error.h"
#include "py_Dameng.h"

//-----------------------------------------------------------------------------
// Declaration of object variable functions.
//-----------------------------------------------------------------------------
static int ObjectVar_Initialize(dm_ObjectVar*, dm_Cursor*);
static void ObjectVar_Finalize(dm_ObjectVar*);
static PyObject* ObjectVar_GetValue(dm_ObjectVar*, unsigned);
static int ObjectVar_SetValue(dm_ObjectVar*, unsigned, PyObject*);
static int ObjectVar_PreDefine(dm_ObjectVar*, dhdesc, sdint2);
static int ObjectVar_PreFetch(dm_ObjectVar*, dhdesc, sdint2);
static int ObjectVar_IsNull(dm_ObjectVar*, unsigned);
static int ObjectVar_BindObjectValue(dm_ObjectVar*, unsigned, dhobj, udint4);

//-----------------------------------------------------------------------------
// Python type declarations
//-----------------------------------------------------------------------------
PyTypeObject g_ObjectVarType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.OBJECTVAR",               // tp_name
    sizeof(dm_ObjectVar),               // tp_basicsize
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
    0,                                  // tp_doc
    0,                                  // tp_traverse
    0,                                  // tp_clear
    0,                                  // tp_richcompare
    0,                                  // tp_weaklistoffset
    0,                                  // tp_iter
    0,                                  // tp_iternext
    0,                                  // tp_methods
    0                                   // tp_members
};


//-----------------------------------------------------------------------------
// variable type declarations
//-----------------------------------------------------------------------------
dm_VarType vt_Object = {
    (InitializeProc) ObjectVar_Initialize,
    (FinalizeProc) ObjectVar_Finalize,
    (PreDefineProc) ObjectVar_PreDefine,
    (PreFetchProc) ObjectVar_PreFetch,
    (IsNullProc) ObjectVar_IsNull,
    (SetValueProc) ObjectVar_SetValue,
    (GetValueProc) ObjectVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)ObjectVar_BindObjectValue,
    &g_ObjectVarType,                   // Python type
    DSQL_C_CLASS,                       // cType    
    sizeof(dhobj),                     // element length
    0,                                  // is character data
    0,                                  // is variable length
    0,                                  // can be copied
    0                                   // can be in array
};

dm_VarType vt_Record = {
    (InitializeProc) ObjectVar_Initialize,
    (FinalizeProc) ObjectVar_Finalize,
    (PreDefineProc) ObjectVar_PreDefine,    
    (PreFetchProc) ObjectVar_PreFetch,
    (IsNullProc) ObjectVar_IsNull,
    (SetValueProc) ObjectVar_SetValue,
    (GetValueProc) ObjectVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)ObjectVar_BindObjectValue,
    &g_ObjectVarType,                   // Python type
    DSQL_C_RECORD,                      // cType    
    sizeof(dhobj),                     // element length
    0,                                  // is character data
    0,                                  // is variable length
    0,                                  // can be copied
    0                                   // can be in array
};

dm_VarType vt_Array = {
    (InitializeProc) ObjectVar_Initialize,
    (FinalizeProc) ObjectVar_Finalize,
    (PreDefineProc) ObjectVar_PreDefine,    
    (PreFetchProc) ObjectVar_PreFetch,
    (IsNullProc) ObjectVar_IsNull,
    (SetValueProc) ObjectVar_SetValue,
    (GetValueProc) ObjectVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)ObjectVar_BindObjectValue,
    &g_ObjectVarType,                   // Python type
    DSQL_C_ARRAY,                       // cType    
    sizeof(dhobj),                     // element length
    0,                                  // is character data
    0,                                  // is variable length
    0,                                  // can be copied
    0                                   // can be in array
};

dm_VarType vt_SArray = {
    (InitializeProc) ObjectVar_Initialize,
    (FinalizeProc) ObjectVar_Finalize,
    (PreDefineProc) ObjectVar_PreDefine,    
    (PreFetchProc) ObjectVar_PreFetch,
    (IsNullProc) ObjectVar_IsNull,
    (SetValueProc) ObjectVar_SetValue,
    (GetValueProc) ObjectVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)ObjectVar_BindObjectValue,
    &g_ObjectVarType,                   // Python type
    DSQL_C_SARRAY,                      // cType    
    sizeof(dhobj),                     // element length
    0,                                  // is character data
    0,                                  // is variable length
    0,                                  // can be copied
    0                                   // can be in array
};


//-----------------------------------------------------------------------------
// ObjectVar_Initialize()
//   Initialize the variable.
//-----------------------------------------------------------------------------
static 
int 
ObjectVar_Initialize(
    dm_ObjectVar*       self,    // variable to initialize
    dm_Cursor*          cursor   // cursor to use
)
{
    udint4  i;

    Py_INCREF(cursor);
    self->cursor        = cursor;

    for (i = 0; i < self->allocatedElements; i++) 
    {
        self->data[i] = NULL;     
    }
    
    self->desc          = NULL;

    self->exObjects     = PyList_New(self->allocatedElements);
    if (self->exObjects == NULL)
        return -1;

    return 0;
}


//-----------------------------------------------------------------------------
// ObjectVar_Finalize()
//   Prepare for variable destruction.
//-----------------------------------------------------------------------------
static 
void 
ObjectVar_Finalize(
    dm_ObjectVar *self // variable to free
)                
{
    udint4                  i;
    dm_ExternalObjectVar*   exObj;

    for (i = 0; i < self->allocatedElements; i++) 
    {
        if (self->exObjects != NULL && PyList_GET_SIZE(self->exObjects) > 0)
            exObj   = (dm_ExternalObjectVar*)PyList_GET_ITEM(self->exObjects, i);
        else
            exObj   = NULL;

        /** 若通过exObject赋值的句柄，则不预释放，由ex自行释放 **/
        if (self->data[i] != NULL && 
            (exObj == NULL || exObj->hobj != self->data[i]))
        {
            dpi_unbind_obj_desc(self->data[i]);
            dpi_free_obj(self->data[i]);
        }
        self->data[i] = NULL;
    }    

    /** 若通过exObject赋值的句柄，则不预释放，由ex自行释放;通过cursor获取的描述句柄由游标句柄释放，所以，此处无需释放 **/    
    self->desc  = NULL;    
    
    Py_CLEAR(self->exObjects);
    Py_CLEAR(self->cursor);
}

int
ObjectVar_GetParamDescHandle(
    dm_ObjectVar*   self,            // variable to set up    
    dhdesc          hdesc_param,
    sdint2          pos,              // position in define list，1-based
    dhobjdesc*      hobjdesc_out
)
{
    DPIRETURN       rt = DSQL_SUCCESS;
    dhobjdesc       objdesc;

    *hobjdesc_out   = NULL;

    rt          = dpi_get_desc_field(hdesc_param, pos, DSQL_DESC_OBJ_DESCRIPTOR, (dpointer)&objdesc, sizeof(dhobjdesc), NULL);
    if (Environment_CheckForError(self->environment, hdesc_param, DSQL_HANDLE_DESC, rt,
        "ObjectVar_GetParamDescHandle():dpi_get_desc_field[DSQL_DESC_OBJ_DESCRIPTOR]") < 0)
    {
        return -1;		
    }

    *hobjdesc_out   = objdesc;
    return 0;
}

int
ObjectVar_GetParamObjHandle(
    dm_ObjectVar*   self,            // variable to set up    
    dhobjdesc       hobjdesc,        // desc handle to bind
    dhobj*          hobj_out
)
{
    DPIRETURN       rt = DSQL_SUCCESS;
    dhobj           hobj;

    *hobj_out   = NULL;

    rt      = dpi_alloc_obj(self->connection->hcon, &hobj);
    if (Environment_CheckForError(self->environment, self->connection->hcon, DSQL_HANDLE_DBC, rt, 
        "ObjectVar_GetParamObjHandle():dpi_alloc_obj") < 0)
    {
        return -1;
    }

    rt      = dpi_bind_obj_desc(hobj, hobjdesc);
    if (Environment_CheckForError(self->environment, self->connection->hcon, DSQL_HANDLE_DBC, rt, 
        "ObjectVar_GetParamObjHandle():dpi_bind_obj_desc") < 0)
    {
        dpi_free_obj(hobj);
        return -1;
    }

    *hobj_out   = hobj;
    return 0;
}

int
ObjectVar_GetParamDescAndObjHandles(
    dm_ObjectVar*   self,            // variable to set up    
    dhdesc          hdesc_param,
    sdint2          pos              // position in define list，1-based
)
{    
    udint4          i;    
    
    if (self->desc == NULL &&
        ObjectVar_GetParamDescHandle(self, hdesc_param, pos, &self->desc) < 0)
        return -1;

    for (i = 0; i < self->allocatedElements; i ++)
    {
        if (self->data[i] != NULL)
        {
            dpi_unbind_obj_desc(self->data[i]);
            dpi_free_obj(self->data[i]);

            self->data[i]           = NULL;
            self->indicator[i]      = DSQL_NULL_DATA;
            self->actualLength[i]   = DSQL_NULL_DATA;
        }
        
        if (ObjectVar_GetParamObjHandle(self, self->desc, &self->data[i]) < 0)
            goto fun_end;

        self->indicator[i]          = sizeof(dhobj);
        self->actualLength[i]       = sizeof(dhobj);
    }

    return 0;

fun_end:
    for (i = 0; i < self->allocatedElements; i ++)
    {
        if (self->data[i] != NULL)
        {
            dpi_unbind_obj_desc(self->data[i]);
            dpi_free_obj(self->data[i]);
            
            self->data[i]           = NULL;
            self->indicator[i]      = DSQL_NULL_DATA;
            self->actualLength[i]   = DSQL_NULL_DATA;
        }        
    }

    return 0;
}

//-----------------------------------------------------------------------------
// ObjectVar_PreDefine()
//   Performs additional steps required for defining objects.
//-----------------------------------------------------------------------------
static int ObjectVar_PreDefine(
    dm_ObjectVar*   self,            // variable to set up    
    dhdesc          hdesc_col,
    sdint2          pos              // position in define list，1-based
)   
{
    return ObjectVar_GetParamDescAndObjHandles(self, hdesc_col, pos);
}

static 
int 
ObjectVar_PreFetch(
    dm_ObjectVar*   self,            // variable to set up    
    dhdesc          hdesc_col,
    sdint2          pos              // position in define list，1-based
)
{    
    /** 一定先执行predefine **/    
    if (self->desc == NULL)
    {
        PyErr_SetString(g_ProgrammingErrorException, 
            "ObjectVar_PreDefine does not execute.");
        return -1;
    }    

    return ObjectVar_GetParamDescAndObjHandles(self, hdesc_col, pos);    
}

//-----------------------------------------------------------------------------
// ObjectVar_IsNull()
//   Returns a boolean indicating if the variable is null or not.
//-----------------------------------------------------------------------------
static 
int 
ObjectVar_IsNull(
    dm_ObjectVar*   self,   // variable to set up
    unsigned        pos     // position to check
)                       
{    
    return (self->data[pos] == NULL || self->indicator[pos] == DSQL_NULL_DATA);
}


//-----------------------------------------------------------------------------
// ObjectVar_GetValue()
//   Returns the value stored at the given array position.
//-----------------------------------------------------------------------------
static 
PyObject*
ObjectVar_GetValue(
    dm_ObjectVar*   self,  // variable to determine value for
    unsigned        pos    // array position
)                       
{
    PyObject*       var;

    // only allowed to get the value once (for now)
    if (!self->data[pos]) 
    {
        PyErr_SetString(g_ProgrammingErrorException,
                "variable value can only be acquired once");
        return NULL;
    }
    
    // for objects, return a representation of the object
    var = ExObjVar_New_FromObjVar(self, self->desc, self->data[pos]);    

    /** 清空，不允许再次获取，由ExObjVar获取数据后，释放 **/
    self->data[pos] = NULL;

    if (var == NULL)
        return NULL;
            
    return var;
}

int
ObjectVar_SetValue_Inner(
    dm_ObjectVar*   var, 
    unsigned        pos, 
    dhobj           hobj,
    dhobjdesc       hobjdesc
)
{
    var->data[pos]          = hobj;
    var->desc               = hobjdesc;

    var->indicator[pos]     = sizeof(dhobj);
    var->actualLength[pos]  = sizeof(dhobj);

    return 0;
}

static 
int 
ObjectVar_SetValue(
    dm_ObjectVar*   var, 
    unsigned        pos, 
    PyObject*       Value)
{
    dm_ExternalObjectVar*  exObjVar;

    if (!PyObject_IsInstance(Value, (PyObject*) &g_ExternalObjectVarType))
    {
        PyErr_SetString(PyExc_TypeError, "expecting OBJECT");
        return -1;
    }

    exObjVar                = (dm_ExternalObjectVar*)Value;    

    if (ExObjVar_MatchCheck(exObjVar, var->desc, var->data[pos], NULL) < 0)
        return -1;

    Py_XDECREF(PyList_GET_ITEM(var->exObjects, pos));

    Py_INCREF(Value);
    PyList_SET_ITEM(var->exObjects, pos, Value);    

    return 0;
}

static 
int 
ObjectVar_BindObjectValue(
    dm_ObjectVar*       var, 
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

PyObject*
ObjectVar_GetBoundExObj(
    dm_ObjectVar*       var, 
    unsigned            pos
)
{
    PyObject*       boundList;
    Py_ssize_t      size;  
    PyObject*       retObj;

    boundList   = var->exObjects;
    if (boundList == NULL)
    {
        PyErr_SetString(g_ProgrammingErrorException, 
            "ObjectVar value does not initialize.");
        return NULL;
    }

    size        = PyList_GET_SIZE(boundList);
    if (size == 0)
    {
        PyErr_SetString(g_ProgrammingErrorException, 
            "No ExObjectVar bound to ObjectVar.");
        return NULL;
    }

    retObj      = PyList_GetItem(boundList, pos);
    if (retObj == NULL)
        return NULL;

    Py_INCREF(retObj);
    return retObj;
}

