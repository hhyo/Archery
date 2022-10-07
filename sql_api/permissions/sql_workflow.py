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


class SqlWorkFlowViewPermission(permissions.BasePermission):
    """SQL工单权限校验"""

    message = "您没有该工单的权限"

    @staticmethod
    def has_list_permission(request, view, obj):
        return request.user.has_perms(["sql.menu_sqlworkflow", "sql.audit_user"])

    @staticmethod
    def has_retrieve_permission(request, view, obj):
        return can_view(request.user, obj.id)

    @staticmethod
    def has_rollback_sql_permission(request, view, obj):
        return can_rollback(request.user, obj.id)

    def has_object_permission(self, request, view, obj):
        return getattr(self, f"has_{view.action}_permission")(request, view, obj)
