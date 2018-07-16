# -*- coding: UTF-8 -*- 

import simplejson as json
import datetime

import subprocess

from django.contrib.auth import authenticate, login
from django.db import transaction
from django.db.models import Q
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.hashers import make_password

from sql.utils.group import user_masters
from sql.models import Config
from sql.utils.permission import superuser_required
from sql.utils.dao import Dao
from .const import Const
from sql.utils.inception import InceptionDao
from sql.utils.aes_decryptor import Prpcrypt
from .models import users, master_config, workflow
from sql.utils.sendmsg import MailSender
import logging
from sql.utils.workflow import Workflow
from sql.utils.config import SysConfig
from sql.utils.extend_json_encoder import ExtendJSONEncoder

logger = logging.getLogger('default')
dao = Dao()
prpCryptor = Prpcrypt()
login_failure_counter = {}  # 登录失败锁定计数器，给loginAuthenticate用的
sqlSHA1_cache = {}  # 存储SQL文本与SHA1值的对应关系，尽量减少与数据库的交互次数,提高效率。格式: {工单ID1:{SQL内容1:sqlSHA1值1, SQL内容2:sqlSHA1值2},}
workflowOb = Workflow()


# 登录失败邮件推送给DBA
def log_mail_record(login_failed_message):
    mail_title = 'login archer'
    logger.warning(login_failed_message)
    dbaAddr = [email['email'] for email in users.objects.filter(role='DBA').values('email')]
    if SysConfig().sys_config.get('mail') == 'true':
        MailSender().sendEmail(mail_title, login_failed_message, dbaAddr)


# ajax接口，登录页面调用，用来验证用户名密码
@csrf_exempt
def loginAuthenticate(username, password):
    """登录认证，包含一个登录失败计数器，5分钟内连续失败5次的账号，会被锁定5分钟"""
    sys_config = SysConfig().sys_config
    if sys_config.get('lock_cnt_threshold'):
        lockCntThreshold = int(sys_config.get('lock_cnt_threshold'))
    else:
        lockCntThreshold = 5
    if sys_config.get('lock_time_threshold'):
        lockTimeThreshold = int(sys_config.get('lock_time_threshold'))
    else:
        lockTimeThreshold = 300

    # 服务端二次验证参数
    if username == "" or password == "" or username is None or password is None:
        result = {'status': 2, 'msg': '登录用户名或密码为空，请重新输入!', 'data': ''}
    elif username in login_failure_counter and login_failure_counter[username]["cnt"] >= lockCntThreshold and (
            datetime.datetime.now() - login_failure_counter[username][
        "last_failure_time"]).seconds <= lockTimeThreshold:
        log_mail_record('user:{},login failed, account locking...'.format(username))
        result = {'status': 3, 'msg': '登录失败超过5次，该账号已被锁定5分钟!', 'data': ''}
    else:
        # 登录
        user = authenticate(username=username, password=password)
        # 登录成功
        if user:
            # 如果登录失败计数器中存在该用户名，则清除之
            if username in login_failure_counter:
                login_failure_counter.pop(username)
            result = {'status': 0, 'msg': 'ok', 'data': user}
        # 登录失败
        else:
            if username not in login_failure_counter:
                # 第一次登录失败，登录失败计数器中不存在该用户，则创建一个该用户的计数器
                login_failure_counter[username] = {"cnt": 1, "last_failure_time": datetime.datetime.now()}
            else:
                if (datetime.datetime.now() - login_failure_counter[username][
                    "last_failure_time"]).seconds <= lockTimeThreshold:
                    login_failure_counter[username]["cnt"] += 1
                else:
                    # 上一次登录失败时间早于5分钟前，则重新计数。以达到超过5分钟自动解锁的目的。
                    login_failure_counter[username]["cnt"] = 1
                login_failure_counter[username]["last_failure_time"] = datetime.datetime.now()
            result = {'status': 1, 'msg': '用户名或密码错误，请重新输入！', 'data': ''}
    return result


