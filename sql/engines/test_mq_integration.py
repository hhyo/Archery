# -*- coding: UTF-8 -*-
"""Optional smoke tests against live RabbitMQ and MQTT brokers."""
import os
import socket
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sql.engines.mqtt import MqttEngine
from sql.engines.rabbitmq import RabbitmqEngine
from sql.models import Instance


def _env_port(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        pytest.skip(f"{name} must be an integer")


def _require_reachable(host, port):
    try:
        with socket.create_connection((host, port), timeout=1):
            pass
    except OSError as exc:
        pytest.skip(f"broker {host}:{port} is unreachable: {exc}")


def _tls_material():
    paths = {
        name: os.getenv(env_name)
        for name, env_name in (
            ("ca_cert", "ARCHERY_TEST_MQ_CA"),
            ("client_cert", "ARCHERY_TEST_MQ_CERT"),
            ("client_key", "ARCHERY_TEST_MQ_KEY"),
        )
    }
    if not all(paths.values()):
        pytest.skip("ARCHERY_TEST_MQ_CA/CERT/KEY are required for mTLS")
    try:
        return {name: Path(path).read_text() for name, path in paths.items()}
    except OSError as exc:
        pytest.skip(f"cannot read mTLS material: {exc}")


def _rabbitmq_engine(tls=False):
    password = os.getenv("ARCHERY_TEST_RABBITMQ_PASSWORD")
    if not password:
        pytest.skip("ARCHERY_TEST_RABBITMQ_PASSWORD is not set")

    host = os.getenv(
        "ARCHERY_TEST_RABBITMQ_TLS_HOST" if tls else "ARCHERY_TEST_RABBITMQ_HOST",
        "localhost" if tls else "127.0.0.1",
    )
    port = _env_port(
        "ARCHERY_TEST_RABBITMQ_TLS_PORT" if tls else "ARCHERY_TEST_RABBITMQ_PORT",
        5671 if tls else 5672,
    )
    _require_reachable(host, port)
    instance = Instance(
        instance_name="rabbitmq_integration",
        type="master",
        db_type="rabbitmq",
        host=host,
        port=port,
        user=os.getenv("ARCHERY_TEST_RABBITMQ_USER", "archery_test"),
        password=password,
        db_name=os.getenv("ARCHERY_TEST_RABBITMQ_VHOST", "/"),
        is_ssl=tls,
        verify_ssl=True,
        **(_tls_material() if tls else {}),
    )
    return RabbitmqEngine(instance=instance)


def _mqtt_engine(tls=False):
    host = os.getenv(
        "ARCHERY_TEST_MQTT_TLS_HOST" if tls else "ARCHERY_TEST_MQTT_HOST",
        "localhost" if tls else "127.0.0.1",
    )
    port = _env_port(
        "ARCHERY_TEST_MQTT_TLS_PORT" if tls else "ARCHERY_TEST_MQTT_PORT",
        8883 if tls else 1883,
    )
    _require_reachable(host, port)
    instance = Instance(
        instance_name="mqtt_integration",
        type="master",
        db_type="mqtt",
        host=host,
        port=port,
        user=os.getenv("ARCHERY_TEST_MQTT_USER", ""),
        password=os.getenv("ARCHERY_TEST_MQTT_PASSWORD", ""),
        db_name="default",
        is_ssl=tls,
        verify_ssl=True,
        **(_tls_material() if tls else {}),
    )
    return MqttEngine(instance=instance)


def _workflow(db_name, sql):
    workflow = MagicMock()
    workflow.db_name = db_name
    workflow.sqlworkflowcontent.sql_content = sql
    return workflow


def _assert_connection(engine):
    result = engine.test_connection()
    assert not result.error, result.error
    assert result.rows == [["连接成功"]]


def _rabbitmq_roundtrip(engine):
    queue = f"archery.integration.{uuid.uuid4().hex}"
    payload = f"rabbitmq-{uuid.uuid4().hex}"
    try:
        write_result = engine.execute_workflow(
            _workflow(
                engine.db_name,
                f'queue_declare {queue}\npublish "" {queue} {payload}',
            )
        )
        assert not write_result.error, write_result.error

        read_result = engine.query(db_name=engine.db_name, sql=f"basic_get {queue}")
        assert not read_result.error, read_result.error
        assert read_result.rows == [[queue, queue, payload]]
    finally:
        engine.execute_workflow(_workflow(engine.db_name, f"queue_delete {queue}"))


def _mqtt_roundtrip(engine):
    topic = f"archery/integration/{uuid.uuid4().hex}"
    payload = f"mqtt-{uuid.uuid4().hex}"
    with ThreadPoolExecutor(max_workers=1) as executor:
        subscribed = executor.submit(engine.query, sql=f"subscribe {topic} 5 1")
        time.sleep(0.5)
        write_result = engine.execute_workflow(
            _workflow(engine.db_name, f"publish {topic} {payload}")
        )
        assert not write_result.error, write_result.error
        read_result = subscribed.result(timeout=7)

    assert not read_result.error, read_result.error
    assert read_result.rows == [[topic, payload, 0, False]]


def test_rabbitmq_plaintext_roundtrip():
    engine = _rabbitmq_engine()
    _assert_connection(engine)
    _rabbitmq_roundtrip(engine)


def test_mqtt_plaintext_roundtrip():
    engine = _mqtt_engine()
    _assert_connection(engine)
    _mqtt_roundtrip(engine)


def test_rabbitmq_mtls_roundtrip():
    engine = _rabbitmq_engine(tls=True)
    _assert_connection(engine)
    _rabbitmq_roundtrip(engine)


def test_mqtt_mtls_roundtrip():
    engine = _mqtt_engine(tls=True)
    _assert_connection(engine)
    _mqtt_roundtrip(engine)
