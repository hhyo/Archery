from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUERY_TEMPLATE = ROOT / "sql" / "templates" / "sqlquery.html"
SUBMIT_TEMPLATE = ROOT / "sql" / "templates" / "sqlsubmit.html"

# Spec §6.2 / §6.3 示例下限 + 关键文案锚点（两页都必须出现）
REQUIRED_SNIPPETS = [
    # MQTT examples
    "sub -t demo/test",
    "sub -t demo/test -C 1",
    "sub -t demo/test -C 10",
    "sub -t demo/test -q 0 -C 5",
    "sub -t demo/test -q 1 -C 5",
    "sub -t demo/test -q 2 -C 1",
    "sub --topic demo/test --count 3",
    "mqttx sub -t demo/test -C 1",
    "mqttx -h 127.0.0.1 -p 1883 sub -t demo/test -C 1",
    "pub -t demo/test -m hello",
    'pub -t demo/test -m "hello from archery"',
    'pub -t demo/test -m "hello" -q 0',
    'pub -t demo/test -m "hello" -q 1',
    'pub --topic demo/test --message "hello" --qos 1',
    'mqttx pub -t demo/test -m "hello from archery"',
    'mqttx -h 127.0.0.1 -p 1883 pub -t demo/test -m "hi"',
    # RabbitMQ examples (rabbitmqadmin A-tier / official keys)
    "get queue=demo.q",
    "get queue=demo.q count=1",
    "get queue=demo.q count=5",
    "get queue=demo.q count=1 ackmode=ack_requeue_false",
    "rabbitmqadmin get queue=demo.q count=1",
    "rabbitmqadmin -H 127.0.0.1 -P 5672 -u guest -p guest get queue=demo.q count=1",
    "declare queue name=demo.q",
    "declare queue name=demo.q durable=true",
    "declare queue name=demo.q durable=false",
    "declare exchange name=demo.ex type=direct",
    "declare exchange name=demo.ex type=topic durable=true",
    "declare binding source=demo.ex destination=demo.q routing_key=demo.q",
    "publish routing_key=demo.q payload=hello",
    'publish routing_key=demo.q payload="hello from archery"',
    'publish routing_key=demo.q payload="hello" exchange=',
    'publish routing_key=demo.rk payload="hello" exchange=demo.ex',
    "purge queue name=demo.q",
    "delete queue name=demo.q",
    "delete exchange name=demo.ex",
    # Timeout / config
    "mq_query_timeout_default",
    "mq_query_timeout_max",
    # DOM anchors
    'id="mqtt_help"',
    'id="rabbitmq_help"',
    'id="mqttHelpSub"',
    'id="rabbitmqHelpGet"',
    "MQTT帮助文档",
    "RabbitMQ帮助文档",
    "本子集未支持",
    "ackmode",
    "ack_requeue_true",
    "ack_requeue_false",
    "reject_requeue_true",
    "reject_requeue_false",
]


def test_query_and_submit_contain_required_mq_help_snippets():
    query = QUERY_TEMPLATE.read_text(encoding="utf-8")
    submit = SUBMIT_TEMPLATE.read_text(encoding="utf-8")
    missing = []
    for snippet in REQUIRED_SNIPPETS:
        if snippet not in query:
            missing.append(f"sqlquery.html missing: {snippet!r}")
        if snippet not in submit:
            missing.append(f"sqlsubmit.html missing: {snippet!r}")
    assert not missing, "\n".join(missing)
