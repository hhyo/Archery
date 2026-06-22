# -*- coding: UTF-8 -*-
import logging
import traceback
import MySQLdb
import MySQLdb.cursors
import MySQLdb.converters
import pymysql
import re
import regex as safe_regex
from enum import Enum

import schemaobject
import sqlparse
from MySQLdb.constants import FIELD_TYPE
from schemaobject.connection import build_database_url

from sql.engines.goinception import GoInceptionEngine
from sql.utils.extract_tables import extract_tables
from sql.utils.sql_utils import get_syntax_type, remove_comments
from . import EngineBase
from .models import ResultSet, ReviewResult, ReviewSet
from sql.utils.data_masking import data_masking
from common.config import SysConfig

logger = logging.getLogger("default")

CRITICAL_DDL_REGEX_MAX_LENGTH = 2048
CRITICAL_DDL_REGEX_TIMEOUT = 0.1

MYSQL_PRIVILEGE_TABLES = {
    "user",
    "db",
    "tables_priv",
    "columns_priv",
    "procs_priv",
    "proxies_priv",
    "global_grants",
    "default_roles",
    "role_edges",
    "password_history",
}
INFORMATION_SCHEMA_PRIVILEGE_TABLES = {
    "user_privileges",
    "schema_privileges",
    "table_privileges",
    "column_privileges",
    "applicable_roles",
    "enabled_roles",
    "administrable_role_authorizations",
}

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


class MysqlForkType(Enum):
    """定义几个支持的版本类型"""

    MYSQL = "mysql"
    MARIADB = "mariadb"
    PERCONA = "percona"


