# -*- coding: UTF-8 -*-
import datetime
import json
from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from common.config import SysConfig
from sql.engines.models import ResultSet
from sql.models import Instance, QueryLog, QueryPrivilegesApply
from sql.utils.resource_group import user_instances

User = get_user_model()


class TestQuery(TestCase):
    """测试查询功能"""

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
        self.instance = Instance.objects.create(
            instance_name="test_instance",
            type="master",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="test_user",
            password="test_password",
        )

    def tearDown(self):
        """清理测试数据"""
        User.objects.all().delete()
        Instance.objects.all().delete()
        QueryLog.objects.all().delete()

    @patch("sql.query.user_instances")
    @patch("sql.query.get_engine")
    @patch("sql.query.query_priv_check")
    def test_query_success(self, mock_priv_check, mock_get_engine, mock_user_instances):
        """测试成功查询"""
        # 设置权限 - 只添加query_submit权限
        query_perm = Permission.objects.get(codename="query_submit")
        self.user.user_permissions.add(query_perm)

        # Mock user_instances
        mock_user_instances.return_value = Instance.objects.filter(
            instance_name="test_instance"
        )

        # Mock query engine
        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "has_star": False,
            "filtered_sql": "SELECT * FROM test_table LIMIT 100",
        }
        mock_engine.filter_sql.return_value = "SELECT * FROM test_table LIMIT 100"
        mock_engine.thread_id = 123
        mock_engine.get_connection.return_value = None

        # Mock query result
        mock_result = ResultSet()
        mock_result.rows = [("test_data",)]
        mock_result.column_list = ["column1"]
        mock_result.affected_rows = 1
        mock_result.error = None
        mock_engine.query.return_value = mock_result

        mock_get_engine.return_value = mock_engine

        # Mock privilege check
        mock_priv_check.return_value = {
            "status": 0,
            "data": {"limit_num": 100, "priv_check": True},
        }

        # 登录并执行查询
        self.client.force_login(self.user)
        response = self.client.post(
            "/query/",
            {
                "instance_name": "test_instance",
                "sql_content": "SELECT * FROM test_table",
                "db_name": "test_db",
                "limit_num": 100,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 0)

    @patch("sql.query.user_instances")
    def test_query_instance_not_found(self, mock_user_instances):
        """测试实例不存在的情况"""
        # 设置权限 - 只添加query_submit权限
        query_perm = Permission.objects.get(codename="query_submit")
        self.user.user_permissions.add(query_perm)

        # Mock user_instances to raise DoesNotExist
        mock_user_instances.return_value.get.side_effect = Instance.DoesNotExist

        self.client.force_login(self.user)
        response = self.client.post(
            "/query/",
            {
                "instance_name": "nonexistent_instance",
                "sql_content": "SELECT * FROM test_table",
                "db_name": "test_db",
                "limit_num": 100,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("未关联该实例", data["msg"])

    @patch("sql.query.user_instances")
    def test_query_missing_parameters(self, mock_user_instances):
        """测试缺少必需参数的情况"""
        # 设置权限
        # 设置权限 - 只添加query_submit权限
        query_perm = Permission.objects.get(codename="query_submit")
        self.user.user_permissions.add(query_perm)

        mock_user_instances.return_value = Instance.objects.filter(
            instance_name="test_instance"
        )

        self.client.force_login(self.user)
        response = self.client.post(
            "/query/",
            {
                "instance_name": "test_instance",
                # Missing sql_content, db_name, limit_num
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("参数可能为空", data["msg"])

    @patch("sql.query.user_instances")
    @patch("sql.query.get_engine")
    def test_query_bad_query(self, mock_get_engine, mock_user_instances):
        """测试禁止执行的查询"""
        # 设置权限
        # 设置权限 - 只添加query_submit权限
        query_perm = Permission.objects.get(codename="query_submit")
        self.user.user_permissions.add(query_perm)

        mock_user_instances.return_value = Instance.objects.filter(
            instance_name="test_instance"
        )

        # Mock query engine with bad query
        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": True,
            "msg": "禁止执行的SQL语句",
        }
        mock_get_engine.return_value = mock_engine

        self.client.force_login(self.user)
        response = self.client.post(
            "/query/",
            {
                "instance_name": "test_instance",
                "sql_content": "DELETE FROM test_table",
                "db_name": "test_db",
                "limit_num": 100,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("禁止执行", data["msg"])

    @patch("sql.query.user_instances")
    @patch("sql.query.get_engine")
    @patch("sql.query.SysConfig")
    def test_query_disable_star(
        self, mock_config, mock_get_engine, mock_user_instances
    ):
        """测试禁用*的情况"""
        # 设置权限 - 只添加query_submit权限
        query_perm = Permission.objects.get(codename="query_submit")
        self.user.user_permissions.add(query_perm)

        mock_user_instances.return_value = Instance.objects.filter(
            instance_name="test_instance"
        )

        # Mock config to disable star
        mock_sys_config = MagicMock()
        mock_sys_config.get.return_value = True
        mock_config.return_value = mock_sys_config

        # Mock query engine with star
        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "has_star": True,
            "msg": "禁止使用*查询",
        }
        mock_get_engine.return_value = mock_engine

        self.client.force_login(self.user)
        response = self.client.post(
            "/query/",
            {
                "instance_name": "test_instance",
                "sql_content": "SELECT * FROM test_table",
                "db_name": "test_db",
                "limit_num": 100,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("禁止", data["msg"])

    @patch("sql.query.user_instances")
    @patch("sql.query.get_engine")
    @patch("sql.query.query_priv_check")
    def test_query_permission_denied(
        self, mock_priv_check, mock_get_engine, mock_user_instances
    ):
        """测试权限检查失败"""
        # 设置权限 - 只添加query_submit权限
        query_perm = Permission.objects.get(codename="query_submit")
        self.user.user_permissions.add(query_perm)

        mock_user_instances.return_value = Instance.objects.filter(
            instance_name="test_instance"
        )

        # Mock query engine
        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "has_star": False,
            "filtered_sql": "SELECT * FROM test_table LIMIT 100",
        }
        mock_get_engine.return_value = mock_engine

        # Mock privilege check failure
        mock_priv_check.return_value = {
            "status": 1,
            "msg": "你无权查询该数据库",
        }

        self.client.force_login(self.user)
        response = self.client.post(
            "/query/",
            {
                "instance_name": "test_instance",
                "sql_content": "SELECT * FROM test_table",
                "db_name": "test_db",
                "limit_num": 100,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("无权", data["msg"])

    def test_query_without_permission(self):
        """测试没有查询权限的情况"""
        self.client.force_login(self.user)
        response = self.client.post(
            "/query/",
            {
                "instance_name": "test_instance",
                "sql_content": "SELECT * FROM test_table",
                "db_name": "test_db",
                "limit_num": 100,
            },
        )

        # Should redirect or return 403
        self.assertIn(response.status_code, [302, 403])
