# -*- coding: UTF-8 -*-
import datetime
import traceback

from aliyunsdkcore.client import AcsClient
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
            self.clt = AcsClient(ak=ak, secret=secret)
        except Exception as m:
            raise Exception(f'阿里云认证失败：{m}{traceback.format_exc()}')
            logger.error(f'阿里云认证失败：{m}{traceback.format_exc()}')

    def request_api(self, request, *values):
        if values:
            for value in values:
                for k, v in value.items():
                    request.add_query_param(k, v)
        request.set_accept_format('json')
        result = self.clt.do_action_with_exception(request)
        return json.dumps(json.loads(result.decode('utf-8')), indent=4, sort_keys=False, ensure_ascii=False)

    # 阿里云UTC时间转换为本地时区时间
    @staticmethod
    def utc2local(utc, utc_format):
        utc_time = datetime.datetime.strptime(utc, utc_format)
        local_tm = datetime.datetime.fromtimestamp(0)
        utc_tm = datetime.datetime.utcfromtimestamp(0)
        localtime = utc_time + (local_tm - utc_tm)
        return localtime

    def DescribeSlowLogs(self, DBInstanceId, StartTime, EndTime, **kwargs):
        """获取实例慢日志列表DBName,SortKey、PageSize、PageNumber"""
        request = DescribeSlowLogsRequest.DescribeSlowLogsRequest()
        values = {"action_name": "DescribeSlowLogs", "DBInstanceId": DBInstanceId,
                  "StartTime": StartTime, "EndTime": EndTime, "SortKey": "TotalExecutionCounts"}
        values = dict(values, **kwargs)
        result = self.request_api(request, values)
        return result

    def DescribeSlowLogRecords(self, DBInstanceId, StartTime, EndTime, **kwargs):
        """查看慢日志明细SQLId,DBName、PageSize、PageNumber"""
        request = DescribeSlowLogRecordsRequest.DescribeSlowLogRecordsRequest()
        values = {"action_name": "DescribeSlowLogRecords", "DBInstanceId": DBInstanceId,
                  "StartTime": StartTime, "EndTime": EndTime}
        values = dict(values, **kwargs)
        result = self.request_api(request, values)
        return result

    def RequestServiceOfCloudDBA(self, DBInstanceId, ServiceRequestType, ServiceRequestParam, **kwargs):
        """
        获取统计信息：'GetTimedMonData',{"Language":"zh","KeyGroup":"mem_cpu_usage","KeyName":"","StartTime":"2018-01-15T04:03:26Z","EndTime":"2018-01-15T05:03:26Z"}
            mem_cpu_usage、iops_usage、detailed_disk_space
        获取process信息：'ShowProcessList',{"Language":"zh","Command":"Query"}  -- Not Sleep , All
        终止进程：'ConfirmKillSessionRequest',{"Language":"zh","SQLRequestID":75865,"SQLStatement":"kill 34022786;"}
        获取表空间信息：'GetSpaceStatForTables',{"Language": "zh", "OrderType": "Data"}
        获取资源利用信息：'GetResourceUsage',{"Language":"zh"}
        """
        request = RequestServiceOfCloudDBARequest.RequestServiceOfCloudDBARequest()
        values = {"action_name": "RequestServiceOfCloudDBA", "DBInstanceId": DBInstanceId,
                  "ServiceRequestType": ServiceRequestType, "ServiceRequestParam": ServiceRequestParam}
        values = dict(values, **kwargs)
        result = self.request_api(request, values)
        return result
