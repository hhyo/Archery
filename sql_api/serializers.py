from rest_framework import serializers
from sql.models import (
    Users,
    Instance,
    Tunnel,
    AliyunRdsConfig,
    CloudAccessKey,
    SqlWorkflow,
    SqlWorkflowContent,
    ResourceGroup,
    WorkflowAudit,
    WorkflowLog,
    QueryPrivilegesApply,
    ArchiveConfig,
)
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from sql.engines import get_engine
from sql.utils.workflow_audit import Audit, get_auditor
from sql.utils.resource_group import user_instances
from common.utils.const import WorkflowType, WorkflowStatus
from common.config import SysConfig
import traceback
import logging

logger = logging.getLogger("default")


class UserSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        with transaction.atomic():
            extra_data = dict()
            for field in ("groups", "user_permissions", "resource_group"):
                if field in validated_data.keys():
                    extra_data[field] = validated_data.pop(field)
            user = Users(**validated_data)
            user.set_password(validated_data["password"])
            user.save()
            for field in extra_data.keys():
                getattr(user, field).set(extra_data[field])
            return user

    def validate_password(self, password):
        try:
            validate_password(password)
        except ValidationError as msg:
            raise serializers.ValidationError(msg)
        return password

    class Meta:
        model = Users
        fields = "__all__"
        extra_kwargs = {"password": {"write_only": True}, "display": {"required": True}}


class UserDetailSerializer(serializers.ModelSerializer):
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            if attr == "password":
                instance.set_password(value)
            elif attr in ("groups", "user_permissions", "resource_group"):
                getattr(instance, attr).set(value)
            else:
                setattr(instance, attr, value)
        instance.save()
        return instance

    def validate_password(self, password):
        try:
            validate_password(password)
        except ValidationError as msg:
            raise serializers.ValidationError(msg)
        return password

    class Meta:
        model = Users
        fields = "__all__"
        extra_kwargs = {
            "password": {"write_only": True, "required": False},
            "username": {"required": False},
        }


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = "__all__"


class ResourceGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceGroup
        fields = "__all__"


class UserAuthSerializer(serializers.Serializer):
    engineer = serializers.CharField(label="用户名")
    password = serializers.CharField(label="密码")


class TwoFASerializer(serializers.Serializer):
    engineer = serializers.CharField(label="用户名")
    enable = serializers.ChoiceField(choices=["true", "false"], label="启用or禁用")
    phone = serializers.CharField(required=False, label="手机号码")
    auth_type = serializers.ChoiceField(
        choices=["totp", "sms"], label="验证类型：totp-Google身份验证器，sms-短信验证码"
    )

    def validate(self, attrs):
        auth_type = attrs.get("auth_type")
        engineer = attrs.get("engineer")
        enable = attrs.get("enable")

        try:
            Users.objects.get(username=engineer)
        except Users.DoesNotExist:
            raise serializers.ValidationError({"errors": "不存在该用户"})

        if auth_type == "sms" and enable == "true":
            if not attrs.get("phone"):
                raise serializers.ValidationError({"errors": "缺少 phone"})

        return attrs


class TwoFAStateSerializer(serializers.Serializer):
    engineer = serializers.CharField(label="用户名")

    def validate(self, attrs):
        engineer = attrs.get("engineer")

        try:
            Users.objects.get(username=engineer)
        except Users.DoesNotExist:
            raise serializers.ValidationError({"errors": "不存在该用户"})

        return attrs


class TwoFASaveSerializer(serializers.Serializer):
    engineer = serializers.CharField(label="用户名")
    key = serializers.CharField(required=False, label="密钥")
    phone = serializers.CharField(required=False, label="手机号码")
    auth_type = serializers.ChoiceField(
        choices=["disabled", "totp", "sms"],
        label="验证类型：disabled-关闭，totp-Google身份验证器，sms-短信验证码",
    )

    def validate(self, attrs):
        engineer = attrs.get("engineer")
        auth_type = attrs.get("auth_type")
        key = attrs.get("key")
        phone = attrs.get("phone")

        if auth_type == "sms":
            if not phone:
                raise serializers.ValidationError({"errors": "缺少 phone"})

        if auth_type == "totp":
            if not key:
                raise serializers.ValidationError({"errors": "缺少 key"})

        try:
            Users.objects.get(username=engineer)
        except Users.DoesNotExist:
            raise serializers.ValidationError({"errors": "不存在该用户"})

        return attrs


