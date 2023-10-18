# -*- coding: UTF-8 -*-
import datetime
import importlib
from enum import Enum
import re
from itertools import chain
from typing import Union, List
from dataclasses import dataclass

import requests
from django.contrib.auth.models import Group
from django.conf import settings

from common.config import SysConfig
from sql.models import (
    QueryPrivilegesApply,
    Users,
    SqlWorkflow,
    ResourceGroup,
    ArchiveConfig, WorkflowAudit, WorkflowAuditDetail,
)
from sql_api.serializers import (
    WorkflowSerializer,
    WorkflowAuditListSerializer,
    QueryPrivilegesApplySerializer,
    ArchiveConfigSerializer
)
from sql.utils.resource_group import auth_group_users
from common.utils.sendmsg import MsgSender
from common.utils.const import WorkflowDict
from sql.utils.workflow_audit import Audit

import logging

logger = logging.getLogger("default")


class EventType(Enum):
    EXECUTE = "execute"
    AUDIT = "audit"
    M2SQL = "m2sql"


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
    generic_webhook = sys_config.get("generic_webhook")
    if not any(
            [
                mail_status,
                ding_status,
                ding_webhook_status,
                wx_status,
                feishu_status,
                feishu_webhook_status,
                qywx_webhook_status,
                generic_webhook,
            ]
    ):
        logger.info("未开启任何消息通知，可在系统设置中开启")
        return False
    else:
        return True


@dataclass
class My2SqlResult:
    submitter: str
    success: bool
    file_path: str = ""
    error: str = ""


def notify_for_my2sql(task):
    """
    my2sql执行结束的通知
    :param task:
    :return:
    """
    if task.success:
        result = My2SqlResult(
            success=True,
            submitter=task.kwargs["user"],
            file_path=task.result[1]
        )
    else:
        result = My2SqlResult(
            success=False,
            submitter=task.kwargs["user"],
            error=task.result
        )
    # 发送
    sys_config = SysConfig()
    auto_notify(workflow=result, sys_config=sys_config, event_type=EventType.M2SQL)


class Notifier:
    name = "base"

    def __init__(self,
                 workflow: Union[SqlWorkflow, ArchiveConfig, QueryPrivilegesApply, My2SqlResult],
                 sys_config: SysConfig,
                 audit: WorkflowAudit = None,
                 audit_detail: WorkflowAuditDetail = None,
                 event_type: EventType = EventType.AUDIT):
        self.workflow = workflow
        self.audit = audit
        self.audit_detail = audit_detail
        self.event_type = event_type
        self.sys_config = sys_config

    def render(self):
        raise NotImplementedError

    def send(self):
        raise NotImplementedError


class GenericWebhookNotifier(Notifier):
    name = "generic_webhook"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_data = None

    def render(self):
        if isinstance(self.workflow, SqlWorkflow):
            workflow_dict = WorkflowSerializer(self.workflow).data
        elif isinstance(self.workflow, ArchiveConfig):
            workflow_dict = ArchiveConfigSerializer(self.workflow).data
        elif isinstance(self.workflow, QueryPrivilegesApply):
            workflow_dict = QueryPrivilegesApplySerializer(self.workflow).data
        else:
            raise ValueError(f"workflow type `{type(self.workflow)}` not supported yet")

        audit_dict = WorkflowAuditListSerializer(self.audit).data
        self.request_data = {
            "audit": audit_dict,
            "workflow": workflow_dict,
        }

    def send(self):
        url = self.sys_config.get("generic_webhook")
        requests.post(url, json=self.request_data)


@dataclass
class LegacyMessage:
    msg_title: str
    msg_content: str
    msg_to: List[Users] = None
    msg_cc: List[Users] = None


