# -*- coding: UTF-8 -*-
import re

import simplejson as json
from threading import Thread
import datetime

from django.contrib.auth.hashers import make_password
from django.contrib.auth import logout
from django.db.models import F
from django.db import connection, transaction
from django.utils import timezone
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse

from sql.utils.dao import Dao
from sql.utils.inception import InceptionDao
from sql.utils.aes_decryptor import Prpcrypt
from sql.utils.permission import role_required, superuser_required
from sql.utils.jobs import job_info, del_sqlcronjob, add_sqlcronjob

from .models import users, master_config, workflow, QueryPrivileges, Group, \
    QueryPrivilegesApply, Config, GroupRelations
from sql.utils.workflow import Workflow
from .sqlreview import getDetailUrl, execute_call_back, execute_skipinc_call_back
from .const import Const, WorkflowDict
from .group import user_groups, user_masters, user_slaves

import logging

logger = logging.getLogger('default')

dao = Dao()
prpCryptor = Prpcrypt()
workflowOb = Workflow()


# 注册用户
def sign_up(request):
    username = request.POST.get('username')
    password = request.POST.get('password')
    password2 = request.POST.get('password2')
    display = request.POST.get('display')
    email = request.POST.get('email')

    if username is None or password is None:
        context = {'errMsg': '用户名和密码不能为空'}
        return render(request, 'error.html', context)
    if len(users.objects.filter(username=username)) > 0:
        context = {'errMsg': '用户名已存在'}
        return render(request, 'error.html', context)
    if password != password2:
        context = {'errMsg': '两次输入密码不一致'}
        return render(request, 'error.html', context)

    new_account = users.objects.create(username=username,
                                       password=make_password(password),
                                       display=display,
                                       email=email,
                                       role='工程师',
                                       is_active=1,
                                       is_staff=1)
    new_account.save()
    return render(request, 'login.html')


# 登录
def login(request):
    return render(request, 'login.html')


# 退出登录
def sign_out(request):
    logout(request)
    return HttpResponseRedirect(reverse('sql:login'))


# SQL上线工单页面
def sqlworkflow(request):
    context = {'currentMenu': 'sqlworkflow'}
    return render(request, 'sqlworkflow.html', context)


# 提交SQL的页面
def submitSql(request):
    user = request.user
    # 获取组信息
    group_list = user_groups(user)

    # 获取所有有效用户，通知对象
    active_user = users.objects.filter(is_active=1)

    context = {'currentMenu': 'sqlworkflow', 'active_user': active_user, 'group_list': group_list}
    return render(request, 'submitSql.html', context)


# 提交SQL给inception进行解析
def autoreview(request):
    workflowid = request.POST.get('workflowid')
    sqlContent = request.POST['sql_content']
    workflowName = request.POST['workflow_name']
    group_name = request.POST['group_name']
    group_id = Group.objects.get(group_name=group_name).group_id
    clusterName = request.POST['cluster_name']
    db_name = request.POST.get('db_name')
    isBackup = request.POST['is_backup']
    reviewMan = request.POST.get('workflow_auditors')
    notify_users = request.POST.getlist('notify_users')

    # 服务器端参数验证
    if sqlContent is None or workflowName is None or clusterName is None or db_name is None or isBackup is None or reviewMan is None:
        context = {'errMsg': '页面提交参数可能为空'}
        return render(request, 'error.html', context)

    # 验证组权限（用户是否在该组、该组是否有指定实例）
    try:
        GroupRelations.objects.get(group_name=group_name, object_name=clusterName, object_type=2)
    except Exception:
        context = {'errMsg': '该组不存在所选主库！'}
        return render(request, 'error.html', context)
    try:
        user_masters(request.user).get(cluster_name=clusterName)
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
        result = InceptionDao().sqlautoReview(sqlContent, clusterName, db_name)
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
                Workflow = workflow()
                Workflow.create_time = timezone.now()
            else:
                Workflow = workflow.objects.get(id=int(workflowid))
            Workflow.workflow_name = workflowName
            Workflow.group_id = group_id
            Workflow.group_name = group_name
            Workflow.engineer = engineer
            Workflow.review_man = reviewMan
            Workflow.status = workflowStatus
            Workflow.is_backup = isBackup
            Workflow.review_content = jsonResult
            Workflow.cluster_name = clusterName
            Workflow.db_name = db_name
            Workflow.sql_content = sqlContent
            Workflow.execute_result = ''
            Workflow.is_manual = is_manual
            Workflow.audit_remark = ''
            Workflow.sql_syntax = sql_syntax
            Workflow.save()
            workflowId = Workflow.id
            # 自动审核通过了，才调用工作流
            if workflowStatus == Const.workflowStatus['manreviewing']:
                # 调用工作流插入审核信息, 查询权限申请workflow_type=2
                # 抄送通知人
                listCcAddr = [email['email'] for email in
                              users.objects.filter(username__in=notify_users).values('email')]
                workflowOb.addworkflowaudit(request, WorkflowDict.workflow_type['sqlreview'], workflowId,
                                            listCcAddr=listCcAddr)
    except Exception as msg:
        context = {'errMsg': msg}
        return render(request, 'error.html', context)

    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))


