# -*- coding: utf-8 -*-

import sqlparse
from django.db import connection


class SqlText(object):

    def __init__(self, mongo_client, start_date, stop_date, schema, hostname):
        self.mongo_client = mongo_client
        self.start_date = start_date
        self.stop_date = stop_date
        self.schema = schema
        self.hostname = hostname

    def get_mysql_text(self):
        """
        获取mysql慢sql的文本，从pt-query-digest存储的结果里获取
        """
        sql = """
        SELECT conv(checksum,10,16) AS `checksum`,
           fact.sample AS `sample`,
           ROUND(SUM(Rows_examined_sum)/SUM(rows_sent_sum),2) AS `index_ratio`,
           SUM(Query_time_sum) / SUM(ts_cnt) AS `query_time_avg`,
           ROUND(SUM(Rows_sent_sum)/SUM(ts_cnt),0) AS `rows_sent_avg`,
           SUM(ts_cnt) AS `ts_cnt`
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
            start_date=self.start_date,
            stop_date=self.stop_date,
            schema=self.schema,
            hostname=self.hostname
        )
        connection.close()
        cursor = connection.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()
        sql_list = []
        for i in result:
            sql_format = sqlparse.format(i[1], strip_whitespace=True).lower()
            sql_list.append({
                "checksum": i[0],
                "sqltext_form": sql_format,
                "sqltext_org": i[1],
                "sqlstats": [{
                    "index_ratio": i[2],
                    "query_time_avg": i[3],
                    "rows_sent_avg": i[4],
                    "ts_cnt": i[5]
                }]
            })
        return sql_list

    def get_text(self, db_type):
        if db_type == "mysql":
            return self.get_mysql_text()

    def get_stat(self, sql_id):
        sql = {
            "SQL_ID": sql_id,
            "USERNAME": self.schema,
            "ETL_DATE": {
                "$gte": self.start_date,
                "$lte": self.stop_date
            }
        }
        condition = {
            "ETL_DATE": 1,
            "PLAN_HASH_VALUE": 1,
            "BUFFER_GETS": 1,
            "CPU_TIME": 1,
            "PER_ELAPSED_TIME": 1,
            "PER_DISK_READS": 1,
            "PER_BUFFER_GETS": 1,
            "EXECUTIONS": 1,
            "ELAPSED_TIME": 1,
            "DISK_READS": 1,
            "PER_CPU_TIME": 1
        }
        result = self.mongo_client.find("sqlstat", sql, condition)
        return result
