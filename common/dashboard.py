# -*- coding: UTF-8 -*-
import logging
from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.http import JsonResponse
from django.core.exceptions import ValidationError

from sql.models import SqlWorkflow, QueryPrivilegesApply, Users, Instance

from common.utils.chart_dao import ChartDao
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from pyecharts.globals import CurrentConfig
from pyecharts import options as opts
from pyecharts.charts import Pie, Bar, Line

CurrentConfig.ONLINE_HOST = "/static/echarts/"


@permission_required("sql.menu_dashboard", raise_exception=True)
def pyecharts(request):
    # 获取统计数据
    dashboard_count_stats = {
        "sql_wf_cnt": SqlWorkflow.objects.count(),
        "query_wf_cnt": QueryPrivilegesApply.objects.count(),
        "user_cnt": Users.objects.filter(is_active=1).count(),
        "ins_cnt": Instance.objects.count(),
    }
    chart_dao = ChartDao()

    data = chart_dao.instance_count_by_type()
    attr = [row[0] for row in data["rows"]]
    value = [row[1] for row in data["rows"]]
    pie6 = create_pie_chart(attr, value)

    data = chart_dao.query_instance_env_info()
    bar4 = gen_stack_chart(data)

    instance_chart = {
        "pie6": pie6.render_embed(),
        "bar4": bar4.render_embed(),
    }
    # 获取图表数据
    # 字符串，近7天日期 "%Y-%m-%d"
    today = (date.today() - relativedelta(days=-1)).strftime("%Y-%m-%d")
    one_week_before = (date.today() - relativedelta(days=+6)).strftime("%Y-%m-%d")
    dashboard_chart = get_chart_data(one_week_before, today)

    return render(
        request,
        "dashboard.html",
        {
            "instance_chart": instance_chart,
            "chart": dashboard_chart,
            "count_stats": dashboard_count_stats,
        },
    )


@permission_required("sql.menu_dashboard", raise_exception=True)
def DashboardApi(request):
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")

    try:
        start_date = validate_date(start_date_str)
        end_date = validate_date(end_date_str)
    except ValidationError as e:
        return JsonResponse({"error: 日期有误"}, status=400)

    dashboard_chart = get_chart_data(start_date, end_date)

    return JsonResponse({"chart": dashboard_chart})


def validate_date(date_str):
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        raise ValidationError(
            f"Invalid date format: {date_str}. Expected format: YYYY-MM-DD."
        )


def get_chart_data(start_date, end_date):
    logging.info("Dashboard: start_date: %s, end_date: %s", start_date, end_date)
    chart_dao = ChartDao()

    # SQL上线数量
    data = chart_dao.workflow_by_date(start_date, end_date)
    attr = chart_dao.get_date_list(
        datetime.strptime(start_date, "%Y-%m-%d"),
        datetime.strptime(end_date, "%Y-%m-%d"),
    )
    _dict = {row[0]: row[1] for row in data["rows"]}
    value = [_dict.get(day, 0) for day in attr]
    bar1 = create_bar_chart(attr, value)

    # SQL上线统计
    data = chart_dao.workflow_by_group(start_date, end_date)
    attr = [row[0] for row in data["rows"]]
    value = [row[1] for row in data["rows"]]
    pie1 = create_pie_chart(attr, value)

    # SQL语法类型
    data = chart_dao.syntax_type(start_date, end_date)
    attr = [row[0] for row in data["rows"]]
    value = [row[1] for row in data["rows"]]
    pie2 = create_pie_chart(attr, value)

    # SQL上线用户
    data = chart_dao.workflow_by_user(start_date, end_date)
    attr = [row[0] for row in data["rows"]]
    value = [row[1] for row in data["rows"]]
    bar2 = create_bar_chart(attr, value)

    # SQL查询统计
    attr = chart_dao.get_date_list(
        datetime.strptime(start_date, "%Y-%m-%d"),
        datetime.strptime(end_date, "%Y-%m-%d"),
    )
    effect_data = chart_dao.querylog_effect_row_by_date(start_date, end_date)
    effect_dict = {row[0]: int(row[1]) for row in effect_data["rows"]}
    effect_value = [effect_dict.get(day, 0) for day in attr]
    count_data = chart_dao.querylog_count_by_date(start_date, end_date)
    count_dict = {row[0]: int(row[1]) for row in count_data["rows"]}
    count_value = [count_dict.get(day, 0) for day in attr]
    line1 = Line(init_opts=opts.InitOpts(width="600", height="380px", bg_color="white"))
    line1.set_global_opts(
        title_opts=opts.TitleOpts(title=""),
        legend_opts=opts.LegendOpts(selected_mode="single"),
    )
    line1.add_xaxis(attr)
    line1.add_yaxis(
        "检索行数",
        effect_value,
        is_smooth=True,
        markpoint_opts=opts.MarkPointOpts(data=[opts.MarkPointItem(type_="average")]),
    )
    line1.add_yaxis(
        "检索次数",
        count_value,
        is_smooth=True,
        markline_opts=opts.MarkLineOpts(
            data=[opts.MarkLineItem(type_="max"), opts.MarkLineItem(type_="average")]
        ),
    )

    # SQL查询用户
    data = chart_dao.querylog_effect_row_by_user(start_date, end_date)
    attr = [row[0] for row in data["rows"]]
    value = [int(row[1]) for row in data["rows"]]
    pie4 = create_pie_chart(attr, value)

    # DB检索行数
    data = chart_dao.querylog_effect_row_by_db(start_date, end_date)
    attr = [row[0] for row in data["rows"]]
    value = [int(row[1]) for row in data["rows"]]
    pie5 = create_pie_chart(attr, value)

    # 慢查询db/user维度统计
    data = chart_dao.slow_query_count_by_db_by_user(start_date, end_date)
    attr = [row[0] for row in data["rows"]]
    value = [int(row[1]) for row in data["rows"]]
    pie3 = create_pie_chart(attr, value)

    # 慢查询db维度统计
    data = chart_dao.slow_query_count_by_db(start_date, end_date)
    attr = [row[0] for row in data["rows"]]
    value = [row[1] for row in data["rows"]]
    bar3 = create_bar_chart(attr, value)

    # SQL上线工单
    data = chart_dao.query_sql_prod_bill(start_date, end_date)
    attr = [row[0] for row in data["rows"]]
    value = [row[1] for row in data["rows"]]
    bar5 = create_bar_chart(attr, value)

    chart = {
        "bar1": bar1.render_embed(),
        "bar2": bar2.render_embed(),
        "bar3": bar3.render_embed(),
        "bar5": bar5.render_embed(),
        "pie1": pie1.render_embed(),
        "pie2": pie2.render_embed(),
        "pie3": pie3.render_embed(),
        "pie4": pie4.render_embed(),
        "pie5": pie5.render_embed(),
        "line1": line1.render_embed(),
    }

    return chart


