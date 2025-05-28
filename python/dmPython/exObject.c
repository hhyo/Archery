/******************************************************
file:
    exObject.c
purpose:
    defines for DM OBJECT variables handing external to dmPython
interface:
    {}
history:
    Date        Who         RefDoc      Memo
    2015-6-11   shenning                Created
*******************************************************/

#include "Error.h"
#include "var_pub.h"
#include "Buffer.h"
#include "py_Dameng.h"

//-----------------------------------------------------------------------------
// Declaration of external object variable functions.
//-----------------------------------------------------------------------------
static void ExternalObjectVar_Free(dm_ExternalObjectVar*);
static PyObject* ExternalObjectVar_New(PyTypeObject*, PyObject*, PyObject*);
static int ExternalObjectVar_Init(dm_ExternalObjectVar*, PyObject*, PyObject*);
PyObject* ExObjVar_ArrayConvertToPython(dm_ObjectType*, dhobjdesc, dhobj, dm_Cursor*);
PyObject* ExObjVar_StructConvertToPython(dm_ObjectType*, dhobjdesc, dhobj, dm_Cursor*);
int ExObjVar_MatchStruct(dm_Connection*, dm_Cursor*, dm_ObjectType*, PyObject*, dhobj, dhobjdesc, int);
int ExObjVar_MatchArray(dm_Connection*, dm_Cursor*, dm_ObjectType*, PyObject*, dhobj, dhobjdesc, int);
static PyObject* ExObjVar_GetValues(dm_ExternalObjectVar*);
static PyObject* ExObjVar_SetValues(dm_ExternalObjectVar*, PyObject*, PyObject*);
static int ExObjVar_get_ValueCount(dm_Connection*, dhobj, udint4*);

static
int
ExObjVar_Struct_Rebind(
    dm_Connection*          connection,
    dm_Cursor*              ownCursor,
    dm_ObjectType*          objType,        
    dhobj                   strt_hobj,
    dhobjdesc               strt_hdesc
);

static
int
ExObjVar_Array_Rebind(
    dm_Connection*          connection,
    dm_Cursor*              ownCursor,
    dm_ObjectType*          objType,        
    dhobj                   arr_hobj,
    dhobjdesc               arr_hdesc
);

int
ExObjVar_Read_Check(
    dm_ExternalObjectVar*  var
)
{    
    if (var->objectValue == NULL)
    {
        PyErr_SetString(PyExc_ValueError, 
            "Invalid variable value.");

        return -1;
    }

    return 0;
}

int
ExObjVar_Write_Check(
    dm_ExternalObjectVar*  var
)
{
    dm_ObjectVar*          obj_var = var->refered_objVar;

    /** 解析服务器参数所得 **/
    if (obj_var != NULL &&
        obj_var->connection != NULL)
    {
        if (obj_var->connection->isConnected <= 0)
        {
            PyErr_SetString(PyExc_ValueError, 
                "The related cursor or connection is closed");

            return -1;
        }        
        else if (obj_var->cursor->execute_num != var->cursor_execNum)
        {
            PyErr_SetString(PyExc_ValueError, 
                "The Object is invalid after subsequent execute");

            return -1;
        }        
    }  
    else if (var->connection != NULL) /** 外部创建 **/
    {
        if (var->connection->isConnected <= 0)
        {
            PyErr_SetString(PyExc_ValueError, 
                "The connection which the Object come from is closed");

            return -1;
        }
    }
    
    return 0;
}

//-----------------------------------------------------------------------------
// Declaration of external object variable members.
//-----------------------------------------------------------------------------
static PyMemberDef g_ExternalObjectVarMembers[] = {
    { "type",       T_OBJECT, offsetof(dm_ExternalObjectVar, objectType),    READONLY },    
    { "valuecount", T_INT, offsetof(dm_ExternalObjectVar, value_count),      READONLY },
    { NULL }
};

//-----------------------------------------------------------------------------
// declaration of methods for Python type "external object"
//-----------------------------------------------------------------------------
static PyMethodDef g_ExternalObjectVarMethods[] = {
    { "getvalue",       (PyCFunction) ExObjVar_GetValues,     METH_NOARGS},
    { "setvalue",       (PyCFunction) ExObjVar_SetValues,     METH_VARARGS | METH_KEYWORDS},    
    {NULL }
};

//-----------------------------------------------------------------------------
// Python type declaration
//-----------------------------------------------------------------------------
PyTypeObject g_ExternalObjectVarType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.OBJECT",                  // tp_name
    sizeof(dm_ExternalObjectVar),       // tp_basicsize
    0,                                  // tp_itemsize
    (destructor) ExternalObjectVar_Free,// tp_dealloc
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
    0, // tp_getattro (getattrofunc) ExternalObjectVar_GetAttr
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
    g_ExternalObjectVarMethods,         // tp_methods
    g_ExternalObjectVarMembers,         // tp_members
    0,                                  // tp_getset
    0,                                  // tp_base
    0,                                  // tp_dict
    0,                                  // tp_descr_get
    0,                                  // tp_descr_set
    0,                                  // tp_dictoffset
    (initproc)ExternalObjectVar_Init,   // tp_init
    0,                                  // tp_alloc
    (newfunc)ExternalObjectVar_New,     // tp_new
    0,                                  // tp_free
    0,                                  // tp_is_gc
    0                                   // tp_bases
};


//-----------------------------------------------------------------------------
// ExternalObjectVar_New()
//   Create a new external LOB variable.
//-----------------------------------------------------------------------------
int
ExternalObjectVar_Alloc_hobj(
    dm_Connection*          connection,
    dhobjdesc               hobjdesc,
    dhobj*                  hobj_out
)
{
    DPIRETURN           rt = DSQL_SUCCESS;
    dhobj               hobj;

    *hobj_out   = NULL;

    rt      = dpi_alloc_obj(connection->hcon, &hobj);
    if (Environment_CheckForError(connection->environment, connection->hcon, DSQL_HANDLE_DBC, rt, 
        "ExternalObjectVar_Alloc_hobj():dpi_alloc_obj") < 0)
    {        
        return -1;
    }

    rt      = dpi_bind_obj_desc(hobj, hobjdesc);
    if (Environment_CheckForError(connection->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "ExternalObjectVar_Alloc_hobj():dpi_bind_obj_desc") < 0)
    {
        dpi_free_obj(hobj);        
        return -1;
    }

    *hobj_out   = hobj;

    return 0;
}

