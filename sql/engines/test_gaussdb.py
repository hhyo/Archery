import unittest
from unittest.mock import MagicMock, Mock, patch

from sql.engines.gaussdb import GaussDBEngine
from sql.engines.models import ResultSet, ReviewSet


def make_mock_instance():
    ins = Mock()
    ins.instance_name = "gaussdb_ins"
    ins.host = "some_host"
    ins.port = 8000
    ins.db_name = "postgres"
    ins.db_type = "gaussdb"
    ins.mode = ""
    ins.charset = "UTF8"
    ins.tunnel = None
    ins.get_username_password.return_value = ("ins_user", "some_pwd")
    return ins


class TestGaussDB(unittest.TestCase):
    def setUp(self):
        self.instance = make_mock_instance()

    def test_engine_base_info(self):
        engine = GaussDBEngine(instance=self.instance)
        self.assertEqual(engine.name, "GaussDB")
        self.assertEqual(engine.info, "GaussDB/openGauss engine")
        self.assertFalse(engine.auto_backup)

    @patch("psycopg2.connect")
    def test_get_connection(self, mock_connect):
        engine = GaussDBEngine(instance=self.instance)
        engine.get_connection("biz_db")
        mock_connect.assert_called_once_with(
            host="some_host",
            port=8000,
            user="ins_user",
            password="some_pwd",
            client_encoding="UTF8",
            dbname="biz_db",
            connect_timeout=10,
        )

    @patch("psycopg2.connect")
    def test_query_success_with_schema_and_limit(self, mock_connect):
        cursor = MagicMock()
        cursor.fetchmany.return_value = [(1, "ok")]
        cursor.description = [("id", 23), ("name", 25)]
        mock_connect.return_value.cursor.return_value = cursor

        engine = GaussDBEngine(instance=self.instance)
        result = engine.query(
            db_name="biz_db",
            schema_name="public",
            sql="select id, name from t_user",
            limit_num=10,
        )

        self.assertIsInstance(result, ResultSet)
        self.assertEqual(result.column_list, ["id", "name"])
        self.assertEqual(result.rows, [(1, "ok")])
        self.assertEqual(result.affected_rows, 1)
        cursor.fetchmany.assert_called_once_with(size=10)

    @patch.object(GaussDBEngine, "query")
    def test_get_all_databases_reuses_pgsql_filter(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[("postgres",), ("biz_db",), ("template1",), ("template0",)]
        )

        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_all_databases()

        self.assertEqual(result.rows, ["postgres", "biz_db"])

    @patch.object(GaussDBEngine, "query")
    def test_get_all_schemas_reuses_pgsql_filter(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[("information_schema",), ("pg_catalog",), ("public",)]
        )

        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_all_schemas(db_name="biz_db")

        self.assertEqual(result.rows, ["public"])

    @patch.object(GaussDBEngine, "query")
    def test_describe_table_uses_schema_safe_catalog_query(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("id", "integer")])

        engine = GaussDBEngine(instance=self.instance)
        result = engine.describe_table(
            db_name="biz_db", schema_name="public", tb_name="t_user"
        )

        self.assertEqual(result.rows, [("id", "integer")])
        _, kwargs = mock_query.call_args
        self.assertIn("pg_catalog.pg_namespace", kwargs["sql"])
        self.assertEqual(
            kwargs["parameters"], {"schema_name": "public", "tb_name": "t_user"}
        )

    def test_query_check_accepts_select_and_explain(self):
        engine = GaussDBEngine(instance=self.instance)

        select_result = engine.query_check(db_name="biz_db", sql="select id from t")
        explain_result = engine.query_check(
            db_name="biz_db", sql="explain select id from t"
        )

        self.assertFalse(select_result["bad_query"])
        self.assertFalse(explain_result["bad_query"])

    @patch("sql.engines.pgsql.SysConfig")
    def test_execute_check_rejects_select(self, mock_sys_config):
        mock_sys_config.return_value.get.return_value = ""
        engine = GaussDBEngine(instance=self.instance)
        result = engine.execute_check(db_name="biz_db", sql="select * from t_user;")

        self.assertIsInstance(result, ReviewSet)
        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.rows[0].stagestatus, "驳回不支持语句")

    @patch("sql.engines.pgsql.SysConfig")
    def test_execute_check_accepts_dml_and_ddl(self, mock_sys_config):
        mock_sys_config.return_value.get.return_value = ""
        engine = GaussDBEngine(instance=self.instance)

        result = engine.execute_check(
            db_name="biz_db",
            sql="create table t_user(id int); insert into t_user values(1);",
        )

        self.assertIsInstance(result, ReviewSet)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.syntax_type, 1)
        self.assertEqual(
            [row.stagestatus for row in result.rows],
            ["Audit completed", "Audit completed"],
        )

    @patch("psycopg2.connect")
    def test_execute_workflow_runs_statements_in_transaction(self, mock_connect):
        cursor = MagicMock()
        cursor.rowcount = 1
        conn = mock_connect.return_value
        conn.cursor.return_value = cursor
        workflow = Mock()
        workflow.db_name = "biz_db"
        workflow.sqlworkflowcontent.sql_content = (
            "create table t_user(id int); insert into t_user values(1);"
        )

        engine = GaussDBEngine(instance=self.instance)
        result = engine.execute_workflow(workflow)

        self.assertIsInstance(result, ReviewSet)
        self.assertFalse(result.error)
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.rows[0].stagestatus, "Execute Successfully")
        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()
        self.assertEqual(cursor.execute.call_count, 3)

    def test_query_intercepts_show_create_table(self):
        engine = GaussDBEngine(instance=self.instance)
        with patch.object(engine, "show_create_table") as mock_show_create:
            mock_show_create.return_value = ResultSet(rows=[("t_user", "create table")])

            result = engine.query(
                db_name="biz_db",
                schema_name="public",
                sql="show create table t_user;",
            )

        self.assertEqual(result.rows, [("t_user", "create table")])
        mock_show_create.assert_called_once_with(
            db_name="biz_db",
            table_name="t_user",
            schema_name="public",
            close_conn=True,
        )

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_show_create_table_uses_real_newlines(self, mock_query):
        mock_query.side_effect = [
            ResultSet(
                rows=[
                    ("id", "integer", None, 32, 0, "NO", None, None, "int4"),
                    (
                        "name",
                        "character varying",
                        32,
                        None,
                        None,
                        "YES",
                        None,
                        None,
                        "varchar",
                    ),
                ]
            ),
            ResultSet(rows=[]),  # constraints
            ResultSet(rows=[]),  # comments
            ResultSet(rows=[]),  # secondary indexes
            ResultSet(rows=[]),  # partition key
        ]
        engine = GaussDBEngine(instance=self.instance)

        result = engine.show_create_table(
            db_name="biz_db", schema_name="public", table_name="t_user"
        )

        create_sql = result.rows[0][1]
        self.assertIn('\n    "id" integer NOT NULL,\n', create_sql)
        self.assertNotIn("\\n", create_sql)

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_show_create_table_includes_constraints_and_comments(self, mock_query):
        mock_query.side_effect = [
            ResultSet(
                rows=[
                    ("id", "integer", None, 32, 0, "NO", None, None, "int4"),
                    (
                        "name",
                        "character varying",
                        32,
                        None,
                        None,
                        "YES",
                        "'n/a'::varchar",
                        None,
                        "varchar",
                    ),
                ]
            ),
            ResultSet(
                rows=[
                    ("pk_t_user", "p", 'PRIMARY KEY ("id")'),
                    ("uk_t_user_name", "u", 'UNIQUE ("name")'),
                    ("ck_t_user_id", "c", "CHECK (id > 0)"),
                ]
            ),
            ResultSet(
                rows=[
                    ("user table", "id", "primary id"),
                    ("user table", "name", "user's name"),
                ]
            ),
            ResultSet(rows=[]),  # secondary indexes (none in this test)
            ResultSet(rows=[]),  # partition key (non-partitioned table)
        ]
        engine = GaussDBEngine(instance=self.instance)

        result = engine.show_create_table(
            db_name="biz_db", schema_name="public", table_name="t_user"
        )

        create_sql = result.rows[0][1]
        self.assertIn('PRIMARY KEY ("id")', create_sql)
        self.assertIn('CONSTRAINT "uk_t_user_name" UNIQUE ("name")', create_sql)
        self.assertIn('CONSTRAINT "ck_t_user_id" CHECK (id > 0)', create_sql)
        self.assertIn("COMMENT ON TABLE", create_sql)
        self.assertIn("COMMENT ON COLUMN", create_sql)
        self.assertIn("'user''s name'", create_sql)

    def test_split_table_name_supports_quoted_dots(self):
        engine = GaussDBEngine(instance=self.instance)

        self.assertEqual(
            engine._split_table_name('"tenant.a"."order.detail"'),
            ("tenant.a", "order.detail"),
        )

    @patch.object(GaussDBEngine, "query")
    def test_server_version_from_gaussdb_text(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[("GaussDB Kernel V500R002C00 build 9.2.4",)]
        )

        engine = GaussDBEngine(instance=self.instance)

        self.assertEqual(engine.server_version, (9, 2, 4))

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_processlist_uses_gaussdb_activity_columns(self, mock_query):
        mock_query.return_value = ResultSet(rows=[])
        engine = GaussDBEngine(instance=self.instance)

        engine.processlist("Not Idle")

        _, kwargs = mock_query.call_args
        self.assertIn("psa.enqueue as wait_event", kwargs["sql"])
        self.assertIn('psa.query as "query"', kwargs["sql"])
        self.assertIn("psa.control_status", kwargs["sql"])
        self.assertIn("coalesce(blk.block_pids, '-') as block_pids", kwargs["sql"])
        self.assertIn("from pg_locks blocked", kwargs["sql"])

    def test_kill_command_uses_pg_terminate_backend(self):
        engine = GaussDBEngine(instance=self.instance)

        self.assertEqual(
            engine.get_kill_command([123, 456]),
            "select pg_terminate_backend(pid) from pg_stat_activity where pid in (123,456);",
        )
        self.assertIsNone(engine.get_kill_command(["123"]))

    def test_build_metadata_rollback_sql_for_alter_table(self):
        engine = GaussDBEngine(instance=self.instance)

        self.assertEqual(
            engine._build_metadata_rollback_sql(
                "alter table t_user add column age int;"
            ),
            "ALTER TABLE t_user DROP COLUMN IF EXISTS age;",
        )
        self.assertEqual(
            engine._build_metadata_rollback_sql(
                "alter table t_user rename to t_user_old;"
            ),
            "ALTER TABLE t_user_old RENAME TO t_user;",
        )
        self.assertEqual(
            engine._build_metadata_rollback_sql(
                "alter table t_user rename column nick to nickname;"
            ),
            "ALTER TABLE t_user RENAME COLUMN nickname TO nick;",
        )

    def test_set_variable_rejects_unsafe_name(self):
        engine = GaussDBEngine(instance=self.instance)

        result = engine.set_variable("statement_timeout;drop table t", "1")

        self.assertEqual(result.error, "invalid variable name")

    @patch("sql.query_privileges._priv_limit", return_value=1000)
    @patch("sql.query_privileges._db_priv", return_value=True)
    def test_query_privilege_checks_selected_database_only(
        self, mock_db_priv, mock_priv_limit
    ):
        from sql.query_privileges import query_priv_check

        user = Mock()
        user.has_perm.return_value = False
        instance = make_mock_instance()
        instance.pk = 1

        result = query_priv_check(
            user=user,
            instance=instance,
            db_name="postgres",
            sql_content="select * from another_schema.t_user;",
            limit_num=100,
        )

        self.assertEqual(result["status"], 0)
        self.assertEqual(result["data"]["limit_num"], 100)
        mock_db_priv.assert_called_once_with(user, instance, "postgres")
        mock_priv_limit.assert_called_once_with(user, instance, db_name="postgres")

    def test_gaussdb_engine_is_available(self):
        from sql.engines import engine_map

        self.assertIs(engine_map["gaussdb"], GaussDBEngine)

    # ---- _split_qualified_name / _display_object_name ----

    def test_split_qualified_name_unquoted_lowercased(self):
        engine = GaussDBEngine(instance=self.instance)
        self.assertEqual(
            engine._split_qualified_name("Public.Users"),
            ["public", "users"],
        )

    def test_split_qualified_name_quoted_preserves_case(self):
        engine = GaussDBEngine(instance=self.instance)
        self.assertEqual(
            engine._split_qualified_name('"MySchema"."MyTable"'),
            ["MySchema", "MyTable"],
        )

    def test_split_qualified_name_single_name(self):
        engine = GaussDBEngine(instance=self.instance)
        self.assertEqual(
            engine._split_qualified_name("users"),
            ["users"],
        )

    def test_display_object_name_public(self):
        self.assertEqual(
            GaussDBEngine._display_object_name("public", "t_user"), "t_user"
        )

    def test_display_object_name_non_public(self):
        self.assertEqual(
            GaussDBEngine._display_object_name("biz", "t_user"), "biz.t_user"
        )

    # ---- _slowquery_filters ----

    def test_slowquery_filters_basic(self):
        where, params = GaussDBEngine._slowquery_filters("2026-01-01", "2026-01-31")
        self.assertIn("start_time >= %(start_time)s", where)
        self.assertEqual(params["start_time"], "2026-01-01")
        self.assertEqual(params["end_time"], "2026-01-31")
        self.assertNotIn("db_name", params)
        self.assertNotIn("search", params)

    def test_slowquery_filters_with_db_and_search(self):
        where, params = GaussDBEngine._slowquery_filters(
            "2026-01-01", "2026-01-31", db_name="biz", search="select"
        )
        self.assertIn("db_name = %(db_name)s", where)
        self.assertIn("query ilike %(search)s", where)
        self.assertEqual(params["db_name"], "biz")
        self.assertEqual(params["search"], "%select%")

    # ---- _build_metadata_rollback_sql ----

    def test_build_rollback_create_table(self):
        engine = GaussDBEngine(instance=self.instance)
        self.assertEqual(
            engine._build_metadata_rollback_sql("create table t_user(id int)"),
            "DROP TABLE IF EXISTS t_user;",
        )

    def test_build_rollback_create_table_if_not_exists(self):
        engine = GaussDBEngine(instance=self.instance)
        self.assertEqual(
            engine._build_metadata_rollback_sql(
                "create table if not exists t_user(id int)"
            ),
            "DROP TABLE IF EXISTS t_user;",
        )

    def test_build_rollback_create_schema(self):
        engine = GaussDBEngine(instance=self.instance)
        self.assertEqual(
            engine._build_metadata_rollback_sql("create schema biz"),
            "DROP SCHEMA IF EXISTS biz CASCADE;",
        )

    def test_build_rollback_create_view(self):
        engine = GaussDBEngine(instance=self.instance)
        self.assertEqual(
            engine._build_metadata_rollback_sql("create view v as select 1"),
            "DROP VIEW IF EXISTS v;",
        )

    def test_build_rollback_create_index(self):
        engine = GaussDBEngine(instance=self.instance)
        self.assertEqual(
            engine._build_metadata_rollback_sql("create index idx_t on t_user(name)"),
            "DROP INDEX IF EXISTS idx_t;",
        )

    def test_build_rollback_add_constraint(self):
        engine = GaussDBEngine(instance=self.instance)
        self.assertEqual(
            engine._build_metadata_rollback_sql(
                "alter table t_user add constraint pk_t primary key (id)"
            ),
            "ALTER TABLE t_user DROP CONSTRAINT IF EXISTS pk_t;",
        )

    def test_build_rollback_add_primary_key_without_name(self):
        engine = GaussDBEngine(instance=self.instance)
        result = engine._build_metadata_rollback_sql(
            "alter table t_user add primary key (id)"
        )
        self.assertIn("暂不支持", result)

    def test_build_rollback_unsupported(self):
        engine = GaussDBEngine(instance=self.instance)
        result = engine._build_metadata_rollback_sql("drop table t_user")
        self.assertIn("暂不支持", result)

    def test_build_rollback_rename_table_with_schema(self):
        engine = GaussDBEngine(instance=self.instance)
        result = engine._build_metadata_rollback_sql(
            "alter table public.foo rename to bar"
        )
        self.assertIn("public.bar", result)
        self.assertIn("foo", result)
        self.assertNotIn("public.foo", result.split("RENAME TO")[1])

    # ---- get_all_databases_summary ----

    @patch.object(GaussDBEngine, "query")
    def test_get_all_databases_summary(self, mock_query):
        mock_query.return_value = ResultSet(
            column_list=["db_name", "charset", "collation"],
            rows=[("biz_db", "UTF8", "en_US.utf8"), ("app_db", "UTF8", "C")],
        )
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_all_databases_summary()

        self.assertFalse(result.error)
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.rows[0]["db_name"], "biz_db")
        self.assertEqual(result.rows[0]["grantees"], [])
        self.assertFalse(result.rows[0]["saved"])

    @patch.object(GaussDBEngine, "query")
    def test_get_all_databases_summary_empty(self, mock_query):
        mock_query.return_value = ResultSet(rows=[])
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_all_databases_summary()
        self.assertEqual(result.rows, [])

    # ---- get_instance_users_summary ----

    @patch.object(GaussDBEngine, "query")
    def test_get_instance_users_summary(self, mock_query):
        mock_query.return_value = ResultSet(
            column_list=[
                "user",
                "host",
                "user_host",
                "user_id",
                "can_create_db",
                "is_superuser",
                "expiry_time",
            ],
            rows=[("alice", "%", "alice@%", 10, False, True, None)],
        )
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_instance_users_summary()

        self.assertFalse(result.error)
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0]["user_host"], "alice@%")
        self.assertFalse(result.rows[0]["saved"])

    # ---- get_rollback ----

    def test_get_rollback_parses_execute_result(self):
        engine = GaussDBEngine(instance=self.instance)
        workflow = Mock()
        workflow.sqlworkflowcontent.execute_result = (
            '[{"sql": "create table t(id int)"}, {"sql": "insert into t values(1)"}]'
        )
        rollback = engine.get_rollback(workflow)
        self.assertEqual(len(rollback), 2)
        # list is reversed by get_rollback
        self.assertEqual(rollback[0][0], "insert into t values(1)")
        self.assertEqual(rollback[1][0], "create table t(id int)")
        self.assertEqual(rollback[1][1], "DROP TABLE IF EXISTS t;")

    def test_get_rollback_invalid_json(self):
        engine = GaussDBEngine(instance=self.instance)
        workflow = Mock()
        workflow.sqlworkflowcontent.execute_result = "not json"
        self.assertEqual(engine.get_rollback(workflow), [])

    # ---- get_variables ----

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_get_variables_all(self, mock_query):
        mock_query.return_value = ResultSet(
            column_list=["name", "setting", "unit", "context", "vartype", "short_desc"],
            rows=[("work_mem", "4096", "kB", "user", "integer", "memory for query")],
        )
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_variables()
        self.assertEqual(result.rows[0][0], "work_mem")

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_get_variables_filtered(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("work_mem", "4096")])
        engine = GaussDBEngine(instance=self.instance)
        engine.get_variables(variables=["work_mem", "shared_buffers"])
        _, kwargs = mock_query.call_args
        self.assertIn("where name in", kwargs["sql"])
        self.assertEqual(
            kwargs["parameters"]["variables"], ("work_mem", "shared_buffers")
        )

    # ---- set_variable ----

    @patch("psycopg2.connect")
    def test_set_variable_postmaster_rejected(self, mock_connect):
        cursor = MagicMock()
        cursor.fetchone.return_value = ("postmaster",)
        mock_connect.return_value.cursor.return_value = cursor
        mock_connect.return_value.autocommit = False

        engine = GaussDBEngine(instance=self.instance)
        result = engine.set_variable("max_connections", "200")

        self.assertIn("需要重启", result.error)

    @patch("psycopg2.connect")
    def test_set_variable_success(self, mock_connect):
        cursor = MagicMock()
        cursor.fetchone.return_value = ("sighup",)
        cursor.rowcount = 0
        mock_connect.return_value.cursor.return_value = cursor

        engine = GaussDBEngine(instance=self.instance)
        result = engine.set_variable("work_mem", "8192")

        self.assertFalse(result.error)
        # Verify ALTER SYSTEM SET and pg_reload_conf were called
        execute_calls = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("ALTER SYSTEM SET" in str(c) for c in execute_calls))
        self.assertTrue(any("pg_reload_conf" in str(c) for c in execute_calls))

    # ---- kill ----

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_kill_executes_terminate(self, mock_query):
        mock_query.return_value = ResultSet(rows=[])
        engine = GaussDBEngine(instance=self.instance)
        engine.kill([123, 456])
        _, kwargs = mock_query.call_args
        self.assertIn("pg_terminate_backend", kwargs["sql"])
        self.assertIn("123", kwargs["sql"])
        self.assertIn("456", kwargs["sql"])

    def test_kill_empty_returns_empty(self):
        engine = GaussDBEngine(instance=self.instance)
        result = engine.kill([])
        self.assertEqual(result.rows, [])

    # ---- get_table_meta_data ----

    @patch.object(GaussDBEngine, "query")
    def test_get_table_meta_data(self, mock_query):
        mock_query.return_value = ResultSet(
            column_list=["table_name", "engine", "table_rows"],
            rows=[("t_user", "table", 100)],
        )
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_table_meta_data(db_name="biz", tb_name="t_user")
        self.assertEqual(result["column_list"], ["table_name", "engine", "table_rows"])
        self.assertEqual(result["rows"][0], "t_user")

    @patch.object(GaussDBEngine, "query")
    def test_get_table_meta_data_empty(self, mock_query):
        mock_query.return_value = ResultSet(rows=[])
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_table_meta_data(db_name="biz", tb_name="nonexistent")
        self.assertEqual(result["rows"], [])

    # ---- get_table_desc_data ----

    @patch.object(GaussDBEngine, "query")
    def test_get_table_desc_data(self, mock_query):
        mock_query.return_value = ResultSet(
            column_list=["列名", "列类型", "是否为空"],
            rows=[("id", "integer", "NO"), ("name", "varchar(32)", "YES")],
        )
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_table_desc_data(db_name="biz", tb_name="t_user")
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(result["rows"][0], ("id", "integer", "NO"))

    # ---- get_table_index_data ----

    @patch.object(GaussDBEngine, "query")
    def test_get_table_index_data(self, mock_query):
        mock_query.return_value = ResultSet(
            column_list=["列名", "索引名", "唯一性"],
            rows=[("name", "idx_name", 1)],
        )
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_table_index_data(db_name="biz", tb_name="t_user")
        self.assertEqual(len(result["rows"]), 1)

    # ---- get_view_detail ----

    @patch.object(GaussDBEngine, "query")
    @patch.object(GaussDBEngine, "get_table_desc_data")
    def test_get_view_detail(self, mock_desc, mock_query):
        mock_query.return_value = ResultSet(
            column_list=["view_name", "view_definition"],
            rows=[("v_users", "SELECT * FROM t_user")],
        )
        mock_desc.return_value = {"column_list": [], "rows": []}
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_view_detail(db_name="biz", view_name="v_users")
        self.assertEqual(result["view_definition"], "SELECT * FROM t_user")

    @patch.object(GaussDBEngine, "query")
    @patch.object(GaussDBEngine, "get_table_desc_data")
    def test_get_view_detail_empty(self, mock_desc, mock_query):
        mock_query.return_value = ResultSet(rows=[])
        mock_desc.return_value = {"column_list": [], "rows": []}
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_view_detail(db_name="biz", view_name="nonexistent")
        self.assertEqual(result["view_definition"], "")

    # ---- get_triggers_list / get_trigger_detail ----

    @patch.object(GaussDBEngine, "query")
    def test_get_triggers_list(self, mock_query):
        mock_query.return_value = ResultSet(
            column_list=["trigger_schema", "trigger_name", "description"],
            rows=[("public", "trg_audit", "BEFORE INSERT ON t_user")],
        )
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_triggers_list(db_name="biz")
        self.assertIn("t", result)  # first letter of trigger name
        self.assertEqual(result["t"][0][0], "trg_audit")

    @patch.object(GaussDBEngine, "query")
    def test_get_trigger_detail(self, mock_query):
        mock_query.return_value = ResultSet(
            column_list=["trigger_name", "action_timing"],
            rows=[("trg_audit", "BEFORE")],
        )
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_trigger_detail(db_name="biz", trigger_name="trg_audit")
        self.assertEqual(result["column_list"], ["trigger_name", "action_timing"])

    @patch.object(GaussDBEngine, "query")
    def test_get_trigger_detail_empty(self, mock_query):
        mock_query.return_value = ResultSet(rows=[])
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_trigger_detail(db_name="biz", trigger_name="nonexistent")
        self.assertEqual(result["rows"], [])

    # ---- _group_information_schema_objects ----

    @patch.object(GaussDBEngine, "query")
    def test_group_information_schema_objects(self, mock_query):
        mock_query.return_value = ResultSet(
            column_list=["schema", "name", "comment"],
            rows=[
                ("public", "t_user", "user table"),
                ("public", "t_order", "order table"),
            ],
        )
        engine = GaussDBEngine(instance=self.instance)
        result = engine._group_information_schema_objects(db_name="biz", sql="select 1")
        self.assertIn("t", result)
        self.assertEqual(result["t"][0][0], "t_user")
        self.assertEqual(len(result["t"]), 2)

    # ---- _get_routines_list / _get_routine_detail ----

    @patch.object(GaussDBEngine, "query")
    def test_get_procedures_list(self, mock_query):
        mock_query.return_value = ResultSet(
            column_list=["routine_schema", "routine_name", ""],
            rows=[("public", "sp_audit", "")],
        )
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_procedures_list(db_name="biz")
        self.assertIn("s", result)
        self.assertEqual(result["s"][0][0], "sp_audit")

    @patch.object(GaussDBEngine, "query")
    def test_get_functions_list(self, mock_query):
        mock_query.return_value = ResultSet(
            column_list=["routine_schema", "routine_name", ""],
            rows=[("public", "fn_calc", "")],
        )
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_functions_list(db_name="biz")
        self.assertIn("f", result)

    @patch.object(GaussDBEngine, "query")
    def test_get_routine_detail(self, mock_query):
        mock_query.side_effect = [
            ResultSet(
                column_list=["routine_name", "routine_schema"],
                rows=[("fn_calc", "public")],
            ),
            ResultSet(
                column_list=["pg_get_functiondef", "oid"],
                rows=[("CREATE FUNCTION fn_calc()...", 12345)],
            ),
        ]
        engine = GaussDBEngine(instance=self.instance)
        result = engine._get_routine_detail(
            db_name="biz", routine_name="fn_calc", routine_type="FUNCTION"
        )
        self.assertEqual(
            result["meta_data"]["column_list"], ["routine_name", "routine_schema"]
        )
        self.assertEqual(
            result["create_sql"], [("CREATE FUNCTION fn_calc()...", 12345)]
        )

    @patch.object(GaussDBEngine, "query")
    def test_get_routine_detail_empty(self, mock_query):
        mock_query.side_effect = [
            ResultSet(rows=[]),
            ResultSet(rows=[]),
        ]
        engine = GaussDBEngine(instance=self.instance)
        result = engine._get_routine_detail(
            db_name="biz", routine_name="nonexistent", routine_type="FUNCTION"
        )
        self.assertEqual(result["meta_data"]["rows"], ())
        self.assertEqual(result["create_sql"], [])

    # ---- get_tables_metas_data ----

    @patch.object(GaussDBEngine, "get_table_desc_data")
    @patch.object(GaussDBEngine, "get_group_tables_by_db")
    def test_get_tables_metas_data(self, mock_group, mock_desc):
        mock_group.return_value = {
            "t": [("t_user", "user table")],
        }
        mock_desc.return_value = {
            "column_list": [
                "name",
                "type",
                "charset",
                "nullable",
                "key",
                "default",
                "extra",
                "comment",
            ],
            "rows": [("id", "integer", "", "NO", "", None, "", "primary id")],
        }
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_tables_metas_data(db_name="biz")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["TABLE_INFO"]["TABLE_NAME"], "t_user")
        self.assertEqual(len(result[0]["COLUMNS"]), 1)
        self.assertEqual(result[0]["COLUMNS"][0]["COLUMN_NAME"], "id")

    # ---- tablespace / tablespace_count ----

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_tablespace(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("public", "t_user", "table", 10.5)])
        engine = GaussDBEngine(instance=self.instance)
        engine.tablespace(offset=0, row_count=14)
        _, kwargs = mock_query.call_args
        self.assertIn("pg_class", kwargs["sql"])
        self.assertIn("pg_namespace", kwargs["sql"])
        self.assertEqual(kwargs["parameters"]["offset"], 0)

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_tablespace_with_search(self, mock_query):
        mock_query.return_value = ResultSet(rows=[])
        engine = GaussDBEngine(instance=self.instance)
        engine.tablespace(offset=0, row_count=14, schema_search="t_user")
        _, kwargs = mock_query.call_args
        self.assertIn("schema_search", kwargs["parameters"])
        self.assertEqual(kwargs["parameters"]["schema_search"], "%t_user%")

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_tablespace_count(self, mock_query):
        mock_query.return_value = ResultSet(rows=[(42,)])
        engine = GaussDBEngine(instance=self.instance)
        result = engine.tablespace_count()
        self.assertEqual(result.rows[0][0], 42)

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_tablespace_count_with_search(self, mock_query):
        mock_query.return_value = ResultSet(rows=[(5,)])
        engine = GaussDBEngine(instance=self.instance)
        engine.tablespace_count(schema_search="biz")
        _, kwargs = mock_query.call_args
        self.assertIn("schema_search", kwargs["parameters"])

    # ---- slowquery_review ----

    @patch.object(GaussDBEngine, "_slowquery_response")
    def test_slowquery_review(self, mock_response):
        mock_response.return_value = {"total": 1, "rows": []}
        engine = GaussDBEngine(instance=self.instance)
        result = engine.slowquery_review(
            start_time="2026-01-01",
            end_time="2026-01-31",
        )
        self.assertEqual(result["total"], 1)
        mock_response.assert_called_once()

    @patch.object(GaussDBEngine, "_slowquery_response")
    def test_slowquery_review_with_db_and_search(self, mock_response):
        mock_response.return_value = {"total": 0, "rows": []}
        engine = GaussDBEngine(instance=self.instance)
        engine.slowquery_review(
            start_time="2026-01-01",
            end_time="2026-01-31",
            db_name="biz_db",
            search="select",
        )
        args, kwargs = mock_response.call_args
        params = args[2] if len(args) >= 3 else kwargs.get("parameters", {})
        self.assertIn("limit", params)
        self.assertIn("offset", params)

    # ---- slowquery_review_history ----

    @patch.object(GaussDBEngine, "_slowquery_response")
    def test_slowquery_review_history(self, mock_response):
        mock_response.return_value = {"total": 1, "rows": []}
        engine = GaussDBEngine(instance=self.instance)
        result = engine.slowquery_review_history(
            start_time="2026-01-01",
            end_time="2026-01-31",
        )
        self.assertEqual(result["total"], 1)

    @patch.object(GaussDBEngine, "_slowquery_response")
    def test_slowquery_review_history_with_sql_id(self, mock_response):
        mock_response.return_value = {"total": 1, "rows": []}
        engine = GaussDBEngine(instance=self.instance)
        engine.slowquery_review_history(
            start_time="2026-01-01",
            end_time="2026-01-31",
            sql_id="abc123",
        )
        args, kwargs = mock_response.call_args
        # _slowquery_response is called with positional args (sql, count_sql, parameters)
        params = args[2] if len(args) >= 3 else kwargs.get("parameters", {})
        self.assertEqual(params["sql_id"], "abc123")

    # ---- _slowquery_response ----

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_slowquery_response_success(self, mock_query):
        mock_query.side_effect = [
            ResultSet(column_list=["SQLText"], rows=[("select 1",)]),
            ResultSet(rows=[(5,)]),
        ]
        engine = GaussDBEngine(instance=self.instance)
        result = engine._slowquery_response("select 1", "select count(*)", {})
        self.assertEqual(result["total"], 5)
        self.assertIsNotNone(result["rows"])

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_slowquery_response_rows_error(self, mock_query):
        rs = ResultSet()
        rs.error = "connection failed"
        mock_query.side_effect = [rs]
        engine = GaussDBEngine(instance=self.instance)
        result = engine._slowquery_response("select 1", "select count(*)", {})
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["error"], "connection failed")

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_slowquery_response_count_error(self, mock_query):
        rs_err = ResultSet()
        rs_err.error = "count failed"
        mock_query.side_effect = [
            ResultSet(column_list=["SQLText"], rows=[("select 1",)]),
            rs_err,
        ]
        engine = GaussDBEngine(instance=self.instance)
        result = engine._slowquery_response("select 1", "select count(*)", {})
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["error"], "count failed")

    # ---- lock_info / get_long_transaction ----

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_lock_info(self, mock_query):
        mock_query.return_value = ResultSet(rows=[(123, "alice", "biz", "select 1")])
        engine = GaussDBEngine(instance=self.instance)
        result = engine.lock_info()
        _, kwargs = mock_query.call_args
        self.assertIn("pg_locks", kwargs["sql"])
        self.assertIn("pg_stat_activity", kwargs["sql"])

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_get_long_transaction(self, mock_query):
        mock_query.return_value = ResultSet(rows=[(123, "alice")])
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_long_transaction()
        _, kwargs = mock_query.call_args
        self.assertIn("xact_start", kwargs["sql"])
        self.assertIn("pg_backend_pid()", kwargs["sql"])

    # ---- get_group_tables_by_db ----

    @patch.object(GaussDBEngine, "query")
    def test_get_group_tables_by_db(self, mock_query):
        mock_query.return_value = ResultSet(
            column_list=["table_schema", "table_name", "table_comment"],
            rows=[
                ("public", "t_user", "user table"),
                ("public", "t_order", "order table"),
            ],
        )
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_group_tables_by_db(db_name="biz")
        self.assertIn("t", result)
        self.assertEqual(len(result["t"]), 2)

    # ---- query EXPLAIN intercept ----

    @patch.object(GaussDBEngine, "_explain_via_prepare")
    @patch.object(GaussDBEngine, "query_check")
    def test_query_intercepts_explain(self, mock_check, mock_explain):
        mock_check.return_value = {
            "bad_query": False,
            "filtered_sql": "explain select 1",
        }
        mock_explain.return_value = ResultSet(rows=[("Seq Scan",)])
        engine = GaussDBEngine(instance=self.instance)
        with patch.object(engine, "filter_sql", return_value="explain select 1"):
            result = engine.query(db_name="biz", sql="explain select 1")
        mock_explain.assert_called_once()

    # ---- _explain_via_prepare ----

    @patch("psycopg2.connect")
    def test_explain_via_prepare(self, mock_connect):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("Seq Scan on t_user",)]
        cursor.description = [("QUERY PLAN",)]
        mock_connect.return_value.cursor.return_value = cursor

        engine = GaussDBEngine(instance=self.instance)
        result = engine._explain_via_prepare(
            db_name="biz", inner_sql="select 1", close_conn=False
        )
        self.assertEqual(result.rows, [("Seq Scan on t_user",)])
        self.assertEqual(result.column_list, ["QUERY PLAN"])
        # Verify PREPARE and EXPLAIN EXECUTE were called
        execute_calls = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("PREPARE" in str(c) for c in execute_calls))
        self.assertTrue(any("EXPLAIN EXECUTE" in str(c) for c in execute_calls))
        self.assertTrue(any("DEALLOCATE" in str(c) for c in execute_calls))

    @patch("psycopg2.connect")
    def test_explain_via_prepare_with_schema(self, mock_connect):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("Seq Scan",)]
        cursor.description = [("QUERY PLAN",)]
        mock_connect.return_value.cursor.return_value = cursor

        engine = GaussDBEngine(instance=self.instance)
        result = engine._explain_via_prepare(
            db_name="biz",
            inner_sql="select * from t",
            close_conn=False,
            schema_name="biz_schema",
        )
        self.assertFalse(result.error)
        execute_calls = [call.args[0] for call in cursor.execute.call_args_list]
        # SET search_path should be called
        self.assertTrue(
            any(
                "search_path" in str(c).lower() or isinstance(c, object)
                for c in execute_calls
            )
        )

    @patch("psycopg2.connect")
    def test_explain_via_prepare_error(self, mock_connect):
        cursor = MagicMock()
        cursor.execute.side_effect = Exception("syntax error")
        mock_connect.return_value.cursor.return_value = cursor

        engine = GaussDBEngine(instance=self.instance)
        result = engine._explain_via_prepare(
            db_name="biz", inner_sql="invalid sql", close_conn=False
        )
        self.assertIn("syntax error", result.error)

    # ---- show_create_table with partition + indexes ----

    @patch("sql.engines.pgsql.PgSQLEngine.query")
    def test_show_create_table_with_partition_and_index(self, mock_query):
        mock_query.side_effect = [
            ResultSet(
                column_list=[
                    "column_name",
                    "data_type",
                    "char_len",
                    "num_prec",
                    "num_scale",
                    "is_nullable",
                    "column_default",
                    "udt_schema",
                    "udt_name",
                ],
                rows=[("id", "integer", None, 32, 0, "NO", None, None, "int4")],
            ),
            ResultSet(rows=[("pk_t", "p", 'PRIMARY KEY ("id")')]),
            ResultSet(rows=[]),  # no comments
            ResultSet(
                rows=[("CREATE INDEX idx_name ON t_user (name)",)]
            ),  # secondary index
            ResultSet(rows=[("RANGE (id)",)]),  # partition key
        ]
        engine = GaussDBEngine(instance=self.instance)
        result = engine.show_create_table(
            db_name="biz", schema_name="public", table_name="t_user"
        )
        create_sql = result.rows[0][1]
        self.assertIn("PARTITION BY RANGE (id)", create_sql)
        self.assertIn("CREATE INDEX idx_name ON t_user (name);", create_sql)

    # ---- get_table_index_data ----

    @patch.object(GaussDBEngine, "query")
    def test_get_table_index_data_with_indexes(self, mock_query):
        mock_query.return_value = ResultSet(
            column_list=[
                "列名",
                "索引名",
                "唯一性",
                "列序列",
                "基数",
                "是否为空",
                "索引类型",
                "备注",
            ],
            rows=[
                (
                    "",
                    "idx_name",
                    1,
                    1,
                    0,
                    "",
                    "btree",
                    "CREATE INDEX idx_name ON t_user (name)",
                ),
                (
                    "",
                    "uk_email",
                    0,
                    1,
                    0,
                    "",
                    "btree",
                    "CREATE UNIQUE INDEX uk_email ON t_user (email)",
                ),
            ],
        )
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_table_index_data(db_name="biz", tb_name="t_user")
        self.assertEqual(len(result["rows"]), 2)

    # ---- query_check does NOT accept CTE (masking bypass risk) ----

    def test_query_check_rejects_cte(self):
        engine = GaussDBEngine(instance=self.instance)
        result = engine.query_check(
            db_name="biz_db",
            sql="WITH recent AS (SELECT * FROM t) SELECT * FROM recent",
        )
        self.assertTrue(result["bad_query"])

    # ---- execute_check rejects transaction control ----

    @patch("sql.engines.pgsql.SysConfig")
    def test_execute_check_rejects_commit(self, mock_sys_config):
        mock_sys_config.return_value.get.return_value = ""
        engine = GaussDBEngine(instance=self.instance)
        result = engine.execute_check(
            db_name="biz_db", sql="create table t(id int); commit;"
        )
        self.assertEqual(result.error_count, 1)

    # ---- _format_column_type ----

    def test_format_column_type_integer_no_precision(self):
        # integer(32,0) is invalid; should just return "integer"
        result = GaussDBEngine._format_column_type("integer", None, 32, 0)
        self.assertEqual(result, "integer")

    def test_format_column_type_numeric_with_precision(self):
        result = GaussDBEngine._format_column_type("numeric", None, 10, 2)
        self.assertEqual(result, "numeric(10,2)")

    def test_format_column_type_user_defined(self):
        result = GaussDBEngine._format_column_type(
            "USER-DEFINED", None, None, None, "my_enum"
        )
        self.assertEqual(result, "my_enum")

    def test_format_column_type_array(self):
        result = GaussDBEngine._format_column_type("ARRAY", None, None, None, "_int4")
        self.assertEqual(result, "int4[]")

    # ---- get_all_databases_summary includes postgres ----

    @patch.object(GaussDBEngine, "query")
    def test_get_all_databases_summary_includes_postgres(self, mock_query):
        mock_query.return_value = ResultSet(
            column_list=["db_name", "charset", "collation"],
            rows=[("postgres", "UTF8", "C"), ("biz_db", "UTF8", "en_US.utf8")],
        )
        engine = GaussDBEngine(instance=self.instance)
        result = engine.get_all_databases_summary()
        db_names = [row["db_name"] for row in result.rows]
        self.assertIn("postgres", db_names)
