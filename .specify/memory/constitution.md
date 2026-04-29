<!--
Sync Impact Report
- Version change: N/A (template) -> 1.0.0
- Modified principles:
	- Template Principle 1 -> I. Multi-Engine Compatibility First
	- Template Principle 2 -> II. Unit Test Priority for Engine Logic
	- Template Principle 3 -> III. Pytest Standardization and Shared Fixtures
	- Template Principle 4 -> IV. Bounded Integration Testing
	- Template Principle 5 -> V. Safe Query and Debuggability
- Added sections:
	- Testing Standards
	- Delivery Workflow & Quality Gates
- Removed sections:
	- None
- Templates requiring updates:
	- ✅ .specify/templates/plan-template.md
	- ✅ .specify/templates/spec-template.md
	- ✅ .specify/templates/tasks-template.md
	- ✅ README.md
	- ✅ .specify/templates/commands/*.md (directory not present; no update required)
- Follow-up TODOs:
	- None
-->

# Archery Constitution

## Core Principles

### I. Multi-Engine Compatibility First
All database-facing changes MUST preserve behavior across supported engines unless
an engine-specific exception is explicitly documented and approved. New logic MUST
be isolated by adapter or engine capability boundary to keep behavior deterministic.
Rationale: this platform serves heterogeneous database stacks, so compatibility is
a product-level invariant, not an optional enhancement.

### II. Unit Test Priority for Engine Logic
Changes to SQL parsing, permission checks, engine adapters, and query orchestration
MUST be covered primarily by unit tests. Integration tests SHOULD be added only for
cross-boundary behavior that cannot be validated with mocks or fakes. Rationale:
unit tests give faster, cheaper, and more stable verification across many engines.

### III. Pytest Standardization and Shared Fixtures
All new tests MUST use pytest style. Shared setup and teardown MUST be centralized
in conftest.py and reusable fixtures; duplicate setup blocks across test modules
MUST be refactored into fixtures. Rationale: fixture-driven composition reduces
duplication, improves readability, and makes cross-engine cases easier to expand.

### IV. Bounded Integration Testing
Integration tests MUST be limited to critical contracts such as ORM/middleware
integration, authentication flow boundaries, and engine driver compatibility checks.
Any new integration test MUST state why unit-level validation is insufficient.
Rationale: selective integration testing keeps pipelines efficient while guarding
high-risk interfaces.

### V. Safe Query and Debuggability
All query execution and debug flows MUST remain auditable with explicit logging,
deterministic error messages, and permission-aware safeguards. Tests for these
flows MUST assert both success and failure paths. Rationale: predictable debugging
and safe execution are core trust requirements for a database operations platform.

## Testing Standards

- Test suites MUST default to pytest invocation and naming conventions configured in
	pyproject.toml.
- Unit tests SHOULD mock external network, storage, and real engine dependencies
	unless an integration test is explicitly justified.
- conftest.py SHOULD expose canonical fixtures for users, permissions, SQL payloads,
	and engine capability flags to prevent per-file duplication.
- Engine-specific edge cases MUST be represented as parametrized pytest cases where
	feasible.

## Delivery Workflow & Quality Gates

- Every feature or bugfix PR MUST include tests aligned with the changed scope.
- Reviewers MUST reject PRs that add repeated setup boilerplate instead of shared
	fixtures.
- Reviewers MUST require explicit rationale when integration tests outnumber unit
	tests for a change set.
- Before merge, CI MUST pass for pytest suite and static checks.

## Governance

This constitution supersedes local conventions for design and test strategy.
Amendments require: (1) a documented proposal, (2) maintainer approval, and
(3) synchronized updates to dependent templates in .specify/templates/.

Versioning policy follows semantic versioning for governance:
- MAJOR: incompatible principle removals or redefinitions.
- MINOR: new principle or materially expanded mandatory guidance.
- PATCH: wording clarifications that do not alter obligations.

Compliance review is mandatory in planning and PR review. Constitution checks in
planning artifacts MUST pass or carry an explicit, approved exception record.

**Version**: 1.0.0 | **Ratified**: 2026-04-28 | **Last Amended**: 2026-04-28
