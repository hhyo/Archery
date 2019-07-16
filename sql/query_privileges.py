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
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django_q.tasks import async_task

from common.config import SysConfig
from common.utils.const import WorkflowDict
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines.inception import InceptionEngine
from sql.models import QueryPrivilegesApply, QueryPrivileges, Instance, ResourceGroup
from sql.notify import notify_for_audit
from sql.utils.resource_group import user_groups, user_instances
from sql.utils.workflow_audit import Audit
from sql.utils.sql_utils import extract_tables

logger = logging.getLogger('default')

__author__ = 'hhyo'


# TODO 权限校验内的语法解析和判断独立到每个engine内
def query_priv_check(user, instance, db_name, sql_content, limit_num):
    """
    查询权限校验
    :param user:
    :param instance:
    :param db_name:
    :param sql_content:
    :param limit_num:
    :return:
    """
    result = {'status': 0, 'msg': 'ok', 'data': {'priv_check': True, 'limit_num': 0}}
    # 如果有can_query_all_instance, 视为管理员, 仅获取limit值信息
    # superuser 拥有全部权限, 不需做特别修改
    if user.has_perm('sql.query_all_instances'):
        priv_limit = int(SysConfig().get('admin_query_limit', 5000))
        result['data']['limit_num'] = min(priv_limit, limit_num) if limit_num else priv_limit
        return result
    # explain和show create跳过权限校验
    if re.match(r"^explain|^show\s+create", sql_content, re.I):
        return result
    # 其他尝试使用inception解析
    try:
        # 尝试使用Inception校验表权限
        table_ref = _table_ref(f"{sql_content.rstrip(';')};", instance, db_name)
        # 循环验证权限，可能存在性能问题，但一次查询涉及的库表数量有限，可忽略
        for table in table_ref:
            # 既无库权限也无表权限
            if not _db_priv(user, instance, table['db']) and not _tb_priv(user, instance, db_name, table['table']):
                result['status'] = 1
                result['msg'] = f"你无{db_name}.{table['table']}表的查询权限！请先到查询权限管理进行申请"
                return result
        # 获取查询涉及库/表权限的最小limit限制，和前端传参作对比，取最小值
        # 循环获取，可能存在性能问题，但一次查询涉及的库表数量有限，可忽略
        for table in table_ref:
            priv_limit = _priv_limit(user, instance, db_name=table['db'], tb_name=table['table'])
            limit_num = min(priv_limit, limit_num) if limit_num else priv_limit
        result['data']['limit_num'] = limit_num
    except SyntaxError as msg:
        result['status'] = 1
        result['msg'] = f"SQL语法错误，{msg}"
        return result
    except Exception as msg:
        # 表权限校验失败再次校验库权限
        # 先获取查询语句涉及的库
        if instance.db_type in ['redis', 'mssql']:
            dbs = [db_name]
        else:
            dbs = [i['schema'].strip('`') for i in extract_tables(sql_content) if i['schema'] is not None]
            dbs.append(db_name)
        # 库去重
        dbs = list(set(dbs))
        # 排序
        dbs.sort()
        # 校验库权限，无库权限直接返回
        for db_name in dbs:
            if not _db_priv(user, instance, db_name):
                result['status'] = 1
                result['msg'] = f"你无{db_name}数据库的查询权限！请先到查询权限管理进行申请"
                return result
        # 有所有库权限则获取最小limit值
        for db_name in dbs:
            priv_limit = _priv_limit(user, instance, db_name=db_name)
            limit_num = min(priv_limit, limit_num) if limit_num else priv_limit
        result['data']['limit_num'] = limit_num

        # 实例为mysql的，需要判断query_check状态
        if instance.db_type == 'mysql':
            # 开启query_check，则禁止执行
            if SysConfig().get('query_check'):
                result['status'] = 1
                result['msg'] = f"无法校验查询语句权限，请检查语法是否正确或联系管理员，错误信息：{msg}"
                return result
            # 关闭query_check，标记权限校验为跳过，可继续执行
            else:
                result['data']['priv_check'] = False

    return result


@permission_required('sql.menu_queryapplylist', raise_exception=True)
def query_priv_apply_list(request):
    """
    获取查询权限申请列表
    :param request:
    :return:
    """
    user = request.user
    limit = int(request.POST.get('limit', 0))
    offset = int(request.POST.get('offset', 0))
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
    instance_name = request.POST.get('instance_name')
    group_name = request.POST.get('group_name')
    group_id = ResourceGroup.objects.get(group_name=group_name).group_id
    priv_type = request.POST.get('priv_type')
    db_name = request.POST.get('db_name')
    db_list = request.POST.getlist('db_list[]')
    table_list = request.POST.getlist('table_list[]')
    valid_date = request.POST.get('valid_date')
    limit_num = request.POST.get('limit_num')

    # 获取用户信息
    user = request.user

    # 服务端参数校验
    result = {'status': 0, 'msg': 'ok', 'data': []}
    if int(priv_type) == 1:
        if not (title and instance_name and db_list and valid_date and limit_num):
            result['status'] = 1
            result['msg'] = '请填写完整'
            return HttpResponse(json.dumps(result), content_type='application/json')
    elif int(priv_type) == 2:
        if not (title and instance_name and db_name and valid_date and table_list and limit_num):
            result['status'] = 1
            result['msg'] = '请填写完整'
            return HttpResponse(json.dumps(result), content_type='application/json')
    try:
        user_instances(request.user, tag_codes=['can_read']).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result['status'] = 1
        result['msg'] = '你所在组未关联该实例！'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 库权限
    ins = Instance.objects.get(instance_name=instance_name)
    if int(priv_type) == 1:
        # 检查申请账号是否已拥库查询权限
        for db_name in db_list:
            if _db_priv(user, ins, db_name):
                result['status'] = 1
                result['msg'] = f'你已拥有{instance_name}实例{db_name}库权限，不能重复申请'
                return HttpResponse(json.dumps(result), content_type='application/json')

    # 表权限
    elif int(priv_type) == 2:
        # 先检查是否拥有库权限
        if _db_priv(user, ins, db_name):
            result['status'] = 1
            result['msg'] = f'你已拥有{instance_name}实例{db_name}库的全部权限，不能重复申请'
            return HttpResponse(json.dumps(result), content_type='application/json')
        # 检查申请账号是否已拥有该表的查询权限
        for tb_name in table_list:
            if _tb_priv(user, ins, db_name, tb_name):
                result['status'] = 1
                result['msg'] = f'你已拥有{instance_name}实例{db_name}.{tb_name}表的查询权限，不能重复申请'
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
                _query_apply_audit_call_back(apply_id, audit_result['data']['workflow_status'])
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


