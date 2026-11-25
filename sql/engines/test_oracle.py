from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import sqlparse
from django.test import SimpleTestCase, TestCase

from common.config import SysConfig
from sql.engines.models import ResultSet, ReviewResult, ReviewSet
from sql.engines.oracle import OracleEngine
from sql.models import Instance, SqlWorkflow, SqlWorkflowContent


class TestOracleLogMiner(SimpleTestCase):
    def _run_workflow(self, version, query_rows, *, is_backup=True):
        sql = "update accounts set enabled = 1 where id = 7"
        review = ReviewResult(
            sql=sql, stmt_type="SQL", object_owner="", object_type="", object_name=""
        )
        workflow = SimpleNamespace(
            id=7,
            db_name="APP",
            syntax_type=2,
            is_backup=is_backup,
            sqlworkflowcontent=SimpleNamespace(
                review_content=ReviewSet(rows=[review]).json(), sql_content=sql
            ),
        )
        conn = MagicMock(version=version)
        cursor = conn.cursor.return_value
        cursor.fetchone.side_effect = query_rows
        engine = OracleEngine()
        engine.conn = conn

        with patch.object(engine, "_backup_by_scn") as scn_backup, patch.object(
            engine, "backup"
        ) as legacy_backup:
            result = engine.execute_workflow(workflow)

        self.assertFalse(result.error)
        conn.commit.assert_called_once()
        return workflow, cursor, scn_backup, legacy_backup

    def test_19c_and_later_workflows_pass_scn_range_to_backup(self):
        versions = (
            ("19.29.0.0.0", 0),
            ("21.0.0.0.0", 1),
            ("23.0.0.0.0", 1),
            ("23.26.0.0.0", 1),
        )
        for version, container_id in versions:
            with self.subTest(version=version):
                workflow, cursor, scn_backup, legacy_backup = self._run_workflow(
                    version, [(420, "YES", container_id), (435,)]
                )
                scn_backup.assert_called_once_with(workflow, cursor, 420, 435)
                legacy_backup.assert_not_called()

    def test_pdb_workflow_executes_sql_without_explicit_redo_registration(self):
        _, _, scn_backup, legacy_backup = self._run_workflow(
            "19.29.0.0.0", [(420, "YES", 3)]
        )
        scn_backup.assert_not_called()
        legacy_backup.assert_not_called()

    def test_pre_19c_versions_use_original_timestamp_backup(self):
        begin_time = datetime(2026, 1, 1, 10)
        end_time = begin_time + timedelta(seconds=5)

        for version in ("11.2.0.4.0", "12.2.0.1.0", "18.0.0.0.0"):
            with self.subTest(version=version):
                workflow, cursor, scn_backup, legacy_backup = self._run_workflow(
                    version, [(begin_time,), (end_time,)]
                )
                self.assertEqual(
                    cursor.execute.call_args_list,
                    [
                        call(
                            "alter session set nls_date_format='yyyy-mm-dd hh24:mi:ss'"
                        ),
                        call("select sysdate from dual"),
                        call(workflow.sqlworkflowcontent.sql_content),
                        call("select sysdate from dual"),
                    ],
                )
                legacy_backup.assert_called_once_with(
                    workflow, cursor=cursor, begin_time=begin_time, end_time=end_time
                )
                scn_backup.assert_not_called()

    def test_workflow_without_backup_still_reads_start_time(self):
        _, cursor, scn_backup, legacy_backup = self._run_workflow(
            "11.2.0.4.0", [(datetime(2026, 1, 1, 10),)], is_backup=False
        )
        self.assertEqual(
            cursor.execute.call_args_list[1], call("select sysdate from dual")
        )
        cursor.fetchone.assert_called_once()
        legacy_backup.assert_not_called()
        scn_backup.assert_not_called()

    def test_scn_backup_registers_logs_and_stores_undo_in_reverse_order(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("archived.log",), ("online.log",)]
        # 第二条回滚 SQL 跨两行，且包含需要原样保留的字符。
        cursor.__iter__.return_value = [
            ("first redo", "first undo", 0, 0),
            ("second redo", "second undo with '<&", 1, 0),
            (None, " and a quote''';", 0, 0),
        ]
        backup_conn = MagicMock()
        engine = OracleEngine()

        with patch.object(engine, "get_backup_connection", return_value=backup_conn):
            engine._backup_by_scn(SimpleNamespace(id=7), cursor, 420, 435)

        select_logs, add_first, add_next, start, _, end = cursor.execute.call_args_list
        self.assertIn("sys.v_$archived_log", select_logs.args[0])
        self.assertIn("sys.v_$logfile", select_logs.args[0])
        self.assertIn(".NEW", add_first.args[0])
        self.assertEqual(add_first.kwargs, {"filename": "archived.log"})
        self.assertIn(".ADDFILE", add_next.args[0])
        self.assertEqual(add_next.kwargs, {"filename": "online.log"})
        self.assertEqual(start.args[1], {"start_scn": 420, "end_scn": 435})
        self.assertNotIn("continuous_mine", start.args[0])
        self.assertIn("end_logmnr", end.args[0])
        write = backup_conn.cursor.return_value.executemany
        write.assert_called_once()
        self.assertEqual(
            write.call_args.args[1],
            [
                ("second redo", "second undo with '<& and a quote''';", 7),
                ("first redo", "first undo", 7),
            ],
        )
        backup_conn.commit.assert_called_once()

    def test_scn_backup_ends_logminer_when_read_fails(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("online.log",)]
        cursor.execute.side_effect = [
            None,
            None,
            None,
            RuntimeError("read failed"),
            None,
        ]

        with self.assertRaisesRegex(RuntimeError, "read failed"):
            OracleEngine()._mine_scn_rollback(cursor, 420, 435)

        self.assertIn("end_logmnr", cursor.execute.call_args.args[0])

    def test_scn_backup_rejects_incomplete_redo_before_storing_rows(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("online.log",)]
        # LogMiner 在正常 DML 后报告 redo 缺口时，已读取的语句也不能写入备份库。
        cursor.__iter__.return_value = [("redo", "undo", 0, 0), (None, None, 0, 1291)]
        backup_conn = MagicMock()
        engine = OracleEngine()

        with patch.object(engine, "get_backup_connection", return_value=backup_conn):
            with self.assertRaisesRegex(ValueError, "STATUS=1291"):
                engine._backup_by_scn(SimpleNamespace(id=7), cursor, 420, 435)

        self.assertIn("operation_code = 34", cursor.execute.call_args_list[-2].args[0])
        self.assertIn("end_logmnr", cursor.execute.call_args.args[0])
        backup_conn.cursor.return_value.executemany.assert_not_called()


