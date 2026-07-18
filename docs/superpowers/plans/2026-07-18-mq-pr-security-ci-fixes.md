# MQ PR Security & CI Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 关闭 PR #3218 的 CI 门禁与约定范围内的安全/MQ 质量审查项，且不改变其它数据库引擎行为。

**Architecture:** 外科式 MQ-only 补丁：删除污染全局的测试 shim；在 `db_type in {mqtt,rabbitmq}` 或 MQ 专用模块内修补权限、密钥、导出、Explain、CLI/引擎与 job 入队 timeout。全局 `Q_CLUISTER_TIMEOUT` 默认保持 master 的 60。

**Tech Stack:** Django、django-q2（`async_task(..., timeout=…)`）、pika、pytest、black、现有 `query_priv_check` / DRF serializers / `sqlquery.html`

**Spec:** `docs/superpowers/specs/2026-07-18-mq-pr-security-ci-fixes-design.md`

## Global Constraints

- 行为变更仅 `mqtt`/`rabbitmq` 或 MQ 专用模块；共享文件只加显式 MQ 分支或 write_only
- **禁止** 修改 `archery/settings.py` 中 `Q_CLUSTER["timeout"]` / `Q_CLUISTER_TIMEOUT` 默认值（保持 60）
- **禁止** 提交本地 `manage.py` 的 `pymysql.install_as_MySQLdb()` shim
- MQ 等待默认仍 60 / 硬顶 3600（SysConfig）；不改回早期 30s
- Windows PowerShell 多命令用 `;`，不用 `&&`
- 每个 Task 结束单独 commit；消息用英文 concise 风格（`fix(mq): …` / `test(mq): …`）

## File Structure

| 路径 | 职责 |
|------|------|
| `sql/services/conftest.py` | 去掉 PyMySQL shim；保留 MQ 测试 fixture |
| `sql_api/conftest.py` | 同上 |
| `sql/query_privileges.py` | mqtt/rabbitmq 并入「当前库」校验分支 |
| `sql/services/mq_query_job.py` | `query_priv_check`；`async_task` per-task timeout |
| `sql_api/serializers.py` | `client_key`/`client_cert` write_only |
| `sql/offlinedownload.py` | MQ 拒绝离线导出；移出 `LINE_BASED_COMMAND_ENGINES` |
| `sql_api/api_sqlquery.py` | MQ API 错误文案消毒 |
| `sql/templates/sqlquery.html` | MQ 禁用 Explain |
| `sql/engines/mqtt.py` / `rabbitmq.py` | `query_check` 拒 explain；durable；publish confirm |
| `sql/engines/mq_cli.py` | 行首连接旗标；`durable=` 解析 |
| 对应 `test_*.py` | TDD 覆盖 |

---

### Task 1: 去掉 conftest PyMySQL shim（修复 Django CI 污染）

**Files:**
- Modify: `sql/services/conftest.py`
- Modify: `sql_api/conftest.py`
- Test: 既有 `sql/services/test_mq_query_job.py`、`sql_api/test_mq_query_job_api.py`（确认仍能收集/跑通 fixture）

**Interfaces:**
- Consumes: 根目录 `conftest.py` 的 `normal_user` / `db_instance` / `super_user`（若子 conftest 删除重复 fixture，测试改用根 fixture；若保留本地 fixture，只删 shim 行）
- Produces: 无进程级 `pymysql.install_as_MySQLdb()`

- [ ] **Step 1: 写/确认回归探针（可选小测）**

在 `sql/services/test_mq_query_job.py` 顶部附近确保至少有一个使用 `db`/`mqtt_instance` 的现有用例；本 Task 不改业务断言。探针目的：去掉 shim 后 fixture 仍工作。

- [ ] **Step 2: 删除 shim**

从两个 conftest 删除：

```python
import pymysql

pymysql.install_as_MySQLdb()
```

保留其余 fixture。若两处与根 `conftest.py` 完全重复的 `normal_user`/`db_instance`，可删除重复 fixture 并让测试依赖根 conftest（pytest 会向上查找）；**不要**引入新的 MySQLdb 垫片。

- [ ] **Step 3: 跑 MQ 相关测试**

```powershell
wsl -e bash -lc 'cd /mnt/e/github/Archery; source .venv-mq/bin/activate; pytest -q sql/services/test_mq_query_job.py sql_api/test_mq_query_job_api.py sql/engines/test_mqtt.py sql/engines/test_rabbitmq.py sql/engines/test_mq_cli.py'
```

