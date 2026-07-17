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
