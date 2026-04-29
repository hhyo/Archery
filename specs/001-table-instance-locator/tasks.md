# Tasks: Table Instance Locator API

**Input**: Design documents from `specs/001-table-instance-locator/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

> **Context**: `sql_api/table_instance_locator.py`, `sql_api/serializers.py`, `sql_api/api_instance.py`,
> and `sql_api/test_table_instance_locator.py` already exist as a v0 implementation.
> These tasks migrate v0 to the new fixed-contract design while preserving URL and module structure.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to ([US1], [US2], [US3])

---

## Phase 1: Setup

> No new project or package setup needed. Existing Django app structure under `sql_api/` is reused.

- [ ] T001 Verify `conftest.py` exposes `db_instance` fixture and add `fake_engine` / `fake_locator_request` shared fixtures to `conftest.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define the fixed data structures shared across all user stories. Nothing in US1–US3 can be correctly implemented until these contracts are in place.

**⚠️ CRITICAL**: Complete this phase before any user story implementation begins.

- [ ] T002 Define `TableLocatorRequest`, `TableLocationItem`, and `LocatorExecutionSummary` dataclasses (or typed dicts) in `sql_api/table_instance_locator.py`; `TableLocationItem` fields: required `instance_name`, `db_type`, `db_name`; optional `instance_id`, `table_name`, `match_type`
- [ ] T003 [P] Update `sql_api/serializers.py`: replace `TableInstanceLookupSerializer` with version accepting `table_name` OR `table_pattern` (mutually exclusive, non-empty after strip, max 256); add `TableLocationItemSerializer` (required: `instance_name`, `db_type`, `db_name`; optional: `instance_id`, `table_name`, `match_type`); add `LocatorExecutionSummarySerializer` and `LocatorFailureReasonSerializer`; update `TableInstanceLookupResponseSerializer` to include `summary` field

**Checkpoint**: Data structures and serializer contracts defined — user story work can begin.

---

## Phase 3: User Story 1 - 按表名快速定位实例 (Priority: P1) 🎯 MVP

**Goal**: User submits `table_name` or `table_pattern`; system returns permission-scoped, deterministically sorted `TableLocationItem` list.

**Independent Test**:
```bash
pytest -q sql_api/test_table_instance_locator.py -k "us1 or serializer or pattern or sort or permission"
```

### Tests for User Story 1

- [ ] T004 [P] [US1] Unit tests for `TableInstanceLookupSerializer` validation in `sql_api/test_table_instance_locator.py`: exact-only accepts; pattern-only accepts; both fields rejects; neither field rejects; blank string rejects; oversized input rejects
- [ ] T005 [P] [US1] Unit tests for pattern matching helper in `sql_api/test_table_instance_locator.py`: `%` wildcard matches multi-char; `_` matches single char; case-insensitive match; exact mode rejects mismatch; pattern mode accepts partial match via `%`
- [ ] T006 [P] [US1] Unit tests for stable sort in `sql_api/test_table_instance_locator.py`: shuffled input produces deterministic order `(instance_name, db_name, table_name, instance_id)`; ties broken consistently
- [ ] T007 [P] [US1] Unit tests for permission isolation in `sql_api/test_table_instance_locator.py`: results contain only instances from the `instances` argument; no additional instance data leaks from locator output

### Implementation for User Story 1

- [ ] T008 [US1] Add `_match_table(table_name: str, candidate: str, match_mode: str) -> bool` helper to `sql_api/table_instance_locator.py` implementing case-insensitive exact and LIKE-style pattern matching (`%` → `.*`, `_` → `.`, via `re` with `re.IGNORECASE`)
- [ ] T009 [US1] Update `default_table_instance_locator` in `sql_api/table_instance_locator.py` to accept `request: TableLocatorRequest` (instead of bare `table_name`), use `_match_table` for both modes, and return `list[TableLocationItem]`; keep `break`-on-first-db-match for exact mode, scan all dbs for pattern mode
- [ ] T010 [US1] Add stable sort step to `resolve_table_instances` in `sql_api/table_instance_locator.py`: sort result by `(instance_name, db_name, table_name or "", instance_id or 0)` ascending before returning
- [ ] T011 [US1] Update `TableInstanceLookup.post` in `sql_api/api_instance.py` to build `TableLocatorRequest` from validated serializer data and pass it to `resolve_table_instances`; return `status/msg/count/data` (summary added in US3)

**Checkpoint**: US1 fully functional. `POST /v1/instance/table-instances/` accepts exact or pattern input, returns permission-scoped sorted list.

---

## Phase 4: User Story 2 - 支持可替换定位实现 (Priority: P2)

**Goal**: Provider entrypoint uses fixed `TableLocatorRequest` / `TableLocationItem` I/O contract; custom provider output is normalized to fixed schema before response.

**Independent Test**:
```bash
pytest -q sql_api/test_table_instance_locator.py -k "us2 or custom or provider or normalize"
```

### Tests for User Story 2

- [ ] T012 [P] [US2] Unit tests for provider normalization in `sql_api/test_table_instance_locator.py`: provider output missing `instance_name` is rejected from result; `db_type` and `db_name` missing triggers item rejection; optional fields absent are omitted from output (not set to `None`); items passing all required fields are retained
- [ ] T013 [P] [US2] Unit tests for custom provider loading in `sql_api/test_table_instance_locator.py`: `settings.TABLE_INSTANCE_LOCATOR` pointing to a callable uses it; custom provider receives `TableLocatorRequest` argument; output is normalized through fixed schema; invalid path raises `RuntimeError`

