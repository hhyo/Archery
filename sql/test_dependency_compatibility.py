"""Exercise dependency APIs without engine connections or task execution."""

import pytest
import paramiko
from sshtunnel import SSHTunnelForwarder

from sql.engines.goinception import GoInceptionEngine
from sql.engines.mysql import MysqlEngine
from sql.engines.tdengine import TDengineEngine


@pytest.mark.parametrize(
    "engine_type", [MysqlEngine, GoInceptionEngine, TDengineEngine]
)
@pytest.mark.parametrize(
    "value, expected",
    [
        ("O'Reilly", "O\\'Reilly"),
        ("a\\b", "a\\\\b"),
        ('a"b', 'a\\"b'),
        ("a\n\r\x00\x1ab", "a\\n\\r\\0\\Zb"),
        ("中文", "中文"),
    ],
)
def test_engine_string_escaping_with_current_pymysql(engine_type, value, expected):
    engine = object.__new__(engine_type)
    assert engine.escape_string(value) == expected


def test_mysql_literal_quotes_the_escaped_value():
    assert MysqlEngine._quote_literal("a'b\\c") == "'a\\'b\\\\c'"


def test_ssh_key_discovery_without_removed_dss_api():
    # Real dependency path: sshtunnel 0.1.5 raises on Paramiko without DSSKey.
    assert (
        SSHTunnelForwarder.get_keys(host_pkey_directories=[], allow_agent=False) == []
    )


def test_ssh_password_forwarder_initializes_without_connecting(mocker):
    connect = mocker.patch("socket.create_connection", side_effect=AssertionError)
    forwarder = SSHTunnelForwarder(
        ("127.0.0.1", 1),
        ssh_username="isolated-test",
        ssh_password="test-only-password",
        ssh_config_file=None,
        host_pkey_directories=[],
        allow_agent=False,
        remote_bind_address=("127.0.0.1", 3306),
    )
    assert not forwarder.is_active
    connect.assert_not_called()


def test_ssh_rsa_forwarder_initializes_without_connecting(mocker):
    connect = mocker.patch("socket.create_connection", side_effect=AssertionError)
    forwarder = SSHTunnelForwarder(
        ("127.0.0.1", 1),
        ssh_username="isolated-test",
        ssh_pkey=paramiko.RSAKey.generate(2048),
        ssh_config_file=None,
        host_pkey_directories=[],
        allow_agent=False,
        remote_bind_address=("127.0.0.1", 3306),
    )
    assert not forwarder.is_active
    connect.assert_not_called()


def test_binlog_reader_imports_with_current_pymysql():
    # Legacy mysql-replication imported the removed pymysql.util module.
    from pymysqlreplication import BinLogStreamReader

    assert callable(BinLogStreamReader)
