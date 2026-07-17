# MQTT / RabbitMQ Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Archery 新增 `mqtt` / `rabbitmq` 实例引擎（类 Redis 命令台），支持用户名密码与可选客户端证书，并先在 WSL 的 EMQX + RabbitMQ 上完成环境与认证验证。

**Architecture:** 两个独立 Engine（`MqttEngine`、`RabbitmqEngine`）继承 `EngineBase`，经 `AVAILABLE_ENGINES` / `ENABLED_ENGINES` 注册；查询页白名单短拉取，上线工单白名单写命令；证书 PEM 存 `Instance` 加密字段；不做 Management API、不做长连接 consume。

**Tech Stack:** Django、pika、paho-mqtt、pytest、WSL Docker（`emqx/emqx:5.1.0`、`rabbitmq:3.13.3-management`）

**Spec:** `docs/superpowers/specs/2026-07-17-mqtt-rabbitmq-engine-design.md`

## Global Constraints

- v1 不做 RabbitMQ Management HTTP API
- v1 不做 `basic.consume` / 常驻 MQTT subscribe；收消息仅短请求拉取
- 认证：用户名密码（可选）+ TLS + 客户端证书（可选）；MQTT 与 RabbitMQ 相同能力
- `sql/migrations/` 被 gitignore；模型改完后本地/CI 用 `python manage.py makemigrations sql` 生成，不提交 migration 文件
- 私钥与测试证书 **不进 git**；放 `docs/superpowers/testdata/mq-certs/` 且该目录加入 `.gitignore`，或仅放生成脚本
- 命令风格对齐 Redis：`shlex` 分词、按行拆分、`query_check` / `execute_check` 白名单
- Windows 开发机通过 WSL Docker 端口映射访问 `127.0.0.1:5672` / `1883`（及 TLS 端口）

## File Structure

| 路径 | 职责 |
|------|------|
| `scripts/mq_env/README.md` | WSL 环境启动、账号、证书验证步骤 |
| `scripts/mq_env/gen_certs.sh` | 生成测试 CA / 服务端 / 客户端证书 |
| `scripts/mq_env/verify_auth.py` | 验证用户名密码 + mTLS 连通（RabbitMQ + EMQX） |
| `sql/models.py` | `DB_TYPE_CHOICES` + `client_cert` / `client_key` / `ca_cert` |
| `archery/settings.py` | 注册 engines |
| `requirements.txt` | `pika`、`paho-mqtt` |
| `sql/engines/rabbitmq.py` | `RabbitmqEngine` |
| `sql/engines/mqtt.py` | `MqttEngine` |
| `sql/engines/test_rabbitmq.py` | mock 单测 |
| `sql/engines/test_mqtt.py` | mock 单测 |
| `sql/engines/test_mq_integration.py` | 可选集成冒烟（不可达 skip） |
| `sql/offlinedownload.py` | `LINE_BASED_COMMAND_ENGINES` |
| `sql/admin.py` | 证书字段控件 |
| `.gitignore` | 忽略 `docs/superpowers/testdata/mq-certs/` |

---

### Task 1: WSL 环境准备与认证验证（阻塞后续实现）

**Files:**
- Create: `scripts/mq_env/README.md`
- Create: `scripts/mq_env/gen_certs.sh`
- Create: `scripts/mq_env/verify_auth.py`
- Modify: `.gitignore`（追加 `docs/superpowers/testdata/mq-certs/`）

**Interfaces:**
- Consumes: 已有 Docker 容器 `rabbitmq_3_13`、`emqx`（或同名镜像）
- Produces: 文档化的连接参数；`verify_auth.py` 退出码 0 表示用户名密码路径通过；带 `--tls` 且证书齐全时 mTLS 通过

- [ ] **Step 1: 确认 Docker 与容器**

在 WSL 中执行：

