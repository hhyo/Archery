import json
from datetime import timedelta, datetime
from unittest.mock import patch, Mock, ANY

from django.contrib.auth import get_user_model
from django.test import TestCase

from sql.engines import EngineBase
from sql.engines.models import ResultSet, ReviewSet
from sql.engines.mssql import MssqlEngine
from sql.engines.mysql import MysqlEngine
from sql.models import Instance, SqlWorkflow, SqlWorkflowContent

User = get_user_model()


class TestEngineBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.u1 = User(username='some_user', display='用户1')
        cls.u1.save()
        cls.ins1 = Instance(instance_name='some_ins', type='master', db_type='mssql', host='some_host',
                            port=1366, user='ins_user', password='some_pass')
        cls.ins1.save()
        cls.wf1 = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer=cls.u1.username,
            engineer_display=cls.u1.display,
            audit_auth_groups='some_group',
            create_time=datetime.now() - timedelta(days=1),
            status='workflow_finish',
            is_backup='是',
            instance=cls.ins1,
            db_name='some_db',
            syntax_type=1
        )
        cls.wfc1 = SqlWorkflowContent.objects.create(
            workflow=cls.wf1,
            sql_content='some_sql',
            execute_result=json.dumps([{
                'id': 1,
                'sql': 'some_content'
            }]))
        cls.wf1.save()

    @classmethod
    def tearDownClass(cls):
        cls.wfc1.delete()
        cls.wf1.delete()
        cls.ins1.delete()
        cls.u1.delete()

    def test_init_with_ins(self):
        engine = EngineBase(instance=self.ins1)
        self.assertEqual(self.ins1.instance_name, engine.instance_name)
        self.assertEqual(self.ins1.user, engine.user)


