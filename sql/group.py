# -*- coding: UTF-8 -*-
import simplejson as json
from django.core import serializers
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from sql.models import Group, Group_Relations
from sql.utils.permission import superuser_required
from sql.views_ajax import workflowOb


# 获取用户组关系信息
@csrf_exempt
def group_relations(request):
    group_name = request.POST.get('group_name')
    type = request.POST.get('type')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    rows = Group_Relations.objects.filter(group_name=group_name, type=type).values(
        'relation_id', 'relation_key', 'group_id', 'group_name', 'type')
    target = [row for row in rows]
    result['data'] = target
    return HttpResponse(json.dumps(result), content_type='application/json')


# 获取用户组的审批流程
@csrf_exempt
def groupauditors(request):
    group_name = request.POST.get('group_name')
    workflow_type = request.POST['workflow_type']
    result = {'status': 0, 'msg': 'ok', 'data': []}
    if group_name:
        group_id = Group.objects.get(group_name=group_name).group_id
        auditors = workflowOb.auditsettings(group_id=group_id, workflow_type=workflow_type)
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
