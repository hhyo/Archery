/******************************************************
file:
    vBfile.c
purpose:
    python type define for DM BFILE variables in dmPython.just be used to col description
interface:
    {}
history:
    Date        Who         RefDoc      Memo
    2017-8-17   Caichichi               Created
*******************************************************/

#include "Buffer.h"
#include "Error.h"
#include "var_pub.h"

static int vBfile_Initialize(dm_BFileVar* var,dm_Cursor* cursor);  
static void vBfile_Finalize(dm_BFileVar* var);
static int vBFile_PreDefine(
    dm_BFileVar*    var,            // variable to set up    
    dhdesc          hdesc_col,
    sdint2          pos              // position in define list，1-based
);

static 
int 
vBfile_SetValue(
    dm_BFileVar*        var,    // variable to set value for
    unsigned            pos,    // array position to set
    PyObject*           value   // value to set
);

static 
PyObject*
vBfile_GetValue(
    dm_BFileVar*        var,        // variable to determine value for
    unsigned            pos         // array position
);

static 
int 
vBfile_BindObjectValue(
    dm_BFileVar*        var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
);

static
int 
BFileVar_Verify(
    dm_BFileVar*     var  // variable to verify
);

//-----------------------------------------------------------------------------
// Python type for BFILE declarations
//-----------------------------------------------------------------------------
PyTypeObject g_BFileVarType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.BFILE",                   // tp_name
    sizeof(dm_BFileVar),                // tp_basicsize
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

dm_VarType vt_BFILE = {
    (InitializeProc) vBfile_Initialize,
    (FinalizeProc) vBfile_Finalize,
    (PreDefineProc) vBFile_PreDefine,
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) vBfile_SetValue,
    (GetValueProc) vBfile_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)vBfile_BindObjectValue,
    &g_BFileVarType,                    // Python type
    DSQL_C_BFILE,                       // cType    
    sizeof(dhbfile),                    // element length
    0,                                  // is character data
    0,                                  // is variable length
    0,                                  // can be copied
    0         
};

static
int
vBfile_Initialize(
    dm_BFileVar*  var,
    dm_Cursor*    cursor
)
{
    udint4          i;

    // initialize members
    Py_INCREF(cursor->connection);
    var->connection = cursor->connection;    

    // initialize the BFILE locators
    for (i = 0; i < var->allocatedElements; i++) 
    {
        ((dhbfile*)var->data)[i]    = NULL;
    }

    return 0;
}

static
void
vBfile_Finalize(
    dm_BFileVar* var
)
{
    Py_CLEAR(var->connection);
    //Py_CLEAR(var);
}

//-----------------------------------------------------------------------------
// vBFile_PreDefine()
//   Performs additional steps required for defining objects.
//-----------------------------------------------------------------------------
static int vBFile_PreDefine(
    dm_BFileVar*    var,            // variable to set up    
    dhdesc          hdesc_col,
    sdint2          pos              // position in define list，1-based
)
{
    DPIRETURN       rt;
    udint4          i;

    // initialize the LOB locators
    for (i = 0; i < var->allocatedElements; i++) 
    {
        rt      = dpi_alloc_bfile(var->connection->hcon, &(((dhbfile*)var->data)[i]));
        if (Environment_CheckForError(var->environment, var->connection->hcon, DSQL_HANDLE_DBC, rt,
            "vBFile_PreDefine():dpi_alloc_bfile") < 0)
        {
            return -1;
        }
    }

    return 0;
}

