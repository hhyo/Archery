import simplejson as json
from django.contrib.auth.decorators import permission_required

from django.http import HttpResponse

from sql.engines import get_engine
from common.utils.extend_json_encoder import ExtendJSONEncoder
from .models import AliyunRdsConfig, Instance

from .aliyun_rds import process_status as aliyun_process_status, create_kill_session as aliyun_create_kill_session, \
    kill_session as aliyun_kill_session, sapce_status as aliyun_sapce_status


# 问题诊断--进程列表
@permission_required('sql.process_view', raise_exception=True)
def process(request):
    instance_name = request.POST.get('instance_name')
    command_type = request.POST.get('command_type')

    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    base_sql = "select id, user, host, db, command, time, state, ifnull(info,'') as info from information_schema.processlist"
    # 判断是RDS还是其他实例
    if len(AliyunRdsConfig.objects.filter(instance=instance, is_enable=True)) > 0:
        result = aliyun_process_status(request)
    else:
        if command_type == 'All':
            sql = base_sql + ";"
        elif command_type == 'Not Sleep':
            sql = "{} where command<>'Sleep';".format(base_sql)
        else:
            sql = "{} where command= '{}';".format(base_sql, command_type)
        query_engine = get_engine(instance=instance)
        processlist = query_engine.query('information_schema', sql).to_dict()

        result = {'status': 0, 'msg': 'ok', 'rows': processlist}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 问题诊断--通过进程id构建请求
@permission_required('sql.process_kill', raise_exception=True)
def create_kill_session(request):
    instance_name = request.POST.get('instance_name')
    thread_ids = request.POST.get('ThreadIDs')

    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    result = {'status': 0, 'msg': 'ok', 'data': []}
    # 判断是RDS还是其他实例
    if len(AliyunRdsConfig.objects.filter(instance=instance, is_enable=True)) > 0:
        result = aliyun_create_kill_session(request)
    else:
        thread_ids = thread_ids.replace('[', '').replace(']', '')
        query_engine = get_engine(instance=instance)
        sql = "select concat('kill ', id, ';') from information_schema.processlist where id in ({});".format(thread_ids)
        all_kill_sql = query_engine.query('information_schema', sql)
        kill_sql = ''
        for row in all_kill_sql.rows:
            kill_sql = kill_sql + row[0]
        result['data'] = kill_sql
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 问题诊断--终止会话
@permission_required('sql.process_kill', raise_exception=True)
def kill_session(request):
    instance_name = request.POST.get('instance_name')
    request_params = request.POST.get('request_params')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 判断是RDS还是其他实例
    if len(AliyunRdsConfig.objects.filter(instance=instance, is_enable=True)) > 0:
        result = aliyun_kill_session(request)
    else:
        kill_sql = request_params
        execute_engine = get_engine(instance=instance)
        execute_engine.execute('information_schema', kill_sql)

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 问题诊断--表空间信息
@permission_required('sql.tablespace_view', raise_exception=True)
def tablesapce(request):
    instance_name = request.POST.get('instance_name')

    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 判断是RDS还是其他实例
    if len(AliyunRdsConfig.objects.filter(instance=instance, is_enable=True)) > 0:
        result = aliyun_sapce_status(request)
    else:
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
        LIMIT 14;'''.format(instance_name)
        execute_engine = get_engine(instance=instance)
        table_space = execute_engine.query('information_schema', sql).to_dict()

        result = {'status': 0, 'msg': 'ok', 'rows': table_space}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 问题诊断--锁等待
@permission_required('sql.trxandlocks_view', raise_exception=True)
def trxandlocks(request):
    instance_name = request.POST.get('instance_name')

    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

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

    execute_engine = get_engine(instance=instance)
    trxandlocks = execute_engine.query('information_schema', sql).to_dict()
    result = {'status': 0, 'msg': 'ok', 'rows': trxandlocks}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
