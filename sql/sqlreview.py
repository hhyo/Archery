# -*- coding: UTF-8 -*-
import re
import simplejson as json

import time
from threading import Thread

from django.db import connection
from django.utils import timezone

from sql.utils.config import SysConfig
from sql.utils.dao import Dao
from .const import Const, WorkflowDict
from sql.utils.sendmsg import MailSender
from sql.utils.inception import InceptionDao
from sql.utils.aes_decryptor import Prpcrypt
from .models import users, workflow, master_config
from .workflow import Workflow
import logging

logger = logging.getLogger('default')

dao = Dao()
prpCryptor = Prpcrypt()
workflowOb = Workflow()


# 获取当前请求url
def getDetailUrl(request):
    scheme = request.scheme
    host = request.META['HTTP_HOST']
    return "%s://%s/detail/" % (scheme, host)


# 根据实例名获取主库连接字符串，并封装成一个dict
def getMasterConnStr(clusterName):
    listMasters = master_config.objects.filter(cluster_name=clusterName)

    masterHost = listMasters[0].master_host
    masterPort = listMasters[0].master_port
    masterUser = listMasters[0].master_user
    masterPassword = prpCryptor.decrypt(listMasters[0].master_password)
    dictConn = {'masterHost': masterHost, 'masterPort': masterPort, 'masterUser': masterUser,
                'masterPassword': masterPassword}
    return dictConn


# SQL工单跳过inception执行回调
def execute_skipinc_call_back(workflowId, clusterName, db_name, sql_content, url):
    workflowDetail = workflow.objects.get(id=workflowId)
    # 获取审核人
    reviewMan = workflowDetail.review_man

    # 获取实例连接信息
    masterInfo = getMasterConnStr(clusterName)
    try:
        # 执行sql
        t_start = time.time()
        execute_result = dao.mysql_execute(masterInfo['masterHost'], masterInfo['masterPort'], masterInfo['masterUser'],
                                           masterInfo['masterPassword'], db_name, sql_content)
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
        # 关闭后重新获取连接，防止超时
        connection.close()
        workflowDetail.save()
    except Exception as e:
        logger.error(e)

    # 发送消息
    send_msg(workflowDetail, url)


# SQL工单执行回调
def execute_call_back(workflowId, clusterName, url):
    workflowDetail = workflow.objects.get(id=workflowId)
    # 获取审核人
    reviewMan = workflowDetail.review_man

    dictConn = getMasterConnStr(clusterName)
    try:
        # 交给inception先split，再执行
        (finalStatus, finalList) = InceptionDao().executeFinal(workflowDetail, dictConn)

        # 封装成JSON格式存进数据库字段里
        strJsonResult = json.dumps(finalList)
        workflowDetail = workflow.objects.get(id=workflowId)
        workflowDetail.execute_result = strJsonResult
        workflowDetail.finish_time = timezone.now()
        workflowDetail.status = finalStatus
        workflowDetail.is_manual = 0
        workflowDetail.audit_remark = ''
        # 关闭后重新获取连接，防止超时
        connection.close()
        workflowDetail.save()
    except Exception as e:
        logger.error(e)

    # 发送消息
    send_msg(workflowDetail, url)


# 给定时任务执行sql
def execute_job(workflowId, url):
    job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflowId)
    logger.debug('execute_job:' + job_id + ' start')
    workflowDetail = workflow.objects.get(id=workflowId)
    clusterName = workflowDetail.cluster_name
    db_name = workflowDetail.db_name

    # 服务器端二次验证，当前工单状态必须为定时执行过状态
    if workflowDetail.status != Const.workflowStatus['timingtask']:
        raise Exception('工单不是定时执行状态')

    # 将流程状态修改为执行中，并更新reviewok_time字段
    workflowDetail.status = Const.workflowStatus['executing']
    workflowDetail.reviewok_time = timezone.now()
    try:
        workflowDetail.save()
    except Exception:
        # 关闭后重新获取连接，防止超时
        connection.close()
        workflowDetail.save()
    logger.debug('execute_job:' + job_id + ' executing')
    # 执行之前重新split并check一遍，更新SHA1缓存；因为如果在执行中，其他进程去做这一步操作的话，会导致inception core dump挂掉
    splitReviewResult = InceptionDao().sqlautoReview(workflowDetail.sql_content, workflowDetail.cluster_name, db_name,
                                                     isSplit='yes')
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


def send_msg(workflowDetail, url):
    mailSender = MailSender()
    # 如果执行完毕了，则根据配置决定是否给提交者和DBA一封邮件提醒，DBA需要知晓审核并执行过的单子
    msg_title = "[{}]工单{}#{}".format(WorkflowDict.workflow_type['sqlreview_display'], workflowDetail.status,
                                     workflowDetail.id)
    msg_content = '''发起人：{}\n审核人：{}\n工单名称：{}\n工单地址：{}\n工单详情预览：{}\n'''.format(
        workflowDetail.engineer, workflowDetail.review_man, workflowDetail.workflow_name, url,
        workflowDetail.sql_content[0:500])

    if SysConfig().sys_config.get('mail') == 'true':
        # 邮件通知申请人，审核人，抄送DBA
        notify_users = workflowDetail.review_man.split(',')
        notify_users.append(workflowDetail.engineer)
        listToAddr = [email['email'] for email in users.objects.filter(username__in=notify_users).values('email')]
        listCcAddr = [email['email'] for email in users.objects.filter(role='DBA').values('email')]
        mailSender.sendEmail(msg_title, msg_content, listToAddr, listCcAddr=listCcAddr)
