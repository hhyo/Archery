# -*- coding: UTF-8 -*-
"""
Redis 引擎单元测试
对 sql/engines/redis.py 中的 RedisEngine 进行全面的功能覆盖测试

所有测试使用 Mock 对象模拟 Instance，不依赖真实 Redis 服务
"""

import json
from unittest.mock import patch, Mock, MagicMock, call

import pytest

from sql.engines.redis import RedisEngine
from sql.engines.models import ResultSet, ReviewSet, ReviewResult

# ====================== Fixtures ======================


@pytest.fixture
def mock_instance():
    """模拟 Instance 对象，避免对 Django ORM 和数据库的依赖"""
    ins = Mock()
    ins.instance_name = "redis_ins"
    ins.host = "127.0.0.1"
    ins.port = 6379
    ins.db_name = "0"
    ins.db_type = "redis"
    ins.mode = ""
    ins.tunnel = None
    ins.is_ssl = False
    ins.get_username_password.return_value = ("ins_user", "some_str")
    return ins


@pytest.fixture
def mock_cluster_instance():
    """模拟集群模式 Instance 对象"""
    ins = Mock()
    ins.instance_name = "redis_cluster_ins"
    ins.host = "127.0.0.1"
    ins.port = 7001
    ins.db_name = "0"
    ins.db_type = "redis"
    ins.mode = "cluster"
    ins.tunnel = None
    ins.is_ssl = False
    ins.get_username_password.return_value = ("ins_user", "some_str")
    return ins


@pytest.fixture
def redis_engine(mock_instance):
    """创建 RedisEngine 实例（单机模式）"""
    return RedisEngine(instance=mock_instance)


@pytest.fixture
def redis_cluster_engine(mock_cluster_instance):
    """创建 RedisEngine 实例（集群模式）"""
    return RedisEngine(instance=mock_cluster_instance)


# ====================== 基本属性 ======================


def test_engine_base_info(redis_engine):
    """测试引擎基本属性"""
    assert redis_engine.name == "Redis"
    assert redis_engine.info == "Redis engine"


# ====================== get_connection ======================


@patch("sql.engines.redis.redis.Redis")
def test_get_connection_standalone(mock_redis, redis_engine):
    """测试单机模式获取连接"""
    redis_engine.get_connection()
    mock_redis.assert_called_once()
    kwargs = mock_redis.call_args.kwargs
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 6379
    assert kwargs["db"] == "0"
    assert kwargs["username"] == "ins_user"
    assert kwargs["password"] == "some_str"
    assert kwargs["decode_responses"] is True
    assert kwargs["ssl"] is False


@patch("sql.engines.redis.redis.Redis")
def test_get_connection_standalone_with_db_name(mock_redis, redis_engine):
    """测试单机模式指定 db_name 获取连接"""
    redis_engine.get_connection(db_name="3")
    kwargs = mock_redis.call_args.kwargs
    assert kwargs["db"] == "3"


@patch("sql.engines.redis.rediscluster.RedisCluster")
def test_get_connection_cluster(mock_redis_cluster, redis_cluster_engine):
    """测试集群模式获取连接"""
    redis_cluster_engine.get_connection()
    mock_redis_cluster.assert_called_once()
    kwargs = mock_redis_cluster.call_args.kwargs
    assert kwargs["startup_nodes"] == [{"host": "127.0.0.1", "port": 7001}]
    assert kwargs["username"] == "ins_user"
    assert kwargs["password"] == "some_str"
    assert kwargs["decode_responses"] is True
    assert kwargs["ssl"] is False


@patch("sql.engines.redis.rediscluster.RedisCluster")
def test_get_connection_cluster_ignores_db_name(
    mock_redis_cluster, redis_cluster_engine
):
    """测试集群模式忽略 db_name 参数"""
    redis_cluster_engine.get_connection(db_name="5")
    kwargs = mock_redis_cluster.call_args.kwargs
    # 集群模式不传 db 参数
    assert "db" not in kwargs


@patch("sql.engines.redis.redis.Redis")
def test_get_connection_empty_password(mock_redis, mock_instance):
    """测试密码为空时传 None"""
    mock_instance.get_username_password.return_value = ("user", "")
    engine = RedisEngine(instance=mock_instance)
    engine.get_connection()
    kwargs = mock_redis.call_args.kwargs
    assert kwargs["password"] is None


