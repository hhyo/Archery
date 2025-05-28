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
#define BFILE_ID_LEN                10      //SESS的注册编号长度
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

/*常规变量定义，其他变量类型都以此结构进行扩展*/
typedef struct{
    dmVar_HEAD
    void *data;	    /*变量数据*/
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
    InitializeProc 	    initializeProc;		/*初始化，比如LOB类型的句柄申请等*/
    FinalizeProc 	    finalizeProc;		/*销毁，对应LOB类型的句柄释放等*/
    PreDefineProc 	    preDefineProc;	    /*绑定列之前处理*/    
    PreFetchProc 	    preFetchProc;		/*执行fetch之前处理*/
    IsNullProc 		    isNullProc;		    /*NULL值处理*/
    SetValueProc 	    setValueProc;		/*写值操作，Python到vt的转换*/
    GetValueProc 	    getValueProc;		/*读值操作，vt待Python的转换*/
    GetBufferSizeProc   getBufferSizeProc;	/*计算缓存大小操作*/
    BindObjectValueProc bindObjectValueProc;    /*OBJECT属性赋值操作*/
    PyTypeObject *	    pythonType;		    /*对应自定义Python类型对象*/
    sdint2 			    cType;			    /*对应绑定绑定C类型（SQL_C_XXX*/    
    udint4 			    size;				/*类型大小，相当于sizeof*/
    int 				isCharacterData;	/*是否为字符型数据，如CLOB和BLOB*/
    int 				isVariableLength;	/*是否变长数据*/
    int 				canBeCopied;		/*是否允许copy*/
    int 				canBeInArray;		/*是否可以作为数组成员*/
} dm_VarType;

dm_VarType*
dmVar_TypeBySQLType (
    udint2      sqlType,             // SQL type, SQL_XXX
    int         value_flag           // 仅LOB类型有效，用于判断是取LOB对象还是取LOB对象中的值
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
    unsigned        ipos             /*参数绑定序号 1-based*/
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
    dpi_interval_t* data;   /* 日-时间间隔类型，可对应到python的timedelta方法*/
} dm_IntervalVar;

typedef struct {
    dmVar_HEAD
    sdbyte*         data;   /* 年-月间隔类型，用字符串形式*/
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
    sdbyte*             data;  /* 时区类型，以字符串形式存放 */
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
    sdint4*     data;   /* 1/2/4字节长度，对应byte/tinyint/smallint/int类型 */
} dm_NumberVar;

typedef struct {
    dmVar_HEAD
    sdbyte*     data;   /* bigint，对应python的Py_Long_Long相关方法，由于低版本中实现不完整，为方便处理，统一用字符串类型来表示 */
} dm_BigintVar;

typedef struct {
    dmVar_HEAD
    sdbyte*     data;   /*base64类型 */
} dm_Base64Var;

typedef struct {
    dmVar_HEAD
    double*     data;   /* float/double/double precision 类型 */
} dm_DoubleVar;

typedef struct {
    dmVar_HEAD
    sdbyte*     data;   /* real类型，dpi接口映射为C的float类型，但python只支持双精度double类型，为避免类型转换导致的精度丢失，改用字符串处理 */
} dm_FloatVar;

typedef struct {
    dmVar_HEAD
    sdbyte*     data;   /* numeric/number/decimal/dec 类型 */
} dm_NumberStrVar;

//-----------------------------------------------------------------------------
// long type
//-----------------------------------------------------------------------------
extern  dm_VarType    vt_LongBinary;
extern  dm_VarType    vt_LongString;

typedef struct {
    dmVar_HEAD
    char *data; /** 前4个字节为有效数据长度 **/
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

    PyObject*           varValue;   /** 属性值对象 **/
    PyObject*			attributes; /** 结构对象（class/record）各成员的属性信息或者数组对象的元素类型，为一个LIST对象，LIST长度对应field_count **/    
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
    dhobj*          data;       /** 对象类型的hdobj数据句柄 **/    
    dhobjdesc		desc;       /** 对象本身的dhobjdesc描述句柄 **/
    dm_Cursor*      cursor;
    PyObject*       exObjects;  /** 通过绑定参数进来的OJBECT对象链表 **/
} dm_ObjectVar;

int
ObjectVar_GetParamDescAndObjHandles(
    dm_ObjectVar*   self,            // variable to set up    
    dhdesc          hdesc_param,
    sdint2          pos              // position in define list，1-based
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
    dm_ObjectVar*       refered_objVar; /** 作为列值或者输出或者输入参数引用的OBJECTVar对象 **/
    udint8              cursor_execNum; /** 关联cursor执行了次数 **/
    dm_Connection*      connection;
    dm_ObjectType*      objectType;
    PyObject*           objectValue;    /** 与Type中属性attributes一一对应 **/    
    dhobj               hobj;
    dhdesc              hobjdesc;  /** 若refered_objVar != NULL，则与其中的desc值相等 **/
    udint4              value_count;
    dm_Cursor*          ownCursor;    
    int                 MatchHandle_execd; /** 是否执行过setvalue **/
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
