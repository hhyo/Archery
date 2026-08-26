# Quickstart: Workflow Operations REST API Migration

## Prerequisites

- Work on branch `003-migrate-workflow-api`.
- Use the repository virtual environment when present.
- Configure a test database and Django settings as required by the existing pytest setup.

## Implementation Sequence

1. Add request serializers, session-user permission helpers, and `sql_api.services.workflow_operations`.
2. Add `sql_api.api_workflow_operations` DRF views and route them under `/api/v1/workflows/` in `sql_api/urls.py`.
3. Update `detail.html`, `rollback.html`, `sqlworkflow.html`, `audit_sqlworkflow.html`, and `sqlexportworkflow.html` to replace old addresses only. Preserve parameter names and existing response parsing; replace form navigation success with navigation to the supplied `redirect_url`.
4. Delete the ten migrated functions and obsolete imports from `sql/sql_workflow.py`; delete the corresponding legacy route entries from `sql/urls.py`.
5. Add service tests and endpoint contract tests; replace legacy route tests in `sql/tests.py`.

## API Smoke Checks

With an authenticated Django session, verify these paths resolve and the old paths return 404:

```text
POST /api/v1/workflows/
POST /api/v1/workflows/audit-list/
GET  /api/v1/workflows/{workflow_id}/content/
GET  /api/v1/workflows/{workflow_id}/rollback/
PATCH /api/v1/workflows/{workflow_id}/execution-window/
POST /api/v1/workflows/{workflow_id}/approval/
POST /api/v1/workflows/{workflow_id}/execution/
POST /api/v1/workflows/{workflow_id}/schedule/
POST /api/v1/workflows/{workflow_id}/termination/
GET  /api/v1/workflows/{workflow_id}/status/
POST /api/v1/workflows/{workflow_id}/osc/
```

Confirm that `/passed/`, `/execute/`, `/timingtask/`, `/alter_run_date/`, `/cancel/`, `/sqlworkflow_list/`, `/sqlworkflow_list_audit/`, `/sqlworkflow/detail_content/`, `/sqlworkflow/backup_sql/`, `/getWorkflowStatus/`, and `/inception/osc_control/` no longer resolve.

## Focused Validation

```bash
pytest -q sql_api/test_workflow_operations_api.py sql/tests.py
```

The test suite must assert:

- `request.user`, not a request field, is the action actor.
- Invalid authorization, time windows, identifiers and modes leave all state unchanged.
- Auto execution and termination remove a pre-existing schedule after commit.
- Approval, rejection, termination, execution and scheduling create the same audit/log outcomes as before.
- Rollback and OSC still delegate through the configured engine adapter.
- All updated templates contain only the new `/api/v1/workflows/` operation addresses.
- Removed legacy operation URLs return 404; this integration check is necessary because only Django URL resolution can prove removal.