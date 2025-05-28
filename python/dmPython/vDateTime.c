/******************************************************
file:
    vDateTime.c
purpose:
    python type define for DM data/time/timestamp variables in dmPython
interface:
    {}
history:
    Date        Who         RefDoc      Memo
    2015-6-9    wmm                     Created
*******************************************************/

#include "Error.h"
#include "py_Dameng.h"
#include "Buffer.h"
#include "var_pub.h"
#include <datetime.h>

//-----------------------------------------------------------------------------
// Declaration of date/time variable functions.
//-----------------------------------------------------------------------------
static int DateVar_SetValue(dm_DateVar*, unsigned, PyObject*);
static PyObject* DateVar_GetValue(dm_DateVar*, unsigned);
static int DateVar_BindObjectValue(dm_DateVar*, unsigned, dhobj, udint4);

static int TimeVar_SetValue(dm_TimeVar*, unsigned, PyObject*);
static PyObject* TimeVar_GetValue(dm_TimeVar*, unsigned);
static int TimeVar_BindObjectValue(dm_TimeVar*, unsigned, dhobj, udint4);

static int TimestampVar_SetValue(dm_TimestampVar*, unsigned, PyObject*);
static PyObject* TimestampVar_GetValue(dm_TimestampVar*, unsigned);
static int TimestampVar_BindObjectValue(dm_TimestampVar*, unsigned, dhobj, udint4);

static int TZVar_SetValue(dm_TZVar*, unsigned, PyObject*);
static PyObject* TZVar_GetValue(dm_TZVar*, unsigned);
static int TZVar_BindObjectValue(dm_TZVar*, unsigned, dhobj, udint4);

//-----------------------------------------------------------------------------
// Python type declarations
//-----------------------------------------------------------------------------
PyTypeObject g_DateType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.DATE",                    // tp_name
    sizeof(dm_DateVar),                 // tp_basicsize
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
    0                                   // tp_doc
};

PyTypeObject g_TimeType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.TIME",                    // tp_name
    sizeof(dm_TimeVar),                 // tp_basicsize
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
    0                                   // tp_doc
};

PyTypeObject g_TimestampType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.TIMESTAMP",               // tp_name
    sizeof(dm_TimestampVar),            // tp_basicsize
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
    0                                   // tp_doc
};

PyTypeObject g_TimeTZType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.TIME_WITH_TIMEZONE",      // tp_name
    sizeof(dm_TZVar),                   // tp_basicsize
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
    0                                   // tp_doc
};

PyTypeObject g_TimestampTZType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.TIMESTAMP_WITH_TIMEZONE", // tp_name
    sizeof(dm_TZVar),                   // tp_basicsize
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
    0                                   // tp_doc
};


//-----------------------------------------------------------------------------
// variable type declarations
//-----------------------------------------------------------------------------
dm_VarType vt_Date = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) DateVar_SetValue,
    (GetValueProc) DateVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)DateVar_BindObjectValue,
    &g_DateType,                        // Python type
    DSQL_C_DATE,                        // C type    
    sizeof(dpi_date_t),                 // element length (default)
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};

dm_VarType vt_Time = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) TimeVar_SetValue,
    (GetValueProc) TimeVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)TimeVar_BindObjectValue,
    &g_TimeType,                        // Python type
    DSQL_C_TIME,                        // C type
    sizeof(dpi_time_t),                 // element length (default)
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};

dm_VarType vt_Timestamp = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,    
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) TimestampVar_SetValue,
    (GetValueProc) TimestampVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)TimestampVar_BindObjectValue,
    &g_TimestampType,                   // Python type
    DSQL_C_TIMESTAMP,                   // C type
    sizeof(dpi_timestamp_t),            // element length (default)
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};

dm_VarType vt_TimeTZ = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) TZVar_SetValue,
    (GetValueProc) TZVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)TZVar_BindObjectValue,
    &g_TimeTZType,                      // Python type
    DSQL_C_NCHAR,                       // C type，以字符串形式处理
    64,                                 // element length (default)，预留64个字节长度
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};

dm_VarType vt_TimestampTZ = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc)TimestampVar_SetValue,
    (GetValueProc)TimestampVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)TimestampVar_BindObjectValue,
    &g_TimestampTZType,                 // Python type
    DSQL_C_TIMESTAMP,                   // C type
    sizeof(dpi_timestamp_t),            // element length (default)
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};

