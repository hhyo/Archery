# -*- coding: UTF-8 -*-
from django.contrib.auth.models import Group
from django.utils import timezone

from sql.utils.resource_group import user_groups, auth_group_users
from sql.utils.sql_review import is_auto_review
from common.utils.const import WorkflowDict
from sql.models import WorkflowAudit, WorkflowAuditDetail, WorkflowAuditSetting, WorkflowLog, ResourceGroup, \
    SqlWorkflow, QueryPrivilegesApply, Users
from common.config import SysConfig


class Audit(object):
    # 新增工单审核
    @staticmethod
    def add(workflow_type, workflow_id):
        result = {'status': 0, 'msg': '', 'data': []}

        # 检查是否已存在待审核数据
        workflow_info = WorkflowAudit.objects.filter(workflow_type=workflow_type, workflow_id=workflow_id,
                                                     current_status=WorkflowDict.workflow_status['audit_wait'])
        if len(workflow_info) >= 1:
            result['msg'] = '该工单当前状态为待审核，请勿重复提交'
            raise Exception(result['msg'])

        # 获取工单信息
        if workflow_type == WorkflowDict.workflow_type['query']:
            workflow_detail = QueryPrivilegesApply.objects.get(apply_id=workflow_id)
            workflow_title = workflow_detail.title
            group_id = workflow_detail.group_id
            group_name = workflow_detail.group_name
            create_user = workflow_detail.user_name
            create_user_display = workflow_detail.user_display
            audit_auth_groups = workflow_detail.audit_auth_groups
            workflow_remark = ''
        elif workflow_type == WorkflowDict.workflow_type['sqlreview']:
            workflow_detail = SqlWorkflow.objects.get(pk=workflow_id)
            workflow_title = workflow_detail.workflow_name
            group_id = workflow_detail.group_id
            group_name = workflow_detail.group_name
            create_user = workflow_detail.engineer
            create_user_display = workflow_detail.engineer_display
            audit_auth_groups = workflow_detail.audit_auth_groups
            workflow_remark = ''
        else:
            result['msg'] = '工单类型不存在'
            raise Exception(result['msg'])

        # 校验是否配置审批流程
        if audit_auth_groups == '':
            result['msg'] = '审批流程不能为空，请先配置审批流程'
            raise Exception(result['msg'])
        else:
            audit_auth_groups_list = audit_auth_groups.split(',')

        # 判断是否无需审核,并且修改审批人为空
        if SysConfig().get('auto_review', False):
            if workflow_type == WorkflowDict.workflow_type['sqlreview']:
                if is_auto_review(workflow_id):
                    sql_workflow = SqlWorkflow.objects.get(id=int(workflow_id))
                    sql_workflow.audit_auth_groups = '无需审批'
                    sql_workflow.status = 'workflow_review_pass'
                    sql_workflow.save()
                    audit_auth_groups_list = None

        # 无审核配置则无需审核，直接通过
        if audit_auth_groups_list is None:
            # 向审核主表插入审核通过的数据
            audit_detail = WorkflowAudit()
            audit_detail.group_id = group_id
            audit_detail.group_name = group_name
            audit_detail.workflow_id = workflow_id
            audit_detail.workflow_type = workflow_type
            audit_detail.workflow_title = workflow_title
            audit_detail.workflow_remark = workflow_remark
            audit_detail.audit_auth_groups = ''
            audit_detail.current_audit = '-1'
            audit_detail.next_audit = '-1'
            audit_detail.current_status = WorkflowDict.workflow_status['audit_success']  # 审核通过
            audit_detail.create_user = create_user
            audit_detail.create_user_display = create_user_display
            audit_detail.save()
            result['data'] = {'workflow_status': WorkflowDict.workflow_status['audit_success']}
            result['msg'] = '无审核配置，直接审核通过'
            # 增加工单日志
            Audit.add_log(audit_id=audit_detail.audit_id,
                          operation_type=0,
                          operation_type_desc='提交',
                          operation_info='无需审批，系统直接审核通过',
                          operator=audit_detail.create_user,
                          operator_display=audit_detail.create_user_display
                          )
        else:
            # 向审核主表插入待审核数据
            audit_detail = WorkflowAudit()
            audit_detail.group_id = group_id
            audit_detail.group_name = group_name
            audit_detail.workflow_id = workflow_id
            audit_detail.workflow_type = workflow_type
            audit_detail.workflow_title = workflow_title
            audit_detail.workflow_remark = workflow_remark
            audit_detail.audit_auth_groups = ','.join(audit_auth_groups_list)
            audit_detail.current_audit = audit_auth_groups_list[0]
            # 判断有无下级审核
            if len(audit_auth_groups_list) == 1:
                audit_detail.next_audit = '-1'
            else:
                audit_detail.next_audit = audit_auth_groups_list[1]

            audit_detail.current_status = WorkflowDict.workflow_status['audit_wait']
            audit_detail.create_user = create_user
            audit_detail.create_user_display = create_user_display
            audit_detail.save()
            result['data'] = {'workflow_status': WorkflowDict.workflow_status['audit_wait']}
            # 增加工单日志
            audit_auth_group, current_audit_auth_group = Audit.review_info(workflow_id, workflow_type)
            Audit.add_log(audit_id=audit_detail.audit_id,
                          operation_type=0,
                          operation_type_desc='提交',
                          operation_info='等待审批，审批流程：{}'.format(audit_auth_group),
                          operator=audit_detail.create_user,
                          operator_display=audit_detail.create_user_display
                          )
        # 增加审核id
        result['data']['audit_id'] = audit_detail.audit_id
        # 返回添加结果
        return result

    # 工单审核
    @staticmethod
    def audit(audit_id, audit_status, audit_user, audit_remark):
        result = {'status': 0, 'msg': 'ok', 'data': 0}
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)

        # 不同审核状态
        if audit_status == WorkflowDict.workflow_status['audit_success']:
            # 判断当前工单是否为待审核状态
            if audit_detail.current_status != WorkflowDict.workflow_status['audit_wait']:
                result['msg'] = '工单不是待审核状态，请返回刷新'
                raise Exception(result['msg'])

            # 判断是否还有下一级审核
            if audit_detail.next_audit == '-1':
                # 更新主表审核状态为审核通过
                audit_result = WorkflowAudit()
                audit_result.audit_id = audit_id
                audit_result.current_audit = '-1'
                audit_result.current_status = WorkflowDict.workflow_status['audit_success']
                audit_result.save(update_fields=['current_audit', 'current_status'])
            else:
                # 更新主表审核下级审核组和当前审核组
                audit_result = WorkflowAudit()
                audit_result.audit_id = audit_id
                audit_result.current_status = WorkflowDict.workflow_status['audit_wait']
                audit_result.current_audit = audit_detail.next_audit
                # 判断后续是否还有下下一级审核组
                audit_auth_groups_list = audit_detail.audit_auth_groups.split(',')
                for index, auth_group in enumerate(audit_auth_groups_list):
                    if auth_group == audit_detail.next_audit:
                        # 无下下级审核组
                        if index == len(audit_auth_groups_list) - 1:
                            audit_result.next_audit = '-1'
                            break
                        # 存在下下级审核组
                        else:
                            audit_result.next_audit = audit_auth_groups_list[index + 1]
                audit_result.save(update_fields=['current_audit', 'next_audit', 'current_status'])

            # 插入审核明细数据
            audit_detail_result = WorkflowAuditDetail()
            audit_detail_result.audit_id = audit_id
            audit_detail_result.audit_user = audit_user
            audit_detail_result.audit_status = WorkflowDict.workflow_status['audit_success']
            audit_detail_result.audit_time = timezone.now()
            audit_detail_result.remark = audit_remark
            audit_detail_result.save()
            # 增加工单日志
            audit_auth_group, current_audit_auth_group = Audit.review_info(audit_detail.workflow_id,
                                                                           audit_detail.workflow_type)
            Audit.add_log(audit_id=audit_id,
                          operation_type=1,
                          operation_type_desc='审批通过',
                          operation_info="审批备注：{}，下级审批：{}".format(audit_remark, current_audit_auth_group),
                          operator=audit_user,
                          operator_display=Users.objects.get(username=audit_user).display
                          )
        elif audit_status == WorkflowDict.workflow_status['audit_reject']:
            # 判断当前工单是否为待审核状态
            if audit_detail.current_status != WorkflowDict.workflow_status['audit_wait']:
                result['msg'] = '工单不是待审核状态，请返回刷新'
                raise Exception(result['msg'])

            # 更新主表审核状态
            audit_result = WorkflowAudit()
            audit_result.audit_id = audit_id
            audit_result.current_audit = '-1'
            audit_result.next_audit = '-1'
            audit_result.current_status = WorkflowDict.workflow_status['audit_reject']
            audit_result.save(update_fields=['current_audit', 'next_audit', 'current_status'])

            # 插入审核明细数据
            audit_detail_result = WorkflowAuditDetail()
            audit_detail_result.audit_id = audit_id
            audit_detail_result.audit_user = audit_user
            audit_detail_result.audit_status = WorkflowDict.workflow_status['audit_reject']
            audit_detail_result.audit_time = timezone.now()
            audit_detail_result.remark = audit_remark
            audit_detail_result.save()
            # 增加工单日志
            Audit.add_log(audit_id=audit_id,
                          operation_type=2,
                          operation_type_desc='审批不通过',
                          operation_info="审批备注：{}".format(audit_remark),
                          operator=audit_user,
                          operator_display=Users.objects.get(username=audit_user).display
                          )
        elif audit_status == WorkflowDict.workflow_status['audit_abort']:
            # 判断当前工单是否为待审核/审核通过状态
            if audit_detail.current_status != WorkflowDict.workflow_status['audit_wait'] and \
                    audit_detail.current_status != WorkflowDict.workflow_status['audit_success']:
                result['msg'] = '工单不是待审核态/审核通过状态，请返回刷新'
                raise Exception(result['msg'])

            # 更新主表审核状态
            audit_result = WorkflowAudit()
            audit_result.audit_id = audit_id
            audit_result.next_audit = '-1'
            audit_result.current_status = WorkflowDict.workflow_status['audit_abort']
            audit_result.save(update_fields=['current_status', 'next_audit'])

            # 插入审核明细数据
            audit_detail_result = WorkflowAuditDetail()
            audit_detail_result.audit_id = audit_id
            audit_detail_result.audit_user = audit_user
            audit_detail_result.audit_status = WorkflowDict.workflow_status['audit_abort']
            audit_detail_result.audit_time = timezone.now()
            audit_detail_result.remark = audit_remark
            audit_detail_result.save()

            # 增加工单日志
            Audit.add_log(audit_id=audit_id,
                          operation_type=3,
                          operation_type_desc='审批取消',
                          operation_info="取消原因：{}".format(audit_remark),
                          operator=audit_user,
                          operator_display=Users.objects.get(username=audit_user).display
                          )
        else:
            result['msg'] = '审核异常'
            raise Exception(result['msg'])

        # 返回审核结果
        result['data'] = {'workflow_status': audit_result.current_status}
        return result

    # 获取用户待办工单数量
    @staticmethod
    def todo(user):
        # 先获取用户所在资源组列表
        group_list = user_groups(user)
        group_ids = [group.group_id for group in group_list]
        # 再获取用户所在权限组列表
        if user.is_superuser:
            auth_group_ids = [group.id for group in Group.objects.all()]
        else:
            auth_group_ids = [group.id for group in Group.objects.filter(user=user)]

        return WorkflowAudit.objects.filter(
            current_status=WorkflowDict.workflow_status['audit_wait'],
            group_id__in=group_ids,
            current_audit__in=auth_group_ids).count()

    # 通过审核id获取审核信息
    @staticmethod
    def detail(audit_id):
        try:
            return WorkflowAudit.objects.get(audit_id=audit_id)
        except Exception:
            return None

    # 通过业务id获取审核信息
    @staticmethod
    def detail_by_workflow_id(workflow_id, workflow_type):
        try:
            return WorkflowAudit.objects.get(workflow_id=workflow_id, workflow_type=workflow_type)
        except Exception:
            return None

    # 通过组和审核类型，获取审核配置信息
    @staticmethod
    def settings(group_id, workflow_type):
        try:
            return WorkflowAuditSetting.objects.get(workflow_type=workflow_type, group_id=group_id).audit_auth_groups
        except Exception:
            return None

    # 修改\添加配置信息
    @staticmethod
    def change_settings(group_id, workflow_type, audit_auth_groups):
        try:
            WorkflowAuditSetting.objects.get(workflow_type=workflow_type, group_id=group_id)
            WorkflowAuditSetting.objects.filter(workflow_type=workflow_type,
                                                group_id=group_id
                                                ).update(audit_auth_groups=audit_auth_groups)
        except Exception:
            inset = WorkflowAuditSetting()
            inset.group_id = group_id
            inset.group_name = ResourceGroup.objects.get(group_id=group_id).group_name
            inset.audit_auth_groups = audit_auth_groups
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
                auth_group_id = Audit.detail_by_workflow_id(workflow_id, workflow_type).current_audit
                audit_auth_group = Group.objects.get(id=auth_group_id).name
            except Exception:
                raise Exception('当前审批auth_group_id不存在，请检查并清洗历史数据')
            if auth_group_users([audit_auth_group], group_id).filter(id=user.id).exists() or user.is_superuser == 1:
                if workflow_type == 1:
                    if user.has_perm('sql.query_review'):
                        result = True
                elif workflow_type == 2:
                    if user.has_perm('sql.sql_review'):
                        result = True
        return result

    # 获取当前工单审批流程和当前审核组
    @staticmethod
    def review_info(workflow_id, workflow_type):
        audit_info = WorkflowAudit.objects.get(workflow_id=workflow_id, workflow_type=workflow_type)
        if audit_info.audit_auth_groups == '':
            audit_auth_group = '无需审批'
        else:
            try:
                audit_auth_group = '->'.join([Group.objects.get(id=auth_group_id).name for auth_group_id in
                                              audit_info.audit_auth_groups.split(',')])
            except Exception:
                audit_auth_group = audit_info.audit_auth_groups
        if audit_info.current_audit == '-1':
            current_audit_auth_group = None
        else:
            try:
                current_audit_auth_group = Group.objects.get(id=audit_info.current_audit).name
            except Exception:
                current_audit_auth_group = audit_info.current_audit
        return audit_auth_group, current_audit_auth_group

    # 新增工单日志
    @staticmethod
    def add_log(audit_id, operation_type, operation_type_desc, operation_info, operator, operator_display):
        WorkflowLog(audit_id=audit_id,
                    operation_type=operation_type,
                    operation_type_desc=operation_type_desc,
                    operation_info=operation_info,
                    operator=operator,
                    operator_display=operator_display
                    ).save()

    # 获取工单日志
    @staticmethod
    def logs(audit_id):
        return WorkflowLog.objects.filter(audit_id=audit_id)
