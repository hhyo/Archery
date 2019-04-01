# -*- coding: UTF-8 -*-
import logging
import re
import traceback
import MySQLdb
import simplejson as json
import sqlparse
from django.db import connection, OperationalError

from common.config import SysConfig
from sql.models import SqlWorkflow
from sql.utils.sql_utils import get_syntax_type
from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult

logger = logging.getLogger('default')


class InceptionEngine(EngineBase):
    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        archer_config = SysConfig()
        inception_host = archer_config.get('inception_host')
        inception_port = int(archer_config.get('inception_port', 6669))
        self.conn = MySQLdb.connect(host=inception_host, port=inception_port, charset='utf8')
        return self.conn

    @staticmethod
    def get_backup_connection():
        archer_config = SysConfig()
        backup_host = archer_config.get('inception_remote_backup_host')
        backup_port = int(archer_config.get('inception_remote_backup_port', 3306))
        backup_user = archer_config.get('inception_remote_backup_user')
        backup_password = archer_config.get('inception_remote_backup_password')
        return MySQLdb.connect(host=backup_host,
                               port=backup_port,
                               user=backup_user,
                               passwd=backup_password,
                               charset='utf8')

    def execute_check(self, instance=None, db_name=None, sql=''):
        """inception check"""
        check_result = ReviewSet(full_sql=sql)
        # 检查 inception 不支持的函数
        check_result.rows = []
        line = 1
        for statement in sqlparse.split(sql):
            # 删除注释语句
            statement = sqlparse.format(statement, strip_comments=True)
            if re.match(r"(\s*)alter(\s+)table(\s+)(\S+)(\s*);|(\s*)alter(\s+)table(\s+)(\S+)\.(\S+)(\s*);",
                        statement.lower() + ";"):
                result = ReviewSet(
                    id=line, errlevel=2, stagestatus='SQL语法错误',
                    errormessage='ALTER TABLE 必须带有选项',
                    sql=statement)
                check_result.is_critical = True
            else:
                result = ReviewSet(id=line, errlevel=0, sql=statement)
            check_result.rows += [result]
            line += 1
        if check_result.is_critical:
            return check_result

        # inception 校验
        check_result.rows = []
        inception_sql = f"""/*--user={instance.user};--password={instance.raw_password};--host={instance.host};
                            --port={instance.port};--enable-check=1;*/
                            inception_magic_start;
                            use {db_name};
                            {sql}
                            inception_magic_commit;"""
        inception_engine = InceptionEngine()
        inception_result = inception_engine.query(sql=inception_sql)
        check_result.syntax_type = 2  # TODO 工单类型 1、DDL，2、DML 仅适用于MySQL，待调整
        for r in inception_result.rows:
            check_result.rows += [ReviewResult(inception_result=r)]
            if r[2] == 1:  # 警告
                check_result.warning_count += 1
            elif r[2] == 2 or re.match(r"\w*comments\w*", r[4], re.I):  # 错误
                check_result.error_count += 1
            if get_syntax_type(r[5]) == 'DDL':
                check_result.syntax_type = 1
        check_result.column_list = inception_result.column_list
        check_result.checked = True
        return check_result

    def execute(self, workflow=None):
        """执行上线单"""
        instance = workflow.instance
        execute_result = ReviewSet(full_sql=workflow.sqlworkflowcontent.sql_content)
        inception_engine = InceptionEngine()
        if workflow.is_backup == '是':
            str_backup = "--enable-remote-backup"
        else:
            str_backup = "--disable-remote-backup"
        # 根据inception的要求，执行之前最好先split一下
        sql_split = f"""/*--user={instance.user};--password={instance.raw_password};--host={instance.host}; 
                         --port={instance.port};--enable-ignore-warnings;--enable-split;*/
                         inception_magic_start;
                         use {workflow.db_name};
                         {workflow.sqlworkflowcontent.sql_content}
                         inception_magic_commit;"""
        split_result = inception_engine.query(sql=sql_split)

        execute_result.rows = []
        # 对于split好的结果，再次交给inception执行，保持长连接里执行.
        for splitRow in split_result.rows:
            sql_tmp = splitRow[1]
            sql_execute = f"""/*--user={instance.user};--password={instance.raw_password};--host={instance.host};
                                --port={instance.port};--enable-execute;--enable-ignore-warnings;{str_backup};*/\
                                inception_magic_start;\
                                {sql_tmp}\
                                inception_magic_commit;"""
            one_line_execute_result = inception_engine.query(sql=sql_execute, close_conn=False)
            # 执行, 把结果转换为ReviewSet
            for sqlRow in one_line_execute_result.to_dict():
                execute_result.rows.append(ReviewResult(
                    id=sqlRow['ID'],
                    stage=sqlRow['stage'],
                    errlevel=sqlRow['errlevel'],
                    stagestatus=sqlRow['stagestatus'],
                    errormessage=sqlRow['errormessage'],
                    sql=sqlRow['SQL'],
                    affected_rows=sqlRow['Affected_rows'],
                    actual_affected_rows=sqlRow['Affected_rows'],
                    sequence=sqlRow['sequence'],
                    backup_dbname=sqlRow['backup_dbname'],
                    execute_time=sqlRow['execute_time'],
                    sqlsha1=sqlRow['sqlsha1']))

            # 每执行一次，就将执行结果更新到工单的execute_result，便于展示执行进度和保存执行信息
            workflow.sqlworkflowcontent.execute_result = execute_result.json()
            try:
                workflow.sqlworkflowcontent.save()
                workflow.save()
            # 防止执行超时
            except OperationalError:
                connection.close()
                workflow.sqlworkflowcontent.save()
                workflow.save()

        # 如果发现任何一个行执行结果里有errLevel为1或2，并且stagestatus列没有包含Execute Successfully字样，则最终执行结果为有异常.
        execute_result.status = "workflow_finish"
        for sqlRow in execute_result.rows:
            if sqlRow.errlevel in (1, 2) and re.match(r"\w*Execute Successfully\w*", sqlRow.stagestatus) is None:
                execute_result.status = "workflow_exception"
                execute_result.error = "Line {0} has error/warning: {1}".format(sqlRow.id, sqlRow.errormessage)
                break
        return execute_result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        conn = self.get_connection()
        with conn.cursor() as cursor:
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
            result_set.column_list = column_list
            result_set.rows = rows
            result_set.affected_rows = effect_row
        if close_conn:
            self.close()
        return result_set

    def query_print(self, instance, db_name=None, sql=''):
        """
        将sql交给inception打印语法树。
        """
        sql = f"""/*--user={instance.user};--password={instance.raw_password};--host={instance.host};
                          --port={instance.port};--enable-query-print;*/
                          inception_magic_start;\
                          use {db_name};
                          {sql}
                          inception_magic_commit;"""
        print_info = self.query(db_name=db_name, sql=sql).to_dict()[0]
        # 兼容语法错误时errlevel=0的场景
        if print_info['errlevel'] == 0 and print_info['errmsg'] == 'None':
            return json.loads(_repair_json_str(print_info['query_tree']))
        elif print_info['errlevel'] == 0 and print_info['errmsg']:
            raise RuntimeError(f"Inception Error: {print_info['query_tree']}")
        else:
            raise RuntimeError(f"Inception Error: {print_info['errmsg']}")

    def get_rollback_list(self, workflow_id):
        """
        获取回滚语句，并且按照执行顺序倒序展示
        """
        workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
        list_execute_result = json.loads(workflow_detail.sqlworkflowcontent.execute_result)
        list_execute_result.reverse()
        list_backup_sql = []
        # 创建连接
        conn = self.get_backup_connection()
        cur = conn.cursor()
        for row in list_execute_result:
            try:
                # 获取backup_db_name， 兼容旧数据'[[]]'格式
                if isinstance(row, list):
                    if row[8] == 'None':
                        continue
                    backup_db_name = row[8]
                    sequence = row[7]
                    sql = row[5]
                else:
                    if row.get('backup_dbname') == 'None':
                        continue
                    backup_db_name = row.get('backup_dbname')
                    sequence = row.get('sequence')
                    sql = row.get('sql')
                opid_time = sequence.replace("'", "")
                sql_table = f"""select tablename 
                                    from {backup_db_name}.$_$Inception_backup_information$_$ 
                                 where opid_time='{opid_time}';"""
                cur.execute(sql_table)
                list_tables = cur.fetchall()
                if list_tables:
                    table_name = list_tables[0][0]
                    sql_back = f"""select rollback_statement 
                                       from {backup_db_name}.{table_name} 
                                    where opid_time='{opid_time}'"""
                    cur.execute(sql_back)
                    list_backup = cur.fetchall()
                    block_rollback_sql_list = [sql]
                    block_rollback_sql = '\n'.join([back_info[0] for back_info in list_backup])
                    block_rollback_sql_list.append(block_rollback_sql)
                    list_backup_sql.append(block_rollback_sql_list)
            except Exception as e:
                logger.error(f"获取回滚语句报错，异常信息{traceback.format_exc()}")
                raise Exception(e)
        return list_backup_sql

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None


def _repair_json_str(json_str):
    """
    处理JSONDecodeError: Expecting property name enclosed in double quotes
    inception语法树出现{"a":1,}、["a":1,]、{'a':1}、[, { }]
    """
    json_str = re.sub(r"{\s*'(.+)':", r'{"\1":', json_str)
    json_str = re.sub(r",\s*?]", "]", json_str)
    json_str = re.sub(r",\s*?}", "}", json_str)
    json_str = re.sub(r"\[,\s*?{", "[{", json_str)
    json_str = json_str.replace("'", "\"")
    return json_str