# ajax接口，登录页面调用，用来验证用户名密码
@csrf_exempt
def authenticateEntry(request):
    """接收http请求，然后把请求中的用户名密码传给loginAuthenticate去验证"""
    username = request.POST.get('username')
    password = request.POST.get('password')

    result = loginAuthenticate(username, password)
    if result['status'] == 0:
        user = result.get('data')
        # 开启LDAP的认证通过后更新用户密码
        if settings.ENABLE_LDAP:
            try:
                users.objects.get(username=username)
            except Exception:
                insert_info = users()
                insert_info.password = make_password(password)
                insert_info.save()
            else:
                replace_info = users.objects.get(username=username)
                replace_info.password = make_password(password)
                replace_info.save()

        # 调用了django内置登录方法，防止管理后台二次登录
        user = authenticate(username=username, password=password)
        if user:
            login(request, user)

        result = {'status': 0, 'msg': 'ok', 'data': None}

    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取审核列表
@csrf_exempt
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
            listWorkflow = workflow.objects.filter(
                Q(engineer_display__contains=search) | Q(workflow_name__contains=search)
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer_display", "status",
                                                            "is_backup", "create_time", "cluster_name", "db_name",
                                                            "group_name", "sql_syntax")
            listWorkflowCount = workflow.objects.filter(
                Q(engineer_display__contains=search) | Q(workflow_name__contains=search)).count()
        else:
            listWorkflow = workflow.objects.filter(
                Q(engineer=user.username) | Q(review_man__contains=user.username)
            ).filter(
                Q(engineer_display__contains=search) | Q(workflow_name__contains=search)
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer_display", "status",
                                                            "is_backup", "create_time", "cluster_name", "db_name",
                                                            "group_name", "sql_syntax")
            listWorkflowCount = workflow.objects.filter(
                Q(engineer=user.username) | Q(review_man__contains=user.username)).filter(
                Q(engineer_display__contains=search) | Q(workflow_name__contains=search)
            ).count()
    elif navStatus in Const.workflowStatus.keys():
        if user.is_superuser == 1:
            listWorkflow = workflow.objects.filter(
                status=Const.workflowStatus[navStatus]
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer_display", "status",
                                                            "is_backup", "create_time", "cluster_name", "db_name",
                                                            "group_name", "sql_syntax")
            listWorkflowCount = workflow.objects.filter(status=Const.workflowStatus[navStatus]).count()
        else:
            listWorkflow = workflow.objects.filter(
                status=Const.workflowStatus[navStatus]
            ).filter(
                Q(engineer=user.username) | Q(review_man__contains=user.username)
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer_display", "status",
                                                            "is_backup", "create_time", "cluster_name", "db_name",
                                                            "group_name", "sql_syntax")
            listWorkflowCount = workflow.objects.filter(
                status=Const.workflowStatus[navStatus]
            ).filter(
                Q(engineer=user.username) | Q(review_man__contains=user.username)).count()
    else:
        context = {'errMsg': '传入的navStatus参数有误！'}
        return render(request, 'error.html', context)

    # QuerySet 序列化
    rows = [row for row in listWorkflow]

    result = {"total": listWorkflowCount, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 提交SQL给inception进行自动审核
@csrf_exempt
def simplecheck(request):
    sqlContent = request.POST.get('sql_content')
    clusterName = request.POST.get('cluster_name')
    db_name = request.POST.get('db_name')

    finalResult = {'status': 0, 'msg': 'ok', 'data': {}}
    # 服务器端参数验证
    if sqlContent is None or clusterName is None or db_name is None:
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
        result = InceptionDao().sqlautoReview(sqlContent, clusterName, db_name)
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


def getSqlSHA1(workflowId):
    """调用django ORM从数据库里查出review_content，从其中获取sqlSHA1值"""
    workflowDetail = get_object_or_404(workflow, pk=workflowId)
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


@csrf_exempt
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
            execute_result = workflow.objects.get(id=workflowId).execute_result
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


@csrf_exempt
def getWorkflowStatus(request):
    """获取某个工单的当前状态"""
    workflowId = request.POST['workflowid']
    if workflowId == '' or workflowId is None:
        context = {"status": -1, 'msg': 'workflowId参数为空.', "data": ""}
        return HttpResponse(json.dumps(context), content_type='application/json')

    workflowId = int(workflowId)
    workflowDetail = get_object_or_404(workflow, pk=workflowId)
    workflowStatus = workflowDetail.status
    result = {"status": workflowStatus, "msg": "", "data": ""}
    return HttpResponse(json.dumps(result), content_type='application/json')


@csrf_exempt
def stopOscProgress(request):
    """中止该SQL的pt-OSC进程"""
    workflowId = request.POST['workflowid']
    sqlID = request.POST['sqlID']
    if workflowId == '' or workflowId is None or sqlID == '' or sqlID is None:
        context = {"status": -1, 'msg': 'workflowId或sqlID参数为空.', "data": ""}
        return HttpResponse(json.dumps(context), content_type='application/json')

    user = request.user
    workflowDetail = workflow.objects.get(id=workflowId)
    try:
        reviewMan = json.loads(workflowDetail.review_man)
    except ValueError:
        reviewMan = (workflowDetail.review_man,)
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


# 获取SQLAdvisor的优化结果
@csrf_exempt
def sqladvisorcheck(request):
    sqlContent = request.POST.get('sql_content')
    clusterName = request.POST.get('cluster_name')
    dbName = request.POST.get('db_name')
    verbose = request.POST.get('verbose')
    finalResult = {'status': 0, 'msg': 'ok', 'data': []}

    # 服务器端参数验证
    if sqlContent is None or clusterName is None:
        finalResult['status'] = 1
        finalResult['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')

    sqlContent = sqlContent.strip()
    if sqlContent[-1] != ";":
        finalResult['status'] = 1
        finalResult['msg'] = 'SQL语句结尾没有以;结尾，请重新修改并提交！'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')
    try:
        user_masters(request.user).get(cluster_name=clusterName)
    except Exception:
        finalResult['status'] = 1
        finalResult['msg'] = '你所在组未关联该主库！'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')

    if verbose is None or verbose == '':
        verbose = 1

    # 取出主库的连接信息
    cluster_info = master_config.objects.get(cluster_name=clusterName)

    # 提交给sqladvisor获取审核结果
    sqladvisor_path = SysConfig().sys_config.get('sqladvisor')
    sqlContent = sqlContent.strip().replace('"', '\\"').replace('`', '\`').replace('\n', ' ')
    try:
        p = subprocess.Popen(sqladvisor_path + ' -h "%s" -P "%s" -u "%s" -p "%s\" -d "%s" -v %s -q "%s"' % (
            str(cluster_info.master_host), str(cluster_info.master_port), str(cluster_info.master_user),
            str(prpCryptor.decrypt(cluster_info.master_password), ), str(dbName), verbose, sqlContent),
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
        stdout, stderr = p.communicate()
        finalResult['data'] = stdout
    except Exception:
        finalResult['data'] = 'sqladvisor运行报错，请联系管理员'
    return HttpResponse(json.dumps(finalResult), content_type='application/json')


# 获取审核列表
@csrf_exempt
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


# 修改系统配置
@csrf_exempt
@superuser_required
def changeconfig(request):
    configs = request.POST.get('configs')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # 清空并替换
    try:
        with transaction.atomic():
            Config.objects.all().delete()
            Config.objects.bulk_create(
                [Config(item=items['key'], value=items['value']) for items in json.loads(configs)])
    except Exception as e:
        result['status'] = 1
        result['msg'] = str(e)

    # 返回结果
    return HttpResponse(json.dumps(result), content_type='application/json')
