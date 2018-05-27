# -*- coding: UTF-8 -*- 
from .models import users
from django.conf import settings

leftMenuBtnsCommon = (
    {'key': 'sqlworkflow', 'name': 'SQL上线工单', 'url': '/sqlworkflow/', 'class': 'glyphicon glyphicon-home',
     'display': True},
    {'key': 'sqlquery', 'name': 'SQL在线查询', 'url': '/sqlquery/', 'class': 'glyphicon glyphicon-search',
     'display': settings.QUERY},
    {'key': 'slowquery', 'name': 'SQL慢查日志', 'url': '/slowquery/', 'class': 'glyphicon glyphicon-align-right',
     'display': settings.SLOWQUERY},
    {'key': 'sqladvisor', 'name': 'SQL优化工具', 'url': '/sqladvisor/', 'class': 'glyphicon glyphicon-wrench',
     'display': settings.SQLADVISOR},
    {'key': 'queryapply', 'name': '查询权限管理', 'url': '/queryapplylist/', 'class': 'glyphicon glyphicon-eye-open',
     'display': settings.QUERY},
    {'key': 'workflow', 'name': '所有待办工单', 'url': '/workflow/', 'class': 'glyphicon glyphicon-shopping-cart',
     'display': settings.QUERY},
)

leftMenuBtnsSuper = (
    {'key': 'diagnosis', 'name': 'RDS进程管理', 'url': '/diagnosis_process/', 'class': 'glyphicon  glyphicon-scissors',
     'display': settings.ALIYUN_RDS_MANAGE},
    {'key': 'config', 'name': '项目配置管理', 'url': '/config/', 'class': 'glyphicon glyphicon glyphicon-option-horizontal',
     'display': True},
    {'key': 'admin', 'name': '后台数据管理', 'url': '/admin/', 'class': 'glyphicon glyphicon-list', 'display': True},
)

leftMenuBtnsDoc = (
    {'key': 'dbaprinciples', 'name': 'SQL审核必读', 'url': '/dbaprinciples/', 'class': 'glyphicon glyphicon-book',
     'display': True},
    {'key': 'charts', 'name': '统计图表展示', 'url': '/charts/', 'class': 'glyphicon glyphicon-file', 'display': True},
)


def global_info(request):
    """存放用户，会话信息等."""
    loginUser = request.session.get('login_username', None)
    if loginUser is not None:
        user = users.objects.get(username=loginUser)
        UserDisplay = user.display
        if UserDisplay == '':
            UserDisplay = loginUser
        if user.is_superuser:
            leftMenuBtns = leftMenuBtnsCommon + leftMenuBtnsSuper + leftMenuBtnsDoc
        else:
            leftMenuBtns = leftMenuBtnsCommon + leftMenuBtnsDoc
    else:
        leftMenuBtns = ()
        UserDisplay = ''

    return {
        'loginUser': loginUser,
        'leftMenuBtns': leftMenuBtns,
        'UserDisplay': UserDisplay
    }
