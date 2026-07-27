# RabbitMQ rabbitmqadmin A-tier AMQP Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align Archery’s RabbitMQ CLI subset with official `rabbitmqadmin` (3.13) parameter names and AMQP-mappable behavior for A-tier commands, with high unit-test coverage; update help docs/contracts accordingly.

**Architecture:** Extend `parse_rabbitmq_line` and `RabbitmqEngine` in place. Parsing enforces official keys; unsupported official optionals fail loudly. Execution uses pika only (no Management HTTP). Help templates and `test_mq_help_templates.py` stay in sync with the new surface.

**Tech Stack:** Python, pytest, unittest.mock, pika (mocked in unit tests), Django templates

**Spec:** `docs/superpowers/specs/2026-07-22-rabbitmq-admin-amqp-align-design.md`

## Global Constraints

- Authority: RabbitMQ 3.13 `rabbitmqadmin help subcommands` — **no invented parameter names**
- `get` uses **`ackmode=`** (not `requeue=`); default **`ack_requeue_true`**; `count` default **`1`**
- Allowed ackmode values only: `ack_requeue_true` | `ack_requeue_false` | `reject_requeue_true` | `reject_requeue_false`
- Binding: only `source` + `destination`; optional `destination_type` (default `queue`, only `queue` allowed); optional `routing_key` (default `""`); reject legacy `queue=`/`exchange=` on binding
- Unsupported optionals (`arguments`, `properties`, `payload_file`, `encoding`, `internal`, `node`, `queue_type`, …): **parse fail**, never silent ignore
- `list` / `close`: parse fail (no fake list-queues success path)
- `publish`: `payload` required in Archery; `exchange` optional → `""`; `amq.default` → `""`
- Explicit `durable`/`auto_delete` only when present; omit kwargs otherwise
- High coverage: every adopted command needs success + missing-required + illegal/unsupported; execution tests assert pika method + kwargs
- No MQTT changes; no Management HTTP client

## File map

| File | Responsibility |
|------|----------------|
| `sql/engines/mq_cli.py` | Official parse/validate surface |
| `sql/engines/rabbitmq.py` | AMQP execute + HELP_ROWS + query/write checks |
| `sql/engines/test_mq_cli.py` | Parse matrix |
| `sql/engines/test_rabbitmq.py` | Engine/check/run_get/write mocks |
| `sql/templates/sqlquery.html` / `sqlsubmit.html` | Help examples |
| `sql/tests/test_mq_help_templates.py` | Snippet contract |

---

### Task 1: Parse — get ackmode + reject list/requeue/unsupported

**Files:**
- Modify: `sql/engines/mq_cli.py` (`parse_rabbitmq_line` get/list branches)
- Test: `sql/engines/test_mq_cli.py`

**Interfaces:**
- Consumes: existing `parse_rabbitmq_line`
- Produces: `cmd.args` for get includes `ackmode` (str, default `ack_requeue_true`); `list`/`close` raise `ValueError` with message containing `Management` or `不支持`

- [ ] **Step 1: Write failing tests** in `sql/engines/test_mq_cli.py`:

```python
def test_rabbitmq_get_defaults_ackmode_and_count():
    g = parse_rabbitmq_line("get queue=q1")
    assert g.args["queue"] == "q1"
    assert g.args["count"] == 1
    assert g.args["ackmode"] == "ack_requeue_true"


@pytest.mark.parametrize(
    "ackmode",
    [
        "ack_requeue_true",
        "ack_requeue_false",
        "reject_requeue_true",
        "reject_requeue_false",
    ],
)
def test_rabbitmq_get_ackmodes(ackmode):
    g = parse_rabbitmq_line(f"get queue=q1 count=2 ackmode={ackmode}")
    assert g.args["ackmode"] == ackmode
    assert g.args["count"] == 2


def test_rabbitmq_get_rejects_requeue_flag():
    with pytest.raises(ValueError, match="ackmode"):
        parse_rabbitmq_line("get queue=q1 requeue=false")


def test_rabbitmq_get_rejects_payload_file_and_encoding():
    with pytest.raises(ValueError):
        parse_rabbitmq_line("get queue=q1 payload_file=x")
    with pytest.raises(ValueError):
        parse_rabbitmq_line("get queue=q1 encoding=auto")


def test_rabbitmq_list_and_close_unsupported():
    with pytest.raises(ValueError):
        parse_rabbitmq_line("list queues")
    with pytest.raises(ValueError):
        parse_rabbitmq_line("list exchanges")
    with pytest.raises(ValueError):
        parse_rabbitmq_line("close connection name=x")
```

Update existing `test_rabbitmq_get_and_publish` / leading-conn-flag tests to expect `ackmode` in args.

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest sql/engines/test_mq_cli.py -k "rabbitmq_get or rabbitmq_list" -v`

- [ ] **Step 3: Implement parse changes**

In `parse_rabbitmq_line`:
- Remove successful `list queues` path; treat `list` and `close` as unsupported actions (or action in set that always raises).
- For `get`: after kv parse, reject keys `requeue`, `payload_file`, `encoding`; validate/default `ackmode`; keep `count` int default 1.
- Allow only known keys for get: `queue`, `count`, `ackmode`.

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest sql/engines/test_mq_cli.py -v`

