import datetime
import logging
import traceback

import simplejson as json
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.models import Group
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature

from django.conf import settings
from common.config import SysConfig
from common.utils.ding_api import get_ding_user_id
from common.utils.sendmsg import MsgSender
from sql.models import Users, ResourceGroup, TwoFactorAuthConfig

logger = logging.getLogger("default")


def init_user(user):
    """
    给用户关联默认资源组和权限组
    :param user:
    :return:
    """
    # 添加到默认权限组
    default_auth_group = SysConfig().get("default_auth_group", "")
    if default_auth_group:
        default_auth_group = default_auth_group.split(",")
        [
            user.groups.add(group)
            for group in Group.objects.filter(name__in=default_auth_group)
        ]

    # 添加到默认资源组
    default_resource_group = SysConfig().get("default_resource_group", "")
    if default_resource_group:
        default_resource_group = default_resource_group.split(",")
        [
            user.resource_group.add(group)
            for group in ResourceGroup.objects.filter(
                group_name__in=default_resource_group
            )
        ]


class ArcheryAuth(object):
    def __init__(self, request):
        self.request = request
        self.sys_config = SysConfig()

    @staticmethod
    def challenge(username=None, password=None):
        # 仅验证密码, 验证成功返回 user 对象, 清空计数器
        user = authenticate(username=username, password=password)
        # 登录成功
        if user:
            # 如果登录成功, 登录失败次数重置为0
            user.failed_login_count = 0
            user.save()
            return user

    def authenticate(self):
        username = self.request.POST.get("username")
        password = self.request.POST.get("password")
        # 确认用户是否已经存在
        try:
            user = Users.objects.get(username=username)
        except Users.DoesNotExist:
            authenticated_user = self.challenge(username=username, password=password)
            if authenticated_user:
                # ldap 首次登录逻辑
                init_user(authenticated_user)
                return {"status": 0, "msg": "ok", "data": authenticated_user}
            else:
                return {
                    "status": 1,
                    "msg": "用户名或密码错误，请重新输入！",
                    "data": "",
                }
        except Exception as e:
            logger.error("验证用户密码时报错")
            logger.error(traceback.format_exc())
            return {"status": 1, "msg": f"服务异常，请联系管理员处理", "data": ""}
        # 已存在用户, 验证是否在锁期间
        # 读取配置文件
        lock_count = int(self.sys_config.get("lock_cnt_threshold", 5))
        lock_time = int(self.sys_config.get("lock_time_threshold", 60 * 5))
        # 验证是否在锁, 分了几个if 防止代码太长
        if user.failed_login_count and user.last_login_failed_at:
            if user.failed_login_count >= lock_count:
                now = datetime.datetime.now()
                if (
                    user.last_login_failed_at + datetime.timedelta(seconds=lock_time)
                    > now
                ):
                    return {
                        "status": 3,
                        "msg": f"登录失败超过限制，该账号已被锁定！请等候大约{lock_time}秒再试",
                        "data": "",
                    }
                else:
                    # 如果锁已超时, 重置失败次数
                    user.failed_login_count = 0
                    user.save()
        authenticated_user = self.challenge(username=username, password=password)
        if authenticated_user:
            if not authenticated_user.last_login:
                init_user(authenticated_user)
            return {"status": 0, "msg": "ok", "data": authenticated_user}
        user.failed_login_count += 1
        user.last_login_failed_at = datetime.datetime.now()
        user.save()
        return {"status": 1, "msg": "用户名或密码错误，请重新输入！", "data": ""}


# ajax接口，登录页面调用，用来验证用户名密码
def authenticate_entry(request):
    """接收http请求，然后把请求中的用户名密码传给ArcherAuth去验证"""
    new_auth = ArcheryAuth(request)
    result = new_auth.authenticate()
    if result["status"] == 0:
        authenticated_user = result["data"]
        twofa_enabled = TwoFactorAuthConfig.objects.filter(user=authenticated_user)
        # 是否开启全局2fa
        if SysConfig().get("enforce_2fa"):
            # 用户是否配置过2fa
            if twofa_enabled:
                verify_mode = "verify_only"
            else:
                verify_mode = "verify_config"
            # 设置无登录状态session
            s = SessionStore()
            s["user"] = authenticated_user.username
            s["verify_mode"] = verify_mode
            s.set_expiry(300)
            s.create()
            result = {"status": 0, "msg": "ok", "data": s.session_key}
        else:
            # 用户是否配置过2fa
            if twofa_enabled:
                # 设置无登录状态session
                s = SessionStore()
                s["user"] = authenticated_user.username
                s["verify_mode"] = "verify_only"
                s.set_expiry(300)
                s.create()
                result = {"status": 0, "msg": "ok", "data": s.session_key}
            else:
                # 未设置2fa直接登录
                login(request, authenticated_user)
                # 从钉钉获取该用户的 dingding_id，用于单独给他发消息
                if SysConfig().get(
                    "ding_to_person"
                ) is True and "admin" not in request.POST.get("username"):
                    get_ding_user_id(request.POST.get("username"))
                result = {"status": 0, "msg": "ok", "data": None}

    return HttpResponse(json.dumps(result), content_type="application/json")


