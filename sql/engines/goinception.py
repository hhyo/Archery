# -*- coding: UTF-8 -*-
import logging
import re
import traceback
import MySQLdb

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
            self.conn = MySQLdb.connect(host=self.host, port=self.port, charset=self.instance.charset or 'utf8mb4',
                                        connect_timeout=10)
            return self.conn
        archer_config = SysConfig()
        go_inception_host = archer_config.get('go_inception_host')
        go_inception_port = int(archer_config.get('go_inception_port', 4000))
        self.conn = MySQLdb.connect(host=go_inception_host, port=go_inception_port, charset='utf8mb4',
                                    connect_timeout=10)
        return self.conn

    def execute_check(self, instance=None, db_name=None, sql=''):
        """inception check"""
        check_result = ReviewSet(full_sql=sql)
        # inception 校验
        check_result.rows = []
        inception_sql = f"""/*--user='{instance.user}';--password='{instance.password}';--host='{instance.host}';--port={instance.port};--check=1;*/
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
        sql_execute = f"""/*--user='{instance.user}';--password='{instance.password}';--host='{instance.host}';--port={instance.port};--execute=1;--ignore-warnings=1;{str_backup};--sleep=200;--sleep_rows=100*/
                            inception_magic_start;
                            use `{workflow.db_name}`;
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
            logger.warning(f'goInception语句执行报错，错误信息{traceback.format_exc()}')
            result_set.error = str(e)
        if close_conn:
            self.close()
        return result_set

    def query_print(self, instance, db_name=None, sql=''):
        """
        打印语法树。
        """
        sql = f"""/*--user='{instance.user}';--password='{instance.password}';--host='{instance.host}';--port={instance.port};--enable-query-print;*/
                          inception_magic_start;\
                          use `{db_name}`;
                          {sql.rstrip(';')};
                          inception_magic_commit;"""
        print_info = self.query(db_name=db_name, sql=sql).to_dict()[1]
        if print_info.get('errmsg'):
            raise RuntimeError(print_info.get('errmsg'))
        return print_info

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

    @staticmethod
    def get_table_ref(query_tree, db_name=None):
        __author__ = 'xxlrr'
        """
        * 从goInception解析后的语法树里解析出兼容Inception格式的引用表信息。
        * 目前的逻辑是在SQL语法树中通过递归查找选中最小的 TableRefs 子树（可能有多个），
        然后在最小的 TableRefs 子树选中Source节点来获取表引用信息。
        * 查找最小TableRefs子树的方案竟然是通过逐步查找最大子树（直到找不到）来获得的，
        具体为什么这样实现，我不记得了，只记得当时是通过猜测goInception的语法树生成规
        则来写代码，结果猜一次错一次错一次猜一次，最终代码逐渐演变于此。或许直接查找最
        小子树才是效率较高的算法，但是就这样吧，反正它能运行 :)
        """
        table_ref = []

        find_queue = [query_tree]
        for tree in find_queue:
            tree = DictTree(tree)

            # nodes = tree.find_max_tree("TableRefs") or tree.find_max_tree("Left", "Right")
            nodes = tree.find_max_tree("TableRefs")
            if nodes:
                # assert isinstance(v, dict) is true
                find_queue.extend([v for node in nodes for v in node.values() if v])
            else:
                snodes = tree.find_max_tree("Source")
                if snodes:
                    table_ref.extend([
                        {
                            "schema": snode['Source']['Schema']['O'] or db_name,
                            "name": snode['Source']['Name']['O']
                        } for snode in snodes
                    ])
                # assert: source node must exists if table_refs node exists.
                # else:
                #     raise Exception("GoInception Error: not found source node")
        return table_ref

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None


class DictTree(dict):
    def find_max_tree(self, *keys):
        __author__ = 'xxlrr'
        """通过广度优先搜索算法查找满足条件的最大子树(不找叶子节点)"""
        fit = []
        find_queue = [self]
        for tree in find_queue:
            for k, v in tree.items():
                if k in keys:
                    fit.append({k: v})
                elif isinstance(v, dict):
                    find_queue.append(v)
                elif isinstance(v, list):
                    find_queue.extend([n for n in v if isinstance(n, dict)])
        return fit
