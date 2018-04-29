# -*- coding:utf-8 -*-
import datetime
import atexit
import fcntl

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers import SchedulerAlreadyRunningError, SchedulerNotRunningError
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django_apscheduler.jobstores import DjangoJobStore, register_events

from sql.const import Const
from sql.models import workflow
from .sqlreview import _execute_job, _getDetailUrl

import logging

logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.DEBUG)

# 用全局锁确保scheduler只运行一次，解决django使用多进程部署时apscheduler重复运行的问题
# 参考：https://vimer.im/posts/Solving-the-problem-of-APScheduler-duplication-in-multi-process/
f = open("scheduler.lock", "wb")
try:
    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
except:
    pass
else:
    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")

    register_events(scheduler)
    scheduler.start()


def unlock():
    fcntl.flock(f, fcntl.LOCK_UN)
    f.close()


atexit.register(unlock)


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