int
ExternalObjectVar_Alloc_handle(
    dm_Connection*          connection,
    PyObject*               nameObj,
    PyObject*               pkgObj,
    PyObject*               schemaObj,
    dhobjdesc*              out_hdesc,
    dhobj*                  out_hobj
)
{
    DPIRETURN           rt = DSQL_SUCCESS;
    sdbyte*             schname = NULL;
    sdbyte*             pkgname = NULL;
    sdbyte*             name = NULL;
    dm_Buffer           name_bf;
    dm_Buffer           pkg_bf;
    dm_Buffer           schema_bf;
    dhobjdesc           hobjdesc;
    dhobj               hobj;

    *out_hdesc  = NULL;
    *out_hobj   = NULL;

    /** 判断连接是否有效 **/
    if (connection->hcon == NULL)
    {
        PyErr_SetString(g_ProgrammingErrorException, "connection is closed or not open");
        return -1;
    }

    if (connection->isConnected == 0)
    {
        PyErr_SetString(g_ProgrammingErrorException, "connection is logout or not login");
        return -1;
    }

    if (dmBuffer_FromObject(&name_bf, nameObj, connection->environment->encoding) < 0)
    {        
        return -1;
    }
    name        = (sdbyte*)name_bf.ptr;

    if (schemaObj != NULL && schemaObj != Py_None)
    {
        if (dmBuffer_FromObject(&schema_bf, schemaObj, connection->environment->encoding) < 0)
        {
            dmBuffer_Clear(&name_bf);            
            return -1;
        }

        schname     = (sdbyte*)schema_bf.ptr;
    } 

    if (pkgObj != NULL && pkgObj != Py_None)
    {
        if (dmBuffer_FromObject(&pkg_bf, pkgObj, connection->environment->encoding) < 0)
        {
            dmBuffer_Clear(&pkg_bf);            
            return -1;
        }

        pkgname     = (sdbyte*)pkg_bf.ptr;
    } 

    rt      = dpi_desc_obj2(connection->hcon, schname, pkgname, name, &hobjdesc);
    if (schemaObj != NULL && schemaObj != Py_None)
    {
        dmBuffer_Clear(&schema_bf);
    }

    if (pkgObj != NULL &&pkgObj != Py_None)
    {
        dmBuffer_Clear(&pkg_bf);
    }

    dmBuffer_Clear(&name_bf);

    if (Environment_CheckForError(connection->environment, connection->hcon, DSQL_HANDLE_DBC, rt, 
        "ExternalObjectVar_Alloc_handle():dpi_desc_obj") < 0)
    {
        return -1;
    }

    if (ExternalObjectVar_Alloc_hobj(connection, hobjdesc, &hobj) < 0)
    {
        dpi_free_obj_desc(hobjdesc);
        return -1;
    }    

    *out_hdesc  = hobjdesc;
    *out_hobj   = hobj;

    return 0;
}

int
ExObjVar_MatchNormalOfArray(
    dm_Cursor*              ownCursor,
    dm_ObjectType*          objType,
    PyObject*               objectValue,
    dhobj                   arr_hobj,
    dhobjdesc               arr_hdesc
)
{
    udint4              value_cnt = 0;
    udint4              i;
    dm_VarType*         varType;
    dm_Var*             varValue; 
    PyObject*           iObject;

    /** 重置转换后的变量值 **/
    if (objType->varValue != NULL)
    {
        Py_CLEAR(objType->varValue);
        objType->varValue   = NULL;
    }

    value_cnt   = PyList_Size(objectValue);
   
    varType     = dmVar_TypeBySQLType(objType->sql_type, 1);
    if (varType == NULL)
        return -1;

    varValue    = dmVar_NewByVarType(ownCursor, varType, value_cnt, objType->prec);
    if (varValue == NULL)
        return -1;
    
    for (i = 0; i < value_cnt; i ++)
    {
        iObject = PyList_GET_ITEM(objectValue, i);

        if (dmVar_SetValue(varValue, i, iObject) < 0)
        {
            Py_CLEAR(varValue);
            return -1;
        }

        if (dmVar_BindObjectValue(varValue, i, arr_hobj, i + 1) < 0)
        {
            Py_CLEAR(varValue);
            return -1;
        }        
    }

    objType->varValue   = (PyObject*)varValue;
    return 0;
}

int
ExObjVar_GetSubHandle_IfNecc(
    dm_Connection*          connection,    
    udint4                  attr_nth,
    dm_ObjectType*          attr_ObjType,
    dhobj                   hobj,
    dhobjdesc               hdesc,
    dhobj*                  sub_hobj,
    dhobjdesc*              sub_hdesc
)
{
    DPIRETURN           rt = DSQL_SUCCESS;
    dhobjdesc           shdesc;
    dhobj               shobj;    
    dm_VarType*         varType;

    *sub_hdesc  = NULL;
    *sub_hobj   = NULL;    

    if (ObjectType_IsObjectType(attr_ObjType) == 0)
        return 0;    

    varType     = dmVar_TypeBySQLType(attr_ObjType->sql_type, 1);
    if (varType == NULL)
        return -1;

    rt  = dpi_get_obj_desc_attr(hdesc, attr_nth, DSQL_ATTR_OBJ_DESC, &shdesc, sizeof(dhobjdesc), NULL);
    if (Environment_CheckForError(attr_ObjType->environment, hdesc, DSQL_HANDLE_OBJDESC, rt, 
        "ExObjVar_AllocSubHandle_IfNecc():dpi_get_obj_desc_attr") < 0)
    {
        return -1;
    }    

    rt  = dpi_alloc_obj(connection->hcon, &shobj);
    if (Environment_CheckForError(attr_ObjType->environment, connection->hcon, DSQL_HANDLE_DBC, rt, 
        "ExObjVar_AllocSubHandle_IfNecc():dpi_alloc_obj") < 0)
    {
        return -1;
    }

    rt  = dpi_bind_obj_desc(shobj, shdesc);
    if (Environment_CheckForError(attr_ObjType->environment, shobj, DSQL_HANDLE_OBJECT, rt, 
        "ExObjVar_AllocSubHandle_IfNecc():dpi_bind_obj_desc") < 0)
    {
        dpi_free_obj(shobj);
        return -1;
    }

    *sub_hdesc  = shdesc;
    *sub_hobj   = shobj;    

    return 0;
}

int
ExObjVar_GetSubAttr_IfNecc(
    dm_Connection*          connection,
    dm_ObjectType*          objType, 
    udint4                  attr_nth,    
    dm_ObjectType**         sub_objType
)
{    
    *sub_objType   = NULL;

    if (ObjectType_IsObjectType(objType) == 0)
        return 0;

    *sub_objType    = ((dm_ObjectAttribute*)PyList_GET_ITEM(objType->attributes, attr_nth - 1))->ObjType;
    if (dmVar_TypeBySQLType((*sub_objType)->sql_type, 1) == NULL)
        return -1;

    return 0;
}

