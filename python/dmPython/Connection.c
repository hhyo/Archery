//-----------------------------------------------------------------------------
// Connection.c
//   Definition of the Python type DmConnection.
//-----------------------------------------------------------------------------
#include "py_Dameng.h"
#include "Error.h"
#include "Buffer.h"
#include "trc.h"
//-----------------------------------------------------------------------------
// Constants for the Python type "Connection" Attributes
//-----------------------------------------------------------------------------
static	udint4		gc_attr_access_mode		= DSQL_ATTR_ACCESS_MODE;
static  udint4      gc_attr_async_enalbe    = DSQL_ATTR_ASYNC_ENABLE;
static  udint4      gc_attr_auto_ipd        = DSQL_ATTR_AUTO_IPD;
static	udint4		gc_attr_autocommit		= DSQL_ATTR_AUTOCOMMIT;
static	udint4		gc_attr_conn_dead		= DSQL_ATTR_CONNECTION_DEAD;
static	udint4		gc_attr_conn_timeout	= DSQL_ATTR_CONNECTION_TIMEOUT;
static	udint4		gc_attr_login_timeout	= DSQL_ATTR_LOGIN_TIMEOUT;
static	udint4		gc_attr_packet_size		= DSQL_ATTR_PACKET_SIZE;
static	udint4		gc_attr_txn_isolation	= DSQL_ATTR_TXN_ISOLATION;
static	udint4		gc_attr_login_port		= DSQL_ATTR_LOGIN_PORT;
static	udint4		gc_attr_str_case_sencitive	= DSQL_ATTR_STR_CASE_SENSITIVE;                                                                          
static	udint4		gc_attr_max_row_size	= DSQL_ATTR_MAX_ROW_SIZE;
static	udint4		gc_attr_login_user		= DSQL_ATTR_LOGIN_USER;
static	udint4		gc_attr_login_server	= DSQL_ATTR_LOGIN_SERVER;
static	udint4		gc_attr_instance_name	= DSQL_ATTR_INSTANCE_NAME;
static	udint4		gc_attr_current_schema	= DSQL_ATTR_CURRENT_SCHEMA;
static	udint4		gc_attr_server_code		= DSQL_ATTR_SERVER_CODE;
static  udint4      gc_attr_local_code      = DSQL_ATTR_LOCAL_CODE;
static  udint4      gc_attr_lang_id         = DSQL_ATTR_LANG_ID;
static	udint4		gc_attr_app_name		= DSQL_ATTR_APP_NAME;
static	udint4		gc_attr_compres_msg		= DSQL_ATTR_COMPRESS_MSG;
static  udint4      gc_attr_rwseparate      = DSQL_ATTR_RWSEPARATE;
static  udint4      gc_attr_rwseparate_percent  = DSQL_ATTR_RWSEPARATE_PERCENT;
static  udint4      gc_attr_current_catalog = DSQL_ATTR_CURRENT_CATALOG;
static  udint4      gc_attr_trx_state       = DSQL_ATTR_TRX_STATE;
static  udint4      gc_attr_use_stmt_pool   = DSQL_ATTR_USE_STMT_POOL;
static	udint4		gc_attr_ssl_path		= DSQL_ATTR_SSL_PATH;
static  udint4      gc_attr_mpp_login       = DSQL_ATTR_MPP_LOGIN;
static	udint4		gc_attr_server_version	= DSQL_ATTR_SERVER_VERSION;
static  udint4      gc_attr_cursor_rollback_behavior = DSQL_ATTR_CURSOR_ROLLBACK_BEHAVIOR;

/* 不可读取，只允许设置 */
static	udint4		gc_attr_ssl_pwd			= DSQL_ATTR_SSL_PWD;
static  udint4      gc_attr_ukey_name       = DSQL_ATTR_UKEY_NAME;
static  udint4      gc_attr_ukey_pin        = DSQL_ATTR_UKEY_PIN;

/* dpi未支持 */
static	udint4		gc_attr_trace			= DSQL_ATTR_TRACE;
static	udint4		gc_attr_trace_file		= DSQL_ATTR_TRACEFILE;


//-----------------------------------------------------------------------------
// functions for the Python type "Connection"
//-----------------------------------------------------------------------------

static
void
Connection_init_inner(
    dm_Connection*     self
)
{
    Py_INCREF(Py_None);
    self->environment   = (dm_Environment *)Py_None;

    Py_INCREF(Py_None);
    self->username      = Py_None;

    Py_INCREF(Py_None);
    self->schema        = Py_None;

    Py_INCREF(Py_None);
    self->password      = Py_None;

    Py_INCREF(Py_None);
    self->server        = Py_None;

    Py_INCREF(Py_None);
    self->port          = Py_None;	

    Py_INCREF(Py_None);
    self->dsn           = Py_None;

    Py_INCREF(Py_None);
    self->inputTypeHandler  = Py_None;

    Py_INCREF(Py_None);
    self->outputTypeHandler = Py_None;

    Py_INCREF(Py_None);
    self->version           = Py_None;

    Py_INCREF(Py_None);
    self->server_status     = Py_None;    

    Py_INCREF(Py_None);
    self->warning           = Py_None;

    Py_INCREF(Py_None);
    self->catalog           = Py_None;

    self->isConnected       = 0;
}



static
void
Connection_Free_inner(
    dm_Connection*     self
)
{
    Py_CLEAR(self->username);
    Py_CLEAR(self->password);
    Py_CLEAR(self->server);
    Py_CLEAR(self->port);
    Py_CLEAR(self->dsn);
    Py_CLEAR(self->inputTypeHandler);	
    Py_CLEAR(self->outputTypeHandler);
    Py_CLEAR(self->environment);
    Py_CLEAR(self->server_status);    
    Py_CLEAR(self->warning);
    Py_CLEAR(self->catalog);
    Py_CLEAR(self->version);
}

//-----------------------------------------------------------------------------
// Connection_SplitComponent()
//   Split the component out of the source and replace the source with the
// characters up to the split string and put the characters after the split
// string in to the target.
//-----------------------------------------------------------------------------
static 
int 
Connection_SplitComponent(
    PyObject**      sourceObj,               // source object to split
    PyObject**      targetObj,               // target object (for component)
    const char*     splitString              // split string (assume one character)
) 
{
    char*           source_str = NULL;
    char*           target_str = NULL;
    char*           pos = NULL;	
    
    if (*sourceObj == Py_None || *targetObj != Py_None || splitString == NULL)
        return 0;

    Py_INCREF(*sourceObj);
    source_str  = py_String_asString(*sourceObj);

    if (PyErr_Occurred())
    {
        return -1;
    }

    if (source_str == NULL || target_str != NULL)
    {
        return 0;
    }

    if (strcmp(splitString, ":") == 0)
    {
        pos = strstr(source_str, "]");
        if (pos == NULL)
            pos = strstr(source_str, splitString);
        else
            pos = strstr(pos, splitString);
    }
    else
        pos = strstr(source_str, splitString);

    if (pos == NULL)
    {
        return 0;
    }

    *pos = 0;

    *sourceObj  = Py_BuildValue("s", source_str);
    if(strcmp(splitString,"?catalog=") == 0)
        *targetObj = Py_BuildValue("s", pos + 9);
    else
        *targetObj  = Py_BuildValue("s", pos + 1);

    //还原pos处的内容
    *pos = *splitString;

    return 1;
}

//-----------------------------------------------------------------------------
// Connection_IsConnected()
//   Determines if the connection object is connected to the database. If not,
// a Python exception is raised.
//-----------------------------------------------------------------------------
static int Connection_IsConnected_without_err(
    dm_Connection*     self        // connection to check
)              
{
	if (!self->hcon) 
    {		
		return -1;
	}

	return 0;
}

static int Connection_IsConnected(
    dm_Connection*     self        // connection to check
)              
{
    if (Connection_IsConnected_without_err(self) < 0)
	{
		PyErr_SetString(g_InterfaceErrorException, "not connected");
		return -1;
	}

	return 0;
}

static int Connection_IsLogin(
    dm_Connection*      self,  // connection to check
	sdint2              isRaiseExcepiton
)               
{
	if (!self->isConnected)
	{
		if (isRaiseExcepiton)
			PyErr_SetString(g_InterfaceErrorException, "not login");

		return -1;
	}

	return 0;
}

