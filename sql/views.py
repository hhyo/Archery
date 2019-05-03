# -*- coding: UTF-8 -*-
import traceback

import simplejson as json

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import Group
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse

from common.config import SysConfig
from sql.engines import get_engine
from common.utils.permission import superuser_required
from sql.engines.models import ReviewResult, ReviewSet
from sql.utils.tasks import task_info

from .models import Users, SqlWorkflow, QueryPrivileges, ResourceGroup, \
    QueryPrivilegesApply, Config, SQL_WORKFLOW_CHOICES, InstanceTag
from sql.utils.workflow_audit import Audit
from sql.utils.sql_review import can_execute, can_timingtask, can_cancel
from common.utils.const import Const, WorkflowDict
from sql.utils.resource_group import user_groups, user_instances

import logging

logger = logging.getLogger('default')


def index(request):
    index_path_url = SysConfig().get('index_path_url', 'sqlworkflow')
    return HttpResponseRedirect(f"/{index_path_url.strip('/')}/")


def login(request):
    """登录页面"""
    if request.user and request.user.is_authenticated:
        return HttpResponseRedirect('/')
    return render(request, 'login.html')


def sqlworkflow(request):
    """SQL上线工单列表页面"""
    return render(request, 'sqlworkflow.html', {'status_list': SQL_WORKFLOW_CHOICES})


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
    if workflow_detail.status in ['workflow_finish', 'workflow_exception'] \
            and workflow_detail.is_manual == 0:
        rows = workflow_detail.sqlworkflowcontent.execute_result
    else:
        rows = workflow_detail.sqlworkflowcontent.review_content
    # 自动审批不通过的不需要获取下列信息
    if workflow_detail.status != 'workflow_autoreviewwrong':
        # 获取当前审批和审批流程
        audit_auth_group, current_audit_auth_group = Audit.review_info(workflow_id, 2)

        # 是否可审核
        is_can_review = Audit.can_review(request.user, workflow_id, 2)
        # 是否可执行
        is_can_execute = can_execute(request.user, workflow_id)
        # 是否可定时执行
        is_can_timingtask = can_timingtask(request.user, workflow_id)
        # 是否可取消
        is_can_cancel = can_cancel(request.user, workflow_id)

        # 获取审核日志
        try:
            audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                   workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
            last_operation_info = Audit.logs(audit_id=audit_id).latest('id').operation_info
        except Exception as e:
            logger.debug(f'无审核日志记录，错误信息{e}')
            last_operation_info = ''
    else:
        audit_auth_group = '系统自动驳回'
        current_audit_auth_group = '系统自动驳回'
        is_can_review = False
        is_can_execute = False
        is_can_timingtask = False
        is_can_cancel = False
        last_operation_info = None

    # 获取定时执行任务信息
    if workflow_detail.status == 'workflow_timingtask':
        job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflow_id)
        job = task_info(job_id)
        if job:
            run_date = job.next_run
        else:
            run_date = ''
    else:
        run_date = ''

    #  兼容旧数据'[[]]'格式，转换为新格式[{}]
    if isinstance(json.loads(rows)[0], list):
        review_result = ReviewSet()
        for r in json.loads(rows):
            review_result.rows += [ReviewResult(inception_result=r)]
        rows = review_result.json()

    context = {'workflow_detail': workflow_detail, 'rows': rows, 'last_operation_info': last_operation_info,
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
    workflow = SqlWorkflow.objects.get(id=workflow_id)

    try:
        query_engine = get_engine(instance=workflow.instance)
        list_backup_sql = query_engine.get_rollback(workflow=workflow)
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


@permission_required('sql.menu_sqlanalyze', raise_exception=True)
def sqlanalyze(request):
    """
    SQL分析页面
    :param request:
    :return:
    """
    # 获取实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, type='all', db_type='mysql')]
    return render(request, 'sqlanalyze.html', {'instances': instances})


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
    instances = [slave for slave in user_instances(request.user, type='slave', db_type='all')]

    context = {'instances': instances}
    return render(request, 'sqlquery.html', context)


# SQL慢日志页面
@permission_required('sql.menu_slowquery', raise_exception=True)
def slowquery(request):
    # 获取用户关联实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, type='all', db_type='mysql')]

    context = {'tab': 'slowquery', 'instances': instances}
    return render(request, 'slowquery.html', context)


# SQL优化工具页面
@permission_required('sql.menu_sqladvisor', raise_exception=True)
def sqladvisor(request):
    # 获取用户关联实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, type='all', db_type='mysql')]

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
    audit_auth_group, current_audit_auth_group = Audit.review_info(apply_id, 1)

    # 是否可审核
    is_can_review = Audit.can_review(request.user, apply_id, 1)
    # 获取审核日志
    if workflow_detail.status == 2:
        try:
            audit_id = Audit.detail_by_workflow_id(workflow_id=apply_id, workflow_type=1).audit_id
            last_operation_info = Audit.logs(audit_id=audit_id).latest('id').operation_info
        except Exception as e:
            logger.debug(f'无审核日志记录，错误信息{e}')
            last_operation_info = ''
    else:
        last_operation_info = ''

    context = {'workflow_detail': workflow_detail, 'audit_auth_group': audit_auth_group,
               'last_operation_info': last_operation_info, 'current_audit_auth_group': current_audit_auth_group,
               'is_can_review': is_can_review}
    return render(request, 'queryapplydetail.html', context)


# 用户的查询权限管理页面
def queryuserprivileges(request):
    # 获取所有用户
    user_list = QueryPrivileges.objects.filter(is_deleted=0).values('user_display').distinct()
    context = {'user_list': user_list}
    return render(request, 'queryuserprivileges.html', context)


# 会话管理页面
@permission_required('sql.menu_dbdiagnostic', raise_exception=True)
def dbdiagnostic(request):
    # 获取用户关联实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, type='all', db_type='mysql')]

    context = {'tab': 'process', 'instances': instances}
    return render(request, 'dbdiagnostic.html', context)


# 工作流审核列表页面
def workflows(request):
    return render(request, "workflow.html")


# 工作流审核详情页面
def workflowsdetail(request, audit_id):
    # 按照不同的workflow_type返回不同的详情
    audit_detail = Audit.detail(audit_id)
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
    # 获取实例标签
    tags = InstanceTag.objects.filter(active=True)
    return render(request, 'instance.html', {'tags': tags})


# 实例用户管理页面
@permission_required('sql.menu_instance', raise_exception=True)
def instanceuser(request, instance_id):
    return render(request, 'instanceuser.html', {'instance_id': instance_id})


# 实例参数管理页面
@permission_required('sql.menu_param', raise_exception=True)
def instance_param(request):
    # 获取用户关联实例列表
    instances = user_instances(request.user, type='all', db_type='mysql')
    context = {'tab': 'param_tab', 'instances': instances}
    return render(request, 'param.html', context)


# binlog2sql页面
@permission_required('sql.menu_binlog2sql', raise_exception=True)
def binlog2sql(request):
    # 获取实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, type='all', db_type='mysql')]
    return render(request, 'binlog2sql.html', {'instances': instances})


# 数据库差异对比页面
@permission_required('sql.menu_schemasync', raise_exception=True)
def schemasync(request):
    # 获取实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, type='all', db_type='mysql')]
    return render(request, 'schemasync.html', {'instances': instances})
