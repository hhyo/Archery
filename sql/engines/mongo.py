# -*- coding: UTF-8 -*-
"""
Copyright (c) 2013-2020, Arik Fraimovich.
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation and/or
   other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS
BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import re
import pymongo
import logging
import traceback
import simplejson as json

from sql.utils.human_time import parse_human_time
from . import EngineBase
from .models import ResultSet
from bson.son import SON
from bson import json_util
from bson.json_util import object_hook as bson_object_hook
from pymongo.errors import OperationFailure
from dateutil.parser import parse

__author__ = 'jackie'

logger = logging.getLogger('default')

date_regex = re.compile(r'ISODate\("(.*)"\)', re.IGNORECASE)


def parse_oids(oids):
    if not isinstance(oids, list):
        raise Exception("$oids takes an array as input.")

    return [bson_object_hook({"$oid": oid}) for oid in oids]


def datetime_parser(dct):
    for k, v in dct.items():
        if isinstance(v, str):
            m = date_regex.findall(v)
            if len(m) > 0:
                dct[k] = parse(m[0], yearfirst=True)

    if "$humanTime" in dct:
        return parse_human_time(dct["$humanTime"])

    if "$oids" in dct:
        return parse_oids(dct["$oids"])

    return bson_object_hook(dct)


def parse_query_json(query):
    return json.loads(query, object_hook=datetime_parser)


def parse_results(results):
    rows = []
    columns = []

    for row in results:
        parsed_row = {}
        for key in row:
            if isinstance(row[key], dict):
                for inner_key in row[key]:
                    column_name = "{}.{}".format(key, inner_key)
                    if column_name in columns:
                        columns.append(column_name)
                    parsed_row[column_name] = row[key][inner_key]
            else:
                if key in columns:
                    columns.append(key)
                parsed_row[key] = row[key]
        rows.append(parsed_row)
    return rows, columns


class MongoEngine(EngineBase):
    def get_connection(self, db_name=None):
        self.db_name = self.db_name or 'admin'
        conn = pymongo.MongoClient(self.host, self.port, authSource=self.db_name, connect=True, connectTimeoutMS=10000)
        if self.user and self.password:
            conn[self.db_name].authenticate(self.user, self.password, self.db_name)
        return conn

    @property
    def name(self):  # pragma: no cover
        return 'Mongo'

    @property
    def info(self):  # pragma: no cover
        return 'Mongo engine'

    def get_all_databases(self):
        result = ResultSet()
        conn = self.get_connection()
        try:
            result.rows = conn.list_database_names()
        except OperationFailure:
            result.rows = [self.db_name]
        return result

    def get_all_tables(self, db_name, **kwargs):
        result = ResultSet()
        conn = self.get_connection()
        db = conn[db_name]
        result.rows = db.list_collection_names()
        return result

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段, 返回一个ResultSet"""
        # https://github.com/getredash/redash/blob/master/redash/query_runner/mongodb.py
        result = ResultSet()
        db = self.get_connection()[db_name]
        collection_name = tb_name
        documents_sample = []
        if "viewOn" in db[collection_name].options():
            for d in db[collection_name].find().limit(2):
                documents_sample.append(d)
        else:
            for d in db[collection_name].find().sort([("$natural", 1)]).limit(1):
                documents_sample.append(d)

            for d in db[collection_name].find().sort([("$natural", -1)]).limit(1):
                documents_sample.append(d)
        columns = []
        # _merge_property_names
        for document in documents_sample:
            for prop in document:
                if prop not in columns:
                    columns.append(prop)
        result.column_list = ['COLUMN_NAME']
        result.rows = columns
        return result

    def describe_table(self, db_name, tb_name, **kwargs):
        """return ResultSet 类似查询"""
        result = self.get_all_columns_by_tb(db_name=db_name, tb_name=tb_name)
        result.rows = [[[r], ] for r in result.rows]
        return result

    def query_check(self, db_name=None, sql=''):
        """提交查询前的检查"""
        result = {'msg': '', 'bad_query': False, 'filtered_sql': sql, 'has_star': False}
        try:
            query_data = parse_query_json(sql)
            collection = query_data.get("collection")
            if not collection:
                raise AttributeError
        except ValueError:
            result['msg'] = "Invalid query format. The query is not a valid JSON."
            result['bad_query'] = True
        except AttributeError:
            result['msg'] = "'collection' must have a value to run a query"
            result['bad_query'] = True
        if result['bad_query']:
            result[
                'msg'] += "<br>关于查询语法请参考：<a target=\"_blank\" href=\"https://redash.io/help/data-sources/querying/mongodb#Query-Examples\">mongodb#Query-Examples</a>"
        return result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True, **kwargs):
        """"""
        result_set = ResultSet(full_sql=sql)
        query_data = parse_query_json(sql)
        query_limit = query_data.get('limit')
        query_data['limit'] = min(limit_num, query_limit) if query_limit else limit_num
        collection = query_data["collection"]

        try:
            conn = self.get_connection()
            db = conn[db_name]
            if collection not in db.list_collection_names():
                result_set.error = 'collection不存在，请确认'
                return result_set
            collection = db[collection]
            q = query_data.get("query", None)
            f = None

            aggregate = query_data.get("aggregate", None)
            if aggregate == 'aggregate':
                for step in aggregate:
                    if "$sort" in step:
                        sort_list = []
                        for sort_item in step["$sort"]:
                            sort_list.append((sort_item["name"], sort_item["direction"]))

                        step["$sort"] = SON(sort_list)

            if "fields" in query_data:
                f = query_data["fields"]

            s = None
            if "sort" in query_data and query_data["sort"]:
                s = []
                for field_data in query_data["sort"]:
                    s.append((field_data["name"], field_data["direction"]))

            columns = []
            rows = []

            cursor = None
            if q or (not q and not aggregate):
                if s:
                    cursor = collection.find(q, f).sort(s).limit(limit_num)
                else:
                    cursor = collection.find(q, f).limit(limit_num)

                if "skip" in query_data:
                    cursor = cursor.skip(query_data["skip"])

                if "limit" in query_data:
                    cursor = cursor.limit(query_data["limit"])

                if "count" in query_data:
                    cursor = cursor.count()

            elif aggregate:
                allow_disk_use = query_data.get("allowDiskUse", False)
                r = collection.aggregate(aggregate, allowDiskUse=allow_disk_use)
                if isinstance(r, dict):
                    cursor = r["result"]
                else:
                    cursor = r

            if "count" in query_data:
                columns.append("count")
                rows.append({"count": cursor})
            else:
                rows, columns = parse_results(cursor)

            if f:
                ordered_columns = []
                for k in sorted(f, key=f.get):
                    if k in columns:
                        ordered_columns.append(k)

                columns = ordered_columns

            if query_data.get("sortColumns"):
                reverse = query_data["sortColumns"] == "desc"
                columns = sorted(columns, key=lambda col: col, reverse=reverse)

            rows = json.loads(json_util.dumps(rows))
            result_set.column_list = columns or ['Result']
            if isinstance(rows, list):
                result_set.rows = tuple([json.dumps(x, ensure_ascii=False)] for x in rows)
                result_set.affected_rows = len(rows)
        except Exception as e:
            logger.warning(f"Mongo命令执行报错，语句：{sql}， 错误信息：{traceback.format_exc()}")
            result_set.error = str(e)
        return result_set
