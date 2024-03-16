# -*- coding: UTF-8 -*-
from sql.utils.sql_utils import get_syntax_type, remove_comments
from sql.engines.mysql import MysqlEngine
from .models import ResultSet, ReviewResult, ReviewSet
from common.utils.timer import FuncTimer
from common.config import SysConfig
import traceback
import pymysql
import sqlparse
import logging
import re


logger = logging.getLogger("default")

class DorisEngine(MysqlEngine):
    def __init__(self, instance=None):
        super(DorisEngine, self).__init__(instance=instance)
        self.config = SysConfig()

    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        if db_name:
            self.conn = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                port=self.port,
                database=db_name,
                connect_timeout=10
            )
        else:
            self.conn = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                port=self.port,
                connect_timeout=10
            )
        return self.conn

    @property
    def name(self):
        return "Doris"

    @property
    def info(self):
        return "Doris engine"

    @property
    def auto_backup(self):
        return False

    @property
    def server_version(self):
        sql = "show frontends"
        result = self.query(sql=sql)
        version = result.rows[0][-1].split("-")[0]
        return tuple([int(n) for n in version.split(".")[:3]])


    def query(self, db_name=None, sql="", limit_num=0, close_conn=True, **kwargs):
        """返回 ResultSet"""
        result_set = ResultSet(full_sql=sql)
        try:
            conn = self.get_connection(db_name=db_name)
            cursor = conn.cursor()
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
            logger.warning(f"Doris语句执行报错，语句：{sql}，错误信息{e}")
            result_set.error = str(e).split("Stack trace")[0]
        finally:
            if close_conn:
                self.close()
        return result_set

    def get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet"""
        sql = "show databases"
        result = self.query(sql=sql)
        db_list = [
            row[0]
            for row in result.rows
            if row[0]
            not in ("__internal_schema","INFORMATION_SCHEMA", "information_schema")
        ]
        result.rows = db_list
        return result

    def get_all_tables(self, db_name, **kwargs):
        """获取table 列表, 返回一个ResultSet"""
        sql = "show tables"
        result = self.query(db_name=db_name, sql=sql)
        tb_list = [row[0] for row in result.rows]
        result.rows = tb_list
        return result

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段, 返回一个ResultSet"""
        sql = f"""desc {db_name}.{tb_name}"""
        result = self.query(db_name=db_name, sql=sql)
        column_list = [row[0] for row in result.rows]
        result.rows = column_list
        return result

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
        if re.match(r"^select|^show|^explain", sql, re.I) is None:
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
        # 不应该查看doris用户信息
        if re.match("authentication|grants|roles|users", sql.lower().replace("\n", ""), re.I):
            result["bad_query"] = True
            result["msg"] = "您无权查看该表"

        return result

    def execute_check(self, db_name=None, sql=""):
        """上线单执行前的检查, 返回Review set"""
        check_result = ReviewSet(full_sql=sql)
        # 禁用/高危语句检查
        line = 1
        critical_ddl_regex = self.config.get("critical_ddl_regex", "")
        p = re.compile(critical_ddl_regex)
        check_result.syntax_type = 2  # TODO 工单类型 0、其他 1、DDL，2、DML
        for statement in sqlparse.split(sql):
            statement = sqlparse.format(statement, strip_comments=True)
            # 禁用语句
            if re.match(r"^select|^show|^explain", statement.lower()):
                result = ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="驳回不支持语句",
                    errormessage="仅支持DML和DDL语句，查询语句请使用SQL查询功能！",
                    sql=statement,
                )
            # 高危语句
            elif critical_ddl_regex and p.match(statement.strip().lower()):
                result = ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="驳回高危SQL",
                    errormessage="禁止提交匹配" + critical_ddl_regex + "条件的语句！",
                    sql=statement,
                )
            # 驳回未带where数据修改语句，如确实需做全部删除或更新，显示的带上where 1=1
            elif re.match(
                r"^update((?!where).)*$|^delete((?!where).)*$", statement.lower()
            ):
                result = ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="驳回未带where数据修改",
                    errormessage="数据修改需带where条件！",
                    sql=statement,
                )
            # 正常语句
            else:
                result = ReviewResult(
                    id=line,
                    errlevel=0,
                    stagestatus="Audit completed",
                    errormessage="None",
                    sql=statement,
                    affected_rows=0,
                    execute_time=0,
                )
            # 判断工单类型
            if get_syntax_type(statement) == "DDL":
                check_result.syntax_type = 1
            check_result.rows += [result]
            line += 1
        # 统计警告和错误数量
        for r in check_result.rows:
            if r.errlevel == 1:
                check_result.warning_count += 1
            if r.errlevel == 2:
                check_result.error_count += 1
        return check_result

    def execute_workflow(self, workflow):
        return self.execute(
            db_name=workflow.db_name, sql=workflow.sqlworkflowcontent.sql_content
        )

    def execute(self, db_name=None, sql="", close_conn=True):
        """执行sql语句 返回 Review set"""
        execute_result = ReviewSet(full_sql=sql)
        conn = self.get_connection(db_name=db_name)
        rowid = 1
        effect_row = 0
        sql_list = sqlparse.split(sql)
        for statement in sql_list:
            try:
                cursor = conn.cursor()
                with FuncTimer() as t:
                    effect_row = cursor.execute(statement)
                cursor.close()
                execute_result.rows.append(
                    ReviewResult(
                        id=rowid,
                        errlevel=0,
                        stagestatus="Execute Successfully",
                        errormessage="None",
                        sql=statement,
                        affected_rows=effect_row,
                        execute_time=t.cost,
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
                        affected_rows=effect_row,
                        execute_time=t.cost,
                    )
                )
                break
            rowid += 1
        if execute_result.error:
            for statement in sql_list[rowid:]:
                execute_result.rows.append(
                    ReviewResult(
                        id=rowid + 1,
                        errlevel=2,
                        stagestatus="Audit Completed",
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