static
PyObject*
Connection_Debug_inner(
    dm_Connection*      self,
    PyObject*           args
)
{
    udint4              debug_type;
    dhstmt              hstmt;
    sdbyte              sql_txt[128];
    DPIRETURN           rt = DSQL_SUCCESS;
    Py_ssize_t          num = 0;

    // make sure we are connected
    if (Connection_IsConnected(self) < 0)
    {
        PyErr_SetString(g_ErrorException, "not connected");
        
        Py_INCREF(Py_None);
        return Py_None;
    }

    // 若未登录，则直接返回
    if (Connection_IsLogin(self, 0) < 0)
    {
        PyErr_SetString(g_ErrorException, "not login");

        Py_INCREF(Py_None);
        return Py_None;
    }

    num = PyTuple_Size(args);
    if (num == 0)
    {
        //没有指定参数，使用默认值
        debug_type = DEBUG_OPEN;
    }
    else
    {
        // parse the arguments
        if (!PyArg_ParseTuple(args, "i", &debug_type))
        {
            PyErr_SetString(g_ErrorException, "invalid arguments");
            return NULL;
        }
    }
    
    if (debug_type < 0 || debug_type > 3)
    {
        PyErr_SetString(g_ErrorException, "invalid arguments");
        return NULL;
    }
    
    // 申请语句句柄
    Py_BEGIN_ALLOW_THREADS
        rt = dpi_alloc_stmt(self->hcon, &hstmt);	
    Py_END_ALLOW_THREADS

    if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt, "Connection_Debug():dpi_alloc_stmt") < 0)
        return NULL;

    sprintf(sql_txt, "SP_SET_PARA_VALUE(1, 'SVR_LOG', %d)", debug_type);

    Py_BEGIN_ALLOW_THREADS
        rt = dpi_exec_direct(hstmt, sql_txt);
        dpi_free_stmt(hstmt);
    Py_END_ALLOW_THREADS

    if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt, "Connection_Debug():dpi_exec_direct") < 0)
        return NULL;	

    Py_INCREF(Py_None);
    return Py_None;
}

static
PyObject*
Connection_Debug(
    dm_Connection*      self,
    PyObject*           args
)
{
    PyObject*           rt_obj;

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Connect_Debug\n"));

    rt_obj      = Connection_Debug_inner(self, args);
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "EXIT Connect_Debug, %s\n", rt_obj == NULL ? "FAILED" : "SUCCESS"));

    return rt_obj;
}

static
PyObject*
Connection_Shutdown_inner(
    dm_Connection*      self,
    PyObject*           args
)
{
    char*               shutdown_type;
    dhstmt              hstmt;
    sdbyte              sql_txt[128];
    DPIRETURN           rt = DSQL_SUCCESS;
    Py_ssize_t          num = 0;

    // make sure we are connected
    if (Connection_IsConnected(self) < 0)
    {
        PyErr_SetString(g_ErrorException, "not connected");

        Py_INCREF(Py_None);
        return Py_None;
    }

    // 若未登录，则直接返回
    if (Connection_IsLogin(self, 0) < 0)
    {
        PyErr_SetString(g_ErrorException, "not login");

        Py_INCREF(Py_None);
        return Py_None;
    }

    num = PyTuple_Size(args);
    if (num == 0)
    {
        //没有指定参数，使用default值
        shutdown_type = SHUTDOWN_DEFAULT;
    }
    else
    {
        // parse the arguments
        if (!PyArg_ParseTuple(args, "s", &shutdown_type))
        {
            PyErr_SetString(g_ErrorException, "invalid arguments");
            return NULL;
        }
    }    

    // 申请语句句柄
    Py_BEGIN_ALLOW_THREADS
        rt = dpi_alloc_stmt(self->hcon, &hstmt);	
    Py_END_ALLOW_THREADS

    if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt, "Connection_Debug():dpi_alloc_stmt") < 0)
        return NULL;

    sprintf(sql_txt, "SHUTDOWN %s", shutdown_type);

    Py_BEGIN_ALLOW_THREADS
        rt = dpi_exec_direct(hstmt, sql_txt);
        dpi_free_stmt(hstmt);
    Py_END_ALLOW_THREADS

        if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt, "Connection_Debug():dpi_exec_direct") < 0)
            return NULL;	

    Py_INCREF(Py_None);
    return Py_None;
}

static
PyObject*
Connection_Shutdown(
    dm_Connection*      self,
    PyObject*           args
)
{
    PyObject*           rt_obj;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Connect_Shutdown\n"));

    rt_obj      = Connection_Shutdown_inner(self, args);
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "Exit Connect_Shutdown, %s\n", rt_obj == NULL ? "FAILED" : "SUCCESS"));    

    return rt_obj;
}

static
PyObject*
Connection_Close_inner(
    dm_Connection*      self
)
{
	DPIRETURN status = DSQL_SUCCESS;
    sdint4    is_active;
	// make sure we are connected
	if (Connection_IsConnected(self) < 0)
    {
        PyErr_Clear();
		goto fun_end;
    }

	// 若未登录，则直接返回
	if (Connection_IsLogin(self, 0) < 0)
    {
        goto fun_end;
	}
    Py_BEGIN_ALLOW_THREADS
        dpi_get_con_attr(self->hcon, DSQL_ATTR_CONNECTION_DEAD, &is_active, sizeof(sdint4), NULL);
    Py_END_ALLOW_THREADS
        if (is_active != DSQL_CD_TRUE)
            // perform a rollback
        {
            Py_BEGIN_ALLOW_THREADS
                status = dpi_rollback(self->hcon);
            Py_END_ALLOW_THREADS

                if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, status,
                    "Connection_Close(): rollback") < 0)
                    return NULL;
        }
	// logout of the server		
	Py_BEGIN_ALLOW_THREADS
		status = dpi_logout(self->hcon);
	Py_END_ALLOW_THREADS
	if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, status,
		"Connection_Close(): logout") < 0)
		return NULL;	

fun_end:

	// free handle
	if (self->hcon)
    {
		Py_BEGIN_ALLOW_THREADS
			dpi_free_con(self->hcon);
		Py_END_ALLOW_THREADS
		self->hcon = NULL;
	}

    Connection_Free_inner(self);

    /** 便于最后一个引用释放之前访问 **/
    Connection_init_inner(self);

	Py_INCREF(Py_None);
	return Py_None;
}

static
PyObject*
Connection_Close(
    dm_Connection*      self
)
{
    PyObject*           rt_obj;

    DMPYTHON_TRACE_INFO(dpy_trace(NULL, NULL, "ENTER Connect_Close\n"));

    rt_obj      = Connection_Close_inner(self);
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, NULL, "ENTER Connect_Close, %s\n", rt_obj == NULL ? "FAILED" : "SUCCESS"));

    return rt_obj;
}

static
PyObject*
Connection_Commit_inner(
    dm_Connection*      self, 
    PyObject*			args
 )
{
	DPIRETURN rt = DSQL_SUCCESS;

	// make sure we are acturally connected
	if (Connection_IsConnected(self) < 0)
		return NULL;

	// 若未登录，则直接返回
	if (Connection_IsLogin(self, 0) < 0){
		Py_INCREF(Py_None);
		return Py_None;
	}

	// perform a commit operation
	Py_BEGIN_ALLOW_THREADS
		rt = dpi_commit(self->hcon);
	Py_END_ALLOW_THREADS
		if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
			"Connection_Commit()") < 0)
		return NULL;

	Py_INCREF(Py_None);
	return Py_None;
}

static
PyObject*
Connection_Commit(
    dm_Connection*      self, 
    PyObject*			args
 )
{
    PyObject*           rt_obj;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Connect_Commit\n"));

    rt_obj      = Connection_Commit_inner(self, args);
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "EXIT Connect_Commit, %s\n", rt_obj == NULL ? "FAILED" : "SUCCESS"));

    return rt_obj;
}


static
PyObject*
Connection_Rollback_inner(
    dm_Connection*      self, 
    PyObject*			args
 )
{
	DPIRETURN rt = DSQL_SUCCESS;

	// make sure we are acturally connected
	if (Connection_IsConnected(self) < 0)
		return NULL;

	// 若未登录，则直接返回
	if (Connection_IsLogin(self, 0) < 0){
		Py_INCREF(Py_None);
		return Py_None;
	}

	// perform the rollback operation
	Py_BEGIN_ALLOW_THREADS
		rt = dpi_rollback(self->hcon);
	Py_END_ALLOW_THREADS
		if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
			"Connection_Rollback") < 0)
			return NULL;
		
	Py_INCREF(Py_None);
	return Py_None;
}

static
PyObject*
Connection_Rollback(
    dm_Connection*      self, 
    PyObject*			args
 )
{
    PyObject*           rt_obj;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Connect_Rollback\n"));

    rt_obj      = Connection_Rollback_inner(self, args);
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "EXIT Connect_Rollback, %s\n", rt_obj == NULL ? "FAILED" : "SUCCESS"));

    return rt_obj;
}

