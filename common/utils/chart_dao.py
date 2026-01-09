# -*- coding: UTF-8 -*-

from datetime import timedelta
from django.db import connection


class ChartDao(object):
    # 直接在Archery数据库查询数据，用于报表
    @staticmethod
    def __query(sql):
        cursor = connection.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        fields = cursor.description
        column_list = []
        if fields:
            for i in fields:
                column_list.append(i[0])
        return {"column_list": column_list, "rows": rows}

    # 获取连续时间
    @staticmethod
    def get_date_list(begin_date, end_date):
        dates = []
        this_day = begin_date
        while this_day <= end_date:
            dates += [this_day.strftime("%Y-%m-%d")]
            this_day += timedelta(days=1)
        return dates

    # 语法类型
    def syntax_type(self, start_date, end_date):
        sql = """
        select
          case when syntax_type = 1
            then 'DDL'
          when syntax_type = 2
            then 'DML'
          else 'Other'
          end as syntax_type,
          count(*)
        from sql_workflow 
        where create_time >= '{}' and create_time <= '{}'
        group by syntax_type;""".format(
            start_date, end_date
        )
        return self.__query(sql)

    # 工单数量统计
    def workflow_by_date(self, start_date, end_date):
        sql = """
        select
          date_format(create_time, '%Y-%m-%d'),
          count(*)
        from sql_workflow
        where create_time >= '{}' and create_time <= '{}'
        group by date_format(create_time, '%Y-%m-%d')
        order by 1 asc;""".format(
            start_date, end_date
        )
        return self.__query(sql)

    # 工单按组统计
    def workflow_by_group(self, start_date, end_date):
        sql = """
        select
          group_name,
          count(*)
        from sql_workflow
        where create_time >= '{}' and create_time <= '{}'
        group by group_id
        order by count(*) desc;""".format(
            start_date, end_date
        )
        return self.__query(sql)

    def workflow_by_user(self, start_date, end_date):
        """工单按人统计"""
        # TODO select 的对象应该为engineer ID, 查询时应作联合查询查出用户中文名
        sql = """
        select
          engineer_display,
          count(*)
        from sql_workflow
        where create_time >= '{}' and create_time <= '{}'
        group by engineer_display
        order by count(*) desc;""".format(
            start_date, end_date
        )
        return self.__query(sql)

    # SQL查询统计(每日检索行数)
    def querylog_effect_row_by_date(self, start_date, end_date):
        sql = """
        select
          date_format(create_time, '%Y-%m-%d'),
          sum(effect_row)
        from query_log
        where create_time >= '{}' and create_time <= '{}'
        group by date_format(create_time, '%Y-%m-%d')
        order by sum(effect_row) desc;""".format(
            start_date, end_date
        )
        return self.__query(sql)

    # SQL查询统计(每日检索次数)
    def querylog_count_by_date(self, start_date, end_date):
        sql = """
        select
          date_format(create_time, '%Y-%m-%d'),
          count(*)
        from query_log
        where create_time >= '{}' and create_time <= '{}'
        group by date_format(create_time, '%Y-%m-%d')
        order by count(*) desc;""".format(
            start_date, end_date
        )
        return self.__query(sql)

    # SQL查询统计(用户检索行数)
    def querylog_effect_row_by_user(self, start_date, end_date):
        sql = """
        select 
          user_display,
          sum(effect_row)
        from query_log
        where create_time >= '{}' and create_time <= '{}'
        group by user_display
        order by sum(effect_row) desc
        limit 20;""".format(
            start_date, end_date
        )
        return self.__query(sql)

    # SQL查询统计(DB检索行数)
    def querylog_effect_row_by_db(self, start_date, end_date):
        sql = """
       select
          db_name,
          sum(effect_row)
        from query_log
        where create_time >= '{}' and create_time <= '{}'
        group by db_name
        order by sum(effect_row) desc
        limit 20;""".format(
            start_date, end_date
        )
        return self.__query(sql)

    # 慢日志历史趋势图(按次数)
    def slow_query_review_history_by_cnt(self, checksum):
        sql = f"""select sum(ts_cnt),date(date_add(ts_min, interval 8 HOUR))
from mysql_slow_query_review_history
where checksum = '{checksum}'
group by date(date_add(ts_min, interval 8 HOUR));"""
        return self.__query(sql)

    # 慢日志历史趋势图(按时长)
    def slow_query_review_history_by_pct_95_time(self, checksum):
        sql = f"""select truncate(Query_time_pct_95,6),date(date_add(ts_min, interval 8 HOUR))
from mysql_slow_query_review_history
where checksum = '{checksum}'
group by date(date_add(ts_min, interval 8 HOUR));"""
        return self.__query(sql)

    # 慢日志db/user维度统计
    def slow_query_count_by_db_by_user(self, start_date, end_date):
        sql = """
        select
            concat(db_max,' user: ' ,user_max),
            sum(ts_cnt) 
        from mysql_slow_query_review_history 
        where ts_min >= '{}' and ts_min <= '{}'
        group by db_max,user_max order by sum(ts_cnt) desc limit 50;
        """.format(
            start_date, end_date
        )
        return self.__query(sql)

    # 慢日志db维度统计
    def slow_query_count_by_db(self, start_date, end_date):
        sql = """
        select
            db_max,
            sum(ts_cnt) 
        from mysql_slow_query_review_history 
        where ts_min >= '{}' and ts_min <= '{}'
        group by db_max order by sum(ts_cnt) desc limit 50;
        """.format(
            start_date, end_date
        )
        return self.__query(sql)

    # 数据库实例类型统计
    def instance_count_by_type(self):
        sql = """
        select db_type,count(1) as cn 
        from sql_instance 
        group by db_type 
        order by 2 desc;"""
        return self.__query(sql)

    def query_sql_prod_bill(self, start_date, end_date):
        sql = """
            SELECT
                CASE
                        a.STATUS
                        WHEN 'workflow_finish' THEN
                        'Finished'
                        WHEN 'workflow_autoreviewwrong' THEN
                        'Auto Review Failed'
                        WHEN 'workflow_abort' THEN
                        'Aborted'
                        WHEN 'workflow_exception' THEN
                        'Exception'
                        WHEN 'workflow_review_pass' THEN
                        'Review Passed'
                        WHEN 'workflow_queuing' THEN
                        'Queuing'
                        WHEN 'workflow_executing' THEN
                        'Executing'
                        WHEN 'workflow_manreviewing' THEN
                        'Waiting for Review' ELSE 'Unknown'
                    END AS status_desc,
                    COUNT( 1 ) AS count 
                FROM sql_workflow a
                    INNER JOIN sql_instance b ON ( a.instance_id = b.id ) 
                WHERE a.create_time >= '{}' and a.create_time <= '{}'
                GROUP BY a.STATUS
                ORDER BY 1;
          """.format(
            start_date, end_date
        )
        return self.__query(sql)

    def query_instance_env_info(self):
        sql = """
             SELECT
            db_type,
            type,
            COUNT(1) AS cn
        FROM
            sql_instance
        GROUP BY
            db_type,
            type
        ORDER BY
            1,
            2;
        """
        return self.__query(sql)
