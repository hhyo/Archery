# -*- coding: UTF-8 -*-
from clickhouse_driver import connect
from sql.utils.sql_utils import get_syntax_type
from .models import ResultSet, ReviewResult, ReviewSet
from common.utils.timer import FuncTimer
from common.config import SysConfig
from . import EngineBase
import sqlparse
import logging
import re

logger = logging.getLogger('default')


class ClickHouseEngine(EngineBase):

    def __init__(self, instance=None):
        super(ClickHouseEngine, self).__init__(instance=instance)
        self.config = SysConfig()

    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        if db_name:
            self.conn = connect(host=self.host, port=self.port, user=self.user, password=self.password,
                                database=db_name, connect_timeout=10)
        else:
            self.conn = connect(host=self.host, port=self.port, user=self.user, password=self.password,
                                connect_timeout=10)
        return self.conn

    @property
    def name(self):
        return 'ClickHouse'

    @property
    def info(self):
        return 'ClickHouse engine'

    @property
    def auto_backup(self):
        """是否支持备份"""
        return False

    @property
    def server_version(self):
        sql = "select value from system.build_options where name = 'VERSION_FULL';"
        result = self.query(sql=sql)
        version = result.rows[0][0].split(' ')[1]
        return tuple([int(n) for n in version.split('.')[:3]])

    def get_table_engine(self, tb_name):
        """获取某个table的engine type"""
        sql = f"""select engine 
                    from system.tables 
                   where database='{tb_name.split('.')[0]}' 
                     and name='{tb_name.split('.')[1]}'"""
        query_result = self.query(sql=sql)
        if query_result.rows:
            result = {'status': 1, 'engine': query_result.rows[0][0]}
        else:
            result = {'status': 0, 'engine': 'None'}
        return result

    def get_all_databases(self):
        """获取数据库列表, 返回一个ResultSet"""
        sql = "show databases"
        result = self.query(sql=sql)
        db_list = [row[0] for row in result.rows
                   if row[0] not in ('system', 'INFORMATION_SCHEMA', 'information_schema', 'datasets')]
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
        sql = f"""select
            name,
            type,
            comment
        from
            system.columns
        where
            database = '{db_name}'
        and table = '{tb_name}';"""
        result = self.query(db_name=db_name, sql=sql)
        column_list = [row[0] for row in result.rows]
        result.rows = column_list
        return result

    def describe_table(self, db_name, tb_name, **kwargs):
        """return ResultSet 类似查询"""
        sql = f"show create table `{tb_name}`;"
        result = self.query(db_name=db_name, sql=sql)

        result.rows[0] = (tb_name,) + (result.rows[0][0].replace('(', '(\n ').replace(',', ',\n '),)
        return result

    def query(self, db_name=None, sql='', limit_num=0, close_conn=True, **kwargs):
        """返回 ResultSet """
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
            logger.warning(f"ClickHouse语句执行报错，语句：{sql}，错误信息{e}")
            result_set.error = str(e).split('Stack trace')[0]
        finally:
            if close_conn:
                self.close()
        return result_set

    def query_check(self, db_name=None, sql=''):
        # 查询语句的检查、注释去除、切分
        result = {'msg': '', 'bad_query': False, 'filtered_sql': sql, 'has_star': False}
        # 删除注释语句，进行语法判断，执行第一条有效sql
        try:
            sql = sqlparse.format(sql, strip_comments=True)
            sql = sqlparse.split(sql)[0]
            result['filtered_sql'] = sql.strip()
        except IndexError:
            result['bad_query'] = True
            result['msg'] = '没有有效的SQL语句'
        if re.match(r"^select|^show|^explain", sql, re.I) is None:
            result['bad_query'] = True
            result['msg'] = '不支持的查询语法类型!'
        if '*' in sql:
            result['has_star'] = True
            result['msg'] = 'SQL语句中含有 * '
        # clickhouse 20.6.3版本开始正式支持explain语法
        if re.match(r"^explain", sql, re.I) and self.server_version < (20, 6, 3):
            result['bad_query'] = True
            result['msg'] = f"当前ClickHouse实例版本低于20.6.3，不支持explain!"
        # select语句先使用Explain判断语法是否正确
        if re.match(r"^select", sql, re.I) and self.server_version >= (20, 6, 3):
            explain_result = self.query(db_name=db_name, sql=f"explain {sql}")
            if explain_result.error:
                result['bad_query'] = True
                result['msg'] = explain_result.error

        return result

    def filter_sql(self, sql='', limit_num=0):
        # 对查询sql增加limit限制,limit n 或 limit n,n 或 limit n offset n统一改写成limit n
        sql = sql.rstrip(';').strip()
        if re.match(r"^select", sql, re.I):
            # LIMIT N
            limit_n = re.compile(r'limit\s+(\d+)\s*$', re.I)
            # LIMIT M OFFSET N
            limit_offset = re.compile(r'limit\s+(\d+)\s+offset\s+(\d+)\s*$', re.I)
            # LIMIT M,N
            offset_comma_limit = re.compile(r'limit\s+(\d+)\s*,\s*(\d+)\s*$', re.I)
            if limit_n.search(sql):
                sql_limit = limit_n.search(sql).group(1)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = limit_n.sub(f'limit {limit_num};', sql)
            elif limit_offset.search(sql):
                sql_limit = limit_offset.search(sql).group(1)
                sql_offset = limit_offset.search(sql).group(2)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = limit_offset.sub(f'limit {limit_num} offset {sql_offset};', sql)
            elif offset_comma_limit.search(sql):
                sql_offset = offset_comma_limit.search(sql).group(1)
                sql_limit = offset_comma_limit.search(sql).group(2)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = offset_comma_limit.sub(f'limit {sql_offset},{limit_num};', sql)
            else:
                sql = f'{sql} limit {limit_num};'
        else:
            sql = f'{sql};'
        return sql

    def explain_check(self, check_result, db_name=None, line=0, statement=''):
        """使用explain ast检查sql语法, 返回Review set"""
        result = ReviewResult(id=line, errlevel=0,
                              stagestatus='Audit completed',
                              errormessage='None',
                              sql=statement,
                              affected_rows=0,
                              execute_time=0, )
        # clickhouse版本>=21.1.2 explain ast才支持非select语句检查
        if self.server_version >= (21, 1, 2):
            explain_result = self.query(db_name=db_name, sql=f"explain ast {statement}")
            if explain_result.error:
                result = ReviewResult(id=line, errlevel=2,
                                      stagestatus='驳回未通过检查SQL',
                                      errormessage=f'explain语法检查错误：{explain_result.error}',
                                      sql=statement)
        return result

    def execute_check(self, db_name=None, sql=''):
        """上线单执行前的检查, 返回Review set"""
        sql = sqlparse.format(sql, strip_comments=True)
        sql_list = sqlparse.split(sql)

        # 禁用/高危语句检查
        check_result = ReviewSet(full_sql=sql)
        line = 1
        critical_ddl_regex = self.config.get('critical_ddl_regex', '')
        p = re.compile(critical_ddl_regex)
        check_result.syntax_type = 2  # TODO 工单类型 0、其他 1、DDL，2、DML

        for statement in sql_list:
            statement = statement.rstrip(';')
            # 禁用语句
            if re.match(r"^select|^show", statement.lower()):
                result = ReviewResult(id=line, errlevel=2,
                                      stagestatus='驳回不支持语句',
                                      errormessage='仅支持DML和DDL语句，查询语句请使用SQL查询功能！',
                                      sql=statement)
            # 高危语句
            elif critical_ddl_regex and p.match(statement.strip().lower()):
                result = ReviewResult(id=line, errlevel=2,
                                      stagestatus='驳回高危SQL',
                                      errormessage='禁止提交匹配' + critical_ddl_regex + '条件的语句！',
                                      sql=statement)
            # alter语句
            elif re.match(r"^alter", statement.lower()):
                # alter table语句
                if re.match(r"^alter\s+table\s+(.+?)\s+", statement.lower()):
                    table_name = re.match(r"^alter\s+table\s+(.+?)\s+", statement.lower(), re.M).group(1)
                    if '.' not in table_name:
                        table_name = f"{db_name}.{table_name}"
                    table_engine = self.get_table_engine(table_name)['engine']
                    table_exist = self.get_table_engine(table_name)['status']
                    if table_exist == 1:
                        if not table_engine.endswith('MergeTree') and table_engine not in ('Merge', 'Distributed'):
                            result = ReviewResult(id=line, errlevel=2,
                                                  stagestatus='驳回不支持SQL',
                                                  errormessage='ALTER TABLE仅支持*MergeTree，Merge以及Distributed等引擎表！',
                                                  sql=statement)
                        else:
                            # delete与update语句，实际是alter语句的变种
                            if re.match(r"^alter\s+table\s+(.+?)\s+(delete|update)\s+", statement.lower()):
                                if not table_engine.endswith('MergeTree'):
                                    result = ReviewResult(id=line, errlevel=2,
                                                          stagestatus='驳回不支持SQL',
                                                          errormessage='DELETE与UPDATE仅支持*MergeTree引擎表！',
                                                          sql=statement)
                                else:
                                    result = self.explain_check(check_result, db_name, line, statement)
                            else:
                                result = self.explain_check(check_result, db_name, line, statement)
                    else:
                        result = ReviewResult(id=line, errlevel=2,
                                              stagestatus='表不存在',
                                              errormessage=f'表 {table_name} 不存在！',
                                              sql=statement)
                # 其他alter语句
                else:
                    result = self.explain_check(check_result, db_name, line, statement)
            # truncate语句
            elif re.match(r"^truncate\s+table\s+(.+?)(\s|$)", statement.lower()):
                table_name = re.match(r"^truncate\s+table\s+(.+?)(\s|$)", statement.lower(), re.M).group(1)
                if '.' not in table_name:
                    table_name = f"{db_name}.{table_name}"
                table_engine = self.get_table_engine(table_name)['engine']
                table_exist = self.get_table_engine(table_name)['status']
                if table_exist == 1:
                    if table_engine in ('View', 'File,', 'URL', 'Buffer', 'Null'):
                        result = ReviewResult(id=line, errlevel=2,
                                              stagestatus='驳回不支持SQL',
                                              errormessage='TRUNCATE不支持View,File,URL,Buffer和Null表引擎！',
                                              sql=statement)
                    else:
                        result = self.explain_check(check_result, db_name, line, statement)
                else:
                    result = ReviewResult(id=line, errlevel=2,
                                          stagestatus='表不存在',
                                          errormessage=f'表 {table_name} 不存在！',
                                          sql=statement)
            # insert语句，explain无法正确判断，暂时只做表存在性检查与简单关键字匹配
            elif re.match(r"^insert", statement.lower()):
                if re.match(r"^insert\s+into\s+(.+?)(\s+|\s*\(.+?)(values|format|select)(\s+|\()", statement.lower()):
                    table_name = re.match(r"^insert\s+into\s+(.+?)(\s+|\s*\(.+?)(values|format|select)(\s+|\()",
                                          statement.lower(), re.M).group(1)
                    if '.' not in table_name:
                        table_name = f"{db_name}.{table_name}"
                    table_exist = self.get_table_engine(table_name)['status']
                    if table_exist == 1:
                        result = ReviewResult(id=line, errlevel=0,
                                              stagestatus='Audit completed',
                                              errormessage='None',
                                              sql=statement,
                                              affected_rows=0,
                                              execute_time=0, )
                    else:
                        result = ReviewResult(id=line, errlevel=2,
                                              stagestatus='表不存在',
                                              errormessage=f'表 {table_name} 不存在！',
                                              sql=statement)
                else:
                    result = ReviewResult(id=line, errlevel=2,
                                          stagestatus='驳回不支持SQL',
                                          errormessage='INSERT语法不正确！',
                                          sql=statement)
            # 其他语句使用explain ast简单检查
            else:
                result = self.explain_check(check_result, db_name, line, statement)

            # 没有找出DDL语句的才继续执行此判断
            if check_result.syntax_type == 2:
                if get_syntax_type(statement, parser=False, db_type='mysql') == 'DDL':
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
        """执行上线单，返回Review set"""
        sql = workflow.sqlworkflowcontent.sql_content
        execute_result = ReviewSet(full_sql=sql)
        sqls = sqlparse.format(sql, strip_comments=True)
        sql_list = sqlparse.split(sqls)

        line = 1
        for statement in sql_list:
            with FuncTimer() as t:
                result = self.execute(db_name=workflow.db_name, sql=statement, close_conn=True)
            if not result.error:
                execute_result.rows.append(ReviewResult(
                    id=line,
                    errlevel=0,
                    stagestatus='Execute Successfully',
                    errormessage='None',
                    sql=statement,
                    affected_rows=0,
                    execute_time=t.cost,
                ))
                line += 1
            else:
                # 追加当前报错语句信息到执行结果中
                execute_result.error = result.error
                execute_result.rows.append(ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus='Execute Failed',
                    errormessage=f'异常信息：{result.error}',
                    sql=statement,
                    affected_rows=0,
                    execute_time=0,
                ))
                line += 1
                # 报错语句后面的语句标记为审核通过、未执行，追加到执行结果中
                for statement in sql_list[line - 1:]:
                    execute_result.rows.append(ReviewResult(
                        id=line,
                        errlevel=0,
                        stagestatus='Audit completed',
                        errormessage=f'前序语句失败, 未执行',
                        sql=statement,
                        affected_rows=0,
                        execute_time=0,
                    ))
                    line += 1
                break
        return execute_result

    def execute(self, db_name=None, sql='', close_conn=True):
        """原生执行语句"""
        result = ResultSet(full_sql=sql)
        conn = self.get_connection(db_name=db_name)
        try:
            cursor = conn.cursor()
            for statement in sqlparse.split(sql):
                cursor.execute(statement)
            cursor.close()
        except Exception as e:
            logger.warning(f"ClickHouse语句执行报错，语句：{sql}，错误信息{e}")
            result.error = str(e).split('Stack trace')[0]
        if close_conn:
            self.close()
        return result

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
