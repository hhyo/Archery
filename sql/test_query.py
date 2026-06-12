from types import SimpleNamespace

import pytest
import simplejson as json
from django.utils.datastructures import MultiValueDict

from sql import query as query_module


class _Request:
    def __init__(self, user=None, post=None, get=None):
        self.user = user or SimpleNamespace(username="tester")
        self.POST = MultiValueDict()
        self.GET = MultiValueDict()

        for key, value in (post or {}).items():
            if isinstance(value, list):
                self.POST.setlist(key, value)
            else:
                self.POST[key] = value

        for key, value in (get or {}).items():
            if isinstance(value, list):
                self.GET.setlist(key, value)
            else:
                self.GET[key] = value


class _FakeQueryResult:
    def __init__(self, rows):
        self.rows = rows


def _json_content(response):
    return json.loads(response.content.decode())


def test_query_calls_execute_sql_query_with_request_params(monkeypatch):
    captured = {}
    expected = {"status": 0, "msg": "ok", "data": {"rows": [[1]]}}

    def fake_execute_sql_query(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(query_module, "execute_sql_query", fake_execute_sql_query)
    user = SimpleNamespace(username="tester")
    request = _Request(
        user=user,
        post={
            "instance_name": "some_ins",
            "db_name": "archery",
            "sql_content": "select 1",
            "limit_num": "100",
            "schema_name": "public",
            "tb_name": "users",
        },
    )

    response = query_module.query.__wrapped__(request)

    assert response["Content-Type"] == "application/json"
    assert _json_content(response) == expected
    assert captured == {
        "user": user,
        "instance_name": "some_ins",
        "db_name": "archery",
        "sql_content": "select 1",
        "limit_num": "100",
        "schema_name": "public",
        "tb_name": "users",
    }


def test_querylog_converts_filters_and_returns_json(monkeypatch):
    captured = {}
    expected = {"total": 1, "rows": [{"id": 1, "sql": "select 1"}]}

    def fake_list_query_logs(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(query_module, "list_query_logs", fake_list_query_logs)
    user = SimpleNamespace(username="tester")
    request = _Request(
        user=user,
        get={
            "limit": "20",
            "offset": "5",
            "star": "true",
            "query_log_id": "7",
            "search": "select",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        },
    )

    response = query_module._querylog(request)

    assert response["Content-Type"] == "application/json"
    assert _json_content(response) == expected
    assert captured == {
        "user": user,
        "limit": 20,
        "offset": 5,
        "star": True,
        "query_log_id": "7",
        "search": "select",
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
    }


def test_favorite_converts_star_and_calls_service(monkeypatch):
    captured = {}
    expected = {"status": 0, "msg": "ok"}

    def fake_update_favorite(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(query_module, "update_favorite", fake_update_favorite)
    user = SimpleNamespace(username="tester")
    request = _Request(
        user=user,
        post={"query_log_id": "9", "star": "true", "alias": "first query"},
    )

    response = query_module.favorite.__wrapped__(request)

    assert _json_content(response) == expected
    assert captured == {
        "user": user,
        "query_log_id": "9",
        "star": True,
        "alias": "first query",
    }


def test_kill_query_conn_uses_instance_engine(monkeypatch):
    killed = {}
    instance = SimpleNamespace(id=1)
    fake_engine = SimpleNamespace(
        kill_connection=lambda thread_id: killed.update(thread_id=thread_id)
    )

    monkeypatch.setattr(
        query_module.Instance.objects,
        "get",
        lambda pk: instance,
    )
    monkeypatch.setattr(query_module, "get_engine", lambda instance: fake_engine)

    query_module.kill_query_conn(instance_id=1, thread_id=12345)

    assert killed == {"thread_id": 12345}


def test_generate_sql_requires_query_desc_and_db_type():
    request = _Request(post={"query_desc": "", "db_type": "mysql"})

    response = query_module.generate_sql.__wrapped__(request)

    assert _json_content(response) == {
        "status": 1,
        "msg": "query_desc or db_type不存在",
        "data": [],
    }


def test_generate_sql_returns_instance_not_found(monkeypatch):
    monkeypatch.setattr(
        query_module.Instance.objects,
        "get",
        lambda instance_name: (_ for _ in ()).throw(query_module.Instance.DoesNotExist),
    )
    request = _Request(
        post={
            "query_desc": "find users",
            "db_type": "mysql",
            "instance_name": "missing",
        }
    )

    response = query_module.generate_sql.__wrapped__(request)

    assert _json_content(response) == {"status": 1, "msg": "实例不存在", "data": []}


def test_generate_sql_builds_table_structure_and_calls_openai(monkeypatch):
    captured = {}
    instance = SimpleNamespace(instance_name="some_ins")
    fake_engine = SimpleNamespace(
        describe_table=lambda db_name, tb_name, schema_name=None: _FakeQueryResult(
            rows=[[tb_name, "ignored", f"create table {tb_name}"]]
        )
    )

    class FakeOpenaiClient:
        def generate_sql_by_openai(self, db_type, table_schema, query_desc):
            captured.update(
                db_type=db_type,
                table_schema=table_schema,
                query_desc=query_desc,
            )
            return "select * from users"

    monkeypatch.setattr(
        query_module.Instance.objects,
        "get",
        lambda instance_name: instance,
    )
    monkeypatch.setattr(query_module, "get_engine", lambda instance: fake_engine)
    monkeypatch.setattr(query_module, "OpenaiClient", FakeOpenaiClient)
    request = _Request(
        post={
            "query_desc": "find users",
            "db_type": "mysql",
            "instance_name": "some_ins",
            "db_name": "archery",
            "schema_name": "public",
            "tb_name_list[]": ["users", "orders"],
        }
    )

    response = query_module.generate_sql.__wrapped__(request)

    assert _json_content(response) == {
        "status": 0,
        "msg": "ok",
        "data": "select * from users",
    }
    assert captured == {
        "db_type": "mysql",
        "table_schema": "create table users\n\ncreate table orders",
        "query_desc": "find users",
    }


def test_generate_sql_returns_exception_message(monkeypatch):
    monkeypatch.setattr(
        query_module.Instance.objects,
        "get",
        lambda instance_name: SimpleNamespace(instance_name="some_ins"),
    )
    monkeypatch.setattr(
        query_module,
        "get_engine",
        lambda instance: (_ for _ in ()).throw(RuntimeError("connect failed")),
    )
    request = _Request(
        post={
            "query_desc": "find users",
            "db_type": "mysql",
            "instance_name": "some_ins",
            "db_name": "archery",
            "tb_name_list": ["users"],
        }
    )

    response = query_module.generate_sql.__wrapped__(request)

    assert _json_content(response) == {
        "status": 1,
        "msg": "connect failed",
        "data": "",
    }


@pytest.mark.parametrize(
    ("config_valid", "expected"),
    [
        (True, {"status": 0, "msg": "ok", "data": True}),
        (
            False,
            {
                "status": 1,
                "msg": "openai 缺少配置, 必需配置[openai_base_url, openai_api_key, default_chat_model]",
                "data": False,
            },
        ),
    ],
)
def test_check_openai_returns_config_status(monkeypatch, config_valid, expected):
    monkeypatch.setattr(query_module, "check_openai_config", lambda: config_valid)

    response = query_module.check_openai(_Request())

    assert _json_content(response) == expected
