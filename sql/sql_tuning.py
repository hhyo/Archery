# -*- coding: UTF-8 -*-

import time

import MySQLdb
import simplejson as json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from sql.utils.extend_json_encoder import ExtendJSONEncoder
from sql.models import master_config
from sql.utils.dao import Dao
from sql.utils.permission import role_required
from .const import SQLTuning
from sql.utils.aes_decryptor import Prpcrypt
import sqlparse
from sqlparse.sql import IdentifierList, Identifier
from sqlparse.tokens import Keyword, DML

prpCryptor = Prpcrypt()

dao = Dao()

sql_variable = '''
select
  lower(variable_name),
  variable_value
from performance_schema.global_variables
where upper(variable_name) in ('%s')
order by variable_name;''' % ('\',\''.join(SQLTuning.SYS_PARM_FILTER))

sql_optimizer_switch = '''
select variable_value
from performance_schema.global_variables
where upper(variable_name) = 'OPTIMIZER_SWITCH';
'''

sql_table_info = '''
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

sql_table_index = '''
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


@csrf_exempt
@role_required(('DBA',))
def tuning(request):
    cluster_name = request.POST.get('cluster_name')
    db_name = request.POST.get('db_name')
    sqltext = request.POST.get('sql_content')
    ses_status = request.POST.get('ses_status')

    basic_information = __basic_information(cluster_name, db_name)
    sys_parameter = __sys_parameter(cluster_name, db_name)
    optimizer_switch = __optimizer_switch(cluster_name, db_name)
    plan, optimizer_rewrite_sql = __sqlplan(cluster_name, db_name, sqltext)
    object_statistics_tableistructure, object_statistics_tableinfo, object_statistics_indexinfo = __object_statistics(
        cluster_name, db_name, sqltext)
    if ses_status == '1':
        session_status = __exec_sql(cluster_name, db_name, sqltext)
    else:
        session_status = {"EXECUTE_TIME": '',
                          "BEFORE_STATUS": {'column_list': [], 'rows': []},
                          "AFTER_STATUS": {'column_list': [], 'rows': []},
                          "SESSION_STATUS(DIFFERENT)": {'column_list': ['status_name', 'before', 'after', 'diff'],
                                                        'rows': []},
                          "PROFILING_DETAIL": {'column_list': [], 'rows': []},
                          "PROFILING_SUMMARY": {'column_list': [], 'rows': []}
                          }

    result = {'status': 0, 'msg': 'ok', 'data': {}}
    result['data']['basic_information'] = basic_information
    result['data']['sqltext'] = sqltext
    result['data']['sys_parameter'] = sys_parameter
    result['data']['optimizer_switch'] = optimizer_switch
    result['data']['plan'] = plan
    result['data']['optimizer_rewrite_sql'] = optimizer_rewrite_sql
    result['data']['object_statistics_tableistructure'] = object_statistics_tableistructure
    result['data']['object_statistics_tableinfo'] = object_statistics_tableinfo
    result['data']['object_statistics_indexinfo'] = object_statistics_indexinfo
    result['data']['session_status'] = session_status
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


def __is_subselect(parsed):
    if not parsed.is_group:
        return False
    for item in parsed.tokens:
        if item.ttype is DML and item.value.upper() == 'SELECT':
            return True
    return False

def __extract_from_part(parsed):
    from_seen = False
    for item in parsed.tokens:
        #print item.ttype,item.value
        if from_seen:
            if __is_subselect(item):
                for x in __extract_from_part(item):
                    yield x
            elif item.ttype is Keyword:
                raise StopIteration
            else:
                yield item
        elif item.ttype is Keyword and item.value.upper() == 'FROM':
            from_seen = True

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

def __extract_tables(p_sqltext):
    stream = __extract_from_part(sqlparse.parse(p_sqltext)[0])
    return list(__extract_table_identifiers(stream))

def __basic_information(cluster_name, db_name):
    # 取出该实例的连接方式
    masterInfo = master_config.objects.get(cluster_name=cluster_name)
    return dao.mysql_query(masterInfo.master_host,
                           masterInfo.master_port,
                           masterInfo.master_user,
                           prpCryptor.decrypt(masterInfo.master_password),
                           db_name,
                           "select @@version")


def __sys_parameter(cluster_name, db_name):
    # 取出该实例的连接方式
    masterInfo = master_config.objects.get(cluster_name=cluster_name)
    return dao.mysql_query(masterInfo.master_host,
                           masterInfo.master_port,
                           masterInfo.master_user,
                           prpCryptor.decrypt(masterInfo.master_password),
                           db_name,
                           sql_variable)


