# -*- coding: UTF-8 -*-
"""
@author: hhyo、yyukai
@license: Apache Licence
@file: redis.py
@time: 2019/03/26
"""

import json
import re
import shlex

import redis
import rediscluster
import logging
import traceback

from common.utils.timer import FuncTimer
from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult

__author__ = "hhyo"

logger = logging.getLogger("default")


class RedisEngine(EngineBase):
    def get_connection(self, db_name=None):
        db_name = db_name or self.db_name
        if self.mode == "cluster":
            return rediscluster.RedisCluster(
                startup_nodes=[{"host": self.host, "port": self.port}],
                username=self.user,
                password=self.password or None,
                encoding_errors="ignore",
                decode_responses=True,
                socket_connect_timeout=10,
                ssl=self.instance.is_ssl,
            )
        else:
            return redis.Redis(
                host=self.host,
                port=self.port,
                db=db_name,
                username=self.user,
                password=self.password or None,
                encoding_errors="ignore",
                decode_responses=True,
                socket_connect_timeout=10,
                ssl=self.instance.is_ssl,
            )

    name = "Redis"

    info = "Redis engine"

    @staticmethod
    def _format_host_port(host, port):
        """格式化 host:port 字符串，IPv6 地址使用 [ip]:port 格式以避免歧义"""
        if ":" in host and not host.startswith("["):
            return f"[{host}]:{port}"
        return f"{host}:{port}"

    def get_cluster_master_nodes(self):
        """
        获取Redis集群所有主节点的host:port列表
        单机模式返回当前实例的host:port
        IPv6 地址使用 [ip]:port 格式
        """
        if self.mode != "cluster":
            return [self._format_host_port(self.host, self.port)]
        try:
            conn = self.get_connection()
            nodes_info = conn.execute_command("CLUSTER", "NODES")
            masters = []
            for line in nodes_info.split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 8 and "master" in parts[2] and "fail" not in parts[2]:
                    # 处理格式: 127.0.0.1:7001@17001、[2001:db8::10]:6379@16379、2001:db8::10:6379@16379
                    # 截取@之前的字符串，去掉[]即为 host:port
                    # 兼容redis7.2,hostname有可能在@之前，例如：ip:port,hostname@cport
                    host_port = parts[1].split("@")[0].split(",")[0]
                    # 如果 CLUSTER NODES 输出中没有方括号（某些 Redis 版本），
                    # 则需要手动添加以保持 IPv6 地址的格式一致性
                    if host_port.count(":") > 1 and not host_port.startswith("["):
                        # IPv6 地址不含方括号，使用 rsplit 分离端口后重新格式化
                        hp = host_port.rsplit(":", 1)
                        if len(hp) == 2:
                            host_port = f"[{hp[0]}]:{hp[1]}"
                    masters.append(host_port)
            return (
                masters if masters else [self._format_host_port(self.host, self.port)]
            )
        except Exception as e:
            logger.warning(f"获取Redis集群节点失败: {e}")
            return [self._format_host_port(self.host, self.port)]

    def test_connection(self):
        """
        使用 PING 命令测试实例连通性。
        - 单节点(redis.Redis): ping() 仅对当前连接节点发送 PING，返回 True/b'PONG'。
        - 集群(rediscluster.RedisCluster): ping() 为广播命令，会向集群中所有主节点发送 PING，
          任一节点不可达即抛出异常；返回值在不同版本可能为 True 或 {node: 'PONG'} 字典。
        """
        result = ResultSet(full_sql="PING")
        result.column_list = ["PING"]
        try:
            conn = self.get_connection()
            ping_result = conn.ping()
            if self.mode == "cluster" and isinstance(ping_result, dict):
                # 集群模式下展开每个主节点的 PING 结果
                rows = [[node, str(resp)] for node, resp in ping_result.items()]
                result.column_list = ["node", "PING"]
                result.rows = tuple(rows)
                result.affected_rows = len(rows)
            else:
                result.rows = ([str(ping_result)],)
                result.affected_rows = 1
        except Exception as e:
            logger.warning(f"Redis PING 执行报错，异常信息：{e}")
            result.error = str(e)
        return result

    def get_all_databases(self, **kwargs):
        """
        获取数据库列表，使用 INFO Keyspace 命令
        单节点模式：返回 db0~db15，补充缺失的库（keys为0），显示格式如 db0[100]
        集群模式：只有 db0，汇总所有主节点的 keys 数量
        :return: ResultSet，rows 为字典列表 [{"value": "0", "text": "db0[100]"}, ...]
        """
        result = ResultSet(full_sql="INFO Keyspace")
        try:
            if self.mode == "cluster":
                # 集群模式：只有 db0，汇总各主节点的 keys
                total_keys = 0
                master_nodes = self.get_cluster_master_nodes()
                for node in master_nodes:
                    try:
                        # IPv6 安全解析：使用 rsplit 从右侧分割，避免 IPv6 地址中的冒号干扰
                        # 例如：[2001:db8::10]:6379 → host=2001:db8::10, port=6379
                        host_port = node.rsplit(":", 1)
                        host = host_port[0].strip("[]")
                        port = int(host_port[1]) if len(host_port) > 1 else self.port
                        node_conn = redis.Redis(
                            host=host,
                            port=port,
                            username=self.user,
                            password=self.password or None,
                            encoding_errors="ignore",
                            decode_responses=True,
                            socket_connect_timeout=10,
                            ssl=self.instance.is_ssl,
                        )
                        info = node_conn.info("Keyspace")
                        if "db0" in info:
                            total_keys += info["db0"].get("keys", 0)
                        node_conn.close()
                    except Exception as e:
                        logger.warning(
                            f"Redis集群节点 {node} INFO Keyspace 执行报错，异常信息：{e}"
                        )
                text = f"db0[{total_keys}]" if total_keys > 0 else "db0"
                result.rows = [{"value": "0", "text": text}]
            else:
                # 单节点模式：获取 Keyspace 信息，补充 0~15 号库
                conn = self.get_connection()
                info = conn.info("Keyspace")
                # 解析 Keyspace 信息，构建 db_num -> keys 的映射
                db_keys = {}
                for key, val in info.items():
                    parts = key.split("db")
                    if len(parts) == 2 and parts[1].isdigit():
                        db_num = int(parts[1])
                        db_keys[db_num] = val.get("keys", 0)
                # 默认配置databases 16，只有16个库，这里取默认配置，不考虑新增到16以上的情况
                # 确定最大库号，至少到 15
                max_db = max(list(db_keys.keys()) + [15])
                # 构建结果列表，补充缺失的库
                db_list = []
                for i in range(max_db + 1):
                    keys = db_keys.get(i, 0)
                    text = f"db{i}[{keys}]" if keys > 0 else f"db{i}"
                    db_list.append({"value": str(i), "text": text})
                result.rows = db_list
        except Exception as e:
            logger.warning(f"Redis INFO Keyspace 执行报错，异常信息：{e}")
            result.error = str(e)
        return result

    def get_all_tables(self, db_name, **kwargs):
        """获取表列表。Redis的key可以理为表。方法只扫描部分表。起到预览作用。"""
        result = ResultSet(full_sql="")
        max_results = 100
        table_info_list = []
        try:
            conn = self.get_connection(db_name)
            scan_rows = conn.scan_iter(match=None, count=20)
            for idx, key in enumerate(scan_rows):
                if idx >= max_results:
                    break
                table_info_list.append(key)
        except Exception as e:
            logger.error(f"get_all_tables执行报错，异常信息：{e}")
            result.message = f"{e}"
        result.rows = table_info_list
        return result

    def query_check(self, db_name=None, sql="", limit_num=0):
        """提交查询前的检查"""
        result = {"msg": "", "bad_query": True, "filtered_sql": sql, "has_star": False}

        # 单单词查询命令（需要单词边界，防止 get 匹配 getdel）
        safe_single_cmds = [
            # 字符串
            "get",
            "mget",
            "strlen",
            "getrange",
            "getbit",
            # Bitmap
            "bitcount",
            "bitpos",
            # Hash
            "hget",
            "hmget",
            "hgetall",
            "hkeys",
            "hvals",
            "hlen",
            "hexists",
            "hstrlen",
            # List
            "llen",
            "lindex",
            "lrange",
            # Set
            "scard",
            "smembers",
            "sismember",
            "srandmember",
            "sdiff",
            "sinter",
            "sunion",
            # Sorted Set
            "zcard",
            "zcount",
            "zrange",
            "zrevrange",
            "zrangebyscore",
            "zrevrangebyscore",
            "zscore",
            "zrank",
            "zrevrank",
            "zlexcount",
            "zrangebylex",
            "zrevrangebylex",
            "zmscore",
            # HyperLogLog
            "pfcount",
            # Geo
            "geopos",
            "geodist",
            "geohash",
            # "georadius",
            # "georadiusbymember",
            "geosearch",
            # 通用
            "exists",
            "ttl",
            "pttl",
            "type",
            "dbsize",
            # "randomkey",  # 禁用 randomkey 命令，防止随机扫描
            "dump",
            # "keys",  # 禁用 keys 命令，防止全库扫描
            "scan",
            # Streams
            "xlen",
            "xrange",
            "xrevrange",
            # "xread",
            "xpending",
            # 服务器
            # "info",  # 禁用 info 命令，防止获取敏感信息
            "time",
            "command",
            "readonly",
        ]

        # 多单词查询命令
        safe_multi_cmds = [
            # "object encoding",
            # "object idletime",
            # "object refcount",
            "memory usage",
            "memory stats",
            "memory doctor",
            # "client list",
            "client info",
            "client getname",
            "client getredir",
            "client trackinginfo",
            # "config get",  # 禁用 config 命令，防止获取密码等敏感信息
            # "slowlog get",
            "slowlog len",
            # "pubsub channels",  # 禁用 pubsub 命令，防止获取敏感信息
            # "pubsub numsub",
            # "pubsub numpat",
            # "acl list",  # 禁用 acl 命令，防止获取敏感信息
            # "acl getuser",
            # "acl cat",
            # "acl whoami",
            # "acl log",
            # "acl help",
            # "module list",  # 禁用 module 命令，防止获取敏感信息
            # "module help",
            # "function list",  # 禁用 function 命令，防止获取敏感信息
            # "function dump",
            # "function stats",
            # "function help",
            # "latency doctor",  # 禁用 latency 命令，防止获取敏感信息
            # "latency graph",
            # "latency history",
            # "latency latest",
            # "cluster nodes",  # 禁用 cluster 命令，防止获取敏感信息
            # "cluster info",
            # "cluster slots",
            # "cluster shards",
            # "cluster keyslot",
            # "cluster countkeysinslot",
            # "xinfo stream",  # 禁用 xinfo 命令，防止获取敏感信息
            # "xinfo groups",
            # "xinfo consumers",
        ]

        sql_stripped = re.sub(r"\s+", " ", sql.strip())
        lower_sql = sql_stripped.lower()

        # 先匹配多单词命令（更具体的优先）
        for cmd in safe_multi_cmds:
            if lower_sql.startswith(cmd):
                result["bad_query"] = False
                break
        else:
            # 再匹配单单词命令（需要单词边界）
            for cmd in safe_single_cmds:
                if re.match(rf"^{cmd}\b", sql_stripped, re.I):
                    result["bad_query"] = False
                    break

        if result["bad_query"]:
            result["msg"] = "禁止执行该命令！"
        return result

    def processlist(self, command_type, **kwargs):
        """获取连接信息"""
        sql = "client list"
        result_set = ResultSet(full_sql=sql)
        conn = self.get_connection(db_name=0)
        clients = conn.client_list()

        # 处理集群模式返回值: 单节点返回 [dict, ...]，集群返回 {node: [dict, ...]}
        all_clients = []
        if isinstance(clients, dict):
            for node_clients in clients.values():
                if isinstance(node_clients, list):
                    all_clients.extend(node_clients)
        elif isinstance(clients, list):
            all_clients = clients

        # 根据空闲时间排序，过滤掉非字典项
        sort_by = "idle"
        reverse = False
        all_clients = sorted(
            [c for c in all_clients if isinstance(c, dict)],
            key=lambda client: client.get(sort_by, 0),
            reverse=reverse,
        )
        result_set.rows = all_clients
        return result_set

    def query(self, db_name=None, sql="", limit_num=0, close_conn=True, **kwargs):
        """返回 ResultSet"""
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection(db_name=db_name)
            rows = conn.execute_command(*shlex.split(sql))
            result_set.column_list = ["Result"]
            if isinstance(rows, list) or isinstance(rows, tuple):
                if re.match(rf"^scan", sql.strip(), re.I):
                    keys = [[row] for row in rows[1]]
                    keys.insert(0, [rows[0]])
                    result_set.rows = tuple(keys)
                    result_set.affected_rows = len(rows[1])
                else:
                    result_set.rows = tuple([row] for row in rows)
                    result_set.affected_rows = len(rows)
            elif isinstance(rows, dict):
                result_set.column_list = ["field", "value"]
                # 对Redis的返回结果进行类型判断，如果是dict,list转为json字符串。
                pairs_list = []
                for k, v in rows.items():
                    if isinstance(v, dict):
                        processed_value = json.dumps(v)
                    elif isinstance(v, list):
                        processed_value = json.dumps(v)
                    else:
                        processed_value = v
                    # 添加处理后的键值对到列表
                    pairs_list.append([k, processed_value])
                # 将列表转换为元组并赋值给 result_set.rows
                result_set.rows = tuple(pairs_list)
                result_set.affected_rows = len(result_set.rows)
            else:
                result_set.rows = tuple([[rows]])
                result_set.affected_rows = 1 if rows else 0
            if limit_num > 0:
                result_set.rows = result_set.rows[0:limit_num]
        except Exception as e:
            logger.warning(
                f"Redis命令执行报错，语句：{sql}， 错误信息：{traceback.format_exc()}"
            )
            result_set.error = str(e)
        return result_set

    def filter_sql(self, sql="", limit_num=0):
        return sql.strip()

    def query_masking(self, db_name=None, sql="", resultset=None):
        """不做脱敏"""
        return resultset

    def execute_check(self, db_name=None, sql=""):
        """上线单执行前的检查, 返回Review set"""
        check_result = ReviewSet(full_sql=sql)
        split_sql = [cmd.strip() for cmd in sql.split("\n") if cmd.strip()]
        line = 1

        # 单单词执行命令（写命令）
        exec_single_cmds = [
            # 字符串
            "append",
            "decr",
            "decrby",
            "getdel",
            "getex",
            "incr",
            "incrby",
            "incrbyfloat",
            "mset",
            "msetnx",
            "psetex",
            "set",
            "setex",
            "setnx",
            "setrange",
            # Hash
            "hdel",
            "hincrby",
            "hincrbyfloat",
            "hmset",
            "hset",
            "hsetnx",
            # List
            "blmove",
            "blmpop",
            # "blpop",
            # "brpop",
            # "brpoplpush",
            "linsert",
            "lmove",
            "lmpop",
            "lpop",
            "lpush",
            "lpushx",
            "lrem",
            "lset",
            "ltrim",
            "rpop",
            "rpoplpush",
            "rpush",
            "rpushx",
            # Set
            "sadd",
            "sdiffstore",
            "sinterstore",
            "smove",
            "spop",
            "srem",
            "sunionstore",
            # Sorted Set
            "zadd",
            "zdiffstore",
            "zincrby",
            "zinterstore",
            "zmpop",
            "zpopmax",
            "zpopmin",
            "zrangestore",
            "zrem",
            "zremrangebylex",
            "zremrangebyrank",
            "zremrangebyscore",
            "zunionstore",
            # Bitmap
            "setbit",
            # HyperLogLog
            "pfadd",
            "pfmerge",
            # Geo
            "geoadd",
            "geosearchstore",
            # 通用
            "copy",
            "del",
            "expire",
            "expireat",
            "move",
            "persist",
            "pexpire",
            "pexpireat",
            "rename",
            "renamenx",
            # "restore",  # 禁用 restore 命令，防止RDB数据恢复
            "sort",
            "touch",
            "unlink",
            # "flushdb",  # 禁用 flushdb 命令，防止数据丢失
            # "flushall",  # 禁用 flushall 命令，防止数据丢失
            # "swapdb",  # 禁用 swapdb 命令，防止数据丢失
            # 事务
            "discard",
            "exec",
            "multi",
            "unwatch",
            "watch",
            # 脚本
            # "eval",  # 禁用 eval 命令，防止执行任意代码
            # "evalsha",
            # 流
            "xack",
            "xadd",
            "xautoclaim",
            "xclaim",
            "xdel",
            "xtrim",
            # 连接
            # "select",  # 禁用 select 命令，防止数据库切换
            # 服务器
            # "save",  # 禁用 save 命令，阻塞式持久化
            "bgsave",
            # "slaveof",  # 禁用 slaveof 命令，防止数据复制
            # "replicaof",
        ]

        # 多单词执行命令（写命令），更具体的命令优先匹配
        exec_multi_cmds = [
            # ACL
            # "acl deluser",  # 禁用 acl 命令，防止设置敏感信息
            # "acl genpass",
            # "acl save",
            # "acl setuser",
            # 客户端
            # "client setname",  # 禁用 client 命令，防止设置客户端名称
            # "client kill",  # 禁用 client 命令，防止客户端断开连接
            # 配置
            # "config set",  # 禁用 config 命令，防止设置敏感信息
            # "config rewrite",
            # "config resetstat",
            # 延迟
            # "latency reset",  # 禁用 latency 命令，防止重置延迟监控数据
            # 内存
            # "memory purge",  # 禁用 memory 命令，防止内存操作
            # 模块
            # "module load",  # 禁用 module 命令，防止加载任意模块
            # "module unload",
            # 脚本
            # "script debug",  # 禁用 script 命令，防止执行任意代码
            # "script flush",
            # "script kill",
            # "script load",
            # 流组
            "xgroup create",
            "xgroup createconsumer",
            "xgroup delconsumer",
            "xgroup destroy",
            "xgroup setid",
        ]

        for cmd in split_sql:
            sql_stripped = re.sub(r"\s+", " ", cmd.strip())
            lower_sql = sql_stripped.lower()

            # 先检测是否为查询命令，执行工单中禁止使用查询命令
            query_check_result = self.query_check(db_name=db_name, sql=cmd)
            if not query_check_result["bad_query"]:
                result = ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="Audit failed",
                    errormessage="禁止使用查询命令！",
                    sql=cmd,
                    affected_rows=0,
                    execute_time=0,
                )
                check_result.rows += [result]
                line += 1
                continue

            # 再检测是否为合法执行命令（多单词优先，更具体）
            is_valid = False
            for safe_cmd in exec_multi_cmds:
                if lower_sql.startswith(safe_cmd):
                    is_valid = True
                    break
            else:
                for safe_cmd in exec_single_cmds:
                    if re.match(rf"^{safe_cmd}\b", sql_stripped, re.I):
                        is_valid = True
                        break

            if is_valid:
                result = ReviewResult(
                    id=line,
                    errlevel=0,
                    stagestatus="Audit completed",
                    errormessage="暂不支持显示影响行数",
                    sql=cmd,
                    affected_rows=0,
                    execute_time=0,
                )
            else:
                result = ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="Audit failed",
                    errormessage="禁止执行该命令！",
                    sql=cmd,
                    affected_rows=0,
                    execute_time=0,
                )
            check_result.rows += [result]
            line += 1
        return check_result

    def execute_workflow(self, workflow):
        """执行上线单，返回Review set"""
        sql = workflow.sqlworkflowcontent.sql_content
        split_sql = [cmd.strip() for cmd in sql.split("\n") if cmd.strip()]
        execute_result = ReviewSet(full_sql=sql)
        line = 1
        cmd = None
        try:
            conn = self.get_connection(db_name=workflow.db_name)
            for cmd in split_sql:
                with FuncTimer() as t:
                    conn.execute_command(*shlex.split(cmd))
                execute_result.rows.append(
                    ReviewResult(
                        id=line,
                        errlevel=0,
                        stagestatus="Execute Successfully",
                        errormessage="暂不支持显示影响行数",
                        sql=cmd,
                        affected_rows=0,
                        execute_time=t.cost,
                    )
                )
                line += 1
        except Exception as e:
            logger.warning(
                f"Redis命令执行报错，语句：{cmd or sql}， 错误信息：{traceback.format_exc()}"
            )
            # 追加当前报错语句信息到执行结果中
            execute_result.error = str(e)
            execute_result.rows.append(
                ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="Execute Failed",
                    errormessage=f"异常信息：{e}",
                    sql=cmd,
                    affected_rows=0,
                    execute_time=0,
                )
            )
            line += 1
            # 报错语句后面的语句标记为审核通过、未执行，追加到执行结果中
            for statement in split_sql[line - 1 :]:
                execute_result.rows.append(
                    ReviewResult(
                        id=line,
                        errlevel=0,
                        stagestatus="Audit completed",
                        errormessage=f"前序语句失败, 未执行",
                        sql=statement,
                        affected_rows=0,
                        execute_time=0,
                    )
                )
                line += 1
        return execute_result
