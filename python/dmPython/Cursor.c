//-----------------------------------------------------------------------------
// Cursor.c
//   Definition of the Python type Cursor.
//-----------------------------------------------------------------------------
#include "py_Dameng.h"
#include "row.h"
#include "Error.h"
#include "Buffer.h"
#include "var_pub.h"
#include "stdio.h"
#include "trc.h"

#include <datetime.h>

static 
PyObject*
Cursor_GetDescription(
    dm_Cursor   *self,
    void*       args
);

PyObject*
Cursor_Execute_inner(
    dm_Cursor*      self, 
    PyObject*       statement,
    PyObject*       executeArgs,
    int             is_many,
    int             exec_direct,
    int             from_call
);

static
sdint2
Cursor_GetParamDescFromDm(
    dm_Cursor*     self
);

PyObject*
Cursor_MakeupProcParams(
	dm_Cursor*     self
);

static
void
Cursor_ExecRs_Clear(
    dm_Cursor*     self    // cursor to set the rowcount on
);

static 
sdint2
Cursor_SetRowCount(
    dm_Cursor*     self    // cursor to set the rowcount on
);

/************************************************************************
purpose:
    设置语句执行id
************************************************************************/
static 
sdint2
Cursor_SetExecId(
    dm_Cursor*     self    /*IN: cursor to set the rowcount on*/
);

void
Cursor_Data_init()
{
	PyDateTime_IMPORT;
}

static 
void
Cursor_init_inner(
    dm_Cursor*     self
)
{
    Py_INCREF(Py_None);
    self->statement     = Py_None;

    Py_INCREF(Py_None);
    self->environment   = (dm_Environment*)Py_None;

    Py_INCREF(Py_None);
    self->connection    = (dm_Connection*)Py_None;

    Py_INCREF(Py_None);
    self->rowFactory    = Py_None;

    Py_INCREF(Py_None);
    self->inputTypeHandler  = Py_None;

    Py_INCREF(Py_None);
    self->outputTypeHandler = Py_None;

    Py_INCREF(Py_None);
    self->description       = Py_None;

    Py_INCREF(Py_None);
    self->map_name_to_index = Py_None;

    Py_INCREF(Py_None);
    self->column_names      = Py_None;

    Py_INCREF(Py_None);
    self->lastrowid_obj     = Py_None;

    Py_INCREF(Py_None);
    self->execid_obj        = Py_None;

    self->rowNum            = 0;
    self->with_rows         = 0;
    self->rowCount          = -1;

    self->col_variables     = NULL;
    self->param_variables   = NULL;
    self->execute_num       = 0;
}

static 
sdint2
Cursor_IsOpen_without_err(
    dm_Cursor*     self
)
{
    if (self->isOpen <= 0)
    {
        return -1;
    }

    return 0;
}

static 
sdint2
Cursor_IsOpen(
    dm_Cursor*     self
)
{
	if (Cursor_IsOpen_without_err(self) < 0){
		PyErr_SetString(g_InternalErrorException, "Not Open");
		return -1;
	}

	return 0;
}

sdint2
Cursor_AllocHandle(
    dm_Cursor*     self
)
{
    DPIRETURN		rt = DSQL_SUCCESS;
    dhstmt			hstmt;	

    Py_BEGIN_ALLOW_THREADS
        rt = dpi_alloc_stmt(self->connection->hcon, &hstmt);	
        rt = dpi_set_stmt_attr(hstmt, DSQL_ATTR_CURSOR_TYPE, (dpointer)DSQL_CURSOR_STATIC, 0);
    Py_END_ALLOW_THREADS
        if (Environment_CheckForError(self->environment, self->connection->hcon, DSQL_HANDLE_DBC, rt, "Cursor_Init():dpi_alloc_stmt") < 0)
            return -1;	

    self->handle    = hstmt;
    return 0;
}

/************************************************************************/
/* purpose:
    set default schema
/************************************************************************/
sdint2  /* 返回错误码 */
Cursor_SetSchema(
    dm_Cursor*     self        /* IN:cursor对象 */
)
{
    DPIRETURN		rt = DSQL_SUCCESS;
    dhstmt			hstmt = self->handle;
    dm_Buffer       sch_buf;
    sdbyte          sql[128];

    //if schema does not set, then return
    if (self->connection->schema == Py_None)
    {
        return 0;
    }

    //get schema from connection obj
    if (dmBuffer_FromObject(&sch_buf, self->connection->schema, self->environment->encoding) < 0)
    {
        PyErr_SetString(PyExc_TypeError, "expecting a None or string schema arguement");
        return -1;
    }

    //set schema
    sprintf(sql, "set schema %s;", (sdbyte*)sch_buf.ptr);

    Py_BEGIN_ALLOW_THREADS
        rt  = dpi_exec_direct(self->handle, sql);
    Py_END_ALLOW_THREADS

    dmBuffer_Clear(&sch_buf);

    if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, rt,
        "Cursor_InternalPrepare(): prepare") < 0) 
    {
        return -1;
    }

    return 0;
}

PyObject*
Cursor_New(    
    dm_Connection*     connection
)
{
    dm_Cursor*         self;
    
    self                = (dm_Cursor*)g_CursorType.tp_alloc(&g_CursorType, 0);
    if (self == NULL)
        return NULL;    

    Cursor_init_inner(self);

    Py_INCREF(connection);
    self->connection    = connection;

    Py_INCREF(connection->environment);
    self->environment   = connection->environment;

    // 申请语句句柄	
    if (Cursor_AllocHandle(self) < 0)
    {
        Cursor_free_inner(self);
        Py_TYPE(self)->tp_free((PyObject*) self);

        return NULL;
    }

    //设置模式
    if (Cursor_SetSchema(self))
    {
        Cursor_free_inner(self);
        Py_TYPE(self)->tp_free((PyObject*) self);

        return NULL;
    }
    
    self->execute_num   = 0;
    self->arraySize     = 50;
    self->org_arraySize = self->arraySize;
    self->bindArraySize = 1;    
    self->org_bindArraySize = self->bindArraySize;
    self->statementType = -1;
    self->outputSize    = -1;
    self->outputSizeColumn = -1;
    self->isOpen        = 1;
    self->isClosed      = 0;

    self->bindColDesc   = NULL;
    self->bindParamDesc = NULL;
    self->paramCount    = 0;
    self->colCount      = 0;
    self->rowNum        = 0;

    //在Cursor_New中设置，避免close后取不到rowcount值
    self->totalRows     = -1;

    self->is_iter       = 0;
    self->output_stream = 0;
    self->outparam_num  = 0;
    self->param_value   = NULL;
    return (PyObject*)self;
}

static 
PyObject*
Cursor_Repr(
    dm_Cursor*     cursor
)
{
	PyObject *connectionRepr, *module, *name, *result, *format, *formatArgs;

    format = dmString_FromAscii("<%s.%s on %s>");
    if (!format)
        return NULL;

    connectionRepr = PyObject_Repr((PyObject*) cursor->connection);
    if (!connectionRepr) {
        Py_DECREF(format);
        return NULL;
    }

    if (GetModuleAndName(Py_TYPE(cursor), &module, &name) < 0) {
        Py_DECREF(format);
        Py_DECREF(connectionRepr);
        return NULL;
    }

    formatArgs = PyTuple_Pack(3, module, name, connectionRepr);
    Py_DECREF(module);
    Py_DECREF(name);
    Py_DECREF(connectionRepr);
    if (!formatArgs) {
        Py_DECREF(format);
        return NULL;
    }

    result = PyUnicode_Format(format, formatArgs);
    Py_DECREF(format);
    Py_DECREF(formatArgs);
    return result;
}


//-----------------------------------------------------------------------------
// Cursor_FreeHandle()
//   Free the handle 
//-----------------------------------------------------------------------------
sdint2 
Cursor_FreeHandle(
    dm_Cursor*      self,       // cursor object
	int             raiseException      // raise an exception, if necesary?
)
{
    DPIRETURN   rt = DSQL_SUCCESS;

	if (self->handle) 
    {
		Py_BEGIN_ALLOW_THREADS
			rt = dpi_free_handle(DSQL_HANDLE_STMT, self->handle);
		Py_END_ALLOW_THREADS
		if (raiseException && 
			Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, rt, "Cursor_FreeHandle():cursor free") < 0)
			return -1;
	}

    self->handle = NULL;
	return  0;
}

void
Cursor_free_paramdesc(
	dm_Cursor*     self
)
{	    
    self->hdesc_param   = NULL;

	if (self->bindParamDesc != NULL)
    {        
		PyMem_Free(self->bindParamDesc);
	}
    self->bindParamDesc = NULL;  

    self->paramCount    = 0;

    self->outparam_num  = 0;
}

void
Cursor_free_coldesc(
	dm_Cursor*     self
)
{	
    self->hdesc_col = NULL;

	if (self->bindColDesc != NULL)
	{		
		PyMem_Free(self->bindColDesc);
	}
	self->bindColDesc = NULL;    
}

void
Cursor_free_inner(
    dm_Cursor*     self
)
{
    Cursor_free_paramdesc(self);
    Cursor_free_coldesc(self);

    Py_CLEAR(self->statement);
    Py_DECREF(self->environment);
    Py_DECREF(self->connection);      
    Py_CLEAR(self->rowFactory);    
    Py_CLEAR(self->inputTypeHandler);    
    Py_CLEAR(self->outputTypeHandler);    
    Py_CLEAR(self->description);    
    Py_CLEAR(self->map_name_to_index);
    Py_CLEAR(self->column_names);
    Py_CLEAR(self->param_variables);
    Py_CLEAR(self->col_variables);
    Py_CLEAR(self->lastrowid_obj);
    Py_CLEAR(self->execid_obj);
}

sdint2
Cursor_InternalClose(
	dm_Cursor*     self
)
{
	Py_BEGIN_ALLOW_THREADS	
	dpi_close_cursor(self->handle);
	Py_END_ALLOW_THREADS

	return 0;
}

static 
PyObject*
Cursor_Close_inner(
    dm_Cursor*     self
)
{
    /** 若显示调用过Cursor_Close，则返回 **/
	if (Cursor_IsOpen(self) < 0)
    {
		PyErr_Clear();

        Py_RETURN_NONE;
    }

    /** 若连接未断开，则执行句柄资源释放 **/
    if (self->connection->isConnected == 1)
    {
        Cursor_InternalClose(self);

        Cursor_FreeHandle(self, 0);
    }	

    /** 释放Cursor内部申请资源 **/
    Cursor_free_inner(self);

    Cursor_init_inner(self);

	self->isOpen = 0;
    self->isClosed = 1;

	Py_INCREF(Py_None);
	return Py_None;
}

static 
PyObject*
Cursor_Close(
    dm_Cursor*     self
)
{
    PyObject*       retObj;

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, NULL, "ENTER Cursor_Close\n"));

    retObj      = Cursor_Close_inner(self);

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, NULL, "EXIT Cursor_Close, %s\n", retObj == NULL ? "FAILED" : "SUCCESS"));

    return retObj;
}

static 
void
Cursor_Free(
    dm_Cursor*     self
)
{	
    if (Cursor_IsOpen_without_err(self) >= 0)    
        Cursor_Close(self);    

    Cursor_free_inner(self);

	Py_TYPE(self)->tp_free((PyObject*) self);
}

static 
sdint2
Cursor_IsDDL(
    sdint2      stmtType
)
{
	switch(stmtType){
		case DSQL_DIAG_FUNC_CODE_CREATE_TAB:
		case DSQL_DIAG_FUNC_CODE_DROP_TAB:
		case DSQL_DIAG_FUNC_CODE_CREATE_VIEW:
		case DSQL_DIAG_FUNC_CODE_DROP_VIEW:
		case DSQL_DIAG_FUNC_CODE_CREATE_INDEX:
		case DSQL_DIAG_FUNC_CODE_DROP_INDEX:
		case DSQL_DIAG_FUNC_CODE_CREATE_USER:
		case DSQL_DIAG_FUNC_CODE_DROP_USER:
		case DSQL_DIAG_FUNC_CODE_CREATE_ROLE:
		case DSQL_DIAG_FUNC_CODE_DROP_ROLE:
		case DSQL_DIAG_FUNC_CODE_DROP:
		case DSQL_DIAG_FUNC_CODE_CREATE_SCHEMA:
		case DSQL_DIAG_FUNC_CODE_CREATE_CONTEXT_INDEX:
		case DSQL_DIAG_FUNC_CODE_DROP_CONTEXT_INDEX:
		case DSQL_DIAG_FUNC_CODE_CREATE_LINK:
			return 0;
	}

	return -1;
}

//-----------------------------------------------------------------------------
// Cursor_GetStatementType()
//   Determine if the cursor is executing a select statement.
//-----------------------------------------------------------------------------
static 
sdint2 
Cursor_GetStatementType(
    dm_Cursor *self        // cursor to perform binds on
)
{
	sdint4          statementType;
	slength         len;
	DPIRETURN       status = DSQL_SUCCESS;
    Py_ssize_t      size, cols;
    dm_Var*         dm_var;

	Py_BEGIN_ALLOW_THREADS
	status = dpi_get_diag_field(DSQL_HANDLE_STMT, self->handle, 0, 
		DSQL_DIAG_DYNAMIC_FUNCTION_CODE, (dpointer) &statementType, 0, &len);
	Py_END_ALLOW_THREADS
	if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, status,
		"Cursor_GetStatementType()") < 0)
	{
		return -1;
	}

	self->statementType = statementType;
    //bug633895 因为垃圾回收可能在连接关闭后执行，导致已被销毁的obj被重复释放，所以提前释放无用的vobject。
    if (self->col_variables == NULL)
        cols = 0;
    else
        cols = PyList_GET_SIZE(self->col_variables);
    for (size = 0; size < cols; size++)
    {
        dm_var = (dm_Var*)PyList_GET_ITEM(self->col_variables, size);
        if (dm_var->type == &vt_Object)
        {
            (*dm_var->type->finalizeProc)(dm_var);
        }
    }
    Py_CLEAR(self->col_variables);

	return 0;
}

