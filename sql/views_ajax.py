# -*- coding: UTF-8 -*- 

import re
import json
import datetime
import multiprocessing

import subprocess

from django.contrib.auth import authenticate, login
from django.db.models import Q
from django.db import transaction
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password
if settings.ENABLE_LDAP:
    from django_auth_ldap.backend import LDAPBackend

from django.core import serializers
from .dao import Dao
from .const import Const, WorkflowDict
from .inception import InceptionDao
from .aes_decryptor import Prpcrypt
from .models import users, master_config, workflow
from sql.sendmail import MailSender
import logging
from .workflow import Workflow
from .query import query_audit_call_back, DateEncoder

logger = logging.getLogger('default')
mailSender = MailSender()
dao = Dao()
inceptionDao = InceptionDao()
prpCryptor = Prpcrypt()
login_failure_counter = {} #登录失败锁定计数器，给loginAuthenticate用的
sqlSHA1_cache = {} #存储SQL文本与SHA1值的对应关系，尽量减少与数据库的交互次数,提高效率。格式: {工单ID1:{SQL内容1:sqlSHA1值1, SQL内容2:sqlSHA1值2},}
workflowOb = Workflow()

def log_mail_record(login_failed_message):
    mail_title = 'login inception'
    logger.warning(login_failed_message)
    if getattr(settings, 'MAIL_ON_OFF') == "on":
        mailSender.sendEmail(mail_title, login_failed_message, getattr(settings, 'MAIL_REVIEW_SECURE_ADDR'))

#ajax接口，登录页面调用，用来验证用户名密码
@csrf_exempt
def loginAuthenticate(username, password):
    """登录认证，包含一个登录失败计数器，5分钟内连续失败5次的账号，会被锁定5分钟"""
    lockCntThreshold = settings.LOCK_CNT_THRESHOLD
    lockTimeThreshold = settings.LOCK_TIME_THRESHOLD

    #服务端二次验证参数
    strUsername = username
    strPassword = password

    if strUsername == "" or strPassword == "" or strUsername is None or strPassword is None:
        result = {'status':2, 'msg':'登录用户名或密码为空，请重新输入!', 'data':''}
    elif strUsername in login_failure_counter and login_failure_counter[strUsername]["cnt"] >= lockCntThreshold and (datetime.datetime.now() - login_failure_counter[strUsername]["last_failure_time"]).seconds <= lockTimeThreshold:
        log_mail_record('user:{},login failed, account locking...'.format(strUsername))
        result = {'status':3, 'msg':'登录失败超过5次，该账号已被锁定5分钟!', 'data':''}
    else:
        correct_users = users.objects.filter(username=strUsername)
        if len(correct_users) == 1 and correct_users[0].is_active and check_password(strPassword, correct_users[0].password) == True:
            #调用了django内置函数check_password函数检测输入的密码是否与django默认的PBKDF2算法相匹配
            if strUsername in login_failure_counter:
                #如果登录失败计数器中存在该用户名，则清除之
                login_failure_counter.pop(strUsername)
            result = {'status':0, 'msg':'ok', 'data':''}
        else:
            if strUsername not in login_failure_counter:
                #第一次登录失败，登录失败计数器中不存在该用户，则创建一个该用户的计数器
                login_failure_counter[strUsername] = {"cnt":1, "last_failure_time":datetime.datetime.now()}
            else:
                if (datetime.datetime.now() - login_failure_counter[strUsername]["last_failure_time"]).seconds <= lockTimeThreshold:
                    login_failure_counter[strUsername]["cnt"] += 1
                else:
                    #上一次登录失败时间早于5分钟前，则重新计数。以达到超过5分钟自动解锁的目的。
                    login_failure_counter[strUsername]["cnt"] = 1
                login_failure_counter[strUsername]["last_failure_time"] = datetime.datetime.now()
            log_mail_record('user:{},login failed, fail count:{}'.format(strUsername,login_failure_counter[strUsername]["cnt"]))
            result = {'status':1, 'msg':'用户名或密码错误，请重新输入！', 'data':''}
    return result

