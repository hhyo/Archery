import datetime
from unittest.mock import patch

import pytest
from pytest_mock import MockFixture
from django.contrib.auth.models import Permission, Group
from django.test import TestCase

from common.config import SysConfig
from common.utils.const import WorkflowStatus, WorkflowType, WorkflowAction
from sql.models import Instance, ResourceGroup, SqlWorkflow, SqlWorkflowContent, QueryPrivilegesApply, ArchiveConfig, \
    WorkflowAudit, WorkflowLog, WorkflowAuditDetail, WorkflowAuditSetting
from sql.utils.tests import User
from sql.utils.workflow_audit import Audit, AuditV2, AuditSetting, AuditException


class TestAudit(TestCase):
    def setUp(self):
        self.sys_config = SysConfig()
        self.user = User.objects.create(
            username="test_user", display="中文显示", is_active=True
        )
        self.su = User.objects.create(
            username="s_user", display="中文显示", is_active=True, is_superuser=True
        )
        tomorrow = datetime.datetime.today() + datetime.timedelta(days=1)
        self.ins = Instance.objects.create(
            instance_name="some_ins",
            type="slave",
            db_type="mysql",
            host="some_host",
            port=3306,
            user="ins_user",
            password="some_str",
        )
        self.res_group = ResourceGroup.objects.create(
            group_id=1, group_name="group_name"
        )
        self.wf = SqlWorkflow.objects.create(
            workflow_name="some_name",
            group_id=1,
            group_name="g1",
            engineer_display="",
            audit_auth_groups="some_audit_group",
            create_time=datetime.datetime.now(),
            status="workflow_timingtask",
            is_backup=True,
            instance=self.ins,
            db_name="some_db",
            syntax_type=1,
        )
        self.own_wf = SqlWorkflow.objects.create(
            workflow_name="some_name",
            group_id=1,
            group_name="g1",
            engineer=self.user.username,
            audit_auth_groups="some_audit_group",
            create_time=datetime.datetime.now(),
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
        self.archive_apply_1 = ArchiveConfig.objects.create(
            title="title",
            resource_group=self.res_group,
            audit_auth_groups="some_audit_group",
            src_instance=self.ins,
            src_db_name="src_db_name",
            src_table_name="src_table_name",
            dest_instance=self.ins,
            dest_db_name="src_db_name",
            dest_table_name="src_table_name",
            condition="1=1",
            mode="file",
            no_delete=True,
            sleep=1,
            status=WorkflowStatus.WAITING,
            state=False,
            user_name="some_user",
            user_display="display",
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
        self.wl = WorkflowLog.objects.create(
            audit_id=self.audit.audit_id, operation_type=1
        )

    def tearDown(self):
        self.sys_config.purge()
        User.objects.all().delete()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()
        WorkflowAudit.objects.all().delete()
        WorkflowAuditDetail.objects.all().delete()
        WorkflowAuditSetting.objects.all().delete()
        QueryPrivilegesApply.objects.all().delete()
        WorkflowLog.objects.all().delete()
        ResourceGroup.objects.all().delete()
        ArchiveConfig.objects.all().delete()

    def test_audit_add_query(self):
        """测试添加查询审核工单"""
        result, _ = Audit.add(1, self.query_apply_1.apply_id)
        audit_id = result["data"]["audit_id"]
        workflow_status = result["data"]["workflow_status"]
        self.assertEqual(workflow_status, WorkflowStatus.WAITING)
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        # 当前审批
        self.assertEqual(audit_detail.current_audit, "some_audit_group")
        # 无下级审批
        self.assertEqual(audit_detail.next_audit, "-1")
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).first()
        self.assertEqual(log_info.operation_type, 0)
        self.assertEqual(log_info.operation_type_desc, "提交")
        self.assertIn("等待审批，审批流程：", log_info.operation_info)

    def test_audit_add_sqlreview(self):
        """测试添加上线审核工单"""
        result, _ = Audit.add(2, self.wf.id)
        audit_id = result["data"]["audit_id"]
        workflow_status = result["data"]["workflow_status"]
        self.assertEqual(workflow_status, WorkflowStatus.WAITING)
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        # 当前审批
        self.assertEqual(audit_detail.current_audit, "some_audit_group")
        # 无下级审批
        self.assertEqual(audit_detail.next_audit, "-1")
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).first()
        self.assertEqual(log_info.operation_type, 0)
        self.assertEqual(log_info.operation_type_desc, "提交")
        self.assertIn("等待审批，审批流程：", log_info.operation_info)

    def test_audit_add_archive_review(self):
        """测试添加数据归档工单"""
        result, workflow_audit_detail = Audit.add(3, self.archive_apply_1.id)
        audit_id = result["data"]["audit_id"]
        workflow_status = result["data"]["workflow_status"]
        self.assertEqual(workflow_status, WorkflowStatus.WAITING)
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        # 当前审批
        self.assertEqual(audit_detail.current_audit, "some_audit_group")
        # 无下级审批
        self.assertEqual(audit_detail.next_audit, "-1")
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).first()
        self.assertEqual(log_info.operation_type, 0)
        self.assertEqual(log_info.operation_type_desc, "提交")
        self.assertIn("等待审批，审批流程：", log_info.operation_info)

    def test_audit_add_wrong_type(self):
        """测试添加不存在的类型"""
        with self.assertRaisesMessage(Exception, "工单类型不存在"):
            Audit.add(4, 1)

    def test_audit_add_settings_not_exists(self):
        """测试审批流程未配置"""
        self.wf.audit_auth_groups = ""
        self.wf.save()
        with self.assertRaisesMessage(Exception, "审批流程不能为空，请先配置审批流程"):
            Audit.add(2, self.wf.id)

    def test_audit_add_duplicate(self):
        """测试重复提交"""
        Audit.add(2, self.wf.id)
        with self.assertRaisesMessage(Exception, "该工单当前状态为待审核，请勿重复提交"):
            Audit.add(2, self.wf.id)

    @patch("sql.utils.workflow_audit.is_auto_review", return_value=True)
    def test_audit_add_auto_review(self, _is_auto_review):
        """测试提交自动审核通过"""
        self.sys_config.set("auto_review", "true")
        result, workflow_audit_detail = Audit.add(2, self.wf.id)
        audit_id = result["data"]["audit_id"]
        workflow_status = result["data"]["workflow_status"]
        self.assertEqual(workflow_status, WorkflowStatus.PASSED)
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        # 无下级审批
        self.assertEqual(audit_detail.next_audit, "-1")
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).first()
        self.assertEqual(log_info.operation_type, 0)
        self.assertEqual(log_info.operation_type_desc, "提交")
        self.assertEqual(log_info.operation_info, "无需审批，系统直接审核通过")

    def test_audit_add_multiple_audit(self):
        """测试提交多级审核"""
        self.wf.audit_auth_groups = "1,2,3"
        self.wf.save()
        result, _ = Audit.add(2, self.wf.id)
        audit_id = result["data"]["audit_id"]
        workflow_status = result["data"]["workflow_status"]
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        self.assertEqual(workflow_status, WorkflowStatus.WAITING)
        # 存在下级审批
        self.assertEqual(audit_detail.current_audit, "1")
        self.assertEqual(audit_detail.next_audit, "2")
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).first()
        self.assertEqual(log_info.operation_type, 0)
        self.assertEqual(log_info.operation_type_desc, "提交")
        self.assertIn("等待审批，审批流程：", log_info.operation_info)

    def test_audit_success_not_exists_next(self):
        """测试审核通过、无下一级"""
        self.audit.current_audit = "3"
        self.audit.next_audit = "-1"
        self.audit.save()
        result, _ = Audit.audit(
            self.audit.audit_id,
            WorkflowStatus.PASSED,
            self.user.username,
            "通过",
        )
        audit_id = self.audit.audit_id
        workflow_status = result["data"]["workflow_status"]
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        self.assertEqual(workflow_status, WorkflowStatus.PASSED)
        # 不存在下级审批
        self.assertEqual(audit_detail.next_audit, "-1")
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).order_by("-id").first()
        self.assertEqual(log_info.operator, self.user.username)
        self.assertEqual(log_info.operator_display, self.user.display)
        self.assertEqual(log_info.operation_type, 1)
        self.assertEqual(log_info.operation_type_desc, "审批通过")
        self.assertEqual(log_info.operation_info, f"审批备注：通过，下级审批：None")

    def test_audit_success_exists_next(self):
        """测试审核通过、存在下一级"""
        self.audit.current_audit = "1"
        self.audit.next_audit = "2"
        self.audit.save()
        result, _ = Audit.audit(
            self.audit.audit_id,
            WorkflowStatus.PASSED,
            self.user.username,
            "通过",
        )
        audit_id = self.audit.audit_id
        workflow_status = result["data"]["workflow_status"]
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        self.assertEqual(workflow_status, WorkflowStatus.WAITING)
        # 存在下级审批
        self.assertEqual(audit_detail.next_audit, "3")
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).order_by("-id").first()
        self.assertEqual(log_info.operator, self.user.username)
        self.assertEqual(log_info.operator_display, self.user.display)
        self.assertEqual(log_info.operation_type, 1)
        self.assertEqual(log_info.operation_type_desc, "审批通过")
        self.assertEqual(log_info.operation_info, f"审批备注：通过，下级审批：2")

    def test_audit_reject(self):
        """测试审核不通过"""
        result, _ = Audit.audit(
            self.audit.audit_id,
            WorkflowStatus.REJECTED,
            self.user.username,
            "不通过",
        )
        audit_id = self.audit.audit_id
        workflow_status = result["data"]["workflow_status"]
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        self.assertEqual(workflow_status, WorkflowStatus.REJECTED)
        # 不存在下级审批
        self.assertEqual(audit_detail.next_audit, "-1")
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).order_by("-id").first()
        self.assertEqual(log_info.operator, self.user.username)
        self.assertEqual(log_info.operator_display, self.user.display)
        self.assertEqual(log_info.operation_type, 2)
        self.assertEqual(log_info.operation_type_desc, "审批不通过")
        self.assertEqual(log_info.operation_info, f"审批备注：不通过")

    def test_audit_abort(self):
        """测试取消审批"""
        self.audit.create_user = self.user.username
        self.audit.save()
        result, _ = Audit.audit(
            self.audit.audit_id,
            WorkflowStatus.ABORTED,
            self.user.username,
            "取消",
        )
        audit_id = self.audit.audit_id
        workflow_status = result["data"]["workflow_status"]
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        self.assertEqual(workflow_status, WorkflowStatus.ABORTED)
        # 不存在下级审批
        self.assertEqual(audit_detail.next_audit, "-1")
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).order_by("-id").first()
        self.assertEqual(log_info.operator, self.user.username)
        self.assertEqual(log_info.operator_display, self.user.display)
        self.assertEqual(log_info.operation_type, 3)
        self.assertEqual(log_info.operation_type_desc, "审批取消")
        self.assertEqual(log_info.operation_info, f"取消原因：取消")

    def test_audit_wrong_exception(self):
        """测试审核异常的状态"""
        with self.assertRaisesMessage(Exception, "审核异常"):
            Audit.audit(self.audit.audit_id, 10, self.user.username, "")

    def test_audit_success_wrong_status(self):
        """测试审核通过，当前状态不是待审核"""
        self.audit.current_status = 1
        self.audit.save()
        with self.assertRaisesMessage(Exception, "工单不是待审核状态，请返回刷新"):
            Audit.audit(
                self.audit.audit_id,
                WorkflowStatus.PASSED,
                self.user.username,
                "",
            )

    def test_audit_reject_wrong_status(self):
        """测试审核不通过，当前状态不是待审核"""
        self.audit.current_status = 1
        self.audit.save()
        with self.assertRaisesMessage(Exception, "工单不是待审核状态，请返回刷新"):
            Audit.audit(
                self.audit.audit_id,
                WorkflowStatus.REJECTED,
                self.user.username,
                "",
            )

    def test_audit_abort_wrong_status(self):
        """测试审核不通过，当前状态不是待审核"""
        self.audit.current_status = 2
        self.audit.save()
        with self.assertRaisesMessage(Exception, "工单不是待审核态/审核通过状态，请返回刷新"):
            Audit.audit(
                self.audit.audit_id,
                WorkflowStatus.ABORTED,
                self.user.username,
                "",
            )

    @patch("sql.utils.workflow_audit.user_groups", return_value=[])
    def test_todo(self, _user_groups):
        """TODO 测试todo数量,未断言"""
        Audit.todo(self.user)
        Audit.todo(self.su)

    def test_detail(self):
        """测试获取审核信息"""
        result = Audit.detail(self.audit.audit_id)
        self.assertEqual(result, self.audit)
        result = Audit.detail(0)
        self.assertEqual(result, None)

    def test_detail_by_workflow_id(self):
        """测试通过业务id获取审核信息"""
        self.audit.workflow_type = WorkflowType.SQL_REVIEW
        self.audit.workflow_id = self.wf.id
        self.audit.save()
        result = Audit.detail_by_workflow_id(self.wf.id, WorkflowType.SQL_REVIEW)
        self.assertEqual(result, self.audit)
        result = Audit.detail_by_workflow_id(0, 0)
        self.assertEqual(result, None)

    def test_settings(self):
        """测试通过组和审核类型，获取审核配置信息"""
        WorkflowAuditSetting.objects.create(
            workflow_type=1, group_id=1, audit_auth_groups="1,2,3"
        )
        result = Audit.settings(workflow_type=1, group_id=1)
        self.assertEqual(result, "1,2,3")
        result = Audit.settings(0, 0)
        self.assertEqual(result, None)

    def test_change_settings_edit(self):
        """修改配置信息"""
        ws = WorkflowAuditSetting.objects.create(
            workflow_type=1, group_id=1, audit_auth_groups="1,2,3"
        )
        Audit.change_settings(workflow_type=1, group_id=1, audit_auth_groups="1,2")
        ws = WorkflowAuditSetting.objects.get(audit_setting_id=ws.audit_setting_id)
        self.assertEqual(ws.audit_auth_groups, "1,2")

    def test_change_settings_add(self):
        """添加配置信息"""
        Audit.change_settings(workflow_type=1, group_id=1, audit_auth_groups="1,2")
        ws = WorkflowAuditSetting.objects.get(workflow_type=1, group_id=1)
        self.assertEqual(ws.audit_auth_groups, "1,2")

    @patch("sql.utils.workflow_audit.auth_group_users")
    @patch("sql.utils.workflow_audit.Audit.detail_by_workflow_id")
    def test_can_review_sql_review(self, _detail_by_workflow_id, _auth_group_users):
        """测试判断用户当前是否是可审核上线工单，非管理员拥有权限"""
        sql_review = Permission.objects.get(codename="sql_review")
        self.user.user_permissions.add(sql_review)
        aug = Group.objects.create(name="auth_group")
        _detail_by_workflow_id.return_value.current_audit = aug.id
        _auth_group_users.return_value.filter.exists = True
        self.audit.workflow_type = WorkflowType.SQL_REVIEW
        self.audit.workflow_id = self.wf.id
        self.audit.save()
        r = Audit.can_review(
            self.user, self.audit.workflow_id, self.audit.workflow_type
        )
        self.assertEqual(r, True)

    @patch("sql.utils.workflow_audit.auth_group_users")
    @patch("sql.utils.workflow_audit.Audit.detail_by_workflow_id")
    def test_cannot_review_self_sql_review(
        self, _detail_by_workflow_id, _auth_group_users
    ):
        """测试确认用户不能审核自己提交的上线工单，非管理员拥有权限"""
        self.sys_config.set("ban_self_audit", "true")
        sql_review = Permission.objects.get(codename="sql_review")
        self.user.user_permissions.add(sql_review)
        aug = Group.objects.create(name="auth_group")
        _detail_by_workflow_id.return_value.current_audit = aug.id
        _auth_group_users.return_value.filter.exists = True
        self.audit.workflow_type = WorkflowType.SQL_REVIEW
        self.audit.workflow_id = self.own_wf.id
        self.audit.save()
        r = Audit.can_review(
            self.user, self.audit.workflow_id, self.audit.workflow_type
        )
        self.assertEqual(r, False)

    @patch("sql.utils.workflow_audit.auth_group_users")
    @patch("sql.utils.workflow_audit.Audit.detail_by_workflow_id")
    def test_can_review_query_review(self, _detail_by_workflow_id, _auth_group_users):
        """测试判断用户当前是否是可审核查询工单，非管理员拥有权限"""
        query_review = Permission.objects.get(codename="query_review")
        self.user.user_permissions.add(query_review)
        aug = Group.objects.create(name="auth_group")
        _detail_by_workflow_id.return_value.current_audit = aug.id
        _auth_group_users.return_value.filter.exists = True
        self.audit.workflow_type = WorkflowType.QUERY
        self.audit.workflow_id = self.query_apply_1.apply_id
        self.audit.save()
        r = Audit.can_review(
            self.user, self.audit.workflow_id, self.audit.workflow_type
        )
        self.assertEqual(r, True)

    @patch("sql.utils.workflow_audit.auth_group_users")
    @patch("sql.utils.workflow_audit.Audit.detail_by_workflow_id")
    def test_can_review_sql_review_super(
        self, _detail_by_workflow_id, _auth_group_users
    ):
        """测试判断用户当前是否是可审核查询工单，用户是管理员"""
        aug = Group.objects.create(name="auth_group")
        _detail_by_workflow_id.return_value.current_audit = aug.id
        _auth_group_users.return_value.filter.exists = True
        self.audit.workflow_type = WorkflowType.SQL_REVIEW
        self.audit.workflow_id = self.wf.id
        self.audit.save()
        r = Audit.can_review(self.su, self.audit.workflow_id, self.audit.workflow_type)
        self.assertEqual(r, True)

    @patch("sql.utils.workflow_audit.auth_group_users")
    @patch("sql.utils.workflow_audit.Audit.detail_by_workflow_id")
    def test_can_review_wrong_status(self, _detail_by_workflow_id, _auth_group_users):
        """测试判断用户当前是否是可审核，非待审核工单"""
        aug = Group.objects.create(name="auth_group")
        _detail_by_workflow_id.return_value.current_audit = aug.id
        _auth_group_users.return_value.filter.exists = True
        self.audit.workflow_type = WorkflowType.SQL_REVIEW
        self.audit.workflow_id = self.wf.id
        self.audit.current_status = WorkflowStatus.PASSED
        self.audit.save()
        r = Audit.can_review(
            self.user, self.audit.workflow_id, self.audit.workflow_type
        )
        self.assertEqual(r, False)

    @patch("sql.utils.workflow_audit.auth_group_users")
    @patch("sql.utils.workflow_audit.Audit.detail_by_workflow_id")
    def test_can_review_no_prem(self, _detail_by_workflow_id, _auth_group_users):
        """测试判断用户当前是否是可审核，普通用户无权限"""
        aug = Group.objects.create(name="auth_group")
        _detail_by_workflow_id.return_value.current_audit = aug.id
        _auth_group_users.return_value.filter.exists = True
        self.audit.workflow_type = WorkflowType.SQL_REVIEW
        self.audit.workflow_id = self.wf.id
        self.audit.save()
        r = Audit.can_review(
            self.user, self.audit.workflow_id, self.audit.workflow_type
        )
        self.assertEqual(r, False)

    @patch("sql.utils.workflow_audit.auth_group_users")
    @patch("sql.utils.workflow_audit.Audit.detail_by_workflow_id")
    def test_can_review_no_prem_exception(
        self, _detail_by_workflow_id, _auth_group_users
    ):
        """测试判断用户当前是否是可审核，权限组不存在"""
        Group.objects.create(name="auth_group")
        _detail_by_workflow_id.side_effect = RuntimeError()
        _auth_group_users.return_value.filter.exists = True
        self.audit.workflow_type = WorkflowType.SQL_REVIEW
        self.audit.workflow_id = self.wf.id
        self.audit.save()
        with self.assertRaisesMessage(Exception, "当前审批auth_group_id不存在，请检查并清洗历史数据"):
            Audit.can_review(
                self.user, self.audit.workflow_id, self.audit.workflow_type
            )

    def test_review_info_no_review(self):
        """测试获取当前工单审批流程和当前审核组，无需审批"""
        self.audit.workflow_type = WorkflowType.SQL_REVIEW
        self.audit.workflow_id = self.wf.id
        self.audit.audit_auth_groups = ""
        self.audit.current_audit = "-1"
        self.audit.save()
        audit_auth_group, current_audit_auth_group = Audit.review_info(
            self.audit.workflow_id, self.audit.workflow_type
        )
        self.assertEqual(audit_auth_group, "无需审批")
        self.assertEqual(current_audit_auth_group, None)

    def test_review_info(self):
        """测试获取当前工单审批流程和当前审核组，无需审批"""
        aug = Group.objects.create(name="DBA")
        self.audit.workflow_type = WorkflowType.SQL_REVIEW
        self.audit.workflow_id = self.wf.id
        self.audit.audit_auth_groups = str(aug.id)
        self.audit.current_audit = str(aug.id)
        self.audit.save()
        audit_auth_group, current_audit_auth_group = Audit.review_info(
            self.audit.workflow_id, self.audit.workflow_type
        )
        self.assertEqual(audit_auth_group, "DBA")
        self.assertEqual(current_audit_auth_group, "DBA")

    def test_logs(self):
        """测试获取工单日志"""
        r = Audit.logs(self.audit.audit_id).first()
        self.assertEqual(r, self.wl)