/* 判断是否执行过prepare，并获取执行语句 */
static
sdint2
Cursor_hasPrepared(
    dm_Cursor*      self,               // cursor to perform prepare on
    PyObject**      statement,
    dm_Buffer*      buffer,
    int             direct_flag
)
{
    /* 没有执行语句，也没有执行过prepare */
    if ((*statement == Py_None) && 
        (self->statement == NULL || self->statement == Py_None)) 
    {
        PyErr_SetString(g_ProgrammingErrorException,
            "no statement specified and no prior statement prepared");

        return -1;
    }    

    /* 对于非DDL语句，不需要再次prepare, executedirect不会执行prepare，需要拷贝获取上次执行语句 */
    if (*statement == Py_None || *statement == self->statement)        
    {
        if(!direct_flag && Cursor_IsDDL (self->statementType) < 0)
            return 1;

        //Py_INCREF(self->statement);
        *statement = self->statement;
    }

    if (dmBuffer_FromObject(buffer, *statement, self->environment->encoding) < 0)
    {
        //Py_XDECREF(*statement);		
        return -1;
    }

    /* 语句长度为0 */    
    if (strlen((char*)buffer->ptr) == 0)
    {
        PyErr_SetString(g_ProgrammingErrorException,
            "no statement specified and no prior statement prepared");

        dmBuffer_Clear(buffer); 
        return -1;
    }

    Py_CLEAR(self->statement);        
    return 0;
}

static
void
Cursor_clearDescExecInfo(
    dm_Cursor*      self,
    int             clear_param
)
{
    /* 关闭游标 */
    Cursor_InternalClose(self);

    /* 清理参数描述信息 */
    if (clear_param)
    {
        Cursor_free_paramdesc(self);
    }

    /* 清理列描述信息 */
    Cursor_free_coldesc(self);

    /** 清除上次执行结果 **/
    Cursor_ExecRs_Clear(self);
}

//-----------------------------------------------------------------------------
// Cursor_InternalPrepare()
//   Internal method for preparing a statement for execution.
//-----------------------------------------------------------------------------
static 
sdint2 
Cursor_InternalPrepare(
    dm_Cursor*      self,               // cursor to perform prepare on
    PyObject*       statement           // statement to prepare    
)
{
    dm_Buffer       statementBuffer;  
    DPIRETURN       status = DSQL_SUCCESS;
    sdint2          ret;

    /* 判断如果已经执行prepare，则直接返回 */
    ret = Cursor_hasPrepared(self, &statement, &statementBuffer, 0);
    if (ret != 0)
        return ret;

    /* 清理上次的描述和执行信息 */
    Cursor_clearDescExecInfo(self, 1);

	// prepare statement
    Py_BEGIN_ALLOW_THREADS
        //prepare之前清空上一次绑定参数信息
        status = dpi_unbind_params(self->handle);
        status = dpi_prepare(self->handle, (sdbyte*)statementBuffer.ptr);
    Py_END_ALLOW_THREADS

    dmBuffer_Clear(&statementBuffer);    
    if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, status,
            "Cursor_InternalPrepare(): prepare") < 0) 
	{
        return -1;
	}

    // clear bind variables, if applicable
    if (!self->setInputSizes) 
    {
        Py_XDECREF(self->param_variables);
        self->param_variables = NULL;
    }

    // clear row factory, if spplicable
    Py_XDECREF(self->rowFactory);
    self->rowFactory = NULL;


    /* 获取各参数的描述信息，cursor.prepare和execute中的prepare都需要获取参数信息 */
    if (Cursor_GetParamDescFromDm(self) < 0)
        return -1;

    Py_INCREF(statement);
    self->statement     = statement;

    return 0;
}

static 
sdint2 
Cursor_InternalExecDirect(
    dm_Cursor*      self,               // cursor to perform prepare on
    PyObject*       statement           // statement to prepare      
)
{
    dm_Buffer       statementBuffer;
    DPIRETURN       status = DSQL_SUCCESS;

    /* dpi_exec_direct不需要执行prepare，调用此接口用于获取执行语句 */
    if (Cursor_hasPrepared(self, &statement, &statementBuffer, 1) < 0)
        return -1;

    /* 清理上次的描述和执行信息 */
    Cursor_clearDescExecInfo(self, 1);

    // prepare statement
    Py_BEGIN_ALLOW_THREADS
        status = dpi_exec_direct(self->handle, (sdbyte*)statementBuffer.ptr);
    Py_END_ALLOW_THREADS

    dmBuffer_Clear(&statementBuffer);
    
    if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, status,
            "Cursor_InternalPrepare(): prepare") < 0) 
    {
        return -1;
    }

    // clear bind variables, if applicable
    if (!self->setInputSizes) 
    {
        Py_XDECREF(self->param_variables);
        self->param_variables = NULL;
    }

    // clear row factory, if spplicable
    Py_XDECREF(self->rowFactory);
    self->rowFactory = NULL;

    // determine if statement is a query
    if (Cursor_GetStatementType(self) < 0)
        return -1;	

    /* 获取执行结果信息 */
    if (Cursor_SetRowCount(self) < 0)
        return -1;

    /* 设置execid */
    if (Cursor_SetExecId(self))
    {
        return -1;
    }

    Py_INCREF(statement);
    self->statement     = statement;

    return 0;
}

//-----------------------------------------------------------------------------
// Cursor_ExecRs_Clear()
//   清除上次执行结果影响
//-----------------------------------------------------------------------------
static
void
Cursor_ExecRs_Clear(
    dm_Cursor*     self    // cursor to set the rowcount on
)
{
    // 清除上次执行的结果集描述记录
    if (self->description != Py_None)
    {
        Py_CLEAR(self->description);

        Py_INCREF(Py_None);
        self->description = Py_None;		
    }

    if (self->map_name_to_index != Py_None)
    {
        Py_CLEAR(self->map_name_to_index);

        Py_INCREF(Py_None);
        self->map_name_to_index = Py_None;
    }

    if (self->column_names != Py_None)
    {
        Py_CLEAR(self->column_names);

        Py_INCREF(Py_None);
        self->column_names  = Py_None;
    }

    self->colCount  = 0;
    self->rowNum    = 0;
    self->rowCount  = -1;
    self->with_rows = 0;
}

//-----------------------------------------------------------------------------
// Cursor_SetRowCount()
//   Set the rowcount variable.
//-----------------------------------------------------------------------------
static 
sdint2
Cursor_SetRowCount(
    dm_Cursor*     self    // cursor to set the rowcount on
)
{
	sdint8      rowCount;
	DPIRETURN   status = DSQL_SUCCESS; 
#ifdef DSQL_ROWID
    sdbyte      lastrowid[12];
#else
    sdint8      lastrowid;
#endif
    sdbyte      lastrowid_str[20];
    udint4      len;

    if (self->statementType == DSQL_DIAG_FUNC_CODE_SELECT||
        self->statementType == DSQL_DIAG_FUNC_CODE_CALL) {		
		self->rowCount = 0;				
		// 记录一次fetch操作读取结果集中剩余行数
		self->actualRows    = -1;

		Py_BEGIN_ALLOW_THREADS
			status = dpi_row_count(self->handle, &rowCount);
		Py_END_ALLOW_THREADS

		if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, status,
			"Cursor_SetRowCount()") < 0)
        {
			return -1;
        }

		self->totalRows = (slength)rowCount;	

        /** 置是否存在结果集标识 **/
        if (self->totalRows > 0)
        {
            self->with_rows = 1;
        }

	} else if (self->statementType == DSQL_DIAG_FUNC_CODE_INSERT ||
		self->statementType == DSQL_DIAG_FUNC_CODE_UPDATE ||
		self->statementType == DSQL_DIAG_FUNC_CODE_DELETE ||
        self->statementType == DSQL_DIAG_FUNC_CODE_MERGE) {
			Py_BEGIN_ALLOW_THREADS
				status = dpi_row_count(self->handle, &rowCount);
			Py_END_ALLOW_THREADS
			if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, status,
				"Cursor_SetRowCount()") < 0)
			{
				return -1;
			}

			self->totalRows = (slength)rowCount;
	} else {
		self->totalRows     = -1;
	}

    /** 追加获取lastrowid **/
    Py_DECREF(self->lastrowid_obj);
    if (self->statementType == DSQL_DIAG_FUNC_CODE_INSERT ||
        self->statementType == DSQL_DIAG_FUNC_CODE_UPDATE ||
        self->statementType == DSQL_DIAG_FUNC_CODE_DELETE )
    {
        Py_BEGIN_ALLOW_THREADS
            status = dpi_get_diag_field(DSQL_HANDLE_STMT, self->handle, 0, DSQL_DIAG_ROWID, (dpointer)&lastrowid, sizeof(lastrowid), NULL);
        Py_END_ALLOW_THREADS
            if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, status,
                "Cursor_SetRowCount()") < 0)
            {
                return -1;
            }
#ifdef DSQL_ROWID
            status  = dpi_rowid_to_char(self->connection->hcon, lastrowid, sizeof(lastrowid), lastrowid_str, sizeof(lastrowid_str), &len);
            if (status == 0 && len > 0)
            {
                self->lastrowid_obj = Py_BuildValue("s#", lastrowid_str, len);
            }
            else
            {
                Py_INCREF(Py_None);
                self->lastrowid_obj     = Py_None;
            }
#else
            self->lastrowid_obj = Py_BuildValue("l", lastrowid);
#endif
    }
    else
    {
        Py_INCREF(Py_None);
        self->lastrowid_obj     = Py_None;
    }

	return 0;
}

/************************************************************************
purpose:
    设置语句执行id
************************************************************************/
static 
sdint2
Cursor_SetExecId(
    dm_Cursor*     self    /*IN: cursor to set the rowcount on*/
)
{
    DPIRETURN   status = DSQL_SUCCESS; 
    udint4      execid;

    /** 获取execid **/
    Py_DECREF(self->execid_obj);

    Py_BEGIN_ALLOW_THREADS
    status = dpi_get_diag_field(DSQL_HANDLE_STMT, self->handle, 0, DSQL_DIAG_EXECID, (dpointer)&execid, 0, NULL);
    Py_END_ALLOW_THREADS

    if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, status,
        "Cursor_SetRowCount()") < 0)
    {
        return -1;
    }

    self->execid_obj = Py_BuildValue("l", execid);
   
    return 0;
}

static
sdint2
Cursor_PutDatadmVar_onerow(
    dm_Cursor*      self,
    Py_ssize_t      irow
)
{
    udint4          i;
    dm_Var*         var;

    for (i = 0; i < self->paramCount; i ++)
    {
        var     = (dm_Var*)PyList_GET_ITEM(self->param_variables, i);

        if (dmVar_PutDataAftExec(var, (udint4)irow) < 0)
        {
            return -1;
        }
    }

    return 0;
}

static
sdint2
Cursor_PutDataVariable(
    dm_Cursor*      self,
    Py_ssize_t      rowsize
)
{    
    int             rt = 0;
    Py_ssize_t      i;

    /* dpi_param_data调用作用，指定某个要put_data的列，所有参数put完，再调用一次，通知调用完成 */
    for (i = 0; i < rowsize; i ++)
    {
        rt      = Cursor_PutDatadmVar_onerow(self, i);
        if (rt < 0)
        {
            return rt;
        }
    }
 
    Py_BEGIN_ALLOW_THREADS
        rt = dpi_param_data(self->handle, NULL);
    Py_END_ALLOW_THREADS
    /* 若为0，则直接返回，说明不需要绑定值 */
    if (rt == DSQL_SUCCESS || rt == DSQL_PARAM_DATA_AVAILABLE)
        return rt;

    /* 返回失败，但不是DSQL_NEED_DATA，则报错 */
    if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, rt, 
        "vLong_PutData():dpi_param_data") < 0)
    {
        return -1;
    }

    return 0;
}

