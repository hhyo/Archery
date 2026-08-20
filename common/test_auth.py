import datetime
import json
import time
from unittest.mock import patch

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.core.signing import TimestampSigner
from django.core.cache import cache
from django.http import HttpResponse
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.models import AnonymousUser

from common.config import SysConfig
from common.auth import (
    init_user,
    ArcheryAuth,
    authenticate_entry,
    sign_up,
    verify_email,
)
from sql.models import Users, ResourceGroup

User = get_user_model()


class TestAuth(TestCase):
    def setUp(self):
        self.username = "some_user"
        self.password = "some_str"
        self.u1 = User(username=self.username, password=self.password, display="用户1")
        self.u1.save()
        self.resource_group1 = ResourceGroup.objects.create(group_name="some_group")
        sys_config = SysConfig()
        sys_config.set("default_resource_group", self.resource_group1.group_name)

    def tearDown(self):
        self.u1.delete()
        self.resource_group1.delete()
        SysConfig().purge()

    def test_init_user(self):
        """用户初始化测试测试"""
        init_user(self.u1)
        self.assertEqual(self.u1, self.resource_group1.users_set.get(pk=self.u1.pk))
        # init 需要是无状态的, 可以重复执行, 执行一次和执行n次结果一样
        init_user(self.u1)
        self.assertEqual(self.u1, self.resource_group1.users_set.get(pk=self.u1.pk))


class TestArcheryAuth(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.sys_config = SysConfig()
        self.username = "test_auth_user"
        self.password = "test_password123"
        self.user = Users.objects.create_user(
            username=self.username, password=self.password, display="AuthUser"
        )
        self.resource_group = ResourceGroup.objects.create(group_name="default_group")
        self.sys_config.set("default_resource_group", self.resource_group.group_name)
        self.sys_config.set("lock_cnt_threshold", 3)
        self.sys_config.set("lock_time_threshold", 60)

    def tearDown(self):
        self.user.delete()
        self.resource_group.delete()
        self.sys_config.purge()

    def test_authenticate_success(self):
        request = self.factory.post(
            "/login/", {"username": self.username, "password": self.password}
        )
        auth = ArcheryAuth(request)
        result = auth.authenticate()
        self.assertEqual(result["status"], 0)
        self.assertEqual(result["data"].username, self.username)

    def test_authenticate_wrong_password(self):
        request = self.factory.post(
            "/login/", {"username": self.username, "password": "wrong_password"}
        )
        auth = ArcheryAuth(request)
        result = auth.authenticate()
        self.assertEqual(result["status"], 1)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_count, 1)

    def test_authenticate_locked(self):
        self.user.failed_login_count = 3
        self.user.last_login_failed_at = datetime.datetime.now()
        self.user.save()
        request = self.factory.post(
            "/login/", {"username": self.username, "password": self.password}
        )
        auth = ArcheryAuth(request)
        result = auth.authenticate()
        self.assertEqual(result["status"], 3)
        self.assertIn("已被锁定", result["msg"])

    def test_authenticate_lock_expired(self):
        self.user.failed_login_count = 3
        self.user.last_login_failed_at = datetime.datetime.now() - datetime.timedelta(
            seconds=100
        )
        self.user.save()
        request = self.factory.post(
            "/login/", {"username": self.username, "password": self.password}
        )
        auth = ArcheryAuth(request)
        result = auth.authenticate()
        self.assertEqual(result["status"], 0)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_count, 0)

    @patch("common.auth.ArcheryAuth.challenge")
    def test_authenticate_new_ldap_user(self, mock_challenge):
        request = self.factory.post(
            "/login/", {"username": "new_ldap_user", "password": "password"}
        )
        auth = ArcheryAuth(request)
        new_user = Users.objects.create(username="new_ldap_user")
        mock_challenge.return_value = new_user
        result = auth.authenticate()
        self.assertEqual(result["status"], 0)
        self.assertEqual(result["data"].username, "new_ldap_user")

    @patch("common.auth.login")
    def test_authenticate_entry(self, mock_login):
        request = self.factory.post(
            "/login/", {"username": self.username, "password": self.password}
        )
        middleware = SessionMiddleware(lambda req: HttpResponse())
        middleware.process_request(request)
        response = authenticate_entry(request)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(content["status"], 0)


