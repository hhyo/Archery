# -*- coding: UTF-8 -*-
import logging
import os
import time
import traceback

import pymysql
import simplejson as json
from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from django_q.tasks import async_task

from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines import get_engine

from sql.plugins.binglog2sql import Binlog2Sql
from .models import Instance

logger = logging.getLogger('default')


# 获取binlog列表
@permission_required('sql.menu_binlog2sql', raise_exception=True)
def binlog_list(request):
    instance_name = request.POST.get('instance_name')
    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
    query_engine = get_engine(instance=instance)
    binlog = query_engine.query('information_schema', 'show binary logs;')
    column_list = binlog.column_list
    rows = []
    for row in binlog.rows:
        row_info = {}
        for row_index, row_item in enumerate(row):
            row_info[column_list[row_index]] = row_item
        rows.append(row_info)

    result = {'status': 0, 'msg': 'ok', 'data': rows}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 通过binlog获取DML
@permission_required('sql.menu_binlog2sql', raise_exception=True)
def binlog2sql(request):
    instance_name = request.POST.get('instance_name')
    save_sql = True if request.POST.get('save_sql') == 'true' else False
    instance = Instance.objects.get(instance_name=instance_name)
    no_pk = True if request.POST.get('no_pk') == 'true' else False
    flashback = True if request.POST.get('flashback') == 'true' else False
    back_interval = 0 if request.POST.get('back_interval') == '' else int(request.POST.get('back_interval'))
    num = 500 if request.POST.get('num') == '' else int(request.POST.get('num'))
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

    # flashback=True获取DML回滚语句
    result = {'status': 0, 'msg': 'ok', 'data': ''}

    # 提交给binlog2sql进行解析
    binlog2sql = Binlog2Sql()
    # 准备参数
    args = {"conn_options": fr"-h{instance.host} -u{instance.user} -p'{instance.raw_password}' -P{instance.port} ",
            "stop_never": False,
            "no-primary-key": no_pk,
            "flashback": flashback,
            "back-interval": back_interval,
            "start-file": start_file,
            "start-position": start_pos,
            "stop-file": end_file,
            "stop-position": end_pos,
            "start-datetime": start_time,
            "stop-datetime": stop_time,
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
        # 读取前500行
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
        # 终止子进程
        p.kill()
        result['data'] = rows
    except RuntimeError as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = str(e)

    # 保存到文件
    if save_sql:
        async_task(binlog2sql_file, args=args)

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


def binlog2sql_file(args):
    """
    :param cmd_args: 生成好的命令
    :return:
    """
    binlog2sql = Binlog2Sql()
    instance = args.get('instance')
    timestamp = int(time.time())
    path = os.path.join(settings.BASE_DIR, 'downloads/binlog2sql/')
    if args.get('flashback'):
        filename = os.path.join(path, f"flashback_{instance.host}_{instance.port}_{timestamp}.sql")
    else:
        filename = os.path.join(path, f"{instance.host}_{instance.port}_{timestamp}.sql")

    # 参数转换
    cmd_args = binlog2sql.generate_args2cmd(args, shell=True)
    # 执行命令保存到文件
    with open(filename, 'w') as f:
        p = binlog2sql.execute_cmd(cmd_args, shell=True)
        for c in iter(lambda: p.stdout.read(1), ''):
            f.write(c)
