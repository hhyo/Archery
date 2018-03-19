# -*- coding: UTF-8 -*-

from django.conf import settings
from django.utils import timezone
from .sendmail import MailSender
from .const import WorkflowDict
from .models import users, WorkflowAudit, WorkflowAuditDetail, WorkflowAuditSetting

DirectionsOb = WorkflowDict()
MailSenderOb = MailSender()


class Workflow(object):
    # 新增业务审核
    def addworkflowaudit(self, request, workflow_type, workflow_id, workflow_title, create_user, workflow_remark=''):
        result = {'status': 0, 'msg': '', 'data': []}

        # 检查是否已存在待审核数据
        workflowInfo = WorkflowAudit.objects.filter(workflow_type=workflow_type, workflow_id=workflow_id,
                                                    current_status=DirectionsOb.workflow_status['audit_wait'])
        if len(workflowInfo) >= 1:
            result['status'] = 1
            result['msg'] = '该工单当前状态为待审核，请勿重复提交'
            return result

        # 获取审核配置
        try:
            settingInfo = WorkflowAuditSetting.objects.get(workflow_type=workflow_type)
        except Exception:
            audit_users_list = None
        else:
            audit_users_list = settingInfo.audit_users.split(',')

        # 无审核配置则无需审核，直接通过
        if audit_users_list is None:
            # 向审核主表插入审核通过的数据
            auditInfo = WorkflowAudit()
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
        elif audit_users_list[-1] == '':
            result['status'] = 1
            result['msg'] = '审核角色配置错误，请重新配置，格式为a,b,c或者a'
            return result
        else:
            # 向审核主表插入待审核数据
            auditInfo = WorkflowAudit()
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
        if workflow_type == DirectionsOb.workflow_type['query']:
            workflow_type_display = DirectionsOb.workflow_type['query_display']
        else:
            workflow_type_display = ''
        if hasattr(settings, 'MAIL_ON_OFF') is True and getattr(settings, 'MAIL_ON_OFF') == 'on' \
                and auditInfo.current_status == DirectionsOb.workflow_status['audit_wait']:
            # 邮件内容
            current_audit_userOb = users.objects.get(username=auditInfo.current_audit_user)
            email_reciver = current_audit_userOb.email
            email_title = "[" + workflow_type_display + "]" + "新的工单申请提醒# " + str(auditInfo.audit_id)
            email_content = "发起人：" + auditInfo.create_user + "\n审核人：" + auditInfo.audit_users \
                            + "\n工单地址：" + request.scheme + "://" + request.get_host() + "/workflowdetail/" \
                            + str(auditInfo.audit_id) + "\n工单名称： " + auditInfo.workflow_title
            MailSenderOb.sendEmail(email_title, email_content, [email_reciver])

        return result

    # 工单审核
    def auditworkflow(self, audit_id, audit_status, audit_user, audit_remark):
        result = {'status': 0, 'msg': 'ok', 'data': 0}

        # 判断当前工单是否为待审核状态
        auditInfo = WorkflowAudit.objects.get(audit_id=audit_id)
        if auditInfo.current_status != DirectionsOb.workflow_status['audit_wait']:
            result['status'] = 1
            result['msg'] = '工单不是待审核状态，请返回刷新'
            return result

        # 判断当前审核人是否有审核权限
        if auditInfo.current_audit_user != audit_user:
            result['status'] = 1
            result['msg'] = '你无权操作,请联系管理员'
            return result

        # 不同审核状态
        if audit_status == 1:
            # 判断是否还有下一级审核
            if auditInfo.next_audit_user == '-1':
                # 更新主表审核状态为审核通过
                auditresult = WorkflowAudit()
                auditresult.audit_id = audit_id
                auditresult.current_audit_user = '-1'
                auditresult.current_status = DirectionsOb.workflow_status['audit_success']
                auditresult.save(update_fields=['current_audit_user', 'current_status', 'current_status'])
            else:
                # 更新主表审核下级审核人和当前审核人
                auditresult = WorkflowAudit()
                auditresult.audit_id = audit_id
                auditresult.current_audit_user = auditInfo.next_audit_user
                # 判断后续是否还有下一级审核人
                audit_users_list = auditInfo.audit_users.split(',')
                for index, audit_user in enumerate(audit_users_list):
                    if audit_user == auditInfo.next_audit_user:
                        if index == len(audit_users_list) - 1:
                            auditresult.next_audit_user = '-1'
                            break
                        else:
                            auditresult.next_audit_user = audit_users_list[index + 1]
                auditresult.save(update_fields=['current_audit_user', 'next_audit_user'])

            # 插入审核明细数据
            audit_detail_result = WorkflowAuditDetail()
            audit_detail_result.audit_id = audit_id
            audit_detail_result.audit_user = audit_user
            audit_detail_result.audit_status = DirectionsOb.workflow_status['audit_success']
            audit_detail_result.audit_time = timezone.now()
            audit_detail_result.remark = audit_remark
            audit_detail_result.save()

            # 返回审核结果
            result['data'] = {'workflow_status': auditresult.current_status}

        elif audit_status == 0:
            # 更新主表审核状态
            auditresult = WorkflowAudit()
            auditresult.audit_id = audit_id
            auditresult.current_audit_user = '-1'
            auditresult.next_audit_user = '-1'
            auditresult.current_status = DirectionsOb.workflow_status['audit_reject']
            auditresult.save(update_fields=['current_audit_user', 'next_audit_user', 'current_status'])

            # 插入审核明细数据
            audit_detail_result = WorkflowAuditDetail()
            audit_detail_result.audit_id = audit_id
            audit_detail_result.audit_user = audit_user
            audit_detail_result.audit_status = DirectionsOb.workflow_status['audit_reject']
            audit_detail_result.audit_time = timezone.now()
            audit_detail_result.remark = audit_remark
            audit_detail_result.save()

            # 返回审核结果
            result['data'] = {'workflow_status': auditresult.current_status}
        else:
            result['status'] = 1
            result['msg'] = '审核异常'
        return result

    # 获取审核列表
    def auditlist(self, loginUserOb, workflow_type, offset=0, limit=14, search=''):
        result = {'status': 0, 'msg': '', 'data': []}

        # 管理员获取所有数据，其他人获取拥有审核权限的数据
        if workflow_type == 0:
            if loginUserOb.is_superuser:
                auditlist = WorkflowAudit.objects.all().filter(workflow_title__contains=search).order_by('-audit_id')[
                            offset:limit]
                auditlistCount = WorkflowAudit.objects.all().filter(workflow_title__contains=search).order_by(
                    '-audit_id').count()
            else:
                auditlist = WorkflowAudit.objects.filter(audit_users__contains=loginUserOb.username,
                                                         workflow_title__contains=search).order_by('-audit_id')[
                            offset:limit]
                auditlistCount = WorkflowAudit.objects.filter(audit_users__contains=loginUserOb.username,
                                                              workflow_title__contains=search).count()
        else:
            if loginUserOb.is_superuser:
                auditlist = WorkflowAudit.objects.all().filter(workflow_type=workflow_type,
                                                               workflow_title__contains=search).order_by('-audit_id')[
                            offset:limit]
                auditlistCount = WorkflowAudit.objects.all().filter(workflow_type=workflow_type,
                                                                    workflow_title__contains=search).order_by(
                    '-audit_id').count()
            else:
                auditlist = WorkflowAudit.objects.filter(workflow_type=workflow_type,
                                                         audit_users__contains=loginUserOb.username,
                                                         workflow_title__contains=search).order_by('-audit_id')[
                            offset:limit]
                auditlistCount = WorkflowAudit.objects.filter(workflow_type=workflow_type,
                                                              audit_users__contains=loginUserOb.username,
                                                              workflow_title__contains=search).count()

        result['data'] = {'auditlist': auditlist, 'auditlistCount': auditlistCount}
        return result

    # 获取审核信息
    def auditinfo(self, audit_id):
        return WorkflowAudit.objects.get(audit_id=audit_id)