void
DateVar_import()
{
    PyDateTime_IMPORT;
}

static 
int 
DateVar_SetValue(
    dm_DateVar*     var,            // variable to set value for
    unsigned        pos,            // array position to set
    PyObject*       value           // value to set
)                    
{
    short           year;
    udbyte          month;
    udbyte          day;
    dpi_date_t*     date;

    if (!PyDate_Check(value)) 
    {
        PyErr_SetString(PyExc_TypeError, "expecting date data");
        return -1;
    }

    year        = (short) PyDateTime_GET_YEAR(value);
    month       = PyDateTime_GET_MONTH(value);
    day         = PyDateTime_GET_DAY(value);

    date        = &var->data[pos];

    date->year  = year;
    date->month = month;
    date->day   = day;

    var->indicator[pos]     = sizeof(dpi_date_t);
    var->actualLength[pos]  = sizeof(dpi_date_t);

    return 0;    
}

static 
int 
TimeVar_SetValue(
    dm_TimeVar*     var,            // variable to set value for
    unsigned        pos,            // array position to set
    PyObject*       value           // value to set
)                    
{
    udbyte          hour; 
    udbyte          minute;
    udbyte          second;
    dpi_time_t*     time;

    if (!PyTime_Check(value))
    {
        PyErr_SetString(PyExc_TypeError, "expecting time data");
        return -1;
    }

    hour    = PyDateTime_TIME_GET_HOUR(value);
    minute  = PyDateTime_TIME_GET_MINUTE(value);
    second  = PyDateTime_TIME_GET_SECOND(value);

    time            = &var->data[pos];

    time->hour      = hour;
    time->minute    = minute;
    time->second    = second;

    var->indicator[pos]     = sizeof(dpi_time_t);
    var->actualLength[pos]  = sizeof(dpi_time_t);

    return 0;
}

static 
int 
TimestampVar_SetValue(
    dm_TimestampVar*    var,            // variable to set value for
    unsigned            pos,            // array position to set
    PyObject*           value           // value to set
)                    
{
    short               year;
    udbyte              month; 
    udbyte              day; 
    udbyte              hour; 
    udbyte              minute;
    udbyte              second;
    udint4              usecond;
    dpi_timestamp_t*    ts;

    if (!PyDateTime_Check(value)) 
    {
        PyErr_SetString(PyExc_TypeError, "expecting datetime data");
        return -1;
    }

    year        = (short) PyDateTime_GET_YEAR(value);
    month       = PyDateTime_GET_MONTH(value);
    day         = PyDateTime_GET_DAY(value);
    hour        = PyDateTime_DATE_GET_HOUR(value);
    minute      = PyDateTime_DATE_GET_MINUTE(value);
    second      = PyDateTime_DATE_GET_SECOND(value);
    usecond     = PyDateTime_DATE_GET_MICROSECOND(value);

    ts          = &var->data[pos];

    ts->year    = year;
    ts->month   = month;
    ts->day     = day;
    ts->hour    = hour;
    ts->minute  = minute;
    ts->second  = second;
    ts->fraction = usecond * 1000;

    var->indicator[pos]     = sizeof(dpi_timestamp_t);
    var->actualLength[pos]  = sizeof(dpi_timestamp_t);

    return 0;
}

static 
PyObject*
DateVar_GetValue(
    dm_DateVar*     var,           // variable to determine value for
    unsigned        pos                // array position
)                       
{
    int             year;
    int             month;
    int             day;    

    year        = var->data[pos].year;
    month       = var->data[pos].month;
    day         = var->data[pos].day;

    if (year <= 0 || year > 9999)
    {
        PyErr_SetString(PyExc_ValueError, "year is out of range");
        return NULL;
    }    
    
    return PyDate_FromDate(year, month, day);    
}

static 
int 
DateVar_BindObjectValue(
    dm_DateVar*         var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
)
{
    DPIRETURN       rt = DSQL_SUCCESS;

    rt      = dpi_set_obj_val(hobj, val_nth, var->type->cType, (dpointer)&var->data[pos], var->indicator[pos]);
    if (Environment_CheckForError(var->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "vCursor_BindObjectValue():dpi_set_obj_val") < 0)
    {
        return -1;
    }

    return 0;
}