#ajax接口，登录页面调用，用来验证用户名密码
@csrf_exempt
def authenticateEntry(request):
    """接收http请求，然后把请求中的用户名密码传给loginAuthenticate去验证"""
    if request.is_ajax():
        strUsername = request.POST.get('username')
        strPassword = request.POST.get('password')
    else:
        strUsername = request.POST['username']
        strPassword = request.POST['password']

    lockCntThreshold = settings.LOCK_CNT_THRESHOLD
    lockTimeThreshold = settings.LOCK_TIME_THRESHOLD

    if settings.ENABLE_LDAP:
        ldap = LDAPBackend()
        user = ldap.authenticate(username=strUsername, password=strPassword)
        if strUsername in login_failure_counter and login_failure_counter[strUsername]["cnt"] >= lockCntThreshold and (
                datetime.datetime.now() - login_failure_counter[strUsername][
            "last_failure_time"]).seconds <= lockTimeThreshold:
            log_mail_record('user:{},login failed, account locking...'.format(strUsername))
            result = {'status': 3, 'msg': '登录失败超过5次，该账号已被锁定5分钟!', 'data': ''}
            return HttpResponse(json.dumps(result), content_type='application/json')
        if user and user.is_active:
            request.session['login_username'] = strUsername
            # 登录管理后台，避免二次登录
            user = authenticate(username=strUsername, password=strPassword)
            if user:
                login(request, user)
            result = {'status': 0, 'msg': 'ok', 'data': ''}
            return HttpResponse(json.dumps(result), content_type='application/json')

    result = loginAuthenticate(strUsername, strPassword)
    if result['status'] == 0:
        request.session['login_username'] = strUsername
        # 登录管理后台，避免二次登录
        user = authenticate(username=strUsername, password=strPassword)
        if user:
            login(request, user)

    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取审核列表
@csrf_exempt
def sqlworkflow(request):
    # 获取用户信息
    loginUser = request.session.get('login_username', False)

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
    loginUserOb = users.objects.get(username=loginUser)

    # 全部工单里面包含搜索条件,待审核前置
    if navStatus == 'all':
        if loginUserOb.is_superuser == 1:
            listWorkflow = workflow.objects.filter(
                Q(engineer__contains=search) | Q(workflow_name__contains=search)
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer", "status",
                                                            "is_backup", "create_time", "cluster_name")
            listWorkflowCount = workflow.objects.filter(
                Q(engineer__contains=search) | Q(workflow_name__contains=search)).count()
        else:
            listWorkflow = workflow.objects.filter(
                Q(engineer=loginUser) | Q(review_man__contains=loginUser)
            ).filter(
                Q(engineer__contains=search) | Q(workflow_name__contains=search)
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer", "status",
                                                            "is_backup", "create_time", "cluster_name")
            listWorkflowCount = workflow.objects.filter(
                Q(engineer=loginUser) | Q(review_man__contains=loginUser)).filter(
                Q(engineer__contains=search) | Q(workflow_name__contains=search)
            ).count()
    elif navStatus in Const.workflowStatus.keys():
        if loginUserOb.is_superuser == 1:
            listWorkflow = workflow.objects.filter(
                status=Const.workflowStatus[navStatus]
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer", "status",
                                                            "is_backup", "create_time", "cluster_name")
            listWorkflowCount = workflow.objects.filter(status=Const.workflowStatus[navStatus]).count()
        else:
            listWorkflow = workflow.objects.filter(
                status=Const.workflowStatus[navStatus]
            ).filter(
                Q(engineer=loginUser) | Q(review_man__contains=loginUser)
            ).order_by('-create_time')[offset:limit].values("id", "workflow_name", "engineer", "status",
                                                            "is_backup", "create_time", "cluster_name")
            listWorkflowCount = workflow.objects.filter(
                status=Const.workflowStatus[navStatus]
            ).filter(
                Q(engineer=loginUser) | Q(review_man__contains=loginUser)).count()
    else:
        context = {'errMsg': '传入的navStatus参数有误！'}
        return render(request, 'error.html', context)

    # QuerySet 序列化
    rows = [row for row in listWorkflow]

    result = {"total": listWorkflowCount, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=DateEncoder), content_type='application/json')


