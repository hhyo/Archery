# -*- coding: UTF-8 -*-
import logging
import traceback
import MySQLdb

from .mysql import MysqlEngine
from .models import ResultSet

logger = logging.getLogger('default')


class MariaDBEngine(MysqlEngine):

    def __init__(self, instance=None):
        super().__init__(instance=instance)

    @property
    def name(self):
        return 'MariaDB'

    @property
    def info(self):
        return 'MariaDB engine'

    @property
    def auto_backup(self):
        """是否支持备份"""
        return True

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True, **kwargs):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        cursorclass = kwargs.get('cursorclass') or MySQLdb.cursors.Cursor
        try:
            conn = self.get_connection(db_name=db_name)
            conn.autocommit(True)
            cursor = conn.cursor(cursorclass)
            effect_row = cursor.execute(sql)
            if int(limit_num) > 0:
                rows = cursor.fetchmany(size=int(limit_num))
            else:
                rows = cursor.fetchall()
            fields = cursor.description

            result_set.column_list = [i[0] for i in fields] if fields else []
            result_set.rows = rows
            result_set.affected_rows = effect_row
        except Exception as e:
            logger.warning(f"MariaDB语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}")
            result_set.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result_set
