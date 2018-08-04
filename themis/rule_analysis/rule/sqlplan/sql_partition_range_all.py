# -*- coding: utf-8 -*-

from .decorator import mongo_query

rule = {
    "db_type" : "O",
    "exclude_obj_type" : [ 
        "SQL_ID", 
        "PLAN_HASH_VALUE"
    ],
    "input_parms" : [],
    "max_score" : "20",
    "obj_info_type" : "PART_TABLE",
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
            "parm_desc" : "分区类型",
            "parm_name" : "obj_info_type"
        }, 
        {
            "parm_desc" : "分区键",
            "parm_name" : "obj_info_key"
        }, 
        {
            "parm_desc" : "分区数量",
            "parm_name" : "obj_info_part_num"
        }, 
        {
            "parm_desc" : "最后一次DDL的时间",
            "parm_name" : "obj_info_ddl_time"
        }
    ],
    "rule_desc" : "分区全扫描",
    "rule_name" : "SQL_PARTITION_RANGE_ALL",
    "rule_status" : "ON",
    "rule_summary" : "分区全扫描",
    "rule_type" : "SQLPLAN",
    "rule_type_detail" : "",
    "solution" : [ 
        "分区键设计是否合理"
    ],
    "weight" : 0.5
}


@mongo_query
def execute_rule(**kwargs):
    """
    functions: 分区全扫描
    """
    sql = """
        db.@collection_name@.find({
            "OPERATION":"PARTITION RANGE",
            "OPTIONS":"ALL",
            "USERNAME":"@username@",
            "ETL_DATE":"@etl_date@"
        }).forEach(function(x){
            db.@sql@.find({
                "SQL_ID":x.SQL_ID,
                "PLAN_HASH_VALUE":x.PLAN_HASH_VALUE,
                "ID":{$eq:x.ID+1}
            }).forEach(function(y){
                db.@tmp@.save({
                    "SQL_ID":y.SQL_ID,
                    "PLAN_HASH_VALUE":y.PLAN_HASH_VALUE,
                    "OBJECT_NAME":y.OBJECT_NAME,
                    "ID":y.ID,
                    "COST":x.COST,
                    "COUNT":""})
                });
            })
    """
    return sql
