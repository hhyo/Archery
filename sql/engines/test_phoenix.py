# -*- coding: UTF-8 -*-
from unittest.mock import patch, MagicMock

from django.test import TestCase

from sql.engines.phoenix import PhoenixEngine
from sql.engines.models import ResultSet
from sql.models import Instance


class TestPhoenixEngine(TestCase):
    """测试Phoenix引擎"""

    def setUp(self):
        """初始化测试环境"""
        self.instance = Instance.objects.create(
            instance_name="test_phoenix",
            type="master",
            db_type="phoenix",
            host="127.0.0.1",
            port=8765,
            user="",
            password="",
        )
        self.engine = PhoenixEngine(instance=self.instance)

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
        self.assertEqual(self.engine.port, 8765)

    @patch("sql.engines.phoenix.phoenixdb.connect")
    def test_get_connection_success(self, mock_connect):
        """测试成功获取数据库连接"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        conn = self.engine.get_connection()
        self.assertIsNotNone(conn)

    @patch("sql.engines.phoenix.phoenixdb.connect")
    def test_get_connection_failure(self, mock_connect):
        """测试连接失败"""
        mock_connect.side_effect = Exception("Connection failed")

        with self.assertRaises(Exception):
            self.engine.get_connection()

    @patch.object(PhoenixEngine, "get_connection")
    def test_query_success(self, mock_get_connection):
        """测试成功执行查询"""
        # Mock connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.description = [("ID",), ("NAME",)]
        mock_cursor.fetchall.return_value = [(1, "test"), (2, "demo")]
        mock_cursor.rowcount = 2
        
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn

        result = self.engine.query(sql="SELECT * FROM TEST_TABLE")

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)
        self.assertEqual(len(result.rows), 2)

    @patch.object(PhoenixEngine, "get_connection")
    def test_query_error(self, mock_get_connection):
        """测试查询失败"""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Query error")
        
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn

        result = self.engine.query(sql="INVALID SQL")

        self.assertIsInstance(result, ResultSet)
        self.assertIsNotNone(result.error)

    @patch.object(PhoenixEngine, "query")
    def test_get_all_tables(self, mock_query):
        """测试获取所有表列表"""
        mock_result = ResultSet()
        mock_result.rows = [("USERS",), ("ORDERS",), ("PRODUCTS",)]
        mock_result.error = None
        mock_query.return_value = mock_result

        result = self.engine.get_all_tables(db_name="")

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)
        self.assertEqual(len(result.rows), 3)

    @patch.object(PhoenixEngine, "query")
    def test_get_all_columns_by_tb(self, mock_query):
        """测试获取表的所有列"""
        mock_result = ResultSet()
        mock_result.rows = [
            ("ID", "INTEGER"),
            ("NAME", "VARCHAR"),
            ("CREATED_AT", "TIMESTAMP"),
        ]
        mock_result.error = None
        mock_query.return_value = mock_result

        result = self.engine.get_all_columns_by_tb(db_name="", tb_name="USERS")

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)
        self.assertEqual(len(result.rows), 3)

    @patch.object(PhoenixEngine, "query")
    def test_describe_table(self, mock_query):
        """测试描述表结构"""
        mock_result = ResultSet()
        mock_result.rows = [
            ("ID", "INTEGER", "NO"),
            ("NAME", "VARCHAR", "YES"),
        ]
        mock_result.error = None
        mock_query.return_value = mock_result

        result = self.engine.describe_table(db_name="", tb_name="USERS")

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)

    def test_query_check_select(self):
        """测试查询语句检查 - SELECT"""
        sql = "SELECT * FROM USERS WHERE ID = 1"
        result = self.engine.query_check(db_name="", sql=sql)

        self.assertIsInstance(result, dict)
        self.assertIn("filtered_sql", result)
        self.assertIn("bad_query", result)
        self.assertFalse(result["bad_query"])

    def test_query_check_ddl_statement(self):
        """测试查询语句检查 - DDL语句"""
        sql = "DROP TABLE USERS"
        result = self.engine.query_check(db_name="", sql=sql)

        self.assertIsInstance(result, dict)
        # Phoenix通常不允许DDL操作在查询中
        # 应该标记为bad_query
        self.assertTrue(result.get("bad_query", False))

    def test_filter_sql_with_limit(self):
        """测试SQL过滤 - 添加LIMIT"""
        sql = "SELECT * FROM USERS"
        filtered_sql = self.engine.filter_sql(sql=sql, limit_num=100)

        self.assertIn("LIMIT", filtered_sql.upper())

    @patch.object(PhoenixEngine, "get_connection")
    def test_close_connection(self, mock_get_connection):
        """测试关闭连接"""
        mock_conn = MagicMock()
        mock_get_connection.return_value = mock_conn

        # 先建立连接
        self.engine.get_connection()
        
        # 关闭连接
        self.engine.close()

    @patch.object(PhoenixEngine, "get_connection")
    def test_execute_workflow(self, mock_get_connection):
        """测试执行工作流"""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn

        workflow = MagicMock()
        workflow.sqlworkflowcontent.sql_content = "UPSERT INTO USERS VALUES (1, 'test')"

        # Phoenix execute_workflow implementation varies
        # This is a basic test structure


class TestPhoenixEngineEdgeCases(TestCase):
    """测试Phoenix引擎边界情况"""

    def setUp(self):
        """初始化测试环境"""
        self.instance = Instance.objects.create(
            instance_name="test_phoenix",
            type="master",
            db_type="phoenix",
            host="127.0.0.1",
            port=8765,
            user="",
            password="",
        )
        self.engine = PhoenixEngine(instance=self.instance)

    def tearDown(self):
        """清理测试数据"""
        Instance.objects.all().delete()

    def test_filter_sql_empty(self):
        """测试过滤空SQL"""
        sql = ""
        filtered_sql = self.engine.filter_sql(sql=sql, limit_num=100)

        self.assertEqual(filtered_sql, sql)

    def test_filter_sql_whitespace_only(self):
        """测试过滤仅包含空白的SQL"""
        sql = "   \n  \t  "
        filtered_sql = self.engine.filter_sql(sql=sql, limit_num=100)

        # Should handle gracefully, likely returning original or stripped string
        self.assertIsInstance(filtered_sql, str)

    @patch.object(PhoenixEngine, "query")
    def test_get_all_columns_empty_table(self, mock_query):
        """测试获取空表的列"""
        mock_result = ResultSet()
        mock_result.rows = []
        mock_result.error = None
        mock_query.return_value = mock_result

        result = self.engine.get_all_columns_by_tb(db_name="", tb_name="EMPTY_TABLE")

        self.assertIsInstance(result, ResultSet)
        self.assertEqual(len(result.rows), 0)
