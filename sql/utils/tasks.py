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


def add_kill_conn_schedule(name, run_date, instance_id, thread_id):
    """添加/修改终止数据库连接的定时任务"""
    del_schedule(name)
    schedule('sql.query.kill_query_conn', instance_id, thread_id,
             name=name, schedule_type='O', next_run=run_date, repeats=1, timeout=-1)


def add_sync_ding_user_schedule():
    """添加钉钉同步用户定时任务"""
    del_schedule(name='同步钉钉用户ID')
    schedule('sql.utils.ding_api.sync_ding_user_id',
             name='同步钉钉用户ID', schedule_type='D', repeats=-1, timeout=-1)


def del_schedule(name):
    """删除task"""
    try:
        sql_schedule = Schedule.objects.get(name=name)
        Schedule.delete(sql_schedule)
        logger.debug(f'删除task：{name}')
    except Schedule.DoesNotExist:
        pass


def task_info(name):
    """获取定时任务详情"""
    try:
        sql_schedule = Schedule.objects.get(name=name)
        return sql_schedule
    except Schedule.DoesNotExist:
        pass
