# Tasks: Workflow Operations REST API Migration

**Input**: Design documents from `/specs/003-migrate-workflow-api/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [workflow-operations.openapi.yaml](contracts/workflow-operations.openapi.yaml), [quickstart.md](quickstart.md)

**Tests**: pytest unit tests are required for service behavior. Narrow DRF integration tests are required only for session authentication, URL dispatch, payload parsing, and verifying removed routes return 404; each such test must state that the Django/DRF boundary cannot be proven by a unit test.

**Organization**: Tasks are grouped by user story so each slice can be implemented, validated, and delivered independently after the shared foundation.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare reusable test support and the dedicated workflow operation module layout.

- [ ] T001 Create reusable authenticated API-client, workflow-audit, and mocked engine/schedule/notification fixtures in `conftest.py`
- [ ] T002 Create the dedicated workflow operation API module in `sql_api/api_workflow_operations.py`
- [ ] T003 [P] Create the focused pytest module skeleton with documented HTTP-boundary rationale in `sql_api/test_workflow_operations_api.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish common request validation, response construction, session authentication, atomic orchestration primitives, and versioned routing that all workflow operation stories require.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T004 Add workflow ID, list-filter, mutation, schedule, execution-window, and OSC request serializers that retain legacy field names in `sql_api/serializers.py`
- [ ] T005 Add an authenticated workflow-page permission class that derives authority solely from `request.user` in `sql_api/permissions.py`
- [ ] T006 Implement shared workflow lookup, compatible response-envelope builders, post-commit side-effect helpers, and mutation result construction in `sql_api/api_workflow_operations.py`
- [ ] T007 Create authenticated DRF APIView base classes that validate path workflow IDs and map domain validation/permission failures to structured 4xx responses in `sql_api/api_workflow_operations.py`
- [ ] T008 Register the `/api/v1/workflows/` API prefix and common view imports in `sql_api/urls.py`
- [ ] T009 [P] Add unit tests for common serializer validation, session-user-only actor selection, compatible response helpers, and deferred side effects in `sql_api/test_workflow_operations_api.py`

**Checkpoint**: Shared API foundation is complete; all story phases can now proceed.

---

## Phase 3: User Story 1 - Manage Workflow Decisions (Priority: P1) 🎯 MVP

**Goal**: Authorized reviewers can approve and authorized submitters/reviewers can terminate workflows through REST endpoints, retaining audit, status, notification, and scheduled-work semantics.

**Independent Test**: Use a session-authenticated reviewer to approve a pending workflow and a permitted submitter/reviewer to terminate eligible workflows; assert audit action, status, notification eligibility, and removal of a pre-existing timing schedule without exercising execution endpoints.

### Tests for User Story 1

- [ ] T010 [P] [US1] Add service unit tests for final approval status transition, audit detail creation, and Pass notification eligibility in `sql_api/test_workflow_operations_api.py`
- [ ] T011 [P] [US1] Add service unit tests for submitter abort, reviewer reject, missing cancellation reason, denied cancellation, and scheduled-work removal after commit in `sql_api/test_workflow_operations_api.py`
- [ ] T012 [US1] Add API integration tests for session-authenticated approval and termination payloads, including the rationale that DRF dispatch/session identity cannot be proven by service unit tests, in `sql_api/test_workflow_operations_api.py`

### Implementation for User Story 1

- [ ] T013 [US1] Implement transactional approval and termination service functions using `request.user`, `get_auditor`, `WorkflowAction`, and post-commit notification/schedule side effects in `sql_api/services/workflow_operations.py`
- [ ] T014 [US1] Implement approval and termination API views returning the compatible mutation envelope in `sql_api/api_workflow_operations.py`
- [ ] T015 [US1] Register `POST /api/v1/workflows/<workflow_id>/approval/` and `POST /api/v1/workflows/<workflow_id>/termination/` in `sql_api/urls.py`
- [ ] T016 [US1] Replace the approval and cancellation form actions with their new `/api/v1/workflows/<workflow_id>/.../` addresses and handle mutation success by navigating to `redirect_url` in `sql/templates/detail.html`

**Checkpoint**: Approval, abort, and rejection work through the new REST paths with the original authorization, audit, schedule cleanup, and notification behavior.

