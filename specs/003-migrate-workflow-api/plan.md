# Implementation Plan: Migrate Workflow Operations API

**Branch**: `003-migrate-workflow-api` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-migrate-workflow-api/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Migrate SQL Workflow submission, read, decision, execution, schedule, rollback, status, log, and online schema change operations to REST endpoints that use `audit_id` as the single external identifier. The design keeps the external URL shape resource-oriented and action-specific where domain actions are not pure CRUD, while request and response field names stay aligned with existing `SqlWorkflow`, `SqlWorkflowContent`, `WorkflowAudit`, and `WorkflowLog` model fields to avoid inventing a parallel data vocabulary.

The implementation path should not be constrained by the old `workflow_id`-based route layout. Existing data remains the source of truth, with `WorkflowAudit.audit_id` resolving to the SQL Workflow row internally. Breaking API changes are allowed when all frontend consumers in this branch are updated in the same change set.

## Technical Context

**Language/Version**: Python 3 with Django project runtime as configured by the repository
**Primary Dependencies**: Django, Django REST Framework, django-filter, drf-spectacular, django-q2, simplejson
**Storage**: Existing relational database tables: `workflow_audit`, `sql_workflow`, `sql_workflow_content`, workflow logs, and scheduler backing storage
**Testing**: pytest using repository `pyproject.toml` configuration and shared `conftest.py` fixtures
**Target Platform**: Archery web application server with browser-based frontend consumers
**Project Type**: Django web application with REST API and server-rendered frontend templates
**Performance Goals**: Keep read/list behavior comparable to existing workflow pages; avoid extra repeated database lookups by resolving `audit_id` to `WorkflowAudit` and related SQL Workflow once per request where feasible
**Constraints**: `audit_id` is the only accepted identifier for new SQL Workflow operation APIs; user-facing API errors must be sanitized while unexpected exceptions are logged; all changed frontend call sites must be updated with breaking API changes
**Scale/Scope**: SQL Workflow APIs only; query privilege and archive workflow operations are deferred unless they share SQL Workflow endpoints

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Multi-engine compatibility impact is listed and bounded by adapter or capability layer.
- [x] Test plan is unit-test-first with pytest; integration scope is explicitly minimized.
- [x] Shared setup is designed via conftest.py fixtures; duplicate setup is eliminated.
- [x] Any integration test includes a written justification for why unit tests are insufficient.
- [x] API errors are sanitized for users and unexpected exceptions are logged.
- [x] Breaking API changes include frontend consumer updates in the same change set.

## Project Structure

### Documentation (this feature)

```text
specs/003-migrate-workflow-api/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── workflow-operations.openapi.yaml
└── tasks.md
```

### Source Code (repository root)

```text
sql_api/
├── api_workflow.py
├── api_workflow_operations.py
├── serializers.py
├── urls.py
└── test_workflow_operations_api.py

sql/
├── models.py
├── templates/
│   ├── detail.html
│   ├── sqlworkflow.html
│   └── sqlexportsubmit.html
└── utils/
    ├── sql_review.py
    ├── workflow_audit.py
    ├── execute_sql.py
    └── tasks.py

conftest.py
```

**Structure Decision**: Keep the feature inside the existing Django app layout. Add or adjust DRF views and serializers in `sql_api/` and update server-rendered template JavaScript in `sql/templates/` so browser consumers call the new `audit_id` routes. Do not introduce new persistence models for the API contract; use `WorkflowAudit.audit_id` as the resource key and map internally to existing SQL Workflow models.

## Complexity Tracking

No constitution violations are planned. The only accepted breaking change is the external identifier switch from `workflow_id` to `audit_id`, justified by the feature requirement and covered by same-change frontend updates.

## Phase 0 Research

See [research.md](./research.md). Decisions cover REST route shape, `audit_id` resolution, serializer alignment with existing models, sanitized error handling, transaction boundaries, OSC progress/control, and test strategy.

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/workflow-operations.openapi.yaml](./contracts/workflow-operations.openapi.yaml), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

- [x] Multi-engine compatibility remains bounded: database execution and OSC behavior continue through existing engine capability APIs.
- [x] Test strategy remains pytest unit-first, with integration tests only for REST authentication, routing, serialization, and persistence boundaries.
- [x] Shared fixture requirements are captured in quickstart validation and later task generation.
- [x] API contracts require structured sanitized errors and logging for unexpected server failures.
- [x] Breaking route/identifier changes require matching frontend template updates before legacy views/routes are removed.
