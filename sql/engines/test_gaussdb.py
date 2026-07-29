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
                    ("id", "integer", None, 32, 0, "NO", None),
                    ("name", "character varying", 32, None, None, "YES", None),
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
                    ("id", "integer", None, 32, 0, "NO", None),
                    (
                        "name",
                        "character varying",
                        32,
                        None,
                        None,
                        "YES",
                        "'n/a'::varchar",
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