#提交SQL给inception进行自动审核
@csrf_exempt
def simplecheck(request):
    if request.is_ajax():
        sqlContent = request.POST.get('sql_content')
        clusterName = request.POST.get('cluster_name')
    else:
        sqlContent = request.POST['sql_content']
        clusterName = request.POST['cluster_name']

    finalResult = {'status':0, 'msg':'ok', 'data':{}}
    #服务器端参数验证
    if sqlContent is None or clusterName is None:
        finalResult['status'] = 1
        finalResult['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')

    sqlContent = sqlContent.rstrip()
    if sqlContent[-1] != ";":
        finalResult['status'] = 1
        finalResult['msg'] = 'SQL语句结尾没有以;结尾，请重新修改并提交！'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')
    #交给inception进行自动审核
    result = inceptionDao.sqlautoReview(sqlContent, clusterName)
    if result is None or len(result) == 0:
        finalResult['status'] = 1
        finalResult['msg'] = 'inception返回的结果集为空！可能是SQL语句有语法错误'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')
    #要把result转成JSON存进数据库里，方便SQL单子详细信息展示
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
        row['sqlsha1'] = row_item[10]
        rows.append(row)
    finalResult['data']['rows'] = rows
    finalResult['data']['column_list'] = column_list
    finalResult['data']['CheckWarningCount'] = CheckWarningCount
    finalResult['data']['CheckErrorCount'] = CheckErrorCount

    return HttpResponse(json.dumps(finalResult), content_type='application/json')

#同步ldap用户到数据库
@csrf_exempt
def syncldapuser(request):
    ldapback = LDAPBackend()
    ldap = ldapback.ldap
    ldapconn = ldap.initialize(settings.AUTH_LDAP_SERVER_URI)
    tls = getattr(settings, 'AUTH_LDAP_START_TLS', None)
    if tls:
        ldapconn.start_tls_s()
    binddn = settings.AUTH_LDAP_BIND_DN
    bind_password = settings.AUTH_LDAP_BIND_PASSWORD
    basedn = settings.AUTH_LDAP_BASEDN
    ldapconn.simple_bind_s(binddn, bind_password)
    ldapusers = ldapconn.search_s(basedn, ldap.SCOPE_SUBTREE, 'objectclass=*', attrlist=settings.AUTH_LDAP_USER_ATTRLIST)
    username_field = settings.AUTH_LDAP_USER_ATTR_MAP['username']
    display_field = settings.AUTH_LDAP_USER_ATTR_MAP['display']
    email_field = settings.AUTH_LDAP_USER_ATTR_MAP['email']
    count = 0
    for user in ldapusers:
        user_attr = user[1]
        if user_attr:
            username = user_attr[username_field][0]
            display = user_attr[display_field][0]
            email = user_attr[email_field][0]
            already_user = users.objects.filter(username=username.decode()).filter(is_ldapuser=True)
            if len(already_user) == 0:
                u = users(username=username.decode(), display=display.decode(), email=email.decode(), is_ldapuser=True)
                u.save()
                count += 1
    result = {'msg': '同步{}个用户。'.format(count)}
    return HttpResponse(json.dumps(result), content_type='application/json')

#请求图表数据
@csrf_exempt
def getMonthCharts(request):
    result = dao.getWorkChartsByMonth()
    return HttpResponse(json.dumps(result), content_type='application/json')

