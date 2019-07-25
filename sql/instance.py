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
from .models import Instance, ParamTemplate, ParamHistory


@permission_required('sql.menu_instance', raise_exception=True)
def lists(request):
    """获取实例列表"""
    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    type = request.POST.get('type')
    db_type = request.POST.get('db_type')
    tags = request.POST.getlist('tags[]')
    limit = offset + limit
    search = request.POST.get('search', '')

    # 组合筛选项
    filter_dict = dict()
    # 过滤搜索
    if search:
        filter_dict['instance_name__icontains'] = search
    # 过滤实例类型
    if type:
        filter_dict['type'] = type
    # 过滤数据库类型
    if db_type:
        filter_dict['db_type'] = db_type

    instances = Instance.objects.filter(**filter_dict)
    # 过滤标签，返回同时包含全部标签的实例，TODO 循环会生成多表JOIN，如果数据量大会存在效率问题
    if tags:
        for tag in tags:
            instances = instances.filter(instancetagrelations__instance_tag=tag,
                                         instancetag__active=True,
                                         instancetagrelations__active=True)

    count = instances.count()
    instances = instances[offset:limit].values("id", "instance_name", "db_type", "type", "host", "port", "user")
    # QuerySet 序列化
    rows = [row for row in instances]

    result = {"total": count, "rows": rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.menu_instance', raise_exception=True)
def users(request):
    """获取实例用户列表"""
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


@permission_required('sql.param_view', raise_exception=True)
def param_list(request):
    """
    获取实例参数列表
    :param request:
    :return:
    """
    instance_id = request.POST.get('instance_id')
    editable = True if request.POST.get('editable') else False
    search = request.POST.get('search', '')
    try:
        ins = Instance.objects.get(id=instance_id)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
    # 获取已配置参数列表
    cnf_params = dict()
    for param in ParamTemplate.objects.filter(db_type=ins.db_type, variable_name__contains=search).values(
            'id', 'variable_name', 'default_value', 'valid_values', 'description', 'editable'):
        param['variable_name'] = param['variable_name'].lower()
        cnf_params[param['variable_name']] = param
    # 获取实例参数列表
    engine = get_engine(instance=ins)
    ins_variables = engine.get_variables()
    # 处理结果
    rows = list()
    for variable in ins_variables.rows:
        variable_name = variable[0].lower()
        row = {
            'variable_name': variable_name,
            'runtime_value': variable[1],
            'editable': False,
        }
        if variable_name in cnf_params.keys():
            row = dict(row, **cnf_params[variable_name])
        rows.append(row)
    # 过滤参数
    if editable:
        rows = [row for row in rows if row['editable']]
    else:
        rows = [row for row in rows if not row['editable']]
    return HttpResponse(json.dumps(rows, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.param_view', raise_exception=True)
def param_history(request):
    """实例参数修改历史"""
    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit
    instance_id = request.POST.get('instance_id')
    search = request.POST.get('search', '')
    phs = ParamHistory.objects.filter(instance__id=instance_id)
    # 过滤搜索条件
    if search:
        phs = ParamHistory.objects.filter(variable_name__contains=search)
    count = phs.count()
    phs = phs[offset:limit].values("instance__instance_name", "variable_name", "old_var", "new_var",
                                   "user_display", "create_time")
    # QuerySet 序列化
    rows = [row for row in phs]

    result = {"total": count, "rows": rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.param_edit', raise_exception=True)
def param_edit(request):
    user = request.user
    instance_id = request.POST.get('instance_id')
    variable_name = request.POST.get('variable_name')
    variable_value = request.POST.get('runtime_value')

    try:
        ins = Instance.objects.get(id=instance_id)
    except Instance.DoesNotExist:
        result = {'status': 1, 'msg': '实例不存在', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 修改参数
    engine = get_engine(instance=ins)
    # 校验是否配置模板
    if not ParamTemplate.objects.filter(variable_name=variable_name).exists():
        result = {'status': 1, 'msg': '请先在参数模板中配置该参数！', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
    # 获取当前运行参数值
    runtime_value = engine.get_variables(variables=[variable_name]).rows[0][1]
    if variable_value == runtime_value:
        result = {'status': 1, 'msg': '参数值与实际运行值一致，未调整！', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
    set_result = engine.set_variable(variable_name=variable_name, variable_value=variable_value)
    if set_result.error:
        result = {'status': 1, 'msg': f'设置错误，错误信息：{set_result.error}', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')
    # 修改成功的保存修改记录
    else:
        ParamHistory.objects.create(
            instance=ins,
            variable_name=variable_name,
            old_var=runtime_value,
            new_var=variable_value,
            set_sql=set_result.full_sql,
            user_name=user.username,
            user_display=user.display
        )
        result = {'status': 0, 'msg': '修改成功，请手动持久化到配置文件！', 'data': []}
    return HttpResponse(json.dumps(result), content_type='application/json')


@permission_required('sql.menu_schemasync', raise_exception=True)
def schemasync(request):
    """对比实例schema信息"""
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
        elif resource_type == 'table' and db_name:
            if schema_name:
                resource = query_engine.get_all_tables(db_name=db_name, schema_name=schema_name)
            else:
                resource = query_engine.get_all_tables(db_name=db_name)
        elif resource_type == 'column' and db_name and tb_name:
            if schema_name:
                resource = query_engine.get_all_columns_by_tb(db_name=db_name, schema_name=schema_name, tb_name=tb_name)
            else:
                resource = query_engine.get_all_columns_by_tb(db_name=db_name, tb_name=tb_name)
        else:
            raise TypeError('不支持的资源类型或者参数不完整！')
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)
    else:
        if resource.error:
            result['status'] = 1
            result['msg'] = resource.error
        else:
            result['data'] = resource.rows
    return HttpResponse(json.dumps(result), content_type='application/json')


def describe(request):
    """获取表结构"""
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
        if schema_name:
            query_result = query_engine.describe_table(db_name, tb_name, schema_name)
        else:
            query_result = query_engine.describe_table(db_name, tb_name)
        result['data'] = query_result.__dict__
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)
    return HttpResponse(json.dumps(result), content_type='application/json')