class LegacyRender(Notifier):
    messages: List[LegacyMessage]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = []

    def render_audit(self):
        # 获取审核信息
        audit_id = self.audit.audit_id
        base_url = self.sys_config.get("archery_base_url", "http://127.0.0.1:8000").rstrip("/")
        workflow_url = "{base_url}/workflow/{audit_id}".format(
            base_url=base_url, audit_id=self.audit.audit_id
        )
        workflow_id = self.audit.workflow_id
        workflow_type = self.audit.workflow_type
        status = self.audit.current_status
        workflow_title = self.audit.workflow_title
        workflow_from = self.audit.create_user_display
        group_name = self.audit.group_name
        # 获取当前审批和审批流程
        workflow_auditors, current_workflow_auditors = Audit.review_info(
            self.audit.workflow_id, self.audit.workflow_type
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
            auth_group_names = Group.objects.get(id=self.audit.current_audit).name
            msg_to = auth_group_users([auth_group_names], self.audit.group_id)
            # 消息内容
            msg_content = """发起时间：{}
发起人：{}
组：{}
目标实例：{}
数据库：{}
审批流程：{}
当前审批：{}
工单名称：{}
工单地址：{}
工单详情预览：{}""".format(
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
            msg_to = [Users.objects.get(username=self.audit.create_user)]
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
            msg_to = [Users.objects.get(username=self.audit.create_user)]
            # 消息内容
            msg_content = """发起时间：{}\n目标实例：{}\n数据库：{}\n工单名称：{}\n工单地址：{}\n驳回原因：{}\n提醒：此工单被审核不通过，请按照驳回原因进行修改！""".format(
                workflow_detail.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                instance,
                db_name,
                workflow_title,
                workflow_url,
                re.sub("[\r\n\f]{2,}", "\n", self.audit_detail.remark),
            )
        elif status == WorkflowDict.workflow_status["audit_abort"]:  # 审核取消，通知所有审核人
            msg_title = "[{}]提交人主动终止工单#{}".format(workflow_type_display, audit_id)
            # 接收人，发送给该资源组内对应权限组所有的用户
            auth_group_names = [
                Group.objects.get(id=auth_group_id).name
                for auth_group_id in self.audit.audit_auth_groups.split(",")
            ]
            msg_to = auth_group_users(auth_group_names, self.audit.group_id)
            # 消息内容
            msg_content = """发起时间：{}\n发起人：{}\n组：{}\n目标实例：{}\n数据库：{}\n工单名称：{}\n工单地址：{}\n终止原因：{}""".format(
                workflow_detail.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                workflow_from,
                group_name,
                instance,
                db_name,
                workflow_title,
                workflow_url,
                re.sub("[\r\n\f]{2,}", "\n", self.audit_detail.remark),
            )
        else:
            raise Exception("工单状态不正确")
        logger.info(f"通知Debug{msg_to}")
        self.messages.append(LegacyMessage(
            msg_title, msg_content, msg_to
        ))

    def render_execute(self):
        base_url = self.sys_config.get("archery_base_url", "http://127.0.0.1:8000").rstrip("/")
        audit_auth_group, current_audit_auth_group = Audit.review_info(self.workflow.id, 2)
        audit_id = Audit.detail_by_workflow_id(self.workflow.id, 2).audit_id
        url = "{base_url}/workflow/{audit_id}".format(base_url=base_url, audit_id=audit_id)
        msg_title = (f"[{WorkflowDict.workflow_type['sqlreview_display']}]工单"
                     f"{self.workflow.get_status_display()}#{audit_id}")
        preview = re.sub(
            '[\r\n\f]{2,}',
            '\n',
            self.workflow.sqlworkflowcontent.sql_content[0:500].replace("\r", ""), )
        msg_content = f"""发起时间：{self.workflow.create_time.strftime("%Y-%m-%d %H:%M:%S")}
发起人：{self.workflow.engineer_display}
组：{self.workflow.group_name}
目标实例：{self.workflow.instance.instance_name}
数据库：{self.workflow.db_name}
审批流程：{audit_auth_group}
工单名称：{self.workflow.workflow_name}
工单地址：{url}
工单详情预览：{preview}"""
        # 邮件通知申请人，抄送DBA
        msg_to = Users.objects.filter(username=self.workflow.engineer)
        msg_cc = auth_group_users(auth_group_names=["DBA"], group_id=self.workflow.group_id)
        self.messages.append(LegacyMessage(
            msg_title, msg_content, msg_to, msg_cc
        ))
        # DDL通知
        if self.sys_config.get("ddl_notify_auth_group") and self.workflow.status == "workflow_finish":
            # 判断上线语句是否存在DDL，存在则通知相关人员
            if self.workflow.syntax_type == 1:
                # 消息内容通知
                msg_title = "[Archery]有新的DDL语句执行完成#{}".format(audit_id)
                msg_content = f"""发起人：{Users.objects.get(username=self.workflow.engineer).display}
变更组：{self.workflow.group_name}
变更实例：{self.workflow.instance.instance_name}
变更数据库：{self.workflow.db_name}
工单名称：{self.workflow.workflow_name}
工单地址：{url}
工单预览：{preview}"""
                # 获取通知成员ddl_notify_auth_group
                ddl_notify_auth_group = self.sys_config.get("ddl_notify_auth_group", "").split(
                    ","
                )
                msg_to = Users.objects.filter(groups__name__in=ddl_notify_auth_group)
                self.messages.append(LegacyMessage(
                    msg_title, msg_content, msg_to
                ))

    def render_m2sql(self):
        submitter_in_db = Users.objects.get(username=self.workflow.submitter)
        if self.workflow.success:
            title = "[Archery 通知]My2SQL执行结束"
            content = f"解析的SQL文件在{self.workflow.file_path}目录下，请前往查看"
        else:
            title = "[Archery 通知]My2SQL执行失败"
            content = self.workflow.error
        self.messages = [
            LegacyMessage(
                msg_to=[submitter_in_db],
                msg_title=title,
                msg_content=content,
            )
        ]

    def render(self):
        """渲染消息, 存储到 self.messages"""
        if self.event_type == EventType.EXECUTE:
            self.render_execute()
        if self.event_type == EventType.AUDIT:
            self.render_audit()
        if self.event_type == EventType.M2SQL:
            self.render_m2sql()


class DingdingWebhookNotifier(LegacyRender):
    name = "dingding_webhook"

    def send(self):
        dingding_webhook = ResourceGroup.objects.get(
            group_id=self.audit.group_id
        ).ding_webhook
        if not dingding_webhook:
            return
        msg_sender = MsgSender()
        for m in self.messages:
            msg_sender.send_ding(dingding_webhook, f"{m.msg_title}\n{m.msg_content}")


class DingdingPersonNotifier(LegacyRender):
    name = "ding_to_person"

    def send(self):
        msg_sender = MsgSender()
        for m in self.messages:
            ding_user_id_list = [
                user.ding_user_id for user in chain(m.msg_to, m.msg_cc) if user.ding_user_id
            ]
            msg_sender.send_ding2user(ding_user_id_list, f"{m.msg_title}\n{m.msg_content}")


class FeishuWebhookNotifier(LegacyRender):
    name = "feishu_webhook"

    def send(self):
        feishu_webhook = ResourceGroup.objects.get(group_id=self.audit.group_id).feishu_webhook
        if not feishu_webhook:
            return
        msg_sender = MsgSender()
        for m in self.messages:
            msg_sender.send_feishu_webhook(feishu_webhook, m.msg_title, m.msg_content)


class FeishuPersonNotifier(LegacyRender):
    name = "feishu_to_person"

    def send(self):
        msg_sender = MsgSender()
        for m in self.messages:
            open_id = [
                user.feishu_open_id for user in chain(m.msg_to, m.msg_cc) if user.feishu_open_id
            ]
            user_mail = [
                user.email for user in chain(m.msg_to, m.msg_cc) if not user.feishu_open_id
            ]
            msg_sender.send_feishu_user(m.msg_title, m.msg_content, open_id, user_mail)


class QywxWebhookNotifier(LegacyRender):
    name = "qywx_webhook"

    def send(self):
        qywx_webhook = ResourceGroup.objects.get(
            group_id=self.audit.group_id
        ).qywx_webhook
        if not qywx_webhook:
            return
        msg_sender = MsgSender()
        for m in self.messages:
            msg_sender.send_qywx_webhook(qywx_webhook, f"{m.msg_title}\n{m.msg_content}")


def auto_notify(sys_config: SysConfig,
                workflow: Union[SqlWorkflow, ArchiveConfig, QueryPrivilegesApply, My2SqlResult] = None,
                audit: WorkflowAudit = None,
                audit_detail: WorkflowAuditDetail = None,
                event_type: EventType = EventType.AUDIT):
    """
    加载所有的 notifier, 调用 notifier 的 render 和 send 方法
    内部方法, 有数据库查询, 为了方便测试, 请勿使用 async_task 调用, 防止 patch 后调用失败
    """
    if not workflow and event_type == EventType.AUDIT:
        if audit.workflow_type == 1:
            workflow = QueryPrivilegesApply.objects.get(apply_id=audit.workflow_id)
        if audit.workflow_type == 2:
            workflow = SqlWorkflow.objects.get(id=audit.workflow_id)
    for notifier in settings.ENABLED_NOTIFIERS:
        file, _class = notifier.split(":")
        notify_module = importlib.import_module(file)
        notifier = getattr(notify_module, _class)
        notifier = notifier(workflow=workflow, audit=audit, audit_detail=audit_detail,
                            event_type=event_type, sys_config=sys_config)
        notifier.render()
        notifier.send()


def notify_for_execute(workflow: SqlWorkflow, sys_config: SysConfig = None):
    if not sys_config:
        sys_config = SysConfig()
    auto_notify(
        workflow=workflow,
        sys_config=sys_config
    )


def notify_for_audit(workflow_audit: WorkflowAudit, workflow_audit_detail: WorkflowAuditDetail = None):
    """
    工作流消息通知适配器, 供 async_task 调用, 方便后续的 mock
    直接传 model 对象, 注意函数内部不要做数据库相关的查询, 以免测试不好mock
    :param workflow_audit:
    :param workflow_audit_detail:
    :return:
    """
    sys_config = SysConfig()
    auto_notify(
        workflow=None,
        audit=workflow_audit,
        audit_detail=workflow_audit_detail,
        sys_config=sys_config
    )
