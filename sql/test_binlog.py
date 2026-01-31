# -*- coding: UTF-8 -*-
import json
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from sql.engines.models import ResultSet
from sql.models import Instance

User = get_user_model()


class TestBinlog(TestCase):
    """测试Binlog功能"""

    def setUp(self):
        """初始化测试环境"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="test_user",
            password="test_password",
            display="测试用户",
            is_active=True,
        )
        self.instance = Instance.objects.create(
            instance_name="test_mysql",
            type="master",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="root",
            password="password",
        )

    def tearDown(self):
        """清理测试数据"""
        User.objects.all().delete()
        Instance.objects.all().delete()

    @patch("sql.binlog.get_engine")
    def test_binlog_list_success(self, mock_get_engine):
        """测试成功获取binlog列表"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="menu_my2sql",
            name="Can view my2sql",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock query engine
        mock_engine = MagicMock()
        mock_result = ResultSet()
        mock_result.rows = [
            ("mysql-bin.000001", 154),
            ("mysql-bin.000002", 256),
        ]
        mock_result.column_list = ["Log_name", "File_size"]
        mock_result.error = None
        mock_engine.query.return_value = mock_result
        mock_get_engine.return_value = mock_engine

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:binlog_list"),
            {
                "instance_name": "test_mysql",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 0)
        self.assertEqual(len(data["data"]), 2)
        self.assertEqual(data["data"][0]["Log_name"], "mysql-bin.000001")

    def test_binlog_list_instance_not_found(self):
        """测试实例不存在时获取binlog列表"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="menu_my2sql",
            name="Can view my2sql",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:binlog_list"),
            {
                "instance_name": "nonexistent_instance",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("不存在", data["msg"])

    @patch("sql.binlog.get_engine")
    def test_binlog_list_query_error(self, mock_get_engine):
        """测试查询binlog失败"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="menu_my2sql",
            name="Can view my2sql",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock query engine with error
        mock_engine = MagicMock()
        mock_result = ResultSet()
        mock_result.error = "Failed to show binary logs"
        mock_engine.query.return_value = mock_result
        mock_get_engine.return_value = mock_engine

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:binlog_list"),
            {
                "instance_name": "test_mysql",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("Failed to show binary logs", data["msg"])

    @patch("sql.binlog.get_engine")
    def test_del_binlog_success(self, mock_get_engine):
        """测试成功删除binlog"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="binlog_del",
            name="Can delete binlog",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock query engine
        mock_engine = MagicMock()
        mock_engine.escape_string.return_value = "mysql-bin.000001"
        mock_result = ResultSet()
        mock_result.error = None
        mock_engine.query.return_value = mock_result
        mock_get_engine.return_value = mock_engine

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:del_binlog"),
            {
                "instance_id": self.instance.id,
                "binlog": "mysql-bin.000001",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 0)
        self.assertIn("成功", data["msg"])

    @patch("sql.binlog.get_engine")
    def test_del_binlog_error(self, mock_get_engine):
        """测试删除binlog失败"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="binlog_del",
            name="Can delete binlog",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock query engine with error
        mock_engine = MagicMock()
        mock_engine.escape_string.return_value = "mysql-bin.000001"
        mock_result = ResultSet()
        mock_result.error = "Permission denied"
        mock_engine.query.return_value = mock_result
        mock_get_engine.return_value = mock_engine

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:del_binlog"),
            {
                "instance_id": self.instance.id,
                "binlog": "mysql-bin.000001",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 2)
        self.assertIn("失败", data["msg"])
        self.assertIn("Permission denied", data["msg"])

    def test_del_binlog_instance_not_found(self):
        """测试实例不存在时删除binlog"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="binlog_del",
            name="Can delete binlog",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:del_binlog"),
            {
                "instance_id": 99999,  # 不存在的实例ID
                "binlog": "mysql-bin.000001",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("不存在", data["msg"])

    @patch("sql.binlog.get_engine")
    def test_del_binlog_empty_binlog(self, mock_get_engine):
        """测试删除空binlog"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="binlog_del",
            name="Can delete binlog",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:del_binlog"),
            {
                "instance_id": self.instance.id,
                "binlog": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        # Should handle empty binlog gracefully
