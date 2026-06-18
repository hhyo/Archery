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
from sql.utils.sql_utils import filter_db_list
from common.utils.const import WorkflowType, WorkflowStatus
from common.config import SysConfig
import logging
from sql.offlinedownload import OffLineDownLoad

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
            logger.error(f"创建AliyunRds失败: {e}", exc_info=True)
            raise serializers.ValidationError(
                {"errors": "创建AliyunRds失败，请联系管理员"}
            )
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


class TableInstanceLookupSerializer(serializers.Serializer):
    table_name = serializers.CharField(label="表名", max_length=256)


class TableInstanceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    db_type = serializers.CharField()
    db_name = serializers.CharField()
    table_name = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )


class LocatorFailureReasonSerializer(serializers.Serializer):
    instance_name = serializers.CharField()
    reason = serializers.CharField()


class LocatorExecutionSummarySerializer(serializers.Serializer):
    processed_instance_count = serializers.IntegerField()
    successful_instance_count = serializers.IntegerField()
    failed_instance_count = serializers.IntegerField()
    failure_reasons = LocatorFailureReasonSerializer(many=True)


class TableInstanceLookupResponseSerializer(serializers.Serializer):
    status = serializers.IntegerField()
    msg = serializers.CharField()
    count = serializers.IntegerField()
    data = TableInstanceSerializer(many=True)
    summary = LocatorExecutionSummarySerializer(required=False, allow_null=True)


class SqlQueryInstancesQuerySerializer(serializers.Serializer):
    type = serializers.CharField(required=False, allow_blank=True)
    db_type = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )
    tag_codes = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )


class SqlQueryResourceQuerySerializer(serializers.Serializer):
    instance_id = serializers.IntegerField(required=False)
    instance_name = serializers.CharField(required=False, allow_blank=True)
    resource_type = serializers.ChoiceField(
        choices=["database", "schema", "table", "column"]
    )
    db_name = serializers.CharField(required=False, allow_blank=True)
    schema_name = serializers.CharField(required=False, allow_blank=True)
    tb_name = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get("instance_id") and not attrs.get("instance_name"):
            raise serializers.ValidationError(
                "instance_id 或 instance_name 必须提供一个"
            )
        resource_type = attrs.get("resource_type")
        if resource_type in ("table", "schema") and not attrs.get("db_name"):
            raise serializers.ValidationError("db_name 不能为空")
        if resource_type == "column" and (
            not attrs.get("db_name") or not attrs.get("tb_name")
        ):
            raise serializers.ValidationError("column 查询需提供 db_name 和 tb_name")
        return attrs


class SqlQueryDescribeTableSerializer(serializers.Serializer):
    instance_name = serializers.CharField()
    db_name = serializers.CharField()
    tb_name = serializers.CharField()
    schema_name = serializers.CharField(required=False, allow_blank=True, default="")


class SqlQueryExecuteSerializer(serializers.Serializer):
    instance_name = serializers.CharField()
    db_name = serializers.CharField()
    schema_name = serializers.CharField(required=False, allow_blank=True)
    tb_name = serializers.CharField(required=False, allow_blank=True)
    sql_content = serializers.CharField()
    limit_num = serializers.IntegerField(min_value=0)


class SqlQueryLogsQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(required=False, default=0, min_value=0)
    offset = serializers.IntegerField(required=False, default=0, min_value=0)
    search = serializers.CharField(required=False, allow_blank=True, default="")
    star = serializers.CharField(required=False, allow_blank=True, default="")
    query_log_id = serializers.IntegerField(required=False)
    start_date = serializers.CharField(required=False, allow_blank=True, default="")
    end_date = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_star(self, value):
        return str(value).lower() == "true"


class SqlQueryFavoriteSerializer(serializers.Serializer):
    query_log_id = serializers.IntegerField(min_value=1)
    star = serializers.CharField()
    alias = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_star(self, value):
        return str(value).lower() == "true"


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


def _get_submit_user(request_user, engineer):
    """根据当前请求用户和指定用户名确定工单提交人。"""
    # 管理员可以指定提交人信息，其他用户只能替自己提交。
    if request_user.is_superuser and engineer:
        try:
            return Users.objects.get(username=engineer)
        except Users.DoesNotExist:
            raise serializers.ValidationError({"errors": f"不存在用户：{engineer}"})
    return request_user