# 展示SQL工单详细内容，以及可以人工审核，审核通过即可执行
def detail(request, workflowId):
    workflowDetail = get_object_or_404(workflow, pk=workflowId)
    if workflowDetail.status in (Const.workflowStatus['finish'], Const.workflowStatus['exception']) \
            and workflowDetail.is_manual == 0:
        listContent = json.loads(workflowDetail.execute_result)
    else:
        listContent = json.loads(workflowDetail.review_content)

    # 获取审核人
    reviewMan = workflowDetail.review_man
    reviewMan = reviewMan.split(',')

    # 获取当前审核人
    try:
        current_audit_user = workflowOb.auditinfobyworkflow_id(workflow_id=workflowId,
                                                               workflow_type=WorkflowDict.workflow_type['sqlreview']
                                                               ).current_audit_user
    except Exception:
        current_audit_user = None

    # 获取用户信息
    loginUserOb = request.user

    # 获取定时执行任务信息
    if workflowDetail.status == Const.workflowStatus['timingtask']:
        job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflowId)
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
        row['sqlsha1'] = row_item[10]
        rows.append(row)

        if workflowDetail.status == '执行中':
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
                 "           <input type=\"hidden\" name=\"workflowid\" value=\"" + str(workflowDetail.id) + "\">",
                 "           <button id=\"btnstop_" + str(row['ID']) + "\" value=\"" + str(row['ID']) + "\"",
                 "                   type=\"button\" class=\"close\" style=\"display: none\" title=\"停止pt-OSC进程\">",
                 "               <span class=\"glyphicons glyphicons-stop\">&times;</span>",
                 "           </button>",
                 "       </form>",
                 "   </div>",
                 "</div>"])
    context = {'currentMenu': 'sqlworkflow', 'workflowDetail': workflowDetail, 'column_list': column_list, 'rows': rows,
               'reviewMan': reviewMan, 'current_audit_user': current_audit_user, 'loginUserOb': loginUserOb,
               'run_date': run_date}
    return render(request, 'detail.html', context)


