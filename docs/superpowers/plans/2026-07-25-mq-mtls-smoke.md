# MQ mTLS Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在本地测试环境上完成 MySQL / MQTT / RabbitMQ 的明文基线与 mTLS+账密冒烟，验证 SQL 查询与 SQL 上线路径。

**Architecture:** 只改本地测试配置与 `scripts/mq_env/` 辅助脚本，不改业务引擎代码（除非冒烟暴露真实缺陷）。先跑明文基线，再把现有 `mqtt_local` / `rabbitmq_local` 切到 mTLS，最后用脚本（正例+负例）和浏览器 UI 双通道验收。

**Tech Stack:** Docker（EMQX 5.8.3、RabbitMQ 3.13）、OpenSSL、Django Instance（`is_ssl` / `verify_ssl` / PEM 字段）、`pika`、`paho-mqtt`、Cursor 浏览器。

## Global Constraints

- 范围：本地测试环境配置 + 冒烟验收；默认不改 `sql/engines/*`。
- 认证强度：MQTT 与 RabbitMQ 必须同时要求「受信客户端证书 + 用户名密码」。
- Instance 策略：直接改写现有 `mqtt_local` / `rabbitmq_local`；不新建并行 TLS 实例。
- 主机名校验：`verify_ssl=True`；服务端证书 SAN 必须包含 `127.0.0.1`（Instance.host）；禁止靠关闭校验绕过。
- 敏感材料：证书、私钥、密码只留在已 gitignore 的 `scripts/mq_env/` 与本地 DB；不提交到 Git。
- `scripts/mq_env/` 整个目录已被 `.gitignore`；该目录下文件的“Commit”步骤一律跳过，只提交本计划/设计文档类变更。
- Windows 宿主通过 WSL Docker 端口映射访问 `127.0.0.1`；命令在 WSL bash 执行，PowerShell 侧禁止使用 `&&`。
- 环境未就绪的用例标 `blocked`，并记录最短补齐步骤；不记成引擎缺陷。

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `scripts/mq_env/gen_certs.sh` | 生成本地 CA/server/client PEM，SAN 含 `127.0.0.1` 与 `localhost` |
| `scripts/mq_env/certs/` | 本地证书目录（已 ignore） |
| `scripts/mq_env/emqx-mtls.hocon` | EMQX 运行时加载的 mTLS + password auth 配置片段 |
| `scripts/mq_env/rabbitmq-mtls.conf` | RabbitMQ `listeners.ssl` / `ssl_options` 配置 |
| `scripts/mq_env/verify_auth.py` | 原生客户端连通性正例/负例 |
| `scripts/mq_env/restore_test_instances.py` | 明文 Instance 恢复 |
| `scripts/mq_env/switch_instances_mtls.py` | 把现有 MQ Instance 切到 mTLS（读 PEM 写入加密字段） |
| `scripts/mq_env/engine_smoke.py` | 直接调用 `MqttEngine` / `RabbitmqEngine` / MySQL 引擎做查询与审核冒烟 |
| `scripts/mq_env/SMOKE_REPORT.md` | 冒烟结果汇总（本地，不提交） |
| `docs/superpowers/specs/2026-07-25-mq-mtls-smoke-design.md` | 已批准设计（只读参考） |

---

### Task 1: 重生带 SAN 的本地证书

**Files:**
- Modify: `scripts/mq_env/gen_certs.sh`
- Create: `scripts/mq_env/certs/*`（本地产物）

**Interfaces:**
- Consumes: OpenSSL
- Produces: `ca.crt`、`server.crt`/`server.key`、`client.crt`/`client.key`；server SAN 含 `DNS:localhost` 与 `IP:127.0.0.1`

- [ ] **Step 1: 更新 `gen_certs.sh`，写入 SAN**

将 `scripts/mq_env/gen_certs.sh` 替换为：