//-----------------------------------------------------------------------------
// Cursor_InternalExecute()
//   Perform the work of executing a cursor and set the rowcount appropriately
// regardless of whether an error takes place.
//-----------------------------------------------------------------------------
static 
sdint2
Cursor_InternalExecute(
	dm_Cursor*      self,
    Py_ssize_t      rowsize
)
{
    DPIRETURN       status      = DSQL_SUCCESS;
    DPIRETURN       rt          = DSQL_SUCCESS;
    sdint2          ret;
    dpointer        ptr         = NULL;
    dpointer        data_ptr    = NULL;
    dm_Var*         dm_var;
    udint4          cols        = 0;
    PyObject*       newParamVal;
    sdint4*         length      = PyMem_Malloc(sizeof(sdint4));
    udint4          i           = 0;

    Cursor_clearDescExecInfo(self, 0);

	Py_BEGIN_ALLOW_THREADS
		status = dpi_exec(self->handle);
	Py_END_ALLOW_THREADS

    /* 若NEED_DATA（仅long string/binary），则补充数据 */
    if (status == DSQL_NEED_DATA)
    {
        status = Cursor_PutDataVariable(self, rowsize);
        if (status < 0)
        {
            PyMem_Free(length);
            return -1;        
        }
    }

    if(self->output_stream == 1 && self->outparam_num > 0)
    {
        while (status == DSQL_SUCCESS)
        {
            Py_BEGIN_ALLOW_THREADS
                status = dpi_more_results(self->handle);
            Py_END_ALLOW_THREADS
        }
    }

    //如果返回值为DSQL_PARAM_DATA_AVAILABLE，则流式获取输出参数
    if (self->output_stream == 1 && status == DSQL_PARAM_DATA_AVAILABLE)
    {
        self->param_value =(PyObject**) PyMem_Malloc((self->outparam_num)*sizeof(PyObject*));

        for(i = 0; i < self->outparam_num; i++)
        {
            self->param_value[i]= PyList_New(0);
        }

        while(1)
        {
            Py_BEGIN_ALLOW_THREADS
            rt = dpi_param_data(self->handle, &ptr);
            Py_END_ALLOW_THREADS

            if (rt == DSQL_PARAM_DATA_AVAILABLE)
            {
                dm_var = (dm_Var*)PyList_GET_ITEM(self->param_variables, ((udbyte)ptr)-1);
                data_ptr = (dpointer)dm_var->data;

                if (Py_TYPE(dm_var) == &g_LongBinaryVarType ||
                    Py_TYPE(dm_var) == &g_LongStringVarType)
                {
                    Py_BEGIN_ALLOW_THREADS
                        rt = dpi_get_data(self->handle, (udbyte)ptr, dm_var->type->cType, NULL, 0, length);
                    Py_END_ALLOW_THREADS
                    if (!DSQL_SUCCEEDED(rt))
                        *length = 0;
                    if(((sdint8*)dm_var->data)[0] != 0)
                        PyMem_FREE((char*)(int3264)((sdint8*)dm_var->data)[0]);
                    ((sdint8*)dm_var->data)[0] = (sdint8)(int3264)PyMem_Malloc(*length + 1);
                    data_ptr = (dpointer)(int3264)((sdint8*)dm_var->data)[0];
                    dm_var->bufferSize = *length + 1;
                }

                Py_BEGIN_ALLOW_THREADS
                    rt = dpi_get_data(self->handle, (udbyte)ptr, dm_var->type->cType, data_ptr, dm_var->bufferSize, length);
                Py_END_ALLOW_THREADS

                if (DSQL_SUCCEEDED(rt))
                {
                    dm_var->indicator[0] = *length;
                    dm_var->actualLength[0] = *length;
                    newParamVal = dmVar_GetValue((dm_Var*)dm_var, 0);
                    PyList_Append(self->param_value[cols++], newParamVal);
                }
                else if (rt == DSQL_NO_DATA)
                {
                    PyList_Append(self->param_value[cols++], Py_None);
                }
                else if (rt == DSQL_ERROR)
                {
                    if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, status,
                        "Cursor_InternalExecute()") < 0)
                    {
                        for (i = 0; i < self->outparam_num; i++)
                        {
                            Py_DECREF(self->param_value[i]);
                        }
                        PyMem_Free(self->param_value);
                        PyMem_Free(length);
                        return -1;
                    }
                }
            }
            else if (rt == DSQL_SUCCESS)
            {
                Py_BEGIN_ALLOW_THREADS
                rt = dpi_more_results(self->handle);
                Py_END_ALLOW_THREADS

                if (rt == DSQL_NO_DATA)
                    break;

                cols = 0;
            }
            else 
            {
                if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, status,
                    "Cursor_InternalExecute()") < 0)
                {
                    for (i = 0; i < self->outparam_num; i++)
                    {
                        Py_DECREF(self->param_value[i]);
                    }
                    PyMem_Free(self->param_value);
                    PyMem_Free(length);
                    return -1;
                }
            }
        }
    }
    else
    {
        if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, status, 
            "Cursor_InternalExecute()") < 0)
        {
            PyMem_Free(length);
            return -1;
        }
    }

    if (Cursor_SetExecId(self) < 0)
    {
        PyMem_Free(length);
        return -1;
    }

    // determine if statement is a query
    if (Cursor_GetStatementType(self) < 0)
    {
        PyMem_Free(length);
        return -1;
    }

    ret     = Cursor_SetRowCount(self);

    //存在绑定参数，则unbind param
    if (self->paramCount > 0)
    {
        Py_BEGIN_ALLOW_THREADS
            status = dpi_unbind_params(self->handle);
        Py_END_ALLOW_THREADS
    }
    PyMem_Free(length);
    return ret;
}

static
sdint2
Cursor_GetColDescFromDm_low(
    dm_Cursor*      self,
    dhdesc          hdesc_col
)
{    
    DPIRETURN   rt = DSQL_SUCCESS;
    udint2      icol;
    sdint4      val_len;

    self->bindColDesc = PyMem_Malloc(self->colCount * sizeof(DmColDesc));
    if (self->bindColDesc == NULL)
    {
        PyErr_NoMemory();
        return -1;
    }
    memset(self->bindColDesc, 0, self->colCount * sizeof(DmColDesc));    

    for (icol = 0; icol < self->colCount; icol ++)
    {
        rt  = dpi_desc_column(self->handle, icol + 1, 
                              self->bindColDesc[icol].name, sizeof(self->bindColDesc[icol].name), &self->bindColDesc[icol].nameLen,
                              &self->bindColDesc[icol].sql_type, &self->bindColDesc[icol].prec, 
                              &self->bindColDesc[icol].scale, &self->bindColDesc[icol].nullable);
        if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, rt,
            "Cursor_GetColDescFromDm():dpi_desc_column") < 0)
        {
            return -1;		
        }

        rt  = dpi_get_desc_field(hdesc_col, icol + 1, DSQL_DESC_DISPLAY_SIZE, (dpointer)&self->bindColDesc[icol].display_size,
            0, &val_len);
        if (Environment_CheckForError(self->environment, hdesc_col, DSQL_HANDLE_DESC, rt,
            "Cursor_GetColDescFromDm():dpi_get_desc_field[DSQL_DESC_DISPLAY_SIZE]") < 0)
        {
            return -1;		
        }        
    }

    return 0;
}

static
sdint2
Cursor_GetColDescFromDm(
    dm_Cursor*     self
)
{
    DPIRETURN   rt = DSQL_SUCCESS;
    sdint4      val_len;

    /* 申请列描述句柄 */    
    Py_BEGIN_ALLOW_THREADS
        rt  = dpi_get_stmt_attr(self->handle, DSQL_ATTR_IMP_ROW_DESC, (dpointer)&self->hdesc_col, 0, &val_len);
    Py_END_ALLOW_THREADS
        if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, rt, 
            "Cursor_GetColDescFromDm():dpi_get_stmt_attr") < 0)
            return -1;	    

    return Cursor_GetColDescFromDm_low(self, self->hdesc_col);        
}

static 
sdint2
Cursor_SetColVariables(
    dm_Cursor*     self
)
{
    udint2          icol;
    dm_Var*         dm_var;
    udint2          varchar_flag = 0;
    sdbyte          attr[10] = {0};
    DPIRETURN       rt = DSQL_SUCCESS;

    if ((int)self->arraySize < 0 || self->arraySize > ULENGTH_MAX)
    {
        PyErr_SetString(g_ErrorException, "Invalid cursor arraysize\n");
        return -1;
    }

    Py_CLEAR(self->col_variables);

    self->col_variables = PyList_New(self->colCount);
    if (self->col_variables == NULL)
    {
        if (!PyErr_Occurred())
            PyErr_NoMemory();

        return -1;
    }
//bug653857 新增nls_numeric_characters，dmPython接口需要进行支持
#ifdef DSQL_ATTR_NLS_NUMERIC_CHARACTERS
    rt = dpi_get_con_attr(self->connection->hcon, DSQL_ATTR_NLS_NUMERIC_CHARACTERS, attr, 10, NULL);
    if (!DSQL_SUCCEEDED(rt) || strcmp(attr, ".,") == 0)
    {
        varchar_flag = 0;
    }
    else
    {
        varchar_flag = 1;
    }
#endif

    for (icol = 0; icol < self->colCount; icol ++)
    {
        dm_var = dmVar_Define(self, self->hdesc_col, icol + 1, (udint4)self->arraySize, varchar_flag);
        if (dm_var == NULL)
            return -1;

        PyList_SET_ITEM(self->col_variables, icol, (PyObject*)dm_var);
    }

    self->org_bindArraySize = self->bindArraySize;

    return 0;
}

static 
sdint2
Cursor_PerformDefine(
    dm_Cursor*      self,
    sdint2*         isQuery
)
{
	DPIRETURN status = DSQL_SUCCESS;	
	sdint2	i = 0;
    PyObject*       desc;

    if (isQuery)
    {
        *isQuery = 0;
    }

	// determine number of items in select-list
	Py_BEGIN_ALLOW_THREADS
	status = dpi_number_columns(self->handle, &self->colCount);
	Py_END_ALLOW_THREADS
	if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, status,
		"Cursor_PerformDefine()") < 0)
	{
		return -1;		
	}

    /* 若列数为0， 则直接返回 */
    if (self->colCount == 0)
    {        
        return 0;
    }

    if (isQuery)
    {
        *isQuery = 1;
    }

    /** 获取各列描述信息 **/
    if (Cursor_GetColDescFromDm(self) < 0)
        return -1;    

    /** 设置列绑定 **/
    if (Cursor_SetColVariables(self) < 0)
        return -1;

    /** 获取描述信息 **/
    desc    = Cursor_GetDescription(self, NULL);
    if (desc == NULL)
        return -1;
    //Py_CLEAR(desc);
    Py_DECREF(desc);

	return 0;
}

static
sdint2
Cursor_GetParamDescFromDm_low(
    dm_Cursor*     self
)
{    
    DPIRETURN   rt = DSQL_SUCCESS;
    udint2      iparam;    

    self->bindParamDesc = PyMem_Malloc(self->paramCount * sizeof(DmParamDesc));
    if (self->bindParamDesc == NULL)
    {
        PyErr_NoMemory();
        return -1;
    }
    memset(self->bindParamDesc, 0, self->paramCount * sizeof(DmParamDesc));

    self->outparam_num =0;
    for (iparam = 0; iparam < self->paramCount; iparam ++)
    {
        rt  = dpi_desc_param(self->handle, iparam + 1, 
                             &self->bindParamDesc[iparam].sql_type, &self->bindParamDesc[iparam].prec, 
                             &self->bindParamDesc[iparam].scale, &self->bindParamDesc[iparam].nullable);
        if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, rt,
            "Cursor_GetColDescFromDm():dpi_desc_param") < 0)
        {
            return -1;		
        }     

        rt  = dpi_get_desc_field(self->hdesc_param, iparam + 1, DSQL_DESC_PARAMETER_TYPE, 
                                 (dpointer)&self->bindParamDesc[iparam].param_type, 0, NULL);

        if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, rt,
            "Cursor_GetColDescFromDm():dpi_get_desc_field") < 0)
        {
            return -1;		
        }

        if(self->bindParamDesc[iparam].param_type == DSQL_PARAM_OUTPUT && self->bindParamDesc[iparam].sql_type != DSQL_RSET)
            self->outparam_num += 1;

        /* 获取参数名称DSQL_DESC_NAME */
        rt  = dpi_get_desc_field(self->hdesc_param, iparam + 1, DSQL_DESC_NAME, 
            (dpointer)self->bindParamDesc[iparam].name, 128, &self->bindParamDesc[iparam].namelen);

        if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, rt,
            "Cursor_GetColDescFromDm():dpi_get_desc_field") < 0)
        {
            return -1;		
        }
    }

    return 0;
}

static
sdint2
Cursor_GetParamDescFromDm(
    dm_Cursor*     self
)
{
    DPIRETURN   rt = DSQL_SUCCESS;
    sdint4      val_len;

    Py_BEGIN_ALLOW_THREADS
        rt = dpi_number_params(self->handle, &self->paramCount);
    Py_END_ALLOW_THREADS
        if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, rt,
            "Cursor_InternalPrepare(): dpi_number_params") < 0) 
            return -1;  

    if (self->paramCount <= 0)
    {
        return 0;
    }

    /** 申请参数描述句柄 **/    
    Py_BEGIN_ALLOW_THREADS
        rt = dpi_get_stmt_attr(self->handle, DSQL_ATTR_IMP_PARAM_DESC, &self->hdesc_param, 0, &val_len);
    Py_END_ALLOW_THREADS
        if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, rt, 
            "Cursor_GetParamDescFromDm():dpi_get_stmt_attr") < 0)
            return -1;

    return Cursor_GetParamDescFromDm_low(self);
}

