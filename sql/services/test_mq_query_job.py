# -*- coding: UTF-8 -*-
import threading
import time

import pytest
from django.contrib.auth.models import Permission
from django.core.cache import cache

from sql.engines.models import ResultSet
from sql.models import Instance, InstanceTag, QueryLog
from sql.services import mq_query_job as svc


@pytest.fixture
def can_read_tag(db):
    tag = InstanceTag.objects.create(
        tag_code="can_read", tag_name="支持查询", active=True
    )
    yield tag
    tag.delete()


@pytest.fixture
def mqtt_instance(db, can_read_tag):
    ins = Instance.objects.create(
        instance_name="mqtt_ins",
        type="slave",
        db_type="mqtt",
        host="127.0.0.1",
        port=1883,
        user="",
        password="",
    )
    ins.instance_tag.add(can_read_tag)
    yield ins
    ins.delete()


@pytest.fixture
def rabbitmq_instance(db, can_read_tag):
    ins = Instance.objects.create(
        instance_name="rabbitmq_ins",
        type="slave",
        db_type="rabbitmq",
        host="127.0.0.1",
        port=5672,
        user="guest",
        password="guest",
    )
    ins.instance_tag.add(can_read_tag)
    yield ins
    ins.delete()


@pytest.fixture
def query_user(normal_user):
    perm = Permission.objects.get(codename="query_all_instances")
    normal_user.user_permissions.add(perm)
    return normal_user


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_create_mq_job_requires_db_priv(monkeypatch, normal_user, mqtt_instance):
    from django.contrib.auth.models import Permission

    from sql.models import ResourceGroup

    perm = Permission.objects.get(codename="query_submit")
    normal_user.user_permissions.add(perm)
    # 用户可读实例（资源组），但无任何库查询权限
    group = ResourceGroup.objects.create(group_name="mq_priv_group")
    normal_user.resource_group.add(group)
    mqtt_instance.resource_group.add(group)
    monkeypatch.setattr(
        "sql.services.mq_query_job.query_priv_check",
        lambda *a, **k: {
            "status": 2,
            "msg": "你无db的查询权限！请先到查询权限管理进行申请",
            "data": {},
        },
    )
    with pytest.raises(PermissionError):
        svc.create_mq_query_job(
            user=normal_user,
            instance_id=mqtt_instance.id,
            db_name="vhost1",
            sql_line="sub -t t",
        )


@pytest.mark.django_db
def test_create_rejects_non_mq_instance(db_instance, query_user, can_read_tag):
    db_instance.instance_tag.add(can_read_tag)
    with pytest.raises(ValueError, match="仅 MQTT/RabbitMQ"):
        svc.create_mq_query_job(query_user, db_instance.id, "db", "sub -t t")


@pytest.mark.django_db
def test_create_rejects_non_async_actions(mqtt_instance, rabbitmq_instance, query_user):
    with pytest.raises(ValueError, match="仅 sub"):
        svc.create_mq_query_job(
            query_user, mqtt_instance.id, "default", "pub -t t -m hi"
        )
    with pytest.raises(ValueError, match="仅 get"):
        svc.create_mq_query_job(query_user, rabbitmq_instance.id, "/", "help")


@pytest.mark.django_db
def test_create_validates_query_command(mqtt_instance, rabbitmq_instance, query_user):
    with pytest.raises(ValueError, match="sub requires topic"):
        svc.create_mq_query_job(query_user, mqtt_instance.id, "default", "sub")
    with pytest.raises(ValueError, match="count 必须为正整数"):
        svc.create_mq_query_job(
            query_user, mqtt_instance.id, "default", "sub -t t -C 0"
        )
    with pytest.raises(ValueError, match="get requires queue"):
        svc.create_mq_query_job(query_user, rabbitmq_instance.id, "/", "get")


