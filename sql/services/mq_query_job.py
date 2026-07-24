# -*- coding: UTF-8 -*-
"""Cancelable async MQ query jobs backed by Django cache + django-q."""

from __future__ import annotations

import logging
import threading
import time
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django_q.tasks import async_task

from common.config import SysConfig
from sql.engines import get_engine
from sql.engines.mq_cli import parse_mqtt_line, parse_rabbitmq_line
from sql.engines.mqtt import MAX_SUBSCRIBE_COUNT, MqttEngine
from sql.engines.rabbitmq import MAX_GET_COUNT, RabbitmqEngine
from sql.models import Instance, QueryLog
from sql.query_privileges import query_priv_check
from sql.utils.resource_group import user_instances

logger = logging.getLogger("default")

CACHE_KEY_PREFIX = "mq_query_job:"
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_TIMEOUT_MAX_SEC = 3600
JOB_CACHE_TTL = DEFAULT_TIMEOUT_MAX_SEC + 600

MQTT_COLUMN_LIST = ["topic", "payload", "qos", "retain"]
RABBITMQ_COLUMN_LIST = ["queue", "routing_key", "body"]


def job_cache_key(job_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}{job_id}"


def cancel_cache_key(job_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}{job_id}:cancel"


def _enqueue_mq_query_job(job_id: str, timeout_sec: int | None = None) -> None:
    """Enqueue job without blocking the create HTTP request.

    When Q_CLUSTER sync=True, django-q runs async_task inline in the caller.
    That would hold POST /mq-jobs/ until sub/get finishes (often the full
    timeout), so the browser cannot poll partial rows. Use a daemon thread
    instead; locmem cache is process-local and shared with poll handlers.

    Non-sync: pass per-task django-q timeout = wait + 60 so long MQ waits
    are not killed by the cluster default (settings.Q_CLUSTER timeout stays 60).
    """
    sync = bool(settings.Q_CLUSTER.get("sync"))
    if sync:
        thread = threading.Thread(
            target=run_mq_query_job,
            args=(job_id,),
            name=f"mq-query-job-{job_id[:8]}",
            daemon=True,
        )
        thread.start()
        return
    wait = int(timeout_sec or DEFAULT_TIMEOUT_SEC)
    async_task(
        "sql.services.mq_query_job.run_mq_query_job",
        job_id,
        timeout=wait + 60,
    )


def _resolve_timeout_sec() -> tuple[int, int]:
    """Return (timeout_sec, cache_ttl) from SysConfig, clamped to [1, hard cap].

    The UI help tabs advertise ``mq_query_timeout_max`` as a 3600-second hard
    cap and the synchronous engine path clamps to MAX_QUERY_TIMEOUT_SEC=3600,
    so bound the configured max by DEFAULT_TIMEOUT_MAX_SEC here too; a mis-set
    value (e.g. 86400) must not let async jobs occupy workers for a day
    (Codex #3).
    """
    config = SysConfig()
    try:
        default = int(config.get("mq_query_timeout_default", DEFAULT_TIMEOUT_SEC))
    except (TypeError, ValueError):
        default = DEFAULT_TIMEOUT_SEC
    try:
        max_sec = int(config.get("mq_query_timeout_max", DEFAULT_TIMEOUT_MAX_SEC))
    except (TypeError, ValueError):
        max_sec = DEFAULT_TIMEOUT_MAX_SEC
    max_sec = max(1, min(max_sec, DEFAULT_TIMEOUT_MAX_SEC))
    timeout_sec = max(1, min(default, max_sec))
    ttl = max(max_sec + 600, JOB_CACHE_TTL)
    return timeout_sec, ttl


def _get_readable_instance(user, instance_id: int) -> Instance:
    return user_instances(user, tag_codes=["can_read"]).get(id=instance_id)


def _assert_job_owner(user, job: dict) -> None:
    if user.is_superuser:
        return
    if job.get("user_id") != user.id:
        raise PermissionError("无权访问该查询任务")


def _load_job(job_id: str) -> dict:
    job = cache.get(job_cache_key(job_id))
    if not job:
        raise KeyError(f"job not found: {job_id}")
    return job


def _save_job(job: dict, ttl: int | None = None) -> dict:
    if ttl is None:
        _, ttl = _resolve_timeout_sec()
    cache.set(job_cache_key(job["job_id"]), job, ttl)
    return job


