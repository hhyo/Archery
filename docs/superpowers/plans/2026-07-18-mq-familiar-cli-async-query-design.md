# MQTTX / rabbitmqadmin CLI + Async Long Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 MQTT/RabbitMQ 引擎命令改为 MQTTX / rabbitmqadmin 子集（连接取自 Instance），并为 `sub`/`get` 提供异步可取消增量查询，且不影响其它数据库引擎。

**Architecture:** 独立解析模块产出结构化 `MqCommand`；引擎 `query_check`/`execute_check`/`query`/`execute_workflow` 消费该结构。长等待查询经 `MqQueryJobService`（Django cache 存状态 + `django_q.async_task` 跑 worker）暴露 create/status/cancel API；SQL 查询页对 MQ 的 `sub`/`get` 走新 API 并轮询增量 rows。

**Tech Stack:** Django、django-q、Django cache、paho-mqtt、pika、pytest、现有 `sqlquery` / `sql_api` 前端

**Spec:** `docs/superpowers/specs/2026-07-18-mq-familiar-cli-async-query-design.md`

## Global Constraints

- MQTT 只接受 MQTTX 子集；RabbitMQ 只接受 rabbitmqadmin 子集；不兼容旧 DSL，不做迁移提示
- 命令中的连接参数静默忽略，不覆盖 Instance；vhost/库以页面 `db_name` 为准
- 默认等待 60s；硬上限 3600s（`SysConfig` 键名见 Task 4）；`-C` 缺省 10、硬顶 100
- 仅 `mqtt`/`rabbitmq` 的 `sub`/`get` 异步；其它引擎与 MQ 其它命令同步
- RabbitMQ `get`：count 未满且未超时/取消时，空队列也干等
- 查询多行：每行 `sub`/`get` 各建一个 job；取消保留并展示已收到 rows
- 上线工单仍同步；多行失败中止
- Windows 开发用 PowerShell 时多命令用 `;` 分隔，不用 `&&`

## File Structure

| 路径 | 职责 |
|------|------|
| `sql/engines/mq_cli.py` | MQTTX / rabbitmqadmin 子集解析；忽略连接旗标；产出 `MqCommand` |
| `sql/engines/test_mq_cli.py` | 解析器单测 |
| `sql/engines/mqtt.py` | 改用 `mq_cli`；`query`/`execute_*` 新语法；暴露可取消的 subscribe 循环钩子 |
| `sql/engines/rabbitmq.py` | 同上（get 干等） |
| `sql/engines/test_mqtt.py` / `test_rabbitmq.py` | 更新为新语法用例 |
| `sql/services/mq_query_job.py` | job 创建 / 状态 / 取消 / worker |
| `sql/services/test_mq_query_job.py` | job 服务单测 |
| `sql_api/api_sqlquery.py` + `serializers.py` + `urls.py` | create/status/cancel 端点 |
| `sql/services/sqlquery_service.py` | 多行拆分：非长等待仍同步；检测整段是否需走 job 由前端/API 分流 |
| `sql/templates/sqlquery.html` | MQ `sub`/`get` 轮询 UI、离开页取消 |
| `scripts/mq_env/README.md` | 指令级用例改为新语法 |
| `common` SysConfig 使用处 | 读取 `mq_query_timeout_default` / `mq_query_timeout_max`（缺省 60 / 3600） |

---

### Task 1: CLI 解析器 `mq_cli.py`

**Files:**
- Create: `sql/engines/mq_cli.py`
- Create: `sql/engines/test_mq_cli.py`

**Interfaces:**
- Produces:
  - `@dataclass MqCommand`: `engine: str` (`mqtt`|`rabbitmq`), `action: str`, `args: dict`, `raw_line: str`
  - `parse_mqtt_line(line: str) -> MqCommand`（raises `ValueError`）
  - `parse_rabbitmq_line(line: str) -> MqCommand`
  - `split_mq_lines(sql: str) -> list[str]`（去空行与 `#` 注释）
  - 连接旗标集合常量 `MQTT_CONN_FLAGS` / `RABBITMQ_CONN_FLAGS`（含长短选项）

- [ ] **Step 1: Write failing tests**

