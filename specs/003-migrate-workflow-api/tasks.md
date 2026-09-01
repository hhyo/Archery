# Tasks: Migrate Workflow Operations API

**Input**: Design documents from `/specs/003-migrate-workflow-api/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [workflow-operations.openapi.yaml](contracts/workflow-operations.openapi.yaml), [quickstart.md](quickstart.md)

**Tests**: Required by the specification and constitution. Write pytest unit tests first, reuse shared fixtures from `conftest.py`, and add narrow DRF integration tests only for routing, authentication, request parsing, and persistence boundaries that unit tests cannot prove.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and delivered independently after the shared foundation.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare shared fixtures, module locations, and contract checks for the `audit_id` API migration.

- [X] T001 Create shared pytest fixtures for authenticated users, SQL Workflow rows, WorkflowAudit rows, SqlWorkflowContent rows, permissions, mocked engines, mocked schedules, and mocked notifications in `conftest.py`
- [X] T002 [P] Create or normalize the focused workflow API pytest module with HTTP-boundary rationale comments in `sql_api/test_workflow_operations_api.py`
- [X] T003 [P] Add OpenAPI contract sanity tests that parse `specs/003-migrate-workflow-api/contracts/workflow-operations.openapi.yaml` and assert every path uses `{audit_id}` except submission in `sql_api/test_workflow_operations_api.py`
- [X] T004 [P] Inventory old `workflow_id` SQL Workflow operation consumers in `sql/templates/detail.html`, `sql/templates/sqlworkflow.html`, `sql/templates/audit_sqlworkflow.html`, and `sql/templates/sqlexportsubmit.html`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the shared `audit_id` lookup, sanitized errors, response envelopes, routing prefix, and serializer contracts required by all stories.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Add `audit_id`-centric request and response serializers for mutation envelopes, SQL Workflow detail, remarks, execution, schedule, execution-window, OSC, and log responses in `sql_api/serializers.py`
- [X] T006 Add a shared helper that resolves `WorkflowAudit.audit_id` to SQL-review `WorkflowAudit` plus related `SqlWorkflow` and rejects missing or non-SQL-review audits with sanitized errors in `sql_api/api_workflow_operations.py`
- [X] T007 Add shared helpers for `audit_id` mutation responses that include both `audit_id` and reference-only `workflow_id` plus a frontend redirect URL in `sql_api/api_workflow_operations.py`
- [X] T008 Add shared helpers that log unexpected exceptions with `audit_id`, action name, and username while returning sanitized DRF validation errors in `sql_api/api_workflow_operations.py`
- [X] T009 Add shared post-commit helper usage for notifications, async execution, and schedule add/remove side effects in `sql_api/api_workflow_operations.py`
- [X] T010 Register the new `/api/v1/sql-workflows/` route family and imports in `sql_api/urls.py`
- [X] T011 [P] Add unit tests for `audit_id` lookup success, nonexistent audit, non-SQL-review audit, mutation response shape, and sanitized error behavior in `sql_api/test_workflow_operations_api.py`

**Checkpoint**: Shared `audit_id` API foundation is complete; all story phases can now proceed.

---

## Phase 3: User Story 1 - Manage Workflow Decisions (Priority: P1) MVP

**Goal**: Authorized reviewers can approve or reject SQL workflows, and authorized submitters/cancel operators can cancel SQL workflows, using `audit_id` as the only operation identifier.

**Independent Test**: Use session-authenticated users to approve one pending workflow, reject another pending workflow, and cancel an eligible workflow; verify audit state, SQL Workflow status, logs, notifications, schedule cleanup, and refusal of unauthorized or malformed requests.

### Tests for User Story 1

- [ ] T012 [P] [US1] Add pytest unit tests for final and intermediate approval transitions, audit detail creation, SQL Workflow status updates, and Pass notification eligibility in `sql_api/test_workflow_operations_api.py`
- [ ] T013 [P] [US1] Add pytest unit tests for reviewer rejection with required `reject_remark`, audit/log status, workflow abort status, Cancel notification eligibility, and scheduled-work removal in `sql_api/test_workflow_operations_api.py`
- [ ] T014 [P] [US1] Add pytest unit tests for submitter cancellation with required `cancel_remark`, authorized cancel operator behavior, denied cancellation, and no partial state change on `AuditException` in `sql_api/test_workflow_operations_api.py`
- [ ] T015 [US1] Add DRF integration tests for `POST /api/v1/sql-workflows/{audit_id}/approval/`, `/rejection/`, and `/cancellation/` covering session identity and request parsing in `sql_api/test_workflow_operations_api.py`

### Implementation for User Story 1

- [X] T016 [US1] Implement `POST /api/v1/sql-workflows/{audit_id}/approval/` using the shared `audit_id` resolver, `get_auditor`, `WorkflowAction.PASS`, atomic updates, and sanitized errors in `sql_api/api_workflow_operations.py`
- [X] T017 [US1] Implement `POST /api/v1/sql-workflows/{audit_id}/rejection/` using reviewer authorization, `WorkflowAction.REJECT`, required `reject_remark`, atomic abort status, schedule cleanup, and sanitized errors in `sql_api/api_workflow_operations.py`
- [X] T018 [US1] Implement `POST /api/v1/sql-workflows/{audit_id}/cancellation/` using submitter/cancel authorization, `WorkflowAction.ABORT`, required `cancel_remark`, atomic abort status, schedule cleanup, and sanitized errors in `sql_api/api_workflow_operations.py`
- [X] T019 [US1] Update SQL Workflow detail-page approval, rejection, and cancellation buttons to call `/api/v1/sql-workflows/{{ audit_id }}/.../` endpoints in `sql/templates/detail.html`
- [X] T020 [US1] Ensure SQL Workflow detail rendering exposes the page's `audit_id` for JavaScript route construction without using `workflow_id` as an operation identifier in `sql/views.py` and `sql/templates/detail.html`

**Checkpoint**: Approval, rejection, and cancellation are fully usable through `audit_id` routes with existing audit semantics and frontend controls.

---

## Phase 4: User Story 2 - Execute and Schedule Workflows (Priority: P1)

**Goal**: Authorized executors can queue automatic execution, confirm manual execution, and schedule future execution using `audit_id` as the only operation identifier.

**Independent Test**: With an approved SQL Workflow and authorized executor, test auto execution, manual completion, and scheduling independently; verify state, timestamps, audit logs, async/schedule side effects, and rejection of invalid mode, invalid time, denied permission, or out-of-window requests.

### Tests for User Story 2

- [ ] T021 [P] [US2] Add pytest unit tests for automatic execution state change, execution audit log, schedule removal, async task dispatch after commit, and sanitized async setup failures in `sql_api/test_workflow_operations_api.py`
- [ ] T022 [P] [US2] Add pytest unit tests for manual execution status, finish time, manual audit log, Execute notification eligibility, and no partial state change on validation failure in `sql_api/test_workflow_operations_api.py`
- [ ] T023 [P] [US2] Add parametrized pytest unit tests for schedule creation or replacement, past `run_date`, execution-window violations, invalid `mode`, and executor authorization failures in `sql_api/test_workflow_operations_api.py`
- [ ] T024 [US2] Add DRF integration tests for `POST /api/v1/sql-workflows/{audit_id}/execution/` and `/schedule/` covering JSON/form payload parsing and session-based authorization in `sql_api/test_workflow_operations_api.py`

### Implementation for User Story 2

- [X] T025 [US2] Implement `POST /api/v1/sql-workflows/{audit_id}/execution/` for `mode=auto` with existing `can_execute`, `on_correct_time_period`, `Audit.add_log`, schedule removal, async execution, and sanitized errors in `sql_api/api_workflow_operations.py`
- [X] T026 [US2] Extend `POST /api/v1/sql-workflows/{audit_id}/execution/` for `mode=manual` with finish timestamp, manual log, Execute notification, and sanitized errors in `sql_api/api_workflow_operations.py`
- [X] T027 [US2] Implement `POST /api/v1/sql-workflows/{audit_id}/schedule/` with existing `can_timingtask`, execution-window validation, one matching schedule, and sanitized errors in `sql_api/api_workflow_operations.py`
- [X] T028 [US2] Update automatic execution, manual execution, and timing-task form actions to call `/api/v1/sql-workflows/{{ audit_id }}/execution/` and `/schedule/` in `sql/templates/detail.html`

**Checkpoint**: Automatic execution, manual execution, and scheduling work through `audit_id` routes without changing existing engine or scheduler boundaries.

---

## Phase 5: User Story 3 - Inspect and Adjust Workflow Operations (Priority: P2)

**Goal**: Authorized users can submit SQL workflows, list workflows with returned `audit_id`, read details/content/status/logs/rollback, adjust execution windows, and view/control OSC progress through `audit_id` REST APIs.

**Independent Test**: Use permitted and denied users to call submission, list, detail, content, status, log, rollback, execution-window, and OSC endpoints; verify model-aligned response fields, engine delegation, legacy-result normalization, sanitized errors, and unchanged state after denied or malformed requests.

### Tests for User Story 3

- [ ] T029 [P] [US3] Add pytest unit tests for SQL Workflow submission returning both `audit_id` and reference-only `workflow_id`, including review failure sanitization and automatic audit creation in `sql_api/test_workflow_operations_api.py`
- [ ] T030 [P] [US3] Add pytest unit tests for list and audit-list responses including `audit_id` per row while preserving filtering, paging, search, and visibility rules in `sql_api/test_workflow_operations_api.py`
- [ ] T031 [P] [US3] Add pytest unit tests for detail, content normalization, status, logs, rollback permission, and execution-window update by `audit_id` in `sql_api/test_workflow_operations_api.py`
- [ ] T032 [P] [US3] Add pytest unit tests for OSC progress via GET, OSC control via POST, unsupported OSC commands, engine errors, and sanitized response messages in `sql_api/test_workflow_operations_api.py`
- [ ] T033 [US3] Add DRF integration tests for submission, list, detail, content, logs, rollback, execution-window, status, and OSC route dispatch by `audit_id` in `sql_api/test_workflow_operations_api.py`

### Implementation for User Story 3

- [X] T034 [US3] Implement `POST /api/v1/sql-workflows/` submission using existing `WorkflowContentSerializer` model-aligned payloads and response data containing `audit_id` plus reference-only `workflow_id` in `sql_api/api_workflow.py` and `sql_api/api_workflow_operations.py`
- [X] T035 [US3] Update SQL Workflow list and audit-list APIs to include `audit_id` in each row while preserving existing filter and Bootstrap Table response fields in `sql_api/api_workflow_operations.py`
- [X] T036 [US3] Implement `GET /api/v1/sql-workflows/{audit_id}/` detail response with model-aligned SQL Workflow fields and reference-only `workflow_id` in `sql_api/api_workflow_operations.py`
- [X] T037 [US3] Implement `GET /api/v1/sql-workflows/{audit_id}/content/`, `/status/`, and `/logs/` with view authorization and existing response conventions in `sql_api/api_workflow_operations.py`
- [X] T038 [US3] Implement `GET /api/v1/sql-workflows/{audit_id}/rollback/` with existing rollback permission checks, engine adapter delegation, and sanitized error logging in `sql_api/api_workflow_operations.py`
- [X] T039 [US3] Implement `PATCH /api/v1/sql-workflows/{audit_id}/execution-window/` with reviewer authorization and model field updates in `sql_api/api_workflow_operations.py`
- [X] T040 [US3] Implement `GET /api/v1/sql-workflows/{audit_id}/osc/` for progress and `POST /api/v1/sql-workflows/{audit_id}/osc/` for pause/resume/kill control in `sql_api/api_workflow_operations.py`
- [X] T041 [US3] Update SQL Workflow list page links, log requests, and detail navigation to use returned `audit_id` in `sql/templates/sqlworkflow.html`
- [X] T042 [US3] Update SQL Workflow submit and offline-export submit success handling to preserve returned `audit_id` for detail navigation in `sql/templates/sqlsubmit.html` and `sql/templates/sqlexportsubmit.html`
- [X] T043 [US3] Update detail page content, status polling, logs, rollback, execution-window, and OSC JavaScript calls to use `/api/v1/sql-workflows/{{ audit_id }}/.../` routes in `sql/templates/detail.html`

**Checkpoint**: SQL Workflow submission and all read/control operations expose and consume `audit_id` while preserving model-aligned fields and existing page behavior.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Remove replaced legacy dependencies, validate the contract, and ensure old operation identifiers do not survive in active SQL Workflow API consumers.

- [ ] T044 Remove or deprecate migrated legacy function-based SQL Workflow operation views after all new `audit_id` endpoints cover their behavior in `sql/views.py` and `sql/urls.py`
- [X] T045 Remove migrated old SQL Workflow operation route entries that expose `workflow_id` operation paths from `sql_api/urls.py` after frontend consumers use `/api/v1/sql-workflows/`
- [ ] T046 [P] Update retired endpoint migration notes in `specs/003-migrate-workflow-api/contracts/workflow-operations.openapi.yaml` and `specs/003-migrate-workflow-api/quickstart.md`
- [X] T047 [P] Add repository checks that fail when migrated SQL Workflow frontend calls still build `/api/v1/workflows/<workflow_id>/` operation routes in `sql_api/test_workflow_operations_api.py`
- [X] T048 Run focused validation commands from `specs/003-migrate-workflow-api/quickstart.md` using the project-local Python environment where applicable
- [ ] T049 Run full configured pytest regression suite and fix only regressions caused by the SQL Workflow `audit_id` migration in `sql_api/test_workflow_operations_api.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Starts immediately.
- **Foundational (Phase 2)**: Depends on T001-T004 and blocks all user stories.
- **US1 (Phase 3)**: Depends on T005-T011 and delivers the MVP decision workflow.
- **US2 (Phase 4)**: Depends on T005-T011 and can proceed in parallel with US1 except for shared files.
- **US3 (Phase 5)**: Depends on T005-T011 and can proceed in parallel with US1/US2 except for shared files.
- **Polish (Phase 6)**: Depends on completed selected story phases and all frontend consumer updates.

