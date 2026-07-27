# MQTT/RabbitMQ PR 安全与 CI 修复设计

日期：2026-07-18  
状态：已批准（待实现）  
PR：https://github.com/hhyo/Archery/pull/3218  
前置规格：`2026-07-17-mqtt-rabbitmq-engine-design.md`、`2026-07-18-mq-familiar-cli-async-query-design.md`

## 1. 背景与目标

上游 PR 被 **lint (black)** 与 **Django CI** 挡住；CodeQL / Codex 指出多处本分支引入的安全与 MQ 质量问题。

**目标：** 在不改变其它数据库引擎行为的前提下，关闭 CI 门禁与约定范围内的安全/MQ 审查项。

**非目标：**

- 修改全局 `Q_CLUSTER.timeout` / `Q_CLUISTER_TIMEOUT` 默认值（master 现为 **60**；本分支未改 settings 中该默认）
- 升级或替换全仓 `mysqlclient` / `pymysql` 版本策略
- 保证上游 Maintainer 立刻合并（只保证检查与审查项可关闭）
- 新 DSL 或兼容已废弃的自定义命令

### 1.1 做法

采用 **外科式 MQ-only 补丁**：所有行为变更落在 `db_type in {mqtt, rabbitmq}`、MQ 专用模块，或对共享文件的显式 MQ 分支 / 密钥 write_only。

### 1.2 范围（A+）

| 类 | 项 |
|----|-----|
| CI | black 格式化本分支相关文件；删除 MQ 测试 conftest 中的 `pymysql.install_as_MySQLdb()` |
| 安全 | MQ job `query_priv_check`；`client_key`/`client_cert` API write_only；离线导出不再对 MQ 破坏性 `query`/`ack`；API 不回传原始 `str(exc)`；Explain 不对 MQ 跑活命令 |
| MQ 质量 | django-q per-task timeout vs MQ wait；rabbitmqadmin 行首连接选项静默忽略；`durable=` 传入 declare；不可路由 publish 不当成功 |

### 1.3 MySQLdb CI 根因（本分支引入）

- master Django CI 近期成功；本分支失败：`608 passed, 13 failed, 735 errors`。
- 栈：`pymysql/connections.py` 导入 `COMMAND`，但 `MySQLdb.constants` 指向已安装的 **mysqlclient** 路径 → 命名空间被 `pymysql.install_as_MySQLdb()` 污染。
- 来源：本分支新增的 `sql/services/conftest.py`、`sql_api/conftest.py` 在 import 时调用 shim；全量 pytest 加载后污染全局（含无关 `OIDCAuthTest`、`sql/tests.py`）。
- **修复：** 删除上述 shim；fixture 复用根 `conftest.py`；CI 继续使用 `mysqlclient`。本地 `manage.py` 的 PyMySQL shim 不得提交进本修复。

### 1.4 隔离硬规则

1. 行为变更仅当 `db_type in {mqtt, rabbitmq}`，或仅改 MQ 专用模块。
2. 共享文件只加 MQ 分支或密钥 write_only；默认路径保持现状。
3. 回归：MQ 单测 + 抽查非 MQ 用例不因 shim/共享改动失败。

## 2. 安全与权限

### 2.1 MQ 异步 job 权限

在 `create_mq_query_job` 中，`can_read` 实例校验之后、入队之前调用：

`query_priv_check(user, instance, db_name, sql_line, limit_num)`

- 将 `mqtt`/`rabbitmq` 并入 `query_privileges` 中与 `redis`/`mssql`/`pgsql` 相同的「仅校验当前选中库」分支。
- `status != 0` → 不创建 job；API 返回 403 + priv 的 `msg`（无 traceback）。
- 既有同步查询 priv 路径不改。

### 2.2 证书私钥不读回

仅改 `InstanceSerializer` / `InstanceDetailSerializer` 的 `extra_kwargs`：为 `client_key`、`client_cert`（及若存在的同类 PEM 字段）设置 `write_only=True`，与 `password` 一致。不改模型语义。

### 2.3 离线导出不再消费消息

`mqtt`/`rabbitmq` **不支持离线导出**：

- 从 `LINE_BASED_COMMAND_ENGINES` 移除二者（或保留拆行但禁止进入 count/`query`）。
- `pre_count_check` / 执行入口对这两种 `db_type` 直接失败并提示不支持。
- `redis`/`memcached` 路径不变。

