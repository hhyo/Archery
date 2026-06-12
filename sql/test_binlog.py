# -*- coding: UTF-8 -*-
"""
binlog.py 单元测试
覆盖 binlog_list、del_binlog、my2sql、my2sql_file 四个函数
"""

import json
import os
from unittest.mock import patch, MagicMock, PropertyMock

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from sql.binlog import (
    binlog_list,
    del_binlog,
    my2sql,
    my2sql_file,
    parse_my2sql_output_line,
    read_my2sql_output_files,
)
from sql.engines.models import ResultSet
from sql.models import Instance

# ====================== Fixtures ======================


@pytest.fixture
def super_user(django_user_model):
    user = django_user_model.objects.create(
        username="super_user", display="超级用户", is_active=True, is_superuser=True
    )
    yield user
    user.delete()


@pytest.fixture
def normal_user(django_user_model, db):
    user = django_user_model.objects.create(
        username="normal_user", display="普通用户", is_active=True
    )
    # 添加 binlog 相关权限
    perms = Permission.objects.filter(codename__in=["menu_my2sql", "binlog_del"])
    user.user_permissions.set(perms)
    yield user
    user.delete()


@pytest.fixture
def db_instance(db):
    ins = Instance.objects.create(
        instance_name="test_instance",
        type="slave",
        db_type="mysql",
        host="127.0.0.1",
        port=3306,
        user="ins_user",
        password="some_str",
    )
    yield ins
    ins.delete()


@pytest.fixture
def client_with_normal_user(normal_user):
    client = Client()
    client.force_login(normal_user)
    return client


@pytest.fixture
def client_with_super_user(super_user):
    client = Client()
    client.force_login(super_user)
    return client


def _make_query_result(columns, rows, error=None):
    """辅助函数：构造 ResultSet 对象"""
    result = ResultSet()
    result.column_list = columns
    result.rows = rows
    result.error = error
    return result


# ====================== my2sql 输出解析测试 ======================


@pytest.mark.parametrize(
    "line,extra_info,expected_sql",
    [
        ("INSERT INTO t1 VALUES(1)\n", "", "INSERT INTO t1 VALUES(1);"),
        (
            "  delete from t1 where id=1;\r\n",
            "# at 123",
            "delete from t1 where id=1;",
        ),
        (
            "\tUpdate t1 set name='archery' where id=1",
            "# extra",
            "Update t1 set name='archery' where id=1;",
        ),
    ],
)
def test_parse_sql_line(line, extra_info, expected_sql):
    """SQL 行会补充分号并保留 extra_info"""
    row_info, current_extra_info = parse_my2sql_output_line(line, extra_info)

    assert row_info["sql"] == expected_sql
    assert current_extra_info == extra_info
    if extra_info:
        assert row_info["extra_info"] == extra_info
    else:
        assert "extra_info" not in row_info


def test_parse_comment_line_updates_extra_info():
    """注释行作为下一条 SQL 的 extra_info"""
    row_info, current_extra_info = parse_my2sql_output_line(
        "  # datetime=2024-01-01 00:00:00\n", ""
    )

    assert row_info is None
    assert current_extra_info == "# datetime=2024-01-01 00:00:00"


def test_parse_ignores_non_sql_line():
    """非 SQL 行会被忽略且不改变 extra_info"""
    row_info, current_extra_info = parse_my2sql_output_line("BEGIN\n", "# existing")

    assert row_info is None
    assert current_extra_info == "# existing"


def test_read_output_files_filters_and_limits_rows(tmp_path):
    """仅读取普通 .sql 文件，并按 num 限制返回行数"""
    first_file = tmp_path / "01.sql"
    first_file.write_text(
        "# datetime=2024-01-01 00:00:00\n"
        "INSERT INTO t1 VALUES(1)\n"
        "BEGIN\n"
        "DELETE FROM t1 WHERE id=1;\n",
        encoding="utf-8",
    )
    ignored_hidden_file = tmp_path / ".hidden.sql"
    ignored_hidden_file.write_text(
        "INSERT INTO hidden_table VALUES(1)\n", encoding="utf-8"
    )
    ignored_text_file = tmp_path / "notes.txt"
    ignored_text_file.write_text("INSERT INTO text_table VALUES(1)\n", encoding="utf-8")
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    nested_file = nested_dir / "02.sql"
    nested_file.write_text("UPDATE t1 SET name='archery'\n", encoding="utf-8")

    rows = read_my2sql_output_files(str(tmp_path), 2)

    assert rows == [
        {
            "sql": "INSERT INTO t1 VALUES(1);",
            "extra_info": "# datetime=2024-01-01 00:00:00",
        },
        {
            "sql": "DELETE FROM t1 WHERE id=1;",
            "extra_info": "# datetime=2024-01-01 00:00:00",
        },
    ]


