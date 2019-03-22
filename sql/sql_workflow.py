# -*- coding: UTF-8 -*-
import datetime
import logging
import re
import traceback

import simplejson as json
import sqlparse
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from common.config import SysConfig
from common.utils.const import Const, WorkflowDict
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.notify import notify_for_audit
from sql.models import ResourceGroup, Users
from sql.utils.resource_group import user_groups, user_instances
from sql.utils.jobs import add_sqlcronjob, del_sqlcronjob
from sql.utils.sql_review import can_timingtask, can_cancel, can_execute
from sql.utils.sql_utils import get_syntax_type
from sql.utils.workflow_audit import Audit
from .models import SqlWorkflow, SqlWorkflowContent, Instance
from django_q.tasks import async_task

from sql.engines import get_engine

logger = logging.getLogger('default')


# 获取审核列表
@permission_required('sql.menu_sqlworkflow', raise_exception=True)
def sqlworkflow_list(request):
    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit
    search = request.POST.get('search', '')

    # 获取筛选参数
    navStatus = request.POST.get('navStatus')

    # 管理员可以看到全部工单，其他人能看到自己提交和审核的工单
    user = request.user

    # 全部工单里面包含搜索条件
    if navStatus == 'all':
        if user.is_superuser:
            workflow_list = SqlWorkflow.objects.filter(
                Q(engineer_display__contains=search) | Q(workflow_name__contains=search)).order_by('-create_time')
        elif user.has_perm('sql.sql_review') or user.has_perm('sql.sql_execute'):
            # 先获取用户所在资源组列表
            group_list = user_groups(user)
            group_ids = [group.group_id for group in group_list]
            workflow_list = SqlWorkflow.objects.filter(group_id__in=group_ids).filter(
                Q(engineer_display__contains=search) | Q(workflow_name__contains=search)).order_by('-create_time')
        else:
            workflow_list = SqlWorkflow.objects.filter(engineer=user.username).filter(
                workflow_name__contains=search).order_by('-create_time')
    else:
        if user.is_superuser:
            workflow_list = SqlWorkflow.objects.filter(
                status=navStatus
            ).order_by('-create_time')
        elif user.has_perm('sql.sql_review') or user.has_perm('sql.sql_execute'):
            # 先获取用户所在资源组列表
            group_list = user_groups(user)
            group_ids = [group.group_id for group in group_list]
            workflow_list = SqlWorkflow.objects.filter(status=navStatus,
                                                       group_id__in=group_ids).order_by('-create_time')
        else:
            workflow_list = SqlWorkflow.objects.filter(status=navStatus, engineer=user.username
                                                       ).order_by('-create_time')
    count = workflow_list.count()
    workflow = workflow_list[offset:limit].values("id", "workflow_name", "engineer_display", "status",
                                                  "is_backup", "create_time", "instance__instance_name", "db_name",
                                                  "group_name", "syntax_type")
    # QuerySet 序列化
    rows = [row for row in workflow]
    result = {"total": count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# SQL检测
@permission_required('sql.sql_submit', raise_exception=True)
def simplecheck(request):
    """SQL检测按钮, 此处没有产生工单"""
    sql_content = request.POST.get('sql_content')
    instance_name = request.POST.get('instance_name')
    instance = Instance.objects.get(instance_name=instance_name)
    db_name = request.POST.get('db_name')

    result = {'status': 0, 'msg': 'ok', 'data': {}}
    # 服务器端参数验证
    if sql_content is None or instance_name is None or db_name is None:
        result['status'] = 1
        result['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(result), content_type='application/json')

    for statement in sqlparse.split(sql_content):
        # 删除注释语句
        statement = sqlparse.format(statement, strip_comments=True)
        if re.match(r"^select", statement.lower()):
            result['status'] = 1
            result['msg'] = '仅支持DML和DDL语句，查询语句请使用SQL查询功能！'
            return HttpResponse(json.dumps(result), content_type='application/json')

    # 交给inception进行自动审核
    try:
        check_engine = get_engine(instance=instance)
        check_result = check_engine.execute_check(db_name=db_name, sql=sql_content.strip())
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = 'Inception审核报错，请检查Inception配置，错误信息：\n{}'.format(str(e))
        return HttpResponse(json.dumps(result), content_type='application/json')

    if not check_result:
        result['status'] = 1
        result['msg'] = 'inception返回的结果集为空！可能是SQL语句有语法错误'
        return JsonResponse(result)
    # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
    column_list = ['id', 'stage', 'errlevel', 'stagestatus', 'errormessage', 'sql', 'affected_rows', 'sequence',
                   'backup_dbname', 'execute_time', 'sqlsha1']
    check_warning_count = 0
    check_error_count = 0
    for row_item in check_result.rows:
        if row_item.errlevel == 1:
            check_warning_count = check_warning_count + 1
        elif row_item.errlevel == 2:
            check_error_count = check_error_count + 1
    result['data']['rows'] = [r.__dict__ for r in check_result.rows]
    result['data']['column_list'] = column_list
    result['data']['CheckWarningCount'] = check_warning_count
    result['data']['CheckErrorCount'] = check_error_count

    return HttpResponse(json.dumps(result), content_type='application/json')


# SQL提交
@permission_required('sql.sql_submit', raise_exception=True)
def autoreview(request):
    """正式提交SQL, 此处生成工单"""
    workflow_id = request.POST.get('workflow_id')
    sql_content = request.POST['sql_content']
    workflow_title = request.POST['workflow_name']
    # 检查用户是否有权限涉及到资源组等， 比较复杂， 可以把检查权限改成一个独立的方法
    # 工单表中可以考虑不存储资源组相关信息
    # 工单和实例关联， 实例和资源组关联， 资源组和用户关联。
    group_name = request.POST['group_name']
    group_id = ResourceGroup.objects.get(group_name=group_name).group_id
    instance_name = request.POST['instance_name']
    instance = Instance.objects.get(instance_name=instance_name)
    db_name = request.POST.get('db_name')
    is_backup = request.POST['is_backup']
    notify_users = request.POST.getlist('notify_users')
    list_cc_addr = [email['email'] for email in Users.objects.filter(username__in=notify_users).values('email')]

    # 服务器端参数验证
    if sql_content is None or workflow_title is None or instance_name is None or db_name is None or is_backup is None:
        context = {'errMsg': '页面提交参数可能为空'}
        return render(request, 'error.html', context)

    # 验证组权限（用户是否在该组、该组是否有指定实例）
    try:
        user_instances(request.user, type='master', db_type='mysql').get(instance_name=instance_name)
    except Exception:
        context = {'errMsg': '你所在组未关联该实例！'}
        return render(request, 'error.html', context)

    sql_content = sql_content.strip()

    # 审核
    try:
        check_engine = get_engine(instance)
        check_result = check_engine.execute_check(db_name=db_name, sql=sql_content)
    except Exception as msg:
        context = {'errMsg': msg}
        return render(request, 'error.html', context)

    if not check_result:
        context = {'errMsg': 'inception返回的结果集为空！可能是SQL语句有语法错误'}
        return render(request, 'error.html', context)
    # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示

    # 遍历result，看是否有任何自动审核不通过的地方，并且按配置确定是标记审核不通过还是放行，放行的可以在工单内跳过inception直接执行
    sys_config = SysConfig()
    is_manual = 0
    workflow_status = 'workflow_manreviewing'
    for row in check_result.rows:
        # 1表示警告，不影响执行
        if row.errlevel == 1 and sys_config.get('auto_review_wrong', '') == '1':
            workflow_status = 'workflow_autoreviewwrong'
            break
        # 2表示严重错误，或者inception不支持的语法，标记手工执行，可以跳过inception直接执行
        elif row.errlevel == 2:
            is_manual = 1
            if sys_config.get('auto_review_wrong', '') in ('', '1', '2'):
                workflow_status = 'workflow_autoreviewwrong'
            break
        elif re.match(r"\w*comments\w*", row.errormessage):
            is_manual = 1
            if sys_config.get('auto_review_wrong', '') in ('', '1', '2'):
                workflow_status = 'workflow_autoreviewwrong'
            break

    # 判断SQL是否包含DDL语句，SQL语法 1、DDL，2、DML
    syntax_type = 2
    for stmt in sqlparse.split(sql_content):
        if get_syntax_type(stmt) == 'DDL':
            syntax_type = 1
            break

    # 调用工作流生成工单
    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 存进数据库里
            sql_workflow = SqlWorkflow.objects.create(
                workflow_name=workflow_title,
                group_id=group_id,
                group_name=group_name,
                engineer=request.user.username,
                engineer_display=request.user.display,
                audit_auth_groups=Audit.settings(group_id, WorkflowDict.workflow_type['sqlreview']),
                status=workflow_status,
                is_backup=is_backup,
                instance=instance,
                db_name=db_name,
                is_manual=is_manual,
                audit_remark='',
                syntax_type=syntax_type,
                create_time=timezone.now()
            )
            SqlWorkflowContent.objects.create(workflow=sql_workflow,
                                              sql_content=sql_content,
                                              review_content=check_result.json(),
                                              execute_result=''
                                              )
            workflow_id = sql_workflow.id
            # 自动审核通过了，才调用工作流
            if workflow_status == 'workflow_manreviewing':
                # 调用工作流插入审核信息, 查询权限申请workflow_type=2
                Audit.add(WorkflowDict.workflow_type['sqlreview'], workflow_id)
    except Exception as msg:
        logger.error(traceback.format_exc())
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    else:
        # 自动审核通过了，才调用工作流，进行消息通知
        if workflow_status == 'workflow_manreviewing':
            # 再次获取审核信息
            audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                   workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
            async_task(notify_for_audit, audit_id=audit_id, email_cc=list_cc_addr, timeout=60)

    return HttpResponseRedirect(reverse('sql:detail', args=(workflow_id,)))


# 审核通过，不执行
@permission_required('sql.sql_review', raise_exception=True)
def passed(request):
    workflow_id = request.POST.get('workflow_id')
    if workflow_id == '' or workflow_id is None:
        context = {'errMsg': 'workflow_id参数为空.'}
        return render(request, 'error.html', context)
    workflow_id = int(workflow_id)
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    audit_remark = request.POST.get('audit_remark', '')

    user = request.user
    if Audit.can_review(request.user, workflow_id, 2) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 调用工作流接口审核
            audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                   workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
            audit_result = Audit.audit(audit_id, WorkflowDict.workflow_status['audit_success'],
                                       user.username, audit_remark)

            # 按照审核结果更新业务表审核状态
            if audit_result['data']['workflow_status'] == WorkflowDict.workflow_status['audit_success']:
                # 将流程状态修改为审核通过，并更新reviewok_time字段
                workflow_detail.status = 'workflow_review_pass'
                workflow_detail.reviewok_time = timezone.now()
                workflow_detail.audit_remark = audit_remark
                workflow_detail.save()
    except Exception as msg:
        logger.error(traceback.format_exc())
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    else:
        # 消息通知
        async_task(notify_for_audit, audit_id=audit_id, audit_remark=audit_remark, timeout=60)

    return HttpResponseRedirect(reverse('sql:detail', args=(workflow_id,)))


# 仅执行SQL
@permission_required('sql.sql_execute', raise_exception=True)
def execute(request):
    workflow_id = int(request.POST.get('workflow_id', 0))
    if workflow_id == 0:
        context = {'errMsg': 'workflow_id参数为空.'}
        return render(request, 'error.html', context)

    if can_execute(request.user, workflow_id) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    # 将流程状态修改为执行中，并更新reviewok_time字段
    SqlWorkflow(id=workflow_id,
                status='workflow_executing',
                reviewok_time=timezone.now()
                ).save(update_fields=['status', 'reviewok_time'])

    # 增加工单日志
    audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                           workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
    Audit.add_log(audit_id=audit_id,
                  operation_type=5,
                  operation_type_desc='执行工单',
                  operation_info="人工操作执行",
                  operator=request.user.username,
                  operator_display=request.user.display
                  )
    # 加入执行队列
    async_task('sql.utils.execute_sql.execute', workflow_id, hook='sql.utils.execute_sql.execute_callback',
               timeout=-1)

    return HttpResponseRedirect(reverse('sql:detail', args=(workflow_id,)))


# 定时执行SQL
@permission_required('sql.sql_execute', raise_exception=True)
def timingtask(request):
    workflow_id = request.POST.get('workflow_id')
    run_date = request.POST.get('run_date')
    if run_date is None or workflow_id is None:
        context = {'errMsg': '时间不能为空'}
        return render(request, 'error.html', context)
    elif run_date < datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
        context = {'errMsg': '时间不能小于当前时间'}
        return render(request, 'error.html', context)
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)

    if can_timingtask(request.user, workflow_id) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    run_date = datetime.datetime.strptime(run_date, "%Y-%m-%d %H:%M")
    job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflow_id)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 将流程状态修改为定时执行
            workflow_detail.status = 'workflow_timingtask'
            workflow_detail.save()
            # 调用添加定时任务
            add_sqlcronjob(job_id, run_date, workflow_id)
            # 增加工单日志
            audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                   workflow_type=WorkflowDict.workflow_type[
                                                       'sqlreview']).audit_id
            Audit.add_log(audit_id=audit_id,
                          operation_type=4,
                          operation_type_desc='定时执行',
                          operation_info="定时执行时间：{}".format(run_date),
                          operator=request.user.username,
                          operator_display=request.user.display
                          )
    except Exception as msg:
        logger.error(traceback.format_exc())
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    return HttpResponseRedirect(reverse('sql:detail', args=(workflow_id,)))


