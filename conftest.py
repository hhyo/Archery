import datetime

import pytest
from pytest_mock import MockFixture
from django.contrib.auth.models import Group

from common.utils.const import WorkflowStatus
from sql.models import (
    Instance,
    ResourceGroup,
    SqlWorkflow,
    SqlWorkflowContent,
    QueryPrivilegesApply,
    ArchiveConfig,
    InstanceTag,
    WorkflowAudit,
)
from common.config import SysConfig
from sql.utils.workflow_audit import AuditV2, AuditSetting


@pytest.fixture
def normal_user(django_user_model):
    user = django_user_model.objects.create(
        username="test_user", display="中文显示", is_active=True
    )
    yield user
    user.delete()


@pytest.fixture
def super_user(django_user_model):
    user = django_user_model.objects.create(
        username="super_user", display="超级用户", is_active=True, is_superuser=True
    )
    yield user
    user.delete()


@pytest.fixture
def db_instance(db):
    ins = Instance.objects.create(
        instance_name="some_ins",
        type="slave",
        db_type="mysql",
        host="some_host",
        port=3306,
        user="ins_user",
        password="some_str",
    )
    yield ins
    ins.delete()


@pytest.fixture
def resource_group(db) -> ResourceGroup:
    res_group = ResourceGroup.objects.create(group_id=1, group_name="group_name")
    yield res_group
    res_group.delete()


@pytest.fixture
def sql_workflow(db_instance):
    wf = SqlWorkflow.objects.create(
        workflow_name="some_name",
        group_id=1,
        group_name="g1",
        engineer_display="",
        audit_auth_groups="some_audit_group",
        create_time=datetime.datetime.now(),
        status="workflow_timingtask",
        is_backup=True,
        instance=db_instance,
        db_name="some_db",
        syntax_type=1,
    )
    wf_content = SqlWorkflowContent.objects.create(
        workflow=wf, sql_content="some_sql", execute_result=""
    )
    yield wf, wf_content
    wf.delete()
    wf_content.delete()


@pytest.fixture
def sql_query_apply(db_instance):
    tomorrow = datetime.datetime.today() + datetime.timedelta(days=1)
    query_apply_1 = QueryPrivilegesApply.objects.create(
        group_id=1,
        group_name="some_name",
        title="some_title1",
        user_name="some_user",
        instance=db_instance,
        db_list="some_db,some_db2",
        limit_num=100,
        valid_date=tomorrow,
        priv_type=1,
        status=0,
        audit_auth_groups="1",
    )
    yield query_apply_1
    query_apply_1.delete()


@pytest.fixture
def archive_apply(db_instance, resource_group):
    archive_apply_1 = ArchiveConfig.objects.create(
        title="title",
        resource_group=resource_group,
        audit_auth_groups="",
        src_instance=db_instance,
        src_db_name="src_db_name",
        src_table_name="src_table_name",
        dest_instance=db_instance,
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
    yield archive_apply_1
    archive_apply_1.delete()


@pytest.fixture
def setup_sys_config(db):
    sys_config = SysConfig()
    yield sys_config
    sys_config.purge()


@pytest.fixture
def create_auth_group(db):
    auth_group = Group.objects.create(name="test_group")
    yield auth_group
    auth_group.delete()


@pytest.fixture
def fake_generate_audit_setting(mocker: MockFixture, super_user, create_auth_group):
    super_user.groups.add(create_auth_group)
    mock_generate_audit_setting = mocker.patch.object(AuditV2, "generate_audit_setting")
    fake_audit_setting = AuditSetting(
        auto_pass=False,
        audit_auth_groups=[create_auth_group.id],
    )
    mock_generate_audit_setting.return_value = fake_audit_setting
    yield mock_generate_audit_setting


@pytest.fixture
def instance_tag(db):
    tag = InstanceTag.objects.create(tag_code="test_tag", tag_name="测试标签")
    yield tag
    tag.delete()


# ─── Table Instance Locator shared fixtures ───────────────────────────────────


class _FakeResult:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error


class _FakeEngine:
    """Fake engine for table-instance-locator unit tests.

    Args:
        instance: the Instance object (provides regex attributes).
        db_tables: dict mapping db_name -> list of table names.
        db_error: if set, get_all_databases() returns an error result.
    """

    def __init__(self, instance, db_tables=None, db_error=None):
        self.instance = instance
        self._db_tables = db_tables or {}
        self._db_error = db_error

    def get_all_databases(self):
        if self._db_error:
            return _FakeResult(error=self._db_error)
        return _FakeResult(rows=list(self._db_tables.keys()))

    def get_all_tables(self, db_name, **kwargs):
        return _FakeResult(rows=self._db_tables.get(db_name, []))


@pytest.fixture
def fake_engine_class():
    """Exposes the _FakeEngine class for use in tests."""
    return _FakeEngine


@pytest.fixture
def fake_locator_request():
    """Factory for building TableLocatorRequest objects in tests."""
    from sql_api.table_instance_locator import TableLocatorRequest

    def _make(table_name=None, table_pattern=None, user_id=None):
        return TableLocatorRequest(
            table_name=table_name,
            table_pattern=table_pattern,
            request_user_id=user_id,
        )

    return _make


@pytest.fixture
def create_resource_group(db):
    resource_group = ResourceGroup.objects.create(
        group_name="group_name",
        is_deleted=False,
        qywx_webhook="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
        feishu_webhook="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
        ding_webhook="https://oapi.dingtalk.com/robot/send?access_token=xxx",
    )
    yield resource_group
    resource_group.delete()


@pytest.fixture
def create_audit_workflow(normal_user, create_resource_group):
    audit_wf = WorkflowAudit.objects.create(
        group_id=create_resource_group.group_id,
        group_name=create_resource_group.group_name,
        workflow_id=1,
        workflow_type=2,
        workflow_title="申请标题",
        workflow_remark="申请备注",
        audit_auth_groups="1",
        current_audit="1",
        next_audit="2",
        current_status=0,
        create_user=normal_user.username,
    )
    yield audit_wf
    audit_wf.delete()


@pytest.fixture
def clean_auth_group(db):
    yield
    Group.objects.all().delete()