- [ ] **Step 5: Commit**

```bash
git add sql/engines/mq_cli.py sql/engines/test_mq_cli.py
git commit -m "feat(mq): align rabbitmq get ackmode and reject list/close"
```

---

### Task 2: Parse — declare/delete/publish official keys

**Files:**
- Modify: `sql/engines/mq_cli.py`
- Test: `sql/engines/test_mq_cli.py`

**Interfaces:**
- Produces: binding args use `source`, `destination`, `destination_type` (default `queue`), `routing_key` (default `""`); delete supports `exchange`/`queue`/`binding`; `auto_delete` bool like `durable`; publish normalizes `amq.default` → `""`

- [ ] **Step 1: Write failing tests**

```python
def test_declare_binding_official_keys():
    cmd = parse_rabbitmq_line(
        "declare binding source=ex destination=q routing_key=rk"
    )
    assert cmd.args["source"] == "ex"
    assert cmd.args["destination"] == "q"
    assert cmd.args["destination_type"] == "queue"
    assert cmd.args["routing_key"] == "rk"


def test_declare_binding_rejects_legacy_queue_exchange_keys():
    with pytest.raises(ValueError, match="source"):
        parse_rabbitmq_line(
            "declare binding queue=q exchange=ex routing_key=rk"
        )


def test_declare_binding_rejects_exchange_destination_type():
    with pytest.raises(ValueError):
        parse_rabbitmq_line(
            "declare binding source=a destination=b destination_type=exchange"
        )


def test_declare_queue_auto_delete():
    cmd = parse_rabbitmq_line("declare queue name=q1 auto_delete=true")
    assert cmd.args["auto_delete"] is True


def test_declare_rejects_arguments():
    with pytest.raises(ValueError):
        parse_rabbitmq_line('declare queue name=q1 arguments={}')


def test_delete_exchange_and_binding():
    d = parse_rabbitmq_line("delete exchange name=ex1")
    assert d.args["target"] == "exchange"
    assert d.args["name"] == "ex1"
    b = parse_rabbitmq_line(
        "delete binding source=ex destination_type=queue destination=q properties_key=rk"
    )
    assert b.args["source"] == "ex"
    assert b.args["destination"] == "q"
    assert b.args["destination_type"] == "queue"
    assert b.args["properties_key"] == "rk"


def test_publish_amq_default_normalizes():
    p = parse_rabbitmq_line(
        'publish routing_key=q payload=hi exchange=amq.default'
    )
    assert p.args["exchange"] == ""


def test_publish_rejects_properties():
    with pytest.raises(ValueError):
        parse_rabbitmq_line(
            'publish routing_key=q payload=hi properties={}'
        )
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest sql/engines/test_mq_cli.py -k "declare_binding or delete_exchange or publish_amq or auto_delete or rejects_arguments or rejects_properties" -v`

- [ ] **Step 3: Implement**

Refactor `parse_rabbitmq_line`:
- `delete`: allow target `queue` | `exchange` | `binding` (binding uses kv, not `name=` only).
- `declare binding`: require source/destination; default destination_type=queue; reject legacy keys and arguments / non-queue destination_type.
- Parse `auto_delete` like `durable`.
- Per-action allowlists of kv keys; anything else → ValueError.
- publish: require payload; normalize exchange.

- [ ] **Step 4: PASS full** `pytest sql/engines/test_mq_cli.py -v`

- [ ] **Step 5: Commit**

```bash
git add sql/engines/mq_cli.py sql/engines/test_mq_cli.py
git commit -m "feat(mq): align rabbitmq declare/delete/publish with rabbitmqadmin keys"
```

---

### Task 3: Engine — run_get ackmode + write commands

**Files:**
- Modify: `sql/engines/rabbitmq.py`
- Test: `sql/engines/test_rabbitmq.py`

**Interfaces:**
- `run_get(..., ackmode=...)` or read from caller; after `basic_get`, apply table from spec §5.1
- `_execute_write_command`: bind via source/destination; unbind; exchange_delete; durable/auto_delete kwargs
- `query_check`: only `get`/`help` (list no longer allowed)
- `execute_check`/`_validate_write_command`: new delete targets + binding keys
- Update `RABBITMQ_HELP_ROWS`; remove list-queues fake query path / `LIST_QUEUES_ERROR` usage for successful parse

- [ ] **Step 1: Write failing engine tests** (adapt existing tests that use legacy binding / list queues)

