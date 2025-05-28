/******************************************************
file:
    var_pub.h
purpose:
    python type define for all DM Variables public function in dmPython
interface:
    {}
history:
    Date        Who         RefDoc      Memo
    2015-6-4    shenning                Created
*******************************************************/

#ifndef _VAR_PUB_H
#define _VAR_PUB_H

#include "strct.h"
#include "object.h"

#define NAMELEN                     128
#define MAX_PATH_LEN                256
#define BFILE_ID_LEN                10      //SESS��ע���ų���
#define END                         0
#define	SPACE				        32	/*   */

#ifdef DM64
typedef sdint8          int3264;
#else
typedef sdint4          int3264;
#endif


//-----------------------------------------------------------------------------
// define structure common to all variables
//-----------------------------------------------------------------------------
struct _dm_VariableType;
#define dmVar_HEAD \
    PyObject_HEAD \
    DmParamDesc*        paramdesc;\
    DmColDesc*          coldesc;\
    dhstmt		        boundCursorHandle; \
    udint2 		        boundPos; \
    dm_Environment*     environment; \
    udint4 				allocatedElements; \
    udint4				actualElements; \
    udint4 				internalFetchNum; \
    int 				isArray; \
    int 				isAllocatedInternally; \
    slength 			*indicator; \
    slength 			*actualLength; \
    udint4 				size; \
    udint4				bufferSize; \
    dm_Connection*      connection;\
    ulength	            output_stream;\
    struct _dm_VariableType*    type;

/*����������壬�����������Ͷ��Դ˽ṹ������չ*/
typedef struct{
    dmVar_HEAD
    void *data;	    /*��������*/
}dm_Var;

//-----------------------------------------------------------------------------
// define function types for the common actions that take place on a variable
//-----------------------------------------------------------------------------
typedef int (*InitializeProc)(dm_Var*, dm_Cursor*);
typedef void (*FinalizeProc)(dm_Var*);
typedef int (*PreDefineProc)(dm_Var*, dhdesc, sdint2);
typedef int (*PreFetchProc)(dm_Var*, dhdesc, sdint2);
typedef int (*IsNullProc)(dm_Var*, unsigned);
typedef int (*SetValueProc)(dm_Var*, unsigned, PyObject*);
typedef PyObject * (*GetValueProc)(dm_Var*, unsigned);
typedef udint4  (*GetBufferSizeProc)(dm_Var*);
typedef DPIRETURN (*BindObjectValueProc)(dm_Var*, unsigned, dhobj, udint4);

typedef struct _dm_VariableType {
    InitializeProc 	    initializeProc;		/*��ʼ��������LOB���͵ľ�������*/
    FinalizeProc 	    finalizeProc;		/*���٣���ӦLOB���͵ľ���ͷŵ�*/
    PreDefineProc 	    preDefineProc;	    /*����֮ǰ����*/    
    PreFetchProc 	    preFetchProc;		/*ִ��fetch֮ǰ����*/
    IsNullProc 		    isNullProc;		    /*NULLֵ����*/
    SetValueProc 	    setValueProc;		/*дֵ������Python��vt��ת��*/
    GetValueProc 	    getValueProc;		/*��ֵ������vt��Python��ת��*/
    GetBufferSizeProc   getBufferSizeProc;	/*���㻺���С����*/
    BindObjectValueProc bindObjectValueProc;    /*OBJECT���Ը�ֵ����*/
    PyTypeObject *	    pythonType;		    /*��Ӧ�Զ���Python���Ͷ���*/
    sdint2 			    cType;			    /*��Ӧ�󶨰�C���ͣ�SQL_C_XXX*/    
    udint4 			    size;				/*���ʹ�С���൱��sizeof*/
    int 				isCharacterData;	/*�Ƿ�Ϊ�ַ������ݣ���CLOB��BLOB*/
    int 				isVariableLength;	/*�Ƿ�䳤����*/
    int 				canBeCopied;		/*�Ƿ�����copy*/
    int 				canBeInArray;		/*�Ƿ������Ϊ�����Ա*/
} dm_VarType;

dm_VarType*
dmVar_TypeBySQLType (
    udint2      sqlType,             // SQL type, SQL_XXX
    int         value_flag           // ��LOB������Ч�������ж���ȡLOB������ȡLOB�����е�ֵ
);

