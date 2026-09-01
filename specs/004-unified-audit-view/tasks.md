# Tasks: Unified Audit Work Order View

**Input**: Design documents from `/specs/004-unified-audit-view/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/unified-workflow-view.md, quickstart.md

**Tests**: The feature specification and plan require pytest coverage for the new unified view behavior. Do not add new tests for legacy detail views that are expected to be removed later; update existing redirect tests to assert direct rendering through `/workflow/<audit_id>/`.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the active feature context and identify existing web detail/list surfaces before changing behavior.

- [X] T001 Verify `.specify/feature.json` points to `specs/004-unified-audit-view` and record any mismatch in specs/004-unified-audit-view/tasks.md
- [X] T002 [P] Review current unified redirect logic in sql/views.py for `workflowsdetail`
- [X] T003 [P] Review legacy detail URL declarations in sql/urls.py for `/detail/<workflow_id>/`, `/queryapplydetail/<apply_id>/`, `/archive/<id>/`, and `/workflow/<audit_id>/`
- [X] T004 [P] Review list title link generation in sql/templates/sqlworkflow.html, sql/templates/sqlexportworkflow.html, sql/templates/queryapplylist.html, and sql/templates/archive.html
- [X] T005 [P] Review existing view tests in sql/tests.py, sql/test_query_privileges.py, and sql/test_archiver.py to identify tests that should be updated toward `/workflow/<audit_id>/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create reusable web rendering structure so user stories can reuse existing behavior without duplicating detail-page logic.

**CRITICAL**: No user story implementation should begin until this phase is complete.

- [X] T006 Extract SQL Workflow detail context construction from `detail` into a reusable helper in sql/views.py without changing `/detail/<workflow_id>/` behavior
- [X] T007 Extract query privilege detail context construction from `queryapplydetail` into a reusable helper in sql/views.py without changing `/queryapplydetail/<apply_id>/` behavior
- [X] T008 Extract archive detail context construction from `archive_detail` into a reusable helper in sql/views.py without changing `/archive/<id>/` behavior
- [X] T009 Add safe unsupported-audit-type handling for unified detail resolution in sql/views.py
- [X] T010 Confirm legacy detail views in sql/views.py still call the extracted helpers and render their existing templates directly

**Checkpoint**: Shared context helpers are ready; legacy routes still render as before.

---

## Phase 3: User Story 1 - Open Any Work Order by Audit ID (Priority: P1) MVP

**Goal**: `/workflow/<audit_id>/` opens supported SQL Workflow, query privilege, archive, and offline download work orders directly, with no redirect.

**Independent Test**: For each supported work order type, an authorized user opens `/workflow/<audit_id>/` and receives the correct detail template and context without relying on the legacy business ID in the URL.

### Tests for User Story 1

- [X] T011 [US1] Update `test_workflowsdetail` in sql/tests.py to assert `/workflow/<query_audit_id>/` returns 200 and renders `queryapplydetail.html` instead of redirecting
- [X] T012 [P] [US1] Add SQL Workflow direct-render coverage for `/workflow/<sql_audit_id>/` in sql/tests.py using existing SQL Workflow fixtures and asserting `detail.html`
- [X] T013 [P] [US1] Add archive direct-render coverage for `/workflow/<archive_audit_id>/` in sql/test_archiver.py using existing archive fixtures and asserting `archivedetail.html`
- [X] T014 [P] [US1] Add offline download direct-render coverage for `/workflow/<offline_export_audit_id>/` in sql/tests.py or sql/test_offlinedownload.py by asserting the SQL Workflow detail branch renders `detail.html`

### Implementation for User Story 1

- [X] T015 [US1] Replace redirect branches in `workflowsdetail` with direct `render` calls for `WorkflowType.QUERY`, `WorkflowType.SQL_REVIEW`, and `WorkflowType.ARCHIVE` in sql/views.py
- [X] T016 [US1] Ensure the SQL Workflow branch in sql/views.py resolves `audit_id` to `WorkflowAudit.workflow_id` internally and passes the resolved audit ID into `detail.html`
- [X] T017 [US1] Ensure the query privilege branch in sql/views.py resolves `audit_id` to `WorkflowAudit.workflow_id` internally and renders `queryapplydetail.html`
- [X] T018 [US1] Ensure the archive branch in sql/views.py resolves `audit_id` to `WorkflowAudit.workflow_id` internally and renders `archivedetail.html`
- [X] T019 [US1] Ensure SQL offline download audit records render through the SQL Workflow branch in sql/views.py without adding a new workflow type
- [X] T020 [US1] Run the US1 focused tests with `.venv/bin/python -m pytest sql/tests.py sql/test_archiver.py sql/test_offlinedownload.py -k "workflowsdetail or unified or offline"` and record any unavailable local environment blocker in specs/004-unified-audit-view/tasks.md

**Checkpoint**: User Story 1 is independently functional as the MVP.

---

## Phase 4: User Story 2 - Understand Type-Specific State and Actions in One Place (Priority: P1)

**Goal**: The unified view preserves type-specific fields, permissions, state, and actions while keeping shared audit context consistent.

