import unittest
import phoenixdb
from . import dbapi20
from phoenixdb.tests import TEST_DB_URL

@unittest.skipIf(TEST_DB_URL is None, "these tests require the PHOENIXDB_TEST_DB_URL environment variable set to a clean database")
class PhoenixConnectionTest(unittest.TestCase):

    def _connect(self, connect_kw_args):
        try:
             r = phoenixdb.connect(
                *(TEST_DB_URL, ), **connect_kw_args
                )
        except AttributeError:
            self.fail("Failed to connect")
        return r

    def test_connection_credentials(self):
        connect_kw_args = {'user':'SCOTT', 'password':'TIGER', 'readonly':'True'}
        con = self._connect(connect_kw_args)
        try:
            self.assertEqual(con._connection_args, {'user':'SCOTT', 'password':'TIGER'},
                'Should have extract user and password'
                )
            self.assertEqual(con._filtered_args, {'readonly':'True'},
                'Should have not extracted foo'
                )
        finally:
            con.close()
