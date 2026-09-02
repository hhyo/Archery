# Data Model: Unified Audit Work Order View

## WorkflowAudit

Existing model: `WorkflowAudit`

Fields used by the unified web view:

- `audit_id`: Public web navigation identifier for `/workflow/<audit_id>/`.
- `workflow_type`: Determines which type-specific detail experience to render.
- `workflow_id`: Internal bridge to the existing work order row.
- `workflow_title`: Title shown in list pages and detail context.
- `workflow_remark`: Audit-level remark where currently displayed.
- `group_id`, `group_name`: Permission and display scope.
- `create_user`, `create_user_display`: Submitter identity.
- `create_time`, `sys_time`: Timeline and sorting data.
- `current_status`, `current_audit`, `next_audit`, `audit_auth_groups`: Review state and current reviewer context.

Relationships:

- One `WorkflowAudit` points to one work order row identified by `workflow_type` and `workflow_id`.
- One `WorkflowAudit` has many `WorkflowLog` rows.

Validation rules:

- `/workflow/<audit_id>/` must return not found for missing audit records.
- Unsupported `workflow_type` values must fail gracefully.
- Permission checks must be evaluated against the resolved work order before rendering sensitive detail content.
- New web-visible work orders must create a `WorkflowAudit` record before they can appear as audit-ID-first list/detail entries.

## DisplayOnlyAuditRecord

Existing model representation: `WorkflowAudit` row for a work order that does not enter a normal human approval path.

Fields used by the unified web view:

- `audit_id`: Required public identifier for new web-visible display-only work orders.
- `workflow_type`: Required type discriminator for SQL Workflow, query privilege, archive, or supported SQL export/offline download variants.
- `workflow_id`: Required bridge to the underlying work order row when that row exists.
- `current_status`: Terminal or display lifecycle state, such as auto-rejected or no-review completed.
- `workflow_remark` and audit log fields: Explain why the record is display-only or auto-rejected where existing audit history supports it.

Relationships:

- One display-only audit record points to one underlying work order row and may have audit logs documenting automatic rejection, skipped human review, or archival-only visibility.

Validation rules:

- Creation flows must not leave a new list-visible SQL Workflow, query privilege, archive, or offline download work order without an audit ID.
- The audit record must identify type and lifecycle result clearly enough for list links, unified detail rendering, and audit history display.
- Existing automatic rejection handling is the reference behavior for preserving audit context when normal review cannot continue.

## SqlWorkflow

Existing model: `SqlWorkflow`

Fields relevant to the unified web view:

- `id`: Legacy SQL Workflow identifier used internally and by legacy `/detail/<workflow_id>/`.
- `workflow_name`, `demand_url`, `group_id`, `group_name`, `instance`, `db_name`: Detail display.
- `engineer`, `engineer_display`: Submitter display.
- `status`: Drives SQL Workflow action visibility.
- `run_date_start`, `run_date_end`, `finish_time`: Execution-window and lifecycle display.
- `is_offline_export`, `export_format`, `file_name`: Offline download/export presentation and download behavior.

Relationships:

- Resolved from `WorkflowAudit.workflow_id` when `workflow_type` is `SQL_REVIEW`.
- Offline download is a SQL Workflow variant rather than a separate audit type.

Validation rules:

- SQL Workflow view permission must pass before rendering.
- SQL Workflow detail actions continue to use the existing audit ID based action URLs established by feature 003.
- New SQL Workflow rows that are visible in web lists must have a related audit record, including auto-review error/auto-reject and no-review cases.
- Existing `/detail/<workflow_id>/` remains available.

## QueryPrivilegesApply

Existing model: `QueryPrivilegesApply`

Fields relevant to the unified web view:

- `apply_id`: Legacy query privilege identifier used internally and by legacy `/queryapplydetail/<apply_id>/`.
- Display title, group, instance, database, and privilege scope fields already used by the existing detail template.
- `status`: Drives review state and action visibility.
- Submitter and reviewer fields used by the existing detail context.

