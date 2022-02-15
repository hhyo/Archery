# -*- coding: UTF-8 -*-
from clickhouse_driver import connect
from . import EngineBase
from .models import ResultSet, ReviewResult, ReviewSet
from common.config import SysConfig
import sqlparse
import logging
import traceback
import re

logger = logging.getLogger('default')


class ClickHouseEngine(EngineBase):

    def __init__(self, instance=None):
        super(ClickHouseEngine, self).__init__(instance=instance)

    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        if db_name:
            self.conn = connect(host=self.host, port=self.port, user=self.user, password=self.password,
                                database=db_name, connect_timeout=10)
        else:
            self.conn = connect(host=self.host, port=self.port, user=self.user, password=self.password,
                                connect_timeout=10)
        return self.conn

    @property
    def name(self):
        return 'ClickHouse'

    @property
    def info(self):
        return 'ClickHouse engine'

    @property
    def auto_backup(self):
        """是否支持备份"""
        return False

    @property
    def server_version(self):
        def numeric_part(s):
            """Returns the leading numeric part of a string.
            """
            re_numeric_part = re.compile(r"^(\d+)")
            m = re_numeric_part.match(s)
            if m:
                return int(m.group(1))
            return None

        sql = "select value from system.build_options where name = 'VERSION_FULL';"
        result = self.query(sql=sql)
        version = result.rows[0][0].split(' ')[1]
        return tuple([numeric_part(n) for n in version.split('.')[:3]])

    def get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet"""
        sql = "show databases"
        result = self.query(sql=sql)
        db_list = [row[0] for row in result.rows if row[0] not in ('system')]
        result.rows = db_list
        return result

    def get_all_tables(self, db_name, **kwargs):
        """获取table 列表, 返回一个ResultSet"""
        sql = "show tables"
        result = self.query(db_name=db_name, sql=sql)
        tb_list = [row[0] for row in result.rows]
        result.rows = tb_list
        return result

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段, 返回一个ResultSet"""
        sql = f"""select
            name,
            type,
            comment
        from
            system.columns
        where
            database = '{db_name}'
        and table = '{tb_name}';"""
        result = self.query(db_name=db_name, sql=sql)
        column_list = [row[0] for row in result.rows]
        result.rows = column_list
        return result

    def describe_table(self, db_name, tb_name, **kwargs):
        """return ResultSet 类似查询"""
        sql = f"show create table `{tb_name}`;"
        result = self.query(db_name=db_name, sql=sql)

        result.rows[0] = (tb_name,) + (result.rows[0][0].replace('(', '(\n ').replace(',', ',\n '),)
        return result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True, **kwargs):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection(db_name=db_name)
            cursor = conn.cursor()
            cursor.execute(sql)
            if int(limit_num) > 0:
                rows = cursor.fetchmany(size=int(limit_num))
            else:
                rows = cursor.fetchall()
            fields = cursor.description

            result_set.column_list = [i[0] for i in fields] if fields else []
            result_set.rows = rows
            result_set.affected_rows = len(rows)
        except Exception as e:
            logger.warning(f"ClickHouse语句执行报错，语句：{sql}，错误信息{e}")
            result_set.error = str(e).split('Stack trace')[0]
        finally:
            if close_conn:
                self.close()
        return result_set

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
        if re.match(r"^select|^show|^explain", sql, re.I) is None:
            result['bad_query'] = True
            result['msg'] = '不支持的查询语法类型!'
        if '*' in sql:
            result['has_star'] = True
            result['msg'] = 'SQL语句中含有 * '
        # select语句先使用Explain判断语法是否正确
        if re.match(r"^select", sql, re.I):
            explain_result = self.query(db_name=db_name, sql=f"explain {sql}")
            if explain_result.error:
                result['bad_query'] = True
                result['msg'] = explain_result.error

        return result

    def filter_sql(self, sql='', limit_num=0):
        # 对查询sql增加limit限制,limit n 或 limit n,n 或 limit n offset n统一改写成limit n
        sql = sql.rstrip(';').strip()
        if re.match(r"^select", sql, re.I):
            # LIMIT N
            limit_n = re.compile(r'limit\s+(\d+)\s*$', re.I)
            # LIMIT M OFFSET N
            limit_offset = re.compile(r'limit\s+(\d+)\s+offset\s+(\d+)\s*$', re.I)
            # LIMIT M,N
            offset_comma_limit = re.compile(r'limit\s+(\d+)\s*,\s*(\d+)\s*$', re.I)
            if limit_n.search(sql):
                sql_limit = limit_n.search(sql).group(1)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = limit_n.sub(f'limit {limit_num};', sql)
            elif limit_offset.search(sql):
                sql_limit = limit_offset.search(sql).group(1)
                sql_offset = limit_offset.search(sql).group(2)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = limit_offset.sub(f'limit {limit_num} offset {sql_offset};', sql)
            elif offset_comma_limit.search(sql):
                sql_offset = offset_comma_limit.search(sql).group(1)
                sql_limit = offset_comma_limit.search(sql).group(2)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = offset_comma_limit.sub(f'limit {sql_offset},{limit_num};', sql)
            else:
                sql = f'{sql} limit {limit_num};'
        else:
            sql = f'{sql};'
        return sql

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
