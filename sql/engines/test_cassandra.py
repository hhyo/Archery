import unittest
from unittest.mock import patch, Mock

from django.test import TestCase
from sql.models import Instance
from sql.engines.cassandra import CassandraEngine
from sql.engines.models import ResultSet

# 启用后, 会运行全部测试, 包括一些集成测试
integration_test_enabled = False
integration_test_host = "localhost"


class CassandraEngineTest(TestCase):
    def setUp(self) -> None:
        self.ins = Instance.objects.create(
            instance_name="some_ins",
            type="slave",
            db_type="cassandra",
            host="localhost",
            port=9200,
            user="cassandra",
            password="cassandra",
            db_name="some_db",
        )
        self.engine = CassandraEngine(instance=self.ins)

    def tearDown(self) -> None:
        self.ins.delete()
        if integration_test_enabled:
            self.engine.execute(sql="drop keyspace test;")

    @patch("sql.engines.cassandra.Cluster.connect")
    def test_get_connection(self, mock_connect):
        _ = self.engine.get_connection()
        mock_connect.assert_called_once()

    @patch("sql.engines.cassandra.CassandraEngine.get_connection")
    def test_query(self, mock_get_connection):
        test_sql = """select 123"""
        self.assertIsInstance(self.engine.query("some_db", test_sql), ResultSet)

    def test_query_check(self):
        test_sql = """select 123; -- this is comment
                      select 456;"""

        result_sql = "select 123;"

        check_result = self.engine.query_check(sql=test_sql)

        self.assertIsInstance(check_result, dict)
        self.assertEqual(False, check_result.get("bad_query"))
        self.assertEqual(result_sql, check_result.get("filtered_sql"))

    def test_query_check_error(self):
        test_sql = """drop table table_a"""

        check_result = self.engine.query_check(sql=test_sql)

        self.assertIsInstance(check_result, dict)
        self.assertEqual(True, check_result.get("bad_query"))

    @patch("sql.engines.cassandra.CassandraEngine.query")
    def test_get_all_databases(self, mock_query):
        mock_query.return_value = ResultSet(rows=[("some_db",)])

        result = self.engine.get_all_databases()

        self.assertIsInstance(result, ResultSet)
        self.assertEqual(result.rows, ["some_db"])

    @patch("sql.engines.cassandra.CassandraEngine.query")
    def test_get_all_tables(self, mock_query):
        # 下面是查表示例返回结果
        mock_query.return_value = ResultSet(rows=[("u",), ("v",), ("w",)])

        table_list = self.engine.get_all_tables("some_db")

        self.assertEqual(table_list.rows, ["u", "v", "w"])

    @patch("sql.engines.cassandra.CassandraEngine.query")
    def test_describe_table(self, mock_query):
        mock_query.return_value = ResultSet()
        self.engine.describe_table("some_db", "some_table")
        mock_query.assert_called_once_with(
            db_name="some_db", sql="describe table some_table"
        )

    @patch("sql.engines.cassandra.CassandraEngine.query")
    def test_get_all_columns_by_tb(self, mock_query):
        mock_query.return_value = ResultSet(
            rows=[("name", "text")], column_list=["column_name", "type"]
        )

        result = self.engine.get_all_columns_by_tb("some_db", "some_table")
        self.assertEqual(result.rows, [("name", "text")])
        self.assertEqual(result.column_list, ["column_name", "type"])


@unittest.skipIf(
    not integration_test_enabled, "cassandra integration test is not enabled"
)
class CassandraIntegrationTest(TestCase):
    def setUp(self):
        self.instance = Instance.objects.create(
            instance_name="int_ins",
            type="slave",
            db_type="cassandra",
            host=integration_test_host,
            port=9042,
            user="cassandra",
            password="cassandra",
            db_name="",
        )
        self.engine = CassandraEngine(instance=self.instance)

        self.keyspace = "test"
        self.table = "test_table"
        # 新建 keyspace
        self.engine.execute(
            sql=f"create keyspace {self.keyspace} with replication = "
            "{'class': 'org.apache.cassandra.locator.SimpleStrategy', "
            "'replication_factor': '1'};"
        )
        # 建表
        self.engine.execute(
            db_name=self.keyspace,
            sql=f"""create table if not exists {self.table}( name text primary key );""",
        )

    def tearDown(self):
        self.engine.execute(sql="drop keyspace test;")

    def test_integrate_query(self):
        self.engine.execute(
            db_name=self.keyspace,
            sql=f"insert into {self.table} (name) values ('test')",
        )

        result = self.engine.query(
            db_name=self.keyspace, sql=f"select * from {self.table}"
        )

        self.assertEqual(result.rows[0][0], "test")
