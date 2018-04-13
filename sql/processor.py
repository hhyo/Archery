# -*- coding: UTF-8 -*- 
from .models import users
from django.conf import settings

leftMenuBtnsCommon = (
    {'key': 'allworkflow', 'name': '查看历史工单', 'url': '/allworkflow/', 'class': 'glyphicon glyphicon-home'},
    {'key': 'submitsql', 'name': '发起SQL上线', 'url': '/submitsql/', 'class': 'glyphicon glyphicon-asterisk'},
    {'key': 'sqlquery', 'name': 'SQL在线查询', 'url': '/sqlquery/', 'class': 'glyphicon glyphicon-search'},
    {'key': 'slowquery', 'name': 'SQL慢查日志', 'url': '/slowquery/', 'class': 'glyphicon glyphicon-align-right'},
    {'key': 'sqladvisor', 'name': 'SQL优化工具', 'url': '/sqladvisor/', 'class': 'glyphicon glyphicon-wrench'},
    {'key': 'queryapply', 'name': '查询权限管理', 'url': '/queryapplylist/', 'class': 'glyphicon glyphicon-eye-open'},
    {'key': 'workflow', 'name': '工单审核管理', 'url': '/workflow/', 'class': 'glyphicon glyphicon-shopping-cart'},
)

leftMenuBtnsAliYun = (
    {'key': 'diagnosis', 'name': 'RDS进程管理', 'url': '/diagnosis_process/','class': 'glyphicon glyphicon glyphicon-scissors'},
)

leftMenuBtnsSuper = (
    {'key': 'admin', 'name': '后台数据管理', 'url': '/admin/', 'class': 'glyphicon glyphicon-list'},
)

leftMenuBtnsDoc = (
    {'key': 'dbaprinciples', 'name': 'SQL审核必读', 'url': '/dbaprinciples/', 'class': 'glyphicon glyphicon-book'},
    {'key': 'charts', 'name': '统计图表展示', 'url': '/charts/', 'class': 'glyphicon glyphicon-file'},
)

if settings.ENABLE_LDAP:
    leftMenuBtnsSuper = (
        {'key': 'ldapsync', 'name': '同步LDAP用户', 'url': '/ldapsync/', 'class': 'glyphicon glyphicon-th-large'},
        {'key': 'admin', 'name': '后台数据管理', 'url': '/admin/', 'class': 'glyphicon glyphicon-list'},
    )

if settings.ENABLE_ALIYUN:
    leftMenuBtnsCommon = leftMenuBtnsCommon + leftMenuBtnsAliYun

def global_info(request):
    """存放用户，会话信息等."""
    loginUser = request.session.get('login_username', None)
    if loginUser is not None:
        user = users.objects.get(username=loginUser)
        UserDisplay = user.display
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
