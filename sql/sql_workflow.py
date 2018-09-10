# -*- coding: UTF-8 -*-
import datetime
import re
from threading import Thread

import simplejson as json

from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction, connection
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from sql.models import SqlGroup, Users
from sql.utils.execute_sql import execute_call_back, execute_skipinc_call_back
from sql.utils.group import user_groups, user_instances
from common.utils.const import Const, WorkflowDict
from sql.utils.inception import InceptionDao
from common.utils.aes_decryptor import Prpcrypt
from sql.utils.jobs import add_sqlcronjob, del_sqlcronjob
from sql.utils.sql_review import can_timingtask, getDetailUrl, can_cancel, can_execute
from .models import SqlWorkflow
import logging
from sql.utils.workflow import Workflow
from common.utils.extend_json_encoder import ExtendJSONEncoder

logger = logging.getLogger('default')
prpCryptor = Prpcrypt()
login_failure_counter = {}  # 登录失败锁定计数器，给loginAuthenticate用的
sqlSHA1_cache = {}  # 存储SQL文本与SHA1值的对应关系，尽量减少与数据库的交互次数,提高效率。格式: {工单ID1:{SQL内容1:sqlSHA1值1, SQL内容2:sqlSHA1值2},}
workflowOb = Workflow()


# 获取审核列表
@permission_required('sql.menu_sqlworkflow', raise_exception=True)
def sqlworkflowlist(request):
    # 获取用户信息
    user = request.user

    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit

    # 获取搜索参数
    search = request.POST.get('search')
    if search is None:
        search = ''

    # 获取筛选参数
    navStatus = request.POST.get('navStatus')

    # 管理员可以看到全部工单，其他人能看到自己提交和审核的工单
    user = request.user

    # 全部工单里面包含搜索条件
    if navStatus == 'all':
        if user.is_superuser == 1:
            workflowlist = SqlWorkflow.objects.filter(
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
            workflowlist = SqlWorkflow.objects.filter(group_id__in=group_ids).filter(
                Q(engineer_display__contains=search) | Q(workflow_name__contains=search)
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer_display", "status",
                                                            "is_backup", "create_time", "instance_name", "db_name",
                                                            "group_name", "sql_syntax")
            count = SqlWorkflow.objects.filter(group_id__in=group_ids).filter(
                Q(engineer_display__contains=search) | Q(workflow_name__contains=search)
            ).count()
        else:
            workflowlist = SqlWorkflow.objects.filter(engineer=user.username).filter(
                workflow_name__contains=search
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer_display", "status",
                                                            "is_backup", "create_time", "instance_name", "db_name",
                                                            "group_name", "sql_syntax")
            count = SqlWorkflow.objects.filter(engineer=user.username).filter(
                workflow_name__contains=search).count()
    elif navStatus in Const.workflowStatus.keys():
        if user.is_superuser == 1:
            workflowlist = SqlWorkflow.objects.filter(
                status=Const.workflowStatus[navStatus]
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer_display", "status",
                                                            "is_backup", "create_time", "instance_name", "db_name",
                                                            "group_name", "sql_syntax")
            count = SqlWorkflow.objects.filter(status=Const.workflowStatus[navStatus]).count()
        elif user.has_perm('sql.sql_review') or user.has_perm('sql.sql_execute'):
            # 先获取用户所在资源组列表
            group_list = user_groups(user)
            group_ids = [group.group_id for group in group_list]
            workflowlist = SqlWorkflow.objects.filter(status=Const.workflowStatus[navStatus], group_id__in=group_ids
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
            workflowlist = SqlWorkflow.objects.filter(status=Const.workflowStatus[navStatus], engineer=user.username
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
    rows = [row for row in workflowlist]

    result = {"total": count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 提交SQL给inception进行自动审核
@permission_required('sql.sql_submit', raise_exception=True)
def simplecheck(request):
    sqlContent = request.POST.get('sql_content')
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')

    finalResult = {'status': 0, 'msg': 'ok', 'data': {}}
    # 服务器端参数验证
    if sqlContent is None or instance_name is None or db_name is None:
        finalResult['status'] = 1
        finalResult['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')

    # # 删除注释语句
    # sqlContent = ''.join(
    #     map(lambda x: re.compile(r'(^--.*|^/\*.*\*/;\s*$)').sub('', x, count=1),
    #         sqlContent.splitlines(1))).strip()
    # # 去除空行
    # sqlContent = re.sub('[\r\n\f]{2,}', '\n', sqlContent)

    sqlContent = sqlContent.strip()

    if sqlContent[-1] != ";":
        finalResult['status'] = 1
        finalResult['msg'] = 'SQL语句结尾没有以;结尾，请重新修改并提交！'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')

    # 交给inception进行自动审核
    try:
        result = InceptionDao().sqlautoReview(sqlContent, instance_name, db_name)
    except Exception as e:
        finalResult['status'] = 1
        finalResult['msg'] = str(e)
        return HttpResponse(json.dumps(finalResult), content_type='application/json')

    if result is None or len(result) == 0:
        finalResult['status'] = 1
        finalResult['msg'] = 'inception返回的结果集为空！可能是SQL语句有语法错误'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')
    # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
    column_list = ['ID', 'stage', 'errlevel', 'stagestatus', 'errormessage', 'SQL', 'Affected_rows', 'sequence',
                   'backup_dbname', 'execute_time', 'sqlsha1']
    rows = []
    CheckWarningCount = 0
    CheckErrorCount = 0
    for row_index, row_item in enumerate(result):
        row = {}
        row['ID'] = row_item[0]
        row['stage'] = row_item[1]
        row['errlevel'] = row_item[2]
        if row['errlevel'] == 1:
            CheckWarningCount = CheckWarningCount + 1
        elif row['errlevel'] == 2:
            CheckErrorCount = CheckErrorCount + 1
        row['stagestatus'] = row_item[3]
        row['errormessage'] = row_item[4]
        row['SQL'] = row_item[5]
        row['Affected_rows'] = row_item[6]
        row['sequence'] = row_item[7]
        row['backup_dbname'] = row_item[8]
        row['execute_time'] = row_item[9]
        # row['sqlsha1'] = row_item[10]
        rows.append(row)
    finalResult['data']['rows'] = rows
    finalResult['data']['column_list'] = column_list
    finalResult['data']['CheckWarningCount'] = CheckWarningCount
    finalResult['data']['CheckErrorCount'] = CheckErrorCount

    return HttpResponse(json.dumps(finalResult), content_type='application/json')


# 提交SQL给inception进行解析
@permission_required('sql.sql_submit', raise_exception=True)
def autoreview(request):
    workflowid = request.POST.get('workflowid')
    sqlContent = request.POST['sql_content']
    workflowName = request.POST['workflow_name']
    group_name = request.POST['group_name']
    group_id = SqlGroup.objects.get(group_name=group_name).group_id
    instance_name = request.POST['instance_name']
    db_name = request.POST.get('db_name')
    isBackup = request.POST['is_backup']
    notify_users = request.POST.getlist('notify_users')

    # 服务器端参数验证
    if sqlContent is None or workflowName is None or instance_name is None or db_name is None or isBackup is None:
        context = {'errMsg': '页面提交参数可能为空'}
        return render(request, 'error.html', context)

    # 验证组权限（用户是否在该组、该组是否有指定实例）
    try:
        user_instances(request.user, 'master').get(instance_name=instance_name)
    except Exception:
        context = {'errMsg': '你所在组未关联该主库！'}
        return render(request, 'error.html', context)

    # # 删除注释语句
    # sqlContent = ''.join(
    #     map(lambda x: re.compile(r'(^--.*|^/\*.*\*/;\s*$)').sub('', x, count=1),
    #         sqlContent.splitlines(1))).strip()
    # # 去除空行
    # sqlContent = re.sub('[\r\n\f]{2,}', '\n', sqlContent)

    sqlContent = sqlContent.strip()

    if sqlContent[-1] != ";":
        context = {'errMsg': "SQL语句结尾没有以;结尾，请后退重新修改并提交！"}
        return render(request, 'error.html', context)

    # 交给inception进行自动审核
    try:
        result = InceptionDao().sqlautoReview(sqlContent, instance_name, db_name)
    except Exception as msg:
        context = {'errMsg': msg}
        return render(request, 'error.html', context)

    if result is None or len(result) == 0:
        context = {'errMsg': 'inception返回的结果集为空！可能是SQL语句有语法错误'}
        return render(request, 'error.html', context)
    # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
    jsonResult = json.dumps(result)

    # 遍历result，看是否有任何自动审核不通过的地方，一旦有，则需要设置is_manual = 0，跳过inception直接执行
    workflowStatus = Const.workflowStatus['manreviewing']
    # inception审核不通过的工单，标记手动执行标签
    is_manual = 0
    for row in result:
        if row[2] == 2:
            is_manual = 1
            break
        elif re.match(r"\w*comments\w*", row[4]):
            is_manual = 1
            break

    # 判断SQL是否包含DDL语句，SQL语法 1、DDL，2、DML
    sql_syntax = 2
    for row in sqlContent.strip(';').split(';'):
        if re.match(r"^alter|^create|^drop|^truncate|^rename", row.strip().lower()):
            sql_syntax = 1
            break

    # 调用工作流生成工单
    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 存进数据库里
            engineer = request.user.username
            if not workflowid:
                sql_workflow = SqlWorkflow()
                sql_workflow.create_time = timezone.now()
            else:
                sql_workflow = SqlWorkflow.objects.get(id=int(workflowid))
            sql_workflow.workflow_name = workflowName
            sql_workflow.group_id = group_id
            sql_workflow.group_name = group_name
            sql_workflow.engineer = engineer
            sql_workflow.engineer_display = request.user.display
            sql_workflow.audit_auth_groups = Workflow.auditsettings(group_id, WorkflowDict.workflow_type['sqlreview'])
            sql_workflow.status = workflowStatus
            sql_workflow.is_backup = isBackup
            sql_workflow.review_content = jsonResult
            sql_workflow.instance_name = instance_name
            sql_workflow.db_name = db_name
            sql_workflow.sql_content = sqlContent
            sql_workflow.execute_result = ''
            sql_workflow.is_manual = is_manual
            sql_workflow.audit_remark = ''
            sql_workflow.sql_syntax = sql_syntax
            sql_workflow.save()
            workflowId = sql_workflow.id
            # 自动审核通过了，才调用工作流
            if workflowStatus == Const.workflowStatus['manreviewing']:
                # 调用工作流插入审核信息, 查询权限申请workflow_type=2
                # 抄送通知人
                listCcAddr = [email['email'] for email in
                              Users.objects.filter(username__in=notify_users).values('email')]
                workflowOb.addworkflowaudit(request, WorkflowDict.workflow_type['sqlreview'], workflowId,
                                            listCcAddr=listCcAddr)
    except Exception as msg:
        context = {'errMsg': msg}
        return render(request, 'error.html', context)

    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))


# 审核通过，不执行
@permission_required('sql.sql_review', raise_exception=True)
def passed(request):
    workflowId = request.POST['workflowid']
    if workflowId == '' or workflowId is None:
        context = {'errMsg': 'workflowId参数为空.'}
        return render(request, 'error.html', context)
    workflowId = int(workflowId)
    workflowDetail = SqlWorkflow.objects.get(id=workflowId)
    audit_remark = request.POST.get('audit_remark', '')

    user = request.user
    if Workflow.can_review(request.user, workflowId, 2) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 调用工作流接口审核
            # 获取audit_id
            audit_id = Workflow.auditinfobyworkflow_id(workflow_id=workflowId,
                                                       workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
            auditresult = workflowOb.auditworkflow(request, audit_id, WorkflowDict.workflow_status['audit_success'],
                                                   user.username, audit_remark)

            # 按照审核结果更新业务表审核状态
            if auditresult['data']['workflow_status'] == WorkflowDict.workflow_status['audit_success']:
                # 将流程状态修改为审核通过，并更新reviewok_time字段
                workflowDetail.status = Const.workflowStatus['pass']
                workflowDetail.reviewok_time = timezone.now()
                workflowDetail.audit_remark = audit_remark
                workflowDetail.save()
    except Exception as msg:
        context = {'errMsg': msg}
        return render(request, 'error.html', context)

    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))


# 仅执行SQL
@permission_required('sql.sql_execute', raise_exception=True)
def execute(request):
    workflowId = request.POST['workflowid']
    if workflowId == '' or workflowId is None:
        context = {'errMsg': 'workflowId参数为空.'}
        return render(request, 'error.html', context)

    workflowId = int(workflowId)
    workflowDetail = SqlWorkflow.objects.get(id=workflowId)
    instance_name = workflowDetail.instance_name
    db_name = workflowDetail.db_name
    url = getDetailUrl(request, workflowId)

    if can_execute(request.user, workflowId) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    # 将流程状态修改为执行中，并更新reviewok_time字段
    workflowDetail.status = Const.workflowStatus['executing']
    workflowDetail.reviewok_time = timezone.now()
    workflowDetail.save()

    # 判断是通过inception执行还是直接执行，is_manual=0则通过inception执行，is_manual=1代表inception审核不通过，需要直接执行
    if workflowDetail.is_manual == 0:
        # 执行之前重新split并check一遍，更新SHA1缓存；因为如果在执行中，其他进程去做这一步操作的话，会导致inception core dump挂掉
        try:
            splitReviewResult = InceptionDao().sqlautoReview(workflowDetail.sql_content, workflowDetail.instance_name,
                                                             db_name,
                                                             isSplit='yes')
        except Exception as msg:
            context = {'errMsg': msg}
            return render(request, 'error.html', context)
        workflowDetail.review_content = json.dumps(splitReviewResult)
        try:
            workflowDetail.save()
        except Exception:
            # 关闭后重新获取连接，防止超时
            connection.close()
            workflowDetail.save()

        # 采取异步回调的方式执行语句，防止出现持续执行中的异常
        t = Thread(target=execute_call_back, args=(workflowId, instance_name, url))
        t.start()
    else:
        # 采取异步回调的方式执行语句，防止出现持续执行中的异常
        t = Thread(target=execute_skipinc_call_back,
                   args=(workflowId, instance_name, db_name, workflowDetail.sql_content, url))
        t.start()
    # 删除定时执行job
    if workflowDetail.status == Const.workflowStatus['timingtask']:
        job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflowId)
        del_sqlcronjob(job_id)
    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))


