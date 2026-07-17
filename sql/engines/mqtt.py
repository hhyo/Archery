# -*- coding: UTF-8 -*-
import logging
import os
import shlex
import ssl
import tempfile
import threading
import time

import paho.mqtt.client as mqtt

from common.utils.timer import FuncTimer
from . import EngineBase
from .models import ResultSet, ReviewResult, ReviewSet

logger = logging.getLogger("default")


class MqttEngine(EngineBase):
    name = "MQTT"
    info = "MQTT engine"
    write_commands = {"publish"}
    connack_timeout = 10

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

    def _ssl_context(self):
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

            return context
        finally:
            for path in temp_paths:
                try:
                    os.unlink(path)
                except OSError:
                    logger.warning("清理 MQTT 临时证书文件失败: %s", path)

    def get_connection(self, db_name=None):
        context = self._ssl_context()
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if self.user:
            client.username_pw_set(self.user, self.password or "")
        if context is not None:
            client.tls_set_context(context)
        return client

    def _connect_and_wait(self, client):
        connected = threading.Event()
        connect_result = {}

        def on_connect(_client, _userdata, _flags, reason_code, _properties):
            connect_result["reason_code"] = reason_code
            connected.set()

        client.on_connect = on_connect
        loop_started = False
        try:
            connect_rc = client.connect(self.host, self.port, keepalive=30)
            if isinstance(connect_rc, int) and connect_rc != mqtt.MQTT_ERR_SUCCESS:
                raise ConnectionError(f"MQTT 连接启动失败，返回码：{connect_rc}")
            client.loop_start()
            loop_started = True
            if not connected.wait(self.connack_timeout):
                raise TimeoutError(
                    f"等待 MQTT CONNACK 超时（{self.connack_timeout} 秒）"
                )

            reason_code = connect_result["reason_code"]
            is_failure = getattr(reason_code, "is_failure", None)
            if is_failure is None:
                is_failure = reason_code != 0
            if is_failure:
                raise ConnectionError(f"MQTT 连接被拒绝：{reason_code}")
        except Exception:
            if loop_started:
                client.loop_stop()
            client.disconnect()
            raise

    def test_connection(self):
        result = ResultSet(full_sql="connection")
        client = None
        connected = False
        try:
            client = self.get_connection()
            self._connect_and_wait(client)
            connected = True
            result.column_list = ["状态"]
            result.rows = [["连接成功"]]
            result.affected_rows = 1
        except Exception as exc:
            result.error = str(exc)
        finally:
            if client is not None and connected:
                client.loop_stop()
                client.disconnect()
        return result

    def get_all_databases(self, **kwargs):
        db_name = self.db_name or "default"
        return ResultSet(rows=[{"value": db_name, "text": db_name}])

    def get_all_tables(self, db_name, **kwargs):
        return ResultSet(rows=[])

    @staticmethod
    def _parse_subscribe(sql):
        parts = shlex.split(sql)
        if not parts or parts[0].lower() != "subscribe":
            raise ValueError("禁止执行该命令！")
        if len(parts) < 2 or len(parts) > 4:
            raise ValueError(
                "subscribe 命令格式：subscribe <topic> [timeout_sec] [max_msgs]"
            )

        try:
            timeout_sec = int(parts[2]) if len(parts) >= 3 else 3
            max_msgs = int(parts[3]) if len(parts) == 4 else 10
        except ValueError as exc:
            raise ValueError("timeout_sec 和 max_msgs 必须为正整数") from exc
        if timeout_sec <= 0 or max_msgs <= 0:
            raise ValueError("timeout_sec 和 max_msgs 必须为正整数")
        return parts[1], min(timeout_sec, 30), min(max_msgs, 100)

    @classmethod
    def _parse_query(cls, sql):
        parts = shlex.split(sql)
        if parts and parts[0].lower() == "help":
            if len(parts) != 1:
                raise ValueError("help 命令不接受参数")
            return "help", None
        return "subscribe", cls._parse_subscribe(sql)

    def query_check(self, db_name=None, sql=""):
        filtered_sql = sql.strip()
        try:
            self._parse_query(filtered_sql)
        except ValueError as exc:
            return {
                "bad_query": True,
                "filtered_sql": filtered_sql,
                "msg": str(exc),
            }
        return {"bad_query": False, "filtered_sql": filtered_sql, "msg": ""}

    def query(
        self,
        db_name=None,
        sql="",
        limit_num=0,
        close_conn=True,
        parameters=None,
        **kwargs,
    ):
        result = ResultSet(
            full_sql=sql, column_list=["topic", "payload", "qos", "retain"]
        )
        client = None
        connected = False
        loop_started = False
        messages = []
        try:
            command, parsed = self._parse_query(sql)
            if command == "help":
                result.column_list = ["命令"]
                result.rows = [
                    ["subscribe <topic> [timeout_sec] [max_msgs]"],
                    ["help"],
                ]
                result.affected_rows = len(result.rows)
                return result

            topic, timeout_sec, max_msgs = parsed

            def on_message(_client, _userdata, message):
                if len(messages) >= max_msgs:
                    return
                payload = message.payload
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8", errors="replace")
                messages.append(
                    [message.topic, payload, message.qos, message.retain]
                )

            client = self.get_connection(db_name)
            client.on_message = on_message
            self._connect_and_wait(client)
            connected = True
            loop_started = True
            client.subscribe(topic, qos=0)

            started_at = time.monotonic()
            while (
                len(messages) < max_msgs
                and time.monotonic() - started_at < timeout_sec
            ):
                time.sleep(0.05)

            if limit_num > 0:
                messages = messages[:limit_num]
            result.rows = messages
            result.affected_rows = len(messages)
            if not messages:
                result.warning = f"订阅等待 {timeout_sec} 秒超时，未收到消息"
        except Exception as exc:
            logger.warning("MQTT 查询执行失败: %s", exc)
            result.error = str(exc)
        finally:
            if client is not None and loop_started:
                client.loop_stop()
            if client is not None and connected and close_conn:
                client.disconnect()
        return result

    def execute_check(self, db_name=None, sql=""):
        """审核 MQTT 上线写命令。"""
        check_result = ReviewSet(full_sql=sql)
        statements = [
            command.strip() for command in sql.splitlines() if command.strip()
        ]

        for line, statement in enumerate(statements, start=1):
            query_result = self.query_check(db_name=db_name, sql=statement)
            if not query_result["bad_query"]:
                errlevel = 2
                status = "Audit failed"
                message = "禁止使用查询命令！"
            else:
                try:
                    self._parse_publish(statement)
                    is_allowed = True
                except ValueError:
                    is_allowed = False
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
    def _parse_publish(statement):
        parts = shlex.split(statement)
        if len(parts) not in {3, 4} or parts[0].lower() != "publish":
            raise ValueError("publish 命令格式：publish <topic> <payload> [qos]")
        try:
            qos = int(parts[3]) if len(parts) == 4 else 0
        except ValueError as exc:
            raise ValueError("qos 必须为 0、1 或 2") from exc
        if qos not in {0, 1, 2}:
            raise ValueError("qos 必须为 0、1 或 2")
        return parts[1], parts[2], qos

    @classmethod
    def _execute_publish(cls, client, statement):
        topic, payload, qos = cls._parse_publish(statement)
        publish_info = client.publish(topic, payload=payload, qos=qos, retain=False)
        publish_info.wait_for_publish()

    def execute_workflow(self, workflow):
        """执行 MQTT 上线工单。"""
        sql = workflow.sqlworkflowcontent.sql_content
        statements = [
            command.strip() for command in sql.splitlines() if command.strip()
        ]
        execute_result = ReviewSet(full_sql=sql)
        client = None
        connected = False
        loop_started = False
        line = 1
        statement = None
        try:
            client = self.get_connection(workflow.db_name)
            self._connect_and_wait(client)
            connected = True
            loop_started = True
            for statement in statements:
                with FuncTimer() as timer:
                    self._execute_publish(client, statement)
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
                "MQTT 命令执行失败，语句：%s，错误信息：%s",
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
            if client is not None and loop_started:
                client.loop_stop()
            if client is not None and connected:
                client.disconnect()
        return execute_result
