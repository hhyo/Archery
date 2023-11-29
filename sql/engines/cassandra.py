import re

import logging
import traceback

from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import tuple_factory
from cassandra.policies import RoundRobinPolicy

import sqlparse

from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult

from sql.models import SqlWorkflow

logger = logging.getLogger("default")


def split_sql(db_name=None, sql=""):
    """切分语句，追加到检测结果中，默认全部检测通过"""
    sql = sqlparse.format(sql, strip_comments=True)
    sql_result = []
    if db_name:
        sql_result += [f"""USE {db_name}"""]
    sql_result += sqlparse.split(sql)
    return sql_result


def dummy_audit(full_sql: str, sql_list) -> ReviewSet:
    check_result = ReviewSet(full_sql=full_sql)
    rowid = 1
    for statement in sql_list:
        check_result.rows.append(
            ReviewResult(
                id=rowid,
                errlevel=0,
                stagestatus="Audit completed",
                errormessage="None",
                sql=statement,
                affected_rows=0,
                execute_time=0,
            )
        )
        rowid += 1
    return check_result


class CassandraEngine(EngineBase):
    name = "Cassandra"
    info = "Cassandra engine"

    def get_connection(self, db_name=None):
        db_name = db_name or self.db_name
        if self.conn:
            if db_name:
                self.conn.execute(f"use {db_name}")
            return self.conn
        auth_provider = PlainTextAuthProvider(
            username=self.user, password=self.password
        )
        hosts = self.host.split(",")
        cluster = Cluster(
            hosts,
            port=self.port,
            auth_provider=auth_provider,
            load_balancing_policy=RoundRobinPolicy(),
            protocol_version=5,
        )
        self.conn = cluster.connect(keyspace=db_name)
        self.conn.row_factory = tuple_factory
        return self.conn

    def close(self):
        if self.conn:
            self.conn.shutdown()
            self.conn = None

    def test_connection(self):
        result = self.get_all_databases()
        self.close()
        return result

    def escape_string(self, value: str) -> str:
        return re.sub(r"[; ]", "", value)

    def get_all_databases(self, **kwargs):
        """
        获取所有的 keyspace/database
        :return:
        """
        result = self.query(sql="SELECT keyspace_name FROM system_schema.keyspaces;")
        result.rows = [x[0] for x in result.rows]
        return result

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有列, 返回一个ResultSet"""
        sql = "select column_name from columns where keyspace_name=%s and table_name=%s"
        result = self.query(
            db_name="system_schema", sql=sql, parameters=(db_name, tb_name)
        )
        result.rows = [x[0] for x in result.rows]
        return result

    def describe_table(self, db_name, tb_name, **kwargs):
        sql = f"describe table {tb_name}"
        result = self.query(db_name=db_name, sql=sql)
        result.column_list = ["table", "create table"]
        filtered_rows = []
        for r in result.rows:
            filtered_rows.append((r[2], r[3]))
        result.rows = filtered_rows
        return result

    def query_check(self, db_name=None, sql="", limit_num: int = 100):
        """提交查询前的检查"""
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
        if re.match(r"^select|^describe", sql, re.I) is None:
            result["bad_query"] = True
            result["msg"] = "不支持的查询语法类型!"
        if "*" in sql:
            result["has_star"] = True
            result["msg"] = "SQL语句中含有 * "
        return result

    def filter_sql(self, sql="", limit_num=0) -> str:
        # 对查询sql增加limit限制,limit n 或 limit n,n 或 limit n offset n统一改写成limit n
        sql = sql.rstrip(";").strip()
        if re.match(r"^select", sql, re.I):
            # LIMIT N
            limit_n = re.compile(r"limit\s+(\d+)\s*$", re.I)
            if limit_n.search(sql):
                sql_limit = limit_n.search(sql).group(1)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = limit_n.sub(f"limit {limit_num};", sql)
            else:
                sql = f"{sql} limit {limit_num};"
        else:
            sql = f"{sql};"
        return sql

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
            rows = conn.execute(sql, parameters=parameters)
            result_set.column_list = rows.column_names
            result_set.rows = rows.all()
            result_set.affected_rows = len(result_set.rows)
            if limit_num > 0:
                result_set.rows = result_set.rows[0:limit_num]
                result_set.affected_rows = min(limit_num, result_set.affected_rows)
        except Exception as e:
            logger.warning(
                f"{self.name} query 错误，语句：{sql}， 错误信息：{traceback.format_exc()}"
            )
            result_set.error = str(e)
        if close_conn:
            self.close()
        return result_set

    def get_all_tables(self, db_name, **kwargs):
        sql = "SELECT table_name FROM system_schema.tables WHERE keyspace_name = %s;"
        parameters = [db_name]
        result = self.query(db_name=db_name, sql=sql, parameters=parameters)
        tb_list = [row[0] for row in result.rows]
        result.rows = tb_list
        return result

    def query_masking(self, db_name=None, sql="", resultset=None):
        """不做脱敏"""
        return resultset

    def execute_check(self, db_name=None, sql=""):
        """上线单执行前的检查, 返回Review set"""
        sql_result = split_sql(db_name, sql)
        return dummy_audit(sql, sql_result)

    def execute(self, db_name=None, sql="", close_conn=True, parameters=None):
        """执行sql语句 返回 Review set"""
        execute_result = ReviewSet(full_sql=sql)
        conn = self.get_connection(db_name=db_name)
        sql_result = split_sql(db_name, sql)
        rowid = 1
        for statement in sql_result:
            try:
                conn.execute(statement)
                execute_result.rows.append(
                    ReviewResult(
                        id=rowid,
                        errlevel=0,
                        stagestatus="Execute Successfully",
                        errormessage="None",
                        sql=statement,
                        affected_rows=0,
                        execute_time=0,
                    )
                )
            except Exception as e:
                logger.warning(
                    f"{self.name} 命令执行报错，语句：{sql}， 错误信息：{traceback.format_exc()}"
                )
                execute_result.error = str(e)
                execute_result.rows.append(
                    ReviewResult(
                        id=rowid,
                        errlevel=2,
                        stagestatus="Execute Failed",
                        errormessage=f"异常信息：{e}",
                        sql=statement,
                        affected_rows=0,
                        execute_time=0,
                    )
                )
                break
            rowid += 1
        if execute_result.error:
            for statement in sql_result[rowid:]:
                execute_result.rows.append(
                    ReviewResult(
                        id=rowid,
                        errlevel=2,
                        stagestatus="Execute Failed",
                        errormessage="前序语句失败, 未执行",
                        sql=statement,
                        affected_rows=0,
                        execute_time=0,
                    )
                )
                rowid += 1
        if close_conn:
            self.close()
        return execute_result

    def execute_workflow(self, workflow: SqlWorkflow):
        """执行上线单，返回Review set"""
        return self.execute(
            db_name=workflow.db_name, sql=workflow.sqlworkflowcontent.sql_content
        )
