import json
import re
import unittest
from unittest.mock import MagicMock, Mock, patch

from sql.engines.kingbase import (
    _ROLLBACK_UNSUPPORTED,
    _SYSTEM_SCHEMA_SQL,
    DRIVER_NAME,
    KES_SYSTEM_SCHEMAS,
    KingbaseEngine,
)
from sql.engines.models import ResultSet, ReviewSet


def make_error_result(message="boom"):
    rs = ResultSet(rows=[])
    rs.error = message
    return rs


def make_mock_instance():
    ins = Mock()
    ins.instance_name = "kingbase_ins"
    ins.host = "some_host"
    ins.port = 54321
    ins.db_name = "test"
    ins.db_type = "kingbase"
    ins.mode = ""
    ins.charset = "UTF8"
    ins.tunnel = None
    ins.get_username_password.return_value = ("ins_user", "some_pwd")
    return ins


class TestKingbaseEngine(unittest.TestCase):
    def setUp(self):
        self.instance = make_mock_instance()

    # ---------- base info ----------
    def test_engine_base_info(self):
        engine = KingbaseEngine(instance=self.instance)
        self.assertEqual(engine.name, "KingbaseES")
        self.assertEqual(engine.info, "KingbaseES engine")
        self.assertFalse(engine.auto_backup)
        self.assertEqual(engine.test_query, "SELECT 1")

    def test_uses_kingbase_driver(self):
        self.assertEqual(DRIVER_NAME, "ksycopg2")

    def test_does_not_inherit_pgsql_engine(self):
        from sql.engines import EngineBase

        self.assertTrue(issubclass(KingbaseEngine, EngineBase))
        self.assertNotIn("PgSQLEngine", [c.__name__ for c in KingbaseEngine.__mro__])

    def test_system_schemas_include_kes_native(self):
        self.assertIn("sys_catalog", KES_SYSTEM_SCHEMAS)
        self.assertIn("pg_catalog", KES_SYSTEM_SCHEMAS)
        self.assertIn("kdb_schedule", KES_SYSTEM_SCHEMAS)

    # ---------- connection ----------
    @patch("sql.engines.kingbase.db_driver.connect")
    def test_get_connection_uses_kes_default_db(self, mock_connect):
        engine = KingbaseEngine(instance=self.instance)
        engine.get_connection()
        mock_connect.assert_called_once_with(
            host="some_host",
            port=54321,
            user="ins_user",
            password="some_pwd",
            client_encoding="UTF8",
            dbname="test",
            connect_timeout=10,
        )

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_get_connection_explicit_db(self, mock_connect):
        engine = KingbaseEngine(instance=self.instance)
        engine.get_connection("biz_db")
        self.assertEqual(mock_connect.call_args.kwargs["dbname"], "biz_db")

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_get_connection_reuses_existing(self, mock_connect):
        engine = KingbaseEngine(instance=self.instance)
        engine.conn = MagicMock()
        engine._conn_db = "biz_db"
        engine.get_connection("biz_db")
        mock_connect.assert_not_called()

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_get_connection_switches_database(self, mock_connect):
        """A cached connection is bound to one database and must be replaced.

        Regression: returning the cached connection regardless of db_name made
        every later call silently query the first database.
        """
        old_conn = MagicMock()
        engine = KingbaseEngine(instance=self.instance)
        engine.conn = old_conn
        engine._conn_db = "test"
        engine.get_connection("security")
        self.assertTrue(old_conn.close.called, "stale connection was not closed")
        self.assertEqual(mock_connect.call_args.kwargs["dbname"], "security")
        self.assertEqual(engine._conn_db, "security")

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_get_connection_failure_leaves_no_stale_state(self, mock_connect):
        """A failed connect must not leave a connection tagged with a db name."""
        mock_connect.side_effect = Exception("FATAL: database does not exist")
        engine = KingbaseEngine(instance=self.instance)
        with self.assertRaises(Exception):
            engine.get_connection("missing_db")
        self.assertIsNone(engine.conn)
        self.assertIsNone(engine._conn_db)

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_close_clears_connection_database(self, mock_connect):
        engine = KingbaseEngine(instance=self.instance)
        engine.conn = MagicMock()
        engine._conn_db = "test"
        engine.close()
        self.assertIsNone(engine.conn)
        self.assertIsNone(engine._conn_db)

    # ---------- query ----------
    @patch("sql.engines.kingbase.db_driver.connect")
    def test_query_success_with_limit(self, mock_connect):
        cursor = MagicMock()
        cursor.fetchmany.return_value = [(1, "ok")]
        cursor.description = [("id", 23), ("name", 25)]
        mock_connect.return_value.cursor.return_value = cursor

        engine = KingbaseEngine(instance=self.instance)
        result = engine.query(sql="select id, name from t", limit_num=10)

        self.assertIsInstance(result, ResultSet)
        self.assertEqual(result.column_list, ["id", "name"])
        self.assertEqual(result.rows, [(1, "ok")])
        self.assertEqual(result.affected_rows, 1)
        cursor.fetchmany.assert_called_once_with(size=10)

    def test_query_check_rejects_non_select(self):
        engine = KingbaseEngine(instance=self.instance)
        self.assertTrue(engine.query_check(sql="delete from t")["bad_query"])
        self.assertFalse(engine.query_check(sql="select 1")["bad_query"])

    def test_filter_sql_appends_limit(self):
        engine = KingbaseEngine(instance=self.instance)
        self.assertEqual(
            engine.filter_sql(sql="select 1", limit_num=100), "select 1 limit 100;"
        )

    # ---------- version ----------
    @patch.object(KingbaseEngine, "query")
    def test_server_version_kes_format(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("KingbaseES V009R001C010",)])
        engine = KingbaseEngine(instance=self.instance)
        self.assertEqual(engine.server_version, (9, 1, 10))

    @patch.object(KingbaseEngine, "query")
    def test_server_version_error(self, mock_query):
        mock_query.return_value = ResultSet(error="boom")
        engine = KingbaseEngine(instance=self.instance)
        self.assertEqual(engine.server_version, tuple())

    # ---------- metadata: all use sys_* catalogs ----------
    @patch.object(KingbaseEngine, "query")
    def test_get_all_databases_uses_sys_database(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[("test",), ("template1",), ("template0",), ("biz",)]
        )
        engine = KingbaseEngine(instance=self.instance)
        result = engine.get_all_databases()
        self.assertIn("sys_database", mock_query.call_args.kwargs["sql"])
        self.assertEqual(result.rows, ["test", "biz"])

    @patch.object(KingbaseEngine, "query")
    def test_get_all_schemas_filters_system(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[("public",), ("sys_catalog",), ("pg_catalog",), ("biz",)]
        )
        engine = KingbaseEngine(instance=self.instance)
        result = engine.get_all_schemas("test")
        self.assertIn("sys_namespace", mock_query.call_args.kwargs["sql"])
        self.assertEqual(result.rows, ["public", "biz"])

    @patch.object(KingbaseEngine, "query")
    def test_get_all_tables_uses_sys_class(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("customers",), ("orders",)])
        engine = KingbaseEngine(instance=self.instance)
        result = engine.get_all_tables("test", schema_name="public")
        sql = mock_query.call_args.kwargs["sql"]
        self.assertIn("sys_class", sql)
        self.assertIn("sys_namespace", sql)
        self.assertEqual(result.rows, ["customers", "orders"])

    # The resource API (/api/v1/sqlquery/resources/) leaves schema_name empty when
    # the caller just wants "the tables of this database", so the engine falls
    # back to the KES default schema "public".
    @patch.object(KingbaseEngine, "query")
    def test_get_all_tables_defaults_to_public_schema(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("customers",)])
        engine = KingbaseEngine(instance=self.instance)
        engine.get_all_tables("test")
        self.assertEqual(
            mock_query.call_args.kwargs["parameters"]["schema_name"], "public"
        )

    @patch.object(KingbaseEngine, "query")
    def test_get_views_list_returns_grouped_dict(self, mock_query):
        """The dictionary tree expects {first_char: [[name, comment], ...]}."""
        mock_query.return_value = ResultSet(
            rows=[("public", "v_orders", "订单视图"), ("public", "v_users", "")]
        )
        engine = KingbaseEngine(instance=self.instance)
        data = engine.get_views_list("test")

        self.assertIsInstance(data, dict)
        self.assertIn("v", data)
        self.assertEqual(data["v"][0], ["v_orders", "订单视图"])

    @patch.object(KingbaseEngine, "query")
    def test_get_views_list_prefixes_non_public_schema(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("biz", "v_orders", "")])
        engine = KingbaseEngine(instance=self.instance)
        data = engine.get_views_list("test")
        self.assertEqual(data["b"][0][0], "biz.v_orders")

    @patch.object(KingbaseEngine, "query")
    def test_get_views_list_excludes_system_schemas(self, mock_query):
        mock_query.return_value = ResultSet(rows=[], column_list=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.get_views_list("test")
        sql = mock_query.call_args.kwargs["sql"]
        self.assertIn("sys_catalog", sql)
        self.assertNotIn("{_SYSTEM_SCHEMA_SQL}", sql)

    @patch.object(KingbaseEngine, "query")
    def test_explicit_schema_overrides_public_default(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("t",)])
        engine = KingbaseEngine(instance=self.instance)
        engine.get_all_tables("test", schema_name="biz")
        self.assertEqual(
            mock_query.call_args.kwargs["parameters"]["schema_name"], "biz"
        )

    @patch.object(KingbaseEngine, "query")
    def test_get_all_columns_uses_sys_attribute(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("id",), ("name",)])
        engine = KingbaseEngine(instance=self.instance)
        result = engine.get_all_columns_by_tb("test", "customers", schema_name="public")
        self.assertIn("sys_attribute", mock_query.call_args.kwargs["sql"])
        self.assertEqual(result.rows, ["id", "name"])

    @patch.object(KingbaseEngine, "query")
    def test_describe_table_uses_sys_catalogs(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("id", "int4")])
        engine = KingbaseEngine(instance=self.instance)
        engine.describe_table("test", "customers", schema_name="public")
        sql = mock_query.call_args.kwargs["sql"]
        self.assertIn("sys_attribute", sql)
        self.assertIn("sys_type", sql)
        self.assertNotIn("pg_catalog", sql)

    @patch.object(KingbaseEngine, "query")
    def test_get_table_meta_data_uses_sys_class(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[("public", "t")], column_list=["a", "b"]
        )
        engine = KingbaseEngine(instance=self.instance)
        result = engine.get_table_meta_data("test", "t", schema_name="public")
        self.assertIn("sys_class", mock_query.call_args.kwargs["sql"])
        self.assertEqual(result["column_list"], ["a", "b"])
        # showTableInfo expects a flat first row, not the whole list
        self.assertEqual(result["rows"], ("public", "t"))

    @patch.object(KingbaseEngine, "query")
    def test_show_create_table_includes_constraints(self, mock_query):
        """Synthesized DDL must include PK/unique/FK/check, not just columns."""
        cols = ResultSet(
            rows=[("id", "integer", None, None, None, "NO", None, "int4")],
            column_list=[
                "column_name",
                "data_type",
                "character_maximum_length",
                "numeric_precision",
                "numeric_scale",
                "is_nullable",
                "column_default",
                "udt_name",
            ],
        )
        constraints = ResultSet(
            rows=[("p", "PRIMARY KEY (id)")], column_list=["contype", "def"]
        )
        indexes = ResultSet(rows=[], column_list=[])
        mock_query.side_effect = [cols, constraints, indexes]
        engine = KingbaseEngine(instance=self.instance)
        # call show_create_table directly: query() is mocked too, so going
        # through query() would just return the first mocked ResultSet.
        result = engine.show_create_table(db_name="test", table_name="public.t")
        ddl = result.rows[0][1]
        self.assertIn("PRIMARY KEY (id)", ddl)
        self.assertIn('CREATE TABLE "public"."t"', ddl)

    @patch.object(KingbaseEngine, "query")
    def test_get_trigger_detail_uses_english_flat_contract(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[
                (
                    "trg",
                    "BEFORE",
                    "INSERT",
                    "t",
                    "ROW",
                    "EXECUTE ...",
                    "",
                    None,
                    "",
                    "",
                    "",
                )
            ],
            column_list=[
                "trigger_name",
                "action_timing",
                "event_manipulation",
                "event_object_table",
                "action_orientation",
                "action_statement",
                "definer",
                "created",
                "sql_mode",
                "character_set_client",
                "collation_connection",
            ],
        )
        engine = KingbaseEngine(instance=self.instance)
        detail = engine.get_trigger_detail("test", "public.trg")
        self.assertIn("information_schema.triggers", mock_query.call_args.kwargs["sql"])
        self.assertEqual(detail["rows"][0], "trg")
        self.assertIn("action_statement", detail["column_list"])

    @patch.object(KingbaseEngine, "query")
    def test_get_routine_detail_returns_modal_contract(self, mock_query):
        meta = ResultSet(
            rows=[("f", "public", "integer", "", None, None, "", "INVOKER", "")],
            column_list=[
                "routine_name",
                "routine_schema",
                "return_type",
                "definer",
                "created",
                "last_altered",
                "sql_mode",
                "security_type",
                "routine_comment",
            ],
        )
        create = ResultSet(rows=[("CREATE FUNCTION f() ...",)], column_list=["def"])
        mock_query.side_effect = [meta, create]
        engine = KingbaseEngine(instance=self.instance)
        detail = engine.get_function_detail("test", "public.f")
        self.assertEqual(set(detail), {"meta_data", "create_sql"})
        self.assertEqual(detail["meta_data"]["rows"][0], "f")
        self.assertEqual(detail["create_sql"], [("CREATE FUNCTION f() ...",)])

    # ---------- monitoring ----------
    @patch.object(KingbaseEngine, "query")
    def test_processlist_uses_sys_stat_activity(self, mock_query):
        mock_query.return_value = ResultSet(rows=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.processlist("Not Idle")
        sql = mock_query.call_args.kwargs["sql"]
        self.assertIn("sys_stat_activity", sql)
        self.assertIn("sys_backend_pid", sql)

    @patch.object(KingbaseEngine, "query")
    def test_slowquery_review_uses_sys_stat_statements(self, mock_query):
        mock_query.side_effect = [
            ResultSet(rows=[(1,)], column_list=["SQLId"]),
            ResultSet(rows=[(5,)]),
        ]
        engine = KingbaseEngine(instance=self.instance)
        result = engine.slowquery_review("2024-01-01 00:00:00", "2024-01-02 00:00:00")
        self.assertEqual(result["total"], 5)
        sql = mock_query.call_args_list[0].kwargs["sql"]
        self.assertIn("sys_stat_statements", sql)
        # front-end table columns must all be present
        for col in (
            "CreateTime",
            "DBName",
            "DurationPct95",
            "ParseTotalRowCounts",
            "ParseRowAvg",
            "ReturnRowAvg",
        ):
            self.assertIn(f'"{col}"', sql)

    @patch.object(KingbaseEngine, "query")
    def test_slowquery_review_filters_by_db_name(self, mock_query):
        mock_query.side_effect = [
            ResultSet(rows=[], column_list=[]),
            ResultSet(rows=[(5,)]),
        ]
        engine = KingbaseEngine(instance=self.instance)
        engine.slowquery_review("2024-01-01", "2024-01-02", db_name="biz_db")
        sql = mock_query.call_args_list[0].kwargs["sql"]
        self.assertIn("sys_database", sql)
        self.assertEqual(
            mock_query.call_args_list[0].kwargs["parameters"]["db_name"], "biz_db"
        )

    @patch.object(KingbaseEngine, "query")
    def test_slowquery_review_history_filters_sql_id(self, mock_query):
        mock_query.side_effect = [
            ResultSet(rows=[], column_list=[]),
            ResultSet(rows=[(1,)]),
        ]
        engine = KingbaseEngine(instance=self.instance)
        engine.slowquery_review_history("2024-01-01", "2024-01-02", sql_id="123")
        params = mock_query.call_args_list[0].kwargs["parameters"]
        self.assertEqual(params["sql_id"], "123")

    # ---------- variables: sys_settings ----------
    @patch.object(KingbaseEngine, "query")
    def test_get_variables_uses_sys_settings(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("work_mem", "4MB")])
        engine = KingbaseEngine(instance=self.instance)
        engine.get_variables()
        sql = mock_query.call_args.kwargs["sql"]
        self.assertIn("sys_settings", sql)
        self.assertNotIn("pg_settings", sql)

    # ---------- session kill ----------
    # These tests assert the generated SQL only: query() is mocked, so no
    # session is actually terminated.
    def test_kill_connection_requires_integer(self):
        engine = KingbaseEngine(instance=self.instance)
        result = engine.kill_connection("abc")
        self.assertEqual(result.error, "thread_id must be an integer")

    @patch.object(KingbaseEngine, "query")
    def test_kill_connection_builds_terminate_statement(self, mock_query):
        mock_query.return_value = ResultSet(rows=[(True,)])
        engine = KingbaseEngine(instance=self.instance)
        engine.kill_connection(1234)
        sql = mock_query.call_args.kwargs["sql"]
        self.assertIn("sys_terminate_backend(1234)", sql)
        mock_query.assert_called_once()

    # ---------- diagnostics: tablespace / locks / long transaction ----------
    @patch.object(KingbaseEngine, "query")
    def test_tablespace_uses_sys_catalog(self, mock_query):
        mock_query.return_value = ResultSet(rows=[], column_list=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.tablespace(offset=0, row_count=14)
        sql = mock_query.call_args.kwargs["sql"]
        self.assertIn("sys_catalog.sys_class", sql)
        self.assertIn("sys_table_size", sql)

    @patch.object(KingbaseEngine, "query")
    def test_lock_info_uses_sys_locks(self, mock_query):
        mock_query.return_value = ResultSet(rows=[], column_list=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.lock_info()
        sql = mock_query.call_args.kwargs["sql"]
        self.assertIn("sys_catalog.sys_locks", sql)
        self.assertIn("sys_catalog.sys_stat_activity", sql)

    @patch.object(KingbaseEngine, "query")
    def test_get_long_transaction_uses_sys_stat_activity(self, mock_query):
        mock_query.return_value = ResultSet(rows=[], column_list=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.get_long_transaction()
        sql = mock_query.call_args.kwargs["sql"]
        self.assertIn("sys_catalog.sys_stat_activity", sql)
        self.assertIn("xact_start", sql)

    # ---------- data dictionary ----------
    @patch.object(KingbaseEngine, "query")
    def test_get_group_tables_by_db(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[("public", "customers", "客户表"), ("public", "orders", "")],
            column_list=["table_schema", "table_name", "table_comment"],
        )
        engine = KingbaseEngine(instance=self.instance)
        data = engine.get_group_tables_by_db(db_name="test")
        self.assertIn("c", data)
        self.assertIn("o", data)
        self.assertIn("sys_catalog.sys_class", mock_query.call_args.kwargs["sql"])

    @patch.object(KingbaseEngine, "query")
    def test_get_table_desc_data_uses_information_schema(self, mock_query):
        mock_query.return_value = ResultSet(rows=[], column_list=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.get_table_desc_data("test", "public.customers")
        sql = mock_query.call_args.kwargs["sql"]
        self.assertIn("information_schema.columns", sql)

    # ---------- database summary ----------
    @patch.object(KingbaseEngine, "query")
    def test_get_all_databases_summary_uses_sys_database(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[("test", "UTF8", "en_US.UTF-8")],
            column_list=["db_name", "charset", "collation"],
        )
        engine = KingbaseEngine(instance=self.instance)
        result = engine.get_all_databases_summary()
        self.assertIn("sys_catalog.sys_database", mock_query.call_args.kwargs["sql"])
        self.assertEqual(result.rows[0]["db_name"], "test")

    # ---------- SQL review (execute_check) ----------
    # execute_check reads critical_ddl_regex through SysConfig, which hits the
    # Config table; patch it so the tests stay database-free.
    @patch("sql.engines.kingbase.SysConfig")
    def test_execute_check_rejects_select(self, mock_sys_config):
        mock_sys_config.return_value.get.return_value = ""
        engine = KingbaseEngine(instance=self.instance)
        result = engine.execute_check(sql="select * from t")
        self.assertEqual(result.rows[0].errlevel, 2)
        self.assertEqual(result.error_count, 1)

    @patch("sql.engines.kingbase.SysConfig")
    def test_execute_check_rejects_transaction_control(self, mock_sys_config):
        mock_sys_config.return_value.get.return_value = ""
        engine = KingbaseEngine(instance=self.instance)
        for stmt in ("commit", "rollback", "begin", "start transaction"):
            result = engine.execute_check(sql=stmt)
            self.assertEqual(result.rows[0].errlevel, 2, stmt)

    @patch("sql.engines.kingbase.SysConfig")
    def test_execute_check_warns_drop_and_truncate(self, mock_sys_config):
        mock_sys_config.return_value.get.return_value = ""
        engine = KingbaseEngine(instance=self.instance)
        result = engine.execute_check(sql="drop table t")
        self.assertEqual(result.rows[0].errlevel, 1)
        self.assertEqual(result.warning_count, 1)

    @patch("sql.engines.kingbase.SysConfig")
    def test_execute_check_warns_update_without_where(self, mock_sys_config):
        mock_sys_config.return_value.get.return_value = ""
        engine = KingbaseEngine(instance=self.instance)
        result = engine.execute_check(sql="update t set a=1")
        self.assertEqual(result.rows[0].errlevel, 1)

    @patch("sql.engines.kingbase.SysConfig")
    def test_execute_check_passes_normal_dml(self, mock_sys_config):
        mock_sys_config.return_value.get.return_value = ""
        engine = KingbaseEngine(instance=self.instance)
        result = engine.execute_check(sql="update t set a=1 where id=1")
        self.assertEqual(result.rows[0].errlevel, 0)
        self.assertEqual(result.error_count, 0)

    @patch("sql.engines.kingbase.SysConfig")
    def test_execute_check_marks_syntax_type_ddl(self, mock_sys_config):
        mock_sys_config.return_value.get.return_value = ""
        engine = KingbaseEngine(instance=self.instance)
        result = engine.execute_check(sql="create table t2(id int)")
        self.assertEqual(result.syntax_type, 1)

    # ---------- rollback generation ----------
    def test_rollback_create_table(self):
        sql = KingbaseEngine._build_metadata_rollback_sql("create table t2(id int)")
        self.assertEqual(sql, "DROP TABLE IF EXISTS t2;")

    # CREATE OR REPLACE / IF NOT EXISTS may have left a pre-existing object
    # untouched, so a DROP-based rollback would destroy data the workflow never
    # created. These must refuse to generate a rollback instead.
    def test_rollback_refuses_add_column_if_not_exists(self):
        sql = KingbaseEngine._build_metadata_rollback_sql(
            "alter table t add column if not exists c int"
        )
        self.assertNotIn("DROP COLUMN", sql)

    def test_rollback_refuses_create_if_not_exists(self):
        for sql in (
            "create table if not exists t(id int)",
            "create view if not exists v as select 1",
            "create schema if not exists s",
            "create sequence if not exists sq",
        ):
            with self.subTest(sql=sql):
                self.assertNotIn(
                    "DROP", KingbaseEngine._build_metadata_rollback_sql(sql)
                )

    def test_rollback_refuses_create_or_replace(self):
        for sql in (
            "create or replace view v as select 1",
            "create or replace function f() returns int as 'select 1' language sql",
        ):
            with self.subTest(sql=sql):
                self.assertNotIn(
                    "DROP", KingbaseEngine._build_metadata_rollback_sql(sql)
                )

    # Dropping a role must not destroy the objects it owns.
    @patch.object(KingbaseEngine, "execute")
    def test_drop_instance_user_does_not_drop_owned(self, mock_exec):
        mock_exec.return_value = ResultSet()
        engine = KingbaseEngine(instance=self.instance)
        engine.drop_instance_user(user_host="app_user@%")
        executed = [c.kwargs.get("sql", "") for c in mock_exec.call_args_list]
        self.assertTrue(
            all("DROP OWNED" not in s for s in executed),
            f"DROP OWNED would delete owned data: {executed}",
        )
        self.assertIn("DROP USER", executed[-1])

    def test_rollback_add_column(self):
        sql = KingbaseEngine._build_metadata_rollback_sql(
            "alter table t add column c int"
        )
        self.assertEqual(sql, "ALTER TABLE t DROP COLUMN IF EXISTS c;")

    def test_rollback_add_constraint(self):
        sql = KingbaseEngine._build_metadata_rollback_sql(
            "alter table t add constraint pk primary key(id)"
        )
        self.assertEqual(sql, "ALTER TABLE t DROP CONSTRAINT IF EXISTS pk;")

    def test_rollback_rename_table_preserves_schema(self):
        sql = KingbaseEngine._build_metadata_rollback_sql(
            "alter table public.foo rename to bar"
        )
        self.assertEqual(sql, "ALTER TABLE public.bar RENAME TO foo;")

    def test_rollback_rename_column(self):
        sql = KingbaseEngine._build_metadata_rollback_sql(
            "alter table t rename column a to b"
        )
        self.assertEqual(sql, "ALTER TABLE t RENAME COLUMN b TO a;")

    def test_rollback_unsupported_returns_hint(self):
        sql = KingbaseEngine._build_metadata_rollback_sql("update t set a=1")
        self.assertIn("暂不支持", sql)

    # ---------- kill command ----------
    @patch.object(KingbaseEngine, "query")
    def test_get_kill_command_builds_statements(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[("SELECT sys_terminate_backend(1);",)]
        )
        engine = KingbaseEngine(instance=self.instance)
        cmds = engine.get_kill_command([1, 2])
        self.assertEqual(cmds, ["SELECT sys_terminate_backend(1);"])
        self.assertIn(
            "sys_catalog.sys_stat_activity", mock_query.call_args.kwargs["sql"]
        )

    def test_get_kill_command_empty(self):
        engine = KingbaseEngine(instance=self.instance)
        self.assertEqual(engine.get_kill_command([]), [])

    # ---------- account management ----------
    def test_quote_ident_rejects_injection(self):
        with self.assertRaises(ValueError):
            KingbaseEngine._quote_ident('user"; DROP TABLE x; --')

    def test_quote_ident_accepts_normal(self):
        self.assertEqual(KingbaseEngine._quote_ident("app_user"), '"app_user"')

    @patch.object(KingbaseEngine, "query")
    @patch.object(KingbaseEngine, "execute")
    def test_create_instance_user(self, mock_exec, mock_query):
        mock_exec.return_value = ResultSet()
        mock_query.return_value = ResultSet(rows=[])
        engine = KingbaseEngine(instance=self.instance)
        result = engine.create_instance_user(user="app_user", password1="Pwd123456!")
        self.assertIsNone(result.error)
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0]["user"], "app_user")
        self.assertIn("CREATE USER", mock_exec.call_args.kwargs["sql"])

    @patch.object(KingbaseEngine, "query")
    @patch.object(KingbaseEngine, "execute")
    def test_create_instance_user_rejects_empty_password(self, mock_exec, mock_query):
        mock_query.return_value = ResultSet(rows=[])
        engine = KingbaseEngine(instance=self.instance)
        result = engine.create_instance_user(user="app_user", password1="")
        self.assertIn("密码不能为空", result.error)
        mock_exec.assert_not_called()

    @patch.object(KingbaseEngine, "query")
    @patch.object(KingbaseEngine, "execute")
    def test_create_instance_user_escapes_password_quote(self, mock_exec, mock_query):
        mock_exec.return_value = ResultSet()
        mock_query.return_value = ResultSet(rows=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.create_instance_user(user="app_user", password1="a'b")
        self.assertIn("'a''b'", mock_exec.call_args.kwargs["sql"])

    @patch.object(KingbaseEngine, "execute")
    def test_drop_instance_user(self, mock_exec):
        mock_exec.return_value = ResultSet()
        engine = KingbaseEngine(instance=self.instance)
        result = engine.drop_instance_user(user_host="app_user@%")
        self.assertIsNone(result.error)
        self.assertIn("DROP USER", mock_exec.call_args.kwargs["sql"])

    @patch.object(KingbaseEngine, "execute")
    def test_reset_instance_user_pwd(self, mock_exec):
        mock_exec.return_value = ResultSet()
        engine = KingbaseEngine(instance=self.instance)
        result = engine.reset_instance_user_pwd(
            user_host="app_user@%", reset_pwd="NewPwd123!"
        )
        self.assertIsNone(result.error)
        self.assertIn("ALTER USER", mock_exec.call_args.kwargs["sql"])
        self.assertIn("PASSWORD", mock_exec.call_args.kwargs["sql"])

    # ---------- password must never reach the logs ----------
    # CREATE/ALTER USER puts the password inline, and execute() logs the failing
    # statement; without masking the plaintext password lands in the log file.
    def test_mask_pwd_in_create_user(self):
        masked = KingbaseEngine._mask_pwd_in_sql(
            "CREATE USER \"app\" PASSWORD 'Secr3t!@#'"
        )
        self.assertNotIn("Secr3t", masked)
        self.assertIn("******", masked)

    def test_mask_pwd_is_case_insensitive(self):
        masked = KingbaseEngine._mask_pwd_in_sql("alter user app password 'lowercase'")
        self.assertNotIn("lowercase", masked)
        self.assertIn("******", masked)

    def test_mask_pwd_handles_dollar_quoted(self):
        masked = KingbaseEngine._mask_pwd_in_sql(
            'ALTER USER "app" PASSWORD <<$tag$super$secre$t$tag$>>'
        )
        self.assertNotIn("super", masked)
        self.assertIn("******", masked)

    def test_mask_pwd_handles_escaped_quotes(self):
        masked = KingbaseEngine._mask_pwd_in_sql(
            "ALTER USER \"app\" PASSWORD 'it''s a secret'"
        )
        self.assertNotIn("secret", masked)
        self.assertIn("******", masked)

    def test_mask_pwd_covers_multiple_statements(self):
        masked = KingbaseEngine._mask_pwd_in_sql(
            "ALTER USER a PASSWORD 'p1'; CREATE USER b PASSWORD 'p2';"
        )
        self.assertNotIn("'p1'", masked)
        self.assertNotIn("'p2'", masked)
        self.assertEqual(masked.count("******"), 2)

    def test_mask_pwd_leaves_other_literals_alone(self):
        """Only PASSWORD literals are masked; VALID UNTIL must survive."""
        for sql in (
            "ALTER USER \"app\" VALID UNTIL '1970-01-01'",
            'DROP USER IF EXISTS "app"',
            "SELECT 1",
        ):
            self.assertEqual(KingbaseEngine._mask_pwd_in_sql(sql), sql)

    # ---------- schema-qualified object names ----------
    # Regression: methods taking tb_name/view_name must accept "schema.table",
    # otherwise objects outside "public" cannot be resolved.
    @patch.object(KingbaseEngine, "query")
    def test_describe_table_accepts_schema_qualified_name(self, mock_query):
        mock_query.return_value = ResultSet(rows=[], column_list=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.describe_table("test", "biz.orders")
        params = mock_query.call_args.kwargs["parameters"]
        self.assertEqual(params["schema_name"], "biz")
        self.assertEqual(params["tb_name"], "orders")

    @patch.object(KingbaseEngine, "query")
    def test_get_all_columns_accepts_schema_qualified_name(self, mock_query):
        mock_query.return_value = ResultSet(rows=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.get_all_columns_by_tb("test", "biz.orders")
        params = mock_query.call_args.kwargs["parameters"]
        self.assertEqual((params["schema_name"], params["tb_name"]), ("biz", "orders"))

    @patch.object(KingbaseEngine, "query")
    def test_get_table_index_data_accepts_schema_qualified_name(self, mock_query):
        mock_query.return_value = ResultSet(rows=[], column_list=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.get_table_index_data("test", "biz.orders")
        params = mock_query.call_args.kwargs["parameters"]
        self.assertEqual((params["schema_name"], params["tb_name"]), ("biz", "orders"))

    @patch.object(KingbaseEngine, "get_table_desc_data")
    @patch.object(KingbaseEngine, "query")
    def test_get_view_detail_accepts_schema_qualified_name(self, mock_query, mock_desc):
        mock_query.return_value = ResultSet(rows=[], column_list=[])
        mock_desc.return_value = {"rows": [], "column_list": []}
        engine = KingbaseEngine(instance=self.instance)
        engine.get_view_detail("test", "biz.v_orders")
        params = mock_query.call_args.kwargs["parameters"]
        self.assertEqual(
            (params["schema_name"], params["view_name"]), ("biz", "v_orders")
        )
        # schema must reach the column lookup too, not just default to public
        self.assertEqual(mock_desc.call_args.kwargs["schema_name"], "biz")

    @patch.object(KingbaseEngine, "get_table_desc_data")
    @patch.object(KingbaseEngine, "query")
    def test_get_view_detail_returns_modal_contract(self, mock_query, mock_desc):
        """The detail modal reads meta_data, desc and view_definition."""
        mock_query.return_value = ResultSet(
            rows=[("v_orders", "SELECT 1", "", "YES", "system", "", "", "")],
            column_list=[
                "view_name",
                "view_definition",
                "check_option",
                "is_updatable",
                "definer",
                "security_type",
                "character_set_client",
                "collation_connection",
            ],
        )
        mock_desc.return_value = {"rows": [], "column_list": []}
        engine = KingbaseEngine(instance=self.instance)
        detail = engine.get_view_detail("test", "public.v_orders")

        self.assertEqual(set(detail), {"meta_data", "desc", "view_definition"})
        self.assertEqual(detail["meta_data"]["rows"][0], "v_orders")
        self.assertEqual(detail["view_definition"], "SELECT 1")

    @patch.object(KingbaseEngine, "query")
    def test_get_table_meta_data_accepts_schema_qualified_name(self, mock_query):
        mock_query.return_value = ResultSet(rows=[], column_list=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.get_table_meta_data("test", "biz.orders")
        params = mock_query.call_args.kwargs["parameters"]
        self.assertEqual((params["schema_name"], params["tb_name"]), ("biz", "orders"))

    def test_split_table_name_defaults_to_public(self):
        self.assertEqual(
            KingbaseEngine._split_table_name("orders"), ("public", "orders")
        )

    def test_split_table_name_honours_explicit_schema(self):
        self.assertEqual(
            KingbaseEngine._split_table_name("orders", "biz"), ("biz", "orders")
        )

    def test_split_table_name_strips_trailing_semicolon(self):
        self.assertEqual(
            KingbaseEngine._split_table_name("biz.orders;"), ("biz", "orders")
        )

    # ---------- system schema filter must be interpolated ----------
    # Regression: the SQL templates use {_SYSTEM_SCHEMA_SQL}, which only works
    # inside an f-string. A missing "f" prefix leaks the literal placeholder
    # into the query and every call fails with a syntax error.
    def test_no_literal_placeholder_leaks_into_sql(self):
        engine = KingbaseEngine(instance=self.instance)
        captured = []

        def fake_query(*args, **kwargs):
            captured.append(kwargs.get("sql", args[0] if args else ""))
            return ResultSet(rows=[], column_list=[])

        with patch.object(KingbaseEngine, "query", side_effect=fake_query):
            engine.get_group_tables_by_db("test")
            engine.get_triggers_list("test")
            engine.get_procedures_list("test")
            engine.get_functions_list("test")
            engine.tablespace()
            engine.tablespace_count()

        self.assertTrue(captured, "no SQL captured")
        for sql in captured:
            self.assertNotIn(
                "{_SYSTEM_SCHEMA_SQL}", sql, "placeholder was not interpolated"
            )
            self.assertIn("sys_catalog", sql)

    @patch.object(KingbaseEngine, "query")
    @patch.object(KingbaseEngine, "execute")
    def test_create_instance_user_rejects_existing_account(self, mock_exec, mock_query):
        mock_query.return_value = ResultSet(rows=[(1,)])
        engine = KingbaseEngine(instance=self.instance)
        result = engine.create_instance_user(user="app_user", password1="Pwd123456!")
        self.assertIn("已存在", result.error)
        mock_exec.assert_not_called()

    # ---------- system schema filtering ----------
    # The two lists are used in different code paths (Python post-filter vs the
    # {_SYSTEM_SCHEMA_SQL} interpolation in SQL). If they drift, objects in a
    # schema that is only in one list leak into the metadata views.
    def test_system_schema_lists_stay_in_sync(self):
        sql_schemas = set(re.findall(r"'([^']+)'", _SYSTEM_SCHEMA_SQL))
        self.assertEqual(
            sql_schemas,
            set(KES_SYSTEM_SCHEMAS),
            "_SYSTEM_SCHEMA_SQL and KES_SYSTEM_SCHEMAS disagree",
        )

    def test_every_known_system_schema_is_filtered(self):
        """Schemas that actually hold objects in KES must not be exposed."""
        engine = KingbaseEngine(instance=self.instance)
        captured = []

        def fake_query(*args, **kwargs):
            captured.append(kwargs.get("sql", args[0] if args else ""))
            return ResultSet(rows=[], column_list=[])

        with patch.object(KingbaseEngine, "query", side_effect=fake_query):
            engine.get_group_tables_by_db("test")
            engine.get_triggers_list("test")

        for sql in captured:
            for schema in ("anon", "src_restrict", "sys_hm", "xlog_record_read"):
                self.assertIn(
                    f"'{schema}'",
                    sql,
                    f"system schema {schema} is not excluded from: {sql[:120]}",
                )

    # ---------- aborted-workflow rollback ----------
    def test_get_rollback_empty_on_aborted_workflow(self):
        class _Content:
            execute_result = json.dumps(
                [
                    {
                        "sql": "create table t1(id int)",
                        "stagestatus": "Execute Successfully",
                    },
                    {"sql": "create table t2(id int)", "stagestatus": "Execute Failed"},
                ]
            )

        class _Workflow:
            status = "workflow_exception"
            sqlworkflowcontent = _Content()

        engine = KingbaseEngine(instance=self.instance)
        self.assertEqual(engine.get_rollback(_Workflow()), [])

    def test_get_rollback_empty_on_failed_row(self):
        class _Content:
            execute_result = json.dumps(
                [
                    {
                        "sql": "create table t1(id int)",
                        "stagestatus": "Execute Successfully",
                    },
                    {
                        "sql": "create table t2(id int)",
                        "stagestatus": "Audit completed",
                    },
                ]
            )

        class _Workflow:
            status = "workflow_finish"
            sqlworkflowcontent = _Content()

        engine = KingbaseEngine(instance=self.instance)
        self.assertEqual(engine.get_rollback(_Workflow()), [])

    # ---------- query validation / filter_sql ----------
    def test_query_check_allows_show_create_table(self):
        engine = KingbaseEngine(instance=self.instance)
        result = engine.query_check(sql="show create table public.t;")
        self.assertFalse(result["bad_query"])

    def test_filter_sql_preserves_limit_with_offset(self):
        engine = KingbaseEngine(instance=self.instance)
        sql = "select * from t limit 10 offset 5"
        self.assertEqual(
            engine.filter_sql(sql, 100), "select * from t limit 10 offset 5;"
        )

    def test_filter_sql_appends_limit_when_absent(self):
        engine = KingbaseEngine(instance=self.instance)
        self.assertEqual(
            engine.filter_sql("select * from t", 50), "select * from t limit 50;"
        )

    # ---------- column type formatting ----------
    def test_format_column_type_user_defined_and_array(self):
        self.assertEqual(
            KingbaseEngine._format_column_type(
                "character varying", 100, None, None, "varchar"
            ),
            "character varying(100)",
        )
        self.assertEqual(
            KingbaseEngine._format_column_type("numeric", None, 12, 2, "numeric"),
            "numeric(12,2)",
        )
        self.assertEqual(
            KingbaseEngine._format_column_type("numeric", None, 12, None, "numeric"),
            "numeric(12)",
        )
        self.assertEqual(
            KingbaseEngine._format_column_type(
                "USER-DEFINED", None, None, None, "myenum"
            ),
            "myenum",
        )
        self.assertEqual(
            KingbaseEngine._format_column_type("ARRAY", None, None, None, "_int4"),
            "int4[]",
        )
        self.assertEqual(
            KingbaseEngine._format_column_type("integer", None, 32, 0, "int4"),
            "integer",
        )

    # ---------- slow query seconds ----------
    @patch.object(KingbaseEngine, "query")
    def test_slowquery_review_converts_ms_to_seconds(self, mock_query):
        mock_query.side_effect = [
            ResultSet(rows=[], column_list=[]),
            ResultSet(rows=[(5,)]),
        ]
        engine = KingbaseEngine(instance=self.instance)
        engine.slowquery_review("2024-01-01", "2024-01-02")
        sql = mock_query.call_args_list[0].kwargs["sql"]
        self.assertIn("total_exec_time / 1000.0", sql)
        self.assertIn("mean_exec_time / 1000.0", sql)

    # ---------- routine overloads ----------
    @patch.object(KingbaseEngine, "query")
    def test_routines_list_includes_argument_signature(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[("public", "myfunc", "integer, text")],
            column_list=["nspname", "proname", "args"],
        )
        engine = KingbaseEngine(instance=self.instance)
        data = engine.get_functions_list("test")
        self.assertEqual(data["m"][0][0], "myfunc(integer, text)")

    @patch.object(KingbaseEngine, "get_table_desc_data")
    @patch.object(KingbaseEngine, "query")
    def test_routine_detail_uses_signature(self, mock_query, mock_desc):
        mock_query.side_effect = [
            ResultSet(rows=[], column_list=[]),  # meta
            ResultSet(rows=[("CREATE FUNCTION ...",)], column_list=[]),  # create
        ]
        mock_desc.return_value = {"rows": [], "column_list": []}
        engine = KingbaseEngine(instance=self.instance)
        engine.get_function_detail("test", "public.myfunc(integer, text)")
        detail_sql = mock_query.call_args_list[1].kwargs["sql"]
        self.assertIn("pg_get_function_identity_arguments", detail_sql)
        self.assertEqual(
            mock_query.call_args_list[1].kwargs["parameters"]["args"],
            "integer, text",
        )

    # ---------- workflow / query execution error paths ----------
    @patch("sql.engines.kingbase.db_driver.connect")
    def test_execute_workflow_success(self, mock_connect):
        cursor = MagicMock()
        cursor.rowcount = 1
        conn = mock_connect.return_value
        conn.cursor.return_value = cursor
        workflow = Mock()
        workflow.db_name = "biz_db"
        workflow.sqlworkflowcontent.sql_content = (
            "create table t_user(id int); insert into t_user values(1);"
        )

        engine = KingbaseEngine(instance=self.instance)
        result = engine.execute_workflow(workflow)

        self.assertIsInstance(result, ReviewSet)
        self.assertFalse(result.error)
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.rows[0].stagestatus, "Execute Successfully")
        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_execute_workflow_failure_rolls_back_and_marks_trailing(self, mock_connect):
        cursor = MagicMock()
        cursor.rowcount = 0
        cursor.execute.side_effect = [None, None, RuntimeError("boom")]
        conn = mock_connect.return_value
        conn.cursor.return_value = cursor
        workflow = Mock()
        workflow.db_name = "biz_db"
        workflow.sqlworkflowcontent.sql_content = (
            "insert into t values(1); insert into t values(2); insert into t values(3);"
        )

        engine = KingbaseEngine(instance=self.instance)
        result = engine.execute_workflow(workflow)

        conn.rollback.assert_called_once()
        self.assertEqual(result.error, "boom")
        failed = [r for r in result.rows if r.stagestatus == "Execute Failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].errlevel, 2)
        skipped = [r for r in result.rows if r.stagestatus == "Audit completed"]
        self.assertEqual(len(skipped), 1)
        self.assertIn("未执行", skipped[0].errormessage)

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_execute_workflow_failure_masks_password(self, mock_connect):
        cursor = MagicMock()
        cursor.execute.side_effect = RuntimeError("create user failed")
        conn = mock_connect.return_value
        conn.cursor.return_value = cursor
        workflow = Mock()
        workflow.db_name = "biz_db"
        workflow.sqlworkflowcontent.sql_content = "create user bob password 's3cr3t';"

        with self.assertLogs("default", level="WARNING") as captured:
            engine = KingbaseEngine(instance=self.instance)
            engine.execute_workflow(workflow)

        joined = "\n".join(captured.output)
        self.assertNotIn("s3cr3t", joined)
        self.assertIn("******", joined)

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_execute_success(self, mock_connect):
        cursor = MagicMock()
        conn = mock_connect.return_value
        conn.cursor.return_value = cursor

        engine = KingbaseEngine(instance=self.instance)
        result = engine.execute(sql="insert into t values(1); insert into t values(2);")

        self.assertFalse(result.error)
        conn.commit.assert_called_once()
        cursor.close.assert_called_once()
        self.assertEqual(cursor.execute.call_count, 2)

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_execute_failure_rolls_back_and_masks_password(self, mock_connect):
        cursor = MagicMock()
        cursor.execute.side_effect = RuntimeError("alter user failed")
        conn = mock_connect.return_value
        conn.cursor.return_value = cursor

        with self.assertLogs("default", level="WARNING") as captured:
            engine = KingbaseEngine(instance=self.instance)
            result = engine.execute(sql="alter user bob password 'hunter2';")

        conn.rollback.assert_called_once()
        self.assertEqual(result.error, "alter user failed")
        joined = "\n".join(captured.output)
        self.assertNotIn("hunter2", joined)
        self.assertIn("******", joined)

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_query_failure_rolls_back_and_masks_password(self, mock_connect):
        cursor = MagicMock()
        cursor.execute.side_effect = RuntimeError("bad sql")
        conn = mock_connect.return_value
        conn.cursor.return_value = cursor

        with self.assertLogs("default", level="WARNING") as captured:
            engine = KingbaseEngine(instance=self.instance)
            result = engine.query(
                sql="select * from t where note = 'PASSWORD 'secret'';"
            )

        conn.rollback.assert_called_once()
        self.assertEqual(result.error, "bad sql")
        joined = "\n".join(captured.output)
        self.assertNotIn("secret", joined)
        self.assertIn("******", joined)

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_query_with_schema_sets_search_path(self, mock_connect):
        cursor = MagicMock()
        cursor.fetchall.return_value = [(1,)]
        cursor.description = [("id", 23)]
        conn = mock_connect.return_value
        conn.cursor.return_value = cursor

        engine = KingbaseEngine(instance=self.instance)
        result = engine.query(sql="select id from t", schema_name="biz")

        self.assertEqual(result.rows, [(1,)])
        execute_sqls = [c.args[0] for c in cursor.execute.call_args_list]
        self.assertTrue(any("search_path" in str(s) for s in execute_sqls))

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_query_json_values_are_serialized(self, mock_connect):
        cursor = MagicMock()
        cursor.fetchall.return_value = [({"a": 1}, [1, 2])]
        cursor.description = [("j", 114), ("arr", 3802)]
        conn = mock_connect.return_value
        conn.cursor.return_value = cursor

        engine = KingbaseEngine(instance=self.instance)
        result = engine.query(sql="select j, arr from t")

        self.assertEqual(result.rows[0][0], '{"a": 1}')
        self.assertEqual(result.rows[0][1], "[1, 2]")

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_query_intercepts_show_create_table(self, mock_connect):
        engine = KingbaseEngine(instance=self.instance)
        with patch.object(engine, "show_create_table") as mock_show_create:
            mock_show_create.return_value = ResultSet(rows=[("t", "create table t")])
            result = engine.query(sql="show create table public.t;")
        mock_show_create.assert_called_once()
        self.assertEqual(result.rows[0][1], "create table t")

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_query_statement_timeout_failure_is_ignored(self, mock_connect):
        cursor = MagicMock()
        cursor.fetchall.return_value = [(1,)]
        cursor.description = [("id", 23)]
        cursor.execute.side_effect = [
            RuntimeError("timeout unsupported"),
            None,
            None,
            None,
        ]
        conn = mock_connect.return_value
        conn.cursor.return_value = cursor

        engine = KingbaseEngine(instance=self.instance)
        result = engine.query(sql="select id from t", max_execution_time=1000)

        self.assertEqual(result.rows, [(1,)])

    # ---------- query_check / filter_sql edge paths ----------
    def test_query_check_empty_sql(self):
        engine = KingbaseEngine(instance=self.instance)
        result = engine.query_check(sql="-- just a comment")
        self.assertTrue(result["bad_query"])

    def test_query_check_flags_star(self):
        engine = KingbaseEngine(instance=self.instance)
        result = engine.query_check(sql="select * from t")
        self.assertTrue(result["has_star"])
        self.assertIn("*", result["msg"])

    def test_filter_sql_preserves_native_limit_variants(self):
        engine = KingbaseEngine(instance=self.instance)
        cases = [
            "select 1 limit 10",
            "select 1 limit 10, 20",
            "select 1 limit 10 offset 20",
            "select 1 limit 10 offset 20 rows",
        ]
        for sql in cases:
            self.assertEqual(engine.filter_sql(sql=sql, limit_num=100), f"{sql};")

    def test_query_masking_select_only(self):
        engine = KingbaseEngine(instance=self.instance)
        rs = ResultSet(rows=[(1,)])
        with patch("sql.engines.kingbase.simple_column_mask") as mock_mask:
            mock_mask.return_value = rs
            result = engine.query_masking(sql="select 1", resultset=rs)
        self.assertTrue(result.is_masked)

        untouched = engine.query_masking(sql="update t set a=1", resultset=rs)
        self.assertIs(untouched, rs)

    # ---------- version fallback paths ----------
    @patch.object(KingbaseEngine, "query")
    def test_server_version_pg_style_fallback(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("PostgreSQL 12.3",)])
        self.assertEqual(
            KingbaseEngine(instance=self.instance).server_version, (12, 3, 0)
        )

    @patch.object(KingbaseEngine, "query")
    def test_server_version_unparseable(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("unknown",)])
        self.assertEqual(KingbaseEngine(instance=self.instance).server_version, ())

    # ---------- execute_check remaining branches ----------
    @patch("sql.engines.kingbase.SysConfig")
    def test_execute_check_critical_ddl_regex(self, mock_sys_config):
        mock_sys_config.return_value.get.return_value = "drop\\s+table\\s+critical"
        engine = KingbaseEngine(instance=self.instance)
        result = engine.execute_check(sql="drop table critical")
        self.assertEqual(result.rows[0].errlevel, 2)
        self.assertEqual(result.rows[0].stagestatus, "驳回高危SQL")

    @patch("sql.engines.kingbase.SysConfig")
    def test_execute_check_skips_empty_statements(self, mock_sys_config):
        mock_sys_config.return_value.get.return_value = ""
        engine = KingbaseEngine(instance=self.instance)
        result = engine.execute_check(sql="-- comment only")
        self.assertEqual(result.rows, [])

    @patch("sql.engines.kingbase.SysConfig")
    def test_execute_check_delete_without_where_warns(self, mock_sys_config):
        mock_sys_config.return_value.get.return_value = ""
        engine = KingbaseEngine(instance=self.instance)
        result = engine.execute_check(sql="delete from t")
        self.assertEqual(result.rows[0].errlevel, 1)
        self.assertEqual(result.warning_count, 1)

    @patch("sql.engines.kingbase.SysConfig")
    def test_execute_check_counts_errors_and_warnings(self, mock_sys_config):
        mock_sys_config.return_value.get.return_value = ""
        engine = KingbaseEngine(instance=self.instance)
        result = engine.execute_check(
            sql="select 1; drop table t; update t set a=1; insert into t values(1)"
        )
        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.warning_count, 2)

    # ---------- rollback / workflow remaining paths ----------
    def test_get_rollback_invalid_json(self):
        class _Content:
            execute_result = "not-json"

        class _Workflow:
            status = "workflow_finish"
            sqlworkflowcontent = _Content()

        engine = KingbaseEngine(instance=self.instance)
        self.assertEqual(engine.get_rollback(_Workflow()), [])

    def test_get_rollback_generates_reverse_statements(self):
        class _Content:
            execute_result = json.dumps(
                [
                    {
                        "sql": "create table t1(id int)",
                        "stagestatus": "Execute Successfully",
                    },
                    {
                        "sql": "alter table t2 add column c int",
                        "stagestatus": "Execute Successfully",
                    },
                ]
            )

        class _Workflow:
            status = "workflow_finish"
            sqlworkflowcontent = _Content()

        engine = KingbaseEngine(instance=self.instance)
        rollback = engine.get_rollback(_Workflow())
        self.assertEqual(len(rollback), 2)
        self.assertEqual(rollback[1][0], "create table t1(id int)")
        self.assertEqual(rollback[1][1], "DROP TABLE IF EXISTS t1;")

    def test_rollback_empty_source_returns_unsupported(self):
        self.assertEqual(
            KingbaseEngine._build_metadata_rollback_sql(""),
            _ROLLBACK_UNSUPPORTED,
        )

    def test_rollback_drop_column_cannot_restore(self):
        self.assertIn(
            "DROP COLUMN",
            KingbaseEngine._build_metadata_rollback_sql("alter table t drop column c"),
        )

    def test_rollback_rename_table_no_schema(self):
        self.assertEqual(
            KingbaseEngine._build_metadata_rollback_sql("alter table t rename to t2"),
            "ALTER TABLE t2 RENAME TO t;",
        )

    def test_rollback_rename_table_with_schema(self):
        self.assertEqual(
            KingbaseEngine._build_metadata_rollback_sql(
                "alter table public.t rename to t2"
            ),
            "ALTER TABLE public.t2 RENAME TO t;",
        )

    def test_execute_workflow_skips_blank_statements(self):
        with patch("sql.engines.kingbase.db_driver.connect") as mock_connect:
            cursor = MagicMock()
            cursor.rowcount = 1
            conn = mock_connect.return_value
            conn.cursor.return_value = cursor
            workflow = Mock()
            workflow.db_name = "biz_db"
            workflow.sqlworkflowcontent.sql_content = ";; create table t(id int); ;"
            engine = KingbaseEngine(instance=self.instance)
            result = engine.execute_workflow(workflow)
        self.assertEqual(len(result.rows), 1)

    # ---------- data dictionary metadata ----------
    @patch.object(KingbaseEngine, "get_table_desc_data")
    @patch.object(KingbaseEngine, "get_group_tables_by_db")
    def test_get_tables_metas_data(self, mock_group, mock_desc):
        mock_group.return_value = {
            "t": [("t_user", "users table")],
        }
        mock_desc.return_value = {
            "rows": [
                ("id", "int", None, "NO", "PRI", None, None, "pk"),
                ("name", "varchar", None, "YES", "", None, None, ""),
            ]
        }
        engine = KingbaseEngine(instance=self.instance)
        metas = engine.get_tables_metas_data("test")
        self.assertEqual(len(metas), 1)
        self.assertEqual(metas[0]["TABLE_INFO"]["TABLE_NAME"], "t_user")
        self.assertEqual(len(metas[0]["COLUMNS"]), 2)
        self.assertEqual(metas[0]["COLUMNS"][0]["COLUMN_NAME"], "id")

    # ---------- account summary ----------
    @patch.object(KingbaseEngine, "query")
    def test_get_instance_users_summary(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[("bob", "%", "bob@%", 16384, True, False, "", None)],
            column_list=[
                "user",
                "host",
                "user_host",
                "user_id",
                "can_create_db",
                "is_superuser",
                "is_locked",
                "expiry_time",
            ],
        )
        engine = KingbaseEngine(instance=self.instance)
        result = engine.get_instance_users_summary()
        self.assertFalse(result.error)
        self.assertIsInstance(result.rows[0], dict)
        self.assertFalse(result.rows[0]["saved"])

    @patch.object(KingbaseEngine, "query")
    def test_get_instance_users_summary_query_error(self, mock_query):
        mock_query.return_value = make_error_result("boom")
        engine = KingbaseEngine(instance=self.instance)
        result = engine.get_instance_users_summary()
        self.assertEqual(result.error, "boom")

    # ---------- show_create_table error paths ----------
    @patch.object(KingbaseEngine, "query")
    def test_show_create_table_query_error(self, mock_query):
        mock_query.return_value = make_error_result("boom")
        engine = KingbaseEngine(instance=self.instance)
        result = engine.show_create_table(
            db_name="test", table_name="public.t", close_conn=False
        )
        self.assertEqual(result.error, "boom")

    @patch.object(KingbaseEngine, "query")
    def test_show_create_table_missing_table(self, mock_query):
        mock_query.return_value = ResultSet(rows=[], column_list=[])
        engine = KingbaseEngine(instance=self.instance)
        result = engine.show_create_table(
            db_name="test", table_name="public.t", close_conn=False
        )
        self.assertIn("不存在", result.error)

    @patch.object(KingbaseEngine, "query")
    def test_show_create_table_with_default_and_index(self, mock_query):
        mock_query.side_effect = [
            ResultSet(
                rows=[
                    ("id", "integer", None, None, None, "NO", "nextval('seq')", "int4")
                ],
                column_list=[],
            ),
            ResultSet(rows=[("p", "PRIMARY KEY (id)")], column_list=[]),
            ResultSet(
                rows=[("idx_t_id", "CREATE INDEX idx_t_id ON t(id)")], column_list=[]
            ),
        ]
        engine = KingbaseEngine(instance=self.instance)
        result = engine.show_create_table(db_name="test", table_name="public.t")
        self.assertIn("DEFAULT nextval", result.rows[0][1])
        self.assertIn("CREATE INDEX", result.rows[0][1])

    # ---------- slow query error paths ----------
    @patch.object(KingbaseEngine, "query")
    def test_slowquery_review_query_error(self, mock_query):
        mock_query.return_value = make_error_result("boom")
        engine = KingbaseEngine(instance=self.instance)
        result = engine.slowquery_review("2026-01-01", "2026-01-02", db_name="test")
        self.assertEqual(result["error"], "boom")

    @patch.object(KingbaseEngine, "query")
    def test_slowquery_review_history_query_error(self, mock_query):
        mock_query.return_value = make_error_result("boom")
        engine = KingbaseEngine(instance=self.instance)
        result = engine.slowquery_review_history("2026-01-01", "2026-01-02")
        self.assertEqual(result["error"], "boom")

    @patch.object(KingbaseEngine, "query")
    def test_slowquery_review_count_error(self, mock_query):
        good = ResultSet(rows=[], column_list=[])
        bad = make_error_result("count failed")
        mock_query.side_effect = [good, bad]
        engine = KingbaseEngine(instance=self.instance)
        result = engine.slowquery_review("2026-01-01", "2026-01-02")
        self.assertEqual(result["error"], "count failed")

    @patch.object(KingbaseEngine, "query")
    def test_slowquery_review_history_filters(self, mock_query):
        good = ResultSet(rows=[], column_list=[])
        mock_query.side_effect = [good, good]
        engine = KingbaseEngine(instance=self.instance)
        result = engine.slowquery_review_history(
            "2026-01-01",
            "2026-01-02",
            db_name="test",
            search="SELECT",
            sort_name="DBName",
            sort_order="asc",
        )
        sql = mock_query.call_args_list[0].kwargs["sql"]
        self.assertIn("ILIKE", sql)
        self.assertIn('"DBName"', sql)
        self.assertIn("ASC", sql)
        self.assertEqual(result["total"], 0)

    # ---------- variables ----------
    @patch.object(KingbaseEngine, "query")
    def test_get_variables_with_filter(self, mock_query):
        mock_query.return_value = ResultSet(rows=[], column_list=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.get_variables(["shared_buffers"])
        self.assertEqual(
            mock_query.call_args.kwargs["parameters"],
            {"variables": ["shared_buffers"]},
        )

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_set_variable_success(self, mock_connect):
        conn = mock_connect.return_value
        cursor = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        engine = KingbaseEngine(instance=self.instance)
        result = engine.set_variable("work_mem", "4MB")
        self.assertFalse(result.error)
        self.assertEqual(result.affected_rows, 1)
        cursor.execute.assert_any_call('ALTER SYSTEM SET "work_mem" = %s;', ("4MB",))

    @patch("sql.engines.kingbase.db_driver.connect")
    def test_set_variable_error(self, mock_connect):
        conn = mock_connect.return_value
        cursor = MagicMock()
        cursor.execute.side_effect = RuntimeError("permission denied")
        conn.cursor.return_value.__enter__.return_value = cursor
        engine = KingbaseEngine(instance=self.instance)
        result = engine.set_variable("work_mem", "4MB")
        self.assertIn("permission denied", result.error)
        conn.rollback.assert_called_once()

    # ---------- diagnostics remaining ----------
    @patch.object(KingbaseEngine, "query")
    def test_kill_connection_query_error(self, mock_query):
        mock_query.return_value = make_error_result("boom")
        engine = KingbaseEngine(instance=self.instance)
        self.assertEqual(engine.get_kill_command(["123"]), [])

    def test_kill_invalid_ids(self):
        engine = KingbaseEngine(instance=self.instance)
        result = engine.kill(["abc"])
        self.assertIn("no valid thread ids", result.error)

    @patch.object(KingbaseEngine, "query")
    def test_kill_valid_ids(self, mock_query):
        mock_query.return_value = ResultSet(rows=[], column_list=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.kill(["123", "456"])
        self.assertEqual(mock_query.call_args.kwargs["parameters"], ([123, 456],))

    @patch.object(KingbaseEngine, "query")
    def test_tablespace_with_search(self, mock_query):
        mock_query.return_value = ResultSet(rows=[], column_list=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.tablespace(offset=0, row_count=14, schema_search="public")
        self.assertIn(
            "%public%", mock_query.call_args.kwargs["parameters"]["schema_search"]
        )

    @patch.object(KingbaseEngine, "query")
    def test_tablespace_count_with_search(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("1",)], column_list=[])
        engine = KingbaseEngine(instance=self.instance)
        result = engine.tablespace_count(schema_search="public")
        self.assertIsInstance(result, ResultSet)
        self.assertIn(
            "%public%", mock_query.call_args.kwargs["parameters"]["schema_search"]
        )

    # ---------- trigger listing ----------
    @patch.object(KingbaseEngine, "query")
    def test_get_triggers_list(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[("public", "trg_a", "trigger a")], column_list=[]
        )
        engine = KingbaseEngine(instance=self.instance)
        data = engine.get_triggers_list("test")
        self.assertEqual(data["t"][0][1], "trigger a")

    # ---------- AI review round 5 fixes ----------
    def test_rollback_quoted_qualified_name(self):
        self.assertEqual(
            KingbaseEngine._build_metadata_rollback_sql(
                'create table "app"."orders" (id int)'
            ),
            'DROP TABLE IF EXISTS "app"."orders";',
        )

    def test_rollback_mixed_qualified_name(self):
        self.assertEqual(
            KingbaseEngine._build_metadata_rollback_sql(
                'create table app."orders" (id int)'
            ),
            'DROP TABLE IF EXISTS app."orders";',
        )

    def test_slowquery_sql_has_no_python_comments(self):
        engine = KingbaseEngine(instance=self.instance)
        with patch.object(engine, "query") as mock_query:
            mock_query.side_effect = [
                ResultSet(rows=[], column_list=[]),
                ResultSet(rows=[], column_list=[]),
            ]
            engine.slowquery_review("2026-01-01", "2026-01-02")
        sql = mock_query.call_args_list[0].kwargs["sql"]
        self.assertNotIn("\n                #", sql)
        self.assertIn("-- sys_stat_statements reports milliseconds", sql)

    def test_show_create_table_identity_column(self):
        mock_cols = ResultSet(
            rows=[
                (
                    "id",
                    "integer",
                    None,
                    None,
                    None,
                    "NO",
                    None,
                    "int4",
                    "YES",
                    "BY DEFAULT",
                    "NO",
                    None,
                )
            ],
            column_list=[],
        )
        with patch.object(KingbaseEngine, "query") as mock_query:
            mock_query.side_effect = [
                mock_cols,
                ResultSet(rows=[], column_list=[]),
                ResultSet(rows=[], column_list=[]),
            ]
            engine = KingbaseEngine(instance=self.instance)
            result = engine.show_create_table(db_name="test", table_name="public.t")
        ddl = result.rows[0][1]
        self.assertIn('"id" integer GENERATED BY DEFAULT AS IDENTITY', ddl)
        self.assertIn("NOT NULL", ddl)

    def test_show_create_table_generated_column(self):
        mock_cols = ResultSet(
            rows=[
                (
                    "total",
                    "numeric",
                    None,
                    None,
                    None,
                    "YES",
                    None,
                    "numeric",
                    "NO",
                    "",
                    "YES",
                    "(price * qty)",
                )
            ],
            column_list=[],
        )
        with patch.object(KingbaseEngine, "query") as mock_query:
            mock_query.side_effect = [
                mock_cols,
                ResultSet(rows=[], column_list=[]),
                ResultSet(rows=[], column_list=[]),
            ]
            engine = KingbaseEngine(instance=self.instance)
            result = engine.show_create_table(db_name="test", table_name="public.t")
        ddl = result.rows[0][1]
        self.assertIn("GENERATED ALWAYS AS (price * qty) STORED", ddl)

    @patch.object(KingbaseEngine, "query")
    def test_processlist_uses_configured_db(self, mock_query):
        mock_query.return_value = ResultSet(rows=[], column_list=[])
        engine = KingbaseEngine(instance=self.instance)
        engine.processlist("Not Idle")
        self.assertIsNone(mock_query.call_args.kwargs.get("db_name"))

    def test_show_create_table_queries_identity_columns(self):
        with patch.object(KingbaseEngine, "query") as mock_query:
            mock_query.side_effect = [
                ResultSet(rows=[], column_list=[]),
            ]
            engine = KingbaseEngine(instance=self.instance)
            engine.show_create_table(db_name="test", table_name="public.t")
        sql = mock_query.call_args_list[0].kwargs["sql"]
        self.assertIn("is_identity", sql)
        self.assertIn("identity_generation", sql)
        self.assertIn("generation_expression", sql)
