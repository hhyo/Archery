# -*- coding: UTF-8 -*-
import logging
import re
import traceback
import pymysql

from common.config import SysConfig
from sql.utils.sql_utils import get_syntax_type
from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult

logger = logging.getLogger('default')


class GoInceptionEngine(EngineBase):
    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        if hasattr(self, 'instance'):
            self.conn = pymysql.connect(host=self.host, port=self.port, charset=self.instance.charset or 'utf8mb4')
            return self.conn
        archer_config = SysConfig()
        go_inception_host = archer_config.get('go_inception_host')
        go_inception_port = int(archer_config.get('go_inception_port', 4000))
        self.conn = pymysql.connect(host=go_inception_host, port=go_inception_port, charset='utf8mb4')
        return self.conn

    def execute_check(self, instance=None, db_name=None, sql=''):
        """inception check"""
        check_result = ReviewSet(full_sql=sql)
        # inception 校验
        check_result.rows = []
        inception_sql = f"""/*--user={instance.user};--password={instance.raw_password};--host={instance.host};--port={instance.port};--check=1;*/
                            inception_magic_start;
                            use `{db_name}`;
                            {sql.rstrip(';')};
                            inception_magic_commit;"""
        inception_result = self.query(sql=inception_sql)
        check_result.syntax_type = 2  # TODO 工单类型 0、其他 1、DDL，2、DML 仅适用于MySQL，待调整
        for r in inception_result.rows:
            check_result.rows += [ReviewResult(inception_result=r)]
            if r[2] == 1:  # 警告
                check_result.warning_count += 1
            elif r[2] == 2:  # 错误
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
            str_backup = "--backup=1"
        else:
            str_backup = "--backup=0"

        # 提交inception执行
        sql_execute = f"""/*--user={instance.user};--password={instance.raw_password};--host={instance.host};--port={instance.port};--execute=1;--ignore-warnings=1;{str_backup};*/
                            inception_magic_start;
                            use `{workflow.db_name}`;
                            {workflow.sqlworkflowcontent.sql_content.rstrip(';')};
                            inception_magic_commit;"""
        inception_result = self.query(sql=sql_execute)
        # 把结果转换为ReviewSet
        for r in inception_result.rows:
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
            logger.error(f'goInception语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}')
            result_set.error = str(e)
        if close_conn:
            self.close()
        return result_set

    def get_variables(self, variables=None):
        """获取实例参数"""
        if variables:
            sql = f"inception get variables like '{variables[0]}';"
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
        else:
            sql = f"inception {command} osc '{sqlsha1}';"
        return self.query(sql=sql)

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
