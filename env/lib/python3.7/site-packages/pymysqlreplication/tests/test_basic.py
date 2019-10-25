# -*- coding: utf-8 -*-
import pymysql
import copy
import time
import sys
import io
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from pymysqlreplication.tests import base
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.gtid import GtidSet
from pymysqlreplication.event import *
from pymysqlreplication.exceptions import TableMetadataUnavailableError
from pymysqlreplication.constants.BINLOG import *
from pymysqlreplication.row_event import *

__all__ = ["TestBasicBinLogStreamReader", "TestMultipleRowBinLogStreamReader", "TestCTLConnectionSettings", "TestGtidBinLogStreamReader"]


class TestBasicBinLogStreamReader(base.PyMySQLReplicationTestCase):
    def ignoredEvents(self):
        return [GtidEvent]

    def test_allowed_event_list(self):
        self.assertEqual(len(self.stream._allowed_event_list(None, None, False)), 14)
        self.assertEqual(len(self.stream._allowed_event_list(None, None, True)), 13)
        self.assertEqual(len(self.stream._allowed_event_list(None, [RotateEvent], False)), 13)
        self.assertEqual(len(self.stream._allowed_event_list([RotateEvent], None, False)), 1)

    def test_read_query_event(self):
        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)

        event = self.stream.fetchone()
        self.assertEqual(event.position, 4)
        self.assertEqual(event.next_binlog, self.bin_log_basename() + ".000001")
        self.assertIsInstance(event, RotateEvent)

        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)

        event = self.stream.fetchone()
        self.assertIsInstance(event, QueryEvent)
        self.assertEqual(event.query, query)

    def test_read_query_event_with_unicode(self):
        query = u"CREATE TABLE `testÈ` (id INT NOT NULL AUTO_INCREMENT, dataÈ VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)

        event = self.stream.fetchone()
        self.assertEqual(event.position, 4)
        self.assertEqual(event.next_binlog, self.bin_log_basename() + ".000001")
        self.assertIsInstance(event, RotateEvent)

        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)

        event = self.stream.fetchone()
        self.assertIsInstance(event, QueryEvent)
        self.assertEqual(event.query, query)


    def test_reading_rotate_event(self):
        query = "CREATE TABLE test_2 (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)

        self.assertIsInstance(self.stream.fetchone(), RotateEvent)
        self.stream.close()

        query = "CREATE TABLE test_3 (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)

        # Rotate event
        self.assertIsInstance(self.stream.fetchone(), RotateEvent)

    """ `test_load_query_event` needs statement-based binlog
    def test_load_query_event(self):
        # prepare csv
        with open("/tmp/test_load_query.csv", "w") as fp:
            fp.write("1,aaa\n2,bbb\n3,ccc\n4,ddd\n")

        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "LOAD DATA INFILE '/tmp/test_load_query.csv' INTO TABLE test \
                FIELDS TERMINATED BY ',' \
                ENCLOSED BY '\"' \
                LINES TERMINATED BY '\r\n'"
        self.execute(query)

        self.assertIsInstance(self.stream.fetchone(), RotateEvent)
        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)
        # create table
        self.assertIsInstance(self.stream.fetchone(), QueryEvent)
        # begin
        self.assertIsInstance(self.stream.fetchone(), QueryEvent)

        self.assertIsInstance(self.stream.fetchone(), BeginLoadQueryEvent)
        self.assertIsInstance(self.stream.fetchone(), ExecuteLoadQueryEvent)

        self.assertIsInstance(self.stream.fetchone(), XidEvent)
    """

    def test_connection_stream_lost_event(self):
        self.stream.close()
        self.stream = BinLogStreamReader(
            self.database, server_id=1024, blocking=True,
            ignored_events=self.ignoredEvents())

        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query2 = "INSERT INTO test (data) VALUES('a')"
        for i in range(0, 10000):
            self.execute(query2)
        self.execute("COMMIT")

        self.assertIsInstance(self.stream.fetchone(), RotateEvent)
        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)

        event = self.stream.fetchone()

        self.assertIsInstance(event, QueryEvent)
        self.assertEqual(event.query, query)

        self.conn_control.kill(self.stream._stream_connection.thread_id())
        for i in range(0, 10000):
            event = self.stream.fetchone()
            self.assertIsNotNone(event)

    def test_filtering_only_events(self):
        self.stream.close()
        self.stream = BinLogStreamReader(
            self.database, server_id=1024, only_events=[QueryEvent])
        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)

        event = self.stream.fetchone()
        self.assertIsInstance(event, QueryEvent)
        self.assertEqual(event.query, query)

    def test_filtering_ignore_events(self):
        self.stream.close()
        self.stream = BinLogStreamReader(
            self.database, server_id=1024, ignored_events=[QueryEvent])
        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)

        event = self.stream.fetchone()
        self.assertIsInstance(event, RotateEvent)

    def test_filtering_table_event_with_only_tables(self):
        self.stream.close()
        self.assertEqual(self.bin_log_format(), "ROW")
        self.stream = BinLogStreamReader(
            self.database,
            server_id=1024,
            only_events=[WriteRowsEvent],
            only_tables = ["test_2"]
        )

        query = "CREATE TABLE test_2 (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "CREATE TABLE test_3 (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)

        self.execute("INSERT INTO test_2 (data) VALUES ('alpha')")
        self.execute("INSERT INTO test_3 (data) VALUES ('alpha')")
        self.execute("INSERT INTO test_2 (data) VALUES ('beta')")
        self.execute("COMMIT")
        event = self.stream.fetchone()
        self.assertEqual(event.table, "test_2")
        event = self.stream.fetchone()
        self.assertEqual(event.table, "test_2")

    def test_filtering_table_event_with_ignored_tables(self):
        self.stream.close()
        self.assertEqual(self.bin_log_format(), "ROW")
        self.stream = BinLogStreamReader(
            self.database,
            server_id=1024,
            only_events=[WriteRowsEvent],
            ignored_tables = ["test_2"]
        )

        query = "CREATE TABLE test_2 (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "CREATE TABLE test_3 (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)

        self.execute("INSERT INTO test_2 (data) VALUES ('alpha')")
        self.execute("INSERT INTO test_3 (data) VALUES ('alpha')")
        self.execute("INSERT INTO test_2 (data) VALUES ('beta')")
        self.execute("COMMIT")
        event = self.stream.fetchone()
        self.assertEqual(event.table, "test_3")

    def test_filtering_table_event_with_only_tables_and_ignored_tables(self):
        self.stream.close()
        self.assertEqual(self.bin_log_format(), "ROW")
        self.stream = BinLogStreamReader(
            self.database,
            server_id=1024,
            only_events=[WriteRowsEvent],
            only_tables = ["test_2"],
            ignored_tables = ["test_3"]
        )

        query = "CREATE TABLE test_2 (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "CREATE TABLE test_3 (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)

        self.execute("INSERT INTO test_2 (data) VALUES ('alpha')")
        self.execute("INSERT INTO test_3 (data) VALUES ('alpha')")
        self.execute("INSERT INTO test_2 (data) VALUES ('beta')")
        self.execute("COMMIT")
        event = self.stream.fetchone()
        self.assertEqual(event.table, "test_2")

    def test_write_row_event(self):
        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "INSERT INTO test (data) VALUES('Hello World')"
        self.execute(query)
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
        self.assertEqual(event.rows[0]["values"]["id"], 1)
        self.assertEqual(event.rows[0]["values"]["data"], "Hello World")
        self.assertEqual(event.schema, "pymysqlreplication_test")
        self.assertEqual(event.table, "test")
        self.assertEqual(event.columns[1].name, 'data')

    def test_delete_row_event(self):
        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "INSERT INTO test (data) VALUES('Hello World')"
        self.execute(query)

        self.resetBinLog()

        query = "DELETE FROM test WHERE id = 1"
        self.execute(query)
        self.execute("COMMIT")

        self.assertIsInstance(self.stream.fetchone(), RotateEvent)
        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)

        #QueryEvent for the BEGIN
        self.assertIsInstance(self.stream.fetchone(), QueryEvent)

        self.assertIsInstance(self.stream.fetchone(), TableMapEvent)

        event = self.stream.fetchone()
        if self.isMySQL56AndMore():
            self.assertEqual(event.event_type, DELETE_ROWS_EVENT_V2)
        else:
            self.assertEqual(event.event_type, DELETE_ROWS_EVENT_V1)
        self.assertIsInstance(event, DeleteRowsEvent)
        self.assertEqual(event.rows[0]["values"]["id"], 1)
        self.assertEqual(event.rows[0]["values"]["data"], "Hello World")

    def test_update_row_event(self):
        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "INSERT INTO test (data) VALUES('Hello')"
        self.execute(query)

        self.resetBinLog()

        query = "UPDATE test SET data = 'World' WHERE id = 1"
        self.execute(query)
        self.execute("COMMIT")

        self.assertIsInstance(self.stream.fetchone(), RotateEvent)
        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)

        #QueryEvent for the BEGIN
        self.assertIsInstance(self.stream.fetchone(), QueryEvent)

        self.assertIsInstance(self.stream.fetchone(), TableMapEvent)

        event = self.stream.fetchone()
        if self.isMySQL56AndMore():
            self.assertEqual(event.event_type, UPDATE_ROWS_EVENT_V2)
        else:
            self.assertEqual(event.event_type, UPDATE_ROWS_EVENT_V1)
        self.assertIsInstance(event, UpdateRowsEvent)
        self.assertEqual(event.rows[0]["before_values"]["id"], 1)
        self.assertEqual(event.rows[0]["before_values"]["data"], "Hello")
        self.assertEqual(event.rows[0]["after_values"]["id"], 1)
        self.assertEqual(event.rows[0]["after_values"]["data"], "World")

    def test_minimal_image_write_row_event(self):
        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "SET SESSION binlog_row_image = 'minimal'"
        self.execute(query)
        query = "INSERT INTO test (data) VALUES('Hello World')"
        self.execute(query)
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
        self.assertEqual(event.rows[0]["values"]["id"], 1)
        self.assertEqual(event.rows[0]["values"]["data"], "Hello World")
        self.assertEqual(event.schema, "pymysqlreplication_test")
        self.assertEqual(event.table, "test")
        self.assertEqual(event.columns[1].name, 'data')

    def test_minimal_image_delete_row_event(self):
        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "INSERT INTO test (data) VALUES('Hello World')"
        self.execute(query)
        query = "SET SESSION binlog_row_image = 'minimal'"
        self.execute(query)
        self.resetBinLog()

        query = "DELETE FROM test WHERE id = 1"
        self.execute(query)
        self.execute("COMMIT")

        self.assertIsInstance(self.stream.fetchone(), RotateEvent)
        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)

        #QueryEvent for the BEGIN
        self.assertIsInstance(self.stream.fetchone(), QueryEvent)

        self.assertIsInstance(self.stream.fetchone(), TableMapEvent)

        event = self.stream.fetchone()
        if self.isMySQL56AndMore():
            self.assertEqual(event.event_type, DELETE_ROWS_EVENT_V2)
        else:
            self.assertEqual(event.event_type, DELETE_ROWS_EVENT_V1)
        self.assertIsInstance(event, DeleteRowsEvent)
        self.assertEqual(event.rows[0]["values"]["id"], 1)
        self.assertEqual(event.rows[0]["values"]["data"], None)

    def test_minimal_image_update_row_event(self):
        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "INSERT INTO test (data) VALUES('Hello')"
        self.execute(query)
        query = "SET SESSION binlog_row_image = 'minimal'"
        self.execute(query)
        self.resetBinLog()

        query = "UPDATE test SET data = 'World' WHERE id = 1"
        self.execute(query)
        self.execute("COMMIT")

        self.assertIsInstance(self.stream.fetchone(), RotateEvent)
        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)

        #QueryEvent for the BEGIN
        self.assertIsInstance(self.stream.fetchone(), QueryEvent)

        self.assertIsInstance(self.stream.fetchone(), TableMapEvent)

        event = self.stream.fetchone()
        if self.isMySQL56AndMore():
            self.assertEqual(event.event_type, UPDATE_ROWS_EVENT_V2)
        else:
            self.assertEqual(event.event_type, UPDATE_ROWS_EVENT_V1)
        self.assertIsInstance(event, UpdateRowsEvent)
        self.assertEqual(event.rows[0]["before_values"]["id"], 1)
        self.assertEqual(event.rows[0]["before_values"]["data"], None)
        self.assertEqual(event.rows[0]["after_values"]["id"], None)
        self.assertEqual(event.rows[0]["after_values"]["data"], "World")

    def test_log_pos(self):
        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "INSERT INTO test (data) VALUES('Hello')"
        self.execute(query)
        self.execute("COMMIT")

        for i in range(6):
            self.stream.fetchone()
        # record position after insert
        log_file, log_pos = self.stream.log_file, self.stream.log_pos

        query = "UPDATE test SET data = 'World' WHERE id = 1"
        self.execute(query)
        self.execute("COMMIT")

        # resume stream from previous position
        if self.stream is not None:
            self.stream.close()
        self.stream = BinLogStreamReader(
            self.database,
            server_id=1024,
            resume_stream=True,
            log_file=log_file,
            log_pos=log_pos,
            ignored_events=self.ignoredEvents()
        )

        self.assertIsInstance(self.stream.fetchone(), RotateEvent)
        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)
        self.assertIsInstance(self.stream.fetchone(), XidEvent)
        # QueryEvent for the BEGIN
        self.assertIsInstance(self.stream.fetchone(), QueryEvent)
        self.assertIsInstance(self.stream.fetchone(), TableMapEvent)
        self.assertIsInstance(self.stream.fetchone(), UpdateRowsEvent)
        self.assertIsInstance(self.stream.fetchone(), XidEvent)


    def test_log_pos_handles_disconnects(self):
        self.stream.close()
        self.stream = BinLogStreamReader(
            self.database,
            server_id=1024,
            resume_stream=False,
            only_events = [FormatDescriptionEvent, QueryEvent, TableMapEvent, WriteRowsEvent, XidEvent]
        )

        query = "CREATE TABLE test (id INT  PRIMARY KEY AUTO_INCREMENT, data VARCHAR (50) NOT NULL)"
        self.execute(query)
        query = "INSERT INTO test (data) VALUES('Hello')"
        self.execute(query)
        self.execute("COMMIT")

        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)
        self.assertGreater(self.stream.log_pos, 0)
        self.assertIsInstance(self.stream.fetchone(), QueryEvent)

        self.assertIsInstance(self.stream.fetchone(), QueryEvent)
        self.assertIsInstance(self.stream.fetchone(), TableMapEvent)
        self.assertIsInstance(self.stream.fetchone(), WriteRowsEvent)

        self.assertIsInstance(self.stream.fetchone(), XidEvent)

        self.assertGreater(self.stream.log_pos, 0)

    def test_skip_to_timestamp(self):
        self.stream.close()
        query = "CREATE TABLE test_1 (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        time.sleep(1)
        query = "SELECT UNIX_TIMESTAMP();"
        timestamp = self.execute(query).fetchone()[0]
        query2 = "CREATE TABLE test_2 (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query2)

        self.stream = BinLogStreamReader(
            self.database,
            server_id=1024,
            skip_to_timestamp=timestamp,
            ignored_events=self.ignoredEvents(),
            )
        event = self.stream.fetchone()
        self.assertIsInstance(event, QueryEvent)
        self.assertEqual(event.query, query2)


