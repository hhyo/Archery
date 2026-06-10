# Implementation Plan: SQLQuery Interface Unification

**Branch**: `002-migrate-sqlquery-drf` | **Date**: 2026-05-29 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/002-migrate-sqlquery-api/spec.md`

## Summary

将 SQL 查询页面涉及的 6 个接口迁移为 DRF 实现，并采用“后端优先兼容”策略：
在 `sql_api` 新增面向 SQLQuery 场景的 DRF 视图与序列化器，抽取现有 `sql.query`、`sql.instance`、`sql.resource_group` 中的业务逻辑到可复用服务层；
对当前页面保留旧 URL 兼容别名或直接将旧路由重绑到 DRF 视图，尽量不改前端调用代码，同时允许未来逐步切换到新的 `/api/v1/sqlquery/...` 规范化路径。

## Technical Context

**Language/Version**: Python 3.x, Django 4.x, Django REST Framework；前端为 jQuery 3 + Bootstrap 3 + Bootstrap Table  
**Primary Dependencies**: djangorestframework, drf-spectacular, django_filters, django-q, mysqlclient, `sql.engines` adapter layer  
**Storage**: 复用现有 Archery MySQL（查询日志等）与外部数据库连接；不引入新存储  
**Testing**: pytest + Django test client + DRF APIClient；保留现有 `sql/tests.py` 页面回归，新增 `sql_api` 聚焦测试  
**Target Platform**: Linux server 上的 Django Web 应用
**Project Type**: 服务端渲染 Web 应用 + DRF backend  
**Performance Goals**: 元数据读取接口不增加额外前端请求轮次；迁移后后端封装层相对现有路径的额外开销控制在可忽略范围；查询执行主耗时仍由引擎执行决定  
**Constraints**: 尽量不改前端模板；页面接口不能直接沿用 `IsInUserWhitelist` 默认权限；必须保留多引擎行为、权限校验、脱敏、超时终止和查询日志语义；允许 URL 与响应契约调整，但页面兼容优先  
**Scale/Scope**: 一个页面上的 6 个用户能力；预计 5 个规范化 DRF endpoint + 若干 legacy alias；前端改动限定在必要的最小兼容适配

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Multi-engine compatibility impact is listed and bounded by adapter or capability layer.  
  *查询执行、database/table 资源读取仍统一走 `sql.engines.get_engine()` 与既有 adapter，不在 DRF 层引入引擎分支。*
- [x] Test plan is unit-test-first with pytest; integration scope is explicitly minimized.  
  *优先验证 serializer、permission、service 和 envelope 兼容；仅对 DRF auth/permission 与 legacy alias 绑定做少量集成测试。*
- [x] Shared setup is designed via conftest.py fixtures; duplicate setup is eliminated.  
  *新增 SQLQuery API 测试复用用户、实例、权限、QueryLog、fake engine fixture，避免在 `sql_api` 和 `sql/tests.py` 重复初始化。*
- [x] Any integration test includes a written justification for why unit tests are insufficient.  
  *仅在 HTTP → SessionAuthentication → DRF permission → service 层边界无法通过 unit test 充分证明时增加，并要求测试注释说明理由。*

## Project Structure

### Documentation (this feature)

```text
specs/002-migrate-sqlquery-api/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── sqlquery-api.openapi.yaml
└── tasks.md
```

### Source Code (repository root)

```text
sql_api/
├── api_sqlquery.py              # 新增：6 个 SQLQuery 场景 DRF 视图
├── serializers.py               # 扩展：请求/响应 serializer
├── urls.py                      # 新增规范化 sqlquery 路由
├── permissions.py               # 可能新增页面场景 permission helper
└── test_sqlquery_api.py         # 新增 pytest 单元/集成测试

sql/
├── query.py                     # 保留或瘦身：legacy view/wrapper 复用 service
├── instance.py                  # 资源读取 legacy view 兼容层
├── resource_group.py            # 实例列表 legacy view 兼容层
├── urls.py                      # legacy URL 绑定到 DRF view 或兼容 wrapper
└── tests.py                     # 页面 smoke / legacy URL 回归