# 审核通过，不执行
def passed(request):
    workflowId = request.POST['workflowid']
    if workflowId == '' or workflowId is None:
        context = {'errMsg': 'workflowId参数为空.'}
        return render(request, 'error.html', context)
    workflowId = int(workflowId)
    workflowDetail = workflow.objects.get(id=workflowId)

    # 获取审核人
    reviewMan = workflowDetail.review_man
    reviewMan = reviewMan.split(',')

    # 服务器端二次验证，正在执行人工审核动作的当前登录用户必须为审核人. 避免攻击或被接口测试工具强行绕过
    loginUser = request.user.username
    if loginUser is None or loginUser not in reviewMan:
        context = {'errMsg': '当前登录用户不是审核人，请重新登录.'}
        return render(request, 'error.html', context)

    # 服务器端二次验证，当前工单状态必须为等待人工审核
    if workflowDetail.status != Const.workflowStatus['manreviewing']:
        context = {'errMsg': '当前工单状态不是等待人工审核中，请刷新当前页面！'}
        return render(request, 'error.html', context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 调用工作流接口审核
            # 获取audit_id
            audit_id = workflowOb.auditinfobyworkflow_id(workflow_id=workflowId,
                                                         workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
            auditresult = workflowOb.auditworkflow(request, audit_id, WorkflowDict.workflow_status['audit_success'],
                                                   loginUser, '')

            # 按照审核结果更新业务表审核状态
            if auditresult['data']['workflow_status'] == WorkflowDict.workflow_status['audit_success']:
                # 将流程状态修改为审核通过，并更新reviewok_time字段
                workflowDetail.status = Const.workflowStatus['pass']
                workflowDetail.reviewok_time = timezone.now()
                workflowDetail.audit_remark = ''
                workflowDetail.save()
    except Exception as msg:
        context = {'errMsg': msg}
        return render(request, 'error.html', context)

    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))


# 仅执行SQL
def execute(request):
    workflowId = request.POST['workflowid']
    if workflowId == '' or workflowId is None:
        context = {'errMsg': 'workflowId参数为空.'}
        return render(request, 'error.html', context)

    workflowId = int(workflowId)
    workflowDetail = workflow.objects.get(id=workflowId)
    clusterName = workflowDetail.cluster_name
    db_name = workflowDetail.db_name
    url = getDetailUrl(request) + str(workflowId) + '/'

    # 获取审核人
    reviewMan = workflowDetail.review_man
    reviewMan = reviewMan.split(',')

    # 服务器端二次验证，正在执行人工审核动作的当前登录用户必须为审核人或者提交人. 避免攻击或被接口测试工具强行绕过
    loginUser = request.user.username
    if loginUser is None or (loginUser not in reviewMan and loginUser != workflowDetail.engineer):
        context = {'errMsg': '当前登录用户不是审核人或者提交人，请重新登录.'}
        return render(request, 'error.html', context)

    # 服务器端二次验证，当前工单状态必须为审核通过状态
    if workflowDetail.status != Const.workflowStatus['pass']:
        context = {'errMsg': '当前工单状态不是审核通过，请刷新当前页面！'}
        return render(request, 'error.html', context)

    # 将流程状态修改为执行中，并更新reviewok_time字段
    workflowDetail.status = Const.workflowStatus['executing']
    workflowDetail.reviewok_time = timezone.now()
    workflowDetail.save()

    # 判断是通过inception执行还是直接执行，is_manual=0则通过inception执行，is_manual=1代表inception审核不通过，需要直接执行
    if workflowDetail.is_manual == 0:
        # 执行之前重新split并check一遍，更新SHA1缓存；因为如果在执行中，其他进程去做这一步操作的话，会导致inception core dump挂掉
        try:
            splitReviewResult = InceptionDao().sqlautoReview(workflowDetail.sql_content, workflowDetail.cluster_name,
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
        t = Thread(target=execute_call_back, args=(workflowId, clusterName, url))
        t.start()
    else:
        # 采取异步回调的方式执行语句，防止出现持续执行中的异常
        t = Thread(target=execute_skipinc_call_back,
                   args=(workflowId, clusterName, db_name, workflowDetail.sql_content, url))
        t.start()

    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))