static 
PyObject*
TimeVar_GetValue(
    dm_TimeVar*     var,           // variable to determine value for
    unsigned        pos            // array position
)                       
{
    udint2          hour; 
    udint2          minute;
    udint2          second;

    hour    = var->data[pos].hour;
    minute  = var->data[pos].minute;
    second  = var->data[pos].second;

    return PyTime_FromTime(hour, minute, second, 0);
}

static 
int 
TimeVar_BindObjectValue(
    dm_TimeVar*         var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
)
{
    DPIRETURN       rt = DSQL_SUCCESS;

    rt      = dpi_set_obj_val(hobj, val_nth, var->type->cType, (dpointer)&var->data[pos], var->indicator[pos]);
    if (Environment_CheckForError(var->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "vCursor_BindObjectValue():dpi_set_obj_val") < 0)
    {
        return -1;
    }

    return 0;
}

static 
PyObject*
TimestampVar_GetValue(
    dm_TimestampVar*    var,           // variable to determine value for
    unsigned            pos                // array position
)                       
{
    int                 year;
    int                 month;
    int                 day;
    int                 hour; 
    int                 minute;
    int                 second;
    int                 usecond;

    year    = var->data[pos].year;
    month   = var->data[pos].month;
    day     = var->data[pos].day;
    hour    = var->data[pos].hour;
    minute  = var->data[pos].minute;
    second  = var->data[pos].second;
    usecond = var->data[pos].fraction / 1000;

    if (year <= 0 || year > 9999)
    {
        PyErr_SetString(PyExc_ValueError, "year is out of range");
        return NULL;
    }

    return PyDateTime_FromDateAndTime(year, month, day, hour, minute, second, usecond);
}

static 
int 
TimestampVar_BindObjectValue(
    dm_TimestampVar*    var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
)
{
    DPIRETURN       rt = DSQL_SUCCESS;

    rt      = dpi_set_obj_val(hobj, val_nth, var->type->cType, (dpointer)&var->data[pos], var->indicator[pos]);
    if (Environment_CheckForError(var->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "vCursor_BindObjectValue():dpi_set_obj_val") < 0)
    {
        return -1;
    }

    return 0;
}

static 
int 
TZVar_SetValue(
    dm_TZVar*           var,            // variable to set value for
    unsigned            pos,            // array position to set
    PyObject*           value           // value to set
)
{
    dm_Buffer           buffer;

    // populate the buffer and confirm the maximum size is not exceeded
    if (dmBuffer_FromObject(&buffer, value, var->environment->encoding) < 0)
        return -1;

    if (buffer.size)
    {
        memcpy(var->data + var->bufferSize * pos, buffer.ptr, buffer.size);
    }

    // keep a copy of the string
    var->indicator[pos]     = buffer.size;
    var->actualLength[pos]  = buffer.size;

    dmBuffer_Clear(&buffer);

    return 0;
}

static 
PyObject* 
TZVar_GetValue(
    dm_TZVar*           var,           // variable to determine value for
    unsigned            pos            // array position
)
{
    PyObject*           stringObj;
    char*               data;

    data = var->data + pos * var->bufferSize;

    if (var->type == &vt_TimeTZ || var->type == &vt_TimestampTZ) 
    {
        stringObj = dmString_FromEncodedString(data, var->actualLength[pos], var->environment->encoding);

        if (!stringObj)
            return NULL;

        return stringObj;
    }

    PyErr_SetString(g_ErrorException, "expecting time with time zone or timestamp with time zone data");
    return NULL;
}

static 
int 
TZVar_BindObjectValue(
    dm_TZVar*           var, 
    unsigned            pos, 
    dhobj               hobj,
    udint4              val_nth
)
{
    DPIRETURN       rt = DSQL_SUCCESS;

    rt      = dpi_set_obj_val(hobj, val_nth, var->type->cType, (dpointer)((sdbyte*)var->data + var->bufferSize * pos), var->indicator[pos]);
    if (Environment_CheckForError(var->environment, hobj, DSQL_HANDLE_OBJECT, rt, 
        "vCursor_BindObjectValue():dpi_set_obj_val") < 0)
    {
        return -1;
    }

    return 0;
}

