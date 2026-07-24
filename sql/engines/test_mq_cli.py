# -*- coding: UTF-8 -*-
import pytest

from sql.engines.mq_cli import (
    parse_mqtt_line,
    parse_rabbitmq_line,
    redact_mq_credentials,
    split_mq_lines,
)


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


def test_declare_binding_official_keys():
    cmd = parse_rabbitmq_line("declare binding source=ex destination=q routing_key=rk")
    assert cmd.args["source"] == "ex"
    assert cmd.args["destination"] == "q"
    assert cmd.args["destination_type"] == "queue"
    assert cmd.args["routing_key"] == "rk"


def test_declare_binding_rejects_legacy_queue_exchange_keys():
    with pytest.raises(ValueError, match="source"):
        parse_rabbitmq_line("declare binding queue=q exchange=ex routing_key=rk")


def test_declare_binding_rejects_exchange_destination_type():
    with pytest.raises(ValueError):
        parse_rabbitmq_line(
            "declare binding source=a destination=b destination_type=exchange"
        )


def test_declare_queue_auto_delete():
    cmd = parse_rabbitmq_line("declare queue name=q1 auto_delete=true")
    assert cmd.args["auto_delete"] is True


def test_declare_rejects_arguments():
    with pytest.raises(ValueError):
        parse_rabbitmq_line("declare queue name=q1 arguments={}")


def test_delete_exchange_and_binding():
    d = parse_rabbitmq_line("delete exchange name=ex1")
    assert d.args["target"] == "exchange"
    assert d.args["name"] == "ex1"
    b = parse_rabbitmq_line(
        "delete binding source=ex destination_type=queue destination=q properties_key=rk"
    )
    assert b.args["source"] == "ex"
    assert b.args["destination"] == "q"
    assert b.args["destination_type"] == "queue"
    assert b.args["properties_key"] == "rk"


def test_publish_amq_default_normalizes():
    p = parse_rabbitmq_line("publish routing_key=q payload=hi exchange=amq.default")
    assert p.args["exchange"] == ""


def test_publish_rejects_properties():
    with pytest.raises(ValueError):
        parse_rabbitmq_line("publish routing_key=q payload=hi properties={}")


def test_rabbitmq_empty_command_rejected():
    with pytest.raises(ValueError, match="empty"):
        parse_rabbitmq_line("")
    with pytest.raises(ValueError, match="empty"):
        parse_rabbitmq_line("rabbitmqadmin")
    with pytest.raises(ValueError, match="empty"):
        parse_rabbitmq_line("rabbitmqadmin -H 127.0.0.1")


def test_rabbitmq_get_requires_queue_and_valid_ackmode():
    with pytest.raises(ValueError, match="queue"):
        parse_rabbitmq_line("get count=1")
    with pytest.raises(ValueError, match="ackmode"):
        parse_rabbitmq_line("get queue=q1 ackmode=bogus")


def test_publish_requires_routing_key_and_payload():
    with pytest.raises(ValueError, match="routing_key"):
        parse_rabbitmq_line("publish payload=hi")
    with pytest.raises(ValueError, match="payload"):
        parse_rabbitmq_line("publish routing_key=q")


def test_declare_missing_required_and_unknown_target():
    with pytest.raises(ValueError, match="target"):
        parse_rabbitmq_line("declare")
    with pytest.raises(ValueError, match="unknown declare target"):
        parse_rabbitmq_line("declare fanout name=x")
    with pytest.raises(ValueError, match="name"):
        parse_rabbitmq_line("declare queue durable=true")
    with pytest.raises(ValueError, match="name"):
        parse_rabbitmq_line("declare exchange type=direct")
    with pytest.raises(ValueError, match="type"):
        parse_rabbitmq_line("declare exchange name=ex")
    with pytest.raises(ValueError, match="source"):
        parse_rabbitmq_line("declare binding destination=q")
    with pytest.raises(ValueError, match="destination"):
        parse_rabbitmq_line("declare binding source=ex")


def test_declare_exchange_requires_type_and_preserves_it():
    with pytest.raises(ValueError, match="type"):
        parse_rabbitmq_line("declare exchange name=demo.ex")
    cmd = parse_rabbitmq_line("declare exchange name=demo.ex type=topic")
    assert cmd.args["name"] == "demo.ex"
    assert cmd.args["type"] == "topic"
    assert cmd.args["target"] == "exchange"


def test_declare_bool_arg_must_be_true_or_false():
    with pytest.raises(ValueError, match="durable"):
        parse_rabbitmq_line("declare queue name=q1 durable=maybe")


