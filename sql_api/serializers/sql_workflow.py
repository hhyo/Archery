# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: sql_workflow.py
@time: 2022/10/07
"""
__author__ = "hhyo"

import logging
import traceback

import simplejson as json
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from sql.engines import ReviewSet, get_engine
from sql.engines.models import ReviewResult
from sql.models import Instance, SqlWorkflow
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
    def execute(obj):
        """执行工单"""
        try:
            query_engine = get_engine(instance=obj.instance)
            return query_engine.execute_workflow(workflow=obj)
        except Exception as msg:
            logger.error(traceback.format_exc())
            raise serializers.ValidationError({"errors": msg})

    class Meta:
        model = SqlWorkflow
        fields = "__all__"


class SqlWorkflowDetailSerializer(SqlWorkflowSerializer):
    """仅用做文档生成，无实际意义"""
