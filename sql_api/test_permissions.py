# -*- coding: UTF-8 -*-
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.request import Request

from common.config import SysConfig
from sql_api.permissions import IsInUserWhitelist, IsOwner

User = get_user_model()


class TestIsInUserWhitelist(TestCase):
    """测试白名单权限"""

    def setUp(self):
        """初始化测试环境"""
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            username="test_user",
            password="test_password",
            display="测试用户",
            is_active=True,
        )
        self.permission = IsInUserWhitelist()

    def tearDown(self):
        """清理测试数据"""
        User.objects.all().delete()

    @patch.object(SysConfig, "get")
    def test_user_in_whitelist(self, mock_get):
        """测试用户在白名单中"""
        # Mock配置返回包含当前用户ID的白名单
        mock_get.return_value = f"{self.user.id},2,3"

        request = self.factory.get("/api/test/")
        request.user = self.user

        has_permission = self.permission.has_permission(request, None)
        self.assertTrue(has_permission)

    @patch.object(SysConfig, "get")
    def test_user_not_in_whitelist(self, mock_get):
        """测试用户不在白名单中"""
        # Mock配置返回不包含当前用户ID的白名单
        mock_get.return_value = "2,3,4"

        request = self.factory.get("/api/test/")
        request.user = self.user

        has_permission = self.permission.has_permission(request, None)
        self.assertFalse(has_permission)

    @patch.object(SysConfig, "get")
    def test_empty_whitelist(self, mock_get):
        """测试空白名单"""
        # Mock配置返回空白名单
        mock_get.return_value = ""

        request = self.factory.get("/api/test/")
        request.user = self.user

        has_permission = self.permission.has_permission(request, None)
        self.assertFalse(has_permission)

    @patch.object(SysConfig, "get")
    def test_none_whitelist(self, mock_get):
        """测试未配置白名单"""
        # Mock配置返回None
        mock_get.return_value = None

        request = self.factory.get("/api/test/")
        request.user = self.user

        has_permission = self.permission.has_permission(request, None)
        self.assertFalse(has_permission)

    @patch.object(SysConfig, "get")
    def test_whitelist_with_spaces(self, mock_get):
        """测试白名单配置包含空格"""
        # Mock配置返回包含空格的白名单
        mock_get.return_value = f" {self.user.id} , 2 , 3 "

        request = self.factory.get("/api/test/")
        request.user = self.user

        has_permission = self.permission.has_permission(request, None)
        # int() 可以处理前后空格，所以应该返回True
        self.assertTrue(has_permission)


class TestIsOwner(TestCase):
    """测试所有者权限"""

    def setUp(self):
        """初始化测试环境"""
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            username="test_user",
            password="test_password",
            display="测试用户",
            is_active=True,
        )
        self.other_user = User.objects.create_user(
            username="other_user",
            password="test_password",
            display="其他用户",
            is_active=True,
        )
        self.permission = IsOwner()

    def tearDown(self):
        """清理测试数据"""
        User.objects.all().delete()

    def test_user_is_owner(self):
        """测试用户是所有者"""
        import json

        request = self.factory.post(
            "/api/test/",
            data=json.dumps({"engineer": "test_user"}),
            content_type="application/json",
        )
        # Wrap in DRF Request to parse data
        request = Request(request)
        request.user = self.user

        has_permission = self.permission.has_permission(request, None)
        self.assertTrue(has_permission)

    def test_user_is_not_owner(self):
        """测试用户不是所有者"""
        import json

        request = self.factory.post(
            "/api/test/",
            data=json.dumps({"engineer": "other_user"}),
            content_type="application/json",
        )
        # Wrap in DRF Request to parse data
        request = Request(request)
        request.user = self.user

        has_permission = self.permission.has_permission(request, None)
        self.assertFalse(has_permission)

    def test_missing_engineer_parameter(self):
        """测试缺少engineer参数"""
        import json

        request = self.factory.post(
            "/api/test/", data=json.dumps({}), content_type="application/json"
        )
        # Wrap in DRF Request to parse data
        request = Request(request)
        request.user = self.user

        has_permission = self.permission.has_permission(request, None)
        self.assertFalse(has_permission)

    def test_none_engineer_parameter(self):
        """测试engineer参数为None"""
        import json

        request = self.factory.post(
            "/api/test/",
            data=json.dumps({"engineer": None}),
            content_type="application/json",
        )
        # Wrap in DRF Request to parse data
        request = Request(request)
        request.user = self.user

        has_permission = self.permission.has_permission(request, None)
        self.assertFalse(has_permission)

    def test_empty_engineer_parameter(self):
        """测试engineer参数为空字符串"""
        import json

        request = self.factory.post(
            "/api/test/",
            data=json.dumps({"engineer": ""}),
            content_type="application/json",
        )
        # Wrap in DRF Request to parse data
        request = Request(request)
        request.user = self.user

        has_permission = self.permission.has_permission(request, None)
        self.assertFalse(has_permission)

    def test_case_sensitive_username(self):
        """测试用户名大小写敏感"""
        import json

        request = self.factory.post(
            "/api/test/",
            data=json.dumps({"engineer": "TEST_USER"}),  # 大写用户名
            content_type="application/json",
        )
        # Wrap in DRF Request to parse data
        request = Request(request)
        request.user = self.user  # 小写用户名

        has_permission = self.permission.has_permission(request, None)
        # 取决于实现，如果用户名大小写敏感，应该返回False
        self.assertFalse(has_permission)