```python
# sql/engines/test_mq_cli.py
import pytest
from sql.engines.mq_cli import parse_mqtt_line, parse_rabbitmq_line, split_mq_lines


def test_split_skips_blank_and_hash_comments():
    assert split_mq_lines("# a\n\npub -t t -m m\n") == ["pub -t t -m m"]


def test_mqtt_pub_strips_mqttx_prefix_and_ignores_host():
    cmd = parse_mqtt_line('mqttx pub -h 1.2.3.4 -p 1883 -t archery/test -m "hello" -q 1')
    assert cmd.action == "pub"
    assert cmd.args == {"topic": "archery/test", "payload": "hello", "qos": 1}


def test_mqtt_sub_defaults():
    cmd = parse_mqtt_line("sub -t archery/test")
    assert cmd.action == "sub"
    assert cmd.args["topic"] == "archery/test"
    assert cmd.args["qos"] == 0
    assert cmd.args["count"] == 10


def test_mqtt_rejects_unknown_flag():
    with pytest.raises(ValueError):
        parse_mqtt_line("sub -t t --bench")


def test_rabbitmq_get_and_publish():
    g = parse_rabbitmq_line("rabbitmqadmin get queue=q1 count=3 -H 127.0.0.1")
    assert g.action == "get"
    assert g.args == {"queue": "q1", "count": 3}
    p = parse_rabbitmq_line('publish routing_key=q1 payload="hi" exchange=')
    assert p.action == "publish"
    assert p.args["routing_key"] == "q1"
    assert p.args["payload"] == "hi"
    assert p.args.get("exchange", "") == ""


def test_old_dsl_rejected():
    with pytest.raises(ValueError):
        parse_mqtt_line('publish archery/test "hello"')
    with pytest.raises(ValueError):
        parse_rabbitmq_line("basic_get q1")
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

```bash
cd /mnt/e/github/Archery
source .venv-mq/bin/activate
export PYTHONPATH=/mnt/e/github/Archery
pytest sql/engines/test_mq_cli.py -v
```

Expected: `ModuleNotFoundError` or import error for `mq_cli`

- [ ] **Step 3: Implement `mq_cli.py`**

实现要点：

- 用 `shlex.split`；剥掉首 token `mqttx` / `rabbitmqadmin`
- MQTT：子命令 `pub`|`sub`|`help`；选项 `-t/--topic`、`-m/--message`、`-q/--qos`、`-C/--count`（仅 sub）；连接选项丢弃
- RabbitMQ：子命令 `get`|`publish`|`declare`|`purge`|`delete`|`list`|`help`；`get` 支持 `queue=` `count=`；`publish` 支持 `routing_key=` `payload=` `exchange=`；`declare queue name=`；`declare exchange name=` `type=`；`declare binding` 解析 queue/exchange/routing_key；`purge queue` / `delete queue`；`list queues`；连接与 `-V` 丢弃
- 旧 DSL 形态不要特判提示，自然因无法匹配而 `ValueError`

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest sql/engines/test_mq_cli.py -v
```

- [ ] **Step 5: Commit**

```bash
git add sql/engines/mq_cli.py sql/engines/test_mq_cli.py
git commit -m "feat(mq): add MQTTX and rabbitmqadmin subset parsers"
```

---

### Task 2: `MqttEngine` 切换到新语法（同步路径）

**Files:**
- Modify: `sql/engines/mqtt.py`
- Modify: `sql/engines/test_mqtt.py`

**Interfaces:**
- Consumes: `parse_mqtt_line`, `split_mq_lines`, `MqCommand`
- Produces:
  - `query_check` / `execute_check` 基于 `pub`/`sub`/`help`
  - `query(sql=...)`：支持多行；`help`/`sub`（同步 sub 仍可用于 worker 内部调用）
  - `run_subscribe(self, topic, qos, max_msgs, timeout_sec, cancel_check=None, on_message=None) -> ResultSet` 供 Task 4 worker 使用
  - `execute_workflow`：只接受 `pub` 行

- [ ] **Step 1: Rewrite failing engine tests to MQTTX syntax**