@patch("sql.engines.redis.redis.Redis")
def test_get_connection_ssl(mock_redis, mock_instance):
    """测试 SSL 连接"""
    mock_instance.is_ssl = True
    engine = RedisEngine(instance=mock_instance)
    engine.get_connection()
    kwargs = mock_redis.call_args.kwargs
    assert kwargs["ssl"] is True


# ====================== get_cluster_master_nodes ======================


def test_get_cluster_master_nodes_standalone(redis_engine):
    """测试单机模式获取主节点，返回自身 host:port"""
    nodes = redis_engine.get_cluster_master_nodes()
    assert nodes == ["127.0.0.1:6379"]


@patch.object(RedisEngine, "get_connection")
def test_get_cluster_master_nodes_cluster(mock_get_conn, redis_cluster_engine):
    """测试集群模式获取主节点列表"""
    cluster_nodes_output = (
        "nodeid1 127.0.0.1:7001@17001 myself,master - 0 1600000000 1 connected 0-5460\n"
        "nodeid2 127.0.0.1:7002@17002 master - 0 1600000000 2 connected 5461-10922\n"
        "nodeid3 127.0.0.1:7003@17003 slave nodeid2 0 1600000000 3 connected\n"
    )
    mock_conn = Mock()
    mock_conn.execute_command.return_value = cluster_nodes_output
    mock_get_conn.return_value = mock_conn

    nodes = redis_cluster_engine.get_cluster_master_nodes()
    assert len(nodes) == 2
    assert "127.0.0.1:7001" in nodes
    assert "127.0.0.1:7002" in nodes


@patch.object(RedisEngine, "get_connection")
def test_get_cluster_master_nodes_cluster_with_fail(
    mock_get_conn, redis_cluster_engine
):
    """测试集群模式中包含 fail 标记的主节点应被排除"""
    cluster_nodes_output = (
        "nodeid1 127.0.0.1:7001@17001 myself,master,fail - 0 1600000000 1 connected 0-5460\n"
        "nodeid2 127.0.0.1:7002@17002 master - 0 1600000000 2 connected 5461-10922\n"
    )
    mock_conn = Mock()
    mock_conn.execute_command.return_value = cluster_nodes_output
    mock_get_conn.return_value = mock_conn

    nodes = redis_cluster_engine.get_cluster_master_nodes()
    assert len(nodes) == 1
    assert "127.0.0.1:7002" in nodes


@patch.object(RedisEngine, "get_connection")
def test_get_cluster_master_nodes_cluster_no_masters(
    mock_get_conn, redis_cluster_engine
):
    """测试集群模式无主节点时回退到自身 host:port"""
    cluster_nodes_output = (
        "nodeid3 127.0.0.1:7003@17003 slave nodeid2 0 1600000000 3 connected\n"
    )
    mock_conn = Mock()
    mock_conn.execute_command.return_value = cluster_nodes_output
    mock_get_conn.return_value = mock_conn

    nodes = redis_cluster_engine.get_cluster_master_nodes()
    # 无 master 时回退到自身
    assert nodes == ["127.0.0.1:7001"]


@patch.object(RedisEngine, "get_connection")
def test_get_cluster_master_nodes_cluster_exception(
    mock_get_conn, redis_cluster_engine
):
    """测试集群模式获取节点信息异常时回退到自身"""
    mock_conn = Mock()
    mock_conn.execute_command.side_effect = Exception("connection error")
    mock_get_conn.return_value = mock_conn

    nodes = redis_cluster_engine.get_cluster_master_nodes()
    assert nodes == ["127.0.0.1:7001"]


@patch.object(RedisEngine, "get_connection")
def test_get_cluster_master_nodes_ipv6(mock_get_conn, redis_cluster_engine):
    """测试集群模式中 IPv6 地址的解析"""
    cluster_nodes_output = "nodeid1 [2001:db8::10]:6379@16379 myself,master - 0 1600000000 1 connected 0-5460\n"
    mock_conn = Mock()
    mock_conn.execute_command.return_value = cluster_nodes_output
    mock_get_conn.return_value = mock_conn

    nodes = redis_cluster_engine.get_cluster_master_nodes()
    assert len(nodes) == 1
    assert nodes[0] == "2001:db8::10:6379"


# ====================== test_connection ======================


@patch.object(RedisEngine, "get_connection")
def test_test_connection(mock_get_conn, redis_engine):
    """测试连接测试，使用 PING 命令"""
    mock_conn = Mock()
    mock_conn.ping.return_value = True
    mock_get_conn.return_value = mock_conn

    result = redis_engine.test_connection()
    assert isinstance(result, ResultSet)
    assert result.full_sql == "PING"
    assert result.affected_rows == 1


