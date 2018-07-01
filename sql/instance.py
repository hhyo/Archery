# -*- coding: UTF-8 -*-
import simplejson as json

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

from sql.utils.aes_decryptor import Prpcrypt
from sql.utils.dao import Dao
from .models import master_config, slave_config

dao = Dao()
prpCryptor = Prpcrypt()

# 获取实例里面的数据库集合
@csrf_exempt
def getdbNameList(request):
    clusterName = request.POST.get('cluster_name')
    is_master = request.POST.get('is_master')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    if is_master:
        try:
            master_info = master_config.objects.get(cluster_name=clusterName)
        except Exception:
            result['status'] = 1
            result['msg'] = '找不到对应的主库配置信息，请配置'
            return HttpResponse(json.dumps(result), content_type='application/json')

        try:
            # 取出该实例主库的连接方式，为了后面连进去获取所有databases
            listDb = dao.getAlldbByCluster(master_info.master_host, master_info.master_port, master_info.master_user,
                                           prpCryptor.decrypt(master_info.master_password))
            # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
            result['data'] = listDb
        except Exception as msg:
            result['status'] = 1
            result['msg'] = str(msg)

    else:
        try:
            slave_info = slave_config.objects.get(cluster_name=clusterName)
        except Exception:
            result['status'] = 1
            result['msg'] = '找不到对应的从库配置信息，请配置'
            return HttpResponse(json.dumps(result), content_type='application/json')

        try:
            # 取出该实例的连接方式，为了后面连进去获取所有databases
            listDb = dao.getAlldbByCluster(slave_info.slave_host, slave_info.slave_port, slave_info.slave_user,
                                           prpCryptor.decrypt(slave_info.slave_password))
            # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
            result['data'] = listDb
        except Exception as msg:
            result['status'] = 1
            result['msg'] = str(msg)

    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取数据库的表集合
@csrf_exempt
def getTableNameList(request):
    clusterName = request.POST.get('cluster_name')
    db_name = request.POST.get('db_name')
    is_master = request.POST.get('is_master')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    if is_master:
        try:
            master_info = master_config.objects.get(cluster_name=clusterName)
        except Exception:
            result['status'] = 1
            result['msg'] = '找不到对应的主库配置信息，请配置'
            return HttpResponse(json.dumps(result), content_type='application/json')

        try:
            # 取出该实例主库的连接方式，为了后面连进去获取所有的表
            listTb = dao.getAllTableByDb(master_info.master_host, master_info.master_port, master_info.master_user,
                                         prpCryptor.decrypt(master_info.master_password), db_name)
            # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
            result['data'] = listTb
        except Exception as msg:
            result['status'] = 1
            result['msg'] = str(msg)

    else:
        try:
            slave_info = slave_config.objects.get(cluster_name=clusterName)
        except Exception:
            result['status'] = 1
            result['msg'] = '找不到对应的从库配置信息，请配置'
            return HttpResponse(json.dumps(result), content_type='application/json')

        try:
            # 取出该实例从库的连接方式，为了后面连进去获取所有的表
            listTb = dao.getAllTableByDb(slave_info.slave_host, slave_info.slave_port, slave_info.slave_user,
                                         prpCryptor.decrypt(slave_info.slave_password), db_name)
            # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
            result['data'] = listTb
        except Exception as msg:
            result['status'] = 1
            result['msg'] = str(msg)

    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取表里面的字段集合
@csrf_exempt
def getColumnNameList(request):
    clusterName = request.POST.get('cluster_name')
    db_name = request.POST.get('db_name')
    tb_name = request.POST.get('tb_name')
    is_master = request.POST.get('is_master')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    if is_master:
        try:
            master_info = master_config.objects.get(cluster_name=clusterName)
        except Exception:
            result['status'] = 1
            result['msg'] = '找不到对应的主库配置信息，请配置'
            return HttpResponse(json.dumps(result), content_type='application/json')

        try:
            # 取出该实例主库的连接方式，为了后面连进去获取所有字段
            listCol = dao.getAllColumnsByTb(master_info.master_host, master_info.master_port, master_info.master_user,
                                            prpCryptor.decrypt(master_info.master_password), db_name, tb_name)
            # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
            result['data'] = listCol
        except Exception as msg:
            result['status'] = 1
            result['msg'] = str(msg)
    else:
        try:
            slave_info = slave_config.objects.get(cluster_name=clusterName)
        except Exception:
            result['status'] = 1
            result['msg'] = '找不到对应的从库配置信息，请配置'
            return HttpResponse(json.dumps(result), content_type='application/json')

        try:
            # 取出该实例的连接方式，为了后面连进去获取表的所有字段
            listCol = dao.getAllColumnsByTb(slave_info.slave_host, slave_info.slave_port, slave_info.slave_user,
                                            prpCryptor.decrypt(slave_info.slave_password), db_name, tb_name)
            # 要把result转成JSON存进数据库里，方便SQL单子详细信息展示
            result['data'] = listCol
        except Exception as msg:
            result['status'] = 1
            result['msg'] = str(msg)
    return HttpResponse(json.dumps(result), content_type='application/json')
