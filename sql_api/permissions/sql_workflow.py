# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: sql_workflow.py
@time: 2022/10/07
"""
__author__ = "hhyo"

from rest_framework import permissions

from sql.utils.sql_review import can_view, can_rollback, can_execute, on_correct_time_period
from sql.utils.workflow_audit import Audit


class SqlWorkFlowViewPermission(permissions.BasePermission):
    """SQL工单权限校验"""

    message = "你没有获取工单列表的权限"
    obj_message = "工单状态不正确或者你没有该工单的权限"

    def has_permission(self, request, view):
        """列表权限"""
        self.message = self.message
        return any(
            [
                request.user.has_perm("sql.menu_sqlworkflow"),
                request.user.has_perm("sql.audit_user"),
            ]
        )

    def has_retrieve_permission(self, request, view, obj):
        """详情权限"""
        self.message = self.obj_message
        return can_view(request.user, obj.id)

    def has_rollback_sql_permission(self, request, view, obj):
        """回滚语句权限"""
        self.message = self.obj_message
        return can_rollback(request.user, obj.id)

    def has_alter_run_date_permission(self, request, view, obj):
        """修改执行时间范围权限"""
        self.message = self.obj_message
        return Audit.can_review(request.user, obj.id, 2)

    def has_execute_permission(self, request, view, obj):
        """执行语句权限"""
        self.message = self.obj_message
        if not can_execute(request.user, obj.id):
            return False
        if not on_correct_time_period(obj.id):
            self.message = "不在可执行时间范围内，如果需要修改执行时间请重新提交工单!"
            return False

    def has_object_permission(self, request, view, obj):
        return getattr(self, f"has_{view.action}_permission")(request, view, obj)
