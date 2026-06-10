# -*- coding: UTF-8 -*-
import json
from unittest.mock import MagicMock, mock_open, patch

import pytest
from django.core.cache import cache
from django.test import Client, RequestFactory

from sql import instance as instance_views
from sql.engines.models import ResultSet
from sql.models import Instance, InstanceTag, ParamHistory, ParamTemplate


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client_with_super_user(super_user):
    client = Client()
    client.force_login(super_user)
    return client


@pytest.fixture
def master_instance(db):
    ins = Instance.objects.create(
        instance_name="test_master",
        type="master",
        db_type="mysql",
        host="127.0.0.1",
        port=3306,
        user="ins_user",
        password="some_str",
        show_db_name_regex="^app_",
        denied_db_name_regex="^app_secret$",
    )
    yield ins
    ins.delete()


@pytest.fixture
def second_instance(db):
    ins = Instance.objects.create(
        instance_name="test_second",
        type="master",
        db_type="mysql",
        host="127.0.0.2",
        port=3306,
        user="ins_user",
        password="some_str",
    )
    yield ins
    ins.delete()


def response_json(response):
    return json.loads(response.content)


def make_engine(**methods):
    engine = MagicMock()
    engine.escape_string.side_effect = lambda value: value
    for name, value in methods.items():
        getattr(engine, name).return_value = value
    return engine


def result_set_error(message):
    result = ResultSet()
    result.error = message
    return result


@pytest.mark.django_db
class TestInstanceList:
    def test_lists_filters_sorts_and_returns_page(self, client_with_super_user):
        Instance.objects.create(
            instance_name="beta",
            type="slave",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="u1",
            password="p1",
        )
        Instance.objects.create(
            instance_name="alpha",
            type="master",
            db_type="mysql",
            host="127.0.0.2",
            port=3307,
            user="u2",
            password="p2",
        )
        Instance.objects.create(
            instance_name="pg-alpha",
            type="master",
            db_type="pgsql",
            host="127.0.0.3",
            port=5432,
            user="u3",
            password="p3",
        )

        response = client_with_super_user.post(
            "/instance/list/",
            data={
                "limit": 10,
                "offset": 0,
                "type": "master",
                "db_type": "mysql",
                "search": "alp",
                "sortName": "instance_name",
                "sortOrder": "asc",
            },
        )

        result = response_json(response)
        assert result["total"] == 1
        assert result["rows"] == [
            {
                "id": result["rows"][0]["id"],
                "instance_name": "alpha",
                "db_type": "mysql",
                "type": "master",
                "host": "127.0.0.2",
                "port": 3307,
                "user": "u2",
            }
        ]

    def test_lists_filters_by_all_active_tags(self, client_with_super_user):
        active = InstanceTag.objects.create(tag_code="active", tag_name="active")
        inactive = InstanceTag.objects.create(
            tag_code="inactive", tag_name="inactive", active=False
        )
        matched = Instance.objects.create(
            instance_name="tagged",
            type="master",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="u1",
            password="p1",
        )
        unmatched = Instance.objects.create(
            instance_name="inactive_tagged",
            type="master",
            db_type="mysql",
            host="127.0.0.2",
            port=3306,
            user="u2",
            password="p2",
        )
        matched.instance_tag.add(active)
        unmatched.instance_tag.add(inactive)

        response = client_with_super_user.post(
            "/instance/list/",
            data={
                "limit": 10,
                "offset": 0,
                "tags[]": [active.id],
                "sortName": "id",
                "sortOrder": "asc",
            },
        )

        result = response_json(response)
        assert result["total"] == 1
        assert result["rows"][0]["instance_name"] == "tagged"


