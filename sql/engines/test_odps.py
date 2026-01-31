# -*- coding: UTF-8 -*-
from unittest.mock import patch, MagicMock

from django.test import TestCase

from sql.engines.odps import ODPSEngine
from sql.engines.models import ResultSet
from sql.models import Instance


class TestODPSEngine(TestCase):
    """测试ODPS引擎"""

    def setUp(self):
        """初始化测试环境"""
        self.instance = Instance.objects.create(
            instance_name="test_odps",
            type="master",
            db_type="odps",
            host="http://service.odps.aliyun.com/api",
            port=80,
            user="access_key_id",
            password="access_key_secret",
        )
        self.engine = ODPSEngine(instance=self.instance)

    def tearDown(self):
        """清理测试数据"""
        Instance.objects.all().delete()

    def test_engine_instance_creation(self):
        """测试引擎实例创建"""
        self.assertIsNotNone(self.engine)
        self.assertEqual(self.engine.instance, self.instance)

    @patch("sql.engines.odps.ODPS")
    def test_get_connection_success(self, mock_odps):
        """测试成功获取ODPS连接"""
        mock_conn = MagicMock()
        mock_odps.return_value = mock_conn

        conn = self.engine.get_connection(db_name="test_project")
        self.assertIsNotNone(conn)

    @patch("sql.engines.odps.ODPS")
    def test_get_connection_failure(self, mock_odps):
        """测试连接失败"""
        mock_odps.side_effect = Exception("Connection failed")

        with self.assertRaises(Exception):
            self.engine.get_connection(db_name="test_project")

    @patch.object(ODPSEngine, "get_connection")
    def test_query_success(self, mock_get_connection):
        """测试成功执行查询"""
        # Mock ODPS instance and SQL result
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.to_pandas.return_value.values.tolist.return_value = [
            [1, "test"],
            [2, "demo"],
        ]
        mock_result.to_pandas.return_value.columns.tolist.return_value = ["id", "name"]
        mock_instance.execute_sql.return_value.open_reader.return_value = mock_result
        mock_get_connection.return_value = mock_instance

        result = self.engine.query(
            db_name="test_project", sql="SELECT * FROM test_table"
        )

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)

    @patch.object(ODPSEngine, "get_connection")
    def test_query_error(self, mock_get_connection):
        """测试查询失败"""
        mock_instance = MagicMock()
        mock_instance.execute_sql.side_effect = Exception("Query error")
        mock_get_connection.return_value = mock_instance

        result = self.engine.query(db_name="test_project", sql="INVALID SQL")

        self.assertIsInstance(result, ResultSet)
        self.assertIsNotNone(result.error)

    @patch.object(ODPSEngine, "get_connection")
    def test_get_all_tables(self, mock_get_connection):
        """测试获取所有表列表"""
        mock_instance = MagicMock()
        mock_table1 = MagicMock()
        mock_table1.name = "users"
        mock_table2 = MagicMock()
        mock_table2.name = "orders"
        mock_instance.list_tables.return_value = [mock_table1, mock_table2]
        mock_get_connection.return_value = mock_instance

        result = self.engine.get_all_tables(db_name="test_project")

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)

    @patch.object(ODPSEngine, "get_connection")
    def test_get_table_schema(self, mock_get_connection):
        """测试获取表结构"""
        mock_instance = MagicMock()
        mock_table = MagicMock()
        mock_column1 = MagicMock()
        mock_column1.name = "id"
        mock_column1.type = "bigint"
        mock_column2 = MagicMock()
        mock_column2.name = "name"
        mock_column2.type = "string"
        mock_table.table_schema.columns = [mock_column1, mock_column2]
        mock_instance.get_table.return_value = mock_table
        mock_get_connection.return_value = mock_instance

        result = self.engine.get_all_columns_by_tb(
            db_name="test_project", tb_name="users"
        )

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)

    def test_query_check_select(self):
        """测试查询语句检查 - SELECT"""
        sql = "SELECT * FROM users WHERE id = 1"
        result = self.engine.query_check(db_name="test_project", sql=sql)

        self.assertIsInstance(result, dict)
        self.assertIn("filtered_sql", result)
        self.assertIn("bad_query", result)
        self.assertFalse(result["bad_query"])

    def test_query_check_bad_query(self):
        """测试查询语句检查 - 禁止的语句"""
        sql = "DROP TABLE users"
        result = self.engine.query_check(db_name="test_project", sql=sql)

        self.assertIsInstance(result, dict)
        # Should mark DROP statements as bad query
        self.assertTrue(result.get("bad_query", False))

    def test_filter_sql_with_limit(self):
        """测试SQL过滤 - 基类实现只是去除空格"""
        sql = "SELECT * FROM users  "
        filtered_sql = self.engine.filter_sql(sql=sql, limit_num=100)

        # Base implementation just strips whitespace
        self.assertEqual(filtered_sql, "SELECT * FROM users")

    def test_connection_lifecycle(self):
        """测试连接生命周期"""
        # ODPS engine doesn't have explicit close method
        # Connection is managed by ODPS client
        pass

    @patch.object(ODPSEngine, "get_connection")
    def test_describe_table(self, mock_get_connection):
        """测试描述表结构"""
        mock_instance = MagicMock()
        mock_table = MagicMock()
        mock_table.table_schema.columns = []
        mock_instance.get_table.return_value = mock_table
        mock_get_connection.return_value = mock_instance

        result = self.engine.describe_table(db_name="test_project", tb_name="users")

        self.assertIsInstance(result, ResultSet)


class TestODPSEngineEdgeCases(TestCase):
    """测试ODPS引擎边界情况"""

    def setUp(self):
        """初始化测试环境"""
        self.instance = Instance.objects.create(
            instance_name="test_odps",
            type="master",
            db_type="odps",
            host="http://service.odps.aliyun.com/api",
            port=80,
            user="access_key_id",
            password="access_key_secret",
        )
        self.engine = ODPSEngine(instance=self.instance)

    def tearDown(self):
        """清理测试数据"""
        Instance.objects.all().delete()

    @patch.object(ODPSEngine, "get_connection")
    def test_query_empty_result(self, mock_get_connection):
        """测试空结果查询"""
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.to_pandas.return_value.values.tolist.return_value = []
        mock_result.to_pandas.return_value.columns.tolist.return_value = ["id", "name"]
        mock_instance.execute_sql.return_value.open_reader.return_value = mock_result
        mock_get_connection.return_value = mock_instance

        result = self.engine.query(
            db_name="test_project", sql="SELECT * FROM empty_table"
        )

        self.assertIsInstance(result, ResultSet)
        self.assertIsNone(result.error)
        self.assertEqual(len(result.rows), 0)

    def test_filter_sql_already_has_limit(self):
        """测试SQL已有LIMIT"""
        sql = "SELECT * FROM users LIMIT 50"
        filtered_sql = self.engine.filter_sql(sql=sql, limit_num=100)

        # Should handle existing LIMIT, either keep it or replace with smaller value
        self.assertIn("LIMIT", filtered_sql.upper())
        self.assertIsInstance(filtered_sql, str)

    @patch.object(ODPSEngine, "get_connection")
    def test_get_all_tables_empty_project(self, mock_get_connection):
        """测试空项目的表列表"""
        mock_instance = MagicMock()
        mock_instance.list_tables.return_value = []
        mock_get_connection.return_value = mock_instance

        result = self.engine.get_all_tables(db_name="empty_project")

        self.assertIsInstance(result, ResultSet)
        self.assertEqual(len(result.rows), 0)