```bash
#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-scripts/mq_env/certs}"
mkdir -p "$OUT"

openssl req -x509 -newkey rsa:2048 -days 3650 -nodes \
  -keyout "$OUT/ca.key" -out "$OUT/ca.crt" \
  -subj "/CN=ArcheryMQTestCA"

# server CSR + SAN for hostname verification against Instance.host=127.0.0.1
openssl req -newkey rsa:2048 -nodes \
  -keyout "$OUT/server.key" -out "$OUT/server.csr" \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

openssl x509 -req -in "$OUT/server.csr" \
  -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" -CAcreateserial \
  -out "$OUT/server.crt" -days 3650 \
  -copy_extensions copy

openssl req -newkey rsa:2048 -nodes \
  -keyout "$OUT/client.key" -out "$OUT/client.csr" \
  -subj "/CN=archery-client"

openssl x509 -req -in "$OUT/client.csr" \
  -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" -CAcreateserial \
  -out "$OUT/client.crt" -days 3650

echo "certs written to $OUT"
openssl x509 -in "$OUT/server.crt" -noout -subject -ext subjectAltName
```

- [ ] **Step 2: 生成证书并核验 SAN**

Run:

```bash
wsl -e bash -lc 'cd /mnt/e/github/Archery; bash scripts/mq_env/gen_certs.sh'
```

Expected: 输出含 `DNS:localhost` 与 `IP Address:127.0.0.1`。

- [ ] **Step 3: Commit**

跳过（`scripts/mq_env/` 已 ignore）。若要把 `gen_certs.sh` 纳入仓库，需先把它移出 ignore 范围；本计划不改 `.gitignore`。

---

### Task 2: 明文基线（脚本）

**Files:**
- Test: `scripts/mq_env/verify_auth.py`
- Create: `scripts/mq_env/engine_smoke.py`
- Test against: 现有 `mqtt_local` / `rabbitmq_local` / `local-mysql`

**Interfaces:**
- Consumes: 当前明文 Instance（1883 / 5672 / 3306）
- Produces: 明文基线通过/失败记录，写入后续 `SMOKE_REPORT.md`

- [ ] **Step 1: 确认明文端口与实例仍为明文**

Run:

```bash
wsl -e bash -lc '
for p in 1883 5672 3306 8000; do
  timeout 1 bash -c "echo >/dev/tcp/127.0.0.1/$p" 2>/dev/null && echo OPEN $p || echo CLOSED $p
done
cd /mnt/e/github/Archery
. .venv/bin/activate
PYTHONPATH=/mnt/e/github/Archery python - <<PY
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE","archery.settings")
django.setup()
from sql.models import Instance
for n in ("mqtt_local","rabbitmq_local","local-mysql"):
    i=Instance.objects.get(instance_name=n)
    print(n, i.port, i.is_ssl, bool(i.ca_cert), repr(i.user))
PY
'
```

Expected: 1883/5672/3306/8000 OPEN；MQTT `1883 is_ssl=False`；RabbitMQ `5672 is_ssl=False`；MySQL `3306`。

若 MQ 实例已是 TLS，先跑：

```bash
wsl -e bash -lc 'cd /mnt/e/github/Archery; . .venv/bin/activate; PYTHONPATH=/mnt/e/github/Archery python scripts/mq_env/restore_test_instances.py'
```

- [ ] **Step 2: 原生客户端验证明文连通性**

Run:

```bash
wsl -e bash -lc '
cd /mnt/e/github/Archery
export ARCHERY_TEST_RABBITMQ_USER=archery_test
export ARCHERY_TEST_RABBITMQ_PASSWORD="ArcheryTest1!"
export ARCHERY_TEST_RABBITMQ_VHOST=/
unset ARCHERY_TEST_MQTT_USER ARCHERY_TEST_MQTT_PASSWORD
.venv/bin/python scripts/mq_env/verify_auth.py
'
```

Expected:

```text
OK rabbitmq 127.0.0.1:5672 vhost=/ tls=False
OK mqtt 127.0.0.1:1883 tls=False
```

- [ ] **Step 3: 写 `engine_smoke.py`（明文引擎冒烟）**

创建 `scripts/mq_env/engine_smoke.py`：

