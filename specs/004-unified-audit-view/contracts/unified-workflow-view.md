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
- Historical list rows without `audit_id` may still link to these entries to preserve access.

## New Work Order Creation Contract

For new SQL Workflow, query privilege, archive, and offline download work orders that appear in web lists or detail pages:

- An audit record must be created and persisted.
- The created row exposed to list/detail rendering must include a non-empty `audit_id`.
- No-review, display-only, and auto-rejected paths follow the same requirement.
- The audit record must preserve enough type and lifecycle information for `/workflow/<audit_id>/` to choose the renderer and show the audit history safely.

## List Link Contract

List pages should point title/detail links at the unified entry when an `audit_id` is available:

| Page | When `audit_id` exists | When historical row lacks `audit_id` |
|------|------------------------|--------------------------------------|
| `sqlworkflow.html` | `/workflow/<audit_id>/` | `/detail/<workflow_id>/` |
| `sqlexportworkflow.html` | `/workflow/<audit_id>/` | `/detail/<workflow_id>/` |
| `queryapplylist.html` | `/workflow/<audit_id>/` | `/queryapplydetail/<apply_id>/` |
| `archive.html` | `/workflow/<audit_id>/` | `/archive/<id>/` |
| `workflow.html` | `/workflow/<audit_id>/` | Existing behavior for the row source |

Fallback behavior:

- A list row with a non-empty `audit_id` must use the unified entry.
- A historical list row without `audit_id` must use the appropriate legacy detail URL for its type.
- List templates and row serializers must not emit `/workflow/None/`, `/workflow//`, or equivalent invalid audit links.

## Test Contract

Required assertions:

- `/workflow/<audit_id>/` returns success and renders the correct template for SQL Workflow, query privilege, and archive audit records.
- SQL offline download rows navigate to `/workflow/<audit_id>/` and render via the SQL Workflow branch.
- Existing `test_workflowsdetail` redirect assertion is replaced with direct-render assertions.
- List template/link tests are updated to expect `/workflow/<audit_id>/` where row data includes `audit_id`.
- List fallback tests cover old rows without `audit_id` and assert the matching legacy detail URL.
- New creation-path tests cover display-only/no-review/auto-rejected visible work orders and assert a non-empty `audit_id`.
- Tests assert that no rendered list link contains `/workflow/None/` or an empty audit ID segment.

Out of scope:

- Adding new tests for legacy detail views solely because they continue to exist.
- Changing API tests or API contracts.
