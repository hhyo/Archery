/******************************************************
file:
    tObject.c
purpose:
    python type define for DM OBJECT TYPE in dmPython,just used for description.
interface:
    {}
history:
    Date        Who         RefDoc      Memo
    2015-6-11   shenning                Created
*******************************************************/
#include "var_pub.h"
#include "Error.h"
#include "py_Dameng.h"
#include "Buffer.h"

//-----------------------------------------------------------------------------
// Declaration of type variable functions.
//-----------------------------------------------------------------------------
static void ObjectType_Free(dm_ObjectType*);
static PyObject *ObjectType_Repr(dm_ObjectType*);
static dm_ObjectAttribute *ObjectAttribute_New(dm_Connection*, dhobjdesc, udint4);
static void ObjectAttribute_Free(dm_ObjectAttribute*);
static PyObject *ObjectAttribute_Repr(dm_ObjectAttribute*);


//-----------------------------------------------------------------------------
// declaration of members for Python type "ObjectType"
//-----------------------------------------------------------------------------
static PyMemberDef g_ObjectTypeMembers[] = {
    { "schema",     T_OBJECT, offsetof(dm_ObjectType, schema),     READONLY },
    { "name",       T_OBJECT, offsetof(dm_ObjectType, name),       READONLY },
    { "attributes", T_OBJECT, offsetof(dm_ObjectType, attributes), READONLY },
    { NULL }
};


//-----------------------------------------------------------------------------
// declaration of members for Python type "ObjectAttribute"
//-----------------------------------------------------------------------------
static PyMemberDef g_ObjectAttributeMembers[] = {
    { "type",       T_OBJECT, offsetof(dm_ObjectAttribute, ObjType),    READONLY },    
    { NULL }
};


//-----------------------------------------------------------------------------
// Python type declarations
//-----------------------------------------------------------------------------
PyTypeObject g_ObjectTypeType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.ObjectType",              // tp_name
    sizeof(dm_ObjectType),              // tp_basicsize
    0,                                  // tp_itemsize
    (destructor) ObjectType_Free,       // tp_dealloc
    0,                                  // tp_print
    0,                                  // tp_getattr
    0,                                  // tp_setattr
    0,                                  // tp_compare
    (reprfunc) ObjectType_Repr,         // tp_repr
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
    g_ObjectTypeMembers,                // tp_members
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