```python
#!/usr/bin/env python
"""Local engine smoke for MySQL / MQTT / RabbitMQ. Gitignored helper."""
import argparse
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "archery.settings")
os.environ.setdefault(
    "SECRET_KEY", "local-mq-test-secret-key-change-me-please-32chars+"
)

import django

django.setup()

from sql.engines import get_engine
from sql.models import Instance, SqlWorkflow, SqlWorkflowContent


def _get(name: str) -> Instance:
    return Instance.objects.get(instance_name=name)


def smoke_mysql():
    eng = get_engine(instance=_get("local-mysql"))
    conn = eng.test_connection()
    if conn.error:
        raise RuntimeError(f"mysql connect: {conn.error}")
    q = eng.query(db_name="demo", sql="select 1 as ok", limit_num=10)
    if q.error:
        raise RuntimeError(f"mysql query: {q.error}")
    print("OK mysql query", q.rows)


def smoke_mqtt_query():
    eng = get_engine(instance=_get("mqtt_local"))
    conn = eng.test_connection()
    if conn.error:
        raise RuntimeError(f"mqtt connect: {conn.error}")
    q = eng.query(sql="help", limit_num=100)
    if q.error:
        raise RuntimeError(f"mqtt help: {q.error}")
    print("OK mqtt help rows=", q.affected_rows)


def smoke_mqtt_check():
    eng = get_engine(instance=_get("mqtt_local"))
    r = eng.execute_check(sql='pub topic=archery/smoke payload="hi" qos=0')
    if r.error_count:
        raise RuntimeError(f"mqtt execute_check failed: {[x.errormessage for x in r.rows]}")
    print("OK mqtt execute_check")


def smoke_rabbit_query():
    eng = get_engine(instance=_get("rabbitmq_local"))
    conn = eng.test_connection()
    if conn.error:
        raise RuntimeError(f"rabbitmq connect: {conn.error}")
    q = eng.query(sql="help", limit_num=100)
    if q.error:
        raise RuntimeError(f"rabbitmq help: {q.error}")
    print("OK rabbitmq help rows=", q.affected_rows)


def smoke_rabbit_check():
    eng = get_engine(instance=_get("rabbitmq_local"))
    r = eng.execute_check(sql="declare queue name=archery.smoke.q durable=false")
    if r.error_count:
        raise RuntimeError(
            f"rabbitmq execute_check failed: {[x.errormessage for x in r.rows]}"
        )
    print("OK rabbitmq execute_check")


def smoke_execute_mqtt():
    """Optional: actually publish via engine (not full workflow UI)."""
    eng = get_engine(instance=_get("mqtt_local"))
    # Minimal stand-in: connect + pub through engine helpers
    client = eng.get_connection()
    eng._connect_and_wait(client)
    try:
        from sql.engines.mq_cli import parse_mqtt_line

        cmd = parse_mqtt_line('pub topic=archery/smoke payload="engine-smoke" qos=0')
        eng._execute_pub(client, cmd)
        print("OK mqtt publish")
    finally:
        client.loop_stop()
        client.disconnect()


def smoke_execute_rabbit():
    eng = get_engine(instance=_get("rabbitmq_local"))
    from sql.engines.mq_cli import parse_rabbitmq_line

    conn = eng.get_connection()
    try:
        ch = conn.channel()
        cmd = parse_rabbitmq_line("declare queue name=archery.smoke.q durable=false")
        eng._execute_write_command(ch, cmd)
        print("OK rabbitmq declare queue")
    finally:
        if conn.is_open:
            conn.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--suite",
        choices=["plain", "tls", "all"],
        default="all",
        help="plain/tls labels are informational; uses current Instance config",
    )
    args = p.parse_args()
    del args  # suite reserved for report labeling by caller
    smoke_mysql()
    smoke_mqtt_query()
    smoke_mqtt_check()
    smoke_execute_mqtt()
    smoke_rabbit_query()
    smoke_rabbit_check()
    smoke_execute_rabbit()
    print("ENGINE_SMOKE_OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ENGINE_SMOKE_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
```

- [ ] **Step 4: 跑引擎明文冒烟**

Run:

```bash
wsl -e bash -lc 'cd /mnt/e/github/Archery; . .venv/bin/activate; PYTHONPATH=/mnt/e/github/Archery python scripts/mq_env/engine_smoke.py --suite plain'
```

Expected: 逐行 `OK ...`，最后 `ENGINE_SMOKE_OK`。

- [ ] **Step 5: Commit**

跳过（本地 helper）。

---

### Task 3: 明文基线（UI）

**Files:**
- None（浏览器操作 + 本地报告）

**Interfaces:**
- Consumes: Archery `http://127.0.0.1:8000`，账号 `admin` / `admin123`（由 `restore_test_instances.py` 设定）
- Produces: UI 明文抽检结果写入 `scripts/mq_env/SMOKE_REPORT.md`

- [ ] **Step 1: 确认 runserver 与（如需）qcluster**

Run:

