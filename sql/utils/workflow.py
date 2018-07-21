# -*- coding: UTF-8 -*-
from django.contrib.auth.models import Group
from django.utils import timezone

from sql.utils.group import user_groups, auth_group_users
from sql.utils.sql_review import is_autoreview
from sql.notify import send_msg
from sql.const import WorkflowDict, Const
from sql.models import WorkflowAudit, WorkflowAuditDetail, WorkflowAuditSetting, SqlGroup, SqlWorkflow, \
    QueryPrivilegesApply
from sql.utils.config import SysConfig


class Workflow(object):
    # 新增业务审核
    def addworkflowaudit(self, request, workflow_type, workflow_id, **kwargs):
        result = {'status': 0, 'msg': '', 'data': []}

        # 检查是否已存在待审核数据
        workflowInfo = WorkflowAudit.objects.filter(workflow_type=workflow_type, workflow_id=workflow_id,
                                                    current_status=WorkflowDict.workflow_status['audit_wait'])
        if len(workflowInfo) >= 1:
            result['msg'] = '该工单当前状态为待审核，请勿重复提交'
            raise Exception(result['msg'])

        # 获取工单信息
        if workflow_type == WorkflowDict.workflow_type['query']:
            workflow_detail = QueryPrivilegesApply.objects.get(apply_id=workflow_id)
            workflow_title = workflow_detail.title
            group_id = workflow_detail.group_id
            group_name = workflow_detail.group_name
            create_user = workflow_detail.user_name
            audit_users = workflow_detail.audit_users
            workflow_remark = ''
        elif workflow_type == WorkflowDict.workflow_type['sqlreview']:
            workflow_detail = SqlWorkflow.objects.get(pk=workflow_id)
            workflow_title = workflow_detail.workflow_name
            group_id = workflow_detail.group_id
            group_name = workflow_detail.group_name
            create_user = workflow_detail.engineer
            audit_users = workflow_detail.review_man
            workflow_remark = ''
        else:
            result['msg'] = '工单类型不存在'
            raise Exception(result['msg'])

        # 校验是否配置审批流程
        if audit_users is None:
            result['msg'] = '审批流程不能为空，请先配置审批流程'
            raise Exception(result['msg'])
        else:
            audit_users_list = audit_users.split(',')

        # 判断是否无需审核,并且修改审批人为空
        if SysConfig().sys_config.get('auto_review', False) == 'true':
            if workflow_type == WorkflowDict.workflow_type['sqlreview']:
                if is_autoreview(workflow_id):
                    Workflow = SqlWorkflow.objects.get(id=int(workflow_id))
                    Workflow.review_man = '无需审批'
                    Workflow.status = '审核通过'
                    Workflow.save()
                    audit_users_list = None

        # 无审核配置则无需审核，直接通过
        if audit_users_list is None:
            # 向审核主表插入审核通过的数据
            auditInfo = WorkflowAudit()
            auditInfo.group_id = group_id
            auditInfo.group_name = group_name
            auditInfo.workflow_id = workflow_id
            auditInfo.workflow_type = workflow_type
            auditInfo.workflow_title = workflow_title
            auditInfo.workflow_remark = workflow_remark
            auditInfo.audit_users = ''
            auditInfo.current_audit_user = '-1'
            auditInfo.next_audit_user = '-1'
            auditInfo.current_status = WorkflowDict.workflow_status['audit_success']  # 审核通过
            auditInfo.create_user = create_user
            auditInfo.create_user_display = request.user.display
            auditInfo.save()
            result['data'] = {'workflow_status': WorkflowDict.workflow_status['audit_success']}
            result['msg'] = '无审核配置，直接审核通过'
        else:
            # 向审核主表插入待审核数据
            auditInfo = WorkflowAudit()
            auditInfo.group_id = group_id
            auditInfo.group_name = group_name
            auditInfo.workflow_id = workflow_id
            auditInfo.workflow_type = workflow_type
            auditInfo.workflow_title = workflow_title
            auditInfo.workflow_remark = workflow_remark
            auditInfo.audit_users = ','.join(audit_users_list)
            auditInfo.current_audit_user = audit_users_list[0]
            # 判断有无下级审核
            if len(audit_users_list) == 1:
                auditInfo.next_audit_user = '-1'
            else:
                auditInfo.next_audit_user = audit_users_list[1]

            auditInfo.current_status = WorkflowDict.workflow_status['audit_wait']
            auditInfo.create_user = create_user
            auditInfo.create_user_display = request.user.display
            auditInfo.save()
            result['data'] = {'workflow_status': WorkflowDict.workflow_status['audit_wait']}

        # 消息通知
        workflow_url = "{}://{}/workflow/{}".format(request.scheme, request.get_host(), auditInfo.audit_id)
        email_cc = kwargs.get('listCcAddr', [])
        send_msg(auditInfo.audit_id, 0, workflow_url=workflow_url, email_cc=email_cc)
        # 返回添加结果
        return result

    # 工单审核
    def auditworkflow(self, request, audit_id, audit_status, audit_user, audit_remark):
        result = {'status': 0, 'msg': 'ok', 'data': 0}
        auditInfo = WorkflowAudit.objects.get(audit_id=audit_id)

        # 不同审核状态
        if audit_status == WorkflowDict.workflow_status['audit_success']:
            # 判断当前工单是否为待审核状态
            if auditInfo.current_status != WorkflowDict.workflow_status['audit_wait']:
                result['msg'] = '工单不是待审核状态，请返回刷新'
                raise Exception(result['msg'])

            # 判断是否还有下一级审核
            if auditInfo.next_audit_user == '-1':
                # 更新主表审核状态为审核通过
                auditresult = WorkflowAudit()
                auditresult.audit_id = audit_id
                auditresult.current_audit_user = '-1'
                auditresult.current_status = WorkflowDict.workflow_status['audit_success']
                auditresult.save(update_fields=['current_audit_user', 'current_status'])
            else:
                # 更新主表审核下级审核人和当前审核人
                auditresult = WorkflowAudit()
                auditresult.audit_id = audit_id
                auditresult.current_status = WorkflowDict.workflow_status['audit_wait']
                auditresult.current_audit_user = auditInfo.next_audit_user
                # 判断后续是否还有下下一级审核人
                audit_users_list = auditInfo.audit_users.split(',')
                for index, audit_user in enumerate(audit_users_list):
                    if audit_user == auditInfo.next_audit_user:
                        # 无下下级审核人
                        if index == len(audit_users_list) - 1:
                            auditresult.next_audit_user = '-1'
                            break
                        # 存在下下级审核人
                        else:
                            auditresult.next_audit_user = audit_users_list[index + 1]
                auditresult.save(update_fields=['current_audit_user', 'next_audit_user', 'current_status'])

            # 插入审核明细数据
            audit_detail_result = WorkflowAuditDetail()
            audit_detail_result.audit_id = audit_id
            audit_detail_result.audit_user = audit_user
            audit_detail_result.audit_status = WorkflowDict.workflow_status['audit_success']
            audit_detail_result.audit_time = timezone.now()
            audit_detail_result.remark = audit_remark
            audit_detail_result.save()
        elif audit_status == WorkflowDict.workflow_status['audit_reject']:
            # 判断当前工单是否为待审核状态
            if auditInfo.current_status != WorkflowDict.workflow_status['audit_wait']:
                result['msg'] = '工单不是待审核状态，请返回刷新'
                raise Exception(result['msg'])

            # 更新主表审核状态
            auditresult = WorkflowAudit()
            auditresult.audit_id = audit_id
            auditresult.current_audit_user = '-1'
            auditresult.next_audit_user = '-1'
            auditresult.current_status = WorkflowDict.workflow_status['audit_reject']
            auditresult.save(update_fields=['current_audit_user', 'next_audit_user', 'current_status'])

            # 插入审核明细数据
            audit_detail_result = WorkflowAuditDetail()
            audit_detail_result.audit_id = audit_id
            audit_detail_result.audit_user = audit_user
            audit_detail_result.audit_status = WorkflowDict.workflow_status['audit_reject']
            audit_detail_result.audit_time = timezone.now()
            audit_detail_result.remark = audit_remark
            audit_detail_result.save()
        elif audit_status == WorkflowDict.workflow_status['audit_abort']:
            # 判断当前工单是否为待审核/审核通过状态
            if auditInfo.current_status != WorkflowDict.workflow_status['audit_wait'] and \
                    auditInfo.current_status != WorkflowDict.workflow_status['audit_success']:
                result['msg'] = '工单不是待审核态/审核通过状态，请返回刷新'
                raise Exception(result['msg'])

            # 更新主表审核状态
            auditresult = WorkflowAudit()
            auditresult.audit_id = audit_id
            auditresult.current_status = WorkflowDict.workflow_status['audit_abort']
            auditresult.save(update_fields=['current_status'])

            # 插入审核明细数据
            audit_detail_result = WorkflowAuditDetail()
            audit_detail_result.audit_id = audit_id
            audit_detail_result.audit_user = audit_user
            audit_detail_result.audit_status = WorkflowDict.workflow_status['audit_abort']
            audit_detail_result.audit_time = timezone.now()
            audit_detail_result.remark = audit_remark
            audit_detail_result.save()
        else:
            result['msg'] = '审核异常'
            raise Exception(result['msg'])

        # 消息通知
        workflow_url = "{}://{}/workflow/{}".format(request.scheme, request.get_host(), auditInfo.audit_id)
        send_msg(auditInfo.audit_id, 0, workflow_url=workflow_url)
        # 返回审核结果
        result['data'] = {'workflow_status': auditresult.current_status}
        return result

    # 获取审核列表
    def auditlist(self, user, workflow_type, offset=0, limit=14, search=''):
        result = {'status': 0, 'msg': '', 'data': []}
        # 先获取用户管理组列表
        group_list = user_groups(user)
        group_ids = [group.group_id for group in group_list]
        # 再获取用户所在权限组列表
        auth_group_ids = [group.id for group in Group.objects.filter(user=user)]

        # 只返回当前待自己审核的数据
        if workflow_type == 0:
            auditlist = WorkflowAudit.objects.filter(
                workflow_title__contains=search,
                current_status=WorkflowDict.workflow_status['audit_wait'],
                group_id__in=group_ids,
                current_audit_user__in=auth_group_ids
            ).order_by('-audit_id')[offset:limit].values(
                'audit_id', 'workflow_type', 'workflow_title', 'create_user_display',
                'create_time', 'current_status', 'audit_users',
                'current_audit_user',
                'group_name')
            auditlistCount = WorkflowAudit.objects.filter(
                workflow_title__contains=search,
                current_status=WorkflowDict.workflow_status['audit_wait'],
                group_id__in=group_ids,
                current_audit_user__in=auth_group_ids
            ).count()
        else:
            auditlist = WorkflowAudit.objects.filter(
                workflow_title__contains=search,
                workflow_type=workflow_type,
                current_status=WorkflowDict.workflow_status['audit_wait'],
                group_id__in=group_ids,
                current_audit_user__in=auth_group_ids
            ).order_by('-audit_id')[offset:limit].values(
                'audit_id', 'workflow_type',
                'workflow_title', 'create_user_display',
                'create_time', 'current_status',
                'audit_users',
                'current_audit_user',
                'group_name')
            auditlistCount = WorkflowAudit.objects.filter(
                workflow_title__contains=search,
                workflow_type=workflow_type,
                current_status=WorkflowDict.workflow_status['audit_wait'],
                group_id__in=group_ids,
                current_audit_user__in=auth_group_ids
            ).count()

        result['data'] = {'auditlist': auditlist, 'auditlistCount': auditlistCount}
        return result

    # 通过审核id获取审核信息
    @staticmethod
    def auditinfo(audit_id):
        try:
            return WorkflowAudit.objects.get(audit_id=audit_id)
        except Exception:
            return None

    # 通过业务id获取审核信息
    @staticmethod
    def auditinfobyworkflow_id(workflow_id, workflow_type):
        try:
            return WorkflowAudit.objects.get(workflow_id=workflow_id, workflow_type=workflow_type)
        except Exception:
            return None

    # 通过组和审核类型，获取审核配置信息
    @staticmethod
    def auditsettings(group_id, workflow_type):
        try:
            return WorkflowAuditSetting.objects.get(workflow_type=workflow_type, group_id=group_id).audit_users
        except Exception:
            return None

    # 修改\添加配置信息
    @staticmethod
    def changesettings(self, group_id, workflow_type, audit_auth_groups):
        try:
            WorkflowAuditSetting.objects.get(workflow_type=workflow_type, group_id=group_id)
            WorkflowAuditSetting.objects.filter(workflow_type=workflow_type,
                                                group_id=group_id
                                                ).update(audit_users=audit_auth_groups)
        except Exception:
            inset = WorkflowAuditSetting()
            inset.group_id = group_id
            inset.group_name = SqlGroup.objects.get(group_id=group_id).group_name
            inset.audit_users = audit_auth_groups
            inset.workflow_type = workflow_type
            inset.save()

    # 判断用户当前是否是可审核
    @staticmethod
    def can_review(user, workflow_id, workflow_type):
        audit_info = WorkflowAudit.objects.get(workflow_id=workflow_id, workflow_type=workflow_type)
        group_id = audit_info.group_id
        result = False
        # 只有待审核状态数据才可以审核
        if audit_info.current_status == WorkflowDict.workflow_status['audit_wait']:
            try:
                auth_group_id = Workflow.auditinfobyworkflow_id(workflow_id, workflow_type).current_audit_user
                audit_auth_group = Group.objects.get(id=auth_group_id).name
            except Exception:
                raise Exception('auth_group_id不存在')
            if len(auth_group_users([audit_auth_group], group_id).filter(id=user.id)) > 0:
                if workflow_type == 1:
                    if user.has_perm('sql.query_review'):
                        result = True
                elif workflow_type == 1:
                    if user.has_perm('sql.sql_review'):
                        result = True
        return result

    # 获取当前工单审批流程和当前审核人
    @staticmethod
    def review_info(workflow_id, workflow_type):
        audit_info = WorkflowAudit.objects.get(workflow_id=workflow_id, workflow_type=workflow_type)
        if audit_info.audit_users == '':
            audit_auth_group = '无需审批'
        else:
            audit_auth_group = '->'.join([Group.objects.get(id=auth_group_id).name for auth_group_id in
                                          audit_info.audit_users.split(',')])
        if audit_info.current_audit_user == '-1':
            current_audit_auth_group = None
        else:
            current_audit_auth_group = Group.objects.get(id=audit_info.current_audit_user).name
        return audit_auth_group, current_audit_auth_group
