import MySQLdb
import json
from datetime import timedelta, datetime
from unittest.mock import patch, Mock, ANY

import sqlparse
from django.contrib.auth import get_user_model
from django.test import TestCase

from common.config import SysConfig
from sql.engines import EngineBase
from sql.engines.goinception import GoInceptionEngine
from sql.engines.models import ResultSet, ReviewSet, ReviewResult
from sql.engines.mssql import MssqlEngine
from sql.engines.mysql import MysqlEngine
from sql.engines.redis import RedisEngine
from sql.engines.pgsql import PgSQLEngine
from sql.engines.oracle import OracleEngine
from sql.engines.mongo import MongoEngine
from sql.engines.clickhouse import ClickHouseEngine
from sql.engines.odps import ODPSEngine
from sql.models import Instance, SqlWorkflow, SqlWorkflowContent

User = get_user_model()


class TestReviewSet(TestCase):
    def test_review_set(self):
        new_review_set = ReviewSet()
        new_review_set.rows = [{'id': '1679123'}]
        self.assertIn('1679123', new_review_set.json())


class TestEngineBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.u1 = User(username='some_user', display='用户1')
        cls.u1.save()
        cls.ins1 = Instance(instance_name='some_ins', type='master', db_type='mssql', host='some_host',
                            port=1366, user='ins_user', password='some_str')
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
            is_backup=True,
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
                            port=1366, user='ins_user', password='some_str')
        cls.ins1.save()
        cls.engine = MssqlEngine(instance=cls.ins1)
        cls.wf = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer_display='',
            audit_auth_groups='some_group',
            create_time=datetime.now() - timedelta(days=1),
            status='workflow_finish',
            is_backup=True,
            instance=cls.ins1,
            db_name='some_db',
            syntax_type=1
        )
        SqlWorkflowContent.objects.create(workflow=cls.wf, sql_content='insert into some_tb values (1)')

    @classmethod
    def tearDownClass(cls):
        cls.ins1.delete()
        cls.wf.delete()
        SqlWorkflowContent.objects.all().delete()

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
        self.assertEqual(dbs.rows, ['db_1', 'db_2'])

    @patch.object(MssqlEngine, 'query')
    def testAllTables(self, mock_query):
        table_result = ResultSet()
        table_result.rows = [('tb_1', 'some_des'), ('tb_2', 'some_des')]
        mock_query.return_value = table_result
        new_engine = MssqlEngine(instance=self.ins1)
        tables = new_engine.get_all_tables('some_db')
        mock_query.assert_called_once_with(db_name='some_db', sql=ANY)
        self.assertEqual(tables.rows, ['tb_1', 'tb_2'])

    @patch.object(MssqlEngine, 'query')
    def testAllColumns(self, mock_query):
        db_result = ResultSet()
        db_result.rows = [('col_1', 'type'), ('col_2', 'type2')]
        mock_query.return_value = db_result
        new_engine = MssqlEngine(instance=self.ins1)
        dbs = new_engine.get_all_columns_by_tb('some_db', 'some_tb')
        self.assertEqual(dbs.rows, ['col_1', 'col_2'])

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
        sp_sql = "sp_helptext '[SomeName].[SomeAction]'"
        check_result = new_engine.query_check(db_name='some_db', sql=sp_sql)
        self.assertFalse(check_result.get('bad_query'))
        self.assertEqual(check_result.get('filtered_sql'), sp_sql)

    def test_filter_sql(self):
        new_engine = MssqlEngine(instance=self.ins1)
        # 只抽查一个函数
        banned_sql = 'select user from user_table'
        check_result = new_engine.filter_sql(sql=banned_sql, limit_num=10)
        self.assertEqual(check_result, "select top 10 user from user_table")

    def test_execute_check(self):
        new_engine = MssqlEngine(instance=self.ins1)
        test_sql = 'use database\ngo\nsome sql1\nGO\nsome sql2\n\r\nGo\nsome sql3\n\r\ngO\n'
        check_result = new_engine.execute_check(db_name=None, sql=test_sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[1].__dict__['sql'], "use database\n")
        self.assertEqual(check_result.rows[2].__dict__['sql'], "\nsome sql1\n")
        self.assertEqual(check_result.rows[4].__dict__['sql'], "\nsome sql3\n\r\n")

    @patch('sql.engines.mssql.MssqlEngine.execute')
    def test_execute_workflow(self, mock_execute):
        mock_execute.return_value.error = None
        new_engine = MssqlEngine(instance=self.ins1)
        new_engine.execute_workflow(self.wf)
        # 有多少个备份表, 就需要execute多少次, 另外加上一条实际执行的次数
        mock_execute.assert_called()
        self.assertEqual(1, mock_execute.call_count)

    @patch('sql.engines.mssql.MssqlEngine.get_connection')
    def test_execute(self, mock_connect):
        mock_cursor = Mock()
        mock_connect.return_value.cursor = mock_cursor
        new_engine = MssqlEngine(instance=self.ins1)
        execute_result = new_engine.execute('some_db', 'some_sql')
        # 验证结果, 无异常
        self.assertIsNone(execute_result.error)
        self.assertEqual('some_sql', execute_result.full_sql)
        self.assertEqual(2, len(execute_result.rows))
        mock_cursor.return_value.execute.assert_called()
        mock_cursor.return_value.commit.assert_called()
        mock_cursor.reset_mock()
        # 验证异常
        mock_cursor.return_value.execute.side_effect = Exception('Boom! some exception!')
        execute_result = new_engine.execute('some_db', 'some_sql')
        self.assertIn('Boom! some exception!', execute_result.error)
        self.assertEqual('some_sql', execute_result.full_sql)
        self.assertEqual(2, len(execute_result.rows))
        mock_cursor.return_value.commit.assert_not_called()
        mock_cursor.return_value.rollback.assert_called()


