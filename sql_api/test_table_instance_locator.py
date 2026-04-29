import pytest

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
