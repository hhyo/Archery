# MQ mTLS 冒烟测试设计

## 背景

当前本地测试环境已运行 MySQL、EMQX、RabbitMQ、Redis、goInception 和 Archery。现有 `mqtt_local`、`rabbitmq_local` 与 `local-mysql` 实例均使用明文连接，证书字段为空。

已探测到：

- EMQX 暴露 `1883` 和 `8883`，但 `8883` 当前只提供服务端 TLS，不校验客户端证书。
- RabbitMQ 只监听并暴露 `5672`，尚未启用或映射 `5671`。
- `scripts/mq_env/certs/` 已有本地 CA、服务端证书和客户端证书，但尚未挂载到 broker，也未写入 Archery Instance。

本设计用于验证 MySQL、MQTT 和 RabbitMQ 的 SQL 查询与 SQL 上线流程，并重点验证 MQTT、RabbitMQ 的“受信客户端证书 + 用户名密码”双重认证路径。

## 目标

1. 在改造前验证现有明文环境的查询与上线基线。
2. 仅调整本地测试环境和测试实例配置，使 MQTT、RabbitMQ 强制使用 mTLS 和用户名密码。
3. 用可重复脚本覆盖连通性、正例、负例和引擎级回归。
4. 用浏览器覆盖真实的 SQL 查询与 SQL 上线用户路径。
5. 区分环境配置问题与 Archery 引擎缺陷。

## 非目标

- 不修改生产部署配置。
- 不为 MySQL 增加 TLS。
- 不覆盖 SSH 隧道或 TLS SNI 场景。
- 不默认修改 MQTT/RabbitMQ 引擎业务代码；冒烟发现的真实缺陷另行记录和修复。
- 不将本地证书、私钥、密码或 `scripts/mq_env/` 下的本地测试产物提交到 Git。

## 总体方案

采用“先跑明文基线，再切换现有实例到 mTLS，最后做脚本与 UI 双通道验收”的方案。

不新增并行的 TLS Instance。`mqtt_local` 和 `rabbitmq_local` 在明文基线完成后直接切换到 TLS，减少测试实例数量，确保 UI 验收使用的就是最终配置。

## 阶段一：明文基线

使用当前配置：

- MySQL：`local-mysql:3306`
- MQTT：`mqtt_local:1883`
- RabbitMQ：`rabbitmq_local:5672`

先通过脚本验证连接，再在 UI 中验证 SQL 查询与 SQL 上线。基线结果用于判断后续失败来自环境切换还是既有功能。

## 阶段二：Broker mTLS 改造

### EMQX

- 使用 `scripts/mq_env/certs/` 中的 CA、服务端证书和服务端私钥配置 `8883`。
- 将客户端校验设为 `verify_peer`。
- 将缺少客户端证书时的行为设为拒绝连接。
- 为 MQTT 创建本地测试用户，并关闭该 TLS 监听器上的匿名访问。
- `1883` 可以保留用于诊断，但切换后不再作为正式冒烟入口。

### RabbitMQ

- 使用同一套本地测试 CA 和服务端证书启用 AMQPS。
- 在容器内监听 `5671`，并映射到宿主机 `5671`。
- 要求客户端提供受该 CA 信任的证书。
- 保留现有 `archery_test` 用户及其 vhost 权限。
- `5672` 可以保留用于诊断，但切换后不再作为正式冒烟入口。

### 安全边界

- MQTT 和 RabbitMQ 均要求客户端证书与用户名密码同时有效。
- 缺少证书、缺少账号、错误密码任一情况都必须连接失败。
- 服务端证书的 SAN 必须包含 Instance 实际连接地址（本地测试为 `127.0.0.1`）；不通过关闭 `verify_ssl` 绕过主机名校验。
- 证书、私钥和测试密码仅存于已忽略的本地测试目录及本地数据库，不写入设计文档或 Git。

## 阶段三：Archery Instance 切换

明文基线通过后，直接改写现有实例：

### `mqtt_local`

