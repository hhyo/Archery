# -*- coding: UTF-8 -*-
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from dateutil.relativedelta import relativedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from sql.models import SqlWorkflow, QueryPrivilegesApply, Instance

User = get_user_model()


class TestDashboard(TestCase):
    """测试仪表板功能"""

    def setUp(self):
        """初始化测试环境"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="test_user",
            password="test_password",
            display="测试用户",
            is_active=True,
        )
        self.superuser = User.objects.create_superuser(
            username="admin",
            password="admin_password",
            display="管理员",
            is_active=True,
        )

    def tearDown(self):
        """清理测试数据"""
        User.objects.all().delete()
        SqlWorkflow.objects.all().delete()
        QueryPrivilegesApply.objects.all().delete()
        Instance.objects.all().delete()

    @patch("common.dashboard.ChartDao")
    def test_dashboard_pyecharts_success(self, mock_chart_dao):
        """测试成功获取仪表板数据"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(User)
        permission = Permission.objects.create(
            codename="menu_dashboard",
            name="Can view dashboard",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # 创建测试数据
        Instance.objects.create(
            instance_name="test_mysql",
            type="master",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="root",
            password="password",
        )

        # Mock ChartDao
        mock_dao_instance = MagicMock()
        mock_dao_instance.instance_count_by_type.return_value = {
            "rows": [("mysql", 1), ("pgsql", 2)]
        }
        mock_dao_instance.query_instance_env_info.return_value = {
            "rows": [("production", "mysql", 1), ("test", "mysql", 1)]
        }
        mock_dao_instance.workflow_by_date.return_value = {
            "rows": [("2024-01-01", 5), ("2024-01-02", 3)]
        }
        mock_dao_instance.get_date_list.return_value = ["2024-01-01", "2024-01-02"]
        mock_chart_dao.return_value = mock_dao_instance

        self.client.force_login(self.user)
        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "dashboard")

    @patch("common.dashboard.ChartDao")
    def test_dashboard_api_success(self, mock_chart_dao):
        """测试仪表板API成功返回"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(User)
        permission = Permission.objects.create(
            codename="menu_dashboard",
            name="Can view dashboard",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock ChartDao
        mock_dao_instance = MagicMock()
        mock_dao_instance.workflow_by_date.return_value = {
            "rows": [("2024-01-01", 5), ("2024-01-02", 3)]
        }
        mock_dao_instance.get_date_list.return_value = ["2024-01-01", "2024-01-02"]
        mock_chart_dao.return_value = mock_dao_instance

        self.client.force_login(self.user)
        response = self.client.get(
            "/dashboard/api/",
            {
                "start_date": "2024-01-01",
                "end_date": "2024-01-07",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("chart", data)

    def test_dashboard_api_invalid_date_format(self):
        """测试无效日期格式"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(User)
        permission = Permission.objects.create(
            codename="menu_dashboard",
            name="Can view dashboard",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.get(
            "/dashboard/api/",
            {
                "start_date": "invalid-date",
                "end_date": "2024-01-07",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_dashboard_api_missing_parameters(self):
        """测试缺少必需参数"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(User)
        permission = Permission.objects.create(
            codename="menu_dashboard",
            name="Can view dashboard",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.get(
            "/dashboard/api/",
            {},  # Missing start_date and end_date
        )

        # Should return 400 for missing required parameters
        self.assertEqual(response.status_code, 400)

    def test_dashboard_count_stats(self):
        """测试仪表板统计数据"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(User)
        permission = Permission.objects.create(
            codename="menu_dashboard",
            name="Can view dashboard",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # 创建测试数据
        instance = Instance.objects.create(
            instance_name="test_mysql",
            type="master",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="root",
            password="password",
        )

        # 验证统计数据准确性
        self.assertEqual(Instance.objects.count(), 1)
        self.assertEqual(
            User.objects.filter(is_active=True).count(), 2
        )  # test_user + admin

    def test_validate_date_valid(self):
        """测试日期验证 - 有效日期"""
        from common.dashboard import validate_date

        # 直接测试实际函数
        result = validate_date("2024-01-01")
        self.assertEqual(result, "2024-01-01")

    def test_validate_date_invalid(self):
        """测试日期验证 - 无效日期"""
        from common.dashboard import validate_date
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            validate_date("invalid-date")

    def test_validate_date_wrong_format(self):
        """测试日期验证 - 错误格式"""
        from common.dashboard import validate_date
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            validate_date("01/01/2024")  # 应该是 YYYY-MM-DD 格式

    @patch("common.dashboard.ChartDao")
    def test_get_chart_data(self, mock_chart_dao):
        """测试获取图表数据"""
        from common.dashboard import get_chart_data

        # Mock ChartDao
        mock_dao_instance = MagicMock()
        mock_dao_instance.workflow_by_date.return_value = {
            "rows": [("2024-01-01", 5), ("2024-01-02", 3)]
        }
        mock_dao_instance.get_date_list.return_value = ["2024-01-01", "2024-01-02"]
        mock_dao_instance.workflow_by_group.return_value = {
            "rows": [("group1", 10), ("group2", 5)]
        }
        mock_dao_instance.workflow_by_user.return_value = {
            "rows": [("user1", 8), ("user2", 7)]
        }
        mock_dao_instance.syntax_check.return_value = {
            "rows": [("通过", 15), ("驳回", 5)]
        }
        mock_dao_instance.query_by_date.return_value = {
            "rows": [("2024-01-01", 100), ("2024-01-02", 120)]
        }
        mock_dao_instance.query_by_user.return_value = {
            "rows": [("user1", 50), ("user2", 70)]
        }
        mock_chart_dao.return_value = mock_dao_instance

        # 调用函数
        result = get_chart_data("2024-01-01", "2024-01-07")

        # 验证返回结果
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        # 验证ChartDao方法被正确调用
        mock_dao_instance.workflow_by_date.assert_called()
        mock_dao_instance.get_date_list.assert_called()

    def test_dashboard_without_permission(self):
        """测试无权限访问仪表板"""
        self.client.force_login(self.user)
        response = self.client.get("/dashboard/")

        # 应该返回403或重定向
        self.assertIn(response.status_code, [302, 403])
