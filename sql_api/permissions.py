from rest_framework import permissions
from common.config import SysConfig


class IsInUserWhitelist(permissions.BasePermission):
    """
    自定义权限，只允许白名单用户调用api
    """
    def has_permission(self, request, view):
        config = SysConfig().get('api_user_whitelist')
        user_list = config.split(',') if config else []
        api_user_whitelist = [int(uid) for uid in user_list]

        # 只有在api_user_whitelist参数中的用户才有权限
        return request.user.id in api_user_whitelist
