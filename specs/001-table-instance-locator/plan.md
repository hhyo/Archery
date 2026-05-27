# Implementation Plan: Table Instance Locator — 前端表定位入口 (US4)

**Branch**: `001-add-table-locator-api` | **Date**: 2026-05-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-table-instance-locator/spec.md`

## Summary

在现有 Table Instance Locator 后端 API（`POST /v1/instance/table-instances/`）基础上，在 SQL 查询页面（`sql/templates/sqlquery.html`）右侧面板实例选择器上方新增表定位输入框。用户输入 ≥1 个字符后，经 500ms 防抖自动调用表定位接口，以 `实例名/数据库名/表名` 单列格式展示匹配结果列表，支持无匹配提示与错误提示，结果供用户手动选择。

## Technical Context

**Language/Version**: Python 3.x (Django 4.x) + Vanilla JavaScript (jQuery 3, Bootstrap 3)
**Primary Dependencies**: Django REST Framework (backend, existing), jQuery, Bootstrap 3, Bootstrap Select (已引入于 sqlquery.html)
**Storage**: N/A（前端纯展示，后端已有 ORM + 引擎适配层）
**Testing**: pytest (backend unit tests via `sql_api/test_table_instance_locator.py`); 前端无独立测试框架，通过手动验收
**Target Platform**: Linux server, Django template rendered HTML page
**Project Type**: web-service — Django template frontend + DRF REST API backend
**Performance Goals**: 95% of debounced-triggered requests return within 5s for 50 instances (SC-002)
**Constraints**: CSRF token required for POST; results must be XSS-safe (escape output); input cleared → cancel pending request; 500ms debounce; min 1 character before firing
**Scale/Scope**: Single HTML template change; single JS block addition; existing API endpoint reuse

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Multi-engine compatibility impact is listed and bounded by adapter or capability layer.
  - **Impact**: 前端调用 `POST /v1/instance/table-instances/` 是引擎无关的 REST 接口；后端已通过 `get_engine()` 适配多引擎，前端变更不引入任何引擎耦合。
- [x] Test plan is unit-test-first with pytest; integration scope is explicitly minimized.
  - 后端测试已在 tasks.md T004–T023 中用 pytest 覆盖；前端 JS 通过 Django 模板手动验收，无独立测试框架引入。
- [x] Shared setup is designed via conftest.py fixtures; duplicate setup is eliminated.
  - T001 中已规划 `conftest.py` 共享 fixtures (`db_instance`, `fake_engine`, `fake_locator_request`)。
- [x] Any integration test includes a written justification for why unit tests are insufficient.
  - T023 包含 DRF auth wiring + permission filtering 的集成测试，含书面理由："DRF auth wiring + permission filtering integration cannot be fully proven via unit tests alone"。

## Project Structure

### Documentation (this feature)

```text
specs/001-table-instance-locator/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output — updated with frontend decisions
├── data-model.md        # Phase 1 output — updated with TableLocatorUIState
├── quickstart.md        # Phase 1 output — updated with frontend usage
├── contracts/
│   └── table-instance-locator.openapi.yaml  # Phase 1 output — API contract (existing)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
sql/
└── templates/
    └── sqlquery.html        # US4: 新增表定位输入框 + 结果列表 HTML/JS block

sql_api/
├── table_instance_locator.py  # US1–US3: 后端定位逻辑（已存在 v0）
├── serializers.py             # US1–US3: 请求/响应序列化（已存在 v0）
├── api_instance.py            # US1–US3: TableInstanceLookup view（已存在 v0）
├── urls.py                    # 已注册 /v1/instance/table-instances/
└── test_table_instance_locator.py  # US1–US3: pytest 单元测试

conftest.py                    # 根级 conftest — 共享 fixtures (T001)
```

**Structure Decision**: 单 Django web-service 项目，前端模板 + 后端 DRF API。
前端变更仅限 `sql/templates/sqlquery.html` 一个文件；后端变更仅限 `sql_api/` 包内。
不引入新应用或新模块。

## Complexity Tracking

> 无 Constitution 违规，此表格保持空白。
