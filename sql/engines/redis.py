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

from common.utils.timer import FuncTimer
from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult

__author__ = 'hhyo'

logger = logging.getLogger('default')


class RedisEngine(EngineBase):
    def get_connection(self, db_name=None):
        db_name = db_name or 0
        return redis.Redis(host=self.host, port=self.port, db=db_name, password=self.password,
                           encoding_errors='ignore', decode_responses=True)

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
        result = ResultSet(full_sql='CONFIG GET databases')
        conn = self.get_connection()
        rows = conn.config_get('databases')['databases']
        db_list = [str(x) for x in range(int(rows))]
        result.rows = db_list
        return result

    def query_check(self, db_name=None, sql='', limit_num=0):
        """提交查询前的检查"""
        result = {'msg': '', 'bad_query': True, 'filtered_sql': sql, 'has_star': False}
        safe_cmd = ["scan", "exists", "ttl", "pttl", "type", "get", "mget", "strlen",
                    "hgetall", "hexists", "hget", "hmget", "hkeys", "hvals",
                    "smembers", "scard", "sdiff", "sunion", "sismember", "llen", "lrange", "lindex"]
        # 命令校验，仅可以执行safe_cmd内的命令
        for cmd in safe_cmd:
            if re.match(fr'^{cmd}', sql.strip(), re.I):
                result['bad_query'] = False
                break
        if result['bad_query']:
            result['msg'] = "禁止执行该命令！"
        return result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection(db_name=db_name)
            rows = conn.execute_command(sql)
            result_set.column_list = ['Result']
            if isinstance(rows, list):
                result_set.rows = tuple([row] for row in rows)
                result_set.affected_rows = len(rows)
            else:
                result_set.rows = tuple([[rows]])
                result_set.affected_rows = 1 if rows else 0
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

    def execute_check(self, db_name=None, sql=''):
        """上线单执行前的检查, 返回Review set"""
        check_result = ReviewSet(full_sql=sql)
        result = ReviewResult(id=1,
                              errlevel=0,
                              stagestatus='Audit completed',
                              errormessage='None',
                              sql=sql,
                              affected_rows=0,
                              execute_time=0, )
        check_result.rows += [result]
        return check_result

    def execute_workflow(self, workflow):
        """执行上线单，返回Review set"""
        sql = workflow.sqlworkflowcontent.sql_content
        execute_result = ReviewSet(full_sql=sql)
        try:
            conn = self.get_connection(db_name=workflow.db_name)
            with FuncTimer() as t:
                conn.execute_command(workflow.sqlworkflowcontent.sql_content)
            execute_result.rows.append(ReviewResult(
                id=1,
                errlevel=0,
                stagestatus='Execute Successfully',
                errormessage='None',
                sql=sql,
                affected_rows=0,
                execute_time=t.cost,
            ))
        except Exception as e:
            logger.error(f"Redis命令执行报错，语句：{sql}， 错误信息：{traceback.format_exc()}")
            execute_result.error = str(e)
            execute_result.rows.append(ReviewResult(
                id=1,
                errlevel=2,
                stagestatus='Execute Failed',
                errormessage=f'异常信息：{e}',
                sql=sql,
                affected_rows=0,
                execute_time=0,
            ))
        return execute_result