### User Story Dependencies

- **US1 (P1)**: Independent after the foundation; validates approval, rejection, and cancellation.
- **US2 (P1)**: Independent after the foundation; validates execution and scheduling.
- **US3 (P2)**: Independent after the foundation; validates submission, reads, execution-window updates, rollback, logs, and OSC.

### Within Each User Story

- Tests must be written before implementation tasks in the same story.
- Serializer/helper changes precede API view implementation.
- API view implementation precedes template consumer updates.
- Template updates that touch `sql/templates/detail.html` must be serialized across US1, US2, and US3.

## Parallel Opportunities

- T002, T003, and T004 can run in parallel after T001 begins.
- T005, T006, T007, T008, and T011 can be split, but edits to `sql_api/api_workflow_operations.py` must be coordinated.
- T012-T014 can run in parallel for US1 tests.
- T021-T023 can run in parallel for US2 tests.
- T029-T032 can run in parallel for US3 tests.
- T041 and T042 can run in parallel with API implementation because they touch different templates from `sql_api/api_workflow_operations.py`.
- T046 and T047 can run in parallel after all route decisions are implemented.

## Parallel Example: User Story 1

```text
Task T012: Add approval transition tests in sql_api/test_workflow_operations_api.py
Task T013: Add rejection tests in sql_api/test_workflow_operations_api.py
Task T014: Add cancellation tests in sql_api/test_workflow_operations_api.py
```