@pytest.mark.django_db
def test_enqueue_passes_timeout_to_async_task(monkeypatch, settings):
    """Non-sync enqueue must pass per-task django-q timeout = wait + 60."""
    settings.Q_CLUSTER = {**dict(settings.Q_CLUSTER), "sync": False}
    captured = {}

    def fake_async_task(func, job_id, *args, **kwargs):
        captured["func"] = func
        captured["job_id"] = job_id
        captured["timeout"] = kwargs.get("timeout")

    monkeypatch.setattr(svc, "async_task", fake_async_task)
    svc._enqueue_mq_query_job("abc", timeout_sec=120)
    assert captured["func"] == "sql.services.mq_query_job.run_mq_query_job"
    assert captured["job_id"] == "abc"
    assert captured["timeout"] == 180  # 120 + 60 buffer


@pytest.mark.django_db
def test_create_writes_pending_job_and_queues_task(
    mqtt_instance, query_user, monkeypatch, settings
):
    settings.Q_CLUSTER = {**dict(settings.Q_CLUSTER), "sync": False}
    queued = []

    def fake_async_task(func_path, job_id, *args, **kwargs):
        queued.append((func_path, job_id, kwargs.get("timeout")))

    monkeypatch.setattr(svc, "async_task", fake_async_task)

    result = svc.create_mq_query_job(
        query_user, mqtt_instance.id, "default", "sub -t demo/topic -C 5"
    )
    assert "job_id" in result
    job_id = result["job_id"]
    job = cache.get(svc.job_cache_key(job_id))
    assert job is not None
    assert job["status"] == "pending"
    assert job["user_id"] == query_user.id
    assert job["instance_id"] == mqtt_instance.id
    assert job["sql_line"] == "sub -t demo/topic -C 5"
    assert job["timeout_sec"] == 60
    assert job["cancel"] is False
    assert job["rows"] == []
    assert queued == [("sql.services.mq_query_job.run_mq_query_job", job_id, 120)]


@pytest.mark.django_db
def test_sync_mode_create_returns_before_job_finishes(
    mqtt_instance, query_user, monkeypatch, settings
):
    """Q_CLUSTER sync must not block create — UI needs job_id to poll partial rows."""
    started = threading.Event()
    release = threading.Event()

    def blocking_run(job_id):
        started.set()
        release.wait(timeout=5)

    monkeypatch.setattr(svc, "run_mq_query_job", blocking_run)
    settings.Q_CLUSTER = {**dict(settings.Q_CLUSTER), "sync": True}

    t0 = time.monotonic()
    result = svc.create_mq_query_job(
        query_user, mqtt_instance.id, "default", "sub -t demo"
    )
    assert time.monotonic() - t0 < 1.0
    assert result["job_id"]
    assert started.wait(2.0)
    assert cache.get(svc.job_cache_key(result["job_id"]))["status"] == "pending"
    release.set()


@pytest.mark.django_db
def test_on_message_sets_column_list_while_partial(
    mqtt_instance, query_user, monkeypatch
):
    """Frontend only renders rows when column_list is set; must be present on partial."""
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)
    job_id = svc.create_mq_query_job(
        query_user, mqtt_instance.id, "default", "sub -t demo -C 2"
    )["job_id"]
    mid = {}

    def fake_run_subscribe(
        self,
        topic,
        qos,
        max_msgs,
        timeout_sec,
        cancel_check=None,
        on_message=None,
        **kwargs,
    ):
        row = ["demo", "hello", 0, False]
        if on_message:
            on_message(row)
            snapshot = cache.get(svc.job_cache_key(job_id))
            mid["status"] = snapshot["status"]
            mid["column_list"] = list(snapshot.get("column_list") or [])
            mid["rows"] = list(snapshot.get("rows") or [])
        result = ResultSet(
            full_sql=kwargs.get("full_sql", ""),
            column_list=["topic", "payload", "qos", "retain"],
        )
        result.rows = [row]
        result.affected_rows = 1
        return result

    monkeypatch.setattr("sql.engines.mqtt.MqttEngine.run_subscribe", fake_run_subscribe)
    svc.run_mq_query_job(job_id)
    assert mid["status"] == "partial"
    assert mid["column_list"] == ["topic", "payload", "qos", "retain"]
    assert mid["rows"] == [["demo", "hello", 0, False]]


