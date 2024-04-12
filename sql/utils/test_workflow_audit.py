import datetime
import json
from unittest.mock import patch

import pytest
from pytest_mock import MockFixture
from django.contrib.auth.models import Permission, Group
from django.test import TestCase

from common.config import SysConfig
from common.utils.const import WorkflowStatus, WorkflowType, WorkflowAction
from sql.models import (
    Instance,
    ResourceGroup,
    SqlWorkflow,
    SqlWorkflowContent,
    QueryPrivilegesApply,
    ArchiveConfig,
    WorkflowAudit,
    WorkflowLog,
    WorkflowAuditDetail,
    WorkflowAuditSetting,
)
from sql.utils.tests import User
from sql.utils.workflow_audit import (
    Audit,
    AuditV2,
    AuditSetting,
    AuditException,
    ReviewNodeType,
)


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
        with self.assertRaisesMessage(
            Exception, "当前审批auth_group_id不存在，请检查并清洗历史数据"
        ):
            Audit.can_review(
                self.user, self.audit.workflow_id, self.audit.workflow_type
            )

    def test_logs(self):
        """测试获取工单日志"""
        r = Audit.logs(self.audit.audit_id).first()
        self.assertEqual(r, self.wl)


# AuditV2 测试
def test_create_audit(
    sql_workflow, sql_query_apply, archive_apply, resource_group, mocker: MockFixture
):
    """测试正常创建, 可正常获取到一个 audit_setting"""
    mock_generate_audit_setting = mocker.patch.object(AuditV2, "generate_audit_setting")
    fake_audit_setting = AuditSetting(
        auto_pass=False,
        audit_auth_groups=[123],
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
    assert (
        sql_query_apply.audit_auth_groups == fake_audit_setting.audit_auth_group_in_db
    )

    audit = AuditV2(
        workflow=archive_apply,
        resource_group=resource_group.group_name,
        resource_group_id=resource_group.group_id,
    )
    audit.create_audit()
    archive_apply.refresh_from_db()
    assert archive_apply.audit_auth_groups == fake_audit_setting.audit_auth_group_in_db


def test_init_no_workflow_and_audit():
    with pytest.raises(ValueError) as e:
        AuditV2()
    assert "WorkflowAudit 或 workflow" in str(e.value)


def test_archive_init_no_resource_group(archive_apply):
    """测试 archive 初始化时指定的资源组不存在"""
    with pytest.raises(AuditException) as e:
        AuditV2(workflow=archive_apply, resource_group="not_exists_group")
    assert "参数错误, 未发现资源组" in str(e.value)


def test_duplicate_create(sql_query_apply, fake_generate_audit_setting):
    audit = AuditV2(workflow=sql_query_apply)
    audit.create_audit()
    with pytest.raises(AuditException) as e:
        audit.create_audit()
    assert "请勿重复提交" in str(e.value)


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
    assert audit.audit.current_status == WorkflowStatus.PASSED


@pytest.mark.parametrize(
    "status,operation,allowed",
    [
        (WorkflowStatus.WAITING, WorkflowAction.SUBMIT, False),
        (WorkflowStatus.WAITING, WorkflowAction.PASS, True),
        (WorkflowStatus.WAITING, WorkflowAction.REJECT, True),
        (WorkflowStatus.WAITING, WorkflowAction.EXECUTE_START, False),
        (WorkflowStatus.PASSED, WorkflowAction.REJECT, True),
        (WorkflowStatus.PASSED, WorkflowAction.PASS, False),
        (WorkflowStatus.REJECTED, WorkflowAction.PASS, False),
        (WorkflowStatus.ABORTED, WorkflowAction.PASS, False),
    ],
)
def test_supported_operate(
    sql_query_apply,
    status,
    super_user,
    operation,
    allowed: bool,
    fake_generate_audit_setting,
):
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
        log = WorkflowLog.objects.filter(
            audit_id=audit.audit.audit_id, operation_type=operation
        ).all()
        assert len(log) == 1


def test_pass_has_next_level(sql_query_apply, super_user, fake_generate_audit_setting):
    fake_generate_audit_setting.return_value = AuditSetting(
        auto_pass=False,
        audit_auth_groups=[1, 2],
    )
    audit = AuditV2(workflow=sql_query_apply)
    audit.create_audit()
    audit.operate(WorkflowAction.PASS, super_user, "ok")
    assert audit.audit.current_status == WorkflowStatus.WAITING
    assert audit.audit.current_audit == 2
    assert audit.audit.next_audit == "-1"


def test_generate_audit_setting_empty_config(sql_query_apply):
    audit = AuditV2(workflow=sql_query_apply)
    with pytest.raises(AuditException) as e:
        audit.generate_audit_setting()
    assert "未配置审流" in str(e.value)


def test_generate_audit_setting_auto_review(
    sql_workflow, setup_sys_config, mocker: MockFixture
):
    sql_workflow, _ = sql_workflow
    setup_sys_config.set("auto_review", True)

    audit = AuditV2(workflow=sql_workflow, sys_config=setup_sys_config)
    mock_is_auto_review = mocker.patch.object(
        audit, "is_auto_review", return_value=True
    )
    audit_setting = audit.generate_audit_setting()
    assert audit_setting.auto_pass is True
    mock_is_auto_review.assert_called()


def test_get_workflow(
    archive_apply,
    sql_query_apply,
    sql_workflow,
    resource_group,
    fake_generate_audit_setting,
):
    """初始化时只传了 audit, 尝试取 workflow"""
    sql_workflow, _ = sql_workflow
    for wf in [sql_query_apply, sql_workflow]:
        a = AuditV2(workflow=wf)
        a.create_audit()
        audit_init_with_audit = AuditV2(audit=a.audit)
        assert audit_init_with_audit.workflow_type == a.workflow_type
        assert audit_init_with_audit.workflow == a.workflow
    a = AuditV2(workflow=archive_apply, resource_group=resource_group.group_name)
    a.create_audit()
    audit_init_with_audit = AuditV2(audit=a.audit)
    assert audit_init_with_audit.workflow_type == a.workflow_type
    assert audit_init_with_audit.workflow == a.workflow


def test_auto_review_non_sql_review(sql_query_apply):
    """当前自动审核仅对 SQL 上线工单生效"""
    audit = AuditV2(workflow=sql_query_apply)
    assert audit.is_auto_review() is False


def test_auto_review_not_applicable(
    db_instance, sql_workflow, instance_tag, setup_sys_config
):
    """未启用, 实例类型不匹配, 实例无对应标签, 正则匹配, 行数超规模"""
    sql_workflow, _ = sql_workflow
    # 未启用
    setup_sys_config.set("auto_review", False)
    audit = AuditV2(workflow=sql_workflow, sys_config=setup_sys_config)
    assert audit.is_auto_review() is False
    setup_sys_config.set("auto_review", True)
    # 实例类型不匹配
    db_instance.db_type = "redis"
    db_instance.save()
    audit.sys_config.set("auto_review_db_type", "mysql")
    assert audit.is_auto_review() is False
    audit.sys_config.set("auto_review_db_type", "redis")
    # 实例无对应标签
    audit.sys_config.set("auto_review_tag", instance_tag.tag_code)
    assert audit.is_auto_review() is False
    db_instance.instance_tag.add(instance_tag)
    # 匹配到高危语句
    audit.sys_config.set("auto_review_regex", "^drop")
    audit.workflow.sqlworkflowcontent.sql_content = "drop table"
    audit.workflow.sqlworkflowcontent.review_content = json.dumps(
        [{"sql": "drop table", "affected_rows": 10}]
    )
    audit.workflow.sqlworkflowcontent.save()
    assert audit.is_auto_review() is False
    audit.sys_config.set("auto_review_regex", "^select")
    # 行数超规模
    audit.sys_config.set("auto_review_max_update_rows", 1)
    assert audit.is_auto_review() is False
    audit.sys_config.set("auto_review_max_update_rows", 1000)
    # 全部条件满足, 自动审核通过
    assert audit.is_auto_review() is True


@pytest.mark.parametrize(
    "sql_command,expected_result",
    [
        ("DROP TABLE my_table;", False),
        ("insert into my_table", True),
        ("FLUSHDB", False),
        ("FLUSHALL", False),
        ("add key", True),
    ],
)
def test_auto_review_with_default_regex(
    db_instance,
    sql_workflow,
    instance_tag,
    setup_sys_config,
    sql_command,
    expected_result,
):
    """
    自动审核逻辑中，测试auto_review_regex未配置时使用默认正则表达式的情况。
    """
    sql_workflow, _ = sql_workflow
    # 设置系统配置未包含 auto_review_regex，模拟未配置的环境
    setup_sys_config.set("auto_review", True)
    setup_sys_config.set("auto_review_db_type", "mysql")
    setup_sys_config.set("auto_review_tag", instance_tag.tag_code)

    db_instance.instance_tag.add(instance_tag)

    # 创建 AuditV2 实例
    audit = AuditV2(workflow=sql_workflow, sys_config=setup_sys_config)
    # 设置审核内容SQL
    audit.workflow.sqlworkflowcontent.sql_content = sql_command
    audit.workflow.sqlworkflowcontent.review_content = json.dumps(
        [{"sql": sql_command, "affected_rows": 0}]
    )
    # 执行自动审核逻辑
    assert audit.is_auto_review() == expected_result


def test_get_review_info(
    sql_query_apply,
    resource_group,
    create_auth_group,
    fake_generate_audit_setting,
    clean_auth_group,
):
    g2 = Group.objects.create(name="g2")
    g3 = Group.objects.create(name="g3")
    fake_generate_audit_setting.return_value = AuditSetting(
        auto_pass=False, audit_auth_groups=[create_auth_group.id, g2.id, g3.id]
    )
    audit = AuditV2(workflow=sql_query_apply)
    audit.create_audit()
    review_info = audit.get_review_info()
    assert review_info.nodes[0].group.name == create_auth_group.name
    assert review_info.nodes[0].is_current_node is True
    assert review_info.nodes[0].is_passed_node is False
    assert review_info.nodes[1].is_current_node is False
    assert review_info.nodes[1].is_passed_node is False

    # 将当前节点设置为第二个节点, 重新生成
    audit.audit.current_audit = str(g2.id)
    audit.audit.save()
    review_info = audit.get_review_info()
    assert review_info.nodes[0].is_current_node is False
    assert review_info.nodes[0].is_passed_node is True
    assert review_info.nodes[1].is_current_node is True
    assert review_info.nodes[1].is_passed_node is False


def test_get_review_info_auto_pass(
    sql_query_apply,
    fake_generate_audit_setting,
    admin_client,
):
    # 自动通过的情况
    fake_generate_audit_setting.return_value = AuditSetting(auto_pass=True)
    audit = AuditV2(workflow=sql_query_apply)
    audit.create_audit()
    review_info = audit.get_review_info()
    assert review_info.nodes[0].node_type == ReviewNodeType.AUTO_PASS
    # 测一下详情页 get
    response = admin_client.get(f"/queryapplydetail/{sql_query_apply.apply_id}/")
    assert response.status_code == 200
    assert "无需审批" in response.content.decode("utf-8")
