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

logger = logging.getLogger("default")

# https://github.com/mysql/mysql-connector-python/blob/master/lib/mysql/connector/constants.py#L168
column_types_map = {
    0: "DECIMAL",
    1: "TINY",
    2: "SHORT",
    3: "LONG",
    4: "FLOAT",
    5: "DOUBLE",
    6: "NULL",
    7: "TIMESTAMP",
    8: "LONGLONG",
    9: "INT24",
    10: "DATE",
    11: "TIME",
    12: "DATETIME",
    13: "YEAR",
    14: "NEWDATE",
    15: "VARCHAR",
    16: "BIT",
    245: "JSON",
    246: "NEWDECIMAL",
    247: "ENUM",
    248: "SET",
    249: "TINY_BLOB",
    250: "MEDIUM_BLOB",
    251: "LONG_BLOB",
    252: "BLOB",
    253: "VAR_STRING",
    254: "STRING",
    255: "GEOMETRY",
}


class MysqlEngine(EngineBase):
    test_query = "SELECT 1"

    def __init__(self, instance=None):
        super().__init__(instance=instance)
        self.config = SysConfig()
        self.inc_engine = GoInceptionEngine()

    def get_connection(self, db_name=None):
        # https://stackoverflow.com/questions/19256155/python-mysqldb-returning-x01-for-bit-values
        conversions = MySQLdb.converters.conversions
        conversions[FIELD_TYPE.BIT] = lambda data: data == b"\x01"
        if self.conn:
            self.thread_id = self.conn.thread_id()
            return self.conn
        if db_name:
            self.conn = MySQLdb.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                passwd=self.password,
                db=db_name,
                charset=self.instance.charset or "utf8mb4",
                conv=conversions,
                connect_timeout=10,
            )
        else:
            self.conn = MySQLdb.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                passwd=self.password,
                charset=self.instance.charset or "utf8mb4",
                conv=conversions,
                connect_timeout=10,
            )
        self.thread_id = self.conn.thread_id()
        return self.conn

    @property
    def name(self):
        return "MySQL"

    @property
    def info(self):
        return "MySQL engine"

    @property
    def auto_backup(self):
        """是否支持备份"""
        return True

    @property
    def seconds_behind_master(self):
        slave_status = self.query(
            sql="show slave status",
            close_conn=False,
            cursorclass=MySQLdb.cursors.DictCursor,
        )
        return (
            slave_status.rows[0].get("Seconds_Behind_Master")
            if slave_status.rows
            else None
        )

    @property
    def server_version(self):
        def numeric_part(s):
            """Returns the leading numeric part of a string."""
            re_numeric_part = re.compile(r"^(\d+)")
            m = re_numeric_part.match(s)
            if m:
                return int(m.group(1))
            return None

        self.get_connection()
        version = self.conn.get_server_info()
        return tuple([numeric_part(n) for n in version.split(".")[:3]])

    @property
    def schema_object(self):
        """获取实例对象信息"""
        url = build_database_url(
            host=self.host, username=self.user, password=self.password, port=self.port
        )
        return schemaobject.SchemaObject(
            url, charset=self.instance.charset or "utf8mb4"
        )

    def kill_connection(self, thread_id):
        """终止数据库连接"""
        self.query(sql=f"kill {thread_id}")

    def get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet"""
        sql = "show databases"
        result = self.query(sql=sql)
        db_list = [
            row[0]
            for row in result.rows
            if row[0]
            not in ("information_schema", "performance_schema", "mysql", "test", "sys")
        ]
        result.rows = db_list
        return result

    def get_all_tables(self, db_name, **kwargs):
        """获取table 列表, 返回一个ResultSet"""
        sql = "show tables"
        result = self.query(db_name=db_name, sql=sql)
        tb_list = [row[0] for row in result.rows if row[0] not in ["test"]]
        result.rows = tb_list
        return result

    def get_group_tables_by_db(self, db_name):
        # escape
        db_name = MySQLdb.escape_string(db_name).decode("utf-8")
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
        db_name = MySQLdb.escape_string(db_name).decode("utf-8")
        tb_name = MySQLdb.escape_string(tb_name).decode("utf-8")
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
        return {"column_list": _meta_data.column_list, "rows": _meta_data.rows[0]}

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
        return {"column_list": _desc_data.column_list, "rows": _desc_data.rows}

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
        return {"column_list": _index_data.column_list, "rows": _index_data.rows}

    def get_tables_metas_data(self, db_name, **kwargs):
        """获取数据库所有表格信息，用作数据字典导出接口"""
        sql_tbs = (
            f"SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='{db_name}';"
        )
        tbs = self.query(
            sql=sql_tbs, cursorclass=MySQLdb.cursors.DictCursor, close_conn=False
        ).rows
        table_metas = []
        for tb in tbs:
            _meta = dict()
            engine_keys = [
                {"key": "COLUMN_NAME", "value": "字段名"},
                {"key": "COLUMN_TYPE", "value": "数据类型"},
                {"key": "COLUMN_DEFAULT", "value": "默认值"},
                {"key": "IS_NULLABLE", "value": "允许非空"},
                {"key": "EXTRA", "value": "自动递增"},
                {"key": "COLUMN_KEY", "value": "是否主键"},
                {"key": "COLUMN_COMMENT", "value": "备注"},
            ]
            _meta["ENGINE_KEYS"] = engine_keys
            _meta["TABLE_INFO"] = tb
            sql_cols = f"""SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA='{tb['TABLE_SCHEMA']}' AND TABLE_NAME='{tb['TABLE_NAME']}';"""
            _meta["COLUMNS"] = self.query(
                sql=sql_cols, cursorclass=MySQLdb.cursors.DictCursor, close_conn=False
            ).rows
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

    @staticmethod
    def result_set_binary_as_hex(result_set):
        """处理ResultSet，将binary处理成hex"""
        new_rows, hex_column_index = [], []
        for idx, _type in enumerate(result_set.column_type):
            if _type in ["TINY_BLOB", "MEDIUM_BLOB", "LONG_BLOB", "BLOB"]:
                hex_column_index.append(idx)
        if hex_column_index:
            for row in result_set.rows:
                row = list(row)
                for index in hex_column_index:
                    row[index] = row[index].hex() if row[index] else row[index]
                new_rows.append(row)
        result_set.rows = tuple(new_rows)
        return result_set

    def query(self, db_name=None, sql="", limit_num=0, close_conn=True, **kwargs):
        """返回 ResultSet"""
        result_set = ResultSet(full_sql=sql)
        max_execution_time = kwargs.get("max_execution_time", 0)
        cursorclass = kwargs.get("cursorclass") or MySQLdb.cursors.Cursor
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
            result_set.column_type = (
                [column_types_map.get(i[1], "") for i in fields] if fields else []
            )
            result_set.rows = rows
            result_set.affected_rows = effect_row
            if kwargs.get("binary_as_hex"):
                result_set = self.result_set_binary_as_hex(result_set)
        except Exception as e:
            logger.warning(f"MySQL语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}")
            result_set.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result_set

    def query_check(self, db_name=None, sql=""):
        # 查询语句的检查、注释去除、切分
        result = {"msg": "", "bad_query": False, "filtered_sql": sql, "has_star": False}
        # 删除注释语句，进行语法判断，执行第一条有效sql
        try:
            sql = sqlparse.format(sql, strip_comments=True)
            sql = sqlparse.split(sql)[0]
            result["filtered_sql"] = sql.strip()
        except IndexError:
            result["bad_query"] = True
            result["msg"] = "没有有效的SQL语句"
        if re.match(r"^select|^show|^explain", sql, re.I) is None:
            result["bad_query"] = True
            result["msg"] = "不支持的查询语法类型!"
        if "*" in sql:
            result["has_star"] = True
            result["msg"] = "SQL语句中含有 * "
        # select语句先使用Explain判断语法是否正确
        if re.match(r"^select", sql, re.I):
            explain_result = self.query(db_name=db_name, sql=f"explain {sql}")
            if explain_result.error:
                result["bad_query"] = True
                result["msg"] = explain_result.error
        # 不应该查看mysql.user表
        if re.match(
            ".*(\\s)+(mysql|`mysql`)(\\s)*\\.(\\s)*(user|`user`)((\\s)*|;).*",
            sql.lower().replace("\n", ""),
        ) or (
            db_name == "mysql"
            and re.match(
                ".*(\\s)+(user|`user`)((\\s)*|;).*", sql.lower().replace("\n", "")
            )
        ):
            result["bad_query"] = True
            result["msg"] = "您无权查看该表"

        return result

    def filter_sql(self, sql="", limit_num=0):
        # 对查询sql增加limit限制,limit n 或 limit n,n 或 limit n offset n统一改写成limit n
        sql = sql.rstrip(";").strip()
        if re.match(r"^select", sql, re.I):
            # LIMIT N
            limit_n = re.compile(r"limit\s+(\d+)\s*$", re.I)
            # LIMIT M OFFSET N
            limit_offset = re.compile(r"limit\s+(\d+)\s+offset\s+(\d+)\s*$", re.I)
            # LIMIT M,N
            offset_comma_limit = re.compile(r"limit\s+(\d+)\s*,\s*(\d+)\s*$", re.I)
            if limit_n.search(sql):
                sql_limit = limit_n.search(sql).group(1)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = limit_n.sub(f"limit {limit_num};", sql)
            elif limit_offset.search(sql):
                sql_limit = limit_offset.search(sql).group(1)
                sql_offset = limit_offset.search(sql).group(2)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = limit_offset.sub(f"limit {limit_num} offset {sql_offset};", sql)
            elif offset_comma_limit.search(sql):
                sql_offset = offset_comma_limit.search(sql).group(1)
                sql_limit = offset_comma_limit.search(sql).group(2)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = offset_comma_limit.sub(f"limit {sql_offset},{limit_num};", sql)
            else:
                sql = f"{sql} limit {limit_num};"
        else:
            sql = f"{sql};"
        return sql

    def query_masking(self, db_name=None, sql="", resultset=None):
        """传入 sql语句, db名, 结果集,
        返回一个脱敏后的结果集"""
        # 仅对select语句脱敏
        if re.match(r"^select", sql, re.I):
            mask_result = data_masking(self.instance, db_name, sql, resultset)
        else:
            mask_result = resultset
        return mask_result

    def execute_check(self, db_name=None, sql=""):
        """上线单执行前的检查, 返回Review set"""
        # 进行Inception检查，获取检测结果
        try:
            check_result = self.inc_engine.execute_check(
                instance=self.instance, db_name=db_name, sql=sql
            )
        except Exception as e:
            logger.debug(f"{self.inc_engine.name}检测语句报错：错误信息{traceback.format_exc()}")
            raise RuntimeError(
                f"{self.inc_engine.name}检测语句报错，请注意检查系统配置中{self.inc_engine.name}配置，错误信息：\n{e}"
            )

        # 判断Inception检测结果
        if check_result.error:
            logger.debug(f"{self.inc_engine.name}检测语句报错：错误信息{check_result.error}")
            raise RuntimeError(
                f"{self.inc_engine.name}检测语句报错，错误信息：\n{check_result.error}"
            )

        # 禁用/高危语句检查
        critical_ddl_regex = self.config.get("critical_ddl_regex", "")
        p = re.compile(critical_ddl_regex)
        for row in check_result.rows:
            statement = row.sql
            # 去除注释
            statement = remove_comments(statement, db_type="mysql")
            # 禁用语句
            if re.match(r"^select", statement.lower()):
                check_result.error_count += 1
                row.stagestatus = "驳回不支持语句"
                row.errlevel = 2
                row.errormessage = "仅支持DML和DDL语句，查询语句请使用SQL查询功能！"
            # 高危语句
            elif critical_ddl_regex and p.match(statement.strip().lower()):
                check_result.error_count += 1
                row.stagestatus = "驳回高危SQL"
                row.errlevel = 2
                row.errormessage = "禁止提交匹配" + critical_ddl_regex + "条件的语句！"
        return check_result

    def execute_workflow(self, workflow):
        """执行上线单，返回Review set"""
        # 判断实例是否只读
        read_only = self.query(sql="SELECT @@global.read_only;").rows[0][0]
        if read_only in (1, "ON"):
            result = ReviewSet(
                full_sql=workflow.sqlworkflowcontent.sql_content,
                rows=[
                    ReviewResult(
                        id=1,
                        errlevel=2,
                        stagestatus="Execute Failed",
                        errormessage="实例read_only=1，禁止执行变更语句!",
                        sql=workflow.sqlworkflowcontent.sql_content,
                    )
                ],
            )
            result.error = ("实例read_only=1，禁止执行变更语句!",)
            return result
        # TODO 原生执行
        # if workflow.is_manual == 1:
        #     return self.execute(db_name=workflow.db_name, sql=workflow.sqlworkflowcontent.sql_content)
        # inception执行
        return self.inc_engine.execute(workflow)

    def execute(self, db_name=None, sql="", close_conn=True):
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
            variables = (
                "','".join(variables)
                if isinstance(variables, list)
                else "','".join(list(variables))
            )
            db = (
                "performance_schema"
                if self.server_version > (5, 7)
                else "information_schema"
            )
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

    def processlist(self, command_type):
        """获取连接信息"""
        base_sql = "select id, user, host, db, command, time, state, ifnull(info,'') as info from information_schema.processlist"
        # escape
        command_type = MySQLdb.escape_string(command_type).decode("utf-8")
        if not command_type:
            command_type = "Query"
        if command_type == "All":
            sql = base_sql + ";"
        elif command_type == "Not Sleep":
            sql = "{} where command<>'Sleep';".format(base_sql)
        else:
            sql = "{} where command= '{}';".format(base_sql, command_type)

        return self.query("information_schema", sql)

    def get_kill_command(self, thread_ids):
        """由传入的线程列表生成kill命令"""
        # 校验传参
        if [i for i in thread_ids if not isinstance(i, int)]:
            return None
        sql = "select concat('kill ', id, ';') from information_schema.processlist where id in ({});".format(
            ",".join(str(tid) for tid in thread_ids)
        )
        all_kill_sql = self.query("information_schema", sql)
        kill_sql = ""
        for row in all_kill_sql.rows:
            kill_sql = kill_sql + row[0]

        return kill_sql

    def kill(self, thread_ids):
        """kill线程"""
        # 校验传参
        if [i for i in thread_ids if not isinstance(i, int)]:
            return ResultSet(full_sql="")
        sql = "select concat('kill ', id, ';') from information_schema.processlist where id in ({});".format(
            ",".join(str(tid) for tid in thread_ids)
        )
        all_kill_sql = self.query("information_schema", sql)
        kill_sql = ""
        for row in all_kill_sql.rows:
            kill_sql = kill_sql + row[0]
        return self.execute("information_schema", kill_sql)

    def tablesapce(self, offset=0, row_count=14):
        """获取表空间信息"""
        sql = """
        SELECT
          table_schema AS table_schema,
          table_name AS table_name,
          engine AS engine,
          TRUNCATE((data_length+index_length+data_free)/1024/1024,2) AS total_size,
          table_rows AS table_rows,
          TRUNCATE(data_length/1024/1024,2) AS data_size,
          TRUNCATE(index_length/1024/1024,2) AS index_size,
          TRUNCATE(data_free/1024/1024,2) AS data_free,
          TRUNCATE(data_free/(data_length+index_length+data_free)*100,2) AS pct_free
        FROM information_schema.tables 
        WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'test', 'sys')
          ORDER BY total_size DESC 
        LIMIT {},{};""".format(
            offset, row_count
        )
        return self.query("information_schema", sql)

    def tablesapce_num(self):
        """获取表空间数量"""
        sql = """
        SELECT count(*)
        FROM information_schema.tables 
        WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'test', 'sys')"""
        return self.query("information_schema", sql)

    def trxandlocks(self):
        """获取锁等待信息"""
        server_version = self.server_version
        if server_version < (8, 0, 1):
            sql = """
                SELECT
                rtrx.`trx_state`                                                        AS "等待的状态",
                rtrx.`trx_started`                                                      AS "等待事务开始时间",
                rtrx.`trx_wait_started`                                                 AS "等待事务等待开始时间",
                lw.`requesting_trx_id`                                                  AS "等待事务ID",
                rtrx.trx_mysql_thread_id                                                AS "等待事务线程ID",
                rtrx.`trx_query`                                                        AS "等待事务的sql",
                CONCAT(rl.`lock_mode`, '-', rl.`lock_table`, '(', rl.`lock_index`, ')') AS "等待的表信息",
                rl.`lock_id`                                                            AS "等待的锁id",
                lw.`blocking_trx_id`                                                    AS "运行的事务id",
                trx.trx_mysql_thread_id                                                 AS "运行的事务线程id",
                CONCAT(l.`lock_mode`, '-', l.`lock_table`, '(', l.`lock_index`, ')')    AS "运行的表信息",
                l.lock_id                                                               AS "运行的锁id",
                trx.`trx_state`                                                         AS "运行事务的状态",
                trx.`trx_started`                                                       AS "运行事务的时间",
                trx.`trx_wait_started`                                                  AS "运行事务的等待开始时间",
                trx.`trx_query`                                                         AS "运行事务的sql"
                FROM information_schema.`INNODB_LOCKS` rl
                , information_schema.`INNODB_LOCKS` l
                , information_schema.`INNODB_LOCK_WAITS` lw
                , information_schema.`INNODB_TRX` rtrx
                , information_schema.`INNODB_TRX` trx
                WHERE rl.`lock_id` = lw.`requested_lock_id`
                    AND l.`lock_id` = lw.`blocking_lock_id`
                    AND lw.requesting_trx_id = rtrx.trx_id
                    AND lw.blocking_trx_id = trx.trx_id;"""

        else:
            sql = """
                SELECT
                rtrx.`trx_state`                                                           AS "等待的状态",
                rtrx.`trx_started`                                                         AS "等待事务开始时间",
                rtrx.`trx_wait_started`                                                    AS "等待事务等待开始时间",
                lw.`REQUESTING_ENGINE_TRANSACTION_ID`                                      AS "等待事务ID",
                rtrx.trx_mysql_thread_id                                                   AS "等待事务线程ID",
                rtrx.`trx_query`                                                           AS "等待事务的sql",
                CONCAT(rl.`lock_mode`, '-', rl.`OBJECT_SCHEMA`, '(', rl.`INDEX_NAME`, ')') AS "等待的表信息",
                rl.`ENGINE_LOCK_ID`                                                        AS "等待的锁id",
                lw.`BLOCKING_ENGINE_TRANSACTION_ID`                                        AS "运行的事务id",
                trx.trx_mysql_thread_id                                                    AS "运行的事务线程id",
                CONCAT(l.`lock_mode`, '-', l.`OBJECT_SCHEMA`, '(', l.`INDEX_NAME`, ')')    AS "运行的表信息",
                l.ENGINE_LOCK_ID                                                           AS "运行的锁id",
                trx.`trx_state`                                                            AS "运行事务的状态",
                trx.`trx_started`                                                          AS "运行事务的时间",
                trx.`trx_wait_started`                                                     AS "运行事务的等待开始时间",
                trx.`trx_query`                                                            AS "运行事务的sql"
                FROM performance_schema.`data_locks` rl
                , performance_schema.`data_locks` l
                , performance_schema.`data_lock_waits` lw
                , information_schema.`INNODB_TRX` rtrx
                , information_schema.`INNODB_TRX` trx
                WHERE rl.`ENGINE_LOCK_ID` = lw.`REQUESTING_ENGINE_LOCK_ID`
                    AND l.`ENGINE_LOCK_ID` = lw.`BLOCKING_ENGINE_LOCK_ID`
                    AND lw.REQUESTING_ENGINE_TRANSACTION_ID = rtrx.trx_id
                    AND lw.BLOCKING_ENGINE_TRANSACTION_ID = trx.trx_id;"""

        return self.query("information_schema", sql)

    def get_long_transaction(self, thread_time=3):
        """获取长事务"""
        sql = """select trx.trx_started,
        trx.trx_state,
        trx.trx_operation_state,
        trx.trx_mysql_thread_id,
        trx.trx_tables_locked,
        trx.trx_rows_locked,
        trx.trx_rows_modified,
        trx.trx_is_read_only,
        trx.trx_isolation_level,
        p.user,
        p.host,
        p.db,
        TO_SECONDS(NOW()) - TO_SECONDS(trx.trx_started) trx_idle_time,
        p.time thread_time,
        IFNULL((SELECT
        GROUP_CONCAT(t1.sql_text SEPARATOR ';
        ')
        FROM performance_schema.events_statements_history t1
        INNER JOIN performance_schema.threads t2
            ON t1.thread_id = t2.thread_id
        WHERE t2.PROCESSLIST_ID = p.id), '') info
        FROM information_schema.INNODB_TRX trx
        INNER JOIN information_schema.PROCESSLIST p
        ON trx.trx_mysql_thread_id = p.id
        WHERE trx.trx_state = 'RUNNING'
        AND p.COMMAND = 'Sleep'
        AND p.time > {}
        ORDER BY trx.trx_started ASC;""".format(
            thread_time
        )

        return self.query("information_schema", sql)

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