int
ExObjVar_MatchArray(
    dm_Connection*          connection,
    dm_Cursor*              ownCursor,
    dm_ObjectType*          objType,    
    PyObject*               objectValue,    
    dhobj                   arr_hobj,
    dhobjdesc               arr_hdesc,
    int                     use_SQLType
)
{
    udint4                  value_cnt = 0;
    int                     ret = -1;    
    dm_ObjectType*          sub_ObjType = NULL;        
    udint4                  i;
    dm_VarType*             varType;
    dm_Var*                 varValue = NULL; 
    PyObject*               iObject;
    dhobj                   sub_hobj = NULL;
    dhobjdesc               sub_hdesc = NULL;
    udint4                  size;
    PyObject*               varValue_lst = NULL;

    if (!PyList_Check(objectValue))
    {
        PyErr_SetString(PyExc_TypeError, 
            "expecting a List of Value");
        return -1;
    }    

    if (ExObjVar_GetSubAttr_IfNecc(connection, objType, 1, &sub_ObjType) < 0)
    {        
        return -1;
    }

    value_cnt       = PyList_Size(objectValue);
    varValue_lst    = PyList_New(value_cnt);
    if (varValue_lst == NULL)
        return -1;    

    for (i = 0; i < value_cnt; i ++)
    {        
        iObject         = PyList_GET_ITEM(objectValue, i);
        if (iObject == Py_None)
        {            
            varType     = dmVar_TypeByValue(iObject, &size);
            if (varType == NULL)
                return -1;

            varValue    = dmVar_New(ownCursor, 1, varType, size);
            if (varValue == NULL)
                return -1;

            if (dmVar_SetValue(varValue, 0, iObject) < 0)
                goto fun_end;

            if (dmVar_BindObjectValue(varValue, 0, arr_hobj, i + 1) < 0)
                goto fun_end;

            if (PyList_SetItem(varValue_lst, i, (PyObject*)varValue) < 0)
                goto fun_end;

            continue;
        }

        if (ExObjVar_GetSubHandle_IfNecc(connection, i + 1, sub_ObjType, arr_hobj, arr_hdesc, &sub_hobj, &sub_hdesc) < 0)
            goto fun_end;

        switch (sub_ObjType->sql_type)
        {
        case DSQL_ARRAY:
        case DSQL_SARRAY:            
            if (ExObjVar_MatchArray(connection, ownCursor, sub_ObjType, iObject, sub_hobj, sub_hdesc, use_SQLType) < 0)
                goto fun_end;

            varType     = dmVar_TypeBySQLType(sub_ObjType->sql_type, 1);
            if (varType == NULL)
                return -1;

            varValue    = dmVar_NewByVarType(ownCursor, varType, 1, sub_ObjType->prec);
            if (varValue == NULL)
                return -1;        

            ObjectVar_SetValue_Inner((dm_ObjectVar*)varValue, 0, sub_hobj, sub_hdesc);
            break;

        case DSQL_RECORD:
        case DSQL_CLASS:            
            if (ExObjVar_MatchStruct(connection, ownCursor, sub_ObjType, iObject, sub_hobj, sub_hdesc, use_SQLType) < 0)
                goto fun_end;

            varType     = dmVar_TypeBySQLType(sub_ObjType->sql_type, 1);
            if (varType == NULL)
                return -1;

            varValue    = dmVar_NewByVarType(ownCursor, varType, 1, sub_ObjType->prec);
            if (varValue == NULL)
                return -1;  

            ObjectVar_SetValue_Inner((dm_ObjectVar*)varValue, 0, sub_hobj, sub_hdesc);
            break;

        default:
            if (use_SQLType != 0)
            {
                varType = dmVar_TypeBySQLType(sub_ObjType->sql_type, 1);

                /** 变长类型，使用实际数据计算size **/
                if (varType != NULL && varType->isVariableLength)
                {
                    if (py_String_Check(iObject))
                    {
                        size    = py_String_GetSize(iObject);
                    }
#if PY_MAJOR_VERSION >= 3
                    else if (PyBytes_Check(iObject))
                    {
                        size    = PyBytes_GET_SIZE(iObject);
                    }
#endif
                    else
                    {
                        PyErr_SetString(PyExc_TypeError,
                            "invalid variable length type.");
                        return -1;
                    }
                }
            }
            else
                varType = dmVar_TypeByValue(iObject, &size);
            if (varType == NULL)
                return -1;

            varValue    = dmVar_New(ownCursor, 1, varType, size);
            if (varValue == NULL)
                return -1;

            if (dmVar_SetValue(varValue, 0, iObject) < 0)
                goto fun_end;       

            break;
        }    

        if (dmVar_BindObjectValue(varValue, 0, arr_hobj, i + 1) < 0)
            goto fun_end;

        if (PyList_SetItem(varValue_lst, i, (PyObject*)varValue) < 0)
            goto fun_end;

        sub_hobj    = NULL;
        sub_hdesc   = NULL;
    }

    /** 重置转换后的变量值 **/
    if (sub_ObjType->varValue != NULL)
    {
        Py_CLEAR(objType->varValue);
        sub_ObjType->varValue   = NULL;
    }

    sub_ObjType->varValue       = varValue_lst;
    ret = 0;

fun_end:
    if (ret < 0)
    {
        if (sub_hobj != NULL)
        {
            dpi_unbind_obj_desc(sub_hobj);
            dpi_free_obj(sub_hobj);
        }        

        Py_CLEAR(varValue);

        Py_CLEAR(varValue_lst);
    }

    return ret;
}

int
ExObjVar_MatchStruct(
    dm_Connection*          connection,
    dm_Cursor*              ownCursor,
    dm_ObjectType*          objType,    
    PyObject*               objectValue,    // value list of a struct    
    dhobj                   strt_hobj,
    dhobjdesc               strt_hdesc,
    int                     use_SQLType
)
{
    udint4                  field_cnt;
    udint4                  value_cnt;
    udint4                  i;
    PyObject*               iObject;
    dm_ObjectType*          sub_ObjType;
    dm_VarType*             varType;
    dm_Var*                 varValue;
    dhobj                   sub_hobj = NULL;
    dhobjdesc               sub_hdesc = NULL;    
    udint4                  size;    

    if (!PyList_Check(objectValue))
    {
        PyErr_SetString(PyExc_TypeError, 
            "expecting a List of Value");
        return -1;
    }

    field_cnt   = PyList_Size(objType->attributes);
    value_cnt   = PyList_GET_SIZE(objectValue);

    for (i = 0; i < field_cnt; i ++)
    {
        if (ExObjVar_GetSubAttr_IfNecc(connection, objType, i + 1, &sub_ObjType) < 0)
            return -1;        

        if (i < value_cnt)
            iObject = PyList_GET_ITEM(objectValue, i);
        else
            iObject = Py_None;

        /** DSQL_NULL_DATA **/
        if (iObject == Py_None)
        {
            varType     = dmVar_TypeByValue(iObject, &size);
            if (varType == NULL)
                return -1;

            varValue    = dmVar_New(ownCursor, 1, varType, size);
            if (varValue == NULL)
                return -1;

            if (dmVar_SetValue(varValue, 0, iObject) < 0)
            {
                Py_CLEAR(varValue);
                return -1;
            }

            if (dmVar_BindObjectValue(varValue, 0, strt_hobj, i + 1) < 0)            
            {
                Py_CLEAR(varValue);
                return -1;
            }

            /** 重置已经转换的变量值，dpi层直接赋值，所以，本地需缓存 **/
            if (sub_ObjType->varValue != NULL)
            {                
                Py_CLEAR(sub_ObjType->varValue);
                sub_ObjType->varValue = NULL;
            }

            sub_ObjType->varValue       = (PyObject*)varValue;
            
            continue;
        }

        if (ExObjVar_GetSubHandle_IfNecc(connection, i + 1, sub_ObjType, strt_hobj, strt_hdesc, &sub_hobj, &sub_hdesc) < 0)
            return -1;                

        if (sub_ObjType->sql_type == DSQL_ARRAY ||
            sub_ObjType->sql_type == DSQL_SARRAY)
        {
            if (ExObjVar_MatchArray(connection, ownCursor, sub_ObjType, iObject, sub_hobj, sub_hdesc, use_SQLType) < 0)             
            {
                dpi_unbind_obj_desc(sub_hobj);
                dpi_free_obj(sub_hobj);
                
                return -1;
            }

            varType     = dmVar_TypeBySQLType(sub_ObjType->sql_type, 1);
            if (varType == NULL)
                return -1;

            varValue    = dmVar_NewByVarType(ownCursor, varType, 1, sub_ObjType->prec);
            if (varValue == NULL)
                return -1;

            ObjectVar_SetValue_Inner((dm_ObjectVar*)varValue, 0, sub_hobj, sub_hdesc);
        }
        else if (sub_ObjType->sql_type == DSQL_RECORD ||
                 sub_ObjType->sql_type == DSQL_CLASS)
        {
            if (ExObjVar_MatchStruct(connection, ownCursor, sub_ObjType, iObject, sub_hobj, sub_hdesc, use_SQLType) < 0)            
            {
                dpi_unbind_obj_desc(sub_hobj);
                dpi_free_obj(sub_hobj);
                
                return -1;
            }

            varType     = dmVar_TypeBySQLType(sub_ObjType->sql_type, 1);
            if (varType == NULL)
                return -1;

            varValue    = dmVar_NewByVarType(ownCursor, varType, 1, sub_ObjType->prec);
            if (varValue == NULL)
                return -1;

            ObjectVar_SetValue_Inner((dm_ObjectVar*)varValue, 0, sub_hobj, sub_hdesc);
        }
        else
        {
            if (use_SQLType != 0)
            {
                varType = dmVar_TypeBySQLType(sub_ObjType->sql_type, 1);
                
                /** 变长类型，使用实际数据计算size **/
                if (varType != NULL && varType->isVariableLength)
                {
                    if (py_String_Check(iObject))
                    {
                        size    = py_String_GetSize(iObject);
                    }
#if PY_MAJOR_VERSION >= 3
                    else if (PyBytes_Check(iObject))
                    {
                        size    = PyBytes_GET_SIZE(iObject);
                    }
#endif
                    else
                    {
                        PyErr_SetString(PyExc_TypeError,
                            "invalid variable length type.");
                        return -1;
                    }
                }
            }
            else
                varType = dmVar_TypeByValue(iObject, &size);
            if (varType == NULL)
                return -1;

            varValue    = dmVar_New(ownCursor, 1, varType, size);
            if (varValue == NULL)
                return -1;

            if (dmVar_SetValue(varValue, 0, iObject) < 0)
            {
                Py_CLEAR(varValue);
                return -1;
            }            
        }

        if (dmVar_BindObjectValue(varValue, 0, strt_hobj, i + 1) < 0)            
        {
            if (sub_hobj != NULL)
            {
                dpi_unbind_obj_desc(sub_hobj);
                dpi_free_obj(sub_hobj);
            }

            Py_CLEAR(varValue);
            return -1;
        }

        /** 重置已经转换的变量值，dpi层直接赋值，所以，本地需缓存 **/
        if (sub_ObjType->varValue != NULL)
        {                
            Py_CLEAR(sub_ObjType->varValue);
            sub_ObjType->varValue   = NULL;
        }

        sub_ObjType->varValue       = (PyObject*)varValue;

        sub_hobj    = NULL;
        sub_hdesc   = NULL;
    }

    return 0;
}

