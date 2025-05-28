#ifndef _ERROR_H
#define _ERROR_H

#include "strct.h"

sdint2 
Environment_CheckForError(
	dm_Environment*     environment,       // environment to raise error in									 
	dhandle	            errorHandle,
	sdint2		        handleType,
	DPIRETURN           rt,                       // status of last call
	char*               context
); 

dm_Environment*
Environment_New();

sdint2
Environment_refresh_local_code(
	dm_Environment*     self,              // environment object
    dhcon               con_handle,
    sdint4              local_code
);

sdint2
Environment_refresh_local_langid(
	dm_Environment*     self,              // environment object
    dhcon               con_handle,
    sdint4              local_langid
);

extern	PyTypeObject g_EnvironmentType;
extern	PyTypeObject g_ErrorType;

#endif	//_ERROR_H

