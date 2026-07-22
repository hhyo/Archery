# -*- coding: UTF-8 -*-
import pytest

from sql.engines.mq_cli import parse_mqtt_line, parse_rabbitmq_line, split_mq_lines


def test_split_skips_blank_and_hash_comments():
    assert split_mq_lines("# a\n\npub -t t -m m\n") == ["pub -t t -m m"]


def test_mqtt_pub_strips_mqttx_prefix_and_ignores_host():
    cmd = parse_mqtt_line(
        'mqttx pub -h 1.2.3.4 -p 1883 -t archery/test -m "hello" -q 1'
    )
    assert cmd.action == "pub"
    assert cmd.args == {"topic": "archery/test", "payload": "hello", "qos": 1}


def test_mqtt_sub_defaults():
    cmd = parse_mqtt_line("sub -t archery/test")
    assert cmd.action == "sub"
    assert cmd.args["topic"] == "archery/test"
    assert cmd.args["qos"] == 0
    assert cmd.args["count"] == 10


def test_mqtt_rejects_unknown_flag():
    with pytest.raises(ValueError):
        parse_mqtt_line("sub -t t --bench")


def test_rabbitmq_get_and_publish():
    g = parse_rabbitmq_line("rabbitmqadmin get queue=q1 count=3 -H 127.0.0.1")
    assert g.action == "get"
    assert g.args == {"queue": "q1", "count": 3, "ackmode": "ack_requeue_true"}
    p = parse_rabbitmq_line('publish routing_key=q1 payload="hi" exchange=')
    assert p.action == "publish"
    assert p.args["routing_key"] == "q1"
    assert p.args["payload"] == "hi"
    assert p.args.get("exchange", "") == ""


def test_rabbitmq_get_defaults_ackmode_and_count():
    g = parse_rabbitmq_line("get queue=q1")
    assert g.args["queue"] == "q1"
    assert g.args["count"] == 1
    assert g.args["ackmode"] == "ack_requeue_true"


@pytest.mark.parametrize(
    "ackmode",
    [
        "ack_requeue_true",
        "ack_requeue_false",
        "reject_requeue_true",
        "reject_requeue_false",
    ],
)
def test_rabbitmq_get_ackmodes(ackmode):
    g = parse_rabbitmq_line(f"get queue=q1 count=2 ackmode={ackmode}")
    assert g.args["ackmode"] == ackmode
    assert g.args["count"] == 2


def test_rabbitmq_get_rejects_requeue_flag():
    with pytest.raises(ValueError, match="ackmode"):
        parse_rabbitmq_line("get queue=q1 requeue=false")


def test_rabbitmq_get_rejects_payload_file_and_encoding():
    with pytest.raises(ValueError):
        parse_rabbitmq_line("get queue=q1 payload_file=x")
    with pytest.raises(ValueError):
        parse_rabbitmq_line("get queue=q1 encoding=auto")


def test_rabbitmq_list_and_close_unsupported():
    with pytest.raises(ValueError):
        parse_rabbitmq_line("list queues")
    with pytest.raises(ValueError):
        parse_rabbitmq_line("list exchanges")
    with pytest.raises(ValueError):
        parse_rabbitmq_line("close connection name=x")


def test_old_dsl_rejected():
    with pytest.raises(ValueError):
        parse_mqtt_line('publish archery/test "hello"')
    with pytest.raises(ValueError):
        parse_rabbitmq_line("basic_get q1")


def test_rabbitmq_leading_conn_flags_ignored():
    cmd = parse_rabbitmq_line(
        "rabbitmqadmin -H 10.0.0.1 -P 15672 -u guest -p guest get queue=q1 count=2"
    )
    assert cmd.action == "get"
    assert cmd.args == {"queue": "q1", "count": 2, "ackmode": "ack_requeue_true"}


def test_mqtt_leading_conn_flags_ignored():
    cmd = parse_mqtt_line("mqttx -h 1.2.3.4 -p 1883 sub -t archery/test")
    assert cmd.action == "sub"
    assert cmd.args["topic"] == "archery/test"


def test_declare_queue_parses_durable():
    cmd = parse_rabbitmq_line("declare queue name=q1 durable=true")
    assert cmd.args["name"] == "q1"
    assert cmd.args["durable"] is True