# 定时执行SQL
@role_required(('DBA',))
def timingtask(request):
    workflowId = request.POST.get('workflowid')
    run_date = request.POST.get('run_date')
    if run_date is None or workflowId is None:
        context = {'errMsg': '时间不能为空'}
        return render(request, 'error.html', context)
    elif run_date < datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
        context = {'errMsg': '时间不能小于当前时间'}
        return render(request, 'error.html', context)
    workflowDetail = workflow.objects.get(id=workflowId)
    if workflowDetail.status not in [Const.workflowStatus['pass'], Const.workflowStatus['timingtask']]:
        context = {'errMsg': '必须为审核通过或者定时执行状态'}
        return render(request, 'error.html', context)

    run_date = datetime.datetime.strptime(run_date, "%Y-%m-%d %H:%M:%S")
    url = getDetailUrl(request) + str(workflowId) + '/'
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
    workflowDetail = workflow.objects.get(id=workflowId)

    # 获取审核人
    reviewMan = workflowDetail.review_man
    reviewMan = reviewMan.split(',')

    audit_remark = request.POST.get('audit_remark')
    if audit_remark is None:
        context = {'errMsg': '驳回原因不能为空'}
        return render(request, 'error.html', context)

    # 服务器端二次验证，如果正在执行终止动作的当前登录用户，不是提交人也不是审核人，则异常.
    loginUser = request.user.username
    if loginUser is None or (loginUser not in reviewMan and loginUser != workflowDetail.engineer):
        context = {'errMsg': '当前登录用户不是审核人也不是提交人，请重新登录.'}
        return render(request, 'error.html', context)

    # 服务器端二次验证，如果当前单子状态是结束状态，则不能发起终止
    if workflowDetail.status in (
            Const.workflowStatus['abort'], Const.workflowStatus['finish'], Const.workflowStatus['autoreviewwrong'],
            Const.workflowStatus['exception']):
        return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 调用工作流接口取消或者驳回
            # 获取audit_id
            audit_id = workflowOb.auditinfobyworkflow_id(workflow_id=workflowId,
                                                         workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
            if loginUser == workflowDetail.engineer:
                auditresult = workflowOb.auditworkflow(request, audit_id, WorkflowDict.workflow_status['audit_abort'],
                                                       loginUser, audit_remark)
            else:
                auditresult = workflowOb.auditworkflow(request, audit_id, WorkflowDict.workflow_status['audit_reject'],
                                                       loginUser, audit_remark)
            # 删除定时执行job
            if workflowDetail.status == Const.workflowStatus['timingtask']:
                job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflowId)
                del_sqlcronjob(job_id)
            # 按照审核结果更新业务表审核状态
            if auditresult['data']['workflow_status'] in (
                    WorkflowDict.workflow_status['audit_abort'], WorkflowDict.workflow_status['audit_reject']):
                # 将流程状态修改为人工终止流程
                workflowDetail.status = Const.workflowStatus['abort']
                workflowDetail.audit_remark = audit_remark
                workflowDetail.save()
    except Exception as msg:
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))


# 展示回滚的SQL
def rollback(request):
    workflowId = request.GET['workflowid']
    if workflowId == '' or workflowId is None:
        context = {'errMsg': 'workflowId参数为空.'}
        return render(request, 'error.html', context)
    workflowId = int(workflowId)
    try:
        listBackupSql = InceptionDao().getRollbackSqlList(workflowId)
    except Exception as msg:
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    workflowDetail = workflow.objects.get(id=workflowId)
    workflowName = workflowDetail.workflow_name
    rollbackWorkflowName = "【回滚工单】原工单Id:%s ,%s" % (workflowId, workflowName)
    context = {'listBackupSql': listBackupSql, 'currentMenu': 'sqlworkflow', 'workflowDetail': workflowDetail,
               'rollbackWorkflowName': rollbackWorkflowName}
    return render(request, 'rollback.html', context)


# SQL审核必读
def dbaprinciples(request):
    context = {'currentMenu': 'dbaprinciples'}
    return render(request, 'dbaprinciples.html', context)


# 图表展示
def charts(request):
    context = {'currentMenu': 'charts'}
    return render(request, 'charts.html', context)


# SQL在线查询
def sqlquery(request):
    # 获取用户关联从库列表
    listAllClusterName = [slave.cluster_name for slave in user_slaves(request.user)]

    context = {'currentMenu': 'sqlquery', 'listAllClusterName': listAllClusterName}
    return render(request, 'sqlquery.html', context)


# SQL慢日志
def slowquery(request):
    # 获取用户关联主库列表
    cluster_name_list = [master.cluster_name for master in user_masters(request.user)]

    context = {'currentMenu': 'slowquery', 'tab': 'slowquery', 'cluster_name_list': cluster_name_list}
    return render(request, 'slowquery.html', context)