```python
def test_query_check_rejects_list():
    engine = RabbitmqEngine(instance=self.ins)
    r = engine.query_check(sql="list queues")
    assert r["bad_query"] is True


def test_run_get_ackmode_ack_requeue_false_acks(self, mock_conn):
    # mock basic_get returns a message once then None
    # assert basic_ack called; basic_nack/reject not called


def test_run_get_ackmode_ack_requeue_true_requeues(self, mock_conn):
    # assert nack or reject with requeue=True


# similarly reject_requeue_* 

def test_execute_declare_binding_official(self, mock_conn):
    # workflow with declare binding source=... destination=...
    # assert queue_bind(queue=destination, exchange=source, routing_key=...)


def test_execute_delete_exchange(self, mock_conn):
    # assert exchange_delete


def test_execute_delete_binding(self, mock_conn):
    # assert queue_unbind(...)
```

Update any remaining tests that still use `declare binding queue=... exchange=...` or expect list queues query success.

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest sql/engines/test_rabbitmq.py -v`

- [ ] **Step 3: Implement engine**

- `run_get`: parameter `ackmode` default `ack_requeue_true`; map to ack/nack/reject.
- Wire `query()` / mq job path to pass `cmd.args["ackmode"]` (check `sql/services/mq_query_job.py` — update if it calls `run_get`).
- Write path for new declare/delete shapes.
- HELP_ROWS official examples only (no list queues as supported query).

- [ ] **Step 4: PASS**

Run: `pytest sql/engines/test_rabbitmq.py sql/engines/test_mq_cli.py sql/services/test_mq_query_job.py -v`

- [ ] **Step 5: Commit**

```bash
git add sql/engines/rabbitmq.py sql/engines/test_rabbitmq.py sql/services/mq_query_job.py sql/services/test_mq_query_job.py
git commit -m "feat(mq): execute rabbitmqadmin-aligned get ackmode and write commands"
```

---

### Task 4: Help templates + contract test sync

**Files:**
- Modify: `sql/templates/sqlquery.html`, `sql/templates/sqlsubmit.html`, `sql/tests/test_mq_help_templates.py`
- Optionally: `docs/superpowers/specs/2026-07-22-mq-ui-help-docs-design.md` note only if needed (prefer code/help only)

**Interfaces:**
- Help examples use `source=`/`destination=`, `ackmode=`, no legacy binding, no “list queues as working query”
- `REQUIRED_SNIPPETS` updated so contract stays green

- [ ] **Step 1: Update `REQUIRED_SNIPPETS`** — replace legacy binding / list-as-ok strings; add e.g.:

```python
"declare binding source=demo.ex destination=demo.q routing_key=demo.q",
"get queue=demo.q count=1 ackmode=ack_requeue_false",
"delete exchange name=demo.ex",
```

Remove snippets that teach `declare binding queue=` or workable `list queues`.

- [ ] **Step 2: Run contract — expect FAIL**

Run: `pytest sql/tests/test_mq_help_templates.py -v`

- [ ] **Step 3: Edit both HTML help panels** (query + submit stay identical for RabbitMQ blocks) to match official examples; document four ackmodes briefly; state list/close unsupported.

- [ ] **Step 4: PASS** `pytest sql/tests/test_mq_help_templates.py sql/engines/test_mq_cli.py sql/engines/test_rabbitmq.py -v`

- [ ] **Step 5: Commit**

```bash
git add sql/templates/sqlquery.html sql/templates/sqlsubmit.html sql/tests/test_mq_help_templates.py
git commit -m "docs(mq): sync RabbitMQ help tabs with rabbitmqadmin A-tier syntax"
```

---

### Task 5: Coverage gate + regression sweep

**Files:** none new (verification task)

- [ ] **Step 1: Run focused coverage**

```bash
pytest sql/engines/test_mq_cli.py sql/engines/test_rabbitmq.py \
  --cov=sql.engines.mq_cli --cov=sql.engines.rabbitmq \
  --cov-report=term-missing -q
```

Inspect missing lines on new branches; add tests if any ackmode/declare/delete branch untested.

- [ ] **Step 2: Full MQ-related sweep**

```bash
pytest sql/engines/test_mq_cli.py sql/engines/test_mqtt.py sql/engines/test_rabbitmq.py \
  sql/services/test_mq_query_job.py sql_api/test_mq_query_job_api.py \
  sql/tests/test_mq_help_templates.py -v
```

Expected: all PASS.

- [ ] **Step 3: Commit only if Step 1 added tests**

```bash
git add sql/engines/test_mq_cli.py sql/engines/test_rabbitmq.py
git commit -m "test(mq): raise coverage for rabbitmqadmin alignment branches"
```

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| get ackmode + defaults | 1, 3 |
| reject requeue/list/close/unsupported optionals | 1, 2 |
| declare/delete/publish official keys | 2, 3 |
| binding break legacy | 2, 3, 4 |
| run_get AMQP mapping | 3 |
| help + contract | 4 |
| high coverage | 1–3, 5 |

## Placeholder / consistency review

- No TBD; ackmode (not requeue) consistent throughout.
- Existing tests that assumed list-queues query OK or legacy binding **must** be rewritten in Task 3 (called out).
- `mq_query_job.py` must pass ackmode into `run_get` (Task 3).

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-22-rabbitmq-admin-amqp-align.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task + review  
**2. Inline Execution** — this session with executing-plans  

Which approach?