@csrf_exempt
def getPersonCharts(request):
    result = dao.getWorkChartsByPerson()
    return HttpResponse(json.dumps(result), content_type='application/json')

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
        context = {"status":-1 ,'msg': 'workflowId或sqlID参数为空.', "data":""}
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
        result = inceptionDao.getOscPercent(sqlSHA1)  #成功获取到SHA1值，去inception里面查询进度
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
            if type(listExecResult) == list and len(listExecResult) >= sqlID-1:
                if dictSHA1[sqlID] in listExecResult[sqlID-1][10]:
                    # 已经执行完毕，进度值置为100
                    pctResult = {"status":0, "msg":"ok", "data":{"percent":100, "timeRemained":""}}
            else:
                # 可能因为前一条SQL是DML，正在执行中；或者还没执行到这一行。但是status返回的是4，而当前SQL实际上还未开始执行。这里建议前端进行重试
                pctResult = {"status":-3, "msg":"进度未知", "data":{"percent":-100, "timeRemained":""}}
    elif dictSHA1 != {} and sqlID not in dictSHA1:
        pctResult = {"status":4, "msg":"该行SQL不是由pt-OSC执行的", "data":""}
    else:
        pctResult = {"status":-2, "msg":"整个工单不由pt-OSC执行", "data":""}
    return HttpResponse(json.dumps(pctResult), content_type='application/json')

@csrf_exempt
def getWorkflowStatus(request):
    """获取某个工单的当前状态"""
    workflowId = request.POST['workflowid']
    if workflowId == '' or workflowId is None :
        context = {"status":-1 ,'msg': 'workflowId参数为空.', "data":""}
        return HttpResponse(json.dumps(context), content_type='application/json')

    workflowId = int(workflowId)
    workflowDetail = get_object_or_404(workflow, pk=workflowId)
    workflowStatus = workflowDetail.status
    result = {"status":workflowStatus, "msg":"", "data":""}
    return HttpResponse(json.dumps(result), content_type='application/json')

@csrf_exempt
def stopOscProgress(request):
    """中止该SQL的pt-OSC进程"""
    workflowId = request.POST['workflowid']
    sqlID = request.POST['sqlID']
    if workflowId == '' or workflowId is None or sqlID == '' or sqlID is None:
        context = {"status":-1 ,'msg': 'workflowId或sqlID参数为空.', "data":""}
        return HttpResponse(json.dumps(context), content_type='application/json')

    loginUser = request.session.get('login_username', False)
    workflowDetail = workflow.objects.get(id=workflowId)
    try:
        listAllReviewMen = json.loads(workflowDetail.review_man)
    except ValueError:
        listAllReviewMen = (workflowDetail.review_man, )
    #服务器端二次验证，当前工单状态必须为等待人工审核,正在执行人工审核动作的当前登录用户必须为审核人. 避免攻击或被接口测试工具强行绕过
    if workflowDetail.status != Const.workflowStatus['executing']:
        context = {"status":-1, "msg":'当前工单状态不是"执行中"，请刷新当前页面！', "data":""}
        return HttpResponse(json.dumps(context), content_type='application/json')
    if loginUser is None or loginUser not in listAllReviewMen:
        context = {"status":-1 ,'msg': '当前登录用户不是审核人，请重新登录.', "data":""}
        return HttpResponse(json.dumps(context), content_type='application/json')

    workflowId = int(workflowId)
    sqlID = int(sqlID)
    if workflowId in sqlSHA1_cache:
        dictSHA1 = sqlSHA1_cache[workflowId]
    else:
        dictSHA1 = getSqlSHA1(workflowId)
    if dictSHA1 != {} and sqlID in dictSHA1:
        sqlSHA1 = dictSHA1[sqlID]
        optResult = inceptionDao.stopOscProgress(sqlSHA1)
    else:
        optResult = {"status":4, "msg":"不是由pt-OSC执行的", "data":""}
    return HttpResponse(json.dumps(optResult), content_type='application/json')

