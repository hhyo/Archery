import json
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, ANY

from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
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
    ArchiveConfig,
)
from sql.notify import (
    auto_notify,
    EventType,
    LegacyRender,
    GenericWebhookNotifier,
    My2SqlResult,
    DingdingWebhookNotifier,
    DingdingPersonNotifier,
    FeishuPersonNotifier,
    FeishuWebhookNotifier,
    QywxWebhookNotifier,
    LegacyMessage,
    Notifier,
    notify_for_execute,
    notify_for_audit,
    notify_for_my2sql,
    MailNotifier,
)

User = get_user_model()


class TestNotify(TestCase):
    """
    测试消息
    """

    def setUp(self):
        self.sys_config = SysConfig()
        self.aug = Group.objects.create(id=1, name="auth_group")
        self.user = User.objects.create(
            username="test_user", display="中文显示", is_active=True
        )
        self.su = User.objects.create(
            username="s_user",
            display="中文显示",
            is_active=True,
            is_superuser=True,
        )
        self.su.groups.add(self.aug)

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
            audit_auth_groups="1",
            current_audit="1",
            next_audit="2",
            current_status=0,
            create_user=self.user.username,
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
        self.audit_query_detail = WorkflowAuditDetail.objects.create(
            audit_id=self.audit_query.audit_id,
            audit_user=self.user.display,
            audit_time=datetime.now(),
            audit_status=1,
            remark="测试query备注",
        )

        self.rs = ResourceGroup.objects.create(group_id=1, ding_webhook="url")

        self.archive_apply = ArchiveConfig.objects.create(
            title="测试归档",
            resource_group=self.rs,
            src_instance=self.ins,
            src_db_name="foo",
            src_table_name="bar",
            dest_db_name="foo-dest",
            dest_table_name="bar-dest",
            mode="purge",
            no_delete=False,
            status=0,
            user_name=self.user.username,
            user_display=self.user.display,
        )
        self.archive_apply_audit = WorkflowAudit.objects.create(
            group_id=1,
            group_name="some_group",
            workflow_id=self.archive_apply.id,
            workflow_type=3,
            workflow_title=self.archive_apply.title,
            workflow_remark="申请备注",
            audit_auth_groups="1,2,3",
            current_audit="1",
            next_audit="2",
            current_status=0,
        )

    def tearDown(self):
        self.sys_config.purge()
        User.objects.all().delete()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()
        WorkflowAudit.objects.all().delete()
        WorkflowAuditDetail.objects.all().delete()
        ArchiveConfig.objects.all().delete()
        ResourceGroup.objects.all().delete()

    def test_empty_notifiers(self):
        with self.settings(ENABLED_NOTIFIERS=()):
            auto_notify(
                workflow=self.wf,
                event_type=EventType.EXECUTE,
                sys_config=self.sys_config,
            )

    def test_base_notifier(self):
        self.sys_config.set("foo", "bar")
        n = Notifier(workflow=self.wf, sys_config=self.sys_config)
        n.sys_config_key = "foo"
        self.assertTrue(n.should_run())
        n.sys_config_key = "not-foo"
        self.assertFalse(n.should_run())

    def test_no_workflow_and_audit(self):
        with self.assertRaises(ValueError):
            n = Notifier(workflow=None, audit=None)

    @patch("sql.notify.FeishuWebhookNotifier.run")
    def test_auto_notify(self, mock_run):
        with self.settings(ENABLED_NOTIFIERS=("sql.notify:FeishuWebhookNotifier",)):
            auto_notify(self.sys_config, event_type=EventType.EXECUTE, workflow=self.wf)
            mock_run.assert_called_once()

    @patch("sql.notify.auto_notify")
    def test_notify_for_execute(self, mock_auto_notify: Mock):
        """测试适配器"""
        notify_for_execute(self.wf)
        mock_auto_notify.assert_called_once_with(
            workflow=self.wf, sys_config=ANY, event_type=EventType.EXECUTE
        )

    @patch("sql.notify.auto_notify")
    def test_notify_for_audit(self, mock_auto_notify: Mock):
        """测试适配器"""
        notify_for_audit(
            workflow_audit=self.audit_wf, workflow_audit_detail=self.audit_wf_detail
        )
        mock_auto_notify.assert_called_once_with(
            workflow=None,
            event_type=EventType.AUDIT,
            sys_config=ANY,
            audit=self.audit_wf,
            audit_detail=self.audit_wf_detail,
        )

    @patch("sql.notify.auto_notify")
    def test_notify_for_m2sql(self, mock_auto_notify: Mock):
        """测试适配器"""
        task = Mock()
        task.success = True
        task.kwargs = {"user": "foo"}
        task.result = ["", "/foo"]
        expect_workflow = My2SqlResult(success=True, submitter="foo", file_path="/foo")
        notify_for_my2sql(task)
        mock_auto_notify.assert_called_once_with(
            workflow=expect_workflow, sys_config=ANY, event_type=EventType.M2SQL
        )
        mock_auto_notify.reset_mock()
        # 测试失败的情况
        task.success = False
        task.result = "Traceback blahblah"
        expect_workflow = My2SqlResult(
            success=False, submitter="foo", error=task.result
        )
        notify_for_my2sql(task)
        mock_auto_notify.assert_called_once_with(
            workflow=expect_workflow, sys_config=ANY, event_type=EventType.M2SQL
        )

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

    def test_legacy_render_execution_ddl(self):
        """DDL 比普通的工单多一个通知 dba"""
        self.wf.syntax_type = 1
        self.wf.status = "workflow_finish"
        self.wf.save()
        self.sys_config.set("ddl_notify_auth_group", self.aug.name)
        notifier = LegacyRender(
            workflow=self.wf, event_type=EventType.EXECUTE, sys_config=self.sys_config
        )
        notifier.render()
        self.assertEqual(len(notifier.messages), 2)
        self.assertIn("有新的DDL语句执行完成", notifier.messages[1].msg_title)

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
        self.assertIn("新的工单申请", notifier.messages[0].msg_title)
        # 测试一下不传 workflow
        notifier = LegacyRender(
            event_type=EventType.AUDIT,
            workflow=None,
            audit=self.audit_wf,
            audit_detail=self.audit_wf_detail,
            sys_config=self.sys_config,
        )
        notifier.render()
        self.assertEqual(len(notifier.messages), 1)
        self.assertIn("新的工单申请", notifier.messages[0].msg_title)

    def test_legacy_render_query_audit(self):
        # 默认是库权限的
        notifier = LegacyRender(
            workflow=self.query_apply_1,
            event_type=EventType.AUDIT,
            audit=self.audit_query,
            audit_detail=self.audit_query_detail,
            sys_config=self.sys_config,
        )
        notifier.render()
        self.assertEqual(len(notifier.messages), 1)
        self.assertIn("数据库清单", notifier.messages[0].msg_content)

        # 表级别的权限申请
        self.query_apply_1.priv_type = 2
        self.query_apply_1.table_list = "foo,bar"
        self.query_apply_1.save()
        notifier = LegacyRender(
            workflow=self.query_apply_1,
            event_type=EventType.AUDIT,
            audit=self.audit_query,
            audit_detail=self.audit_query_detail,
            sys_config=self.sys_config,
        )
        notifier.render()
        self.assertEqual(len(notifier.messages), 1)
        self.assertIn("表清单", notifier.messages[0].msg_content)
        self.assertIn("foo,bar", notifier.messages[0].msg_content)

    def test_legacy_render_archive_audit(self):
        notifier = LegacyRender(
            workflow=self.archive_apply,
            event_type=EventType.AUDIT,
            audit=self.archive_apply_audit,
            sys_config=self.sys_config,
        )
        notifier.render()
        self.assertEqual(len(notifier.messages), 1)
        self.assertIn("归档表", notifier.messages[0].msg_content)

    def test_legacy_render_audit_success(self):
        """审核通过消息"""
        # 只测试上线工单
        self.audit_wf.current_status = 1
        self.audit_wf.save()
        notifier = LegacyRender(
            workflow=self.wf,
            event_type=EventType.AUDIT,
            audit=self.audit_wf,
            sys_config=self.sys_config,
        )
        notifier.render()
        self.assertEqual(len(notifier.messages), 1)
        self.assertIn("工单审核通过", notifier.messages[0].msg_title)

    def test_legacy_render_audit_reject(self):
        self.audit_wf.current_status = 2
        self.audit_wf.save()
        self.audit_wf_detail.remark = "驳回foo-bar"
        self.audit_wf_detail.save()
        notifier = LegacyRender(
            workflow=self.wf,
            event_type=EventType.AUDIT,
            audit=self.audit_wf,
            audit_detail=self.audit_wf_detail,
            sys_config=self.sys_config,
        )
        notifier.render()
        self.assertEqual(len(notifier.messages), 1)
        self.assertIn("工单被驳回", notifier.messages[0].msg_title)
        self.assertIn("驳回foo-bar", notifier.messages[0].msg_content)

    def test_legacy_render_audit_abort(self):
        self.audit_wf.current_status = 3
        self.audit_wf.save()
        self.audit_wf_detail.remark = "撤回foo-bar"
        self.audit_wf_detail.save()
        notifier = LegacyRender(
            workflow=self.wf,
            event_type=EventType.AUDIT,
            audit=self.audit_wf,
            audit_detail=self.audit_wf_detail,
            sys_config=self.sys_config,
        )
        notifier.render()
        self.assertEqual(len(notifier.messages), 1)
        self.assertIn("提交人主动终止工单", notifier.messages[0].msg_title)
        self.assertIn("撤回foo-bar", notifier.messages[0].msg_content)

    def test_legacy_render_m2sql(self):
        successful_workflow = My2SqlResult(
            submitter=self.user.username, success=True, file_path="/foo/bar"
        )
        notifier = LegacyRender(
            workflow=successful_workflow,
            sys_config=self.sys_config,
            event_type=EventType.M2SQL,
        )
        notifier.render()
        self.assertEqual(len(notifier.messages), 1)
        self.assertEqual(notifier.messages[0].msg_title, "[Archery 通知]My2SQL执行结束")
        # 失败
        failed_workflow = My2SqlResult(
            submitter=self.user.username, success=False, error="Traceback blahblah"
        )
        notifier = LegacyRender(
            workflow=failed_workflow,
            sys_config=self.sys_config,
            event_type=EventType.M2SQL,
        )
        notifier.render()
        self.assertEqual(len(notifier.messages), 1)
        self.assertEqual(notifier.messages[0].msg_title, "[Archery 通知]My2SQL执行失败")

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
        print(json.dumps(notifier.request_data))
        self.assertDictEqual(
            notifier.request_data["audit"],
            {
                "audit_id": self.audit_wf.audit_id,
                "group_name": "some_group",
                "workflow_type": 2,
                "create_user_display": "",
                "workflow_title": "申请标题",
                "audit_auth_groups": self.audit_wf.audit_auth_groups,
                "current_audit": "1",
                "current_status": 0,
                "create_time": self.audit_wf.create_time.isoformat(),
            },
        )
        self.assertDictEqual(
            notifier.request_data["workflow_content"]["workflow"],
            {
                "id": self.wf.id,
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
                "instance": self.ins.id,
                "create_time": self.wf.create_time.isoformat(),
            },
        )
        self.assertEqual(
            notifier.request_data["workflow_content"]["sql_content"], "some_sql"
        )
        self.assertEqual(
            notifier.request_data["instance"]["instance_name"], self.ins.instance_name
        )