@pytest.mark.django_db
def test_timeout_sec_uses_sysconfig_default_and_clamp(
    mqtt_instance, query_user, monkeypatch, setup_sys_config
):
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)

    setup_sys_config.set("mq_query_timeout_default", "120")
    setup_sys_config.set("mq_query_timeout_max", "200")
    job_id = svc.create_mq_query_job(
        query_user, mqtt_instance.id, "default", "sub -t t"
    )["job_id"]
    assert cache.get(svc.job_cache_key(job_id))["timeout_sec"] == 120

    setup_sys_config.set("mq_query_timeout_default", "9999")
    setup_sys_config.set("mq_query_timeout_max", "100")
    job_id = svc.create_mq_query_job(
        query_user, mqtt_instance.id, "default", "sub -t t2"
    )["job_id"]
    assert cache.get(svc.job_cache_key(job_id))["timeout_sec"] == 100

    setup_sys_config.set("mq_query_timeout_default", "0")
    setup_sys_config.set("mq_query_timeout_max", "3600")
    job_id = svc.create_mq_query_job(
        query_user, mqtt_instance.id, "default", "sub -t t3"
    )["job_id"]
    assert cache.get(svc.job_cache_key(job_id))["timeout_sec"] == 1


@pytest.mark.django_db
def test_cancel_sets_flag_and_preserves_rows(mqtt_instance, query_user, monkeypatch):
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)

    job_id = svc.create_mq_query_job(
        query_user, mqtt_instance.id, "default", "sub -t demo"
    )["job_id"]
    key = svc.job_cache_key(job_id)
    job = cache.get(key)
    job["status"] = "partial"
    job["rows"] = [["demo", "payload-1", 0, False]]
    job["column_list"] = ["topic", "payload", "qos", "retain"]
    cache.set(key, job, svc.JOB_CACHE_TTL)

    cancelled = svc.cancel_mq_query_job(query_user, job_id)
    assert cancelled["cancel"] is True
    assert cancelled["rows"] == [["demo", "payload-1", 0, False]]

    calls = {"cancel_checks": 0}

    def fake_run_subscribe(
        self,
        topic,
        qos,
        max_msgs,
        timeout_sec,
        cancel_check=None,
        on_message=None,
        **kwargs,
    ):
        row = ["demo", "payload-1", 0, False]
        if on_message:
            on_message(row)
        if cancel_check:
            calls["cancel_checks"] += 1
            assert cancel_check() is True
        result = ResultSet(
            full_sql=kwargs.get("full_sql", ""),
            column_list=["topic", "payload", "qos", "retain"],
        )
        result.rows = [row]
        result.affected_rows = 1
        return result

    monkeypatch.setattr("sql.engines.mqtt.MqttEngine.run_subscribe", fake_run_subscribe)
    svc.run_mq_query_job(job_id)
    final = cache.get(key)
    assert final["status"] == "cancelled"
    assert final["rows"] == [["demo", "payload-1", 0, False]]
    # Cancelled before the worker started: the engine is skipped entirely (no
    # broker connection / subscribe), so its cancel_check is never invoked.
    assert calls["cancel_checks"] == 0


@pytest.mark.django_db
def test_run_mq_query_job_marks_done(mqtt_instance, query_user, monkeypatch):
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)
    job_id = svc.create_mq_query_job(
        query_user, mqtt_instance.id, "default", "sub -t demo -C 2"
    )["job_id"]

    def fake_run_subscribe(
        self,
        topic,
        qos,
        max_msgs,
        timeout_sec,
        cancel_check=None,
        on_message=None,
        **kwargs,
    ):
        assert topic == "demo"
        assert max_msgs == 2
        assert timeout_sec == 60
        rows = [
            ["demo", "a", 0, False],
            ["demo", "b", 0, False],
        ]
        for row in rows:
            if on_message:
                on_message(row)
        result = ResultSet(
            full_sql=kwargs.get("full_sql", ""),
            column_list=["topic", "payload", "qos", "retain"],
        )
        result.rows = rows
        result.affected_rows = 2
        return result

    monkeypatch.setattr("sql.engines.mqtt.MqttEngine.run_subscribe", fake_run_subscribe)
    svc.run_mq_query_job(job_id)
    job = svc.get_mq_query_job(query_user, job_id)
    assert job["status"] == "done"
    assert len(job["rows"]) == 2
    assert job["column_list"] == ["topic", "payload", "qos", "retain"]


