# MQTT / RabbitMQ Engine 设计

日期：2026-07-17  
状态：草稿（待用户审阅）

> **命令语法**以 [2026-07-18 设计](2026-07-18-mq-familiar-cli-async-query-design.md) 为准（MQTTX / rabbitmqadmin 子集）；本文其余章节（实例、认证、安全边界）仍有效。

## 1. 背景与目标

Archery 通过 `EngineBase` + `AVAILABLE_ENGINES` / `ENABLED_ENGINES` + `Instance.db_type` 扩展数据源。现有引擎含 Redis、Memcached 等非 SQL 类型，但 **不支持 MQTT 与 RabbitMQ**。

### 目标（v1）

将 MQTT、RabbitMQ 作为与 Redis 同级的**实例类型**：

- 登记实例、测试连通
- SQL 查询页：只读 / 短拉取类命令（白名单）
- SQL 上线工单：写命令（白名单），工单中禁止只读命令
- 认证：用户名密码（可选）+ TLS + **客户端证书（可选）**；MQTT 与 RabbitMQ 一致

### 非目标（v1）

- RabbitMQ Management HTTP API（及独立 mgmt host/port 配置）
- 真正的长连接 `basic.consume` / MQTT 常驻订阅
- 完整 topic / queue 资源树浏览
- 客户端证书以外的高级 PKI（如 UI 上传后自动轮换）

## 2. 前置条件：环境准备（必须先完成）

实现与集成测试开始前，**必须先在 WSL 环境把 broker 准备好，并完成账号与证书验证**。引擎代码依赖可连通、可认证的真实服务做可选集成测试。

### 2.1 运行时环境

| 组件 | 约定 |
|------|------|
| 宿主 | WSL2（Ubuntu）+ Docker |
| MQTT | EMQX（已用镜像 `emqx/emqx:5.1.0`，容器名建议 `emqx`） |
| RabbitMQ | `rabbitmq:3.13.x-management`（容器名建议 `rabbitmq_3_13`） |
| 常用端口 | MQTT `1883` / MQTTS `8883`；AMQP `5672` / AMQPS `5671`；EMQX Dashboard `18083`；RabbitMQ Mgmt `15672`（Mgmt 仅运维用，**产品 v1 不依赖**） |

启动检查示例：

```bash
sudo systemctl start docker   # 若 daemon 未运行
docker start rabbitmq_3_13 emqx
# 端口探测
# 5672 / 1883 在 WSL 内 TCP 可达
```

### 2.2 用户名密码验证（必做）

在写引擎前，用客户端或一次性脚本确认：

1. **RabbitMQ**：使用实例计划采用的用户（当前环境已有 `root` / `qworker` 等，**勿假设 `guest`**）对 `127.0.0.1:5672` 完成 AMQP 登录；失败则先在容器内建用户/授权。
2. **EMQX**：使用计划采用的 MQTT 用户名密码连接 `127.0.0.1:1883`；若启用匿名则明确记录，集成测试环境变量需与之一致。

验证通过标准：能建连，并完成一次最小往返（RabbitMQ：声明临时队列或 `basic_publish`/`basic_get`；MQTT：`publish` + 短时 `subscribe` 收到消息）。

### 2.3 证书验证（必做，证书可选但能力要验通）

产品要求证书字段**可选**，但环境侧需准备一套可用的测试证书，并验证：

1. 生成或导入测试用 CA、服务端证书、**客户端证书 + 私钥**（MQTT / RabbitMQ 可各一套或共用测试 CA）。
2. 配置 EMQX 监听器（如 `8883`）与 RabbitMQ TLS 监听（如 `5671`）信任该 CA，并要求/允许客户端证书。
3. 分别验证：
   - **仅用户名密码 + TLS**（无客户端证书）
   - **TLS + 客户端证书 ± 用户名密码**
4. 将证书路径、密码、端口写入集成测试环境变量或本地未入库的配置说明（**私钥不进 git**）。

未完成 §2.2 / §2.3 前，不进入引擎功能实现与「真实挂载」集成测试。

### 2.4 可选集成测试约定

- CI / 本地无 broker：相关用例 **skip**
- 探测 `ARCHERY_TEST_MQTT_HOST` / `ARCHERY_TEST_RABBITMQ_HOST`（或默认 `127.0.0.1:1883` / `5672`）可达则跑冒烟
- 覆盖：用户名密码连通；在证书环境变量齐全时覆盖 mTLS 连通

## 3. 架构

```text
Instance(db_type=mqtt|rabbitmq)
        │
        ▼
   get_engine()
        │
   ┌────┴────┐
   ▼         ▼
MqttEngine  RabbitmqEngine   ← 两个独立 Engine（方案 1）
   │         │
   │         └─ pika → AMQP
   └─ paho-mqtt → MQTT (EMQX)
```

对齐 Redis：

| 入口 | 方法 |
|------|------|
| 测试连通 | `test_connection` |
| 查询页 | `query` + `query_check` |
| 上线工单 | `execute_check` + `execute_workflow` |
| 资源列表 | `get_all_databases` / `get_all_tables` |

不引入共享 `MessageQueueEngineBase`（MQTT 与 AMQP 差异大，第一版分开实现）。

## 4. 数据模型与连接

### 4.1 复用 `Instance` 字段

| 字段 | MQTT | RabbitMQ |
|------|------|----------|
| `host` / `port` | broker | AMQP |
| `user` / `password` | 可选 | 可选（可与证书并用） |
| `is_ssl` / `verify_ssl` | TLS | AMQPS / TLS |
| `db_name` | 逻辑库名，默认 `default` | **vhost**，空则 `/` |
| `tunnel` | 沿用现有 SSH 隧道 | 同左 |