**Independent Test**: Representative work orders across all supported types render the same template context values and permission-driven actions as their legacy direct detail pages.

### Tests for User Story 2

- [X] T021 [P] [US2] Add or update SQL Workflow context assertions for `/workflow/<sql_audit_id>/` in sql/tests.py covering `workflow_detail`, `audit_id`, `review_info`, and action flags
- [X] T022 [P] [US2] Add or update query privilege context assertions for `/workflow/<query_audit_id>/` in sql/tests.py covering `workflow_detail`, `review_info`, `last_operation_info`, and `is_can_review`
- [X] T023 [P] [US2] Add or update archive context assertions for `/workflow/<archive_audit_id>/` in sql/test_archiver.py covering `archive_config`, `review_info`, `last_operation_info`, and `can_review`
- [X] T024 [P] [US2] Add invalid or nonexistent audit ID coverage for `/workflow/<audit_id>/` in sql/tests.py asserting safe not-found behavior

### Implementation for User Story 2

- [X] T025 [US2] Preserve SQL Workflow permission denial and autoreview-wrong context behavior when rendered through `/workflow/<audit_id>/` in sql/views.py
- [X] T026 [US2] Preserve query privilege reviewer resolution and last-operation behavior when rendered through `/workflow/<audit_id>/` in sql/views.py
- [X] T027 [US2] Preserve archive reviewer resolution and can-review behavior when rendered through `/workflow/<audit_id>/` in sql/views.py
- [X] T028 [US2] Ensure unsupported or missing audit records in sql/views.py return safe not-found behavior without exposing unrelated work order data
- [X] T029 [US2] Run the US2 focused tests with `.venv/bin/python -m pytest sql/tests.py sql/test_archiver.py -k "workflow or context or audit"` and record any unavailable local environment blocker in specs/004-unified-audit-view/tasks.md

**Checkpoint**: User Stories 1 and 2 both work independently through the unified detail entry.

---

## Phase 5: User Story 3 - Follow Existing Links Without Disruption (Priority: P2)

**Goal**: Normal list navigation points at `/workflow/<audit_id>/`, while legacy detail URLs remain usable.

**Independent Test**: Users can navigate from SQL Workflow, SQL export/offline download, query privilege, and archive lists to `/workflow/<audit_id>/`; existing direct legacy detail URLs still return their previous pages.

### Tests for User Story 3

- [X] T030 [P] [US3] Update SQL Workflow list link expectations in sql/tests.py or template-focused tests to expect `/workflow/<audit_id>/` from sql/templates/sqlworkflow.html
- [X] T031 [P] [US3] Update SQL export/offline download list link expectations in sql/tests.py or template-focused tests to expect `/workflow/<audit_id>/` from sql/templates/sqlexportworkflow.html
- [X] T032 [P] [US3] Update query privilege list or post-audit navigation expectations in sql/test_query_privileges.py to expect `/workflow/<audit_id>/` where normal navigation now uses audit ID
- [X] T033 [P] [US3] Update archive list link expectations in sql/test_archiver.py or template-focused tests to expect `/workflow/<audit_id>/` from sql/templates/archive.html

### Implementation for User Story 3

- [X] T034 [US3] Change SQL Workflow title links from `/detail/` to `/workflow/` using `row.audit_id` in sql/templates/sqlworkflow.html
- [X] T035 [US3] Change SQL export/offline download title links from `/detail/` to `/workflow/` using `row.audit_id` in sql/templates/sqlexportworkflow.html
- [X] T036 [US3] Change query privilege title links from `/queryapplydetail/` to `/workflow/` using `row.audit_id` in sql/templates/queryapplylist.html
- [X] T037 [US3] Change archive title links from `/archive/` to `/workflow/` using `row.audit_id` in sql/templates/archive.html
- [X] T038 [US3] Verify data providers used by sql/templates/sqlworkflow.html, sql/templates/sqlexportworkflow.html, sql/templates/queryapplylist.html, and sql/templates/archive.html include `audit_id`; add only web-list data shaping needed for links without changing API contracts
- [X] T039 [US3] Confirm `/detail/<workflow_id>/`, `/queryapplydetail/<apply_id>/`, and `/archive/<id>/` still render through existing URL patterns in sql/urls.py and sql/views.py
- [X] T040 [US3] Run the US3 focused tests with `.venv/bin/python -m pytest sql/tests.py sql/test_query_privileges.py sql/test_archiver.py -k "list or link or redirect or detail"` and record any unavailable local environment blocker in specs/004-unified-audit-view/tasks.md

**Checkpoint**: All user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification and cleanup across the web migration.

