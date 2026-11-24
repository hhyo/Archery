# -*- coding: UTF-8 -*-
"""
@license: Apache Licence
@file: kingbase.py
@desc: KingbaseES (KES) engine for Archery.

Design goals (independent KingbaseES entry):
  - Independent db_type "kingbase" with its own name.
  - Driver: ksycopg2 (Kingbase's own Python driver, published on PyPI).
  - Metadata and monitoring SQL use KES-native sys_* catalogs (sys_catalog.sys_database,
    sys_catalog.sys_namespace, sys_catalog.sys_class, sys_catalog.sys_attribute, sys_catalog.sys_type, sys_catalog.sys_description,
    sys_catalog.sys_settings, sys_catalog.sys_stat_activity, sys_stat_statements).
"""

import json
import re
import logging
import traceback

import ksycopg2 as db_driver
import sqlparse
from ksycopg2 import sql as db_sql

from common.config import SysConfig
from common.utils.timer import FuncTimer
from sql.utils.sql_utils import get_syntax_type
from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult
from sql.utils.data_masking import simple_column_mask

logger = logging.getLogger("default")

DRIVER_NAME = "ksycopg2"

# KES default database and listen port.
KES_DEFAULT_DB = "test"
KES_DEFAULT_PORT = 54321

# KES system schemas that should be hidden from the user-facing object lists.
KES_SYSTEM_SCHEMAS = (
    "information_schema",
    "sys_catalog",
    "sys",
    "pg_catalog",
    "pg_bitmapindex",
    "kdb_schedule",
    "sys_hm",
    "sysaudit",
    "sysmac",
    "xlog_record_read",
    "src_restrict",
    "anon",
    "dbms_job",
    "dbms_scheduler",
    "perf",
)

# SQL fragment excluding KES system schemas from user-facing object lists.
# KES has no pg_toast/pg_temp schemas; toast relations live under sys_catalog.
# Keep this in sync with KES_SYSTEM_SCHEMAS; both lists filter system objects
# out of the metadata views.
_SYSTEM_SCHEMA_SQL = (
    "('sys_catalog', 'information_schema', 'sys', 'pg_catalog', "
    "'pg_bitmapindex', 'kdb_schedule', 'sysaudit', 'sysmac', "
    "'dbms_job', 'dbms_scheduler', 'perf', 'anon', 'src_restrict', "
    "'sys_hm', 'xlog_record_read')"
)

# JSON / JSONB type codes in KES.
JSON_TYPE_CODES = (114, 3802)

# Shown when a statement cannot be reversed automatically.
_ROLLBACK_UNSUPPORTED = (
    "KingbaseES 暂不支持该语句的自动回滚生成；请使用备份/PITR 或人工补偿SQL。"
)


