# -*- coding: utf-8 -*-

import json

from django.db import connection

from themis.rule_analysis.libs.mysql_plan_stat.json_plan_parse import json_plan_item


class MysqlPlanOrStat(object):
    """
    mysql 执行计划和统计信息的解析类
    """

    def __init__(self, db_client, mongo_client, rule_type):
        self.db_client = db_client
        self.mongo_client = mongo_client
        self.rule_type = rule_type

    def get_sql_info(self, start_date, stop_date, schema, hostname):
        """
        """

        result = self.get_pt_query_sql(start_date, stop_date, schema, hostname)
        if not result:
            return False
        self.mongo_client.drop("sqlinfo")
        self.mongo_client.drop("planitem")
        for r in result:
            json_result = {}
            json_result['checksum'] = r[0]
            json_result['index_ratio'] = r[1]
            json_result['query_time_avg'] = r[2]
            json_result['rows_sent_avg'] = r[3]
            json_result['hostname_max'] = hostname.split(':')[0]
            json_result['port'] = r[4].split(':')[1]
            json_result['db_max'] = r[5]
            json_result['ts_cnt'] = r[6]
            json_result['Query_time_sum'] = r[7]
            json_result['Lock_time_sum'] = r[8]
            json_result['Rows_sent_sum'] = r[9]
            json_result['Rows_examined_sum'] = r[10]
            json_result['client_max'] = r[11]
            json_result['sample'] = r[12]
            self.mongo_client.insert("sqlinfo", json_result)
        return True

    def get_pt_query_sql(self, start_date, stop_date, schema, hostname):
        """
        获取pt-query-digets工具保存的结果
        """
        sql = """
        SELECT conv(checksum,10,16) AS `checksum`,
        ROUND(SUM(Rows_examined_sum)/SUM(rows_sent_sum),2) AS `index_ratio`,
        SUM(Query_time_sum) / SUM(ts_cnt) AS `query_time_avg`,
        ROUND(SUM(Rows_sent_sum)/SUM(ts_cnt),0) AS `rows_sent_avg`,
        MAX(hostname_max) AS `hostname_max`,
        MAX(db_max) AS `db_max`,
        SUM(ts_cnt) AS `ts_cnt`,
        SUM(Query_time_sum) AS `Query_time_sum`,
        SUM(Lock_time_sum) AS `Lock_time_sum`,
        SUM(Rows_sent_sum) AS `Rows_sent_sum`,
        SUM(Rows_examined_sum) AS `Rows_examined_sum`,
        MAX(client_max) AS `client_max`,
        fact.sample AS `sample`
        FROM `mysql_slow_query_review` AS `fact`
        JOIN `mysql_slow_query_review_history` AS `dimension` USING (`checksum`)
        WHERE dimension.ts_min >= '{start_date}'
          AND dimension.ts_min <= '{stop_date}'
          AND db_max='{schema}'
          AND hostname_max='{hostname}'
        GROUP BY checksum
        ORDER BY Query_time_sum DESC LIMIT 1000 ;
        """
        sql = sql.format(
            start_date=start_date,
            stop_date=stop_date,
            schema=schema,
            hostname=hostname
        )
        connection.close()
        cursor = connection.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()
        return result

    def get_sql_plan(self, user, passwd):
        collection = "sqlinfo"
        sql = {}
        condition = {
            "_id": 1,
            "hostname_max": 1,
            "port": 1,
            "db_max": 1,
            "checksum": 1,
            "sample": 1
        }
        sqlinfos = self.mongo_client.find(collection, sql, condition)
        for sqlinfo in sqlinfos:
            checksum = sqlinfo["checksum"]
            # 获取执行计划
            plan = self.get_json_sqlplan_from_mysql(sqlinfo, user, passwd)
            if plan[0]:
                plan_json_get = json.loads(plan[0][0][0])
            else:
                plan_json_get = {"complex": 1}
            sql = {"_id": sqlinfo["_id"]}
            condition = {
                "$set": {"sqlplan_json": plan_json_get, "sqlplan": plan[1]}
            }
            self.mongo_client.update("sqlinfo", sql, condition)
            # 解析json树，并将结果保存到mongo里
            json_plan_item(
                self.mongo_client, checksum, plan_json_get, sqlinfo["db_max"])

    def get_json_sqlplan_from_mysql(self, sqlinfo, user, passwd):
        """
        根据pt-query-digest工具提供的慢sql，回库获取sql的执行计划
        参数 sqlinfo: 包含hostname_max, port, db_max, checksum, sample等信息
            user: 待执行sql的目标机器的帐号
            passwd: 待执行sql的目标机器的密码
        """

        # 去除sql语句最前边的无用信息
        explain_sql = sqlinfo["sample"]
        temp = []
        for key in ["SELECT", "UPDATE", "DELETE", "INSERT"]:
            temp.append(explain_sql.upper().find(key))
        temp = list(set(temp))
        if -1 in temp:
            temp.remove(-1)
        try:
            index = min(temp)
        except Exception:
            index = 0
        explain_sql = explain_sql[index:]

        # 解析执行计划
        # 解析explain和explain format=json时，由于sql过于复杂，会话会出现sleep状态假死现象，通过设置
        # set wait_timeout=3来避免，也可能会出现query状态查询过长，可采用pt-kill工具，防止影响正常业务
        # 由于在执行explain和explain format=json的时候，经常会出现意外情况，因此就没有利用已经初始化好的全局会话，
        # 而是每次执行都先初始化一个会话
        if self.rule_type.upper() == "SQLPLAN":
            self.db_client.new_connect(
                host=sqlinfo["hostname_max"], port=int(sqlinfo["port"]),
                user=user, passwd=passwd, db=sqlinfo["db_max"])
            self.db_client.cursor.execute("set wait_timeout=3")
            try:
                self.db_client.cursor.execute(
                    "eXplAin format=json " + str(explain_sql) + ";")
                mysql_result_json = self.db_client.cursor.fetchall()
                self.db_client.close()
            except Exception:
                mysql_result_json = None
        else:
            mysql_result_json = None
        self.db_client.new_connect(
            host=sqlinfo["hostname_max"], port=int(sqlinfo["port"]),
            user=user, passwd=passwd, db=sqlinfo["db_max"])
        self.db_client.execute("set wait_timeout=3;")
        try:
            self.db_client.cursor.execute("eXplAin " + str(explain_sql) + ";")
            mysql_result_normal = self.db_client.cursor.fetchall()
            self.db_client.close()
        except Exception:
            mysql_result_normal = ""
        return mysql_result_json, mysql_result_normal

    def rule_match(self, collection):
        match_list = []
        sql_plan = {}
        sql_text = {}
        for sql_id in self.mongo_client.find(collection, {}, {"_id": 0}):
            match_list.append(sql_id)
            result = self.mongo_client.find(
                "sqlinfo", {"checksum": sql_id["checksum"]})
            sql_text.update({sql_id["checksum"]: result[0]["sample"]})
            sql_plan.update({sql_id["checksum"]: result[0]["sqlplan"]})
        return match_list, sql_text, sql_plan
