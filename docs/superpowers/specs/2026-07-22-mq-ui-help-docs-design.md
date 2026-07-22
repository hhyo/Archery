# MQTT / RabbitMQ UI 帮助文档设计

日期：2026-07-22  
状态：已定稿（待实现计划）  
关联：

- 命令子集与超时语义以  
  `docs/superpowers/specs/2026-07-18-mq-familiar-cli-async-query-design.md` 为准  
- UI 交互对标查询页现有 **Redis 帮助文档** Tab（`sql/templates/sqlquery.html`）

## 1. 背景与问题

Redis 在 SQL 查询页选中实例后，会显示「Redis帮助文档」Tab，按 Key / String / Hash 等分组介绍命令。

MQTT / RabbitMQ 已支持 MQTTX / rabbitmqadmin **子集**，但：

- 查询页没有同类帮助 Tab  
- 上线页没有帮助入口（仅有 Mongo 一行提示）  
- 用户无法从页面得知：支持哪些子命令与参数、示例如何写、超时由何处控制  

引擎内 `help` 命令仅返回短语法行（`MQTT_HELP_ROWS` / `RABBITMQ_HELP_ROWS`），不足以替代分组帮助。

## 2. 目标

1. 在 **SQL 查询页**与 **SQL 上线页**，选中 MQTT 或 RabbitMQ 实例时，显示与 Redis 同构的 **帮助文档 Tab**。  
2. 文案按 **MQTTX / rabbitmqadmin 命令分组**介绍；每组含说明、本子集语法、**一行一条可复制示例**。  
3. **两页展示同一引擎的全部分组全文**（不因页面裁剪文档）；执行权限仍由各页原有校验约束。  
4. 写清超时：等待时长由 SysConfig 控制，**不是** CLI 超时旗标。  
5. 文案只描述「熟悉 CLI 子集」；不写实现过程产物或迁移历史。

## 3. 非目标

- 不修改引擎 `MQTT_HELP_ROWS` / `RABBITMQ_HELP_ROWS`（`help` 命令保持短语法）  
- 不后端生成帮助、不新增 i18n 词条（静态中文 HTML，与 Redis 一致）  
- 不修正 Redis 帮助中过时条目  
- 不改变命令解析或异步查询行为  

## 4. 方案选择

**方案 1（采用）：直接仿 Redis**

- 在 `sqlquery.html`、`sqlsubmit.html` 增加 MQTT / RabbitMQ 帮助面板与 Tab 显隐 JS  
- 查询页沿用 `engineDisplayConfig` + `*_help_tab_add/remove`  
- 上线页补齐与查询页同构的轻量 Tab 容器（现状无 Redis 式帮助 Tab）  

未采用：共享 `{% include %}`（方案 2）、配置驱动渲染（方案 3）。理由：与现有 Redis 路径一致、改动面可控；命令集不大，两页静态全文可接受。

## 5. 页面行为

### 5.1 查询页（`sql/templates/sqlquery.html`）

| 项 | 行为 |
|----|------|
| 触发 | 实例 optgroup 为 MQTT / RabbitMQ |
| Tab 标题 | 「MQTT帮助文档」/「RabbitMQ帮助文档」 |
| 显隐 | `engineDisplayConfig` 增加 `showMqttHelp` / `showRabbitmqHelp`；与 Redis 帮助互斥 |
| 切实例 | 移除他引擎帮助 Tab，挂上当前引擎帮助 Tab |
| 内容 | 该引擎 **全部分组**（含读/写）；radio 切换分组 |

MQTT / RabbitMQ 的 format / explain 保持现有禁用逻辑。

### 5.2 上线页（`sql/templates/sqlsubmit.html`）

