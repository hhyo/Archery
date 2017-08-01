# -*- coding: UTF-8 -*- 

import re
import json
import time
import multiprocessing
from collections import OrderedDict

from django.db.models import Q
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password

from .dao import Dao
from .const import Const
from .sendmail import MailSender
from .inception import InceptionDao
from .aes_decryptor import Prpcrypt
from .models import users, master_config, workflow

dao = Dao()
inceptionDao = InceptionDao()
mailSender = MailSender()
prpCryptor = Prpcrypt()

def login(request):
    return render(request, 'login.html')

def logout(request):
    if request.session.get('login_username', False):
        del request.session['login_username']
    return render(request, 'login.html')

#首页，也是查看所有SQL工单页面，具备翻页功能
def allworkflow(request):
    #一个页面展示
    PAGE_LIMIT = 12

    pageNo = 0
    navStatus = ''
    listAllWorkflow = []

    #参数检查
    if 'pageNo' in request.GET:
        pageNo = request.GET['pageNo']
    else:
        pageNo = '0'
    
    if 'navStatus' in request.GET:
        navStatus = request.GET['navStatus']
    else:
        navStatus = 'all'
    if not isinstance(pageNo, str) or not isinstance(navStatus, str):
        raise TypeError('pageNo或navStatus页面传入参数不对')
    else:
        try:
            pageNo = int(pageNo)
            if pageNo < 0:
                pageNo = 0
        except ValueError as ve:
            context = {'errMsg': 'pageNo参数不是int.'}
            return render(request, 'error.html', context)

    loginUser = request.session.get('login_username', False)
    #查询workflow model，根据pageNo和navStatus获取对应的内容
    offset = pageNo * PAGE_LIMIT
    limit = offset + PAGE_LIMIT

    #修改全部工单、审核不通过、已执行完毕界面工程师只能看到自己发起的工单，审核人可以看到全部
    listWorkflow = []
    #查询全部流程
    loginUserOb = users.objects.get(username=loginUser)
    role = loginUserOb.role
    if navStatus == 'all' and role == '审核人':
        #这句话等同于select * from sql_workflow order by create_time desc limit {offset, limit};
        listWorkflow = workflow.objects.exclude(status=Const.workflowStatus['autoreviewwrong']).order_by('-create_time')[offset:limit]
    elif navStatus == 'all' and role == '工程师':
        listWorkflow = workflow.objects.filter(Q(engineer=loginUser) | Q(status=Const.workflowStatus['autoreviewwrong']), engineer=loginUser).order_by('-create_time')[offset:limit]
    elif navStatus == 'waitingforme':
        listWorkflow = workflow.objects.filter(Q(status=Const.workflowStatus['manreviewing'], review_man=loginUser) | Q(status=Const.workflowStatus['manreviewing'], review_man__contains='"' + loginUser + '"')).order_by('-create_time')[offset:limit]
    elif navStatus == 'finish' and role == '审核人':
        listWorkflow = workflow.objects.filter(status=Const.workflowStatus['finish']).order_by('-create_time')[offset:limit]
    elif navStatus == 'finish' and role == '工程师':
        listWorkflow = workflow.objects.filter(status=Const.workflowStatus['finish'], engineer=loginUser).order_by('-create_time')[offset:limit]
    elif navStatus == 'executing' and role == '审核人':
        listWorkflow = workflow.objects.filter(status=Const.workflowStatus['executing']).order_by('-create_time')[offset:limit]
    elif navStatus == 'executing' and role == '工程师':
        listWorkflow = workflow.objects.filter(status=Const.workflowStatus['executing'], engineer=loginUser).order_by('-create_time')[offset:limit]
    elif navStatus == 'abort' and role == '审核人':
        listWorkflow = workflow.objects.filter(status=Const.workflowStatus['abort']).order_by('-create_time')[offset:limit]
    elif navStatus == 'abort' and role == '工程师':
        listWorkflow = workflow.objects.filter(status=Const.workflowStatus['abort'], engineer=loginUser).order_by('-create_time')[offset:limit]
    elif navStatus == 'autoreviewwrong' and role == '审核人':
        listWorkflow = workflow.objects.filter(status=Const.workflowStatus['autoreviewwrong']).order_by('-create_time')[offset:limit]
    elif navStatus == 'autoreviewwrong' and role == '工程师':
        listWorkflow = workflow.objects.filter(status=Const.workflowStatus['autoreviewwrong'], engineer=loginUser).order_by('-create_time')[offset:limit]
    else:
        context = {'errMsg': '传入的navStatus参数有误！'}
        return render(request, 'error.html', context)


    context = {'currentMenu':'allworkflow', 'listWorkflow':listWorkflow, 'pageNo':pageNo, 'navStatus':navStatus, 'PAGE_LIMIT':PAGE_LIMIT, 'role':role}
    return render(request, 'allWorkflow.html', context)

