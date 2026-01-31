# -*- coding: UTF-8 -*-
import datetime
import json
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, RequestFactory

from sql.models import AuditEntry
from sql.audit_log import (
    audit_input,
    audit_log,
    get_client_ip,
    user_logged_in_callback,
    user_logged_out_callback,
    user_login_failed_callback,
)

User = get_user_model()


class TestAuditLog(TestCase):
    """测试审计日志功能"""

    def setUp(self):
        """初始化测试环境"""
        self.client = Client()
        self.factory = RequestFactory()
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
        AuditEntry.objects.all().delete()

    def test_audit_input_success(self):
        """测试成功记录审计日志"""
        self.client.force_login(self.user)
        response = self.client.post(
            "/audit/input/",
            {
                "action": "查询数据",
                "extra_info": "查询了test_table表",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["user_name"], "test_user")
        self.assertEqual(data["action"], "查询数据")
        self.assertEqual(data["extra_info"], "查询了test_table表")

        # 验证数据库中是否创建了记录
        audit = AuditEntry.objects.filter(
            user_name="test_user", action="查询数据"
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.extra_info, "查询了test_table表")

    def test_audit_input_without_extra_info(self):
        """测试不带额外信息的审计日志"""
        self.client.force_login(self.user)
        response = self.client.post(
            "/audit/input/",
            {
                "action": "登录系统",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["action"], "登录系统")
        self.assertEqual(data["extra_info"], "")

    def test_audit_log_list(self):
        """测试获取审计日志列表"""
        # 创建测试数据
        AuditEntry.objects.create(
            user_id=self.user.id,
            user_name=self.user.username,
            user_display=self.user.display,
            action="查询数据",
            extra_info="查询了test_table表",
        )
        AuditEntry.objects.create(
            user_id=self.user.id,
            user_name=self.user.username,
            user_display=self.user.display,
            action="修改配置",
            extra_info="修改了系统配置",
        )

        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(User)
        permission = Permission.objects.create(
            codename="audit_user",
            name="Can audit user",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            "/audit/log/",
            {
                "limit": 10,
                "offset": 0,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["rows"]), 2)

    def test_audit_log_filter_by_action(self):
        """测试按操作类型过滤审计日志"""
        # 创建测试数据
        AuditEntry.objects.create(
            user_id=self.user.id,
            user_name=self.user.username,
            user_display=self.user.display,
            action="查询数据",
            extra_info="test",
        )
        AuditEntry.objects.create(
            user_id=self.user.id,
            user_name=self.user.username,
            user_display=self.user.display,
            action="修改配置",
            extra_info="test",
        )

        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(User)
        permission = Permission.objects.create(
            codename="audit_user",
            name="Can audit user",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            "/audit/log/",
            {
                "limit": 10,
                "offset": 0,
                "action": "查询数据",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["rows"][0]["action"], "查询数据")

    def test_audit_log_filter_by_date_range(self):
        """测试按日期范围过滤审计日志"""
        # 创建不同日期的测试数据
        today = datetime.datetime.now()
        yesterday = today - datetime.timedelta(days=1)

        AuditEntry.objects.create(
            user_id=self.user.id,
            user_name=self.user.username,
            user_display=self.user.display,
            action="查询数据",
            extra_info="today",
            action_time=today,
        )
        AuditEntry.objects.create(
            user_id=self.user.id,
            user_name=self.user.username,
            user_display=self.user.display,
            action="查询数据",
            extra_info="yesterday",
            action_time=yesterday,
        )

        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(User)
        permission = Permission.objects.create(
            codename="audit_user",
            name="Can audit user",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            "/audit/log/",
            {
                "limit": 10,
                "offset": 0,
                "start_date": today.strftime("%Y-%m-%d"),
                "end_date": today.strftime("%Y-%m-%d"),
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["rows"][0]["extra_info"], "today")

    def test_audit_log_search(self):
        """测试搜索审计日志"""
        # 创建测试数据
        AuditEntry.objects.create(
            user_id=self.user.id,
            user_name=self.user.username,
            user_display=self.user.display,
            action="查询数据",
            extra_info="查询了test_table表",
        )
        AuditEntry.objects.create(
            user_id=self.user.id,
            user_name=self.user.username,
            user_display=self.user.display,
            action="修改配置",
            extra_info="修改了系统配置",
        )

        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(User)
        permission = Permission.objects.create(
            codename="audit_user",
            name="Can audit user",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            "/audit/log/",
            {
                "limit": 10,
                "offset": 0,
                "search": "test_table",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)
        self.assertIn("test_table", data["rows"][0]["extra_info"])

    def test_get_client_ip_with_forwarded_for(self):
        """测试从X-Forwarded-For获取客户端IP"""
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "192.168.1.1, 10.0.0.1"

        ip = get_client_ip(request)
        self.assertEqual(ip, "192.168.1.1")

    def test_get_client_ip_without_forwarded_for(self):
        """测试从REMOTE_ADDR获取客户端IP"""
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.2"

        ip = get_client_ip(request)
        self.assertEqual(ip, "192.168.1.2")

    def test_user_logged_in_callback(self):
        """测试用户登录回调"""
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        user_logged_in_callback(None, request, self.user)

        # 验证是否创建了登录日志
        audit = AuditEntry.objects.filter(
            user_name=self.user.username, action="登入"
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.extra_info, "192.168.1.1")

    def test_user_logged_out_callback(self):
        """测试用户登出回调"""
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.2"

        user_logged_out_callback(None, request, self.user)

        # 验证是否创建了登出日志
        audit = AuditEntry.objects.filter(
            user_name=self.user.username, action="登出"
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.extra_info, "192.168.1.2")

    def test_user_login_failed_callback_existing_user(self):
        """测试登录失败回调 - 已存在的用户"""
        credentials = {"username": "test_user"}

        user_login_failed_callback(None, credentials=credentials)

        # 验证是否创建了登录失败日志
        audit = AuditEntry.objects.filter(
            user_name="test_user", action="登入失败"
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.user_id, self.user.id)
        self.assertEqual(audit.user_display, "测试用户")

    def test_user_login_failed_callback_nonexistent_user(self):
        """测试登录失败回调 - 不存在的用户"""
        credentials = {"username": "nonexistent_user"}

        user_login_failed_callback(None, credentials=credentials)

        # 验证是否创建了登录失败日志
        audit = AuditEntry.objects.filter(
            user_name="nonexistent_user", action="登入失败"
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.user_id, 0)
        self.assertEqual(audit.user_display, "")
