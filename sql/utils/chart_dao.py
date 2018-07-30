# -*- coding: UTF-8 -*-

import MySQLdb
from datetime import datetime, timedelta
from django.db import connection


class ChartDao(object):
    # 直接在archer数据库查询数据，用于报表
    def __query(self, sql):
        cursor = connection.cursor()
        effect_row = cursor.execute(sql)
        rows = cursor.fetchall()
        fields = cursor.description
        column_list = []
        if fields:
            for i in fields:
                column_list.append(i[0])
        result = {}
        result['column_list'] = column_list
        result['rows'] = rows
        result['effect_row'] = effect_row
        return result

    # 获取连续时间
    def get_date_list(self, begin_date, end_date):
        dates = []
        dt = datetime.strptime(begin_date, "%Y-%m-%d")
        date = begin_date[:]
        while date <= end_date:
            dates.append(date)
            dt += timedelta(days=1)
            date = dt.strftime("%Y-%m-%d")
        return dates

    # 语法类型
    def sql_syntax(self):
        sql = '''
        select
          case when sql_syntax = 1
            then 'DDL'
          when sql_syntax = 2
            then 'DML'
          end as sql_syntax,
          count(*)
        from sql_workflow
        group by sql_syntax;'''
        return self.__query(sql)

    # 工单数量统计
    def workflow_by_date(self, cycle):
        sql = '''
        select
          date_format(create_time, '%Y-%m-%d'),
          count(*)
        from sql_workflow
        where create_time >= date_add(now(), interval -{} month)
        group by date_format(create_time, '%Y-%m-%d')
        order by 1 asc;'''.format(cycle)
        return self.__query(sql)

    # 工单按组统计
    def workflow_by_group(self, cycle):
        sql = '''
        select
          group_name,
          count(*)
        from sql_workflow
        where create_time >= date_add(now(), interval -{} month )
        group by group_id
        order by count(*) desc;'''.format(cycle)
        return self.__query(sql)

    # 工单按人统计
    def workflow_by_user(self, cycle):
        sql = '''
        select
          engineer_display,
          count(*)
        from sql_workflow
        where create_time >= date_add(now(), interval -{} month)
        group by engineer_display
        order by count(*) desc;'''.format(cycle)
        return self.__query(sql)


    # SQL查询统计(每日检索行数)
    def querylog_effect_row_by_date(self, cycle):
        sql = '''
        select
          date_format(create_time, '%Y-%m-%d'),
          sum(effect_row)
        from query_log
        where create_time >= date_add(now(), interval -{} month )
        group by date_format(create_time, '%Y-%m-%d')
        order by sum(effect_row) desc;'''.format(cycle)
        return self.__query(sql)

    # SQL查询统计(每日检索次数)
    def querylog_count_by_date(self, cycle):
        sql = '''
        select
          date_format(create_time, '%Y-%m-%d'),
          count(*)
        from query_log
        where create_time >= date_add(now(), interval -{} month )
        group by date_format(create_time, '%Y-%m-%d')
        order by count(*) desc;'''.format(cycle)
        return self.__query(sql)

    # SQL查询统计(用户检索行数)
    def querylog_effect_row_by_user(self, cycle):
        sql = '''
        select 
          username,
          sum(effect_row)
        from query_log
        where create_time >= date_add(now(), interval -{} month)
        group by username
        order by sum(effect_row) desc
        limit 10;'''.format(cycle)
        return self.__query(sql)

    # SQL查询统计(DB检索行数)
    def querylog_effect_row_by_db(self, cycle):
        sql = '''
       select
          db_name,
          sum(effect_row)
        from query_log
        where create_time >= date_add(now(), interval -{} month )
        group by db_name
        order by sum(effect_row) desc
        limit 10;'''.format(cycle)
        return self.__query(sql)
