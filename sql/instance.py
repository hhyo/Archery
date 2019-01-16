# -*- coding: UTF-8 -*-
import os
import subprocess
import time

import simplejson as json
from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, QueryDict

from common.config import SysConfig
from common.utils.aes_decryptor import Prpcrypt
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines import get_engine
from sql.utils.dao import Dao

from .models import Instance, ParamTemp, ParamHistory


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
    instance_name = Instance.objects.get(id=instance_id).instance_name
    sql_get_user = '''select concat("\'", user, "\'", '@', "\'", host,"\'") as query from mysql.user;'''
    dao = Dao(instance_name=instance_name, flag=True)
    db_users = dao.mysql_query('mysql', sql_get_user)['rows']
    # 获取用户权限信息
    data = []
    for db_user in db_users:
        user_info = {}
        user_priv = dao.mysql_query('mysql', 'show grants for {};'.format(db_user[0]))['rows']
        user_info['user'] = db_user[0]
        user_info['privileges'] = user_priv
        data.append(user_info)
    # 关闭连接
    dao.close()
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

    command = path + ' %s --output-directory=%s --tag=%s \
            mysql://%s:%s@%s:%d/%s  mysql://%s:%s@%s:%d/%s' % (options,
                                                               output_directory,
                                                               timestamp,
                                                               instance_info.user,
                                                               Prpcrypt().decrypt(instance_info.password),
                                                               instance_info.host,
                                                               instance_info.port,
                                                               db_name,
                                                               target_instance_info.user,
                                                               Prpcrypt().decrypt(target_instance_info.password),
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


@permission_required('sql.param_view', raise_exception=True)
def param_list(request):
    instance_name = request.POST.get('instance_name')
    search = request.POST.get('search', '')
    try:
        ins = Instance.objects.get(instance_name=instance_name)
        params = dict()
        for p in ParamTemp.objects.filter(db_type=ins.db_type, param__contains=search):
            params[p.param] = [p.default_var, p.is_reboot, p.available_var, p.description]
        p_list = list(params.keys())
        sql = "SELECT * FROM `information_schema`.`GLOBAL_VARIABLES` WHERE VARIABLE_NAME in ('{}');".format("','".join(p_list))
        col_list = Dao(instance_name=instance_name).mysql_query('information_schema', sql)
        print(sql, col_list)
        res = list()
        for idx, val in col_list['rows']:
            res.append({
                'p': idx,
                'd_v': params[idx][0],
                'rb': '是' if params[idx][1] == 1 else '否',
                'a_v': params[idx][2],
                'desc': params[idx][3],
                'r_v': val
            })
    except Instance.DoesNotExist:
        print('Instance.DoesNotExist')
    except Exception as e:
        print(e)
    return HttpResponse(json.dumps(res, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.param_view', raise_exception=True)
def param_history(request):
    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit
    instance_name = request.POST.get('instance_name')
    search = request.POST.get('search', '')
    if search:
        phs = ParamHistory.objects.filter(instance__instance_name=instance_name)[offset:limit]
    else:
        phs = ParamHistory.objects.filter(instance__instance_name=instance_name, param__contains=search)[offset:limit]
    res = list()
    for r in phs:
        is_active = '是' if r.is_active == 1 else '否'
        res.append({"id": r.id, "p": r.param, "old_v": r.old_var, "new_v": r.new_var, "act": is_active, "t": r.create_time})
    result = {'total': len(res), 'rows': res}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@csrf_exempt
@permission_required('sql.param_edit', raise_exception=True)
def param_save(request):
    post_data = QueryDict(request.body).dict()
    instance_name = post_data['instance_name']
    param = post_data['p']
    run_v = post_data['r_v']

    try:
        sql = "SELECT * FROM `information_schema`.`GLOBAL_VARIABLES` WHERE VARIABLE_NAME='{}';".format(param)
        col_list = Dao(instance_name=instance_name).mysql_query('information_schema', sql)
        p = col_list['rows'][0]
        if p[0] == run_v:
            return HttpResponse(json.dumps({'status': 1, 'msg': '参数与实际一致，未调整！'}), content_type='application/json')
        else:
            ph = ParamHistory.objects.create(instance=Instance.objects.get(instance_name=instance_name), param=param,
                                             old_var=p[1], new_var=run_v)
            sql = "UPDATE GLOBAL_VARIABLES SET VARIABLE_VALUE ='{}' WHERE VARIABLE_NAME='{}';".format(run_v, param)
            col_list = Dao(instance_name=instance_name).mysql_query('information_schema', sql)
            if 'Error' in col_list:
                ph.is_active = 1
                res = {'status': 1, 'msg': col_list['Error']}
            else:
                ph.is_active = 0
                res = {'status': 0, 'msg': '更新成功！'}
            ph.save()
    except Exception as e:
        res = {'status': 1, 'msg': str(e)}
    return HttpResponse(json.dumps(res), content_type='application/json')
