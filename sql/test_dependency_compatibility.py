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


def test_failed_ssh_start_does_not_hang_during_finalization():
    import subprocess
    import sys
    import textwrap

    # Set up a real local forwarder, but never connect to a gateway.
    # A subprocess timeout catches socketserver.shutdown() deadlocks.
    code = textwrap.dedent("""
        import gc
        import sshtunnel
        from types import SimpleNamespace
        from sql.utils import ssh_tunnel
        original = sshtunnel.SSHTunnelForwarder
        original._connect_to_gateway = lambda self: setattr(
            self, "_transport", SimpleNamespace(is_active=lambda: False)
        )

        def local_forwarder(**kwargs):
            kwargs.update(
                allow_agent=False, host_pkey_directories=[],
                ssh_config_file=None, local_bind_address=('127.0.0.1', 0),
            )
            return original(**kwargs)

        ssh_tunnel.SSHTunnelForwarder = local_forwarder
        try:
            ssh_tunnel.SSHConnection(
                '127.0.0.1', 3306, '127.0.0.1', 1,
                'test-only', 'test-only', '', '',
            )
        except sshtunnel.BaseSSHTunnelForwarderError:
            pass
        else:
            raise AssertionError('Expected gateway failure')
        gc.collect()
        print('finalization completed')
        """)
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, result.stderr
    assert "finalization completed" in result.stdout


def test_invalid_ssh_key_does_not_leave_an_uninitialized_server():
    from sql.utils.ssh_tunnel import SSHConnection

    connection = object.__new__(SSHConnection)
    with pytest.raises(paramiko.SSHException):
        connection.__init__(
            "127.0.0.1",
            3306,
            "127.0.0.1",
            1,
            "test-only",
            "",
            "invalid test key",
            "",
        )
    assert connection.server is None
    connection.__del__()


def test_started_ssh_forwarder_is_closed_once_on_finalization(mocker):
    from sql.utils.ssh_tunnel import SSHConnection

    forwarder = mocker.Mock(is_alive=False, local_bind_port=12345)
    forwarder.start.side_effect = lambda: setattr(forwarder, "is_alive", True)
    forwarder.close.side_effect = lambda: setattr(forwarder, "is_alive", False)
    mocker.patch("sql.utils.ssh_tunnel.SSHTunnelForwarder", return_value=forwarder)

    connection = SSHConnection(
        "127.0.0.1",
        3306,
        "127.0.0.1",
        22,
        "test-only",
        "test-only",
        "",
        "",
    )
    forwarder.start.assert_called_once_with()
    assert connection.get_ssh() == ("127.0.0.1", 12345)

    connection.__del__()
    forwarder.close.assert_called_once_with()
    assert not forwarder.is_alive

    # Repeated cleanup must not try to stop a server that is already stopped.
    connection.__del__()
    forwarder.close.assert_called_once_with()