static
sdint2
Cursor_SetParamRowSize_Oper(
	dm_Cursor*      cursor,
	udint4			paramrowSize
)
{
	DPIRETURN		rt = DSQL_SUCCESS;

	Py_BEGIN_ALLOW_THREADS
		rt = dpi_set_stmt_attr(cursor->handle, DSQL_ATTR_PARAMSET_SIZE, (dpointer)paramrowSize, 0);
	Py_END_ALLOW_THREADS
	if (Environment_CheckForError(cursor->environment, cursor->handle, DSQL_HANDLE_STMT, rt,
		"Cursor_SetParamRowSize_Oper():dpi_set_stmt_attr") < 0)
		return -1;

	return 0;
}

static
sdint2
Cursor_setParamVariablesHelper(
    dm_Cursor*      self,
    PyObject*       iValue,
    unsigned        numElements, 
    unsigned        irow,   /* 绑定参数的行号，0-based */
    unsigned        ipos,   /* 绑定参数的编号，1-based */
    dm_Var*         org_var,
    dm_Var**        new_var
)
{
    dm_Var*         dm_var = NULL;    
    int             is_udt = 0;    

    *new_var    = NULL;
    is_udt      = dmVar_Check(iValue); 

    /** 已经存在，若为None，则替换为新的变量类型；否则，与新类型不一样，则报错 **/
    if (org_var != NULL)
    {
        /** 自定义类型，替换;否则，将新值加入到org_var中 **/
        if (is_udt == 1)
        {
            /** 不是同一个变量，则替换，重用 **/
            if ((PyObject*)org_var != iValue)
            {
                Py_INCREF(iValue);
                *new_var    = (dm_Var*)iValue;                
            }            
        }
        else if (numElements > ((dm_Var*)org_var)->allocatedElements)
        {
            *new_var    = dmVar_NewByVarType(self, org_var->type, numElements, org_var->size);
            if (!*new_var)
                return -1;

            if (dmVar_SetValue(*new_var, irow, iValue) < 0)
                return -1;
        }
        else if (dmVar_SetValue(org_var, irow, iValue) < 0)
        {
            // executemany() should simply fail after the first element
            if (irow > 0)
                return -1;

            // anything other than index error or type error should fail
            if (!PyErr_ExceptionMatches(PyExc_IndexError) &&
                !PyErr_ExceptionMatches(PyExc_TypeError))
                return -1;

            // clear the exception and try to create a new variable
            PyErr_Clear();
            org_var = NULL;
        }        
    }    

    /** 若原来无变量，则重新定义 **/
    if (org_var == NULL)
    {
        /** 若为自定义类型，则直接转换;否则，根据Python数据创建udt变量**/
        if (is_udt)
        {
            Py_INCREF(iValue);

            dm_var             = (dm_Var*)iValue;
            dm_var->boundPos   = 0;
        }
        else
        {
            dm_var             = dmVar_NewByValue(self, iValue, numElements, ipos);
            if (dm_var == NULL)
                return -1;

            if (dmVar_SetValue(dm_var, irow, iValue) < 0)
                return -1;
        }

        (*new_var)  = dm_var;
    }

    return 0;
}

/** 根据绑定参数名称从dict中找到目标参数值 **/
static
PyObject*
Cursor_getParamValue_FromDict(
    dm_Cursor*      self,
    PyObject*       dict,
    PyObject*       dickKeys,
    int             iparam
)
{
    PyObject*       iValue = Py_None;
    PyObject*       keyObj;
    Py_ssize_t      key_num;
    Py_ssize_t      key_i;
    char*           strvalue;

    iValue      = PyDict_GetItemString(dict, self->bindParamDesc[iparam].name);
    if (iValue != NULL)
        return iValue;

    iValue      = Py_None;
    key_num     = PyList_GET_SIZE(dickKeys);
    for (key_i = 0; key_i < key_num; key_i ++)
    {
        keyObj      = PyList_GetItem(dickKeys, key_i); 
        if (keyObj == NULL)
            return NULL;

        strvalue    = py_String_asString(keyObj);
#ifdef WIN32
        if (stricmp(strvalue, self->bindParamDesc[iparam].name) == 0)
#else        
        if (strcasecmp(strvalue, self->bindParamDesc[iparam].name) == 0)
#endif        
        {
            iValue  = PyDict_GetItemString(dict, strvalue);
            if (iValue == NULL)
            {
                PyErr_SetString(PyExc_ValueError, 
                    "Error occurs in dict to be bound");
                return NULL;
            }

            break;
        }
    }

    return iValue;
}   

/** 设置参数变量，仅支持按位置绑定 **/
static
sdint2
Cursor_setParamVariables_oneRow(
    dm_Cursor*      self,
    PyObject*       parameters,
    Py_ssize_t      irow,
    Py_ssize_t      n_row
)
{
    sdint2          ret = -1;
    int             boundByPos = 0;
    int             iparam;    
    Py_ssize_t      param_num = 0;
    PyObject*       iValue;    
    PyObject*       dictKeys = NULL;
    dm_Var*         new_var = NULL;
    dm_VarType*     new_varType = NULL;     //参数类型
    dm_VarType*     tmp_varType = NULL;     //临时变量
    udint4          size;
    int             is_udt;
    sdint2          param_type;
    DmParamDesc*    bindParamDesc;          // 绑定参数信息
    
    /** 若参数不是序列，则报错 **/
    if (parameters != NULL && parameters != Py_None)
    {
        if (PySequence_Check(parameters))
        {
            param_num   = PySequence_Size(parameters);        
            boundByPos  = 1;
        }
        else if (PyDict_Check(parameters))
        {
            param_num   = PyDict_Size(parameters);
            boundByPos  = 0;
            dictKeys    = PyDict_Keys(parameters);
        }
        else
        {
            PyErr_SetString(g_ProgrammingErrorException, 
                "only bound by Position or Name supported.");

            return -1;
        }            
    }    
    
    /* 此处param_variables长度与语句中参数个数一定相等，往列表中加入值 */    
    for (iparam = 0; iparam < self->paramCount; iparam ++)
    {       
        iValue          = Py_None;

        bindParamDesc   = &self->bindParamDesc[iparam];
        param_type      = bindParamDesc->param_type;

        if (param_num > 0)
        {
            if (!boundByPos)
            {           
                iValue  = Cursor_getParamValue_FromDict(self, parameters, dictKeys, iparam);
                if (iValue == NULL)
                    goto fun_end;
            }
            else if (iparam < param_num)
            {
                iValue  = PySequence_GetItem(parameters, iparam);
                if (!iValue)
                    goto fun_end;
                Py_DECREF(iValue);
            }
        }

        /* 若为Py_None，则下一个 */
        if (iValue == Py_None)
        {
            continue;
        }

        /* 变量是否为用户自定义 */
        is_udt  = dmVar_Check(iValue); 

        /* prepare时已经准备好空的param_variables，里面存放的是未赋值的对象 */
        new_var = (dm_Var*)PyList_GET_ITEM(self->param_variables, iparam);

        /* 当前变量列第一次出现非None的绑定参数值，生成新变量，则加入到List中 */
        if (new_var == NULL)
        {
            new_varType = dmVar_TypeByValue(iValue, &size);
            if (new_varType == NULL)
                goto fun_end;

            /* 若为输入输出或者输出或者输入类型，且参数描述类型为LongString或者LongBinary，则进行转化 */
            if (param_type == DSQL_PARAM_INPUT_OUTPUT ||
                param_type == DSQL_PARAM_OUTPUT ||
                param_type == DSQL_PARAM_INPUT)
            {
                tmp_varType = dmVar_TypeBySQLType(bindParamDesc->sql_type, 1);
                if (tmp_varType == NULL)
                {
                    goto fun_end;
                }

                //sql_type是服务器推荐类型，如果是varchar，而绑定数据是bytes，则绑定类型用binary
                if (bindParamDesc->sql_type == DSQL_VARCHAR && new_varType == &vt_Binary)
                {
                    bindParamDesc->sql_type = DSQL_BINARY;

                    if (bindParamDesc->prec > size)
                    {
                        bindParamDesc->prec = size;
                    }
                }

                // bug631212 如果数据库内部使用numeric，而使用dmPython传入int类型数据时绑定类型仍然使用float类型否则第一个使用int后之后绑定参数将会丢失小数部分
                if (bindParamDesc->sql_type == DSQL_DEC && new_varType != &vt_Boolean && param_type == DSQL_PARAM_INPUT && (n_row > 1))
                {
                    new_varType = &vt_Float;
                }

                //sql_type是服务器推荐类型，如果是varchar，而绑定数据是datetime，则绑定类型用timestamp
                if (bindParamDesc->sql_type == DSQL_VARCHAR && new_varType == &vt_Timestamp)
                {
                    bindParamDesc->sql_type = DSQL_TIMESTAMP;

                    bindParamDesc->prec     = 26;
                    bindParamDesc->scale    = 6;
                }

                // bug627535 当输出参数为CLOB类型时进行转换会导致输出错误，例如作为returnging输出参数时存在text类型参数，因此在此处对于输出参数且SQL类型为CLOB类型时不再进行转换
                if(!((param_type == DSQL_PARAM_OUTPUT)&&(bindParamDesc->sql_type == DSQL_CLOB)))
                {
                    //python2.7中超长二进制流串读取出来是long str类型，绑定时按 参数描述sql类型 映射的 变量类型 去绑定
                    if (new_varType == &vt_String || new_varType == &vt_Binary || new_varType == &vt_LongString)
                    {
                        if (new_varType == tmp_varType ||
                            tmp_varType == &vt_LongString || tmp_varType == &vt_LongBinary)
                        {
                            new_varType = tmp_varType;
                            size = -1;
                        }
                    }
                }          
            }

            //如果绑定参数是用户定义类型，并且作为输出参数，则直接将该参数绑定，不需要重新分配一个new_var
            if ((param_type == DSQL_PARAM_INPUT_OUTPUT || param_type == DSQL_PARAM_OUTPUT) &&
                is_udt == 1)
            {
                new_var = iValue;
                Py_INCREF(iValue);
            }
            else
            {
                new_var     = dmVar_NewByVarType(self, new_varType, n_row, size);
                if (new_var == NULL)
                {
                    goto fun_end;
                }

                /** 若为复合类型，则需先生成句柄对象 **/
                if (new_var->type->pythonType == &g_ObjectVarType &&
                    ObjectVar_GetParamDescAndObjHandles((dm_ObjectVar*)new_var, self->hdesc_param, iparam + 1) < 0)
                {
                    goto fun_end;
                }

                /* 往新生成的变量对象中赋值 */
                if (dmVar_SetValue(new_var, irow, iValue) < 0)
                {
                    goto fun_end;
                }
            }

            /* 将已经赋值的变量加入的参数列表中，待绑定使用 */
            PyList_SetItem(self->param_variables, iparam, new_var);

            continue;
        }
        
        /* 一定是批量绑定，前面的行已经存在，加入新行，直接设置变量值 */
        if (dmVar_SetValue(new_var, irow, iValue) < 0)
        {
            goto fun_end;
        }                                   
    }    
    
    ret     = 0;

fun_end:
    Py_XDECREF(dictKeys);

    return ret;
}

static
sdint2
Cursor_setParamVariables(
    dm_Cursor*      self,
    PyObject*       parameters,
    int             is_many,
    Py_ssize_t*     prow_size
)
{
    int                 boundByPos;
    PyObject*           tmp_param = NULL;    
    Py_ssize_t          irow;
    int                 iparam;    
    dm_Var*             new_var = NULL;
    dm_VarType*         new_varType;    

    if (is_many)
    {
        if (parameters == NULL || parameters == Py_None || PyDict_Check(parameters))
        {
            PyErr_SetString(g_InterfaceErrorException, "expecting a sequence of parameters");

            return -1;
        }

        /** 若参数不是序列，则报错 **/
        boundByPos      = PySequence_Check(parameters);
        if (boundByPos == 0)
        {
            PyErr_SetString(g_ProgrammingErrorException, 
                "only bound by Position supported.");
            
            return -1;
        }

        // ensure that input sizes are reset
        // this is done before binding is attempted so that if binding fails and
        // a new statement is prepared, the bind variables will be reset and
        // spurious errors will not occur
        self->setInputSizes         = 0;
    }

    /** 计算绑定参数的行数，并申请足够的绑定参数空间 **/
    if (is_many == 0)
        *prow_size          = 1;
    else
        *prow_size          = PySequence_Size(parameters);

    Py_CLEAR(self->param_variables);

    /* 按参数个数申请list的大小，list中的每个item表示每个参数待绑定的值，多行绑定时每个item有多个值 */
    self->param_variables   = PyList_New(self->paramCount);
    if (self->param_variables == NULL)
    {
        return -1; 
    }

    /* 给各参数赋值，若未指定，则为NULL */
    for (irow = 0; irow < *prow_size; irow ++)
    {
        /* 非并行直接取 */
        if (irow == 0 && is_many == 0)
        {
            tmp_param   = parameters;
        }
        else /* 并行取其中的一行 */
        {
            tmp_param   = PySequence_GetItem(parameters, irow);
            Py_DECREF(tmp_param);
        }        

        if (Cursor_setParamVariables_oneRow(self, tmp_param, irow, *prow_size) < 0)
        {
            return -1;
        }
    }

    /* 以上仅处理存在绑定参数值的情况，若某一列未绑定过或者均为None，则此处根据SQL_TYPE申请绑定对象 */
    for (iparam = 0; iparam < self->paramCount; iparam ++)
    {
        new_var         = PyList_GET_ITEM(self->param_variables, iparam);
        if (new_var != NULL)
            continue;

        new_varType     = dmVar_TypeBySQLType(self->bindParamDesc[iparam].sql_type, 1);
        if (new_varType == NULL)
        {
            return -1;
        }

        new_var         = dmVar_NewByVarType(self, new_varType, *prow_size, new_varType->size);
        if (new_var == NULL)
        {
            return -1;
        }
        
        /* 非输入参数类型，且为复合类型，则需先生成句柄对象 **/
        if ((self->bindParamDesc[iparam].param_type == DSQL_PARAM_INPUT_OUTPUT ||
            self->bindParamDesc[iparam].param_type == DSQL_PARAM_OUTPUT) &&
            new_var->type->pythonType == &g_ObjectVarType &&
            ObjectVar_GetParamDescAndObjHandles((dm_ObjectVar*)new_var, self->hdesc_param, iparam + 1) < 0)
        {
            return -1;        
        }

        PyList_SetItem(self->param_variables, iparam, new_var);
    }

    return 0;
}

