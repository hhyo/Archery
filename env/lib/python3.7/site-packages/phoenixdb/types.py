# Copyright 2015 Lukas Lalinsky
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import time
import datetime
from decimal import Decimal
from phoenixdb.calcite import common_pb2

__all__ = [
    'Date', 'Time', 'Timestamp', 'DateFromTicks', 'TimeFromTicks', 'TimestampFromTicks',
    'Binary', 'STRING', 'BINARY', 'NUMBER', 'DATETIME', 'ROWID', 'BOOLEAN',
    'JAVA_CLASSES', 'JAVA_CLASSES_MAP', 'TypeHelper',
]


def Date(year, month, day):
    """Constructs an object holding a date value."""
    return datetime.date(year, month, day)


def Time(hour, minute, second):
    """Constructs an object holding a time value."""
    return datetime.time(hour, minute, second)


def Timestamp(year, month, day, hour, minute, second):
    """Constructs an object holding a datetime/timestamp value."""
    return datetime.datetime(year, month, day, hour, minute, second)


def DateFromTicks(ticks):
    """Constructs an object holding a date value from the given UNIX timestamp."""
    return Date(*time.localtime(ticks)[:3])


def TimeFromTicks(ticks):
    """Constructs an object holding a time value from the given UNIX timestamp."""
    return Time(*time.localtime(ticks)[3:6])


def TimestampFromTicks(ticks):
    """Constructs an object holding a datetime/timestamp value from the given UNIX timestamp."""
    return Timestamp(*time.localtime(ticks)[:6])


def Binary(value):
    """Constructs an object capable of holding a binary (long) string value."""
    return bytes(value)


def time_from_java_sql_time(n):
    dt = datetime.datetime(1970, 1, 1) + datetime.timedelta(milliseconds=n)
    return dt.time()


def time_to_java_sql_time(t):
    return ((t.hour * 60 + t.minute) * 60 + t.second) * 1000 + t.microsecond // 1000


def date_from_java_sql_date(n):
    return datetime.date(1970, 1, 1) + datetime.timedelta(days=n)


def date_to_java_sql_date(d):
    if isinstance(d, datetime.datetime):
        d = d.date()
    td = d - datetime.date(1970, 1, 1)
    return td.days


def datetime_from_java_sql_timestamp(n):
    return datetime.datetime(1970, 1, 1) + datetime.timedelta(milliseconds=n)


def datetime_to_java_sql_timestamp(d):
    td = d - datetime.datetime(1970, 1, 1)
    return td.microseconds // 1000 + (td.seconds + td.days * 24 * 3600) * 1000


class ColumnType(object):

    def __init__(self, eq_types):
        self.eq_types = tuple(eq_types)
        self.eq_types_set = set(eq_types)

    def __eq__(self, other):
        return other in self.eq_types_set

    def __cmp__(self, other):
        if other in self.eq_types_set:
            return 0
        if other < self.eq_types:
            return 1
        else:
            return -1


STRING = ColumnType(['VARCHAR', 'CHAR'])
"""Type object that can be used to describe string-based columns."""

BINARY = ColumnType(['BINARY', 'VARBINARY'])
"""Type object that can be used to describe (long) binary columns."""

NUMBER = ColumnType(['INTEGER', 'UNSIGNED_INT', 'BIGINT', 'UNSIGNED_LONG', 'TINYINT', 'UNSIGNED_TINYINT', 'SMALLINT', 'UNSIGNED_SMALLINT', 'FLOAT', 'UNSIGNED_FLOAT', 'DOUBLE', 'UNSIGNED_DOUBLE', 'DECIMAL'])
"""Type object that can be used to describe numeric columns."""

DATETIME = ColumnType(['TIME', 'DATE', 'TIMESTAMP', 'UNSIGNED_TIME', 'UNSIGNED_DATE', 'UNSIGNED_TIMESTAMP'])
"""Type object that can be used to describe date/time columns."""

ROWID = ColumnType([])
"""Only implemented for DB API 2.0 compatibility, not used."""

BOOLEAN = ColumnType(['BOOLEAN'])
"""Type object that can be used to describe boolean columns. This is a phoenixdb-specific extension."""


# XXX ARRAY

JAVA_CLASSES = {
    'bool_value': [
        ('java.lang.Boolean', common_pb2.BOOLEAN, None, None),
    ],
    'string_value': [
        ('java.lang.Character', common_pb2.CHARACTER, None, None),
        ('java.lang.String', common_pb2.STRING, None, None),
        ('java.math.BigDecimal', common_pb2.BIG_DECIMAL, str, Decimal),
    ],
    'number_value': [
        ('java.lang.Integer', common_pb2.INTEGER, None, int),
        ('java.lang.Short', common_pb2.SHORT, None, int),
        ('java.lang.Long', common_pb2.LONG, None, long if sys.version_info[0] < 3 else int),
        ('java.lang.Byte', common_pb2.BYTE, None, int),
        ('java.sql.Time', common_pb2.JAVA_SQL_TIME, time_to_java_sql_time, time_from_java_sql_time),
        ('java.sql.Date', common_pb2.JAVA_SQL_DATE, date_to_java_sql_date, date_from_java_sql_date),
        ('java.sql.Timestamp', common_pb2.JAVA_SQL_TIMESTAMP, datetime_to_java_sql_timestamp, datetime_from_java_sql_timestamp),
    ],
    'bytes_value': [
        ('[B', common_pb2.BYTE_STRING, Binary, None),
    ],
    'double_value': [
        # if common_pb2.FLOAT is used, incorrect values are sent
        ('java.lang.Float', common_pb2.DOUBLE, float, float),
        ('java.lang.Double', common_pb2.DOUBLE, float, float),
    ]
}
"""Groups of Java classes."""

JAVA_CLASSES_MAP = dict( (v[0], (k, v[1], v[2], v[3])) for k in JAVA_CLASSES for v in JAVA_CLASSES[k] )
"""Flips the available types to allow for faster lookup by Java class.

This mapping should be structured as:
    {
        'java.math.BigDecimal': ('string_value', common_pb2.BIG_DECIMAL, str, Decimal),),
        ...
        '<java class>': (<field_name>, <Rep enum>, <mutate_to function>, <cast_from function>),
    }
"""


class TypeHelper(object):
    @staticmethod
    def from_class(klass):
        """Retrieves a Rep and functions to cast to/from based on the Java class.

        :param klass:
            The string of the Java class for the column or parameter.

        :returns: tuple ``(field_name, rep, mutate_to, cast_from)``
            WHERE
            ``field_name`` is the attribute in ``common_pb2.TypedValue``
            ``rep`` is the common_pb2.Rep enum
            ``mutate_to`` is the function to cast values into Phoenix values, if any
            ``cast_from`` is the function to cast from the Phoenix value to the Python value, if any

        :raises:
            NotImplementedError
        """
        if klass not in JAVA_CLASSES_MAP:
            raise NotImplementedError('type {} is not supported'.format(klass))

        return JAVA_CLASSES_MAP[klass]
