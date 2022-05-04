# -*- coding: UTF-8 -*-
import logging
import traceback
import MySQLdb
import re

import schemaobject
import sqlparse
from MySQLdb.constants import FIELD_TYPE
from schemaobject.connection import build_database_url

from sql.engines.goinception import GoInceptionEngine
from sql.utils.sql_utils import get_syntax_type, remove_comments
from . import EngineBase
from .models import ResultSet, ReviewResult, ReviewSet
from sql.utils.data_masking import data_masking
from common.config import SysConfig

logger = logging.getLogger('default')


class MysqlEngine(EngineBase):

    def __init__(self, instance=None):
        super().__init__(instance=instance)
        self.config = SysConfig()
        self.inc_engine = GoInceptionEngine()

    def get_connection(self, db_name=None):
        # https://stackoverflow.com/questions/19256155/python-mysqldb-returning-x01-for-bit-values
        conversions = MySQLdb.converters.conversions
        conversions[FIELD_TYPE.BIT] = lambda data: data == b'\x01'
        if self.conn:
            self.thread_id = self.conn.thread_id()
            return self.conn
        if db_name:
            self.conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password,
                                        db=db_name, charset=self.instance.charset or 'utf8mb4',
                                        conv=conversions,
                                        connect_timeout=10)
        else:
            self.conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password,
                                        charset=self.instance.charset or 'utf8mb4',
                                        conv=conversions,
                                        connect_timeout=10)
        self.thread_id = self.conn.thread_id()
        return self.conn

    @property
    def name(self):
        return 'MySQL'

    @property
    def info(self):
        return 'MySQL engine'

    @property
    def auto_backup(self):
        """是否支持备份"""
        return True

    @property
    def seconds_behind_master(self):
        slave_status = self.query(sql='show slave status', close_conn=False, cursorclass=MySQLdb.cursors.DictCursor)
        return slave_status.rows[0].get('Seconds_Behind_Master') if slave_status.rows else None

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

        self.get_connection()
        version = self.conn.get_server_info()
        return tuple([numeric_part(n) for n in version.split('.')[:3]])

    @property
    def schema_object(self):
        """获取实例对象信息"""
        url = build_database_url(host=self.host,
                                 username=self.user,
                                 password=self.password,
                                 port=self.port)
        return schemaobject.SchemaObject(url, charset=self.instance.charset or 'utf8mb4')

    def kill_connection(self, thread_id):
        """终止数据库连接"""
        self.query(sql=f'kill {thread_id}')

    def get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet"""
        sql = "show databases"
        result = self.query(sql=sql)
        db_list = [row[0] for row in result.rows
                   if row[0] not in ('information_schema', 'performance_schema', 'mysql', 'test', 'sys')]
        result.rows = db_list
        return result

    def get_all_tables(self, db_name, **kwargs):
        """获取table 列表, 返回一个ResultSet"""
        sql = "show tables"
        result = self.query(db_name=db_name, sql=sql)
        tb_list = [row[0] for row in result.rows if row[0] not in ['test']]
        result.rows = tb_list
        return result

    def get_group_tables_by_db(self, db_name):
        # escape
        db_name = MySQLdb.escape_string(db_name).decode('utf-8')
        data = {}
        sql = f"""SELECT TABLE_NAME,
                            TABLE_COMMENT
                        FROM
                            information_schema.TABLES
                        WHERE
                            TABLE_SCHEMA='{db_name}';"""
        result = self.query(db_name=db_name, sql=sql)
        for row in result.rows:
            table_name, table_cmt = row[0], row[1]
            if table_name[0] not in data:
                data[table_name[0]] = list()
            data[table_name[0]].append([table_name, table_cmt])
        return data

    def get_table_meta_data(self, db_name, tb_name, **kwargs):
        """数据字典页面使用：获取表格的元信息，返回一个dict{column_list: [], rows: []}"""
        # escape
        db_name = MySQLdb.escape_string(db_name).decode('utf-8')
        tb_name = MySQLdb.escape_string(tb_name).decode('utf-8')
        sql = f"""SELECT
                        TABLE_NAME as table_name,
                        ENGINE as engine,
                        ROW_FORMAT as row_format,
                        TABLE_ROWS as table_rows,
                        AVG_ROW_LENGTH as avg_row_length,
                        round(DATA_LENGTH/1024, 2) as data_length,
                        MAX_DATA_LENGTH as max_data_length,
                        round(INDEX_LENGTH/1024, 2) as index_length,
                        round((DATA_LENGTH + INDEX_LENGTH)/1024, 2) as data_total,
                        DATA_FREE as data_free,
                        AUTO_INCREMENT as auto_increment,
                        TABLE_COLLATION as table_collation,
                        CREATE_TIME as create_time,
                        CHECK_TIME as check_time,
                        UPDATE_TIME as update_time,
                        TABLE_COMMENT as table_comment
                    FROM
                        information_schema.TABLES
                    WHERE
                        TABLE_SCHEMA='{db_name}'
                            AND TABLE_NAME='{tb_name}'"""
        _meta_data = self.query(db_name, sql)
        return {'column_list': _meta_data.column_list, 'rows': _meta_data.rows[0]}

    def get_table_desc_data(self, db_name, tb_name, **kwargs):
        """获取表格字段信息"""
        sql = f"""SELECT 
                        COLUMN_NAME as '列名',
                        COLUMN_TYPE as '列类型',
                        CHARACTER_SET_NAME as '列字符集',
                        IS_NULLABLE as '是否为空',
                        COLUMN_KEY as '索引列',
                        COLUMN_DEFAULT as '默认值',
                        EXTRA as '拓展信息',
                        COLUMN_COMMENT as '列说明'
                    FROM
                        information_schema.COLUMNS
                    WHERE
                        TABLE_SCHEMA = '{db_name}'
                            AND TABLE_NAME = '{tb_name}'
                    ORDER BY ORDINAL_POSITION;"""
        _desc_data = self.query(db_name, sql)
        return {'column_list': _desc_data.column_list, 'rows': _desc_data.rows}

    def get_table_index_data(self, db_name, tb_name, **kwargs):
        """获取表格索引信息"""
        sql = f"""SELECT
                        COLUMN_NAME as '列名',
                        INDEX_NAME as '索引名',
                        NON_UNIQUE as '唯一性',
                        SEQ_IN_INDEX as '列序列',
                        CARDINALITY as '基数',
                        NULLABLE as '是否为空',
                        INDEX_TYPE as '索引类型',
                        COMMENT as '备注'
                    FROM
                        information_schema.STATISTICS
                    WHERE
                        TABLE_SCHEMA = '{db_name}'
                    AND TABLE_NAME = '{tb_name}';"""
        _index_data = self.query(db_name, sql)
        return {'column_list': _index_data.column_list, 'rows': _index_data.rows}

    def get_tables_metas_data(self, db_name, **kwargs):
        """获取数据库所有表格信息，用作数据字典导出接口"""
        sql_tbs = f"SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='{db_name}';"
        tbs = self.query(sql=sql_tbs, cursorclass=MySQLdb.cursors.DictCursor, close_conn=False).rows
        table_metas = []
        for tb in tbs:
            _meta = dict()
            engine_keys = [{"key": "COLUMN_NAME", "value": "字段名"}, {"key": "COLUMN_TYPE", "value": "数据类型"},
                           {"key": "COLUMN_DEFAULT", "value": "默认值"}, {"key": "IS_NULLABLE", "value": "允许非空"},
                           {"key": "EXTRA", "value": "自动递增"}, {"key": "COLUMN_KEY", "value": "是否主键"},
                           {"key": "COLUMN_COMMENT", "value": "备注"}]
            _meta["ENGINE_KEYS"] = engine_keys
            _meta['TABLE_INFO'] = tb
            sql_cols = f"""SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA='{tb['TABLE_SCHEMA']}' AND TABLE_NAME='{tb['TABLE_NAME']}';"""
            _meta['COLUMNS'] = self.query(sql=sql_cols, cursorclass=MySQLdb.cursors.DictCursor, close_conn=False).rows
            table_metas.append(_meta)
        return table_metas

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段, 返回一个ResultSet"""
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
        result = self.query(db_name=db_name, sql=sql)
        column_list = [row[0] for row in result.rows]
        result.rows = column_list
        return result

    def describe_table(self, db_name, tb_name, **kwargs):
        """return ResultSet 类似查询"""
        sql = f"show create table `{tb_name}`;"
        result = self.query(db_name=db_name, sql=sql)
        return result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True, **kwargs):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        max_execution_time = kwargs.get('max_execution_time', 0)
        cursorclass = kwargs.get('cursorclass') or MySQLdb.cursors.Cursor
        try:
            conn = self.get_connection(db_name=db_name)
            conn.autocommit(True)
            cursor = conn.cursor(cursorclass)
            try:
                cursor.execute(f"set session max_execution_time={max_execution_time};")
            except MySQLdb.OperationalError:
                pass
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
            logger.warning(f"MySQL语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}")
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
        # select语句先使用Explain判断语法是否正确
        if re.match(r"^select", sql, re.I):
            explain_result = self.query(db_name=db_name, sql=f"explain {sql}")
            if explain_result.error:
                result['bad_query'] = True
                result['msg'] = explain_result.error
        # 不应该查看mysql.user表
        if re.match('.*(\\s)+(mysql|`mysql`)(\\s)*\\.(\\s)*(user|`user`)((\\s)*|;).*', sql.lower().replace('\n', '')) or \
                (db_name == "mysql" and re.match('.*(\\s)+(user|`user`)((\\s)*|;).*', sql.lower().replace('\n', ''))):
            result['bad_query'] = True
            result['msg'] = '您无权查看该表'

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
        # 进行Inception检查，获取检测结果
        try:
            check_result = self.inc_engine.execute_check(instance=self.instance, db_name=db_name, sql=sql)
        except Exception as e:
            logger.debug(f"{self.inc_engine.name}检测语句报错：错误信息{traceback.format_exc()}")
            raise RuntimeError(f"{self.inc_engine.name}检测语句报错，请注意检查系统配置中{self.inc_engine.name}配置，错误信息：\n{e}")

        # 判断Inception检测结果
        if check_result.error:
            logger.debug(f"{self.inc_engine.name}检测语句报错：错误信息{check_result.error}")
            raise RuntimeError(f"{self.inc_engine.name}检测语句报错，错误信息：\n{check_result.error}")

        # 禁用/高危语句检查
        critical_ddl_regex = self.config.get('critical_ddl_regex', '')
        p = re.compile(critical_ddl_regex)
        for row in check_result.rows:
            statement = row.sql
            # 去除注释
            statement = remove_comments(statement, db_type='mysql')
            # 禁用语句
            if re.match(r"^select", statement.lower()):
                check_result.error_count += 1
                row.stagestatus = '驳回不支持语句'
                row.errlevel = 2
                row.errormessage = '仅支持DML和DDL语句，查询语句请使用SQL查询功能！'
            # 高危语句
            elif critical_ddl_regex and p.match(statement.strip().lower()):
                check_result.error_count += 1
                row.stagestatus = '驳回高危SQL'
                row.errlevel = 2
                row.errormessage = '禁止提交匹配' + critical_ddl_regex + '条件的语句！'
        return check_result

    def execute_workflow(self, workflow):
        """执行上线单，返回Review set"""
        # 判断实例是否只读
        read_only = self.query(sql='SELECT @@global.read_only;').rows[0][0]
        if read_only in (1, 'ON'):
            result = ReviewSet(
                full_sql=workflow.sqlworkflowcontent.sql_content,
                rows=[ReviewResult(id=1, errlevel=2,
                                   stagestatus='Execute Failed',
                                   errormessage='实例read_only=1，禁止执行变更语句!',
                                   sql=workflow.sqlworkflowcontent.sql_content)])
            result.error = '实例read_only=1，禁止执行变更语句!',
            return result
        # TODO 原生执行
        # if workflow.is_manual == 1:
        #     return self.execute(db_name=workflow.db_name, sql=workflow.sqlworkflowcontent.sql_content)
        # inception执行
        return self.inc_engine.execute(workflow)

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
            logger.warning(f"MySQL语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}")
            result.error = str(e)
        if close_conn:
            self.close()
        return result

    def get_rollback(self, workflow):
        """通过inception获取回滚语句列表"""
        inception_engine = GoInceptionEngine()
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

    def osc_control(self, **kwargs):
        """控制osc执行，获取进度、终止、暂停、恢复等
            get、kill、pause、resume
        """
        return self.inc_engine.osc_control(**kwargs)

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
