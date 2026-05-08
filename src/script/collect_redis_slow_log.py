import redis
import hashlib
from datetime import datetime
import pymysql
import re

# 配置
# redis节点信息，由于redis cluster架构每个节点都有单独的slowlog，所以需要写全redis cluster所有节点
REDIS_LIST = [
    {"host": "127.0.0.1", "port": 6379, "username": "", "password": ""},
    {"host": "127.0.0.1", "port": 7001, "username": "", "password": ""},
    {"host": "127.0.0.1", "port": 7002, "username": "", "password": ""},
    {"host": "127.0.0.1", "port": 7003, "username": "", "password": ""},
    {
        "host": "127.0.0.1",
        "port": 8001,
        "username": "",
        "password": "123456",
    },
    {
        "host": "127.0.0.1",
        "port": 8002,
        "username": "",
        "password": "123456",
    },
    {
        "host": "127.0.0.1",
        "port": 8003,
        "username": "",
        "password": "123456",
    },
    {"host": "127.0.0.1", "port": 9001, "username": "", "password": ""},
    {"host": "127.0.0.1", "port": 9002, "username": "", "password": ""},
    {"host": "127.0.0.1", "port": 9003, "username": "", "password": ""},
]
MYSQL_DSN = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "123456",
    "db": "archery",
}


def normalize_command(cmd_str):
    """参数化命令：将第一个词转为小写，第二个词中的连续数字替换为*，忽略其余部分"""
    if not cmd_str or not cmd_str.strip():
        return ""
    # 按空格分割，多个空格自动合并
    parts = cmd_str.split()
    if len(parts) == 0:
        return ""
    # 第一个词转为小写
    cmd = parts[0].lower()
    if len(parts) == 1:
        return cmd
    # 处理第二个词：连续数字替换为 *
    arg1 = parts[1]
    arg1_processed = re.sub(r"\d+", "*", arg1)
    return f"{cmd} {arg1_processed}"


def collect_slowlog_for_node(
    redis_host, redis_port, redis_username=None, redis_password=None
):
    """采集单个 Redis 节点的慢日志"""
    node_name = f"{redis_host}:{redis_port}"
    print(f"=== 开始采集 {node_name} ===")

    r = redis.Redis(
        host=redis_host,
        port=redis_port,
        username=redis_username,
        password=redis_password,
    )
    db = pymysql.connect(**MYSQL_DSN)
    cursor = db.cursor()

    # 1. 获取上次处理的最大ID
    cursor.execute(
        "SELECT last_processed_id FROM redis_slowlog_cursor WHERE hostname = %s",
        (node_name,),
    )
    row = cursor.fetchone()
    last_id = row[0] if row else 0

    # 2. 获取最近5000条慢日志
    slowlogs = r.slowlog_get(5000)
    if not slowlogs:
        print(f"  {node_name} 无慢日志，跳过")
        cursor.close()
        db.close()
        return

    new_logs = []
    max_new_id = last_id
    for entry in slowlogs:
        entry_id = entry["id"]
        if entry_id > last_id:
            new_logs.append(entry)
            if entry_id > max_new_id:
                max_new_id = entry_id

    if not new_logs:
        print(f"  {node_name} 无新增慢日志，跳过")
        cursor.close()
        db.close()
        return

    # 3. 处理每条新日志
    groups = {}
    for log in new_logs:
        fingerprint = normalize_command(log["command"].decode("utf-8"))
        checksum = hashlib.md5(fingerprint.encode()).hexdigest()
        timestamp = datetime.fromtimestamp(log["start_time"])
        duration = log["duration"]  # 微秒

        # 更新指纹表
        sql_review = """
            INSERT INTO redis_slow_query_review (checksum, fingerprint, sample, first_seen, last_seen)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                last_seen = IF(VALUES(last_seen) > last_seen, VALUES(last_seen), last_seen)
        """
        sample = log["command"].decode("utf-8")
        cursor.execute(
            sql_review, (checksum, fingerprint, sample, timestamp, timestamp)
        )
        db.commit()

        # 暂存用于聚合
        key = checksum
        if key not in groups:
            groups[key] = {"durations": [], "timestamps": [], "sample": sample}
        groups[key]["durations"].append(duration)
        groups[key]["timestamps"].append(timestamp)

    # 4. 聚合写入历史表
    for checksum, data in groups.items():
        durations = data["durations"]
        timestamps = data["timestamps"]
        history_sample = data["sample"]
        cnt = len(durations)
        duration_sum = sum(durations)
        duration_min = min(durations)
        duration_max = max(durations)
        durations_sorted = sorted(durations)
        duration_median = durations_sorted[cnt // 2]
        p95_idx = int(cnt * 0.95) - 1
        duration_pct_95 = (
            durations_sorted[p95_idx] if p95_idx >= 0 else durations_sorted[-1]
        )
        # 计算标准差
        mean = duration_sum / cnt
        variance = sum((x - mean) ** 2 for x in durations) / cnt
        duration_stddev = variance**0.5

        ts_min = min(timestamps)
        ts_max = max(timestamps)

        sql_history = """
            INSERT INTO redis_slow_query_review_history
            (checksum, sample, hostname, ts_min, ts_max, cnt, duration_sum, duration_min, duration_max,
             duration_pct_95, duration_stddev, duration_median)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                cnt = VALUES(cnt), duration_sum = VALUES(duration_sum), duration_min = VALUES(duration_min),
                duration_max = VALUES(duration_max), duration_pct_95 = VALUES(duration_pct_95),
                duration_stddev = VALUES(duration_stddev), duration_median = VALUES(duration_median)
        """
        cursor.execute(
            sql_history,
            (
                checksum,
                history_sample,
                node_name,
                ts_min,
                ts_max,
                cnt,
                duration_sum,
                duration_min,
                duration_max,
                duration_pct_95,
                duration_stddev,
                duration_median,
            ),
        )
        db.commit()

    # 5. 更新游标
    cursor.execute(
        """
        INSERT INTO redis_slowlog_cursor (hostname, last_processed_id, updated_at)
        VALUES (%s, %s, NOW())
        ON DUPLICATE KEY UPDATE last_processed_id = VALUES(last_processed_id), updated_at = NOW()
    """,
        (node_name, max_new_id),
    )
    db.commit()

    cursor.close()
    db.close()
    print(f"=== 采集完成 {node_name}，新增 {len(new_logs)} 条慢日志 ===")


def collect_slowlog():
    """分批采集所有 Redis 节点的慢日志"""
    for node in REDIS_LIST:
        try:
            collect_slowlog_for_node(
                redis_host=node["host"],
                redis_port=node["port"],
                redis_username=node.get("username"),
                redis_password=node.get("password"),
            )
        except Exception as e:
            print(f"采集 {node['host']}:{node['port']} 失败: {e}")


if __name__ == "__main__":
    collect_slowlog()