def _update_job(job_id: str, mutator, ttl: int | None = None) -> dict:
    """Re-get job from cache, apply mutator in place, then set.

    Reduces lost-update races between cancel and on_message by always
    merging against the latest cached payload before write.
    """
    if ttl is None:
        _, ttl = _resolve_timeout_sec()
    key = job_cache_key(job_id)
    current = cache.get(key)
    if not current:
        raise KeyError(f"job not found: {job_id}")
    mutator(current)
    cache.set(key, current, ttl)
    return current


def _is_cancelled(job_id: str, job: dict | None = None) -> bool:
    if cache.get(cancel_cache_key(job_id)):
        return True
    if job is not None and job.get("cancel"):
        return True
    current = cache.get(job_cache_key(job_id))
    return bool(current and current.get("cancel"))


def create_mq_query_job(user, instance_id, db_name, sql_line) -> dict:
    instance = _get_readable_instance(user, instance_id)
    if instance.db_type not in ("mqtt", "rabbitmq"):
        raise ValueError("仅 MQTT/RabbitMQ 支持异步查询任务")

    line = (sql_line or "").strip()
    if not line:
        raise ValueError("sql_line 不能为空")

    if instance.db_type == "mqtt":
        cmd = parse_mqtt_line(line)
        if cmd.action != "sub":
            raise ValueError("仅 sub 支持异步任务")
        MqttEngine._validate_query_command(cmd)
        requested_count = int(cmd.args.get("count", 10))
        # Mirror MqttEngine.get_all_databases so the privilege check runs
        # against the same database name the engine will use (Codex #12).
        effective_db = db_name or instance.db_name or "default"
    else:
        cmd = parse_rabbitmq_line(line)
        if cmd.action != "get":
            raise ValueError("仅 get 支持异步任务")
        RabbitmqEngine._validate_query_command(cmd)
        requested_count = int(cmd.args.get("count", 1))
        # Mirror RabbitmqEngine._vhost so the privilege check and the engine
        # agree on the vhost instead of checking "" but running on "/" (Codex #12).
        effective_db = db_name or instance.db_name or "/"

    # Pass the requested count so query_priv_check returns the caller's
    # effective row limit; the worker enforces it (Codex #5).
    priv = query_priv_check(user, instance, effective_db, line, requested_count)
    if priv.get("status") != 0:
        raise PermissionError(priv.get("msg") or "无查询权限")
    limit_num = int(priv.get("data", {}).get("limit_num") or 0)

    timeout_sec, ttl = _resolve_timeout_sec()
    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id,
        "user_id": user.id,
        "instance_id": instance.id,
        "db_name": effective_db,
        "sql_line": line,
        "status": "pending",
        "column_list": [],
        "rows": [],
        "warning": "",
        "error": "",
        "cancel": False,
        "timeout_sec": timeout_sec,
        "limit_num": limit_num,
    }
    _save_job(job, ttl)
    _enqueue_mq_query_job(job_id, timeout_sec=timeout_sec)
    return {"job_id": job_id}


def get_mq_query_job(user, job_id: str) -> dict:
    job = _load_job(job_id)
    _assert_job_owner(user, job)
    return job


def cancel_mq_query_job(user, job_id: str) -> dict:
    job = _load_job(job_id)
    _assert_job_owner(user, job)
    _, ttl = _resolve_timeout_sec()
    # Dedicated cancel key so cancel_check survives job payload RMW races.
    cache.set(cancel_cache_key(job_id), True, ttl)

    def mark_cancel(current):
        current["cancel"] = True

    return _update_job(job_id, mark_cancel, ttl)


def _write_query_log(job, instance_name, effect_row, cost_time) -> None:
    """Mirror the sync path's QueryLog for async MQ reads (Codex #4).

    Without this, sub/get executed through the mq-jobs endpoint never reach
    execute_sql_query, so they are absent from query history/audit. Logging
    must never break the job itself.
    """
    try:
        user = get_user_model().objects.filter(pk=job.get("user_id")).first()
        QueryLog.objects.create(
            username=user.username if user else str(job.get("user_id")),
            user_display=(getattr(user, "display", "") or "") if user else "",
            db_name=job.get("db_name") or "",
            instance_name=instance_name,
            sqllog=job.get("sql_line") or "",
            effect_row=effect_row,
            cost_time=str(cost_time),
            priv_check=True,
            hit_rule=False,
            masking=False,
        )
    except Exception as exc:
        logger.warning("MQ 查询日志写入失败：%s", exc)


