# MQTT / RabbitMQ 熟悉 CLI 语法与长等待查询 设计

日期：2026-07-18  
状态：已定稿（待实现计划）  
关联：`docs/superpowers/specs/2026-07-17-mqtt-rabbitmq-engine-design.md`（实例类型、认证、短拉取安全边界仍有效；**命令语法与长等待查询路径以本文为准**）

## 1. 背景与问题

v1 引擎采用 Archery 自研 DSL（如 `publish topic "msg"`、`basic_get q`），与 MQTTX / rabbitmqadmin 习惯不一致，强迫使用者再学一套语法。

同时连接信息已在 `Instance` 上配置，命令中不应再要求填写登录参数。

长等待类查询（MQTT 订阅窗口、RabbitMQ 在超时前持续取消息）若走同步 HTTP，存在卡死 worker、关闭页面后服务端仍执行的问题。

## 2. 目标

1. **语法**：MQTT 只接受 **MQTTX CLI 子集**；RabbitMQ 只接受 **rabbitmqadmin 子集**。  
2. **连接**：一律使用当前选中实例；命令中的连接类参数 **静默忽略**（不报错、不覆盖实例）。  
3. **批量**：编辑器支持 **多行**，每行一条命令；查询与上线均支持。  
4. **长等待查询**：MQTT `sub` 与 RabbitMQ `get` 走 **异步任务 + 可取消 + 增量展示**；其它引擎与其它 MQ 命令保持同步。  
5. **不兼容**旧自研 DSL；不提供「请改用新语法」类迁移提示。

## 3. 非目标

- 完整实现 MQTTX / rabbitmqadmin 全部子命令（无 bench、无文件批量导入等）  
- 长连接 `basic.consume` / MQTT 常驻订阅进程  
- 把全部 SQL 查询页改为异步（不得影响 MySQL 等其它引擎）  
- 上线工单异步化  
- 兼容或探测旧 DSL

## 4. 方案选择

采用 **引擎内替换解析器（方案 1）**：在 `MqttEngine` / `RabbitmqEngine` 内解析熟悉 CLI 子集，底层仍用 `paho-mqtt` / `pika`，连接取自 `Instance`。

长等待查询另增 **任务 + 轮询 + 取消** 路径，且 **仅** 在 `db_type in {mqtt, rabbitmq}` 且命令为 `sub` / `get` 时启用。

## 5. 命令子集与场景白名单

### 5.1 通用

- 每行独立解析；空行跳过；支持行首 `#` 注释。  
- 允许可选程序名前缀：`mqttx` / `rabbitmqadmin`（有则剥掉）。  
- 未知业务选项：该行拒绝。  
- 连接类选项：解析后丢弃。  
- `help`：只打印本引擎允许的子集示例（示例不含 host/port/user）。

### 5.2 静默忽略的连接参数

| MQTTX | rabbitmqadmin |
|-------|----------------|
| `-h` / `--host`，`-p` / `--port`，`-u` / `--username`，`-P` / `--password`，以及命令中出现的 TLS/证书连接类选项 | `-H` / `--host`，`-P` / `--port`，`-u` / `--username`，`-p` / `--password`，`-V` / `--vhost` |

Vhost / 逻辑库以页面所选 `db_name` 为准；命令中的 `-V` 忽略。

### 5.3 MQTT（MQTTX 风格）

| 场景 | 允许 | 说明 |
|------|------|------|
| 查询 | `sub -t <topic> [-q N] [-C N]`（及文档约定的长选项等价） | 异步；见 §6 |
| 查询 | `help` | 同步 |
| 上线 | `pub -t <topic> -m <payload> [-q N]` | 同步工单执行 |
| 查询禁写 / 上线禁只读 | `pub` 进查询、`sub` 进上线 | 检查失败 |

默认：QoS `0`；`-C` 缺省 `10`，硬上限 `100`。

### 5.4 RabbitMQ（rabbitmqadmin 风格）

| 场景 | 允许 | 说明 |
|------|------|------|
| 查询 | `get queue=<name> [count=N]` | 异步；见 §6 |
| 查询 | `list queues` | 同步 |
| 查询 | `help` | 同步 |
| 上线 | `publish routing_key=… payload=… [exchange=…]` | exchange 缺省 `""` |
| 上线 | `declare queue name=…` | |
| 上线 | `declare exchange name=… [type=…]` | type 缺省 `direct` |
| 上线 | `declare binding …`（参数对齐 rabbitmqadmin 常用写法） | |
| 上线 | `purge queue name=…` | |
| 上线 | `delete queue name=…` | |

`get` 的 `count` 缺省 `1`。

### 5.5 多行批量

