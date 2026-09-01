# Data Model: Migrate Workflow Operations API

## SQL Workflow

Existing model: `SqlWorkflow`

Fields exposed by the API should align with existing model names:

- `id`: Legacy SQL Workflow identifier, returned for reference only.
- `audit_id`: Operation identifier from the related Workflow Audit Record.
- `workflow_name`: Work item title.
- `demand_url`: Optional demand or ticket link.
- `group_id`, `group_name`: Resource group scope.
- `instance`, `instance_name`: Target instance reference and display name.
- `db_name`: Target database.
- `syntax_type`: SQL type classification from review.
- `is_backup`: Backup flag.
- `engineer`, `engineer_display`: Submitter identity.
- `status`, `status_display`: SQL Workflow lifecycle status.
- `audit_auth_groups`: Existing approval group string, returned only where existing consumers need it.
- `run_date_start`, `run_date_end`: Optional execution window.
- `create_time`, `finish_time`: Creation and completion timestamps.
- `is_manual`: Manual execution marker.
- `is_offline_export`, `export_format`, `file_name`: Existing fields returned where the SQL Workflow row represents an offline export.

Validation rules:

- Submission must validate resource group, instance access, SQL review/pre-count behavior, backup rules, and approval flow creation.
- New read and operation APIs must not accept `id` or `workflow_id` as identifiers.
- `workflow_id` may appear only as reference data in responses.

## SQL Workflow Content

Existing model: `SqlWorkflowContent`

Fields:

- `workflow_id`: Legacy relation to SQL Workflow, returned only as reference data when needed.
- `sql_content`: Submitted SQL.
- `review_content`: Review result JSON.
- `execute_result`: Execution result JSON.

Validation rules:

- Content reads require workflow view permission.
- Empty or legacy result data must be normalized into a readable result representation.
- Raw JSON parsing failures must not expose exception text to users.

## Workflow Audit Record

Existing model: `WorkflowAudit`

Fields:

- `audit_id`: Primary API identifier.
- `workflow_id`: Legacy business row identifier, returned as reference data.
- `workflow_type`: Must be SQL review for this feature's mandatory APIs.
- `workflow_title`, `workflow_remark`: Existing audit title and remark fields.
- `group_id`, `group_name`: Resource group scope.
- `audit_auth_groups`, `current_audit`, `next_audit`: Existing approval flow fields.
- `current_status`: Audit lifecycle status.
- `create_user`, `create_user_display`, `create_time`, `sys_time`: Audit ownership and timestamps.

Relationships:

- One Workflow Audit Record references one SQL Workflow by `workflow_type=SQL_REVIEW` and `workflow_id=SqlWorkflow.id`.
- One Workflow Audit Record has many workflow log entries.

Validation rules:

- New APIs must look up by `audit_id` and reject missing, malformed, nonexistent, or non-SQL-review audit records.
- Authorization checks must use the resolved SQL Workflow and existing permission/resource-group rules.

## Workflow Log

Existing model: `WorkflowLog`

Fields exposed by log API:

- `operation_type_desc`
- `operation_info`
- `operator_display`
- `operation_time`

Validation rules:

- Logs are read by `audit_id`.
- Log responses must be limited to users who can view the related SQL Workflow.

## Scheduled Execution

Existing scheduler helper boundary: SQL schedule task name and run time.

Fields represented in API behavior:

- `audit_id`: Operation identifier.
- `run_date`: Requested execution time.
- Derived `workflow_id`: Used internally for existing schedule name and execution task payload.

Validation rules:

- `run_date` must be in the future.
- `run_date` must fall within the workflow execution window when one exists.
- Scheduling replaces or results in exactly one matching pending scheduled execution.
- Automatic execution, cancellation, and rejection must remove matching pending scheduled execution.

## Online Schema Change Operation

Existing engine capability boundary: `osc_control(command, sqlsha1)`.

Fields:

- `audit_id`: Operation identifier.
- `sqlsha1`: OSC statement identifier.
- `command`: One of `get`, `pause`, `resume`, `kill`.
- Response rows: Existing engine result columns such as `DBNAME`, `TABLENAME`, `PERCENT`, `SQLSHA1`, `REMAINTIME`, and `INFOMATION`.

Validation rules:

- OSC progress and control require permission to view the related SQL Workflow.
- Unsupported commands must be rejected without changing workflow state.
- Engine errors must be logged and returned as sanitized structured errors or status messages.

## State Transitions

| Action | Preconditions | Result |
|--------|---------------|--------|
| Submit SQL Workflow | Authenticated submitter has resource and instance access | SQL Workflow and content are created; Workflow Audit Record is created; response includes `audit_id` and `workflow_id` |
| Approve | User has reviewer authority for current audit node | Audit advances; SQL Workflow becomes review-passed when final approval completes |
| Reject | User has reviewer authority and supplies reason | Audit records reviewer rejection; SQL Workflow becomes aborted; pending schedule is removed |
| Cancel | Submitter or authorized cancel operator supplies reason | Audit records cancellation or abort; SQL Workflow becomes aborted; pending schedule is removed |
| Execute auto | User can execute and execution window is valid | SQL Workflow enters queue; pending schedule is removed; async execution starts after commit |
| Execute manual | User can execute and execution window is valid | SQL Workflow is marked finished with finish time and manual execution log |
| Schedule | User can schedule and run date is valid | SQL Workflow is marked scheduled and one pending schedule is created |
| Adjust execution window | User can review current workflow | Execution window fields are updated |
| Read detail/content/status/log/rollback/OSC progress | User can view or has specific rollback permission | Data is returned without state change |
| OSC control | User can view workflow and command is supported | Existing engine OSC command runs and returns operation rows/status |
