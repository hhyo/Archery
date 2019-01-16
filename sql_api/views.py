from django.shortcuts import render
from django.shortcuts import get_object_or_404
# Create your views here.

from sql_api.serializers import SqlWorkflowDetailSerilizer, SqlWorkflowListSerilizer
from sql.models import SqlWorkflow
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

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