dm_VarType*
dmVar_TypeByValue(
    PyObject*       value,              // Python type
    udint4*         size               // size to use (OUT)    
);

//-----------------------------------------------------------------------------
// dmVar_TypeByPythonType()
//   Return a variable type given a Python type object or NULL if the Python
// type does not have a corresponding variable type.
//----------------------------------------------------------------------------- 
dm_VarType*
dmVar_TypeByPythonType(
    dm_Cursor*      cursor,         // cursor variable created for
    PyObject*       type            // Python type
);

dm_Var*
dmVar_New(
    dm_Cursor*          cursor,         /* cursor to associate variable with */
    udint4              numElements,    /* number of elements to allocate */
    dm_VarType*         type,           /* variable type */
    sdint4              size            /* used only for variable length types */
);

int 
dmVar_Bind(
    dm_Var*         var,     // variable to bind
    dm_Cursor*      cursor,  // cursor to bind to    
    udint2          pos      // position to bind to
);

int 
dmVar_Check(
    PyObject*       object  // Python object to check
);

dm_Var*
dmVar_NewByValue(
    dm_Cursor*      cursor,         // cursor to associate variable with
    PyObject*       value,          // Python value to associate
    unsigned        numElements,     // number of elements to allocate
    unsigned        ipos             /*��������� 1-based*/
);

dm_Var*
dmVar_NewByType(
    dm_Cursor*  cursor,         // cursor to associate variable with
    PyObject*   value,            // Python data type to associate
    unsigned    numElements        // number of elements to allocate
);

dm_Var*
dmVar_NewByVarType(
    dm_Cursor*          cursor,         // cursor to associate variable with
    dm_VarType*         varType,            // Python data type to associate
    unsigned            numElements,        // number of elements to allocate
    udint4              size            // buffer length to alloc
);

int
dmVar_IsNull(
    dm_Var*       var // variable to return the string for
);

int 
dmVar_SetValue(
    dm_Var*         var,        // variable to set
    udint4          arrayPos,   // array position
    PyObject*       value       // value to set
);

PyObject*
dmVar_GetValue(
    dm_Var*         var,      // variable to get the value for
    udint4          arrayPos  // array position
);

int
dmVar_BindObjectValue(
    dm_Var*         var,
    udint4          arrayPos,
    dhobj           obj_hobj,
    udint4          value_nth
);

dm_Var*
dmVar_Define(
    dm_Cursor*      cursor,         // cursor in use
    dhdesc          hdesc_col,
    udint2          position,       // position in define list
    udint4          numElements,    // number of elements to create
    udint2          varchar_flag    // whether used DSQL_ATTR_NLS_NUMERIC_CHARACTERS
);

int 
dmVar_Resize(
    dm_Var*         self,   // variable to resize
    unsigned        size    // new size to use
);

void
dmVar_Import();

int
dmVar_PutDataAftExec(
    dm_Var*         var,        // for variable to put data
    udint4          arrayPos    // array position
);

void
dmVar_Finalize(
    dm_Var*       self
);

//-----------------------------------------------------------------------------
// interval type
//-----------------------------------------------------------------------------
extern  dm_VarType    vt_Interval;
extern  dm_VarType    vt_YMInterval;

typedef struct {
    dmVar_HEAD
    dpi_interval_t* data;   /* ��-ʱ�������ͣ��ɶ�Ӧ��python��timedelta����*/
} dm_IntervalVar;

typedef struct {
    dmVar_HEAD
    sdbyte*         data;   /* ��-�¼�����ͣ����ַ�����ʽ*/
} dm_YMIntervalVar;

void
IntervalVar_import();

//-----------------------------------------------------------------------------
// date/time/timestamp type
//-----------------------------------------------------------------------------
extern  dm_VarType    vt_Date;
extern  dm_VarType    vt_Time;
extern  dm_VarType    vt_Timestamp;
extern  dm_VarType    vt_TimeTZ;
extern  dm_VarType    vt_TimestampTZ;

typedef struct {
    dmVar_HEAD
    dpi_date_t*         data;
} dm_DateVar;

typedef struct {
    dmVar_HEAD
    dpi_time_t*         data;
} dm_TimeVar;