```bash
wsl -e bash -lc 'ps -eo pid,cmd | grep -E "runserver|qcluster" | grep -v grep'
```

若没有 `runserver`：

```bash
wsl -e bash -lc 'cd /mnt/e/github/Archery; . .venv/bin/activate; nohup python manage.py runserver 0.0.0.0:8000 > /tmp/archery-runserver.log 2>&1 &'
```

若 SQL 上线执行依赖 Django-Q 且无 `qcluster`，另开：

```bash
wsl -e bash -lc 'cd /mnt/e/github/Archery; . .venv/bin/activate; nohup python manage.py qcluster > /tmp/archery-qcluster.log 2>&1 &'
```

- [ ] **Step 2: UI SQL 查询抽检**

用 Cursor 浏览器登录后执行：

| 实例 | 命令 | 期望 |
| --- | --- | --- |
| `local-mysql` / db `demo` | `select 1` | 返回一行 |
| `mqtt_local` | `help` | 命令帮助表 |
| `rabbitmq_local` | `help` | 命令帮助表 |

截图保存到 `scripts/mq_env/screenshots/plain-query-*.png`（本地）。

- [ ] **Step 3: UI SQL 上线抽检**

| 实例 | 工单 SQL | 期望 |
| --- | --- | --- |
| `local-mysql` | 幂等测试 SQL，例如 `create table if not exists archery_smoke_t(id int)` | 审核通过并可执行（或按现有 inception 规则给出可解释结果） |
| `mqtt_local` | `pub topic=archery/smoke/ui payload="plain-ui" qos=0` | 审核通过并执行成功 |
| `rabbitmq_local` | `declare queue name=archery.smoke.ui durable=false` | 审核通过并执行成功 |

- [ ] **Step 4: 写入明文基线报告片段**

创建/追加 `scripts/mq_env/SMOKE_REPORT.md`：

```markdown
# MQ mTLS Smoke Report

## Phase A — Plain baseline
- verify_auth: PASS/FAIL
- engine_smoke: PASS/FAIL
- UI query MySQL/MQTT/RabbitMQ: PASS/FAIL
- UI workflow MySQL/MQTT/RabbitMQ: PASS/FAIL
- notes:
```

- [ ] **Step 5: Commit**

跳过。

---

### Task 4: 配置 EMQX mTLS + 测试用户

**Files:**
- Create: `scripts/mq_env/emqx-mtls.hocon`
- Modify: 运行中 `emqx` 容器配置（通过 `emqx ctl conf load`）

**Interfaces:**
- Consumes: `scripts/mq_env/certs/{ca,server,client}.{crt,key}`
- Produces: `8883` 强制客户端证书；password auth 用户 `archery_mqtt` / `ArcheryTest1!`；匿名关闭

- [ ] **Step 1: 把证书拷进容器并写 HOCON 片段**

创建 `scripts/mq_env/emqx-mtls.hocon`：

```hocon
listeners.ssl.default {
  bind = "0.0.0.0:8883"
  ssl_options {
    cacertfile = "/opt/emqx/etc/certs/archery/ca.crt"
    certfile = "/opt/emqx/etc/certs/archery/server.crt"
    keyfile = "/opt/emqx/etc/certs/archery/server.key"
    verify = verify_peer
    fail_if_no_peer_cert = true
  }
}

authentication = [
  {
    mechanism = password_based
    backend = built_in_database
    enable = true
  }
]
```

Run:

```bash
wsl -e bash -lc '
cd /mnt/e/github/Archery
docker exec emqx mkdir -p /opt/emqx/etc/certs/archery
docker cp scripts/mq_env/certs/ca.crt emqx:/opt/emqx/etc/certs/archery/ca.crt
docker cp scripts/mq_env/certs/server.crt emqx:/opt/emqx/etc/certs/archery/server.crt
docker cp scripts/mq_env/certs/server.key emqx:/opt/emqx/etc/certs/archery/server.key
docker cp scripts/mq_env/emqx-mtls.hocon emqx:/tmp/emqx-mtls.hocon
docker exec emqx emqx ctl conf load --merge /tmp/emqx-mtls.hocon
'
```

Expected: conf load 成功，无报错。

- [ ] **Step 2: 创建 MQTT 测试用户并核验监听器**

Run:

```bash
wsl -e bash -lc '
# EMQX 5 built-in DB via HTTP API (default dashboard admin may need bootstrap).
# Prefer CLI user creation if available; otherwise use Dashboard API after login.
docker exec emqx emqx ctl listeners
# Create user through conf bootstrap CSV + reload if API auth blocks:
docker exec emqx sh -c "printf \"user_id,password,is_superuser\narchery_mqtt,ArcheryTest1!,false\n\" > /opt/emqx/etc/auth-built-in-db-bootstrap.csv"
docker exec emqx emqx ctl conf reload --merge
'
```

若 `authentication` 已生效但用户未导入，改用 Dashboard API（默认首次需改密时，以本机实际仪表盘状态为准）：

```bash
wsl -e bash -lc '
# After dashboard is reachable at :18083 with a known admin password:
curl -s -u "admin:PUBLIC_DASHBOARD_PASSWORD" \
  -H "Content-Type: application/json" \
  -X POST "http://127.0.0.1:18083/api/v5/authentication/password_based:built_in_database/users" \
  -d "{\"user_id\":\"archery_mqtt\",\"password\":\"ArcheryTest1!\"}"
'
```

Expected: `ssl:default` running；用户创建成功（或已存在）。

- [ ] **Step 3: 负例/正例探测 8883（原生客户端）**

Run:

```bash
wsl -e bash -lc '
cd /mnt/e/github/Archery
CA=scripts/mq_env/certs/ca.crt
CERT=scripts/mq_env/certs/client.crt
KEY=scripts/mq_env/certs/client.key

# negative: no client cert -> must fail
.venv/bin/python - <<PY
import ssl, paho.mqtt.client as mqtt
c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
c.tls_set(ca_certs="scripts/mq_env/certs/ca.crt")
c.username_pw_set("archery_mqtt","ArcheryTest1!")
try:
    c.connect("127.0.0.1",8883,30); c.disconnect(); raise SystemExit("UNEXPECTED SUCCESS")
except Exception as e:
    print("OK neg no-cert:", type(e).__name__, e)
PY

# positive: cert + password
export ARCHERY_TEST_RABBITMQ_USER=archery_test
export ARCHERY_TEST_RABBITMQ_PASSWORD="ArcheryTest1!"
# verify_auth currently requires rabbit too; call mqtt function directly:
.venv/bin/python - <<PY
from scripts.mq_env.verify_auth import verify_mqtt
verify_mqtt("127.0.0.1",8883,"archery_mqtt","ArcheryTest1!",tls=True,
            ca="scripts/mq_env/certs/ca.crt",
            cert="scripts/mq_env/certs/client.crt",
            key="scripts/mq_env/certs/client.key")
PY
'
```

Expected: 无证失败；有证+密码打印 `OK mqtt 127.0.0.1:8883 tls=True`。

> 若 `from scripts.mq_env.verify_auth` 因包路径失败，改为 `PYTHONPATH=/mnt/e/github/Archery` 后 `import importlib.util` 加载文件，或临时把函数调用写成同目录绝对路径加载。

- [ ] **Step 4: Commit**

跳过。

---

### Task 5: 配置 RabbitMQ AMQPS 并映射 5671

**Files:**
- Create: `scripts/mq_env/rabbitmq-mtls.conf`
- Recreate: 容器 `rabbitmq_3_13`（保留数据卷，新增 `-p 5671:5671` 与证书挂载）

**Interfaces:**
- Consumes: 同一套 `scripts/mq_env/certs/`
- Produces: 宿主机 `5671` OPEN；AMQPS 强制客户端证书；`archery_test` 用户仍可用

- [ ] **Step 1: 写 RabbitMQ SSL 配置**

创建 `scripts/mq_env/rabbitmq-mtls.conf`：

```ini
listeners.ssl.default = 5671

ssl_options.cacertfile = /etc/rabbitmq/certs/ca.crt
ssl_options.certfile   = /etc/rabbitmq/certs/server.crt
ssl_options.keyfile    = /etc/rabbitmq/certs/server.key
ssl_options.verify     = verify_peer
ssl_options.fail_if_no_peer_cert = true
```

- [ ] **Step 2: 记录现有容器卷名并重建（保留数据）**

Run:

