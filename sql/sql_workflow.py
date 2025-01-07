# -*- coding: UTF-8 -*-
import datetime
import logging
import traceback

import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django_q.tasks import async_task

from common.config import SysConfig
from common.utils.const import WorkflowStatus, WorkflowType, WorkflowAction
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines import get_engine
from sql.engines.models import ReviewResult, ReviewSet
from sql.notify import notify_for_audit, EventType, notify_for_execute
from sql.utils.resource_group import user_groups
from sql.utils.sql_review import (
    can_timingtask,
    can_cancel,
    can_execute,
    on_query_low_peak_time_ddl,
    on_correct_time_period,
    can_view,
    can_rollback,
)
from sql.utils.tasks import add_sql_schedule, del_schedule
from sql.utils.workflow_audit import Audit, get_auditor, AuditException
from .models import SqlWorkflow

logger = logging.getLogger("default")


@permission_required("sql.menu_sqlworkflow", raise_exception=True)
def sql_workflow_list(request):
    return _sql_workflow_list(request)


@permission_required("sql.audit_user", raise_exception=True)
def sql_workflow_list_audit(request):
    return _sql_workflow_list(request)


def _sql_workflow_list(request):
    """
    获取审核列表
    :param request:
    :return:
    """
    nav_status = request.POST.get("navStatus")
    instance_id = request.POST.get("instance_id")
    resource_group_id = request.POST.get("group_id")
    start_date = request.POST.get("start_date")
    end_date = request.POST.get("end_date")
    limit = int(request.POST.get("limit", 0))
    offset = int(request.POST.get("offset", 0))
    limit = offset + limit
    limit = limit if limit else None
    search = request.POST.get("search")
    user = request.user

    # 组合筛选项
    filter_dict = dict()
    # 工单状态
    if nav_status:
        filter_dict["status"] = nav_status
    # 实例
    if instance_id:
        filter_dict["instance_id"] = instance_id
    # 资源组
    if resource_group_id:
        filter_dict["group_id"] = resource_group_id
    # 时间
    if start_date and end_date:
        end_date = datetime.datetime.strptime(
            end_date, "%Y-%m-%d"
        ) + datetime.timedelta(days=1)
        filter_dict["create_time__range"] = (start_date, end_date)
    # 管理员，审计员，可查看所有工单
    if user.is_superuser or user.has_perm("sql.audit_user"):
        pass
    # 非管理员，拥有审核权限、资源组粒度执行权限的，可以查看组内所有工单
    elif user.has_perm("sql.sql_review") or user.has_perm(
        "sql.sql_execute_for_resource_group"
    ):
        # 先获取用户所在资源组列表
        group_list = user_groups(user)
        group_ids = [group.group_id for group in group_list]
        filter_dict["group_id__in"] = group_ids
    # 其他人只能查看自己提交的工单
    else:
        filter_dict["engineer"] = user.username

    # 过滤组合筛选项
    workflow = SqlWorkflow.objects.filter(**filter_dict)

    # 过滤搜索项，模糊检索项包括提交人名称、工单名
    if search:
        workflow = workflow.filter(
            Q(engineer_display__icontains=search) | Q(workflow_name__icontains=search)
        )

    count = workflow.count()
    workflow_list = workflow.order_by("-create_time")[offset:limit].values(
        "id",
        "workflow_name",
        "engineer_display",
        "status",
        "is_backup",
        "create_time",
        "instance__instance_name",
        "db_name",
        "group_name",
        "syntax_type",
    )

    # QuerySet 序列化
    rows = [row for row in workflow_list]
    result = {"total": count, "rows": rows}
    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