@permission_required('sql.menu_queryapplylist', raise_exception=True)
def user_query_priv(request):
    """
    用户的查询权限管理
    :param request:
    :return:
    """
    user = request.user
    user_display = request.POST.get('user_display', 'all')
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
                _query_apply_audit_call_back(audit_detail.workflow_id, audit_result['data']['workflow_status'])

    except Exception as msg:
        logger.error(traceback.format_exc())
        context = {'errMsg': msg}
        return render(request, 'error.html', context)
    else:
        # 消息通知
        async_task(notify_for_audit, audit_id=audit_id, audit_remark=audit_remark, timeout=60)

    return HttpResponseRedirect(reverse('sql:queryapplydetail', args=(apply_id,)))


def _table_ref(sql_content, instance, db_name):
    """
    解析语法树，获取语句涉及的表，用于查询权限限制
    :param sql_content:
    :param instance:
    :param db_name:
    :return:
    """
    if instance.db_type != 'mysql':
        raise RuntimeError('Inception Error: 仅支持MySQL实例')
    inception_engine = InceptionEngine()
    query_tree = inception_engine.query_print(instance=instance, db_name=db_name, sql=sql_content)
    table_ref = query_tree.get('table_ref', [])
    db_list = [table_info['db'] for table_info in table_ref]
    table_list = [table_info['table'] for table_info in table_ref]
    # 异常解析的情形
    if '' in db_list or '*' in table_list:
        raise RuntimeError('Inception Error: 存在空数据库表信息')
    if not (db_list or table_list):
        raise RuntimeError('Inception Error: 未解析到任何库表信息')
    return table_ref


def _db_priv(user, instance, db_name):
    """
    检测用户是否拥有指定库权限
    :param user: 用户对象
    :param instance: 实例对象
    :param db_name: 库名
    :return: 权限存在则返回对应权限的limit_num，否则返回False
    TODO 返回统一为 int 类型, 不存在返回0 (虽然其实在python中 0==False)
    """
    # 获取用户库权限
    user_privileges = QueryPrivileges.objects.filter(user_name=user.username, instance=instance, db_name=str(db_name),
                                                     valid_date__gte=datetime.datetime.now(), is_deleted=0,
                                                     priv_type=1)
    if user.is_superuser:
        return int(SysConfig().get('admin_query_limit', 5000))
    else:
        if user_privileges.exists():
            return user_privileges.first().limit_num
    return False


def _tb_priv(user, instance, db_name, tb_name):
    """
    检测用户是否拥有指定表权限
    :param user: 用户对象
    :param instance: 实例对象
    :param db_name: 库名
    :param tb_name: 表名
    :return: 权限存在则返回对应权限的limit_num，否则返回False
    """
    # 获取用户表权限
    user_privileges = QueryPrivileges.objects.filter(user_name=user.username, instance=instance, db_name=str(db_name),
                                                     table_name=str(tb_name), valid_date__gte=datetime.datetime.now(),
                                                     is_deleted=0, priv_type=2)
    if user.is_superuser:
        return int(SysConfig().get('admin_query_limit', 5000))
    else:
        if user_privileges.exists():
            return user_privileges.first().limit_num
    return False


def _priv_limit(user, instance, db_name, tb_name=None):
    """
    获取用户拥有的查询权限的最小limit限制，用于返回结果集限制
    :param db_name:
    :param tb_name: 可为空，为空时返回库权限
    :return:
    """
    # 获取库表权限limit值
    db_limit_num = _db_priv(user, instance, db_name)
    if tb_name:
        tb_limit_num = _tb_priv(user, instance, db_name, tb_name)
    else:
        tb_limit_num = None
    # 返回最小值
    if db_limit_num and tb_limit_num:
        return min(db_limit_num, tb_limit_num)
    elif db_limit_num:
        return db_limit_num
    elif tb_limit_num:
        return tb_limit_num
    else:
        raise RuntimeError('用户无任何有效权限！')


def _query_apply_audit_call_back(apply_id, workflow_status):
    """
    查询权限申请用于工作流审核回调
    :param apply_id: 申请id
    :param workflow_status: 审核结果
    :return:
    """
    # 更新业务表状态
    apply_info = QueryPrivilegesApply.objects.get(apply_id=apply_id)
    apply_info.status = workflow_status
    apply_info.save()
    # 审核通过插入权限信息，批量插入，减少性能消耗
    if workflow_status == WorkflowDict.workflow_status['audit_success']:
        apply_queryset = QueryPrivilegesApply.objects.get(apply_id=apply_id)
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
