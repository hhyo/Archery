import simplejson as json
import sys
import types
from unittest.mock import Mock

aliyun_sdk = types.ModuleType("common.utils.aliyun_sdk")
aliyun_sdk.Aliyun = Mock(name="Aliyun")
sys.modules["common.utils.aliyun_sdk"] = aliyun_sdk

from sql.engines.cloud import aliyun_rds
from sql.engines.cloud.aliyun_rds import AliyunRDS
from sql.engines.models import ResultSet


def _engine():
    engine = AliyunRDS.__new__(AliyunRDS)
    engine.instance_name = "rds_instance"
    return engine


def _mock_rds_config(mocker):
    instance_info = Mock(name="instance_info")
    objects = mocker.patch.object(aliyun_rds.AliyunRdsConfig, "objects")
    objects.get.return_value = instance_info
    return instance_info, objects


def test_processlist_uses_default_query_command(mocker):
    instance_info, objects = _mock_rds_config(mocker)
    aliyun = mocker.patch.object(aliyun_rds, "Aliyun")
    process_rows = [{"Id": 1, "User": "root", "Command": "Query"}]
    aliyun.return_value.RequestServiceOfCloudDBA.return_value = json.dumps(
        {"AttrData": json.dumps({"ProcessList": process_rows})}
    )

    result = _engine().processlist("")

    objects.get.assert_called_once_with(instance__instance_name="rds_instance")
    aliyun.assert_called_once_with(rds=instance_info)
    aliyun.return_value.RequestServiceOfCloudDBA.assert_called_once_with(
        "ShowProcessList", {"Language": "zh", "Command": "Query"}
    )
    assert isinstance(result, ResultSet)
    assert result.full_sql == "show processlist"
    assert result.rows == process_rows


def test_processlist_uses_requested_command(mocker):
    _mock_rds_config(mocker)
    aliyun = mocker.patch.object(aliyun_rds, "Aliyun")
    aliyun.return_value.RequestServiceOfCloudDBA.return_value = json.dumps(
        {"AttrData": json.dumps({"ProcessList": []})}
    )

    _engine().processlist("Sleep")

    aliyun.return_value.RequestServiceOfCloudDBA.assert_called_once_with(
        "ShowProcessList", {"Language": "zh", "Command": "Sleep"}
    )


def test_get_kill_command_returns_request_attr_data(mocker):
    _mock_rds_config(mocker)
    aliyun = mocker.patch.object(aliyun_rds, "Aliyun")
    aliyun.return_value.RequestServiceOfCloudDBA.return_value = json.dumps(
        {"AttrData": "kill-request-id"}
    )

    result = _engine().get_kill_command([1, 2])

    aliyun.return_value.RequestServiceOfCloudDBA.assert_called_once_with(
        "CreateKillSessionRequest", {"Language": "zh", "ThreadIDs": [1, 2]}
    )
    assert result == "kill-request-id"


def test_kill_confirms_kill_session_request(mocker):
    _mock_rds_config(mocker)
    aliyun = mocker.patch.object(aliyun_rds, "Aliyun")
    aliyun.return_value.RequestServiceOfCloudDBA.return_value = json.dumps(
        {"AttrData": {"Success": True}}
    )

    result = _engine().kill([1, 2])

    aliyun.return_value.RequestServiceOfCloudDBA.assert_called_once_with(
        "ConfirmKillSessionRequest", {"Language": "zh"}
    )
    assert isinstance(result, ResultSet)
    assert result.full_sql == "kill 1;kill 2;"
    assert result.rows == {"Success": True}
    assert result.error is None


def test_tablespace_returns_empty_list_when_sdk_list_data_empty(mocker):
    _mock_rds_config(mocker)
    aliyun = mocker.patch.object(aliyun_rds, "Aliyun")
    aliyun.return_value.RequestServiceOfCloudDBA.return_value = json.dumps(
        {"ListData": ""}
    )

    result = _engine().tablespace(offset=0, limit=10)

    aliyun.return_value.RequestServiceOfCloudDBA.assert_called_once_with(
        "GetSpaceStatForTables", {"Language": "zh", "OrderType": "Data"}
    )
    assert result.full_sql == "select * FROM information_schema.tables"
    assert result.rows == []


def test_tablespace_filters_rows_by_schema_search(mocker):
    _mock_rds_config(mocker)
    aliyun = mocker.patch.object(aliyun_rds, "Aliyun")
    space_rows = [
        {"DBName": "app", "TableName": "orders", "DataSize": 10},
        {"DBName": "log", "TableName": "events", "DataSize": 20},
    ]
    aliyun.return_value.RequestServiceOfCloudDBA.return_value = json.dumps(
        {"ListData": json.dumps(space_rows)}
    )

    result = _engine().tablespace(offset=0, limit=10, schema_search="ORDER")

    assert result.rows == [space_rows[0]]


