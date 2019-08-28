# -*- coding: UTF-8 -*-
import logging
import traceback
import re
import sqlparse

import phoenixdb
from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult

logger = logging.getLogger('default')


class PhoenixEngine(EngineBase):
    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn

        database_url = f'http://{self.host}:{self.port}/'
        self.conn = phoenixdb.connect(database_url, autocommit=True)
        return self.conn

    def get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet"""
        sql = "SELECT DISTINCT TABLE_SCHEM FROM SYSTEM.CATALOG"
        result = self.query(sql=sql)
        result.rows = [row[0] for row in result.rows if row[0] is not None]
        return result

    def get_all_tables(self, db_name):
        """获取table 列表, 返回一个ResultSet"""
        sql = f"SELECT DISTINCT TABLE_NAME FROM SYSTEM.CATALOG WHERE TABLE_SCHEM = '{db_name}'"
        result = self.query(db_name=db_name, sql=sql)
        result.rows = [row[0] for row in result.rows if row[0] is not None]
        return result

    def get_all_columns_by_tb(self, db_name, tb_name):
        """获取所有字段, 返回一个ResultSet"""

        sql = f""" SELECT DISTINCT COLUMN_NAME FROM SYSTEM.CATALOG
 WHERE TABLE_SCHEM = '{db_name}' AND table_name = '{tb_name}' AND column_name is not null"""
        return self.query(sql=sql)

    def describe_table(self, db_name, tb_name):
        """return ResultSet"""
        sql = f"""SELECT COLUMN_NAME,SqlTypeName(DATA_TYPE) FROM SYSTEM.CATALOG
 WHERE TABLE_SCHEM = '{db_name}' and table_name = '{tb_name}' and column_name is not null"""
        result = self.query(sql=sql)
        return result

    def query_check(self, db_name=None, sql=''):
        # 查询语句的检查、注释去除、切分
        result = {'msg': '', 'bad_query': False, 'filtered_sql': sql, 'has_star': False}
        keyword_warning = ''
        sql_whitelist = ['select', 'explain']
        # 根据白名单list拼接pattern语句
        whitelist_pattern = "^" + "|^".join(sql_whitelist)
        # 删除注释语句，进行语法判断，执行第一条有效sql
        try:
            sql = sql.format(sql, strip_comments=True)
            sql = sqlparse.split(sql)[0]
            result['filtered_sql'] = sql.strip()
            # sql_lower = sql.lower()
        except IndexError:
            result['has_star'] = True
            result['msg'] = '没有有效的SQL语句'
            return result
        if re.match(whitelist_pattern, sql) is None:
            result['bad_query'] = True
            result['msg'] = '仅支持{}语法!'.format(','.join(sql_whitelist))
            return result
        if result.get('bad_query'):
            result['msg'] = keyword_warning
        return result

    def filter_sql(self, sql='', limit_num=0):
        """检查是SELECT语句否添加了limit限制关键词"""
        sql = sql.rstrip(';').strip()
        if re.match(r"^select", sql, re.I):
            if not re.compile(r'limit\s+(\d+)\s*((,|offset)\s*\d+)?\s*$', re.I).search(sql):
                sql = f'{sql} limit {limit_num}'
        else:
            sql = f'{sql};'
        return sql.strip()

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
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
            logger.warning(f"PhoenixDB语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}")
            result_set.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result_set

    def query_masking(self, db_name=None, sql='', resultset=None):
        """传入 sql语句, db名, 结果集, 返回一个脱敏后的结果集"""
        return resultset

    def execute_check(self, db_name=None, sql=''):
        """上线单执行前的检查, 返回Review set"""
        check_result = ReviewSet(full_sql=sql)
        # 切分语句，追加到检测结果中，默认全部检测通过
        rowid = 1
        split_sql = sqlparse.split(sql)
        for statement in split_sql:
            check_result.rows.append(ReviewResult(
                id=rowid,
                errlevel=0,
                stagestatus='Audit completed',
                errormessage='None',
                sql=statement,
                affected_rows=0,
                execute_time=0, )
            )
            rowid += 1
        return check_result

    def execute_workflow(self, workflow):
        """PhoenixDB无需备份"""
        return self.execute(db_name=workflow.db_name, sql=workflow.sqlworkflowcontent.sql_content)

    def execute(self, db_name=None, sql='', close_conn=True):
        """原生执行语句"""
        execute_result = ReviewSet(full_sql=sql)
        conn = self.get_connection(db_name=db_name)
        cursor = conn.cursor()
        rowid = 1
        split_sql = sqlparse.split(sql)
        for statement in split_sql:
            try:
                cursor.execute(statement.rstrip(";"))
            except Exception as e:
                logger.error(f"Phoenix命令执行报错，语句：{sql}， 错误信息：{traceback.format_exc()}")
                execute_result.error = str(e)
                execute_result.rows.append(ReviewResult(
                    id=rowid,
                    errlevel=2,
                    stagestatus='Execute Failed',
                    errormessage=f'异常信息：{e}',
                    sql=statement,
                    affected_rows=0,
                    execute_time=0,
                ))
                break
            else:
                execute_result.rows.append(ReviewResult(
                    id=rowid,
                    errlevel=0,
                    stagestatus='Execute Successfully',
                    errormessage='None',
                    sql=statement,
                    affected_rows=cursor.rowcount,
                    execute_time=0,
                ))
            rowid += 1
        if execute_result.error:
            # 如果失败, 将剩下的部分加入结果集返回
            for statement in split_sql[rowid:]:
                execute_result.rows.append(ReviewResult(
                    id=rowid,
                    errlevel=2,
                    stagestatus='Execute Failed',
                    errormessage=f'前序语句失败, 未执行',
                    sql=statement,
                    affected_rows=0,
                    execute_time=0,
                ))
                rowid += 1

        if close_conn:
            self.close()
        return execute_result

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