sql/templates/
└── sqlquery.html                # 仅在必要时做最小 URL/参数适配
```

**Structure Decision**: 选择现有 Django Web 应用结构；主要变更集中在 `sql_api/` 新增场景视图，并通过 `sql/urls.py` 和少量 legacy wrapper 吸收兼容需求，避免大规模前端改动。

## Complexity Tracking

No constitution violations. All gate checks pass.

---

## Phase 0: Research Summary

See [research.md](research.md) for full decision log. Key decisions:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Migration seam | DRF view + shared backend service extraction | 把重构集中在后端，避免把复杂逻辑继续留在 template AJAX 对应的函数视图中 |
| URL strategy | 提供 `/api/v1/sqlquery/...` 规范化路径，同时保留旧 URL 兼容别名 | 兼顾长期可维护性与“尽量不改前端” |
| Permission model | 页面场景接口使用 `IsAuthenticated` + endpoint-specific Django permission/resource checks，不使用默认 whitelist | 当前 `sql_api` 默认白名单会阻塞普通页面用户 |
| Response compatibility | 分 endpoint 保留旧 envelope（如 `status/msg/data`、`total/rows`） | 历史列表与查询执行的前端解析方式不同，不能用单一全局 renderer 粗暴统一 |
| Resource contract | 资源读取以 `instance_name` + `resource_type` 为主，保留可选 `schema_name` 兼容 PgSQL | 用户范围只要求 instance/database/table，但现有 PgSQL 流程依赖 schema |
| Frontend change budget | 默认不改模板中的业务流程，只在必须时改 URL 或参数名 | 满足用户“变更尽量集中在后端”的要求 |

---

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) and [contracts/sqlquery-api.openapi.yaml](contracts/sqlquery-api.openapi.yaml) for full schema.

### Key entities

- **`AccessibleInstanceItem`**: 当前用户可访问的实例摘要，最少包含 `id/type/db_type/instance_name`
- **`InstanceResourceRequest`**: 资源联动请求，核心字段为 `instance_name`、`resource_type`、可选 `db_name/schema_name`
- **`SqlQueryExecutionRequest`**: 查询执行输入，包含实例、database、可选 schema/table、SQL 文本和行数上限
- **`QueryLogItem`**: 历史查询列表单行记录，保留 bootstrap-table 依赖字段
- **`FavoriteMutationRequest`**: 收藏/取消收藏动作，包含 `query_log_id`、`star`、`alias`

### API contracts

规范化 DRF endpoint：

- `GET /api/v1/sqlquery/instances/`
- `GET /api/v1/sqlquery/resources/`
- `POST /api/v1/sqlquery/execute/`
- `GET /api/v1/sqlquery/logs/`
- `POST /api/v1/sqlquery/favorites/`

兼容 alias（供当前页面继续调用）：

- `GET /group/user_all_instances/`
- `GET /instance/instance_resource/`
- `POST /query/`
- `GET /query/querylog/`
- `POST /query/favorite/`

### Frontend compatibility strategy

1. 页面优先继续使用现有 URL 与 envelope；后端将 legacy route 指向 DRF view 或兼容 wrapper。  
2. 仅当 legacy 路由全局复用成本过高时，才在 `sqlquery.html` 中做集中式 URL 替换。  
3. 对 `querylog` 保留 `total/rows` 分页结构；对执行查询和收藏保留 `status/msg/data` 风格，避免重写现有 JS 分支。  
4. `schema_name` 作为可选字段继续接受，避免破坏 PgSQL 的现有前端交互。

### Post-design constitution check

- [x] Multi-engine compatibility remains inside engine adapters and shared query services.
- [x] Test design remains pytest-first with shared fixtures and minimal integrations.
- [x] Legacy compatibility is handled by backend aliasing, not duplicated frontend flows.
- [x] No design step requires widening DRF whitelist semantics to page users.
