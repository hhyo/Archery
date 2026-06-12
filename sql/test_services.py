from types import SimpleNamespace

import pytest

from sql.services import resource_service
from sql.services import sqlquery_service


class _FakeQuerySet:
    def __init__(self, rows):
        self._rows = rows

    def order_by(self, *args, **kwargs):
        return self

    def values(self, *args, **kwargs):
        return self._rows


class _FakeConfig:
    def __init__(self, mapping=None):
        self.mapping = mapping or {}

    def get(self, key, default=None):
        return self.mapping.get(key, default)


def _fake_query_result(error=None, affected_rows=3):
    return SimpleNamespace(
        error=error,
        affected_rows=affected_rows,
        rows=[[1]],
        column_list=["col"],
        full_sql="select 1",
        mask_rule_hit=False,
        is_masked=False,
        query_time=0,
    )


@pytest.mark.django_db
def test_list_user_accessible_instances_returns_compat_shape(monkeypatch):
    fake_rows = [
        {"id": 1, "instance_name": "ins1", "type": "slave", "db_type": "mysql"}
    ]
    monkeypatch.setattr(
        resource_service,
        "user_instances",
        lambda user, *args, **kwargs: _FakeQuerySet(fake_rows),
    )

    result = resource_service.list_user_accessible_instances(user=SimpleNamespace())

    assert result["status"] == 0
    assert result["msg"] == "ok"
    assert result["data"] == fake_rows


@pytest.mark.django_db
def test_list_instance_resources_returns_not_found_when_no_permission(monkeypatch):
    monkeypatch.setattr(
        resource_service,
        "_resolve_instance_for_user",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            resource_service.Instance.DoesNotExist
        ),
    )

    result = resource_service.list_instance_resources(
        user=SimpleNamespace(),
        resource_type="database",
        instance_name="ins",
    )

    assert result["status"] == 1
    assert "实例不存在或无权限" in result["msg"]


@pytest.mark.django_db
def test_list_instance_resources_database_success(monkeypatch):
    fake_engine = SimpleNamespace(
        escape_string=lambda s: s,
        get_all_databases=lambda: SimpleNamespace(rows=["db1", "db2"], error=None),
        instance=SimpleNamespace(show_db_name_regex=".*", denied_db_name_regex=""),
    )
    monkeypatch.setattr(
        resource_service,
        "_resolve_instance_for_user",
        lambda *args, **kwargs: SimpleNamespace(id=1),
    )
    monkeypatch.setattr(resource_service, "get_engine", lambda instance: fake_engine)
    monkeypatch.setattr(
        resource_service, "filter_db_list", lambda db_list, **kwargs: db_list
    )

    result = resource_service.list_instance_resources(
        user=SimpleNamespace(),
        resource_type="database",
        instance_name="ins",
    )

    assert result["status"] == 0
    assert result["data"] == ["db1", "db2"]


@pytest.mark.django_db
def test_list_instance_resources_invalid_resource_type(monkeypatch):
    fake_engine = SimpleNamespace(
        escape_string=lambda s: s,
    )
    monkeypatch.setattr(
        resource_service,
        "_resolve_instance_for_user",
        lambda *args, **kwargs: SimpleNamespace(id=1),
    )
    monkeypatch.setattr(resource_service, "get_engine", lambda instance: fake_engine)

    result = resource_service.list_instance_resources(
        user=SimpleNamespace(),
        resource_type="schema",
        instance_name="ins",
        db_name="",
    )

    assert result["status"] == 1
    assert "不支持的资源类型或者参数不完整" in result["msg"]


@pytest.mark.django_db
def test_describe_table_structure_returns_not_found_when_no_permission(monkeypatch):
    monkeypatch.setattr(
        resource_service,
        "_resolve_instance_for_user",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            resource_service.Instance.DoesNotExist
        ),
    )

    result = resource_service.describe_table_structure(
        user=SimpleNamespace(),
        instance_name="ins",
        db_name="archery",
        tb_name="users",
    )

    assert result["status"] == 1
    assert "实例不存在或无权限" in result["msg"]


