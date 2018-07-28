# -*- coding: UTF-8 -*-
import simplejson as json
from django.db.models import F

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

from sql.utils.aes_decryptor import Prpcrypt
from sql.utils.dao import Dao
from sql.utils.extend_json_encoder import ExtendJSONEncoder
from .models import Instance, SlaveConfig

prpCryptor = Prpcrypt()


# 获取实例列表
@csrf_exempt
def lists(request):
    is_master = int(request.POST.get('is_master', 0))
    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit

    # 获取搜索参数
    search = request.POST.get('search')
    if search is None:
        search = ''
    if is_master:
        instances = Instance.objects.filter(cluster_name__contains=search)[offset:limit] \
            .annotate(name=F('cluster_name'),
                      host=F('master_host'),
                      port=F('master_port'),
                      user=F('master_user'),
                      ).values("id", "name", "host", "port", "user", "create_time")
        count = Instance.objects.filter(cluster_name__contains=search).count()
    else:
        instances = SlaveConfig.objects.filter(cluster_name__contains=search)[offset:limit] \
            .annotate(name=F('cluster_name'),
                      host=F('slave_host'),
                      port=F('slave_port'),
                      user=F('slave_user'),
                      ).values("id", "name", "host", "port", "user", "create_time")
        count = Instance.objects.filter(cluster_name__contains=search).count()

    # QuerySet 序列化
    rows = [row for row in instances]

    result = {"total": count, "rows": rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 获取实例用户列表
@csrf_exempt
def user_list(request):
    instance_name = request.POST.get('instance_name')
    is_master = int(request.POST.get('is_master', 0))
    if is_master:
        Instance.objects.get('')

    # QuerySet 序列化
    rows = [row for row in instances]

    result = {'status': 0, 'msg': 'ok', 'data': rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 获取实例里面的数据库集合
@csrf_exempt
def getdbNameList(request):
    cluster_name = request.POST.get('cluster_name')
    is_master = int(request.POST.get('is_master', 0))
    result = {'status': 0, 'msg': 'ok', 'data': []}

    try:
        # 取出该实例的连接方式，为了后面连进去获取所有databases
        db_list = Dao(instance_name=cluster_name, is_master=is_master).getAlldbByCluster()
        # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
        result['data'] = db_list
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)

    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取数据库的表集合
@csrf_exempt
def getTableNameList(request):
    cluster_name = request.POST.get('cluster_name')
    db_name = request.POST.get('db_name')
    is_master = int(request.POST.get('is_master', 0))
    result = {'status': 0, 'msg': 'ok', 'data': []}

    try:
        # 取出该实例从库的连接方式，为了后面连进去获取所有的表
        tb_list = Dao(instance_name=cluster_name, is_master=is_master).getAllTableByDb(db_name)
        # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
        result['data'] = tb_list
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)

    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取表里面的字段集合
@csrf_exempt
def getColumnNameList(request):
    cluster_name = request.POST.get('cluster_name')
    db_name = request.POST.get('db_name')
    tb_name = request.POST.get('tb_name')
    is_master = int(request.POST.get('is_master', 0))
    result = {'status': 0, 'msg': 'ok', 'data': []}

    try:
        # 取出该实例的连接方式，为了后面连进去获取表的所有字段
        col_list = Dao(instance_name=cluster_name, is_master=is_master).getAllColumnsByTb(db_name, tb_name)
        # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
        result['data'] = col_list
    except Exception as msg:
        result['status'] = 1
        result['msg'] = str(msg)
    return HttpResponse(json.dumps(result), content_type='application/json')