static
sdint2
Cursor_BindParamVariable(
   dm_Cursor*       self,
   Py_ssize_t       rowsize
)
{
    DPIRETURN		rt = DSQL_SUCCESS;
    udint2          iparam;
    dm_Var*         dm_var;
    ulength         rsize;

    rsize           = (ulength)rowsize;

    Py_BEGIN_ALLOW_THREADS
        rt = dpi_set_stmt_attr(self->handle, DSQL_ATTR_PARAMSET_SIZE, (dpointer)rsize, 0);
    Py_END_ALLOW_THREADS
        if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, rt,
            "Desc_SetParamRowSize_Oper():dpi_set_stmt_attr") < 0)
            return -1;

    for (iparam = 0; iparam < self->paramCount; iparam ++)
    {
        dm_var = (dm_Var*)PyList_GET_ITEM(self->param_variables, iparam);
        if (dm_var == NULL)
        {
            PyErr_SetString(g_ProgrammingErrorException,
                            "Not all parameters bound.");
            return -1;
        }

        if (dmVar_Bind(dm_var, self, iparam + 1) < 0)
            return -1;
    }

    return 0;
}

//-----------------------------------------------------------------------------
// Cursor_PerformBind()
//   Perform the binds on the cursor.
//-----------------------------------------------------------------------------
static
sdint2
Cursor_PerformBind(
   dm_Cursor*       self,                   // cursor to perform binds on
   PyObject*        parameters,	               // parameters to bind
   sdint2           isMany,						// 是否执行多行操作
   Py_ssize_t*      rowsize
)
{
    *rowsize        = 0;

    /** 若设置了setinputsize，绑定参数个数必须和setinputsize中的列个数一致 **/
    if (self->setInputSizes)
    {
        if (PyList_Check(self->param_variables))
        {
            if (PyList_GET_SIZE(self->param_variables) != self->paramCount)
            {
                self->setInputSizes = 0;

                Py_XDECREF(self->param_variables);
                self->param_variables = NULL;

                return 0;
            }
        }
    }

    /** 若参数个数为0，则直接返回 **/
    if (self->paramCount == 0)
        return 0;        

    /** 根据各参数描述信息，定义变量对象 **/
    if (Cursor_setParamVariables(self, parameters, isMany, rowsize) < 0)
        return -1;

    /** 绑定参数 **/
    return Cursor_BindParamVariable(self, *rowsize);
}

// 解决参数为动态或静态不能调用系统函数统一处理的问题
sdint4
Cursor_ParseArgs(
	PyObject		*args,
	PyObject		**specArg,		// SQL语句等第一个所需参数
	PyObject		**seqArg		// 其他序列参数
)
{
	Py_ssize_t  argCount = PyTuple_GET_SIZE(args);  
	sdint4      iparam;
	PyObject*   itemParam = NULL;
    PyObject*   itemParam_fst = NULL;

    if (specArg != NULL)
        *specArg = NULL;

    if (seqArg != NULL)
        *seqArg = NULL;

    if (argCount == 0)
        return 0;
	
	*specArg = PyTuple_GetItem(args, 0);
	if (!*specArg)
		return -1;	

    if (argCount == 1)
        return 0;

	// 若第一个参数非tuple且非list且非dict，则认为是动态参数
	itemParam_fst   = PyTuple_GetItem(args, 1);
	if (itemParam_fst == NULL)
		return -1;
    
    itemParam   = itemParam_fst;

	// 动态参数
	if (!PyTuple_Check(itemParam) && !PyList_Check(itemParam) && !PyDict_Check(itemParam))
	{
		*seqArg = PyList_New(argCount - 1);
		if (!*seqArg)
			return -1;
		        
        Py_INCREF(itemParam);
		PyList_SetItem(*seqArg, 0, itemParam);		

		for (iparam = 2; iparam < argCount; iparam ++)
		{
			itemParam = PyTuple_GetItem(args, iparam);
			if (itemParam == NULL)
				return -1;

            Py_INCREF(itemParam);
			PyList_SetItem(*seqArg, iparam - 1, itemParam);			
		}
	}	
	else if(argCount == 2)
	{
		Py_INCREF(itemParam);
		*seqArg = itemParam;
	}
    else
    {
        PyErr_SetString(PyExc_ValueError, 
            "expecting a sequence or dict parameters");
        return -1;
    }
	
	return 0;
}

/* 增加executedirect方法，对应dpi_exec_direct */
static 
PyObject*
Cursor_ExecuteDirect(
    dm_Cursor*      self, 
    PyObject*       args
)
{
    PyObject*       statement = NULL;
    PyObject*       ret_obj = NULL;

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_ExecuteDirect\n"));
    
    if (!PyArg_ParseTuple(args, "O", &statement))
        goto fun_end;
    
    DMPYTHON_TRACE_INFO(dpy_trace(statement, NULL, "ENTER Cursor_ExecuteDirect,before Cursor_Execute_inner\n"));

    ret_obj         = Cursor_Execute_inner(self, statement, NULL, 0, 1, 0);

fun_end:
    
    DMPYTHON_TRACE_INFO(dpy_trace(statement, NULL, "EXIT Cursor_ExecuteDirect, %s\n", ret_obj == NULL ? "FAILED" : "SUCCESS"));

    return ret_obj;
}

int
Cursor_outparam_exist(
    dm_Cursor*     self
)
{
    udint2      i;

    if (self->paramCount == 0 ||
        self->bindParamDesc == NULL)
        return 0;

    for (i = 0; i < self->paramCount; i ++)
    {
        if (self->bindParamDesc[i].param_type == DSQL_PARAM_INPUT_OUTPUT ||
            self->bindParamDesc[i].param_type == DSQL_PARAM_OUTPUT)
            return 1;
    }

    return 0;
}

void
Cursor_BoundParamAndCols_Clear(
    dm_Cursor*     self
)
{
    Py_ssize_t      size;
    Py_ssize_t      i;
    PyObject*       item;

    if (self->param_variables != NULL)
    {
        size    = PyList_GET_SIZE(self->param_variables);
        
        for (i = 0; i < size; i ++)
        {
            item    = PyList_GET_ITEM(self->param_variables, i);
            if (item != NULL)
            {
                dmVar_Finalize((dm_Var*)item);
            }
        }
    }

    if (self->col_variables != NULL)
    {
        size    = PyList_GET_SIZE(self->col_variables);

        for (i = 0; i < size; i ++)
        {
            item    = PyList_GET_ITEM(self->col_variables, i);
            if (item != NULL)
            {
                dmVar_Finalize((dm_Var*)item);
            }
        }
    }
}

PyObject*
Cursor_Execute_inner(
    dm_Cursor*      self, 
    PyObject*       statement,
    PyObject*       executeArgs,
    int             is_many,
    int             exec_direct,
    int             from_call
)
{
    sdint2          isQuery = 0;
    PyObject*       paramsRet = NULL;
    Py_ssize_t      rowsize;

    /** statement为NULL，报错 **/
    if (statement == NULL)
    {
        PyErr_SetString(PyExc_TypeError, "expecting a None or string statement arguement");
        
        return NULL;
    }

    if (executeArgs && 
        !PySequence_Check(executeArgs) && !PyDict_Check(executeArgs))
    {
        PyErr_SetString(PyExc_TypeError, "expecting a sequence or dict args");
        
        return NULL;
    }

    // make sure the cursor is open
    if (Cursor_IsOpen(self) < 0)
        return NULL;

    self->execute_num   += 1;

    // prepare the statement, if applicable
    if (exec_direct == 1)
    {
        if (Cursor_InternalExecDirect(self, statement) < 0)
            return NULL;
    }
    else
    {
        if (Cursor_InternalPrepare(self, statement) < 0)
        {
            goto fun_end;
        }

        // perform binds
        if (Cursor_PerformBind(self, executeArgs, is_many, &rowsize) < 0)
        {
            goto fun_end;
        }

        // execute the statement
        if (Cursor_InternalExecute(self, rowsize) < 0)
        {
            goto fun_end;
        }
    }

    // perform defines, if necessary    
    if ((self->statementType == DSQL_DIAG_FUNC_CODE_SELECT ||
        self->statementType == DSQL_DIAG_FUNC_CODE_CALL) && 
        Cursor_PerformDefine(self, &isQuery) < 0)
    {
        goto fun_end;
    }

    // reset the values of setoutputsize()
    self->outputSize = -1;
    self->outputSizeColumn = -1; 

    //reset the values of setinputsize()
    if (self->setInputSizes)
    {
        self->setInputSizes = 0;

        Py_XDECREF(self->param_variables);
        self->param_variables = NULL;
    }

    /** 若是CALL操作或者存在输出参数，则直接返回参数列表 **/
    if (from_call == 1 || Cursor_outparam_exist(self))
    {
        paramsRet = Cursor_MakeupProcParams(self);
        if (paramsRet == NULL)
        {
            goto fun_end;
        }

        /* paramsRet是由PyList_NEW出来，引用计数默认为1，这里不需要再加1，直接返回 */
        //Py_INCREF(paramsRet);
        return paramsRet;        
    }        

    // for queries, return the cursor for convenience
    if (isQuery) 
    {
        Py_INCREF(self);
        return (PyObject*) self;        
    }

    // for all other statements, simply return None
    Py_INCREF(Py_None);
    return Py_None;    

fun_end:
    /** 执行失败，释放变量 **/
    Cursor_BoundParamAndCols_Clear(self);

    return NULL;
}

static 
PyObject*
Cursor_Execute(
    dm_Cursor*      self, 
    PyObject*       args, 
    PyObject*       keywordArgs
)
{
	PyObject*       statement = NULL;
    PyObject*       executeArgs = NULL; /** 为内部申请，需主动释放 **/
    PyObject*       retObject = NULL;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_Execute\n"));

	if (Cursor_ParseArgs(args, &statement, &executeArgs) < 0)
		goto fun_end;

    if (executeArgs == NULL && keywordArgs != NULL)
    {       
        executeArgs = keywordArgs;
        Py_INCREF(executeArgs);
    }
    
    DMPYTHON_TRACE_INFO(dpy_trace(statement, executeArgs, "ENTER Cursor_Execute,before Cursor_Execute_inner\n"));

    retObject       = Cursor_Execute_inner(self, statement, executeArgs, 0, 0, 0);
    Py_CLEAR(executeArgs);

fun_end:

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, NULL, "EXIT Cursor_Execute, %s\n", retObject == NULL ? "FAILED" : "SUCCESS"));

    return retObject;
}

static
PyObject*
Cursor_nextset_inner(
    dm_Cursor*     self
)
{
    DPIRETURN       rt = DSQL_SUCCESS;

    rt      = dpi_more_results(self->handle);
    if (!DSQL_SUCCEEDED(rt) && rt != DSQL_NO_DATA)
    {
        Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, rt,"Cursor_nextset_inner()");        

        return NULL;
    }

    if (rt == DSQL_NO_DATA)
    {
        Py_RETURN_NONE;
    }

    Py_RETURN_TRUE;
}

static
PyObject*
Cursor_nextset_Inner_ex(
    dm_Cursor*     self
)
{    
    PyObject*       ret;    

    /** 清除上次执行结果 **/
    Cursor_ExecRs_Clear(self);

    /** 清除列描述 **/
    Cursor_free_coldesc(self);

    /** 判断是否还存在结果集，若无，或者失败，则直接返回 **/
    ret     = Cursor_nextset_inner(self);
    if (!ret || ret == Py_None)
        return ret;
    
    /** 存在结果集 **/
    if (Cursor_PerformDefine(self, NULL) < 0)
        return NULL;

    if (Cursor_SetRowCount(self) < 0)
        return NULL;

    Py_RETURN_TRUE;
}

static
PyObject*
Cursor_nextset(
    dm_Cursor*     self
)
{
    PyObject*       retObj;

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, NULL, "ENTER Cursor_nextset\n"));

    retObj          = Cursor_nextset_Inner_ex(self);

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, NULL, "EXIT Cursor_nextset, %s\n", retObj == NULL ? "FAILED" : "SUCCESS"));

    return retObj;
}

/************************************************************************
purpose:
    Cursor_ContextManagerEnter()
    Called when the cursor is used as a context manager and simply returns it
    to the caller.
************************************************************************/
static
PyObject*       /*返回py对象*/
Cursor_ContextManagerEnter(
    dm_Cursor*  cursor,     /*IN:cursor*/
    PyObject*   args        /*IN:args*/
)
{
    Py_INCREF(cursor);
    return (PyObject*) cursor;
}

