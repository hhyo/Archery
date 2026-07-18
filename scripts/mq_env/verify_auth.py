#!/usr/bin/env python3
"""Verify RabbitMQ (AMQP) and EMQX (MQTT) auth. Exit 0 on success."""

import argparse
import os
import ssl
import sys
import time
import uuid

import paho.mqtt.client as mqtt
import pika


def verify_rabbitmq(
    host, port, user, password, vhost, tls=False, ca=None, cert=None, key=None
):
    creds = pika.PlainCredentials(user, password) if user else None
    params = pika.ConnectionParameters(
        host=host,
        port=port,
        virtual_host=vhost,
        credentials=creds,
        socket_timeout=10,
        blocked_connection_timeout=10,
    )
    if tls:
        context = (
            ssl.create_default_context(cafile=ca)
            if ca
            else ssl.create_default_context()
        )
        if cert and key:
            context.load_cert_chain(certfile=cert, keyfile=key)
        params.ssl_options = pika.SSLOptions(context, server_hostname=host)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    q = f"archery.verify.{uuid.uuid4().hex[:8]}"
    ch.queue_declare(queue=q, durable=False, auto_delete=True)
    body = b"archery-ping"
    ch.basic_publish(exchange="", routing_key=q, body=body)
    method, _props, got = ch.basic_get(queue=q, auto_ack=True)
    conn.close()
    if got != body:
        raise RuntimeError(f"rabbitmq roundtrip failed: {got!r}")
    print(f"OK rabbitmq {host}:{port} vhost={vhost} tls={tls}")


def verify_mqtt(host, port, user, password, tls=False, ca=None, cert=None, key=None):
    topic = f"archery/verify/{uuid.uuid4().hex[:8]}"
    payload = b"archery-ping"
    received = {}

    def on_message(client, userdata, msg):
        received["payload"] = msg.payload

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"archery-verify-{uuid.uuid4().hex[:6]}",
    )
    if user:
        client.username_pw_set(user, password or None)
    if tls:
        client.tls_set(ca_certs=ca, certfile=cert, keyfile=key)
    client.on_message = on_message
    client.connect(host, port, keepalive=30)
    client.subscribe(topic, qos=0)
    client.loop_start()
    time.sleep(0.5)
    client.publish(topic, payload, qos=0)
    for _ in range(20):
        if "payload" in received:
            break
        time.sleep(0.25)
    client.loop_stop()
    client.disconnect()
    if received.get("payload") != payload:
        raise RuntimeError(f"mqtt roundtrip failed: {received.get('payload')!r}")
    print(f"OK mqtt {host}:{port} tls={tls}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--amqp-host", default=os.getenv("ARCHERY_TEST_RABBITMQ_HOST", "127.0.0.1")
    )
    p.add_argument(
        "--amqp-port",
        type=int,
        default=int(os.getenv("ARCHERY_TEST_RABBITMQ_PORT", "5672")),
    )
    p.add_argument(
        "--amqp-user", default=os.getenv("ARCHERY_TEST_RABBITMQ_USER", "root")
    )
    p.add_argument(
        "--amqp-password", default=os.getenv("ARCHERY_TEST_RABBITMQ_PASSWORD", "")
    )
    p.add_argument("--vhost", default=os.getenv("ARCHERY_TEST_RABBITMQ_VHOST", "/"))
    p.add_argument(
        "--mqtt-host", default=os.getenv("ARCHERY_TEST_MQTT_HOST", "127.0.0.1")
    )
    p.add_argument(
        "--mqtt-port",
        type=int,
        default=int(os.getenv("ARCHERY_TEST_MQTT_PORT", "1883")),
    )
    p.add_argument("--mqtt-user", default=os.getenv("ARCHERY_TEST_MQTT_USER", ""))
    p.add_argument(
        "--mqtt-password", default=os.getenv("ARCHERY_TEST_MQTT_PASSWORD", "")
    )
    p.add_argument("--tls", action="store_true")
    p.add_argument("--ca", default=os.getenv("ARCHERY_TEST_MQ_CA", ""))
    p.add_argument("--cert", default=os.getenv("ARCHERY_TEST_MQ_CERT", ""))
    p.add_argument("--key", default=os.getenv("ARCHERY_TEST_MQ_KEY", ""))
    args = p.parse_args()
    if not args.amqp_password:
        print("Set ARCHERY_TEST_RABBITMQ_PASSWORD or --amqp-password", file=sys.stderr)
        return 2
    verify_rabbitmq(
        args.amqp_host,
        args.amqp_port,
        args.amqp_user,
        args.amqp_password,
        args.vhost,
        tls=args.tls,
        ca=args.ca or None,
        cert=args.cert or None,
        key=args.key or None,
    )
    verify_mqtt(
        args.mqtt_host,
        args.mqtt_port,
        args.mqtt_user,
        args.mqtt_password,
        tls=args.tls,
        ca=args.ca or None,
        cert=args.cert or None,
        key=args.key or None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
