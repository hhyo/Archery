# -*- coding: utf-8 -*-
'''Test abnormal conditions, such as caused by a MySQL crash
'''
import os.path

from pymysqlreplication.tests import base
from pymysqlreplication.tests.binlogfilereader import SimpleBinLogFileReader
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.event import GtidEvent
from pymysqlreplication.event import RotateEvent

class TestAbnormalBinLogStreamReader(base.PyMySQLReplicationTestCase):
    '''Test abnormal condition handling in the BinLogStreamReader
    '''

    @staticmethod
    def ignored_events():
        '''Events the BinLogStreamReader should ignore'''
        return [GtidEvent]

    def test_no_trailing_rotate_event(self):
        '''A missing RotateEvent and skip_to_timestamp cause corruption

        This test shows that a binlog file which lacks the trailing RotateEvent
        and the use of the ``skip_to_timestamp`` argument together can cause
        the table_map to become corrupt.  The trailing RotateEvent has a
        timestamp, but may be lost if the server crashes.  The leading
        RotateEvent in the next binlog file always has a timestamp of 0, thus
        is discarded when ``skip_to_timestamp`` is greater than zero.
        '''
        self.execute(
            'CREATE TABLE test (id INT NOT NULL AUTO_INCREMENT, '
            'data VARCHAR (50) NOT NULL, PRIMARY KEY(id))')
        self.execute('SET AUTOCOMMIT = 0')
        self.execute('INSERT INTO test(id, data) VALUES (1, "Hello")')
        self.execute('COMMIT')
        timestamp = self.execute('SELECT UNIX_TIMESTAMP()').fetchone()[0]
        self.execute('FLUSH BINARY LOGS')
        self.execute('INSERT INTO test(id, data) VALUES (2, "Hi")')
        self.stream.close()
        self._remove_trailing_rotate_event_from_first_binlog()

        binlog = self.execute("SHOW BINARY LOGS").fetchone()[0]

        self.stream = BinLogStreamReader(
            self.database,
            server_id=1024,
            log_pos=4,
            log_file=binlog,
            skip_to_timestamp=timestamp,
            ignored_events=self.ignored_events())
        for _ in self.stream:
            pass
        # The table_map should be empty because of the binlog being rotated.
        self.assertEqual({}, self.stream.table_map)

    def _remove_trailing_rotate_event_from_first_binlog(self):
        '''Remove the trailing RotateEvent from the first binlog

        According to the MySQL Internals Manual, a RotateEvent will be added to
        the end of a binlog when the binlog is rotated.  This may not happen if
        the server crashes, for example.

        This method removes the trailing RotateEvent to verify that the library
        properly handles this case.
        '''
        datadir = self.execute("SHOW VARIABLES LIKE 'datadir'").fetchone()[1]
        binlog = self.execute("SHOW BINARY LOGS").fetchone()[0]
        binlogpath = os.path.join(datadir, binlog)

        reader = SimpleBinLogFileReader(binlogpath, only_events=[RotateEvent])
        for _ in reader:
            reader.truncatebinlog()
            break