# ====================== get_all_databases ======================


@patch.object(RedisEngine, "get_connection")
def test_get_all_databases_normal(mock_get_conn, redis_engine):
    """测试单节点模式获取数据库列表，使用 INFO Keyspace"""
    mock_conn = Mock()
    mock_conn.info.return_value = {
        "db0": {"keys": 100, "expires": 5, "avg_ttl": 0},
        "db3": {"keys": 200, "expires": 0, "avg_ttl": 0},
    }
    mock_get_conn.return_value = mock_conn

    result = redis_engine.get_all_databases()
    assert isinstance(result, ResultSet)
    assert result.full_sql == "INFO Keyspace"
    # 单节点应返回 db0~db15，补充缺失的库
    assert len(result.rows) == 16
    # 验证有 keys 的库显示格式
    assert result.rows[0] == {"value": "0", "text": "db0[100]"}
    assert result.rows[3] == {"value": "3", "text": "db3[200]"}
    # 验证无 keys 的库显示格式
    assert result.rows[1] == {"value": "1", "text": "db1"}
    assert result.rows[2] == {"value": "2", "text": "db2"}
    # 验证 value 值
    assert result.rows[15]["value"] == "15"


@patch.object(RedisEngine, "get_connection")
def test_get_all_databases_fallback_via_info(mock_get_conn, redis_engine):
    """测试 INFO Keyspace 返回部分数据库时补充 0~15 号库"""
    mock_conn = Mock()
    mock_conn.info.return_value = {
        "db0": {"keys": 10, "expires": 0},
        "db3": {"keys": 5, "expires": 0},
        "db5": {"keys": 0, "expires": 0},
    }
    mock_get_conn.return_value = mock_conn

    result = redis_engine.get_all_databases()
    assert isinstance(result, ResultSet)
    # 单节点至少返回 0~15，共 16 个库
    assert len(result.rows) == 16
    # db0 有 keys
    assert result.rows[0] == {"value": "0", "text": "db0[10]"}
    # db1 无 keys
    assert result.rows[1] == {"value": "1", "text": "db1"}
    # db5 的 keys 为 0，不显示 keys 数量
    assert result.rows[5] == {"value": "5", "text": "db5"}


@patch.object(RedisEngine, "get_connection")
def test_get_all_databases_fallback_with_high_db(mock_get_conn, redis_engine):
    """测试 INFO Keyspace 返回高编号数据库时扩展库列表"""
    mock_conn = Mock()
    mock_conn.info.return_value = {
        "db5": {"keys": 30, "expires": 0},
        "db20": {"keys": 50, "expires": 0},
    }
    mock_get_conn.return_value = mock_conn

    result = redis_engine.get_all_databases()
    # max([5,20] + [15]) + 1 = 21, 所以 0~20
    assert len(result.rows) == 21
    assert result.rows[0] == {"value": "0", "text": "db0"}
    assert result.rows[5] == {"value": "5", "text": "db5[30]"}
    assert result.rows[20] == {"value": "20", "text": "db20[50]"}


@patch.object(RedisEngine, "get_cluster_master_nodes")
@patch("sql.engines.redis.redis.Redis")
def test_get_all_databases_cluster(
    mock_redis_cls, mock_get_masters, redis_cluster_engine
):
    """测试集群模式获取数据库列表，只有 db0，汇总各主节点 keys"""
    mock_get_masters.return_value = ["127.0.0.1:7001", "127.0.0.1:7002"]

    # 模拟两个主节点的连接和 INFO Keyspace 返回
    mock_conn1 = Mock()
    mock_conn1.info.return_value = {"db0": {"keys": 100, "expires": 0}}
    mock_conn2 = Mock()
    mock_conn2.info.return_value = {"db0": {"keys": 200, "expires": 0}}
    mock_redis_cls.side_effect = [mock_conn1, mock_conn2]

    result = redis_cluster_engine.get_all_databases()
    assert isinstance(result, ResultSet)
    # 集群模式只返回 db0
    assert len(result.rows) == 1
    assert result.rows[0] == {"value": "0", "text": "db0[300]"}


