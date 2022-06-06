import logging
import traceback
import MySQLdb
#import simplejson as json
import json
from django.contrib.auth.decorators import permission_required

from django.http import HttpResponse

from sql.engines import get_engine
from common.utils.extend_json_encoder import ExtendJSONEncoder, ExtendJSONEncoderBytes
from sql.utils.resource_group import user_instances
from .models import AliyunRdsConfig, Instance

from .aliyun_rds import process_status as aliyun_process_status, create_kill_session as aliyun_create_kill_session, \
    kill_session as aliyun_kill_session, sapce_status as aliyun_sapce_status

logger = logging.getLogger('default')

# 问题诊断--进程列表
@permission_required('sql.process_view', raise_exception=True)
def process(request):
    instance_name = request.POST.get('instance_name')
    command_type = request.POST.get('command_type')

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '你所在组未关联该实例', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    query_engine = get_engine(instance=instance)
    query_result = None
    if instance.db_type == 'mysql':
        base_sql = "select id, user, host, db, command, time, state, ifnull(info,'') as info from information_schema.processlist"
        # 判断是RDS还是其他实例
        if AliyunRdsConfig.objects.filter(instance=instance, is_enable=True).exists():
            result = aliyun_process_status(request)
        else:
            # escape
            command_type = MySQLdb.escape_string(command_type).decode('utf-8')
            if not command_type:
                command_type = 'Query'
            if command_type == 'All':
                sql = base_sql + ";"
            elif command_type == 'Not Sleep':
                sql = "{} where command<>'Sleep';".format(base_sql)
            else:
                sql = "{} where command= '{}';".format(base_sql, command_type)
            
            query_result = query_engine.query('information_schema', sql)

    elif instance.db_type == 'mongo':
        query_result = query_engine.current_op(command_type)
        print(query_result)
        
    else:
        result = {'status': 1, 'msg': '暂时不支持%s类型数据库的进程列表查询' % instance.db_type , 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
     
    if query_result:       
        if not query_result.error:
            processlist = query_result.to_dict()
            result = {'status': 0, 'msg': 'ok', 'rows': processlist}
        else:
            result = {'status': 1, 'msg': query_result.error}
    
    # 返回查询结果
    # ExtendJSONEncoderBytes 使用json模块，bigint_as_string只支持simplejson
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoderBytes),
                        content_type='application/json')


