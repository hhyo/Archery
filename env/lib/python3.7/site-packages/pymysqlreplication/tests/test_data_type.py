# -*- coding: utf-8 -*-

import copy
import platform
import sys
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from decimal import Decimal

from pymysqlreplication.tests import base
from pymysqlreplication.constants.BINLOG import *
from pymysqlreplication.row_event import *
from pymysqlreplication.event import *
from pymysqlreplication._compat import text_type


__all__ = ["TestDataType"]


def to_binary_dict(d):
    def encode_value(v):
        if isinstance(v, text_type):
            return v.encode()
        if isinstance(v, list):
            return [encode_value(x) for x in v]
        return v
    return dict([(k.encode(), encode_value(v)) for (k, v) in d.items()])


class TestDataType(base.PyMySQLReplicationTestCase):
    def ignoredEvents(self):
        return [GtidEvent]

    def create_and_insert_value(self, create_query, insert_query):
        self.execute(create_query)
        self.execute(insert_query)
        self.execute("COMMIT")

        self.assertIsInstance(self.stream.fetchone(), RotateEvent)
        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)
        #QueryEvent for the Create Table
        self.assertIsInstance(self.stream.fetchone(), QueryEvent)

        #QueryEvent for the BEGIN
        self.assertIsInstance(self.stream.fetchone(), QueryEvent)

        self.assertIsInstance(self.stream.fetchone(), TableMapEvent)

        event = self.stream.fetchone()
        if self.isMySQL56AndMore():
            self.assertEqual(event.event_type, WRITE_ROWS_EVENT_V2)
        else:
            self.assertEqual(event.event_type, WRITE_ROWS_EVENT_V1)
        self.assertIsInstance(event, WriteRowsEvent)
        return event

    def test_decimal(self):
        create_query = "CREATE TABLE test (test DECIMAL(2,1))"
        insert_query = "INSERT INTO test VALUES(4.2)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.columns[0].precision, 2)
        self.assertEqual(event.columns[0].decimals, 1)
        self.assertEqual(event.rows[0]["values"]["test"], Decimal("4.2"))

    def test_decimal_long_values(self):
        create_query = "CREATE TABLE test (\
            test DECIMAL(20,10) \
        )"
        insert_query = "INSERT INTO test VALUES(42000.123456)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], Decimal("42000.123456"))

    def test_decimal_long_values_1(self):
        create_query = "CREATE TABLE test (\
            test DECIMAL(20,10) \
        )"
        insert_query = "INSERT INTO test VALUES(9000000123.123456)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], Decimal("9000000123.123456"))

    def test_decimal_long_values_2(self):
        create_query = "CREATE TABLE test (\
            test DECIMAL(20,10) \
        )"
        insert_query = "INSERT INTO test VALUES(9000000123.0000012345)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"],
                Decimal("9000000123.0000012345"))

    def test_decimal_negative_values(self):
        create_query = "CREATE TABLE test (\
            test DECIMAL(20,10) \
        )"
        insert_query = "INSERT INTO test VALUES(-42000.123456)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], Decimal("-42000.123456"))

    def test_decimal_two_values(self):
        create_query = "CREATE TABLE test (\
            test DECIMAL(2,1), \
            test2 DECIMAL(20,10) \
        )"
        insert_query = "INSERT INTO test VALUES(4.2, 42000.123456)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], Decimal("4.2"))
        self.assertEqual(event.rows[0]["values"]["test2"], Decimal("42000.123456"))

    def test_decimal_with_zero_scale_1(self):
        create_query = "CREATE TABLE test (test DECIMAL(23,0))"
        insert_query = "INSERT INTO test VALUES(10)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], Decimal("10"))

    def test_decimal_with_zero_scale_2(self):
        create_query = "CREATE TABLE test (test DECIMAL(23,0))"
        insert_query = "INSERT INTO test VALUES(12345678912345678912345)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], Decimal("12345678912345678912345"))

    def test_decimal_with_zero_scale_3(self):
        create_query = "CREATE TABLE test (test DECIMAL(23,0))"
        insert_query = "INSERT INTO test VALUES(100000.0)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], Decimal("100000"))

    def test_decimal_with_zero_scale_4(self):
        create_query = "CREATE TABLE test (test DECIMAL(23,0))"
        insert_query = "INSERT INTO test VALUES(-100000.0)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], Decimal("-100000"))

    def test_decimal_with_zero_scale_6(self):
        create_query = "CREATE TABLE test (test DECIMAL(23,0))"
        insert_query = "INSERT INTO test VALUES(-1234567891234567891234)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], Decimal("-1234567891234567891234"))

    def test_tiny(self):
        create_query = "CREATE TABLE test (id TINYINT UNSIGNED NOT NULL, test TINYINT)"
        insert_query = "INSERT INTO test VALUES(255, -128)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["id"], 255)
        self.assertEqual(event.rows[0]["values"]["test"], -128)

    def test_tiny_maps_to_boolean_true(self):
        create_query = "CREATE TABLE test (id TINYINT UNSIGNED NOT NULL, test BOOLEAN)"
        insert_query = "INSERT INTO test VALUES(1, TRUE)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["id"], 1)
        self.assertEqual(type(event.rows[0]["values"]["test"]), type(1))
        self.assertEqual(event.rows[0]["values"]["test"], 1)

    def test_tiny_maps_to_boolean_false(self):
        create_query = "CREATE TABLE test (id TINYINT UNSIGNED NOT NULL, test BOOLEAN)"
        insert_query = "INSERT INTO test VALUES(1, FALSE)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["id"], 1)
        self.assertEqual(type(event.rows[0]["values"]["test"]), type(0))
        self.assertEqual(event.rows[0]["values"]["test"], 0)

    def test_tiny_maps_to_none(self):
        create_query = "CREATE TABLE test (id TINYINT UNSIGNED NOT NULL, test BOOLEAN)"
        insert_query = "INSERT INTO test VALUES(1, NULL)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["id"], 1)
        self.assertEqual(type(event.rows[0]["values"]["test"]), type(None))
        self.assertEqual(event.rows[0]["values"]["test"], None)

    def test_tiny_maps_to_none_2(self):
        create_query = "CREATE TABLE test (test BOOLEAN)"
        insert_query = "INSERT INTO test VALUES(NULL)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], None)

    def test_short(self):
        create_query = "CREATE TABLE test (id SMALLINT UNSIGNED NOT NULL, test SMALLINT)"
        insert_query = "INSERT INTO test VALUES(65535, -32768)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["id"], 65535)
        self.assertEqual(event.rows[0]["values"]["test"], -32768)

    def test_long(self):
        create_query = "CREATE TABLE test (id INT UNSIGNED NOT NULL, test INT)"
        insert_query = "INSERT INTO test VALUES(4294967295, -2147483648)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["id"], 4294967295)
        self.assertEqual(event.rows[0]["values"]["test"], -2147483648)

    def test_float(self):
        create_query = "CREATE TABLE test (id FLOAT NOT NULL, test FLOAT)"
        insert_query = "INSERT INTO test VALUES(42.42, -84.84)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(round(event.rows[0]["values"]["id"], 2), 42.42)
        self.assertEqual(round(event.rows[0]["values"]["test"],2 ), -84.84)

    def test_double(self):
        create_query = "CREATE TABLE test (id DOUBLE NOT NULL, test DOUBLE)"
        insert_query = "INSERT INTO test VALUES(42.42, -84.84)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(round(event.rows[0]["values"]["id"], 2), 42.42)
        self.assertEqual(round(event.rows[0]["values"]["test"],2 ), -84.84)

    def test_timestamp(self):
        create_query = "CREATE TABLE test (test TIMESTAMP);"
        insert_query = "INSERT INTO test VALUES('1984-12-03 12:33:07')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], datetime.datetime(1984, 12, 3, 12, 33, 7))

    def test_timestamp_mysql56(self):
        if not self.isMySQL56AndMore():
            self.skipTest("Not supported in this version of MySQL")
        self.set_sql_mode()
        create_query = '''CREATE TABLE test (test0 TIMESTAMP(0),
            test1 TIMESTAMP(1),
            test2 TIMESTAMP(2),
            test3 TIMESTAMP(3),
            test4 TIMESTAMP(4),
            test5 TIMESTAMP(5),
            test6 TIMESTAMP(6));'''
        insert_query = '''INSERT INTO test VALUES('1984-12-03 12:33:07',
            '1984-12-03 12:33:07.1',
            '1984-12-03 12:33:07.12',
            '1984-12-03 12:33:07.123',
            '1984-12-03 12:33:07.1234',
            '1984-12-03 12:33:07.12345',
            '1984-12-03 12:33:07.123456')'''
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test0"], datetime.datetime(1984, 12, 3, 12, 33, 7))
        self.assertEqual(event.rows[0]["values"]["test1"], datetime.datetime(1984, 12, 3, 12, 33, 7, 100000))
        self.assertEqual(event.rows[0]["values"]["test2"], datetime.datetime(1984, 12, 3, 12, 33, 7, 120000))
        self.assertEqual(event.rows[0]["values"]["test3"], datetime.datetime(1984, 12, 3, 12, 33, 7, 123000))
        self.assertEqual(event.rows[0]["values"]["test4"], datetime.datetime(1984, 12, 3, 12, 33, 7, 123400))
        self.assertEqual(event.rows[0]["values"]["test5"], datetime.datetime(1984, 12, 3, 12, 33, 7, 123450))
        self.assertEqual(event.rows[0]["values"]["test6"], datetime.datetime(1984, 12, 3, 12, 33, 7, 123456))

    def test_longlong(self):
        create_query = "CREATE TABLE test (id BIGINT UNSIGNED NOT NULL, test BIGINT)"
        insert_query = "INSERT INTO test VALUES(18446744073709551615, -9223372036854775808)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["id"], 18446744073709551615)
        self.assertEqual(event.rows[0]["values"]["test"], -9223372036854775808)

    def test_int24(self):
        create_query = "CREATE TABLE test (id MEDIUMINT UNSIGNED NOT NULL, test MEDIUMINT, test2 MEDIUMINT, test3 MEDIUMINT, test4 MEDIUMINT, test5 MEDIUMINT)"
        insert_query = "INSERT INTO test VALUES(16777215, 8388607, -8388608, 8, -8, 0)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["id"], 16777215)
        self.assertEqual(event.rows[0]["values"]["test"], 8388607)
        self.assertEqual(event.rows[0]["values"]["test2"], -8388608)
        self.assertEqual(event.rows[0]["values"]["test3"], 8)
        self.assertEqual(event.rows[0]["values"]["test4"], -8)
        self.assertEqual(event.rows[0]["values"]["test5"], 0)

    def test_date(self):
        create_query = "CREATE TABLE test (test DATE);"
        insert_query = "INSERT INTO test VALUES('1984-12-03')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], datetime.date(1984, 12, 3))

    def test_zero_date(self):
        create_query = "CREATE TABLE test (id INTEGER, test DATE, test2 DATE);"
        insert_query = "INSERT INTO test (id, test2) VALUES(1, '0000-01-21')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], None)
        self.assertEqual(event.rows[0]["values"]["test2"], None)

    def test_zero_month(self):
        self.set_sql_mode()
        create_query = "CREATE TABLE test (id INTEGER, test DATE, test2 DATE);"
        insert_query = "INSERT INTO test (id, test2) VALUES(1, '2015-00-21')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], None)
        self.assertEqual(event.rows[0]["values"]["test2"], None)

    def test_zero_day(self):
        self.set_sql_mode()
        create_query = "CREATE TABLE test (id INTEGER, test DATE, test2 DATE);"
        insert_query = "INSERT INTO test (id, test2) VALUES(1, '2015-05-00')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], None)
        self.assertEqual(event.rows[0]["values"]["test2"], None)

    def test_time(self):
        create_query = "CREATE TABLE test (test1 TIME, test2 TIME);"
        insert_query = "INSERT INTO test VALUES('838:59:59', '-838:59:59')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test1"], datetime.timedelta(
            microseconds=(((838*60) + 59)*60 + 59)*1000000
        ))
        self.assertEqual(event.rows[0]["values"]["test2"], datetime.timedelta(
            microseconds=(((-838*60) + 59)*60 + 59)*1000000
        ))

    def test_time2(self):
        if not self.isMySQL56AndMore():
            self.skipTest("Not supported in this version of MySQL")
        create_query = "CREATE TABLE test (test1 TIME(6), test2 TIME(6));"
        insert_query = """
            INSERT INTO test VALUES('838:59:59.000000', '-838:59:59.000000');
        """
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test1"], datetime.timedelta(
            microseconds=(((838*60) + 59)*60 + 59)*1000000 + 0
        ))
        self.assertEqual(event.rows[0]["values"]["test2"], datetime.timedelta(
            microseconds=(((-838*60) + 59)*60 + 59)*1000000 + 0
        ))

    def test_zero_time(self):
        create_query = "CREATE TABLE test (id INTEGER, test TIME NOT NULL DEFAULT 0);"
        insert_query = "INSERT INTO test (id) VALUES(1)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], datetime.timedelta(seconds=0))

    def test_datetime(self):
        create_query = "CREATE TABLE test (test DATETIME);"
        insert_query = "INSERT INTO test VALUES('1984-12-03 12:33:07')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], datetime.datetime(1984, 12, 3, 12, 33, 7))

    def test_zero_datetime(self):
        self.set_sql_mode()
        create_query = "CREATE TABLE test (id INTEGER, test DATETIME NOT NULL DEFAULT 0);"
        insert_query = "INSERT INTO test (id) VALUES(1)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], None)

    def test_broken_datetime(self):
        self.set_sql_mode()
        create_query = "CREATE TABLE test (test DATETIME NOT NULL);"
        insert_query = "INSERT INTO test VALUES('2013-00-00 00:00:00')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], None)

    def test_year(self):
        if self.isMySQL57():
            # https://dev.mysql.com/doc/refman/5.7/en/migrating-to-year4.html
            self.skipTest("YEAR(2) is unsupported in mysql 5.7")
        create_query = "CREATE TABLE test (a YEAR(4), b YEAR(2))"
        insert_query = "INSERT INTO test VALUES(1984, 1984)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["a"], 1984)
        self.assertEqual(event.rows[0]["values"]["b"], 1984)

    def test_varchar(self):
        create_query = "CREATE TABLE test (test VARCHAR(242)) CHARACTER SET latin1 COLLATE latin1_bin;"
        insert_query = "INSERT INTO test VALUES('Hello')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], 'Hello')
        self.assertEqual(event.columns[0].max_length, 242)

    def test_bit(self):
        create_query = "CREATE TABLE test (test BIT(6), \
                test2 BIT(16), \
                test3 BIT(12), \
                test4 BIT(9), \
                test5 BIT(64) \
                );"
        insert_query = "INSERT INTO test VALUES( \
                    b'100010', \
                    b'1000101010111000', \
                    b'100010101101', \
                    b'101100111', \
                    b'1101011010110100100111100011010100010100101110111011101011011010')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.columns[0].bits, 6)
        self.assertEqual(event.columns[1].bits, 16)
        self.assertEqual(event.columns[2].bits, 12)
        self.assertEqual(event.columns[3].bits, 9)
        self.assertEqual(event.columns[4].bits, 64)
        self.assertEqual(event.rows[0]["values"]["test"], "100010")
        self.assertEqual(event.rows[0]["values"]["test2"], "1000101010111000")
        self.assertEqual(event.rows[0]["values"]["test3"], "100010101101")
        self.assertEqual(event.rows[0]["values"]["test4"], "101100111")
        self.assertEqual(event.rows[0]["values"]["test5"], "1101011010110100100111100011010100010100101110111011101011011010")

    def test_enum(self):
        create_query = "CREATE TABLE test (test ENUM('a', 'ba', 'c'), test2 ENUM('a', 'ba', 'c')) CHARACTER SET latin1 COLLATE latin1_bin;"
        insert_query = "INSERT INTO test VALUES('ba', 'a')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], 'ba')
        self.assertEqual(event.rows[0]["values"]["test2"], 'a')

    def test_enum_empty_string(self):
        create_query = "CREATE TABLE test (test ENUM('a', 'ba', 'c'), test2 ENUM('a', 'ba', 'c')) CHARACTER SET latin1 COLLATE latin1_bin;"
        insert_query = "INSERT INTO test VALUES('ba', 'asdf')"
        last_sql_mode = self.execute("SELECT @@SESSION.sql_mode;"). \
            fetchall()[0][0]
        self.execute("SET SESSION sql_mode = 'ANSI';")
        event = self.create_and_insert_value(create_query, insert_query)
        self.execute("SET SESSION sql_mode = '%s';" % last_sql_mode)

        self.assertEqual(event.rows[0]["values"]["test"], 'ba')
        self.assertEqual(event.rows[0]["values"]["test2"], '')

    def test_set(self):
        create_query = "CREATE TABLE test (test SET('a', 'ba', 'c'), test2 SET('a', 'ba', 'c')) CHARACTER SET latin1 COLLATE latin1_bin;"
        insert_query = "INSERT INTO test VALUES('ba,a,c', 'a,c')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], set(('a', 'ba', 'c')))
        self.assertEqual(event.rows[0]["values"]["test2"], set(('a', 'c')))

    def test_tiny_blob(self):
        create_query = "CREATE TABLE test (test TINYBLOB, test2 TINYTEXT) CHARACTER SET latin1 COLLATE latin1_bin;"
        insert_query = "INSERT INTO test VALUES('Hello', 'World')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], b'Hello')
        self.assertEqual(event.rows[0]["values"]["test2"], 'World')

    def test_medium_blob(self):
        create_query = "CREATE TABLE test (test MEDIUMBLOB, test2 MEDIUMTEXT) CHARACTER SET latin1 COLLATE latin1_bin;"
        insert_query = "INSERT INTO test VALUES('Hello', 'World')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], b'Hello')
        self.assertEqual(event.rows[0]["values"]["test2"], 'World')

    def test_long_blob(self):
        create_query = "CREATE TABLE test (test LONGBLOB, test2 LONGTEXT) CHARACTER SET latin1 COLLATE latin1_bin;"
        insert_query = "INSERT INTO test VALUES('Hello', 'World')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], b'Hello')
        self.assertEqual(event.rows[0]["values"]["test2"], 'World')

    def test_blob(self):
        create_query = "CREATE TABLE test (test BLOB, test2 TEXT) CHARACTER SET latin1 COLLATE latin1_bin;"
        insert_query = "INSERT INTO test VALUES('Hello', 'World')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], b'Hello')
        self.assertEqual(event.rows[0]["values"]["test2"], 'World')

    def test_string(self):
        create_query = "CREATE TABLE test (test CHAR(12)) CHARACTER SET latin1 COLLATE latin1_bin;"
        insert_query = "INSERT INTO test VALUES('Hello')"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], 'Hello')

    def test_geometry(self):
        create_query = "CREATE TABLE test (test GEOMETRY);"
        insert_query = "INSERT INTO test VALUES(GeomFromText('POINT(1 1)'))"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], b'\x00\x00\x00\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\xf0?\x00\x00\x00\x00\x00\x00\xf0?')

    def test_json(self):
        if not self.isMySQL57():
            self.skipTest("Json is only supported in mysql 5.7")
        create_query = "CREATE TABLE test (id int, value json);"
        insert_query = """INSERT INTO test (id, value) VALUES (1, '{"my_key": "my_val", "my_key2": "my_val2"}');"""
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["value"], {b"my_key": b"my_val", b"my_key2": b"my_val2"})

    def test_json_array(self):
        if not self.isMySQL57():
            self.skipTest("Json is only supported in mysql 5.7")
        create_query = "CREATE TABLE test (id int, value json);"
        insert_query = """INSERT INTO test (id, value) VALUES (1, '["my_val", "my_val2"]');"""
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["value"], [b'my_val', b'my_val2'])

    def test_json_large(self):
        if not self.isMySQL57():
            self.skipTest("Json is only supported in mysql 5.7")
        data = dict([('foooo%i'%i, 'baaaaar%i'%i) for i in range(2560)])  # Make it large enough to reach 2^16 length
        create_query = "CREATE TABLE test (id int, value json);"
        insert_query = """INSERT INTO test (id, value) VALUES (1, '%s');""" % json.dumps(data)
        event = self.create_and_insert_value(create_query, insert_query)

        self.assertEqual(event.rows[0]["values"]["value"], to_binary_dict(data))

    def test_json_types(self):
        if not self.isMySQL57():
            self.skipTest("Json is only supported in mysql 5.7")

        types = [
           True,
           False,
           None,
           1.2,
           2^14,
           2^30,
           2^62,
           -1 * 2^14,
           -1 * 2^30,
           -1 * 2^62,
           ['foo', 'bar']
        ]

        for t in types:
            data = {'foo': t}
            create_query = "CREATE TABLE test (id int, value json);"
            insert_query = """INSERT INTO test (id, value) VALUES (1, '%s');""" % json.dumps(data)
            event = self.create_and_insert_value(create_query, insert_query)
            self.assertEqual(event.rows[0]["values"]["value"], to_binary_dict(data))

            self.tearDown()
            self.setUp()

    def test_json_basic(self):
        if not self.isMySQL57():
            self.skipTest("Json is only supported in mysql 5.7")

        types = [
           True,
           False,
           None,
           1.2,
           2^14,
           2^30,
           2^62,
           -1 * 2^14,
           -1 * 2^30,
           -1 * 2^62,
        ]

        for data in types:
            create_query = "CREATE TABLE test (id int, value json);"
            insert_query = """INSERT INTO test (id, value) VALUES (1, '%s');""" % json.dumps(data)
            event = self.create_and_insert_value(create_query, insert_query)
            self.assertEqual(event.rows[0]["values"]["value"], data)

            self.tearDown()
            self.setUp()

    def test_json_unicode(self):
        if not self.isMySQL57():
            self.skipTest("Json is only supported in mysql 5.7")
        create_query = "CREATE TABLE test (id int, value json);"
        insert_query = u"""INSERT INTO test (id, value) VALUES (1, '{"miam": "🍔"}');"""
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["value"][b"miam"], u'🍔'.encode('utf8'))

    def test_json_long_string(self):
        if not self.isMySQL57():
            self.skipTest("Json is only supported in mysql 5.7")
        create_query = "CREATE TABLE test (id int, value json);"
        # The string length needs to be larger than what can fit in a single byte.
        string_value = "super_long_string" * 100
        insert_query = "INSERT INTO test (id, value) VALUES (1, '{\"my_key\": \"%s\"}');" % (string_value,)
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["value"], to_binary_dict({"my_key": string_value}))

    def test_null(self):
        create_query = "CREATE TABLE test ( \
            test TINYINT NULL DEFAULT NULL, \
            test2 TINYINT NULL DEFAULT NULL, \
            test3 TINYINT NULL DEFAULT NULL, \
            test4 TINYINT NULL DEFAULT NULL, \
            test5 TINYINT NULL DEFAULT NULL, \
            test6 TINYINT NULL DEFAULT NULL, \
            test7 TINYINT NULL DEFAULT NULL, \
            test8 TINYINT NULL DEFAULT NULL, \
            test9 TINYINT NULL DEFAULT NULL, \
            test10 TINYINT NULL DEFAULT NULL, \
            test11 TINYINT NULL DEFAULT NULL, \
            test12 TINYINT NULL DEFAULT NULL, \
            test13 TINYINT NULL DEFAULT NULL, \
            test14 TINYINT NULL DEFAULT NULL, \
            test15 TINYINT NULL DEFAULT NULL, \
            test16 TINYINT NULL DEFAULT NULL, \
            test17 TINYINT NULL DEFAULT NULL, \
            test18 TINYINT NULL DEFAULT NULL, \
            test19 TINYINT NULL DEFAULT NULL, \
            test20 TINYINT NULL DEFAULT NULL\
            )"
        insert_query = "INSERT INTO test (test, test2, test3, test7, test20) VALUES(NULL, -128, NULL, 42, 84)"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], None)
        self.assertEqual(event.rows[0]["values"]["test2"], -128)
        self.assertEqual(event.rows[0]["values"]["test3"], None)
        self.assertEqual(event.rows[0]["values"]["test7"], 42)
        self.assertEqual(event.rows[0]["values"]["test20"], 84)

    def test_encoding_latin1(self):
        db = copy.copy(self.database)
        db["charset"] = "latin1"
        self.connect_conn_control(db)

        if platform.python_version_tuple()[0] == "2":
            string = unichr(233)
        else:
            string = "\u00e9"

        create_query = "CREATE TABLE test (test CHAR(12)) CHARACTER SET latin1 COLLATE latin1_bin;"
        insert_query = b"INSERT INTO test VALUES('" + string.encode('latin-1') + b"');"
        event = self.create_and_insert_value(create_query, insert_query)
        self.assertEqual(event.rows[0]["values"]["test"], string)

    def test_encoding_utf8(self):
        if platform.python_version_tuple()[0] == "2":
            string = unichr(0x20ac)
        else:
            string = "\u20ac"

        create_query = "CREATE TABLE test (test CHAR(12)) CHARACTER SET utf8 COLLATE utf8_bin;"
        insert_query = b"INSERT INTO test VALUES('" + string.encode('utf-8') + b"')"

        event = self.create_and_insert_value(create_query, insert_query)
        self.assertMultiLineEqual(event.rows[0]["values"]["test"], string)


if __name__ == "__main__":
    unittest.main()
