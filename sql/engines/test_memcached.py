# -*- coding: UTF-8 -*-
import unittest
from unittest import mock

from sql.engines.memcached import MemcachedEngine
from sql.engines.models import ResultSet, ReviewResult
from sql.models import Instance


class TestMemcachedEngine(unittest.TestCase):
    def setUp(self):
        # 创建测试实例
        self.instance = Instance(
            instance_name="Memcached",
            type="master",
            db_type="memcached",
            host="127.0.0.1",
            port=11211,
            user="",
            password="",
        )
        self.engine = MemcachedEngine(instance=self.instance)

    @mock.patch("sql.engines.memcached.pymemcache.Client")
    def test_get_connection(self, mock_client):
        """测试获取连接"""
        # 设置mock返回值
        mock_conn = mock.MagicMock()
        mock_client.return_value = mock_conn

        # 测试默认连接
        conn = self.engine.get_connection()
        mock_client.assert_called_once_with(
            server=("127.0.0.1", 11211), connect_timeout=10.0, timeout=10.0
        )

        # 测试指定节点连接
        mock_client.reset_mock()
        self.engine.nodes = {"Node - 1": "192.168.1.1"}
        conn = self.engine.get_connection("Node - 1")
        mock_client.assert_called_once_with(
            server=("192.168.1.1", 11211), connect_timeout=10.0, timeout=10.0
        )

        # 测试节点不存在的情况
        with self.assertRaises(Exception):
            self.engine.get_connection("non_existent_node")

    @mock.patch("sql.engines.memcached.pymemcache.Client")
    def test_test_connection(self, mock_client):
        """测试连接是否正常"""
        # 模拟连接成功
        mock_conn = mock.MagicMock()
        mock_conn.version.return_value = "1.6.9"
        mock_client.return_value = mock_conn

        result = self.engine.test_connection()
        self.assertEqual(result.rows[0][0], "连接成功，版本: 1.6.9")

        # 模拟连接失败
        mock_client.side_effect = Exception("连接失败")
        with self.assertRaises(Exception):
            self.engine.test_connection()

    def test_get_all_databases(self):
        """测试获取所有数据库（节点）"""
        self.engine.nodes = {"Node - 0": "127.0.0.1", "Node - 1": "192.168.1.1"}

        result = self.engine.get_all_databases()
        self.assertEqual(len(result.rows), 2)
        self.assertIn(["Node - 0"], result.rows)
        self.assertIn(["Node - 1"], result.rows)

    @mock.patch("sql.engines.memcached.pymemcache.Client")
    def test_query_get_command(self, mock_client):
        """测试get命令"""
        # 模拟get命令响应
        mock_conn = mock.MagicMock()
        mock_conn.get.return_value = "test_value"
        mock_client.return_value = mock_conn

        result = self.engine.query(sql="get test_key")

        # 验证结果
        mock_conn.get.assert_called_once_with("test_key")
        self.assertEqual(result.rows[0][0], "test_value")

    @mock.patch("sql.engines.memcached.pymemcache.Client")
    def test_execute_set_command(self, mock_client):
        """测试set命令"""
        # 模拟set命令响应
        mock_conn = mock.MagicMock()
        mock_conn.set.return_value = True
        mock_client.return_value = mock_conn

        result = self.engine.execute(sql="set test_key test_value 3600")

        # 验证结果
        mock_conn.set.assert_called_once_with("test_key", "test_value", expire=3600)
        self.assertTrue(
            isinstance(result.rows[0], ReviewResult), "结果不是ReviewResult类型"
        )
        self.assertEqual(result.rows[0].stagestatus, "Success")

    @mock.patch("sql.engines.memcached.pymemcache.Client")
    def test_execute_delete_command(self, mock_client):
        """测试delete命令"""
        # 模拟delete命令响应
        mock_conn = mock.MagicMock()
        mock_conn.delete.return_value = True
        mock_client.return_value = mock_conn

        result = self.engine.execute(sql="delete test_key")

        # 验证结果
        mock_conn.delete.assert_called_once_with("test_key")
        self.assertTrue(
            isinstance(result.rows[0], ReviewResult), "结果不是ReviewResult类型"
        )
        self.assertEqual(result.rows[0].stagestatus, "Success")

    @mock.patch("sql.engines.memcached.pymemcache.Client")
    def test_execute_version_command(self, mock_client):
        """测试version命令"""
        # 模拟version命令响应
        mock_conn = mock.MagicMock()
        mock_conn.version.return_value = "1.6.9"
        mock_client.return_value = mock_conn

        result = self.engine.query(sql="version")

        # 验证结果
        mock_conn.version.assert_called_once()
        self.assertEqual(result.rows[0][0], "1.6.9")

    @mock.patch("sql.engines.memcached.pymemcache.Client")
    def test_query_gets_command(self, mock_client):
        """测试gets命令"""
        # 模拟gets命令响应
        mock_conn = mock.MagicMock()
        mock_conn.gets_many.return_value = {
            "key1": ("value1", 123),
            "key2": ("value2", 456),
        }
        mock_client.return_value = mock_conn

        result = self.engine.query(sql="gets key1 key2")

        # 验证结果
        mock_conn.gets_many.assert_called_once_with(["key1", "key2"])
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.rows[0][0], "key1")
        self.assertEqual(result.rows[0][1], "value1")

    @mock.patch("sql.engines.memcached.pymemcache.Client")
    def test_execute_incr_command(self, mock_client):
        """测试incr命令"""
        # 模拟incr命令响应
        mock_conn = mock.MagicMock()
        mock_conn.incr.return_value = 11
        mock_client.return_value = mock_conn

        result = self.engine.execute(sql="incr counter 1")

        # 验证结果
        mock_conn.incr.assert_called_once_with("counter", 1)
        self.assertTrue(
            isinstance(result.rows[0], ReviewResult), "结果不是ReviewResult类型"
        )
        self.assertEqual(result.rows[0].stagestatus, "Success")

    @mock.patch("sql.engines.memcached.pymemcache.Client")
    def test_execute_decr_command(self, mock_client):
        """测试decr命令"""
        # 模拟decr命令响应
        mock_conn = mock.MagicMock()
        mock_conn.decr.return_value = 9
        mock_client.return_value = mock_conn

        result = self.engine.execute(sql="decr counter 1")

        # 验证结果
        mock_conn.decr.assert_called_once_with("counter", 1)
        self.assertTrue(
            isinstance(result.rows[0], ReviewResult), "结果不是ReviewResult类型"
        )
        self.assertEqual(result.rows[0].stagestatus, "Success")

    @mock.patch("sql.engines.memcached.pymemcache.Client")
    def test_execute_touch_command(self, mock_client):
        """测试touch命令"""
        # 模拟touch命令响应
        mock_conn = mock.MagicMock()
        mock_conn.touch.return_value = True
        mock_client.return_value = mock_conn

        result = self.engine.execute(sql="touch test_key 3600")

        # 验证结果
        mock_conn.touch.assert_called_once_with("test_key", expire=3600)
        self.assertTrue(
            isinstance(result.rows[0], ReviewResult), "结果不是ReviewResult类型"
        )
        self.assertEqual(result.rows[0].stagestatus, "Success")

    def test_query_check(self):
        """测试query_check方法"""
        # 测试支持的命令
        result = self.engine.query_check(sql="get test_key")
        self.assertFalse(result["bad_query"])

        # 测试不支持的命令
        result = self.engine.query_check(sql="unknown_command")
        self.assertTrue(result["bad_query"])

    @mock.patch("sql.engines.memcached.pymemcache.Client")
    def test_server_version(self, mock_client):
        """测试获取服务器版本"""
        # 模拟版本响应
        mock_conn = mock.MagicMock()
        mock_conn.version.return_value = "1.6.9"
        mock_client.return_value = mock_conn

        version = self.engine.server_version
        self.assertEqual((1, 6, 9), version, "版本号解析错误")

        # 模拟获取失败
        mock_conn.version.side_effect = Exception("获取失败")
        version = self.engine.server_version
        self.assertEqual(version, ())

    def test_execute_check(self):
        """测试execute_check方法"""
        # 测试支持的命令
        result = self.engine.execute_check(sql="set test_key 0 3600 test_value")
        self.assertEqual(1, len(result.rows))
        self.assertEqual(result.rows[0].stage, "Check")
        self.assertEqual(result.rows[0].stagestatus, "Success")

        # 测试不支持的命令
        result = self.engine.execute_check(sql="unknown_command")
        self.assertEqual(1, len(result.rows))
        self.assertEqual(result.rows[0].stage, "Check")
        self.assertEqual(result.rows[0].stagestatus, "Fail")


if __name__ == "__main__":
    unittest.main()
