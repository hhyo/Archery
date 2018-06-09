# -*- coding: UTF-8 -*-
from archer import settings
from sql.workflow import Workflow
from .models import users, Config
from .config import SysConfig


def menu():
    sys_config = SysConfig().sys_config
    if sys_config.get('sqladvisor') != '':
        sqladvisor_display = 'true'
    else:
        sqladvisor_display = 'false'
    leftMenuBtnsCommon = (
        {'key': 'sqlworkflow', 'name': 'SQL上线工单', 'url': '/sqlworkflow/', 'class': 'glyphicon glyphicon-home',
         'display': 'true'},
        {'key': 'sqlquery', 'name': 'SQL在线查询', 'url': '/sqlquery/', 'class': 'glyphicon glyphicon-search',
         'display': sys_config.get('query')},
        {'key': 'slowquery', 'name': 'SQL慢查日志', 'url': '/slowquery/', 'class': 'glyphicon glyphicon-align-right',
         'display': sys_config.get('slowquery')},
        {'key': 'sqladvisor', 'name': 'SQL优化工具', 'url': '/sqladvisor/', 'class': 'glyphicon glyphicon-wrench',
         'display': sqladvisor_display},
        {'key': 'queryapply', 'name': '查询权限管理', 'url': '/queryapplylist/', 'class': 'glyphicon glyphicon-eye-open',
         'display': sys_config.get('query')}
    )

    leftMenuBtnsSuper = (
        {'key': 'diagnosis', 'name': 'RDS进程管理', 'url': '/diagnosis_process/', 'class': 'glyphicon  glyphicon-scissors',
         'display': sys_config.get('aliyun_rds_manage')},
        {'key': 'config', 'name': '系统配置管理', 'url': '/config/',
         'class': 'glyphicon glyphicon glyphicon-option-horizontal',
         'display': 'true'},
        {'key': 'admin', 'name': '后台数据管理', 'url': '/admin/', 'class': 'glyphicon glyphicon-list', 'display': 'true'},
    )

    leftMenuBtnsDoc = (
        {'key': 'dbaprinciples', 'name': 'SQL审核必读', 'url': '/dbaprinciples/', 'class': 'glyphicon glyphicon-book',
         'display': 'true'},
        {'key': 'charts', 'name': '统计图表展示', 'url': '/charts/', 'class': 'glyphicon glyphicon-file', 'display': 'true'},
    )
    return leftMenuBtnsCommon, leftMenuBtnsSuper, leftMenuBtnsDoc


def global_info(request):
    """存放用户，会话信息等."""
    loginUser = request.session.get('login_username', None)
    if loginUser is not None:
        leftMenuBtnsCommon, leftMenuBtnsSuper, leftMenuBtnsDoc = menu()
        user = users.objects.get(username=loginUser)
        UserDisplay = user.display
        if UserDisplay == '':
            UserDisplay = loginUser
        if user.is_superuser:
            leftMenuBtns = leftMenuBtnsCommon + leftMenuBtnsSuper + leftMenuBtnsDoc
        else:
            leftMenuBtns = leftMenuBtnsCommon + leftMenuBtnsDoc
        # 获取待办数量
        try:
            todo = Workflow().auditlist(user, 0, 0, 1)['data']['auditlistCount']
        except Exception:
            todo = 0
    else:
        leftMenuBtns = ()
        UserDisplay = ''
        todo = 0

    return {
        'loginUser': loginUser,
        'leftMenuBtns': leftMenuBtns,
        'UserDisplay': UserDisplay,
        'todo': todo,
    }
