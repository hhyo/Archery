# -*- coding: UTF-8 -*-
from sql.utils.workflow_audit import Audit
from archery import display_version
from common.config import SysConfig
from sql.models import TwoFactorAuthConfig


def global_info(request):
    """存放用户，菜单信息等."""
    user = request.user
    twofa_type = "disabled"
    if user and user.is_authenticated:
        # 获取待办数量
        try:
            todo = Audit.todo(user)
        except Exception:
            todo = 0

        twofa_config = TwoFactorAuthConfig.objects.filter(user=user)
        if twofa_config:
            twofa_type = twofa_config[0].auth_type
        else:
            twofa_type = "disabled"
    else:
        todo = 0

    watermark_enabled = SysConfig().get("watermark_enabled", False)

    return {
        "todo": todo,
        "archery_version": display_version,
        "watermark_enabled": watermark_enabled,
        "twofa_type": twofa_type,
    }
