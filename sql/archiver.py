# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: archive.py
@time: 2020/01/10
"""
import logging
import os
import re
import traceback
import time

import simplejson as json
from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.db import transaction, connection, close_old_connections
from django.db.models import Q, Value as V, TextField
from django.db.models.functions import Concat
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django_q.tasks import async_task

from common.utils.const import WorkflowDict
from common.utils.extend_json_encoder import ExtendJSONEncoder
from common.utils.timer import FuncTimer
from sql.engines import get_engine
from sql.notify import notify_for_audit
from sql.plugins.pt_archiver import PtArchiver
from sql.utils.resource_group import user_instances, user_groups
from sql.models import ArchiveConfig, ArchiveLog, Instance, ResourceGroup
from sql.utils.workflow_audit import Audit

logger = logging.getLogger('default')
__author__ = 'hhyo'


@permission_required('sql.menu_archive', raise_exception=True)
def archive_list(request):
    """
    获取归档申请列表
    :param request:
    :return:
    """
    user = request.user
    filter_instance_id = request.GET.get('filter_instance_id')
    state = request.GET.get('state')
    limit = int(request.GET.get('limit', 0))
    offset = int(request.GET.get('offset', 0))
    limit = offset + limit
    search = request.GET.get('search', '')

    # 组合筛选项
    filter_dict = dict()
    if filter_instance_id:
        filter_dict['src_instance'] = filter_instance_id
    if state == 'true':
        filter_dict['state'] = True
    elif state == 'false':
        filter_dict['state'] = False

    # 管理员可以看到全部数据
    if user.is_superuser:
        pass
    # 拥有审核权限、可以查看组内所有工单
    elif user.has_perm('sql.archive_review'):
        # 先获取用户所在资源组列表
        group_list = user_groups(user)
        group_ids = [group.group_id for group in group_list]
        filter_dict['resource_group__in'] = group_ids
    # 其他人只能看到自己提交的工单
    else:
        filter_dict['user_name'] = user.username

    # 过滤组合筛选项
    archive_config = ArchiveConfig.objects.filter(**filter_dict)

    # 过滤搜索项，支持模糊搜索标题、用户
    if search:
        archive_config = archive_config.filter(Q(title__icontains=search) | Q(user_display__icontains=search))

    count = archive_config.count()
    lists = archive_config.order_by('-id')[offset:limit].values(
        'id', 'title', 'src_instance__instance_name', 'src_db_name', 'src_table_name',
        'dest_instance__instance_name', 'dest_db_name', 'dest_table_name', 'sleep',
        'mode', 'no_delete', 'status', 'state', 'user_display', 'create_time', 'resource_group__group_name'
    )

    # QuerySet 序列化
    rows = [row for row in lists]

    result = {"total": count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.archive_apply', raise_exception=True)
def archive_apply(request):
    """申请归档实例数据"""
    user = request.user
    title = request.POST.get('title')
    group_name = request.POST.get('group_name')
    src_instance_name = request.POST.get('src_instance_name')
    src_db_name = request.POST.get('src_db_name')
    src_table_name = request.POST.get('src_table_name')
    mode = request.POST.get('mode')
    dest_instance_name = request.POST.get('dest_instance_name')
    dest_db_name = request.POST.get('dest_db_name')
    dest_table_name = request.POST.get('dest_table_name')
    condition = request.POST.get('condition')
    no_delete = True if request.POST.get('no_delete') == 'true' else False
    sleep = request.POST.get('sleep') or 0
    result = {'status': 0, 'msg': 'ok', 'data': {}}

    # 参数校验
    if not all(
            [title, group_name, src_instance_name, src_db_name, src_table_name, mode, condition]) or no_delete is None:
        return JsonResponse({'status': 1, 'msg': '请填写完整！', 'data': {}})
    if mode == 'dest' and not all([dest_instance_name, dest_db_name, dest_table_name]):
        return JsonResponse({'status': 1, 'msg': '归档到实例时目标实例信息必选！', 'data': {}})

    # 获取源实例信息
    try:
        s_ins = user_instances(request.user, db_type=['mysql']).get(instance_name=src_instance_name)
    except Instance.DoesNotExist:
        return JsonResponse({'status': 1, 'msg': '你所在组未关联该实例！', 'data': {}})

    # 获取目标实例信息
    if mode == 'dest':
        try:
            d_ins = user_instances(request.user, db_type=['mysql']).get(instance_name=dest_instance_name)
        except Instance.DoesNotExist:
            return JsonResponse({'status': 1, 'msg': '你所在组未关联该实例！', 'data': {}})
    else:
        d_ins = None

    # 获取资源组和审批信息
    res_group = ResourceGroup.objects.get(group_name=group_name)
    audit_auth_groups = Audit.settings(res_group.group_id, WorkflowDict.workflow_type['archive'])
    if not audit_auth_groups:
        return JsonResponse({'status': 1, 'msg': '审批流程不能为空，请先配置审批流程', 'data': {}})

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 保存申请信息到数据库
            archive_info = ArchiveConfig.objects.create(
                title=title,
                resource_group=res_group,
                audit_auth_groups=audit_auth_groups,
                src_instance=s_ins,
                src_db_name=src_db_name,
                src_table_name=src_table_name,
                dest_instance=d_ins,
                dest_db_name=dest_db_name,
                dest_table_name=dest_table_name,
                condition=condition,
                mode=mode,
                no_delete=no_delete,
                sleep=sleep,
                status=WorkflowDict.workflow_status['audit_wait'],
                state=False,
                user_name=user.username,
                user_display=user.display,
            )
            archive_id = archive_info.id
            # 调用工作流插入审核信息
            audit_result = Audit.add(WorkflowDict.workflow_type['archive'], archive_id)
    except Exception as msg:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = str(msg)
    else:
        result = audit_result
        # 消息通知
        audit_id = Audit.detail_by_workflow_id(workflow_id=archive_id,
                                               workflow_type=WorkflowDict.workflow_type['archive']).audit_id
        async_task(notify_for_audit, audit_id=audit_id, timeout=60, task_name=f'archive-apply-{archive_id}')
    return HttpResponse(json.dumps(result), content_type='application/json')


@permission_required('sql.archive_review', raise_exception=True)
def archive_audit(request):
    """
    审核数据归档申请
    :param request:
    :return:
    """
    # 获取用户信息
    user = request.user
    archive_id = int(request.POST['archive_id'])
    audit_status = int(request.POST['audit_status'])
    audit_remark = request.POST.get('audit_remark')

    if audit_remark is None:
        audit_remark = ''

    if Audit.can_review(request.user, archive_id, 3) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            audit_id = Audit.detail_by_workflow_id(workflow_id=archive_id,
                                                   workflow_type=WorkflowDict.workflow_type['archive']).audit_id

            # 调用工作流插入审核信息，更新业务表审核状态
            audit_status = Audit.audit(audit_id, audit_status, user.username, audit_remark)['data']['workflow_status']
            ArchiveConfig(id=archive_id,
                          status=audit_status,
                          state=True if audit_status == WorkflowDict.workflow_status['audit_success'] else False
                          ).save(update_fields=['status', 'state'])
    except Exception as msg:
        logger.error(traceback.format_exc())
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    else:
        # 消息通知
        async_task(notify_for_audit, audit_id=audit_id, audit_remark=audit_remark, timeout=60,
                   task_name=f'archive-audit-{archive_id}')

    return HttpResponseRedirect(reverse('sql:archive_detail', args=(archive_id,)))


def add_archive_task(archive_ids=None):
    """
    添加数据归档异步任务，仅处理有效归档任务
    :param archive_ids: 归档任务id列表
    :return:
    """
    archive_ids = archive_ids or []
    if not isinstance(archive_ids, list):
        archive_ids = list(archive_ids)
    # 没有传archive_id代表全部归档任务统一调度
    if archive_ids:
        archive_cnf_list = ArchiveConfig.objects.filter(
            id__in=archive_ids, state=True, status=WorkflowDict.workflow_status['audit_success'])
    else:
        archive_cnf_list = ArchiveConfig.objects.filter(
            state=True, status=WorkflowDict.workflow_status['audit_success'])

    # 添加task任务
    for archive_info in archive_cnf_list:
        archive_id = archive_info.id
        async_task('sql.archiver.archive',
                   archive_id,
                   group=f'archive-{time.strftime("%Y-%m-%d %H:%M:%S ")}', timeout=-1,
                   task_name=f'archive-{archive_id}')


def archive(archive_id):
    """
    执行数据库归档
    :return:
    """
    archive_info = ArchiveConfig.objects.get(id=archive_id)
    s_ins = archive_info.src_instance
    src_db_name = archive_info.src_db_name
    src_table_name = archive_info.src_table_name
    condition = archive_info.condition
    no_delete = archive_info.no_delete
    sleep = archive_info.sleep
    mode = archive_info.mode

    # 获取归档表的字符集信息
    s_engine = get_engine(s_ins)
    s_db = s_engine.schema_object.databases[src_db_name]
    s_tb = s_db.tables[src_table_name]
    s_charset = s_tb.options['charset'].value
    if s_charset is None:
        s_charset = s_db.options['charset'].value

    pt_archiver = PtArchiver()
    # 准备参数
    source = fr"h={s_ins.host},u={s_ins.user},p='{s_ins.password}'," \
        fr"P={s_ins.port},D={src_db_name},t={src_table_name},A={s_charset}"
    args = {
        "no-version-check": True,
        "source": source,
        "where": condition,
        "progress": 5000,
        "statistics": True,
        "charset": 'utf8',
        "limit": 10000,
        "txn-size": 1000,
        "sleep": sleep
    }

    # 归档到目标实例
    if mode == 'dest':
        d_ins = archive_info.dest_instance
        dest_db_name = archive_info.dest_db_name
        dest_table_name = archive_info.dest_table_name
        # 目标表的字符集信息
        d_engine = get_engine(d_ins)
        d_db = d_engine.schema_object.databases[dest_db_name]
        d_tb = d_db.tables[dest_table_name]
        d_charset = d_tb.options['charset'].value
        if d_charset is None:
            d_charset = d_db.options['charset'].value
        # dest
        dest = fr"h={d_ins.host},u={d_ins.user},p={d_ins.password},P={d_ins.port}," \
            fr"D={dest_db_name},t={dest_table_name},A={d_charset}"
        args['dest'] = dest
        if no_delete:
            args['no-delete'] = True
    elif mode == 'file':
        output_directory = os.path.join(settings.BASE_DIR, 'downloads/archiver')
        os.makedirs(output_directory, exist_ok=True)
        args['file'] = f'{output_directory}/{s_ins.instance_name}-{src_db_name}-{src_table_name}.txt'
        if no_delete:
            args['no-delete'] = True
    elif mode == 'purge':
        args['purge'] = True

    # 参数检查
    args_check_result = pt_archiver.check_args(args)
    if args_check_result['status'] == 1:
        return JsonResponse(args_check_result)
    # 参数转换
    cmd_args = pt_archiver.generate_args2cmd(args, shell=True)
    # 执行命令，获取结果
    select_cnt = 0
    insert_cnt = 0
    delete_cnt = 0
    with FuncTimer() as t:
        p = pt_archiver.execute_cmd(cmd_args, shell=True)
        stdout = ''
        for line in iter(p.stdout.readline, ''):
            if re.match(r'^SELECT\s(\d+)$', line, re.I):
                select_cnt = re.findall(r'^SELECT\s(\d+)$', line)
            elif re.match(r'^INSERT\s(\d+)$', line, re.I):
                insert_cnt = re.findall(r'^INSERT\s(\d+)$', line)
            elif re.match(r'^DELETE\s(\d+)$', line, re.I):
                delete_cnt = re.findall(r'^DELETE\s(\d+)$', line)
            stdout += f'{line}\n'
    statistics = stdout
    # 获取异常信息
    stderr = p.stderr.read()
    if stderr:
        statistics = stdout + stderr

    # 判断归档结果
    select_cnt = int(select_cnt[0]) if select_cnt else 0
    insert_cnt = int(insert_cnt[0]) if insert_cnt else 0
    delete_cnt = int(delete_cnt[0]) if delete_cnt else 0
    error_info = ''
    success = True
    if stderr:
        error_info = f'命令执行报错:{stderr}'
        success = False
    if mode == 'dest':
        # 删除源数据，判断删除数量和写入数量
        if not no_delete and (insert_cnt != delete_cnt):
            error_info = f"删除和写入数量不一致:{insert_cnt}!={delete_cnt}"
            success = False
    elif mode == 'file':
        # 删除源数据，判断查询数量和删除数量
        if not no_delete and (select_cnt != delete_cnt):
            error_info = f"查询和删除数量不一致:{select_cnt}!={delete_cnt}"
            success = False
    elif mode == 'purge':
        # 直接删除。判断查询数量和删除数量
        if select_cnt != delete_cnt:
            error_info = f"查询和删除数量不一致:{select_cnt}!={delete_cnt}"
            success = False

    # 执行信息保存到数据库
    if connection.connection and not connection.is_usable():
        close_old_connections()
    # 更新最后归档时间
    ArchiveConfig(id=archive_id, last_archive_time=t.end).save(update_fields=['last_archive_time'])
    # 替换密码信息后保存
    ArchiveLog.objects.create(
        archive=archive_info,
        cmd=cmd_args.replace(s_ins.password, '***').replace(
            d_ins.password, '***') if mode == 'dest' else cmd_args.replace(s_ins.password, '***'),
        condition=condition,
        mode=mode,
        no_delete=no_delete,
        sleep=sleep,
        select_cnt=select_cnt,
        insert_cnt=insert_cnt,
        delete_cnt=delete_cnt,
        statistics=statistics,
        success=success,
        error_info=error_info,
        start_time=t.start,
        end_time=t.end
    )
    if not success:
        raise Exception(f'{error_info}\n{statistics}')


@permission_required('sql.menu_archive', raise_exception=True)
def archive_log(request):
    """获取归档日志列表"""
    limit = int(request.GET.get('limit', 0))
    offset = int(request.GET.get('offset', 0))
    limit = offset + limit
    archive_id = request.GET.get('archive_id')

    archive_logs = ArchiveLog.objects.filter(archive=archive_id).annotate(
        info=Concat('cmd', V('\n'), 'statistics', output_field=TextField()))
    count = archive_logs.count()
    lists = archive_logs.order_by('-id')[offset:limit].values(
        'cmd', 'info', 'condition', 'mode', 'no_delete', 'select_cnt',
        'insert_cnt', 'delete_cnt', 'success', 'error_info', 'start_time', 'end_time'
    )
    # QuerySet 序列化
    rows = [row for row in lists]
    result = {"total": count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.archive_mgt', raise_exception=True)
def archive_switch(request):
    """开启关闭归档任务"""
    archive_id = request.POST.get('archive_id')
    state = True if request.POST.get('state') == 'true' else False
    # 更新启用状态
    try:
        ArchiveConfig(id=archive_id, state=state).save(update_fields=['state'])
        return JsonResponse({'status': 0, 'msg': 'ok', 'data': {}})
    except Exception as msg:
        return JsonResponse({'status': 1, 'msg': f'{msg}', 'data': {}})


@permission_required('sql.archive_mgt', raise_exception=True)
def archive_once(request):
    """单次立即调用归档任务"""
    archive_id = request.GET.get('archive_id')
    async_task('sql.archiver.archive', archive_id, timeout=-1, task_name=f'archive-{archive_id}')
    return JsonResponse({'status': 0, 'msg': 'ok', 'data': {}})
