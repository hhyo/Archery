import logging
import traceback
import re

from . import EngineBase
import pyodbc
from .models import ResultSet, ReviewResult, ReviewSet

logger = logging.getLogger('default')

class MssqlEngine(EngineBase):
    @property
    def Connection(self):
        connstr = """DRIVER=ODBC Driver 17 for SQL Server;SERVER={0};PORT={1};UID={2};PWD={3};
client charset = UTF-8;connect timeout=10;CHARSET=UTF8;""".format(self.host,
                                                                  self.port, self.user, self.password)
        conn = pyodbc.connect(connstr)
        return conn

    def get_all_databases(self):
        """连进指定的mssql实例里，读取所有databases并返回"""
        sql = "SELECT name FROM master.sys.databases"
        result = self.query(sql=sql)
        db_list = [row[0] for row in result.rows
                       if row[0] not in ('information_schema', 'performance_schema', 'mysql', 'test', 'sys')]
        return db_list

    # 连进指定的mysql实例里，读取所有tables并返回
    def get_all_tables(self, db_name):
        """return List [tables]"""
        sql = """SELECT TABLE_NAME
FROM {0}.INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE';""".format(db_name)
        result = self.query(db_name=db_name, sql=sql)
        tb_list = [row[0] for row in result.rows if row[0] not in ['test']]
        return tb_list

    def get_all_columns_by_tb(self, db_name, tb_name):
        """return list [columns]"""
        result = self.descibe_table(db_name, tb_name)
        column_list = [row[0] for row in result.rows]
        return column_list
    
    def descibe_table(self, db_name, tb_name):
        """return ResultSet"""
        sql = r"""select
c.name ColumnName,
t.name ColumnType,
c.length  ColumnLength,
c.scale   ColumnScale,
c.isnullable ColumnNull,
    case when i.id is not null then 'Y' else 'N' end TablePk
from (select name,id,uid from {0}..sysobjects where (xtype='U' or xtype='V') ) o 
inner join {0}..syscolumns c on o.id=c.id 
inner join {0}..systypes t on c.xtype=t.xusertype 
left join {0}..sysusers u on u.uid=o.uid
left join (select name,id,uid,parent_obj from {0}..sysobjects where xtype='PK' )  opk on opk.parent_obj=o.id 
left join (select id,name,indid from {0}..sysindexes) ie on ie.id=o.id and ie.name=opk.name
left join {0}..sysindexkeys i on i.id=o.id and i.colid=c.colid and i.indid=ie.indid
WHERE O.name NOT LIKE 'MS%' AND O.name NOT LIKE 'SY%'
and O.name='{1}'
order by o.name,c.colid""".format(db_name, tb_name)
        result = self.query(sql=sql)
        return result
    
    def query_check(self, db_name=None, sql='', limit_num=10):
        # 连进指定的mysql实例里，执行sql并返回
        if '*' in sql:
            return {'bad_query':True}
        # 对查询sql增加limit限制
        if re.match(r"^select", sql.lower()):
            if re.search(r"top\s+(\d+)$", sql.lower()) is None:
                if re.search(r"top\s+\d+\s*,\s*(\d+)$", sql.lower()) is None:
                    sql = sql.replace("select", "select top {}".format(limit_num))
        return {'filtered_sql': sql}
    
    def query(self, db_name=None, sql='', limit_num=0):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.Connection
            cursor = conn.cursor()
            if db_name:
                cursor.execute('use {}'.format(db_name))
            effect_row = cursor.execute(sql)
            if int(limit_num) > 0:
                rows = cursor.fetchmany(int(limit_num))
            else:
                rows = cursor.fetchall()
            fields = cursor.description

            column_list = []
            if fields:
                for i in fields:
                    column_list.append(i[0])
            result_set.column_list = column_list
            result_set.rows = [tuple(x) for x in rows]
            result_set.affected_rows = len(result_set.rows)
        except Exception as e:
            logger.error(traceback.format_exc())
            result_set.error = str(e)
        finally:
            conn.close()
        return result_set