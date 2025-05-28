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

/** ����������Ϣ�ṹ **/
typedef struct{
    sdint2      param_type;     /* �������ͣ�INPUT/ OUTPUT / INPUT_OUTPUT */

    sdbyte      name[128 + 1];  /* �������� */
    sdint4      namelen;        /* �������Ƴ��� */

    sdint2		sql_type;
    ulength		prec;	
    sdint2		scale;
    sdint2		nullable;
}DmParamDesc;

/** ��������Ϣ�ṹ **/
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
	sdbyte		    encoding[128];     	/** ���ص�ǰʹ�ñ������� **/
	sdbyte		    nencoding[128];
	udint2		    maxBytesPerCharacter;
    
    sdint4          local_code;         /** ���ص�ǰʹ�õı����ţ���encoding���Ӧ **/
    sdint4          local_langid;      	/** ���ص�ǰʹ�õ��������� **/

    PyObject**      warning;            /* ָ��connection�ϵľ�����Ϣ */
} dm_Environment;


//-----------------------------------------------------------------------------
// structure for the Python type "Connection"
//-----------------------------------------------------------------------------
typedef struct {
	PyObject_HEAD
	dhcon			hcon;					// ���Ӿ��
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
	sdint2			isConnected;			// �Ƿ��Ѿ����ӣ�1 �����ϣ�0 δ������
} dm_Connection;


//-----------------------------------------------------------------------------
// structure for the Python type "Cursor"
//-----------------------------------------------------------------------------
typedef struct {
	PyObject_HEAD
	dhstmt              handle;	        // �����
    dhdesc	            hdesc_col;		// ���������
	dhdesc	            hdesc_param;	// �����������
    PyObject*           col_variables;  // �а󶨱���
    PyObject*           param_variables;    /*�����󶨱���*/
	dm_Connection*      connection;
	dm_Environment*     environment;
	DmColDesc*	        bindColDesc;		// ��������
	udint2			    colCount;
	DmParamDesc*        bindParamDesc;		// �󶨲�����Ϣ
	udint2			    paramCount;		// ��󶨲����ĸ���
	PyObject*           statement;	
	PyObject*           rowFactory;
	PyObject*           inputTypeHandler;
	PyObject*           outputTypeHandler;
	ulength	            arraySize;			// Ĭ�Ͻ���������黺��Ĵ�С
    ulength             org_arraySize;      /** �ϴ���Ч�Ľ������ȡ���� **/
    ulength             bindArraySize;      // �󶨲���Ĭ������
    ulength             org_bindArraySize;  /** �ϴ���Ч�Ĳ��������� **/
	int                 numbersAsStrings;
	int                 setInputSizes;		// �Ƿ���ù�setinputsizes
	int                 outputSize;
	int                 outputSizeColumn;
	sdint8              rowCount;	  // �Ѿ��ӽ������ȡ�õ�����
	ulength             actualRows;		// һ��fetch�������ʵ��ȡ�õ�����
	ulength	            rowNum;			// һ��fetch�����������к�	
	sdint8	            totalRows;		// �������������
	int                 statementType;
	int                 isDML;
	int                 isOpen;   
    int                 isClosed;
	PyObject*           description;
	PyObject*           map_name_to_index;
    PyObject*           column_names;
    PyObject*           lastrowid_obj;  /** ��Ӧ��׼��lastrowid���� **/
    PyObject*           execid_obj;     /** sql���ִ��id **/
    int                 with_rows;      /** �Ƿ���ڽ���� **/
    udint8              execute_num;    /** ��¼��ǰ������ڴ�����ִ�д��� **/
    ulength	            output_stream;    // �Ƿ�ʹ����ʽ������Ͱ󶨲���
    int                 is_iter;        /** �Ƿ�ʹ�õ����� **/
    int                 outparam_num;   //�����������
    PyObject**          param_value;    //�������ֵ
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