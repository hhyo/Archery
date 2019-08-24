# -*- coding: UTF-8 -*-
import re
import pymongo
import logging
import traceback
import json

from . import EngineBase
from .models import ResultSet
from bson import json_util

__author__ = 'jackie'

logger = logging.getLogger('default')


class MongoEngine(EngineBase):
    def get_connection(self, db_name=None):
        conn = pymongo.MongoClient(self.host, self.port, connect=True, connectTimeoutMS=10000)
        if self.user and self.password:
            conn.admin.authenticate(self.user, self.password)
        return conn

    @property
    def name(self):  # pragma: no cover
        return 'Mongo'

    @property
    def info(self):  # pragma: no cover
        return 'Mongo engine'

    def get_all_databases(self):
        result = ResultSet(full_sql='get databases')
        conn = self.get_connection()
        result.rows = conn.list_database_names()
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

    def get_all_tables(self, db_name):
        result = ResultSet(full_sql='get tables')
        conn = self.get_connection()
        db = conn[db_name]
        result.rows = db.list_collection_names()
        return result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True):
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
