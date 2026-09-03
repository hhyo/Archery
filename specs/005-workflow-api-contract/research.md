# Phase 0 Research: Workflow API Contract Completeness

## Decision: Instance Detail Uses Authenticated Access Plus Instance Permission

Instance detail will be readable by logged-in users only when the target instance is included in either `user_instances(user, tag_codes=["can_write"])` or `user_instances(user, tag_codes=["can_read"])`.

**Rationale**: The current CLI needs instance metadata for display, but ordinary users should only see metadata for instances they can submit SQL workflows against or query. This matches the permission model already used by SQL workflow submission and query resource access.

**Alternatives considered**:

- Keep administrator-only access: rejected because generated clients and CLI users cannot resolve workflow instance ids.
- Allow any logged-in user to read any instance: rejected because instance inventory leaks across resource boundaries.
- Require both submit and query access: rejected because users may legitimately need review display metadata for either online workflow or offline/query workflows.

## Decision: Public Instance Serializer Is an Explicit Allowlist

The read-only instance response will use a narrow public field allowlist: id, instance name, database type, role/type, host/port only if considered useful to ordinary users, and resource-group display metadata if already visible elsewhere. It will exclude account names, passwords, secrets, tunnels, access keys, operational configuration, internal flags, audit-only settings, and any value whose primary audience is administrators.

**Rationale**: Existing `InstanceDetailSerializer` exposes all model fields except write-only password behavior, which is inappropriate for a user-facing detail endpoint. An allowlist is easier to audit than trying to blacklist sensitive fields.

**Alternatives considered**:

- Reuse `InstanceDetailSerializer`: rejected because it is configuration-oriented and includes internal fields.
- Maintain a sensitive-field blacklist: rejected because future model fields could become exposed by default.

## Decision: Reuse Existing SQL Workflow Detail Endpoint

Clients will use the existing `/api/v1/sql-workflows/{audit_id}/` surface to retrieve one SQL Workflow. This feature will not add or document a duplicate `/api/v1/workflow/{id}/` retrieve endpoint.

**Rationale**: The SQL Workflow audit-id endpoint already exists and matches the single-workflow lookup need. Reusing it avoids two detail endpoints with competing identifier semantics and keeps the generated client aligned with the newer SQL Workflow contract.

**Alternatives considered**:

- Add `/api/v1/workflow/{id}/` retrieve: rejected because it duplicates existing SQL Workflow detail behavior and reintroduces workflow-id versus audit-id ambiguity.
- Continue list pagination scanning: rejected because it is brittle, slower, and hides direct lookup semantics from the contract.

## Decision: `workflow.instance` Is Documented As An Instance Identifier

Workflow list and detail contracts will explicitly type `workflow.instance` as an integer instance id.

**Rationale**: The CLI can then deterministically call instance detail to enrich display output. This also prevents generated clients from modeling the field as a nested object or display string.

**Alternatives considered**:

- Embed instance detail in workflow responses: rejected because it widens workflow payloads and duplicates permission concerns.
- Return instance display name only: rejected because clients still need stable identity for later resolution.

## Decision: Document Extension Strategy With `additionalProperties`

Workflow, workflow content, and workflow log response contracts will allow additional properties where current CLI behavior may rely on unknown fields. Core fields remain explicitly documented, and extensions cannot override core field meanings. Runtime DRF serializers stay on native behavior; this feature does not add a custom unknown-field preservation serializer.

**Rationale**: Generated clients need to see the extension strategy in the contract without requiring the server to enumerate every historical or plugin-provided field up front.

**Alternatives considered**:

- Enumerate every possible extension key: rejected because current unknown fields are open-ended and may vary by engine/result source.
- Drop extension fields: rejected because preserving them is part of CLI compatibility.

## Decision: Document Existing SQL Workflow Action Bodies

The existing audit-id SQL Workflow approval endpoint will document an optional `audit_remark` request field and the standard action result response. The existing audit-id SQL Workflow execution endpoint will document required `mode` with `auto` and `manual` choices and the same standard action result response. Both endpoints derive the actor from the authenticated session and the workflow from the path audit id; neither endpoint documents or requires `engineer`.

**Rationale**: The implementation already reads these request fields and returns a mutation/action response. Documenting them removes `No response body` and path-only OpenAPI output without changing runtime semantics.

**Alternatives considered**:

- Add `engineer` to match older workflow execution serializers: rejected because the audit-id endpoints use the authenticated session and should not reintroduce caller-supplied identity.
- Leave approval/execution path-only: rejected because generated clients cannot know the required execution mode or action response shape.

## Decision: Document Logs And Status Response Bodies

The existing audit-id SQL Workflow logs endpoint will document a response with `total` and `rows`, and each row will include `operation_type_desc`, `operation_info`, `operator_display`, and `operation_time` plus the extension strategy. The existing status endpoint will document `status`, `msg`, and `data`, with `status` carrying the workflow status code used by watch clients.

**Rationale**: The runtime already returns these bodies, but the generated OpenAPI currently omits them. Watch and CLI clients need the schema to generate stable models.

**Alternatives considered**:

- Keep schema implicit: rejected because generated clients see no response body.
- Return only status text for watch: rejected because current runtime and clients expect the status code field.

## Decision: Tests Stay Unit-First With Minimal API Integration

Unit tests will cover the instance permission helper, public instance serializer allowlist, workflow serializer instance id mapping, and runtime serializer shapes. Integration tests will cover authenticated request dispatch and permission-denied/not-found mapping. Generated schema details may be checked with temporary scripts and do not need committed tests.

**Rationale**: This follows the constitution and keeps the suite fast while still validating the external REST contract.

**Alternatives considered**:

- Broad end-to-end tests only: rejected because they are slower and less precise for permission/serialization edge cases.
- Schema-only validation: rejected because it cannot prove runtime permission filtering or sensitive-field exclusion.
