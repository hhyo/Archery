#ifndef _DMPYTHON_TRC_H
#define _DMPYTHON_TRC_H

#include <time.h>
#include <stdarg.h>
#include "DPItypes.h"
#include <Python.h>

#define DMPYTHON_TRACE_OFF     0
#define DMPYTHON_TRACE_ON      1

extern udint4   dmpython_trace_mod;

#ifdef WIN32
#define DMPYTHON_TRACE_FILE    ".\\dmPython_trace.log"
#else
#define DMPYTHON_TRACE_FILE    "./dmPython_trace.log"
#endif

#ifdef DM64
#ifdef WIN32
#define slengthprefix   "%I64d"
#else
#define slengthprefix   "%lld"
#endif
#else
#define slengthprefix   "%ld"
#endif

#define DMPYTHON_TRACE_INFO(act)\
if (dmpython_trace_mod != DMPYTHON_TRACE_OFF)\
{\
    act;\
}\

void
dpy_trace(    
    PyObject*       statement,
    PyObject*       args,
    sdbyte*         info,
    ...
);


#endif #_DMPATHON_TRC_H