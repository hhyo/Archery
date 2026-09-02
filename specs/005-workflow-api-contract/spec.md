# Feature Specification: Workflow API Contract Completeness

**Feature Branch**: `005-workflow-api-contract`  
**Created**: 2026-09-02  
**Status**: Draft  
**Input**: User description: "我们目前缺一些接口, 本次实现中需要补齐按现有 CLI 输出依赖和 OpenAPI 扫了一遍，目前缺口主要是这些：GET /api/v1/instance/{id}/ 获取实例详情；使用现有 SQL Workflow detail API，不重复实现 workflow detail；workflow list/detail response schema 需要明确 workflow.instance 是 instance id；workflow log response 的扩展字段策略；workflow content / workflow response 的扩展字段策略。实例详情开放给登录用户，但必须有实例提交或查询权限，且只暴露普通用户有价值的只读字段。"

## Clarifications

### Session 2026-09-02

- Q: 现有 SQL Workflow logs/status/approval/execution API 是否缺少 OpenAPI request/response body 契约？ → A: 是；补齐现有接口 schema，不新增重复接口。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Preserve CLI Review Text From Workflow Results (Priority: P1)

As a CLI user reviewing workflow output, I can resolve the instance referenced by a workflow into its display name, database type, and role so that existing review text remains complete and readable.

**Why this priority**: The current CLI output depends on instance metadata to render entries such as `#8 farm_m (mysql, master)`. Without a stable way to retrieve that metadata, generated clients cannot preserve existing user-facing output.

**Independent Test**: Given a workflow response containing an instance reference, retrieve that referenced instance and verify the resulting review text includes the expected instance name, database type, and role without scanning unrelated resources.

**Acceptance Scenarios**:

1. **Given** a workflow references an existing instance by identifier, **When** a client requests that instance, **Then** the response includes the instance name, database type, and role values required to render existing review text.
2. **Given** a workflow references an instance for which the requester has neither submission nor query permission, **When** the requester asks for that instance, **Then** access is refused with a stable, sanitized error and no unrelated instance details are exposed.
3. **Given** a workflow references a missing or invalid instance identifier, **When** the requester asks for that instance, **Then** the result clearly indicates that the instance cannot be found.

---

### User Story 2 - Use Existing SQL Workflow Detail Contract (Priority: P1)

As a client maintainer, I can use the existing SQL Workflow detail endpoint to retrieve one workflow directly so that workflow-specific operations no longer depend on list pagination and local scanning.

**Why this priority**: The existing SQL Workflow detail endpoint already matches the single-workflow lookup need, and reusing it avoids duplicate contracts with competing identifier semantics.

**Independent Test**: Given a known SQL Workflow audit identifier, request the existing SQL Workflow detail endpoint and verify the returned workflow is the requested one with the same fields needed by current list consumers.

**Acceptance Scenarios**:

1. **Given** a user may view a SQL Workflow, **When** the user requests that workflow through the existing SQL Workflow detail endpoint, **Then** the response contains exactly that workflow's detail data.
2. **Given** the workflow list response contains workflow fields consumed by existing clients, **When** the same workflow is retrieved through the existing SQL Workflow detail endpoint, **Then** those fields are available with compatible meanings.
3. **Given** a SQL Workflow audit identifier is missing, invalid, nonexistent, or not visible to the requester, **When** the direct lookup is attempted, **Then** the system returns a clear failure without requiring clients to scan workflow lists.

---

### User Story 3 - Document Structured Workflow JSON Extension Strategy (Priority: P2)

As a CLI or generated-client consumer, I can rely on a documented extension strategy for workflow, workflow content, and workflow log results so that structured review JSON compatibility is explicit in the API contract.

**Why this priority**: Existing CLI behavior retains unknown response data in extension containers. If generated models silently drop that data, downstream review automation may lose information even when the main workflow still succeeds.

