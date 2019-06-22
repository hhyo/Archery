# -*- coding: UTF-8 -*-
import logging
import re
import traceback
import MySQLdb
import simplejson as json
import sqlparse

from common.config import SysConfig
from sql.utils.sql_utils import get_syntax_type
from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult

logger = logging.getLogger('default')


class InceptionEngine(EngineBase):
    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        if hasattr(self, 'instance'):
            self.conn = MySQLdb.connect(host=self.host, port=self.port, charset=self.instance.charset or 'utf8mb4')
            return self.conn
        archer_config = SysConfig()
        inception_host = archer_config.get('inception_host')
        inception_port = int(archer_config.get('inception_port', 6669))
        self.conn = MySQLdb.connect(host=inception_host, port=inception_port, charset='utf8mb4')
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
                               charset='utf8mb4')

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
                result = ReviewResult(id=line,
                                      errlevel=2,
                                      stagestatus='SQL语法错误',
                                      errormessage='ALTER TABLE 必须带有选项',
                                      sql=statement)
                check_result.is_critical = True
            else:
                result = ReviewResult(id=line, errlevel=0, sql=statement)
            check_result.rows += [result]
            line += 1
        if check_result.is_critical:
            return check_result

        # inception 校验
        check_result.rows = []
        inception_sql = f"""/*--user={instance.user};--password={instance.raw_password};--host={instance.host};
                            --port={instance.port};--enable-check=1;*/
                            inception_magic_start;
                            use `{db_name}`;
                            {sql}
                            inception_magic_commit;"""
        inception_result = self.query(sql=inception_sql)
        check_result.syntax_type = 2  # TODO 工单类型 0、其他 1、DDL，2、DML 仅适用于MySQL，待调整
        for r in inception_result.rows:
            check_result.rows += [ReviewResult(inception_result=r)]
            if r[2] == 1:  # 警告
                check_result.warning_count += 1
            elif r[2] == 2 or re.match(r"\w*comments\w*", r[4], re.I):  # 错误
                check_result.error_count += 1
            # 没有找出DDL语句的才继续执行此判断
            if check_result.syntax_type == 2:
                if get_syntax_type(r[5], parser=False, db_type='mysql') == 'DDL':
                    check_result.syntax_type = 1
        check_result.column_list = inception_result.column_list
        check_result.checked = True
        check_result.error = inception_result.error
        check_result.warning = inception_result.warning
        return check_result

    def execute(self, workflow=None):
        """执行上线单"""
        instance = workflow.instance
        execute_result = ReviewSet(full_sql=workflow.sqlworkflowcontent.sql_content)
        if workflow.is_backup:
            str_backup = "--enable-remote-backup"
        else:
            str_backup = "--disable-remote-backup"
        # 根据inception的要求，执行之前最好先split一下
        sql_split = f"""/*--user={instance.user};--password={instance.raw_password};--host={instance.host}; 
                         --port={instance.port};--enable-ignore-warnings;--enable-split;*/
                         inception_magic_start;
                         use `{workflow.db_name}`;
                         {workflow.sqlworkflowcontent.sql_content}
                         inception_magic_commit;"""
        split_result = self.query(sql=sql_split)

        # 对于split好的结果，再次交给inception执行，保持长连接里执行.
        for splitRow in split_result.rows:
            sql_tmp = splitRow[1]
            sql_execute = f"""/*--user={instance.user};--password={instance.raw_password};--host={instance.host};
                                --port={instance.port};--enable-execute;--enable-ignore-warnings;{str_backup};*/
                                inception_magic_start;
                                {sql_tmp}
                                inception_magic_commit;"""
            one_line_execute_result = self.query(sql=sql_execute, close_conn=False)
            # 把结果转换为ReviewSet
            for r in one_line_execute_result.rows:
                execute_result.rows += [ReviewResult(inception_result=r)]

        # 如果发现任何一个行执行结果里有errLevel为1或2，并且状态列没有包含Execute Successfully，则最终执行结果为有异常.
        for r in execute_result.rows:
            if r.errlevel in (1, 2) and not re.search(r"Execute Successfully", r.stagestatus):
                execute_result.error = "Line {0} has error/warning: {1}".format(r.id, r.errormessage)
                break
        return execute_result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True):
        """返回 ResultSet """
        result_set = ResultSet(full_sql=sql)
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
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
            logger.error(f"Inception语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}")
            result_set.error = str(e)
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
                          use `{db_name}`;
                          {sql}
                          inception_magic_commit;"""
        print_info = self.query(db_name=db_name, sql=sql).to_dict()[0]
        # 兼容语法错误时errlevel=0的场景
        if print_info['errlevel'] == 0 and print_info['errmsg'] == 'None':
            return json.loads(_repair_json_str(print_info['query_tree']))
        elif print_info['errlevel'] == 0 and print_info['errmsg'] == 'Global environment':
            raise SyntaxError(f"Inception Error: {print_info['query_tree']}")
        else:
            raise RuntimeError(f"Inception Error: {print_info['errmsg']}")

    def get_rollback(self, workflow):
        """
        获取回滚语句，并且按照执行顺序倒序展示，return ['源语句'，'回滚语句']
        """
        list_execute_result = json.loads(workflow.sqlworkflowcontent.execute_result)
        # 回滚语句倒序展示
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
                # 新数据
                else:
                    if row.get('backup_dbname') in ('None', ''):
                        continue
                    backup_db_name = row.get('backup_dbname')
                    sequence = row.get('sequence')
                    sql = row.get('sql')
                # 获取备份表名
                opid_time = sequence.replace("'", "")
                sql_table = f"""select tablename 
                                from {backup_db_name}.$_$Inception_backup_information$_$ 
                                where opid_time='{opid_time}';"""

                cur.execute(sql_table)
                list_tables = cur.fetchall()
                if list_tables:
                    # 获取备份语句
                    table_name = list_tables[0][0]
                    sql_back = f"""select rollback_statement 
                                   from {backup_db_name}.{table_name} 
                                   where opid_time='{opid_time}'"""
                    cur.execute(sql_back)
                    list_backup = cur.fetchall()
                    # 拼接成回滚语句列表,['源语句'，'回滚语句']
                    list_backup_sql.append([sql, '\n'.join([back_info[0] for back_info in list_backup])])
            except Exception as e:
                logger.error(f"获取回滚语句报错，异常信息{traceback.format_exc()}")
                raise Exception(e)
        return list_backup_sql

    def get_variables(self, variables=None):
        """获取实例参数"""
        if variables:
            sql = f"inception get variables '{variables[0]}';"
        else:
            sql = "inception get variables;"
        return self.query(sql=sql)

    def set_variable(self, variable_name, variable_value):
        """修改实例参数值"""
        sql = f"""inception set {variable_name}={variable_value};"""
        return self.query(sql=sql)

    def osc_control(self, **kwargs):
        """控制osc执行，获取进度、终止、暂停、恢复等"""
        sqlsha1 = kwargs.get('sqlsha1')
        command = kwargs.get('command')
        if command == 'get':
            sql = f"inception get osc_percent '{sqlsha1}';"
        elif command == 'kill':
            sql = f"inception stop alter '{sqlsha1}';"
        else:
            raise ValueError('pt-osc不支持暂停和恢复，需要停止执行请使用终止按钮！')
        return self.query(sql=sql)

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
