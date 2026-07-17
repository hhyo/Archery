# WSL 消息队列测试环境

本目录用于验证 Archery 的 RabbitMQ（AMQP）和 EMQX（MQTT）连接。以下账号和密码仅供本机测试，不得用于生产环境。

## 启动容器

在 Windows PowerShell 中进入仓库后，通过 WSL 启动 Docker 和已有容器：

```bash
wsl -u root -e bash -lc 'systemctl start docker'
wsl -e bash -lc 'docker start rabbitmq_3_13 emqx 2>/dev/null || true; docker ps --filter name=rabbitmq_3_13 --filter name=emqx --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
```

预期容器均为 `Up`，RabbitMQ 暴露 `5672`，EMQX 暴露 `1883`。

## 明文测试连接参数

本次验收使用：

| 服务 | 主机/端口 | 用户 | 密码 | vhost / 认证模式 |
| --- | --- | --- | --- | --- |
| RabbitMQ | `127.0.0.1:5672` | `archery_test` | `ArcheryTest1!` | `/` |
| EMQX | `127.0.0.1:1883` | 空 | 空 | 允许匿名 |

查看 RabbitMQ 用户：

```bash
docker exec rabbitmq_3_13 rabbitmqctl list_users
```

若需重新创建专用测试用户：

```bash
docker exec rabbitmq_3_13 rabbitmqctl add_user archery_test 'ArcheryTest1!'
docker exec rabbitmq_3_13 rabbitmqctl set_permissions -p / archery_test '.*' '.*' '.*'
docker exec rabbitmq_3_13 rabbitmqctl set_user_tags archery_test administrator
```

如果 `/` 尚不存在，先运行：

```bash
docker exec rabbitmq_3_13 rabbitmqctl add_vhost /
```

EMQX 当前 `1883` 监听允许匿名连接，因此 `MQTT_USER` / `MQTT_PASS` 均为空。若关闭匿名访问，应在 EMQX 中创建测试用户，并把用户名密码分别设置为 `ARCHERY_TEST_MQTT_USER` 和 `ARCHERY_TEST_MQTT_PASSWORD`。

## 运行明文认证验收

先在 WSL 安装依赖：

```bash
pip3 install pika paho-mqtt
```

若发行版启用了 PEP 668，可改用虚拟环境，或仅在本地测试环境执行：

```bash
python3 -m pip install --user --break-system-packages pika paho-mqtt
```

从仓库根目录运行：

```bash
export ARCHERY_TEST_RABBITMQ_USER=archery_test
export ARCHERY_TEST_RABBITMQ_PASSWORD='ArcheryTest1!'
export ARCHERY_TEST_RABBITMQ_VHOST=/
unset ARCHERY_TEST_MQTT_USER ARCHERY_TEST_MQTT_PASSWORD
python3 scripts/mq_env/verify_auth.py
```

打印 `OK rabbitmq ...` 和 `OK mqtt ...` 且退出码为 `0` 即通过。

## 生成并配置测试证书

证书和私钥写入已被 `.gitignore` 忽略的目录：

```bash
bash scripts/mq_env/gen_certs.sh
```

默认输出到 `docs/superpowers/testdata/mq-certs/`，包含 CA、服务端证书和客户端证书。私钥不得提交到 Git。

RabbitMQ 可把该目录只读挂载到容器后，在 `rabbitmq.conf` 中配置：

```ini
listeners.ssl.default = 5671
ssl_options.cacertfile = /certs/ca.crt
ssl_options.certfile = /certs/server.crt
ssl_options.keyfile = /certs/server.key
ssl_options.verify = verify_peer
ssl_options.fail_if_no_peer_cert = false
```

EMQX 5.1 可把证书目录只读挂载到容器后，在 `emqx.conf` 中配置：

```hocon
listeners.ssl.default {
  bind = "0.0.0.0:8883"
  ssl_options {
    cacertfile = "/certs/ca.crt"
    certfile = "/certs/server.crt"
    keyfile = "/certs/server.key"
    verify = verify_peer
    fail_if_no_peer_cert = false
  }
}
```

重建或重启容器使配置生效。脚本生成的服务端证书 CN 为 `localhost`，TLS 验证时应使用 `localhost`：

