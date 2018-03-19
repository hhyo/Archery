# -*- coding: UTF-8 -*- 
from .models import users
from django.conf import settings

leftMenuBtnsCommon = (
                   {'key':'allworkflow',        'name':'查看历史工单',     'url':'/allworkflow/',              'class':'glyphicon glyphicon-home'},
                   {'key':'submitsql',          'name':'发起SQL上线',       'url':'/submitsql/',               'class':'glyphicon glyphicon-asterisk'},
                   {'key': 'sqlquery',          'name': 'SQL在线查询',      'url': '/sqlquery/',                'class': 'glyphicon glyphicon-search'},
                   {'key': 'queryapply',        'name':'查询权限管理',      'url': '/queryapplylist/',         'class': 'glyphicon glyphicon-eye-open'},
)
leftMenuBtnsSuper = (
                   {'key': 'workflow', 'name': '查询权限审核', 'url': '/workflow/', 'class': 'glyphicon glyphicon-shopping-cart'},
                   {'key': 'admin', 'name': '后台数据管理', 'url': '/admin/', 'class': 'glyphicon glyphicon-list'},
)
leftMenuBtnsDoc = (
                   {'key':'dbaprinciples',     'name':'SQL审核必读',       'url':'/dbaprinciples/',        'class':'glyphicon glyphicon-book'},
                   {'key':'charts',     'name':'统计图表展示',       'url':'/charts/',        'class':'glyphicon glyphicon-file'},
)

if settings.ENABLE_LDAP:
    leftMenuBtnsSuper = (
        {'key': 'masterconfig', 'name': '主库地址配置', 'url': '/admin/sql/master_config/', 'class': 'glyphicon glyphicon-user'},
        {'key': 'userconfig', 'name': '用户权限配置', 'url': '/admin/sql/users/', 'class': 'glyphicon glyphicon-th-large'},
        {'key': 'ldapsync', 'name': '同步LDAP用户', 'url': '/ldapsync/', 'class': 'glyphicon glyphicon-th-large'},
        {'key': 'workflowconfig', 'name': '所有工单管理', 'url': '/admin/sql/workflow/','class': 'glyphicon glyphicon-list-alt'},
    )

def global_info(request):
    """存放用户，会话信息等."""
    loginUser = request.session.get('login_username', None)
    if loginUser is not None:
        user = users.objects.get(username=loginUser)
        if user.is_superuser:
            leftMenuBtns = leftMenuBtnsCommon + leftMenuBtnsSuper + leftMenuBtnsDoc
        else:
            leftMenuBtns = leftMenuBtnsCommon + leftMenuBtnsDoc
    else:
        leftMenuBtns = ()

    return {
        'loginUser':loginUser,
        'leftMenuBtns':leftMenuBtns,
    }