/** 匹配描述与值 **/
int
ExObjVar_MatchHandle(
    dm_ExternalObjectVar*   self,
    dhobjdesc               hobjdesc,
    dhobj                   hobj
)
{       
    if (self->objectType->sql_type == DSQL_ARRAY ||
        self->objectType->sql_type == DSQL_SARRAY)
        return ExObjVar_MatchArray(self->connection, self->ownCursor, self->objectType, self->objectValue, hobj, hobjdesc, 0);

    return ExObjVar_MatchStruct(self->connection, self->ownCursor, self->objectType, self->objectValue, hobj, hobjdesc, 0);
}

/** 匹配描述与值 **/
int
ExObjVar_MatchHandle_useSQLType(
    dm_ExternalObjectVar*   self,
    dhobjdesc               hobjdesc,
    dhobj                   hobj
)
{       
    if (self->objectType->sql_type == DSQL_ARRAY ||
        self->objectType->sql_type == DSQL_SARRAY)
        return ExObjVar_MatchArray(self->connection, self->ownCursor, self->objectType, self->objectValue, hobj, hobjdesc, 1);

    return ExObjVar_MatchStruct(self->connection, self->ownCursor, self->objectType, self->objectValue, hobj, hobjdesc, 1);
}

static
int
ExObjVar_Struct_Rebind(
    dm_Connection*          connection,
    dm_Cursor*              ownCursor,
    dm_ObjectType*          objType,        
    dhobj                   strt_hobj,
    dhobjdesc               strt_hdesc
)
{
    udint4                  field_cnt;    
    udint4                  i;
    dm_ObjectType*          sub_ObjType;    
    dm_Var*                 varValue;
    dhobj                   sub_hobj = NULL;
    dhobjdesc               sub_hdesc = NULL;   
    dhobj                   org_sub_hobj = NULL; 
    dhobjdesc               org_sub_hdesc = NULL;

    field_cnt   = PyList_Size(objType->attributes);    

    for (i = 0; i < field_cnt; i ++)
    {
        if (ExObjVar_GetSubAttr_IfNecc(connection, objType, i + 1, &sub_ObjType) < 0)
            return -1; 

        if (sub_ObjType->varValue == NULL)
        {
            PyErr_SetString(g_ProgrammingErrorException, 
                "ExObject value has not be initialized");
            return -1;
        }

        varValue    = (dm_Var*)sub_ObjType->varValue;
        if (varValue->type->pythonType == &g_ObjectVarType)
        {
            if (ExObjVar_GetSubHandle_IfNecc(connection, i + 1, sub_ObjType, strt_hobj, strt_hdesc, &sub_hobj, &sub_hdesc) < 0)
                return -1;                

            if (sub_ObjType->sql_type == DSQL_ARRAY ||
                sub_ObjType->sql_type == DSQL_SARRAY)
            {
                if (ExObjVar_Array_Rebind(connection, ownCursor, sub_ObjType, sub_hobj, sub_hdesc) < 0)
                    return -1;
            }
            else
            {
                if (ExObjVar_Struct_Rebind(connection, ownCursor, sub_ObjType, sub_hobj, sub_hdesc) < 0)
                    return -1;
            }

            org_sub_hobj    = ((dm_ObjectVar*)varValue)->data[0];
            org_sub_hdesc   = ((dm_ObjectVar*)varValue)->desc;

            ObjectVar_SetValue_Inner((dm_ObjectVar*)varValue, 0, sub_hobj, sub_hdesc);

            if (dmVar_BindObjectValue(varValue, 0, strt_hobj, i + 1) < 0)            
            {
                ObjectVar_SetValue_Inner((dm_ObjectVar*)varValue, 0, org_sub_hobj, org_sub_hdesc);

                return -1;
            }

            ObjectVar_SetValue_Inner((dm_ObjectVar*)varValue, 0, org_sub_hobj, org_sub_hdesc);
        }
        else
        {
            if (dmVar_BindObjectValue(varValue, 0, strt_hobj, i + 1) < 0)            
            {                
                return -1;
            }
        }        
    }

    return 0;
}