---

## Phase 4: User Story 2 - Execute and Schedule Workflows (Priority: P1)

**Goal**: Authorized executors can queue automatic execution, confirm manual execution, and create or replace future schedules through REST APIs with correct audit and schedule lifecycle behavior.

**Independent Test**: With an authorized executor and an approved workflow, test auto, manual, and schedule modes independently; verify status, timestamps, logs, deferred queue/schedule work, and rejection of invalid time/mode/permission cases.

### Tests for User Story 2

- [ ] T017 [P] [US2] Add service unit tests for automatic and manual execution state changes, audit logs, Execute notification eligibility, and removal of an existing schedule after commit in `sql_api/test_workflow_operations_api.py`
- [ ] T018 [P] [US2] Add parametrized service unit tests for schedule creation/replacement, past timestamps, execution-window violations, invalid modes, and executor authorization failures in `sql_api/test_workflow_operations_api.py`
- [ ] T019 [US2] Add API integration tests for execution and schedule endpoints with the rationale that HTTP method/payload parsing and session dispatch require DRF integration coverage in `sql_api/test_workflow_operations_api.py`

### Implementation for User Story 2

- [ ] T020 [US2] Implement transactional automatic execution, manual completion, and schedule replacement services using existing permission helpers, `Audit.add_log`, and post-commit django-q work in `sql_api/services/workflow_operations.py`
- [ ] T021 [US2] Implement execution and scheduling API views that accept legacy `mode` and `run_date` fields and return compatible mutation envelopes in `sql_api/api_workflow_operations.py`
- [ ] T022 [US2] Register `POST /api/v1/workflows/<workflow_id>/execution/` and `POST /api/v1/workflows/<workflow_id>/schedule/` in `sql_api/urls.py`
- [ ] T023 [US2] Replace automatic execution, manual execution, and timing-task form actions with the new API paths and redirect-on-success behavior in `sql/templates/detail.html`

**Checkpoint**: Automatic, manual, and scheduled execution are independently usable through the new REST API with consistent logs, state, timing validation, and task lifecycle.

---

## Phase 5: User Story 3 - Inspect and Adjust Workflow Operations (Priority: P2)

**Goal**: Authorized users can list, inspect, retrieve rollback data, adjust execution windows, inspect status, and control OSC execution through compatible REST responses.

**Independent Test**: Use permitted and denied session users to call list, content, rollback, window, status, and OSC endpoints; verify legacy response envelopes, engine delegation, and unchanged state after denied or malformed requests.

### Tests for User Story 3

- [ ] T024 [P] [US3] Add service unit tests for visibility-filtered list results, legacy content-row normalization, rollback permission, execution-window update authorization, status visibility, and OSC engine delegation in `sql_api/test_workflow_operations_api.py`
- [ ] T025 [US3] Add API integration tests for Bootstrap Table list envelopes, compatible detail/rollback/status/OSC responses, and authenticated routing with the rationale that URL dispatch and form/query parsing require DRF integration coverage in `sql_api/test_workflow_operations_api.py`

### Implementation for User Story 3

- [ ] T026 [US3] Implement list filtering/pagination, detail-content normalization, rollback retrieval, execution-window update, status lookup, and OSC-control services using existing permission helpers and engine adapters in `sql_api/services/workflow_operations.py`
- [ ] T027 [US3] Implement list, audit-list, content, rollback, execution-window, status, and OSC API views with legacy-compatible response envelopes in `sql_api/api_workflow_operations.py`
- [ ] T028 [US3] Register list, audit-list, content, rollback, execution-window, status, and OSC paths under `/api/v1/workflows/` in `sql_api/urls.py`
- [ ] T029 [P] [US3] Replace workflow list request URLs only in `sql/templates/sqlworkflow.html`, `sql/templates/audit_sqlworkflow.html`, and `sql/templates/sqlexportworkflow.html`
- [ ] T030 [US3] Replace content, OSC, execution-window, status, and rollback request URLs only while preserving existing payloads and response parsing in `sql/templates/detail.html` and `sql/templates/rollback.html`

