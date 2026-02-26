from pytest_mock import MockFixture
from unittest.mock import Mock

from sql.engines.doris import DorisEngine
from sql.engines.models import ResultSet


def test_doris_server_info(db_instance, mocker: MockFixture):
    mock_query = mocker.patch.object(DorisEngine, "query")

    # Mock realistic "show frontends" output with 19 columns
    # Include column_list to enable column name lookup
    column_names = [
        "Name",
        "IP",
        "EditLogPort",
        "HttpPort",
        "QueryPort",
        "RpcPort",
        "ArrowFlightSqlPort",
        "Role",
        "IsMaster",
        "ClusterId",
        "Join",
        "Alive",
        "ReplayedJournalId",
        "LastStartTime",
        "LastHeartbeat",
        "IsHelper",
        "ErrMsg",
        "Version",
        "Status",
    ]

    mock_row = [
        "fe_id",  # 0: Name
        "192.168.1.100",  # 1: IP
        "9010",  # 2: EditLogPort
        "8030",  # 3: HttpPort
        "9030",  # 4: QueryPort
        "9020",  # 5: RpcPort
        "-1",  # 6: ArrowFlightSqlPort
        "FOLLOWER",  # 7: Role
        "true",  # 8: IsMaster
        "1234567890",  # 9: ClusterId
        "true",  # 10: Join
        "true",  # 11: Alive
        "8210343",  # 12: ReplayedJournalId
        "2026-01-15 03:20:09",  # 13: LastStartTime
        "2026-02-24 07:13:44",  # 14: LastHeartbeat
        "true",  # 15: IsHelper
        "",  # 16: ErrMsg
        "doris-2.1.0-rc01-97b77e6cda",  # 17: Version (column name: "Version")
        "Yes",  # 18: Status
    ]

    mock_query.return_value = ResultSet(
        full_sql="show frontends",
        rows=[mock_row],
        column_list=column_names,  # Add column names for robust lookup
    )
    db_instance.db_type = "doris"
    engine = DorisEngine(instance=db_instance)
    version = engine.server_version
    assert version == (2, 1, 0)


def test_forbidden_db(db_instance, mocker: MockFixture):
    db_instance.db_type = "doris"
    mock_query = mocker.patch.object(DorisEngine, "query")
    mock_query.return_value = ResultSet(
        full_sql="show databases", rows=[["__internal_schema"]]
    )

    engine = DorisEngine(instance=db_instance)
    all_db = engine.get_all_databases()
    assert all_db.rows == []


# Tests without database dependency (using Mock directly)


def test_doris_version_parsing_no_db(mocker: MockFixture):
    """Test version parsing without database dependency"""
    # Create mock instance without database
    mock_instance = Mock()
    mock_instance.instance_name = "test_instance"
    mock_instance.host = "localhost"
    mock_instance.port = 9030
    mock_instance.db_name = "test"
    mock_instance.db_type = "doris"
    mock_instance.mode = ""
    mock_instance.tunnel = None
    # Mock get_username_password to return tuple
    mock_instance.get_username_password.return_value = ("root", "password")

    # Create engine
    engine = DorisEngine(instance=mock_instance)

    # Mock the query method
    column_names = [
        "Name",
        "IP",
        "EditLogPort",
        "HttpPort",
        "QueryPort",
        "RpcPort",
        "ArrowFlightSqlPort",
        "Role",
        "IsMaster",
        "ClusterId",
        "Join",
        "Alive",
        "ReplayedJournalId",
        "LastStartTime",
        "LastHeartbeat",
        "IsHelper",
        "ErrMsg",
        "Version",
        "Status",
    ]

    mock_row = [
        "fe_id",
        "192.168.1.100",
        "9010",
        "8030",
        "9030",
        "9020",
        "-1",
        "FOLLOWER",
        "true",
        "1234567890",
        "true",
        "true",
        "8210343",
        "2026-01-15 03:20:09",
        "2026-02-24 07:13:44",
        "true",
        "",
        "doris-2.1.11-rc01-97b77e6cda",
        "Yes",
    ]

    mock_query = mocker.patch.object(engine, "query")
    mock_query.return_value = ResultSet(
        full_sql="show frontends", rows=[mock_row], column_list=column_names
    )

    version = engine.server_version
    assert version == (2, 1, 11)


def test_doris_version_fallback_no_db(mocker: MockFixture):
    """Test fallback to index -2 without database dependency"""
    mock_instance = Mock()
    mock_instance.instance_name = "test_instance"
    mock_instance.host = "localhost"
    mock_instance.port = 9030
    mock_instance.db_name = "test"
    mock_instance.db_type = "doris"
    mock_instance.mode = ""
    mock_instance.tunnel = None
    mock_instance.get_username_password.return_value = ("root", "password")

    engine = DorisEngine(instance=mock_instance)

    # Test without column_list
    mock_row = [""] * 17 + ["doris-3.0.1-stable", "Yes"]

    mock_query = mocker.patch.object(engine, "query")
    mock_query.return_value = ResultSet(
        full_sql="show frontends", rows=[mock_row], column_list=None
    )

    version = engine.server_version
    assert version == (3, 0, 1)


