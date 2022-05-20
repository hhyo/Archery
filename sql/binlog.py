# -*- coding: UTF-8 -*-
import MySQLdb
import logging
import os
import time
import traceback
import shlex

import simplejson as json
from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse, JsonResponse
from django_q.tasks import async_task

from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines import get_engine

from sql.plugins.binglog2sql import Binlog2Sql
from sql.plugins.my2sql import My2SQL
from sql.notify import notify_for_binlog2sql, notify_for_my2sql
from .models import Instance

logger = logging.getLogger('default')


@permission_required('sql.menu_binlog2sql', raise_exception=True)
def binlog_list(request):
    """
    获取binlog列表
    :param request:
    :return:
    """
    instance_name = request.POST.get('instance_name')
    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
    query_engine = get_engine(instance=instance)
    query_result = query_engine.query('information_schema', 'show binary logs;')
    if not query_result.error:
        column_list = query_result.column_list
        rows = []
        for row in query_result.rows:
            row_info = {}
            for row_index, row_item in enumerate(row):
                row_info[column_list[row_index]] = row_item
            rows.append(row_info)
        result = {'status': 0, 'msg': 'ok', 'data': rows}
    else:
        result = {'status': 1, 'msg': query_result.error}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.binlog_del', raise_exception=True)
def del_binlog(request):
    instance_id = request.POST.get('instance_id')
    binlog = request.POST.get('binlog', '')
    try:
        instance = Instance.objects.get(id=instance_id)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    # escape
    binlog = MySQLdb.escape_string(binlog).decode('utf-8')

    if binlog:
        query_engine = get_engine(instance=instance)
        query_result = query_engine.query(sql=fr"purge master logs to '{binlog}';")
        if query_result.error is None:
            result = {'status': 0, 'msg': '清理成功', 'data': ''}
        else:
            result = {'status': 2, 'msg': f'清理失败,Error:{query_result.error}', 'data': ''}
    else:
        result = {'status': 1, 'msg': 'Error:未选择binlog！', 'data': ''}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.menu_binlog2sql', raise_exception=True)
def binlog2sql(request):
    """
    通过解析binlog获取SQL
    :param request:
    :return:
    """
    instance_name = request.POST.get('instance_name')
    save_sql = True if request.POST.get('save_sql') == 'true' else False
    instance = Instance.objects.get(instance_name=instance_name)
    no_pk = True if request.POST.get('no_pk') == 'true' else False
    flashback = True if request.POST.get('flashback') == 'true' else False
    back_interval = 0 if request.POST.get('back_interval') == '' else int(request.POST.get('back_interval'))
    num = 30 if request.POST.get('num') == '' else int(request.POST.get('num'))
    start_file = request.POST.get('start_file')
    start_pos = request.POST.get('start_pos') if request.POST.get('start_pos') == '' else int(
        request.POST.get('start_pos'))
    end_file = request.POST.get('end_file')
    end_pos = request.POST.get('end_pos') if request.POST.get('end_pos') == '' else int(request.POST.get('end_pos'))
    stop_time = request.POST.get('stop_time')
    start_time = request.POST.get('start_time')
    only_schemas = request.POST.getlist('only_schemas')
    only_tables = request.POST.getlist('only_tables[]')
    only_dml = True if request.POST.get('only_dml') == 'true' else False
    sql_type = ['INSERT', 'UPDATE', 'DELETE'] if request.POST.getlist('sql_type[]') == [] else request.POST.getlist(
        'sql_type[]')
    # 校验sql_type
    if [i for i in sql_type if i not in ['INSERT', 'UPDATE', 'DELETE']]:
        return JsonResponse({'status': 1, 'msg': '类型过滤参数不正确', 'data': {}})

    # flashback=True获取DML回滚语句
    result = {'status': 0, 'msg': 'ok', 'data': ''}

    # 提交给binlog2sql进行解析
    binlog2sql = Binlog2Sql()
    # 准备参数
    instance_password = shlex.quote(f'"{str(instance.password)}"')
    args = {"conn_options": fr"-h{shlex.quote(str(instance.host))} -u{shlex.quote(str(instance.user))} \
                -p'{instance_password}' -P{shlex.quote(str(instance.port))} ",
            "stop_never": False,
            "no-primary-key": no_pk,
            "flashback": flashback,
            "back-interval": back_interval,
            "start-file": start_file,
            "start-position": start_pos,
            "stop-file": end_file,
            "stop-position": end_pos,
            "start-datetime": '"'+start_time+'"',
            "stop-datetime": '"'+stop_time+'"',
            "databases": ' '.join(only_schemas),
            "tables": ' '.join(only_tables),
            "only-dml": only_dml,
            "sql-type": ' '.join(sql_type),
            "instance": instance
            }

    # 参数检查
    args_check_result = binlog2sql.check_args(args)
    if args_check_result['status'] == 1:
        return HttpResponse(json.dumps(args_check_result), content_type='application/json')
    # 参数转换
    cmd_args = binlog2sql.generate_args2cmd(args, shell=True)
    # 执行命令
    try:
        p = binlog2sql.execute_cmd(cmd_args, shell=True)
        # 读取前num行后结束
        rows = []
        n = 1
        for line in iter(p.stdout.readline, ''):
            if n <= num:
                n = n + 1
                row_info = {}
                try:
                    row_info['sql'] = line.split('; #')[0] + ";"
                    row_info['binlog_info'] = line.split('; #')[1].rstrip('\"')
                except IndexError:
                    row_info['sql'] = line
                    row_info['binlog_info'] = None
                rows.append(row_info)
            else:
                break
        if rows.__len__() == 0:
            # 判断是否有异常
            stderr = p.stderr.read()
            if stderr:
                result['status'] = 1
                result['msg'] = stderr
                return HttpResponse(json.dumps(result), content_type='application/json')
        # 终止子进程
        p.kill()
        result['data'] = rows
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = str(e)

    # 异步保存到文件
    if save_sql:
        args.pop('conn_options')
        async_task(binlog2sql_file, args=args, user=request.user, hook=notify_for_binlog2sql, timeout=-1,
                   task_name=f'binlog2sql-{time.time()}')

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