# 定时执行SQL
@permission_required('sql.sql_execute', raise_exception=True)
def timingtask(request):
    workflowId = request.POST.get('workflowid')
    run_date = request.POST.get('run_date')
    if run_date is None or workflowId is None:
        context = {'errMsg': '时间不能为空'}
        return render(request, 'error.html', context)
    elif run_date < datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
        context = {'errMsg': '时间不能小于当前时间'}
        return render(request, 'error.html', context)
    workflowDetail = SqlWorkflow.objects.get(id=workflowId)

    if can_timingtask(request.user, workflowId) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    run_date = datetime.datetime.strptime(run_date, "%Y-%m-%d %H:%M:%S")
    url = getDetailUrl(request, workflowId)
    job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflowId)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 将流程状态修改为定时执行
            workflowDetail.status = Const.workflowStatus['timingtask']
            workflowDetail.save()
            # 调用添加定时任务
            add_sqlcronjob(job_id, run_date, workflowId, url)
    except Exception as msg:
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))


# 终止流程
def cancel(request):
    workflowId = request.POST['workflowid']
    if workflowId == '' or workflowId is None:
        context = {'errMsg': 'workflowId参数为空.'}
        return render(request, 'error.html', context)

    workflowId = int(workflowId)
    workflowDetail = SqlWorkflow.objects.get(id=workflowId)
    audit_remark = request.POST.get('cancel_remark')
    if audit_remark is None:
        context = {'errMsg': '终止原因不能为空'}
        return render(request, 'error.html', context)

    user = request.user
    if can_cancel(request.user, workflowId) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 调用工作流接口取消或者驳回
            # 获取audit_id
            audit_id = Workflow.auditinfobyworkflow_id(workflow_id=workflowId,
                                                       workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
            # 仅待审核的需要调用工作流，审核通过的不需要
            if workflowDetail.status != Const.workflowStatus['manreviewing']:
                # 增加工单日志
                if user.username == workflowDetail.engineer:
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
                if user.username == workflowDetail.engineer:
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
            if workflowDetail.status == Const.workflowStatus['timingtask']:
                job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflowId)
                del_sqlcronjob(job_id)
            # 将流程状态修改为人工终止流程
            workflowDetail.status = Const.workflowStatus['abort']
            workflowDetail.audit_remark = audit_remark
            workflowDetail.save()
    except Exception as msg:
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))


