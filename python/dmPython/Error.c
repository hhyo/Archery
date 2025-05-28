//-----------------------------------------------------------------------------
// Error.c
//   Error handling.
//-----------------------------------------------------------------------------
#include "Error.h"

//-----------------------------------------------------------------------------
// Error_Free()
//   Deallocate the environment, disconnecting from the database if necessary.
//-----------------------------------------------------------------------------
static 
void Error_Free(
    dm_Error*      self    // error object
)                    
{
    if (self->context != NULL)
    {
        PyMem_Free(self->context);
        self->context   = NULL;
    }

	Py_CLEAR(self->message);
	PyObject_Del(self);
}


//-----------------------------------------------------------------------------
// Error_Str()
//   Return a string representation of the error variable.
//-----------------------------------------------------------------------------
static 
PyObject*
Error_Str(
    dm_Error*      self  // variable to return the string for
)
{
	if (self->message) {
		Py_INCREF(self->message);
		return self->message;
	}
	return Py_BuildValue("s","");
}


//-----------------------------------------------------------------------------
// declaration of members
//-----------------------------------------------------------------------------
static PyMemberDef g_ErrorMembers[] = {
	{ "code", T_INT, offsetof(dm_Error, code), READONLY },
	{ "offset", T_INT, offsetof(dm_Error, offset), READONLY },
	{ "message", T_OBJECT, offsetof(dm_Error, message), READONLY },
	{ "context", T_STRING, offsetof(dm_Error, context), READONLY },
	{ NULL }
};


//-----------------------------------------------------------------------------
// declaration of Python type
//-----------------------------------------------------------------------------
PyTypeObject g_ErrorType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	"dmPython.DmError",                 // tp_name
	sizeof(dm_Error),                   // tp_basicsize
	0,                                  // tp_itemsize
	(destructor) Error_Free,            // tp_dealloc
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
	(reprfunc) Error_Str,               // tp_str
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
	g_ErrorMembers,                     // tp_members
	0                                   // tp_getset
};

