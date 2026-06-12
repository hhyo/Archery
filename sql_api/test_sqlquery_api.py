import pytest
from rest_framework.test import APIClient

CANONICAL = {
    "instances": "/api/v1/sqlquery/instances/",
    "resources": "/api/v1/sqlquery/resources/",
    "describetable": "/api/v1/sqlquery/describetable/",
    "execute": "/api/v1/sqlquery/execute/",
    "logs": "/api/v1/sqlquery/logs/",
    "favorites": "/api/v1/sqlquery/favorites/",
}


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_user(normal_user):
    return normal_user


@pytest.fixture
def privileged_user(super_user):
    return super_user


@pytest.mark.django_db
def test_instances_returns_expected_shape(monkeypatch, api_client, authenticated_user):
    expected = {"status": 0, "msg": "ok", "data": [{"id": 1, "instance_name": "ins"}]}

    monkeypatch.setattr(
        "sql_api.api_sqlquery.list_user_accessible_instances",
        lambda **kwargs: expected,
    )

    api_client.force_authenticate(user=authenticated_user)
    response = api_client.get(CANONICAL["instances"])

    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.django_db
def test_resources_returns_expected_shape(monkeypatch, api_client, authenticated_user):
    expected = {"status": 0, "msg": "ok", "data": ["db1", "db2"]}

    monkeypatch.setattr(
        "sql_api.api_sqlquery.list_instance_resources",
        lambda **kwargs: expected,
    )

    api_client.force_authenticate(user=authenticated_user)
    params = {"instance_name": "some_ins", "resource_type": "database"}
    response = api_client.get(CANONICAL["resources"], params)

    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.django_db
def test_describetable_returns_expected_shape(
    monkeypatch, api_client, authenticated_user
):
    expected = {
        "status": 0,
        "msg": "ok",
        "data": {"column_list": ["id", "name"], "rows": [["id", "int"]]},
    }

    monkeypatch.setattr(
        "sql_api.api_sqlquery.describe_table_structure",
        lambda **kwargs: expected,
    )

    api_client.force_authenticate(user=authenticated_user)
    payload = {
        "instance_name": "some_ins",
        "db_name": "archery",
        "tb_name": "users",
        "schema_name": "",
    }
    response = api_client.post(CANONICAL["describetable"], payload, format="json")

    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.django_db
def test_execute_requires_query_permission_or_superuser(api_client, authenticated_user):
    api_client.force_authenticate(user=authenticated_user)
    payload = {
        "instance_name": "some_ins",
        "db_name": "archery",
        "sql_content": "select 1",
        "limit_num": 10,
    }
    response = api_client.post(CANONICAL["execute"], payload, format="json")
    assert response.status_code == 200
    assert response.json()["status"] == 1
    assert "无执行查询权限" in response.json()["msg"]


@pytest.mark.django_db
def test_execute_calls_service(monkeypatch, api_client, privileged_user):
    expected = {
        "status": 0,
        "msg": "ok",
        "data": {"rows": [[1]], "column_list": ["1"], "affected_rows": 1},
    }
    monkeypatch.setattr(
        "sql_api.api_sqlquery.execute_sql_query", lambda **kwargs: expected
    )

    api_client.force_authenticate(user=privileged_user)
    payload = {
        "instance_name": "some_ins",
        "db_name": "archery",
        "sql_content": "select 1",
        "limit_num": 10,
    }
    response = api_client.post(CANONICAL["execute"], payload, format="json")

    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.django_db
def test_execute_renders_non_utf8_bytes_with_simplejson(
    monkeypatch, api_client, privileged_user
):
    expected = {
        "status": 0,
        "msg": "ok",
        "data": {"rows": [[b"\xff\xbd"]], "column_list": ["blob"], "affected_rows": 1},
    }
    monkeypatch.setattr(
        "sql_api.api_sqlquery.execute_sql_query", lambda **kwargs: expected
    )

    api_client.force_authenticate(user=privileged_user)
    payload = {
        "instance_name": "some_ins",
        "db_name": "archery",
        "sql_content": "select 1",
        "limit_num": 10,
    }
    response = api_client.post(CANONICAL["execute"], payload, format="json")

    assert response.status_code == 200
    assert response.json() == {
        "status": 0,
        "msg": "ok",
        "data": {"rows": [["/70="]], "column_list": ["blob"], "affected_rows": 1},
    }


@pytest.mark.django_db
def test_logs_returns_bootstrap_table_shape(monkeypatch, api_client, privileged_user):
    expected = {"total": 1, "rows": [{"id": 1, "sqllog": "select 1"}]}
    monkeypatch.setattr(
        "sql_api.api_sqlquery.list_query_logs", lambda **kwargs: expected
    )

    api_client.force_authenticate(user=privileged_user)
    response = api_client.get(CANONICAL["logs"], {"limit": 10, "offset": 0})

    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.django_db
def test_favorite_returns_expected_shape(monkeypatch, api_client, privileged_user):
    expected = {"status": 0, "msg": "ok"}
    monkeypatch.setattr(
        "sql_api.api_sqlquery.update_favorite", lambda **kwargs: expected
    )

    api_client.force_authenticate(user=privileged_user)
    response = api_client.post(
        CANONICAL["favorites"],
        {"query_log_id": 1, "star": "true", "alias": "first"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json() == expected
