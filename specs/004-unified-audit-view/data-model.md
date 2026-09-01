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
- Normal list navigation should use `WorkflowAudit.audit_id`; legacy detail URL remains available.

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
