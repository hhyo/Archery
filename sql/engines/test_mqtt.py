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
        result = engine.query_check(sql="sub -t archery/test -C 5")
        self.assertFalse(result["bad_query"])

    def test_query_check_allows_help(self):
        engine = MqttEngine(instance=self.ins)
        result = engine.query_check(sql="help")
        self.assertFalse(result["bad_query"])

    def test_query_check_blocks_publish(self):
        engine = MqttEngine(instance=self.ins)
        result = engine.query_check(sql="pub -t archery/test -m hi")
        self.assertTrue(result["bad_query"])

    def test_query_check_rejects_invalid_subscribe_arguments(self):
        engine = MqttEngine(instance=self.ins)
        for command in (
            "sub",
            "sub -t",
            "sub -t topic --bench",
            "subscribe archery/test",
            "sub -t topic -C 0",
        ):
            with self.subTest(command=command):
                self.assertTrue(engine.query_check(sql=command)["bad_query"])

    def test_mqtt_query_check_rejects_explain_prefix(self):
        engine = MqttEngine(instance=self.ins)
        for sql in ("explain sub -t t", "explain", "EXPLAIN\nsub -t t"):
            with self.subTest(sql=sql):
                out = engine.query_check(sql=sql)
                self.assertTrue(out["bad_query"])
                self.assertIn("不支持执行计划", out["msg"])

    def test_execute_check_allows_publish_only(self):
        engine = MqttEngine(instance=self.ins)
        allowed = engine.execute_check(sql='pub -t archery/test -m "hello world"')
        allowed_qos = engine.execute_check(
            sql='pub -t archery/test -m "hello world" -q 2'
        )
        blocked = engine.execute_check(sql="sub -t archery/test")
        self.assertEqual(allowed.rows[0].errlevel, 0)
        self.assertEqual(allowed_qos.rows[0].errlevel, 0)
        self.assertEqual(blocked.rows[0].errlevel, 2)
        self.assertEqual(blocked.rows[0].errormessage, "禁止使用查询命令！")

    def test_execute_check_rejects_invalid_publish_qos(self):
        engine = MqttEngine(instance=self.ins)
        for command in (
            'pub -t archery/test -m "hello" -q 3',
            'pub -t archery/test -m "hello" -q invalid',
            'pub -t archery/test -m "hello" --bench',
        ):
            with self.subTest(command=command):
                result = engine.execute_check(sql=command)
                self.assertEqual(result.rows[0].errlevel, 2)

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_test_connection(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.loop_start.side_effect = lambda: mock_client.on_connect(
            mock_client, None, None, 0, None
        )
        engine = MqttEngine(instance=self.ins)

        result = engine.test_connection()

        mock_client_cls.assert_called_once()
        mock_client.connect.assert_called_once_with("127.0.0.1", 1883, keepalive=30)
        mock_client.loop_start.assert_called_once()
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()
        self.assertFalse(result.error)

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_test_connection_reports_bad_credentials(self, mock_client_cls):
        self.ins.user = "bad-user"
        self.ins.password = "bad-password"
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        reason_code = MagicMock(is_failure=True)
        reason_code.__str__.return_value = "Not authorized"
        mock_client.loop_start.side_effect = lambda: mock_client.on_connect(
            mock_client, None, None, reason_code, None
        )
        engine = MqttEngine(instance=self.ins)

        result = engine.test_connection()

        self.assertIn("Not authorized", result.error)
        self.assertEqual(result.rows, [])

    @patch("sql.engines.mqtt.threading.Event.wait", return_value=False)
    @patch("sql.engines.mqtt.mqtt.Client")
    def test_test_connection_reports_connack_timeout(self, mock_client_cls, _mock_wait):
        engine = MqttEngine(instance=self.ins)

        result = engine.test_connection()

        self.assertIn("CONNACK", result.error)
        self.assertIn("超时", result.error)
        mock_client_cls.return_value.loop_stop.assert_called_once()
        mock_client_cls.return_value.disconnect.assert_called_once()

    @patch("sql.engines.mqtt.time.monotonic", side_effect=[0, 61])
    @patch("sql.engines.mqtt.mqtt.Client")
    def test_subscribe_caps_message_count(self, mock_client_cls, _mock_monotonic):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.subscribe.return_value = (0, 1)

        def deliver_messages(*_args, **_kwargs):
            mock_client.on_connect(mock_client, None, None, 0, None)
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

        result = engine.query(sql="sub -t archery/test -C 999")

        mock_client.subscribe.assert_called_once_with("archery/test", qos=0)
        self.assertEqual(result.affected_rows, 100)
        self.assertEqual(result.error, None)

    @patch("sql.engines.mqtt.time.monotonic", side_effect=[0, 60])
    @patch("sql.engines.mqtt.mqtt.Client")
    def test_subscribe_uses_defaults(self, mock_client_cls, _mock_monotonic):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.subscribe.return_value = (0, 1)
        mock_client.loop_start.side_effect = lambda: mock_client.on_connect(
            mock_client, None, None, 0, None
        )
        engine = MqttEngine(instance=self.ins)

        result = engine.query(sql="sub -t archery/test")

        self.assertEqual(result.error, None)
        self.assertEqual(result.column_list, ["topic", "payload", "qos", "retain"])
        self.assertIn("超时", result.warning)
        self.assertIn("60", result.warning)

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_subscribe_collects_messages_and_decodes_payload(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.subscribe.return_value = (0, 1)

        def deliver_message(*_args, **_kwargs):
            mock_client.on_connect(mock_client, None, None, 0, None)
            message = MagicMock(
                topic="archery/test", payload=b"hello", qos=1, retain=False
            )
            mock_client.on_message(mock_client, None, message)

        mock_client.loop_start.side_effect = deliver_message
        engine = MqttEngine(instance=self.ins)

        result = engine.query(sql="sub -t archery/test -C 1")

        self.assertEqual(result.rows, [["archery/test", "hello", 1, False]])
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_client_uses_version2_and_credentials(self, mock_client_cls):
        self.ins.user = "mqtt-user"
        self.ins.password = "mqtt-password"
        mock_client_cls.return_value.loop_start.side_effect = (
            lambda: mock_client_cls.return_value.on_connect(
                mock_client_cls.return_value, None, None, 0, None
            )
        )
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
        mock_client_cls.return_value.loop_start.side_effect = (
            lambda: mock_client_cls.return_value.on_connect(
                mock_client_cls.return_value, None, None, 0, None
            )
        )
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
    def test_client_cert_and_key_are_validated_without_ssl(self, mock_client_cls):
        self.ins.is_ssl = False
        self.ins.client_cert = "CERT PEM"
        self.ins.client_key = ""
        engine = MqttEngine(instance=self.ins)

        result = engine.test_connection()

        self.assertIn("必须同时配置", result.error)
        mock_client_cls.assert_not_called()

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_query_reports_bad_credentials(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        reason_code = MagicMock(is_failure=True)
        reason_code.__str__.return_value = "Bad user name or password"
        mock_client.loop_start.side_effect = lambda: mock_client.on_connect(
            mock_client, None, None, reason_code, None
        )
        engine = MqttEngine(instance=self.ins)

        result = engine.query(sql="sub -t archery/test -C 1")

        self.assertIn("Bad user name or password", result.error)
        mock_client.subscribe.assert_not_called()

    def test_query_help(self):
        engine = MqttEngine(instance=self.ins)

        result = engine.query(sql="help")

        self.assertEqual(result.error, None)
        self.assertIn(["sub -t <topic> [-q N] [-C N]"], result.rows)
        self.assertIn(["pub -t <topic> -m <payload> [-q N]"], result.rows)
        self.assertIn(["help"], result.rows)

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_execute_workflow_publishes(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.loop_start.side_effect = lambda: mock_client.on_connect(
            mock_client, None, None, 0, None
        )
        workflow = MagicMock()
        workflow.db_name = "default"
        workflow.sqlworkflowcontent.sql_content = 'pub -t archery/test -m "hello world"'
        engine = MqttEngine(instance=self.ins)

        result = engine.execute_workflow(workflow)

        mock_client.publish.assert_called_once_with(
            "archery/test", payload="hello world", qos=0, retain=False
        )
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()
        self.assertEqual(result.rows[0].errlevel, 0)

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_execute_workflow_publishes_with_qos(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.loop_start.side_effect = lambda: mock_client.on_connect(
            mock_client, None, None, 0, None
        )
        workflow = MagicMock()
        workflow.db_name = "default"
        workflow.sqlworkflowcontent.sql_content = (
            'pub -t archery/test -m "hello world" -q 2'
        )
        engine = MqttEngine(instance=self.ins)

        result = engine.execute_workflow(workflow)

        mock_client.publish.assert_called_once_with(
            "archery/test", payload="hello world", qos=2, retain=False
        )
        self.assertEqual(result.rows[0].errlevel, 0)

    @patch("sql.engines.mqtt.time.monotonic", side_effect=[0, 0.01, 0.02, 60])
    @patch("sql.engines.mqtt.mqtt.Client")
    def test_run_subscribe_honors_cancel_check_and_on_message(
        self, mock_client_cls, _mock_monotonic
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.subscribe.return_value = (0, 1)
        mock_client.loop_start.side_effect = lambda: mock_client.on_connect(
            mock_client, None, None, 0, None
        )
        engine = MqttEngine(instance=self.ins)
        seen = []
        ticks = {"n": 0}

        def cancel_check():
            ticks["n"] += 1
            return ticks["n"] >= 2

        result = engine.run_subscribe(
            topic="archery/test",
            qos=1,
            max_msgs=10,
            timeout_sec=60,
            cancel_check=cancel_check,
            on_message=seen.append,
        )

        mock_client.subscribe.assert_called_once_with("archery/test", qos=1)
        self.assertEqual(result.error, None)
        self.assertEqual(result.rows, [])
        self.assertEqual(seen, [])

    # --- Codex #10: errlevel=2 rows must increment error_count ---

    def test_execute_check_counts_errors(self):
        engine = MqttEngine(instance=self.ins)
        result = engine.execute_check(
            sql="sub -t archery/test\npub -t archery/test -m hi -q 9"
        )
        self.assertEqual(result.error_count, 2)
        self.assertTrue(all(row.errlevel == 2 for row in result.rows))

        clean = engine.execute_check(sql='pub -t archery/test -m "hi"')
        self.assertEqual(clean.error_count, 0)

    # --- Codex #13: connection failure must record the first command ---

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_execute_workflow_connection_failure_records_first_command(
        self, mock_client_cls
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        reason_code = MagicMock(is_failure=True)
        reason_code.__str__.return_value = "Not authorized"
        mock_client.loop_start.side_effect = lambda: mock_client.on_connect(
            mock_client, None, None, reason_code, None
        )
        workflow = MagicMock()
        workflow.db_name = "default"
        workflow.sqlworkflowcontent.sql_content = "\n".join(
            ['pub -t a -m "1"', 'pub -t b -m "2"', 'pub -t c -m "3"']
        )
        engine = MqttEngine(instance=self.ins)

        result = engine.execute_workflow(workflow)

        self.assertTrue(result.error)
        self.assertEqual(len(result.rows), 3)
        self.assertEqual(result.rows[0].sql, 'pub -t a -m "1"')
        self.assertEqual(result.rows[0].errlevel, 2)
        self.assertEqual(result.rows[1].sql, 'pub -t b -m "2"')
        self.assertEqual(result.rows[2].sql, 'pub -t c -m "3"')

    # --- Codex #15: SUBACK denial must fail fast, not wait out the timeout ---

    @patch("sql.engines.mqtt.time.monotonic", side_effect=[0, 0.01, 0.02, 60])
    @patch("sql.engines.mqtt.mqtt.Client")
    def test_run_subscribe_fails_fast_when_subscription_rejected(
        self, mock_client_cls, _mock_monotonic
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.subscribe.return_value = (0, 1)

        def connect_and_deny(*_args, **_kwargs):
            mock_client.on_connect(mock_client, None, None, 0, None)
            denied = MagicMock(is_failure=True)
            denied.__str__.return_value = "Not authorized"
            mock_client.on_subscribe(mock_client, None, 1, [denied], None)

        mock_client.loop_start.side_effect = connect_and_deny
        engine = MqttEngine(instance=self.ins)

        result = engine.run_subscribe(
            topic="archery/test", qos=0, max_msgs=10, timeout_sec=60
        )

        self.assertIn("订阅被拒绝", result.error)
        self.assertEqual(result.rows, [])

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_run_subscribe_raises_when_subscribe_request_fails(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.subscribe.return_value = (mqtt.MQTT_ERR_NO_CONN, 1)
        mock_client.loop_start.side_effect = lambda: mock_client.on_connect(
            mock_client, None, None, 0, None
        )
        engine = MqttEngine(instance=self.ins)

        result = engine.run_subscribe(
            topic="archery/test", qos=0, max_msgs=1, timeout_sec=60
        )

        self.assertIn("订阅请求失败", result.error)

    # --- Codex review: a stalled QoS publish must not hang the worker ---

    @patch("sql.engines.mqtt.mqtt.Client")
    def test_execute_workflow_publish_timeout_records_failure(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.loop_start.side_effect = lambda: mock_client.on_connect(
            mock_client, None, None, 0, None
        )
        publish_info = MagicMock()
        publish_info.wait_for_publish.side_effect = RuntimeError("timed out")
        mock_client.publish.return_value = publish_info
        workflow = MagicMock()
        workflow.db_name = "default"
        workflow.sqlworkflowcontent.sql_content = 'pub -t archery/test -m "hi" -q 1'
        engine = MqttEngine(instance=self.ins)

        result = engine.execute_workflow(workflow)

        self.assertTrue(result.error)
        self.assertEqual(result.rows[0].errlevel, 2)

    # --- Codex review: a mid-subscribe disconnect must fail, not look successful ---

    @patch("sql.engines.mqtt.time.monotonic", side_effect=[0, 0.01, 0.02, 60])
    @patch("sql.engines.mqtt.mqtt.Client")
    def test_run_subscribe_fails_on_disconnect(self, mock_client_cls, _mock_monotonic):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.subscribe.return_value = (0, 1)

        def connect_then_disconnect(*_a, **_k):
            mock_client.on_connect(mock_client, None, None, 0, None)
            mock_client.on_disconnect(mock_client, None, 0, 7, None)

        mock_client.loop_start.side_effect = connect_then_disconnect
        engine = MqttEngine(instance=self.ins)

        result = engine.run_subscribe(
            topic="archery/test", qos=0, max_msgs=5, timeout_sec=60
        )

        self.assertIn("断开", result.error)