def getSqlSHA1(workflowId):
    """调用django ORM从数据库里查出review_content，从其中获取sqlSHA1值"""
    workflowDetail = get_object_or_404(SqlWorkflow, pk=workflowId)
    dictSHA1 = {}
    # 使用json.loads方法，把review_content从str转成list,
    listReCheckResult = json.loads(workflowDetail.review_content)

    for rownum in range(len(listReCheckResult)):
        id = rownum + 1
        sqlSHA1 = listReCheckResult[rownum][10]
        if sqlSHA1 != '':
            dictSHA1[id] = sqlSHA1

    if dictSHA1 != {}:
        # 如果找到有sqlSHA1值，说明是通过pt-OSC操作的，将其放入缓存。
        # 因为使用OSC执行的SQL占较少数，所以不设置缓存过期时间
        sqlSHA1_cache[workflowId] = dictSHA1
    return dictSHA1


def getOscPercent(request):
    """获取该SQL的pt-OSC执行进度和剩余时间"""
    workflowId = request.POST['workflowid']
    sqlID = request.POST['sqlID']
    if workflowId == '' or workflowId is None or sqlID == '' or sqlID is None:
        context = {"status": -1, 'msg': 'workflowId或sqlID参数为空.', "data": ""}
        return HttpResponse(json.dumps(context), content_type='application/json')

    workflowId = int(workflowId)
    sqlID = int(sqlID)
    dictSHA1 = {}
    if workflowId in sqlSHA1_cache:
        dictSHA1 = sqlSHA1_cache[workflowId]
        # cachehit = "已命中"
    else:
        dictSHA1 = getSqlSHA1(workflowId)

    if dictSHA1 != {} and sqlID in dictSHA1:
        sqlSHA1 = dictSHA1[sqlID]
        try:
            result = InceptionDao().getOscPercent(sqlSHA1)  # 成功获取到SHA1值，去inception里面查询进度
        except Exception as msg:
            result = {'status': 1, 'msg': msg, 'data': ''}
            return HttpResponse(json.dumps(result), content_type='application/json')

        if result["status"] == 0:
            # 获取到进度值
            pctResult = result
        else:
            # result["status"] == 1, 未获取到进度值,需要与workflow.execute_result对比，来判断是已经执行过了，还是还未执行
            execute_result = SqlWorkflow.objects.get(id=workflowId).execute_result
            try:
                listExecResult = json.loads(execute_result)
            except ValueError:
                listExecResult = execute_result
            if type(listExecResult) == list and len(listExecResult) >= sqlID - 1:
                if dictSHA1[sqlID] in listExecResult[sqlID - 1][10]:
                    # 已经执行完毕，进度值置为100
                    pctResult = {"status": 0, "msg": "ok", "data": {"percent": 100, "timeRemained": ""}}
            else:
                # 可能因为前一条SQL是DML，正在执行中；或者还没执行到这一行。但是status返回的是4，而当前SQL实际上还未开始执行。这里建议前端进行重试
                pctResult = {"status": -3, "msg": "进度未知", "data": {"percent": -100, "timeRemained": ""}}
    elif dictSHA1 != {} and sqlID not in dictSHA1:
        pctResult = {"status": 4, "msg": "该行SQL不是由pt-OSC执行的", "data": ""}
    else:
        pctResult = {"status": -2, "msg": "整个工单不由pt-OSC执行", "data": ""}
    return HttpResponse(json.dumps(pctResult), content_type='application/json')


