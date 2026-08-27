import datetime
import logging

import simplejson as json
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django_q.tasks import async_task
from rest_framework import views
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from common.config import SysConfig
from common.utils.const import WorkflowAction, WorkflowStatus, WorkflowType
from sql.engines import get_engine
from sql.engines.models import ReviewResult, ReviewSet
from sql.models import SqlWorkflow
from sql.notify import notify_for_audit, notify_for_execute
from sql.utils.resource_group import user_groups
from sql.utils.sql_review import (
    can_cancel,
    can_execute,
    can_rollback,
    can_timingtask,
    can_view,
    on_correct_time_period,
)
from sql.utils.tasks import add_sql_schedule, del_schedule
from sql.utils.workflow_audit import Audit, AuditException, get_auditor
from .permissions import IsWorkflowPageUser
from .serializers import (
    WorkflowExecutionSerializer,
    WorkflowExecutionWindowSerializer,
    WorkflowListRequestSerializer,
    WorkflowOscSerializer,
    WorkflowRemarkSerializer,
    WorkflowScheduleSerializer,
    WorkflowTerminationSerializer,
)

logger = logging.getLogger("default")


def get_workflow(workflow_id):
    try:
        return SqlWorkflow.objects.get(id=workflow_id)
    except SqlWorkflow.DoesNotExist as exc:
        raise NotFound("工单不存在") from exc


def mutation_response(workflow_id, message):
    return {
        "status": 0,
        "msg": message,
        "data": {
            "workflow_id": workflow_id,
            "redirect_url": reverse("sql:detail", args=(workflow_id,)),
        },
    }


def should_notify(config, phase):
    phases = config.get("notify_phase_control")
    return phase in phases.split(",") if phases else True


def ensure_viewable(user, workflow_id):
    if not can_view(user, workflow_id):
        raise PermissionDenied("你无权查看当前工单！")


class WorkflowOperationAPIView(views.APIView):
    """Base view for session-authenticated workflow operation endpoints."""

    permission_classes = [IsWorkflowPageUser]

    def validated_data(self, serializer_class, request):
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


class WorkflowListView(WorkflowOperationAPIView):
    def post(self, request):
        data = self.validated_data(WorkflowListRequestSerializer, request)
        filters = {}
        syntax_type = data.get("syntax_type", [])
        if syntax_type:
            filters["syntax_type__in"] = syntax_type
        for input_name, field in (
            ("navStatus", "status"),
            ("instance_id", "instance_id"),
            ("group_id", "group_id"),
        ):
            if data.get(input_name):
                filters[field] = data[input_name]
        if data.get("start_date") and data.get("end_date"):
            filters["create_time__range"] = (
                data["start_date"],
                data["end_date"] + datetime.timedelta(days=1),
            )
        user = request.user
        if not (user.is_superuser or user.has_perm("sql.audit_user")):
            if user.has_perm("sql.sql_review") or user.has_perm(
                "sql.sql_execute_for_resource_group"
            ):
                filters["group_id__in"] = [
                    group.group_id for group in user_groups(user)
                ]
            else:
                filters["engineer"] = user.username
        workflows = SqlWorkflow.objects.filter(**filters)
        if data.get("search"):
            workflows = workflows.filter(
                Q(engineer_display__icontains=data["search"])
                | Q(workflow_name__icontains=data["search"])
            )
        offset, limit = data.get("offset", 0), data.get("limit", 0)
        rows = workflows.order_by("-create_time")[
            offset : offset + limit if limit else None
        ].values(
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
            "export_format",
        )
        return Response({"total": workflows.count(), "rows": list(rows)})


class WorkflowAuditListView(WorkflowOperationAPIView):
    def post(self, request):
        if not request.user.has_perm("sql.audit_user"):
            raise PermissionDenied("你无权查看审核工单列表！")
        data = self.validated_data(WorkflowListRequestSerializer, request)
        filters = {}
        syntax_type = data.get("syntax_type", [])
        if syntax_type:
            filters["syntax_type__in"] = syntax_type
        for input_name, field in (
            ("navStatus", "status"),
            ("instance_id", "instance_id"),
            ("group_id", "group_id"),
        ):
            if data.get(input_name):
                filters[field] = data[input_name]
        if data.get("start_date") and data.get("end_date"):
            filters["create_time__range"] = (
                data["start_date"],
                data["end_date"] + datetime.timedelta(days=1),
            )
        workflows = SqlWorkflow.objects.filter(**filters)
        if data.get("search"):
            workflows = workflows.filter(
                Q(engineer_display__icontains=data["search"])
                | Q(workflow_name__icontains=data["search"])
            )
        offset, limit = data.get("offset", 0), data.get("limit", 0)
        rows = workflows.order_by("-create_time")[
            offset : offset + limit if limit else None
        ].values(
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
            "export_format",
        )
        return Response({"total": workflows.count(), "rows": list(rows)})