Expected: PASS（或仅与本机 sqlite lock 无关的既有环境问题；CI 使用 mysqlclient，不应再有 `COMMAND` ImportError）。

- [ ] **Step 4: Commit**

```powershell
git add sql/services/conftest.py sql_api/conftest.py
git commit -m "fix(mq): stop pymysql MySQLdb shim in test confests"
```

---

### Task 2: black 格式化本分支文件

**Files:**
- Modify: CI 报出的约 13 个需重排文件（以 `black` dry-run 列表为准）

**Interfaces:** 无

- [ ] **Step 1: 列出需格式化文件**

```powershell
wsl -e bash -lc 'cd /mnt/e/github/Archery; source .venv-mq/bin/activate; black --check --diff .'
```

Expected: 列出 would reformat 的路径（约 13 个，多为 MQ 相关）。

- [ ] **Step 2: 只格式化失败列表中的文件**

```powershell
wsl -e bash -lc 'cd /mnt/e/github/Archery; source .venv-mq/bin/activate; black <file1> <file2> ...'
```

勿对无关大范围机械重排。

- [ ] **Step 3: 再 check**

```powershell
wsl -e bash -lc 'cd /mnt/e/github/Archery; source .venv-mq/bin/activate; black --check .'
```

Expected: All done / 无 would reformat。

- [ ] **Step 4: Commit**

```powershell
git add <formatted files>
git commit -m "style(mq): apply black to branch files"
```

---

### Task 3: MQ job 调用 `query_priv_check` + 当前库分支

**Files:**
- Modify: `sql/query_privileges.py`（约 103 行：`redis`/`mssql`/`pgsql` 列表）
- Modify: `sql/services/mq_query_job.py`（`create_mq_query_job`）
- Modify: `sql/services/test_mq_query_job.py`
- Modify: `sql/test_query_privileges.py`（可选一条 mqtt 当前库用例）

**Interfaces:**
- Consumes: `query_priv_check(user, instance, db_name, sql_content, limit_num) -> dict`（`status` 0=ok，2=无库权限）
- Produces: `create_mq_query_job` 在 priv 失败时 `raise PermissionError(msg)`（API Task 5 映射 403）

- [ ] **Step 1: 写失败测试**

```python
# sql/services/test_mq_query_job.py
@pytest.mark.django_db
def test_create_mq_job_requires_db_priv(monkeypatch, normal_user, mqtt_instance):
    from django.contrib.auth.models import Permission

    perm = Permission.objects.get(codename="query_submit")
    normal_user.user_permissions.add(perm)
    # 用户可读实例，但无任何库查询权限
    monkeypatch.setattr(
        "sql.services.mq_query_job.query_priv_check",
        lambda *a, **k: {"status": 2, "msg": "你无db的查询权限！请先到查询权限管理进行申请", "data": {}},
    )
    with pytest.raises(PermissionError):
        svc.create_mq_query_job(
            user=normal_user,
            instance_id=mqtt_instance.id,
            db_name="vhost1",
            sql_line="sub -t t",
        )
```

同时在 `sql/query_privileges.py` 测试中加（或改）断言：`db_type=="mqtt"` 时只校验 `db_name`，不走 `extract_tables`（可 mock `extract_tables` 确认未被调用）。

- [ ] **Step 2: 跑测确认失败**

```powershell
wsl -e bash -lc 'cd /mnt/e/github/Archery; source .venv-mq/bin/activate; pytest -q sql/services/test_mq_query_job.py::test_create_mq_job_requires_db_priv -v'
```

Expected: FAIL（尚未调用 priv 或未 raise）。

- [ ] **Step 3: 实现**

`sql/query_privileges.py`：

```python
if instance.db_type in ["redis", "mssql", "pgsql", "mqtt", "rabbitmq"]:
    dbs = [db_name]
```

`sql/services/mq_query_job.py`：

```python
from sql.query_privileges import query_priv_check

def create_mq_query_job(user, instance_id, db_name, sql_line) -> dict:
    instance = _get_readable_instance(user, instance_id)
    # ... 现有 db_type / parse / validate ...
    priv = query_priv_check(user, instance, db_name or "", line, 0)
    if priv.get("status") != 0:
        raise PermissionError(priv.get("msg") or "无查询权限")
    # ... 现有 enqueue ...
```

