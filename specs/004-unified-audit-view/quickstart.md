# Quickstart: Unified Audit Work Order View

## Prerequisites

- Use the project-local Python environment if present, such as `.venv/bin/python`.
- Reuse existing test fixtures for users, resource groups, SQL Workflow rows, query privilege applications, archive applications, and workflow audit records.
- Do not install dependencies into the system Python environment.

## Validation Commands

Inspect the active feature artifacts:

```bash
sed -n '1,220p' specs/004-unified-audit-view/plan.md
sed -n '1,220p' specs/004-unified-audit-view/contracts/unified-workflow-view.md
```

Run the focused web-view tests after implementation. Prefer the local virtual environment if it exists:

```bash
.venv/bin/python -m pytest sql/tests.py sql/test_query_privileges.py sql/test_archiver.py
```

If the repository has no local virtual environment, ask before creating one or installing dependencies.

## Manual Validation Scenarios

1. SQL Workflow direct render
   - Create or locate a SQL Workflow with a `WorkflowAudit` row.
   - Open `/workflow/<audit_id>/`.
   - Expected: the response succeeds and renders the SQL Workflow detail content directly; the browser does not move to `/detail/<workflow_id>/`.

2. Offline download direct render
   - Create or locate an offline download/export SQL Workflow with a `WorkflowAudit` row.
   - Open `/workflow/<audit_id>/`.
   - Expected: the response succeeds through the SQL Workflow detail branch and preserves offline download/export display behavior.

3. Query privilege direct render
   - Create or locate a query privilege work order with a `WorkflowAudit` row.
   - Open `/workflow/<audit_id>/`.
   - Expected: the response succeeds and renders query privilege detail content directly; the browser does not move to `/queryapplydetail/<apply_id>/`.

4. Archive direct render
   - Create or locate an archive work order with a `WorkflowAudit` row.
   - Open `/workflow/<audit_id>/`.
   - Expected: the response succeeds and renders archive detail content directly; the browser does not move to `/archive/<id>/`.

5. Legacy URL compatibility
   - Open `/detail/<workflow_id>/`, `/queryapplydetail/<apply_id>/`, and `/archive/<id>/` for existing allowed records.
   - Expected: each old URL remains usable and renders its existing detail page.

6. List link migration
   - Open SQL Workflow, SQL export/offline download, query privilege, and archive list pages.
   - Expected: title/detail links use `/workflow/<audit_id>/` when `audit_id` is available.

7. Historical no-audit list fallback
   - Locate or fixture an old SQL Workflow, query privilege, or archive list row without an associated audit ID.
   - Open the relevant list page.
   - Expected: the row links to its legacy detail URL (`/detail/<workflow_id>/`, `/queryapplydetail/<apply_id>/`, or `/archive/<id>/`) and does not render `/workflow/None/` or `/workflow//`.

8. New display-only audit creation
   - Create or fixture a web-visible work order path that has no human review or is automatically rejected before manual review, following the existing auto-reject branch where applicable.
   - Expected: the created work order has a non-empty audit ID, appears in lists with `/workflow/<audit_id>/`, and opens directly in the unified detail view.

9. Error and permission handling
   - Open `/workflow/<missing_or_unauthorized_audit_id>/`.
   - Expected: not-found or permission-denied behavior is clear and no unrelated work order data is shown.
