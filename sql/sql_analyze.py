# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: sql_analyze.py 
@time: 2019/03/14
"""
import simplejson as json
from django.contrib.auth.decorators import permission_required

from common.config import SysConfig
from sql.plugins.soar import Soar
from sql.utils.sql_utils import generate_sql
from django.http import HttpResponse
from common.utils.extend_json_encoder import ExtendJSONEncoder
from .models import Instance

__author__ = 'hhyo'


@permission_required('sql.sql_analyze', raise_exception=True)
def generate(request):
    """
    解析上传文件为SQL列表
    :param request:
    :return:
    """
    text = request.POST.get('text')
    if text is None:
        result = {"total": 0, "rows": []}
    else:
        rows = generate_sql(text)
        result = {"total": len(rows), "rows": rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.sql_analyze', raise_exception=True)
def analyze(request):
    """
    利用soar分析SQL
    :param request:
    :return:
    """
    text = request.POST.get('text')
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    if not text:
        result = {"total": 0, "rows": []}
    else:
        soar = Soar()
        if instance_name != '' and db_name != '':
            soar_test_dsn = SysConfig().get('soar_test_dsn')
            # 获取实例连接信息
            instance_info = Instance.objects.get(instance_name=instance_name)
            online_dsn = "{user}:{pwd}@{host}:{port}/{db}".format(user=instance_info.user,
                                                                  pwd=instance_info.raw_password,
                                                                  host=instance_info.host,
                                                                  port=instance_info.port,
                                                                  db=db_name)
        else:
            online_dsn = ''
            soar_test_dsn = ''
        args = {"report-type": "markdown",
                "query": '',
                "online-dsn": online_dsn,
                "test-dsn": soar_test_dsn,
                "allow-online-as-test": "false"}
        rows = generate_sql(text)
        for row in rows:
            args['query'] = row['sql'].replace('"', '\\"').replace('`', '').replace('\n', ' ')
            cmd_args = soar.generate_args2cmd(args=args, shell=True)
            stdout, stderr = soar.execute_cmd(cmd_args, shell=True).communicate()
            row['report'] = stdout if stdout else stderr
        result = {"total": len(rows), "rows": rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
