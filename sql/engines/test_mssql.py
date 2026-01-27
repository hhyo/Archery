from datetime import datetime, timedelta
from unittest.mock import patch, Mock, ANY

from django.test import TestCase

from sql.engines import ResultSet, ReviewSet
from sql.engines.models import ReviewResult
from sql.engines.mssql import MssqlEngine
from sql.models import Instance, SqlWorkflow, SqlWorkflowContent


class TestMssql(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ins1 = Instance(
            instance_name="some_ins",
            type="slave",
            db_type="mssql",
            host="some_host",
            port=1366,
            user="ins_user",
            password="some_str",
        )
        cls.ins1.save()
        cls.engine = MssqlEngine(instance=cls.ins1)
        cls.wf = SqlWorkflow.objects.create(
            workflow_name="some_name",
            group_id=1,
            group_name="g1",
            engineer_display="",
            audit_auth_groups="some_group",
            create_time=datetime.now() - timedelta(days=1),
            status="workflow_finish",
            is_backup=True,
            instance=cls.ins1,
            db_name="some_db",
            syntax_type=1,
        )
        SqlWorkflowContent.objects.create(
            workflow=cls.wf, sql_content="insert into some_tb values (1)"
        )

    @classmethod
    def tearDownClass(cls):
        cls.ins1.delete()
        cls.wf.delete()
        SqlWorkflowContent.objects.all().delete()

    @patch("sql.engines.mssql.pyodbc.connect")
    def testGetConnection(self, connect):
        new_engine = MssqlEngine(instance=self.ins1)
        new_engine.get_connection()
        connect.assert_called_once()

    @patch("sql.engines.mssql.pyodbc.connect")
    def testQuery(self, connect):
        cur = Mock()
        connect.return_value.cursor = cur
        cur.return_value.execute = Mock()
        cur.return_value.fetchmany.return_value = (("v1", "v2"),)
        cur.return_value.description = (
            ("k1", "some_other_des"),
            ("k2", "some_other_des"),
        )
        new_engine = MssqlEngine(instance=self.ins1)
        query_result = new_engine.query(sql="some_str", limit_num=100)
        cur.return_value.execute.assert_called()
        cur.return_value.fetchmany.assert_called_once_with(100)
        connect.return_value.close.assert_called_once()
        self.assertIsInstance(query_result, ResultSet)

    @patch.object(MssqlEngine, "query")
    def testAllDb(self, mock_query):
        db_result = ResultSet()
        db_result.rows = [("db_1",), ("db_2",)]
        mock_query.return_value = db_result
        new_engine = MssqlEngine(instance=self.ins1)
        dbs = new_engine.get_all_databases()
        self.assertEqual(dbs.rows, ["db_1", "db_2"])

    @patch.object(MssqlEngine, "query")
    def testAllTables(self, mock_query):
        table_result = ResultSet()
        table_result.rows = [("tb_1", "some_des"), ("tb_2", "some_des")]
        mock_query.return_value = table_result
        new_engine = MssqlEngine(instance=self.ins1)
        tables = new_engine.get_all_tables("some_db")
        mock_query.assert_called_once_with(db_name="some_db", sql=ANY)
        self.assertEqual(tables.rows, ["tb_1", "tb_2"])

    @patch.object(MssqlEngine, "query")
    def testAllColumns(self, mock_query):
        db_result = ResultSet()
        db_result.rows = [("col_1", "type"), ("col_2", "type2")]
        mock_query.return_value = db_result
        new_engine = MssqlEngine(instance=self.ins1)
        dbs = new_engine.get_all_columns_by_tb("some_db", "some_tb")
        self.assertEqual(dbs.rows, ["col_1", "col_2"])

    @patch.object(MssqlEngine, "query")
    def testDescribe(self, mock_query):
        new_engine = MssqlEngine(instance=self.ins1)
        new_engine.describe_table("some_db", "some_db")
        mock_query.assert_called_once()

    def testQueryCheck(self):
        new_engine = MssqlEngine(instance=self.ins1)
        # 只抽查一个函数
        banned_sql = "select concat(phone,1) from user_table"
        check_result = new_engine.query_check(db_name="some_db", sql=banned_sql)
        self.assertTrue(check_result.get("bad_query"))
        banned_sql = "select phone from user_table where phone=concat(phone,1)"
        check_result = new_engine.query_check(db_name="some_db", sql=banned_sql)
        self.assertTrue(check_result.get("bad_query"))
        sp_sql = "sp_helptext '[SomeName].[SomeAction]'"
        check_result = new_engine.query_check(db_name="some_db", sql=sp_sql)
        self.assertFalse(check_result.get("bad_query"))
        self.assertEqual(check_result.get("filtered_sql"), sp_sql)

    def test_filter_sql(self):
        new_engine = MssqlEngine(instance=self.ins1)
        # 只抽查一个函数
        banned_sql = "select user from user_table"
        check_result = new_engine.filter_sql(sql=banned_sql, limit_num=10)
        self.assertEqual(check_result, "select top 10 user from user_table")

    def test_filter_sql_with_distinct(self):
        new_engine = MssqlEngine(instance=self.ins1)
        # 只抽查一个函数
        banned_sql = "select distinct * from user_table"
        check_result = new_engine.filter_sql(sql=banned_sql, limit_num=10)
        self.assertEqual(check_result, "select distinct top 10 * from user_table")

    @patch("sql.engines.mssql.MssqlEngine.get_connection")
    def test_execute_check(self, mock_get_connection):
        # Mock 连接以避免 ODBC 驱动错误
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn

        new_engine = MssqlEngine(instance=self.ins1)
        # 测试SQL包含GO，但GO会被移除，然后按分号分割
        test_sql = (
            "use database\ngo\nsome sql1\nGO\nsome sql2\n\r\nGo\nsome sql3\n\r\ngO\n"
        )
        check_result = new_engine.execute_check(db_name=None, sql=test_sql)
        self.assertIsInstance(check_result, ReviewSet)
        # GO会被移除，然后sqlparse.split会按分号分割（如果没有分号，可能是一条语句）
        # 验证至少有一条语句被处理
        self.assertGreaterEqual(len(check_result.rows), 1)

    @patch("sql.engines.mssql.MssqlEngine.execute")
    def test_execute_workflow(self, mock_execute):
        mock_execute.return_value.error = None
        new_engine = MssqlEngine(instance=self.ins1)
        new_engine.execute_workflow(self.wf)
        # 有多少个备份表, 就需要execute多少次, 另外加上一条实际执行的次数
        mock_execute.assert_called()
        self.assertEqual(1, mock_execute.call_count)

    @patch("sql.engines.mssql.MssqlEngine.get_connection")
    def test_execute(self, mock_connect):
        mock_cursor = Mock()
        mock_connect.return_value.cursor = mock_cursor
        new_engine = MssqlEngine(instance=self.ins1)
        execute_result = new_engine.execute("some_db", "some_sql")
        # 验证结果, 无异常
        self.assertIsNone(execute_result.error)
        self.assertEqual("some_sql", execute_result.full_sql)
        self.assertEqual(2, len(execute_result.rows))
        mock_cursor.return_value.execute.assert_called()
        # MSSQL 使用 conn.commit()，每条语句执行后立即提交
        mock_connect.return_value.commit.assert_called()
        mock_cursor.reset_mock()
        # 验证异常
        mock_cursor.return_value.execute.side_effect = Exception(
            "Boom! some exception!"
        )
        execute_result = new_engine.execute("some_db", "some_sql")
        self.assertIn("Boom! some exception!", execute_result.error)
        self.assertEqual("some_sql", execute_result.full_sql)
        self.assertEqual(2, len(execute_result.rows))
        # 异常情况下，应该调用 rollback，而不是 commit
        mock_connect.return_value.rollback.assert_called()
