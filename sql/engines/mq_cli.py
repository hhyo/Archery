# -*- coding: UTF-8 -*-
"""MQTTX / rabbitmqadmin CLI subset parser for MQTT and RabbitMQ engines."""

from __future__ import annotations

import shlex
from dataclasses import dataclass

MQTT_CONN_FLAGS = frozenset(
    {
        "-h",
        "--host",
        "-p",
        "--port",
        "-u",
        "--username",
        "-P",
        "--password",
        "--ca",
        "--cert",
        "--key",
        "--insecure",
        "--protocol",
        "--ws",
        "--ws-path",
    }
)

RABBITMQ_CONN_FLAGS = frozenset(
    {
        "-H",
        "--host",
        "-P",
        "--port",
        "-u",
        "--username",
        "-p",
        "--password",
        "-V",
        "--vhost",
    }
)

MQTT_ACTIONS = frozenset({"pub", "sub", "help"})
RABBITMQ_ACTIONS = frozenset(
    {"get", "publish", "declare", "purge", "delete", "list", "help"}
)
RABBITMQ_UNSUPPORTED_ACTIONS = frozenset({"list", "close"})
RABBITMQ_GET_ACKMODES = frozenset(
    {
        "ack_requeue_true",
        "ack_requeue_false",
        "reject_requeue_true",
        "reject_requeue_false",
    }
)
RABBITMQ_GET_KEYS = frozenset({"queue", "count", "ackmode"})
RABBITMQ_PUBLISH_KEYS = frozenset({"routing_key", "payload", "exchange"})
RABBITMQ_DECLARE_QUEUE_KEYS = frozenset({"name", "durable", "auto_delete"})
RABBITMQ_DECLARE_EXCHANGE_KEYS = frozenset({"name", "type", "durable", "auto_delete"})
RABBITMQ_DECLARE_BINDING_KEYS = frozenset(
    {"source", "destination", "destination_type", "routing_key"}
)
RABBITMQ_DELETE_QUEUE_KEYS = frozenset({"name"})
RABBITMQ_DELETE_EXCHANGE_KEYS = frozenset({"name"})
RABBITMQ_DELETE_BINDING_KEYS = frozenset(
    {"source", "destination", "destination_type", "properties_key"}
)
RABBITMQ_PURGE_KEYS = frozenset({"name"})
RABBITMQ_BOOL_TRUE = frozenset({"true", "1", "yes"})
RABBITMQ_BOOL_FALSE = frozenset({"false", "0", "no"})
RABBITMQ_BOOL_VALUES = RABBITMQ_BOOL_TRUE | RABBITMQ_BOOL_FALSE


@dataclass
class MqCommand:
    engine: str
    action: str
    args: dict
    raw_line: str


def split_mq_lines(sql: str) -> list[str]:
    lines: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return lines


def _consume_flag_value(tokens: list[str], index: int) -> int:
    if index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
        return index + 2
    return index + 1


def _skip_leading_conn_flags(tokens: list[str], conn_flags: frozenset) -> list[str]:
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in conn_flags:
            i = _consume_flag_value(tokens, i)
            continue
        if tok.startswith("--") and "=" in tok:
            name = tok.split("=", 1)[0]
            if name in conn_flags:
                i += 1
                continue
        break
    return tokens[i:]


def _parse_kv(token: str) -> tuple[str, str] | None:
    if "=" not in token:
        return None
    key, _, value = token.partition("=")
    if not key:
        return None
    return key, value


