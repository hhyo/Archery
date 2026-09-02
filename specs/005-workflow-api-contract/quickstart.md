# Quickstart: Workflow API Contract Completeness

## Prerequisites

- Use the project-local Python environment if present, for example `.venv/bin/python`.
- Database test fixtures include at least one user, one resource group, one instance tagged `can_write`, one instance tagged `can_read`, one inaccessible instance, one SQL workflow, workflow content, workflow audit, and workflow logs.
- API authentication is available through the existing DRF/session or token test helpers.

## Validation Commands

Run the focused API tests:

```bash
pytest sql_api/test_api_instance.py sql_api/test_workflow_operations_api.py
```

Regenerate or inspect the OpenAPI schema using the project's existing schema tooling and confirm it includes the contracts in [contracts/workflow-api-contract.openapi.yaml](./contracts/workflow-api-contract.openapi.yaml).

## Scenario 1: Authorized Instance Detail

1. Authenticate as a normal user whose resource group includes the target instance with `can_write`.
2. Request `GET /api/v1/instance/{id}/`.
3. Confirm the response includes `id`, `instance_name`, `db_type`, and `type`.
4. Confirm the response excludes host, port, username, password, tunnel credentials, access keys, and administrator-only configuration.
5. Repeat with a user whose resource group includes the target instance with `can_read`; the request should also succeed.

## Scenario 2: Unauthorized Instance Detail

1. Authenticate as a normal user without `can_write` or `can_read` access to the target instance.
2. Request `GET /api/v1/instance/{id}/`.
3. Confirm the response is denied with a sanitized deterministic error.
4. Confirm no sensitive instance fields appear in the error response.

## Scenario 3: Existing SQL Workflow Detail By Audit ID

1. Authenticate as a user who can view an existing workflow.
2. Request `GET /api/v1/sql-workflows/{audit_id}/`.
3. Confirm the response describes exactly that workflow and includes `workflow.instance` as the numeric instance id.
4. Confirm a missing or inaccessible audit id returns a sanitized not-found or permission-denied response.

## Scenario 4: No Duplicate Workflow Detail Endpoint

1. Inspect the generated API contract.
2. Confirm this feature documents single SQL Workflow lookup through `GET /api/v1/sql-workflows/{audit_id}/`.
3. Confirm this feature does not add a new `GET /api/v1/workflow/{id}/` retrieve operation.

## Scenario 5: Extension Data Preservation

1. Prepare workflow, workflow content, and workflow log responses with additional nested fields beyond the documented core fields.
2. Parse responses with generated-client models.
3. Confirm core fields keep their documented types.
4. Confirm additional nested fields remain available for CLI structured review JSON.

## Scenario 6: Logs And Status Schema

1. Inspect generated OpenAPI for `GET /api/v1/sql-workflows/{audit_id}/logs/`.
2. Confirm it documents a response body with `total` and `rows`.
3. Confirm each log row documents `operation_type_desc`, `operation_info`, `operator_display`, `operation_time`, and the extension strategy.
4. Inspect generated OpenAPI for `GET /api/v1/sql-workflows/{audit_id}/status/`.
5. Confirm it documents a response body with workflow status code in `status`.

## Scenario 7: Approval And Execution Schema

1. Inspect generated OpenAPI for `POST /api/v1/sql-workflows/{audit_id}/approval/`.
2. Confirm it documents optional `audit_remark` and the standard action result response.
3. Inspect generated OpenAPI for `POST /api/v1/sql-workflows/{audit_id}/execution/`.
4. Confirm it documents required `mode` with `auto` and `manual` choices and the standard action result response.
5. Confirm neither audit-id endpoint documents `engineer` as a request field.

## Integration Test Rationale

Use integration tests only for REST authentication, URL dispatch, HTTP status mapping, and response rendering. Permission helper decisions, serializer allowlists, workflow instance id mapping, and runtime serializer shapes should be covered by unit tests; generated schema checks may be run with temporary scripts when needed.
