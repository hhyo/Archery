# -*- coding: UTF-8 -*-
import json

from django.core import serializers
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from .sendmail import MailSender
from .const import WorkflowDict
from .models import users, WorkflowAudit, WorkflowAuditDetail, WorkflowAuditSetting, Group, workflow, \
    QueryPrivilegesApply

DirectionsOb = WorkflowDict()
MailSenderOb = MailSender()


class Workflow(object):
    # 新增业务审核
    def addworkflowaudit(self, request, workflow_type, workflow_id, **kwargs):
        result = {'status': 0, 'msg': '', 'data': []}

        # 检查是否已存在待审核数据
        workflowInfo = WorkflowAudit.objects.filter(workflow_type=workflow_type, workflow_id=workflow_id,
                                                    current_status=DirectionsOb.workflow_status['audit_wait'])
        if len(workflowInfo) >= 1:
            result['msg'] = '该工单当前状态为待审核，请勿重复提交'
            raise Exception(result['msg'])

        if workflow_type == DirectionsOb.workflow_type['query']:
            workflow_detail = QueryPrivilegesApply.objects.get(apply_id=workflow_id)
            workflow_title = workflow_detail.title
            workflow_auditors = workflow_detail.audit_users
            group_id = workflow_detail.group_id
            group_name = workflow_detail.group_name
            create_user = workflow_detail.user_name
            workflow_remark = ''
            workflow_type_display = DirectionsOb.workflow_type['query_display']
            email_info = ''
        elif workflow_type == DirectionsOb.workflow_type['sqlreview']:
            workflow_detail = workflow.objects.get(pk=workflow_id)
            workflow_title = workflow_detail.workflow_name
            workflow_auditors = workflow_detail.review_man
            group_id = workflow_detail.group_id
            group_name = workflow_detail.group_name
            create_user = workflow_detail.engineer
            workflow_remark = ''
            workflow_type_display = DirectionsOb.workflow_type['sqlreview_display']
            email_info = workflow_detail.sql_content
        else:
            result['msg'] = '工单类型不存在'
            raise Exception(result['msg'])

        # 获取审核配置
        # try:
        #     settingInfo = WorkflowAuditSetting.objects.get(workflow_type=workflow_type)
        # except Exception:
        #     audit_users_list = None
        # else:
        #     audit_users_list = settingInfo.audit_users.split(',')
        if workflow_auditors:
            # 验证审批流是否和配置一致
            auditor_list = self.groupauditors(group_id, workflow_type).get('data')
            if workflow_auditors == ','.join(auditor_list):
                audit_users_list = workflow_auditors.split(',')
            else:
                result['msg'] = '审批流程与后台配置不同，请核实'
                raise Exception(result['msg'])
        else:
            result['msg'] = '审批流程不能为空，请先配置审批流程'
            raise Exception(result['msg'])

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
            auditInfo.current_status = DirectionsOb.workflow_status['audit_success']  # 审核通过
            auditInfo.create_user = create_user
            auditInfo.save()
            result['data'] = {'workflow_status': DirectionsOb.workflow_status['audit_success']}
            result['msg'] = '无审核配置，直接审核通过'
            return result
        else:
            user_list = [user[0] for user in users.objects.all().values_list('username')]
            for audit_user in audit_users_list:
                if audit_user not in user_list:
                    result['msg'] = '审批人不存在，请重新配置，格式为a,b,c或者a'
                    raise Exception(result['msg'])
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

            auditInfo.current_status = DirectionsOb.workflow_status['audit_wait']
            auditInfo.create_user = create_user
            auditInfo.save()
            result['data'] = {'workflow_status': DirectionsOb.workflow_status['audit_wait']}

        # 如果待审核则发送邮件通知当前审核人
        if getattr(settings, 'MAIL_ON_OFF') \
                and auditInfo.current_status == DirectionsOb.workflow_status['audit_wait']:
            # 邮件内容
            current_audit_userOb = users.objects.get(username=auditInfo.current_audit_user)
            email_reciver = current_audit_userOb.email
            # 抄送对象
            if kwargs.get('listCcAddr'):
                listCcAddr = kwargs.get('listCcAddr')
            else:
                listCcAddr = []
            email_title = "[" + workflow_type_display + "]" + "新的工单申请提醒# " + str(auditInfo.audit_id)
            email_content = "发起人：" + auditInfo.create_user + "\n审核人：" + auditInfo.audit_users \
                            + "\n工单地址：" + request.scheme + "://" + request.get_host() + "/workflowdetail/" \
                            + str(auditInfo.audit_id) + "\n工单名称：" + auditInfo.workflow_title \
                            + "\n工单详情：" + email_info
            MailSenderOb.sendEmail(email_title, email_content, [email_reciver], listCcAddr=listCcAddr)

        return result

    # 工单审核
    def auditworkflow(self, request, audit_id, audit_status, audit_user, audit_remark):
        result = {'status': 0, 'msg': 'ok', 'data': 0}
        auditInfo = WorkflowAudit.objects.get(audit_id=audit_id)

        # 获取业务信息
        if auditInfo.workflow_type == DirectionsOb.workflow_type['query']:
            workflow_type_display = DirectionsOb.workflow_type['query_display']
            email_info = ''
        elif auditInfo.workflow_type == DirectionsOb.workflow_type['sqlreview']:
            workflow_detail = workflow.objects.get(pk=auditInfo.workflow_id)
            workflow_type_display = DirectionsOb.workflow_type['sqlreview_display']
            email_info = workflow_detail.sql_content
        else:
            result['msg'] = '工单类型不存在'
            raise Exception(result['msg'])

        # 不同审核状态
        if audit_status == WorkflowDict.workflow_status['audit_success']:
            # 判断当前工单是否为待审核状态
            if auditInfo.current_status != DirectionsOb.workflow_status['audit_wait']:
                result['msg'] = '工单不是待审核状态，请返回刷新'
                raise Exception(result['msg'])

            # 判断当前审核人是否有审核权限
            if auditInfo.current_audit_user != audit_user:
                result['msg'] = '你无权操作,请联系管理员'
                raise Exception(result['msg'])

            # 判断是否还有下一级审核
            if auditInfo.next_audit_user == '-1':
                # 更新主表审核状态为审核通过
                auditresult = WorkflowAudit()
                auditresult.audit_id = audit_id
                auditresult.current_audit_user = '-1'
                auditresult.current_status = DirectionsOb.workflow_status['audit_success']
                auditresult.save(update_fields=['current_audit_user', 'current_status'])
            else:
                # 更新主表审核下级审核人和当前审核人
                auditresult = WorkflowAudit()
                auditresult.audit_id = audit_id
                auditresult.current_status = DirectionsOb.workflow_status['audit_wait']
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
            audit_detail_result.audit_id = WorkflowAudit.objects.get(audit_id=audit_id)
            audit_detail_result.audit_user = audit_user
            audit_detail_result.audit_status = DirectionsOb.workflow_status['audit_success']
            audit_detail_result.audit_time = timezone.now()
            audit_detail_result.remark = audit_remark
            audit_detail_result.save()
        elif audit_status == WorkflowDict.workflow_status['audit_reject']:
            # 判断当前工单是否为待审核状态
            if auditInfo.current_status != DirectionsOb.workflow_status['audit_wait']:
                result['msg'] = '工单不是待审核状态，请返回刷新'
                raise Exception(result['msg'])

            # 判断当前审核人是否有审核权限
            if auditInfo.current_audit_user != audit_user:
                result['msg'] = '你无权操作,请联系管理员'
                raise Exception(result['msg'])

            # 更新主表审核状态
            auditresult = WorkflowAudit()
            auditresult.audit_id = audit_id
            auditresult.current_audit_user = '-1'
            auditresult.next_audit_user = '-1'
            auditresult.current_status = DirectionsOb.workflow_status['audit_reject']
            auditresult.save(update_fields=['current_audit_user', 'next_audit_user', 'current_status'])

            # 插入审核明细数据
            audit_detail_result = WorkflowAuditDetail()
            audit_detail_result.audit_id = WorkflowAudit.objects.get(audit_id=audit_id)
            audit_detail_result.audit_user = audit_user
            audit_detail_result.audit_status = DirectionsOb.workflow_status['audit_reject']
            audit_detail_result.audit_time = timezone.now()
            audit_detail_result.remark = audit_remark
            audit_detail_result.save()
        elif audit_status == WorkflowDict.workflow_status['audit_abort']:
            # 判断当前工单是否为待审核/审核通过状态
            if auditInfo.current_status != DirectionsOb.workflow_status['audit_wait'] and \
                    auditInfo.current_status != DirectionsOb.workflow_status['audit_success']:
                result['msg'] = '工单不是待审核态/审核通过状态，请返回刷新'
                raise Exception(result['msg'])

            # 判断当前操作人是否有取消权限
            if auditInfo.create_user != audit_user:
                result['msg'] = '你无权操作,请联系管理员'
                raise Exception(result['msg'])

            # 更新主表审核状态
            auditresult = WorkflowAudit()
            auditresult.audit_id = audit_id
            auditresult.current_status = DirectionsOb.workflow_status['audit_abort']
            auditresult.save(update_fields=['current_status'])

            # 插入审核明细数据
            audit_detail_result = WorkflowAuditDetail()
            audit_detail_result.audit_id = WorkflowAudit.objects.get(audit_id=audit_id)
            audit_detail_result.audit_user = audit_user
            audit_detail_result.audit_status = DirectionsOb.workflow_status['audit_abort']
            audit_detail_result.audit_time = timezone.now()
            audit_detail_result.remark = audit_remark
            audit_detail_result.save()
        else:
            result['msg'] = '审核异常'
            raise Exception(result['msg'])

        # 按照审核状态发送邮件
        if getattr(settings, 'MAIL_ON_OFF'):
            # 重新获取审核状态
            auditInfo = WorkflowAudit.objects.get(audit_id=audit_id)
            # 给下级审核人发送邮件
            if auditInfo.current_status == DirectionsOb.workflow_status['audit_wait']:
                # 邮件内容
                email_reciver = users.objects.get(username=auditInfo.current_audit_user).email
                email_title = "[" + workflow_type_display + "]" + "新的工单申请提醒# " + str(auditInfo.audit_id)
                email_content = "发起人：" + auditInfo.create_user + "\n审核人：" + auditInfo.audit_users \
                                + "\n工单地址：" + request.scheme + "://" + request.get_host() + "/workflowdetail/" \
                                + str(auditInfo.audit_id) + "\n工单名称：" + auditInfo.workflow_title \
                                + "\n工单详情：" + email_info
                MailSenderOb.sendEmail(email_title, email_content, [email_reciver])
            # 审核通过，通知提交人，抄送DBA
            elif auditInfo.current_status == WorkflowDict.workflow_status['audit_success']:
                email_reciver = users.objects.get(username=auditInfo.create_user).email
                listCcAddr = [email['email'] for email in users.objects.filter(role='DBA').values('email')]
                email_title = "[" + workflow_type_display + "]" + "工单审核通过 # " + str(auditInfo.audit_id)
                email_content = "发起人：" + auditInfo.create_user + "\n审核人：" + auditInfo.audit_users \
                                + "\n工单地址：" + request.scheme + "://" + request.get_host() + "/workflowdetail/" \
                                + str(audit_id) + "\n工单名称： " + auditInfo.workflow_title \
                                + "\n审核备注： " + audit_remark
                MailSenderOb.sendEmail(email_title, email_content, [email_reciver], listCcAddr=listCcAddr)
            # 审核驳回，通知提交人
            elif auditInfo.current_status == WorkflowDict.workflow_status['audit_reject']:
                email_reciver = users.objects.get(username=auditInfo.create_user).email
                email_title = "[" + workflow_type_display + "]" + "工单被驳回 # " + str(auditInfo.audit_id)
                email_content = "发起人：" + auditInfo.create_user + "\n审核人：" + auditInfo.audit_users \
                                + "\n工单地址：" + request.scheme + "://" + request.get_host() + "/workflowdetail/" \
                                + str(audit_id) + "\n工单名称： " + auditInfo.workflow_title \
                                + "\n审核备注： " + audit_remark + "\n提醒：此工单被审核不通过，请重新提交或修改工单"
                MailSenderOb.sendEmail(email_title, email_content, [email_reciver])
            # 主动取消，通知所有审核人
            elif auditInfo.current_status == WorkflowDict.workflow_status['audit_abort']:
                email_reciver = [email['email'] for email in
                                 users.objects.filter(username__in=auditInfo.audit_users.split(',')).values('email')]
                email_title = "[" + workflow_type_display + "]" + "提交人主动终止SQL上线工单流程 # " + str(auditInfo.audit_id)
                email_content = "发起人：" + auditInfo.create_user + "\n审核人：" + auditInfo.audit_users \
                                + "\n工单地址：" + request.scheme + "://" + request.get_host() + "/workflowdetail/" \
                                + str(audit_id) + "\n工单名称： " + auditInfo.workflow_title \
                                + "\n提醒：提交人主动终止流程"
                MailSenderOb.sendEmail(email_title, email_content, [email_reciver])
        # 返回审核结果
        result['data'] = {'workflow_status': auditresult.current_status}
        return result

    # 获取审核列表
    def auditlist(self, loginUserOb, workflow_type, offset=0, limit=14, search=''):
        result = {'status': 0, 'msg': '', 'data': []}

        # 只返回当前待自己审核的数据
        if workflow_type == 0:
            auditlist = WorkflowAudit.objects.filter(
                workflow_title__contains=search,
                current_status=WorkflowDict.workflow_status['audit_wait'],
                current_audit_user=loginUserOb.username
            ).order_by('-audit_id')[offset:limit].values(
                'audit_id', 'workflow_type', 'workflow_title', 'create_user',
                'create_time', 'current_status', 'audit_users',
                'current_audit_user',
                'group_name')
            auditlistCount = WorkflowAudit.objects.filter(
                workflow_title__contains=search,
                current_status=WorkflowDict.workflow_status['audit_wait'],
                current_audit_user=loginUserOb.username
            ).count()
        else:
            auditlist = WorkflowAudit.objects.filter(
                workflow_title__contains=search,
                workflow_type=workflow_type,
                current_status=WorkflowDict.workflow_status['audit_wait'],
                current_audit_user=loginUserOb.username
            ).order_by('-audit_id')[offset:limit].values(
                'audit_id', 'workflow_type',
                'workflow_title', 'create_user',
                'create_time', 'current_status',
                'audit_users',
                'current_audit_user',
                'group_name')
            auditlistCount = WorkflowAudit.objects.filter(
                workflow_title__contains=search,
                workflow_type=workflow_type,
                current_status=WorkflowDict.workflow_status['audit_wait'],
                current_audit_user=loginUserOb.username
            ).count()

        result['data'] = {'auditlist': auditlist, 'auditlistCount': auditlistCount}
        return result

    # 通过审核id获取审核信息
    def auditinfo(self, audit_id):
        try:
            return WorkflowAudit.objects.get(audit_id=audit_id)
        except Exception:
            return None

    # 通过业务id获取审核信息
    def auditinfobyworkflow_id(self, workflow_id, workflow_type):
        try:
            return WorkflowAudit.objects.get(workflow_id=workflow_id, workflow_type=workflow_type)
        except Exception:
            return None

    # 通过项目组和审核类型，获取审核配置信息
    def auditsettings(self, group_id, workflow_type):
        try:
            return WorkflowAuditSetting.objects.get(workflow_type=workflow_type, group_id=group_id)
        except Exception:
            return None

    # 修改\添加配置信息
    def changesettings(self, group_id, workflow_type, audit_users):
        audit_users_list = audit_users.split(',')
        user_list = [user[0] for user in users.objects.all().values_list('username')]
        for audit_user in audit_users_list:
            if audit_user not in user_list:
                msg = '审批人不存在，请重新配置，格式为a,b,c或者a'
                raise Exception(msg)
        try:
            WorkflowAuditSetting.objects.get(workflow_type=workflow_type, group_id=group_id)
            WorkflowAuditSetting.objects.filter(workflow_type=workflow_type,
                                                group_id=group_id
                                                ).update(audit_users=audit_users)
        except Exception:
            inset = WorkflowAuditSetting()
            inset.group_id = group_id
            inset.group_name = Group.objects.get(group_id=group_id).group_name
            inset.audit_users = audit_users
            inset.workflow_type = workflow_type
            inset.save()

    # 获取项目的审核人
    def groupauditors(self, group_id, workflow_type):
        result = {'status': 0, 'msg': 'ok', 'data': []}

        # 获取审核人列表
        auditors = self.auditsettings(group_id=group_id, workflow_type=workflow_type)
        if auditors:
            auditor_list = auditors.audit_users.split(',')
            result['data'] = auditor_list
        return result
