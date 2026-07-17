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

在 Archery **SQL 查询** 页选择对应实例与逻辑库后执行：

**RabbitMQ**（允许 `basic_get`、`get`、`queue_declare_passive`、`help`）：

```text
queue_declare_passive archery_test_queue
basic_get archery_test_queue
help
```

**MQTT**（允许 `subscribe`、`help`）：

```text
subscribe archery/test 3 10
help
```

查询页执行写命令应被拦截，例如：

```text
publish "" archery_test_queue "forbidden-on-query-page"
publish archery/test "forbidden-on-query-page"
```

### 上线工单命令示例（写命令）

通过 **SQL 上线** 提交工单；审核通过后执行。

**RabbitMQ**（允许 `publish`、`queue_declare`、`exchange_declare`、`queue_bind`、`purge` / `queue_purge`、`queue_delete`）：

```text
queue_declare archery_test_queue
publish "" archery_test_queue "hello from archery"
```

**MQTT**（允许 `publish`）：

```text
publish archery/test "hello from archery"
```

工单中提交只读命令应被拒绝（如 `basic_get`、`subscribe`）。

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

## 手工验收清单

按顺序勾选；前四项为明文环境必做，第五项在 TLS 监听与证书挂载完成后执行。

- [ ] **1. Admin 可创建实例** — 在 **实例配置** 中分别新建 `db_type=MQTT` 与 `db_type=RabbitMQ` 实例，字段按上文示例填写并保存无报错。
- [ ] **2. 测试连通成功** — 两个实例均点击 **测试连接**，返回成功（失败时先确认 Docker 容器 Up、端口与凭据一致）。
- [ ] **3. 查询页只读 / 短拉取成功，写命令被拒** — RabbitMQ 执行 `basic_get` 或 `queue_declare_passive` 有结果或空结果；MQTT 执行 `subscribe archery/test 3 10` 能短拉取；同页执行 `publish ...` 被拦截并提示禁止。
- [ ] **4. 上线工单写命令成功** — RabbitMQ 工单 `queue_declare` + `publish` 执行成功；MQTT 工单 `publish archery/test "..."` 执行成功；工单内 `basic_get` / `subscribe` 在审核阶段被拒绝。
- [ ] **5. （证书环境就绪时）mTLS 连通成功** — 实例启用 SSL 并填写 CA / 客户端证书与密钥；RabbitMQ `5671`、EMQX `8883` 使用测试 CA 监听后，**测试连接**、查询短拉取与工单写命令均成功；或 `verify_auth.py --tls` 与 `test_mq_integration.py` 中 mTLS 用例 PASS 而非 skip。
