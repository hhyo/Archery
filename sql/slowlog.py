# -*- coding: UTF-8 -*-
import simplejson as json
from django.contrib.auth.decorators import permission_required

from django.db.models import F, Sum
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import datetime

from sql.utils.group import user_masters
from sql.utils.extend_json_encoder import ExtendJSONEncoder
from .models import Instance, SlowQuery, SlowQueryHistory, AliyunRdsConfig
from sql.utils.config import SysConfig
import logging

logger = logging.getLogger('default')

if SysConfig().sys_config.get('aliyun_rds_manage') == 'true':
    from .aliyun_rds import slowquery_review as aliyun_rds_slowquery_review, \
        slowquery_review_history as aliyun_rds_slowquery_review_history


# 获取SQL慢日志统计
@csrf_exempt
@permission_required('sql.menu_slowquery', raise_exception=True)
def slowquery_review(request):
    cluster_name = request.POST.get('cluster_name')
    # 服务端权限校验
    try:
        user_masters(request.user).get(cluster_name=cluster_name)
    except Exception:
        result = {'status': 1, 'msg': '你所在组未关联该主库', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 判断是RDS还是其他实例
    cluster_info = Instance.objects.get(cluster_name=cluster_name)
    if len(AliyunRdsConfig.objects.filter(cluster_name=cluster_name)) > 0:
        if SysConfig().sys_config.get('aliyun_rds_manage') == 'true':
            # 调用阿里云慢日志接口
            result = aliyun_rds_slowquery_review(request)
        else:
            raise Exception('未开启rds管理，无法查看rds数据！')
    else:
        StartTime = request.POST.get('StartTime')
        EndTime = request.POST.get('EndTime')
        DBName = request.POST.get('db_name')
        limit = int(request.POST.get('limit'))
        offset = int(request.POST.get('offset'))
        limit = offset + limit

        # 时间处理
        EndTime = datetime.datetime.strptime(EndTime, '%Y-%m-%d') + datetime.timedelta(days=1)
        # DBName非必传
        if DBName:
            # 获取慢查数据
            slowsql_obj = SlowQuery.objects.filter(
                slowqueryhistory__hostname_max=(cluster_info.master_host + ':' + str(cluster_info.master_port)),
                slowqueryhistory__db_max=DBName,
                slowqueryhistory__ts_min__range=(StartTime, EndTime),
                last_seen__range=(StartTime, EndTime)
            ).annotate(CreateTime=F('last_seen'),
                       SQLId=F('checksum'),
                       DBName=F('slowqueryhistory__db_max'),  # 数据库
                       SQLText=F('fingerprint'),  # SQL语句
                       ).values(
                'CreateTime', 'SQLId', 'DBName', 'SQLText'
            ).annotate(
                MySQLTotalExecutionCounts=Sum('slowqueryhistory__ts_cnt'),  # 执行总次数
                MySQLTotalExecutionTimes=Sum('slowqueryhistory__query_time_sum'),  # 执行总时长
                ParseTotalRowCounts=Sum('slowqueryhistory__rows_examined_sum'),  # 扫描总行数
                ReturnTotalRowCounts=Sum('slowqueryhistory__rows_sent_sum'),  # 返回总行数
            ).order_by('-MySQLTotalExecutionCounts')[offset:limit]  # 执行总次数倒序排列

            slowsql_obj_count = SlowQuery.objects.filter(
                slowqueryhistory__hostname_max=(cluster_info.master_host + ':' + str(cluster_info.master_port)),
                slowqueryhistory__db_max=DBName,
                slowqueryhistory__ts_min__range=(StartTime, EndTime),
                last_seen__range=(StartTime, EndTime)
            ).annotate(CreateTime=F('last_seen'),
                       SQLId=F('checksum'),
                       DBName=F('slowqueryhistory__db_max'),  # 数据库
                       SQLText=F('fingerprint'),  # SQL语句
                       ).values(
                'CreateTime', 'SQLId', 'DBName', 'SQLText'
            ).annotate(
                MySQLTotalExecutionCounts=Sum('slowqueryhistory__ts_cnt'),  # 执行总次数
                MySQLTotalExecutionTimes=Sum('slowqueryhistory__query_time_sum'),  # 执行总时长
                ParseTotalRowCounts=Sum('slowqueryhistory__rows_examined_sum'),  # 扫描总行数
                ReturnTotalRowCounts=Sum('slowqueryhistory__rows_sent_sum'),  # 返回总行数
            ).count()
        else:
            # 获取慢查数据
            slowsql_obj = SlowQuery.objects.filter(
                slowqueryhistory__hostname_max=(cluster_info.master_host + ':' + str(cluster_info.master_port)),
                slowqueryhistory__ts_min__range=(StartTime, EndTime),
                last_seen__range=(StartTime, EndTime)
            ).annotate(CreateTime=F('last_seen'),
                       SQLId=F('checksum'),
                       DBName=F('slowqueryhistory__db_max'),  # 数据库
                       SQLText=F('fingerprint'),  # SQL语句
                       ).values(
                'CreateTime', 'SQLId', 'DBName', 'SQLText'
            ).annotate(
                MySQLTotalExecutionCounts=Sum('slowqueryhistory__ts_cnt'),  # 执行总次数
                MySQLTotalExecutionTimes=Sum('slowqueryhistory__query_time_sum'),  # 执行总时长
                ParseTotalRowCounts=Sum('slowqueryhistory__rows_examined_sum'),  # 扫描总行数
                ReturnTotalRowCounts=Sum('slowqueryhistory__rows_sent_sum'),  # 返回总行数
            ).order_by('-MySQLTotalExecutionCounts')[offset:limit]  # 执行总次数倒序排列

            slowsql_obj_count = SlowQuery.objects.filter(
                slowqueryhistory__hostname_max=(cluster_info.master_host + ':' + str(cluster_info.master_port)),
                slowqueryhistory__ts_min__range=(StartTime, EndTime),
                last_seen__range=(StartTime, EndTime)
            ).annotate(CreateTime=F('last_seen'),
                       SQLId=F('checksum'),
                       DBName=F('slowqueryhistory__db_max'),  # 数据库
                       SQLText=F('fingerprint'),  # SQL语句
                       ).values(
                'CreateTime', 'SQLId', 'DBName', 'SQLText'
            ).annotate(
                MySQLTotalExecutionCounts=Sum('slowqueryhistory__ts_cnt'),  # 执行总次数
                MySQLTotalExecutionTimes=Sum('slowqueryhistory__query_time_sum'),  # 执行总时长
                ParseTotalRowCounts=Sum('slowqueryhistory__rows_examined_sum'),  # 扫描总行数
                ReturnTotalRowCounts=Sum('slowqueryhistory__rows_sent_sum'),  # 返回总行数
            ).count()
        # QuerySet 序列化
        SQLSlowLog = [SlowLog for SlowLog in slowsql_obj]
        result = {"total": slowsql_obj_count, "rows": SQLSlowLog}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 获取SQL慢日志明细
@csrf_exempt
@permission_required('sql.menu_slowquery', raise_exception=True)
def slowquery_review_history(request):
    cluster_name = request.POST.get('cluster_name')
    # 服务端权限校验
    try:
        user_masters(request.user).get(cluster_name=cluster_name)
    except Exception:
        result = {'status': 1, 'msg': '你所在组未关联该主库', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 判断是RDS还是其他实例
    cluster_info = Instance.objects.get(cluster_name=cluster_name)
    if len(AliyunRdsConfig.objects.filter(cluster_name=cluster_name)) > 0:
        if SysConfig().sys_config.get('aliyun_rds_manage') == 'true':
            # 调用阿里云慢日志接口
            result = aliyun_rds_slowquery_review_history(request)
        else:
            raise Exception('未开启rds管理，无法查看rds数据！')
    else:
        StartTime = request.POST.get('StartTime')
        EndTime = request.POST.get('EndTime')
        DBName = request.POST.get('db_name')
        SQLId = request.POST.get('SQLId')
        limit = int(request.POST.get('limit'))
        offset = int(request.POST.get('offset'))

        # 时间处理
        EndTime = datetime.datetime.strptime(EndTime, '%Y-%m-%d') + datetime.timedelta(days=1)
        limit = offset + limit
        # SQLId、DBName非必传
        if SQLId:
            # 获取慢查明细数据
            slowsql_record_obj = SlowQueryHistory.objects.filter(
                hostname_max=(cluster_info.master_host + ':' + str(cluster_info.master_port)),
                checksum=int(SQLId),
                ts_min__range=(StartTime, EndTime)
            ).annotate(ExecutionStartTime=F('ts_min'),  # 执行开始时间
                       DBName=F('db_max'),  # 数据库名
                       HostAddress=F('user_max'),  # 用户名
                       SQLText=F('sample'),  # SQL语句
                       QueryTimes=F('query_time_sum'),  # 执行时长(秒)
                       LockTimes=F('lock_time_sum'),  # 锁定时长(秒)
                       ParseRowCounts=F('rows_examined_sum'),  # 解析行数
                       ReturnRowCounts=F('rows_sent_sum')  # 返回行数
                       ).values(
                'ExecutionStartTime', 'DBName', 'HostAddress', 'SQLText', 'QueryTimes', 'LockTimes', 'ParseRowCounts',
                'ReturnRowCounts'
            )[offset:limit]

            slowsql_obj_count = SlowQueryHistory.objects.filter(
                hostname_max=(cluster_info.master_host + ':' + str(cluster_info.master_port)),
                checksum=int(SQLId),
                ts_min__range=(StartTime, EndTime)
            ).count()
        else:
            if DBName:
                # 获取慢查明细数据
                slowsql_record_obj = SlowQueryHistory.objects.filter(
                    hostname_max=(cluster_info.master_host + ':' + str(cluster_info.master_port)),
                    db_max=DBName,
                    ts_min__range=(StartTime, EndTime)
                ).annotate(ExecutionStartTime=F('ts_min'),  # 执行开始时间
                           DBName=F('db_max'),  # 数据库名
                           HostAddress=F('user_max'),  # 用户名
                           SQLText=F('sample'),  # SQL语句
                           QueryTimes=F('query_time_sum'),  # 执行时长(秒)
                           LockTimes=F('lock_time_sum'),  # 锁定时长(秒)
                           ParseRowCounts=F('rows_examined_sum'),  # 解析行数
                           ReturnRowCounts=F('rows_sent_sum')  # 返回行数
                           ).values(
                    'ExecutionStartTime', 'DBName', 'HostAddress', 'SQLText', 'QueryTimes', 'LockTimes',
                    'ParseRowCounts',
                    'ReturnRowCounts'
                )[offset:limit]  # 执行总次数倒序排列

                slowsql_obj_count = SlowQueryHistory.objects.filter(
                    hostname_max=(cluster_info.master_host + ':' + str(cluster_info.master_port)),
                    db_max=DBName,
                    ts_min__range=(StartTime, EndTime)
                ).count()
            else:
                # 获取慢查明细数据
                slowsql_record_obj = SlowQueryHistory.objects.filter(
                    hostname_max=(cluster_info.master_host + ':' + str(cluster_info.master_port)),
                    ts_min__range=(StartTime, EndTime)
                ).annotate(ExecutionStartTime=F('ts_min'),  # 执行开始时间
                           DBName=F('db_max'),  # 数据库名
                           HostAddress=F('user_max'),  # 用户名
                           SQLText=F('sample'),  # SQL语句
                           QueryTimes=F('query_time_sum'),  # 执行时长(秒)
                           LockTimes=F('lock_time_sum'),  # 锁定时长(秒)
                           ParseRowCounts=F('rows_examined_sum'),  # 解析行数
                           ReturnRowCounts=F('rows_sent_sum')  # 返回行数
                           ).values(
                    'ExecutionStartTime', 'DBName', 'HostAddress', 'SQLText', 'QueryTimes', 'LockTimes',
                    'ParseRowCounts',
                    'ReturnRowCounts'
                )[offset:limit]  # 执行总次数倒序排列

                slowsql_obj_count = SlowQueryHistory.objects.filter(
                    hostname_max=(cluster_info.master_host + ':' + str(cluster_info.master_port)),
                    ts_min__range=(StartTime, EndTime)
                ).count()
        # QuerySet 序列化
        SQLSlowRecord = [SlowRecord for SlowRecord in slowsql_record_obj]
        result = {"total": slowsql_obj_count, "rows": SQLSlowRecord}

        # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
