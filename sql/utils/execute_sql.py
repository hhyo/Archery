# -*- coding: UTF-8 -*-
import re
import sqlparse
from sql.utils.resource_group import auth_group_users
from common.config import SysConfig
from common.utils.const import Const, WorkflowDict
from common.utils.sendmsg import MsgSender
from sql.models import Users, SqlWorkflow, ResourceGroup
from sql.utils.workflow_audit import Audit
from sql.engines import get_engine
import logging

logger = logging.getLogger('default')


def execute(workflow_id):
    """为延时或异步任务准备的execute, 传入工单ID即可"""
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    # 给定时执行的工单增加执行日志
    if workflow_detail.status == 'workflow_timingtask':
        audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                               workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
        Audit.add_log(audit_id=audit_id,
                      operation_type=5,
                      operation_type_desc='执行工单',
                      operation_info='系统定时执行',
                      operator='',
                      operator_display='系统'
                      )
    execute_engine = get_engine(workflow=workflow_detail)
    return execute_engine.execute_workflow()


def execute_callback(task):
    """异步任务的回调, 将结果填入数据库等等
    使用django-q的hook, 传入参数为整个task
    task.result 是真正的结果
    """
    workflow_id = task.args[0]
    workflow = SqlWorkflow.objects.get(id=workflow_id)
    workflow.finish_time = task.stopped

    if not task.success:
        # 不成功会返回字符串
        workflow.status = 'workflow_exception'
    elif task.result.warning or task.result.error:
        workflow.status = 'workflow_exception'
        execute_result = task.result
    else:
        workflow.status = 'workflow_finish'
        execute_result = task.result
    workflow.execute_result = execute_result.json()
    workflow.audit_remark = ''
    workflow.save()

    # 增加工单日志
    audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                           workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
    Audit.add_log(audit_id=audit_id,
                  operation_type=6,
                  operation_type_desc='执行结束',
                  operation_info='执行结果：{}'.format(workflow.status),
                  operator='',
                  operator_display='系统'
                  )

    # 发送消息
    send_msg(workflow)


# 执行结果通知
def send_msg(workflow_detail):
    mail_sender = MsgSender()
    sys_config = SysConfig()
    # 获取当前审批和审批流程
    base_url = sys_config.get('archery_base_url', 'http://127.0.0.1:8000').rstrip('/')
    audit_auth_group, current_audit_auth_group = Audit.review_info(workflow_detail.id, 2)
    audit_id = Audit.detail_by_workflow_id(workflow_detail.id, 2).audit_id
    url = "{base_url}/workflow/{audit_id}".format(base_url=base_url, audit_id=audit_id)
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
        MsgSender.send_ding(webhook_url, msg_title + '\n' + msg_content)

    # DDL通知
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
