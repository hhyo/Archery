#ifndef _BUFFER_H
#define _BUFFER_H

#include <Python.h>

#include "DPI.h"
#include "DPIext.h"
#include "DPItypes.h"

// define structure for abstracting string buffers
typedef struct {
	const void *ptr;
	Py_ssize_t numCharacters;
	Py_ssize_t size;
	PyObject *obj;
} dm_Buffer;


#define dmBuffer_Clear(buf)             Py_XDECREF((buf)->obj)

sdint2 
dmBuffer_FromObject(
    dm_Buffer  *buf,                    // buffer to fill
    PyObject   *obj,                      // object (string or Unicode object)
    const char *encoding               // encoding to use, if applicable
);

#endif	//_BUFFER_H

