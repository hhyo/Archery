# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: sqlstats.py
@time: 2020/01/04
"""
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_page
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines import get_engine
from sql.models import Instance
import simplejson as json
from common.utils.chart_dao import ChartDao

__author__ = 'hhyo'


@cache_page(60 * 60)
def top_sql(request):
    """TOP SQL"""
    instance_name = request.GET.get('instance_name')
    db_name = request.GET.get('db_name')
    order = request.GET.get('order')

    if order == 'count':
        order = 'exec_count'
    elif order == 'latency':
        order = 'avg_latency'
    else:
        return JsonResponse({'status': 1, 'msg': '不支持的排序类型', 'data': []})

    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '实例不存在', 'data': []})

    if db_name:
        sql = f"""select query,db,exec_count,format_time(avg_latency) avg_timer_wait
from x$statement_analysis
where query regexp '^select|^update|^insert|^delete'
and db='{db_name}'
order by {order} desc
limit 20;"""
    else:
        sql = f"""select query,db,exec_count,format_time(avg_latency) avg_timer_wait
from x$statement_analysis
where query regexp '^select|^update|^insert|^delete'
order by {order} desc
limit 20;"""

    query_engine = get_engine(instance=instance)
    query_result = query_engine.query('sys', sql)
    if not query_result.error:
        data = query_result.to_dict()
        result = {'status': 0, 'msg': 'ok', 'rows': data}
    else:
        result = {'status': 1, 'msg': query_result.error}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@cache_page(60 * 60)
def top_slow_sql(request):
    """TOP SLOW SQL"""
    instance_name = request.GET.get('instance_name')
    db_name = request.GET.get('db_name')
    order = request.GET.get('order')

    if order == 'count':
        order = 'ts_cnt'
    elif order == 'latency':
        order = 'Query_time_sum'
    else:
        return JsonResponse({'status': 1, 'msg': '不支持的排序类型', 'data': []})

    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '实例不存在', 'data': []})

    hostname_max = f'{instance.host}:{instance.port}'
    query_result = ChartDao().slow_query_top(hostname_max, db_name, order)
    if not query_result['error']:
        data = []
        for r in query_result['rows']:
            data += [dict(zip(query_result['column_list'], r))]
        result = {'status': 0, 'msg': 'ok', 'rows': data}
    else:
        result = {'status': 1, 'msg': query_result['error']}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
