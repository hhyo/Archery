# RabbitMQ rabbitmqadmin A 档命令对齐（AMQP）设计

日期：2026-07-22  
状态：已定稿（待实现计划）  
权威来源：本机 `rabbitmq:3.13-management` 容器内 `rabbitmqadmin help subcommands`（Management 插件自带 CLI）；实现参数名/必填项/可选框与该输出一致，**禁止自造参数名或语义**。  
关联：

- `docs/superpowers/specs/2026-07-18-mq-familiar-cli-async-query-design.md`（异步 get、连接忽略、场景分工）
- `docs/superpowers/specs/2026-07-22-mq-ui-help-docs-design.md`（帮助 Tab；本变更后须同步示例）

## 1. 背景与问题

当前 Archery RabbitMQ 子集部分命令与官方 `rabbitmqadmin` 不一致（例如 binding 使用 `queue=`/`exchange=`；`list queues` 假支持；缺少 `auto_delete`、`delete exchange`、`ackmode` 等）。用户希望在 **不引入 Management HTTP** 的前提下，把能用 AMQP（pika）落地的命令对齐官方语法，并由单元测试高覆盖锁住行为。

## 2. 目标

1. **语法与官方一致**：参数名、必填/可选、子目标（`declare`/`delete` 的 object 词）以 `rabbitmqadmin help subcommands` 为准。  
2. **执行走 AMQP**：在 Instance 连接上用 pika 实现可映射语义。  
3. **破坏性对齐**：binding 只接受 `source`/`destination`（及官方可选键）；旧 `queue=`/`exchange=` 绑定写法拒绝。  
4. **高覆盖单测**：解析、校验、执行路径（含 mock channel）与错误文案均有测试；关键矩阵见 §8。  
5. **帮助与契约测试**随语法更新，避免文档教错命令。

## 3. 非目标

- Management HTTP：`list *`、`show`、`close connection`、带列名的 list  
- 官方有但本阶段不做的可选参数：`arguments`、`properties`、`payload_file`、`payload_encoding`/`encoding`、`internal`、`node`、`queue_type`、exchange↔exchange binding（`destination_type=exchange`）  
- 从 stdin 读 publish payload（Archery 行命令无 stdin）  
- MQTT 变更  

若用户传入本阶段未实现的官方可选参数 → **解析失败**（与「未知参数」一致），不得静默忽略（避免行为与官方 CLI 表象不符）。

## 4. 方案

**就地扩展** `sql/engines/mq_cli.py` + `sql/engines/rabbitmq.py`（方案 1）。不引入子进程、不抽大模块。

## 5. 官方命令面（本阶段采纳）

以下摘自 RabbitMQ 3.13 `rabbitmqadmin help subcommands`，并标注本阶段是否实现。

### 5.1 查询

| 官方语法 | 本阶段 |
|----------|--------|
| `get queue=... [count=... ackmode=... payload_file=... encoding=...]` | 实现 `queue`（必填）、`count`、`ackmode`；拒绝 `payload_file`/`encoding` |
| `help` | 保持；更新帮助行 |
| `list …` | **不支持**（解析失败，明确文案：需 Management，本子集未实现） |

**`get` 官方要点（不得改名）：**

- 参数名是 **`ackmode`**，不是历史文档里的 `requeue`（3.7+ 已替换）。  
- 传入 `requeue=` → 解析失败，错误中提示改用 `ackmode=`。  
- `count` 缺省与官方一致：`1`。  
- `ackmode` 缺省与官方 rabbitmqadmin 源码 EXTRA_VERBS 一致：`ack_requeue_true`。  
- 允许的 `ackmode` 值（Management get API / CLI 通用）：  
  `ack_requeue_true` \| `ack_requeue_false` \| `reject_requeue_true` \| `reject_requeue_false`  
- AMQP 映射（实现必须按此，测试锁住）：  

| ackmode | 取到消息后 |
|---------|------------|
| `ack_requeue_true` | nack/reject + requeue=True（消息回队列；结果仍展示） |
| `ack_requeue_false` | ack（移出队列） |
| `reject_requeue_true` | reject + requeue=True |
| `reject_requeue_false` | reject + requeue=False |

异步 job、超时 SysConfig、空队列干等：**不变**。

### 5.2 上线 — declare

| 官方语法 | 本阶段 |
|----------|--------|
| `declare exchange name=... type=... [auto_delete=... durable=... internal=... arguments=...]` | 必填 `name`+`type`；可选 `durable`/`auto_delete`；拒绝 `internal`/`arguments` |
| `declare queue name=... [auto_delete=... durable=... arguments=... node=... queue_type=...]` | 必填 `name`；可选 `durable`/`auto_delete`；拒绝其余可选 |
| `declare binding source=... destination=... [destination_type=... routing_key=... arguments=...]` | 必填 `source`+`destination`；可选 `destination_type`（仅允许 `queue`，缺省 `queue`）、`routing_key`（缺省 `""`）；拒绝 `arguments` 与 `destination_type=exchange` |

显式 `durable`/`auto_delete`：解析为 bool 后传入 pika；**省略则不传该 kwarg**（与官方「可选」一致，不在文档里谎称默认 true）。

