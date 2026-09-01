# Implementation Plan: Unified Audit Work Order View

**Branch**: `004-unified-audit-view` | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-unified-audit-view/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Unify the web work order detail experience around `/workflow/<audit_id>/` for SQL Workflow, query privilege, archive, and offline download work orders. The existing `/workflow/<audit_id>/` view currently resolves the audit record and redirects to type-specific legacy detail pages; this feature cancels that redirect and renders the correct detail template directly from the unified view after resolving the work order type. Existing legacy detail URLs such as `/detail/<workflow_id>/`, `/queryapplydetail/<apply_id>/`, and `/archive/<id>/` remain usable, while list pages and normal web navigation move to the new audit ID based detail link.

The implementation is web-focused and should not introduce API contract changes. Tests should move coverage from redirect expectations to direct rendering through the new unified view; do not add new tests for views that are expected to be removed later.

## Technical Context

**Language/Version**: Python 3 with Django project runtime as configured by the repository  
**Primary Dependencies**: Django server-rendered views/templates, existing workflow audit utilities, jQuery/bootstrap-table based templates  
**Storage**: Existing relational data models only: `WorkflowAudit`, `WorkflowLog`, `SqlWorkflow`, `QueryPrivilegesApply`, `ArchiveConfig`; offline download remains represented by `SqlWorkflow.is_offline_export`  
**Testing**: pytest using repository `pyproject.toml` configuration and shared fixtures; update existing Django view tests rather than creating duplicate coverage for legacy views  
**Target Platform**: Archery browser-based web application  
**Project Type**: Django web application with server-rendered frontend templates  
**Performance Goals**: Opening `/workflow/<audit_id>/` should be comparable to opening the old type-specific detail page, with audit lookup plus the same type-specific data lookup performed once per request  
**Constraints**: Web-only change; no API contract change; legacy detail URLs remain usable; `/workflow/<audit_id>/` directly renders instead of redirecting; list-page title links move to audit ID based URLs; tests must focus on the new view and avoid adding coverage for soon-to-be-deleted old views  
**Scale/Scope**: Four web flows: SQL Workflow list/detail, query privilege list/detail, archive list/detail, and offline download list/detail; audit todo list already uses `/workflow/<audit_id>/` links

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Multi-engine compatibility impact is listed and bounded by adapter or capability layer.
- [x] Test plan is unit-test-first with pytest; integration scope is explicitly minimized.
- [x] Shared setup is designed via conftest.py fixtures; duplicate setup is eliminated.
- [x] Any integration test includes a written justification for why unit tests are insufficient.
- [x] User-facing failures avoid raw internal exceptions and preserve permission-aware behavior.
- [x] Frontend call sites are updated in the same change set as the web navigation change.

## Project Structure

### Documentation (this feature)

```text
specs/004-unified-audit-view/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── unified-workflow-view.md
└── tasks.md
```

### Source Code (repository root)

```text
sql/
├── views.py
├── urls.py
├── tests.py
├── test_archiver.py
├── test_query_privileges.py
└── templates/
    ├── sqlworkflow.html
    ├── sqlexportworkflow.html
    ├── queryapplylist.html
    ├── archive.html
    ├── detail.html
    ├── queryapplydetail.html
    ├── archivedetail.html
    └── workflow.html

common/
└── workflow.py
```

**Structure Decision**: Keep the feature in the existing Django app layout. `sql/views.py` owns both the legacy detail views and the unified `workflowsdetail` entry point. The unified view should reuse existing type-specific context-building behavior so `/workflow/<audit_id>/` renders `detail.html`, `queryapplydetail.html`, or `archivedetail.html` directly. SQL offline download is a SQL Workflow detail variant and should render through the SQL Workflow branch with existing offline-export context and template behavior. List templates should update title/detail links to `/workflow/<audit_id>/` where their row data includes `audit_id`.

## Complexity Tracking

No constitution violations are planned. The main complexity is temporary coexistence: old detail URLs stay available while normal navigation moves to the unified audit ID URL. This is required to avoid disrupting bookmarks and existing references during the web transition.

## Phase 0 Research

See [research.md](./research.md). Decisions cover direct rendering from `/workflow/<audit_id>/`, list link migration, offline download representation, legacy URL compatibility, and test migration.

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/unified-workflow-view.md](./contracts/unified-workflow-view.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

- [x] Multi-engine compatibility remains bounded: this feature changes web navigation and rendering only; existing SQL execution, query privilege, archive, and offline download logic stays behind current domain utilities.
- [x] Test strategy remains pytest-first and focuses on view resolution, template rendering, context, permissions, and list link output.
- [x] Shared fixture requirements are captured for task generation; new setup should reuse existing SQL Workflow, query privilege, archive, audit, user, group, and permission fixtures.
- [x] Integration scope is limited to Django request/template behavior that cannot be proven by pure unit tests.
- [x] User-facing error behavior remains permission-aware and avoids exposing internal exceptions.
