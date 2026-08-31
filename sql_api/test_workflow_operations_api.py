"""Focused workflow REST API tests.

HTTP integration cases in this module cover URL dispatch and session identity, which
cannot be proven by service-level unit tests.
"""

import pytest
import yaml
from sql.engines.models import ResultSet
from sql.models import SqlWorkflow

from sql_api.serializers import (
    WorkflowExecutionSerializer,
    WorkflowTerminationSerializer,
)
from sql_api import api_workflow_operations
from sql_api.api_workflow_operations import mutation_response


def test_openapi_contract_uses_audit_id_paths():
    with open(
        "specs/003-migrate-workflow-api/contracts/workflow-operations.openapi.yaml"
    ) as contract:
        paths = yaml.safe_load(contract)["paths"]

    assert "/api/v1/sql-workflows/" in paths
    assert all("workflow_id" not in path for path in paths)
    assert all(
        path == "/api/v1/sql-workflows/" or "{audit_id}" in path
        for path in paths
    )


def test_legacy_workflow_operation_route_is_retired(client):
    response = client.post(
        "/api/v1/workflows/17/approval/", {"audit_remark": "同意"}
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_mutation_response_uses_workflow_detail_url():
    response = mutation_response(42, "操作成功")

    assert response == {
        "status": 0,
        "msg": "操作成功",
        "data": {"audit_id": None, "workflow_id": 42, "redirect_url": "/detail/42/"},
    }


def test_workflow_mutation_serializers_retain_legacy_field_names():
    execution = WorkflowExecutionSerializer(data={"mode": "auto"})
    termination = WorkflowTerminationSerializer(data={"cancel_remark": "终止原因"})

    assert execution.is_valid(), execution.errors
    assert termination.is_valid(), termination.errors


@pytest.mark.django_db
def test_approval_endpoint_uses_path_id_and_session_user(
    authenticated_api_client, normal_user, mocker
):
    workflow = mocker.Mock(id=17)
    auditor = mocker.Mock()
    auditor.audit.current_status = api_workflow_operations.WorkflowStatus.PASSED
    auditor.workflow = workflow
    mocker.patch.object(
        api_workflow_operations,
        "get_sql_workflow_by_audit_id",
        return_value=(auditor.audit, workflow),
    )
    get_auditor = mocker.patch.object(
        api_workflow_operations, "get_auditor", return_value=auditor
    )
    mocker.patch.object(api_workflow_operations, "should_notify", return_value=False)
    normal_user.has_perm = mocker.Mock(return_value=True)

    response = authenticated_api_client.post(
        "/api/v1/sql-workflows/17/approval/", {"audit_remark": "同意"}, format="json"
    )

    assert response.status_code == 200
    get_auditor.assert_called_once()
    auditor.operate.assert_called_once_with(
        api_workflow_operations.WorkflowAction.PASS, normal_user, "同意"
    )


@pytest.mark.django_db
def test_execution_endpoint_rejects_invalid_mode_before_service_call(
    authenticated_api_client, mocker
):
    response = authenticated_api_client.post(
        "/api/v1/sql-workflows/17/execution/", {"mode": "invalid"}, format="json"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_workflow_list_returns_submitters_workflow(
    authenticated_api_client, normal_user, workflow_api_data, mocker
):
    workflow, _, audit = workflow_api_data
    normal_user.has_perm = mocker.Mock(
        side_effect=lambda permission: permission == "sql.menu_sqlworkflow"
    )

    response = authenticated_api_client.post(
        "/api/v1/sql-workflows/list/", {"limit": 20, "offset": 0}, format="json"
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["rows"][0]["id"] == workflow.id
    assert response.json()["rows"][0]["audit_id"] == audit.audit_id
    assert response.json()["rows"][0]["audit_id"] == audit.audit_id


@pytest.mark.django_db
def test_workflow_list_filters_json_syntax_type(
    authenticated_api_client, normal_user, workflow_api_data, mocker
):
    workflow, _, audit = workflow_api_data
    normal_user.has_perm = mocker.Mock(
        side_effect=lambda permission: permission == "sql.menu_sqlworkflow"
    )
    export_workflow = SqlWorkflow.objects.create(
        workflow_name="export workflow",
        group_id=workflow.group_id,
        group_name=workflow.group_name,
        instance=workflow.instance,
        db_name=workflow.db_name,
        syntax_type=3,
        is_backup=workflow.is_backup,
        engineer=workflow.engineer,
        engineer_display=workflow.engineer_display,
        status=workflow.status,
        audit_auth_groups="",
    )

    response = authenticated_api_client.post(
        "/api/v1/sql-workflows/list/",
        {"syntax_type": [3], "limit": 20, "offset": 0},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["rows"][0]["id"] == export_workflow.id


@pytest.mark.django_db
def test_workflow_audit_list_returns_workflows(
    authenticated_api_client, normal_user, workflow_api_data, mocker
):
    workflow, _, audit = workflow_api_data
    normal_user.has_perm = mocker.Mock(return_value=True)

    response = authenticated_api_client.post(
        "/api/v1/sql-workflows/audit-list/", {"limit": 20, "offset": 0}, format="json"
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["rows"][0]["id"] == workflow.id


@pytest.mark.django_db
def test_workflow_detail_returns_saved_fields_for_viewable_workflow(
    authenticated_api_client, workflow_api_data
):
    # HTTP integration verifies URL dispatch, session identity, and response rendering.
    workflow, _, audit = workflow_api_data

    response = authenticated_api_client.get(f"/api/v1/sql-workflows/{audit.audit_id}/")

    assert response.status_code == 200
    workflow_data = response.json()
    assert workflow_data.items() >= {
        "id": workflow.id,
        "workflow_name": "workflow api test",
        "instance": workflow.instance_id,
        "instance_name": "some_ins",
        "db_name": "test_db",
        "status": "workflow_review_pass",
    }.items()


@pytest.mark.django_db
def test_workflow_detail_denies_unviewable_workflow(
    authenticated_api_client, workflow_api_data, mocker
):
    # HTTP integration verifies permission failures are mapped by the API boundary.
    workflow, _, audit = workflow_api_data
    mocker.patch.object(api_workflow_operations, "can_view", return_value=False)

    response = authenticated_api_client.get(f"/api/v1/sql-workflows/{audit.audit_id}/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_workflow_detail_returns_not_found_for_unknown_workflow(
    authenticated_api_client,
):
    # HTTP integration verifies path ID lookup and DRF not-found mapping.
    response = authenticated_api_client.get("/api/v1/sql-workflows/999999/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_workflow_content_and_status_return_compatible_responses(
    authenticated_api_client, workflow_api_data
):
    workflow, _, audit = workflow_api_data

    content_response = authenticated_api_client.get(
        f"/api/v1/sql-workflows/{audit.audit_id}/content/"
    )
    status_response = authenticated_api_client.get(
        f"/api/v1/sql-workflows/{audit.audit_id}/status/"
    )

    assert content_response.status_code == 200
    assert content_response.json()["rows"][0]["sql"] == "select 1"
    assert status_response.json() == {
        "status": "workflow_review_pass",
        "msg": "",
        "data": "",
    }


@pytest.mark.django_db
def test_rollback_and_osc_return_engine_results(
    authenticated_api_client, workflow_api_data, mocker
):
    workflow, _, audit = workflow_api_data
    mocker.patch.object(api_workflow_operations, "can_rollback", return_value=True)
    engine = mocker.patch.object(api_workflow_operations, "get_engine").return_value
    engine.get_rollback.return_value = [["update t", "update t rollback"]]
    engine.osc_control.return_value = ResultSet(rows=[])

    rollback_response = authenticated_api_client.get(
        f"/api/v1/sql-workflows/{audit.audit_id}/rollback/"
    )
    osc_response = authenticated_api_client.post(
        f"/api/v1/sql-workflows/{audit.audit_id}/osc/",
        {"command": "get", "sqlsha1": "hash"},
        format="json",
    )

    assert rollback_response.json() == {
        "status": 0,
        "msg": "",
        "rows": [["update t", "update t rollback"]],
    }
    assert osc_response.json() == {"total": 0, "rows": [], "msg": None}


@pytest.mark.django_db
def test_execution_window_updates_workflow(
    authenticated_api_client, normal_user, workflow_api_data, mocker
):
    workflow, _, audit = workflow_api_data
    normal_user.has_perm = mocker.Mock(return_value=True)
    mocker.patch.object(api_workflow_operations.Audit, "can_review", return_value=True)

    response = authenticated_api_client.patch(
        f"/api/v1/sql-workflows/{audit.audit_id}/execution-window/",
        {
            "run_date_start": "2030-01-01T10:00:00",
            "run_date_end": "2030-01-01T11:00:00",
        },
        format="json",
    )

    workflow.refresh_from_db()
    assert response.status_code == 200
    assert workflow.run_date_start is not None
    assert workflow.run_date_end is not None


@pytest.mark.django_db
def test_terminate_scheduled_workflow_removes_schedule_after_commit(
    authenticated_api_client, normal_user, mocker
):
    normal_user.username = "engineer"
    normal_user.has_perm = mocker.Mock(return_value=False)
    workflow = mocker.Mock(id=7, engineer="engineer", status="workflow_timingtask")
    auditor = mocker.Mock()
    auditor.audit = mocker.Mock(audit_id=70)
    mocker.patch.object(
        api_workflow_operations,
        "get_sql_workflow_by_audit_id",
        return_value=(auditor.audit, workflow),
    )
    mocker.patch.object(api_workflow_operations, "can_cancel", return_value=True)
    mocker.patch.object(api_workflow_operations, "get_auditor", return_value=auditor)
    mocker.patch.object(api_workflow_operations, "SysConfig")
    on_commit = mocker.patch.object(
        api_workflow_operations.transaction,
        "on_commit",
        side_effect=lambda callback: callback(),
    )
    delete_schedule = mocker.patch.object(api_workflow_operations, "del_schedule")
    mocker.patch.object(api_workflow_operations, "should_notify", return_value=False)

    response = authenticated_api_client.post(
        "/api/v1/sql-workflows/70/cancellation/", {"cancel_remark": "取消"}, format="json"
    )

    assert response.status_code == 200
    assert workflow.status == "workflow_abort"
    delete_schedule.assert_called_once_with("sqlreview-timing-7")
    assert on_commit.call_count >= 1


@pytest.mark.django_db
def test_auto_execution_queues_task_and_removes_schedule_after_commit(
    authenticated_api_client, normal_user, mocker
):
    normal_user.display = "执行人"
    normal_user.has_perm = mocker.Mock(return_value=True)
    workflow = mocker.Mock(id=8)
    audit = mocker.Mock(audit_id=3)
    mocker.patch.object(api_workflow_operations, "can_execute", return_value=True)
    mocker.patch.object(
        api_workflow_operations, "on_correct_time_period", return_value=True
    )
    mocker.patch.object(
        api_workflow_operations,
        "get_sql_workflow_by_audit_id",
        return_value=(audit, workflow),
    )
    mocker.patch.object(api_workflow_operations.Audit, "add_log")
    mocker.patch.object(
        api_workflow_operations.transaction,
        "on_commit",
        side_effect=lambda callback: callback(),
    )
    delete_schedule = mocker.patch.object(api_workflow_operations, "del_schedule")
    queue_task = mocker.patch.object(api_workflow_operations, "async_task")

    response = authenticated_api_client.post(
        "/api/v1/sql-workflows/3/execution/", {"mode": "auto"}, format="json"
    )

    assert response.status_code == 200
    assert workflow.status == "workflow_queuing"
    delete_schedule.assert_called_once_with("sqlreview-timing-8")
    queue_task.assert_called_once()


@pytest.mark.django_db
def test_schedule_creates_timing_task_for_authorized_executor(
    authenticated_api_client, normal_user, workflow_api_data, mocker
):
    workflow, _, audit = workflow_api_data
    normal_user.has_perm = mocker.Mock(return_value=True)
    mocker.patch.object(api_workflow_operations, "can_timingtask", return_value=True)
    mocker.patch.object(
        api_workflow_operations, "on_correct_time_period", return_value=True
    )
    mocker.patch.object(
        api_workflow_operations.Audit, "detail_by_workflow_id", return_value=audit
    )
    add_log = mocker.patch.object(api_workflow_operations.Audit, "add_log")
    schedule = mocker.patch.object(api_workflow_operations, "add_sql_schedule")
    mocker.patch.object(
        api_workflow_operations.transaction,
        "on_commit",
        side_effect=lambda callback: callback(),
    )

    response = authenticated_api_client.post(
        f"/api/v1/sql-workflows/{audit.audit_id}/schedule/",
        {"run_date": "2030-01-01 10:00"},
        format="json",
    )

    workflow.refresh_from_db()
    assert response.status_code == 200
    assert response.json()["msg"] == "定时执行已设置"
    assert workflow.status == "workflow_timingtask"
    add_log.assert_called_once()
    schedule.assert_called_once()


def test_schedule_rejects_past_time_before_side_effects(
    authenticated_api_client, mocker
):
    workflow = mocker.Mock(id=9)
    audit = mocker.Mock(audit_id=9)
    mocker.patch.object(
        api_workflow_operations,
        "get_sql_workflow_by_audit_id",
        return_value=(audit, workflow),
    )
    schedule = mocker.patch.object(api_workflow_operations, "add_sql_schedule")

    response = authenticated_api_client.post(
        "/api/v1/sql-workflows/9/schedule/",
        {"run_date": "2000-01-01 00:00"},
        format="json",
    )

    assert response.status_code == 400
    schedule.assert_not_called()


@pytest.mark.django_db
def test_osc_control_does_not_expose_engine_error(authenticated_api_client, mocker):
    workflow = mocker.Mock(id=10)
    audit = mocker.Mock(audit_id=10)
    mocker.patch.object(
        api_workflow_operations,
        "get_sql_workflow_by_audit_id",
        return_value=(audit, workflow),
    )
    mocker.patch.object(api_workflow_operations, "ensure_viewable")
    mocker.patch.object(api_workflow_operations, "get_engine").side_effect = (
        RuntimeError("engine failed")
    )

    response = authenticated_api_client.post(
        "/api/v1/sql-workflows/10/osc/",
        {"command": "get", "sqlsha1": "hash"},
        format="json",
    )

    assert response.json() == {"total": 0, "rows": [], "msg": "OSC 操作失败"}
