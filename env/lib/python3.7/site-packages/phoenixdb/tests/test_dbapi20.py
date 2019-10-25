import unittest
import phoenixdb
from . import dbapi20
from phoenixdb.tests import TEST_DB_URL


@unittest.skipIf(TEST_DB_URL is None, "these tests require the PHOENIXDB_TEST_DB_URL environment variable set to a clean database")
class PhoenixDatabaseAPI20Test(dbapi20.DatabaseAPI20Test):
    driver = phoenixdb
    connect_args = (TEST_DB_URL, )

    ddl1 = 'create table %sbooze (name varchar(20) primary key)' % dbapi20.DatabaseAPI20Test.table_prefix
    ddl2 = 'create table %sbarflys (name varchar(20) primary key, drink varchar(30))' % dbapi20.DatabaseAPI20Test.table_prefix
    insert = 'upsert'

    def test_nextset(self): pass
    def test_setoutputsize(self): pass

    def _connect(self):
        con = dbapi20.DatabaseAPI20Test._connect(self)
        con.autocommit = True
        return con

    def test_None(self):
        con = self._connect()
        try:
            cur = con.cursor()
            self.executeDDL2(cur)
            cur.execute("%s into %sbarflys values ('a', NULL)" % (self.insert, self.table_prefix))
            cur.execute('select drink from %sbarflys' % self.table_prefix)
            r = cur.fetchall()
            self.assertEqual(len(r),1)
            self.assertEqual(len(r[0]),1)
            self.assertEqual(r[0][0],None,'NULL value not returned as None')
        finally:
            con.close()

    def test_autocommit(self):
        con = dbapi20.DatabaseAPI20Test._connect(self)
        self.assertFalse(con.autocommit)
        con.autocommit = True
        self.assertTrue(con.autocommit)
        con.autocommit = False
        self.assertFalse(con.autocommit)
        con.close()

    def test_readonly(self):
        con = dbapi20.DatabaseAPI20Test._connect(self)
        self.assertFalse(con.readonly)
        con.readonly = True
        self.assertTrue(con.readonly)
        con.readonly = False
        self.assertFalse(con.readonly)
        con.close()

    def test_iter(self):
        # https://www.python.org/dev/peps/pep-0249/#iter
        con = self._connect()
        try:
            cur = con.cursor()
            if hasattr(cur,'__iter__'):
                self.assertIs(cur,iter(cur))
        finally:
            con.close()

    def test_next(self):
        # https://www.python.org/dev/peps/pep-0249/#next
        con = self._connect()
        try:
            cur = con.cursor()
            if not hasattr(cur,'next'):
                return

            # cursor.next should raise an Error if called before
            # executing a select-type query
            self.assertRaises(self.driver.Error,cur.next)

            # cursor.next should raise an Error if called after
            # executing a query that cannnot return rows
            self.executeDDL1(cur)
            self.assertRaises(self.driver.Error,cur.next)

            # cursor.next should return None if a query retrieves '
            # no rows
            cur.execute('select name from %sbooze' % self.table_prefix)
            self.assertRaises(StopIteration,cur.next)
            self.failUnless(cur.rowcount in (-1,0))

            # cursor.next should raise an Error if called after
            # executing a query that cannnot return rows
            cur.execute("%s into %sbooze values ('Victoria Bitter')" % (
                self.insert, self.table_prefix
                ))
            self.assertRaises(self.driver.Error,cur.next)

            cur.execute('select name from %sbooze' % self.table_prefix)
            r = cur.next()
            self.assertEqual(len(r),1,
                'cursor.next should have retrieved a row with one column'
                )
            self.assertEqual(r[0],'Victoria Bitter',
                'cursor.next retrieved incorrect data'
                )
            # cursor.next should raise StopIteration if no more rows available
            self.assertRaises(StopIteration,cur.next)
            self.failUnless(cur.rowcount in (-1,1))
        finally:
            con.close()
