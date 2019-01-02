# -*- coding: UTF-8 -*-
import re
import traceback

import simplejson as json

import time
from threading import Thread
import sqlparse
from django.db import connection
from django.utils import timezone

from sql.utils.resource_group import auth_group_users
from common.config import SysConfig
from sql.utils.dao import Dao
from common.utils.const import Const, WorkflowDict
from common.utils.sendmsg import MailSender
from sql.utils.inception import InceptionDao
from sql.models import Users, SqlWorkflow, ResourceGroup
from sql.utils.workflow import Workflow
from sql.engines import get_engine
from django_q.tasks import async_task, result
import logging

logger = logging.getLogger('default')

def execute(workflow_id):
    """为延时或异步任务准备的execute, 传入工单ID即可"""
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    execute_engine = get_engine(workflow=workflow_detail)
    return execute_engine.execute()
def execute_callback(task):
    """异步任务的回调, 将结果填入数据库等等
    使用django-q的hook, 传入参数为整个task
    task.result 是真正的结果
    """
    workflow_id = task.args[0]
    workflow = SqlWorkflow.objects.get(id=workflow_id)
    workflow.finish_time = task.stopped
    execute_result = {}
    
    if not task.success:
        # 不成功会返回字符串
        workflow.status = Const.workflowStatus['exception']
        execute_result['Error'] = task.result
    elif task.result.get('Warning') or task.result.get('Error'):
        workflow.status = Const.workflowStatus['exception']
        execute_result = task.result
    else:
        workflow.status = Const.workflowStatus['finish']
        execute_result = task.result
    execute_result['execute_time'] = '{:.4f} sec'.format(task.time_taken())
    workflow.execute_result = json.dumps(execute_result)
    workflow.audit_remark = ''
    workflow.is_backup = '否'
    workflow.save()

    # 增加工单日志
    # 获取audit_id
    audit_id = Workflow.audit_info_by_workflow_id(workflow_id=workflow_id,
                                                  workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
    Workflow.add_workflow_log(audit_id=audit_id,
                              operation_type=6,
                              operation_type_desc='执行结束',
                              operation_info='执行结果：{}'.format(workflow.status),
                              operator='',
                              operator_display='系统'
                              )

    # 发送消息
    send_msg(workflow_detail, url)

# SQL工单跳过inception执行
def execute_skipinc_call_back(workflow_id, instance_name, db_name, sql_content, url):
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    try:
        # 执行sql
        t_start = time.time()
        execute_result = Dao(instance_name=instance_name).mysql_execute(db_name, sql_content)
        t_end = time.time()
        execute_time = "%5s" % "{:.4f}".format(t_end - t_start)
        execute_result['execute_time'] = execute_time + 'sec'

        workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
        if execute_result.get('Warning'):
            workflow_detail.status = Const.workflowStatus['exception']
        elif execute_result.get('Error'):
            workflow_detail.status = Const.workflowStatus['exception']
        else:
            workflow_detail.status = Const.workflowStatus['finish']
        workflow_detail.finish_time = timezone.now()
        workflow_detail.execute_result = json.dumps(execute_result)
        workflow_detail.is_manual = 1
        workflow_detail.audit_remark = ''
        workflow_detail.is_backup = '否'
        # 关闭后重新获取连接，防止超时
        connection.close()
        workflow_detail.save()
    except Exception:
        logger.error(traceback.format_exc())

    # 增加工单日志
    # 获取audit_id
    audit_id = Workflow.audit_info_by_workflow_id(workflow_id=workflow_id,
                                                  workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
    Workflow.add_workflow_log(audit_id=audit_id,
                              operation_type=6,
                              operation_type_desc='执行结束',
                              operation_info='执行结果：{}'.format(workflow_detail.status),
                              operator='',
                              operator_display='系统'
                              )

    # 发送消息
    send_msg(workflow_detail, url)


# SQL工单执行
def execute_call_back(workflow_id, instance_name, url):
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    try:
        # 交给inception先split，再执行
        (finalStatus, finalList) = InceptionDao(instance_name=instance_name).execute_final(workflow_detail)

        # 封装成JSON格式存进数据库字段里
        str_json_result = json.dumps(finalList)
        workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
        workflow_detail.execute_result = str_json_result
        workflow_detail.finish_time = timezone.now()
        workflow_detail.status = finalStatus
        workflow_detail.is_manual = 0
        workflow_detail.audit_remark = ''
        # 关闭后重新获取连接，防止超时
        connection.close()
        workflow_detail.save()
    except Exception:
        logger.error(traceback.format_exc())

    # 增加工单日志
    # 获取audit_id
    audit_id = Workflow.audit_info_by_workflow_id(workflow_id=workflow_id,
                                                  workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
    Workflow.add_workflow_log(audit_id=audit_id,
                              operation_type=6,
                              operation_type_desc='执行结束',
                              operation_info='执行结果：{}'.format(workflow_detail.status),
                              operator='',
                              operator_display='系统'
                              )

    # 发送消息
    send_msg(workflow_detail, url)


# 给定时任务执行sql
def execute_job(workflow_id, url):
    job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflow_id)
    logger.debug('execute_job:' + job_id + ' start')
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    instance_name = workflow_detail.instance_name
    db_name = workflow_detail.db_name

    # 服务器端二次验证，当前工单状态必须为定时执行过状态
    if workflow_detail.status != Const.workflowStatus['timingtask']:
        raise Exception('工单不是定时执行状态')

    # 将流程状态修改为执行中，并更新reviewok_time字段
    workflow_detail.status = Const.workflowStatus['executing']
    workflow_detail.reviewok_time = timezone.now()
    try:
        workflow_detail.save()
    except Exception:
        # 关闭后重新获取连接，防止超时
        connection.close()
        workflow_detail.save()
    logger.debug('execute_job:' + job_id + ' executing')
    # 执行之前重新split并check一遍，更新SHA1缓存；因为如果在执行中，其他进程去做这一步操作的话，会导致inception core dump挂掉
    split_review_result = InceptionDao(instance_name=instance_name).sqlauto_review(workflow_detail.sql_content,
                                                                                   db_name,
                                                                                   is_split='yes')
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

    # 增加工单日志
    # 获取audit_id
    audit_id = Workflow.audit_info_by_workflow_id(workflow_id=workflow_id,
                                                  workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
    Workflow.add_workflow_log(audit_id=audit_id,
                              operation_type=5,
                              operation_type_desc='执行工单',
                              operation_info='系统定时执行',
                              operator='',
                              operator_display='系统'
                              )


# 执行结果通知
def send_msg(workflow_detail, url):
    mail_sender = MailSender()
    sys_config = SysConfig().sys_config
    # 获取当前审批和审批流程
    audit_auth_group, current_audit_auth_group = Workflow.review_info(workflow_detail.id, 2)
    audit_id = Workflow.audit_info_by_workflow_id(workflow_detail.id, 2).audit_id
    # 如果执行完毕了，则根据配置决定是否给提交者和DBA一封邮件提醒，DBA需要知晓审核并执行过的单子
    msg_title = "[{}]工单{}#{}".format(WorkflowDict.workflow_type['sqlreview_display'], workflow_detail.status, audit_id)
    msg_content = '''发起人：{}\n组：{}\n审批流程：{}\n工单名称：{}\n工单地址：{}\n工单详情预览：{}\n'''.format(
        workflow_detail.engineer_display, workflow_detail.group_name, audit_auth_group, workflow_detail.workflow_name,
        url,
        re.sub('[\r\n\f]{2,}', '\n', workflow_detail.sql_content[0:500].replace('\r', '')))

    if sys_config.get('mail'):
        # 邮件通知申请人，抄送DBA
        list_to_addr = [email['email'] for email in
                        Users.objects.filter(username=workflow_detail.engineer).values('email')]
        list_cc_addr = [email['email'] for email in
                        auth_group_users(auth_group_names=['DBA'], group_id=workflow_detail.group_id).values('email')]
        logger.debug('发送执行结果通知，消息audit_id={}'.format(audit_id))
        logger.debug('消息标题:{}\n通知对象：{}\n消息内容：{}'.format(msg_title, list_to_addr + list_cc_addr, msg_content))
        mail_sender.send_email(msg_title, msg_content, list_to_addr, list_cc_addr=list_cc_addr)
    if sys_config.get('ding'):
        # 钉钉通知申请人，审核人，抄送DBA
        webhook_url = ResourceGroup.objects.get(group_id=workflow_detail.group_id).ding_webhook
        MailSender.send_ding(webhook_url, msg_title + '\n' + msg_content)

    if sys_config.get('mail') and sys_config.get('ddl_notify_auth_group', None) \
            and workflow_detail.status == '已正常结束':
        # 判断上线语句是否存在DDL，存在则通知相关人员
        sql_content = workflow_detail.sql_content
        # 删除注释语句
        sql_content = ''.join(
            map(lambda x: re.compile(r'(^--\s+.*|^/\*.*\*/;\s*$)').sub('', x, count=1),
                sql_content.splitlines(1))).strip()
        # 去除空行
        sql_content = re.sub('[\r\n\f]{2,}', '\n', sql_content)

        # 匹配DDL语句CREATE、ALTER（排除索引变更）、DROP、TRUNCATE、RENAME
        send = 0
        for statement in sqlparse.split(sql_content):
            # alter语法
            if re.match(r"^alter\s+table\s+\S+\s+(add|alter|change|drop|rename|modify)\s+(?!.*(index|key|unique))",
                        statement.strip().lower()):
                send = 1
                break
            # create语法
            elif re.match(r"^create\s+(temporary\s+)?(database|schema|table)", statement.strip().lower()):
                send = 1
                break
            # drop语法
            elif re.match(r"^drop|^rename|^truncate", statement.strip().lower()):
                send = 1
                break
            # rename语法
            elif re.match(r"", statement.strip().lower()):
                send = 1
                break
            # truncate语法
            elif re.match(r"", statement.strip().lower()):
                send = 1
                break

        if send == 1:
            # 消息内容通知
            msg_title = '[archery]有新的DDL语句执行完成#{}'.format(audit_id)
            msg_content = '''发起人：{}\n变更组：{}\n变更实例：{}\n变更数据库：{}\n工单名称：{}\n工单地址：{}\n工单预览：{}\n'''.format(
                Users.objects.get(username=workflow_detail.engineer).display,
                workflow_detail.group_name,
                workflow_detail.instance_name,
                workflow_detail.db_name,
                workflow_detail.workflow_name,
                url,
                workflow_detail.sql_content[0:500])
            # 获取通知成员
            msg_to = [email['email'] for email in
                      Users.objects.filter(groups__name=sys_config.get('ddl_notify_auth_group')).values('email')]

            # 发送
            logger.debug('发送DDL通知，消息audit_id={}'.format(audit_id))
            logger.debug('消息标题:{}\n通知对象：{}\n消息内容：{}'.format(msg_title, msg_to, msg_content))
            mail_sender.send_email(msg_title, msg_content, msg_to)
