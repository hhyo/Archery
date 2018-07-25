# -*- coding:utf-8 -*-
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers import SchedulerAlreadyRunningError
from django_apscheduler.jobstores import DjangoJobStore, register_events,register_job
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor

import threading
from time import ctime,sleep

from sql.utils.execute_sql import execute_job

import logging

logger = logging.getLogger('default')
logging.getLogger('apscheduler').setLevel(logging.DEBUG)


executors = {
    'default': ThreadPoolExecutor(20),
    'processpool': ProcessPoolExecutor(5)
}
job_defaults = {
    'coalesce': False,
    'max_instances': 3
}

# 初始化scheduler
scheduler = BackgroundScheduler(executors=executors, job_defaults=job_defaults)
scheduler.add_jobstore(DjangoJobStore(), "default")


def execute_jobs():
    while True:
        #scheduler.print_jobs()
        try:
            scheduler._process_jobs()
        except Exception as e:
            print(e)
            logger.debug("start to process jobs ,but no jobs")
        sleep(60)

register_events(scheduler)
try:
    scheduler.start()
except SchedulerAlreadyRunningError:
    logger.debug("Scheduler is already running!")

t1 = threading.Thread(target=execute_jobs)
t1.start()


# 添加/修改sql执行任务
def add_sqlcronjob(job_id, run_date, workflowId, url):
    #scheduler = BackgroundScheduler()
    #scheduler.add_jobstore(DjangoJobStore(), "default")
    scheduler.add_job(execute_job, 'date', run_date=run_date, args=[workflowId, url], id=job_id,misfire_grace_time=300,
                      replace_existing=True)
    register_events(scheduler)
    try:
        scheduler.start()
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
