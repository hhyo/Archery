# -*- coding: UTF-8 -*-
import datetime
import traceback

from aliyunsdkcore import client
from aliyunsdkrds.request.v20140815 import DescribeSlowLogsRequest, DescribeSlowLogRecordsRequest, \
    RequestServiceOfCloudDBARequest
import simplejson as json
from sql.models import AliyunAccessKey
import logging

logger = logging.getLogger('default')


class Aliyun(object):
    def __init__(self):
        try:
            auth = AliyunAccessKey.objects.get(is_enable=True)
            ak = auth.raw_ak
            secret = auth.raw_secret
        except Exception:
            logger.error(traceback.format_exc())
            logger.error('没有找到有效的ak信息！')
        else:
            self.clt = client.AcsClient(
                ak=ak,
                secret=secret)

    def request_api(self, request, *values):
        if values:
            for value in values:
                for k, v in value.items():
                    request.add_query_param(k, v)
        request.set_accept_format('json')
        result = self.clt.do_action_with_exception(request)
        return json.dumps(json.loads(result.decode('utf-8')), indent=4, sort_keys=False, ensure_ascii=False)

    # 阿里云2017-12-10T16:00:00Z时间加上8小时时区显示
    @staticmethod
    def aliyun_time_format(str_time):
        if 'T' in str_time:
            Ymd = str_time.split('T')[0]
            HMS = str_time.split('T')[1].split('Z')[0]
            str_time = '%s %s' % (Ymd, HMS)
            time = datetime.datetime.strptime(str_time, "%Y-%m-%d %H:%M:%S")
            format_time = time + datetime.timedelta(hours=8)
        elif 'Z' in str_time:
            Ymd = str_time.split('Z')[0]
            format_time = '%s' % Ymd
        else:
            format_time = str_time
        return format_time

    def DescribeSlowLogs(self, DBInstanceId, StartTime, EndTime, **kwargs):
        '''获取实例慢日志列表
        DBName,SortKey、PageSize、PageNumber'''
        request = DescribeSlowLogsRequest.DescribeSlowLogsRequest()
        values = {"action_name": "DescribeSlowLogs", "DBInstanceId": DBInstanceId,
                  "StartTime": StartTime, "EndTime": EndTime, "SortKey": "TotalExecutionCounts"}
        values = dict(values, **kwargs)
        result = self.request_api(request, values)
        return result

    def DescribeSlowLogRecords(self, DBInstanceId, StartTime, EndTime, **kwargs):
        '''查看慢日志明细
        SQLId,DBName、PageSize、PageNumber'''
        request = DescribeSlowLogRecordsRequest.DescribeSlowLogRecordsRequest()
        values = {"action_name": "DescribeSlowLogRecords", "DBInstanceId": DBInstanceId,
                  "StartTime": StartTime, "EndTime": EndTime}
        values = dict(values, **kwargs)
        result = self.request_api(request, values)
        return result

    def RequestServiceOfCloudDBA(self, DBInstanceId, ServiceRequestType, ServiceRequestParam, **kwargs):
        '''
        获取统计信息：'GetTimedMonData',{"Language":"zh","KeyGroup":"mem_cpu_usage","KeyName":"","StartTime":"2018-01-15T04:03:26Z","EndTime":"2018-01-15T05:03:26Z"}
            mem_cpu_usage、iops_usage、detailed_disk_space
        获取process信息：'ShowProcessList',{"Language":"zh","Command":"Query"}  -- Not Sleep , All
        终止进程：'ConfirmKillSessionRequest',{"Language":"zh","SQLRequestID":75865,"SQLStatement":"kill 34022786;"}
        获取表空间信息：'GetSpaceStatForTables',{"Language": "zh", "OrderType": "Data"}
        获取资源利用信息：'GetResourceUsage',{"Language":"zh"}
        '''
        request = RequestServiceOfCloudDBARequest.RequestServiceOfCloudDBARequest()
        values = {"action_name": "RequestServiceOfCloudDBA", "DBInstanceId": DBInstanceId,
                  "ServiceRequestType": ServiceRequestType, "ServiceRequestParam": ServiceRequestParam}
        values = dict(values, **kwargs)
        result = self.request_api(request, values)
        return result
