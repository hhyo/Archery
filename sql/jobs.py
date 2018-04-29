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
from .sqlreview import execute_job, getDetailUrl

import logging

logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.DEBUG)

logger = logging.getLogger('default')

# 初始化scheduler
scheduler = BackgroundScheduler()
scheduler.add_jobstore(DjangoJobStore(), "default")
register_events(scheduler)
scheduler.start()


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
    url = getDetailUrl(request) + str(workflowId) + '/'
    job_id = Const.workflowJobprefix['sqlreview'] + '-' + str(workflowId)

    try:
        scheduler = BackgroundScheduler()
        scheduler.add_jobstore(DjangoJobStore(), "default")
        scheduler.add_job(execute_job, 'date', run_date=run_date, args=[workflowId, url], id=job_id,
                          replace_existing=True)
        register_events(scheduler)
        scheduler.start()
        workflowDetail.status = Const.workflowStatus['tasktiming']
        workflowDetail.save()
    except Exception as e:
        context = {'errMsg': '任务添加失败，错误信息：' + str(e)}
        return render(request, 'error.html', context)
    else:
        logger.debug('add_sqlcronjob:' + job_id)

    return HttpResponseRedirect(reverse('sql:detail', args=(workflowId,)))


# 删除sql执行任务
def del_sqlcronjob(job_id):
    logger.debug('del_sqlcronjob:' + job_id)
    return scheduler.remove_job(job_id)


# 获取任务详情
def job_info(job_id):
    return scheduler.get_job(job_id)
