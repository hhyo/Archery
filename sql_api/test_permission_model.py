import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_normal_user_cannot_access_non_query_api(api_client, normal_user):
    api_client.force_authenticate(user=normal_user)
    response = api_client.get("/api/v1/instance/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_superuser_can_access_non_query_api(api_client, super_user):
    api_client.force_authenticate(user=super_user)
    response = api_client.get("/api/v1/instance/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_normal_user_can_access_query_api(api_client, normal_user, monkeypatch):
    expected = {"status": 0, "msg": "ok", "data": [{"id": 1, "instance_name": "ins"}]}
    monkeypatch.setattr(
        "sql_api.api_sqlquery.list_user_accessible_instances",
        lambda **kwargs: expected,
    )

    api_client.force_authenticate(user=normal_user)
    response = api_client.get("/api/v1/sqlquery/instances/")

    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.django_db
def test_normal_user_can_access_table_locator(api_client, normal_user, monkeypatch):
    monkeypatch.setattr("sql_api.api_instance.user_instances", lambda user: [])
    monkeypatch.setattr(
        "sql_api.api_instance.resolve_table_instances", lambda **kwargs: []
    )

    api_client.force_authenticate(user=normal_user)
    response = api_client.post(
        "/api/v1/instance/table-instances/",
        {"table_name": "orders"},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == 0
    assert body["count"] == 0
