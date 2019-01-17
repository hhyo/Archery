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

from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines import get_engine
from sql.utils.binlog2sql.binlog2sql import Binlog2sql
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
    instance = Instance.objects.get(instance_name=instance_name)
    conn_setting = {'host': instance.host, 'port': int(instance.port), 'user': instance.user,
                    'passwd': instance.raw_password, 'charset': 'utf8'}
    no_pk = True if request.POST.get('no_pk') == 'true' else False
    flashback = True if request.POST.get('flashback') == 'true' else False
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
    try:
        binlog2sql = Binlog2sql(connection_settings=conn_setting, start_file=start_file, start_pos=start_pos,
                                end_file=end_file, end_pos=end_pos, start_time=start_time,
                                stop_time=stop_time, only_schemas=' '.join(only_schemas),
                                only_tables=' '.join(only_tables),
                                no_pk=no_pk, flashback=flashback, stop_never=False,
                                back_interval=1.0, only_dml=only_dml, sql_type=sql_type)
        timestamp = int(time.time())
        path = os.path.join(settings.BASE_DIR, 'downloads/binlog2sql/')
        if flashback:
            filename = os.path.join(path, 'flashback_{}_{}_{}.sql'.format(conn_setting['host'],
                                                                          conn_setting['port'],
                                                                          timestamp))
        else:
            filename = os.path.join(path, '{}_{}_{}.sql'.format(conn_setting['host'],
                                                                conn_setting['port'],
                                                                timestamp))
        # 获取sql语句，忽略wait_timeout的错误
        try:
            binlog2sql.process_binlog(filename)
        except pymysql.err.OperationalError:
            logger.error(traceback.format_exc())

        # 读取前5000行
        rows = []
        n = 1
        with open(filename) as f:
            for row in f:
                if n <= 5000:
                    row_info = {}
                    try:
                        row_info['sql'] = row.split('; #')[0] + ";"
                        row_info['binlog_info'] = row.split('; #')[1].rstrip('\"')
                    except Exception:
                        row_info['sql'] = row
                        row_info['binlog_info'] = None
                    rows.append(row_info)
                    n = n + 1
        result['data'] = rows
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = str(e)

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
