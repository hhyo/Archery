/******************************************************
file:
    vInterval.h
purpose:
    python type define for DM interval variables in dmPython
interface:
    {}
history:
    Date        Who         RefDoc      Memo
    2015-6-8    shenning                Created
*******************************************************/

#include "py_Dameng.h"
#include "var_pub.h"
#include <datetime.h>
#include "Error.h"
#include "Buffer.h"

//-----------------------------------------------------------------------------
// Declaration of interval variable functions.
//-----------------------------------------------------------------------------
static int IntervalVar_SetValue(dm_IntervalVar*, unsigned, PyObject*);
static PyObject* IntervalVar_GetValue(dm_IntervalVar*, unsigned);
static int IntervalVar_BindObjectValue(dm_IntervalVar*, unsigned, dhobj, udint4);

static int YMIntervalVar_SetValue(dm_YMIntervalVar*, unsigned, PyObject*);
static PyObject* YMIntervalVar_GetValue(dm_YMIntervalVar*, unsigned);
static int YMIntervalVar_BindObjectValue(dm_YMIntervalVar*, unsigned, dhobj, udint4);

//-----------------------------------------------------------------------------
// Python type declarations
//-----------------------------------------------------------------------------
PyTypeObject g_IntervalVarType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.INTERVAL",                // tp_name
    sizeof(dm_IntervalVar),             // tp_basicsize
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

PyTypeObject g_YMIntervalVarType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "dmPython.YEAR_MONTH_INTERVAL",     // tp_name
    sizeof(dm_YMIntervalVar),           // tp_basicsize
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
dm_VarType vt_Interval = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) IntervalVar_SetValue,
    (GetValueProc) IntervalVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)IntervalVar_BindObjectValue,
    &g_IntervalVarType,                 // Python type
    DSQL_C_INTERVAL_DAY_TO_SECOND,      // CType    
    sizeof(dpi_interval_t),             // element length (default)
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};

dm_VarType vt_YMInterval = {
    (InitializeProc) NULL,
    (FinalizeProc) NULL,
    (PreDefineProc) NULL,
    (PreFetchProc) NULL,
    (IsNullProc) NULL,
    (SetValueProc) YMIntervalVar_SetValue,
    (GetValueProc) YMIntervalVar_GetValue,
    (GetBufferSizeProc) NULL,
    (BindObjectValueProc)YMIntervalVar_BindObjectValue,
    &g_YMIntervalVarType,               // Python type
    DSQL_C_NCHAR,                       // CType，对应字符串形式
    64,                                 // element length (default)
    0,                                  // is character data
    0,                                  // is variable length
    1,                                  // can be copied
    1                                   // can be in array
};

void
IntervalVar_import()
{
    PyDateTime_IMPORT;
}


