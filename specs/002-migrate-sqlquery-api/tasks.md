# Tasks: SQLQuery Interface Unification

**Input**: Design documents from `/specs/002-migrate-sqlquery-api/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/sqlquery-api.openapi.yaml

**Tests**: 采用 pytest 单元优先；仅在认证/权限/路由边界无法通过单元测试充分证明时增加最小集成测试。  
**Organization**: 任务按用户故事分组，保证每个故事可独立实现与验证。

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 建立本次重构所需的后端基础骨架与测试入口。

- [X] T001 创建 SQLQuery 服务层目录与模块骨架在 `sql/services/__init__.py`、`sql/services/sqlquery_service.py`、`sql/services/querylog_service.py`、`sql/services/resource_service.py`
- [X] T002 创建 SQLQuery API 测试文件骨架在 `sql_api/test_sqlquery_api.py` 并补充共享夹具入口到 `conftest.py`
- [X] T003 [P] 创建 SQLQuery API 响应封装与错误映射工具在 `sql_api/sqlquery_response.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 完成所有用户故事共享的阻塞性基础能力。

**⚠️ CRITICAL**: 本阶段完成前不得开始任何用户故事实现。

- [X] T004 在 `sql_api/permissions.py` 新增页面场景权限类并显式绕开默认 `IsInUserWhitelist` 继承路径
- [X] T005 [P] 在 `sql_api/serializers.py` 新增 6 个接口的请求/响应 serializer（instances/resources/execute/logs/favorites）
- [X] T006 [P] 在 `sql_api/api_sqlquery.py` 创建 SQLQuery 视图骨架（5 个 canonical endpoint）
- [X] T007 在 `sql_api/urls.py` 注册 canonical 路由 `/api/v1/sqlquery/*`
- [X] T008 在 `sql/urls.py` 增加 legacy alias 到 SQLQuery DRF 视图的路由绑定（`/group/user_all_instances/`、`/instance/instance_resource/`、`/query/`、`/query/querylog/`、`/query/favorite/`）
- [X] T009 在 `sql/services/sqlquery_service.py` 抽取查询执行公共编排逻辑（权限校验、SQL 过滤、超时终止、脱敏、审计日志）
- [X] T010 [P] 在 `sql/services/querylog_service.py` 抽取历史查询与收藏写入公共逻辑
- [X] T011 [P] 在 `sql/services/resource_service.py` 抽取实例列表、database 列表、table 列表公共逻辑

**Checkpoint**: 基础能力完成，用户故事可以并行推进。

---

## Phase 3: User Story 1 - 安全执行查询 (Priority: P1) 🎯 MVP

**Goal**: 将 SQL 执行接口迁移为 DRF，同时保持现有查询安全与结果行为不变。  
**Independent Test**: 仅实现本故事时，用户可通过现有页面发起查询并得到与当前一致的成功/失败行为。

### Tests for User Story 1

- [ ] T012 [P] [US1] 在 `sql_api/test_sqlquery_api.py` 新增查询执行 serializer 与参数校验单元测试（必填字段、limit、空 SQL）
- [ ] T013 [P] [US1] 在 `sql_api/test_sqlquery_api.py` 新增查询执行服务单元测试（无权限实例、bad query、脱敏异常、成功落库）
- [X] T014 [US1] 在 `sql_api/test_sqlquery_api.py` 新增执行接口集成测试（Session 认证 + 页面权限 + legacy `/query/` alias）并在用例注释中说明边界理由

### Implementation for User Story 1

- [X] T015 [US1] 在 `sql_api/api_sqlquery.py` 实现 `POST /api/v1/sqlquery/execute/` 视图并接入 `sql/services/sqlquery_service.py`
- [X] T016 [US1] 在 `sql/services/sqlquery_service.py` 对齐现有 `sql/query.py` 的查询行为与返回 envelope（`status/msg/data`）
- [X] T017 [US1] 在 `sql/query.py` 将 legacy 查询入口改为复用服务层（删除重复逻辑但保留兼容调用）
- [ ] T018 [US1] 在 `sql/tests.py` 补充或调整针对 `/query/` 的回归断言以锁定兼容行为

**Checkpoint**: US1 可独立交付，页面主查询流程可用。

---

## Phase 4: User Story 2 - 管理历史与收藏 (Priority: P2)

**Goal**: 迁移历史查询与收藏接口，保持分页筛选与收藏交互稳定。  
**Independent Test**: 仅实现本故事时，用户可查询历史、筛选、收藏/取消收藏且权限边界正确。

### Tests for User Story 2

- [ ] T019 [P] [US2] 在 `sql_api/test_sqlquery_api.py` 新增历史列表单元测试（`limit/offset/search/star/query_log_id` 过滤）
- [ ] T020 [P] [US2] 在 `sql_api/test_sqlquery_api.py` 新增历史可见性与收藏写权限单元测试（普通用户/审计员/超级用户）
- [X] T021 [US2] 在 `sql_api/test_sqlquery_api.py` 新增 `/query/querylog/` 与 `/query/favorite/` alias 集成测试并附集成必要性说明

### Implementation for User Story 2

- [X] T022 [US2] 在 `sql_api/api_sqlquery.py` 实现 `GET /api/v1/sqlquery/logs/`（返回 `total/rows` 兼容结构）
- [X] T023 [US2] 在 `sql_api/api_sqlquery.py` 实现 `POST /api/v1/sqlquery/favorites/`（返回 `status/msg` 兼容结构）
- [X] T024 [US2] 在 `sql/services/querylog_service.py` 实现历史过滤与收藏更新逻辑并复用现有 `QueryLog` 模型字段
- [X] T025 [US2] 在 `sql/query.py` 将 `querylog` 与 `favorite` legacy 函数改为复用服务层或 DRF 视图共享逻辑
- [ ] T026 [US2] 在 `sql/tests.py` 增补历史与收藏的兼容回归用例（重点覆盖 `total/rows` 与 `status/msg`）

