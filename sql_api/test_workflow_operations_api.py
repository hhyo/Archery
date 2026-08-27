"""Focused workflow REST API tests.

HTTP integration cases in this module cover URL dispatch and session identity, which
cannot be proven by service-level unit tests.
"""

import pytest
from django.urls import Resolver404, resolve

from sql_api.serializers import (
    WorkflowExecutionSerializer,
    WorkflowTerminationSerializer,
)
from sql_api import api_workflow_operations
from sql_api.api_workflow_operations import mutation_response


@pytest.mark.django_db
def test_mutation_response_uses_workflow_detail_url():
    response = mutation_response(42, "操作成功")

    assert response == {
        "status": 0,
        "msg": "操作成功",
        "data": {"workflow_id": 42, "redirect_url": "/detail/42/"},
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
    workflow = mocker.Mock()
    auditor = mocker.Mock()
    auditor.audit.current_status = api_workflow_operations.WorkflowStatus.PASSED
    auditor.workflow = workflow
    mocker.patch.object(api_workflow_operations, "get_workflow", return_value=workflow)
    get_auditor = mocker.patch.object(
        api_workflow_operations, "get_auditor", return_value=auditor
    )
    mocker.patch.object(api_workflow_operations, "should_notify", return_value=False)
    normal_user.has_perm = mocker.Mock(return_value=True)

    response = authenticated_api_client.post(
        "/api/v1/workflows/17/approval/", {"audit_remark": "同意"}, format="json"
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
        "/api/v1/workflows/17/execution/", {"mode": "invalid"}, format="json"
    )

    assert response.status_code == 400


def test_workflow_operation_routes_replace_legacy_routes():
    assert resolve("/api/v1/workflows/17/status/").kwargs == {"workflow_id": 17}
    with pytest.raises(Resolver404):
        resolve("/getWorkflowStatus/")


@pytest.mark.django_db
def test_terminate_scheduled_workflow_removes_schedule_after_commit(
    authenticated_api_client, normal_user, mocker
):
    normal_user.username = "engineer"
    normal_user.has_perm = mocker.Mock(return_value=False)
    workflow = mocker.Mock(engineer="engineer", status="workflow_timingtask")
    auditor = mocker.Mock()
    auditor.audit = mocker.Mock()
    mocker.patch.object(api_workflow_operations, "get_workflow", return_value=workflow)
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
        "/api/v1/workflows/7/termination/", {"cancel_remark": "取消"}, format="json"
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
    workflow = mocker.Mock()
    audit = mocker.Mock(audit_id=3)
    mocker.patch.object(api_workflow_operations, "can_execute", return_value=True)
    mocker.patch.object(
        api_workflow_operations, "on_correct_time_period", return_value=True
    )
    mocker.patch.object(api_workflow_operations, "get_workflow", return_value=workflow)
    mocker.patch.object(
        api_workflow_operations.Audit, "detail_by_workflow_id", return_value=audit
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
        "/api/v1/workflows/8/execution/", {"mode": "auto"}, format="json"
    )

    assert response.status_code == 200
    assert workflow.status == "workflow_queuing"
    delete_schedule.assert_called_once_with("sqlreview-timing-8")
    queue_task.assert_called_once()


def test_schedule_rejects_past_time_before_side_effects(
    authenticated_api_client, mocker
):
    schedule = mocker.patch.object(api_workflow_operations, "add_sql_schedule")

    response = authenticated_api_client.post(
        "/api/v1/workflows/9/schedule/",
        {"run_date": "2000-01-01 00:00"},
        format="json",
    )

    assert response.status_code == 400
    schedule.assert_not_called()


@pytest.mark.django_db
def test_osc_control_returns_engine_error_in_compatible_envelope(
    authenticated_api_client, mocker
):
    workflow = mocker.Mock()
    mocker.patch.object(api_workflow_operations, "get_workflow", return_value=workflow)
    mocker.patch.object(api_workflow_operations, "ensure_viewable")
    mocker.patch.object(api_workflow_operations, "get_engine").side_effect = (
        RuntimeError("engine failed")
    )

    response = authenticated_api_client.post(
        "/api/v1/workflows/10/osc/",
        {"command": "get", "sqlsha1": "hash"},
        format="json",
    )

    assert response.json() == {"total": 0, "rows": [], "msg": "engine failed"}