- **查询**：多行按行执行；每一行 `sub`/`get` **各自创建一个 job**（取消只影响对应 job；UI 按行展示各 job 的增量结果）。非长等待行仍同步执行并插入该行结果。  
- **上线**：多行同步按行执行；前序失败则后续中止（与现有工单行为一致）。

## 6. 长等待查询：异步 + 取消 + 增量展示

### 6.1 适用范围

仅当同时满足：

1. `instance.db_type` 为 `mqtt` 或 `rabbitmq`  
2. 该行命令为 MQTT `sub` 或 RabbitMQ `get`  

其它引擎、MQ 的 `help` / `list queues` / 全部上线写命令：保持现有同步路径。

### 6.2 超时

| 项 | 值 |
|----|-----|
| 默认等待 | **60s** |
| 硬上限 | **3600s（1 小时）** |
| 可配置 | `SysConfig` 可调整硬上限（及可选默认值） |

防卡死与关页：

- 前端离开页面 / 显式停止 → 调用取消 API  
- Worker 循环每 tick 检查取消标记 → 断连并结束  
- 硬上限为最后保险丝，避免遗忘取消时无限占用

### 6.3 数据流

```text
创建任务（白名单校验、忽略连接参数、注入 Instance）
  → job_id
轮询状态：pending | running | partial | done | cancelled | failed
  → partial/done 携带已收到的 rows → UI 增量刷新
取消：POST cancel(job_id) → worker 停止
```

### 6.4 引擎循环语义

**MQTT `sub`**

- 订阅后在超时 / 达 `-C` / 取消前接收消息。  
- 每收到一条追加到任务结果快照（增量展示）。  
- 超时结束：`done`，可带 warning「等待超时」，rows 为已收到消息（可为空）。

**RabbitMQ `get`**

- 在超时 / 收满 `count` / 取消前循环 `basic_get`。  
- **队列暂时为空也继续干等**，直到超时或取消（不只在有消息时返回）。  
- 每取到一条追加快照；自动 ack 策略与现网一致。  
- 超时结束：返回已收到消息（可为 0 条）+ 超时提示。

### 6.5 多条消息展示

等待过程中收到的多条消息均展示（受 `-C` / `count` 上限约束）；采用 **增量刷新**（轮询带上当前已累积 rows），而非仅结束时一次性显示。

## 7. 与旧设计 / 旧 DSL 的关系

| 项目 | 处理 |
|------|------|
| 2026-07-17 引擎设计中的认证、实例字段、禁止长 consume | 保留 |
| 自研 DSL 命令表 | **废止**；实现以本文 §5 为准 |
| 已存在的旧命令字符串 | 按「无法解析 / 禁止」失败，**不**做迁移提示 |

文档与 `scripts/mq_env/README.md` 中的指令级用例需在实现时改为 MQTTX / rabbitmqadmin 示例。

## 8. 错误处理

| 情况 | 行为 |
|------|------|
| 非子集语法 / 未知业务选项 | 该行或任务创建失败 |
| 写命令出现在查询 / 只读出现在上线 | 检查失败（沿用现有 errlevel 风格） |
| Broker 连接失败 | job `failed` 或同步路径返回 error |
| 用户取消 | job `cancelled`，**保留并展示**取消前已收到的 rows |
| 达硬超时 | `done` + warning + 已收到 rows |

## 9. 测试要点

1. **解析单元测试**：MQTTX `pub`/`sub`、rabbitmqadmin `publish`/`get`/`declare`；忽略 `-h/-p/-u` 等；拒绝未知业务选项；多行与 `#` 注释。  
2. **白名单**：查询/上线交叉拒绝。  
3. **异步**：`sub`/`get` 创建 job、partial 增量条数、cancel 后循环退出、默认 60s / 硬顶 3600s 裁剪。  
4. **隔离**：非 MQ 引擎仍走同步 execute，行为不变。  
5. **可选集成**：真实 EMQX / RabbitMQ 上验证干等超时与增量收消息。  
6. **回归**：旧 DSL 样本应失败（无友好迁移文案要求）。

## 10. 决策摘要

| 决策 | 选择 |
|------|------|
| 交互形态 | 熟悉 CLI 子集，连接来自实例 |
| 方言 | MQTT→MQTTX；RabbitMQ→rabbitmqadmin |
| 旧 DSL | 不兼容、不提示 |
| 连接参数出现在命令中 | 静默忽略 |
| 批量 | 多行，每行一条；查询与上线均支持 |
| 长等待 | 仅 MQTT `sub` + RabbitMQ `get` 异步+取消+增量 |
| 空队列 get | 干等到超时 |
| 默认 / 硬顶超时 | 60s / 3600s（SysConfig 可调硬顶） |
| 实现主路径 | 引擎内换解析器 + MQ 专用任务 API |
