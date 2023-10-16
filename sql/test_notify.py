from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import TestCase

from common.config import SysConfig
from common.utils.const import WorkflowDict
from sql.models import Instance, SqlWorkflow, SqlWorkflowContent, QueryPrivilegesApply, WorkflowAudit, ResourceGroup
from sql.notify import notify_for_audit, notify_for_my2sql, auto_notify, EventType
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
        self.audit = WorkflowAudit.objects.create(
            group_id=1,
            group_name="some_group",
            workflow_id=1,
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
            auto_notify(workflow=self.wf, event_type=EventType.EXECUTE, sys_config=self.sys_config)

    def test_notify_disable(self):
        """
        测试关闭通知
        :return:
        """
        # 关闭消息通知
        self.sys_config.set("mail", "false")
        self.sys_config.set("ding", "false")
        r = notify_for_audit(audit_id=self.audit.audit_id)
        self.assertIsNone(r)

    @patch("sql.notify.MsgSender")
    @patch("sql.notify.auth_group_users")
    def test_notify_for_sqlreview_audit_wait(self, _auth_group_users, _msg_sender):
        """
        测试SQL上线申请审核通知
        :return:
        """
        # 通知人修改
        _auth_group_users.return_value = [self.user]
        # 开启消息通知
        self.sys_config.set("mail", "true")
        self.sys_config.set("ding", "true")
        # 修改工单状态为待审核
        self.audit.workflow_type = WorkflowDict.workflow_type["sqlreview"]
        self.audit.workflow_id = self.wf.id
        self.audit.current_status = WorkflowDict.workflow_status["audit_wait"]
        self.audit.save()
        r = notify_for_audit(audit_id=self.audit.audit_id)
        self.assertIsNone(r)
        _msg_sender.assert_called_once()

    @patch("sql.notify.MsgSender")
    @patch("sql.notify.auth_group_users")
    def test_notify_for_sqlreview_audit_success(self, _auth_group_users, _msg_sender):
        """
        测试SQL上线申请审核通过通知
        :return:
        """
        # 通知人修改
        _auth_group_users.return_value = [self.user]
        # 开启消息通知
        self.sys_config.set("mail", "true")
        self.sys_config.set("ding", "true")
        # 修改工单状态审核通过
        self.audit.workflow_type = WorkflowDict.workflow_type["sqlreview"]
        self.audit.workflow_id = self.wf.id
        self.audit.current_status = WorkflowDict.workflow_status["audit_success"]
        self.audit.create_user = self.user.username
        self.audit.save()
        r = notify_for_audit(audit_id=self.audit.audit_id)
        self.assertIsNone(r)
        _msg_sender.assert_called_once()

    @patch("sql.notify.MsgSender")
    @patch("sql.notify.auth_group_users")
    def test_notify_for_sqlreview_audit_reject(self, _auth_group_users, _msg_sender):
        """
        测试SQL上线申请审核驳回通知
        :return:
        """
        # 通知人修改
        _auth_group_users.return_value = [self.user]
        # 开启消息通知
        self.sys_config.set("mail", "true")
        self.sys_config.set("ding", "true")
        # 修改工单状态审核通过
        self.audit.workflow_type = WorkflowDict.workflow_type["sqlreview"]
        self.audit.workflow_id = self.wf.id
        self.audit.current_status = WorkflowDict.workflow_status["audit_reject"]
        self.audit.create_user = self.user.username
        self.audit.save()
        r = notify_for_audit(audit_id=self.audit.audit_id)
        self.assertIsNone(r)
        _msg_sender.assert_called_once()

    @patch("sql.notify.MsgSender")
    @patch("sql.notify.auth_group_users")
    def test_notify_for_sqlreview_audit_abort(self, _auth_group_users, _msg_sender):
        """
        测试SQL上线申请审核取消通知
        :return:
        """
        # 通知人修改
        _auth_group_users.return_value = [self.user]
        # 开启消息通知
        self.sys_config.set("mail", "true")
        self.sys_config.set("ding", "true")
        # 修改工单状态审核取消
        self.audit.workflow_type = WorkflowDict.workflow_type["sqlreview"]
        self.audit.workflow_id = self.wf.id
        self.audit.current_status = WorkflowDict.workflow_status["audit_abort"]
        self.audit.create_user = self.user.username
        self.audit.audit_auth_groups = self.aug.id
        self.audit.save()
        r = notify_for_audit(audit_id=self.audit.audit_id)
        self.assertIsNone(r)
        _msg_sender.assert_called_once()

    @patch("sql.notify.MsgSender")
    @patch("sql.notify.auth_group_users")
    def test_notify_for_sqlreview_wrong_workflow_type(
        self, _auth_group_users, _msg_sender
    ):
        """
        测试不存在的工单类型
        :return:
        """
        # 通知人修改
        _auth_group_users.return_value = [self.user]
        # 开启消息通知
        self.sys_config.set("mail", "true")
        self.sys_config.set("ding", "true")
        # 修改工单状态审核取消
        self.audit.workflow_type = 10
        self.audit.save()
        with self.assertRaisesMessage(Exception, "工单类型不正确"):
            notify_for_audit(audit_id=self.audit.audit_id)

    @patch("sql.notify.MsgSender")
    @patch("sql.notify.auth_group_users")
    def test_notify_for_query_audit_wait_apply_db_perm(
        self, _auth_group_users, _msg_sender
    ):
        """
        测试查询申请库权限
        :return:
        """
        # 通知人修改
        _auth_group_users.return_value = [self.user]
        # 开启消息通知
        self.sys_config.set("mail", "true")
        self.sys_config.set("ding", "true")
        # 修改工单状态为待审核
        self.audit.workflow_type = WorkflowDict.workflow_type["query"]
        self.audit.workflow_id = self.query_apply_1.apply_id
        self.audit.current_status = WorkflowDict.workflow_status["audit_wait"]
        self.audit.save()
        # 修改工单为库权限申请
        self.query_apply_1.priv_type = 1
        self.query_apply_1.save()
        r = notify_for_audit(audit_id=self.audit.audit_id)
        self.assertIsNone(r)
        _msg_sender.assert_called_once()

    @patch("sql.notify.MsgSender")
    @patch("sql.notify.auth_group_users")
    def test_notify_for_query_audit_wait_apply_tb_perm(
        self, _auth_group_users, _msg_sender
    ):
        """
        测试查询申请表权限
        :return:
        """
        # 通知人修改
        _auth_group_users.return_value = [self.user]
        # 开启消息通知
        self.sys_config.set("mail", "true")
        self.sys_config.set("ding", "true")
        # 修改工单状态为待审核
        self.audit.workflow_type = WorkflowDict.workflow_type["query"]
        self.audit.workflow_id = self.query_apply_1.apply_id
        self.audit.current_status = WorkflowDict.workflow_status["audit_wait"]
        self.audit.save()
        # 修改工单为表权限申请
        self.query_apply_1.priv_type = 2
        self.query_apply_1.save()
        r = notify_for_audit(audit_id=self.audit.audit_id)
        self.assertIsNone(r)
        _msg_sender.assert_called_once()

    @patch("sql.notify.MsgSender")
    def test_notify_for_execute_disable(self, _msg_sender):
        """
        测试执行消息关闭
        :return:
        """
        # 开启消息通知
        self.sys_config.set("mail", "false")
        self.sys_config.set("ding", "false")
        r = auto_notify(self.wf, event_type=EventType.M2SQL)
        self.assertIsNone(r)

    @patch("sql.notify.auth_group_users")
    @patch("sql.notify.Audit")
    @patch("sql.notify.MsgSender")
    def test_notify_for_execute(self, _msg_sender, _audit, _auth_group_users):
        """
        测试执行消息
        :return:
        """
        _auth_group_users.return_value = [self.user]
        # 处理工单信息
        _audit.review_info.return_value = (
            self.audit.audit_auth_groups,
            self.audit.current_audit,
        )
        # 开启消息通知
        self.sys_config.set("mail", "true")
        self.sys_config.set("ding", "true")
        self.sys_config.set("ddl_notify_auth_group", self.aug.name)
        # 修改工单状态为执行结束，修改为DDL工单
        self.wf.status = "workflow_finish"
        self.wf.syntax_type = 1
        self.wf.save()
        r = auto_notify(workflow=self.wf, sys_config=self.sys_config)
        self.assertIsNone(r)
        _msg_sender.assert_called()

    # 下面的测试均为 notifier 的测试, 测试 render 和 send