Relationships:

- Resolved from `WorkflowAudit.workflow_id` when `workflow_type` is `QUERY`.

Validation rules:

- Query privilege review permission and current audit node behavior must match the legacy detail page.
- New query privilege applications visible in web lists must have a related audit record even when no human approval step is required.
- Normal list navigation should use `WorkflowAudit.audit_id`; legacy detail URL remains available.

## ArchiveConfig

Existing model: `ArchiveConfig`

Fields relevant to the unified web view:

- `id`: Legacy archive identifier used internally and by legacy `/archive/<id>/`.
- Archive source/target configuration, schedule, resource group, and status fields currently rendered by `archivedetail.html`.
- `resource_group`: Permission and current reviewer resolution.

Relationships:

- Resolved from `WorkflowAudit.workflow_id` when `workflow_type` is `ARCHIVE`.

Validation rules:

- Archive review, switch, once-run, and log display behavior remain unchanged.
- New archive requests visible in web lists must have a related audit record even when the lifecycle is display-only or automatically rejected.
- Normal list navigation should use `WorkflowAudit.audit_id`; legacy detail URL remains available.

## ListRowNavigation

Existing representation: dictionaries or serialized rows returned by SQL Workflow, SQL export/offline download, query privilege, archive, and todo list views.

Fields:

- `audit_id`: Preferred public navigation identifier; required for new web-visible work orders, nullable for historical rows.
- Legacy row identifier: `workflow_id`, `id`, or `apply_id` depending on list type; retained for old-row fallback and internal operations.
- Type-specific display fields: title, group, status, creator, create time, and other fields already shown by each list page.

Validation rules:

- If `audit_id` is present, title/detail navigation must point to `/workflow/<audit_id>/`.
- If `audit_id` is missing for a historical row, navigation must point to the matching legacy detail URL for that list type.
- List rendering must never generate `/workflow/None/`, `/workflow//`, or an equivalent invalid audit link.

## WorkflowLog

Existing model: `WorkflowLog`

Fields used by list/detail experiences:

- `audit_id`: Links logs to the unified audit record.
- `operation_type_desc`, `operation_info`, `operator_display`, `operation_time`: Existing audit timeline display.

Validation rules:

- Logs shown from the unified detail context must correspond to the resolved audit ID.
- Existing log endpoints are unchanged in this web-focused feature.

## State Transitions

This feature does not introduce new domain state transitions. It changes which web entry point renders existing work order states:

| Web Event | Preconditions | Result |
|-----------|---------------|--------|
| Open `/workflow/<audit_id>/` for SQL Workflow | Audit exists, type is SQL review, user can view SQL Workflow | Render `detail.html` directly with existing SQL Workflow context |
| Open `/workflow/<audit_id>/` for offline download | Audit exists, type is SQL review, related SQL Workflow is offline export, user can view it | Render SQL Workflow detail directly with offline-export data available |
| Open `/workflow/<audit_id>/` for query privilege | Audit exists, type is query privilege, user can view/review as allowed | Render `queryapplydetail.html` directly |
| Open `/workflow/<audit_id>/` for archive | Audit exists, type is archive, user can view/review as allowed | Render `archivedetail.html` directly |
| Open legacy detail URL | Existing legacy preconditions pass | Render the old detail URL as before |
| Open unsupported audit type | Audit exists but no supported renderer exists | Show safe not-found or unsupported-work-order response |
| Create new display-only/no-review/auto-rejected visible work order | Work order creation continues after no-review decision or auto-review failure | Create audit record with type, lifecycle result, and usable `audit_id` |
| Render list row with audit ID | Row has non-empty `audit_id` | Link title/detail action to `/workflow/<audit_id>/` |
| Render historical list row without audit ID | Row lacks `audit_id` but has legacy identifier | Link title/detail action to the appropriate legacy detail URL |