class TwoFAVerifySerializer(serializers.Serializer):
    engineer = serializers.CharField(label="用户名")
    otp = serializers.IntegerField(label="一次性密码/验证码")
    key = serializers.CharField(required=False, label="密钥")
    phone = serializers.CharField(required=False, label="手机号码")
    auth_type = serializers.CharField(label="验证方式")

    def validate(self, attrs):
        engineer = attrs.get("engineer")
        auth_type = attrs.get("auth_type")

        if auth_type == "sms":
            if not attrs.get("phone"):
                raise serializers.ValidationError({"errors": "缺少 phone"})

        try:
            Users.objects.get(username=engineer)
        except Users.DoesNotExist:
            raise serializers.ValidationError({"errors": "不存在该用户"})

        return attrs


class InstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instance
        fields = "__all__"
        extra_kwargs = {"password": {"write_only": True}}


class InstanceDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instance
        fields = "__all__"
        extra_kwargs = {
            "password": {"write_only": True},
            "instance_name": {"required": False},
            "type": {"required": False},
            "db_type": {"required": False},
            "host": {"required": False},
        }


class TunnelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tunnel
        fields = "__all__"
        write_only_fields = ["password", "pkey", "pkey_password"]


class CloudAccessKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = CloudAccessKey
        fields = "__all__"


class AliyunRdsSerializer(serializers.ModelSerializer):
    ak = CloudAccessKeySerializer()

    def create(self, validated_data):
        """创建包含accesskey的aliyunrds实例"""
        rds_data = validated_data.pop("ak")

        try:
            with transaction.atomic():
                ak = CloudAccessKey.objects.create(**rds_data)
                rds = AliyunRdsConfig.objects.create(ak=ak, **validated_data)
        except Exception as e:
            logger.error(f"创建AliyunRds报错，错误信息：{traceback.format_exc()}")
            raise serializers.ValidationError({"errors": str(e)})
        else:
            return rds

    class Meta:
        model = AliyunRdsConfig
        fields = ("id", "rds_dbinstanceid", "is_enable", "instance", "ak")


class QueryPrivilegesApplySerializer(serializers.ModelSerializer):
    class Meta:
        model = QueryPrivilegesApply
        fields = "__all__"


class ArchiveConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArchiveConfig
        fields = "__all__"


class InstanceResourceSerializer(serializers.Serializer):
    instance_id = serializers.IntegerField(label="实例id")
    resource_type = serializers.ChoiceField(
        choices=["database", "schema", "table", "column"], label="资源类型"
    )
    db_name = serializers.CharField(required=False, label="数据库名")
    schema_name = serializers.CharField(required=False, label="schema名")
    tb_name = serializers.CharField(required=False, label="表名")

    def validate(self, attrs):
        instance_id = attrs.get("instance_id")

        try:
            Instance.objects.get(id=instance_id)
        except Instance.DoesNotExist:
            raise serializers.ValidationError({"errors": "不存在该实例"})

        return attrs


class InstanceResourceListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    result = serializers.ListField()


class ExecuteCheckSerializer(serializers.Serializer):
    instance_id = serializers.IntegerField(label="实例id")
    db_name = serializers.CharField(label="数据库名")
    full_sql = serializers.CharField(label="SQL内容")

    def validate_instance_id(self, instance_id):
        try:
            Instance.objects.get(pk=instance_id)
        except Instance.DoesNotExist:
            raise serializers.ValidationError(
                {"errors": f"不存在该实例：{instance_id}"}
            )
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
    rows = serializers.JSONField(read_only=True)
    column_list = serializers.JSONField(read_only=True)
    status = serializers.CharField(read_only=True)
    affected_rows = serializers.IntegerField(read_only=True)


class WorkflowSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        if data.get("run_date_start") == "":
            data["run_date_start"] = None
        if data.get("run_date_end") == "":
            data["run_date_end"] = None
        return super().to_internal_value(data)

    @staticmethod
    def validate_group_id(group_id):
        try:
            ResourceGroup.objects.get(pk=group_id)
        except ResourceGroup.DoesNotExist:
            raise serializers.ValidationError({"errors": f"不存在该资源组：{group_id}"})
        return group_id

    class Meta:
        model = SqlWorkflow
        fields = "__all__"
        read_only_fields = [
            "status",
            "syntax_type",
            "audit_auth_groups",
            "engineer_display",
            "group_name",
            "finish_time",
            "is_manual",
        ]
        extra_kwargs = {
            "demand_url": {"required": False},
            "is_backup": {"required": False},
            "engineer": {"required": False},
        }


class WorkflowContentSerializer(serializers.ModelSerializer):
    workflow = WorkflowSerializer()

    def create(self, validated_data):
        """使用原工单submit流程创建工单"""
        workflow_data = validated_data.pop("workflow")
        instance = workflow_data["instance"]
        sql_content = validated_data["sql_content"].strip()
        group = ResourceGroup.objects.get(pk=workflow_data["group_id"])
        engineer = workflow_data.get("engineer")

        # 管理员可以指定提交人信息
        if self.context["request"].user.is_superuser and engineer:
            try:
                user = Users.objects.get(username=engineer)
            except Users.DoesNotExist:
                raise serializers.ValidationError({"errors": f"不存在用户：{engineer}"})
        # 提交人只能是自己
        else:
            user = self.context["request"].user

        # 验证提交用户的组权限（用户是否在该组、该组是否有指定实例）
        try:
            user_instances(user, tag_codes=["can_write"]).get(id=instance.id)
        except instance.DoesNotExist:
            raise serializers.ValidationError({"errors": "你所在组未关联该实例！"})

        # 再次交给engine进行检测，防止绕过
        try:
            check_engine = get_engine(instance=instance)
            check_result = check_engine.execute_check(
                db_name=workflow_data["db_name"], sql=sql_content
            )
        except Exception as e:
            raise serializers.ValidationError({"errors": str(e)})

        # 未开启备份选项，并且engine支持备份，强制设置备份
        is_backup = (
            workflow_data["is_backup"] if "is_backup" in workflow_data.keys() else False
        )
        sys_config = SysConfig()
        if not sys_config.get("enable_backup_switch") and check_engine.auto_backup:
            is_backup = True

        # 按照系统配置确定是自动驳回还是放行
        auto_review_wrong = sys_config.get(
            "auto_review_wrong", ""
        )  # 1表示出现警告就驳回，2和空表示出现错误才驳回
        workflow_status = "workflow_manreviewing"
        if check_result.warning_count > 0 and auto_review_wrong == "1":
            workflow_status = "workflow_autoreviewwrong"
        elif check_result.error_count > 0 and auto_review_wrong in ("", "1", "2"):
            workflow_status = "workflow_autoreviewwrong"

        workflow_data.update(
            status=workflow_status,
            is_backup=is_backup,
            is_manual=0,
            syntax_type=check_result.syntax_type,
            engineer=user.username,
            engineer_display=user.display,
            group_name=group.group_name,
            audit_auth_groups="",
        )
        try:
            with transaction.atomic():
                workflow = SqlWorkflow(**workflow_data)
                validated_data["review_content"] = check_result.json()
                workflow.save()
                workflow_content = SqlWorkflowContent.objects.create(
                    workflow=workflow, **validated_data
                )
                # 自动创建工作流
                auditor = get_auditor(workflow=workflow)
                auditor.create_audit()
        except Exception as e:
            logger.error(f"提交工单报错，错误信息：{traceback.format_exc()}")
            raise serializers.ValidationError({"errors": str(e)})
        # 有时候提交后自动审批通过, 在这里改写一下 workflow 状态
        if auditor.audit.current_status == WorkflowStatus.PASSED:
            auditor.workflow.status = "workflow_review_pass"
        auditor.workflow.save()
        return workflow_content

    class Meta:
        model = SqlWorkflowContent
        fields = (
            "id",
            "workflow_id",
            "workflow",
            "sql_content",
            "review_content",
            "execute_result",
        )
        read_only_fields = ["review_content", "execute_result"]