```bash
python3 scripts/mq_env/verify_auth.py --tls \
  --amqp-host localhost --mqtt-host localhost \
  --amqp-port 5671 --mqtt-port 8883 \
  --ca docs/superpowers/testdata/mq-certs/ca.crt \
  --cert docs/superpowers/testdata/mq-certs/client.crt \
  --key docs/superpowers/testdata/mq-certs/client.key
```

当前容器尚未挂载这套测试 CA/证书；完成上述 TLS 监听配置前，明文用户名密码验收是本任务的硬门禁。

## Archery 实例配置示例

在 Django Admin（**实例配置**）中新增实例时，**数据库类型** 选择 `MQTT` 或 `RabbitMQ`。下列字段与 `sql/models.py` 中 `Instance` 模型一致；证书三字段在 Admin 中可见（`client_key` 为密码框，`client_cert` / `ca_cert` 为多行文本）。

### RabbitMQ（明文 AMQP）

| 字段 | 值 |
| --- | --- |
| 实例名称 | `rabbitmq_local`（任意唯一名） |
| 实例类型 | 主库 |
| 数据库类型 | `RabbitMQ` |
| 实例连接 | `127.0.0.1` |
| 端口 | `5672` |
| 用户名 | `archery_test` |
| 密码 | `ArcheryTest1!` |
| 是否启用 SSL | 否 |
| 数据库（vhost） | `/` |
| 客户端证书 / 客户端密钥 / CA 证书 | 留空 |

保存后点击 **测试连接**，应返回成功。

**必做：实例标签 + 资源组。** SQL 在线查询按标签 `can_read` 拉实例，SQL 上线按 `can_write` 拉实例。新建实例后须在 Admin 勾选这两个标签，并把实例（及当前用户）关联到同一资源组；否则两个页面的「选择实例」下拉会为空。本地一键种子脚本 `setup_local.py` 已自动打标签并关联资源组 `mq-test`。

### MQTT（匿名 EMQX）

| 字段 | 值 |
| --- | --- |
| 实例名称 | `mqtt_local`（任意唯一名） |
| 实例类型 | 主库 |
| 数据库类型 | `MQTT` |
| 实例连接 | `127.0.0.1` |
| 端口 | `1883` |
| 用户名 / 密码 | 留空（EMQX 当前允许匿名） |
| 是否启用 SSL | 否 |
| 数据库 | `default`（或留空，引擎默认 `default`） |
| 客户端证书 / 客户端密钥 / CA 证书 | 留空 |

### mTLS（证书环境就绪后）

完成上文 **生成并配置测试证书** 与 broker TLS 监听（RabbitMQ `5671`、EMQX `8883`）后，在实例上额外设置：

| 字段 | RabbitMQ | MQTT |
| --- | --- | --- |
| 是否启用 SSL | 是 | 是 |
| 是否验证服务端 SSL 证书 | 按需（测试 CA 建议开启） | 同左 |
| 端口 | `5671` | `8883` |
| CA 证书 | 粘贴 `ca.crt` PEM 全文 | 同左 |
| 客户端证书 | 粘贴 `client.crt` PEM 全文 | 同左 |
| 客户端密钥 | 粘贴 `client.key` PEM 全文 | 同左 |

`client_cert` 与 `client_key` 必须成对填写；仅有其一会在建连前报错。用户名密码可与 mTLS 同时使用。

**当前状态**：测试证书已可生成，但容器尚未挂载并启用 `5671` / `8883` 的测试 CA 监听；mTLS 实例验收为后续跟进项，明文实例应先通过。

### 查询页命令示例（只读 / 短拉取）

详见下文 **「指令级测试用例」**。

### 上线工单命令示例（写命令）

详见下文 **「指令级测试用例」**。

## 指令级测试用例（输入 → 预期）

公共前置：

| 项 | 值 |
| --- | --- |
| 查询页 | 实例 `rabbitmq_local` 库 `/`，或 `mqtt_local` 库 `default` |
| 上线页 | 资源组先选 `mq-test`，再选同上实例/库 |
| 登录 | `archer` / `archer` |

说明：查询页「拦截」指提交后提示类似 **禁止执行该命令！**（`bad_query`）；上线「检测失败」指检测结果 `errlevel=2`，文案为 **禁止使用查询命令！** 或 **禁止执行该命令！**。

