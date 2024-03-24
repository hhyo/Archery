# -*- coding: UTF-8 -*-
import dataclasses
import importlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Union, Optional, List
import logging

from django.contrib.auth.models import Group
from django.utils import timezone
from django.conf import settings

from sql.engines.models import ReviewResult
from sql.utils.resource_group import user_groups, auth_group_users
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
from sql.utils.sql_utils import remove_comments

logger = logging.getLogger("default")


class AuditException(Exception):
    pass


class ReviewNodeType(Enum):
    GROUP = "group"
    AUTO_PASS = "auto_pass"


@dataclass
class ReviewNode:
    group: Optional[Group] = None
    node_type: ReviewNodeType = ReviewNodeType.GROUP
    is_current_node: bool = False
    is_passed_node: bool = False

    def __post_init__(self):
        if self.node_type == ReviewNodeType.GROUP and not self.group:
            raise ValueError(
                f"group not provided and node_type is set as {self.node_type}"
            )

    @property
    def is_auto_pass(self):
        return self.node_type == ReviewNodeType.AUTO_PASS


@dataclass
class ReviewInfo:
    nodes: List[ReviewNode] = field(default_factory=list)
    current_node_index: int = None

    @property
    def readable_info(self) -> str:
        """生成可读的工作流, 形如 g1(passed) -> g2(current) -> g3
        一般用途是渲染消息
        """
        steps = []
        for index, n in enumerate(self.nodes):
            if n.is_current_node:
                self.current_node_index = index
                steps.append(f"{n.group.name}(current)")
                continue
            if n.is_passed_node:
                steps.append(f"{n.group.name}(passed)")
                continue
            steps.append(n.group.name)
        return " -> ".join(steps)

    @property
    def current_node(self) -> ReviewNode:
        if self.current_node_index:
            return self.nodes[self.current_node_index]
        for index, n in enumerate(self.nodes):
            if n.is_current_node:
                self.current_node_index = n
                return n


@dataclass
class AuditSetting:
    """
    audit_auth_groups 为 django 组的 id
    """

    audit_auth_groups: List = field(default_factory=list)
    auto_pass: bool = False

    @property
    def audit_auth_group_in_db(self):
        return ",".join(str(x) for x in self.audit_auth_groups)


