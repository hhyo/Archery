# -*- coding: UTF-8 -*-

import time

import simplejson as json
from MySQLdb.connections import numeric_part
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse

from common.utils.extend_json_encoder import ExtendJSONEncoder
from common.utils.const import SQLTuning
from sql.utils.dao import Dao
import sqlparse
from sqlparse.sql import IdentifierList, Identifier
from sqlparse.tokens import Keyword, DML


@permission_required('sql.optimize_sqltuning', raise_exception=True)
def tuning(request):
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    sqltext = request.POST.get('sql_content')
    option = request.POST.getlist('option[]')

    sql_tunning = SqlTuning(instance_name=instance_name, db_name=db_name, sqltext=sqltext)
    result = {'status': 0, 'msg': 'ok', 'data': {}}
    if 'sys_parm' in option:
        basic_information = sql_tunning.basic_information()
        sys_parameter = sql_tunning.sys_parameter()
        optimizer_switch = sql_tunning.optimizer_switch()
        result['data']['basic_information'] = basic_information
        result['data']['sys_parameter'] = sys_parameter
        result['data']['optimizer_switch'] = optimizer_switch
    if 'sql_plan' in option:
        plan, optimizer_rewrite_sql = sql_tunning.sqlplan()
        result['data']['optimizer_rewrite_sql'] = optimizer_rewrite_sql
        result['data']['plan'] = plan
    if 'obj_stat' in option:
        object_statistics_tableistructure, object_statistics_tableinfo, object_statistics_indexinfo = sql_tunning.object_statistics()
        result['data']['object_statistics_tableistructure'] = object_statistics_tableistructure
        result['data']['object_statistics_tableinfo'] = object_statistics_tableinfo
        result['data']['object_statistics_indexinfo'] = object_statistics_indexinfo
    if 'sql_profile' in option:
        session_status = sql_tunning.exec_sql()
        result['data']['session_status'] = session_status
    # 关闭连接
    sql_tunning.dao.close()
    result['data']['sqltext'] = sqltext
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