PyTypeObject g_ObjectAttributeType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.ObjectAttribute",         // tp_name
    sizeof(dm_ObjectAttribute),         // tp_basicsize
    0,                                  // tp_itemsize
    (destructor) ObjectAttribute_Free,  // tp_dealloc
    0,                                  // tp_print
    0,                                  // tp_getattr
    0,                                  // tp_setattr
    0,                                  // tp_compare
    (reprfunc) ObjectAttribute_Repr,    // tp_repr
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
    g_ObjectAttributeMembers,           // tp_members
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
// ObjectType_Describe()
//   Describe the type and store information about it as needed.
//-----------------------------------------------------------------------------
static 
int 
ObjectType_Describe(
    dm_ObjectType*     self,            // type to populate
    dm_Connection*      connection,     // connection for type information    
    dhobjdesc           descHandle,     // handle to object description    
    udint4              pos,            // pos to describe
    udint4*             field_count     // out of filed count
)           
{
    DPIRETURN           rt = DSQL_SUCCESS;    
    sdbyte              schname[128 + 1];
    sdbyte              name[128 + 1]; 
    slength             val_len;    

    memset(schname, 0, sizeof(schname));
    memset(name, 0, sizeof(name));    

    rt      = dpi_get_obj_desc_attr(descHandle, pos, DSQL_ATTR_OBJ_TYPE, (dpointer)&self->sql_type, 0, &val_len);    
    if (Environment_CheckForError(self->environment, descHandle, DSQL_HANDLE_OBJDESC, rt, 
        "ObjectType_Describe(): dpi_get_obj_desc_attr[DSQL_ATTR_OBJ_TYPE]") < 0)
        return -1;

    rt      = dpi_get_obj_desc_attr(descHandle, pos, DSQL_ATTR_OBJ_PREC, (dpointer)&self->prec, 0, &val_len);
    if (Environment_CheckForError(self->environment, descHandle, DSQL_HANDLE_OBJDESC, rt, 
        "ObjectType_Describe(): dpi_get_obj_desc_attr[DSQL_ATTR_OBJ_PREC]") < 0)
        return -1;

    rt      = dpi_get_obj_desc_attr(descHandle, pos, DSQL_ATTR_OBJ_SCALE, (dpointer)&self->scale, 0, &val_len);
    if (Environment_CheckForError(self->environment, descHandle, DSQL_HANDLE_OBJDESC, rt, 
        "ObjectType_Describe(): dpi_get_obj_desc_attr[DSQL_ATTR_OBJ_SCALE]") < 0)
        return -1;

    rt      = dpi_get_obj_desc_attr(descHandle, pos, DSQL_ATTR_OBJ_FIELD_COUNT, (dpointer)field_count, 0, &val_len);
    if (Environment_CheckForError(self->environment, descHandle, DSQL_HANDLE_OBJDESC, rt, 
        "ObjectType_Describe(): dpi_get_obj_desc_attr[DSQL_ATTR_OBJ_FIELD_COUNT]") < 0)
        return -1;

    if (self->sql_type == DSQL_CLASS ||
        self->sql_type == DSQL_RECORD ||
        self->sql_type == DSQL_ARRAY ||
        self->sql_type == DSQL_SARRAY)
    {
        rt      = dpi_get_obj_desc_attr(descHandle, pos, DSQL_ATTR_OBJ_NAME, (dpointer)name, sizeof(name), &val_len);
        if (Environment_CheckForError(self->environment, descHandle, DSQL_HANDLE_OBJDESC, rt, 
            "ObjectType_Describe(): dpi_get_obj_desc_attr[DSQL_ATTR_OBJ_NAME]") < 0)
            return -1;

        rt      = dpi_get_obj_desc_attr(descHandle, pos, DSQL_ATTR_OBJ_SCHAME, (dpointer)schname, sizeof(schname), &val_len);
        if (Environment_CheckForError(self->environment, descHandle, DSQL_HANDLE_OBJDESC, rt, 
            "ObjectType_Describe(): dpi_get_obj_desc_attr[DSQL_ATTR_OBJ_SCHAME]") < 0)
            return -1;
    }    

    if (strlen(name) > 0)    
    {
        self->name  = dmString_FromEncodedString(name, strlen(name), self->environment->encoding);
    }
    else
    {
        Py_INCREF(Py_None);
        self->name  = Py_None;
    }

    if (strlen(schname) > 0)
    {
        self->schema    = dmString_FromEncodedString(schname, strlen(schname), self->environment->encoding);
    }
    else
    {
        Py_INCREF(Py_None);
        self->schema    = Py_None;
    }

    return 0;
}

static 
dm_ObjectType*
ObjectType_alloc(
    dm_Connection* connection         // connection for type information    
)
{
    dm_ObjectType *self;

    self = (dm_ObjectType*) g_ObjectTypeType.tp_alloc(&g_ObjectTypeType, 0);
    if (!self)
        return NULL;

    //Py_INCREF(connection->environment);
    Py_INCREF(connection);
    self->connection    = connection;
    self->environment   = connection->environment;    
    self->schema        = NULL;
    self->name          = NULL;
    self->attributes    = NULL;
    self->varValue      = NULL;

    return self;
}


//-----------------------------------------------------------------------------
// ObjectType_Initialize()
//   Initialize the object type with the information that is required.
//-----------------------------------------------------------------------------
static 
int 
ObjectType_Initialize(
    dm_ObjectType*  self,               // type to initialize
    dm_Connection*  connection,         // connection for type information    
    dhobjdesc       descHandle,      // handle to object description
    udint4          filed_count
)
{
    udint4                  pos = 0;        // 0 for self; other for attributes            
    dm_ObjectAttribute*     sub_attr;        

    /** 定义类型中属性为一LIST **/
    self->attributes   = PyList_New(filed_count);
    if (self->attributes == NULL)
    {
        PyErr_NoMemory();
        return -1;
    }
    
    /** 按顺序初始化各属性信息，并将其放入到属性LIST中 **/
    for (pos = 0; pos < filed_count; pos ++)
    {
        sub_attr    = ObjectAttribute_New(connection, descHandle, pos + 1);         
        if (sub_attr == NULL)
        {
            return -1;
        }

        PyList_SET_ITEM(self->attributes, pos, (PyObject*)sub_attr);
    }       

    return 0;
}


