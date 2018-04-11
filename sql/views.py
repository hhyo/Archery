# -*- coding: UTF-8 -*- 

import re
import json
import time
from threading import Thread
from collections import OrderedDict

import time
from django.db.models import Q
from django.db import connection
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password
from django.core.urlresolvers import reverse

from .dao import Dao
from .const import Const, WorkflowDict
from .sendmail import MailSender
from .inception import InceptionDao
from .aes_decryptor import Prpcrypt
from .models import users, master_config, AliyunRdsConfig, workflow, slave_config, QueryPrivileges
from .workflow import Workflow
from .permission import role_required, superuser_required
import logging

logger = logging.getLogger('default')

dao = Dao()
inceptionDao = InceptionDao()
mailSender = MailSender()
prpCryptor = Prpcrypt()
workflowOb = Workflow()

#根据集群名获取主库连接字符串，并封装成一个dict
def getMasterConnStr(clusterName):
    listMasters = master_config.objects.filter(cluster_name=clusterName)

    masterHost = listMasters[0].master_host
    masterPort = listMasters[0].master_port
    masterUser = listMasters[0].master_user
    masterPassword = prpCryptor.decrypt(listMasters[0].master_password)
    dictConn = {'masterHost':masterHost, 'masterPort':masterPort, 'masterUser':masterUser, 'masterPassword':masterPassword}
    return dictConn

#获取当前请求url
def _getDetailUrl(request):
    scheme = request.scheme
    host = request.META['HTTP_HOST']
    return "%s://%s/detail/" % (scheme, host)

#SQL工单跳过inception执行回调
def execute_skipinc_call_back(workflowId , clusterName, sql_content, url):
    workflowDetail = workflow.objects.get(id=workflowId)
    # 获取审核人
    try:
        listAllReviewMen = json.loads(workflowDetail.review_man)
    except ValueError:
        listAllReviewMen = (workflowDetail.review_man,)
    # 获取集群连接信息
    masterInfo = getMasterConnStr(clusterName)
    try:
        # 执行sql
        t_start = time.time()
        execute_result = dao.mysql_execute(masterInfo['masterHost'], masterInfo['masterPort'], masterInfo['masterUser'],
                                           masterInfo['masterPassword'], sql_content)
        t_end = time.time()
        execute_time = "%5s" % "{:.4f}".format(t_end - t_start)
        execute_result['execute_time'] = execute_time + 'sec'

        workflowDetail = workflow.objects.get(id=workflowId)
        if execute_result.get('Warning'):
            workflowDetail.status = Const.workflowStatus['exception']
        elif execute_result.get('Error'):
            workflowDetail.status = Const.workflowStatus['exception']
        else:
            workflowDetail.status = Const.workflowStatus['finish']
        workflowDetail.finish_time = timezone.now()
        workflowDetail.execute_result = json.dumps(execute_result)
        workflowDetail.is_manual = 1
        workflowDetail.audit_remark = ''
        workflowDetail.is_backup = '否'
        # 重新获取连接，防止超时
        connection.close()
        workflowDetail.save()
    except Exception as e:
        logger.error(e)

    # 如果执行完毕了，则根据settings.py里的配置决定是否给提交者和DBA一封邮件提醒.DBA需要知晓审核并执行过的单子
    if getattr(settings, 'MAIL_ON_OFF') == "on":
        # 给主、副审核人，申请人，DBA各发一封邮件
        engineer = workflowDetail.engineer
        reviewMen = workflowDetail.review_man
        workflowStatus = workflowDetail.status
        workflowName = workflowDetail.workflow_name
        objEngineer = users.objects.get(username=engineer)
        strTitle = "SQL上线工单执行完毕 # " + str(workflowId)
        strContent = "发起人：" + engineer + "\n审核人：" + reviewMen + "\n工单地址：" + url + "\n工单名称： " + workflowName + "\n执行结果：" + workflowStatus
        mailSender.sendEmail(strTitle, strContent, [objEngineer.email])
        mailSender.sendEmail(strTitle, strContent, getattr(settings, 'MAIL_REVIEW_DBA_ADDR'))
        for reviewMan in listAllReviewMen:
            if reviewMan == "":
                continue
            objReviewMan = users.objects.get(username=reviewMan)
            mailSender.sendEmail(strTitle, strContent, [objReviewMan.email])

