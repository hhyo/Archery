# Quickstart: Table Instance Locator API

## 1. Endpoint

- Method: `POST`
- Path: `v1/instance/table-instances/`
- Module: `sql_api.api_instance.TableInstanceLookup`

## 2. Request examples

Exact match:

```json
{
  "table_name": "orders"
}
```

Pattern match:

```json
{
  "table_pattern": "order%"
}
```

Invalid (both fields):

```json
{
  "table_name": "orders",
  "table_pattern": "order%"
}
```

## 3. Response example

```json
{
  "status": 0,
  "msg": "query success",
  "count": 2,
  "data": [
    {
      "instance_id": 12,
      "instance_name": "prod-mysql-a",
      "db_type": "mysql",
      "db_name": "sales",
      "table_name": "orders",
      "match_type": "exact"
    }
  ],
  "summary": {
    "processed_instance_count": 10,
    "success_instance_count": 9,
    "failed_instance_count": 1,
    "failure_reasons": [
      {
        "instance_id": 21,
        "instance_name": "legacy-pg",
        "reason": "metadata timeout"
      }
    ]
  }
}
```

## 5. 前端表定位入口（sqlquery.html）

**位置**: SQL 查询页面右侧面板 → 实例选择器上方

**交互流程**:

1. 用户在 `#table-locator-input` 输入框输入 ≥1 个字符。
2. 500ms 内无新输入，自动向 `POST /v1/instance/table-instances/` 发起请求（携带 CSRF token）。
3. 请求体: `{"table_name": "<用户输入>"}` (Content-Type: application/json)
4. 响应成功（`status=0`）: 在输入框下方 `#table-locator-results` 列表中以 `实例名/数据库名/表名` 格式显示每条结果。
5. 响应空结果（`status=0, count=0`）: 显示"无匹配结果"提示文本。
6. 请求失败（`status!=0` 或网络错误）: 显示可读错误信息。
7. 输入框清空: 立即中止待发/进行中请求，清空结果列表。

**HTML 结构（新增部分）**:

```html
<div class="form-group" id="div-table-locator">
    <input id="table-locator-input" type="text" class="form-control"
           placeholder="按表名定位实例（如 orders）" autocomplete="off"/>
    <div id="table-locator-loading" style="display:none">
        <small class="text-muted">查询中...</small>
    </div>
    <ul id="table-locator-results" class="list-unstyled" style="max-height:160px;overflow-y:auto;"></ul>
</div>
```

**安全注意事项**:
- 结果项通过 `$('<li>').text(text)` 设置（文本节点），不使用 innerHTML，防止 XSS。
- CSRF token 通过 jQuery AJAX setup 全局注入（与页面其他 POST 请求一致）。

Configure custom implementation:

```python
TABLE_INSTANCE_LOCATOR = "my_module.my_locator:locate"
```

Provider requirements:
- Accept fixed request structure and authorized `instances` list.
- Return data normalizable to fixed response schema.
- Never leak unauthorized instance/database/table info.

## 5. Test plan (unit-first)

Run focused tests:

```bash
pytest -q sql_api/test_table_instance_locator.py
```

Recommended unit cases:
- serializer validation: exact/pattern mutual exclusivity and empty input rejection
- default locator: permission-filtered instances only
- pattern matching behavior (`%`, `_`, case-insensitive)
- stable sorting under non-deterministic traversal input
- partial failure summary generation with successful item retention
- custom provider normalization and contract enforcement

Fixture guidance:
- Reuse shared fixtures from `conftest.py`.
- Add fake-engine fixtures in module-level fixture blocks to avoid duplicated setup.

Integration tests (only if needed):
- DRF endpoint wiring + auth boundary + serializer integration.
- Include rationale in test docstring when unit test cannot prove behavior.
