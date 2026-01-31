# -*- coding: UTF-8 -*-
import json
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from sql.models import Instance

User = get_user_model()


class TestSqlOptimize(TestCase):
    """测试SQL优化功能"""

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

    @patch("sql.sql_optimize.user_instances")
    @patch("sql.sql_optimize.SysConfig")
    @patch("sql.sql_optimize.SQLAdvisor")
    def test_optimize_sqladvisor_success(
        self, mock_sqladvisor, mock_config, mock_user_instances
    ):
        """测试SQLAdvisor优化成功"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="optimize_sqladvisor",
            name="Can optimize with sqladvisor",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock SysConfig
        mock_sys_config = MagicMock()
        mock_sys_config.get.return_value = "/usr/local/bin/sqladvisor"
        mock_config.return_value = mock_sys_config

        # Mock SQLAdvisor
        mock_advisor = MagicMock()
        mock_advisor.check_args.return_value = {"status": 0}
        mock_advisor.generate_args2cmd.return_value = ["sqladvisor", "-h", "..."]
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"Recommended index: ALTER TABLE users ADD INDEX idx_id(id)",
            b"",
        )
        mock_advisor.execute_cmd.return_value = mock_process
        mock_sqladvisor.return_value = mock_advisor

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:optimize_sqladvisor"),
            {
                "sql_content": "SELECT * FROM users WHERE id = 1",
                "instance_name": "test_mysql",
                "db_name": "test_db",
                "verbose": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 0)
        self.assertIn("Recommended index", data["data"])

    def test_optimize_sqladvisor_missing_parameters(self):
        """测试缺少必需参数"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="optimize_sqladvisor",
            name="Can optimize with sqladvisor",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:optimize_sqladvisor"),
            {
                # Missing sql_content and instance_name
                "db_name": "test_db",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("参数可能为空", data["msg"])

    @patch("sql.sql_optimize.user_instances")
    def test_optimize_sqladvisor_instance_not_found(self, mock_user_instances):
        """测试实例不存在"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="optimize_sqladvisor",
            name="Can optimize with sqladvisor",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances to raise exception
        mock_user_instances.return_value.get.side_effect = Instance.DoesNotExist

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:optimize_sqladvisor"),
            {
                "sql_content": "SELECT * FROM users WHERE id = 1",
                "instance_name": "nonexistent",
                "db_name": "test_db",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("未关联该实例", data["msg"])

    @patch("sql.sql_optimize.user_instances")
    @patch("sql.sql_optimize.SysConfig")
    def test_optimize_sqladvisor_path_not_configured(
        self, mock_config, mock_user_instances
    ):
        """测试SQLAdvisor路径未配置"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="optimize_sqladvisor",
            name="Can optimize with sqladvisor",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock SysConfig to return None
        mock_sys_config = MagicMock()
        mock_sys_config.get.return_value = None
        mock_config.return_value = mock_sys_config

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:optimize_sqladvisor"),
            {
                "sql_content": "SELECT * FROM users WHERE id = 1",
                "instance_name": "test_mysql",
                "db_name": "test_db",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("配置SQLAdvisor路径", data["msg"])

    @patch("sql.sql_optimize.user_instances")
    @patch("sql.sql_optimize.SysConfig")
    @patch("sql.sql_optimize.SQLAdvisor")
    def test_optimize_sqladvisor_args_check_failed(
        self, mock_sqladvisor, mock_config, mock_user_instances
    ):
        """测试参数检查失败"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="optimize_sqladvisor",
            name="Can optimize with sqladvisor",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock SysConfig
        mock_sys_config = MagicMock()
        mock_sys_config.get.return_value = "/usr/local/bin/sqladvisor"
        mock_config.return_value = mock_sys_config

        # Mock SQLAdvisor args check to fail
        mock_advisor = MagicMock()
        mock_advisor.check_args.return_value = {
            "status": 1,
            "msg": "Invalid SQL statement",
        }
        mock_sqladvisor.return_value = mock_advisor

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:optimize_sqladvisor"),
            {
                "sql_content": "INVALID SQL",
                "instance_name": "test_mysql",
                "db_name": "test_db",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)

    @patch("sql.sql_optimize.user_instances")
    @patch("sql.sql_optimize.SysConfig")
    @patch("sql.sql_optimize.Soar")
    def test_optimize_soar_success(self, mock_soar, mock_config, mock_user_instances):
        """测试SOAR优化成功"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="optimize_soar",
            name="Can optimize with soar",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock SysConfig
        mock_sys_config = MagicMock()
        mock_sys_config.get.return_value = "user:pass@localhost:3306/test"
        mock_config.return_value = mock_sys_config

        # Mock Soar
        mock_soar_instance = MagicMock()
        mock_soar_instance.generate_args2cmd.return_value = ["soar", "-query", "..."]
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"# Rewrite Suggestions\nRewritten SQL: ...",
            b"",
        )
        mock_soar_instance.execute_cmd.return_value = mock_process
        mock_soar.return_value = mock_soar_instance

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:optimize_soar"),
            {
                "instance_name": "test_mysql",
                "db_name": "test_db",
                "sql": "SELECT * FROM users WHERE id = 1",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 0)

    def test_optimize_soar_missing_parameters(self):
        """测试SOAR缺少必需参数"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="optimize_soar",
            name="Can optimize with soar",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:optimize_soar"),
            {
                # Missing required parameters
                "instance_name": "test_mysql",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("参数可能为空", data["msg"])