/************************************************************************
purpose:
    Cursor_ContextManagerExit()
    Called when the cursor is used as a context manager and simply closes the
    cursor.
************************************************************************/
static
PyObject*       /*返回py对象*/
Cursor_ContextManagerExit(
    dm_Cursor*  cursor,     /*IN:cursor*/
    PyObject*   args        /*IN:args*/
)
{
    PyObject *excType, *excValue, *excTraceback, *result;

    if (!PyArg_ParseTuple(args, "OOO", &excType, &excValue, &excTraceback))
        return NULL;
    result = Cursor_Close(cursor);
    if (!result)
        return NULL;
    Py_DECREF(result);
    Py_INCREF(Py_False);
    return Py_False;
}

static 
PyObject*
Cursor_ExecuteMany(
    dm_Cursor*      self, 
    PyObject*       args
)
{
	PyObject*       statement;
    PyObject*       argsList;
    PyObject*       rowParams;
    PyObject*       retObj = NULL;

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_ExecuteMany\n"));

	if (!PyArg_ParseTuple(args, "OO", &statement, &argsList))
		return NULL;
    
    DMPYTHON_TRACE_INFO(dpy_trace(statement, argsList, "ENTER Cursor_ExecuteMany, after parse args\n"));

	if (PyIter_Check(argsList))
	{	
        Py_INCREF(Py_None);
        retObj      = Py_None;

		while(1)
		{
			rowParams = PyIter_Next(argsList);
			if (rowParams == NULL)
				break;

            Py_XDECREF(retObj);
            retObj  = Cursor_Execute_inner(self, statement, rowParams, 0, 0, 0);

            DMPYTHON_TRACE_INFO(dpy_trace(statement, rowParams, "ENTER Cursor_ExecuteMany, Cursor_Execute_inner Per Row, %s\n", retObj == NULL ? "FAILED" : "SUCCESS"));

            if (retObj == NULL)
            {
                Py_DECREF(rowParams);
                return NULL;
            }

			Py_DECREF(rowParams);
		}
        
        return retObj;
	}
	
    retObj  = Cursor_Execute_inner(self, statement, argsList, 1, 0, 0);

    DMPYTHON_TRACE_INFO(dpy_trace(statement, argsList, "ENTER Cursor_ExecuteMany, Cursor_Execute_inner Per Row, %s\n", retObj == NULL ? "FAILED" : "SUCCESS"));

    return retObj;
}

static 
PyObject*
Cursor_Prepare(
    dm_Cursor*      self, 
    PyObject*       args
)
{
	PyObject*   	statement = NULL;
    PyObject*       ret_obj = NULL;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_Prepare\n"));

	// statement text and optional tag is expected	
	if (!PyArg_ParseTuple(args, "O", &statement))
		goto fun_end;

	// make sure the cursor is open
	if (Cursor_IsOpen(self) < 0)
		goto fun_end;

    self->execute_num   += 1;
    
    DMPYTHON_TRACE_INFO(dpy_trace(statement, NULL, "ENTER Cursor_Prepare,before Cursor_InternalPrepare\n"));

	// prepare the statement
	if (Cursor_InternalPrepare(self, statement) < 0)
		goto fun_end;

	Py_INCREF(Py_None);	
    ret_obj     = Py_None;

fun_end:

    DMPYTHON_TRACE_INFO(dpy_trace(statement, NULL, "EXIT Cursor_Prepare, %s\n", ret_obj == NULL ? "FAILED" : "SUCCESS"));

    return ret_obj;
}

static 
sdint2
Cursor_FixupBoundCursor(
    dm_Cursor*         self
)
{
	if (self->handle && self->statementType < 0)
	{
        Cursor_ExecRs_Clear(self);

		if (Cursor_GetStatementType(self) < 0)
			return -1;

		if (Cursor_PerformDefine(self, NULL) < 0)
			return -1;

		if (Cursor_SetRowCount(self) < 0)
			return -1;
	}

	return 0;
}

static 
sdint2
Cursor_VerifyFetch(
    dm_Cursor*     self
)
{
	if (Cursor_IsOpen(self) < 0)
		return -1;

	if (Cursor_FixupBoundCursor(self) < 0)
		return -1;

	if (self->colCount <= 0)
	{
		PyErr_SetString(g_InterfaceErrorException, "not a query");
		return -1;
	}
	
	return 0;
}

static 
sdint2
Cursor_InternalFetch(
    dm_Cursor*     self
)  
{
    DPIRETURN       status = DSQL_SUCCESS;
    ulength         rowCount;
    ulength         realToGet;
    ulength         rowleft;
    int             i;
    dm_Var*         var;
    ulength         array_size;

    if (!self->colCount || self->col_variables == NULL) 
    {
        PyErr_SetString(g_InterfaceErrorException, "query not executed");
        return -1;
    }

    /** fetch之前可能又重新设置了arraysize **/
    if ((int)self->arraySize < 0 || self->arraySize > ULENGTH_MAX)
    {
        PyErr_SetString(g_ErrorException, "Invalid cursor arraysize\n");
        return -1;
    }

    /** 避免fetch之前又重新设置了arraysize **/
    array_size      = self->arraySize;
    if (self->arraySize > self->org_arraySize)
    {
        array_size  = self->org_arraySize;
    }

    rowleft         = (ulength)(self->totalRows - self->rowCount);   
    /** 取两者之间较小的 **/
	realToGet       = array_size < rowleft ? array_size : rowleft;    

    for (i = 0; i < PyList_GET_SIZE(self->col_variables); i ++)
    {
        var = (dm_Var*) PyList_GET_ITEM(self->col_variables, i);

        var->internalFetchNum++;
        if (var->type->preFetchProc) 
        {
            if ((*var->type->preFetchProc)(var, self->hdesc_col, i + 1) < 0)
                return -1;
        }
    }

    Py_BEGIN_ALLOW_THREADS	
		status = dpi_set_stmt_attr(self->handle, DSQL_ATTR_ROW_ARRAY_SIZE, (dpointer)realToGet, sizeof(realToGet));
	Py_END_ALLOW_THREADS

	if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, status,
		"Cursor_InternalFetch(): dpi_set_stmt_attr") < 0)
		return -1;

	Py_BEGIN_ALLOW_THREADS
		status = dpi_fetch(self->handle, &rowCount);
    Py_END_ALLOW_THREADS
    if (status != DSQL_NO_DATA) {
        if (Environment_CheckForError(self->environment, self->handle, DSQL_HANDLE_STMT, status,
                "Cursor_InternalFetch(): fetch") < 0)
            return -1;
    }

	self->rowNum = 0;
	self->actualRows = rowCount - self->rowNum;

    return 0;
}

static 
sdint2
Cursor_MoreRows(
    dm_Cursor*     self
)
{
    /*初始化为-1*/
	if (self->actualRows == (ulength)(-1) ||  
        self->rowNum >= self->actualRows)
	{
		if (self->rowCount >= self->totalRows)
			return 0;

		if (self->actualRows == (ulength)(-1) || self->rowNum == self->actualRows)
			if (Cursor_InternalFetch(self) < 0)
				return -1;		
	}
	
	return 1;
}

//-----------------------------------------------------------------------------
// Cursor_CreateRow()
//   Create an object for the row. The object created is a tuple unless a row
// factory function has been defined in which case it is the result of the
// row factory function called with the argument tuple that would otherwise be
// returned.
//-----------------------------------------------------------------------------
/*static 
PyObject*
Cursor_CreateRow(
	dm_Cursor*      self                   // cursor object
)
{
	PyObject*       item;
	int             numItems, pos;
	PyObject**      apValues;
    dm_Var*         dm_var;

	// create a new tuple
	numItems = self->colCount;
	apValues = PyMem_Malloc(sizeof(PyObject*) * numItems);
	if (!apValues)
		return PyErr_NoMemory();

	// acquire the value for each item
	for (pos = 0; pos < numItems; pos++) 
    {
        dm_var     = (dm_Var*)PyList_GET_ITEM(self->col_variables, pos);
        if (dm_var != NULL)
        {
            item    = dmVar_GetValue(dm_var, self->rowNum);		
        }
        
		if (dm_var == NULL || item == NULL)
		{
			FreeRowValues(pos, apValues);
			return NULL;
		}

		apValues[pos] = item;
	}

	// increment row counters
	self->rowCount++;
	self->rowNum ++;	

	return (PyObject*)Row_New(self->description, self->map_name_to_index, numItems, apValues);
}*/

static 
PyObject*
Cursor_CreateRow_AsTuple(
	dm_Cursor*      self                   // cursor object
)
{
    PyObject*       item;
    PyObject*       tuple;
    int             numItems, pos;
    dm_Var*         dm_var;

    // create a new tuple
    numItems    = self->colCount;
    tuple       = PyTuple_New(numItems);
    if (tuple == NULL)
        return NULL;

    // acquire the value for each item
    for (pos = 0; pos < numItems; pos++) 
    {
        dm_var     = (dm_Var*)PyList_GET_ITEM(self->col_variables, pos);
        if (dm_var != NULL)
        {
            item    = dmVar_GetValue(dm_var, self->rowNum);		
        }

        if (dm_var == NULL || item == NULL)
        {
            Py_XDECREF(tuple);
            return NULL;
        }

        PyTuple_SetItem(tuple, pos, item);
    }

    // increment row counters
    self->rowCount++;
    self->rowNum ++;	

    return tuple;
}

static 
PyObject*
Cursor_CreateRow_AsDict(
	dm_Cursor*      self                   // cursor object
)
{
    PyObject*       item = NULL;
    PyObject*       dict = NULL;
    PyObject*       key = NULL;
    int             numItems, pos;
    DmColDesc       *colinfo;
    dm_Var*         dm_var;

    // create a new tuple
    numItems    = self->colCount;

    dict        = PyDict_New();
    if (dict == NULL)
        return NULL;

    // acquire the value for each item
    for (pos = 0; pos < numItems; pos++) 
    {
        dm_var     = (dm_Var*)PyList_GET_ITEM(self->col_variables, pos);
        if (dm_var != NULL)
        {
            item    = dmVar_GetValue(dm_var, self->rowNum);		
        }

        if (dm_var == NULL || item == NULL)
        {
            Py_XDECREF(dict);
            return NULL;
        }

        colinfo     = &self->bindColDesc[pos];

        key         = dmString_FromEncodedString(colinfo->name, strlen(colinfo->name), self->environment->encoding);

        PyDict_SetItem(dict, key, item);

        /* PyDict_SetItem会使index,key的内存计数加1，循环里index,key只用一次，用完需主动内存计数减1 */
        Py_DECREF(item);
        Py_XDECREF(key);
    }

    // increment row counters
    self->rowCount++;
    self->rowNum ++;	

    return dict;
}

PyObject *
Cursor_One_Fetch(
	dm_Cursor*     self
)
{
	sdint4	rt;
	
	rt = Cursor_MoreRows(self);
	if (rt < 0)
		return NULL;
	else if (rt > 0)
    {
        if (self->connection->cursor_class == DICT_CURSOR)
        {
            return Cursor_CreateRow_AsDict(self);
        }
        else
        {
            return Cursor_CreateRow_AsTuple(self); /*BUG553553调整为返回tuple*/
        }
    }

	Py_INCREF(Py_None);
	return Py_None;
}


PyObject*
Cursor_Many_Fetch(
	dm_Cursor*      self,
	ulength			rowSize
)
{
	ulength		index;
	PyObject	*list, *tuple;

	list = PyList_New(rowSize);
	for (index = 0; index < rowSize; index ++){
		tuple = Cursor_One_Fetch(self);
		if (tuple == NULL){
			Py_DECREF(list);
			return NULL;
		}

		PyList_SET_ITEM(list, index, tuple);
	}

	//Py_INCREF(list);
	return list;
}


static 
PyObject*
Cursor_FetchOne(
    dm_Cursor*      self, 
    PyObject*       args
)
{
    PyObject*       ret_obj = NULL;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_FetchOne\n"));

	if (Cursor_VerifyFetch(self) < 0)
		goto fun_end;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_FetchOne,before Cursor_One_Fetch\n"));

	ret_obj         = Cursor_One_Fetch(self);

fun_end:
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "EXIT Cursor_FetchOne, %s\n", ret_obj == NULL ? "FAILED" : "SUCCESS"));

    return ret_obj;
}

static 
PyObject*
Cursor_FetchMany(
    dm_Cursor*      self, 
    PyObject*       args, 
    PyObject*       keywords
)
{
    static char*    keywordList[] = { "rows", NULL };
    ulength		    rowToGet;
    ulength         rowleft;
    Py_ssize_t      inputRow = self->arraySize;
    PyObject*       ret_obj = NULL;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_FetchMany\n"));

	if (Cursor_VerifyFetch(self) < 0)
		goto fun_end;

    if (!PyArg_ParseTupleAndKeywords(args, keywords, "|i", keywordList, &inputRow))
        goto fun_end;

	if (inputRow < 0 || inputRow >= INT_MAX)
    {
		PyErr_SetString(g_InterfaceErrorException, "Invalid rows value");
		goto fun_end;
	}	

    /* 输入rows小于未获取行数rowleft，则返回rows行数据，否则返回剩余所有行 */
    rowleft     = (ulength)(self->totalRows - self->rowCount);
	rowToGet    = (ulength)inputRow < rowleft ? (ulength)inputRow : rowleft;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_FetchMany,before Cursor_Many_Fetch rowleft ["slengthprefix"], rowToGet ["slengthprefix"]\n", rowleft, rowToGet));
	
    ret_obj     = Cursor_Many_Fetch(self, rowToGet);

fun_end:
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "EXIT Cursor_FetchMany, %s\n", ret_obj == NULL ? "FAILED" : "SUCCESS"));

    return ret_obj;
}

