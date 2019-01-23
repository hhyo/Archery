# -*- coding: UTF-8 -*-
import os
import subprocess
import time

import simplejson as json
from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse

from common.config import SysConfig
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines import get_engine
from .models import Instance


# 获取实例列表
@permission_required('sql.menu_instance', raise_exception=True)
def lists(request):
    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    type = request.POST.get('type')
    limit = offset + limit
    search = request.POST.get('search', '')

    if type:
        instances = Instance.objects.filter(instance_name__contains=search, type=type)[offset:limit] \
            .values("id", "instance_name", "db_type", "type", "host", "port", "user")
        count = Instance.objects.filter(instance_name__contains=search, type=type).count()
    else:
        instances = Instance.objects.filter(instance_name__contains=search)[offset:limit] \
            .values("id", "instance_name", "db_type", "type", "host", "port", "user")
        count = Instance.objects.filter(instance_name__contains=search).count()

    # QuerySet 序列化
    rows = [row for row in instances]

    result = {"total": count, "rows": rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 获取实例用户列表
@permission_required('sql.menu_instance', raise_exception=True)
def users(request):
    instance_id = request.POST.get('instance_id')
    try:
        instance = Instance.objects.get(id=instance_id)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    sql_get_user = '''select concat("\'", user, "\'", '@', "\'", host,"\'") as query from mysql.user;'''
    query_engine = get_engine(instance=instance)
    db_users = query_engine.query('mysql', sql_get_user).rows
    # 获取用户权限信息
    data = []
    for db_user in db_users:
        user_info = {}
        user_priv = query_engine.query('mysql', 'show grants for {};'.format(db_user[0]), close_conn=False).rows
        user_info['user'] = db_user[0]
        user_info['privileges'] = user_priv
        data.append(user_info)
    # 关闭连接
    query_engine.close()
    result = {'status': 0, 'msg': 'ok', 'data': data}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 对比实例schema信息
@permission_required('sql.menu_schemasync', raise_exception=True)
def schemasync(request):
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    target_instance_name = request.POST.get('target_instance_name')
    target_db_name = request.POST.get('target_db_name')
    sync_auto_inc = '--sync-auto-inc' if request.POST.get('sync_auto_inc') == 'true' else ''
    sync_comments = '--sync-comments' if request.POST.get('sync_comments') == 'true' else ''
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # diff 选项
    options = sync_auto_inc + ' ' + sync_comments

    # 循环对比全部数据库
    if db_name == 'all' or target_db_name == 'all':
        db_name = '*'
        target_db_name = '*'

    # 取出该实例的连接方式
    instance_info = Instance.objects.get(instance_name=instance_name)
    target_instance_info = Instance.objects.get(instance_name=target_instance_name)

    # 获取对比结果文件
    path = SysConfig().sys_config.get('schemasync', '')
    timestamp = int(time.time())
    output_directory = os.path.join(settings.BASE_DIR, 'downloads/schemasync/')

    command = path + " %s --output-directory=%s --tag=%s \
            mysql://%s:'%s'@%s:%d/%s  mysql://%s:'%s'@%s:%d/%s" % (options,
                                                               output_directory,
                                                               timestamp,
                                                               instance_info.user,
                                                               instance_info.raw_password,
                                                               instance_info.host,
                                                               instance_info.port,
                                                               db_name,
                                                               target_instance_info.user,
                                                               target_instance_info.raw_password,
                                                               target_instance_info.host,
                                                               target_instance_info.port,
                                                               target_db_name)
    diff = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            shell=True, universal_newlines=True)
    diff_stdout, diff_stderr = diff.communicate()

    # 非全部数据库对比可以读取对比结果并在前端展示
    if db_name != '*':
        date = time.strftime("%Y%m%d", time.localtime())
        patch_sql_file = '%s%s_%s.%s.patch.sql' % (output_directory, target_db_name, timestamp, date)
        revert_sql_file = '%s%s_%s.%s.revert.sql' % (output_directory, target_db_name, timestamp, date)
        cat_patch_sql = subprocess.Popen(['cat', patch_sql_file], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, universal_newlines=True)
        cat_revert_sql = subprocess.Popen(['cat', revert_sql_file], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT, universal_newlines=True)
        patch_stdout, patch_stderr = cat_patch_sql.communicate()
        revert_stdout, revert_stderr = cat_revert_sql.communicate()
        result['data'] = {'diff_stdout': diff_stdout, 'patch_stdout': patch_stdout, 'revert_stdout': revert_stdout}
    else:
        result['data'] = {'diff_stdout': diff_stdout, 'patch_stdout': '', 'revert_stdout': ''}

    # 删除对比文件
    # subprocess.call(['rm', '-rf', patch_sql_file, revert_sql_file, 'schemasync.log'])
    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取实例里面的数据库集合
def get_db_name_list(request):
    instance_name = request.POST.get('instance_name')
    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    try:
        # 取出该实例的连接方式，为了后面连进去获取所有databases
        query_engine = get_engine(instance=instance)
        db_list = query_engine.get_all_databases()
        # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
        result['data'] = db_list
        if not db_list:
            result['status'] = 1
            result['msg'] = '数据库列表为空, 可能是权限或配置有误'
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)

    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取数据库的表集合
def get_table_name_list(request):
    instance_name = request.POST.get('instance_name')
    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
    db_name = request.POST.get('db_name')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    try:
        # 取出该实例实例的连接方式，为了后面连进去获取所有的表
        query_engine = get_engine(instance=instance)
        table_list = query_engine.get_all_tables(db_name)
        # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
        result['data'] = table_list
        if not table_list:
            result['status'] = 1
            result['msg'] = '表列表为空, 可能是权限或配置有误, 请再次确认库名'
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)

    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取表里面的字段集合
def get_column_name_list(request):
    instance_name = request.POST.get('instance_name')
    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
    db_name = request.POST.get('db_name')
    tb_name = request.POST.get('tb_name')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    try:
        # 取出该实例的连接方式，为了后面连进去获取表的所有字段
        query_engine = get_engine(instance=instance)
        col_list = query_engine.get_all_columns_by_tb(db_name, tb_name)
        # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
        result['data'] = col_list
        if not col_list:
            result['status'] = 1
            result['msg'] = '字段列表为空, 可能是权限或配置有误'
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)
    return HttpResponse(json.dumps(result), content_type='application/json')


def describe(request):
    instance_name = request.POST.get('instance_name')
    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
    db_name = request.POST.get('db_name')
    tb_name = request.POST.get('tb_name')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    try:
        # 取出该实例的连接方式，为了后面连进去获取表的所有字段
        query_engine = get_engine(instance=instance)
        query_result = query_engine.descibe_table(db_name, tb_name)
        # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
        result['data'] = query_result.__dict__
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)
    return HttpResponse(json.dumps(result), content_type='application/json')