class AuditWorkflowSerializer(serializers.Serializer):
    engineer = serializers.CharField(label="操作用户")
    workflow_id = serializers.IntegerField(label="工单id")
    audit_remark = serializers.CharField(label="审批备注")
    workflow_type = serializers.ChoiceField(
        choices=WorkflowType.choices,
        label="工单类型：1-查询权限申请，2-SQL上线申请，3-数据归档申请",
    )
    audit_type = serializers.ChoiceField(choices=["pass", "cancel"], label="审核类型")

    def validate(self, attrs):
        engineer = attrs.get("engineer")
        workflow_id = attrs.get("workflow_id")
        workflow_type = attrs.get("workflow_type")

        try:
            Users.objects.get(username=engineer)
        except Users.DoesNotExist:
            raise serializers.ValidationError({"errors": f"不存在该用户：{engineer}"})

        try:
            WorkflowAudit.objects.get(
                workflow_id=workflow_id, workflow_type=workflow_type
            )
        except WorkflowAudit.DoesNotExist:
            raise serializers.ValidationError({"errors": "不存在该工单"})

        return attrs


class WorkflowAuditSerializer(serializers.Serializer):
    engineer = serializers.CharField(label="操作用户")

    def validate_engineer(self, engineer):
        try:
            Users.objects.get(username=engineer)
        except Users.DoesNotExist:
            raise serializers.ValidationError({"errors": f"不存在该用户：{engineer}"})
        return engineer


class WorkflowAuditListSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowAudit
        exclude = [
            "group_id",
            "workflow_id",
            "workflow_remark",
            "next_audit",
            "create_user",
            "sys_time",
        ]


class WorkflowLogSerializer(serializers.Serializer):
    workflow_id = serializers.IntegerField(label="工单id")
    workflow_type = serializers.ChoiceField(
        choices=[1, 2, 3],
        label="工单类型：1-查询权限申请，2-SQL上线申请，3-数据归档申请",
    )

    def validate(self, attrs):
        workflow_id = attrs.get("workflow_id")
        workflow_type = attrs.get("workflow_type")

        try:
            WorkflowAudit.objects.get(
                workflow_id=workflow_id, workflow_type=workflow_type
            )
        except WorkflowAudit.DoesNotExist:
            raise serializers.ValidationError({"errors": "不存在该工单"})

        return attrs


class WorkflowLogListSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowLog
        fields = [
            "operation_type_desc",
            "operation_info",
            "operator_display",
            "operation_time",
        ]


class ExecuteWorkflowSerializer(serializers.Serializer):
    engineer = serializers.CharField(required=False, label="操作用户")
    workflow_id = serializers.IntegerField(label="工单id")
    workflow_type = serializers.ChoiceField(
        choices=[2, 3], label="工单类型：1-查询权限申请，2-SQL上线申请，3-数据归档申请"
    )
    mode = serializers.ChoiceField(
        choices=["auto", "manual"],
        label="执行模式：auto-线上执行，manual-已手动执行",
        required=False,
    )

    def validate(self, attrs):
        engineer = attrs.get("engineer")
        workflow_id = attrs.get("workflow_id")
        workflow_type = attrs.get("workflow_type")
        mode = attrs.get("mode")

        # SQL上线工单的mode和engineer为必需字段
        if workflow_type == 2:
            if not mode:
                raise serializers.ValidationError({"errors": "缺少 mode"})
            if not engineer:
                raise serializers.ValidationError({"errors": "缺少 engineer"})

            try:
                Users.objects.get(username=engineer)
            except Users.DoesNotExist:
                raise serializers.ValidationError(
                    {"errors": f"不存在该用户：{engineer}"}
                )

        try:
            WorkflowAudit.objects.get(
                workflow_id=workflow_id, workflow_type=workflow_type
            )
        except WorkflowAudit.DoesNotExist:
            raise serializers.ValidationError({"errors": "不存在该工单"})

        return attrs