//-----------------------------------------------------------------------------
// ObjectType_New()
//   Allocate a new object type.
//-----------------------------------------------------------------------------
dm_ObjectType*
ObjectType_New(
    dm_Connection*  connection,         // connection for type information    
    dhobjdesc       descHandle      // handle to object description
)
{
    dm_ObjectType*  self;
    udint4          field_cnt;


    self        = ObjectType_alloc(connection);
    if (self == NULL)
        return NULL;

    // get top level parameter descriptor
    if (ObjectType_Describe(self, connection, descHandle, 0, &field_cnt) < 0)
    {
        Py_DECREF(self);

        return NULL;
    }    

    if (ObjectType_Initialize(self, connection, descHandle, field_cnt) < 0) 
    {
        Py_DECREF(self);
        return NULL;
    }

    return self;
}


//-----------------------------------------------------------------------------
// ObjectType_NewByName()
//   Create a new object type given its name.
//-----------------------------------------------------------------------------
static 
dm_ObjectType*
ObjectType_NewByName(
    dm_Connection*  connection,   // connection for type information
    PyObject*       name,         // name of object type to describe
    PyObject*       schname       // schename name of object type to describe
)                                       
{
    dhobjdesc       hobjdesc;
    dhobj           hobj;
    dm_ObjectType*  result;
    dm_Buffer       buffer_name;
    dm_Buffer       buffer_schname;
    sdbyte*         p_name = NULL;
    sdbyte*         p_schname = NULL;
    DPIRETURN       rt = DSQL_SUCCESS;
    
    if (dmBuffer_FromObject(&buffer_name, name, connection->environment->encoding) < 0)
    {
        return NULL;
    }
    p_name          = (sdbyte*)buffer_name.ptr;

    if (schname != NULL && schname != Py_None)
    {
        if (dmBuffer_FromObject(&buffer_schname, schname, connection->environment->encoding) < 0)
            return NULL;

        p_schname   = (sdbyte*)buffer_schname.ptr;
    }

    // allocate describe handle
    rt              = dpi_desc_obj(connection->hcon, p_schname, p_name, &hobjdesc);
    dmBuffer_Clear(&buffer_name);
    if (schname != NULL && schname != Py_None)
        dmBuffer_Clear(&buffer_schname);

    if (Environment_CheckForError(connection->environment, connection->hcon, DSQL_HANDLE_DBC, rt,
        "ObjectType_NewByName(): dpi_desc_obj") < 0)
        return NULL;

    // allocate obj handle
    rt              = dpi_alloc_obj(connection->hcon, &hobj);
    if (Environment_CheckForError(connection->environment, connection->hcon, DSQL_HANDLE_DBC, rt,
        "ObjectType_NewByName(): dpi_alloc_obj") < 0)
    {
        dpi_free_obj_desc(hobjdesc);

        return NULL;
    }

    // bind obj handle with desc handle
    rt              = dpi_bind_obj_desc(hobj, hobjdesc);
    if (Environment_CheckForError(connection->environment, hobj, DSQL_HANDLE_OBJECT, rt,
        "ObjectType_NewByName(): dpi_bind_obj_desc") < 0)
    {
        dpi_free_obj_desc(hobjdesc);
        dpi_free_obj(hobj);

        return NULL;
    }

    // get object type
    result = ObjectType_New(connection, hobjdesc);
    if (!result) 
    {
        dpi_free_obj_desc(hobjdesc);
        dpi_free_obj(hobj);

        return NULL;
    }

    return result;
}