static PyObject	*Connection_GetConAttr(
    dm_Connection*      self,    // connection
	sdint4*             attr_id		// attribute type
)
{
	DPIRETURN	rt = DSQL_SUCCESS;
	sdint4		len;
	sdint4		int4Value;
    sdint2      int2Value;
    udint4      uint4Value;
	sdbyte		strValue[500];
    PyObject*   retObj = NULL;    

	// check if connected
	if (Connection_IsConnected(self) < 0)
	{
		return NULL;
	}

	switch(*attr_id){
		case DSQL_ATTR_ACCESS_MODE:
		case DSQL_ATTR_ASYNC_ENABLE:
		case DSQL_ATTR_AUTO_IPD:
		case DSQL_ATTR_AUTOCOMMIT:
		case DSQL_ATTR_CONNECTION_DEAD:
        case DSQL_ATTR_CONNECTION_TIMEOUT:
		case DSQL_ATTR_LOGIN_TIMEOUT:
		case DSQL_ATTR_PACKET_SIZE:
		case DSQL_ATTR_TXN_ISOLATION:		
		case DSQL_ATTR_MAX_ROW_SIZE:		
		case DSQL_ATTR_LANG_ID:
        case DSQL_ATTR_LOCAL_CODE:
		case DSQL_ATTR_SERVER_CODE:
		case DSQL_ATTR_USE_STMT_POOL:
		case DSQL_ATTR_COMPRESS_MSG:
        case DSQL_ATTR_RWSEPARATE:
        case DSQL_ATTR_RWSEPARATE_PERCENT:
        case DSQL_ATTR_TRX_STATE:
        case DSQL_ATTR_MPP_LOGIN:
        case DSQL_ATTR_CURSOR_ROLLBACK_BEHAVIOR:

			Py_BEGIN_ALLOW_THREADS
				rt  = dpi_get_con_attr(self->hcon, *attr_id, (dpointer)(&int4Value), 0, &len);
			Py_END_ALLOW_THREADS

                if (DSQL_SUCCEEDED(rt))
                {                    
                    return Py_BuildValue("i", int4Value);
                }

			break;

        case DSQL_ATTR_LOGIN_PORT:            

            Py_BEGIN_ALLOW_THREADS
                rt  = dpi_get_con_attr(self->hcon, *attr_id, (dpointer)(&int2Value), 0, &len);
            Py_END_ALLOW_THREADS

                if (DSQL_SUCCEEDED(rt))
                {
                    return Py_BuildValue("i", int2Value);
                }

                break; 

        case DSQL_ATTR_STR_CASE_SENSITIVE:            

            Py_BEGIN_ALLOW_THREADS
                rt  = dpi_get_con_attr(self->hcon, *attr_id, (dpointer)(&uint4Value), 0, &len);
            Py_END_ALLOW_THREADS

                if (DSQL_SUCCEEDED(rt))
                {
                    return Py_BuildValue("i", uint4Value);
                }

            break;         

		default:               

			Py_BEGIN_ALLOW_THREADS
				rt = dpi_get_con_attr(self->hcon, *attr_id, strValue, 500, &len);
			Py_END_ALLOW_THREADS

                if (DSQL_SUCCEEDED(rt))
                {
                    return dmString_FromEncodedString(strValue, strlen(strValue), self->environment->encoding);                    
                }

			break;

	}

	Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt, "Connection_GetConAttr()");
	return NULL;    
}


static int	Connection_SetConAttr(
    dm_Connection*          self,   // connection
    PyObject*               value,   // attribute value to set
    sdint4*                 attr_id	 // attribute type
){
	DPIRETURN	rt = DSQL_SUCCESS;
	long		numValue;
	char*		strValue;
	sdint4		val_len = 0;
	sdint2		isNumVal = 0;     // 是否为数字值，0 否 1 是
	dm_Buffer   buffer;
    sdint4      lang_id;

	// check attributes
	switch(*attr_id){
		case DSQL_ATTR_ACCESS_MODE:
		case DSQL_ATTR_ASYNC_ENABLE:
		case DSQL_ATTR_AUTO_IPD:
		case DSQL_ATTR_AUTOCOMMIT:
		case DSQL_ATTR_CONNECTION_DEAD:
        case DSQL_ATTR_CONNECTION_TIMEOUT:         
		case DSQL_ATTR_LOGIN_TIMEOUT:
		case DSQL_ATTR_PACKET_SIZE:
		case DSQL_ATTR_TXN_ISOLATION:
		case DSQL_ATTR_LOGIN_PORT:
		case DSQL_ATTR_STR_CASE_SENSITIVE:
		case DSQL_ATTR_MAX_ROW_SIZE:
		case DSQL_ATTR_LOCAL_CODE:
		case DSQL_ATTR_LANG_ID:
		case DSQL_ATTR_SERVER_CODE:
		case DSQL_ATTR_USE_STMT_POOL:
		case DSQL_ATTR_COMPRESS_MSG:
        case DSQL_ATTR_RWSEPARATE:
        case DSQL_ATTR_RWSEPARATE_PERCENT:
			isNumVal = 1;
			break;

		default:
			isNumVal = 0;
			break;
	}	
	
	// parse arguements by attribute type
	if (isNumVal)  // 数字
	{		
#if PY_MAJOR_VERSION >= 3
        if (!PyLong_Check(value))
        {
            PyErr_SetString(PyExc_TypeError, "Invalid attribute value to set, expecting integer value");
            return -1;
        }

        numValue    = PyLong_AsUnsignedLong(value);
        if (numValue < 0)
        {
            return -1;
        }

        if (numValue > INT_MAX)
        {
            PyErr_SetString(PyExc_OverflowError, "Invalid attribute value to set, the value is overflow");
            return -1;
        }
#else
        if (!PyInt_Check(value))
        {
            PyErr_SetString(PyExc_TypeError, "Invalid attribute value to set, expecting integer value");
            return -1;
        }

        numValue = PyInt_AsUnsignedLongMask(value);
        if (numValue < 0 || numValue > INT_MAX)
        {
            PyErr_SetString(PyExc_OverflowError, "Invalid attribute value to set, the value is overflow");
            return -1;
        }
#endif  
        if (*attr_id == DSQL_ATTR_LOCAL_CODE)
        {
            if (numValue != PG_UTF8 && numValue != PG_GBK && numValue != PG_BIG5 && numValue != PG_GB18030)
            {
                lang_id = LANGUAGE_EN;
                if (lang_id != self->environment->local_langid)
                {
                    PyErr_SetString(PyExc_TypeError, "Invalid attribute value to set, this value only can be used when lang_id = LANGUAGE_EN");
                    return -1;
                }
            }
        }

		Py_BEGIN_ALLOW_THREADS
			rt = dpi_set_con_attr(self->hcon, *attr_id, (dpointer)numValue, val_len);
		Py_END_ALLOW_THREADS
	}	
	else
	{
		if (!py_String_Check(value))
		{
			PyErr_SetString(PyExc_TypeError, "Invalid attribute value to set, expecting  string value");
			return -1;
		}

		if(dmBuffer_FromObject(&buffer, value, self->environment->encoding) < 0)
			return -1;

		strValue = PyMem_Malloc(buffer.size + 1);
		strcpy(strValue, buffer.ptr);
		dmBuffer_Clear(&buffer);		

		Py_BEGIN_ALLOW_THREADS
			rt = dpi_set_con_attr(self->hcon, *attr_id, strValue, (sdint4)strlen(strValue));
		Py_END_ALLOW_THREADS
		PyMem_Free(strValue);
	}

	if(Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt, 
		"Connection_SetConAttr()") < 0)
		return -1;

    /** 若设置LOCAL_CODE或者LANG_ID成功，则更新当前使用的环境对象的上编码方式 **/
    if (*attr_id == DSQL_ATTR_LOCAL_CODE)
    {
        Environment_refresh_local_code(self->environment, self->hcon, self->environment->local_code);
    }

    if (*attr_id == DSQL_ATTR_LANG_ID)
    {
        Environment_refresh_local_langid(self->environment, self->hcon, self->environment->local_langid);
    }

	
	return 0;
}

static 
int
Connection_Free(
    dm_Connection*      self    // connection itself               
)
{		
    if (Connection_IsConnected_without_err(self) >= 0)    
        Connection_Close(self);

    Connection_Free_inner(self);

	Py_TYPE(self)->tp_free((PyObject*) self);	

	return 0;
}


static
PyObject*
Connection_New(
    PyTypeObject*       type,     // object type 
    PyObject*           args,	  // arguments
    PyObject*           keywords  // keywords 
)
{
	dm_Connection *self;

	// create the object
	self = (dm_Connection*) type->tp_alloc(type, 0);
	if (!self)
		return NULL;	

	self->environment = NULL;
	self->isConnected = 0;

	return (PyObject*) self;
}

/* 获取server_status字符串 */
static
void
Connection_make_svrstat(
    dm_Connection*     self    
)
{
    char                print_info[1024];
    PyObject*           format = NULL;
    PyObject*           formatArgs = NULL;    

    dpi_get_diag_field(DSQL_HANDLE_DBC, self->hcon, 0, DSQL_DIAG_SERVER_STAT, print_info, sizeof(print_info), NULL);
    
    self->server_status = dmString_FromEncodedString(print_info, strlen(print_info), self->environment->encoding);
}

