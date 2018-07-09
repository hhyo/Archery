# -*- coding: UTF-8 -*-

from django.shortcuts import render
from pyecharts import Pie, Bar, Line
from pyecharts import Page, Grid
from sql.utils.inception import InceptionDao
from sql.utils.chart_dao import ChartDao

chart_dao = ChartDao()


def pyecharts(request):
    # 工单数量统计
    bar1 = Bar('工单数量统计', width="100%")
    month_data = chart_dao.workflow_by_date('year')
    month_attr = [row[0] for row in month_data['rows']]
    month_value = [row[1] for row in month_data['rows']]
    bar1.add("月统计", month_attr, month_value, is_stack=False, legend_selectedmode='single')

    # 工单按组统计
    pie1 = Pie('工单按组统计', width="100%")
    data = chart_dao.workflow_by_group(1)
    attr = [row[0] for row in data['rows']]
    value = [row[1] for row in data['rows']]
    pie1.add("月统计", attr, value, is_legend_show=False, is_label_show=True)

    # 工单按人统计
    bar2 = Bar('工单按人统计', width="100%")
    data = chart_dao.workflow_by_user(1)
    attr = [row[0] for row in data['rows']]
    value = [row[1] for row in data['rows']]
    bar2.add("月统计", attr, value, is_label_show=True)

    # SQL语句类型统计
    pie2 = Pie("SQL类型统计", width="100%")
    data = chart_dao.sql_syntax()
    attr = [row[0] for row in data['rows']]
    value = [row[1] for row in data['rows']]
    pie2.add("", attr, value, is_label_show=True)

    # SQL执行情况统计
    pie3 = Pie("SQL执行统计", width="100%")
    data = InceptionDao().statistic()
    attr = data['column_list']
    if data['column_list']:
        value = [int(row) for row in data['rows'][0]]
    else:
        value = []
    pie3.add("", attr, value, is_legend_show=True)

    # 可视化展示页面
    page = Page()
    page.add(bar1)
    page.add(pie1)
    page.add(bar2)
    page.add(pie2)
    page.add(pie3)
    myechart = page.render_embed()  # 渲染配置
    host = 'https://pyecharts.github.io/assets/js'  # js文件源地址
    script_list = page.get_js_dependencies()  # 获取依赖的js文件名称（只获取当前视图需要的js）
    return render(request, "charts.html", {"myechart": myechart, "host": host, "script_list": script_list})
