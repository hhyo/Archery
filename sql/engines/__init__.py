"""engine base库, 包含一个``EngineBase`` class和一个get_engine函数"""
from sql.engines.models import ResultSet
from sql.utils.ssh_tunnel import SSHConnection


class EngineBase:
    """enginebase 只定义了init函数和若干方法的名字, 具体实现用mysql.py pg.py等实现"""

    def __init__(self, instance=None):
        self.conn = None
        self.thread_id = None
        if instance:
            self.instance = instance
            self.instance_name = instance.instance_name
            self.host = instance.host
            self.port = int(instance.port)
            self.user = instance.user
            self.password = instance.password
            self.db_name = instance.db_name
            self.mode = instance.mode

            # 判断如果配置了隧道则连接隧道，只测试了MySQL
            if self.instance.tunnel:
                self.ssh = SSHConnection(
                    self.host,
                    self.port,
                    instance.tunnel.host,
                    instance.tunnel.port,
                    instance.tunnel.user,
                    instance.tunnel.password,
                    instance.tunnel.pkey,
                    instance.tunnel.pkey_password,
                )
                self.host,self.port = self.ssh.get_ssh()

    def __del__(self):
        if hasattr(self, 'ssh'):
            del self.ssh
        if hasattr(self, 'remotessh'):
            del self.remotessh

    def remote_instance_conn(self, instance=None):
        # 判断如果配置了隧道则连接隧道
        if not hasattr(self, 'remotessh') and instance.tunnel:
            self.remotessh = SSHConnection(
                instance.host,
                instance.port,
                instance.tunnel.host,
                instance.tunnel.port,
                instance.tunnel.user,
                instance.tunnel.password,
                instance.tunnel.pkey,
                instance.tunnel.pkey_password,
            )
            self.remote_host, self.remote_port = self.remotessh.get_ssh()
            self.remote_user = instance.user
            self.remote_password = instance.password
        elif not instance.tunnel:
            self.remote_host = instance.host
            self.remote_port = instance.port
            self.remote_user = instance.user
            self.remote_password = instance.password
        return self.remote_host, self.remote_port, self.remote_user, self.remote_password

    def get_connection(self, db_name=None):
        """返回一个conn实例"""

    @property
    def name(self):
        """返回engine名称"""
        return "base"

    @property
    def info(self):
        """返回引擎简介"""
        return "Base engine"

    @property
    def auto_backup(self):
        """是否支持备份"""
        return False

    @property
    def seconds_behind_master(self):
        """实例同步延迟情况"""
        return None

    @property
    def server_version(self):
        """返回引擎服务器版本，返回对象为tuple (x,y,z)"""
        return tuple()

    def kill_connection(self, thread_id):
        """终止数据库连接"""

    def get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet，rows=list"""
        return ResultSet()

    def get_all_tables(self, db_name, **kwargs):
        """获取table 列表, 返回一个ResultSet，rows=list"""
        return ResultSet()

    def get_group_tables_by_db(self, db_name, **kwargs):
        """获取首字符分组的table列表，返回一个dict"""
        return dict()

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
        """获取数据库所有表格信息，用作数据字典导出接口"""
        return list()

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段, 返回一个ResultSet，rows=list"""
        return ResultSet()

    def describe_table(self, db_name, tb_name, **kwargs):
        """获取表结构, 返回一个 ResultSet，rows=list"""
        return ResultSet()

    def query_check(self, db_name=None, sql=""):
        """查询语句的检查、注释去除、切分, 返回一个字典 {'bad_query': bool, 'filtered_sql': str}"""

    def filter_sql(self, sql='', limit_num=0):
        """给查询语句增加结果级限制或者改写语句, 返回修改后的语句"""
        return sql.strip()

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True, **kwargs):
        """实际查询 返回一个ResultSet"""

    def query_masking(self, db_name=None, sql='', resultset=None):
        """传入 sql语句, db名, 结果集,
        返回一个脱敏后的结果集"""
        return resultset

    def execute_check(self, db_name=None, sql=''):
        """执行语句的检查 返回一个ReviewSet"""

    def execute(self):
        """执行语句 返回一个ReviewSet"""

    def get_execute_percentage(self):
        """获取执行进度"""

    def get_rollback(self, workflow):
        """获取工单回滚语句"""

    def get_variables(self, variables=None):
        """获取实例参数，返回一个 ResultSet"""
        return ResultSet()

    def set_variable(self, variable_name, variable_value):
        """修改实例参数值，返回一个 ResultSet"""
        return ResultSet()


def get_engine(instance=None):  # pragma: no cover
    """获取数据库操作engine"""
    if instance.db_type == "mysql":
        from .mysql import MysqlEngine

        return MysqlEngine(instance=instance)
    elif instance.db_type == "mssql":
        from .mssql import MssqlEngine

        return MssqlEngine(instance=instance)
    elif instance.db_type == "redis":
        from .redis import RedisEngine

        return RedisEngine(instance=instance)
    elif instance.db_type == "pgsql":
        from .pgsql import PgSQLEngine

        return PgSQLEngine(instance=instance)
    elif instance.db_type == "oracle":
        from .oracle import OracleEngine

        return OracleEngine(instance=instance)
    elif instance.db_type == "mongo":
        from .mongo import MongoEngine

        return MongoEngine(instance=instance)
    elif instance.db_type == "goinception":
        from .goinception import GoInceptionEngine

        return GoInceptionEngine(instance=instance)
    elif instance.db_type == "phoenix":
        from .phoenix import PhoenixEngine

        return PhoenixEngine(instance=instance)

    elif instance.db_type == 'odps':
        from .odps import ODPSEngine

        return ODPSEngine(instance=instance)

    elif instance.db_type == 'clickhouse':
        from .clickhouse import ClickHouseEngine

        return ClickHouseEngine(instance=instance)
