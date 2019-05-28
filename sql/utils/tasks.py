# -*- coding:utf-8 -*-
from django_q.tasks import schedule
from django_q.models import Schedule

import logging

logger = logging.getLogger('default')


def add_sql_schedule(name, run_date, workflow_id):
    """添加/修改sql定时任务"""
    del_schedule(name)
    schedule('sql.utils.execute_sql.execute', workflow_id,
             hook='sql.utils.execute_sql.execute_callback',
             name=name, schedule_type='O', next_run=run_date, repeats=1, timeout=-1)
    logger.debug(f"添加SQL定时执行任务：{name} 执行时间：{run_date}")


def del_schedule(name):
    """删除task"""
    try:
        sql_schedule = Schedule.objects.get(name=name)
        Schedule.delete(sql_schedule)
        logger.debug(f'删除task：{name}')
    except Schedule.DoesNotExist:
        logger.debug(f'删除task：{name}失败，任务不存在')


def task_info(name):
    """获取定时任务详情"""
    try:
        sql_schedule = Schedule.objects.get(name=name)
        return sql_schedule
    except Schedule.DoesNotExist:
        pass
