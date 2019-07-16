import simplejson as json
from django.contrib.auth.models import Group
from django.http import HttpResponse

from common.utils.const import WorkflowDict
from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.models import WorkflowAudit, WorkflowLog
from sql.utils.resource_group import user_groups


# 获取审核列表
def lists(request):
    # 获取用户信息
    user = request.user

    limit = int(request.POST.get('limit'))
    offset = int(request.POST.get('offset'))
    workflow_type = int(request.POST.get('workflow_type'))
    limit = offset + limit
    search = request.POST.get('search', '')

    # 先获取用户所在资源组列表
    group_list = user_groups(user)
    group_ids = [group.group_id for group in group_list]
    # 再获取用户所在权限组列表
    if user.is_superuser:
        auth_group_ids = [group.id for group in Group.objects.all()]
    else:
        auth_group_ids = [group.id for group in Group.objects.filter(user=user)]

    # 只返回所在资源组当前待自己审核的数据
    workflow_audit = WorkflowAudit.objects.filter(
        workflow_title__icontains=search,
        current_status=WorkflowDict.workflow_status['audit_wait'],
        group_id__in=group_ids,
        current_audit__in=auth_group_ids
    )
    # 过滤工单类型
    if workflow_type != 0:
        workflow_audit.filter(workflow_type=workflow_type)

    audit_list_count = workflow_audit.count()
    audit_list = workflow_audit.order_by('-audit_id')[offset:limit].values(
        'audit_id', 'workflow_type',
        'workflow_title', 'create_user_display',
        'create_time', 'current_status',
        'audit_auth_groups',
        'current_audit',
        'group_name')

    # QuerySet 序列化
    rows = [row for row in audit_list]

    result = {"total": audit_list_count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')


# 获取工单日志
def log(request):
    workflow_id = request.POST.get('workflow_id')
    workflow_type = request.POST.get('workflow_type')
    try:
        audit_id = WorkflowAudit.objects.get(workflow_id=workflow_id, workflow_type=workflow_type).audit_id
        workflow_logs = WorkflowLog.objects.filter(audit_id=audit_id).order_by('-id').values(
            'operation_type_desc',
            'operation_info',
            'operator_display',
            'operation_time')
        count = WorkflowLog.objects.filter(audit_id=audit_id).count()
    except Exception:
        workflow_logs = []
        count = 0

    # QuerySet 序列化
    rows = [row for row in workflow_logs]
    result = {"total": count, "rows": rows}
    # 返回查询结果
    return HttpResponse(json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
                        content_type='application/json')
