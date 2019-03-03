# -*- coding: UTF-8 -*-
import datetime
import re
from django.contrib.auth.models import Group
from common.config import SysConfig
from sql.models import QueryPrivilegesApply, Users, SqlWorkflow, ResourceGroup
from sql.utils.resource_group import auth_group_users
from common.utils.sendmsg import MsgSender
from common.utils.const import WorkflowDict
from sql.utils.workflow_audit import Audit

import logging

logger = logging.getLogger('default')


def notify(audit_id, msg_type=0, **kwargs):
    """
    工作流消息通知，不包含工单执行结束的通知
    :param audit_id:
    :param msg_type: 0.all,1.email,2.dingding
    :param kwargs:
    :return:
    """
    # 判断是否开启消息通知，未开启直接返回
    sys_config = SysConfig()
    if not sys_config.get('mail') and not sys_config.get('ding'):
        logger.info('未开启消息通知，可在系统设置中开启')
        return None
    # 获取审核信息
    audit_detail = Audit.detail(audit_id=audit_id)
    audit_id = audit_detail.audit_id
    workflow_audit_remark = kwargs.get('audit_remark', '')
    base_url = sys_config.get('archery_base_url', 'http://127.0.0.1:8000').rstrip('/')
    workflow_url = "{base_url}/workflow/{audit_id}".format(base_url=base_url, audit_id=audit_detail.audit_id)
    msg_email_cc = kwargs.get('email_cc', [])
    workflow_id = audit_detail.workflow_id
    workflow_type = audit_detail.workflow_type
    status = audit_detail.current_status
    workflow_title = audit_detail.workflow_title
    workflow_from = audit_detail.create_user_display
    group_name = audit_detail.group_name
    webhook_url = ResourceGroup.objects.get(group_id=audit_detail.group_id).ding_webhook

    # 获取当前审批和审批流程
    workflow_auditors, current_workflow_auditors = Audit.review_info(audit_detail.workflow_id,
                                                                     audit_detail.workflow_type)

    # 准备消息内容
    if workflow_type == WorkflowDict.workflow_type['query']:
        workflow_type_display = WorkflowDict.workflow_type['query_display']
        workflow_detail = QueryPrivilegesApply.objects.get(apply_id=workflow_id)
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
        else:
            workflow_content = ''
    elif workflow_type == WorkflowDict.workflow_type['sqlreview']:
        workflow_type_display = WorkflowDict.workflow_type['sqlreview_display']
        workflow_detail = SqlWorkflow.objects.get(pk=workflow_id)
        workflow_content = re.sub('[\r\n\f]{2,}', '\n', workflow_detail.sql_content[0:500].replace('\r', ''))
    else:
        raise Exception('工单类型不正确')

    # 准备消息格式
    if status == WorkflowDict.workflow_status['audit_wait']:  # 申请阶段
        msg_title = "[{}]新的工单申请#{}".format(workflow_type_display, audit_id)
        # 接收人，发送给该资源组内对应权限组所有的用户
        auth_group_names = Group.objects.get(id=audit_detail.current_audit).name
        msg_email_reciver = [user.email for user in
                             auth_group_users([auth_group_names], audit_detail.group_id)]
        # 消息内容
        msg_content = '''发起人：{}\n组：{}\n审批流程：{}\n当前审批：{}\n工单名称：{}\n工单地址：{}\n工单详情预览：{}\n'''.format(
            workflow_from,
            group_name,
            workflow_auditors,
            current_workflow_auditors,
            workflow_title,
            workflow_url,
            workflow_content)
    elif status == WorkflowDict.workflow_status['audit_success']:  # 审核通过
        msg_title = "[{}]工单审核通过#{}".format(workflow_type_display, audit_id)
        # 接收人，仅发送给申请人
        msg_email_reciver = [Users.objects.get(username=audit_detail.create_user).email]
        # 消息内容
        msg_content = '''发起人：{}\n组：{}\n审批流程：{}\n工单名称：{}\n工单地址：{}\n工单详情预览：{}\n'''.format(
            workflow_from,
            group_name,
            workflow_auditors,
            workflow_title,
            workflow_url,
            workflow_content)
    elif status == WorkflowDict.workflow_status['audit_reject']:  # 审核驳回
        msg_title = "[{}]工单被驳回#{}".format(workflow_type_display, audit_id)
        # 接收人，仅发送给申请人
        msg_email_reciver = [Users.objects.get(username=audit_detail.create_user).email]
        # 消息内容
        msg_content = '''工单名称：{}\n工单地址：{}\n驳回原因：{}\n提醒：此工单被审核不通过，请按照驳回原因进行修改！'''.format(
            workflow_title,
            workflow_url,
            workflow_audit_remark)
    elif status == WorkflowDict.workflow_status['audit_abort']:  # 审核取消，通知所有审核人
        msg_title = "[{}]提交人主动终止工单#{}".format(workflow_type_display, audit_id)
        # 接收人，发送给该资源组内对应权限组所有的用户
        auth_group_names = [Group.objects.get(id=auth_group_id).name for auth_group_id in
                            audit_detail.audit_auth_groups.split(',')]
        msg_email_reciver = [user.email for user in auth_group_users(auth_group_names, audit_detail.group_id)]
        # 消息内容
        msg_content = '''发起人：{}\n组：{}\n工单名称：{}\n工单地址：{}\n提醒：提交人主动终止流程'''.format(
            workflow_from,
            group_name,
            workflow_title,
            workflow_url)
    else:
        raise Exception('工单状态不正确')

    # 判断是发送钉钉还是发送邮件
    msg_sender = MsgSender()
    logger.info('发送消息通知，消息audit_id={}'.format(audit_id))
    logger.info('消息标题:{}\n通知对象：{}\n消息内容：{}'.format(msg_title, msg_email_reciver, msg_content))
    if msg_type == 0:
        if sys_config.get('mail'):
            msg_sender.send_email(msg_title, msg_content, msg_email_reciver, list_cc_addr=msg_email_cc)
        if sys_config.get('ding'):
            msg_sender.send_ding(webhook_url, msg_title + '\n' + msg_content)
    elif msg_type == 1:
        msg_sender.send_email(msg_title, msg_content, msg_email_reciver, list_cc_addr=msg_email_cc)
    elif msg_type == 2:
        msg_sender.send_ding(webhook_url, msg_title + '\n' + msg_content)