```bash
wsl -e bash -lc '
VOL=$(docker inspect -f "{{range .Mounts}}{{if eq .Destination \"/var/lib/rabbitmq\"}}{{.Name}}{{end}}{{end}}" rabbitmq_3_13)
echo "DATA_VOL=$VOL"
docker stop rabbitmq_3_13
docker rm rabbitmq_3_13
docker run -d --name rabbitmq_3_13 \
  -p 5672:5672 -p 5671:5671 -p 15672:15672 \
  -v "$VOL:/var/lib/rabbitmq" \
  -v /mnt/e/github/Archery/scripts/mq_env/certs:/etc/rabbitmq/certs:ro \
  -v /mnt/e/github/Archery/scripts/mq_env/rabbitmq-mtls.conf:/etc/rabbitmq/conf.d/20-mtls.conf:ro \
  rabbitmq:3.13-management
sleep 8
docker exec rabbitmq_3_13 rabbitmq-diagnostics listeners
timeout 1 bash -c "echo >/dev/tcp/127.0.0.1/5671" && echo OPEN 5671 || echo CLOSED 5671
docker exec rabbitmq_3_13 rabbitmqctl list_users
'
```

Expected: listeners 含 `port: 5671, protocol: amqp/ssl`；`OPEN 5671`；用户含 `archery_test`。

若用户丢失，重建：

```bash
wsl -e bash -lc '
docker exec rabbitmq_3_13 rabbitmqctl add_user archery_test "ArcheryTest1!" || true
docker exec rabbitmq_3_13 rabbitmqctl set_permissions -p / archery_test ".*" ".*" ".*"
docker exec rabbitmq_3_13 rabbitmqctl set_user_tags archery_test administrator
'
```

- [ ] **Step 3: 正例/负例探测 AMQPS**

Run:

```bash
wsl -e bash -lc '
cd /mnt/e/github/Archery
.venv/bin/python - <<PY
from scripts.mq_env.verify_auth import verify_rabbitmq
# or load via importlib if needed
import importlib.util
spec = importlib.util.spec_from_file_location("verify_auth", "scripts/mq_env/verify_auth.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

# negative: tls without client cert
try:
    m.verify_rabbitmq("127.0.0.1",5671,"archery_test","ArcheryTest1!","/",
                      tls=True, ca="scripts/mq_env/certs/ca.crt")
    raise SystemExit("UNEXPECTED SUCCESS without client cert")
except Exception as e:
    print("OK neg no-cert:", type(e).__name__)

# positive
m.verify_rabbitmq("127.0.0.1",5671,"archery_test","ArcheryTest1!","/",
                  tls=True,
                  ca="scripts/mq_env/certs/ca.crt",
                  cert="scripts/mq_env/certs/client.crt",
                  key="scripts/mq_env/certs/client.key")
PY
'
```

Expected: 无证失败；有证打印 `OK rabbitmq 127.0.0.1:5671 ... tls=True`。

- [ ] **Step 4: Commit**

跳过。

---

### Task 6: 切换现有 Instance 到 mTLS

**Files:**
- Create: `scripts/mq_env/switch_instances_mtls.py`
- Modify: Django DB 中 `mqtt_local` / `rabbitmq_local`

**Interfaces:**
- Consumes: PEM 文件；MQTT 用户 `archery_mqtt` / `ArcheryTest1!`；RabbitMQ 用户 `archery_test` / `ArcheryTest1!`
- Produces: `mqtt_local` → `8883` + SSL 字段；`rabbitmq_local` → `5671` + SSL 字段；`local-mysql` 不变

- [ ] **Step 1: 写切换脚本**

创建 `scripts/mq_env/switch_instances_mtls.py`：