def getWorkflowStatus(request):
    """获取某个工单的当前状态"""
    workflowId = request.POST['workflowid']
    if workflowId == '' or workflowId is None:
        context = {"status": -1, 'msg': 'workflowId参数为空.', "data": ""}
        return HttpResponse(json.dumps(context), content_type='application/json')

    workflowId = int(workflowId)
    workflowDetail = get_object_or_404(SqlWorkflow, pk=workflowId)
    workflowStatus = workflowDetail.status
    result = {"status": workflowStatus, "msg": "", "data": ""}
    return HttpResponse(json.dumps(result), content_type='application/json')


def stopOscProgress(request):
    """中止该SQL的pt-OSC进程"""
    workflowId = request.POST['workflowid']
    sqlID = request.POST['sqlID']
    if workflowId == '' or workflowId is None or sqlID == '' or sqlID is None:
        context = {"status": -1, 'msg': 'workflowId或sqlID参数为空.', "data": ""}
        return HttpResponse(json.dumps(context), content_type='application/json')

    user = request.user
    workflowDetail = SqlWorkflow.objects.get(id=workflowId)
    try:
        reviewMan = json.loads(workflowDetail.audit_auth_groups)
    except ValueError:
        reviewMan = (workflowDetail.audit_auth_groups,)
    # 服务器端二次验证，当前工单状态必须为等待人工审核,正在执行人工审核动作的当前登录用户必须为审核人. 避免攻击或被接口测试工具强行绕过
    if workflowDetail.status != Const.workflowStatus['executing']:
        context = {"status": -1, "msg": '当前工单状态不是"执行中"，请刷新当前页面！', "data": ""}
        return HttpResponse(json.dumps(context), content_type='application/json')
    if user.username is None or user.username not in reviewMan:
        context = {"status": -1, 'msg': '当前登录用户不是审核人，请重新登录.', "data": ""}
        return HttpResponse(json.dumps(context), content_type='application/json')

    workflowId = int(workflowId)
    sqlID = int(sqlID)
    if workflowId in sqlSHA1_cache:
        dictSHA1 = sqlSHA1_cache[workflowId]
    else:
        dictSHA1 = getSqlSHA1(workflowId)
    if dictSHA1 != {} and sqlID in dictSHA1:
        sqlSHA1 = dictSHA1[sqlID]
        try:
            optResult = InceptionDao().stopOscProgress(sqlSHA1)
        except Exception as msg:
            result = {'status': 1, 'msg': msg, 'data': ''}
            return HttpResponse(json.dumps(result), content_type='application/json')
    else:
        optResult = {"status": 4, "msg": "不是由pt-OSC执行的", "data": ""}
    return HttpResponse(json.dumps(optResult), content_type='application/json')


# 获取审核列表
def workflowlist(request):
    # 获取用户信息
    user = request.user

    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    workflow_type = int(request.POST.get('workflow_type'))
    limit = offset + limit

    # 获取搜索参数
    search = request.POST.get('search')
    if search is None:
        search = ''

    # 调用工作流接口获取审核列表
    result = workflowOb.auditlist(user, workflow_type, offset, limit, search)
    auditlist = result['data']['auditlist']
    auditlistCount = result['data']['auditlistCount']

    # QuerySet 序列化
    rows = [row for row in auditlist]

    result = {"total": auditlistCount, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
