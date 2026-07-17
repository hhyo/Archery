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

    def test_query_check_allows_basic_get(self):
        engine = RabbitmqEngine(instance=self.ins)
        r = engine.query_check(sql="basic_get myqueue")
        self.assertFalse(r["bad_query"])

    def test_query_check_blocks_publish(self):
        engine = RabbitmqEngine(instance=self.ins)
        r = engine.query_check(sql='publish amq.default rk "hi"')
        self.assertTrue(r["bad_query"])

    @patch("sql.engines.rabbitmq.pika.BlockingConnection")
    def test_basic_get_auto_ack(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_ch = MagicMock()
        mock_conn.channel.return_value = mock_ch
        mock_conn_cls.return_value = mock_conn
        method = MagicMock()
        method.delivery_tag = 1
        method.routing_key = "myqueue"
        mock_ch.basic_get.return_value = (method, MagicMock(), b"hello")
        engine = RabbitmqEngine(instance=self.ins)
        result = engine.query(db_name="/", sql="basic_get myqueue")
        mock_ch.basic_ack.assert_called_with(delivery_tag=1)
        self.assertIn("hello", str(result.rows))
