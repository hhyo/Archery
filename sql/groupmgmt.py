# -*- coding: UTF-8 -*-

import simplejson as json

from django.db.models import F
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

from sql.models import Group, GroupRelations, Users, MasterConfig, SlaveConfig
from sql.utils.permission import superuser_required

import logging
from sql.utils.workflow import Workflow
from sql.utils.extend_json_encoder import ExtendJSONEncoder

logger = logging.getLogger('default')


# 获取组列表
@csrf_exempt
@superuser_required
def group(request):
    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    limit = offset + limit

    # 获取搜索参数
    search = request.POST.get('search')
    if search is None:
        search = ''

    # 全部工单里面包含搜索条件
    group_list = Group.objects.filter(group_name__contains=search)[offset:limit].values("group_id",
                                                                                        "group_name",
                                                                                        "ding_webhook")
    group_count = Group.objects.filter(group_name__contains=search).count()

    # QuerySet 序列化
    rows = [row for row in group_list]

    result = {"total": group_count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 获取组已关联对象信息
@csrf_exempt
def associated_objects(request):
    '''
    type：(0, '用户'), (1, '角色'), (2, '主库'), (3, '从库')
    '''
    group_name = request.POST.get('group_name')
    object_type = request.POST.get('type')

    if object_type:
        rows = GroupRelations.objects.filter(group_name=group_name, object_type=object_type).values(
            'id', 'object_id', 'object_name', 'group_id', 'group_name', 'object_type')
        count = GroupRelations.objects.filter(group_name=group_name, object_type=object_type).count()
    else:
        rows = GroupRelations.objects.filter(group_name=group_name).values(
            'id', 'object_id', 'object_name', 'group_id', 'group_name', 'object_type')
        count = GroupRelations.objects.filter(group_name=group_name).count()
    rows = [row for row in rows]
    result = {'status': 0, 'msg': 'ok', "total": count, "rows": rows}
    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取组未关联对象信息
@csrf_exempt
def unassociated_objects(request):
    '''
    type：(0, '用户'), (1, '角色'), (2, '主库'), (3, '从库')
    '''
    group_name = request.POST.get('group_name')
    object_type = int(request.POST.get('object_type'))

    associated_object_ids = [object_id['object_id'] for object_id in
                             GroupRelations.objects.filter(group_name=group_name,
                                                           object_type=object_type).values('object_id')]

    if object_type == 0:
        unassociated_objects = Users.objects.exclude(pk__in=associated_object_ids
                                                     ).annotate(object_id=F('pk'),
                                                                object_name=F('display')
                                                                ).values('object_id', 'object_name')
    elif object_type == 2:
        unassociated_objects = MasterConfig.objects.exclude(pk__in=associated_object_ids
                                                            ).annotate(object_id=F('pk'),
                                                                        object_name=F('cluster_name')
                                                                        ).values('object_id', 'object_name')
    elif object_type == 3:
        unassociated_objects = SlaveConfig.objects.exclude(pk__in=associated_object_ids
                                                           ).annotate(object_id=F('pk'),
                                                                       object_name=F('cluster_name')
                                                                       ).values('object_id', 'object_name')
    else:
        unassociated_objects = []

    rows = [row for row in unassociated_objects]

    result = {'status': 0, 'msg': 'ok', "rows": rows, "total": len(rows)}
    return HttpResponse(json.dumps(result), content_type='application/json')


# 添加组关联对象
@csrf_exempt
@superuser_required
def addrelation(request):
    '''
    type：(0, '用户'), (1, '角色'), (2, '主库'), (3, '从库')
    '''
    group_name = request.POST.get('group_name')
    object_type = request.POST.get('object_type')
    object_list = json.loads(request.POST.get('object_info'))
    group_id = Group.objects.get(group_name=group_name).group_id
    try:
        GroupRelations.objects.bulk_create(
            [GroupRelations(object_id=int(object.split(',')[0]),
                            object_type=object_type,
                            object_name=object.split(',')[1],
                            group_id=group_id,
                            group_name=group_name) for object in object_list])
        result = {'status': 0, 'msg': 'ok'}
    except Exception as e:
        result = {'status': 1, 'msg': str(e)}
    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取组的审批流程
@csrf_exempt
def auditors(request):
    group_name = request.POST.get('group_name')
    workflow_type = request.POST['workflow_type']
    result = {'status': 0, 'msg': 'ok', 'data': {'auditors': '', 'auditors_display': ''}}
    if group_name:
        group_id = Group.objects.get(group_name=group_name).group_id
        auditors = Workflow().auditsettings(group_id=group_id, workflow_type=workflow_type)
    else:
        result['status'] = 1
        result['msg'] = '参数错误'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 获取所有用户
    if auditors:
        auditors = auditors.audit_users
        auditors_display = ','.join([Users.objects.get(username=auditor).display for auditor in auditors.split(',')])
        result['data']['auditors'] = auditors
        result['data']['auditors_display'] = auditors_display

    return HttpResponse(json.dumps(result), content_type='application/json')


# 组审批流程配置
@csrf_exempt
@superuser_required
def changeauditors(request):
    audit_users = request.POST.get('audit_users')
    group_name = request.POST.get('group_name')
    workflow_type = request.POST.get('workflow_type')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # 调用工作流修改审核配置
    group_id = Group.objects.get(group_name=group_name).group_id
    try:
        Workflow().changesettings(group_id, workflow_type, audit_users)
    except Exception as msg:
        result['msg'] = str(msg)
        result['status'] = 1

    # 返回结果
    return HttpResponse(json.dumps(result), content_type='application/json')