**Checkpoint**: US2 可独立交付，历史与收藏能力稳定。

---

## Phase 5: User Story 3 - 加载实例与表元数据 (Priority: P3)

**Goal**: 迁移实例列表、database 列表、table 列表接口，保持现有联动体验。  
**Independent Test**: 仅实现本故事时，页面实例/数据库/表选择器可正常级联加载且权限范围正确。

### Tests for User Story 3

- [ ] T027 [P] [US3] 在 `sql_api/test_sqlquery_api.py` 新增实例列表接口单元测试（资源组过滤、排序、tag 过滤）
- [ ] T028 [P] [US3] 在 `sql_api/test_sqlquery_api.py` 新增 database/table 资源接口单元测试（`resource_type`、`db_name`、可选 `schema_name`）
- [X] T029 [US3] 在 `sql_api/test_sqlquery_api.py` 新增 `/group/user_all_instances/` 与 `/instance/instance_resource/` alias 集成测试并附理由

### Implementation for User Story 3

- [X] T030 [US3] 在 `sql_api/api_sqlquery.py` 实现 `GET /api/v1/sqlquery/instances/` 与 `GET /api/v1/sqlquery/resources/`
- [X] T031 [US3] 在 `sql/services/resource_service.py` 实现实例、database、table 读取服务并复用 `user_instances` 与 `get_engine`
- [X] T032 [US3] 在 `sql/resource_group.py` 与 `sql/instance.py` 将 legacy 入口改为复用服务层或共享 DRF 视图逻辑
- [ ] T033 [US3] 在 `sql/tests.py` 新增资源联动兼容回归（实例→database→table 流程）

**Checkpoint**: US3 可独立交付，6 个目标接口全部可用。

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 收口文档、回归与清理，确保可发布。

- [ ] T034 [P] 更新实现后契约与文档在 `specs/002-migrate-sqlquery-api/contracts/sqlquery-api.openapi.yaml`、`specs/002-migrate-sqlquery-api/quickstart.md`
- [X] T035 [P] 补充实现说明与兼容策略注释在 `sql_api/api_sqlquery.py`、`sql/services/*.py`
- [X] T036 运行并修复目标回归测试 `pytest -q sql_api/test_sqlquery_api.py` 与 `pytest -q sql/tests.py -k "sqlquery or query_log or star"`

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 (Setup): 无依赖，可立即开始。
- Phase 2 (Foundational): 依赖 Phase 1，且阻塞所有用户故事。
- Phase 3/4/5 (User Stories): 均依赖 Phase 2 完成；之后可并行或按优先级执行。
- Phase 6 (Polish): 依赖目标用户故事完成。

### User Story Dependencies

- US1 (P1): 仅依赖 Foundational，优先形成 MVP。
- US2 (P2): 依赖 Foundational；与 US1 逻辑独立，但建议在 US1 稳定后合入。
- US3 (P3): 依赖 Foundational；与 US1/US2 可并行开发。

### Within Each User Story

- 先写并验证测试失败，再实现功能。
- 先实现 service，再接入 API view，再绑定 legacy alias。
- 每个故事完成后即可独立验收。

### Parallel Opportunities

- Setup 阶段 `T003` 可并行。
- Foundational 阶段 `T005`、`T006`、`T010`、`T011` 可并行。
- US1 阶段 `T012` 与 `T013` 可并行。
- US2 阶段 `T019` 与 `T020` 可并行。
- US3 阶段 `T027` 与 `T028` 可并行。
- Polish 阶段 `T034` 与 `T035` 可并行。

## Parallel Example: User Story 1

```bash
# 并行编写 US1 单元测试
T012: sql_api/test_sqlquery_api.py
T013: sql_api/test_sqlquery_api.py

# 测试完成后串行推进实现
T015 -> T016 -> T017 -> T018
```

## Parallel Example: User Story 2

```bash
# 并行编写 US2 单元测试
T019: sql_api/test_sqlquery_api.py
T020: sql_api/test_sqlquery_api.py

# 实现阶段
T022/T023 与 T024 可交错推进，最后执行 T025/T026
```

## Parallel Example: User Story 3

```bash
# 并行编写 US3 单元测试
T027: sql_api/test_sqlquery_api.py
T028: sql_api/test_sqlquery_api.py

# 实现阶段
T030 与 T031 并行，完成后执行 T032/T033
```

## Implementation Strategy

### MVP First (US1)

1. 完成 Phase 1 + Phase 2。
2. 交付 Phase 3 (US1)。
3. 执行 US1 独立验收并确认页面主查询流程稳定。

### Incremental Delivery

1. US1 上线后，再合入 US2（历史与收藏）。
2. US2 稳定后，再合入 US3（实例/database/table 联动）。
3. 最后执行 Phase 6 做统一收口。

### Team Parallel Strategy

1. 全员先完成 Foundational。
2. 开发者 A: US1；开发者 B: US2；开发者 C: US3。
3. 各故事完成后独立验收，再统一回归。

## Notes

- [P] 任务表示可并行（不同文件、无未完成依赖）。
- 每条任务都映射了明确文件路径，便于直接由 LLM 执行。
- 优先保证后端改造集中完成；仅在 alias 成本过高时触发前端最小改动。