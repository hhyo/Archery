# -*- coding: UTF-8 -*-
import json
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from common.utils.const import WorkflowStatus
from sql.models import WorkflowAudit, WorkflowLog, ResourceGroup

User = get_user_model()


class TestWorkflow(TestCase):
    """测试工单流程功能"""

    def setUp(self):
        """初始化测试环境"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="test_user",
            password="test_password",
            display="测试用户",
            is_active=True,
        )
        self.superuser = User.objects.create_superuser(
            username="admin",
            password="admin_password",
            display="管理员",
            is_active=True,
        )
        
        # 创建资源组
        self.resource_group = ResourceGroup.objects.create(
            group_id=1,
            group_name="测试资源组",
        )
        
        # 创建权限组
        self.auth_group = Group.objects.create(name="审核组")
        self.user.groups.add(self.auth_group)

    def tearDown(self):
        """清理测试数据"""
        User.objects.all().delete()
        WorkflowAudit.objects.all().delete()
        WorkflowLog.objects.all().delete()
        ResourceGroup.objects.all().delete()
        Group.objects.all().delete()

    @patch("common.workflow.user_groups")
    def test_workflow_lists_success(self, mock_user_groups):
        """测试成功获取待审核工单列表"""
        # Mock user_groups
        mock_user_groups.return_value = ResourceGroup.objects.filter(
            group_id=self.resource_group.group_id
        )

        # 创建待审核工单
        WorkflowAudit.objects.create(
            group_id=self.resource_group.group_id,
            group_name=self.resource_group.group_name,
            workflow_id=1,
            workflow_type=1,
            workflow_title="测试SQL上线",
            create_user="test_user",
            create_user_display="测试用户",
            audit_auth_groups=str(self.auth_group.id),
            current_audit=str(self.auth_group.id),
            current_status=WorkflowStatus.WAITING,
        )
        WorkflowAudit.objects.create(
            group_id=self.resource_group.group_id,
            group_name=self.resource_group.group_name,
            workflow_id=2,
            workflow_type=2,
            workflow_title="测试查询权限申请",
            create_user="test_user",
            create_user_display="测试用户",
            audit_auth_groups=str(self.auth_group.id),
            current_audit=str(self.auth_group.id),
            current_status=WorkflowStatus.WAITING,
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("common:workflow_list"),
            {
                "limit": 10,
                "offset": 0,
                "workflow_type": 0,  # 所有类型
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["rows"]), 2)

    @patch("common.workflow.user_groups")
    def test_workflow_lists_filter_by_type(self, mock_user_groups):
        """测试按工单类型过滤"""
        # Mock user_groups
        mock_user_groups.return_value = ResourceGroup.objects.filter(
            group_id=self.resource_group.group_id
        )

        # 创建不同类型的工单
        WorkflowAudit.objects.create(
            group_id=self.resource_group.group_id,
            group_name=self.resource_group.group_name,
            workflow_id=1,
            workflow_type=1,  # SQL上线
            workflow_title="测试SQL上线",
            create_user="test_user",
            create_user_display="测试用户",
            audit_auth_groups=str(self.auth_group.id),
            current_audit=str(self.auth_group.id),
            current_status=WorkflowStatus.WAITING,
        )
        WorkflowAudit.objects.create(
            group_id=self.resource_group.group_id,
            group_name=self.resource_group.group_name,
            workflow_id=2,
            workflow_type=2,  # 查询权限申请
            workflow_title="测试查询权限申请",
            create_user="test_user",
            create_user_display="测试用户",
            audit_auth_groups=str(self.auth_group.id),
            current_audit=str(self.auth_group.id),
            current_status=WorkflowStatus.WAITING,
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("common:workflow_list"),
            {
                "limit": 10,
                "offset": 0,
                "workflow_type": 1,  # 只查询SQL上线
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["rows"][0]["workflow_type"], 1)

    @patch("common.workflow.user_groups")
    def test_workflow_lists_search(self, mock_user_groups):
        """测试搜索工单"""
        # Mock user_groups
        mock_user_groups.return_value = ResourceGroup.objects.filter(
            group_id=self.resource_group.group_id
        )

        # 创建工单
        WorkflowAudit.objects.create(
            group_id=self.resource_group.group_id,
            group_name=self.resource_group.group_name,
            workflow_id=1,
            workflow_type=1,
            workflow_title="生产环境SQL上线",
            create_user="test_user",
            create_user_display="测试用户",
            audit_auth_groups=str(self.auth_group.id),
            current_audit=str(self.auth_group.id),
            current_status=WorkflowStatus.WAITING,
        )
        WorkflowAudit.objects.create(
            group_id=self.resource_group.group_id,
            group_name=self.resource_group.group_name,
            workflow_id=2,
            workflow_type=1,
            workflow_title="测试环境SQL上线",
            create_user="test_user",
            create_user_display="测试用户",
            audit_auth_groups=str(self.auth_group.id),
            current_audit=str(self.auth_group.id),
            current_status=WorkflowStatus.WAITING,
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("common:workflow_list"),
            {
                "limit": 10,
                "offset": 0,
                "workflow_type": 0,
                "search": "生产环境",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)
        self.assertIn("生产环境", data["rows"][0]["workflow_title"])

    @patch("common.workflow.user_groups")
    def test_workflow_lists_only_waiting(self, mock_user_groups):
        """测试只显示待审核工单"""
        # Mock user_groups
        mock_user_groups.return_value = ResourceGroup.objects.filter(
            group_id=self.resource_group.group_id
        )

        # 创建不同状态的工单
        WorkflowAudit.objects.create(
            group_id=self.resource_group.group_id,
            group_name=self.resource_group.group_name,
            workflow_id=1,
            workflow_type=1,
            workflow_title="待审核工单",
            create_user="test_user",
            create_user_display="测试用户",
            audit_auth_groups=str(self.auth_group.id),
            current_audit=str(self.auth_group.id),
            current_status=WorkflowStatus.WAITING,
        )
        WorkflowAudit.objects.create(
            group_id=self.resource_group.group_id,
            group_name=self.resource_group.group_name,
            workflow_id=2,
            workflow_type=1,
            workflow_title="已通过工单",
            create_user="test_user",
            create_user_display="测试用户",
            audit_auth_groups=str(self.auth_group.id),
            current_audit=str(self.auth_group.id),
            current_status=WorkflowStatus.PASSED,
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("common:workflow_list"),
            {
                "limit": 10,
                "offset": 0,
                "workflow_type": 0,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        # 应该只返回待审核的工单
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["rows"][0]["current_status"], WorkflowStatus.WAITING)

    def test_workflow_log_success(self):
        """测试成功获取工单日志"""
        # 创建工单
        workflow = WorkflowAudit.objects.create(
            group_id=self.resource_group.group_id,
            group_name=self.resource_group.group_name,
            workflow_id=1,
            workflow_type=1,
            workflow_title="测试工单",
            create_user="test_user",
            create_user_display="测试用户",
            audit_auth_groups=str(self.auth_group.id),
            current_audit=str(self.auth_group.id),
            current_status=WorkflowStatus.WAITING,
        )

        # 创建工单日志
        WorkflowLog.objects.create(
            audit_id=workflow.audit_id,
            operation_type=1,
            operation_type_desc="提交",
            operation_info="提交工单",
            operator=self.user.username,
            operator_display=self.user.display,
        )
        WorkflowLog.objects.create(
            audit_id=workflow.audit_id,
            operation_type=2,
            operation_type_desc="审核",
            operation_info="审核通过",
            operator=self.user.username,
            operator_display=self.user.display,
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("common:workflow_log"),
            {
                "workflow_id": 1,
                "workflow_type": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["rows"]), 2)

    def test_workflow_log_not_found(self):
        """测试工单不存在时获取日志"""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("common:workflow_log"),
            {
                "workflow_id": 99999,
                "workflow_type": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 0)
        self.assertEqual(len(data["rows"]), 0)

    def test_workflow_log_order(self):
        """测试工单日志按时间倒序排列"""
        # 创建工单
        workflow = WorkflowAudit.objects.create(
            group_id=self.resource_group.group_id,
            group_name=self.resource_group.group_name,
            workflow_id=1,
            workflow_type=1,
            workflow_title="测试工单",
            create_user="test_user",
            create_user_display="测试用户",
            audit_auth_groups=str(self.auth_group.id),
            current_audit=str(self.auth_group.id),
            current_status=WorkflowStatus.WAITING,
        )

        # 创建多条日志
        for i in range(3):
            WorkflowLog.objects.create(
                audit_id=workflow.audit_id,
                operation_type=i + 1,
                operation_type_desc=f"操作{i + 1}",
                operation_info=f"操作信息{i + 1}",
                operator=self.user.username,
                operator_display=self.user.display,
            )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("common:workflow_log"),
            {
                "workflow_id": 1,
                "workflow_type": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        # 验证是否按时间倒序（最新的在前面）
        self.assertEqual(data["rows"][0]["operation_type_desc"], "操作3")
