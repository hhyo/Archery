# Data Model: Workflow API Contract Completeness

## Instance

Represents a configured database instance that may be referenced by workflow records.

**Public read fields**:

- `id`: Stable instance identifier.
- `instance_name`: User-facing instance display name.
- `db_type`: Database engine family used in review text.
- `type`: Instance role/type, such as master or replica, used in review text.

**Fields excluded from public read detail**:

- Connection usernames and passwords.
- Secrets, tokens, tunnel credentials, access keys, and private keys.
- Internal operational configuration and administrator-only flags.
- Any field whose value is only useful for configuring or operating the instance as an administrator.

**Validation rules**:

- Requester must be authenticated.
- Requester must have either submit-style `can_write` access or query-style `can_read` access to the instance.
- Superusers and users with all-instance query permission are eligible through the existing instance permission helper.
- Missing, invalid, or unauthorized ids return deterministic sanitized failures.

## Workflow

Represents a SQL workflow record visible through existing workflow APIs.

**Core fields**:

- `id`: SQL Workflow row identifier returned as workflow data.
- `workflow_id`: Alias/reference to the SQL Workflow row identifier where used by existing clients.
- `audit_id`: SQL Workflow audit identifier when an audit record exists.
- `workflow_name`: User-facing workflow title.
- `status`: Lifecycle status.
- `instance`: Instance identifier. This is an id, not an embedded object or display name.
- `instance_name`: Optional denormalized display value where existing responses already include it.
- `db_name`: Target database name.
- `group_name`: Resource group display name.
- `engineer_display`: Submitter display name.
- `syntax_type`: Review/execution result category.
- `create_time`: Created timestamp.

**Relationships**:

- `Workflow.instance` references `Instance.id`.
- A SQL workflow may have one `WorkflowAudit` record for SQL review operations.
- A SQL workflow may have one `WorkflowContent` record.
- A SQL workflow may have many `WorkflowLog` records through its audit id.

**Validation rules**:

- SQL Workflow operation/detail lookup under `/api/v1/sql-workflows/` continues to use audit id.
- This feature does not add a duplicate workflow detail endpoint keyed by workflow id.
- Requester must pass existing workflow visibility checks.

## Workflow Content

Represents saved SQL review or execution content.

**Core fields**:

- `rows`: Review or execution result rows.
- `workflow`: Workflow object when returned by create/list style responses.
- `sql_content`: Submitted SQL where already part of the current contract.
- `review_content`: Saved review result where already part of the current contract.
- `execute_result`: Saved execution result where already part of the current contract.

**Extension data**:

- Additional properties are preserved for generated-client compatibility.
- Nested objects and arrays must remain intact.
- Extensions must not replace or change documented core field meanings.

## Workflow Log

Represents workflow history visible to authorized users.

**Core fields**:

- `operation_type_desc`: Operation label.
- `operation_info`: Operation detail text.
- `operator_display`: Display name of the actor.
- `operation_time`: Operation timestamp.

**Extension data**:

- Additional properties are preserved for CLI structured JSON compatibility.
- Extensions must not mask core log fields.

## Workflow Status

Represents the current state returned to watch or polling clients.

**Core fields**:

- `status`: Current workflow status code.
- `msg`: Message text, empty when there is no additional status message.
- `data`: Additional status payload, empty when no payload is available.

## Workflow Action Result

Represents the standard response returned after approval, execution, and similar workflow actions.

**Core fields**:

- `status`: Numeric action result code.
- `msg`: User-facing action result message.
- `data.audit_id`: SQL Workflow audit identifier.
- `data.workflow_id`: SQL Workflow row identifier.
- `data.redirect_url`: Existing workflow detail redirect URL when returned by the current API.

## Workflow Approval Request

Represents the body for approving an existing SQL Workflow.

**Core fields**:

- `audit_remark`: Optional approval remark. Empty string is allowed by the current API.

**Derived values**:

- Acting user is derived from the authenticated session.
- Workflow is derived from the path audit identifier.

## Workflow Execution Request

Represents the body for executing an existing SQL Workflow.

**Core fields**:

- `mode`: Required execution mode. Allowed values are `auto` and `manual`.

**Derived values**:

- Acting user is derived from the authenticated session.
- Workflow is derived from the path audit identifier.
- No `engineer` field is accepted or required for the audit-id execution endpoint.

## Extension Data

Represents unknown or optional fields preserved from workflow-related responses.

**Rules**:

- Must support primitive values, objects, arrays, and nulls.
- Must be retained by generated clients and CLI JSON output.
- Must remain separate in meaning from documented core fields.
