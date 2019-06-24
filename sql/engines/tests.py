import json
from datetime import timedelta, datetime
from unittest.mock import patch, Mock, ANY

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
from sql.engines.inception import InceptionEngine, _repair_json_str
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
                            port=1366, user='ins_user', password='some_pass')
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
                             port=1366, user='ins_user', password='some_pass')
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
        self.assertEqual(check_result, 'select user from usertable limit 10;')

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

    @patch('sql.engines.mysql.InceptionEngine')
    def test_execute_check_select_sql(self, _inception_engine):
        sql = 'select * from user'
        inc_row = ReviewResult(id=1,
                               errlevel=0,
                               stagestatus='Audit completed',
                               errormessage='None',
                               sql=sql,
                               affected_rows=0,
                               execute_time=0, )
        row = ReviewResult(id=1, errlevel=2,
                           stagestatus='驳回不支持语句',
                           errormessage='仅支持DML和DDL语句，查询语句请使用SQL查询功能！',
                           sql=sql)
        _inception_engine.return_value.execute_check.return_value = ReviewSet(full_sql=sql, rows=[inc_row])
        new_engine = MysqlEngine(instance=self.ins1)
        check_result = new_engine.execute_check(db_name='archery', sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch('sql.engines.mysql.InceptionEngine')
    def test_execute_check_critical_sql(self, _inception_engine):
        self.sys_config.set('critical_ddl_regex', '^|update')
        self.sys_config.get_all_config()
        sql = 'update user set id=1'
        inc_row = ReviewResult(id=1,
                               errlevel=0,
                               stagestatus='Audit completed',
                               errormessage='None',
                               sql=sql,
                               affected_rows=0,
                               execute_time=0, )
        row = ReviewResult(id=1, errlevel=2,
                           stagestatus='驳回高危SQL',
                           errormessage='禁止提交匹配' + '^|update' + '条件的语句！',
                           sql=sql)
        _inception_engine.return_value.execute_check.return_value = ReviewSet(full_sql=sql, rows=[inc_row])
        new_engine = MysqlEngine(instance=self.ins1)
        check_result = new_engine.execute_check(db_name='archery', sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch('sql.engines.mysql.InceptionEngine')
    def test_execute_check_normal_sql(self, _inception_engine):
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

    @patch('sql.engines.mysql.InceptionEngine')
    def test_execute_check_normal_sql_with_Exception(self, _inception_engine):
        sql = 'update user set id=1'
        _inception_engine.return_value.execute_check.side_effect = RuntimeError()
        new_engine = MysqlEngine(instance=self.ins1)
        with self.assertRaises(RuntimeError):
            new_engine.execute_check(db_name=0, sql=sql)

    @patch('sql.engines.mysql.InceptionEngine')
    def test_execute_workflow(self, _inception_engine):
        sql = 'update user set id=1'
        _inception_engine.return_value.execute.return_value = ReviewSet(full_sql=sql)
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

    @patch.object(MysqlEngine, 'query')
    def test_server_version(self, _query):
        _query.return_value.rows = (('5.7.20',),)
        new_engine = MysqlEngine(instance=self.ins1)
        server_version = new_engine.server_version
        self.assertTupleEqual(server_version, (5, 7, 20))

    @patch.object(MysqlEngine, 'query')
    def test_get_variables_not_filter(self, _query):
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.get_variables()
        _query.assert_called_once()

    @patch.object(MysqlEngine, 'query')
    def test_get_variables_filter(self, _query):
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
        self.sys_config.set('go_inception', 'true')
        _inception_engine.return_value.osc_control.return_value = ReviewSet()
        command = 'get'
        sqlsha1 = 'xxxxx'
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.osc_control(sqlsha1=sqlsha1, command=command)

    @patch('sql.engines.mysql.InceptionEngine')
    def test_osc_inception(self, _inception_engine):
        self.sys_config.set('go_inception', 'false')
        _inception_engine.return_value.osc_control.return_value = ReviewSet()
        command = 'get'
        sqlsha1 = 'xxxxx'
        new_engine = MysqlEngine(instance=self.ins1)
        new_engine.osc_control(sqlsha1=sqlsha1, command=command)


class TestRedis(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ins = Instance(instance_name='some_ins', type='slave', db_type='redis', host='some_host',
                           port=1366, user='ins_user', password='some_pass')
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
                           execute_time=0,
                           full_sql=sql)
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
                           execute_time=0,
                           full_sql=sql)
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
                           port=1366, user='ins_user', password='some_pass')
        cls.ins.save()

    @classmethod
    def tearDownClass(cls):
        cls.ins.delete()

    @patch('psycopg2.connect')
    def test_engine_base_info(self, _conn):
        new_engine = PgSQLEngine(instance=self.ins)
        self.assertEqual(new_engine.name, 'PgSQL')
        self.assertEqual(new_engine.info, 'PgSQL engine')

    @patch('psycopg2.connect')
    def test_get_connection(self, _conn):
        new_engine = PgSQLEngine(instance=self.ins)
        new_engine.get_connection()
        _conn.assert_called_once()

    @patch('psycopg2.connect.cursor.execute')
    @patch('psycopg2.connect.cursor')
    @patch('psycopg2.connect')
    def test_query(self, _conn, _cursor, _execute):
        _conn.return_value.cursor.return_value.fetchmany.return_value = [(1,)]
        new_engine = PgSQLEngine(instance=self.ins)
        query_result = new_engine.query(db_name=0, sql='select 1', limit_num=100)
        self.assertIsInstance(query_result, ResultSet)
        self.assertListEqual(query_result.rows, [(1,)])

    @patch('psycopg2.connect.cursor.execute')
    @patch('psycopg2.connect.cursor')
    @patch('psycopg2.connect')
    def test_query_not_limit(self, _conn, _cursor, _execute):
        _conn.return_value.cursor.return_value.fetchall.return_value = [(1,)]
        new_engine = PgSQLEngine(instance=self.ins)
        query_result = new_engine.query(db_name=0, sql='select 1', limit_num=0)
        self.assertIsInstance(query_result, ResultSet)
        self.assertListEqual(query_result.rows, [(1,)])

    @patch('sql.engines.pgsql.PgSQLEngine.query',
           return_value=ResultSet(rows=[('postgres',), ('archery',), ('template1',), ('template0',)]))
    def test_get_all_databases(self, _query):
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


