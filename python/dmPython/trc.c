#include "trc.h"
#include<fcntl.h>
#include<sys/types.h>
#include<sys/stat.h>
#include <stdio.h>
#include <time.h> 
#include "py_Dameng.h"


#define MAX_TRACE_MASSEGE_LEN (2048)
#define MAX_TIMESTAMP_STR_LEN (32)
#define TIMESTAMPE_BUF_LEN    (MAX_TIMESTAMP_STR_LEN + 1)

udint4  dmpython_trace_mod = DMPYTHON_TRACE_OFF;

#ifdef WIN32 
#define LOCALTIME(tm,ti)  localtime_s(tm,ti) 
#else 
#define LOCALTIME(tm,ti)  localtime_r(ti,tm) 
#endif 

static
void
dpy_get_timestamp(
    sdbyte*       buf
)
{
    struct tm	cur_time;
    time_t		ltime;
    
    if (buf == NULL)
    {
        return;
    }
    
    time(&ltime);
    LOCALTIME(&cur_time, &ltime);
   
    sprintf(buf, "%04d-%02d-%02d %02d:%02d:%02d",
        cur_time.tm_year + 1900, 
        cur_time.tm_mon + 1, 
        cur_time.tm_mday, 
        cur_time.tm_hour, 
        cur_time.tm_min, 
        cur_time.tm_sec);
}

void
dpy_trace(
    PyObject*       statement,
    PyObject*       args,
    sdbyte*         info,
    ...
)
{    
    sdbyte          timestamp[TIMESTAMPE_BUF_LEN];    
    va_list         vl;
    char*           statementStr = NULL;
    char*           argsStr = NULL;
    PyObject*       tempObj;
    FILE*           fp;

    // 打开文件
    fp = fopen(DMPYTHON_TRACE_FILE, "a+");
    if (fp == NULL)
    {
        return;
    }

    // 写时间戳
    dpy_get_timestamp(timestamp);
    fwrite(timestamp, 1, strlen(timestamp), fp);
    fwrite("\t", 1, 1, fp);

    // 写info信息
    va_start(vl, info);
    vfprintf(fp, info, vl);
    va_end(vl);

    // 写statement
    if (statement != NULL && statement != Py_None)
    {
        tempObj = PyObject_Str(statement);
        if (tempObj != NULL)
        {
            statementStr = py_String_asString(tempObj);
            Py_DECREF(tempObj);
            fwrite(statementStr, 1, strlen(statementStr), fp);
            fwrite("\n", 1, 1, fp);
        }
}
    // 写args
    if (args != NULL && args != Py_None)
    {
        tempObj = PyObject_Str(args);
        if (tempObj != NULL)
        {
            argsStr = py_String_asString(tempObj);
            Py_DECREF(tempObj);
            fwrite(argsStr, 1, strlen(argsStr), fp);
            fwrite("\n", 1, 1, fp);
        }
    }
    fwrite("\n", 1, 1, fp);
    //关闭文件
    fflush(fp);
    fclose(fp);
}

