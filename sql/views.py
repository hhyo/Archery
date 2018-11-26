# -*- coding: UTF-8 -*-
import traceback

import simplejson as json

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import Group
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse

from sql.utils.inception import InceptionDao
from common.utils.permission import superuser_required
from sql.utils.jobs import job_info

from .models import Users, SqlWorkflow, QueryPrivileges, SqlGroup, \
    QueryPrivilegesApply, Config
from sql.utils.workflow import Workflow
from sql.utils.sql_review import can_execute, can_timingtask, can_cancel
from common.utils.const import Const, WorkflowDict
from sql.utils.group import user_groups, user_instances

import logging

logger = logging.getLogger('default')


# 登录页面
def login(request):
    return render(request, 'login.html')


# SQL上线工单列表页面
@permission_required('sql.menu_sqlworkflow', raise_exception=True)
def sqlworkflow(request):
    return render(request, 'sqlworkflow.html')


# 提交SQL的页面
@permission_required('sql.sql_submit', raise_exception=True)
def submitSql(request):
    user = request.user
    # 获取组信息
    group_list = user_groups(user)

    # 获取所有有效用户，通知对象
    active_user = Users.objects.filter(is_active=1)

    context = {'active_user': active_user, 'group_list': group_list}
    return render(request, 'sqlsubmit.html', context)


# 展示SQL工单详细页面
def detail(request, workflow_id):
    workflow_detail = get_object_or_404(SqlWorkflow, pk=workflow_id)
    if workflow_detail.status in (Const.workflowStatus['finish'], Const.workflowStatus['exception']) \
            and workflow_detail.is_manual == 0:
        listContent = json.loads(workflow_detail.execute_result)
    else:
        listContent = json.loads(workflow_detail.review_content)

    # 自动审批不通过的不需要获取下列信息
    if workflow_detail.status != Const.workflowStatus['autoreviewwrong']:
        # 获取当前审批和审批流程
        audit_auth_group, current_audit_auth_group = Workflow.review_info(workflow_id, 2)

        # 是否可审核
        is_can_review = Workflow.can_review(request.user, workflow_id, 2)
        # 是否可执行
        is_can_execute = can_execute(request.user, workflow_id)
        # 是否可定时执行
        is_can_timingtask = can_timingtask(request.user, workflow_id)
        # 是否可取消
        is_can_cancel = can_cancel(request.user, workflow_id)
    else:
        audit_auth_group = '系统自动驳回'
        current_audit_auth_group = '系统自动驳回'
        is_can_review = False
        is_can_execute = False
        is_can_timingtask = False
        is_can_cancel = False

    # 获取定时执行任务信息
    if workflow_detail.status == Const.workflowStatus['timingtask']:
        job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflow_id)
        job = job_info(job_id)
        if job:
            run_date = job.next_run_time
        else:
            run_date = ''
    else:
        run_date = ''

    # sql结果
    column_list = ['ID', 'stage', 'errlevel', 'stagestatus', 'errormessage', 'SQL', 'Affected_rows', 'sequence',
                   'backup_dbname', 'execute_time', 'sqlsha1']
    rows = []
    for row_index, row_item in enumerate(listContent):
        row = {}
        row['ID'] = row_index + 1
        row['stage'] = row_item[1]
        row['errlevel'] = row_item[2]
        row['stagestatus'] = row_item[3]
        row['errormessage'] = row_item[4]
        row['SQL'] = row_item[5]
        row['Affected_rows'] = row_item[6]
        row['sequence'] = row_item[7]
        row['backup_dbname'] = row_item[8]
        row['execute_time'] = row_item[9]
        # row['sqlsha1'] = row_item[10]
        rows.append(row)

        if workflow_detail.status == '执行中':
            row['stagestatus'] = ''.join(
                ["<div id=\"td_" + str(row['ID']) + "\" class=\"form-inline\">",
                 "   <div class=\"progress form-group\" style=\"width: 80%; height: 18px; float: left;\">",
                 "       <div id=\"div_" + str(row['ID']) + "\" class=\"progress-bar\" role=\"progressbar\"",
                 "            aria-valuenow=\"60\"",
                 "            aria-valuemin=\"0\" aria-valuemax=\"100\">",
                 "           <span id=\"span_" + str(row['ID']) + "\"></span>",
                 "       </div>",
                 "   </div>",
                 "   <div class=\"form-group\" style=\"width: 10%; height: 18px; float: right;\">",
                 "       <form method=\"post\">",
                 "           <input type=\"hidden\" name=\"workflow_id\" value=\"" + str(workflow_detail.id) + "\">",
                 "           <button id=\"btnstop_" + str(row['ID']) + "\" value=\"" + str(row['ID']) + "\"",
                 "                   type=\"button\" class=\"close\" style=\"display: none\" title=\"停止pt-OSC进程\">",
                 "               <span class=\"glyphicons glyphicons-stop\">&times;</span>",
                 "           </button>",
                 "       </form>",
                 "   </div>",
                 "</div>"])
    context = {'workflow_detail': workflow_detail, 'column_list': column_list, 'rows': rows,
               'is_can_review': is_can_review, 'is_can_execute': is_can_execute, 'is_can_timingtask': is_can_timingtask,
               'is_can_cancel': is_can_cancel, 'audit_auth_group': audit_auth_group,
               'current_audit_auth_group': current_audit_auth_group, 'run_date': run_date}
    return render(request, 'detail.html', context)