class WorkflowContentView(WorkflowOperationAPIView):
    def get(self, request, workflow_id):
        workflow = get_workflow(workflow_id)
        ensure_viewable(request.user, workflow_id)
        content = workflow.sqlworkflowcontent
        rows = (
            content.execute_result
            if workflow.status in ["workflow_finish", "workflow_exception"]
            else content.review_content
        )
        try:
            loaded = json.loads(rows)
            if loaded and isinstance(loaded[-1], list):
                result = ReviewSet()
                for row in loaded:
                    result.rows.append(ReviewResult(inception_result=row))
                rows = result.json()
        except (IndexError, json.decoder.JSONDecodeError):
            rows = ReviewSet(
                rows=[
                    ReviewResult(
                        id=1,
                        sql=content.sql_content,
                        errormessage="Json decode failed.执行结果Json解析失败, 请联系管理员",
                    )
                ]
            ).json()
        return Response({"rows": json.loads(rows)})


class WorkflowRollbackView(WorkflowOperationAPIView):
    def get(self, request, workflow_id):
        if not can_rollback(request.user, workflow_id):
            raise PermissionDenied("你无权查看当前工单的回滚语句！")
        workflow = get_workflow(workflow_id)
        try:
            rows = get_engine(instance=workflow.instance).get_rollback(
                workflow=workflow
            )
        except Exception:
            logger.exception("获取工单回滚语句失败，workflow_id=%s", workflow_id)
            return Response({"status": 1, "msg": "获取回滚语句失败", "rows": []})
        return Response({"status": 0, "msg": "", "rows": rows})


class WorkflowExecutionWindowView(WorkflowOperationAPIView):
    def patch(self, request, workflow_id):
        data = self.validated_data(WorkflowExecutionWindowSerializer, request)
        if not request.user.has_perm("sql.sql_review") or not Audit.can_review(
            request.user, workflow_id, WorkflowType.SQL_REVIEW
        ):
            raise PermissionDenied("你无权操作当前工单！")
        workflow = get_workflow(workflow_id)
        workflow.run_date_start, workflow.run_date_end = data.get(
            "run_date_start"
        ), data.get("run_date_end")
        workflow.save(update_fields=["run_date_start", "run_date_end"])
        return Response(mutation_response(workflow_id, "可执行时间已更新"))

    post = patch


class WorkflowApprovalView(WorkflowOperationAPIView):
    def post(self, request, workflow_id):
        data = self.validated_data(WorkflowRemarkSerializer, request)
        if not request.user.has_perm("sql.sql_review"):
            raise PermissionDenied("你无权操作当前工单！")
        workflow, config = get_workflow(workflow_id), SysConfig()
        with transaction.atomic():
            auditor = get_auditor(workflow=workflow, sys_config=config)
            try:
                detail = auditor.operate(
                    WorkflowAction.PASS, request.user, data["audit_remark"]
                )
            except AuditException:
                logger.exception("审核工单失败，workflow_id=%s", workflow_id)
                raise ValidationError({"detail": "审核工单失败"})
            if auditor.audit.current_status == WorkflowStatus.PASSED:
                auditor.workflow.status = "workflow_review_pass"
                auditor.workflow.save(update_fields=["status"])
            if should_notify(config, "Pass"):
                transaction.on_commit(
                    lambda: async_task(
                        notify_for_audit,
                        workflow_audit=auditor.audit,
                        workflow_audit_detail=detail,
                        timeout=60,
                        task_name=f"sqlreview-pass-{workflow_id}",
                    )
                )
        return Response(mutation_response(workflow_id, "审核通过"))


class WorkflowExecutionView(WorkflowOperationAPIView):
    def post(self, request, workflow_id):
        data = self.validated_data(WorkflowExecutionSerializer, request)
        if not (
            request.user.has_perm("sql.sql_execute")
            or request.user.has_perm("sql.sql_execute_for_resource_group")
        ) or not can_execute(request.user, workflow_id):
            raise PermissionDenied("你无权执行当前工单！")
        if not on_correct_time_period(workflow_id):
            raise ValidationError(
                {"detail": "不在可执行时间范围内，如果需要修改执行时间请重新提交工单!"}
            )
        workflow = get_workflow(workflow_id)
        audit_id = Audit.detail_by_workflow_id(
            workflow_id, WorkflowType.SQL_REVIEW
        ).audit_id
        with transaction.atomic():
            if data["mode"] == "auto":
                workflow.status = "workflow_queuing"
                workflow.save(update_fields=["status"])
                Audit.add_log(
                    audit_id,
                    5,
                    "执行工单",
                    "工单执行排队中",
                    request.user.username,
                    request.user.display,
                )
                transaction.on_commit(
                    lambda: del_schedule(f"sqlreview-timing-{workflow_id}")
                )
                transaction.on_commit(
                    lambda: async_task(
                        "sql.utils.execute_sql.execute",
                        workflow_id,
                        request.user,
                        hook="sql.utils.execute_sql.execute_callback",
                        timeout=-1,
                        task_name=f"sqlreview-execute-{workflow_id}",
                    )
                )
                message = "工单执行排队中"
            else:
                workflow.status, workflow.finish_time = (
                    "workflow_finish",
                    timezone.now(),
                )
                workflow.save(update_fields=["status", "finish_time"])
                Audit.add_log(
                    audit_id,
                    6,
                    "手工工单",
                    "确认手工执行结束",
                    request.user.username,
                    request.user.display,
                )
                if should_notify(SysConfig(), "Execute"):
                    transaction.on_commit(lambda: notify_for_execute(workflow=workflow))
                message = "已确认手工执行结束"
        return Response(mutation_response(workflow_id, message))


