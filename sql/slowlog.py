# -*- coding: UTF-8 -*-
import MySQLdb
import simplejson as json
import datetime
import pymysql
from django.contrib.auth.decorators import permission_required
from django.db.models import F, Sum, Value as V, Max
from django.db.models.functions import Concat
from django.http import HttpResponse
from django.views.decorators.cache import cache_page
from pyecharts.charts import Line
from pyecharts import options as opts
from common.utils.chart_dao import ChartDao
from sql.engines import get_engine

from sql.utils.resource_group import user_instances
from common.utils.extend_json_encoder import ExtendJSONEncoder
from .models import Instance, SlowQuery, SlowQueryHistory, AliyunRdsConfig


import logging

logger = logging.getLogger("default")


# 获取SQL慢日志统计
@permission_required("sql.menu_slowquery", raise_exception=True)
def slowquery_review(request):
    instance_name = request.POST.get("instance_name")
    start_time = request.POST.get("StartTime")
    end_time = request.POST.get("EndTime")
    db_name = request.POST.get("db_name")
    limit = int(request.POST.get("limit"))
    offset = int(request.POST.get("offset"))
    # 服务端权限校验
    try:
        user_instances(request.user, db_type=["mysql"]).get(instance_name=instance_name)
    except Exception:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 判断是RDS还是其他实例
    instance_info = Instance.objects.get(instance_name=instance_name)
    if AliyunRdsConfig.objects.filter(instance=instance_info, is_enable=True).exists():
        # 调用阿里云慢日志接口
        query_engine = get_engine(instance=instance_info)
        result = query_engine.slowquery_review(
            start_time, end_time, db_name, limit, offset
        )
    else:
        limit = offset + limit
        search = request.POST.get("search")
        sortName = str(request.POST.get("sortName"))
        sortOrder = str(request.POST.get("sortOrder")).lower()

        # 时间处理
        end_time = datetime.datetime.strptime(
            end_time, "%Y-%m-%d"
        ) + datetime.timedelta(days=1)
        filter_kwargs = {"slowqueryhistory__db_max": db_name} if db_name else {}
        # 获取慢查数据
        slowsql_obj = (
            SlowQuery.objects.filter(
                slowqueryhistory__hostname_max=(
                    instance_info.host + ":" + str(instance_info.port)
                ),
                slowqueryhistory__ts_min__range=(start_time, end_time),
                fingerprint__icontains=search,
                **filter_kwargs
            )
            .annotate(SQLText=F("fingerprint"), SQLId=F("checksum"))
            .values("SQLText", "SQLId")
            .annotate(
                CreateTime=Max("slowqueryhistory__ts_max"),
                DBName=Max("slowqueryhistory__db_max"),  # 数据库
                QueryTimeAvg=Sum("slowqueryhistory__query_time_sum")
                / Sum("slowqueryhistory__ts_cnt"),  # 平均执行时长
                MySQLTotalExecutionCounts=Sum("slowqueryhistory__ts_cnt"),  # 执行总次数
                MySQLTotalExecutionTimes=Sum(
                    "slowqueryhistory__query_time_sum"
                ),  # 执行总时长
                ParseTotalRowCounts=Sum(
                    "slowqueryhistory__rows_examined_sum"
                ),  # 扫描总行数
                ReturnTotalRowCounts=Sum(
                    "slowqueryhistory__rows_sent_sum"
                ),  # 返回总行数
                ParseRowAvg=Sum("slowqueryhistory__rows_examined_sum")
                / Sum("slowqueryhistory__ts_cnt"),  # 平均扫描行数
                ReturnRowAvg=Sum("slowqueryhistory__rows_sent_sum")
                / Sum("slowqueryhistory__ts_cnt"),  # 平均返回行数
            )
        )
        slow_sql_count = slowsql_obj.count()
        # 默认“执行总次数”倒序排列
        slow_sql_list = slowsql_obj.order_by(
            "-" + sortName if "desc".__eq__(sortOrder) else sortName
        )[offset:limit]

        # QuerySet 序列化
        sql_slow_log = []
        for SlowLog in slow_sql_list:
            SlowLog["QueryTimeAvg"] = round(SlowLog["QueryTimeAvg"], 6)
            SlowLog["MySQLTotalExecutionTimes"] = round(
                SlowLog["MySQLTotalExecutionTimes"], 6
            )
            SlowLog["ParseRowAvg"] = int(SlowLog["ParseRowAvg"])
            SlowLog["ReturnRowAvg"] = int(SlowLog["ReturnRowAvg"])
            sql_slow_log.append(SlowLog)
        result = {"total": slow_sql_count, "rows": sql_slow_log}

    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