def detail_content(request):
    """获取工单内容"""
    workflow_id = request.GET.get("workflow_id")
    workflow_detail = get_object_or_404(SqlWorkflow, pk=workflow_id)
    if not can_view(request.user, workflow_id):
        raise PermissionDenied
    if workflow_detail.status in ["workflow_finish", "workflow_exception"]:
        rows = workflow_detail.sqlworkflowcontent.execute_result
    else:
        rows = workflow_detail.sqlworkflowcontent.review_content

    review_result = ReviewSet()
    if rows:
        try:
            # 检验rows能不能正常解析
            loaded_rows = json.loads(rows)
            #  兼容旧数据'[[]]'格式，转换为新格式[{}]
            if isinstance(loaded_rows[-1], list):
                for r in loaded_rows:
                    review_result.rows += [ReviewResult(inception_result=r)]
                rows = review_result.json()
        except IndexError:
            review_result.rows += [
                ReviewResult(
                    id=1,
                    sql=workflow_detail.sqlworkflowcontent.sql_content,
                    errormessage="Json decode failed."
                    "执行结果Json解析失败, 请联系管理员",
                )
            ]
            rows = review_result.json()
        except json.decoder.JSONDecodeError:
            review_result.rows += [
                ReviewResult(
                    id=1,
                    sql=workflow_detail.sqlworkflowcontent.sql_content,
                    # 迫于无法单元测试这里加上英文报错信息
                    errormessage="Json decode failed."
                    "执行结果Json解析失败, 请联系管理员",
                )
            ]
            rows = review_result.json()
    else:
        rows = workflow_detail.sqlworkflowcontent.review_content

    result = {"rows": json.loads(rows)}
    return HttpResponse(json.dumps(result), content_type="application/json")


def backup_sql(request):
    """获取回滚语句"""
    workflow_id = request.GET.get("workflow_id")
    if not can_rollback(request.user, workflow_id):
        raise PermissionDenied
    workflow = get_object_or_404(SqlWorkflow, pk=workflow_id)

    try:
        query_engine = get_engine(instance=workflow.instance)
        list_backup_sql = query_engine.get_rollback(workflow=workflow)
    except Exception as msg:
        logger.error(traceback.format_exc())
        return JsonResponse({"status": 1, "msg": f"{msg}", "rows": []})

    result = {"status": 0, "msg": "", "rows": list_backup_sql}
    return HttpResponse(json.dumps(result), content_type="application/json")


@permission_required("sql.sql_review", raise_exception=True)
def alter_run_date(request):
    """
    审核人修改可执行时间
    :param request:
    :return:
    """
    workflow_id = int(request.POST.get("workflow_id", 0))
    run_date_start = request.POST.get("run_date_start")
    run_date_end = request.POST.get("run_date_end")
    if workflow_id == 0:
        context = {"errMsg": "workflow_id参数为空."}
        return render(request, "error.html", context)

    user = request.user
    if Audit.can_review(user, workflow_id, 2) is False:
        context = {"errMsg": "你无权操作当前工单！"}
        return render(request, "error.html", context)

    try:
        # 存进数据库里
        SqlWorkflow(
            id=workflow_id,
            run_date_start=run_date_start or None,
            run_date_end=run_date_end or None,
        ).save(update_fields=["run_date_start", "run_date_end"])
    except Exception as msg:
        context = {"errMsg": msg}
        return render(request, "error.html", context)

    return HttpResponseRedirect(reverse("sql:detail", args=(workflow_id,)))


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
            return render(
                request, "error.html", {"errMsg": f"审核失败, 错误信息: {str(e)}"}
            )
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


