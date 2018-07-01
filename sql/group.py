# -*- coding: UTF-8 -*-
import simplejson as json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from sql.models import Group, GroupRelations
from sql.utils.permission import superuser_required
from .workflow import Workflow
from .models import master_config, slave_config


# 获取用户关联组列表
def user_groups(user):
    if user.is_superuser == 1:
        group_list = [group for group in Group.objects.filter(is_deleted=0)]
    else:
        group_ids = [group['group_id'] for group in
                     GroupRelations.objects.filter(object_id=user.id, object_type=0).values('group_id')]
        group_list = [group for group in Group.objects.filter(group_id__in=group_ids, is_deleted=0)]
    return group_list


# 获取用户关联主库列表（通过组间接关联）
def user_masters(user):
    # 先获取用户管理组列表
    group_list = user_groups(user)
    group_ids = [group.group_id for group in group_list]
    # 获取组关联的主库列表
    master_ids = [group['object_id'] for group in
                  GroupRelations.objects.filter(group_id__in=group_ids, object_type=2).values('object_id')]
    # 获取主库信息
    masters = master_config.objects.filter(pk__in=master_ids)
    return masters


# 获取用户关联从库列表（通过组间接关联）
def user_slaves(user):
    # 先获取用户管理组列表
    group_list = user_groups(user)
    group_ids = [group.group_id for group in group_list]
    # 获取组关联的主库列表
    slave_ids = [group['object_id'] for group in
                 GroupRelations.objects.filter(group_id__in=group_ids, object_type=3).values('object_id')]
    # 获取主库信息
    slaves = slave_config.objects.filter(pk__in=slave_ids)
    return slaves


# 获取组关系信息
@csrf_exempt
def group_relations(request):
    '''
    type：(0, '用户'), (1, '角色'), (2, '主库'), (3, '从库')
    '''
    group_name = request.POST.get('group_name')
    object_type = request.POST.get('type')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    rows = GroupRelations.objects.filter(group_name=group_name, object_type=object_type).values(
        'object_id', 'object_name', 'group_id', 'group_name', 'object_type')
    target = [row for row in rows]
    result['data'] = target
    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取组的审批流程
@csrf_exempt
def group_auditors(request):
    group_name = request.POST.get('group_name')
    workflow_type = request.POST['workflow_type']
    result = {'status': 0, 'msg': 'ok', 'data': []}
    if group_name:
        group_id = Group.objects.get(group_name=group_name).group_id
        auditors = Workflow().auditsettings(group_id=group_id, workflow_type=workflow_type)
    else:
        result['status'] = 1
        result['msg'] = '参数错误'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 获取所有用户
    if auditors:
        auditor_list = auditors.audit_users.split(',')
        result['data'] = auditor_list
    else:
        result['data'] = []

    return HttpResponse(json.dumps(result), content_type='application/json')
