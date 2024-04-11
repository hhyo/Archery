# -*- coding: UTF-8 -*-
from sql.utils.workflow_audit import Audit
from archery import display_version
from common.config import SysConfig
from sql.models import TwoFactorAuthConfig


def global_info(request):
    """存放用户，菜单信息等."""
    twofa_type = "disabled"
    try:
        if request.user and request.user.is_authenticated:
            # 获取待办数量
            todo = Audit.todo(request.user)
            twofa_config = TwoFactorAuthConfig.objects.filter(user=request.user)
            if twofa_config:
                twofa_type = twofa_config[0].auth_type
        else:
            todo = 0
    except Exception:
        todo = 0

    watermark_enabled = SysConfig().get("watermark_enabled", False)
    # 添加公告
    announcement_content_enabled = SysConfig().get(
        "announcement_content_enabled", False
    )
    announcement_content = ""
    if announcement_content_enabled:
        announcement_content = SysConfig().get("announcement_content", "")

    return {
        "todo": todo,
        "archery_version": display_version,
        "watermark_enabled": watermark_enabled,
        "announcement_content_enabled": announcement_content_enabled,
        "announcement_content": announcement_content,
        "twofa_type": twofa_type,
    }
