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

from common.config import SysConfig
from common.utils.timer import FuncTimer
from sql.utils.sql_utils import get_syntax_type
from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult
from sql.utils.data_masking import simple_column_mask

__author__ = 'hhyo、yyukai'

logger = logging.getLogger('default')


class PgSQLEngine(EngineBase):
    def get_connection(self, db_name=None):
        db_name = db_name or self.db_name or 'postgres'
        if self.conn:
            return self.conn
        self.conn = psycopg2.connect(host=self.host, port=self.port, user=self.user,
                                     password=self.password, dbname=db_name, connect_timeout=10)
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

    def get_all_schemas(self, db_name, **kwargs):
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

    def get_all_tables(self, db_name, **kwargs):
        """
        获取表列表
        :param db_name:
        :param schema_name:
        :return:
        """
        schema_name = kwargs.get('schema_name')
        sql = f"""SELECT table_name 
        FROM information_schema.tables 
        where table_schema ='{schema_name}';"""
        result = self.query(db_name=db_name, sql=sql)
        tb_list = [row[0] for row in result.rows if row[0] not in ['test']]
        result.rows = tb_list
        return result

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """
        获取字段列表
        :param db_name:
        :param tb_name:
        :param schema_name:
        :return:
        """
        schema_name = kwargs.get('schema_name')
        sql = f"""SELECT column_name
        FROM information_schema.columns 
        where table_name='{tb_name}'
        and table_schema ='{schema_name}';"""
        result = self.query(db_name=db_name, sql=sql)
        column_list = [row[0] for row in result.rows]
        result.rows = column_list
        return result

    def describe_table(self, db_name, tb_name, **kwargs):
        """
        获取表结构信息
        :param db_name:
        :param tb_name:
        :param schema_name:
        :return:
        """
        schema_name = kwargs.get('schema_name')
        sql = f"""select
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
        where table_name = '{tb_name}'
        and col.table_schema = '{schema_name}'
        order by ordinal_position;"""
        result = self.query(db_name=db_name, schema_name=schema_name, sql=sql)
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

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True, **kwargs):
        """返回 ResultSet """
        schema_name = kwargs.get('schema_name')
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection(db_name=db_name)
            max_execution_time = kwargs.get('max_execution_time', 0)
            cursor = conn.cursor()
            try:
                cursor.execute(f"SET statement_timeout TO {max_execution_time};")
            except:
                pass
            if schema_name:
                cursor.execute(f"SET search_path TO {schema_name};")
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
            logger.warning(f"PgSQL命令执行报错，语句：{sql}， 错误信息：{traceback.format_exc()}")
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
        """简单字段脱敏规则, 仅对select有效"""
        if re.match(r"^select", sql, re.I):
            filtered_result = simple_column_mask(self.instance, resultset)
            filtered_result.is_masked = True
        else:
            filtered_result = resultset
        return filtered_result

    def execute_check(self, db_name=None, sql=''):
        """上线单执行前的检查, 返回Review set"""
        config = SysConfig()
        check_result = ReviewSet(full_sql=sql)
        # 禁用/高危语句检查
        line = 1
        critical_ddl_regex = config.get('critical_ddl_regex', '')
        p = re.compile(critical_ddl_regex)
        check_result.syntax_type = 2  # TODO 工单类型 0、其他 1、DDL，2、DML
        for statement in sqlparse.split(sql):
            statement = sqlparse.format(statement, strip_comments=True)
            # 禁用语句
            if re.match(r"^select", statement.lower()):
                result = ReviewResult(id=line, errlevel=2,
                                      stagestatus='驳回不支持语句',
                                      errormessage='仅支持DML和DDL语句，查询语句请使用SQL查询功能！',
                                      sql=statement)
            # 高危语句
            elif critical_ddl_regex and p.match(statement.strip().lower()):
                result = ReviewResult(id=line, errlevel=2,
                                      stagestatus='驳回高危SQL',
                                      errormessage='禁止提交匹配' + critical_ddl_regex + '条件的语句！',
                                      sql=statement)

            # 正常语句
            else:
                result = ReviewResult(id=line, errlevel=0,
                                      stagestatus='Audit completed',
                                      errormessage='None',
                                      sql=statement,
                                      affected_rows=0,
                                      execute_time=0, )
            # 判断工单类型
            if get_syntax_type(statement) == 'DDL':
                check_result.syntax_type = 1
            check_result.rows += [result]
            line += 1
        # 统计警告和错误数量
        for r in check_result.rows:
            if r.errlevel == 1:
                check_result.warning_count += 1
            if r.errlevel == 2:
                check_result.error_count += 1
        return check_result

    def execute_workflow(self, workflow, close_conn=True):
        """执行上线单，返回Review set"""
        sql = workflow.sqlworkflowcontent.sql_content
        execute_result = ReviewSet(full_sql=sql)
        # 删除注释语句，切分语句，将切换CURRENT_SCHEMA语句增加到切分结果中
        sql = sqlparse.format(sql, strip_comments=True)
        split_sql = sqlparse.split(sql)
        line = 1
        statement = None
        db_name = workflow.db_name
        try:
            conn = self.get_connection(db_name=db_name)
            cursor = conn.cursor()
            # 逐条执行切分语句，追加到执行结果中
            for statement in split_sql:
                statement = statement.rstrip(';')
                with FuncTimer() as t:
                    cursor.execute(statement)
                    conn.commit()
                execute_result.rows.append(ReviewResult(
                    id=line,
                    errlevel=0,
                    stagestatus='Execute Successfully',
                    errormessage='None',
                    sql=statement,
                    affected_rows=cursor.rowcount,
                    execute_time=t.cost,
                ))
                line += 1
        except Exception as e:
            logger.warning(f"PGSQL命令执行报错，语句：{statement or sql}， 错误信息：{traceback.format_exc()}")
            execute_result.error = str(e)
            # 追加当前报错语句信息到执行结果中
            execute_result.rows.append(ReviewResult(
                id=line,
                errlevel=2,
                stagestatus='Execute Failed',
                errormessage=f'异常信息：{e}',
                sql=statement or sql,
                affected_rows=0,
                execute_time=0,
            ))
            line += 1
            # 报错语句后面的语句标记为审核通过、未执行，追加到执行结果中
            for statement in split_sql[line - 1:]:
                execute_result.rows.append(ReviewResult(
                    id=line,
                    errlevel=0,
                    stagestatus='Audit completed',
                    errormessage=f'前序语句失败, 未执行',
                    sql=statement,
                    affected_rows=0,
                    execute_time=0,
                ))
                line += 1
        finally:
            if close_conn:
                self.close()
        return execute_result

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
