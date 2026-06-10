# Data Model: SQLQuery Interface Unification

## 1) AccessibleInstanceItem

Represents one instance visible to the current user on the SQL query page.

Fields:
- `id` (int, required): instance primary key.
- `type` (string, required): instance type/category used by existing UI filtering.
- `db_type` (string, required): engine type shown in grouped select options.
- `instance_name` (string, required): display name and primary lookup key for page requests.

Validation/normalization rules:
- Returned items must already be filtered by `user_instances(user, ...)`.
- Ordering remains locale-aware by instance name to preserve current UX.
- Contract keeps current field names to avoid front-end remapping.

## 2) InstanceResourceRequest

Represents a resource lookup request for database or table lists.

Fields:
- `instance_name` (string, required for legacy compatibility) or `instance_id` (int, optional for canonical API): target instance.
- `resource_type` (enum, required): `database` or `table`.
- `db_name` (string, optional): required when `resource_type=table`.
- `schema_name` (string, optional): compatibility field for PgSQL table lookup.

Validation rules:
- `resource_type=database` requires a resolvable instance.
- `resource_type=table` requires both a resolvable instance and non-empty `db_name`.
- `schema_name` is optional and ignored for engines that do not need it.
- Response format remains `{status, msg, data}` with `data` as a flat array.

## 3) SqlQueryExecutionRequest

Represents the payload for executing a SQL statement.

Fields:
- `instance_name` (string, required)
- `db_name` (string, required)
- `schema_name` (string, optional)
- `tb_name` (string, optional)
- `sql_content` (string, required)
- `limit_num` (integer, required)

Derived/runtime fields:
- `request_user`
- `priv_check_result`
- `effective_limit_num`
- `schedule_name` / `thread_id` for timeout termination

Validation and processing rules:
- Instance must belong to the caller's authorized scope.
- SQL must pass existing `query_check`, privilege check, limit rewriting, and masking flow.
- Explain-mode transformations remain a frontend concern unless compatibility wrappers move them server-side later.

## 4) SqlQueryExecutionResult

Represents the envelope returned to the current page after a query.

Fields:
- `status` (int): `0` success, non-zero failure.
- `msg` (string)
- `data` (object)

Nested `data` payload fields used by current UI:
- `column_list` (array)
- `rows` (array)
- `query_time` (number)
- `mask_time` (number)
- `full_sql` (string)
- `seconds_behind_master` (number, optional)
- `error` (string, optional)
- other engine-specific fields currently present in `query_result.__dict__`

Compatibility rules:
- Big integers, decimals, and datetimes must remain JSON-safe for current JS consumers.
- Successful execution continues to create/update `QueryLog` side effects.

## 5) QueryLogListRequest

Represents a history list/filter request coming from bootstrap-table.

Fields:
- `limit` (int, optional)
- `offset` (int, optional)
- `search` (string, optional)
- `star` (string/bool, optional)
- `query_log_id` (int, optional)

Validation rules:
- `limit` and `offset` default to current bootstrap-table behavior.
- `star=true` narrows to favorites; missing/false keeps all visible records.
- Visibility remains role-aware: normal users only see own logs; audit/superuser can see broader scope.

## 6) QueryLogItem

Represents one row in query history.

Fields:
- `id` (int)
- `instance_name` (string)
- `db_name` (string)
- `sqllog` (string)
- `effect_row` (int)
- `cost_time` (number)
- `user_display` (string)
- `favorite` (bool)
- `alias` (string)
- `create_time` (datetime string)

Compatibility rules:
- History endpoint response remains `{total, rows}`.
- Field names remain unchanged so bootstrap-table column config can be reused.

## 7) FavoriteMutationRequest

Represents a favorite/unfavorite action.

Fields:
- `query_log_id` (int, required)
- `star` (bool/string, required)
- `alias` (string, optional)

Validation rules:
- Caller must be allowed to mutate the target query log record.
- `alias` may be empty when `star=false`.
- Response remains `{status, msg}` for current modal flow.