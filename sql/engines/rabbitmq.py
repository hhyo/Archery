# -*- coding: UTF-8 -*-
import logging
import os
import shlex
import ssl
import tempfile

import pika

from common.utils.timer import FuncTimer
from . import EngineBase
from .models import ResultSet, ReviewResult, ReviewSet

logger = logging.getLogger("default")


class RabbitmqEngine(EngineBase):
    name = "RabbitMQ"
    info = "RabbitMQ engine"
    write_commands = {
        "publish",
        "queue_declare",
        "exchange_declare",
        "queue_bind",
        "purge",
        "queue_purge",
        "queue_delete",
    }

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
        cert, key = self._validate_certs()
        if not self.instance.is_ssl:
            return None

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

    def execute_check(self, db_name=None, sql=""):
        """审核 RabbitMQ 上线写命令。"""
        check_result = ReviewSet(full_sql=sql)
        statements = [command.strip() for command in sql.splitlines() if command.strip()]

        for line, statement in enumerate(statements, start=1):
            query_result = self.query_check(db_name=db_name, sql=statement)
            if not query_result["bad_query"]:
                errlevel = 2
                status = "Audit failed"
                message = "禁止使用查询命令！"
            else:
                try:
                    parts = shlex.split(statement)
                except ValueError:
                    parts = []
                is_allowed = bool(parts) and parts[0].lower() in self.write_commands
                errlevel = 0 if is_allowed else 2
                status = "Audit completed" if is_allowed else "Audit failed"
                message = "暂不支持显示影响行数" if is_allowed else "禁止执行该命令！"

            check_result.rows.append(
                ReviewResult(
                    id=line,
                    errlevel=errlevel,
                    stagestatus=status,
                    errormessage=message,
                    sql=statement,
                    affected_rows=0,
                    execute_time=0,
                )
            )
        return check_result

    @staticmethod
    def _execute_write_command(channel, statement):
        parts = shlex.split(statement)
        if not parts:
            raise ValueError("命令不能为空")

        command = parts[0].lower()
        if command == "publish":
            if len(parts) != 4:
                raise ValueError("publish 命令格式：publish <exchange> <routing_key> <body>")
            channel.basic_publish(
                exchange=parts[1], routing_key=parts[2], body=parts[3]
            )
        elif command == "queue_declare":
            if len(parts) != 2:
                raise ValueError("queue_declare 命令格式：queue_declare <queue>")
            channel.queue_declare(queue=parts[1])
        elif command == "exchange_declare":
            if len(parts) not in {2, 3}:
                raise ValueError(
                    "exchange_declare 命令格式：exchange_declare <exchange> [type]"
                )
            channel.exchange_declare(
                exchange=parts[1],
                exchange_type=parts[2] if len(parts) == 3 else "direct",
            )
        elif command == "queue_bind":
            if len(parts) not in {3, 4}:
                raise ValueError(
                    "queue_bind 命令格式：queue_bind <queue> <exchange> [routing_key]"
                )
            channel.queue_bind(
                queue=parts[1],
                exchange=parts[2],
                routing_key=parts[3] if len(parts) == 4 else "",
            )
        elif command in {"purge", "queue_purge"}:
            if len(parts) != 2:
                raise ValueError(f"{command} 命令格式：{command} <queue>")
            channel.queue_purge(queue=parts[1])
        elif command == "queue_delete":
            if len(parts) != 2:
                raise ValueError("queue_delete 命令格式：queue_delete <queue>")
            channel.queue_delete(queue=parts[1])
        else:
            raise ValueError("禁止执行该命令！")

    def execute_workflow(self, workflow):
        """执行 RabbitMQ 上线工单。"""
        sql = workflow.sqlworkflowcontent.sql_content
        statements = [command.strip() for command in sql.splitlines() if command.strip()]
        execute_result = ReviewSet(full_sql=sql)
        conn = None
        line = 1
        statement = None
        try:
            conn = self.get_connection(db_name=workflow.db_name)
            channel = conn.channel()
            for statement in statements:
                with FuncTimer() as timer:
                    self._execute_write_command(channel, statement)
                execute_result.rows.append(
                    ReviewResult(
                        id=line,
                        errlevel=0,
                        stagestatus="Execute Successfully",
                        errormessage="暂不支持显示影响行数",
                        sql=statement,
                        affected_rows=0,
                        execute_time=timer.cost,
                    )
                )
                line += 1
        except Exception as exc:
            logger.warning(
                "RabbitMQ 命令执行失败，语句：%s，错误信息：%s",
                statement or sql,
                exc,
            )
            execute_result.error = str(exc)
            execute_result.rows.append(
                ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="Execute Failed",
                    errormessage=f"异常信息：{exc}",
                    sql=statement,
                    affected_rows=0,
                    execute_time=0,
                )
            )
            line += 1
            for pending_statement in statements[line - 1 :]:
                execute_result.rows.append(
                    ReviewResult(
                        id=line,
                        errlevel=0,
                        stagestatus="Audit completed",
                        errormessage="前序语句失败, 未执行",
                        sql=pending_statement,
                        affected_rows=0,
                        execute_time=0,
                    )
                )
                line += 1
        finally:
            if conn is not None and conn.is_open:
                conn.close()
        return execute_result