def test_doris_version_formats_no_db(mocker: MockFixture):
    """Test different version formats without database dependency"""
    test_cases = [
        ("doris-2.1.11-rc01-97b77e6cda", (2, 1, 11)),
        ("doris-1.2.3", (1, 2, 3)),
        ("doris-10.20.30-beta", (10, 20, 30)),
    ]

    for version_string, expected in test_cases:
        mock_instance = Mock()
        mock_instance.instance_name = "test_instance"
        mock_instance.host = "localhost"
        mock_instance.port = 9030
        mock_instance.db_name = "test"
        mock_instance.db_type = "doris"
        mock_instance.mode = ""
        mock_instance.tunnel = None
        mock_instance.get_username_password.return_value = ("root", "password")

        engine = DorisEngine(instance=mock_instance)

        column_names = [""] * 17 + ["Version", "Status"]
        mock_row = [""] * 17 + [version_string, "Yes"]

        mock_query = mocker.patch.object(engine, "query")
        mock_query.return_value = ResultSet(
            full_sql="show frontends", rows=[mock_row], column_list=column_names
        )

        version = engine.server_version
        assert (
            version == expected
        ), f"Expected {expected}, got {version} for '{version_string}'"


def test_doris_original_bug_fixed_no_db(mocker: MockFixture):
    """Verify the original bug is fixed (accessing column -1 with 'Yes' value)"""
    mock_instance = Mock()
    mock_instance.instance_name = "test_instance"
    mock_instance.host = "localhost"
    mock_instance.port = 9030
    mock_instance.db_name = "test"
    mock_instance.db_type = "doris"
    mock_instance.mode = ""
    mock_instance.tunnel = None
    mock_instance.get_username_password.return_value = ("root", "password")

    engine = DorisEngine(instance=mock_instance)

    # Simulate production scenario with 19 columns
    # Column -1 is "Yes" (Status), Column -2 is version string
    column_names = [
        "Name",
        "IP",
        "EditLogPort",
        "HttpPort",
        "QueryPort",
        "RpcPort",
        "ArrowFlightSqlPort",
        "Role",
        "IsMaster",
        "ClusterId",
        "Join",
        "Alive",
        "ReplayedJournalId",
        "LastStartTime",
        "LastHeartbeat",
        "IsHelper",
        "ErrMsg",
        "Version",
        "Status",
    ]

    mock_row = [
        "fe_id",
        "192.168.1.100",
        "9010",
        "8030",
        "9030",
        "9020",
        "-1",
        "FOLLOWER",
        "true",
        "1234567890",
        "true",
        "true",
        "8210343",
        "2026-01-15 03:20:09",
        "2026-02-24 07:13:44",
        "true",
        "",
        "doris-2.1.11-rc01-97b77e6cda",
        "Yes",
    ]

    # Verify the bug would have occurred with old code
    assert mock_row[-1] == "Yes", "Last column should be 'Yes'"
    assert "doris-" in mock_row[-2], "Second-to-last column should be version"

    mock_query = mocker.patch.object(engine, "query")
    mock_query.return_value = ResultSet(
        full_sql="show frontends", rows=[mock_row], column_list=column_names
    )

    # Should not raise ValueError anymore
    version = engine.server_version
    assert version == (2, 1, 11)


def test_doris_version_column_reordering_no_db(mocker: MockFixture):
    """Test robustness when columns are reordered"""
    mock_instance = Mock()
    mock_instance.instance_name = "test_instance"
    mock_instance.host = "localhost"
    mock_instance.port = 9030
    mock_instance.db_name = "test"
    mock_instance.db_type = "doris"
    mock_instance.mode = ""
    mock_instance.tunnel = None
    mock_instance.get_username_password.return_value = ("root", "password")

    engine = DorisEngine(instance=mock_instance)

    # Simulate column reordering: Version moved to different position
    column_names = ["Name", "IP", "Version", "Status", "Other1", "Other2"]
    mock_row = ["fe_id", "192.168.1.100", "doris-2.5.0", "Yes", "foo", "bar"]

    mock_query = mocker.patch.object(engine, "query")
    mock_query.return_value = ResultSet(
        full_sql="show frontends", rows=[mock_row], column_list=column_names
    )

    # Should still work because we search by column name, not position
    version = engine.server_version
    assert version == (2, 5, 0)
