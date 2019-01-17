# -*-coding: utf-8-*-
import logging
import traceback
import MySQLdb
import simplejson as json
from common.config import SysConfig
from sql.models import SqlWorkflow

from . import EngineBase
from .models import ResultSet

logger = logging.getLogger('default')


class InceptionEngine(EngineBase):
    def get_connection(self, db_name=None):
        archer_config = SysConfig()
        inception_host = archer_config.get('inception_host')
        inception_port = int(archer_config.get('inception_port', 6669))
        conn = MySQLdb.connect(host=inception_host, port=inception_port, charset='utf8')
        return conn

    def get_backup_connection(self):
        archer_config = SysConfig()
        backup_host = archer_config.get('inception_remote_backup_host')
        backup_port = int(archer_config.get('inception_remote_backup_port', 3306))
        backup_user = archer_config.get('inception_remote_backup_user')
        backup_password = archer_config.get('inception_remote_backup_password')
        return MySQLdb.connect(host=backup_host,
                               port=backup_port,
                               user=backup_user,
                               passwd=backup_password,
                               charset='utf8')

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        conn = self.get_connection()
        with conn.cursor() as cursor:
            effect_row = cursor.execute(sql)
            if int(limit_num) > 0:
                rows = cursor.fetchmany(size=int(limit_num))
            else:
                rows = cursor.fetchall()
            fields = cursor.description

            column_list = []
            if fields:
                for i in fields:
                    column_list.append(i[0])
            result_set.column_list = column_list
            result_set.rows = rows
            result_set.affected_rows = effect_row
        conn.close()
        return result_set

    def query_print(self, db_name=None, sql=''):
        """
        将sql交给inception打印语法树。
        """
        sql = "/*--user=%s;--password=%s;--host=%s;--port=%d;--enable-query-print;*/\
                          inception_magic_start;\
                          use %s;\
                          %s\
                          inception_magic_commit;" % (self.user,
                                                      self.password,
                                                      self.host,
                                                      self.port,
                                                      db_name,
                                                      sql)
        return self.query(db_name=db_name, sql=sql)

    def get_rollback_list(self, workflow_id):
        """
        获取回滚语句，并且按照执行顺序倒序展示
        """
        workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
        list_execute_result = json.loads(workflow_detail.execute_result)
        list_execute_result.reverse()
        list_backup_sql = []
        # 创建连接
        conn = self.get_backup_connection()
        cur = conn.cursor()
        for row in list_execute_result:
            try:
                # 获取backup_db_name， 兼容旧数据'[[]]'格式
                if isinstance(row, list):
                    if row[8] == 'None':
                        continue
                    backup_db_name = row[8]
                    sequence = row[7]
                    sql = row[5]
                else:
                    if row.get('backup_dbname') == 'None':
                        continue
                    backup_db_name = row.get('backup_dbname')
                    sequence = row.get('sequence')
                    sql = row.get('sql')
                opid_time = sequence.replace("'", "")
                sql_table = "select tablename from {}.$_$Inception_backup_information$_$ where opid_time='{}';".format(
                    backup_db_name, opid_time)
                cur.execute(sql_table)
                list_tables = cur.fetchall()
                if list_tables:
                    table_name = list_tables[0][0]
                    sql_back = "select rollback_statement from {}.{} where opid_time='{}'".format(
                        backup_db_name, table_name, opid_time)
                    cur.execute(sql_back)
                    list_backup = cur.fetchall()
                    block_rollback_sql_list = [sql]
                    block_rollback_sql = '\n'.join([back_info[0] for back_info in list_backup])
                    block_rollback_sql_list.append(block_rollback_sql)
                    list_backup_sql.append(block_rollback_sql_list)
            except Exception as e:
                logger.error(traceback.format_exc())
                raise Exception(e)
        return list_backup_sql
