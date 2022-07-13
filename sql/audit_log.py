# -*- coding: UTF-8 -*-
import logging
import datetime
import simplejson as json

from django.dispatch import receiver
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Q
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)

from .models import AuditEntry, Users
from common.utils.permission import superuser_required
from common.utils.extend_json_encoder import ExtendJSONEncoder

log = logging.getLogger("default")


@login_required
def audit_input(request):
    """用户提交的操作信息"""
    result = {}
    action = request.POST.get("action")
    extra_info = request.POST.get("extra_info", "")

    result["user_id"] = request.user.id
    result["user_name"] = request.user.username
    result["user_display"] = request.user.display
    result["action"] = action
    result["extra_info"] = extra_info

    audit = AuditEntry(**result)
    audit.save()

    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


@permission_required("sql.audit_user", raise_exception=True)
def audit_log(request):
    """获取审计日志列表"""
    limit = int(request.POST.get("limit", 0))
    offset = int(request.POST.get("offset", 0))
    limit = offset + limit
    limit = limit if limit else None
    search = request.POST.get("search", "")
    action = request.POST.get("action", "")
    start_date = request.POST.get("start_date")
    end_date = request.POST.get("end_date")

    filter_dict = dict()
    if start_date and end_date:
        end_date = datetime.datetime.strptime(
            end_date, "%Y-%m-%d"
        ) + datetime.timedelta(days=1)
        filter_dict["action_time__range"] = (start_date, end_date)
    if action:
        filter_dict["action"] = action

    audit_log_obj = AuditEntry.objects.filter(**filter_dict)
    if search:
        audit_log_obj = audit_log_obj.filter(
            Q(user_name__icontains=search)
            | Q(action__icontains=search)
            | Q(extra_info__icontains=search)
        )

    audit_log_count = audit_log_obj.count()
    audit_log_list = audit_log_obj.order_by("-action_time")[offset:limit].values(
        "user_id", "user_name", "user_display", "action", "extra_info", "action_time"
    )

    # QuerySet 序列化
    rows = [row for row in audit_log_list]

    result = {"total": audit_log_count, "rows": rows}
    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


@receiver(user_logged_in)
def user_logged_in_callback(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    now = timezone.now()
    AuditEntry.objects.create(
        action="登入",
        extra_info=ip,
        user_id=user.id,
        user_name=user.username,
        user_display=user.display,
        action_time=now,
    )


@receiver(user_logged_out)
def user_logged_out_callback(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    now = timezone.now()
    AuditEntry.objects.create(
        action="登出",
        extra_info=ip,
        user_id=user.id,
        user_name=user.username,
        user_display=user.display,
        action_time=now,
    )


@receiver(user_login_failed)
def user_login_failed_callback(sender, credentials, **kwargs):
    now = timezone.now()
    user_name = credentials.get("username", None)
    user_obj = Users.objects.filter(username=user_name)[0:1]
    user_count = user_obj.count()
    user_id = 0
    user_display = ""
    if user_count > 0:
        user_id = user_obj[0].id
        user_display = user_obj[0].display
    AuditEntry.objects.create(
        action="登入失败",
        user_id=user_id,
        user_name=user_name,
        user_display=user_display,
        action_time=now,
    )
