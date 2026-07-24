# -*- coding: UTF-8 -*-
import logging
import os
import ssl
import tempfile
import time

import pika

from common.utils.timer import FuncTimer
from . import EngineBase
from .models import ResultSet, ReviewResult, ReviewSet
from .mq_cli import parse_rabbitmq_line, split_mq_lines

logger = logging.getLogger("default")

RABBITMQ_HELP_ROWS = [
    ["get queue=<name> [count=N] [ackmode=…]"],
    ["publish routing_key=… payload=… [exchange=…]"],
    ["declare queue name=… [durable=…] [auto_delete=…]"],
    ["declare exchange name=… type=… [durable=…] [auto_delete=…]"],
    ["declare binding source=… destination=… [routing_key=…]"],
    ["purge queue name=…"],
    ["delete queue name=…"],
    ["delete exchange name=…"],
    [
        "delete binding source=… destination=… "
        "[destination_type=queue] [properties_key=…]"
    ],
    ["help"],
]
DEFAULT_QUERY_TIMEOUT_SEC = 60
MAX_QUERY_TIMEOUT_SEC = 3600
MAX_GET_COUNT = 100


class RabbitmqEngine(EngineBase):
    name = "RabbitMQ"
    info = "RabbitMQ engine"
    write_commands = {"publish", "declare", "purge", "delete"}

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

    @classmethod
    def _validate_query_command(cls, cmd):
        if cmd.action not in {"get", "help"}:
            raise ValueError("禁止执行该命令！")
        if cmd.action == "help":
            return
        if "queue" not in cmd.args:
            raise ValueError("get requires queue")
        count = cmd.args.get("count", 1)
        if not isinstance(count, int) or count <= 0:
            raise ValueError("count 必须为正整数")

    @classmethod
    def _validate_write_command(cls, cmd):
        if cmd.action not in cls.write_commands:
            raise ValueError("禁止执行该命令！")
        if cmd.action == "publish":
            if "routing_key" not in cmd.args:
                raise ValueError("publish requires routing_key")
            if "payload" not in cmd.args:
                raise ValueError("publish requires payload")
        elif cmd.action == "declare":
            target = cmd.args.get("target")
            if target == "queue" and "name" not in cmd.args:
                raise ValueError("declare queue requires name")
            if target == "exchange":
                if "name" not in cmd.args:
                    raise ValueError("declare exchange requires name")
                if "type" not in cmd.args:
                    raise ValueError("declare exchange requires type")
            if target == "binding":
                for key in ("source", "destination"):
                    if key not in cmd.args:
                        raise ValueError(f"declare binding requires {key}")
        elif cmd.action == "purge":
            if cmd.args.get("target") != "queue" or "name" not in cmd.args:
                raise ValueError("purge queue requires name")
        elif cmd.action == "delete":
            target = cmd.args.get("target")
            if target == "queue":
                if "name" not in cmd.args:
                    raise ValueError("delete queue requires name")
            elif target == "exchange":
                if "name" not in cmd.args:
                    raise ValueError("delete exchange requires name")
            elif target == "binding":
                for key in ("source", "destination"):
                    if key not in cmd.args:
                        raise ValueError(f"delete binding requires {key}")
            else:
                raise ValueError("delete requires queue, exchange, or binding")

    @staticmethod
    def _clamp_timeout_sec(timeout_sec):
        try:
            value = int(timeout_sec)
        except (TypeError, ValueError) as exc:
            raise ValueError("timeout_sec 必须为正整数") from exc
        if value <= 0:
            raise ValueError("timeout_sec 必须为正整数")
        return min(value, MAX_QUERY_TIMEOUT_SEC)

    def query_check(self, db_name=None, sql=""):
        filtered_sql = sql.strip()
        lowered = filtered_sql.lower()
        if (
            lowered.startswith("explain ")
            or lowered.startswith("explain\n")
            or lowered == "explain"
        ):
            return {
                "bad_query": True,
                "filtered_sql": filtered_sql,
                "msg": "MQTT/RabbitMQ 不支持执行计划",
            }
        try:
            lines = split_mq_lines(filtered_sql)
            if not lines:
                raise ValueError("empty rabbitmq command")
            for line in lines:
                cmd = parse_rabbitmq_line(line)
                self._validate_query_command(cmd)
        except ValueError as exc:
            return {
                "bad_query": True,
                "filtered_sql": filtered_sql,
                "msg": str(exc),
            }
        return {"bad_query": False, "filtered_sql": filtered_sql, "msg": ""}

    def run_get(
        self,
        queue,
        count,
        timeout_sec,
        cancel_check=None,
        on_message=None,
        db_name=None,
        close_conn=True,
        limit_num=0,
        full_sql="",
        ackmode="ack_requeue_true",
    ):
        result = ResultSet(
            full_sql=full_sql, column_list=["queue", "routing_key", "body"]
        )
        conn = None
        rows = []
        delivery_tags = []
        try:
            conn = self.get_connection(db_name)
            channel = conn.channel()
            started_at = time.monotonic()
            cancelled = False
            while len(rows) < count and time.monotonic() - started_at < timeout_sec:
                if cancel_check and cancel_check():
                    cancelled = True
                    break
                method, _properties, body = channel.basic_get(
                    queue=queue, auto_ack=False
                )
                if method is not None:
                    payload = (
                        body.decode("utf-8", errors="replace")
                        if isinstance(body, bytes)
                        else body
                    )
                    row = [queue, method.routing_key, payload]
                    rows.append(row)
                    delivery_tags.append(method.delivery_tag)
                    if on_message is not None:
                        on_message(row)
                else:
                    time.sleep(0.05)

            if limit_num > 0:
                rows = rows[:limit_num]
                delivery_tags = delivery_tags[:limit_num]
            # Apply the ackmode only AFTER the whole batch is fetched.
            # Requeueing each delivery before the next basic_get made that same
            # head message eligible again, so count>1 with ack_requeue_true /
            # reject_requeue_true returned duplicates instead of a batch of
            # distinct messages (Codex #7).
            for delivery_tag in delivery_tags:
                self._apply_get_ackmode(channel, delivery_tag, ackmode)
            result.rows = rows
            result.affected_rows = len(rows)
            if not rows and not cancelled:
                result.warning = f"获取等待 {timeout_sec} 秒超时，未收到消息"
        except Exception as exc:
            logger.warning("RabbitMQ get 执行失败: %s", exc)
            result.error = str(exc)
        finally:
            if close_conn and conn is not None and conn.is_open:
                conn.close()
        return result

    @staticmethod
    def _apply_get_ackmode(channel, delivery_tag, ackmode):
        if ackmode == "ack_requeue_false":
            channel.basic_ack(delivery_tag=delivery_tag)
        elif ackmode == "ack_requeue_true":
            channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
        elif ackmode == "reject_requeue_true":
            channel.basic_reject(delivery_tag=delivery_tag, requeue=True)
        elif ackmode == "reject_requeue_false":
            channel.basic_reject(delivery_tag=delivery_tag, requeue=False)
        else:
            raise ValueError(f"invalid ackmode: {ackmode}")

    def query(
        self,
        db_name=None,
        sql="",
        limit_num=0,
        close_conn=True,
        parameters=None,
        **kwargs,
    ):
        result = ResultSet(full_sql=sql, column_list=["queue", "routing_key", "body"])
        try:
            lines = split_mq_lines(sql)
            if not lines:
                raise ValueError("empty rabbitmq command")
            commands = [parse_rabbitmq_line(line) for line in lines]
            for cmd in commands:
                self._validate_query_command(cmd)

            help_only = all(cmd.action == "help" for cmd in commands)
            if help_only:
                result.column_list = ["命令"]
                result.rows = list(RABBITMQ_HELP_ROWS)
                result.affected_rows = len(result.rows)
                return result

            timeout_sec = self._clamp_timeout_sec(
                kwargs.get("timeout_sec", DEFAULT_QUERY_TIMEOUT_SEC)
            )
            aggregated = []
            warning = None
            for cmd in commands:
                if cmd.action == "help":
                    continue
                max_msgs = min(int(cmd.args.get("count", 1)), MAX_GET_COUNT)
                get_result = self.run_get(
                    queue=cmd.args["queue"],
                    count=max_msgs,
                    timeout_sec=timeout_sec,
                    cancel_check=None,
                    on_message=None,
                    db_name=db_name,
                    close_conn=close_conn,
                    limit_num=limit_num,
                    full_sql=cmd.raw_line,
                    ackmode=cmd.args.get("ackmode", "ack_requeue_true"),
                )
                if get_result.error:
                    result.error = get_result.error
                    return result
                aggregated.extend(get_result.rows)
                if get_result.warning:
                    warning = get_result.warning

            if limit_num > 0:
                aggregated = aggregated[:limit_num]
            result.rows = aggregated
            result.affected_rows = len(aggregated)
            if warning and not aggregated:
                result.warning = warning
            elif not aggregated:
                result.warning = f"获取等待 {timeout_sec} 秒超时，未收到消息"
        except Exception as exc:
            logger.warning("RabbitMQ 查询执行失败: %s", exc)
            result.error = str(exc)
        return result

    def execute_check(self, db_name=None, sql=""):
        """审核 RabbitMQ 上线写命令。"""
        check_result = ReviewSet(full_sql=sql)
        statements = split_mq_lines(sql)

        for line, statement in enumerate(statements, start=1):
            try:
                cmd = parse_rabbitmq_line(statement)
                if cmd.action in {"get", "help"}:
                    errlevel = 2
                    status = "Audit failed"
                    message = "禁止使用查询命令！"
                else:
                    self._validate_write_command(cmd)
                    errlevel = 0
                    status = "Audit completed"
                    message = "暂不支持显示影响行数"
            except ValueError:
                errlevel = 2
                status = "Audit failed"
                message = "禁止执行该命令！"

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
            if errlevel == 2:
                # The submit page gates its warning confirmation on
                # error_count; without this, invalid MQ workflows report zero
                # errors and skip the confirmation (Codex #10).
                check_result.error_count += 1
        return check_result

    @staticmethod
    def _execute_write_command(channel, cmd):
        action = cmd.action
        args = cmd.args
        if action == "publish":
            channel.confirm_delivery()
            try:
                channel.basic_publish(
                    exchange=args.get("exchange", ""),
                    routing_key=args["routing_key"],
                    body=args["payload"],
                    mandatory=True,
                )
            except Exception as exc:
                if type(exc).__name__ in {"UnroutableError", "NackError"}:
                    raise ValueError("消息不可路由或未被确认") from exc
                raise
        elif action == "declare":
            target = args.get("target")
            if target == "queue":
                kwargs = {"queue": args["name"]}
                if "durable" in args:
                    kwargs["durable"] = args["durable"]
                if "auto_delete" in args:
                    kwargs["auto_delete"] = args["auto_delete"]
                channel.queue_declare(**kwargs)
            elif target == "exchange":
                kwargs = {
                    "exchange": args["name"],
                    "exchange_type": args["type"],
                }
                if "durable" in args:
                    kwargs["durable"] = args["durable"]
                if "auto_delete" in args:
                    kwargs["auto_delete"] = args["auto_delete"]
                channel.exchange_declare(**kwargs)
            elif target == "binding":
                channel.queue_bind(
                    queue=args["destination"],
                    exchange=args["source"],
                    routing_key=args.get("routing_key", ""),
                )
            else:
                raise ValueError("禁止执行该命令！")
        elif action == "purge":
            channel.queue_purge(queue=args["name"])
        elif action == "delete":
            target = args.get("target")
            if target == "queue":
                channel.queue_delete(queue=args["name"])
            elif target == "exchange":
                channel.exchange_delete(exchange=args["name"])
            elif target == "binding":
                channel.queue_unbind(
                    queue=args["destination"],
                    exchange=args["source"],
                    routing_key=args.get("properties_key", ""),
                )
            else:
                raise ValueError("禁止执行该命令！")
        else:
            raise ValueError("禁止执行该命令！")

    def execute_workflow(self, workflow):
        """执行 RabbitMQ 上线工单。"""
        sql = workflow.sqlworkflowcontent.sql_content
        statements = split_mq_lines(sql)
        execute_result = ReviewSet(full_sql=sql)
        conn = None
        line = 1
        # Initialize to the first command so a connection failure (raised
        # before the loop assigns `statement`) still records it instead of
        # sql=None and dropping it from the pending rows (Codex #13).
        statement = statements[0] if statements else None
        try:
            conn = self.get_connection(db_name=workflow.db_name)
            channel = conn.channel()
            for statement in statements:
                cmd = parse_rabbitmq_line(statement)
                self._validate_write_command(cmd)
                with FuncTimer() as timer:
                    self._execute_write_command(channel, cmd)
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
