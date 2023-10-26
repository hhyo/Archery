# -*- coding: UTF-8 -*-
import importlib
from dataclasses import dataclass, field
from typing import Union, Optional, List

from django.contrib.auth.models import Group
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings

from sql.utils.resource_group import user_groups, auth_group_users
from sql.utils.sql_review import is_auto_review
from common.utils.const import WorkflowStatus, WorkflowType, WorkflowAction
from sql.models import (
    WorkflowAudit,
    WorkflowAuditDetail,
    WorkflowAuditSetting,
    WorkflowLog,
    ResourceGroup,
    SqlWorkflow,
    QueryPrivilegesApply,
    Users,
    ArchiveConfig,
)
from common.config import SysConfig


class AuditException(Exception):
    pass


@dataclass
class AuditSetting:
    audit_auth_groups: List[str] = field(default_factory=list)
    auto_pass: bool = False

    @property
    def audit_auth_group_in_db(self):
        return ",".join(self.audit_auth_groups)


# 列出审核工单中不同状态的合法操作
SUPPORTED_OPERATION_GRID = {
    WorkflowStatus.WAITING.value: [
        WorkflowAction.PASS,
        WorkflowAction.REJECT,
        WorkflowAction.ABORT,
    ],
    WorkflowStatus.PASSED.value: [
        WorkflowAction.ABORT,
        WorkflowAction.EXECUTE_SET_TIME,
        WorkflowAction.EXECUTE_START,
        WorkflowAction.EXECUTE_END,
    ],
    WorkflowStatus.REJECTED.value: [],
    WorkflowStatus.ABORTED.value: [],
}


