# Feature Specification: Migrate Workflow Operations API

**Feature Branch**: `003-migrate-workflow-api`  
**Created**: 2026-08-26  
**Status**: Draft  
**Input**: User description: "我想把这个文件里涉及到的, 对工单的操作都迁移至 rest api 来进行实现, 并删除原有的 view"

## Clarifications

### Session 2026-08-26

- Q: 工单操作的 REST API 实现是否应新增仅作转发或包装的一行服务函数？ → A: 不新增；将操作逻辑直接嵌入对应 API view。

### Session 2026-08-31

- Q: 是否需要补充一个根据 ID 获取 SQL Workflow 基础详情的 REST 接口？ → A: 需要；新增按 ID 获取 sqlworkflow 详情的 REST 接口。
- Q: 新接口是否应该把提交 SQL Workflow 后的返回主标识也改成 `audit_id`，并让前端详情页后续所有操作都只携带 `audit_id`? → A: 响应同时返回 `audit_id` 和 `workflow_id`，但文档规定只有 `audit_id` 可用于操作。
- Q: 拒绝工单和发起人终止工单在新 API 中应该是两个独立动作，还是继续共用一个取消/终止动作并由后端判断含义? → A: 拆成独立动作：`reject` 仅审核人可用，`cancel` 仅发起人或有终止权限者可用。
- Q: 新 SQL Workflow 的详情、内容、状态和日志读取接口是否也必须改为只接受 `audit_id`? → A: 全都用 `audit_id`。
- Q: 本次 spec 是否要求把本分支里已经改造过的查询权限和归档工单操作也同步改为 `audit_id` 入口? → A: 本次只要求 SQL Workflow 样本闭环，其他工单后续分支处理。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manage Workflow Decisions (Priority: P1)

As an authorized workflow participant, I can approve, reject, or cancel a SQL workflow through the supported REST interface so that its audit state and workflow state remain consistent.

**Why this priority**: Approval, rejection, and cancellation control whether a submitted workflow can proceed and must preserve the existing authorization and audit trail.

**Independent Test**: An authorized requester approves a pending workflow, a reviewer rejects another workflow, and an authorized operator cancels an eligible workflow; each returns the expected outcome, records the correct action and leaves the workflow in the expected state.

**Acceptance Scenarios**:

1. **Given** a reviewer is authorized to approve a pending workflow, **When** the reviewer submits an approval decision, **Then** the approval is recorded and the workflow becomes approved after its required approval sequence completes.
2. **Given** a workflow submitter or authorized cancel operator can cancel an eligible workflow, **When** the operator supplies a cancellation reason through the cancel action, **Then** the cancellation is recorded as a cancellation or abort action and the workflow becomes manually terminated.
3. **Given** a reviewer is authorized to reject an eligible workflow, **When** the reviewer supplies a rejection reason through the reject action, **Then** the rejection is recorded as a reviewer rejection and the workflow becomes manually terminated.
4. **Given** a requester lacks the required authority or supplies a missing required cancellation or rejection reason, **When** the requester attempts a decision, **Then** the decision is refused and no workflow or audit state changes.

---

### User Story 2 - Execute and Schedule Workflows (Priority: P1)

As an authorized executor, I can execute a workflow automatically or manually, or schedule it for a permitted future time, so that operational work is completed with an accurate state and audit history.

**Why this priority**: Execution is the user-facing outcome of an approved workflow and incorrect transitions may cause untracked database changes or missed scheduled work.

**Independent Test**: An authorized executor performs each execution mode on an eligible workflow and verifies the resulting workflow state, audit record and scheduled-work behavior.

**Acceptance Scenarios**:

1. **Given** an executor is authorized and the workflow is within its allowed execution period, **When** automatic execution is requested, **Then** the workflow enters the execution queue, any existing schedule is removed, and an execution audit record is added.
2. **Given** an executor is authorized and the workflow is within its allowed execution period, **When** manual completion is confirmed, **Then** the workflow is marked complete with a completion time and a manual-execution audit record is added.
3. **Given** an executor is authorized and provides a future time within the allowed execution period, **When** scheduling is requested, **Then** the workflow is marked scheduled and exactly one matching scheduled execution is created.
4. **Given** a requested execution or schedule is unauthorized, outside the allowed time period, or scheduled in the past, **When** the request is made, **Then** it is refused without creating execution work or changing the workflow state.

---

### User Story 3 - Inspect and Adjust Workflow Operations (Priority: P2)

As an authorized workflow participant, I can retrieve a workflow's current status, read its details and rollback statements where permitted, adjust its execution window when reviewing it, and control an active online schema change operation.

**Why this priority**: These operations support safe review, monitoring and recovery around the primary decision and execution flows.

**Independent Test**: Authorized and unauthorized users request each operational capability and verify that results are available only within their permissions and changes are retained correctly.

**Acceptance Scenarios**:

1. **Given** a user can view a workflow, **When** the user requests workflow details by audit ID, **Then** the user receives the workflow's saved SQL Workflow detail fields without requiring list filtering.
2. **Given** a user can view a workflow, **When** the user requests workflow content or current status, **Then** the user receives the workflow's appropriate review or execution result and current state.
3. **Given** a user has rollback permission for a workflow, **When** the user requests rollback statements, **Then** the user receives the available statements or a clear failure result without exposing unauthorized data.
4. **Given** an authorized reviewer adjusts an eligible workflow's execution window, **When** valid window values are supplied, **Then** the new values are retained for later execution checks.
5. **Given** an authorized user controls an active online schema change operation, **When** a supported control request is submitted, **Then** the user receives its resulting operation records and status message.

### Edge Cases

- A workflow identifier is missing, malformed, or does not exist; the request must fail without changing state.
- A workflow is cancelled or rejected while it has a scheduled execution; the matching schedule must be removed before the request completes.
- An approval, rejection, cancellation, schedule creation, or execution request fails after validation; the workflow and audit records must not be left in a partially updated state.
- A workflow has no saved review or execution result, or contains legacy result data; authorized users receive a valid, readable result representation.
- A request uses an unsupported execution mode or online schema change command; it must be refused without changing workflow state.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose supported REST endpoints for every workflow operation currently provided by the legacy workflow operation views: listing workflows, submitting SQL Workflow tickets, reading SQL Workflow details by audit ID, reading workflow content, reading rollback statements, adjusting execution windows, approving, rejecting, cancelling, executing, scheduling, reading current status, viewing online schema change progress, and controlling online schema change execution.
- **FR-002**: The system MUST enforce the same existing authentication, role, resource-group, workflow-state, and time-window authorization rules before performing each operation.
- **FR-003**: The system MUST reject missing, malformed, nonexistent, unauthorized, or invalid operation requests with a clear structured error result and MUST NOT change workflow, audit, or scheduling data.
- **FR-004**: The system MUST record approval, reviewer rejection, requester cancellation, automatic execution, manual execution, and scheduled execution actions in the workflow audit history with the actor and operation details.
- **FR-005**: The system MUST update workflow status and relevant timestamps consistently with each successfully completed operation.
- **FR-006**: The system MUST create, replace, or remove scheduled execution work consistently with scheduling, automatic execution, cancellation, and rejection actions; cancellation or rejection of a scheduled workflow MUST remove its matching scheduled work.
- **FR-007**: The system MUST preserve existing configured notification behavior for approval, cancellation, rejection, and manual execution actions, including whether that notification phase is enabled.
- **FR-008**: The system MUST preserve workflow list filtering, paging, search, visibility rules, and response data needed by existing workflow consumers.
- **FR-009**: The system MUST return workflow details, status, rollback statements, and online schema change control results only to users authorized for the corresponding workflow and action.
- **FR-010**: The system MUST process a state-changing workflow operation atomically so a failed operation cannot leave inconsistent workflow state, audit history, or schedule state.
- **FR-011**: The system MUST remove the legacy function-based workflow operation views after the REST endpoints cover their supported behavior, and no active route may depend on a removed legacy view.
- **FR-012**: The system MUST document any intentionally retired legacy endpoint or request/response behavior and provide a migration path for active consumers before removal.
- **FR-013**: The system MUST implement each migrated operation directly in its corresponding REST API view and MUST NOT add one-line forwarding or wrapper functions solely to delegate that operation elsewhere.
- **FR-014**: The system MUST use `audit_id` as the only accepted identifier for new SQL Workflow detail, content, status, log, rollback, execution-window, approval, rejection, cancellation, execution, schedule, online schema change progress, and online schema change control APIs; responses MAY include both `audit_id` and legacy `workflow_id`, but clients MUST NOT use `workflow_id` for those APIs.
- **FR-015**: The system MUST expose reviewer rejection and workflow cancellation as separate API actions; the reject action MUST require reviewer authority, and the cancel action MUST require the submitter or another explicitly authorized cancellation operator.
- **FR-016**: The system MUST limit the mandatory `audit_id` migration scope of this feature to SQL Workflow APIs; query privilege, archive, and offline export APIs are out of scope unless they already share SQL Workflow endpoints.

