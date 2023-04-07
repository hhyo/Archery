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

from common.config import SysConfig
from common.utils.const import WorkflowDict
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.notify import notify_for_audit, notify_for_execute
from sql.utils.tasks import add_sql_schedule, del_schedule
from sql.utils.sql_review import (
    can_timingtask,
    can_cancel,
    can_execute,
    on_correct_time_period,
)
from sql.utils.workflow_audit import Audit
from .models import SqlWorkflow
from django_q.tasks import async_task

from sql.engines import get_engine

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

    user = request.user
    if Audit.can_review(user, workflow_id, 2) is False:
        context = {"errMsg": "你无权操作当前工单！"}
        return render(request, "error.html", context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 调用工作流接口审核
            audit_id = Audit.detail_by_workflow_id(
                workflow_id=workflow_id,
                workflow_type=WorkflowDict.workflow_type["sqlreview"],
            ).audit_id
            audit_result = Audit.audit(
                audit_id,
                WorkflowDict.workflow_status["audit_success"],
                user.username,
                audit_remark,
            )

            # 按照审核结果更新业务表审核状态
            if (
                audit_result["data"]["workflow_status"]
                == WorkflowDict.workflow_status["audit_success"]
            ):
                # 将流程状态修改为审核通过
                SqlWorkflow(id=workflow_id, status="workflow_review_pass").save(
                    update_fields=["status"]
                )
    except Exception as msg:
        logger.error(f"审核工单报错，错误信息：{traceback.format_exc()}")
        context = {"errMsg": msg}
        return render(request, "error.html", context)
    else:
        # 开启了Pass阶段通知参数才发送消息通知
        sys_config = SysConfig()
        is_notified = (
            "Pass" in sys_config.get("notify_phase_control").split(",")
            if sys_config.get("notify_phase_control")
            else True
        )
        if is_notified:
            async_task(
                notify_for_audit,
                audit_id=audit_id,
                audit_remark=audit_remark,
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
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    audit_remark = request.POST.get("cancel_remark")
    if audit_remark is None:
        context = {"errMsg": "终止原因不能为空"}
        return render(request, "error.html", context)

    user = request.user
    if can_cancel(request.user, workflow_id) is False:
        context = {"errMsg": "你无权操作当前工单！"}
        return render(request, "error.html", context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 调用工作流接口取消或者驳回
            audit_id = Audit.detail_by_workflow_id(
                workflow_id=workflow_id,
                workflow_type=WorkflowDict.workflow_type["sqlreview"],
            ).audit_id
            # 仅待审核的需要调用工作流，审核通过的不需要
            if workflow_detail.status != "workflow_manreviewing":
                # 增加工单日志
                if user.username == workflow_detail.engineer:
                    Audit.add_log(
                        audit_id=audit_id,
                        operation_type=3,
                        operation_type_desc="取消执行",
                        operation_info="取消原因：{}".format(audit_remark),
                        operator=request.user.username,
                        operator_display=request.user.display,
                    )
                else:
                    Audit.add_log(
                        audit_id=audit_id,
                        operation_type=2,
                        operation_type_desc="审批不通过",
                        operation_info="审批备注：{}".format(audit_remark),
                        operator=request.user.username,
                        operator_display=request.user.display,
                    )
            else:
                if user.username == workflow_detail.engineer:
                    Audit.audit(
                        audit_id,
                        WorkflowDict.workflow_status["audit_abort"],
                        user.username,
                        audit_remark,
                    )
                # 非提交人需要校验审核权限
                elif user.has_perm("sql.sql_review"):
                    Audit.audit(
                        audit_id,
                        WorkflowDict.workflow_status["audit_reject"],
                        user.username,
                        audit_remark,
                    )
                else:
                    raise PermissionDenied

            # 删除定时执行task
            if workflow_detail.status == "workflow_timingtask":
                schedule_name = f"sqlreview-timing-{workflow_id}"
                del_schedule(schedule_name)
            # 将流程状态修改为人工终止流程
            workflow_detail.status = "workflow_abort"
            workflow_detail.save()
    except Exception as msg:
        logger.error(f"取消工单报错，错误信息：{traceback.format_exc()}")
        context = {"errMsg": msg}
        return render(request, "error.html", context)
    else:
        # 发送取消、驳回通知，开启了Cancel阶段通知参数才发送消息通知
        sys_config = SysConfig()
        is_notified = (
            "Cancel" in sys_config.get("notify_phase_control").split(",")
            if sys_config.get("notify_phase_control")
            else True
        )
        if is_notified:
            audit_detail = Audit.detail_by_workflow_id(
                workflow_id=workflow_id,
                workflow_type=WorkflowDict.workflow_type["sqlreview"],
            )
            if audit_detail.current_status in (
                WorkflowDict.workflow_status["audit_abort"],
                WorkflowDict.workflow_status["audit_reject"],
            ):
                async_task(
                    notify_for_audit,
                    audit_id=audit_detail.audit_id,
                    audit_remark=audit_remark,
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