class TestMultipleRowBinLogStreamReader(base.PyMySQLReplicationTestCase):
    def ignoredEvents(self):
        return [GtidEvent]

    def test_insert_multiple_row_event(self):
        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)

        self.resetBinLog()

        query = "INSERT INTO test (data) VALUES('Hello'),('World')"
        self.execute(query)
        self.execute("COMMIT")

        self.assertIsInstance(self.stream.fetchone(), RotateEvent)
        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)
        #QueryEvent for the BEGIN
        self.assertIsInstance(self.stream.fetchone(), QueryEvent)

        self.assertIsInstance(self.stream.fetchone(), TableMapEvent)

        event = self.stream.fetchone()
        if self.isMySQL56AndMore():
            self.assertEqual(event.event_type, WRITE_ROWS_EVENT_V2)
        else:
            self.assertEqual(event.event_type, WRITE_ROWS_EVENT_V1)
        self.assertIsInstance(event, WriteRowsEvent)
        self.assertEqual(len(event.rows), 2)
        self.assertEqual(event.rows[0]["values"]["id"], 1)
        self.assertEqual(event.rows[0]["values"]["data"], "Hello")

        self.assertEqual(event.rows[1]["values"]["id"], 2)
        self.assertEqual(event.rows[1]["values"]["data"], "World")

    def test_update_multiple_row_event(self):
        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "INSERT INTO test (data) VALUES('Hello')"
        self.execute(query)
        query = "INSERT INTO test (data) VALUES('World')"
        self.execute(query)

        self.resetBinLog()

        query = "UPDATE test SET data = 'Toto'"
        self.execute(query)
        self.execute("COMMIT")

        self.assertIsInstance(self.stream.fetchone(), RotateEvent)
        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)
        #QueryEvent for the BEGIN
        self.assertIsInstance(self.stream.fetchone(), QueryEvent)

        self.assertIsInstance(self.stream.fetchone(), TableMapEvent)

        event = self.stream.fetchone()
        if self.isMySQL56AndMore():
            self.assertEqual(event.event_type, UPDATE_ROWS_EVENT_V2)
        else:
            self.assertEqual(event.event_type, UPDATE_ROWS_EVENT_V1)
        self.assertIsInstance(event, UpdateRowsEvent)
        self.assertEqual(len(event.rows), 2)
        self.assertEqual(event.rows[0]["before_values"]["id"], 1)
        self.assertEqual(event.rows[0]["before_values"]["data"], "Hello")
        self.assertEqual(event.rows[0]["after_values"]["id"], 1)
        self.assertEqual(event.rows[0]["after_values"]["data"], "Toto")

        self.assertEqual(event.rows[1]["before_values"]["id"], 2)
        self.assertEqual(event.rows[1]["before_values"]["data"], "World")
        self.assertEqual(event.rows[1]["after_values"]["id"], 2)
        self.assertEqual(event.rows[1]["after_values"]["data"], "Toto")

    def test_delete_multiple_row_event(self):
        query = "CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "INSERT INTO test (data) VALUES('Hello')"
        self.execute(query)
        query = "INSERT INTO test (data) VALUES('World')"
        self.execute(query)

        self.resetBinLog()

        query = "DELETE FROM test"
        self.execute(query)
        self.execute("COMMIT")

        self.assertIsInstance(self.stream.fetchone(), RotateEvent)
        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)

        #QueryEvent for the BEGIN
        self.assertIsInstance(self.stream.fetchone(), QueryEvent)

        self.assertIsInstance(self.stream.fetchone(), TableMapEvent)

        event = self.stream.fetchone()
        if self.isMySQL56AndMore():
            self.assertEqual(event.event_type, DELETE_ROWS_EVENT_V2)
        else:
            self.assertEqual(event.event_type, DELETE_ROWS_EVENT_V1)
        self.assertIsInstance(event, DeleteRowsEvent)
        self.assertEqual(len(event.rows), 2)
        self.assertEqual(event.rows[0]["values"]["id"], 1)
        self.assertEqual(event.rows[0]["values"]["data"], "Hello")

        self.assertEqual(event.rows[1]["values"]["id"], 2)
        self.assertEqual(event.rows[1]["values"]["data"], "World")

    def test_drop_table(self):
        self.execute("CREATE TABLE test (id INTEGER(11))")
        self.execute("INSERT INTO test VALUES (1)")
        self.execute("DROP TABLE test")
        self.execute("COMMIT")

        #RotateEvent
        self.stream.fetchone()
        #FormatDescription
        self.stream.fetchone()
        #QueryEvent for the Create Table
        self.stream.fetchone()

        #QueryEvent for the BEGIN
        self.stream.fetchone()

        event = self.stream.fetchone()
        self.assertIsInstance(event, TableMapEvent)

        event = self.stream.fetchone()
        if self.isMySQL56AndMore():
            self.assertEqual(event.event_type, WRITE_ROWS_EVENT_V2)
        else:
            self.assertEqual(event.event_type, WRITE_ROWS_EVENT_V1)
        self.assertIsInstance(event, WriteRowsEvent)

        self.assertEqual([], event.rows)

    def test_drop_table_tablemetadata_unavailable(self):
        self.stream.close()
        self.execute("CREATE TABLE test (id INTEGER(11))")
        self.execute("INSERT INTO test VALUES (1)")
        self.execute("DROP TABLE test")
        self.execute("COMMIT")

        self.stream = BinLogStreamReader(
            self.database,
            server_id=1024,
            only_events=(WriteRowsEvent,),
            fail_on_table_metadata_unavailable=True
        )
        had_error = False
        try:
            event = self.stream.fetchone()
        except TableMetadataUnavailableError as e:
            had_error = True
            assert "test" in e.args[0]
        finally:
            self.resetBinLog()
            assert had_error

    def test_drop_column(self):
        self.stream.close()
        self.execute("CREATE TABLE test_drop_column (id INTEGER(11), data VARCHAR(50))")
        self.execute("INSERT INTO test_drop_column VALUES (1, 'A value')")
        self.execute("COMMIT")
        self.execute("ALTER TABLE test_drop_column DROP COLUMN data")
        self.execute("INSERT INTO test_drop_column VALUES (2)")
        self.execute("COMMIT")

        self.stream = BinLogStreamReader(
            self.database,
            server_id=1024,
            only_events=(WriteRowsEvent,)
            )
        try:
            self.stream.fetchone()  # insert with two values
            self.stream.fetchone()  # insert with one value
        except Exception as e:
            self.fail("raised unexpected exception: {exception}".format(exception=e))
        finally:
            self.resetBinLog()

    @unittest.expectedFailure
    def test_alter_column(self):
        self.stream.close()
        self.execute("CREATE TABLE test_alter_column (id INTEGER(11), data VARCHAR(50))")
        self.execute("INSERT INTO test_alter_column VALUES (1, 'A value')")
        self.execute("COMMIT")
        # this is a problem only when column is added in position other than at the end
        self.execute("ALTER TABLE test_alter_column ADD COLUMN another_data VARCHAR(50) AFTER id")
        self.execute("INSERT INTO test_alter_column VALUES (2, 'Another value', 'A value')")
        self.execute("COMMIT")

        self.stream = BinLogStreamReader(
            self.database,
            server_id=1024,
            only_events=(WriteRowsEvent,),
            )
        event = self.stream.fetchone()  # insert with two values
        # both of these asserts fail because of issue underlying proble described in issue #118
        # because it got table schema info after the alter table, it wrongly assumes the second
        # column of the first insert is 'another_data'
        # ER: {'id': 1, 'data': 'A value'}
        # AR: {'id': 1, 'another_data': 'A value'}
        self.assertIn("data", event.rows[0]["values"])
        self.assertNot("another_data", event.rows[0]["values"])
        self.assertEqual(event.rows[0]["values"]["data"], 'A value')
        self.stream.fetchone()  # insert with three values

