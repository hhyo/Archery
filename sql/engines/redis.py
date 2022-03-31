# -*- coding: UTF-8 -*-
""" 
@author: hhyo、yyukai
@license: Apache Licence
@file: redis.py
@time: 2019/03/26
"""

import re
import shlex

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
        db_name = db_name or self.db_name
        if self.mode == 'cluster':
            return redis.cluster.RedisCluster(host=self.host, port=self.port, password=self.password,
                                encoding_errors='ignore', decode_responses=True, socket_connect_timeout=10)
        else:
            return redis.Redis(host=self.host, port=self.port, db=db_name, password=self.password,
                         encoding_errors='ignore', decode_responses=True, socket_connect_timeout=10)

    @property
    def name(self):
        return 'Redis'

    @property
    def info(self):
        return 'Redis engine'

    def get_all_databases(self, **kwargs):
        """
        获取数据库列表
        :return:
        """
        result = ResultSet(full_sql='CONFIG GET databases')
        conn = self.get_connection()
        try:
            rows = conn.config_get('databases')['databases']
        except Exception as e:
            logger.warning(f"Redis CONFIG GET databases 执行报错，异常信息：{e}")
            rows = 16
            result.error = str(e)

        db_list = [str(x) for x in range(int(rows))]
        result.rows = db_list
        return result

    def query_check(self, db_name=None, sql='', limit_num=0):
        """提交查询前的检查"""
        result = {'msg': '', 'bad_query': True, 'filtered_sql': sql, 'has_star': False}
        safe_cmd = ["scan", "exists", "ttl", "pttl", "type", "get", "mget", "strlen",
                    "hgetall", "hexists", "hget", "hmget", "hkeys", "hvals",
                    "smembers", "scard", "sdiff", "sunion", "sismember", "llen", "lrange", "lindex",
                    "zrange","zrangebyscore","zscore","zcard","zcount","zrank"]
        # 命令校验，仅可以执行safe_cmd内的命令
        for cmd in safe_cmd:
            if re.match(fr'^{cmd}', sql.strip(), re.I):
                result['bad_query'] = False
                break
        if result['bad_query']:
            result['msg'] = "禁止执行该命令！"
        return result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True, **kwargs):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection(db_name=db_name)
            rows = conn.execute_command(*shlex.split(sql))
            result_set.column_list = ['Result']
            if isinstance(rows, list) or isinstance(rows, tuple):
                if re.match(fr'^scan', sql.strip(), re.I):
                    keys = [[row] for row in rows[1]]
                    keys.insert(0, [rows[0]])
                    result_set.rows = tuple(keys)
                    result_set.affected_rows = len(rows[1])
                else:
                    result_set.rows = tuple([row] for row in rows)
                    result_set.affected_rows = len(rows)
            elif isinstance(rows, dict):
                result_set.column_list = ["field", "value"]
                result_set.rows = tuple([[k, v] for k, v in rows.items()])
                result_set.affected_rows = len(result_set.rows)
            else:
                result_set.rows = tuple([[rows]])
                result_set.affected_rows = 1 if rows else 0
            if limit_num > 0:
                result_set.rows = result_set.rows[0:limit_num]
        except Exception as e:
            logger.warning(f"Redis命令执行报错，语句：{sql}， 错误信息：{traceback.format_exc()}")
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
        split_sql = [cmd.strip() for cmd in sql.split('\n') if cmd.strip()]
        line = 1
        for cmd in split_sql:
            result = ReviewResult(id=line,
                                  errlevel=0,
                                  stagestatus='Audit completed',
                                  errormessage='None',
                                  sql=cmd,
                                  affected_rows=0,
                                  execute_time=0, )
            check_result.rows += [result]
            line += 1
        return check_result

    def execute_workflow(self, workflow):
        """执行上线单，返回Review set"""
        sql = workflow.sqlworkflowcontent.sql_content
        split_sql = [cmd.strip() for cmd in sql.split('\n') if cmd.strip()]
        execute_result = ReviewSet(full_sql=sql)
        line = 1
        cmd = None
        try:
            conn = self.get_connection(db_name=workflow.db_name)
            for cmd in split_sql:
                with FuncTimer() as t:
                    conn.execute_command(*shlex.split(cmd))
                execute_result.rows.append(ReviewResult(
                    id=line,
                    errlevel=0,
                    stagestatus='Execute Successfully',
                    errormessage='None',
                    sql=cmd,
                    affected_rows=0,
                    execute_time=t.cost,
                ))
                line += 1
        except Exception as e:
            logger.warning(f"Redis命令执行报错，语句：{cmd or sql}， 错误信息：{traceback.format_exc()}")
            # 追加当前报错语句信息到执行结果中
            execute_result.error = str(e)
            execute_result.rows.append(ReviewResult(
                id=line,
                errlevel=2,
                stagestatus='Execute Failed',
                errormessage=f'异常信息：{e}',
                sql=cmd,
                affected_rows=0,
                execute_time=0,
            ))
            line += 1
            # 报错语句后面的语句标记为审核通过、未执行，追加到执行结果中
            for statement in split_sql[line - 1:]:
                execute_result.rows.append(ReviewResult(
                    id=line,
                    errlevel=0,
                    stagestatus='Audit completed',
                    errormessage=f'前序语句失败, 未执行',
                    sql=statement,
                    affected_rows=0,
                    execute_time=0,
                ))
                line += 1
        return execute_result