def test_read_output_files_carries_extra_info_across_files(tmp_path):
    """跨文件读取时沿用最近一次 extra_info"""
    first_file = tmp_path / "01.sql"
    first_file.write_text("# binlog=mysql-bin.000001\n", encoding="utf-8")
    second_file = tmp_path / "02.sql"
    second_file.write_text("UPDATE t1 SET id=2 WHERE id=1\n", encoding="utf-8")

    rows = read_my2sql_output_files(str(tmp_path), 10)

    assert rows == [
        {
            "sql": "UPDATE t1 SET id=2 WHERE id=1;",
            "extra_info": "# binlog=mysql-bin.000001",
        }
    ]


def test_read_output_files_returns_empty_for_directory_without_sql(tmp_path):
    """目录中没有可读取 SQL 文件时返回空列表"""
    (tmp_path / "notes.txt").write_text("UPDATE t1 SET id=1\n", encoding="utf-8")

    assert read_my2sql_output_files(str(tmp_path), 10) == []


# ====================== binlog_list 测试 ======================


def test_instance_not_exist(client_with_super_user):
    """实例不存在时返回错误"""
    data = {"instance_name": "not_exist_instance"}
    r = client_with_super_user.post("/binlog/list/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 1
    assert result["msg"] == "实例不存在"


@patch("sql.binlog.get_engine")
def test_binlog_list_success(mock_get_engine, client_with_super_user, db_instance):
    """获取binlog列表成功"""
    mock_engine = MagicMock()
    mock_engine.query.return_value = _make_query_result(
        columns=["Log_name", "File_size"],
        rows=[
            ("mysql-bin.000001", 154),
            ("mysql-bin.000002", 356),
        ],
        error=None,
    )
    mock_get_engine.return_value = mock_engine

    data = {"instance_name": db_instance.instance_name}
    r = client_with_super_user.post("/binlog/list/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 0
    assert result["msg"] == "ok"
    assert len(result["data"]) == 2
    assert result["data"][0]["Log_name"] == "mysql-bin.000001"
    assert result["data"][0]["File_size"] == 154
    assert result["data"][1]["Log_name"] == "mysql-bin.000002"


@patch("sql.binlog.get_engine")
def test_binlog_list_query_error(mock_get_engine, client_with_super_user, db_instance):
    """获取binlog列表查询失败"""
    mock_engine = MagicMock()
    mock_engine.query.return_value = _make_query_result(
        columns=[], rows=[], error="查询出错"
    )
    mock_get_engine.return_value = mock_engine

    data = {"instance_name": db_instance.instance_name}
    r = client_with_super_user.post("/binlog/list/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 1
    assert result["msg"] == "查询出错"


@patch("sql.binlog.get_engine")
def test_binlog_list_empty(mock_get_engine, client_with_super_user, db_instance):
    """获取binlog列表为空"""
    mock_engine = MagicMock()
    mock_engine.query.return_value = _make_query_result(
        columns=["Log_name", "File_size"], rows=[], error=None
    )
    mock_get_engine.return_value = mock_engine

    data = {"instance_name": db_instance.instance_name}
    r = client_with_super_user.post("/binlog/list/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 0
    assert result["data"] == []


@pytest.mark.django_db(transaction=True)
def test_binlog_list_no_permission(db_instance):
    """无权限用户访问被拒"""
    from sql.models import Users

    user = Users.objects.create(username="no_perm_user", is_active=True)
    client = Client()
    client.force_login(user)
    data = {"instance_name": db_instance.instance_name}
    r = client.post("/binlog/list/", data=data)
    # 无权限应返回 403
    assert r.status_code == 403
    user.delete()


# ====================== del_binlog 测试 ======================


def test_del_binlog_instance_not_exist(client_with_super_user):
    """实例不存在时返回错误"""
    data = {"instance_id": 99999, "binlog": "mysql-bin.000001"}
    r = client_with_super_user.post("/binlog/del_log/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 1
    assert result["msg"] == "实例不存在"


def test_del_binlog_no_binlog_selected(client_with_super_user, db_instance):
    """未选择binlog时返回错误"""
    data = {"instance_id": db_instance.id, "binlog": ""}
    r = client_with_super_user.post("/binlog/del_log/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 1
    assert "未选择binlog" in result["msg"]


@patch("sql.binlog.get_engine")
def test_del_binlog_success(mock_get_engine, client_with_super_user, db_instance):
    """清理binlog成功"""
    mock_engine = MagicMock()
    mock_engine.escape_string.return_value = "mysql-bin.000001"
    mock_engine.query.return_value = _make_query_result(columns=[], rows=[], error=None)
    mock_get_engine.return_value = mock_engine

    data = {"instance_id": db_instance.id, "binlog": "mysql-bin.000001"}
    r = client_with_super_user.post("/binlog/del_log/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 0
    assert result["msg"] == "清理成功"
    # 验证 escape_string 被调用
    mock_engine.escape_string.assert_called_once_with("mysql-bin.000001")
    # 验证 purge 命令被正确执行
    mock_engine.query.assert_called_once()


@patch("sql.binlog.get_engine")
def test_del_binlog_fail(mock_get_engine, client_with_super_user, db_instance):
    """清理binlog失败"""
    mock_engine = MagicMock()
    mock_engine.escape_string.return_value = "mysql-bin.000001"
    mock_engine.query.return_value = _make_query_result(
        columns=[], rows=[], error="purge error"
    )
    mock_get_engine.return_value = mock_engine

    data = {"instance_id": db_instance.id, "binlog": "mysql-bin.000001"}
    r = client_with_super_user.post("/binlog/del_log/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 2
    assert "清理失败" in result["msg"]
    assert "purge error" in result["msg"]


@pytest.mark.django_db(transaction=True)
def test_del_binlog_no_permission(db_instance):
    """无权限用户访问被拒"""
    from sql.models import Users

    user = Users.objects.create(username="no_perm_user2", is_active=True)
    client = Client()
    client.force_login(user)
    data = {"instance_id": db_instance.id, "binlog": "mysql-bin.000001"}
    r = client.post("/binlog/del_log/", data=data)
    assert r.status_code == 403
    user.delete()


# ====================== my2sql 测试 ======================


@patch("sql.binlog.get_engine")
@patch("sql.binlog.My2SQL")
def test_my2sql_args_check_fail(
    mock_my2sql_cls, mock_get_engine, client_with_super_user, db_instance
):
    """参数校验失败时返回错误"""
    mock_my2sql = MagicMock()
    mock_my2sql.check_args.return_value = {
        "status": 1,
        "msg": "可执行文件路径不能为空！",
        "data": {},
    }
    mock_my2sql_cls.return_value = mock_my2sql

    data = {
        "instance_name": db_instance.instance_name,
        "save_sql": "false",
        "rollback": "false",
        "num": "30",
        "threads": "4",
        "start_file": "mysql-bin.000001",
        "start_pos": "",
        "end_file": "",
        "end_pos": "",
        "stop_time": "",
        "start_time": "",
        "only_schemas": [],
        "only_tables[]": [],
        "sql_type[]": [],
        "extra_info": "false",
        "ignore_primary_key": "false",
        "full_columns": "false",
        "no_db_prefix": "false",
        "file_per_table": "false",
    }
    r = client_with_super_user.post("/binlog/my2sql/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 1
    assert "可执行文件路径不能为空" in result["msg"]


@pytest.mark.django_db(transaction=True)
def test_my2sql_instance_not_exist(client_with_super_user):
    """实例不存在时视图未捕获DoesNotExist异常"""
    data = {
        "instance_name": "not_exist_instance",
        "save_sql": "false",
        "rollback": "false",
        "num": "30",
        "threads": "4",
        "start_file": "mysql-bin.000001",
    }
    # my2sql 视图中 Instance.objects.get 未做 try/except，
    # 故 Instance.DoesNotExist 会直接抛出
    with pytest.raises(Instance.DoesNotExist):
        client_with_super_user.post("/binlog/my2sql/", data=data)


@patch("sql.binlog.async_task")
@patch("sql.binlog.My2SQL")
def test_my2sql_success_with_rows(
    mock_my2sql_cls, mock_async_task, client_with_super_user, db_instance
):
    """my2sql解析成功，返回SQL行"""
    mock_my2sql = MagicMock()
    mock_my2sql.check_args.return_value = {"status": 0, "msg": "ok", "data": {}}
    mock_my2sql.generate_args2cmd.return_value = ["my2sql", "-host", "127.0.0.1"]

    # 模拟子进程输出
    mock_process = MagicMock()
    mock_process.stdout.readline.side_effect = [
        "INSERT INTO t1 VALUES(1)",
        "DELETE FROM t1 WHERE id=1",
        "UPDATE t1 SET a=1",
        "",
    ]
    mock_process.stderr.read.return_value = ""
    mock_my2sql.execute_cmd.return_value = mock_process
    mock_my2sql_cls.return_value = mock_my2sql

    data = {
        "instance_name": db_instance.instance_name,
        "save_sql": "false",
        "rollback": "false",
        "num": "30",
        "threads": "4",
        "start_file": "mysql-bin.000001",
        "start_pos": "",
        "end_file": "",
        "end_pos": "",
        "stop_time": "",
        "start_time": "",
        "extra_info": "false",
        "ignore_primary_key": "false",
        "full_columns": "false",
        "no_db_prefix": "false",
        "file_per_table": "false",
    }
    r = client_with_super_user.post("/binlog/my2sql/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 0
    assert len(result["data"]) == 3
    assert result["data"][0]["sql"] == "INSERT INTO t1 VALUES(1);"
    assert result["data"][1]["sql"] == "DELETE FROM t1 WHERE id=1;"
    assert result["data"][2]["sql"] == "UPDATE t1 SET a=1;"
    # 验证子进程被终止
    mock_process.kill.assert_called_once()
    # 验证异步保存未触发
    mock_async_task.assert_not_called()


@patch("sql.binlog.async_task")
@patch("sql.binlog.My2SQL")
def test_my2sql_no_rows_with_stderr(
    mock_my2sql_cls, mock_async_task, client_with_super_user, db_instance
):
    """my2sql解析无SQL行但有错误输出"""
    mock_my2sql = MagicMock()
    mock_my2sql.check_args.return_value = {"status": 0, "msg": "ok", "data": {}}
    mock_my2sql.generate_args2cmd.return_value = ["my2sql", "-host", "127.0.0.1"]

    mock_process = MagicMock()
    mock_process.stdout.readline.return_value = ""
    mock_process.stderr.read.return_value = "Error: binary log not found"
    mock_my2sql.execute_cmd.return_value = mock_process
    mock_my2sql_cls.return_value = mock_my2sql

    data = {
        "instance_name": db_instance.instance_name,
        "save_sql": "false",
        "rollback": "false",
        "num": "30",
        "threads": "4",
        "start_file": "mysql-bin.000001",
        "start_pos": "",
        "end_file": "",
        "end_pos": "",
        "stop_time": "",
        "start_time": "",
        "extra_info": "false",
        "ignore_primary_key": "false",
        "full_columns": "false",
        "no_db_prefix": "false",
        "file_per_table": "false",
    }
    r = client_with_super_user.post("/binlog/my2sql/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 1
    assert "binary log not found" in result["msg"]


@patch("sql.binlog.async_task")
@patch("sql.binlog.My2SQL")
def test_my2sql_no_rows_no_stderr(
    mock_my2sql_cls, mock_async_task, client_with_super_user, db_instance
):
    """my2sql解析无SQL行且无错误输出"""
    mock_my2sql = MagicMock()
    mock_my2sql.check_args.return_value = {"status": 0, "msg": "ok", "data": {}}
    mock_my2sql.generate_args2cmd.return_value = ["my2sql", "-host", "127.0.0.1"]

    mock_process = MagicMock()
    mock_process.stdout.readline.return_value = ""
    mock_process.stderr.read.return_value = ""
    mock_my2sql.execute_cmd.return_value = mock_process
    mock_my2sql_cls.return_value = mock_my2sql

    data = {
        "instance_name": db_instance.instance_name,
        "save_sql": "false",
        "rollback": "false",
        "num": "30",
        "threads": "4",
        "start_file": "mysql-bin.000001",
        "start_pos": "",
        "end_file": "",
        "end_pos": "",
        "stop_time": "",
        "start_time": "",
        "extra_info": "false",
        "ignore_primary_key": "false",
        "full_columns": "false",
        "no_db_prefix": "false",
        "file_per_table": "false",
    }
    r = client_with_super_user.post("/binlog/my2sql/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 0
    assert result["data"] == []


@patch("sql.binlog.My2SQL")
def test_my2sql_exception_during_execution(
    mock_my2sql_cls, client_with_super_user, db_instance
):
    """my2sql执行过程中抛出异常"""
    mock_my2sql = MagicMock()
    mock_my2sql.check_args.return_value = {"status": 0, "msg": "ok", "data": {}}
    mock_my2sql.generate_args2cmd.return_value = ["my2sql", "-host", "127.0.0.1"]
    mock_my2sql.execute_cmd.side_effect = RuntimeError("命令执行失败")
    mock_my2sql_cls.return_value = mock_my2sql

    data = {
        "instance_name": db_instance.instance_name,
        "save_sql": "false",
        "rollback": "false",
        "num": "30",
        "threads": "4",
        "start_file": "mysql-bin.000001",
        "start_pos": "",
        "end_file": "",
        "end_pos": "",
        "stop_time": "",
        "start_time": "",
        "extra_info": "false",
        "ignore_primary_key": "false",
        "full_columns": "false",
        "no_db_prefix": "false",
        "file_per_table": "false",
    }
    r = client_with_super_user.post("/binlog/my2sql/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 1
    assert "命令执行失败" in result["msg"]


@patch("sql.binlog.async_task")
@patch("sql.binlog.My2SQL")
def test_my2sql_save_sql_triggered(
    mock_my2sql_cls, mock_async_task, client_with_super_user, db_instance
):
    """save_sql为true时触发异步保存"""
    mock_my2sql = MagicMock()
    mock_my2sql.check_args.return_value = {"status": 0, "msg": "ok", "data": {}}
    mock_my2sql.generate_args2cmd.return_value = ["my2sql", "-host", "127.0.0.1"]

    mock_process = MagicMock()
    mock_process.stdout.readline.side_effect = [
        "INSERT INTO t1 VALUES(1)",
        "",
    ]
    mock_process.stderr.read.return_value = ""
    mock_my2sql.execute_cmd.return_value = mock_process
    mock_my2sql_cls.return_value = mock_my2sql

    data = {
        "instance_name": db_instance.instance_name,
        "save_sql": "true",
        "rollback": "false",
        "num": "30",
        "threads": "4",
        "start_file": "mysql-bin.000001",
        "start_pos": "",
        "end_file": "",
        "end_pos": "",
        "stop_time": "",
        "start_time": "",
        "extra_info": "false",
        "ignore_primary_key": "false",
        "full_columns": "false",
        "no_db_prefix": "false",
        "file_per_table": "false",
    }
    r = client_with_super_user.post("/binlog/my2sql/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 0
    # 验证异步任务被调用
    mock_async_task.assert_called_once()
    call_kwargs = mock_async_task.call_args
    assert call_kwargs[1]["hook"] is not None  # hook=notify_for_my2sql


@patch("sql.binlog.async_task")
@patch("sql.binlog.My2SQL")
def test_my2sql_rollback_mode(
    mock_my2sql_cls, mock_async_task, client_with_super_user, db_instance
):
    """rollback模式解析"""
    mock_my2sql = MagicMock()
    mock_my2sql.check_args.return_value = {"status": 0, "msg": "ok", "data": {}}
    mock_my2sql.generate_args2cmd.return_value = [
        "my2sql",
        "-work-type",
        "rollback",
    ]

    mock_process = MagicMock()
    mock_process.stdout.readline.side_effect = [
        "DELETE FROM t1 WHERE id=1",
        "",
    ]
    mock_process.stderr.read.return_value = ""
    mock_my2sql.execute_cmd.return_value = mock_process
    mock_my2sql_cls.return_value = mock_my2sql

    data = {
        "instance_name": db_instance.instance_name,
        "save_sql": "false",
        "rollback": "true",
        "num": "30",
        "threads": "4",
        "start_file": "mysql-bin.000001",
        "start_pos": "",
        "end_file": "",
        "end_pos": "",
        "stop_time": "",
        "start_time": "",
        "extra_info": "false",
        "ignore_primary_key": "false",
        "full_columns": "false",
        "no_db_prefix": "false",
        "file_per_table": "false",
    }
    r = client_with_super_user.post("/binlog/my2sql/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 0
    # 验证 work_type 被设置为 rollback
    args_passed = mock_my2sql.generate_args2cmd.call_args[0][0]
    assert args_passed["work-type"] == "rollback"


@patch("sql.binlog.async_task")
@patch("sql.binlog.My2SQL")
def test_my2sql_num_limit(
    mock_my2sql_cls, mock_async_task, client_with_super_user, db_instance
):
    """测试num参数限制返回行数"""
    mock_my2sql = MagicMock()
    mock_my2sql.check_args.return_value = {"status": 0, "msg": "ok", "data": {}}
    mock_my2sql.generate_args2cmd.return_value = ["my2sql"]

    # 模拟输出5行SQL，但num限制为2
    mock_process = MagicMock()
    mock_process.stdout.readline.side_effect = [
        "INSERT INTO t1 VALUES(1)",
        "DELETE FROM t1 WHERE id=1",
        "UPDATE t1 SET a=1",
        "INSERT INTO t2 VALUES(2)",
        "DELETE FROM t2 WHERE id=2",
        "",
    ]
    mock_process.stderr.read.return_value = ""
    mock_my2sql.execute_cmd.return_value = mock_process
    mock_my2sql_cls.return_value = mock_my2sql

    data = {
        "instance_name": db_instance.instance_name,
        "save_sql": "false",
        "rollback": "false",
        "num": "2",
        "threads": "4",
        "start_file": "mysql-bin.000001",
        "start_pos": "",
        "end_file": "",
        "end_pos": "",
        "stop_time": "",
        "start_time": "",
        "extra_info": "false",
        "ignore_primary_key": "false",
        "full_columns": "false",
        "no_db_prefix": "false",
        "file_per_table": "false",
    }
    r = client_with_super_user.post("/binlog/my2sql/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 0
    assert len(result["data"]) == 2


@patch("sql.binlog.read_my2sql_output_files")
@patch("sql.binlog.async_task")
@patch("sql.binlog.My2SQL")
def test_my2sql_extra_options(
    mock_my2sql_cls,
    mock_async_task,
    mock_read_output_files,
    client_with_super_user,
    db_instance,
):
    """测试 extra_info、ignore_primary_key、full_columns 等选项"""
    mock_my2sql = MagicMock()
    mock_my2sql.check_args.return_value = {"status": 0, "msg": "ok", "data": {}}
    mock_my2sql.generate_args2cmd.return_value = ["my2sql"]
    mock_read_output_files.return_value = [{"sql": "INSERT INTO t1 VALUES(1);"}]

    mock_process = MagicMock()
    mock_process.communicate.return_value = ("", "")
    mock_my2sql.execute_cmd.return_value = mock_process
    mock_my2sql_cls.return_value = mock_my2sql

    data = {
        "instance_name": db_instance.instance_name,
        "save_sql": "false",
        "rollback": "false",
        "num": "30",
        "threads": "4",
        "start_file": "mysql-bin.000001",
        "start_pos": "",
        "end_file": "",
        "end_pos": "",
        "stop_time": "",
        "start_time": "",
        "extra_info": "true",
        "ignore_primary_key": "true",
        "full_columns": "true",
        "no_db_prefix": "true",
        "file_per_table": "true",
    }
    r = client_with_super_user.post("/binlog/my2sql/", data=data)
    result = json.loads(r.content)
    assert result["status"] == 0
    # 验证参数传递
    args_passed = mock_my2sql.generate_args2cmd.call_args[0][0]
    assert args_passed["add-extraInfo"] is True
    assert args_passed["ignore-primaryKey-forInsert"] is True
    assert args_passed["full-columns"] is True
    assert args_passed["do-not-add-prifixDb"] is True
    assert args_passed["file-per-table"] is True


@pytest.mark.django_db(transaction=True)
def test_my2sql_no_permission(db_instance):
    """无权限用户访问被拒"""
    from sql.models import Users

    user = Users.objects.create(username="no_perm_user3", is_active=True)
    client = Client()
    client.force_login(user)
    data = {"instance_name": db_instance.instance_name}
    r = client.post("/binlog/my2sql/", data=data)
    assert r.status_code == 403
    user.delete()


# ====================== my2sql_file 测试 ======================


@patch("sql.binlog.My2SQL")
@patch("sql.binlog.os.makedirs")
def test_my2sql_file_success(mock_makedirs, mock_my2sql_cls, db_instance, settings):
    """my2sql_file 正常执行"""
    settings.BASE_DIR = "/tmp/archery_test"

    mock_my2sql = MagicMock()
    mock_my2sql.generate_args2cmd.return_value = ["my2sql", "-output-dir", "/tmp"]
    mock_my2sql.execute_cmd.return_value = MagicMock()
    mock_my2sql_cls.return_value = mock_my2sql

    user = MagicMock()
    args = {
        "instance": db_instance,
        "start-file": "mysql-bin.000001",
        "work-type": "2sql",
    }

    result = my2sql_file(args, user)
    assert result == (user, os.path.join("/tmp/archery_test", "downloads/my2sql/"))
    # 验证参数中 instance 被弹出
    call_args = mock_my2sql.generate_args2cmd.call_args[0][0]
    assert "instance" not in call_args
    assert "output-dir" in call_args
    # 验证目录创建
    mock_makedirs.assert_called_once()


@patch("sql.binlog.My2SQL")
@patch("sql.binlog.os.makedirs")
def test_my2sql_file_args_updated(
    mock_makedirs, mock_my2sql_cls, db_instance, settings
):
    """my2sql_file 参数正确更新"""
    settings.BASE_DIR = "/tmp/archery_test"

    mock_my2sql = MagicMock()
    mock_my2sql.generate_args2cmd.return_value = ["my2sql"]
    mock_my2sql.execute_cmd.return_value = MagicMock()
    mock_my2sql_cls.return_value = mock_my2sql

    user = MagicMock()
    args = {
        "instance": db_instance,
        "start-file": "mysql-bin.000001",
        "work-type": "2sql",
    }

    my2sql_file(args, user)
    # 验证 instance 的连接信息被重新放入 args
    call_args = mock_my2sql.generate_args2cmd.call_args[0][0]
    assert call_args["host"] == db_instance.host
    assert call_args["port"] == db_instance.port


@patch("sql.binlog.My2SQL")
@patch("sql.binlog.os.makedirs")
def test_my2sql_file_execute_cmd_called(
    mock_makedirs, mock_my2sql_cls, db_instance, settings
):
    """my2sql_file 正确调用 execute_cmd"""
    settings.BASE_DIR = "/tmp/archery_test"

    mock_my2sql = MagicMock()
    mock_my2sql.generate_args2cmd.return_value = ["my2sql", "-output-dir", "/tmp"]
    mock_my2sql.execute_cmd.return_value = MagicMock()
    mock_my2sql_cls.return_value = mock_my2sql

    user = MagicMock()
    args = {
        "instance": db_instance,
        "start-file": "mysql-bin.000001",
    }

    my2sql_file(args, user)
    mock_my2sql.execute_cmd.assert_called_once_with(["my2sql", "-output-dir", "/tmp"])
