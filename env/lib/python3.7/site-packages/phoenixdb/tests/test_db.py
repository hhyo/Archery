import unittest
import phoenixdb
import phoenixdb.cursor
from phoenixdb.tests import TEST_DB_URL


@unittest.skipIf(TEST_DB_URL is None, "these tests require the PHOENIXDB_TEST_DB_URL environment variable set to a clean database")
class PhoenixDatabaseTest(unittest.TestCase):

    def test_select_literal(self):
        db = phoenixdb.connect(TEST_DB_URL, autocommit=True)
        self.addCleanup(db.close)

        with db.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS test")
            cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, text VARCHAR)")
            cursor.executemany("UPSERT INTO test VALUES (?, ?)", [[i, 'text {}'.format(i)] for i in range(10)])

        with db.cursor() as cursor:
            cursor.itersize = 4
            cursor.execute("SELECT * FROM test WHERE id>1 ORDER BY id")
            self.assertEqual(cursor.fetchall(), [[i, 'text {}'.format(i)] for i in range(2, 10)])

    def test_select_parameter(self):
        db = phoenixdb.connect(TEST_DB_URL, autocommit=True)
        self.addCleanup(db.close)

        with db.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS test")
            cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, text VARCHAR)")
            cursor.executemany("UPSERT INTO test VALUES (?, ?)", [[i, 'text {}'.format(i)] for i in range(10)])

        with db.cursor() as cursor:
            cursor.itersize = 4
            cursor.execute("SELECT * FROM test WHERE id>? ORDER BY id", [1])
            self.assertEqual(cursor.fetchall(), [[i, 'text {}'.format(i)] for i in range(2, 10)])

    def _check_dict_cursor(self, cursor):
        cursor.execute("DROP TABLE IF EXISTS test")
        cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, text VARCHAR)")
        cursor.execute("UPSERT INTO test VALUES (?, ?)", [1, 'text 1'])
        cursor.execute("SELECT * FROM test ORDER BY id")
        self.assertEqual(cursor.fetchall(), [{'ID': 1, 'TEXT': 'text 1'}])

    def test_dict_cursor_default_parameter(self):
        db = phoenixdb.connect(TEST_DB_URL, autocommit=True, cursor_factory=phoenixdb.cursor.DictCursor)
        self.addCleanup(db.close)

        with db.cursor() as cursor:
            self._check_dict_cursor(cursor)

    def test_dict_cursor_default_attribute(self):
        db = phoenixdb.connect(TEST_DB_URL, autocommit=True)
        db.cursor_factory = phoenixdb.cursor.DictCursor
        self.addCleanup(db.close)

        with db.cursor() as cursor:
            self._check_dict_cursor(cursor)

    def test_dict_cursor(self):
        db = phoenixdb.connect(TEST_DB_URL, autocommit=True)
        self.addCleanup(db.close)

        with db.cursor(cursor_factory=phoenixdb.cursor.DictCursor) as cursor:
            self._check_dict_cursor(cursor)