class TestCTLConnectionSettings(base.PyMySQLReplicationTestCase):

    def setUp(self):
        super(TestCTLConnectionSettings, self).setUp()
        self.stream.close()
        ctl_db = copy.copy(self.database)
        ctl_db["db"] = None
        ctl_db["port"] = 3307
        self.ctl_conn_control = pymysql.connect(**ctl_db)
        self.ctl_conn_control.cursor().execute("DROP DATABASE IF EXISTS pymysqlreplication_test")
        self.ctl_conn_control.cursor().execute("CREATE DATABASE pymysqlreplication_test")
        self.ctl_conn_control.close()
        ctl_db["db"] = "pymysqlreplication_test"
        self.ctl_conn_control = pymysql.connect(**ctl_db)
        self.stream = BinLogStreamReader(
            self.database,
            ctl_connection_settings=ctl_db,
            server_id=1024,
            only_events=(WriteRowsEvent,),
            fail_on_table_metadata_unavailable=True
        )

    def tearDown(self):
        super(TestCTLConnectionSettings, self).tearDown()
        self.ctl_conn_control.close()

    def test_seperate_ctl_settings_table_metadata_unavailable(self):
        self.execute("CREATE TABLE test (id INTEGER(11))")
        self.execute("INSERT INTO test VALUES (1)")
        self.execute("COMMIT")

        had_error = False
        try:
            event = self.stream.fetchone()
        except TableMetadataUnavailableError as e:
            had_error = True
            assert "test" in e.args[0]
        finally:
            self.resetBinLog()
            assert had_error

    def test_seperate_ctl_settings_no_error(self):
        self.execute("CREATE TABLE test (id INTEGER(11))")
        self.execute("INSERT INTO test VALUES (1)")
        self.execute("DROP TABLE test")
        self.execute("COMMIT")
        self.ctl_conn_control.cursor().execute("CREATE TABLE test (id INTEGER(11))")
        self.ctl_conn_control.cursor().execute("INSERT INTO test VALUES (1)")
        self.ctl_conn_control.cursor().execute("COMMIT")
        try:
            self.stream.fetchone()
        except Exception as e:
            self.fail("raised unexpected exception: {exception}".format(exception=e))
        finally:
            self.resetBinLog()

