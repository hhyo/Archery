# -*- coding: UTF-8 -*-
import simplejson as json
import datetime
from django.contrib.auth.decorators import permission_required
from django.db.models import F, Sum, Value as V, Max
from django.db.models.functions import Concat
from django.http import HttpResponse
from sql.utils.resource_group import user_instances
from common.utils.extend_json_encoder import ExtendJSONEncoder
from .models import Instance, SlowQuery, SlowQueryHistory, AliyunRdsConfig

from .aliyun_rds import slowquery_review as aliyun_rds_slowquery_review, \
    slowquery_review_history as aliyun_rds_slowquery_review_history

import logging

logger = logging.getLogger('default')


# 获取SQL慢日志统计
@permission_required('sql.menu_slowquery', raise_exception=True)
def slowquery_review(request):
    instance_name = request.POST.get('instance_name')
    # 服务端权限校验
    try:
        user_instances(request.user, db_type=['mysql']).get(instance_name=instance_name)
    except Exception:
        result = {'status': 1, 'msg': '你所在组未关联该实例', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 判断是RDS还是其他实例
    instance_info = Instance.objects.get(instance_name=instance_name)
    if len(AliyunRdsConfig.objects.filter(instance=instance_info, is_enable=True)) > 0:
        # 调用阿里云慢日志接口
        result = aliyun_rds_slowquery_review(request)
    else:
        start_time = request.POST.get('StartTime')
        end_time = request.POST.get('EndTime')
        db_name = request.POST.get('db_name')
        limit = int(request.POST.get('limit'))
        offset = int(request.POST.get('offset'))
        limit = offset + limit

        # 时间处理
        end_time = datetime.datetime.strptime(end_time, '%Y-%m-%d') + datetime.timedelta(days=1)
        # DBName非必传
        if db_name:
            # 获取慢查数据
            slowsql_obj = SlowQuery.objects.filter(
                slowqueryhistory__hostname_max=(instance_info.host + ':' + str(instance_info.port)),
                slowqueryhistory__db_max=db_name,
                slowqueryhistory__ts_min__range=(start_time, end_time)
            ).annotate(SQLText=F('fingerprint'), SQLId=F('checksum')).values('SQLText', 'SQLId').annotate(
                CreateTime=Max('slowqueryhistory__ts_max'),
                DBName=Max('slowqueryhistory__db_max'),  # 数据库
                QueryTimeAvg=Sum('slowqueryhistory__query_time_sum') / Sum('slowqueryhistory__ts_cnt'),  # 平均执行时长
                MySQLTotalExecutionCounts=Sum('slowqueryhistory__ts_cnt'),  # 执行总次数
                MySQLTotalExecutionTimes=Sum('slowqueryhistory__query_time_sum'),  # 执行总时长
                ParseTotalRowCounts=Sum('slowqueryhistory__rows_examined_sum'),  # 扫描总行数
                ReturnTotalRowCounts=Sum('slowqueryhistory__rows_sent_sum'),  # 返回总行数
            )
        else:
            # 获取慢查数据
            slowsql_obj = SlowQuery.objects.filter(
                slowqueryhistory__hostname_max=(instance_info.host + ':' + str(instance_info.port)),
                slowqueryhistory__ts_min__range=(start_time, end_time),
            ).annotate(SQLText=F('fingerprint'), SQLId=F('checksum')).values('SQLText', 'SQLId').annotate(
                CreateTime=Max('slowqueryhistory__ts_max'),
                DBName=Max('slowqueryhistory__db_max'),  # 数据库
                QueryTimeAvg=Sum('slowqueryhistory__query_time_sum') / Sum('slowqueryhistory__ts_cnt'),  # 平均执行时长
                MySQLTotalExecutionCounts=Sum('slowqueryhistory__ts_cnt'),  # 执行总次数
                MySQLTotalExecutionTimes=Sum('slowqueryhistory__query_time_sum'),  # 执行总时长
                ParseTotalRowCounts=Sum('slowqueryhistory__rows_examined_sum'),  # 扫描总行数
                ReturnTotalRowCounts=Sum('slowqueryhistory__rows_sent_sum'),  # 返回总行数
            )
        slow_sql_count = slowsql_obj.count()
        slow_sql_list = slowsql_obj.order_by('-MySQLTotalExecutionCounts')[offset:limit]  # 执行总次数倒序排列

        # QuerySet 序列化
        sql_slow_log = [SlowLog for SlowLog in slow_sql_list]
        result = {"total": slow_sql_count, "rows": sql_slow_log}

    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 获取SQL慢日志明细
@permission_required('sql.menu_slowquery', raise_exception=True)
def slowquery_review_history(request):
    instance_name = request.POST.get('instance_name')
    # 服务端权限校验
    try:
        user_instances(request.user, db_type=['mysql']).get(instance_name=instance_name)
    except Exception:
        result = {'status': 1, 'msg': '你所在组未关联该实例', 'data': []}
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 判断是RDS还是其他实例
    instance_info = Instance.objects.get(instance_name=instance_name)
    if len(AliyunRdsConfig.objects.filter(instance=instance_info, is_enable=True)) > 0:
        # 调用阿里云慢日志接口
        result = aliyun_rds_slowquery_review_history(request)
    else:
        start_time = request.POST.get('StartTime')
        end_time = request.POST.get('EndTime')
        db_name = request.POST.get('db_name')
        sql_id = request.POST.get('SQLId')
        limit = int(request.POST.get('limit'))
        offset = int(request.POST.get('offset'))

        # 时间处理
        end_time = datetime.datetime.strptime(end_time, '%Y-%m-%d') + datetime.timedelta(days=1)
        limit = offset + limit
        # SQLId、DBName非必传
        if sql_id:
            # 获取慢查明细数据
            slow_sql_record_obj = SlowQueryHistory.objects.filter(
                hostname_max=(instance_info.host + ':' + str(instance_info.port)),
                checksum=sql_id,
                ts_min__range=(start_time, end_time)
            ).annotate(ExecutionStartTime=F('ts_min'),  # 本次统计(每5分钟一次)该类型sql语句出现的最小时间
                       DBName=F('db_max'),  # 数据库名
                       HostAddress=Concat(V('\''), 'user_max', V('\''), V('@'), V('\''), 'client_max', V('\'')),  # 用户名
                       SQLText=F('sample'),  # SQL语句
                       TotalExecutionCounts=F('ts_cnt'),  # 本次统计该sql语句出现的次数
                       QueryTimePct95=F('query_time_pct_95'),  # 本次统计该sql语句95%耗时
                       QueryTimes=F('query_time_sum'),  # 本次统计该sql语句花费的总时间(秒)
                       LockTimes=F('lock_time_sum'),  # 本次统计该sql语句锁定总时长(秒)
                       ParseRowCounts=F('rows_examined_sum'),  # 本次统计该sql语句解析总行数
                       ReturnRowCounts=F('rows_sent_sum')  # 本次统计该sql语句返回总行数
                       )
        else:
            if db_name:
                # 获取慢查明细数据
                slow_sql_record_obj = SlowQueryHistory.objects.filter(
                    hostname_max=(instance_info.host + ':' + str(instance_info.port)),
                    db_max=db_name,
                    ts_min__range=(start_time, end_time)
                ).annotate(ExecutionStartTime=F('ts_min'),  # 本次统计(每5分钟一次)该类型sql语句出现的最小时间
                           DBName=F('db_max'),  # 数据库名
                           HostAddress=Concat(V('\''), 'user_max', V('\''), V('@'), V('\''), 'client_max', V('\'')),
                           # 用户名
                           SQLText=F('sample'),  # SQL语句
                           TotalExecutionCounts=F('ts_cnt'),  # 本次统计该sql语句出现的次数
                           QueryTimePct95=F('query_time_pct_95'),  # 本次统计该sql语句出现的次数
                           QueryTimes=F('query_time_sum'),  # 本次统计该sql语句花费的总时间(秒)
                           LockTimes=F('lock_time_sum'),  # 本次统计该sql语句锁定总时长(秒)
                           ParseRowCounts=F('rows_examined_sum'),  # 本次统计该sql语句解析总行数
                           ReturnRowCounts=F('rows_sent_sum')  # 本次统计该sql语句返回总行数
                           )
            else:
                # 获取慢查明细数据
                slow_sql_record_obj = SlowQueryHistory.objects.filter(
                    hostname_max=(instance_info.host + ':' + str(instance_info.port)),
                    ts_min__range=(start_time, end_time)
                ).annotate(ExecutionStartTime=F('ts_min'),  # 本次统计(每5分钟一次)该类型sql语句出现的最小时间
                           DBName=F('db_max'),  # 数据库名
                           HostAddress=Concat(V('\''), 'user_max', V('\''), V('@'), V('\''), 'client_max', V('\'')),
                           # 用户名
                           SQLText=F('sample'),  # SQL语句
                           TotalExecutionCounts=F('ts_cnt'),  # 本次统计该sql语句出现的次数
                           QueryTimePct95=F('query_time_pct_95'),  # 本次统计该sql语句95%耗时
                           QueryTimes=F('query_time_sum'),  # 本次统计该sql语句花费的总时间(秒)
                           LockTimes=F('lock_time_sum'),  # 本次统计该sql语句锁定总时长(秒)
                           ParseRowCounts=F('rows_examined_sum'),  # 本次统计该sql语句解析总行数
                           ReturnRowCounts=F('rows_sent_sum')  # 本次统计该sql语句返回总行数
                           )

        slow_sql_record_count = slow_sql_record_obj.count()
        slow_sql_record_list = slow_sql_record_obj[offset:limit].values('ExecutionStartTime', 'DBName', 'HostAddress',
                                                                        'SQLText',
                                                                        'TotalExecutionCounts', 'QueryTimePct95',
                                                                        'QueryTimes', 'LockTimes', 'ParseRowCounts',
                                                                        'ReturnRowCounts'
                                                                        )

        # QuerySet 序列化
        sql_slow_record = [SlowRecord for SlowRecord in slow_sql_record_list]
        result = {"total": slow_sql_record_count, "rows": sql_slow_record}

        # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
