# Research: Migrate Workflow Operations API

## Decision: Use `WorkflowAudit.audit_id` as the REST resource identifier

Rationale: `audit_id` is already the primary key of `WorkflowAudit` and uniquely identifies the approval process that all new workflow operations act upon. It also gives a consistent identifier shape for future workflow types even though their business table primary keys differ.

Alternatives considered: Continue using `workflow_id`, but that preserves the current SQL-specific API shape. Use a composite `{workflow_type, workflow_id}`, but that makes clients understand internal table identity.

## Decision: Resolve `audit_id` once at the API boundary

Rationale: Each request should fetch the `WorkflowAudit` by `audit_id`, verify it is `WorkflowType.SQL_REVIEW`, and then resolve the related `SqlWorkflow` through the audit record. This keeps the external contract independent from business table IDs while preserving existing model relationships.

Alternatives considered: Add a new Ticket table, but the feature can be completed with existing storage. Let serializers accept both `audit_id` and `workflow_id`, but that contradicts the clarified API contract.

## Decision: Prefer RESTful resources with explicit domain action endpoints

Rationale: Reads map naturally to resource endpoints, while approval, rejection, cancellation, execution, scheduling, and OSC controls are domain actions with side effects. Separate action endpoints keep permissions, request schemas, audit logs, and frontend button mappings clear.

Alternatives considered: A single `/actions/` endpoint with an action enum, but it weakens schema clarity and makes per-action validation less explicit. Pure CRUD-only resources do not model execution and audit decisions well.

## Decision: Align request and response fields with existing model fields

Rationale: The API should avoid a separate DTO vocabulary. SQL Workflow submission and detail responses should keep names such as `workflow_name`, `demand_url`, `group_id`, `instance`, `db_name`, `is_backup`, `run_date_start`, and `run_date_end`, while adding `audit_id` where clients need the new identifier.

Alternatives considered: Rename fields into a new generic ticket contract, but that adds mapping cost and frontend churn without a data model change.

## Decision: Return both `audit_id` and `workflow_id`, but accept only `audit_id`

Rationale: Returning `workflow_id` helps existing pages display legacy links and debug data, while rejecting it as an input for new endpoints prevents clients from continuing the old operation model.

Alternatives considered: Hide `workflow_id` entirely, but that makes migration and troubleshooting harder. Accept both IDs temporarily, but that undermines the clarified breaking change.

## Decision: Split reviewer rejection and workflow cancellation

Rationale: `reject` and `cancel` have different actors, authorization rules, and audit meaning. Keeping them separate makes tests and frontend controls less ambiguous, even if the implementation can reuse existing audit transition primitives internally.

Alternatives considered: Keep a single termination endpoint, but it forces the server to infer intent from the actor and preserves a confusing contract.

## Decision: Sanitize user-facing errors and log unexpected exceptions

Rationale: The constitution requires raw exceptions, tracebacks, database errors, and internal details to stay out of API responses. API views should return stable structured errors and log unexpected exceptions with context such as `audit_id`, action, and username.

Alternatives considered: Continue returning `str(exception)` from serializer/view errors, but that leaks internal failure details and violates the constitution.

## Decision: Preserve existing engine and scheduler boundaries

Rationale: Multi-engine behavior belongs in existing engine adapters and scheduling helpers. The API migration should not reimplement SQL execution, rollback lookup, OSC control, or scheduler mechanics.

Alternatives considered: Add new API-specific execution services, but that increases behavior duplication. Direct engine calls outside existing capability boundaries risk multi-engine regressions.

## Decision: Use pytest unit tests first and narrow API integration tests

Rationale: Permission checks, state transitions, audit logging, notification eligibility, and schedule lifecycle can be tested with focused unit tests using shared fixtures. Integration tests should prove URL routing, authentication, serialization, and database persistence for representative success/failure paths.

Alternatives considered: Broad end-to-end template/browser tests for every operation, but that is slower and mostly duplicates unit coverage. Legacy unittest-style setup would violate the project testing constitution.
