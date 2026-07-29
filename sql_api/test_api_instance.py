import pytest
from rest_framework.test import APIClient
from sql.models import Instance
from rest_framework.exceptions import ValidationError

CANONICAL = {
    "instance_resource": "/api/v1/instance/resource/",
}


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_user(super_user):
    return super_user


@pytest.fixture
def test_instance():
    instance = Instance.objects.create(
        instance_name="test_instance",
        type="mysql",
        db_type="mysql",
        host="127.0.0.1",
        port=3306,
        user="root",
        password="password",
    )
    return instance


class MockResource:
    def __init__(self, rows, error=None):
        self.rows = rows
        self.error = error


class MockEngine:
    def __init__(self, instance):
        self.instance = instance

        # Mock enum for fork_type
        class ForkType:
            value = "mysql"

        self.server_fork_type = ForkType()

    def escape_string(self, value):
        return value

    def get_all_databases(self):
        return MockResource(["db1", "db2"])

    def get_all_schemas(self, db_name):
        return MockResource(["schema1", "schema2"])

    def get_all_tables(self, db_name, schema_name):
        return MockResource(["table1", "table2"])

    def get_all_columns_by_tb(self, db_name, tb_name, schema_name):
        return MockResource(["col1", "col2"])


@pytest.mark.django_db
def test_instance_resource_database(
    monkeypatch, api_client, authenticated_user, test_instance
):
    monkeypatch.setattr(
        "sql_api.api_instance.get_engine", lambda instance: MockEngine(instance)
    )
    monkeypatch.setattr(
        "sql_api.api_instance.filter_db_list",
        lambda db_list, db_name_regex, is_match_regex: db_list,
    )
    api_client.force_authenticate(user=authenticated_user)

    response = api_client.post(
        CANONICAL["instance_resource"],
        {"instance_id": test_instance.id, "resource_type": "database"},
    )

    assert response.status_code == 200
    assert response.data["count"] == 2
    assert response.data["result"] == ["db1", "db2"]


@pytest.mark.django_db
def test_instance_resource_schema(
    monkeypatch, api_client, authenticated_user, test_instance
):
    monkeypatch.setattr(
        "sql_api.api_instance.get_engine", lambda instance: MockEngine(instance)
    )
    api_client.force_authenticate(user=authenticated_user)

    response = api_client.post(
        CANONICAL["instance_resource"],
        {"instance_id": test_instance.id, "resource_type": "schema", "db_name": "db1"},
    )

    assert response.status_code == 200
    assert response.data["count"] == 2
    assert response.data["result"] == ["schema1", "schema2"]


@pytest.mark.django_db
def test_instance_resource_table(
    monkeypatch, api_client, authenticated_user, test_instance
):
    monkeypatch.setattr(
        "sql_api.api_instance.get_engine", lambda instance: MockEngine(instance)
    )
    api_client.force_authenticate(user=authenticated_user)

    response = api_client.post(
        CANONICAL["instance_resource"],
        {
            "instance_id": test_instance.id,
            "resource_type": "table",
            "db_name": "db1",
            "schema_name": "schema1",
        },
    )

    assert response.status_code == 200
    assert response.data["count"] == 2
    assert response.data["result"] == ["table1", "table2"]


@pytest.mark.django_db
def test_instance_resource_column(
    monkeypatch, api_client, authenticated_user, test_instance
):
    monkeypatch.setattr(
        "sql_api.api_instance.get_engine", lambda instance: MockEngine(instance)
    )
    api_client.force_authenticate(user=authenticated_user)

    response = api_client.post(
        CANONICAL["instance_resource"],
        {
            "instance_id": test_instance.id,
            "resource_type": "column",
            "db_name": "db1",
            "tb_name": "table1",
            "schema_name": "schema1",
        },
    )

    assert response.status_code == 200
    assert response.data["count"] == 2
    assert response.data["result"] == ["col1", "col2"]


@pytest.mark.django_db
def test_instance_resource_server_info(
    monkeypatch, api_client, authenticated_user, test_instance
):
    monkeypatch.setattr(
        "sql_api.api_instance.get_engine", lambda instance: MockEngine(instance)
    )
    api_client.force_authenticate(user=authenticated_user)

    response = api_client.post(
        CANONICAL["instance_resource"],
        {"instance_id": test_instance.id, "resource_type": "server_info"},
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["result"] == ["mysql"]


@pytest.mark.django_db
def test_instance_resource_server_info_no_fork(
    monkeypatch, api_client, authenticated_user, test_instance
):
    class MockEngineNoFork:
        def __init__(self, instance):
            self.instance = instance

        def escape_string(self, value):
            return value

    monkeypatch.setattr(
        "sql_api.api_instance.get_engine", lambda instance: MockEngineNoFork(instance)
    )
    api_client.force_authenticate(user=authenticated_user)

    response = api_client.post(
        CANONICAL["instance_resource"],
        {"instance_id": test_instance.id, "resource_type": "server_info"},
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["result"] == ["mysql"]


@pytest.mark.django_db
def test_instance_resource_invalid_params(
    api_client, authenticated_user, test_instance
):
    api_client.force_authenticate(user=authenticated_user)

    response = api_client.post(
        CANONICAL["instance_resource"],
        {
            "instance_id": test_instance.id,
            # missing resource_type
        },
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_instance_resource_invalid_type(
    monkeypatch, api_client, authenticated_user, test_instance
):
    monkeypatch.setattr(
        "sql_api.api_instance.get_engine", lambda instance: MockEngine(instance)
    )
    api_client.force_authenticate(user=authenticated_user)

    response = api_client.post(
        CANONICAL["instance_resource"],
        {"instance_id": test_instance.id, "resource_type": "invalid_type"},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_instance_resource_missing_args(
    monkeypatch, api_client, authenticated_user, test_instance
):
    monkeypatch.setattr(
        "sql_api.api_instance.get_engine", lambda instance: MockEngine(instance)
    )
    api_client.force_authenticate(user=authenticated_user)

    response = api_client.post(
        CANONICAL["instance_resource"],
        {"instance_id": test_instance.id, "resource_type": "table"},  # Missing db_name
    )

    assert response.status_code == 400
    assert "errors" in response.data


@pytest.mark.django_db
def test_instance_resource_engine_exception(
    monkeypatch, api_client, authenticated_user, test_instance
):
    def mock_get_engine(instance):
        raise Exception("Connection failed")

    monkeypatch.setattr("sql_api.api_instance.get_engine", mock_get_engine)
    api_client.force_authenticate(user=authenticated_user)

    response = api_client.post(
        CANONICAL["instance_resource"],
        {"instance_id": test_instance.id, "resource_type": "database"},
    )

    assert response.status_code == 400
    assert "errors" in response.data


@pytest.mark.django_db
def test_instance_resource_engine_error_resource(
    monkeypatch, api_client, authenticated_user, test_instance
):
    class ErrorEngine(MockEngine):
        def get_all_databases(self):
            return MockResource([], error="Error getting databases")

    monkeypatch.setattr(
        "sql_api.api_instance.get_engine", lambda instance: ErrorEngine(instance)
    )
    api_client.force_authenticate(user=authenticated_user)

    response = api_client.post(
        CANONICAL["instance_resource"],
        {"instance_id": test_instance.id, "resource_type": "database"},
    )

    assert response.status_code == 400
    assert "errors" in response.data
