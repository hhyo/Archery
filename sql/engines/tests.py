from django.test import TestCase
from unittest.mock import patch, Mock, ANY
from sql.models import Instance
from sql.engines.mssql import MssqlEngine
from sql.engines.models import ResultSet


class TestMssql(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ins1 = Instance(instance_name='some_ins', type='slave', db_type='mssql', host='some_host',
                             port=1366, user='ins_user', password='some_pass')
        cls.ins1.save()

    @classmethod
    def tearDownClass(cls):
        cls.ins1.delete()

    @patch('pyodbc.connect')
    def testGetConnection(self,connect):
        new_engine = MssqlEngine(instance=self.ins1)
        new_engine.get_connection()
        connect.assert_called_once()

    @patch('pyodbc.connect')
    def testQuery(self, connect):
        cur = Mock()
        connect.return_value.cursor = cur
        cur.return_value.execute = Mock()
        cur.return_value.fetchmany.return_value = (('v1','v2'),)
        cur.return_value.description = (('k1','some_other_des'),('k2','some_other_des'))
        new_engine = MssqlEngine(instance=self.ins1)
        query_result = new_engine.query(sql='some_str',limit_num=100)
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
        table_result.rows = [('tb_1','some_des'), ('tb_2','some_des')]
        mock_query.return_value = table_result
        new_engine = MssqlEngine(instance=self.ins1)
        tables = new_engine.get_all_tables('some_db')
        mock_query.assert_called_once_with(db_name='some_db', sql=ANY)
        self.assertEqual(tables,['tb_1','tb_2'])

