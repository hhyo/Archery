# -*- coding: utf-8 -*-
import MySQLdb

from sql.models import Instance
from common.utils.aes_decryptor import Prpcrypt

prpCryptor = Prpcrypt()


class DbOperat(object):
    """
    数据库连接模块，支持mysql的连接
    """

    def __init__(self, instance_name, db_name, flag=True, charset="utf8"):
        instance_info = Instance.objects.get(instance_name=instance_name)
        self.host = instance_info.host
        self.port = int(instance_info.port)
        self.user = instance_info.user
        self.password = prpCryptor.decrypt(instance_info.password)
        if flag:
            self.conn = MySQLdb.connect(host=self.host,
                                        port=int(self.port),
                                        user=self.user,
                                        passwd=self.password,
                                        db=db_name,
                                        charset=charset)
            self.cursor = self.conn.cursor()

    def get_db_cursor(self):
        return self.cursor

    def execute(self, sql):
        self.cursor.execute(sql)
        results = self.cursor.fetchall()
        return results

    def close(self):
        self.cursor.close()
        self.conn.close()

    def escape(self, string):
        return MySQLdb.escape_string(string)

    def new_connect(self, host, port, db, user, passwd):
        self.conn = MySQLdb.connect(host=host, port=port, user=user, passwd=passwd, db=db, charset="utf8")
        self.cursor = self.conn.cursor()


if __name__ == "__main__":
    pass
