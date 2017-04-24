# -*- coding: UTF-8 -*- 
from .models import users
leftMenuBtnsCommon = (
                   {'key':'allworkflow',        'name':'查看历史工单',     'url':'/allworkflow/',              'class':'glyphicon glyphicon-home'},
                   {'key':'submitsql',          'name':'发起SQL上线',       'url':'/submitsql/',               'class':'glyphicon glyphicon-asterisk'},
               )
leftMenuBtnsSuper = (
                   {'key':'masterconfig',       'name':'主库地址配置',      'url':'/admin/sql/master_config/',      'class':'glyphicon glyphicon-user'},
                   {'key':'userconfig',         'name':'用户权限配置',       'url':'/admin/sql/users/',        'class':'glyphicon glyphicon-th-large'},
                   {'key':'workflowconfig',     'name':'所有工单管理',       'url':'/admin/sql/workflow/',        'class':'glyphicon glyphicon-list-alt'},
)
leftMenuBtnsDoc = (
                   {'key':'dbaprinciples',     'name':'SQL审核必读',       'url':'/dbaprinciples/',        'class':'glyphicon glyphicon-book'},
                   {'key':'charts',     'name':'统计图表展示',       'url':'/charts/',        'class':'glyphicon glyphicon-file'},
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