```bash
sudo systemctl start docker
docker start rabbitmq_3_13 emqx 2>/dev/null || true
docker ps --filter name=rabbitmq_3_13 --filter name=emqx --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

Expected: 两容器 `Up`，端口含 `5672`、`1883`。

- [ ] **Step 2: 写入 `.gitignore` 与 README**

`.gitignore` 追加：

```
docs/superpowers/testdata/mq-certs/
```

`scripts/mq_env/README.md` 内容要点：

1. 启动容器命令
2. RabbitMQ 用户：用 `docker exec rabbitmq_3_13 rabbitmqctl list_users` 查看；若需专用测试用户：

```bash
docker exec rabbitmq_3_13 rabbitmqctl add_user archery_test 'ArcheryTest1!'
docker exec rabbitmq_3_13 rabbitmqctl set_permissions -p / archery_test '.*' '.*' '.*'
docker exec rabbitmq_3_13 rabbitmqctl set_user_tags archery_test administrator
```

3. EMQX：默认允许匿名或创建用户；记录 `MQTT_USER` / `MQTT_PASS`
4. 证书：运行 `gen_certs.sh`，再按 README 配置 RabbitMQ/EMQX TLS 监听
5. 运行 `python3 scripts/mq_env/verify_auth.py` 验收

- [ ] **Step 3: 实现 `gen_certs.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-docs/superpowers/testdata/mq-certs}"
mkdir -p "$OUT"
openssl req -x509 -newkey rsa:2048 -days 3650 -nodes \
  -keyout "$OUT/ca.key" -out "$OUT/ca.crt" \
  -subj "/CN=ArcheryMQTestCA"
openssl req -newkey rsa:2048 -nodes -keyout "$OUT/server.key" -out "$OUT/server.csr" \
  -subj "/CN=localhost"
openssl x509 -req -in "$OUT/server.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" -CAcreateserial \
  -out "$OUT/server.crt" -days 3650
openssl req -newkey rsa:2048 -nodes -keyout "$OUT/client.key" -out "$OUT/client.csr" \
  -subj "/CN=archery-client"
openssl x509 -req -in "$OUT/client.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" -CAcreateserial \
  -out "$OUT/client.crt" -days 3650
echo "certs written to $OUT"
```

- [ ] **Step 4: 实现 `verify_auth.py`（用户名密码路径必过）**

依赖：先在 WSL `pip3 install pika paho-mqtt`。

```python
#!/usr/bin/env python3
"""Verify RabbitMQ (AMQP) and EMQX (MQTT) auth. Exit 0 on success."""
import argparse
import os
import ssl
import sys
import time
import uuid

import paho.mqtt.client as mqtt
import pika


def verify_rabbitmq(host, port, user, password, vhost, tls=False, ca=None, cert=None, key=None):
    creds = pika.PlainCredentials(user, password) if user else None
    params = pika.ConnectionParameters(
        host=host,
        port=port,
        virtual_host=vhost,
        credentials=creds,
        socket_timeout=10,
        blocked_connection_timeout=10,
    )
    if tls:
        context = ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()
        if cert and key:
            context.load_cert_chain(certfile=cert, keyfile=key)
        params.ssl_options = pika.SSLOptions(context, server_hostname=host)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    q = f"archery.verify.{uuid.uuid4().hex[:8]}"
    ch.queue_declare(queue=q, durable=False, auto_delete=True)
    body = b"archery-ping"
    ch.basic_publish(exchange="", routing_key=q, body=body)
    method, _props, got = ch.basic_get(queue=q, auto_ack=True)
    conn.close()
    if got != body:
        raise RuntimeError(f"rabbitmq roundtrip failed: {got!r}")
    print(f"OK rabbitmq {host}:{port} vhost={vhost} tls={tls}")