# 注册用户
def sign_up(request):
    sign_up_enabled = SysConfig().get("sign_up_enabled", False)
    if not sign_up_enabled:
        result = {"status": 1, "msg": "注册未启用,请联系管理员开启", "data": None}
        return HttpResponse(json.dumps(result), content_type="application/json")
    username = request.POST.get("username")
    password = request.POST.get("password")
    password2 = request.POST.get("password2")
    display = request.POST.get("display")
    email = request.POST.get("email")
    result = {"status": 0, "msg": "ok", "data": None}

    if not (username and password):
        result["status"] = 1
        result["msg"] = "用户名和密码不能为空"
    elif len(Users.objects.filter(username=username)) > 0:
        result["status"] = 1
        result["msg"] = "用户名已存在"
    elif password != password2:
        result["status"] = 1
        result["msg"] = "两次输入密码不一致"
    elif not display:
        result["status"] = 1
        result["msg"] = "请填写中文名"
    elif not email:
        result["status"] = 1
        result["msg"] = "请填写邮箱"
    else:
        # 验证密码
        try:
            validate_password(password)

            signer = TimestampSigner()
            token = signer.sign(username)
            import urllib.parse

            token_encoded = urllib.parse.quote(token)
            base_url = (
                SysConfig().get("archery_base_url", "http://127.0.0.1:9123").rstrip("/")
            )
            verify_link = f"{base_url}/verify_email/?token={token_encoded}"

            html_content = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px;">
                <h3>Archery 注册邮箱验证</h3>
                <p>请点击下方链接完成邮箱激活（24小时内有效）：</p>
                <p><a href="{verify_link}" style="color: #337ab7; text-decoration: none; word-break: break-all;">{verify_link}</a></p>
                <p style="color: #999; font-size: 12px; margin-top: 30px;">如果上述链接无法点击，请完整复制该链接并粘贴至浏览器地址栏中访问。</p>
            </div>
            """

            try:
                MsgSender().send_email(
                    "Archery 注册邮箱验证", html_content, [email], content_type="html"
                )
            except Exception as e:
                logger.error(f"注册发送邮件失败: {traceback.format_exc()}")
                result["status"] = 1
                result["msg"] = f"发送验证邮件失败, 请联系管理员检查邮件配置: {str(e)}"
                return HttpResponse(json.dumps(result), content_type="application/json")

            Users.objects.create_user(
                username=username,
                password=password,
                display=display,
                email=email,
                is_active=0,
                is_staff=True,
            )
            result["msg"] = "注册成功，请前往邮箱点击激活链接"
        except ValidationError as msg:
            result["status"] = 1
            result["msg"] = str(msg)
    return HttpResponse(json.dumps(result), content_type="application/json")


# 退出登录
def sign_out(request):
    user = request.user
    logout(request)
    # 如果开启了钉钉认证，重定向到钉钉退出登录页面
    if user.ding_user_id and settings.ENABLE_DINGDING:
        return HttpResponseRedirect(
            redirect_to="https://login.dingtalk.com/oauth2/logout"
        )
    return HttpResponseRedirect(reverse("sql:login"))


def verify_email(request):
    token = request.GET.get("token")
    if not token:
        return HttpResponse("缺少 token 参数", status=400)

    # 强制清理当前浏览器的登录状态，避免激活后直接带着上一个账号的 Session 登录
    logout(request)

    signer = TimestampSigner()
    try:
        # 24小时有效期
        username = signer.unsign(token, max_age=86400)
        user = Users.objects.get(username=username)
        user.is_active = 1
        user.save()

        success_html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>邮箱激活成功</title>
            <meta http-equiv="refresh" content="3;url=/login/" />
            <style>
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; text-align: center; padding-top: 100px; background-color: #f7f7f7; }}
                .msg-box {{ background-color: #fff; padding: 40px; border-radius: 8px; display: inline-block; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                h2 {{ color: #5cb85c; }}
                p {{ color: #666; margin-top: 20px; font-size: 16px; }}
                a {{ color: #337ab7; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <div class="msg-box">
                <h2>✓ 邮箱激活成功！</h2>
                <p>您的账号 <b>{username}</b> 已成功激活并可正常登录。</p>
                <p>3秒后将自动跳转到<a href="/login/">登录页面</a>...</p>
            </div>
        </body>
        </html>
        """
        return HttpResponse(success_html)
    except SignatureExpired:
        return HttpResponse("激活链接已过期，请重新注册", status=400)
    except BadSignature:
        return HttpResponse("激活链接无效", status=400)
    except Users.DoesNotExist:
        return HttpResponse("用户不存在", status=404)
    except Exception:
        logger.error(f"激活邮箱异常: {traceback.format_exc()}")
        return HttpResponse("系统异常", status=500)
