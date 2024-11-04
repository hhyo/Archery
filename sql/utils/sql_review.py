import datetime
import json
import re
from django.db import transaction

from sql.engines.models import ReviewResult
from sql.models import SqlWorkflow
from common.config import SysConfig
from sql.utils.resource_group import user_groups
from sql.utils.sql_utils import remove_comments


def can_execute(user, workflow_id):
    """
    判断用户当前是否可执行，两种情况下用户有执行权限
    1.登录用户有资源组粒度执行权限，并且为组内用户
    2.当前登录用户为提交人，并且有执行权限
    :param user:
    :param workflow_id:
    :return:
    """
    result = False
    # 保证工单当前是可执行状态
    with transaction.atomic():
        workflow_detail = SqlWorkflow.objects.select_for_update().get(id=workflow_id)
        # 只有审核通过和定时执行的数据才可以立即执行
        if workflow_detail.status not in [
            "workflow_review_pass",
            "workflow_timingtask",
        ]:
            return False
    # 当前登录用户有资源组粒度执行权限，并且为组内用户
    group_ids = [group.group_id for group in user_groups(user)]
    if workflow_detail.group_id in group_ids and user.has_perm(
        "sql.sql_execute_for_resource_group"
    ):
        result = True
    # 当前登录用户为提交人，并且有执行权限
    if workflow_detail.engineer == user.username and user.has_perm("sql.sql_execute"):
        result = True
    return result


def on_query_low_peak_time_ddl(workflow_id, run_date=None):
    """
    判断是否是ddl，ddl必须在业务低峰期执行，包括人工执行和定时执行
    :param workflow_id:
    :param run_date:
    :return:
    """
    config = SysConfig()
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = True
    ctime = run_date or datetime.datetime.now()
    run_time = f"{ctime.hour:02}:{ctime.minute:02}"
    syntax_type = workflow_detail.syntax_type
    periods = config.get("query_low_peak", "")
    peak_action = config.get("query_low_peak_query", "")

    def is_without_peak_periods(run_time, periods):
        for period in periods.split(","):
            start, end = period.split("-")
            if start <= run_time <= end:
                return True  # 如果 run_time 在当前时间段内，直接返回 True
        return False  # 只有当 run_time 不在任何时间段内时，才返回 False

    if "DML" in peak_action and syntax_type == 2:
        return is_without_peak_periods(run_time, periods)
    if "DDL" in peak_action and syntax_type == 1:
        return is_without_peak_periods(run_time, periods)
    return result


def on_correct_time_period(workflow_id, run_date=None):
    """
    判断是否在可执行时间段内，包括人工执行和定时执行
    :param workflow_id:
    :param run_date:
    :return:
    """
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = True
    ctime = run_date or datetime.datetime.now()
    stime = workflow_detail.run_date_start
    etime = workflow_detail.run_date_end
    if (stime and stime > ctime) or (etime and etime < ctime):
        result = False
    return result


def can_timingtask(user, workflow_id):
    """
    判断用户当前是否可定时执行，两种情况下用户有定时执行权限
    1.登录用户有资源组粒度执行权限，并且为组内用户
    2.当前登录用户为提交人，并且有执行权限
    :param user:
    :param workflow_id:
    :return:
    """
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = False
    # 只有审核通过和定时执行的数据才可以执行
    if workflow_detail.status in ["workflow_review_pass", "workflow_timingtask"]:
        # 当前登录用户有资源组粒度执行权限，并且为组内用户
        group_ids = [group.group_id for group in user_groups(user)]
        if workflow_detail.group_id in group_ids and user.has_perm(
            "sql.sql_execute_for_resource_group"
        ):
            result = True
        # 当前登录用户为提交人，并且有执行权限
        if workflow_detail.engineer == user.username and user.has_perm(
            "sql.sql_execute"
        ):
            result = True
    return result


def can_cancel(user, workflow_id):
    """
    判断用户当前是否是可终止，
    审核中、审核通过的的工单，审核人和提交人可终止
    :param user:
    :param workflow_id:
    :return:
    """
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = False
    # 审核中的工单，审核人和提交人可终止
    if workflow_detail.status == "workflow_manreviewing":
        from sql.utils.workflow_audit import Audit

        return any(
            [
                Audit.can_review(user, workflow_id, 2),
                user.username == workflow_detail.engineer,
            ]
        )
    elif workflow_detail.status in ["workflow_review_pass", "workflow_timingtask"]:
        return any(
            [can_execute(user, workflow_id), user.username == workflow_detail.engineer]
        )
    return result


def can_view(user, workflow_id):
    """
    判断用户当前是否可以查看工单信息，和列表过滤逻辑保存一致
    :param user:
    :param workflow_id:
    :return:
    """
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = False
    # 管理员，可查看所有工单
    if user.is_superuser:
        result = True
    # 非管理员，拥有审核权限、资源组粒度执行权限的，可以查看组内所有工单
    elif user.has_perm("sql.sql_review") or user.has_perm(
        "sql.sql_execute_for_resource_group"
    ):
        # 先获取用户所在资源组列表
        group_list = user_groups(user)
        group_ids = [group.group_id for group in group_list]
        if workflow_detail.group_id in group_ids:
            result = True
    # 其他人只能查看自己提交的工单
    else:
        if workflow_detail.engineer == user.username:
            result = True
    return result


def can_rollback(user, workflow_id):
    """
    判断用户当前是否可以查看回滚信息，和工单详情保持一致
    执行结束并且开启备份的工单可以查看回滚信息
    :param user:
    :param workflow_id:
    :return:
    """
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    result = False
    # 执行结束并且开启备份的工单可以查看回滚信息
    if workflow_detail.is_backup and workflow_detail.status in (
        "workflow_finish",
        "workflow_exception",
    ):
        return can_view(user, workflow_id)
    return result