### Implementation for User Story 2

- [ ] T014 [US2] Update `resolve_table_instances` in `sql_api/table_instance_locator.py` to accept `request: TableLocatorRequest` and pass it to both default and custom providers; update normalization to validate required fields (`instance_name`, `db_type`, `db_name` non-empty) and reject non-conforming items; omit optional fields when absent rather than defaulting to empty/zero
- [ ] T015 [US2] Update `_load_custom_locator` in `sql_api/table_instance_locator.py` to document expected provider signature: `(request: TableLocatorRequest, instances: Iterable[Instance], **kwargs) -> tuple[list[TableLocationItem], LocatorExecutionSummary]`

**Checkpoint**: US1 + US2 functional. Custom providers conforming to new contract work without caller changes.

---

## Phase 5: User Story 3 - 无结果与异常可解释反馈 (Priority: P3)

**Goal**: Partial instance failures are tracked in `LocatorExecutionSummary` and returned with every response; empty and no-permission results are distinguishable.

**Independent Test**:
```bash
pytest -q sql_api/test_table_instance_locator.py -k "us3 or summary or partial or empty or no_permission"
```

### Tests for User Story 3

- [ ] T016 [P] [US3] Unit tests for partial failure summary in `sql_api/test_table_instance_locator.py`: instance engine error is recorded in `failure_reasons`; `failed_instance_count` increments per failed instance; successful instances still appear in result; `processed = success + failed`
- [ ] T017 [P] [US3] Unit tests for empty and no-permission responses in `sql_api/test_table_instance_locator.py`: zero-permission input returns empty list + summary with `processed_instance_count=0`; no-match input returns empty `data` list + summary reflecting all instances processed; response `status=0` in both cases

### Implementation for User Story 3

- [ ] T018 [US3] Update `default_table_instance_locator` in `sql_api/table_instance_locator.py` to track per-instance failure reasons (engine error, database list error, table list error) and return `tuple[list[TableLocationItem], LocatorExecutionSummary]` with `processed/success/failed` counts and `failure_reasons` list
- [ ] T019 [US3] Update `resolve_table_instances` in `sql_api/table_instance_locator.py` to always return `tuple[list[TableLocationItem], LocatorExecutionSummary]`; require all providers (default and custom) to return this tuple; raise `ValueError` if provider returns a bare list
- [ ] T020 [US3] Update `TableInstanceLookup.post` in `sql_api/api_instance.py` to unpack `(data, summary)` from `resolve_table_instances`; include `summary` in response body; preserve `status=0` for empty results; return `status=1` only on unrecoverable exceptions

**Checkpoint**: All three user stories functional. Partial failures surface in summary without breaking the response.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T021 [P] Update `TableInstanceLookupResponseSerializer` in `sql_api/serializers.py` to add `summary` field using `LocatorExecutionSummarySerializer` and verify `@extend_schema` annotations on `TableInstanceLookup` still reference correct serializers in `sql_api/api_instance.py`
- [ ] T022 [P] Run full test suite for the module and fix any failures: `pytest -q sql_api/test_table_instance_locator.py`
- [ ] T023 Validate quickstart.md scenarios manually or via integration test in `sql_api/test_table_instance_locator.py` (rationale: DRF auth wiring + permission filtering integration cannot be fully proven via unit tests alone); mark with `@pytest.mark.django_db` and include rationale in docstring

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup / conftest)
    └─► Phase 2 (Data structures + Serializers) — blocks everything
            └─► Phase 3 US1 (Pattern match, sort, serializer)
                    └─► Phase 4 US2 (Provider contract, normalization)
                            └─► Phase 5 US3 (Summary, partial failure)
                                    └─► Phase 6 (Polish)
```

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2 only. No dependency on US2 or US3. Can deliver MVP independently.
- **US2 (P2)**: Depends on Phase 2 + US1 data structures. Provider must use `TableLocatorRequest` defined in Phase 2.
- **US3 (P3)**: Depends on US1 implementation of `default_table_instance_locator` and US2 `resolve_table_instances` return type.

### Within Each User Story

- Tests (T004–T007, T012–T013, T016–T017) are written **before** implementation and must fail first.
- Within each story: serializer/helper tasks before core logic; core logic before view layer.
- Parallel tasks marked [P] touch different logical sections; sequence within each group is top-to-bottom.

### Parallel Opportunities

- T002 (dataclasses in `table_instance_locator.py`) ‖ T003 (serializers in `serializers.py`) — different files
- Within US1: T004 ‖ T005 ‖ T006 ‖ T007 — all in test file, independent test cases
- Within US2: T012 ‖ T013 — independent test cases
- Within US3: T016 ‖ T017 — independent test cases
- T021 ‖ T022 in Polish phase

---

## Implementation Strategy

**MVP (deliver US1 alone)**:
1. Complete Phase 1 + Phase 2
2. Complete Phase 3 (T004–T011)
3. Endpoint functional for exact + pattern search with stable output

**Incremental delivery**:
- Add US2 (T012–T015): custom provider ecosystem support
- Add US3 (T016–T020): observability and partial-failure UX
- Polish (T021–T023): schema docs and integration validation

**Total tasks**: 23  
**Tasks per story**: US1 = 8, US2 = 4, US3 = 5, Foundational = 3, Polish = 3  
**Parallel opportunities**: 10 tasks marked [P]