#SQL工单执行回调
def execute_call_back(workflowId , clusterName, url):
    workflowDetail = workflow.objects.get(id=workflowId)
    # 获取审核人
    try:
        listAllReviewMen = json.loads(workflowDetail.review_man)
    except ValueError:
        listAllReviewMen = (workflowDetail.review_man,)

    dictConn = getMasterConnStr(clusterName)
    try:
        #交给inception先split，再执行
        (finalStatus, finalList) = inceptionDao.executeFinal(workflowDetail, dictConn)

        #封装成JSON格式存进数据库字段里
        strJsonResult = json.dumps(finalList)
        workflowDetail = workflow.objects.get(id=workflowId)
        workflowDetail.execute_result = strJsonResult
        workflowDetail.finish_time = timezone.now()
        workflowDetail.status = finalStatus
        workflowDetail.is_manual=0
        workflowDetail.audit_remark = ''
        # 重新获取连接，防止超时
        connection.close()
        workflowDetail.save()
    except Exception as e:
        logger.error(e)

    #如果执行完毕了，则根据settings.py里的配置决定是否给提交者和DBA一封邮件提醒.DBA需要知晓审核并执行过的单子
    if hasattr(settings, 'MAIL_ON_OFF') == True:
        if getattr(settings, 'MAIL_ON_OFF') == "on":
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

def login(request):
    return render(request, 'login.html')

def logout(request):
    if request.session.get('login_username', False):
        del request.session['login_username']
    return render(request, 'login.html')

#首页，也是查看所有SQL工单页面，具备翻页功能
def allworkflow(request):
    context = {'currentMenu':'allworkflow'}
    return render(request, 'allWorkflow.html', context)

#提交SQL的页面
def submitSql(request):
    masters = master_config.objects.all().order_by('cluster_name')
    if len(masters) == 0:
       context = {'errMsg': '请先配置主库信息'}
       return render(request, 'error.html', context)

    #获取所有集群名称
    listAllClusterName = [master.cluster_name for master in masters]

    dictAllClusterDb = OrderedDict()
    #每一个都首先获取主库地址在哪里
    for clusterName in listAllClusterName:
        listMasters = master_config.objects.filter(cluster_name=clusterName)
        #取出该集群的名称以及连接方式，为了后面连进去获取所有databases
        masterHost = listMasters[0].master_host
        masterPort = listMasters[0].master_port
        masterUser = listMasters[0].master_user
        masterPassword = prpCryptor.decrypt(listMasters[0].master_password)

        listDb = dao.getAlldbByCluster(masterHost, masterPort, masterUser, masterPassword)
        dictAllClusterDb[clusterName] = listDb

    #获取所有审核人
    loginUser = request.session.get('login_username', False)
    reviewMen = users.objects.filter(role='审核人')
    if len(reviewMen) == 0:
       context = {'errMsg': '请先配置审核人'}
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
        Workflow.create_time = timezone.now()
    else:
        Workflow = workflow.objects.get(id=int(workflowid))
    Workflow.workflow_name = workflowName
    Workflow.engineer = engineer
    Workflow.review_man = json.dumps(listAllReviewMen, ensure_ascii=False)
    Workflow.status = workflowStatus
    Workflow.is_backup = isBackup
    Workflow.review_content = jsonResult
    Workflow.cluster_name = master_config.objects.get(cluster_name=clusterName)
    Workflow.sql_content = sqlContent
    Workflow.execute_result = ''
    Workflow.audit_remark = ''
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
                    strContent = "发起人：" + engineer + "\n审核人：" + str(listAllReviewMen)  + "\n工单地址：" + url + "\n工单名称： " + workflowName + "\n具体SQL：" + sqlContent
                    objReviewMan = users.objects.get(username=reviewMan)
                    mailSender.sendEmail(strTitle, strContent, [objReviewMan.email])
            else:
                #不发邮件
                pass

    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))