```python
#!/usr/bin/env python
"""Switch mqtt_local / rabbitmq_local to mTLS. Gitignored helper."""
import argparse
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "archery.settings")
os.environ.setdefault(
    "SECRET_KEY", "local-mq-test-secret-key-change-me-please-32chars+"
)

import django

django.setup()

from sql.models import Instance

CERT_DIR = Path(__file__).resolve().parent / "certs"


def _read(name: str) -> str:
    return (CERT_DIR / name).read_text(encoding="utf-8")


def switch_mtls():
    ca, cert, key = _read("ca.crt"), _read("client.crt"), _read("client.key")
    mqtt, _ = Instance.objects.update_or_create(
        instance_name="mqtt_local",
        defaults={
            "type": "master",
            "db_type": "mqtt",
            "host": "127.0.0.1",
            "port": 8883,
            "user": "archery_mqtt",
            "password": "ArcheryTest1!",
            "db_name": "default",
            "is_ssl": True,
            "verify_ssl": True,
            "ca_cert": ca,
            "client_cert": cert,
            "client_key": key,
        },
    )
    rabbit, _ = Instance.objects.update_or_create(
        instance_name="rabbitmq_local",
        defaults={
            "type": "master",
            "db_type": "rabbitmq",
            "host": "127.0.0.1",
            "port": 5671,
            "user": "archery_test",
            "password": "ArcheryTest1!",
            "db_name": "/",
            "is_ssl": True,
            "verify_ssl": True,
            "ca_cert": ca,
            "client_cert": cert,
            "client_key": key,
        },
    )
    print("switched", mqtt.instance_name, mqtt.port, mqtt.is_ssl)
    print("switched", rabbit.instance_name, rabbit.port, rabbit.is_ssl)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["mtls", "plain"], default="mtls")
    args = p.parse_args()
    if args.mode == "plain":
        # Reuse existing restore helper for plain defaults.
        from restore_test_instances import main as restore_main

        restore_main()
        return
    switch_mtls()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 执行切换并核对字段**

Run:

```bash
wsl -e bash -lc '
cd /mnt/e/github/Archery
. .venv/bin/activate
PYTHONPATH=/mnt/e/github/Archery python scripts/mq_env/switch_instances_mtls.py --mode mtls
PYTHONPATH=/mnt/e/github/Archery python - <<PY
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE","archery.settings")
django.setup()
from sql.models import Instance
for n in ("mqtt_local","rabbitmq_local","local-mysql"):
    i=Instance.objects.get(instance_name=n)
    print(n, i.port, i.is_ssl, i.verify_ssl, bool(i.ca_cert), bool(i.client_cert), bool(i.client_key), repr(i.user))
PY
'
```

Expected: MQTT `8883 True True True True True 'archery_mqtt'`；RabbitMQ `5671 ... 'archery_test'`；MySQL 仍明文。

- [ ] **Step 3: Commit**

跳过。

---

### Task 7: mTLS 脚本正例 / 负例 / 引擎冒烟

**Files:**
- Test: `scripts/mq_env/verify_auth.py`、`scripts/mq_env/engine_smoke.py`

**Interfaces:**
- Consumes: 已切换的 Instance 与 broker mTLS
- Produces: 正例 PASS、三类负例 FAIL（按预期）、`ENGINE_SMOKE_OK`

- [ ] **Step 1: 原生客户端完整正例**

Run:

```bash
wsl -e bash -lc '
cd /mnt/e/github/Archery
.venv/bin/python scripts/mq_env/verify_auth.py \
  --tls \
  --amqp-port 5671 \
  --mqtt-port 8883 \
  --amqp-user archery_test --amqp-password "ArcheryTest1!" \
  --mqtt-user archery_mqtt --mqtt-password "ArcheryTest1!" \
  --ca scripts/mq_env/certs/ca.crt \
  --cert scripts/mq_env/certs/client.crt \
  --key scripts/mq_env/certs/client.key
