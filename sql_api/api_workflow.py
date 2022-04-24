from rest_framework import views, generics, status, serializers
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .serializers import WorkflowContentSerializer, ExecuteCheckSerializer, \
    ExecuteCheckResultSerializer, WorkflowAuditSerializer, WorkflowAuditListSerializer, \
    WorkflowLogSerializer, WorkflowLogListSerializer, AuditWorkflowSerializer, ExecuteWorkflowSerializer
from .pagination import CustomizedPagination
from .filters import WorkflowFilter, WorkflowAuditFilter
from sql.models import SqlWorkflow, SqlWorkflowContent, Instance, WorkflowAudit, Users, WorkflowLog, ArchiveConfig
from sql.utils.sql_review import can_cancel, can_execute, on_correct_time_period
from sql.utils.resource_group import user_groups
from sql.utils.workflow_audit import Audit
from sql.utils.tasks import del_schedule
from sql.notify import notify_for_audit, notify_for_execute
from sql.query_privileges import _query_apply_audit_call_back
from sql.engines import get_engine
from common.utils.const import WorkflowDict
from common.config import SysConfig
from django.contrib.auth.models import Group
from django.db import transaction
from django_q.tasks import async_task
import traceback
import datetime
import logging

logger = logging.getLogger('default')


class ExecuteCheck(views.APIView):
    @extend_schema(summary="SQL检查",
                   request=ExecuteCheckSerializer,
                   responses={200: ExecuteCheckResultSerializer},
                   description="对提供的SQL进行语法检查")
    def post(self, request):
        # 参数验证
        serializer = ExecuteCheckSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        instance = Instance.objects.get(pk=request.data['instance_id'])
        check_engine = get_engine(instance=instance)
        check_result = check_engine.execute_check(db_name=request.data['db_name'],
                                                  sql=request.data['full_sql'].strip())
        review_result_list = []
        for r in check_result.rows:
            review_result_list += [r.__dict__]
        check_result.rows = review_result_list
        serializer_obj = ExecuteCheckResultSerializer(check_result)
        return Response(serializer_obj.data)


class WorkflowList(generics.ListAPIView):
    """
    列出所有的workflow或者提交一条新的workflow
    """
    filterset_class = WorkflowFilter
    pagination_class = CustomizedPagination
    serializer_class = WorkflowContentSerializer
    queryset = SqlWorkflowContent.objects.all().select_related('workflow').order_by('-id')

    @extend_schema(summary="SQL上线工单清单",
                   request=WorkflowContentSerializer,
                   responses={200: WorkflowContentSerializer},
                   description="列出所有SQL上线工单（过滤，分页）")
    def get(self, request):
        workflows = self.filter_queryset(self.queryset)
        page_wf = self.paginate_queryset(queryset=workflows)
        serializer_obj = self.get_serializer(page_wf, many=True)
        data = {
            'data': serializer_obj.data
        }
        return self.get_paginated_response(data)

    @extend_schema(summary="提交SQL上线工单",
                   request=WorkflowContentSerializer,
                   responses={201: WorkflowContentSerializer},
                   description="提交一条SQL上线工单")
    def post(self, request):
        serializer = WorkflowContentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WorkflowAuditList(generics.ListAPIView):
    """
    列出指定用户当前待自己审核的工单
    """
    filterset_class = WorkflowAuditFilter
    pagination_class = CustomizedPagination
    serializer_class = WorkflowAuditListSerializer
    queryset = WorkflowAudit.objects.filter(
        current_status=WorkflowDict.workflow_status['audit_wait']).order_by('-audit_id')

    @extend_schema(exclude=True)
    def get(self, request):
        return Response({"detail": "方法 “GET” 不被允许。"})

    @extend_schema(summary="待审核清单",
                   request=WorkflowAuditSerializer,
                   responses={200: WorkflowAuditListSerializer},
                   description="列出指定用户待审核清单（过滤，分页）")
    def post(self, request):
        # 参数验证
        serializer = WorkflowAuditSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # 先获取用户所在资源组列表
        user = Users.objects.get(username=request.data['engineer'])
        group_list = user_groups(user)
        group_ids = [group.group_id for group in group_list]

        # 再获取用户所在权限组列表
        if user.is_superuser:
            auth_group_ids = [group.id for group in Group.objects.all()]
        else:
            auth_group_ids = [group.id for group in Group.objects.filter(user=user)]

        self.queryset = self.queryset.filter(current_status=WorkflowDict.workflow_status['audit_wait'],
                                             group_id__in=group_ids,
                                             current_audit__in=auth_group_ids)
        audit = self.filter_queryset(self.queryset)
        page_audit = self.paginate_queryset(queryset=audit)
        serializer_obj = self.get_serializer(page_audit, many=True)
        data = {
            'data': serializer_obj.data
        }
        return self.get_paginated_response(data)