def test_slowquery_review_formats_rows_and_request_params(mocker):
    _mock_rds_config(mocker)
    aliyun = mocker.patch.object(aliyun_rds, "Aliyun")
    aliyun.utc2local.return_value = "2026-06-01 00:00:00"
    slow_log = {
        "TotalRecordCount": 1,
        "PageRecordCount": 10,
        "PageNumber": 2,
        "Items": {
            "SQLSlowLog": [
                {
                    "SQLHASH": 12345678901234567890,
                    "CreateTime": "2026-06-01Z",
                    "SQLText": "select 1",
                }
            ]
        },
    }
    aliyun.return_value.DescribeSlowLogs.return_value = json.dumps(slow_log)

    result = _engine().slowquery_review(
        "2026-06-01", "2026-06-02", "app_db", limit=10, offset=10
    )

    aliyun.return_value.DescribeSlowLogs.assert_called_once_with(
        "2026-06-01Z",
        "2026-06-02Z",
        PageSize=10,
        PageNumber=2.0,
        DBName="app_db",
    )
    aliyun.utc2local.assert_called_once_with("2026-06-01Z", utc_format="%Y-%m-%dZ")
    assert result["total"] == 1
    assert result["PageSize"] == 10
    assert result["PageNumber"] == 2
    assert result["rows"][0]["SQLId"] == "12345678901234567890"
    assert result["rows"][0]["CreateTime"] == "2026-06-01 00:00:00"


def test_slowquery_review_omits_empty_db_name(mocker):
    _mock_rds_config(mocker)
    aliyun = mocker.patch.object(aliyun_rds, "Aliyun")
    aliyun.return_value.DescribeSlowLogs.return_value = json.dumps(
        {
            "TotalRecordCount": 0,
            "PageRecordCount": 10,
            "PageNumber": 1,
            "Items": {"SQLSlowLog": []},
        }
    )

    _engine().slowquery_review("2026-06-01", "2026-06-02", "", limit=10, offset=0)

    assert "DBName" not in aliyun.return_value.DescribeSlowLogs.call_args.kwargs


def test_slowquery_review_history_formats_time_and_host(mocker):
    _mock_rds_config(mocker)
    aliyun = mocker.patch.object(aliyun_rds, "Aliyun")
    aliyun.utc2local.return_value = "2026-06-01 08:00:00"
    slow_record = {
        "TotalRecordCount": 1,
        "PageRecordCount": 20,
        "PageNumber": 2,
        "Items": {
            "SQLSlowRecord": [
                {
                    "ExecutionStartTime": "2026-06-01T00:00:00Z",
                    "HostAddress": "10.0.0.1[10.0.0.1:3306]",
                    "SQLText": "select 1",
                }
            ]
        },
    }
    aliyun.return_value.DescribeSlowLogRecords.return_value = json.dumps(slow_record)

    result = _engine().slowquery_review_history(
        "2026-06-01",
        "2026-06-02",
        db_name="app_db",
        sql_id="987",
        limit=20,
        offset=20,
    )

    aliyun.return_value.DescribeSlowLogRecords.assert_called_once_with(
        "2026-05-31T16:00Z",
        "2026-06-02T15:59Z",
        PageSize=20,
        PageNumber=2.0,
        SQLHASH="987",
        DBName="app_db",
    )
    aliyun.utc2local.assert_called_once_with(
        "2026-06-01T00:00:00Z", utc_format="%Y-%m-%dT%H:%M:%SZ"
    )
    assert result["total"] == 1
    assert result["PageSize"] == 20
    assert result["PageNumber"] == 2
    assert result["rows"][0]["ExecutionStartTime"] == "2026-06-01 08:00:00"
    assert result["rows"][0]["HostAddress"] == "10.0.0.1"


def test_slowquery_review_history_omits_optional_filters(mocker):
    _mock_rds_config(mocker)
    aliyun = mocker.patch.object(aliyun_rds, "Aliyun")
    aliyun.return_value.DescribeSlowLogRecords.return_value = json.dumps(
        {
            "TotalRecordCount": 0,
            "PageRecordCount": 10,
            "PageNumber": 1,
            "Items": {"SQLSlowRecord": []},
        }
    )

    _engine().slowquery_review_history(
        "2026-06-01", "2026-06-02", db_name="", sql_id="", limit=10, offset=0
    )

    kwargs = aliyun.return_value.DescribeSlowLogRecords.call_args.kwargs
    assert "DBName" not in kwargs
    assert "SQLHASH" not in kwargs
