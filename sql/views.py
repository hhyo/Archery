# -*- coding: UTF-8 -*-
import os
import traceback

import simplejson as json
from django.conf import settings

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, FileResponse
from django.urls import reverse

from archery import settings
from common.config import SysConfig
from sql.engines import get_engine
from common.utils.permission import superuser_required
from common.utils.convert import Convert
from sql.engines.models import ReviewResult, ReviewSet
from sql.utils.tasks import task_info

from .models import Users, SqlWorkflow, QueryPrivileges, ResourceGroup, \
    QueryPrivilegesApply, Config, SQL_WORKFLOW_CHOICES, InstanceTag, Instance, QueryLog, ArchiveConfig, AuditEntry
from sql.utils.workflow_audit import Audit
from sql.utils.sql_review import can_execute, can_timingtask, can_cancel, can_view, can_rollback
from common.utils.const import Const, WorkflowDict
from sql.utils.resource_group import user_groups, user_instances, auth_group_users

import logging

logger = logging.getLogger('default')


def index(request):
    index_path_url = SysConfig().get('index_path_url', 'sqlworkflow')
    return HttpResponseRedirect(f"/{index_path_url.strip('/')}/")


def login(request):
    """登录页面"""
    if request.user and request.user.is_authenticated:
        return HttpResponseRedirect('/')

    return render(request, 'login.html', context={'sign_up_enabled': SysConfig().get('sign_up_enabled')})


def twofa(request):
    """2fa认证页面"""
    if request.user.is_authenticated:
        return HttpResponseRedirect('/')

    username = request.session.get('user')
    if username:
        auth_type = request.session.get('auth_type')
        verify_mode = request.session.get('verify_mode')
    else:
        return HttpResponseRedirect('/login/')

    return render(request, '2fa.html', context={'verify_mode': verify_mode, 'auth_type': auth_type, 'username': username})


@permission_required('sql.menu_dashboard', raise_exception=True)
def dashboard(request):
    """dashboard页面"""
    return render(request, 'dashboard.html')


def sqlworkflow(request):
    """SQL上线工单列表页面"""
    user = request.user
    # 过滤筛选项的数据
    filter_dict = dict()
    # 管理员，可查看所有工单
    if user.is_superuser or user.has_perm('sql.audit_user'):
        pass
    # 非管理员，拥有审核权限、资源组粒度执行权限的，可以查看组内所有工单
    elif user.has_perm('sql.sql_review') or user.has_perm('sql.sql_execute_for_resource_group'):
        # 先获取用户所在资源组列表
        group_list = user_groups(user)
        group_ids = [group.group_id for group in group_list]
        filter_dict['group_id__in'] = group_ids
    # 其他人只能查看自己提交的工单
    else:
        filter_dict['engineer'] = user.username
    instance_id = SqlWorkflow.objects.filter(**filter_dict).values('instance_id').distinct()
    instance = Instance.objects.filter(pk__in=instance_id).order_by(Convert('instance_name', 'gbk').asc())
    resource_group_id = SqlWorkflow.objects.filter(**filter_dict).values('group_id').distinct()
    resource_group = ResourceGroup.objects.filter(group_id__in=resource_group_id)

    return render(request, 'sqlworkflow.html',
                  {'status_list': SQL_WORKFLOW_CHOICES,
                   'instance': instance, 'resource_group': resource_group})


@permission_required('sql.sql_submit', raise_exception=True)
def submit_sql(request):
    """提交SQL的页面"""
    user = request.user
    # 获取组信息
    group_list = user_groups(user)

    # 获取所有有效用户，通知对象
    active_user = Users.objects.filter(is_active=1)

    # 获取系统配置
    archer_config = SysConfig()

    # 主动创建标签
    InstanceTag.objects.get_or_create(tag_code='can_write', defaults={'tag_name': '支持上线', 'active': True})

    context = {'active_user': active_user, 'group_list': group_list,
               'enable_backup_switch': archer_config.get('enable_backup_switch')}
    return render(request, 'sqlsubmit.html', context)