#提交SQL的页面
def submitSql(request):
    masters = master_config.objects.all().order_by('cluster_name')
    if len(masters) == 0:
       context = {'errMsg': '集群数为0，可能后端数据没有配置集群'}
       return render(request, 'error.html', context) 
    
    #获取所有集群名称
    listAllClusterName = [master.cluster_name for master in masters]

    dictAllClusterDb = OrderedDict()
    #每一个都首先获取主库地址在哪里
    for clusterName in listAllClusterName:
        listMasters = master_config.objects.filter(cluster_name=clusterName)
        if len(listMasters) != 1:
            context = {'errMsg': '存在两个集群名称一样的集群，请修改数据库'}
            return render(request, 'error.html', context)
        #取出该集群的名称以及连接方式，为了后面连进去获取所有databases
        masterHost = listMasters[0].master_host
        masterPort = listMasters[0].master_port
        masterUser = listMasters[0].master_user
        masterPassword = prpCryptor.decrypt(listMasters[0].master_password)

        listDb = dao.getAlldbByCluster(masterHost, masterPort, masterUser, masterPassword)
        dictAllClusterDb[clusterName] = listDb

    #获取所有审核人，当前登录用户不可以审核
    loginUser = request.session.get('login_username', False)
    reviewMen = users.objects.filter(role='审核人').exclude(username=loginUser)
    if len(reviewMen) == 0:
       context = {'errMsg': '审核人为0，请配置审核人'}
       return render(request, 'error.html', context) 
    listAllReviewMen = [user.username for user in reviewMen]
  
    context = {'currentMenu':'submitsql', 'dictAllClusterDb':dictAllClusterDb, 'reviewMen':reviewMen}
    return render(request, 'submitSql.html', context)