| 项 | 行为 |
|----|------|
| 触发 | 选中 MQTT / RabbitMQ 实例 |
| UI | 新增与查询页同构的帮助 Tab 区（挂在表单或检测结果附近均可，以实现时布局清晰为准） |
| 内容 | 与查询页 **同一套分组与示例全文**（方案 B） |
| 其它引擎 | 不显示 MQ 帮助；Mongo 一行提示逻辑不变 |

### 5.3 与异步结果 Tab 共存

查询页已有 SQL 日志 / 异步 MQ 结果等 Tab。帮助 Tab 与之并列；默认不必抢占激活态（与 Redis 帮助一致：添加 Tab，用户需要时点击）。切换实例时只维护帮助 Tab 的增删，不打断正在进行的异步查询轮询（除非现有离开页逻辑本身会取消）。

## 6. 分组与文案结构

### 6.1 版式（每个分组面板）

固定顺序：

1. **分组说明**：该子命令族在 MQTTX / rabbitmqadmin 中的用途  
2. **本子集语法**：列出已支持的参数、默认值、上限；未支持的分组写明「本子集未支持」  
3. **可复制示例**：等宽、**一行一条命令**，便于整行复制；禁止把多条命令挤进同一段叙述  
4. **连接参数**（若适用）：可写在命令中但会被忽略的旗标列表；实际连接用 Instance  
5. **超时 / 异步**（若适用）：仅 SysConfig；见 §6.4  
6. **该分组在完整 CLI 中常见但子集未实现的参数**（仅列真实 MQTTX / rabbitmqadmin 项）

口吻：面向「熟悉 MQTTX / rabbitmqadmin 的用户」；标题使用「MQTTX 子集」「rabbitmqadmin 子集」。

### 6.2 RabbitMQ 分组（对齐 rabbitmqadmin）

| 分组 | 本子集 | 面板要点 |
|------|--------|----------|
| `help` | 支持 | 示例含 `help` |
| `list` | 仅 `list queues` | 说明无 Management API 时的明确错误；示例含 `list queues` |
| `show` | 未支持 | 说明用途 +「本子集未支持」 |
| `declare` | `queue` / `exchange` / `binding` | 参数与 `durable` / `type` 默认；丰富可复制示例 |
| `delete` | 仅 `delete queue name=…` | 语法 + 示例 |
| `publish` | `routing_key` / `payload` / 可选 `exchange` | exchange 缺省 `""`；不可路由失败说明；示例 |
| `get` | `queue=` / `count=` | 异步干等、ack 行为固定、无 `ackmode`；超时 §6.4；示例 |
| `purge` | `purge queue name=…` | 语法 + 示例 |
| `close` | 未支持 | 说明用途 +「本子集未支持」 |

`get` / `list` / `declare` 等示例须包含：最简形式、带可选参数、带可忽略连接参数（如 `rabbitmqadmin -H … get queue=…`）、以及上线联调常用组合（declare → publish；消费用 get）。

**示例下限（可复制行，实现时可略增不可减）：**

```text
get queue=demo.q
get queue=demo.q count=1
get queue=demo.q count=5
rabbitmqadmin get queue=demo.q count=1
rabbitmqadmin -H 127.0.0.1 -P 5672 -u guest -p guest get queue=demo.q count=1
list queues
help
declare queue name=demo.q
declare queue name=demo.q durable=true
declare queue name=demo.q durable=false
declare exchange name=demo.ex
declare exchange name=demo.ex type=direct
declare exchange name=demo.ex type=topic durable=true
declare binding queue=demo.q exchange=demo.ex routing_key=demo.q
publish routing_key=demo.q payload=hello
publish routing_key=demo.q payload="hello from archery"
publish routing_key=demo.q payload="hello" exchange=
publish routing_key=demo.rk payload="hello" exchange=demo.ex
purge queue name=demo.q
delete queue name=demo.q
```

另可用编号写「推荐联调顺序」，命令本身仍各占一行。

### 6.3 MQTT 分组（对齐 MQTTX）