`limit_num=0` 可接受：非 MySQL 分支只用来算最小 limit；MQ 条数由 CLI `-C`/`count` 控制。

- [ ] **Step 4: 跑测通过**

```powershell
wsl -e bash -lc 'cd /mnt/e/github/Archery; source .venv-mq/bin/activate; pytest -q sql/services/test_mq_query_job.py sql/test_query_privileges.py -k "mqtt or rabbitmq or create_mq or redis" '
```

Expected: 相关用例 PASS；其它引擎 priv 用例不被破坏。

- [ ] **Step 5: Commit**

```powershell
git add sql/query_privileges.py sql/services/mq_query_job.py sql/services/test_mq_query_job.py sql/test_query_privileges.py
git commit -m "fix(mq): require query_priv_check for async mq jobs"
```

---

### Task 4: Instance API `client_key` / `client_cert` write_only

**Files:**
- Modify: `sql_api/serializers.py`（`InstanceSerializer`、`InstanceDetailSerializer`）
- Create 或 Modify: `sql_api/test_instance_serializer_secrets.py`（短文件即可）

**Interfaces:**
- Produces: GET 序列化结果不含 `client_key`/`client_cert`；写入仍可接受

- [ ] **Step 1: 写失败测试**

```python
# sql_api/test_instance_serializer_secrets.py
import pytest
from sql.models import Instance
from sql_api.serializers import InstanceSerializer, InstanceDetailSerializer


@pytest.mark.django_db
def test_instance_serializer_hides_client_key_and_cert():
    ins = Instance.objects.create(
        instance_name="sec_ins",
        type="slave",
        db_type="mqtt",
        host="127.0.0.1",
        port=8883,
        user="",
        password="secret-pass",
        client_cert="CERTPEM",
        client_key="KEYPEM",
    )
    data = InstanceSerializer(ins).data
    assert "password" not in data or data.get("password") in (None, "", "******")
    # password 已是 write_only：键通常不在 data
    assert "client_key" not in data
    assert "client_cert" not in data
    detail = InstanceDetailSerializer(ins).data
    assert "client_key" not in detail
    assert "client_cert" not in detail
```

（若项目对 `password` 的序列化表现特殊，只强断言 `client_key`/`client_cert` 不在 data。）

- [ ] **Step 2: 跑测确认失败**

```powershell
wsl -e bash -lc 'cd /mnt/e/github/Archery; source .venv-mq/bin/activate; pytest -q sql_api/test_instance_serializer_secrets.py -v'
```

Expected: FAIL（字段仍出现在 `__all__` 读出）。

- [ ] **Step 3: 实现**

```python
class InstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instance
        fields = "__all__"
        extra_kwargs = {
            "password": {"write_only": True},
            "client_key": {"write_only": True},
            "client_cert": {"write_only": True},
        }


class InstanceDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instance
        fields = "__all__"
        extra_kwargs = {
            "password": {"write_only": True},
            "client_key": {"write_only": True},
            "client_cert": {"write_only": True},
            "instance_name": {"required": False},
            "type": {"required": False},
            "db_type": {"required": False},
            "host": {"required": False},
        }
```

- [ ] **Step 4: 跑测通过 + Commit**

```powershell
wsl -e bash -lc 'cd /mnt/e/github/Archery; source .venv-mq/bin/activate; pytest -q sql_api/test_instance_serializer_secrets.py -v'
git add sql_api/serializers.py sql_api/test_instance_serializer_secrets.py
git commit -m "fix(mq): hide client_key and client_cert on instance API"
```

---

### Task 5: 离线导出拒绝 mqtt/rabbitmq

**Files:**
- Modify: `sql/offlinedownload.py`
- Create 或 Modify: `sql/test_offlinedownload_mq.py`（或现有 offlinedownload 测试文件）