class WorkflowScheduleView(WorkflowOperationAPIView):
    def post(self, request, workflow_id):
        data = self.validated_data(WorkflowScheduleSerializer, request)
        run_date = data["run_date"]
        if timezone.is_naive(run_date) and timezone.is_aware(timezone.now()):
            run_date = timezone.make_aware(run_date)
        if run_date <= timezone.now():
            raise ValidationError({"run_date": "时间不能小于当前时间"})
        if not (
            request.user.has_perm("sql.sql_execute")
            or request.user.has_perm("sql.sql_execute_for_resource_group")
        ) or not can_timingtask(request.user, workflow_id):
            raise PermissionDenied("你无权操作当前工单！")
        if not on_correct_time_period(workflow_id, run_date):
            raise ValidationError(
                {
                    "run_date": "不在可执行时间范围内，如果需要修改执行时间请重新提交工单!"
                }
            )
        workflow = get_workflow(workflow_id)
        audit_id = Audit.detail_by_workflow_id(
            workflow_id, WorkflowType.SQL_REVIEW
        ).audit_id
        with transaction.atomic():
            workflow.status = "workflow_timingtask"
            workflow.save(update_fields=["status"])
            Audit.add_log(
                audit_id,
                4,
                "定时执行",
                f"定时执行时间：{run_date}",
                request.user.username,
                request.user.display,
            )
            transaction.on_commit(
                lambda: add_sql_schedule(
                    f"sqlreview-timing-{workflow_id}", run_date, workflow_id
                )
            )
        return Response(mutation_response(workflow_id, "定时执行已设置"))


class WorkflowTerminationView(WorkflowOperationAPIView):
    def post(self, request, workflow_id):
        data = self.validated_data(WorkflowTerminationSerializer, request)
        workflow = get_workflow(workflow_id)
        if not can_cancel(request.user, workflow_id):
            raise PermissionDenied("你无权操作当前工单！")
        action = (
            WorkflowAction.ABORT
            if request.user.username == workflow.engineer
            else WorkflowAction.REJECT
        )
        if action == WorkflowAction.REJECT and not request.user.has_perm(
            "sql.sql_review"
        ):
            raise PermissionDenied("你无权操作当前工单！")
        config, was_scheduled = SysConfig(), workflow.status == "workflow_timingtask"
        with transaction.atomic():
            auditor = get_auditor(workflow=workflow, sys_config=config)
            try:
                detail = auditor.operate(action, request.user, data["cancel_remark"])
            except AuditException:
                logger.exception("终止工单失败，workflow_id=%s", workflow_id)
                raise ValidationError({"detail": "终止工单失败"})
            workflow.status = "workflow_abort"
            workflow.save(update_fields=["status"])
            if was_scheduled:
                transaction.on_commit(
                    lambda: del_schedule(f"sqlreview-timing-{workflow_id}")
                )
            if should_notify(config, "Cancel"):
                transaction.on_commit(
                    lambda: async_task(
                        notify_for_audit,
                        workflow_audit=auditor.audit,
                        workflow_audit_detail=detail,
                        timeout=60,
                        task_name=f"sqlreview-cancel-{workflow_id}",
                    )
                )
        return Response(mutation_response(workflow_id, "工单已终止"))


class WorkflowStatusView(WorkflowOperationAPIView):
    def get(self, request, workflow_id):
        workflow = get_workflow(workflow_id)
        ensure_viewable(request.user, workflow_id)
        return Response({"status": workflow.status, "msg": "", "data": ""})


class WorkflowOscView(WorkflowOperationAPIView):
    def post(self, request, workflow_id):
        data = self.validated_data(WorkflowOscSerializer, request)
        workflow = get_workflow(workflow_id)
        ensure_viewable(request.user, workflow_id)
        try:
            result = get_engine(workflow.instance).osc_control(
                command=data["command"], sqlsha1=data["sqlsha1"]
            )
            rows, error = result.to_dict(), result.error
        except Exception:
            logger.exception("控制 OSC 执行失败，workflow_id=%s", workflow_id)
            rows, error = [], "OSC 操作失败"
        return Response({"total": len(rows), "rows": rows, "msg": error})
