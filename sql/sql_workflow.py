# -*- coding: UTF-8 -*-
import datetime
import logging
import traceback

import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django_q.tasks import async_task

from common.config import SysConfig
from common.utils.const import WorkflowStatus, WorkflowType, WorkflowAction
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines import get_engine
from sql.notify import notify_for_audit, EventType, notify_for_execute
from sql.utils.sql_review import (
    can_timingtask,
    can_cancel,
    can_execute,
    on_correct_time_period,
)
from sql.utils.tasks import add_sql_schedule, del_schedule
from sql.utils.workflow_audit import Audit, get_auditor, AuditException
from .models import SqlWorkflow

logger = logging.getLogger("default")


@permission_required("sql.sql_review", raise_exception=True)
def passed(request):
    """
    审核通过，不执行
    :param request:
    :return:
    """
    workflow_id = int(request.POST.get("workflow_id", 0))
    audit_remark = request.POST.get("audit_remark", "")
    if workflow_id == 0:
        context = {"errMsg": "workflow_id参数为空."}
        return render(request, "error.html", context)
    try:
        sql_workflow = SqlWorkflow.objects.get(id=workflow_id)
    except SqlWorkflow.DoesNotExist:
        return render(request, "error.html", {"errMsg": "工单不存在"})

    sys_config = SysConfig()
    auditor = get_auditor(workflow=sql_workflow, sys_config=sys_config)
    # 使用事务保持数据一致性
    with transaction.atomic():
        try:
            workflow_audit_detail = auditor.operate(
                WorkflowAction.PASS, request.user, audit_remark
            )
        except AuditException as e:
            return render(request, "error.html", {"errMsg": f"审核失败, 错误信息: {str(e)}"})
        if auditor.audit.current_status == WorkflowStatus.PASSED:
            # 审批流全部走完了, 把工单标记为审核通过
            auditor.workflow.status = "workflow_review_pass"
            auditor.workflow.save()

    # 开启了Pass阶段通知参数才发送消息通知
    is_notified = (
        "Pass" in sys_config.get("notify_phase_control").split(",")
        if sys_config.get("notify_phase_control")
        else True
    )
    if is_notified:
        async_task(
            notify_for_audit,
            workflow_audit=auditor.audit,
            workflow_audit_detail=workflow_audit_detail,
            timeout=60,
            task_name=f"sqlreview-pass-{workflow_id}",
        )

    return HttpResponseRedirect(reverse("sql:detail", args=(workflow_id,)))


def cancel(request):
    """
    终止流程
    :param request:
    :return:
    """
    workflow_id = int(request.POST.get("workflow_id", 0))
    if workflow_id == 0:
        context = {"errMsg": "workflow_id参数为空."}
        return render(request, "error.html", context)
    sql_workflow = SqlWorkflow.objects.get(id=workflow_id)
    audit_remark = request.POST.get("cancel_remark")
    if audit_remark is None:
        context = {"errMsg": "终止原因不能为空"}
        return render(request, "error.html", context)

    user = request.user
    if can_cancel(request.user, workflow_id) is False:
        context = {"errMsg": "你无权操作当前工单！"}
        return render(request, "error.html", context)

    # 使用事务保持数据一致性
    if user.username == sql_workflow.engineer:
        action = WorkflowAction.ABORT
    elif user.has_perm("sql.sql_review"):
        action = WorkflowAction.REJECT
    else:
        raise PermissionDenied
    with transaction.atomic():
        auditor = get_auditor(workflow=sql_workflow)
        try:
            workflow_audit_detail = auditor.operate(action, request.user, audit_remark)
        except AuditException as e:
            logger.error(f"取消工单报错，错误信息：{traceback.format_exc()}")
            return render(request, "error.html", {"errMsg": f"{str(e)}"})
        # 将流程状态修改为人工终止流程
        sql_workflow.status = "workflow_abort"
        sql_workflow.save()
    # 删除定时执行task
    if sql_workflow.status == "workflow_timingtask":
        del_schedule(f"sqlreview-timing-{workflow_id}")
    # 发送取消、驳回通知，开启了Cancel阶段通知参数才发送消息通知
    sys_config = SysConfig()
    is_notified = (
        "Cancel" in sys_config.get("notify_phase_control").split(",")
        if sys_config.get("notify_phase_control")
        else True
    )
    if is_notified:
        async_task(
            notify_for_audit,
            workflow_audit=auditor.audit,
            workflow_audit_detail=workflow_audit_detail,
            timeout=60,
            task_name=f"sqlreview-cancel-{workflow_id}",
        )
    return HttpResponseRedirect(reverse("sql:detail", args=(workflow_id,)))


def osc_control(request):
    """用于mysql控制osc执行"""
    workflow_id = request.POST.get("workflow_id")
    sqlsha1 = request.POST.get("sqlsha1")
    command = request.POST.get("command")
    workflow = SqlWorkflow.objects.get(id=workflow_id)
    execute_engine = get_engine(workflow.instance)
    try:
        execute_result = execute_engine.osc_control(command=command, sqlsha1=sqlsha1)
        rows = execute_result.to_dict()
        error = execute_result.error
    except Exception as e:
        rows = []
        error = str(e)
    result = {"total": len(rows), "rows": rows, "msg": error}
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )
