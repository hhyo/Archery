# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: sql_optimize.py
@time: 2019/03/04
"""
import MySQLdb
import re

import simplejson as json
import sqlparse
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from common.config import SysConfig
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines import get_engine
from sql.models import Instance
from sql.plugins.soar import Soar
from sql.plugins.sqladvisor import SQLAdvisor
from sql.sql_tuning import SqlTuning
from sql.utils.resource_group import user_instances

__author__ = 'hhyo'


@permission_required('sql.optimize_sqladvisor', raise_exception=True)
def optimize_sqladvisor(request):
    sql_content = request.POST.get('sql_content')
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    verbose = request.POST.get('verbose', 1)
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # 服务器端参数验证
    if sql_content is None or instance_name is None:
        result['status'] = 1
        result['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(result), content_type='application/json')

    try:
        instance_info = user_instances(request.user, db_type=['mysql']).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result['status'] = 1
        result['msg'] = '你所在组未关联该实例！'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 检查sqladvisor程序路径
    sqladvisor_path = SysConfig().get('sqladvisor')
    if sqladvisor_path is None:
        result['status'] = 1
        result['msg'] = '请配置SQLAdvisor路径！'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 提交给sqladvisor获取分析报告
    sqladvisor = SQLAdvisor()
    # 准备参数
    args = {"h": instance_info.host,
            "P": instance_info.port,
            "u": instance_info.user,
            "p": instance_info.password,
            "d": db_name,
            "v": verbose,
            "q": sql_content.strip()
            }

    # 参数检查
    args_check_result = sqladvisor.check_args(args)
    if args_check_result['status'] == 1:
        return HttpResponse(json.dumps(args_check_result), content_type='application/json')
    # 参数转换
    cmd_args = sqladvisor.generate_args2cmd(args, shell=True)
    # 执行命令
    try:
        stdout, stderr = sqladvisor.execute_cmd(cmd_args, shell=True).communicate()
        result['data'] = f'{stdout}{stderr}'
    except RuntimeError as e:
        result['status'] = 1
        result['msg'] = str(e)
    return HttpResponse(json.dumps(result), content_type='application/json')


@permission_required('sql.optimize_soar', raise_exception=True)
def optimize_soar(request):
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    sql = request.POST.get('sql')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # 服务器端参数验证
    if not (instance_name and db_name and sql):
        result['status'] = 1
        result['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(result), content_type='application/json')
    try:
        instance_info = user_instances(request.user, db_type=['mysql']).get(instance_name=instance_name)
    except Exception:
        result['status'] = 1
        result['msg'] = '你所在组未关联该实例'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 检查测试实例的连接信息和soar程序路径
    soar_test_dsn = SysConfig().get('soar_test_dsn')
    soar_path = SysConfig().get('soar')
    if not (soar_path and soar_test_dsn):
        result['status'] = 1
        result['msg'] = '请配置soar_path和test_dsn！'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 目标实例的连接信息
    online_dsn = '{user}:"{pwd}"@{host}:{port}/{db}'.format(user=instance_info.user,
                                                          pwd=instance_info.password,
                                                          host=instance_info.host,
                                                          port=instance_info.port,
                                                          db=db_name)

    # 提交给soar获取分析报告
    soar = Soar()
    # 准备参数
    args = {"online-dsn": online_dsn,
            "test-dsn": soar_test_dsn,
            "allow-online-as-test": "false",
            "report-type": "markdown",
            "query": sql.strip()
            }
    # 参数检查
    args_check_result = soar.check_args(args)
    if args_check_result['status'] == 1:
        return HttpResponse(json.dumps(args_check_result), content_type='application/json')
    # 参数转换
    cmd_args = soar.generate_args2cmd(args, shell=True)
    # 执行命令
    try:
        stdout, stderr = soar.execute_cmd(cmd_args, shell=True).communicate()
        result['data'] = stdout if stdout else stderr
    except RuntimeError as e:
        result['status'] = 1
        result['msg'] = str(e)
    return HttpResponse(json.dumps(result), content_type='application/json')


@permission_required('sql.optimize_sqltuning', raise_exception=True)
def optimize_sqltuning(request):
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    sqltext = request.POST.get('sql_content')
    option = request.POST.getlist('option[]')
    sqltext = sqlparse.format(sqltext, strip_comments=True)
    sqltext = sqlparse.split(sqltext)[0]
    if re.match(r"^select|^show|^explain", sqltext, re.I) is None:
        result = {'status': 1, 'msg': '只支持查询SQL！', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
    try:
        user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '你所在组未关联该实例！', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
    # escape
    db_name = MySQLdb.escape_string(db_name).decode('utf-8')

    sql_tunning = SqlTuning(instance_name=instance_name, db_name=db_name, sqltext=sqltext)
    result = {'status': 0, 'msg': 'ok', 'data': {}}
    if 'sys_parm' in option:
        basic_information = sql_tunning.basic_information()
        sys_parameter = sql_tunning.sys_parameter()
        optimizer_switch = sql_tunning.optimizer_switch()
        result['data']['basic_information'] = basic_information
        result['data']['sys_parameter'] = sys_parameter
        result['data']['optimizer_switch'] = optimizer_switch
    if 'sql_plan' in option:
        plan, optimizer_rewrite_sql = sql_tunning.sqlplan()
        result['data']['optimizer_rewrite_sql'] = optimizer_rewrite_sql
        result['data']['plan'] = plan
    if 'obj_stat' in option:
        result['data']['object_statistics'] = sql_tunning.object_statistics()
    if 'sql_profile' in option:
        session_status = sql_tunning.exec_sql()
        result['data']['session_status'] = session_status
    # 关闭连接
    sql_tunning.engine.close()
    result['data']['sqltext'] = sqltext
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


def explain(request):
    """
    SQL优化界面获取SQL执行计划
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
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 删除注释语句，进行语法判断，执行第一条有效sql
    sql_content = sqlparse.format(sql_content.strip(), strip_comments=True)
    try:
        sql_content = sqlparse.split(sql_content)[0]
    except IndexError:
        result['status'] = 1
        result['msg'] = '没有有效的SQL语句'
        return HttpResponse(json.dumps(result), content_type='application/json')
    else:
        # 过滤非explain的语句
        if not re.match(r"^explain", sql_content, re.I):
            result['status'] = 1
            result['msg'] = '仅支持explain开头的语句，请检查'
            return HttpResponse(json.dumps(result), content_type='application/json')

    # 执行获取执行计划语句
    query_engine = get_engine(instance=instance)
    sql_result = query_engine.query(str(db_name), sql_content).to_sep_dict()
    result['data'] = sql_result

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