def verify_mqtt(host, port, user, password, tls=False, ca=None, cert=None, key=None):
    topic = f"archery/verify/{uuid.uuid4().hex[:8]}"
    payload = b"archery-ping"
    received = {}

    def on_message(client, userdata, msg):
        received["payload"] = msg.payload

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"archery-verify-{uuid.uuid4().hex[:6]}",
    )
    if user:
        client.username_pw_set(user, password or None)
    if tls:
        client.tls_set(ca_certs=ca, certfile=cert, keyfile=key)
    client.on_message = on_message
    client.connect(host, port, keepalive=30)
    client.subscribe(topic, qos=0)
    client.loop_start()
    time.sleep(0.5)
    client.publish(topic, payload, qos=0)
    for _ in range(20):
        if "payload" in received:
            break
        time.sleep(0.25)
    client.loop_stop()
    client.disconnect()
    if received.get("payload") != payload:
        raise RuntimeError(f"mqtt roundtrip failed: {received.get('payload')!r}")
    print(f"OK mqtt {host}:{port} tls={tls}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--amqp-host", default=os.getenv("ARCHERY_TEST_RABBITMQ_HOST", "127.0.0.1"))
    p.add_argument("--amqp-port", type=int, default=int(os.getenv("ARCHERY_TEST_RABBITMQ_PORT", "5672")))
    p.add_argument("--amqp-user", default=os.getenv("ARCHERY_TEST_RABBITMQ_USER", "root"))
    p.add_argument("--amqp-password", default=os.getenv("ARCHERY_TEST_RABBITMQ_PASSWORD", ""))
    p.add_argument("--vhost", default=os.getenv("ARCHERY_TEST_RABBITMQ_VHOST", "/"))
    p.add_argument("--mqtt-host", default=os.getenv("ARCHERY_TEST_MQTT_HOST", "127.0.0.1"))
    p.add_argument("--mqtt-port", type=int, default=int(os.getenv("ARCHERY_TEST_MQTT_PORT", "1883")))
    p.add_argument("--mqtt-user", default=os.getenv("ARCHERY_TEST_MQTT_USER", ""))
    p.add_argument("--mqtt-password", default=os.getenv("ARCHERY_TEST_MQTT_PASSWORD", ""))
    p.add_argument("--tls", action="store_true")
    p.add_argument("--ca", default=os.getenv("ARCHERY_TEST_MQ_CA", ""))
    p.add_argument("--cert", default=os.getenv("ARCHERY_TEST_MQ_CERT", ""))
    p.add_argument("--key", default=os.getenv("ARCHERY_TEST_MQ_KEY", ""))
    args = p.parse_args()
    if not args.amqp_password:
        print("Set ARCHERY_TEST_RABBITMQ_PASSWORD or --amqp-password", file=sys.stderr)
        return 2
    verify_rabbitmq(
        args.amqp_host,
        args.amqp_port,
        args.amqp_user,
        args.amqp_password,
        args.vhost,
        tls=args.tls,
        ca=args.ca or None,
        cert=args.cert or None,
        key=args.key or None,
    )
    verify_mqtt(
        args.mqtt_host,
        args.mqtt_port,
        args.mqtt_user,
        args.mqtt_password,
        tls=args.tls,
        ca=args.ca or None,
        cert=args.cert or None,
        key=args.key or None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 跑通用户名密码验证（必须通过才能进 Task 2）**

```bash
export ARCHERY_TEST_RABBITMQ_USER=root
export ARCHERY_TEST_RABBITMQ_PASSWORD='实际密码'
python3 scripts/mq_env/verify_auth.py
```

Expected: 打印 `OK rabbitmq ...` 与 `OK mqtt ...`，退出码 0。

- [ ] **Step 6: 证书路径验证（能力必验；监听未配齐可稍后，但脚本与证书生成要就绪）**

```bash
bash scripts/mq_env/gen_certs.sh
# 按 README 配置 5671 / 8883 后：
python3 scripts/mq_env/verify_auth.py --tls \
  --amqp-port 5671 --mqtt-port 8883 \
  --ca docs/superpowers/testdata/mq-certs/ca.crt \
  --cert docs/superpowers/testdata/mq-certs/client.crt \
  --key docs/superpowers/testdata/mq-certs/client.key
```

Expected: `OK ... tls=True`。明文用户名密码验证（Step 5）是硬门禁。

- [ ] **Step 7: Commit**

```bash
git add scripts/mq_env .gitignore
git commit -m "chore(mq): add WSL broker env verify scripts for MQTT/RabbitMQ"
```

---

### Task 2: 依赖、模型字段、Admin、行命令引擎标记

**Files:**
- Modify: `requirements.txt`
- Modify: `sql/models.py`
- Modify: `sql/offlinedownload.py`
- Modify: `sql/admin.py`

**Interfaces:**
- Produces: `Instance.client_cert` / `client_key` / `ca_cert`；`DB_TYPE_CHOICES` 含 mqtt/rabbitmq

**Note:** `AVAILABLE_ENGINES` 注册放到 Task 3，与引擎文件一起提交，避免半注册。

- [ ] **Step 1: 追加依赖**

```
pika==1.3.2
paho-mqtt==2.1.0
```

- [ ] **Step 2: 扩展模型**

`DB_TYPE_CHOICES` 增加 `("mqtt", "MQTT")`、`("rabbitmq", "RabbitMQ")`。

`Instance` 在 `verify_ssl` 后增加三个 `EncryptedTextField`：`client_cert`、`client_key`、`ca_cert`（`blank=True, null=True, default=""`）。

- [ ] **Step 3: offlinedownload**

```python
LINE_BASED_COMMAND_ENGINES = {"redis", "memcached", "mqtt", "rabbitmq"}
```

- [ ] **Step 4: Admin 控件**

`InstanceAdmin.formfield_for_dbfield`：`client_key` 用 `PasswordInput(render_value=True)`；`client_cert`/`ca_cert` 用 `Textarea`。

- [ ] **Step 5: Commit**

```bash
git add requirements.txt sql/models.py sql/offlinedownload.py sql/admin.py
git commit -m "feat(mq): add Instance cert fields and mq deps for MQTT/RabbitMQ"
```

---

### Task 3: RabbitmqEngine 连接与查询拉取 — TDD

**Files:**
- Create: `sql/engines/rabbitmq.py`
- Create: `sql/engines/mqtt.py`（最小占位）
- Create: `sql/engines/test_rabbitmq.py`
- Modify: `archery/settings.py`

**Interfaces:**
- Produces: `RabbitmqEngine.get_connection` / `test_connection` / `get_all_databases` / `query` / `query_check`

- [ ] **Step 0: settings + mqtt 占位**

`ENABLED_ENGINES` 与 `AVAILABLE_ENGINES` 加入：

```python
"mqtt": {"path": "sql.engines.mqtt:MqttEngine"},
"rabbitmq": {"path": "sql.engines.rabbitmq:RabbitmqEngine"},
```

`mqtt.py` 占位类：`name`/`info`；`get_all_databases` 返回 `default`；`test_connection` 可暂 `raise NotImplementedError`（Task 5 替换）。

- [ ] **Step 1: 写失败单测**

```python
# -*- coding: UTF-8 -*-
from unittest import TestCase
from unittest.mock import MagicMock, patch

from sql.engines.rabbitmq import RabbitmqEngine
from sql.models import Instance


class TestRabbitmqEngine(TestCase):
    def setUp(self):
        self.ins = Instance(
            instance_name="rmq_test",
            type="master",
            db_type="rabbitmq",
            host="127.0.0.1",
            port=5672,
            user="root",
            password="secret",
            db_name="/",
        )

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_test_connection_ok(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_conn.is_open = True
        mock_conn_cls.return_value = mock_conn
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.test_connection()
        self.assertFalse(result.error)
        mock_conn.close.assert_called()

    def test_query_check_allows_basic_get(self):
        engine = RabbitmqEngine(instance=self.ins)
        r = engine.query_check(sql="basic_get myqueue")
        self.assertFalse(r["bad_query"])

    def test_query_check_blocks_publish(self):
        engine = RabbitmqEngine(instance=self.ins)
        r = engine.query_check(sql='publish amq.default rk "hi"')
        self.assertTrue(r["bad_query"])

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_basic_get_auto_ack(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_ch = MagicMock()
        mock_conn.channel.return_value = mock_ch
        mock_conn_cls.return_value = mock_conn
        method = MagicMock()
        method.delivery_tag = 1
        method.routing_key = "myqueue"
        mock_ch.basic_get.return_value = (method, MagicMock(), b"hello")
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.query(db_name="/", sql="basic_get myqueue")
        mock_ch.basic_ack.assert_called_with(delivery_tag=1)
        self.assertIn("hello", str(result.rows))
```

- [ ] **Step 2: 跑测确认失败**

```bash
pytest sql/engines/test_rabbitmq.py -v
```

Expected: FAIL（导入失败）。

- [ ] **Step 3: 实现 `RabbitmqEngine`（连接 + 查询）**

必须包含：

- `_vhost(db_name)` → `db_name or self.db_name or "/"`
- `_validate_certs()`：cert/key 缺一不可
- `_ssl_options()`：临时 PEM 文件 + `pika.SSLOptions`；`verify_ssl=False` 时关闭校验
- `get_connection` / `test_connection` / `get_all_databases`（当前 vhost 一项）/ `get_all_tables`（空）
- `query_check`：允许 `basic_get`、`get`、`queue_declare_passive`、`help`
- `query`：`basic_get` 同连接 `basic_ack`；超时/空队列返回空结果

- [ ] **Step 4: 跑测通过**

```bash
pytest sql/engines/test_rabbitmq.py -v
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add archery/settings.py sql/engines/rabbitmq.py sql/engines/mqtt.py sql/engines/test_rabbitmq.py
git commit -m "feat(rabbitmq): add RabbitmqEngine connection and query pull"
```

---

### Task 4: RabbitmqEngine 上线写命令

**Files:**
- Modify: `sql/engines/rabbitmq.py`
- Modify: `sql/engines/test_rabbitmq.py`

**Interfaces:**
- Produces: `execute_check` / `execute_workflow`

- [ ] **Step 1: 追加单测**

```python
    def test_execute_check_allows_publish(self):
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.execute_check(sql='publish "" myqueue "hello"')
        self.assertEqual(result.rows[0].errlevel, 0)

    def test_execute_check_rejects_basic_get(self):
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.execute_check(sql="basic_get myqueue")
        self.assertEqual(result.rows[0].errlevel, 2)

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_execute_workflow_publish(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_ch = MagicMock()
        mock_conn.channel.return_value = mock_ch
        mock_conn_cls.return_value = mock_conn
        workflow = MagicMock()
        workflow.db_name = "/"
        workflow.sqlworkflowcontent.sql_content = 'publish "" myqueue "hello"'
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.execute_workflow(workflow)
        mock_ch.basic_publish.assert_called()
        self.assertEqual(result.rows[0].errlevel, 0)
```

- [ ] **Step 2: 跑测失败 → 实现 → 通过**

写命令白名单：`publish`、`queue_declare`、`exchange_declare`、`queue_bind`、`purge`/`queue_purge`、`queue_delete`。

只读命令进工单 → `errlevel=2`「禁止使用查询命令！」。

- [ ] **Step 3: Commit**

```bash
git add sql/engines/rabbitmq.py sql/engines/test_rabbitmq.py
git commit -m "feat(rabbitmq): add execute_check and execute_workflow write commands"
```

---

### Task 5: MqttEngine 完整实现 — TDD

**Files:**
- Replace: `sql/engines/mqtt.py`
- Create: `sql/engines/test_mqtt.py`

**Interfaces:**
- Produces: `subscribe` 短拉取（查询）；`publish`（工单）；TLS/证书参数传入 paho

- [ ] **Step 1: 写单测**

```python
# -*- coding: UTF-8 -*-
from unittest import TestCase
from unittest.mock import MagicMock, patch

from sql.engines.mqtt import MqttEngine
from sql.models import Instance


class TestMqttEngine(TestCase):
    def setUp(self):
        self.ins = Instance(
            instance_name="mqtt_test",
            type="master",
            db_type="mqtt",
            host="127.0.0.1",
            port=1883,
            user="",
            password="",
            db_name="default",
        )

    def test_query_check_allows_subscribe(self):
        engine = MqttEngine(instance=self.ins)
        r = engine.query_check(sql="subscribe archery/test 2 5")
        self.assertFalse(r["bad_query"])

    def test_query_check_blocks_publish(self):
        engine = MqttEngine(instance=self.ins)
        r = engine.query_check(sql='publish archery/test "hi"')
        self.assertTrue(r["bad_query"])

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_test_connection(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        engine = MqttEngine(instance=self.ins)
        result = engine.test_connection()
        mock_client.connect.assert_called()
        mock_client.disconnect.assert_called()
        self.assertFalse(result.error)
```

- [ ] **Step 2: 实现并跑通**

- `Client(CallbackAPIVersion.VERSION2, ...)`
- `subscribe <topic> [timeout_sec] [max_msgs]`：硬顶 `timeout_sec<=30`、`max_msgs<=100`；默认 3 秒 / 10 条
- `publish` 仅工单路径
- 证书/TLS 与 RabbitMQ 相同可选组合

```bash
pytest sql/engines/test_mqtt.py -v
```

- [ ] **Step 3: Commit**

```bash
git add sql/engines/mqtt.py sql/engines/test_mqtt.py
git commit -m "feat(mqtt): add MqttEngine query subscribe and workflow publish"
```

---

### Task 6: 可选集成冒烟测试

**Files:**
- Create: `sql/engines/test_mq_integration.py`

- [ ] **Step 1: 编写 skip 友好测试**

- 无 `ARCHERY_TEST_RABBITMQ_PASSWORD` 或端口不通 → `pytest.skip`
- RabbitMQ：`test_connection` → 工单式 `queue_declare` + `publish` → `basic_get` 断言 payload
- MQTT：短 `subscribe` + `publish`（可通过引擎工单/查询组合）断言收到消息
- 证书用例：仅当 `ARCHERY_TEST_MQ_CA/CERT/KEY` 与 TLS 端口存在时运行

- [ ] **Step 2: 本地验证**

```bash
export ARCHERY_TEST_RABBITMQ_PASSWORD='...'
pytest sql/engines/test_mq_integration.py -v
```

Expected: 有 broker 时 PASS；CI 无 broker 时 skip。

- [ ] **Step 3: Commit**

```bash
git add sql/engines/test_mq_integration.py
git commit -m "test(mq): add optional live EMQX/RabbitMQ integration smoke tests"
```

---

### Task 7: 文档收尾与验收清单

**Files:**
- Modify: `scripts/mq_env/README.md`

- [ ] **Step 1: 补充 Archery 实例配置示例与命令示例**

含：`db_type`、端口、证书字段、查询/工单示例。

- [ ] **Step 2: 手工验收清单**

1. Admin 可创建 mqtt/rabbitmq 实例  
2. 测试连通成功  
3. 查询页只读/短拉取成功，写命令被拒  
4. 上线工单写命令成功  
5. （证书环境就绪时）mTLS 连通成功  

- [ ] **Step 3: Commit**

```bash
git add scripts/mq_env/README.md
git commit -m "docs(mq): document instance setup and acceptance checklist"
```

---

## Self-Review (plan vs spec)

| Spec 项 | Task |
|---------|------|
| §2 环境准备 + 用户名密码/证书验证 | Task 1（硬门禁） |
| 双独立 Engine | Task 3–5 |
| Instance 证书字段 | Task 2 |
| 无 Management / 无 consume | 白名单约束 |
| 查询/工单双路径 | Task 3–5 |
| offlinedownload | Task 2 |
| mock + 可选集成 | Task 3–6 |
| pika / paho-mqtt | Task 2 |