@patch.object(RedisEngine, "get_cluster_master_nodes")
@patch("sql.engines.redis.redis.Redis")
def test_get_all_databases_cluster_no_keys(
    mock_redis_cls, mock_get_masters, redis_cluster_engine
):
    """测试集群模式 db0 无 keys 时显示 db0"""
    mock_get_masters.return_value = ["127.0.0.1:7001"]

    mock_conn1 = Mock()
    mock_conn1.info.return_value = {}
    mock_redis_cls.side_effect = [mock_conn1]

    result = redis_cluster_engine.get_all_databases()
    assert result.rows[0] == {"value": "0", "text": "db0"}


@patch.object(RedisEngine, "get_connection")
def test_get_all_databases_exception_fallback(mock_get_conn, redis_engine):
    """测试 INFO Keyspace 执行报错时回退到默认 0~15 号库"""
    mock_conn = Mock()
    mock_conn.info.side_effect = Exception("connection error")
    mock_get_conn.return_value = mock_conn

    result = redis_engine.get_all_databases()
    assert isinstance(result, ResultSet)
    # 回退应返回默认的 0~15 号库
    assert len(result.rows) == 16
    assert result.rows[0] == {"value": "0", "text": "db0"}
    assert result.rows[15] == {"value": "15", "text": "db15"}


# ====================== get_all_tables ======================


@patch.object(RedisEngine, "get_connection")
def test_get_all_tables_normal(mock_get_conn, redis_engine):
    """测试获取 key 列表"""
    mock_conn = Mock()
    mock_conn.scan_iter.return_value = iter(["key1", "key2", "key3"])
    mock_get_conn.return_value = mock_conn

    result = redis_engine.get_all_tables(db_name="0")
    assert isinstance(result, ResultSet)
    assert result.rows == ["key1", "key2", "key3"]


@patch.object(RedisEngine, "get_connection")
def test_get_all_tables_max_results(mock_get_conn, redis_engine):
    """测试获取 key 列表不超过最大数量 100"""
    mock_conn = Mock()
    # 生成超过100个 key
    keys = [f"key_{i}" for i in range(150)]
    mock_conn.scan_iter.return_value = iter(keys)
    mock_get_conn.return_value = mock_conn

    result = redis_engine.get_all_tables(db_name="0")
    assert len(result.rows) == 100


@patch.object(RedisEngine, "get_connection")
def test_get_all_tables_error(mock_get_conn, redis_engine):
    """测试获取 key 列表时出错"""
    mock_conn = Mock()
    mock_conn.scan_iter.side_effect = Exception("scan error")
    mock_get_conn.return_value = mock_conn

    result = redis_engine.get_all_tables(db_name="0")
    assert isinstance(result, ResultSet)
    assert result.rows == []
    assert "scan error" in result.message


# ====================== query_check ======================


def test_query_check_safe_cmd_get(redis_engine):
    """测试安全命令 get 通过检查"""
    result = redis_engine.query_check(sql="get mykey")
    assert result["bad_query"] is False
    assert result["msg"] == ""


def test_query_check_safe_cmd_ttl(redis_engine):
    """测试安全命令 ttl 通过检查"""
    result = redis_engine.query_check(sql="ttl mykey")
    assert result["bad_query"] is False


def test_query_check_safe_cmd_hgetall(redis_engine):
    """测试安全命令 hgetall 通过检查"""
    result = redis_engine.query_check(sql="hgetall myhash")
    assert result["bad_query"] is False


def test_query_check_safe_cmd_info(redis_engine):
    """测试安全命令 info 通过检查"""
    result = redis_engine.query_check(sql="info")
    assert result["bad_query"] is False


def test_query_check_safe_cmd_scan(redis_engine):
    """测试安全命令 scan 通过检查"""
    result = redis_engine.query_check(sql="scan 0 count 10")
    assert result["bad_query"] is False


def test_query_check_unsafe_cmd(redis_engine):
    """测试不安全命令被拒绝"""
    result = redis_engine.query_check(sql="set mykey value")
    assert result["bad_query"] is True
    assert result["msg"] == "禁止执行该命令！"


def test_query_check_unsafe_cmd_del(redis_engine):
    """测试 del 命令被拒绝"""
    result = redis_engine.query_check(sql="del mykey")
    assert result["bad_query"] is True


def test_query_check_unsafe_cmd_flushdb(redis_engine):
    """测试 flushdb 命令被拒绝"""
    result = redis_engine.query_check(sql="flushdb")
    assert result["bad_query"] is True


