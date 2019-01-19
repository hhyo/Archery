# -*- coding: UTF-8 -*-
from sql.utils.workflow_audit import Audit


def global_info(request):
    """存放用户，菜单信息等."""
    user = request.user
    if user and user.is_authenticated:
        # 获取待办数量
        try:
            todo = Audit.todo(user)
        except Exception:
            todo = 0
    else:
        todo = 0

    return {
        'todo': todo,
    }