static
int
ExObjVar_Array_Rebind(
    dm_Connection*          connection,
    dm_Cursor*              ownCursor,
    dm_ObjectType*          objType,        
    dhobj                   arr_hobj,
    dhobjdesc               arr_hdesc
)
{
    udint4                  value_cnt = 0;    
    dm_ObjectType*          sub_ObjType = NULL;        
    dm_Var*                 varValue = NULL;     
    dhobj                   sub_hobj = NULL;
    dhobjdesc               sub_hdesc = NULL;
    dhobj                   org_sub_hobj = NULL; 
    dhobjdesc               org_sub_hdesc = NULL;
    udint4                  i;

    if (ExObjVar_GetSubAttr_IfNecc(connection, objType, 1, &sub_ObjType) < 0)
    {        
        return -1;
    }

    /** 数组可能会存在不需要初始化的情况 **/
    if (sub_ObjType->varValue == NULL)
        return 0;

    if (!PyList_Check(sub_ObjType->varValue))
    {
        PyErr_SetString(g_ProgrammingErrorException, 
            "ExObject Data is not a array");
        return -1;
    }    

    value_cnt       = PyList_Size(sub_ObjType->varValue);    

    for (i = 0; i < value_cnt; i ++)
    {        
        varValue    = (dm_Var*)PyList_GET_ITEM(sub_ObjType->varValue, i);

        if (varValue->type->pythonType == &g_ObjectVarType)
        {
            if (ExObjVar_GetSubHandle_IfNecc(connection, i + 1, sub_ObjType, arr_hobj, arr_hdesc, &sub_hobj, &sub_hdesc) < 0)
                return -1;                

            if (sub_ObjType->sql_type == DSQL_ARRAY ||
                sub_ObjType->sql_type == DSQL_SARRAY)
            {
                if (ExObjVar_Array_Rebind(connection, ownCursor, sub_ObjType, sub_hobj, sub_hdesc) < 0)
                    return -1;
            }
            else
            {
                if (ExObjVar_Struct_Rebind(connection, ownCursor, sub_ObjType, sub_hobj, sub_hdesc) < 0)
                    return -1;
            }

            org_sub_hobj    = ((dm_ObjectVar*)varValue)->data[0];
            org_sub_hdesc   = ((dm_ObjectVar*)varValue)->desc;

            ObjectVar_SetValue_Inner((dm_ObjectVar*)varValue, 0, sub_hobj, sub_hdesc);

            if (dmVar_BindObjectValue(varValue, 0, arr_hobj, i + 1) < 0)            
            {
                ObjectVar_SetValue_Inner((dm_ObjectVar*)varValue, 0, org_sub_hobj, org_sub_hdesc);

                return -1;
            }

            ObjectVar_SetValue_Inner((dm_ObjectVar*)varValue, 0, org_sub_hobj, org_sub_hdesc);
        }
        else
        {
            if (dmVar_BindObjectValue(varValue, 0, arr_hobj, i + 1) < 0)            
            {                
                return -1;
            }
        }    
    }

    return 0;
}

int
ExObjVar_Rebind_hobj(
    dm_ExternalObjectVar*   self,
    dhobjdesc               hobjdesc,
    dhobj                   hobj
)
{
    if (self->objectType->sql_type == DSQL_ARRAY ||
        self->objectType->sql_type == DSQL_SARRAY)
        return ExObjVar_Array_Rebind(self->connection, self->ownCursor, self->objectType, hobj, hobjdesc);

    return ExObjVar_Struct_Rebind(self->connection, self->ownCursor, self->objectType, hobj, hobjdesc);
}

/** 根据指定的对象句柄和描述，校验值与描述是否匹配 **/
int
ExObjVar_MatchCheck(
    dm_ExternalObjectVar*   self,
    dhobjdesc               hobjdesc,
    dhobj                   hobj,
    udint4*                 value_count
)
{        
    /** 若其中一个句柄为NULL，则认为无效 **/    
    if (hobjdesc == NULL || hobj == NULL)
    {                
        PyErr_SetString(PyExc_ValueError, 
            "specified object handle or object descriptor handle is invalid");
        return -1;
    }    

    /** rebind **/
    if (hobj != self->hobj)
    {
        if (ExObjVar_Read_Check(self) < 0)
            return -1;

        /** 执行过ExObjVar_MatchHandle，仅可能通过setvalue驱动 **/
        if (self->MatchHandle_execd != 0)
        {
            if (ExObjVar_Rebind_hobj(self, hobjdesc, hobj) < 0)
                return -1;
        }
        else
        {
            /** 解析服务器返回值获取objectvalue，变量类型一定是通过SQLType返回，再次利用SQLType获取值重新绑定.
                因小于python3的版本中二进制串和字符串无法区分 **/
            if (ExObjVar_MatchHandle_useSQLType(self, hobjdesc, hobj) < 0)
                return -1;
        }
    }
    else
    {
        /** 匹配值校验 **/    
        if (ExObjVar_MatchHandle(self, hobjdesc, hobj) < 0)
            return -1;

        self->MatchHandle_execd = 1;
    }    

    /** 重新获取值个数 **/
    if (value_count != NULL)    
        return ExObjVar_get_ValueCount(self->connection, hobj, value_count);    

    return 0;
}

int
ExObjVar_MatchCheck_Self(
    dm_ExternalObjectVar*  self
)
{
    dhobj           hobj = NULL;
    int             ret = 0;

    if (self->hobjdesc == NULL || 
        (self->refered_objVar == NULL && self->hobj == NULL))
    {                
        PyErr_SetString(PyExc_ValueError, 
            "object handle or object descriptor handle is invalid");
        return -1;
    }

    /** hobj == NULL(通过dmVar_GetValue获取的对象hobj == NULL)， 则重新申请 **/
    if (self->hobj == NULL && 
        ExternalObjectVar_Alloc_hobj(self->connection, self->hobjdesc, &hobj) < 0)
        return -1;

    if (hobj != NULL)
    {
        ret     = ExObjVar_MatchCheck(self, self->hobjdesc, hobj, &self->value_count);
        
        dpi_unbind_obj_desc(hobj);
        dpi_free_obj(hobj);

        return ret;
    }

    return ExObjVar_MatchCheck(self, self->hobjdesc, self->hobj, &self->value_count);
}

static
int
ExObjVar_get_ValueCount(
    dm_Connection*          connection,    
    dhobj                   hobj,
    udint4*                 val_count
)
{
    DPIRETURN       rt = DSQL_SUCCESS;

    rt      = dpi_get_obj_attr(hobj, 0, DSQL_ATTR_OBJ_VAL_COUNT, (dpointer)val_count, sizeof(udint4), NULL);
    if (Environment_CheckForError(connection->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "ExObjVar_get_ValueCount():dpi_get_obj_attr") < 0)
        return -1;

    return 0;
}

int
ExObjVar_InitInner(
    dm_Connection*          connection,
    dm_ExternalObjectVar*   self,
    dhobj                   hobj,
    dhdesc                  hobjdesc,
    int                     getVal_flag
)
{
    udint4                  field_cnt;
    udint4                  value_cnt;

    Py_INCREF(connection);
    self->connection    = connection;

    /** 申请临时句柄 **/
    self->ownCursor     = (dm_Cursor*) Connection_NewCursor_Inner(connection, NULL);
    if (self->ownCursor == NULL)
        return -1;

    self->objectType = ObjectType_New(connection, hobjdesc);
    if (!self->objectType)    
        return -1;        

    if (ExObjVar_get_ValueCount(connection, hobj, &value_cnt) < 0)
        return -1;

    self->value_count   = value_cnt;

    if (getVal_flag == 0)
    {                
        self->objectValue   = PyList_New(0);
        if (self->objectValue == NULL)
            return -1;

        return 0;
    }    

    field_cnt           = PyList_GET_SIZE(self->objectType->attributes);    

    /** STRUCT类型，value_cnt == field_cnt; ARRAY类型不等，但field_cnt=1 **/
    if (self->objectType->sql_type == DSQL_CLASS ||
        self->objectType->sql_type == DSQL_RECORD)
    {     
        self->objectValue   = ExObjVar_StructConvertToPython(self->objectType, hobjdesc, hobj, self->ownCursor);        
    } 
    else
    {       
        self->objectValue   = ExObjVar_ArrayConvertToPython(self->objectType, hobjdesc, hobj, self->ownCursor);        
    }

    if (self->objectValue == NULL)
        return -1;

    return 0;
}