**Checkpoint**: All remaining read/control operations use the unified REST prefix, preserve existing page data handling, and continue to respect visibility and engine boundaries.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Remove replaced legacy code, validate the public contract, and ensure no route or template still depends on old operation URLs.

- [ ] T031 Remove migrated function-based workflow operation views and obsolete imports from `sql/sql_workflow.py`
- [ ] T032 Remove all migrated legacy operation route entries and the `sql_workflow` import dependency from `sql/urls.py`
- [ ] T033 Replace legacy workflow URL tests with REST contract, old-route-404, and URL-only frontend reference checks in `sql/tests.py`
- [ ] T034 [P] Update retired URL and client migration guidance in `specs/003-migrate-workflow-api/contracts/workflow-operations.openapi.yaml` and `specs/003-migrate-workflow-api/quickstart.md`
- [ ] T035 Run the focused pytest validation from `sql_api/test_workflow_operations_api.py` and `sql/tests.py`
- [ ] T036 Run the full configured pytest suite and resolve only regressions caused by this migration in `pyproject.toml`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Starts immediately.
- **Foundational (Phase 2)**: Depends on T001-T003 and blocks all user stories.
- **US1 (Phase 3)**: Depends on T004-T009; provides the MVP workflow decision slice.
- **US2 (Phase 4)**: Depends on T004-T009; may be developed in parallel with US1, but its `detail.html` work must be sequenced with T016 to avoid file conflicts.
- **US3 (Phase 5)**: Depends on T004-T009; may be developed in parallel with US1/US2, but T030 must be sequenced after T016 and T023 because all change `detail.html`.
- **Polish (Phase 6)**: Depends on all selected user story phases and their endpoint/template updates.

### User Story Dependencies

- **US1 (P1)**: Independent after the foundation; it does not require execution or inspection endpoints.
- **US2 (P1)**: Independent after the foundation; it reuses only shared service/serializer primitives.
- **US3 (P2)**: Independent after the foundation; it reuses only shared service/serializer primitives.

### Parallel Opportunities

- T001, T002, and T003 can proceed together.
- T004, T005, and T009 can proceed in parallel once the corresponding module locations exist; T006-T008 follow their required shared interfaces.
- After Phase 2, T010-T012, T017-T019, and T024-T025 can be assigned to separate developers.
- T013-T015, T020-T022, and T026-T028 can proceed in parallel by story; serialize edits to `sql_api/urls.py`, `sql_api/api_workflow_operations.py`, `sql_api/services/workflow_operations.py`, and `sql_api/test_workflow_operations_api.py` when they overlap.
- T029 is parallel with service/view work because it touches only three list templates.
- T031-T034 can proceed in parallel after all API and frontend migration tasks complete.

## Parallel Examples

### User Story 1

```text
Task T010: Unit tests for approval behavior in sql_api/test_workflow_operations_api.py
Task T011: Unit tests for termination behavior in sql_api/test_workflow_operations_api.py
```

### User Story 2

```text
Task T017: Unit tests for automatic/manual execution in sql_api/test_workflow_operations_api.py
Task T018: Parametrized tests for scheduling and invalid execution cases in sql_api/test_workflow_operations_api.py
```

### User Story 3

```text
Task T024: Unit tests for retrieval/control service behaviors in sql_api/test_workflow_operations_api.py
Task T029: URL-only list-template replacements in sql/templates/sqlworkflow.html, sql/templates/audit_sqlworkflow.html, and sql/templates/sqlexportworkflow.html
```

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Setup and Foundational phases.
2. Implement and validate US1 through approval and termination endpoints.
3. Verify audit, notification eligibility, and scheduled-work removal independently.
4. Demonstrate only `/api/v1/workflows/<workflow_id>/approval/` and `/api/v1/workflows/<workflow_id>/termination/` before adding execution or inspection behavior.

### Incremental Delivery

1. Complete the shared foundation.
2. Add US1 and validate decisions.
3. Add US2 and validate execution/scheduling without changing US1 behavior.
4. Add US3 and validate reading/control behavior plus URL-only template replacement.
5. Remove legacy views/routes and run focused then full regression validation.

### Format Validation

All 36 tasks use the required checklist format: checkbox, sequential task ID, optional `[P]` only for parallel work, `[US#]` on every user-story task, and exact repository file paths.