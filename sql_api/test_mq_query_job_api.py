# -*- coding: UTF-8 -*-
import pytest
from django.contrib.auth.models import Permission
from django.core.cache import cache
from rest_framework.test import APIClient

from sql.models import Instance, InstanceTag

MQ_JOBS = "/api/v1/sqlquery/mq-jobs/"
MQ_JOB_DETAIL = "/api/v1/sqlquery/mq-jobs/{job_id}/"
MQ_JOB_CANCEL = "/api/v1/sqlquery/mq-jobs/{job_id}/cancel/"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def mqtt_instance(db):
    tag = InstanceTag.objects.create(
        tag_code="can_read", tag_name="支持查询", active=True
    )
    ins = Instance.objects.create(
        instance_name="mqtt_api_ins",
        type="slave",
        db_type="mqtt",
        host="127.0.0.1",
        port=1883,
        user="",
        password="",
    )
    ins.instance_tag.add(tag)
    yield ins
    ins.delete()
    tag.delete()


@pytest.fixture
def query_user(normal_user):
    for codename in ("query_all_instances", "query_submit"):
        perm = Permission.objects.get(codename=codename)
        normal_user.user_permissions.add(perm)
    return normal_user


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_create_mq_job_returns_job_id(monkeypatch, api_client, super_user):
    captured = {}

    def fake_create(user, instance_id, db_name, sql_line):
        captured["user"] = user
        captured["instance_id"] = instance_id
        captured["db_name"] = db_name
        captured["sql_line"] = sql_line
        return {"job_id": "abc123"}

    monkeypatch.setattr("sql_api.api_sqlquery.create_mq_query_job", fake_create)

    api_client.force_authenticate(user=super_user)
    response = api_client.post(
        MQ_JOBS,
        {
            "instance_id": 42,
            "db_name": "default",
            "sql_line": "sub -t demo/topic -C 5",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.json() == {"job_id": "abc123"}
    assert captured["user"] == super_user
    assert captured["instance_id"] == 42
    assert captured["db_name"] == "default"
    assert captured["sql_line"] == "sub -t demo/topic -C 5"


@pytest.mark.django_db
def test_create_mq_job_resolves_instance_name(
    monkeypatch, api_client, super_user, db_instance
):
    captured = {}

    def fake_create(user, instance_id, db_name, sql_line):
        captured["instance_id"] = instance_id
        return {"job_id": "named1"}

    monkeypatch.setattr("sql_api.api_sqlquery.create_mq_query_job", fake_create)

    api_client.force_authenticate(user=super_user)
    response = api_client.post(
        MQ_JOBS,
        {
            "instance_name": db_instance.instance_name,
            "db_name": "default",
            "sql_line": "sub -t t -C 1",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.json() == {"job_id": "named1"}
    assert captured["instance_id"] == db_instance.id


@pytest.mark.django_db
def test_create_mq_job_requires_auth(api_client):
    response = api_client.post(
        MQ_JOBS,
        {"instance_id": 1, "db_name": "d", "sql_line": "sub -t t"},
        format="json",
    )
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_create_mq_job_validation_error(api_client, super_user):
    api_client.force_authenticate(user=super_user)
    response = api_client.post(
        MQ_JOBS,
        {"db_name": "default", "sql_line": "sub -t t"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_get_mq_job_returns_payload_without_cancel(monkeypatch, api_client, super_user):
    job = {
        "job_id": "j1",
        "user_id": super_user.id,
        "instance_id": 1,
        "db_name": "default",
        "sql_line": "sub -t t",
        "status": "running",
        "column_list": ["payload"],
        "rows": [["hi"]],
        "warning": "",
        "error": "",
        "cancel": True,
        "timeout_sec": 60,
    }
    monkeypatch.setattr(
        "sql_api.api_sqlquery.get_mq_query_job",
        lambda user, job_id: job,
    )

    api_client.force_authenticate(user=super_user)
    response = api_client.get(MQ_JOB_DETAIL.format(job_id="j1"))

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "j1"
    assert body["status"] == "running"
    assert body["rows"] == [["hi"]]
    assert "cancel" not in body


@pytest.mark.django_db
def test_get_mq_job_not_found(monkeypatch, api_client, super_user):
    def raise_missing(user, job_id):
        raise KeyError(f"job not found: {job_id}")

    monkeypatch.setattr("sql_api.api_sqlquery.get_mq_query_job", raise_missing)

    api_client.force_authenticate(user=super_user)
    response = api_client.get(MQ_JOB_DETAIL.format(job_id="missing"))
    assert response.status_code == 404


@pytest.mark.django_db
def test_cancel_mq_job_returns_status(monkeypatch, api_client, super_user):
    monkeypatch.setattr(
        "sql_api.api_sqlquery.cancel_mq_query_job",
        lambda user, job_id: {
            "job_id": job_id,
            "status": "running",
            "cancel": True,
            "rows": [],
        },
    )

    api_client.force_authenticate(user=super_user)
    response = api_client.post(MQ_JOB_CANCEL.format(job_id="j1"), format="json")

    assert response.status_code == 200
    assert response.json() == {"status": "running"}


@pytest.mark.django_db
def test_create_mq_job_service_value_error(monkeypatch, api_client, super_user):
    def raise_value(user, instance_id, db_name, sql_line):
        raise ValueError("仅 MQTT/RabbitMQ 支持异步查询任务")

    monkeypatch.setattr("sql_api.api_sqlquery.create_mq_query_job", raise_value)

    api_client.force_authenticate(user=super_user)
    response = api_client.post(
        MQ_JOBS,
        {
            "instance_id": 1,
            "db_name": "d",
            "sql_line": "sub -t t",
        },
        format="json",
    )
    assert response.status_code == 400
    assert "MQTT" in response.json()["msg"]


@pytest.mark.django_db
def test_mq_job_apis_require_query_submit(
    monkeypatch, api_client, normal_user, mqtt_instance
):
    """Logged-in user without query_submit cannot create/detail/cancel."""
    perm = Permission.objects.get(codename="query_all_instances")
    normal_user.user_permissions.add(perm)
    monkeypatch.setattr(
        "sql.services.mq_query_job._enqueue_mq_query_job", lambda *a, **k: None
    )

    api_client.force_authenticate(user=normal_user)
    create_resp = api_client.post(
        MQ_JOBS,
        {
            "instance_id": mqtt_instance.id,
            "db_name": "default",
            "sql_line": "sub -t demo/topic -C 1",
        },
        format="json",
    )
    assert create_resp.status_code == 403
    assert "无执行查询权限" in create_resp.json()["msg"]

    detail_resp = api_client.get(MQ_JOB_DETAIL.format(job_id="x"))
    assert detail_resp.status_code == 403

    cancel_resp = api_client.post(MQ_JOB_CANCEL.format(job_id="x"), format="json")
    assert cancel_resp.status_code == 403


@pytest.mark.django_db
def test_create_get_cancel_with_async_task_mocked(
    monkeypatch, api_client, query_user, mqtt_instance, settings
):
    settings.Q_CLUSTER = {**dict(settings.Q_CLUSTER), "sync": False}
    queued = []

    def fake_async_task(func_path, job_id, *args, **kwargs):
        queued.append((func_path, job_id))

    monkeypatch.setattr("sql.services.mq_query_job.async_task", fake_async_task)

    api_client.force_authenticate(user=query_user)
    create_resp = api_client.post(
        MQ_JOBS,
        {
            "instance_id": mqtt_instance.id,
            "db_name": "default",
            "sql_line": "sub -t demo/topic -C 3",
        },
        format="json",
    )
    assert create_resp.status_code == 200
    job_id = create_resp.json()["job_id"]
    assert queued == [("sql.services.mq_query_job.run_mq_query_job", job_id)]

    detail_resp = api_client.get(MQ_JOB_DETAIL.format(job_id=job_id))
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == "pending"
    assert "cancel" not in detail_resp.json()

    cancel_resp = api_client.post(MQ_JOB_CANCEL.format(job_id=job_id), format="json")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "pending"
