# -*- coding: UTF-8 -*-
from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from pyecharts import Pie, Bar, Line
from pyecharts import Page
from sql.utils.inception import InceptionDao
from sql.utils.chart_dao import ChartDao
from datetime import date
from dateutil.relativedelta import relativedelta

chart_dao = ChartDao()


@permission_required('sql.menu_dashboard', raise_exception=True)
def pyecharts(request):
    # 工单数量统计
    bar1 = Bar('SQL上线工单统计(数量)', width="100%")
    data = chart_dao.workflow_by_date(1)
    begin_date = (date.today() - relativedelta(months=+1)).strftime("%Y-%m-%d")
    attr = chart_dao.get_date_list(begin_date, date.today().strftime("%Y-%m-%d"))
    dict = {}
    for row in data['rows']:
        dict[row[0]] = row[1]
    value = [dict.get(day) if dict.get(day) else 0 for day in attr]
    bar1.add("月统计", attr, value, is_stack=False, legend_selectedmode='single')

    # 工单按组统计
    pie1 = Pie('SQL上线工单统计(组)', width="100%")
    data = chart_dao.workflow_by_group(1)
    attr = [row[0] for row in data['rows']]
    value = [row[1] for row in data['rows']]
    pie1.add("月统计", attr, value, is_legend_show=False, is_label_show=True)

    # 工单按人统计
    bar2 = Bar('SQL上线工单统计(用户)', width="100%")
    data = chart_dao.workflow_by_user(1)
    attr = [row[0] for row in data['rows']]
    value = [row[1] for row in data['rows']]
    bar2.add("月统计", attr, value, is_label_show=True)

    # SQL语句类型统计
    pie2 = Pie("SQL上线工单统计(类型)", width="100%")
    data = chart_dao.sql_syntax()
    attr = [row[0] for row in data['rows']]
    value = [row[1] for row in data['rows']]
    pie2.add("", attr, value, is_label_show=True)

    # SQL执行情况统计
    pie3 = Pie("SQL上线工单统计(Inception)", width="100%")
    data = InceptionDao().statistic()
    attr = data['column_list']
    if data['column_list']:
        value = [int(row) for row in data['rows'][0]]
    else:
        value = []
    pie3.add("", attr, value, is_legend_show=False, is_label_show=True)

    # SQL查询统计(每日检索行数)
    line1 = Line("SQL查询统计", width="100%")
    begin_date = (date.today() - relativedelta(months=+1)).strftime("%Y-%m-%d")
    attr = chart_dao.get_date_list(begin_date, date.today().strftime("%Y-%m-%d"))
    effect_data = chart_dao.querylog_effect_row_by_date(1)
    effect_dict = {}
    for row in effect_data['rows']:
        effect_dict[row[0]] = int(row[1])
    effect_value = [effect_dict.get(day) if effect_dict.get(day) else 0 for day in attr]
    count_data = chart_dao.querylog_count_by_date(1)
    count_dict = {}
    for row in count_data['rows']:
        count_dict[row[0]] = int(row[1])
    count_value = [count_dict.get(day) if count_dict.get(day) else 0 for day in attr]

    line1.add("检索行数", attr, effect_value, is_stack=False, legend_selectedmode='single', mark_point=["average"])
    line1.add("检索次数", attr, count_value, is_stack=False, legend_selectedmode='single', is_smooth=True,
              mark_line=["max", "average"])

    # SQL查询统计(用户检索行数)
    pie4 = Pie("SQL查询统计(用户检索行数)", width="100%")
    data = chart_dao.querylog_effect_row_by_user(1)
    attr = [row[0] for row in data['rows']]
    value = [int(row[1]) for row in data['rows']]
    pie4.add("月统计", attr, value, radius=[40, 75], is_legend_show=False, is_label_show=True)

    # SQL查询统计(DB检索行数)
    pie5 = Pie("SQL查询统计(DB检索行数)", width="100%")
    data = chart_dao.querylog_effect_row_by_db(1)
    attr = [row[0] for row in data['rows']]
    value = [int(row[1]) for row in data['rows']]
    pie5.add("月统计", attr, value, is_legend_show=False, is_label_show=True)

    # 可视化展示页面
    page = Page()
    page.add(bar1)
    page.add(pie1)
    page.add(bar2)
    page.add(pie2)
    page.add(pie3)
    page.add(line1)
    page.add(pie4)
    page.add(pie5)
    myechart = page.render_embed()  # 渲染配置
    host = 'https://pyecharts.github.io/assets/js'  # js文件源地址
    script_list = page.get_js_dependencies()  # 获取依赖的js文件名称（只获取当前视图需要的js）
    return render(request, "charts.html", {"myechart": myechart, "host": host, "script_list": script_list})