static
int
Connection_connect_inner(
    dm_Connection*     self
)
{
	DPIRETURN		rt = DSQL_SUCCESS;				// 返回值	
	dm_Buffer       buffer;
	//char			*server, *username, *password;
    char            server[256];
    char            username[256];
    char            password[256];
    char            catalog[256];
    char            server_str[512];
	sdint4			attr_id;        

	if(dmBuffer_FromObject(&buffer, self->server, self->environment->encoding) < 0)
		return -1;
	//server = PyMem_Malloc(buffer.size + 1);
	strcpy(server, buffer.ptr);
	dmBuffer_Clear(&buffer);

	if(dmBuffer_FromObject(&buffer, self->username, self->environment->encoding) < 0)
    {     
		return -1;
    }
	strcpy(username, buffer.ptr);
	dmBuffer_Clear(&buffer);

	if(dmBuffer_FromObject(&buffer, self->password, self->environment->encoding) < 0)
    {
		return -1;
    }
	strcpy(password, buffer.ptr);
	dmBuffer_Clear(&buffer);

    if(self->catalog != Py_None)
    {
        if (dmBuffer_FromObject(&buffer, self->catalog, self->environment->encoding) < 0)
        {
            return -1;
        }
        strcpy(catalog, buffer.ptr);
        dmBuffer_Clear(&buffer);

        sprintf(server_str, "%s/%s", server, catalog);
        // 连接数据库服务器
        Py_BEGIN_ALLOW_THREADS
            rt = dpi_login(self->hcon, server_str, username, password);
        Py_END_ALLOW_THREADS
    }
    else
    {
	    // 连接数据库服务器
	    Py_BEGIN_ALLOW_THREADS
		    rt = dpi_login(self->hcon, server, username, password);
	    Py_END_ALLOW_THREADS
    }
	if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt, 
		"Connection_connect():Connect to db server") < 0)
		return -1;

	// 读取是否自动提交属性，以及访问模式属性
	attr_id = DSQL_ATTR_AUTOCOMMIT;
	if (!Connection_GetConAttr(self, &attr_id))
		return -1;

	attr_id = DSQL_ATTR_ACCESS_MODE;
	if (!Connection_GetConAttr(self, &attr_id))
		return -1;

    /* 连接成功后，获取server_status串 */
    Connection_make_svrstat(self);

	self->isConnected = 1;

    return 0;
}

static
int
Connection_connect(
    dm_Connection*     self
)
{
    int                 rt;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, NULL, "ENTER Connect_connect\n"));

    rt          = Connection_connect_inner(self);
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, NULL, "EXIT Connect_connect, %s\n", rt < 0 ? "FAILED" : "SUCCESS"));

    return rt;
}


static
PyObject*
Connection_Ping_inner(
    dm_Connection*      self,
    PyObject*           args

 )
{
    DPIRETURN       rt = DSQL_SUCCESS;
    int             rt1;
    sdint4          is_active;
    dm_Buffer       buffer;
    char            server[256];
    char            username[256];
    char            password[256];
    sdint4          reconnect;//reconnect=0 不进行重连，reconnect=1 进行重连。
    sdint4          num;
    // make sure we are acturally connected
    if (Connection_IsConnected(self) < 0)
        return NULL;

    // 若未登录，则直接返回
    if (Connection_IsLogin(self, 0) < 0){
        return NULL;
    }
    num = PyTuple_Size(args);
    if (num == 0)
    {
        //没有指定参数，使用默认值
        reconnect = 0;
    }
    else
    {
        // parse the arguments
        if (!PyArg_ParseTuple(args, "i", &reconnect))
        {
            PyErr_SetString(g_ErrorException, "invalid arguments");
            return NULL;
        }
    }

    if (reconnect < 0 || reconnect > 1)
    {
        PyErr_SetString(g_ErrorException, "invalid arguments");
        return NULL;
    }


    // perform a commit operation
    Py_BEGIN_ALLOW_THREADS
        rt = dpi_get_con_attr(self->hcon,DSQL_ATTR_CONNECTION_DEAD, &is_active, sizeof(sdint4), NULL);
    Py_END_ALLOW_THREADS
        if (is_active == DSQL_CD_TRUE && reconnect == 1)
        {
            Py_BEGIN_ALLOW_THREADS
                rt = dpi_logout(self->hcon);
            Py_END_ALLOW_THREADS

            if (dmBuffer_FromObject(&buffer, self->server, self->environment->encoding) < 0)
                return NULL;
            strcpy(server, buffer.ptr);
            dmBuffer_Clear(&buffer);

            if (dmBuffer_FromObject(&buffer, self->username, self->environment->encoding) < 0)
            {
                return NULL;
            }
            strcpy(username, buffer.ptr);
            dmBuffer_Clear(&buffer);

            if (dmBuffer_FromObject(&buffer, self->password, self->environment->encoding) < 0)
            {
                return NULL;
            }
            strcpy(password, buffer.ptr);
            dmBuffer_Clear(&buffer);

            // 连接数据库服务器
            Py_BEGIN_ALLOW_THREADS
                rt = dpi_login(self->hcon, server, username, password);
            Py_END_ALLOW_THREADS
                if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                    "Connection_connect():Connect to db server") < 0)
                    return NULL;
        }         
        else if (is_active == DSQL_CD_TRUE)
            return NULL;
    Py_INCREF(Py_None);
    return Py_None;
} 

static
PyObject*
Connection_Ping(
    dm_Connection*      self, 
    PyObject*			args
 )
{
    PyObject*           rt_obj;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Connect_Ping\n"));

    rt_obj      = Connection_Ping_inner(self, args);
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "EXIT Connect_Ping, %s\n", rt_obj == NULL ? "FAILED" : "SUCCESS"));

    return rt_obj;
}
/************************************************************************
purpose:
    Connection_ContextManagerEnter()
    Called when the connection is used as a context manager and simply returns
    itconn as a convenience to the caller.
************************************************************************/
static
PyObject*
Connection_ContextManagerEnter(
    dm_Connection*      conn,
    PyObject*           args
)
{
    if (Connection_IsConnected(conn) < 0)
        return NULL;
    Py_INCREF(conn);
    return (PyObject*) conn;
}

/************************************************************************
purpose:
    Connection_ContextManagerExit()
    Called when the connection is used as a context manager and if any
    exception a rollback takes place; otherwise, a commit takes place.
************************************************************************/
static 
PyObject*
Connection_ContextManagerExit(
    dm_Connection*      conn,
    PyObject*           args
)
{
    PyObject *excType, *excValue, *excTraceback, *result;

    if (!PyArg_ParseTuple(args, "OOO", &excType, &excValue, &excTraceback))
        return NULL;

    result = Connection_Close(conn);
    if (!result)
        return NULL;
    Py_DECREF(result);

    Py_INCREF(Py_False);
    return Py_False;
}

static
void
Connection_makedsn(
    dm_Connection*     self    
)
{
    PyObject*   format = NULL;
    PyObject*   formatArgs = NULL;    

    format      = dmString_FromAscii("%s:%i");
    formatArgs  = PyTuple_Pack(2, self->server,self->port);
    self->dsn   = PyUnicode_Format(format, formatArgs);

    Py_XDECREF(format);
    Py_XDECREF(formatArgs);
}