//-----------------------------------------------------------------------------
// ObjectType_Free()
//   Free the memory associated with an object type.
//-----------------------------------------------------------------------------
static 
void ObjectType_Free(
    dm_ObjectType*     self    // object type to free
)   
{    
    //Py_CLEAR(self->environment);
    Py_CLEAR(self->connection);
    Py_CLEAR(self->schema);
    Py_CLEAR(self->name);
    Py_CLEAR(self->varValue);
    Py_CLEAR(self->attributes);    
    Py_TYPE(self)->tp_free((PyObject*) self);
}


//-----------------------------------------------------------------------------
// ObjectType_Repr()
//   Return a string representation of the object type.
//-----------------------------------------------------------------------------
static
PyObject*
ObjectType_Repr(
    dm_ObjectType* self    // object type to return the string for
)
{
    PyObject*   module;
    PyObject*   name;
    PyObject*   result;
    PyObject*   format;
    PyObject*   formatArgs;
    dm_VarType*   varType;

    if (GetModuleAndName(Py_TYPE(self), &module, &name) < 0)
        return NULL;

    /** 若是普通类型，则直接获取普通数据类型 **/
    if (self->sql_type != DSQL_ARRAY &&
        self->sql_type != DSQL_SARRAY &&
        self->sql_type != DSQL_CLASS &&
        self->sql_type != DSQL_RECORD)
    {
        varType = dmVar_TypeBySQLType(self->sql_type, 1);
        if (varType == NULL)
            return NULL;

        format = dmString_FromAscii("<%s.%s %s>");
        if (!format) 
        {
            Py_DECREF(module);
            Py_DECREF(name);
            return NULL;
        }

        formatArgs = PyTuple_Pack(3, module, name, varType->pythonType);
        Py_DECREF(module);
        Py_DECREF(name);
        if (!formatArgs) 
        {
            Py_DECREF(format);
            return NULL;
        }        
    }
    else
    {
        format = dmString_FromAscii("<%s.%s %s.%s>");
        if (!format) 
        {
            Py_DECREF(module);
            Py_DECREF(name);
            return NULL;
        }

        formatArgs = PyTuple_Pack(4, module, name, self->schema, self->name);
        Py_DECREF(module);
        Py_DECREF(name);
        if (!formatArgs) 
        {
            Py_DECREF(format);
            return NULL;
        }
    }    

    result = py_String_Format(format, formatArgs);
    Py_DECREF(format);
    Py_DECREF(formatArgs);
    return result;
}

int
ObjectType_IsObjectType(
    dm_ObjectType* self    // object type to return the string for
)
{
    if (self->sql_type == DSQL_ARRAY ||
        self->sql_type == DSQL_SARRAY ||
        self->sql_type == DSQL_RECORD ||
        self->sql_type == DSQL_CLASS)
        return 1;

    return 0;
}


//-----------------------------------------------------------------------------
// ObjectAttribute_Initialize()
//   Initialize the new object attribute.
//-----------------------------------------------------------------------------
static 
int 
ObjectAttribute_Initialize(
    dm_ObjectAttribute*     self,          // object attribute to initialize
    dm_Connection*          connection,    // connection in use        
    dhobjdesc               strt_hdesc,     // 对应所属对象的描述句柄
    udint4                  attr_nth       // 对应当前属性对象在所属对象中序号1-based 
)
{
    udint4                  field_cnt;
    dm_ObjectType*          objType = NULL;
    DPIRETURN               rt = DSQL_SUCCESS;
    dhobjdesc               sub_desc;    
    
    objType     = ObjectType_alloc(connection);
    if (objType == NULL)
        return -1;       

    /** 获取当前属性基本描述信息 **/
    if (ObjectType_Describe(objType, connection, strt_hdesc, attr_nth, &field_cnt) < 0)
    {
        Py_DECREF(objType);
        return -1;
    }

    /** 若当前属性为复合类型，则获取其自身描述句柄，供获取属性本身成员属性使用 **/
    if (objType->sql_type == DSQL_CLASS || objType->sql_type == DSQL_RECORD ||
        objType->sql_type == DSQL_ARRAY || objType->sql_type == DSQL_SARRAY)
    {
        rt      = dpi_get_obj_desc_attr(strt_hdesc, attr_nth, DSQL_ATTR_OBJ_DESC, (dpointer)&sub_desc, 0, NULL);
        if (Environment_CheckForError(objType->environment, strt_hdesc, DSQL_HANDLE_OBJDESC, rt, 
            "ObjectType_Initialize(): dpi_get_obj_desc_attr[DSQL_ATTR_OBJ_DESC]") < 0)
        {            
            return -1;
        }

        /** 初始化属性本身成员描述，sub_desc释放由其父亲执行free_obj_desc时释放，此处不需要主动释放 **/
        if (ObjectType_Initialize(objType, connection, sub_desc, field_cnt) < 0)
        {                        
            Py_DECREF(objType);
            return -1;
        }        
    }

    /** DM并未给出属性名称，此处使用类型名称 **/
    Py_INCREF(objType->name);
    self->name      = objType->name;

    Py_INCREF(objType->schema);
    self->schema    = objType->schema;

    self->ObjType   = objType;

    return 0;
}