将 `test_mqtt.py` 中所有 `subscribe …` / `publish …` DSL 改为例如：

- 查询允许：`sub -t archery/test -C 5`
- 查询拒绝：`pub -t archery/test -m hi`
- 上线允许：`pub -t archery/test -m "hello world" -q 2`
- `help` 行内容改为 MQTTX 示例字符串
- 超时/条数：默认 timeout 来自参数或 60；硬顶 3600 在调用方裁剪（引擎 `run_subscribe` 接收已裁剪值）

先改测试再跑，确认失败（旧实现仍认 DSL）。

- [ ] **Step 2: Run targeted tests — expect FAIL on assertions**

```bash
pytest sql/engines/test_mqtt.py -v
```

- [ ] **Step 3: Implement engine changes**

- `query_check`：对每一行 `parse_mqtt_line`；仅 `sub`/`help` 通过
- `execute_check`：仅 `pub`；`sub`/`help` →「禁止使用查询命令！」
- `query`：多行循环；`sub` 调用 `run_subscribe`（同步，无 cancel）
- `run_subscribe`：现有订阅循环抽出；每条消息可调 `on_message(row)`；每 tick 若 `cancel_check and cancel_check(): break`
- `execute_workflow`：`pub` → 现有 publish 逻辑（从 `cmd.args` 取 topic/payload/qos）

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest sql/engines/test_mqtt.py sql/engines/test_mq_cli.py -v
```

- [ ] **Step 5: Commit**

```bash
git add sql/engines/mqtt.py sql/engines/test_mqtt.py
git commit -m "feat(mqtt): switch engine to MQTTX subset commands"
```

---

### Task 3: `RabbitmqEngine` 切换到新语法 + get 干等

**Files:**
- Modify: `sql/engines/rabbitmq.py`
- Modify: `sql/engines/test_rabbitmq.py`

**Interfaces:**
- Consumes: `parse_rabbitmq_line`, `split_mq_lines`
- Produces: `run_get(queue, count, timeout_sec, cancel_check=None, on_message=None) -> ResultSet`（空队列干等到超时）

- [ ] **Step 1: Update tests to rabbitmqadmin syntax**

- 查询：`get queue=archery_test_queue count=1`、`list queues`、`help`
- 拒绝：`publish routing_key=q payload=x` 出现在 query_check
- 上线：`publish` / `declare queue` / `declare exchange` / `declare binding` / `purge queue` / `delete queue`
- 新增：`run_get` 在 mock `basic_get` 连续返回空时，仍循环直到 `cancel_check` 或 timeout（用 mock time / cancel 触发，避免真睡 60s）

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest sql/engines/test_rabbitmq.py -v
```

- [ ] **Step 3: Implement**

- 解析与白名单对齐 spec §5.4
- `run_get`：`while not cancelled and not timed_out and len(rows) < count: method, props, body = basic_get(...); if method: ack + append + on_message; else: sleep(0.05)`
- `query` 多行；`list queues`：**query_check 允许**（与定稿一致）。因 v1 无 Management API，`query()` 返回 `ResultSet(error="list queues 需要 RabbitMQ Management API，当前引擎未启用")`，不假装成功。单测断言该 error 文案。禁止为通过 list 而引入 Management HTTP 客户端。

- [ ] **Step 4: PASS**

```bash
pytest sql/engines/test_rabbitmq.py sql/engines/test_mq_cli.py -v
```

- [ ] **Step 5: Commit**

```bash
git add sql/engines/rabbitmq.py sql/engines/test_rabbitmq.py
git commit -m "feat(rabbitmq): switch to rabbitmqadmin subset; get waits until timeout"
```

---

### Task 4: `MqQueryJobService`（cache + async_task）

**Files:**
- Create: `sql/services/mq_query_job.py`
- Create: `sql/services/test_mq_query_job.py`

**Interfaces:**
- Produces:
  - `create_mq_query_job(user, instance_id, db_name, sql_line) -> dict` with `job_id`
  - `get_mq_query_job(user, job_id) -> dict` status payload
  - `cancel_mq_query_job(user, job_id) -> dict`
  - `run_mq_query_job(job_id: str) -> None`（django-q 入口）
