import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from common.config import SysConfig
from sql.models import Instance, ResourceGroup
from sql_api.table_instance_locator import (
    default_table_instance_locator,
    resolve_table_instances,
)


class FakeResult:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error


class FakeEngine:
    def __init__(self, instance, db_tables):
        self.instance = instance
        self._db_tables = db_tables

    def get_all_databases(self):
        return FakeResult(rows=list(self._db_tables.keys()))

    def get_all_tables(self, db_name, **kwargs):
        return FakeResult(rows=self._db_tables.get(db_name, []))


def custom_locator(table_name, instances, **kwargs):
    return [
        {
            "id": ins.id,
            "name": f"custom-{ins.instance_name}",
            "db_type": ins.db_type,
            "db_name": "custom_db",
        }
        for ins in instances
    ]


def custom_minimal_locator(table_name, instances, **kwargs):
    return [{"name": "minimal-instance"}]


@pytest.mark.django_db
def test_default_table_instance_locator_found(monkeypatch, db_instance):
    fake_engine = FakeEngine(db_instance, {"archery": ["users", "orders"]})
    monkeypatch.setattr(
        "sql_api.table_instance_locator.get_engine",
        lambda instance: fake_engine,
    )

    result = default_table_instance_locator("orders", [db_instance])

    assert len(result) == 1
    assert result[0]["name"] == db_instance.instance_name
    assert result[0]["db_name"] == "archery"


@pytest.mark.django_db
def test_resolve_table_instances_with_custom_locator(settings, db_instance):
    settings.TABLE_INSTANCE_LOCATOR = (
        "sql_api.test_table_instance_locator:custom_locator"
    )

    result = resolve_table_instances("orders", [db_instance])

    assert len(result) == 1
    assert result[0]["name"] == f"custom-{db_instance.instance_name}"


@pytest.mark.django_db
def test_resolve_table_instances_custom_locator_must_return_list(settings, db_instance):
    settings.TABLE_INSTANCE_LOCATOR = (
        "sql_api.test_table_instance_locator:invalid_locator"
    )

    with pytest.raises(ValueError):
        resolve_table_instances("orders", [db_instance])


@pytest.mark.django_db
def test_resolve_table_instances_custom_locator_can_return_minimal_dict(
    settings, db_instance
):
    settings.TABLE_INSTANCE_LOCATOR = (
        "sql_api.test_table_instance_locator:custom_minimal_locator"
    )

    result = resolve_table_instances("orders", [db_instance])

    assert result == [
        {
            "id": 0,
            "name": "minimal-instance",
            "db_type": "",
            "db_name": "",
        }
    ]


def invalid_locator(table_name, instances, **kwargs):
    return {"invalid": True}


# ---------------------------------------------------------------------------
# T026: Integration tests — DRF auth wiring + permission-scoped instance lookup
#
# Rationale: DRF auth wiring (IsInUserWhitelist permission class) and
# permission-scoped instance filtering via user_instances(request.user) cannot
# be fully proven via unit tests of the locator logic alone.  These tests cross
# the HTTP → authentication → permission → view → locator boundary.
# ---------------------------------------------------------------------------

_TABLE_INSTANCES_URL = "/api/v1/instance/table-instances/"


@pytest.fixture
def api_user(django_user_model):
    user = django_user_model.objects.create(username="api_test_user", is_active=True)
    user.set_password("pw")
    user.save()
    SysConfig().set("api_user_whitelist", user.id)
    yield user
    SysConfig().purge()
    user.delete()


@pytest.fixture
def api_client_auth(api_user):
    client = APIClient()
    client.force_authenticate(user=api_user)
    return client


_WHITELIST_RF_SETTINGS = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("sql_api.permissions.IsInUserWhitelist",),
}


@pytest.mark.django_db
@override_settings(REST_FRAMEWORK=_WHITELIST_RF_SETTINGS)
def test_unauthenticated_request_is_rejected():
    """Unauthenticated callers must be rejected (403) by IsInUserWhitelist."""
    client = APIClient()
    r = client.post(_TABLE_INSTANCES_URL, {"table_name": "orders"}, format="json")
    assert r.status_code == 403


@pytest.mark.django_db
@override_settings(REST_FRAMEWORK=_WHITELIST_RF_SETTINGS)
def test_user_not_in_whitelist_is_rejected(django_user_model):
    """Authenticated users absent from api_user_whitelist must receive 403."""
    user = django_user_model.objects.create(username="unwhitelisted", is_active=True)
    # Ensure whitelist is empty — no Config entry means empty whitelist
    SysConfig().purge()
    try:
        client = APIClient()
        client.force_authenticate(user=user)
        r = client.post(_TABLE_INSTANCES_URL, {"table_name": "orders"}, format="json")
        assert r.status_code == 403
    finally:
        user.delete()


@pytest.mark.django_db
def test_whitelisted_user_receives_response_structure(
    api_user, api_client_auth, db_instance, monkeypatch
):
    """Whitelisted user gets a well-formed {status, msg, count, data} response."""
    rg = ResourceGroup.objects.create(group_id=901, group_name="rg_test_901")
    # Users.resource_group is the M2M field from the User side
    api_user.resource_group.add(rg)
    db_instance.resource_group.add(rg)

    fake_engine = FakeEngine(db_instance, {"shop": ["orders", "products"]})
    monkeypatch.setattr(
        "sql_api.table_instance_locator.get_engine", lambda instance: fake_engine
    )

    r = api_client_auth.post(
        _TABLE_INSTANCES_URL, {"table_name": "orders"}, format="json"
    )

    rg.delete()

    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "msg" in body
    assert "count" in body
    assert "data" in body
    assert body["status"] == 0


@pytest.mark.django_db
def test_instance_outside_resource_group_excluded(api_user, db_instance, monkeypatch):
    """Instances not in the requesting user's resource groups must not appear in results.

    This validates user_instances() permission scoping: the user has no resource
    group associations, so the locator receives an empty instance queryset and
    returns no results even when the table physically exists on db_instance.
    """
    # api_user has no resource group → user_instances() returns empty queryset
    fake_engine = FakeEngine(db_instance, {"shop": ["orders"]})
    monkeypatch.setattr(
        "sql_api.table_instance_locator.get_engine", lambda instance: fake_engine
    )

    client = APIClient()
    client.force_authenticate(user=api_user)
    r = client.post(_TABLE_INSTANCES_URL, {"table_name": "orders"}, format="json")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == 0
    assert body["count"] == 0
    assert body["data"] == []


@pytest.mark.django_db
def test_invalid_input_returns_status_1(api_client_auth):
    """Missing table_name field must yield status=1 in the response body."""
    r = api_client_auth.post(_TABLE_INSTANCES_URL, {}, format="json")
    assert r.status_code == 200
    assert r.json()["status"] == 1