---

### A. 在线查询 · RabbitMQ（实例 `rabbitmq_local`，库 `/`）

| # | 输入（整行粘贴） | 预期结果 |
| --- | --- | --- |
| A1 | `help` | 成功。结果表列名 `命令`，含 `get queue=<name> [count=N]`、`list queues`、`publish …`、`declare …`、`purge …`、`delete …`、`help` 等 rabbitmqadmin 子集示例。 |
| A2 | `list queues` | 失败，错误含 `list queues 需要 RabbitMQ Management API`（说明已连上 broker，但 v1 未启用 Mgmt API）。 |
| A3 | `get queue=archery_test_queue count=1` | **异步**长等待。**队列空**：默认约 60s 后 0 行，warning 含「获取等待 … 秒超时，未收到消息」。**队列有消息**（先跑 B2）：1 行，列 `queue` / `routing_key` / `body`；`body` 含写入内容；消息会被 ack 消费掉。 |
| A4 | `publish routing_key=archery_test_queue payload="x"` | **拦截**：禁止执行该命令！（查询白名单不含写命令） |
| A5 | `declare queue name=archery_test_queue` | **拦截**：禁止执行该命令！ |
| A6 | `get` | **拦截**：格式错误（如 `get requires queue`）。 |
| A7 | `basic_get archery_test_queue` | **拦截**：旧 DSL，无法解析 / 禁止执行。 |
| A8 | `SELECT 1` | **拦截**：禁止执行该命令！ |

推荐顺序：A1 → A4（确认拦截）→ 上线 B2 建队写入 → 回查询 A3。

---

### B. SQL 上线 · RabbitMQ（资源组 `mq-test`，实例 `rabbitmq_local`，库 `/`）

检测通过后审核/执行；本地 `Q_CLUSTER.sync=True` 时可能自动通过，以实际 UI 为准。

| # | 工单 SQL 内容（可多行） | 检测预期 | 执行预期 |
| --- | --- | --- | --- |
| B1 | `declare queue name=archery_test_queue` | 通过：`Audit completed`，提示「暂不支持显示影响行数」 | 成功：`Execute Successfully`；broker 上出现队列 `archery_test_queue`。 |
| B2 | ```text
declare queue name=archery_test_queue
publish routing_key=archery_test_queue payload="hello from archery"
``` | 两行均通过 | 两行均 `Execute Successfully`；向默认 exchange 按 routing_key=`archery_test_queue` 投递 body=`hello from archery`。 |
| B3 | `publish routing_key=archery_test_queue payload="msg-2"` | 通过 | 成功；查询页再 `get queue=archery_test_queue count=1` 可读到 `msg-2`（若队列未被别的消费者掏空）。 |
| B4 | `declare exchange name=archery_test_ex type=topic` | 通过 | 成功；创建 topic 类型交换机（省略 type 时默认 `direct`）。 |
| B5 | ```text
declare queue name=archery_test_q2
declare binding queue=archery_test_q2 exchange=archery_test_ex routing_key=archery.rk
publish exchange=archery_test_ex routing_key=archery.rk payload="bound-msg"
``` | 三行均通过（需先有 B4 的 exchange，或本工单前加 `declare exchange`） | 全部成功；向绑定队列投递。 |
| B6 | `purge queue name=archery_test_queue` | 通过 | 成功；队列消息被清空。 |
| B7 | `delete queue name=archery_test_q2` | 通过 | 成功；队列删除（勿删仍要继续测的 `archery_test_queue`，或测完再删）。 |
| B8 | `get queue=archery_test_queue count=1` | **失败**：`Audit failed`，**禁止使用查询命令！** | 不应执行 |
| B9 | `help` | **失败**：禁止使用查询命令！ | 不应执行 |
| B10 | `sub -t archery/test` | **失败**：禁止执行该命令！（非写白名单） | 不应执行 |
| B11 | `publish routing_key=archery_test_queue` | **失败**：禁止执行该命令！（缺 `payload=`） | 不应执行 |

`publish` 格式（上线，rabbitmqadmin 风格）：

```text
publish routing_key=<name> payload=<body> [exchange=<name>]
```

