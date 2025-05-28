//-----------------------------------------------------------------------------
// Environment.c
//   Environment handling.
//-----------------------------------------------------------------------------
#include "py_Dameng.h"
#include "Error.h"

//-----------------------------------------------------------------------------
// forward declarations
//-----------------------------------------------------------------------------
static void Environment_Free(dm_Environment*);


//-----------------------------------------------------------------------------
// declaration of Python type
//-----------------------------------------------------------------------------
PyTypeObject g_EnvironmentType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	"dmPython.DmdbEnvironment",	                // tp_name
	sizeof(dm_Environment),             // tp_basicsize
	0,                                  // tp_itemsize
	(destructor) Environment_Free,      // tp_dealloc
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
// Error_New()
//   Create a new error object.
//-----------------------------------------------------------------------------
static
dm_Error*
Error_New(
	dm_Environment*     environment,
	dhandle		        handle,
	sdint2		        handleType,
	int                 retrieveError,                  // retrieve error from DPI?
	char*			    context
)
{
    sdbyte          error_buf[4096];
	sdbyte			errorText[4096];
	sdint4			errorCode;
	sdint2			errorLen;
	dm_Error        *self;
	DPIRETURN		rt = DSQL_SUCCESS;

	self = (dm_Error*) g_ErrorType.tp_alloc(&g_ErrorType, 0);
	if (!self)
		return NULL;

	if (!retrieveError)
		return self;

	if (context)
    {        
		self->context = PyMem_Malloc(strlen(context) + 1);
		if (self->context)
			strcpy(self->context, context);
	}
    else
    {
        self->context = NULL;
    }

	Py_BEGIN_ALLOW_THREADS
	rt = dpi_get_diag_rec(handleType, handle, 1, &errorCode, errorText, sizeof(errorText), &errorLen);	
	Py_END_ALLOW_THREADS

	if (!DSQL_SUCCEEDED(rt))
	{		
		Py_DECREF(self);
		PyErr_SetString(g_InternalErrorException, "Error occurs when call 'dpi_get_diag_rec'");
		return NULL;
	}
	else
	{
        sprintf(error_buf, "[CODE:%d]%s", errorCode, errorText);
        self->message = dmString_FromEncodedString(error_buf, strlen(error_buf), environment->encoding);
		self->code = errorCode;

		if (self->message)
			return self;
		else{
			Py_DECREF(self);
			return NULL;
		}
	}
}

// parse local coding
static
sdint2
Environment_Parse_Coding(
    sdint4		codeId,
    sdbyte*     code_name
)
{
	switch(codeId)
	{
	case PG_UTF8:
        sprintf(code_name, "%s", "UTF8");		
		break;

	case PG_GBK:
        sprintf(code_name, "%s", "GBK");		
		break;

	case PG_BIG5:
        sprintf(code_name, "%s", "BIG5");		
		break;

	case PG_ISO_8859_9:
        sprintf(code_name, "%s", "ISO_8859_9");		
		break;

	case PG_EUC_JP:
        sprintf(code_name, "%s", "EUC_JP");		
		break;

	case PG_EUC_KR:
        sprintf(code_name, "%s", "EUC_KR");				
		break;

	case PG_KOI8R:
        sprintf(code_name, "%s", "KOI8-R");		
		break;

	case PG_ISO_8859_1:
        sprintf(code_name, "%s", "ISO_8859_1");		
		break;

	case PG_SQL_ASCII:
        sprintf(code_name, "%s", "ASCII");
		break;

	case PG_GB18030:
        sprintf(code_name, "%s", "GB18030");		
		break;	

    case PG_ISO_8859_11:
        sprintf(code_name, "%s", "ISO_8859_11");        
        break;

	default:	
        return -1;        
	}	

    return 0;
}