/************************************************************************
purpose:
    初始化连接
************************************************************************/
static
sdint2
Connection_Init(
    dm_Connection*      self,               /*IN:连接对象*/
    PyObject*			args,               /*IN:参数*/
    PyObject            *keywordArgs        /*IN:连接属性*/
)
{
	DPIRETURN		rt = DSQL_SUCCESS;				// 返回值	
	PyObject*       username_obj = NULL;
    PyObject*       schema_obj = NULL;
    PyObject*       password_obj = NULL;
    PyObject*       host_obj = NULL;
    PyObject*       server_obj = NULL;
    PyObject*       port_obj = NULL;
    PyObject*       dsn_obj = NULL;
    PyObject*       accessmode_obj = NULL;
    PyObject*       autocommit_obj = NULL;
    PyObject*       conn_timeout_obj = NULL;
    PyObject*       login_timeout_obj = NULL;             
    PyObject*       cursor_rollback_obj = NULL;    
    PyObject*       tmp_port_obj = Py_None;
    PyObject*       txn_isolation_obj = NULL;
    PyObject*       cmpress_msg_obj = NULL;
    PyObject*       stmt_pool_obj = NULL;
    PyObject*       mpp_login_obj = NULL;
    PyObject*       rwseparate_obj = NULL;
    PyObject*       rwseparate_percent_obj = NULL;
    PyObject*       lang_id_obj = NULL;
    PyObject*       local_code_obj = NULL;
    PyObject*       cursor_class_obj = NULL;
    PyObject*       catalog_obj = NULL;

    char*           username_def = "SYSDBA";
    char*           host_def = "localhost";
	udint4          port = DSQL_DEAFAULT_TCPIP_PORT;
    udint4          mode = DSQL_MODE_DEFAULT;
    udint4          autocommit = DSQL_AUTOCOMMIT_DEFAULT;
    udint4          conn_timeout = 1000;
    udint4          login_timeout = 1000;
    sdint4          txn_isolation = -1;
    sdbyte*         app_name = NULL;
    sdint4          cmpress_msg = -1;
    sdint4          stmt_pool = -1;
    char*           ssl_path = NULL;
    char*           ssl_pwd = NULL;
    sdint4          mpp_login = -1;
    char*           ukey_name = NULL;
    char*           ukey_pin = NULL;
    char*           shake_crypto = NULL;
    char*           dmsvc_path = NULL;
    sdint4          rwseparate = -1;
    sdint4          rwseparate_percent = -1;
    udint4          corsor_behavior = DSQL_CB_DEFALUT;    
    sdint4          lang_id = -1;
    sdint4          local_code = -1;
    sdint4          cursor_class = -1;
    char*           end;
    char*           str;    

    // define keyword arguments
    static char *keywordList[] = { "user", "password", "dsn", "host", "server", "port",  
                                    "access_mode", "autoCommit", "connection_timeout", "login_timeout",
                                    "txn_isolation", "app_name",
                                    "compress_msg", "use_stmt_pool", "ssl_path", "ssl_pwd", 
                                    "mpp_login", "ukey_name", "ukey_pin", "rwseparate", 
                                    "rwseparate_percent", "cursor_rollback_behavior", "lang_id", 
                                    "local_code", "cursorclass", "schema", "shake_crypto", "catalog", "dmsvc_path", NULL};

    /** 初始化Connection部分成员变量 **/
    Connection_init_inner(self);

    /** 初始化环境变量 **/
    Py_XDECREF(self->environment);
    self->environment = Environment_New();
    if (!self->environment)
        return -1;	

    /** 初始化环境变量的warning字段 **/
    Py_INCREF(self->warning);
    self->environment->warning = &self->warning;

	// parse arguments
   if (!PyArg_ParseTupleAndKeywords(args, keywordArgs,"|OOOOOOOOOOOsOOssOssOOOOOOOsOs", keywordList,     
        &username_obj, &password_obj, &dsn_obj, &host_obj, &server_obj, &port_obj,  
        &accessmode_obj, &autocommit_obj, &conn_timeout_obj, &login_timeout_obj, 
        &txn_isolation_obj, &app_name, 
        &cmpress_msg_obj, &stmt_pool_obj, &ssl_path, &ssl_pwd, 
        &mpp_login_obj, &ukey_name, &ukey_pin, &rwseparate_obj, 
        &rwseparate_percent_obj, &cursor_rollback_obj, &lang_id_obj, &local_code_obj, &cursor_class_obj, &schema_obj,
        &shake_crypto, &catalog_obj, &dmsvc_path))
        return -1;	      

   /* server和host只允许指定一个 */
   if (host_obj != NULL && server_obj != NULL)
   {
       PyErr_SetString(g_NotSupportedErrorException, "host or server can only set one");
       return -1;
   }

   //keep a copy of schema_obj
   if (schema_obj != NULL)
   {
       Py_XINCREF(schema_obj);
       self->schema = schema_obj;
   }

   if (catalog_obj != NULL)
   {
       Py_XINCREF(catalog_obj);
       self->catalog = catalog_obj;
   }

	// keep a copy of the credentials
    if (username_obj != NULL)
    {
        Py_XINCREF(username_obj);
        self->username = username_obj;

        /* username允许为"user/password@ip:port"形式，分别解析到对应字段上 */
        if (Connection_SplitComponent(&self->username, &self->password, "/") < 0)
            return -1;

        if (Connection_SplitComponent(&self->password, &self->server, "@") < 0)
            return -1;

        if (Connection_SplitComponent(&self->server, &tmp_port_obj, ":") < 0)
            return -1;

        rt = Connection_SplitComponent(&tmp_port_obj, &self->schema, "/");
        if (rt < 0)
            return -1;
        else if (rt == 0)
        {
            rt = Connection_SplitComponent(&tmp_port_obj, &self->catalog, "?catalog=");
            if (rt < 0)
                return -1;
        }
        else
        {
            rt = Connection_SplitComponent(&self->schema, &self->catalog, "?catalog=");
            if (rt < 0)
                return -1;
        }
		
		/* 转换字符串形式的port*/
        if (tmp_port_obj != Py_None)
        {
            str          = py_String_asString(tmp_port_obj);
            if (PyErr_Occurred())
            {
                return -1;
            }
            
#if PY_MAJOR_VERSION < 3
            self->port   = PyInt_FromString(str, &end, 10);
#else
            self->port   = PyLong_FromString(str, &end, 10);
#endif      
            if (PyErr_Occurred())
            {                
                return -1;
            }
        }
    }
    else
    {
        self->username   = Py_BuildValue("s", username_def);
    }

    if (password_obj != NULL)
    {
        /* 如果已从"user/password@ip:port"中解析出password，则不允许再用关键字方式覆盖 */
        if (self->password == Py_None)
        {
            Py_XINCREF(password_obj);
            self->password = password_obj;
        }
    }
    else
    {
        /* 如果没有输入密码则报错 */
        if (self->password == Py_None)
        {
            PyErr_SetString(g_NotSupportedErrorException, "password cannot be empty");
            return -1;
        }
    }

    if (dsn_obj != NULL)
    {
        /* 如果已从"user/password@ip:port"中解析出server，则不允许再用dsn关键字方式覆盖 */
        if (self->server == Py_None)
        {
            Py_XINCREF(dsn_obj);
            self->server = dsn_obj;

            /* dsn为ip:port形式，解析到对应字段去 */
            if (Connection_SplitComponent(&self->server, &tmp_port_obj, ":") < 0)
                return -1;

            /* 转换字符串形式的port*/
            if (tmp_port_obj != Py_None)
            {
                str          = py_String_asString(tmp_port_obj);
                if (PyErr_Occurred())
                {
                    return -1;
                }

#if PY_MAJOR_VERSION < 3
                self->port   = PyInt_FromString(str, &end, 10);
#else
                self->port   = PyLong_FromString(str, &end, 10);
#endif
                if (PyErr_Occurred())
                {
                    return -1;
                }
            }
        }
    }

    /* server和host只允许指定一个 */
    if (host_obj != NULL && self->server == Py_None)
    {
        Py_XINCREF(host_obj);
        self->server = host_obj;
        /* host为ip:port形式，解析到对应字段去 */
        if (Connection_SplitComponent(&self->server, &tmp_port_obj, ":") < 0)
            return -1;

        /* 转换字符串形式的port*/
        if (tmp_port_obj != Py_None)
        {
            str = py_String_asString(tmp_port_obj);
            if (PyErr_Occurred())
            {
                return -1;
            }

#if PY_MAJOR_VERSION < 3
            self->port = PyInt_FromString(str, &end, 10);
#else
            self->port = PyLong_FromString(str, &end, 10);
#endif
            if (PyErr_Occurred())
            {
                return -1;
            }
        }
    }
    else if (server_obj != NULL && self->server == Py_None)
    {
        Py_XINCREF(server_obj);
        self->server = server_obj;
        /* server为ip:port形式，解析到对应字段去 */
        if (Connection_SplitComponent(&self->server, &tmp_port_obj, ":") < 0)
            return -1;

        /* 转换字符串形式的port*/
        if (tmp_port_obj != Py_None)
        {
            str = py_String_asString(tmp_port_obj);
            if (PyErr_Occurred())
            {
                return -1;
            }

#if PY_MAJOR_VERSION < 3
            self->port = PyInt_FromString(str, &end, 10);
#else
            self->port = PyLong_FromString(str, &end, 10);
#endif
            if (PyErr_Occurred())
            {
                return -1;
            }
        }
    }
    else if (self->server == Py_None)
    {
        self->server = Py_BuildValue("s", host_def);
    }

    if (port_obj != NULL && self->port == Py_None)
    {       
        if (py_String_Check(port_obj))
        {
            str = py_String_asString(port_obj);
            if (PyErr_Occurred())
            {
                return -1;
            }

#if PY_MAJOR_VERSION < 3
            self->port   = PyInt_FromString(str, &end, 10);
#else
            self->port   = PyLong_FromString(str, &end, 10);
#endif
            if (PyErr_Occurred())
            {
                return -1;
            }
        }
        else if (PyLong_Check(port_obj))
        {       
            Py_INCREF(port_obj);
            self->port      = port_obj;    
        }
#if PY_MAJOR_VERSION < 3
        else if (PyInt_Check(port_obj))
        {            
            Py_INCREF(port_obj);
            self->port      = port_obj;    
        }
#endif
        else
        {            
            PyErr_SetString(PyExc_TypeError, 
                "port : expecting an Integer or Long value.");
        }
    }
    else
    {
        if (self->port == Py_None)
        {
#if PY_MAJOR_VERSION < 3
            self->port   = Py_BuildValue("i", port);
#else
            self->port   = Py_BuildValue("l", port);
#endif
        }
    }    

    // 申请连接句柄
    Py_BEGIN_ALLOW_THREADS
        rt	= dpi_alloc_con(self->environment->handle, &self->hcon);
    Py_END_ALLOW_THREADS

        if (Environment_CheckForError(self->environment, self->environment->handle, DSQL_HANDLE_ENV, rt,
            "Connection_connect():alloc connection handle") < 0)
        {
            self->hcon = NULL;
            return -1;
        }

        /** 优先判断本地语言和编码方式 **/
        if (lang_id_obj != NULL)
        {
            lang_id = DmIntNumber_AsInt(lang_id_obj, "lang_id");
            if (PyErr_Occurred())
                return -1;            

            if (lang_id != -1 && lang_id != self->environment->local_langid)
            {
                Py_BEGIN_ALLOW_THREADS
                    rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_LANG_ID, (dpointer)lang_id, 0);
                Py_END_ALLOW_THREADS

                    if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                        "Connection_connect():set connection attribute port") < 0)
                        return -1;

                /** 若设置成功，则更新环境变量上值 **/
                Environment_refresh_local_langid(self->environment, NULL, lang_id);
            }
        }        

        if (local_code_obj != NULL)
        {
            local_code  = DmIntNumber_AsInt(local_code_obj, "local_code");
            if (PyErr_Occurred())
                return -1;    

            if (local_code != -1 && local_code != self->environment->local_code)
            {       
                Py_BEGIN_ALLOW_THREADS
                    rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_LOCAL_CODE, (dpointer)local_code, 0);
                Py_END_ALLOW_THREADS

                    if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                        "Connection_connect():set connection attribute port") < 0)
                        return -1;	

                /** 若设置成功，则更新环境变量上值 **/
                Environment_refresh_local_code(self->environment, NULL, local_code);
            }
            // bug663202 因为有些编码格式无法编码中文，所以将服务器消息格式强制改为英文
            if (local_code != PG_UTF8 && local_code != PG_GBK && local_code != PG_BIG5 && local_code != PG_GB18030)
            {
                lang_id = LANGUAGE_EN;
                if (lang_id != self->environment->local_langid)
                {
                    Py_BEGIN_ALLOW_THREADS
                        rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_LANG_ID, (dpointer)lang_id, 0);
                    Py_END_ALLOW_THREADS

                        if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                            "Connection_connect():set connection attribute port") < 0)
                            return -1;

                    /** 若设置成功，则更新环境变量上值 **/
                    Environment_refresh_local_langid(self->environment, NULL, lang_id);
                }
            }
        }

        if (cursor_class_obj != NULL)
        {
            cursor_class  = DmIntNumber_AsInt(cursor_class_obj, "cursor_class");
            if (PyErr_Occurred())
                return -1;    

            if (cursor_class != -1)
            {       
                self->cursor_class  = cursor_class;
            }
        }

    /** 连接成功，重新获取环境上属性 **/
    Environment_refresh_local_code(self->environment, self->hcon, PG_GB18030);
    Environment_refresh_local_langid(self->environment, self->hcon, LANGUAGE_CN);
