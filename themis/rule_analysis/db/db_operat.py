# -*- coding: utf-8 -*-
import MySQLdb
from django.db import connection
from sql.models import Instance
import logging

logger = logging.getLogger('default')


class DbOperat(object):
    """
    数据库连接模块，支持mysql的连接
    """

    def __init__(self, instance_name, db_name, flag=True, charset="utf8mb4"):
        try:
            instance_info = Instance.objects.get(instance_name=instance_name)
        except Exception:
            connection.close()
            instance_info = Instance.objects.get(instance_name=instance_name)
        self.host = instance_info.host
        self.port = int(instance_info.port)
        self.user = instance_info.user
        self.password = instance_info.raw_password
        self.charset = instance_info.charset or charset
        if flag:
            self.conn = MySQLdb.connect(host=self.host,
                                        port=int(self.port),
                                        user=self.user,
                                        passwd=self.password,
                                        db=db_name,
                                        charset=self.charset)
            self.cursor = self.conn.cursor()

    def get_db_cursor(self):
        return self.cursor

    def execute(self, sql):
        try:
            self.cursor.execute(sql)
            results = self.cursor.fetchall()
        except Exception as e:
            logger.error(f"Themis执行MySQL语句出错，语句：{sql}，错误信息：{e}")
            raise Exception(e)
        else:
            return results

    def close(self):
        self.cursor.close()
        self.conn.close()

    def escape(self, string):
        return MySQLdb.escape_string(string)

    def new_connect(self, host, port, db, user, passwd):
        self.conn = MySQLdb.connect(host=host, port=port, user=user, passwd=passwd, db=db, charset="utf8mb4")
        self.cursor = self.conn.cursor()


if __name__ == "__main__":
    pass