def test_query_check_case_insensitive(redis_engine):
    """测试命令检查大小写不敏感"""
    result = redis_engine.query_check(sql="GET mykey")
    assert result["bad_query"] is False

    result2 = redis_engine.query_check(sql="INFO memory")
    assert result2["bad_query"] is False


def test_query_check_filtered_sql_preserved(redis_engine):
    """测试 query_check 保留原始 sql"""
    sql = "get mykey"
    result = redis_engine.query_check(sql=sql)
    assert result["filtered_sql"] == sql


def test_query_check_has_star_default(redis_engine):
    """测试 query_check has_star 默认为 False"""
    result = redis_engine.query_check(sql="get mykey")
    assert result["has_star"] is False


# ====================== processlist ======================


@patch.object(RedisEngine, "get_connection")
def test_processlist(mock_get_conn, redis_engine):
    """测试获取连接列表"""
    mock_conn = Mock()
    clients = [
        {"id": 1, "addr": "127.0.0.1:12345", "idle": 100},
        {"id": 2, "addr": "127.0.0.1:12346", "idle": 50},
    ]
    mock_conn.client_list.return_value = clients
    mock_get_conn.return_value = mock_conn

    result = redis_engine.processlist(command_type="All")
    assert isinstance(result, ResultSet)
    assert result.full_sql == "client list"
    # 结果按 idle 升序排列
    assert result.rows[0]["idle"] == 50
    assert result.rows[1]["idle"] == 100


@patch.object(RedisEngine, "get_connection")
def test_processlist_sorted_by_idle(mock_get_conn, redis_engine):
    """测试连接列表按 idle 时间排序"""
    mock_conn = Mock()
    clients = [
        {"id": 1, "addr": "127.0.0.1:12345", "idle": 300},
        {"id": 2, "addr": "127.0.0.1:12346", "idle": 10},
        {"id": 3, "addr": "127.0.0.1:12347", "idle": 100},
    ]
    mock_conn.client_list.return_value = clients
    mock_get_conn.return_value = mock_conn

    result = redis_engine.processlist(command_type="All")
    idle_values = [c["idle"] for c in result.rows]
    assert idle_values == [10, 100, 300]


# ====================== query ======================


@patch.object(RedisEngine, "get_connection")
def test_query_list_result(mock_get_conn, redis_engine):
    """测试查询返回列表结果"""
    mock_conn = Mock()
    mock_conn.execute_command.return_value = ["val1", "val2", "val3"]
    mock_get_conn.return_value = mock_conn

    result = redis_engine.query(db_name="0", sql="mget key1 key2 key3")
    assert isinstance(result, ResultSet)
    assert result.column_list == ["Result"]
    assert result.rows == (["val1"], ["val2"], ["val3"])
    assert result.affected_rows == 3


@patch.object(RedisEngine, "get_connection")
def test_query_dict_result(mock_get_conn, redis_engine):
    """测试查询返回字典结果"""
    mock_conn = Mock()
    mock_conn.execute_command.return_value = {"key1": "val1", "key2": "val2"}
    mock_get_conn.return_value = mock_conn

    result = redis_engine.query(db_name="0", sql="hgetall myhash")
    assert isinstance(result, ResultSet)
    assert result.column_list == ["field", "value"]
    assert result.affected_rows == 2


@patch.object(RedisEngine, "get_connection")
def test_query_dict_with_nested_dict(mock_get_conn, redis_engine):
    """测试查询返回字典中包含嵌套 dict 时转为 JSON"""
    mock_conn = Mock()
    mock_conn.execute_command.return_value = {"key1": {"nested": "val"}}
    mock_get_conn.return_value = mock_conn

    result = redis_engine.query(db_name="0", sql="hgetall myhash")
    assert result.column_list == ["field", "value"]
    # 嵌套 dict 应被转为 json 字符串
    for row in result.rows:
        if row[0] == "key1":
            assert row[1] == json.dumps({"nested": "val"})


@patch.object(RedisEngine, "get_connection")
def test_query_dict_with_nested_list(mock_get_conn, redis_engine):
    """测试查询返回字典中包含 list 时转为 JSON"""
    mock_conn = Mock()
    mock_conn.execute_command.return_value = {"key1": [1, 2, 3]}
    mock_get_conn.return_value = mock_conn

    result = redis_engine.query(db_name="0", sql="hgetall myhash")
    for row in result.rows:
        if row[0] == "key1":
            assert row[1] == json.dumps([1, 2, 3])


