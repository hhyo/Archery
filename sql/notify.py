# -*- coding: UTF-8 -*-
from sql.utils.sendmsg import MailSender
from .const import WorkflowDict


# 邮件消息通知,1.email,2.dingding
def send_msg(msg_data, msg_type, status):
    msg_sender = MailSender()
    if msg_data['workflow_type'] == WorkflowDict.workflow_type['query']:
        workflow_type = WorkflowDict.workflow_type['query_display']
    elif msg_data['workflow_type'] == WorkflowDict.workflow_type['sqlreview']:
        workflow_type = WorkflowDict.workflow_type['sqlreview_display']
    else:
        workflow_type = ''

    if status == WorkflowDict.workflow_status['audit_wait']:  # 申请阶段
        msg_title = "[{}]新的工单申请#{}".format(workflow_type, msg_data.get('audit_id'))
        msg_content = '''发起人：{}\n审核人：{}\n工单名称：{}\n工单地址：{}\n工单详情预览：{}\n'''.format(
            msg_data['workflow_from'],
            msg_data['workflow_auditors'],
            msg_data['workflow_title'],
            msg_data['workflow_url'],
            msg_data['workflow_content'])
    elif status == WorkflowDict.workflow_status['audit_success']:  # 审核通过
        msg_title = "[{}]工单审核通过#{}".format(workflow_type, msg_data.get('audit_id'))
        msg_content = '''发起人：{}\n审核人：{}\n工单名称：{}\n工单地址：{}\n工单详情预览：{}\n'''.format(
            msg_data['workflow_from'],
            msg_data['workflow_auditors'],
            msg_data['workflow_title'],
            msg_data['workflow_url'],
            msg_data['workflow_content'])
    elif status == WorkflowDict.workflow_status['audit_reject']:  # 审核驳回
        msg_title = "[{}]工单被驳回#{}".format(workflow_type, msg_data.get('audit_id'))
        msg_content = '''工单名称：{}\n工单地址：{}\n驳回原因：{}\n提醒：此工单被审核不通过，请按照驳回原因进行修改！'''.format(
            msg_data['workflow_title'],
            msg_data['workflow_url'],
            msg_data[
                'workflow_audit_remark'])
    elif status == WorkflowDict.workflow_status['audit_abort']:  # 审核取消
        msg_title = "[{}]提交人主动终止工单#{}".format(workflow_type, msg_data.get('audit_id'))
        msg_content = '''发起人：{}\n工单名称：{}\n工单地址：{}\n提醒：提交人主动终止流程'''.format(
            msg_data['workflow_from'],
            msg_data['workflow_title'],
            msg_data['workflow_url'])
    else:
        msg_title = ''
        msg_content = ''

    # 判断是发送钉钉还是发送邮件
    if msg_type == 1:
        email_reciver = msg_data['email_reciver']
        email_cc = msg_data['email_cc']
        msg_sender.sendEmail(msg_title, msg_content, [email_reciver], listCcAddr=email_cc)
    else:
        raise Exception('无该通知类型')