默认交换机投递到队列：省略 `exchange=`（内部默认 `""`），`routing_key` 用队列名。

---

### C. 在线查询 · MQTT（实例 `mqtt_local`，库 `default`）

| # | 输入 | 预期结果 |
| --- | --- | --- |
| C1 | `help` | 成功。列 `命令`，3 行：`sub -t <topic> [-q N] [-C N]`、`pub -t <topic> -m <payload> [-q N]`、`help`。 |
| C2 | `sub -t archery/test -C 10` | **异步**长等待。列 `topic` / `payload` / `qos` / `retain`。**窗口内无消息**：默认约 60s 后 0 行，warning 含「订阅等待 … 秒超时，未收到消息」。**有消息**（先跑 D1 或外部发布）：最多 10 行，`topic` 匹配，`payload` 为消息体。 |
| C3 | `sub -t archery/test` | 成功；默认 `-C 10`（行为同 C2）。 |
| C4 | `sub -t archery/test -C 2` | 成功；最多收 2 条（`-C` 硬上限 100）。 |
| C5 | `pub -t archery/test -m "x"` | **拦截**：禁止执行该命令！ |
| C6 | `sub` | **拦截**：格式错误（如 `missing topic value` / `unknown mqtt action`）。 |
| C7 | `sub -t archery/test -C 0` | **拦截**：格式或数值错误。 |
| C8 | `help foo` | **拦截**：格式错误（`unknown flag: foo` 一类）。 |
| C9 | `get queue=q` | **拦截**：禁止执行该命令！ |

有消息验证建议：先提交上线 D1，再立刻在查询页跑 C2（订阅窗口内发消息更稳：先开 C2，另开上线 D1 或外部 `mqttx pub` / `mosquitto_pub`）。

---

### D. SQL 上线 · MQTT（资源组 `mq-test`，实例 `mqtt_local`，库 `default`）

| # | 工单 SQL 内容 | 检测预期 | 执行预期 |
| --- | --- | --- | --- |
| D1 | `pub -t archery/test -m "hello from archery"` | 通过：`Audit completed`，「暂不支持显示影响行数」 | 成功：`Execute Successfully`；topic=`archery/test`，payload 如上，默认 qos=0。 |
| D2 | `pub -t archery/test -m "qos-one" -q 1` | 通过 | 成功；qos=1 发布。 |
| D3 | ```text
pub -t archery/test -m "line-1"
pub -t archery/test -m "line-2" -q 0
``` | 两行均通过 | 两行均执行成功。 |
| D4 | `sub -t archery/test -C 10` | **失败**：禁止使用查询命令！ | 不应执行 |
| D5 | `help` | **失败**：禁止使用查询命令！ | 不应执行 |
| D6 | `pub -t archery/test` | **失败**：禁止执行该命令！（缺 `-m`） | 不应执行 |
| D7 | `pub -t archery/test -m "x" -q 9` | **失败**：禁止执行该命令！（qos 非法；合法为 0/1/2） | 不应执行 |
| D8 | `declare queue name=x` | **失败**：禁止执行该命令！ | 不应执行 |

`pub` 格式（上线，MQTTX 风格）：

```text
pub -t <topic> -m <payload> [-q N]
```

`-q` 可选，默认 `0`，仅允许 `0` / `1` / `2`。

---

### E. 推荐最小回归路径（约 10 分钟）

1. 查询 RabbitMQ：`help`（A1）→ `publish routing_key=… payload=…` 应拦截（A4）
2. 上线 RabbitMQ：粘贴 B2 整段 → 检测通过 → 执行成功
3. 查询 RabbitMQ：`get queue=archery_test_queue count=1`（A3 读到 `hello from archery`）
4. 查询 MQTT：`help`（C1）→ `pub -t … -m …` 应拦截（C5）
5. 上线 MQTT：D1 → 执行成功
6. 查询 MQTT：`sub -t archery/test`（C2/C3；若空结果可再发一条 D1 后立刻订阅）
7. 上线反向：B8、D4 检测失败

命令速查（连接参数取自实例，命令中可省略 host/port/user）：

```text
sub -t archery/test
pub -t archery/test -m "hello from archery"
get queue=archery_test_queue count=1
publish routing_key=archery_test_queue payload="hello from archery"
```