def detail(request, workflow_id):
    """展示SQL工单详细页面"""
    workflow_detail = get_object_or_404(SqlWorkflow, pk=workflow_id)
    if not can_view(request.user, workflow_id):
        raise PermissionDenied
    # 自动审批不通过的不需要获取下列信息
    if workflow_detail.status != 'workflow_autoreviewwrong':
        # 获取当前审批和审批流程
        audit_auth_group, current_audit_auth_group = Audit.review_info(workflow_id, 2)

        # 是否可审核
        is_can_review = Audit.can_review(request.user, workflow_id, 2)
        # 是否可执行 TODO 这几个判断方法入参都修改为workflow对象，可减少多次数据库交互
        is_can_execute = can_execute(request.user, workflow_id)
        # 是否可定时执行
        is_can_timingtask = can_timingtask(request.user, workflow_id)
        # 是否可取消
        is_can_cancel = can_cancel(request.user, workflow_id)
        # 是否可查看回滚信息
        is_can_rollback = can_rollback(request.user, workflow_id)

        # 获取审核日志
        try:
            audit_detail = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                       workflow_type=WorkflowDict.workflow_type['sqlreview'])
            audit_id = audit_detail.audit_id
            last_operation_info = Audit.logs(audit_id=audit_id).latest('id').operation_info
            # 等待审批的展示当前全部审批人
            if workflow_detail.status == 'workflow_manreviewing':
                auth_group_name = Group.objects.get(id=audit_detail.current_audit).name
                current_audit_users = auth_group_users([auth_group_name], audit_detail.group_id)
                current_audit_users_display = [user.display for user in current_audit_users]
                last_operation_info += '，当前审批人：' + ','.join(current_audit_users_display)
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
        is_can_rollback = False
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

    # 获取是否开启手工执行确认
    manual = SysConfig().get('manual')

    context = {'workflow_detail': workflow_detail, 'last_operation_info': last_operation_info,
               'is_can_review': is_can_review, 'is_can_execute': is_can_execute, 'is_can_timingtask': is_can_timingtask,
               'is_can_cancel': is_can_cancel, 'is_can_rollback': is_can_rollback, 'audit_auth_group': audit_auth_group,
               'manual': manual, 'current_audit_auth_group': current_audit_auth_group, 'run_date': run_date}
    return render(request, 'detail.html', context)


def rollback(request):
    """展示回滚的SQL页面"""
    workflow_id = request.GET.get('workflow_id')
    if not can_rollback(request.user, workflow_id):
        raise PermissionDenied
    download = request.GET.get('download')
    if workflow_id == '' or workflow_id is None:
        context = {'errMsg': 'workflow_id参数为空.'}
        return render(request, 'error.html', context)
    workflow = SqlWorkflow.objects.get(id=int(workflow_id))

    # 直接下载回滚语句
    if download:
        try:
            query_engine = get_engine(instance=workflow.instance)
            list_backup_sql = query_engine.get_rollback(workflow=workflow)
        except Exception as msg:
            logger.error(traceback.format_exc())
            context = {'errMsg': msg}
            return render(request, 'error.html', context)

        # 获取数据，存入目录
        path = os.path.join(settings.BASE_DIR, 'downloads/rollback')
        os.makedirs(path, exist_ok=True)
        file_name = f'{path}/rollback_{workflow_id}.sql'
        with open(file_name, 'w') as f:
            for sql in list_backup_sql:
                f.write(f'/*{sql[0]}*/\n{sql[1]}\n')
        # 返回
        response = FileResponse(open(file_name, 'rb'))
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = f'attachment;filename="rollback_{workflow_id}.sql"'
        return response
    # 异步获取，并在页面展示，如果数据量大加载会缓慢
    else:
        rollback_workflow_name = f"【回滚工单】原工单Id:{workflow_id} ,{workflow.workflow_name}"
        context = {'workflow_detail': workflow, 'rollback_workflow_name': rollback_workflow_name}
        return render(request, 'rollback.html', context)


@permission_required('sql.menu_sqlanalyze', raise_exception=True)
def sqlanalyze(request):
    """SQL分析页面"""
    return render(request, 'sqlanalyze.html')


@permission_required('sql.menu_query', raise_exception=True)
def sqlquery(request):
    """SQL在线查询页面"""
    # 主动创建标签
    InstanceTag.objects.get_or_create(tag_code='can_read', defaults={'tag_name': '支持查询', 'active': True})
    # 收藏语句
    user = request.user
    favorites = QueryLog.objects.filter(username=user.username, favorite=True).values('id', 'alias')
    can_download = 1 if user.has_perm('sql.query_download') or user.is_superuser else 0
    return render(request, 'sqlquery.html', {'favorites': favorites, 'can_download':can_download})


