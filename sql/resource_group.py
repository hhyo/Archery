# -*- coding: UTF-8 -*-
import logging
import traceback

import simplejson as json
from django.contrib.auth.models import Group
from django.db.models import F
from django.http import HttpResponse

from common.utils.extend_json_encoder import ExtendJSONEncoder
from common.utils.permission import superuser_required
from sql.models import ResourceGroup, ResourceGroupRelations, Users, Instance, InstanceTag
from sql.utils.workflow_audit import Audit

logger = logging.getLogger('default')


@superuser_required
def group(request):
    """获取资源组列表"""
    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit
    search = request.POST.get('search', '')

    # 过滤搜索条件
    group_obj = ResourceGroup.objects.filter(group_name__icontains=search)
    group_count = group_obj.count()
    group_list = group_obj[offset:limit].values("group_id", "group_name", "ding_webhook")

    # QuerySet 序列化
    rows = [row for row in group_list]

    result = {"total": group_count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


def associated_objects(request):
    """
    获取资源组已关联对象信息
    type：(0, '用户'), (1, '实例')
    """
    group_id = int(request.POST.get('group_id'))
    object_type = request.POST.get('type')
    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit
    search = request.POST.get('search')

    rows_obj = ResourceGroupRelations.objects.filter(group_id=group_id)
    # 过滤搜索项
    if search:
        rows_obj = rows_obj.filter(object_name__icontains=search)
    # 过滤对象类型
    if object_type:
        rows_obj = rows_obj.filter(object_type=object_type)
    count = rows_obj.count()
    rows = rows_obj[offset:limit].values('id', 'object_id', 'object_name', 'group_id', 'group_name', 'object_type',
                                         'create_time')
    rows = [row for row in rows]
    result = {'status': 0, 'msg': 'ok', "total": count, "rows": rows}
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder), content_type='application/json')


def unassociated_objects(request):
    """
    获取资源组未关联对象信息
    type：(0, '用户'), (1, '实例')
    """
    group_id = int(request.POST.get('group_id'))
    object_type = int(request.POST.get('object_type'))

    associated_object_ids = [object_id['object_id'] for object_id in
                             ResourceGroupRelations.objects.filter(group_id=group_id,
                                                                   object_type=object_type).values('object_id')]

    if object_type == 0:
        rows = Users.objects.exclude(pk__in=associated_object_ids).annotate(object_id=F('pk'),
                                                                            object_name=F('display')
                                                                            ).values('object_id', 'object_name')
    elif object_type == 1:
        rows = Instance.objects.exclude(pk__in=associated_object_ids).annotate(object_id=F('pk'),
                                                                               object_name=F('instance_name')
                                                                               ).values('object_id', 'object_name')
    else:
        rows = []

    rows = [row for row in rows]

    result = {'status': 0, 'msg': 'ok', "rows": rows, "total": len(rows)}
    return HttpResponse(json.dumps(result), content_type='application/json')


def instances(request):
    """获取资源组关联实例列表"""
    group_name = request.POST.get('group_name')
    group_id = ResourceGroup.objects.get(group_name=group_name).group_id
    tag_code = request.POST.get('tag_code')

    # 先获取资源组关联所有实例列表
    instance_ids = [group['object_id'] for group in
                    ResourceGroupRelations.objects.filter(group_id=group_id, object_type=1).values('object_id')]

    instances = Instance.objects.filter(pk__in=instance_ids)

    # 过滤tag
    if tag_code:
        tag_id = InstanceTag.objects.get(tag_code=tag_code).id
        instances = Instance.objects.filter(instancetagrelations__instance_tag=tag_id,
                                            instancetagrelations__active=True
                                            ).values('id', 'type', 'db_type', 'instance_name')

    rows = [row for row in instances]
    result = {'status': 0, 'msg': 'ok', "data": rows}
    return HttpResponse(json.dumps(result), content_type='application/json')


@superuser_required
def addrelation(request):
    """
    添加资源组关联对象
    type：(0, '用户'), (1, '实例')
    """
    group_id = int(request.POST.get('group_id'))
    object_type = request.POST.get('object_type')
    object_list = json.loads(request.POST.get('object_info'))
    group_name = ResourceGroup.objects.get(group_id=group_id).group_name
    try:
        ResourceGroupRelations.objects.bulk_create(
            [ResourceGroupRelations(object_id=int(object.split(',')[0]),
                                    object_type=object_type,
                                    object_name=object.split(',')[1],
                                    group_id=group_id,
                                    group_name=group_name) for object in object_list])
        result = {'status': 0, 'msg': 'ok'}
    except Exception as e:
        logger.error(traceback.format_exc())
        result = {'status': 1, 'msg': str(e)}
    return HttpResponse(json.dumps(result), content_type='application/json')


def auditors(request):
    """获取资源组的审批流程"""
    group_name = request.POST.get('group_name')
    workflow_type = request.POST['workflow_type']
    result = {'status': 0, 'msg': 'ok', 'data': {'auditors': '', 'auditors_display': ''}}
    if group_name:
        group_id = ResourceGroup.objects.get(group_name=group_name).group_id
        audit_auth_groups = Audit.settings(group_id=group_id, workflow_type=workflow_type)
    else:
        result['status'] = 1
        result['msg'] = '参数错误'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 获取权限组名称
    if audit_auth_groups:
        # 校验配置
        for auth_group_id in audit_auth_groups.split(','):
            try:
                Group.objects.get(id=auth_group_id)
            except Exception:
                result['status'] = 1
                result['msg'] = '审批流程权限组不存在，请重新配置！'
                return HttpResponse(json.dumps(result), content_type='application/json')
        audit_auth_groups_name = '->'.join(
            [Group.objects.get(id=auth_group_id).name for auth_group_id in audit_auth_groups.split(',')])
        result['data']['auditors'] = audit_auth_groups
        result['data']['auditors_display'] = audit_auth_groups_name

    return HttpResponse(json.dumps(result), content_type='application/json')


@superuser_required
def changeauditors(request):
    """设置资源组的审批流程"""
    auth_groups = request.POST.get('audit_auth_groups')
    group_name = request.POST.get('group_name')
    workflow_type = request.POST.get('workflow_type')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # 调用工作流修改审核配置
    group_id = ResourceGroup.objects.get(group_name=group_name).group_id
    audit_auth_groups = [str(Group.objects.get(name=auth_group).id) for auth_group in auth_groups.split(',')]
    try:
        Audit.change_settings(group_id, workflow_type, ','.join(audit_auth_groups))
    except Exception as msg:
        logger.error(traceback.format_exc())
        result['msg'] = str(msg)
        result['status'] = 1

    # 返回结果
    return HttpResponse(json.dumps(result), content_type='application/json')
