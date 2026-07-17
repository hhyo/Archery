# -*- coding: UTF-8 -*-
import logging
import os
import shlex
import ssl
import tempfile

import pika

from . import EngineBase
from .models import ResultSet

logger = logging.getLogger("default")


class RabbitmqEngine(EngineBase):
    name = "RabbitMQ"
    info = "RabbitMQ engine"

    def _vhost(self, db_name=None):
        return db_name or self.db_name or "/"

    def _validate_certs(self):
        cert = self.instance.client_cert or ""
        key = self.instance.client_key or ""
        if bool(cert) != bool(key):
            raise ValueError("客户端证书和客户端密钥必须同时配置")
        return cert, key

    @staticmethod
    def _write_temp_pem(content):
        pem = tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False)
        try:
            pem.write(content)
            return pem.name
        finally:
            pem.close()

    def _ssl_options(self):
        if not self.instance.is_ssl:
            return None

        cert, key = self._validate_certs()
        ca_cert = self.instance.ca_cert or ""
        temp_paths = []
        try:
            if ca_cert:
                ca_path = self._write_temp_pem(ca_cert)
                temp_paths.append(ca_path)
                context = ssl.create_default_context(cafile=ca_path)
            else:
                context = ssl.create_default_context()

            if not self.instance.verify_ssl:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE

            if cert:
                cert_path = self._write_temp_pem(cert)
                key_path = self._write_temp_pem(key)
                temp_paths.extend((cert_path, key_path))
                context.load_cert_chain(certfile=cert_path, keyfile=key_path)

            return pika.SSLOptions(context, self.host)
        finally:
            for path in temp_paths:
                try:
                    os.unlink(path)
                except OSError:
                    logger.warning("清理 RabbitMQ 临时证书文件失败: %s", path)

    def get_connection(self, db_name=None):
        parameters = {
            "host": self.host,
            "port": self.port,
            "virtual_host": self._vhost(db_name),
            "socket_timeout": 10,
            "blocked_connection_timeout": 10,
        }
        if self.user:
            parameters["credentials"] = pika.PlainCredentials(
                self.user, self.password or ""
            )
        ssl_options = self._ssl_options()
        if ssl_options:
            parameters["ssl_options"] = ssl_options
        return pika.BlockingConnection(pika.ConnectionParameters(**parameters))

    def test_connection(self):
        result = ResultSet(full_sql="connection")
        conn = None
        try:
            conn = self.get_connection()
            if not conn.is_open:
                raise ConnectionError("RabbitMQ 连接未打开")
            result.column_list = ["状态"]
            result.rows = [["连接成功"]]
            result.affected_rows = 1
        except Exception as exc:
            result.error = str(exc)
        finally:
            if conn is not None and conn.is_open:
                conn.close()
        return result

    def get_all_databases(self, **kwargs):
        vhost = self._vhost()
        return ResultSet(rows=[{"value": vhost, "text": vhost}])

    def get_all_tables(self, db_name, **kwargs):
        return ResultSet(rows=[])

    def query_check(self, db_name=None, sql=""):
        filtered_sql = sql.strip()
        try:
            parts = shlex.split(filtered_sql)
        except ValueError as exc:
            return {
                "bad_query": True,
                "filtered_sql": filtered_sql,
                "msg": str(exc),
            }

        allowed = {"basic_get", "get", "queue_declare_passive", "help"}
        bad_query = not parts or parts[0].lower() not in allowed
        return {
            "bad_query": bad_query,
            "filtered_sql": filtered_sql,
            "msg": "禁止执行该命令！" if bad_query else "",
        }

    def query(
        self,
        db_name=None,
        sql="",
        limit_num=0,
        close_conn=True,
        parameters=None,
        **kwargs,
    ):
        result = ResultSet(full_sql=sql)
        conn = None
        try:
            parts = shlex.split(sql)
            if not parts:
                raise ValueError("命令不能为空")
            command = parts[0].lower()

            if command == "help":
                result.column_list = ["命令"]
                result.rows = [
                    ["basic_get <queue>"],
                    ["get <queue>"],
                    ["queue_declare_passive <queue>"],
                    ["help"],
                ]
            else:
                if len(parts) != 2:
                    raise ValueError(f"{command} 命令需要且仅需要一个队列名")
                queue = parts[1]
                conn = self.get_connection(db_name)
                channel = conn.channel()

                if command in {"basic_get", "get"}:
                    method, properties, body = channel.basic_get(
                        queue=queue, auto_ack=False
                    )
                    result.column_list = ["queue", "routing_key", "body"]
                    if method is not None:
                        channel.basic_ack(delivery_tag=method.delivery_tag)
                        payload = (
                            body.decode("utf-8", errors="replace")
                            if isinstance(body, bytes)
                            else body
                        )
                        result.rows = [[queue, method.routing_key, payload]]
                elif command == "queue_declare_passive":
                    declared = channel.queue_declare(queue=queue, passive=True)
                    method = declared.method
                    result.column_list = ["queue", "message_count", "consumer_count"]
                    result.rows = [
                        [method.queue, method.message_count, method.consumer_count]
                    ]
                else:
                    raise ValueError("禁止执行该命令！")

            if limit_num > 0:
                result.rows = result.rows[:limit_num]
            result.affected_rows = len(result.rows)
        except Exception as exc:
            logger.warning("RabbitMQ 查询执行失败: %s", exc)
            result.error = str(exc)
        finally:
            if close_conn and conn is not None and conn.is_open:
                conn.close()
        return result