**Interfaces:**
- Produces: `LINE_BASED_COMMAND_ENGINES = {"redis", "memcached"}`；`pre_count_check` / `execute_offline_download` 对 mqtt/rabbitmq 立即失败且不调用 `engine.query`

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.django_db
def test_pre_count_check_rejects_mqtt(monkeypatch, db):
    from sql.offlinedownload import OffLineDownLoad, LINE_BASED_COMMAND_ENGINES
    from sql.models import Instance
    from types import SimpleNamespace

    assert "mqtt" not in LINE_BASED_COMMAND_ENGINES
    assert "rabbitmq" not in LINE_BASED_COMMAND_ENGINES

    ins = Instance.objects.create(
        instance_name="mq_exp", type="slave", db_type="mqtt",
        host="127.0.0.1", port=1883, user="", password="",
    )
    called = {"query": False}

    class BoomEngine:
        def query_check(self, **kwargs):
            return {"bad_query": False, "filtered_sql": "sub -t t"}
        def query(self, **kwargs):
            called["query"] = True
            raise AssertionError("must not query")
        def filter_sql(self, sql, limit_num):
            return sql

    monkeypatch.setattr("sql.offlinedownload.get_engine", lambda instance: BoomEngine())
    wf = SimpleNamespace(
        sql_content="sub -t t",
        instance=ins,
        db_type="mqtt",
        db_name="",
        selected_db_name="",
    )
    # OffLineDownLoad.pre_count_check 使用 workflow.instance
    result = OffLineDownLoad().pre_count_check(wf)
    assert result.error_count >= 1
    assert called["query"] is False
    assert any("离线导出" in (r.errormessage or "") for r in result.rows)
```

（按 `pre_count_check` 实际读取的 workflow 字段微调 SimpleNamespace；核心是 **不** `query`。）

- [ ] **Step 2: 跑测确认失败**

- [ ] **Step 3: 实现**

```python
LINE_BASED_COMMAND_ENGINES = {"redis", "memcached"}
MQ_EXPORT_UNSUPPORTED = frozenset({"mqtt", "rabbitmq"})
```

在 `pre_count_check` 开头（拿到 `instance` 后）：

```python
if instance.db_type in MQ_EXPORT_UNSUPPORTED:
    result = ReviewResult(
        stage="自动审核失败",
        errlevel=2,
        stagestatus="检查未通过！",
        errormessage="MQTT/RabbitMQ 不支持离线导出",
        affected_rows=0,
        sql=full_sql,
    )
    check_result.rows = [result]
    check_result.error_count = 1
    return check_result
```

在 `execute_offline_download` 开头同样拒绝（防御）。

- [ ] **Step 4: 跑测通过 + Commit**

```powershell
git commit -m "fix(mq): reject offline export for mqtt and rabbitmq"
```

---

### Task 6: MQ API 错误信息消毒（CodeQL）

**Files:**
- Modify: `sql_api/api_sqlquery.py`
- Modify: `sql_api/test_mq_query_job_api.py`

**Interfaces:**
- Produces: `_mq_public_error_msg(exc) -> str`；PermissionError/未知异常不回传 `str(exc)` 原始内容；已知 ValueError 用固定中文短句白名单

- [ ] **Step 1: 写失败测试**

```python
def test_create_mq_job_permission_error_is_generic(monkeypatch, api_client, query_user, mqtt_named_instance):
    def boom(*a, **k):
        raise PermissionError("内部路径 /secret/traceback 细节")
    monkeypatch.setattr("sql_api.api_sqlquery.create_mq_query_job", boom)
    api_client.force_authenticate(user=query_user)
    resp = api_client.post(MQ_JOBS, {...})
    assert resp.status_code == 403
    assert "/secret/" not in resp.data["msg"]
    assert "traceback" not in resp.data["msg"].lower()
```

对 `ValueError("仅 sub 支持异步任务")` 仍可返回该业务短句（在白名单内）。

- [ ] **Step 2: 跑测确认失败**

- [ ] **Step 3: 实现**

```python
_MQ_VALUE_ERROR_MESSAGES = frozenset({
    "仅 MQTT/RabbitMQ 支持异步查询任务",
    "sql_line 不能为空",
    "仅 sub 支持异步任务",
    "仅 get 支持异步任务",
    # 引擎校验可能抛出的短句可按测试补全
})

def _mq_client_error_msg(exc: Exception, *, permission: bool = False) -> str:
    if permission:
        # priv 文案允许透出（无路径）；其它 PermissionError 用固定句
        msg = str(exc)
        if msg and "权限" in msg and "/" not in msg and "Traceback" not in msg:
            return msg
        return "无权访问该查询任务"
    msg = str(exc)
    if msg in _MQ_VALUE_ERROR_MESSAGES:
        return msg
    logger.warning("mq job api error: %s", exc, exc_info=True)
    return "请求无效"