PyObject*
ExObjVar_New_FromObjVar(
    dm_ObjectVar*   objVar,
    dhobjdesc       hobjdesc,
    dhobj           hobj
)                  
{
    dm_ExternalObjectVar*   self;    
    int                     ret = 0;
    
    self    = (dm_ExternalObjectVar*)ExternalObjectVar_New(&g_ExternalObjectVarType, NULL, NULL);
    if (self == NULL)
        return NULL;    

    ret     = ExObjVar_InitInner(objVar->connection, self, hobj, hobjdesc, 1);
    dpi_unbind_obj_desc(hobj);
    dpi_free_obj(hobj);

    if (ret < 0)
    {
        Py_CLEAR(self);
        return NULL;
    }

    /** 若在作为参数绑定，hobj已经无效，此处将self->hobj置为NULL，当作为绑定参数时再重新申请 **/
    self->hobj              = NULL;
    self->hobjdesc          = hobjdesc;    /** 生命周期为一次执行过程 **/

    Py_INCREF(objVar);
    self->refered_objVar    = objVar;      /** 增加引用，避免objvar在exObj之前释放 **/
    self->cursor_execNum    = objVar->cursor->execute_num;

    return (PyObject*)self;
}

static 
PyObject* 
ExternalObjectVar_New(
    PyTypeObject*   type, 
    PyObject*       args, 
    PyObject*       keywords
)
{
    dm_ExternalObjectVar*  self;

    self                = (dm_ExternalObjectVar*)g_ExternalObjectVarType.tp_alloc(&g_ExternalObjectVarType, 0);
    if (!self)
        return NULL;

    self->connection    = NULL;
    self->objectType    = NULL;
    self->objectValue   = NULL;
    self->hobj          = NULL;
    self->hobjdesc      = NULL;
    self->ownCursor     = NULL;
    self->value_count   = 0;
    self->refered_objVar    = NULL;
    self->MatchHandle_execd    = 0;

    return (PyObject*)self;
}

static 
int 
ExternalObjectVar_Init(
    dm_ExternalObjectVar*   self, 
    PyObject*               args, 
    PyObject*               keywords
)
{    
    PyObject*               conn_obj = NULL;
    PyObject*               name_obj = NULL;
    PyObject*               schema_obj = NULL;
    PyObject*               pkg_obj = NULL;
    dm_Connection*          connection = NULL;
    dhobjdesc               hobjdesc;
    dhobj                   hobj;    

/** 2.2开始定义 **/
#ifndef BUILD_VERSION_MIN
    static char*            keywordList[] = {"connection", "name", "schema", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, keywords, "OO|O", keywordList,
        &conn_obj, &name_obj, &schema_obj))
        return -1;
#else
    static char*            keywordList[] = {"connection", "name", "package", "schema", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, keywords, "OO|OO", keywordList,
        &conn_obj, &name_obj, &pkg_obj, &schema_obj))
        return -1;
#endif    

    /** 判断参数是否有效 **/
    if (!PyObject_IsInstance(conn_obj, (PyObject*)&g_ConnectionType))
    {
        PyErr_SetString(g_ProgrammingErrorException, 
            "position[0/connection] expecting a connection instance");
        return -1;
    }

    if (!py_String_Check(name_obj))
    {
        PyErr_SetString(g_ProgrammingErrorException, 
            "position[1/name] expecting a string object");
        return -1;
    }

    if (pkg_obj != NULL && pkg_obj != Py_None && !py_String_asString(pkg_obj))
    {
        PyErr_SetString(g_ProgrammingErrorException, 
            "position[2/package] expecting a string object");
        return -1;
    }

    if (schema_obj != NULL && schema_obj != Py_None && !py_String_asString(schema_obj))
    {
        PyErr_SetString(g_ProgrammingErrorException, 
            "position[3/schema] expecting a string object");
        return -1;
    }

    connection  = (dm_Connection*)conn_obj;

    /** 获取描述句柄 **/
    if (ExternalObjectVar_Alloc_handle(connection, name_obj, pkg_obj, schema_obj, &hobjdesc, &hobj) < 0)
        return -1;

    /** 初始化对象信息 **/
    if (ExObjVar_InitInner(connection, self, hobj, hobjdesc, 0) < 0)    
    {
        dpi_unbind_obj_desc(hobj);
        dpi_free_obj(hobj);
        
        return -1;
    } 

    /** 若获取描述信息中，schema名为空，则可能为包中类型，替换为输入参数中名称 **/
    if (self->objectType->schema == Py_None)
    {
        Py_INCREF(name_obj);

        Py_DECREF(self->objectType->name);
        self->objectType->name  = name_obj;        
    }

    self->hobj      = hobj;
    self->hobjdesc  = hobjdesc;    
    return 0;
}


//-----------------------------------------------------------------------------
// ExternalObjectVar_Free()
//   Free an external LOB variable.
//-----------------------------------------------------------------------------
static void ExternalObjectVar_Free(
    dm_ExternalObjectVar*  self     // variable to free
)
{
    /** hobj均有自己内部申请，可自行释放 **/
    if (self->hobj != NULL && self->connection != NULL && self->connection->isConnected != 0)
    {
        dpi_unbind_obj_desc(self->hobj);
        dpi_free_obj(self->hobj);       
    }    

    /** refered_objVar != NULL时，hobjdesc为从refered_objVar获取，由refered_objVar自己释放 **/
    if (self->hobjdesc != NULL && self->refered_objVar == NULL  && self->connection != NULL && self->connection->isConnected != 0)
    {
        dpi_free_obj_desc(self->hobjdesc);
    }    

    self->value_count   = 0;
    Py_XDECREF(self->refered_objVar);
    Py_CLEAR(self->ownCursor);
    Py_CLEAR(self->objectValue);
    Py_CLEAR(self->objectType);    
    Py_CLEAR(self->connection);
    Py_TYPE(self)->tp_free((PyObject*) self);
}

