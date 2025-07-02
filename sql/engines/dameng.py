# -*- coding: UTF-8 -*-
import logging
import traceback
import re
import sqlparse
# Import the Dameng Python driver
# Assuming the driver is named 'dmPython' and can be imported as such
# This might need adjustment based on the actual driver name and installation
try:
    import dmPython
except ImportError:
    # Fallback or error handling if dmPython is not available
    # For now, we'll let it raise an error if not found,
    # as it's a core dependency for this engine.
    pass

from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult
from sql.utils.data_masking import brute_mask # Or a more specific masking function if available/needed
from common.config import SysConfig

logger = logging.getLogger("default")

class DamengEngine(EngineBase):
    test_query = "SELECT 1 FROM DUAL"  # DUAL is common in Oracle-like DBs, adjust if DM uses something else

    def get_connection(self, db_name=None):
        """
        Establishes a connection to the Dameng database.
        The connection parameters (host, port, user, password) are expected
        to be available as instance attributes (self.host, self.port, etc.).
        """
        if self.conn:
            return self.conn

        try:
            self.conn = dmPython.connect(
                user=self.user,
                password=self.password,
                host=self.host,
                port=int(self.port),
                autoCommit=False
            )
        except Exception as e:
            logger.error(f"Dameng connection failed for user {self.user} on {self.host}:{self.port}. Error: {e}\n{traceback.format_exc()}")
            raise
        return self.conn

    name = "Dameng"
    info = "Dameng Database Engine"

    @property
    def auto_backup(self):
        return False

    def get_all_databases(self):
        sql = "SELECT USERNAME FROM ALL_USERS WHERE USERNAME NOT IN ('SYS','SYSTEM','SYSDBA','SYSAUDITOR', 'CTLSYS', 'SQLGUARD', 'STREAMAGO', 'REPLSYS', 'SECURITY', 'DSVIEW', 'DBAUDIT', 'ETLTOOL', 'DMHR') ORDER BY USERNAME"
        result = self.query(sql=sql)

        db_list = [row[0] for row in result.rows]
        result.rows = db_list
        return result

    def get_all_tables(self, db_name, **kwargs):
        schema_name = db_name
        sql = f"SELECT TABLE_NAME FROM ALL_TABLES WHERE OWNER = '{schema_name.upper()}' ORDER BY TABLE_NAME"
        result = self.query(db_name=schema_name, sql=sql)
        tb_list = [row[0] for row in result.rows if row[0] not in ["test"]]
        result.rows = tb_list
        return result

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        schema_name = db_name
        sql = f"SELECT COLUMN_NAME FROM ALL_TAB_COLUMNS WHERE OWNER = '{schema_name.upper()}' AND TABLE_NAME = '{tb_name.upper()}' ORDER BY COLUMN_ID"
        result = self.query(db_name=schema_name, sql=sql)
        column_list = [row[0] for row in result.rows]
        result.rows = column_list
        return result

    def describe_table(self, db_name, tb_name, **kwargs):
        schema_name = db_name
        sql = f"""
        SELECT
            COLUMN_NAME,
            DATA_TYPE,
            DATA_LENGTH,
            CHAR_LENGTH,
            DATA_PRECISION,
            DATA_SCALE,
            NULLABLE,
            DATA_DEFAULT
        FROM ALL_TAB_COLUMNS ATC
        WHERE OWNER = '{schema_name.upper()}' AND TABLE_NAME = '{tb_name.upper()}'
        ORDER BY COLUMN_ID
        """
        result = self.query(db_name=schema_name, sql=sql)
        return result

    def query(self, db_name=None, sql="", limit_num=0, close_conn=True, parameters=None, **kwargs):
        result_set = ResultSet(full_sql=sql)
        cursor = None
        conn = None
        try:
            conn = self.get_connection(db_name=db_name)
            cursor = conn.cursor()

            cursor.execute(sql, parameters or [])

            if int(limit_num) > 0:
                rows = cursor.fetchmany(int(limit_num))
            else:
                rows = cursor.fetchall()

            fields = cursor.description
            result_set.column_list = [i[0] for i in fields] if fields else []
            result_set.rows = rows
            result_set.affected_rows = cursor.rowcount

        except Exception as e:
            logger.warning(f"Dameng SQL execution failed. DB: {db_name}, SQL: {sql}. Error: {traceback.format_exc()}")
            result_set.error = str(e)
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception as cur_e:
                    logger.warning(f"Error closing Dameng cursor: {cur_e}")
            if close_conn and conn:
                self.close()
        return result_set

    def query_check(self, db_name=None, sql=""):
        result = {"msg": "", "bad_query": False, "filtered_sql": sql, "has_star": False}
        try:
            clean_sql = sqlparse.format(sql, strip_comments=True)
            statements = sqlparse.split(clean_sql)
            if not statements:
                result["bad_query"] = True
                result["msg"] = "No valid SQL statement found."
                return result

            first_statement = statements[0].strip()
            result["filtered_sql"] = first_statement

            if not re.match(r"^(SELECT|EXPLAIN|SHOW)\s", first_statement, re.IGNORECASE):
                result["bad_query"] = True
                result["msg"] = "Only SELECT, EXPLAIN, or SHOW statements are allowed."

            if "*" in first_statement:
                result["has_star"] = True
                result["msg"] += " Query contains '*' which is discouraged. "
        except Exception as e:
            logger.warning(f"Error during Dameng query_check: {e}")
            result["bad_query"] = True
            result["msg"] = f"Failed to parse/validate query: {str(e)}"
        return result

    def filter_sql(self, sql="", limit_num=0):
        sql = sql.rstrip(";").strip()
        limit_num = int(limit_num)

        if re.match(r"^SELECT", sql, re.IGNORECASE) and limit_num > 0:
            if "ROWNUM" not in sql.upper():
                sql = f"SELECT * FROM ({sql}) WHERE ROWNUM <= {limit_num}"
        return f"{sql};"


    def query_masking(self, db_name=None, sql="", resultset=None):
        if resultset and re.match(r"^SELECT", sql, re.IGNORECASE):
            masked_resultset = brute_mask(self.instance, resultset)
            masked_resultset.is_masked = True
            return masked_resultset
        return resultset

    def execute_check(self, db_name=None, sql=""):
        review_set = ReviewSet(full_sql=sql)
        statements = sqlparse.split(sqlparse.format(sql, strip_comments=True))

        sys_config = SysConfig()
        critical_ddl_regex = sys_config.get("critical_ddl_regex", "")
        p_critical = re.compile(critical_ddl_regex, re.IGNORECASE) if critical_ddl_regex else None

        line_num = 1
        for stmt in statements:
            s = stmt.strip()
            if not s: continue

            review_result = ReviewResult(
                id=line_num, errlevel=0, stagestatus="Audit completed",
                errormessage="None", sql=s, affected_rows=0, execute_time=0
            )

            if re.match(r"^SELECT", s, re.IGNORECASE):
                review_result.errlevel = 2
                review_result.stagestatus = "Rejected"
                review_result.errormessage = "SELECT statements not allowed in execution workflows."
            elif p_critical and p_critical.match(s):
                review_result.errlevel = 2
                review_result.stagestatus = "Rejected"
                review_result.errormessage = f"Statement matches critical DDL regex."

            if review_result.errlevel == 2: review_set.error_count += 1
            elif review_result.errlevel == 1: review_set.warning_count += 1

            review_set.rows.append(review_result)
            line_num += 1

        if review_set.error_count > 0:
            review_set.error = "One or more statements failed audit."
        return review_set

    def execute_workflow(self, workflow):
        sql_content = workflow.sqlworkflowcontent.sql_content
        db_name = workflow.db_name

        execute_result_set = ReviewSet(full_sql=sql_content)
        statements = sqlparse.split(sqlparse.format(sql_content, strip_comments=True))

        conn = None
        cursor = None
        try:
            conn = self.get_connection(db_name=db_name)
            cursor = conn.cursor()

            line_num = 1
            for stmt_idx, stmt in enumerate(statements):
                s = stmt.strip()
                if not s: continue

                review_result = ReviewResult(id=line_num, sql=s)
                try:
                    cursor.execute(s)

                    review_result.errlevel = 0
                    review_result.stagestatus = "Execute Successfully"
                    review_result.errormessage = "None"
                    review_result.affected_rows = cursor.rowcount
                except Exception as e:
                    logger.error(f"Dameng execution error. DB: {db_name}, SQL: {s}\nError: {traceback.format_exc()}")
                    review_result.errlevel = 2
                    review_result.stagestatus = "Execute Failed"
                    review_result.errormessage = str(e)
                    execute_result_set.error_count += 1
                    execute_result_set.error = "Error during workflow execution."

                    execute_result_set.rows.append(review_result)
                    line_num += 1

                    for subsequent_stmt in statements[stmt_idx+1:]:
                        ss = subsequent_stmt.strip()
                        if not ss: continue
                        execute_result_set.rows.append(ReviewResult(
                            id=line_num, sql=ss, errlevel=0, stagestatus="Not Executed",
                            errormessage="Skipped due to previous error.", affected_rows=0, execute_time=0
                        ))
                        line_num +=1
                    break

                execute_result_set.rows.append(review_result)
                line_num += 1
        except Exception as e:
            logger.error(f"Dameng workflow connection/setup failed. DB: {db_name}. Error: {e}\n{traceback.format_exc()}")
            execute_result_set.error = f"Workflow failed: {str(e)}"
            if not execute_result_set.rows:
                 for idx, stmt_text in enumerate(statements):
                    st = stmt_text.strip()
                    if not st: continue
                    execute_result_set.rows.append(ReviewResult(
                        id=idx + 1, sql=st, errlevel=2, stagestatus="Execute Failed",
                        errormessage=f"Connection/setup error: {str(e)}"
                    ))
        finally:
            if cursor:
                try: cursor.close()
                except Exception: pass
            if conn:
                self.close()

        return execute_result_set

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception as e:
                logger.error(f"Error closing Dameng connection: {e}\n{traceback.format_exc()}")
            finally:
                self.conn = None

    def processlist(self, command_type=None, **kwargs):
        sql = "SELECT SESS_ID, SQL_TEXT, STATE, CLIENT_INFO FROM V$SESSIONS WHERE TYPE='USER'"
        if command_type and command_type.upper() == 'NOT SLEEP':
            sql += " AND STATE <> 'IDLE'"
        elif command_type and command_type.upper() != 'ALL':
            pass
        sql += " ORDER BY SESS_ID"
        return self.query(sql=sql, close_conn=True)

    def get_kill_command(self, thread_ids):
        # Dameng: ALTER SYSTEM KILL SESSION 'sid' or 'sid, serial#';
        # Assuming thread_ids are SIDs or list of [SID, SERIAL#]
        # This is a simplified placeholder. Real implementation needs to know format of thread_ids.
        # If thread_ids are just SIDs:
        if not isinstance(thread_ids, list): thread_ids = [thread_ids]
        kill_cmds = []
        for tid in thread_ids:
            if isinstance(tid, (list, tuple)) and len(tid) == 2: # [sid, serial]
                 kill_cmds.append(f"ALTER SYSTEM KILL SESSION '{tid[0]},{tid[1]}';")
            else: # assume tid is just sid
                 kill_cmds.append(f"ALTER SYSTEM KILL SESSION '{tid}';")
        return " ".join(kill_cmds) # Return as a single string of commands or list

    def kill_connection(self, thread_id): # Changed from kill to kill_connection to match EngineBase
        # thread_id might be a single ID or a list.
        # Assuming it's a single SID or a [SID, SERIAL#] list/tuple for this example.
        # The actual execute method would handle a list of commands if get_kill_command returns that.
        # This is a placeholder and needs robust implementation.
        if isinstance(thread_id, (list,tuple)) and len(thread_id) == 2: # [sid, serial]
            kill_sql = f"ALTER SYSTEM KILL SESSION '{thread_id[0]},{thread_id[1]}';"
        else: # assume thread_id is just sid
            kill_sql = f"ALTER SYSTEM KILL SESSION '{thread_id}';"

        # The base EngineBase.execute method is not defined with parameters.
        # We should use self.query or self.execute_workflow for DDL-like commands.
        # Since ALTER SYSTEM is DDL-like and doesn't return rows in the same way as SELECT:
        # We'll use a simplified execute pattern here.
        # This assumes high privileges for the connected user.
        result = ResultSet(full_sql=kill_sql)
        try:
            conn = self.get_connection() # Should connect as a user with kill privileges
            cursor = conn.cursor()
            cursor.execute(kill_sql)
            # No commit needed for ALTER SYSTEM typically.
            result.affected_rows = cursor.rowcount # May not be meaningful
        except Exception as e:
            logger.error(f"Failed to kill Dameng session {thread_id}: {e}\n{traceback.format_exc()}")
            result.error = str(e)
        finally:
            if conn:
                self.close()
        return result