@patch.object(RedisEngine, "get_connection")
def test_query_scalar_result(mock_get_conn, redis_engine):
    """测试查询返回标量结果（字符串/数字）"""
    mock_conn = Mock()
    mock_conn.execute_command.return_value = "hello"
    mock_get_conn.return_value = mock_conn

    result = redis_engine.query(db_name="0", sql="get mykey")
    assert isinstance(result, ResultSet)
    assert result.column_list == ["Result"]
    assert result.rows == (["hello"],)
    assert result.affected_rows == 1


@patch.object(RedisEngine, "get_connection")
def test_query_scalar_zero(mock_get_conn, redis_engine):
    """测试查询返回 0 时的 affected_rows
    注意：代码中 `1 if rows else 0` 对整数 0 视为 falsy，
    所以 affected_rows 为 0，这是已知行为"""
    mock_conn = Mock()
    mock_conn.execute_command.return_value = 0
    mock_get_conn.return_value = mock_conn

    result = redis_engine.query(db_name="0", sql="exists nonexist")
    assert result.rows == ([0],)
    # 0 is falsy in Python, so `1 if rows else 0` evaluates to 0
    assert result.affected_rows == 0


@patch.object(RedisEngine, "get_connection")
def test_query_scalar_none(mock_get_conn, redis_engine):
    """测试查询返回 None 时的 affected_rows 为 0"""
    mock_conn = Mock()
    mock_conn.execute_command.return_value = None
    mock_get_conn.return_value = mock_conn

    result = redis_engine.query(db_name="0", sql="get nonexist")
    assert result.rows == ([None],)
    assert result.affected_rows == 0


@patch.object(RedisEngine, "get_connection")
def test_query_scan_result(mock_get_conn, redis_engine):
    """测试 scan 命令返回特殊格式结果"""
    mock_conn = Mock()
    # scan 返回 (cursor, [keys])
    mock_conn.execute_command.return_value = ("123", ["key1", "key2"])
    mock_get_conn.return_value = mock_conn

    result = redis_engine.query(db_name="0", sql="scan 0 count 10")
    assert isinstance(result, ResultSet)
    assert result.column_list == ["Result"]
    # scan 的结果格式: cursor 在第一个, 然后 keys
    assert result.rows[0] == ["123"]
    assert result.rows[1] == ["key1"]
    assert result.rows[2] == ["key2"]
    assert result.affected_rows == 2


@patch.object(RedisEngine, "get_connection")
def test_query_with_limit(mock_get_conn, redis_engine):
    """测试查询结果 limit 截断"""
    mock_conn = Mock()
    mock_conn.execute_command.return_value = ["v1", "v2", "v3", "v4", "v5"]
    mock_get_conn.return_value = mock_conn

    result = redis_engine.query(db_name="0", sql="mget k1 k2 k3 k4 k5", limit_num=3)
    assert len(result.rows) == 3


@patch.object(RedisEngine, "get_connection")
def test_query_error(mock_get_conn, redis_engine):
    """测试查询执行出错"""
    mock_conn = Mock()
    mock_conn.execute_command.side_effect = Exception("WRONGTYPE Operation")
    mock_get_conn.return_value = mock_conn

    result = redis_engine.query(db_name="0", sql="get mykey")
    assert result.error is not None
    assert "WRONGTYPE Operation" in result.error


@patch.object(RedisEngine, "get_connection")
def test_query_tuple_result(mock_get_conn, redis_engine):
    """测试查询返回 tuple 结果"""
    mock_conn = Mock()
    mock_conn.execute_command.return_value = ("val1", "val2")
    mock_get_conn.return_value = mock_conn

    result = redis_engine.query(db_name="0", sql="mget key1 key2")
    assert result.column_list == ["Result"]
    assert result.rows == (["val1"], ["val2"])
    assert result.affected_rows == 2


# ====================== filter_sql ======================


def test_filter_sql(redis_engine):
    """测试 filter_sql 仅做 strip"""
    assert redis_engine.filter_sql(sql="  get mykey  ") == "get mykey"


def test_filter_sql_with_limit_num(redis_engine):
    """测试 filter_sql 忽略 limit_num（Redis 不支持 limit 语法）"""
    assert redis_engine.filter_sql(sql="get mykey", limit_num=100) == "get mykey"


# ====================== query_masking ======================


def test_query_masking(redis_engine):
    """测试 query_masking 不做脱敏，原样返回"""
    rs = ResultSet(full_sql="get mykey")
    rs.rows = [["value1"]]
    result = redis_engine.query_masking(db_name="0", sql="get mykey", resultset=rs)
    assert result is rs


