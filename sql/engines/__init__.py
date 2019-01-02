"""engine base库, 包含一个``EngineBase`` class和一个get_engine函数"""
from sql.models import Instance, SqlWorkflow
from common.utils.aes_decryptor import Prpcrypt
class EngineBase:
    """enginebase 只定义了init函数和若干方法的名字, 具体实现用mysql.py pg.py等实现"""
    def __init__(self, instance=None, workflow=None):
        if workflow:
            self.workflow = workflow
            instance = Instance.objects.get(instance_name=self.workflow.instance_name)
            self.sql = workflow.sql_content
        if instance:
            self.instance_name = instance.instance_name
            self.host = instance.host
            self.port = int(instance.port)
            self.user = instance.user
            self.password = Prpcrypt().decrypt(instance.password)
    
    @property
    def Connection(self):
        """返回一个conn实例"""
    @property
    def name(self):
        """返回engine名称"""
        return 'base'
    @property
    def info(self):
        """返回引擎简介"""
        return 'Base engine'
    def get_all_databases(self):
        """获取数据库列表, 返回一个list"""
    def get_all_tables(self, db_name):
        """获取table 列表, 返回一个list"""
    def get_all_columns_by_tb(self, db_name, tb_name):
        """获取所有字段, 返回一个list"""
    def query_check(self, db_name=None, sql=''):
        """查询语句的检查"""
    def query(self, db_name=None, sql='', limit_num=0):
        """实际查询"""
    def execute_check(self, db_name=None, sql=''):
        """执行语句的检查"""
    def execute(self):
        """执行语句"""
    def get_execute_percentage(self):
        """获取执行进度"""
    def get_rollback(self):
        """获取工单回滚语句"""


def get_engine(instance=None, workflow=None):
    """获取数据库操作engine"""
    if workflow:
        instance = Instance.objects.get(instance_name=workflow.instance_name)
    if instance.db_type == 'mysql':
        from .mysql import MysqlEngine
        return MysqlEngine(instance=instance)