# -*- coding: UTF-8 -*-
import logging
import traceback
import MySQLdb
import re
import sqlparse
from MySQLdb.connections import numeric_part

from sql.engines.goinception import GoInceptionEngine
from . import EngineBase
from .models import ResultSet, ReviewResult, ReviewSet
from .inception import InceptionEngine
from sql.utils.data_masking import data_masking
from common.config import SysConfig

logger = logging.getLogger('default')


class MysqlEngine(EngineBase):
    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        if db_name:
            self.conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password,
                                        db=db_name, charset='utf8mb4')
        else:
            self.conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password,
                                        charset='utf8mb4')
        return self.conn

    @property
    def name(self):
        return 'MySQL'

    @property
    def info(self):
        return 'MySQL engine'

    @property
    def server_version(self):
        version = self.query(sql="select @@version").rows[0][0]
        return tuple([numeric_part(n) for n in version.split('.')[:3]])

    def get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet"""
        sql = "show databases"
        result = self.query(sql=sql)
        db_list = [row[0] for row in result.rows
                   if row[0] not in ('information_schema', 'performance_schema', 'mysql', 'test', 'sys')]
        result.rows = db_list
        return result

    def get_all_tables(self, db_name):
        """获取table 列表, 返回一个ResultSet"""
        sql = "show tables"
        result = self.query(db_name=db_name, sql=sql)
        tb_list = [row[0] for row in result.rows if row[0] not in ['test']]
        result.rows = tb_list
        return result

    def get_all_columns_by_tb(self, db_name, tb_name):
        """获取所有字段, 返回一个ResultSet"""
        result = self.describe_table(db_name, tb_name)
        column_list = [row[0] for row in result.rows]
        result.rows = column_list
        return result

    def describe_table(self, db_name, tb_name):
        """return ResultSet 类似查询"""
        sql = f"""SELECT 
            COLUMN_NAME,
            COLUMN_TYPE,
            CHARACTER_SET_NAME,
            IS_NULLABLE,
            COLUMN_KEY,
            EXTRA,
            COLUMN_COMMENT
        FROM
            information_schema.COLUMNS
        WHERE
            TABLE_SCHEMA = '{db_name}'
                AND TABLE_NAME = '{tb_name}'
        ORDER BY ORDINAL_POSITION;"""
        result = self.query(sql=sql)
        return result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection(db_name=db_name)
            cursor = conn.cursor()
            effect_row = cursor.execute(sql)
            if int(limit_num) > 0:
                rows = cursor.fetchmany(size=int(limit_num))
            else:
                rows = cursor.fetchall()
            fields = cursor.description

            result_set.column_list = [i[0] for i in fields] if fields else []
            result_set.rows = rows
            result_set.affected_rows = effect_row
        except Exception as e:
            logger.error(f"MySQL语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}")
            result_set.error = str(e)
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
        return result

    def filter_sql(self, sql='', limit_num=0):
        # 对查询sql增加limit限制，# TODO limit改写待优化
        sql_lower = sql.lower().rstrip(';').strip()
        if re.match(r"^select", sql_lower):
            if re.search(r"limit\s+(\d+)$", sql_lower) is None:
                if re.search(r"limit\s+\d+\s*,\s*(\d+)$", sql_lower) is None:
                    return f"{sql.rstrip(';')} limit {limit_num};"
        return f"{sql.rstrip(';')};"

    def query_masking(self, db_name=None, sql='', resultset=None):
        """传入 sql语句, db名, 结果集,
        返回一个脱敏后的结果集"""
        # 仅对select语句脱敏
        if re.match(r"^select", sql, re.I):
            mask_result = data_masking(self.instance, db_name, sql, resultset)
        else:
            mask_result = resultset
        return mask_result

    def execute_check(self, db_name=None, sql=''):
        """上线单执行前的检查, 返回Review set"""
        config = SysConfig()
        check_result = ReviewSet(full_sql=sql)
        # 禁用语句检查
        line = 1
        for statement in sqlparse.split(sql):
            statement = sqlparse.format(statement, strip_comments=True)
            if re.match(r"^select", statement.lower()):
                check_result.is_critical = True
                result = ReviewResult(id=line, errlevel=2,
                                      stagestatus='驳回高危SQL',
                                      errormessage='仅支持DML和DDL语句，查询语句请使用SQL查询功能！',
                                      sql=statement)
                check_result.rows += [result]
                check_result.error_count += 1
        # 高危SQL检查
        if not check_result.is_critical and config.get('critical_ddl_regex'):
            # 如果启用critical_ddl 的检查
            critical_ddl_regex = config.get('critical_ddl_regex')
            p = re.compile(critical_ddl_regex)
            # 逐行匹配正则
            line = 1
            for statement in sqlparse.split(sql):
                # 删除注释语句
                statement = sqlparse.format(statement, strip_comments=True)
                if p.match(statement.strip().lower()):
                    result = ReviewResult(id=line, errlevel=2,
                                          stagestatus='驳回高危SQL',
                                          errormessage='禁止提交匹配' + critical_ddl_regex + '条件的语句！',
                                          sql=statement)
                    check_result.is_critical = True
                    check_result.error_count += 1
                else:
                    result = ReviewResult(id=line, errlevel=0, sql=statement)
                check_result.rows += [result]
                line += 1
        # 高危/禁用语句直接返回
        if check_result.is_critical:
            return check_result
        # 通过检测的再进行inception检查
        elif config.get('go_inception'):
            try:
                inception_engine = GoInceptionEngine()
                check_result = inception_engine.execute_check(instance=self.instance, db_name=db_name, sql=sql)
            except Exception as e:
                logger.debug(f"Inception检测语句报错：错误信息{traceback.format_exc()}")
                raise RuntimeError(f"Inception检测语句报错，请注意检查系统配置中Inception配置，错误信息：\n{e}")
        else:
            try:
                inception_engine = InceptionEngine()
                check_result = inception_engine.execute_check(instance=self.instance, db_name=db_name, sql=sql)
            except Exception as e:
                logger.debug(f"Inception检测语句报错：错误信息{traceback.format_exc()}")
                raise RuntimeError(f"Inception检测语句报错，请注意检查系统配置中Inception配置，错误信息：\n{e}")
        return check_result

    def execute_workflow(self, workflow):
        """执行上线单，返回Review set"""
        # 原生执行
        if workflow.is_manual == 1:
            return self.execute(db_name=workflow.db_name, sql=workflow.sqlworkflowcontent.sql_content)
        # inception执行
        elif SysConfig().get('go_inception'):
            inception_engine = GoInceptionEngine()
            return inception_engine.execute(workflow)
        else:
            inception_engine = InceptionEngine()
            return inception_engine.execute(workflow)

    def execute(self, db_name=None, sql='', close_conn=True):
        """原生执行语句"""
        result = ResultSet(full_sql=sql)
        conn = self.get_connection(db_name=db_name)
        try:
            cursor = conn.cursor()
            for statement in sqlparse.split(sql):
                cursor.execute(statement)
            conn.commit()
            cursor.close()
        except Exception as e:
            logger.error(f"MySQL语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}")
            result.error = str(e)
        if close_conn:
            self.close()
        return result

    def get_rollback(self, workflow):
        """通过inception获取回滚语句列表"""
        inception_engine = InceptionEngine()
        return inception_engine.get_rollback(workflow)

    def get_variables(self, variables=None):
        """获取实例参数"""
        if variables:
            variables = "','".join(variables) if isinstance(variables, list) else "','".join(list(variables))
            db = 'performance_schema' if self.server_version > (5, 7) else 'information_schema'
            sql = f"""select * from {db}.global_variables where variable_name in ('{variables}');"""
        else:
            sql = "show global variables;"
        return self.query(sql=sql)

    def set_variable(self, variable_name, variable_value):
        """修改实例参数值"""
        sql = f"""set global {variable_name}={variable_value};"""
        return self.query(sql=sql)

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
