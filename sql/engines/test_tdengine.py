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
        mock_connect.return_value.cursor.return_value = cursor

        engine = TDengineEngine(instance=self.instance)
        rs = engine.execute(
            db_name="db1",
            sql="insert into t values(1);insert into t values(2);",
        )
        self.assertIsInstance(rs, ResultSet)
        self.assertIsNone(rs.error)
        self.assertEqual(cursor.execute.call_count, 2)
        cursor.close.assert_called_once()

    @patch("sql.engines.tdengine.taosws.connect")
    def test_execute_error(self, mock_connect):
        cursor = Mock()
        cursor.execute.side_effect = Exception("execute failed")
        mock_connect.return_value.cursor.return_value = cursor

        engine = TDengineEngine(instance=self.instance)
        rs = engine.execute(sql="bad sql")
        self.assertIn("execute failed", rs.error)

    def test_close(self):
        engine = TDengineEngine(instance=self.instance)
        conn = Mock()
        engine.conn = conn
        engine.close()
        conn.close.assert_called_once()
        self.assertIsNone(engine.conn)