### 4.2 新增字段（mqtt / rabbitmq 共用，其他引擎忽略）

| 字段 | 说明 |
|------|------|
| `client_cert` | 客户端证书 PEM（加密存储，可选） |
| `client_key` | 客户端私钥 PEM（加密存储，可选） |
| `ca_cert` | 校验服务端用 CA（加密存储，可选） |

规则：

- 三字段均可空
- 仅有 cert 无 key（或不完整）→ 建连前明确报错
- 有 `client_cert` + `client_key` → 启用 mTLS；可同时带用户名密码

**不**新增 Management 专用 host/port；v1 不做 Management API。

### 4.3 资源映射

- **MQTT**：`get_all_databases()` → 固定一项（`db_name` 或 `default`）；`get_all_tables()` → 空
- **RabbitMQ**：`get_all_databases()` → 当前 vhost 一项（无 Management，不枚举全部 vhost）；`get_all_tables()` → 空；查询/执行时 `db_name` 作为 AMQP vhost

### 4.4 连接行为

- 短连接；查询结束默认关闭
- 连接与操作设超时
- 收消息：短时拉取，强制 timeout / max_msgs 上限，避免拖死 Web 请求

## 5. 命令集与安全

风格接近 Redis：按行拆分 + `shlex` 分词；未列命令一律拒绝。

### 5.1 MQTT

**查询页**：`subscribe <topic> [timeout_sec] [max_msgs]`、`help`（`topics` 若无法枚举可返回不支持提示）

**上线工单**：`publish <topic> <payload> [qos]`（及可选别名）

查询页不执行 `publish`（写走上线工单）。

### 5.2 RabbitMQ（纯 AMQP）

**查询页**：`basic_get` / `get <queue> [...]`、`queue_declare_passive <queue>`、`help`

**上线工单**：`publish`、`queue_declare`、`exchange_declare`、`queue_bind`、`purge`、`queue_delete` 等（具体参数表在实现计划中定稿）

**明确不纳入**（与 Web 短请求冲突）：

- `basic.consume` / `basic.cancel`
- 独立的 `basic.ack` / `nack` / `reject` / `basic.qos`

**同请求确认**：`basic_get` 在同一连接内自动 ack（或参数控制后仍在本请求内 ack），再关闭连接。这是管理台「看一条」，不是生产级消费模型。

### 5.3 检查逻辑

- `query_check`：非查询白名单 → `bad_query=True`
- `execute_check`：只读进工单失败；写命令不在白名单失败
- 证书内容不写日志；错误可含 host/port/vhost，不含私钥

## 6. 改动清单

| 区域 | 改动 |
|------|------|
| `sql/engines/mqtt.py` | 新建 `MqttEngine` |
| `sql/engines/rabbitmq.py` | 新建 `RabbitmqEngine` |
| `sql/engines/test_*.py` | mock 单测 + 可选集成冒烟 |
| `sql/models.py` | `DB_TYPE_CHOICES` + 证书三字段；migration |
| `archery/settings.py` | `AVAILABLE_ENGINES` / 默认 `ENABLED_ENGINES` |
| `requirements.txt` | `paho-mqtt`、`pika` |
| 实例表单 UI | mqtt/rabbitmq 显示可选证书字段 |
| `sql/offlinedownload.py` | `LINE_BASED_COMMAND_ENGINES` 加入 `mqtt`、`rabbitmq` |
| 文档 | WSL 环境准备、账号/证书验证步骤、集成测试 env |

慢日志 / 会话诊断等 **不**强行支持。

## 7. 错误处理

| 场景 | 行为 |
|------|------|
| 连接 / TLS / 证书失败 | 可读错误；查询写入 `ResultSet.error` |
| 命令不在白名单 | 检查阶段拦截，不触达 broker |
| 短拉取超时且 0 条 | 成功空结果 + 超时提示 |
| 工单中途失败 | 对齐 Redis：已成功行保留，失败行记录，后续中止 |

## 8. 测试策略

1. **单元测试（必过）**：mock `paho-mqtt` / `pika`——连通、白名单、自动 ack、`publish` 工单路径、证书参数传入客户端。
2. **可选集成测试**：§2 环境就绪后，对 WSL 中 EMQX + RabbitMQ 做冒烟（含用户名密码；证书 env 齐全时含 mTLS）。不可达则 skip。
3. **成功标准**：§1 目标可演示；§2 验证清单有记录；无 Management、无常驻 `consume`。

## 9. 实现顺序建议

1. **环境**：WSL Docker 中 EMQX + RabbitMQ 常开；完成用户名密码与证书两条认证路径的手工/脚本验证并记录参数  
2. **模型与配置**：`DB_TYPE_CHOICES`、证书字段、migration、依赖、settings  
3. **RabbitmqEngine** → **MqttEngine**（或并行，但各自独立 PR/提交亦可）  
4. **UI** 证书字段展示  
5. mock 单测 + 可选集成冒烟  
6. 文档（环境与验证步骤）

## 10. 已确认决策摘要

| 决策点 | 结论 |
|--------|------|
| 用途 | 新实例类型（类 Redis），非通知通道 / 非 django-q |
| 能力 | 类 Redis 命令台 + 查询/上线双路径 |
| 交付 | MQTT 与 RabbitMQ 同一设计、两个 Engine |
| RabbitMQ 接入 | 仅 AMQP（pika），不做 Management |
| 资源树 | RabbitMQ：`db_name`=vhost；MQTT：单一虚拟库 |
| 收消息 | 短请求拉取，不做长订阅 |
| 认证 | 两者均支持用户名密码 + TLS + 可选客户端证书 |
| 证书存储 | `Instance` 上加密字段 |
| 集成测试 | 可选；基于 WSL 的 RabbitMQ + EMQX；环境与证书验证前置 |