@dataclass
class AuditV2:
    # workflow 对象有可能是还没有在数据库中创建的对象, 这里需要注意
    workflow: Union[SqlWorkflow, ArchiveConfig, QueryPrivilegesApply]
    sys_config: SysConfig = field(default_factory=SysConfig)
    audit: WorkflowAudit = None
    workflow_type: WorkflowType = WorkflowType.SQL_REVIEW
    workflow_pk_field: str = "id"
    # 归档表中没有下面两个参数, 所以对归档表来说一下两参数必传
    resource_group: str = ""
    resource_group_id: int = 0

    def __post_init__(self):
        if isinstance(self.workflow, SqlWorkflow):
            self.workflow_type = WorkflowType.SQL_REVIEW
            self.workflow_pk_field = "id"
        elif isinstance(self.workflow, ArchiveConfig):
            self.workflow_type = WorkflowType.ARCHIVE
            self.workflow_pk_field = "id"
            try:
                group_in_db = ResourceGroup.objects.get(group_name=self.resource_group)
                self.resource_group_id = group_in_db.group_id
            except ResourceGroup.DoesNotExist:
                raise AuditException(f"参数错误, 未发现资源组 {self.resource_group}")
        elif isinstance(self.workflow, QueryPrivilegesApply):
            self.workflow_type = WorkflowType.QUERY
            self.workflow_pk_field = "apply_id"

    def generate_audit_setting(self) -> AuditSetting:
        if self.workflow_type == WorkflowType.SQL_REVIEW:
            if self.sys_config.get("auto_review", False):
                # 判断是否无需审批
                if is_auto_review(self.workflow.id):
                    return AuditSetting(auto_pass=True, audit_auth_groups=["无需审批"])
        if self.workflow_type in [WorkflowType.SQL_REVIEW, WorkflowType.QUERY]:
            group_id = self.workflow.group_id

        else:
            # ArchiveConfig
            group_id = self.resource_group_id
        try:
            workflow_audit_setting = WorkflowAuditSetting.objects.get(
                workflow_type=self.workflow_type, group_id=group_id
            )
        except WorkflowAuditSetting.DoesNotExist:
            raise AuditException(f"审批类型 {self.workflow_type.label} 未配置审流")
        return AuditSetting(
            audit_auth_groups=workflow_audit_setting.audit_auth_groups.split(",")
        )

    def create_audit(self) -> WorkflowAuditDetail:
        """按照传进来的工作流创建审批流, 返回一个 message如果有任何错误, 会以 exception 的形式抛出, 其他情况都是正常进行"""
        # 检查是否已存在待审核数据
        workflow_info = self.get_audit_info()
        if workflow_info:
            raise AuditException("该工单当前状态为待审核，请勿重复提交")
        # 获取审批流程
        try:
            audit_setting = self.generate_audit_setting()
        except AuditException as e:
            raise e

        if self.workflow_type == WorkflowType.QUERY:
            workflow_title = self.workflow.title
            group_id = self.workflow.group_id
            group_name = self.workflow.group_name
            create_user = self.workflow.user_name
            create_user_display = self.workflow.user_display
            self.workflow.audit_auth_groups = audit_setting.audit_auth_group_in_db
        elif self.workflow_type == WorkflowType.SQL_REVIEW:
            workflow_title = self.workflow.workflow_name
            group_id = self.workflow.group_id
            group_name = self.workflow.group_name
            create_user = self.workflow.engineer
            create_user_display = self.workflow.engineer_display
            self.workflow.audit_auth_groups = audit_setting.audit_auth_group_in_db
        elif self.workflow_type == WorkflowType.ARCHIVE:
            workflow_title = self.workflow.title
            group_id = self.resource_group_id
            group_name = self.resource_group
            create_user = self.workflow.user_name
            create_user_display = self.workflow.user_display
            self.workflow.audit_auth_groups = audit_setting.audit_auth_group_in_db
        else:
            raise AuditException(f"不支持的审核类型: {self.workflow_type.label}")
        self.workflow.save()
        self.audit = WorkflowAudit(
            group_id=group_id,
            group_name=group_name,
            workflow_id=self.workflow.__getattribute__(self.workflow_pk_field),
            workflow_type=self.workflow_type,
            workflow_title=workflow_title,
            audit_auth_groups=audit_setting.audit_auth_group_in_db,
            current_audit="-1",
            next_audit="-1",
            create_user=create_user,
            create_user_display=create_user_display,
        )
        # 自动通过的情况
        if audit_setting.auto_pass and self.workflow_type == WorkflowType.SQL_REVIEW:
            self.audit.current_status = WorkflowStatus.PASSED
            self.audit.save()
            WorkflowLog.objects.create(
                audit_id=self.audit.audit_id,
                operation_type=WorkflowAction.SUBMIT,
                operation_type_desc=WorkflowAction.SUBMIT.label,
                operation_info="无需审批，系统直接审核通过",
                operator=self.audit.create_user,
                operator_display=self.audit.create_user_display,
            )
            self.workflow.status = "workflow_review_pass"
            self.workflow.save()

            return "无需审批, 直接审核通过"

        # 向审核主表插入待审核数据
        self.audit.current_audit = audit_setting.audit_auth_groups[0]
        # 判断有无下级审核
        if len(audit_setting.audit_auth_groups) == 1:
            self.audit.next_audit = "-1"
        else:
            self.audit.next_audit = audit_setting.audit_auth_groups[1]

        self.audit.current_status = WorkflowStatus.WAITING
        self.audit.create_user = create_user
        self.audit.create_user_display = create_user_display
        self.audit.save()
        audit_log = WorkflowLog(
            audit_id=self.audit.audit_id,
            operation_type=WorkflowAction.SUBMIT,
            operation_type_desc=WorkflowAction.SUBMIT.label,
            operation_info="等待审批，审批流程：{}".format(self.audit.audit_auth_groups),
            operator=self.audit.create_user,
            operator_display=self.audit.create_user_display,
        )
        audit_log.save()
        return "工单已正常提交"

    def operate(
        self, action: WorkflowAction, actor: Users, remark: str
    ) -> WorkflowAuditDetail:
        """操作已提交的工单"""
        if not self.audit:
            self.get_audit_info()

        allowed_actions = SUPPORTED_OPERATION_GRID.get(self.audit.current_status)
        if not allowed_actions:
            raise AuditException(
                f"不允许的操作, 工单当前状态为 {self.audit.current_status}, 不允许做任何操作"
            )
        if action not in allowed_actions:
            raise AuditException(
                f"不允许的操作, 工单当前状态为 {self.audit.current_status}, 允许的操作为{','.join(x.label for x in allowed_actions)}"
            )

        if action == WorkflowAction.PASS:
            return self.operate_pass(actor, remark)
        if action == WorkflowAction.REJECT:
            return self.operate_reject(actor, remark)
        if action == WorkflowAction.ABORT:
            return self.operate_abort(actor, remark)

    def get_audit_info(self) -> Optional[WorkflowAudit]:
        """尝试根据 workflow 取出审批工作流"""
        if self.audit:
            return self.audit
        try:
            self.audit = WorkflowAudit.objects.get(
                workflow_type=self.workflow_type,
                workflow_id=getattr(self.workflow, self.workflow_pk_field),
            )
            return self.audit
        except ObjectDoesNotExist:
            return None

    def operate_pass(self, actor: Users, remark: str) -> WorkflowAuditDetail:
        # 判断是否还有下一级审核
        if self.audit.next_audit == "-1":
            # 无下一级, 更新主表审核状态为审核通过
            self.audit.current_audit = "-1"
            self.audit.current_status = WorkflowStatus.PASSED
            self.audit.save()
        else:
            # 更新主表审核下级审核组和当前审核组
            self.audit.current_status = WorkflowStatus.WAITING
            self.audit.current_audit = self.audit.next_audit
            # 判断后续是否还有下下一级审核组
            audit_auth_groups_list = self.audit.audit_auth_groups.split(",")
            for index, auth_group in enumerate(audit_auth_groups_list):
                if auth_group == self.audit.next_audit:
                    # 无下下级审核组
                    if index == len(audit_auth_groups_list) - 1:
                        self.audit.next_audit = "-1"
                    # 存在下下级审核组
                    else:
                        self.audit.next_audit = audit_auth_groups_list[index + 1]
                    break
            self.audit.save()

        # 插入审核明细数据
        audit_detail_result = WorkflowAuditDetail.objects.create(
            audit_id=self.audit.audit_id,
            audit_user=actor.username,
            audit_status=WorkflowStatus.PASSED,
            audit_time=timezone.now(),
            remark=remark,
        )

        # 增加工单日志
        WorkflowLog.objects.create(
            audit_id=self.audit.audit_id,
            operation_type=WorkflowAction.PASS,
            operation_type_desc=WorkflowAction.PASS.label,
            operation_info="审批备注：{}，下级审批：{}".format(remark, self.audit.current_audit),
            operator=actor.username,
            operator_display=actor.display,
        )
        return audit_detail_result

    def operate_reject(self, actor: Users, remark: str) -> WorkflowAuditDetail:
        # 更新主表审核状态
        self.audit.current_audit = "-1"
        self.audit.next_audit = "-1"
        self.audit.current_status = WorkflowStatus.REJECTED
        self.audit.save()
        # 插入审核明细数据
        workflow_audit_detail = WorkflowAuditDetail.objects.create(
            audit_id=self.audit.audit_id,
            audit_user=actor.username,
            audit_status=WorkflowStatus.REJECTED,
            audit_time=timezone.now(),
            remark=remark,
        )
        # 增加工单日志
        WorkflowLog.objects.create(
            audit_id=self.audit.audit_id,
            operation_type=2,
            operation_type_desc="审批不通过",
            operation_info="审批备注：{}".format(remark),
            operator=actor.username,
            operator_display=actor.display,
        )

        return workflow_audit_detail

    def operate_abort(self, actor: Users, remark: str) -> WorkflowAuditDetail:
        # 更新主表审核状态

        self.audit.next_audit = "-1"
        self.audit.current_status = WorkflowStatus.ABORTED
        self.audit.save()

        # 插入审核明细数据
        workflow_audit_detail = WorkflowAuditDetail.objects.create(
            audit_id=self.audit.audit_id,
            audit_user=actor.username,
            audit_status=WorkflowStatus.ABORTED,
            audit_time=timezone.now(),
            remark=remark,
        )
        # 增加工单日志
        WorkflowLog.objects.create(
            audit_id=self.audit.audit_id,
            operation_type=3,
            operation_type_desc="审批取消",
            operation_info="取消原因：{}".format(remark),
            operator=actor.username,
            operator_display=actor.display,
        )
        return workflow_audit_detail


