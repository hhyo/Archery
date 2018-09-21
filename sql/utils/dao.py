# -*- coding: UTF-8 -*- 

import MySQLdb
import traceback

from common.utils.aes_decryptor import Prpcrypt
from sql.models import Instance
import logging

logger = logging.getLogger('default')


class Dao(object):
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

    # 连进指定的mysql实例里，读取所有databases并返回
    def getAlldbByCluster(self):
        try:
            conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password, charset='utf8')
            cursor = conn.cursor()
            sql = "show databases"
            cursor.execute(sql)
            db_list = [row[0] for row in cursor.fetchall()
                       if row[0] not in ('information_schema', 'performance_schema', 'mysql', 'test', 'sys')]
        except MySQLdb.Warning as w:
            logger.error(traceback.format_exc())
            raise Exception(w)
        except MySQLdb.Error as e:
            logger.error(traceback.format_exc())
            raise Exception(e)
        else:
            cursor.close()
            conn.close()
        return db_list

    # 连进指定的mysql实例里，读取所有tables并返回
    def getAllTableByDb(self, db_name):
        try:
            conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password, db=db_name,
                                   charset='utf8')
            cursor = conn.cursor()
            sql = "show tables"
            cursor.execute(sql)
            tb_list = [row[0] for row in cursor.fetchall() if row[0] not in ['test']]
        except MySQLdb.Warning as w:
            logger.error(traceback.format_exc())
            raise Exception(w)
        except MySQLdb.Error as e:
            logger.error(traceback.format_exc())
            raise Exception(e)
        else:
            cursor.close()
            conn.close()
        return tb_list

    # 连进指定的mysql实例里，读取所有Columns并返回
    def getAllColumnsByTb(self, db_name, tb_name):
        try:
            conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password, db=db_name,
                                   charset='utf8')
            cursor = conn.cursor()
            sql = "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='%s' AND TABLE_NAME='%s';" % (
                db_name, tb_name)
            cursor.execute(sql)
            col_list = [row[0] for row in cursor.fetchall()]
        except MySQLdb.Warning as w:
            logger.error(traceback.format_exc())
            raise Exception(w)
        except MySQLdb.Error as e:
            logger.error(traceback.format_exc())
            raise Exception(e)
        else:
            cursor.close()
            conn.close()
        return col_list

    # 连进指定的mysql实例里，执行sql并返回
    def mysql_query(self, db_name=None, sql='', limit_num=0):
        result = {'column_list': [], 'rows': [], 'effect_row': 0}
        try:
            if self.flag:
                conn = self.conn
                cursor = self.cursor
                if db_name:
                    cursor.execute('use {}'.format(db_name))
            else:
                conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password, db=db_name,
                                       charset='utf8')
                cursor = conn.cursor()
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
            result['column_list'] = column_list
            result['rows'] = rows
            result['effect_row'] = effect_row

        except MySQLdb.Warning as w:
            logger.error(traceback.format_exc())
            result['Warning'] = str(w)
        except MySQLdb.Error as e:
            logger.error(traceback.format_exc())
            result['Error'] = str(e)
        else:
            if self.flag:
                # 结束后手动close
                pass
            else:
                conn.rollback()
                cursor.close()
                conn.close()
        return result

    # 连进指定的mysql实例里，执行sql并返回
    def mysql_execute(self, db_name, sql):
        result = {}
        try:
            conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password, db=db_name,
                                   charset='utf8')
            cursor = conn.cursor()
            effect_row = cursor.execute(sql)
            # result = {}
            # result['effect_row'] = effect_row
            conn.commit()
        except MySQLdb.Warning as w:
            logger.error(traceback.format_exc())
            result['Warning'] = str(w)
        except MySQLdb.Error as e:
            logger.error(traceback.format_exc())
            result['Error'] = str(e)
        else:
            cursor.close()
            conn.close()
        return result