#展示SQL工单详细内容，以及可以人工审核，审核通过即可执行
def detail(request, workflowId):
    workflowDetail = get_object_or_404(workflow, pk=workflowId)
    if workflowDetail.status in (Const.workflowStatus['finish'], Const.workflowStatus['exception']) \
            and workflowDetail.is_manual == 0:
        listContent = json.loads(workflowDetail.execute_result)
    else:
        listContent = json.loads(workflowDetail.review_content)
    try:
        listAllReviewMen = json.loads(workflowDetail.review_man)
    except ValueError:
        listAllReviewMen = (workflowDetail.review_man, )

    # 获取用户信息
    loginUser = request.session.get('login_username', False)
    loginUserOb = users.objects.get(username=loginUser)

    column_list = ['ID', 'stage', 'errlevel', 'stagestatus', 'errormessage', 'SQL', 'Affected_rows', 'sequence',
                   'backup_dbname', 'execute_time', 'sqlsha1']
    rows = []
    for row_index, row_item in enumerate(listContent):
        row = {}
        row['ID'] = row_index+1
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
    context = {'currentMenu':'allworkflow', 'workflowDetail':workflowDetail, 'column_list':column_list,'rows':rows,
               'listAllReviewMen':listAllReviewMen,'loginUserOb': loginUserOb}
    return render(request, 'detail.html', context)

#审核通过，不执行
def passonly(request):
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

    #将流程状态修改为审核通过，并更新reviewok_time字段
    workflowDetail.status = Const.workflowStatus['pass']
    workflowDetail.reviewok_time = timezone.now()
    workflowDetail.audit_remark = ''
    workflowDetail.save()

    #如果执行完毕了，则根据settings.py里的配置决定是否给提交者和DBA一封邮件提醒.DBA需要知晓审核并执行过的单子
    if getattr(settings, 'MAIL_ON_OFF') == "on":
        url = _getDetailUrl(request) + str(workflowId) + '/'

        #给主、副审核人，申请人，DBA各发一封邮件
        engineer = workflowDetail.engineer
        reviewMen = workflowDetail.review_man
        workflowStatus = workflowDetail.status
        workflowName = workflowDetail.workflow_name
        objEngineer = users.objects.get(username=engineer)
        strTitle = "SQL上线工单审核通过 # " + str(workflowId)
        strContent = "发起人：" + engineer + "\n审核人：" + reviewMen + "\n工单地址：" + url + "\n工单名称： " + workflowName +"\n审核结果：" + workflowStatus
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

    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))


# 仅执行SQL
def executeonly(request):
    workflowId = request.POST['workflowid']
    if workflowId == '' or workflowId is None:
        context = {'errMsg': 'workflowId参数为空.'}
        return render(request, 'error.html', context)

    workflowId = int(workflowId)
    workflowDetail = workflow.objects.get(id=workflowId)
    clusterName = workflowDetail.cluster_name
    url = _getDetailUrl(request) + str(workflowId) + '/'

    try:
        listAllReviewMen = json.loads(workflowDetail.review_man)
    except ValueError:
        listAllReviewMen = (workflowDetail.review_man, )

    #服务器端二次验证，正在执行人工审核动作的当前登录用户必须为审核人或者提交人. 避免攻击或被接口测试工具强行绕过
    loginUser = request.session.get('login_username', False)
    if loginUser is None or (loginUser not in listAllReviewMen and loginUser != workflowDetail.engineer):
        context = {'errMsg': '当前登录用户不是审核人或者提交人，请重新登录.'}
        return render(request, 'error.html', context)

    #服务器端二次验证，当前工单状态必须为审核通过状态
    if workflowDetail.status != Const.workflowStatus['pass']:
        context = {'errMsg': '当前工单状态不是审核通过，请刷新当前页面！'}
        return render(request, 'error.html', context)

    #将流程状态修改为执行中，并更新reviewok_time字段
    workflowDetail.status = Const.workflowStatus['executing']
    workflowDetail.reviewok_time = timezone.now()
    #执行之前重新split并check一遍，更新SHA1缓存；因为如果在执行中，其他进程去做这一步操作的话，会导致inception core dump挂掉
    splitReviewResult = inceptionDao.sqlautoReview(workflowDetail.sql_content, workflowDetail.cluster_name, isSplit='yes')
    workflowDetail.review_content = json.dumps(splitReviewResult)
    workflowDetail.save()

    # 采取异步回调的方式执行语句，防止出现持续执行中的异常
    t = Thread(target=execute_call_back, args=(workflowId, clusterName, url))
    t.start()

    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))