@pytest.mark.django_db
def test_get_rejects_other_user(
    mqtt_instance, query_user, django_user_model, monkeypatch
):
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)
    job_id = svc.create_mq_query_job(
        query_user, mqtt_instance.id, "default", "sub -t demo"
    )["job_id"]
    other = django_user_model.objects.create(username="other_user", is_active=True)
    with pytest.raises(PermissionError):
        svc.get_mq_query_job(other, job_id)
    with pytest.raises(PermissionError):
        svc.cancel_mq_query_job(other, job_id)


@pytest.mark.django_db
def test_cancel_key_survives_stale_job_overwrite(
    mqtt_instance, query_user, monkeypatch
):
    """Dedicated cancel key keeps cancel_check true even if job payload loses cancel."""
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)
    job_id = svc.create_mq_query_job(
        query_user, mqtt_instance.id, "default", "sub -t demo"
    )["job_id"]
    svc.cancel_mq_query_job(query_user, job_id)

    # Simulate a racing on_message that overwrote cancel=False onto the job dict.
    key = svc.job_cache_key(job_id)
    stale = cache.get(key)
    stale["cancel"] = False
    stale["status"] = "partial"
    stale["rows"] = [["demo", "x", 0, False]]
    cache.set(key, stale, svc.JOB_CACHE_TTL)

    assert cache.get(svc.cancel_cache_key(job_id)) is True
    assert svc._is_cancelled(job_id) is True


@pytest.mark.django_db
def test_run_mq_query_job_passes_ackmode_to_run_get(
    rabbitmq_instance, query_user, monkeypatch
):
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)
    job_id = svc.create_mq_query_job(
        query_user,
        rabbitmq_instance.id,
        "/",
        "get queue=demo.q count=1 ackmode=reject_requeue_true",
    )["job_id"]
    captured = {}

    def fake_run_get(self, queue, count, timeout_sec, **kwargs):
        captured["queue"] = queue
        captured["count"] = count
        captured["ackmode"] = kwargs.get("ackmode")
        result = ResultSet(
            full_sql=kwargs.get("full_sql", ""),
            column_list=["queue", "routing_key", "body"],
        )
        result.rows = [["demo.q", "rk", "hi"]]
        result.affected_rows = 1
        return result

    monkeypatch.setattr("sql.engines.rabbitmq.RabbitmqEngine.run_get", fake_run_get)
    svc.run_mq_query_job(job_id)
    assert captured["queue"] == "demo.q"
    assert captured["count"] == 1
    assert captured["ackmode"] == "reject_requeue_true"
    job = svc.get_mq_query_job(query_user, job_id)
    assert job["status"] == "done"


# --- Codex #3: mq_query_timeout_max is clamped to the 3600s hard cap ---


@pytest.mark.django_db
def test_timeout_max_clamped_to_hard_cap(
    mqtt_instance, query_user, monkeypatch, setup_sys_config
):
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)
    setup_sys_config.set("mq_query_timeout_default", "86400")
    setup_sys_config.set("mq_query_timeout_max", "86400")
    job_id = svc.create_mq_query_job(
        query_user, mqtt_instance.id, "default", "sub -t t"
    )["job_id"]
    assert cache.get(svc.job_cache_key(job_id))["timeout_sec"] == 3600


# --- Codex #5: worker clamps fetched count to the privilege limit ---