'
```

Expected:

```text
OK rabbitmq 127.0.0.1:5671 vhost=/ tls=True
OK mqtt 127.0.0.1:8883 tls=True
```

- [ ] **Step 2: 负例矩阵（必须失败）**

Run:

```bash
wsl -e bash -lc '
cd /mnt/e/github/Archery
.venv/bin/python - <<PY
import importlib.util
spec = importlib.util.spec_from_file_location("v", "scripts/mq_env/verify_auth.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
CA, CERT, KEY = "scripts/mq_env/certs/ca.crt", "scripts/mq_env/certs/client.crt", "scripts/mq_env/certs/client.key"

def expect_fail(label, fn):
    try:
        fn(); print("FAIL unexpected success:", label); raise SystemExit(1)
    except Exception as e:
        print("OK expected fail:", label, type(e).__name__)

# MQTT
expect_fail("mqtt no-cert", lambda: m.verify_mqtt("127.0.0.1",8883,"archery_mqtt","ArcheryTest1!",True,CA,None,None))
expect_fail("mqtt no-user", lambda: m.verify_mqtt("127.0.0.1",8883,"","",True,CA,CERT,KEY))
expect_fail("mqtt bad-pass", lambda: m.verify_mqtt("127.0.0.1",8883,"archery_mqtt","wrong",True,CA,CERT,KEY))
# RabbitMQ
expect_fail("amqp no-cert", lambda: m.verify_rabbitmq("127.0.0.1",5671,"archery_test","ArcheryTest1!","/",True,CA,None,None))
expect_fail("amqp no-user", lambda: m.verify_rabbitmq("127.0.0.1",5671,"","","/",True,CA,CERT,KEY))
expect_fail("amqp bad-pass", lambda: m.verify_rabbitmq("127.0.0.1",5671,"archery_test","wrong","/",True,CA,CERT,KEY))
print("NEG_MATRIX_OK")
PY
'
```

Expected: 六个 `OK expected fail` + `NEG_MATRIX_OK`。

- [ ] **Step 3: 引擎路径冒烟（读 Instance PEM）**

Run:

```bash
wsl -e bash -lc 'cd /mnt/e/github/Archery; . .venv/bin/activate; PYTHONPATH=/mnt/e/github/Archery python scripts/mq_env/engine_smoke.py --suite tls'
```

Expected: `ENGINE_SMOKE_OK`。若失败且原生客户端已 PASS → 记为候选引擎缺陷（保留 traceback）。

- [ ] **Step 4: Commit**

跳过。

---

### Task 8: mTLS UI 抽检 + 汇总报告

**Files:**
- Create/Update: `scripts/mq_env/SMOKE_REPORT.md`
- Screenshots: `scripts/mq_env/screenshots/tls-*.png`（本地）

**Interfaces:**
- Consumes: 已切 TLS 的 Instance；Task 7 脚本结论
- Produces: 最终 PASS / FAIL / blocked 汇总

- [ ] **Step 1: UI SQL 查询（TLS）**

| 实例 | 命令 | 期望 |
| --- | --- | --- |
| `mqtt_local`（8883） | `help` | 成功 |
| `rabbitmq_local`（5671） | `help` | 成功 |
| `local-mysql` | `select 1` | 成功（对照组） |

- [ ] **Step 2: UI SQL 上线（TLS）**

| 实例 | 工单 SQL | 期望 |
| --- | --- | --- |
| `mqtt_local` | `pub topic=archery/smoke/ui payload="tls-ui" qos=0` | 审核+执行成功 |
| `rabbitmq_local` | `declare queue name=archery.smoke.ui.tls durable=false` | 审核+执行成功 |

- [ ] **Step 3: 完成 `SMOKE_REPORT.md`**

追加：

```markdown
## Phase D — mTLS
- broker EMQX verify_peer: PASS/FAIL/blocked
- broker RabbitMQ 5671: PASS/FAIL/blocked
- verify_auth positive: PASS/FAIL
- negative matrix: PASS/FAIL
- engine_smoke: PASS/FAIL
- UI query: PASS/FAIL
- UI workflow: PASS/FAIL
- MySQL still OK: PASS/FAIL
- defects / blocked notes:
```

归因规则遵循设计文档：环境问题 → blocked；原生 OK / 引擎 FAIL → 引擎缺陷；引擎 OK / UI FAIL → 端到端缺陷。

- [ ] **Step 4: 可选回切明文（便于后续日常开发）**

```bash
wsl -e bash -lc 'cd /mnt/e/github/Archery; . .venv/bin/activate; PYTHONPATH=/mnt/e/github/Archery python scripts/mq_env/restore_test_instances.py'
```

Broker mTLS 配置可保留；仅把 Instance 端口/字段改回明文即可继续用 1883/5672。

- [ ] **Step 5: Commit**

若仅有文档更新需要入库，提交冒烟结论的非敏感摘要到设计旁注或新 issue；**不要**提交 `SMOKE_REPORT.md` 中含密码/证书的内容。本任务默认不提交本地报告。

---

## Self-Review

1. **Spec coverage:** 明文基线、broker mTLS、Instance 切换、脚本正/负例、引擎路径、UI 查询/上线、归因与通过标准均有对应 Task；MySQL TLS 明确排除。
2. **Placeholder scan:** 无 TBD/TODO；EMQX 用户创建保留了 CLI/API 两条可执行路径以应对仪表盘初始状态差异。
3. **Type consistency:** Instance 字段名与模型一致（`is_ssl` / `verify_ssl` / `ca_cert` / `client_cert` / `client_key`）；端口 8883/5671 与设计一致；SAN 要求已落到 Task 1。
