import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch, Mock, ANY

import MySQLdb
from django.test import RequestFactory, SimpleTestCase

from common.config import SysConfig
from sql import instance_account
from sql.engines import ResultSet, ReviewSet
from sql.engines.models import ReviewResult
from sql.engines.mysql import MysqlEngine, MysqlForkType
from sql.models import Instance


class TestMysql(SimpleTestCase):
    def setUp(self):
        self.ins1 = Instance(
            instance_name="some_ins",
            type="slave",
            db_type="mysql",
            host="some_host",
            port=1366,
            user="ins_user",
            password="some_str",
        )
        self.sys_config = SysConfig()
        self.wf = SimpleNamespace(
            workflow_name="some_name",
            group_id=1,
            group_name="g1",
            engineer_display="",
            audit_auth_groups="some_group",
            create_time=datetime.now() - timedelta(days=1),
            status="workflow_finish",
            is_backup=True,
            instance=self.ins1,
            db_name="some_db",
            syntax_type=1,
        )
        self.wf.sqlworkflowcontent = SimpleNamespace(sql_content="update user set id=1")

    def tearDown(self):
        self.sys_config.sys_config = {}

    @patch("MySQLdb.connect")
    def test_engine_base_info(self, _conn):
        new_engine = MysqlEngine(instance=self.ins1)
        self.assertEqual(new_engine.name, "MySQL")
        self.assertEqual(new_engine.info, "MySQL engine")

    @patch("MySQLdb.connect")
    def testGetConnection(self, connect):
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.get_connection()
        connect.assert_called_once()

    @patch("MySQLdb.connect")
    def testQuery(self, connect):
        cur = Mock()
        connect.return_value.cursor = cur
        cur.return_value.execute = Mock()
        cur.return_value.fetchmany.return_value = (("v1", "v2"),)
        cur.return_value.description = (
            ("k1", "some_other_des"),
            ("k2", "some_other_des"),
        )
        new_engine = MysqlEngine(instance=self.ins1)
        query_result = new_engine.query(sql="some_str", limit_num=100)
        cur.return_value.execute.assert_called()
        cur.return_value.fetchmany.assert_called_once_with(size=100)
        connect.return_value.close.assert_called_once()
        self.assertIsInstance(query_result, ResultSet)

    @patch("MySQLdb.connect")
    def test_get_tables_metas_data(self, connect):
        """增加单元测试方法。test_get_tables_metas_data"""
        mock_conn = Mock()
        mock_cursor = Mock()
        connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # 模拟查询结果
        tables_result = [{"TABLE_SCHEMA": "test_db", "TABLE_NAME": "test_table"}]

        columns_result = [
            {
                "COLUMN_NAME": "id",
                "COLUMN_TYPE": "int",
                "COLUMN_DEFAULT": None,
                "IS_NULLABLE": "NO",
                "EXTRA": "auto_increment",
                "COLUMN_KEY": "PRI",
                "COLUMN_COMMENT": "",
            },
            {
                "COLUMN_NAME": "name",
                "COLUMN_TYPE": "varchar(255)",
                "COLUMN_DEFAULT": None,
                "IS_NULLABLE": "YES",
                "EXTRA": "",
                "COLUMN_KEY": "",
                "COLUMN_COMMENT": "",
            },
        ]
        # 创建要测试的类的实例
        new_engine = MysqlEngine(instance=self.ins1)
        # Mock self.query 方法
        new_engine.query = Mock()
        new_engine.query.side_effect = [
            Mock(rows=tables_result),  # 模拟 tbs 结果
            Mock(rows=columns_result),  # 模拟 columns 结果
        ]
        # 调用要测试的方法
        result = new_engine.get_tables_metas_data(db_name="test_db")

        # 断言返回结果是否符合预期
        expected_result = [
            {
                "ENGINE_KEYS": [
                    {"key": "COLUMN_NAME", "value": "字段名"},
                    {"key": "COLUMN_TYPE", "value": "数据类型"},
                    {"key": "COLUMN_DEFAULT", "value": "默认值"},
                    {"key": "IS_NULLABLE", "value": "允许非空"},
                    {"key": "EXTRA", "value": "自动递增"},
                    {"key": "COLUMN_KEY", "value": "是否主键"},
                    {"key": "COLUMN_COMMENT", "value": "备注"},
                ],
                "TABLE_INFO": {"TABLE_SCHEMA": "test_db", "TABLE_NAME": "test_table"},
                "COLUMNS": [
                    {
                        "COLUMN_NAME": "id",
                        "COLUMN_TYPE": "int",
                        "COLUMN_DEFAULT": None,
                        "IS_NULLABLE": "NO",
                        "EXTRA": "auto_increment",
                        "COLUMN_KEY": "PRI",
                        "COLUMN_COMMENT": "",
                    },
                    {
                        "COLUMN_NAME": "name",
                        "COLUMN_TYPE": "varchar(255)",
                        "COLUMN_DEFAULT": None,
                        "IS_NULLABLE": "YES",
                        "EXTRA": "",
                        "COLUMN_KEY": "",
                        "COLUMN_COMMENT": "",
                    },
                ],
            }
        ]

        self.assertEqual(result, expected_result)

    @patch.object(MysqlEngine, "query")
    def testAllDb(self, mock_query):
        db_result = ResultSet()
        db_result.rows = [("db_1",), ("db_2",)]
        mock_query.return_value = db_result
        new_engine = MysqlEngine(instance=self.ins1)
        dbs = new_engine.get_all_databases()
        self.assertEqual(dbs.rows, ["db_1", "db_2"])

    @patch.object(MysqlEngine, "query")
    def testAllTables(self, mock_query):
        table_result = ResultSet()
        table_result.rows = [("tb_1", "some_des"), ("tb_2", "some_des")]
        mock_query.return_value = table_result
        new_engine = MysqlEngine(instance=self.ins1)
        tables = new_engine.get_all_tables("some_db")
        mock_query.assert_called_once_with(db_name="some_db", sql=ANY)
        self.assertEqual(tables.rows, ["tb_1", "tb_2"])

    @patch.object(MysqlEngine, "query")
    def testAllColumns(self, mock_query):
        db_result = ResultSet()
        db_result.rows = [("col_1", "type"), ("col_2", "type2")]
        mock_query.return_value = db_result
        new_engine = MysqlEngine(instance=self.ins1)
        dbs = new_engine.get_all_columns_by_tb("some_db", "some_tb")
        self.assertEqual(dbs.rows, ["col_1", "col_2"])

    @patch.object(MysqlEngine, "query")
    def testDescribe(self, mock_query):
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.describe_table("some_db", "some_db")
        mock_query.assert_called_once()

    @patch.object(MysqlEngine, "query")
    def test_get_views_list(self, mock_query):
        r = ResultSet()
        r.rows = [("v1", "select 1"), ("v2", "select 2"), ("a_view", None)]
        mock_query.return_value = r
        engine = MysqlEngine(instance=self.ins1)
        data = engine.get_views_list(db_name="some_db")
        self.assertIn("v", data)
        self.assertIn("a", data)
        self.assertEqual(data["v"][0][0], "v1")

    @patch.object(MysqlEngine, "get_table_desc_data")
    @patch.object(MysqlEngine, "query")
    def test_get_view_detail(self, mock_query, mock_desc):
        r = ResultSet()
        r.column_list = [
            "view_name",
            "view_definition",
            "check_option",
            "is_updatable",
            "definer",
            "security_type",
            "character_set_client",
            "collation_connection",
        ]
        r.rows = [
            (
                "v1",
                "select 1",
                "NONE",
                "YES",
                "root@%",
                "DEFINER",
                "utf8",
                "utf8_general_ci",
            )
        ]
        mock_query.return_value = r
        mock_desc.return_value = {"column_list": [], "rows": []}
        engine = MysqlEngine(instance=self.ins1)
        data = engine.get_view_detail(db_name="some_db", view_name="v1")
        self.assertEqual(data["view_definition"], "select 1")
        self.assertIn("meta_data", data)
        self.assertIn("desc", data)

    @patch.object(MysqlEngine, "query")
    def test_get_triggers_list(self, mock_query):
        r = ResultSet()
        r.rows = [("tg1", "BEFORE", "INSERT", "t1")]
        mock_query.return_value = r
        engine = MysqlEngine(instance=self.ins1)
        data = engine.get_triggers_list(db_name="some_db")
        self.assertIn("t", data)
        self.assertEqual(data["t"][0][0], "tg1")
        self.assertIn("BEFORE", data["t"][0][1])

    @patch.object(MysqlEngine, "query")
    def test_get_trigger_detail(self, mock_query):
        r = ResultSet()
        r.column_list = [
            "trigger_name",
            "action_timing",
            "event_manipulation",
            "event_object_table",
            "action_orientation",
            "action_statement",
            "definer",
            "created",
            "sql_mode",
            "character_set_client",
            "collation_connection",
        ]
        r.rows = [
            (
                "tg1",
                "BEFORE",
                "INSERT",
                "t1",
                "ROW",
                "BEGIN END",
                "root@%",
                None,
                "",
                "utf8",
                "utf8",
            )
        ]
        mock_query.return_value = r
        engine = MysqlEngine(instance=self.ins1)
        data = engine.get_trigger_detail(db_name="some_db", trigger_name="tg1")
        self.assertIn("column_list", data)
        self.assertTrue(len(data["rows"]) > 0)

    @patch.object(MysqlEngine, "query")
    def test_get_procedures_list(self, mock_query):
        r = ResultSet()
        r.rows = [("p1", "comment1"), ("p2", "comment2")]
        mock_query.return_value = r
        engine = MysqlEngine(instance=self.ins1)
        data = engine.get_procedures_list(db_name="some_db")
        self.assertIn("p", data)
        self.assertEqual(len(data["p"]), 2)

    @patch.object(MysqlEngine, "query")
    def test_get_procedure_detail(self, mock_query):
        meta = ResultSet()
        meta.column_list = [
            "routine_name",
            "routine_schema",
            "definer",
            "created",
            "last_altered",
            "sql_mode",
            "security_type",
            "routine_comment",
        ]
        meta.rows = [("p1", "some_db", "root@%", None, None, "", "DEFINER", "")]
        create = ResultSet()
        create.rows = [("p1", "", "CREATE PROCEDURE p1() BEGIN END", "")]
        mock_query.side_effect = [meta, create]
        engine = MysqlEngine(instance=self.ins1)
        data = engine.get_procedure_detail(db_name="some_db", proc_name="p1")
        self.assertIn("meta_data", data)
        self.assertEqual(data["create_sql"], create.rows)

    @patch.object(MysqlEngine, "query")
    def test_get_functions_list(self, mock_query):
        r = ResultSet()
        r.rows = [("f1", "cmt"), ("f2", "cmt2")]
        mock_query.return_value = r
        engine = MysqlEngine(instance=self.ins1)
        data = engine.get_functions_list(db_name="some_db")
        self.assertIn("f", data)
        self.assertEqual(len(data["f"]), 2)

    @patch.object(MysqlEngine, "query")
    def test_get_function_detail(self, mock_query):
        meta = ResultSet()
        meta.column_list = [
            "routine_name",
            "routine_schema",
            "return_type",
            "definer",
            "created",
            "last_altered",
            "sql_mode",
            "security_type",
            "routine_comment",
        ]
        meta.rows = [("f1", "some_db", "int", "root@%", None, None, "", "DEFINER", "")]
        create = ResultSet()
        create.rows = [("f1", "", "CREATE FUNCTION f1() RETURNS INT RETURN 1", "", "")]
        mock_query.side_effect = [meta, create]
        engine = MysqlEngine(instance=self.ins1)
        data = engine.get_function_detail(db_name="some_db", func_name="f1")
        self.assertIn("meta_data", data)
        self.assertEqual(data["create_sql"], create.rows)

    @patch.object(MysqlEngine, "query")
    def test_get_events_list(self, mock_query):
        r = ResultSet()
        r.rows = [("e1", "ENABLED", "RECURRING", 1, "DAY")]
        mock_query.return_value = r
        engine = MysqlEngine(instance=self.ins1)
        data = engine.get_events_list(db_name="some_db")
        self.assertIn("e", data)
        self.assertIn("EVERY", data["e"][0][1])

    @patch.object(MysqlEngine, "query")
    def test_get_event_detail(self, mock_query):
        meta = ResultSet()
        meta.column_list = [
            "event_name",
            "event_schema",
            "definer",
            "event_type",
            "interval_value",
            "interval_field",
            "status",
            "execute_at",
            "starts",
            "ends",
            "last_executed",
            "on_completion",
            "created",
            "last_altered",
            "event_comment",
        ]
        meta.rows = [
            (
                "e1",
                "some_db",
                "root@%",
                "RECURRING",
                1,
                "DAY",
                "ENABLED",
                None,
                None,
                None,
                None,
                "NOT PRESERVE",
                None,
                None,
                "",
            )
        ]
        create = ResultSet()
        create.rows = [
            (
                "e1",
                "",
                "",
                "CREATE EVENT e1 ON SCHEDULE EVERY 1 DAY DO SELECT 1",
                "",
                "",
            )
        ]
        mock_query.side_effect = [meta, create]
        engine = MysqlEngine(instance=self.ins1)
        data = engine.get_event_detail(db_name="some_db", event_name="e1")
        self.assertIn("meta_data", data)
        self.assertEqual(data["create_sql"], create.rows)

    def testQueryCheck(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = "-- 测试\n select user from usertable"
        check_result = new_engine.query_check(db_name="some_db", sql=sql_without_limit)
        self.assertEqual(check_result["filtered_sql"], "select user from usertable")

    def test_query_check_wrong_sql(self):
        new_engine = MysqlEngine(instance=self.ins1)
        wrong_sql = "-- 测试"
        check_result = new_engine.query_check(db_name="some_db", sql=wrong_sql)
        self.assertDictEqual(
            check_result,
            {
                "msg": "不支持的查询语法类型!",
                "bad_query": True,
                "filtered_sql": "-- 测试",
                "has_star": False,
            },
        )

    def test_query_check_update_sql(self):
        new_engine = MysqlEngine(instance=self.ins1)
        update_sql = "update user set id=0"
        check_result = new_engine.query_check(db_name="some_db", sql=update_sql)
        self.assertDictEqual(
            check_result,
            {
                "msg": "不支持的查询语法类型!",
                "bad_query": True,
                "filtered_sql": "update user set id=0",
                "has_star": False,
            },
        )

    def test_filter_sql_with_delimiter(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = "select user from usertable;"
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=100)
        self.assertEqual(check_result, "select user from usertable limit 100;")

    def test_filter_sql_without_delimiter(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = "select user from usertable"
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=100)
        self.assertEqual(check_result, "select user from usertable limit 100;")

    def test_filter_sql_with_limit(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = "select user from usertable limit 10"
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, "select user from usertable limit 1;")

    def test_filter_sql_with_limit_min(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = "select user from usertable limit 10"
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=100)
        self.assertEqual(check_result, "select user from usertable limit 10;")

    def test_filter_sql_with_limit_offset(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = "select user from usertable limit 10 offset 100"
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, "select user from usertable limit 1 offset 100;")

    def test_filter_sql_with_limit_nn(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = "select user from usertable limit 10, 100"
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, "select user from usertable limit 10,1;")

    def test_filter_sql_upper(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = "SELECT USER FROM usertable LIMIT 10, 100"
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, "SELECT USER FROM usertable limit 10,1;")

    def test_filter_sql_not_select(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = "show create table usertable;"
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, "show create table usertable;")

    @patch("sql.engines.mysql.data_masking", return_value=ResultSet())
    def test_query_masking(self, _data_masking):
        query_result = ResultSet()
        new_engine = MysqlEngine(instance=self.ins1)
        masking_result = new_engine.query_masking(
            db_name="archery", sql="select 1", resultset=query_result
        )
        self.assertIsInstance(masking_result, ResultSet)

    @patch("sql.engines.mysql.data_masking", return_value=ResultSet())
    def test_query_masking_not_select(self, _data_masking):
        query_result = ResultSet()
        new_engine = MysqlEngine(instance=self.ins1)
        masking_result = new_engine.query_masking(
            db_name="archery", sql="explain select 1", resultset=query_result
        )
        self.assertEqual(masking_result, query_result)

    @patch("sql.engines.mysql.GoInceptionEngine")
    def test_execute_check_select_sql(self, _inception_engine):
        sql = "select * from user"
        inc_row = ReviewResult(
            id=1,
            errlevel=0,
            stagestatus="Audit completed",
            errormessage="None",
            sql=sql,
            affected_rows=0,
            execute_time="",
        )
        row = ReviewResult(
            id=1,
            errlevel=2,
            stagestatus="驳回不支持语句",
            errormessage="仅支持DML和DDL语句，查询语句请使用SQL查询功能！",
            sql=sql,
        )
        _inception_engine.return_value.execute_check.return_value = ReviewSet(
            full_sql=sql, rows=[inc_row]
        )
        new_engine = MysqlEngine(instance=self.ins1)
        config = {
            "goinception": "true",
            "critical_ddl_regex": "",
            "ddl_dml_separation": False,
        }
        new_engine.config.get = Mock(
            side_effect=lambda key, default=None: config.get(key, default)
        )
        check_result = new_engine.execute_check(db_name="archery", sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch("sql.engines.mysql.GoInceptionEngine")
    def test_execute_check_critical_sql(self, _inception_engine):
        sql = "update user set id=1"
        inc_row = ReviewResult(
            id=1,
            errlevel=0,
            stagestatus="Audit completed",
            errormessage="None",
            sql=sql,
            affected_rows=0,
            execute_time="",
        )
        row = ReviewResult(
            id=1,
            errlevel=2,
            stagestatus="驳回高危SQL",
            errormessage="禁止提交匹配" + "^|update" + "条件的语句！",
            sql=sql,
        )
        _inception_engine.return_value.execute_check.return_value = ReviewSet(
            full_sql=sql, rows=[inc_row]
        )
        new_engine = MysqlEngine(instance=self.ins1)
        config = {
            "goinception": "true",
            "critical_ddl_regex": "^|update",
            "ddl_dml_separation": False,
        }
        new_engine.config.get = Mock(
            side_effect=lambda key, default=None: config.get(key, default)
        )
        check_result = new_engine.execute_check(db_name="archery", sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch("sql.engines.mysql.GoInceptionEngine")
    def test_execute_check_normal_sql(self, _inception_engine):
        sql = "update user set id=1"
        row = ReviewResult(
            id=1,
            errlevel=0,
            stagestatus="Audit completed",
            errormessage="None",
            sql=sql,
            affected_rows=0,
            execute_time=0,
        )
        _inception_engine.return_value.execute_check.return_value = ReviewSet(
            full_sql=sql, rows=[row]
        )
        new_engine = MysqlEngine(instance=self.ins1)
        config = {
            "goinception": "true",
            "critical_ddl_regex": "",
            "ddl_dml_separation": False,
        }
        new_engine.config.get = Mock(
            side_effect=lambda key, default=None: config.get(key, default)
        )
        check_result = new_engine.execute_check(db_name="archery", sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch("sql.engines.mysql.GoInceptionEngine")
    def test_execute_check_normal_sql_with_Exception(self, _inception_engine):
        sql = "update user set id=1"
        _inception_engine.return_value.execute_check.side_effect = RuntimeError()
        new_engine = MysqlEngine(instance=self.ins1)
        with self.assertRaises(RuntimeError):
            new_engine.execute_check(db_name=0, sql=sql)

    @patch.object(MysqlEngine, "query")
    @patch("sql.engines.mysql.GoInceptionEngine")
    def test_execute_workflow(self, _inception_engine, _query):
        sql = "update user set id=1"
        _inception_engine.return_value.execute.return_value = ReviewSet(full_sql=sql)
        _query.return_value.rows = (("0",),)
        new_engine = MysqlEngine(instance=self.ins1)
        execute_result = new_engine.execute_workflow(self.wf)
        self.assertIsInstance(execute_result, ReviewSet)

    @patch("MySQLdb.connect.cursor.execute")
    @patch("MySQLdb.connect.cursor")
    @patch("MySQLdb.connect")
    def test_execute(self, _connect, _cursor, _execute):
        new_engine = MysqlEngine(instance=self.ins1)
        execute_result = new_engine.execute(self.wf)
        self.assertIsInstance(execute_result, ResultSet)

    @patch("MySQLdb.connect")
    def test_server_version(self, _connect):
        _connect.return_value.get_server_info.return_value = "5.7.20-16log"
        new_engine = MysqlEngine(instance=self.ins1)
        server_version = new_engine.server_version
        self.assertTupleEqual(server_version, (5, 7, 20))

    @patch.object(MysqlEngine, "query")
    def test_get_variables_not_filter(self, _query):
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.get_variables()
        _query.assert_called_once()

    @patch("MySQLdb.connect")
    @patch.object(MysqlEngine, "query")
    def test_get_variables_filter(self, _query, _connect):
        _connect.return_value.get_server_info.return_value = "5.7.20-16log"
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.get_variables(variables=["binlog_format"])
        _query.assert_called_once_with(
            sql="show global variables where variable_name in (%s);",
            parameters=("binlog_format",),
        )

    @patch.object(MysqlEngine, "query")
    def test_set_variable(self, _query):
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.set_variable("binlog_format", "ROW")
        _query.assert_called_once_with(
            sql="set global binlog_format=%s;", parameters=("ROW",)
        )

        _query.reset_mock()
        result = new_engine.set_variable("binlog_format;drop user u", "ROW")
        self.assertEqual(result.error, "参数名称不合法")
        _query.assert_not_called()

    @patch("sql.engines.mysql.GoInceptionEngine")
    def test_osc_go_inception(self, _inception_engine):
        _inception_engine.return_value.osc_control.return_value = ReviewSet()
        command = "get"
        sqlsha1 = "xxxxx"
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.osc_control(sqlsha1=sqlsha1, command=command)

    @patch("sql.engines.mysql.GoInceptionEngine")
    def test_osc_inception(self, _inception_engine):
        _inception_engine.return_value.osc_control.return_value = ReviewSet()
        command = "get"
        sqlsha1 = "xxxxx"
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.osc_control(sqlsha1=sqlsha1, command=command)

    @patch.object(MysqlEngine, "query")
    def test_kill_connection(self, _query):
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.kill_connection(100)
        _query.assert_called_once_with(sql="kill %s", parameters=(100,))

    @patch("MySQLdb.connect")
    @patch.object(MysqlEngine, "query")
    def test_seconds_behind_master(self, _query, mock_connect):
        # Mock 连接以避免实际连接尝试
        mock_conn = Mock()
        mock_conn.get_server_info.return_value = "8.0.0"
        mock_conn.thread_id.return_value = 12345
        mock_connect.return_value = mock_conn

        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.seconds_behind_master
        _query.assert_called_once_with(
            sql="show slave status",
            close_conn=False,
            cursorclass=MySQLdb.cursors.DictCursor,
        )

    @patch.object(MysqlEngine, "query")
    def test_processlist(self, _query):
        new_engine = MysqlEngine(instance=self.ins1)
        _query.return_value = ResultSet()
        for command_type in ["Query", "All", "Not Sleep"]:
            r = new_engine.processlist(command_type)
            self.assertIsInstance(r, ResultSet)

    @patch.object(MysqlEngine, "query")
    def test_get_kill_command(self, _query):
        new_engine = MysqlEngine(instance=self.ins1)
        _query.return_value.rows = (("kill 1;",), ("kill 2;",))
        r = new_engine.get_kill_command([1, 2])
        self.assertEqual(r, "kill 1;kill 2;")

    @patch("MySQLdb.connect.cursor.execute")
    @patch("MySQLdb.connect.cursor")
    @patch("MySQLdb.connect")
    @patch.object(MysqlEngine, "query")
    def test_kill(self, _query, _connect, _cursor, _execute):
        new_engine = MysqlEngine(instance=self.ins1)
        _query.return_value.rows = (("kill 1;",), ("kill 2;",))
        _execute.return_value = ResultSet()
        r = new_engine.kill([1, 2])
        self.assertIsInstance(r, ResultSet)

    @patch.object(MysqlEngine, "query")
    def test_tablespace(self, _query):
        new_engine = MysqlEngine(instance=self.ins1)
        _query.return_value = ResultSet()
        r = new_engine.tablespace()
        self.assertIsInstance(r, ResultSet)

    @patch.object(MysqlEngine, "query")
    def test_tablespace_count(self, _query):
        new_engine = MysqlEngine(instance=self.ins1)
        _query.return_value = ResultSet()
        r = new_engine.tablespace_count()
        self.assertIsInstance(r, ResultSet)

    @patch.object(MysqlEngine, "query")
    @patch("MySQLdb.connect")
    def test_trxandlocks(self, _connect, _query):
        new_engine = MysqlEngine(instance=self.ins1)
        _connect.return_value = Mock()
        for v in ["5.7.0", "8.0.1"]:
            _connect.return_value.get_server_info.return_value = v
            _query.return_value = ResultSet()
            r = new_engine.trxandlocks()
            self.assertIsInstance(r, ResultSet)

    @patch.object(MysqlEngine, "query")
    def test_get_long_transaction(self, _query):
        new_engine = MysqlEngine(instance=self.ins1)
        _query.return_value = ResultSet()
        r = new_engine.get_long_transaction()
        self.assertIsInstance(r, ResultSet)

    @patch.object(MysqlEngine, "get_bind_users")
    @patch.object(MysqlEngine, "query")
    def test_get_all_databases_summary(self, _query, _get_bind_users):
        db_result1 = ResultSet()
        db_result1.rows = [("some_db", "utf8mb4", "utf8mb4_general_ci")]
        _query.return_value = db_result1
        _get_bind_users.return_value = [("'some_user'@'%'", "cooperate_sign")]
        new_engine = MysqlEngine(instance=self.ins1)
        dbs = new_engine.get_all_databases_summary()
        self.assertEqual(
            dbs.rows,
            [
                {
                    "db_name": "some_db",
                    "charset": "utf8mb4",
                    "collation": "utf8mb4_general_ci",
                    "grantees": ["'some_user'@'%'"],
                    "saved": False,
                }
            ],
        )

    @patch("MySQLdb.connect")
    @patch.object(MysqlEngine, "query")
    def test_get_instance_users_summary(self, _query, _connect):
        result = ResultSet()
        result.error = "query error"
        _query.return_value = result
        new_engine = MysqlEngine(instance=self.ins1)
        user_summary = new_engine.get_instance_users_summary()
        self.assertEqual(user_summary.error, "query error")

        result_with_lock = ResultSet()
        result_with_lock.rows = [("root", "localhost", "N")]
        _query.return_value = result_with_lock
        _connect.return_value.get_server_info.return_value = "5.7.20-16log"
        self.assertTupleEqual(new_engine.server_version, (5, 7, 20))
        user_summary_with_lock = new_engine.get_instance_users_summary()
        self.assertEqual(
            user_summary_with_lock.rows,
            [
                {
                    "host": "localhost",
                    "is_locked": "N",
                    "privileges": [("root", "localhost", "N")],
                    "saved": False,
                    "user": "root",
                    "user_host": "`root`@`localhost`",
                }
            ],
        )

    @patch("MySQLdb.connect")
    @patch.object(MysqlEngine, "query")
    def test_get_instance_users_summary_without_lock(self, _query, _connect):
        result_without_lock = ResultSet()
        result_without_lock.rows = [("root", "localhost")]
        _query.return_value = result_without_lock
        mysql_engine = MysqlEngine(instance=self.ins1)
        _connect.return_value.get_server_info.return_value = "5.7.5-16log"
        self.assertTupleEqual(mysql_engine.server_version, (5, 7, 5))
        user_summary_without_lock = mysql_engine.get_instance_users_summary()
        self.assertEqual(
            user_summary_without_lock.rows,
            [
                {
                    "host": "localhost",
                    "is_locked": None,
                    "privileges": [("root", "localhost")],
                    "saved": False,
                    "user": "root",
                    "user_host": "`root`@`localhost`",
                }
            ],
        )

    @patch("MySQLdb.connect")
    @patch.object(MysqlEngine, "execute")
    def test_create_instance_user(self, _execute, _connect):
        _execute.return_value = ResultSet()
        new_engine = MysqlEngine(instance=self.ins1)
        result = new_engine.create_instance_user(
            user="some_user", host="%", password1="123456", remark=""
        )
        self.assertEqual(
            result.rows,
            [
                {
                    "instance": self.ins1,
                    "user": "some_user",
                    "host": "%",
                    "password": "123456",
                    "remark": "",
                }
            ],
        )

    def test_auto_backup(self):
        new_engine = MysqlEngine(instance=self.ins1)
        self.assertTrue(new_engine.auto_backup)

    @patch("schemaobject.SchemaObject")
    @patch("sql.engines.mysql.build_database_url")
    def test_schema_object(self, build_database_url, schema_object):
        build_database_url.return_value = "mysql://some_host:1366"
        new_engine = MysqlEngine(instance=self.ins1)

        self.assertEqual(new_engine.schema_object, schema_object.return_value)
        build_database_url.assert_called_once_with(
            host="some_host",
            username="ins_user",
            password="some_str",
            port=1366,
        )
        schema_object.assert_called_once_with(
            "mysql://some_host:1366", charset="utf8mb4"
        )

    @patch("MySQLdb.connect")
    def test_server_info_and_fork_type(self, connect):
        connect.return_value.get_server_info.return_value = "10.4.2-MariaDB"
        engine = MysqlEngine(instance=self.ins1)

        self.assertEqual(engine.server_info, "10.4.2-MariaDB")
        self.assertEqual(engine.server_fork_type, MysqlForkType.MARIADB)
        self.assertEqual(engine.server_info, "10.4.2-MariaDB")
        connect.return_value.get_server_info.assert_called_once()

    @patch("MySQLdb.connect")
    def test_server_version_with_missing_numeric_part(self, connect):
        connect.return_value.get_server_info.return_value = "8.0.rc"
        engine = MysqlEngine(instance=self.ins1)

        self.assertTupleEqual(engine.server_version, (8, 0, None))

    @patch.object(MysqlEngine, "query")
    def test_seconds_behind_master_uses_replica_status_and_empty_result(self, query):
        query.return_value = ResultSet(rows=[])
        engine = MysqlEngine(instance=self.ins1)
        engine._server_version = (8, 4, 0)
        engine._server_info = "8.4.0"

        self.assertIsNone(engine.seconds_behind_master)
        query.assert_called_once_with(
            sql="show replica status",
            close_conn=False,
            cursorclass=MySQLdb.cursors.DictCursor,
        )

    @patch.object(MysqlEngine, "query")
    def test_get_group_tables_by_db(self, query):
        query.return_value = ResultSet(rows=[("alpha", "c1"), ("beta", "c2")])
        engine = MysqlEngine(instance=self.ins1)

        self.assertEqual(
            engine.get_group_tables_by_db("some_db"),
            {"a": [["alpha", "c1"]], "b": [["beta", "c2"]]},
        )

    @patch.object(MysqlEngine, "query")
    def test_table_detail_helpers(self, query):
        query.return_value = ResultSet(column_list=["c1"], rows=[("row",)])
        engine = MysqlEngine(instance=self.ins1)

        self.assertEqual(
            engine.get_table_meta_data("some_db", "some_tb"),
            {"column_list": ["c1"], "rows": ("row",)},
        )
        self.assertEqual(
            engine.get_table_desc_data("some_db", "some_tb"),
            {"column_list": ["c1"], "rows": [("row",)]},
        )
        self.assertEqual(
            engine.get_table_index_data("some_db", "some_tb"),
            {"column_list": ["c1"], "rows": [("row",)]},
        )

    @patch.object(MysqlEngine, "query")
    def test_get_events_list_one_time(self, query):
        query.return_value = ResultSet(
            rows=[("e1", "DISABLED", "ONE TIME", None, None)]
        )
        engine = MysqlEngine(instance=self.ins1)

        self.assertEqual(
            engine.get_events_list("some_db"),
            {"e": [["e1", "DISABLED ONE TIME"]]},
        )

    def test_result_set_binary_as_hex(self):
        result_set = ResultSet(
            rows=[(b"\x0f", "plain"), (None, "empty")],
            column_type=["BLOB", "VARCHAR"],
        )

        result = MysqlEngine.result_set_binary_as_hex(result_set)

        self.assertEqual(result.rows, (["0f", "plain"], [None, "empty"]))

    @patch("MySQLdb.connect")
    def test_query_fetchall_binary_and_max_execution_time_fallback(self, connect):
        cursor = Mock()
        cursor.execute.side_effect = [MySQLdb.OperationalError(), 2]
        cursor.fetchall.return_value = [(b"\x0a",)]
        cursor.description = (("payload", 252),)
        connect.return_value.cursor.return_value = cursor
        engine = MysqlEngine(instance=self.ins1)

        result = engine.query(sql="select payload from t", binary_as_hex=True)

        self.assertEqual(result.column_type, ["BLOB"])
        self.assertEqual(result.rows, (["0a"],))
        self.assertEqual(result.affected_rows, 2)

    @patch.object(MysqlEngine, "get_connection", side_effect=RuntimeError("boom"))
    def test_query_connection_error(self, _get_connection):
        engine = MysqlEngine(instance=self.ins1)

        result = engine.query(sql="select 1")

        self.assertEqual(result.error, "boom")

    @patch.object(MysqlEngine, "query")
    def test_query_check_empty_star_explain_and_forbidden_user(self, query):
        engine = MysqlEngine(instance=self.ins1)
        query.return_value = ResultSet()
        query.return_value.error = "syntax error"

        empty_result = engine.query_check(sql="-- only comment")
        self.assertTrue(empty_result["bad_query"])
        self.assertEqual(empty_result["msg"], "不支持的查询语法类型!")
        self.assertEqual(
            engine.query_check(sql="select * from t")["msg"], "syntax error"
        )

        query.return_value.error = None
        forbidden = engine.query_check(db_name="mysql", sql="select id from user")
        self.assertTrue(forbidden["bad_query"])
        self.assertEqual(forbidden["msg"], "您无权查看该表")

        forbidden = engine.query_check(
            db_name="information_schema", sql="select * from user_privileges"
        )
        self.assertTrue(forbidden["bad_query"])
        self.assertEqual(forbidden["msg"], "您无权查看该表")

        forbidden = engine.query_check(sql="show grants for `u`@`%`")
        self.assertTrue(forbidden["bad_query"])
        self.assertEqual(forbidden["msg"], "您无权查看该表")

    @patch("sql.engines.mysql.GoInceptionEngine")
    def test_execute_check_inception_error_and_ddl_dml_separation(self, inception):
        check_error = ReviewSet()
        check_error.error = "check error"
        inception.return_value.execute_check.return_value = check_error
        engine = MysqlEngine(instance=self.ins1)

        with self.assertRaises(RuntimeError):
            engine.execute_check(db_name="archery", sql="update user set id=1")

        rows = [
            ReviewResult(id=1, sql="create table t(id int)"),
            ReviewResult(id=2, sql="insert into t values(1)"),
        ]
        inception.return_value.execute_check.return_value = ReviewSet(rows=rows)
        config = {"critical_ddl_regex": "", "ddl_dml_separation": True}
        engine = MysqlEngine(instance=self.ins1)
        engine.config.get = Mock(
            side_effect=lambda key, default=None: config.get(key, default)
        )

        result = engine.execute_check(
            db_name="archery",
            sql="create table t(id int);insert into t values(1);",
        )

        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.rows[1].errormessage, "DDL语句和DML语句不能同时执行！")

    @patch("sql.engines.mysql.GoInceptionEngine")
    def test_execute_check_rejects_critical_regex_timeout(self, inception):
        rows = [ReviewResult(id=1, sql="update user set id=1")]
        inception.return_value.execute_check.return_value = ReviewSet(rows=rows)
        engine = MysqlEngine(instance=self.ins1)
        config = {"critical_ddl_regex": "(a+)+$", "ddl_dml_separation": False}
        engine.config.get = Mock(
            side_effect=lambda key, default=None: config.get(key, default)
        )

        with patch.object(engine, "_compile_safe_regex") as compile_safe_regex:
            compiled = Mock()
            compiled.match.side_effect = TimeoutError()
            compile_safe_regex.return_value = compiled
            result = engine.execute_check(db_name="archery", sql="update user set id=1")

        self.assertEqual(result.error_count, 1)
        self.assertEqual(
            result.rows[0].errormessage,
            "critical_ddl_regex匹配超时，已拒绝执行以避免ReDoS",
        )

    @patch("sql.engines.mysql.GoInceptionEngine")
    def test_execute_check_rejects_invalid_critical_regex(self, inception):
        rows = [ReviewResult(id=1, sql="update user set id=1")]
        inception.return_value.execute_check.return_value = ReviewSet(rows=rows)
        engine = MysqlEngine(instance=self.ins1)
        config = {"critical_ddl_regex": "[", "ddl_dml_separation": False}
        engine.config.get = Mock(
            side_effect=lambda key, default=None: config.get(key, default)
        )

        result = engine.execute_check(db_name="archery", sql="update user set id=1")

        self.assertEqual(result.error_count, 1)
        self.assertIn("critical_ddl_regex配置不合法", result.rows[0].errormessage)

    @patch.object(MysqlEngine, "query")
    def test_execute_workflow_read_only(self, query):
        query.return_value = ResultSet(rows=[("ON",)])
        engine = MysqlEngine(instance=self.ins1)

        result = engine.execute_workflow(self.wf)

        self.assertEqual(result.error, ("实例read_only=1，禁止执行变更语句!",))
        self.assertEqual(result.rows[0].sql, "update user set id=1")

    @patch.object(MysqlEngine, "get_connection")
    def test_execute_error(self, get_connection):
        cursor = Mock()
        cursor.execute.side_effect = RuntimeError("execute failed")
        get_connection.return_value.cursor.return_value = cursor
        engine = MysqlEngine(instance=self.ins1)

        result = engine.execute(sql="select 1")

        self.assertEqual(result.error, "execute failed")

    @patch("sql.engines.mysql.GoInceptionEngine")
    def test_get_rollback(self, inception):
        inception.return_value.get_rollback.return_value = ReviewSet()
        engine = MysqlEngine(instance=self.ins1)

        self.assertIsInstance(engine.get_rollback(self.wf), ReviewSet)

    @patch.object(MysqlEngine, "query")
    def test_processlist_empty_and_escaped_command(self, query):
        query.return_value = ResultSet()
        engine = MysqlEngine(instance=self.ins1)

        engine.processlist("")
        engine.processlist("Query'")

        self.assertIn("command=%s;", query.call_args_list[0].args[1])
        self.assertEqual(query.call_args_list[0].kwargs["parameters"], ("Query",))
        self.assertIn("command=%s;", query.call_args_list[1].args[1])
        self.assertEqual(query.call_args_list[1].kwargs["parameters"], ("Query'",))

    @patch.object(MysqlEngine, "query")
    def test_get_kill_command_and_kill_reject_invalid_ids(self, query):
        engine = MysqlEngine(instance=self.ins1)

        self.assertIsNone(engine.get_kill_command([1, "2"]))
        result = engine.kill([1, "2"])

        self.assertIsInstance(result, ResultSet)
        query.assert_not_called()

    @patch.object(MysqlEngine, "query")
    def test_tablespace_search_filters_are_escaped(self, query):
        query.return_value = ResultSet()
        engine = MysqlEngine(instance=self.ins1)

        engine.tablespace(schema_search="app_'")
        engine.tablespace_count(schema_search="app_'")

        self.assertIn("table_schema LIKE %s", query.call_args_list[0].args[1])
        self.assertEqual(
            query.call_args_list[0].kwargs["parameters"],
            ("%app_'%", "%app_'%", 0, 14),
        )
        self.assertIn("table_schema LIKE %s", query.call_args_list[1].args[1])
        self.assertEqual(
            query.call_args_list[1].kwargs["parameters"], ("%app_'%", "%app_'%")
        )

    @patch.object(MysqlEngine, "query")
    def test_trxandlocks_uses_performance_schema_for_mysql_8(self, query):
        query.return_value = ResultSet()
        engine = MysqlEngine(instance=self.ins1)
        engine._server_version = (8, 0, 1)

        engine.trxandlocks()

        self.assertIn("performance_schema.`data_locks`", query.call_args.args[1])

    @patch("MySQLdb.connect")
    @patch.object(MysqlEngine, "query")
    def test_get_instance_users_summary_fallback_without_lock(self, query, connect):
        connect.return_value.get_server_info.return_value = "8.0.0"
        failed = ResultSet()
        failed.error = "unknown column account_locked"
        fallback = ResultSet(rows=[("u", "%")])
        grants = ResultSet(rows=[("grant usage",)])
        query.side_effect = [failed, fallback, grants]
        engine = MysqlEngine(instance=self.ins1)

        result = engine.get_instance_users_summary()

        self.assertIsNone(result.rows[0]["is_locked"])
        self.assertEqual(result.rows[0]["privileges"], [("grant usage",)])

    @patch.object(MysqlEngine, "execute")
    def test_drop_and_reset_instance_user(self, execute):
        execute.return_value = ResultSet()
        engine = MysqlEngine(instance=self.ins1)

        engine.drop_instance_user("`u`@`%`")
        engine.reset_instance_user_pwd("`u`@`%`", "new'pwd")

        self.assertEqual(execute.call_args_list[0].kwargs["sql"], "DROP USER `u`@`%`;")
        self.assertIn("new\\'pwd", execute.call_args_list[1].kwargs["sql"])

        execute.reset_mock()
        result = engine.drop_instance_user("`u`@`%`;DROP USER `x`@`%`")
        self.assertEqual(result.error, "账号格式不合法")
        execute.assert_not_called()

    @patch.object(MysqlEngine, "execute")
    def test_create_instance_user_multiple_hosts(self, execute):
        execute.return_value = ResultSet()
        engine = MysqlEngine(instance=self.ins1)

        result = engine.create_instance_user(
            user="some_user",
            host="%|localhost",
            password1="123456",
            remark="multi",
        )

        self.assertEqual([row["host"] for row in result.rows], ["%", "localhost"])
        self.assertIn("`some_user`@`%`", execute.call_args.kwargs["sql"])
        self.assertIn("`some_user`@`localhost`", execute.call_args.kwargs["sql"])

    @patch.object(MysqlEngine, "execute")
    def test_instance_user_privilege_sql_is_validated_and_quoted(self, execute):
        execute.return_value = ResultSet()
        engine = MysqlEngine(instance=self.ins1)

        result = engine.grant_instance_user(
            user_host="`u`@`%`",
            op_type=0,
            priv_type=1,
            privs={"db_privs": ["SELECT", "GRANT"]},
            db_names=["app`db"],
        )

        self.assertIsNone(result.error)
        self.assertEqual(
            execute.call_args.kwargs["sql"],
            "GRANT SELECT,GRANT OPTION ON `app``db`.* TO `u`@`%`;",
        )

        execute.reset_mock()
        result = engine.grant_instance_user(
            user_host="`u`@`%`",
            op_type=0,
            priv_type=1,
            privs={"db_privs": ["SELECT;DROP USER"]},
            db_names=["app"],
        )

        self.assertEqual(result.error, "权限项不合法")
        execute.assert_not_called()

    @patch.object(MysqlEngine, "execute")
    def test_instance_user_lock_rejects_injected_user_host(self, execute):
        execute.return_value = ResultSet()
        engine = MysqlEngine(instance=self.ins1)

        result = engine.set_instance_user_lock("`u`@`%`", "N")

        self.assertIsNone(result.error)
        self.assertEqual(
            execute.call_args.kwargs["sql"], "ALTER USER `u`@`%` ACCOUNT LOCK;"
        )

        execute.reset_mock()
        result = engine.set_instance_user_lock("`u`@`%`;DROP USER `x`@`%`", "N")

        self.assertEqual(result.error, "账号格式不合法")
        execute.assert_not_called()

    @patch("sql.instance_account.get_engine")
    @patch("sql.instance_account.user_instances")
    def test_mysql_grant_view_delegates_to_engine_safe_method(
        self, user_instances, get_engine
    ):
        request = RequestFactory().post(
            "/instance/user/grant/",
            data={
                "instance_id": "1",
                "user_host": "`u`@`%`",
                "op_type": "0",
                "priv_type": "1",
                "privs": json.dumps(
                    {
                        "global_privs": [],
                        "db_privs": ["SELECT"],
                        "tb_privs": [],
                        "col_privs": [],
                    }
                ),
                "db_name[]": ["app"],
            },
        )
        request.user = Mock()
        request.user.has_perms.return_value = True
        instance = Instance(id=1, db_type="mysql")
        user_instances.return_value.get.return_value = instance
        engine = Mock()
        engine.grant_instance_user.return_value = ResultSet(
            full_sql="GRANT SELECT ON `app`.* TO `u`@`%`;"
        )
        get_engine.return_value = engine

        response = instance_account.grant(request)
        data = json.loads(response.content)

        self.assertEqual(data["status"], 0)
        self.assertEqual(data["data"], "GRANT SELECT ON `app`.* TO `u`@`%`;")
        engine.grant_instance_user.assert_called_once_with(
            user_host="`u`@`%`",
            op_type="0",
            priv_type="1",
            privs={
                "global_privs": [],
                "db_privs": ["SELECT"],
                "tb_privs": [],
                "col_privs": [],
            },
            db_names=["app"],
            tb_names=None,
            col_names=[],
        )
        engine.execute.assert_not_called()

    @patch("sql.instance_account.get_engine")
    @patch("sql.instance_account.user_instances")
    def test_mysql_lock_view_delegates_to_engine_safe_method(
        self, user_instances, get_engine
    ):
        request = RequestFactory().post(
            "/instance/user/lock/",
            data={"instance_id": "1", "user_host": "`u`@`%`", "is_locked": "N"},
        )
        request.user = Mock()
        request.user.has_perms.return_value = True
        instance = Instance(id=1, db_type="mysql")
        user_instances.return_value.get.return_value = instance
        engine = Mock()
        engine.set_instance_user_lock.return_value = ResultSet()
        get_engine.return_value = engine

        response = instance_account.lock(request)
        data = json.loads(response.content)

        self.assertEqual(data["status"], 0)
        engine.set_instance_user_lock.assert_called_once_with(
            user_host="`u`@`%`", is_locked="N"
        )
        engine.execute.assert_not_called()

    # ------------------------------------------------------------------ #
    #  _quote_identifier / _quote_literal / _quote_account_part 错误分支   #
    # ------------------------------------------------------------------ #
    def test_quote_identifier_errors(self):
        with self.assertRaises(ValueError):
            MysqlEngine._quote_identifier(None)
        with self.assertRaises(ValueError):
            MysqlEngine._quote_identifier("")
        with self.assertRaises(ValueError):
            MysqlEngine._quote_identifier("ab\x00cd")

    def test_quote_literal_errors(self):
        with self.assertRaises(ValueError):
            MysqlEngine._quote_literal(None)
        with self.assertRaises(ValueError):
            MysqlEngine._quote_literal("ab\x00cd")

    def test_quote_account_part_errors(self):
        with self.assertRaises(ValueError):
            MysqlEngine._quote_account_part(None)
        with self.assertRaises(ValueError):
            MysqlEngine._quote_account_part("ab\x00cd")

    # ------------------------------------------------------------------ #
    #  _parse_account_part 各种引号/转义/边界                               #
    # ------------------------------------------------------------------ #
    def test_parse_account_part_unquoted(self):
        value, pos = MysqlEngine._parse_account_part("user@host", 0)
        self.assertEqual(value, "user")
        self.assertEqual(pos, 4)

    def test_parse_account_part_leading_space(self):
        value, pos = MysqlEngine._parse_account_part("  user@host", 0)
        self.assertEqual(value, "user")

    def test_parse_account_part_empty_after_space(self):
        with self.assertRaises(ValueError):
            MysqlEngine._parse_account_part("   ", 0)

    def test_parse_account_part_unquoted_empty_value(self):
        with self.assertRaises(ValueError):
            MysqlEngine._parse_account_part("@host", 0)

    def test_parse_account_part_backtick_escaped(self):
        # `us``er` -> user with embedded backtick
        value, pos = MysqlEngine._parse_account_part("`us``er`@host", 0)
        self.assertEqual(value, "us`er")

    def test_parse_account_part_single_quoted(self):
        value, pos = MysqlEngine._parse_account_part("'user'@host", 0)
        self.assertEqual(value, "user")

    def test_parse_account_part_single_quoted_escaped_backslash(self):
        # 'us\'er' -> us'er (backslash escape for single-quoted)
        value, pos = MysqlEngine._parse_account_part("'us\\'er'@host", 0)
        self.assertEqual(value, "us'er")

    def test_parse_account_part_single_quoted_doubled(self):
        # 'us''er' -> us'er (doubled quote escape)
        value, pos = MysqlEngine._parse_account_part("'us''er'@host", 0)
        self.assertEqual(value, "us'er")

    def test_parse_account_part_double_quoted(self):
        value, pos = MysqlEngine._parse_account_part('"user"@host', 0)
        self.assertEqual(value, "user")

    def test_parse_account_part_double_quoted_escaped_backslash(self):
        value, pos = MysqlEngine._parse_account_part('"us\\"er"@host', 0)
        self.assertEqual(value, 'us"er')

    def test_parse_account_part_double_quoted_doubled(self):
        value, pos = MysqlEngine._parse_account_part('"us""er"@host', 0)
        self.assertEqual(value, 'us"er')

    def test_parse_account_part_unterminated_quote(self):
        with self.assertRaises(ValueError):
            MysqlEngine._parse_account_part("'user", 0)

    # ------------------------------------------------------------------ #
    #  _parse_user_host 边界                                              #
    # ------------------------------------------------------------------ #
    def test_parse_user_host_none(self):
        with self.assertRaises(ValueError):
            MysqlEngine._parse_user_host(None)

    def test_parse_user_host_no_at(self):
        with self.assertRaises(ValueError):
            MysqlEngine._parse_user_host("user_only")

    def test_parse_user_host_trailing_garbage(self):
        with self.assertRaises(ValueError):
            MysqlEngine._parse_user_host("`u`@`%` extra")

    # ------------------------------------------------------------------ #
    #  _coerce_int 错误分支                                               #
    # ------------------------------------------------------------------ #
    def test_coerce_int_bool_rejected(self):
        with self.assertRaises(ValueError):
            MysqlEngine._coerce_int(True, "test")

    def test_coerce_int_non_numeric(self):
        with self.assertRaises(ValueError):
            MysqlEngine._coerce_int("abc", "test")

    def test_coerce_int_below_minimum(self):
        with self.assertRaises(ValueError):
            MysqlEngine._coerce_int(-1, "test", minimum=0)

    # ------------------------------------------------------------------ #
    #  _validate_thread_ids 错误分支                                       #
    # ------------------------------------------------------------------ #
    def test_validate_thread_ids_not_list(self):
        with self.assertRaises(ValueError):
            MysqlEngine._validate_thread_ids("not_a_list")

    def test_validate_thread_ids_bool_element(self):
        with self.assertRaises(ValueError):
            MysqlEngine._validate_thread_ids([True])

    def test_validate_thread_ids_string_element(self):
        with self.assertRaises(ValueError):
            MysqlEngine._validate_thread_ids([1, "2"])

    # ------------------------------------------------------------------ #
    #  _normalize_privileges                                              #
    # ------------------------------------------------------------------ #
    def test_normalize_privileges_empty(self):
        with self.assertRaises(ValueError):
            MysqlEngine._normalize_privileges([], MysqlEngine.GLOBAL_PRIVILEGES)

    def test_normalize_privileges_none(self):
        with self.assertRaises(ValueError):
            MysqlEngine._normalize_privileges(None, MysqlEngine.GLOBAL_PRIVILEGES)

    # ------------------------------------------------------------------ #
    #  _as_list 边界                                                      #
    # ------------------------------------------------------------------ #
    def test_as_list_none(self):
        self.assertEqual(MysqlEngine._as_list(None), [])

    def test_as_list_single_value(self):
        self.assertEqual(MysqlEngine._as_list("single"), ["single"])

    # ------------------------------------------------------------------ #
    #  _compile_safe_regex                                                #
    # ------------------------------------------------------------------ #
    def test_compile_safe_regex_too_long(self):
        with self.assertRaises(ValueError):
            MysqlEngine._compile_safe_regex("a" * 2049)

    # ------------------------------------------------------------------ #
    #  escape_string                                                      #
    # ------------------------------------------------------------------ #
    def test_escape_string(self):
        engine = MysqlEngine(instance=self.ins1)
        self.assertEqual(engine.escape_string("it's"), "it\\'s")

    # ------------------------------------------------------------------ #
    #  kill_connection ValueError path                                     #
    # ------------------------------------------------------------------ #
    def test_kill_connection_invalid_thread_id(self):
        engine = MysqlEngine(instance=self.ins1)
        result = engine.kill_connection("abc")
        self.assertIsNotNone(result.error)

    # ------------------------------------------------------------------ #
    #  get_bind_users                                                     #
    # ------------------------------------------------------------------ #
    @patch.object(MysqlEngine, "query")
    def test_get_bind_users(self, query):
        query.return_value = ResultSet(rows=[("'u'@'%'", "some_db")])
        engine = MysqlEngine(instance=self.ins1)
        rows = engine.get_bind_users("some_db")
        self.assertEqual(rows, [("'u'@'%'", "some_db")])

    # ------------------------------------------------------------------ #
    #  get_instance_users_summary — MariaDB lock SQL branch               #
    # ------------------------------------------------------------------ #
    @patch("MySQLdb.connect")
    @patch.object(MysqlEngine, "query")
    def test_get_instance_users_summary_mariadb_lock(self, query, connect):
        connect.return_value.get_server_info.return_value = "10.4.2-MariaDB"
        result = ResultSet(rows=[("root", "localhost", "Y")])
        grants = ResultSet(rows=[("GRANT ALL",)])
        query.side_effect = [result, grants]
        engine = MysqlEngine(instance=self.ins1)

        summary = engine.get_instance_users_summary()

        self.assertEqual(summary.rows[0]["is_locked"], "Y")
        self.assertEqual(summary.rows[0]["user"], "root")
        # 确认使用了 MariaDB 的 global_priv SQL
        self.assertIn("global_priv", query.call_args_list[0].args[1])

    # ------------------------------------------------------------------ #
    #  create_instance_user — ValueError + empty accounts                  #
    # ------------------------------------------------------------------ #
    @patch.object(MysqlEngine, "execute")
    def test_create_instance_user_null_byte_password(self, execute):
        engine = MysqlEngine(instance=self.ins1)
        result = engine.create_instance_user(
            user="u", host="%", password1="pass\x00word", remark=""
        )
        self.assertIsNotNone(result.error)
        execute.assert_not_called()

    @patch.object(MysqlEngine, "execute")
    def test_create_instance_user_null_byte_user(self, execute):
        """覆盖 create_instance_user 的 ValueError catch (line 952-953)"""
        engine = MysqlEngine(instance=self.ins1)
        result = engine.create_instance_user(
            user="u\x00x", host="%", password1="pwd", remark=""
        )
        self.assertIsNotNone(result.error)
        execute.assert_not_called()

    def test_parse_user_host_with_space_before_at(self):
        """覆盖 _parse_user_host line 264 — 引号括起的 user 后面有空格再到 @"""
        user, host = MysqlEngine._parse_user_host("`user` @`host`")
        self.assertEqual(user, "user")
        self.assertEqual(host, "host")

    def test_reset_instance_user_pwd_null_byte(self):
        """覆盖 reset_instance_user_pwd ValueError catch (lines 1062-1063)"""
        engine = MysqlEngine(instance=self.ins1)
        result = engine.reset_instance_user_pwd("`u`@`%`", "pwd\x00bad")
        self.assertIsNotNone(result.error)

    @patch.object(MysqlEngine, "execute")
    def test_grant_instance_user_db_no_db_names(self, execute):
        """覆盖 grant_instance_user 空 grant_sql 路径 (line 1032)"""
        engine = MysqlEngine(instance=self.ins1)
        result = engine.grant_instance_user(
            user_host="`u`@`%`",
            op_type=0,
            priv_type=1,
            privs={"db_privs": ["SELECT"]},
            db_names=None,
        )
        self.assertEqual(result.error, "授权语句不能为空")
        execute.assert_not_called()

    # ------------------------------------------------------------------ #
    #  grant_instance_user — global (priv_type=0)                          #
    # ------------------------------------------------------------------ #
    @patch.object(MysqlEngine, "execute")
    def test_grant_instance_user_global_privileges(self, execute):
        execute.return_value = ResultSet()
        engine = MysqlEngine(instance=self.ins1)
        result = engine.grant_instance_user(
            user_host="`u`@`%`",
            op_type=0,
            priv_type=0,
            privs={"global_privs": ["SELECT", "INSERT"]},
        )
        self.assertIsNone(result.error)
        self.assertIn("ON *.*", execute.call_args.kwargs["sql"])
        self.assertIn("TO", execute.call_args.kwargs["sql"])

    # ------------------------------------------------------------------ #
    #  grant_instance_user — revoke (op_type=1)                            #
    # ------------------------------------------------------------------ #
    @patch.object(MysqlEngine, "execute")
    def test_grant_instance_user_revoke(self, execute):
        execute.return_value = ResultSet()
        engine = MysqlEngine(instance=self.ins1)
        result = engine.grant_instance_user(
            user_host="`u`@`%`",
            op_type=1,
            priv_type=0,
            privs={"global_privs": ["SELECT"]},
        )
        self.assertIsNone(result.error)
        self.assertIn("REVOKE", execute.call_args.kwargs["sql"])
        self.assertIn("FROM", execute.call_args.kwargs["sql"])

    # ------------------------------------------------------------------ #
    #  grant_instance_user — invalid op_type                               #
    # ------------------------------------------------------------------ #
    def test_grant_instance_user_invalid_op_type(self):
        engine = MysqlEngine(instance=self.ins1)
        result = engine.grant_instance_user(
            user_host="`u`@`%`",
            op_type=99,
            priv_type=0,
            privs={"global_privs": ["SELECT"]},
        )
        self.assertEqual(result.error, "操作类型不合法")

    # ------------------------------------------------------------------ #
    #  grant_instance_user — table (priv_type=2)                           #
    # ------------------------------------------------------------------ #
    @patch.object(MysqlEngine, "execute")
    def test_grant_instance_user_table_privileges(self, execute):
        execute.return_value = ResultSet()
        engine = MysqlEngine(instance=self.ins1)
        result = engine.grant_instance_user(
            user_host="`u`@`%`",
            op_type=0,
            priv_type=2,
            privs={"tb_privs": ["SELECT"]},
            db_names=["mydb"],
            tb_names=["t1", "t2"],
        )
        self.assertIsNone(result.error)
        sql = execute.call_args.kwargs["sql"]
        self.assertIn("`mydb`.`t1`", sql)
        self.assertIn("`mydb`.`t2`", sql)

    # ------------------------------------------------------------------ #
    #  grant_instance_user — column (priv_type=3)                          #
    # ------------------------------------------------------------------ #
    @patch.object(MysqlEngine, "execute")
    def test_grant_instance_user_column_privileges(self, execute):
        execute.return_value = ResultSet()
        engine = MysqlEngine(instance=self.ins1)
        result = engine.grant_instance_user(
            user_host="`u`@`%`",
            op_type=0,
            priv_type=3,
            privs={"col_privs": ["SELECT", "UPDATE"]},
            db_names=["mydb"],
            tb_names=["t1"],
            col_names=["col1", "col2"],
        )
        self.assertIsNone(result.error)
        sql = execute.call_args.kwargs["sql"]
        self.assertIn("SELECT(`col1`,`col2`)", sql)
        self.assertIn("UPDATE(`col1`,`col2`)", sql)

    # ------------------------------------------------------------------ #
    #  grant_instance_user — column with no col_names                      #
    # ------------------------------------------------------------------ #
    def test_grant_instance_user_column_empty_cols(self):
        engine = MysqlEngine(instance=self.ins1)
        result = engine.grant_instance_user(
            user_host="`u`@`%`",
            op_type=0,
            priv_type=3,
            privs={"col_privs": ["SELECT"]},
            db_names=["mydb"],
            tb_names=["t1"],
            col_names=None,
        )
        self.assertEqual(result.error, "列名不能为空")

    # ------------------------------------------------------------------ #
    #  grant_instance_user — invalid priv_type                             #
    # ------------------------------------------------------------------ #
    def test_grant_instance_user_invalid_priv_type(self):
        engine = MysqlEngine(instance=self.ins1)
        result = engine.grant_instance_user(
            user_host="`u`@`%`",
            op_type=0,
            priv_type=99,
            privs={"global_privs": ["SELECT"]},
        )
        self.assertEqual(result.error, "权限类型不合法")

    # ------------------------------------------------------------------ #
    #  set_instance_user_lock — unlock + invalid status                    #
    # ------------------------------------------------------------------ #
    @patch.object(MysqlEngine, "execute")
    def test_set_instance_user_lock_unlock(self, execute):
        execute.return_value = ResultSet()
        engine = MysqlEngine(instance=self.ins1)
        result = engine.set_instance_user_lock("`u`@`%`", "Y")
        self.assertIsNone(result.error)
        self.assertIn("ACCOUNT UNLOCK", execute.call_args.kwargs["sql"])

    def test_set_instance_user_lock_invalid_status(self):
        engine = MysqlEngine(instance=self.ins1)
        result = engine.set_instance_user_lock("`u`@`%`", "X")
        self.assertEqual(result.error, "锁定状态不合法")

    # ------------------------------------------------------------------ #
    #  query — MariaDB max_statement_time branch                           #
    # ------------------------------------------------------------------ #
    @patch("MySQLdb.connect")
    def test_query_mariadb_max_statement_time(self, connect):
        cursor = Mock()
        cursor.execute.return_value = 0
        cursor.fetchall.return_value = []
        cursor.description = None
        connect.return_value.cursor.return_value = cursor
        connect.return_value.get_server_info.return_value = "10.5.0-MariaDB"
        engine = MysqlEngine(instance=self.ins1)

        engine.query(sql="select 1")

        # 第一个 execute 应该是 max_statement_time (MariaDB)
        first_call_sql = cursor.execute.call_args_list[0].args[0]
        self.assertIn("max_statement_time", first_call_sql)

    # ------------------------------------------------------------------ #
    #  _normalize_identifier                                               #
    # ------------------------------------------------------------------ #
    def test_normalize_identifier(self):
        self.assertEqual(MysqlEngine._normalize_identifier(None), "")
        self.assertEqual(MysqlEngine._normalize_identifier("`MyDB`"), "mydb")
        self.assertEqual(MysqlEngine._normalize_identifier("'MyDB'"), "mydb")
        self.assertEqual(MysqlEngine._normalize_identifier('"MyDB"'), "mydb")
        self.assertEqual(MysqlEngine._normalize_identifier("plain"), "plain")
        self.assertEqual(MysqlEngine._normalize_identifier("`my``db`"), "my`db")

    # ------------------------------------------------------------------ #
    #  _sql_references_forbidden_privilege_object — extract_tables 异常     #
    # ------------------------------------------------------------------ #
    @patch("sql.engines.mysql.extract_tables", side_effect=Exception("parse error"))
    def test_sql_references_forbidden_extract_tables_error(self, _extract):
        result = MysqlEngine._sql_references_forbidden_privilege_object(
            "some_db", "select 1 from normal_table"
        )
        self.assertFalse(result)

    def test_sql_references_forbidden_mysql_schema_via_regex(self):
        result = MysqlEngine._sql_references_forbidden_privilege_object(
            "some_db", "select * from mysql.user"
        )
        self.assertTrue(result)

    def test_sql_references_forbidden_info_schema_via_regex(self):
        result = MysqlEngine._sql_references_forbidden_privilege_object(
            "some_db", "select * from information_schema.user_privileges"
        )
        self.assertTrue(result)

    def test_sql_references_forbidden_via_extract_tables(self):
        # 使用子查询方式，extract_tables 可以解析出 mysql.global_grants
        result = MysqlEngine._sql_references_forbidden_privilege_object(
            "some_db", "select * from (select * from mysql.global_grants) t"
        )
        self.assertTrue(result)

    def test_sql_references_forbidden_info_schema_via_extract_tables(self):
        result = MysqlEngine._sql_references_forbidden_privilege_object(
            "some_db",
            "select * from (select * from information_schema.user_privileges) t",
        )
        self.assertTrue(result)

    # ------------------------------------------------------------------ #
    #  _sql_is_forbidden_account_statement                                 #
    # ------------------------------------------------------------------ #
    def test_sql_is_forbidden_show_create_user(self):
        self.assertTrue(
            MysqlEngine._sql_is_forbidden_account_statement("SHOW CREATE USER `u`@`%`")
        )
        self.assertFalse(MysqlEngine._sql_is_forbidden_account_statement("SELECT 1"))

    # ------------------------------------------------------------------ #
    #  execute_check — invalid regex with empty rows                       #
    # ------------------------------------------------------------------ #
    @patch("sql.engines.mysql.GoInceptionEngine")
    def test_execute_check_invalid_regex_empty_rows(self, inception):
        inception.return_value.execute_check.return_value = ReviewSet(rows=[])
        engine = MysqlEngine(instance=self.ins1)
        config = {"critical_ddl_regex": "[", "ddl_dml_separation": False}
        engine.config.get = Mock(
            side_effect=lambda key, default=None: config.get(key, default)
        )

        result = engine.execute_check(db_name="archery", sql="update user set id=1")

        self.assertIn("critical_ddl_regex配置不合法", result.error)

    # ------------------------------------------------------------------ #
    #  execute_check — DDL/DML separation with critical_ddl_regex (no match) #
    # ------------------------------------------------------------------ #
    @patch("sql.engines.mysql.GoInceptionEngine")
    def test_execute_check_ddl_dml_separation_with_critical_regex(self, inception):
        rows = [
            ReviewResult(id=1, sql="create table t(id int)"),
            ReviewResult(id=2, sql="insert into t values(1)"),
        ]
        inception.return_value.execute_check.return_value = ReviewSet(rows=rows)
        engine = MysqlEngine(instance=self.ins1)
        # critical_ddl_regex 有值但不匹配任何语句，同时开启 ddl_dml_separation
        config = {"critical_ddl_regex": "^drop database", "ddl_dml_separation": True}
        engine.config.get = Mock(
            side_effect=lambda key, default=None: config.get(key, default)
        )

        result = engine.execute_check(
            db_name="archery",
            sql="create table t(id int);insert into t values(1);",
        )

        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.rows[1].errormessage, "DDL语句和DML语句不能同时执行！")

    # ------------------------------------------------------------------ #
    #  get_kill_command / kill — empty thread_ids                           #
    # ------------------------------------------------------------------ #
    @patch.object(MysqlEngine, "query")
    def test_get_kill_command_empty_ids(self, query):
        engine = MysqlEngine(instance=self.ins1)
        result = engine.get_kill_command([], thread_ids_check=False)
        self.assertEqual(result, "")
        query.assert_not_called()

    @patch.object(MysqlEngine, "query")
    def test_kill_empty_ids(self, query):
        engine = MysqlEngine(instance=self.ins1)
        result = engine.kill([], thread_ids_check=False)
        self.assertIsInstance(result, ResultSet)
        query.assert_not_called()

    # ------------------------------------------------------------------ #
    #  tablespace — invalid offset/row_count                               #
    # ------------------------------------------------------------------ #
    def test_tablespace_invalid_offset(self):
        engine = MysqlEngine(instance=self.ins1)
        result = engine.tablespace(offset="abc")
        self.assertIsNotNone(result.error)

    def test_tablespace_negative_row_count(self):
        engine = MysqlEngine(instance=self.ins1)
        result = engine.tablespace(row_count=-1)
        self.assertIsNotNone(result.error)

    # ------------------------------------------------------------------ #
    #  close                                                               #
    # ------------------------------------------------------------------ #
    def test_close_with_conn(self):
        engine = MysqlEngine(instance=self.ins1)
        mock_conn = Mock()
        engine.conn = mock_conn
        engine.close()
        mock_conn.close.assert_called_once()
        self.assertIsNone(engine.conn)

    def test_close_without_conn(self):
        engine = MysqlEngine(instance=self.ins1)
        engine.conn = None
        engine.close()  # should not raise
        self.assertIsNone(engine.conn)