**Independent Test**: Given the generated API contract, verify workflow, workflow content, and workflow log responses document their core fields and extension strategy without changing existing runtime responses.

**Acceptance Scenarios**:

1. **Given** workflow log responses may include extension data, **When** a generated client is built from the contract, **Then** the extension strategy is visible from the schema.
2. **Given** workflow content may include extension data, **When** a generated client is built from the contract, **Then** documented core fields keep their defined meanings.
3. **Given** workflow responses may include extension data, **When** a generated client is built from the contract, **Then** core workflow fields keep their documented types.
4. **Given** a watch client requests SQL Workflow status, **When** a generated client reads the status response, **Then** the workflow status code is available through a documented response field.
5. **Given** an approver or executor performs an action, **When** a generated client submits approval or execution requests, **Then** request and response bodies are documented and match the existing runtime contract.

### Edge Cases

- A workflow has no associated instance; consumers must receive a clear absence signal and must not invent instance display text.
- A logged-in user can see a workflow but has no submission or query access to its instance; instance detail must still be denied.
- An instance role or type is missing for legacy data; consumers must receive the available fields and a stable empty or unknown value for missing display components.
- A workflow appears in list results but is deleted or becomes inaccessible before direct retrieval through the existing SQL Workflow detail endpoint; the lookup must fail consistently and safely.
- Workflow list and workflow detail disagree on the instance reference; this must be treated as a contract violation during validation.
- Extension data contains keys that overlap with defined response fields; defined fields must retain their documented meanings, and extension handling must not mask them.
- Extension data contains nested objects or arrays; the contract must make the extension strategy explicit for generated-client authors.
- Approval requests omit a remark; the existing default empty remark behavior must be documented if retained.
- Execution requests omit or send an unsupported execution mode; the request must be rejected with a deterministic validation response.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a way for authorized consumers to retrieve one instance by identifier.
- **FR-002**: The instance detail result MUST include the instance identifier, display name, database type, and instance role or type needed to reproduce existing CLI review text.
- **FR-003**: The instance detail result MUST be available to logged-in users only when they have either submission permission or query permission for the requested instance, matching the permission model used when submitting SQL workflows or querying instance resources.
- **FR-004**: The instance detail result MUST expose only user-valuable read-only fields and MUST NOT expose internal or sensitive fields such as connection account names, passwords, secrets, tokens, implementation flags, or operational configuration that ordinary users do not need.
- **FR-005**: The system MUST use the existing SQL Workflow detail endpoint for single-workflow retrieval and MUST NOT introduce a duplicate workflow detail endpoint for this feature.
- **FR-006**: The existing SQL Workflow detail result MUST include the workflow fields needed by existing workflow list consumers, including the workflow identifier, status, content summary, instance reference, and review data needed for CLI output.
- **FR-007**: Workflow list and single-workflow results MUST document `workflow.instance` as an instance identifier, not an embedded instance object or display name.
- **FR-008**: Any consumer that receives a workflow instance identifier MUST be able to use that identifier to request instance detail when the requester is authorized for both resources.
- **FR-009**: Workflow log results MUST define a stable strategy for extension data by either documenting all supported extension fields or preserving additional fields as extension data.
- **FR-010**: Workflow content results MUST define a stable strategy for extension data by either documenting all supported extension fields or preserving additional fields as extension data.
- **FR-011**: Workflow results MUST define a stable strategy for extension data by either documenting all supported extension fields or preserving additional fields as extension data.
- **FR-012**: The extension strategy MUST NOT alter the meaning, type, or required presence of documented core fields.
- **FR-013**: The public contract MUST make the structured review JSON extension strategy explicit for generated-client authors.
- **FR-014**: Contract documentation MUST clearly distinguish core fields from extension data for workflow, workflow content, and workflow log results.
- **FR-015**: Failure responses for missing, invalid, unauthorized, or inaccessible instance and workflow identifiers MUST be deterministic, sanitized, and suitable for client error handling.
- **FR-016**: Existing workflow list behavior MUST remain compatible for current consumers while clients migrate away from list pagination scans for single-workflow retrieval.
- **FR-017**: The existing SQL Workflow logs endpoint MUST document a response body containing `total` and `rows`, where each log row includes `operation_type_desc`, `operation_info`, `operator_display`, and `operation_time`, and MUST document the extension data strategy.
- **FR-018**: The existing SQL Workflow status endpoint MUST document a response body containing the current workflow status code in `status`.
- **FR-019**: The existing SQL Workflow approval endpoint MUST document that the acting user and workflow are derived from the authenticated session and path audit identifier, that the request body may contain `audit_remark`, and that the response body is the standard action result.
- **FR-020**: The existing SQL Workflow execution endpoint MUST document that the acting user and workflow are derived from the authenticated session and path audit identifier, that the request body requires execution `mode`, and that the response body is the standard action result.
- **FR-021**: SQL Workflow approval and execution contracts MUST NOT require or document an `engineer` request field for these existing audit-id endpoints.