@pytest.mark.django_db
class TestParamList:
    def test_param_list_rejects_invalid_instance_id(self, client_with_super_user):
        response = client_with_super_user.post(
            "/param/list/", data={"instance_id": "x"}
        )

        assert response_json(response) == {
            "status": 1,
            "msg": "实例ID不合法",
            "data": [],
        }

    def test_param_list_instance_not_exist(self, client_with_super_user):
        response = client_with_super_user.post("/param/list/", data={"instance_id": 0})

        assert response_json(response) == {
            "status": 1,
            "msg": "实例不存在",
            "data": [],
        }

    @patch("sql.instance.get_engine")
    def test_param_list_merges_template_and_filters_editable(
        self, mock_get_engine, client_with_super_user, master_instance
    ):
        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="binlog_format",
            default_value="ROW",
            valid_values="ROW|STATEMENT",
            description="binlog mode",
            editable=True,
        )
        mock_get_engine.return_value.get_variables.return_value = ResultSet(
            rows=(("BINLOG_FORMAT", "STATEMENT"), ("max_connections", "151"))
        )

        response = client_with_super_user.post(
            "/param/list/",
            data={"instance_id": master_instance.id, "editable": "true"},
        )

        assert response_json(response) == [
            {
                "variable_name": "binlog_format",
                "runtime_value": "STATEMENT",
                "editable": True,
                "id": ParamTemplate.objects.get(variable_name="binlog_format").id,
                "default_value": "ROW",
                "valid_values": "ROW|STATEMENT",
                "description": "binlog mode",
            }
        ]

    @patch("sql.instance.get_engine")
    def test_param_list_returns_non_editable_when_editable_flag_absent(
        self, mock_get_engine, client_with_super_user, master_instance
    ):
        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="binlog_format",
            default_value="ROW",
            editable=True,
        )
        mock_get_engine.return_value.get_variables.return_value = ResultSet(
            rows=(("BINLOG_FORMAT", "ROW"), ("max_connections", "151"))
        )

        response = client_with_super_user.post(
            "/param/list/",
            data={"instance_id": master_instance.id},
        )

        assert response_json(response) == [
            {
                "variable_name": "max_connections",
                "runtime_value": "151",
                "editable": False,
            }
        ]


@pytest.mark.django_db
class TestParamHistory:
    def test_param_history_paginates_and_filters_by_search(
        self, client_with_super_user, master_instance, second_instance, super_user
    ):
        ParamHistory.objects.create(
            instance=master_instance,
            variable_name="binlog_format",
            old_var="ROW",
            new_var="STATEMENT",
            set_sql="set global binlog_format='STATEMENT'",
            user_name=super_user.username,
            user_display=super_user.display,
        )
        ParamHistory.objects.create(
            instance=second_instance,
            variable_name="binlog_cache_size",
            old_var="1",
            new_var="2",
            set_sql="set global binlog_cache_size=2",
            user_name=super_user.username,
            user_display=super_user.display,
        )

        response = client_with_super_user.post(
            "/param/history/",
            data={
                "instance_id": master_instance.id,
                "search": "binlog_format",
                "limit": 10,
                "offset": 0,
            },
        )

        result = response_json(response)
        assert result["total"] == 1
        assert result["rows"][0]["variable_name"] == "binlog_format"