### 2.4 API 错误信息（CodeQL）

MQ job 的 create/get/cancel：

- 已知业务 `ValueError` → 白名单/业务短中文 `msg`（不含栈与路径）。
- `PermissionError` / 未知异常 → 固定文案 + 服务端日志；响应不带原始 `str(exc)`。

### 2.5 Explain

- 前端：`isMqEngine` 时隐藏/禁用「执行计划」，点击提示不支持。
- 后端：若仍收到 explain 包装的 MQ 命令，在 MQ `query_check` 或同步入口拒绝。
- 其它库 explain 不动。

## 3. MQ 质量

### 3.1 django-q worker timeout vs MQ wait

- **不改** 全局 `Q_CLUSTER["timeout"]` 默认 60（与 master 一致）。
- MQ 等待默认 60 / 硬顶 3600 仍由 `mq_query_timeout_default` / `mq_query_timeout_max`（SysConfig）控制；早期短订阅硬顶 30s 已由熟悉 CLI 规格取代，**本次不改回 30**。
- 入队时尽量 `async_task(..., timeout=timeout_sec + 缓冲)`（若 django-q2 支持 per-task timeout）；不支持则入队前校验并在运维文档中要求 `Q_CLUISTER_TIMEOUT >= mq_query_timeout_max`。
- 保留现有 `Q_CLUSTER sync=True` 时的 daemon 线程方案，避免阻塞轮询。

### 3.2 rabbitmqadmin 行首连接选项

允许 `rabbitmqadmin [-H|-P|-V|-u|-p|--host=…] <action> …`：解析时 **静默忽略** 已知连接旗标及其参数值，连接仍只用 Instance。未知旗标报错。MQTT 侧若已有「忽略连接旗标」则对齐。

### 3.3 `durable=`

解析 `declare queue|exchange … durable=true|false`。未写 `durable` 时保持当前行为（不传或等价于现状，避免无谓变更已有声明语义）。写出时传入 `queue_declare` / `exchange_declare` 的 `durable=`。binding 无此参数。

### 3.4 不可路由 publish

写路径 `publish`：delivery confirm + `mandatory=True`；不可路由 / nack → 工单 `Execute Failed` 或查询结果 error。不得标成成功。

## 4. 落地文件与验收

### 4.1 预期文件

| 区域 | 文件 |
|------|------|
| CI shim | `sql/services/conftest.py`、`sql_api/conftest.py` |
| 权限 | `sql/services/mq_query_job.py`、`sql/query_privileges.py` |
| 密钥 | `sql_api/serializers.py` |
| 离线导出 | `sql/offlinedownload.py` |
| API 错误 | `sql_api/api_sqlquery.py` |
| Explain | `sql/templates/sqlquery.html` + MQ engine `query_check` |
| CLI/引擎 | `sql/engines/mq_cli.py`、`sql/engines/rabbitmq.py`（必要时 `mqtt.py`） |
| Job timeout | `sql/services/mq_query_job.py` |
| 格式 | black 触及的本分支文件 |
| 测试 | `test_mqtt` / `test_rabbitmq` / `test_mq_query_job*` 等增补 |

### 4.2 验收

1. `black --check` 对本分支相关文件通过。
2. 全量 Django CI 不再出现 `MySQLdb.constants.COMMAND` 污染导致的大面积 setup ERROR。
3. 无库权限用户无法创建 MQ `sub`/`get` job。
4. Instance API GET 不返回 `client_key`/`client_cert` 明文。
5. mqtt/rabbitmq 离线导出提交失败且不 `ack` 消息。
6. MQ Explain 前端不可用，后端拒绝。
7. `declare … durable=true` 生效；不可路由 `publish` 失败；行首 `-H` 等被忽略且仍用 Instance。
8. 抽查 mysql/redis 同步查询与既有单测无回归。
9. 全局 `Q_CLUISTER_TIMEOUT` 默认值仍为 60，与 master 一致。

## 5. 实现顺序建议

1. 去 conftest shim + black（先让 CI 可绿）
2. 安全五项（priv、serializer、offline、API 错误、explain）
3. MQ 质量四项（timeout 入队、旗标、durable、publish）
4. 补测与全量/定向回归

实现前另写 implementation plan（writing-plans），本文件只定设计。