#ifdef LANGUAGE_CNT_HK
    if (self->environment->local_langid == LANGUAGE_CNT_HK)
    {
        local_code = self->environment->local_code;
        if (local_code != PG_UTF8 && local_code != PG_BIG5 && local_code != PG_GB18030)
        {
            PyErr_SetString(PyExc_TypeError, "Invalid lang_id value to set, LANGUAGE_CNT_HK only can be used when local_code = PG_UTF8, PG_BIG5 or PG_GB18030");
            return -1;
        }
    }
#endif
    if (self->environment->local_langid == LANGUAGE_CN)
    {
        local_code = self->environment->local_code;
        if (local_code != PG_UTF8 && local_code != PG_GBK && local_code != PG_BIG5 && local_code != PG_GB18030)
        {
            PyErr_SetString(PyExc_TypeError, "Invalid lang_id value to set, LANGUAGE_CN only can be used when local_code = PG_UTF8, PG_BIG5, PG_GBK or PG_GB18030");
            return -1;
        }
    }


    /** 非默认端口号，需要设置端口属性 **/
    port    = DmIntNumber_AsInt(self->port, "port");
    if (PyErr_Occurred())
        return -1;        
    if (port != DSQL_DEAFAULT_TCPIP_PORT)
    {
        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_LOGIN_PORT, (dpointer)port, 0);
        Py_END_ALLOW_THREADS

        if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
            "Connection_connect():set connection attribute port") < 0)
            return -1;	
    }

    /** 拼出dsn串 ip:port **/
    Connection_makedsn(self);

    //access_mode
    if (accessmode_obj != NULL)
    {
        mode    = DmIntNumber_AsInt(accessmode_obj, "access_mode");
        if (PyErr_Occurred())
            return -1;        

        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_ACCESS_MODE, (dpointer)mode, 0);
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute access_mode") < 0)
                return -1;	
    }

    //autoCommit
    if (autocommit_obj != NULL)
    {
        autocommit  = DmIntNumber_AsInt(autocommit_obj, "autoCommit");
        if (PyErr_Occurred())
            return -1;        

        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_AUTOCOMMIT, (dpointer)autocommit, 0);
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute autoCommit") < 0)
                return -1;	
    }

    //connection_timeout
    if (conn_timeout_obj != NULL)
    {
        conn_timeout    = DmIntNumber_AsInt(conn_timeout_obj, "connection_timeout");
        if (PyErr_Occurred())
            return -1;                

        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_CONNECTION_TIMEOUT, (dpointer)conn_timeout, 0);
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute connection_timeout") < 0)
                return -1;	
    }

    //login_timeout
    if (login_timeout_obj != NULL)
    {
        login_timeout   = DmIntNumber_AsInt(login_timeout_obj, "login_timeout");
        if (PyErr_Occurred())
            return -1;       

        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_LOGIN_TIMEOUT, (dpointer)login_timeout, 0);
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute login_timeout") < 0)
                return -1;	
    }

    //txn_isolation
    if (txn_isolation_obj != NULL)
    {
        txn_isolation   = DmIntNumber_AsInt(txn_isolation_obj, "txn_isolation");
        if (PyErr_Occurred())
            return -1;              

        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_TXN_ISOLATION, (dpointer)txn_isolation, 0);
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute txn_isolation") < 0)
                return -1;
    }

    //compress_msg
    if (cmpress_msg_obj != NULL)
    {        
        cmpress_msg = DmIntNumber_AsInt(cmpress_msg_obj, "compress_msg");
        if (PyErr_Occurred())
            return -1;               

        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_COMPRESS_MSG, (dpointer)cmpress_msg, 0);
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute compress_msg") < 0)
                return -1;
    }

    //use_stmt_pool
    if (stmt_pool_obj != NULL)
    {        
        stmt_pool   = DmIntNumber_AsInt(stmt_pool_obj, "use_stmt_pool");
        if (PyErr_Occurred())
            return -1;               

        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_USE_STMT_POOL, (dpointer)stmt_pool, 0);
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute use_stmt_pool") < 0)
                return -1;
    }

    //cursor_rollback_behavior
    if (cursor_rollback_obj != NULL)
    {
        corsor_behavior = DmIntNumber_AsInt(cursor_rollback_obj, "cursor_rollback_behavior");
        if (PyErr_Occurred())
            return -1;               

        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_CURSOR_ROLLBACK_BEHAVIOR, (dpointer)corsor_behavior, 0);
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute cursor_rollback_behavior") < 0)
                return -1;
    }    

    //mpp_login
    if (mpp_login_obj != NULL)
    {
        mpp_login   = DmIntNumber_AsInt(mpp_login_obj, "mpp_login");
        if (PyErr_Occurred())
            return -1;               

        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_MPP_LOGIN, (dpointer)mpp_login, 0);
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute mpp_login") < 0)
                return -1;
    }

    //rwseparate
    if (rwseparate_obj != NULL)
    {   
        rwseparate  = DmIntNumber_AsInt(rwseparate_obj, "rwseparate");
        if (PyErr_Occurred())
            return -1;               

        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_RWSEPARATE, (dpointer)rwseparate, 0);
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute rwseparate") < 0)
                return -1;
    }

    //rwseparate_percent
    if (rwseparate_percent_obj != NULL)
    {        
        rwseparate_percent  = DmIntNumber_AsInt(rwseparate_percent_obj, "rwseparate_percent");
        if (PyErr_Occurred())
            return -1;               

        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_RWSEPARATE_PERCENT, (dpointer)rwseparate_percent, 0);
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute rwseparate_percent") < 0)
                return -1;
    }

    //app_name
    if (app_name != NULL)
    {
        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_APP_NAME, (dpointer)app_name, (sdint4)strlen(app_name));
        Py_END_ALLOW_THREADS
        
        if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute app_name") < 0)
            return -1;
    }

    //ssl_path
    if (ssl_path != NULL)
    {
        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_SSL_PATH, (dpointer)ssl_path, (sdint4)strlen(ssl_path));
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute ssl_path") < 0)
                return -1;
    }

    //ssl_pwd
    if (ssl_pwd != NULL)
    {
        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_SSL_PWD, (dpointer)ssl_pwd, (sdint4)strlen(ssl_pwd));
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute ssl_pwd") < 0)
                return -1;
    }

    //ukey_name
    if (ukey_name != NULL)
    {
        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_UKEY_NAME, (dpointer)ukey_name, (sdint4)strlen(ukey_name));
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute ukey_name") < 0)
                return -1;
    }

    if (ukey_pin != NULL)
    {
        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_UKEY_PIN, (dpointer)ukey_pin, (sdint4)strlen(ukey_pin));
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute ukey_pin") < 0)
                return -1;
    }