@pytest.mark.django_db
def test_priv_limit_clamps_worker_count(rabbitmq_instance, query_user, monkeypatch):
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)
    monkeypatch.setattr(
        "sql.services.mq_query_job.query_priv_check",
        lambda *a, **k: {"status": 0, "msg": "ok", "data": {"limit_num": 3}},
    )
    job_id = svc.create_mq_query_job(
        query_user, rabbitmq_instance.id, "/", "get queue=q count=10"
    )["job_id"]
    assert cache.get(svc.job_cache_key(job_id))["limit_num"] == 3

    captured = {}

    def fake_run_get(self, queue, count, timeout_sec, **kwargs):
        captured["count"] = count
        result = ResultSet(full_sql="", column_list=["queue", "routing_key", "body"])
        result.rows = []
        result.affected_rows = 0
        return result

    monkeypatch.setattr("sql.engines.rabbitmq.RabbitmqEngine.run_get", fake_run_get)
    svc.run_mq_query_job(job_id)
    assert captured["count"] == 3  # clamped from 10 to the privilege limit


@pytest.mark.django_db
def test_create_passes_requested_count_to_priv_check(
    rabbitmq_instance, query_user, monkeypatch
):
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)
    captured = {}

    def fake_priv_check(user, instance, db_name, sql, limit_num):
        captured["limit_num_arg"] = limit_num
        return {"status": 0, "msg": "ok", "data": {"limit_num": 0}}

    monkeypatch.setattr("sql.services.mq_query_job.query_priv_check", fake_priv_check)
    svc.create_mq_query_job(
        query_user, rabbitmq_instance.id, "/", "get queue=q count=7"
    )
    assert captured["limit_num_arg"] == 7


# --- Codex #8: engine error must not wipe incremental cached rows ---


@pytest.mark.django_db
def test_failed_engine_preserves_cached_partial_rows(
    rabbitmq_instance, query_user, monkeypatch
):
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)
    job_id = svc.create_mq_query_job(
        query_user,
        rabbitmq_instance.id,
        "/",
        "get queue=q count=3 ackmode=ack_requeue_true",
    )["job_id"]
    key = svc.job_cache_key(job_id)

    def fake_run_get(
        self,
        queue,
        count,
        timeout_sec,
        cancel_check=None,
        on_message=None,
        **kwargs,
    ):
        if on_message:
            on_message(["q", "rk", "partial-body"])
        result = ResultSet(full_sql="", column_list=["queue", "routing_key", "body"])
        result.error = "channel closed"
        # result.rows stays the default [] (engine never assigned final rows)
        return result

    monkeypatch.setattr("sql.engines.rabbitmq.RabbitmqEngine.run_get", fake_run_get)
    svc.run_mq_query_job(job_id)
    final = cache.get(key)
    assert final["status"] == "failed"
    assert final["rows"] == [["q", "rk", "partial-body"]]


# --- Codex #12: privilege check uses the engine's effective db/vhost ---


@pytest.mark.django_db
def test_db_name_normalized_before_priv_check(
    rabbitmq_instance, mqtt_instance, query_user, monkeypatch
):
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)
    captured = {}

    def fake_priv_check(user, instance, db_name, sql, limit_num):
        captured["db_name"] = db_name
        return {"status": 0, "msg": "ok", "data": {"limit_num": 0}}

    monkeypatch.setattr("sql.services.mq_query_job.query_priv_check", fake_priv_check)

    # rabbitmq: omitted db_name -> "/" (engine default vhost)
    svc.create_mq_query_job(query_user, rabbitmq_instance.id, "", "get queue=q")
    assert captured["db_name"] == "/"

    # mqtt: omitted db_name -> "default"
    svc.create_mq_query_job(query_user, mqtt_instance.id, "", "sub -t t")
    assert captured["db_name"] == "default"


# --- Codex #4: completed async MQ reads are written to QueryLog ---


