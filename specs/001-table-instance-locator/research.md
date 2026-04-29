# Research: Table Instance Locator API

## Decision 1: Input mode and validation contract
- Decision: Request accepts exactly one of `table_name` or `table_pattern`; reject empty strings and reject requests that provide both or neither.
- Rationale: Aligns with FR-001/FR-002 and avoids ambiguous matching behavior.
- Alternatives considered:
  - Accept both fields and prioritize one: rejected because it creates hidden precedence and harder debugging.
  - Keep only `table_name`: rejected because spec explicitly requires pattern mode.

## Decision 2: Pattern semantics
- Decision: Use case-insensitive SQL-LIKE semantics (`%` and `_` wildcards), convert to safe matcher internally.
- Rationale: Familiar to DB users and easy to explain/document.
- Alternatives considered:
  - Python regex only: rejected because less predictable for non-technical API consumers.
  - Engine-native per-database pattern syntax: rejected for cross-engine consistency risk.

## Decision 3: Provider extension point
- Decision: Keep settings-based provider loading via `TABLE_INSTANCE_LOCATOR` and require provider I/O normalization into fixed response schema.
- Rationale: Preserves existing extension behavior while enforcing FR-006 fixed contracts.
- Alternatives considered:
  - Remove custom provider: rejected because extensibility is a core requirement.
  - Plugin registry with dynamic discovery: rejected for v1 complexity.

## Decision 4: Partial-failure reporting
- Decision: Return successful matches plus `summary` containing processed/succeeded/failed instance counts and failure reasons keyed by instance.
- Rationale: Satisfies FR-008 and improves diagnosability without failing the full request.
- Alternatives considered:
  - Fail-fast on first instance error: rejected because it loses useful partial results.
  - Log-only failures without API summary: rejected because user cannot distinguish no-match vs partial outage.

## Decision 5: Stable ordering
- Decision: Sort final result by `(instance_name, db_name, table_name, instance_id)` ascending.
- Rationale: Deterministic responses satisfy FR-009 and simplify client-side diffing/caching.
- Alternatives considered:
  - Keep traversal order: rejected because backend instance order can drift.
  - Sort only by instance id: rejected because readability is lower for users.

## Decision 6: Test strategy and scope
- Decision: Prioritize pytest unit tests for serializer validation, provider normalization, sorting, permission filtering, and partial-failure behavior; integration tests only for DRF wiring when unit tests cannot prove behavior.
- Rationale: Matches constitution principles II/III/IV and user test preferences.
- Alternatives considered:
  - Broad integration-first tests: rejected due to slower and brittle multi-engine setup.