#ifdef DSQL_ATTR_SHAKE_CRYPTO
    //shake_crypto
    if (shake_crypto != NULL)
    {
        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_SHAKE_CRYPTO, (dpointer)shake_crypto, (sdint4)strlen(shake_crypto));
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute shake_crypto") < 0)
                return -1;
    }
#endif

#ifdef DSQL_ATTR_DM_SVC_PATH
    if (dmsvc_path != NULL)
    {
        Py_BEGIN_ALLOW_THREADS
            rt = dpi_set_con_attr(self->hcon, DSQL_ATTR_DM_SVC_PATH, (dpointer)dmsvc_path, DSQL_NTS);
        Py_END_ALLOW_THREADS

            if (Environment_CheckForError(self->environment, self->hcon, DSQL_HANDLE_DBC, rt,
                "Connection_connect():set connection attribute dmsvc_path") < 0)
                return -1;
    }
#endif

	return Connection_connect(self);
}

static
PyObject*
Connection_Repr(
    dm_Connection*     connection
)
{
	PyObject *module, *name, *result, *format, *formatArgs = NULL;

	if (GetModuleAndName(Py_TYPE(connection), &module, &name) < 0)
		return NULL;

	if (connection->username && connection->username != Py_None &&
		connection->server && connection->server != Py_None &&
		connection->port && connection->port != Py_None) {
			format = dmString_FromAscii("<%s.%s to %s@%s:%i>");
			if (format)
				formatArgs = PyTuple_Pack(5, module, name, connection->username,
				connection->server,connection->port);
	} else {
		format = dmString_FromAscii("<%s.%s to server exception>");
		if (format)
			formatArgs = PyTuple_Pack(2, module, name);
	}
	Py_DECREF(module);
	Py_DECREF(name);

	if (!format)
		return NULL;

	if (!formatArgs) {
		Py_DECREF(format);
		return NULL;
	}	

	result = PyUnicode_Format(format, formatArgs);
	Py_DECREF(format);
	Py_DECREF(formatArgs);
	return result;
}

PyObject*
Connection_NewCursor_Inner(
    dm_Connection*          self, 
    PyObject*				args
 )
{
    int         ret;

    ret     = Connection_IsConnected(self);
	if (ret != 0)
		return NULL;

    ret     = Connection_IsLogin(self, 0);
    if (ret != 0)	
		return NULL;

    return Cursor_New(self);    
}

static 
PyObject*
Connection_NewCursor(
    dm_Connection*          self, 
    PyObject*				args
 )
{
    PyObject*               rt_cursor;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Connection_NewCursor\n"));

    rt_cursor   = Connection_NewCursor_Inner(self, args);
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "EXIT Connection_NewCursor, %s\n", rt_cursor == NULL ? "FAILED" : "SUCCESS"));

    return rt_cursor;
}

/* cursor to set the explain info */
PyObject*
Connection_GetExplainInfo_Inner(
    dm_Cursor*     cursor
)
{
    char            explain_info[PY_SQL_MAX_LEN];
    DPIRETURN       ret = DSQL_SUCCESS;

    memset(explain_info, 0, PY_SQL_MAX_LEN);

    if (cursor->statementType == DSQL_DIAG_FUNC_CODE_EXPLAIN) 
    {
        ret = dpi_get_diag_field(DSQL_HANDLE_STMT, cursor->handle, 1, DSQL_DIAG_EXPLAIN, explain_info, PY_SQL_MAX_LEN, NULL);
        if (Environment_CheckForError(cursor->environment, cursor->handle, DSQL_HANDLE_STMT, ret, 
            "Connection_GetExplainInfo_Inner()") < 0)
            return NULL;	

        return dmString_FromEncodedString(explain_info, strlen(explain_info), cursor->environment->encoding);    
    }    

    Py_RETURN_NONE;
}

static
PyObject*
Connection_GetExplainInfo_inner_ex(
    dm_Connection*          self, 
    PyObject*				args
)
{
    PyObject*           statement = NULL;
    dm_Cursor*          cursor = NULL;
    dm_Buffer           stmt_Buffer;
    PyObject*           retObj = NULL;
    PyObject*           statementObj = NULL;
    Py_ssize_t          size;
    char*               sql_buf = NULL;

    if (!PyArg_ParseTuple(args, "O", &statement))
        return NULL;

    if (Connection_IsConnected(self) < 0)
        return NULL;

    if (dmBuffer_FromObject(&stmt_Buffer, statement, self->environment->encoding) < 0)
    {
        Py_XDECREF(statement);
        return NULL;
    }

    size    = strlen((char*)stmt_Buffer.ptr) + 8; /** len(explain) + ' ' **/

    sql_buf = PyMem_Malloc(size + 1);
    if (sql_buf == NULL)
    {
        PyErr_NoMemory();
        return NULL;
    }

    sprintf(sql_buf, "EXPLAIN %s", (char*)stmt_Buffer.ptr);
    statementObj    = dmString_FromAscii(sql_buf);
    if (statementObj == NULL)
    {
        PyMem_Free(sql_buf);
        return NULL;
    }

    cursor  = (dm_Cursor*)Connection_NewCursor_Inner(self, args);
    if (cursor == NULL)
    {
        Py_CLEAR(statementObj);

        if (sql_buf != NULL)
        {
            PyMem_Free(sql_buf);
        }

        return NULL;
    }    

    retObj  = PyObject_CallMethod( (PyObject*) cursor, "executedirect", "O", statementObj);
    
    Py_CLEAR(statementObj);
    if (sql_buf != NULL)
    {
        PyMem_Free(sql_buf);
    }

    if (!retObj)
    {        
        return NULL;
    }

    /** 获取explain信息 **/
    retObj  = Connection_GetExplainInfo_Inner(cursor);
    Py_CLEAR(cursor);

    return retObj;
}

static
PyObject*
Connection_GetExplainInfo(
    dm_Connection*          self, 
    PyObject*				args
)
{
    PyObject*           rt_obj;
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "ENTER Connection_GetExplainInfo\n"));

    rt_obj      = Connection_GetExplainInfo_inner_ex(self, args);
    
    DMPYTHON_TRACE_INFO(dpy_trace(NULL, args, "EXIT Connection_GetExplainInfo, %s\n", rt_obj == NULL ? "FAILED" : "SUCCESS"));

    return rt_obj;
}

//-----------------------------------------------------------------------------
// declaration of methods for Python type "Connection"
//-----------------------------------------------------------------------------
static PyMethodDef g_ConnectionMethods[] = {
	{ "cursor",     (PyCFunction) Connection_NewCursor,             METH_NOARGS,        "To create a new cursor"},
	{ "commit",     (PyCFunction) Connection_Commit,                METH_NOARGS,        "Commit"},
	{ "rollback",   (PyCFunction) Connection_Rollback,              METH_NOARGS,        "Rollback" },
	//{ "begin",    (PyCFunction) Connection_Begin, METH_VARARGS },
	//{ "prepare",  (PyCFunction) Connection_Prepare, METH_NOARGS },
	{ "close",      (PyCFunction) Connection_Close,                 METH_NOARGS,        "Close the connection"},
    { "disconnect", (PyCFunction) Connection_Close,                 METH_NOARGS,        "Close the connection"},
    { "debug",      (PyCFunction) Connection_Debug,                 METH_VARARGS,       "Set SVR_LOG in dm.ini"},
    { "shutdown",   (PyCFunction) Connection_Shutdown,              METH_VARARGS,       "Shutdown dmserver"},
    { "explain",    (PyCFunction) Connection_GetExplainInfo,        METH_VARARGS,       "Get sql explaination information"},
	{ "ping",       (PyCFunction) Connection_Ping,                  METH_VARARGS,       "ping the connection"},
	//{ "cancel",   (PyCFunction) Connection_Cancel, METH_NOARGS },
	//{ "register", (PyCFunction) Connection_RegisterCallback, METH_VARARGS },
	//{ "unregister",(PyCFunction) Connection_UnregisterCallback, METH_VARARGS },
    { "__enter__",  (PyCFunction) Connection_ContextManagerEnter,   METH_NOARGS,        ""},
    { "__exit__",   (PyCFunction) Connection_ContextManagerExit,    METH_VARARGS,       ""},
	//{ "shutdown", (PyCFunction) Connection_Shutdown, METH_VARARGS | METH_KEYWORDS},
	//{ "startup",  (PyCFunction) Connection_Startup, METH_VARARGS | METH_KEYWORDS},
	//{ "subscribe",(PyCFunction) Connection_Subscribe, METH_VARARGS | METH_KEYWORDS},
	{ NULL }
};