void
get_bfile_info(
    char*           bfile_path,
    unsigned int    bfile_len,
    char*           dir_name,
    char*           file_name,
    unsigned int*   bfile_id
)
{
    char*           start;
    char*           end;
    char*           ptr;
    unsigned int    search_len;
    unsigned int    len;
    unsigned int    id = 0;

    assert(dir_name != NULL && file_name != NULL && bfile_id != NULL);

    *dir_name = END;
    *file_name = END;
    *bfile_id = 0;

    start = bfile_path;
    end = bfile_path + bfile_len;
    search_len = bfile_len;

    //dir
    ptr = memchr(start, ':', search_len);
    assert(ptr != NULL);
    if (ptr == NULL)
        return;

    len = (unsigned int)(ptr - start);
    assert(len <= NAMELEN);
    if (len > NAMELEN)
        return;

    memcpy(dir_name, start, len);
    dir_name[len] = END;

    //filename
    start = ptr + 1;
    search_len -= (len + 1);
    ptr = memchr(start, ':', search_len);
    if (ptr == NULL)
    {
        len = (unsigned int)(end - start);
        assert(len <= MAX_PATH_LEN);
        if (len > MAX_PATH_LEN)
            return;

        memcpy(file_name, start, len);
        file_name[len] = END;

        return;
    }

    len = (unsigned int)(ptr - start);
    assert(len <= MAX_PATH_LEN);
    if (len > MAX_PATH_LEN)
        return;

    memcpy(file_name, start, len);
    file_name[len] = END;

    //bfile_id
    ptr++;
    len = (unsigned int)(end - ptr);
    assert(len == BFILE_ID_LEN);
    if (len != BFILE_ID_LEN)
        return;

    while (ptr != end)
    {
        if (*ptr != SPACE)
        {
            assert(*ptr >= '0' && *ptr <= '9');
            if (*ptr < '0' || *ptr > '9')
                return;

            id = id * 10 + (*ptr - '0');
        }

        ptr++;
    }

    *bfile_id = id;
}

//-----------------------------------------------------------------------------
// vBfile_SetValue()
//   Set the value of the variable.
//-----------------------------------------------------------------------------
static 
int 
vBfile_SetValue(
    dm_BFileVar*        var,    // variable to set value for
    unsigned            pos,    // array position to set
    PyObject*           value   // value to set
)                    
{

    dm_ExternalBFile*   exbfile;
    dm_BFileVar*        src_bfile;
    dhstmt              stmt = NULL;

    if (!PyObject_IsInstance(value, (PyObject*) &g_exBFileVarType)) 
    {
        PyErr_SetString(PyExc_TypeError, "expecting a exBFile Object");
        return -1;
    }   

    exbfile                 = (dm_ExternalBFile*)value;
    src_bfile               = exbfile->BFileVar;
     
    if (BFileVar_Verify(src_bfile) < 0)
    {
        return -1;
    }
    
    ((dhbfile*)var->data)[pos]          = ((dhbfile*)src_bfile->data)[pos];               
    var->bufferSize         = sizeof(dhbfile);
    var->type->cType        = DSQL_C_BFILE;
    var->indicator[pos]     = sizeof(dhbfile);
    var->actualLength[pos]  = sizeof(dhbfile);

    return 0;
}

//-----------------------------------------------------------------------------
// vBfile_GetValue()
//   Returns the value stored at the given array position.
//-----------------------------------------------------------------------------
static 
PyObject*
vBfile_GetValue(
    dm_BFileVar*    var,        // variable to determine value for
    unsigned        pos         // array position
)                  
{
    return exBFileVar_NEW(var, pos);
}

static 
int 
vBfile_BindObjectValue(
    dm_BFileVar*        var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
)
{
    DPIRETURN       rt;

    rt      = dpi_set_obj_val(hobj, val_nth, DSQL_C_BFILE, ((dhbfile*)var->data)[pos], sizeof(dhbfile));
    if (Environment_CheckForError(var->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "vBfile_BindObjectValue():dpi_set_obj_val") < 0)
    {
        return -1;
    }

    return 0;
}

//-----------------------------------------------------------------------------
// BFileVar_Verify()
//   Verify that the BFILE var is still valid.
//-----------------------------------------------------------------------------
static
int 
BFileVar_Verify(
    dm_BFileVar*     var  // variable to verify
)
{
    dm_Var*       dm_var = (dm_Var*)var;
    /** 连接断开，bfile句柄无效；cursor关闭，bfile句柄操作可能会报错，此处增加校验 **/
    if (dm_var->connection->isConnected <= 0)
    {
        PyErr_SetString(PyExc_ValueError, 
            "The related cursor or connection is closed");
        return -1;
    }

    return 0;
}