@pytest.mark.django_db
class TestParamEdit:
    def test_param_edit_rejects_invalid_instance_id(self, client_with_super_user):
        response = client_with_super_user.post(
            "/param/edit/",
            data={"instance_id": "x", "variable_name": "a", "runtime_value": "1"},
        )

        assert response_json(response) == {
            "status": 1,
            "msg": "实例ID不合法",
            "data": [],
        }

    def test_param_edit_instance_not_exist(self, client_with_super_user):
        response = client_with_super_user.post(
            "/param/edit/",
            data={"instance_id": 0, "variable_name": "a", "runtime_value": "1"},
        )

        assert response_json(response) == {
            "status": 1,
            "msg": "实例不存在",
            "data": [],
        }

    @patch("sql.instance.get_engine")
    def test_param_edit_template_missing(
        self, mock_get_engine, client_with_super_user, master_instance
    ):
        mock_get_engine.return_value.escape_string.side_effect = lambda value: value

        response = client_with_super_user.post(
            "/param/edit/",
            data={
                "instance_id": master_instance.id,
                "variable_name": "binlog_format",
                "runtime_value": "ROW",
            },
        )

        assert response_json(response) == {
            "status": 1,
            "msg": "请先在参数模板中配置该参数！",
            "data": [],
        }

    @patch("sql.instance.get_engine")
    def test_param_edit_value_not_changed(
        self, mock_get_engine, client_with_super_user, master_instance
    ):
        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="binlog_format",
            default_value="ROW",
            editable=True,
        )
        engine = make_engine()
        engine.get_variables.return_value = ResultSet(rows=(("binlog_format", "ROW"),))
        mock_get_engine.return_value = engine

        response = client_with_super_user.post(
            "/param/edit/",
            data={
                "instance_id": master_instance.id,
                "variable_name": "binlog_format",
                "runtime_value": "ROW",
            },
        )

        assert response_json(response) == {
            "status": 1,
            "msg": "参数值与实际运行值一致，未调整！",
            "data": [],
        }

    @patch("sql.instance.get_engine")
    def test_param_edit_set_error(
        self, mock_get_engine, client_with_super_user, master_instance
    ):
        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="binlog_format",
            default_value="ROW",
            editable=True,
        )
        engine = make_engine()
        engine.get_variables.return_value = ResultSet(rows=(("binlog_format", "ROW"),))
        engine.set_variable.return_value = result_set_error("修改报错")
        mock_get_engine.return_value = engine

        response = client_with_super_user.post(
            "/param/edit/",
            data={
                "instance_id": master_instance.id,
                "variable_name": "binlog_format",
                "runtime_value": "STATEMENT",
            },
        )

        assert response_json(response) == {
            "status": 1,
            "msg": "设置错误，错误信息：修改报错",
            "data": [],
        }
        assert ParamHistory.objects.count() == 0

    @patch("sql.instance.get_engine")
    def test_param_edit_success_creates_history(
        self, mock_get_engine, client_with_super_user, master_instance, super_user
    ):
        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="binlog_format",
            default_value="ROW",
            editable=True,
        )
        engine = make_engine()
        engine.get_variables.return_value = ResultSet(rows=(("binlog_format", "ROW"),))
        engine.set_variable.return_value = ResultSet(
            full_sql="set global binlog_format='STATEMENT'"
        )
        mock_get_engine.return_value = engine

        response = client_with_super_user.post(
            "/param/edit/",
            data={
                "instance_id": master_instance.id,
                "variable_name": "binlog_format",
                "runtime_value": "STATEMENT",
            },
        )

        assert response_json(response) == {
            "status": 0,
            "msg": "修改成功，请手动持久化到配置文件！",
            "data": [],
        }
        history = ParamHistory.objects.get()
        assert history.instance == master_instance
        assert history.variable_name == "binlog_format"
        assert history.old_var == "ROW"
        assert history.new_var == "STATEMENT"
        assert history.user_name == super_user.username


