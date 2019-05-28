# -*- coding: UTF-8 -*-
import simplejson as json

from common.utils.const import WorkflowDict
from sql.engines.models import ReviewSet, ReviewResult
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
        # 不成功会返回错误堆栈信息，构造一个错误信息追加到执行结果后面
        workflow.status = 'workflow_exception'
        if workflow.sqlworkflowcontent.execute_result:
            execute_result = json.loads(workflow.sqlworkflowcontent.execute_result)
        else:
            execute_result = []
        execute_result.append(ReviewResult(
            id=0,
            stage='Execute failed',
            errlevel=2,
            stagestatus='异常终止',
            errormessage=task.result,
            sql='执行异常信息',
            affected_rows=0,
            actual_affected_rows=0,
            sequence='0_0_0',
            backup_dbname=None,
            execute_time=0,
            sqlsha1='').__dict__)
        execute_result = json.dumps(execute_result)
    elif task.result.warning or task.result.error:
        execute_result = task.result
        workflow.status = 'workflow_exception'
        execute_result = execute_result.json()
    else:
        execute_result = task.result
        workflow.status = 'workflow_finish'
        execute_result = execute_result.json()
    # 保存执行结果
    workflow.sqlworkflowcontent.execute_result = execute_result
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
