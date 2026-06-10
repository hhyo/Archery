# Research: SQLQuery Interface Unification

## Decision 1: Migration seam and URL strategy
- Decision: 为 SQLQuery 场景新增规范化 DRF endpoint，同时保留现有页面调用的 legacy URL 兼容层；核心业务逻辑抽取到共享 service，由 DRF 视图和 legacy wrapper 共同调用。
- Rationale: 用户明确希望“尽量不改前端代码、尽量将更改集中在后端”；仅新增 DRF URL 而强制前端全部切换，会把大量改动压到模板里；仅保留旧函数视图又达不到授权与接口统一的目标。
- Alternatives considered:
  - 只新增 `/api/v1/...` 并修改前端全部 AJAX URL：被拒，前端改动面过大。
  - 直接把旧 Django 函数视图改成 DRF 逻辑但不建立规范化 namespace：被拒，长期 API 可发现性和文档性差。

## Decision 2: Permission model for page-facing DRF views
- Decision: 页面场景的 DRF 视图显式使用 `SessionAuthentication`/`IsAuthenticated` 与 endpoint-specific Django permission/resource checks；不沿用 `REST_FRAMEWORK` 默认的 `IsInUserWhitelist`。
- Rationale: 当前 `sql_api` 默认权限适用于开放 API，而不是模板页面里的普通登录用户；如果直接继承默认设置，SQL 查询页面的大多数 AJAX 请求会被拒绝。
- Alternatives considered:
  - 将所有页面用户加入 `api_user_whitelist`：被拒，这会把页面授权语义错误地耦合到开放 API 白名单。
  - 彻底绕过 DRF permission，仅在 service 层做权限：被拒，认证与权限边界不清晰，也无法充分利用 DRF 授权配置。

## Decision 3: Response compatibility is per-endpoint, not global
- Decision: 采用 per-view envelope 兼容策略，分别保留现有前端依赖的返回结构：执行查询与收藏接口保留 `status/msg/data`，历史记录保留 `total/rows`，实例/资源列表保留 `status/msg/data`。
- Rationale: SQL 查询页面中不同 AJAX 回调依赖不同结构；统一套一个全局 renderer 反而会制造额外适配成本。
- Alternatives considered:
  - 统一为 DRF 默认 `{detail: ...}` 或 pagination `count/results`：被拒，前端需要大范围改写。
  - 强制全接口统一为 `status/msg/data`：被拒，bootstrap-table 现有历史列表直接依赖 `total/rows`。

## Decision 4: Resource lookup contract keeps optional schema compatibility
- Decision: 资源读取 contract 以 `instance_name + resource_type` 为主，`resource_type` 仍支持 `database` 与 `table`；同时继续接受可选 `schema_name` 以兼容 PgSQL 的现有流程，但不把“schema 读取”列为本次迁移范围内的独立用户能力。
- Rationale: 用户本次明确的接口范围只有实例、database、table；但现有前端对 PgSQL 的表读取流程依赖 schema 参数，直接移除会导致行为回退。
- Alternatives considered:
  - 彻底删除 `schema_name`：被拒，会破坏现有 PgSQL 交互。
  - 把 schema 当作第 7 个正式迁移接口：被拒，超出本次明确范围。

## Decision 5: Query execution service extraction
- Decision: 从 `sql.query.query` 中抽取查询执行 orchestration 服务，保留原有引擎调用、权限校验、SQL 过滤、超时终止、脱敏与 QueryLog 落库语义。
- Rationale: `/query/` 是本次最复杂接口；如果只把整个函数粘进 DRF 视图，后续很难测试、复用和回归。
- Alternatives considered:
  - DRF 视图直接复制 legacy 逻辑：被拒，逻辑重复且回归风险高。
  - 只包一层 `call_legacy_view()`：被拒，没有实现真正的后端收敛。

## Decision 6: Permission semantics should be pinned by tests before normalization
- Decision: 对 6 个接口的授权语义编写回归测试，优先锁定“当前有效行为”，再在实现中通过 DRF permission class 和 service 校验显式表达；不在重构过程中静默改变角色语义。
- Rationale: 现有页面视图与部分 legacy 接口的 Django permission codename 并不完全一致，直接“顺手统一”容易引入权限回归。
- Alternatives considered:
  - 立即统一全部接口到单一 codename：被拒，缺乏现状基线，容易误伤现有角色。
  - 继续依赖 middleware 和页面入口隐式控制：被拒，不符合“充分利用授权配置”的目标。

## Decision 7: Test strategy and scope
- Decision: 优先使用 pytest 单元测试验证 serializer、permission、service 与 envelope 兼容；仅对 DRF auth wiring、legacy alias 路由绑定、SessionAuthentication 与权限边界增加最少量集成测试，并在测试注释中说明 unit test 不足之处。
- Rationale: 符合宪章的 unit-first、shared fixtures、bounded integration 原则。
- Alternatives considered:
  - 端到端前端联动测试优先：被拒，过重且与本次“后端集中改造”不匹配。
  - 仅保留旧 `sql/tests.py` smoke：被拒，无法证明 DRF 权限与契约稳定性。