def __optimizer_switch(cluster_name, db_name):
    # 取出该实例的连接方式
    masterInfo = master_config.objects.get(cluster_name=cluster_name)
    return dao.mysql_query(masterInfo.master_host,
                           masterInfo.master_port,
                           masterInfo.master_user,
                           prpCryptor.decrypt(masterInfo.master_password),
                           db_name,
                           sql_optimizer_switch)


def __sqlplan(cluster_name, db_name, sqltext):
    # 取出该实例的连接方式
    masterInfo = master_config.objects.get(cluster_name=cluster_name)

    db = MySQLdb.connect(host=masterInfo.master_host,
                         port=masterInfo.master_port,
                         user=masterInfo.master_user,
                         passwd=prpCryptor.decrypt(masterInfo.master_password),
                         db=db_name,
                         charset='utf8mb4')
    cursor = db.cursor()
    effect_row = cursor.execute("explain extended " + sqltext)
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
    db.close()
    return plan, optimizer_rewrite_sql


def __object_statistics(cluster_name, db_name, sqltext):
    # 取出该实例的连接方式
    masterInfo = master_config.objects.get(cluster_name=cluster_name)
    all_tableistructure = {'column_list': [], 'rows': []}
    all_tableinfo = {'column_list': [], 'rows': []}
    all_indexinfo = {'column_list': [], 'rows': []}
    for index, table_name in enumerate(__extract_tables(sqltext)):
        tableistructure = dao.mysql_query(masterInfo.master_host,
                                          masterInfo.master_port,
                                          masterInfo.master_user,
                                          prpCryptor.decrypt(masterInfo.master_password),
                                          db_name, "show create table {};".format(table_name.lower()))
        all_tableistructure['column_list'] = tableistructure['column_list']
        all_tableistructure['rows'] = tableistructure['rows']

        tableinfo = dao.mysql_query(masterInfo.master_host,
                                    masterInfo.master_port,
                                    masterInfo.master_user,
                                    prpCryptor.decrypt(masterInfo.master_password),
                                    db_name,
                                    sql_table_info % (db_name, table_name.lower()))
        all_tableinfo['column_list'] = tableinfo['column_list']
        all_tableinfo['rows'].extend(tableinfo['rows'])

        indexinfo = dao.mysql_query(masterInfo.master_host,
                                    masterInfo.master_port,
                                    masterInfo.master_user,
                                    prpCryptor.decrypt(masterInfo.master_password),
                                    db_name,
                                    sql_table_index % (db_name, table_name.lower()))
        all_indexinfo['column_list'] = indexinfo['column_list']
        all_indexinfo['rows'].extend(indexinfo['rows'])
    return all_tableistructure, all_tableinfo, all_indexinfo


def __exec_sql(cluster_name, db_name, sqltext):
    # 取出该实例的连接方式
    masterInfo = master_config.objects.get(cluster_name=cluster_name)
    result = {"EXECUTE_TIME": 0,
              "BEFORE_STATUS": {'column_list': [], 'rows': []},
              "AFTER_STATUS": {'column_list': [], 'rows': []},
              "SESSION_STATUS(DIFFERENT)": {'column_list': ['status_name', 'before', 'after', 'diff'], 'rows': []},
              "PROFILING_DETAIL": {'column_list': [], 'rows': []},
              "PROFILING_SUMMARY": {'column_list': [], 'rows': []}
              }

    conn = MySQLdb.connect(host=masterInfo.master_host,
                           port=masterInfo.master_port,
                           user=masterInfo.master_user,
                           passwd=prpCryptor.decrypt(masterInfo.master_password),
                           db=db_name,
                           charset='utf8mb4')
    cursor = conn.cursor()

    cursor.execute("set profiling=1")
    cursor.execute("select ifnull(max(query_id),0) from INFORMATION_SCHEMA.PROFILING")
    records = cursor.fetchall()
    query_id = records[0][0] + 2  # skip next sql

    cursor.execute(
        "select concat(upper(left(variable_name,1)),substring(lower(variable_name),2,(length(variable_name)-1))) var_name,variable_value var_value from performance_schema.session_status order by 1")
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
    cursor.execute(sqltext)
    t_end = time.time()
    cost_time = "%5s" % "{:.4f}".format(t_end - t_start)
    result['EXECUTE_TIME'] = cost_time

    cursor.execute(
        "select concat(upper(left(variable_name,1)),substring(lower(variable_name),2,(length(variable_name)-1))) var_name,variable_value var_value from performance_schema.session_status order by 1")
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