class KingbaseEngine(EngineBase):
    """KingbaseES engine using ksycopg2 and KES-native sys_* catalogs."""

    name = "KingbaseES"
    info = "KingbaseES engine"
    test_query = "SELECT 1"

    # Database the cached self.conn is bound to (None when not connected).
    _conn_db = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def get_connection(self, db_name=None):
        """Open a ksycopg2 connection. KES default database is 'test'.

        A KES connection is bound to a single database, so a cached connection
        is only reused when it targets the same database; otherwise it is
        closed first and a new one is opened.
        """
        db_name = db_name or self.db_name or KES_DEFAULT_DB
        if self.conn and self._conn_db == db_name:
            return self.conn
        if self.conn:
            self.close()
        conn = db_driver.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            client_encoding=self.instance.charset,
            dbname=db_name,
            connect_timeout=10,
        )
        self.conn = conn
        self._conn_db = db_name
        return conn

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception:  # pragma: no cover
                pass
            self.conn = None
        self._conn_db = None

    # ------------------------------------------------------------------
    # Version
    # ------------------------------------------------------------------
    @property
    def server_version(self):
        """Parse KingbaseES version text, e.g. 'KingbaseES V009R001C010'.

        Returns a tuple (major, minor, patch):
          V009R001C010 -> (9, 1, 10)
        Falls back to a PostgreSQL-style x.y.z string when absent.
        """
        result = self.query(sql="SELECT version();")
        if result.error or not result.rows:
            return tuple()
        version_text = str(result.rows[0][0])
        match = re.search(r"V(\d+)R(\d+)C(\d+)", version_text, re.I)
        if match:
            return int(match.group(1)), int(match.group(2)), int(match.group(3))
        match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", version_text)
        if match:
            return int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)
        return tuple()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def query_check(self, db_name=None, sql=""):
        """Only SELECT / EXPLAIN statements are allowed for online queries."""
        result = {"msg": "", "bad_query": False, "filtered_sql": sql, "has_star": False}
        try:
            sql = sqlparse.format(sql, strip_comments=True)
            sql = sqlparse.split(sql)[0]
            result["filtered_sql"] = sql.strip()
        except IndexError:
            result["bad_query"] = True
            result["msg"] = "没有有效的SQL语句"
        if re.match(r"^select|^explain", sql, re.I) is None:
            # SHOW CREATE TABLE is synthesized by query() so it is safe to
            # allow through validation (the table-structure shortcut uses it).
            if re.match(r"^\s*show\s+create\s+table\s+", sql, re.I):
                result["bad_query"] = False
                result["msg"] = ""
            else:
                result["bad_query"] = True
                result["msg"] = "不支持的查询语法类型!"
        if "*" in sql:
            result["has_star"] = True
            result["msg"] += "SQL语句中含有 * "
        return result

    def query(
        self,
        db_name=None,
        sql="",
        limit_num=0,
        close_conn=True,
        parameters=None,
        **kwargs,
    ):
        """Execute a read-only query and return a ResultSet.

        SHOW CREATE TABLE is MySQL syntax; the data dictionary still sends it,
        so route it to show_create_table() which synthesizes the DDL.
        """
        show_create_match = re.match(
            r'^\s*show\s+create\s+table\s+("?[\w.]+"?)\s*;?\s*$', sql or "", re.I
        )
        if show_create_match:
            return self.show_create_table(
                db_name=db_name,
                table_name=show_create_match.group(1),
                schema_name=kwargs.get("schema_name"),
                close_conn=close_conn,
            )
        schema_name = kwargs.get("schema_name")
        result_set = ResultSet(full_sql=sql)
        conn = None
        try:
            conn = self.get_connection(db_name=db_name)
            conn.autocommit = False
            max_execution_time = kwargs.get("max_execution_time", 0)
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SET statement_timeout TO %s;", (int(max_execution_time),)
                )
            except Exception:
                pass
            cursor.execute("SET transaction ISOLATION LEVEL READ COMMITTED READ ONLY;")
            if schema_name:
                cursor.execute(
                    db_sql.SQL("SET search_path TO {};").format(
                        db_sql.Identifier(schema_name)
                    )
                )
            cursor.execute(sql, parameters)
            rows = (
                cursor.fetchmany(size=int(limit_num))
                if int(limit_num) > 0
                else cursor.fetchall()
            )
            conn.commit()
            fields = cursor.description
            column_type_codes = [i[1] for i in fields] if fields else []
            converted_rows = []
            for row in rows:
                new_row = []
                for idx, col_value in enumerate(row):
                    type_code = (
                        column_type_codes[idx] if idx < len(column_type_codes) else None
                    )
                    if type_code in JSON_TYPE_CODES and isinstance(
                        col_value, (dict, list)
                    ):
                        new_row.append(json.dumps(col_value, ensure_ascii=False))
                    else:
                        new_row.append(col_value)
                converted_rows.append(tuple(new_row))
            result_set.column_list = [i[0] for i in fields] if fields else []
            result_set.rows = converted_rows
            result_set.affected_rows = len(converted_rows)
        except Exception as e:
            if conn:
                conn.rollback()
            safe_sql = self._PWD_IN_SQL_RE.sub(r"\1'******'", str(sql or ""))
            safe_trace = self._PWD_IN_SQL_RE.sub(r"\1'******'", traceback.format_exc())
            logger.warning(
                f"KingbaseES 命令执行报错，语句：{safe_sql}，" f"错误信息：{safe_trace}"
            )
            result_set.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result_set

    def filter_sql(self, sql="", limit_num=0):
        """Append a LIMIT clause for plain SELECT statements."""
        sql_lower = sql.lower().rstrip(";").strip()
        if re.match(r"^select", sql_lower):
            # A native LIMIT at the end already caps the result, including
            # the "LIMIT n OFFSET m" form. Never append a second LIMIT.
            has_native_limit = any(
                re.search(pattern, sql_lower)
                for pattern in (
                    r"limit\s+\d+$",
                    r"limit\s+\d+\s*,\s*\d+$",
                    r"limit\s+\d+\s+offset\s+\d+$",
                    r"limit\s+\d+\s+offset\s+\d+\s+rows?$",
                )
            )
            if not has_native_limit:
                return f"{sql.rstrip(';')} limit {limit_num};"
        return f"{sql.rstrip(';')};"

    def query_masking(self, db_name=None, sql="", resultset=None):
        """Apply simple column masking, only for SELECT statements."""
        if re.match(r"^select", sql, re.I):
            filtered_result = simple_column_mask(self.instance, resultset)
            filtered_result.is_masked = True
            return filtered_result
        return resultset

    # ------------------------------------------------------------------
    # SQL review / workflow execution / rollback
    # ------------------------------------------------------------------
    # Statements that would break Archery's transaction handling.
    _REJECT_STMT_RE = re.compile(
        r"^\s*(commit|rollback|begin|start\s+transaction|savepoint|"
        r"set\s+transaction|end)\b",
        re.I,
    )

    def execute_check(self, db_name=None, sql=""):
        """Pre-execution review for SQL workflow, returns a ReviewSet.

        Rules:
          - SELECT / EXPLAIN are rejected (use the query page instead).
          - Statements matching critical_ddl_regex are rejected.
          - Transaction-control statements are rejected (they break the
            workflow transaction management).
          - UPDATE / DELETE without WHERE, and DROP/TRUNCATE are warnings.
        """
        config = SysConfig()
        check_result = ReviewSet(full_sql=sql)
        line = 1
        critical_ddl_regex = config.get("critical_ddl_regex", "")
        critical_pattern = (
            re.compile(critical_ddl_regex) if critical_ddl_regex else None
        )
        check_result.syntax_type = 2  # 0 other, 1 DDL, 2 DML

        for statement in sqlparse.split(sql):
            statement = sqlparse.format(statement, strip_comments=True).strip()
            if not statement:
                continue
            sql_lower = statement.lower()

            if re.match(r"^(select|explain)\b", sql_lower):
                result = ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="驳回不支持语句",
                    errormessage="仅支持DML和DDL语句，查询语句请使用SQL查询功能！",
                    sql=statement,
                )
            elif self._REJECT_STMT_RE.match(statement):
                result = ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="驳回不支持语句",
                    errormessage="事务控制语句(COMMIT/ROLLBACK/BEGIN)不允许在工单中执行",
                    sql=statement,
                )
            elif critical_pattern and critical_pattern.match(sql_lower):
                result = ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="驳回高危SQL",
                    errormessage=f"禁止提交匹配 {critical_ddl_regex} 条件的语句！",
                    sql=statement,
                )
            elif re.match(r"^(drop|truncate)\b", sql_lower):
                result = ReviewResult(
                    id=line,
                    errlevel=1,
                    stagestatus="高危操作",
                    errormessage="DROP/TRUNCATE 属于不可逆操作，请确认已备份！",
                    sql=statement,
                )
            elif re.match(r"^(update|delete)\b", sql_lower) and not re.search(
                r"\bwhere\b", sql_lower
            ):
                result = ReviewResult(
                    id=line,
                    errlevel=1,
                    stagestatus="警告",
                    errormessage="UPDATE/DELETE 未包含 WHERE 条件，将影响全表数据！",
                    sql=statement,
                )
            else:
                result = ReviewResult(
                    id=line,
                    errlevel=0,
                    stagestatus="Audit completed",
                    errormessage="None",
                    sql=statement,
                    affected_rows=0,
                    execute_time=0,
                )

            if get_syntax_type(statement) == "DDL":
                check_result.syntax_type = 1
            check_result.rows += [result]
            line += 1

        for r in check_result.rows:
            if r.errlevel == 1:
                check_result.warning_count += 1
            if r.errlevel == 2:
                check_result.error_count += 1
        return check_result

    def execute_workflow(self, workflow, close_conn=True):
        """Execute a SQL workflow inside a single transaction."""
        sql = workflow.sqlworkflowcontent.sql_content
        execute_result = ReviewSet(full_sql=sql)
        split_sql = sqlparse.split(sqlparse.format(sql, strip_comments=True))
        line = 1
        statement = None
        db_name = workflow.db_name
        conn = None
        try:
            conn = self.get_connection(db_name=db_name)
            conn.autocommit = False
            cursor = conn.cursor()
            cursor.execute("SET transaction ISOLATION LEVEL READ COMMITTED READ WRITE;")
            for statement in split_sql:
                statement = statement.rstrip(";")
                if not statement.strip():
                    continue
                with FuncTimer() as t:
                    cursor.execute(statement)
                execute_result.rows.append(
                    ReviewResult(
                        id=line,
                        errlevel=0,
                        stagestatus="Execute Successfully",
                        errormessage="None",
                        sql=statement,
                        affected_rows=cursor.rowcount,
                        execute_time=t.cost,
                    )
                )
                line += 1
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            failed_sql = statement or sql
            safe_sql = self._PWD_IN_SQL_RE.sub(r"\1'******'", str(failed_sql or ""))
            safe_trace = self._PWD_IN_SQL_RE.sub(r"\1'******'", traceback.format_exc())
            logger.warning(
                f"KingbaseES 命令执行报错，语句：{safe_sql}，" f"错误信息：{safe_trace}"
            )
            execute_result.error = str(e)
            execute_result.rows.append(
                ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="Execute Failed",
                    errormessage=f"异常信息：{e}",
                    sql=statement or sql,
                    affected_rows=0,
                    execute_time=0,
                )
            )
            line += 1
            for trailing in split_sql[line - 1 :]:
                execute_result.rows.append(
                    ReviewResult(
                        id=line,
                        errlevel=0,
                        stagestatus="Audit completed",
                        errormessage="前序语句失败, 未执行",
                        sql=trailing,
                        affected_rows=0,
                        execute_time=0,
                    )
                )
                line += 1
        finally:
            if close_conn:
                self.close()
        return execute_result

    def execute(self, db_name=None, sql="", close_conn=True, parameters=None):
        """Execute statements without review (used by instance database creation)."""
        result = ResultSet(full_sql=sql)
        conn = None
        try:
            conn = self.get_connection(db_name=db_name)
            conn.autocommit = False
            cursor = conn.cursor()
            for statement in sqlparse.split(sql):
                if statement.strip():
                    cursor.execute(statement, parameters)
            conn.commit()
            cursor.close()
        except Exception as e:
            if conn:
                conn.rollback()
            safe_sql = self._PWD_IN_SQL_RE.sub(r"\1'******'", str(sql or ""))
            safe_trace = self._PWD_IN_SQL_RE.sub(r"\1'******'", traceback.format_exc())
            logger.warning(
                f"KingbaseES 语句执行报错，语句：{safe_sql}，" f"错误信息：{safe_trace}"
            )
            result.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result

    def get_rollback(self, workflow):
        """Generate rollback statements from the workflow's execution result.

        When the workflow transaction was aborted, nothing actually committed,
        so there is nothing to roll back. Generating metadata reverses from the
        attempted statements would be destructive: a failed CREATE TABLE ... on
        an existing table would produce a DROP of that pre-existing table.
        """
        if getattr(workflow, "status", None) == "workflow_exception":
            return []
        try:
            list_execute_result = json.loads(workflow.sqlworkflowcontent.execute_result)
        except Exception:
            return []
        # Any statement that did not execute successfully means the transaction
        # was rolled back as a whole; no statement's effects are reversible.
        for item in list_execute_result:
            stage = str(item.get("stagestatus", "")) if isinstance(item, dict) else ""
            if stage and stage != "Execute Successfully":
                return []
        list_execute_result.reverse()
        rollback_sql = []
        for item in list_execute_result:
            source_sql = item.get("sql", "") if isinstance(item, dict) else ""
            rollback_sql.append(
                [source_sql, self._build_metadata_rollback_sql(source_sql)]
            )
        return rollback_sql

    @staticmethod
    def _build_metadata_rollback_sql(source_sql):
        """Best-effort reverse statement for DDL; DML cannot be auto-rolled back."""
        source = str(source_sql or "").strip().rstrip(";")
        unsupported = _ROLLBACK_UNSUPPORTED
        parsed = sqlparse.parse(source)
        if not parsed:
            return unsupported

        # CREATE <object>
        create_match = re.match(
            r"^\s*create\s+(or\s+replace\s+)?(?:temp(?:orary)?\s+)?"
            r"(table|view|index|schema|sequence)\s+(if\s+not\s+exists\s+)?"
            r'((?:"[^"]+"|\w+)(?:\.(?:"[^"]+"|\w+))?)',
            source,
            re.I,
        )
        if create_match:
            or_replace = bool(create_match.group(1))
            obj_type = create_match.group(2).lower()
            if_not_exists = bool(create_match.group(3))
            obj_name = create_match.group(4)
            # "CREATE OR REPLACE" / "IF NOT EXISTS" may leave a pre-existing
            # object untouched, so dropping it on rollback would destroy data
            # the workflow never created.
            if or_replace or if_not_exists:
                return (
                    _ROLLBACK_UNSUPPORTED
                    + "该语句为 CREATE OR REPLACE / IF NOT EXISTS，"
                    "对象可能已存在，自动回滚会删除原有对象。"
                )
            return {
                "table": f"DROP TABLE IF EXISTS {obj_name};",
                "view": f"DROP VIEW IF EXISTS {obj_name};",
                "index": f"DROP INDEX IF EXISTS {obj_name};",
                "schema": f"DROP SCHEMA IF EXISTS {obj_name} CASCADE;",
                "sequence": f"DROP SEQUENCE IF EXISTS {obj_name};",
            }[obj_type]

        # ALTER TABLE ... ADD CONSTRAINT
        m = re.match(
            r"^\s*alter\s+table\s+(\S+)\s+add\s+constraint\s+(\S+)", source, re.I
        )
        if m:
            return f"ALTER TABLE {m.group(1)} DROP CONSTRAINT IF EXISTS {m.group(2)};"

        # ALTER TABLE ... ADD [COLUMN] col
        m = re.match(
            r"^\s*alter\s+table\s+(\S+)\s+add\s+(?:column\s+)?"
            r"(if\s+not\s+exists\s+)?(\S+)",
            source,
            re.I,
        )
        if m:
            # IF NOT EXISTS may be a no-op when the column already exists;
            # dropping it on rollback would destroy pre-existing data.
            if m.group(2):
                return (
                    _ROLLBACK_UNSUPPORTED + "ADD COLUMN IF NOT EXISTS 可能未新增列，"
                    "自动回滚会删除原有列及其数据。"
                )
            return f"ALTER TABLE {m.group(1)} DROP COLUMN IF EXISTS {m.group(3)};"

        # ALTER TABLE ... DROP COLUMN col → cannot restore data
        if re.match(r"^\s*alter\s+table\s+\S+\s+drop\s+column\b", source, re.I):
            return "无法自动生成回滚：DROP COLUMN 已丢失数据，请从备份恢复。"

        # ALTER TABLE ... RENAME COLUMN a TO b
        m = re.match(
            r"^\s*alter\s+table\s+(\S+)\s+rename\s+column\s+(\S+)\s+to\s+(\S+)",
            source,
            re.I,
        )
        if m:
            return (
                f"ALTER TABLE {m.group(1)} RENAME COLUMN {m.group(3)} TO {m.group(2)};"
            )

        # ALTER TABLE ... RENAME TO x
        m = re.match(r"^\s*alter\s+table\s+(\S+)\s+rename\s+to\s+(\S+)", source, re.I)
        if m:
            old_name, new_name = m.group(1), m.group(2)
            if "." in old_name:
                schema, base = old_name.rsplit(".", 1)
                return f"ALTER TABLE {schema}.{new_name} RENAME TO {base};"
            return f"ALTER TABLE {new_name} RENAME TO {old_name};"

        return unsupported

    # ------------------------------------------------------------------
    # Metadata (KES-native sys_* SQL)
    # ------------------------------------------------------------------
    def get_all_databases(self):
        """List databases using KES sys_catalog.sys_database."""
        sql = "SELECT datname FROM sys_catalog.sys_database WHERE datallowconn = true;"
        result = self.query(sql=sql)
        result.rows = [
            row[0] for row in result.rows if row[0] not in ("template0", "template1")
        ]
        return result

    def get_all_schemas(self, db_name, **kwargs):
        """List schemas using KES sys_catalog.sys_namespace."""
        sql = "SELECT nspname FROM sys_catalog.sys_namespace ORDER BY nspname;"
        result = self.query(db_name=db_name, sql=sql)
        result.rows = [
            row[0] for row in result.rows if row[0] not in KES_SYSTEM_SCHEMAS
        ]
        return result

    def get_all_tables(self, db_name, **kwargs):
        """List tables using KES sys_catalog.sys_class + sys_catalog.sys_namespace."""
        schema_name = kwargs.get("schema_name") or "public"
        sql = """
            SELECT c.relname
            FROM sys_catalog.sys_class c
            JOIN sys_catalog.sys_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %(schema_name)s
              AND c.relkind IN ('r', 'p')
            ORDER BY c.relname;
        """
        result = self.query(
            db_name=db_name, sql=sql, parameters={"schema_name": schema_name}
        )
        result.rows = [row[0] for row in result.rows]
        return result

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """List columns using KES sys_catalog.sys_attribute + sys_catalog.sys_type."""
        schema_name, tb_name = self._split_table_name(
            tb_name, kwargs.get("schema_name")
        )
        sql = """
            SELECT a.attname
            FROM sys_catalog.sys_attribute a
            JOIN sys_catalog.sys_class c ON c.oid = a.attrelid
            JOIN sys_catalog.sys_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = %(tb_name)s
              AND n.nspname = %(schema_name)s
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY a.attnum;
        """
        result = self.query(
            db_name=db_name,
            sql=sql,
            parameters={"schema_name": schema_name, "tb_name": tb_name},
        )
        result.rows = [row[0] for row in result.rows]
        return result

    def describe_table(self, db_name, tb_name, **kwargs):
        """Describe a table using KES-native catalogs."""
        schema_name, tb_name = self._split_table_name(
            tb_name, kwargs.get("schema_name")
        )
        sql = """
            SELECT
                a.attname AS column_name,
                t.typname AS data_type,
                CASE WHEN a.atttypmod > 0 THEN a.atttypmod - 4 END AS character_maximum_length,
                NULL AS numeric_precision,
                NULL AS numeric_scale,
                CASE WHEN a.attnotnull THEN 'NO' ELSE 'YES' END AS is_nullable,
                sys_get_expr(ad.adbin, ad.adrelid) AS column_default,
                des.description AS description
            FROM sys_catalog.sys_attribute a
            JOIN sys_catalog.sys_class c ON c.oid = a.attrelid
            JOIN sys_catalog.sys_namespace n ON n.oid = c.relnamespace
            JOIN sys_catalog.sys_type t ON t.oid = a.atttypid
            LEFT JOIN sys_catalog.sys_attrdef ad ON ad.adrelid = c.oid AND ad.adnum = a.attnum
            LEFT JOIN sys_catalog.sys_description des ON des.objoid = c.oid AND des.objsubid = a.attnum
            WHERE c.relname = %(tb_name)s
              AND n.nspname = %(schema_name)s
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY a.attnum;
        """
        return self.query(
            db_name=db_name,
            sql=sql,
            parameters={"schema_name": schema_name, "tb_name": tb_name},
        )

    def get_table_meta_data(self, db_name, tb_name, **kwargs):
        """Table metadata using KES sys_* catalogs (for data dictionary)."""
        schema_name, tb_name = self._split_table_name(
            tb_name, kwargs.get("schema_name")
        )
        sql = """
            SELECT
                n.nspname AS schema_name,
                c.relname AS table_name,
                obj_description(c.oid) AS table_comment,
                sys_size_pretty(sys_total_relation_size(c.oid)) AS table_size,
                c.reltuples::bigint AS estimated_rows
            FROM sys_catalog.sys_class c
            JOIN sys_catalog.sys_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = %(tb_name)s AND n.nspname = %(schema_name)s;
        """
        result = self.query(
            db_name=db_name,
            sql=sql,
            parameters={"schema_name": schema_name, "tb_name": tb_name},
        )
        # showTableInfo reads meta_data.rows as one flat row aligned with
        # column_list, so return the first row rather than the whole list.
        return {
            "rows": result.rows[0] if result.rows else (),
            "column_list": result.column_list,
        }

    def get_table_desc_data(self, db_name, tb_name, **kwargs):
        """Column metadata for the data dictionary."""
        schema_name, clean_table_name = self._split_table_name(
            tb_name, kwargs.get("schema_name")
        )
        sql = """
            SELECT
                col.column_name AS "列名",
                CASE
                    WHEN col.character_maximum_length IS NOT NULL
                        THEN col.data_type || '(' || col.character_maximum_length || ')'
                    WHEN col.data_type IN ('numeric', 'decimal')
                         AND col.numeric_precision IS NOT NULL AND col.numeric_scale IS NOT NULL
                        THEN col.data_type || '(' || col.numeric_precision || ',' || col.numeric_scale || ')'
                    WHEN col.data_type IN ('numeric', 'decimal') AND col.numeric_precision IS NOT NULL
                        THEN col.data_type || '(' || col.numeric_precision || ')'
                    ELSE col.data_type
                END AS "列类型",
                '' AS "列字符集",
                col.is_nullable AS "是否为空",
                CASE WHEN kcu.column_name IS NOT NULL THEN 'PRI' ELSE '' END AS "索引列",
                col.column_default AS "默认值",
                '' AS "拓展信息",
                COALESCE(des.description, '') AS "列说明"
            FROM information_schema.columns col
            LEFT JOIN information_schema.table_constraints tc
                ON tc.table_schema = col.table_schema
                AND tc.table_name = col.table_name
                AND tc.constraint_type = 'PRIMARY KEY'
            LEFT JOIN information_schema.key_column_usage kcu
                ON kcu.constraint_schema = tc.constraint_schema
                AND kcu.constraint_name = tc.constraint_name
                AND kcu.table_schema = col.table_schema
                AND kcu.table_name = col.table_name
                AND kcu.column_name = col.column_name
            LEFT JOIN sys_catalog.sys_class cls
                ON cls.relname = col.table_name
                AND cls.relnamespace = (
                    SELECT oid FROM sys_catalog.sys_namespace WHERE nspname = col.table_schema
                )
            LEFT JOIN sys_catalog.sys_description des
                ON des.objoid = cls.oid AND des.objsubid = col.ordinal_position
            WHERE col.table_schema = %(schema_name)s
              AND col.table_name = %(tb_name)s
            ORDER BY col.ordinal_position;
        """
        result = self.query(
            db_name=db_name,
            sql=sql,
            parameters={"schema_name": schema_name, "tb_name": clean_table_name},
        )
        return {"rows": result.rows, "column_list": result.column_list}

    # ------------------------------------------------------------------
    # Object name helpers (shared by data dictionary)
    # ------------------------------------------------------------------
    @staticmethod
    def _split_qualified_name(name):
        """Split a qualified name by '.', keeping double-quoted parts intact."""
        parts, buf, in_quote = [], "", False
        for ch in name:
            if ch == '"':
                in_quote = not in_quote
                continue
            if ch == "." and not in_quote:
                parts.append(buf)
                buf = ""
            else:
                buf += ch
        if buf:
            parts.append(buf)
        return parts

    @classmethod
    def _split_table_name(cls, table_name, schema_name=None):
        clean_name = (table_name or "").strip().rstrip(";")
        parts = cls._split_qualified_name(clean_name)
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        return schema_name or "public", parts[0] if parts else ""

    @staticmethod
    def _display_object_name(schema_name, object_name):
        if schema_name == "public":
            return object_name
        return f"{schema_name}.{object_name}"

    def get_group_tables_by_db(self, db_name, **kwargs):
        """Group tables by first character, for the data dictionary tree."""
        data = {}
        sql = f"""
            SELECT n.nspname AS table_schema,
                   c.relname AS table_name,
                   COALESCE(obj_description(c.oid), '') AS table_comment
            FROM sys_catalog.sys_class c
            JOIN sys_catalog.sys_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'p')
              AND n.nspname NOT IN {_SYSTEM_SCHEMA_SQL}
            ORDER BY n.nspname, c.relname;
        """
        result = self.query(db_name=db_name, sql=sql)
        for schema_name, table_name, table_comment in result.rows:
            display_name = self._display_object_name(schema_name, table_name)
            data.setdefault(display_name[0], []).append(
                [display_name, (table_comment or "")[:80]]
            )
        return data

    def get_tables_metas_data(self, db_name, **kwargs):
        """All table metadata for the data dictionary export."""
        tables = []
        for group_tables in self.get_group_tables_by_db(db_name=db_name).values():
            for table_name, table_comment in group_tables:
                tables.append((table_name, table_comment))
        engine_keys = [
            {"key": "COLUMN_NAME", "value": "字段名"},
            {"key": "COLUMN_TYPE", "value": "数据类型"},
            {"key": "COLUMN_DEFAULT", "value": "默认值"},
            {"key": "IS_NULLABLE", "value": "允许非空"},
            {"key": "COLUMN_KEY", "value": "是否主键"},
            {"key": "COLUMN_COMMENT", "value": "备注"},
        ]
        table_metas = []
        for table_name, table_comment in tables:
            desc = self.get_table_desc_data(db_name=db_name, tb_name=table_name)
            columns = []
            for row in desc["rows"]:
                columns.append(
                    {
                        "COLUMN_NAME": row[0],
                        "COLUMN_TYPE": row[1],
                        "COLUMN_DEFAULT": row[5],
                        "IS_NULLABLE": row[3],
                        "COLUMN_KEY": row[4],
                        "COLUMN_COMMENT": row[7],
                    }
                )
            table_metas.append(
                {
                    "ENGINE_KEYS": engine_keys,
                    "TABLE_INFO": {
                        "TABLE_NAME": table_name,
                        "TABLE_COMMENT": table_comment,
                    },
                    "COLUMNS": tuple(columns),
                }
            )
        return table_metas

    def show_create_table(
        self, db_name=None, table_name="", schema_name=None, close_conn=True
    ):
        """Return a readable CREATE TABLE statement for the query page shortcut."""
        result_set = ResultSet(full_sql=f"show create table {table_name}")
        schema_name, clean_name = self._split_table_name(table_name, schema_name)
        sql = """
            SELECT column_name, data_type, character_maximum_length,
                   numeric_precision, numeric_scale, is_nullable, column_default,
                   udt_name, is_identity, identity_generation, is_generated,
                   generation_expression
            FROM information_schema.columns
            WHERE table_schema = %(schema_name)s AND table_name = %(table_name)s
            ORDER BY ordinal_position;
        """
        columns = self.query(
            db_name=db_name,
            sql=sql,
            close_conn=False,
            parameters={"schema_name": schema_name, "table_name": clean_name},
        )
        if columns.error:
            result_set.error = columns.error
            if close_conn:
                self.close()
            return result_set
        if not columns.rows:
            result_set.error = f"表 {schema_name}.{clean_name} 不存在"
            if close_conn:
                self.close()
            return result_set

        defs = []
        for row in columns.rows:
            col_name, data_type, char_len, num_prec, num_scale = row[:5]
            is_nullable = row[5] if len(row) > 5 else "YES"
            default = row[6] if len(row) > 6 else None
            udt_name = row[7] if len(row) > 7 else ""
            is_identity = row[8] if len(row) > 8 else "NO"
            identity_generation = row[9] if len(row) > 9 else ""
            is_generated = row[10] if len(row) > 10 else "NO"
            generation_expression = row[11] if len(row) > 11 else ""
            col_type = self._format_column_type(
                data_type, char_len, num_prec, num_scale, udt_name
            )
            line = f'    "{col_name}" {col_type}'
            if str(is_identity).upper() == "YES":
                # KES reports ALWAYS / BY DEFAULT in identity_generation.
                identity_mode = str(identity_generation or "ALWAYS").upper()
                if identity_mode not in ("ALWAYS", "BY DEFAULT"):
                    identity_mode = "ALWAYS"
                line += f" GENERATED {identity_mode} AS IDENTITY"
            elif str(is_generated).upper() == "YES":
                expression = (generation_expression or "").strip()
                # KES may already return the expression wrapped in parentheses.
                if not (expression.startswith("(") and expression.endswith(")")):
                    expression = f"({expression})"
                line += f" GENERATED ALWAYS AS {expression} STORED"
            elif default:
                line += f" DEFAULT {default}"
            if is_nullable == "NO":
                line += " NOT NULL"
            defs.append(line)

        # Append constraints (PK / UNIQUE / FK / CHECK) and secondary indexes
        # so the copied DDL reproduces the whole structure, not just columns.
        constraint_sql = """
            SELECT contype, pg_get_constraintdef(c.oid)
            FROM sys_catalog.sys_constraint c
            JOIN sys_catalog.sys_class t ON t.oid = c.conrelid
            JOIN sys_catalog.sys_namespace n ON n.oid = t.relnamespace
            WHERE t.relname = %(tb_name)s AND n.nspname = %(schema_name)s
              AND c.contype IN ('p', 'u', 'f', 'c')
              AND c.conname NOT LIKE '%%_not_null'
            ORDER BY c.contype, c.conname;
        """
        constraints = self.query(
            db_name=db_name,
            sql=constraint_sql,
            close_conn=False,
            parameters={"schema_name": schema_name, "tb_name": clean_name},
        )
        if not constraints.error:
            for _contype, definition in constraints.rows:
                if definition:
                    # pg_get_constraintdef already returns e.g.
                    # "PRIMARY KEY (id)" / "FOREIGN KEY (..) REFERENCES ..".
                    defs.append(f"    {definition}")

        index_sql = """
            SELECT i.relname, pg_get_indexdef(x.indexrelid)
            FROM sys_catalog.sys_index x
            JOIN sys_catalog.sys_class t ON t.oid = x.indrelid
            JOIN sys_catalog.sys_class i ON i.oid = x.indexrelid
            JOIN sys_catalog.sys_namespace n ON n.oid = t.relnamespace
            WHERE t.relname = %(tb_name)s AND n.nspname = %(schema_name)s
              AND NOT x.indisprimary AND NOT x.indisunique
            ORDER BY i.relname;
        """
        indexes = self.query(
            db_name=db_name,
            sql=index_sql,
            close_conn=False,
            parameters={"schema_name": schema_name, "tb_name": clean_name},
        )
        index_defs = []
        if not indexes.error:
            for _name, definition in indexes.rows:
                if definition:
                    index_defs.append(definition + ";")

        create_sql = (
            f'CREATE TABLE "{schema_name}"."{clean_name}" (\n'
            + ",\n".join(defs)
            + "\n);"
        )
        if index_defs:
            create_sql += "\n" + "\n".join(index_defs)

        result_set.column_list = ["Table", "Create Table"]
        result_set.rows = [(clean_name, create_sql)]
        result_set.affected_rows = 1
        if close_conn:
            self.close()
        return result_set

    def get_table_index_data(self, db_name, tb_name, **kwargs):
        """Index metadata using KES sys_catalog.sys_index + sys_catalog.sys_class."""
        schema_name, tb_name = self._split_table_name(
            tb_name, kwargs.get("schema_name")
        )
        sql = """
            SELECT
                i.relname AS 索引名,
                CASE WHEN x.indisunique THEN 'YES' ELSE 'NO' END AS 唯一,
                a.attname AS 列名,
                x.indisprimary AS 主键
            FROM sys_catalog.sys_index x
            JOIN sys_catalog.sys_class c ON c.oid = x.indrelid
            JOIN sys_catalog.sys_class i ON i.oid = x.indexrelid
            JOIN sys_catalog.sys_namespace n ON n.oid = c.relnamespace
            LEFT JOIN sys_catalog.sys_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(x.indkey)
            WHERE c.relname = %(tb_name)s AND n.nspname = %(schema_name)s
            ORDER BY i.relname, a.attnum;
        """
        result = self.query(
            db_name=db_name,
            sql=sql,
            parameters={"schema_name": schema_name, "tb_name": tb_name},
        )
        return {"rows": result.rows, "column_list": result.column_list}

    def get_views_list(self, db_name, **kwargs):
        """Group views by first character, for the data dictionary tree."""
        data = {}
        sql = f"""
            SELECT n.nspname AS table_schema,
                   c.relname AS table_name,
                   obj_description(c.oid) AS table_comment
            FROM sys_catalog.sys_class c
            JOIN sys_catalog.sys_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'v'
              AND n.nspname NOT IN {_SYSTEM_SCHEMA_SQL}
            ORDER BY n.nspname, c.relname;
        """
        result = self.query(db_name=db_name, sql=sql)
        for schema_name, view_name, view_comment in result.rows:
            display_name = self._display_object_name(schema_name, view_name)
            data.setdefault(display_name[0], []).append(
                [display_name, (view_comment or "")[:80]]
            )
        return data

    def get_view_detail(self, db_name, view_name, **kwargs):
        """View metadata for the data dictionary detail modal.

        Returns the same payload shape as the other dictionary engines:
        meta_data (one row keyed by column names), desc (columns) and
        view_definition (the SQL text the modal renders).
        """
        schema_name, clean_view_name = self._split_table_name(
            view_name, kwargs.get("schema_name")
        )
        sql = """
            SELECT c.relname AS view_name,
                   sys_get_viewdef(c.oid, true) AS view_definition,
                   '' AS check_option,
                   CASE WHEN c.relkind = 'v' THEN 'YES' ELSE 'NO' END AS is_updatable,
                   pg_get_userbyid(c.relowner) AS definer,
                   '' AS security_type,
                   '' AS character_set_client,
                   '' AS collation_connection
            FROM sys_catalog.sys_class c
            JOIN sys_catalog.sys_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = %(view_name)s AND n.nspname = %(schema_name)s;
        """
        meta = self.query(
            db_name=db_name,
            sql=sql,
            parameters={"schema_name": schema_name, "view_name": clean_view_name},
        )
        return {
            "meta_data": {
                "column_list": meta.column_list,
                "rows": meta.rows[0] if meta.rows else (),
            },
            "desc": self.get_table_desc_data(
                db_name=db_name,
                tb_name=clean_view_name,
                schema_name=schema_name,
            ),
            "view_definition": meta.rows[0][1] if meta.rows else "",
        }

    # ------------------------------------------------------------------
    # Triggers / procedures / functions (data dictionary)
    # ------------------------------------------------------------------
    def get_triggers_list(self, db_name, **kwargs):
        """Trigger list from information_schema.triggers."""
        data = {}
        sql = f"""
            SELECT trigger_schema,
                   trigger_name,
                   action_timing || ' ' || event_manipulation || ' ON ' || event_object_table AS description
            FROM information_schema.triggers
            WHERE trigger_schema NOT IN {_SYSTEM_SCHEMA_SQL}
            ORDER BY trigger_schema, trigger_name;
        """
        result = self.query(db_name=db_name, sql=sql)
        for schema_name, trigger_name, description in result.rows:
            display_name = self._display_object_name(schema_name, trigger_name)
            data.setdefault(display_name[0], []).append([display_name, description])
        return data

    def get_trigger_detail(self, db_name, trigger_name, **kwargs):
        """Trigger definition using sys_get_triggerdef."""
        schema_name, clean_name = self._split_table_name(
            trigger_name, kwargs.get("schema_name")
        )
        # The detail modal reads flat English aliases (trigger_name,
        # action_statement, ...), matching the information_schema shape.
        sql = """
            SELECT trigger_name,
                   action_timing,
                   event_manipulation,
                   event_object_table,
                   action_orientation,
                   action_statement,
                   '' AS definer,
                   null AS created,
                   '' AS sql_mode,
                   '' AS character_set_client,
                   '' AS collation_connection
            FROM information_schema.triggers
            WHERE trigger_schema = %(schema_name)s
              AND trigger_name = %(trigger_name)s;
        """
        result = self.query(
            db_name=db_name,
            sql=sql,
            parameters={"schema_name": schema_name, "trigger_name": clean_name},
        )
        return {
            "rows": result.rows[0] if result.rows else (),
            "column_list": result.column_list,
        }

    def _get_routines_list(self, db_name, routine_type):
        data = {}
        # Include the argument signature so overloaded routines remain distinct
        # in the dictionary tree and the detail modal can address one of them.
        sql = f"""
            SELECT n.nspname, p.proname,
                   pg_get_function_identity_arguments(p.oid) AS args
            FROM sys_catalog.sys_proc p
            JOIN sys_catalog.sys_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname NOT IN {_SYSTEM_SCHEMA_SQL}
              AND p.prokind = %(prokind)s
            ORDER BY n.nspname, p.proname, args;
        """
        result = self.query(
            db_name=db_name,
            sql=sql,
            parameters={"prokind": "p" if routine_type == "PROCEDURE" else "f"},
        )
        for schema_name, routine_name, args in result.rows:
            display_name = self._display_object_name(
                schema_name, f"{routine_name}({args})"
            )
            data.setdefault(display_name[0], []).append([display_name, ""])
        return data

    def _get_routine_detail(self, db_name, routine_name, routine_type, **kwargs):
        schema_name, clean_name = self._split_table_name(
            routine_name, kwargs.get("schema_name")
        )
        # The list exposes "name(arg1, arg2)" to disambiguate overloads. Parse
        # it back to the bare name and the identity argument signature.
        bare_name, args = clean_name, None
        match = re.match(r"^([^()]+)\((.*)\)$", clean_name, re.S)
        if match:
            bare_name, args = match.group(1).strip(), match.group(2).strip()
        arg_clause = ""
        params = {
            "schema_name": schema_name,
            "routine_name": bare_name,
            "routine_type": routine_type,
            "prokind": "p" if routine_type == "PROCEDURE" else "f",
        }
        if args:
            arg_clause = "AND pg_get_function_identity_arguments(p.oid) = %(args)s"
            params["args"] = args

        meta_sql = """
            SELECT routine_name,
                   routine_schema,
                   data_type AS return_type,
                   '' AS definer,
                   null AS created,
                   null AS last_altered,
                   '' AS sql_mode,
                   security_type,
                   '' AS routine_comment
            FROM information_schema.routines
            WHERE routine_schema = %(schema_name)s
              AND routine_name = %(routine_name)s
              AND routine_type = %(routine_type)s;
        """
        meta = self.query(
            db_name=db_name,
            sql=meta_sql,
            close_conn=False,
            parameters={
                "schema_name": schema_name,
                "routine_name": bare_name,
                "routine_type": routine_type,
            },
        )
        create_sql = f"""
            SELECT sys_get_functiondef(p.oid) AS definition
            FROM sys_catalog.sys_proc p
            JOIN sys_catalog.sys_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = %(schema_name)s
              AND p.proname = %(routine_name)s
              AND p.prokind = %(prokind)s
              {arg_clause};
        """
        create = self.query(db_name=db_name, sql=create_sql, parameters=params)
        return {
            "meta_data": {
                "column_list": meta.column_list,
                "rows": meta.rows[0] if meta.rows else (),
            },
            "create_sql": create.rows,
        }

    def get_procedures_list(self, db_name, **kwargs):
        return self._get_routines_list(db_name=db_name, routine_type="PROCEDURE")

    def get_procedure_detail(self, db_name, proc_name, **kwargs):
        return self._get_routine_detail(
            db_name=db_name, routine_name=proc_name, routine_type="PROCEDURE"
        )

    def get_functions_list(self, db_name, **kwargs):
        return self._get_routines_list(db_name=db_name, routine_type="FUNCTION")

    def get_function_detail(self, db_name, func_name, **kwargs):
        return self._get_routine_detail(
            db_name=db_name, routine_name=func_name, routine_type="FUNCTION"
        )

    # ------------------------------------------------------------------
    # Database management
    # ------------------------------------------------------------------
    def get_all_databases_summary(self):
        """Database summary for the instance database management page."""
        sql = """
            SELECT datname AS db_name,
                   sys_encoding_to_char(encoding) AS charset,
                   datcollate AS collation
            FROM sys_catalog.sys_database
            WHERE datname NOT IN ('template0', 'template1', 'information_schema');
        """
        result = self.query(sql=sql)
        if not result.error and result.rows and result.column_list:
            cols = result.column_list
            rows = []
            for row in result.rows:
                d = dict(zip(cols, row))
                d["grantees"] = []
                d["saved"] = False
                rows.append(d)
            result.rows = rows
        return result

    def get_instance_users_summary(self):
        """Account listing using sys_catalog.sys_user."""
        sql = """
            SELECT usename AS "user",
                   '%' AS host,
                   usename || '@%' AS user_host,
                   usesysid AS user_id,
                   usecreatedb AS can_create_db,
                   usesuper AS is_superuser,
                   CASE
                       WHEN valuntil IS NOT NULL AND valuntil <= now() THEN '已锁定'
                       ELSE ''
                   END AS is_locked,
                   valuntil AS expiry_time
            FROM sys_catalog.sys_user
            ORDER BY usename;
        """
        result = self.query(sql=sql)
        if not result.error and result.rows and result.column_list:
            cols = result.column_list
            result.rows = [dict(zip(cols, row)) for row in result.rows]
            for row in result.rows:
                row["saved"] = False
        return result

    # ------------------------------------------------------------------
    # Account management (write operations)
    # ------------------------------------------------------------------
    @staticmethod
    def _quote_ident(name):
        """Quote an identifier for KES, rejecting obviously unsafe input."""
        value = str(name or "").strip()
        if not re.match(r"^[A-Za-z_\u4e00-\u9fa5][A-Za-z0-9_$\u4e00-\u9fa5]*$", value):
            raise ValueError(f"非法的账号名: {name}")
        return f'"{value}"'

    @staticmethod
    def _quote_pwd(password):
        return "'" + str(password).replace("'", "''") + "'"

    @staticmethod
    def _format_column_type(data_type, char_length, num_prec, num_scale, udt_name=None):
        """Format a column type, resolving USER-DEFINED / ARRAY markers."""
        if (
            data_type in ("character varying", "character", "varchar", "char")
            and char_length
        ):
            return f"{data_type}({char_length})"
        if data_type in ("numeric", "decimal") and num_prec is not None:
            if num_scale is not None:
                return f"{data_type}({num_prec},{num_scale})"
            return f"{data_type}({num_prec})"
        if data_type == "USER-DEFINED" and udt_name:
            return udt_name
        if data_type == "ARRAY" and udt_name:
            # KES reports array udt_name as '_int4', '_varchar', etc.
            return f"{udt_name.lstrip('_')}[]"
        return data_type

    # CREATE/ALTER USER carry the password inline, so the statement must never
    # reach a log file verbatim. Matches both plain and <<>>-quoted forms.
    _PWD_IN_SQL_RE = re.compile(r"(PASSWORD\s+)(?:<<[^>]*>>|'(?:[^']|'')*')", re.I)

    @classmethod
    def _mask_pwd_in_sql(cls, sql):
        """Replace an inline password literal before logging the statement."""
        return cls._PWD_IN_SQL_RE.sub(r"\1'******'", str(sql or ""))

    def create_instance_user(self, **kwargs):
        """Create a KES account via CREATE USER."""
        user = kwargs.get("user", "")
        password1 = kwargs.get("password1", "")
        remark = kwargs.get("remark", "")
        result = ResultSet()
        try:
            account = self._quote_ident(user)
            if not password1:
                raise ValueError("密码不能为空")
            exists = self.query(
                sql="SELECT 1 FROM sys_catalog.sys_user WHERE usename = %(user)s;",
                parameters={"user": user},
            )
            if exists.error:
                return exists
            if exists.rows:
                raise ValueError(f"账号 {user} 已存在")
            sql = f"CREATE USER {account} PASSWORD {self._quote_pwd(password1)}"
            exec_result = self.execute(db_name=self.db_name or KES_DEFAULT_DB, sql=sql)
            if exec_result.error:
                return exec_result
            result.rows = [
                {
                    "instance": self.instance,
                    "user": user,
                    "host": "%",
                    "password": password1,
                    "remark": remark,
                }
            ]
            result.affected_rows = 1
        except ValueError as e:
            result.error = str(e)
        return result

    def drop_instance_user(self, **kwargs):
        """Drop a KES account via DROP USER.

        Deliberately no DROP OWNED BY: in KES that drops every object the role
        owns along with its data, which is not what "delete account" means. If
        the role still owns objects, DROP USER fails and the error is surfaced
        so the operator can reassign ownership first.
        """
        user_host = kwargs.get("user_host", "")
        result = ResultSet()
        try:
            user = str(user_host).split("@")[0] if user_host else ""
            account = self._quote_ident(user)
            exec_result = self.execute(
                db_name=self.db_name or KES_DEFAULT_DB,
                sql=f"DROP USER IF EXISTS {account}",
            )
            if exec_result.error:
                return exec_result
            result.affected_rows = 1
        except ValueError as e:
            result.error = str(e)
        return result

    def reset_instance_user_pwd(self, **kwargs):
        """Reset a KES account password via ALTER USER."""
        user_host = kwargs.get("user_host", "")
        reset_pwd = kwargs.get("reset_pwd", "")
        result = ResultSet()
        try:
            user = str(user_host).split("@")[0] if user_host else ""
            account = self._quote_ident(user)
            if not reset_pwd:
                raise ValueError("密码不能为空")
            exec_result = self.execute(
                db_name=self.db_name or KES_DEFAULT_DB,
                sql=f"ALTER USER {account} PASSWORD {self._quote_pwd(reset_pwd)}",
            )
            if exec_result.error:
                return exec_result
            result.affected_rows = 1
        except ValueError as e:
            result.error = str(e)
        return result

    # ------------------------------------------------------------------
    # Monitoring (KES-native sys_stat_* views)
    # ------------------------------------------------------------------
    def processlist(self, command_type, **kwargs):
        """Session list using KES sys_catalog.sys_stat_activity."""
        command_type = self.escape_string(command_type)
        if not command_type:
            command_type = "Not Idle"
        idle_filter = "AND psa.state <> 'idle'" if command_type == "Not Idle" else ""
        sql = f"""
            SELECT
                psa.pid,
                psa.datname,
                psa.usename,
                psa.application_name,
                psa.state,
                psa.client_addr::text AS client_addr,
                psa.client_port,
                psa.wait_event_type,
                psa.wait_event,
                psa.query_start,
                psa.backend_start,
                psa.xact_start,
                psa.state_change,
                psa.query,
                ROUND(GREATEST(EXTRACT(EPOCH FROM (now() - psa.query_start)), 0)::numeric, 4) AS elapsed_time_seconds
            FROM sys_catalog.sys_stat_activity psa
            WHERE psa.pid <> sys_backend_pid()
              {idle_filter}
            ORDER BY
                CASE WHEN psa.state = 'active' THEN 10
                     WHEN psa.state LIKE 'idle in transaction%%' THEN 5
                     WHEN psa.state = 'idle' THEN 99 ELSE 100 END,
                elapsed_time_seconds DESC;
        """
        return self.query(sql=sql)

    def slowquery_review(
        self,
        start_time,
        end_time,
        db_name="",
        limit=30,
        offset=0,
        search="",
        sort_name="calls",
        sort_order="desc",
        **kwargs,
    ):
        """Slow query review using KES sys_stat_statements.

        sys_stat_statements is cumulative (no per-query timestamps), so this
        reports the current top statements by the requested sort key.
        """
        where = "WHERE 1=1"
        params = {}
        if search:
            where += " AND s.query ILIKE %(search)s"
            params["search"] = f"%{search}%"
        if db_name:
            # sys_stat_statements carries dbid, not a database name.
            where += " AND d.datname = %(db_name)s"
            params["db_name"] = db_name
        sort_map = {
            "calls": "calls",
            "MySQLTotalExecutionCounts": "calls",
            "total_exec_time": "total_exec_time",
            "MySQLTotalExecutionTimes": "total_exec_time",
            "mean_exec_time": "mean_exec_time",
            "QueryTimeAvg": "mean_exec_time",
            "CreateTime": "CreateTime",
            "DBName": "DBName",
            "ParseTotalRowCounts": "ParseTotalRowCounts",
            "ParseRowAvg": "ParseRowAvg",
            "ReturnTotalRowCounts": "ReturnTotalRowCounts",
            "ReturnRowAvg": "ReturnRowAvg",
        }
        order_by = f'"{sort_map.get(sort_name, "mean_exec_time")}"'
        order = "ASC" if str(sort_order).lower() == "asc" else "DESC"
        params.update({"limit": limit, "offset": offset})
        # Aliases match the slow-query table columns; values KES cannot supply
        # (per-execution timestamps / percentiles) are filled from aggregates.
        sql = f"""
            SELECT
                now() AS "CreateTime",
                COALESCE(d.datname, '') AS "DBName",
                queryid::text AS "SQLId",
                left(s.query, 500) AS "SQLText",
                s.calls AS "MySQLTotalExecutionCounts",
                -- sys_stat_statements reports milliseconds; the UI labels
                -- these aliases as seconds.
                round((s.total_exec_time / 1000.0)::numeric, 6) AS "MySQLTotalExecutionTimes",
                round((s.mean_exec_time / 1000.0)::numeric, 6) AS "QueryTimeAvg",
                round((s.mean_exec_time / 1000.0)::numeric, 6) AS "DurationPct95",
                s.rows AS "ParseTotalRowCounts",
                s.rows AS "ReturnTotalRowCounts",
                CASE WHEN s.calls > 0
                     THEN round((s.rows::numeric / s.calls), 3) ELSE 0 END AS "ParseRowAvg",
                CASE WHEN s.calls > 0
                     THEN round((s.rows::numeric / s.calls), 3) ELSE 0 END AS "ReturnRowAvg"
            FROM sys_stat_statements s
            LEFT JOIN sys_catalog.sys_database d ON d.oid = s.dbid
            {where}
            ORDER BY {order_by} {order}
            OFFSET %(offset)s LIMIT %(limit)s;
        """
        count_sql = f"""
            SELECT count(*)
            FROM sys_stat_statements s
            LEFT JOIN sys_catalog.sys_database d ON d.oid = s.dbid
            {where};
        """
        rows_result = self.query(sql=sql, close_conn=False, parameters=params)
        if rows_result.error:
            self.close()
            return {"total": 0, "rows": [], "error": rows_result.error}
        count_result = self.query(sql=count_sql, parameters=params)
        if count_result.error:
            self.close()
            return {"total": 0, "rows": [], "error": count_result.error}
        total = count_result.rows[0][0] if count_result.rows else 0
        return {"total": total, "rows": rows_result.to_dict()}

    def slowquery_review_history(
        self,
        start_time,
        end_time,
        db_name=None,
        sql_id="",
        limit=30,
        offset=0,
        search="",
        sort_name="ParseRowCounts",
        sort_order="desc",
        **kwargs,
    ):
        """Slow-query detail rows, in the shape the slow-log detail page expects.

        KES keeps only the cumulative sys_stat_statements view -- there is no
        statement-history table with per-execution timestamps -- so each row is
        a current snapshot of one statement and start_time/end_time are not
        applied as a range filter. When sql_id is given (the user drilled into
        one row) the result is narrowed to that statement.
        """
        # Sort on the output aliases (quoted) so the ORDER BY never references
        # a base-table column that may not exist.
        sort_map = {
            "ExecutionStartTime": "ExecutionStartTime",
            "DBName": "DBName",
            "SQLText": "SQLText",
            "TotalExecutionCounts": "TotalExecutionCounts",
            "QueryTimes": "QueryTimes",
            "ReturnRowCounts": "ReturnRowCounts",
            "ParseRowCounts": "ParseRowCounts",
            "calls": "TotalExecutionCounts",
        }
        order_by = f'"{sort_map.get(sort_name, "ParseRowCounts")}"'
        order = "ASC" if str(sort_order).lower() == "asc" else "DESC"

        where = "WHERE 1=1"
        params = {}
        if db_name:
            where += " AND d.datname = %(db_name)s"
            params["db_name"] = db_name
        if search:
            where += " AND s.query ILIKE %(search)s"
            params["search"] = f"%{search}%"
        if sql_id:
            # queryid is bigint in KES; filter textually to avoid overflow on
            # identifiers that do not look numeric.
            where += " AND s.queryid::text = %(sql_id)s"
            params["sql_id"] = str(sql_id)
        params.update({"limit": limit, "offset": offset})

        sql = f"""
            SELECT
                now() AS "ExecutionStartTime",
                COALESCE(d.datname, '') AS "DBName",
                '' || COALESCE(s.userid::text, '') AS "HostAddress",
                COALESCE(s.query, '') AS "SQLText",
                s.calls AS "TotalExecutionCounts",
                0 AS "QueryTimePct95",
                round((s.total_exec_time / 1000.0)::numeric, 6) AS "QueryTimes",
                0 AS "LockTimes",
                s.rows AS "ParseRowCounts",
                s.rows AS "ReturnRowCounts",
                s.queryid::text AS "SQLId"
            FROM sys_stat_statements s
            LEFT JOIN sys_catalog.sys_database d ON d.oid = s.dbid
            {where}
            ORDER BY {order_by} {order}
            OFFSET %(offset)s LIMIT %(limit)s;
        """
        count_sql = f"""
            SELECT count(*)
            FROM sys_stat_statements s
            LEFT JOIN sys_catalog.sys_database d ON d.oid = s.dbid
            {where};
        """
        rows_result = self.query(sql=sql, close_conn=False, parameters=params)
        if rows_result.error:
            self.close()
            return {"total": 0, "rows": [], "error": rows_result.error}
        count_result = self.query(sql=count_sql, parameters=params)
        if count_result.error:
            self.close()
            return {"total": 0, "rows": [], "error": count_result.error}
        total = count_result.rows[0][0] if count_result.rows else 0
        return {"total": total, "rows": rows_result.to_dict()}

    # ------------------------------------------------------------------
    # Variables (KES sys_catalog.sys_settings)
    # ------------------------------------------------------------------
    def get_variables(self, variables=None):
        """Instance parameters from the KES sys_catalog.sys_settings system view."""
        sql = (
            "SELECT name, setting, unit, context, vartype, short_desc "
            "FROM sys_catalog.sys_settings"
        )
        params = None
        if variables:
            sql += " WHERE name = ANY(%(variables)s)"
            params = {"variables": variables}
        sql += " ORDER BY name;"
        return self.query(sql=sql, parameters=params)

    def set_variable(self, variable_name, variable_value):
        """Modify an instance parameter via ALTER SYSTEM + sys_reload_conf."""
        result = ResultSet(
            full_sql=f"ALTER SYSTEM SET {variable_name} = {variable_value}"
        )
        conn = self.get_connection()
        try:
            conn.autocommit = True
            with conn.cursor() as cursor:
                cursor.execute(
                    f'ALTER SYSTEM SET "{variable_name}" = %s;', (variable_value,)
                )
                cursor.execute("SELECT sys_reload_conf();")
            result.affected_rows = 1
        except Exception:
            conn.rollback()
            logger.warning(f"KingbaseES set_variable error: {traceback.format_exc()}")
            result.error = traceback.format_exc()
        finally:
            self.close()
        return result

    def kill_connection(self, thread_id):
        """Terminate a session using KES sys_terminate_backend."""
        if not str(thread_id).isdigit():
            rs = ResultSet()
            rs.error = "thread_id must be an integer"
            return rs
        return self.query(sql=f"SELECT sys_terminate_backend({int(thread_id)});")

    def get_kill_command(self, thread_ids, thread_ids_check=True):
        """Build the kill statement list for the selected session ids."""
        ids = [int(t) for t in (thread_ids or []) if str(t).isdigit()]
        if not ids:
            return []
        placeholders = ",".join(["%s"] * len(ids))
        sql = (
            "SELECT 'SELECT sys_terminate_backend(' || pid || ');' "
            f"FROM sys_catalog.sys_stat_activity WHERE pid IN ({placeholders}) ORDER BY pid;"
        )
        result = self.query(sql=sql, parameters=tuple(ids))
        if result.error:
            return []
        return [row[0] for row in result.rows]

    def kill(self, thread_ids):
        """Terminate multiple sessions (Archery db_diagnostic interface)."""
        ids = [int(t) for t in thread_ids if str(t).isdigit()]
        if not ids:
            rs = ResultSet()
            rs.error = "no valid thread ids"
            return rs
        return self.query(
            sql="SELECT sys_terminate_backend(pid) FROM sys_catalog.sys_stat_activity "
            "WHERE pid = ANY(%s);",
            parameters=(ids,),
        )

    # ------------------------------------------------------------------
    # Diagnostics: tablespace / locks / long transactions
    # ------------------------------------------------------------------
    def tablespace(self, offset=0, row_count=14, schema_search=""):
        """Table size ranking using KES sys_catalog catalogs."""
        search_condition = ""
        parameters = {"offset": offset, "row_count": row_count}
        if schema_search:
            search_condition = """
                AND (n.nspname LIKE %(schema_search)s OR c.relname LIKE %(schema_search)s)
            """
            parameters["schema_search"] = f"%{schema_search}%"
        sql = f"""
            SELECT
                n.nspname AS table_schema,
                c.relname AS table_name,
                CASE c.relkind
                    WHEN 'r' THEN 'table'
                    WHEN 'p' THEN 'partitioned table'
                    WHEN 'm' THEN 'materialized view'
                    ELSE c.relkind::text
                END AS engine,
                ROUND((sys_table_size(c.oid) + sys_indexes_size(c.oid)) / 1024.0 / 1024.0, 2) AS total_size,
                COALESCE(c.reltuples::bigint, 0) AS table_rows,
                ROUND(sys_table_size(c.oid) / 1024.0 / 1024.0, 2) AS data_size,
                ROUND(sys_indexes_size(c.oid) / 1024.0 / 1024.0, 2) AS index_size,
                0 AS data_free
            FROM sys_catalog.sys_class c
            JOIN sys_catalog.sys_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'p', 'm')
              AND n.nspname NOT IN {_SYSTEM_SCHEMA_SQL}
              {search_condition}
            ORDER BY total_size DESC
            OFFSET %(offset)s LIMIT %(row_count)s;
        """
        return self.query(sql=sql, parameters=parameters)

    def tablespace_count(self, schema_search=""):
        """Total number of tables counted by tablespace()."""
        search_condition = ""
        parameters = {}
        if schema_search:
            search_condition = """
                AND (n.nspname LIKE %(schema_search)s OR c.relname LIKE %(schema_search)s)
            """
            parameters["schema_search"] = f"%{schema_search}%"
        sql = f"""
            SELECT count(*)
            FROM sys_catalog.sys_class c
            JOIN sys_catalog.sys_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'p', 'm')
              AND n.nspname NOT IN {_SYSTEM_SCHEMA_SQL}
              {search_condition};
        """
        return self.query(sql=sql, parameters=parameters)

    def lock_info(self):
        """Lock wait tree using KES sys_locks + sys_stat_activity."""
        sql = """
            SELECT
                blocked.pid AS blocked_pid,
                blocked.usename AS blocked_user,
                blocked.datname AS blocked_database,
                blocked.query AS blocked_query,
                blocked.query_start AS blocked_query_start,
                blocking.pid AS blocking_pid,
                blocking.usename AS blocking_user,
                blocking.query AS blocking_query,
                blocking.query_start AS blocking_query_start,
                blocked_locks.locktype,
                blocked_locks.mode AS blocked_mode,
                blocking_locks.mode AS blocking_mode,
                blocked_locks.relation::regclass::text AS relation
            FROM sys_catalog.sys_locks blocked_locks
            JOIN sys_catalog.sys_stat_activity blocked ON blocked.pid = blocked_locks.pid
            JOIN sys_catalog.sys_locks blocking_locks
                ON blocking_locks.locktype = blocked_locks.locktype
                AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
                AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
                AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
                AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
                AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
                AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
                AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
                AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
                AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
                AND blocking_locks.pid <> blocked_locks.pid
            JOIN sys_catalog.sys_stat_activity blocking ON blocking.pid = blocking_locks.pid
            WHERE NOT blocked_locks.granted AND blocking_locks.granted
            ORDER BY blocked.query_start;
        """
        return self.query(sql=sql)

    def get_long_transaction(self):
        """Long-running transactions using KES sys_stat_activity."""
        sql = """
            SELECT
                xact_start AS trx_started,
                now() - xact_start AS trx_idle_time,
                state AS trx_state,
                usename AS "user",
                client_addr::text AS host,
                datname AS db,
                pid AS trx_mysql_thread_id,
                '' AS trx_operation_state,
                0 AS trx_tables_locked,
                0 AS trx_rows_locked,
                0 AS trx_rows_modified,
                '' AS trx_is_read_only,
                '' AS trx_isolation_level,
                ROUND(GREATEST(EXTRACT(EPOCH FROM now() - xact_start), 0)::numeric, 4) AS thread_time,
                query AS info
            FROM sys_catalog.sys_stat_activity
            WHERE xact_start IS NOT NULL
              AND pid <> sys_backend_pid()
            ORDER BY xact_start;
        """
        return self.query(sql=sql)
