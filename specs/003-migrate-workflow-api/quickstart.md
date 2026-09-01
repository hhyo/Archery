# Quickstart: Migrate Workflow Operations API

## Prerequisites

- Use the project-local Python environment when one exists, such as `.venv/bin/python`.
- Install dependencies only into the project-local environment.
- Ensure the test database and Django settings used by the existing test suite are available.
- Review the API contract in [contracts/workflow-operations.openapi.yaml](./contracts/workflow-operations.openapi.yaml).

## Validation Steps

### 1. Run focused API tests

```bash
pytest sql_api/test_workflow_operations_api.py
```

Expected outcome:

- SQL Workflow submission returns both `audit_id` and `workflow_id`.
- Detail, content, status, log, rollback, execution-window, approval, rejection, cancellation, execution, schedule, and OSC endpoints accept `audit_id`.
- New operation endpoints reject `workflow_id` as an identifier.
- User-facing validation failures do not expose raw exception text.

### 2. Run workflow unit tests

```bash
pytest sql/utils/test_workflow_audit.py sql/utils/tests.py
```

Expected outcome:

- Audit state transitions remain correct.
- Permission checks and execution-window checks remain unchanged.
- Scheduled execution is removed when automatic execution, rejection, or cancellation makes it obsolete.

### 3. Run API regression tests

```bash
pytest sql_api/tests.py
```

Expected outcome:

- Existing API behavior outside this SQL Workflow migration remains intact.
- Offline export behavior that shares SQL Workflow submission remains compatible with returned `audit_id`.

### 4. Manual browser smoke check

Use a development server and an authenticated user with SQL submit/review/execute permissions.

1. Submit a SQL Workflow from the existing SQL Workflow submit page.
2. Confirm the response or redirect path carries enough data for the detail page to resolve `audit_id`.
3. Open the detail page and approve the workflow using the new endpoint.
4. Reject another workflow and confirm the rejection reason appears in audit history.
5. Cancel a scheduled workflow and confirm the matching schedule no longer exists.
6. Execute an approved workflow in manual mode and confirm status and finish time update.
7. For an OSC-capable DDL workflow, open progress and run a supported control command.

Expected outcome:

- All updated frontend actions use `audit_id` routes.
- No active frontend call uses `workflow_id` for the migrated SQL Workflow APIs.
- Errors shown in the UI are stable and sanitized.

## Contract Checks

During implementation, verify these route families exist and are documented:

- `POST /api/v1/sql-workflows/`
- `GET /api/v1/sql-workflows/{audit_id}/`
- `GET /api/v1/sql-workflows/{audit_id}/content/`
- `GET /api/v1/sql-workflows/{audit_id}/logs/`
- `GET /api/v1/sql-workflows/{audit_id}/rollback/`
- `PATCH /api/v1/sql-workflows/{audit_id}/execution-window/`
- `POST /api/v1/sql-workflows/{audit_id}/approval/`
- `POST /api/v1/sql-workflows/{audit_id}/rejection/`
- `POST /api/v1/sql-workflows/{audit_id}/cancellation/`
- `POST /api/v1/sql-workflows/{audit_id}/execution/`
- `POST /api/v1/sql-workflows/{audit_id}/schedule/`
- `GET /api/v1/sql-workflows/{audit_id}/status/`
- `GET /api/v1/sql-workflows/{audit_id}/osc/`
- `POST /api/v1/sql-workflows/{audit_id}/osc/`

## Frontend Consumer Checks

Search for old route or payload usage:

```bash
rg "workflows/.+workflow_id|workflow_id|/workflow/log/" sql/templates sql/static sql_api
```

Expected outcome:

- Remaining `workflow_id` usages are either response display/reference fields, internal server-side resolution, or explicitly out-of-scope legacy APIs.
- Migrated SQL Workflow frontend calls use `audit_id` for route construction and request identity.