### 可选：引擎集成冒烟测试

Archery 进程需能访问 WSL 内 broker（`127.0.0.1` 或 WSL IP）。在仓库根目录：

```bash
export ARCHERY_TEST_RABBITMQ_USER=archery_test
export ARCHERY_TEST_RABBITMQ_PASSWORD='ArcheryTest1!'
export ARCHERY_TEST_RABBITMQ_VHOST=/
unset ARCHERY_TEST_MQTT_USER ARCHERY_TEST_MQTT_PASSWORD
pytest sql/engines/test_mq_integration.py -v
```

有 broker 且无密码缺失时明文用例应 PASS；mTLS 用例在 `ARCHERY_TEST_MQ_CA/CERT/KEY` 与 TLS 端口未就绪时按预期 skip。

## 手工 UI 测试步骤（明文，推荐按此顺序）

以下假设已用 `setup_local.py` 种子过（用户 `archer`、资源组 `mq-test`、实例 `mqtt_local` / `rabbitmq_local`，且已打 `can_read` + `can_write` 标签）。

### 0. 启动依赖

在 Windows PowerShell：

```powershell
# 1) 启动 broker
wsl -u root -e bash -lc 'systemctl start docker'
wsl -e bash -lc 'docker start rabbitmq_3_13 emqx 2>/dev/null; docker ps --filter name=rabbitmq_3_13 --filter name=emqx --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'

# 2)（可选）确认明文连接
wsl -e bash -lc "cd /mnt/e/github/Archery; source .venv-mq/bin/activate; export ARCHERY_TEST_RABBITMQ_USER=archery_test ARCHERY_TEST_RABBITMQ_PASSWORD='ArcheryTest1!' ARCHERY_TEST_RABBITMQ_VHOST=/; unset ARCHERY_TEST_MQTT_USER ARCHERY_TEST_MQTT_PASSWORD; python3 scripts/mq_env/verify_auth.py"

# 3) 若尚未种子或实例下拉为空，重新种子（会补 can_read/can_write）
wsl -e bash -lc 'cd /mnt/e/github/Archery; source .venv-mq/bin/activate; export PYTHONPATH=/mnt/e/github/Archery SECRET_KEY=local-mq-test-secret-key-change-me-please-32chars-plus; python scripts/mq_env/setup_local.py'

# 4) 启动 Archery（另开一个窗口保持运行）
wsl -e bash -lc 'bash /mnt/e/github/Archery/scripts/mq_env/start_runserver.sh'
```

浏览器打开：<http://127.0.0.1:8000/login/>  
账号：**`archer` / `archer`**

### 1. 确认实例标签与连通（约 2 分钟）

1. 打开 <http://127.0.0.1:8000/admin/sql/instance/>（或菜单 **实例管理**）。
2. 点开 `mqtt_local`、`rabbitmq_local`，确认：
   - 已关联资源组 **`mq-test`**
   - 标签勾选 **`支持查询 (can_read)`**、**`支持上线 (can_write)`**
3. 对两个实例分别点 **测试连接**，应成功。  
   失败时先看第 0 步容器是否 `Up`、端口 `5672` / `1883`、RabbitMQ 用户是否为 `archery_test`。

### 2. SQL 在线查询（只读 / 短拉取）

1. 打开菜单 **SQL 查询**（路径一般为 `/sqlquery/`）。
2. **选择实例** 下拉应能看到：
   - `mqtt_local`（类型 MQTT）
   - `rabbitmq_local`（类型 RabbitMQ）  
   若为空：回到步骤 1 检查标签；或重跑 `setup_local.py` 后强制刷新页面（Ctrl+F5）。
3. 选 **`rabbitmq_local`** → **选择数据库** 应为 **`/`**。
4. 在编辑器执行（逐条）：

```text
help
list queues
get queue=archery_test_queue count=1
```

预期：`help` 有 rabbitmqadmin 子集说明；`list queues` 报 Mgmt API 未启用或 `get` 异步等待后返回（队列不存在时可能 0 行 + 超时 warning）。

5. 同页执行写命令，应被拦截：

```text
publish routing_key=archery_test_queue payload="forbidden-on-query-page"
```

6. 改选 **`mqtt_local`** → 数据库 **`default`**，执行：