| 分组 | 本子集 | 面板要点 |
|------|--------|----------|
| `help` | 支持 | 示例含 `help` |
| `sub` | `-t/--topic`、`-q/--qos`、`-C/--count` | 默认 QoS 0；`-C` 缺省 10、上限 100；异步 + 超时 §6.4 |
| `pub` | `-t/--topic`、`-m/--message`、`-q/--qos` | 上线同步执行；示例 |
| 其它 | 未支持 | 一笔：未列出的 MQTTX 子命令/选项本子集不可用 |

**示例下限：**

```text
sub -t demo/test
sub -t demo/test -C 1
sub -t demo/test -C 10
sub -t demo/test -q 0 -C 5
sub -t demo/test -q 1 -C 5
sub -t demo/test -q 2 -C 1
sub --topic demo/test --count 3
mqttx sub -t demo/test -C 1
mqttx -h 127.0.0.1 -p 1883 sub -t demo/test -C 1
help
pub -t demo/test -m hello
pub -t demo/test -m "hello from archery"
pub -t demo/test -m "hello" -q 0
pub -t demo/test -m "hello" -q 1
pub --topic demo/test --message "hello" --qos 1
mqttx pub -t demo/test -m "hello from archery"
mqttx -h 127.0.0.1 -p 1883 pub -t demo/test -m "hi"
```

### 6.4 超时与异步（写在 `sub` / `get` 分组内，可互链）

| 项 | 说明 |
|----|------|
| CLI | 本子集 **不提供** 等待超时旗标 |
| 配置 | `mq_query_timeout_default`（默认 **60** 秒）、`mq_query_timeout_max`（硬顶 **3600** 秒） |
| 行为 | 查询页 `sub` / `get` 异步；收满条数 / 超时 / 取消结束；RabbitMQ 空队列干等至超时 |
| 上线 | `pub` / `publish` 等同步，不适用上述等待超时 |

连接类参数忽略列表与 familiar-cli spec §5.2 一致（MQTTX / rabbitmqadmin 同名连接选项）。

### 6.5 文案禁忌

- 不出现内部实现代号、迁移说明、已废弃自研语法对照  
- 「未支持」只对照 **真实 MQTTX / rabbitmqadmin** 能力（例如 `get` 的 `ackmode`、`show`/`close`、未列入的 MQTTX 选项）  
- 不把非该 CLI 的旗标当作用户必读「禁止项」

## 7. 实现范围

| 文件 | 变更 |
|------|------|
| `sql/templates/sqlquery.html` | MQTT/RabbitMQ 帮助面板 HTML、radio、`engineDisplayConfig`、Tab add/remove |
| `sql/templates/sqlsubmit.html` | 帮助 Tab 容器 + 同构面板与显隐 JS |

无后端、无迁移、无强制单测；手工验收即可。

## 8. 验收标准

1. 查询页选 `mqtt` / `rabbitmq` 实例 → 出现对应帮助 Tab；选 MySQL/Redis → MQ 帮助消失且不与 Redis 帮助并存错误。  
2. 上线页选 MQTT/RabbitMQ → 出现帮助 Tab，分组与示例与查询页全文一致。  
3. 每个**已支持**分组均有按行可复制示例；示例命令可被当前解析器接受（连接旗标可忽略的那些除外语义仍为「可粘贴」）。  
4. `sub`/`get` 分组写明 SysConfig 超时项名与默认/硬顶。  
5. `show`/`close`（及 MQTT「其它」）标明未支持；`list queues` 说明 Management API 现状。  
6. 执行路径不变：查询页仍拒写、上线页仍拒只读（帮助仅文档，不放宽校验）。

## 9. 测试计划

- 手工：上述验收 1–6  
- 回归：Redis 帮助 Tab、Mongo 上线提示、MQ 异步 `sub`/`get` 仍可用  

## 10. 开放决策

无。方案、页面范围、全文双页、分组表、示例下限与超时表述均已在设计讨论中确认。
