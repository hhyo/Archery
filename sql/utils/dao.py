# -*- coding: UTF-8 -*- 

import MySQLdb
from sql.utils.aes_decryptor import Prpcrypt
from sql.models import Instance
import logging

prpCryptor = Prpcrypt()

logger = logging.getLogger('default')


class Dao(object):
    def __init__(self, instance_name=None, **kwargs):
        if instance_name:
            try:
                instance_info = Instance.objects.get(instance_name=instance_name)
                self.host = instance_info.host
                self.port = int(instance_info.port)
                self.user = instance_info.user
                self.password = prpCryptor.decrypt(instance_info.password)
            except Exception:
                raise Exception('找不到对应的实例配置信息，请配置')
        else:
            self.host = kwargs.get('host', '')
            self.port = kwargs.get('port', 0)
            self.user = kwargs.get('user', '')
            self.password = kwargs.get('password', '')

    # 连进指定的mysql实例里，读取所有databases并返回
    def getAlldbByCluster(self):
        conn = None
        cursor = None

        try:
            conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password, charset='utf8')
            cursor = conn.cursor()
            sql = "show databases"
            cursor.execute(sql)
            db_list = [row[0] for row in cursor.fetchall()
                       if row[0] not in ('information_schema', 'performance_schema', 'mysql', 'test')]
        except MySQLdb.Warning as w:
            raise Exception(w)
        except MySQLdb.Error as e:
            raise Exception(e)
        finally:
            if cursor is not None:
                cursor.close()
            if conn is not None:
                conn.commit()
                conn.close()
        return db_list

    # 连进指定的mysql实例里，读取所有tables并返回
    def getAllTableByDb(self, db_name):
        conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password, db=db_name,
                               charset='utf8')
        try:
            cursor = conn.cursor()
            sql = "show tables"
            cursor.execute(sql)
            tb_list = [row[0] for row in cursor.fetchall() if row[0] not in ['test']]
        except MySQLdb.Warning as w:
            raise Exception(w)
        except MySQLdb.Error as e:
            raise Exception(e)
        finally:
            conn.commit()
            conn.close()
        return tb_list

    # 连进指定的mysql实例里，读取所有Columns并返回
    def getAllColumnsByTb(self, db_name, tb_name):
        conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password, db=db_name,
                               charset='utf8')
        try:
            cursor = conn.cursor()
            sql = "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='%s' AND TABLE_NAME='%s';" % (
                db_name, tb_name)
            cursor.execute(sql)
            col_list = [row[0] for row in cursor.fetchall()]
        except MySQLdb.Warning as w:
            raise Exception(w)
        except MySQLdb.Error as e:
            raise Exception(e)
        finally:
            conn.commit()
            conn.close()
        return col_list

    # 连进指定的mysql实例里，执行sql并返回
    def mysql_query(self, db_name, sql, limit_num=0):
        result = {'column_list': [], 'rows': [], 'effect_row': 0}
        conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password, db=db_name,
                               charset='utf8')
        try:
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
            logger.warning(str(w))
            result['Warning'] = str(w)
        except MySQLdb.Error as e:
            logger.error(str(e))
            result['Error'] = str(e)
        finally:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                conn.close()
        return result

    # 连进指定的mysql实例里，执行sql并返回
    def mysql_execute(self, db_name, sql):
        result = {}
        conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.password, db=db_name,
                               charset='utf8')
        try:

            cursor = conn.cursor()
            effect_row = cursor.execute(sql)
            # result = {}
            # result['effect_row'] = effect_row
            conn.commit()
        except MySQLdb.Warning as w:
            logger.warning(str(w))
            result['Warning'] = str(w)
        except MySQLdb.Error as e:
            logger.error(str(e))
            result['Error'] = str(e)
        finally:
            conn.close()
        return result
