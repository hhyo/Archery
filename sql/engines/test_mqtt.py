# -*- coding: UTF-8 -*-
from unittest import TestCase
from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt

from sql.engines.mqtt import MqttEngine
from sql.models import Instance


class TestMqttEngine(TestCase):
    def setUp(self):
        self.ins = Instance(
            instance_name="mqtt_test",
            type="master",
            db_type="mqtt",
            host="127.0.0.1",
            port=1883,
            user="",
            password="",
            db_name="default",
        )

    def test_query_check_allows_subscribe(self):
        engine = MqttEngine(instance=self.ins)
        result = engine.query_check(sql="subscribe archery/test 2 5")
        self.assertFalse(result["bad_query"])

    def test_query_check_blocks_publish(self):
        engine = MqttEngine(instance=self.ins)
        result = engine.query_check(sql='publish archery/test "hi"')
        self.assertTrue(result["bad_query"])

    def test_query_check_rejects_invalid_subscribe_arguments(self):
        engine = MqttEngine(instance=self.ins)
        for command in (
            "subscribe",
            "subscribe topic invalid",
            "subscribe topic 0",
            "subscribe topic 1 0",
            "subscribe topic 1 2 extra",
        ):
            with self.subTest(command=command):
                self.assertTrue(engine.query_check(sql=command)["bad_query"])

    def test_execute_check_allows_publish_only(self):
        engine = MqttEngine(instance=self.ins)
        allowed = engine.execute_check(sql='publish archery/test "hello world"')
        blocked = engine.execute_check(sql="subscribe archery/test")
        self.assertEqual(allowed.rows[0].errlevel, 0)
        self.assertEqual(blocked.rows[0].errlevel, 2)
        self.assertEqual(blocked.rows[0].errormessage, "禁止使用查询命令！")

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_test_connection(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        engine = MqttEngine(instance=self.ins)

        result = engine.test_connection()

        mock_client_cls.assert_called_once()
        mock_client.connect.assert_called_once_with("127.0.0.1", 1883, keepalive=30)
        mock_client.disconnect.assert_called_once()
        self.assertFalse(result.error)

    @patch("sql.engines.mqtt.time.monotonic", side_effect=[0, 31])
    @patch("sql.engines.mqtt.mqtt.Client")
    def test_subscribe_caps_timeout_and_message_count(
        self, mock_client_cls, _mock_monotonic
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        def deliver_messages(*_args, **_kwargs):
            for index in range(101):
                message = MagicMock(
                    topic="archery/test",
                    payload=str(index).encode(),
                    qos=0,
                    retain=False,
                )
                mock_client.on_message(mock_client, None, message)

        mock_client.loop_start.side_effect = deliver_messages
        engine = MqttEngine(instance=self.ins)

        result = engine.query(sql="subscribe archery/test 999 999")

        mock_client.subscribe.assert_called_once_with("archery/test", qos=0)
        self.assertEqual(result.affected_rows, 100)
        self.assertEqual(result.error, None)

    @patch("sql.engines.mqtt.time.monotonic", side_effect=[0, 3])
    @patch("sql.engines.mqtt.mqtt.Client")
    def test_subscribe_uses_defaults(self, mock_client_cls, _mock_monotonic):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        engine = MqttEngine(instance=self.ins)

        result = engine.query(sql="subscribe archery/test")

        self.assertEqual(result.error, None)
        self.assertEqual(result.column_list, ["topic", "payload", "qos", "retain"])

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_subscribe_collects_messages_and_decodes_payload(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        def deliver_message(*_args, **_kwargs):
            message = MagicMock(
                topic="archery/test", payload=b"hello", qos=1, retain=False
            )
            mock_client.on_message(mock_client, None, message)

        mock_client.loop_start.side_effect = deliver_message
        engine = MqttEngine(instance=self.ins)

        result = engine.query(sql="subscribe archery/test 3 1")

        self.assertEqual(result.rows, [["archery/test", "hello", 1, False]])
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_client_uses_version2_and_credentials(self, mock_client_cls):
        self.ins.user = "mqtt-user"
        self.ins.password = "mqtt-password"
        engine = MqttEngine(instance=self.ins)

        engine.test_connection()

        args, _kwargs = mock_client_cls.call_args
        self.assertEqual(args[0], mqtt.CallbackAPIVersion.VERSION2)
        mock_client_cls.return_value.username_pw_set.assert_called_once_with(
            "mqtt-user", "mqtt-password"
        )

    @patch("sql.engines.mqtt.ssl.create_default_context")
    @patch("sql.engines.mqtt.mqtt.Client")
    def test_tls_configures_ca_client_cert_and_verification(
        self, mock_client_cls, mock_create_context
    ):
        self.ins.is_ssl = True
        self.ins.verify_ssl = False
        self.ins.ca_cert = "CA PEM"
        self.ins.client_cert = "CERT PEM"
        self.ins.client_key = "KEY PEM"
        context = MagicMock()
        mock_create_context.return_value = context
        engine = MqttEngine(instance=self.ins)

        result = engine.test_connection()

        self.assertEqual(result.error, None)
        mock_create_context.assert_called_once()
        context.load_cert_chain.assert_called_once()
        self.assertFalse(context.check_hostname)
        self.assertEqual(context.verify_mode, 0)
        mock_client_cls.return_value.tls_set_context.assert_called_once_with(context)

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_client_cert_and_key_must_be_configured_together(self, mock_client_cls):
        self.ins.is_ssl = True
        self.ins.client_cert = "CERT PEM"
        self.ins.client_key = ""
        engine = MqttEngine(instance=self.ins)

        result = engine.test_connection()

        self.assertIn("必须同时配置", result.error)
        mock_client_cls.assert_not_called()

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_execute_workflow_publishes(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        workflow = MagicMock()
        workflow.db_name = "default"
        workflow.sqlworkflowcontent.sql_content = 'publish archery/test "hello world"'
        engine = MqttEngine(instance=self.ins)

        result = engine.execute_workflow(workflow)

        mock_client.publish.assert_called_once_with(
            "archery/test", payload="hello world", qos=0, retain=False
        )
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()
        self.assertEqual(result.rows[0].errlevel, 0)
