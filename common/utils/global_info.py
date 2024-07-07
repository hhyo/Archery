# -*- coding: UTF-8 -*-
from sql.utils.workflow_audit import Audit
from archery import display_version, settings
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

    sys_config = SysConfig()
    watermark_enabled = sys_config.get("watermark_enabled", False)
    # 添加公告
    announcement_content_enabled = sys_config.get("announcement_content_enabled", False)
    announcement_content = sys_config.get("announcement_content", "")
    custom_title_suffix = sys_config.get("custom_title_suffix", "")
    if not custom_title_suffix:
        custom_title_suffix = settings.CUSTOM_TITLE_SUFFIX
    auto_review = sys_config.get("auto_review", "")
    if not auto_review:
        auto_review = False
    auto_review_wrong = sys_config.get("auto_review_wrong", "")
    if not auto_review_wrong:
        auto_review_wrong = "2"
    auto_review_wrong_disubmit = sys_config.get("auto_review_wrong_disubmit", "")
    if not auto_review_wrong_disubmit:
        auto_review_wrong_disubmit = False
    print(auto_review_wrong_disubmit)
    return {
        "todo": todo,
        "archery_version": display_version,
        "watermark_enabled": watermark_enabled,
        "announcement_content_enabled": announcement_content_enabled,
        "custom_title_suffix": custom_title_suffix,
        "announcement_content": announcement_content,
        "twofa_type": twofa_type,
        "auto_review": auto_review,
        "auto_review_wrong": auto_review_wrong,
        "auto_review_wrong_disubmit": auto_review_wrong_disubmit,
    }