```text
help
sub -t archery/test -C 10
```

预期：异步短订阅后返回（可能 0 条消息）；再执行 `pub -t archery/test -m "x"` 应被拦截。

### 3. SQL 上线（写命令工单）

> **按钮说明（易踩坑）**：「SQL提交」默认是灰色不可点的，这是产品设计，不是 MQTT bug。必须先填齐表单并点红色 **「SQL检测」**，检测接口成功返回后，「SQL提交」才会变绿可点。检测后若再改编辑器内容，提交按钮会再次灰掉，需重新检测。

必填项（缺一则点「SQL检测」会弹窗，提交按钮一直灰）：

| 字段 | 说明 |
| --- | --- |
| 上线单名称 | 必填，&lt;50 字 |
| 资源组 | `mq-test` |
| 实例 / 数据库 | `mqtt_local` + `default` 或 `rabbitmq_local` + `/` |
| 审批流程 | 选组后应显示审批组名；若提示「请配置审批流程」，说明资源组未配 WorkflowAuditSetting（`setup_local.py` 会创建权限组 `mq-approver` 并挂到 `mq-test`） |
| 可执行时间 | 可选；若填写，起止间隔须 ≥ 60 分钟 |

1. 打开菜单 **SQL 上线**（路径一般为 `/submitsql/`）。
2. 填写上线单名称，**资源组** 选 **`mq-test`**（必须先选组，实例下拉才会加载；并应出现审批流程展示）。
3. **选择实例** 应出现 `mqtt_local` / `rabbitmq_local`；库名同上（`/` 或 `default`）。
4. 输入命令后先点 **SQL检测**，表格出现且审核状态为 pass，再点 **SQL提交**。
5. **RabbitMQ 工单**：实例 `rabbitmq_local`，库 `/`，SQL 内容：

```text
declare queue name=archery_test_queue
publish routing_key=archery_test_queue payload="hello from archery"
```

提交 → 审核通过 → 执行，应成功。

5. **MQTT 工单**：实例 `mqtt_local`，库 `default`，SQL 内容：

```text
pub -t archery/test -m "hello from archery"
```

提交 → 审核通过 → 执行，应成功。

6. 反向校验：在上线工单里提交只读命令（如 `get queue=… count=1` 或 `sub -t …`），审核/检测阶段应拒绝。

> 本地 `Q_CLUSTER.sync=True` 时审批流可能自动通过或同步执行，以你环境实际弹窗为准；关键是写命令能跑通、只读命令在上线路径被拒。

### 4. 查询 ↔ 上线串联（可选）

1. 用步骤 3 的 RabbitMQ `publish routing_key=…` 写入一条消息。
2. 回到 **SQL 查询**，对同一实例执行 `get queue=archery_test_queue count=1`，应能读到刚写入的内容（或至少不再是“永远连不上”）。
3. MQTT：一边用外部工具或另开终端往 `archery/test` 发消息，一边在查询页 `sub -t archery/test -C 10`，应能短拉取到。

### 5. mTLS（证书环境就绪后再做）

见上文「生成并配置测试证书」与验收清单第 5 项；当前容器默认未开 `5671`/`8883`，可跳过。

## 手工验收清单

按顺序勾选；前四项为明文环境必做，第五项在 TLS 监听与证书挂载完成后执行。

- [ ] **0. 环境就绪** — broker Up；`verify_auth.py` 打印 OK；Archery 已启动；`archer` 可登录。
- [ ] **1. 实例标签与连通** — 两实例有 `can_read`/`can_write` + 资源组 `mq-test`；测试连接成功。
- [ ] **2. 查询页下拉有数据** — 能选到实例与库（`/` / `default`）。
- [ ] **3. 查询页只读成功、写命令被拒** — RabbitMQ `get queue=…` / `list queues`；MQTT `sub -t …`；`pub` / `publish` 被拦截。
- [ ] **4. 上线工单写命令成功** — 先选 `mq-test`；RabbitMQ `declare`+`publish`；MQTT `pub -t … -m …`；工单内只读命令被拒。
- [ ] **5. （可选）串联验证** — 上线写入后查询页能读到。
- [ ] **6. （证书环境就绪时）mTLS** — 见上文 TLS 说明。