### Test Strategy Constraints *(mandatory)*

- **TSC-001**: Validation plan MUST prioritize pytest unit tests for instance lookup permissions, workflow lookup permissions, and response field mapping; schema generation MAY be checked with temporary scripts rather than committed tests.
- **TSC-002**: Shared test setup MUST be implemented using conftest.py and reusable fixtures; duplicated setup blocks are not allowed.
- **TSC-003**: Integration tests MUST be limited to request handling, authentication and authorization, contract serialization, and generated-client compatibility that cannot be proven via unit tests.
- **TSC-004**: Any added integration test MUST include a short rationale describing why a unit test is insufficient.

### Key Entities *(include if feature involves data)*

- **Instance**: A database instance visible to authorized users, with an identifier, display name, database type, and role or type used in workflow review displays.
- **Workflow**: A submitted operational work item with an identifier, lifecycle status, content, review metadata, and an instance reference.
- **Workflow Instance Reference**: The value carried as `workflow.instance`; it represents the identifier of an Instance and can be resolved through instance detail when permitted.
- **Workflow Log**: A record or collection of records describing workflow review, execution, or status history, including core fields and optional extension data.
- **Workflow Content**: The structured review content for a workflow, including core fields and optional extension data needed by CLI JSON output.
- **Extension Data**: Additional structured fields in workflow-related responses that are outside the required core schema but are preserved for client compatibility.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of workflows returned to the CLI with a valid instance reference can be resolved to instance display metadata by authorized users.
- **SC-002**: 100% of SQL Workflow detail lookup tests return the requested workflow through the existing detail endpoint without using workflow list pagination or client-side scanning.
- **SC-003**: 100% of workflow list and existing SQL Workflow detail contract checks verify that `workflow.instance` is an instance identifier.
- **SC-004**: 100% of workflow log, workflow content, and workflow response contract checks document the structured review JSON extension strategy.
- **SC-005**: Existing CLI review text and structured review JSON fixtures remain unchanged for all covered happy-path workflow examples.
- **SC-006**: 100% of unauthorized, missing, and invalid instance or workflow lookup tests return sanitized deterministic failures.
- **SC-007**: Generated OpenAPI output shows response bodies for SQL Workflow logs and status, and request/response bodies for SQL Workflow approval and execution, in 100% of contract validation runs.

## Assumptions

- Existing authentication, authorization, visibility, and error-response conventions remain the source of truth.
- The primary consumers are the existing CLI and generated clients created from the public contract.
- The feature preserves current workflow list behavior and relies on the existing SQL Workflow detail endpoint rather than adding a duplicate workflow detail API.
- The instance metadata required for review text is limited to the fields currently needed to render instance name, database type, and role or type.
- Extension data is considered part of the CLI compatibility contract when current CLI structured JSON preserves it.