class AuditWorkflow(views.APIView):
    """
    审核workflow，包括查询权限申请、SQL上线申请、数据归档申请
    """

    @extend_schema(summary="审核工单",
                   request=AuditWorkflowSerializer,
                   description="审核一条工单（通过或终止）")
    def post(self, request):
        # 参数验证
        serializer = AuditWorkflowSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        audit_type = request.data['audit_type']
        workflow_type = request.data['workflow_type']
        workflow_id = request.data['workflow_id']
        audit_remark = request.data['audit_remark']
        engineer = request.data['engineer']
        user = Users.objects.get(username=engineer)

        # 审核查询权限申请
        if workflow_type == 1:
            audit_status = 1 if audit_type == 'pass' else 2

            if audit_remark is None:
                audit_remark = ''

            if Audit.can_review(user, workflow_id, workflow_type) is False:
                raise serializers.ValidationError({"errors": "你无权操作当前工单！"})

            # 使用事务保持数据一致性
            try:
                with transaction.atomic():
                    audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                           workflow_type=WorkflowDict.workflow_type['query']).audit_id

                    # 调用工作流接口审核
                    audit_result = Audit.audit(audit_id, audit_status, user.username, audit_remark)

                    # 按照审核结果更新业务表审核状态
                    audit_detail = Audit.detail(audit_id)
                    if audit_detail.workflow_type == WorkflowDict.workflow_type['query']:
                        # 更新业务表审核状态,插入权限信息
                        _query_apply_audit_call_back(audit_detail.workflow_id, audit_result['data']['workflow_status'])

            except Exception as msg:
                logger.error(traceback.format_exc())
                raise serializers.ValidationError({'errors': msg})
            else:
                # 消息通知
                async_task(notify_for_audit, audit_id=audit_id, audit_remark=audit_remark, timeout=60,
                           task_name=f'query-priv-audit-{workflow_id}')
                return Response({'msg': 'passed'}) if audit_type == 'pass' else Response({'msg': 'canceled'})
        # 审核SQL上线申请
        elif workflow_type == 2:
            # SQL上线申请通过
            if audit_type == 'pass':
                # 权限验证
                if Audit.can_review(user, workflow_id, workflow_type) is False:
                    raise serializers.ValidationError({"errors": "你无权操作当前工单！"})

                # 使用事务保持数据一致性
                try:
                    with transaction.atomic():
                        # 调用工作流接口审核
                        audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                               workflow_type=WorkflowDict.workflow_type[
                                                                   'sqlreview']).audit_id
                        audit_result = Audit.audit(audit_id, WorkflowDict.workflow_status['audit_success'],
                                                   user.username, audit_remark)

                        # 按照审核结果更新业务表审核状态
                        if audit_result['data']['workflow_status'] == WorkflowDict.workflow_status['audit_success']:
                            # 将流程状态修改为审核通过
                            SqlWorkflow(id=workflow_id, status='workflow_review_pass').save(update_fields=['status'])
                except Exception as msg:
                    logger.error(traceback.format_exc())
                    raise serializers.ValidationError({'errors': msg})
                else:
                    # 开启了Pass阶段通知参数才发送消息通知
                    sys_config = SysConfig()
                    is_notified = 'Pass' in sys_config.get('notify_phase_control').split(',') \
                        if sys_config.get('notify_phase_control') else True
                    if is_notified:
                        async_task(notify_for_audit, audit_id=audit_id, audit_remark=audit_remark, timeout=60,
                                   task_name=f'sqlreview-pass-{workflow_id}')
                    return Response({'msg': 'passed'})
            # SQL上线申请驳回/取消
            elif audit_type == 'cancel':
                workflow_detail = SqlWorkflow.objects.get(id=workflow_id)

                if audit_remark is None:
                    raise serializers.ValidationError({"errors": "终止原因不能为空"})

                if can_cancel(user, workflow_id) is False:
                    raise serializers.ValidationError({"errors": "你无权操作当前工单！"})

                # 使用事务保持数据一致性
                try:
                    with transaction.atomic():
                        # 调用工作流接口取消或者驳回
                        audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                               workflow_type=WorkflowDict.workflow_type[
                                                                   'sqlreview']).audit_id
                        # 仅待审核的需要调用工作流，审核通过的不需要
                        if workflow_detail.status != 'workflow_manreviewing':
                            # 增加工单日志
                            if user.username == workflow_detail.engineer:
                                Audit.add_log(audit_id=audit_id,
                                              operation_type=3,
                                              operation_type_desc='取消执行',
                                              operation_info="取消原因：{}".format(audit_remark),
                                              operator=user.username,
                                              operator_display=user.display
                                              )
                            else:
                                Audit.add_log(audit_id=audit_id,
                                              operation_type=2,
                                              operation_type_desc='审批不通过',
                                              operation_info="审批备注：{}".format(audit_remark),
                                              operator=user.username,
                                              operator_display=user.display
                                              )
                        else:
                            if user.username == workflow_detail.engineer:
                                Audit.audit(audit_id,
                                            WorkflowDict.workflow_status['audit_abort'],
                                            user.username, audit_remark)
                            # 非提交人需要校验审核权限
                            elif user.has_perm('sql.sql_review'):
                                Audit.audit(audit_id,
                                            WorkflowDict.workflow_status['audit_reject'],
                                            user.username, audit_remark)
                            else:
                                raise serializers.ValidationError({"errors": "Permission Denied"})

                        # 删除定时执行task
                        if workflow_detail.status == 'workflow_timingtask':
                            schedule_name = f"sqlreview-timing-{workflow_id}"
                            del_schedule(schedule_name)
                        # 将流程状态修改为人工终止流程
                        workflow_detail.status = 'workflow_abort'
                        workflow_detail.save()
                except Exception as msg:
                    logger.error(f"取消工单报错，错误信息：{traceback.format_exc()}")
                    raise serializers.ValidationError({'errors': msg})
                else:
                    # 发送取消、驳回通知，开启了Cancel阶段通知参数才发送消息通知
                    sys_config = SysConfig()
                    is_notified = 'Cancel' in sys_config.get('notify_phase_control').split(',') \
                        if sys_config.get('notify_phase_control') else True
                    if is_notified:
                        audit_detail = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                                   workflow_type=WorkflowDict.workflow_type[
                                                                       'sqlreview'])
                        if audit_detail.current_status in (
                                WorkflowDict.workflow_status['audit_abort'],
                                WorkflowDict.workflow_status['audit_reject']):
                            async_task(notify_for_audit, audit_id=audit_detail.audit_id, audit_remark=audit_remark,
                                       timeout=60,
                                       task_name=f'sqlreview-cancel-{workflow_id}')
                    return Response({'msg': 'canceled'})
        # 审核数据归档申请
        elif workflow_type == 3:
            audit_status = 1 if audit_type == 'pass' else 2

            if audit_remark is None:
                audit_remark = ''

            if Audit.can_review(user, workflow_id, workflow_type) is False:
                raise serializers.ValidationError({"errors": "你无权操作当前工单！"})

            # 使用事务保持数据一致性
            try:
                with transaction.atomic():
                    audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                           workflow_type=WorkflowDict.workflow_type['archive']).audit_id

                    # 调用工作流插入审核信息，更新业务表审核状态
                    audit_status = Audit.audit(audit_id, audit_status, user.username, audit_remark)['data'][
                        'workflow_status']
                    ArchiveConfig(id=workflow_id,
                                  status=audit_status,
                                  state=True if audit_status == WorkflowDict.workflow_status['audit_success'] else False
                                  ).save(update_fields=['status', 'state'])
            except Exception as msg:
                logger.error(traceback.format_exc())
                raise serializers.ValidationError({'errors': msg})
            else:
                # 消息通知
                async_task(notify_for_audit, audit_id=audit_id, audit_remark=audit_remark, timeout=60,
                           task_name=f'archive-audit-{workflow_id}')
                return Response({'msg': 'passed'}) if audit_type == 'pass' else Response({'msg': 'canceled'})


