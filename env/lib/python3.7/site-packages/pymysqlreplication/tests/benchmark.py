# -*- coding: utf-8 -*-
#
# This is a sample script in order to make benchmark
# on library speed.
#
#

import pymysql
import time
import random
import os
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import *
import cProfile


def execute(con, query):
    c = con.cursor()
    c.execute(query)
    return c

def consume_events():
    stream = BinLogStreamReader(connection_settings=database,
                                server_id=3,
                                resume_stream=False,
                                blocking=True,
                                only_events = [UpdateRowsEvent],
                                only_tables = ['test'] )
    start = time.clock()
    i = 0.0
    for binlogevent in stream:
            i += 1.0
            if i % 1000 == 0:
                print("%d event by seconds (%d total)" % (i / (time.clock() - start), i))
    stream.close()


database = {
    "host": "localhost",
    "user": "root",
    "passwd": "",
    "use_unicode": True,
    "charset": "utf8",
    "db": "pymysqlreplication_test"
}

conn = pymysql.connect(**database)

execute(conn, "DROP DATABASE IF EXISTS pymysqlreplication_test")
execute(conn, "CREATE DATABASE pymysqlreplication_test")
conn = pymysql.connect(**database)
execute(conn, "CREATE TABLE test (i INT) ENGINE = MEMORY")
execute(conn, "INSERT INTO test VALUES(1)")
execute(conn, "CREATE TABLE test2 (i INT) ENGINE = MEMORY")
execute(conn, "INSERT INTO test2 VALUES(1)")
execute(conn, "RESET MASTER")


if os.fork() != 0:
    print("Start insert data")
    while True:
        execute(conn, "UPDATE test SET i = i + 1;")
        execute(conn, "UPDATE test2 SET i = i + 1;")
else:
    consume_events()
    #cProfile.run('consume_events()')