#提交SQL给inception进行解析
def autoreview(request):
    workflowid = request.POST.get('workflowid')
    sqlContent = request.POST['sql_content']
    workflowName = request.POST['workflow_name']
    clusterName = request.POST['cluster_name']
    isBackup = request.POST['is_backup']
    reviewMan = request.POST['review_man']
    subReviewMen = request.POST.get('sub_review_man', '')
    listAllReviewMen = (reviewMan, subReviewMen)
   
    #服务器端参数验证
    if sqlContent is None or workflowName is None or clusterName is None or isBackup is None or reviewMan is None:
        context = {'errMsg': '页面提交参数可能为空'}
        return render(request, 'error.html', context)
    sqlContent = sqlContent.rstrip()
    if sqlContent[-1] != ";":
        context = {'errMsg': "SQL语句结尾没有以;结尾，请后退重新修改并提交！"}
        return render(request, 'error.html', context)
 
    #交给inception进行自动审核
    result = inceptionDao.sqlautoReview(sqlContent, clusterName)
    if result is None or len(result) == 0:
        context = {'errMsg': 'inception返回的结果集为空！可能是SQL语句有语法错误'}
        return render(request, 'error.html', context)
    #要把result转成JSON存进数据库里，方便SQL单子详细信息展示
    jsonResult = json.dumps(result)

    #遍历result，看是否有任何自动审核不通过的地方，一旦有，则为自动审核不通过；没有的话，则为等待人工审核状态
    workflowStatus = Const.workflowStatus['manreviewing']
    for row in result:
        if row[2] == 2:
            #状态为2表示严重错误，必须修改
            workflowStatus = Const.workflowStatus['autoreviewwrong']
            break
        elif re.match(r"\w*comments\w*", row[4]):
            workflowStatus = Const.workflowStatus['autoreviewwrong']
            break

    #存进数据库里
    engineer = request.session.get('login_username', False)
    if not workflowid:
        Workflow = workflow()
        Workflow.create_time = getNow()
    else:
        Workflow = workflow.objects.get(id=int(workflowid))
    Workflow.workflow_name = workflowName
    Workflow.engineer = engineer
    Workflow.review_man = json.dumps(listAllReviewMen, ensure_ascii=False)
    Workflow.status = workflowStatus
    Workflow.is_backup = isBackup
    Workflow.review_content = jsonResult
    Workflow.cluster_name = clusterName
    Workflow.sql_content = sqlContent
    Workflow.execute_result = ''
    Workflow.save()
    workflowId = Workflow.id

    #自动审核通过了，才发邮件
    if workflowStatus == Const.workflowStatus['manreviewing']:
        #如果进入等待人工审核状态了，则根据settings.py里的配置决定是否给审核人发一封邮件提醒.
        if hasattr(settings, 'MAIL_ON_OFF') == True:
            if getattr(settings, 'MAIL_ON_OFF') == "on":
                url = _getDetailUrl(request) + str(workflowId) + '/'

                #发一封邮件
                strTitle = "新的SQL上线工单提醒 # " + str(workflowId)
                objEngineer = users.objects.get(username=engineer)
                for reviewMan in listAllReviewMen:
                    if reviewMan == "":
                        continue
                    strContent = "发起人：" + engineer + "\n审核人：" + reviewMan  + "\n工单地址：" + url + "\n工单名称： " + workflowName + "\n具体SQL：" + sqlContent
                    objReviewMan = users.objects.get(username=reviewMan)
                    mailSender.sendEmail(strTitle, strContent, [objReviewMan.email])
            else:
                #不发邮件
                pass
    
    return HttpResponseRedirect('/detail/' + str(workflowId) + '/') 

#展示SQL工单详细内容，以及可以人工审核，审核通过即可执行
def detail(request, workflowId):
    workflowDetail = get_object_or_404(workflow, pk=workflowId)
    if workflowDetail.status in (Const.workflowStatus['finish'], Const.workflowStatus['exception']):
        listContent = json.loads(workflowDetail.execute_result)
    else:
        listContent = json.loads(workflowDetail.review_content)
    try:
        listAllReviewMen = json.loads(workflowDetail.review_man)
    except ValueError:
        listAllReviewMen = (workflowDetail.review_man, )

    # 格式化detail界面sql语句和审核/执行结果 by 搬砖工
    for Content in listContent:
        Content[4] = Content[4].split('\n')     # 审核/执行结果
        Content[5] = Content[5].split('\r\n')   # sql语句
    context = {'currentMenu':'allworkflow', 'workflowDetail':workflowDetail, 'listContent':listContent,'listAllReviewMen':listAllReviewMen}
    return render(request, 'detail.html', context)