# 创建柱状图
def create_bar_chart(attr, value, width="600", height="380px"):
    bar = Bar(init_opts=opts.InitOpts(width=width, height=height, bg_color="white"))
    bar.add_xaxis(attr)

    if len(attr) > 60:
        bar.add_yaxis(
            "",
            value,
            label_opts=opts.LabelOpts(is_show=False),
            markline_opts=opts.MarkLineOpts(
                data=[
                    opts.MarkLineItem(type_="max"),
                    opts.MarkLineItem(type_="average"),
                ]
            ),
        )
    else:
        bar.add_yaxis("", value, label_opts=opts.LabelOpts())

    if len(attr) > 0 and attr[0] and len(attr[0]) > 20:
        bar.set_global_opts(
            xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=-10)),
            legend_opts=opts.LegendOpts(pos_left="right"),
        )
    return bar


# 创建饼图
def create_pie_chart(attr, value, width="600", height="380px"):
    pie = Pie(init_opts=opts.InitOpts(width=width, height=height, bg_color="white"))
    pie.set_global_opts(
        title_opts=opts.TitleOpts(title=""),
        legend_opts=opts.LegendOpts(
            orient="vertical", pos_top="15%", pos_left="2%", is_show=False
        ),
    )
    pie.set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c}"))
    pie.add("", [list(z) for z in zip(attr, value)]) if attr and value else None
    return pie


# 生成堆叠图
def gen_stack_chart(data):
    rows = data.get("rows", [])
    envs = list(set(row[0] for row in rows if len(row) >= 1))  # X轴
    db_types = list(set(row[1] for row in rows if len(row) >= 2))  # 堆叠1
    env_dict = {env: {db_type: 0 for db_type in db_types} for env in envs}  # 堆叠2

    # 填充
    for row in rows:
        if len(row) == 3:
            env, db_type, count = row
            if env in env_dict and db_type in env_dict[env]:
                env_dict[env][db_type] = count

    # 将环境-数据库类型的计数转化为数据列表
    db_data = {db_type: [] for db_type in db_types}
    for env in envs:
        for db_type in db_types:
            db_data[db_type].append(env_dict[env][db_type])

    # 绘制堆叠柱状图
    stack_bar = Bar(
        init_opts=opts.InitOpts(width="800px", height="380px", bg_color="white")
    ).add_xaxis(
        envs
    )  # 设置X轴数据（环境）

    for db_type in db_types:
        y_values = db_data[db_type]

        stack_bar.add_yaxis(
            series_name=db_type,
            y_axis=y_values,
            stack="stack1",
            label_opts=opts.LabelOpts(is_show=False),
        )

    # 隐藏Y轴的刻度标签
    stack_bar.set_global_opts(
        xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=-10)),
        legend_opts=opts.LegendOpts(pos_left="right"),
    )
    return stack_bar
