# -*- coding: UTF-8 -*-

import time

import MySQLdb
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

    result['data']['sqltext'] = sqltext
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


class SqlTuning(object):
    def __init__(self, instance_name, db_name, sqltext):
        self.dao = Dao(instance_name=instance_name)
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
        return self.dao.mysql_query(self.db_name, "select @@version")

    def sys_parameter(self):
        # 获取mysql版本信息
        version = self.basic_information()['rows'][0][0]
        server_version = tuple([numeric_part(n) for n in version.split('.')[:2]])
        if server_version < (5, 7):
            sql = self.sql_variable.replace('performance_schema', 'information_schema')
        else:
            sql = self.sql_variable
        return self.dao.mysql_query(self.db_name, sql)

    def optimizer_switch(self):
        # 获取mysql版本信息
        version = self.basic_information()['rows'][0][0]
        server_version = tuple([numeric_part(n) for n in version.split('.')[:2]])
        if server_version < (5, 7):
            sql = self.sql_optimizer_switch.replace('performance_schema', 'information_schema')
        else:
            sql = self.sql_variable
        return self.dao.mysql_query(self.db_name, sql)

    def sqlplan(self):
        conn = MySQLdb.connect(host=self.dao.host,
                               port=self.dao.port,
                               user=self.dao.user,
                               passwd=self.dao.password,
                               db=self.db_name, charset='utf8')
        cursor = conn.cursor()
        effect_row = cursor.execute("explain extended " + self.sqltext)
        rows = cursor.fetchall()
        fields = cursor.description
        column_list = []
        if fields:
            for i in fields:
                column_list.append(i[0])
        plan = {}
        plan['column_list'] = column_list
        plan['rows'] = rows
        plan['effect_row'] = effect_row

        effect_row = cursor.execute("show warnings")
        rows = cursor.fetchall()
        fields = cursor.description
        column_list = []
        if fields:
            for i in fields:
                column_list.append(i[0])
        optimizer_rewrite_sql = {}
        optimizer_rewrite_sql['column_list'] = column_list
        optimizer_rewrite_sql['rows'] = rows
        optimizer_rewrite_sql['effect_row'] = effect_row
        cursor.close()
        conn.close()
        return plan, optimizer_rewrite_sql

    def object_statistics(self):
        all_tableistructure = {'column_list': [], 'rows': []}
        all_tableinfo = {'column_list': [], 'rows': []}
        all_indexinfo = {'column_list': [], 'rows': []}
        for index, table_name in enumerate(self.__extract_tables(self.sqltext)):
            tableistructure = self.dao.mysql_query(self.db_name,
                                                   "show create table {};".format(table_name.replace('`', '').lower()))
            all_tableistructure['column_list'] = tableistructure['column_list']
            all_tableistructure['rows'] = tableistructure['rows']

            tableinfo = self.dao.mysql_query(self.db_name,
                                             self.sql_table_info % (self.db_name, table_name.replace('`', '').lower()))
            all_tableinfo['column_list'] = tableinfo['column_list']
            all_tableinfo['rows'].extend(tableinfo['rows'])

            indexinfo = self.dao.mysql_query(self.db_name,
                                             self.sql_table_index % (self.db_name, table_name.replace('`', '').lower()))
            all_indexinfo['column_list'] = indexinfo['column_list']
            all_indexinfo['rows'].extend(indexinfo['rows'])
        return all_tableistructure, all_tableinfo, all_indexinfo

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
        conn = MySQLdb.connect(host=self.dao.host,
                               port=self.dao.port,
                               user=self.dao.user,
                               passwd=self.dao.password,
                               db=self.db_name, charset='utf8')
        cursor = conn.cursor()

        cursor.execute("set profiling=1")
        cursor.execute("select ifnull(max(query_id),0) from INFORMATION_SCHEMA.PROFILING")
        records = cursor.fetchall()
        query_id = records[0][0] + 2  # skip next sql

        cursor.execute(sql)
        rows = cursor.fetchall()
        fields = cursor.description
        column_list = []
        if fields:
            for i in fields:
                column_list.append(i[0])
        result['BEFORE_STATUS']['column_list'] = column_list
        result['BEFORE_STATUS']['rows'] = rows

        # 执行查询语句,统计执行时间
        t_start = time.time()
        cursor.execute(self.sqltext)
        t_end = time.time()
        cost_time = "%5s" % "{:.4f}".format(t_end - t_start)
        result['EXECUTE_TIME'] = cost_time

        cursor.execute(sql)
        rows = cursor.fetchall()
        fields = cursor.description
        column_list = []
        if fields:
            for i in fields:
                column_list.append(i[0])
        result['AFTER_STATUS']['column_list'] = column_list
        result['AFTER_STATUS']['rows'] = rows

        cursor.execute(
            "select STATE,DURATION,CPU_USER,CPU_SYSTEM,BLOCK_OPS_IN,BLOCK_OPS_OUT ,MESSAGES_SENT ,MESSAGES_RECEIVED ,PAGE_FAULTS_MAJOR ,PAGE_FAULTS_MINOR ,SWAPS from INFORMATION_SCHEMA.PROFILING where query_id=" + str(
                query_id) + " order by seq")
        rows = cursor.fetchall()
        fields = cursor.description
        column_list = []
        if fields:
            for i in fields:
                column_list.append(i[0])
        result['PROFILING_DETAIL']['column_list'] = column_list
        result['PROFILING_DETAIL']['rows'] = rows

        cursor.execute(
            "SELECT STATE,SUM(DURATION) AS Total_R,ROUND(100*SUM(DURATION)/(SELECT SUM(DURATION) FROM INFORMATION_SCHEMA.PROFILING WHERE QUERY_ID=" + str(
                query_id) + "),2) AS Pct_R,COUNT(*) AS Calls,SUM(DURATION)/COUNT(*) AS R_Call FROM INFORMATION_SCHEMA.PROFILING WHERE QUERY_ID=" + str(
                query_id) + " GROUP BY STATE ORDER BY Total_R DESC")
        rows = cursor.fetchall()
        fields = cursor.description
        column_list = []
        if fields:
            for i in fields:
                column_list.append(i[0])
        result['PROFILING_SUMMARY']['column_list'] = column_list
        result['PROFILING_SUMMARY']['rows'] = rows

        cursor.close()
        conn.close()

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
