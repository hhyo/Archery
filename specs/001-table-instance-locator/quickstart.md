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

## 4. Custom provider

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