class TestMysql(TestCase):

    def setUp(self):
        self.ins1 = Instance(instance_name='some_ins', type='slave', db_type='mysql', host='some_host',
                             port=1366, user='ins_user', password='some_str')
        self.ins1.save()
        self.sys_config = SysConfig()
        self.wf = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer_display='',
            audit_auth_groups='some_group',
            create_time=datetime.now() - timedelta(days=1),
            status='workflow_finish',
            is_backup=True,
            instance=self.ins1,
            db_name='some_db',
            syntax_type=1
        )
        SqlWorkflowContent.objects.create(workflow=self.wf)

    def tearDown(self):
        self.ins1.delete()
        self.sys_config.purge()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()

    @patch('MySQLdb.connect')
    def test_engine_base_info(self, _conn):
        new_engine = MysqlEngine(instance=self.ins1)
        self.assertEqual(new_engine.name, 'MySQL')
        self.assertEqual(new_engine.info, 'MySQL engine')

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
        self.assertEqual(dbs.rows, ['db_1', 'db_2'])

    @patch.object(MysqlEngine, 'query')
    def testAllTables(self, mock_query):
        table_result = ResultSet()
        table_result.rows = [('tb_1', 'some_des'), ('tb_2', 'some_des')]
        mock_query.return_value = table_result
        new_engine = MysqlEngine(instance=self.ins1)
        tables = new_engine.get_all_tables('some_db')
        mock_query.assert_called_once_with(db_name='some_db', sql=ANY)
        self.assertEqual(tables.rows, ['tb_1', 'tb_2'])

    @patch.object(MysqlEngine, 'query')
    def testAllColumns(self, mock_query):
        db_result = ResultSet()
        db_result.rows = [('col_1', 'type'), ('col_2', 'type2')]
        mock_query.return_value = db_result
        new_engine = MysqlEngine(instance=self.ins1)
        dbs = new_engine.get_all_columns_by_tb('some_db', 'some_tb')
        self.assertEqual(dbs.rows, ['col_1', 'col_2'])

    @patch.object(MysqlEngine, 'query')
    def testDescribe(self, mock_query):
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.describe_table('some_db', 'some_db')
        mock_query.assert_called_once()

    def testQueryCheck(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = '-- 测试\n select user from usertable'
        check_result = new_engine.query_check(db_name='some_db', sql=sql_without_limit)
        self.assertEqual(check_result['filtered_sql'], 'select user from usertable')

    def test_query_check_wrong_sql(self):
        new_engine = MysqlEngine(instance=self.ins1)
        wrong_sql = '-- 测试'
        check_result = new_engine.query_check(db_name='some_db', sql=wrong_sql)
        self.assertDictEqual(check_result,
                             {'msg': '不支持的查询语法类型!', 'bad_query': True, 'filtered_sql': '-- 测试', 'has_star': False})

    def test_query_check_update_sql(self):
        new_engine = MysqlEngine(instance=self.ins1)
        update_sql = 'update user set id=0'
        check_result = new_engine.query_check(db_name='some_db', sql=update_sql)
        self.assertDictEqual(check_result,
                             {'msg': '不支持的查询语法类型!', 'bad_query': True, 'filtered_sql': 'update user set id=0',
                              'has_star': False})

    def test_filter_sql_with_delimiter(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = 'select user from usertable;'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=100)
        self.assertEqual(check_result, 'select user from usertable limit 100;')

    def test_filter_sql_without_delimiter(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = 'select user from usertable'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=100)
        self.assertEqual(check_result, 'select user from usertable limit 100;')

    def test_filter_sql_with_limit(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = 'select user from usertable limit 10'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, 'select user from usertable limit 1;')

    def test_filter_sql_with_limit_min(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = 'select user from usertable limit 10'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=100)
        self.assertEqual(check_result, 'select user from usertable limit 10;')

    def test_filter_sql_with_limit_offset(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = 'select user from usertable limit 10 offset 100'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, 'select user from usertable limit 1 offset 100;')

    def test_filter_sql_with_limit_nn(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = 'select user from usertable limit 10, 100'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, 'select user from usertable limit 10,1;')

    def test_filter_sql_upper(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = 'SELECT USER FROM usertable LIMIT 10, 100'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, 'SELECT USER FROM usertable limit 10,1;')

    def test_filter_sql_not_select(self):
        new_engine = MysqlEngine(instance=self.ins1)
        sql_without_limit = 'show create table usertable;'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, 'show create table usertable;')

    @patch('sql.engines.mysql.data_masking', return_value=ResultSet())
    def test_query_masking(self, _data_masking):
        query_result = ResultSet()
        new_engine = MysqlEngine(instance=self.ins1)
        masking_result = new_engine.query_masking(db_name='archery', sql='select 1', resultset=query_result)
        self.assertIsInstance(masking_result, ResultSet)

    @patch('sql.engines.mysql.data_masking', return_value=ResultSet())
    def test_query_masking_not_select(self, _data_masking):
        query_result = ResultSet()
        new_engine = MysqlEngine(instance=self.ins1)
        masking_result = new_engine.query_masking(db_name='archery', sql='explain select 1', resultset=query_result)
        self.assertEqual(masking_result, query_result)

    @patch('sql.engines.mysql.GoInceptionEngine')
    def test_execute_check_select_sql(self, _inception_engine):
        self.sys_config.set('goinception', 'true')
        sql = 'select * from user'
        inc_row = ReviewResult(id=1,
                               errlevel=0,
                               stagestatus='Audit completed',
                               errormessage='None',
                               sql=sql,
                               affected_rows=0,
                               execute_time='', )
        row = ReviewResult(id=1, errlevel=2,
                           stagestatus='驳回不支持语句',
                           errormessage='仅支持DML和DDL语句，查询语句请使用SQL查询功能！',
                           sql=sql)
        _inception_engine.return_value.execute_check.return_value = ReviewSet(full_sql=sql, rows=[inc_row])
        new_engine = MysqlEngine(instance=self.ins1)
        check_result = new_engine.execute_check(db_name='archery', sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch('sql.engines.mysql.GoInceptionEngine')
    def test_execute_check_critical_sql(self, _inception_engine):
        self.sys_config.set('goinception', 'true')
        self.sys_config.set('critical_ddl_regex', '^|update')
        self.sys_config.get_all_config()
        sql = 'update user set id=1'
        inc_row = ReviewResult(id=1,
                               errlevel=0,
                               stagestatus='Audit completed',
                               errormessage='None',
                               sql=sql,
                               affected_rows=0,
                               execute_time='', )
        row = ReviewResult(id=1, errlevel=2,
                           stagestatus='驳回高危SQL',
                           errormessage='禁止提交匹配' + '^|update' + '条件的语句！',
                           sql=sql)
        _inception_engine.return_value.execute_check.return_value = ReviewSet(full_sql=sql, rows=[inc_row])
        new_engine = MysqlEngine(instance=self.ins1)
        check_result = new_engine.execute_check(db_name='archery', sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch('sql.engines.mysql.GoInceptionEngine')
    def test_execute_check_normal_sql(self, _inception_engine):
        self.sys_config.set('goinception', 'true')
        sql = 'update user set id=1'
        row = ReviewResult(id=1,
                           errlevel=0,
                           stagestatus='Audit completed',
                           errormessage='None',
                           sql=sql,
                           affected_rows=0,
                           execute_time=0, )
        _inception_engine.return_value.execute_check.return_value = ReviewSet(full_sql=sql, rows=[row])
        new_engine = MysqlEngine(instance=self.ins1)
        check_result = new_engine.execute_check(db_name='archery', sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch('sql.engines.mysql.GoInceptionEngine')
    def test_execute_check_normal_sql_with_Exception(self, _inception_engine):
        sql = 'update user set id=1'
        _inception_engine.return_value.execute_check.side_effect = RuntimeError()
        new_engine = MysqlEngine(instance=self.ins1)
        with self.assertRaises(RuntimeError):
            new_engine.execute_check(db_name=0, sql=sql)

    @patch.object(MysqlEngine, 'query')
    @patch('sql.engines.mysql.GoInceptionEngine')
    def test_execute_workflow(self, _inception_engine, _query):
        self.sys_config.set('goinception', 'true')
        sql = 'update user set id=1'
        _inception_engine.return_value.execute.return_value = ReviewSet(full_sql=sql)
        _query.return_value.rows = (('0',),)
        new_engine = MysqlEngine(instance=self.ins1)
        execute_result = new_engine.execute_workflow(self.wf)
        self.assertIsInstance(execute_result, ReviewSet)

    @patch('MySQLdb.connect.cursor.execute')
    @patch('MySQLdb.connect.cursor')
    @patch('MySQLdb.connect')
    def test_execute(self, _connect, _cursor, _execute):
        new_engine = MysqlEngine(instance=self.ins1)
        execute_result = new_engine.execute(self.wf)
        self.assertIsInstance(execute_result, ResultSet)

    @patch('MySQLdb.connect')
    def test_server_version(self, _connect):
        _connect.return_value.get_server_info.return_value = '5.7.20-16log'
        new_engine = MysqlEngine(instance=self.ins1)
        server_version = new_engine.server_version
        self.assertTupleEqual(server_version, (5, 7, 20))

    @patch.object(MysqlEngine, 'query')
    def test_get_variables_not_filter(self, _query):
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.get_variables()
        _query.assert_called_once()

    @patch('MySQLdb.connect')
    @patch.object(MysqlEngine, 'query')
    def test_get_variables_filter(self, _query, _connect):
        _connect.return_value.get_server_info.return_value = '5.7.20-16log'
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.get_variables(variables=['binlog_format'])
        _query.assert_called()

    @patch.object(MysqlEngine, 'query')
    def test_set_variable(self, _query):
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.set_variable('binlog_format', 'ROW')
        _query.assert_called_once_with(sql="set global binlog_format=ROW;")

    @patch('sql.engines.mysql.GoInceptionEngine')
    def test_osc_go_inception(self, _inception_engine):
        self.sys_config.set('goinception', 'false')
        _inception_engine.return_value.osc_control.return_value = ReviewSet()
        command = 'get'
        sqlsha1 = 'xxxxx'
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.osc_control(sqlsha1=sqlsha1, command=command)

    @patch('sql.engines.mysql.GoInceptionEngine')
    def test_osc_inception(self, _inception_engine):
        self.sys_config.set('goinception', 'true')
        _inception_engine.return_value.osc_control.return_value = ReviewSet()
        command = 'get'
        sqlsha1 = 'xxxxx'
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.osc_control(sqlsha1=sqlsha1, command=command)

    @patch.object(MysqlEngine, 'query')
    def test_kill_connection(self, _query):
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.kill_connection(100)
        _query.assert_called_once_with(sql="kill 100")

    @patch.object(MysqlEngine, 'query')
    def test_seconds_behind_master(self, _query):
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.seconds_behind_master
        _query.assert_called_once_with(sql="show slave status", close_conn=False,
                                       cursorclass=MySQLdb.cursors.DictCursor)


class TestRedis(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ins = Instance(instance_name='some_ins', type='slave', db_type='redis', mode='standalone',
                           host='some_host', port=1366, user='ins_user', password='some_str')
        cls.ins.save()

    @classmethod
    def tearDownClass(cls):
        cls.ins.delete()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()

    @patch('redis.Redis')
    def test_engine_base_info(self, _conn):
        new_engine = RedisEngine(instance=self.ins)
        self.assertEqual(new_engine.name, 'Redis')
        self.assertEqual(new_engine.info, 'Redis engine')

    @patch('redis.Redis')
    def test_get_connection(self, _conn):
        new_engine = RedisEngine(instance=self.ins)
        new_engine.get_connection()
        _conn.assert_called_once()

    @patch('redis.Redis.execute_command', return_value=[1, 2, 3])
    def test_query_return_list(self, _execute_command):
        new_engine = RedisEngine(instance=self.ins)
        query_result = new_engine.query(db_name=0, sql='keys *', limit_num=100)
        self.assertIsInstance(query_result, ResultSet)
        self.assertTupleEqual(query_result.rows, ([1], [2], [3]))

    @patch('redis.Redis.execute_command', return_value='text')
    def test_query_return_str(self, _execute_command):
        new_engine = RedisEngine(instance=self.ins)
        query_result = new_engine.query(db_name=0, sql='keys *', limit_num=100)
        self.assertIsInstance(query_result, ResultSet)
        self.assertTupleEqual(query_result.rows, (['text'],))

    @patch('redis.Redis.execute_command', return_value='text')
    def test_query_execute(self, _execute_command):
        new_engine = RedisEngine(instance=self.ins)
        query_result = new_engine.query(db_name=0, sql='keys *', limit_num=100)
        self.assertIsInstance(query_result, ResultSet)
        self.assertTupleEqual(query_result.rows, (['text'],))

    @patch('redis.Redis.config_get', return_value={"databases": 4})
    def test_get_all_databases(self, _config_get):
        new_engine = RedisEngine(instance=self.ins)
        dbs = new_engine.get_all_databases()
        self.assertListEqual(dbs.rows, ['0', '1', '2', '3'])

    def test_query_check_safe_cmd(self):
        safe_cmd = "keys 1*"
        new_engine = RedisEngine(instance=self.ins)
        check_result = new_engine.query_check(db_name=0, sql=safe_cmd)
        self.assertDictEqual(check_result,
                             {'msg': '禁止执行该命令！', 'bad_query': True, 'filtered_sql': safe_cmd, 'has_star': False})

    def test_query_check_danger_cmd(self):
        safe_cmd = "keys *"
        new_engine = RedisEngine(instance=self.ins)
        check_result = new_engine.query_check(db_name=0, sql=safe_cmd)
        self.assertDictEqual(check_result,
                             {'msg': '禁止执行该命令！', 'bad_query': True, 'filtered_sql': safe_cmd, 'has_star': False})

    def test_filter_sql(self):
        safe_cmd = "keys 1*"
        new_engine = RedisEngine(instance=self.ins)
        check_result = new_engine.filter_sql(sql=safe_cmd, limit_num=100)
        self.assertEqual(check_result, 'keys 1*')

    def test_query_masking(self):
        query_result = ResultSet()
        new_engine = RedisEngine(instance=self.ins)
        masking_result = new_engine.query_masking(db_name=0, sql='', resultset=query_result)
        self.assertEqual(masking_result, query_result)

    def test_execute_check(self):
        sql = 'set 1 1'
        row = ReviewResult(id=1,
                           errlevel=0,
                           stagestatus='Audit completed',
                           errormessage='None',
                           sql=sql,
                           affected_rows=0,
                           execute_time=0)
        new_engine = RedisEngine(instance=self.ins)
        check_result = new_engine.execute_check(db_name=0, sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch('redis.Redis.execute_command', return_value='text')
    def test_execute_workflow_success(self, _execute_command):
        sql = 'set 1 1'
        row = ReviewResult(id=1,
                           errlevel=0,
                           stagestatus='Execute Successfully',
                           errormessage='None',
                           sql=sql,
                           affected_rows=0,
                           execute_time=0)
        wf = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer_display='',
            audit_auth_groups='some_group',
            create_time=datetime.now() - timedelta(days=1),
            status='workflow_finish',
            is_backup=True,
            instance=self.ins,
            db_name='some_db',
            syntax_type=1
        )
        SqlWorkflowContent.objects.create(workflow=wf, sql_content=sql)
        new_engine = RedisEngine(instance=self.ins)
        execute_result = new_engine.execute_workflow(workflow=wf)
        self.assertIsInstance(execute_result, ReviewSet)
        self.assertEqual(execute_result.rows[0].__dict__.keys(), row.__dict__.keys())


class TestPgSQL(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ins = Instance(instance_name='some_ins', type='slave', db_type='pgsql', host='some_host',
                           port=1366, user='ins_user', password='some_str')
        cls.ins.save()
        cls.sys_config = SysConfig()

    @classmethod
    def tearDownClass(cls):
        cls.ins.delete()
        cls.sys_config.purge()

    @patch('psycopg2.connect')
    def test_engine_base_info(self, _conn):
        new_engine = PgSQLEngine(instance=self.ins)
        self.assertEqual(new_engine.name, 'PgSQL')
        self.assertEqual(new_engine.info, 'PgSQL engine')

    @patch('psycopg2.connect')
    def test_get_connection(self, _conn):
        new_engine = PgSQLEngine(instance=self.ins)
        new_engine.get_connection("some_dbname")
        _conn.assert_called_once()

    @patch('psycopg2.connect.cursor.execute')
    @patch('psycopg2.connect.cursor')
    @patch('psycopg2.connect')
    def test_query(self, _conn, _cursor, _execute):
        _conn.return_value.cursor.return_value.fetchmany.return_value = [(1,)]
        new_engine = PgSQLEngine(instance=self.ins)
        query_result = new_engine.query(db_name="some_dbname", sql='select 1', limit_num=100, schema_name="some_schema")
        self.assertIsInstance(query_result, ResultSet)
        self.assertListEqual(query_result.rows, [(1,)])

    @patch('psycopg2.connect.cursor.execute')
    @patch('psycopg2.connect.cursor')
    @patch('psycopg2.connect')
    def test_query_not_limit(self, _conn, _cursor, _execute):
        _conn.return_value.cursor.return_value.fetchall.return_value = [(1,)]
        new_engine = PgSQLEngine(instance=self.ins)
        query_result = new_engine.query(db_name="some_dbname", sql='select 1', limit_num=0, schema_name="some_schema")
        self.assertIsInstance(query_result, ResultSet)
        self.assertListEqual(query_result.rows, [(1,)])

    @patch('sql.engines.pgsql.PgSQLEngine.query',
           return_value=ResultSet(rows=[('postgres',), ('archery',), ('template1',), ('template0',)]))
    def test_get_all_databases(self, query):
        new_engine = PgSQLEngine(instance=self.ins)
        dbs = new_engine.get_all_databases()
        self.assertListEqual(dbs.rows, ['archery'])

    @patch('sql.engines.pgsql.PgSQLEngine.query',
           return_value=ResultSet(rows=[('information_schema',), ('archery',), ('pg_catalog',)]))
    def test_get_all_schemas(self, _query):
        new_engine = PgSQLEngine(instance=self.ins)
        schemas = new_engine.get_all_schemas(db_name='archery')
        self.assertListEqual(schemas.rows, ['archery'])

    @patch('sql.engines.pgsql.PgSQLEngine.query', return_value=ResultSet(rows=[('test',), ('test2',)]))
    def test_get_all_tables(self, _query):
        new_engine = PgSQLEngine(instance=self.ins)
        tables = new_engine.get_all_tables(db_name='archery', schema_name='archery')
        self.assertListEqual(tables.rows, ['test2'])

    @patch('sql.engines.pgsql.PgSQLEngine.query',
           return_value=ResultSet(rows=[('id',), ('name',)]))
    def test_get_all_columns_by_tb(self, _query):
        new_engine = PgSQLEngine(instance=self.ins)
        columns = new_engine.get_all_columns_by_tb(db_name='archery', tb_name='test2', schema_name='archery')
        self.assertListEqual(columns.rows, ['id', 'name'])

    @patch('sql.engines.pgsql.PgSQLEngine.query',
           return_value=ResultSet(rows=[('postgres',), ('archery',), ('template1',), ('template0',)]))
    def test_describe_table(self, _query):
        new_engine = PgSQLEngine(instance=self.ins)
        describe = new_engine.describe_table(db_name='archery', schema_name='archery', tb_name='text')
        self.assertIsInstance(describe, ResultSet)

    def test_query_check_disable_sql(self):
        sql = "update xxx set a=1 "
        new_engine = PgSQLEngine(instance=self.ins)
        check_result = new_engine.query_check(db_name='archery', sql=sql)
        self.assertDictEqual(check_result,
                             {'msg': '不支持的查询语法类型!', 'bad_query': True, 'filtered_sql': sql.strip(), 'has_star': False})

    def test_query_check_star_sql(self):
        sql = "select * from xx "
        new_engine = PgSQLEngine(instance=self.ins)
        check_result = new_engine.query_check(db_name='archery', sql=sql)
        self.assertDictEqual(check_result,
                             {'msg': 'SQL语句中含有 * ', 'bad_query': False, 'filtered_sql': sql.strip(), 'has_star': True})

    def test_filter_sql_with_delimiter(self):
        sql = "select * from xx;"
        new_engine = PgSQLEngine(instance=self.ins)
        check_result = new_engine.filter_sql(sql=sql, limit_num=100)
        self.assertEqual(check_result, "select * from xx limit 100;")

    def test_filter_sql_without_delimiter(self):
        sql = "select * from xx"
        new_engine = PgSQLEngine(instance=self.ins)
        check_result = new_engine.filter_sql(sql=sql, limit_num=100)
        self.assertEqual(check_result, "select * from xx limit 100;")

    def test_filter_sql_with_limit(self):
        sql = "select * from xx limit 10"
        new_engine = PgSQLEngine(instance=self.ins)
        check_result = new_engine.filter_sql(sql=sql, limit_num=1)
        self.assertEqual(check_result, "select * from xx limit 10;")

    def test_query_masking(self):
        query_result = ResultSet()
        new_engine = PgSQLEngine(instance=self.ins)
        masking_result = new_engine.query_masking(db_name=0, sql='', resultset=query_result)
        self.assertEqual(masking_result, query_result)

    def test_execute_check_select_sql(self):
        sql = 'select * from user;'
        row = ReviewResult(id=1, errlevel=2,
                           stagestatus='驳回不支持语句',
                           errormessage='仅支持DML和DDL语句，查询语句请使用SQL查询功能！',
                           sql=sql)
        new_engine = PgSQLEngine(instance=self.ins)
        check_result = new_engine.execute_check(db_name='archery', sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    def test_execute_check_critical_sql(self):
        self.sys_config.set('critical_ddl_regex', '^|update')
        self.sys_config.get_all_config()
        sql = 'update user set id=1'
        row = ReviewResult(id=1, errlevel=2,
                           stagestatus='驳回高危SQL',
                           errormessage='禁止提交匹配' + '^|update' + '条件的语句！',
                           sql=sql)
        new_engine = PgSQLEngine(instance=self.ins)
        check_result = new_engine.execute_check(db_name='archery', sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    def test_execute_check_normal_sql(self):
        self.sys_config.purge()
        sql = 'alter table tb set id=1'
        row = ReviewResult(id=1,
                           errlevel=0,
                           stagestatus='Audit completed',
                           errormessage='None',
                           sql=sql,
                           affected_rows=0,
                           execute_time=0, )
        new_engine = PgSQLEngine(instance=self.ins)
        check_result = new_engine.execute_check(db_name='archery', sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch('psycopg2.connect.cursor.execute')
    @patch('psycopg2.connect.cursor')
    @patch('psycopg2.connect')
    def test_execute_workflow_success(self, _conn, _cursor, _execute):
        sql = 'update user set id=1'
        row = ReviewResult(id=1,
                           errlevel=0,
                           stagestatus='Execute Successfully',
                           errormessage='None',
                           sql=sql,
                           affected_rows=0,
                           execute_time=0)
        wf = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer_display='',
            audit_auth_groups='some_group',
            create_time=datetime.now() - timedelta(days=1),
            status='workflow_finish',
            is_backup=True,
            instance=self.ins,
            db_name='some_db',
            syntax_type=1
        )
        SqlWorkflowContent.objects.create(workflow=wf, sql_content=sql)
        new_engine = PgSQLEngine(instance=self.ins)
        execute_result = new_engine.execute_workflow(workflow=wf)
        self.assertIsInstance(execute_result, ReviewSet)
        self.assertEqual(execute_result.rows[0].__dict__.keys(), row.__dict__.keys())

    @patch('psycopg2.connect.cursor.execute')
    @patch('psycopg2.connect.cursor')
    @patch('psycopg2.connect', return_value=RuntimeError)
    def test_execute_workflow_exception(self, _conn, _cursor, _execute):
        sql = 'update user set id=1'
        row = ReviewResult(id=1,
                           errlevel=2,
                           stagestatus='Execute Failed',
                           errormessage=f'异常信息：{f"Oracle命令执行报错，语句：{sql}"}',
                           sql=sql,
                           affected_rows=0,
                           execute_time=0, )
        wf = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer_display='',
            audit_auth_groups='some_group',
            create_time=datetime.now() - timedelta(days=1),
            status='workflow_finish',
            is_backup=True,
            instance=self.ins,
            db_name='some_db',
            syntax_type=1
        )
        SqlWorkflowContent.objects.create(workflow=wf, sql_content=sql)
        with self.assertRaises(AttributeError):
            new_engine = PgSQLEngine(instance=self.ins)
            execute_result = new_engine.execute_workflow(workflow=wf)
            self.assertIsInstance(execute_result, ReviewSet)
            self.assertEqual(execute_result.rows[0].__dict__.keys(), row.__dict__.keys())


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


class TestGoInception(TestCase):
    def setUp(self):
        self.ins = Instance.objects.create(instance_name='some_ins', type='slave', db_type='mysql',
                                           host='some_host',
                                           port=3306, user='ins_user', password='some_str')
        self.ins_inc = Instance.objects.create(instance_name='some_ins_inc', type='slave', db_type='goinception',
                                               host='some_host', port=4000)
        self.wf = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer_display='',
            audit_auth_groups='some_group',
            create_time=datetime.now() - timedelta(days=1),
            status='workflow_finish',
            is_backup=True,
            instance=self.ins,
            db_name='some_db',
            syntax_type=1
        )
        SqlWorkflowContent.objects.create(workflow=self.wf)

    def tearDown(self):
        self.ins.delete()
        self.ins_inc.delete()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()

    @patch('MySQLdb.connect')
    def test_get_connection(self, _connect):
        new_engine = GoInceptionEngine()
        new_engine.get_connection()
        _connect.assert_called_once()

    @patch('sql.engines.goinception.GoInceptionEngine.query')
    def test_execute_check_normal_sql(self, _query):
        sql = 'update user set id=100'
        row = [1, 'CHECKED', 0, 'Audit completed', 'None', 'use archery', 0, "'0_0_0'", 'None', '0', '', '']
        _query.return_value = ResultSet(full_sql=sql, rows=[row])
        new_engine = GoInceptionEngine()
        check_result = new_engine.execute_check(instance=self.ins, db_name=0, sql=sql)
        self.assertIsInstance(check_result, ReviewSet)

    @patch('sql.engines.goinception.GoInceptionEngine.query')
    def test_execute_exception(self, _query):
        sql = 'update user set id=100'
        row = [1, 'CHECKED', 1, 'Execute failed', 'None', 'use archery', 0, "'0_0_0'", 'None', '0', '', '']
        column_list = ['order_id', 'stage', 'error_level', 'stage_status', 'error_message', 'sql',
                       'affected_rows', 'sequence', 'backup_dbname', 'execute_time', 'sqlsha1', 'backup_time']
        _query.return_value = ResultSet(full_sql=sql, rows=[row], column_list=column_list)
        new_engine = GoInceptionEngine()
        execute_result = new_engine.execute(workflow=self.wf)
        self.assertIsInstance(execute_result, ReviewSet)

    @patch('sql.engines.goinception.GoInceptionEngine.query')
    def test_execute_finish(self, _query):
        sql = 'update user set id=100'
        row = [1, 'CHECKED', 0, 'Execute Successfully', 'None', 'use archery', 0, "'0_0_0'", 'None', '0', '', '']
        column_list = ['order_id', 'stage', 'error_level', 'stage_status', 'error_message', 'sql',
                       'affected_rows', 'sequence', 'backup_dbname', 'execute_time', 'sqlsha1', 'backup_time']
        _query.return_value = ResultSet(full_sql=sql, rows=[row], column_list=column_list)
        new_engine = GoInceptionEngine()
        execute_result = new_engine.execute(workflow=self.wf)
        self.assertIsInstance(execute_result, ReviewSet)

    @patch('MySQLdb.connect.cursor.execute')
    @patch('MySQLdb.connect.cursor')
    @patch('MySQLdb.connect')
    def test_query(self, _conn, _cursor, _execute):
        _conn.return_value.cursor.return_value.fetchall.return_value = [(1,)]
        new_engine = GoInceptionEngine()
        query_result = new_engine.query(db_name=0, sql='select 1', limit_num=100)
        self.assertIsInstance(query_result, ResultSet)

    @patch('MySQLdb.connect.cursor.execute')
    @patch('MySQLdb.connect.cursor')
    @patch('MySQLdb.connect')
    def test_query_not_limit(self, _conn, _cursor, _execute):
        _conn.return_value.cursor.return_value.fetchall.return_value = [(1,)]
        new_engine = GoInceptionEngine(instance=self.ins)
        query_result = new_engine.query(db_name=0, sql='select 1', limit_num=0)
        self.assertIsInstance(query_result, ResultSet)

    @patch('sql.engines.goinception.GoInceptionEngine.query')
    def test_osc_get(self, _query):
        new_engine = GoInceptionEngine()
        command = 'get'
        sqlsha1 = 'xxxxx'
        sql = f"inception get osc_percent '{sqlsha1}';"
        _query.return_value = ResultSet(full_sql=sql, rows=[], column_list=[])
        new_engine.osc_control(sqlsha1=sqlsha1, command=command)
        _query.assert_called_once_with(sql=sql)

    @patch('sql.engines.goinception.GoInceptionEngine.query')
    def test_osc_pause(self, _query):
        new_engine = GoInceptionEngine()
        command = 'pause'
        sqlsha1 = 'xxxxx'
        sql = f"inception {command} osc '{sqlsha1}';"
        _query.return_value = ResultSet(full_sql=sql, rows=[], column_list=[])
        new_engine.osc_control(sqlsha1=sqlsha1, command=command)
        _query.assert_called_once_with(sql=sql)

    @patch('sql.engines.goinception.GoInceptionEngine.query')
    def test_osc_resume(self, _query):
        new_engine = GoInceptionEngine()
        command = 'resume'
        sqlsha1 = 'xxxxx'
        sql = f"inception {command} osc '{sqlsha1}';"
        _query.return_value = ResultSet(full_sql=sql, rows=[], column_list=[])
        new_engine.osc_control(sqlsha1=sqlsha1, command=command)
        _query.assert_called_once_with(sql=sql)

    @patch('sql.engines.goinception.GoInceptionEngine.query')
    def test_osc_kill(self, _query):
        new_engine = GoInceptionEngine()
        command = 'kill'
        sqlsha1 = 'xxxxx'
        sql = f"inception kill osc '{sqlsha1}';"
        _query.return_value = ResultSet(full_sql=sql, rows=[], column_list=[])
        new_engine.osc_control(sqlsha1=sqlsha1, command=command)
        _query.assert_called_once_with(sql=sql)

    @patch('sql.engines.goinception.GoInceptionEngine.query')
    def test_get_variables(self, _query):
        new_engine = GoInceptionEngine(instance=self.ins_inc)
        new_engine.get_variables()
        sql = f"inception get variables;"
        _query.assert_called_once_with(sql=sql)

    @patch('sql.engines.goinception.GoInceptionEngine.query')
    def test_get_variables_filter(self, _query):
        new_engine = GoInceptionEngine(instance=self.ins_inc)
        new_engine.get_variables(variables=['inception_osc_on'])
        sql = f"inception get variables like 'inception_osc_on';"
        _query.assert_called_once_with(sql=sql)

    @patch('sql.engines.goinception.GoInceptionEngine.query')
    def test_set_variable(self, _query):
        new_engine = GoInceptionEngine(instance=self.ins)
        new_engine.set_variable('inception_osc_on', 'on')
        _query.assert_called_once_with(sql="inception set inception_osc_on=on;")


class TestOracle(TestCase):
    """Oracle 测试"""

    def setUp(self):
        self.ins = Instance.objects.create(instance_name='some_ins', type='slave', db_type='oracle',
                                           host='some_host', port=3306, user='ins_user', password='some_str',
                                           sid='some_id')
        self.wf = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer_display='',
            audit_auth_groups='some_group',
            create_time=datetime.now() - timedelta(days=1),
            status='workflow_finish',
            is_backup=True,
            instance=self.ins,
            db_name='some_db',
            syntax_type=1
        )
        SqlWorkflowContent.objects.create(workflow=self.wf)
        self.sys_config = SysConfig()

    def tearDown(self):
        self.ins.delete()
        self.sys_config.purge()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()

    @patch('cx_Oracle.makedsn')
    @patch('cx_Oracle.connect')
    def test_get_connection(self, _connect, _makedsn):
        # 填写 sid 测试
        new_engine = OracleEngine(self.ins)
        new_engine.get_connection()
        _connect.assert_called_once()
        _makedsn.assert_called_once()
        # 填写 service_name 测试
        _connect.reset_mock()
        _makedsn.reset_mock()
        self.ins.service_name = 'some_service'
        self.ins.sid = ''
        self.ins.save()
        new_engine = OracleEngine(self.ins)
        new_engine.get_connection()
        _connect.assert_called_once()
        _makedsn.assert_called_once()
        # 都不填写, 检测 ValueError
        _connect.reset_mock()
        _makedsn.reset_mock()
        self.ins.service_name = ''
        self.ins.sid = ''
        self.ins.save()
        new_engine = OracleEngine(self.ins)
        with self.assertRaises(ValueError):
            new_engine.get_connection()

    @patch('cx_Oracle.connect')
    def test_engine_base_info(self, _conn):
        new_engine = OracleEngine(instance=self.ins)
        self.assertEqual(new_engine.name, 'Oracle')
        self.assertEqual(new_engine.info, 'Oracle engine')
        _conn.return_value.version = '12.1.0.2.0'
        self.assertTupleEqual(new_engine.server_version, ('12', '1', '0'))

    @patch('cx_Oracle.connect.cursor.execute')
    @patch('cx_Oracle.connect.cursor')
    @patch('cx_Oracle.connect')
    def test_query(self, _conn, _cursor, _execute):
        _conn.return_value.cursor.return_value.fetchmany.return_value = [(1,)]
        new_engine = OracleEngine(instance=self.ins)
        query_result = new_engine.query(db_name='archery', sql='select 1', limit_num=100)
        self.assertIsInstance(query_result, ResultSet)
        self.assertListEqual(query_result.rows, [(1,)])

    @patch('cx_Oracle.connect.cursor.execute')
    @patch('cx_Oracle.connect.cursor')
    @patch('cx_Oracle.connect')
    def test_query_not_limit(self, _conn, _cursor, _execute):
        _conn.return_value.cursor.return_value.fetchall.return_value = [(1,)]
        new_engine = OracleEngine(instance=self.ins)
        query_result = new_engine.query(db_name=0, sql='select 1', limit_num=0)
        self.assertIsInstance(query_result, ResultSet)
        self.assertListEqual(query_result.rows, [(1,)])

    @patch('sql.engines.oracle.OracleEngine.query',
           return_value=ResultSet(rows=[('AUD_SYS',), ('archery',), ('ANONYMOUS',)]))
    def test_get_all_databases(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        dbs = new_engine.get_all_databases()
        self.assertListEqual(dbs.rows, ['archery'])

    @patch('sql.engines.oracle.OracleEngine.query',
           return_value=ResultSet(rows=[('AUD_SYS',), ('archery',), ('ANONYMOUS',)]))
    def test__get_all_databases(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        dbs = new_engine._get_all_databases()
        self.assertListEqual(dbs.rows, ['AUD_SYS', 'archery', 'ANONYMOUS'])

    @patch('sql.engines.oracle.OracleEngine.query',
           return_value=ResultSet(rows=[('archery',)]))
    def test__get_all_instances(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        dbs = new_engine._get_all_instances()
        self.assertListEqual(dbs.rows, ['archery'])

    @patch('sql.engines.oracle.OracleEngine.query',
           return_value=ResultSet(rows=[('ANONYMOUS',), ('archery',), ('SYSTEM',)]))
    def test_get_all_schemas(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        schemas = new_engine._get_all_schemas()
        self.assertListEqual(schemas.rows, ['archery'])

    @patch('sql.engines.oracle.OracleEngine.query', return_value=ResultSet(rows=[('test',), ('test2',)]))
    def test_get_all_tables(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        tables = new_engine.get_all_tables(db_name='archery')
        self.assertListEqual(tables.rows, ['test2'])

    @patch('sql.engines.oracle.OracleEngine.query',
           return_value=ResultSet(rows=[('id',), ('name',)]))
    def test_get_all_columns_by_tb(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        columns = new_engine.get_all_columns_by_tb(db_name='archery', tb_name='test2')
        self.assertListEqual(columns.rows, ['id', 'name'])

    @patch('sql.engines.oracle.OracleEngine.query',
           return_value=ResultSet(rows=[('archery',), ('template1',), ('template0',)]))
    def test_describe_table(self, _query):
        new_engine = OracleEngine(instance=self.ins)
        describe = new_engine.describe_table(db_name='archery', tb_name='text')
        self.assertIsInstance(describe, ResultSet)

    def test_query_check_disable_sql(self):
        sql = "update xxx set a=1;"
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.query_check(db_name='archery', sql=sql)
        self.assertDictEqual(check_result,
                             {'msg': '不支持语法!', 'bad_query': True, 'filtered_sql': sql.strip(';'),
                              'has_star': False})

    @patch('sql.engines.oracle.OracleEngine.explain_check', return_value={'msg': '', 'rows': 0})
    def test_query_check_star_sql(self, _explain_check):
        sql = "select * from xx;"
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.query_check(db_name='archery', sql=sql)
        self.assertDictEqual(check_result,
                             {'msg': '禁止使用 * 关键词\n', 'bad_query': False, 'filtered_sql': sql.strip(';'),
                              'has_star': True})

    def test_query_check_IndexError(self):
        sql = ""
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.query_check(db_name='archery', sql=sql)
        self.assertDictEqual(check_result,
                             {'msg': '没有有效的SQL语句', 'bad_query': True, 'filtered_sql': sql.strip(), 'has_star': False})

    def test_filter_sql_with_delimiter(self):
        sql = "select * from xx;"
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.filter_sql(sql=sql, limit_num=100)
        self.assertEqual(check_result, "select sql_audit.* from (select * from xx) sql_audit where rownum <= 100")

    def test_filter_sql_with_delimiter_and_where(self):
        sql = "select * from xx where id>1;"
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.filter_sql(sql=sql, limit_num=100)
        self.assertEqual(check_result,
                         "select sql_audit.* from (select * from xx where id>1) sql_audit where rownum <= 100")

    def test_filter_sql_without_delimiter(self):
        sql = "select * from xx;"
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.filter_sql(sql=sql, limit_num=100)
        self.assertEqual(check_result, "select sql_audit.* from (select * from xx) sql_audit where rownum <= 100")

    def test_filter_sql_with_limit(self):
        sql = "select * from xx limit 10;"
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.filter_sql(sql=sql, limit_num=1)
        self.assertEqual(check_result,
                         "select sql_audit.* from (select * from xx limit 10) sql_audit where rownum <= 1")

    def test_query_masking(self):
        query_result = ResultSet()
        new_engine = OracleEngine(instance=self.ins)
        masking_result = new_engine.query_masking(sql='select 1 from dual', resultset=query_result)
        self.assertEqual(masking_result, query_result)

    def test_execute_check_select_sql(self):
        sql = 'select * from user;'
        row = ReviewResult(id=1, errlevel=2,
                           stagestatus='驳回不支持语句',
                           errormessage='仅支持DML和DDL语句，查询语句请使用SQL查询功能！',
                           sql=sqlparse.format(sql, strip_comments=True, reindent=True, keyword_case='lower'))
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.execute_check(db_name='archery', sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    def test_execute_check_critical_sql(self):
        self.sys_config.set('critical_ddl_regex', '^|update')
        self.sys_config.get_all_config()
        sql = 'update user set id=1'
        row = ReviewResult(id=1, errlevel=2,
                           stagestatus='驳回高危SQL',
                           errormessage='禁止提交匹配' + '^|update' + '条件的语句！',
                           sql=sqlparse.format(sql, strip_comments=True, reindent=True, keyword_case='lower'))
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.execute_check(db_name='archery', sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch('sql.engines.oracle.OracleEngine.explain_check', return_value={'msg': '', 'rows': 0})
    @patch('sql.engines.oracle.OracleEngine.get_sql_first_object_name', return_value='tb')
    @patch('sql.engines.oracle.OracleEngine.object_name_check', return_value=True)
    def test_execute_check_normal_sql(self, _explain_check, _get_sql_first_object_name, _object_name_check):
        self.sys_config.purge()
        sql = 'alter table tb set id=1'
        row = ReviewResult(id=1,
                           errlevel=1,
                           stagestatus='当前平台，此语法不支持审核！',
                           errormessage='当前平台，此语法不支持审核！',
                           sql=sqlparse.format(sql, strip_comments=True, reindent=True, keyword_case='lower'),
                           affected_rows=0,
                           execute_time=0,
                           stmt_type='SQL',
                           object_owner='',
                           object_type='',
                           object_name='',
                           )
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.execute_check(db_name='archery', sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch('cx_Oracle.connect.cursor.execute')
    @patch('cx_Oracle.connect.cursor')
    @patch('cx_Oracle.connect')
    def test_execute_workflow_success(self, _conn, _cursor, _execute):
        sql = 'update user set id=1'
        review_row = ReviewResult(id=1,
                                  errlevel=0,
                                  stagestatus='Execute Successfully',
                                  errormessage='None',
                                  sql=sql,
                                  affected_rows=0,
                                  execute_time=0,
                                  stmt_type='SQL',
                                  object_owner='',
                                  object_type='',
                                  object_name='', )
        execute_row = ReviewResult(id=1,
                                   errlevel=0,
                                   stagestatus='Execute Successfully',
                                   errormessage='None',
                                   sql=sql,
                                   affected_rows=0,
                                   execute_time=0)
        wf = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer_display='',
            audit_auth_groups='some_group',
            create_time=datetime.now() - timedelta(days=1),
            status='workflow_finish',
            is_backup=True,
            instance=self.ins,
            db_name='some_db',
            syntax_type=1
        )
        SqlWorkflowContent.objects.create(workflow=wf, sql_content=sql,
                                          review_content=ReviewSet(rows=[review_row]).json())
        new_engine = OracleEngine(instance=self.ins)
        execute_result = new_engine.execute_workflow(workflow=wf)
        self.assertIsInstance(execute_result, ReviewSet)
        self.assertEqual(execute_result.rows[0].__dict__.keys(), execute_row.__dict__.keys())

    @patch('cx_Oracle.connect.cursor.execute')
    @patch('cx_Oracle.connect.cursor')
    @patch('cx_Oracle.connect', return_value=RuntimeError)
    def test_execute_workflow_exception(self, _conn, _cursor, _execute):
        sql = 'update user set id=1'
        row = ReviewResult(id=1,
                           errlevel=2,
                           stagestatus='Execute Failed',
                           errormessage=f'异常信息：{f"Oracle命令执行报错，语句：{sql}"}',
                           sql=sql,
                           affected_rows=0,
                           execute_time=0,
                           stmt_type='SQL',
                           object_owner='',
                           object_type='',
                           object_name='',
                           )
        wf = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer_display='',
            audit_auth_groups='some_group',
            create_time=datetime.now() - timedelta(days=1),
            status='workflow_finish',
            is_backup=True,
            instance=self.ins,
            db_name='some_db',
            syntax_type=1
        )
        SqlWorkflowContent.objects.create(workflow=wf, sql_content=sql, review_content=ReviewSet(rows=[row]).json())
        with self.assertRaises(AttributeError):
            new_engine = OracleEngine(instance=self.ins)
            execute_result = new_engine.execute_workflow(workflow=wf)
            self.assertIsInstance(execute_result, ReviewSet)
            self.assertEqual(execute_result.rows[0].__dict__.keys(), row.__dict__.keys())


class MongoTest(TestCase):
    def setUp(self) -> None:
        self.ins = Instance.objects.create(instance_name='some_ins', type='slave', db_type='mongo',
                                           host='some_host', port=3306, user='ins_user')
        self.engine = MongoEngine(instance=self.ins)

    def tearDown(self) -> None:
        self.ins.delete()

    @patch('sql.engines.mongo.pymongo')
    def test_get_connection(self, mock_pymongo):
        _ = self.engine.get_connection()
        mock_pymongo.MongoClient.assert_called_once()

    @patch('sql.engines.mongo.MongoEngine.get_connection')
    def test_query(self, mock_get_connection):
        # TODO 正常查询还没做
        test_sql = """db.job.find().count()"""
        self.assertIsInstance(self.engine.query('some_db', test_sql), ResultSet)

    @patch('sql.engines.mongo.MongoEngine.get_all_tables')
    def test_query_check(self, mock_get_all_tables):
        test_sql = """db.job.find().count()"""
        mock_get_all_tables.return_value.rows = ("job")
        check_result = self.engine.query_check('some_db', sql=test_sql)
        mock_get_all_tables.assert_called_once()
        self.assertEqual(False, check_result.get('bad_query'))

    @patch('sql.engines.mongo.MongoEngine.get_connection')
    def test_get_all_databases(self, mock_get_connection):
        db_list = self.engine.get_all_databases()
        self.assertIsInstance(db_list, ResultSet)
        # mock_get_connection.return_value.list_database_names.assert_called_once()

    @patch('sql.engines.mongo.MongoEngine.get_connection')
    def test_get_all_tables(self, mock_get_connection):
        mock_db = Mock()
        # 下面是查表示例返回结果
        mock_db.list_collection_names.return_value = ['u', 'v', 'w']
        mock_get_connection.return_value = {'some_db': mock_db}
        table_list = self.engine.get_all_tables('some_db')
        mock_db.list_collection_names.assert_called_once()
        self.assertEqual(table_list.rows, ['u', 'v', 'w'])

    def test_filter_sql(self):
        sql = """explain db.job.find().count()"""
        check_result = self.engine.filter_sql(sql, 0)
        self.assertEqual(check_result, 'db.job.find().count().explain()')

    @patch('sql.engines.mongo.MongoEngine.exec_cmd')
    def test_get_slave(self, mock_exec_cmd):
        mock_exec_cmd.return_value = "172.30.2.123:27017"
        flag = self.engine.get_slave()
        self.assertEqual(True, flag)

    @patch('sql.engines.mongo.MongoEngine.get_all_columns_by_tb')
    def test_parse_tuple(self, mock_get_all_columns_by_tb):
        cols = ["_id", "title", "tags", "likes"]
        mock_get_all_columns_by_tb.return_value.rows = cols
        cursor = [{'_id': {'$oid': '5f10162029684728e70045ab'}, 'title': 'MongoDB', 'tags': 'mongodb', 'likes': 100}]
        rows, columns = self.engine.parse_tuple(cursor, 'some_db', 'job')
        alldata = json.dumps(cursor[0], ensure_ascii=False, indent=2, separators=(",", ":"))
        rerows = (alldata, "ObjectId('5f10162029684728e70045ab')", 'MongoDB', 'mongodb', '100')
        self.assertEqual(columns, ['mongodballdata', '_id', 'title', 'tags', 'likes'])
        self.assertEqual(rows[0], rerows)

    @patch('sql.engines.mongo.MongoEngine.get_table_conut')
    @patch('sql.engines.mongo.MongoEngine.get_all_tables')
    def test_execute_check(self, mock_get_all_tables, mock_get_table_conut):
        sql = '''db.job.createIndex({"skuId":1},{background:true});'''
        mock_get_all_tables.return_value.rows = ("job")
        mock_get_table_conut.return_value = 1000
        row = ReviewResult(id=1, errlevel=0,
                           stagestatus='Audit completed',
                           errormessage='检测通过',
                           affected_rows=1000,
                           sql=sql,
                           execute_time=0)
        check_result = self.engine.execute_check('some_db', sql)
        self.assertEqual(check_result.rows[0].__dict__["errormessage"], row.__dict__["errormessage"])

    @patch('sql.engines.mongo.MongoEngine.exec_cmd')
    @patch('sql.engines.mongo.MongoEngine.get_master')
    def test_execute(self, mock_get_master, mock_exec_cmd):
        sql = '''db.job.find().createIndex({"skuId":1},{background:true})'''
        mock_exec_cmd.return_value = '''{
                                        "createdCollectionAutomatically" : false,
                                        "numIndexesBefore" : 2,
                                        "numIndexesAfter" : 3,
                                        "ok" : 1
                                      }'''

        check_result = self.engine.execute("some_db", sql)
        mock_get_master.assert_called_once()
        self.assertEqual(check_result.rows[0].__dict__["errlevel"], 0)

    def test_fill_query_columns(self):
        columns = ["_id", "title", "tags", "likes"]
        cursor = [{"_id": {"$oid": "5f10162029684728e70045ab"}, "title": "MongoDB", "text": "archery", "likes": 100},
                  {"_id": {"$oid": "7f10162029684728e70045ab"}, "author": "archery"}]
        cols = self.engine.fill_query_columns(cursor, columns=columns)
        self.assertEqual(cols, ["_id", "title", "tags", "likes", "text", "author"])

    @patch('sql.engines.mongo.MongoEngine.current_op')
    def test_current_op(self, mock_current_op):
        mock_current_op.return_value = ResultSet()
        command_types = ['Full', 'All', 'Inner', 'Active']
        for command_type in command_types:
            result_set = self.engine.current_op(command_type)
            self.assertIsInstance(result_set, ResultSet)

    @patch('sql.engines.mongo.MongoEngine.get_kill_command')
    def test_get_kill_command(self, mock_kill_command):
        """TODO mock后这个测试无意义，后续CI可增加真实的mongo验证"""
        mock_kill_command.return_value = 'db.killOp(111);db.killOp(222);'
        kill_command1 = self.engine.get_kill_command([111, 222])
        self.assertEqual(kill_command1, 'db.killOp(111);db.killOp(222);')
        mock_kill_command.return_value = 'db.killOp("shards: 111");db.killOp("shards: 111");'
        kill_command2 = self.engine.get_kill_command(['shards: 111', 'shards: 222'])
        self.assertEqual(kill_command2, 'db.killOp("shards: 111");db.killOp("shards: 111");')

    @patch('sql.engines.mongo.MongoEngine.kill_op')
    def test_kill_op(self, mock_kill_op):
        self.engine.kill_op([111, 222])
        self.engine.kill_op(['shards: 111', 'shards: 222'])
        self.assertEqual("", "")


class TestClickHouse(TestCase):

    def setUp(self):
        self.ins1 = Instance(instance_name='some_ins', type='slave', db_type='clickhouse', host='some_host',
                             port=9000, user='ins_user', password='some_str')
        self.ins1.save()
        self.sys_config = SysConfig()
        self.wf = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer_display='',
            audit_auth_groups='some_group',
            create_time=datetime.now() - timedelta(days=1),
            status='workflow_finish',
            is_backup=False,
            instance=self.ins1,
            db_name='some_db',
            syntax_type=1
        )
        SqlWorkflowContent.objects.create(workflow=self.wf)

    def tearDown(self):
        self.ins1.delete()
        self.sys_config.purge()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()

    @patch.object(ClickHouseEngine, 'query')
    def test_server_version(self, mock_query):
        result = ResultSet()
        result.rows = [('ClickHouse 22.1.3.7',)]
        mock_query.return_value = result
        new_engine = ClickHouseEngine(instance=self.ins1)
        server_version = new_engine.server_version
        self.assertTupleEqual(server_version, (22, 1, 3))

    @patch.object(ClickHouseEngine, 'query')
    def test_table_engine(self, mock_query):
        table_name = 'default.tb_test'
        result = ResultSet()
        result.rows = [('MergeTree',)]
        mock_query.return_value = result
        new_engine = ClickHouseEngine(instance=self.ins1)
        table_engine = new_engine.get_table_engine(table_name)
        self.assertDictEqual(table_engine, {'status': 1, 'engine': 'MergeTree'})

    @patch('clickhouse_driver.connect')
    def test_engine_base_info(self, _conn):
        new_engine = ClickHouseEngine(instance=self.ins1)
        self.assertEqual(new_engine.name, 'ClickHouse')
        self.assertEqual(new_engine.info, 'ClickHouse engine')

    @patch.object(ClickHouseEngine, 'get_connection')
    def testGetConnection(self, connect):
        new_engine = ClickHouseEngine(instance=self.ins1)
        new_engine.get_connection()
        connect.assert_called_once()

    @patch.object(ClickHouseEngine, 'query')
    def testQuery(self, mock_query):
        result = ResultSet()
        result.rows = [('v1', 'v2'), ]
        mock_query.return_value = result
        new_engine = ClickHouseEngine(instance=self.ins1)
        query_result = new_engine.query(sql='some_sql', limit_num=100)
        self.assertListEqual(query_result.rows, [('v1', 'v2'), ])

    @patch.object(ClickHouseEngine, 'query')
    def testAllDb(self, mock_query):
        db_result = ResultSet()
        db_result.rows = [('db_1',), ('db_2',)]
        mock_query.return_value = db_result
        new_engine = ClickHouseEngine(instance=self.ins1)
        dbs = new_engine.get_all_databases()
        self.assertEqual(dbs.rows, ['db_1', 'db_2'])

    @patch.object(ClickHouseEngine, 'query')
    def testAllTables(self, mock_query):
        table_result = ResultSet()
        table_result.rows = [('tb_1', 'some_des'), ('tb_2', 'some_des')]
        mock_query.return_value = table_result
        new_engine = ClickHouseEngine(instance=self.ins1)
        tables = new_engine.get_all_tables('some_db')
        mock_query.assert_called_once_with(db_name='some_db', sql=ANY)
        self.assertEqual(tables.rows, ['tb_1', 'tb_2'])

    @patch.object(ClickHouseEngine, 'query')
    def testAllColumns(self, mock_query):
        db_result = ResultSet()
        db_result.rows = [('col_1', 'type'), ('col_2', 'type2')]
        mock_query.return_value = db_result
        new_engine = ClickHouseEngine(instance=self.ins1)
        dbs = new_engine.get_all_columns_by_tb('some_db', 'some_tb')
        self.assertEqual(dbs.rows, ['col_1', 'col_2'])

    @patch.object(ClickHouseEngine, 'query')
    def testDescribe(self, mock_query):
        new_engine = ClickHouseEngine(instance=self.ins1)
        new_engine.describe_table('some_db', 'some_db')
        mock_query.assert_called_once()

    def test_query_check_wrong_sql(self):
        new_engine = ClickHouseEngine(instance=self.ins1)
        wrong_sql = '-- 测试'
        check_result = new_engine.query_check(db_name='some_db', sql=wrong_sql)
        self.assertDictEqual(check_result,
                             {'msg': '不支持的查询语法类型!', 'bad_query': True, 'filtered_sql': '-- 测试', 'has_star': False})

    def test_query_check_update_sql(self):
        new_engine = ClickHouseEngine(instance=self.ins1)
        update_sql = 'update user set id=0'
        check_result = new_engine.query_check(db_name='some_db', sql=update_sql)
        self.assertDictEqual(check_result,
                             {'msg': '不支持的查询语法类型!', 'bad_query': True, 'filtered_sql': 'update user set id=0',
                              'has_star': False})

    @patch.object(ClickHouseEngine, 'query')
    def test_explain_check(self, mock_query):
        result = ResultSet()
        result.rows = [('ClickHouse 20.1.3.7',)]
        mock_query.return_value = result
        new_engine = ClickHouseEngine(instance=self.ins1)
        server_version = new_engine.server_version
        sql = "insert into tb_test(note) values ('xbb');"
        check_result = ReviewSet(full_sql=sql)
        explain_result = new_engine.explain_check(check_result, db_name='some_db', line=1, statement=sql)
        self.assertEqual(explain_result.stagestatus, "Audit completed")

    def test_execute_check_select_sql(self):
        new_engine = ClickHouseEngine(instance=self.ins1)
        select_sql = 'select id,name from tb_test'
        check_result = new_engine.execute_check(db_name='some_db', sql=select_sql)
        self.assertEqual(check_result.rows[0].errormessage, "仅支持DML和DDL语句，查询语句请使用SQL查询功能！")

    @patch.object(ClickHouseEngine, 'query')
    def test_execute_check_alter_sql(self, mock_query):
        table_name = 'default.tb_test'
        result = ResultSet()
        result.rows = [('Log',)]
        mock_query.return_value = result
        new_engine = ClickHouseEngine(instance=self.ins1)
        table_engine = new_engine.get_table_engine(table_name)
        alter_sql = "alter table default.tb_test add column remark String"
        check_result = new_engine.execute_check(db_name='some_db', sql=alter_sql)
        self.assertEqual(check_result.rows[0].errormessage, "ALTER TABLE仅支持*MergeTree，Merge以及Distributed等引擎表！")

    def test_filter_sql_with_delimiter(self):
        new_engine = ClickHouseEngine(instance=self.ins1)
        sql_without_limit = 'select user from usertable;'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=100)
        self.assertEqual(check_result, 'select user from usertable limit 100;')

    def test_filter_sql_without_delimiter(self):
        new_engine = ClickHouseEngine(instance=self.ins1)
        sql_without_limit = 'select user from usertable'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=100)
        self.assertEqual(check_result, 'select user from usertable limit 100;')

    def test_filter_sql_with_limit(self):
        new_engine = ClickHouseEngine(instance=self.ins1)
        sql_without_limit = 'select user from usertable limit 10'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, 'select user from usertable limit 1;')

    def test_filter_sql_with_limit_min(self):
        new_engine = ClickHouseEngine(instance=self.ins1)
        sql_without_limit = 'select user from usertable limit 10'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=100)
        self.assertEqual(check_result, 'select user from usertable limit 10;')

    def test_filter_sql_with_limit_offset(self):
        new_engine = ClickHouseEngine(instance=self.ins1)
        sql_without_limit = 'select user from usertable limit 10 offset 100'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, 'select user from usertable limit 1 offset 100;')

    def test_filter_sql_with_limit_nn(self):
        new_engine = ClickHouseEngine(instance=self.ins1)
        sql_without_limit = 'select user from usertable limit 10, 100'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, 'select user from usertable limit 10,1;')

    def test_filter_sql_upper(self):
        new_engine = ClickHouseEngine(instance=self.ins1)
        sql_without_limit = 'SELECT USER FROM usertable LIMIT 10, 100'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, 'SELECT USER FROM usertable limit 10,1;')

    def test_filter_sql_not_select(self):
        new_engine = ClickHouseEngine(instance=self.ins1)
        sql_without_limit = 'show create table usertable;'
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, 'show create table usertable;')

    @patch('clickhouse_driver.connect.cursor.execute')
    @patch('clickhouse_driver.connect.cursor')
    @patch('clickhouse_driver.connect')
    def test_execute(self, _connect, _cursor, _execute):
        new_engine = ClickHouseEngine(instance=self.ins1)
        execute_result = new_engine.execute(self.wf)
        self.assertIsInstance(execute_result, ResultSet)

    @patch('clickhouse_driver.connect.cursor.execute')
    @patch('clickhouse_driver.connect.cursor')
    @patch('clickhouse_driver.connect')
    def test_execute_workflow_success(self, _conn, _cursor, _execute):
        sql = "insert into tb_test values('test')"
        row = ReviewResult(id=1,
                           errlevel=0,
                           stagestatus='Execute Successfully',
                           errormessage='None',
                           sql=sql,
                           affected_rows=0,
                           execute_time=0)
        wf = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer_display='',
            audit_auth_groups='some_group',
            create_time=datetime.now() - timedelta(days=1),
            status='workflow_finish',
            is_backup=False,
            instance=self.ins1,
            db_name='some_db',
            syntax_type=1
        )
        SqlWorkflowContent.objects.create(workflow=wf, sql_content=sql)
        new_engine = ClickHouseEngine(instance=self.ins1)
        execute_result = new_engine.execute_workflow(workflow=wf)
        self.assertIsInstance(execute_result, ReviewSet)
        self.assertEqual(execute_result.rows[0].__dict__.keys(), row.__dict__.keys())


class ODPSTest(TestCase):
    def setUp(self) -> None:
        self.ins = Instance.objects.create(instance_name='some_ins', type='slave', db_type='odps',
                                           host='some_host', port=9200, user='ins_user', db_name='some_db')
        self.engine = ODPSEngine(instance=self.ins)

    def tearDown(self) -> None:
        self.ins.delete()

    @patch('sql.engines.odps.ODPSEngine.get_connection')
    def test_get_connection(self, mock_odps):
        _ = self.engine.get_connection()
        mock_odps.assert_called_once()

    @patch('sql.engines.odps.ODPSEngine.get_connection')
    def test_query(self, mock_get_connection):
        test_sql = """select 123"""
        self.assertIsInstance(self.engine.query('some_db', test_sql), ResultSet)

    def test_query_check(self):
        test_sql = """select 123; -- this is comment
                      select 456;"""

        result_sql = "select 123;"

        check_result = self.engine.query_check(sql=test_sql)

        self.assertIsInstance(check_result, dict)
        self.assertEqual(False, check_result.get("bad_query"))
        self.assertEqual(result_sql, check_result.get("filtered_sql"))

    def test_query_check_error(self):
        test_sql = """drop table table_a"""

        check_result = self.engine.query_check(sql=test_sql)

        self.assertIsInstance(check_result, dict)
        self.assertEqual(True, check_result.get("bad_query"))

    @patch('sql.engines.odps.ODPSEngine.get_connection')
    def test_get_all_databases(self, mock_get_connection):
        mock_conn = Mock()
        mock_conn.exist_project.return_value = True
        mock_conn.project = 'some_db'

        mock_get_connection.return_value = mock_conn

        result = self.engine.get_all_databases()

        self.assertIsInstance(result, ResultSet)
        self.assertEqual(result.rows, ['some_db'])

    @patch('sql.engines.odps.ODPSEngine.get_connection')
    def test_get_all_tables(self, mock_get_connection):
        # 下面是查表示例返回结果
        class T:
            def __init__(self, name):
                self.name = name

        mock_conn = Mock()
        mock_conn.list_tables.return_value = [T('u'), T('v'), T('w')]
        mock_get_connection.return_value = mock_conn

        table_list = self.engine.get_all_tables('some_db')

        self.assertEqual(table_list.rows, ['u', 'v', 'w'])

    @patch('sql.engines.odps.ODPSEngine.get_all_columns_by_tb')
    def test_describe_table(self, mock_get_all_columns_by_tb):
        self.engine.describe_table('some_db', 'some_table')
        mock_get_all_columns_by_tb.assert_called_once()

    @patch('sql.engines.odps.ODPSEngine.get_connection')
    def test_get_all_columns_by_tb(self, mock_get_connection):
        mock_conn = Mock()

        mock_cols = Mock()

        mock_col = Mock()
        mock_col.name, mock_col.type, mock_col.comment = 'XiaoMing', 'string', 'name'

        mock_cols.schema.columns = [mock_col]
        mock_conn.get_table.return_value = mock_cols
        mock_get_connection.return_value = mock_conn

        result = self.engine.get_all_columns_by_tb('some_db', 'some_table')
        mock_get_connection.assert_called_once()
        mock_conn.get_table.assert_called_once()
        self.assertEqual(result.rows, [['XiaoMing', 'string', 'name']])
        self.assertEqual(result.column_list, ['COLUMN_NAME', 'COLUMN_TYPE', 'COLUMN_COMMENT'])