typedef struct {
    dmVar_HEAD
    dpi_timestamp_t*    data;
} dm_TimestampVar;

typedef struct {
    dmVar_HEAD
    sdbyte*             data;  /* ʱ�����ͣ����ַ�����ʽ��� */
} dm_TZVar;

void
DateVar_import();


//-----------------------------------------------------------------------------
//  string type
//-----------------------------------------------------------------------------
extern  dm_VarType    vt_String;
extern  dm_VarType    vt_FixedChar;
extern  dm_VarType    vt_Binary;
extern  dm_VarType    vt_FixedBinary;

#if PY_MAJOR_VERSION < 3
extern  dm_VarType    vt_UnicodeString;
extern  dm_VarType    vt_FixedUnicodeChar;
#endif

typedef struct {
    dmVar_HEAD
    sdbyte*      data;
} dm_StringVar;


//-----------------------------------------------------------------------------
// number type
//-----------------------------------------------------------------------------
extern  dm_VarType    vt_Integer;
extern  dm_VarType    vt_Bigint;
extern  dm_VarType    vt_RowId;

extern  dm_VarType    vt_Double;
extern  dm_VarType    vt_Float;

extern  dm_VarType    vt_Boolean;
extern  dm_VarType    vt_NumberAsString;

typedef struct {
    dmVar_HEAD
    sdint4*     data;   /* 1/2/4�ֽڳ��ȣ���Ӧbyte/tinyint/smallint/int���� */
} dm_NumberVar;

typedef struct {
    dmVar_HEAD
    sdbyte*     data;   /* bigint����Ӧpython��Py_Long_Long��ط��������ڵͰ汾��ʵ�ֲ�������Ϊ���㴦��ͳһ���ַ�����������ʾ */
} dm_BigintVar;

typedef struct {
    dmVar_HEAD
    sdbyte*     data;   /*base64���� */
} dm_Base64Var;

typedef struct {
    dmVar_HEAD
    double*     data;   /* float/double/double precision ���� */
} dm_DoubleVar;

typedef struct {
    dmVar_HEAD
    sdbyte*     data;   /* real���ͣ�dpi�ӿ�ӳ��ΪC��float���ͣ���pythonֻ֧��˫����double���ͣ�Ϊ��������ת�����µľ��ȶ�ʧ�������ַ������� */
} dm_FloatVar;

typedef struct {
    dmVar_HEAD
    sdbyte*     data;   /* numeric/number/decimal/dec ���� */
} dm_NumberStrVar;

//-----------------------------------------------------------------------------
// long type
//-----------------------------------------------------------------------------
extern  dm_VarType    vt_LongBinary;
extern  dm_VarType    vt_LongString;

typedef struct {
    dmVar_HEAD
    char *data; /** ǰ4���ֽ�Ϊ��Ч���ݳ��� **/
} dm_LongVar;

int
vLong_PutData(
    dm_LongVar*     self,    // variable to get buffer size
    udint4          arrayPos    // array position
);

//-----------------------------------------------------------------------------
// BFILE type
//-----------------------------------------------------------------------------
extern  dm_VarType    vt_BFILE;

typedef struct {
    dmVar_HEAD
    void*               data;
    unsigned            pos;
} dm_BFileVar;

typedef struct {
    PyObject_HEAD
    dm_BFileVar*    BFileVar;
    unsigned        pos;
} dm_ExternalBFile;

//-----------------------------------------------------------------------------
// LOB type
//-----------------------------------------------------------------------------
extern  dm_VarType    vt_BLOB;
extern  dm_VarType    vt_CLOB;

typedef struct {
    dmVar_HEAD
    dhloblctr*			data;
    PyObject*           exLobs;    
} dm_LobVar;

int 
vLobVar_Write(
    dm_LobVar*      var,        // variable to perform write against
    unsigned        position,   // position to perform write against
    PyObject*       dataObj,    // data object to write into LOB
    udint4          start_pos,     // offset into variable
    udint4*         amount      // amount to write
);

//-----------------------------------------------------------------------------
// external LOB type
//-----------------------------------------------------------------------------
typedef struct {
    PyObject_HEAD
    dm_LobVar*  lobVar;
    unsigned    pos;
    unsigned    internalFetchNum;
} dm_ExternalLobVar;