def binlog2sql_file(args, user):
    """
    用于异步保存binlog解析的文件
    :param args: 参数
    :param user: 操作用户对象，用户消息推送
    :return:
    """
    binlog2sql = Binlog2Sql()
    instance = args.get('instance')
    instance_password = shlex.quote(f'"{str(instance.password)}"')
    conn_options = fr"-h{shlex.quote(str(instance.host))} -u{shlex.quote(str(instance.user))} \
        -p'{instance_password}' -P{shlex.quote(str(instance.port))}"
    args['conn_options'] = conn_options
    timestamp = int(time.time())
    path = os.path.join(settings.BASE_DIR, 'downloads/binlog2sql/')
    os.makedirs(path, exist_ok=True)
    if args.get('flashback'):
        filename = os.path.join(path, f"flashback_{instance.host}_{instance.port}_{timestamp}.sql")
    else:
        filename = os.path.join(path, f"{instance.host}_{instance.port}_{timestamp}.sql")

    # 参数转换
    cmd_args = binlog2sql.generate_args2cmd(args, shell=True)
    # 执行命令保存到文件
    with open(filename, 'w') as f:
        p = binlog2sql.execute_cmd(cmd_args, shell=True)
        for c in iter(p.stdout.readline, ''):
            f.write(c)
    return user, filename