//-----------------------------------------------------------------------------
// ExternalObjectVar_GetAttributeValue()
//   Retrieve an attribute on the external LOB variable object.
//-----------------------------------------------------------------------------
PyObject*
ExObjVar_NormalConvertToPython(
    dhobj                   hobj,
    dm_Cursor*              ownCursor,
    dm_ObjectType*          ObjType,
    udint4                  val_nth // 1-based
)
{
    dm_VarType*             valType;
    dm_Var*                 valObj;
    DPIRETURN               rt = DSQL_SUCCESS;  
    PyObject*               retObj;
    slength                 data_len;
    udint4                  offset = 0;

    valType     = dmVar_TypeBySQLType(ObjType->sql_type, 1);
    if (valType == NULL)
        return NULL;

    if (valType->pythonType == &g_LongBinaryVarType ||
        valType->pythonType == &g_LongStringVarType)
    {
        rt      = dpi_get_obj_val(hobj, val_nth, valType->cType, NULL, 0, &data_len);
        if (Environment_CheckForError(ObjType->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
            "ExObjVar_NormalConvertToPython():dpi_get_obj_val for LONG BINARY or LONG CHAR") < 0)
        {            
            return NULL;
        }    

        offset  += sizeof(udint4);
    }
    else
    {
        data_len        = ObjType->prec;
    }

    valObj      = dmVar_NewByVarType(ownCursor, valType, 1, data_len);
    if (valObj == NULL)
        return NULL;       

    rt          = dpi_get_obj_val(hobj, val_nth, valType->cType, (dpointer)((sdbyte*)valObj->data + offset), valObj->bufferSize, &valObj->indicator[0]);
    if (Environment_CheckForError(ObjType->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "ExObjVar_NormalConvertToPython():dpi_get_obj_val") < 0)
    {
        Py_CLEAR(valObj);
        return NULL;
    }

    /** 更新前4个字节的长度记录 **/
    if (offset > 0)
    {
        *((udint4 *) valObj->data) = valObj->indicator[0];
    }

    valObj->actualLength[0] = valObj->indicator[0];
    
    retObj  = dmVar_GetValue(valObj, 0);
    Py_CLEAR(valObj);

    return retObj;
}

PyObject*
ExObjVar_GetAttrValue_NormalOFArray(    
    dhobj                   hobj,
    dm_ObjectType*          ObjType,
    dm_Cursor*              ownCursor,
    udint4                  numElements
)
{        
    PyObject*               resultVal;
    PyObject*               tmpVal;    
    udint4                  i; 

    resultVal   = PyList_New(numElements);
    if (resultVal == NULL)
    {
        PyErr_NoMemory();        
        return NULL;
    }

    for (i = 0; i < numElements; i ++)
    {
        tmpVal  = ExObjVar_NormalConvertToPython(hobj, ownCursor, ObjType, i + 1);
        if (tmpVal == NULL)
        {
            Py_CLEAR(tmpVal);
            return NULL;
        }

        PyList_SET_ITEM(resultVal, i, tmpVal);
    }    
       
    return resultVal;
}

/** 数组嵌套数组 **/
PyObject*
ExObjVar_GetAttrValue_ArrayOFArray(    
    dm_ObjectType*          attrType,        /** 成员数组描述对象 **/
    dhobjdesc               attr_hdesc,     /** 成员数组描述句柄 **/
    dm_Cursor*              ownCursor,
    udint4                  numElements,
    dhobj                   arr_hobj        /** 所属ARRAY对象的数据句柄 **/
)
{        
    PyObject*               resultVal;
    PyObject*               tmpVal;    
    udint4                  i;  
    dhobj                   sub_hobj;
    slength                 sub_val_len;
    DPIRETURN               rt = DSQL_SUCCESS;
    dm_VarType*             varType;

    varType     = dmVar_TypeBySQLType(attrType->sql_type, 1);
    if (varType == NULL)
        return NULL;

    resultVal   = PyList_New(numElements);
    if (resultVal == NULL)
    {
        PyErr_NoMemory();        
        return NULL;
    }

    for (i = 0; i < numElements; i ++)
    {
        rt      = dpi_get_obj_val(arr_hobj, i + 1, varType->cType, (dpointer)&sub_hobj, sizeof(dhobj), &sub_val_len);
        if (Environment_CheckForError(attrType->environment, arr_hobj, DSQL_HANDLE_OBJECT, rt, 
            "ExObjVar_GetAttrValue_ArrayOFArray(): dpi_get_obj_val") < 0)
        {                  
            Py_CLEAR(resultVal);
            return NULL;
        }

        if (sub_val_len == DSQL_NULL_DATA)
        {
            Py_INCREF(Py_None);
            PyList_SET_ITEM(resultVal, i, Py_None);

            continue;
        }

        tmpVal  = ExObjVar_ArrayConvertToPython(attrType, attr_hdesc, sub_hobj, ownCursor);
        if (tmpVal == NULL)
        {
            Py_CLEAR(resultVal);
            return NULL;
        }

        PyList_SET_ITEM(resultVal, i, tmpVal);
    }    
       
    return resultVal;
}

/** 数组嵌套STRUCT **/
PyObject*
ExObjVar_GetAttrValue_StructOFArray(    
    dm_ObjectType*          attrType,    /** 成员STRUCT对象描述 **/
    dhobjdesc               strt_hdesc,  /** 成员STRUCT对象描述句柄 **/
    dm_Cursor*              ownCursor,
    udint4                  numElements,
    dhobj                   arr_hobj     /** 所属数组对象数据句柄 **/
)
{        
    PyObject*               resultVal;
    PyObject*               tmpVal;    
    udint4                  i;  
    dhobj                   sub_hobj;
    slength                 sub_val_len;
    DPIRETURN               rt = DSQL_SUCCESS;
    dm_VarType*             varType;

    varType     = dmVar_TypeBySQLType(attrType->sql_type, 1);
    if (varType == NULL)
        return NULL;

    resultVal   = PyList_New(numElements);
    if (resultVal == NULL)
    {
        PyErr_NoMemory();        
        return NULL;
    }

    for (i = 0; i < numElements; i ++)
    {
        rt      = dpi_get_obj_val(arr_hobj, i + 1, varType->cType, (dpointer)&sub_hobj, sizeof(dhobj), &sub_val_len);
        if (Environment_CheckForError(attrType->environment, arr_hobj, DSQL_HANDLE_OBJECT, rt, 
            "ExObjVar_GetAttrValue_StructOFArray(): dpi_get_obj_val") < 0)
        {                  
            Py_CLEAR(resultVal);
            return NULL;
        }

        if (sub_val_len == DSQL_NULL_DATA)
        {
            Py_INCREF(Py_None);
            PyList_SET_ITEM(resultVal, i, Py_None);

            continue;
        }

        tmpVal  = ExObjVar_StructConvertToPython(attrType, strt_hdesc, sub_hobj, ownCursor);
        if (tmpVal == NULL)
        {
            Py_CLEAR(resultVal);
            return NULL;
        }

        PyList_SET_ITEM(resultVal, i, tmpVal);
    }    
       
    return resultVal;
}

