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
from sql.utils.data_masking import brute_mask
from common.config import SysConfig
from sql.models import SqlBackupHistory
import json

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
                autoCommit=True
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

            # Attempt to set schema for the current session/cursor if db_name is provided.
            if db_name:
                try:
                    set_schema_sql = f"SET SCHEMA {db_name.upper()}" # Common syntax, VERIFY FOR DAMENG
                    logger.debug(f"Attempting to set Dameng schema: {set_schema_sql}")
                    cursor.execute(set_schema_sql)
                    logger.info(f"Dameng session schema set to {db_name.upper()} for current query execution.")
                except Exception as schema_err:
                    logger.warning(f"Failed to set schema '{db_name.upper()}' for Dameng query. Error: {schema_err}. Query will proceed.")

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

        # Get connection for validation
        conn = None
        try:
            conn = self.get_connection(db_name=db_name)

            line_num = 1
            for stmt in statements:
                s = stmt.strip()
                if not s:
                    continue

                review_result = ReviewResult(
                    id=line_num, errlevel=0, stagestatus="Audit completed",
                    errormessage="None", sql=s, affected_rows=0, execute_time=0
                )

                # Existing checks
                if re.match(r"^SELECT", s, re.IGNORECASE):
                    review_result.errlevel = 2
                    review_result.stagestatus = "Rejected"
                    review_result.errormessage = "SELECT statements not allowed in execution workflows."
                elif p_critical and p_critical.match(s):
                    review_result.errlevel = 2
                    review_result.stagestatus = "Rejected"
                    review_result.errormessage = f"Statement matches critical DDL regex."

                # New Dameng validation logic for INSERT, UPDATE, DELETE
                # Only perform this check if no other error was found yet
                if review_result.errlevel == 0:
                    stmt_type = sqlparse.parse(s)[0].get_type()
                    if stmt_type in ('INSERT', 'UPDATE', 'DELETE'):
                        cursor = None
                        try:
                            # Use EXPLAIN FOR to validate syntax and object existence without execution
                            explain_sql = f"EXPLAIN FOR {s}"
                            cursor = conn.cursor()
                            cursor.execute(explain_sql)
                            cursor.fetchall()  # Consume results to ensure check is complete
                        except Exception as e:
                            logger.warning(f"Dameng syntax check failed for statement: {s}\nError: {traceback.format_exc()}")
                            review_result.errlevel = 2
                            review_result.stagestatus = "Rejected"
                            review_result.errormessage = f"达梦语法或字段有效性检查失败: {e}"
                        finally:
                            if cursor:
                                cursor.close()

                if review_result.errlevel == 2:
                    review_set.error_count += 1
                elif review_result.errlevel == 1:
                    review_set.warning_count += 1

                review_set.rows.append(review_result)
                line_num += 1

        except Exception as e:
            logger.error(f"Error during Dameng execute_check connection/setup: {traceback.format_exc()}")
            review_set.error = f"连接达梦数据库失败: {e}"
            review_set.error_count = len([s for s in statements if s.strip()])
            line_num = 1
            for stmt in statements:
                s = stmt.strip()
                if not s: continue
                review_set.rows.append(ReviewResult(
                    id=line_num, sql=s, errlevel=2, stagestatus="Audit failed",
                    errormessage=f"连接达梦数据库失败: {e}"
                ))
                line_num += 1
        finally:
            if conn:
                self.close()

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
            # Set autocommit to False to control transaction manually

            # Backup logic starts here
            if workflow.is_backup:
                try:
                    logger.info(f"Workflow ID {workflow.id}: Backup option is enabled. Starting backup process.")
                    backup_cursor = conn.cursor()
                    for stmt in statements:
                        s = stmt.strip()
                        if not s:
                            continue

                        parsed = sqlparse.parse(s)[0]
                        stmt_type = parsed.get_type()

                        if stmt_type in ('UPDATE', 'DELETE'):
                            table_name = None
                            where_clause = ""

                            # Extract table name
                            from_seen = False
                            update_seen = False
                            for t in parsed.tokens:
                                if t.is_keyword and t.normalized == 'FROM':
                                    from_seen = True
                                    continue
                                if t.is_keyword and t.normalized == 'UPDATE':
                                    update_seen = True
                                    continue
                                if (from_seen or update_seen) and isinstance(t, sqlparse.sql.Identifier):
                                    table_name = t.get_real_name()
                                    break

                            # Extract where clause
                            where_token = next((t for t in parsed.tokens if isinstance(t, sqlparse.sql.Where)), None)
                            if where_token:
                                where_clause = where_token.value

                            if table_name:
                                backup_sql = f"SELECT * FROM {table_name} {where_clause}"
                                logger.info(f"Executing backup query for workflow {workflow.id}: {backup_sql}")
                                backup_cursor.execute(backup_sql)
                                rows = backup_cursor.fetchall()
                                if rows:
                                    columns = [desc[0] for desc in backup_cursor.description]
                                    backup_data = [dict(zip(columns, row)) for row in rows]

                                    # Save to backup history
                                    SqlBackupHistory.objects.create(
                                        workflow=workflow,
                                        table_name=table_name,
                                        sql_statement=s,
                                        backup_data=backup_data
                                    )
                                    logger.info(f"Backed up {len(rows)} rows from {table_name} for workflow {workflow.id}")
                    backup_cursor.close()
                except Exception as e:
                    logger.error(f"Backup failed for workflow {workflow.id}. Error: {traceback.format_exc()}")
                    execute_result_set.error = f"数据备份失败: {e}"
                    execute_result_set.error_count = 1
                    for idx, stmt_text_for_error in enumerate(statements):
                        st_err = stmt_text_for_error.strip()
                        if not st_err: continue
                        execute_result_set.rows.append(ReviewResult(
                            id=idx + 1, sql=st_err, errlevel=2, stagestatus="Execute Failed",
                            errormessage=f"数据备份失败: {e}"
                        ))
                    conn.rollback()
                    return execute_result_set

            # Attempt to set schema for the current session if db_name is provided
            cursor = conn.cursor()
            if db_name:
                try:
                    set_schema_sql = f"SET SCHEMA {db_name.upper()}"
                    logger.debug(f"Attempting to set Dameng schema for workflow: {set_schema_sql}")
                    cursor.execute(set_schema_sql)
                    logger.info(f"Dameng session schema set to {db_name.upper()} for workflow execution.")
                except Exception as schema_err:
                    logger.error(f"CRITICAL: Failed to set schema '{db_name.upper()}' for Dameng workflow. Error: {schema_err}")
                    execute_result_set.error = f"Failed to set schema '{db_name.upper()}': {schema_err}"
                    # Populate error for all statements
                    for idx, stmt_text_for_error in enumerate(statements):
                        st_err = stmt_text_for_error.strip()
                        if not st_err: continue
                        execute_result_set.rows.append(ReviewResult(
                            id=idx + 1, sql=st_err, errlevel=2, stagestatus="Execute Failed",
                            errormessage=f"Failed to set schema '{db_name.upper()}': {schema_err}"
                        ))
                    conn.rollback()
                    return execute_result_set

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
                    # Add failed result and break loop
                    execute_result_set.rows.append(review_result)
                    line_num += 1
                    # Mark subsequent statements as not executed
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

            # After loop, commit or rollback
            if execute_result_set.error_count == 0:
                logger.info(f"Workflow ID {workflow.id}: All statements executed successfully. Committing transaction.")
                conn.commit()
            else:
                logger.warning(f"Workflow ID {workflow.id}: Errors occurred. Rolling back transaction.")
                conn.rollback()

        except Exception as e:
            logger.error(f"Dameng workflow connection/setup/backup failed. DB: {db_name}. Error: {e}\n{traceback.format_exc()}")
            execute_result_set.error = f"Workflow failed: {str(e)}"
            if not execute_result_set.rows: # If error before any statement processing
                 for idx, stmt_text in enumerate(statements):
                    st = stmt_text.strip()
                    if not st: continue
                    execute_result_set.rows.append(ReviewResult(
                        id=idx + 1, sql=st, errlevel=2, stagestatus="Execute Failed",
                        errormessage=f"Connection/setup/backup error: {str(e)}"
                    ))
            if conn:
                try:
                    conn.rollback()
                except Exception as rb_err:
                    logger.error(f"Error during rollback attempt after workflow failure: {rb_err}")
        finally:
            if cursor:
                try: cursor.close()
                except Exception: pass
            if conn:
                # Restore autocommit state and close
                self.close()

        return execute_result_set

    def get_rollback(self, workflow):
        """
        获取回滚语句
        """
        # NOTE: This method constructs rollback SQL strings manually and might not handle all data types correctly (e.g., dates, binary data).
        # It assumes that primary keys are not updated.
        # 获取备份历史
        backup_history = SqlBackupHistory.objects.filter(workflow=workflow)
        if not backup_history:
            return []

        rollback_sql_list = []
        for history in backup_history:
            original_sql = history.sql_statement
            parsed = sqlparse.parse(original_sql)[0]
            stmt_type = parsed.get_type()
            table_name = history.table_name
            backup_data = json.loads(history.backup_data)

            if stmt_type == 'DELETE':
                for row in backup_data:
                    columns = ", ".join(row.keys())
                    values = ", ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in row.values()])
                    rollback_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({values});"
                    rollback_sql_list.append([original_sql, rollback_sql])
            elif stmt_type == 'UPDATE':
                # 获取主键
                primary_key = self._get_primary_key(workflow.db_name, table_name)
                if not primary_key:
                    raise Exception(f"无法找到表 {table_name} 的主键，无法生成UPDATE回滚语句。")

                for row in backup_data:
                    set_clause = ", ".join([f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}" for k, v in row.items() if k != primary_key])
                    where_clause = f"{primary_key} = '{row[primary_key]}'" if isinstance(row[primary_key], str) else f"{primary_key} = {row[primary_key]}"
                    rollback_sql = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause};"
                    rollback_sql_list.append([original_sql, rollback_sql])
        return rollback_sql_list

    def _get_primary_key(self, db_name, tb_name):
        """
        获取表的主键
        """
        sql = f"SELECT COLUMN_NAME FROM ALL_CONSTRAINTS C, ALL_CONS_COLUMNS CC WHERE C.CONSTRAINT_NAME = CC.CONSTRAINT_NAME AND C.CONSTRAINT_TYPE = 'P' AND C.OWNER = '{db_name.upper()}' AND C.TABLE_NAME = '{tb_name.upper()}'"
        result = self.query(db_name=db_name, sql=sql)
        if result.rows:
            return result.rows[0][0]
        return None

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