//-----------------------------------------------------------------------------
// Environment_GetCharacterSetName()
//   Retrieve and store the IANA character set name for the attribute.
//-----------------------------------------------------------------------------
sdint2
Environment_refresh_local_code(
	dm_Environment*     self,              // environment object
    dhcon               con_handle,
    sdint4              local_code
)                   
{
	DPIRETURN		rt = DSQL_SUCCESS;
	sdint4			codeId;
	sdint4			len;

    codeId      = local_code;

    if (con_handle != NULL)
    {
        Py_BEGIN_ALLOW_THREADS
            rt	= dpi_get_con_attr(con_handle, DSQL_ATTR_LOCAL_CODE, &codeId, 0, &len);
        Py_END_ALLOW_THREADS        
        if (Environment_CheckForError(self, con_handle, DSQL_HANDLE_DBC, rt, "Environment_refresh_local_code(): get charset id" ) < 0) 
            return -1;
    }	

	rt = Environment_Parse_Coding(codeId, self->encoding);
	if (rt < 0){
		PyErr_SetString(g_InternalErrorException, "Environment_refresh_local_code: Invalid encoding type has been got.");
		return -1;
	}

    self->local_code    = codeId;

	return 0;
}

sdint2
Environment_refresh_local_langid(
	dm_Environment*     self,              // environment object
    dhcon               con_handle,
    sdint4              local_langid
)                   
{
	DPIRETURN		rt = DSQL_SUCCESS;
	sdint4			langid;
	sdint4			len;

    langid          = local_langid;

    if (con_handle != NULL)
    {
        Py_BEGIN_ALLOW_THREADS
            rt	= dpi_get_con_attr(con_handle, DSQL_ATTR_LANG_ID, &langid, 0, &len);
        Py_END_ALLOW_THREADS         
        if (Environment_CheckForError(self, con_handle, DSQL_HANDLE_DBC, rt, "Environment_refresh_local_langid(): get lang id" ) < 0) 
            return -1;
    }	

    self->local_langid  = langid;
	
	return 0;
}

//-----------------------------------------------------------------------------
// Environment_New()
//   Create a new environment object.
//----------------------------------------------------------------------------- 
dm_Environment*
Environment_New() 
{
	dm_Environment *env;
	DPIRETURN		rt = DSQL_SUCCESS;
    sdint4			len;
    sdbyte          context[512];
    sdbyte          context_tmp[512];

	// create a new object for the Dameng environment
	env = (dm_Environment*) g_EnvironmentType.tp_alloc(&g_EnvironmentType, 0);
	if (!env)
		return NULL;
    
	env->handle                 = NULL;	
	env->maxBytesPerCharacter   = 4;
    env->local_code             = PG_GB18030;
    env->local_langid           = LANGUAGE_CN;
    sprintf(env->encoding, "%s", "gb18030"); 
    
	// 申请环境句柄
	rt	= dpi_alloc_env(&env->handle);
    if (!DSQL_SUCCEEDED(rt))
    {
        sprintf(context, "Environment_New():alloc environment handle");
        goto fun_end;
    }	

    rt	= dpi_get_env_attr(env->handle, DSQL_ATTR_LOCAL_CODE, &env->local_code, 0, &len);
    if (!DSQL_SUCCEEDED(rt))
    {
        sprintf(context, "Environment_New():get local_code");
        goto fun_end;
    }       	

    rt	= dpi_get_env_attr(env->handle, DSQL_ATTR_LANG_ID, &env->local_langid, 0, &len);
    if (!DSQL_SUCCEEDED(rt))
    {
        sprintf(context, "Environment_New():get local_code");         
    }

fun_end:
    if (DSQL_SUCCEEDED(rt))
    {
        if (Environment_Parse_Coding(env->local_code, env->encoding) < 0)
        {
            sprintf(context_tmp, "Environment_New: Invalid local code [%d] has been got.", env->local_code);
            PyErr_SetString(g_InternalErrorException, context);
        }
        else
        {
            return env;
        }        
    }

    if (!DSQL_SUCCEEDED(rt))
    {
        Environment_CheckForError(env, env->handle, DSQL_HANDLE_ENV, rt, context);    
    }

    if (env->handle != NULL)
    {
        dpi_free_env(env->handle);
        env->handle = NULL;
    }

    Py_DECREF(env);
    return NULL;
}

