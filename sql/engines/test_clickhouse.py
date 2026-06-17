# -*- coding: UTF-8 -*-
"""
ClickHouse 引擎单元测试
对 sql/engines/clickhouse.py 中的 ClickHouseEngine 进行全面的功能覆盖测试

所有测试使用 Mock 对象模拟 Instance，不依赖真实数据库
"""

from unittest.mock import patch, Mock

import pytest

from sql.engines.clickhouse import ClickHouseEngine
from sql.engines.models import ResultSet, ReviewSet, ReviewResult


@pytest.fixture
def mock_instance():
    """模拟 Instance 对象，避免对 Django ORM 和数据库的依赖"""
    ins = Mock()
    ins.instance_name = "ch_ins"
    ins.host = "some_host"
    ins.port = 9000
    ins.db_name = "test_db"
    ins.db_type = "clickhouse"
    ins.mode = ""
    ins.tunnel = None
    ins.get_username_password.return_value = ("ins_user", "some_str")
    return ins


# ----------------- 基本属性 -----------------
def test_engine_base_info(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    assert engine.name == "ClickHouse"
    assert engine.info == "ClickHouse engine"
    assert engine.test_query == "SELECT 1"


def test_auto_backup(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    assert engine.auto_backup is False


def test_escape_string(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    # 包含特殊字符时应被转义
    result = engine.escape_string("a'b\\c")
    assert isinstance(result, str)
    assert result != "a'b\\c"


# ----------------- 连接管理 -----------------
@patch("sql.engines.clickhouse.connect")
def test_get_connection_without_db(mock_connect, mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    engine.get_connection()
    mock_connect.assert_called_once()
    kwargs = mock_connect.call_args.kwargs
    assert "database" not in kwargs
    assert kwargs["host"] == "some_host"
    assert kwargs["port"] == 9000


@patch("sql.engines.clickhouse.connect")
def test_get_connection_with_db(mock_connect, mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    engine.get_connection(db_name="my_db")
    mock_connect.assert_called_once()
    kwargs = mock_connect.call_args.kwargs
    assert kwargs.get("database") == "my_db"


@patch("sql.engines.clickhouse.connect")
def test_get_connection_reuse(mock_connect, mock_instance):
    """已存在的连接应被复用"""
    engine = ClickHouseEngine(instance=mock_instance)
    engine.conn = Mock()
    conn = engine.get_connection()
    assert conn is engine.conn
    mock_connect.assert_not_called()


def test_close(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    mock_conn = Mock()
    engine.conn = mock_conn
    engine.close()
    mock_conn.close.assert_called_once()
    assert engine.conn is None


def test_close_when_no_conn(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    engine.conn = None
    engine.close()  # 不应抛异常
    assert engine.conn is None


# ----------------- query -----------------
@patch("sql.engines.clickhouse.connect")
def test_query_success(mock_connect, mock_instance):
    mock_cursor = Mock()
    mock_cursor.fetchmany.return_value = [("v1", "v2")]
    mock_cursor.description = (("k1", "x"), ("k2", "x"))
    mock_connect.return_value.cursor.return_value = mock_cursor

    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.query(sql="select 1", limit_num=10)
    mock_cursor.execute.assert_called_once()
    mock_cursor.fetchmany.assert_called_once_with(size=10)
    assert isinstance(rs, ResultSet)
    assert rs.column_list == ["k1", "k2"]
    assert rs.rows == [("v1", "v2")]
    assert rs.affected_rows == 1


@patch("sql.engines.clickhouse.connect")
def test_query_fetchall(mock_connect, mock_instance):
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = [("a",), ("b",)]
    mock_cursor.description = (("col", "x"),)
    mock_connect.return_value.cursor.return_value = mock_cursor

    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.query(sql="select 1", limit_num=0)
    mock_cursor.fetchall.assert_called_once()
    assert rs.affected_rows == 2


@patch("sql.engines.clickhouse.connect")
def test_query_error(mock_connect, mock_instance):
    mock_cursor = Mock()
    mock_cursor.execute.side_effect = Exception("boom\nStack trace:xxx")
    mock_connect.return_value.cursor.return_value = mock_cursor

    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.query(sql="bad sql")
    assert "boom" in rs.error
    assert "Stack trace" not in rs.error


# ----------------- server_version -----------------
@patch.object(ClickHouseEngine, "query")
def test_server_version(mock_query, mock_instance):
    mock_query.return_value = ResultSet(rows=[("ClickHouse 21.8.3.44",)])
    engine = ClickHouseEngine(instance=mock_instance)
    assert engine.server_version == (21, 8, 3)


# ----------------- 结构类查询 -----------------
@patch.object(ClickHouseEngine, "query")
def test_get_table_engine_exist(mock_query, mock_instance):
    mock_query.return_value = ResultSet(rows=[("MergeTree",)])
    engine = ClickHouseEngine(instance=mock_instance)
    ret = engine.get_table_engine("db.tb")
    assert ret == {"status": 1, "engine": "MergeTree"}


@patch.object(ClickHouseEngine, "query")
def test_get_table_engine_not_exist(mock_query, mock_instance):
    mock_query.return_value = ResultSet(rows=[])
    engine = ClickHouseEngine(instance=mock_instance)
    ret = engine.get_table_engine("db.tb")
    assert ret == {"status": 0, "engine": "None"}


@patch.object(ClickHouseEngine, "query")
def test_get_all_databases(mock_query, mock_instance):
    mock_query.return_value = ResultSet(
        rows=[
            ("system",),
            ("INFORMATION_SCHEMA",),
            ("information_schema",),
            ("datasets",),
            ("my_db",),
            ("another",),
        ]
    )
    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.get_all_databases()
    assert rs.rows == ["my_db", "another"]


@patch.object(ClickHouseEngine, "query")
def test_get_all_tables(mock_query, mock_instance):
    mock_query.return_value = ResultSet(rows=[("t1",), ("t2",)])
    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.get_all_tables(db_name="my_db")
    assert rs.rows == ["t1", "t2"]


@patch.object(ClickHouseEngine, "query")
def test_get_all_columns_by_tb(mock_query, mock_instance):
    mock_query.return_value = ResultSet(
        rows=[("id", "Int32", ""), ("name", "String", "")]
    )
    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.get_all_columns_by_tb(db_name="my_db", tb_name="t1")
    assert rs.rows == ["id", "name"]


@patch.object(ClickHouseEngine, "query")
def test_describe_table(mock_query, mock_instance):
    mock_query.return_value = ResultSet(
        rows=[("CREATE TABLE t1 (id Int32,name String) ENGINE = MergeTree",)]
    )
    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.describe_table(db_name="my_db", tb_name="t1")
    assert rs.rows[0][0] == "t1"
    assert "\n" in rs.rows[0][1]


# ----------------- query_check -----------------
@patch.object(ClickHouseEngine, "server_version", new=(21, 8, 3))
@patch.object(ClickHouseEngine, "query")
def test_query_check_valid_select(mock_query, mock_instance):
    mock_query.return_value = ResultSet(rows=[("plan",)])
    engine = ClickHouseEngine(instance=mock_instance)
    result = engine.query_check(db_name="my_db", sql="select id from t1")
    assert result["bad_query"] is False


@patch.object(ClickHouseEngine, "server_version", new=(21, 8, 3))
def test_query_check_bad_syntax_type(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    result = engine.query_check(db_name="my_db", sql="delete from t1")
    assert result["bad_query"] is True
    assert result["msg"] == "不支持的查询语法类型!"


@patch.object(ClickHouseEngine, "server_version", new=(21, 8, 3))
@patch.object(ClickHouseEngine, "query")
def test_query_check_has_star(mock_query, mock_instance):
    mock_query.return_value = ResultSet(rows=[("plan",)])
    engine = ClickHouseEngine(instance=mock_instance)
    result = engine.query_check(db_name="my_db", sql="select * from t1")
    assert result["has_star"] is True


@patch.object(ClickHouseEngine, "server_version", new=(20, 1, 0))
def test_query_check_explain_low_version(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    result = engine.query_check(db_name="my_db", sql="explain select 1")
    assert result["bad_query"] is True
    assert "不支持explain" in result["msg"]


@patch.object(ClickHouseEngine, "server_version", new=(21, 8, 3))
@patch.object(ClickHouseEngine, "query")
def test_query_check_explain_error(mock_query, mock_instance):
    rs = ResultSet()
    rs.error = "syntax error"
    mock_query.return_value = rs
    engine = ClickHouseEngine(instance=mock_instance)
    result = engine.query_check(db_name="my_db", sql="select id from t1")
    assert result["bad_query"] is True
    assert result["msg"] == "syntax error"


def test_query_check_empty(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    result = engine.query_check(db_name="my_db", sql="-- only comment\n")
    assert result["bad_query"] is True


# ----------------- filter_sql -----------------
def test_filter_sql_no_limit(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    sql = engine.filter_sql(sql="select id from t1", limit_num=100)
    assert sql == "select id from t1 limit 100;"


def test_filter_sql_with_limit_n(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    sql = engine.filter_sql(sql="select id from t1 limit 200", limit_num=100)
    assert sql == "select id from t1 limit 100;"


def test_filter_sql_with_limit_offset(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    sql = engine.filter_sql(sql="select id from t1 limit 200 offset 50", limit_num=100)
    assert sql == "select id from t1 limit 100 offset 50;"


def test_filter_sql_with_offset_comma_limit(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    sql = engine.filter_sql(sql="select id from t1 limit 10,200", limit_num=100)
    assert sql == "select id from t1 limit 10,100;"


def test_filter_sql_not_select(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    sql = engine.filter_sql(sql="show tables", limit_num=100)
    assert sql == "show tables;"


# ----------------- explain_check -----------------
@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
@patch.object(ClickHouseEngine, "query")
def test_explain_check_ok(mock_query, mock_instance):
    mock_query.return_value = ResultSet(rows=[("ast",)])
    engine = ClickHouseEngine(instance=mock_instance)
    ret = engine.explain_check(
        check_result=ReviewSet(),
        db_name="db",
        line=1,
        statement="alter table t1 add column c1 Int32",
    )
    assert ret.errlevel == 0


@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
@patch.object(ClickHouseEngine, "query")
def test_explain_check_error(mock_query, mock_instance):
    rs = ResultSet()
    rs.error = "bad ast"
    mock_query.return_value = rs
    engine = ClickHouseEngine(instance=mock_instance)
    ret = engine.explain_check(
        check_result=ReviewSet(), db_name="db", line=1, statement="alter table t1"
    )
    assert ret.errlevel == 2
    assert "bad ast" in ret.errormessage


@patch.object(ClickHouseEngine, "server_version", new=(20, 1, 0))
def test_explain_check_version_too_low(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    ret = engine.explain_check(
        check_result=ReviewSet(), db_name="db", line=1, statement="alter table t1"
    )
    # 低版本直接返回审核通过结果，不会执行 explain
    assert ret.errlevel == 0


# ----------------- execute_check -----------------
def _mock_config(engine, critical_ddl_regex=""):
    """辅助：mock 引擎的 config 对象"""
    mock_cfg = Mock()
    mock_cfg.get.return_value = critical_ddl_regex
    engine.config = mock_cfg


@patch.object(ClickHouseEngine, "server_version", new=(21, 8, 3))
def test_execute_check_reject_select(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine)
    ret = engine.execute_check(db_name="db", sql="select 1;")
    assert isinstance(ret, ReviewSet)
    assert ret.rows[0].errlevel == 2
    assert "仅支持DML和DDL语句" in ret.rows[0].errormessage


@patch.object(ClickHouseEngine, "server_version", new=(21, 8, 3))
def test_execute_check_critical_ddl(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine, critical_ddl_regex="^drop")
    ret = engine.execute_check(db_name="db", sql="drop table t1;")
    assert ret.rows[0].errlevel == 2
    assert "高危" in ret.rows[0].stagestatus


@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
@patch.object(ClickHouseEngine, "get_table_engine")
def test_execute_check_alter_table_not_exist(mock_get_engine, mock_instance):
    mock_get_engine.return_value = {"status": 0, "engine": "None"}
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine)
    ret = engine.execute_check(db_name="db", sql="alter table t1 add column c Int;")
    assert ret.rows[0].errlevel == 2
    assert ret.rows[0].stagestatus == "表不存在"


@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
@patch.object(ClickHouseEngine, "get_table_engine")
def test_execute_check_alter_table_unsupported_engine(mock_get_engine, mock_instance):
    mock_get_engine.return_value = {"status": 1, "engine": "Log"}
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine)
    ret = engine.execute_check(db_name="db", sql="alter table t1 add column c Int;")
    assert ret.rows[0].errlevel == 2
    assert "MergeTree" in ret.rows[0].errormessage


@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
@patch.object(ClickHouseEngine, "get_table_engine")
@patch.object(ClickHouseEngine, "explain_check")
def test_execute_check_alter_table_mergetree(
    mock_explain, mock_get_engine, mock_instance
):
    mock_get_engine.return_value = {"status": 1, "engine": "MergeTree"}
    mock_explain.return_value = ReviewResult(
        id=1,
        errlevel=0,
        stagestatus="Audit completed",
        errormessage="None",
        sql="alter table t1 add column c Int",
        affected_rows=0,
        execute_time=0,
    )
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine)
    ret = engine.execute_check(db_name="db", sql="alter table t1 add column c Int;")
    assert ret.rows[0].errlevel == 0
    mock_explain.assert_called_once()


@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
@patch.object(ClickHouseEngine, "get_table_engine")
def test_execute_check_alter_delete_non_mergetree(mock_get_engine, mock_instance):
    mock_get_engine.return_value = {"status": 1, "engine": "Distributed"}
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine)
    ret = engine.execute_check(db_name="db", sql="alter table t1 delete where id=1;")
    assert ret.rows[0].errlevel == 2
    assert "DELETE与UPDATE" in ret.rows[0].errormessage


@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
@patch.object(ClickHouseEngine, "get_table_engine")
@patch.object(ClickHouseEngine, "explain_check")
def test_execute_check_alter_delete_mergetree_calls_explain(
    mock_explain, mock_get_engine, mock_instance
):
    mock_get_engine.return_value = {"status": 1, "engine": "ReplacingMergeTree"}
    mock_explain.return_value = ReviewResult(
        id=1,
        errlevel=0,
        stagestatus="Audit completed",
        errormessage="None",
        sql="alter table t1 delete where id=1",
    )
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine)
    ret = engine.execute_check(db_name="db", sql="alter table t1 delete where id=1;")
    assert ret.rows[0].errlevel == 0
    mock_explain.assert_called_once()


@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
@patch.object(ClickHouseEngine, "explain_check")
def test_execute_check_other_alter_calls_explain(mock_explain, mock_instance):
    mock_explain.return_value = ReviewResult(
        id=1,
        errlevel=0,
        stagestatus="Audit completed",
        errormessage="None",
        sql="alter user default identified by 'pwd'",
    )
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine)
    ret = engine.execute_check(
        db_name="db", sql="alter user default identified by 'pwd';"
    )
    assert ret.rows[0].errlevel == 0
    mock_explain.assert_called_once()


@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
@patch.object(ClickHouseEngine, "get_table_engine")
def test_execute_check_truncate_unsupported_engine(mock_get_engine, mock_instance):
    mock_get_engine.return_value = {"status": 1, "engine": "View"}
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine)
    ret = engine.execute_check(db_name="db", sql="truncate table t1;")
    assert ret.rows[0].errlevel == 2
    assert "TRUNCATE" in ret.rows[0].errormessage


@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
@patch.object(ClickHouseEngine, "get_table_engine")
@patch.object(ClickHouseEngine, "explain_check")
def test_execute_check_truncate_supported_engine_calls_explain(
    mock_explain, mock_get_engine, mock_instance
):
    mock_get_engine.return_value = {"status": 1, "engine": "MergeTree"}
    mock_explain.return_value = ReviewResult(
        id=1,
        errlevel=0,
        stagestatus="Audit completed",
        errormessage="None",
        sql="truncate table t1",
    )
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine)
    ret = engine.execute_check(db_name="db", sql="truncate table t1;")
    assert ret.rows[0].errlevel == 0
    mock_explain.assert_called_once()


@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
@patch.object(ClickHouseEngine, "get_table_engine")
def test_execute_check_truncate_table_not_exist(mock_get_engine, mock_instance):
    mock_get_engine.return_value = {"status": 0, "engine": "None"}
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine)
    ret = engine.execute_check(db_name="db", sql="truncate table t1;")
    assert ret.rows[0].errlevel == 2
    assert ret.rows[0].stagestatus == "表不存在"


@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
@patch.object(ClickHouseEngine, "get_table_engine")
def test_execute_check_insert_table_exist(mock_get_engine, mock_instance):
    mock_get_engine.return_value = {"status": 1, "engine": "MergeTree"}
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine)
    ret = engine.execute_check(db_name="db", sql="insert into t1 values (1, 'a');")
    assert ret.rows[0].errlevel == 0


@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
@patch.object(ClickHouseEngine, "get_table_engine")
def test_execute_check_insert_table_not_exist(mock_get_engine, mock_instance):
    mock_get_engine.return_value = {"status": 0, "engine": "None"}
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine)
    ret = engine.execute_check(db_name="db", sql="insert into t1 values (1, 'a');")
    assert ret.rows[0].errlevel == 2
    assert ret.rows[0].stagestatus == "表不存在"


@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
def test_execute_check_insert_bad_syntax(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine)
    ret = engine.execute_check(db_name="db", sql="insert into ;")
    assert ret.rows[0].errlevel == 2
    assert "INSERT语法不正确" in ret.rows[0].errormessage


@patch.object(ClickHouseEngine, "server_version", new=(21, 1, 2))
@patch.object(ClickHouseEngine, "explain_check")
def test_execute_check_other_statement_uses_explain(mock_explain, mock_instance):
    mock_explain.return_value = ReviewResult(
        id=1,
        errlevel=1,
        stagestatus="Audit completed",
        errormessage="warning",
        sql="create database db2",
    )
    engine = ClickHouseEngine(instance=mock_instance)
    _mock_config(engine)
    ret = engine.execute_check(db_name="db", sql="create database db2;")
    assert ret.rows[0].errlevel == 1
    assert ret.warning_count == 1
    mock_explain.assert_called_once()


# ----------------- execute -----------------
@patch("sql.engines.clickhouse.connect")
def test_execute_success(mock_connect, mock_instance):
    mock_cursor = Mock()
    mock_connect.return_value.cursor.return_value = mock_cursor
    engine = ClickHouseEngine(instance=mock_instance)
    result = engine.execute(db_name="db", sql="insert into t1 values(1);")
    assert isinstance(result, ResultSet)
    assert result.error is None
    mock_cursor.execute.assert_called()


@patch("sql.engines.clickhouse.connect")
def test_execute_error(mock_connect, mock_instance):
    mock_cursor = Mock()
    mock_cursor.execute.side_effect = Exception("failed\nStack trace:...")
    mock_connect.return_value.cursor.return_value = mock_cursor
    engine = ClickHouseEngine(instance=mock_instance)
    result = engine.execute(db_name="db", sql="bad sql")
    assert "failed" in result.error
    assert "Stack trace" not in result.error


# ----------------- execute_workflow -----------------
def _build_workflow_mock(sql_content, db_name="db"):
    wf = Mock()
    wf.db_name = db_name
    wf.sqlworkflowcontent = Mock()
    wf.sqlworkflowcontent.sql_content = sql_content
    return wf


@patch.object(ClickHouseEngine, "execute")
def test_execute_workflow_all_success(mock_execute, mock_instance):
    rs = ResultSet()
    rs.error = None
    mock_execute.return_value = rs
    wf = _build_workflow_mock("insert into t values(1);insert into t values(2);")
    engine = ClickHouseEngine(instance=mock_instance)
    ret = engine.execute_workflow(wf)
    assert isinstance(ret, ReviewSet)
    assert len(ret.rows) == 2
    for r in ret.rows:
        assert r.errlevel == 0


@patch.object(ClickHouseEngine, "execute")
def test_execute_workflow_fail_stop(mock_execute, mock_instance):
    ok = ResultSet()
    ok.error = None
    bad = ResultSet()
    bad.error = "err"
    mock_execute.side_effect = [ok, bad]
    wf = _build_workflow_mock(
        "insert into t values(1);insert into t values(2);insert into t values(3);"
    )
    engine = ClickHouseEngine(instance=mock_instance)
    ret = engine.execute_workflow(wf)
    # 第一条成功，第二条失败，第三条标记为未执行
    assert ret.rows[0].errlevel == 0
    assert ret.rows[1].errlevel == 2
    assert ret.error == "err"


# ----------------- 数据字典相关 -----------------
@patch.object(ClickHouseEngine, "query")
def test_get_group_tables_by_db(mock_query, mock_instance):
    mock_query.return_value = ResultSet(
        rows=[("apple", "c1"), ("ant", "c2"), ("banana", "c3")]
    )
    engine = ClickHouseEngine(instance=mock_instance)
    ret = engine.get_group_tables_by_db(db_name="db")
    assert "a" in ret
    assert "b" in ret
    assert len(ret["a"]) == 2


@patch.object(ClickHouseEngine, "query")
def test_get_table_meta_data(mock_query, mock_instance):
    mock_query.return_value = ResultSet(
        column_list=["table_name", "engine"],
        rows=[("t1", "MergeTree")],
    )
    engine = ClickHouseEngine(instance=mock_instance)
    ret = engine.get_table_meta_data(db_name="db", tb_name="t1")
    assert ret["column_list"] == ["table_name", "engine"]
    assert ret["rows"] == ("t1", "MergeTree")


@patch.object(ClickHouseEngine, "query")
def test_get_table_desc_data(mock_query, mock_instance):
    mock_query.return_value = ResultSet(
        column_list=["列名", "列类型"],
        rows=[("id", "Int32"), ("name", "String")],
    )
    engine = ClickHouseEngine(instance=mock_instance)
    ret = engine.get_table_desc_data(db_name="db", tb_name="t1")
    assert len(ret["rows"]) == 2


@patch.object(ClickHouseEngine, "query")
def test_get_table_index_data(mock_query, mock_instance):
    mock_query.return_value = ResultSet(
        column_list=["索引名", "索引类型", "索引表达式", "粒度"],
        rows=[("idx1", "minmax", "id", 8192)],
    )
    engine = ClickHouseEngine(instance=mock_instance)
    ret = engine.get_table_index_data(db_name="db", tb_name="t1")
    assert len(ret["rows"]) == 1


@patch.object(ClickHouseEngine, "query")
def test_get_tables_metas_data(mock_query, mock_instance):
    tbs_rs = ResultSet(
        column_list=["TABLE_NAME", "TABLE_COMMENT", "ENGINE"],
        rows=[("t1", "comment", "MergeTree")],
    )
    cols_rs = ResultSet(
        column_list=[
            "COLUMN_NAME",
            "COLUMN_TYPE",
            "COLUMN_DEFAULT",
            "IS_IN_PRIMARY_KEY",
            "COLUMN_COMMENT",
        ],
        rows=[("id", "Int32", "", 1, "主键"), ("name", "String", "", 0, "名称")],
    )
    mock_query.side_effect = [tbs_rs, cols_rs]
    engine = ClickHouseEngine(instance=mock_instance)
    ret = engine.get_tables_metas_data(db_name="db")
    assert len(ret) == 1
    assert ret[0]["TABLE_INFO"]["TABLE_NAME"] == "t1"
    assert len(ret[0]["COLUMNS"]) == 2
    assert ret[0]["COLUMNS"][0]["COLUMN_NAME"] == "id"


@patch.object(ClickHouseEngine, "query")
def test_tablespace_default(mock_query, mock_instance):
    mock_query.return_value = ResultSet(
        column_list=[
            "database",
            "table",
            "engine",
            "table_rows",
            "total_size",
            "marks_bytes",
            "data_uncompressed",
            "data_compressed",
            "compress_ratio",
        ],
        rows=[
            (
                "my_db",
                "t1",
                "MergeTree",
                1000000,
                "1.00 GiB",
                "10.00 MiB",
                "2.00 GiB",
                "500.00 MiB",
                24.41,
            )
        ],
    )
    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.tablespace()
    mock_query.assert_called_once()
    call_sql = mock_query.call_args.kwargs.get(
        "sql", mock_query.call_args[1].get("sql")
    )
    assert "LIMIT 0,14" in call_sql
    assert isinstance(rs, ResultSet)
    assert rs.rows[0][0] == "my_db"
    assert rs.rows[0][1] == "t1"


@patch.object(ClickHouseEngine, "query")
def test_tablespace_custom_pagination(mock_query, mock_instance):
    mock_query.return_value = ResultSet(
        column_list=["database", "table", "engine", "table_rows"],
        rows=[("my_db", "t2", "Log", 1000000)],
    )
    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.tablespace(offset=14, row_count=7)
    mock_query.assert_called_once()
    call_sql = mock_query.call_args.kwargs.get(
        "sql", mock_query.call_args[1].get("sql")
    )
    assert "LIMIT 14,7" in call_sql
    assert rs.rows[0][1] == "t2"


@patch.object(ClickHouseEngine, "query")
def test_tablespace_with_schema_search(mock_query, mock_instance):
    mock_query.return_value = ResultSet(rows=[])
    engine = ClickHouseEngine(instance=mock_instance)
    engine.tablespace(schema_search="sales")
    call_sql = mock_query.call_args.kwargs.get(
        "sql", mock_query.call_args[1].get("sql")
    )
    assert "database LIKE '%sales%'" in call_sql
    assert "table LIKE '%sales%'" in call_sql


@patch.object(ClickHouseEngine, "query")
def test_tablespace_empty(mock_query, mock_instance):
    mock_query.return_value = ResultSet(
        column_list=[
            "database",
            "table",
            "engine",
            "table_rows",
            "total_size",
            "marks_bytes",
            "data_uncompressed",
            "data_compressed",
            "compress_ratio",
        ],
        rows=[],
    )
    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.tablespace()
    assert rs.rows == []


@patch.object(ClickHouseEngine, "query")
def test_tablespace_count(mock_query, mock_instance):
    mock_query.return_value = ResultSet(rows=[(5,)])
    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.tablespace_count()
    mock_query.assert_called_once()
    call_sql = mock_query.call_args.kwargs.get(
        "sql", mock_query.call_args[1].get("sql")
    )
    assert "count(DISTINCT" in call_sql
    assert "system.parts" in call_sql
    assert rs.rows[0][0] == 5


@patch.object(ClickHouseEngine, "query")
def test_tablespace_count_with_schema_search(mock_query, mock_instance):
    mock_query.return_value = ResultSet(rows=[(2,)])
    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.tablespace_count(schema_search="sales")
    call_sql = mock_query.call_args.kwargs.get(
        "sql", mock_query.call_args[1].get("sql")
    )
    assert "database LIKE '%sales%'" in call_sql
    assert "table LIKE '%sales%'" in call_sql
    assert rs.rows[0][0] == 2


@patch.object(ClickHouseEngine, "query")
def test_tablespace_count_zero(mock_query, mock_instance):
    mock_query.return_value = ResultSet(rows=[(0,)])
    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.tablespace_count()
    assert rs.rows[0][0] == 0


# ----------------- processlist -----------------
@patch.object(ClickHouseEngine, "query")
def test_processlist(mock_query, mock_instance):
    mock_query.return_value = ResultSet(
        column_list=[
            "query_id",
            "user",
            "ip",
            "port",
            "current_database",
            "time",
            "total_rows_approx",
            "memory",
            "query_kind",
            "query",
        ],
        rows=[
            (
                "qid-1",
                "default",
                "127.0.0.1",
                9000,
                "my_db",
                0.1,
                100,
                "1.00 MiB",
                "Select",
                "select 1",
            )
        ],
    )
    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.processlist(command_type="Process")
    mock_query.assert_called_once()
    call_sql = mock_query.call_args.kwargs.get(
        "sql", mock_query.call_args[1].get("sql")
    )
    # 校验关键字段都出现在 SQL 中
    assert "system.processes" in call_sql
    assert "query_id" in call_sql
    assert "replaceRegexpOne" in call_sql
    assert isinstance(rs, ResultSet)
    assert rs.rows[0][0] == "qid-1"
    assert rs.rows[0][2] == "127.0.0.1"


@patch.object(ClickHouseEngine, "query")
def test_processlist_empty(mock_query, mock_instance):
    mock_query.return_value = ResultSet(rows=[])
    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.processlist(command_type="Process")
    assert rs.rows == []


# ----------------- get_kill_command -----------------
def test_get_kill_command_empty(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    assert engine.get_kill_command([]) == ""


def test_get_kill_command_skips_blank_query_id(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    cmd = engine.get_kill_command(["qid-1", "   ", "qid-2"])
    assert cmd.count("KILL QUERY WHERE query_id = ") == 2
    assert "qid-1" in cmd
    assert "qid-2" in cmd


def test_get_kill_command_single(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    cmd = engine.get_kill_command(["qid-1"])
    assert cmd == "KILL QUERY WHERE query_id = 'qid-1';"


def test_get_kill_command_multiple(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    cmd = engine.get_kill_command(["qid-1", "qid-2", "qid-3"])
    assert cmd.count("KILL QUERY WHERE query_id = ") == 3
    assert "'qid-1'" in cmd
    assert "'qid-2'" in cmd
    assert "'qid-3'" in cmd
    # 多条语句以分号分隔
    assert cmd.endswith(";")


def test_get_kill_command_escape(mock_instance):
    """包含特殊字符的 query_id 应被转义"""
    engine = ClickHouseEngine(instance=mock_instance)
    cmd = engine.get_kill_command(["a'b"])
    # 转义后的字符串不应等于原始字符串
    assert "a'b" not in cmd or cmd != "KILL QUERY WHERE query_id = 'a'b';"
    assert cmd.startswith("KILL QUERY WHERE query_id = '")
    assert cmd.endswith("';")


# ----------------- kill -----------------
def test_kill_empty_ids(mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.kill([])
    assert isinstance(rs, ResultSet)
    assert rs.rows == []


@patch.object(ClickHouseEngine, "execute")
def test_kill_with_ids(mock_execute, mock_instance):
    mock_execute.return_value = ResultSet()
    engine = ClickHouseEngine(instance=mock_instance)
    rs = engine.kill(["qid-1", "qid-2"])
    mock_execute.assert_called_once()
    call_kwargs = mock_execute.call_args.kwargs
    call_sql = call_kwargs.get("sql") or mock_execute.call_args[0][0]
    assert "KILL QUERY" in call_sql
    assert "qid-1" in call_sql
    assert "qid-2" in call_sql
    assert isinstance(rs, ResultSet)


@patch.object(ClickHouseEngine, "execute")
def test_kill_does_not_call_execute_when_no_ids(mock_execute, mock_instance):
    engine = ClickHouseEngine(instance=mock_instance)
    engine.kill([])
    mock_execute.assert_not_called()
