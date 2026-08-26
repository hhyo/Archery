# Research: Workflow Operations REST API Migration

## Decision 1: Use a dedicated session-user workflow API module

**Decision**: Add `sql_api.api_workflow_operations` and route its views under `/api/v1/workflows/`; do not reuse `api_workflow.AuditWorkflow` or `ExecuteWorkflow` directly.

**Rationale**: Existing generic workflow views accept `engineer` from the request body and then operate as that user. The migrated page behavior must enforce the authenticated session user, matching the original views and preventing actor spoofing. A dedicated module can preserve old page field names while deriving all permissions and audit actors from `request.user`.

**Alternatives considered**:

- Extend `api_workflow.AuditWorkflow` and `ExecuteWorkflow`: rejected because their public payload and actor semantics serve a different, generic API contract.
- Put the operation code directly in `sql_api.urls`: rejected because permission, transaction and notification behavior would not be independently testable.

## Decision 2: Standardize paths under `/api/v1/workflows/` without legacy aliases

**Decision**: Route every migrated capability beneath `/api/v1/workflows/`, use plural `workflows`, and remove the corresponding `sql/urls.py` paths.

**Rationale**: The project already mounts `sql_api.urls` at `/api/` and has versioned routes below `v1/`. The requested migration explicitly excludes old URLs. A single prefix makes operation discovery and frontend replacement mechanical.

**Alternatives considered**:

- Keep the old routes as aliases: rejected by the user requirement and would retain two contracts to maintain.
- Reuse `/api/v1/workflow/`: rejected because it is already a broader generic submission/audit API with different semantics.

## Decision 3: Preserve form fields and page response envelopes

**Decision**: Keep established input names (`workflow_id`, `audit_remark`, `cancel_remark`, `mode`, `run_date`, `run_date_start`, `run_date_end`, `sqlsha1`, `command`) and preserve data-oriented response envelopes (`total/rows`, `rows`, `status/msg/rows`, `status/msg/data`). Replace redirects with structured successful REST responses for state-changing endpoints; update the existing page success handler only where it relied on form navigation.

**Rationale**: URL-only frontend updates are feasible for AJAX calls and lists only when parameter names and response parsing remain stable. HTML redirects are not REST responses, so the client needs a small shared success behavior to navigate to the existing detail page after successful mutation.

**Alternatives considered**:

- Normalize every response to a new global envelope: rejected because it would widen frontend churn and risk Bootstrap Table/result parsing regressions.
- Keep HTML redirect responses: rejected because REST endpoints should return explicit outcomes and clients need reliable error handling.

## Decision 4: Extract transactional operation orchestration

**Decision**: Move state-changing logic into service functions called by DRF views. Database workflow/audit updates occur in `transaction.atomic()`; external queue, schedule deletion/creation and notifications execute with `transaction.on_commit()`.

**Rationale**: Original views interleave database writes and external side effects. Central orchestration allows tests to assert unchanged state on failure and avoids sending notifications or queueing execution before a committed state. The termination service captures whether the workflow was scheduled before changing its status, eliminating the current unreachable cleanup condition.

**Alternatives considered**:

- Copy legacy logic into each API view: rejected because it duplicates correctness-sensitive state transitions and makes unit testing harder.
- Run django-q operations inside the database transaction: rejected because external side effects cannot be rolled back and can observe uncommitted or later-rolled-back state.

## Decision 5: Keep multi-engine behavior at existing adapters

**Decision**: Detail normalization remains in the API layer, while rollback and OSC continue to call `get_engine(instance=workflow.instance)`.

**Rationale**: Existing engines encapsulate database-specific rollback and OSC logic. The API migration changes transport and orchestration only, so it must not introduce database-type branching.

**Alternatives considered**:

- Implement rollback/OSC per database in REST views: rejected because it violates the adapter boundary and risks divergent engine behavior.

## Decision 6: Test at the service boundary first

**Decision**: Add pytest service tests with reusable fixtures for permissions, workflows, audits and mocks; add narrow `APIClient` tests for authenticated dispatch, routes, payload parsing and absence of legacy routes.

**Rationale**: State transition, audit, scheduling and notification rules can be deterministically tested with mocks. Only URL resolving, DRF request parsing and session authentication need integration coverage.

**Alternatives considered**:

- Test only through API endpoints: rejected by the constitution because it would make most tests slower and duplicate fixture setup.