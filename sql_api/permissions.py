from rest_framework import permissions
from common.config import SysConfig


class IsApiSystemAdmin(permissions.BasePermission):
    """默认 API 权限：仅登录后的系统管理员可访问。"""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)


class IsInUserWhitelist(permissions.BasePermission):
    """
    自定义权限，只允许白名单用户调用api
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        config = SysConfig().get("api_user_whitelist")
        user_list = config.split(",") if config else []
        api_user_whitelist = [int(uid) for uid in user_list]

        # 只有在api_user_whitelist参数中的用户才有权限
        return request.user.id in api_user_whitelist


class IsOwner(permissions.BasePermission):
    """
    当参数engineer与请求用户一致时才有权限
    """

    def has_permission(self, request, view):
        try:
            engineer = request.data["engineer"]
        except KeyError as e:
            return False

        return engineer == request.user.username


class IsSqlQueryPageUser(permissions.BasePermission):
    """SQL 查询页面场景权限：登录且具备页面相关权限之一。"""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.has_perm("sql.menu_query") or user.has_perm("sql.menu_sqlquery")
