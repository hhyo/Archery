# -*- coding: UTF-8 -*-
import datetime
import re
from itertools import chain

from django.contrib.auth.models import Group
from common.config import SysConfig
from sql.models import (
    QueryPrivilegesApply,
    Users,
    SqlWorkflow,
    ResourceGroup,
    ArchiveConfig,
)
from sql.utils.resource_group import auth_group_users
from common.utils.sendmsg import MsgSender
from common.utils.const import WorkflowDict
from sql.utils.workflow_audit import Audit

import logging

logger = logging.getLogger("default")


def __notify_cnf_status():
    """返回消息通知开关"""
    sys_config = SysConfig()
    mail_status = sys_config.get("mail")
    ding_status = sys_config.get("ding_to_person")
    ding_webhook_status = sys_config.get("ding")
    wx_status = sys_config.get("wx")
    qywx_webhook_status = sys_config.get("qywx_webhook")
    feishu_webhook_status = sys_config.get("feishu_webhook")
    feishu_status = sys_config.get("feishu")
    if not any(
        [
            mail_status,
            ding_status,
            ding_webhook_status,
            wx_status,
            feishu_status,
            feishu_webhook_status,
            qywx_webhook_status,
        ]
    ):
        logger.info("未开启任何消息通知，可在系统设置中开启")
        return False
    else:
        return True


def __send(msg_title, msg_content, msg_to, msg_cc=None, **kwargs):
    """
    按照通知配置发送通知消息
    :param msg_title: 通知标题
    :param msg_content: 通知内容
    :param msg_to:  通知人user list
    :return:
    """
    sys_config = SysConfig()
    msg_sender = MsgSender()
    msg_cc = msg_cc if msg_cc else []
    dingding_webhook = kwargs.get("dingding_webhook")
    feishu_webhook = kwargs.get("feishu_webhook")
    qywx_webhook = kwargs.get("qywx_webhook")
    msg_to_email = [user.email for user in msg_to if user.email]
    msg_cc_email = [user.email for user in msg_cc if user.email]
    msg_to_ding_user = [
        user.ding_user_id for user in chain(msg_to, msg_cc) if user.ding_user_id
    ]
    msg_to_wx_user = [
        user.wx_user_id if user.wx_user_id else user.username
        for user in chain(msg_to, msg_cc)
    ]
    logger.info(f"{msg_to_email}{msg_cc_email}{msg_to_wx_user}{chain(msg_to, msg_cc)}")
    if sys_config.get("mail"):
        msg_sender.send_email(
            msg_title, msg_content, msg_to_email, list_cc_addr=msg_cc_email
        )
    if sys_config.get("ding") and dingding_webhook:
        msg_sender.send_ding(dingding_webhook, msg_title + "\n" + msg_content)
    if sys_config.get("ding_to_person"):
        msg_sender.send_ding2user(msg_to_ding_user, msg_title + "\n" + msg_content)
    if sys_config.get("wx"):
        msg_sender.send_wx2user(msg_title + "\n" + msg_content, msg_to_wx_user)
    if sys_config.get("feishu_webhook") and feishu_webhook:
        msg_sender.send_feishu_webhook(feishu_webhook, msg_title, msg_content)
    if sys_config.get("feishu"):
        open_id = [
            user.feishu_open_id for user in chain(msg_to, msg_cc) if user.feishu_open_id
        ]
        user_mail = [
            user.email for user in chain(msg_to, msg_cc) if not user.feishu_open_id
        ]
        msg_sender.send_feishu_user(msg_title, msg_content, open_id, user_mail)
    if sys_config.get("qywx_webhook") and qywx_webhook:
        msg_sender.send_qywx_webhook(qywx_webhook, msg_title + "\n" + msg_content)


