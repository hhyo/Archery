# -*- coding: UTF-8 -*-

import simplejson as json

from django.contrib.auth import logout
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import Group
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import escape

from sql.utils.inception import InceptionDao
from common.utils.aes_decryptor import Prpcrypt
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

prpCryptor = Prpcrypt()
workflowOb = Workflow()


# 登录
def login(request):
    return render(request, 'login.html')


# 退出登录
def sign_out(request):
    logout(request)
    return HttpResponseRedirect(reverse('sql:login'))


# SQL上线工单页面
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
    return render(request, 'submitSql.html', context)


# 提交SQL给inception进行解析
@permission_required('sql.sql_submit', raise_exception=True)
def autoreview(request):
    workflowid = escape(request.POST.get('workflowid', ''))
    sqlContent = escape(request.POST['sql_content'])
    workflowName = escape(request.POST['workflow_name'])
    group_name = escape(request.POST['group_name'])
    group_id = SqlGroup.objects.get(group_name=group_name).group_id
    instance_name = escape(request.POST['instance_name'])
    db_name = escape(request.POST.get('db_name'))
    isBackup = escape(request.POST['is_backup'])
    notify_users = escape(request.POST.getlist('notify_users'))

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


# 展示SQL工单详细页面
def detail(request, workflowId):
    workflowDetail = get_object_or_404(SqlWorkflow, pk=workflowId)
    if workflowDetail.status in (Const.workflowStatus['finish'], Const.workflowStatus['exception']) \
            and workflowDetail.is_manual == 0:
        listContent = json.loads(workflowDetail.execute_result)
    else:
        listContent = json.loads(workflowDetail.review_content)

    # 获取当前审批和审批流程
    audit_auth_group, current_audit_auth_group = Workflow.review_info(workflowId, 2)

    # 是否可审核
    is_can_review = Workflow.can_review(request.user, workflowId, 2)
    # 是否可执行
    is_can_execute = can_execute(request.user, workflowId)
    # 是否可定时执行
    is_can_timingtask = can_timingtask(request.user, workflowId)
    # 是否可取消
    is_can_cancel = can_cancel(request.user, workflowId)

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
        # row['sqlsha1'] = row_item[10]
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
    context = {'workflowDetail': workflowDetail, 'column_list': column_list, 'rows': rows,
               'is_can_review': is_can_review, 'is_can_execute': is_can_execute, 'is_can_timingtask': is_can_timingtask,
               'is_can_cancel': is_can_cancel, 'audit_auth_group': audit_auth_group,
               'current_audit_auth_group': current_audit_auth_group, 'run_date': run_date}
    return render(request, 'detail.html', context)


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
    workflowDetail = SqlWorkflow.objects.get(id=workflowId)
    workflowName = workflowDetail.workflow_name
    rollbackWorkflowName = "【回滚工单】原工单Id:%s ,%s" % (workflowId, workflowName)
    context = {'listBackupSql': listBackupSql, 'workflowDetail': workflowDetail,
               'rollbackWorkflowName': rollbackWorkflowName}
    return render(request, 'rollback.html', context)


# SQL审核必读
@permission_required('sql.menu_document', raise_exception=True)
def dbaprinciples(request):
    return render(request, 'dbaprinciples.html')


# 图表展示
@permission_required('sql.menu_dashboard', raise_exception=True)
def dashboard(request):
    return render(request, 'dashboard.html')


# SQL在线查询
@permission_required('sql.menu_query', raise_exception=True)
def sqlquery(request):
    # 获取用户关联从库列表
    instances = [slave.instance_name for slave in user_instances(request.user, 'slave')]

    context = {'instances': instances}
    return render(request, 'sqlquery.html', context)


# SQL慢日志
@permission_required('sql.menu_slowquery', raise_exception=True)
def slowquery(request):
    # 获取用户关联实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, 'all')]

    context = {'tab': 'slowquery', 'instances': instances}
    return render(request, 'slowquery.html', context)


# SQL优化工具
@permission_required('sql.menu_sqladvisor', raise_exception=True)
def sqladvisor(request):
    # 获取用户关联实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, 'all')]

    context = {'instances': instances}
    return render(request, 'sqladvisor.html', context)


# 查询权限申请列表
@permission_required('sql.menu_queryapplylist', raise_exception=True)
def queryapplylist(request):
    user = request.user
    # 获取项目组
    group_list = user_groups(user)

    context = {'group_list': group_list}
    return render(request, 'queryapplylist.html', context)


# 查询权限申请详情
def queryapplydetail(request, apply_id):
    workflowDetail = QueryPrivilegesApply.objects.get(apply_id=apply_id)
    # 获取当前审批和审批流程
    audit_auth_group, current_audit_auth_group = Workflow.review_info(apply_id, 1)

    # 是否可审核
    is_can_review = Workflow.can_review(request.user, apply_id, 1)

    context = {'workflowDetail': workflowDetail, 'audit_auth_group': audit_auth_group,
               'current_audit_auth_group': current_audit_auth_group, 'is_can_review': is_can_review}
    return render(request, 'queryapplydetail.html', context)


# 用户的查询权限管理
def queryuserprivileges(request):
    # 获取所有用户
    user_list = QueryPrivileges.objects.filter(is_deleted=0).values('user_name').distinct()
    context = {'user_list': user_list}
    return render(request, 'queryuserprivileges.html', context)


# 问题诊断--进程
@permission_required('sql.menu_dbdiagnostic', raise_exception=True)
def dbdiagnostic(request):
    # 获取用户关联实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, 'all')]

    context = {'tab': 'process', 'instances': instances}
    return render(request, 'dbdiagnostic.html', context)


# 获取工作流审核列表
def workflows(request):
    return render(request, "workflow.html")


# 工作流审核详情
def workflowsdetail(request, audit_id):
    # 按照不同的workflow_type返回不同的详情
    auditInfo = Workflow.auditinfo(audit_id)
    if auditInfo.workflow_type == WorkflowDict.workflow_type['query']:
        return HttpResponseRedirect(reverse('sql:queryapplydetail', args=(auditInfo.workflow_id,)))
    elif auditInfo.workflow_type == WorkflowDict.workflow_type['sqlreview']:
        return HttpResponseRedirect(reverse('sql:detail', args=(auditInfo.workflow_id,)))


# 配置管理
@superuser_required
def config(request):
    # 获取所有项目组名称
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


# 资源组管理
@superuser_required
def group(request):
    return render(request, 'group.html')


# 资源组组关系管理
@superuser_required
def groupmgmt(request, group_id):
    group = SqlGroup.objects.get(group_id=group_id)
    return render(request, 'groupmgmt.html', {'group': group})


# 实例管理
@permission_required('sql.menu_instance', raise_exception=True)
def instance(request):
    return render(request, 'instance.html')


# 实例用户管理
@permission_required('sql.menu_instance', raise_exception=True)
def instanceuser(request, instance_id):
    return render(request, 'instanceuser.html', {'instance_id': instance_id})


# binlog2sql
@permission_required('sql.menu_binlog2sql', raise_exception=True)
def binlog2sql(request):
    # 获取实例列表
    instances = [instance.instance_name for instance in user_instances(request.user, 'all')]
    return render(request, 'binlog2sql.html', {'instances': instances})
