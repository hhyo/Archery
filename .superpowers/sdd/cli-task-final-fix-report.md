# CLI Final Fix Report — Important findings from whole-branch review

**Branch:** `feat/mqtt-rabbitmq-engine`  
**Date:** 2026-07-18  
**Review:** `.superpowers/sdd/cli-final-review.md`

## Status

**DONE** — all 5 Important findings + cheap Minors addressed.

## Fixes

| # | Finding | Fix |
|---|---------|-----|
| I1 | MQ job APIs omit `sql.query_submit` | `_deny_without_query_submit` on create/detail/cancel views (mirror execute: superuser or `sql.query_submit`) |
| I2 | Async create skips engine validation | `create_mq_query_job` calls `MqttEngine._validate_query_command` / `RabbitmqEngine._validate_query_command` before enqueue |
| I3 | Cache RMW race cancel vs on_message | Dedicated `mq_query_job:{id}:cancel` key + `_update_job` re-get-merge-set for cancel/on_message/finalize; `_is_cancelled` reads cancel key |
| I4 | Integration smoke still old DSL | `test_mq_integration.py` rewritten to MQTTX/rabbitmqadmin; README pointer unchanged (still valid) |
| I5 | Sync execute accepts blocking sub/get | `execute_sql_query` rejects mqtt `sub` / rabbitmq `get` with hint to `/api/v1/sqlquery/mq-jobs/` |
| M1 | Dead `_skip_conn_flags` | Removed from `mq_cli.py` |
| M4 | README duplicate “5.” | MQTT 工单 → 6.；反向校验 → 7. |

Also: exception path in `run_mq_query_job` now prefers `cancelled` when cancel flagged (Minor #8, cheap).

## Files touched

- `sql_api/api_sqlquery.py`
- `sql/services/mq_query_job.py`
- `sql/services/sqlquery_service.py`
- `sql/engines/mq_cli.py`
- `sql/engines/test_mq_integration.py`
- `scripts/mq_env/README.md`
- `sql/services/test_mq_query_job.py`
- `sql_api/test_mq_query_job_api.py`
- `sql/test_services.py`

## Test results (WSL `.venv-mq`)

```text
# engines
pytest --confcutdir=sql/engines \
  sql/engines/test_mq_cli.py sql/engines/test_mqtt.py sql/engines/test_rabbitmq.py -q
→ 44 passed

# job service
pytest --confcutdir=sql/services sql/services/test_mq_query_job.py -q
→ 9 passed

# job API
pytest --confcutdir=sql_api sql_api/test_mq_query_job_api.py -q
→ 10 passed

# execute path
pytest --confcutdir=sql sql/test_services.py -q -k execute_sql_query
→ 6 passed, 8 deselected
```

**Total focused:** 69 passed.

New/updated coverage: create-time validation; API 403 without `query_submit`; cancel-key survives stale job overwrite; sync execute rejects sub/get.

## Concerns / residual

1. `_update_job` is still get-then-set (no cache lock); cancel **flag** is durable via separate key, but a theoretical race can still drop a just-appended row if cancel’s merge races on_message between get/set. Acceptable for Django cache backends without WATCH.
2. Sync `help` / RabbitMQ `list` still allowed on execute (intentional; only long-wait sub/get blocked).
3. `manage.py` pymysql shim left uncommitted (local env only).
4. Live integration smoke not re-run here (needs brokers + env vars); syntax updated so it should pass when brokers are up.