```

create/get/cancel 中：

```python
except ValueError as exc:
    return Response({"msg": _mq_client_error_msg(exc)}, status=400)
except PermissionError as exc:
    return Response({"msg": _mq_client_error_msg(exc, permission=True)}, status=403)
```

- [ ] **Step 4: 跑测通过 + Commit**

```powershell
git commit -m "fix(mq): sanitize mq job API error responses"
```

---

### Task 7: Explain 对 MQ 禁用（前端 + 后端）

**Files:**
- Modify: `sql/templates/sqlquery.html`
- Modify: `sql/engines/mqtt.py`、`sql/engines/rabbitmq.py`（`query_check`）
- Modify: `sql/engines/test_mqtt.py`、`sql/engines/test_rabbitmq.py`

**Interfaces:**
- Produces: 前端 `isMqEngine` 时隐藏 `#btn-explain`；后端若 SQL 以 `explain` 开头则 `bad_query`

- [ ] **Step 1: 写后端失败测试**

```python
def test_mqtt_query_check_rejects_explain_prefix():
    engine = MqttEngine(instance=SimpleNamespace(...))  # 按现有测试构造
    out = engine.query_check(sql="explain sub -t t")
    assert out["bad_query"] is True
    assert "explain" in out["msg"].lower() or "不支持" in out["msg"]
```

- [ ] **Step 2: 跑测确认失败**

- [ ] **Step 3: 实现后端**

在 `MqttEngine.query_check` / `RabbitmqEngine.query_check` 的 `filtered_sql = sql.strip()` 之后：

```python
lowered = filtered_sql.lower()
if lowered.startswith("explain ") or lowered.startswith("explain\n") or lowered == "explain":
    return {
        "bad_query": True,
        "filtered_sql": filtered_sql,
        "msg": "MQTT/RabbitMQ 不支持执行计划",
    }
```

- [ ] **Step 4: 前端**

在 `sqlquery.html` 已有 `isMqEngine` 处：

1. 切换实例/库类型时：`$("#btn-explain").toggle(!isMqEngine(dbType));`
2. `$("#btn-explain").click` 开头：

```javascript
if (isMqEngine(getCurrentDbType())) {  // 使用页面已有取 dbType 方式
    alert('MQTT/RabbitMQ 不支持执行计划');
    return false;
}
```

（`getCurrentDbType` 换成模板里现有变量，如 `sessionStorage` / `#db_type` 同类读取。）

- [ ] **Step 5: 跑测 + Commit**

```powershell
git commit -m "fix(mq): disable explain for mqtt and rabbitmq"
```

---

### Task 8: rabbitmqadmin / mqttx 行首连接旗标

**Files:**
- Modify: `sql/engines/mq_cli.py`
- Modify: `sql/engines/test_mq_cli.py`

**Interfaces:**
- Produces: `parse_rabbitmq_line` / `parse_mqtt_line` 在读 action 前跳过 `RABBITMQ_CONN_FLAGS` / `MQTT_CONN_FLAGS`（及取值）；`--host=x` 形式若需支持可在跳过逻辑中处理 `flag.startswith("--") and "=" in flag`

- [ ] **Step 1: 写失败测试**

```python
def test_rabbitmq_leading_conn_flags_ignored():
    cmd = parse_rabbitmq_line(
        "rabbitmqadmin -H 10.0.0.1 -P 15672 -u guest -p guest get queue=q1 count=2"
    )
    assert cmd.action == "get"
    assert cmd.args == {"queue": "q1", "count": 2}


def test_mqtt_leading_conn_flags_ignored():
    cmd = parse_mqtt_line("mqttx -h 1.2.3.4 -p 1883 sub -t archery/test")
    assert cmd.action == "sub"
    assert cmd.args["topic"] == "archery/test"
```

- [ ] **Step 2: 跑测确认失败**（当前会把 `-H` 当成 action）

- [ ] **Step 3: 实现**

```python
def _skip_leading_conn_flags(tokens: list[str], conn_flags: frozenset) -> list[str]:
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in conn_flags:
            i = _consume_flag_value(tokens, i)
            continue
        if tok.startswith("--") and "=" in tok:
            name = tok.split("=", 1)[0]
            if name in conn_flags:
                i += 1
                continue
        break
    return tokens[i:]
```

