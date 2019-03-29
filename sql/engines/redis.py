# -*- coding: UTF-8 -*-
""" 
@author: hhyo、yyukai
@license: Apache Licence 
@file: redis.py 
@time: 2019/03/26
"""

import re
import redis
import logging
import traceback
from . import EngineBase
from .models import ResultSet

__author__ = 'hhyo'

logger = logging.getLogger('default')


class RedisEngine(EngineBase):
    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        self.conn = redis.Redis(host=self.host, port=self.port, db=0, password=self.password,
                                encoding_errors='ignore', decode_responses=True)
        return self.conn

    @property
    def name(self):
        return 'Redis'

    @property
    def info(self):
        return 'Redis engine'

    def get_all_databases(self):
        """
        获取数据库列表
        :return:
        """
        conn = self.get_connection()
        rows = conn.config_get('databases')['databases']
        db_list = [str(x) for x in range(int(rows))]
        return db_list

    def query_check(self, db_name=None, sql='', limit_num=0):
        """提交查询前的检查"""
        result = {'msg': '', 'bad_query': False, 'filtered_sql': sql, 'has_star': False}
        safe_cmd = ["exists", "ttl", "pttl", "type", "get", "mget", "strlen",
                    "hgetall", "hexists", "hget", "hmget", "keys", "hkeys", "hvals",
                    "smembers", "scard", "sdiff", "sunion", "sismember", "llen", "lrange", "lindex"]
        # 命令校验，仅可以执行safe_cmd内的命令
        for cmd in safe_cmd:
            result['bad_query'] = True
            if re.match(fr'^{cmd}', sql.strip(), re.I):
                result['bad_query'] = False
                break
        # 禁止keys *
        if re.match(r'^keys\s+\*', sql.strip(), re.I):
            result['bad_query'] = True
        if result['bad_query']:
            result['msg'] = "禁止执行该命令！"
        return result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection()
            if db_name:
                conn.execute_command(f"select {db_name}")
            rows = conn.execute_command(sql)
            result_set.column_list = ['Result']
            if isinstance(rows, list):
                result_set.rows = tuple([row] for row in rows)
                result_set.affected_rows = len(rows)
            else:
                result_set.rows = tuple([[rows]])
                result_set.affected_rows = 1
            if limit_num > 0:
                result_set.rows = result_set.rows[0:limit_num]
        except Exception as e:
            logger.error(f"Redis命令执行报错，语句：{sql}， 错误信息：{traceback.format_exc()}")
            result_set.error = str(e)
        return result_set

    def filter_sql(self, sql='', limit_num=0):
        return sql.strip()

    def query_masking(self, db_name=None, sql='', resultset=None):
        """不做脱敏"""
        return resultset
