#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import datetime
import pymysql
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.event import QueryEvent, RotateEvent, FormatDescriptionEvent
from .binlog2sql_util import command_line_args, concat_sql_from_binlog_event, create_unique_file, temp_open, \
    reversed_lines, is_dml_event, event_type


class Binlog2sql(object):

    def __init__(self, connection_settings, start_file=None, start_pos=None, end_file=None, end_pos=None,
                 start_time=None, stop_time=None, only_schemas=None, only_tables=None, no_pk=False,
                 flashback=False, stop_never=False, back_interval=1.0, only_dml=True, sql_type=None):
        """
        conn_setting: {'host': 127.0.0.1, 'port': 3306, 'user': user, 'passwd': passwd, 'charset': 'utf8'}
        """

        if not start_file:
            raise ValueError('Lack of parameter: start_file')

        self.conn_setting = connection_settings
        self.start_file = start_file
        self.start_pos = start_pos if start_pos else 4  # use binlog v4
        self.end_file = end_file if end_file else start_file
        self.end_pos = end_pos
        if start_time:
            self.start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        else:
            self.start_time = datetime.datetime.strptime('1980-01-01 00:00:00', "%Y-%m-%d %H:%M:%S")
        if stop_time:
            self.stop_time = datetime.datetime.strptime(stop_time, "%Y-%m-%d %H:%M:%S")
        else:
            self.stop_time = datetime.datetime.strptime('2999-12-31 00:00:00', "%Y-%m-%d %H:%M:%S")

        self.only_schemas = only_schemas if only_schemas else None
        self.only_tables = only_tables if only_tables else None
        self.no_pk, self.flashback, self.stop_never, self.back_interval = (no_pk, flashback, stop_never, back_interval)
        self.only_dml = only_dml
        self.sql_type = [t.upper() for t in sql_type] if sql_type else []

        self.binlogList = []
        self.connection = pymysql.connect(**self.conn_setting)
        with self.connection as cursor:
            cursor.execute("SHOW MASTER STATUS")
            self.eof_file, self.eof_pos = cursor.fetchone()[:2]
            cursor.execute("SHOW MASTER LOGS")
            bin_index = [row[0] for row in cursor.fetchall()]
            if self.start_file not in bin_index:
                raise ValueError('parameter error: start_file %s not in mysql server' % self.start_file)
            binlog2i = lambda x: x.split('.')[1]
            for binary in bin_index:
                if binlog2i(self.start_file) <= binlog2i(binary) <= binlog2i(self.end_file):
                    self.binlogList.append(binary)

            cursor.execute("SELECT @@server_id")
            self.server_id = cursor.fetchone()[0]
            if not self.server_id:
                raise ValueError('missing server_id in %s:%s' % (self.conn_setting['host'], self.conn_setting['port']))

    def process_binlog(self):
        sql_list = []
        stream = BinLogStreamReader(connection_settings=self.conn_setting, server_id=self.server_id,
                                    log_file=self.start_file, log_pos=self.start_pos, only_schemas=self.only_schemas,
                                    only_tables=self.only_tables, resume_stream=True)

        flag_last_event = False
        e_start_pos, last_pos = stream.log_pos, stream.log_pos
        # to simplify code, we do not use flock for tmp_file.
        tmp_file = create_unique_file('%s.%s' % (self.conn_setting['host'], self.conn_setting['port']))
        with temp_open(tmp_file, "w") as f_tmp, self.connection as cursor:
            for binlog_event in stream:
                if not self.stop_never:
                    try:
                        event_time = datetime.datetime.fromtimestamp(binlog_event.timestamp)
                    except OSError:
                        event_time = datetime.datetime(1980, 1, 1, 0, 0)
                    if (stream.log_file == self.end_file and stream.log_pos == self.end_pos) or \
                            (stream.log_file == self.eof_file and stream.log_pos == self.eof_pos):
                        flag_last_event = True
                    elif event_time < self.start_time:
                        if not (isinstance(binlog_event, RotateEvent)
                                or isinstance(binlog_event, FormatDescriptionEvent)):
                            last_pos = binlog_event.packet.log_pos
                        continue
                    elif (stream.log_file not in self.binlogList) or \
                            (self.end_pos and stream.log_file == self.end_file and stream.log_pos > self.end_pos) or \
                            (stream.log_file == self.eof_file and stream.log_pos > self.eof_pos) or \
                            (event_time >= self.stop_time):
                        break
                    # else:
                    #     raise ValueError('unknown binlog file or position')

                if isinstance(binlog_event, QueryEvent) and binlog_event.query == 'BEGIN':
                    e_start_pos = last_pos

                if isinstance(binlog_event, QueryEvent) and not self.only_dml:
                    sql = concat_sql_from_binlog_event(cursor=cursor, binlog_event=binlog_event,
                                                       flashback=self.flashback, no_pk=self.no_pk)
                    if sql:
                        # print(sql)
                        sql_list.append(sql)
                elif is_dml_event(binlog_event) and event_type(binlog_event) in self.sql_type:
                    for row in binlog_event.rows:
                        sql = concat_sql_from_binlog_event(cursor=cursor, binlog_event=binlog_event, no_pk=self.no_pk,
                                                           row=row, flashback=self.flashback, e_start_pos=e_start_pos)
                        if self.flashback:
                            f_tmp.write(sql + '\n')
                        else:
                            # print(sql)
                            sql_list.append(sql)

                if not (isinstance(binlog_event, RotateEvent) or isinstance(binlog_event, FormatDescriptionEvent)):
                    last_pos = binlog_event.packet.log_pos
                if flag_last_event:
                    break

            stream.close()
            f_tmp.close()
            if self.flashback:
                sql_list = self.print_rollback_sql(filename=tmp_file)
        # return True
        return sql_list

    def print_rollback_sql(self, filename):
        """print rollback sql from tmp_file"""
        sql_list = []
        with open(filename, "rb") as f_tmp:
            batch_size = 1000
            i = 0
            for line in reversed_lines(f_tmp):
                # print(line.rstrip())
                sql_list.append(line.rstrip())
                if i >= batch_size:
                    i = 0
                    if self.back_interval:
                        print('SELECT SLEEP(%s);' % self.back_interval)
                else:
                    i += 1
        return sql_list

    def __del__(self):
        pass


if __name__ == '__main__':
    args = command_line_args(sys.argv[1:])
    conn_setting = {'host': args.host, 'port': args.port, 'user': args.user, 'passwd': args.password, 'charset': 'utf8'}
    binlog2sql = Binlog2sql(connection_settings=conn_setting, start_file=args.start_file, start_pos=args.start_pos,
                            end_file=args.end_file, end_pos=args.end_pos, start_time=args.start_time,
                            stop_time=args.stop_time, only_schemas=args.databases, only_tables=args.tables,
                            no_pk=args.no_pk, flashback=args.flashback, stop_never=args.stop_never,
                            back_interval=args.back_interval, only_dml=args.only_dml, sql_type=args.sql_type)
    binlog2sql.process_binlog()
