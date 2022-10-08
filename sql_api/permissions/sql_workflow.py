# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: sql_workflow.py
@time: 2022/10/07
"""
__author__ = "hhyo"

from rest_framework import permissions

from sql.utils.sql_review import can_view, can_rollback
from sql.utils.workflow_audit import Audit


class SqlWorkFlowViewPermission(permissions.BasePermission):
    """SQL工单权限校验"""

    message = "你无权操作当前工单"

    def has_permission(self, request, view):
        self.message = "你没有获取工单列表的权限"
        return any(
            [
                request.user.has_perm("sql.menu_sqlworkflow"),
                request.user.has_perm("sql.audit_user"),
            ]
        )

    def has_retrieve_permission(self, request, view, obj):
        self.message = "你无权操作当前工单"
        return can_view(request.user, obj.id)

    def has_rollback_sql_permission(self, request, view, obj):
        self.message = "工单状态不正确或者你没有该工单的权限"
        return can_rollback(request.user, obj.id)

    def has_alter_run_date_permission(self, request, view, obj):
        self.message = "工单状态不正确或者你没有该工单的权限"
        return Audit.can_review(request.user, obj.id, 2)

    def has_object_permission(self, request, view, obj):
        return getattr(self, f"has_{view.action}_permission")(request, view, obj)
