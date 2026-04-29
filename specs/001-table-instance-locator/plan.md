# Implementation Plan: Table Instance Locator API

**Branch**: `001-add-table-locator-api` | **Date**: 2026-04-28 | **Spec**: `specs/001-table-instance-locator/spec.md`
**Input**: Feature specification from `specs/001-table-instance-locator/spec.md`

## Summary

Add a fixed-contract table locator API that supports exact name and pattern search, restricted to instances the current user can query. Keep a pluggable provider entrypoint (`settings.TABLE_INSTANCE_LOCATOR`) while standardizing request/response structures, deterministic ordering, and partial-failure summaries.

## Technical Context

**Language/Version**: Python 3.x, Django 4.1.13  
**Primary Dependencies**: Django REST Framework, drf-spectacular, existing `sql.engines` adapters, `sql.utils.resource_group.user_instances`  
**Storage**: Runtime metadata from authorized database instances; no new persistent storage  
**Testing**: pytest (`test_*.py`) with fixtures from `conftest.py` and module-level fixtures  
**Target Platform**: Linux server deployment  
**Project Type**: Django web-service API  
**Performance Goals**: In typical 50 authorized instances, p95 <= 5s with partial-result fallback  
**Constraints**: Strict permission isolation, fixed schema for request/response and provider I/O, deterministic stable sort  
**Scale/Scope**: User-scoped traversal of up to dozens of instances per request; one endpoint in `sql_api`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Multi-engine compatibility impact is listed and bounded by adapter or capability layer.
- [x] Test plan is unit-test-first with pytest; integration scope is explicitly minimized.
- [x] Shared setup is designed via conftest.py fixtures; duplicate setup is eliminated.
- [x] Any integration test includes a written justification for why unit tests are insufficient.

Initial gate result: PASS.

## Phase 0 Research Decisions

1. Pattern matching contract: support exactly one of `table_name` or `table_pattern`; pattern uses SQL-LIKE style wildcards (`%`, `_`) with case-insensitive matching.
2. Partial failures: response includes `summary` object with success/failure counts and per-instance failure reasons, while still returning successful matches.
3. Stable ordering: canonical ordering is `(instance_name, db_name, table_name, instance_id)` ascending.
4. Pluggable provider compatibility: keep settings-based provider loader, but enforce normalized provider output to fixed schema before API response.

## Project Structure

### Documentation (this feature)

```text
specs/001-table-instance-locator/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── table-instance-locator.openapi.yaml
└── tasks.md
```

### Source Code (repository root)

```text
sql_api/
├── api_instance.py
├── serializers.py
├── table_instance_locator.py
├── urls.py
└── test_table_instance_locator.py

sql/
├── engines/
└── models.py

common/
└── (existing auth/middleware; unchanged by default)

conftest.py
```

**Structure Decision**: Use existing Django API module structure under `sql_api` and engine abstraction in `sql.engines`; no new top-level app or service layer introduced.

## Phase 1 Design Output Mapping

- Data model: `specs/001-table-instance-locator/data-model.md`
- API contract: `specs/001-table-instance-locator/contracts/table-instance-locator.openapi.yaml`
- Consumer/developer flow: `specs/001-table-instance-locator/quickstart.md`
- Agent context updated in `.github/copilot-instructions.md`

## Post-Design Constitution Re-Check

- [x] Multi-engine compatibility remains adapter-driven; no engine-specific hardcoding in contract.
- [x] Test design remains unit-first (serializer/provider/normalization/sort/partial-failure) with minimal integration touchpoints.
- [x] Fixture reuse is explicit in quickstart test plan (`conftest.py` + reusable fake engine fixtures).
- [x] Integration tests are optional and require written rationale.

Post-design gate result: PASS.

## Complexity Tracking

No constitution violations requiring exceptions.
