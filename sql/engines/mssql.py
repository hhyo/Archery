# -*- coding: UTF-8 -*-
import logging
import traceback
import re
import sqlparse

from . import EngineBase
import pyodbc
from .models import ResultSet, ReviewSet, ReviewResult
from common.config import SysConfig
from sql.utils.data_masking import brute_mask
from django.utils import timezone

logger = logging.getLogger('default')


class MssqlEngine(EngineBase):
    def get_connection(self, db_name=None):
        connstr = """DRIVER=ODBC Driver 17 for SQL Server;SERVER={0},{1};UID={2};PWD={3};
client charset = UTF-8;connect timeout=10;CHARSET={4};""".format(self.host, self.port, self.user, self.password,
                                                                 self.instance.charset or 'UTF8')
        if self.conn:
            return self.conn
        self.conn = pyodbc.connect(connstr)
        return self.conn

    def get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet"""
        sql = "SELECT name FROM master.sys.databases"
        result = self.query(sql=sql)
        db_list = [row[0] for row in result.rows
                   if row[0] not in ('master', 'msdb', 'tempdb', 'model')]
        result.rows = db_list
        return result

    def get_all_tables(self, db_name):
        """获取table 列表, 返回一个ResultSet"""
        sql = """SELECT TABLE_NAME
        FROM {0}.INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE';""".format(db_name)
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
        """return ResultSet"""
        sql = r"""select
        c.name ColumnName,
        t.name ColumnType,
        c.length  ColumnLength,
        c.scale   ColumnScale,
        c.isnullable ColumnNull,
            case when i.id is not null then 'Y' else 'N' end TablePk
        from (select name,id,uid from {0}..sysobjects where (xtype='U' or xtype='V') ) o 
        inner join {0}..syscolumns c on o.id=c.id 
        inner join {0}..systypes t on c.xtype=t.xusertype 
        left join {0}..sysusers u on u.uid=o.uid
        left join (select name,id,uid,parent_obj from {0}..sysobjects where xtype='PK' )  opk on opk.parent_obj=o.id 
        left join (select id,name,indid from {0}..sysindexes) ie on ie.id=o.id and ie.name=opk.name
        left join {0}..sysindexkeys i on i.id=o.id and i.colid=c.colid and i.indid=ie.indid
        WHERE O.name NOT LIKE 'MS%' AND O.name NOT LIKE 'SY%'
        and O.name='{1}'
        order by o.name,c.colid""".format(db_name, tb_name)
        result = self.query(sql=sql)
        return result

    def query_check(self, db_name=None, sql=''):
        # 查询语句的检查、注释去除、切分
        result = {'msg': '', 'bad_query': False, 'filtered_sql': sql, 'has_star': False}
        banned_keywords = ["ascii", "char", "charindex", "concat", "concat_ws", "difference", "format",
                           "len", "nchar", "patindex", "quotename", "replace", "replicate",
                           "reverse", "right", "soundex", "space", "str", "string_agg",
                           "string_escape", "string_split", "stuff", "substring", "trim", "unicode"]
        keyword_warning = ''
        star_patter = r"(^|,| )\*( |\(|$)"
        sql_whitelist = ['select', 'sp_helptext']
        # 根据白名单list拼接pattern语句
        whitelist_pattern = "^" + "|^".join(sql_whitelist)
        # 删除注释语句，进行语法判断，执行第一条有效sql
        try:
            sql = sql.format(sql, strip_comments=True)
            sql = sqlparse.split(sql)[0]
            result['filtered_sql'] = sql.strip()
            sql_lower = sql.lower()
        except IndexError:
            result['has_star'] = True
            result['msg'] = '没有有效的SQL语句'
            return result
        if re.match(whitelist_pattern, sql_lower) is None:
            result['bad_query'] = True
            result['msg'] = '仅支持{}语法!'.format(','.join(sql_whitelist))
            return result
        if re.search(star_patter, sql_lower) is not None:
            keyword_warning += '禁止使用 * 关键词\n'
            result['bad_query'] = True
            result['has_star'] = True
        if '+' in sql_lower:
            keyword_warning += '禁止使用 + 关键词\n'
            result['bad_query'] = True
        for keyword in banned_keywords:
            pattern = r"(^|,| |=){}( |\(|$)".format(keyword)
            if re.search(pattern, sql_lower) is not None:
                keyword_warning += '禁止使用 {} 关键词\n'.format(keyword)
                result['bad_query'] = True
        if result.get('bad_query'):
            result['msg'] = keyword_warning
        return result

    def filter_sql(self, sql='', limit_num=0):
        sql_lower = sql.lower()
        # 对查询sql增加limit限制
        if re.match(r"^select", sql_lower):
            if sql_lower.find(' top ') == -1:
                return sql_lower.replace('select', 'select top {}'.format(limit_num))
        return sql.strip()

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            if db_name:
                cursor.execute('use [{}];'.format(db_name))
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
            logger.error(f"MsSQL语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}")
            result_set.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result_set

    def query_masking(self, db_name=None, sql='', resultset=None):
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
        # 切分语句，追加到检测结果中，默认全部检测通过
        split_reg = re.compile('^GO$', re.I | re.M)
        sql = re.split(split_reg, sql, 0)
        sql = filter(None, sql)
        split_sql = [f"""use [{db_name}]"""]
        for i in sql:
            split_sql = split_sql + [i]
        rowid = 1
        for statement in split_sql:
            check_result.rows.append(ReviewResult(
                id=rowid,
                errlevel=0,
                stagestatus='Audit completed',
                errormessage='None',
                sql=statement,
                affected_rows=0,
                execute_time=0, ))
            rowid += 1
        return check_result

    def execute_workflow(self, workflow):
        if workflow.is_backup:
            # TODO mssql 备份未实现
            pass
        return self.execute(db_name=workflow.db_name, sql=workflow.sqlworkflowcontent.sql_content)

    def execute(self, db_name=None, sql='', close_conn=True):
        """执行sql语句 返回 Review set"""
        execute_result = ReviewSet(full_sql=sql)
        conn = self.get_connection(db_name=db_name)
        cursor = conn.cursor()
        split_reg = re.compile('^GO$', re.I | re.M)
        sql = re.split(split_reg, sql, 0)
        sql = filter(None, sql)
        split_sql = [f"""use [{db_name}]"""]
        for i in sql:
            split_sql = split_sql + [i]
        rowid = 1
        for statement in split_sql:
            try:
                cursor.execute(statement)
            except Exception as e:
                logger.error(f"Mssql命令执行报错，语句：{sql}， 错误信息：{traceback.format_exc()}")
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
            # 如果失败, 将剩下的部分加入结果集, 并将语句回滚
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
            cursor.rollback()
            for row in execute_result.rows:
                if row.stagestatus == 'Execute Successfully':
                    row.stagestatus += '\nRollback Successfully'
        else:
            cursor.commit()
        if close_conn:
            self.close()
        return execute_result

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