class TestMssql(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ins1 = Instance(instance_name='some_ins', type='slave', db_type='mssql', host='some_host',
                            port=1366, user='ins_user', password='some_pass')
        cls.ins1.save()
        cls.engine = MssqlEngine(instance=cls.ins1)

    @classmethod
    def tearDownClass(cls):
        cls.ins1.delete()

    @patch('sql.engines.mssql.pyodbc.connect')
    def testGetConnection(self, connect):
        new_engine = MssqlEngine(instance=self.ins1)
        new_engine.get_connection()
        connect.assert_called_once()

    @patch('sql.engines.mssql.pyodbc.connect')
    def testQuery(self, connect):
        cur = Mock()
        connect.return_value.cursor = cur
        cur.return_value.execute = Mock()
        cur.return_value.fetchmany.return_value = (('v1', 'v2'),)
        cur.return_value.description = (('k1', 'some_other_des'), ('k2', 'some_other_des'))
        new_engine = MssqlEngine(instance=self.ins1)
        query_result = new_engine.query(sql='some_str', limit_num=100)
        cur.return_value.execute.assert_called()
        cur.return_value.fetchmany.assert_called_once_with(100)
        connect.return_value.close.assert_called_once()
        self.assertIsInstance(query_result, ResultSet)

    @patch.object(MssqlEngine, 'query')
    def testAllDb(self, mock_query):
        db_result = ResultSet()
        db_result.rows = [('db_1',), ('db_2',)]
        mock_query.return_value = db_result
        new_engine = MssqlEngine(instance=self.ins1)
        dbs = new_engine.get_all_databases()
        self.assertEqual(dbs, ['db_1', 'db_2'])

    @patch.object(MssqlEngine, 'query')
    def testAllTables(self, mock_query):
        table_result = ResultSet()
        table_result.rows = [('tb_1', 'some_des'), ('tb_2', 'some_des')]
        mock_query.return_value = table_result
        new_engine = MssqlEngine(instance=self.ins1)
        tables = new_engine.get_all_tables('some_db')
        mock_query.assert_called_once_with(db_name='some_db', sql=ANY)
        self.assertEqual(tables, ['tb_1', 'tb_2'])

    @patch.object(MssqlEngine, 'query')
    def testAllColumns(self, mock_query):
        db_result = ResultSet()
        db_result.rows = [('col_1', 'type'), ('col_2', 'type2')]
        mock_query.return_value = db_result
        new_engine = MssqlEngine(instance=self.ins1)
        dbs = new_engine.get_all_columns_by_tb('some_db', 'some_tb')
        self.assertEqual(dbs, ['col_1', 'col_2'])

    @patch.object(MssqlEngine, 'query')
    def testDescribe(self, mock_query):
        new_engine = MssqlEngine(instance=self.ins1)
        new_engine.describe_table('some_db', 'some_db')
        mock_query.assert_called_once()

    def testQueryCheck(self):
        new_engine = MssqlEngine(instance=self.ins1)
        # 只抽查一个函数
        banned_sql = 'select concat(phone,1) from user_table'
        check_result = new_engine.query_check(db_name='some_db', sql=banned_sql)
        self.assertTrue(check_result.get('bad_query'))
        banned_sql = 'select phone from user_table where phone=concat(phone,1)'
        check_result = new_engine.query_check(db_name='some_db', sql=banned_sql)
        self.assertTrue(check_result.get('bad_query'))


class TestMysql(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ins1 = Instance(instance_name='some_ins', type='slave', db_type='mysql', host='some_host',
                            port=1366, user='ins_user', password='some_pass')
        cls.ins1.save()

    @classmethod
    def tearDownClass(cls):
        cls.ins1.delete()

    @patch('MySQLdb.connect')
    def testGetConnection(self, connect):
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.get_connection()
        connect.assert_called_once()

    @patch('MySQLdb.connect')
    def testQuery(self, connect):
        cur = Mock()
        connect.return_value.cursor = cur
        cur.return_value.execute = Mock()
        cur.return_value.fetchmany.return_value = (('v1', 'v2'),)
        cur.return_value.description = (('k1', 'some_other_des'), ('k2', 'some_other_des'))
        new_engine = MysqlEngine(instance=self.ins1)
        query_result = new_engine.query(sql='some_str', limit_num=100)
        cur.return_value.execute.assert_called()
        cur.return_value.fetchmany.assert_called_once_with(size=100)
        connect.return_value.close.assert_called_once()
        self.assertIsInstance(query_result, ResultSet)

    @patch.object(MysqlEngine, 'query')
    def testAllDb(self, mock_query):
        db_result = ResultSet()
        db_result.rows = [('db_1',), ('db_2',)]
        mock_query.return_value = db_result
        new_engine = MysqlEngine(instance=self.ins1)
        dbs = new_engine.get_all_databases()
        self.assertEqual(dbs, ['db_1', 'db_2'])

    @patch.object(MysqlEngine, 'query')
    def testAllTables(self, mock_query):
        table_result = ResultSet()
        table_result.rows = [('tb_1', 'some_des'), ('tb_2', 'some_des')]
        mock_query.return_value = table_result
        new_engine = MysqlEngine(instance=self.ins1)
        tables = new_engine.get_all_tables('some_db')
        mock_query.assert_called_once_with(db_name='some_db', sql=ANY)
        self.assertEqual(tables, ['tb_1', 'tb_2'])

    @patch.object(MysqlEngine, 'query')
    def testAllColumns(self, mock_query):
        db_result = ResultSet()
        db_result.rows = [('col_1', 'type'), ('col_2', 'type2')]
        mock_query.return_value = db_result
        new_engine = MysqlEngine(instance=self.ins1)
        dbs = new_engine.get_all_columns_by_tb('some_db', 'some_tb')
        self.assertEqual(dbs, ['col_1', 'col_2'])

    @patch.object(MysqlEngine, 'query')
    def testDescribe(self, mock_query):
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.describe_table('some_db', 'some_db')
        mock_query.assert_called_once()

    def testQueryCheck(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = 'select user from usertable'
        check_result = new_engine.query_check(db_name='some_db', sql=sql_without_limit, limit_num=100)
        self.assertEqual(check_result['filtered_sql'], 'select user from usertable limit 100;')


class TestModel(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_result_set_rows_shadow(self):
        # 测试默认值为空列表的坑
        # 如果默认值是空列表，又使用的是累加的方法更新，会导致残留上次的列表
        result_set1 = ResultSet()
        for i in range(10):
            result_set1.rows += [i]
        brand_new_result_set = ResultSet()
        self.assertEqual(brand_new_result_set.rows, [])

        review_set1 = ReviewSet()
        for i in range(10):
            review_set1.rows += [i]
        brand_new_review_set = ReviewSet()
        self.assertEqual(brand_new_review_set.rows, [])
