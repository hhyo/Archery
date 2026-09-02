# Feature Specification: Unified Audit Work Order View

**Feature Branch**: `004-unified-audit-view`  
**Created**: 2026-09-01  
**Status**: Draft  
**Input**: User description: "003 的开发已经完成, 在其中, 我们在设计 API 时, 使用了统一的 audit id 来进行设计, 客户端一侧仅会接触到这个 id。我想在 web 的设计中同样遵循这一原则, 将 sqlworkflow 工单, queryprivilege 工单, 归档工单, 和 offline download 工单都这样设计, 并且将其合并为同一个 view, 在其中做具体的工单类型判断, 然后进行渲染, 进一步降低用户理解的难度"

## Clarifications

### Session 2026-09-02

- Q: How should the web design handle new work orders that would otherwise have no audit ID, and old work orders that already lack one? → A: New work orders that need web detail/list visibility must always create an audit record, including no-review or auto-rejected display-only cases; existing old work orders without an audit ID should keep list navigation usable by falling back to their legacy detail URL.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open Any Work Order by Audit ID (Priority: P1)

As an authenticated user with access to a work order, I can open SQL Workflow, query privilege, archive, or offline download work orders using one audit identifier so that I do not need to know each work order type's legacy identifier rules.

**Why this priority**: The unified audit identifier is the central product contract from the completed backend work and is the main simplification users will experience.

**Independent Test**: For each supported work order type, open a permitted work order using only its audit identifier and verify that the correct detail content is shown without requiring a workflow ID, privilege ID, archive ID, download ID, or type-specific URL from the user.

**Acceptance Scenarios**:

1. **Given** a user has permission to view a SQL Workflow work order, **When** the user opens the unified work order view with its audit ID, **Then** the page shows SQL Workflow details and actions relevant to that work order.
2. **Given** a user has permission to view a query privilege work order, **When** the user opens the unified work order view with its audit ID, **Then** the page shows query privilege details and actions relevant to that work order.
3. **Given** a user has permission to view an archive work order, **When** the user opens the unified work order view with its audit ID, **Then** the page shows archive details and actions relevant to that work order.
4. **Given** a user has permission to view an offline download work order, **When** the user opens the unified work order view with its audit ID, **Then** the page shows offline download details and actions relevant to that work order.

---

### User Story 2 - Understand Type-Specific State and Actions in One Place (Priority: P1)

As a requester, reviewer, or operator, I can use one work order detail page that adapts to the work order type so that I can review status, content, audit history, and available actions without learning four separate page patterns.

**Why this priority**: A single view only reduces cognitive load if it still presents each work order type's distinct content and permitted actions clearly.

**Independent Test**: Open representative work orders across all four types and verify that the shared sections stay consistent while each type displays only the fields and actions that make sense for that type and current user.

**Acceptance Scenarios**:

1. **Given** a work order has type-specific fields and shared audit metadata, **When** it is rendered in the unified view, **Then** shared metadata appears in consistent locations and type-specific details appear in a clearly labeled detail area.
2. **Given** a user lacks permission for a type-specific operation, **When** the work order is displayed, **Then** the unavailable operation is hidden or disabled with a clear permission-aware explanation.
3. **Given** a work order changes state after an action, **When** the view refreshes or reopens, **Then** the visible state, timeline, and available actions reflect the latest authorized state.

---

### User Story 3 - Follow Existing Links Without Disruption (Priority: P2)

As an existing user following older notifications, bookmarks, or list links, I can still reach the correct work order experience while the product transitions to the unified audit ID model.

**Why this priority**: Existing links and user habits should not break abruptly during the web migration.

**Independent Test**: Use current list entries, notification links, and supported legacy entry points for each work order type and verify that they land on the unified view or provide a clear migration path using the audit ID.

**Acceptance Scenarios**:

1. **Given** a current work order list contains links for any supported work order type, **When** a user follows a link, **Then** the user lands on the unified work order view identified by audit ID.
2. **Given** an old listed work order has no associated audit ID, **When** a user follows its list link, **Then** the user lands on that work order's legacy detail page instead of a broken unified link.
3. **Given** a supported legacy detail link can be mapped to an audit ID, **When** a user follows that link, **Then** the user is redirected or guided to the unified view without losing context.
4. **Given** a legacy link cannot be mapped safely, **When** a user follows that link, **Then** the user sees a clear explanation and no unrelated work order data is shown.

### Edge Cases

- The audit ID is missing, malformed, nonexistent, or belongs to an unsupported audit record; the user must receive a clear not-found or invalid-request result without exposing internal details.
- The audit ID exists but the user is not authorized to view it; the user must receive a permission-aware denial and no sensitive work order content.
- The audit ID resolves to a supported work order type whose underlying work order data was deleted, archived, or is otherwise incomplete; the view must show a safe recoverable state with the audit context that the user is allowed to see.
- The audit ID resolves to a work order type added in the future but not yet supported by the unified view; the view must fail gracefully and make the unsupported type clear.
- A user opens the unified view while the work order status changes; the refreshed state must not show stale actions that are no longer valid.
- Search results, notifications, or list pages provide both audit ID and legacy IDs during transition; the web experience must consistently treat audit ID as the primary navigation and operation identifier.
- A newly created work order does not require human review or is automatically rejected before manual review; it must still have an audit record so the web experience can identify, display, and archive it by audit ID.
- An old persisted work order appears in a list but has no associated audit ID; its list link must fall back to the appropriate legacy detail URL for that work order type.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The web experience MUST provide one unified work order detail view for SQL Workflow, query privilege, archive, and offline download work orders.
- **FR-002**: The unified work order view MUST be reachable by audit ID, and normal client-side navigation for supported work order details MUST use audit ID as the primary identifier.
- **FR-003**: Users MUST NOT be required to know, enter, copy, or navigate by type-specific legacy identifiers when opening or operating on supported work orders from the web experience.
- **FR-004**: The unified view MUST determine the work order type from the resolved audit record and render the appropriate content for SQL Workflow, query privilege, archive, or offline download work orders.
- **FR-005**: The unified view MUST display shared audit information consistently across supported work order types, including status, requester, reviewers or operators where applicable, creation time, update time, and audit history.
- **FR-006**: The unified view MUST display type-specific details and operations only when they apply to the resolved work order type.
- **FR-007**: The unified view MUST preserve existing permission, visibility, and state rules for every supported work order type before showing details or offering actions.
- **FR-008**: State-changing actions initiated from the unified view MUST use audit ID as the client-visible identifier.
- **FR-009**: SQL Workflow actions in the web experience MUST follow the completed unified audit ID contract from feature 003, including avoiding client reliance on workflow ID for detail, status, log, review, execution, and control actions.
- **FR-010**: Query privilege, archive, and offline download web flows MUST adopt the same audit ID principle so that users interact with each work order through audit ID rather than type-specific work order IDs.
- **FR-011**: Existing work order list pages, dashboard entries, notification links, and other supported navigation sources MUST take users to the unified work order view whenever an audit ID is available.
- **FR-012**: Supported legacy entry points that can be mapped to audit ID MUST preserve user access by taking the user to the unified view or clearly indicating the new audit ID based path.
- **FR-013**: The unified view MUST show clear user-facing errors for invalid audit IDs, unsupported work order types, missing underlying records, and permission denials without exposing raw internal exceptions or implementation details.
- **FR-014**: The web experience MUST maintain clear visual distinction between shared audit information and type-specific work order content so users can understand what is common and what belongs to the current work order type.
- **FR-015**: The migration MUST avoid reducing the existing user-visible capabilities for SQL Workflow, query privilege, archive, and offline download work orders unless an intentionally retired capability is documented before release.
- **FR-016**: The product documentation or in-app navigation labels affected by this change MUST describe the destination as a unified work order detail experience rather than four separate detail pages.
- **FR-017**: New SQL Workflow, query privilege, archive, and offline download work orders that need web list/detail visibility MUST create an audit record even when they do not require human review or are automatically rejected before manual review.
- **FR-018**: Audit records created for no-review or automatically rejected display-only work orders MUST identify the work order type and lifecycle result clearly enough for the unified view, list pages, and audit history to display them.
- **FR-019**: List pages MUST fall back to the appropriate legacy detail URL for old persisted work orders that do not have an associated audit ID, rather than generating an unusable unified detail link.