### Test Strategy Constraints *(mandatory)*

- **TSC-001**: Validation plan MUST prioritize pytest unit tests for workflow permission checks, state transitions, audit creation, notification eligibility, and scheduled-work lifecycle.
- **TSC-002**: Shared test setup MUST be implemented using conftest.py and reusable fixtures; duplicated setup blocks are not allowed.
- **TSC-003**: Integration tests MUST be limited to REST request handling, authentication and authorization, and persistence boundaries that cannot be proven via unit tests.
- **TSC-004**: Any added integration test MUST include a short rationale describing why a unit test is insufficient.

### Key Entities *(include if feature involves data)*

- **SQL Workflow**: A submitted SQL-related work item with submitter, resource scope, execution window, lifecycle state, and completion information.
- **Workflow Audit Record**: The approval process and action history for a workflow, including acting user, decision or operation, remark, and resulting state.
- **Operation Identifier**: The `audit_id` that uniquely identifies the workflow audit record used by new workflow detail, read, and operation APIs; legacy `workflow_id` may be returned as reference data but is not accepted as an API identifier.
- **Scheduled Execution**: A future execution reservation associated with one workflow and its planned run time.
- **Workflow Result**: The review or execution output associated with a workflow, including rollback information where available.
- **Online Schema Change Operation**: A controllable database alteration activity associated with an eligible workflow.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the identified SQL Workflow operation capabilities in FR-001 are available through documented REST endpoints, with no active route invoking a legacy workflow operation view.
- **SC-002**: In automated tests, 100% of authorized approval, rejection, cancellation, execution, scheduling, detail, and status scenarios produce the expected workflow state and audit outcome.
- **SC-003**: In automated tests, 100% of unauthorized or invalid state-changing requests leave workflow state, audit history, and scheduled execution unchanged.
- **SC-004**: A scheduled workflow cancelled or rejected through the REST interface has no matching pending scheduled execution after the request completes in 100% of automated test runs.
- **SC-005**: Existing workflow users can complete approval, rejection, cancellation, execution, and scheduling through their supported clients without manually editing workflow records.

## Assumptions

- Existing authenticated users, permissions, resource-group rules, workflow states, audit records, schedules, and notification configuration remain the source of truth.
- The SQL Workflow operation capabilities are bounded to the functions in `sql_workflow.py`; unrelated workflow display pages and non-workflow modules are out of scope except where route or consumer updates are required for this migration.
- Query privilege and archive workflow operations are not mandatory deliverables for this feature; they may be migrated in later features using the SQL Workflow `audit_id` contract as the reference pattern.
- Existing active consumers will be identified before legacy endpoint retirement; any consumer requiring a transition will receive documented REST endpoint and payload guidance.
- REST responses use the project's established structured result conventions, with endpoint contracts defined during planning.
