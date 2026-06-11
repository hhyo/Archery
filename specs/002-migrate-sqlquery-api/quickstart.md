# Quickstart: SQLQuery Interface Unification

## 1. Canonical endpoints

- `GET /api/v1/sqlquery/instances/`
- `GET /api/v1/sqlquery/resources/`
- `POST /api/v1/sqlquery/execute/`
- `GET /api/v1/sqlquery/logs/`
- `POST /api/v1/sqlquery/favorites/`

## 2. Legacy compatibility aliases for current page

- `GET /group/user_all_instances/` → instances
- `GET /instance/instance_resource/` → resources
- `POST /query/` → execute
- `GET /query/querylog/` → logs
- `POST /query/favorite/` → favorites

## 3. Request examples

Get authorized instances:

```http
GET /api/v1/sqlquery/instances/?tag_codes=can_read
```

Get databases for one instance:

```http
GET /api/v1/sqlquery/resources/?instance_name=test-mysql&resource_type=database
```

Get tables for one instance/database:

```http
GET /api/v1/sqlquery/resources/?instance_name=test-mysql&db_name=archery&resource_type=table
```

Execute query:

```json
POST /api/v1/sqlquery/execute/
{
  "instance_name": "test-mysql",
  "db_name": "archery",
  "schema_name": "",
  "tb_name": "sql_workflow",
  "sql_content": "select 1;",
  "limit_num": 100
}
```

Get logs:

```http
GET /api/v1/sqlquery/logs/?limit=20&offset=0&search=select
```

Favorite one query log:

```json
POST /api/v1/sqlquery/favorites/
{
  "query_log_id": 123,
  "star": true,
  "alias": "常用检查语句"
}
```

## 4. Manual verification flow

1. 使用具备 SQL 查询页面权限的普通用户登录，打开 `/sqlquery/`，确认实例下拉框仍能加载当前用户有权访问的实例。
2. 选择一个实例后，确认 database 列表能正常加载；再选择一个 database，确认 table 列表能正常加载。
3. 输入一条允许的查询语句并执行，确认结果页仍能展示数据、耗时、脱敏时间和主从延迟信息。
4. 打开查询历史，确认 bootstrap-table 仍能显示分页数据，并支持搜索、按收藏筛选和一键重查。
5. 在历史记录中收藏和取消收藏一条 SQL，确认状态和别名都能正确刷新。
6. 使用无相应权限的用户重复调用上述接口，确认被拒绝且返回可读错误，而不是 DRF 默认 HTML/JSON 异常页。

## 5. Focused test commands

```bash
pytest -q sql_api/test_sqlquery_api.py
pytest -q sql/tests.py -k "sqlquery or query_log or star"
```

Integration-test note:
- 仅对 DRF auth wiring、legacy alias 路由绑定和 session 登录场景增加跨边界测试。
- 其余执行路径优先通过 fake engine / monkeypatch 的 unit-first 方式验证。