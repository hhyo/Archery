# UI Contract: Unified Work Order Detail View

## Scope

This contract defines expected web navigation and rendering behavior. It does not define or change backend API endpoints.

## Unified Detail Entry

Path: `/workflow/<audit_id>/`

Input:

- `audit_id`: Existing `WorkflowAudit.audit_id`.

Resolution:

- Resolve the audit record by `audit_id`.
- Determine work order type from `WorkflowAudit.workflow_type`.
- Resolve the underlying work order using `WorkflowAudit.workflow_id`.
- Render the matching detail template directly.

Expected rendering:

| Audit Type | Work Order Variant | Template | Notes |
|------------|--------------------|----------|-------|
| `QUERY` | Query privilege | `queryapplydetail.html` | No redirect to `/queryapplydetail/<apply_id>/` |
| `SQL_REVIEW` | SQL Workflow | `detail.html` | No redirect to `/detail/<workflow_id>/` |
| `SQL_REVIEW` | Offline download/export | `detail.html` | Identified from SQL Workflow export fields |
| `ARCHIVE` | Archive | `archivedetail.html` | No redirect to `/archive/<id>/` |

Error behavior:

- Missing audit ID route match: normal URL handling.
- Nonexistent audit ID: not found.
- Unsupported audit type: not found or clear unsupported response.
- Unauthorized user: permission denial without work order details.
- Missing underlying work order: not found or clear unavailable response.

## Legacy Detail Entries

The following paths remain usable during this feature:

- `/detail/<workflow_id>/`
- `/queryapplydetail/<apply_id>/`
- `/archive/<id>/`

Expected behavior:

- Existing direct rendering remains intact.
- These paths are compatibility entries, not the normal target for list-page detail links.

## List Link Contract

List pages should point title/detail links at the unified entry when an `audit_id` is available:

| Page | Current Legacy Detail Target | New Target |
|------|------------------------------|------------|
| `sqlworkflow.html` | `/detail/<workflow_id>/` | `/workflow/<audit_id>/` |
| `sqlexportworkflow.html` | `/detail/<workflow_id>/` | `/workflow/<audit_id>/` |
| `queryapplylist.html` | `/queryapplydetail/<apply_id>/` | `/workflow/<audit_id>/` |
| `archive.html` | `/archive/<id>/` | `/workflow/<audit_id>/` |
| `workflow.html` | `/workflow/<audit_id>/` | unchanged |

Fallback behavior:

- If a transitional list row lacks `audit_id`, keep the old link only where needed to preserve usability.
- Tests should prefer fixtures/rows that include `audit_id`, because that is the target navigation model.

## Test Contract

Required assertions:

- `/workflow/<audit_id>/` returns success and renders the correct template for SQL Workflow, query privilege, and archive audit records.
- SQL offline download rows navigate to `/workflow/<audit_id>/` and render via the SQL Workflow branch.
- Existing `test_workflowsdetail` redirect assertion is replaced with direct-render assertions.
- List template/link tests are updated to expect `/workflow/<audit_id>/` where row data includes `audit_id`.

Out of scope:

- Adding new tests for legacy detail views solely because they continue to exist.
- Changing API tests or API contracts.