# 终止流程
def cancel(request):
    workflow_id = request.POST.get('workflow_id')
    if workflow_id == '' or workflow_id is None:
        context = {'errMsg': 'workflow_id参数为空.'}
        return render(request, 'error.html', context)

    workflow_id = int(workflow_id)
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    audit_remark = request.POST.get('cancel_remark')
    if audit_remark is None:
        context = {'errMsg': '终止原因不能为空'}
        return render(request, 'error.html', context)

    user = request.user
    if can_cancel(request.user, workflow_id) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 调用工作流接口取消或者驳回
            audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                   workflow_type=WorkflowDict.workflow_type[
                                                       'sqlreview']).audit_id
            # 仅待审核的需要调用工作流，审核通过的不需要
            if workflow_detail.status != 'workflow_manreviewing':
                # 增加工单日志
                if user.username == workflow_detail.engineer:
                    Audit.add_log(audit_id=audit_id,
                                  operation_type=3,
                                  operation_type_desc='取消执行',
                                  operation_info="取消原因：{}".format(audit_remark),
                                  operator=request.user.username,
                                  operator_display=request.user.display
                                  )
                else:
                    Audit.add_log(audit_id=audit_id,
                                  operation_type=2,
                                  operation_type_desc='审批不通过',
                                  operation_info="审批备注：{}".format(audit_remark),
                                  operator=request.user.username,
                                  operator_display=request.user.display
                                  )
            else:
                if user.username == workflow_detail.engineer:
                    Audit.audit(audit_id,
                                WorkflowDict.workflow_status['audit_abort'],
                                user.username, audit_remark)
                # 非提交人需要校验审核权限
                elif user.has_perm('sql.sql_review'):
                    Audit.audit(audit_id,
                                WorkflowDict.workflow_status['audit_reject'],
                                user.username, audit_remark)
                else:
                    raise PermissionDenied

            # 删除定时执行job
            if workflow_detail.status == 'workflow_timingtask':
                job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflow_id)
                del_sqlcronjob(job_id)
            # 将流程状态修改为人工终止流程
            workflow_detail.status = 'workflow_abort'
            workflow_detail.audit_remark = audit_remark
            workflow_detail.save()
    except Exception as msg:
        logger.error(traceback.format_exc())
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    else:
        # 仅未审核通过又取消的工单需要发送消息，审核通过的不发送
        audit_detail = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                   workflow_type=WorkflowDict.workflow_type['sqlreview'])
        if audit_detail.current_status == WorkflowDict.workflow_status['audit_abort']:
            async_task(notify_for_audit, audit_id=audit_detail.audit_id, audit_remark=audit_remark, timeout=60)
    return HttpResponseRedirect(reverse('sql:detail', args=(workflow_id,)))


def get_workflow_status(request):
    """
    获取某个工单的当前状态
    """
    workflow_id = request.POST['workflow_id']
    if workflow_id == '' or workflow_id is None:
        context = {"status": -1, 'msg': 'workflow_id参数为空.', "data": ""}
        return HttpResponse(json.dumps(context), content_type='application/json')

    workflow_id = int(workflow_id)
    workflow_detail = get_object_or_404(SqlWorkflow, pk=workflow_id)
    result = {"status": workflow_detail.status, "msg": "", "data": ""}
    return JsonResponse(result)
