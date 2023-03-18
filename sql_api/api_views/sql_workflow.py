# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: sql_workflow.py
@time: 2022/10/07
"""
__author__ = "hhyo"

import django_filters
from django.contrib.auth.decorators import permission_required
from django.utils.decorators import method_decorator
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import views, permissions, serializers, viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sql.engines import get_engine
from sql.models import SqlWorkflow
from sql.utils.resource_group import user_groups
from sql_api.filters import SqlWorkflowFilter
from sql_api.pagination import CustomizedPaginationV2
from sql_api.permissions.sql_workflow import SqlWorkFlowViewPermission
from sql_api.serializers.sql_workflow import (
    ExecuteCheckSerializer,
    ExecuteCheckResultSerializer,
    SqlWorkflowSerializer,
    SqlWorkflowDetailSerializer,
    SqlWorkflowExecuteSerializer,
    SqlWorkflowTimingTaskSerializer,
)


class ExecuteCheck(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="SQL检查",
        request=ExecuteCheckSerializer,
        responses={200: ExecuteCheckResultSerializer},
        description="对提供的SQL进行语法检查",
    )
    @method_decorator(permission_required("sql.sql_submit", raise_exception=True))
    def post(self, request):
        # 参数验证
        serializer = ExecuteCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.get_instance()
        # 交给engine进行检测
        try:
            check_engine = get_engine(instance=instance)
            check_result = check_engine.execute_check(
                db_name=request.data["db_name"], sql=request.data["full_sql"].strip()
            )
        except Exception as e:
            raise serializers.ValidationError({"errors": f"{e}"})
        check_result.rows = check_result.to_dict()
        serializer_obj = ExecuteCheckResultSerializer(check_result)
        return Response(serializer_obj.data)


@extend_schema_view(
    create=extend_schema(exclude=True),
    partial_update=extend_schema(exclude=True),
    list=extend_schema(
        summary="获取SQL工单列表",
        description="获取SQL工单列表，支持筛选、分页、检索等",
        request=SqlWorkflowSerializer,
        responses={
            200: SqlWorkflowSerializer(exclude=["sql_content", "display_content"])
        },
    ),
    retrieve=extend_schema(
        summary="获取SQL工单详情",
        description="通过工单ID获取工单详情",
        responses={200: SqlWorkflowDetailSerializer},
    ),
    rollback_sql=extend_schema(
        summary="获取SQL工单回滚语句",
        responses={
            200: serializers.ListSerializer(
                child=serializers.ListField(default=["sql", "rollback_sql"])
            )
        },
        description="通过工单ID获取回滚语句",
    ),
    alter_run_date=extend_schema(
        summary="修改SQL工单可执行时间范围",
        request=SqlWorkflowSerializer(fields=["run_date_start", "run_date_end"]),
        responses={200: SqlWorkflowSerializer},
        description="通过工单ID修改SQL工单可执行时间范围",
    ),
    execute=extend_schema(
        summary="立即执行工单",
        request=SqlWorkflowExecuteSerializer,
        responses={200: OpenApiTypes.NUMBER},
        description="通过工单ID执行工单",
    ),
    timing_task=extend_schema(
        summary="设置定时执行工单",
        request=SqlWorkflowTimingTaskSerializer,
        responses={200: OpenApiTypes.DATETIME},
        description="通过工单ID执行工单",
    ),
)
class SqlWorkflowView(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, SqlWorkFlowViewPermission]
    serializer_class = SqlWorkflowSerializer
    pagination_class = CustomizedPaginationV2
    filter_backends = [
        filters.SearchFilter,
        django_filters.rest_framework.DjangoFilterBackend,
    ]
    filterset_class = SqlWorkflowFilter
    search_fields = ["engineer_display", "workflow_name"]
    http_method_names = ["get", "post", "patch"]

    def get_queryset(self):
        """
        1、非管理员，拥有审核权限、资源组粒度执行权限的，可以查看组内所有工单
        2、管理员，审计员，可查看所有工单
        """
        filter_dict = {}
        user = self.request.user
        # 管理员，审计员，可查看所有工单
        if user.is_superuser or user.has_perm("sql.audit_user"):
            pass
        # 非管理员，拥有审核权限、资源组粒度执行权限的，可以查看组内所有工单
        elif user.has_perm("sql.sql_review") or user.has_perm(
            "sql.sql_execute_for_resource_group"
        ):
            filter_dict["group_id__in"] = [
                group.group_id for group in user_groups(user)
            ]
        # 其他人只能查看自己提交的工单
        else:
            filter_dict["engineer"] = user.username
        queryset = SqlWorkflow.objects.filter(**filter_dict).order_by("-id")
        return self.get_serializer_class().setup_eager_loading(queryset)

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs.setdefault("context", self.get_serializer_context())
        if self.action == "retrieve":
            return serializer_class(*args, **kwargs)
        return serializer_class(
            *args, **kwargs, exclude=["sql_content", "display_content"]
        )

    @action(
        methods=["get"],
        detail=True,
        pagination_class=None,
        filter_backends=[],
        search_fields=None,
    )
    def rollback_sql(self, request, *args, **kwargs):
        obj = self.get_object()
        data = self.get_serializer().rollback_sql(obj)
        return Response(data)

    @method_decorator(permission_required("sql.sql_review", raise_exception=True))
    @action(methods=["patch"], detail=True)
    def alter_run_date(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @action(methods=["post"], detail=True)
    def execute(self, request, *args, **kwargs):
        obj = self.get_object()
        SqlWorkflowExecuteSerializer(data=request.data).is_valid(raise_exception=True)
        mode = request.data.get("mode")
        serializer = self.get_serializer()
        serializer.execute(obj, mode=mode, username=request.user.username)
        return Response(obj.id)

    @action(methods=["post"], detail=True)
    def timing_task(self, request, *args, **kwargs):
        obj = self.get_object()
        SqlWorkflowTimingTaskSerializer(data=request.data).is_valid(
            raise_exception=True
        )
        run_date = request.data.get("run_date")
        serializer = self.get_serializer()
        serializer.timing_task(obj, run_date=run_date, username=request.user.username)
        return Response(run_date)
