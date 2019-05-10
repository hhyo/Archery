# -*- coding: UTF-8 -*-
# https://stackoverflow.com/questions/7942520/relationship-between-catalog-schema-user-and-database-instance
import logging
import traceback
import re
import sqlparse

from . import EngineBase
import cx_Oracle
from .models import ResultSet, ReviewSet, ReviewResult
from sql.utils.data_masking import brute_mask

logger = logging.getLogger('default')


class OracleEngine(EngineBase):
    
    def __init__(self, instance=None):
        super(OracleEngine, self).__init__(instance=instance)
        self.service_name = instance.service_name
        self.sid = instance.sid
    
    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        if self.sid:
            dsn = cx_Oracle.makedsn(self.host, self.port, self.sid)
            self.conn = cx_Oracle.connect(self.user, self.password, dsn=dsn)
        elif self.service_name:
            dsn = cx_Oracle.makedsn(self.host, self.port, service_name=self.service_name)
            self.conn = cx_Oracle.connect(self.user, self.password, dsn=dsn)
        else:
            self.conn = None
        return self.conn

    def get_all_databases(self):
        """获取数据库列表， 返回resultSet 供上层调用， 底层实际上是获取oracle的schema列表"""
        return self._get_all_schemas()

    def _get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet"""
        sql = "select name from v$database"
        result = self.query(sql=sql)
        db_list = [row[0] for row in result.rows]
        result.rows = db_list
        return result

    def _get_all_instances(self):
        """获取实例列表, 返回一个ResultSet"""
        sql = "select instance_name from v$instance"
        result = self.query(sql=sql)
        instance_list = [row[0] for row in result.rows]
        result.rows = instance_list
        return result

    def _get_all_schemas(self):
        """
        获取模式列表
        :return:
        """
        result = self.query(sql="select username from sys.dba_users")
        schema_list = [row[0] for row in result.rows if row[0] not in ['ORACLE_OCM', 'DIP', 'DBSNMP', 'APPQOSSYS',
                                                                       'MGMT_VIEW', 'SYS', 'SYSTEM', 'OUTLN']]
        result.rows = schema_list
        return result

    def get_all_tables(self, schema_name):
        """获取table 列表, 返回一个ResultSet"""
        sql = f"""select
        TABLE_NAME
        from dba_tab_privs
        where grantee in ('{schema_name}')
        union
        select
        OBJECT_NAME
        from dba_objects
        WHERE OWNER IN ('{schema_name}') and object_type in ('TABLE')
        """
        result = self.query(sql=sql)
        tb_list = [row[0] for row in result.rows if row[0] not in ['test']]
        result.rows = tb_list
        return result

    def get_all_columns_by_tb(self, schema_name, tb_name):
        """获取所有字段, 返回一个ResultSet"""
        result = self.describe_table(schema_name, tb_name)
        column_list = [row[0] for row in result.rows]
        result.rows = column_list
        return result

    def describe_table(self, schema_name, tb_name):
        """return ResultSet"""
        # https://www.thepolyglotdeveloper.com/2015/01/find-tables-oracle-database-column-name/
        sql = f"""SELECT
        column_name,
        data_type,
        data_length,
        nullable,
        data_default
        FROM all_tab_cols
        WHERE table_name = '{tb_name}'
        """
        result = self.query(sql=sql)
        return result

    def query_check(self, db_name=None, sql=''):
        # 查询语句的检查、注释去除、切分
        result = {'msg': '', 'bad_query': False, 'filtered_sql': sql, 'has_star': False}
        keyword_warning = ''
        star_patter = r"(^|,| )\*( |\(|$)"
        # 删除注释语句，进行语法判断，执行第一条有效sql
        try:
            sql = sql.format(sql, strip_comments=True)
            sql = sqlparse.split(sql)[0]
            result['filtered_sql'] = re.sub(r';$', '', sql.strip())
            sql_lower = sql.lower()
        except IndexError:
            result['bad_query'] = True
            result['msg'] = '没有有效的SQL语句'
            return result
        if re.match(r"^select", sql_lower) is None:
            result['bad_query'] = True
            result['msg'] = '仅支持^select语法!'
            return result
        if re.search(star_patter, sql_lower) is not None:
            keyword_warning += '禁止使用 * 关键词\n'
            result['has_star'] = True
        if '+' in sql_lower:
            keyword_warning += '禁止使用 + 关键词\n'
            result['bad_query'] = True
        if result.get('bad_query'):
            result['msg'] = keyword_warning
        return result

    def filter_sql(self, sql='', limit_num=0):
        sql_lower = sql.lower()
        # 对查询sql增加limit限制
        if re.match(r"^select", sql_lower):
            if sql_lower.find(' rownum ') == -1:
                if sql_lower.find(' where ') == -1:
                    return f"{sql.rstrip(';')} WHERE ROWNUM <= {limit_num}"
                else:
                    return f"{sql.rstrip(';')} AND ROWNUM <= {limit_num}"
        return sql.strip()

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            # if schema_name:
            #     cursor.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {schema_name}")
            cursor.execute(sql)
            if int(limit_num) > 0:
                rows = cursor.fetchmany(int(limit_num))
            else:
                rows = cursor.fetchall()
            fields = cursor.description

            result_set.column_list = [i[0] for i in fields] if fields else []
            result_set.rows = [tuple(x) for x in rows]
            result_set.affected_rows = len(result_set.rows)
        except Exception as e:
            logger.error(f"Oracle 语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}")
            result_set.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result_set

    def query_masking(self, schema_name=None, sql='', resultset=None):
        """传入 sql语句, db名, 结果集,
        返回一个脱敏后的结果集"""
        # 仅对select语句脱敏
        if re.match(r"^select", sql, re.I):
            filtered_result = brute_mask(resultset)
            filtered_result.is_masked = True
        else:
            filtered_result = resultset
        return filtered_result

    def execute_check(self, db_name=None, sql=''):
        """上线单执行前的检查, 返回Review set"""
        check_result = ReviewSet(full_sql=sql)
        result = ReviewResult(id=1,
                              errlevel=0,
                              stagestatus='Audit completed',
                              errormessage='None',
                              sql=sql,
                              affected_rows=0,
                              execute_time=0, )
        check_result.rows += [result]
        return check_result

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
