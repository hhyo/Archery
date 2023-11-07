import datetime

import pytest
from pytest_mock import MockFixture

from common.utils.const import WorkflowStatus
from sql.models import (
    Instance,
    ResourceGroup,
    SqlWorkflow,
    SqlWorkflowContent,
    QueryPrivilegesApply,
    ArchiveConfig,
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
def fake_generate_audit_setting(mocker: MockFixture):
    mock_generate_audit_setting = mocker.patch.object(AuditV2, "generate_audit_setting")
    fake_audit_setting = AuditSetting(
        auto_pass=False,
        audit_auth_groups=[123],
    )
    mock_generate_audit_setting.return_value = fake_audit_setting
    yield mock_generate_audit_setting
