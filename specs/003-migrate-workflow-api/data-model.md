# Data Model: Workflow Operations REST API Migration

## Existing Persistent Entities

### SQL Workflow (`SqlWorkflow`)

Represents an SQL work item.

| Field / concept | Role in this feature | Validation / ownership |
|---|---|---|
| `id` | Identifies the target workflow | Positive existing identifier required for every target-specific endpoint. |
| `engineer` | Workflow submitter | Determines submitter abort authority and executor authority with `sql.sql_execute`. |
| `group_id` | Resource group | Used by visibility and group-scoped review/execute permissions. |
| `status` | Lifecycle state | Updated only by transactional operation services. |
| `run_date_start`, `run_date_end` | Permitted execution window | Reviewer may update; execute/schedule must validate target time. |
| `finish_time` | Manual completion time | Set only on successful manual completion. |
| `instance` | Database target | Passed unchanged to the engine adapter for rollback and OSC. |
| `is_backup` | Rollback eligibility | Combined with final/exception status and view permission. |

### Workflow Audit (`WorkflowAudit`) and Log (`WorkflowLog`)

Track approval state and immutable action history. Approval, abort and reject use the existing audit operator. Automatic/manual execution and scheduling append existing log records with the session actor's username and display name.

### Scheduled Execution (`django_q.Schedule`)

One schedule is identified by `sqlreview-timing-{workflow_id}`. It runs the existing SQL execution task exactly once. It is replaced on reschedule and removed after a successful auto-execute or termination commit.

### Workflow Content (`SqlWorkflowContent`)

Stores review and execution result JSON. The detail endpoint selects execution results for finish/exception workflows, otherwise review results; legacy list-form result rows are converted to the existing object form before returning `{"rows": [...]}`.

## Request Models

| Request | Fields | Rules |
|---|---|---|
| Workflow list | `syntax_type[]`, `navStatus`, `instance_id`, `group_id`, `start_date`, `end_date`, `limit`, `offset`, `search` | Preserve Bootstrap Table paging/filter inputs; visibility derives from `request.user`. |
| Execution window update | `workflow_id`, `run_date_start`, `run_date_end` | Reviewer level 2 required; blank dates clear their respective value. |
| Approval | `workflow_id`, `audit_remark` | `sql.sql_review` required; audit operator validates current review state. |
| Execution | `workflow_id`, `mode` | `mode` is `auto` or `manual`; executor and time window required. |
| Schedule | `workflow_id`, `run_date` | `run_date` is future, parseable as `%Y-%m-%d %H:%M`, allowed by workflow window and executor authority. |
| Termination | `workflow_id`, `cancel_remark` | Nonempty reason; actor is submitter (abort) or reviewer (reject), subject to existing cancellation rules. |
| OSC control | `workflow_id`, `sqlsha1`, `command` | Actor must be allowed to view the workflow; command validation is delegated to the engine. |

## Lifecycle Transitions

```text
workflow_manreviewing --approve(final audit step)--> workflow_review_pass
workflow_manreviewing --abort/reject---------------> workflow_abort
workflow_review_pass --schedule--------------------> workflow_timingtask
workflow_timingtask --schedule(replace)------------> workflow_timingtask
workflow_review_pass/workflow_timingtask --auto----> workflow_queuing
workflow_review_pass/workflow_timingtask --manual--> workflow_finish
workflow_review_pass/workflow_timingtask --abort---> workflow_abort
```

All transitions require the existing permission helper and audit rules. Invalid transitions do not mutate workflow, audit or schedule data.

## Derived Response Models

| Response | Compatibility shape |
|---|---|
| List | `{"total": number, "rows": [workflow summary]}` |
| Detail | `{"rows": [review or execution result]}` |
| Rollback | `{"status": 0|1, "msg": string, "rows": [statement]}` |
| Current status | `{"status": workflow_status, "msg": "", "data": ""}` |
| OSC control | `{"total": number, "rows": [operation], "msg": string}` |
| Mutation success | `{"status": 0, "msg": string, "data": {"workflow_id": number, "redirect_url": string}}` |
| Mutation validation/authorization failure | DRF 4xx structured error body; no state changes |