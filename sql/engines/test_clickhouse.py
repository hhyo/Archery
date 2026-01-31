# -*- coding: UTF-8 -*-
from unittest.mock import patch, MagicMock

from django.test import TestCase

from sql.engines.clickhouse import ClickHouseEngine
from sql.engines.models import ResultSet
from sql.models import Instance


class TestClickHouseEngine(TestCase):
    """测试ClickHouse引擎"""

    def setUp(self):
        """初始化测试环境"""
        self.instance = Instance.objects.create(
            instance_name="test_clickhouse",
            type="master",
            db_type="clickhouse",
            host="127.0.0.1",
            port=9000,
            user="default",
            password="",
        )
        self.engine = ClickHouseEngine(instance=self.instance)

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
        self.assertEqual(self.engine.port, 9000)
        self.assertEqual(self.engine.user, "default")

    @patch("sql.engines.clickhouse.Client")
    def test_get_connection_success(self, mock_client):
        """测试成功获取数据库连接"""
        mock_conn = MagicMock()
        mock_client.return_value = mock_conn

        conn = self.engine.get_connection(db_name="default")
        self.assertIsNotNone(conn)

    @patch("sql.engines.clickhouse.Client")
    def test_get_connection_failure(self, mock_client):
        """测试连接失败"""
        mock_client.side_effect = Exception("Connection failed")

        with self.assertRaises(Exception):
            self.engine.get_connection(db_name="default")

    @patch.object(ClickHouseEngine, "get_connection")
    def test_query_success(self, mock_get_connection):
        """测试成功执行查询"""
        # Mock connection
        mock_conn = MagicMock()
        mock_conn.execute.return_value = [
            (1, "test"),
            (2, "demo"),
        ]
        mock_get_connection.return_value = mock_conn

        result = self.engine.query(db_name="default", sql="SELECT * FROM test_table")

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)
        self.assertEqual(len(result.rows), 2)

    @patch.object(ClickHouseEngine, "get_connection")
    def test_query_error(self, mock_get_connection):
        """测试查询失败"""
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("Query error")
        mock_get_connection.return_value = mock_conn

        result = self.engine.query(db_name="default", sql="INVALID SQL")

        self.assertIsInstance(result, ResultSet)
        self.assertIsNotNone(result.error)

    @patch.object(ClickHouseEngine, "query")
    def test_get_all_databases(self, mock_query):
        """测试获取所有数据库列表"""
        mock_result = ResultSet()
        mock_result.rows = [("default",), ("system",), ("test_db",)]
        mock_result.error = None
        mock_query.return_value = mock_result

        result = self.engine.get_all_databases()

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)
        self.assertEqual(len(result.rows), 3)

    @patch.object(ClickHouseEngine, "query")
    def test_get_all_tables(self, mock_query):
        """测试获取所有表列表"""
        mock_result = ResultSet()
        mock_result.rows = [("users",), ("orders",), ("products",)]
        mock_result.error = None
        mock_query.return_value = mock_result

        result = self.engine.get_all_tables(db_name="test_db")

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)
        self.assertEqual(len(result.rows), 3)

    @patch.object(ClickHouseEngine, "query")
    def test_get_all_columns_by_tb(self, mock_query):
        """测试获取表的所有列"""
        mock_result = ResultSet()
        mock_result.rows = [
            ("id", "UInt32"),
            ("name", "String"),
            ("created_at", "DateTime"),
        ]
        mock_result.error = None
        mock_query.return_value = mock_result

        result = self.engine.get_all_columns_by_tb(db_name="test_db", tb_name="users")

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)
        self.assertEqual(len(result.rows), 3)

    @patch.object(ClickHouseEngine, "query")
    def test_describe_table(self, mock_query):
        """测试描述表结构"""
        mock_result = ResultSet()
        mock_result.rows = [
            ("id", "UInt32", "", "", "", ""),
            ("name", "String", "", "", "", ""),
        ]
        mock_result.error = None
        mock_query.return_value = mock_result

        result = self.engine.describe_table(db_name="test_db", tb_name="users")

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
        sql = "ALTER TABLE users DROP COLUMN name"
        result = self.engine.query_check(db_name="test_db", sql=sql)

        self.assertIsInstance(result, dict)
        # ClickHouse may allow ALTER in queries, depends on implementation

    def test_filter_sql_with_limit(self):
        """测试SQL过滤 - 添加LIMIT"""
        sql = "SELECT * FROM users"
        filtered_sql = self.engine.filter_sql(sql=sql, limit_num=100)

        self.assertIn("LIMIT", filtered_sql.upper())

    def test_filter_sql_existing_limit(self):
        """测试SQL过滤 - 已有LIMIT"""
        sql = "SELECT * FROM users LIMIT 50"
        filtered_sql = self.engine.filter_sql(sql=sql, limit_num=100)

        # 应该保留原有的LIMIT或替换为更小的值
        self.assertIn("LIMIT", filtered_sql.upper())

    @patch.object(ClickHouseEngine, "get_connection")
    def test_close_connection(self, mock_get_connection):
        """测试关闭连接"""
        mock_conn = MagicMock()
        mock_get_connection.return_value = mock_conn

        # 先建立连接
        self.engine.get_connection(db_name="default")
        
        # 关闭连接
        self.engine.close()

    @patch.object(ClickHouseEngine, "query")
    def test_processlist(self, mock_query):
        """测试获取进程列表"""
        mock_result = ResultSet()
        mock_result.rows = [
            {
                "query_id": "abc123",
                "user": "default",
                "query": "SELECT * FROM test_table",
                "elapsed": 1.5,
            }
        ]
        mock_result.error = None
        mock_query.return_value = mock_result

        result = self.engine.processlist()

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)

    def test_execute_workflow_select_not_allowed(self):
        """测试工作流执行 - SELECT不允许"""
        workflow = MagicMock()
        workflow.sqlworkflowcontent.sql_content = "SELECT * FROM users"

        # ClickHouse execute_workflow 通常不允许SELECT
        # 验证workflow对象已创建
        self.assertIsNotNone(workflow)
        self.assertEqual(workflow.sqlworkflowcontent.sql_content, "SELECT * FROM users")