## Parallel Example: User Story 2

```text
Task T021: Add auto-execution tests in sql_api/test_workflow_operations_api.py
Task T022: Add manual-execution tests in sql_api/test_workflow_operations_api.py
Task T023: Add schedule validation tests in sql_api/test_workflow_operations_api.py
```

## Parallel Example: User Story 3

```text
Task T029: Add submission tests in sql_api/test_workflow_operations_api.py
Task T030: Add list/audit-list tests in sql_api/test_workflow_operations_api.py
Task T032: Add OSC tests in sql_api/test_workflow_operations_api.py
Task T041: Update sql/templates/sqlworkflow.html to use returned audit_id
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete US1 tests T012-T015 and confirm they fail against the old `workflow_id` contract.
3. Implement US1 tasks T016-T020.
4. Validate approval, rejection, and cancellation independently before execution or inspection work.

### Incremental Delivery

1. Foundation: `audit_id` resolver, serializers, sanitized error helpers, and route family.
2. US1: decision actions and detail-page decision controls.
3. US2: execution and scheduling actions.
4. US3: submission, list/read/control endpoints, and remaining frontend calls.
5. Polish: remove old route dependencies, update docs, run focused and full validation.

### Format Validation

All 49 tasks use the required checklist format: checkbox, sequential task ID, optional `[P]` only for parallel work, `[US#]` on every user-story task, and exact repository file paths.
