from datetime import datetime, timedelta
from unittest.mock import patch

import sqlparse
from django.test import TestCase

from common.config import SysConfig
from sql.engines.models import ResultSet, ReviewResult, ReviewSet
from sql.engines.oracle import OracleEngine
from sql.models import Instance, SqlWorkflow, SqlWorkflowContent


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

    @patch("cx_Oracle.makedsn")
    @patch("cx_Oracle.connect")
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

    @patch("cx_Oracle.connect")
    def test_engine_base_info(self, _conn):
        new_engine = OracleEngine(instance=self.ins)
        self.assertEqual(new_engine.name, "Oracle")
        self.assertEqual(new_engine.info, "Oracle engine")
        _conn.return_value.version = "12.1.0.2.0"
        self.assertTupleEqual(new_engine.server_version, ("12", "1", "0"))

    @patch("cx_Oracle.connect.cursor.execute")
    @patch("cx_Oracle.connect.cursor")
    @patch("cx_Oracle.connect")
    def test_query(self, _conn, _cursor, _execute):
        _conn.return_value.cursor.return_value.fetchmany.return_value = [(1,)]
        new_engine = OracleEngine(instance=self.ins)
        query_result = new_engine.query(
            db_name="archery", sql="select 1", limit_num=100
        )
        self.assertIsInstance(query_result, ResultSet)
        self.assertListEqual(query_result.rows, [(1,)])

    @patch("cx_Oracle.connect.cursor.execute")
    @patch("cx_Oracle.connect.cursor")
    @patch("cx_Oracle.connect")
    def test_query_not_limit(self, _conn, _cursor, _execute):
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

    @patch("cx_Oracle.connect.cursor.execute")
    @patch("cx_Oracle.connect.cursor")
    @patch("cx_Oracle.connect")
    def test_execute_workflow_success(self, _conn, _cursor, _execute):
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

    @patch("cx_Oracle.connect.cursor.execute")
    @patch("cx_Oracle.connect.cursor")
    @patch("cx_Oracle.connect", return_value=RuntimeError)
    def test_execute_workflow_exception(self, _conn, _cursor, _execute):
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

    @patch("cx_Oracle.connect.cursor.execute")
    @patch("cx_Oracle.connect.cursor")
    @patch("cx_Oracle.connect")
    def test_execute(self, _connect, _cursor, _execute):
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
    @patch("cx_Oracle.connect.cursor.execute")
    @patch("cx_Oracle.connect.cursor")
    @patch("cx_Oracle.connect")
    def test_kill_session(self, _query, _connect, _cursor, _execute):
        new_engine = OracleEngine(instance=self.ins)
        _query.return_value.rows = (
            ("alter system kill session '12,123';",),
            ("alter system kill session '34,345';",),
        )
        _execute.return_value = ResultSet()
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
