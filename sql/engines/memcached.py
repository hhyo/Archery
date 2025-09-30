#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import logging
import pymemcache

from typing import List
from . import EngineBase
from .models import ResultSet, ReviewSet

logger = logging.getLogger("default")


class MemcachedEngine(EngineBase):
    test_query = "stats"
    name = "Memcached"
    info = "Memcached engine"

    def __init__(self, instance=None):
        super().__init__(instance=instance)
        # 用于存储多个节点连接: db_name -> conn
        # 如果 instance.host 使用 , 分割
        self.nodes = {}

        if not instance:
            return

        for i, host in enumerate(instance.host.split(",")):
            db_name = f"Node - {i}"
            self.nodes[db_name] = host.strip()

    def get_connection(self, db_name=None):
        db_name = db_name or "Node - 0"

        if db_name not in self.nodes:
            logger.warning(f"Memcached节点 {db_name} 不存在，使用默认节点 {db_name}")
            raise Exception(f"Memcached节点 {db_name} 不存在")

        node_host = self.nodes[db_name]

        try:
            conn = pymemcache.Client(server=(node_host, self.port), connect_timeout=10.0, timeout=10.0)
            return conn
        except Exception as e:
            raise Exception(f"连接Memcached节点 {node_host} 失败: {str(e)}")

    def test_connection(self):
        """测试实例链接是否正常"""
        try:
            conn = self.get_connection(None)
            # 使用 version 命令测试
            version = conn.version()
            if version:
                return ResultSet(rows=[[f"连接成功，版本: {version}"]], column_list=["状态"])
        except Exception as e:
            logger.error(f"测试连接失败: {str(e)}")
            raise Exception(f"测试连接失败: {str(e)}")

    def get_all_databases(self):
        """获取所有可用节点，将节点作为"数据库"返回"""
        result_set = ResultSet(column_list=["节点"], rows=[])
        try:
            for db_name in self.nodes:
                result_set.rows.append([db_name])
            return result_set
        except Exception as e:
            logger.error(f"获取所有节点失败: {str(e)}")
            raise Exception(f"获取所有节点失败: {str(e)}")

    def get_all_tables(self, db_name, **kwargs):
        return ResultSet(rows=[])

    # 修改后的 query 方法
    def query(self, db_name=None, sql="", limit_num=0, close_conn=True, parameters=None, **kwargs):
        """实际查询 返回一个ResultSet，采用cmd table驱动模式"""
        result_set = ResultSet(full_sql=sql)

        try:
            conn = self.get_connection(db_name)

            # 简单解析SQL命令
            sql = sql.strip().lower()
            if not sql:
                raise Exception("空SQL语句")

            # 提取命令名称
            parts = sql.split(" ", -1)
            cmd = parts[0]
            cmd_args = parts[1:]

            # 命令处理函数映射表
            cmd_handlers = {
                "get": _handle_get,
                "set": _handle_set,
                "delete": _handle_delete,
                "version": _handle_version,
                "gets": _handle_gets,
                "incr": _handle_incr,
                "decr": _handle_decr,
                "touch": _handle_touch,
            }

            # 查找并执行对应的命令处理函数
            if cmd in cmd_handlers:
                result_set = cmd_handlers[cmd](conn, sql, cmd_args)
            else:
                raise Exception(f"不支持的命令: {cmd}")

        except Exception as e:
            logger.error(f"查询执行失败: {str(e)}")
            result_set.error = str(e)
            result_set.rows = [[f"错误: {str(e)}"]]
        finally:
            if close_conn:
                # 只关闭默认连接，保留节点连接
                if self.conn:
                    self.conn = None
                # 不关闭节点连接，因为可能会在后续查询中使用

        return result_set

    def query_check(self, db_name=None, sql=""):
        """查询语句的检查、注释去除、切分, 返回一个字典 {'bad_query': bool, 'filtered_sql': str}"""
        # 简单的SQL语法检查
        sql = sql.strip().lower()
        allowed_commands = ["version", "get", "set", "delete", "gets", "incr", "decr", "touch"]

        cmd = sql.split(" ")[0].strip()
        if cmd not in allowed_commands:
            return {"bad_query": True, "filtered_sql": sql,
                    "msg": "Only (version, get, set, delete, gets, incr, decr, touch) are supported"}

        return {"bad_query": False, "filtered_sql": sql}

    @property
    def server_version(self):
        """返回引擎服务器版本"""
        try:
            conn = self.get_connection()
            version = conn.version()
            # 尝试解析版本号为tuple
            parts = version.split()
            version_tuple = tuple(int(part) if part.isdigit() else 0 for part in parts[:3])
            return version_tuple
        except Exception as e:
            logger.error(f"获取Memcached版本失败: {str(e)}")
            return tuple()

    # 以下是Memcached不支持的功能，返回默认值或空结果

    @property
    def auto_backup(self):
        """是否支持备份"""
        return False

    @property
    def seconds_behind_master(self):
        """实例同步延迟情况"""
        return None

    def processlist(self, command_type, **kwargs):
        """获取连接信息"""
        return ResultSet()

    def kill_connection(self, thread_id):
        """终止数据库连接"""
        # Memcached不支持终止特定连接
        pass

    def get_table_meta_data(self, db_name, tb_name, **kwargs):
        """获取表格元信息"""
        return dict()

    def get_table_desc_data(self, db_name, tb_name, **kwargs):
        """获取表格字段信息"""
        return dict()

    def get_table_index_data(self, db_name, tb_name, **kwargs):
        """获取表格索引信息"""
        return dict()

    def get_tables_metas_data(self, db_name, **kwargs):
        """获取数据库所有表格信息"""
        return list()

    def get_all_databases_summary(self):
        """获取实例所有的数据库描述信息"""
        return ResultSet()

    def get_instance_users_summary(self):
        """获取实例所有账号信息"""
        return ResultSet()

    def create_instance_user(self, **kwargs):
        """创建实例账号"""
        return ResultSet()

    def drop_instance_user(self, **kwargs):
        """删除实例账号"""
        return ResultSet()

    def reset_instance_user_pwd(self, **kwargs):
        """重置实例账号密码"""
        return ResultSet()

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段"""
        return ResultSet()

    def describe_table(self, db_name, tb_name, **kwargs):
        """获取表结构"""
        return ResultSet()

    def execute(self, **kwargs):
        return ReviewSet()

    def execute_check(self, db_name=None, sql=""):
        """执行语句的检查"""
        return ReviewSet()

    def get_execute_percentage(self):
        """获取执行进度"""
        return 100

    def get_rollback(self, workflow):
        """获取工单回滚语句"""
        return list()

    def get_variables(self, variables=None):
        """获取实例参数"""
        return ResultSet()

    def set_variable(self, variable_name, variable_value):
        """修改实例参数值"""
        # Memcached不支持动态修改参数
        return ResultSet()

    def query_masking(self, db_name=None, sql="", resultset=None):
        """数据脱敏"""
        return resultset


# 命令处理函数

def _handle_get(conn: pymemcache.Client, sql: str, cmd_args: List[str]):
    """
    处理get命令: get <key>
    """

    result_set = ResultSet(full_sql=sql)

    if len(cmd_args) < 1:
        raise Exception("get命令格式错误")

    try:
        key = cmd_args[0].strip()
        value = conn.get(key)
        result_set.column_list = ["值"]
        result_set.rows = [[value if value is not None else "None"]]
    except Exception as e:
        raise Exception(f"get命令执行失败: {str(e)}")

    result_set.affected_rows = len(result_set.rows)
    return result_set


def _handle_set(conn: pymemcache.Client, sql: str, cmd_args: List[str]):
    """
    处理set命令: set <key> <value> [expiry]
    """

    result_set = ResultSet(full_sql=sql)

    if len(cmd_args) < 2:
        raise Exception("set命令格式错误")

    try:
        key = cmd_args[0].strip()
        expiry = int(cmd_args[2].strip()) if len(cmd_args) > 2 else 0
        value = cmd_args[1].strip()
        ok = conn.set(key, value, expire=expiry)
        result_set.rows = [["OK"] if ok else ["FAIL"]]
        result_set.column_list = ["状态"]
    except Exception as e:
        raise Exception(f"set命令执行失败: {str(e)}")

    result_set.affected_rows = len(result_set.rows)
    return result_set


def _handle_delete(conn: pymemcache.Client, sql: str, cmd_args: List[str]):
    """
    处理delete命令: delete <key>
    """

    result_set = ResultSet(full_sql=sql)

    if len(cmd_args) < 1:
        raise Exception("delete命令格式错误")

    try:
        key = cmd_args[0].strip()
        ok = conn.delete(key)
        result_set.rows = [["OK"] if ok else ["FAIL"]]
        result_set.column_list = ["状态"]
    except Exception as e:
        raise Exception(f"delete命令执行失败: {str(e)}")

    result_set.affected_rows = len(result_set.rows)
    return result_set


def _handle_version(conn: pymemcache.Client, sql: str, cmd_args: List[str]):
    """
    处理version命令: version
    """

    result_set = ResultSet(full_sql=sql)
    version = conn.version()
    result_set.rows = [[version]]
    result_set.column_list = ["版本"]
    result_set.affected_rows = 1
    return result_set


def _handle_gets(conn: pymemcache.Client, sql: str, cmd_args: List[str]):
    """
    处理gets命令: gets <key1> <key2>
    """

    result_set = ResultSet(full_sql=sql)

    if len(cmd_args) < 1:
        raise Exception("gets命令格式错误")

    try:
        keys = [v.strip() for v in cmd_args]
        values = conn.gets_many(keys)
        result_set.column_list = ["键", "值", "CAS"]
        for key, (value, cas) in values.items():
            result_set.rows.append([key, value if value is not None else "None", cas])
    except Exception as e:
        raise Exception(f"gets命令执行失败: {str(e)}")

    result_set.affected_rows = len(result_set.rows)
    return result_set


def _handle_incr(conn: pymemcache.Client, sql: str, cmd_args: List[str]):
    """
    处理incr命令: incr <key> [value]
    """

    result_set = ResultSet(full_sql=sql)

    if len(cmd_args) < 1:
        raise Exception("incr命令格式错误")
    try:
        key = cmd_args[0].strip()
        value = int(cmd_args[1].strip()) if len(cmd_args) > 1 else 1
        result = conn.incr(key, value)
        result_set.rows = [[str(result) if result is not None else "NOT_FOUND"]]
        result_set.column_list = ["结果"]
    except Exception as e:
        raise Exception(f"incr命令执行失败: {str(e)}")

    result_set.affected_rows = 1
    return result_set


def _handle_decr(conn: pymemcache.Client, sql: str, cmd_args: List[str]):
    """
    处理decr命令: decr <key> [value]
    """
    result_set = ResultSet(full_sql=sql)

    if len(cmd_args) < 1:
        raise Exception("decr命令格式错误")
    try:
        key = cmd_args[0].strip()
        value = int(cmd_args[1].strip()) if len(cmd_args) > 1 else 1
        result = conn.decr(key, value)
        result_set.rows = [[str(result) if result is not None else "NOT_FOUND"]]
        result_set.column_list = ["结果"]
    except Exception as e:
        raise Exception(f"decr命令执行失败: {str(e)}")

    result_set.affected_rows = 1
    return result_set


def _handle_touch(conn: pymemcache.Client, sql: str, cmd_args: List[str]):
    """
    处理touch命令: touch <key> <expiry>
    """

    result_set = ResultSet(full_sql=sql)

    if len(cmd_args) < 2:
        raise Exception("touch命令格式错误")

    try:
        key = cmd_args[0].strip()
        expiry = int(cmd_args[1].strip())
        ok = conn.touch(key, expire=expiry)
        result_set.rows = [["OK"] if ok else ["FAIL"]]
        result_set.column_list = ["状态"]
    except Exception as e:
        raise Exception(f"touch命令执行失败: {str(e)}")

    result_set.affected_rows = 1
    return result_set