//-----------------------------------------------------------------------------
// ObjectAttribute_New()
//   Allocate a new object attribute.
//-----------------------------------------------------------------------------
static 
dm_ObjectAttribute*
ObjectAttribute_New(
    dm_Connection*  connection,         // connection information    
    dhobjdesc       descHandle,         // objdeschandle used to get desc info of this attribute
    udint4          nth                 // parameter sequence, 1-based
)
{
    dm_ObjectAttribute *self;

    self = (dm_ObjectAttribute*)
        g_ObjectAttributeType.tp_alloc(&g_ObjectAttributeType, 0);
    if (!self)
        return NULL;

    Py_INCREF(connection);
    self->connection    = connection;
    self->name          = NULL;
    self->ObjType       = NULL;
    self->schema        = NULL;

    if (ObjectAttribute_Initialize(self, connection, descHandle, nth) < 0) 
    {
        Py_DECREF(self);
        return NULL;
    }

    return self;
}


//-----------------------------------------------------------------------------
// ObjectAttribute_Free()
//   Free the memory associated with an object attribute.
//-----------------------------------------------------------------------------
static 
void 
ObjectAttribute_Free(
    dm_ObjectAttribute *self // object attribute to free
)          
{
    Py_CLEAR(self->connection);
    Py_CLEAR(self->name);
    Py_CLEAR(self->ObjType);
    Py_TYPE(self)->tp_free((PyObject*) self);
}


//-----------------------------------------------------------------------------
// ObjectAttribute_Repr()
//   Return a string representation of the object attribute.
//-----------------------------------------------------------------------------
static 
PyObject*
ObjectAttribute_Repr(
    dm_ObjectAttribute *self   // attribute to return the string for
)          
{
    PyObject*   module;
    PyObject*   name;
    PyObject*   result;
    PyObject*   format = NULL;
    PyObject*   formatArgs = NULL;
    dm_VarType*   objType;

    if (GetModuleAndName(Py_TYPE(self), &module, &name) < 0)
        return NULL;

    switch (self->ObjType->sql_type)
    {
    case DSQL_CLASS:
        format          = dmString_FromAscii("<%s.%s %s.%s>");
        if (format != NULL)
            formatArgs  = PyTuple_Pack(4, module, name, self->schema, self->name);
        break;

    case DSQL_ARRAY:
    case DSQL_SARRAY:
    case DSQL_RECORD:
        format          = dmString_FromAscii("<%s.%s %s>");
        if (format != NULL)
            formatArgs  = PyTuple_Pack(3, module, name, self->name);
        break;

    default:
        objType         = dmVar_TypeBySQLType(self->ObjType->sql_type, 1);
        if (objType != NULL)
        {
            format      = dmString_FromAscii("<%s.%s %s>");
            if (format != NULL)
                formatArgs  = PyTuple_Pack(3, module, name, objType->pythonType);
        }        
        break;
    }

    Py_DECREF(module);
    Py_DECREF(name);

    if (format == NULL) 
    {        
        return NULL;
    }
    
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


