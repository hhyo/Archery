"""engine base库, 包含一个``EngineBase`` class和一个get_engine函数"""

import importlib
from sql.engines.models import ResultSet, ReviewSet
from sql.utils.ssh_tunnel import SSHConnection
from django.conf import settings


class EngineBase:
    """enginebase 只定义了init函数和若干方法的名字, 具体实现用mysql.py pg.py等实现"""

    test_query = None

    name = "Base"
    info = "base engine"

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
            self.is_ssl = instance.is_ssl

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
                self.host, self.port = self.ssh.get_ssh()

    def __del__(self):
        if hasattr(self, "ssh"):
            del self.ssh
        if hasattr(self, "remotessh"):
            del self.remotessh

    def remote_instance_conn(self, instance=None):
        # 判断如果配置了隧道则连接隧道
        if not hasattr(self, "remotessh") and instance.tunnel:
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
        return (
            self.remote_host,
            self.remote_port,
            self.remote_user,
            self.remote_password,
        )

    def get_connection(self, db_name=None):
        """返回一个conn实例"""

    def test_connection(self):
        """测试实例链接是否正常"""
        return self.query(sql=self.test_query)

    def escape_string(self, value: str) -> str:
        """参数转义"""
        return value

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

    def get_all_databases_summary(self):
        """实例数据库管理功能，获取实例所有的数据库描述信息"""
        return ResultSet()

    def get_instance_users_summary(self):
        """实例账号管理功能，获取实例所有账号信息"""
        return ResultSet()

    def create_instance_user(self, **kwargs):
        """实例账号管理功能，创建实例账号"""
        return ResultSet()

    def drop_instance_user(self, **kwargs):
        """实例账号管理功能，删除实例账号"""
        return ResultSet()

    def reset_instance_user_pwd(self, **kwargs):
        """实例账号管理功能，重置实例账号密码"""
        return ResultSet()

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段, 返回一个ResultSet，rows=list"""
        return ResultSet()

    def describe_table(self, db_name, tb_name, **kwargs):
        """获取表结构, 返回一个 ResultSet，rows=list"""
        return ResultSet()

    def query_check(self, db_name=None, sql=""):
        """查询语句的检查、注释去除、切分, 返回一个字典 {'bad_query': bool, 'filtered_sql': str}"""

    def filter_sql(self, sql="", limit_num=0):
        """给查询语句增加结果级限制或者改写语句, 返回修改后的语句"""
        return sql.strip()

    def query(
        self,
        db_name=None,
        sql="",
        limit_num=0,
        close_conn=True,
        parameters=None,
        **kwargs,
    ):
        """实际查询 返回一个ResultSet"""
        return ResultSet()

    def query_masking(self, db_name=None, sql="", resultset=None):
        """传入 sql语句, db名, 结果集,
        返回一个脱敏后的结果集"""
        return resultset

    def execute_check(self, db_name=None, sql=""):
        """执行语句的检查 返回一个ReviewSet"""
        return ReviewSet()

    def execute(self, **kwargs):
        """执行语句 返回一个ReviewSet"""
        return ReviewSet()

    def get_execute_percentage(self):
        """获取执行进度"""

    def get_rollback(self, workflow):
        """获取工单回滚语句"""
        return list()

    def get_variables(self, variables=None):
        """获取实例参数，返回一个 ResultSet"""
        return ResultSet()

    def set_variable(self, variable_name, variable_value):
        """修改实例参数值，返回一个 ResultSet"""
        return ResultSet()


def get_engine_map():
    available_engines = settings.AVAILABLE_ENGINES
    enabled_engines = {}
    for e in settings.ENABLED_ENGINES:
        config = available_engines.get(e)
        if not config:
            raise ValueError(f"invalid engine {e}, not found in engine map")
        module, o = config["path"].split(":")
        engine = getattr(importlib.import_module(module), o)
        enabled_engines[e] = engine
    return enabled_engines


engine_map = get_engine_map()


def get_engine(instance=None):  # pragma: no cover
    """获取数据库操作engine"""
    if instance.db_type == "mysql":
        from sql.models import AliyunRdsConfig

        if AliyunRdsConfig.objects.filter(instance=instance, is_enable=True).exists():
            from .cloud.aliyun_rds import AliyunRDS

            return AliyunRDS(instance=instance)
    engine = engine_map.get(instance.db_type)
    if not engine:
        raise ValueError(
            f"engine {instance.db_type} not enabled or not supported, please contact admin"
        )
    return engine(instance=instance)
