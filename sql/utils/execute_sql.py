# -*- coding: UTF-8 -*-
import re

import simplejson as json

import time
from threading import Thread

from django.db import connection
from django.utils import timezone

from sql.utils.group import auth_group_users
from sql.utils.config import SysConfig
from sql.utils.dao import Dao
from sql.const import Const, WorkflowDict
from sql.utils.sendmsg import MailSender
from sql.utils.inception import InceptionDao
from sql.models import Users, SqlWorkflow, SqlGroup
from sql.utils.sql_review import getMasterConnStr
from sql.utils.workflow import Workflow
import logging

logger = logging.getLogger('default')


# SQL工单跳过inception执行回调
def execute_skipinc_call_back(workflowId, instance_name, db_name, sql_content, url):
    workflowDetail = SqlWorkflow.objects.get(id=workflowId)
    try:
        # 执行sql
        t_start = time.time()
        execute_result = Dao(instance_name=instance_name).mysql_execute(db_name, sql_content)
        t_end = time.time()
        execute_time = "%5s" % "{:.4f}".format(t_end - t_start)
        execute_result['execute_time'] = execute_time + 'sec'

        workflowDetail = SqlWorkflow.objects.get(id=workflowId)
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
def execute_call_back(workflowId, instance_name, url):
    workflowDetail = SqlWorkflow.objects.get(id=workflowId)
    dictConn = getMasterConnStr(instance_name)
    try:
        # 交给inception先split，再执行
        (finalStatus, finalList) = InceptionDao().executeFinal(workflowDetail, dictConn)

        # 封装成JSON格式存进数据库字段里
        strJsonResult = json.dumps(finalList)
        workflowDetail = SqlWorkflow.objects.get(id=workflowId)
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
    workflowDetail = SqlWorkflow.objects.get(id=workflowId)
    instance_name = workflowDetail.instance_name
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
    splitReviewResult = InceptionDao().sqlautoReview(workflowDetail.sql_content, workflowDetail.instance_name, db_name,
                                                     isSplit='yes')
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


# 执行结果通知
def send_msg(workflowDetail, url):
    mailSender = MailSender()
    sys_config = SysConfig().sys_config
    # 获取当前审批和审批流程
    audit_auth_group, current_audit_auth_group = Workflow.review_info(workflowDetail.id, 2)
    audit_id = Workflow.auditinfobyworkflow_id(workflowDetail.id, 2).audit_id
    # 如果执行完毕了，则根据配置决定是否给提交者和DBA一封邮件提醒，DBA需要知晓审核并执行过的单子
    msg_title = "[{}]工单{}#{}".format(WorkflowDict.workflow_type['sqlreview_display'], workflowDetail.status, audit_id)
    msg_content = '''发起人：{}\n审批流程：{}\n工单名称：{}\n工单地址：{}\n工单详情预览：{}\n'''.format(
        workflowDetail.engineer_display, audit_auth_group, workflowDetail.workflow_name, url,
        workflowDetail.sql_content[0:500])

    if sys_config.get('mail') == 'true':
        # 邮件通知申请人，审核人，抄送DBA
        notify_users = workflowDetail.audit_auth_groups.split(',')
        notify_users.append(workflowDetail.engineer)
        listToAddr = [email['email'] for email in Users.objects.filter(username__in=notify_users).values('email')]
        listCcAddr = [email['email'] for email in
                      auth_group_users(auth_group_names=['DBA'], group_id=workflowDetail.group_id).values('email')]
        mailSender.send_email(msg_title, msg_content, listToAddr, listCcAddr=listCcAddr)
    if sys_config.get('ding') == 'true':
        # 钉钉通知申请人，审核人，抄送DBA
        webhook_url = SqlGroup.objects.get(group_id=workflowDetail.group_id).ding_webhook
        MailSender.send_ding(webhook_url, msg_title + '\n' + msg_content)

    if sys_config.get('mail') == 'true' and sys_config.get('ddl_notify_auth_group', None) \
            and workflowDetail.status == '已正常结束':
        # 判断上线语句是否存在DDL，存在则通知相关人员
        sql_content = workflowDetail.sql_content
        # 删除注释语句
        sql_content = ''.join(
            map(lambda x: re.compile(r'(^--\s+.*|^/\*.*\*/;\s*$)').sub('', x, count=1),
                sql_content.splitlines(1))).strip()
        # 去除空行
        sql_content = re.sub('[\r\n\f]{2,}', '\n', sql_content)

        # 匹配DDL语句CREATE、ALTER（排除索引变更）、DROP、TRUNCATE、RENAME
        send = 0
        for row in sql_content.strip(';').split(';'):
            # alter语法
            if re.match(r"^alter\s+table\s+\S+\s+(add|alter|change|drop|rename|modify)\s+(?!.*(index|key|unique))",
                        row.strip().lower()):
                send = 1
                break
            # create语法
            elif re.match(r"^create\s+(temporary\s+)?(database|schema|table)", row.strip().lower()):
                send = 1
                break
            # drop语法
            elif re.match(r"^drop", row.strip().lower()):
                send = 1
                break
            # rename语法
            elif re.match(r"^rename", row.strip().lower()):
                send = 1
                break
            # truncate语法
            elif re.match(r"^truncate", row.strip().lower()):
                send = 1
                break

        if send == 1:
            # 消息内容通知
            msg_title = '[Archer]有新的DDL语句执行完成#{}'.format(audit_id)
            msg_content = '''发起人：{}\n变更组：{}\n变更实例：{}\n变更数据库：{}\n工单名称：{}\n工单地址：{}\n工单预览：{}\n'''.format(
                Users.objects.get(username=workflowDetail.engineer).display,
                workflowDetail.group_name,
                workflowDetail.instance_name,
                workflowDetail.db_name,
                workflowDetail.workflow_name,
                url,
                workflowDetail.sql_content[0:500])
            # 获取通知成员
            msg_to = [email['email'] for email in
                      Users.objects.filter(groups__name=sys_config.get('ddl_notify_auth_group')).values('email')]

            # 发送
            mailSender.send_email(msg_title, msg_content, msg_to)
