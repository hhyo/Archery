# -*- coding: UTF-8 -*-

import MySQLdb

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
        where create_time >= date_add(now(), interval -1 {} )
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