# 获取SQLAdvisor的优化结果
@csrf_exempt
def sqladvisorcheck(request):
    if request.is_ajax():
        sqlContent = request.POST.get('sql_content')
        clusterName = request.POST.get('cluster_name')
        dbName = request.POST.get('db_name')
        verbose = request.POST.get('verbose')
    else:
        sqlContent = request.POST['sql_content']
        clusterName = request.POST['cluster_name']
        dbName = request.POST.POST['db_name']
        verbose = request.POST.POST['verbose']
    finalResult = {'status': 0, 'msg': 'ok', 'data': []}

    # 服务器端参数验证
    if sqlContent is None or clusterName is None:
        finalResult['status'] = 1
        finalResult['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')

    sqlContent = sqlContent.rstrip()
    if sqlContent[-1] != ";":
        finalResult['status'] = 1
        finalResult['msg'] = 'SQL语句结尾没有以;结尾，请重新修改并提交！'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')

    if verbose is None or verbose == '':
        verbose = 1

    # 取出主库的连接信息
    cluster_info = master_config.objects.get(cluster_name=clusterName)

    # 提交给sqladvisor获取审核结果
    sqladvisor_path = getattr(settings, 'SQLADVISOR')
    sqlContent = sqlContent.rstrip().replace('"', '\\"').replace('`', '\`').replace('\n', ' ')
    try:
        p = subprocess.Popen(sqladvisor_path + ' -h "%s" -P "%s" -u "%s" -p "%s\" -d "%s" -v %s -q "%s"' % (
            str(cluster_info.master_host), str(cluster_info.master_port), str(cluster_info.master_user),
            str(prpCryptor.decrypt(cluster_info.master_password),), str(dbName), verbose, sqlContent), stdin=subprocess.PIPE,
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
    loginUser = request.session.get('login_username', False)
    loginUserOb = users.objects.get(username=loginUser)

    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    workflow_type = int(request.POST.get('workflow_type'))
    limit = offset + limit

    # 获取搜索参数
    search = request.POST.get('search')
    if search is None:
        search = ''

    # 调用工作流接口获取审核列表
    result = workflowOb.auditlist(loginUserOb, workflow_type, offset, limit, search)
    auditlist = result['data']['auditlist']
    auditlistCount = result['data']['auditlistCount']

    # QuerySet 序列化
    auditlist = serializers.serialize("json", auditlist)
    auditlist = json.loads(auditlist)
    list = []
    for i in range(len(auditlist)):
        auditlist[i]['fields']['id'] = auditlist[i]['pk']
        list.append(auditlist[i]['fields'])
    result = {"total": auditlistCount, "rows": list}

    result = {"total": auditlistCount, "rows": list}
    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 工单审核
@csrf_exempt
def workflowaudit(request):
    # 获取用户信息
    loginUser = request.session.get('login_username', False)
    result = {'status': 0, 'msg': 'ok', 'data': []}

    audit_id = int(request.POST['audit_id'])
    audit_status = int(request.POST['audit_status'])
    audit_remark = request.POST['audit_remark']

    # 获取审核信息
    auditInfo = workflowOb.auditinfo(audit_id)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 调用工作流接口审核
            auditresult = workflowOb.auditworkflow(audit_id, audit_status, loginUser, audit_remark)

            # 按照审核结果更新业务表审核状态
            if auditresult['status'] == 0:
                if auditInfo.workflow_type == WorkflowDict.workflow_type['query']:
                    # 更新业务表审核状态,插入权限信息
                    query_audit_call_back(auditInfo.workflow_id, auditresult['data']['workflow_status'])

                    # 给拒绝和审核通过的申请人发送邮件
                    if hasattr(settings, 'MAIL_ON_OFF') is True and getattr(settings, 'MAIL_ON_OFF') == "on":
                        email_reciver = users.objects.get(username=auditInfo.create_user).email

                        email_content = "发起人：" + auditInfo.create_user + "\n审核人：" + auditInfo.audit_users \
                                        + "\n工单地址：" + request.scheme + "://" + request.get_host() + "/workflowdetail/" \
                                        + str(audit_id) + "\n工单名称： " + auditInfo.workflow_title \
                                        + "\n审核备注： " + audit_remark
                        if auditresult['data']['workflow_status'] == WorkflowDict.workflow_status['audit_success']:
                            email_title = "工单审核通过 # " + str(auditInfo.audit_id)
                            mailSender.sendEmail(email_title, email_content, [email_reciver])
                        elif auditresult['data']['workflow_status'] == WorkflowDict.workflow_status['audit_reject']:
                            email_title = "工单被驳回 # " + str(auditInfo.audit_id)
                            mailSender.sendEmail(email_title, email_content, [email_reciver])
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)
    else:
        result = auditresult
    return HttpResponse(json.dumps(result), content_type='application/json')