class MysqlEngine(EngineBase):
    name = "MySQL"
    info = "MySQL engine"
    test_query = "SELECT 1"
    _server_version = None
    _server_fork_type = None
    _server_info = None

    GLOBAL_PRIVILEGES = {
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "FILE",
        "CREATE",
        "ALTER",
        "INDEX",
        "DROP",
        "CREATE TEMPORARY TABLES",
        "SHOW VIEW",
        "CREATE ROUTINE",
        "ALTER ROUTINE",
        "EXECUTE",
        "CREATE VIEW",
        "EVENT",
        "TRIGGER",
        "GRANT",
        "SUPER",
        "PROCESS",
        "RELOAD",
        "SHUTDOWN",
        "SHOW DATABASES",
        "LOCK TABLES",
        "REFERENCES",
        "REPLICATION CLIENT",
        "REPLICATION SLAVE",
        "CREATE USER",
    }
    DB_PRIVILEGES = {
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "CREATE",
        "ALTER",
        "INDEX",
        "DROP",
        "CREATE TEMPORARY TABLES",
        "SHOW VIEW",
        "CREATE ROUTINE",
        "ALTER ROUTINE",
        "EXECUTE",
        "CREATE VIEW",
        "EVENT",
        "TRIGGER",
        "GRANT",
        "LOCK TABLES",
        "REFERENCES",
    }
    TABLE_PRIVILEGES = {
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "CREATE",
        "ALTER",
        "INDEX",
        "DROP",
        "SHOW VIEW",
        "CREATE VIEW",
        "TRIGGER",
        "GRANT",
        "REFERENCES",
    }
    COLUMN_PRIVILEGES = {"SELECT", "INSERT", "UPDATE", "REFERENCES"}
    VARIABLE_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")

    def __init__(self, instance=None):
        super().__init__(instance=instance)
        self.config = SysConfig()
        self.inc_engine = GoInceptionEngine()

    @staticmethod
    def _error_result(message, full_sql=""):
        result = ResultSet(full_sql=full_sql)
        result.error = message
        return result

    @staticmethod
    def _quote_identifier(identifier):
        if identifier is None:
            raise ValueError("标识符不能为空")
        identifier = str(identifier)
        if identifier == "" or "\x00" in identifier:
            raise ValueError("标识符不合法")
        return f"`{identifier.replace('`', '``')}`"

    @staticmethod
    def _quote_literal(value):
        if value is None:
            raise ValueError("参数值不能为空")
        value = str(value)
        if "\x00" in value:
            raise ValueError("参数值不合法")
        return f"'{pymysql.escape_string(value)}'"

    @staticmethod
    def _quote_account_part(value):
        if value is None:
            raise ValueError("账号信息不能为空")
        value = str(value)
        if "\x00" in value:
            raise ValueError("账号信息不合法")
        return f"`{value.replace('`', '``')}`"

    @classmethod
    def _format_user_host(cls, user, host):
        return f"{cls._quote_account_part(user)}@{cls._quote_account_part(host)}"

    @classmethod
    def _parse_account_part(cls, account, start):
        length = len(account)
        while start < length and account[start].isspace():
            start += 1
        if start >= length:
            raise ValueError("账号格式不合法")

        quote = account[start] if account[start] in ("`", "'", '"') else None
        if not quote:
            end = start
            while end < length and account[end] != "@":
                end += 1
            value = account[start:end].strip()
            if not value:
                raise ValueError("账号格式不合法")
            return value, end

        start += 1
        chars = []
        while start < length:
            ch = account[start]
            if ch == "\\" and quote in ("'", '"') and start + 1 < length:
                chars.append(account[start + 1])
                start += 2
                continue
            if ch == quote:
                if quote == "`" and start + 1 < length and account[start + 1] == "`":
                    chars.append("`")
                    start += 2
                    continue
                if (
                    quote in ("'", '"')
                    and start + 1 < length
                    and account[start + 1] == quote
                ):
                    chars.append(quote)
                    start += 2
                    continue
                return "".join(chars), start + 1
            chars.append(ch)
            start += 1
        raise ValueError("账号格式不合法")

    @classmethod
    def _parse_user_host(cls, user_host):
        if user_host is None:
            raise ValueError("账号格式不合法")
        user_host = str(user_host).strip()
        user, pos = cls._parse_account_part(user_host, 0)
        while pos < len(user_host) and user_host[pos].isspace():
            pos += 1
        if pos >= len(user_host) or user_host[pos] != "@":
            raise ValueError("账号格式不合法")
        host, pos = cls._parse_account_part(user_host, pos + 1)
        if user_host[pos:].strip():
            raise ValueError("账号格式不合法")
        return user, host

    @classmethod
    def _normalize_user_host(cls, user_host):
        user, host = cls._parse_user_host(user_host)
        return cls._format_user_host(user, host)

    @staticmethod
    def _coerce_int(value, name, minimum=None):
        if isinstance(value, bool):
            raise ValueError(f"{name}不合法")
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name}不合法")
        if minimum is not None and value < minimum:
            raise ValueError(f"{name}不合法")
        return value

    @classmethod
    def _validate_thread_ids(cls, thread_ids):
        if not isinstance(thread_ids, (list, tuple)):
            raise ValueError("线程ID不合法")
        safe_ids = []
        for thread_id in thread_ids:
            if isinstance(thread_id, bool) or not isinstance(thread_id, int):
                raise ValueError("线程ID不合法")
            safe_ids.append(thread_id)
        return safe_ids

    @classmethod
    def _normalize_privileges(cls, privs, allowed_privs):
        normalized = []
        for priv in privs or []:
            priv = str(priv).upper()
            if priv not in allowed_privs:
                raise ValueError("权限项不合法")
            normalized.append("GRANT OPTION" if priv == "GRANT" else priv)
        if not normalized:
            raise ValueError("权限项不能为空")
        return normalized

    @staticmethod
    def _as_list(value):
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]

    @staticmethod
    def _compile_safe_regex(pattern):
        if not pattern:
            return None
        if len(pattern) > CRITICAL_DDL_REGEX_MAX_LENGTH:
            raise ValueError("critical_ddl_regex长度超过2048，已拒绝执行")
        try:
            return safe_regex.compile(pattern)
        except safe_regex.error as e:
            raise ValueError(f"critical_ddl_regex配置不合法：{e}")

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

    def escape_string(self, value: str) -> str:
        """字符串参数转义"""
        return pymysql.escape_string(value)

    @property
    def auto_backup(self):
        """是否支持备份"""
        return True

    @property
    def seconds_behind_master(self):
        server_version = self.server_version
        ##非maria分支且版本号大于8.4，就使用show replica status获取主从延迟
        if self.server_fork_type != MysqlForkType.MARIADB and server_version >= (8, 4):
            status_sql = "show replica status"
        else:
            status_sql = "show slave status"
        slave_status = self.query(
            sql=status_sql,
            close_conn=False,
            cursorclass=MySQLdb.cursors.DictCursor,
        )
        return (
            slave_status.rows[0].get("Seconds_Behind_Master")
            or slave_status.rows[0].get("Seconds_Behind_Source")
            if slave_status.rows
            else None
        )

    @property
    def server_version(self):
        if self._server_version:
            return self._server_version

        def numeric_part(s):
            """Returns the leading numeric part of a string."""
            re_numeric_part = re.compile(r"^(\d+)")
            m = re_numeric_part.match(s)
            if m:
                return int(m.group(1))
            return None

        self.get_connection()
        version = self.conn.get_server_info()
        self._server_version = tuple([numeric_part(n) for n in version.split(".")[:3]])
        return self._server_version

    @property
    def server_info(self):
        if self._server_info:
            return self._server_info
        conn = self.get_connection()
        self._server_info = conn.get_server_info()
        return self._server_info

    @property
    def server_fork_type(self):
        """确认 server 具体是哪种 mysql, mysql, mariadb, 还是 percona"""
        server_info = self.server_info
        for i in list(MysqlForkType):
            if i.value in server_info.lower():
                return i
        return MysqlForkType.MYSQL

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
        try:
            thread_id = self._coerce_int(thread_id, "线程ID", minimum=0)
        except ValueError as e:
            return self._error_result(str(e))
        return self.query(sql="kill %s", parameters=(thread_id,))

    # 禁止查询的数据库
    forbidden_databases = [
        "information_schema",
        "performance_schema",
        "mysql",
        "test",
        "sys",
    ]

    def get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet"""
        sql = "show databases"
        result = self.query(sql=sql)
        db_list = [
            row[0] for row in result.rows if row[0] not in self.forbidden_databases
        ]
        result.rows = db_list
        return result

    forbidden_tables = ["test"]

    def get_all_tables(self, db_name, **kwargs):
        """获取table 列表, 返回一个ResultSet"""
        sql = "show tables"
        result = self.query(db_name=db_name, sql=sql)
        tb_list = [row[0] for row in result.rows if row[0] not in self.forbidden_tables]
        result.rows = tb_list
        return result

    def get_group_tables_by_db(self, db_name):
        data = {}
        sql = f"""SELECT TABLE_NAME,
                            TABLE_COMMENT
                        FROM
                            information_schema.TABLES
                        WHERE
                            TABLE_SCHEMA=%(db_name)s;"""
        result = self.query(db_name=db_name, sql=sql, parameters={"db_name": db_name})
        for row in result.rows:
            table_name, table_cmt = row[0], row[1]
            if table_name[0] not in data:
                data[table_name[0]] = list()
            data[table_name[0]].append([table_name, table_cmt])
        return data

    def get_table_meta_data(self, db_name, tb_name, **kwargs):
        """数据字典页面使用：获取表格的元信息，返回一个dict{column_list: [], rows: []}"""
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
                        TABLE_SCHEMA=%(db_name)s
                            AND TABLE_NAME=%(tb_name)s"""
        _meta_data = self.query(
            db_name, sql, parameters={"db_name": db_name, "tb_name": tb_name}
        )
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
                        TABLE_SCHEMA = %(db_name)s
                            AND TABLE_NAME = %(tb_name)s
                    ORDER BY ORDINAL_POSITION;"""
        _desc_data = self.query(
            db_name, sql, parameters={"db_name": db_name, "tb_name": tb_name}
        )
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
                        TABLE_SCHEMA = %(db_name)s
                    AND TABLE_NAME = %(tb_name)s;"""
        _index_data = self.query(
            db_name, sql, parameters={"db_name": db_name, "tb_name": tb_name}
        )
        return {"column_list": _index_data.column_list, "rows": _index_data.rows}

    def get_views_list(self, db_name, **kwargs):
        """获取视图列表，按首字符分组"""
        data = {}
        sql = """SELECT TABLE_NAME, VIEW_DEFINITION
                    FROM information_schema.VIEWS
                    WHERE TABLE_SCHEMA=%(db_name)s;"""
        result = self.query(db_name=db_name, sql=sql, parameters={"db_name": db_name})
        for row in result.rows:
            view_name = row[0]
            view_comment = row[1][:80] if row[1] else ""
            if view_name[0] not in data:
                data[view_name[0]] = list()
            data[view_name[0]].append([view_name, view_comment])
        return data

    def get_view_detail(self, db_name, view_name, **kwargs):
        """获取视图详情"""
        sql = """SELECT
                    TABLE_NAME as view_name,
                    VIEW_DEFINITION as view_definition,
                    CHECK_OPTION as check_option,
                    IS_UPDATABLE as is_updatable,
                    DEFINER as definer,
                    SECURITY_TYPE as security_type,
                    CHARACTER_SET_CLIENT as character_set_client,
                    COLLATION_CONNECTION as collation_connection
                FROM information_schema.VIEWS
                WHERE TABLE_SCHEMA=%(db_name)s AND TABLE_NAME=%(view_name)s;"""
        _meta = self.query(
            db_name, sql, parameters={"db_name": db_name, "view_name": view_name}
        )
        meta_data = {
            "column_list": _meta.column_list,
            "rows": _meta.rows[0] if _meta.rows else [],
        }
        view_definition = ""
        if _meta.rows:
            # VIEW_DEFINITION 在第二列
            view_definition = _meta.rows[0][1] or ""
        desc = self.get_table_desc_data(db_name=db_name, tb_name=view_name)
        return {
            "meta_data": meta_data,
            "desc": desc,
            "view_definition": view_definition,
        }

    def get_triggers_list(self, db_name, **kwargs):
        """获取触发器列表，按首字符分组"""
        data = {}
        sql = """SELECT
                    TRIGGER_NAME,
                    ACTION_TIMING,
                    EVENT_MANIPULATION,
                    EVENT_OBJECT_TABLE
                FROM information_schema.TRIGGERS
                WHERE TRIGGER_SCHEMA=%(db_name)s;"""
        result = self.query(db_name=db_name, sql=sql, parameters={"db_name": db_name})
        for row in result.rows:
            trigger_name = row[0]
            desc = f"{row[1]} {row[2]} ON {row[3]}"
            if trigger_name[0] not in data:
                data[trigger_name[0]] = list()
            data[trigger_name[0]].append([trigger_name, desc])
        return data

    def get_trigger_detail(self, db_name, trigger_name, **kwargs):
        """获取触发器详情"""
        sql = """SELECT
                    TRIGGER_NAME as trigger_name,
                    ACTION_TIMING as action_timing,
                    EVENT_MANIPULATION as event_manipulation,
                    EVENT_OBJECT_TABLE as event_object_table,
                    ACTION_ORIENTATION as action_orientation,
                    ACTION_STATEMENT as action_statement,
                    DEFINER as definer,
                    CREATED as created,
                    SQL_MODE as sql_mode,
                    CHARACTER_SET_CLIENT as character_set_client,
                    COLLATION_CONNECTION as collation_connection
                FROM information_schema.TRIGGERS
                WHERE TRIGGER_SCHEMA=%(db_name)s AND TRIGGER_NAME=%(trigger_name)s;"""
        _data = self.query(
            db_name,
            sql,
            parameters={"db_name": db_name, "trigger_name": trigger_name},
        )
        return {
            "column_list": _data.column_list,
            "rows": _data.rows[0] if _data.rows else [],
        }

    def get_procedures_list(self, db_name, **kwargs):
        """获取存储过程列表，按首字符分组"""
        data = {}
        sql = """SELECT ROUTINE_NAME, ROUTINE_COMMENT
                    FROM information_schema.ROUTINES
                    WHERE ROUTINE_SCHEMA=%(db_name)s AND ROUTINE_TYPE='PROCEDURE';"""
        result = self.query(db_name=db_name, sql=sql, parameters={"db_name": db_name})
        for row in result.rows:
            proc_name = row[0]
            proc_cmt = row[1]
            if proc_name[0] not in data:
                data[proc_name[0]] = list()
            data[proc_name[0]].append([proc_name, proc_cmt])
        return data

    def get_procedure_detail(self, db_name, proc_name, **kwargs):
        """获取存储过程详情"""
        sql_meta = """SELECT
                    ROUTINE_NAME as routine_name,
                    ROUTINE_SCHEMA as routine_schema,
                    DEFINER as definer,
                    CREATED as created,
                    LAST_ALTERED as last_altered,
                    SQL_MODE as sql_mode,
                    SECURITY_TYPE as security_type,
                    ROUTINE_COMMENT as routine_comment
                FROM information_schema.ROUTINES
                WHERE ROUTINE_SCHEMA=%(db_name)s
                    AND ROUTINE_NAME=%(proc_name)s
                    AND ROUTINE_TYPE='PROCEDURE';"""
        _meta = self.query(
            db_name,
            sql_meta,
            parameters={"db_name": db_name, "proc_name": proc_name},
        )
        meta_data = {
            "column_list": _meta.column_list,
            "rows": _meta.rows[0] if _meta.rows else [],
        }
        _create = self.query(
            db_name, f"SHOW CREATE PROCEDURE {self._quote_identifier(proc_name)};"
        )
        create_sql = _create.rows
        return {"meta_data": meta_data, "create_sql": create_sql}

    def get_functions_list(self, db_name, **kwargs):
        """获取函数列表，按首字符分组"""
        data = {}
        sql = """SELECT ROUTINE_NAME, ROUTINE_COMMENT
                    FROM information_schema.ROUTINES
                    WHERE ROUTINE_SCHEMA=%(db_name)s AND ROUTINE_TYPE='FUNCTION';"""
        result = self.query(db_name=db_name, sql=sql, parameters={"db_name": db_name})
        for row in result.rows:
            func_name = row[0]
            func_cmt = row[1]
            if func_name[0] not in data:
                data[func_name[0]] = list()
            data[func_name[0]].append([func_name, func_cmt])
        return data

    def get_function_detail(self, db_name, func_name, **kwargs):
        """获取函数详情"""
        sql_meta = """SELECT
                    ROUTINE_NAME as routine_name,
                    ROUTINE_SCHEMA as routine_schema,
                    DTD_IDENTIFIER as return_type,
                    DEFINER as definer,
                    CREATED as created,
                    LAST_ALTERED as last_altered,
                    SQL_MODE as sql_mode,
                    SECURITY_TYPE as security_type,
                    ROUTINE_COMMENT as routine_comment
                FROM information_schema.ROUTINES
                WHERE ROUTINE_SCHEMA=%(db_name)s
                    AND ROUTINE_NAME=%(func_name)s
                    AND ROUTINE_TYPE='FUNCTION';"""
        _meta = self.query(
            db_name,
            sql_meta,
            parameters={"db_name": db_name, "func_name": func_name},
        )
        meta_data = {
            "column_list": _meta.column_list,
            "rows": _meta.rows[0] if _meta.rows else [],
        }
        _create = self.query(
            db_name, f"SHOW CREATE FUNCTION {self._quote_identifier(func_name)};"
        )
        create_sql = _create.rows
        return {"meta_data": meta_data, "create_sql": create_sql}

    def get_events_list(self, db_name, **kwargs):
        """获取定时任务列表，按首字符分组"""
        data = {}
        sql = """SELECT
                    EVENT_NAME,
                    STATUS,
                    EVENT_TYPE,
                    INTERVAL_VALUE,
                    INTERVAL_FIELD
                FROM information_schema.EVENTS
                WHERE EVENT_SCHEMA=%(db_name)s;"""
        result = self.query(db_name=db_name, sql=sql, parameters={"db_name": db_name})
        for row in result.rows:
            event_name = row[0]
            status = row[1]
            event_type = row[2]
            interval_value = row[3]
            interval_field = row[4]
            if event_type == "RECURRING":
                desc = f"{status} EVERY {interval_value} {interval_field}"
            else:
                desc = f"{status} ONE TIME"
            if event_name[0] not in data:
                data[event_name[0]] = list()
            data[event_name[0]].append([event_name, desc])
        return data

    def get_event_detail(self, db_name, event_name, **kwargs):
        """获取定时任务详情"""
        sql_meta = """SELECT
                    EVENT_NAME as event_name,
                    EVENT_SCHEMA as event_schema,
                    DEFINER as definer,
                    EVENT_TYPE as event_type,
                    INTERVAL_VALUE as interval_value,
                    INTERVAL_FIELD as interval_field,
                    STATUS as status,
                    EXECUTE_AT as execute_at,
                    STARTS as starts,
                    ENDS as ends,
                    LAST_EXECUTED as last_executed,
                    ON_COMPLETION as on_completion,
                    CREATED as created,
                    LAST_ALTERED as last_altered,
                    EVENT_COMMENT as event_comment
                FROM information_schema.EVENTS
                WHERE EVENT_SCHEMA=%(db_name)s AND EVENT_NAME=%(event_name)s;"""
        _meta = self.query(
            db_name,
            sql_meta,
            parameters={"db_name": db_name, "event_name": event_name},
        )
        meta_data = {
            "column_list": _meta.column_list,
            "rows": _meta.rows[0] if _meta.rows else [],
        }
        _create = self.query(
            db_name, f"SHOW CREATE EVENT {self._quote_identifier(event_name)};"
        )
        create_sql = _create.rows
        return {"meta_data": meta_data, "create_sql": create_sql}

    def get_tables_metas_data(self, db_name, **kwargs):
        """获取数据库所有表格信息，用作数据字典导出接口"""
        sql_tbs = f"SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%(db_name)s ORDER BY TABLE_SCHEMA,TABLE_NAME;"
        tbs = self.query(
            sql=sql_tbs,
            cursorclass=MySQLdb.cursors.DictCursor,
            close_conn=False,
            parameters={"db_name": db_name},
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
            sql_cols = """SELECT * FROM INFORMATION_SCHEMA.COLUMNS
                            WHERE TABLE_SCHEMA=%(table_schema)s AND TABLE_NAME=%(table_name)s
                            ORDER BY TABLE_SCHEMA,TABLE_NAME,ORDINAL_POSITION;"""
            _meta["COLUMNS"] = self.query(
                sql=sql_cols,
                cursorclass=MySQLdb.cursors.DictCursor,
                close_conn=False,
                parameters={
                    "table_schema": tb["TABLE_SCHEMA"],
                    "table_name": tb["TABLE_NAME"],
                },
            ).rows
            table_metas.append(_meta)
        return table_metas

    def get_bind_users(self, db_name: str):
        sql_get_bind_users = f"""select group_concat(distinct(GRANTEE)),TABLE_SCHEMA
                from information_schema.SCHEMA_PRIVILEGES
                where TABLE_SCHEMA=%(db_name)s
                group by TABLE_SCHEMA;"""
        return self.query(
            "information_schema",
            sql_get_bind_users,
            close_conn=False,
            parameters={"db_name": db_name},
        ).rows

    def get_all_databases_summary(self):
        """实例数据库管理功能，获取实例所有的数据库描述信息"""
        # 获取所有数据库
        sql_get_db = """SELECT SCHEMA_NAME,DEFAULT_CHARACTER_SET_NAME,DEFAULT_COLLATION_NAME 
        FROM information_schema.SCHEMATA
        WHERE SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'test', 'sys');"""
        query_result = self.query("information_schema", sql_get_db, close_conn=False)
        if not query_result.error:
            dbs = query_result.rows
            # 获取数据库关联用户信息
            rows = []
            for db in dbs:
                bind_users = self.get_bind_users(db_name=db[0])
                row = {
                    "db_name": db[0],
                    "charset": db[1],
                    "collation": db[2],
                    "grantees": bind_users[0][0].split(",") if bind_users else [],
                    "saved": False,
                }
                rows.append(row)
            query_result.rows = rows
        return query_result

    def get_instance_users_summary(self):
        """实例账号管理功能，获取实例所有账号信息"""
        server_version = self.server_version
        sql_get_user_without_account_locked = "select user, host from mysql.user;"
        # MySQL 5.7.6版本, mariadb 10.4.2  起支持ACCOUNT LOCK
        if self.server_fork_type == MysqlForkType.MYSQL and server_version >= (5, 7, 6):
            support_account_lock = True
            sql_get_user = "select user, host, account_locked from mysql.user;"
        elif self.server_fork_type == MysqlForkType.MARIADB and self.server_version >= (
            10,
            4,
            2,
        ):
            support_account_lock = True
            sql_get_user = "SELECT user, host, JSON_EXTRACT(priv, '$.account_locked') AS account_locked FROM mysql.global_priv;"
        else:
            support_account_lock = False
            sql_get_user = sql_get_user_without_account_locked
        query_result = self.query("mysql", sql_get_user)
        if query_result.error and "account_locked" in sql_get_user:
            # 查询出错了, fallback 到不带 lock 信息的 sql
            query_result = self.query("mysql", sql_get_user_without_account_locked)
        if not query_result.error:
            db_users = query_result.rows
            # 获取用户权限信息
            rows = []
            for db_user in db_users:
                user_host = self._format_user_host(db_user[0], db_user[1])
                user_priv = self.query(
                    "mysql", "show grants for {};".format(user_host), close_conn=False
                ).rows
                row = {
                    "user_host": user_host,
                    "user": db_user[0],
                    "host": db_user[1],
                    "privileges": user_priv,
                    "saved": False,
                    "is_locked": (
                        db_user[2]
                        if support_account_lock and len(db_user) == 3
                        else None
                    ),
                }
                rows.append(row)
            query_result.rows = rows
        return query_result

    def create_instance_user(self, **kwargs):
        """实例账号管理功能，创建实例账号"""
        user = kwargs.get("user", "")
        host = kwargs.get("host", "")
        password1 = kwargs.get("password1", "")
        remark = kwargs.get("remark", "")
        # 在一个事务内执行
        hosts = host.split("|")
        create_user_cmd = ""
        accounts = []
        try:
            password_literal = self._quote_literal(password1)
            for host in hosts:
                account = self._format_user_host(user, host)
                create_user_cmd += (
                    f"create user {account} identified by {password_literal};"
                )
                accounts.append(
                    {
                        "instance": self.instance,
                        "user": user,
                        "host": host,
                        "password": password1,
                        "remark": remark,
                    }
                )
        except ValueError as e:
            return self._error_result(str(e))
        if not accounts:
            return self._error_result("账号信息不能为空")
        exec_result = self.execute(db_name="mysql", sql=create_user_cmd)
        exec_result.rows = accounts
        return exec_result

    def grant_instance_user(
        self,
        user_host,
        op_type,
        priv_type,
        privs,
        db_names=None,
        tb_names=None,
        col_names=None,
    ):
        """实例账号管理功能，授予/回收账号权限"""
        try:
            user_host = self._normalize_user_host(user_host)
            op_type = self._coerce_int(op_type, "操作类型")
            priv_type = self._coerce_int(priv_type, "权限类型")
            if op_type == 0:
                action, target = "GRANT", "TO"
            elif op_type == 1:
                action, target = "REVOKE", "FROM"
            else:
                raise ValueError("操作类型不合法")

            grant_sql = ""
            if priv_type == 0:
                grant_privs = self._normalize_privileges(
                    privs.get("global_privs", []), self.GLOBAL_PRIVILEGES
                )
                grant_sql = (
                    f"{action} {','.join(grant_privs)} ON *.* {target} {user_host};"
                )
            elif priv_type == 1:
                grant_privs = self._normalize_privileges(
                    privs.get("db_privs", []), self.DB_PRIVILEGES
                )
                for db_name in self._as_list(db_names):
                    grant_sql += (
                        f"{action} {','.join(grant_privs)} ON "
                        f"{self._quote_identifier(db_name)}.* {target} {user_host};"
                    )
            elif priv_type == 2:
                grant_privs = self._normalize_privileges(
                    privs.get("tb_privs", []), self.TABLE_PRIVILEGES
                )
                quoted_db = self._quote_identifier(self._as_list(db_names)[0])
                for tb_name in self._as_list(tb_names):
                    grant_sql += (
                        f"{action} {','.join(grant_privs)} ON "
                        f"{quoted_db}.{self._quote_identifier(tb_name)} {target} {user_host};"
                    )
            elif priv_type == 3:
                grant_privs = self._normalize_privileges(
                    privs.get("col_privs", []), self.COLUMN_PRIVILEGES
                )
                quoted_db = self._quote_identifier(self._as_list(db_names)[0])
                quoted_tb = self._quote_identifier(self._as_list(tb_names)[0])
                quoted_cols = ",".join(
                    self._quote_identifier(col_name)
                    for col_name in self._as_list(col_names)
                )
                if not quoted_cols:
                    raise ValueError("列名不能为空")
                for priv in grant_privs:
                    grant_sql += (
                        f"{action} {priv}({quoted_cols}) ON "
                        f"{quoted_db}.{quoted_tb} {target} {user_host};"
                    )
            else:
                raise ValueError("权限类型不合法")
        except (AttributeError, IndexError, ValueError) as e:
            return self._error_result(str(e))

        if not grant_sql:
            return self._error_result("授权语句不能为空")
        return self.execute(db_name="mysql", sql=grant_sql)

    def set_instance_user_lock(self, user_host, is_locked):
        """实例账号管理功能，锁定/解锁账号"""
        try:
            user_host = self._normalize_user_host(user_host)
        except ValueError as e:
            return self._error_result(str(e))
        if is_locked == "N":
            lock_sql = f"ALTER USER {user_host} ACCOUNT LOCK;"
        elif is_locked == "Y":
            lock_sql = f"ALTER USER {user_host} ACCOUNT UNLOCK;"
        else:
            return self._error_result("锁定状态不合法")
        return self.execute(db_name="mysql", sql=lock_sql)

    def drop_instance_user(self, user_host: str, **kwarg):
        """实例账号管理功能，删除实例账号"""
        try:
            user_host = self._normalize_user_host(user_host)
        except ValueError as e:
            return self._error_result(str(e))
        return self.execute(db_name="mysql", sql=f"DROP USER {user_host};")

    def reset_instance_user_pwd(self, user_host: str, reset_pwd: str, **kwargs):
        """实例账号管理功能，重置实例账号密码"""
        try:
            user_host = self._normalize_user_host(user_host)
            reset_pwd = self._quote_literal(reset_pwd)
        except ValueError as e:
            return self._error_result(str(e))
        return self.execute(
            db_name="mysql", sql=f"ALTER USER {user_host} IDENTIFIED BY {reset_pwd};"
        )

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段, 返回一个ResultSet"""
        sql = """SELECT
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
            TABLE_SCHEMA = %(db_name)s
                AND TABLE_NAME = %(tb_name)s
        ORDER BY ORDINAL_POSITION;"""
        result = self.query(
            db_name=db_name,
            sql=sql,
            parameters={"db_name": db_name, "tb_name": tb_name},
        )
        column_list = [row[0] for row in result.rows]
        result.rows = column_list
        return result

    def describe_table(self, db_name, tb_name, **kwargs):
        """return ResultSet 类似查询"""
        sql = f"show create table {self._quote_identifier(tb_name)};"
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

    def query(
        self,
        db_name=None,
        sql="",
        limit_num=0,
        close_conn=True,
        parameters=None,
        **kwargs,
    ):
        """返回 ResultSet"""
        result_set = ResultSet(full_sql=sql)
        max_execution_time = kwargs.get("max_execution_time", 0)
        cursorclass = kwargs.get("cursorclass") or MySQLdb.cursors.Cursor
        try:
            conn = self.get_connection(db_name=db_name)
            conn.autocommit(True)
            cursor = conn.cursor(cursorclass)
            try:
                if self.server_fork_type == MysqlForkType.MARIADB:
                    cursor.execute(
                        f"set session max_statement_time={max_execution_time / 1000};"
                    )
                else:
                    cursor.execute(
                        f"set session max_execution_time={max_execution_time};"
                    )
            except MySQLdb.OperationalError:
                pass
            effect_row = cursor.execute(sql, parameters)
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
            logger.warning(
                f"{self.name}语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}"
            )
            result_set.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result_set

    @staticmethod
    def _normalize_identifier(value):
        if value is None:
            return ""
        value = str(value).strip()
        if len(value) >= 2 and value[0] in ("`", "'", '"') and value[-1] == value[0]:
            value = value[1:-1]
        return value.replace("``", "`").lower()

    @classmethod
    def _sql_references_forbidden_privilege_object(cls, db_name, sql):
        sql_lower = sql.lower()
        for schema, tables in (
            ("mysql", MYSQL_PRIVILEGE_TABLES),
            ("information_schema", INFORMATION_SCHEMA_PRIVILEGE_TABLES),
        ):
            table_pattern = "|".join(re.escape(table) for table in sorted(tables))
            if re.search(
                rf"(?<![\w`])`?{schema}`?\s*\.\s*`?(?:{table_pattern})`?(?![\w`])",
                sql_lower,
            ):
                return True

        try:
            table_refs = extract_tables(sql)
        except Exception:
            table_refs = ()

        current_db = cls._normalize_identifier(db_name)
        current_tables = None
        if current_db == "mysql":
            current_tables = MYSQL_PRIVILEGE_TABLES
        elif current_db == "information_schema":
            current_tables = INFORMATION_SCHEMA_PRIVILEGE_TABLES
        if current_tables:
            table_pattern = "|".join(
                re.escape(table) for table in sorted(current_tables)
            )
            if re.search(
                rf"\b(from|join|update|into|table)\s+`?(?:{table_pattern})`?(?![\w`])",
                sql_lower,
            ):
                return True

        for table_ref in table_refs:
            schema = cls._normalize_identifier(table_ref.schema) or current_db
            name = cls._normalize_identifier(table_ref.name)
            if schema == "mysql" and name in MYSQL_PRIVILEGE_TABLES:
                return True
            if (
                schema == "information_schema"
                and name in INFORMATION_SCHEMA_PRIVILEGE_TABLES
            ):
                return True
        return False

    @staticmethod
    def _sql_is_forbidden_account_statement(sql):
        return bool(
            re.match(r"^\s*show\s+grants\b", sql, re.I)
            or re.match(r"^\s*show\s+create\s+user\b", sql, re.I)
        )

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
        if self._sql_is_forbidden_account_statement(
            sql
        ) or self._sql_references_forbidden_privilege_object(db_name, sql):
            result["bad_query"] = True
            result["msg"] = "您无权查看该表"
            return result
        # select语句先使用Explain判断语法是否正确
        if re.match(r"^select", sql, re.I):
            explain_result = self.query(db_name=db_name, sql=f"explain {sql}")
            if explain_result.error:
                result["bad_query"] = True
                result["msg"] = explain_result.error

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
            logger.debug(
                f"{self.inc_engine.name}检测语句报错：错误信息{traceback.format_exc()}"
            )
            raise RuntimeError(
                f"{self.inc_engine.name}检测语句报错，请注意检查系统配置中{self.inc_engine.name}配置，错误信息：\n{e}"
            )

        # 判断Inception检测结果
        if check_result.error:
            logger.debug(
                f"{self.inc_engine.name}检测语句报错：错误信息{check_result.error}"
            )
            raise RuntimeError(
                f"{self.inc_engine.name}检测语句报错，错误信息：\n{check_result.error}"
            )

        # 禁用/高危语句检查
        critical_ddl_regex = self.config.get("critical_ddl_regex", "")
        ddl_dml_separation = self.config.get("ddl_dml_separation", False)
        try:
            p = self._compile_safe_regex(critical_ddl_regex)
        except ValueError as e:
            check_result.error_count += len(check_result.rows) or 1
            for row in check_result.rows:
                row.stagestatus = "驳回高危SQL"
                row.errlevel = 2
                row.errormessage = str(e)
            if not check_result.rows:
                check_result.error = str(e)
            return check_result
        # 获取语句类型：DDL或者DML
        ddl_dml_flag = ""
        for row in check_result.rows:
            statement = row.sql
            # 去除注释
            statement = remove_comments(statement, db_type="mysql")
            # 获取提交类型
            syntax_type = get_syntax_type(statement, parser=False, db_type="mysql")
            # 禁用语句
            if re.match(r"^select", statement.lower()):
                check_result.error_count += 1
                row.stagestatus = "驳回不支持语句"
                row.errlevel = 2
                row.errormessage = "仅支持DML和DDL语句，查询语句请使用SQL查询功能！"
            # 高危语句
            elif critical_ddl_regex and p:
                try:
                    critical_match = p.match(
                        statement.strip().lower(),
                        timeout=CRITICAL_DDL_REGEX_TIMEOUT,
                    )
                except TimeoutError:
                    check_result.error_count += 1
                    row.stagestatus = "驳回高危SQL"
                    row.errlevel = 2
                    row.errormessage = (
                        "critical_ddl_regex匹配超时，已拒绝执行以避免ReDoS"
                    )
                    continue
                if not critical_match:
                    if ddl_dml_separation and syntax_type in ("DDL", "DML"):
                        if ddl_dml_flag == "":
                            ddl_dml_flag = syntax_type
                        elif ddl_dml_flag != syntax_type:
                            check_result.error_count += 1
                            row.stagestatus = "驳回不支持语句"
                            row.errlevel = 2
                            row.errormessage = "DDL语句和DML语句不能同时执行！"
                    continue
                check_result.error_count += 1
                row.stagestatus = "驳回高危SQL"
                row.errlevel = 2
                row.errormessage = "禁止提交匹配" + critical_ddl_regex + "条件的语句！"
            elif ddl_dml_separation and syntax_type in ("DDL", "DML"):
                if ddl_dml_flag == "":
                    ddl_dml_flag = syntax_type
                elif ddl_dml_flag != syntax_type:
                    check_result.error_count += 1
                    row.stagestatus = "驳回不支持语句"
                    row.errlevel = 2
                    row.errormessage = "DDL语句和DML语句不能同时执行！"
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

    def execute(self, db_name=None, sql="", close_conn=True, parameters=None):
        """原生执行语句"""
        result = ResultSet(full_sql=sql)
        conn = self.get_connection(db_name=db_name)
        try:
            cursor = conn.cursor()
            for statement in sqlparse.split(sql):
                cursor.execute(statement, parameters)
            conn.commit()
            cursor.close()
        except Exception as e:
            logger.warning(
                f"{self.name}语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}"
            )
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
            variables = self._as_list(variables)
            placeholders = ",".join(["%s"] * len(variables))
            sql = f"show global variables where variable_name in ({placeholders});"
            return self.query(sql=sql, parameters=tuple(variables))
        else:
            sql = "show global variables;"
        return self.query(sql=sql)

    def set_variable(self, variable_name, variable_value):
        """修改实例参数值"""
        if not variable_name or not self.VARIABLE_NAME_RE.match(str(variable_name)):
            return self._error_result("参数名称不合法")
        sql = f"set global {variable_name}=%s;"
        return self.query(sql=sql, parameters=(variable_value,))

    def osc_control(self, **kwargs):
        """控制osc执行，获取进度、终止、暂停、恢复等
        get、kill、pause、resume
        """
        return self.inc_engine.osc_control(**kwargs)

    def processlist(
        self,
        command_type,
        base_sql="select id, user, host, db, command, time, state, ifnull(info,'') as info from information_schema.processlist",
        **kwargs,
    ):
        """获取连接信息"""
        if not command_type:
            command_type = "Query"
        if command_type == "All":
            sql = base_sql + ";"
            parameters = None
        elif command_type == "Not Sleep":
            sql = "{} where command<>%s;".format(base_sql)
            parameters = ("Sleep",)
        else:
            sql = "{} where command=%s;".format(base_sql)
            parameters = (command_type,)

        return self.query("information_schema", sql, parameters=parameters)

    def get_kill_command(self, thread_ids, thread_ids_check=True):
        """由传入的线程列表生成kill命令"""
        # 校验传参
        if thread_ids_check:
            try:
                thread_ids = self._validate_thread_ids(thread_ids)
            except ValueError:
                return None
        if not thread_ids:
            return ""
        placeholders = ",".join(["%s"] * len(thread_ids))
        sql = (
            "select concat('kill ', id, ';') from information_schema.processlist "
            f"where id in ({placeholders});"
        )
        all_kill_sql = self.query(
            "information_schema", sql, parameters=tuple(thread_ids)
        )
        kill_sql = ""
        for row in all_kill_sql.rows:
            kill_sql = kill_sql + row[0]

        return kill_sql

    def kill(self, thread_ids, thread_ids_check=True):
        """kill线程"""
        # 校验传参
        if thread_ids_check:
            try:
                thread_ids = self._validate_thread_ids(thread_ids)
            except ValueError:
                return ResultSet(full_sql="")
        if not thread_ids:
            return ResultSet(full_sql="")
        placeholders = ",".join(["%s"] * len(thread_ids))
        sql = (
            "select concat('kill ', id, ';') from information_schema.processlist "
            f"where id in ({placeholders});"
        )
        all_kill_sql = self.query(
            "information_schema", sql, parameters=tuple(thread_ids)
        )
        kill_sql = ""
        for row in all_kill_sql.rows:
            kill_sql = kill_sql + row[0]
        return self.execute("information_schema", kill_sql)

    def tablespace(self, offset=0, row_count=14, schema_search=""):
        """获取表空间信息"""
        try:
            offset = self._coerce_int(offset, "offset", minimum=0)
            row_count = self._coerce_int(row_count, "row_count", minimum=0)
        except ValueError as e:
            return self._error_result(str(e))
        search_condition = ""
        parameters = []
        if schema_search:
            search_condition = " AND (table_schema LIKE %s OR table_name LIKE %s)"
            search_keyword = f"%{schema_search}%"
            parameters.extend([search_keyword, search_keyword])
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
        WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'test', 'sys'){search_condition}
          ORDER BY total_size DESC 
        LIMIT %s,%s;""".format(search_condition=search_condition)
        parameters.extend([offset, row_count])
        return self.query("information_schema", sql, parameters=tuple(parameters))

    def tablespace_count(self, schema_search=""):
        """获取表空间数量"""
        search_condition = ""
        parameters = []
        if schema_search:
            search_condition = " AND (table_schema LIKE %s OR table_name LIKE %s)"
            search_keyword = f"%{schema_search}%"
            parameters.extend([search_keyword, search_keyword])
        sql = """
        SELECT count(*)
        FROM information_schema.tables 
        WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'test', 'sys'){search_condition}""".format(
            search_condition=search_condition
        )
        return self.query(
            "information_schema", sql, parameters=tuple(parameters) or None
        )

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
        GROUP_CONCAT(t1.sql_text order by t1.TIMER_START desc SEPARATOR ';
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
        ORDER BY trx.trx_started ASC;""".format(thread_time)

        return self.query("information_schema", sql)

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
