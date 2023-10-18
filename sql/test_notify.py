from datetime import datetime, timedelta

from django.contrib.auth.models import Group
from django.test import TestCase

from common.config import SysConfig
from sql.models import (
    Instance,
    SqlWorkflow,
    SqlWorkflowContent,
    QueryPrivilegesApply,
    WorkflowAudit,
    WorkflowAuditDetail,
    ResourceGroup,
)
from sql.notify import auto_notify, EventType, LegacyRender, GenericWebhookNotifier
from sql.tests import User


class TestNotify(TestCase):
    """
    测试消息
    """

    def setUp(self):
        self.sys_config = SysConfig()
        self.user = User.objects.create(
            username="test_user", display="中文显示", is_active=True
        )
        self.su = User.objects.create(
            username="s_user", display="中文显示", is_active=True, is_superuser=True
        )
        tomorrow = datetime.today() + timedelta(days=1)
        self.ins = Instance.objects.create(
            instance_name="some_ins",
            type="slave",
            db_type="mysql",
            host="some_host",
            port=3306,
            user="ins_user",
            password="some_str",
        )
        self.wf = SqlWorkflow.objects.create(
            workflow_name="some_name",
            group_id=1,
            group_name="g1",
            engineer=self.user.username,
            engineer_display=self.user.display,
            audit_auth_groups="some_audit_group",
            create_time=datetime.now(),
            status="workflow_timingtask",
            is_backup=True,
            instance=self.ins,
            db_name="some_db",
            syntax_type=1,
        )
        SqlWorkflowContent.objects.create(
            workflow=self.wf, sql_content="some_sql", execute_result=""
        )
        self.query_apply_1 = QueryPrivilegesApply.objects.create(
            group_id=1,
            group_name="some_name",
            title="some_title1",
            user_name="some_user",
            instance=self.ins,
            db_list="some_db,some_db2",
            limit_num=100,
            valid_date=tomorrow,
            priv_type=1,
            status=0,
            audit_auth_groups="some_audit_group",
        )
        # 必须要有的几个
        # WorkflowAudit, 审核表, 每一个工作流关联一条记录
        # WorkflowAuditDetail, 审核详情, 每一个审核步骤一条记录, 并且都关联到一个 WorkflowAudit
        self.audit_wf = WorkflowAudit.objects.create(
            group_id=1,
            group_name="some_group",
            workflow_id=self.wf.id,
            workflow_type=2,
            workflow_title="申请标题",
            workflow_remark="申请备注",
            audit_auth_groups="1,2,3",
            current_audit="1",
            next_audit="2",
            current_status=0,
        )
        self.audit_wf_detail = WorkflowAuditDetail.objects.create(
            audit_id=self.audit_wf.audit_id,
            audit_user=self.user.display,
            audit_time=datetime.now(),
            audit_status=1,
            remark="测试备注",
        )
        self.audit_query = WorkflowAudit.objects.create(
            group_id=1,
            group_name="some_group",
            workflow_id=self.query_apply_1.apply_id,
            workflow_type=1,
            workflow_title="申请标题",
            workflow_remark="申请备注",
            audit_auth_groups="1,2,3",
            current_audit="1",
            next_audit="2",
            current_status=0,
        )
        self.aug = Group.objects.create(id=1, name="auth_group")
        self.rs = ResourceGroup.objects.create(group_id=1, ding_webhook="url")

    def tearDown(self):
        self.sys_config.purge()
        User.objects.all().delete()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()
        WorkflowAudit.objects.all().delete()
        ResourceGroup.objects.all().delete()

    def test_empty_notifiers(self):
        with self.settings(ENABLED_NOTIFIERS=()):
            auto_notify(
                workflow=self.wf,
                event_type=EventType.EXECUTE,
                sys_config=self.sys_config,
            )

    # 测试该调用 auto_notify 的地方要调用

    # 下面的测试均为 notifier 的测试, 测试 render 和 send
    def test_legacy_render_execution(self):
        notifier = LegacyRender(
            workflow=self.wf, event_type=EventType.EXECUTE, sys_config=self.sys_config
        )
        notifier.render()
        self.assertEqual(len(notifier.messages), 1)
        self.assertIn("工单", notifier.messages[0].msg_title)
        with self.assertRaises(NotImplementedError):
            notifier.send()

    def test_legacy_render_audit(self):
        notifier = LegacyRender(
            workflow=self.wf,
            event_type=EventType.AUDIT,
            audit=self.audit_wf,
            audit_detail=self.audit_wf_detail,
            sys_config=self.sys_config,
        )
        notifier.render()
        self.assertEqual(len(notifier.messages), 1)

    def test_general_webhook(self):
        notifier = GenericWebhookNotifier(
            workflow=self.wf,
            event_type=EventType.AUDIT,
            audit=self.audit_wf,
            audit_detail=self.audit_wf_detail,
            sys_config=self.sys_config,
        )
        notifier.render()
        self.assertIsNotNone(notifier.request_data)
        self.assertDictEqual(
            notifier.request_data["audit"],
            {
                "audit_id": 3,
                "group_name": "some_group",
                "workflow_type": 2,
                "create_user_display": "",
                "workflow_title": "申请标题",
                "audit_auth_groups": "1,2,3",
                "current_audit": "1",
                "current_status": 0,
                "create_time": self.audit_wf.create_time.isoformat(),
            },
        )
        self.assertDictEqual(
            notifier.request_data["workflow"],
            {
                "id": 2,
                "workflow_name": "some_name",
                "demand_url": "",
                "group_id": 1,
                "group_name": "g1",
                "db_name": "some_db",
                "syntax_type": 1,
                "is_backup": True,
                "engineer": "test_user",
                "engineer_display": "中文显示",
                "status": "workflow_timingtask",
                "audit_auth_groups": "some_audit_group",
                "run_date_start": None,
                "run_date_end": None,
                "finish_time": None,
                "is_manual": 0,
                "instance": 2,
                "create_time": self.wf.create_time.isoformat(),
            },
        )
