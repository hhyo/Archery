import simplejson as json

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

from sql.utils.aes_decryptor import Prpcrypt
from sql.utils.dao import Dao
from sql.utils.extend_json_encoder import ExtendJSONEncoder
from sql.utils.permission import role_required
from sql.utils.config import SysConfig
from .models import master_config

if SysConfig().sys_config.get('aliyun_rds_manage') == 'true':
    from .aliyun_rds import process_status as aliyun_process_status, \
        create_kill_session as aliyun_create_kill_session, kill_session as aliyun_kill_session, \
        sapce_status as aliyun_sapce_status

dao = Dao()
prpCryptor = Prpcrypt()


# 问题诊断--进程列表
@csrf_exempt
@role_required(('DBA',))
def process(request):
    cluster_name = request.POST.get('cluster_name')
    command_type = request.POST.get('command_type')

    base_sql = "select id, user, host, db, command, time, state, ifnull(info,'') as info from information_schema.processlist"
    # 判断是RDS还是其他实例
    if SysConfig().sys_config.get('aliyun_rds_manage') == 'true':
        result = aliyun_process_status(request)
    else:
        master_info = master_config.objects.get(cluster_name=cluster_name)
        if command_type == 'All':
            sql = base_sql + ";"
        elif command_type == 'Not Sleep':
            sql = "{} where command<>'Sleep';".format(base_sql)
        else:
            sql = "{} where command= '{}';".format(base_sql, command_type)
        processlist = dao.mysql_query(master_info.master_host, master_info.master_port, master_info.master_user,
                                      prpCryptor.decrypt(master_info.master_password), 'information_schema', sql)
        column_list = processlist['column_list']
        rows = []
        for row in processlist['rows']:
            row_info = {}
            for row_index, row_item in enumerate(row):
                row_info[column_list[row_index]] = row_item
            rows.append(row_info)
        result = {'status': 0, 'msg': 'ok', 'data': rows}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 问题诊断--通过进程id构建请求
@csrf_exempt
@role_required(('DBA',))
def create_kill_session(request):
    cluster_name = request.POST.get('cluster_name')
    ThreadIDs = request.POST.get('ThreadIDs')

    result = {'status': 0, 'msg': 'ok', 'data': []}
    # 判断是RDS还是其他实例
    if SysConfig().sys_config.get('aliyun_rds_manage') == 'true':
        result = aliyun_create_kill_session(request)
    else:
        master_info = master_config.objects.get(cluster_name=cluster_name)
        ThreadIDs = ThreadIDs.replace('[', '').replace(']', '')
        sql = "select concat('kill ', id, ';') from information_schema.processlist where id in ({});".format(ThreadIDs)
        all_kill_sql = dao.mysql_query(master_info.master_host, master_info.master_port, master_info.master_user,
                                       prpCryptor.decrypt(master_info.master_password), 'information_schema', sql)
        kill_sql = ''
        for row in all_kill_sql['rows']:
            kill_sql = kill_sql + row[0]
        result['data'] = kill_sql
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 问题诊断--终止会话
@csrf_exempt
@role_required(('DBA',))
def kill_session(request):
    cluster_name = request.POST.get('cluster_name')
    request_params = request.POST.get('request_params')

    result = {'status': 0, 'msg': 'ok', 'data': []}
    # 判断是RDS还是其他实例
    if SysConfig().sys_config.get('aliyun_rds_manage') == 'true':
        result = aliyun_kill_session(request)
    else:
        master_info = master_config.objects.get(cluster_name=cluster_name)
        kill_sql = request_params
        dao.mysql_execute(master_info.master_host, master_info.master_port, master_info.master_user,
                          prpCryptor.decrypt(master_info.master_password), 'information_schema', kill_sql)

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 问题诊断--锁信息
@csrf_exempt
@role_required(('DBA',))
def tablesapce(request):
    cluster_name = request.POST.get('cluster_name')

    # 判断是RDS还是其他实例
    if SysConfig().sys_config.get('aliyun_rds_manage') == 'true':
        result = aliyun_sapce_status(request)
    else:
        master_info = master_config.objects.get(cluster_name=cluster_name)
        sql = '''
        SELECT
          table_schema,
          table_name,
          engine,
          TRUNCATE((data_length+index_length+data_free)/1024/1024,2) AS total_size,
          table_rows,
          TRUNCATE(data_length/1024/1024,2) AS data_size,
          TRUNCATE(index_length/1024/1024,2) AS index_size,
          TRUNCATE(data_free/1024/1024,2) AS data_free,
          TRUNCATE(data_free/(data_length+index_length+data_free)*100,2) AS pct_free
        FROM information_schema.tables 
        WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'test', 'sys')
          ORDER BY total_size DESC 
        LIMIT 14;'''.format(cluster_name)
        table_space = dao.mysql_query(master_info.master_host, master_info.master_port, master_info.master_user,
                                      prpCryptor.decrypt(master_info.master_password), 'information_schema', sql)
        column_list = table_space['column_list']
        rows = []
        for row in table_space['rows']:
            row_info = {}
            for row_index, row_item in enumerate(row):
                row_info[column_list[row_index]] = row_item
            rows.append(row_info)

        result = {'status': 0, 'msg': 'ok', 'data': rows}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 问题诊断--锁等待
@csrf_exempt
@role_required(('DBA',))
def trxandlocks(request):
    cluster_name = request.POST.get('cluster_name')
    master_info = master_config.objects.get(cluster_name=cluster_name)
    sql = '''
    SELECT
      rtrx.`trx_state`                                                        AS "等待的状态",
      rtrx.`trx_started`                                                      AS "等待事务开始时间",
      rtrx.`trx_wait_started`                                                 AS "等待事务等待开始时间",
      lw.`requesting_trx_id`                                                  AS "等待事务ID",
      rtrx.trx_mysql_thread_id                                                AS "等待事务线程ID",
      rtrx.`trx_query`                                                        AS "等待事务的sql",
      CONCAT(rl.`lock_mode`, '-', rl.`lock_table`, '(', rl.`lock_index`, ')') AS "等待的表信息",
      rl.`lock_id`                                                            AS "等待的锁id",
      lw.`blocking_trx_id`                                                    AS "运行的事务id",
      trx.trx_mysql_thread_id                                                 AS "运行的事务线程id",
      CONCAT(l.`lock_mode`, '-', l.`lock_table`, '(', l.`lock_index`, ')')    AS "运行的表信息",
      l.lock_id                                                               AS "运行的锁id",
      trx.`trx_state`                                                         AS "运行事务的状态",
      trx.`trx_started`                                                       AS "运行事务的时间",
      trx.`trx_wait_started`                                                  AS "运行事务的等待开始时间",
      trx.`trx_query`                                                         AS "运行事务的sql"
    FROM information_schema.`INNODB_LOCKS` rl
      , information_schema.`INNODB_LOCKS` l
      , information_schema.`INNODB_LOCK_WAITS` lw
      , information_schema.`INNODB_TRX` rtrx
      , information_schema.`INNODB_TRX` trx
    WHERE rl.`lock_id` = lw.`requested_lock_id`
          AND l.`lock_id` = lw.`blocking_lock_id`
          AND lw.requesting_trx_id = rtrx.trx_id
          AND lw.blocking_trx_id = trx.trx_id;'''

    trxandlocks = dao.mysql_query(master_info.master_host, master_info.master_port, master_info.master_user,
                                  prpCryptor.decrypt(master_info.master_password), 'information_schema', sql)
    result = {'status': 0, 'msg': 'ok', 'data': trxandlocks}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
