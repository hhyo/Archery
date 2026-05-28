# Tasks: Table Instance Locator API + 前端表定位入口

**Input**: Design documents from `specs/001-table-instance-locator/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

> **Context**: `sql_api/table_instance_locator.py`, `sql_api/serializers.py`, `sql_api/api_instance.py`,
> and `sql_api/test_table_instance_locator.py` already exist as a v0 implementation.
> These tasks migrate v0 to the new fixed-contract design while preserving URL and module structure.
> US4 adds a table-locator input widget to `sql/templates/sqlquery.html`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to ([US1], [US2], [US3], [US4])

---

## Phase 1: Setup

> No new project or package setup needed. Existing Django app structure under `sql_api/` is reused.

- [X] T001 Verify `conftest.py` exposes `db_instance` fixture and add `fake_engine` / `fake_locator_request` shared fixtures to `conftest.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define the fixed data structures shared across all user stories. Nothing in US1–US3 can be correctly implemented until these contracts are in place.

**⚠️ CRITICAL**: Complete this phase before any user story implementation begins.

- [X] T002 Define `TableLocatorRequest`, `TableLocationItem`, and `LocatorExecutionSummary` dataclasses (or typed dicts) in `sql_api/table_instance_locator.py`; `TableLocationItem` fields: required `instance_name`, `db_type`, `db_name`; optional `instance_id`, `table_name`, `match_type`
- [X] T003 [P] Update `sql_api/serializers.py`: replace `TableInstanceLookupSerializer` with version accepting `table_name` OR `table_pattern` (mutually exclusive, non-empty after strip, max 256); add `TableLocationItemSerializer` (required: `instance_name`, `db_type`, `db_name`; optional: `instance_id`, `table_name`, `match_type`); add `LocatorExecutionSummarySerializer` and `LocatorFailureReasonSerializer`; update `TableInstanceLookupResponseSerializer` to include `summary` field

**Checkpoint**: Data structures and serializer contracts defined — user story work can begin.

---

## Phase 3: User Story 1 - 按表名快速定位实例 (Priority: P1) 🎯 MVP

**Goal**: User submits `table_name` or `table_pattern`; system returns permission-scoped, deterministically sorted `TableLocationItem` list.

**Independent Test**:
```bash
pytest -q sql_api/test_table_instance_locator.py -k "us1 or serializer or pattern or sort or permission"
```

### Tests for User Story 1

- [X] T004 [P] [US1] Unit tests for `TableInstanceLookupSerializer` validation in `sql_api/test_table_instance_locator.py`: exact-only accepts; pattern-only accepts; both fields rejects; neither field rejects; blank string rejects; oversized input rejects
- [X] T005 [P] [US1] Unit tests for pattern matching helper in `sql_api/test_table_instance_locator.py`: `%` wildcard matches multi-char; `_` matches single char; case-insensitive match; exact mode rejects mismatch; pattern mode accepts partial match via `%`
- [X] T006 [P] [US1] Unit tests for stable sort in `sql_api/test_table_instance_locator.py`: shuffled input produces deterministic order `(instance_name, db_name, table_name, instance_id)`; ties broken consistently
- [X] T007 [P] [US1] Unit tests for permission isolation in `sql_api/test_table_instance_locator.py`: results contain only instances from the `instances` argument; no additional instance data leaks from locator output

### Implementation for User Story 1

- [X] T008 [US1] Add `_match_table(table_name: str, candidate: str, match_mode: str) -> bool` helper to `sql_api/table_instance_locator.py` implementing case-insensitive exact and LIKE-style pattern matching (`%` → `.*`, `_` → `.`, via `re` with `re.IGNORECASE`)
- [X] T009 [US1] Update `default_table_instance_locator` in `sql_api/table_instance_locator.py` to accept `request: TableLocatorRequest` (instead of bare `table_name`), use `_match_table` for both modes, and return `list[TableLocationItem]`; keep `break`-on-first-db-match for exact mode, scan all dbs for pattern mode
- [X] T010 [US1] Add stable sort step to `resolve_table_instances` in `sql_api/table_instance_locator.py`: sort result by `(instance_name, db_name, table_name or "", instance_id or 0)` ascending before returning
- [X] T011 [US1] Update `TableInstanceLookup.post` in `sql_api/api_instance.py` to build `TableLocatorRequest` from validated serializer data and pass it to `resolve_table_instances`; return `status/msg/count/data` (summary added in US3)