# AuditV2 测试
def test_create_audit(sql_workflow, sql_query_apply, archive_apply, resource_group,
                      mocker: MockFixture):
    """测试正常创建, 可正常获取到一个 audit_setting"""
    mock_generate_audit_setting = mocker.patch.object(AuditV2, "generate_audit_setting")
    fake_audit_setting = AuditSetting(
        auto_pass=False,
        audit_auth_groups=["some_auth_group"],
    )
    mock_generate_audit_setting.return_value = fake_audit_setting

    workflow, workflow_content = sql_workflow
    audit = AuditV2(workflow=workflow)
    audit.create_audit()
    workflow.refresh_from_db()
    assert workflow.audit_auth_groups == fake_audit_setting.audit_auth_group_in_db

    audit = AuditV2(workflow=sql_query_apply)
    audit.create_audit()
    sql_query_apply.refresh_from_db()
    assert sql_query_apply.audit_auth_groups == fake_audit_setting.audit_auth_group_in_db

    audit = AuditV2(workflow=archive_apply,
                    resource_group=resource_group.group_name,
                    resource_group_id=resource_group.group_id)
    audit.create_audit()
    archive_apply.refresh_from_db()
    assert archive_apply.audit_auth_groups == fake_audit_setting.audit_auth_group_in_db


