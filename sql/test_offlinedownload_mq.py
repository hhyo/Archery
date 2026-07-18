# -*- coding: UTF-8 -*-
from types import SimpleNamespace

import pytest

from sql.models import Instance
from sql.offlinedownload import OffLineDownLoad, LINE_BASED_COMMAND_ENGINES


@pytest.mark.django_db
def test_pre_count_check_rejects_mqtt(monkeypatch):
    assert "mqtt" not in LINE_BASED_COMMAND_ENGINES
    assert "rabbitmq" not in LINE_BASED_COMMAND_ENGINES

    ins = Instance.objects.create(
        instance_name="mq_exp",
        type="slave",
        db_type="mqtt",
        host="127.0.0.1",
        port=1883,
        user="",
        password="",
    )
    called = {"query": False}

    class BoomEngine:
        def query_check(self, **kwargs):
            return {"bad_query": False, "filtered_sql": "sub -t t"}

        def query(self, **kwargs):
            called["query"] = True
            raise AssertionError("must not query")

        def filter_sql(self, sql, limit_num):
            return sql

    monkeypatch.setattr("sql.offlinedownload.get_engine", lambda instance: BoomEngine())
    wf = SimpleNamespace(
        sql_content="sub -t t",
        instance=ins,
        db_type="mqtt",
        db_name="",
        selected_db_name="",
    )
    result = OffLineDownLoad().pre_count_check(wf)
    assert result.error_count >= 1
    assert called["query"] is False
    assert any("离线导出" in (r.errormessage or "") for r in result.rows)


@pytest.mark.django_db
def test_pre_count_check_rejects_rabbitmq(monkeypatch):
    assert "rabbitmq" not in LINE_BASED_COMMAND_ENGINES

    ins = Instance.objects.create(
        instance_name="rmq_exp",
        type="slave",
        db_type="rabbitmq",
        host="127.0.0.1",
        port=5672,
        user="",
        password="",
    )
    called = {"query": False}

    class BoomEngine:
        def query_check(self, **kwargs):
            return {"bad_query": False, "filtered_sql": "basic.get -q q"}

        def query(self, **kwargs):
            called["query"] = True
            raise AssertionError("must not query")

        def filter_sql(self, sql, limit_num):
            return sql

    monkeypatch.setattr("sql.offlinedownload.get_engine", lambda instance: BoomEngine())
    wf = SimpleNamespace(
        sql_content="basic.get -q q",
        instance=ins,
        db_type="rabbitmq",
        db_name="",
        selected_db_name="",
    )
    result = OffLineDownLoad().pre_count_check(wf)
    assert result.error_count >= 1
    assert called["query"] is False
    assert any("离线导出" in (r.errormessage or "") for r in result.rows)


@pytest.mark.django_db
def test_execute_offline_download_rejects_mqtt(monkeypatch):
    ins = Instance.objects.create(
        instance_name="mq_exec",
        type="slave",
        db_type="mqtt",
        host="127.0.0.1",
        port=1883,
        user="",
        password="",
    )
    called = {"query": False}

    class BoomEngine:
        def query(self, **kwargs):
            called["query"] = True
            raise AssertionError("must not query")

    monkeypatch.setattr("sql.offlinedownload.get_engine", lambda instance: BoomEngine())
    content = SimpleNamespace(sql_content="sub -t t")
    wf = SimpleNamespace(
        sqlworkflowcontent=content,
        instance=ins,
        db_name="",
        export_format="csv",
        id=1,
    )
    result = OffLineDownLoad().execute_offline_download(wf)
    assert result.error_count >= 1 or any(
        getattr(r, "errlevel", 0) == 2 for r in result.rows
    )
    assert called["query"] is False
    assert any("离线导出" in (r.errormessage or "") for r in result.rows)
