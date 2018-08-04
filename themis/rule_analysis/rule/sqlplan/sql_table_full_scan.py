# -*- coding: utf-8 -*-

from .decorator import mongo_query

rule = {    
    "db_type" : "O",
    "exclude_obj_type" : [ 
        "SQL_ID", 
        "PLAN_HASH_VALUE"
    ],
    "input_parms" : [ 
        {
            "parm_desc" : "表物理大小",
            "parm_name" : "table_phy_size",
            "parm_unit" : "MB",
            "parm_value" : 2048
        }, 
        {
            "parm_desc" : "表行数",
            "parm_name" : "table_row_num",
            "parm_value" : 100000
        }
    ],
    "max_score" : "20",
    "obj_info_type" : "TABLE",
    "output_parms" : [ 
        {
            "parm_desc" : "SQL_ID",
            "parm_name" : "SQL_ID"
        }, 
        {
            "parm_desc" : "PLAN_HASH_VALUE",
            "parm_name" : "PLAN_HASH_VALUE"
        }, 
        {
            "parm_desc" : "SQL_TEXT",
            "parm_name" : "SQL_TEXT"
        }, 
        {
            "parm_desc" : "SQL_FULLTEXT",
            "parm_name" : "SQL_FULLTEXT"
        }, 
        {
            "parm_desc" : "SQL_PLAN",
            "parm_name" : "SQL_PLAN"
        }, 
        {
            "parm_desc" : "使用的cpu资源",
            "parm_name" : "STAT_CPU"
        }, 
        {
            "parm_desc" : "执行次数",
            "parm_name" : "STAT_EXEC"
        }, 
        {
            "parm_desc" : "使用buffer的资源",
            "parm_name" : "STAT_BUFFER_GETS"
        }, 
        {
            "parm_desc" : "物理读情况",
            "parm_name" : "STAT_DISK_READS"
        }, 
        {
            "parm_desc" : "解析的时间",
            "parm_name" : "STAT_ELAPSED_TIME"
        }, 
        {
            "parm_desc" : "名称",
            "parm_name" : "obj_info_name"
        }, 
        {
            "parm_desc" : "物理大小",
            "parm_name" : "obj_info_phy_size"
        }, 
        {
            "parm_desc" : "记录数",
            "parm_name" : "obj_info_num"
        }, 
        {
            "parm_desc" : "表类型",
            "parm_name" : "obj_info_type"
        }, 
        {
            "parm_desc" : "最后一次分析的时间",
            "parm_name" : "obj_info_last_analyzed"
        }, 
        {
            "parm_desc" : "最后一次DDL的时间",
            "parm_name" : "obj_info_ddl_time"
        }
    ],
    "rule_desc" : "大表全表扫描",
    "rule_name" : "SQL_TABLE_FULL_SCAN",
    "rule_status" : "ON",
    "rule_summary" : "大表全表扫描",
    "rule_type" : "SQLPLAN",
    "rule_type_detail" : "",
    "solution" : [ 
        "1.缺索引评估创建索引", 
        "2.取max、min值评估创建索引", 
        "3.索引失效重建索引，分区表维护记得维护索引", 
        "4.对条件字段使用函数或表达式a.函数、表达式放到等于号的右边b.创建函数索引(下策)", 
        "5.出现隐式转换a.不同类型的谓词匹配先显式转换b.表定义根据数据选择正确的数据类型", 
        "6.使用isNULL做查询条件a.不建议使用null值b.null值较少的情况可创建组合索引或者伪列索引(createindexidx_1ontab1(col1,0)c.将null定义一个普通变量", 
        "7.使用不等运算符<>!=做查询条件a.尽量少用不等判断；b.如果列值是连续，可把否定操作更改为两个区间；c.如果列值不多，可用inlist枚举其他所有值", 
        "8.模糊匹配'％a％''％a'建议精确匹配", 
        "9.sql逻辑，比如最大值，改用窗口函数", 
        "10.弱选择sql，返回结果集较大建议a.添加更多的谓词减少数据的访问，比如时间b.改造分区表c.使用覆盖索引", 
        "11.hintfull禁用hint1", 
        "2.统计信息不准确数据批量加载程序触发收集统计信息"
    ],
    "weight" : 0.5
}


@mongo_query
def execute(**kwargs):
    sql = """
        db.@collection_name@.find({
            "OPERATION":"TABLE ACCESS",
            "OPTIONS":"FULL",
            "USERNAME":"@username@",
            "ETL_DATE":"@etl_date@"
        }).forEach(function(x){
            if(db.obj_tab_info.findOne({
                "TABLE_NAME":x.OBJECT_NAME,
                $or: [{
                    "NUM_ROWS":{$gt:@table_row_num@}},
                    {"PHY_SIZE(MB)":{$gt:@table_phy_size@}
                    }]
                })
            )
        db.@tmp@.save({
            "SQL_ID":x.SQL_ID,
            "PLAN_HASH_VALUE":x.PLAN_HASH_VALUE,
            "OBJECT_NAME":x.OBJECT_NAME,
            "ID":x.ID,
            "COST":x.COST,
            "COUNT":""
            });
        })
    """
    table_row_num = kwargs.get("table_row_num")
    table_phy_size = kwargs.get("table_phy_size")
    sql = sql.replace("@table_phy_size@", table_phy_size).\
            replace("@table_row_num@", table_row_num)
    return sql