# SQL优化工具
def sqladvisor(request):
    # 获取用户关联主库列表
    cluster_name_list = [master.cluster_name for master in user_masters(request.user)]

    context = {'currentMenu': 'sqladvisor', 'listAllClusterName': cluster_name_list}
    return render(request, 'sqladvisor.html', context)


# 查询权限申请列表
def queryapplylist(request):
    user = request.user
    # 获取项目组
    group_list = user_groups(user)

    context = {'currentMenu': 'queryapply', 'group_list': group_list}
    return render(request, 'queryapplylist.html', context)


# 查询权限申请详情
def queryapplydetail(request, apply_id):
    workflowDetail = QueryPrivilegesApply.objects.get(apply_id=apply_id)
    # 获取当前审核人
    audit_info = workflowOb.auditinfobyworkflow_id(workflow_id=apply_id,
                                                   workflow_type=WorkflowDict.workflow_type['query'])

    context = {'currentMenu': 'queryapply', 'workflowDetail': workflowDetail, 'audit_info': audit_info}
    return render(request, 'queryapplydetail.html', context)


# 用户的查询权限管理
def queryuserprivileges(request):
    # 获取用户信息
    loginUserOb = request.user
    # 获取所有用户
    user_list = QueryPrivileges.objects.filter(is_deleted=0).values('user_name').distinct()
    context = {'currentMenu': 'queryapply', 'user_list': user_list, 'loginUserOb': loginUserOb}
    return render(request, 'queryuserprivileges.html', context)


# 问题诊断--进程
def diagnosis_process(request):
    # 获取用户信息
    loginUserOb = request.user

    # 获取所有实例名称
    masters = master_config.objects.all().order_by('cluster_name')
    cluster_name_list = [master.cluster_name for master in masters]

    context = {'currentMenu': 'diagnosis', 'tab': 'process', 'cluster_name_list': cluster_name_list,
               'loginUserOb': loginUserOb}
    return render(request, 'diagnosis.html', context)


# 问题诊断--空间
def diagnosis_sapce(request):
    # 获取所有实例名称
    masters = master_config.objects.all().order_by('cluster_name')
    cluster_name_list = [master.cluster_name for master in masters]

    context = {'currentMenu': 'diagnosis', 'tab': 'space', 'cluster_name_list': cluster_name_list}
    return render(request, 'diagnosis.html', context)


# 获取工作流审核列表
def workflows(request):
    # 获取用户信息
    loginUserOb = request.user
    context = {'currentMenu': 'workflow', "loginUserOb": loginUserOb}
    return render(request, "workflow.html", context)


# 工作流审核详情
def workflowsdetail(request, audit_id):
    # 按照不同的workflow_type返回不同的详情
    auditInfo = workflowOb.auditinfo(audit_id)
    if auditInfo.workflow_type == WorkflowDict.workflow_type['query']:
        return HttpResponseRedirect(reverse('sql:queryapplydetail', args=(auditInfo.workflow_id,)))
    elif auditInfo.workflow_type == WorkflowDict.workflow_type['sqlreview']:
        return HttpResponseRedirect(reverse('sql:detail', args=(auditInfo.workflow_id,)))


# 配置管理
@superuser_required
def config(request):
    # 获取所有项组名称
    group_list = Group.objects.all().annotate(id=F('group_id'),
                                              name=F('group_name'),
                                              parent=F('group_parent_id'),
                                              level=F('group_level')
                                              ).values('id', 'name', 'parent', 'level')

    group_list = [group for group in group_list]

    # 获取所有用户
    user_list = users.objects.filter(is_active=1).values('username', 'display')
    # 获取所有配置项
    all_config = Config.objects.all().values('item', 'value')
    sys_config = {}
    for items in all_config:
        sys_config[items['item']] = items['value']

    context = {'currentMenu': 'config', 'group_list': group_list, 'user_list': user_list,
               'config': sys_config, 'WorkflowDict': WorkflowDict}
    return render(request, 'config.html', context)
