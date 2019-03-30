# -*- coding: UTF-8 -*-
import os
import time

import simplejson as json
from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse

from common.config import SysConfig
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines import get_engine
from sql.plugins.schemasync import SchemaSync
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
        instances_obj = Instance.objects.filter(instance_name__icontains=search, type=type)
    else:
        instances_obj = Instance.objects.filter(instance_name__icontains=search)

    count = instances_obj.count()
    instances = instances_obj[offset:limit].values("id", "instance_name", "db_type", "type", "host", "port", "user")
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
    result = {'status': 0, 'msg': 'ok', 'rows': data}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 对比实例schema信息
@permission_required('sql.menu_schemasync', raise_exception=True)
def schemasync(request):
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    target_instance_name = request.POST.get('target_instance_name')
    target_db_name = request.POST.get('target_db_name')
    sync_auto_inc = True if request.POST.get('sync_auto_inc') == 'true' else False
    sync_comments = True if request.POST.get('sync_comments') == 'true' else False
    result = {'status': 0, 'msg': 'ok', 'data': {'diff_stdout': '', 'patch_stdout': '', 'revert_stdout': ''}}

    # 循环对比全部数据库
    if db_name == 'all' or target_db_name == 'all':
        db_name = '*'
        target_db_name = '*'

    # 取出该实例的连接方式
    instance_info = Instance.objects.get(instance_name=instance_name)
    target_instance_info = Instance.objects.get(instance_name=target_instance_name)

    # 检查SchemaSync程序路径
    path = SysConfig().get('schemasync')
    if path is None:
        result['status'] = 1
        result['msg'] = '请配置SchemaSync路径！'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 提交给SchemaSync获取对比结果
    schema_sync = SchemaSync()
    # 准备参数
    tag = int(time.time())
    output_directory = os.path.join(settings.BASE_DIR, 'downloads/schemasync/')
    args = {
        "sync-auto-inc": sync_auto_inc,
        "sync-comments": sync_comments,
        "tag": tag,
        "output-directory": output_directory,
        "source": r"mysql://{user}:'{pwd}'@{host}:{port}/{database}".format(user=instance_info.user,
                                                                            pwd=instance_info.raw_password,
                                                                            host=instance_info.host,
                                                                            port=instance_info.port,
                                                                            database=db_name),
        "target": r"mysql://{user}:'{pwd}'@{host}:{port}/{database}".format(user=target_instance_info.user,
                                                                            pwd=target_instance_info.raw_password,
                                                                            host=target_instance_info.host,
                                                                            port=target_instance_info.port,
                                                                            database=target_db_name)
    }
    # 参数检查
    args_check_result = schema_sync.check_args(args)
    if args_check_result['status'] == 1:
        return HttpResponse(json.dumps(args_check_result), content_type='application/json')
    # 参数转换
    cmd_args = schema_sync.generate_args2cmd(args, shell=True)
    # 执行命令
    try:
        stdout, stderr = schema_sync.execute_cmd(cmd_args, shell=True).communicate()
        diff_stdout = f'{stdout}{stderr}'
    except RuntimeError as e:
        diff_stdout = str(e)

    # 非全部数据库对比可以读取对比结果并在前端展示
    if db_name != '*':
        date = time.strftime("%Y%m%d", time.localtime())
        patch_sql_file = '%s%s_%s.%s.patch.sql' % (output_directory, target_db_name, tag, date)
        revert_sql_file = '%s%s_%s.%s.revert.sql' % (output_directory, target_db_name, tag, date)
        try:
            with open(patch_sql_file, 'r') as f:
                patch_sql = f.read()
        except FileNotFoundError as e:
            patch_sql = str(e)
        try:
            with open(revert_sql_file, 'r') as f:
                revert_sql = f.read()
        except FileNotFoundError as e:
            revert_sql = str(e)
        result['data'] = {'diff_stdout': diff_stdout, 'patch_stdout': patch_sql, 'revert_stdout': revert_sql}
    else:
        result['data'] = {'diff_stdout': diff_stdout, 'patch_stdout': '', 'revert_stdout': ''}

    return HttpResponse(json.dumps(result), content_type='application/json')


def instance_resource(request):
    """
    获取实例内的资源信息，database、schema、table、column
    :param request:
    :return:
    """
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    schema_name = request.POST.get('schema_name')
    tb_name = request.POST.get('tb_name')

    resource_type = request.POST.get('resource_type')
    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    try:
        query_engine = get_engine(instance=instance)
        if resource_type == 'database':
            resource = query_engine.get_all_databases()
        elif resource_type == 'schema' and db_name:
            resource = query_engine.get_all_schemas(db_name=db_name)
        elif resource_type == 'table' and (db_name or schema_name):
            resource = query_engine.get_all_tables(db_name=db_name, schema_name=schema_name)
        elif resource_type == 'column' and db_name and tb_name:
            resource = query_engine.get_all_columns_by_tb(db_name=db_name, schema_name=schema_name, tb_name=tb_name)
        else:
            raise TypeError('不支持的资源类型或者参数不完整！')
        result['data'] = resource
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
    schema_name = request.POST.get('schema_name')
    tb_name = request.POST.get('tb_name')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    try:
        query_engine = get_engine(instance=instance)
        query_result = query_engine.describe_table(db_name, tb_name, schema_name)
        result['data'] = query_result.__dict__
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)
    return HttpResponse(json.dumps(result), content_type='application/json')
