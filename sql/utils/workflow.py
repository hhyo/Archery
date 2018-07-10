# -*- coding: UTF-8 -*-
import datetime

from django.utils import timezone
from sql.sqlreview import is_autoreview
from sql.notify import send_msg
from sql.const import WorkflowDict
from sql.models import users, WorkflowAudit, WorkflowAuditDetail, WorkflowAuditSetting, Group, workflow, \
    QueryPrivilegesApply
from sql.utils.config import SysConfig
from sql.utils.group import group_dbas


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

        if workflow_type == WorkflowDict.workflow_type['query']:
            workflow_detail = QueryPrivilegesApply.objects.get(apply_id=workflow_id)
            workflow_title = workflow_detail.title
            workflow_auditors = workflow_detail.audit_users
            group_id = workflow_detail.group_id
            group_name = workflow_detail.group_name
            create_user = workflow_detail.user_name
            workflow_remark = ''
            if workflow_detail.priv_type == 1:
                notify_text = '''数据库清单：{}\n授权截止时间：{}\n结果集：{}\n'''.format(
                    workflow_detail.db_list,
                    datetime.datetime.strftime(
                        workflow_detail.valid_date,
                        '%Y-%m-%d %H:%M:%S'),
                    workflow_detail.limit_num)
            elif workflow_detail.priv_type == 2:
                notify_text = '''数据库：{}\n表清单：{}\n授权截止时间：{}\n结果集：{}\n'''.format(
                    workflow_detail.db_list,
                    workflow_detail.table_list,
                    datetime.datetime.strftime(
                        workflow_detail.valid_date,
                        '%Y-%m-%d %H:%M:%S'),
                    workflow_detail.limit_num)
            else:
                notify_text = ''
        elif workflow_type == WorkflowDict.workflow_type['sqlreview']:
            workflow_detail = workflow.objects.get(pk=workflow_id)
            workflow_title = workflow_detail.workflow_name
            workflow_auditors = workflow_detail.review_man
            group_id = workflow_detail.group_id
            group_name = workflow_detail.group_name
            create_user = workflow_detail.engineer
            workflow_remark = ''
            notify_text = workflow_detail.sql_content
        else:
            result['msg'] = '工单类型不存在'
            raise Exception(result['msg'])

        # 验证审批流是否和配置一致
        try:
            audit_users = WorkflowAuditSetting.objects.get(workflow_type=workflow_type, group_id=group_id).audit_users
        except Exception:
            audit_users = None
        if workflow_auditors == audit_users:
            pass
        else:
            result['msg'] = '审批流程与后台配置不同，请核实'
            raise Exception(result['msg'])

        if workflow_auditors is None:
            result['msg'] = '审批流程不能为空，请先配置审批流程'
            raise Exception(result['msg'])
        else:
            audit_users_list = workflow_auditors.split(',')

        # 判断是否无需审核,并且修改审批人为空
        if SysConfig().sys_config.get('auto_review', False) == 'true':
            if workflow_type == WorkflowDict.workflow_type['sqlreview']:
                if is_autoreview(workflow_id):
                    Workflow = workflow.objects.get(id=int(workflow_id))
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

            auditInfo.current_status = WorkflowDict.workflow_status['audit_wait']
            auditInfo.create_user = create_user
            auditInfo.create_user_display = request.user.display
            auditInfo.save()
            result['data'] = {'workflow_status': WorkflowDict.workflow_status['audit_wait']}

        # 消息通知
        # 消息内容
        msg_data = {}
        msg_data['audit_id'] = auditInfo.audit_id
        msg_data['workflow_type'] = auditInfo.workflow_type
        msg_data['workflow_from'] = auditInfo.create_user_display
        if audit_users_list is None:
            msg_data['workflow_auditors'] = '无需审批，系统自动审核通过'
        else:
            # 获取审核人中文名
            workflow_auditors_display = [users.objects.get(username=auditor).display for auditor in
                                  auditInfo.audit_users.split(',')]
            msg_data['workflow_auditors'] = ','.join(workflow_auditors_display)
        msg_data['workflow_title'] = auditInfo.workflow_title
        msg_data['workflow_url'] = "{}://{}/workflow/{}".format(request.scheme,
                                                                      request.get_host(),
                                                                      auditInfo.audit_id)
        msg_data['workflow_content'] = notify_text
        # 如果待审核则发送邮件通知当前审核人以及抄送对象
        if auditInfo.current_status == WorkflowDict.workflow_status['audit_wait']:
            # 接收人
            current_audit_userOb = users.objects.get(username=auditInfo.current_audit_user)
            msg_data['email_reciver'] = current_audit_userOb.email
            # 抄送对象
            if kwargs.get('listCcAddr'):
                listCcAddr = kwargs.get('listCcAddr')
            else:
                listCcAddr = []
            msg_data['email_cc'] = listCcAddr
        # 如果直接审核通过则发送消息通知DBA和提交人以及抄送对象
        elif auditInfo.current_status == WorkflowDict.workflow_status['audit_success']:
            # 接收人
            msg_data['email_reciver'] = [users.objects.get(username=auditInfo.create_user).email]
            # 抄送对象
            if kwargs.get('listCcAddr'):
                listCcAddr = kwargs.get('listCcAddr')
            else:
                listCcAddr = []
            msg_data['email_cc'] = listCcAddr.append(
                [email['email'] for email in group_dbas(group_id).values('email')])

        sys_config = SysConfig().sys_config
        if sys_config.get('mail') == 'true':
            send_msg(msg_data, 1, auditInfo.current_status)
        if sys_config.get('ding') == 'true':
            msg_data['webhook_url'] = Group.objects.get(group_id=auditInfo.group_id).ding_webhook
            send_msg(msg_data, 2, auditInfo.current_status)

        return result

    # 工单审核
    def auditworkflow(self, request, audit_id, audit_status, audit_user, audit_remark):
        result = {'status': 0, 'msg': 'ok', 'data': 0}
        auditInfo = WorkflowAudit.objects.get(audit_id=audit_id)

        # 获取业务信息
        if auditInfo.workflow_type == WorkflowDict.workflow_type['query']:
            workflow_detail = QueryPrivilegesApply.objects.get(pk=auditInfo.workflow_id)
            if workflow_detail.priv_type == 1:
                notify_text = '''数据库清单：{}\n授权截止时间：{}\n结果集：{}\n'''.format(
                    workflow_detail.db_list,
                    datetime.datetime.strftime(workflow_detail.valid_date,
                                               '%Y-%m-%d %H:%M:%S'),
                    workflow_detail.limit_num)
            elif workflow_detail.priv_type == 2:
                notify_text = '''数据库：{}\n表清单：{}\n授权截止时间：{}\n结果集：{}\n'''.format(
                    workflow_detail.db_list,
                    workflow_detail.table_list,
                    datetime.datetime.strftime(workflow_detail.valid_date,
                                               '%Y-%m-%d %H:%M:%S'),
                    workflow_detail.limit_num)
            else:
                notify_text = ''
        elif auditInfo.workflow_type == WorkflowDict.workflow_type['sqlreview']:
            workflow_detail = workflow.objects.get(pk=auditInfo.workflow_id)
            notify_text = workflow_detail.sql_content
        else:
            result['msg'] = '工单类型不存在'
            raise Exception(result['msg'])

        # 不同审核状态
        if audit_status == WorkflowDict.workflow_status['audit_success']:
            # 判断当前工单是否为待审核状态
            if auditInfo.current_status != WorkflowDict.workflow_status['audit_wait']:
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

            # 判断当前审核人是否有审核权限
            if auditInfo.current_audit_user != audit_user:
                result['msg'] = '你无权操作,请联系管理员'
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

            # 判断当前操作人是否有取消权限
            if auditInfo.create_user != audit_user:
                result['msg'] = '你无权操作,请联系管理员'
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

        # 准备消息发送
        # 重新获取审核状态
        auditInfo = WorkflowAudit.objects.get(audit_id=audit_id)
        # 消息内容
        msg_data = {}
        msg_data['audit_id'] = auditInfo.audit_id
        msg_data['workflow_type'] = auditInfo.workflow_type
        msg_data['workflow_from'] = auditInfo.create_user_display
        # 获取审核人中文名
        workflow_auditors_display = [users.objects.get(username=auditor).display for auditor in
                              auditInfo.audit_users.split(',')]
        msg_data['workflow_auditors'] = ','.join(workflow_auditors_display)
        msg_data['workflow_title'] = auditInfo.workflow_title
        msg_data['workflow_url'] = "{}://{}/workflow/{}".format(request.scheme,
                                                                      request.get_host(),
                                                                      auditInfo.audit_id)
        msg_data['workflow_content'] = notify_text
        # 给下级审核人发送邮件
        if auditInfo.current_status == WorkflowDict.workflow_status['audit_wait']:
            # 邮件内容
            msg_data['email_reciver'] = [users.objects.get(username=auditInfo.current_audit_user).email]
            msg_data['email_cc'] = []
        # 审核通过，通知提交人，抄送DBA
        elif auditInfo.current_status == WorkflowDict.workflow_status['audit_success']:
            # 邮件内容
            msg_data['email_reciver'] = [users.objects.get(username=auditInfo.create_user).email]
            listCcAddr = [email['email'] for email in group_dbas(auditInfo.group_id).values('email')]
            msg_data['email_cc'] = listCcAddr
        # 审核驳回，通知提交人
        elif auditInfo.current_status == WorkflowDict.workflow_status['audit_reject']:
            # 邮件内容
            msg_data['email_reciver'] = [users.objects.get(username=auditInfo.create_user).email]
            msg_data['email_cc'] = []
            msg_data['workflow_audit_remark'] = audit_remark
        # 主动取消，通知所有审核人
        elif auditInfo.current_status == WorkflowDict.workflow_status['audit_abort']:
            # 邮件内容
            msg_data['email_reciver'] = [email['email'] for email in
                                         users.objects.filter(
                                             username__in=auditInfo.audit_users.split(',')).values(
                                             'email')]
            msg_data['email_cc'] = []
        sys_config = SysConfig().sys_config
        if sys_config.get('mail') == 'true':
            send_msg(msg_data, 1, auditInfo.current_status)
        if sys_config.get('ding') == 'true':
            msg_data['webhook_url'] = Group.objects.get(group_id=auditInfo.group_id).ding_webhook
            send_msg(msg_data, 2, auditInfo.current_status)
        # 返回审核结果
        result['data'] = {'workflow_status': auditresult.current_status}
        return result

    # 获取审核列表
    def auditlist(self, user, workflow_type, offset=0, limit=14, search=''):
        result = {'status': 0, 'msg': '', 'data': []}

        # 只返回当前待自己审核的数据
        if workflow_type == 0:
            auditlist = WorkflowAudit.objects.filter(
                workflow_title__contains=search,
                current_status=WorkflowDict.workflow_status['audit_wait'],
                current_audit_user=user.username
            ).order_by('-audit_id')[offset:limit].values(
                'audit_id', 'workflow_type', 'workflow_title', 'create_user_display',
                'create_time', 'current_status', 'audit_users',
                'current_audit_user',
                'group_name')
            auditlistCount = WorkflowAudit.objects.filter(
                workflow_title__contains=search,
                current_status=WorkflowDict.workflow_status['audit_wait'],
                current_audit_user=user.username
            ).count()
        else:
            auditlist = WorkflowAudit.objects.filter(
                workflow_title__contains=search,
                workflow_type=workflow_type,
                current_status=WorkflowDict.workflow_status['audit_wait'],
                current_audit_user=user.username
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
                current_audit_user=user.username
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

    # 通过组和审核类型，获取审核配置信息
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
