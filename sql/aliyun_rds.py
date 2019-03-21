# -*- coding: UTF-8 -*-

import simplejson as json
import datetime

from common.utils.aliyun_sdk import Aliyun
from .models import AliyunRdsConfig


# 获取SQL慢日志统计
def slowquery_review(request):
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    start_time = request.POST.get('StartTime')
    end_time = request.POST.get('EndTime')
    limit = request.POST.get('limit')
    offset = request.POST.get('offset')

    # 计算页数
    page_number = (int(offset) + int(limit)) / int(limit)
    values = {"PageSize": int(limit), "PageNumber": int(page_number)}
    # DBName非必传
    if db_name:
        values['DBName'] = db_name

    # UTC时间转化成阿里云需求的时间格式
    start_time = '%sZ' % start_time
    end_time = '%sZ' % end_time

    # 通过实例名称获取关联的rds实例id
    instance_info = AliyunRdsConfig.objects.get(instance__instance_name=instance_name)
    # 调用aliyun接口获取SQL慢日志统计
    slowsql = Aliyun().DescribeSlowLogs(instance_info.rds_dbinstanceid, start_time, end_time, **values)

    # 解决table数据丢失精度、格式化时间
    sql_slow_log = json.loads(slowsql)['Items']['SQLSlowLog']
    for SlowLog in sql_slow_log:
        SlowLog['SQLId'] = str(SlowLog['SQLHASH'])
        SlowLog['CreateTime'] = Aliyun.aliyun_time_format(SlowLog['CreateTime'])

    result = {"total": json.loads(slowsql)['TotalRecordCount'], "rows": sql_slow_log,
              "PageSize": json.loads(slowsql)['PageRecordCount'], "PageNumber": json.loads(slowsql)['PageNumber']}
    # 返回查询结果
    return result


# 获取SQL慢日志明细
def slowquery_review_history(request):
    instance_name = request.POST.get('instance_name')
    start_time = request.POST.get('StartTime')
    end_time = request.POST.get('EndTime')
    db_name = request.POST.get('db_name')
    sql_id = request.POST.get('SQLId')
    limit = request.POST.get('limit')
    offset = request.POST.get('offset')

    # 计算页数
    page_number = (int(offset) + int(limit)) / int(limit)
    values = {"PageSize": int(limit), "PageNumber": int(page_number)}
    # SQLId、DBName非必传
    if sql_id:
        values['SQLHASH'] = sql_id
    if db_name:
        values['DBName'] = db_name

    # UTC时间转化成阿里云需求的时间格式
    start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d").date() - datetime.timedelta(days=1)
    start_time = '%sT16:00Z' % start_time
    end_time = '%sT15:59Z' % end_time

    # 通过实例名称获取关联的rds实例id
    instance_info = AliyunRdsConfig.objects.get(instance__instance_name=instance_name)
    # 调用aliyun接口获取SQL慢日志统计
    slowsql = Aliyun().DescribeSlowLogRecords(instance_info.rds_dbinstanceid, start_time, end_time, **values)

    # 格式化时间\过滤HostAddress
    sql_slow_record = json.loads(slowsql)['Items']['SQLSlowRecord']
    for SlowRecord in sql_slow_record:
        SlowRecord['ExecutionStartTime'] = Aliyun.aliyun_time_format(SlowRecord['ExecutionStartTime']).strftime(
            "%Y-%m-%d %H:%M:%S")
        SlowRecord['HostAddress'] = SlowRecord['HostAddress'].split('[')[0]

    result = {"total": json.loads(slowsql)['TotalRecordCount'], "rows": sql_slow_record,
              "PageSize": json.loads(slowsql)['PageRecordCount'], "PageNumber": json.loads(slowsql)['PageNumber']}

    # 返回查询结果
    return result


# 问题诊断--进程列表
def process_status(request):
    instance_name = request.POST.get('instance_name')
    command_type = request.POST.get('command_type')

    if command_type is None or command_type == '':
        command_type = 'Query'

    # 通过实例名称获取关联的rds实例id
    instance_info = AliyunRdsConfig.objects.get(instance__instance_name=instance_name)
    # 调用aliyun接口获取进程数据
    process_info = Aliyun().RequestServiceOfCloudDBA(instance_info.rds_dbinstanceid, 'ShowProcessList',
                                                     {"Language": "zh", "Command": command_type})

    # 提取进程列表
    process_list = json.loads(process_info)['AttrData']
    process_list = json.loads(process_list)['ProcessList']

    result = {'status': 0, 'msg': 'ok', 'rows': process_list}

    # 返回查询结果
    return result


# 问题诊断--通过进程id构建请求id
def create_kill_session(request):
    instance_name = request.POST.get('instance_name')
    thread_ids = request.POST.get('ThreadIDs')

    result = {'status': 0, 'msg': 'ok', 'data': []}
    # 通过实例名称获取关联的rds实例id
    instance_info = AliyunRdsConfig.objects.get(instance__instance_name=instance_name)
    # 调用aliyun接口获取进程数据
    request_info = Aliyun().RequestServiceOfCloudDBA(instance_info.rds_dbinstanceid, 'CreateKillSessionRequest',
                                                     {"Language": "zh", "ThreadIDs": json.loads(thread_ids)})

    # 提取进程列表
    request_list = json.loads(request_info)['AttrData']

    result['data'] = request_list

    # 返回处理结果
    return result


# 问题诊断--终止会话
def kill_session(request):
    instance_name = request.POST.get('instance_name')
    request_params = request.POST.get('request_params')

    result = {'status': 0, 'msg': 'ok', 'data': []}
    # 通过实例名称获取关联的rds实例id
    instance_info = AliyunRdsConfig.objects.get(instance__instance_name=instance_name)
    # 调用aliyun接口获取终止进程
    request_params = json.loads(request_params)
    service_request_param = dict({"Language": "zh"}, **request_params)
    kill_result = Aliyun().RequestServiceOfCloudDBA(instance_info.rds_dbinstanceid, 'ConfirmKillSessionRequest',
                                                    service_request_param)

    # 获取处理结果
    kill_result = json.loads(kill_result)['AttrData']

    result['data'] = kill_result

    # 返回查询结果
    return result


# 问题诊断--空间列表
def sapce_status(request):
    instance_name = request.POST.get('instance_name')

    # 通过实例名称获取关联的rds实例id
    instance_info = AliyunRdsConfig.objects.get(instance__instance_name=instance_name)
    # 调用aliyun接口获取进程数据
    space_info = Aliyun().RequestServiceOfCloudDBA(instance_info.rds_dbinstanceid, 'GetSpaceStatForTables',
                                                   {"Language": "zh", "OrderType": "Data"})

    # 提取进程列表
    space_list = json.loads(space_info)['ListData']
    if space_list:
        space_list = json.loads(space_list)
    else:
        space_list = []

    result = {'status': 0, 'msg': 'ok', 'rows': space_list}

    # 返回查询结果
    return result
