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

    def test_query_check_rejects_list(self):
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.query_check(sql="list queues")
        self.assertTrue(result["bad_query"])
        self.assertTrue(
            "Management" in result["msg"] or "不支持" in result["msg"],
            result["msg"],
        )

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
            "declare binding source=myexchange destination=myqueue routing_key=rk",
            "purge queue name=myqueue",
            "delete queue name=myqueue",
            "delete exchange name=myexchange",
            "delete binding source=myexchange destination=myqueue",
        ]

        for command in commands:
            with self.subTest(command=command):
                result = engine.execute_check(sql=command)
                self.assertEqual(result.rows[0].errlevel, 0)

    def test_execute_check_rejects_legacy_binding(self):
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.execute_check(
            sql="declare binding queue=myqueue exchange=myexchange routing_key=rk"
        )
        self.assertEqual(result.rows[0].errlevel, 2)

    def test_execute_check_rejects_get(self):
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.execute_check(sql="get queue=myqueue count=1")
        self.assertEqual(result.rows[0].errlevel, 2)
        self.assertEqual(result.rows[0].errormessage, "禁止使用查询命令！")

    def test_query_help(self):
        engine = RabbitmqEngine(instance=self.ins)

        result = engine.query(sql="help")

        self.assertEqual(result.error, None)
        self.assertTrue(
            any("ackmode" in row[0] for row in result.rows),
            result.rows,
        )
        self.assertTrue(
            any(
                "source=" in row[0] and "destination=" in row[0] for row in result.rows
            ),
            result.rows,
        )
        self.assertFalse(any("list queues" in row[0] for row in result.rows))
        self.assertIn(["help"], result.rows)

    def test_query_list_queues_fails_at_parse(self):
        engine = RabbitmqEngine(instance=self.ins)

        result = engine.query(sql="list queues")

        self.assertTrue(result.error)
        self.assertTrue(
            "Management" in result.error or "不支持" in result.error,
            result.error,
        )

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_query_get_default_ackmode_requeues_and_returns_body(self, mock_conn_cls):
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

        mock_ch.basic_ack.assert_not_called()
        requeued = False
        if mock_ch.basic_nack.called:
            kwargs = mock_ch.basic_nack.call_args.kwargs
            requeued = kwargs.get("requeue") is True
        elif mock_ch.basic_reject.called:
            kwargs = mock_ch.basic_reject.call_args.kwargs
            requeued = kwargs.get("requeue") is True
        self.assertTrue(requeued)
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
            ackmode="ack_requeue_false",
        )

        self.assertEqual(
            result.rows,
            [["q1", "rk1", "one"], ["q1", "rk2", "two"]],
        )
        self.assertEqual(seen, result.rows)
        self.assertEqual(mock_ch.basic_ack.call_count, 2)
        self.assertTrue(mock_sleep.called)

    def _mock_get_once(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_ch = MagicMock()
        mock_conn.channel.return_value = mock_ch
        mock_conn.is_open = True
        mock_conn_cls.return_value = mock_conn
        method = MagicMock(delivery_tag=7, routing_key="rk")
        mock_ch.basic_get.side_effect = [
            (method, MagicMock(), b"body"),
            (None, None, None),
        ]
        return mock_ch

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_run_get_ackmode_ack_requeue_false_acks(self, mock_conn_cls):
        mock_ch = self._mock_get_once(mock_conn_cls)
        engine = RabbitmqEngine(instance=self.ins)

        result = engine.run_get(
            queue="q",
            count=1,
            timeout_sec=60,
            ackmode="ack_requeue_false",
        )

        mock_ch.basic_ack.assert_called_once_with(delivery_tag=7)
        mock_ch.basic_nack.assert_not_called()
        mock_ch.basic_reject.assert_not_called()
        self.assertEqual(result.rows, [["q", "rk", "body"]])

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_run_get_ackmode_ack_requeue_true_requeues(self, mock_conn_cls):
        mock_ch = self._mock_get_once(mock_conn_cls)
        engine = RabbitmqEngine(instance=self.ins)

        engine.run_get(queue="q", count=1, timeout_sec=60, ackmode="ack_requeue_true")

        mock_ch.basic_ack.assert_not_called()
        if mock_ch.basic_nack.called:
            mock_ch.basic_nack.assert_called_once_with(delivery_tag=7, requeue=True)
        else:
            mock_ch.basic_reject.assert_called_once_with(delivery_tag=7, requeue=True)

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_run_get_ackmode_reject_requeue_true(self, mock_conn_cls):
        mock_ch = self._mock_get_once(mock_conn_cls)
        engine = RabbitmqEngine(instance=self.ins)

        engine.run_get(
            queue="q", count=1, timeout_sec=60, ackmode="reject_requeue_true"
        )

        mock_ch.basic_ack.assert_not_called()
        mock_ch.basic_reject.assert_called_once_with(delivery_tag=7, requeue=True)

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_run_get_ackmode_reject_requeue_false(self, mock_conn_cls):
        mock_ch = self._mock_get_once(mock_conn_cls)
        engine = RabbitmqEngine(instance=self.ins)

        engine.run_get(
            queue="q", count=1, timeout_sec=60, ackmode="reject_requeue_false"
        )

        mock_ch.basic_ack.assert_not_called()
        mock_ch.basic_reject.assert_called_once_with(delivery_tag=7, requeue=False)

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_query_passes_ackmode_to_run_get(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_ch = MagicMock()
        mock_conn.channel.return_value = mock_ch
        mock_conn.is_open = True
        mock_conn_cls.return_value = mock_conn
        method = MagicMock(delivery_tag=1, routing_key="rk")
        mock_ch.basic_get.return_value = (method, MagicMock(), b"x")
        engine = RabbitmqEngine(instance=self.ins)

        engine.query(sql="get queue=q count=1 ackmode=ack_requeue_false")

        mock_ch.basic_ack.assert_called_once_with(delivery_tag=1)

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

        mock_ch.confirm_delivery.assert_called_once_with()
        mock_ch.basic_publish.assert_called_once_with(
            exchange="",
            routing_key="myqueue",
            body="hello",
            mandatory=True,
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
                "declare queue name=myqueue auto_delete=true",
                "declare exchange name=myexchange type=topic durable=true",
                "declare binding source=myexchange destination=myqueue routing_key=rk",
                "purge queue name=myqueue",
                "delete queue name=myqueue",
            ]
        )
        engine = RabbitmqEngine(instance=self.ins)

        result = engine.execute_workflow(workflow)

        mock_ch.queue_declare.assert_called_once_with(queue="myqueue", auto_delete=True)
        mock_ch.exchange_declare.assert_called_once_with(
            exchange="myexchange", exchange_type="topic", durable=True
        )
        mock_ch.queue_bind.assert_called_once_with(
            queue="myqueue", exchange="myexchange", routing_key="rk"
        )
        mock_ch.queue_purge.assert_called_once_with(queue="myqueue")
        mock_ch.queue_delete.assert_called_once_with(queue="myqueue")
        self.assertEqual(len(result.rows), 5)
        self.assertTrue(all(row.errlevel == 0 for row in result.rows))

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_execute_declare_binding_official(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_ch = MagicMock()
        mock_conn.channel.return_value = mock_ch
        mock_conn.is_open = True
        mock_conn_cls.return_value = mock_conn
        workflow = MagicMock()
        workflow.db_name = "/"
        workflow.sqlworkflowcontent.sql_content = (
            "declare binding source=demo.ex destination=demo.q routing_key=demo.q"
        )
        engine = RabbitmqEngine(instance=self.ins)

        result = engine.execute_workflow(workflow)

        mock_ch.queue_bind.assert_called_once_with(
            queue="demo.q", exchange="demo.ex", routing_key="demo.q"
        )
        self.assertEqual(result.rows[0].errlevel, 0)

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_execute_delete_exchange(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_ch = MagicMock()
        mock_conn.channel.return_value = mock_ch
        mock_conn.is_open = True
        mock_conn_cls.return_value = mock_conn
        workflow = MagicMock()
        workflow.db_name = "/"
        workflow.sqlworkflowcontent.sql_content = "delete exchange name=demo.ex"
        engine = RabbitmqEngine(instance=self.ins)

        result = engine.execute_workflow(workflow)

        mock_ch.exchange_delete.assert_called_once_with(exchange="demo.ex")
        self.assertEqual(result.rows[0].errlevel, 0)

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_execute_delete_binding(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_ch = MagicMock()
        mock_conn.channel.return_value = mock_ch
        mock_conn.is_open = True
        mock_conn_cls.return_value = mock_conn
        workflow = MagicMock()
        workflow.db_name = "/"
        workflow.sqlworkflowcontent.sql_content = (
            "delete binding source=demo.ex destination=demo.q properties_key=rk"
        )
        engine = RabbitmqEngine(instance=self.ins)

        result = engine.execute_workflow(workflow)

        mock_ch.queue_unbind.assert_called_once_with(
            queue="demo.q", exchange="demo.ex", routing_key="rk"
        )
        self.assertEqual(result.rows[0].errlevel, 0)

    def test_queue_declare_passes_durable(self):
        from sql.engines.mq_cli import parse_rabbitmq_line

        channel = MagicMock()
        cmd = parse_rabbitmq_line("declare queue name=q1 durable=true")
        RabbitmqEngine._execute_write_command(channel, cmd)
        channel.queue_declare.assert_called_once_with(queue="q1", durable=True)

    def test_queue_declare_passes_auto_delete(self):
        from sql.engines.mq_cli import parse_rabbitmq_line

        channel = MagicMock()
        cmd = parse_rabbitmq_line("declare queue name=q1 auto_delete=true")
        RabbitmqEngine._execute_write_command(channel, cmd)
        channel.queue_declare.assert_called_once_with(queue="q1", auto_delete=True)

    def test_publish_unroutable_raises(self):
        import pika.exceptions
        from sql.engines.mq_cli import parse_rabbitmq_line

        cmd_publish = parse_rabbitmq_line('publish routing_key=q1 payload="hello"')

        class Ch:
            def __init__(self):
                self.confirmed = False

            def confirm_delivery(self):
                self.confirmed = True

            def basic_publish(self, **kwargs):
                assert kwargs.get("mandatory") is True
                raise pika.exceptions.UnroutableError("x")

        channel = Ch()
        with self.assertRaises((pika.exceptions.UnroutableError, ValueError)):
            RabbitmqEngine._execute_write_command(channel, cmd_publish)
        self.assertTrue(channel.confirmed)

    def test_publish_calls_confirm_delivery(self):
        from sql.engines.mq_cli import parse_rabbitmq_line

        channel = MagicMock()
        cmd = parse_rabbitmq_line('publish routing_key=q1 payload="hello"')
        RabbitmqEngine._execute_write_command(channel, cmd)
        channel.confirm_delivery.assert_called_once_with()
        channel.basic_publish.assert_called_once_with(
            exchange="",
            routing_key="q1",
            body="hello",
            mandatory=True,
        )

    def test_validate_query_command_requires_queue_and_positive_count(self):
        from sql.engines.mq_cli import MqCommand

        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_query_command(
                MqCommand(engine="rabbitmq", action="publish", args={}, raw_line="")
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_query_command(
                MqCommand(
                    engine="rabbitmq",
                    action="get",
                    args={"count": 1},
                    raw_line="",
                )
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_query_command(
                MqCommand(
                    engine="rabbitmq",
                    action="get",
                    args={"queue": "q", "count": 0},
                    raw_line="",
                )
            )

    def test_validate_write_command_missing_required(self):
        from sql.engines.mq_cli import MqCommand

        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_write_command(
                MqCommand(engine="rabbitmq", action="get", args={}, raw_line="")
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_write_command(
                MqCommand(
                    engine="rabbitmq",
                    action="publish",
                    args={"payload": "x"},
                    raw_line="",
                )
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_write_command(
                MqCommand(
                    engine="rabbitmq",
                    action="publish",
                    args={"routing_key": "q"},
                    raw_line="",
                )
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_write_command(
                MqCommand(
                    engine="rabbitmq",
                    action="declare",
                    args={"target": "queue"},
                    raw_line="",
                )
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_write_command(
                MqCommand(
                    engine="rabbitmq",
                    action="declare",
                    args={"target": "exchange"},
                    raw_line="",
                )
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_write_command(
                MqCommand(
                    engine="rabbitmq",
                    action="declare",
                    args={"target": "exchange", "name": "ex"},
                    raw_line="",
                )
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_write_command(
                MqCommand(
                    engine="rabbitmq",
                    action="declare",
                    args={"target": "binding", "source": "ex"},
                    raw_line="",
                )
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_write_command(
                MqCommand(
                    engine="rabbitmq",
                    action="purge",
                    args={"target": "queue"},
                    raw_line="",
                )
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_write_command(
                MqCommand(
                    engine="rabbitmq",
                    action="delete",
                    args={"target": "queue"},
                    raw_line="",
                )
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_write_command(
                MqCommand(
                    engine="rabbitmq",
                    action="delete",
                    args={"target": "exchange"},
                    raw_line="",
                )
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_write_command(
                MqCommand(
                    engine="rabbitmq",
                    action="delete",
                    args={"target": "binding", "source": "ex"},
                    raw_line="",
                )
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._validate_write_command(
                MqCommand(
                    engine="rabbitmq",
                    action="delete",
                    args={"target": "fanout", "name": "x"},
                    raw_line="",
                )
            )

    def test_apply_get_ackmode_rejects_unknown(self):
        channel = MagicMock()
        with self.assertRaises(ValueError):
            RabbitmqEngine._apply_get_ackmode(channel, 1, "not_a_mode")

    def test_exchange_declare_passes_auto_delete(self):
        from sql.engines.mq_cli import parse_rabbitmq_line

        channel = MagicMock()
        cmd = parse_rabbitmq_line(
            "declare exchange name=ex1 type=fanout auto_delete=true"
        )
        RabbitmqEngine._execute_write_command(channel, cmd)
        channel.exchange_declare.assert_called_once_with(
            exchange="ex1", exchange_type="fanout", auto_delete=True
        )

    def test_execute_write_rejects_unknown_declare_delete_target(self):
        from sql.engines.mq_cli import MqCommand

        channel = MagicMock()
        with self.assertRaises(ValueError):
            RabbitmqEngine._execute_write_command(
                channel,
                MqCommand(
                    engine="rabbitmq",
                    action="declare",
                    args={"target": "fanout", "name": "x"},
                    raw_line="",
                ),
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._execute_write_command(
                channel,
                MqCommand(
                    engine="rabbitmq",
                    action="delete",
                    args={"target": "fanout", "name": "x"},
                    raw_line="",
                ),
            )
        with self.assertRaises(ValueError):
            RabbitmqEngine._execute_write_command(
                channel,
                MqCommand(
                    engine="rabbitmq",
                    action="help",
                    args={},
                    raw_line="",
                ),
            )
