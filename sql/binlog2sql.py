# -*- coding: UTF-8 -*-
import os
import time

import simplejson as json
import logging
import traceback
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from sql.utils.dao import Dao
from sql.utils.binlog2sql.binlog2sql import Binlog2sql
from common.utils.extend_json_encoder import ExtendJSONEncoder
from common.utils.aes_decryptor import Prpcrypt
from .models import Instance
from django.conf import settings

logger = logging.getLogger('default')


# 获取binlog列表
@permission_required('sql.menu_binlog2sql', raise_exception=True)
def binlog_list(request):
    instance_name = request.POST.get('instance_name')
    binlog = Dao(instance_name=instance_name).mysql_query('information_schema', 'show binary logs;')
    column_list = binlog['column_list']
    rows = []
    for row in binlog['rows']:
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
                    'passwd': Prpcrypt().decrypt(instance.password), 'charset': 'utf8'}
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
        sql_list = binlog2sql.process_binlog()
        rows = []
        for row in sql_list:
            row_info = {}
            try:
                row_info['sql'] = row.split('; #')[0] + ";"
                row_info['binlog_info'] = row.split('; #')[1].rstrip('\"')
            except Exception:
                row_info['sql'] = row
                row_info['binlog_info'] = None
            rows.append(row_info)
        result['data'] = rows[0:5000]
        # 保存文件
        if len(sql_list) > 0:
            timestamp = int(time.time())
            path = os.path.join(settings.BASE_DIR, 'downloads/binlog2sql/')
            if flashback:
                with open(os.path.join(path, 'rollback_{}.sql'.format(timestamp)), 'w') as f:
                    for sql in sql_list:
                        f.write(sql + '\n')
            else:
                with open(os.path.join(path, 'do_{}.sql'.format(timestamp)), 'w') as f:
                    for sql in sql_list:
                        f.write(sql + '\n')
    except Exception as e:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = str(e)

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
