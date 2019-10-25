# -*- coding: utf-8 -*-

import pymysql
import copy
from pymysqlreplication import BinLogStreamReader
import os
import sys

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

base = unittest.TestCase


class PyMySQLReplicationTestCase(base):
    def ignoredEvents(self):
        return []

    def setUp(self):

        db = os.environ.get('DB')
        # default
        self.database = {
            "host": "localhost",
            "user": "root",
            "passwd": "",
            "port": 3306,
            "use_unicode": True,
            "charset": "utf8",
            "db": "pymysqlreplication_test"
        }
        if os.getenv("TRAVIS") is not None and db == "mysql56":
            self.database["user"] = "travis"

        self.conn_control = None
        db = copy.copy(self.database)
        db["db"] = None
        self.connect_conn_control(db)
        self.execute("DROP DATABASE IF EXISTS pymysqlreplication_test")
        self.execute("CREATE DATABASE pymysqlreplication_test")
        db = copy.copy(self.database)
        self.connect_conn_control(db)
        self.stream = None
        self.resetBinLog()
        self.isMySQL56AndMore()

    def getMySQLVersion(self):
        """Return the MySQL version of the server
        If version is 5.6.10-log the result is 5.6.10
        """
        return self.execute("SELECT VERSION()").fetchone()[0].split('-')[0]

    def isMySQL56AndMore(self):
        version = float(self.getMySQLVersion().rsplit('.', 1)[0])
        if version >= 5.6:
            return True
        return False

    def isMySQL57(self):
        version = float(self.getMySQLVersion().rsplit('.', 1)[0])
        return version == 5.7

    @property
    def supportsGTID(self):
        if not self.isMySQL56AndMore():
            return False
        return self.execute("SELECT @@global.gtid_mode ").fetchone()[0] == "ON"

    def connect_conn_control(self, db):
        if self.conn_control is not None:
            self.conn_control.close()
        self.conn_control = pymysql.connect(**db)

    def tearDown(self):
        self.conn_control.close()
        self.conn_control = None
        self.stream.close()
        self.stream = None

    def execute(self, query):
        c = self.conn_control.cursor()
        c.execute(query)
        return c

    def resetBinLog(self):
        self.execute("RESET MASTER")
        if self.stream is not None:
            self.stream.close()
        self.stream = BinLogStreamReader(self.database, server_id=1024,
                                         ignored_events=self.ignoredEvents())

    def set_sql_mode(self):
        """set sql_mode to test with same sql_mode (mysql 5.7 sql_mode default is changed)"""
        version = float(self.getMySQLVersion().rsplit('.', 1)[0])
        if version == 5.7:
            self.execute("set @@sql_mode='NO_ENGINE_SUBSTITUTION'")

    def bin_log_format(self):
        query = "select @@binlog_format"
        cursor = self.execute(query)
        result = cursor.fetchone()
        return result[0]

    def bin_log_basename(self):
        cursor = self.execute('select @@log_bin_basename')
        bin_log_basename = cursor.fetchone()[0]
        bin_log_basename = bin_log_basename.split("/")[-1]
        return bin_log_basename
