# -*- coding: UTF-8 -*-
import datetime

from sql.models import QueryPrivilegesApply, Users, SqlWorkflow, Group, WorkflowAudit
from sql.utils.group import group_dbas
from sql.utils.sendmsg import MailSender
from .const import WorkflowDict


# 邮件消息通知,0.all,1.email,2.dingding
def send_msg(audit_id, msg_type, **kwargs):
    msg_sender = MailSender()
    audit_info = WorkflowAudit.objects.get(audit_id=audit_id)
    workflow_id = audit_info.workflow_id
    workflow_type = audit_info.workflow_type
    status = audit_info.current_status
    workflow_title = audit_info.workflow_title
    group_name = audit_info.group_name
    workflow_from = audit_info.create_user_display
    # 获取审核人中文名
    if audit_info.audit_users is None:
        workflow_auditors = '无需审批，系统自动审核通过'
    else:
        workflow_auditors = '.'.join([Users.objects.get(username=auditor).display for auditor in
                                      audit_info.audit_users.split(',')])
    workflow_url = kwargs.get('workflow_url')
    webhook_url = Group.objects.get(group_id=audit_info.group_id).ding_webhook

    # 准备消息内容
    if workflow_type == WorkflowDict.workflow_type['query']:
        workflow_type_display = WorkflowDict.workflow_type['query_display']
        workflow_detail = QueryPrivilegesApply.objects.get(apply_id=workflow_id)
        workflow_audit_remark = ''
        if workflow_detail.priv_type == 1:
            workflow_content = '''数据库清单：{}\n授权截止时间：{}\n结果集：{}\n'''.format(
                workflow_detail.db_list,
                datetime.datetime.strftime(workflow_detail.valid_date, '%Y-%m-%d %H:%M:%S'),
                workflow_detail.limit_num)
        elif workflow_detail.priv_type == 2:
            workflow_content = '''数据库：{}\n表清单：{}\n授权截止时间：{}\n结果集：{}\n'''.format(
                workflow_detail.db_list,
                workflow_detail.table_list,
                datetime.datetime.strftime(workflow_detail.valid_date, '%Y-%m-%d %H:%M:%S'),
                workflow_detail.limit_num)
    elif workflow_type == WorkflowDict.workflow_type['sqlreview']:
        workflow_type_display = WorkflowDict.workflow_type['sqlreview_display']
        workflow_detail = SqlWorkflow.objects.get(pk=workflow_id)
        workflow_audit_remark = workflow_detail.audit_remark
        workflow_content = workflow_detail.sql_content
    else:
        raise Exception('工单类型不正确')

    # 准备消息格式
    if status == WorkflowDict.workflow_status['audit_wait']:  # 申请阶段
        msg_title = "[{}]新的工单申请#{}".format(workflow_type_display, audit_id)
        # 接收人
        msg_email_reciver = [Users.objects.get(username=audit_info.current_audit_user).email]
        # 抄送对象
        email_cc = kwargs.get('email_cc', [])
        msg_email_cc = email_cc
        msg_content = '''发起人：{}\n审核人：{}\n工单名称：{}\n工单地址：{}\n工单详情预览：{}\n'''.format(
            workflow_from,
            workflow_auditors,
            workflow_title,
            workflow_url,
            workflow_content)
    elif status == WorkflowDict.workflow_status['audit_success']:  # 审核通过
        msg_title = "[{}]工单审核通过#{}".format(workflow_type_display, audit_id)
        # 接收人
        msg_email_reciver = [Users.objects.get(username=audit_info.create_user).email]
        # 抄送对象
        email_cc = kwargs.get('email_cc', [])
        msg_email_cc = email_cc.append(
            [email['email'] for email in group_dbas(audit_info.group_id).values('email')])
        msg_content = '''发起人：{}\n审核人：{}\n工单名称：{}\n工单地址：{}\n工单详情预览：{}\n'''.format(
            workflow_from,
            workflow_auditors,
            workflow_title,
            workflow_url,
            workflow_content)
    elif status == WorkflowDict.workflow_status['audit_reject']:  # 审核驳回
        msg_title = "[{}]工单被驳回#{}".format(workflow_type_display, audit_id)
        # 接收人
        msg_email_reciver = [Users.objects.get(username=audit_info.create_user).email]
        msg_email_cc = []
        msg_content = '''工单名称：{}\n工单地址：{}\n驳回原因：{}\n提醒：此工单被审核不通过，请按照驳回原因进行修改！'''.format(
            workflow_title,
            workflow_url,
            workflow_audit_remark)
    elif status == WorkflowDict.workflow_status['audit_abort']:  # 审核取消
        msg_title = "[{}]提交人主动终止工单#{}".format(workflow_type_display, audit_id)
        msg_email_reciver = [email['email'] for email in
                             Users.objects.filter(username__in=audit_info.audit_users.split(',')).values('email')]
        msg_email_cc = []
        msg_content = '''发起人：{}\n工单名称：{}\n工单地址：{}\n提醒：提交人主动终止流程'''.format(
            workflow_from,
            workflow_title,
            workflow_url)
    else:
        raise Exception('工单状态不正确')

    if isinstance(msg_email_reciver, str):
        msg_email_reciver = [msg_email_reciver]
    if isinstance(msg_email_cc, str):
        msg_email_cc = [msg_email_cc]

    # 判断是发送钉钉还是发送邮件
    if msg_type == 0:
        msg_sender.sendEmail(msg_title, msg_content, msg_email_reciver, listCcAddr=msg_email_cc)
        msg_sender.sendDing(webhook_url, msg_title + '\n' + msg_content)
    if msg_type == 1:
        msg_sender.sendEmail(msg_title, msg_content, msg_email_reciver, listCcAddr=msg_email_cc)
    elif msg_type == 2:
        msg_sender.sendDing(webhook_url, msg_title + '\n' + msg_content)