#人工审核也通过，执行SQL
def execute(request):
    workflowId = request.POST['workflowid']
    if workflowId == '' or workflowId is None:
        context = {'errMsg': 'workflowId参数为空.'}
        return render(request, 'error.html', context)

    workflowId = int(workflowId)
    workflowDetail = workflow.objects.get(id=workflowId)
    clusterName = workflowDetail.cluster_name
    url = _getDetailUrl(request) + str(workflowId) + '/'

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


    #将流程状态修改为执行中，并更新reviewok_time字段
    workflowDetail.status = Const.workflowStatus['executing']
    workflowDetail.reviewok_time = timezone.now()
    #执行之前重新split并check一遍，更新SHA1缓存；因为如果在执行中，其他进程去做这一步操作的话，会导致inception core dump挂掉
    splitReviewResult = inceptionDao.sqlautoReview(workflowDetail.sql_content, workflowDetail.cluster_name, isSplit='yes')
    workflowDetail.review_content = json.dumps(splitReviewResult)
    workflowDetail.save()

    # 采取异步回调的方式执行语句，防止出现持续执行中的异常
    t = Thread(target=execute_call_back, args=(workflowId, clusterName, url))
    t.start()

    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))


# 跳过inception直接执行申请
@superuser_required
def execute_skipinc(request):
    workflowId = request.POST['workflowid']

    # 获取工单信息
    workflowId = int(workflowId)
    workflowDetail = workflow.objects.get(id=workflowId)
    sql_content = workflowDetail.sql_content
    clusterName = workflowDetail.cluster_name
    url = _getDetailUrl(request) + str(workflowId) + '/'

    #服务器端二次验证，当前工单状态必须为等待人工审核/审核通过/自动审核不通过
    if workflowDetail.status not in [Const.workflowStatus['manreviewing'],Const.workflowStatus['pass'],Const.workflowStatus['autoreviewwrong']]:
        context = {'errMsg': '当前工单状态不是等待人工审核/审核通过/自动审核不通过，请刷新当前页面！'}
        return render(request, 'error.html', context)

    # 更新工单状态为执行中
    workflowDetail = workflow.objects.get(id=workflowId)
    workflowDetail.status = Const.workflowStatus['executing']
    workflowDetail.reviewok_time = timezone.now()
    workflowDetail.save()

    # 采取异步回调的方式执行语句，防止出现持续执行中的异常
    t = Thread(target=execute_skipinc_call_back, args=(workflowId, clusterName, sql_content, url))
    t.start()

    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))

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

    audit_remark = request.POST.get('audit_remark')
    if audit_remark is None:
        context = {'errMsg': '驳回原因不能为空'}
        return render(request, 'error.html', context)

    #服务器端二次验证，如果正在执行终止动作的当前登录用户，不是发起人也不是审核人，则异常.
    loginUser = request.session.get('login_username', False)
    if loginUser is None or (loginUser not in listAllReviewMen and loginUser != workflowDetail.engineer):
        context = {'errMsg': '当前登录用户不是审核人也不是发起人，请重新登录.'}
        return render(request, 'error.html', context)

    #服务器端二次验证，如果当前单子状态是结束状态，则不能发起终止
    if workflowDetail.status in (Const.workflowStatus['abort'], Const.workflowStatus['finish'], Const.workflowStatus['autoreviewwrong'], Const.workflowStatus['exception']):
        return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))

    workflowDetail.status = Const.workflowStatus['abort']
    workflowDetail.audit_remark = audit_remark
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

    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))

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

#ldap用户同步
def ldapsync(request):
    context = {'currentMenu':'ldapsync'}
    return render(request, 'ldapsync.html', context)

#SQL审核必读
def dbaprinciples(request):
    context = {'currentMenu':'dbaprinciples'}
    return render(request, 'dbaprinciples.html', context)

