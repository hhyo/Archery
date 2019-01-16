# -*- coding: UTF-8 -*-
import traceback
import datetime
import simplejson as json

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import Group, Permission
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse

from sql.utils.inception import InceptionDao
from common.utils.permission import superuser_required
from sql.utils.jobs import job_info

from .models import Users, Instance, SqlWorkflow, QueryPrivileges, ResourceGroup, \
    QueryPrivilegesApply, Config, RedisApply
from sql.utils.workflow import Workflow
from sql.utils.sql_review import can_execute, can_timingtask, can_cancel
from common.utils.const import Const, WorkflowDict
from sql.utils.resource_group import user_groups, user_instances

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
def submit_sql(request):
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
        rows = workflow_detail.execute_result
    else:
        rows = workflow_detail.review_content
    list_content = json.loads(rows)
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
            run_date = job.next_run
        else:
            run_date = ''
    else:
        run_date = ''

    # sql结果
    column_list = ['ID', 'stage', 'errlevel', 'stagestatus', 'errormessage', 'SQL', 'Affected_rows', 'sequence',
                   'backup_dbname', 'execute_time', 'sqlsha1']
    context = {'workflow_detail': workflow_detail, 'column_list': column_list, 'rows':rows,
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
        list_backup_sql = InceptionDao().get_rollback_sql_list(workflow_id)
    except Exception as msg:
        logger.error(traceback.format_exc())
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    workflow_title = workflow_detail.workflow_name
    rollback_workflow_name = "【回滚工单】原工单Id:%s ,%s" % (workflow_id, workflow_title)
    context = {'list_backup_sql': list_backup_sql, 'workflow_detail': workflow_detail,
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


# SQL导出查询（大数据异步查询）
@permission_required('sql.menu_export_query', raise_exception=True)
def export_query(request):
    # 获取用户关联从库列表
    # listAllClusterName = [slave.instance_name for slave in user_instances(request.user, 'slave')]
    listAllClusterName = [slave.instance_name for slave in Instance.objects.filter(type='slave')]
    # 获取导出查询审核人
    auditors = list()
    for p in Permission.objects.filter(codename='export_query_review'):
        for g in p.group_set.all():
            auditors.extend(g.user_set.all())
    context = {'listAllClusterName': listAllClusterName, 'auditors': auditors}
    return render(request, 'export_query.html', context)


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


@permission_required('sql.menu_redis', raise_exception=True)
def redis(request):
    # 获取用户关联实例列表
    redis_list = Instance.objects.filter(db_type='redis').order_by('hostname')
    return render(request, 'redis.html', {'redis_list': redis_list, 'db_list': range(0, 16)})


@permission_required('sql.menu_redis', raise_exception=True)
def redis_apply(request):
    # 超过24H 未审核的申请设置为过期状态
    one_day_before = (datetime.datetime.now() + datetime.timedelta(days=-1)).strftime("%Y-%m-%d %H:%M:%S")
    RedisApply.objects.filter(create_time__lte=one_day_before).filter(status=0).update(status=4)
    redis_list = Instance.objects.filter(db_type='redis').order_by('hostname')
    return render(request, 'redis_apply.html', {'redis_list': redis_list})


# 参数管理
@permission_required('sql.menu_param', raise_exception=True)
def param(request):
    # 获取用户关联实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, 'all')]

    context = {'tab': 'param_tab', 'instances': instances}
    return render(request, 'param_setting.html', context)


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
    group_list = ResourceGroup.objects.all()

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
    group = ResourceGroup.objects.get(group_id=group_id)
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