def _normalize_db_resource_value(item):
    """将数据库资源列表中的不同返回格式统一转换为数据库名称字符串。"""
    if isinstance(item, dict):
        return str(item.get("value"))
    if isinstance(item, (list, tuple)) and len(item) == 1:
        return str(item[0])
    return str(item)


def _visible_db_names(instance):
    """获取实例中经过展示和屏蔽规则过滤后的可见数据库名称集合。"""
    query_engine = get_engine(instance=instance)
    resource = query_engine.get_all_databases()
    if getattr(resource, "error", None):
        logger.error(f"获取实例 {instance.id} 数据库列表失败: {resource.error}")
        raise serializers.ValidationError(
            {"errors": f"{instance.instance_name}: 获取数据库列表失败，请联系管理员"}
        )
    db_list = filter_db_list(
        db_list=resource.rows,
        db_name_regex=instance.show_db_name_regex,
        is_match_regex=True,
    )
    db_list = filter_db_list(
        db_list=db_list,
        db_name_regex=instance.denied_db_name_regex,
        is_match_regex=False,
    )
    return {_normalize_db_resource_value(db) for db in db_list}


def _build_batch_workflow_name(base_name, instance_name, db_name):
    """为批量提交的子工单生成包含实例名和数据库名的工单名称。"""
    suffix = f"-{instance_name}-{db_name}"
    if len(suffix) >= 50:
        return suffix[:50]
    return f"{base_name[: 50 - len(suffix)]}{suffix}"


def _create_workflow_content(workflow_data, sql_content, check_result):
    """创建单个 SQL 工单、保存 SQL 内容并初始化审批流程。"""
    try:
        with transaction.atomic():
            workflow = SqlWorkflow(**workflow_data)
            workflow.save()
            workflow_content = SqlWorkflowContent.objects.create(
                workflow=workflow,
                sql_content=sql_content,
                review_content=check_result.json(),
            )
            auditor = get_auditor(workflow=workflow)
            auditor.create_audit()
            if auditor.audit.current_status == WorkflowStatus.REJECTED:
                auditor.workflow.status = "workflow_autoreviewwrong"
            elif auditor.audit.current_status == WorkflowStatus.PASSED:
                auditor.workflow.status = "workflow_review_pass"
            auditor.workflow.save()
            return workflow_content
    except Exception as e:
        logger.error(f"提交工单失败: {e}", exc_info=True)
        raise serializers.ValidationError({"errors": "提交工单失败，请联系管理员"})


class WorkflowContentSerializer(serializers.ModelSerializer):
    workflow = WorkflowSerializer()

    def create(self, validated_data):
        """使用原工单submit流程创建工单"""
        workflow_data = validated_data.pop("workflow")
        instance = workflow_data["instance"]
        sql_content = validated_data["sql_content"].strip()
        group = ResourceGroup.objects.get(pk=workflow_data["group_id"])
        user = _get_submit_user(
            self.context["request"].user, workflow_data.get("engineer")
        )

        # 验证提交用户的组权限（用户是否在该组、该组是否有指定实例）
        tag_codes = (
            ["can_read"] if workflow_data["is_offline_export"] else ["can_write"]
        )
        try:
            user_instances(user, tag_codes=tag_codes).get(id=instance.id)
        except instance.DoesNotExist:
            raise serializers.ValidationError({"errors": "你所在组未关联该实例！"})

        # 再次交给engine进行检测，防止绕过
        try:
            check_engine = get_engine(instance=instance)
            sql_export = OffLineDownLoad()
            if workflow_data["is_offline_export"]:
                instance.sql_content = sql_content
                instance.selected_db_name = workflow_data["db_name"]
                check_result = sql_export.pre_count_check(workflow=instance)
            else:
                check_result = check_engine.execute_check(
                    db_name=workflow_data["db_name"], sql=sql_content
                )
        except Exception as e:
            logger.error(f"提交工单SQL检查失败: {e}", exc_info=True)
            raise serializers.ValidationError({"errors": "SQL检查失败，请联系管理员"})

        # 未开启备份选项，并且engine支持备份，强制设置备份
        is_backup = (
            False
            if workflow_data["is_offline_export"]
            else workflow_data.get("is_backup", False)
        )
        sys_config = SysConfig()
        if not sys_config.get("enable_backup_switch") and check_engine.auto_backup:
            if not workflow_data["is_offline_export"]:
                is_backup = True

        workflow_data.update(
            status="workflow_manreviewing",
            is_backup=is_backup,
            is_manual=0,
            syntax_type=check_result.syntax_type,
            engineer=user.username,
            engineer_display=user.display,
            group_name=group.group_name,
            audit_auth_groups="",
        )
        return _create_workflow_content(workflow_data, sql_content, check_result)

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