class SqlTuning(object):
    def __init__(self, instance_name, db_name, sqltext):
        self.dao = Dao(instance_name=instance_name, flag=True)
        self.db_name = db_name
        self.sqltext = sqltext
        self.sql_variable = '''
    select
      lower(variable_name),
      variable_value
    from performance_schema.global_variables
    where upper(variable_name) in ('%s')
    order by variable_name;''' % ('\',\''.join(SQLTuning.SYS_PARM_FILTER))
        self.sql_optimizer_switch = '''
    select variable_value
    from performance_schema.global_variables
    where upper(variable_name) = 'OPTIMIZER_SWITCH';
    '''
        self.sql_table_info = '''
    select
      table_name,
      engine,
      row_format                                           as format,
      table_rows,
      avg_row_length                                       as avg_row,
      round((data_length + index_length) / 1024 / 1024, 2) as total_mb,
      round((data_length) / 1024 / 1024, 2)                as data_mb,
      round((index_length) / 1024 / 1024, 2)               as index_mb
    from information_schema.tables
    where table_schema = '%s' and table_name = '%s'
    '''
        self.sql_table_index = '''
    select
      table_name,
      index_name,
      non_unique,
      seq_in_index,
      column_name,
      collation,
      cardinality,
      nullable,
      index_type
    from information_schema.statistics
    where table_schema = '%s' and table_name = '%s'
    order by 1, 3;    
    '''

    @staticmethod
    def __is_subselect(parsed):
        if not parsed.is_group:
            return False
        for item in parsed.tokens:
            if item.ttype is DML and item.value.upper() == 'SELECT':
                return True
        return False

    def __extract_from_part(self, parsed):
        from_seen = False
        for item in parsed.tokens:
            # print item.ttype,item.value
            if from_seen:
                if self.__is_subselect(item):
                    for x in self.__extract_from_part(item):
                        yield x
                elif item.ttype is Keyword:
                    raise StopIteration
                else:
                    yield item
            elif item.ttype is Keyword and item.value.upper() == 'FROM':
                from_seen = True

    @staticmethod
    def __extract_table_identifiers(token_stream):
        for item in token_stream:
            if isinstance(item, IdentifierList):
                for identifier in item.get_identifiers():
                    yield identifier.get_real_name()
            elif isinstance(item, Identifier):
                yield item.get_real_name()
            # It's a bug to check for Keyword here, but in the example
            # above some tables names are identified as keywords...
            elif item.ttype is Keyword:
                yield item.value

    def __extract_tables(self, p_sqltext):
        stream = self.__extract_from_part(sqlparse.parse(p_sqltext)[0])
        return list(self.__extract_table_identifiers(stream))

    def basic_information(self):
        return self.dao.mysql_query(sql="select @@version")

    def sys_parameter(self):
        # 获取mysql版本信息
        version = self.basic_information()['rows'][0][0]
        server_version = tuple([numeric_part(n) for n in version.split('.')[:2]])
        if server_version < (5, 7):
            sql = self.sql_variable.replace('performance_schema', 'information_schema')
        else:
            sql = self.sql_variable
        return self.dao.mysql_query(sql=sql)

    def optimizer_switch(self):
        # 获取mysql版本信息
        version = self.basic_information()['rows'][0][0]
        server_version = tuple([numeric_part(n) for n in version.split('.')[:2]])
        if server_version < (5, 7):
            sql = self.sql_optimizer_switch.replace('performance_schema', 'information_schema')
        else:
            sql = self.sql_optimizer_switch
        return self.dao.mysql_query(sql=sql)

    def sqlplan(self):
        plan = self.dao.mysql_query(self.db_name, "explain extended " + self.sqltext)
        optimizer_rewrite_sql = self.dao.mysql_query(sql="show warnings")
        return plan, optimizer_rewrite_sql

    # 获取关联表信息存在缺陷，只能获取到一张表
    def object_statistics(self):
        tableistructure = {'column_list': [], 'rows': []}
        tableinfo = {'column_list': [], 'rows': []}
        indexinfo = {'column_list': [], 'rows': []}
        for index, table_name in enumerate(self.__extract_tables(self.sqltext)):
            tableistructure = self.dao.mysql_query(db_name=self.db_name, sql="show create table {};".format(
                table_name.replace('`', '').lower()))

            tableinfo = self.dao.mysql_query(
                sql=self.sql_table_info % (self.db_name, table_name.replace('`', '').lower()))

            indexinfo = self.dao.mysql_query(
                sql=self.sql_table_index % (self.db_name, table_name.replace('`', '').lower()))
        return tableistructure, tableinfo, indexinfo

    def exec_sql(self):
        result = {"EXECUTE_TIME": 0,
                  "BEFORE_STATUS": {'column_list': [], 'rows': []},
                  "AFTER_STATUS": {'column_list': [], 'rows': []},
                  "SESSION_STATUS(DIFFERENT)": {'column_list': ['status_name', 'before', 'after', 'diff'], 'rows': []},
                  "PROFILING_DETAIL": {'column_list': [], 'rows': []},
                  "PROFILING_SUMMARY": {'column_list': [], 'rows': []}
                  }
        sql_profiling = "select concat(upper(left(variable_name,1)),substring(lower(variable_name),2,(length(variable_name)-1))) var_name,variable_value var_value from performance_schema.session_status order by 1"

        # 获取mysql版本信息
        version = self.basic_information()['rows'][0][0]
        server_version = tuple([numeric_part(n) for n in version.split('.')[:2]])
        if server_version < (5, 7):
            sql = sql_profiling.replace('performance_schema', 'information_schema')
        else:
            sql = sql_profiling
        self.dao.mysql_query(sql="set profiling=1")
        records = self.dao.mysql_query(sql="select ifnull(max(query_id),0) from INFORMATION_SCHEMA.PROFILING")
        query_id = records['rows'][0][0] + 3  # skip next sql
        # 获取执行前信息
        result['BEFORE_STATUS'] = self.dao.mysql_query(sql=sql)

        # 执行查询语句,统计执行时间
        t_start = time.time()
        self.dao.mysql_query(sql=self.sqltext)
        t_end = time.time()
        cost_time = "%5s" % "{:.4f}".format(t_end - t_start)
        result['EXECUTE_TIME'] = cost_time

        # 获取执行后信息
        result['AFTER_STATUS'] = self.dao.mysql_query(sql=sql)

        # 获取PROFILING_DETAIL信息
        result['PROFILING_DETAIL'] = self.dao.mysql_query(
            sql="select STATE,DURATION,CPU_USER,CPU_SYSTEM,BLOCK_OPS_IN,BLOCK_OPS_OUT ,MESSAGES_SENT ,MESSAGES_RECEIVED ,PAGE_FAULTS_MAJOR ,PAGE_FAULTS_MINOR ,SWAPS from INFORMATION_SCHEMA.PROFILING where query_id=" + str(
                query_id) + " order by seq")
        result['PROFILING_SUMMARY'] = self.dao.mysql_query(
            sql="SELECT STATE,SUM(DURATION) AS Total_R,ROUND(100*SUM(DURATION)/(SELECT SUM(DURATION) FROM INFORMATION_SCHEMA.PROFILING WHERE QUERY_ID=" + str(
                query_id) + "),2) AS Pct_R,COUNT(*) AS Calls,SUM(DURATION)/COUNT(*) AS R_Call FROM INFORMATION_SCHEMA.PROFILING WHERE QUERY_ID=" + str(
                query_id) + " GROUP BY STATE ORDER BY Total_R DESC")

        # 处理执行前后对比信息
        before_status_rows = [list(item) for item in result['BEFORE_STATUS']['rows']]
        after_status_rows = [list(item) for item in result['AFTER_STATUS']['rows']]
        for index, item in enumerate(before_status_rows):
            if before_status_rows[index][1] != after_status_rows[index][1]:
                before_status_rows[index].append(after_status_rows[index][1])
                before_status_rows[index].append(
                    str(float(after_status_rows[index][1]) - float(before_status_rows[index][1])))
        diff_rows = [item for item in before_status_rows if len(item) == 4]
        result['SESSION_STATUS(DIFFERENT)']['rows'] = diff_rows
        return result