**Checkpoint**: US1 fully functional. `POST /v1/instance/table-instances/` accepts exact or pattern input, returns permission-scoped sorted list.

---

## Phase 4: User Story 2 - 支持可替换定位实现 (Priority: P2)

**Goal**: Provider entrypoint uses fixed `TableLocatorRequest` / `TableLocationItem` I/O contract; custom provider output is normalized to fixed schema before response.

**Independent Test**:
```bash
pytest -q sql_api/test_table_instance_locator.py -k "us2 or custom or provider or normalize"
```

### Tests for User Story 2

- [X] T12 [P] [US2] Unit tests for provider normalization in `sql_api/test_table_instance_locator.py`: provider output missing `instance_name` is rejected from result; `db_type` and `db_name` missing triggers item rejection; optional fields absent are omitted from output (not set to `None`); items passing all required fields are retained
- [X] T13 [P] [US2] Unit tests for custom provider loading in `sql_api/test_table_instance_locator.py`: `settings.TABLE_INSTANCE_LOCATOR` pointing to a callable uses it; custom provider receives `TableLocatorRequest` argument; output is normalized through fixed schema; invalid path raises `RuntimeError`

### Implementation for User Story 2

- [X] T14 [US2] Update `resolve_table_instances` in `sql_api/table_instance_locator.py` to accept `request: TableLocatorRequest` and pass it to both default and custom providers; update normalization to validate required fields (`instance_name`, `db_type`, `db_name` non-empty) and reject non-conforming items; omit optional fields when absent rather than defaulting to empty/zero
- [X] T15 [US2] Update `_load_custom_locator` in `sql_api/table_instance_locator.py` to document expected provider signature: `(request: TableLocatorRequest, instances: Iterable[Instance], **kwargs) -> tuple[list[TableLocationItem], LocatorExecutionSummary]`

**Checkpoint**: US1 + US2 functional. Custom providers conforming to new contract work without caller changes.

---

## Phase 5: User Story 3 - 无结果与异常可解释反馈 (Priority: P3)

**Goal**: Partial instance failures are tracked in `LocatorExecutionSummary` and returned with every response; empty and no-permission results are distinguishable.

**Independent Test**:
```bash
pytest -q sql_api/test_table_instance_locator.py -k "us3 or summary or partial or empty or no_permission"
```

### Tests for User Story 3

- [X] T16 [P] [US3] Unit tests for partial failure summary in `sql_api/test_table_instance_locator.py`: instance engine error is recorded in `failure_reasons`; `failed_instance_count` increments per failed instance; successful instances still appear in result; `processed = success + failed`
- [X] T17 [P] [US3] Unit tests for empty and no-permission responses in `sql_api/test_table_instance_locator.py`: zero-permission input returns empty list + summary with `processed_instance_count=0`; no-match input returns empty `data` list + summary reflecting all instances processed; response `status=0` in both cases

### Implementation for User Story 3

- [X] T18 [US3] Update `default_table_instance_locator` in `sql_api/table_instance_locator.py` to track per-instance failure reasons (engine error, database list error, table list error) and return `tuple[list[TableLocationItem], LocatorExecutionSummary]` with `processed/success/failed` counts and `failure_reasons` list
- [X] T19 [US3] Update `resolve_table_instances` in `sql_api/table_instance_locator.py` to always return `tuple[list[TableLocationItem], LocatorExecutionSummary]`; require all providers (default and custom) to return this tuple; raise `ValueError` if provider returns a bare list
- [X] T20 [US3] Update `TableInstanceLookup.post` in `sql_api/api_instance.py` to unpack `(data, summary)` from `resolve_table_instances`; include `summary` in response body; preserve `status=0` for empty results; return `status=1` only on unrecoverable exceptions

**Checkpoint**: All three backend user stories functional. Partial failures surface in summary without breaking the response.

---

## Phase 6: User Story 4 - 前端表定位入口 (Priority: P2)

**Goal**: SQL 查询页面右侧面板新增表定位输入框，输入 ≥1 字符后 500ms 防抖自动调用 `POST /v1/instance/table-instances/`，以 `实例名/数据库名/表名` 格式展示匹配结果列表。

**Independent Test**: 手动验收（见 quickstart.md §5）—— 在 `/sqlquery/` 页面输入表名，确认结果列表渲染正确；清空输入确认结果列表清空；网络请求失败确认错误提示显示。