- Cache key: `mq_query_job:{job_id}`；TTL >= hard max + 600s
- Payload shape:

```python
{
  "job_id": str,
  "user_id": int,
  "instance_id": int,
  "db_name": str,
  "sql_line": str,
  "status": "pending"|"running"|"partial"|"done"|"cancelled"|"failed",
  "column_list": list,
  "rows": list,          # incremental
  "warning": str,
  "error": str,
  "cancel": False,
  "timeout_sec": int,
}
```

- [ ] **Step 1: Failing tests**

```python
# sql/services/test_mq_query_job.py
import pytest
from django.core.cache import cache
from sql.services import mq_query_job as svc

@pytest.mark.django_db
def test_create_rejects_non_mq_instance(db_instance, normal_user):
    # db_instance fixture is mysql
    with pytest.raises(ValueError):
        svc.create_mq_query_job(normal_user, db_instance.id, "db", "sub -t t")

@pytest.mark.django_db
def test_cancel_sets_flag(mqtt_instance, normal_user, monkeypatch):
    # create mqtt Instance in fixture or inline
    ...
```

（测试中构造 `db_type=mqtt` 的 Instance；`monkeypatch` `async_task` 为同步立即调用或 no-op，再单测 `run_mq_query_job` 读 cancel。）

最小用例：

1. create 写入 cache status=pending/running  
2. cancel → `cancel=True`，最终 status=cancelled 且 rows 保留  
3. `timeout_sec` 被 clamp 到 `[1, max]`，默认 60，max 来自 SysConfig 缺省 3600  

SysConfig keys:

- `mq_query_timeout_default` → int，默认 60  
- `mq_query_timeout_max` → int，默认 3600  

从命令行无法表达 timeout 时（MQTTX sub 无标准短超时旗标）：**只用 SysConfig 默认**，不新增自造 CLI 旗标（符合定稿：避免再学参数）。可选：若解析到非连接的未知超时旗标则拒绝。

- [ ] **Step 2: Run — FAIL**

```bash
pytest sql/services/test_mq_query_job.py -v
```

- [ ] **Step 3: Implement service**

```python
def create_mq_query_job(user, instance_id, db_name, sql_line):
    instance = user_instances(user, tag_codes=["can_read"]).get(id=instance_id)
    if instance.db_type not in ("mqtt", "rabbitmq"):
        raise ValueError("仅 MQTT/RabbitMQ 支持异步查询任务")
    line = sql_line.strip()
    if instance.db_type == "mqtt":
        cmd = parse_mqtt_line(line)
        if cmd.action != "sub":
            raise ValueError("仅 sub 支持异步任务")
    else:
        cmd = parse_rabbitmq_line(line)
        if cmd.action != "get":
            raise ValueError("仅 get 支持异步任务")
    # build job, cache.set, async_task("sql.services.mq_query_job.run_mq_query_job", job_id)
    ...

def run_mq_query_job(job_id):
    job = cache.get(...)
    engine = get_engine(instance)
    def cancel_check():
        j = cache.get(key)
        return bool(j and j.get("cancel"))
    def on_message(row):
        j = cache.get(key)
        j["rows"].append(row)
        j["status"] = "partial"
        cache.set(key, j, ttl)
    # call engine.run_subscribe / run_get
    # set done/cancelled/failed
```

权限：create/get/cancel 均校验 `job["user_id"] == request.user.id`（或超管）。

- [ ] **Step 4: PASS + Commit**

```bash
pytest sql/services/test_mq_query_job.py -v
git add sql/services/mq_query_job.py sql/services/test_mq_query_job.py
git commit -m "feat(mq): add cancelable async query job service"
```

---

### Task 5: API 端点

**Files:**
- Modify: `sql_api/serializers.py`（新增 Job create/status/cancel serializer）
- Modify: `sql_api/api_sqlquery.py`
- Modify: `sql_api/urls.py`
- Create or modify: `sql_api/tests.py`（或 `sql_api/test_mq_query_job_api.py`）

