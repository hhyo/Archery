# -*- coding: UTF-8 -*-
import taosws
from .models import ResultSet, ReviewResult
from common.config import SysConfig
from . import EngineBase
from pymysql import escape_string
import sqlparse
import logging
import re

logger = logging.getLogger("default")


class TDengineEngine(EngineBase):
    test_query = "SELECT 1"

    def __init__(self, instance=None):
        super(TDengineEngine, self).__init__(instance=instance)
        self.config = SysConfig()

    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        if db_name:
            self.conn = taosws.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=db_name,
                read_timeout="600",
            )
        else:
            self.conn = taosws.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                read_timeout="600",
            )
        return self.conn

    name = "TDengine"
    info = "TDengine engine"

    def escape_string(self, value: str) -> str:
        """字符串参数转义"""
        return escape_string(value)

    @property
    def auto_backup(self):
        """是否支持备份"""
        return False

    @property
    def server_version(self):
        sql = "select server_version();"
        result = self.query(sql=sql)
        version = result.rows[0][0]
        return tuple([int(n) for n in version.split(".")[:3]])

    def get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet"""
        sql = "show databases"
        result = self.query(sql=sql)
        db_list = [
            row[0]
            for row in result.rows
            if row[0] not in ("information_schema", "performance_schema", "log")
        ]
        result.rows = sorted(db_list)
        return result

    def get_all_tables(self, db_name, **kwargs):
        """获取table 列表, 包含普通表和超级表，返回一个ResultSet"""
        ntable_sql = """select
            table_name
        from
            information_schema.ins_tables
        where 
            type = 'NORMAL_TABLE'
        and db_name = '%s';
        """ % self.escape_string(db_name)
        table_result = self.query(db_name=db_name, sql=ntable_sql)
        tb_list = sorted([row[0] for row in table_result.rows])
        tb_list.insert(0, "普通表") if tb_list else []
        stable_sql = """select
            stable_name
        from
            information_schema.ins_stables
        where 
            db_name = '%s';
        """ % self.escape_string(db_name)
        stable_result = self.query(db_name=db_name, sql=stable_sql)
        stb_list = sorted([row[0] for row in stable_result.rows])
        stb_list.insert(0, "超级表") if stb_list else []
        tb_list.extend(stb_list)
        stable_result.rows = tb_list
        return stable_result

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段, 返回一个ResultSet"""
        sql = """select
            col_name,
            col_type
        from
            information_schema.ins_columns
        where
            db_name = '%s'
        and table_name = '%s';"""
        result = self.query(
            db_name=db_name,
            sql=sql,
            parameters=(db_name, tb_name),
        )
        column_list = [row[0] for row in result.rows]
        result.rows = column_list
        return result

    def get_table_type(self, db_name, tb_name, **kwargs):
        """获取表类型, 返回stable或table"""
        stable_sql = """select
            stable_name
        from
            information_schema.ins_stables
        where
            db_name = '%s'
        and stable_name = '%s';"""
        stable_result = self.query(
            db_name=db_name,
            sql=stable_sql,
            parameters=(db_name, tb_name),
        )
        if stable_result.rows:
            return "stable"
        table_sql = """select
            table_name
        from
            information_schema.ins_tables
        where
            db_name = '%s'
        and table_name = '%s';"""
        table_result = self.query(
            db_name=db_name,
            sql=table_sql,
            parameters=(db_name, tb_name),
        )
        if table_result.rows:
            return "table"
        return None

    def describe_table(self, db_name, tb_name, **kwargs):
        """return ResultSet 类似查询"""
        tb_name = self.escape_string(tb_name)
        table_type = self.get_table_type(db_name, tb_name)
        if table_type == "table":
            sql = f"show create table `{tb_name}`;"
        else:
            sql = f"show create stable `{tb_name}`;"
        result = self.query(db_name=db_name, sql=sql)
        formatted = re.sub(
            r"(CREATE\s+(?:STABLE|TABLE)\s+`[^`]+`\s*)\(`",
            r"\1(\n    `",
            result.rows[0][1],
        )
        formatted = formatted.replace(", `", ",\n    `")
        formatted = re.sub(r"\)\s*TAGS", "\n)\nTAGS", formatted)
        formatted = re.sub(r"\)\s*SMA", "\n)\nSMA", formatted)
        formatted = formatted.replace("TAGS (`", "TAGS (\n    `")
        formatted = formatted.replace("SMA(`", "SMA(\n    `")
        formatted = re.sub(r"(`\s*)\)$", r"\1\n)", formatted)

        result.rows[0] = (tb_name,) + (formatted,)
        return result

    def query(
        self,
        db_name=None,
        sql="",
        limit_num=0,
        close_conn=True,
        parameters=None,
        **kwargs,
    ):
        """返回 ResultSet"""
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection(db_name=db_name)
            cursor = conn.cursor()
            if parameters:
                parameters = tuple(self.escape_string(str(p)) for p in parameters)
                cursor.execute(sql % parameters)
            else:
                cursor.execute(sql)
            if int(limit_num) > 0:
                rows = cursor.fetchmany(size=int(limit_num))
            else:
                rows = cursor.fetchall()
            fields = cursor.description

            result_set.column_list = [i[0] for i in fields] if fields else []
            result_set.rows = rows
            result_set.affected_rows = len(rows)
        except Exception as e:
            logger.warning(f"TDengine语句执行报错，语句：{sql}，错误信息{e}")
            result_set.error = str(e)
        finally:
            if close_conn:
                self.close()
        return result_set

    def query_check(self, db_name=None, sql=""):
        # 查询语句的检查、注释去除、切分
        result = {"msg": "", "bad_query": False, "filtered_sql": sql, "has_star": False}
        # 删除注释语句，进行语法判断，执行第一条有效sql
        try:
            sql = sqlparse.format(sql, strip_comments=True)
            sql = sqlparse.split(sql)[0]
            result["filtered_sql"] = sql.strip()
        except IndexError:
            result["bad_query"] = True
            result["msg"] = "没有有效的SQL语句"
        if re.match(r"^select|^show|^explain|^with", sql, re.I) is None:
            result["bad_query"] = True
            result["msg"] = "不支持的查询语法类型!"
        if "*" in sql:
            result["has_star"] = True
            result["msg"] = "SQL语句中含有 * "
        # select语句先使用Explain判断语法是否正确
        if re.match(r"^select", sql, re.I):
            explain_result = self.query(db_name=db_name, sql=f"explain {sql}")
            if explain_result.error:
                result["bad_query"] = True
                result["msg"] = explain_result.error

        return result

    def filter_sql(self, sql="", limit_num=0):
        # 对查询sql增加limit限制,limit n 或 limit n,n 或 limit n offset n统一改写成limit n
        sql = sql.rstrip(";").strip()
        if re.match(r"^select", sql, re.I):
            # LIMIT N
            limit_n = re.compile(r"limit\s+(\d+)\s*$", re.I)
            # LIMIT M OFFSET N
            limit_offset = re.compile(r"limit\s+(\d+)\s+offset\s+(\d+)\s*$", re.I)
            # LIMIT M,N
            offset_comma_limit = re.compile(r"limit\s+(\d+)\s*,\s*(\d+)\s*$", re.I)
            if limit_n.search(sql):
                sql_limit = limit_n.search(sql).group(1)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = limit_n.sub(f"limit {limit_num};", sql)
            elif limit_offset.search(sql):
                sql_limit = limit_offset.search(sql).group(1)
                sql_offset = limit_offset.search(sql).group(2)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = limit_offset.sub(f"limit {limit_num} offset {sql_offset};", sql)
            elif offset_comma_limit.search(sql):
                sql_offset = offset_comma_limit.search(sql).group(1)
                sql_limit = offset_comma_limit.search(sql).group(2)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = offset_comma_limit.sub(f"limit {sql_offset},{limit_num};", sql)
            else:
                sql = f"{sql} limit {limit_num};"
        else:
            sql = f"{sql};"
        return sql

    def processlist(self, command_type, **kwargs):
        """获取query会话信息"""
        sql = "show queries"

        return self.query(sql=sql)

    def get_kill_command(self, kill_ids):
        """由传入的kill_id列表生成kill命令"""
        # 校验传参，kill_ids格式：[kill_id1:xxx, kill_id2:xxx]
        if any(
            [
                i if re.fullmatch(r"[0-9a-zA-Z]+:[0-9a-zA-Z]+", i) is None else None
                for i in kill_ids
            ]
        ):
            return None
        all_kill_sql = "".join(f"kill query '{i}';" for i in kill_ids)

        return all_kill_sql

    def kill_query(self, kill_ids):
        """kill query"""
        # 校验传参，kill_ids格式：[kill_id1:xxx, kill_id2:xxx]
        if any(
            [
                i if re.fullmatch(r"[0-9a-zA-Z]+:[0-9a-zA-Z]+", i) is None else None
                for i in kill_ids
            ]
        ):
            return ResultSet(full_sql="")
        # 查询最新processlist，校验query还未完成的，才进行kill操作
        processlist_result = self.processlist(command_type="all")
        latest_kill_ids = [row[0] for row in processlist_result.rows]
        valid_kill_ids = [i for i in kill_ids if i in latest_kill_ids]
        if not valid_kill_ids:
            return ResultSet(full_sql="")
        all_kill_sql = "".join(f"kill query '{i}';" for i in valid_kill_ids)
        return self.execute(sql=all_kill_sql)

    def execute(self, db_name=None, sql="", close_conn=True, parameters=None):
        """原生执行语句"""
        result = ResultSet(full_sql=sql)
        conn = self.get_connection(db_name=db_name)
        try:
            cursor = conn.cursor()
            for statement in sqlparse.split(sql):
                cursor.execute(statement)
            cursor.close()
        except Exception as e:
            logger.warning(f"TDengine语句执行报错，语句：{sql}，错误信息{e}")
            result.error = str(e)
        if close_conn:
            self.close()
        return result

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
