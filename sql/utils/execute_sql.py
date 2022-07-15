# -*- coding: UTF-8 -*-
import logging
import traceback

from django.db import close_old_connections, connection, transaction
from django_redis import get_redis_connection
from common.utils.const import WorkflowDict
from common.config import SysConfig
from sql.engines.models import ReviewResult, ReviewSet
from sql.models import SqlWorkflow
from sql.notify import notify_for_execute
from sql.utils.workflow_audit import Audit
from sql.engines import get_engine

logger = logging.getLogger("default")


def execute(workflow_id, user=None):
    """为延时或异步任务准备的execute, 传入工单ID和执行人信息"""
    # 使用当前读防止重复执行
    with transaction.atomic():
        workflow_detail = SqlWorkflow.objects.select_for_update().get(id=workflow_id)
        # 只有排队中和定时执行的数据才可以继续执行，否则直接抛错
        if workflow_detail.status not in ["workflow_queuing", "workflow_timingtask"]:
            raise Exception("工单状态不正确，禁止执行！")
        # 将工单状态修改为执行中
        else:
            SqlWorkflow(id=workflow_id, status="workflow_executing").save(
                update_fields=["status"]
            )
    # 增加执行日志
    audit_id = Audit.detail_by_workflow_id(
        workflow_id=workflow_id, workflow_type=WorkflowDict.workflow_type["sqlreview"]
    ).audit_id
    Audit.add_log(
        audit_id=audit_id,
        operation_type=5,
        operation_type_desc="执行工单",
        operation_info="工单开始执行" if user else "系统定时执行工单",
        operator=user.username if user else "",
        operator_display=user.display if user else "系统",
    )
    execute_engine = get_engine(instance=workflow_detail.instance)
    return execute_engine.execute_workflow(workflow=workflow_detail)


def execute_callback(task):
    """异步任务的回调, 将结果填入数据库等等
    使用django-q的hook, 传入参数为整个task
    task.result 是真正的结果
    """
    # https://stackoverflow.com/questions/7835272/django-operationalerror-2006-mysql-server-has-gone-away
    if connection.connection and not connection.is_usable():
        close_old_connections()
    workflow_id = task.args[0]
    # 判断工单状态，如果不是执行中的，不允许更新信息，直接抛错记录日志
    with transaction.atomic():
        workflow = SqlWorkflow.objects.get(id=workflow_id)
        if workflow.status != "workflow_executing":
            raise Exception(f"工单{workflow.id}状态不正确，禁止重复更新执行结果！")

    workflow.finish_time = task.stopped

    if not task.success:
        # 不成功会返回错误堆栈信息，构造一个错误信息
        workflow.status = "workflow_exception"
        execute_result = ReviewSet(full_sql=workflow.sqlworkflowcontent.sql_content)
        execute_result.rows = [
            ReviewResult(
                stage="Execute failed",
                errlevel=2,
                stagestatus="异常终止",
                errormessage=task.result,
                sql=workflow.sqlworkflowcontent.sql_content,
            )
        ]
    elif task.result.warning or task.result.error:
        execute_result = task.result
        workflow.status = "workflow_exception"
    else:
        execute_result = task.result
        workflow.status = "workflow_finish"
    try:
        # 保存执行结果
        workflow.sqlworkflowcontent.execute_result = execute_result.json()
        workflow.sqlworkflowcontent.save()
        workflow.save()
    except Exception as e:
        logger.error(f"SQL工单回调异常: {workflow_id} {traceback.format_exc()}")
        SqlWorkflow.objects.filter(id=workflow_id).update(
            finish_time=task.stopped,
            status="workflow_exception",
        )
        workflow.sqlworkflowcontent.execute_result = {f"{e}"}
        workflow.sqlworkflowcontent.save()
    # 增加工单日志
    audit_id = Audit.detail_by_workflow_id(
        workflow_id=workflow_id, workflow_type=WorkflowDict.workflow_type["sqlreview"]
    ).audit_id
    Audit.add_log(
        audit_id=audit_id,
        operation_type=6,
        operation_type_desc="执行结束",
        operation_info="执行结果：{}".format(workflow.get_status_display()),
        operator="",
        operator_display="系统",
    )

    # DDL工单结束后清空实例资源缓存
    if workflow.syntax_type == 1:
        r = get_redis_connection("default")
        for key in r.scan_iter(match="*insRes*", count=2000):
            r.delete(key)

    # 开启了Execute阶段通知参数才发送消息通知
    sys_config = SysConfig()
    is_notified = (
        "Execute" in sys_config.get("notify_phase_control").split(",")
        if sys_config.get("notify_phase_control")
        else True
    )
    if is_notified:
        notify_for_execute(workflow)
