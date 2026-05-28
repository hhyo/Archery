# Implementation Plan: Table Instance Locator API + 前端表定位入口

**Branch**: `001-add-table-locator-api` | **Date**: 2026-05-28 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/001-table-instance-locator/spec.md`

## Summary

新增"表定位"能力：用户输入表名，系统遍历当前用户有查询权限的实例，返回包含该表的 `(实例, 数据库, 表名)` 三元组列表。  
后端通过 DRF `POST /api/v1/instance/table-instances/` 提供固定契约接口，支持可替换实现（`settings.TABLE_INSTANCE_LOCATOR`），返回含部分失败摘要的 `summary` 字段。  
前端在 `sql/templates/sqlquery.html` 的实例选择器上方新增防抖输入框（500ms），展示 `实例名/数据库名/表名` 单列结果列表，用户点击结果项后**自动填充**实例、数据库、表三个 selectpicker（FR-013/014），并在实例不在当前资源组时提示内联警告（FR-014）。

## Technical Context

**Language/Version**: Python 3.x, Django 4.x (DRF)；前端 jQuery 3 + Bootstrap 3 + Bootstrap Select  
**Primary Dependencies**: djangorestframework, drf-spectacular, mysqlclient, sql.engines adapter layer  
**Storage**: N/A (read-only metadata query over existing instance connections)  
**Testing**: pytest + Django TestCase；conftest.py shared fixtures  
**Target Platform**: Linux server（Django web application）  
**Project Type**: web-service (DRF API) + Django template frontend  
**Performance Goals**: 50 实例场景下 95% 请求 ≤5 秒（SC-002）  
**Constraints**: 遍历实例为串行 IO；结果按 `(instance_name, db_name, table_name, instance_id)` 稳定排序  
**Scale/Scope**: 单用户最多数十个授权实例；前端单页面小组件

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Multi-engine compatibility impact is listed and bounded by adapter or capability layer.  
  *All engine queries go through `sql.engines.get_engine(instance=...)` adapter; no engine-specific code in locator.*
- [x] Test plan is unit-test-first with pytest; integration scope is explicitly minimized.  
  *Unit tests cover serializer, pattern matching, sort, permission, partial-failure; one integration test (T026) for DRF auth wiring with justification.*
- [x] Shared setup is designed via conftest.py fixtures; duplicate setup is eliminated.  
  *`conftest.py` provides `db_instance`, `fake_engine`, `fake_locator_request` fixtures.*
- [x] Any integration test includes a written justification for why unit tests are insufficient.  
  *T026 docstring: "DRF auth wiring + permission filtering integration cannot be fully proven via unit tests alone."*

## Project Structure

### Documentation (this feature)

```text
specs/001-table-instance-locator/
├── plan.md              # This file
├── research.md          # Phase 0: decisions on input contract, pattern semantics, provider extension, frontend UX
├── data-model.md        # Phase 1: TableLocatorRequest, TableLocationItem, LocatorExecutionSummary, TableLocatorUIState
├── quickstart.md        # Phase 1: manual verification steps for US1–US4
├── contracts/           # Phase 1: API request/response schema
└── tasks.md             # Phase 2: T001–T031 implementation tasks
```

### Source Code (repository root)

```text
sql_api/
├── table_instance_locator.py   # Core locator logic: default impl, provider loading, normalization
├── api_instance.py             # DRF view: TableInstanceLookup (POST /api/v1/instance/table-instances/)
├── serializers.py              # Request/response serializers including TableInstanceSerializer
├── urls.py                     # Route: v1/instance/table-instances/
├── test_table_instance_locator.py  # Unit + integration tests (pytest)
└── tests.py

sql/
└── templates/
    └── sqlquery.html           # US4: #div-table-locator widget + locateTable() JS + click autofill

archery/
└── urls.py                     # Root: path("api/", include(sql_api.urls)) — full URL /api/v1/...
```

## Complexity Tracking

No constitution violations. All gate checks pass.

---

## Phase 0: Research Summary

See [research.md](research.md) for full decision log. Key decisions:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Input mode | `table_name` (exact) XOR `table_pattern` (LIKE-style) | FR-001/002; avoids ambiguity |
| Pattern semantics | SQL-LIKE `%`/`_` via regex with `re.IGNORECASE` | Familiar to DB users; cross-engine consistent |
| Provider extension | `settings.TABLE_INSTANCE_LOCATOR` callable; I/O normalized to fixed schema | FR-006; preserves extensibility without protocol drift |
| Partial failure | Continue on per-instance errors; return `summary` with failure reasons | FR-008; partial results > no results |
| Stable ordering | Sort by `(instance_name, db_name, table_name, instance_id)` | FR-009; deterministic responses |
| Frontend trigger | 500ms debounce, ≥1 char, `$.ajax` POST | Matches existing jQuery style; avoids request flood |
| Frontend result format | `实例名/数据库名/表名` single-column `<li>` items | User confirmed; lowest complexity |
| Click-to-autofill | Poll `#db_name`/`#table_name` options after triggering `#instance_name` change | Non-invasive; no modifications to existing `get_instance()` |
| XSS safety | `$('<li>').text(value)` text nodes only; never innerHTML | OWASP A03 |

---

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) and [contracts/](contracts/) for full schema.

### Key entities

- **`TableLocatorRequest`**: `table_name` XOR `table_pattern`; `match_mode` derived; `request_user_id` from auth context
- **`TableLocationItem`**: required `instance_name`, `db_type`, `db_name`; optional `instance_id`, `table_name`, `match_type`  
  — `table_name` is returned by backend (FR-015) and used by frontend autofill (FR-013)
- **`LocatorExecutionSummary`**: `processed/success/failed` counts + `failure_reasons[]`
- **`TableLocatorUIState`**: `inputValue`, `debounceTimer`, `pendingXHR`, `_pendingTableName`, `_fillPollTimer`

### API contract

```
POST /api/v1/instance/table-instances/
Content-Type: application/json
Body: {"table_name": "orders"}  OR  {"table_pattern": "ord%"}

Response 200:
{
  "status": 0,           // 0=ok, 1=error
  "msg": "查询成功",
  "count": 2,
  "data": [
    {"name": "prod-mysql", "db_type": "MySQL", "db_name": "shop", "table_name": "orders", "id": 1}
  ],
  "summary": {
    "processed_instance_count": 5,
    "successful_instance_count": 4,
    "failed_instance_count": 1,
    "failure_reasons": [{"instance_name": "dev-mysql", "reason": "connection refused"}]
  }
}
```

### Frontend autofill flow (FR-013/014)

1. User clicks `<li>` result item carrying `data-instance`, `data-db`, `data-table` attributes
2. Check if `instance_name` exists in `#instance_name option[value="..."]`
   - **Not found** → show inline `<small class="text-warning">该实例不在当前资源组</small>` on the `<li>`; return
3. Empty `#table-locator-results`; cancel pending fill: `clearInterval(_fillPollTimer); _pendingTableName = null`
4. Set `#instance_name` selectpicker value; trigger `change` → `get_instance()` runs async, loads DB list
5. Poll `#db_name option[value="<dbName>"]` every 200ms (max 30 × = 6s)
6. When found: set `#db_name` + trigger `change` → existing handler loads table list
7. If `tableName` present: poll `#table_name option[value="<tableName>"]` every 200ms (max 30×)
   - Cancel if `_pendingTableName` is reset to `null` (user started new search)
8. When found: `$('#table_name').selectpicker('val', tableName).selectpicker('refresh')`

