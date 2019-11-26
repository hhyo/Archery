# -*- coding: UTF-8 -*-
import asyncio
import logging
import re
import traceback

from common.config import SysConfig
from sql.utils.async_tasks import async_tasks
from sql.utils.sql_conn import setup_conn, shutdown_conn
from sql.utils.sql_utils import get_syntax_type
from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult

logger = logging.getLogger('default')


class GoInceptionEngine(EngineBase):
    def get_connection(self, db_name=None, **kwargs):
        if self.pool: return self.pool
        if hasattr(self, 'instance'):
            if db_name:
                self.pool = setup_conn(self.host,
                                       self.port,
                                       user=self.user,
                                       password=self.password,
                                       database=db_name,
                                       charset=self.instance.charset or 'utf8mb4',
                                       connect_timeout=10,
                                       **kwargs)
            else:
                self.pool = setup_conn(self.host,
                                       self.port,
                                       user=self.user,
                                       password=self.password,
                                       charset=self.instance.charset or 'utf8mb4',
                                       connect_timeout=10,
                                       **kwargs)
        else:
            archer_config = SysConfig()
            go_inception_host = archer_config.get('go_inception_host')
            go_inception_port = int(archer_config.get('go_inception_port', 4000))
            self.pool = setup_conn(
                go_inception_host,
                go_inception_port,
                charset='utf8mb4',
                connect_timeout=10,
                use_unicode=True)
        return self.pool

    def execute_check(self, instance=None, db_name=None, sql=''):
        """inception check"""
        check_result = ReviewSet(full_sql=sql)
        # inception 校验
        check_result.rows = []
        inception_sql = f"""/*--user={instance.user};--password={instance.password};--host={instance.host};--port={instance.port};--check=1;*/
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
        db_names = []
        if workflow.db_name:
            db_names.append(workflow.db_name)

        global execute_result

        # 异步执行
        asyncio.run(async_tasks(self.execute_sql, db_names, instance, workflow))
        logger.info("Debug execute result in goinception execute func {0}".format(execute_result))
        return execute_result

    async def execute_sql(self, db_name, instance, workflow):
        # 结果写入全局变量
        global execute_result
        execute_result = ReviewSet(full_sql=workflow.sqlworkflowcontent.sql_content)
        if workflow.is_backup:
            str_backup = "--backup=1"
        else:
            str_backup = "--backup=0"

        # 提交inception执行
        sql_execute = f"""/*--user={instance.user};--password={instance.password};--host={instance.host};--port={instance.port};--execute=1;--ignore-warnings=1;{str_backup};*/
                            inception_magic_start;
                            use `{db_name}`;
                            {workflow.sqlworkflowcontent.sql_content.rstrip(';')};
                            inception_magic_commit;"""
        inception_result = self.query(sql=sql_execute)

        # 执行报错，inception crash或者执行中连接异常的场景
        if inception_result.error and not execute_result.rows:
            execute_result.error = inception_result.error
            execute_result.rows = [ReviewResult(
                stage='Execute failed',
                errlevel=2,
                stagestatus='异常终止',
                errormessage=f'goInception Error: {inception_result.error}',
                sql=workflow.sqlworkflowcontent.sql_content)]
            return execute_result

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
        # conn = self.get_connection()
        # 从连接池获取数据库连接
        if db_name:
            pool = self.get_connection(db_name=db_name, use_unicode=True)
        else:
            pool = self.get_connection(use_unicode=True)
        try:
            conn = pool.connection()
        except Exception as e:
            logger.error("SQL连接失败，请重试！")
            result_set.error = str(e)
            return result_set
        cursor = conn.cursor()
        try:
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
            logger.warning(f'goInception语句执行报错，语句：{sql}，错误信息{traceback.format_exc()}')
            result_set.error = str(e)
        else:
            cursor.close()
            conn.close()
        if close_conn:
            self.close(pool=pool)
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

    def close(self, pool=None):
        if not pool:
            pool = self.pool
        if pool:
            shutdown_conn(pool=pool)
