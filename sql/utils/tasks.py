# -*- coding:utf-8 -*-
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from celery import signature
from celery.result import AsyncResult
from celery.exceptions import SoftTimeLimitExceeded
import logging
import pytz

logger = logging.getLogger("default")
tz = pytz.timezone('Asia/Shanghai')

def add_sql_schedule(name, run_date, workflow_id):
    # 因这里存在循环调用问题，所以不能直接import execute
    if run_date.tzinfo is None or run_date.tzinfo.utcoffset(run_date) is None:
        run_date = tz.localize(run_date)  # 确保 run_date 带有时区信息
    execute_sql_sig = signature('sql.utils.execute_sql.execute', args=(workflow_id,),task_id=name)
    # 创建回调任务的签名
    callback_sig = signature('sql.utils.execute_sql.execute_callback', args=(workflow_id,))
    task_chain = execute_sql_sig | callback_sig

    # 调度链式任务
    task_chain.apply_async(eta=run_date)
    logger.warning(f"添加 SQL 定时执行任务：{name} 执行时间：{run_date}")



def add_kill_conn_schedule(name, run_date, instance_id, thread_id):
    if run_date.tzinfo is None or run_date.tzinfo.utcoffset(run_date) is None:
        run_date = tz.localize(run_date)  # 确保 run_date 带有时区信息
    """添加/修改终止数据库连接的定时任务"""
    sig = signature('sql.query.kill_query_conn', args=[instance_id,thread_id])
    sig.apply_async(eta=run_date, task_id=name)


def add_sync_ding_user_schedule():
    schedule, created = IntervalSchedule.objects.get_or_create(
        every=1,  # 每1天
        period=IntervalSchedule.DAYS
    )
    """添加钉钉同步用户定时任务"""
    PeriodicTask.objects.filter(name="同步钉钉用户ID").delete()
    # 现在创建定时任务
    PeriodicTask.objects.create(
        interval=schedule,  # 使用上面创建的调度间隔
        name='sync_ding_user_id_every_day',  # 名称
        task='path.to.tasks.sync_ding_user_id',  # Celery 任务的导入路径
    )

def del_schedule(name):
    """删除schedule"""
    task_result = AsyncResult(name)
    try:
        task_result.revoke(terminate=False)  # 如果任务已经开始执行，可以尝试终止它
    except SoftTimeLimitExceeded:
        print("任务执行时间过长，尝试终止失败")
    except Exception as e:
        print(f"终止任务时发生错误：{str(e)}")


def task_info(name):
    """
    获取定时任务详情
    如果未使用celery beat实现的定时任务，这里无法获取到对应的结果，只会返回一个None
    """
    try:
        periodic_task = PeriodicTask.objects.get(name=name)
        return periodic_task
    except PeriodicTask.DoesNotExist:
        return None