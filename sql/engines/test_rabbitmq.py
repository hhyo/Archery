# -*- coding: UTF-8 -*-
from unittest import TestCase
from unittest.mock import MagicMock, patch

from sql.engines.rabbitmq import RabbitmqEngine
from sql.models import Instance


class TestRabbitmqEngine(TestCase):
    def setUp(self):
        self.ins = Instance(
            instance_name="rmq_test",
            type="master",
            db_type="rabbitmq",
            host="127.0.0.1",
            port=5672,
            user="root",
            password="secret",
            db_name="/",
        )

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_test_connection_ok(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_conn.is_open = True
        mock_conn_cls.return_value = mock_conn
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.test_connection()
        self.assertFalse(result.error)
        mock_conn.close.assert_called()

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_client_cert_and_key_are_validated_without_ssl(self, mock_conn_cls):
        self.ins.is_ssl = False
        self.ins.client_cert = "CERT PEM"
        self.ins.client_key = ""
        engine = RabbitmqEngine(instance=self.ins)

        result = engine.test_connection()

        self.assertIn("必须同时配置", result.error)
        mock_conn_cls.assert_not_called()

    def test_query_check_allows_get(self):
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.query_check(sql="get queue=archery_test_queue count=1")
        self.assertFalse(result["bad_query"])

    def test_query_check_allows_list_queues(self):
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.query_check(sql="list queues")
        self.assertFalse(result["bad_query"])

    def test_query_check_allows_help(self):
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.query_check(sql="help")
        self.assertFalse(result["bad_query"])

    def test_query_check_blocks_publish(self):
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.query_check(sql="publish routing_key=q payload=x")
        self.assertTrue(result["bad_query"])

    def test_query_check_rejects_old_dsl(self):
        engine = RabbitmqEngine(instance=self.ins)
        for command in (
            "basic_get myqueue",
            "get myqueue",
            "queue_declare_passive myqueue",
        ):
            with self.subTest(command=command):
                self.assertTrue(engine.query_check(sql=command)["bad_query"])

    def test_rabbitmq_query_check_rejects_explain_prefix(self):
        engine = RabbitmqEngine(instance=self.ins)
        for sql in ("explain get queue=q count=1", "explain", "EXPLAIN\nget queue=q"):
            with self.subTest(sql=sql):
                out = engine.query_check(sql=sql)
                self.assertTrue(out["bad_query"])
                self.assertIn("不支持执行计划", out["msg"])

    def test_execute_check_allows_write_commands(self):
        engine = RabbitmqEngine(instance=self.ins)
        commands = [
            'publish routing_key=myqueue payload="hello"',
            "declare queue name=myqueue",
            "declare exchange name=myexchange type=direct",
            "declare binding queue=myqueue exchange=myexchange routing_key=rk",
            "purge queue name=myqueue",
            "delete queue name=myqueue",
        ]

        for command in commands:
            with self.subTest(command=command):
                result = engine.execute_check(sql=command)
                self.assertEqual(result.rows[0].errlevel, 0)

    def test_execute_check_rejects_get(self):
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.execute_check(sql="get queue=myqueue count=1")
        self.assertEqual(result.rows[0].errlevel, 2)
        self.assertEqual(result.rows[0].errormessage, "禁止使用查询命令！")

    def test_query_help(self):
        engine = RabbitmqEngine(instance=self.ins)

        result = engine.query(sql="help")

        self.assertEqual(result.error, None)
        self.assertIn(["get queue=<name> [count=N]"], result.rows)
        self.assertIn(["list queues"], result.rows)
        self.assertIn(["help"], result.rows)

    def test_query_list_queues_returns_management_api_error(self):
        engine = RabbitmqEngine(instance=self.ins)

        result = engine.query(sql="list queues")

        self.assertEqual(
            result.error,
            "list queues 需要 RabbitMQ Management API，当前引擎未启用",
        )

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_query_get_acks_and_returns_body(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_ch = MagicMock()
        mock_conn.channel.return_value = mock_ch
        mock_conn.is_open = True
        mock_conn_cls.return_value = mock_conn
        method = MagicMock()
        method.delivery_tag = 1
        method.routing_key = "archery_test_queue"
        mock_ch.basic_get.return_value = (method, MagicMock(), b"hello")
        engine = RabbitmqEngine(instance=self.ins)

        result = engine.query(db_name="/", sql="get queue=archery_test_queue count=1")

        mock_ch.basic_ack.assert_called_with(delivery_tag=1)
        self.assertEqual(
            result.rows, [["archery_test_queue", "archery_test_queue", "hello"]]
        )
        self.assertEqual(result.error, None)

    @patch("sql.engines.rabbitmq.time.sleep")
    @patch("sql.engines.rabbitmq.time.monotonic", side_effect=[0, 0.01, 0.02, 60])
    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_query_get_waits_on_empty_until_timeout(
        self, mock_conn_cls, _mock_monotonic, mock_sleep
    ):
        mock_conn = MagicMock()
        mock_ch = MagicMock()
        mock_conn.channel.return_value = mock_ch
        mock_conn.is_open = True
        mock_conn_cls.return_value = mock_conn
        mock_ch.basic_get.return_value = (None, None, None)
        engine = RabbitmqEngine(instance=self.ins)

        result = engine.query(sql="get queue=archery_test_queue count=1")

        self.assertEqual(result.rows, [])
        self.assertIn("超时", result.warning)
        self.assertIn("60", result.warning)
        self.assertTrue(mock_sleep.called)
        mock_ch.basic_ack.assert_not_called()

    @patch("sql.engines.rabbitmq.time.sleep")
    @patch("sql.engines.rabbitmq.time.monotonic", side_effect=[0, 0.01, 0.02, 60])
    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_run_get_honors_cancel_check_and_on_message(
        self, mock_conn_cls, _mock_monotonic, mock_sleep
    ):
        mock_conn = MagicMock()
        mock_ch = MagicMock()
        mock_conn.channel.return_value = mock_ch
        mock_conn.is_open = True
        mock_conn_cls.return_value = mock_conn
        mock_ch.basic_get.return_value = (None, None, None)
        engine = RabbitmqEngine(instance=self.ins)
        seen = []
        ticks = {"n": 0}

        def cancel_check():
            ticks["n"] += 1
            return ticks["n"] >= 2

        result = engine.run_get(
            queue="archery_test_queue",
            count=10,
            timeout_sec=60,
            cancel_check=cancel_check,
            on_message=seen.append,
        )

        self.assertEqual(result.error, None)
        self.assertEqual(result.rows, [])
        self.assertEqual(seen, [])
        self.assertTrue(mock_ch.basic_get.called)
        self.assertTrue(mock_sleep.called)

    @patch("sql.engines.rabbitmq.time.sleep")
    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_run_get_collects_messages_and_calls_on_message(
        self, mock_conn_cls, mock_sleep
    ):
        mock_conn = MagicMock()
        mock_ch = MagicMock()
        mock_conn.channel.return_value = mock_ch
        mock_conn.is_open = True
        mock_conn_cls.return_value = mock_conn
        method1 = MagicMock(delivery_tag=1, routing_key="rk1")
        method2 = MagicMock(delivery_tag=2, routing_key="rk2")
        mock_ch.basic_get.side_effect = [
            (None, None, None),
            (method1, MagicMock(), b"one"),
            (method2, MagicMock(), b"two"),
        ]
        engine = RabbitmqEngine(instance=self.ins)
        seen = []

        result = engine.run_get(
            queue="q1",
            count=2,
            timeout_sec=60,
            on_message=seen.append,
        )

        self.assertEqual(
            result.rows,
            [["q1", "rk1", "one"], ["q1", "rk2", "two"]],
        )
        self.assertEqual(seen, result.rows)
        self.assertEqual(mock_ch.basic_ack.call_count, 2)
        self.assertTrue(mock_sleep.called)

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_execute_workflow_publish(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_ch = MagicMock()
        mock_conn.channel.return_value = mock_ch
        mock_conn.is_open = True
        mock_conn_cls.return_value = mock_conn
        workflow = MagicMock()
        workflow.db_name = "/"
        workflow.sqlworkflowcontent.sql_content = (
            'publish routing_key=myqueue payload="hello"'
        )
        engine = RabbitmqEngine(instance=self.ins)

        result = engine.execute_workflow(workflow)

        mock_ch.basic_publish.assert_called_once_with(
            exchange="", routing_key="myqueue", body="hello"
        )
        self.assertEqual(result.rows[0].errlevel, 0)
        mock_conn.close.assert_called_once()

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_execute_workflow_declare_and_purge(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_ch = MagicMock()
        mock_conn.channel.return_value = mock_ch
        mock_conn.is_open = True
        mock_conn_cls.return_value = mock_conn
        workflow = MagicMock()
        workflow.db_name = "/"
        workflow.sqlworkflowcontent.sql_content = "\n".join(
            [
                "declare queue name=myqueue",
                "declare exchange name=myexchange type=topic",
                "declare binding queue=myqueue exchange=myexchange routing_key=rk",
                "purge queue name=myqueue",
                "delete queue name=myqueue",
            ]
        )
        engine = RabbitmqEngine(instance=self.ins)

        result = engine.execute_workflow(workflow)

        mock_ch.queue_declare.assert_called_once_with(queue="myqueue")
        mock_ch.exchange_declare.assert_called_once_with(
            exchange="myexchange", exchange_type="topic"
        )
        mock_ch.queue_bind.assert_called_once_with(
            queue="myqueue", exchange="myexchange", routing_key="rk"
        )
        mock_ch.queue_purge.assert_called_once_with(queue="myqueue")
        mock_ch.queue_delete.assert_called_once_with(queue="myqueue")
        self.assertEqual(len(result.rows), 5)
        self.assertTrue(all(row.errlevel == 0 for row in result.rows))

    def test_queue_declare_passes_durable(self):
        from sql.engines.mq_cli import parse_rabbitmq_line

        channel = MagicMock()
        cmd = parse_rabbitmq_line("declare queue name=q1 durable=true")
        RabbitmqEngine._execute_write_command(channel, cmd)
        channel.queue_declare.assert_called_once_with(queue="q1", durable=True)
