# -*- coding: UTF-8 -*-
import logging
import re
import time
import traceback

import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.core import serializers
from django.db import connection, OperationalError
from django.db.models import Q
from django.http import HttpResponse
from django_q.tasks import async_task, fetch

from common.config import SysConfig
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.query_privileges import query_priv_check
from .models import QueryLog, Instance
from sql.engines import get_engine, ResultSet

logger = logging.getLogger('default')


@permission_required('sql.query_submit', raise_exception=True)
def query(request):
    """
    获取SQL查询结果
    :param request:
    :return:
    """
    instance_name = request.POST.get('instance_name')
    sql_content = request.POST.get('sql_content')
    db_name = request.POST.get('db_name')
    limit_num = int(request.POST.get('limit_num', 0))
    user = request.user

    result = {'status': 0, 'msg': 'ok', 'data': {}}
    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result['status'] = 1
        result['msg'] = '实例不存在'
        return result

    # 服务器端参数验证
    if None in [sql_content, db_name, instance_name, limit_num]:
        result['status'] = 1
        result['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(result), content_type='application/json')

    try:
        config = SysConfig()
        # 查询前的检查，禁用语句检查，语句切分
        query_engine = get_engine(instance=instance)
        query_check_info = query_engine.query_check(db_name=db_name, sql=sql_content)
        if query_check_info.get('bad_query'):
            # 引擎内部判断为 bad_query
            result['status'] = 1
            result['msg'] = query_check_info.get('msg')
            return HttpResponse(json.dumps(result), content_type='application/json')
        if query_check_info.get('has_star') and config.get('disable_star') is True:
            # 引擎内部判断为有 * 且禁止 * 选项打开
            result['status'] = 1
            result['msg'] = query_check_info.get('msg')
            return HttpResponse(json.dumps(result), content_type='application/json')
        sql_content = query_check_info['filtered_sql']

        # 查询权限校验，并且获取limit_num
        priv_check_info = query_priv_check(user, instance, db_name, sql_content, limit_num)
        if priv_check_info['status'] == 0:
            limit_num = priv_check_info['data']['limit_num']
            priv_check = priv_check_info['data']['priv_check']
        else:
            result['status'] = 1
            result['msg'] = priv_check_info['msg']
            return HttpResponse(json.dumps(result), content_type='application/json')
        # explain的limit_num设置为0
        limit_num = 0 if re.match(r"^explain", sql_content.lower()) else limit_num

        # 对查询sql增加limit限制或者改写语句
        sql_content = query_engine.filter_sql(sql=sql_content, limit_num=limit_num)

        # 执行查询语句，timeout=max_execution_time
        max_execution_time = int(config.get('max_execution_time', 60))
        query_task_id = async_task(query_engine.query, db_name=str(db_name), sql=sql_content, limit_num=limit_num,
                                   timeout=max_execution_time, cached=60)
        # 等待执行结果，max_execution_time后还没有返回结果代表将会被终止
        query_task = fetch(query_task_id, wait=max_execution_time * 1000, cached=True)
        # 在max_execution_time内执行结束
        if query_task:
            if query_task.success:
                query_result = query_task.result
                query_result.query_time = query_task.time_taken()
            else:
                query_result = ResultSet(full_sql=sql_content)
                query_result.error = query_task.result
        # 等待超时，async_task主动关闭连接
        else:
            query_result = ResultSet(full_sql=sql_content)
            query_result.error = f'查询时间超过 {max_execution_time} 秒，已被主动终止，请优化语句或者联系管理员。'

        # 查询异常
        if query_result.error:
            result['status'] = 1
            result['msg'] = query_result.error
        # 数据脱敏，仅对查询无错误的结果集进行脱敏，并且按照query_check配置是否返回
        elif config.get('data_masking'):
            query_masking_task_id = async_task(query_engine.query_masking, db_name=db_name, sql=sql_content,
                                               resultset=query_result, cached=60)
            query_masking_task = fetch(query_masking_task_id, wait=60 * 1000, cached=True)
            if query_masking_task.success:
                masking_result = query_masking_task.result
                masking_result.mask_time = query_masking_task.time_taken()
                # 脱敏出错
                if masking_result.error:
                    # 开启query_check，直接返回异常，禁止执行
                    if config.get('query_check'):
                        result['status'] = 1
                        result['msg'] = masking_result.error
                    # 关闭query_check，忽略错误信息，返回未脱敏数据，权限校验标记为跳过
                    else:
                        query_result.error = None
                        priv_check = False
                        result['data'] = query_result.__dict__
                    logger.error(f'数据脱敏异常，查询语句：{sql_content}\n，错误信息：{masking_result.error}')
                # 正常脱敏
                else:
                    result['data'] = masking_result.__dict__
            else:
                logger.error(f'数据脱敏异常，查询语句：{sql_content}\n，错误信息：{query_masking_task.result}')
                # 抛出未定义异常，并且开启query_check，直接返回异常，禁止执行
                if config.get('query_check'):
                    result['status'] = 1
                    result['msg'] = f'数据脱敏异常，请联系管理员，错误信息：{query_masking_task.result}'
                # 关闭query_check，忽略错误信息，返回未脱敏数据，权限校验标记为跳过
                else:
                    query_result.error = None
                    priv_check = False
                    result['data'] = query_result.__dict__
        # 无需脱敏的语句
        else:
            result['data'] = query_result.__dict__

        # 仅将成功的查询语句记录存入数据库
        if not query_result.error:
            if int(limit_num) == 0:
                limit_num = int(query_result.affected_rows)
            else:
                limit_num = min(int(limit_num), int(query_result.affected_rows))
            query_log = QueryLog(
                username=user.username,
                user_display=user.display,
                db_name=db_name,
                instance_name=instance.instance_name,
                sqllog=sql_content,
                effect_row=limit_num,
                cost_time=query_result.query_time,
                priv_check=priv_check,
                hit_rule=query_result.mask_rule_hit,
                masking=query_result.is_masked
            )
            # 防止查询超时
            try:
                query_log.save()
            except OperationalError:
                connection.close()
                query_log.save()
    except Exception as e:
        logger.error(f'查询异常报错，查询语句：{sql_content}\n，错误信息：{traceback.format_exc()}')
        result['status'] = 1
        result['msg'] = f'查询异常报错，错误信息：{e}'
        return HttpResponse(json.dumps(result), content_type='application/json')
    # 返回查询结果
    try:
        return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                            content_type='application/json')
    # 虽然能正常返回，但是依然会乱码
    except UnicodeDecodeError:
        return HttpResponse(json.dumps(result, default=str, bigint_as_string=True, encoding='latin1'),
                            content_type='application/json')


@permission_required('sql.menu_sqlquery', raise_exception=True)
def querylog(request):
    """
    获取sql查询记录
    :param request:
    :return:
    """
    # 获取用户信息
    user = request.user

    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit
    search = request.POST.get('search', '')

    sql_log = QueryLog.objects.all()
    # 过滤搜索信息
    sql_log = sql_log.filter(Q(sqllog__icontains=search) | Q(user_display__icontains=search))
    # 管理员查看全部数据
    if user.is_superuser:
        sql_log = sql_log
    # 普通用户查看自己的数据
    else:
        sql_log = sql_log.filter(username=user.username)

    sql_log_count = sql_log.count()
    sql_log_list = sql_log.order_by('-id')[offset:limit]
    # QuerySet 序列化
    sql_log_list = serializers.serialize("json", sql_log_list)
    sql_log_list = json.loads(sql_log_list)
    sql_log = [log_info['fields'] for log_info in sql_log_list]

    result = {"total": sql_log_count, "rows": sql_log}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
