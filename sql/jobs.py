# -*- coding:utf-8 -*-
import datetime
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers import SchedulerAlreadyRunningError, SchedulerNotRunningError
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django_apscheduler.jobstores import DjangoJobStore, register_events, register_job

from sql.const import Const
from sql.models import workflow
from .sqlreview import _execute_job, _getDetailUrl

import logging

logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.DEBUG)

scheduler = BackgroundScheduler()
scheduler.add_jobstore(DjangoJobStore(), "default")


# 增加心跳检测job防止任务执行完成后调度器自动关闭
@scheduler.scheduled_job("cron", second=0, id='Heartbeat')
def heartbeat_job():
    time.sleep(5)
    print("Scheduler is running!")


register_events(scheduler)

try:
    scheduler.start()
    print("Scheduler started!")
except SchedulerAlreadyRunningError:
    print("Scheduler is already running!")


# 添加/修改sql执行任务
def add_sqlcronjob(request):
    workflowId = request.POST.get('workflowid')
    run_date = request.POST.get('run_date')
    if run_date is None or workflowId is None:
        context = {'errMsg': '时间不能为空'}
        return render(request, 'error.html', context)
    elif run_date < datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
        context = {'errMsg': '时间不能小于当前时间'}
        return render(request, 'error.html', context)
    workflowDetail = workflow.objects.get(id=workflowId)
    if workflowDetail.status not in ['审核通过', '定时执行']:
        context = {'errMsg': '必须为审核通过或者定时执行状态'}
        return render(request, 'error.html', context)

    run_date = datetime.datetime.strptime(run_date, "%Y-%m-%d %H:%M:%S")
    url = _getDetailUrl(request) + str(workflowId) + '/'
    job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflowId)

    try:
        scheduler.add_job(_execute_job, 'date', run_date=run_date, args=[workflowId, url], id=job_id,
                          replace_existing=True)
        workflowDetail.status = Const.workflowStatus['tasktiming']
        workflowDetail.save()
    except Exception as e:
        context = {'errMsg': '任务添加失败，错误信息：' + str(e)}
        return render(request, 'error.html', context)
    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))


# 删除sql执行任务
def del_sqlcronjob(job_id):
    return scheduler.remove_job(job_id)


# 获取任务详情
def job_info(job_id):
    return scheduler.get_job(job_id)