@pytest.mark.django_db
def test_describe_table_structure_success(monkeypatch):
    query_result = SimpleNamespace(
        error=None,
        column_list=["Field", "Type"],
        rows=[["id", "int"], ["name", "varchar(255)"]],
    )
    fake_engine = SimpleNamespace(
        escape_string=lambda s: s,
        describe_table=lambda db_name, tb_name, schema_name="": query_result,
    )
    monkeypatch.setattr(
        resource_service,
        "_resolve_instance_for_user",
        lambda *args, **kwargs: SimpleNamespace(id=1),
    )
    monkeypatch.setattr(resource_service, "get_engine", lambda instance: fake_engine)

    result = resource_service.describe_table_structure(
        user=SimpleNamespace(),
        instance_name="ins",
        db_name="archery",
        tb_name="users",
        schema_name="",
    )

    assert result["status"] == 0
    assert result["msg"] == "ok"
    assert result["data"] == query_result.__dict__


@pytest.mark.django_db
def test_describe_table_structure_engine_error_field(monkeypatch):
    query_result = SimpleNamespace(error="bad table", column_list=[], rows=[])
    fake_engine = SimpleNamespace(
        escape_string=lambda s: s,
        describe_table=lambda db_name, tb_name, schema_name="": query_result,
    )
    monkeypatch.setattr(
        resource_service,
        "_resolve_instance_for_user",
        lambda *args, **kwargs: SimpleNamespace(id=1),
    )
    monkeypatch.setattr(resource_service, "get_engine", lambda instance: fake_engine)

    result = resource_service.describe_table_structure(
        user=SimpleNamespace(),
        instance_name="ins",
        db_name="archery",
        tb_name="users",
    )

    assert result["status"] == 1
    assert result["msg"] == "bad table"


@pytest.mark.django_db
def test_describe_table_structure_exception(monkeypatch):
    fake_engine = SimpleNamespace(
        escape_string=lambda s: s,
        describe_table=lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("boom")
        ),
    )
    monkeypatch.setattr(
        resource_service,
        "_resolve_instance_for_user",
        lambda *args, **kwargs: SimpleNamespace(id=1),
    )
    monkeypatch.setattr(resource_service, "get_engine", lambda instance: fake_engine)

    result = resource_service.describe_table_structure(
        user=SimpleNamespace(),
        instance_name="ins",
        db_name="archery",
        tb_name="users",
    )

    assert result["status"] == 1
    assert "boom" in result["msg"]


@pytest.mark.django_db
def test_execute_sql_query_invalid_limit_returns_error():
    result = sqlquery_service.execute_sql_query(
        user=SimpleNamespace(username="u", display="U"),
        instance_name="ins",
        db_name="db",
        sql_content="select 1",
        limit_num="bad",
    )

    assert result["status"] == 1
    assert "limit_num 非法" in result["msg"]


@pytest.mark.django_db
def test_execute_sql_query_instance_not_found(monkeypatch):
    monkeypatch.setattr(
        sqlquery_service,
        "user_instances",
        lambda user: SimpleNamespace(
            get=lambda **kwargs: (_ for _ in ()).throw(
                sqlquery_service.Instance.DoesNotExist
            )
        ),
    )

    result = sqlquery_service.execute_sql_query(
        user=SimpleNamespace(username="u", display="U"),
        instance_name="ins",
        db_name="db",
        sql_content="select 1",
        limit_num=10,
    )

    assert result["status"] == 1
    assert "你所在组未关联该实例" in result["msg"]