> **Dependency**: 需要 US1（Phase 3）完成后 `POST /v1/instance/table-instances/` 可用；与 US2/US3 无阻塞依赖。

### Implementation for User Story 4

- [X] T21 [US4] In `sql/templates/sqlquery.html`, insert `#div-table-locator` HTML block in the `col-md-3` panel **immediately before** the `#instance_name` form-group div: `<div class="form-group" id="div-table-locator">` containing `<input id="table-locator-input" type="text" class="form-control" placeholder="按表名定位实例（如 orders）" autocomplete="off"/>`, `<div id="table-locator-loading" style="display:none"><small class="text-muted">查询中...</small></div>`, and `<ul id="table-locator-results" class="list-unstyled" style="max-height:160px;overflow-y:auto;margin-top:4px;"></ul>`

- [X] T22 [US4] In `sql/templates/sqlquery.html` `{% block js %}`, add `locateTable()` JS function: declares module-scoped `var _locatorXHR = null`; aborts pending `_locatorXHR` before sending; shows `#table-locator-loading`; POSTs `{table_name: value}` to `/v1/instance/table-instances/` (CSRF token handled globally by `base.html` `$.ajaxSetup`); on `complete` hides loading + sets `_locatorXHR = null`; on `success` renders each result item as `$('<li>').text(item.name + '/' + item.db_name + '/' + (item.table_name || ''))` (text node — no innerHTML); on `status=0` with empty data renders `$('<li class="text-muted">').text('无匹配结果')`; on `status!=0` or `error` (excluding `abort`) renders `$('<li class="text-danger">').text(data.msg || '请求失败')`

- [X] T23 [US4] In `sql/templates/sqlquery.html` `{% block js %}`, add `#table-locator-input` event handler: `$('#table-locator-input').on('input', function() {...})`; uses module-scoped `var _locatorTimer = null`; on each input event: `clearTimeout(_locatorTimer)`; if `val.trim() === ''` aborts `_locatorXHR` + clears `_locatorXHR = null` + empties `#table-locator-results` + hides `#table-locator-loading` and returns; if `val.trim().length >= 1` sets `_locatorTimer = setTimeout(function(){ locateTable(); }, 500)`

**Checkpoint**: US4 手动验收通过 — 输入触发查询、防抖生效、结果列表正确渲染、清空正确中止请求。

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T024 [P] Update `TableInstanceLookupResponseSerializer` in `sql_api/serializers.py` to add `summary` field using `LocatorExecutionSummarySerializer` and verify `@extend_schema` annotations on `TableInstanceLookup` still reference correct serializers in `sql_api/api_instance.py`
- [X] T025 [P] Run full test suite for the module and fix any failures: `pytest -q sql_api/test_table_instance_locator.py`
- [X] T026 Validate quickstart.md scenarios manually or via integration test in `sql_api/test_table_instance_locator.py` (rationale: DRF auth wiring + permission filtering integration cannot be fully proven via unit tests alone); mark with `@pytest.mark.django_db` and include rationale in docstring

---

## Phase 8: User Story 4 扩展 - 点击结果自动填充表单 (Session 2026-05-28)

**Goal**: 结果项可点击，点击后自动填充实例/数据库/表三个 selectpicker；若实例不在当前资源组则内联提示不填充；后端同步返回 `table_name` 字段。

> **依赖**: Phase 6 (T21–T23) 已完成；T027/T028 为后端改动，可与 T029–T031 并行。

### Backend: FR-015 — 返回 table_name 字段

- [X] T027 [P] [US4] Update `default_table_instance_locator` in `sql_api/table_instance_locator.py`: replace `any()` check with a loop capturing the matched `table_name`; include `table_name` key in each appended result dict
- [X] T028 [P] [US4] Add `table_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)` to `TableInstanceSerializer` in `sql_api/serializers.py`; also pass `"table_name": item.get("table_name", "")` in the normalization dict of `resolve_table_instances`

### Frontend: FR-013/FR-014 — 点击结果自动填充

- [X] T029 [US4] In `sql/templates/sqlquery.html` `locateTable()`: add `data-instance`, `data-db`, `data-table` attributes on each `<li>` via `.data()`; add hover highlight via `.hover()`; add `cursor: pointer` style to clickable items

