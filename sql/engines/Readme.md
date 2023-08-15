# Engine 说明

## Cassandra
当前连接时, 使用参数基本为写死参数, 具体可以参照代码.

如果需要覆盖, 可以自行继承

具体方法为:
1. 新增一个文件夹`extras`在根目录, 和`sql`, `sql_api`等文件夹平级 可以docker 打包时加入, 也可以使用卷挂载的方式
2. 新增一个文件, `mycassandra.py`
```python
from sql.engines.cassandra import CassandraEngine

class MyCassandraEngine(CassandraEngine):
    def get_connection(self, db_name=None):
        db_name = db_name or self.db_name
        if self.conn:
            if db_name:
                self.conn.execute(f"use {db_name}")
            return self.conn
        hosts = self.host.split(",")
        # 在这里更改你获取 session 的方式
        auth_provider = PlainTextAuthProvider(
            username=self.user, password=self.password
        )
        cluster = Cluster(hosts, port=self.port, auth_provider=auth_provider,
                          load_balancing_policy=RoundRobinPolicy(), protocol_version=5)
        self.conn = cluster.connect(keyspace=db_name)
        # 下面这一句最好是不要动.
        self.conn.row_factory = tuple_factory
        return self.conn
```
3. 修改settings , 加载你刚写的 engine
```python
AVAILABLE_ENGINES = {
    "mysql": {"path": "sql.engines.mysql:MysqlEngine"},
    # 这里改成你的 engine
    "cassandra": {"path": "extras.mycassandra:MyCassandraEngine"},
    "clickhouse": {"path": "sql.engines.clickhouse:ClickHouseEngine"},
    "goinception": {"path": "sql.engines.goinception:GoInceptionEngine"},
    "mssql": {"path": "sql.engines.mssql:MssqlEngine"},
    "redis": {"path": "sql.engines.redis:RedisEngine"},
    "pqsql": {"path": "sql.engines.pgsql:PgSQLEngine"},
    "oracle": {"path": "sql.engines.oracle:OracleEngine"},
    "mongo": {"path": "sql.engines.mongo:MongoEngine"},
    "phoenix": {"path": "sql.engines.phoenix:PhoenixEngine"},
    "odps": {"path": "sql.engines.odps:ODPSEngine"},
}
```