#人工审核也通过，执行SQL
def execute(request):
    workflowId = request.POST['workflowid']
    if workflowId == '' or workflowId is None:
        context = {'errMsg': 'workflowId参数为空.'}
        return render(request, 'error.html', context)
    
    workflowId = int(workflowId)
    workflowDetail = workflow.objects.get(id=workflowId)
    clusterName = workflowDetail.cluster_name
    try:
        listAllReviewMen = json.loads(workflowDetail.review_man)
    except ValueError:
        listAllReviewMen = (workflowDetail.review_man, )

    #服务器端二次验证，正在执行人工审核动作的当前登录用户必须为审核人. 避免攻击或被接口测试工具强行绕过
    loginUser = request.session.get('login_username', False)
    if loginUser is None or loginUser not in listAllReviewMen:
        context = {'errMsg': '当前登录用户不是审核人，请重新登录.'}
        return render(request, 'error.html', context)

    #服务器端二次验证，当前工单状态必须为等待人工审核
    if workflowDetail.status != Const.workflowStatus['manreviewing']:
        context = {'errMsg': '当前工单状态不是等待人工审核中，请刷新当前页面！'}
        return render(request, 'error.html', context)

    dictConn = getMasterConnStr(clusterName)

    #将流程状态修改为执行中，并更新reviewok_time字段
    workflowDetail.status = Const.workflowStatus['executing']
    workflowDetail.reviewok_time = getNow()
    #执行之前重新split并check一遍，更新SHA1缓存；因为如果在执行中，其他进程去做这一步操作的话，会导致inception core dump挂掉
    splitReviewResult = inceptionDao.sqlautoReview(workflowDetail.sql_content, workflowDetail.cluster_name, isSplit='yes')
    workflowDetail.review_content = json.dumps(splitReviewResult)
    workflowDetail.save()

    #交给inception先split，再执行
    (finalStatus, finalList) = inceptionDao.executeFinal(workflowDetail, dictConn)

    #封装成JSON格式存进数据库字段里
    strJsonResult = json.dumps(finalList)
    workflowDetail.execute_result = strJsonResult
    workflowDetail.finish_time = getNow()
    workflowDetail.status = finalStatus
    workflowDetail.save()

    #如果执行完毕了，则根据settings.py里的配置决定是否给提交者和DBA一封邮件提醒.DBA需要知晓审核并执行过的单子
    if hasattr(settings, 'MAIL_ON_OFF') == True:
        if getattr(settings, 'MAIL_ON_OFF') == "on":
            url = _getDetailUrl(request) + str(workflowId) + '/'

            #给主、副审核人，申请人，DBA各发一封邮件
            engineer = workflowDetail.engineer
            reviewMen = workflowDetail.review_man
            workflowStatus = workflowDetail.status
            workflowName = workflowDetail.workflow_name
            objEngineer = users.objects.get(username=engineer)
            strTitle = "SQL上线工单执行完毕 # " + str(workflowId)
            strContent = "发起人：" + engineer + "\n审核人：" + reviewMen + "\n工单地址：" + url + "\n工单名称： " + workflowName +"\n执行结果：" + workflowStatus
            mailSender.sendEmail(strTitle, strContent, [objEngineer.email])
            mailSender.sendEmail(strTitle, strContent, getattr(settings, 'MAIL_REVIEW_DBA_ADDR'))
            for reviewMan in listAllReviewMen:
                if reviewMan == "":
                    continue
                objReviewMan = users.objects.get(username=reviewMan)
                mailSender.sendEmail(strTitle, strContent, [objReviewMan.email])
        else:
            #不发邮件
            pass

    return HttpResponseRedirect('/detail/' + str(workflowId) + '/') 