PyObject*
ExternalLobVar_New(
    dm_LobVar*      var,    // variable to encapsulate
    unsigned        pos     // position in array to encapsulate
);

PyObject*
exLobVar_BytesToString(
    PyObject*       bsObject,
    slength         len
);

PyObject *exLobVar_Str(dm_ExternalLobVar*);
PyObject*
exLobVar_Bytes(
    dm_ExternalLobVar* var  // variable to return the string for
);  

//-----------------------------------------------------------------------------
// Cursor variable type
//-----------------------------------------------------------------------------
extern  dm_VarType vt_Cursor;

typedef struct {
    dmVar_HEAD
    dhstmt*         data;
    PyObject*       cursors;
} dm_CursorVar;

//-----------------------------------------------------------------------------
// Object variable type
//-----------------------------------------------------------------------------
typedef struct {
    PyObject_HEAD
    dm_Connection*      connection;
    dm_Environment*     environment;
    PyObject*			schema;
    PyObject*			name;    
    sdint2              sql_type;
    sdint2              prec;
    sdint2              scale;         

    PyObject*           varValue;   /** ����ֵ���� **/
    PyObject*			attributes; /** �ṹ����class/record������Ա��������Ϣ������������Ԫ�����ͣ�Ϊһ��LIST����LIST���ȶ�Ӧfield_count **/    
} dm_ObjectType;

typedef struct {
    PyObject_HEAD
    dm_Connection*      connection;
    PyObject*			schema;
    PyObject*			name;    
    dm_ObjectType*      ObjType;
} dm_ObjectAttribute;

dm_ObjectType* ObjectType_New(dm_Connection*, dhobjdesc);

int
ObjectType_IsObjectType(
    dm_ObjectType* self    // object type to return the string for
);

//-----------------------------------------------------------------------------
// Object type
//-----------------------------------------------------------------------------
extern dm_VarType vt_Object;
extern dm_VarType vt_Record;
extern dm_VarType vt_Array;
extern dm_VarType vt_SArray;

typedef struct {
    dmVar_HEAD
    dhobj*          data;       /** �������͵�hdobj���ݾ�� **/    
    dhobjdesc		desc;       /** �������dhobjdesc������� **/
    dm_Cursor*      cursor;
    PyObject*       exObjects;  /** ͨ���󶨲���������OJBECT�������� **/
} dm_ObjectVar;

int
ObjectVar_GetParamDescAndObjHandles(
    dm_ObjectVar*   self,            // variable to set up    
    dhdesc          hdesc_param,
    sdint2          pos              // position in define list��1-based
);

int
ObjectVar_SetValue_Inner(
    dm_ObjectVar*   var, 
    unsigned        pos, 
    dhobj           hobj,
    dhobjdesc       hobjdesc
);

PyObject*
ObjectVar_GetBoundExObj(
    dm_ObjectVar*       var, 
    unsigned            pos
);

//-----------------------------------------------------------------------------
// external Object type
//-----------------------------------------------------------------------------
typedef struct {
    PyObject_HEAD   
    dm_ObjectVar*       refered_objVar; /** ��Ϊ��ֵ���������������������õ�OBJECTVar���� **/
    udint8              cursor_execNum; /** ����cursorִ���˴��� **/
    dm_Connection*      connection;
    dm_ObjectType*      objectType;
    PyObject*           objectValue;    /** ��Type������attributesһһ��Ӧ **/    
    dhobj               hobj;
    dhdesc              hobjdesc;  /** ��refered_objVar != NULL���������е�descֵ��� **/
    udint4              value_count;
    dm_Cursor*          ownCursor;    
    int                 MatchHandle_execd; /** �Ƿ�ִ�й�setvalue **/
} dm_ExternalObjectVar;

PyObject*
ExObjVar_New_FromObjVar(    
    dm_ObjectVar*   objVar,    
    dhobjdesc       hobjdesc,
    dhobj           hobj
);

int
ExObjVar_MatchCheck(
    dm_ExternalObjectVar*   self,
    dhobjdesc               hobjdesc,
    dhobj                   hobj,
    udint4*                 value_count
);

PyObject*
exBFileVar_NEW(
    dm_BFileVar*    var,        // variable to determine value for
    unsigned        pos         // array position
);

#endif
