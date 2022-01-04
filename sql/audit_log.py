# -*- coding: UTF-8 -*-
import logging
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import AuditEntry, Users
from django.utils import timezone
from common.utils.permission import superuser_required
from django.http import HttpResponse
import simplejson as json
from common.utils.extend_json_encoder import ExtendJSONEncoder
from django.db.models import Q

log = logging.getLogger('default')


@superuser_required
def audit_log(request):
    """获取登录审计日志列表"""
    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit
    search = request.POST.get('search', '')

    # 过滤搜索条件
    audit_log_obj = AuditEntry.objects.filter(Q(user_name__icontains=search) | Q(action__icontains=search)| Q(ip__icontains=search))
    audit_log_count = audit_log_obj.count()
    audit_log_list = audit_log_obj.order_by('-action_time')[offset:limit].values("user_id", "user_name", "ip", "action", "action_time")

    # QuerySet 序列化
    rows = [row for row in audit_log_list]

    result = {"total": audit_log_count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@receiver(user_logged_in)
def user_logged_in_callback(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    now = timezone.now()
    AuditEntry.objects.create(action=u'登入', ip=ip, user_id=user.id, user_name=user.username, action_time=now)


@receiver(user_logged_out)
def user_logged_out_callback(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    now = timezone.now()
    AuditEntry.objects.create(action=u'登出', ip=ip, user_id=user.id, user_name=user.username, action_time=now)


@receiver(user_login_failed)
def user_login_failed_callback(sender, credentials, **kwargs):
    now = timezone.now()
    user_name = credentials.get('username', None)
    user_obj = Users.objects.filter(username=user_name)[0:1]
    user_count = user_obj.count()
    user_id = 0
    if user_count > 0:
        user_id = user_obj[0].id
    AuditEntry.objects.create(action=u'登入失败', user_id=user_id, user_name=user_name
                              , action_time=now)