- 端口改为 `8883`
- 设置 `is_ssl=True`
- 设置 `verify_ssl=True`
- 写入 `ca_cert`、`client_cert` 和 `client_key`
- 设置 MQTT 测试用户名和密码

### `rabbitmq_local`

- 端口改为 `5671`
- 设置 `is_ssl=True`
- 设置 `verify_ssl=True`
- 写入 `ca_cert`、`client_cert` 和 `client_key`
- 保留 RabbitMQ 测试用户名、密码和 vhost

### `local-mysql`

保持明文配置不变，作为非 MQ 对照组。

实例切换脚本应可重复执行，并从 `scripts/mq_env/certs/` 读取 PEM 内容。脚本只负责本地测试状态切换，不提交敏感材料。

## 执行分工

### 脚本

脚本负责测试广度、负例和可重复性：

1. 复用或扩展 `scripts/mq_env/verify_auth.py`，验证 TLS、CA、客户端证书、客户端私钥与用户名密码组合。
2. 提供幂等的实例切换能力，将现有 MQTT、RabbitMQ Instance 从明文切换到 mTLS。
3. 直接调用 MQTT、RabbitMQ 引擎的连接、查询、审核和执行入口，证明从 Instance 读取证书的完整路径可用。
4. 覆盖缺客户端证书、缺用户名密码和错误密码等负例。

### UI

UI 负责真实用户路径：

1. 在 SQL 查询页分别选择 MySQL、MQTT 和 RabbitMQ 实例执行测试命令。
2. 在 SQL 上线页提交 MQTT、RabbitMQ 写命令，完成审核和执行。
3. 核对结果状态、错误提示和结果表格是否与脚本结论一致。
4. 保留关键步骤截图并汇总冒烟结果。

## 验收矩阵

| 引擎 | 明文基线 | mTLS + 账密 | SQL 查询 | SQL 上线 |
| --- | --- | --- | --- | --- |
| MySQL | 必测 | 不适用 | `select 1` 或等价查询 | 安全、可回滚或幂等的测试 SQL |
| MQTT | 必测 | 必测 | `help`、短超时 `sub` | `pub` 工单审核并执行 |
| RabbitMQ | 必测 | 必测 | `help` 或等价只读命令 | `declare queue` 或等价写命令 |

mTLS 阶段还必须执行以下脚本负例：

| 场景 | 预期结果 |
| --- | --- |
| 无客户端证书，账号正确 | TLS 连接失败 |
| 客户端证书正确，无账号 | 认证失败 |
| 客户端证书正确，密码错误 | 认证失败 |
| 客户端证书与账号密码均正确 | 查询和上线成功 |

## 执行顺序

1. 脚本验证明文连接和引擎基线。
2. UI 抽检明文 SQL 查询与 SQL 上线。
3. 配置 broker mTLS，并切换现有 Instance。
4. 脚本验证 mTLS 正例、负例和引擎完整路径。
5. UI 抽检 mTLS SQL 查询与 SQL 上线。
6. 汇总结果、截图、环境阻塞和缺陷。

## 错误处理与归因

- TLS 端口未监听、证书未挂载或 broker 未强制客户端证书：判定为环境配置未完成。
- 原生客户端脚本无法连接：先判定 broker、证书或账号配置问题，不进入 UI 验收。
- 原生客户端成功，但 Archery 引擎失败：判定为候选引擎缺陷，保留异常和最小复现。
- 引擎脚本成功，但 UI 失败：判定为候选端到端或 UI 流程缺陷。
- 环境未就绪时，对应用例标记为 `blocked`，记录最短补齐步骤，不将其记为引擎失败。

## 通过标准

- 明文阶段：MySQL、MQTT、RabbitMQ 的查询与上线基线均通过。
- mTLS 阶段：MQTT、RabbitMQ 正例均通过，所有负例均按预期失败。
- MySQL 在 MQ 环境切换后仍可正常查询和上线。
- 脚本与 UI 对同一正例的成功或失败结论一致。
- 没有未解释的异常；所有失败均明确归类为环境阻塞或产品缺陷。

