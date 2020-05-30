# -*- coding: UTF-8 -*-
# https://stackoverflow.com/questions/7942520/relationship-between-catalog-schema-user-and-database-instance
import logging
import traceback
import re
import sqlparse
import MySQLdb
import simplejson as json
import threading

from common.config import SysConfig
from common.utils.timer import FuncTimer
from sql.utils.sql_utils import get_syntax_type, get_full_sqlitem_list, get_exec_sqlitem_list
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
            self.conn = cx_Oracle.connect(self.user, self.password, dsn=dsn, encoding="UTF-8", nencoding="UTF-8")
        elif self.service_name:
            dsn = cx_Oracle.makedsn(self.host, self.port, service_name=self.service_name)
            self.conn = cx_Oracle.connect(self.user, self.password, dsn=dsn, encoding="UTF-8", nencoding="UTF-8")
        else:
            raise ValueError('sid 和 dsn 均未填写, 请联系管理页补充该实例配置.')
        return self.conn

    @property
    def name(self):
        return 'Oracle'

    @property
    def info(self):
        return 'Oracle engine'

    @property
    def auto_backup(self):
        """是否支持备份"""
        return True

    @staticmethod
    def get_backup_connection():
        """备份库连接"""
        archer_config = SysConfig()
        backup_host = archer_config.get('inception_remote_backup_host')
        backup_port = int(archer_config.get('inception_remote_backup_port', 3306))
        backup_user = archer_config.get('inception_remote_backup_user')
        backup_password = archer_config.get('inception_remote_backup_password')
        return MySQLdb.connect(host=backup_host,
                               port=backup_port,
                               user=backup_user,
                               passwd=backup_password,
                               charset='utf8mb4',
                               autocommit=True
                               )

    @property
    def server_version(self):
        conn = self.get_connection()
        version = conn.version
        return tuple([n for n in version.split('.')[:3]])

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
        result = self.query(sql="SELECT username FROM all_users order by username")
        sysschema = (
            'AUD_SYS', 'ANONYMOUS', 'APEX_030200', 'APEX_PUBLIC_USER', 'APPQOSSYS', 'BI USERS', 'CTXSYS', 'DBSNMP',
            'DIP USERS', 'EXFSYS', 'FLOWS_FILES', 'HR USERS', 'IX USERS', 'MDDATA', 'MDSYS', 'MGMT_VIEW', 'OE USERS',
            'OLAPSYS', 'ORACLE_OCM', 'ORDDATA', 'ORDPLUGINS', 'ORDSYS', 'OUTLN', 'OWBSYS', 'OWBSYS_AUDIT', 'PM USERS',
            'SCOTT', 'SH USERS', 'SI_INFORMTN_SCHEMA', 'SPATIAL_CSW_ADMIN_USR', 'SPATIAL_WFS_ADMIN_USR', 'SYS',
            'SYSMAN', 'SYSTEM', 'WMSYS', 'XDB', 'XS$NULL', 'DIP', 'OJVMSYS', 'LBACSYS')
        schema_list = [row[0] for row in result.rows if row[0] not in sysschema]
        result.rows = schema_list
        return result

    def get_all_tables(self, db_name, **kwargs):
        """获取table 列表, 返回一个ResultSet"""
        sql = f"""SELECT table_name FROM all_tables WHERE nvl(tablespace_name, 'no tablespace') NOT IN ('SYSTEM', 'SYSAUX') AND OWNER = '{db_name}' AND IOT_NAME IS NULL AND DURATION IS NULL order by table_name
        """
        result = self.query(db_name=db_name, sql=sql)
        tb_list = [row[0] for row in result.rows if row[0] not in ['test']]
        result.rows = tb_list
        return result

    def get_all_objects(self, db_name, **kwargs):
        """获取object_name 列表, 返回一个ResultSet"""
        sql = f"""SELECT object_name FROM all_objects WHERE OWNER = '{db_name}' """
        result = self.query(db_name=db_name, sql=sql)
        tb_list = [row[0] for row in result.rows if row[0] not in ['test']]
        result.rows = tb_list
        return result

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段, 返回一个ResultSet"""
        result = self.describe_table(db_name, tb_name)
        column_list = [row[0] for row in result.rows]
        result.rows = column_list
        return result

    def describe_table(self, db_name, tb_name, **kwargs):
        """return ResultSet"""
        # https://www.thepolyglotdeveloper.com/2015/01/find-tables-oracle-database-column-name/
        sql = f"""SELECT
        column_name,
        data_type,
        data_length,
        nullable,
        data_default
        FROM all_tab_cols
        WHERE table_name = '{tb_name}' and owner = '{db_name}' order by column_id
        """
        result = self.query(db_name=db_name, sql=sql)
        return result

    def object_name_check(self, db_name=None, object_name=''):
        """获取table 列表, 返回一个ResultSet"""
        if '.' in object_name:
            schema_name = object_name.split('.')[0]
            object_name = object_name.split('.')[1]
            sql = f"""SELECT object_name FROM all_objects WHERE OWNER = upper('{schema_name}') and  OBJECT_NAME =  upper('{object_name}')"""
        else:
            sql = f"""SELECT object_name FROM all_objects WHERE OWNER = upper('{db_name}') and  OBJECT_NAME = upper('{object_name}')"""
        result = self.query(db_name=db_name, sql=sql, close_conn=False)
        if result.affected_rows > 0:
            return True
        else:
            return False

    @staticmethod
    def get_sql_first_object_name(sql=''):
        """获取sql文本中的object_name"""
        object_name = ''
        if re.match(r"^create\s+table\s", sql):
            object_name = re.match(r"^create\s+table\s(.+?)(\s|\()", sql, re.M).group(1)
        elif re.match(r"^create\s+index\s", sql):
            object_name = re.match(r"^create\s+index\s(.+?)\s", sql, re.M).group(1)
        elif re.match(r"^create\s+unique\s+index\s", sql):
            object_name = re.match(r"^create\s+unique\s+index\s(.+?)\s", sql, re.M).group(1)
        elif re.match(r"^create\s+sequence\s", sql):
            object_name = re.match(r"^create\s+sequence\s(.+?)(\s|$)", sql, re.M).group(1)
        elif re.match(r"^alter\s+table\s", sql):
            object_name = re.match(r"^alter\s+table\s(.+?)\s", sql, re.M).group(1)
        elif re.match(r"^create\s+function\s", sql):
            object_name = re.match(r"^create\s+function\s(.+?)(\s|\()", sql, re.M).group(1)
        elif re.match(r"^create\s+view\s", sql):
            object_name = re.match(r"^create\s+view\s(.+?)\s", sql, re.M).group(1)
        elif re.match(r"^create\s+procedure\s", sql):
            object_name = re.match(r"^create\s+procedure\s(.+?)\s", sql, re.M).group(1)
        elif re.match(r"^create\s+package\s+body", sql):
            object_name = re.match(r"^create\s+package\s+body\s(.+?)\s", sql, re.M).group(1)
        elif re.match(r"^create\s+package\s", sql):
            object_name = re.match(r"^create\s+package\s(.+?)\s", sql, re.M).group(1)
        else:
            return object_name.strip()
        return object_name.strip()

    @staticmethod
    def check_create_index_table(sql='', object_name_list=None, db_name=''):
        object_name_list = object_name_list or set()
        if re.match(r"^create\s+index\s", sql):
            table_name = re.match(r"^create\s+index\s+.+\s+on\s(.+?)(\(|\s\()", sql, re.M).group(1)
            if '.' not in table_name:
                table_name = f"{db_name}.{table_name}"
            if table_name in object_name_list:
                return True
            else:
                return False
        elif re.match(r"^create\s+unique\s+index\s", sql):
            table_name = re.match(r"^create\s+unique\s+index\s+.+\s+on\s(.+?)(\(|\s\()", sql, re.M).group(1)
            if '.' not in table_name:
                table_name = f"{db_name}.{table_name}"
            if table_name in object_name_list:
                return True
            else:
                return False
        else:
            return False

    @staticmethod
    def get_dml_table(sql='', object_name_list=None, db_name=''):
        object_name_list = object_name_list or set()
        if re.match(r"^update", sql):
            table_name = re.match(r"^update\s(.+?)\s", sql, re.M).group(1)
            if '.' not in table_name:
                table_name = f"{db_name}.{table_name}"
            if table_name in object_name_list:
                return True
            else:
                return False
        elif re.match(r"^delete", sql):
            table_name = re.match(r"^delete\s+from\s(.+?)\s", sql, re.M).group(1)
            if '.' not in table_name:
                table_name = f"{db_name}.{table_name}"
            if table_name in object_name_list:
                return True
            else:
                return False
        elif re.match(r"^insert\s", sql):
            table_name = re.match(r"^insert\s+((into)|(all\s+into))\s(.+?)(\(|\s)", sql, re.M).group(4)
            if '.' not in table_name:
                table_name = f"{db_name}.{table_name}"
            if table_name in object_name_list:
                return True
            else:
                return False
        else:
            return False

    @staticmethod
    def where_check(sql=''):
        if re.match(r"^update((?!where).)*$|^delete((?!where).)*$", sql):
            return True
        else:
            parsed = sqlparse.parse(sql)[0]
            flattened = list(parsed.flatten())
            n_skip = 0
            flattened = flattened[:len(flattened) - n_skip]
            logical_operators = ('AND', 'OR', 'NOT', 'BETWEEN', 'ORDER BY', 'GROUP BY', 'HAVING')
            for t in reversed(flattened):
                if t.is_keyword:
                    return True
            return False

    def explain_check(self, db_name=None, sql='', close_conn=False):
        # 使用explain进行支持的SQL语法审核，连接需不中断，防止数据库不断fork进程的大批量消耗
        result = {'msg': '', 'rows': 0}
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            if db_name:
                cursor.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {db_name}")
            if re.match(r"^explain", sql, re.I):
                sql = sql
            else:
                sql = f"explain plan for {sql}"
            sql = sql.rstrip(';')
            cursor.execute(sql)
            # 获取影响行数
            cursor.execute(f"select CARDINALITY from SYS.PLAN_TABLE$ where id = 0")
            rows = cursor.fetchone()
            conn.rollback()
            if rows[0] is None:
                result['rows'] = 0
            else:
                result['rows'] = rows[0]
        except Exception as e:
            logger.warning(f"Oracle 语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}")
            result['msg'] = str(e)
        finally:
            if close_conn:
                self.close()
            return result

    def query_check(self, db_name=None, sql=''):
        # 查询语句的检查、注释去除、切分
        result = {'msg': '', 'bad_query': False, 'filtered_sql': sql, 'has_star': False}
        keyword_warning = ''
        star_patter = r"(^|,|\s)\*(\s|\(|$)"
        # 删除注释语句，进行语法判断，执行第一条有效sql
        try:
            sql = sqlparse.format(sql, strip_comments=True)
            sql = sqlparse.split(sql)[0]
            result['filtered_sql'] = re.sub(r';$', '', sql.strip())
            sql_lower = sql.lower()
        except IndexError:
            result['bad_query'] = True
            result['msg'] = '没有有效的SQL语句'
            return result
        if re.match(r"^select|^with|^explain", sql_lower) is None:
            result['bad_query'] = True
            result['msg'] = '不支持语法!'
            return result
        if re.search(star_patter, sql_lower) is not None:
            keyword_warning += '禁止使用 * 关键词\n'
            result['has_star'] = True
        if '+' in sql_lower:
            keyword_warning += '禁止使用 + 关键词\n'
            result['bad_query'] = True
        if result.get('bad_query') or result.get('has_star'):
            result['msg'] = keyword_warning
        return result

    def filter_sql(self, sql='', limit_num=0):
        sql_lower = sql.lower()
        # 对查询sql增加limit限制
        if re.match(r"^select|^with", sql_lower) and not (
                re.match(r"^select\s+sql_audit.", sql_lower) and sql_lower.find(" sql_audit where rownum <= ") != -1):
            sql = f"select sql_audit.* from ({sql.rstrip(';')}) sql_audit where rownum <= {limit_num}"
        return sql.strip()

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True, **kwargs):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            if db_name:
                cursor.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {db_name}")
            sql = sql.rstrip(';')
            # 支持oralce查询SQL执行计划语句
            if re.match(r"^explain", sql, re.I):
                cursor.execute(sql)
                # 重置SQL文本，获取SQL执行计划
                sql = f"select PLAN_TABLE_OUTPUT from table(dbms_xplan.display)"
            cursor.execute(sql)
            fields = cursor.description
            if any(x[1] == cx_Oracle.CLOB for x in fields):
                rows = [tuple([(c.read() if type(c) == cx_Oracle.LOB else c) for c in r]) for r in cursor]
                if int(limit_num) > 0:
                    rows = rows[0:int(limit_num)]
            else:
                if int(limit_num) > 0:
                    rows = cursor.fetchmany(int(limit_num))
                else:
                    rows = cursor.fetchall()
            result_set.column_list = [i[0] for i in fields] if fields else []
            result_set.rows = [tuple(x) for x in rows]
            result_set.affected_rows = len(result_set.rows)
        except Exception as e:
            logger.warning(f"Oracle 语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}")
            result_set.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result_set

    def query_masking(self, schema_name=None, sql='', resultset=None):
        """传入 sql语句, db名, 结果集,
        返回一个脱敏后的结果集"""
        # 仅对select语句脱敏
        if re.match(r"^select|^with", sql, re.I):
            filtered_result = brute_mask(self.instance, resultset)
            filtered_result.is_masked = True
        else:
            filtered_result = resultset
        return filtered_result

    def execute_check(self, db_name=None, sql='', close_conn=True):
        """
        上线单执行前的检查, 返回Review set
        update by Jan.song 20200302
        使用explain对数据修改预计进行检测
        """
        config = SysConfig()
        check_result = ReviewSet(full_sql=sql)
        # explain支持的语法
        explain_re = r"^merge|^update|^delete|^insert|^create\s+table|^create\s+index|^create\s+unique\s+index"
        # 禁用/高危语句检查
        line = 1
        # 保存SQL中的新建对象
        object_name_list = set()
        critical_ddl_regex = config.get('critical_ddl_regex', '')
        p = re.compile(critical_ddl_regex)
        check_result.syntax_type = 2  # TODO 工单类型 0、其他 1、DDL，2、DML
        try:
            sqlitemList = get_full_sqlitem_list(sql, db_name)
            for sqlitem in sqlitemList:
                sql_lower = sqlitem.statement.lower().rstrip(';')
                # 禁用语句
                if re.match(r"^select|^with|^explain", sql_lower):
                    check_result.is_critical = True
                    result = ReviewResult(id=line, errlevel=2,
                                          stagestatus='驳回不支持语句',
                                          errormessage='仅支持DML和DDL语句，查询语句请使用SQL查询功能！',
                                          sql=sqlitem.statement)
                # 高危语句
                elif critical_ddl_regex and p.match(sql_lower.strip()):
                    check_result.is_critical = True
                    result = ReviewResult(id=line, errlevel=2,
                                          stagestatus='驳回高危SQL',
                                          errormessage='禁止提交匹配' + critical_ddl_regex + '条件的语句！',
                                          sql=sqlitem.statement)
                # 驳回未带where数据修改语句，如确实需做全部删除或更新，显示的带上where 1=1
                elif re.match(r"^update((?!where).)*$|^delete((?!where).)*$", sql_lower):
                    check_result.is_critical = True
                    result = ReviewResult(id=line, errlevel=2,
                                          stagestatus='驳回未带where数据修改',
                                          errormessage='数据修改需带where条件！',
                                          sql=sqlitem.statement)
                # 驳回事务控制，会话控制SQL
                elif re.match(r"^set|^rollback|^exit", sql_lower):
                    check_result.is_critical = True
                    result = ReviewResult(id=line, errlevel=2,
                                          stagestatus='SQL中不能包含^set|^rollback|^exit',
                                          errormessage='SQL中不能包含^set|^rollback|^exit',
                                          sql=sqlitem.statement)

                # 通过explain对SQL做语法语义检查
                elif re.match(explain_re, sql_lower) and sqlitem.stmt_type == 'SQL':
                    if self.check_create_index_table(db_name=db_name, sql=sql_lower, object_name_list=object_name_list):
                        object_name = self.get_sql_first_object_name(sql=sql_lower)
                        if '.' in object_name:
                            object_name = object_name
                        else:
                            object_name = f"""{db_name}.{object_name}"""
                        object_name_list.add(object_name)
                        result = ReviewResult(id=line, errlevel=1,
                                              stagestatus='WARNING:新建表的新建索引语句暂无法检测！',
                                              errormessage='WARNING:新建表的新建索引语句暂无法检测！',
                                              stmt_type=sqlitem.stmt_type,
                                              object_owner=sqlitem.object_owner,
                                              object_type=sqlitem.object_type,
                                              object_name=sqlitem.object_name,
                                              sql=sqlitem.statement)
                    elif len(object_name_list) > 0 and self.get_dml_table(db_name=db_name, sql=sql_lower,
                                                                          object_name_list=object_name_list):
                        result = ReviewResult(id=line, errlevel=1,
                                              stagestatus='WARNING:新建表的数据修改暂无法检测！',
                                              errormessage='WARNING:新建表的数据修改暂无法检测！',
                                              stmt_type=sqlitem.stmt_type,
                                              object_owner=sqlitem.object_owner,
                                              object_type=sqlitem.object_type,
                                              object_name=sqlitem.object_name,
                                              sql=sqlitem.statement)
                    else:
                        result_set = self.explain_check(db_name=db_name, sql=sqlitem.statement, close_conn=False)
                        if result_set['msg']:
                            check_result.is_critical = True
                            result = ReviewResult(id=line, errlevel=2,
                                                  stagestatus='explain语法检查未通过！',
                                                  errormessage=result_set['msg'],
                                                  sql=sqlitem.statement)
                        else:
                            # 对create table\create index\create unique index语法做对象存在性检测
                            if re.match(r"^create\s+table|^create\s+index|^create\s+unique\s+index", sql_lower):
                                object_name = self.get_sql_first_object_name(sql=sql_lower)
                                # 保存create对象对后续SQL做存在性判断
                                if '.' in object_name:
                                    object_name = object_name
                                else:
                                    object_name = f"""{db_name}.{object_name}"""
                                if self.object_name_check(db_name=db_name,
                                                          object_name=object_name) or object_name in object_name_list:
                                    check_result.is_critical = True
                                    result = ReviewResult(id=line, errlevel=2,
                                                          stagestatus=f"""{object_name}对象已经存在！""",
                                                          errormessage=f"""{object_name}对象已经存在！""",
                                                          sql=sqlitem.statement)
                                else:
                                    object_name_list.add(object_name)
                                    if result_set['rows'] > 1000:
                                        result = ReviewResult(id=line, errlevel=1,
                                                              stagestatus='影响行数大于1000，请关注',
                                                              errormessage='影响行数大于1000，请关注',
                                                              sql=sqlitem.statement,
                                                              stmt_type=sqlitem.stmt_type,
                                                              object_owner=sqlitem.object_owner,
                                                              object_type=sqlitem.object_type,
                                                              object_name=sqlitem.object_name,
                                                              affected_rows=result_set['rows'],
                                                              execute_time=0, )
                                    else:
                                        result = ReviewResult(id=line, errlevel=0,
                                                              stagestatus='Audit completed',
                                                              errormessage='None',
                                                              sql=sqlitem.statement,
                                                              stmt_type=sqlitem.stmt_type,
                                                              object_owner=sqlitem.object_owner,
                                                              object_type=sqlitem.object_type,
                                                              object_name=sqlitem.object_name,
                                                              affected_rows=result_set['rows'],
                                                              execute_time=0, )
                            else:
                                if result_set['rows'] > 1000:
                                    result = ReviewResult(id=line, errlevel=1,
                                                          stagestatus='影响行数大于1000，请关注',
                                                          errormessage='影响行数大于1000，请关注',
                                                          sql=sqlitem.statement,
                                                          stmt_type=sqlitem.stmt_type,
                                                          object_owner=sqlitem.object_owner,
                                                          object_type=sqlitem.object_type,
                                                          object_name=sqlitem.object_name,
                                                          affected_rows=result_set['rows'],
                                                          execute_time=0, )
                                else:
                                    result = ReviewResult(id=line, errlevel=0,
                                                          stagestatus='Audit completed',
                                                          errormessage='None',
                                                          sql=sqlitem.statement,
                                                          stmt_type=sqlitem.stmt_type,
                                                          object_owner=sqlitem.object_owner,
                                                          object_type=sqlitem.object_type,
                                                          object_name=sqlitem.object_name,
                                                          affected_rows=result_set['rows'],
                                                          execute_time=0, )
                # 其它无法用explain判断的语句
                else:
                    # 对alter table做对象存在性检查
                    if re.match(r"^alter\s+table\s", sql_lower):
                        object_name = self.get_sql_first_object_name(sql=sql_lower)
                        if '.' in object_name:
                            object_name = object_name
                        else:
                            object_name = f"""{db_name}.{object_name}"""
                        if not self.object_name_check(db_name=db_name,
                                                      object_name=object_name) and object_name not in object_name_list:
                            check_result.is_critical = True
                            result = ReviewResult(id=line, errlevel=2,
                                                  stagestatus=f"""{object_name}对象不存在！""",
                                                  errormessage=f"""{object_name}对象不存在！""",
                                                  sql=sqlitem.statement)
                        else:
                            result = ReviewResult(id=line, errlevel=1,
                                                  stagestatus='当前平台，此语法不支持审核！',
                                                  errormessage='当前平台，此语法不支持审核！',
                                                  sql=sqlitem.statement,
                                                  stmt_type=sqlitem.stmt_type,
                                                  object_owner=sqlitem.object_owner,
                                                  object_type=sqlitem.object_type,
                                                  object_name=sqlitem.object_name,
                                                  affected_rows=0,
                                                  execute_time=0, )
                    # 对create做对象存在性检查
                    elif re.match(r"^create", sql_lower):
                        object_name = self.get_sql_first_object_name(sql=sql_lower)
                        if '.' in object_name:
                            object_name = object_name
                        else:
                            object_name = f"""{db_name}.{object_name}"""
                        if self.object_name_check(db_name=db_name,
                                                  object_name=object_name) or object_name in object_name_list:
                            check_result.is_critical = True
                            result = ReviewResult(id=line, errlevel=2,
                                                  stagestatus=f"""{object_name}对象已经存在！""",
                                                  errormessage=f"""{object_name}对象已经存在！""",
                                                  sql=sqlitem.statement)
                        else:
                            object_name_list.add(object_name)
                            result = ReviewResult(id=line, errlevel=1,
                                                  stagestatus='当前平台，此语法不支持审核！',
                                                  errormessage='当前平台，此语法不支持审核！',
                                                  sql=sqlitem.statement,
                                                  stmt_type=sqlitem.stmt_type,
                                                  object_owner=sqlitem.object_owner,
                                                  object_type=sqlitem.object_type,
                                                  object_name=sqlitem.object_name,
                                                  affected_rows=0,
                                                  execute_time=0, )
                    else:
                        result = ReviewResult(id=line, errlevel=1,
                                              stagestatus='当前平台，此语法不支持审核！',
                                              errormessage='当前平台，此语法不支持审核！',
                                              sql=sqlitem.statement,
                                              stmt_type=sqlitem.stmt_type,
                                              object_owner=sqlitem.object_owner,
                                              object_type=sqlitem.object_type,
                                              object_name=sqlitem.object_name,
                                              affected_rows=0,
                                              execute_time=0, )
                # 判断工单类型
                if get_syntax_type(sql=sqlitem.statement, db_type='oracle') == 'DDL':
                    check_result.syntax_type = 1
                check_result.rows += [result]
                # 遇到禁用和高危语句直接返回，提高效率
                if check_result.is_critical:
                    check_result.error_count += 1
                    return check_result
                line += 1
        except Exception as e:
            logger.warning(f"Oracle 语句执行报错，第{line}个SQL：{sqlitem.statement}，错误信息{traceback.format_exc()}")
            check_result.error = str(e)
        finally:
            if close_conn:
                self.close()
        return check_result

    def execute_workflow(self, workflow, close_conn=True):
        """执行上线单，返回Review set
           原来的逻辑是根据 sql_content简单来分割SQL，进而再执行这些SQL
           新的逻辑变更为根据审核结果中记录的sql来执行，
           如果是PLSQL存储过程等对象定义操作，还需检查确认新建对象是否编译通过!
        """
        review_content = workflow.sqlworkflowcontent.review_content
        review_result = json.loads(review_content)
        sqlitemList = get_exec_sqlitem_list(review_result, workflow.db_name)

        sql = workflow.sqlworkflowcontent.sql_content
        execute_result = ReviewSet(full_sql=sql)

        line = 1
        statement = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            # 获取执行工单时间，用于备份SQL的日志挖掘起始时间
            cursor.execute(f"alter session set nls_date_format='yyyy-mm-dd hh24:mi:ss'")
            cursor.execute(f"select sysdate from dual")
            rows = cursor.fetchone()
            begin_time = rows[0]
            # 逐条执行切分语句，追加到执行结果中
            for sqlitem in sqlitemList:
                statement = sqlitem.statement
                if sqlitem.stmt_type == "SQL":
                    statement = statement.rstrip(';')
                with FuncTimer() as t:
                    if statement != '':
                        cursor.execute(statement)
                        conn.commit()

                rowcount = cursor.rowcount
                stagestatus = "Execute Successfully"
                if sqlitem.stmt_type == "PLSQL" and sqlitem.object_name and sqlitem.object_name != 'ANONYMOUS' and sqlitem.object_name != '':
                    query_obj_sql = f"""SELECT OBJECT_NAME, STATUS, TO_CHAR(LAST_DDL_TIME, 'YYYY-MM-DD HH24:MI:SS') FROM ALL_OBJECTS 
                                         WHERE OWNER = '{sqlitem.object_owner}' 
                                         AND OBJECT_NAME = '{sqlitem.object_name}' 
                                        """
                    cursor.execute(query_obj_sql)
                    row = cursor.fetchone()
                    if row:
                        status = row[1]
                        if status and status == "INVALID":
                            stagestatus = "Compile Failed. Object " + sqlitem.object_owner + "." + sqlitem.object_name + " is invalid."
                    else:
                        stagestatus = "Compile Failed. Object " + sqlitem.object_owner + "." + sqlitem.object_name + " doesn't exist."

                    if stagestatus != "Execute Successfully":
                        raise Exception(stagestatus)

                execute_result.rows.append(ReviewResult(
                    id=line,
                    errlevel=0,
                    stagestatus=stagestatus,
                    errormessage='None',
                    sql=statement,
                    affected_rows=cursor.rowcount,
                    execute_time=t.cost,
                ))
                line += 1
        except Exception as e:
            logger.warning(f"Oracle命令执行报错，工单id：{workflow.id}，语句：{statement or sql}， 错误信息：{traceback.format_exc()}")
            execute_result.error = str(e)
            # conn.rollback()
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
            for sqlitem in sqlitemList[line - 1:]:
                execute_result.rows.append(ReviewResult(
                    id=line,
                    errlevel=0,
                    stagestatus='Audit completed',
                    errormessage=f'前序语句失败, 未执行',
                    sql=sqlitem.statement,
                    affected_rows=0,
                    execute_time=0,
                ))
                line += 1
        finally:
            # 备份
            if workflow.is_backup:
                try:
                    cursor.execute(f"select sysdate from dual")
                    rows = cursor.fetchone()
                    end_time = rows[0]
                    self.backup(workflow, cursor=cursor, begin_time=begin_time, end_time=end_time)
                except Exception as e:
                    logger.error(f"Oracle工单备份异常，工单id：{workflow.id}， 错误信息：{traceback.format_exc()}")
            if close_conn:
                self.close()
        return execute_result

    def backup(self, workflow, cursor, begin_time, end_time):
        """
        :param workflow: 工单对象，作为备份记录与工单的关联列
        :param cursor: 执行SQL的当前会话游标
        :param begin_time: 执行SQL开始时间
        :param end_time: 执行SQL结束时间
        :return:
        """
        # add Jan.song 2020402
        # 生成回滚SQL,执行用户需要有grant select any transaction to 权限，需要有grant execute on dbms_logmnr to权限
        # 数据库需开启最小化附加日志alter database add supplemental log data;
        # 需为归档模式;开启附件日志会增加redo日志量,一般不会有多大影响，需评估归档磁盘空间，redo磁盘IO性能
        try:
            # 备份存放数据库和MySQL备份库统一，需新建备份用database和table，table存放备份SQL，记录使用workflow.id关联上线工单
            workflow_id = workflow.id
            conn = self.get_backup_connection()
            backup_cursor = conn.cursor()
            backup_cursor.execute(f"""create database if not exists ora_backup;""")
            backup_cursor.execute(f"use ora_backup;")
            backup_cursor.execute(f"""CREATE TABLE if not exists `sql_rollback` (
                                       `id` bigint(20) NOT NULL AUTO_INCREMENT,
                                       `redo_sql` mediumtext,
                                       `undo_sql` mediumtext,
                                       `workflow_id` bigint(20) NOT NULL,
                                        PRIMARY KEY (`id`),
                                        key `idx_sql_rollback_01` (`workflow_id`)
                                     ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
            # 使用logminer抓取回滚SQL
            logmnr_start_sql = f'''begin
                                        dbms_logmnr.start_logmnr(
                                        starttime=>to_date('{begin_time}','yyyy-mm-dd hh24:mi:ss'),
                                        endtime=>to_date('{end_time}','yyyy/mm/dd hh24:mi:ss'),
                                        options=>dbms_logmnr.dict_from_online_catalog + dbms_logmnr.continuous_mine);
                                    end;'''
            undo_sql = f'''select sql_redo,sql_undo from v$logmnr_contents 
                                  where  SEG_OWNER not in ('SYS','SYSTEM')
                                         and session# = (select sid from v$mystat where rownum = 1)
                                         and serial# = (select serial# from v$session s where s.sid = (select sid from v$mystat where rownum = 1 )) order by scn desc'''
            logmnr_end_sql = f'''begin
                                    dbms_logmnr.end_logmnr;
                                 end;'''
            cursor.execute(logmnr_start_sql)
            cursor.execute(undo_sql)
            rows = cursor.fetchall()
            cursor.execute(logmnr_end_sql)
            if len(rows) > 0:
                for row in rows:
                    redo_sql = f"{row[0]}"
                    redo_sql = redo_sql.replace("'", "\\'")
                    if row[1] is None:
                        undo_sql = f' '
                    else:
                        undo_sql = f"{row[1]}"
                    undo_sql = undo_sql.replace("'", "\\'")
                    # 回滚SQL入库
                    sql = f"""insert into sql_rollback(redo_sql,undo_sql,workflow_id) values('{redo_sql}','{undo_sql}',{workflow_id});"""
                    backup_cursor.execute(sql)
        except Exception as e:
            logger.warning(f"备份失败，错误信息{traceback.format_exc()}")
            return False
        finally:
            # 关闭连接
            if conn:
                conn.close()
        return True

    def get_rollback(self, workflow):
        """
         add by Jan.song 20200402
        获取回滚语句，并且按照执行顺序倒序展示，return ['源语句'，'回滚语句']
        """
        list_execute_result = json.loads(workflow.sqlworkflowcontent.execute_result)
        # 回滚语句倒序展示
        list_execute_result.reverse()
        list_backup_sql = []
        try:
            # 创建连接
            conn = self.get_backup_connection()
            cur = conn.cursor()
            sql = f"""select redo_sql,undo_sql from sql_rollback where workflow_id = {workflow.id} order by id;"""
            cur.execute(f"use ora_backup;")
            cur.execute(sql)
            list_tables = cur.fetchall()
            for row in list_tables:
                redo_sql = row[0]
                undo_sql = row[1]
                # 拼接成回滚语句列表,['源语句'，'回滚语句']
                list_backup_sql.append([redo_sql, undo_sql])
        except Exception as e:
            logger.error(f"获取回滚语句报错，异常信息{traceback.format_exc()}")
            raise Exception(e)
        # 关闭连接
        if conn:
            conn.close()
        return list_backup_sql

    def sqltuningadvisor(self, db_name=None, sql='', close_conn=True, **kwargs):
        """
        add by Jan.song 20200421
        使用DBMS_SQLTUNE包做sql tuning支持
        执行用户需要有advior角色
        返回 ResultSet
        """
        result_set = ResultSet(full_sql=sql)
        task_name = 'sqlaudit' + f'''{threading.currentThread().ident}'''
        task_begin = 0
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            sql = sql.rstrip(';')
            # 创建分析任务
            create_task_sql = f'''DECLARE
                                  my_task_name VARCHAR2(30);
                                  my_sqltext  CLOB;
                                  BEGIN
                                  my_sqltext := '{sql}';
                                  my_task_name := DBMS_SQLTUNE.CREATE_TUNING_TASK(
                                  sql_text    => my_sqltext,
                                  user_name   => '{db_name}', 
                                  scope       => 'COMPREHENSIVE',
                                  time_limit  => 30,
                                  task_name   => '{task_name}',
                                  description => 'tuning');
                                  DBMS_SQLTUNE.EXECUTE_TUNING_TASK( task_name => '{task_name}');
                                  END;'''
            task_begin = 1
            cursor.execute(create_task_sql)
            # 获取分析报告
            get_task_sql = f'''select DBMS_SQLTUNE.REPORT_TUNING_TASK( '{task_name}') from dual'''
            cursor.execute(get_task_sql)
            fields = cursor.description
            if any(x[1] == cx_Oracle.CLOB for x in fields):
                rows = [tuple([(c.read() if type(c) == cx_Oracle.LOB else c) for c in r]) for r in cursor]
            else:
                rows = cursor.fetchall()
            result_set.column_list = [i[0] for i in fields] if fields else []
            result_set.rows = [tuple(x) for x in rows]
            result_set.affected_rows = len(result_set.rows)
        except Exception as e:
            logger.warning(f"Oracle 语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}")
            result_set.error = str(e)
        finally:
            # 结束分析任务
            if task_begin == 1:
                end_sql = f'''DECLARE 
                             begin 
                             dbms_sqltune.drop_tuning_task('{task_name}');
                             end;'''
                cursor.execute(end_sql)
            if close_conn:
                self.close()
        return result_set

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
