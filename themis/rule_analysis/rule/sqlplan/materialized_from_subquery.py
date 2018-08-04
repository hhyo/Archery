# -*- coding: utf-8 -*-

from .decorator import mongo_query


rule = {
    "db_type" : "mysql",
    "exclude_obj_type" : "",
    "input_parms" : [],
    "max_score" : 10.0,
    "output_datas" : [ 
        {
            "parm_desc" : "CHECKSUM",
            "parm_name" : "CHECKSUM"
        }, 
        {
            "parm_desc" : "执行次数",
            "parm_name" : "ts_cnt"
        }, 
        {
            "parm_desc" : "平均执行时间",
            "parm_name" : "query_time_avg"
        }, 
        {
            "parm_desc" : "平均返回记录数",
            "parm_name" : "rows_sent_avg"
        }, 
        {
            "parm_desc" : "扫描命中率",
            "parm_name" : "index_ratio"
        }
    ],
    "rule_cmd" : "",
    "rule_desc" : "materialized_from_subquery",
    "rule_name" : "materialized_from_subquery",
    "rule_status" : "ON",
    "rule_summary" : "",
    "rule_type" : "SQLPLAN",
    "solution" : [ 
        "1.使用连接查询", 
        "2.避免大的结果集"
    ],
    "weight" : 0.1
}


@mongo_query
def execute_rule(**kwargs):
    sql = """
    db.planitem.find({
        schemas:@schema_name@,
        item_type : materialized_from_subquery
    }).forEach(function(x){
        db.sqlinfo.find({
            checksum:x.checksum
        }).forEach(function(y){
            db.@tmp@.save({
                checksum :y.checksum,
                ts_cnt :y.ts_cnt,
                query_time_avg :y.query_time_avg,
                rows_sent_avg :y.rows_sent_avg,
                index_ratio :y.index_ratio
            })
        })
    })
    """
    return sql
