# -*-coding: utf-8-*-

import logging
import MySQLdb
from common.config import SysConfig

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