# ====================== execute_check ======================


def test_execute_check_single_cmd(redis_engine):
    """测试审核单条命令"""
    result = redis_engine.execute_check(db_name="0", sql="set mykey value")
    assert isinstance(result, ReviewSet)
    assert len(result.rows) == 1
    assert result.rows[0].sql == "set mykey value"
    assert result.rows[0].errlevel == 0
    assert result.rows[0].stagestatus == "Audit completed"
    assert result.rows[0].errormessage == "暂不支持显示影响行数"


def test_execute_check_multiple_cmds(redis_engine):
    """测试审核多条命令（按换行分割）"""
    sql = "set key1 val1\nset key2 val2\nset key3 val3"
    result = redis_engine.execute_check(db_name="0", sql=sql)
    assert len(result.rows) == 3
    for i, row in enumerate(result.rows):
        assert row.id == i + 1
        assert row.errlevel == 0


def test_execute_check_empty_lines(redis_engine):
    """测试审核时跳过空行"""
    sql = "set key1 val1\n\nset key2 val2\n  \n"
    result = redis_engine.execute_check(db_name="0", sql=sql)
    assert len(result.rows) == 2


def test_execute_check_line_numbers(redis_engine):
    """测试审核结果的行号递增"""
    sql = "set key1 val1\nset key2 val2"
    result = redis_engine.execute_check(db_name="0", sql=sql)
    assert result.rows[0].id == 1
    assert result.rows[1].id == 2


# ====================== execute_workflow ======================


def _build_workflow_mock(sql_content, db_name="0"):
    """辅助：构造 workflow Mock 对象"""
    wf = Mock()
    wf.db_name = db_name
    wf.sqlworkflowcontent = Mock()
    wf.sqlworkflowcontent.sql_content = sql_content
    return wf


@patch.object(RedisEngine, "get_connection")
def test_execute_workflow_all_success(mock_get_conn, redis_engine):
    """测试执行工作流全部成功"""
    mock_conn = Mock()
    mock_get_conn.return_value = mock_conn

    wf = _build_workflow_mock("set key1 val1\nset key2 val2")
    result = redis_engine.execute_workflow(wf)
    assert isinstance(result, ReviewSet)
    assert len(result.rows) == 2
    assert result.rows[0].errlevel == 0
    assert result.rows[0].stagestatus == "Execute Successfully"
    assert result.rows[1].errlevel == 0
    assert result.rows[1].stagestatus == "Execute Successfully"
    # 每条命令应调用一次 execute_command
    assert mock_conn.execute_command.call_count == 2


@patch.object(RedisEngine, "get_connection")
def test_execute_workflow_fail_mid(mock_get_conn, redis_engine):
    """测试执行工作流中途失败，后续语句标记为未执行"""
    mock_conn = Mock()
    mock_conn.execute_command.side_effect = [
        None,  # 第一条成功
        Exception("OOM"),  # 第二条失败
    ]
    mock_get_conn.return_value = mock_conn

    wf = _build_workflow_mock("set key1 val1\nset key2 val2\nset key3 val3")
    result = redis_engine.execute_workflow(wf)
    assert isinstance(result, ReviewSet)
    # 第一条成功
    assert result.rows[0].errlevel == 0
    assert result.rows[0].stagestatus == "Execute Successfully"
    # 第二条失败
    assert result.rows[1].errlevel == 2
    assert result.rows[1].stagestatus == "Execute Failed"
    assert "OOM" in result.rows[1].errormessage
    # 第三条未执行
    assert result.rows[2].errlevel == 0
    assert result.rows[2].stagestatus == "Audit completed"
    assert "未执行" in result.rows[2].errormessage
    # ReviewSet 应有 error
    assert result.error is not None


@patch.object(RedisEngine, "get_connection")
def test_execute_workflow_single_cmd_success(mock_get_conn, redis_engine):
    """测试执行工作流单条命令成功"""
    mock_conn = Mock()
    mock_get_conn.return_value = mock_conn

    wf = _build_workflow_mock("set key1 val1")
    result = redis_engine.execute_workflow(wf)
    assert len(result.rows) == 1
    assert result.rows[0].errlevel == 0
    assert result.rows[0].stagestatus == "Execute Successfully"
    assert result.rows[0].sql == "set key1 val1"


