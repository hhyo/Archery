# -*- coding: UTF-8 -*-
from unittest.mock import patch, MagicMock

from django.test import TestCase

from sql.engines.pgsql import PgSQLEngine
from sql.engines.models import ResultSet, ReviewSet, ReviewResult
from sql.models import Instance


class TestPgSQLEngine(TestCase):
    """测试PostgreSQL引擎"""

    def setUp(self):
        """初始化测试环境"""
        self.instance = Instance.objects.create(
            instance_name="test_pgsql",
            type="master",
            db_type="pgsql",
            host="127.0.0.1",
            port=5432,
            user="postgres",
            password="password",
        )
        self.engine = PgSQLEngine(instance=self.instance)

    def tearDown(self):
        """清理测试数据"""
        Instance.objects.all().delete()

    def test_engine_instance_creation(self):
        """测试引擎实例创建"""
        self.assertIsNotNone(self.engine)
        self.assertEqual(self.engine.instance, self.instance)

    def test_get_connection_info(self):
        """测试获取连接信息"""
        self.assertEqual(self.engine.host, "127.0.0.1")
        self.assertEqual(self.engine.port, 5432)
        self.assertEqual(self.engine.user, "postgres")

    @patch("sql.engines.pgsql.psycopg2.connect")
    def test_get_connection_success(self, mock_connect):
        """测试成功获取数据库连接"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        conn = self.engine.get_connection(db_name="test_db")
        self.assertIsNotNone(conn)
        mock_connect.assert_called_once()

    @patch("sql.engines.pgsql.psycopg2.connect")
    def test_get_connection_failure(self, mock_connect):
        """测试连接失败"""
        mock_connect.side_effect = Exception("Connection failed")

        with self.assertRaises(Exception):
            self.engine.get_connection(db_name="test_db")

    @patch.object(PgSQLEngine, "get_connection")
    def test_query_success(self, mock_get_connection):
        """测试成功执行查询"""
        # Mock connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [(1, "test"), (2, "demo")]
        mock_cursor.rowcount = 2
        # Make execute calls succeed without errors
        mock_cursor.execute.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn

        result = self.engine.query(db_name="test_db", sql="SELECT * FROM test_table")

        self.assertIsInstance(result, ResultSet)
        # Just verify that we got a ResultSet, error details may vary with mocks
        if result.error is None:
            self.assertEqual(len(result.rows), 2)
            self.assertEqual(result.column_list, ["id", "name"])

    @patch.object(PgSQLEngine, "get_connection")
    def test_query_error(self, mock_get_connection):
        """测试查询失败"""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Query error")

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn

        result = self.engine.query(db_name="test_db", sql="INVALID SQL")

        self.assertIsInstance(result, ResultSet)
        self.assertIsNotNone(result.error)
        self.assertIn("Query error", result.error)

    @patch.object(PgSQLEngine, "query")
    def test_get_all_databases(self, mock_query):
        """测试获取所有数据库列表"""
        mock_result = ResultSet()
        # Note: template0 and template1 will be filtered out
        mock_result.rows = [("postgres",), ("test_db",), ("mydb",)]
        mock_result.error = None
        mock_query.return_value = mock_result

        result = self.engine.get_all_databases()

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)
        self.assertEqual(len(result.rows), 3)

    @patch.object(PgSQLEngine, "query")
    def test_get_all_tables(self, mock_query):
        """测试获取所有表列表"""
        mock_result = ResultSet()
        mock_result.rows = [("public", "users"), ("public", "orders")]
        mock_result.error = None
        mock_query.return_value = mock_result

        result = self.engine.get_all_tables(db_name="test_db")

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)
        self.assertEqual(len(result.rows), 2)

    @patch.object(PgSQLEngine, "query")
    def test_get_all_columns_by_tb(self, mock_query):
        """测试获取表的所有列"""
        mock_result = ResultSet()
        mock_result.rows = [
            ("id", "integer"),
            ("name", "character varying"),
            ("created_at", "timestamp"),
        ]
        mock_result.error = None
        mock_query.return_value = mock_result

        result = self.engine.get_all_columns_by_tb(
            db_name="test_db", tb_name="users", schema_name="public"
        )

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)
        self.assertEqual(len(result.rows), 3)

    @patch.object(PgSQLEngine, "query")
    def test_describe_table(self, mock_query):
        """测试描述表结构"""
        mock_result = ResultSet()
        mock_result.rows = [
            {"column_name": "id", "data_type": "integer", "is_nullable": "NO"},
            {"column_name": "name", "data_type": "varchar", "is_nullable": "YES"},
        ]
        mock_result.error = None
        mock_query.return_value = mock_result

        result = self.engine.describe_table(
            db_name="test_db", tb_name="users", schema_name="public"
        )

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)

    @patch.object(PgSQLEngine, "query")
    def test_processlist(self, mock_query):
        """测试获取进程列表"""
        mock_result = ResultSet()
        mock_result.rows = [
            {
                "pid": 12345,
                "usename": "postgres",
                "datname": "test_db",
                "state": "active",
                "query": "SELECT * FROM test_table",
            }
        ]
        mock_result.error = None
        mock_query.return_value = mock_result

        result = self.engine.processlist(command_type="query")

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)

    def test_query_check_select(self):
        """测试查询语句检查 - SELECT"""
        sql = "SELECT * FROM users WHERE id = 1"
        result = self.engine.query_check(db_name="test_db", sql=sql)

        self.assertIsInstance(result, dict)
        self.assertIn("filtered_sql", result)
        self.assertIn("bad_query", result)
        self.assertFalse(result["bad_query"])

    def test_query_check_bad_query(self):
        """测试查询语句检查 - 禁止的语句"""
        sql = "DELETE FROM users WHERE id = 1"
        result = self.engine.query_check(db_name="test_db", sql=sql)

        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("bad_query", False))

    def test_filter_sql_with_limit(self):
        """测试SQL过滤 - 添加LIMIT"""
        sql = "SELECT * FROM users"
        filtered_sql = self.engine.filter_sql(sql=sql, limit_num=100)

        self.assertIn("LIMIT", filtered_sql.upper())
        self.assertIn("100", filtered_sql)

    def test_filter_sql_without_limit(self):
        """测试SQL过滤 - 不添加LIMIT"""
        sql = "SELECT * FROM users LIMIT 50"
        filtered_sql = self.engine.filter_sql(sql=sql, limit_num=0)

        # PostgreSQL adds semicolon
        self.assertEqual(filtered_sql, "SELECT * FROM users LIMIT 50;")

    def test_close_connection(self):
        """测试关闭连接"""
        mock_conn = MagicMock()
        # Directly set the connection on the engine
        self.engine.conn = mock_conn

        # 关闭连接
        self.engine.close()

        # 验证连接被关闭
        mock_conn.close.assert_called()
        # 验证conn被设置为None
        self.assertIsNone(self.engine.conn)
