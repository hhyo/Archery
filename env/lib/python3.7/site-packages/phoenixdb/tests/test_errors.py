from phoenixdb.tests import DatabaseTestCase


class ProgrammingErrorTest(DatabaseTestCase):

    def test_invalid_sql(self):
        with self.conn.cursor() as cursor:
            with self.assertRaises(self.conn.ProgrammingError) as cm:
                cursor.execute("UPS")
            self.assertEqual("Syntax error. Encountered \"UPS\" at line 1, column 1.", cm.exception.message)
            self.assertEqual(601, cm.exception.code)
            self.assertEqual("42P00", cm.exception.sqlstate)


class IntegrityErrorTest(DatabaseTestCase):

    def test_null_in_pk(self):
        self.createTable("phoenixdb_test_tbl1", "id integer primary key")
        with self.conn.cursor() as cursor:
            with self.assertRaises(self.conn.IntegrityError) as cm:
                cursor.execute("UPSERT INTO phoenixdb_test_tbl1 VALUES (NULL)")
            self.assertEqual("Constraint violation. PHOENIXDB_TEST_TBL1.ID may not be null", cm.exception.message)
            self.assertEqual(218, cm.exception.code)
            self.assertIn(cm.exception.sqlstate, ("22018", "23018"))


class DataErrorTest(DatabaseTestCase):

    def test_number_outside_of_range(self):
        self.createTable("phoenixdb_test_tbl1", "id tinyint primary key")
        with self.conn.cursor() as cursor:
            with self.assertRaises(self.conn.DataError) as cm:
                cursor.execute("UPSERT INTO phoenixdb_test_tbl1 VALUES (10000)")
            self.assertEqual("Type mismatch. TINYINT and INTEGER for 10000", cm.exception.message)
            self.assertEqual(203, cm.exception.code)
            self.assertEqual("22005", cm.exception.sqlstate)

    def test_division_by_zero(self):
        self.createTable("phoenixdb_test_tbl1", "id integer primary key")
        with self.conn.cursor() as cursor:
            with self.assertRaises(self.conn.DataError) as cm:
                cursor.execute("UPSERT INTO phoenixdb_test_tbl1 VALUES (2/0)")
            self.assertEqual("Divide by zero.", cm.exception.message)
            self.assertEqual(202, cm.exception.code)
            self.assertEqual("22012", cm.exception.sqlstate)
