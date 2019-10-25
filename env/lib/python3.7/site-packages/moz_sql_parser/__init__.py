# encoding: utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#

from __future__ import absolute_import, division, unicode_literals

from collections import Mapping
import json
from threading import Lock

from mo_future import binary_type, items, number_types, text_type
from pyparsing import ParseException, ParseResults

from moz_sql_parser.sql_parser import SQLParser, all_exceptions


def __deploy__():
    # ONLY MEANT TO BE RUN FOR DEPLOYMENT
    from mo_files import File
    source_file = File("moz_sql_parser/sql_parser.py")
    lines = source_file.read().split("\n")
    lines = [
        "sys.setrecursionlimit(1500)" if line.startswith("sys.setrecursionlimit") else line
        for line in lines
    ]
    source_file.write("\n".join(lines))


parseLocker = Lock()  # ENSURE ONLY ONE PARSING AT A TIME


def parse(sql):
    with parseLocker:
        try:
            all_exceptions.clear()
            sql = sql.rstrip().rstrip(";")
            parse_result = SQLParser.parseString(sql, parseAll=True)
            return _scrub(parse_result)
        except Exception as e:
            if isinstance(e, ParseException) and e.msg == "Expected end of text":
                problems = all_exceptions.get(e.loc, [])
                expecting = [
                    f
                    for f in (set(p.msg.lstrip("Expected").strip() for p in problems)-{"Found unwanted token"})
                    if not f.startswith("{")
                ]
                raise ParseException(sql, e.loc, "Expecting one of (" + (", ".join(expecting)) + ")")
            raise


def format(json, **kwargs):
    from moz_sql_parser.formatting import Formatter
    return Formatter(**kwargs).format(json)


def _scrub(result):
    if isinstance(result, text_type):
        return result
    elif isinstance(result, binary_type):
        return result.decode('utf8')
    elif isinstance(result, number_types):
        return result
    elif not result:
        return {}
    elif isinstance(result, (list, ParseResults)):
        if not result:
            return None
        elif len(result) == 1:
            return _scrub(result[0])
        else:
            output = [
                rr
                for r in result
                for rr in [_scrub(r)]
                if rr != None
            ]
            # IF ALL MEMBERS OF A LIST ARE LITERALS, THEN MAKE THE LIST LITERAL
            if all(isinstance(r, Mapping) and "literal" in r.keys() for r in output):
                output = {"literal": [r['literal'] for r in output]}
            return output
    elif not items(result):
        return {}
    else:
        return {
            k: vv
            for k, v in result.items()
            for vv in [_scrub(v)]
            if vv != None
        }


_ = json.dumps


__all__ = [
    'parse',
    'format'
]