def execute(request):
    """
    执行SQL
    :param request:
    :return:
    """
    # 校验多个权限
    if not (
        request.user.has_perm("sql.sql_execute")
        or request.user.has_perm("sql.sql_execute_for_resource_group")
    ):
        raise PermissionDenied
    workflow_id = int(request.POST.get("workflow_id", 0))
    if workflow_id == 0:
        context = {"errMsg": "workflow_id参数为空."}
        return render(request, "error.html", context)

    if can_execute(request.user, workflow_id) is False:
        context = {"errMsg": "你无权操作当前工单！"}
        return render(request, "error.html", context)

    if on_correct_time_period(workflow_id) is False:
        context = {
            "errMsg": "不在可执行时间范围内，如果需要修改执行时间请重新提交工单!"
        }
        return render(request, "error.html", context)
    sys_config = SysConfig()
    if (
        not request.user.is_superuser
        and on_query_low_peak_time_ddl(workflow_id) is False
    ):
        periods = sys_config.get("query_low_peak", "")
        peak_action = sys_config.get("query_low_peak_query", "")
        context = {
            "errMsg": "管理员设置了业务低峰期时间范围:%s,你只能在业务低峰时间范围执行%s工单操作!"
            % (periods, peak_action)
        }
        return render(request, "error.html", context)
    # 获取审核信息
    audit_id = Audit.detail_by_workflow_id(
        workflow_id=workflow_id, workflow_type=WorkflowType.SQL_REVIEW
    ).audit_id
    # 根据执行模式进行对应修改
    mode = request.POST.get("mode")
    # 交由系统执行
    if mode == "auto":
        # 修改工单状态为排队中
        SqlWorkflow(id=workflow_id, status="workflow_queuing").save(
            update_fields=["status"]
        )
        # 删除定时执行任务
        schedule_name = f"sqlreview-timing-{workflow_id}"
        del_schedule(schedule_name)
        # 加入执行队列
        async_task(
            "sql.utils.execute_sql.execute",
            workflow_id,
            request.user,
            hook="sql.utils.execute_sql.execute_callback",
            timeout=-1,
            task_name=f"sqlreview-execute-{workflow_id}",
        )
        # 增加工单日志
        Audit.add_log(
            audit_id=audit_id,
            operation_type=5,
            operation_type_desc="执行工单",
            operation_info="工单执行排队中",
            operator=request.user.username,
            operator_display=request.user.display,
        )

    # 线下手工执行
    elif mode == "manual":
        # 将流程状态修改为执行结束
        SqlWorkflow(
            id=workflow_id,
            status="workflow_finish",
            finish_time=datetime.datetime.now(),
        ).save(update_fields=["status", "finish_time"])
        # 增加工单日志
        Audit.add_log(
            audit_id=audit_id,
            operation_type=6,
            operation_type_desc="手工工单",
            operation_info="确认手工执行结束",
            operator=request.user.username,
            operator_display=request.user.display,
        )
        # 开启了Execute阶段通知参数才发送消息通知
        sys_config = SysConfig()
        is_notified = (
            "Execute" in sys_config.get("notify_phase_control").split(",")
            if sys_config.get("notify_phase_control")
            else True
        )
        if is_notified:
            notify_for_execute(workflow=SqlWorkflow.objects.get(id=workflow_id))
    return HttpResponseRedirect(reverse("sql:detail", args=(workflow_id,)))


def timing_task(request):
    """
    定时执行SQL
    :param request:
    :return:
    """
    # 校验多个权限
    if not (
        request.user.has_perm("sql.sql_execute")
        or request.user.has_perm("sql.sql_execute_for_resource_group")
    ):
        raise PermissionDenied
    workflow_id = request.POST.get("workflow_id")
    run_date = request.POST.get("run_date")
    if run_date is None or workflow_id is None:
        context = {"errMsg": "时间不能为空"}
        return render(request, "error.html", context)
    elif run_date < datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"):
        context = {"errMsg": "时间不能小于当前时间"}
        return render(request, "error.html", context)
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)

    if can_timingtask(request.user, workflow_id) is False:
        context = {"errMsg": "你无权操作当前工单！"}
        return render(request, "error.html", context)

    run_date = datetime.datetime.strptime(run_date, "%Y-%m-%d %H:%M")
    schedule_name = f"sqlreview-timing-{workflow_id}"

    if on_correct_time_period(workflow_id, run_date) is False:
        context = {
            "errMsg": "不在可执行时间范围内，如果需要修改执    行时间请重新提交工单!"
        }
        return render(request, "error.html", context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 将流程状态修改为定时执行
            workflow_detail.status = "workflow_timingtask"
            workflow_detail.save()
            # 调用添加定时任务
            add_sql_schedule(schedule_name, run_date, workflow_id)
            # 增加工单日志
            audit_id = Audit.detail_by_workflow_id(
                workflow_id=workflow_id,
                workflow_type=WorkflowType.SQL_REVIEW,
            ).audit_id
            Audit.add_log(
                audit_id=audit_id,
                operation_type=4,
                operation_type_desc="定时执行",
                operation_info="定时执行时间：{}".format(run_date),
                operator=request.user.username,
                operator_display=request.user.display,
            )
    except Exception as msg:
        logger.error(f"定时执行工单报错，错误信息：{traceback.format_exc()}")
        context = {"errMsg": msg}
        return render(request, "error.html", context)
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


def get_workflow_status(request):
    """
    获取某个工单的当前状态
    """
    workflow_id = request.POST["workflow_id"]
    if workflow_id == "" or workflow_id is None:
        context = {"status": -1, "msg": "workflow_id参数为空.", "data": ""}
        return HttpResponse(json.dumps(context), content_type="application/json")

    workflow_id = int(workflow_id)
    workflow_detail = get_object_or_404(SqlWorkflow, pk=workflow_id)
    result = {"status": workflow_detail.status, "msg": "", "data": ""}
    return JsonResponse(result)


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