def notify_for_audit(audit_id, **kwargs):
    """
    工作流消息通知，不包含工单执行结束的通知
    :param audit_id:
    :param kwargs:
    :return:
    """
    # 判断是否开启消息通知，未开启直接返回
    if not __notify_cnf_status():
        return None
    sys_config = SysConfig()

    # 获取审核信息
    audit_detail = Audit.detail(audit_id=audit_id)
    audit_id = audit_detail.audit_id
    workflow_audit_remark = kwargs.get("audit_remark", "")
    base_url = sys_config.get("archery_base_url", "http://127.0.0.1:8000").rstrip("/")
    workflow_url = "{base_url}/workflow/{audit_id}".format(
        base_url=base_url, audit_id=audit_detail.audit_id
    )
    workflow_id = audit_detail.workflow_id
    workflow_type = audit_detail.workflow_type
    status = audit_detail.current_status
    workflow_title = audit_detail.workflow_title
    workflow_from = audit_detail.create_user_display
    group_name = audit_detail.group_name
    dingding_webhook = ResourceGroup.objects.get(
        group_id=audit_detail.group_id
    ).ding_webhook
    feishu_webhook = ResourceGroup.objects.get(
        group_id=audit_detail.group_id
    ).feishu_webhook
    qywx_webhook = ResourceGroup.objects.get(
        group_id=audit_detail.group_id
    ).qywx_webhook
    # 获取当前审批和审批流程
    workflow_auditors, current_workflow_auditors = Audit.review_info(
        audit_detail.workflow_id, audit_detail.workflow_type
    )

    # 准备消息内容
    if workflow_type == WorkflowDict.workflow_type["query"]:
        workflow_type_display = WorkflowDict.workflow_type["query_display"]
        workflow_detail = QueryPrivilegesApply.objects.get(apply_id=workflow_id)
        instance = workflow_detail.instance.instance_name
        db_name = " "
        if workflow_detail.priv_type == 1:
            workflow_content = """数据库清单：{}\n授权截止时间：{}\n结果集：{}\n""".format(
                workflow_detail.db_list,
                datetime.datetime.strftime(
                    workflow_detail.valid_date, "%Y-%m-%d %H:%M:%S"
                ),
                workflow_detail.limit_num,
            )
        elif workflow_detail.priv_type == 2:
            db_name = workflow_detail.db_list
            workflow_content = """数据库：{}\n表清单：{}\n授权截止时间：{}\n结果集：{}\n""".format(
                workflow_detail.db_list,
                workflow_detail.table_list,
                datetime.datetime.strftime(
                    workflow_detail.valid_date, "%Y-%m-%d %H:%M:%S"
                ),
                workflow_detail.limit_num,
            )
        else:
            workflow_content = ""
    elif workflow_type == WorkflowDict.workflow_type["sqlreview"]:
        workflow_type_display = WorkflowDict.workflow_type["sqlreview_display"]
        workflow_detail = SqlWorkflow.objects.get(pk=workflow_id)
        instance = workflow_detail.instance.instance_name
        db_name = workflow_detail.db_name
        workflow_content = re.sub(
            "[\r\n\f]{2,}",
            "\n",
            workflow_detail.sqlworkflowcontent.sql_content[0:500].replace("\r", ""),
        )
    elif workflow_type == WorkflowDict.workflow_type["archive"]:
        workflow_type_display = WorkflowDict.workflow_type["archive_display"]
        workflow_detail = ArchiveConfig.objects.get(pk=workflow_id)
        instance = workflow_detail.src_instance.instance_name
        db_name = workflow_detail.src_db_name
        workflow_content = """归档表：{}\n归档模式：{}\n归档条件：{}\n""".format(
            workflow_detail.src_table_name,
            workflow_detail.mode,
            workflow_detail.condition,
        )
    else:
        raise Exception("工单类型不正确")

    # 准备消息格式
    if status == WorkflowDict.workflow_status["audit_wait"]:  # 申请阶段
        msg_title = "[{}]新的工单申请#{}".format(workflow_type_display, audit_id)
        # 接收人，发送给该资源组内对应权限组所有的用户
        auth_group_names = Group.objects.get(id=audit_detail.current_audit).name
        msg_to = auth_group_users([auth_group_names], audit_detail.group_id)
        msg_cc = Users.objects.filter(username__in=kwargs.get("cc_users", []))
        # 消息内容
        msg_content = """发起时间：{}\n发起人：{}\n组：{}\n目标实例：{}\n数据库：{}\n审批流程：{}\n当前审批：{}\n工单名称：{}\n工单地址：{}\n工单详情预览：{}\n""".format(
            workflow_detail.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            workflow_from,
            group_name,
            instance,
            db_name,
            workflow_auditors,
            current_workflow_auditors,
            workflow_title,
            workflow_url,
            workflow_content,
        )
    elif status == WorkflowDict.workflow_status["audit_success"]:  # 审核通过
        msg_title = "[{}]工单审核通过#{}".format(workflow_type_display, audit_id)
        # 接收人，仅发送给申请人
        msg_to = [Users.objects.get(username=audit_detail.create_user)]
        msg_cc = Users.objects.filter(username__in=kwargs.get("cc_users", []))
        # 消息内容
        msg_content = """发起时间：{}\n发起人：{}\n组：{}\n目标实例：{}\n数据库：{}\n审批流程：{}\n工单名称：{}\n工单地址：{}\n工单详情预览：{}\n""".format(
            workflow_detail.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            workflow_from,
            group_name,
            instance,
            db_name,
            workflow_auditors,
            workflow_title,
            workflow_url,
            workflow_content,
        )
    elif status == WorkflowDict.workflow_status["audit_reject"]:  # 审核驳回
        msg_title = "[{}]工单被驳回#{}".format(workflow_type_display, audit_id)
        # 接收人，仅发送给申请人
        msg_to = [Users.objects.get(username=audit_detail.create_user)]
        msg_cc = Users.objects.filter(username__in=kwargs.get("cc_users", []))
        # 消息内容
        msg_content = """发起时间：{}\n目标实例：{}\n数据库：{}\n工单名称：{}\n工单地址：{}\n驳回原因：{}\n提醒：此工单被审核不通过，请按照驳回原因进行修改！""".format(
            workflow_detail.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            instance,
            db_name,
            workflow_title,
            workflow_url,
            re.sub("[\r\n\f]{2,}", "\n", workflow_audit_remark),
        )
    elif status == WorkflowDict.workflow_status["audit_abort"]:  # 审核取消，通知所有审核人
        msg_title = "[{}]提交人主动终止工单#{}".format(workflow_type_display, audit_id)
        # 接收人，发送给该资源组内对应权限组所有的用户
        auth_group_names = [
            Group.objects.get(id=auth_group_id).name
            for auth_group_id in audit_detail.audit_auth_groups.split(",")
        ]
        msg_to = auth_group_users(auth_group_names, audit_detail.group_id)
        msg_cc = Users.objects.filter(username__in=kwargs.get("cc_users", []))
        # 消息内容
        msg_content = """发起时间：{}\n发起人：{}\n组：{}\n目标实例：{}\n数据库：{}\n工单名称：{}\n工单地址：{}\n终止原因：{}""".format(
            workflow_detail.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            workflow_from,
            group_name,
            instance,
            db_name,
            workflow_title,
            workflow_url,
            re.sub("[\r\n\f]{2,}", "\n", workflow_audit_remark),
        )
    else:
        raise Exception("工单状态不正确")
    logger.info(f"通知Debug{msg_to}{msg_cc}")
    # 发送通知
    __send(
        msg_title,
        msg_content,
        msg_to,
        msg_cc,
        feishu_webhook=feishu_webhook,
        dingding_webhook=dingding_webhook,
        qywx_webhook=qywx_webhook,
    )