static
PyObject*
Cursor_FetchAll(
    dm_Cursor*      self, 
    PyObject*       args
)
{
	ulength		    rowToGet;
    PyObject*       ret_obj = NULL;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_FetchAll\n"));

	if (Cursor_VerifyFetch(self) < 0)
		goto fun_end;

	rowToGet    = (ulength)(self->totalRows - self->rowCount);
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_FetchAll,before Cursor_Many_Fetch rowToGet ["slengthprefix"]\n", rowToGet));

	ret_obj     = Cursor_Many_Fetch(self, rowToGet);

fun_end:

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "EXIT Cursor_FetchAll, %s\n", ret_obj == NULL ? "FAILED" : "SUCCESS"));

    return ret_obj;
}

static
PyObject*
Cursor_GetIter(
    dm_Cursor*     self
)
{
	if (Cursor_VerifyFetch(self) < 0)
		return NULL;

    self->is_iter   = 1;

	Py_INCREF(self);
	return (PyObject*)self;
}

static 
PyObject*
Cursor_GetNext_Inner(
    dm_Cursor*     self
)
{
	PyObject		*retObj;

	if (Cursor_VerifyFetch(self) < 0)
		return NULL;

	retObj = Cursor_One_Fetch(self);

    if (retObj != Py_None)
    {
        return retObj;
    }

    //PyErr_SetString(PyExc_StopIteration, "No data");

    if (self->is_iter == 1)
    {
        self->is_iter   = 0;

        return NULL;
    }
    else
    {
        Py_RETURN_NONE;
    }
}

static 
PyObject*
Cursor_GetNext(
    dm_Cursor*     self
)
{
    PyObject*       retObj;

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, NULL, "ENTER Cursor_GetNext\n"));

    retObj      = Cursor_GetNext_Inner(self);

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, NULL, "EXIT Cursor_GetNext\n"));

    return retObj;
}

static
udint4
Cursor_CalcStmtSize(
    dm_Cursor*      self,
    char*           procName,
    udint4          paramCount,
    udbyte          ret_value   /** 0：无返回值；1：有返回值 **/
)
{
    /************************************************************************/
    /* 语句块格式：
    /* begin
    /* ? = func(); ==>存储函数
    /*  proc();     ==>存储过程
    /* end;
    /************************************************************************/
    udint4          size = 20; /** = 5(begin)+2('"''"') + 1(' ') + 3('('')'';') + 1(' ') + 4(end;) **/
    
    if (ret_value != 0)
    {
        size    += 4; /** '?'' ''='' '**/
    }

    size        += (udint4)strlen(procName);

    if (paramCount > 0)
    {
        size    += paramCount;      /*?*/
        size    += (paramCount - 1);/*,*/ 
        size    += (paramCount - 1);/*' '*/
    }

    return size;
}

sdint4 Cursor_escape_quotes(char* dst, int dst_len, char* src, int src_len)
{
    char* to_start = dst;
    char* end = NULL;
    char* to_end = to_start + (dst_len ? dst_len - 1 : 2 * src_len);
    int		overflow = 0;

    for (end = src + src_len; src < end; src++)
    {
        if (*src == '\"')
        {
            if (dst + 2 > to_end)
            {
                overflow = 1;
                break;
            }
            *dst++ = '\"';
            *dst++ = '\"';
        }
        else
        {
            if (dst + 1 > to_end)
            {
                overflow = 1;
                break;
            }
            *dst++ = *src;
        }
    }
    *dst = 0;

    return overflow ? -1 : (int)(dst - to_start);
}

static
PyObject*
Cursor_MakeStmtSQL(
    dm_Cursor*      self,
	char*           procName,
	udint4          paramCount,
    udbyte          ret_value   /** 0：无返回值；1：有返回值 **/
)
{
    udint4          sql_len;
    sdbyte*         sql = NULL;	
	udint4	        iparam;
    PyObject*       sql_obj;
    char*           pos = NULL;

    sql_len = Cursor_CalcStmtSize(self, procName, paramCount, ret_value);
    sql     = PyMem_Malloc(sql_len + 1); /* 预留结尾符 */
    if (sql == NULL)
    {
        return PyErr_NoMemory();
    }

    sprintf(sql, "begin ");
    
    if (ret_value != 0)
    {
        strcat(sql, "? = ");
    }

    strcat(sql, "\"");
    pos = strstr(procName, ".");
    if(pos == NULL)
    {
        strcat(sql, procName);
        strcat(sql, "\"");
    }
    else
    {
        *pos = 0;
        strcat(sql, procName);
        strcat(sql, "\".\"");
        strcat(sql, pos + 1);
        strcat(sql, "\"");
        *pos = '.';
    }

    strcat(sql, "(");	
	for (iparam = 0; iparam < paramCount; iparam ++)
	{
		if (iparam != paramCount -1)
			strcat(sql, "?, ");
		else
			strcat(sql, "?");
	}
	strcat(sql, "); end;");

	sql_obj = dmString_FromAscii(sql);

    PyMem_Free(sql);

    return sql_obj;
}


PyObject*
Cursor_MakeupProcParams(
	dm_Cursor*     self
)
{
	sdint4		iparam;
    sdint4      paramCount = self->paramCount;	
	PyObject*   paramVal;
    PyObject*   newParamVal;
    PyObject*   paramsRet;
    sdint4      ioutparam  = 0;

	paramsRet = PyList_New(paramCount);
    if(self->output_stream != 1)
    { 
	    for (iparam = 0; iparam < paramCount; iparam ++)
	    {
            paramVal    = PyList_GET_ITEM(self->param_variables, iparam);
            if (paramVal == NULL)
            {
                Py_DECREF(paramsRet);
                return NULL;
            }       

            /** 若是OBJECT类型的输入或者输入输出参数，则直接返回绑定时的对象引用 **/
            if (((dm_Var*)paramVal)->type->pythonType == &g_ObjectVarType &&
                self->bindParamDesc[iparam].param_type == DSQL_PARAM_INPUT)
            {
                newParamVal = ObjectVar_GetBoundExObj((dm_ObjectVar*)paramVal, 0);
            }
            else
            {
                newParamVal = dmVar_GetValue((dm_Var*)paramVal, 0);
            }
            if (newParamVal == NULL)
            {
                Py_DECREF(paramsRet);
                return NULL;
            }

		    PyList_SetItem(paramsRet, iparam, newParamVal);
	    }
    }
    else
    {
        for (iparam = 0; iparam < paramCount; iparam++)
        {
            paramVal = PyList_GET_ITEM(self->param_variables, iparam);
            if (paramVal == NULL)
            {
                Py_DECREF(paramsRet);
                return NULL;
            }

            /** 若是OBJECT类型的输入或者输入输出参数，则直接返回绑定时的对象引用 **/
            if (((dm_Var*)paramVal)->type->pythonType == &g_ObjectVarType &&
                self->bindParamDesc[iparam].param_type == DSQL_PARAM_INPUT)
            {
                newParamVal = ObjectVar_GetBoundExObj((dm_ObjectVar*)paramVal, 0);
            }
            else if (self->bindParamDesc[iparam].param_type == DSQL_PARAM_OUTPUT)
            {
                if(self->param_value == NULL || self->param_value[ioutparam] == NULL)
                    newParamVal = Py_None;
                else
                    newParamVal = self->param_value[ioutparam];
                ioutparam++;
            }
            else
            {
                newParamVal = dmVar_GetValue((dm_Var*)paramVal, 0);
            }
            if (newParamVal == NULL)
            {
                Py_DECREF(paramsRet);
                return NULL;
            }

            PyList_SetItem(paramsRet, iparam, newParamVal);
        }
        if (self->param_value)
        {
            PyMem_Free(self->param_value);
            self->param_value = NULL;
        }
            
    }
		
	return paramsRet;
}

static
PyObject*
Cursor_CallExec_inner(
    dm_Cursor*      self, 
    PyObject*       args, 
    udint4          ret_value   /* 是否需要返回值 */
)
{
    PyObject*       nameObj = NULL;
    PyObject*       parameters = NULL;
    PyObject*       sql = NULL;    
    char*           procName = NULL;
    Py_ssize_t      paramCount = 0;
    dm_Buffer       buffer;  
    PyObject*       retObj = NULL;

    if (Cursor_ParseArgs(args, &nameObj, &parameters) < 0)
        return NULL;

    if (nameObj == NULL || nameObj == Py_None)
    {
        PyErr_SetString(g_InterfaceErrorException, "procedure name is illegal");
        return NULL;
    }

    // 计算名称	
    if (dmBuffer_FromObject(&buffer, nameObj, self->environment->encoding) < 0)
        return NULL;

    procName = PyMem_Malloc(buffer.size * 2 + 1);
    if (procName == NULL)
    {
        PyErr_NoMemory();
        return NULL;
    }

    Cursor_escape_quotes(procName, buffer.size * 2 + 1, buffer.ptr, buffer.size);
    dmBuffer_Clear(&buffer);    

    // 计算绑定参数个数
    if (parameters != NULL)
        paramCount = PySequence_Size(parameters);
    else
        paramCount = 0;	

    // 构造SQL语句
    sql = Cursor_MakeStmtSQL(self, procName, (udint4)paramCount, ret_value);
    PyMem_Free(procName);

    if (ret_value != 0)
    {
        /** 若需要返回值，插入None到parameters的第一个位置 **/
        //Py_XINCREF(parameters);

        if (parameters == NULL || parameters == Py_None)
        {            
            parameters  = PyList_New(1);

            /* PyList_SetItem:“steals” a reference to item，
            此处Py_None在代码块内其他地方引用计数没有累加过，
            因此需要主动加1，避免parameters清理的时候把系统变量PyNone多清理1次  */
            Py_INCREF(Py_None);
            PyList_SetItem(parameters, 0, Py_None);
        }
        else
        {
            PyList_Insert(parameters, 0, Py_None);            
        }        
    }

    /** 执行 **/
    retObj  = Cursor_Execute_inner(self, sql, parameters, 0, 0, 1);
    Py_CLEAR(sql);
    Py_CLEAR(parameters);
    
    return retObj;
}

static 
PyObject*
Cursor_CallProc(
    dm_Cursor*      self, 
    PyObject*       args
)
{
    PyObject*       retObj;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_CallProc\n"));

	retObj  = Cursor_CallExec_inner(self, args, 0);

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "EXIT Cursor_CallProc, %s\n", retObj == NULL ? "FAILED" : "SUCCESS"));

    return retObj;
}

static 
PyObject*
Cursor_CallFunc(
    dm_Cursor*      self, 
    PyObject*       args
)
{
    PyObject*       retObj;

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_CallFunc\n"));

	retObj      = Cursor_CallExec_inner(self, args, 1);

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "EXIT Cursor_CallFunc, %s\n", retObj == NULL ? "FAILED" : "SUCCESS"));

    return retObj;
}

static
PyObject*
Cursor_GetDescription(
	dm_Cursor   *self,
    void*       args
)
{
	PyObject*           desc = NULL;
    PyObject*           coldesc = NULL;
    dm_VarType*         varType = NULL;
    PyObject*           typecode = NULL;
    PyObject*           colmap = NULL;
    PyObject*           index = NULL;
    PyObject*           colname_arr = NULL;
    PyObject*           colname = NULL;
	DmColDesc           *colinfo;
	sdint2		        icol;
    PyObject*           retObj = NULL;
    PyObject*           key = NULL;

    if (Cursor_IsOpen(self) < 0)
    {
        return NULL;
    }

    if (Cursor_FixupBoundCursor(self) < 0)
    {
        return NULL;
    }

    if (self->colCount <= 0)
    {
        Py_INCREF(Py_None);
        return Py_None;
    }

    if (self->description != Py_None)
    {
        Py_INCREF(self->description);
        return self->description;
    }

    colname_arr = PyList_New(self->colCount);
	desc        = PyList_New(self->colCount);
	colmap      = PyDict_New();
	for (icol = 0; icol < self->colCount; icol ++)
	{
		colinfo = &self->bindColDesc[icol];

		// 标准中要求7个描述信息：name,type_code,display_size ,internal_size, precision, scale, null_ok
        varType = dmVar_TypeBySQLType(colinfo->sql_type, 0);
        if (varType == NULL)
        {
            goto done;
        }
        typecode    = (PyObject*)varType->pythonType;

        colname     = dmString_FromEncodedString(colinfo->name, strlen(colinfo->name), self->environment->encoding);
        if (colname == NULL)
        {
            PyErr_SetString(g_OperationalErrorException, "NULL String");
            goto done;
        }          
        
        coldesc     = Py_BuildValue("(OOiiiii)",
                                colname,            
                                typecode,
                                colinfo->display_size,
                                colinfo->prec,
                                colinfo->prec,            
                                colinfo->scale,            
                                colinfo->nullable);

        /* Py_BuildValue会使colname内存计数多加1次，colname只用一次，用完需主动减1 */
        Py_XDECREF(colname);

        if (colinfo == NULL)
        {
            goto done;
        }

		// map_name_to_index
#if PY_MAJOR_VERSION < 3
		index = PyInt_FromLong(icol);
#else
        index = PyLong_FromLong(icol);
#endif
		if (!index)
        {
			goto done;
        }

        key             = dmString_FromEncodedString(colinfo->name, strlen(colinfo->name), self->environment->encoding);

		PyDict_SetItem(colmap, 
                       key,
                       index);
        /* PyDict_SetItem会使index,key的内存计数加1，循环里index,key只用一次，用完需主动内存计数减1 */
		Py_DECREF(index);       // SetItemString increments
        Py_XDECREF(key);
        index           = NULL;

		PyList_SetItem(desc, icol, coldesc);
		coldesc         = NULL;            // reference stolen by SET_ITEM
        //Py_XDECREF(coldesc);

        PyList_SetItem(colname_arr, 
                       icol, 
                       dmString_FromEncodedString(colinfo->name, strlen(colinfo->name), self->environment->encoding));
	}

	Py_XDECREF(self->description);
	self->description = desc;
	desc    = NULL;

    Py_XDECREF(self->map_name_to_index);
	self->map_name_to_index = colmap;
	colmap  = NULL;

    Py_XDECREF(self->column_names);
    self->column_names  = colname_arr;
    colname_arr = NULL;

done:

    Py_INCREF(self->description);
	retObj  = self->description;

	return retObj;
}

