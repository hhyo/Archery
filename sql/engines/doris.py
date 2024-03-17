# -*- coding: UTF-8 -*-
from sql.utils.sql_utils import get_syntax_type, remove_comments
from sql.engines.mysql import MysqlEngine
from .models import ResultSet, ReviewResult, ReviewSet
from common.utils.timer import FuncTimer
from common.config import SysConfig
from MySQLdb.constants import FIELD_TYPE
import traceback
import MySQLdb
import pymysql
import sqlparse
import logging
import re


logger = logging.getLogger("default")


class DorisEngine(MysqlEngine):
    name = "Doris"
    info = "Doris engine"

    auto_backup = False

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

    forbidden_databases = [
        "__internal_schema",
        "INFORMATION_SCHEMA",
        "information_schema",
    ]

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