//-----------------------------------------------------------------------------
// IntervalVar_SetValue()
//   Set the value of the variable.
//-----------------------------------------------------------------------------
static
int 
IntervalVar_SetValue(
    dm_IntervalVar*     var,    // variable to set value for
    unsigned            pos,    // array position to set
    PyObject*           value   // value to set
)                    
{
    int                 days;
    int                 hours;
    int                 minutes;
    int                 seconds;
    int                 microseconds;
    int                 fraction; /** 纳秒 **/
    sdint8              total_seconds;

    PyDateTime_Delta*   delta;      
    dpi_interval_t*     ds;

    if (!PyDelta_Check(value)) 
    {
        PyErr_SetString(PyExc_TypeError, "expecting timedelta data");
        return -1;
    }

    delta       = (PyDateTime_Delta*) value;
    
    days        = delta->days;
    hours       = delta->seconds / 3600;
    minutes     = (delta->seconds - hours * 3600) / 60;
    seconds     = delta->seconds - hours * 3600 - minutes * 60;
    fraction    = delta->microseconds * 1000;
    
    ds          = &var->data[pos];

    ds->interval_type   = DSQL_IS_DAY_TO_SECOND;
    ds->interval_sign   = days >= 0 ? 0 : 1;

    //delta的日有正负值，时，分，秒，微秒都只有正值，而interval_sign表示的是整个intval是正值还是负值
    //因此delta的日为负值时不能表示整个intval是负值，需要进行换算
    //例如days = -1, hours = 23表示的是-1小时，而不是-1天23小时
    //delta传进来时是已经换算成各个单位能表示的最大值了，day如果为负，整个的结果最终必为负的
    if (days < 0)
    {
        total_seconds       = delta->days * 24 * 3600 + delta->seconds;

        if (total_seconds < 0 && delta->microseconds > 0)
        {
            //例如，最终算出来是-1s, +30micros,实际结果应该是0s, -999970 micros
            total_seconds++;
            microseconds    = 1000000 - delta->microseconds;
        }
        else
        {
            microseconds    = delta->microseconds;
        }

        seconds             = total_seconds % 60;
        total_seconds       -= seconds;

        minutes             = (total_seconds / 60) % 60;
        total_seconds       -= minutes * 60;

        hours               = (total_seconds / 3600) % 24;
        total_seconds       -= hours * 3600;

        days                = total_seconds / (3600 * 24);
        fraction            = microseconds * 1000;
    }

    ds->intval.day_second.day       = (udint4)abs(days);
    ds->intval.day_second.hour      = (udint4)abs(hours);
    ds->intval.day_second.minute    = (udint4)abs(minutes);
    ds->intval.day_second.second    = (udint4)abs(seconds);
    ds->intval.day_second.fraction  = (udint4)abs(fraction);
    

    var->indicator[pos]     = sizeof(dpi_interval_t);
    var->actualLength[pos]  = sizeof(dpi_interval_t);
    
    return 0;
}


//-----------------------------------------------------------------------------
// IntervalVar_GetValue()
//   Returns the value stored at the given array position.
//-----------------------------------------------------------------------------
static
PyObject*
IntervalVar_GetValue(
    dm_IntervalVar*     var,    // variable to determine value for
    unsigned            pos     // array position
)                       
{
    int                 days;    
    int                 seconds;
    int                 microseconds;
    dpi_interval_t*     ds;
    sdint8              total_seconds;

    ds          = &var->data[pos];
    days        = ds->intval.day_second.day;
    
    seconds     = ds->intval.day_second.hour * 3600 + 
                  ds->intval.day_second.minute * 60 + 
                  ds->intval.day_second.second;
    microseconds= ds->intval.day_second.fraction / 1000;

    //interval_sign=1表示的是整个interval都为负数，而转换为delta时，只有days可以是负数，其他位用正数
    if (ds->interval_sign == 1)
    {
        //intv上的day,hour,minute,seconds都是正值，sign用来区分正负
        total_seconds   = days * 24 * 60 * 60 + seconds;        //用正值表示负的总秒数

        //microseconds转成正值
        microseconds    = 1000000 - microseconds;               //前面算出来的微秒是正值，但sign=1时表示的是负多少微秒，转成正值
        total_seconds++;

        //seconds转成正值
        seconds         = (24 * 60 * 60) - total_seconds % (24 * 60 * 60);

        days            = total_seconds / (24 * 60 * 60) + 1;
        days            = days * (-1);
    }

    return PyDelta_FromDSU(days, seconds, microseconds);
}

static 
int 
IntervalVar_BindObjectValue(
    dm_IntervalVar*     var, 
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
YMIntervalVar_SetValue(
    dm_YMIntervalVar*   var, 
    unsigned            pos, 
    PyObject*           value
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
YMIntervalVar_GetValue(
    dm_YMIntervalVar*   var, 
    unsigned            pos
)
{
    PyObject*           stringObj;
    char*               data;

    data = var->data + pos * var->bufferSize;

    if (var->type == &vt_YMInterval) 
    {
        stringObj = dmString_FromEncodedString(data, var->actualLength[pos], var->environment->encoding);

        if (!stringObj)
            return NULL;

        return stringObj;
    }

    PyErr_SetString(g_ErrorException, "expecting year-month interval data");
    return NULL;    
}

static 
int 
YMIntervalVar_BindObjectValue(
    dm_YMIntervalVar*   var, 
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

