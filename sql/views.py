# -*- coding: UTF-8 -*-
import os
import traceback

import simplejson as json
from django.conf import settings

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
    QueryPrivilegesApply, Config, SQL_WORKFLOW_CHOICES, InstanceTag, Instance
from sql.utils.workflow_audit import Audit
from sql.utils.sql_review import can_execute, can_timingtask, can_cancel
from common.utils.const import Const, WorkflowDict
from sql.utils.resource_group import user_groups

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
    if user.is_superuser:
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
    if workflow_detail.status in ['workflow_finish', 'workflow_exception']:
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

    # 获取是否开启手工执行确认
    manual = SysConfig().get('manual')

    review_result = ReviewSet()
    if rows:
        try:
            # 检验rows能不能正常解析
            loaded_rows = json.loads(rows)
            #  兼容旧数据'[[]]'格式，转换为新格式[{}]
            if isinstance(loaded_rows[-1], list):
                for r in loaded_rows:
                    review_result.rows += [ReviewResult(inception_result=r)]
                rows = review_result.json()
        except IndexError:
            review_result.rows += [ReviewResult(
                errormessage="Json decode failed."
                             "执行结果Json解析失败, 请联系管理员"
            )]
            rows = review_result.json()
        except json.decoder.JSONDecodeError:
            review_result.rows += [ReviewResult(
                # 迫于无法单元测试这里加上英文报错信息
                errormessage="Json decode failed."
                             "执行结果Json解析失败, 请联系管理员"
            )]
            rows = review_result.json()
    else:
        rows = workflow_detail.sqlworkflowcontent.review_content

    context = {'workflow_detail': workflow_detail, 'rows': rows, 'last_operation_info': last_operation_info,
               'is_can_review': is_can_review, 'is_can_execute': is_can_execute, 'is_can_timingtask': is_can_timingtask,
               'is_can_cancel': is_can_cancel, 'audit_auth_group': audit_auth_group, 'manual': manual,
               'current_audit_auth_group': current_audit_auth_group, 'run_date': run_date}
    return render(request, 'detail.html', context)


def rollback(request):
    """展示回滚的SQL页面"""
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
    """SQL分析页面"""
    return render(request, 'sqlanalyze.html')


@permission_required('sql.menu_query', raise_exception=True)
def sqlquery(request):
    """SQL在线查询页面"""
    # 主动创建标签
    InstanceTag.objects.get_or_create(tag_code='can_read', defaults={'tag_name': '支持查询', 'active': True})
    return render(request, 'sqlquery.html')


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


@permission_required('sql.menu_instance', raise_exception=True)
def instanceuser(request, instance_id):
    """实例用户管理页面"""
    return render(request, 'instanceuser.html', {'instance_id': instance_id})


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


@permission_required('sql.menu_schemasync', raise_exception=True)
def schemasync(request):
    """数据库差异对比页面"""
    return render(request, 'schemasync.html')


@superuser_required
def config(request):
    """配置管理页面"""
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


@permission_required('sql.menu_document', raise_exception=True)
def dbaprinciples(request):
    """SQL文档页面"""
    #  读取MD文件
    file = os.path.join(settings.BASE_DIR, 'docs/mysql_db_design_guide.md')
    with open(file, 'r') as f:
        md = f.read().replace('\n', '\\n')
    return render(request, 'dbaprinciples.html', {'md': md})