@pytest.mark.django_db
class TestParamCompare:
    def test_param_compare_rejects_invalid_ids(
        self, client_with_super_user, master_instance
    ):
        response = client_with_super_user.post(
            "/param/compare/",
            data={"instance_id1": "x", "instance_id2": master_instance.id},
        )

        assert response_json(response) == {
            "status": 1,
            "msg": "源实例ID不合法",
            "data": [],
        }

    def test_param_compare_source_not_exist(
        self, client_with_super_user, second_instance
    ):
        response = client_with_super_user.post(
            "/param/compare/",
            data={"instance_id1": 0, "instance_id2": second_instance.id},
        )

        assert response_json(response) == {
            "status": 1,
            "msg": "源实例不存在",
            "data": [],
        }

    def test_param_compare_target_not_exist(
        self, client_with_super_user, master_instance
    ):
        response = client_with_super_user.post(
            "/param/compare/",
            data={"instance_id1": master_instance.id, "instance_id2": 0},
        )

        assert response_json(response) == {
            "status": 1,
            "msg": "目标实例不存在",
            "data": [],
        }

    def test_param_compare_db_type_not_match(
        self, client_with_super_user, master_instance
    ):
        pg_instance = Instance.objects.create(
            instance_name="pg_instance",
            type="master",
            db_type="pgsql",
            host="127.0.0.3",
            port=5432,
            user="ins_user",
            password="some_str",
        )

        response = client_with_super_user.post(
            "/param/compare/",
            data={"instance_id1": master_instance.id, "instance_id2": pg_instance.id},
        )

        assert response_json(response) == {
            "status": 1,
            "msg": "两个实例的数据库类型不一致，无法对比",
            "data": [],
        }

    def test_param_compare_unsupported_db_type(self, client_with_super_user):
        ins1 = Instance.objects.create(
            instance_name="redis1",
            type="master",
            db_type="redis",
            host="127.0.0.1",
            port=6379,
            user="",
            password="",
        )
        ins2 = Instance.objects.create(
            instance_name="redis2",
            type="master",
            db_type="redis",
            host="127.0.0.2",
            port=6379,
            user="",
            password="",
        )

        response = client_with_super_user.post(
            "/param/compare/",
            data={"instance_id1": ins1.id, "instance_id2": ins2.id},
        )

        assert response_json(response) == {
            "status": 1,
            "msg": "redis 引擎不支持参数对比功能",
            "data": [],
        }

    @patch("sql.instance.get_engine")
    def test_param_compare_source_engine_exception(
        self, mock_get_engine, client_with_super_user, master_instance, second_instance
    ):
        mock_get_engine.side_effect = RuntimeError("connect failed")

        response = client_with_super_user.post(
            "/param/compare/",
            data={
                "instance_id1": master_instance.id,
                "instance_id2": second_instance.id,
            },
        )

        assert response_json(response) == {
            "status": 1,
            "msg": "获取源实例参数失败，请联系管理员",
            "data": [],
        }

    @patch("sql.instance.get_engine")
    def test_param_compare_target_result_error(
        self, mock_get_engine, client_with_super_user, master_instance, second_instance
    ):
        source_engine = make_engine()
        source_engine.get_variables.return_value = ResultSet(rows=(("a", "1"),))
        target_engine = make_engine()
        target_engine.get_variables.return_value = result_set_error("target error")
        mock_get_engine.side_effect = [source_engine, target_engine]

        response = client_with_super_user.post(
            "/param/compare/",
            data={
                "instance_id1": master_instance.id,
                "instance_id2": second_instance.id,
            },
        )

        assert response_json(response) == {
            "status": 1,
            "msg": "获取目标实例参数失败，请联系管理员",
            "data": [],
        }

    @patch("sql.instance.get_engine")
    def test_param_compare_diff_only_with_template_description(
        self, mock_get_engine, client_with_super_user, master_instance, second_instance
    ):
        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="binlog_format",
            default_value="ROW",
            description="binlog mode",
            editable=True,
        )
        source_engine = make_engine()
        source_engine.get_variables.return_value = ResultSet(
            rows=(("binlog_format", "ROW"), ("max_connections", "151"), ("a", "1"))
        )
        target_engine = make_engine()
        target_engine.get_variables.return_value = ResultSet(
            rows=(
                ("binlog_format", "STATEMENT"),
                ("max_connections", "151"),
                ("b", "2"),
            )
        )
        mock_get_engine.side_effect = [source_engine, target_engine]

        response = client_with_super_user.post(
            "/param/compare/",
            data={
                "instance_id1": master_instance.id,
                "instance_id2": second_instance.id,
                "diff_only": "true",
            },
        )

        result = response_json(response)
        assert result["status"] == 0
        assert result["data"]["total"] == 4
        assert result["data"]["same_count"] == 1
        assert result["data"]["diff_count"] == 3
        rows = result["data"]["rows"]
        assert [row["variable_name"] for row in rows] == ["a", "b", "binlog_format"]
        assert rows[0]["diff_type"] == "仅源实例存在"
        assert rows[1]["diff_type"] == "仅目标实例存在"
        assert rows[2]["diff_type"] == "值不同"
        assert rows[2]["description"] == "binlog mode"
        assert rows[2]["default_value"] == "ROW"

    @patch("sql.instance.get_engine")
    def test_param_compare_show_all(
        self, mock_get_engine, client_with_super_user, master_instance, second_instance
    ):
        source_engine = make_engine()
        source_engine.get_variables.return_value = ResultSet(rows=(("a", "1"),))
        target_engine = make_engine()
        target_engine.get_variables.return_value = ResultSet(rows=(("a", "1"),))
        mock_get_engine.side_effect = [source_engine, target_engine]

        response = client_with_super_user.post(
            "/param/compare/",
            data={
                "instance_id1": master_instance.id,
                "instance_id2": second_instance.id,
                "diff_only": "false",
            },
        )

        result = response_json(response)
        assert result["data"]["same_count"] == 1
        assert result["data"]["diff_count"] == 0
        assert result["data"]["rows"][0]["diff_type"] == "一致"