class BatchWorkflowSubmitSerializer(serializers.Serializer):
    """批量提交 SQL 上线工单的参数校验和工单创建序列化器。"""

    workflow = serializers.DictField()
    sql_content = serializers.CharField(label="SQL内容")

    @staticmethod
    def _dedupe_check(values, field_name):
        """校验列表字段是否存在重复值，并统一转换为字符串列表。"""
        normalized = [str(value) for value in values]
        if len(normalized) != len(set(normalized)):
            raise serializers.ValidationError({"errors": f"{field_name} 存在重复项"})
        return normalized

    def validate(self, attrs):
        """校验批量提交参数、实例权限、资源组关系和数据库可见性。"""
        workflow_payload = attrs["workflow"].copy()
        sql_content = attrs["sql_content"].strip()
        if not sql_content:
            raise serializers.ValidationError({"errors": "SQL内容不能为空"})

        instance_ids = workflow_payload.pop("instances", None)
        db_names = workflow_payload.pop("db_names", None)
        if not instance_ids:
            raise serializers.ValidationError({"errors": "请选择实例"})
        if not db_names:
            raise serializers.ValidationError({"errors": "请选择数据库"})

        try:
            instance_ids = [int(value) for value in instance_ids]
        except (TypeError, ValueError):
            raise serializers.ValidationError({"errors": "实例ID格式错误"})
        self._dedupe_check(instance_ids, "实例")
        db_names = self._dedupe_check(db_names, "数据库")

        workflow_payload.setdefault("is_offline_export", 0)
        if int(workflow_payload.get("is_offline_export") or 0) != 0:
            raise serializers.ValidationError({"errors": "批量提交不支持离线导出工单"})

        instances_by_id = Instance.objects.in_bulk(instance_ids)
        missing_ids = [pk for pk in instance_ids if pk not in instances_by_id]
        if missing_ids:
            raise serializers.ValidationError(
                {"errors": f"不存在实例：{','.join(str(pk) for pk in missing_ids)}"}
            )
        instances = [instances_by_id[pk] for pk in instance_ids]
        if len({instance.db_type for instance in instances}) > 1:
            raise serializers.ValidationError(
                {"errors": "批量提交实例必须属于同一数据库类型"}
            )

        single_payload = workflow_payload.copy()
        single_payload["instance"] = instances[0].id
        single_payload["db_name"] = db_names[0]
        workflow_serializer = WorkflowSerializer(data=single_payload)
        workflow_serializer.is_valid(raise_exception=True)
        base_workflow_data = workflow_serializer.validated_data
        group = ResourceGroup.objects.get(pk=base_workflow_data["group_id"])
        user = _get_submit_user(
            self.context["request"].user, base_workflow_data.get("engineer")
        )

        accessible_instances = user_instances(user, tag_codes=["can_write"]).filter(
            id__in=instance_ids
        )
        accessible_ids = set(accessible_instances.values_list("id", flat=True))
        for instance in instances:
            if instance.id not in accessible_ids:
                raise serializers.ValidationError({"errors": "你所在组未关联该实例！"})
            if not group.instance_set.filter(id=instance.id).exists():
                raise serializers.ValidationError(
                    {"errors": f"资源组未关联实例：{instance.instance_name}"}
                )

        for instance in instances:
            visible_db_names = _visible_db_names(instance)
            invisible_db_names = [
                db_name for db_name in db_names if db_name not in visible_db_names
            ]
            if invisible_db_names:
                raise serializers.ValidationError(
                    {
                        "errors": "{} 不存在或无权限访问数据库：{}".format(
                            instance.instance_name, ",".join(invisible_db_names)
                        )
                    }
                )

        attrs["sql_content"] = sql_content
        attrs["base_workflow_data"] = base_workflow_data
        attrs["instances"] = instances
        attrs["db_names"] = db_names
        attrs["group"] = group
        attrs["submit_user"] = user
        return attrs

    def create(self, validated_data):
        """按实例和数据库组合批量创建 SQL 上线工单及其审批记录。"""
        sql_content = validated_data["sql_content"]
        instances = validated_data["instances"]
        db_names = validated_data["db_names"]
        group = validated_data["group"]
        user = validated_data["submit_user"]
        base_workflow_data = validated_data["base_workflow_data"]

        first_instance = instances[0]
        first_db_name = db_names[0]
        try:
            check_engine = get_engine(instance=first_instance)
            check_result = check_engine.execute_check(
                db_name=first_db_name, sql=sql_content
            )
        except Exception as e:
            logger.error(f"批量提交工单SQL检查失败: {e}", exc_info=True)
            raise serializers.ValidationError({"errors": "SQL检查失败，请联系管理员"})

        is_backup = base_workflow_data.get("is_backup", False)
        sys_config = SysConfig()
        if not sys_config.get("enable_backup_switch") and check_engine.auto_backup:
            is_backup = True

        target_count = len(instances) * len(db_names)
        workflow_contents = []
        try:
            with transaction.atomic():
                for instance in instances:
                    for db_name in db_names:
                        workflow_data = base_workflow_data.copy()
                        if target_count > 1:
                            workflow_data["workflow_name"] = _build_batch_workflow_name(
                                base_workflow_data["workflow_name"],
                                instance.instance_name,
                                db_name,
                            )
                        workflow_data.update(
                            group_name=group.group_name,
                            instance=instance,
                            db_name=db_name,
                            status="workflow_manreviewing",
                            is_backup=is_backup,
                            is_manual=0,
                            is_offline_export=0,
                            syntax_type=check_result.syntax_type,
                            engineer=user.username,
                            engineer_display=user.display,
                            audit_auth_groups="",
                        )
                        workflow = SqlWorkflow(**workflow_data)
                        workflow.save()
                        workflow_content = SqlWorkflowContent.objects.create(
                            workflow=workflow,
                            sql_content=sql_content,
                            review_content=check_result.json(),
                        )
                        auditor = get_auditor(workflow=workflow)
                        auditor.create_audit()
                        if auditor.audit.current_status == WorkflowStatus.REJECTED:
                            auditor.workflow.status = "workflow_autoreviewwrong"
                        elif auditor.audit.current_status == WorkflowStatus.PASSED:
                            auditor.workflow.status = "workflow_review_pass"
                        auditor.workflow.save()
                        workflow_contents.append(workflow_content)
        except Exception as e:
            logger.error(f"批量提交工单失败: {e}", exc_info=True)
            raise serializers.ValidationError(
                {"errors": "批量提交工单失败，请联系管理员"}
            )

        return workflow_contents


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


