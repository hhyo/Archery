# -*- coding: UTF-8 -*-

import re
import logging

from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult

from odps import ODPS


logger = logging.getLogger('default')


class ODPSEngine(EngineBase):

    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn

        db_name = db_name if db_name else self.instance.db_name

        if db_name is None:
            raise ValueError("db_name不能为空")

        self.conn = ODPS(self.user, self.password, project=db_name, endpoint=self.host)

        return self.conn

    @property
    def name(self):
        return 'ODPS'

    @property
    def info(self):
        return 'ODPS engine'

    def get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet
            ODPS只有project概念, 直接返回project名称
        """
        result = ResultSet()

        try:
            conn = self.get_connection(self.get_connection())
            result.rows = [conn.project]
        except Exception as e:
            logger.warning(f"ODPS执行异常, {e}")
            result.rows = [self.instance.db_name]
        return result

    def get_all_tables(self, db_name, **kwargs):
        """获取table 列表, 返回一个ResultSet"""

        db_name = db_name if db_name else self.instance.db_name
        result_set = ResultSet()

        try:
            conn = self.get_connection(db_name=db_name)

            rows = [t.name for t in conn.list_tables()]
            result_set.rows = rows

        except Exception as e:
            logger.warning(f"ODPS语句执行报错, 错误信息{e}")
            result_set.error = str(e)

        return result_set

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段, 返回一个ResultSet"""

        column_list = ['COLUMN_NAME', 'COLUMN_TYPE', 'COLUMN_COMMENT']

        conn = self.get_connection(db_name)

        table = conn.get_table(tb_name)

        schema_cols = table.schema.columns

        rows = []

        for col in schema_cols:
            rows.append([col.name, str(col.type), col.comment])

        result = ResultSet()
        result.column_list = column_list
        result.rows = rows
        return result

    def describe_table(self, db_name, tb_name, **kwargs):
        """return ResultSet 类似查询"""

        result = self.get_all_columns_by_tb(db_name, tb_name)

        return result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True,  **kwargs):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)

        if not re.match(r"^select", sql, re.I):
            result_set.error = str("仅支持ODPS查询语句")

        # 存在limit，替换limit; 不存在，添加limit
        if re.search('limit', sql):
            sql = re.sub('limit.+(\d+)', 'limit ' + str(limit_num), sql)
        else:
            if sql.strip()[-1] == ';':
                sql = sql[:-1]
            sql = sql + ' limit ' + str(limit_num) + ';'

        try:
            conn = self.get_connection(db_name)
            effect_row = conn.execute_sql(sql)
            reader = effect_row.open_reader()
            rows = [row.values for row in reader]
            column_list = getattr(reader, '_schema').names

            result_set.column_list = column_list
            result_set.rows = rows
            result_set.affected_rows = len(rows)

        except Exception as e:
            logger.warning(f"ODPS语句执行报错, 语句：{sql}，错误信息{e}")
            result_set.error = str(e)
        return result_set

