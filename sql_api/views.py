from django.shortcuts import render
from django.shortcuts import get_object_or_404
from rest_framework import status
# Create your views here.
from sql.engines import get_engine
from sql_api.serializers import SqlWorkflowDetailSerilizer, SqlWorkflowListSerilizer, InstanceSerilizer
from sql.models import SqlWorkflow, Instance
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes, action

class IsOwner(BasePermission):
    message = 'Not allowed because you don\'t own it' 

    def has_permission(self, request, view):
        if view.action == 'list':
            return request.user.is_authenticated
        # 允许所有人创建
        elif view.action == 'create':
            return True
        #允许所有人查看
        elif view.action == 'retrieve':
            return True
        elif view.action in ['update', 'partial_update', 'destroy']:
            return False
        else:
            return False

    def has_object_permission(self, request, view, obj):
        return obj.engineer == request.user.username or request.user.is_superuser

class SqlWorkflowViewSet(viewsets.ViewSet):
    """
    sql 工单接口
    """
    permission_classes = (IsOwner, )
    def get_queryset(self, request):
        if request.user.is_superuser:
            return SqlWorkflow.objects.all()
        return SqlWorkflow.objects.filter(engineer=request.user.username)
    def list(self, request):
        """sql 工单列表, 超级管理员可以显示所有数据, 非管理员显示engineer为自己的"""
        queryset = self.get_queryset(request)
        serializer = SqlWorkflowListSerilizer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        queryset = SqlWorkflow.objects.all()
        wf = get_object_or_404(queryset, pk=pk)
        self.check_object_permissions(request, wf)
        serializer = SqlWorkflowDetailSerilizer(wf)
        return Response(serializer.data)

class InstanceViewSet(viewsets.ViewSet):
    """实例接口"""
    def list(self, request):
        """Instance列表"""
        queryset = Instance.objects.all()
        serializer = InstanceSerilizer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """Instance详情"""
        queryset = Instance.objects.all()
        ins = get_object_or_404(queryset, pk=pk)
        serializer = InstanceSerilizer(ins)
        return Response(serializer.data)
    
    @action(detail=True)
    def db_list(self, request, pk=None):
        """实例数据库列表"""
        queryset = Instance.objects.all()
        ins = get_object_or_404(queryset, pk=pk)
        try:
        # 取出该实例的连接方式，为了后面连进去获取所有databases
            query_engine = get_engine(instance=ins)
            db_list = query_engine.get_all_databases()
            # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
            if not db_list:
                result = {'error':'数据库列表为空, 可能是权限或配置有误'}
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
        except Exception as msg:
            result = {'error':str(msg)}
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(db_list)
    
    @action(detail=True)
    def table_list(self, request, pk=None):
        queryset = Instance.objects.all()
        ins = get_object_or_404(queryset, pk=pk)
        db_name = request.GET.get('db_name')
        try:
        # 取出该实例的连接方式，为了后面连进去获取所有databases
            query_engine = get_engine(instance=ins)
            table_list = query_engine.get_all_tables(db_name)
            # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
            if not table_list:
                result = {'error':'表列表为空, 可能是权限或配置有误'}
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
        except Exception as msg:
            result = {'error':str(msg)}
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(table_list)
    
    @action(detail=True)
    def column_list(self, request, pk=None):
        queryset = Instance.objects.all()
        ins = get_object_or_404(queryset, pk=pk)
        db_name = request.GET.get('db_name')
        tb_name = request.GET.get('table_name')
        try:
        # 取出该实例的连接方式，为了后面连进去获取所有databases
            query_engine = get_engine(instance=ins)
            col_list = query_engine.get_all_columns_by_tb(db_name, tb_name)
            if not col_list:
                result = {'error':'字段列表为空, 可能是权限或配置有误'}
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
        except Exception as msg:
            result = {'error':str(msg)}
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(col_list)