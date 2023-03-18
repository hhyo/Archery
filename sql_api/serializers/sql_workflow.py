# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: sql_workflow.py
@time: 2022/10/07
"""
__author__ = "hhyo"

import datetime
import logging
import traceback

import simplejson as json
from django.db import transaction
from django_q.tasks import async_task
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from common.config import SysConfig
from common.utils.const import WorkflowDict
from sql.engines import ReviewSet, get_engine
from sql.engines.models import ReviewResult
from sql.models import Instance, SqlWorkflow, Users
from sql.notify import notify_for_execute
from sql.utils.sql_review import on_correct_time_period
from sql.utils.tasks import del_schedule, add_sql_schedule
from sql.utils.workflow_audit import Audit
from sql_api.serializers import BaseModelSerializer

logger = logging.getLogger("default")


class ReviewResultSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    stage = serializers.CharField(read_only=True)
    errlevel = serializers.IntegerField(read_only=True)
    stagestatus = serializers.CharField(read_only=True)
    errormessage = serializers.CharField(read_only=True)
    sql = serializers.CharField(read_only=True)
    affected_rows = serializers.IntegerField(read_only=True)
    sequence = serializers.CharField(read_only=True)
    backup_dbname = serializers.CharField(read_only=True)
    execute_time = serializers.CharField(read_only=True)
    sqlsha1 = serializers.CharField(read_only=True)
    backup_time = serializers.CharField(read_only=True)
    actual_affected_rows = serializers.CharField(read_only=True)


class ExecuteCheckSerializer(serializers.Serializer):
    instance_id = serializers.IntegerField(label="实例id")
    db_name = serializers.CharField(label="数据库名")
    full_sql = serializers.CharField(label="SQL内容")

    @staticmethod
    def validate_instance_id(instance_id):
        try:
            Instance.objects.get(pk=instance_id)
        except Instance.DoesNotExist:
            raise serializers.ValidationError({"errors": f"不存在该实例：{instance_id}"})
        return instance_id

    def get_instance(self):
        return Instance.objects.get(pk=self.validated_data["instance_id"])


class ExecuteCheckResultSerializer(serializers.Serializer):
    is_execute = serializers.BooleanField(read_only=True, default=False)
    checked = serializers.CharField(read_only=True)
    warning = serializers.CharField(read_only=True)
    error = serializers.CharField(read_only=True)
    warning_count = serializers.IntegerField(read_only=True)
    error_count = serializers.IntegerField(read_only=True)
    is_critical = serializers.BooleanField(read_only=True, default=False)
    syntax_type = serializers.IntegerField(read_only=True)
    rows = serializers.ListField(child=ReviewResultSerializer(), read_only=True)
    column_list = serializers.ListField(read_only=True)
    status = serializers.CharField(read_only=True)
    affected_rows = serializers.IntegerField(read_only=True)


class SqlWorkflowSerializer(BaseModelSerializer):
    """SQL工单"""

    instance_name = serializers.CharField(source="instance.instance_name")
    sql_content = serializers.CharField(source="sqlworkflowcontent.sql_content")
    display_content = serializers.SerializerMethodField()

    @staticmethod
    def setup_eager_loading(queryset):
        queryset = queryset.select_related("instance")
        return queryset

    @extend_schema_field(field=serializers.ListField(child=ReviewResultSerializer()))
    def get_display_content(self, obj):
        """获取工单详情用于列表展示的内容，区分不同的状态进行转换"""
        if obj.status in ["workflow_finish", "workflow_exception"]:
            rows = obj.sqlworkflowcontent.execute_result
        else:
            rows = obj.sqlworkflowcontent.review_content

        review_result = ReviewSet()
        if rows:
            try:
                # 检验rows能不能正常解析
                loaded_rows = json.loads(rows)
                #  兼容旧数据'[[]]'格式，转换为新格式[{}]
                if isinstance(loaded_rows[-1], list):
                    for r in loaded_rows:
                        review_result.rows += [ReviewResult(inception_result=r)]
                    rows = review_result.json()
            except IndexError:
                review_result.rows += [
                    ReviewResult(
                        id=1,
                        sql=obj.sqlworkflowcontent.sql_content,
                        errormessage="Json decode failed." "执行结果Json解析失败, 请联系管理员",
                    )
                ]
                rows = review_result.json()
            except json.decoder.JSONDecoder:
                review_result.rows += [
                    ReviewResult(
                        id=1,
                        sql=obj.sqlworkflowcontent.sql_content,
                        # 迫于无法单元测试这里加上英文报错信息
                        errormessage="Json decode failed." "执行结果Json解析失败, 请联系管理员",
                    )
                ]
                rows = review_result.json()
        else:
            rows = obj.sqlworkflowcontent.review_content
        return json.loads(rows)

    @staticmethod
    def rollback_sql(obj):
        """获取工单回滚语句"""
        try:
            query_engine = get_engine(instance=obj.instance)
            return query_engine.get_rollback(workflow=obj)
        except Exception as msg:
            logger.error(traceback.format_exc())
            raise serializers.ValidationError({"errors": msg})

    @staticmethod
    def execute(obj, mode, username):
        """执行工单"""
        user = Users.objects.get(username=username)
        # 获取审核信息
        audit_id = Audit.detail_by_workflow_id(
            workflow_id=obj.id, workflow_type=WorkflowDict.workflow_type["sqlreview"]
        ).audit_id
        # 根据执行模式进行对应修改
        # 交由系统执行
        if mode == "auto":
            # 修改工单状态为排队中
            rows = SqlWorkflow.objects.filter(
                id=obj.id,
                status__in=[
                    "workflow_review_pass",
                    "workflow_timingtask",
                ],
            ).update(status="workflow_queuing")
            if not rows:
                raise serializers.ValidationError({"errors": "工单状态不正确"})
            # 删除定时执行任务
            schedule_name = f"sqlreview-timing-{obj.id}"
            del_schedule(schedule_name)
            # 增加工单日志
            Audit.add_log(
                audit_id=audit_id,
                operation_type=5,
                operation_type_desc="执行工单",
                operation_info="工单执行排队中",
                operator=user.username,
                operator_display=user.display,
            )
            # 加入执行队列
            async_task(
                "sql.utils.execute_sql.execute",
                obj.id,
                user,
                hook="sql.utils.execute_sql.execute_callback",
                timeout=-1,
                task_name=f"sqlreview-execute-{obj.id}",
            )
        # 线下手工执行
        elif mode == "manual":
            # 将流程状态修改为执行结束
            rows = SqlWorkflow.objects.filter(
                id=obj.id,
                status__in=[
                    "workflow_review_pass",
                    "workflow_timingtask",
                ],
            ).update(status="workflow_finish", finish_time=datetime.datetime.now())
            if not rows:
                raise serializers.ValidationError({"errors": "工单状态不正确"})
            # 增加工单日志
            Audit.add_log(
                audit_id=audit_id,
                operation_type=6,
                operation_type_desc="手工工单",
                operation_info="确认手工执行结束",
                operator=user.username,
                operator_display=user.display,
            )
            # 开启了Execute阶段通知参数才发送消息通知
            sys_config = SysConfig()
            is_notified = (
                "Execute" in sys_config.get("notify_phase_control").split(",")
                if sys_config.get("notify_phase_control")
                else True
            )
            if is_notified:
                notify_for_execute(SqlWorkflow.objects.get(id=obj.id))

    @staticmethod
    def timing_task(obj, run_date, username):
        """定时执行"""
        user = Users.objects.get(username=username)
        run_date = datetime.datetime.strptime(run_date, "%Y-%m-%d %H:%M")
        if run_date < datetime.datetime.now():
            raise serializers.ValidationError({"errors": "定时执行时间不能小于当前时间"})
        if on_correct_time_period(obj.id, run_date) is False:
            raise serializers.ValidationError(
                {"errors": "定时执行时间不在可执行时间范围内，如果需要修改执行时间请重新提交工单!"}
            )
        with transaction.atomic():
            # 将流程状态修改为定时执行
            rows = SqlWorkflow.objects.filter(
                id=obj.id,
                status__in=["workflow_review_pass", "workflow_timingtask"],
            ).update(status="workflow_timingtask")
            if not rows:
                raise serializers.ValidationError({"errors": "工单状态不正确"})
            # 调用添加定时任务
            schedule_name = f"sqlreview-timing-{obj.id}"
            add_sql_schedule(schedule_name, run_date, obj.id)
            # 增加工单日志
            audit_id = Audit.detail_by_workflow_id(
                workflow_id=obj.id,
                workflow_type=WorkflowDict.workflow_type["sqlreview"],
            ).audit_id
            Audit.add_log(
                audit_id=audit_id,
                operation_type=4,
                operation_type_desc="定时执行",
                operation_info="定时执行时间：{}".format(run_date),
                operator=user.username,
                operator_display=user.display,
            )

    class Meta:
        model = SqlWorkflow
        fields = "__all__"


class SqlWorkflowDetailSerializer(SqlWorkflowSerializer):
    """仅用做文档生成，无实际意义"""


class SqlWorkflowExecuteSerializer(serializers.Serializer):
    """执行SQL工单"""

    mode = serializers.ChoiceField(
        choices=["auto", "manual"], label="执行模式：auto-线上执行，manual-已手动执行"
    )


class SqlWorkflowTimingTaskSerializer(serializers.Serializer):
    """定时执行SQL工单"""

    run_date = serializers.DateTimeField(
        label="定时执行时间",
    )
