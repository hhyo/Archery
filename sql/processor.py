# coding: utf-8

leftMenuBtns = (
                   {'key':'allworkflow',        'name':'查看历史工单',     'url':'/allworkflow/',              'class':'glyphicon glyphicon-home'},
                   {'key':'submitsql',          'name':'发起SQL上线',       'url':'/submitsql/',               'class':'glyphicon glyphicon-asterisk'},
                   {'key':'masterconfig',       'name':'主库地址配置',      'url':'/admin/sql/master_config/',      'class':'glyphicon glyphicon-user'},
                   {'key':'userconfig',         'name':'用户权限配置',       'url':'/admin/sql/users/',        'class':'glyphicon glyphicon-th-large'},
                   {'key':'workflowconfig',     'name':'所有工单管理',       'url':'/admin/sql/workflow/',        'class':'glyphicon glyphicon-list-alt'},
               )

def global_info(request):
    """存放用户，会话信息等."""
    loginUser = request.session.get('login_username', '匿名用户')
    return {
        'loginUser':loginUser,
        'leftMenuBtns':leftMenuBtns,
    }
