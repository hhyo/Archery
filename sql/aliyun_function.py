# -*- coding: UTF-8 -*-

import simplejson as json
import datetime

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from .aliyun_api import Aliyun
from .permission import superuser_required

from .models import users, AliyunRdsConfig

aliyun = Aliyun()


# 获取SQL慢日志统计
@csrf_exempt
def slowquery_review(request):
    cluster_name = request.POST.get('cluster_name')
    DBName = request.POST.get('db_name')
    StartTime = request.POST.get('StartTime')
    EndTime = request.POST.get('EndTime')
    limit = request.POST.get('limit')
    offset = request.POST.get('offset')

    # 计算页数
    PageNumber = (int(offset) + int(limit)) / int(limit)
    values = {"PageSize": int(limit), "PageNumber": int(PageNumber)}
    # DBName非必传
    if DBName:
        values['DBName'] = DBName

    # UTC时间转化成阿里云需求的时间格式
    StartTime = '%sZ' % StartTime
    EndTime = '%sZ' % EndTime

    # 通过实例名称获取实例id
    cluster_info = AliyunRdsConfig.objects.get(cluster_name=cluster_name)
    # 调用aliyun接口获取SQL慢日志统计
    slowsql = aliyun.DescribeSlowLogs(cluster_info.rds_dbinstanceid, StartTime, EndTime, **values)

    # 解决table数据丢失精度、格式化时间
    SQLSlowLog = json.loads(slowsql)['Items']['SQLSlowLog']
    for SlowLog in SQLSlowLog:
        SlowLog['SQLId'] = str(SlowLog['SQLId'])
        SlowLog['CreateTime'] = aliyun.aliyun_time_format(SlowLog['CreateTime'])

    result = {"total": json.loads(slowsql)['TotalRecordCount'], "rows": SQLSlowLog,
              "PageSize": json.loads(slowsql)['PageRecordCount'], "PageNumber": json.loads(slowsql)['PageNumber']}
    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取SQL慢日志明细
@csrf_exempt
def slowquery_review_history(request):
    cluster_name = request.POST.get('cluster_name')
    StartTime = request.POST.get('StartTime')
    EndTime = request.POST.get('EndTime')
    DBName = request.POST.get('db_name')
    SQLId = request.POST.get('SQLId')
    limit = request.POST.get('limit')
    offset = request.POST.get('offset')

    # 计算页数
    PageNumber = (int(offset) + int(limit)) / int(limit)
    values = {"PageSize": int(limit), "PageNumber": int(PageNumber)}
    # SQLId、DBName非必传
    if SQLId:
        values['SQLId'] = SQLId
    if DBName:
        values['DBName'] = DBName

    # UTC时间转化成阿里云需求的时间格式
    StartTime = datetime.datetime.strptime(StartTime, "%Y-%m-%d").date() - datetime.timedelta(days=1)
    StartTime = '%sT16:00Z' % StartTime
    EndTime = '%sT15:59Z' % EndTime

    # 通过实例名称获取实例id
    cluster_info = AliyunRdsConfig.objects.get(cluster_name=cluster_name)
    # 调用aliyun接口获取SQL慢日志统计
    slowsql = aliyun.DescribeSlowLogRecords(cluster_info.rds_dbinstanceid, StartTime, EndTime, **values)

    # 格式化时间\过滤HostAddress
    SQLSlowRecord = json.loads(slowsql)['Items']['SQLSlowRecord']
    for SlowRecord in SQLSlowRecord:
        SlowRecord['ExecutionStartTime'] = aliyun.aliyun_time_format(SlowRecord['ExecutionStartTime']).strftime(
            "%Y-%m-%d %H:%M:%S")
        SlowRecord['HostAddress'] = SlowRecord['HostAddress'].split('[')[0]

    result = {"total": json.loads(slowsql)['TotalRecordCount'], "rows": SQLSlowRecord,
              "PageSize": json.loads(slowsql)['PageRecordCount'], "PageNumber": json.loads(slowsql)['PageNumber']}

    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 问题诊断--进程列表
