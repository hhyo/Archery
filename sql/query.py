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
from sql.engines.models import ResultSet
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
    limit_num = request.POST.get('limit_num')
    user = request.user

    result = {'status': 0, 'msg': 'ok', 'data': {}}
    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result['status'] = 1
        result['msg'] = '实例不存在'
        return result

    # 服务器端参数验证
    if sql_content is None or db_name is None or instance_name is None or limit_num is None:
        result['status'] = 1
        result['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 删除注释语句，进行语法判断，执行第一条有效sql
    sql_content = sqlparse.format(sql_content.strip(), strip_comments=True)
    sql_content = sqlparse.split(sql_content)[0].rstrip(';')

    try:
        # 查询权限校验
        priv_check_info = query_priv_check(user, instance_name, db_name, sql_content, limit_num)
        if priv_check_info['status'] == 0:
            limit_num = priv_check_info['data']['limit_num']
            priv_check = priv_check_info['data']['priv_check']
        else:
            result['status'] = priv_check_info['status']
            result['msg'] = priv_check_info['msg']
            data = ResultSet(full_sql=sql_content)
            data.error = priv_check_info['msg']
            result['data'] = data.__dict__
            return HttpResponse(json.dumps(result), content_type='application/json')
        limit_num = 0 if re.match(r"^explain", sql_content.lower()) else limit_num

        # 查询检查
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

        # 数据脱敏
        t_start = time.time()
        # 仅对正确查询并返回的语句进行脱敏
        if SysConfig().get('data_masking') and re.match(r"^select", sql_content, re.I) and query_result.error is None:
            try:
                masking_result = query_engine.query_masking(db_name=db_name, sql=sql_content, resultset=query_result)
                # 脱敏报错的处理
                if masking_result.is_critical is True:
                    # 开启query_check，直接返回异常，禁止执行
                    if SysConfig().get('query_check'):
                        masking_result.rows = []
                        masking_result.column_list = []
                        masking_result = {'status': masking_result.status,
                                          'msg': masking_result.error,
                                          'data':query_result.__dict__}
                        return HttpResponse(json.dumps(masking_result), content_type='application/json')
                query_result = masking_result
            except Exception:
                # 抛出未定义异常
                logger.error(f'数据脱敏异常，查询语句:{sql_content}\n，错误信息：{traceback.format_exc()}')
                # 开启query_check，直接返回异常，禁止执行
                if SysConfig().get('query_check'):
                    result['status'] = 1
                    result['msg'] = '脱敏数据报错,请联系管理员'
                    return HttpResponse(json.dumps(result), content_type='application/json')
        t_end = time.time()
        query_result.mask_time = "%5s" % "{:.4f}".format(t_end - t_start)
        sql_result = query_result.__dict__
        result['data'] = sql_result

        # 成功的查询语句记录存入数据库
        if sql_result.get('error'):
            pass
        else:
            if int(limit_num) == 0:
                limit_num = int(sql_result['affected_rows'])
            else:
                limit_num = min(int(limit_num), int(sql_result['affected_rows']))
            query_log = QueryLog(
                username=user.username,
                user_display=user.display,
                db_name=db_name,
                instance_name=instance.instance_name,
                sqllog=sql_content,
                effect_row=limit_num,
                cost_time=query_result.query_time,
                priv_check=priv_check,
                hit_rule=query_result.mask_rule_hit,  # '查询是否命中脱敏规则', choices=((0, '未知'), (1, '命中'), (2, '未命中'),)
                masking=query_result.is_masked  # '查询结果是否正常脱敏', choices=((1, '是'), (2, '否')
            )
            # 防止查询超时
            try:
                query_log.save()
            except:
                connection.close()
                query_log.save()
    except Exception as e:
        # 抛出未定义异常
        logger.error(f'查询异常报错，查询语句:{sql_content}\n，错误信息：{traceback.format_exc()}')
        result['status'] = 1
        result['msg'] = str(e)

    # 返回查询结果
    try:
        return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                            content_type='application/json')
    except Exception:
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

    # 查询个人记录，超管查看所有数据
    if user.is_superuser:
        sql_log_obj = QueryLog.objects.all().filter(Q(sqllog__icontains=search) | Q(user_display__icontains=search))
    else:
        sql_log_obj = QueryLog.objects.filter(username=user.username).filter(sqllog__icontains=search)

    sql_log_count = sql_log_obj.count()
    sql_log_list = sql_log_obj.order_by('-id')[offset:limit]
    # QuerySet 序列化
    sql_log_list = serializers.serialize("json", sql_log_list)
    sql_log_list = json.loads(sql_log_list)
    sql_log = [log_info['fields'] for log_info in sql_log_list]

    result = {"total": sql_log_count, "rows": sql_log}
    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')


@permission_required('sql.optimize_sqladvisor', raise_exception=True)
def explain(request):
    """
    获取SQL执行计划
    :param request:
    :return:
    """
    sql_content = request.POST.get('sql_content')
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # 服务器端参数验证
    if sql_content is None or instance_name is None:
        result['status'] = 1
        result['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(result), content_type='application/json')

    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    sql_content = sql_content.strip()

    # 过滤非查询的语句
    if re.match(r"^explain", sql_content.lower()):
        pass
    else:
        result['status'] = 1
        result['msg'] = '仅支持explain开头的语句，请检查'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 执行第一条有效sql
    sql_content = sqlparse.split(sql_content)[0].rstrip(';')

    # 执行获取执行计划语句
    query_engine = get_engine(instance=instance)
    sql_result = query_engine.query(str(db_name), sql_content).to_sep_dict()

    result['data'] = sql_result

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
