# -*- coding: UTF-8 -*-
import datetime
import logging
import traceback

import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from common.config import SysConfig
from common.utils.const import Const, WorkflowDict
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines.models import ReviewResult, ReviewSet
from sql.notify import notify_for_audit, notify_for_execute
from sql.models import ResourceGroup
from sql.utils.resource_group import user_groups, user_instances
from sql.utils.tasks import add_sql_schedule, del_schedule
from sql.utils.sql_review import can_timingtask, can_cancel, can_execute, on_correct_time_period, can_view, can_rollback
from sql.utils.workflow_audit import Audit
from .models import SqlWorkflow, SqlWorkflowContent, Instance
from django_q.tasks import async_task

from sql.engines import get_engine

logger = logging.getLogger('default')


@permission_required('sql.menu_sqlworkflow', raise_exception=True)
def sql_workflow_list(request):
    return _sql_workflow_list(request)

@permission_required('sql.audit_user', raise_exception=True)
def sql_workflow_list_audit(request):
    return _sql_workflow_list(request)

def _sql_workflow_list(request):
    """
    获取审核列表
    :param request:
    :return:
    """
    nav_status = request.POST.get('navStatus')
    instance_id = request.POST.get('instance_id')
    resource_group_id = request.POST.get('group_id')
    start_date = request.POST.get('start_date')
    end_date = request.POST.get('end_date')
    limit = int(request.POST.get('limit',0))
    offset = int(request.POST.get('offset',0))
    limit = offset + limit
    limit = limit if limit else None
    search = request.POST.get('search')
    user = request.user

    # 组合筛选项
    filter_dict = dict()
    # 工单状态
    if nav_status:
        filter_dict['status'] = nav_status
    # 实例
    if instance_id:
        filter_dict['instance_id'] = instance_id
    # 资源组
    if resource_group_id:
        filter_dict['group_id'] = resource_group_id
    # 时间
    if start_date and end_date:
        end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d') + datetime.timedelta(days=1)
        filter_dict['create_time__range'] = (start_date, end_date)
    # 管理员，审计员，可查看所有工单
    if user.is_superuser or user.has_perm('sql.audit_user'):
        pass
    # 非管理员，拥有审核权限、资源组粒度执行权限的，可以查看组内所有工单
    elif user.has_perm('sql.sql_review') or user.has_perm('sql.sql_execute_for_resource_group'):
        # 先获取用户所在资源组列表
        group_list = user_groups(user)
        group_ids = [group.group_id for group in group_list]
        filter_dict['group_id__in'] = group_ids
    # 其他人只能查看自己提交的工单
    else:
        filter_dict['engineer'] = user.username

    # 过滤组合筛选项
    workflow = SqlWorkflow.objects.filter(**filter_dict)

    # 过滤搜索项，模糊检索项包括提交人名称、工单名
    if search:
        workflow = workflow.filter(Q(engineer_display__icontains=search) | Q(workflow_name__icontains=search))

    count = workflow.count()
    workflow_list = workflow.order_by('-create_time')[offset:limit].values(
        "id", "workflow_name", "engineer_display",
        "status", "is_backup", "create_time",
        "instance__instance_name", "db_name",
        "group_name", "syntax_type")

    # QuerySet 序列化
    rows = [row for row in workflow_list]
    result = {"total": count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.sql_submit', raise_exception=True)
def check(request):
    """SQL检测按钮, 此处没有产生工单"""
    sql_content = request.POST.get('sql_content')
    instance_name = request.POST.get('instance_name')
    instance = Instance.objects.get(instance_name=instance_name)
    db_name = request.POST.get('db_name')

    result = {'status': 0, 'msg': 'ok', 'data': {}}
    # 服务器端参数验证
    if sql_content is None or instance_name is None or db_name is None:
        result['status'] = 1
        result['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 交给engine进行检测
    try:
        check_engine = get_engine(instance=instance)
        check_result = check_engine.execute_check(db_name=db_name, sql=sql_content.strip())
    except Exception as e:
        result['status'] = 1
        result['msg'] = str(e)
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 处理检测结果
    result['data']['rows'] = check_result.to_dict()
    result['data']['CheckWarningCount'] = check_result.warning_count
    result['data']['CheckErrorCount'] = check_result.error_count
    return HttpResponse(json.dumps(result), content_type='application/json')


@permission_required('sql.sql_submit', raise_exception=True)
def submit(request):
    """正式提交SQL, 此处生成工单"""
    sql_content = request.POST.get('sql_content').strip()
    workflow_title = request.POST.get('workflow_name')
    demand_url = request.POST.get('demand_url', '')
    # 检查用户是否有权限涉及到资源组等， 比较复杂， 可以把检查权限改成一个独立的方法
    group_name = request.POST.get('group_name')
    group_id = ResourceGroup.objects.get(group_name=group_name).group_id
    instance_name = request.POST.get('instance_name')
    instance = Instance.objects.get(instance_name=instance_name)
    db_name = request.POST.get('db_name')
    is_backup = True if request.POST.get('is_backup') == 'True' else False
    cc_users = request.POST.getlist('cc_users')
    run_date_start = request.POST.get('run_date_start')
    run_date_end = request.POST.get('run_date_end')

    # 服务器端参数验证
    if None in [sql_content, db_name, instance_name, db_name, is_backup, demand_url]:
        context = {'errMsg': '页面提交参数可能为空'}
        return render(request, 'error.html', context)

    # 验证组权限（用户是否在该组、该组是否有指定实例）
    try:
        user_instances(request.user, tag_codes=['can_write']).get(instance_name=instance_name)
    except instance.DoesNotExist:
        context = {'errMsg': '你所在组未关联该实例！'}
        return render(request, 'error.html', context)

    # 再次交给engine进行检测，防止绕过
    try:
        check_engine = get_engine(instance=instance)
        check_result = check_engine.execute_check(db_name=db_name, sql=sql_content.strip())
    except Exception as e:
        context = {'errMsg': str(e)}
        return render(request, 'error.html', context)

    # 未开启备份选项，并且engine支持备份，强制设置备份
    sys_config = SysConfig()
    if not sys_config.get('enable_backup_switch') and check_engine.auto_backup:
        is_backup = True

    # 按照系统配置确定是自动驳回还是放行
    auto_review_wrong = sys_config.get('auto_review_wrong', '')  # 1表示出现警告就驳回，2和空表示出现错误才驳回
    workflow_status = 'workflow_manreviewing'
    if check_result.warning_count > 0 and auto_review_wrong == '1':
        workflow_status = 'workflow_autoreviewwrong'
    elif check_result.error_count > 0 and auto_review_wrong in ('', '1', '2'):
        workflow_status = 'workflow_autoreviewwrong'

    # 调用工作流生成工单
    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 存进数据库里
            sql_workflow = SqlWorkflow.objects.create(
                workflow_name=workflow_title,
                demand_url=demand_url,
                group_id=group_id,
                group_name=group_name,
                engineer=request.user.username,
                engineer_display=request.user.display,
                audit_auth_groups=Audit.settings(group_id, WorkflowDict.workflow_type['sqlreview']),
                status=workflow_status,
                is_backup=is_backup,
                instance=instance,
                db_name=db_name,
                is_manual=0,
                syntax_type=check_result.syntax_type,
                create_time=timezone.now(),
                run_date_start=run_date_start or None,
                run_date_end=run_date_end or None
            )
            SqlWorkflowContent.objects.create(workflow=sql_workflow,
                                              sql_content=sql_content,
                                              review_content=check_result.json(),
                                              execute_result=''
                                              )
            workflow_id = sql_workflow.id
            # 自动审核通过了，才调用工作流
            if workflow_status == 'workflow_manreviewing':
                # 调用工作流插入审核信息, SQL上线权限申请workflow_type=2
                Audit.add(WorkflowDict.workflow_type['sqlreview'], workflow_id)
    except Exception as msg:
        logger.error(f"提交工单报错，错误信息：{traceback.format_exc()}")
        context = {'errMsg': msg}
        logger.error(traceback.format_exc())
        return render(request, 'error.html', context)
    else:
        # 自动审核通过且开启了Apply阶段通知参数才发送消息通知
        is_notified = 'Apply' in sys_config.get('notify_phase_control').split(',') \
            if sys_config.get('notify_phase_control') else True
        if workflow_status == 'workflow_manreviewing' and is_notified:
            # 获取审核信息
            audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                   workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
            async_task(notify_for_audit, audit_id=audit_id, cc_users=cc_users, timeout=60,
                       task_name=f'sqlreview-submit-{workflow_id}')

    return HttpResponseRedirect(reverse('sql:detail', args=(workflow_id,)))


def detail_content(request):
    """获取工单内容"""
    workflow_id = request.GET.get('workflow_id')
    workflow_detail = get_object_or_404(SqlWorkflow, pk=workflow_id)
    if not can_view(request.user, workflow_id):
        raise PermissionDenied
    if workflow_detail.status in ['workflow_finish', 'workflow_exception']:
        rows = workflow_detail.sqlworkflowcontent.execute_result
    else:
        rows = workflow_detail.sqlworkflowcontent.review_content

    review_result = ReviewSet()
    if rows:
        try:
            # 检验rows能不能正常解析
            loaded_rows = json.loads(rows)
            #  兼容旧数据'[[]]'格式，转换为新格式[{}]
            if isinstance(loaded_rows[-1], list):
                for r in loaded_rows:
                    review_result.rows += [ReviewResult(inception_result=r)]
                rows = review_result.json()
        except IndexError:
            review_result.rows += [ReviewResult(
                id=1,
                sql=workflow_detail.sqlworkflowcontent.sql_content,
                errormessage="Json decode failed."
                             "执行结果Json解析失败, 请联系管理员"
            )]
            rows = review_result.json()
        except json.decoder.JSONDecodeError:
            review_result.rows += [ReviewResult(
                id=1,
                sql=workflow_detail.sqlworkflowcontent.sql_content,
                # 迫于无法单元测试这里加上英文报错信息
                errormessage="Json decode failed."
                             "执行结果Json解析失败, 请联系管理员"
            )]
            rows = review_result.json()
    else:
        rows = workflow_detail.sqlworkflowcontent.review_content

    result = {"rows": json.loads(rows)}
    return HttpResponse(json.dumps(result), content_type='application/json')


def backup_sql(request):
    """获取回滚语句"""
    workflow_id = request.GET.get('workflow_id')
    if not can_rollback(request.user, workflow_id):
        raise PermissionDenied
    workflow = get_object_or_404(SqlWorkflow, pk=workflow_id)

    try:
        query_engine = get_engine(instance=workflow.instance)
        list_backup_sql = query_engine.get_rollback(workflow=workflow)
    except Exception as msg:
        logger.error(traceback.format_exc())
        return JsonResponse({'status': 1, 'msg': f'{msg}', 'rows': []})

    result = {'status': 0, 'msg': '', 'rows': list_backup_sql}
    return HttpResponse(json.dumps(result), content_type='application/json')


@permission_required('sql.sql_review', raise_exception=True)
def alter_run_date(request):
    """
    审核人修改可执行时间
    :param request:
    :return:
    """
    workflow_id = int(request.POST.get('workflow_id', 0))
    run_date_start = request.POST.get('run_date_start')
    run_date_end = request.POST.get('run_date_end')
    if workflow_id == 0:
        context = {'errMsg': 'workflow_id参数为空.'}
        return render(request, 'error.html', context)

    user = request.user
    if Audit.can_review(user, workflow_id, 2) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    try:
        # 存进数据库里
        SqlWorkflow(id=workflow_id,
                    run_date_start=run_date_start or None,
                    run_date_end=run_date_end or None
                    ).save(update_fields=['run_date_start', 'run_date_end'])
    except Exception as msg:
        context = {'errMsg': msg}
        return render(request, 'error.html', context)

    return HttpResponseRedirect(reverse('sql:detail', args=(workflow_id,)))


@permission_required('sql.sql_review', raise_exception=True)
def passed(request):
    """
    审核通过，不执行
    :param request:
    :return:
    """
    workflow_id = int(request.POST.get('workflow_id', 0))
    audit_remark = request.POST.get('audit_remark', '')
    if workflow_id == 0:
        context = {'errMsg': 'workflow_id参数为空.'}
        return render(request, 'error.html', context)

    user = request.user
    if Audit.can_review(user, workflow_id, 2) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 调用工作流接口审核
            audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                   workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
            audit_result = Audit.audit(audit_id, WorkflowDict.workflow_status['audit_success'],
                                       user.username, audit_remark)

            # 按照审核结果更新业务表审核状态
            if audit_result['data']['workflow_status'] == WorkflowDict.workflow_status['audit_success']:
                # 将流程状态修改为审核通过
                SqlWorkflow(id=workflow_id, status='workflow_review_pass').save(update_fields=['status'])
    except Exception as msg:
        logger.error(f"审核工单报错，错误信息：{traceback.format_exc()}")
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    else:
        # 开启了Pass阶段通知参数才发送消息通知
        sys_config = SysConfig()
        is_notified = 'Pass' in sys_config.get('notify_phase_control').split(',') \
            if sys_config.get('notify_phase_control') else True
        if is_notified:
            async_task(notify_for_audit, audit_id=audit_id, audit_remark=audit_remark, timeout=60,
                       task_name=f'sqlreview-pass-{workflow_id}')

    return HttpResponseRedirect(reverse('sql:detail', args=(workflow_id,)))


def execute(request):
    """
    执行SQL
    :param request:
    :return:
    """
    # 校验多个权限
    if not (request.user.has_perm('sql.sql_execute') or request.user.has_perm('sql.sql_execute_for_resource_group')):
        raise PermissionDenied
    workflow_id = int(request.POST.get('workflow_id', 0))
    if workflow_id == 0:
        context = {'errMsg': 'workflow_id参数为空.'}
        return render(request, 'error.html', context)

    if can_execute(request.user, workflow_id) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    if on_correct_time_period(workflow_id) is False:
        context = {'errMsg': '不在可执行时间范围内，如果需要修改执行时间请重新提交工单!'}
        return render(request, 'error.html', context)
    # 获取审核信息
    audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                           workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id
    # 根据执行模式进行对应修改
    mode = request.POST.get('mode')
    # 交由系统执行
    if mode == "auto":
        # 修改工单状态为排队中
        SqlWorkflow(id=workflow_id, status="workflow_queuing").save(update_fields=['status'])
        # 删除定时执行任务
        schedule_name = f"sqlreview-timing-{workflow_id}"
        del_schedule(schedule_name)
        # 加入执行队列
        async_task('sql.utils.execute_sql.execute', workflow_id, request.user,
                   hook='sql.utils.execute_sql.execute_callback',
                   timeout=-1, task_name=f'sqlreview-execute-{workflow_id}')
        # 增加工单日志
        Audit.add_log(audit_id=audit_id,
                      operation_type=5,
                      operation_type_desc='执行工单',
                      operation_info='工单执行排队中',
                      operator=request.user.username,
                      operator_display=request.user.display)

    # 线下手工执行
    elif mode == "manual":
        # 将流程状态修改为执行结束
        SqlWorkflow(id=workflow_id, status="workflow_finish", finish_time=datetime.datetime.now()
                    ).save(update_fields=['status', 'finish_time'])
        # 增加工单日志
        Audit.add_log(audit_id=audit_id,
                      operation_type=6,
                      operation_type_desc='手工工单',
                      operation_info='确认手工执行结束',
                      operator=request.user.username,
                      operator_display=request.user.display)
        # 开启了Execute阶段通知参数才发送消息通知
        sys_config = SysConfig()
        is_notified = 'Execute' in sys_config.get('notify_phase_control').split(',') \
            if sys_config.get('notify_phase_control') else True
        if is_notified:
            notify_for_execute(SqlWorkflow.objects.get(id=workflow_id))
    return HttpResponseRedirect(reverse('sql:detail', args=(workflow_id,)))


def timing_task(request):
    """
    定时执行SQL
    :param request:
    :return:
    """
    # 校验多个权限
    if not (request.user.has_perm('sql.sql_execute') or request.user.has_perm('sql.sql_execute_for_resource_group')):
        raise PermissionDenied
    workflow_id = request.POST.get('workflow_id')
    run_date = request.POST.get('run_date')
    if run_date is None or workflow_id is None:
        context = {'errMsg': '时间不能为空'}
        return render(request, 'error.html', context)
    elif run_date < datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
        context = {'errMsg': '时间不能小于当前时间'}
        return render(request, 'error.html', context)
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)

    if can_timingtask(request.user, workflow_id) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    run_date = datetime.datetime.strptime(run_date, "%Y-%m-%d %H:%M")
    schedule_name = f"sqlreview-timing-{workflow_id}"

    if on_correct_time_period(workflow_id, run_date) is False:
        context = {'errMsg': '不在可执行时间范围内，如果需要修改执    行时间请重新提交工单!'}
        return render(request, 'error.html', context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 将流程状态修改为定时执行
            workflow_detail.status = 'workflow_timingtask'
            workflow_detail.save()
            # 调用添加定时任务
            add_sql_schedule(schedule_name, run_date, workflow_id)
            # 增加工单日志
            audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                   workflow_type=WorkflowDict.workflow_type[
                                                       'sqlreview']).audit_id
            Audit.add_log(audit_id=audit_id,
                          operation_type=4,
                          operation_type_desc='定时执行',
                          operation_info="定时执行时间：{}".format(run_date),
                          operator=request.user.username,
                          operator_display=request.user.display
                          )
    except Exception as msg:
        logger.error(f"定时执行工单报错，错误信息：{traceback.format_exc()}")
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    return HttpResponseRedirect(reverse('sql:detail', args=(workflow_id,)))


def cancel(request):
    """
    终止流程
    :param request:
    :return:
    """
    workflow_id = int(request.POST.get('workflow_id', 0))
    if workflow_id == 0:
        context = {'errMsg': 'workflow_id参数为空.'}
        return render(request, 'error.html', context)
    workflow_detail = SqlWorkflow.objects.get(id=workflow_id)
    audit_remark = request.POST.get('cancel_remark')
    if audit_remark is None:
        context = {'errMsg': '终止原因不能为空'}
        return render(request, 'error.html', context)

    user = request.user
    if can_cancel(request.user, workflow_id) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 调用工作流接口取消或者驳回
            audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                   workflow_type=WorkflowDict.workflow_type[
                                                       'sqlreview']).audit_id
            # 仅待审核的需要调用工作流，审核通过的不需要
            if workflow_detail.status != 'workflow_manreviewing':
                # 增加工单日志
                if user.username == workflow_detail.engineer:
                    Audit.add_log(audit_id=audit_id,
                                  operation_type=3,
                                  operation_type_desc='取消执行',
                                  operation_info="取消原因：{}".format(audit_remark),
                                  operator=request.user.username,
                                  operator_display=request.user.display
                                  )
                else:
                    Audit.add_log(audit_id=audit_id,
                                  operation_type=2,
                                  operation_type_desc='审批不通过',
                                  operation_info="审批备注：{}".format(audit_remark),
                                  operator=request.user.username,
                                  operator_display=request.user.display
                                  )
            else:
                if user.username == workflow_detail.engineer:
                    Audit.audit(audit_id,
                                WorkflowDict.workflow_status['audit_abort'],
                                user.username, audit_remark)
                # 非提交人需要校验审核权限
                elif user.has_perm('sql.sql_review'):
                    Audit.audit(audit_id,
                                WorkflowDict.workflow_status['audit_reject'],
                                user.username, audit_remark)
                else:
                    raise PermissionDenied

            # 删除定时执行task
            if workflow_detail.status == 'workflow_timingtask':
                schedule_name = f"sqlreview-timing-{workflow_id}"
                del_schedule(schedule_name)
            # 将流程状态修改为人工终止流程
            workflow_detail.status = 'workflow_abort'
            workflow_detail.save()
    except Exception as msg:
        logger.error(f"取消工单报错，错误信息：{traceback.format_exc()}")
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    else:
        # 发送取消、驳回通知，开启了Cancel阶段通知参数才发送消息通知
        sys_config = SysConfig()
        is_notified = 'Cancel' in sys_config.get('notify_phase_control').split(',') \
            if sys_config.get('notify_phase_control') else True
        if is_notified:
            audit_detail = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                   workflow_type=WorkflowDict.workflow_type['sqlreview'])
            if audit_detail.current_status in (
                    WorkflowDict.workflow_status['audit_abort'], WorkflowDict.workflow_status['audit_reject']):
                async_task(notify_for_audit, audit_id=audit_detail.audit_id, audit_remark=audit_remark, timeout=60,
                           task_name=f'sqlreview-cancel-{workflow_id}')
    return HttpResponseRedirect(reverse('sql:detail', args=(workflow_id,)))


def get_workflow_status(request):
    """
    获取某个工单的当前状态
    """
    workflow_id = request.POST['workflow_id']
    if workflow_id == '' or workflow_id is None:
        context = {"status": -1, 'msg': 'workflow_id参数为空.', "data": ""}
        return HttpResponse(json.dumps(context), content_type='application/json')

    workflow_id = int(workflow_id)
    workflow_detail = get_object_or_404(SqlWorkflow, pk=workflow_id)
    result = {"status": workflow_detail.status, "msg": "", "data": ""}
    return JsonResponse(result)


def osc_control(request):
    """用于mysql控制osc执行"""
    workflow_id = request.POST.get('workflow_id')
    sqlsha1 = request.POST.get('sqlsha1')
    command = request.POST.get('command')
    workflow = SqlWorkflow.objects.get(id=workflow_id)
    execute_engine = get_engine(workflow.instance)
    try:
        execute_result = execute_engine.osc_control(command=command, sqlsha1=sqlsha1)
        rows = execute_result.to_dict()
        error = execute_result.error
    except Exception as e:
        rows = []
        error = str(e)
    result = {"total": len(rows), "rows": rows, "msg": error}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