static 
PyObject*
Cursor_Parse(
    dm_Cursor*      self, 
    PyObject*       args
)
{
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_Parse, NOT support\n"));

	PyErr_SetString(g_NotSupportedErrorException, "not support");
	return NULL;
}

static 
PyObject*
Cursor_SetInputSizes_inner(
    dm_Cursor*      self,
    PyObject*       args,
    PyObject*       keywords
)
{
    int             numArgs;
    int             numkeywordArgs=0;
    PyObject*       value;
    dm_Var*         var;
    Py_ssize_t      i;
    PyObject*       key;

    // make sure the cursor is open
    if (Cursor_IsOpen(self) < 0)
        return NULL;

    // eliminate existing bind variables
    Py_CLEAR(self->param_variables);

    // if number of argument is 0, then return None;else create a new one
    numArgs = PyTuple_Size(args);
    // 如果存在keywords，计算keywords的数量
    if (keywords)
        numkeywordArgs = PyDict_Size(keywords);
    // args与keywords不能同时存在
    if (numArgs > 0 && numkeywordArgs>0)
        Py_RETURN_NONE;
    // 如果都不存在返回空
    if (numArgs == 0 && numkeywordArgs == 0)
    {
        return NULL;
    }
    // 如果keywords存在创建字典，否则创建链表
    if (numkeywordArgs > 0)
        self->param_variables = PyDict_New();
    else
        self->param_variables   = PyList_New(numArgs);
    if (self->param_variables == NULL)
        return NULL;

    if ((sdint4)self->bindArraySize < 0 ||
        self->bindArraySize > ULENGTH_MAX)
    {
        PyErr_SetString(g_ProgrammingErrorException, 
            "invalid value of bindarraysize");

        return NULL;
    }
    
    // set the flag of inputSize 1
    self->setInputSizes     = 1;

    // process each input
    if (numkeywordArgs > 0)
    {
        i = 0;
        // 依次处理keywords
        while (PyDict_Next(keywords, &i, &key, &value))
        {
            var = dmVar_NewByType(self, value, self->bindArraySize);
            if (!var)
                return NULL;
            //构造新的字典键值对加入字典
            if (PyDict_SetItem(self->param_variables, key, (PyObject*)var) < 0)
            {
                Py_DECREF(var);
                return NULL;
            }
            Py_DECREF(var);
        }
    }
    else
    {
        for (i = 0; i < numArgs; i++)
        {
            value = PyTuple_GET_ITEM(args, i);
            if (value == Py_None)
            {
                Py_INCREF(Py_None);
                PyList_SET_ITEM(self->param_variables, i, Py_None);
            }
            else
            {
                var = dmVar_NewByType(self, value, self->bindArraySize);
                if (!var)
                    return NULL;
                PyList_SET_ITEM(self->param_variables, i, (PyObject*)var);
            }
        }
    }
    self->org_bindArraySize = self->bindArraySize;

    Py_INCREF(self->param_variables);
    return self->param_variables;
}

static 
PyObject*
Cursor_SetInputSizes(
    dm_Cursor*      self,
    PyObject*       args,
    PyObject*       keywords
)
{
    PyObject*       ret_obj;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_SetInputSizes\n"));

    ret_obj         = Cursor_SetInputSizes_inner(self, args, keywords);
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "EXIT Cursor_SetInputSizes, %s\n", ret_obj == NULL ? "FAILED" : "SUCCESS"));

    return ret_obj;
}

static 
PyObject*
Cursor_SetOutputSize_inner(
    dm_Cursor*      self, 
    PyObject*       args
)
{
    self->outputSizeColumn = -1;
    if (!PyArg_ParseTuple(args, "i|i", &self->outputSize,
        &self->outputSizeColumn))
        return NULL;

    Py_INCREF(Py_None);
    return Py_None;
}

static 
PyObject*
Cursor_SetOutputSize(
    dm_Cursor*      self, 
    PyObject*       args
)
{
    PyObject*       retObj;

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_SetOutputSize\n"));

    retObj      = Cursor_SetOutputSize_inner(self, args);

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "EXIT Cursor_SetOutputSize, %s\n", retObj == NULL ? "FAILED" : "SUCCESS"));

    return retObj;
}

static 
PyObject*
Cursor_Var(
    dm_Cursor*      self, 
    PyObject*       args, 
    PyObject*       keywords
)
{
    PyObject*           retObj = NULL;
    dm_VarType*         varType;

    static char *keywordList[] = { "typ", "size", "arraysize", "inconverter",
        "outconverter", "typename", "encoding_errors", "bypass_decode",
        "encodingErrors", NULL };

    Py_ssize_t encodingErrorsLength, encodingErrorsDeprecatedLength;
    const char *encodingErrors, *encodingErrorsDeprecated;
    PyObject *inConverter, *outConverter, *typeNameObj;
    int size, arraySize, bypassDecode;
    PyObject *type;
    dm_Var *var = NULL;

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_Var\n"));

    //参数解析
    size                = 0;
    bypassDecode        = 0;
    arraySize           = self->arraySize;
    encodingErrors      = NULL;
    encodingErrorsDeprecated = NULL;
    inConverter         = NULL;
    outConverter        = NULL;
    typeNameObj         = NULL;

    if (!PyArg_ParseTupleAndKeywords(args, keywords, "O|iiOOOz#pz#",
        keywordList, &type, &size, &arraySize, &inConverter, &outConverter,
        &typeNameObj, &encodingErrors, &encodingErrorsLength,
        &bypassDecode, &encodingErrorsDeprecated,
        &encodingErrorsDeprecatedLength))
        return NULL;

    varType = dmVar_TypeByPythonType(self, type);
    
    if (varType != NULL)
    {
        var = dmVar_NewByVarType(self, varType, 1, varType->size);
    }

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "EXIT Cursor_Var, %s\n", var == NULL ? "FAILED" : "SUCCESS"));

    retObj = (PyObject*)(var);

    return retObj;
}

static 
PyObject*
Cursor_ArrayVar(
    dm_Cursor*      self, 
    PyObject*       args
)
{
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_ArrayVar Not Support\n"));

	PyErr_SetString(g_NotSupportedErrorException, "not support");
	return NULL;
}

static 
PyObject*
Cursor_BindNames(
    dm_Cursor*      self,
    PyObject*       args
)
{
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Cursor_BindNames Not Support\n"));

	PyErr_SetString(g_NotSupportedErrorException, "not support");
	return NULL;
}

//-----------------------------------------------------------------------------
// declaration of methods for Python type "Cursor"
//-----------------------------------------------------------------------------
static PyMethodDef g_CursorMethods[] = {
    { "execute",        (PyCFunction) Cursor_Execute,           METH_VARARGS | METH_KEYWORDS},
    { "executedirect",  (PyCFunction) Cursor_ExecuteDirect,     METH_VARARGS},
    { "fetchall",       (PyCFunction) Cursor_FetchAll,          METH_NOARGS },
    { "fetchone",       (PyCFunction) Cursor_FetchOne,          METH_NOARGS },
    { "fetchmany",      (PyCFunction) Cursor_FetchMany,         METH_VARARGS | METH_KEYWORDS },
    { "prepare",        (PyCFunction) Cursor_Prepare,           METH_VARARGS },
    { "parse",          (PyCFunction) Cursor_Parse,             METH_VARARGS },
    { "setinputsizes",  (PyCFunction) Cursor_SetInputSizes,     METH_VARARGS | METH_KEYWORDS },
    { "executemany",    (PyCFunction) Cursor_ExecuteMany,       METH_VARARGS },
    { "callproc",       (PyCFunction) Cursor_CallProc,          METH_VARARGS},
    { "callfunc",       (PyCFunction) Cursor_CallFunc,          METH_VARARGS},
    { "setoutputsize",  (PyCFunction) Cursor_SetOutputSize,     METH_VARARGS },
    { "var",            (PyCFunction) Cursor_Var,               METH_VARARGS | METH_KEYWORDS },
    { "arrayvar",       (PyCFunction) Cursor_ArrayVar,          METH_VARARGS },
    { "bindnames",      (PyCFunction) Cursor_BindNames,         METH_NOARGS },
    { "close",          (PyCFunction) Cursor_Close,             METH_NOARGS },
    { "next",           (PyCFunction) Cursor_GetNext,           METH_NOARGS },
    { "nextset",        (PyCFunction) Cursor_nextset,           METH_NOARGS },
    { "__enter__",      (PyCFunction) Cursor_ContextManagerEnter, METH_NOARGS },
    { "__exit__",       (PyCFunction) Cursor_ContextManagerExit,METH_VARARGS },
    { NULL,             NULL }
};


//-----------------------------------------------------------------------------
// declaration of members for Python type "Cursor"
//-----------------------------------------------------------------------------
static PyMemberDef g_CursorMembers[] = {
    { "arraysize",      T_INT,          offsetof(dm_Cursor, arraySize),        0 },
    { "bindarraysize",  T_INT,          offsetof(dm_Cursor, bindArraySize),    0 },
    { "rowcount",       T_INT,          offsetof(dm_Cursor, totalRows),        READONLY },  /** 结果集总行数 **/
    { "rownumber",      T_INT,          offsetof(dm_Cursor, rowCount),         READONLY },   /** 游标所在当前位置0-based **/
    { "with_rows",      T_BOOL,         offsetof(dm_Cursor, with_rows),        READONLY },   /** 游标所在当前位置0-based **/
    { "statement",      T_OBJECT,       offsetof(dm_Cursor, statement),        READONLY },
    { "connection",     T_OBJECT_EX,    offsetof(dm_Cursor, connection),       READONLY },       
    { "column_names",   T_OBJECT_EX,    offsetof(dm_Cursor, column_names),     READONLY },
    { "lastrowid",      T_OBJECT,       offsetof(dm_Cursor, lastrowid_obj),    RESTRICTED },
    { "execid",         T_OBJECT,       offsetof(dm_Cursor, execid_obj),       READONLY },
    { "_isClosed",      T_INT,          offsetof(dm_Cursor, isClosed),         READ_RESTRICTED },
    { "_statement",     T_OBJECT,       offsetof(dm_Cursor, statement),        READ_RESTRICTED },
    { "output_stream",  T_INT,          offsetof(dm_Cursor, output_stream),    0 },
    { NULL }
};


//-----------------------------------------------------------------------------
// declaration of calculated members for Python type "Connection"
//-----------------------------------------------------------------------------
static PyGetSetDef g_CursorCalcMembers[] = {
    { "description",            (getter) Cursor_GetDescription, 0,  0,  0},
    { NULL }
};


//-----------------------------------------------------------------------------
// declaration of Python type "Cursor"
//-----------------------------------------------------------------------------
PyTypeObject g_CursorType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "DmdbCursor",                     // tp_name
    sizeof(dm_Cursor),                  // tp_basicsize
    0,                                  // tp_itemsize
    (destructor) Cursor_Free,           // tp_dealloc
    0,                                  // tp_print
    0,                                  // tp_getattr
    0,                                  // tp_setattr
    0,                                  // tp_compare
    (reprfunc) Cursor_Repr,             // tp_repr
    0,                                  // tp_as_number
    0,                                  // tp_as_sequence
    0,                                  // tp_as_mapping
    0,                                  // tp_hash
    0,                                  // tp_call
    0,                                  // tp_str
    0,                                  // tp_getattro
    0,                                  // tp_setattro
    0,                                  // tp_as_buffer
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    // tp_flags
    0,                                  // tp_doc
    0,                                  // tp_traverse
    0,                                  // tp_clear
    0,                                  // tp_richcompare
    0,                                  // tp_weaklistoffset
    (getiterfunc) Cursor_GetIter,       // tp_iter
    (iternextfunc) Cursor_GetNext,      // tp_iternext
    g_CursorMethods,                    // tp_methods
    g_CursorMembers,                    // tp_members
    g_CursorCalcMembers,                // tp_getset
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