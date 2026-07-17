# -*- coding: UTF-8 -*-
"""MQTTX / rabbitmqadmin CLI subset parser for MQTT and RabbitMQ engines."""
from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Iterable

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
RABBITMQ_ACTIONS = frozenset({"get", "publish", "declare", "purge", "delete", "list", "help"})


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


def _skip_conn_flags(tokens: list[str], index: int, conn_flags: Iterable[str]) -> int:
    while index < len(tokens) and tokens[index] in conn_flags:
        index = _consume_flag_value(tokens, index)
    return index


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


def parse_rabbitmq_line(line: str) -> MqCommand:
    tokens = shlex.split(line, posix=True)
    if not tokens:
        raise ValueError("empty rabbitmq command")
    if tokens[0] == "rabbitmqadmin":
        tokens = tokens[1:]
    if not tokens:
        raise ValueError("empty rabbitmq command")

    action = tokens[0]
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
    elif action in {"purge", "delete"}:
        if i >= len(tokens) or tokens[i] != "queue":
            raise ValueError(f"{action} requires queue")
        sub_target = "queue"
        i += 1
    elif action == "list":
        if i >= len(tokens) or tokens[i] != "queues":
            raise ValueError("list requires queues")
        sub_target = "queues"
        i += 1

    args = _parse_rabbitmq_kv_args(tokens, i)
    if sub_target is not None:
        args["target"] = sub_target

    if action == "get":
        if "queue" not in args:
            raise ValueError("get requires queue")
        if "count" in args:
            args["count"] = int(args["count"])
        else:
            args["count"] = 1
    elif action == "publish":
        if "routing_key" not in args:
            raise ValueError("publish requires routing_key")
        if "payload" not in args:
            raise ValueError("publish requires payload")
        args.setdefault("exchange", "")
    elif action == "declare":
        if sub_target == "queue" and "name" not in args:
            raise ValueError("declare queue requires name")
        if sub_target == "exchange":
            if "name" not in args:
                raise ValueError("declare exchange requires name")
            args.setdefault("type", "direct")
        if sub_target == "binding":
            for key in ("queue", "exchange", "routing_key"):
                if key not in args:
                    raise ValueError(f"declare binding requires {key}")
    elif action in {"purge", "delete"}:
        if "name" not in args:
            raise ValueError(f"{action} queue requires name")

    return MqCommand(engine="rabbitmq", action=action, args=args, raw_line=line)