def optimize_sqltuningadvisor(request):
    """
    sqltuningadvisor工具获取优化报告
    :param request:
    :return:
    """
    sql_content = request.POST.get('sql_content')
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('schema_name')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # 服务器端参数验证
    if sql_content is None or instance_name is None:
        result['status'] = 1
        result['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(result), content_type='application/json')

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 不删除注释语句，已获取加hints的SQL优化建议，进行语法判断，执行第一条有效sql
    sql_content = sqlparse.format(sql_content.strip(), strip_comments=False)
    # 对单引号加转义符,支持plsql语法
    sql_content = sql_content.replace("'", "''");
    try:
        sql_content = sqlparse.split(sql_content)[0]
    except IndexError:
        result['status'] = 1
        result['msg'] = '没有有效的SQL语句'
        return HttpResponse(json.dumps(result), content_type='application/json')
    else:
        # 过滤非Oracle语句
        if not instance.db_type == 'oracle':
            result['status'] = 1
            result['msg'] = 'SQLTuningAdvisor仅支持oracle数据库的检查'
            return HttpResponse(json.dumps(result), content_type='application/json')

    # 执行获取优化报告
    query_engine = get_engine(instance=instance)
    sql_result = query_engine.sqltuningadvisor(str(db_name), sql_content).to_sep_dict()
    result['data'] = sql_result

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