旧键：`declare binding` 若出现 `queue=` 或 `exchange=` → 失败，提示使用 `source`/`destination`。

### 5.3 上线 — delete / purge

| 官方语法 | 本阶段 |
|----------|--------|
| `delete exchange name=...` | 实现 → `exchange_delete` |
| `delete queue name=...` | 保持 → `queue_delete` |
| `delete binding source=... destination_type=... destination=... [properties_key=...]` | 实现；`destination_type` 仅 `queue`；`properties_key` 缺省视为 `""`（与常见 CLI 用法一致）；执行 `queue_unbind(queue=destination, exchange=source, routing_key=properties_key or "")` |
| `purge queue name=...` | 保持 |

### 5.4 上线 — publish

| 官方语法 | 本阶段 |
|----------|--------|
| `publish routing_key=... [payload=... properties=... exchange=... payload_encoding=...]` | 必填 `routing_key`；`payload` 在 Archery 中**必填**（无 stdin）；`exchange` 可选；拒绝 `properties`/`payload_encoding` |

`exchange` 缺省：官方 CLI 对缺省 exchange 使用 default exchange；AMQP 侧传 `exchange=""`。若用户显式写 `exchange=amq.default`，归一为 `""` 再 publish（与 default exchange 等价）。

保持 `confirm_delivery` + `mandatory=True` 与不可路由失败语义（产品已定安全行为；与「裸 rabbitmqadmin HTTP publish」不完全同一传输层，但命令参数面仍对齐官方）。

## 6. 查询 / 上线分工

| 允许查询 | 允许上线 |
|----------|----------|
| `get`、`help` | `publish`、`declare`、`delete`、`purge` |

`list`/`close` 任一场景均拒绝。

## 7. 实现落点

| 文件 | 变更 |
|------|------|
| `sql/engines/mq_cli.py` | 解析：ackmode、auto_delete、binding source/destination/destination_type、delete exchange/binding、list 拒绝、未知/未实现可选参数拒绝 |
| `sql/engines/rabbitmq.py` | 执行映射；`run_get` 按 ackmode；declare/delete 扩展；HELP_ROWS 更新 |
| `sql/engines/test_mq_cli.py` | 解析矩阵高覆盖 |
| `sql/engines/test_rabbitmq.py` | query_check/execute_check/execute_workflow/run_get mock 高覆盖 |
| `sql/templates/sqlquery.html` / `sqlsubmit.html` | 帮助示例改为官方键名；去掉假 list 可执行暗示 |
| `sql/tests/test_mq_help_templates.py` | 契约字符串同步 |

## 8. 测试要求（高覆盖，强制）

原则：每个官方采纳的命令至少有 **成功路径 + 缺参失败 + 非法值失败**；破坏性变更有 **旧语法拒绝**；执行层用 mock channel 断言调用的方法与 kwargs。

### 8.1 解析（`test_mq_cli.py`）

- `get`：缺省 count/ackmode；显式四种 ackmode；拒绝 `requeue=`；拒绝 `payload_file`/`encoding`  
- `declare queue/exchange/binding`：必填、可选 bool、拒绝未实现可选、binding 旧键拒绝、`destination_type=exchange` 拒绝  
- `delete queue/exchange/binding`：必填组合  
- `publish`：缺省 exchange；`amq.default` 归一；拒绝 properties/encoding  
- `list`/`close`：失败  
- `rabbitmqadmin` 前缀与连接旗标忽略回归  

### 8.2 引擎（`test_rabbitmq.py`）

- `query_check`/`execute_check` 白名单与场景互斥  
- `run_get`：四种 ackmode 分别断言 ack / nack|reject + requeue 标志  
- `_execute_write_command`：queue_declare/exchange_declare 仅在显式时含 durable/auto_delete；bind/unbind kwargs；exchange_delete；publish exchange `""`  
- `list` 不再走「提交成功再 error 字符串」的假支持（与解析失败一致）  

覆盖率目标：变更涉及的 `mq_cli` rabbit 分支与 `RabbitmqEngine` 新增/改动分支 **行覆盖尽可能高**（实现计划中写明对新增函数跑 `pytest --cov` 检查清单）；禁止只测「能 parse」不测「调用了正确 pika API」。

## 9. 验收

1. 对照本机 `rabbitmqadmin help subcommands`，本阶段命令的参数名与必填项一致。  
2. §8 测试全部通过。  
3. 帮助 Tab / 契约测试无旧 binding 键、无 `requeue=`、无「list 可当查询用」的误导。  
4. 异步 get + 超时、publish 不可路由、连接旗标忽略不回归。  

## 10. 对先前讨论稿的修正

- 此前草案写的 `get … requeue=` **作废**；以官方 **`ackmode=`** 为准（用户最初粘贴的 `requeue` 为过时文档）。  
- `list queues`：由「可提交后固定 error」改为 **解析即不支持**。  
- binding / delete binding 的键名以官方 `help` 为准，含 `destination_type`。  

## 11. 开放决策

无。范围（AMQP / A 档 / 方案 1 / 只认标准 binding / 高覆盖 / 官方为准）已确认；`ackmode` 对齐为对「命令必须与官方一样」的落实。
