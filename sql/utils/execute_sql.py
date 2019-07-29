# -*- coding: UTF-8 -*-

from common.utils.const import WorkflowDict
from sql.engines.models import ReviewResult, ReviewSet
from sql.models import SqlWorkflow
from sql.notify import notify_for_execute
from sql.utils.workflow_audit import Audit
from sql.engines import get_engine


def execute(workflow_id):
    """为延时或异步任务准备的execute, 传入工单ID即可"""
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    # 给定时执行的工单增加执行日志
    if workflow_detail.status == 'workflow_timingtask':
        # 将工单状态修改为执行中
        SqlWorkflow(id=workflow_id, status='workflow_executing').save(update_fields=['status'])
        audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                               workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
        Audit.add_log(audit_id=audit_id,
                      operation_type=5,
                      operation_type_desc='执行工单',
                      operation_info='系统定时执行',
                      operator='',
                      operator_display='系统'
                      )
    execute_engine = get_engine(instance=workflow_detail.instance)
    return execute_engine.execute_workflow(workflow=workflow_detail)


def execute_callback(task):
    """异步任务的回调, 将结果填入数据库等等
    使用django-q的hook, 传入参数为整个task
    task.result 是真正的结果
    """
    workflow_id = task.args[0]
    workflow = SqlWorkflow.objects.get(id=workflow_id)
    workflow.finish_time = task.stopped

    if not task.success:
        # 不成功会返回错误堆栈信息，构造一个错误信息
        workflow.status = 'workflow_exception'
        execute_result = ReviewSet(full_sql=workflow.sqlworkflowcontent.sql_content)
        execute_result.rows = [ReviewResult(
            stage='Execute failed',
            errlevel=2,
            stagestatus='异常终止',
            errormessage=task.result,
            sql=workflow.sqlworkflowcontent.sql_content)]
    elif task.result.warning or task.result.error:
        execute_result = task.result
        workflow.status = 'workflow_exception'
    else:
        execute_result = task.result
        workflow.status = 'workflow_finish'
    # 保存执行结果
    workflow.sqlworkflowcontent.execute_result = execute_result.json()
    workflow.sqlworkflowcontent.save()
    workflow.save()

    # 增加工单日志
    audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                           workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
    Audit.add_log(audit_id=audit_id,
                  operation_type=6,
                  operation_type_desc='执行结束',
                  operation_info='执行结果：{}'.format(workflow.get_status_display()),
                  operator='',
                  operator_display='系统'
                  )

    # 发送消息
    notify_for_execute(workflow)
