# -*- coding: UTF-8 -*-
import sqlparse
# -*- coding: UTF-8 -*-

import MySQLdb
import traceback

from common.utils.aes_decryptor import Prpcrypt
from sql.models import Instance
import logging

logger = logging.getLogger('default')


class mysql_exec(object):
    def __init__(self, instance_name=None, flag=False, **kwargs):
        self.flag = flag
        if instance_name:
            try:
                instance_info = Instance.objects.get(instance_name=instance_name)

                self.host = instance_info.host
                self.port = int(instance_info.port)
                self.user = instance_info.user
                self.password = Prpcrypt().decrypt(instance_info.password)
                if self.flag:
                    self.conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password,
                                                charset='utf8')
                    self.cursor = self.conn.cursor()
            except Exception:
                raise Exception('找不到对应的实例配置信息，请配置')
        else:
            self.host = kwargs.get('host', '')
            self.port = kwargs.get('port', 0)
            self.user = kwargs.get('user', '')
            self.password = kwargs.get('password', '')

    def close(self):
        self.cursor.close()
        self.conn.close()

    def execute(self, db_name=None, sql='', close_conn=True):
        """原生执行语句"""
        result = {}
        conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password, db=db_name,
                                   charset='utf8')
        try:
            cursor = conn.cursor()
            for statement in sqlparse.split(sql):
                cursor.execute(statement)
            conn.commit()
            cursor.close()
        except Exception as e:
            logger.error(traceback.format_exc())
            result['Error'] = str(e)
        else:
            cursor.close()
            conn.close()
        return result