- [X] T030 [US4] In `sql/templates/sqlquery.html` `<!-- 表定位 -->` script block, add delegated click handler `$('#table-locator-results').on('click', 'li', ...)`:
  - (FR-014) If `$('#instance_name option[value="instanceName"]').length === 0`: append `<small class="text-warning locator-warning">该实例不在当前资源组</small>` to the `<li>`; return
  - Empty `#table-locator-results`; cancel pending fill: `clearInterval(_fillPollTimer); _pendingTableName = null`
  - Set `#instance_name` selectpicker to `instanceName`; trigger `change`
  - Poll `#db_name option[value="dbName"]` every 200ms (max 30 iterations); on found: set `#db_name` value, trigger `change`
  - Poll `#table_name option[value="tableName"]` every 200ms (max 30 iterations); cancel if `_pendingTableName === null`; on found: set `#table_name` value + `selectpicker('refresh')`

- [X] T031 [US4] In `$('#table-locator-input').on('input', ...)` handler: on each keystroke add `clearInterval(_fillPollTimer); _pendingTableName = null` to cancel any in-progress autofill when user starts a new search

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup / conftest)
    └─► Phase 2 (Data structures + Serializers) — blocks US1/US2/US3
            └─► Phase 3 US1 (Pattern match, sort, serializer)  ──┐
                    └─► Phase 4 US2 (Provider contract)           │ independent
                            └─► Phase 5 US3 (Summary/partial)     │ of US4
                    └─► Phase 6 US4 (Frontend widget) ────────────┘
                            └─► Phase 7 (Polish)
                            └─► Phase 8 (US4 autofill — T027–T031)
```

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2 only. No dependency on US2/US3/US4. Delivers MVP independently.
- **US2 (P2)**: Depends on Phase 2 + US1 data structures. Provider must use `TableLocatorRequest`.
- **US3 (P3)**: Depends on US1 implementation of `default_table_instance_locator` + US2 `resolve_table_instances` return type.
- **US4 (P2)**: Depends on US1 (`POST /v1/instance/table-instances/` available). Independent of US2/US3.

### Within Each User Story

- Tests (T004–T007, T012–T013, T016–T017) are written **before** implementation and must fail first.
- Within each backend story: serializer/helper tasks before core logic; core logic before view layer.
- US4: HTML structure (T021) → JS function (T022) → JS event handler (T023) — sequential within single file.
- Parallel tasks marked [P] touch different logical sections; sequence within each group is top-to-bottom.

### Parallel Opportunities

- T002 (dataclasses in `table_instance_locator.py`) ‖ T003 (serializers in `serializers.py`) — different files
- Within US1: T004 ‖ T005 ‖ T006 ‖ T007 — all in test file, independent test cases
- Within US2: T012 ‖ T013 — independent test cases
- Within US3: T016 ‖ T017 — independent test cases
- Phase 3 US1 (T004–T011) ‖ Phase 6 US4 (T021–T023) — completely different files
- T027 ‖ T028 (backend FR-015) ‖ T029–T031 (frontend FR-013/014) — different files
- T024 ‖ T025 in Polish phase

---

## Implementation Strategy

**MVP (deliver US1 + US4 alone)**:
1. Complete Phase 1 + Phase 2
2. Complete Phase 3 (T004–T011) — backend API functional
3. Complete Phase 6 (T021–T023) — frontend widget callable
4. Endpoint + UI fully functional for exact search with stable output

**Incremental delivery**:
- Add US2 (T012–T015): custom provider ecosystem support
- Add US3 (T016–T020): observability and partial-failure UX
- Polish (T024–T026): schema docs and integration validation

**Total tasks**: 31
**Tasks per story**: US1 = 8, US2 = 4, US3 = 5, US4 = 8 (T021–T023 + T027–T031), Foundational = 3, Polish = 3
**Parallel opportunities**: 13 tasks marked [P]
**Independent test criteria**:
- US1: `pytest -q sql_api/test_table_instance_locator.py -k "us1 or serializer or pattern or sort or permission"`
- US2: `pytest -q sql_api/test_table_instance_locator.py -k "us2 or custom or provider or normalize"`
- US3: `pytest -q sql_api/test_table_instance_locator.py -k "us3 or summary or partial or empty or no_permission"`
- US4: 手动验收 — `/sqlquery/` 页面输入表名确认结果渲染（见 quickstart.md §5）