# 问题诊断--通过线程id构建请求 这里只是用于确定将要kill的线程id还在运行
@permission_required('sql.process_kill', raise_exception=True)
def create_kill_session(request):
    instance_name = request.POST.get('instance_name')
    thread_ids = request.POST.get('ThreadIDs')

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '你所在组未关联该实例', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    result = {'status': 0, 'msg': 'ok', 'data': []}
    query_engine = get_engine(instance=instance)
    if instance.db_type == 'mysql':
        # 判断是RDS还是其他实例
        if AliyunRdsConfig.objects.filter(instance=instance, is_enable=True).exists():
            result = aliyun_create_kill_session(request)
        else:
            thread_ids = json.loads(thread_ids)
            
            sql = "select concat('kill ', id, ';') from information_schema.processlist where id in ({});"\
                .format(','.join(str(tid) for tid in thread_ids))
            all_kill_sql = query_engine.query('information_schema', sql)
            kill_sql = ''
            for row in all_kill_sql.rows:
                kill_sql = kill_sql + row[0]
            result['data'] = kill_sql
    
    elif instance.db_type == 'mongo':
        kill_command = query_engine.get_kill_command(json.loads(thread_ids))
        result['data'] = kill_command

    else:
        result = {'status': 1, 'msg': '暂时不支持%s类型数据库通过进程id构建请求' % instance.db_type , 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 问题诊断--终止会话 这里是实际执行kill的操作
@permission_required('sql.process_kill', raise_exception=True)
def kill_session(request):
    instance_name = request.POST.get('instance_name')
    thread_ids = request.POST.get('ThreadIDs')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '你所在组未关联该实例', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    engine = get_engine(instance=instance)
    if instance.db_type == 'mysql':    
        # 判断是RDS还是其他实例
        if AliyunRdsConfig.objects.filter(instance=instance, is_enable=True).exists():
            result = aliyun_kill_session(request)
        else:
            thread_ids = json.loads(thread_ids)
            
            sql = "select concat('kill ', id, ';') from information_schema.processlist where id in ({});"\
                .format(','.join(str(tid) for tid in thread_ids))
            all_kill_sql = engine.query('information_schema', sql)
            kill_sql = ''
            for row in all_kill_sql.rows:
                kill_sql = kill_sql + row[0]
            engine.execute('information_schema', kill_sql)
    
    elif instance.db_type == 'mongo':
        engine.kill_op(json.loads(thread_ids))

    else:
        result = {'status': 1, 'msg': '暂时不支持%s类型数据库终止会话' % instance.db_type , 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 问题诊断--表空间信息
@permission_required('sql.tablespace_view', raise_exception=True)
def tablesapce(request):
    instance_name = request.POST.get('instance_name')

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '你所在组未关联该实例', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    if instance.db_type != 'mysql':
        result = {'status': 1, 'msg': '暂时不支持%s类型数据库的表空间信息查询' % instance.db_type , 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 判断是RDS还是其他实例
    if AliyunRdsConfig.objects.filter(instance=instance, is_enable=True).exists():
        result = aliyun_sapce_status(request)
    else:
        sql = '''
        SELECT
          table_schema AS table_schema,
          table_name AS table_name,
          engine AS engine,
          TRUNCATE((data_length+index_length+data_free)/1024/1024,2) AS total_size,
          table_rows AS table_rows,
          TRUNCATE(data_length/1024/1024,2) AS data_size,
          TRUNCATE(index_length/1024/1024,2) AS index_size,
          TRUNCATE(data_free/1024/1024,2) AS data_free,
          TRUNCATE(data_free/(data_length+index_length+data_free)*100,2) AS pct_free
        FROM information_schema.tables 
        WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'test', 'sys')
          ORDER BY total_size DESC 
        LIMIT 14;'''.format(instance_name)
        query_engine = get_engine(instance=instance)
        query_result = query_engine.query('information_schema', sql)
        if not query_result.error:
            table_space = query_result.to_dict()
            result = {'status': 0, 'msg': 'ok', 'rows': table_space}
        else:
            result = {'status': 1, 'msg': query_result.error}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 问题诊断--锁等待
@permission_required('sql.trxandlocks_view', raise_exception=True)
def trxandlocks(request):
    instance_name = request.POST.get('instance_name')

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '你所在组未关联该实例', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    if instance.db_type != 'mysql':
        result = {'status': 1, 'msg': '暂时不支持%s类型数据库的锁等待查询' % instance.db_type , 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    query_engine = get_engine(instance=instance)
    server_version = query_engine.server_version
    if server_version < (8, 0, 1):
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

    else:
        sql = '''
            SELECT
              rtrx.`trx_state`                                                           AS "等待的状态",
              rtrx.`trx_started`                                                         AS "等待事务开始时间",
              rtrx.`trx_wait_started`                                                    AS "等待事务等待开始时间",
              lw.`REQUESTING_ENGINE_TRANSACTION_ID`                                      AS "等待事务ID",
              rtrx.trx_mysql_thread_id                                                   AS "等待事务线程ID",
              rtrx.`trx_query`                                                           AS "等待事务的sql",
              CONCAT(rl.`lock_mode`, '-', rl.`OBJECT_SCHEMA`, '(', rl.`INDEX_NAME`, ')') AS "等待的表信息",
              rl.`ENGINE_LOCK_ID`                                                        AS "等待的锁id",
              lw.`BLOCKING_ENGINE_TRANSACTION_ID`                                        AS "运行的事务id",
              trx.trx_mysql_thread_id                                                    AS "运行的事务线程id",
              CONCAT(l.`lock_mode`, '-', l.`OBJECT_SCHEMA`, '(', l.`INDEX_NAME`, ')')    AS "运行的表信息",
              l.ENGINE_LOCK_ID                                                           AS "运行的锁id",
              trx.`trx_state`                                                            AS "运行事务的状态",
              trx.`trx_started`                                                          AS "运行事务的时间",
              trx.`trx_wait_started`                                                     AS "运行事务的等待开始时间",
              trx.`trx_query`                                                            AS "运行事务的sql"
            FROM performance_schema.`data_locks` rl
              , performance_schema.`data_locks` l
              , performance_schema.`data_lock_waits` lw
              , information_schema.`INNODB_TRX` rtrx
              , information_schema.`INNODB_TRX` trx
            WHERE rl.`ENGINE_LOCK_ID` = lw.`REQUESTING_ENGINE_LOCK_ID`
                  AND l.`ENGINE_LOCK_ID` = lw.`BLOCKING_ENGINE_LOCK_ID`
                  AND lw.REQUESTING_ENGINE_TRANSACTION_ID = rtrx.trx_id
                  AND lw.BLOCKING_ENGINE_TRANSACTION_ID = trx.trx_id;'''

    query_result = query_engine.query('information_schema', sql)
    if not query_result.error:
        trxandlocks = query_result.to_dict()
        result = {'status': 0, 'msg': 'ok', 'rows': trxandlocks}
    else:
        result = {'status': 1, 'msg': query_result.error}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 问题诊断--长事务
@permission_required('sql.trx_view', raise_exception=True)
def innodb_trx(request):
    instance_name = request.POST.get('instance_name')

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '你所在组未关联该实例', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    if instance.db_type != 'mysql':
        result = {'status': 1, 'msg': '暂时不支持%s类型数据库的长事务查询' % instance.db_type , 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    query_engine = get_engine(instance=instance)
    sql = '''select trx.trx_started,
       trx.trx_state,
       trx.trx_operation_state,
       trx.trx_mysql_thread_id,
       trx.trx_tables_locked,
       trx.trx_rows_locked,
       trx.trx_rows_modified,
       trx.trx_is_read_only,
       trx.trx_isolation_level,
      p.user,
      p.host,
      p.db,
      TO_SECONDS(NOW()) - TO_SECONDS(trx.trx_started) trx_idle_time,
      p.time thread_time,
      IFNULL((SELECT
       GROUP_CONCAT(t1.sql_text SEPARATOR ';
      ')
    FROM performance_schema.events_statements_history t1
      INNER JOIN performance_schema.threads t2
        ON t1.thread_id = t2.thread_id
    WHERE t2.PROCESSLIST_ID = p.id), '') info
FROM information_schema.INNODB_TRX trx
  INNER JOIN information_schema.PROCESSLIST p
    ON trx.trx_mysql_thread_id = p.id
    WHERE trx.trx_state = 'RUNNING'
    AND p.COMMAND = 'Sleep'
    AND p.time > 3
    ORDER BY trx.trx_started ASC;'''

    query_result = query_engine.query('information_schema', sql)
    if not query_result.error:
        trx = query_result.to_dict()
        result = {'status': 0, 'msg': 'ok', 'rows': trx}
    else:
        result = {'status': 1, 'msg': query_result.error}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