class TestGtidBinLogStreamReader(base.PyMySQLReplicationTestCase):
    def setUp(self):
        super(TestGtidBinLogStreamReader, self).setUp()
        if not self.supportsGTID:
            raise unittest.SkipTest("database does not support GTID, skipping GTID tests")

    def test_read_query_event(self):
        query = "CREATE TABLE test (id INT NOT NULL, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "SELECT @@global.gtid_executed;"
        gtid = self.execute(query).fetchone()[0]

        self.stream.close()
        self.stream = BinLogStreamReader(
            self.database, server_id=1024, blocking=True, auto_position=gtid,
            ignored_events=[HeartbeatLogEvent])

        self.assertIsInstance(self.stream.fetchone(), RotateEvent)
        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)

        # Insert first event
        query = "BEGIN;"
        self.execute(query)
        query = "INSERT INTO test (id, data) VALUES(1, 'Hello');"
        self.execute(query)
        query = "COMMIT;"
        self.execute(query)

        firstevent = self.stream.fetchone()
        self.assertIsInstance(firstevent, GtidEvent)

        self.assertIsInstance(self.stream.fetchone(), QueryEvent)
        self.assertIsInstance(self.stream.fetchone(), TableMapEvent)
        self.assertIsInstance(self.stream.fetchone(), WriteRowsEvent)
        self.assertIsInstance(self.stream.fetchone(), XidEvent)

        # Insert second event
        query = "BEGIN;"
        self.execute(query)
        query = "INSERT INTO test (id, data) VALUES(2, 'Hello');"
        self.execute(query)
        query = "COMMIT;"
        self.execute(query)

        secondevent = self.stream.fetchone()
        self.assertIsInstance(secondevent, GtidEvent)

        self.assertIsInstance(self.stream.fetchone(), QueryEvent)
        self.assertIsInstance(self.stream.fetchone(), TableMapEvent)
        self.assertIsInstance(self.stream.fetchone(), WriteRowsEvent)
        self.assertIsInstance(self.stream.fetchone(), XidEvent)

        self.assertEqual(secondevent.gno, firstevent.gno + 1)

    def test_position_gtid(self):
        query = "CREATE TABLE test (id INT NOT NULL, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)
        query = "BEGIN;"
        self.execute(query)
        query = "INSERT INTO test (id, data) VALUES(1, 'Hello');"
        self.execute(query)
        query = "COMMIT;"
        self.execute(query)

        query = "SELECT @@global.gtid_executed;"
        gtid = self.execute(query).fetchone()[0]

        query = "CREATE TABLE test2 (id INT NOT NULL, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))"
        self.execute(query)

        self.stream.close()
        self.stream = BinLogStreamReader(
            self.database, server_id=1024, blocking=True, auto_position=gtid,
            ignored_events=[HeartbeatLogEvent])

        self.assertIsInstance(self.stream.fetchone(), RotateEvent)
        self.assertIsInstance(self.stream.fetchone(), FormatDescriptionEvent)
        self.assertIsInstance(self.stream.fetchone(), GtidEvent)
        event = self.stream.fetchone()

        self.assertEqual(event.query, 'CREATE TABLE test2 (id INT NOT NULL, data VARCHAR (50) NOT NULL, PRIMARY KEY (id))');


