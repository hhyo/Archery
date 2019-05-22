# -*- coding: UTF-8 -*-
""" 
@author: hhyo、yyukai
@license: Apache Licence 
@file: pgsql.py 
@time: 2019/03/29
"""
import re
import psycopg2
import logging
import traceback
import sqlparse

from . import EngineBase
from .models import ResultSet

__author__ = 'hhyo、yyukai'

logger = logging.getLogger('default')


class PgSQLEngine(EngineBase):
    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        db_name = db_name if db_name else 'postgres'
        self.conn = psycopg2.connect(host=self.host, port=self.port, user=self.user,
                                     password=self.password, dbname=db_name)
        return self.conn

    @property
    def name(self):
        return 'PgSQL'

    @property
    def info(self):
        return 'PgSQL engine'

    def get_all_databases(self):
        """
        获取数据库列表
        :return:
        """
        result = self.query(sql=f"SELECT datname FROM pg_database;")
        db_list = [row[0] for row in result.rows if row[0] not in ['postgres', 'template0', 'template1']]
        result.rows = db_list
        return result

    def get_all_schemas(self, db_name):
        """
        获取模式列表
        :return:
        """
        result = self.query(db_name=db_name, sql=f"select schema_name from information_schema.schemata;")
        schema_list = [row[0] for row in result.rows if row[0] not in ['information_schema',
                                                                       'pg_catalog', 'pg_toast_temp_1',
                                                                       'pg_temp_1', 'pg_toast']]
        result.rows = schema_list
        return result

    def get_all_tables(self, db_name, schema_name=None):
        """
        获取表列表
        :param db_name:
        :param schema_name:
        :return:
        """
        sql = f"""SELECT table_name 
        FROM information_schema.tables 
        where table_catalog='{db_name}'
        and table_schema ='{schema_name}';"""
        result = self.query(db_name=db_name, sql=sql)
        tb_list = [row[0] for row in result.rows if row[0] not in ['test']]
        result.rows = tb_list
        return result

    def get_all_columns_by_tb(self, db_name, tb_name, schema_name=None):
        """
        获取字段列表
        :param db_name:
        :param tb_name:
        :param schema_name:
        :return:
        """
        sql = f"""SELECT column_name
        FROM information_schema.columns 
        where table_catalog='{db_name}'
        and table_name='{tb_name}'
        and table_schema ='{schema_name}';"""
        result = self.query(db_name=db_name, sql=sql)
        column_list = [row[0] for row in result.rows]
        result.rows = column_list
        return result

    def describe_table(self, db_name, tb_name, schema_name=None):
        """
        获取表结构信息
        :param db_name:
        :param tb_name:
        :param schema_name:
        :return:
        """
        sql = fr"""select
        col.column_name,
        col.data_type,
        col.character_maximum_length,
        col.numeric_precision,
        col.numeric_scale,
        col.is_nullable,
        col.column_default,
        des.description
        from
        information_schema.columns col left join pg_description des on
        col.table_name::regclass = des.objoid
        and col.ordinal_position = des.objsubid
        where table_catalog='{db_name}'
        and table_schema = '{schema_name}'
        and table_name = '{tb_name}'
        order by ordinal_position;"""
        result = self.query(db_name=db_name, sql=sql)
        return result

    def query_check(self, db_name=None, sql=''):
        # 查询语句的检查、注释去除、切分
        result = {'msg': '', 'bad_query': False, 'filtered_sql': sql, 'has_star': False}
        # 删除注释语句，进行语法判断，执行第一条有效sql
        try:
            sql = sqlparse.format(sql, strip_comments=True)
            sql = sqlparse.split(sql)[0]
            result['filtered_sql'] = sql.strip()
        except IndexError:
            result['bad_query'] = True
            result['msg'] = '没有有效的SQL语句'
        if re.match(r"^select", sql, re.I) is None:
            result['bad_query'] = True
            result['msg'] = '不支持的查询语法类型!'
        if '*' in sql:
            result['has_star'] = True
            result['msg'] = 'SQL语句中含有 * '
        return result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection(db_name=db_name)
            cursor = conn.cursor()
            cursor.execute(sql)
            effect_row = cursor.rowcount
            if int(limit_num) > 0:
                rows = cursor.fetchmany(size=int(limit_num))
            else:
                rows = cursor.fetchall()
            fields = cursor.description

            result_set.column_list = [i[0] for i in fields] if fields else []
            result_set.rows = rows
            result_set.affected_rows = effect_row
        except Exception as e:
            logger.error(f"PgSQL命令执行报错，语句：{sql}， 错误信息：{traceback.format_exc()}")
            result_set.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result_set

    def filter_sql(self, sql='', limit_num=0):
        # 对查询sql增加limit限制，# TODO limit改写待优化
        sql_lower = sql.lower().rstrip(';').strip()
        if re.match(r"^select", sql_lower):
            if re.search(r"limit\s+(\d+)$", sql_lower) is None:
                if re.search(r"limit\s+\d+\s*,\s*(\d+)$", sql_lower) is None:
                    return f"{sql.rstrip(';')} limit {limit_num};"
        return f"{sql.rstrip(';')};"

    def query_masking(self, db_name=None, sql='', resultset=None):
        """不做脱敏"""
        return resultset

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