//-----------------------------------------------------------------------------
// Environment_Free()
//   Deallocate the environment. Note that destroying the environment handle
// will automatically destroy any child handles that were created.
//-----------------------------------------------------------------------------
static 
void 
Environment_Free(
    dm_Environment *self // environment object
)              
{
	if (self->handle){
		dpi_free_env(self->handle);
		self->handle = NULL;
	}	

	Py_TYPE(self)->tp_free((PyObject*) self);
}

//-----------------------------------------------------------------------------
// Environment_RaiseError()
//   Reads the error that was caused by the last Oracle statement and raise an
// exception for Python. At this point it is assumed that the Oracle
// environment is fully initialized.
//-----------------------------------------------------------------------------
static 
sdint2 
Environment_RaiseError(
    dm_Environment*     environment,
    dhandle             errorHandle,
    sdint2              handleType,
    char*               context
) 
{
	PyObject *exceptionType;
	dm_Error *error;

	error = Error_New(environment, errorHandle, handleType, 1, context);	
	if (error) {
		switch (error->code) {
			case -6601:
			case -6602:
			case -6603:
			case -6604:
			case -6605:
			case -6606:
			case -6607:
			case -6608:
			case -6609:
			case -6610:
			case -6611:
			case -6612:
				exceptionType = g_IntegrityErrorException;
				break;

			case -501:
			case -502:
			case -503:
			case -504:
			case -505:
			case -506:
			case -507:
			case -508:
			case -509:
			case -510:
			case -511:
			case -512:
			case -513:
			case -514:
			case -515:
			case -516:
			case -517:
			case -518:
			case -519:
			case -520:
			case -521:
			case -522:
			case -523:
			case -524:
			case -525:
			case -526:
				exceptionType = g_OperationalErrorException;
				break;

			default:
				exceptionType = g_DatabaseErrorException;
				break;
		}
		PyErr_SetObject(exceptionType, (PyObject*) error);
		Py_DECREF(error);
	}
	return -1;
}

/** 获取dpi的报错信息，赋值到connection的warning成员 **/
sdint2 
Environment_SetWarning(
    dm_Environment*     environment,		
    dhandle             errorHandle,
    sdint2              handleType
)
{
    char            err_msg[1024];
    DPIRETURN       ret = DSQL_SUCCESS;

    memset(err_msg, 0, 1024);

    if (handleType == DSQL_HANDLE_STMT || handleType == DSQL_HANDLE_DBC)
    {
        ret = dpi_get_diag_field(handleType, errorHandle, 1, DSQL_DIAG_MESSAGE_TEXT, &err_msg, sizeof(err_msg), NULL);
        if (DSQL_SUCCEEDED(ret))
        {
            *environment->warning = dmString_FromEncodedString(err_msg, strlen(err_msg), environment->encoding);
        }
    }
    
    return 0;
}

//-----------------------------------------------------------------------------
// Environment_CheckForError()
//   Check for an error in the last call and if an error has occurred, raise a
// Python exception.
//-----------------------------------------------------------------------------
sdint2 
Environment_CheckForError(
	dm_Environment*     environment,
	dhandle             errorHandle,
	sdint2              handleType,
	DPIRETURN           rt,                       // status of last call
	char*               context
) 
{
	dm_Error    *error;
	char		*errorText = "InValid handle";    

	if (!DSQL_SUCCEEDED(rt)) 
	{	
        if (rt == DSQL_NO_DATA)
        {
            return 0;
        }

        Environment_SetWarning(environment, errorHandle, handleType);
        
		if (rt != DSQL_INVALID_HANDLE)
			return Environment_RaiseError(environment, errorHandle, handleType, context);

		error = Error_New(environment,  errorHandle, handleType, 0, context);
		if (!error)
			return -1;

#if PY_MAJOR_VERSION < 3
		error->message  = PyBytes_FromString(errorText);
#else     
		error->message  = PyUnicode_Decode(errorText, strlen(errorText), environment->encoding,
			NULL);
#endif
		error->code = rt;

		PyErr_SetObject(g_DatabaseErrorException, (PyObject*) error);
		return -1;
	}	

	return 0;
}