class TestOracle(TestCase):
    """Oracle 测试"""

    def setUp(self):
        self.ins = Instance.objects.create(
            instance_name="some_ins",
            type="slave",
            db_type="oracle",
            host="some_host",
            port=3306,
            user="ins_user",
            password="some_str",
            sid="some_id",
        )
        self.wf = SqlWorkflow.objects.create(
            workflow_name="some_name",
            group_id=1,
            group_name="g1",
            engineer_display="",
            audit_auth_groups="some_group",
            create_time=datetime.now() - timedelta(days=1),
            status="workflow_finish",
            is_backup=True,
            instance=self.ins,
            db_name="some_db",
            syntax_type=1,
        )
        SqlWorkflowContent.objects.create(workflow=self.wf)
        self.sys_config = SysConfig()

    def tearDown(self):
        self.ins.delete()
        self.sys_config.purge()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()

    @patch("oracledb.makedsn")
    @patch("oracledb.connect")
    def test_get_connection(self, _connect, _makedsn):
        # 填写 sid 测试
        new_engine = OracleEngine(self.ins)
        new_engine.get_connection()
        _connect.assert_called_once()
        _makedsn.assert_called_once()
        # 填写 service_name 测试
        _connect.reset_mock()
        _makedsn.reset_mock()
        self.ins.service_name = "some_service"
        self.ins.sid = ""
        self.ins.save()
        new_engine = OracleEngine(self.ins)
        new_engine.get_connection()
        _connect.assert_called_once()
        _makedsn.assert_called_once()
        # 都不填写, 检测 ValueError
        _connect.reset_mock()
        _makedsn.reset_mock()
        self.ins.service_name = ""
        self.ins.sid = ""
        self.ins.save()
        new_engine = OracleEngine(self.ins)
        with self.assertRaises(ValueError):
            new_engine.get_connection()

    @patch("oracledb.connect")
    def test_engine_base_info(self, _conn):
        new_engine = OracleEngine(instance=self.ins)
        self.assertEqual(new_engine.name, "Oracle")
        self.assertEqual(new_engine.info, "Oracle engine")
        _conn.return_value.version = "12.1.0.2.0"
        self.assertTupleEqual(new_engine.server_version, ("12", "1", "0"))

    @patch("oracledb.connect")
    def test_query(self, _conn):
        _conn.return_value.cursor.return_value.fetchmany.return_value = [(1,)]
        new_engine = OracleEngine(instance=self.ins)
        query_result = new_engine.query(
            db_name="archery", sql="select 1", limit_num=100
        )
        self.assertIsInstance(query_result, ResultSet)
        self.assertListEqual(query_result.rows, [(1,)])

    @patch("oracledb.connect")
    def test_query_not_limit(self, _conn):
        _conn.return_value.cursor.return_value.fetchall.return_value = [(1,)]
        new_engine = OracleEngine(instance=self.ins)
        query_result = new_engine.query(db_name=0, sql="select 1", limit_num=0)
        self.assertIsInstance(query_result, ResultSet)
        self.assertListEqual(query_result.rows, [(1,)])

    @patch(
        "sql.engines.oracle.OracleEngine.query",
        return_value=ResultSet(rows=[("AUD_SYS",), ("archery",), ("ANONYMOUS",)]),
    )
    def test_get_all_databases(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        dbs = new_engine.get_all_databases()
        self.assertListEqual(dbs.rows, ["archery"])

    @patch(
        "sql.engines.oracle.OracleEngine.query",
        return_value=ResultSet(rows=[("AUD_SYS",), ("archery",), ("ANONYMOUS",)]),
    )
    def test__get_all_databases(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        dbs = new_engine._get_all_databases()
        self.assertListEqual(dbs.rows, ["AUD_SYS", "archery", "ANONYMOUS"])

    @patch(
        "sql.engines.oracle.OracleEngine.query",
        return_value=ResultSet(rows=[("archery",)]),
    )
    def test__get_all_instances(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        dbs = new_engine._get_all_instances()
        self.assertListEqual(dbs.rows, ["archery"])

    @patch(
        "sql.engines.oracle.OracleEngine.query",
        return_value=ResultSet(rows=[("ANONYMOUS",), ("archery",), ("SYSTEM",)]),
    )
    def test_get_all_schemas(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        schemas = new_engine._get_all_schemas()
        self.assertListEqual(schemas.rows, ["archery"])

    @patch(
        "sql.engines.oracle.OracleEngine.query",
        return_value=ResultSet(rows=[("test",), ("test2",)]),
    )
    def test_get_all_tables(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        tables = new_engine.get_all_tables(db_name="archery")
        self.assertListEqual(tables.rows, ["test2"])

    @patch(
        "sql.engines.oracle.OracleEngine.query",
        return_value=ResultSet(rows=[("id",), ("name",)]),
    )
    def test_get_all_columns_by_tb(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        columns = new_engine.get_all_columns_by_tb(db_name="archery", tb_name="test2")
        self.assertListEqual(columns.rows, ["id", "name"])

    @patch(
        "sql.engines.oracle.OracleEngine.query",
        return_value=ResultSet(rows=[("archery",), ("template1",), ("template0",)]),
    )
    def test_describe_table(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        describe = new_engine.describe_table(db_name="archery", tb_name="text")
        self.assertIsInstance(describe, ResultSet)

    def test_query_check_disable_sql(self):
        sql = "update xxx set a=1;"
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.query_check(db_name="archery", sql=sql)
        self.assertDictEqual(
            check_result,
            {
                "msg": "不支持语法!",
                "bad_query": True,
                "filtered_sql": sql.strip(";"),
                "has_star": False,
            },
        )

    @patch(
        "sql.engines.oracle.OracleEngine.explain_check",
        return_value={"msg": "", "rows": 0},
    )
    def test_query_check_star_sql(self, _explain_check):
        sql = "select * from xx;"
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.query_check(db_name="archery", sql=sql)
        self.assertDictEqual(
            check_result,
            {
                "msg": "禁止使用 * 关键词\n",
                "bad_query": False,
                "filtered_sql": sql.strip(";"),
                "has_star": True,
            },
        )

    def test_query_check_IndexError(self):
        sql = ""
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.query_check(db_name="archery", sql=sql)
        self.assertDictEqual(
            check_result,
            {
                "msg": "没有有效的SQL语句",
                "bad_query": True,
                "filtered_sql": sql.strip(),
                "has_star": False,
            },
        )

    def test_query_masking(self):
        query_result = ResultSet()
        new_engine = OracleEngine(instance=self.ins)
        masking_result = new_engine.query_masking(
            sql="select 1 from dual", resultset=query_result
        )
        self.assertEqual(masking_result, query_result)

    def test_execute_check_select_sql(self):
        sql = "select * from user;"
        row = ReviewResult(
            id=1,
            errlevel=2,
            stagestatus="驳回不支持语句",
            errormessage="仅支持DML和DDL语句，查询语句请使用SQL查询功能！",
            sql=sqlparse.format(
                sql, strip_comments=True, reindent=True, keyword_case="lower"
            ),
        )
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.execute_check(db_name="archery", sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    def test_execute_check_critical_sql(self):
        self.sys_config.set("critical_ddl_regex", "^|update")
        self.sys_config.get_all_config()
        sql = "update user set id=1"
        row = ReviewResult(
            id=1,
            errlevel=2,
            stagestatus="驳回高危SQL",
            errormessage="禁止提交匹配" + "^|update" + "条件的语句！",
            sql=sqlparse.format(
                sql, strip_comments=True, reindent=True, keyword_case="lower"
            ),
        )
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.execute_check(db_name="archery", sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch(
        "sql.engines.oracle.OracleEngine.explain_check",
        return_value={"msg": "", "rows": 0},
    )
    @patch(
        "sql.engines.oracle.OracleEngine.get_sql_first_object_name", return_value="tb"
    )
    @patch("sql.engines.oracle.OracleEngine.object_name_check", return_value=True)
    def test_execute_check_normal_sql(
        self, _explain_check, _get_sql_first_object_name, _object_name_check
    ):
        self.sys_config.purge()
        sql = "alter table tb set id=1"
        row = ReviewResult(
            id=1,
            errlevel=1,
            stagestatus="当前平台，此语法不支持审核！",
            errormessage="当前平台，此语法不支持审核！",
            sql=sqlparse.format(
                sql, strip_comments=True, reindent=True, keyword_case="lower"
            ),
            affected_rows=0,
            execute_time=0,
            stmt_type="SQL",
            object_owner="",
            object_type="",
            object_name="",
        )
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.execute_check(db_name="archery", sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    def test_get_sql_first_object_name(self):
        """
        测试获取sql文本中的object_name
        :return:
        """
        new_engine = OracleEngine(instance=self.ins)
        sql = """create or replace procedure INSERTUSER
(id IN NUMBER,
name IN VARCHAR2)
is
begin
    insert into user1 values(id,name);
end;"""
        object_name = new_engine.get_sql_first_object_name(sql)
        self.assertEqual(object_name, "INSERTUSER")

    @patch(
        "sql.engines.oracle.OracleEngine.get_sql_first_object_name",
        return_value="INSERTUSER",
    )
    @patch("sql.engines.oracle.OracleEngine.object_name_check", return_value=True)
    def test_execute_check_replace_exist_plsql_object(
        self, _get_sql_first_object_name, _object_name_check
    ):
        sql = """create or replace procedure INSERTUSER
(id IN NUMBER,
name IN VARCHAR2)
is
begin
    insert into user1 values(id,name);
end;"""
        row = ReviewResult(
            id=1,
            errlevel=1,
            stagestatus=""""TRADE".INSERTUSER对象已经存在，请确认是否替换！""",
            errormessage=""""TRADE".INSERTUSER对象已经存在，请确认是否替换！""",
            sql=sqlparse.format(
                sql, strip_comments=True, reindent=True, keyword_case="lower"
            ),
            affected_rows=0,
            execute_time=0,
            stmt_type="SQL",
            object_owner="",
            object_type="",
            object_name="",
        )
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.execute_check(db_name="TRADE", sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch(
        "sql.engines.oracle.OracleEngine.get_sql_first_object_name",
        return_value="INSERTUSER",
    )
    @patch("sql.engines.oracle.OracleEngine.object_name_check", return_value=True)
    def test_execute_check_exist_plsql_object(
        self, _get_sql_first_object_name, _object_name_check
    ):
        sql = """create procedure INSERTUSER
(id IN NUMBER,
name IN VARCHAR2)
is
begin
    insert into user1 values(id,name);
end;"""
        row = ReviewResult(
            id=1,
            errlevel=2,
            stagestatus=""""TRADE".INSERTUSER对象已经存在！""",
            errormessage=""""TRADE".INSERTUSER对象已经存在！""",
            sql=sqlparse.format(
                sql, strip_comments=True, reindent=True, keyword_case="lower"
            ),
        )
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.execute_check(db_name="TRADE", sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch("oracledb.connect")
    def test_execute_workflow_success(self, _conn):
        sql = "update user set id=1"
        review_row = ReviewResult(
            id=1,
            errlevel=0,
            stagestatus="Execute Successfully",
            errormessage="None",
            sql=sql,
            affected_rows=0,
            execute_time=0,
            stmt_type="SQL",
            object_owner="",
            object_type="",
            object_name="",
        )
        execute_row = ReviewResult(
            id=1,
            errlevel=0,
            stagestatus="Execute Successfully",
            errormessage="None",
            sql=sql,
            affected_rows=0,
            execute_time=0,
        )
        wf = SqlWorkflow.objects.create(
            workflow_name="some_name",
            group_id=1,
            group_name="g1",
            engineer_display="",
            audit_auth_groups="some_group",
            create_time=datetime.now() - timedelta(days=1),
            status="workflow_finish",
            is_backup=True,
            instance=self.ins,
            db_name="some_db",
            syntax_type=1,
        )
        SqlWorkflowContent.objects.create(
            workflow=wf,
            sql_content=sql,
            review_content=ReviewSet(rows=[review_row]).json(),
        )
        new_engine = OracleEngine(instance=self.ins)
        execute_result = new_engine.execute_workflow(workflow=wf)
        self.assertIsInstance(execute_result, ReviewSet)
        self.assertEqual(
            execute_result.rows[0].__dict__.keys(), execute_row.__dict__.keys()
        )

    @patch("oracledb.connect", return_value=RuntimeError)
    def test_execute_workflow_exception(self, _conn):
        sql = "update user set id=1"
        row = ReviewResult(
            id=1,
            errlevel=2,
            stagestatus="Execute Failed",
            errormessage=f'异常信息：{f"Oracle命令执行报错，语句：{sql}"}',
            sql=sql,
            affected_rows=0,
            execute_time=0,
            stmt_type="SQL",
            object_owner="",
            object_type="",
            object_name="",
        )
        wf = SqlWorkflow.objects.create(
            workflow_name="some_name",
            group_id=1,
            group_name="g1",
            engineer_display="",
            audit_auth_groups="some_group",
            create_time=datetime.now() - timedelta(days=1),
            status="workflow_finish",
            is_backup=True,
            instance=self.ins,
            db_name="some_db",
            syntax_type=1,
        )
        SqlWorkflowContent.objects.create(
            workflow=wf, sql_content=sql, review_content=ReviewSet(rows=[row]).json()
        )
        with self.assertRaises(AttributeError):
            new_engine = OracleEngine(instance=self.ins)
            execute_result = new_engine.execute_workflow(workflow=wf)
            self.assertIsInstance(execute_result, ReviewSet)
            self.assertEqual(
                execute_result.rows[0].__dict__.keys(), row.__dict__.keys()
            )

    @patch("oracledb.connect")
    def test_execute(self, _connect):
        new_engine = OracleEngine(instance=self.ins)
        sql = "update abc set count=1 where id=1;"
        execute_result = new_engine.execute(sql)
        self.assertIsInstance(execute_result, ResultSet)

    @patch("sql.engines.oracle.OracleEngine.query")
    def test_processlist(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        _query.return_value = ResultSet()
        for command_type in ["All", "Active", "Others"]:
            r = new_engine.processlist(command_type)
            self.assertIsInstance(r, ResultSet)

    @patch("sql.engines.oracle.OracleEngine.query")
    def test_get_kill_command(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        _query.return_value.rows = (
            ("alter system kill session '12,123';",),
            ("alter system kill session '34,345';",),
        )
        r = new_engine.get_kill_command([[12, 123], [34, 345]])
        self.assertEqual(
            r, "alter system kill session '12,123';alter system kill session '34,345';"
        )

    @patch("sql.engines.oracle.OracleEngine.query")
    @patch("oracledb.connect")
    def test_kill_session(self, _connect, _query):
        new_engine = OracleEngine(instance=self.ins)
        _query.return_value.rows = (
            ("alter system kill session '12,123';",),
            ("alter system kill session '34,345';",),
        )
        _connect.return_value.cursor.return_value.execute.return_value = ResultSet()
        r = new_engine.kill_session([[12, 123], [34, 345]])
        self.assertIsInstance(r, ResultSet)

    @patch("sql.engines.oracle.OracleEngine.query")
    def test_tablespace(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        _query.return_value = ResultSet()
        r = new_engine.tablespace()
        self.assertIsInstance(r, ResultSet)

    @patch("sql.engines.oracle.OracleEngine.query")
    def test_tablespace_count(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        _query.return_value = ResultSet()
        r = new_engine.tablespace_count()
        self.assertIsInstance(r, ResultSet)

    @patch("sql.engines.oracle.OracleEngine.query")
    def test_lock_info(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        _query.return_value = ResultSet()
        r = new_engine.lock_info()
        self.assertIsInstance(r, ResultSet)

    @patch("sql.engines.oracle.OracleEngine.query")
    def test_get_table_desc_data(self, _query):
        """测试获取表格字段信息方法"""
        new_engine = OracleEngine(instance=self.ins)

        mock_result = ResultSet()
        mock_result.column_list = [
            "列名",
            "列注释",
            "字段类型",
            "字段默认值",
            "是否为空",
            "所属索引",
            "约束类型",
        ]
        mock_result.rows = [
            ("ID", "主键ID", "NUMBER(10)", "1", " NOT NULL", "PK_USER", "P")
        ]
        _query.return_value = mock_result

        result = new_engine.get_table_desc_data(db_name="TEST_SCHEMA", tb_name="USERS")

        self.assertIsInstance(result, dict)
        self.assertIn("column_list", result)
        self.assertIn("rows", result)
        self.assertIsInstance(result["column_list"], list)
        self.assertIsInstance(result["rows"], list)
        _query.assert_called_once()

    @patch("sql.engines.oracle.OracleEngine.query")
    def test_get_table_index_data(self, _query):
        """测试获取表格索引信息方法"""
        new_engine = OracleEngine(instance=self.ins)

        mock_result = ResultSet()
        mock_result.column_list = [
            "索引名称",
            "唯一性",
            "索引类型",
            "压缩属性",
            "表空间",
            "状态",
            "分区",
        ]
        mock_result.rows = [
            ("PK_USERS", "UNIQUE", "NORMAL", "DISABLED", "USERS_TBS", "VALID", "NO")
        ]
        _query.return_value = mock_result

        result = new_engine.get_table_index_data(db_name="TEST_SCHEMA", tb_name="USERS")

        self.assertIsInstance(result, dict)
        self.assertIn("column_list", result)
        self.assertIn("rows", result)
        self.assertIsInstance(result["column_list"], list)
        self.assertIsInstance(result["rows"], list)
        _query.assert_called_once()
