# -*- coding: UTF-8 -*-
import json
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from sql.models import Instance

User = get_user_model()


class TestSqlAnalyze(TestCase):
    """测试SQL分析功能"""

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

    @patch("sql.sql_analyze.generate_sql")
    def test_generate_sql_success(self, mock_generate_sql):
        """测试成功生成SQL列表"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="sql_analyze",
            name="Can analyze sql",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock generate_sql
        mock_generate_sql.return_value = [
            {"sql": "SELECT * FROM users WHERE id = 1"},
            {"sql": "UPDATE users SET name = 'test' WHERE id = 1"},
        ]

        self.client.force_login(self.user)
        response = self.client.post(
            "/sql_analyze/generate/",
            {
                "text": "SELECT * FROM users WHERE id = 1;\nUPDATE users SET name = 'test' WHERE id = 1;",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["rows"]), 2)

    def test_generate_sql_empty_text(self):
        """测试空文本生成SQL"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="sql_analyze",
            name="Can analyze sql",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            "/sql_analyze/generate/",
            {},  # No text parameter
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 0)
        self.assertEqual(len(data["rows"]), 0)

    @patch("sql.sql_analyze.user_instances")
    @patch("sql.sql_analyze.generate_sql")
    @patch("sql.sql_analyze.Soar")
    @patch("sql.sql_analyze.SysConfig")
    def test_analyze_with_instance(
        self, mock_config, mock_soar, mock_generate_sql, mock_user_instances
    ):
        """测试使用实例进行SQL分析"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="sql_analyze",
            name="Can analyze sql",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock SysConfig
        mock_sys_config = MagicMock()
        mock_sys_config.get.return_value = "user:pass@localhost:3306/test"
        mock_config.return_value = mock_sys_config

        # Mock generate_sql
        mock_generate_sql.return_value = [
            {"sql": "SELECT * FROM users WHERE id = 1"},
        ]

        # Mock Soar
        mock_soar_instance = MagicMock()
        mock_soar_instance.generate_args2cmd.return_value = ["soar", "-query", "..."]
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"# SQL Analysis Report\nScore: 100",
            b"",
        )
        mock_soar_instance.execute_cmd.return_value = mock_process
        mock_soar.return_value = mock_soar_instance

        self.client.force_login(self.user)
        response = self.client.post(
            "/sql_analyze/analyze/",
            {
                "text": "SELECT * FROM users WHERE id = 1;",
                "instance_name": "test_mysql",
                "db_name": "test_db",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)
        self.assertIn("report", data["rows"][0])

    @patch("sql.sql_analyze.generate_sql")
    @patch("sql.sql_analyze.Soar")
    def test_analyze_without_instance(self, mock_soar, mock_generate_sql):
        """测试不使用实例进行SQL分析"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="sql_analyze",
            name="Can analyze sql",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock generate_sql
        mock_generate_sql.return_value = [
            {"sql": "SELECT * FROM users WHERE id = 1"},
        ]

        # Mock Soar
        mock_soar_instance = MagicMock()
        mock_soar_instance.generate_args2cmd.return_value = ["soar", "-query", "..."]
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"# SQL Analysis Report\nScore: 90",
            b"",
        )
        mock_soar_instance.execute_cmd.return_value = mock_process
        mock_soar.return_value = mock_soar_instance

        self.client.force_login(self.user)
        response = self.client.post(
            "/sql_analyze/analyze/",
            {
                "text": "SELECT * FROM users WHERE id = 1;",
                "instance_name": "",
                "db_name": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)

    @patch("sql.sql_analyze.user_instances")
    def test_analyze_instance_not_found(self, mock_user_instances):
        """测试实例不存在"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="sql_analyze",
            name="Can analyze sql",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances to raise exception
        mock_user_instances.return_value.get.side_effect = Instance.DoesNotExist

        self.client.force_login(self.user)
        response = self.client.post(
            "/sql_analyze/analyze/",
            {
                "text": "SELECT * FROM users WHERE id = 1;",
                "instance_name": "nonexistent",
                "db_name": "test_db",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("未关联该实例", data["msg"])

    def test_analyze_empty_text(self):
        """测试空文本分析"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="sql_analyze",
            name="Can analyze sql",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            "/sql_analyze/analyze/",
            {
                "text": "",
                "instance_name": "",
                "db_name": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 0)

    @patch("sql.sql_analyze.user_instances")
    @patch("sql.sql_analyze.generate_sql")
    @patch("sql.sql_analyze.Path")
    def test_analyze_file_path_blocked(
        self, mock_path, mock_generate_sql, mock_user_instances
    ):
        """测试阻止文件路径作为SQL"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="sql_analyze",
            name="Can analyze sql",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock generate_sql to return a file path
        mock_generate_sql.return_value = [
            {"sql": "/etc/passwd"},
        ]

        # Mock Path to simulate file exists
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        self.client.force_login(self.user)
        response = self.client.post(
            "/sql_analyze/analyze/",
            {
                "text": "/etc/passwd",
                "instance_name": "test_mysql",
                "db_name": "test_db",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("不合法", data["msg"])
