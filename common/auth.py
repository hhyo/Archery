import datetime
import logging
import traceback

import simplejson as json
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.models import Group
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from common.config import SysConfig
from sql.utils.ding_api import get_ding_user_id
from sql.models import Users, ResourceGroup, ResourceGroupRelations

logger = logging.getLogger('default')


def init_user(user):
    default_auth_group = SysConfig().sys_config.get('default_auth_group', '')
    if default_auth_group:
        try:
            group = Group.objects.get(name=default_auth_group)
            user.groups.add(group)
        except Exception:
            logger.error(traceback.format_exc())
            logger.error('无name为{}的权限组，无法默认关联，请到系统设置进行配置'.format(default_auth_group))
    # 添加到默认资源组
    default_resource_group = SysConfig().sys_config.get('default_resource_group', '')
    if default_resource_group:
        try:
            new_relation = ResourceGroupRelations(
                object_type=0,
                object_id=user.id,
                object_name=str(user),
                group_id=ResourceGroup.objects.get(group_name=default_resource_group).group_id,
                group_name=default_resource_group)
            new_relation.save()
        except Exception:
            logger.error(traceback.format_exc())
            logger.error('无name为{}的资源组，无法默认关联，请到系统设置进行配置'.format(default_resource_group))


class ArcherAuth(object):
    def __init__(self, request):
        self.request = request

    def challenge(self, username=None, password=None):
        # 仅验证密码, 验证成功返回 user 对象, 清空计数器
        user = authenticate(username=username, password=password)
        # 登录成功
        if user:
            # 从钉钉获取该用户的 dingding_id，用于单独给他发消息
            if SysConfig().get("ding_to_person") is True and "admin" not in username:
                get_ding_user_id(username)

            # 如果登录成功, 登录失败次数重置为0
            user.failed_login_count = 0
            user.save()
            return user

    def authenticate(self):
        username = self.request.POST.get('username')
        password = self.request.POST.get('password')
        # 验证时候在加锁时间内
        now = datetime.datetime.now()
        try:
            user = Users.objects.get(username=username)
        except Users.DoesNotExist:
            authenticated_user = self.challenge(username=username, password=password)
            if authenticated_user:
                # ldap 首次登录逻辑
                init_user(authenticated_user)
                login(self.request, authenticated_user)
                return {'status': 0, 'msg': 'ok', 'data': authenticated_user}
            else:
                return {'status': 1, 'msg': '用户名或密码错误，请重新输入！', 'data': ''}
        except:
            logger.error('验证用户密码时报错')
            logger.error(traceback.format_exc())
            return {'status': 1, 'msg': '服务器错误{}'.format(traceback.format_exc()), 'data': ''}
        # 已存在用户, 验证是否在锁期间
        # 读取配置文件
        sys_config = SysConfig().sys_config
        if sys_config.get('lock_cnt_threshold'):
            lock_count = int(sys_config.get('lock_cnt_threshold'))
        else:
            lock_count = 5
        if sys_config.get('lock_time_threshold'):
            lock_time = int(sys_config.get('lock_time_threshold'))
        else:
            lock_time = 60 * 5
        # 验证是否在锁, 分了几个if 防止代码太长
        if user.failed_login_count and user.last_login_failed_at:
            if user.failed_login_count >= lock_count:
                now = datetime.datetime.now()
                if user.last_login_failed_at + datetime.timedelta(seconds=lock_time) > now:
                    return {'status': 3, 'msg': '登录失败超过限制，该账号已被锁定!请等候大约{}秒再试'.format(lock_time), 'data': ''}
                else:
                    # 如果锁已超时, 重置失败次数
                    user.failed_login_count = 0
                    user.save()
        authenticated_user = self.challenge(username=username, password=password)
        if authenticated_user:
            if not authenticated_user.last_login:
                init_user(authenticated_user)
            login(self.request, authenticated_user)
            return {'status': 0, 'msg': 'ok', 'data': authenticated_user}
        user.failed_login_count += 1
        user.last_login_failed_at = datetime.datetime.now()
        user.save()
        return {'status': 1, 'msg': '用户名或密码错误，请重新输入！', 'data': ''}


# ajax接口，登录页面调用，用来验证用户名密码
def authenticate_entry(request):
    """接收http请求，然后把请求中的用户名密码传给ArcherAuth去验证"""
    new_auth = ArcherAuth(request)
    result = new_auth.authenticate()
    if result['status'] == 0:
        result = {'status': 0, 'msg': 'ok', 'data': None}

    return HttpResponse(json.dumps(result), content_type='application/json')


# 注册用户
def sign_up(request):
    sign_up_enabled = SysConfig().get('sign_up_enabled', False)
    if not sign_up_enabled :
        result = {'status': 1, 'msg': '注册未启用,请联系管理员开启', 'data': None}
        return HttpResponse(json.dumps(result), content_type='application/json')
    username = request.POST.get('username')
    password = request.POST.get('password')
    password2 = request.POST.get('password2')
    display = request.POST.get('display')
    email = request.POST.get('email')
    result = {'status': 0, 'msg': 'ok', 'data': None}

    if not (username and password):
        result['status'] = 1
        result['msg'] = '用户名和密码不能为空'
    elif len(Users.objects.filter(username=username)) > 0:
        result['status'] = 1
        result['msg'] = '用户名已存在'
    elif password != password2:
        result['status'] = 1
        result['msg'] = '两次输入密码不一致'
    else:
        # 验证密码
        try:
            validate_password(password)
        except ValidationError as msg:
            result['status'] = 1
            result['msg'] = str(msg)
        new_user = Users.objects.create_user(username=username,
                                             password=password,
                                             display=display,
                                             email=email,
                                             is_active=1)
        init_user(new_user)
    return HttpResponse(json.dumps(result), content_type='application/json')


# 退出登录
def sign_out(request):
    logout(request)
    return HttpResponseRedirect(reverse('sql:login'))
