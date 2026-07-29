# -*- coding: UTF-8 -*-
"""
GaussDB/openGauss engine.

GaussDB for openGauss is compatible with the PostgreSQL wire protocol, so this
engine reuses PgSQL behavior and keeps a separate db_type for product
configuration, UI grouping, permission checks and future dialect differences.
"""

import re
import logging
import sqlparse

logger = logging.getLogger("default")

from .models import ResultSet
from .pgsql import PgSQLEngine


class GaussDBEngine(PgSQLEngine):
    test_query = "SELECT 1"

    name = "GaussDB"
    info = "GaussDB/openGauss engine"

    # Statements that must not appear inside an Archery-managed transaction
    _REJECT_STMT_RE = re.compile(
        r"^\s*(commit|rollback|begin|start\s+transaction|set\s+transaction)\b",
        re.I,
    )

    def get_connection(self, db_name=None):
        db_name = db_name or self.db_name or "postgres"
        return super().get_connection(db_name=db_name)

    def query(
        self,
        db_name=None,
        sql="",
        limit_num=0,
        close_conn=True,
        parameters=None,
        **kwargs,
    ):
        show_create_match = re.match(
            r'^\s*show\s+create\s+table\s+("?[\w.]+"?)\s*;?\s*$', sql, re.I
        )
        if show_create_match:
            return self.show_create_table(
                db_name=db_name,
                table_name=show_create_match.group(1),
                schema_name=kwargs.get("schema_name"),
                close_conn=close_conn,
            )
        # GaussDB PBE 机制会拦截 explain 语句，返回参数化信息而非执行计划。
        # 使用 PREPARE + EXPLAIN EXECUTE 绕过。
        # Only intercept bare EXPLAIN (no ANALYZE, FORMAT, etc.) to avoid
        # breaking EXPLAIN ANALYZE / EXPLAIN (FORMAT JSON) which GaussDB handles natively.
        explain_match = re.match(
            r"^\s*explain\s+(select|with|insert|update|delete)\b", sql, re.I
        )
        if explain_match:
            inner_sql = (
                re.sub(r"^\s*explain\s+", "", sql, flags=re.I).rstrip(";").strip()
            )
            return self._explain_via_prepare(
                db_name=db_name,
                inner_sql=inner_sql,
                close_conn=close_conn,
                schema_name=kwargs.get("schema_name"),
                max_execution_time=kwargs.get("max_execution_time", 0),
            )
        return super().query(
            db_name=db_name,
            sql=sql,
            limit_num=limit_num,
            close_conn=close_conn,
            parameters=parameters,
            **kwargs,
        )

    def _explain_via_prepare(
        self,
        db_name=None,
        inner_sql="",
        close_conn=True,
        schema_name=None,
        max_execution_time=0,
    ):
        """通过 PREPARE + EXPLAIN EXECUTE 绕过 GaussDB PBE 机制获取执行计划。"""
        from sql.engines.models import ResultSet

        result_set = ResultSet(full_sql=f"explain {inner_sql};")
        conn = None
        try:
            conn = self.get_connection(db_name=db_name)
            conn.autocommit = True
            cursor = conn.cursor()
            if schema_name:
                from psycopg2 import sql as pg_sql

                cursor.execute(
                    pg_sql.SQL("SET search_path TO {};").format(
                        pg_sql.Identifier(schema_name)
                    )
                )
            if max_execution_time:
                try:
                    cursor.execute(
                        "SET statement_timeout TO %s;", (int(max_execution_time),)
                    )
                except Exception:
                    pass
            stmt_name = f"archery_explain_{id(inner_sql) & 0xffffff}"
            # PREPARE
            cursor.execute(f"PREPARE {stmt_name} AS {inner_sql};")
            # EXPLAIN EXECUTE
            cursor.execute(f"EXPLAIN EXECUTE {stmt_name};")
            rows = cursor.fetchall()
            fields = cursor.description
            result_set.column_list = [i[0] for i in fields] if fields else []
            result_set.rows = rows
            # DEALLOCATE
            try:
                cursor.execute(f"DEALLOCATE {stmt_name};")
            except Exception:
                pass
        except Exception as e:
            result_set.error = str(e)
        finally:
            if "cursor" in dir() and cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn and close_conn:
                conn.close()
        return result_set

    def get_all_databases_summary(self):
        """实例数据库管理功能，获取实例所有的数据库描述信息。"""
        sql = """
        SELECT datname AS db_name,
               pg_encoding_to_char(encoding) AS charset,
               datcollate AS collation
        FROM pg_database
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
        """获取 GaussDB 实例所有用户信息，返回 dict 格式的行。"""
        sql = """
        SELECT usename AS "user",
               '%' AS host,
               usename || '@%' AS user_host,
               usesysid AS user_id,
               usecreatedb AS can_create_db,
               usesuper AS is_superuser,
               valuntil AS expiry_time
        FROM pg_user
        ORDER BY usename;
        """
        result = self.query(sql=sql)
        if not result.error and result.rows and result.column_list:
            cols = result.column_list
            result.rows = [dict(zip(cols, row)) for row in result.rows]
            for row in result.rows:
                row["saved"] = False
        return result

    def query_check(self, db_name=None, sql=""):
        """查询语句检查，允许 show create table 和 WITH/CTE 语法。"""
        result = super().query_check(db_name=db_name, sql=sql)
        if result.get("bad_query"):
            if re.match(r"^\s*show\s+create\s+table\s+", sql, re.I):
                result["bad_query"] = False
                result["msg"] = ""
            elif re.match(r"^\s*with\b", sql, re.I):
                result["bad_query"] = False
                result["msg"] = ""
        return result

    def execute_check(self, db_name=None, sql=""):
        """Reject transaction-control statements that would break Archery's
        transaction management (e.g. explicit COMMIT/ROLLBACK in a workflow)."""
        result = super().execute_check(db_name=db_name, sql=sql)
        if not result.error_count:
            for row in result.rows:
                stmt = row.sql.strip() if hasattr(row, "sql") else ""
                if stmt and self._REJECT_STMT_RE.match(stmt):
                    row.stagestatus = "驳回不支持语句"
                    row.errorlevel = "Error"
                    row.errormessage = (
                        "事务控制语句(COMMIT/ROLLBACK/BEGIN)不允许在工单中执行"
                    )
                    result.error_count += 1
        return result

    @property
    def server_version(self):
        """Return server version tuple, accepting GaussDB/openGauss version text."""
        result = self.query(sql="select version();")
        if result.error or not result.rows:
            return tuple()

        version_text = str(result.rows[0][0])
        version = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", version_text)
        if not version:
            return tuple()

        major, minor, patch = version.groups()
        return int(major), int(minor), int(patch or 0)

    def describe_table(self, db_name, tb_name, **kwargs):
        """
        获取表结构信息.

        Avoid table_name::regclass so schema-qualified and mixed-case tables work
        more reliably on GaussDB/openGauss compatibility deployments.
        """
        schema_name = kwargs.get("schema_name") or "public"
        sql = """
            select
                col.column_name,
                col.data_type,
                col.character_maximum_length,
                col.numeric_precision,
                col.numeric_scale,
                col.is_nullable,
                col.column_default,
                des.description
            from information_schema.columns col
            left join pg_catalog.pg_class cls
                on cls.relname = col.table_name
                and cls.relnamespace = (
                    select oid from pg_catalog.pg_namespace where nspname = col.table_schema
                )
            left join pg_catalog.pg_namespace ns
                on ns.oid = cls.relnamespace
            left join pg_catalog.pg_description des
                on des.objoid = cls.oid
                and des.objsubid = col.ordinal_position
            where col.table_name = %(tb_name)s
                and col.table_schema = %(schema_name)s
            order by col.ordinal_position;
        """
        return self.query(
            db_name=db_name,
            schema_name=schema_name,
            sql=sql,
            parameters={"schema_name": schema_name, "tb_name": tb_name},
        )

    def show_create_table(
        self, db_name=None, table_name="", schema_name=None, close_conn=True
    ):
        """Return a readable CREATE TABLE statement for the query page shortcut."""
        result_set = ResultSet(full_sql=f"show create table {table_name}")
        schema_name, clean_table_name = self._split_table_name(table_name, schema_name)
        sql = """
            select
                col.column_name,
                col.data_type,
                col.character_maximum_length,
                col.numeric_precision,
                col.numeric_scale,
                col.is_nullable,
                col.column_default,
                col.udt_schema,
                col.udt_name
            from information_schema.columns col
            where col.table_schema = %(schema_name)s
                and col.table_name = %(table_name)s
            order by col.ordinal_position;
        """
        columns = super().query(
            db_name=db_name,
            sql=sql,
            close_conn=False,
            parameters={"schema_name": schema_name, "table_name": clean_table_name},
        )
        if columns.error:
            result_set.error = columns.error
            if close_conn:
                self.close()
            return result_set
        if not columns.rows:
            result_set.error = f"table {schema_name}.{clean_table_name} does not exist"
            if close_conn:
                self.close()
            return result_set

        pk_sql = """
            select
                con.conname,
                con.contype,
                pg_get_constraintdef(con.oid, true)
            from pg_constraint con
            join pg_class cls on cls.oid = con.conrelid
            join pg_namespace ns on ns.oid = cls.relnamespace
            where ns.nspname = %(schema_name)s
                and cls.relname = %(table_name)s
                and con.contype in ('p', 'u', 'c', 'f')
            order by
                case con.contype
                    when 'p' then 1
                    when 'u' then 2
                    when 'c' then 3
                    when 'f' then 4
                    else 5
                end,
                con.conname;
        """
        constraints = super().query(
            db_name=db_name,
            sql=pk_sql,
            close_conn=False,
            parameters={"schema_name": schema_name, "table_name": clean_table_name},
        )
        comment_sql = """
            select
                coalesce(obj_description(cls.oid), '') as table_comment,
                col.attname,
                coalesce(des.description, '') as column_comment
            from pg_class cls
            join pg_namespace ns on ns.oid = cls.relnamespace
            left join pg_attribute col
                on col.attrelid = cls.oid
                and col.attnum > 0
                and not col.attisdropped
            left join pg_description des
                on des.objoid = cls.oid
                and des.objsubid = col.attnum
            where ns.nspname = %(schema_name)s
                and cls.relname = %(table_name)s
            order by col.attnum;
        """
        comments = super().query(
            db_name=db_name,
            sql=comment_sql,
            close_conn=False,
            parameters={"schema_name": schema_name, "table_name": clean_table_name},
        )
        table_comment = ""
        column_comments = {}
        if comments.error:
            logger.warning(
                "Failed to query comments for %s.%s: %s",
                schema_name,
                clean_table_name,
                comments.error,
            )
        if not comments.error:
            for table_desc, column_name, column_desc in comments.rows:
                table_comment = table_comment or table_desc or ""
                if column_name and column_desc:
                    column_comments[column_name] = column_desc

        column_defs = []
        for row in columns.rows:
            (
                column_name,
                data_type,
                char_length,
                numeric_precision,
                numeric_scale,
                is_nullable,
                column_default,
                udt_schema,
                udt_name,
            ) = row
            column_type = self._format_column_type(
                data_type, char_length, numeric_precision, numeric_scale, udt_name
            )
            column_def = f"    {self._quote_identifier(column_name)} {column_type}"
            if column_default:
                column_def += f" DEFAULT {column_default}"
            if is_nullable == "NO":
                column_def += " NOT NULL"
            column_defs.append(column_def)
        if constraints.error:
            logger.warning(
                "Failed to query constraints for %s.%s: %s",
                schema_name,
                clean_table_name,
                constraints.error,
            )
        if not constraints.error:
            for constraint_name, constraint_type, constraint_def in constraints.rows:
                if constraint_type == "p":
                    column_defs.append(f"    {constraint_def}")
                else:
                    column_defs.append(
                        f"    CONSTRAINT {self._quote_identifier(constraint_name)} {constraint_def}"
                    )

        index_sql = """
            select indexdef
            from pg_indexes
            where schemaname = %(schema_name)s
                and tablename = %(table_name)s
                and indexname not in (
                    select con.conname
                    from pg_constraint con
                    join pg_class cls on cls.oid = con.conrelid
                    join pg_namespace ns on ns.oid = cls.relnamespace
                    where ns.nspname = %(schema_name)s
                        and cls.relname = %(table_name)s
                        and con.contype in ('p', 'u')
                )
            order by indexname;
        """
        indexes = super().query(
            db_name=db_name,
            sql=index_sql,
            close_conn=False,
            parameters={"schema_name": schema_name, "table_name": clean_table_name},
        )

        partition_sql = """
            select pg_get_partkeydef(cls.oid)
            from pg_class cls
            join pg_namespace ns on ns.oid = cls.relnamespace
            join pg_partitioned_table pt on pt.partrelid = cls.oid
            where ns.nspname = %(schema_name)s
                and cls.relname = %(table_name)s;
        """
        partitions = super().query(
            db_name=db_name,
            sql=partition_sql,
            close_conn=close_conn,
            parameters={"schema_name": schema_name, "table_name": clean_table_name},
        )

        create_sql = (
            f"CREATE TABLE {self._quote_identifier(schema_name)}."
            f"{self._quote_identifier(clean_table_name)} (\n"
            + ",\n".join(column_defs)
            + "\n)"
        )
        if not partitions.error and partitions.rows:
            partkey = partitions.rows[0][0]
            if partkey:
                create_sql += f"\nPARTITION BY {partkey}"
        create_sql += ";"
        if not indexes.error:
            for (indexdef,) in indexes.rows:
                if indexdef:
                    create_sql += f"\n{indexdef};"
        comment_sqls = []
        if table_comment:
            comment_sqls.append(
                "COMMENT ON TABLE {}.{} IS {};".format(
                    self._quote_identifier(schema_name),
                    self._quote_identifier(clean_table_name),
                    self._quote_literal(table_comment),
                )
            )
        for column_name, column_comment in column_comments.items():
            comment_sqls.append(
                "COMMENT ON COLUMN {}.{}.{} IS {};".format(
                    self._quote_identifier(schema_name),
                    self._quote_identifier(clean_table_name),
                    self._quote_identifier(column_name),
                    self._quote_literal(column_comment),
                )
            )
        if comment_sqls:
            create_sql += "\n" + "\n".join(comment_sqls)
        result_set.column_list = ["Table", "Create Table"]
        result_set.rows = [(clean_table_name, create_sql)]
        result_set.affected_rows = 1
        return result_set

    def processlist(self, command_type, **kwargs):
        sql = """
            select
                psa.pid as id,
                coalesce(blk.block_pids, '-') as block_pids,
                psa.datname,
                psa.usename,
                psa.application_name,
                psa.state,
                psa.client_addr::text as client_addr,
                round(GREATEST(EXTRACT(EPOCH FROM (now() - psa.query_start)),0)::numeric,4) as elapsed_time_seconds,
                GREATEST(now() - psa.query_start, INTERVAL '0 second') AS elapsed_time,
                psa.query as "query",
                '' as wait_event_type,
                psa.enqueue as wait_event,
                psa.query_start,
                psa.backend_start,
                psa.client_hostname,
                psa.client_port,
                psa.xact_start as transaction_start_time,
                psa.state_change,
                psa.query_id,
                psa.control_status
            from pg_stat_activity psa
            left join (
                select
                    blocked.pid,
                    string_agg(blocking.pid::text, ',' order by blocking.pid) as block_pids
                from pg_locks blocked
                join pg_locks blocking
                    on blocked.locktype = blocking.locktype
                    and blocked.database is not distinct from blocking.database
                    and blocked.relation is not distinct from blocking.relation
                    and blocked.page is not distinct from blocking.page
                    and blocked.tuple is not distinct from blocking.tuple
                    and blocked.virtualxid is not distinct from blocking.virtualxid
                    and blocked.transactionid is not distinct from blocking.transactionid
                    and blocked.classid is not distinct from blocking.classid
                    and blocked.objid is not distinct from blocking.objid
                    and blocked.objsubid is not distinct from blocking.objsubid
                    and blocked.pid <> blocking.pid
                where not blocked.granted
                    and blocking.granted
                group by blocked.pid
            ) blk on blk.pid = psa.pid
            where psa.pid <> pg_backend_pid()
            $state_not_idle$
            order by
                case
                    when psa.state = 'active' then 10
                    when psa.state like 'idle in transaction%' then 5
                    when psa.state = 'idle' then 99
                    else 100
                end,
                elapsed_time_seconds desc;
        """
        command_type = self.escape_string(command_type)
        if not command_type:
            command_type = "Not Idle"
        if command_type == "Not Idle":
            sql = sql.replace("$state_not_idle$", "and psa.state <> 'idle'")
        sql = sql.replace("$state_not_idle$", "")
        return super().query(db_name=self.db_name or "postgres", sql=sql)

    def get_kill_command(self, thread_ids):
        if not thread_ids:
            return ""
        safe_ids = []
        for thread_id in thread_ids:
            if not isinstance(thread_id, int):
                return None
            safe_ids.append(str(thread_id))
        return "select pg_terminate_backend(pid) from pg_stat_activity where pid in ({});".format(
            ",".join(safe_ids)
        )

    def kill(self, thread_ids):
        kill_sql = self.get_kill_command(thread_ids)
        if not kill_sql:
            return ResultSet(full_sql="")
        return super().query(db_name=self.db_name or "postgres", sql=kill_sql)

    def tablespace(self, offset=0, row_count=14, schema_search=""):
        search_condition = ""
        parameters = {"offset": offset, "row_count": row_count}
        if schema_search:
            search_condition = """
                and (
                    n.nspname like %(schema_search)s
                    or c.relname like %(schema_search)s
                )
            """
            parameters["schema_search"] = f"%{schema_search}%"
        sql = f"""
            select
                n.nspname as table_schema,
                c.relname as table_name,
                case c.relkind
                    when 'r' then 'table'
                    when 'p' then 'partitioned table'
                    when 'm' then 'materialized view'
                    else c.relkind::text
                end as engine,
                round((pg_table_size(c.oid) + pg_indexes_size(c.oid)) / 1024.0 / 1024.0, 2) as total_size,
                coalesce(c.reltuples::bigint, 0) as table_rows,
                round(pg_table_size(c.oid) / 1024.0 / 1024.0, 2) as data_size,
                round(pg_indexes_size(c.oid) / 1024.0 / 1024.0, 2) as index_size,
                0 as data_free,
                0 as pct_free
            from pg_class c
            join pg_namespace n on n.oid = c.relnamespace
            where c.relkind in ('r', 'p', 'm')
                and n.nspname not in ('pg_catalog', 'information_schema')
                and n.nspname not in ('sys', 'dbe_perf', 'db4ai', 'dbe_pldeveloper')
                and n.nspname not like 'dbe_%%'
                and n.nspname not like 'pkg_%%'
                and n.nspname not like 'prvt_%%'
                and n.nspname not like 'pg_toast%%'
                and n.nspname not like 'pg_temp%%'
                and has_schema_privilege(n.oid, 'USAGE')
                and has_table_privilege(c.oid, 'SELECT')
                {search_condition}
            order by total_size desc
            offset %(offset)s limit %(row_count)s;
        """
        return super().query(
            db_name=self.db_name or "postgres", sql=sql, parameters=parameters
        )

    def tablespace_count(self, schema_search=""):
        search_condition = ""
        parameters = {}
        if schema_search:
            search_condition = """
                and (
                    n.nspname like %(schema_search)s
                    or c.relname like %(schema_search)s
                )
            """
            parameters["schema_search"] = f"%{schema_search}%"
        sql = f"""
            select count(*)
            from pg_class c
            join pg_namespace n on n.oid = c.relnamespace
            where c.relkind in ('r', 'p', 'm')
                and n.nspname not in ('pg_catalog', 'information_schema')
                and n.nspname not in ('sys', 'dbe_perf', 'db4ai', 'dbe_pldeveloper')
                and n.nspname not like 'dbe_%%'
                and n.nspname not like 'pkg_%%'
                and n.nspname not like 'prvt_%%'
                and n.nspname not like 'pg_toast%%'
                and n.nspname not like 'pg_temp%%'
                and has_schema_privilege(n.oid, 'USAGE')
                and has_table_privilege(c.oid, 'SELECT')
                {search_condition};
        """
        return super().query(
            db_name=self.db_name or "postgres", sql=sql, parameters=parameters
        )

    def get_group_tables_by_db(self, db_name):
        data = {}
        sql = """
            select
                n.nspname as table_schema,
                c.relname as table_name,
                coalesce(obj_description(c.oid), '') as table_comment
            from pg_class c
            join pg_namespace n on n.oid = c.relnamespace
            where c.relkind in ('r', 'p')
                and n.nspname not in ('pg_catalog', 'information_schema')
                and n.nspname not in ('sys', 'dbe_perf', 'db4ai', 'dbe_pldeveloper')
                and n.nspname not like 'dbe_%%'
                and n.nspname not like 'pkg_%%'
                and n.nspname not like 'prvt_%%'
                and n.nspname not like 'pg_toast%%'
                and n.nspname not like 'pg_temp%%'
                and has_schema_privilege(n.oid, 'USAGE')
                and has_table_privilege(c.oid, 'SELECT')
            order by n.nspname, c.relname;
        """
        result = self.query(db_name=db_name, sql=sql)
        for schema_name, table_name, table_comment in result.rows:
            display_name = self._display_object_name(schema_name, table_name)
            group_key = display_name[0]
            data.setdefault(group_key, []).append([display_name, table_comment or ""])
        return data

    def get_table_meta_data(self, db_name, tb_name, **kwargs):
        schema_name, clean_table_name = self._split_table_name(tb_name)
        sql = """
            select
                c.relname as table_name,
                case c.relkind
                    when 'r' then 'table'
                    when 'p' then 'partitioned table'
                    else c.relkind::text
                end as engine,
                '' as row_format,
                coalesce(c.reltuples::bigint, 0) as table_rows,
                0 as avg_row_length,
                round(pg_table_size(c.oid) / 1024.0, 2) as data_length,
                0 as max_data_length,
                round(pg_indexes_size(c.oid) / 1024.0, 2) as index_length,
                round((pg_table_size(c.oid) + pg_indexes_size(c.oid)) / 1024.0, 2) as data_total,
                0 as data_free,
                '' as auto_increment,
                current_setting('server_encoding') as table_collation,
                null as create_time,
                null as check_time,
                null as update_time,
                coalesce(obj_description(c.oid), '') as table_comment
            from pg_class c
            join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = %(schema_name)s
                and c.relname = %(table_name)s
                and c.relkind in ('r', 'p', 'm', 'v');
        """
        meta_data = self.query(
            db_name=db_name,
            sql=sql,
            parameters={"schema_name": schema_name, "table_name": clean_table_name},
        )
        return {
            "column_list": meta_data.column_list,
            "rows": meta_data.rows[0] if meta_data.rows else [],
        }

    def get_table_desc_data(self, db_name, tb_name, **kwargs):
        schema_name, clean_table_name = self._split_table_name(tb_name)
        sql = """
            select
                col.column_name as "列名",
                case
                    when col.character_maximum_length is not null
                        then col.data_type || '(' || col.character_maximum_length || ')'
                    when col.data_type in ('numeric', 'decimal') and col.numeric_precision is not null and col.numeric_scale is not null
                        then col.data_type || '(' || col.numeric_precision || ',' || col.numeric_scale || ')'
                    when col.data_type in ('numeric', 'decimal') and col.numeric_precision is not null
                        then col.data_type || '(' || col.numeric_precision || ')'
                    else col.data_type
                end as "列类型",
                '' as "列字符集",
                col.is_nullable as "是否为空",
                case when kcu.column_name is not null then 'PRI' else '' end as "索引列",
                col.column_default as "默认值",
                '' as "拓展信息",
                coalesce(des.description, '') as "列说明"
            from information_schema.columns col
            left join information_schema.table_constraints tc
                on tc.table_schema = col.table_schema
                and tc.table_name = col.table_name
                and tc.constraint_type = 'PRIMARY KEY'
            left join information_schema.key_column_usage kcu
                on kcu.constraint_schema = tc.constraint_schema
                and kcu.constraint_name = tc.constraint_name
                and kcu.table_schema = col.table_schema
                and kcu.table_name = col.table_name
                and kcu.column_name = col.column_name
            left join pg_catalog.pg_class cls
                on cls.relname = col.table_name
                and cls.relnamespace = (
                    select oid from pg_catalog.pg_namespace where nspname = col.table_schema
                )
            left join pg_catalog.pg_namespace ns
                on ns.oid = cls.relnamespace and ns.nspname = col.table_schema
            left join pg_catalog.pg_description des
                on des.objoid = cls.oid and des.objsubid = col.ordinal_position
            where col.table_schema = %(schema_name)s
                and col.table_name = %(table_name)s
            order by col.ordinal_position;
        """
        desc_data = self.query(
            db_name=db_name,
            sql=sql,
            parameters={"schema_name": schema_name, "table_name": clean_table_name},
        )
        return {"column_list": desc_data.column_list, "rows": desc_data.rows}

    def get_table_index_data(self, db_name, tb_name, **kwargs):
        schema_name, clean_table_name = self._split_table_name(tb_name)
        sql = """
            select
                att.attname as "列名",
                idx.relname as "索引名",
                case when i.indisunique then 0 else 1 end as "唯一性",
                i.indkey[i.ord] as "列序列",
                0 as "基数",
                '' as "是否为空",
                am.amname as "索引类型",
                pg_get_indexdef(i.indexrelid, i.ord, true) as "备注"
            from pg_index i
            join pg_class idx on idx.oid = i.indexrelid
            join pg_class tbl on tbl.oid = i.indrelid
            join pg_namespace ns on ns.oid = tbl.relnamespace
            join pg_am am on am.oid = idx.relam
            join generate_subscripts(i.indkey, 1) as i(ord) on true
            join pg_attribute att
                on att.attrelid = tbl.oid
                and att.attnum = i.indkey[i.ord]
            where ns.nspname = %(schema_name)s
                and tbl.relname = %(table_name)s
            order by idx.relname, i.ord;
        """
        index_data = self.query(
            db_name=db_name,
            sql=sql,
            parameters={"schema_name": schema_name, "table_name": clean_table_name},
        )
        return {"column_list": index_data.column_list, "rows": index_data.rows}

    def get_views_list(self, db_name, **kwargs):
        return self._group_information_schema_objects(
            db_name=db_name,
            sql="""
                select table_schema, table_name, coalesce(view_definition, '')
                from information_schema.views
                where table_schema not in ('pg_catalog', 'information_schema', 'sys', 'dbe_perf', 'db4ai', 'dbe_pldeveloper', 'resource_manager', 'sqladvisor')
                    and table_schema not like 'dbe_%%'
                    and table_schema not like 'pkg_%%'
                    and table_schema not like 'prvt_%%'
                order by table_schema, table_name;
            """,
        )

    def get_view_detail(self, db_name, view_name, **kwargs):
        schema_name, clean_view_name = self._split_table_name(view_name)
        sql = """
            select
                table_name as view_name,
                view_definition,
                check_option,
                is_updatable,
                '' as definer,
                '' as security_type,
                '' as character_set_client,
                '' as collation_connection
            from information_schema.views
            where table_schema = %(schema_name)s
                and table_name = %(view_name)s;
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
            "desc": self.get_table_desc_data(db_name=db_name, tb_name=view_name),
            "view_definition": meta.rows[0][1] if meta.rows else "",
        }

    def get_triggers_list(self, db_name, **kwargs):
        data = {}
        sql = """
            select
                trigger_schema,
                trigger_name,
                action_timing || ' ' || event_manipulation || ' ON ' || event_object_table as description
            from information_schema.triggers
            where trigger_schema not in ('pg_catalog', 'information_schema', 'sys', 'dbe_perf', 'db4ai', 'dbe_pldeveloper', 'resource_manager', 'sqladvisor')
                and trigger_schema not like 'dbe_%%'
                and trigger_schema not like 'pkg_%%'
                and trigger_schema not like 'prvt_%%'
            order by trigger_schema, trigger_name;
        """
        result = self.query(db_name=db_name, sql=sql)
        for schema_name, trigger_name, description in result.rows:
            display_name = self._display_object_name(schema_name, trigger_name)
            data.setdefault(display_name[0], []).append([display_name, description])
        return data

    def get_trigger_detail(self, db_name, trigger_name, **kwargs):
        schema_name, clean_trigger_name = self._split_table_name(trigger_name)
        sql = """
            select
                trigger_name,
                action_timing,
                event_manipulation,
                event_object_table,
                action_orientation,
                action_statement,
                '' as definer,
                null as created,
                '' as sql_mode,
                '' as character_set_client,
                '' as collation_connection
            from information_schema.triggers
            where trigger_schema = %(schema_name)s
                and trigger_name = %(trigger_name)s;
        """
        data = self.query(
            db_name=db_name,
            sql=sql,
            parameters={"schema_name": schema_name, "trigger_name": clean_trigger_name},
        )
        return {
            "column_list": data.column_list,
            "rows": data.rows[0] if data.rows else [],
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

    def get_tables_metas_data(self, db_name, **kwargs):
        tables = []
        for group_tables in self.get_group_tables_by_db(db_name=db_name).values():
            for table_name, table_comment in group_tables:
                tables.append((table_name, table_comment))
        table_metas = []
        engine_keys = [
            {"key": "COLUMN_NAME", "value": "字段名"},
            {"key": "COLUMN_TYPE", "value": "数据类型"},
            {"key": "COLUMN_DEFAULT", "value": "默认值"},
            {"key": "IS_NULLABLE", "value": "允许非空"},
            {"key": "COLUMN_KEY", "value": "是否主键"},
            {"key": "COLUMN_COMMENT", "value": "备注"},
        ]
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

    def slowquery_review(
        self,
        start_time,
        end_time,
        db_name="",
        limit=30,
        offset=0,
        search="",
        sort_name="MySQLTotalExecutionCounts",
        sort_order="desc",
    ):
        sort_map = {
            "CreateTime": "CreateTime",
            "DBName": "DBName",
            "SQLText": "SQLText",
            "MySQLTotalExecutionCounts": "MySQLTotalExecutionCounts",
            "MySQLTotalExecutionTimes": "MySQLTotalExecutionTimes",
            "QueryTimeAvg": "QueryTimeAvg",
            "ParseTotalRowCounts": "ParseTotalRowCounts",
            "ReturnTotalRowCounts": "ReturnTotalRowCounts",
            "ParseRowAvg": "ParseRowAvg",
            "ReturnRowAvg": "ReturnRowAvg",
        }
        order_by = sort_map.get(sort_name, "MySQLTotalExecutionCounts")
        order = "asc" if str(sort_order).lower() == "asc" else "desc"
        where_clause, parameters = self._slowquery_filters(
            start_time, end_time, db_name, search
        )
        parameters.update({"limit": limit, "offset": offset})
        sql = f"""
            with base as (
                select
                    coalesce(unique_query_id::text, md5(coalesce(query, ''))) as sql_id,
                    coalesce(db_name::text, '') as db_name,
                    coalesce(query, '') as query,
                    start_time,
                    finish_time,
                    greatest(coalesce(extract(epoch from finish_time - start_time), 0), 0) as duration_seconds,
                    coalesce(n_tuples_fetched, 0) as rows_examined,
                    coalesce(n_returned_rows, n_tuples_returned, 0) as rows_sent
                from dbe_perf.statement_history
                {where_clause}
            ), agg as (
                select
                    max(start_time) as "CreateTime",
                    max(db_name) as "DBName",
                    max(query) as "SQLText",
                    sql_id as "SQLId",
                    count(*) as "MySQLTotalExecutionCounts",
                    round(sum(duration_seconds)::numeric, 6) as "MySQLTotalExecutionTimes",
                    round(avg(duration_seconds)::numeric, 6) as "QueryTimeAvg",
                    sum(rows_examined) as "ParseTotalRowCounts",
                    sum(rows_sent) as "ReturnTotalRowCounts",
                    round(avg(rows_examined)::numeric, 0) as "ParseRowAvg",
                    round(avg(rows_sent)::numeric, 0) as "ReturnRowAvg"
                from base
                group by sql_id
            )
            select * from agg
            order by "{order_by}" {order}
            offset %(offset)s limit %(limit)s;
        """
        count_sql = f"""
            select count(distinct coalesce(unique_query_id::text, md5(coalesce(query, ''))))
            from dbe_perf.statement_history
            {where_clause};
        """
        return self._slowquery_response(sql, count_sql, parameters)

    def slowquery_review_history(
        self,
        start_time,
        end_time,
        db_name="",
        sql_id="",
        limit=30,
        offset=0,
        search="",
        sort_name="ParseRowCounts",
        sort_order="desc",
    ):
        sort_map = {
            "ExecutionStartTime": "ExecutionStartTime",
            "DBName": "DBName",
            "HostAddress": "HostAddress",
            "SQLText": "SQLText",
            "TotalExecutionCounts": "TotalExecutionCounts",
            "QueryTimePct95": "QueryTimePct95",
            "QueryTimes": "QueryTimes",
            "LockTimes": "LockTimes",
            "ParseRowCounts": "ParseRowCounts",
            "ReturnRowCounts": "ReturnRowCounts",
        }
        order_by = sort_map.get(sort_name, "ParseRowCounts")
        order = "asc" if str(sort_order).lower() == "asc" else "desc"
        where_clause, parameters = self._slowquery_filters(
            start_time, end_time, db_name, search
        )
        if sql_id:
            where_clause += """
                and coalesce(unique_query_id::text, md5(coalesce(query, ''))) = %(sql_id)s
            """
            parameters["sql_id"] = sql_id
        parameters.update({"limit": limit, "offset": offset})
        sql = f"""
            select
                start_time as "ExecutionStartTime",
                coalesce(db_name::text, '') as "DBName",
                '''' || coalesce(user_name::text, '') || '''@''' || coalesce(client_addr::text, '') || '''' as "HostAddress",
                coalesce(query, '') as "SQLText",
                1 as "TotalExecutionCounts",
                0 as "QueryTimePct95",
                round(greatest(coalesce(extract(epoch from finish_time - start_time), 0), 0)::numeric, 6) as "QueryTimes",
                round((coalesce(lock_time, 0) / 1000000.0)::numeric, 6) as "LockTimes",
                coalesce(n_tuples_fetched, 0) as "ParseRowCounts",
                coalesce(n_returned_rows, n_tuples_returned, 0) as "ReturnRowCounts"
            from dbe_perf.statement_history
            {where_clause}
            order by "{order_by}" {order}
            offset %(offset)s limit %(limit)s;
        """
        count_sql = f"""
            select count(*)
            from dbe_perf.statement_history
            {where_clause};
        """
        return self._slowquery_response(sql, count_sql, parameters)

    def lock_info(self):
        sql = """
            select
                blocked.pid as blocked_pid,
                blocked.usename as blocked_user,
                blocked.datname as blocked_database,
                blocked.query as blocked_query,
                blocked.query_start as blocked_query_start,
                blocking.pid as blocking_pid,
                blocking.usename as blocking_user,
                blocking.query as blocking_query,
                blocking.query_start as blocking_query_start,
                blocked_locks.locktype,
                blocked_locks.mode as blocked_mode,
                blocking_locks.mode as blocking_mode,
                blocked_locks.relation::regclass::text as relation
            from pg_locks blocked_locks
            join pg_stat_activity blocked on blocked.pid = blocked_locks.pid
            join pg_locks blocking_locks
                on blocking_locks.locktype = blocked_locks.locktype
                and blocking_locks.database is not distinct from blocked_locks.database
                and blocking_locks.relation is not distinct from blocked_locks.relation
                and blocking_locks.page is not distinct from blocked_locks.page
                and blocking_locks.tuple is not distinct from blocked_locks.tuple
                and blocking_locks.virtualxid is not distinct from blocked_locks.virtualxid
                and blocking_locks.transactionid is not distinct from blocked_locks.transactionid
                and blocking_locks.classid is not distinct from blocked_locks.classid
                and blocking_locks.objid is not distinct from blocked_locks.objid
                and blocking_locks.objsubid is not distinct from blocked_locks.objsubid
                and blocking_locks.pid <> blocked_locks.pid
            join pg_stat_activity blocking on blocking.pid = blocking_locks.pid
            where not blocked_locks.granted
                and blocking_locks.granted
            order by blocked.query_start;
        """
        return super().query(db_name=self.db_name or "postgres", sql=sql)

    def get_long_transaction(self):
        sql = """
            select
                xact_start as trx_started,
                now() - xact_start as trx_idle_time,
                state as trx_state,
                usename as "user",
                client_addr::text as host,
                datname as db,
                pid as trx_mysql_thread_id,
                enqueue as trx_operation_state,
                0 as trx_tables_locked,
                0 as trx_rows_locked,
                0 as trx_rows_modified,
                '' as trx_is_read_only,
                '' as trx_isolation_level,
                round(greatest(extract(epoch from now() - xact_start), 0)::numeric, 4) as thread_time,
                query as info
            from pg_stat_activity
            where xact_start is not null
                and pid <> pg_backend_pid()
            order by xact_start;
        """
        return super().query(db_name=self.db_name or "postgres", sql=sql)

    def get_rollback(self, workflow):
        list_execute_result = []
        try:
            import json

            list_execute_result = json.loads(workflow.sqlworkflowcontent.execute_result)
        except Exception:
            return []
        list_execute_result.reverse()
        rollback_sql = []
        for item in list_execute_result:
            source_sql = item.get("sql", "") if isinstance(item, dict) else ""
            rollback_sql.append(
                [source_sql, self._build_metadata_rollback_sql(source_sql)]
            )
        return rollback_sql

    def get_variables(self, variables=None):
        parameters = {}
        where_clause = ""
        if variables:
            where_clause = "where name in %(variables)s"
            parameters["variables"] = tuple(variables)
        sql = f"""
            select name, setting, unit, context, vartype, short_desc
            from pg_settings
            {where_clause}
            order by name;
        """
        return super().query(
            db_name=self.db_name or "postgres", sql=sql, parameters=parameters
        )

    def set_variable(self, variable_name, variable_value):
        result_set = ResultSet()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", str(variable_name or "")):
            result_set.error = "invalid variable name"
            return result_set
        # Check if the parameter requires a restart (postmaster context)
        check_sql = "select context from pg_settings where name = %(name)s;"
        alter_sql = (
            f"ALTER SYSTEM SET {self._quote_identifier(variable_name)} = %(value)s;"
        )
        result_set.full_sql = alter_sql
        conn = None
        try:
            conn = self.get_connection(db_name=self.db_name or "postgres")
            conn.autocommit = True  # ALTER SYSTEM cannot run inside a transaction block
            cursor = conn.cursor()
            cursor.execute(check_sql, {"name": variable_name})
            row = cursor.fetchone()
            if row and row[0] == "postmaster":
                result_set.error = (
                    f"参数 {variable_name} 需要重启实例才能生效，不支持在线修改"
                )
                return result_set
            cursor.execute(alter_sql, {"value": variable_value})
            # Reload config so the change takes effect immediately (for non-postmaster params)
            try:
                cursor.execute("SELECT pg_reload_conf();")
            except Exception:
                pass  # reload is best-effort; some params may need restart
            conn.commit()
            result_set.affected_rows = cursor.rowcount if cursor.rowcount > 0 else 0
        except Exception as e:
            result_set.error = str(e)
        finally:
            self.close()
        return result_set

    @staticmethod
    def _quote_identifier(identifier):
        return '"' + str(identifier).replace('"', '""') + '"'

    @staticmethod
    def _quote_literal(value):
        return "'" + str(value).replace("'", "''") + "'"

    @staticmethod
    def _format_column_type(
        data_type, char_length, numeric_precision, numeric_scale, udt_name=None
    ):
        if (
            data_type in ("character varying", "character", "varchar", "char")
            and char_length
        ):
            return f"{data_type}({char_length})"
        # Only numeric/decimal types should have precision/scale;
        # integer family (integer, bigint, smallint) has numeric_precision
        # but appending it produces invalid syntax like integer(32,0)
        if data_type in ("numeric", "decimal") and numeric_precision:
            if numeric_scale is not None:
                return f"{data_type}({numeric_precision},{numeric_scale})"
            return f"{data_type}({numeric_precision})"
        # Handle USER-DEFINED types (enum, domain, composite) and ARRAY
        if data_type == "USER-DEFINED" and udt_name:
            return udt_name
        if data_type == "ARRAY" and udt_name:
            # udt_name for arrays looks like '_int4' → strip leading '_'
            elem = udt_name.lstrip("_")
            return f"{elem}[]"
        return data_type

    @staticmethod
    def _split_table_name(table_name, schema_name=None):
        clean_name = table_name.strip().rstrip(";")
        parts = GaussDBEngine._split_qualified_name(clean_name)
        if len(parts) >= 2:
            schema_part, table_part = parts[-2], parts[-1]
            return schema_part, table_part
        return schema_name or "public", parts[0] if parts else ""

    @staticmethod
    def _split_qualified_name(name):
        """Split a qualified name by '.', respecting double-quoted identifiers.
        Unquoted parts are folded to lowercase (PostgreSQL/openGauss behavior).
        Quoted parts retain their exact casing with quotes removed."""
        result = []
        current = []
        had_quotes = False
        in_quotes = False
        i = 0
        while i < len(name):
            char = name[i]
            if char == '"':
                if in_quotes and i + 1 < len(name) and name[i + 1] == '"':
                    current.append('"')
                    i += 2
                    continue
                in_quotes = not in_quotes
                had_quotes = True
            elif char == "." and not in_quotes:
                seg = "".join(current).strip()
                if seg:
                    result.append(seg if had_quotes else seg.lower())
                current = []
                had_quotes = False
            else:
                current.append(char)
            i += 1
        seg = "".join(current).strip()
        if seg:
            result.append(seg if had_quotes else seg.lower())
        return result

    @staticmethod
    def _display_object_name(schema_name, object_name):
        if schema_name == "public":
            return object_name
        return f"{schema_name}.{object_name}"

    def _group_information_schema_objects(self, db_name, sql):
        data = {}
        result = self.query(db_name=db_name, sql=sql)
        for schema_name, object_name, object_comment in result.rows:
            display_name = self._display_object_name(schema_name, object_name)
            data.setdefault(display_name[0], []).append(
                [display_name, (object_comment or "")[:80]]
            )
        return data

    def _get_routines_list(self, db_name, routine_type):
        data = {}
        sql = """
            select routine_schema, routine_name, ''
            from information_schema.routines
            where routine_schema not in ('pg_catalog', 'information_schema', 'sys', 'dbe_perf', 'db4ai', 'dbe_pldeveloper', 'resource_manager', 'sqladvisor')
                and routine_schema not like 'dbe_%%'
                and routine_schema not like 'pkg_%%'
                and routine_schema not like 'prvt_%%'
                and routine_type = %(routine_type)s
            order by routine_schema, routine_name, specific_name;
        """
        result = self.query(
            db_name=db_name, sql=sql, parameters={"routine_type": routine_type}
        )
        for schema_name, routine_name, routine_comment in result.rows:
            display_name = self._display_object_name(schema_name, routine_name)
            data.setdefault(display_name[0], []).append([display_name, routine_comment])
        return data

    def _get_routine_detail(self, db_name, routine_name, routine_type):
        schema_name, clean_routine_name = self._split_table_name(routine_name)
        sql_meta = """
            select
                routine_name,
                routine_schema,
                data_type as return_type,
                '' as definer,
                null as created,
                null as last_altered,
                '' as sql_mode,
                security_type,
                '' as routine_comment
            from information_schema.routines
            where routine_schema = %(schema_name)s
                and routine_name = %(routine_name)s
                and routine_type = %(routine_type)s;
        """
        meta = self.query(
            db_name=db_name,
            sql=sql_meta,
            close_conn=False,
            parameters={
                "schema_name": schema_name,
                "routine_name": clean_routine_name,
                "routine_type": routine_type,
            },
        )
        prokind = "p" if routine_type == "PROCEDURE" else "f"
        sql_create = """
            select pg_get_functiondef(p.oid), p.oid
            from pg_proc p
            join pg_namespace n on n.oid = p.pronamespace
            where n.nspname = %(schema_name)s
                and p.proname = %(routine_name)s
                and p.prokind = %(prokind)s
            order by p.oid;
        """
        create = self.query(
            db_name=db_name,
            sql=sql_create,
            parameters={
                "schema_name": schema_name,
                "routine_name": clean_routine_name,
                "prokind": prokind,
            },
        )
        return {
            "meta_data": {
                "column_list": meta.column_list,
                "rows": meta.rows[0] if meta.rows else (),
            },
            "create_sql": create.rows,
        }

    @staticmethod
    def _slowquery_filters(start_time, end_time, db_name="", search=""):
        where_clause = """
            where start_time >= %(start_time)s::timestamp
                and start_time < (%(end_time)s::timestamp + interval '1 day')
        """
        parameters = {"start_time": start_time, "end_time": end_time}
        if db_name:
            where_clause += " and db_name = %(db_name)s"
            parameters["db_name"] = db_name
        if search:
            where_clause += " and query ilike %(search)s"
            parameters["search"] = f"%{search}%"
        return where_clause, parameters

    def _slowquery_response(self, sql, count_sql, parameters):
        rows_result = super().query(
            db_name=self.db_name or "postgres",
            sql=sql,
            close_conn=False,
            parameters=parameters,
        )
        if rows_result.error:
            self.close()
            return {"total": 0, "rows": [], "error": rows_result.error}
        count_result = super().query(
            db_name=self.db_name or "postgres", sql=count_sql, parameters=parameters
        )
        if count_result.error:
            self.close()
            return {"total": 0, "rows": [], "error": count_result.error}
        total = count_result.rows[0][0] if count_result.rows else 0
        return {"total": total, "rows": rows_result.to_dict()}

    def _build_metadata_rollback_sql(self, source_sql):
        parsed = sqlparse.parse(source_sql or "")
        if not parsed:
            return "GaussDB 暂不支持该语句的自动回滚生成。"
        statement = parsed[0]
        tokens = [
            token
            for token in statement.tokens
            if not token.is_whitespace
            and token.ttype is not sqlparse.tokens.Punctuation
        ]
        words = [token.value for token in tokens]
        normalized = [word.upper() for word in words]
        source = str(source_sql or "").strip().rstrip(";")
        if len(normalized) >= 3 and normalized[0] == "CREATE":
            object_type = normalized[1]
            # Skip optional clauses like IF NOT EXISTS / OR REPLACE
            name_idx = 2
            while name_idx < len(normalized) and normalized[name_idx] in (
                "IF",
                "NOT",
                "EXISTS",
                "IF NOT EXISTS",
                "OR",
                "REPLACE",
                "OR REPLACE",
                "TEMP",
                "TEMPORARY",
            ):
                name_idx += 1
            if name_idx >= len(words):
                return "GaussDB 暂不支持该语句的自动回滚生成。"
            object_name = words[name_idx]
            if object_type == "SCHEMA":
                return f"DROP SCHEMA IF EXISTS {object_name} CASCADE;"
            if object_type == "TABLE":
                return f"DROP TABLE IF EXISTS {object_name};"
            if object_type == "VIEW":
                return f"DROP VIEW IF EXISTS {object_name};"
            if object_type == "INDEX":
                return f"DROP INDEX IF EXISTS {object_name};"
        alter_add_constraint = re.match(
            r"^\s*alter\s+table\s+(.+?)\s+add\s+(?:constraint|primary\s+key|unique|foreign\s+key)\b",
            source,
            re.I | re.S,
        )
        if alter_add_constraint:
            table_name = alter_add_constraint.group(1)
            constraint_name_match = re.match(
                r"^\s*alter\s+table\s+(.+?)\s+add\s+constraint\s+(\"?[^\s\"]+\"?)\b",
                source,
                re.I | re.S,
            )
            if constraint_name_match:
                constraint_name = constraint_name_match.group(2)
                return f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {constraint_name};"
            return "GaussDB 暂不支持该语句的自动回滚生成。"
        alter_add_column = re.match(
            r"^\s*alter\s+table\s+(.+?)\s+add\s+(?:column\s+)?(?:if\s+not\s+exists\s+)?(\"?[^\s\"]+\"?)\s+",
            source,
            re.I | re.S,
        )
        if alter_add_column:
            table_name, column_name = alter_add_column.groups()
            return f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS {column_name};"
        alter_rename_table = re.match(
            r"^\s*alter\s+table\s+(.+?)\s+rename\s+to\s+(.+?)\s*$",
            source,
            re.I | re.S,
        )
        if alter_rename_table:
            old_name, new_name = alter_rename_table.groups()
            return f"ALTER TABLE {new_name} RENAME TO {old_name};"
        alter_rename_column = re.match(
            r"^\s*alter\s+table\s+(.+?)\s+rename\s+column\s+(.+?)\s+to\s+(.+?)\s*$",
            source,
            re.I | re.S,
        )
        if alter_rename_column:
            table_name, old_column, new_column = alter_rename_column.groups()
            return (
                f"ALTER TABLE {table_name} RENAME COLUMN {new_column} TO {old_column};"
            )
        return (
            "GaussDB 暂不支持该语句的自动行级回滚；请使用数据库备份/PITR或人工补偿SQL。"
        )