@patch.object(RedisEngine, "get_connection")
def test_execute_workflow_first_cmd_fail(mock_get_conn, redis_engine):
    """测试执行工作流第一条命令就失败"""
    mock_conn = Mock()
    mock_conn.execute_command.side_effect = Exception("CONN REFUSED")
    mock_get_conn.return_value = mock_conn

    wf = _build_workflow_mock("set key1 val1\nset key2 val2")
    result = redis_engine.execute_workflow(wf)
    # 第一条失败
    assert result.rows[0].errlevel == 2
    assert result.rows[0].stagestatus == "Execute Failed"
    # 第二条未执行
    assert result.rows[1].errlevel == 0
    assert result.rows[1].stagestatus == "Audit completed"


@patch.object(RedisEngine, "get_connection")
def test_execute_workflow_error_in_result(mock_get_conn, redis_engine):
    """测试执行工作流失败时 error 被设置"""
    mock_conn = Mock()
    mock_conn.execute_command.side_effect = Exception("BOOM")
    mock_get_conn.return_value = mock_conn

    wf = _build_workflow_mock("set key1 val1")
    result = redis_engine.execute_workflow(wf)
    assert result.error is not None
    assert "BOOM" in result.error


@patch.object(RedisEngine, "get_connection")
def test_execute_workflow_execute_time(mock_get_conn, redis_engine):
    """测试执行工作流成功时记录执行时间"""
    mock_conn = Mock()
    mock_get_conn.return_value = mock_conn

    wf = _build_workflow_mock("set key1 val1")
    result = redis_engine.execute_workflow(wf)
    # 执行时间应 >= 0
    assert result.rows[0].execute_time >= 0


@patch.object(RedisEngine, "get_connection")
def test_execute_workflow_empty_lines(mock_get_conn, redis_engine):
    """测试执行工作流时空行被跳过"""
    mock_conn = Mock()
    mock_get_conn.return_value = mock_conn

    wf = _build_workflow_mock("set key1 val1\n\nset key2 val2\n  \n")
    result = redis_engine.execute_workflow(wf)
    assert len(result.rows) == 2


@patch.object(RedisEngine, "get_connection")
def test_execute_workflow_shlex_split(mock_get_conn, redis_engine):
    """测试执行工作流时使用 shlex 分割命令参数"""
    mock_conn = Mock()
    mock_get_conn.return_value = mock_conn

    wf = _build_workflow_mock("set 'my key' 'my value'")
    redis_engine.execute_workflow(wf)
    # 验证 execute_command 被调用时参数被正确分割
    call_args = mock_conn.execute_command.call_args[0]
    assert "set" in call_args
    assert "my key" in call_args
    assert "my value" in call_args


# ====================== 综合场景 ======================


def test_query_check_all_safe_commands(redis_engine):
    """测试所有安全命令都能通过检查"""
    safe_commands = [
        "scan 0",
        "exists key",
        "ttl key",
        "pttl key",
        "type key",
        "get key",
        "mget key1 key2",
        "strlen key",
        "hgetall hash",
        "hlen hash",
        "hexists hash field",
        "hget hash field",
        "hmget hash f1 f2",
        "hkeys hash",
        "hvals hash",
        "smembers set",
        "scard set",
        "sdiff s1 s2",
        "sunion s1 s2",
        "sismember set member",
        "llen list",
        "lrange list 0 -1",
        "lindex list 0",
        "zrange zset 0 -1",
        "zrangebyscore zset 0 100",
        "zscore zset member",
        "zcard zset",
        "zcount zset 0 100",
        "zrank zset member",
        "info",
    ]
    for cmd in safe_commands:
        result = redis_engine.query_check(sql=cmd)
        assert result["bad_query"] is False, f"Safe command rejected: {cmd}"


def test_query_check_all_unsafe_commands(redis_engine):
    """测试常见的危险命令被拒绝"""
    unsafe_commands = [
        "set key val",
        "del key",
        "flushdb",
        "flushall",
        "rename key1 key2",
        "expire key 60",
        "persist key",
        "incr counter",
        "decr counter",
        "lpush list val",
        "rpush list val",
        "sadd set member",
        "zadd zset 1 member",
        "hset hash field val",
        "config set maxmemory 100mb",
        "shutdown",
        "debug",
        "slaveof no one",
        "acl setuser",
    ]
    for cmd in unsafe_commands:
        result = redis_engine.query_check(sql=cmd)
        assert result["bad_query"] is True, f"Unsafe command allowed: {cmd}"