@permission_required('sql.menu_my2sql', raise_exception=True)
def my2sql(request):
    """
    通过解析binlog获取SQL--使用my2sql
    :param request:
    :return:
    """
    instance_name = request.POST.get('instance_name')
    save_sql = True if request.POST.get('save_sql') == 'true' else False
    instance = Instance.objects.get(instance_name=instance_name)
    work_type = 'rollback' if request.POST.get('rollback') == 'true' else '2sql'
    num = 30 if request.POST.get('num') == '' else int(request.POST.get('num'))
    threads = 4 if request.POST.get('threads') == '' else int(request.POST.get('threads'))
    start_file = request.POST.get('start_file')
    start_pos = request.POST.get('start_pos') if request.POST.get('start_pos') == '' else int(
        request.POST.get('start_pos'))
    end_file = request.POST.get('end_file')
    end_pos = request.POST.get('end_pos') if request.POST.get('end_pos') == '' else int(request.POST.get('end_pos'))
    stop_time = request.POST.get('stop_time')
    start_time = request.POST.get('start_time')
    only_schemas = request.POST.getlist('only_schemas')
    only_tables = request.POST.getlist('only_tables[]')
    sql_type = [] if request.POST.getlist('sql_type[]') == [] else request.POST.getlist('sql_type[]')
    extra_info = True if request.POST.get('extra_info') == 'true' else False
    ignore_primary_key = True if request.POST.get('ignore_primary_key') == 'true' else False
    full_columns = True if request.POST.get('full_columns') == 'true' else False
    no_db_prefix = True if request.POST.get('no_db_prefix') == 'true' else False
    file_per_table = True if request.POST.get('file_per_table') == 'true' else False

    result = {'status': 0, 'msg': 'ok', 'data': []}

    # 提交给my2sql进行解析
    my2sql = My2SQL()

    # 准备参数
    instance_password = shlex.quote(f'"{str(instance.password)}"')
    args = {"conn_options": fr"-host {shlex.quote(str(instance.host))} -user {shlex.quote(str(instance.user))} \
                -password '{instance_password}' -port {shlex.quote(str(instance.port))} ",
            "work-type": work_type,
            "start-file": start_file,
            "start-pos": start_pos,
            "stop-file": end_file,
            "stop-pos": end_pos,
            "start-datetime": start_time,
            "stop-datetime": stop_time,
            "databases": ' '.join(only_schemas),
            "tables": ','.join(only_tables),
            "sql": ','.join(sql_type),
            "instance": instance,
            "threads": threads,
            "add-extraInfo": extra_info,
            "ignore-primaryKey-forInsert": ignore_primary_key,
            "full-columns": full_columns,
            "do-not-add-prifixDb": no_db_prefix,
            "file-per-table": file_per_table,
            "output-toScreen": True
            }

    # 参数检查
    args_check_result = my2sql.check_args(args)
    if args_check_result['status'] == 1:
        return HttpResponse(json.dumps(args_check_result), content_type='application/json')
    # 参数转换
    cmd_args = my2sql.generate_args2cmd(args, shell=True)

    # 执行命令
    try:
        p = my2sql.execute_cmd(cmd_args, shell=True)
        # 读取前num行后结束
        rows = []
        n = 1
        for line in iter(p.stdout.readline, ''):
            if n <= num and isinstance(line, str):
                if line[0:6].upper() in ('INSERT', 'DELETE', 'UPDATE'):
                    n = n + 1
                    row_info = {}
                    try:
                        row_info['sql'] = line + ';'
                    except IndexError:
                        row_info['sql'] = line + ';'
                    rows.append(row_info)
            else:
                break

        if rows.__len__() == 0:
            # 判断是否有异常
            stderr = p.stderr.read()
            if stderr and isinstance(stderr, str):
                result['status'] = 1
                result['msg'] = stderr
                return HttpResponse(json.dumps(result), content_type='application/json')
        # 终止子进程
        p.kill()
        result['data'] = rows
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = str(e)

    # 异步保存到文件
    if save_sql:
        args.pop('conn_options')
        args.pop('output-toScreen')
        async_task(my2sql_file, args=args, user=request.user, hook=notify_for_my2sql, timeout=-1,
                   task_name=f'my2sql-{time.time()}')

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


def my2sql_file(args, user):
    """
    用于异步保存binlog解析的文件
    :param args: 参数
    :param user: 操作用户对象，用户消息推送
    :return:
    """
    my2sql = My2SQL()
    instance = args.get('instance')
    instance_password = shlex.quote(f'"{str(instance.password)}"')
    conn_options = fr"-host {shlex.quote(str(instance.host))} -user {shlex.quote(str(instance.user))} \
        -password '{instance_password}' -port {shlex.quote(str(instance.port))} "
    args['conn_options'] = conn_options
    path = os.path.join(settings.BASE_DIR, 'downloads/my2sql/')
    os.makedirs(path, exist_ok=True)

    # 参数转换
    args["output-dir"] = path
    cmd_args = my2sql.generate_args2cmd(args, shell=True)
    # 使用output-dir参数执行命令保存sql
    my2sql.execute_cmd(cmd_args, shell=True)
    return user, path