//-----------------------------------------------------------------------------
// declaration of members for Python type "Connection"
//-----------------------------------------------------------------------------
static PyMemberDef g_ConnectionMembers[] = {
    { "dsn",                    T_OBJECT,   offsetof(dm_Connection, dsn),              READONLY },
    { "server_status",          T_OBJECT,   offsetof(dm_Connection, server_status),    READONLY },    
    { "warning",                T_OBJECT,   offsetof(dm_Connection, warning),          READONLY },
    //{ "password", T_OBJECT, offsetof(dm_Connection, password), 0 },   
    //{ "autocommit", T_INT, offsetof(dm_Connection, autocommit), 0 },
	//{ "port", T_OBJECT, offsetof(dm_Connection, port), 0},
    //{ "inputtypehandler", T_OBJECT, offsetof(dm_Connection, inputTypeHandler), 0 },
    //{ "outputtypehandler", T_OBJECT, offsetof(dm_Connection, outputTypeHandler), 0 },
    { NULL }
};

//-----------------------------------------------------------------------------
// declaration of calculated members for Python type "Connection"
//-----------------------------------------------------------------------------
static PyGetSetDef g_ConnectionCalcMembers[] = {
    { "access_mode",            (getter) Connection_GetConAttr, (setter)Connection_SetConAttr,  0,  &gc_attr_access_mode},
    { "DSQL_ATTR_ACCESS_MODE",  (getter) Connection_GetConAttr, (setter)Connection_SetConAttr,  0,  &gc_attr_access_mode},

    { "async_enable",           (getter) Connection_GetConAttr, (setter)Connection_SetConAttr,  0,  &gc_attr_async_enalbe},
    { "DSQL_ATTR_ASYNC_ENABLE", (getter) Connection_GetConAttr, (setter)Connection_SetConAttr,  0,  &gc_attr_async_enalbe},

    { "auto_ipd",               (getter) Connection_GetConAttr, (setter)Connection_SetConAttr,  0,  &gc_attr_auto_ipd},
    { "DSQL_ATTR_AUTO_IPD",     (getter) Connection_GetConAttr, (setter)Connection_SetConAttr,  0,  &gc_attr_auto_ipd},

    { "server_code",            (getter) Connection_GetConAttr, 0,                              0,  &gc_attr_server_code },
    { "DSQL_ATTR_SERVER_CODE",  (getter) Connection_GetConAttr, 0,                              0,  &gc_attr_server_code },

    { "local_code",             (getter) Connection_GetConAttr, (setter)Connection_SetConAttr,  0,  &gc_attr_local_code },
    { "DSQL_ATTR_LOCAL_CODE",   (getter) Connection_GetConAttr, (setter)Connection_SetConAttr,  0,  &gc_attr_local_code },

    { "lang_id",                (getter) Connection_GetConAttr, (setter)Connection_SetConAttr,  0,  &gc_attr_lang_id },
    { "DSQL_ATTR_LANG_ID",      (getter) Connection_GetConAttr, (setter)Connection_SetConAttr,  0,  &gc_attr_lang_id },

    { "app_name",               (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_app_name},
    { "DSQL_ATTR_APP_NAME",     (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_app_name},

    { "current_schema",                 (getter) Connection_GetConAttr, 0,                              0, &gc_attr_current_schema },
    { "DSQL_ATTR_CURRENT_SCHEMA",       (getter) Connection_GetConAttr, 0,                              0, &gc_attr_current_schema },

	{ "txn_isolation",                  (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_txn_isolation},  
    { "DSQL_ATTR_TXN_ISOLATION",        (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_txn_isolation},  

	{ "str_case_sensitive",             (getter)Connection_GetConAttr,  0,                              0,  &gc_attr_str_case_sencitive},
    { "DSQL_ATTR_STR_CASE_SENSITIVE",   (getter)Connection_GetConAttr,  0,                              0,  &gc_attr_str_case_sencitive},

    { "max_row_size",                   (getter)Connection_GetConAttr,  0,                              0,  &gc_attr_max_row_size},
    { "DSQL_ATTR_MAX_ROW_SIZE",         (getter)Connection_GetConAttr,  0,                              0,  &gc_attr_max_row_size},	

	{ "compress_msg",                   (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_compres_msg},
    { "DSQL_ATTR_COMPRESS_MSG",         (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_compres_msg},

    { "rwseparate",                     (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_rwseparate},
    { "DSQL_ATTR_RWSEPARATE",           (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_rwseparate},

    { "rwseparate_percent",             (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_rwseparate_percent},
    { "DSQL_ATTR_RWSEPARATE_PERCENT",   (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_rwseparate_percent},

    { "current_catalog",                (getter)Connection_GetConAttr,  0,                              0,  &gc_attr_current_catalog},
    { "DSQL_ATTR_CURRENT_CATALOG",      (getter)Connection_GetConAttr,  0,                              0,  &gc_attr_current_catalog},

    { "trx_state",                      (getter)Connection_GetConAttr,  0,                              0,  &gc_attr_trx_state},
    { "DSQL_ATTR_TRX_STATE",            (getter)Connection_GetConAttr,  0,                              0,  &gc_attr_trx_state},

    { "use_stmt_pool",                  (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_use_stmt_pool},
    { "DSQL_ATTR_USE_STMT_POOL",        (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_use_stmt_pool},

	{ "ssl_path",                       (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_ssl_path},
    { "DSQL_ATTR_SSL_PATH",             (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_ssl_path},

    { "mpp_login",                      (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_mpp_login},
    { "DSQL_ATTR_MPP_LOGIN",            (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_mpp_login},
	
    { "server_version",                 (getter)Connection_GetConAttr,  0,                              0,  &gc_attr_server_version},
    { "DSQL_ATTR_SERVER_VERSION",       (getter)Connection_GetConAttr,  0,                              0,  &gc_attr_server_version},

    { "cursor_rollback_behavior",           (getter)Connection_GetConAttr,  0,                          0,  &gc_attr_cursor_rollback_behavior},
    { "DSQL_ATTR_CURSOR_ROLLBACK_BEHAVIOR", (getter)Connection_GetConAttr,  0,                          0,  &gc_attr_cursor_rollback_behavior},

    { "autoCommit",                     (getter)Connection_GetConAttr, (setter)Connection_SetConAttr,   0,  &gc_attr_autocommit},
    { "DSQL_ATTR_AUTOCOMMIT",           (getter)Connection_GetConAttr, (setter)Connection_SetConAttr,   0,  &gc_attr_autocommit},

    { "connection_dead",                (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_conn_dead},
    { "DSQL_ATTR_CONNECTION_DEAD",      (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_conn_dead},

    { "connection_timeout",             (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_conn_timeout},
    { "DSQL_ATTR_CONNECTION_TIMEOUT",   (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_conn_timeout},

    { "login_timeout",                  (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_login_timeout},
    { "DSQL_ATTR_LOGIN_TIMEOUT",        (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_login_timeout},

    { "packet_size",                    (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_packet_size},
    { "DSQL_ATTR_PACKET_SIZE",          (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0,  &gc_attr_packet_size},

	{ "port",                           (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0, &gc_attr_login_port},
    { "DSQL_ATTR_LOGIN_PORT",           (getter)Connection_GetConAttr,  (setter)Connection_SetConAttr,  0, &gc_attr_login_port},

    { "user",                           (getter)Connection_GetConAttr,  0,                              0, &gc_attr_login_user},
    { "DSQL_ATTR_LOGIN_USER",           (getter)Connection_GetConAttr,  0,                              0, &gc_attr_login_user},

    { "server",                         (getter)Connection_GetConAttr,  0,                              0, &gc_attr_login_server},
    { "DSQL_ATTR_LOGIN_SERVER",         (getter)Connection_GetConAttr,  0,                              0, &gc_attr_login_server},

    { "inst_name",                      (getter)Connection_GetConAttr,  0,                              0, &gc_attr_instance_name},
    { "DSQL_ATTR_INSTANCE_NAME",        (getter)Connection_GetConAttr,  0,                              0, &gc_attr_instance_name},

    { NULL }
};


//-----------------------------------------------------------------------------
// declaration of Python type "Connection"
//-----------------------------------------------------------------------------
PyTypeObject g_ConnectionType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.Connection",              // tp_name
    sizeof(dm_Connection),              // tp_basicsize
    0,                                  // tp_itemsize
    (destructor) Connection_Free,       // tp_dealloc
    0,                                  // tp_print
    0,                                  // tp_getattr
    0,                                  // tp_setattr
    0,                                  // tp_compare
    (reprfunc) Connection_Repr,         // tp_repr
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
    0,                                  // tp_iter
    0,                                  // tp_iternext
    g_ConnectionMethods,                // tp_methods
    g_ConnectionMembers,                // tp_members
    g_ConnectionCalcMembers,            // tp_getset
    0,                                  // tp_base
    0,                                  // tp_dict
    0,                                  // tp_descr_get
    0,                                  // tp_descr_set
    0,                                  // tp_dictoffset
    (initproc) Connection_Init,         // tp_init
    0,                                  // tp_alloc
    (newfunc) Connection_New,           // tp_new
    0,                                  // tp_free
    0,                                  // tp_is_gc
    0                                   // tp_bases
};