@pytest.mark.django_db
class TestSchemaSync:
    @patch("sql.instance.SchemaSync")
    def test_schemasync_returns_args_validation_error(
        self, mock_schema_sync, client_with_super_user, master_instance
    ):
        sync = mock_schema_sync.return_value
        sync.check_args.return_value = {"status": 1, "msg": "bad args", "data": []}

        response = client_with_super_user.post(
            "/instance/schemasync/",
            data={
                "instance_name": master_instance.instance_name,
                "db_name": "app",
                "target_instance_name": master_instance.instance_name,
                "target_db_name": "app",
            },
        )

        assert response_json(response) == {"status": 1, "msg": "bad args", "data": []}

    @patch("sql.instance.os.makedirs")
    @patch("sql.instance.SchemaSync")
    def test_schemasync_success_all_database_skips_result_files(
        self, mock_schema_sync, mock_makedirs, client_with_super_user, master_instance
    ):
        sync = mock_schema_sync.return_value
        sync.check_args.return_value = {"status": 0, "msg": "ok"}
        sync.generate_args2cmd.return_value = ["schemasync"]
        sync.execute_cmd.return_value.communicate.return_value = ("diff", "")

        response = client_with_super_user.post(
            "/instance/schemasync/",
            data={
                "instance_name": master_instance.instance_name,
                "db_name": "all",
                "target_instance_name": master_instance.instance_name,
                "target_db_name": "all",
                "sync_auto_inc": "true",
                "sync_comments": "false",
            },
        )

        assert response_json(response) == {
            "status": 0,
            "msg": "ok",
            "data": {"diff_stdout": "diff", "patch_stdout": "", "revert_stdout": ""},
        }
        sync.execute_cmd.assert_called_once_with(["schemasync"])

    @patch("builtins.open", new_callable=mock_open)
    @patch("sql.instance.os.makedirs")
    @patch("sql.instance.SchemaSync")
    def test_schemasync_command_exception_and_missing_result_files(
        self,
        mock_schema_sync,
        mock_makedirs,
        mock_file_open,
        client_with_super_user,
        master_instance,
    ):
        sync = mock_schema_sync.return_value
        sync.check_args.return_value = {"status": 0, "msg": "ok"}
        sync.generate_args2cmd.return_value = ["schemasync"]
        sync.execute_cmd.side_effect = RuntimeError("boom")
        mock_file_open.side_effect = FileNotFoundError("missing")

        response = client_with_super_user.post(
            "/instance/schemasync/",
            data={
                "instance_name": master_instance.instance_name,
                "db_name": "app",
                "target_instance_name": master_instance.instance_name,
                "target_db_name": "app",
            },
        )

        assert response_json(response) == {
            "status": 0,
            "msg": "ok",
            "data": {
                "diff_stdout": "执行对比命令失败，请联系管理员",
                "patch_stdout": "读取对比结果文件失败，请联系管理员",
                "revert_stdout": "读取对比结果文件失败，请联系管理员",
            },
        }