@permission_required('sql.menu_queryapplylist', raise_exception=True)
def queryapplylist(request):
    """查询权限申请列表页面"""
    user = request.user
    # 获取资源组
    group_list = user_groups(user)

    context = {'group_list': group_list}
    return render(request, 'queryapplylist.html', context)


def queryapplydetail(request, apply_id):
    """查询权限申请详情页面"""
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


def queryuserprivileges(request):
    """查询权限管理页面"""
    # 获取所有用户
    user_list = QueryPrivileges.objects.filter(is_deleted=0).values('user_display').distinct()
    context = {'user_list': user_list}
    return render(request, 'queryuserprivileges.html', context)


@permission_required('sql.menu_sqladvisor', raise_exception=True)
def sqladvisor(request):
    """SQL优化工具页面"""
    return render(request, 'sqladvisor.html')


@permission_required('sql.menu_slowquery', raise_exception=True)
def slowquery(request):
    """SQL慢日志页面"""
    return render(request, 'slowquery.html')


@permission_required('sql.menu_instance', raise_exception=True)
def instance(request):
    """实例管理页面"""
    # 获取实例标签
    tags = InstanceTag.objects.filter(active=True)
    return render(request, 'instance.html', {'tags': tags})


@permission_required('sql.menu_instance_account', raise_exception=True)
def instanceaccount(request):
    """实例账号管理页面"""
    return render(request, 'instanceaccount.html')


@permission_required('sql.menu_database', raise_exception=True)
def database(request):
    """实例数据库管理页面"""
    # 获取所有有效用户，通知对象
    active_user = Users.objects.filter(is_active=1)

    return render(request, 'database.html', {"active_user": active_user})


@permission_required('sql.menu_dbdiagnostic', raise_exception=True)
def dbdiagnostic(request):
    """会话管理页面"""
    return render(request, 'dbdiagnostic.html')


@permission_required('sql.menu_data_dictionary', raise_exception=True)
def data_dictionary(request):
    """数据字典页面"""
    return render(request, 'data_dictionary.html', locals())


@permission_required('sql.menu_param', raise_exception=True)
def instance_param(request):
    """实例参数管理页面"""
    return render(request, 'param.html')


@permission_required('sql.menu_binlog2sql', raise_exception=True)
def binlog2sql(request):
    """binlog2sql页面"""
    return render(request, 'binlog2sql.html')


@permission_required('sql.menu_my2sql', raise_exception=True)
def my2sql(request):
    """my2sql页面"""
    return render(request, 'my2sql.html')


@permission_required('sql.menu_schemasync', raise_exception=True)
def schemasync(request):
    """数据库差异对比页面"""
    return render(request, 'schemasync.html')


@permission_required('sql.menu_archive', raise_exception=True)
def archive(request):
    """归档列表页面"""
    # 获取资源组
    group_list = user_groups(request.user)
    ins_list = user_instances(request.user, db_type=['mysql']).order_by(Convert('instance_name', 'gbk').asc())
    return render(request, 'archive.html', {'group_list': group_list, 'ins_list': ins_list})


def archive_detail(request, id):
    """归档详情页面"""
    archive_config = ArchiveConfig.objects.get(pk=id)
    # 获取当前审批和审批流程、是否可审核
    try:
        audit_auth_group, current_audit_auth_group = Audit.review_info(id, 3)
        is_can_review = Audit.can_review(request.user, id, 3)
    except Exception as e:
        logger.debug(f'归档配置{id}无审核信息，{e}')
        audit_auth_group, current_audit_auth_group = None, None
        is_can_review = False
    # 获取审核日志
    if archive_config.status == 2:
        try:
            audit_id = Audit.detail_by_workflow_id(workflow_id=id, workflow_type=3).audit_id
            last_operation_info = Audit.logs(audit_id=audit_id).latest('id').operation_info
        except Exception as e:
            logger.debug(f'归档配置{id}无审核日志记录，错误信息{e}')
            last_operation_info = ''
    else:
        last_operation_info = ''

    context = {'archive_config': archive_config, 'audit_auth_group': audit_auth_group,
               'last_operation_info': last_operation_info, 'current_audit_auth_group': current_audit_auth_group,
               'is_can_review': is_can_review}
    return render(request, 'archivedetail.html', context)


