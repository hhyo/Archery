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
try:
    scheduler.start()
    logger.debug("Scheduler started!")
except SchedulerAlreadyRunningError:
    logger.debug("Scheduler is already running!")


# 添加/修改sql执行任务
def add_sqlcronjob(job_id, run_date, workflowId, url):
    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")
    scheduler.add_job(execute_job, 'date', run_date=run_date, args=[workflowId, url], id=job_id,
                      replace_existing=True)
    register_events(scheduler)
    try:
        scheduler.start()
        logger.debug("Scheduler started!")
    except SchedulerAlreadyRunningError:
        logger.debug("Scheduler is already running!")
    logger.debug('add_sqlcronjob:' + job_id + " run_date:" + run_date.strftime('%Y-%m-%d %H:%M:%S'))


# 删除sql执行任务
def del_sqlcronjob(job_id):
    logger.debug('del_sqlcronjob:' + job_id)
    return scheduler.remove_job(job_id)


# 获取任务详情
def job_info(job_id):
    return scheduler.get_job(job_id)
