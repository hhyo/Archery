# -*- coding: UTF-8 -*-
import re
import pymongo
import logging
import traceback
import json

from . import EngineBase
from .models import ResultSet
from bson import json_util
from pymongo.errors import OperationFailure

__author__ = 'jackie'

logger = logging.getLogger('default')


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
        result = {'msg': '', 'bad_query': True, 'filtered_sql': sql, 'has_star': False}
        safe_cmd = ['find']
        sql = sql.split('.')[1]
        for cmd in safe_cmd:
            if re.match(fr'^{cmd}\(.*', sql.strip(), re.I):
                result['bad_query'] = False
                break
        if result['bad_query']:
            result['msg'] = """禁止执行该命令！正确格式为：{collection_name}.find() or {collection_name}.find(expression)""", \
                            """如 : 'test.find({"id":{"$gt":1.0}})'"""
        return result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True, **kwargs):
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection()
            db = conn[db_name]
            collect = db[sql.split('.')[0]]
            match = re.compile(r'[(](.*)[)]', re.S)
            sql = re.findall(match, sql)[0]
            if sql != '':
                sql = json.loads(sql)
                result = collect.find(sql).limit(limit_num)
            else:
                result = collect.find(sql).limit(limit_num)
            rows = json.loads(json_util.dumps(result))
            result_set.column_list = ['Result']
            if isinstance(rows, list):
                result_set.rows = tuple([json.dumps(x, ensure_ascii=False)] for x in rows)
                result_set.affected_rows = len(rows)
        except Exception as e:
            logger.warning(f"Mongo命令执行报错，语句：{sql}， 错误信息：{traceback.format_exc()}")
            result_set.error = str(e)
        return result_set
