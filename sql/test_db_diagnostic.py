# -*- coding: UTF-8 -*-
import json
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from sql.engines.models import ResultSet
from sql.models import Instance

User = get_user_model()


class TestDbDiagnostic(TestCase):
    """测试数据库诊断功能"""

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

    @patch("sql.db_diagnostic.user_instances")
    @patch("sql.db_diagnostic.get_engine")
    def test_process_list_success(self, mock_get_engine, mock_user_instances):
        """测试成功获取进程列表"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="process_view",
            name="Can view process",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock query engine
        mock_engine = MagicMock()
        mock_result = ResultSet()
        mock_result.rows = [
            {"Id": 1, "User": "root", "Host": "localhost", "db": "test_db", "Command": "Query", "Time": 10, "State": "executing", "Info": "SELECT * FROM test_table"},
            {"Id": 2, "User": "app", "Host": "192.168.1.1", "db": "app_db", "Command": "Sleep", "Time": 5, "State": "idle", "Info": None},
        ]
        mock_result.error = None
        mock_engine.processlist.return_value = mock_result
        mock_get_engine.return_value = mock_engine

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:process_view"),
            {
                "instance_name": "test_mysql",
                "command_type": "All",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 0)
        self.assertIn("rows", data)

    @patch("sql.db_diagnostic.user_instances")
    def test_process_list_instance_not_found(self, mock_user_instances):
        """测试实例不存在或无权限"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="process_view",
            name="Can view process",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances to raise exception
        mock_user_instances.return_value.get.side_effect = Instance.DoesNotExist

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:process_view"),
            {
                "instance_name": "nonexistent_instance",
                "command_type": "All",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("未关联该实例", data["msg"])

    @patch("sql.db_diagnostic.user_instances")
    @patch("sql.db_diagnostic.get_engine")
    def test_process_list_with_error(self, mock_get_engine, mock_user_instances):
        """测试查询进程列表失败"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="process_view",
            name="Can view process",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock query engine with error
        mock_engine = MagicMock()
        mock_result = ResultSet()
        mock_result.error = "Access denied"
        mock_engine.processlist.return_value = mock_result
        mock_get_engine.return_value = mock_engine

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:process_view"),
            {
                "instance_name": "test_mysql",
                "command_type": "All",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("Access denied", data["msg"])

    @patch("sql.db_diagnostic.user_instances")
    @patch("sql.db_diagnostic.get_engine")
    def test_create_kill_session_success(self, mock_get_engine, mock_user_instances):
        """测试成功创建终止会话请求"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="process_kill",
            name="Can kill process",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock query engine
        mock_engine = MagicMock()
        mock_engine.get_kill_command.return_value = [
            "KILL 123",
            "KILL 456",
        ]
        mock_get_engine.return_value = mock_engine

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:create_kill_session"),
            {
                "instance_name": "test_mysql",
                "ThreadIDs": json.dumps([123, 456]),
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 0)
        self.assertEqual(len(data["data"]), 2)
        self.assertIn("KILL 123", data["data"])

    @patch("sql.db_diagnostic.user_instances")
    def test_create_kill_session_instance_not_found(self, mock_user_instances):
        """测试实例不存在时创建终止会话请求"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="process_kill",
            name="Can kill process",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances to raise exception
        mock_user_instances.return_value.get.side_effect = Instance.DoesNotExist

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:create_kill_session"),
            {
                "instance_name": "nonexistent_instance",
                "ThreadIDs": json.dumps([123]),
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("未关联该实例", data["msg"])

    @patch("sql.db_diagnostic.user_instances")
    @patch("sql.db_diagnostic.get_engine")
    def test_create_kill_session_not_supported(self, mock_get_engine, mock_user_instances):
        """测试不支持的数据库类型"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="process_kill",
            name="Can kill process",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock query engine without get_kill_command method
        mock_engine = MagicMock()
        del mock_engine.get_kill_command  # Remove the method to simulate AttributeError
        mock_get_engine.return_value = mock_engine

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:create_kill_session"),
            {
                "instance_name": "test_mysql",
                "ThreadIDs": json.dumps([123]),
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("不支持", data["msg"])

    @patch("sql.db_diagnostic.user_instances")
    @patch("sql.db_diagnostic.get_engine")
    def test_kill_session_mysql_success(self, mock_get_engine, mock_user_instances):
        """测试成功终止MySQL会话"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="process_kill",
            name="Can kill process",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock query engine
        mock_engine = MagicMock()
        mock_result = ResultSet()
        mock_result.error = None
        mock_engine.kill.return_value = mock_result
        mock_get_engine.return_value = mock_engine

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:kill_session"),
            {
                "instance_name": "test_mysql",
                "ThreadIDs": json.dumps([123, 456]),
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 0)

    @patch("sql.db_diagnostic.user_instances")
    def test_kill_session_instance_not_found(self, mock_user_instances):
        """测试实例不存在时终止会话"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="process_kill",
            name="Can kill process",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances to raise exception
        mock_user_instances.return_value.get.side_effect = Instance.DoesNotExist

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:kill_session"),
            {
                "instance_name": "nonexistent_instance",
                "ThreadIDs": json.dumps([123]),
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("未关联该实例", data["msg"])
