# -*- coding: UTF-8 -*-
import logging
import re
import time
import traceback

import simplejson as json
import sqlparse
from django.contrib.auth.decorators import permission_required
from django.core import serializers
from django.db import connection
from django.db.models import Q
from django.http import HttpResponse

from common.config import SysConfig
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.query_privileges import query_priv_check
from .models import QueryLog, Instance
from sql.engines import get_engine

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
    if not (sql_content and db_name and instance_name and limit_num):
        result['status'] = 1
        result['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 删除注释语句，进行语法判断，执行第一条有效sql
    sql_content = sqlparse.format(sql_content.strip(), strip_comments=True)
    try:
        sql_content = sqlparse.split(sql_content)[0]
    except IndexError:
        result['status'] = 1
        result['msg'] = '没有有效的SQL语句'
        return HttpResponse(json.dumps(result), content_type='application/json')

    try:
        # 查询权限校验
        check_info = query_priv_check(user, instance_name, db_name, sql_content, limit_num)
        if check_info['status'] == 0:
            limit_num = check_info['data']['limit_num']
            priv_check = check_info['data']['priv_check']
        else:
            result['status'] = 1
            result['msg'] = check_info['msg']
            return HttpResponse(json.dumps(result), content_type='application/json')
        # explain的limit_num = 0设置为0
        limit_num = 0 if re.match(r"^explain", sql_content.lower()) else limit_num

        # 查询前的检查，禁用语句等校验
        query_engine = get_engine(instance=instance)
        filter_result = query_engine.query_check(db_name=db_name, sql=sql_content, limit_num=limit_num)
        if filter_result.get('bad_query'):
            # 引擎内部判断为 bad_query
            result['status'] = 1
            result['msg'] = filter_result.get('msg')
            return HttpResponse(json.dumps(result), content_type='application/json')
        if filter_result.get('has_star') and SysConfig().get('disable_star') is True:
            # 引擎内部判断为有 * 且禁止 * 选项打开
            result['status'] = 1
            result['msg'] = filter_result.get('msg')
            return HttpResponse(json.dumps(result), content_type='application/json')
        else:
            sql_content = filter_result['filtered_sql']

        # 执行查询语句,统计执行时间
        t_start = time.time()
        query_result = query_engine.query(db_name=str(db_name), sql=sql_content, limit_num=limit_num)
        t_end = time.time()
        query_result.query_time = "%5s" % "{:.4f}".format(t_end - t_start)

        # 数据脱敏，仅对正确查询并返回的语句进行脱敏
        if SysConfig().get('data_masking') and re.match(r"^select", sql_content, re.I) and query_result.error is None:
            try:
                # 记录脱敏时间
                t_start = time.time()
                masking_result = query_engine.query_masking(db_name=db_name, sql=sql_content, resultset=query_result)
                t_end = time.time()
                masking_result.mask_time = "%5s" % "{:.4f}".format(t_end - t_start)
                # 脱敏出错，并且开启query_check，直接返回异常，禁止执行
                if masking_result.error and SysConfig().get('query_check'):
                    result['status'] = 1
                    result['msg'] = masking_result.error
                # 脱敏出错，关闭query_check，忽略错误信息，返回未脱敏数据
                elif masking_result.error and not SysConfig().get('query_check'):
                    query_result.error = None
                    result['data'] = query_result.__dict__
                # 正常脱敏
                else:
                    result['data'] = masking_result.__dict__
            except Exception as e:
                logger.error(f'数据脱敏异常，查询语句：{sql_content}\n，错误信息：{traceback.format_exc()}')
                # 抛出未定义异常，并且开启query_check，直接返回异常，禁止执行
                if SysConfig().get('query_check'):
                    result['status'] = 1
                    result['msg'] = f'数据脱敏异常，请联系管理员，错误信息：{e}'
                # 关闭query_check，忽略错误信息，返回未脱敏数据
                else:
                    query_result.error = None
                    result['data'] = query_result.__dict__
        # 无需脱敏的语句
        else:
            if query_result.error:
                result['status'] = 1
                result['msg'] = query_result.error
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
            except:
                connection.close()
                query_log.save()
        # 返回查询结果
        return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                            content_type='application/json')
    except Exception as e:
        logger.error(f'查询异常报错，查询语句：{sql_content}\n，错误信息：{traceback.format_exc()}')
        result['status'] = 1
        result['msg'] = f'查询异常报错，错误信息：{e}'
        return HttpResponse(json.dumps(result), content_type='application/json')


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
    return HttpResponse(json.dumps(result), content_type='application/json')