class TestSignUp(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.sys_config = SysConfig()
        self.sys_config.set("sign_up_enabled", True)

    def tearDown(self):
        self.sys_config.purge()

    def test_sign_up_disabled(self):
        self.sys_config.set("sign_up_enabled", False)
        request = self.factory.post("/signup/", {})
        response = sign_up(request)
        content = json.loads(response.content)
        self.assertEqual(content["status"], 1)
        self.assertEqual(content["msg"], "注册未启用,请联系管理员开启")

    def test_sign_up_missing_args(self):
        request = self.factory.post("/signup/", {"username": "test"})
        response = sign_up(request)
        content = json.loads(response.content)
        self.assertEqual(content["status"], 1)
        self.assertEqual(content["msg"], "用户名和密码不能为空")

    def test_sign_up_password_mismatch(self):
        request = self.factory.post(
            "/signup/", {"username": "test", "password": "123", "password2": "456"}
        )
        response = sign_up(request)
        content = json.loads(response.content)
        self.assertEqual(content["status"], 1)
        self.assertEqual(content["msg"], "两次输入密码不一致")

    @patch("common.auth.MsgSender.send_email")
    def test_sign_up_success(self, mock_send_email):
        mock_send_email.return_value = "success"
        request = self.factory.post(
            "/signup/",
            {
                "username": "new_user",
                "password": "StrongPassword123!",
                "password2": "StrongPassword123!",
                "display": "NewUser",
                "email": "new_user@test.com",
            },
        )
        response = sign_up(request)
        content = json.loads(response.content)
        self.assertEqual(content["status"], 0)
        self.assertTrue(Users.objects.filter(username="new_user").exists())
        Users.objects.get(username="new_user").delete()

    @patch("common.auth.MsgSender.send_email")
    def test_sign_up_email_fail(self, mock_send_email):
        mock_send_email.return_value = "fail"
        request = self.factory.post(
            "/signup/",
            {
                "username": "new_user_fail",
                "password": "StrongPassword123!",
                "password2": "StrongPassword123!",
                "display": "NewUser",
                "email": "new_user@test.com",
            },
        )
        response = sign_up(request)
        content = json.loads(response.content)
        self.assertEqual(content["status"], 1)
        self.assertFalse(Users.objects.filter(username="new_user_fail").exists())


class TestVerifyEmail(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.username = "verify_user"
        self.user = Users.objects.create_user(
            username=self.username, password="123", display="Verify", is_active=0
        )
        self.signer = TimestampSigner()

    def tearDown(self):
        Users.objects.filter(username=self.username).delete()

    def test_verify_email_missing_token(self):
        request = self.factory.get("/verify_email/")
        request.user = AnonymousUser()
        response = verify_email(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode(), "缺少 token 参数")

    def test_verify_email_success(self):
        token = self.signer.sign(self.username)
        request = self.factory.get(f"/verify_email/?token={token}")
        request.user = AnonymousUser()
        middleware = SessionMiddleware(lambda req: HttpResponse())
        middleware.process_request(request)
        response = verify_email(request)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.is_active, 1)

    def test_verify_email_expired(self):
        with patch("django.core.signing.time.time", return_value=time.time() - 86401):
            token = self.signer.sign(self.username)

        request = self.factory.get(f"/verify_email/?token={token}")
        request.user = AnonymousUser()
        middleware = SessionMiddleware(lambda req: HttpResponse())
        middleware.process_request(request)
        response = verify_email(request)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Users.objects.filter(username=self.username).exists())

    def test_verify_email_cached(self):
        token = self.signer.sign(self.username)
        cache_key = f"email_activated_{token}"
        cache.set(cache_key, True, timeout=86400)
        request = self.factory.get(f"/verify_email/?token={token}")
        request.user = AnonymousUser()
        middleware = SessionMiddleware(lambda req: HttpResponse())
        middleware.process_request(request)
        response = verify_email(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode(), "激活链接已失效")
        cache.delete(cache_key)

    def test_verify_email_bad_signature(self):
        request = self.factory.get("/verify_email/?token=invalid_token")
        request.user = AnonymousUser()
        middleware = SessionMiddleware(lambda req: HttpResponse())
        middleware.process_request(request)
        response = verify_email(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode(), "激活链接无效")
