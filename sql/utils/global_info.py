# -*- coding: UTF-8 -*-
from sql.workflow import Workflow
from sql.models import users
from sql.utils.config import SysConfig


def global_info(request):
    """存放用户，菜单信息等."""
    user = request.user
    if user:
        # 获取待办数量
        try:
            todo = Workflow().auditlist(user, 0, 0, 1)['data']['auditlistCount']
        except Exception:
            todo = 0
    else:
        todo = 0

    return {
        'loginUser': user.username,
        'todo': todo,
    }