class Audit(object):
    """老版 Audit, 建议不再更新新内容, 转而使用 AuditV2"""

    # 新增工单审核
    @staticmethod
    def add(workflow_type, workflow_id):
        result = {"status": 0, "msg": "", "data": []}

        # 检查是否已存在待审核数据
        workflow_info = WorkflowAudit.objects.filter(
            workflow_type=workflow_type,
            workflow_id=workflow_id,
            current_status=WorkflowStatus.WAITING,
        )
        if len(workflow_info) >= 1:
            result["msg"] = "该工单当前状态为待审核，请勿重复提交"
            raise Exception(result["msg"])

        # 获取工单信息
        if workflow_type == WorkflowType.QUERY:
            workflow_detail = QueryPrivilegesApply.objects.get(apply_id=workflow_id)
            workflow_title = workflow_detail.title
            group_id = workflow_detail.group_id
            group_name = workflow_detail.group_name
            create_user = workflow_detail.user_name
            create_user_display = workflow_detail.user_display
            audit_auth_groups = workflow_detail.audit_auth_groups
            workflow_remark = ""
        elif workflow_type == WorkflowType.SQL_REVIEW:
            workflow_detail = SqlWorkflow.objects.get(pk=workflow_id)
            workflow_title = workflow_detail.workflow_name
            group_id = workflow_detail.group_id
            group_name = workflow_detail.group_name
            create_user = workflow_detail.engineer
            create_user_display = workflow_detail.engineer_display
            audit_auth_groups = workflow_detail.audit_auth_groups
            workflow_remark = ""
        elif workflow_type == WorkflowType.ARCHIVE:
            workflow_detail = ArchiveConfig.objects.get(pk=workflow_id)
            workflow_title = workflow_detail.title
            group_id = workflow_detail.resource_group.group_id
            group_name = workflow_detail.resource_group.group_name
            create_user = workflow_detail.user_name
            create_user_display = workflow_detail.user_display
            audit_auth_groups = workflow_detail.audit_auth_groups
            workflow_remark = ""
        else:
            result["msg"] = "工单类型不存在"
            raise Exception(result["msg"])

        # 校验是否配置审批流程
        if audit_auth_groups == "":
            result["msg"] = "审批流程不能为空，请先配置审批流程"
            raise Exception(result["msg"])
        else:
            audit_auth_groups_list = audit_auth_groups.split(",")

        # 判断是否无需审核,并且修改审批人为空
        if SysConfig().get("auto_review", False):
            if workflow_type == WorkflowType.SQL_REVIEW:
                if is_auto_review(workflow_id):
                    sql_workflow = SqlWorkflow.objects.get(id=int(workflow_id))
                    sql_workflow.audit_auth_groups = "无需审批"
                    sql_workflow.status = "workflow_review_pass"
                    sql_workflow.save()
                    audit_auth_groups_list = None

        # 无审核配置则无需审核，直接通过
        if audit_auth_groups_list is None:
            # 向审核主表插入审核通过的数据
            audit_detail = WorkflowAudit()
            audit_detail.group_id = group_id
            audit_detail.group_name = group_name
            audit_detail.workflow_id = workflow_id
            audit_detail.workflow_type = workflow_type
            audit_detail.workflow_title = workflow_title
            audit_detail.workflow_remark = workflow_remark
            audit_detail.audit_auth_groups = ""
            audit_detail.current_audit = "-1"
            audit_detail.next_audit = "-1"
            audit_detail.current_status = WorkflowStatus.PASSED  # 审核通过
            audit_detail.create_user = create_user
            audit_detail.create_user_display = create_user_display
            audit_detail.save()
            result["data"] = {"workflow_status": WorkflowStatus.PASSED}
            result["msg"] = "无审核配置，直接审核通过"
            # 增加工单日志
            Audit.add_log(
                audit_id=audit_detail.audit_id,
                operation_type=0,
                operation_type_desc="提交",
                operation_info="无需审批，系统直接审核通过",
                operator=audit_detail.create_user,
                operator_display=audit_detail.create_user_display,
            )
        else:
            # 向审核主表插入待审核数据
            audit_detail = WorkflowAudit()
            audit_detail.group_id = group_id
            audit_detail.group_name = group_name
            audit_detail.workflow_id = workflow_id
            audit_detail.workflow_type = workflow_type
            audit_detail.workflow_title = workflow_title
            audit_detail.workflow_remark = workflow_remark
            audit_detail.audit_auth_groups = ",".join(audit_auth_groups_list)
            audit_detail.current_audit = audit_auth_groups_list[0]
            # 判断有无下级审核
            if len(audit_auth_groups_list) == 1:
                audit_detail.next_audit = "-1"
            else:
                audit_detail.next_audit = audit_auth_groups_list[1]

            audit_detail.current_status = WorkflowStatus.WAITING
            audit_detail.create_user = create_user
            audit_detail.create_user_display = create_user_display
            audit_detail.save()
            result["data"] = {"workflow_status": WorkflowStatus.WAITING}
            # 增加工单日志
            audit_auth_group, current_audit_auth_group = Audit.review_info(
                workflow_id, workflow_type
            )
            Audit.add_log(
                audit_id=audit_detail.audit_id,
                operation_type=0,
                operation_type_desc="提交",
                operation_info="等待审批，审批流程：{}".format(audit_auth_group),
                operator=audit_detail.create_user,
                operator_display=audit_detail.create_user_display,
            )
        # 增加审核id
        result["data"]["audit_id"] = audit_detail.audit_id
        # 返回添加结果
        return result, audit_detail

    # 工单审核
    @staticmethod
    def audit(
        audit_id, audit_status, audit_user, audit_remark
    ) -> (dict, WorkflowAuditDetail):
        result = {"status": 0, "msg": "ok", "data": 0}
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)

        # 不同审核状态
        if audit_status == WorkflowStatus.PASSED:
            # 判断当前工单是否为待审核状态
            if audit_detail.current_status != WorkflowStatus.WAITING:
                result["msg"] = "工单不是待审核状态，请返回刷新"
                raise Exception(result["msg"])

            # 判断是否还有下一级审核
            if audit_detail.next_audit == "-1":
                # 更新主表审核状态为审核通过
                audit_result = WorkflowAudit()
                audit_result.audit_id = audit_id
                audit_result.current_audit = "-1"
                audit_result.current_status = WorkflowStatus.PASSED
                audit_result.save(update_fields=["current_audit", "current_status"])
            else:
                # 更新主表审核下级审核组和当前审核组
                audit_result = WorkflowAudit()
                audit_result.audit_id = audit_id
                audit_result.current_status = WorkflowStatus.WAITING
                audit_result.current_audit = audit_detail.next_audit
                # 判断后续是否还有下下一级审核组
                audit_auth_groups_list = audit_detail.audit_auth_groups.split(",")
                for index, auth_group in enumerate(audit_auth_groups_list):
                    if auth_group == audit_detail.next_audit:
                        # 无下下级审核组
                        if index == len(audit_auth_groups_list) - 1:
                            audit_result.next_audit = "-1"
                            break
                        # 存在下下级审核组
                        else:
                            audit_result.next_audit = audit_auth_groups_list[index + 1]
                audit_result.save(
                    update_fields=["current_audit", "next_audit", "current_status"]
                )

            # 插入审核明细数据
            audit_detail_result = WorkflowAuditDetail()
            audit_detail_result.audit_id = audit_id
            audit_detail_result.audit_user = audit_user
            audit_detail_result.audit_status = WorkflowStatus.PASSED
            audit_detail_result.audit_time = timezone.now()
            audit_detail_result.remark = audit_remark
            audit_detail_result.save()
            # 增加工单日志
            audit_auth_group, current_audit_auth_group = Audit.review_info(
                audit_detail.workflow_id, audit_detail.workflow_type
            )
            Audit.add_log(
                audit_id=audit_id,
                operation_type=1,
                operation_type_desc="审批通过",
                operation_info="审批备注：{}，下级审批：{}".format(
                    audit_remark, current_audit_auth_group
                ),
                operator=audit_user,
                operator_display=Users.objects.get(username=audit_user).display,
            )
        elif audit_status == WorkflowStatus.REJECTED:
            # 判断当前工单是否为待审核状态
            if audit_detail.current_status != WorkflowStatus.WAITING:
                result["msg"] = "工单不是待审核状态，请返回刷新"
                raise Exception(result["msg"])

            # 更新主表审核状态
            audit_result = WorkflowAudit()
            audit_result.audit_id = audit_id
            audit_result.current_audit = "-1"
            audit_result.next_audit = "-1"
            audit_result.current_status = WorkflowStatus.REJECTED
            audit_result.save(
                update_fields=["current_audit", "next_audit", "current_status"]
            )

            # 插入审核明细数据
            audit_detail_result = WorkflowAuditDetail()
            audit_detail_result.audit_id = audit_id
            audit_detail_result.audit_user = audit_user
            audit_detail_result.audit_status = WorkflowStatus.REJECTED
            audit_detail_result.audit_time = timezone.now()
            audit_detail_result.remark = audit_remark
            audit_detail_result.save()
            # 增加工单日志
            Audit.add_log(
                audit_id=audit_id,
                operation_type=2,
                operation_type_desc="审批不通过",
                operation_info="审批备注：{}".format(audit_remark),
                operator=audit_user,
                operator_display=Users.objects.get(username=audit_user).display,
            )
        elif audit_status == WorkflowStatus.ABORTED:
            # 判断当前工单是否为待审核/审核通过状态
            if (
                audit_detail.current_status != WorkflowStatus.WAITING
                and audit_detail.current_status != WorkflowStatus.PASSED
            ):
                result["msg"] = "工单不是待审核态/审核通过状态，请返回刷新"
                raise Exception(result["msg"])

            # 更新主表审核状态
            audit_result = WorkflowAudit()
            audit_result.audit_id = audit_id
            audit_result.next_audit = "-1"
            audit_result.current_status = WorkflowStatus.ABORTED
            audit_result.save(update_fields=["current_status", "next_audit"])

            # 插入审核明细数据
            audit_detail_result = WorkflowAuditDetail()
            audit_detail_result.audit_id = audit_id
            audit_detail_result.audit_user = audit_user
            audit_detail_result.audit_status = WorkflowStatus.ABORTED
            audit_detail_result.audit_time = timezone.now()
            audit_detail_result.remark = audit_remark
            audit_detail_result.save()

            # 增加工单日志
            Audit.add_log(
                audit_id=audit_id,
                operation_type=3,
                operation_type_desc="审批取消",
                operation_info="取消原因：{}".format(audit_remark),
                operator=audit_user,
                operator_display=Users.objects.get(username=audit_user).display,
            )
        else:
            result["msg"] = "审核异常"
            raise Exception(result["msg"])

        # 返回审核结果
        result["data"] = {"workflow_status": audit_result.current_status}
        return result, audit_detail_result

    # 获取用户待办工单数量
    @staticmethod
    def todo(user):
        # 先获取用户所在资源组列表
        group_list = user_groups(user)
        group_ids = [group.group_id for group in group_list]
        # 再获取用户所在权限组列表
        if user.is_superuser:
            auth_group_ids = [group.id for group in Group.objects.all()]
        else:
            auth_group_ids = [group.id for group in Group.objects.filter(user=user)]

        return WorkflowAudit.objects.filter(
            current_status=WorkflowStatus.WAITING,
            group_id__in=group_ids,
            current_audit__in=auth_group_ids,
        ).count()

    # 通过审核id获取审核信息
    @staticmethod
    def detail(audit_id):
        try:
            return WorkflowAudit.objects.get(audit_id=audit_id)
        except Exception:
            return None

    # 通过业务id获取审核信息
    @staticmethod
    def detail_by_workflow_id(workflow_id, workflow_type) -> WorkflowAudit:
        try:
            return WorkflowAudit.objects.get(
                workflow_id=workflow_id, workflow_type=workflow_type
            )
        except Exception:
            return None

    # 通过组和审核类型，获取审核配置信息
    @staticmethod
    def settings(group_id, workflow_type):
        try:
            return WorkflowAuditSetting.objects.get(
                workflow_type=workflow_type, group_id=group_id
            ).audit_auth_groups
        except Exception:
            return None

    # 修改\添加配置信息
    @staticmethod
    def change_settings(group_id, workflow_type, audit_auth_groups):
        try:
            WorkflowAuditSetting.objects.get(
                workflow_type=workflow_type, group_id=group_id
            )
            WorkflowAuditSetting.objects.filter(
                workflow_type=workflow_type, group_id=group_id
            ).update(audit_auth_groups=audit_auth_groups)
        except Exception:
            inset = WorkflowAuditSetting()
            inset.group_id = group_id
            inset.group_name = ResourceGroup.objects.get(group_id=group_id).group_name
            inset.audit_auth_groups = audit_auth_groups
            inset.workflow_type = workflow_type
            inset.save()

    # 判断用户当前是否是可审核
    @staticmethod
    def can_review(user, workflow_id, workflow_type):
        audit_info = WorkflowAudit.objects.get(
            workflow_id=workflow_id, workflow_type=workflow_type
        )
        group_id = audit_info.group_id
        result = False

        def get_workflow_applicant(workflow_id, workflow_type):
            user = ""
            if workflow_type == 1:
                workflow = QueryPrivilegesApply.objects.get(apply_id=workflow_id)
                user = workflow.user_name
            elif workflow_type == 2:
                workflow = SqlWorkflow.objects.get(id=workflow_id)
                user = workflow.engineer
            elif workflow_type == 3:
                workflow = ArchiveConfig.objects.get(id=workflow_id)
                user = workflow.user_name
            return user

        applicant = get_workflow_applicant(workflow_id, workflow_type)
        if (
            user.username == applicant
            and not user.is_superuser
            and SysConfig().get("ban_self_audit")
        ):
            return result
        # 只有待审核状态数据才可以审核
        if audit_info.current_status == WorkflowStatus.WAITING:
            try:
                auth_group_id = Audit.detail_by_workflow_id(
                    workflow_id, workflow_type
                ).current_audit
                audit_auth_group = Group.objects.get(id=auth_group_id).name
            except Exception:
                raise Exception("当前审批auth_group_id不存在，请检查并清洗历史数据")
            if (
                auth_group_users([audit_auth_group], group_id)
                .filter(id=user.id)
                .exists()
                or user.is_superuser == 1
            ):
                if workflow_type == 1:
                    if user.has_perm("sql.query_review"):
                        result = True
                elif workflow_type == 2:
                    if user.has_perm("sql.sql_review"):
                        result = True
                elif workflow_type == 3:
                    if user.has_perm("sql.archive_review"):
                        result = True
        return result

    # 获取当前工单审批流程和当前审核组
    @staticmethod
    def review_info(workflow_id, workflow_type):
        audit_info = WorkflowAudit.objects.get(
            workflow_id=workflow_id, workflow_type=workflow_type
        )
        if audit_info.audit_auth_groups == "":
            audit_auth_group = "无需审批"
        else:
            try:
                audit_auth_group = "->".join(
                    [
                        Group.objects.get(id=auth_group_id).name
                        for auth_group_id in audit_info.audit_auth_groups.split(",")
                    ]
                )
            except Exception:
                audit_auth_group = audit_info.audit_auth_groups
        if audit_info.current_audit == "-1":
            current_audit_auth_group = None
        else:
            try:
                current_audit_auth_group = Group.objects.get(
                    id=audit_info.current_audit
                ).name
            except Exception:
                current_audit_auth_group = audit_info.current_audit
        return audit_auth_group, current_audit_auth_group

    # 新增工单日志
    @staticmethod
    def add_log(
        audit_id,
        operation_type,
        operation_type_desc,
        operation_info,
        operator,
        operator_display,
    ):
        log = WorkflowLog(
            audit_id=audit_id,
            operation_type=operation_type,
            operation_type_desc=operation_type_desc,
            operation_info=operation_info,
            operator=operator,
            operator_display=operator_display,
        )
        log.save()
        return log

    # 获取工单日志
    @staticmethod
    def logs(audit_id):
        return WorkflowLog.objects.filter(audit_id=audit_id)


def get_auditor(
    # workflow 对象有可能是还没有在数据库中创建的对象, 这里需要注意
    workflow: Union[SqlWorkflow, ArchiveConfig, QueryPrivilegesApply],
    sys_config: SysConfig = field(default_factory=SysConfig),


    audit: WorkflowAudit = None,
    workflow_type: WorkflowType = WorkflowType.SQL_REVIEW,
    workflow_pk_field: str = "id",
    # 归档表中没有下面两个参数, 所以对归档表来说一下两参数必传
    resource_group: str = "",
    resource_group_id: int = 0,
) -> AuditV2:
    current_auditor = settings.CURRENT_AUDITOR
    module, o = current_auditor.split(":")
    auditor = getattr(importlib.import_module(module), o)
    return auditor(workflow=workflow,workflow_type=workflow_type,
                   workflow_pk_field=workflow_pk_field,
                   sys_config=sys_config,
                   audit=audit,
                   resource_group=resource_group, resource_group_id=resource_group_id)
