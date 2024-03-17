from pytest_mock import MockFixture

from sql.engines.doris import DorisEngine
from sql.engines.models import ResultSet


def test_doris_server_info(db_instance, mocker: MockFixture):
    mock_query = mocker.patch.object(DorisEngine, "query")
    mock_query.return_value = ResultSet(
        full_sql="show frontends", rows=[["foo", "bar", "2.1.0-doris"]]
    )
    db_instance.db_type = "doris"
    engine = DorisEngine(instance=db_instance)
    version = engine.server_version
    assert version == (2, 1, 0)


def test_doris_query(db_instance, mocker: MockFixture):
    mock_get_connection = mocker.patch.object(DorisEngine, "get_connection")

    class DummyCursor:
        def __init__(self):
            self.description = [("foo",), ("bar",)]
            self.fetchall = lambda: [("baz", "qux")]

        def execute(self, sql):
            pass

    mock_get_connection.return_value.cursor.return_value = DummyCursor()
    db_instance.db_type = "doris"
    engine = DorisEngine(instance=db_instance)
    result_set = engine.query(sql="select * from foo")
    assert result_set.column_list == ["foo", "bar"]
    assert result_set.rows == [("baz", "qux")]
    assert result_set.affected_rows == 1


def test_forbidden_db(db_instance, mocker: MockFixture):
    db_instance.db_type = "doris"
    mock_query = mocker.patch.object(DorisEngine, "query")
    mock_query.return_value = ResultSet(
        full_sql="show databases", rows=[["__internal_schema"]]
    )

    engine = DorisEngine(instance=db_instance)
    all_db = engine.get_all_databases()
    assert all_db.rows == []