在 `parse_mqtt_line` / `parse_rabbitmq_line` 去掉 `mqttx`/`rabbitmqadmin` 前缀后：

```python
tokens = _skip_leading_conn_flags(tokens, MQTT_CONN_FLAGS)  # 或 RABBITMQ_
```

- [ ] **Step 4: 跑测通过 + Commit**

```powershell
git commit -m "fix(mq): ignore leading connection flags in mq CLI parsers"
```

---

### Task 9: `durable=` 传入 declare

**Files:**
- Modify: `sql/engines/mq_cli.py`（declare 时解析 `durable` 为 bool，写入 `args`）
- Modify: `sql/engines/rabbitmq.py`（`queue_declare` / `exchange_declare`）
- Modify: `sql/engines/test_mq_cli.py`、`sql/engines/test_rabbitmq.py`

**Interfaces:**
- Produces: `args["durable"]` 仅在用户写出时存在；引擎 `if "durable" in args: kwargs["durable"]=args["durable"]`

- [ ] **Step 1: 写失败测试**

```python
def test_declare_queue_parses_durable():
    cmd = parse_rabbitmq_line("declare queue name=q1 durable=true")
    assert cmd.args["name"] == "q1"
    assert cmd.args["durable"] is True


def test_queue_declare_passes_durable(monkeypatch):
    # mock channel.queue_declare 捕获 kwargs
    ...
    RabbitmqEngine._execute_write_command(channel, cmd)
    assert called["durable"] is True
```

未写 `durable` 的既有用例：`queue_declare` **不**传 `durable=`（保持现状）。

- [ ] **Step 2: 跑测确认失败**

- [ ] **Step 3: 实现**

在 `parse_rabbitmq_line` 的 declare 分支后：

```python
if "durable" in args:
    val = args["durable"].lower()
    if val not in {"true", "false", "1", "0", "yes", "no"}:
        raise ValueError("durable must be true or false")
    args["durable"] = val in {"true", "1", "yes"}
```

```python
elif target == "queue":
    kwargs = {"queue": args["name"]}
    if "durable" in args:
        kwargs["durable"] = args["durable"]
    channel.queue_declare(**kwargs)
elif target == "exchange":
    kwargs = {
        "exchange": args["name"],
        "exchange_type": args.get("type", "direct"),
    }
    if "durable" in args:
        kwargs["durable"] = args["durable"]
    channel.exchange_declare(**kwargs)
```

- [ ] **Step 4: 跑测通过 + Commit**

```powershell
git commit -m "feat(mq): pass durable flag through rabbitmq declare"
```

---

### Task 10: 不可路由 publish 失败

**Files:**
- Modify: `sql/engines/rabbitmq.py`（`_execute_write_command`）
- Modify: `sql/engines/test_rabbitmq.py`

**Interfaces:**
- Produces: publish 前 `channel.confirm_delivery()`；`basic_publish(..., mandatory=True)`；捕获 `pika.exceptions.UnroutableError`（及若存在的 Nack 类）转为 `ValueError("消息不可路由")` 或原样抛出由 `execute_workflow` 记失败

- [ ] **Step 1: 写失败测试**

```python
def test_publish_unroutable_raises(monkeypatch):
    import pika.exceptions

    class Ch:
        def confirm_delivery(self):
            self.confirmed = True
        def basic_publish(self, **kwargs):
            assert kwargs.get("mandatory") is True
            raise pika.exceptions.UnroutableError("x")

    with pytest.raises((pika.exceptions.UnroutableError, ValueError)):
        RabbitmqEngine._execute_write_command(Ch(), cmd_publish)
```

并断言成功路径会调用 `confirm_delivery`。

- [ ] **Step 2: 跑测确认失败**

- [ ] **Step 3: 实现**

```python
if action == "publish":
    channel.confirm_delivery()
    channel.basic_publish(
        exchange=args.get("exchange", ""),
        routing_key=args["routing_key"],
        body=args["payload"],
        mandatory=True,
    )
```

若 pika 版本对不可路由行为不同，以测试为准包一层：

```python
try:
    channel.basic_publish(...)
except Exception as exc:
    if type(exc).__name__ in {"UnroutableError", "NackError"}:
        raise ValueError("消息不可路由或未被确认") from exc
    raise
```

- [ ] **Step 4: 跑测通过 + Commit**

```powershell
git commit -m "fix(mq): fail unroutable rabbitmq publish"
```