# 展示回滚的SQL页面
def rollback(request):
    workflow_id = request.GET['workflow_id']
    if workflow_id == '' or workflow_id is None:
        context = {'errMsg': 'workflow_id参数为空.'}
        return render(request, 'error.html', context)
    workflow_id = int(workflow_id)
    try:
        listBackupSql = InceptionDao().get_rollback_sql_list(workflow_id)
    except Exception as msg:
        logger.error(traceback.format_exc())
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    workflow_title = workflow_detail.workflow_name
    rollback_workflow_name = "【回滚工单】原工单Id:%s ,%s" % (workflow_id, workflow_title)
    context = {'listBackupSql': listBackupSql, 'workflow_detail': workflow_detail,
               'rollback_workflow_name': rollback_workflow_name}
    return render(request, 'rollback.html', context)


# SQL文档页面
@permission_required('sql.menu_document', raise_exception=True)
def dbaprinciples(request):
    return render(request, 'dbaprinciples.html')


# dashboard页面
@permission_required('sql.menu_dashboard', raise_exception=True)
def dashboard(request):
    return render(request, 'dashboard.html')


# SQL在线查询页面
@permission_required('sql.menu_query', raise_exception=True)
def sqlquery(request):
    # 获取用户关联实例列表
    instances = [slave.instance_name for slave in user_instances(request.user, 'slave')]

    context = {'instances': instances}
    return render(request, 'sqlquery.html', context)


# SQL慢日志页面
@permission_required('sql.menu_slowquery', raise_exception=True)
def slowquery(request):
    # 获取用户关联实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, 'all')]

    context = {'tab': 'slowquery', 'instances': instances}
    return render(request, 'slowquery.html', context)


# SQL优化工具页面
@permission_required('sql.menu_sqladvisor', raise_exception=True)
def sqladvisor(request):
    # 获取用户关联实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, 'all')]

    context = {'instances': instances}
    return render(request, 'sqladvisor.html', context)


# 查询权限申请列表页面
@permission_required('sql.menu_queryapplylist', raise_exception=True)
def queryapplylist(request):
    user = request.user
    # 获取资源组
    group_list = user_groups(user)

    context = {'group_list': group_list}
    return render(request, 'queryapplylist.html', context)


# 查询权限申请详情页面
def queryapplydetail(request, apply_id):
    workflow_detail = QueryPrivilegesApply.objects.get(apply_id=apply_id)
    # 获取当前审批和审批流程
    audit_auth_group, current_audit_auth_group = Workflow.review_info(apply_id, 1)

    # 是否可审核
    is_can_review = Workflow.can_review(request.user, apply_id, 1)

    context = {'workflow_detail': workflow_detail, 'audit_auth_group': audit_auth_group,
               'current_audit_auth_group': current_audit_auth_group, 'is_can_review': is_can_review}
    return render(request, 'queryapplydetail.html', context)


# 用户的查询权限管理页面
def queryuserprivileges(request):
    # 获取所有用户
    user_list = QueryPrivileges.objects.filter(is_deleted=0).values('user_name').distinct()
    context = {'user_list': user_list}
    return render(request, 'queryuserprivileges.html', context)


# 会话管理页面
@permission_required('sql.menu_dbdiagnostic', raise_exception=True)
def dbdiagnostic(request):
    # 获取用户关联实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, 'all')]

    context = {'tab': 'process', 'instances': instances}
    return render(request, 'dbdiagnostic.html', context)


# 工作流审核列表页面
def workflows(request):
    return render(request, "workflow.html")


# 工作流审核详情页面
def workflowsdetail(request, audit_id):
    # 按照不同的workflow_type返回不同的详情
    audit_detail = Workflow.audit_detail(audit_id)
    if audit_detail.workflow_type == WorkflowDict.workflow_type['query']:
        return HttpResponseRedirect(reverse('sql:queryapplydetail', args=(audit_detail.workflow_id,)))
    elif audit_detail.workflow_type == WorkflowDict.workflow_type['sqlreview']:
        return HttpResponseRedirect(reverse('sql:detail', args=(audit_detail.workflow_id,)))


# 配置管理页面
@superuser_required
def config(request):
    # 获取所有资源组名称
    group_list = SqlGroup.objects.all()

    # 获取所有权限组
    auth_group_list = Group.objects.all()
    # 获取所有配置项
    all_config = Config.objects.all().values('item', 'value')
    sys_config = {}
    for items in all_config:
        sys_config[items['item']] = items['value']

    context = {'group_list': group_list, 'auth_group_list': auth_group_list,
               'config': sys_config, 'WorkflowDict': WorkflowDict}
    return render(request, 'config.html', context)


# 资源组管理页面
@superuser_required
def group(request):
    return render(request, 'group.html')


# 资源组组关系管理页面
@superuser_required
def groupmgmt(request, group_id):
    group = SqlGroup.objects.get(group_id=group_id)
    return render(request, 'groupmgmt.html', {'group': group})


# 实例管理页面
@permission_required('sql.menu_instance', raise_exception=True)
def instance(request):
    return render(request, 'instance.html')


# 实例用户管理页面
@permission_required('sql.menu_instance', raise_exception=True)
def instanceuser(request, instance_id):
    return render(request, 'instanceuser.html', {'instance_id': instance_id})


# binlog2sql页面
@permission_required('sql.menu_binlog2sql', raise_exception=True)
def binlog2sql(request):
    # 获取实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, 'all')]
    return render(request, 'binlog2sql.html', {'instances': instances})


# 数据库差异对比页面
@permission_required('sql.menu_schemasync', raise_exception=True)
def schemasync(request):
    # 获取实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, 'all')]
    return render(request, 'schemasync.html', {'instances': instances})