class BatchWorkflowOperationSerializer(serializers.Serializer):
    """批量审核、执行或终止 SQL 工单的参数校验序列化器。"""

    operation = serializers.ChoiceField(
        choices=["audit", "execute", "cancel"], label="批量操作类型"
    )
    workflow_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        label="工单ID列表",
    )
    remark = serializers.CharField(required=False, allow_blank=True, default="")
    mode = serializers.ChoiceField(
        choices=["auto"], required=False, default="auto", label="执行模式"
    )

    def validate(self, attrs):
        """校验批量操作工单是否存在、状态是否一致以及终止原因是否完整。"""
        workflow_ids = attrs["workflow_ids"]
        if len(workflow_ids) != len(set(workflow_ids)):
            raise serializers.ValidationError({"errors": "工单ID存在重复项"})
        if attrs["operation"] == "cancel" and not attrs.get("remark"):
            raise serializers.ValidationError({"errors": "终止原因不能为空"})
        workflows = list(
            SqlWorkflow.objects.filter(id__in=workflow_ids).order_by(
                "create_time", "id"
            )
        )
        if len(workflows) != len(workflow_ids):
            found_ids = {workflow.id for workflow in workflows}
            missing_ids = [str(pk) for pk in workflow_ids if pk not in found_ids]
            raise serializers.ValidationError(
                {"errors": f"不存在工单：{','.join(missing_ids)}"}
            )
        statuses = {workflow.status for workflow in workflows}
        if len(statuses) != 1:
            raise serializers.ValidationError(
                {"errors": "批量操作的工单必须处于同一状态"}
            )
        attrs["workflows"] = workflows
        return attrs
