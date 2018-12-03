# -*- coding: UTF-8 -*-
import datetime
import logging
import re
import traceback
from threading import Thread

import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction, connection
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from common.config import SysConfig
from common.utils.const import Const, WorkflowDict
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.models import SqlGroup, Users
from sql.utils.execute_sql import execute_call_back, execute_skipinc_call_back
from sql.utils.group import user_groups, user_instances
from sql.utils.inception import InceptionDao
from sql.utils.jobs import add_sqlcronjob, del_sqlcronjob
from sql.utils.sql_review import can_timingtask, get_detail_url, can_cancel, can_execute
from sql.utils.workflow import Workflow
from .models import SqlWorkflow

logger = logging.getLogger('default')
sqlSHA1_cache = {}  # 存储SQL文本与SHA1值的对应关系，尽量减少与数据库的交互次数,提高效率。格式: {工单ID1:{SQL内容1:sqlSHA1值1, SQL内容2:sqlSHA1值2},}
workflowOb = Workflow()


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
        if user.is_superuser == 1:
            workflow_list = SqlWorkflow.objects.filter(
                Q(engineer_display__contains=search) | Q(workflow_name__contains=search)
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer_display", "status",
                                                            "is_backup", "create_time", "instance_name", "db_name",
                                                            "group_name", "sql_syntax")
            count = SqlWorkflow.objects.filter(
                Q(engineer_display__contains=search) | Q(workflow_name__contains=search)).count()
        elif user.has_perm('sql.sql_review') or user.has_perm('sql.sql_execute'):
            # 先获取用户所在资源组列表
            group_list = user_groups(user)
            group_ids = [group.group_id for group in group_list]
            workflow_list = SqlWorkflow.objects.filter(group_id__in=group_ids).filter(
                Q(engineer_display__contains=search) | Q(workflow_name__contains=search)
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer_display", "status",
                                                            "is_backup", "create_time", "instance_name", "db_name",
                                                            "group_name", "sql_syntax")
            count = SqlWorkflow.objects.filter(group_id__in=group_ids).filter(
                Q(engineer_display__contains=search) | Q(workflow_name__contains=search)
            ).count()
        else:
            workflow_list = SqlWorkflow.objects.filter(engineer=user.username).filter(
                workflow_name__contains=search
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer_display", "status",
                                                            "is_backup", "create_time", "instance_name", "db_name",
                                                            "group_name", "sql_syntax")
            count = SqlWorkflow.objects.filter(engineer=user.username).filter(
                workflow_name__contains=search).count()
    elif navStatus in Const.workflowStatus.keys():
        if user.is_superuser == 1:
            workflow_list = SqlWorkflow.objects.filter(
                status=Const.workflowStatus[navStatus]
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer_display", "status",
                                                            "is_backup", "create_time", "instance_name", "db_name",
                                                            "group_name", "sql_syntax")
            count = SqlWorkflow.objects.filter(status=Const.workflowStatus[navStatus]).count()
        elif user.has_perm('sql.sql_review') or user.has_perm('sql.sql_execute'):
            # 先获取用户所在资源组列表
            group_list = user_groups(user)
            group_ids = [group.group_id for group in group_list]
            workflow_list = SqlWorkflow.objects.filter(status=Const.workflowStatus[navStatus], group_id__in=group_ids
                                                       ).order_by('-create_time')[offset:limit].values("id",
                                                                                                       "workflow_name",
                                                                                                       "engineer_display",
                                                                                                       "status",
                                                                                                       "is_backup",
                                                                                                       "create_time",
                                                                                                       "instance_name",
                                                                                                       "db_name",
                                                                                                       "group_name",
                                                                                                       "sql_syntax")
            count = SqlWorkflow.objects.filter(status=Const.workflowStatus[navStatus], group_id__in=group_ids).count()
        else:
            workflow_list = SqlWorkflow.objects.filter(status=Const.workflowStatus[navStatus], engineer=user.username
                                                       ).order_by('-create_time')[offset:limit].values("id",
                                                                                                       "workflow_name",
                                                                                                       "engineer_display",
                                                                                                       "status",
                                                                                                       "is_backup",
                                                                                                       "create_time",
                                                                                                       "instance_name",
                                                                                                       "db_name",
                                                                                                       "group_name",
                                                                                                       "sql_syntax")
            count = SqlWorkflow.objects.filter(status=Const.workflowStatus[navStatus], engineer=user.username).count()
    else:
        context = {'errMsg': '传入的navStatus参数有误！'}
        return render(request, 'error.html', context)

    # QuerySet 序列化
    rows = [row for row in workflow_list]

    result = {"total": count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# SQL检测
@permission_required('sql.sql_submit', raise_exception=True)
def simplecheck(request):
    sql_content = request.POST.get('sql_content')
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')

    result = {'status': 0, 'msg': 'ok', 'data': {}}
    # 服务器端参数验证
    if sql_content is None or instance_name is None or db_name is None:
        result['status'] = 1
        result['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # # 删除注释语句
    # sql_content = ''.join(
    #     map(lambda x: re.compile(r'(^--.*|^/\*.*\*/;\s*$)').sub('', x, count=1),
    #         sql_content.splitlines(1))).strip()
    # # 去除空行
    # sql_content = re.sub('[\r\n\f]{2,}', '\n', sql_content)

    sql_content = sql_content.strip()

    # 交给inception进行自动审核
    try:
        inception_result = InceptionDao(instance_name=instance_name).sqlauto_review(sql_content, db_name)
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = 'Inception审核报错，请检查Inception配置，错误信息：\n{}'.format(str(e))
        return HttpResponse(json.dumps(result), content_type='application/json')

    if inception_result is None or len(inception_result) == 0:
        result['status'] = 1
        result['msg'] = 'inception返回的结果集为空！可能是SQL语句有语法错误'
        return HttpResponse(json.dumps(result), content_type='application/json')
    # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
    column_list = ['ID', 'stage', 'errlevel', 'stagestatus', 'errormessage', 'SQL', 'Affected_rows', 'sequence',
                   'backup_dbname', 'execute_time', 'sqlsha1']
    rows = []
    check_warning_count = 0
    check_error_count = 0
    for row_index, row_item in enumerate(inception_result):
        row = {}
        row['ID'] = row_item[0]
        row['stage'] = row_item[1]
        row['errlevel'] = row_item[2]
        if row['errlevel'] == 1:
            check_warning_count = check_warning_count + 1
        elif row['errlevel'] == 2:
            check_error_count = check_error_count + 1
        row['stagestatus'] = row_item[3]
        row['errormessage'] = row_item[4]
        row['SQL'] = row_item[5]
        row['Affected_rows'] = row_item[6]
        row['sequence'] = row_item[7]
        row['backup_dbname'] = row_item[8]
        row['execute_time'] = row_item[9]
        # row['sqlsha1'] = row_item[10]
        rows.append(row)
    result['data']['rows'] = rows
    result['data']['column_list'] = column_list
    result['data']['CheckWarningCount'] = check_warning_count
    result['data']['CheckErrorCount'] = check_error_count

    return HttpResponse(json.dumps(result), content_type='application/json')


# SQL提交
@permission_required('sql.sql_submit', raise_exception=True)
def autoreview(request):
    workflow_id = request.POST.get('workflow_id')
    sql_content = request.POST['sql_content']
    workflow_title = request.POST['workflow_name']
    group_name = request.POST['group_name']
    group_id = SqlGroup.objects.get(group_name=group_name).group_id
    instance_name = request.POST['instance_name']
    db_name = request.POST.get('db_name')
    is_backup = request.POST['is_backup']
    notify_users = request.POST.getlist('notify_users')

    # 服务器端参数验证
    if sql_content is None or workflow_title is None or instance_name is None or db_name is None or is_backup is None:
        context = {'errMsg': '页面提交参数可能为空'}
        return render(request, 'error.html', context)

    # 验证组权限（用户是否在该组、该组是否有指定实例）
    try:
        user_instances(request.user, 'master').get(instance_name=instance_name)
    except Exception:
        context = {'errMsg': '你所在组未关联该实例！'}
        return render(request, 'error.html', context)

    # # 删除注释语句
    # sql_content = ''.join(
    #     map(lambda x: re.compile(r'(^--.*|^/\*.*\*/;\s*$)').sub('', x, count=1),
    #         sql_content.splitlines(1))).strip()
    # # 去除空行
    # sql_content = re.sub('[\r\n\f]{2,}', '\n', sql_content)

    sql_content = sql_content.strip()

    if sql_content[-1] != ";":
        context = {'errMsg': "SQL语句结尾没有以;结尾，请后退重新修改并提交！"}
        return render(request, 'error.html', context)

    # 交给inception进行自动审核
    try:
        inception_result = InceptionDao(instance_name=instance_name).sqlauto_review(sql_content, db_name)
    except Exception as msg:
        context = {'errMsg': msg}
        return render(request, 'error.html', context)

    if inception_result is None or len(inception_result) == 0:
        context = {'errMsg': 'inception返回的结果集为空！可能是SQL语句有语法错误'}
        return render(request, 'error.html', context)
    # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
    json_result = json.dumps(inception_result)

    # 遍历result，看是否有任何自动审核不通过的地方，并且按配置确定是标记审核不通过还是放行，放行的可以在工单内跳过inception直接执行
    sys_config = SysConfig().sys_config
    is_manual = 0
    workflow_status = Const.workflowStatus['manreviewing']
    for row in inception_result:
        # 1表示警告，不影响执行
        if row[2] == 1 and sys_config.get('auto_review_wrong', '') == '1':
            workflow_status = Const.workflowStatus['autoreviewwrong']
            break
        # 2表示严重错误，或者inception不支持的语法，标记手工执行，可以跳过inception直接执行
        elif row[2] == 2:
            is_manual = 1
            if sys_config.get('auto_review_wrong', '') in ('', '1', '2'):
                workflow_status = Const.workflowStatus['autoreviewwrong']
            break
        elif re.match(r"\w*comments\w*", row[4]):
            is_manual = 1
            if sys_config.get('auto_review_wrong', '') in ('', '1', '2'):
                workflow_status = Const.workflowStatus['autoreviewwrong']
            break

    # 判断SQL是否包含DDL语句，SQL语法 1、DDL，2、DML
    sql_syntax = 2
    for row in sql_content.strip(';').split(';'):
        if re.match(r"^alter|^create|^drop|^truncate|^rename", row.strip().lower()):
            sql_syntax = 1
            break

    # 调用工作流生成工单
    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 存进数据库里
            engineer = request.user.username
            if not workflow_id:
                sql_workflow = SqlWorkflow()
                sql_workflow.create_time = timezone.now()
            else:
                sql_workflow = SqlWorkflow.objects.get(id=int(workflow_id))
            sql_workflow.workflow_name = workflow_title
            sql_workflow.group_id = group_id
            sql_workflow.group_name = group_name
            sql_workflow.engineer = engineer
            sql_workflow.engineer_display = request.user.display
            sql_workflow.audit_auth_groups = Workflow.audit_settings(group_id, WorkflowDict.workflow_type['sqlreview'])
            sql_workflow.status = workflow_status
            sql_workflow.is_backup = is_backup
            sql_workflow.review_content = json_result
            sql_workflow.instance_name = instance_name
            sql_workflow.db_name = db_name
            sql_workflow.sql_content = sql_content
            sql_workflow.execute_result = ''
            sql_workflow.is_manual = is_manual
            sql_workflow.audit_remark = ''
            sql_workflow.sql_syntax = sql_syntax
            sql_workflow.save()
            workflow_id = sql_workflow.id
            # 自动审核通过了，才调用工作流
            if workflow_status == Const.workflowStatus['manreviewing']:
                # 调用工作流插入审核信息, 查询权限申请workflow_type=2
                # 抄送通知人
                list_cc_addr = [email['email'] for email in
                                Users.objects.filter(username__in=notify_users).values('email')]
                workflowOb.addworkflowaudit(request, WorkflowDict.workflow_type['sqlreview'], workflow_id,
                                            list_cc_addr=list_cc_addr)
    except Exception as msg:
        logger.error(traceback.format_exc())
        context = {'errMsg': msg}
        return render(request, 'error.html', context)

    return HttpResponseRedirect(reverse('sql:detail', args=(workflow_id,)))


# 审核通过，不执行
@permission_required('sql.sql_review', raise_exception=True)
def passed(request):
    workflow_id = request.POST['workflow_id']
    if workflow_id == '' or workflow_id is None:
        context = {'errMsg': 'workflow_id参数为空.'}
        return render(request, 'error.html', context)
    workflow_id = int(workflow_id)
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    audit_remark = request.POST.get('audit_remark', '')

    user = request.user
    if Workflow.can_review(request.user, workflow_id, 2) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 调用工作流接口审核
            # 获取audit_id
            audit_id = Workflow.audit_info_by_workflow_id(workflow_id=workflow_id,
                                                          workflow_type=WorkflowDict.workflow_type[
                                                              'sqlreview']).audit_id
            audit_result = workflowOb.auditworkflow(request, audit_id, WorkflowDict.workflow_status['audit_success'],
                                                    user.username, audit_remark)

            # 按照审核结果更新业务表审核状态
            if audit_result['data']['workflow_status'] == WorkflowDict.workflow_status['audit_success']:
                # 将流程状态修改为审核通过，并更新reviewok_time字段
                workflow_detail.status = Const.workflowStatus['pass']
                workflow_detail.reviewok_time = timezone.now()
                workflow_detail.audit_remark = audit_remark
                workflow_detail.save()
    except Exception as msg:
        logger.error(traceback.format_exc())
        context = {'errMsg': msg}
        return render(request, 'error.html', context)

    return HttpResponseRedirect(reverse('sql:detail', args=(workflow_id,)))


# 仅执行SQL
@permission_required('sql.sql_execute', raise_exception=True)
def execute(request):
    workflow_id = request.POST['workflow_id']
    if workflow_id == '' or workflow_id is None:
        context = {'errMsg': 'workflow_id参数为空.'}
        return render(request, 'error.html', context)

    workflow_id = int(workflow_id)
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    instance_name = workflow_detail.instance_name
    db_name = workflow_detail.db_name
    url = get_detail_url(request, workflow_id)

    if can_execute(request.user, workflow_id) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    # 判断是否高危SQL，禁止执行
    if SysConfig().sys_config.get('critical_ddl_regex', '') != '':
        if InceptionDao().critical_ddl(workflow_detail.sql_content):
            context = {'errMsg': '高危语句，禁止执行！'}
            return render(request, 'error.html', context)

    # 将流程状态修改为执行中，并更新reviewok_time字段
    workflow_detail.status = Const.workflowStatus['executing']
    workflow_detail.reviewok_time = timezone.now()
    workflow_detail.save()

    # 判断是通过inception执行还是直接执行，is_manual=0则通过inception执行，is_manual=1代表inception审核不通过，需要直接执行
    if workflow_detail.is_manual == 0:
        # 执行之前重新split并check一遍，更新SHA1缓存；因为如果在执行中，其他进程去做这一步操作的话，会导致inception core dump挂掉
        try:
            split_review_result = InceptionDao(instance_name=instance_name).sqlauto_review(workflow_detail.sql_content,
                                                                                           db_name,
                                                                                           is_split='yes')
        except Exception as msg:
            logger.error(traceback.format_exc())
            context = {'errMsg': msg}
            return render(request, 'error.html', context)
        workflow_detail.review_content = json.dumps(split_review_result)
        try:
            workflow_detail.save()
        except Exception:
            # 关闭后重新获取连接，防止超时
            connection.close()
            workflow_detail.save()

        # 采取异步回调的方式执行语句，防止出现持续执行中的异常
        t = Thread(target=execute_call_back, args=(workflow_id, instance_name, url))
        t.start()
    else:
        # 采取异步回调的方式执行语句，防止出现持续执行中的异常
        t = Thread(target=execute_skipinc_call_back,
                   args=(workflow_id, instance_name, db_name, workflow_detail.sql_content, url))
        t.start()
    # 删除定时执行job
    if workflow_detail.status == Const.workflowStatus['timingtask']:
        job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflow_id)
        del_sqlcronjob(job_id)
    # 增加工单日志
    # 获取audit_id
    audit_id = Workflow.audit_info_by_workflow_id(workflow_id=workflow_id,
                                                  workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
    workflowOb.add_workflow_log(audit_id=audit_id,
                                operation_type=5,
                                operation_type_desc='执行工单',
                                operation_info="人工操作执行",
                                operator=request.user.username,
                                operator_display=request.user.display
                                )
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

    # 判断是否高危SQL，禁止执行
    if SysConfig().sys_config.get('critical_ddl_regex', '') != '':
        if InceptionDao().critical_ddl(workflow_detail.sql_content):
            context = {'errMsg': '高危语句，禁止执行！'}
            return render(request, 'error.html', context)

    run_date = datetime.datetime.strptime(run_date, "%Y-%m-%d %H:%M:%S")
    url = get_detail_url(request, workflow_id)
    job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflow_id)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 将流程状态修改为定时执行
            workflow_detail.status = Const.workflowStatus['timingtask']
            workflow_detail.save()
            # 调用添加定时任务
            add_sqlcronjob(job_id, run_date, workflow_id, url)
            # 增加工单日志
            # 获取audit_id
            audit_id = Workflow.audit_info_by_workflow_id(workflow_id=workflow_id,
                                                          workflow_type=WorkflowDict.workflow_type[
                                                              'sqlreview']).audit_id
            workflowOb.add_workflow_log(audit_id=audit_id,
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
    workflow_id = request.POST['workflow_id']
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
            # 获取audit_id
            audit_id = Workflow.audit_info_by_workflow_id(workflow_id=workflow_id,
                                                          workflow_type=WorkflowDict.workflow_type[
                                                              'sqlreview']).audit_id
            # 仅待审核的需要调用工作流，审核通过的不需要
            if workflow_detail.status != Const.workflowStatus['manreviewing']:
                # 增加工单日志
                if user.username == workflow_detail.engineer:
                    workflowOb.add_workflow_log(audit_id=audit_id,
                                                operation_type=3,
                                                operation_type_desc='取消执行',
                                                operation_info="取消原因：{}".format(audit_remark),
                                                operator=request.user.username,
                                                operator_display=request.user.display
                                                )
                else:
                    workflowOb.add_workflow_log(audit_id=audit_id,
                                                operation_type=2,
                                                operation_type_desc='审批不通过',
                                                operation_info="审批备注：{}".format(audit_remark),
                                                operator=request.user.username,
                                                operator_display=request.user.display
                                                )
            else:
                if user.username == workflow_detail.engineer:
                    workflowOb.auditworkflow(request, audit_id,
                                             WorkflowDict.workflow_status['audit_abort'],
                                             user.username, audit_remark)
                # 非提交人需要校验审核权限
                elif user.has_perm('sql.sql_review'):
                    workflowOb.auditworkflow(request, audit_id,
                                             WorkflowDict.workflow_status['audit_reject'],
                                             user.username, audit_remark)
                else:
                    raise PermissionDenied

            # 删除定时执行job
            if workflow_detail.status == Const.workflowStatus['timingtask']:
                job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflow_id)
                del_sqlcronjob(job_id)
            # 将流程状态修改为人工终止流程
            workflow_detail.status = Const.workflowStatus['abort']
            workflow_detail.audit_remark = audit_remark
            workflow_detail.save()
    except Exception as msg:
        logger.error(traceback.format_exc())
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    return HttpResponseRedirect(reverse('sql:detail', args=(workflow_id,)))


def get_sql_sha1(workflow_id):
    """
    调用django ORM从数据库里查出review_content，从其中获取sqlSHA1值
    """
    workflow_detail = get_object_or_404(SqlWorkflow, pk=workflow_id)
    dict_sha1 = {}
    # 使用json.loads方法，把review_content从str转成list,
    list_re_check_result = json.loads(workflow_detail.review_content)

    for rownum in range(len(list_re_check_result)):
        id = rownum + 1
        sql_sha1 = list_re_check_result[rownum][10]
        if sql_sha1 != '':
            dict_sha1[id] = sql_sha1

    if dict_sha1 != {}:
        # 如果找到有sqlSHA1值，说明是通过pt-OSC操作的，将其放入缓存。
        # 因为使用OSC执行的SQL占较少数，所以不设置缓存过期时间
        sqlSHA1_cache[workflow_id] = dict_sha1
    return dict_sha1


def get_osc_percent(request):
    """
    获取该SQL的pt-OSC执行进度和剩余时间
    """
    workflow_id = request.POST['workflow_id']
    sql_id = request.POST['sqlID']
    if workflow_id == '' or workflow_id is None or sql_id == '' or sql_id is None:
        context = {"status": -1, 'msg': 'workflow_id或sqlID参数为空.', "data": ""}
        return HttpResponse(json.dumps(context), content_type='application/json')

    workflow_id = int(workflow_id)
    sql_id = int(sql_id)
    dict_sha1 = {}
    if workflow_id in sqlSHA1_cache:
        dict_sha1 = sqlSHA1_cache[workflow_id]
        # cachehit = "已命中"
    else:
        dict_sha1 = get_sql_sha1(workflow_id)

    if dict_sha1 != {} and sql_id in dict_sha1:
        sql_sha1 = dict_sha1[sql_id]
        try:
            result = InceptionDao().get_osc_percent(sql_sha1)  # 成功获取到SHA1值，去inception里面查询进度
        except Exception as msg:
            logger.error(traceback.format_exc())
            result = {'status': 1, 'msg': msg, 'data': ''}
            return HttpResponse(json.dumps(result), content_type='application/json')

        if result["status"] == 0:
            # 获取到进度值
            pct_result = result
        else:
            # result["status"] == 1, 未获取到进度值,需要与workflow.execute_result对比，来判断是已经执行过了，还是还未执行
            execute_result = SqlWorkflow.objects.get(id=workflow_id).execute_result
            try:
                list_exec_result = json.loads(execute_result)
            except ValueError:
                list_exec_result = execute_result
            if type(list_exec_result) == list and len(list_exec_result) >= sql_id - 1:
                if dict_sha1[sql_id] in list_exec_result[sql_id - 1][10]:
                    # 已经执行完毕，进度值置为100
                    pct_result = {"status": 0, "msg": "ok", "data": {"percent": 100, "timeRemained": ""}}
            else:
                # 可能因为前一条SQL是DML，正在执行中；或者还没执行到这一行。但是status返回的是4，而当前SQL实际上还未开始执行。这里建议前端进行重试
                pct_result = {"status": -3, "msg": "进度未知", "data": {"percent": -100, "timeRemained": ""}}
    elif dict_sha1 != {} and sql_id not in dict_sha1:
        pct_result = {"status": 4, "msg": "该行SQL不是由pt-OSC执行的", "data": ""}
    else:
        pct_result = {"status": -2, "msg": "整个工单不由pt-OSC执行", "data": ""}
    return HttpResponse(json.dumps(pct_result), content_type='application/json')


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
    workflow_status = workflow_detail.status
    result = {"status": workflow_status, "msg": "", "data": ""}
    return HttpResponse(json.dumps(result), content_type='application/json')


def stop_osc_progress(request):
    """
    中止该SQL的pt-OSC进程
    """
    workflow_id = request.POST['workflow_id']
    sql_id = request.POST['sqlID']
    if workflow_id == '' or workflow_id is None or sql_id == '' or sql_id is None:
        context = {"status": -1, 'msg': 'workflow_id或sqlID参数为空.', "data": ""}
        return HttpResponse(json.dumps(context), content_type='application/json')

    user = request.user
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    try:
        review_man = json.loads(workflow_detail.audit_auth_groups)
    except ValueError:
        review_man = (workflow_detail.audit_auth_groups,)
    # 服务器端二次验证，当前工单状态必须为等待人工审核,正在执行人工审核动作的当前登录用户必须为审核人. 避免攻击或被接口测试工具强行绕过
    if workflow_detail.status != Const.workflowStatus['executing']:
        context = {"status": -1, "msg": '当前工单状态不是"执行中"，请刷新当前页面！', "data": ""}
        return HttpResponse(json.dumps(context), content_type='application/json')
    if user.username is None or user.username not in review_man:
        context = {"status": -1, 'msg': '当前登录用户不是审核人，请重新登录.', "data": ""}
        return HttpResponse(json.dumps(context), content_type='application/json')

    workflow_id = int(workflow_id)
    sql_id = int(sql_id)
    if workflow_id in sqlSHA1_cache:
        dict_sha1 = sqlSHA1_cache[workflow_id]
    else:
        dict_sha1 = get_sql_sha1(workflow_id)
    if dict_sha1 != {} and sql_id in dict_sha1:
        sql_sha1 = dict_sha1[sql_id]
        try:
            opt_result = InceptionDao().stop_osc_progress(sql_sha1)
        except Exception as msg:
            logger.error(traceback.format_exc())
            result = {'status': 1, 'msg': msg, 'data': ''}
            return HttpResponse(json.dumps(result), content_type='application/json')
    else:
        opt_result = {"status": 4, "msg": "不是由pt-OSC执行的", "data": ""}
    return HttpResponse(json.dumps(opt_result), content_type='application/json')