@csrf_exempt
def process_status(request):
    cluster_name = request.POST.get('cluster_name')
    command_type = request.POST.get('command_type')

    if command_type is None or command_type == '':
        command_type = 'Query'

    # 通过实例名称获取实例id
    cluster_info = AliyunRdsConfig.objects.get(cluster_name=cluster_name)
    # 调用aliyun接口获取进程数据
    process_info = aliyun.RequestServiceOfCloudDBA(cluster_info.rds_dbinstanceid, 'ShowProcessList',
                                                   {"Language": "zh", "Command": command_type})

    # 提取进程列表
    process_list = json.loads(process_info)['AttrData']
    process_list = json.loads(process_list)['ProcessList']

    result = {'status': 0, 'msg': 'ok', 'data': process_list}

    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')


# 问题诊断--通过进程id构建请求id
@csrf_exempt
@superuser_required
def create_kill_session(request):
    cluster_name = request.POST.get('cluster_name')
    ThreadIDs = request.POST.get('ThreadIDs')

    # 获取用户信息
    loginUser = request.session.get('login_username', False)
    loginUserOb = users.objects.get(username=loginUser)

    result = {'status': 0, 'msg': 'ok', 'data': []}
    if loginUserOb.is_superuser:
        # 通过集群名称获取实例id
        cluster_info = AliyunRdsConfig.objects.get(cluster_name=cluster_name)
        # 调用aliyun接口获取进程数据
        request_info = aliyun.RequestServiceOfCloudDBA(cluster_info.rds_dbinstanceid, 'CreateKillSessionRequest',
                                                       {"Language": "zh", "ThreadIDs": json.loads(ThreadIDs)})

        # 提取进程列表
        request_list = json.loads(request_info)['AttrData']

        result['data'] = request_list

        # 返回查询结果
        return HttpResponse(json.dumps(result), content_type='application/json')
    else:
        result['status'] = 1
        result['msg'] = '你无权操作'
        return HttpResponse(json.dumps(result), content_type='application/json')


# 问题诊断--终止会话
@csrf_exempt
@superuser_required
def kill_session(request):
    cluster_name = request.POST.get('cluster_name')
    request_params = request.POST.get('request_params')

    # 获取用户信息
    loginUser = request.session.get('login_username', False)
    loginUserOb = users.objects.get(username=loginUser)

    result = {'status': 0, 'msg': 'ok', 'data': []}
    if loginUserOb.is_superuser:
        # 通过实例名称获取实例id
        cluster_info = AliyunRdsConfig.objects.get(cluster_name=cluster_name)
        # 调用aliyun接口获取进程数据
        request_params = json.loads(request_params)
        ServiceRequestParam = dict({"Language": "zh"}, **request_params)
        kill_result = aliyun.RequestServiceOfCloudDBA(cluster_info.rds_dbinstanceid, 'ConfirmKillSessionRequest',
                                                      ServiceRequestParam)

        # 获取处理结果
        kill_result = json.loads(kill_result)['AttrData']

        result['data'] = kill_result

        # 返回查询结果
        return HttpResponse(json.dumps(result), content_type='application/json')
    else:
        result['status'] = 1
        result['msg'] = '你无权操作'
        return HttpResponse(json.dumps(result), content_type='application/json')


# 问题诊断--空间列表
@csrf_exempt
def sapce_status(request):
    cluster_name = request.POST.get('cluster_name')

    # 通过实例名称获取实例id
    cluster_info = AliyunRdsConfig.objects.get(cluster_name=cluster_name)
    # 调用aliyun接口获取进程数据
    space_info = aliyun.RequestServiceOfCloudDBA(cluster_info.rds_dbinstanceid, 'GetSpaceStatForTables',
                                                 {"Language": "zh", "OrderType": "Data"})

    # 提取进程列表
    space_list = json.loads(space_info)['ListData']
    space_list = json.loads(space_list)

    result = {'status': 0, 'msg': 'ok', 'data': space_list}

    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type='application/json')
