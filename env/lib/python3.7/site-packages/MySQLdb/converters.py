"""MySQLdb type conversion module

This module handles all the type conversions for MySQL. If the default
type conversions aren't what you need, you can make your own. The
dictionary conversions maps some kind of type to a conversion function
which returns the corresponding value:

Key: FIELD_TYPE.* (from MySQLdb.constants)

Conversion function:

    Arguments: string

    Returns: Python object

Key: Python type object (from types) or class

Conversion function:

    Arguments: Python object of indicated type or class AND
               conversion dictionary

    Returns: SQL literal value

    Notes: Most conversion functions can ignore the dictionary, but
           it is a required parameter. It is necessary for converting
           things like sequences and instances.

Don't modify conversions if you can avoid it. Instead, make copies
(with the copy() method), modify the copies, and then pass them to
MySQL.connect().
"""

from _mysql import string_literal, escape, NULL
from MySQLdb.constants import FIELD_TYPE, FLAG
from MySQLdb.times import *
from MySQLdb.compat import PY2, long

NoneType = type(None)

import array

try:
    ArrayType = array.ArrayType
except AttributeError:
    ArrayType = array.array


def Bool2Str(s, d): return str(int(s))

def Str2Set(s):
    return set([ i for i in s.split(',') if i ])

def Set2Str(s, d):
    # Only support ascii string.  Not tested.
    return string_literal(','.join(s), d)

def Thing2Str(s, d):
    """Convert something into a string via str()."""
    return str(s)

def Unicode2Str(s, d):
    """Convert a unicode object to a string using the default encoding.
    This is only used as a placeholder for the real function, which
    is connection-dependent."""
    return s.encode()

def Float2Str(o, d):
    return '%.15g' % o

def None2NULL(o, d):
    """Convert None to NULL."""
    return NULL  # duh

def Thing2Literal(o, d):
    """Convert something into a SQL string literal.  If using
    MySQL-3.23 or newer, string_literal() is a method of the
    _mysql.MYSQL object, and this function will be overridden with
    that method when the connection is created."""
    return string_literal(o, d)


def char_array(s):
    return array.array('c', s)

def array2Str(o, d):
    return Thing2Literal(o.tostring(), d)

def quote_tuple(t, d):
    return "(%s)" % (','.join(escape_sequence(t, d)))

# bytes or str regarding to BINARY_FLAG.
_bytes_or_str = [(FLAG.BINARY, bytes)]

conversions = {
    int: Thing2Str,
    long: Thing2Str,
    float: Float2Str,
    NoneType: None2NULL,
    ArrayType: array2Str,
    bool: Bool2Str,
    Date: Thing2Literal,
    DateTimeType: DateTime2literal,
    DateTimeDeltaType: DateTimeDelta2literal,
    str: Thing2Literal,  # default
    set: Set2Str,

    FIELD_TYPE.TINY: int,
    FIELD_TYPE.SHORT: int,
    FIELD_TYPE.LONG: long,
    FIELD_TYPE.FLOAT: float,
    FIELD_TYPE.DOUBLE: float,
    FIELD_TYPE.DECIMAL: float,
    FIELD_TYPE.NEWDECIMAL: float,
    FIELD_TYPE.LONGLONG: long,
    FIELD_TYPE.INT24: int,
    FIELD_TYPE.YEAR: int,
    FIELD_TYPE.SET: Str2Set,
    FIELD_TYPE.TIMESTAMP: mysql_timestamp_converter,
    FIELD_TYPE.DATETIME: DateTime_or_None,
    FIELD_TYPE.TIME: TimeDelta_or_None,
    FIELD_TYPE.DATE: Date_or_None,

    FIELD_TYPE.TINY_BLOB: _bytes_or_str,
    FIELD_TYPE.MEDIUM_BLOB: _bytes_or_str,
    FIELD_TYPE.LONG_BLOB: _bytes_or_str,
    FIELD_TYPE.BLOB: _bytes_or_str,
    FIELD_TYPE.STRING: _bytes_or_str,
    FIELD_TYPE.VAR_STRING: _bytes_or_str,
    FIELD_TYPE.VARCHAR: _bytes_or_str,
}

if PY2:
    conversions[unicode] = Unicode2Str
else:
    conversions[bytes] = Thing2Literal

try:
    from decimal import Decimal
    conversions[FIELD_TYPE.DECIMAL] = Decimal
    conversions[FIELD_TYPE.NEWDECIMAL] = Decimal
except ImportError:
    pass