#终止流程
def cancel(request):
    workflowId = request.POST['workflowid']
    if workflowId == '' or workflowId is None:
        context = {'errMsg': 'workflowId参数为空.'}
        return render(request, 'error.html', context)

    workflowId = int(workflowId)
    workflowDetail = workflow.objects.get(id=workflowId)
    reviewMan = workflowDetail.review_man
    try:
        listAllReviewMen = json.loads(reviewMan)
    except ValueError:
        listAllReviewMen = (reviewMan, )

    #服务器端二次验证，如果正在执行终止动作的当前登录用户，不是发起人也不是审核人，则异常.
    loginUser = request.session.get('login_username', False)
    if loginUser is None or (loginUser not in listAllReviewMen and loginUser != workflowDetail.engineer):
        context = {'errMsg': '当前登录用户不是审核人也不是发起人，请重新登录.'}
        return render(request, 'error.html', context)

    #服务器端二次验证，如果当前单子状态是结束状态，则不能发起终止
    if workflowDetail.status in (Const.workflowStatus['abort'], Const.workflowStatus['finish'], Const.workflowStatus['autoreviewwrong'], Const.workflowStatus['exception']):
        return HttpResponseRedirect('/detail/' + str(workflowId) + '/')

    workflowDetail.status = Const.workflowStatus['abort']
    workflowDetail.save()
	
    #如果人工终止了，则根据settings.py里的配置决定是否给提交者和审核人发邮件提醒。如果是发起人终止流程，则给主、副审核人各发一封；如果是审核人终止流程，则给发起人发一封邮件，并附带说明此单子被拒绝掉了，需要重新修改.
    if hasattr(settings, 'MAIL_ON_OFF') == True:
        if getattr(settings, 'MAIL_ON_OFF') == "on":
            url = _getDetailUrl(request) + str(workflowId) + '/'

            engineer = workflowDetail.engineer
            workflowStatus = workflowDetail.status
            workflowName = workflowDetail.workflow_name
            if loginUser == engineer:
                strTitle = "发起人主动终止SQL上线工单流程 # " + str(workflowId)
                strContent = "发起人：" + engineer + "\n审核人：" + reviewMan + "\n工单地址：" + url + "\n工单名称： " + workflowName +"\n执行结果：" + workflowStatus +"\n提醒：发起人主动终止流程"
                for reviewMan in listAllReviewMen:
                    if reviewMan == "":
                        continue
                    objReviewMan = users.objects.get(username=reviewMan)
                    mailSender.sendEmail(strTitle, strContent, [objReviewMan.email])
            else:
                objEngineer = users.objects.get(username=engineer)
                strTitle = "SQL上线工单被拒绝执行 # " + str(workflowId)
                strContent = "发起人：" + engineer + "\n审核人：" + reviewMan + "\n工单地址：" + url + "\n工单名称： " + workflowName +"\n执行结果：" + workflowStatus +"\n提醒：此工单被拒绝执行，请登陆重新提交或修改工单"
                mailSender.sendEmail(strTitle, strContent, [objEngineer.email])
        else:
            #不发邮件
            pass

    return HttpResponseRedirect('/detail/' + str(workflowId) + '/')

#展示回滚的SQL
def rollback(request):
    workflowId = request.GET['workflowid']
    if workflowId == '' or workflowId is None:
        context = {'errMsg': 'workflowId参数为空.'}
        return render(request, 'error.html', context)
    workflowId = int(workflowId)
    listBackupSql = inceptionDao.getRollbackSqlList(workflowId)
    workflowDetail = workflow.objects.get(id=workflowId)
    workflowName = workflowDetail.workflow_name
    rollbackWorkflowName = "【回滚工单】原工单Id:%s ,%s" % (workflowId, workflowName)
    cluster_name = workflowDetail.cluster_name
    try:
        listAllReviewMen = json.loads(workflowDetail.review_man)
        review_man = listAllReviewMen[0]
        sub_review_man = listAllReviewMen[1]
    except ValueError:
        review_man = workflowDetail.review_man
        sub_review_man = ''

    context = {'listBackupSql':listBackupSql, 'rollbackWorkflowName':rollbackWorkflowName, 'cluster_name':cluster_name, 'review_man':review_man, 'sub_review_man':sub_review_man}
    return render(request, 'rollback.html', context)

#SQL审核必读
def dbaprinciples(request):
    context = {'currentMenu':'dbaprinciples'}
    return render(request, 'dbaprinciples.html', context)

#图表展示
def charts(request):
    context = {'currentMenu':'charts'}
    return render(request, 'charts.html', context)

#根据集群名获取主库连接字符串，并封装成一个dict
def getMasterConnStr(clusterName):
    listMasters = master_config.objects.filter(cluster_name=clusterName)
    
    masterHost = listMasters[0].master_host
    masterPort = listMasters[0].master_port
    masterUser = listMasters[0].master_user
    masterPassword = prpCryptor.decrypt(listMasters[0].master_password)
    dictConn = {'masterHost':masterHost, 'masterPort':masterPort, 'masterUser':masterUser, 'masterPassword':masterPassword}
    return dictConn

#获取当前时间
def getNow():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

#获取当前请求url
def _getDetailUrl(request):
    scheme = request.scheme
    host = request.META['HTTP_HOST']
    return "%s://%s/detail/" % (scheme, host)