def test_purge_requires_queue_target_and_name():
    with pytest.raises(ValueError, match="purge"):
        parse_rabbitmq_line("purge")
    with pytest.raises(ValueError, match="purge"):
        parse_rabbitmq_line("purge exchange name=ex")
    with pytest.raises(ValueError, match="name"):
        parse_rabbitmq_line("purge queue")


def test_delete_missing_required_and_legacy_binding_keys():
    with pytest.raises(ValueError, match="delete requires"):
        parse_rabbitmq_line("delete")
    with pytest.raises(ValueError, match="delete requires"):
        parse_rabbitmq_line("delete fanout name=x")
    with pytest.raises(ValueError, match="name"):
        parse_rabbitmq_line("delete queue")
    with pytest.raises(ValueError, match="name"):
        parse_rabbitmq_line("delete exchange")
    with pytest.raises(ValueError, match="source"):
        parse_rabbitmq_line("delete binding queue=q exchange=ex properties_key=rk")
    with pytest.raises(ValueError, match="source"):
        parse_rabbitmq_line("delete binding destination=q")
    with pytest.raises(ValueError, match="destination"):
        parse_rabbitmq_line("delete binding source=ex")
    with pytest.raises(ValueError, match="destination_type"):
        parse_rabbitmq_line(
            "delete binding source=ex destination=q destination_type=exchange"
        )


# --- Codex #2: valueless MQTT connection flags must not eat the subcommand ---


def test_mqtt_valueless_flag_before_subcommand_not_consumed():
    cmd = parse_mqtt_line("mqttx --insecure sub -t archery/test")
    assert cmd.action == "sub"
    assert cmd.args["topic"] == "archery/test"


def test_mqtt_valueless_ws_flag_before_subcommand():
    cmd = parse_mqtt_line("mqttx --ws sub -t archery/test -C 3")
    assert cmd.action == "sub"
    assert cmd.args["topic"] == "archery/test"
    assert cmd.args["count"] == 3


def test_mqtt_valueless_flag_mixed_with_valued_conn_flags():
    cmd = parse_mqtt_line("mqttx -h 1.2.3.4 --insecure -p 1883 sub -t t")
    assert cmd.action == "sub"
    assert cmd.args["topic"] == "t"


def test_mqtt_valueless_flag_after_subcommand_ignored():
    cmd = parse_mqtt_line("sub -t archery/test --insecure")
    assert cmd.action == "sub"
    assert cmd.args["topic"] == "archery/test"


# --- Codex #14: a trailing SQL terminator (;) must be stripped before parsing ---


def test_mqtt_strips_trailing_statement_terminator():
    cmd = parse_mqtt_line("sub -t archery/test;")
    assert cmd.action == "sub"
    assert cmd.args["topic"] == "archery/test"


def test_rabbitmq_strips_trailing_statement_terminator():
    g = parse_rabbitmq_line("get queue=q1 count=1;")
    assert g.action == "get"
    assert g.args["queue"] == "q1"
    assert g.args["count"] == 1


def test_rabbitmq_delete_strips_terminator_from_name():
    d = parse_rabbitmq_line("delete queue name=orders;")
    assert d.args["name"] == "orders"


def test_quoted_payload_ending_with_semicolon_preserved():
    # A ';' inside quotes (line ends with the closing quote) is payload, not a
    # terminator, and must survive parsing.
    p = parse_rabbitmq_line('publish routing_key=q payload="hello;"')
    assert p.args["payload"] == "hello;"


# --- Codex review: redact password connection flags from logged MQ lines ---


def test_redact_mqtt_password_but_not_port():
    out = redact_mq_credentials("mqttx -P secret sub -t demo", "mqtt")
    assert "secret" not in out
    assert "***" in out
    # -p is the MQTT port, not the password: must NOT be redacted.
    out_port = redact_mq_credentials("mqttx -p 1883 sub -t demo", "mqtt")
    assert "1883" in out_port


def test_redact_rabbitmq_password_but_not_port():
    out = redact_mq_credentials("rabbitmqadmin -p secret get queue=q", "rabbitmq")
    assert "secret" not in out
    # -P is the RabbitMQ port, not the password: must NOT be redacted.
    out_port = redact_mq_credentials("rabbitmqadmin -P 5672 get queue=q", "rabbitmq")
    assert "5672" in out_port


def test_redact_long_password_flag_and_equals_form():
    out = redact_mq_credentials("mqttx --password s3cret sub -t t", "mqtt")
    assert "s3cret" not in out
    out_eq = redact_mq_credentials(
        "rabbitmqadmin --password=s3cret get queue=q", "rabbitmq"
    )
    assert "s3cret" not in out_eq
    assert "--password=***" in out_eq


def test_redact_unknown_engine_masks_both_short_forms():
    out = redact_mq_credentials("-p a -P b sub -t t", None)
    assert "a" not in out.split() and "b" not in out.split()
