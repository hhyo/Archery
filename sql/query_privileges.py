# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: query_privileges.py 
@time: 2019/03/24
"""
import logging
import datetime
import re
import traceback

import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.db.models import Min, Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django_q.tasks import async_task

from common.config import SysConfig
from common.utils.const import WorkflowDict
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.models import QueryPrivilegesApply, QueryPrivileges, Instance, ResourceGroup
from sql.notify import notify_for_audit
from sql.utils.data_masking import Masking
from sql.utils.resource_group import user_groups, user_instances
from sql.utils.workflow_audit import Audit

logger = logging.getLogger('default')

__author__ = 'hhyo'

"""
权限管理模块待优化，计划剥离库、表权限校验到单独的方法，在查询和申请时方法可以复用
"""


def query_apply_audit_call_back(workflow_id, workflow_status):
    """
    查询权限申请用于工作流审核回调
    :param workflow_id:
    :param workflow_status:
    :return:
    """
    # 更新业务表状态
    apply_info = QueryPrivilegesApply.objects.get(apply_id=workflow_id)
    apply_info.status = workflow_status
    apply_info.save()
    # 审核通过插入权限信息，批量插入，减少性能消耗
    if workflow_status == WorkflowDict.workflow_status['audit_success']:
        apply_queryset = QueryPrivilegesApply.objects.get(apply_id=workflow_id)
        # 库权限

        if apply_queryset.priv_type == 1:
            insert_list = [QueryPrivileges(
                user_name=apply_queryset.user_name,
                user_display=apply_queryset.user_display,
                instance=apply_queryset.instance,
                db_name=db_name,
                table_name=apply_queryset.table_list, valid_date=apply_queryset.valid_date,
                limit_num=apply_queryset.limit_num, priv_type=apply_queryset.priv_type) for db_name in
                apply_queryset.db_list.split(',')]
        # 表权限
        elif apply_queryset.priv_type == 2:
            insert_list = [QueryPrivileges(
                user_name=apply_queryset.user_name,
                user_display=apply_queryset.user_display,
                instance=apply_queryset.instance,
                db_name=apply_queryset.db_list,
                table_name=table_name, valid_date=apply_queryset.valid_date,
                limit_num=apply_queryset.limit_num, priv_type=apply_queryset.priv_type) for table_name in
                apply_queryset.table_list.split(',')]
        QueryPrivileges.objects.bulk_create(insert_list)


def query_priv_check(user, instance_name, db_name, sql_content, limit_num):
    """
    查询权限校验
    :param user:
    :param instance_name:
    :param db_name:
    :param sql_content:
    :param limit_num:
    :return:
    """
    result = {'status': 0, 'msg': 'ok', 'data': {'priv_check': 1, 'limit_num': 0}}
    instance = Instance.objects.get(instance_name=instance_name)
    table_ref = None  # 查询语句涉及的表信息
    # 获取用户所有未过期权限
    user_privileges = QueryPrivileges.objects.filter(user_name=user.username, instance=instance,
                                                     valid_date__gte=datetime.datetime.now(), is_deleted=0)
    # 检查用户是否有该数据库/表的查询权限
    if user.is_superuser:
        user_limit_num = int(SysConfig().get('admin_query_limit', 5000))
        limit_num = int(user_limit_num) if int(limit_num) == 0 else min(int(limit_num), int(user_limit_num))
        result['data']['limit_num'] = limit_num
        return result

    # 查看表结构的语句，inception语法树解析会报错，故单独处理，explain直接跳过不做校验
    elif re.match(r"^show\s+create\s+table", sql_content.lower()):
        tb_name = re.sub(r'^show\s+create\s+table', '', sql_content, count=1, flags=0).strip()
        # 先判断是否有整库权限
        db_privileges = user_privileges.filter(db_name=db_name, priv_type=1)
        # 无整库权限再验证表权限
        if len(db_privileges) == 0:
            tb_privileges = user_privileges.filter(db_name=db_name, table_name=tb_name, priv_type=2)
            if len(tb_privileges) == 0:
                result['status'] = 1
                result['msg'] = '你无' + db_name + '.' + tb_name + '表的查询权限！请先到查询权限管理进行申请'
                return result
    # sql查询, 可以校验到表级权限
    elif instance.db_type == 'mysql':
        # 首先使用inception的语法树打印获取查询涉及的的表
        table_ref_result = Masking().query_table_ref(sql_content + ';', instance_name, db_name)

        # 正确解析拿到表数据，可以校验表权限
        if table_ref_result['status'] == 0:
            table_ref = table_ref_result['data']
            # 先判断是否有整库权限
            for table in table_ref:
                db_privileges = user_privileges.filter(db_name=table['db'], priv_type=1)
                # 无整库权限再验证表权限
                if len(db_privileges) == 0:
                    tb_privileges = user_privileges.filter(db_name=table['db'], table_name=table['table'])
                    if len(tb_privileges) == 0:
                        result['status'] = 1
                        result['msg'] = '你无' + table['db'] + '.' + table['table'] + '表的查询权限！请先到查询权限管理进行申请'
                        return result

        # 获取表数据报错，检查配置文件是否允许继续执行，并进行库权限校验
        else:
            # 校验库权限，防止inception的语法树打印错误时连库权限也未做校验
            privileges = user_privileges.filter(db_name=db_name, priv_type=1)
            if len(privileges) == 0:
                result['status'] = 1
                result['msg'] = '你无' + db_name + '数据库的查询权限！请先到查询权限管理进行申请'
                return result
            if SysConfig().get('query_check'):
                return table_ref_result
            else:
                result['data']['priv_check'] = 2

    # 获取查询涉及表的最小limit限制
    if table_ref:
        db_list = [table_info['db'] for table_info in table_ref]
        table_list = [table_info['table'] for table_info in table_ref]
        user_limit_num = user_privileges.filter(db_name__in=db_list, table_name__in=table_list, priv_type=2
                                                ).aggregate(Min('limit_num'))['limit_num__min']
        if user_limit_num is None:
            # 如果表没获取到则获取涉及库的最小limit限制
            user_limit_num = user_privileges.filter(db_name=db_name, priv_type=1
                                                    ).aggregate(Min('limit_num'))['limit_num__min']
    else:
        # 如果表没获取到则获取涉及库的最小limit限制
        user_limit_num = user_privileges.filter(db_name=db_name, priv_type=1
                                                ).aggregate(Min('limit_num'))['limit_num__min']
    if user_limit_num is None:
        result['status'] = 1
        result['msg'] = '你无' + db_name + '数据库的查询权限！请先到查询权限管理进行申请'
        return result
    limit_num = int(user_limit_num) if int(limit_num) == 0 else min(int(limit_num), int(user_limit_num))
    result['data']['limit_num'] = limit_num
    return result


@permission_required('sql.menu_queryapplylist', raise_exception=True)
def query_priv_apply_list(request):
    """
    获取查询权限申请列表
    :param request:
    :return:
    """
    user = request.user
    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit
    search = request.POST.get('search', '')

    query_privs = QueryPrivilegesApply.objects.all()
    # 过滤搜索项，支持模糊搜索标题、用户
    if search:
        query_privs = query_privs.filter(Q(title__icontains=search) | Q(user_display__icontains=search))
    # 管理员可以看到全部数据
    if user.is_superuser:
        query_privs = query_privs
    # 拥有审核权限、可以查看组内所有工单
    elif user.has_perm('sql.query_review'):
        # 先获取用户所在资源组列表
        group_list = user_groups(user)
        group_ids = [group.group_id for group in group_list]
        query_privs = query_privs.filter(group_id__in=group_ids)
    # 其他人只能看到自己提交的工单
    else:
        query_privs = query_privs.filter(user_name=user.username)

    count = query_privs.count()
    lists = query_privs.order_by('-apply_id')[offset:limit].values(
        'apply_id', 'title', 'instance__instance_name', 'db_list', 'priv_type', 'table_list', 'limit_num', 'valid_date',
        'user_display', 'status', 'create_time', 'group_name'
    )

    # QuerySet 序列化
    rows = [row for row in lists]

    result = {"total": count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.query_applypriv', raise_exception=True)
def query_priv_apply(request):
    """
    申请查询权限
    :param request:
    :return:
    """
    title = request.POST['title']
    instance_name = request.POST['instance_name']
    group_name = request.POST['group_name']
    group_id = ResourceGroup.objects.get(group_name=group_name).group_id
    priv_type = request.POST['priv_type']
    db_name = request.POST['db_name']
    valid_date = request.POST['valid_date']
    limit_num = request.POST['limit_num']

    # 获取用户信息
    user = request.user

    # 服务端参数校验
    result = {'status': 0, 'msg': 'ok', 'data': []}
    if int(priv_type) == 1:
        db_list = request.POST['db_list']
        if title is None or instance_name is None or db_list is None or valid_date is None or limit_num is None:
            result['status'] = 1
            result['msg'] = '请填写完整'
            return HttpResponse(json.dumps(result), content_type='application/json')
    elif int(priv_type) == 2:
        table_list = request.POST['table_list']
        if title is None or instance_name is None or db_name is None or valid_date is None or table_list is None or limit_num is None:
            result['status'] = 1
            result['msg'] = '请填写完整'
            return HttpResponse(json.dumps(result), content_type='application/json')
    try:
        user_instances(request.user, type='slave', db_type='all').get(instance_name=instance_name)
    except Exception:
        context = {'errMsg': '你所在组未关联该实例！'}
        return render(request, 'error.html', context)

    # 判断是否需要限制到表级别的权限
    # 库权限
    ins = Instance.objects.get(instance_name=instance_name)
    # 获取用户所有未过期权限
    user_privileges = QueryPrivileges.objects.filter(user_name=user.username, instance=ins,
                                                     valid_date__gte=datetime.datetime.now(), is_deleted=0)
    if int(priv_type) == 1:
        db_list = db_list.split(',')
        # 检查申请账号是否已拥整个库的查询权限
        own_dbs = user_privileges.filter(db_name__in=db_list, priv_type=1).values('db_name')
        own_db_list = [table_info['db_name'] for table_info in own_dbs]
        if own_db_list is None:
            pass
        else:
            for db_name in db_list:
                if db_name in own_db_list:
                    result['status'] = 1
                    result['msg'] = '你已拥有' + instance_name + '实例' + db_name + '库的全部查询权限，不能重复申请'
                    return HttpResponse(json.dumps(result), content_type='application/json')
    # 表权限
    elif int(priv_type) == 2:
        table_list = table_list.split(',')
        # 检查申请账号是否已拥有该表的查询权限
        own_tables = user_privileges.filter(db_name=db_name,
                                            table_name__in=table_list,
                                            priv_type=2).values('table_name')
        own_table_list = [table_info['table_name'] for table_info in own_tables]
        if own_table_list is None:
            pass
        else:
            for table_name in table_list:
                if table_name in own_table_list:
                    result['status'] = 1
                    result['msg'] = '你已拥有' + instance_name + '实例' + db_name + '.' + table_name + '表的查询权限，不能重复申请'
                    return HttpResponse(json.dumps(result), content_type='application/json')

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            # 保存申请信息到数据库
            applyinfo = QueryPrivilegesApply(
                title=title,
                group_id=group_id,
                group_name=group_name,
                audit_auth_groups=Audit.settings(group_id, WorkflowDict.workflow_type['query']),
                user_name=user.username,
                user_display=user.display,
                instance=ins,
                priv_type=int(priv_type),
                valid_date=valid_date,
                status=WorkflowDict.workflow_status['audit_wait'],
                limit_num=limit_num
            )
            if int(priv_type) == 1:
                applyinfo.db_list = ','.join(db_list)
                applyinfo.table_list = ''
            elif int(priv_type) == 2:
                applyinfo.db_list = db_name
                applyinfo.table_list = ','.join(table_list)
            applyinfo.save()
            apply_id = applyinfo.apply_id

            # 调用工作流插入审核信息,查询权限申请workflow_type=1
            audit_result = Audit.add(WorkflowDict.workflow_type['query'], apply_id)
            if audit_result['status'] == 0:
                # 更新业务表审核状态,判断是否插入权限信息
                query_apply_audit_call_back(apply_id, audit_result['data']['workflow_status'])
    except Exception as msg:
        logger.error(traceback.format_exc())
        result['status'] = 1
        result['msg'] = str(msg)
    else:
        result = audit_result
        # 消息通知
        audit_id = Audit.detail_by_workflow_id(workflow_id=apply_id,
                                               workflow_type=WorkflowDict.workflow_type['query']).audit_id
        async_task(notify_for_audit, audit_id=audit_id, timeout=60)
    return HttpResponse(json.dumps(result), content_type='application/json')


def user_query_priv(request):
    """
    用户的查询权限管理
    :param request:
    :return:
    """
    user = request.user
    user_display = request.POST.get('user_display')
    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit
    search = request.POST.get('search', '')

    user_query_privs = QueryPrivileges.objects.filter(is_deleted=0, valid_date__gte=datetime.datetime.now())
    # 过滤搜索项，支持模糊搜索用户、数据库、表
    if search:
        user_query_privs = user_query_privs.filter(Q(user_display__icontains=search) |
                                                   Q(db_name__icontains=search) |
                                                   Q(table_name__icontains=search))
    # 过滤用户
    if user_display != 'all':
        user_query_privs = user_query_privs.filter(user_display=user_display)
    # 管理员可以看到全部数据
    if user.is_superuser:
        user_query_privs = user_query_privs
    # 拥有管理权限、可以查看组内所有工单
    elif user.has_perm('sql.query_mgtpriv'):
        # 先获取用户所在资源组列表
        group_list = user_groups(user)
        group_ids = [group.group_id for group in group_list]
        user_query_privs = user_query_privs.filter(instance__queryprivilegesapply__group_id__in=group_ids)
    # 其他人只能看到自己提交的工单
    else:
        user_query_privs = user_query_privs.filter(user_name=user.username)

    privileges_count = user_query_privs.distinct().count()
    privileges_list = user_query_privs.distinct().order_by('-privilege_id')[offset:limit].values(
        'privilege_id', 'user_display', 'instance__instance_name', 'db_name', 'priv_type',
        'table_name', 'limit_num', 'valid_date'
    )

    # QuerySet 序列化
    rows = [row for row in privileges_list]

    result = {"total": privileges_count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


@permission_required('sql.query_mgtpriv', raise_exception=True)
def query_priv_modify(request):
    """
    变更权限信息
    :param request:
    :return:
    """
    privilege_id = request.POST.get('privilege_id')
    type = request.POST.get('type')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # type=1删除权限,type=2变更权限
    try:
        privilege = QueryPrivileges.objects.get(privilege_id=int(privilege_id))
    except QueryPrivileges.DoesNotExist:
        result['msg'] = '待操作权限不存在'
        result['status'] = 1
        return HttpResponse(json.dumps(result), content_type='application/json')

    if int(type) == 1:
        # 删除权限
        privilege.is_deleted = 1
        privilege.save(update_fields=['is_deleted'])
        return HttpResponse(json.dumps(result), content_type='application/json')
    elif int(type) == 2:
        # 变更权限
        valid_date = request.POST.get('valid_date')
        limit_num = request.POST.get('limit_num')
        privilege.valid_date = valid_date
        privilege.limit_num = limit_num
        privilege.save(update_fields=['valid_date', 'limit_num'])
        return HttpResponse(json.dumps(result), content_type='application/json')


@permission_required('sql.query_review', raise_exception=True)
def query_priv_audit(request):
    """
    查询权限审核
    :param request:
    :return:
    """
    # 获取用户信息
    user = request.user
    apply_id = int(request.POST['apply_id'])
    audit_status = int(request.POST['audit_status'])
    audit_remark = request.POST.get('audit_remark')

    if audit_remark is None:
        audit_remark = ''

    if Audit.can_review(request.user, apply_id, 1) is False:
        context = {'errMsg': '你无权操作当前工单！'}
        return render(request, 'error.html', context)

    # 使用事务保持数据一致性
    try:
        with transaction.atomic():
            audit_id = Audit.detail_by_workflow_id(workflow_id=apply_id,
                                                   workflow_type=WorkflowDict.workflow_type['query']).audit_id

            # 调用工作流接口审核
            audit_result = Audit.audit(audit_id, audit_status, user.username, audit_remark)

            # 按照审核结果更新业务表审核状态
            audit_detail = Audit.detail(audit_id)
            if audit_detail.workflow_type == WorkflowDict.workflow_type['query']:
                # 更新业务表审核状态,插入权限信息
                query_apply_audit_call_back(audit_detail.workflow_id, audit_result['data']['workflow_status'])

    except Exception as msg:
        logger.error(traceback.format_exc())
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    else:
        # 消息通知
        async_task(notify_for_audit, audit_id=audit_id, audit_remark=audit_remark, timeout=60)

    return HttpResponseRedirect(reverse('sql:queryapplydetail', args=(apply_id,)))