def test_create_audit_auto_pass(sql_workflow, mocker: MockFixture):
    workflow, workflow_content = sql_workflow
    mock_generate_audit_setting = mocker.patch.object(AuditV2, "generate_audit_setting")
    fake_audit_setting = AuditSetting(
        auto_pass=True,
        audit_auth_groups=[],
    )
    mock_generate_audit_setting.return_value = fake_audit_setting
    audit = AuditV2(workflow=workflow)
    audit.create_audit()
    workflow.refresh_from_db()
    assert workflow.status == "workflow_review_pass"
    assert audit.audit.current_status == WorkflowStatus.PASSED


@pytest.fixture
def fake_generate_audit_setting(mocker: MockFixture):
    mock_generate_audit_setting = mocker.patch.object(AuditV2, "generate_audit_setting")
    fake_audit_setting = AuditSetting(
        auto_pass=False,
        audit_auth_groups=["some_auth_group"],
    )
    mock_generate_audit_setting.return_value = fake_audit_setting
    yield mock_generate_audit_setting


@pytest.mark.parametrize("status,operation,allowed", [
    (WorkflowStatus.WAITING, WorkflowAction.SUBMIT, False),
    (WorkflowStatus.WAITING, WorkflowAction.PASS, True),
    (WorkflowStatus.WAITING, WorkflowAction.REJECT, True),
    (WorkflowStatus.WAITING, WorkflowAction.EXECUTE_START, False),
    (WorkflowStatus.PASSED, WorkflowAction.ABORT, True),
    (WorkflowStatus.PASSED, WorkflowAction.REJECT, False),
    (WorkflowStatus.PASSED, WorkflowAction.PASS, False),
    (WorkflowStatus.REJECTED, WorkflowAction.PASS, False),
    (WorkflowStatus.ABORTED, WorkflowAction.PASS, False),
])
def test_supported_operate(sql_query_apply, status, super_user, operation, allowed: bool, fake_generate_audit_setting):
    audit = AuditV2(workflow=sql_query_apply)
    audit.create_audit()
    audit.audit.current_status = status
    audit.audit.save()
    if not allowed:
        with pytest.raises(AuditException) as e:
            audit.operate(operation, super_user, "test")
        assert "不允许的操作" in str(e.value)
    else:
        result = audit.operate(operation, super_user, "test")
        assert isinstance(result, WorkflowAuditDetail)
        assert result.audit_id == audit.audit.audit_id
        # 在 log 表里找对于的记录
        log = WorkflowLog.objects.filter(audit_id=audit.audit.audit_id, operation_type=operation).all()
        assert len(log) == 1


def test_pass_has_next_level(sql_query_apply, super_user, fake_generate_audit_setting):
    fake_generate_audit_setting.return_value = AuditSetting(
        auto_pass=False,
        audit_auth_groups=["some_auth_group", "another_auth_group"],
    )
    audit = AuditV2(workflow=sql_query_apply)
    audit.create_audit()
    audit.operate(WorkflowAction.PASS, super_user, "ok")
    assert audit.audit.current_status == WorkflowStatus.WAITING
    assert audit.audit.current_audit == "another_auth_group"
    assert audit.audit.next_audit == "-1"


def test_generate_audit_setting_empty_config(sql_query_apply):
    audit = AuditV2(workflow=sql_query_apply)
    with pytest.raises(AuditException) as e:
        audit_setting = audit.generate_audit_setting()
    assert "未配置审流" in str(e.value)


def test_generate_audit_setting_full_config(sql_workflow, sql_query_apply, archive_apply, resource_group,
                      mocker: MockFixture):
    pass
