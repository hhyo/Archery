# -*- coding: UTF-8 -*-
import simplejson as json
from django.db.models import F

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

from sql.utils.aes_decryptor import Prpcrypt
from sql.utils.dao import Dao
from sql.utils.extend_json_encoder import ExtendJSONEncoder
from .models import Instance

prpCryptor = Prpcrypt()


# 获取实例列表
@csrf_exempt
def lists(request):
    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit

    # 获取搜索参数
    search = request.POST.get('search')
    if search is None:
        search = ''

    instances = Instance.objects.filter(instance_name__contains=search)[offset:limit] \
        .values("id", "instance_name", "db_type", "type", "host", "port", "user", "create_time")
    count = Instance.objects.filter(instance_name__contains=search).count()

    # QuerySet 序列化
    rows = [row for row in instances]

    result = {"total": count, "rows": rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 获取实例用户列表
@csrf_exempt
def users(request):
    instance_id = request.POST.get('instance_id')
    instance_name = Instance.objects.get(id=instance_id).instance_name
    sql_get_user = '''select concat("\'", user, "\'", '@', "\'", host,"\'") as query from mysql.user;'''
    dao = Dao(instance_name=instance_name)
    db_users = dao.mysql_query('mysql', sql_get_user)['rows']
    # 获取用户权限信息
    data = []
    for db_user in db_users:
        user_info = {}
        user_priv = dao.mysql_query('mysql', 'show grants for {};'.format(db_user[0]))['rows']
        user_info['user'] = db_user[0]
        user_info['privileges'] = user_priv
        data.append(user_info)

    result = {'status': 0, 'msg': 'ok', 'data': data}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 获取实例里面的数据库集合
@csrf_exempt
def getdbNameList(request):
    instance_name = request.POST.get('instance_name')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    try:
        # 取出该实例的连接方式，为了后面连进去获取所有databases
        db_list = Dao(instance_name=instance_name).getAlldbByCluster()
        # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
        result['data'] = db_list
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)

    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取数据库的表集合
@csrf_exempt
def getTableNameList(request):
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    try:
        # 取出该实例从库的连接方式，为了后面连进去获取所有的表
        tb_list = Dao(instance_name=instance_name).getAllTableByDb(db_name)
        # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
        result['data'] = tb_list
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)

    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取表里面的字段集合
@csrf_exempt
def getColumnNameList(request):
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    tb_name = request.POST.get('tb_name')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    try:
        # 取出该实例的连接方式，为了后面连进去获取表的所有字段
        col_list = Dao(instance_name=instance_name).getAllColumnsByTb(db_name, tb_name)
        # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
        result['data'] = col_list
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)
    return HttpResponse(json.dumps(result), content_type='application/json')