- [X] T041 [P] Remove unused redirect imports from sql/views.py if no remaining code path needs them after direct rendering
- [X] T042 [P] Search for remaining normal-navigation links to `/detail/`, `/queryapplydetail/`, and `/archive/` in sql/templates/ and document intentional legacy-only occurrences in specs/004-unified-audit-view/tasks.md
- [X] T043 Run quickstart validation from specs/004-unified-audit-view/quickstart.md using the project-local Python environment
- [X] T044 Run targeted formatting or lint checks for changed files in sql/views.py, sql/templates/sqlworkflow.html, sql/templates/sqlexportworkflow.html, sql/templates/queryapplylist.html, and sql/templates/archive.html according to repository conventions
- [X] T045 Review changed tests in sql/tests.py, sql/test_query_privileges.py, sql/test_archiver.py, and sql/test_offlinedownload.py to ensure they use existing fixtures or conftest.py fixtures and do not duplicate setup for legacy detail views

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion; blocks all user stories because direct rendering should share existing context logic.
- **User Story 1 (Phase 3)**: Depends on Foundational; delivers the MVP unified detail view.
- **User Story 2 (Phase 4)**: Depends on Foundational and can run after or alongside US1 once shared helpers exist; safest after US1 direct rendering is in place.
- **User Story 3 (Phase 5)**: Depends on Foundational; can run after US1 so list links have a working destination.
- **Polish (Phase 6)**: Depends on desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Required MVP; no dependency on US2 or US3 after Phase 2.
- **US2 (P1)**: Uses the same unified rendering entry as US1; validates detail context and permission correctness.
- **US3 (P2)**: Depends on a working `/workflow/<audit_id>/` destination from US1 before switching normal list navigation.

### Within Each User Story

- Write or update tests before implementation tasks in that story.
- Keep legacy URL behavior stable while implementing unified rendering.
- Update existing tests instead of adding new tests for soon-to-be-deleted legacy views.
- Run focused tests at each checkpoint before moving to the next story.

## Parallel Opportunities

- T002, T003, T004, and T005 can run in parallel during setup.
- T011 through T014 can be prepared in parallel because they target different work order examples or test files.
- T021 through T024 can be prepared in parallel because each validates a separate context/error case.
- T030 through T033 can be prepared in parallel because each targets a separate list/navigation surface.
- T041 and T042 can run in parallel during polish after implementation stabilizes.

## Parallel Example: User Story 1

```bash
Task: "Add SQL Workflow direct-render coverage for /workflow/<sql_audit_id>/ in sql/tests.py"
Task: "Add archive direct-render coverage for /workflow/<archive_audit_id>/ in sql/test_archiver.py"
Task: "Add offline download direct-render coverage for /workflow/<offline_export_audit_id>/ in sql/tests.py or sql/test_offlinedownload.py"
```

## Parallel Example: User Story 3

```bash
Task: "Change SQL Workflow title links from /detail/ to /workflow/ using row.audit_id in sql/templates/sqlworkflow.html"
Task: "Change query privilege title links from /queryapplydetail/ to /workflow/ using row.audit_id in sql/templates/queryapplylist.html"
Task: "Change archive title links from /archive/ to /workflow/ using row.audit_id in sql/templates/archive.html"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup review.
2. Complete Phase 2 context-helper extraction.
3. Update direct-render tests for `/workflow/<audit_id>/`.
4. Replace redirect behavior in `workflowsdetail` with direct rendering.
5. Stop and validate SQL Workflow, query privilege, archive, and offline download direct rendering.

### Incremental Delivery

1. Deliver US1 to make `/workflow/<audit_id>/` directly useful.
2. Deliver US2 to verify context, permissions, and safe error behavior.
3. Deliver US3 to move normal list navigation to the unified view while keeping old detail URLs usable.
4. Finish with quickstart validation and cleanup.

### Testing Guardrails

- Do not add new test cases whose only purpose is to cover legacy detail views planned for later deletion.
- Do not change API tests for this web-only feature unless an existing web test imports a changed helper and must be adjusted.
- Prefer updating `test_workflowsdetail` and related list/navigation assertions over creating a parallel old/new test matrix.

## Validation Notes

- `.venv/bin/python -m pytest sql/tests.py::TestView::test_workflowsdetail sql/tests.py::TestView::test_workflowsdetail_sqlworkflow_renders_detail sql/tests.py::TestView::test_workflowsdetail_offline_download_renders_sql_detail sql/tests.py::TestView::test_workflowsdetail_missing_audit_id_returns_404 sql/test_query_privileges.py::test_query_privilege_audit sql/test_archiver.py::test_archive_detail_view` passed.
- `.venv/bin/python -m pytest sql/tests.py::TestView -k "sqlworkflow or sqlexportworkflow or queryapplylist or archive or workflowsdetail"` passed.
- `.venv/bin/python -m black --check sql/views.py sql/query_privileges.py sql/archiver.py sql/tests.py sql/test_query_privileges.py sql/test_archiver.py` passed.
- Broader exploratory pytest command including `sql/test_offlinedownload.py -k offline` selected the existing offline download test class and failed in setup because `settings.DATABASES["default"]["PORT"]` is an empty string; the precise unified offline-download render test in `sql/tests.py` passed.
- Remaining `/detail/`, `/queryapplydetail/`, and `/archive/` occurrences are legacy direct tests, legacy-compatible fallback after submit when no audit ID is returned, archive module operation endpoints, or audit-only navigation outside the requested list/detail migration scope.
