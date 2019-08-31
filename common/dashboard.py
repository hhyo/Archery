# -*- coding: UTF-8 -*-
from django.contrib.auth.decorators import permission_required
from django.shortcuts import render

from common.utils.chart_dao import ChartDao
from datetime import date
from dateutil.relativedelta import relativedelta

from pyecharts import options as opts
from pyecharts.charts import Pie, Bar, Line, Page


@permission_required('sql.menu_dashboard', raise_exception=True)
def pyecharts(request):
    """dashboard view"""
    # 工单数量统计
    chart_dao = ChartDao()
    data = chart_dao.workflow_by_date(30)
    today = date.today()
    one_month_before = today - relativedelta(days=+30)
    attr = chart_dao.get_date_list(one_month_before, today)
    _dict = {}
    for row in data['rows']:
        _dict[row[0]] = row[1]
    value = [_dict.get(day) if _dict.get(day) else 0 for day in attr]
    bar1 = Bar()
    bar1.add_xaxis(attr)
    bar1.add_yaxis("月统计", value)
    bar1.set_global_opts(title_opts=opts.TitleOpts(title='SQL上线工单统计(数量)'),
                         datazoom_opts=opts.DataZoomOpts(is_show=True),
                         toolbox_opts=opts.ToolboxOpts(is_show=True))

    # 工单按组统计
    data = chart_dao.workflow_by_group(30)
    attr = [row[0] for row in data['rows']]
    value = [row[1] for row in data['rows']]
    pie1 = Pie()
    pie1.set_global_opts(title_opts=opts.TitleOpts(title='SQL上线工单统计(组)'),
                         legend_opts=opts.LegendOpts(
                             orient="vertical", pos_top="15%", pos_left="2%"
                         ))
    pie1.set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c}"))
    pie1.add("", [list(z) for z in zip(attr, value)])

    # 工单按人统计
    data = chart_dao.workflow_by_user(30)
    attr = [row[0] for row in data['rows']]
    value = [row[1] for row in data['rows']]
    bar2 = Bar()
    bar2.add_xaxis(attr)
    bar2.add_yaxis("月统计", value)
    bar2.set_global_opts(title_opts=opts.TitleOpts(title='SQL上线工单统计(用户)'))

    # SQL语句类型统计
    data = chart_dao.syntax_type()
    attr = [row[0] for row in data['rows']]
    value = [row[1] for row in data['rows']]
    pie2 = Pie()
    pie2.set_global_opts(title_opts=opts.TitleOpts(title='SQL上线工单统计(类型)'),
                         legend_opts=opts.LegendOpts(
                             orient="vertical", pos_top="15%", pos_left="2%"
                         ))
    pie2.set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c}"))
    pie2.add("", [list(z) for z in zip(attr, value)])

    # SQL查询统计(每日检索行数)
    attr = chart_dao.get_date_list(one_month_before, today)
    effect_data = chart_dao.querylog_effect_row_by_date(30)
    effect_dict = {}
    for row in effect_data['rows']:
        effect_dict[row[0]] = int(row[1])
    effect_value = [effect_dict.get(day) if effect_dict.get(day) else 0 for day in attr]
    count_data = chart_dao.querylog_count_by_date(30)
    count_dict = {}
    for row in count_data['rows']:
        count_dict[row[0]] = int(row[1])
    count_value = [count_dict.get(day) if count_dict.get(day) else 0 for day in attr]
    line1 = Line()
    line1.set_global_opts(title_opts=opts.TitleOpts(title='SQL查询统计'),
                          legend_opts=opts.LegendOpts(selected_mode='single'))
    line1.add_xaxis(attr)
    line1.add_yaxis("检索行数", effect_value,
                    markpoint_opts=opts.MarkPointOpts(data=[opts.MarkPointItem(type_="average")]))
    line1.add_yaxis("检索次数", count_value, is_smooth=True,
                    markline_opts=opts.MarkLineOpts(data=[opts.MarkLineItem(type_="max"),
                                                          opts.MarkLineItem(type_="average")]))

    # SQL查询统计(用户检索行数)
    data = chart_dao.querylog_effect_row_by_user(30)
    attr = [row[0] for row in data['rows']]
    value = [int(row[1]) for row in data['rows']]
    pie4 = Pie()
    pie4.set_global_opts(title_opts=opts.TitleOpts(title='SQL查询统计(用户检索行数)'),
                         legend_opts=opts.LegendOpts(
                             orient="vertical", pos_top="15%", pos_left="2%"
                         ))
    pie4.set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c}"))
    pie4.add("", [list(z) for z in zip(attr, value)])

    # SQL查询统计(DB检索行数)
    data = chart_dao.querylog_effect_row_by_db(30)
    attr = [row[0] for row in data['rows']]
    value = [int(row[1]) for row in data['rows']]
    pie5 = Pie()
    pie5.set_global_opts(title_opts=opts.TitleOpts(title='SQL查询统计(DB检索行数)'),
                         legend_opts=opts.LegendOpts(
                             orient="vertical", pos_top="15%", pos_left="2%"
                         ))
    pie5.set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c}", position="left"))

    pie5.add("", [list(z) for z in zip(attr, value)])

    # 可视化展示页面
    page = Page(layout=Page.SimplePageLayout)
    page.add(bar1, pie1, bar2, pie2, line1, pie4, pie5)
    print(page.render_embed())
    return render(request, "dashboard.html", {"chart": page.render_embed()})
