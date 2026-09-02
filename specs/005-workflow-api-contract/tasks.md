# Tasks: Workflow API Contract Completeness

**Input**: Design documents from `/specs/005-workflow-api-contract/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Pytest unit-test-first is required by the feature specification and constitution. Integration tests are limited to REST authentication, URL dispatch, response rendering, and generated OpenAPI schema boundaries.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm current API surface, local test entrypoints, and schema generation baseline before changing behavior.

- [X] T001 Inspect current instance, workflow, and SQL Workflow API routes in `sql_api/urls.py` and record any route-name changes needed in `specs/005-workflow-api-contract/quickstart.md`
- [X] T002 [P] Inspect current instance/workflow serializers in `sql_api/serializers.py` for sensitive instance fields and existing SQL Workflow request/response serializers
- [X] T003 [P] Inspect current SQL Workflow operation views in `sql_api/api_workflow_operations.py` for missing `extend_schema` request/response annotations on logs, status, approval, and execution

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared serializers/helpers that all stories rely on before touching endpoint behavior.

**CRITICAL**: No user story work should begin until this phase is complete.

- [X] T004 Add `PublicInstanceSerializer` with an explicit read-only field allowlist in `sql_api/serializers.py`
- [X] T005 Add `can_read_public_instance(user, instance)` helper using `user_instances(user, tag_codes=["can_write"])` or `user_instances(user, tag_codes=["can_read"])` in `sql_api/api_instance.py`
- [X] T006 Add response serializers for SQL Workflow status and action result bodies in `sql_api/serializers.py`
- [X] T007 Add schema serializers for SQL Workflow content/log responses in `sql_api/serializers.py`

**Checkpoint**: Shared serializer and permission primitives are ready for independently testable stories.

---

## Phase 3: User Story 1 - Preserve CLI Review Text From Workflow Results (Priority: P1) MVP

**Goal**: Authorized CLI/generated-client users can retrieve safe instance display metadata for workflow review text.

**Independent Test**: Given a workflow response containing an instance id, an authenticated user with `can_write` or `can_read` access can retrieve instance name, db type, and role/type; unauthorized users cannot retrieve details; sensitive fields are never returned.

### Tests for User Story 1 (unit tests first)

- [X] T008 [P] [US1] Add pytest fixtures for public instance detail users, resource groups, `can_write`, `can_read`, and inaccessible instances in `conftest.py`
- [X] T009 [P] [US1] Add unit tests for `can_read_public_instance` covering `can_write`, `can_read`, superuser/all-instance access, and denied users in `sql_api/test_api_instance.py`
- [X] T010 [P] [US1] Add serializer allowlist tests asserting `PublicInstanceSerializer` includes `id`, `instance_name`, `db_type`, `type` and excludes account/password/secret/internal fields in `sql_api/test_api_instance.py`
- [X] T011 [US1] Add HTTP integration tests for `GET /api/v1/instance/{id}/` authenticated success, unauthenticated denial, unauthorized denial, and missing id in `sql_api/test_api_instance.py`

### Implementation for User Story 1

- [X] T012 [US1] Add `permission_classes = [permissions.IsAuthenticated]` to `InstanceDetail` and implement `get` using `PublicInstanceSerializer` in `sql_api/api_instance.py`
- [X] T013 [US1] Enforce public instance detail permission with `can_read_public_instance` and sanitized `PermissionDenied`/`NotFound` responses in `sql_api/api_instance.py`
- [X] T014 [US1] Add `extend_schema` for `GET /api/v1/instance/{id}/` with `PublicInstanceSerializer` response and 401/403/404 cases in `sql_api/api_instance.py`
- [X] T015 [US1] Verify existing `PUT` and `DELETE /api/v1/instance/{id}/` administrator/configuration behavior remains unchanged in `sql_api/api_instance.py` and `sql_api/test_api_instance.py`

**Checkpoint**: User Story 1 is complete when instance detail can power CLI review text without leaking sensitive fields.

---

## Phase 4: User Story 2 - Use Existing SQL Workflow Detail Contract (Priority: P1)

**Goal**: Clients use the existing SQL Workflow detail endpoint for one workflow, and workflow responses consistently document `workflow.instance` as an instance id.

**Independent Test**: Given a known `audit_id`, `GET /api/v1/sql-workflows/{audit_id}/` returns the requested workflow and `instance` is the numeric instance id; no duplicate `GET /api/v1/workflow/{id}/` retrieve is introduced.

### Tests for User Story 2 (unit tests first)

- [X] T016 [P] [US2] Add serializer tests asserting `SqlWorkflowDetailSerializer` returns `instance` as the numeric `Instance.id` in `sql_api/test_workflow_operations_api.py`
- [X] T017 [P] [US2] Validate with a temporary schema-generation script that `/api/v1/sql-workflows/{audit_id}/` response documents `instance` as an integer id
- [X] T018 [US2] Confirm with a temporary schema-generation script that no new `GET /api/v1/workflow/{id}/` retrieve operation is introduced

### Implementation for User Story 2

- [X] T019 [US2] Update `SqlWorkflowDetailSerializer` schema metadata so `instance` is documented as an integer instance id in `sql_api/serializers.py`
- [X] T020 [US2] Ensure `WorkflowListView` and `WorkflowDetailView` OpenAPI annotations use the same workflow detail schema semantics for `instance` in `sql_api/api_workflow_operations.py`
- [X] T021 [US2] Confirm `sql_api/urls.py` continues routing single SQL Workflow retrieval through `v1/sql-workflows/<int:audit_id>/` only

**Checkpoint**: User Story 2 is complete when generated clients can resolve instance ids from existing SQL Workflow detail without relying on workflow list scanning or duplicate endpoints.

---

## Phase 5: User Story 3 - Keep Structured Workflow JSON Extensible (Priority: P2)

**Goal**: Workflow log/content/workflow responses document their extension strategy and generated OpenAPI includes logs, status, approval, and execution body schemas.

**Independent Test**: Generated OpenAPI shows response bodies for logs and status, request/response bodies for approval and execution, `mode` is required for execution, `engineer` is absent from audit-id action requests, and extension strategy is documented for structured review JSON.

### Tests for User Story 3 (unit tests first)

- [X] T022 [P] [US3] Add serializer tests for `WorkflowLogList` rows with `operation_type_desc`, `operation_info`, `operator_display`, and `operation_time` in `sql_api/test_workflow_operations_api.py`
- [X] T023 [P] [US3] Add serializer/schema tests for `WorkflowStatus` response containing workflow status code in `status` in `sql_api/test_workflow_operations_api.py`
- [X] T024 [P] [US3] Add serializer/schema tests for `WorkflowApprovalRequest` allowing optional `audit_remark` and excluding `engineer` in `sql_api/test_workflow_operations_api.py`
- [X] T025 [P] [US3] Add serializer/schema tests for `WorkflowExecutionRequest` requiring `mode` with `auto`/`manual` and excluding `engineer` in `sql_api/test_workflow_operations_api.py`
- [X] T026 [US3] Validate with a temporary schema-generation script that logs/status response bodies and approval/execution request/response bodies are present in generated schema

### Implementation for User Story 3

- [X] T027 [US3] Add `extend_schema` request/response annotations for `WorkflowLogView.get` using the log list response schema in `sql_api/api_workflow_operations.py`
- [X] T028 [US3] Add `extend_schema` response annotation for `WorkflowStatusView.get` using the workflow status response schema in `sql_api/api_workflow_operations.py`
- [X] T029 [US3] Add `extend_schema` request/response annotations for `WorkflowApprovalView.post` using approval request and action result schemas in `sql_api/api_workflow_operations.py`
- [X] T030 [US3] Add `extend_schema` request/response annotations for `WorkflowExecutionView.post` using execution request and action result schemas in `sql_api/api_workflow_operations.py`
- [X] T031 [US3] Keep workflow, workflow content, and workflow log response serializers on DRF native serializer behavior while documenting extension strategy in the contract

**Checkpoint**: User Story 3 is complete when generated clients no longer see `No response body` or path-only contracts for the covered SQL Workflow endpoints.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the full contract and keep documentation aligned with implementation.

- [X] T032 [P] Update `specs/005-workflow-api-contract/contracts/workflow-api-contract.openapi.yaml` if implementation names or response shapes differ from the planned contract
- [X] T033 [P] Update `specs/005-workflow-api-contract/quickstart.md` with final validation commands and any narrowed field allowlist decisions
- [X] T034 Run `.venv/bin/python` or the project-local Python to validate generated OpenAPI schema and compare key paths against `specs/005-workflow-api-contract/contracts/workflow-api-contract.openapi.yaml`
- [X] T035 Run focused pytest validation for `sql_api/test_api_instance.py` and `sql_api/test_workflow_operations_api.py`
- [X] T036 Run broader impacted API tests if focused tests pass, including `sql_api/test_sqlquery_api.py` if instance permission helpers are touched

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; recommended MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational; can run in parallel with US1 after shared serializers are ready.
- **User Story 3 (Phase 5)**: Depends on Foundational; can run in parallel with US2 after shared response serializers exist.
- **Polish (Phase 6)**: Depends on all selected user stories.

### User Story Dependencies

- **US1**: Independent after Foundation; delivers instance metadata needed by CLI review text.
- **US2**: Independent after Foundation; verifies existing SQL Workflow detail and instance id contract.
- **US3**: Independent after Foundation; complements US2 with missing schema bodies and extension strategy.

### Within Each User Story

- Tests should be written first and fail before implementation.
- Serializer/permission helpers should be completed before endpoint annotations that reference them.
- Integration tests should be added only for REST dispatch, auth/status mapping, response rendering, and generated schema boundaries.

## Parallel Opportunities

- T002 and T003 can run in parallel during setup.
- T008, T009, and T010 can run in parallel for US1 because they touch fixtures, permission tests, and serializer tests.
- T016 and T017 can run in parallel for US2 because they validate runtime serializer behavior and generated schema behavior.
- T022, T023, T024, and T025 can run in parallel for US3 because each targets a distinct response/request schema.
- T032 and T033 can run in parallel during polish after implementation is stable.

## Parallel Example: User Story 1

```bash
Task: "Add pytest fixtures for public instance detail users, resource groups, can_write, can_read, and inaccessible instances in conftest.py"
Task: "Add unit tests for can_read_public_instance covering can_write, can_read, superuser/all-instance access, and denied users in sql_api/test_api_instance.py"
Task: "Add serializer allowlist tests asserting PublicInstanceSerializer includes id, instance_name, db_type, type and excludes account/password/secret/internal fields in sql_api/test_api_instance.py"
```

## Parallel Example: User Story 3

```bash
Task: "Add serializer tests for WorkflowLogList rows with operation_type_desc, operation_info, operator_display, and operation_time in sql_api/test_workflow_operations_api.py"
Task: "Add serializer/schema tests for WorkflowStatus response containing workflow status code in status in sql_api/test_workflow_operations_api.py"
Task: "Add serializer/schema tests for WorkflowApprovalRequest allowing optional audit_remark and excluding engineer in sql_api/test_workflow_operations_api.py"
Task: "Add serializer/schema tests for WorkflowExecutionRequest requiring mode with auto/manual and excluding engineer in sql_api/test_workflow_operations_api.py"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup and Phase 2 foundational serializers/helpers.
2. Complete Phase 3 to expose safe instance detail for users with `can_write` or `can_read`.
3. Validate US1 independently with focused pytest tests and manual schema inspection.

### Incremental Delivery

1. Deliver US1 so CLI review text can resolve instance metadata safely.
2. Deliver US2 so clients use existing SQL Workflow detail with stable `workflow.instance` id semantics.
3. Deliver US3 so generated clients receive complete logs/status/action schemas and a documented extension strategy.
4. Run polish validation and compare generated schema against the planned contract.

### Notes

- Do not add `GET /api/v1/workflow/{id}/` retrieve in this feature.
- Do not document or accept `engineer` in audit-id approval/execution requests.
- Keep public instance fields allowlisted; do not reuse all-field instance configuration serializers for user-facing reads.
- Preserve existing `PUT` and `DELETE /api/v1/instance/{id}/` behavior unless a failing test proves route-level permission leakage.