class TestGtidRepresentation(unittest.TestCase):
    def test_gtidset_representation(self):
        set_repr = '57b70f4e-20d3-11e5-a393-4a63946f7eac:1-56,' \
                   '4350f323-7565-4e59-8763-4b1b83a0ce0e:1-20'

        myset = GtidSet(set_repr)
        self.assertEqual(str(myset), set_repr)

    def test_gtidset_representation_newline(self):
        set_repr = '57b70f4e-20d3-11e5-a393-4a63946f7eac:1-56,' \
                   '4350f323-7565-4e59-8763-4b1b83a0ce0e:1-20'
        mysql_repr = '57b70f4e-20d3-11e5-a393-4a63946f7eac:1-56,\n' \
                   '4350f323-7565-4e59-8763-4b1b83a0ce0e:1-20'

        myset = GtidSet(mysql_repr)
        self.assertEqual(str(myset), set_repr)

    def test_gtidset_representation_payload(self):
        set_repr = '57b70f4e-20d3-11e5-a393-4a63946f7eac:1-56,' \
                   '4350f323-7565-4e59-8763-4b1b83a0ce0e:1-20'

        myset = GtidSet(set_repr)
        payload = myset.encode()
        parsedset = myset.decode(io.BytesIO(payload))

        self.assertEqual(str(myset), str(parsedset))

        set_repr = '57b70f4e-20d3-11e5-a393-4a63946f7eac:1,' \
                   '4350f323-7565-4e59-8763-4b1b83a0ce0e:1-20'

        myset = GtidSet(set_repr)
        payload = myset.encode()
        parsedset = myset.decode(io.BytesIO(payload))

        self.assertEqual(str(myset), str(parsedset))

if __name__ == "__main__":
    import unittest
    unittest.main()