class ExecuteWorkflow(views.APIView):
    """
    执行workflow，包括SQL上线工单、数据归档工单
    """

    @extend_schema(summary="执行工单",
                   request=ExecuteWorkflowSerializer,
                   description="执行一条工单")
    def post(self, request):
        # 参数验证
        serializer = ExecuteWorkflowSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        workflow_type = request.data['workflow_type']
        workflow_id = request.data['workflow_id']

        # 执行SQL上线工单
        if workflow_type == 2:
            mode = request.data['mode']
            engineer = request.data['engineer']
            user = Users.objects.get(username=engineer)

            # 校验多个权限
            if not (user.has_perm('sql.sql_execute') or user.has_perm('sql.sql_execute_for_resource_group')):
                raise serializers.ValidationError({"errors": "你无权执行当前工单！"})

            if can_execute(user, workflow_id) is False:
                raise serializers.ValidationError({"errors": "你无权执行当前工单！"})

            if on_correct_time_period(workflow_id) is False:
                raise serializers.ValidationError({"errors": "不在可执行时间范围内，如果需要修改执行时间请重新提交工单!"})

            # 获取审核信息
            audit_id = Audit.detail_by_workflow_id(workflow_id=workflow_id,
                                                   workflow_type=WorkflowDict.workflow_type['sqlreview']).audit_id

            # 交由系统执行
            if mode == "auto":
                # 修改工单状态为排队中
                SqlWorkflow(id=workflow_id, status="workflow_queuing").save(update_fields=['status'])
                # 删除定时执行任务
                schedule_name = f"sqlreview-timing-{workflow_id}"
                del_schedule(schedule_name)
                # 加入执行队列
                async_task('sql.utils.execute_sql.execute', workflow_id, user,
                           hook='sql.utils.execute_sql.execute_callback',
                           timeout=-1, task_name=f'sqlreview-execute-{workflow_id}')
                # 增加工单日志
                Audit.add_log(audit_id=audit_id,
                              operation_type=5,
                              operation_type_desc='执行工单',
                              operation_info='工单执行排队中',
                              operator=user.username,
                              operator_display=user.display)

            # 线下手工执行
            elif mode == "manual":
                # 将流程状态修改为执行结束
                SqlWorkflow(id=workflow_id, status="workflow_finish", finish_time=datetime.datetime.now()
                            ).save(update_fields=['status', 'finish_time'])
                # 增加工单日志
                Audit.add_log(audit_id=audit_id,
                              operation_type=6,
                              operation_type_desc='手工工单',
                              operation_info='确认手工执行结束',
                              operator=user.username,
                              operator_display=user.display)
                # 开启了Execute阶段通知参数才发送消息通知
                sys_config = SysConfig()
                is_notified = 'Execute' in sys_config.get('notify_phase_control').split(',') \
                    if sys_config.get('notify_phase_control') else True
                if is_notified:
                    notify_for_execute(SqlWorkflow.objects.get(id=workflow_id))
        # 执行数据归档工单
        elif workflow_type == 3:
            async_task('sql.archiver.archive', workflow_id, timeout=-1, task_name=f'archive-{workflow_id}')

        return Response({'msg': '开始执行，执行结果请到工单详情页查看'})


class WorkflowLogList(generics.ListAPIView):
    """
    获取某个工单的日志
    """
    pagination_class = CustomizedPagination
    serializer_class = WorkflowLogListSerializer
    queryset = WorkflowLog.objects.all()

    @extend_schema(exclude=True)
    def get(self, request):
        return Response({"detail": "方法 “GET” 不被允许。"})

    @extend_schema(summary="工单日志",
                   request=WorkflowLogSerializer,
                   responses={200: WorkflowLogListSerializer},
                   description="获取某个工单的日志（分页）")
    def post(self, request):
        # 参数验证
        serializer = WorkflowLogSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        audit_id = WorkflowAudit.objects.get(workflow_id=request.data['workflow_id'],
                                             workflow_type=request.data['workflow_type']).audit_id
        workflow_logs = self.queryset.filter(audit_id=audit_id).order_by('-id')
        page_log = self.paginate_queryset(queryset=workflow_logs)
        serializer_obj = self.get_serializer(page_log, many=True)
        data = {
            'data': serializer_obj.data
        }
        return self.get_paginated_response(data)
