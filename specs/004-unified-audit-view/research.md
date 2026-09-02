# Research: Unified Audit Work Order View

## Decision: Make `/workflow/<audit_id>/` render directly

Rationale: `sql.views.workflowsdetail` already resolves the audit record and branches by work order type, but currently returns redirects to legacy detail pages. Direct rendering preserves the same audit ID entry point while removing the extra navigation step and lowering user-visible complexity.

Alternatives considered: Keep redirects and only change list links, but that keeps the old page model visible in browser URLs. Replace old detail routes immediately, but the user explicitly requires legacy URLs such as `/detail/x` to remain available.

## Decision: Reuse existing type-specific detail rendering behavior

Rationale: Existing `detail`, `queryapplydetail`, and `archive_detail` views already build the context required by their templates. The safest web-only plan is to extract or share that context-building logic so the unified view can render the same templates directly without changing API contracts or domain behavior.

Alternatives considered: Create one brand-new template for every work order type, but that increases UI churn and risk. Duplicate context-building logic inside `workflowsdetail`, but that makes future behavior drift more likely.

## Decision: Treat offline download as a SQL Workflow detail variant

Rationale: The repository represents offline download/export through SQL Workflow fields and pages such as `sqlexportworkflow.html` linking to SQL detail. There is no separate `WorkflowType` value for offline download in `WorkflowAudit`; the type distinction is currently carried by SQL Workflow data such as `is_offline_export`.

Alternatives considered: Add a new work order type for offline download, but that would be an API/data model change outside this web-focused feature. Keep offline download links on `/detail/<workflow_id>/`, but that breaks the goal that normal web navigation uses audit ID.

## Decision: Update list-page detail links to audit ID URLs

Rationale: Current SQL and export list templates link titles to `/detail/<workflow_id>/`; query privilege links to `/queryapplydetail/<apply_id>/`; archive links to `/archive/<id>/`. Rows already need or can include audit IDs for log/navigation behavior, so title/detail links should point to `/workflow/<audit_id>/` whenever an audit ID is available.

Alternatives considered: Only update the todo workflow list, but it already uses `/workflow/<audit_id>/` and would leave the main list pages inconsistent. Show both old and new links, but that preserves the old mental model.

## Decision: Use legacy detail fallback for historical rows without audit ID

Rationale: Older persisted work orders may appear in list pages without an associated `WorkflowAudit` row. Generating `/workflow/None/`, `/workflow//`, or equivalent broken links would make those records unreachable from lists. A link formatter should branch per row: use `/workflow/<audit_id>/` when present, otherwise keep the appropriate legacy URL for that work order type.

Alternatives considered: Require a historical backfill before the web migration, but that increases release risk and changes the scope from web migration to data repair. Hide no-audit rows from lists, but that would remove existing visibility. Always attempt unified resolution from legacy IDs at click time, but the list already knows whether an audit ID is available and can choose the safer URL.

## Decision: Always create audit records for new web-visible work orders

Rationale: The unified web model depends on audit ID as the user-facing identifier. New SQL Workflow, query privilege, archive, and offline download work orders that remain visible in web lists/details must create at least a display-only audit record, including no-review and auto-rejected paths. The existing auto-reject branch is the reference pattern because it preserves a lifecycle record even when manual approval is skipped or fails early.

Alternatives considered: Let no-review or auto-rejected work orders remain without audit records and rely on legacy detail URLs, but that perpetuates two mental models for new data. Backfill later only, but new records would continue adding exceptions. Introduce a separate display identifier outside `WorkflowAudit`, but that duplicates the audit ID contract from feature 003.

## Decision: Keep legacy detail URLs usable during this feature

Rationale: Existing bookmarks, notifications, and direct links may still target `/detail/<workflow_id>/`, `/queryapplydetail/<apply_id>/`, or `/archive/<id>/`. The requested migration changes normal navigation, not backwards compatibility for these URLs.

Alternatives considered: Redirect legacy detail URLs to `/workflow/<audit_id>/`, but the user specifically said old detail URLs should remain usable. Delete old URLs now, but that creates unnecessary disruption.

## Decision: Move tests to the new unified view, not the soon-to-be-deleted views

Rationale: Existing `test_workflowsdetail` currently asserts a redirect. It should assert direct rendering through `/workflow/<audit_id>/` for supported work order types. New or changed tests should verify the new view behavior and list-link generation; do not add dedicated coverage for old detail views beyond preserving currently necessary smoke checks.

Alternatives considered: Add parallel tests for every old and new path, but that spends coverage on views intended for deletion. Remove all old-path tests immediately, but existing compatibility still matters until a later removal feature.

## Decision: Do not change API contracts in this feature

Rationale: Feature 003 handled SQL Workflow API migration. The current feature is explicitly scoped to web list/detail behavior and should consume existing data shape rather than change backend endpoints.

Alternatives considered: Add new API fields or endpoints for query privilege, archive, or offline download, but that expands scope beyond the user's web-only request.