def notify_for_execute(workflow):
    """
    工单执行结束的通知
    :param workflow:
    :return:
    """
    # 判断是否开启消息通知，未开启直接返回
    if not __notify_cnf_status():
        return None
    sys_config = SysConfig()

    # 获取当前审批和审批流程
    base_url = sys_config.get("archery_base_url", "http://127.0.0.1:8000").rstrip("/")
    audit_auth_group, current_audit_auth_group = Audit.review_info(workflow.id, 2)
    audit_id = Audit.detail_by_workflow_id(workflow.id, 2).audit_id
    url = "{base_url}/workflow/{audit_id}".format(base_url=base_url, audit_id=audit_id)
    msg_title = "[{}]工单{}#{}".format(
        WorkflowDict.workflow_type["sqlreview_display"],
        workflow.get_status_display(),
        audit_id,
    )
    msg_content = """发起时间：{}\n发起人：{}\n组：{}\n目标实例：{}\n数据库：{}\n审批流程：{}\n工单名称：{}\n工单地址：{}\n工单详情预览：{}\n""".format(
        workflow.create_time.strftime("%Y-%m-%d %H:%M:%S"),
        workflow.engineer_display,
        workflow.group_name,
        workflow.instance.instance_name,
        workflow.db_name,
        audit_auth_group,
        workflow.workflow_name,
        url,
        re.sub(
            "[\r\n\f]{2,}",
            "\n",
            workflow.sqlworkflowcontent.sql_content[0:500].replace("\r", ""),
        ),
    )
    # 邮件通知申请人，抄送DBA
    msg_to = Users.objects.filter(username=workflow.engineer)
    msg_cc = auth_group_users(auth_group_names=["DBA"], group_id=workflow.group_id)

    # 处理接收人
    dingding_webhook = ResourceGroup.objects.get(
        group_id=workflow.group_id
    ).ding_webhook
    feishu_webhook = ResourceGroup.objects.get(
        group_id=workflow.group_id
    ).feishu_webhook
    qywx_webhook = ResourceGroup.objects.get(group_id=workflow.group_id).qywx_webhook
    # 发送通知
    __send(
        msg_title,
        msg_content,
        msg_to,
        msg_cc,
        dingding_webhook=dingding_webhook,
        feishu_webhook=feishu_webhook,
        qywx_webhook=qywx_webhook,
    )

    # DDL通知
    if sys_config.get("ddl_notify_auth_group") and workflow.status == "workflow_finish":
        # 判断上线语句是否存在DDL，存在则通知相关人员
        if workflow.syntax_type == 1:
            # 消息内容通知
            msg_title = "[Archery]有新的DDL语句执行完成#{}".format(audit_id)
            msg_content = """发起人：{}\n变更组：{}\n变更实例：{}\n变更数据库：{}\n工单名称：{}\n工单地址：{}\n工单预览：{}\n""".format(
                Users.objects.get(username=workflow.engineer).display,
                workflow.group_name,
                workflow.instance.instance_name,
                workflow.db_name,
                workflow.workflow_name,
                url,
                workflow.sqlworkflowcontent.sql_content[0:500],
            )
            # 获取通知成员ddl_notify_auth_group
            ddl_notify_auth_group = sys_config.get("ddl_notify_auth_group", "").split(
                ","
            )
            msg_to = Users.objects.filter(groups__name__in=ddl_notify_auth_group)
            # 发送通知
            __send(msg_title, msg_content, msg_to, msg_cc)


def notify_for_my2sql(task):
    """
    my2sql执行结束的通知
    :param task:
    :return:
    """
    # 判断是否开启消息通知，未开启直接返回
    if not __notify_cnf_status():
        return None
    if task.success:
        msg_title = "[Archery 通知]My2SQL执行结束"
        msg_content = f"解析的SQL文件在{task.result[1]}目录下，请前往查看"
    else:
        msg_title = "[Archery 通知]My2SQL执行失败"
        msg_content = f"{task.result}"
    # 发送
    msg_to = [task.kwargs["user"]]
    __send(msg_title, msg_content, msg_to)