---

### Task 11: MQ job `async_task` per-task timeout

**Files:**
- Modify: `sql/services/mq_query_job.py`（`_enqueue_mq_query_job`）
- Modify: `sql/services/test_mq_query_job.py`
- Modify（可选一句）: `scripts/mq_env/README.md` — 说明异步模式下 `Q_CLUISTER_TIMEOUT` 应 ≥ `mq_query_timeout_max`，**默认 settings 仍为 60**

**Interfaces:**
- Consumes: django-q2 `async_task(func, *args, timeout=seconds)`（见 `.venv-mq/.../django_q/tasks.py` opt_keys 含 `timeout`）
- Produces: 非 sync 入队：`async_task(..., job_id, timeout=timeout_sec + 60)`；**不**改 `settings.Q_CLUSTER`

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.django_db
def test_enqueue_passes_timeout_to_async_task(monkeypatch, mqtt_instance, normal_user):
    captured = {}
    monkeypatch.setattr(svc.settings.Q_CLUSTER, "get", lambda k, d=None: False if k == "sync" else d)
    # 更稳妥：monkeypatch settings.Q_CLUSTER 为 {"sync": False, ...}
    def fake_async_task(func, job_id, *args, **kwargs):
        captured["func"] = func
        captured["job_id"] = job_id
        captured["timeout"] = kwargs.get("timeout")
    monkeypatch.setattr(svc, "async_task", fake_async_task)
    # 直接测 _enqueue 需要 job 已存在；或 spy create 路径
    svc._enqueue_mq_query_job_with_timeout("abc", timeout_sec=120)  # 若抽出辅助函数
    assert captured["timeout"] == 180  # 120 + 60 buffer
```

推荐抽出：

```python
def _enqueue_mq_query_job(job_id: str, timeout_sec: int | None = None) -> None:
    ...
    wait = int(timeout_sec or DEFAULT_TIMEOUT_SEC)
    async_task(
        "sql.services.mq_query_job.run_mq_query_job",
        job_id,
        timeout=wait + 60,
    )
```

`create_mq_query_job` 调用 `_enqueue_mq_query_job(job_id, timeout_sec=timeout_sec)`。

- [ ] **Step 2: 跑测确认失败**

- [ ] **Step 3: 实现**（如上；sync 分支仍用 daemon thread，不传 django-q timeout）

- [ ] **Step 4: README 一句运维说明（可选）+ Commit**

```powershell
git commit -m "fix(mq): pass per-task django-q timeout for mq jobs"
```

---

### Task 12: 汇总回归

**Files:** 无新文件（除非发现漏测）

- [ ] **Step 1: MQ 套件**

```powershell
wsl -e bash -lc 'cd /mnt/e/github/Archery; source .venv-mq/bin/activate; pytest -q sql/engines/test_mq_cli.py sql/engines/test_mqtt.py sql/engines/test_rabbitmq.py sql/services/test_mq_query_job.py sql_api/test_mq_query_job_api.py sql_api/test_instance_serializer_secrets.py'
```

Expected: PASS。

- [ ] **Step 2: black**

```powershell
wsl -e bash -lc 'cd /mnt/e/github/Archery; source .venv-mq/bin/activate; black --check .'
```

Expected: 干净。

- [ ] **Step 3: 确认 settings 未改 timeout 默认**

```powershell
git diff master -- archery/settings.py | Select-String timeout
```

Expected: 无 `Q_CLUISTER_TIMEOUT` / `"timeout":` 默认值变更（仅允许 mqtt/rabbitmq 引擎注册 diff）。

- [ ] **Step 4: 若有未提交文档微调则 commit；否则结束**

---

## Spec coverage (self-review)

| Spec 项 | Task |
|---------|------|
| 去 conftest shim / MySQLdb CI | 1 |
| black | 2 |
| query_priv_check + 当前库 | 3 |
| client_key/cert write_only | 4 |
| 离线导出拒绝 MQ | 5 |
| API 不回传 str(exc) | 6 |
| Explain 双保险 | 7 |
| 行首连接旗标 | 8 |
| durable= | 9 |
| 不可路由 publish | 10 |
| per-task timeout；不改全局 Q 默认 | 11 |
| 回归 / 验收 | 12 |

无 TBD/占位；`async_task` 的 `timeout` 关键字已对照 django-q2 源码确认。