# 获取SQL慢日志明细
@permission_required("sql.menu_slowquery", raise_exception=True)
def slowquery_review_history(request):
    instance_name = request.POST.get("instance_name")
    start_time = request.POST.get("StartTime")
    end_time = request.POST.get("EndTime")
    db_name = request.POST.get("db_name")
    sql_id = request.POST.get("SQLId")
    limit = int(request.POST.get("limit"))
    offset = int(request.POST.get("offset"))
    # 服务端权限校验
    try:
        user_instances(request.user, db_type=["mysql"]).get(instance_name=instance_name)
    except Exception:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 判断是RDS还是其他实例
    instance_info = Instance.objects.get(instance_name=instance_name)
    if AliyunRdsConfig.objects.filter(instance=instance_info, is_enable=True).exists():
        # 调用阿里云慢日志接口
        query_engine = get_engine(instance=instance_info)
        result = query_engine.slowquery_review_history(
            start_time, end_time, db_name, sql_id, limit, offset
        )
    else:
        search = request.POST.get("search")
        sortName = str(request.POST.get("sortName"))
        sortOrder = str(request.POST.get("sortOrder")).lower()

        # 时间处理
        end_time = datetime.datetime.strptime(
            end_time, "%Y-%m-%d"
        ) + datetime.timedelta(days=1)
        limit = offset + limit
        filter_kwargs = {}
        filter_kwargs.update({"checksum": sql_id}) if sql_id else None
        filter_kwargs.update({"db_max": db_name}) if db_name else None
        # SQLId、DBName非必传
        # 获取慢查明细数据
        slow_sql_record_obj = SlowQueryHistory.objects.filter(
            hostname_max=(instance_info.host + ":" + str(instance_info.port)),
            ts_min__range=(start_time, end_time),
            sample__icontains=search,
            **filter_kwargs
        ).annotate(
            ExecutionStartTime=F(
                "ts_min"
            ),  # 本次统计(每5分钟一次)该类型sql语句出现的最小时间
            DBName=F("db_max"),  # 数据库名
            HostAddress=Concat(
                V("'"), "user_max", V("'"), V("@"), V("'"), "client_max", V("'")
            ),  # 用户名
            SQLText=F("sample"),  # SQL语句
            TotalExecutionCounts=F("ts_cnt"),  # 本次统计该sql语句出现的次数
            QueryTimePct95=F("query_time_pct_95"),  # 本次统计该sql语句95%耗时
            QueryTimes=F("query_time_sum"),  # 本次统计该sql语句花费的总时间(秒)
            LockTimes=F("lock_time_sum"),  # 本次统计该sql语句锁定总时长(秒)
            ParseRowCounts=F("rows_examined_sum"),  # 本次统计该sql语句解析总行数
            ReturnRowCounts=F("rows_sent_sum"),  # 本次统计该sql语句返回总行数
        )

        slow_sql_record_count = slow_sql_record_obj.count()
        slow_sql_record_list = slow_sql_record_obj.order_by(
            "-" + sortName if "desc".__eq__(sortOrder) else sortName
        )[offset:limit].values(
            "ExecutionStartTime",
            "DBName",
            "HostAddress",
            "SQLText",
            "TotalExecutionCounts",
            "QueryTimePct95",
            "QueryTimes",
            "LockTimes",
            "ParseRowCounts",
            "ReturnRowCounts",
        )

        # QuerySet 序列化
        sql_slow_record = []
        for SlowRecord in slow_sql_record_list:
            SlowRecord["QueryTimePct95"] = round(SlowRecord["QueryTimePct95"], 6)
            SlowRecord["QueryTimes"] = round(SlowRecord["QueryTimes"], 6)
            SlowRecord["LockTimes"] = round(SlowRecord["LockTimes"], 6)
            sql_slow_record.append(SlowRecord)
        result = {"total": slow_sql_record_count, "rows": sql_slow_record}

        # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


@cache_page(60 * 10)
def report(request):
    """返回慢SQL历史趋势"""
    checksum = request.GET.get("checksum")
    checksum = pymysql.escape_string(checksum)
    cnt_data = ChartDao().slow_query_review_history_by_cnt(checksum)
    pct_data = ChartDao().slow_query_review_history_by_pct_95_time(checksum)
    cnt_x_data = [row[1] for row in cnt_data["rows"]]
    cnt_y_data = [int(row[0]) for row in cnt_data["rows"]]
    pct_y_data = [str(row[0]) for row in pct_data["rows"]]
    line = Line(init_opts=opts.InitOpts(width="800", height="380px"))
    line.add_xaxis(cnt_x_data)
    line.add_yaxis(
        "慢查次数",
        cnt_y_data,
        is_smooth=True,
        markline_opts=opts.MarkLineOpts(
            data=[
                opts.MarkLineItem(type_="max", name="最大值"),
                opts.MarkLineItem(type_="average", name="平均值"),
            ]
        ),
    )
    line.add_yaxis("慢查时长(95%)", pct_y_data, is_smooth=True, is_symbol_show=False)
    line.set_series_opts(
        areastyle_opts=opts.AreaStyleOpts(
            opacity=0.5,
        )
    )
    line.set_global_opts(
        title_opts=opts.TitleOpts(title="SQL历史趋势"),
        legend_opts=opts.LegendOpts(selected_mode="single"),
        xaxis_opts=opts.AxisOpts(
            axistick_opts=opts.AxisTickOpts(is_align_with_label=True),
            is_scale=False,
            boundary_gap=False,
        ),
    )

    result = {"status": 0, "msg": "", "data": line.render_embed()}
    return HttpResponse(json.dumps(result), content_type="application/json")