#图表展示
def charts(request):
    context = {'currentMenu':'charts'}
    return render(request, 'charts.html', context)

# SQL在线查询
def sqlquery(request):
    # 获取所有从库集群名称
    slaves = slave_config.objects.all().order_by('cluster_name')
    if len(slaves) == 0:
        context = {'errMsg': '请先配置从库信息'}
        return render(request, 'error.html', context)
    listAllClusterName = [slave.cluster_name for slave in slaves]

    context = {'currentMenu': 'sqlquery', 'listAllClusterName': listAllClusterName}
    return render(request, 'sqlquery.html', context)

# SQL慢日志
def slowquery(request):
    # 获取所有集群主库名称
    masters = master_config.objects.all().order_by('cluster_name')
    if len(masters) == 0:
        context = {'errMsg': '请先配置主库信息'}
        return render(request, 'error.html', context)
    cluster_name_list = [master.cluster_name for master in masters]

    context = {'currentMenu': 'slowquery', 'tab': 'slowquery', 'cluster_name_list': cluster_name_list}
    return render(request, 'slowquery.html', context)

# SQL优化工具
def sqladvisor(request):
    # 获取所有集群主库名称
    masters = master_config.objects.all().order_by('cluster_name')
    if len(masters) == 0:
        context = {'errMsg': '请先配置主库信息'}
        return render(request, 'error.html', context)
    cluster_name_list = [master.cluster_name for master in masters]

    context = {'currentMenu': 'sqladvisor', 'listAllClusterName': cluster_name_list}
    return render(request, 'sqladvisor.html', context)

# 查询权限申请列表
def queryapplylist(request, workflow_id):
    if workflow_id is None:
        workflow_id = 0
    slaves = slave_config.objects.all().order_by('cluster_name')
    # 获取所有集群名称
    listAllClusterName = [slave.cluster_name for slave in slaves]
    context = {'currentMenu': 'queryapply', 'listAllClusterName': listAllClusterName, 'workflow_id': workflow_id}
    return render(request, 'queryapplylist.html', context)


# 用户的查询权限管理
def queryuserprivileges(request):
    # 获取用户信息
    loginUser = request.session.get('login_username', False)
    loginUserOb = users.objects.get(username=loginUser)
    # 获取所有用户
    user_list = QueryPrivileges.objects.filter(is_deleted=0).values('user_name').distinct()
    context = {'currentMenu': 'queryapply', 'user_list': user_list, 'loginUserOb': loginUserOb}
    return render(request, 'queryuserprivileges.html', context)

# 问题诊断--进程
def diagnosis_process(request):
    # 获取用户信息
    loginUser = request.session.get('login_username', False)
    loginUserOb = users.objects.get(username=loginUser)

    # 获取所有集群名称
    masters = AliyunRdsConfig.objects.all().order_by('cluster_name')
    cluster_name_list = [master.cluster_name for master in masters]

    context = {'currentMenu': 'diagnosis', 'tab': 'process', 'cluster_name_list': cluster_name_list,
               'loginUserOb': loginUserOb}
    return render(request, 'diagnosis.html', context)

# 问题诊断--空间
def diagnosis_sapce(request):
    # 获取所有集群名称
    masters = AliyunRdsConfig.objects.all().order_by('cluster_name')
    cluster_name_list = [master.cluster_name for master in masters]

    context = {'currentMenu': 'diagnosis', 'tab': 'space', 'cluster_name_list': cluster_name_list}
    return render(request, 'diagnosis.html', context)

# 获取工作流审核列表
def workflows(request):
    # 获取用户信息
    loginUser = request.session.get('login_username', False)
    loginUserOb = users.objects.get(username=loginUser)
    context = {'currentMenu': 'workflow', "loginUserOb": loginUserOb}
    return render(request, "workflow.html", context)


# 工作流审核列表
def workflowsdetail(request, audit_id):
    # 按照不同的workflow_type返回不同的详情
    auditInfo = workflowOb.auditinfo(audit_id)
    if auditInfo.workflow_type == WorkflowDict.workflow_type['query']:
        return HttpResponseRedirect(reverse('sql:queryapplylist', args=(auditInfo.workflow_id,)))