def run_mq_query_job(job_id: str) -> None:
    key = job_cache_key(job_id)
    job = cache.get(key)
    if not job:
        logger.warning("mq query job missing: %s", job_id)
        return

    _, ttl = _resolve_timeout_sec()
    # Honor cancellation requested before the worker started (user hit Stop or
    # left the page between create and enqueue pickup). Without this, the worker
    # would still open a broker connection / subscribe and could append rows to
    # a job the user already cancelled (Codex review).
    if _is_cancelled(job_id, job):

        def mark_cancelled(current):
            current["cancel"] = True
            current["status"] = "cancelled"

        _update_job(job_id, mark_cancelled, ttl)
        return

    job["status"] = "running"
    _save_job(job, ttl)

    instance_name = ""
    query_started = time.monotonic()
    try:
        instance = Instance.objects.get(pk=job["instance_id"])
        instance_name = instance.instance_name
        engine = get_engine(instance)
        line = job["sql_line"]
        timeout_sec = int(job.get("timeout_sec") or DEFAULT_TIMEOUT_SEC)
        limit_num = int(job.get("limit_num") or 0)

        def cancel_check():
            return _is_cancelled(job_id)

        def on_message(row):
            def append_row(current):
                if not current.get("column_list"):
                    current["column_list"] = list(column_list)
                current["rows"].append(row)
                current["status"] = "partial"

            try:
                _update_job(job_id, append_row, ttl)
            except KeyError:
                return

        if instance.db_type == "mqtt":
            cmd = parse_mqtt_line(line)
            max_msgs = min(int(cmd.args.get("count", 10)), MAX_SUBSCRIBE_COUNT)
            # Enforce the caller's query-privilege row limit (Codex #5).
            if limit_num > 0:
                max_msgs = min(max_msgs, limit_num)
            column_list = MQTT_COLUMN_LIST
            result = engine.run_subscribe(
                topic=cmd.args["topic"],
                qos=cmd.args.get("qos", 0),
                max_msgs=max_msgs,
                timeout_sec=timeout_sec,
                cancel_check=cancel_check,
                on_message=on_message,
                db_name=job.get("db_name") or None,
                full_sql=cmd.raw_line,
            )
        elif instance.db_type == "rabbitmq":
            cmd = parse_rabbitmq_line(line)
            count = min(int(cmd.args.get("count", 1)), MAX_GET_COUNT)
            # Clamp the fetched (and, with ack_requeue_false, removed) message
            # count to the caller's query-privilege limit (Codex #5).
            if limit_num > 0:
                count = min(count, limit_num)
            column_list = RABBITMQ_COLUMN_LIST
            result = engine.run_get(
                queue=cmd.args["queue"],
                count=count,
                timeout_sec=timeout_sec,
                cancel_check=cancel_check,
                on_message=on_message,
                db_name=job.get("db_name") or None,
                full_sql=cmd.raw_line,
                ackmode=cmd.args.get("ackmode", "ack_requeue_true"),
            )
        else:
            raise ValueError("仅 MQTT/RabbitMQ 支持异步查询任务")

        def finalize(current):
            current["column_list"] = list(result.column_list or [])
            # Prefer engine rows as authoritative. On an engine error the
            # ResultSet keeps its default empty list, so fall back to the
            # incremental cached rows instead of wiping partial rows that
            # on_message already stored (with ack_requeue_false those rows may
            # already have been removed from the queue) (Codex #8).
            current["rows"] = list(result.rows or current.get("rows") or [])
            current["warning"] = result.warning or ""
            current["error"] = result.error or ""
            if _is_cancelled(job_id, current):
                current["cancel"] = True
                current["status"] = "cancelled"
            elif result.error:
                current["status"] = "failed"
            else:
                current["status"] = "done"

        _update_job(job_id, finalize, ttl)
        _write_query_log(
            job,
            instance_name,
            effect_row=len(result.rows or []),
            cost_time=round(time.monotonic() - query_started, 3),
        )
    except Exception as exc:
        logger.warning("mq query job failed: %s %s", job_id, exc)

        def mark_failed(current):
            current["error"] = str(exc)
            if _is_cancelled(job_id, current):
                current["cancel"] = True
                current["status"] = "cancelled"
            else:
                current["status"] = "failed"

        try:
            _update_job(job_id, mark_failed, ttl)
        except KeyError:
            pass
        _write_query_log(
            job,
            instance_name,
            effect_row=0,
            cost_time=round(time.monotonic() - query_started, 3),
        )
