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

## Decision 7: 前端触发机制
- Decision: 输入框使用 500ms 防抖（debounce），输入 ≥1 个字符后自动触发；清空时取消待发请求并清空结果列表。
- Rationale: 避免每次击键都发起 API 请求（后端需遍历多实例，成本高）；1 字符起步适用于中文表名（如"订单"第一个字即可缩窄范围）。
- Alternatives considered:
  - 按钮手动触发：被拒，增加操作步骤，不符合用户反馈（问题 Q3 答案 B）。
  - 3 字符触发阈值：被拒，对中文表名门槛过高（用户确认 Q5 答案：1 个字符）。

## Decision 8: 前端结果展示格式
- Decision: 以 `实例名/数据库名/表名` 拼接字符串，每条结果渲染为 `<li>` 列表项，整体包裹在输入框下方的无序列表中。
- Rationale: 单列拼接文本用户确认（Q4 答案 B），信息密度适中，无需多列表格，实现简单，符合现有 Bootstrap 3 风格。
- Alternatives considered:
  - 多列 Bootstrap Table：被拒，引入额外依赖复杂度，用户选择单列即可满足需求。
  - 下拉 selectpicker：被拒，selectpicker 适合预加载有限选项，不适合动态搜索结果列表。

## Decision 9: 前端 API 调用方式
- Decision: 使用 jQuery `$.ajax` POST 调用 `/v1/instance/table-instances/`，携带 Django CSRF token，请求体为 JSON（`table_name` 字段）。
- Rationale: 与现有 sqlquery.html 的所有 AJAX 调用风格一致（同文件已有多处 `$.ajax` 调用），无需引入新依赖。
- Alternatives considered:
  - fetch API：被拒，与现有代码风格不一致，需额外处理 CSRF。
  - 纯 pattern 模式（`table_pattern`）：首版使用精确匹配（`table_name`）降低复杂度；pattern 支持可在后续任务中扩展。

## Decision 10: 输出 XSS 安全
- Decision: 结果文本通过字符串拼接前对 `instance_name`、`db_name`、`table_name` 进行 HTML 转义（使用 `$('<li>').text(text)` 方式设置文本节点而非 innerHTML）。
- Rationale: 实例名/数据库名/表名来自后端，理论上可信，但遵循 OWASP A03 输出编码原则，避免潜在的存储型 XSS。
- Alternatives considered:
  - 直接 innerHTML 拼接：被拒，存在 XSS 风险。

## Decision 6: Test strategy and scope
- Decision: Prioritize pytest unit tests for serializer validation, provider normalization, sorting, permission filtering, and partial-failure behavior; integration tests only for DRF wiring when unit tests cannot prove behavior.
- Rationale: Matches constitution principles II/III/IV and user test preferences.
- Alternatives considered:
  - Broad integration-first tests: rejected due to slower and brittle multi-engine setup.