@pytest.mark.django_db
def test_execute_sql_query_bad_query_rejected(monkeypatch):
    fake_engine = SimpleNamespace(
        query_check=lambda **kwargs: {
            "bad_query": True,
            "msg": "bad",
            "filtered_sql": "select 1",
            "has_star": False,
        }
    )
    monkeypatch.setattr(
        sqlquery_service,
        "user_instances",
        lambda user: SimpleNamespace(
            get=lambda **kwargs: SimpleNamespace(id=1, instance_name="ins")
        ),
    )
    monkeypatch.setattr(sqlquery_service, "SysConfig", lambda: _FakeConfig())
    monkeypatch.setattr(sqlquery_service, "get_engine", lambda instance: fake_engine)

    result = sqlquery_service.execute_sql_query(
        user=SimpleNamespace(username="u", display="U"),
        instance_name="ins",
        db_name="db",
        sql_content="select 1",
        limit_num=10,
    )

    assert result["status"] == 1
    assert result["msg"] == "bad"


@pytest.mark.django_db
def test_execute_sql_query_priv_check_failed(monkeypatch):
    fake_engine = SimpleNamespace(
        query_check=lambda **kwargs: {
            "bad_query": False,
            "msg": "",
            "filtered_sql": "select 1",
            "has_star": False,
        }
    )
    monkeypatch.setattr(
        sqlquery_service,
        "user_instances",
        lambda user: SimpleNamespace(
            get=lambda **kwargs: SimpleNamespace(id=1, instance_name="ins")
        ),
    )
    monkeypatch.setattr(sqlquery_service, "SysConfig", lambda: _FakeConfig())
    monkeypatch.setattr(sqlquery_service, "get_engine", lambda instance: fake_engine)
    monkeypatch.setattr(
        sqlquery_service,
        "query_priv_check",
        lambda *args, **kwargs: {"status": 2, "msg": "no priv", "data": {}},
    )

    result = sqlquery_service.execute_sql_query(
        user=SimpleNamespace(username="u", display="U"),
        instance_name="ins",
        db_name="db",
        sql_content="select 1",
        limit_num=10,
    )

    assert result["status"] == 2
    assert result["msg"] == "no priv"


@pytest.mark.django_db
def test_execute_sql_query_success_and_querylog_created(monkeypatch):
    query_result = _fake_query_result(error=None, affected_rows=5)
    fake_engine = SimpleNamespace(
        query_check=lambda **kwargs: {
            "bad_query": False,
            "msg": "",
            "filtered_sql": "select 1",
            "has_star": False,
        },
        filter_sql=lambda **kwargs: "select 1 limit 10",
        get_connection=lambda **kwargs: None,
        query=lambda *args, **kwargs: query_result,
        thread_id=None,
        seconds_behind_master=0,
    )

    created = {}
    monkeypatch.setattr(
        sqlquery_service,
        "user_instances",
        lambda user: SimpleNamespace(
            get=lambda **kwargs: SimpleNamespace(id=1, instance_name="ins")
        ),
    )
    monkeypatch.setattr(
        sqlquery_service,
        "SysConfig",
        lambda: _FakeConfig({"disable_star": False, "data_masking": False}),
    )
    monkeypatch.setattr(sqlquery_service, "get_engine", lambda instance: fake_engine)
    monkeypatch.setattr(
        sqlquery_service,
        "query_priv_check",
        lambda *args, **kwargs: {
            "status": 0,
            "msg": "ok",
            "data": {"limit_num": 10, "priv_check": True},
        },
    )
    monkeypatch.setattr(
        sqlquery_service.QueryLog.objects,
        "create",
        lambda **kwargs: created.update(kwargs),
    )
    monkeypatch.setattr(sqlquery_service.connection, "connection", None)

    result = sqlquery_service.execute_sql_query(
        user=SimpleNamespace(username="u", display="U"),
        instance_name="ins",
        db_name="db",
        sql_content="select 1",
        limit_num=10,
    )

    assert result["status"] == 0
    assert result["msg"] == "ok"
    assert result["data"]["rows"] == [[1]]
    assert result["data"]["seconds_behind_master"] == 0
    assert created["instance_name"] == "ins"
    assert created["effect_row"] == 5