@pytest.mark.django_db
def test_async_job_writes_query_log(mqtt_instance, query_user, monkeypatch):
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)
    job_id = svc.create_mq_query_job(
        query_user, mqtt_instance.id, "default", "sub -t demo -C 1"
    )["job_id"]

    def fake_run_subscribe(
        self,
        topic,
        qos,
        max_msgs,
        timeout_sec,
        cancel_check=None,
        on_message=None,
        **kwargs,
    ):
        if on_message:
            on_message(["demo", "hi", 0, False])
        result = ResultSet(
            full_sql="", column_list=["topic", "payload", "qos", "retain"]
        )
        result.rows = [["demo", "hi", 0, False]]
        result.affected_rows = 1
        return result

    monkeypatch.setattr("sql.engines.mqtt.MqttEngine.run_subscribe", fake_run_subscribe)
    before = QueryLog.objects.count()
    svc.run_mq_query_job(job_id)
    assert QueryLog.objects.count() == before + 1
    log = QueryLog.objects.latest("id")
    assert log.sqllog == "sub -t demo -C 1"
    assert log.instance_name == "mqtt_ins"
    assert log.effect_row == 1
    assert log.username == query_user.username


# --- Codex review: cancellation requested before the worker starts is honored ---


@pytest.mark.django_db
def test_pre_start_cancellation_skips_engine(mqtt_instance, query_user, monkeypatch):
    """A job cancelled before the worker picks it up must finalize as cancelled
    without opening a broker connection / subscribing."""
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)
    job_id = svc.create_mq_query_job(
        query_user, mqtt_instance.id, "default", "sub -t demo"
    )["job_id"]

    # User cancels before the worker runs.
    svc.cancel_mq_query_job(query_user, job_id)

    called = {"run_subscribe": False}

    def fake_run_subscribe(self, *args, **kwargs):
        called["run_subscribe"] = True
        result = ResultSet(
            full_sql="", column_list=["topic", "payload", "qos", "retain"]
        )
        result.rows = [["demo", "x", 0, False]]
        return result

    monkeypatch.setattr("sql.engines.mqtt.MqttEngine.run_subscribe", fake_run_subscribe)
    svc.run_mq_query_job(job_id)

    assert called["run_subscribe"] is False
    assert cache.get(svc.job_cache_key(job_id))["status"] == "cancelled"


# --- Codex review: passwords written into a command must not reach QueryLog ---


@pytest.mark.django_db
def test_query_log_redacts_mqtt_password(mqtt_instance, query_user, monkeypatch):
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)
    job_id = svc.create_mq_query_job(
        query_user, mqtt_instance.id, "default", "mqttx -P hunter2 sub -t demo -C 1"
    )["job_id"]

    def fake_run_subscribe(
        self,
        topic,
        qos,
        max_msgs,
        timeout_sec,
        cancel_check=None,
        on_message=None,
        **kwargs,
    ):
        result = ResultSet(
            full_sql="", column_list=["topic", "payload", "qos", "retain"]
        )
        result.rows = [["demo", "hi", 0, False]]
        result.affected_rows = 1
        return result

    monkeypatch.setattr("sql.engines.mqtt.MqttEngine.run_subscribe", fake_run_subscribe)
    svc.run_mq_query_job(job_id)

    log = QueryLog.objects.latest("id")
    assert "hunter2" not in log.sqllog
    assert "***" in log.sqllog


# --- Codex review: read-only query jobs must not use destructive ackmodes ---


@pytest.mark.django_db
def test_create_rejects_destructive_ackmode(rabbitmq_instance, query_user, monkeypatch):
    monkeypatch.setattr(svc, "_enqueue_mq_query_job", lambda *a, **k: None)
    for ackmode in ("ack_requeue_false", "reject_requeue_false"):
        with pytest.raises(ValueError, match="回队模式"):
            svc.create_mq_query_job(
                query_user,
                rabbitmq_instance.id,
                "/",
                f"get queue=q ackmode={ackmode}",
            )
    # requeue modes are still allowed on the query path
    job_id = svc.create_mq_query_job(
        query_user, rabbitmq_instance.id, "/", "get queue=q ackmode=ack_requeue_true"
    )["job_id"]
    assert job_id
