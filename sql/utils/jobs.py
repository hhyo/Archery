# -*- coding:utf-8 -*-
from django_q.tasks import schedule
from django_q.models import Schedule

import logging

logger = logging.getLogger('default')


# 添加/修改sql执行任务
def add_sqlcronjob(job_id, run_date, workflow_id, url):
    del_sqlcronjob(job_id)
    schedule('sql.utils.execute_sql.execute_job', workflow_id, url, name=job_id, schedule_type='O', next_run=run_date, repeats=1)
    logger.debug('add_sqlcronjob:' + job_id + " run_date:" + run_date.strftime('%Y-%m-%d %H:%M:%S'))


# 删除sql执行任务
def del_sqlcronjob(job_id):
    try:
        sql_schedule = Schedule.objects.get(name=job_id)
        Schedule.delete(sql_schedule)
        logger.debug('del_sqlcronjob:' + job_id)
    except Schedule.DoesNotExist:
        logger.debug('del_sqlcronjob {} failed, job does not exist'.format(job_id))


# 获取任务详情
def job_info(job_id):
    try:
        sql_schedule = Schedule.objects.get(name=job_id)
        return sql_schedule
    except Schedule.DoesNotExist:
        pass