# 列出审核工单中不同状态的合法操作
SUPPORTED_OPERATION_GRID = {
    WorkflowStatus.WAITING.value: [
        WorkflowAction.PASS,
        WorkflowAction.REJECT,
        WorkflowAction.ABORT,
    ],
    WorkflowStatus.PASSED.value: [
        WorkflowAction.REJECT,
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
    workflow: Union[SqlWorkflow, ArchiveConfig, QueryPrivilegesApply] = None
    sys_config: SysConfig = field(default_factory=SysConfig)
    audit: WorkflowAudit = None
    workflow_type: WorkflowType = WorkflowType.SQL_REVIEW
    # 归档表中没有下面两个参数, 所以对归档表来说一下两参数必传
    resource_group: str = ""
    resource_group_id: int = 0

    def __post_init__(self):
        if not self.workflow:
            if not self.audit:
                raise ValueError("需要提供 WorkflowAudit 或 workflow")
            self.get_workflow()
        self.workflow_type = self.workflow.workflow_type
        if isinstance(self.workflow, SqlWorkflow):
            self.resource_group = self.workflow.group_name
            self.resource_group_id = self.workflow.group_id
        elif isinstance(self.workflow, ArchiveConfig):
            try:
                group_in_db = ResourceGroup.objects.get(group_name=self.resource_group)
                self.resource_group_id = group_in_db.group_id
            except ResourceGroup.DoesNotExist:
                raise AuditException(f"参数错误, 未发现资源组 {self.resource_group}")
        elif isinstance(self.workflow, QueryPrivilegesApply):
            self.resource_group = self.workflow.group_name
            self.resource_group_id = self.workflow.group_id
        # 该方法可能获取不到相关的审批流, 但是也不要报错, 因为有的时候是新建工单, 此时还没有审批流
        self.get_audit_info()
        # 防止 get_auditor 显式的传了个 None
        if not self.sys_config:
            self.sys_config = SysConfig()

    @property
    def review_info(self) -> (str, str):
        """获取可读的审批流信息, 包含整体的审批流和当前节点信息"""
        if self.audit.audit_auth_groups == "":
            audit_auth_group = "无需审批"
        else:
            try:
                audit_auth_group = "->".join(
                    [
                        Group.objects.get(id=auth_group_id).name
                        for auth_group_id in self.audit.audit_auth_groups.split(",")
                    ]
                )
            except Group.DoesNotExist:
                audit_auth_group = self.audit.audit_auth_groups
        if self.audit.current_audit == "-1":
            current_audit_auth_group = None
        else:
            try:
                current_audit_auth_group = Group.objects.get(
                    id=self.audit.current_audit
                ).name
            except Group.DoesNotExist:
                current_audit_auth_group = self.audit.current_audit
        return audit_auth_group, current_audit_auth_group

    def get_workflow(self):
        """尝试从 audit 中取出 workflow"""
        self.workflow = self.audit.get_workflow()
        if self.audit.workflow_type == WorkflowType.ARCHIVE:
            self.resource_group = self.audit.group_name
            self.resource_group_id = self.audit.group_id

    def is_auto_review(self) -> bool:
        if self.workflow_type != WorkflowType.SQL_REVIEW:
            # 当前自动审核仅对 sql 上线工单有用
            return False
        auto_review_enabled = self.sys_config.get("auto_review", False)
        if not auto_review_enabled:
            return False
        auto_review_tags = self.sys_config.get("auto_review_tag", "").split(",")
        auto_review_db_type = self.sys_config.get("auto_review_db_type", "").split(",")
        # TODO 这里也可以放到engine中实现，但是配置项可能会相对复杂
        if self.workflow.instance.db_type not in auto_review_db_type:
            return False
        if not self.workflow.instance.instance_tag.filter(
            tag_code__in=auto_review_tags
        ).exists():
            return False

        # 获取正则表达式
        auto_review_regex = self.sys_config.get(
            "auto_review_regex", "^alter|^create|^drop|^truncate|^rename|^delete"
        )
        p = re.compile(auto_review_regex, re.I)

        # 判断是否匹配到需要手动审核的语句
        all_affected_rows = 0
        review_content = self.workflow.sqlworkflowcontent.review_content
        for review_row in json.loads(review_content):
            review_result = ReviewResult(**review_row)
            # 去除SQL注释 https://github.com/hhyo/Archery/issues/949
            sql = remove_comments(review_result.sql).replace("\n", "").replace("\r", "")
            # 正则匹配
            if p.match(sql):
                # 匹配成功, 代表需要人工复核
                return False
            # 影响行数加测, 总语句影响行数超过指定数量则需要人工审核
            all_affected_rows += int(review_result.affected_rows)
        if all_affected_rows > int(
            self.sys_config.get("auto_review_max_update_rows", 50)
        ):
            # 影响行数超规模, 需要人工审核
            return False
        return True

    def generate_audit_setting(self) -> AuditSetting:
        if self.is_auto_review():
            return AuditSetting(auto_pass=True)
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

    def create_audit(self) -> str:
        """按照传进来的工作流创建审批流, 返回一个 message如果有任何错误, 会以 exception 的形式抛出, 其他情况都是正常进行"""
        # 检查是否已存在待审核数据
        workflow_info = self.get_audit_info()
        if workflow_info:
            raise AuditException("该工单当前状态为待审核，请勿重复提交")
        # 获取审批流程
        audit_setting = self.generate_audit_setting()

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
            workflow_id=self.workflow.pk,
            workflow_type=self.workflow_type,
            workflow_title=workflow_title,
            audit_auth_groups=audit_setting.audit_auth_group_in_db,
            current_audit="-1",
            next_audit="-1",
            create_user=create_user,
            create_user_display=create_user_display,
        )
        # 自动通过的情况
        if audit_setting.auto_pass:
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
        readable_review_flow, _ = self.review_info
        audit_log = WorkflowLog(
            audit_id=self.audit.audit_id,
            operation_type=WorkflowAction.SUBMIT,
            operation_type_desc=WorkflowAction.SUBMIT.label,
            operation_info="等待审批，审批流程：{}".format(readable_review_flow),
            operator=self.audit.create_user,
            operator_display=self.audit.create_user_display,
        )
        audit_log.save()
        return "工单已正常提交"

    def can_operate(self, action: WorkflowAction, actor: Users):
        """检查用户是否有权限做相关操作, 如有权限问题, raise AuditException, 无问题返回 True"""
        # 首先检查工单状态和相关操作是否匹配, 如已通过的工单不能再通过
        allowed_actions = SUPPORTED_OPERATION_GRID.get(self.audit.current_status)
        if not allowed_actions:
            raise AuditException(
                f"不允许的操作, 工单当前状态为 {self.audit.current_status}, 不允许做任何操作"
            )
        if action not in allowed_actions:
            raise AuditException(
                f"不允许的操作, 工单当前状态为 {self.audit.current_status}, 允许的操作为{','.join(x.label for x in allowed_actions)}"
            )
        if self.workflow_type == WorkflowType.QUERY:
            need_user_permission = "sql.query_review"
        elif self.workflow_type == WorkflowType.SQL_REVIEW:
            need_user_permission = "sql.sql_review"
        elif self.workflow_type == WorkflowType.ARCHIVE:
            need_user_permission = "sql.archive_review"
        else:
            raise AuditException(f"不支持的工单类型: {self.workflow_type}")

        if action == WorkflowAction.ABORT:
            if actor.username != self.audit.create_user:
                raise AuditException(f"只有工单提交者可以撤回工单")
            return True
        if action in [WorkflowAction.PASS, WorkflowAction.REJECT]:
            # 需要检查权限
            # 超级用户可以审批所有工单
            if actor.is_superuser:
                return True
            # 看是否本人审核
            if actor.username == self.audit.create_user and self.sys_config.get(
                "ban_self_audit"
            ):
                raise AuditException("当前配置禁止本人审核自己的工单")
            # 确认用户权限
            if not actor.has_perm(need_user_permission):
                raise AuditException("用户无相关审批权限, 请合理配置权限")

            # 确认权限, 是否在当前审核组内
            try:
                audit_auth_group = Group.objects.get(id=self.audit.current_audit)
            except Group.DoesNotExist:
                raise AuditException(
                    "当前审批权限组不存在, 请联系管理员检查并清洗错误数据"
                )
            if not auth_group_users([audit_auth_group.name], self.resource_group_id):
                raise AuditException("用户不在当前审批审批节点的用户组内, 无权限审核")
            return True
        if action in [
            WorkflowAction.EXECUTE_START,
            WorkflowAction.EXECUTE_END,
            WorkflowAction.EXECUTE_SET_TIME,
        ]:
            # 一般是系统自动流转, 自动通过
            return True

        raise AuditException(f"不支持的操作, 无法判断权限")

    def operate(
        self, action: WorkflowAction, actor: Users, remark: str
    ) -> WorkflowAuditDetail:
        """操作已提交的工单"""
        if not self.audit:
            raise AuditException(f"给定工单未绑定审批信息, 无法进行操作")
        self.can_operate(action, actor)

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
        self.audit = self.workflow.get_audit()
        return self.audit

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
            try:
                position = audit_auth_groups_list.index(str(self.audit.current_audit))
            except ValueError as e:
                logger.error(
                    f"审批流配置错误, 审批节点{self.audit.current_audit} 不在审批流内: 审核ID {self.audit.audit_id}"
                )
                raise e
            if position + 1 >= len(audit_auth_groups_list):
                # 最后一个节点
                self.audit.next_audit = "-1"
            else:
                self.audit.next_audit = audit_auth_groups_list[position + 1]
            self.audit.save()

        # 插入审核明细数据
        audit_detail_result = WorkflowAuditDetail.objects.create(
            audit_id=self.audit.audit_id,
            audit_user=actor.username,
            audit_status=WorkflowStatus.PASSED,
            audit_time=timezone.now(),
            remark=remark,
        )

        if self.audit.current_audit == "-1":
            operation_info = f"审批备注: {remark}, 无下级审批"
        else:
            operation_info = f"审批备注：{remark}, 下级审批：{self.audit.current_audit}"

        # 增加工单日志
        WorkflowLog.objects.create(
            audit_id=self.audit.audit_id,
            operation_type=WorkflowAction.PASS,
            operation_type_desc=WorkflowAction.PASS.label,
            operation_info=operation_info,
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

    def get_review_info(self) -> ReviewInfo:
        """提供审批流各节点的状态
        如果总体是待审核状态, 当前节点之前为已通过, 当前节点为当前节点, 未通过, 当前节点之后为未通过
        如果总体为其他状态, 节点的属性都不设置, 均为默认值
        """
        self.get_audit_info()
        review_nodes = []
        has_met_current_node = False
        current_node_group_id = int(self.audit.current_audit)
        for g in self.audit.audit_auth_groups.split(","):
            if not g:
                # 空的值, 代表的是自动通过
                review_nodes.append(
                    ReviewNode(
                        node_type=ReviewNodeType.AUTO_PASS,
                        is_passed_node=True,
                    )
                )
                continue
            try:
                g = int(g)
            except ValueError:  # pragma: no cover
                # 脏数据, 当成自动通过
                # 兼容代码, 一般是空值代表自动通过
                review_nodes.append(
                    ReviewNode(
                        node_type=ReviewNodeType.AUTO_PASS,
                        is_passed_node=True,
                    )
                )
                continue
            try:
                group_in_db = Group.objects.get(id=g)
            except Group.DoesNotExist:
                raise AuditException(f"参数错误, 未发现资源组 {self.resource_group}")
            if self.audit.current_status != WorkflowStatus.WAITING:
                # 总体状态不是待审核, 不设置详细的属性
                review_nodes.append(
                    ReviewNode(
                        group=group_in_db,
                    )
                )
                continue
            if current_node_group_id == g:
                # 当前节点, 一定为未通过
                has_met_current_node = True
                review_nodes.append(
                    ReviewNode(
                        group=group_in_db,
                        is_current_node=True,
                        is_passed_node=False,
                    )
                )
                continue
            if has_met_current_node:
                # 当前节点之后的节点, 一定为未通过
                review_nodes.append(
                    ReviewNode(
                        group=group_in_db,
                        is_passed_node=False,
                    )
                )
                continue
            # 以上情况之外的情况, 一定为已经通过的节点
            review_nodes.append(
                ReviewNode(
                    group=group_in_db,
                    is_passed_node=True,
                )
            )
        return ReviewInfo(nodes=review_nodes)


class Audit(object):
    """老版 Audit, 建议不再更新新内容, 转而使用 AuditV2"""

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
                user.is_superuser
                or auth_group_users([audit_auth_group], group_id)
                .filter(id=user.id)
                .exists()
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
    workflow: Union[SqlWorkflow, ArchiveConfig, QueryPrivilegesApply] = None,
    sys_config: SysConfig = None,
    audit: WorkflowAudit = None,
    workflow_type: WorkflowType = WorkflowType.SQL_REVIEW,
    # 归档表中没有下面两个参数, 所以对归档表来说一下两参数必传
    resource_group: str = "",
    resource_group_id: int = 0,
) -> AuditV2:
    current_auditor = settings.CURRENT_AUDITOR
    module, o = current_auditor.split(":")
    auditor = getattr(importlib.import_module(module), o)
    return auditor(
        workflow=workflow,
        workflow_type=workflow_type,
        sys_config=sys_config,
        audit=audit,
        resource_group=resource_group,
        resource_group_id=resource_group_id,
    )