def _parse_mqtt_flags(tokens: list[str], start: int, action: str) -> dict:
    args: dict = {}
    i = start
    while i < len(tokens):
        tok = tokens[i]
        if tok in MQTT_CONN_FLAGS:
            i = _consume_flag_value(tokens, i)
            continue
        if tok in ("-t", "--topic"):
            i += 1
            if i >= len(tokens):
                raise ValueError("missing topic value")
            args["topic"] = tokens[i]
            i += 1
            continue
        if tok in ("-m", "--message"):
            i += 1
            if i >= len(tokens):
                raise ValueError("missing message value")
            args["payload"] = tokens[i]
            i += 1
            continue
        if tok in ("-q", "--qos"):
            i += 1
            if i >= len(tokens):
                raise ValueError("missing qos value")
            args["qos"] = int(tokens[i])
            i += 1
            continue
        if tok in ("-C", "--count"):
            if action != "sub":
                raise ValueError(f"unknown flag: {tok}")
            i += 1
            if i >= len(tokens):
                raise ValueError("missing count value")
            args["count"] = int(tokens[i])
            i += 1
            continue
        raise ValueError(f"unknown flag: {tok}")
    return args


def parse_mqtt_line(line: str) -> MqCommand:
    tokens = shlex.split(line, posix=True)
    if not tokens:
        raise ValueError("empty mqtt command")
    if tokens[0] == "mqttx":
        tokens = tokens[1:]
    if not tokens:
        raise ValueError("empty mqtt command")

    tokens = _skip_leading_conn_flags(tokens, MQTT_CONN_FLAGS)
    if not tokens:
        raise ValueError("empty mqtt command")

    action = tokens[0]
    if action not in MQTT_ACTIONS:
        raise ValueError(f"unknown mqtt action: {action}")

    args = _parse_mqtt_flags(tokens, 1, action)

    if action == "sub":
        args.setdefault("qos", 0)
        args.setdefault("count", 10)
    elif action == "pub":
        if "topic" not in args:
            raise ValueError("pub requires topic")
        if "payload" not in args:
            raise ValueError("pub requires message")
        args.setdefault("qos", 0)

    return MqCommand(engine="mqtt", action=action, args=args, raw_line=line)


def _parse_rabbitmq_kv_args(tokens: list[str], start: int) -> dict:
    args: dict = {}
    i = start
    while i < len(tokens):
        tok = tokens[i]
        if tok in RABBITMQ_CONN_FLAGS:
            i = _consume_flag_value(tokens, i)
            continue
        kv = _parse_kv(tok)
        if kv is None:
            raise ValueError(f"unexpected token: {tok}")
        key, value = kv
        args[key] = value
        i += 1
    return args


def _reject_unknown_keys(args: dict, allowed: frozenset, label: str) -> None:
    unknown = set(args) - allowed
    if unknown:
        bad = sorted(unknown)[0]
        raise ValueError(f"unsupported {label} parameter: {bad}")


def _parse_bool_arg(args: dict, key: str) -> None:
    if key not in args:
        return
    val = str(args[key]).lower()
    if val not in RABBITMQ_BOOL_VALUES:
        raise ValueError(f"{key} must be true or false")
    args[key] = val in RABBITMQ_BOOL_TRUE