@superuser_required
def config(request):
    """配置管理页面"""
    # 获取所有资源组名称
    group_list = ResourceGroup.objects.all()
    # 获取所有权限组
    auth_group_list = Group.objects.all()
    # 获取所有实例标签
    instance_tags = InstanceTag.objects.all()
    # 支持自动审核的数据库类型
    db_type = ['mysql', 'oracle', 'mongo', 'clickhouse']
    # 获取所有配置项
    all_config = Config.objects.all().values('item', 'value')
    sys_config = {}
    for items in all_config:
        sys_config[items['item']] = items['value']

    context = {'group_list': group_list, 'auth_group_list': auth_group_list, 'instance_tags': instance_tags,
               'db_type': db_type, 'config': sys_config, 'WorkflowDict': WorkflowDict}
    return render(request, 'config.html', context)


@superuser_required
def group(request):
    """资源组管理页面"""
    return render(request, 'group.html')


@superuser_required
def groupmgmt(request, group_id):
    """资源组组关系管理页面"""
    group = ResourceGroup.objects.get(group_id=group_id)
    return render(request, 'groupmgmt.html', {'group': group})


def workflows(request):
    """待办列表页面"""
    return render(request, "workflow.html")


def workflowsdetail(request, audit_id):
    """待办详情"""
    # 按照不同的workflow_type返回不同的详情
    audit_detail = Audit.detail(audit_id)
    if audit_detail.workflow_type == WorkflowDict.workflow_type['query']:
        return HttpResponseRedirect(reverse('sql:queryapplydetail', args=(audit_detail.workflow_id,)))
    elif audit_detail.workflow_type == WorkflowDict.workflow_type['sqlreview']:
        return HttpResponseRedirect(reverse('sql:detail', args=(audit_detail.workflow_id,)))
    elif audit_detail.workflow_type == WorkflowDict.workflow_type['archive']:
        return HttpResponseRedirect(reverse('sql:archive_detail', args=(audit_detail.workflow_id,)))


@permission_required('sql.menu_document', raise_exception=True)
def dbaprinciples(request):
    """SQL文档页面"""
    #  读取MD文件
    file = os.path.join(settings.BASE_DIR, 'docs/docs.md')
    with open(file, 'r', encoding="utf-8") as f:
        md = f.read().replace('\n', '\\n')
    return render(request, 'dbaprinciples.html', {'md': md})


@permission_required('sql.audit_user', raise_exception=True)
def audit(request):
    """通用审计日志页面"""
    _action_types = AuditEntry.objects.values_list('action').distinct()
    action_types = [ i[0] for i in _action_types ]
    return render(request, 'audit.html', {'action_types': action_types})


@permission_required('sql.audit_user', raise_exception=True)
def audit_sqlquery(request):
    """SQL在线查询页面审计"""
    user = request.user
    favorites = QueryLog.objects.filter(username=user.username, favorite=True).values('id', 'alias')
    return render(request, 'audit_sqlquery.html', {'favorites': favorites})


def audit_sqlworkflow(request):
    """SQL上线工单列表页面"""
    user = request.user
    # 过滤筛选项的数据
    filter_dict = dict()
    # 管理员，可查看所有工单
    if user.is_superuser or user.has_perm('sql.audit_user'):
        pass
    # 非管理员，拥有审核权限、资源组粒度执行权限的，可以查看组内所有工单
    elif user.has_perm('sql.sql_review') or user.has_perm('sql.sql_execute_for_resource_group'):
        # 先获取用户所在资源组列表
        group_list = user_groups(user)
        group_ids = [group.group_id for group in group_list]
        filter_dict['group_id__in'] = group_ids
    # 其他人只能查看自己提交的工单
    else:
        filter_dict['engineer'] = user.username
    instance_id = SqlWorkflow.objects.filter(**filter_dict).values('instance_id').distinct()
    instance = Instance.objects.filter(pk__in=instance_id)
    resource_group_id = SqlWorkflow.objects.filter(**filter_dict).values('group_id').distinct()
    resource_group = ResourceGroup.objects.filter(group_id__in=resource_group_id)

    return render(request, 'audit_sqlworkflow.html',
                  {'status_list': SQL_WORKFLOW_CHOICES,
                   'instance': instance, 'resource_group': resource_group})