PyObject*
ExObjVar_ArrayConvertToPython(
    dm_ObjectType*          attrType,   /** ARRAY对象类型描述对象 **/    
    dhobjdesc               arr_hdesc,  /** ARRAY对象类型描述句柄 **/
    dhobj                   arr_hobj,   /** ARRAY对象数值句柄 **/
    dm_Cursor*              ownCursor    
)
{
    DPIRETURN               rt = DSQL_SUCCESS;
    dm_ObjectType*          sub_attrType;   /** 属性成员自身描述 **/    
    dhobjdesc               sub_hdesc = NULL;      /** 属性成员自身对应描述句柄 **/
    udint4                  val_count;
    PyObject*               res_obj;

    sub_attrType    = ((dm_ObjectAttribute*)PyList_GetItem(attrType->attributes, 0))->ObjType;
    if (sub_attrType == NULL)
        return NULL;  

    /** 获取数据个数属性 **/
    rt      = dpi_get_obj_attr(arr_hobj, 0, DSQL_ATTR_OBJ_VAL_COUNT, (dpointer)&val_count, sizeof(udint4), NULL);
    if (Environment_CheckForError(sub_attrType->environment, arr_hobj, DSQL_HANDLE_OBJECT, rt, 
        "ExObjVar_ArrayConvertToPython():dpi_get_obj_attr") < 0)
        return NULL;    

    /** 获取成员描述句柄 **/
    if (sub_attrType->sql_type == DSQL_ARRAY ||
        sub_attrType->sql_type == DSQL_SARRAY ||
        sub_attrType->sql_type == DSQL_RECORD ||
        sub_attrType->sql_type == DSQL_CLASS)
    {
        rt      = dpi_get_obj_desc_attr(arr_hdesc, 1, DSQL_ATTR_OBJ_DESC, (dpointer)&sub_hdesc, 0, NULL);
        if (Environment_CheckForError(attrType->environment, arr_hdesc, DSQL_HANDLE_OBJDESC, rt, 
            "ExObjVar_ArrayConvertToPython(): dpi_get_obj_desc_attr[DSQL_ATTR_OBJ_DESC]") < 0)
        {                  
            return NULL;
        }
    }

    /** 根据成员数据类型获取相应数组值对象，并返回 **/
    switch (sub_attrType->sql_type)
    {
    case DSQL_ARRAY:
    case DSQL_SARRAY:
        res_obj = ExObjVar_GetAttrValue_ArrayOFArray(sub_attrType, sub_hdesc, ownCursor, val_count, arr_hobj);       
        break;

    case DSQL_RECORD:
    case DSQL_CLASS:
        res_obj = ExObjVar_GetAttrValue_StructOFArray(sub_attrType, sub_hdesc, ownCursor, val_count, arr_hobj);
        break;

    default:
        res_obj = ExObjVar_GetAttrValue_NormalOFArray(arr_hobj, sub_attrType, ownCursor, val_count);
        break;
    }    
    
    return res_obj;
}

PyObject*
ExObjVar_StructConvertToPython(
    dm_ObjectType*          attrType,    /** STRUCT对象类型描述**/    
    dhobjdesc               strt_hdesc,  /** STRUCT对象类型描述句柄 **/
    dhobj                   strt_hobj,   /** STRUCT对象数据句柄 **/
    dm_Cursor*              ownCursor    
)
{
    udint4                  field_cnt;
    udint4                  i;
    PyObject*               valList;
    PyObject*               valMem;    
    DPIRETURN               rt = DSQL_SUCCESS;
    dm_ObjectType*          sub_attrType;
    dm_VarType*             sub_varType;
    dhobjdesc               sub_hdesc = NULL;
    dhobj                   sub_hobj = NULL;
    slength                 sub_val_len;

    /** STRUCT类型，其值个数与属性个数相等 **/
    field_cnt   = PyList_Size(attrType->attributes);
    valList     = PyList_New(field_cnt);
    if (valList == NULL)
    {
        PyErr_NoMemory();
        return NULL;
    }

    for (i = 0; i < field_cnt; i ++)
    {        
        sub_attrType = ((dm_ObjectAttribute*)PyList_GetItem(attrType->attributes, i))->ObjType;
        if (sub_attrType == NULL)
        {
            Py_CLEAR(valList);
            return NULL;
        }

        /** 获取成员描述句柄 **/
        if (sub_attrType->sql_type == DSQL_ARRAY ||
            sub_attrType->sql_type == DSQL_SARRAY ||
            sub_attrType->sql_type == DSQL_RECORD ||
            sub_attrType->sql_type == DSQL_CLASS)
        {
            sub_varType     = dmVar_TypeBySQLType(sub_attrType->sql_type, 1);
            if (sub_varType == NULL)
            {
                Py_CLEAR(valList);
                return NULL;
            }

            rt      = dpi_get_obj_val(strt_hobj, i + 1, sub_varType->cType, (dpointer)&sub_hobj, sizeof(dhobj), &sub_val_len);
            if (Environment_CheckForError(attrType->environment, strt_hobj, DSQL_HANDLE_OBJECT, rt, 
                "ExObjVar_StructConvertToPython(): dpi_get_obj_val") < 0)
            {        
                Py_CLEAR(valList);
                return NULL;
            }

            /** 若为NULL，则直接插入None **/
            if (sub_val_len == DSQL_NULL_DATA)
            {
                Py_INCREF(Py_None);
                PyList_SET_ITEM(valList, i, Py_None);

                continue;
            }

            rt      = dpi_get_obj_desc_attr(strt_hdesc, i + 1, DSQL_ATTR_OBJ_DESC, (dpointer)&sub_hdesc, 0, NULL);
            if (Environment_CheckForError(attrType->environment, strt_hdesc, DSQL_HANDLE_OBJDESC, rt, 
                "ExObjVar_StructConvertToPython(): dpi_get_obj_desc_attr[DSQL_ATTR_OBJ_DESC]") < 0)
            {        
                Py_CLEAR(valList);
                return NULL;
            }
        }

        switch (sub_attrType->sql_type)
        {
        case DSQL_CLASS:
        case DSQL_RECORD:
            valMem  = ExObjVar_StructConvertToPython(sub_attrType, sub_hdesc, sub_hobj, ownCursor);
            break;

        case DSQL_ARRAY:
        case DSQL_SARRAY:
            valMem  = ExObjVar_ArrayConvertToPython(sub_attrType, sub_hdesc, sub_hobj, ownCursor);
            break;

        default:
            valMem  = ExObjVar_NormalConvertToPython(strt_hobj, ownCursor, sub_attrType, i + 1);
            break;
        }

        sub_hdesc   = NULL;
                
        if (valMem == NULL)
        {
            Py_CLEAR(valList);
            return NULL;
        }

        PyList_SET_ITEM(valList, i, valMem);
    }

    return valList;
}

static 
PyObject* 
ExObjVar_GetValues(
    dm_ExternalObjectVar*  var
)
{    
    if (ExObjVar_Read_Check(var) < 0)
        return NULL;

    Py_INCREF(var->objectValue);
    return var->objectValue;
}

static 
PyObject* 
ExObjVar_SetValues(
    dm_ExternalObjectVar*   var, 
    PyObject*               args,
    PyObject*               keywords
)
{
    PyObject*       value = NULL;    
    PyObject*       new_value = NULL;
    Py_ssize_t      valut_cnt = 0;
    static char*    keywordList[] = {"value", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, keywords, "O", keywordList, &value))
        return NULL;

    if (ExObjVar_Write_Check(var) < 0)
        return NULL;

    if (!PyList_Check(value))
    {
        PyErr_SetString(PyExc_TypeError, "expecting a List of Value");
        return NULL;
    }    

    /** 若为非动态数组，给定数据个数超过目标个数，则截取目标个数的元素 **/
    valut_cnt       = PyList_GET_SIZE(value);    
    if (var->objectType->sql_type != DSQL_ARRAY &&
        valut_cnt > (Py_ssize_t)var->value_count)
    {
        new_value   = PyList_GetSlice(value, 0, var->value_count);
        if (new_value == NULL)
            return NULL;        
    }
    else
    {
        Py_INCREF(value);
        new_value   = value; 
    }

    Py_CLEAR(var->objectValue);    
    var->objectValue    = new_value;
        

    /** 校验数据是否与描述一致 **/
    if (ExObjVar_MatchCheck_Self(var) < 0)
    {
        Py_CLEAR(var->objectValue); 
        return NULL;
    }

    Py_RETURN_NONE;
}