def parse_rabbitmq_line(line: str) -> MqCommand:
    tokens = shlex.split(line, posix=True)
    if not tokens:
        raise ValueError("empty rabbitmq command")
    if tokens[0] == "rabbitmqadmin":
        tokens = tokens[1:]
    if not tokens:
        raise ValueError("empty rabbitmq command")

    tokens = _skip_leading_conn_flags(tokens, RABBITMQ_CONN_FLAGS)
    if not tokens:
        raise ValueError("empty rabbitmq command")

    action = tokens[0]
    if action in RABBITMQ_UNSUPPORTED_ACTIONS:
        raise ValueError(f"{action} 需要 RabbitMQ Management API，当前不支持")
    if action not in RABBITMQ_ACTIONS:
        raise ValueError(f"unknown rabbitmq action: {action}")

    i = 1
    sub_target = None

    if action == "declare":
        if i >= len(tokens):
            raise ValueError("declare requires target")
        sub_target = tokens[i]
        if sub_target not in {"queue", "exchange", "binding"}:
            raise ValueError(f"unknown declare target: {sub_target}")
        i += 1
    elif action == "purge":
        if i >= len(tokens) or tokens[i] != "queue":
            raise ValueError("purge requires queue")
        sub_target = "queue"
        i += 1
    elif action == "delete":
        if i >= len(tokens) or tokens[i] not in {
            "queue",
            "exchange",
            "binding",
        }:
            raise ValueError("delete requires queue, exchange, or binding")
        sub_target = tokens[i]
        i += 1

    args = _parse_rabbitmq_kv_args(tokens, i)

    if action == "get":
        if "queue" not in args:
            raise ValueError("get requires queue")
        if "requeue" in args:
            raise ValueError("requeue is not supported; use ackmode instead")
        _reject_unknown_keys(args, RABBITMQ_GET_KEYS, "get")
        if "count" in args:
            args["count"] = int(args["count"])
        else:
            args["count"] = 1
        ackmode = args.get("ackmode", "ack_requeue_true")
        if ackmode not in RABBITMQ_GET_ACKMODES:
            raise ValueError(f"invalid ackmode: {ackmode}")
        args["ackmode"] = ackmode
    elif action == "publish":
        _reject_unknown_keys(args, RABBITMQ_PUBLISH_KEYS, "publish")
        if "routing_key" not in args:
            raise ValueError("publish requires routing_key")
        if "payload" not in args:
            raise ValueError("publish requires payload")
        exchange = args.get("exchange", "")
        if exchange == "amq.default":
            exchange = ""
        args["exchange"] = exchange
    elif action == "declare":
        if sub_target == "queue":
            _reject_unknown_keys(args, RABBITMQ_DECLARE_QUEUE_KEYS, "declare queue")
            if "name" not in args:
                raise ValueError("declare queue requires name")
        elif sub_target == "exchange":
            _reject_unknown_keys(
                args, RABBITMQ_DECLARE_EXCHANGE_KEYS, "declare exchange"
            )
            if "name" not in args:
                raise ValueError("declare exchange requires name")
            if "type" not in args:
                raise ValueError("declare exchange requires type")
        elif sub_target == "binding":
            if "queue" in args or "exchange" in args:
                raise ValueError(
                    "declare binding uses source= and destination=, "
                    "not queue=/exchange="
                )
            _reject_unknown_keys(args, RABBITMQ_DECLARE_BINDING_KEYS, "declare binding")
            if "source" not in args:
                raise ValueError("declare binding requires source")
            if "destination" not in args:
                raise ValueError("declare binding requires destination")
            destination_type = args.get("destination_type", "queue")
            if destination_type != "queue":
                raise ValueError("declare binding destination_type must be queue")
            args["destination_type"] = destination_type
            args.setdefault("routing_key", "")
        _parse_bool_arg(args, "durable")
        _parse_bool_arg(args, "auto_delete")
    elif action == "purge":
        _reject_unknown_keys(args, RABBITMQ_PURGE_KEYS, "purge")
        if "name" not in args:
            raise ValueError("purge queue requires name")
    elif action == "delete":
        if sub_target == "queue":
            _reject_unknown_keys(args, RABBITMQ_DELETE_QUEUE_KEYS, "delete queue")
            if "name" not in args:
                raise ValueError("delete queue requires name")
        elif sub_target == "exchange":
            _reject_unknown_keys(args, RABBITMQ_DELETE_EXCHANGE_KEYS, "delete exchange")
            if "name" not in args:
                raise ValueError("delete exchange requires name")
        elif sub_target == "binding":
            if "queue" in args or "exchange" in args:
                raise ValueError(
                    "delete binding uses source= and destination=, "
                    "not queue=/exchange="
                )
            _reject_unknown_keys(args, RABBITMQ_DELETE_BINDING_KEYS, "delete binding")
            if "source" not in args:
                raise ValueError("delete binding requires source")
            if "destination" not in args:
                raise ValueError("delete binding requires destination")
            destination_type = args.get("destination_type", "queue")
            if destination_type != "queue":
                raise ValueError("delete binding destination_type must be queue")
            args["destination_type"] = destination_type
            args.setdefault("properties_key", "")

    if sub_target is not None:
        args["target"] = sub_target

    return MqCommand(engine="rabbitmq", action=action, args=args, raw_line=line)
