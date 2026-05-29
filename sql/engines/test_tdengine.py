import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sql.engines.models import ResultSet

if "taosws" not in sys.modules:
    sys.modules["taosws"] = SimpleNamespace(connect=Mock())

from sql.engines.tdengine import TDengineEngine


def make_mock_instance():
    ins = Mock()
    ins.instance_name = "td_ins"
    ins.host = "some_host"
    ins.port = 6041
    ins.db_name = "test_db"
    ins.db_type = "tdengine"
    ins.mode = ""
    ins.tunnel = None
    ins.get_username_password.return_value = ("ins_user", "some_pwd")
    return ins


class TestTDengine(unittest.TestCase):
    def setUp(self):
        self.instance = make_mock_instance()

    def test_engine_base_info(self):
        engine = TDengineEngine(instance=self.instance)
        self.assertEqual(engine.name, "TDengine")
        self.assertEqual(engine.info, "TDengine engine")
        self.assertFalse(engine.auto_backup)

    @patch("sql.engines.tdengine.escape_string")
    def test_escape_string(self, mock_escape):
        mock_escape.return_value = "escaped"
        engine = TDengineEngine(instance=self.instance)
        self.assertEqual(engine.escape_string("a'b"), "escaped")

    @patch("sql.engines.tdengine.taosws.connect")
    def test_get_connection_without_db(self, mock_connect):
        engine = TDengineEngine(instance=self.instance)
        engine.get_connection()
        mock_connect.assert_called_once_with(
            host="some_host",
            port=6041,
            user="ins_user",
            password="some_pwd",
            read_timeout="600",
        )

    @patch("sql.engines.tdengine.taosws.connect")
    def test_get_connection_with_db(self, mock_connect):
        engine = TDengineEngine(instance=self.instance)
        engine.get_connection(db_name="my_db")
        mock_connect.assert_called_once_with(
            host="some_host",
            port=6041,
            user="ins_user",
            password="some_pwd",
            database="my_db",
            read_timeout="600",
        )

    @patch("sql.engines.tdengine.taosws.connect")
    def test_get_connection_reuse(self, mock_connect):
        engine = TDengineEngine(instance=self.instance)
        engine.conn = Mock()
        conn = engine.get_connection()
        self.assertIs(conn, engine.conn)
        mock_connect.assert_not_called()

    @patch("sql.engines.tdengine.taosws.connect")
    def test_query_success_with_limit(self, mock_connect):
        cursor = Mock()
        cursor.fetchmany.return_value = [("v1", "v2")]
        cursor.description = (("k1",), ("k2",))
        mock_connect.return_value.cursor.return_value = cursor

        engine = TDengineEngine(instance=self.instance)
        rs = engine.query(sql="select 1", limit_num=1)

        cursor.execute.assert_called_once_with("select 1")
        cursor.fetchmany.assert_called_once_with(size=1)
        self.assertIsInstance(rs, ResultSet)
        self.assertEqual(rs.column_list, ["k1", "k2"])
        self.assertEqual(rs.rows, [("v1", "v2")])
        self.assertEqual(rs.affected_rows, 1)

    @patch("sql.engines.tdengine.taosws.connect")
    def test_query_with_parameters(self, mock_connect):
        cursor = Mock()
        cursor.fetchall.return_value = [("ok",)]
        cursor.description = (("col1",),)
        mock_connect.return_value.cursor.return_value = cursor

        engine = TDengineEngine(instance=self.instance)
        with patch.object(engine, "escape_string", side_effect=lambda x: x):
            rs = engine.query(
                db_name="db1",
                sql="select * from t where a='%s' and b='%s'",
                parameters=("x", "1"),
            )

        cursor.execute.assert_called_once_with("select * from t where a='x' and b='1'")
        self.assertEqual(rs.affected_rows, 1)

    @patch("sql.engines.tdengine.taosws.connect")
    def test_query_error(self, mock_connect):
        cursor = Mock()
        cursor.execute.side_effect = Exception("boom")
        mock_connect.return_value.cursor.return_value = cursor

        engine = TDengineEngine(instance=self.instance)
        rs = engine.query(sql="bad sql")
        self.assertIn("boom", rs.error)

    @patch.object(TDengineEngine, "query")
    def test_server_version(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("3.3.4.9",)])
        engine = TDengineEngine(instance=self.instance)
        self.assertTupleEqual(engine.server_version, (3, 3, 4))

    @patch.object(TDengineEngine, "query")
    def test_get_all_databases(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[
                ("information_schema",),
                ("log",),
                ("db_b",),
                ("db_a",),
            ]
        )
        engine = TDengineEngine(instance=self.instance)
        rs = engine.get_all_databases()
        self.assertEqual(rs.rows, ["db_a", "db_b"])

    @patch.object(TDengineEngine, "query")
    def test_get_all_tables(self, mock_query):
        ntable_rs = ResultSet(rows=[("n2",), ("n1",)])
        stable_rs = ResultSet(rows=[("s2",), ("s1",)])
        mock_query.side_effect = [ntable_rs, stable_rs]

        engine = TDengineEngine(instance=self.instance)
        rs = engine.get_all_tables("db1")
        self.assertEqual(
            rs.rows,
            [
                "\u666e\u901a\u8868",
                "n1",
                "n2",
                "\u8d85\u7ea7\u8868",
                "s1",
                "s2",
            ],
        )

    @patch.object(TDengineEngine, "query")
    def test_get_all_columns_by_tb(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("c1", "INT"), ("c2", "BINARY")])
        engine = TDengineEngine(instance=self.instance)
        rs = engine.get_all_columns_by_tb("db1", "tb1")
        mock_query.assert_called_once()
        self.assertEqual(rs.rows, ["c1", "c2"])

    @patch.object(TDengineEngine, "query")
    def test_get_table_type_stable(self, mock_query):
        mock_query.side_effect = [ResultSet(rows=[("st1",)]), ResultSet(rows=[])]
        engine = TDengineEngine(instance=self.instance)
        self.assertEqual(engine.get_table_type("db1", "st1"), "stable")

    @patch.object(TDengineEngine, "query")
    def test_get_table_type_table(self, mock_query):
        mock_query.side_effect = [ResultSet(rows=[]), ResultSet(rows=[("tb1",)])]
        engine = TDengineEngine(instance=self.instance)
        self.assertEqual(engine.get_table_type("db1", "tb1"), "table")

    @patch.object(TDengineEngine, "query")
    def test_get_table_type_none(self, mock_query):
        mock_query.side_effect = [ResultSet(rows=[]), ResultSet(rows=[])]
        engine = TDengineEngine(instance=self.instance)
        self.assertIsNone(engine.get_table_type("db1", "missing"))

    @patch.object(TDengineEngine, "get_table_type", return_value="table")
    @patch.object(TDengineEngine, "query")
    def test_describe_table_format(self, mock_query, _table_type):
        mock_query.return_value = ResultSet(
            rows=[
                (
                    "tb1",
                    "CREATE TABLE `tb1` (`ts` TIMESTAMP, `v` INT) TAGS (`site` NCHAR(16))",
                )
            ]
        )
        engine = TDengineEngine(instance=self.instance)
        rs = engine.describe_table("db1", "tb1")

        self.assertEqual(rs.rows[0][0], "tb1")
        self.assertIn("CREATE TABLE `tb1` (\n    `ts` TIMESTAMP", rs.rows[0][1])
        self.assertIn("\n)\nTAGS (\n    `site` NCHAR(16)", rs.rows[0][1])

    @patch.object(TDengineEngine, "query")
    def test_query_check_valid_select(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("plan",)])
        engine = TDengineEngine(instance=self.instance)
        ret = engine.query_check(db_name="db1", sql="select id from tb1")
        self.assertFalse(ret["bad_query"])
        self.assertEqual(ret["filtered_sql"], "select id from tb1")

    def test_query_check_not_supported_type(self):
        engine = TDengineEngine(instance=self.instance)
        ret = engine.query_check(db_name="db1", sql="update tb1 set v=1")
        self.assertTrue(ret["bad_query"])

    @patch.object(TDengineEngine, "query")
    def test_query_check_has_star(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("plan",)])
        engine = TDengineEngine(instance=self.instance)
        ret = engine.query_check(db_name="db1", sql="select * from tb1")
        self.assertTrue(ret["has_star"])

    @patch.object(TDengineEngine, "query")
    def test_query_check_explain_error(self, mock_query):
        rs = ResultSet()
        rs.error = "syntax error"
        mock_query.return_value = rs

        engine = TDengineEngine(instance=self.instance)
        ret = engine.query_check(db_name="db1", sql="select id from tb1")
        self.assertTrue(ret["bad_query"])
        self.assertEqual(ret["msg"], "syntax error")

    def test_filter_sql_select_no_limit(self):
        engine = TDengineEngine(instance=self.instance)
        sql = engine.filter_sql(sql="select id from tb1", limit_num=100)
        self.assertEqual(sql, "select id from tb1 limit 100;")

    def test_filter_sql_with_limit_n(self):
        engine = TDengineEngine(instance=self.instance)
        sql = engine.filter_sql(sql="select id from tb1 limit 200", limit_num=100)
        self.assertEqual(sql, "select id from tb1 limit 100;")

    def test_filter_sql_with_limit_offset(self):
        engine = TDengineEngine(instance=self.instance)
        sql = engine.filter_sql(
            sql="select id from tb1 limit 200 offset 10", limit_num=100
        )
        self.assertEqual(sql, "select id from tb1 limit 100 offset 10;")

    def test_filter_sql_with_offset_comma_limit(self):
        engine = TDengineEngine(instance=self.instance)
        sql = engine.filter_sql(sql="select id from tb1 limit 10,200", limit_num=100)
        self.assertEqual(sql, "select id from tb1 limit 10,100;")

    def test_filter_sql_not_select(self):
        engine = TDengineEngine(instance=self.instance)
        sql = engine.filter_sql(sql="show databases", limit_num=100)
        self.assertEqual(sql, "show databases;")

    def test_get_kill_command(self):
        engine = TDengineEngine(instance=self.instance)
        sql = engine.get_kill_command(["a1:b2", "c3:d4"])
        self.assertEqual(sql, "kill query 'a1:b2';kill query 'c3:d4';")

    def test_get_kill_command_invalid(self):
        engine = TDengineEngine(instance=self.instance)
        self.assertIsNone(engine.get_kill_command(["invalid-id"]))

    @patch.object(TDengineEngine, "execute")
    def test_kill_query_invalid_ids(self, mock_execute):
        engine = TDengineEngine(instance=self.instance)
        rs = engine.kill_query(["invalid-id"])
        self.assertIsInstance(rs, ResultSet)
        mock_execute.assert_not_called()

    @patch.object(TDengineEngine, "execute")
    @patch.object(TDengineEngine, "processlist")
    def test_kill_query_valid_ids(self, mock_processlist, mock_execute):
        mock_processlist.return_value = ResultSet(rows=[("a1:b2",), ("x9:y8",)])
        mock_execute.return_value = ResultSet(full_sql="killed")

        engine = TDengineEngine(instance=self.instance)
        engine.kill_query(["a1:b2", "not:found"])
        mock_execute.assert_called_once_with(sql="kill query 'a1:b2';")

    @patch("sql.engines.tdengine.taosws.connect")
    def test_execute_success_multi_statement(self, mock_connect):
        cursor = Mock()
        cursor.execute.side_effect = [1, 2]
        mock_connect.return_value.cursor.return_value = cursor

        engine = TDengineEngine(instance=self.instance)
        rs = engine.execute(
            db_name="db1",
            sql="insert into t values(1);insert into t values(2);",
        )
        self.assertIsInstance(rs, ResultSet)
        self.assertIsNone(rs.error)
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertEqual(rs.affected_rows, 3)
        cursor.close.assert_called_once()

    @patch("sql.engines.tdengine.taosws.connect")
    def test_execute_error(self, mock_connect):
        cursor = Mock()
        cursor.execute.side_effect = Exception("execute failed")
        mock_connect.return_value.cursor.return_value = cursor

        engine = TDengineEngine(instance=self.instance)
        rs = engine.execute(sql="bad sql")
        self.assertIn("execute failed", rs.error)

    @patch.object(TDengineEngine, "query")
    def test_obj_check_database_exists(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("metrics",)])

        engine = TDengineEngine(instance=self.instance)
        with patch.object(engine, "escape_string", side_effect=lambda x: x):
            ret = engine.obj_check(obj_name="`metrics`", obj_type="database")

        self.assertEqual(ret, {"exists": True, "type": "database"})
        mock_query.assert_called_once()
        self.assertIn("name = 'metrics'", mock_query.call_args.kwargs["sql"])

    @patch.object(TDengineEngine, "query")
    def test_obj_check_table_with_qualified_name_prefers_stable(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("meters",)])

        engine = TDengineEngine(instance=self.instance)
        with patch.object(engine, "escape_string", side_effect=lambda x: x):
            ret = engine.obj_check(
                db_name="fallback_db",
                obj_name="`metrics`.`meters`",
                obj_type="table",
            )

        self.assertEqual(ret, {"exists": True, "type": "stable"})
        mock_query.assert_called_once()
        self.assertEqual(mock_query.call_args.kwargs["db_name"], "metrics")
        self.assertIn("stable_name = 'meters'", mock_query.call_args.kwargs["sql"])

    @patch.object(TDengineEngine, "query")
    def test_obj_check_table_detects_child_table(self, mock_query):
        mock_query.side_effect = [
            ResultSet(rows=[]),
            ResultSet(rows=[("d1001",)]),
            ResultSet(rows=[]),
        ]

        engine = TDengineEngine(instance=self.instance)
        with patch.object(engine, "escape_string", side_effect=lambda x: x):
            ret = engine.obj_check(
                db_name="metrics", obj_name="d1001", obj_type="table"
            )

        self.assertEqual(ret, {"exists": True, "type": "ctable"})
        self.assertEqual(mock_query.call_count, 3)

    @patch.object(TDengineEngine, "query")
    def test_obj_check_returns_false_for_unsupported_type_empty_name_or_db(
        self, mock_query
    ):
        engine = TDengineEngine(instance=self.instance)

        self.assertEqual(
            engine.obj_check(obj_name="meters", obj_type="view"),
            {"exists": False, "type": None},
        )
        self.assertEqual(
            engine.obj_check(db_name="metrics", obj_name="", obj_type="table"),
            {"exists": False, "type": None},
        )
        self.assertEqual(
            engine.obj_check(db_name="", obj_name="meters", obj_type="table"),
            {"exists": False, "type": None},
        )
        mock_query.assert_not_called()

    @patch.object(TDengineEngine, "query")
    def test_obj_check_table_detects_normal_table(self, mock_query):
        mock_query.side_effect = [
            ResultSet(rows=[]),
            ResultSet(rows=[]),
            ResultSet(rows=[("readings",)]),
        ]

        engine = TDengineEngine(instance=self.instance)
        with patch.object(engine, "escape_string", side_effect=lambda x: x):
            ret = engine.obj_check(
                db_name="metrics", obj_name="readings", obj_type="table"
            )

        self.assertEqual(ret, {"exists": True, "type": "table"})
        self.assertEqual(mock_query.call_count, 3)

    def test_execute_check_rejects_query_sql(self):
        engine = TDengineEngine(instance=self.instance)
        engine.config = Mock()
        engine.config.get.return_value = ""

        ret = engine.execute_check(db_name="metrics", sql="select * from meters;")

        self.assertEqual(ret.error_count, 1)
        self.assertEqual(ret.rows[0].errlevel, 2)
        self.assertEqual(
            ret.rows[0].stagestatus, "\u9a73\u56de\u4e0d\u652f\u6301\u8bed\u53e5"
        )

    @patch.object(TDengineEngine, "obj_check")
    def test_execute_check_create_database_rejects_existing_db(self, mock_obj_check):
        mock_obj_check.return_value = {"exists": True, "type": "database"}
        engine = TDengineEngine(instance=self.instance)
        engine.config = Mock()
        engine.config.get.return_value = ""

        ret = engine.execute_check(
            sql="create database metrics precision 'ms' keep 365;"
        )

        self.assertEqual(ret.error_count, 1)
        self.assertEqual(ret.rows[0].stagestatus, "\u5bf9\u8c61\u5df2\u5b58\u5728")
        self.assertEqual(
            ret.rows[0].errormessage,
            "\u6570\u636e\u5e93 metrics \u5df2\u5b58\u5728\uff0c\u4e0d\u5141\u8bb8\u91cd\u590d\u521b\u5efa\uff01",
        )
        mock_obj_check.assert_called_once_with(obj_name="metrics", obj_type="database")

    @patch.object(TDengineEngine, "obj_check")
    def test_execute_check_accepts_create_database_without_options(
        self, mock_obj_check
    ):
        mock_obj_check.return_value = {"exists": False, "type": None}
        engine = TDengineEngine(instance=self.instance)
        engine.config = Mock()
        engine.config.get.return_value = ""

        ret = engine.execute_check(sql="create database metrics;")

        self.assertEqual(ret.error_count, 0)
        self.assertEqual(ret.rows[0].errlevel, 0)
        self.assertEqual(ret.rows[0].stagestatus, "Audit completed")

    @patch.object(TDengineEngine, "obj_check")
    def test_execute_check_rejects_create_database_invalid_option(self, mock_obj_check):
        mock_obj_check.return_value = {"exists": False, "type": None}
        engine = TDengineEngine(instance=self.instance)
        engine.config = Mock()
        engine.config.get.return_value = ""

        ret = engine.execute_check(sql="create database metrics unknown_option 1;")

        self.assertEqual(ret.error_count, 1)
        self.assertEqual(ret.rows[0].errlevel, 2)
        self.assertEqual(
            ret.rows[0].errormessage,
            "CREATE DATABASE \u8bed\u6cd5\u4e0d\u6b63\u786e\uff01",
        )

    @patch.object(TDengineEngine, "obj_check")
    def test_execute_check_accepts_create_stable_table_and_subtable(
        self, mock_obj_check
    ):
        mock_obj_check.side_effect = [
            {"exists": False, "type": None},
            {"exists": False, "type": None},
            {"exists": True, "type": "stable"},
            {"exists": False, "type": None},
        ]
        engine = TDengineEngine(instance=self.instance)
        engine.config = Mock()
        engine.config.get.return_value = ""

        ret = engine.execute_check(
            db_name="metrics",
            sql="""
                create stable meters (ts timestamp, v int) tags (location binary(20)) comment 'meter' keep 365;
                create table d1001 using meters tags ('beijing');
                create table readings (ts timestamp, v int) ttl 30;
            """,
        )

        self.assertEqual(ret.error_count, 0)
        self.assertEqual([row.errlevel for row in ret.rows], [0, 0, 0])
        self.assertEqual(ret.syntax_type, 1)

    @patch.object(TDengineEngine, "obj_check")
    def test_execute_check_rejects_subtable_using_non_stable(self, mock_obj_check):
        def check_obj(db_name=None, obj_name=None, obj_type="table"):
            if obj_name == "d1001":
                return {"exists": False, "type": None}
            return {"exists": True, "type": "table"}

        mock_obj_check.side_effect = check_obj
        engine = TDengineEngine(instance=self.instance)
        engine.config = Mock()
        engine.config.get.return_value = ""

        ret = engine.execute_check(
            db_name="metrics",
            sql="create table d1001 using readings tags ('beijing');",
        )

        self.assertEqual(ret.error_count, 1)
        self.assertEqual(
            ret.rows[0].errormessage,
            "USING \u5bf9\u8c61 readings \u4e0d\u662f\u8d85\u7ea7\u8868\uff01",
        )

    @patch.object(TDengineEngine, "obj_check")
    def test_execute_check_rejects_existing_or_invalid_create_stable(
        self, mock_obj_check
    ):
        mock_obj_check.side_effect = [
            {"exists": True, "type": "stable"},
            {"exists": False, "type": None},
        ]
        engine = TDengineEngine(instance=self.instance)
        engine.config = Mock()
        engine.config.get.return_value = ""

        ret = engine.execute_check(
            db_name="metrics",
            sql="""
                create stable meters (ts timestamp, v int) tags (location binary(20));
                create stable bad_stable (ts timestamp, v int) tags (location binary(20)) invalid_option 1;
            """,
        )

        self.assertEqual([row.errlevel for row in ret.rows], [2, 2])
        self.assertEqual(ret.error_count, 2)
        self.assertEqual(
            ret.rows[0].errormessage,
            "\u5bf9\u8c61 meters \u5df2\u5b58\u5728\uff0c\u4e0d\u5141\u8bb8\u91cd\u590d\u521b\u5efa\uff01",
        )
        self.assertEqual(
            ret.rows[1].errormessage,
            "CREATE STABLE \u8bed\u6cd5\u4e0d\u6b63\u786e\uff01",
        )

    @patch.object(TDengineEngine, "obj_check")
    def test_execute_check_rejects_existing_or_missing_using_create_subtable(
        self, mock_obj_check
    ):
        mock_obj_check.side_effect = [
            {"exists": True, "type": "ctable"},
            {"exists": True, "type": "stable"},
            {"exists": False, "type": None},
            {"exists": False, "type": None},
        ]
        engine = TDengineEngine(instance=self.instance)
        engine.config = Mock()
        engine.config.get.return_value = ""

        ret = engine.execute_check(
            db_name="metrics",
            sql="""
                create table d1001 using meters tags ('beijing');
                create table d1002 using missing_stable tags ('shanghai');
            """,
        )

        self.assertEqual([row.errlevel for row in ret.rows], [2, 2])
        self.assertEqual(ret.error_count, 2)
        self.assertEqual(
            ret.rows[0].errormessage,
            "\u5bf9\u8c61 d1001 \u5df2\u5b58\u5728\uff0c\u4e0d\u5141\u8bb8\u91cd\u590d\u521b\u5efa\uff01",
        )
        self.assertEqual(
            ret.rows[1].errormessage,
            "\u8d85\u7ea7\u8868 missing_stable \u4e0d\u5b58\u5728\uff01",
        )

    @patch.object(TDengineEngine, "obj_check")
    def test_execute_check_validates_alter_by_object_type(self, mock_obj_check):
        def check_obj(db_name=None, obj_name=None, obj_type="table"):
            return {
                "meters": {"exists": True, "type": "stable"},
                "readings": {"exists": True, "type": "table"},
                "d1001": {"exists": True, "type": "ctable"},
            }.get(obj_name, {"exists": False, "type": None})

        mock_obj_check.side_effect = check_obj
        engine = TDengineEngine(instance=self.instance)
        engine.config = Mock()
        engine.config.get.return_value = ""

        ret = engine.execute_check(
            db_name="metrics",
            sql="""
                alter stable meters add tag location binary(20);
                alter table readings add column v2 int;
                alter table d1001 set tag location='shanghai';
                alter table meters add column invalid int;
            """,
        )

        self.assertEqual([row.errlevel for row in ret.rows], [0, 0, 0, 2])
        self.assertEqual(ret.error_count, 1)
        self.assertEqual(
            ret.rows[3].errormessage,
            "\u8d85\u7ea7\u8868\u4ec5\u652f\u6301 ALTER STABLE \u8bed\u6cd5\uff01",
        )

    @patch.object(TDengineEngine, "obj_check")
    def test_execute_check_validates_insert_delete_and_drop(self, mock_obj_check):
        def check_obj(db_name=None, obj_name=None, obj_type="table"):
            if obj_type == "database":
                return {"exists": True, "type": "database"}
            return {
                "meters": {"exists": True, "type": "stable"},
                "readings": {"exists": True, "type": "table"},
                "d1001": {"exists": True, "type": "ctable"},
                "missing": {"exists": False, "type": None},
            }.get(obj_name, {"exists": False, "type": None})

        mock_obj_check.side_effect = check_obj
        engine = TDengineEngine(instance=self.instance)
        engine.config = Mock()
        engine.config.get.return_value = ""

        ret = engine.execute_check(
            db_name="metrics",
            sql="""
                insert into readings values(now, 1);
                insert into d1002 using meters tags ('new') values(now, 1);
                delete from d1001 where ts < now - 1d;
                drop table readings, if exists missing;
                drop stable meters;
                drop table meters;
            """,
        )

        self.assertEqual([row.errlevel for row in ret.rows], [0, 0, 0, 0, 0, 2])
        self.assertEqual(ret.error_count, 1)
        self.assertEqual(
            ret.rows[5].errormessage,
            "\u5bf9\u8c61 meters \u4e3a\u8d85\u7ea7\u8868\uff0c\u8bf7\u4f7f\u7528 DROP STABLE\uff01",
        )

    @patch.object(TDengineEngine, "obj_check")
    def test_execute_check_validates_insert_subquery_and_block_errors(
        self, mock_obj_check
    ):
        def check_obj(db_name=None, obj_name=None, obj_type="table"):
            return {
                "missing_stable": {"exists": False, "type": None},
                "readings": {"exists": True, "type": "table"},
                "d1002": {"exists": False, "type": None},
                "d1003": {"exists": False, "type": None},
                "meters": {"exists": True, "type": "stable"},
                "missing_table": {"exists": False, "type": None},
            }.get(obj_name, {"exists": False, "type": None})

        mock_obj_check.side_effect = check_obj
        engine = TDengineEngine(instance=self.instance)
        engine.config = Mock()
        engine.config.get.return_value = ""

        ret = engine.execute_check(
            db_name="metrics",
            sql="""
                insert into missing_stable (tbname, ts, v) select tbname, ts, v from source;
                insert into readings (tbname, ts, v) select tbname, ts, v from source;
                insert into d1002 using missing_stable tags ('new') values(now, 1);
                insert into d1003 using readings tags ('new') values(now, 1);
                insert into meters using meters tags ('new') values(now, 1);
                insert into missing_table values(now, 1);
                insert into;
            """,
        )

        self.assertEqual([row.errlevel for row in ret.rows], [2, 2, 2, 2, 2, 2, 2])
        self.assertEqual(ret.error_count, 7)
        self.assertEqual(
            ret.rows[0].errormessage,
            "\u8d85\u7ea7\u8868 missing_stable \u4e0d\u5b58\u5728\uff01",
        )
        self.assertEqual(
            ret.rows[1].errormessage,
            "readings \u4e0d\u662f\u8d85\u7ea7\u8868\uff0c\u4e0d\u80fd\u4f7f\u7528 tbname \u5b50\u67e5\u8be2\u8bed\u6cd5\uff01",
        )
        self.assertEqual(
            ret.rows[2].errormessage,
            "\u8d85\u7ea7\u8868 missing_stable \u4e0d\u5b58\u5728\uff01",
        )
        self.assertEqual(
            ret.rows[3].errormessage,
            "USING \u5bf9\u8c61 readings \u4e0d\u662f\u8d85\u7ea7\u8868\uff01",
        )
        self.assertEqual(
            ret.rows[4].errormessage,
            "meters \u4e3a\u8d85\u7ea7\u8868\uff0c\u4e0d\u80fd\u4f7f\u7528 USING \u8bed\u6cd5\u5199\u5165\uff01",
        )
        self.assertEqual(
            ret.rows[5].errormessage,
            "\u8868 missing_table \u4e0d\u5b58\u5728\uff01",
        )
        self.assertEqual(
            ret.rows[6].errormessage, "INSERT\u8bed\u6cd5\u4e0d\u6b63\u786e\uff01"
        )

    @patch.object(TDengineEngine, "obj_check")
    def test_execute_check_rejects_drop_database_missing_without_if_exists(
        self, mock_obj_check
    ):
        mock_obj_check.return_value = {"exists": False, "type": None}
        engine = TDengineEngine(instance=self.instance)
        engine.config = Mock()
        engine.config.get.return_value = ""

        ret = engine.execute_check(db_name="metrics", sql="drop database missing_db;")

        self.assertEqual(ret.error_count, 1)
        self.assertEqual(ret.rows[0].errlevel, 2)
        self.assertEqual(
            ret.rows[0].errormessage,
            "\u6570\u636e\u5e93 missing_db \u4e0d\u5b58\u5728\uff01",
        )

    @patch.object(TDengineEngine, "obj_check")
    def test_execute_check_critical_regex_rejects_matching_sql(self, mock_obj_check):
        mock_obj_check.return_value = {"exists": True, "type": "table"}
        engine = TDengineEngine(instance=self.instance)
        engine.config = Mock()
        engine.config.get.return_value = r"^drop\s+database"

        ret = engine.execute_check(db_name="metrics", sql="drop database metrics;")

        self.assertEqual(ret.error_count, 1)
        self.assertEqual(ret.rows[0].stagestatus, "\u9a73\u56de\u9ad8\u5371SQL")
        mock_obj_check.assert_not_called()

    @patch.object(TDengineEngine, "execute")
    def test_execute_workflow_stops_after_failed_statement(self, mock_execute):
        ok = ResultSet(affected_rows=2)
        failed = ResultSet(affected_rows=0)
        failed.error = "execute failed"
        mock_execute.side_effect = [ok, failed]
        workflow = SimpleNamespace(
            db_name="metrics",
            sqlworkflowcontent=SimpleNamespace(sql_content="""
                    insert into readings values(now, 1);
                    insert into missing values(now, 1);
                    insert into readings values(now, 2);
                """),
        )
        engine = TDengineEngine(instance=self.instance)

        ret = engine.execute_workflow(workflow)

        self.assertEqual(mock_execute.call_count, 2)
        self.assertEqual(ret.error, "execute failed")
        self.assertEqual(
            [row.stagestatus for row in ret.rows],
            ["Execute Successfully", "Execute Failed", "Audit completed"],
        )
        self.assertEqual(ret.rows[0].affected_rows, 2)
        self.assertEqual(
            ret.rows[2].errormessage,
            "\u524d\u5e8f\u8bed\u53e5\u5931\u8d25, \u672a\u6267\u884c",
        )

    def test_close(self):
        engine = TDengineEngine(instance=self.instance)
        conn = Mock()
        engine.conn = conn
        engine.close()
        conn.close.assert_called_once()
        self.assertIsNone(engine.conn)
