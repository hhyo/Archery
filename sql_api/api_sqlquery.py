import logging

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, views
from rest_framework.response import Response

from sql.services.querylog_service import list_query_logs, update_favorite
from sql.services.resource_service import (
    describe_table_structure,
    list_instance_resources,
    list_user_accessible_instances,
)
from sql.services.sqlquery_service import execute_sql_query

from .renderers import SimpleJSONRenderer
from .serializers import (
    SqlQueryExecuteSerializer,
    SqlQueryFavoriteSerializer,
    SqlQueryDescribeTableSerializer,
    SqlQueryInstancesQuerySerializer,
    SqlQueryLogsQuerySerializer,
    SqlQueryResourceQuerySerializer,
)

logger = logging.getLogger(__name__)


def _get_list_values(params, key):
    values = params.getlist(key)
    if values:
        return values
    return params.getlist(f"{key}[]")


class SQLQueryInstancesView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="SQLQuery 可访问实例列表")
    def get(self, request):
        payload = {
            "db_type": _get_list_values(request.query_params, "db_type"),
            "tag_codes": _get_list_values(request.query_params, "tag_codes"),
        }
        req_type = request.query_params.get("type")
        if req_type is not None:
            payload["type"] = req_type
        serializer = SqlQueryInstancesQuerySerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        data = list_user_accessible_instances(
            user=request.user,
            type=serializer.validated_data.get("type"),
            db_type=serializer.validated_data.get("db_type"),
            tag_codes=serializer.validated_data.get("tag_codes"),
        )
        return Response(data)


class SQLQueryResourcesView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="SQLQuery 实例资源列表")
    def get(self, request):
        serializer = SqlQueryResourceQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = list_instance_resources(user=request.user, **serializer.validated_data)
        return Response(data)


class SQLQueryDescribeTableView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="SQLQuery 表结构")
    def post(self, request):
        serializer = SqlQueryDescribeTableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = describe_table_structure(user=request.user, **serializer.validated_data)
        return Response(data)


class SQLQueryExecuteView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [SimpleJSONRenderer]

    @extend_schema(summary="SQLQuery 执行查询")
    def post(self, request):
        if not (request.user.is_superuser or request.user.has_perm("sql.query_submit")):
            return Response({"status": 1, "msg": "无执行查询权限", "data": {}})
        serializer = SqlQueryExecuteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = execute_sql_query(user=request.user, **serializer.validated_data)
        return Response(data)


class SQLQueryLogsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="SQLQuery 历史查询记录")
    def get(self, request):
        if not (
            request.user.is_superuser
            or request.user.has_perm("sql.menu_sqlquery")
            or request.user.has_perm("sql.audit_user")
        ):
            return Response({"total": 0, "rows": []})

        serializer = SqlQueryLogsQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = list_query_logs(user=request.user, **serializer.validated_data)
        return Response(data)


class SQLQueryFavoritesView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="SQLQuery 收藏/取消收藏")
    def post(self, request):
        if not (
            request.user.is_superuser or request.user.has_perm("sql.menu_sqlquery")
        ):
            return Response({"status": 1, "msg": "无收藏操作权限"})
        serializer = SqlQueryFavoriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = update_favorite(user=request.user, **serializer.validated_data)
        return Response(data)