class TestInception(TestCase):
    def setUp(self):
        self.ins = Instance.objects.create(instance_name='some_ins', type='slave', db_type='mysql', host='some_host',
                                           port=3306, user='ins_user', password='some_pass')
        self.ins_inc = Instance.objects.create(instance_name='some_ins_inc', type='slave', db_type='inception',
                                               host='some_host', port=6669)
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
        new_engine = InceptionEngine()
        new_engine.get_connection()
        _connect.assert_called_once()

    @patch('MySQLdb.connect')
    def test_get_backup_connection(self, _connect):
        new_engine = InceptionEngine()
        new_engine.get_backup_connection()
        _connect.assert_called_once()

    def test_execute_check_critical_sql(self):
        sql = 'alter table user'
        row = ReviewResult(id=1, errlevel=2, stagestatus='SQL语法错误',
                           errormessage='ALTER TABLE 必须带有选项',
                           sql=sql)
        new_engine = InceptionEngine()
        check_result = new_engine.execute_check(db_name=0, sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch('sql.engines.inception.InceptionEngine.query')
    def test_execute_check_normal_sql(self, _query):
        sql = 'update user set id=100'
        row = [1, 'CHECKED', 0, 'Audit completed', 'None', 'use archery', 0, "'0_0_0'", 'None', '0', '']
        _query.return_value = ResultSet(full_sql=sql, rows=[row])
        new_engine = InceptionEngine()
        check_result = new_engine.execute_check(instance=self.ins, db_name=0, sql=sql)
        self.assertIsInstance(check_result, ReviewSet)

    @patch('sql.engines.inception.InceptionEngine.query')
    def test_execute_exception(self, _query):
        sql = 'update user set id=100'
        row = [1, 'CHECKED', 1, 'Execute failed', 'None', 'use archery', 0, "'0_0_0'", 'None', '0', '']
        column_list = ['ID', 'stage', 'errlevel', 'stagestatus', 'errormessage', 'SQL', 'Affected_rows', 'sequence',
                       'backup_dbname', 'execute_time', 'sqlsha1']
        _query.return_value = ResultSet(full_sql=sql, rows=[row], column_list=column_list)
        new_engine = InceptionEngine()
        execute_result = new_engine.execute(workflow=self.wf)
        self.assertIsInstance(execute_result, ReviewSet)

    @patch('sql.engines.inception.InceptionEngine.query')
    def test_execute_finish(self, _query):
        sql = 'update user set id=100'
        row = [1, 'CHECKED', 0, 'Execute Successfully', 'None', 'use archery', 0, "'0_0_0'", 'None', '0', '']
        column_list = ['ID', 'stage', 'errlevel', 'stagestatus', 'errormessage', 'SQL', 'Affected_rows', 'sequence',
                       'backup_dbname', 'execute_time', 'sqlsha1']
        _query.return_value = ResultSet(full_sql=sql, rows=[row], column_list=column_list)
        new_engine = InceptionEngine()
        execute_result = new_engine.execute(workflow=self.wf)
        self.assertIsInstance(execute_result, ReviewSet)

    @patch('MySQLdb.connect.cursor.execute')
    @patch('MySQLdb.connect.cursor')
    @patch('MySQLdb.connect')
    def test_query(self, _conn, _cursor, _execute):
        _conn.return_value.cursor.return_value.fetchall.return_value = [(1,)]
        new_engine = InceptionEngine()
        query_result = new_engine.query(db_name=0, sql='select 1', limit_num=100)
        self.assertIsInstance(query_result, ResultSet)

    @patch('MySQLdb.connect.cursor.execute')
    @patch('MySQLdb.connect.cursor')
    @patch('MySQLdb.connect')
    def test_query_not_limit(self, _conn, _cursor, _execute):
        _conn.return_value.cursor.return_value.fetchall.return_value = [(1,)]
        new_engine = InceptionEngine(instance=self.ins)
        query_result = new_engine.query(db_name=0, sql='select 1', limit_num=0)
        self.assertIsInstance(query_result, ResultSet)

    @patch('sql.engines.inception.InceptionEngine.query')
    def test_query_print(self, _query):
        sql = 'update user set id=100'
        row = [1,
               'select * from sql_instance limit 100',
               0,
               '{"command":"select","select_list":[{"type":"FIELD_ITEM","field":"*"}],"table_ref":[{"db":"archery","table":"sql_instance"}],"limit":{"limit":[{"type":"INT_ITEM","value":"100"}]}}',
               'None']
        column_list = ['ID', 'statement', 'errlevel', 'query_tree', 'errmsg']
        _query.return_value = ResultSet(full_sql=sql, rows=[row], column_list=column_list)
        new_engine = InceptionEngine()
        print_result = new_engine.query_print(self.ins, db_name=None, sql=sql)
        self.assertDictEqual(print_result, json.loads(_repair_json_str(row[3])))

    @patch('MySQLdb.connect')
    def test_get_rollback_list(self, _connect):
        self.wf.sqlworkflowcontent.execute_result = """[{
            "id": 1,
            "stage": "RERUN",
            "errlevel": 0,
            "stagestatus": "Execute Successfully",
            "errormessage": "None",
            "sql": "use archer_test",
            "affected_rows": 0,
            "sequence": "'1554135032_13038_0'",
            "backup_dbname": "None",
            "execute_time": "0.000",
            "sqlsha1": "",
            "actual_affected_rows": 0
        }, {
            "id": 2,
            "stage": "EXECUTED",
            "errlevel": 0,
            "stagestatus": "Execute Successfully Backup successfully",
            "errormessage": "None",
            "sql": "insert into tt1 (user_name)values('A'),('B'),('C')",
            "affected_rows": 3,
            "sequence": "'1554135032_13038_1'",
            "backup_dbname": "mysql_3306_archer_test",
            "execute_time": "0.000",
            "sqlsha1": "",
            "actual_affected_rows": 3
        }]"""
        self.wf.sqlworkflowcontent.save()
        new_engine = InceptionEngine()
        new_engine.get_rollback(self.wf)

    @patch('sql.engines.inception.InceptionEngine.query')
    def test_osc_get(self, _query):
        new_engine = InceptionEngine()
        command = 'get'
        sqlsha1 = 'xxxxx'
        sql = f"inception get osc_percent '{sqlsha1}';"
        _query.return_value = ResultSet(full_sql=sql, rows=[], column_list=[])
        new_engine.osc_control(sqlsha1=sqlsha1, command=command)
        _query.assert_called_once_with(sql=sql)

    @patch('sql.engines.inception.InceptionEngine.query')
    def test_osc_kill(self, _query):
        new_engine = InceptionEngine()
        command = 'kill'
        sqlsha1 = 'xxxxx'
        sql = f"inception stop alter '{sqlsha1}';"
        _query.return_value = ResultSet(full_sql=sql, rows=[], column_list=[])
        new_engine.osc_control(sqlsha1=sqlsha1, command=command)
        _query.assert_called_once_with(sql=sql)

    @patch('sql.engines.inception.InceptionEngine.query')
    def test_osc_not_support(self, _query):
        new_engine = InceptionEngine()
        command = 'stop'
        sqlsha1 = 'xxxxx'
        sql = f"inception stop alter '{sqlsha1}';"
        _query.return_value = ResultSet(full_sql=sql, rows=[], column_list=[])
        with self.assertRaisesMessage(ValueError, 'pt-osc不支持暂停和恢复，需要停止执行请使用终止按钮！'):
            new_engine.osc_control(sqlsha1=sqlsha1, command=command)

    @patch('sql.engines.inception.InceptionEngine.query')
    def test_get_variables(self, _query):
        new_engine = InceptionEngine(instance=self.ins_inc)
        new_engine.get_variables()
        sql = f"inception get variables;"
        _query.assert_called_once_with(sql=sql)

    @patch('sql.engines.inception.InceptionEngine.query')
    def test_get_variables_filter(self, _query):
        new_engine = InceptionEngine(instance=self.ins_inc)
        new_engine.get_variables(variables=['inception_osc_on'])
        sql = f"inception get variables 'inception_osc_on';"
        _query.assert_called_once_with(sql=sql)

    @patch('sql.engines.inception.InceptionEngine.query')
    def test_set_variable(self, _query):
        new_engine = InceptionEngine(instance=self.ins)
        new_engine.set_variable('inception_osc_on', 'on')
        _query.assert_called_once_with(sql="inception set inception_osc_on=on;")


class TestGoInception(TestCase):
    def setUp(self):
        self.ins = Instance.objects.create(instance_name='some_ins', type='slave', db_type='mysql',
                                           host='some_host',
                                           port=3306, user='ins_user', password='some_pass')
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

    @patch('pymysql.connect')
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

    @patch('pymysql.connect.cursor.execute')
    @patch('pymysql.connect.cursor')
    @patch('pymysql.connect')
    def test_query(self, _conn, _cursor, _execute):
        _conn.return_value.cursor.return_value.fetchall.return_value = [(1,)]
        new_engine = GoInceptionEngine()
        query_result = new_engine.query(db_name=0, sql='select 1', limit_num=100)
        self.assertIsInstance(query_result, ResultSet)

    @patch('pymysql.connect.cursor.execute')
    @patch('pymysql.connect.cursor')
    @patch('pymysql.connect')
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
                                           host='some_host', port=3306, user='ins_user', password='some_pass',
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
                             {'msg': '仅支持^select语法!', 'bad_query': True, 'filtered_sql': sql.strip(';'),
                              'has_star': False})

    def test_query_check_star_sql(self):
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

    def test_query_check_plus(self):
        sql = "select 100+1 from tb;"
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.query_check(db_name='archery', sql=sql)
        self.assertDictEqual(check_result,
                             {'msg': '禁止使用 + 关键词\n', 'bad_query': True, 'filtered_sql': sql.strip(';'),
                              'has_star': False})

    def test_filter_sql_with_delimiter(self):
        sql = "select * from xx;"
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.filter_sql(sql=sql, limit_num=100)
        self.assertEqual(check_result, "select * from xx WHERE ROWNUM <= 100")

    def test_filter_sql_with_delimiter_and_where(self):
        sql = "select * from xx where id>1;"
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.filter_sql(sql=sql, limit_num=100)
        self.assertEqual(check_result, "select * from xx where id>1 AND ROWNUM <= 100")

    def test_filter_sql_without_delimiter(self):
        sql = "select * from xx;"
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.filter_sql(sql=sql, limit_num=100)
        self.assertEqual(check_result, "select * from xx WHERE ROWNUM <= 100")

    def test_filter_sql_with_limit(self):
        sql = "select * from xx limit 10;"
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.filter_sql(sql=sql, limit_num=1)
        self.assertEqual(check_result, "select * from xx limit 10 WHERE ROWNUM <= 1")

    def test_query_masking(self):
        query_result = ResultSet()
        new_engine = OracleEngine(instance=self.ins)
        masking_result = new_engine.query_masking(schema_name='', sql='select 1', resultset=query_result)
        self.assertEqual(masking_result, query_result)

    def test_execute_check_select_sql(self):
        sql = 'select * from user;'
        row = ReviewResult(id=1, errlevel=2,
                           stagestatus='驳回不支持语句',
                           errormessage='仅支持DML和DDL语句，查询语句请使用SQL查询功能！',
                           sql=sql)
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
                           sql=sql)
        new_engine = OracleEngine(instance=self.ins)
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
        new_engine = OracleEngine(instance=self.ins)
        check_result = new_engine.execute_check(db_name='archery', sql=sql)
        self.assertIsInstance(check_result, ReviewSet)
        self.assertEqual(check_result.rows[0].__dict__, row.__dict__)

    @patch('cx_Oracle.connect.cursor.execute')
    @patch('cx_Oracle.connect.cursor')
    @patch('cx_Oracle.connect')
    def test_execute_workflow_success(self, _conn, _cursor, _execute):
        sql = 'update user set id=1'
        row = ReviewResult(id=1,
                           errlevel=0,
                           stagestatus='Execute Successfully',
                           errormessage='None',
                           sql=sql,
                           affected_rows=0,
                           execute_time=0,
                           full_sql=sql)
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
        new_engine = OracleEngine(instance=self.ins)
        execute_result = new_engine.execute_workflow(workflow=wf)
        self.assertIsInstance(execute_result, ReviewSet)
        self.assertEqual(execute_result.rows[0].__dict__.keys(), row.__dict__.keys())

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
            new_engine = OracleEngine(instance=self.ins)
            execute_result = new_engine.execute_workflow(workflow=wf)
            self.assertIsInstance(execute_result, ReviewSet)
            self.assertEqual(execute_result.rows[0].__dict__.keys(), row.__dict__.keys())
