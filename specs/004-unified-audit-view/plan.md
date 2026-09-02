# Implementation Plan: Unified Audit Work Order View

**Branch**: `004-unified-audit-view` | **Date**: 2026-09-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-unified-audit-view/spec.md`

## Summary

Unify SQL Workflow, query privilege, archive, and offline download web detail navigation behind `/workflow/<audit_id>/`. The unified view resolves the audit record, branches by work order type, and renders the existing type-specific detail experience directly rather than redirecting to legacy detail URLs.

List pages should link to `/workflow/<audit_id>/` whenever audit ID is present, while historical rows without an audit ID fall back to their legacy detail URL. New web-visible work orders, including no-review and auto-rejected display-only cases, must create an audit record so future navigation remains audit-ID-first.

## Technical Context

**Language/Version**: Python/Django web application, existing project runtime
**Primary Dependencies**: Django views/templates, existing `sql` app workflow/audit models and permission helpers
**Storage**: Existing relational database models; no storage engine or schema redesign planned by the web migration
**Testing**: pytest via project-local `.venv/bin/python -m pytest`
**Target Platform**: Existing Archery web deployment
**Project Type**: Web application
**Performance Goals**: Preserve existing list/detail request behavior; avoid adding extra redirect round trips on `/workflow/<audit_id>/`
**Constraints**: Web-only change; API contracts remain unchanged. New web-visible work orders must have audit records, including display-only no-review and auto-rejected cases. Historical list rows may lack audit IDs and must link to legacy detail URLs instead of broken unified URLs.
**Scale/Scope**: Four supported work order families: SQL Workflow, query privilege, archive, and offline download/export as a SQL Workflow variant.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Multi-engine compatibility impact is listed and bounded by adapter or capability layer. No SQL parser or engine adapter behavior changes are planned.
- [x] Test plan is unit-test-first with pytest; integration scope is explicitly minimized to Django request/template routing where needed.
- [x] Shared setup is designed via conftest.py fixtures; duplicate setup is eliminated.
- [x] Any integration test includes a written justification for why unit tests are insufficient.

## Project Structure

### Documentation (this feature)

```text
specs/004-unified-audit-view/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
sql/
├── views.py
├── query_privileges.py
├── archiver.py
├── models.py
├── tests.py
├── test_query_privileges.py
└── test_archiver.py

sql/templates/
├── sqlworkflow.html
├── sqlexportworkflow.html
├── detail.html
├── queryapplylist.html
├── queryapplydetail.html
├── archive.html
└── archivedetail.html
```

**Structure Decision**: Keep the change inside the existing Django `sql` app. Share or extract existing detail-context logic where needed, update list rows/templates to prefer audit-ID links with legacy fallback, and avoid introducing a new frontend package or API surface.

## Phase 0: Research Output

Research decisions are captured in [research.md](./research.md). All clarification points are resolved and no unresolved clarification markers remain.

## Phase 1: Design Output

- Data model and lifecycle constraints: [data-model.md](./data-model.md)
- Web navigation/rendering contract: [contracts/unified-workflow-view.md](./contracts/unified-workflow-view.md)
- Validation guide: [quickstart.md](./quickstart.md)

## Post-Design Constitution Check

- [x] Multi-engine compatibility remains unaffected; the plan does not change SQL execution, parser behavior, or engine adapters.
- [x] Tests target routing/link formatting/context behavior with pytest and do not add broad integration coverage for soon-to-be-deleted views.
- [x] Shared fixtures remain the expected setup mechanism for any new or moved test coverage.
- [x] Integration tests, if added for Django request handling, must include the required rationale.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
