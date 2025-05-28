/******************************************************
file:
    var.h
purpose:
    all struct info in DmPython
interface:
    {}
history:
    Date        Who         RefDoc      Memo
    2015-6-4    shenning                Created
*******************************************************/

#ifndef _STRCT_H
#define _STRCT_H

#include "py_Dameng.h"

#include "DPI.h"
#include "DPIext.h"
#include "DPItypes.h"

/** 参数描述信息结构 **/
typedef struct{
    sdint2      param_type;     /* 参数类型，INPUT/ OUTPUT / INPUT_OUTPUT */

    sdbyte      name[128 + 1];  /* 参数名称 */
    sdint4      namelen;        /* 参数名称长度 */

    sdint2		sql_type;
    ulength		prec;	
    sdint2		scale;
    sdint2		nullable;
}DmParamDesc;

/** 列描述信息结构 **/
typedef struct{
    sdbyte		name[128 + 1];
    sdint2		nameLen;

    sdint2		sql_type;
    ulength		prec;	
    sdint2		scale;
    sdint2		nullable; 

    slength     display_size;
}DmColDesc;

//-----------------------------------------------------------------------------
// structure for the Python type
//-----------------------------------------------------------------------------
typedef struct {
	PyObject_HEAD
	sdint4		code;
	sdint4		offset;
	PyObject    *message;
	char        *context;
} dm_Error;


//-----------------------------------------------------------------------------
// structure for the Python type
//-----------------------------------------------------------------------------
typedef struct {
	PyObject_HEAD
	dhenv		    handle;
	sdbyte		    encoding[128];     	/** 本地当前使用编码名称 **/
	sdbyte		    nencoding[128];
	udint2		    maxBytesPerCharacter;
    
    sdint4          local_code;         /** 本地当前使用的编码编号，与encoding相对应 **/
    sdint4          local_langid;      	/** 本地当前使用的语言类型 **/

    PyObject**      warning;            /* 指向connection上的警告信息 */
} dm_Environment;


//-----------------------------------------------------------------------------
// structure for the Python type "Connection"
//-----------------------------------------------------------------------------
typedef struct {
	PyObject_HEAD
	dhcon			hcon;					// 连接句柄
	dm_Environment  *environment;
	PyObject		*username;
    PyObject        *schema;
	PyObject		*password;
	PyObject		*server;
	PyObject     	*port;	
    PyObject     	*dsn;	
	PyObject		*inputTypeHandler;
	PyObject		*outputTypeHandler;
	PyObject		*version;
    PyObject		*server_status;
    PyObject		*explain;
    PyObject		*warning;
    PyObject        *catalog;
	sdint2			autocommit;
	sdint2			commitMode;
    sdint4          cursor_class;
	sdint2			isConnected;			// 是否已经连接，1 连接上，0 未连接上
} dm_Connection;


//-----------------------------------------------------------------------------
// structure for the Python type "Cursor"
//-----------------------------------------------------------------------------
typedef struct {
	PyObject_HEAD
	dhstmt              handle;	        // 语句句柄
    dhdesc	            hdesc_col;		// 列描述句柄
	dhdesc	            hdesc_param;	// 参数描述句柄
    PyObject*           col_variables;  // 列绑定变量
    PyObject*           param_variables;    /*参数绑定变量*/
	dm_Connection*      connection;
	dm_Environment*     environment;
	DmColDesc*	        bindColDesc;		// 绑定列描述
	udint2			    colCount;
	DmParamDesc*        bindParamDesc;		// 绑定参数信息
	udint2			    paramCount;		// 需绑定参数的个数
	PyObject*           statement;	
	PyObject*           rowFactory;
	PyObject*           inputTypeHandler;
	PyObject*           outputTypeHandler;
	ulength	            arraySize;			// 默认结果集行数组缓存的大小
    ulength             org_arraySize;      /** 上次有效的结果集获取行数 **/
    ulength             bindArraySize;      // 绑定参数默认行数
    ulength             org_bindArraySize;  /** 上次有效的参数绑定行数 **/
	int                 numbersAsStrings;
	int                 setInputSizes;		// 是否调用过setinputsizes
	int                 outputSize;
	int                 outputSizeColumn;
	sdint8              rowCount;	  // 已经从结果集中取得的行数
	ulength             actualRows;		// 一次fetch结果集中实际取得的行数
	ulength	            rowNum;			// 一次fetch操作中所在行号	
	sdint8	            totalRows;		// 结果集中总行数
	int                 statementType;
	int                 isDML;
	int                 isOpen;   
    int                 isClosed;
	PyObject*           description;
	PyObject*           map_name_to_index;
    PyObject*           column_names;
    PyObject*           lastrowid_obj;  /** 对应标准中lastrowid属性 **/
    PyObject*           execid_obj;     /** sql语句执行id **/
    int                 with_rows;      /** 是否存在结果集 **/
    udint8              execute_num;    /** 记录当前句柄，在创建后执行次数 **/
    ulength	            output_stream;    // 是否使用流式输出类型绑定参数
    int                 is_iter;        /** 是否使用迭代器 **/
    int                 outparam_num;   //输出参数个数
    PyObject**          param_value;    //输出参数值
} dm_Cursor;

typedef struct
{
	// A Row must act like a sequence (a tuple of results) to meet the DB API specification, but we also allow values
	// to be accessed via lowercased column names.  We also supply a `columns` attribute which returns the list of
	// column names.

	PyObject_HEAD

	// cursor.description, accessed as _description
	PyObject* description;

	// A Python dictionary mapping from column name to a PyInteger, used to access columns by name.
	PyObject* map_name_to_index;

	// The number of values in apValues.
	Py_ssize_t cValues;
	// The column values, stored as an array.
	PyObject** apValues;
}Row;

void
Cursor_Data_init();

sdint2 
Cursor_FreeHandle(
    dm_Cursor*      self,       // cursor object
	int             raiseException      // raise an exception, if necesary?
);

PyObject*
Connection_NewCursor_Inner(
    dm_Connection*          self, 
    PyObject*				args
 );

PyObject*
Cursor_New(    
    dm_Connection*     connection
);

void
Cursor_free_inner(
    dm_Cursor*     self
);

#endif