class TestNotifySend(TestCase):
    audit_wf: WorkflowAudit = None
    rs: ResourceGroup = None
    user: User = None

    @classmethod
    def setUpClass(cls):
        cls.user = User.objects.create(
            username="test",
            email="test@example.com",
            ding_user_id="1234",
            wx_user_id="1234",
            feishu_open_id="1234",
        )
        cls.rs = ResourceGroup.objects.create(
            group_name="test",
            ding_webhook="ding_url",
            feishu_webhook="feishu_url",
            qywx_webhook="qywx_url",
        )
        cls.audit_wf = WorkflowAudit.objects.create(
            group_id=cls.rs.group_id,
            group_name="some_group",
            workflow_id=1,
            workflow_type=2,
            workflow_title="申请标题",
            workflow_remark="申请备注",
            audit_auth_groups="1",
            current_audit="1",
            next_audit="2",
            current_status=0,
            create_user=cls.user.username,
        )

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.rs.delete()
        cls.audit_wf.delete()

    def setUp(self):
        self.patcher = patch("sql.notify.MsgSender")
        self.mock_msg_sender = self.patcher.start()
        self.get_workflow_patcher = patch("sql.models.WorkflowAudit.get_workflow")
        self.mock_get_workflow = self.get_workflow_patcher.start()
        self.sys_config = SysConfig()

    def tearDown(self):
        self.patcher.stop()
        self.get_workflow_patcher.stop()

    def generate_notifier(self, module) -> Notifier:
        return module(workflow=None, audit=self.audit_wf, sys_config=self.sys_config)

    def test_ding_webhook_send(self):
        mocker = Mock()
        setattr(self.mock_msg_sender.return_value, "send_ding", mocker)
        notifier = self.generate_notifier(DingdingWebhookNotifier)
        notifier.messages = [
            LegacyMessage(msg_to=[self.user], msg_title="test", msg_content="test")
        ]
        notifier.send()
        mocker.assert_called_once()

    def test_ding_person_send(self):
        mocker = Mock()
        setattr(self.mock_msg_sender.return_value, "send_ding2user", mocker)
        notifier = self.generate_notifier(DingdingPersonNotifier)
        notifier.messages = [
            LegacyMessage(msg_to=[self.user], msg_title="test", msg_content="test")
        ]
        notifier.send()
        mocker.assert_called_once()

    def test_feishu_webhook(self):
        mocker = Mock()
        setattr(self.mock_msg_sender.return_value, "send_feishu_webhook", mocker)
        notifier = self.generate_notifier(FeishuWebhookNotifier)
        notifier.messages = [
            LegacyMessage(msg_to=[self.user], msg_title="test", msg_content="test")
        ]
        notifier.send()
        mocker.assert_called_once()

    def test_feishu_person(self):
        mocker = Mock()
        setattr(self.mock_msg_sender.return_value, "send_feishu_user", mocker)
        notifier = self.generate_notifier(FeishuPersonNotifier)
        notifier.messages = [
            LegacyMessage(msg_to=[self.user], msg_title="test", msg_content="test")
        ]
        notifier.send()
        mocker.assert_called_once()

    def test_qywx_webhook(self):
        mocker = Mock()
        setattr(self.mock_msg_sender.return_value, "send_qywx_webhook", mocker)
        notifier = self.generate_notifier(QywxWebhookNotifier)
        notifier.messages = [
            LegacyMessage(msg_to=[self.user], msg_title="test", msg_content="test")
        ]
        notifier.send()
        mocker.assert_called_once()

    def test_mail(self):
        mocker = Mock()
        setattr(self.mock_msg_sender.return_value, "send_email", mocker)
        notifier = self.generate_notifier(MailNotifier)
        notifier.messages = [
            LegacyMessage(msg_to=[self.user], msg_title="test", msg_content="test")
        ]
        notifier.send()
        mocker.assert_called_once()


def test_override_sys_key():
    """dataclass 的继承有时候让人有点困惑, 在这里补一个测试确认可以正常覆盖一些值"""

    class OverrideNotifier(Notifier):
        sys_config_key = "test"

    n = OverrideNotifier(workflow=Mock())
    assert n.sys_config_key == "test"