**Interfaces:**
- `POST /api/v1/sqlquery/mq-jobs/` body: `{instance_id|instance_name, db_name, sql_line}` → `{job_id}`
- `GET /api/v1/sqlquery/mq-jobs/<job_id>/` → job payload（无 `cancel` 字段对外可省略）
- `POST /api/v1/sqlquery/mq-jobs/<job_id>/cancel/` → `{status: cancelled|...}`

- [ ] **Step 1: API tests with APIClient + mock async_task**

- [ ] **Step 2: FAIL then implement views wiring `mq_query_job` service**

- [ ] **Step 3: PASS + Commit**

```bash
git add sql_api/serializers.py sql_api/api_sqlquery.py sql_api/urls.py sql_api/test_mq_query_job_api.py
git commit -m "feat(mq): expose mq async query job APIs"
```

---

### Task 6: 查询页前端（增量 + 关页取消）

**Files:**
- Modify: `sql/templates/sqlquery.html`

**行为：**

1. 执行前：若当前实例 `db_type` 为 mqtt/rabbitmq，将编辑器按行拆分（跳过空行/`#`）。  
2. 对每行：若以 `sub`/`mqttx sub` 或 `get`/`rabbitmqadmin get` 开头 → `POST mq-jobs`，记下 `job_id`；否则走原同步 execute（整段或按行，保持与现网一致的最小改动：**MQ 实例下按行分流**）。  
3. 对每个 job：每 500ms `GET` 状态；`partial`/`done`/`cancelled` 时刷新结果表（追加或按 job 分块展示）。  
4. `pagehide`/`beforeunload`/用户点停止：对未完成 job `POST cancel`。  
5. `help` / 其它同步行：仍走原 API。

- [ ] **Step 1: 实现前端分流与轮询（无自动化前端测时，用手工清单）**

手工验收（写入 PR 说明）：

- MQTT：`sub -t archery/test` 等待中发消息，表格增量出现  
- 关页或停止后 worker 停止（日志/二次 publish 不再增加）  
- RabbitMQ：`get queue=q count=5` 空队列干等，超时后 0 行 + warning  
- MySQL 实例执行不受影响  

- [ ] **Step 2: Commit**

```bash
git add sql/templates/sqlquery.html
git commit -m "feat(mq): poll async mq jobs with incremental results and cancel on leave"
```

---

### Task 7: 文档与种子说明

**Files:**
- Modify: `scripts/mq_env/README.md`（指令级用例改为 MQTTX / rabbitmqadmin；删除旧 DSL 示例）
- Modify: `docs/superpowers/specs/2026-07-17-mqtt-rabbitmq-engine-design.md` 顶部加一行：**命令语法以 2026-07-18 spec 为准**（仅加注，避免大面积换行噪声）

- [ ] **Step 1: 更新 README 最小回归路径命令**

示例：

```text
sub -t archery/test
pub -t archery/test -m "hello from archery"
get queue=archery_test_queue count=1
publish routing_key=archery_test_queue payload="hello from archery"
```

- [ ] **Step 2: Commit**

```bash
git add scripts/mq_env/README.md docs/superpowers/specs/2026-07-17-mqtt-rabbitmq-engine-design.md
git commit -m "docs(mq): replace custom DSL examples with MQTTX/rabbitmqadmin"
```

---

## Spec coverage checklist

| Spec 项 | Task |
|---------|------|
| MQTTX / rabbitmqadmin 解析与忽略连接参数 | 1 |
| 引擎白名单与执行 | 2, 3 |
| 不兼容旧 DSL | 1–3 测试 |
| get 干等超时 | 3, 4 |
| 异步+取消+增量；仅 sub/get | 4–6 |
| 默认 60 / 硬顶 3600 SysConfig | 4 |
| 多行每行一 job | 4, 6 |
| 其它引擎不受影响 | 4 校验 + 6 手工 |
| 文档 | 7 |
| `list queues` 无 Mgmt API | Task 3：允许命令但执行返回明确 error |

## Placeholder / consistency review

- 无 TBD；`list queues` 冲突已在 Task 3 用可实现裁决收口  
- Job payload 字段名在 Task 4/5/6 一致  
- 超时仅 SysConfig，不新增自造 CLI 超时旗标  

---

## Execution Handoff