### Test Strategy Constraints *(mandatory)*

- **TSC-001**: Validation plan MUST prioritize pytest unit tests for permission decisions, work order type resolution, action availability, and audit ID based routing decisions.
- **TSC-002**: Shared test setup MUST be implemented using conftest.py and reusable fixtures; duplicated setup blocks are not allowed.
- **TSC-003**: Integration tests MUST be limited to web request handling, authenticated navigation, and cross-boundary behavior that cannot be proven via unit tests.
- **TSC-004**: Any added integration test MUST include a short rationale describing why a unit test is insufficient.

### Key Entities *(include if feature involves data)*

- **Audit Record**: The shared audit object identified by audit ID, carrying the work order type, lifecycle state, participants, timestamps, and audit history.
- **Display-Only Audit Record**: An audit record created for a work order that has no human review path or was automatically rejected before manual review, used to make the work order identifiable, viewable, and archivable through the same audit ID model.
- **Unified Work Order View**: The user-facing detail experience that resolves an audit ID and presents common audit context plus type-specific work order content.
- **SQL Workflow Work Order**: A SQL change or execution work item governed by the audit ID contract established in feature 003.
- **Query Privilege Work Order**: A request for query access whose web navigation and operations are represented through audit ID.
- **Archive Work Order**: A data archive request whose web navigation and operations are represented through audit ID.
- **Offline Download Work Order**: An offline export or download request whose web navigation and operations are represented through audit ID.
- **Legacy Work Order Identifier**: A type-specific identifier that may still exist internally or in transitional links but is not the normal client-visible way to operate supported work orders.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of supported SQL Workflow, query privilege, archive, and offline download detail navigation paths that have an audit ID open the unified work order view.
- **SC-002**: In automated tests, 100% of supported work order types render the correct shared audit information and type-specific detail sections when opened by an authorized user using audit ID.
- **SC-003**: In automated tests, 100% of state-changing actions started from the unified view use audit ID as the client-visible identifier and preserve the existing permission and state rules for that work order type.
- **SC-004**: In automated tests, 100% of invalid, nonexistent, unsupported, or unauthorized audit ID requests produce safe user-facing errors and reveal no unrelated work order content.
- **SC-005**: Users can move from a work order list or notification to the correct detail page for any supported work order type in no more than one navigation step.
- **SC-006**: User-facing work order documentation and navigation labels no longer require users to choose among four separate detail page concepts for the supported work order types.
- **SC-007**: In automated tests, 100% of newly created display-only, no-review, or automatically rejected work orders that remain visible in web lists have an audit ID.
- **SC-008**: In automated tests, 100% of old listed work orders without an audit ID link to their appropriate legacy detail page and do not render broken `/workflow/None/` or equivalent links.

## Assumptions

- Feature 003 has already established the SQL Workflow audit ID contract and remains the reference behavior for SQL Workflow web changes.
- The supported scope for this feature is limited to SQL Workflow, query privilege, archive, and offline download work orders.
- Legacy identifiers may still be retained internally or displayed as secondary reference data where useful, but users should not depend on them for normal web navigation or actions.
- Existing authentication, authorization, audit history, and work order lifecycle rules remain authoritative.
- Any service contract gaps for query privilege, archive, or offline download that prevent audit ID only web behavior will be handled as part of this feature's planning scope.
- Newly created work orders can always create at least a display-only audit record, following the same principle as existing automatic rejection handling.
- Historical data may contain work orders without audit records, and this feature will preserve access to them through legacy detail URLs instead of requiring immediate backfill.
