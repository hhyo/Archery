# -*- coding: UTF-8 -*-
import importlib
import logging
from typing import Optional

from django.db import models
from django.contrib.auth.models import AbstractUser
from mirage import fields
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from mirage.crypto import Crypto

from common.utils.const import WorkflowStatus, WorkflowType, WorkflowAction

logger = logging.getLogger("default")
file, _class = settings.PASSWORD_MIXIN_PATH.split(":")

try:
    password_module = importlib.import_module(file)
    PasswordMixin = getattr(password_module, _class)
except (ImportError, AttributeError) as e:
    logger.error(
        f"failed to import password minxin {settings.PASSWORD_MIXIN_PATH}, {str(e)}"
    )
    logger.error(f"falling back to dummy mixin")
    from sql.plugins.password import DummyMixin

    PasswordMixin = DummyMixin


class ResourceGroup(models.Model):
    """
    资源组
    """

    group_id = models.AutoField(_("Group ID"), primary_key=True)
    group_name = models.CharField(_("Group Name"), max_length=100, unique=True)
    group_parent_id = models.BigIntegerField(_("Parent ID"), default=0)
    group_sort = models.IntegerField(_("Sort Order"), default=1)
    group_level = models.IntegerField(_("Level"), default=1)
    ding_webhook = models.CharField(_("DingTalk Webhook URL"), max_length=255, blank=True)
    feishu_webhook = models.CharField(_("Feishu Webhook URL"), max_length=255, blank=True)
    qywx_webhook = models.CharField(_("WeCom Webhook URL"), max_length=255, blank=True)
    is_deleted = models.IntegerField(
        _("Deleted"), choices=((0, _("No")), (1, _("Yes"))), default=0
    )
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.group_name

    class Meta:
        managed = True
        db_table = "resource_group"
        verbose_name = _("Resource Group Management")
        verbose_name_plural = _("Resource Group Management")


class Users(AbstractUser):
    """
    用户信息扩展
    """

    display = models.CharField(_("Display Name"), max_length=50, default="")
    ding_user_id = models.CharField(_("DingTalk User ID"), max_length=64, blank=True)
    wx_user_id = models.CharField(_("WeCom User ID"), max_length=64, blank=True)
    feishu_open_id = models.CharField(_("Feishu OpenID"), max_length=64, blank=True)
    failed_login_count = models.IntegerField(_("Failed Login Count"), default=0)
    last_login_failed_at = models.DateTimeField(
        _("Last Failed Login Time"), blank=True, null=True
    )
    resource_group = models.ManyToManyField(
        ResourceGroup, verbose_name=_("Resource Group"), blank=True
    )

    def save(self, *args, **kwargs):
        self.failed_login_count = min(127, self.failed_login_count)
        self.failed_login_count = max(0, self.failed_login_count)
        super(Users, self).save(*args, **kwargs)

    def __str__(self):
        if self.display:
            return self.display
        return self.username

    class Meta:
        managed = True
        db_table = "sql_users"
        verbose_name = _("User Management")
        verbose_name_plural = _("User Management")


class TwoFactorAuthConfig(models.Model):
    """
    2fa配置信息
    """

    auth_type_choice = (
        ("totp", _("Google Authenticator")),
        ("sms", _("SMS Code")),
    )

    username = fields.EncryptedCharField(verbose_name=_("Username"), max_length=200)
    auth_type = fields.EncryptedCharField(
        verbose_name=_("Authentication Type"), max_length=128, choices=auth_type_choice
    )
    phone = fields.EncryptedCharField(
        verbose_name=_("Mobile Number"), max_length=64, null=True, default=""
    )
    secret_key = fields.EncryptedCharField(
        verbose_name=_("Secret Key"), max_length=256, null=True
    )
    user = models.ForeignKey(Users, on_delete=models.CASCADE)

    class Meta:
        managed = True
        db_table = "2fa_config"
        verbose_name = _("2FA Configuration")
        verbose_name_plural = _("2FA Configuration")
        unique_together = ("user", "auth_type")


class InstanceTag(models.Model):
    """Instance Tag Configuration"""

    tag_code = models.CharField(_("Tag Code"), max_length=20, unique=True)
    tag_name = models.CharField(_("Tag Name"), max_length=20, unique=True)
    active = models.BooleanField(_("Active Status"), default=True)
    create_time = models.DateTimeField(_("Created At"), auto_now_add=True)

    def __str__(self):
        return self.tag_name

    class Meta:
        managed = True
        db_table = "sql_instance_tag"
        verbose_name = _("Instance Tag")
        verbose_name_plural = _("Instance Tag")


DB_TYPE_CHOICES = (
    ("mysql", "MySQL"),
    ("mssql", "MsSQL"),
    ("redis", "Redis"),
    ("pgsql", "PgSQL"),
    ("oracle", "Oracle"),
    ("mongo", "Mongo"),
    ("phoenix", "Phoenix"),
    ("odps", "ODPS"),
    ("clickhouse", "ClickHouse"),
    ("goinception", "goInception"),
    ("cassandra", "Cassandra"),
    ("doris", "Doris"),
    ("elasticsearch", "Elasticsearch"),
    ("opensearch", "OpenSearch"),
    ("memcached", "Memcached"),
    ("tdengine", "TDengine"),
)


class Tunnel(models.Model):
    """
    SSH隧道配置
    """

    tunnel_name = models.CharField(_("Tunnel Name"), max_length=50, unique=True)
    host = models.CharField(_("Tunnel Endpoint"), max_length=200)
    port = models.IntegerField(_("Port"), default=0)
    user = fields.EncryptedCharField(
        verbose_name=_("Username"), max_length=200, default="", blank=True, null=True
    )
    password = fields.EncryptedCharField(
        verbose_name=_("Password"), max_length=300, default="", blank=True, null=True
    )
    pkey = fields.EncryptedTextField(verbose_name=_("Private Key"), blank=True, null=True)
    pkey_path = models.FileField(
        verbose_name=_("Key File"), blank=True, null=True, upload_to="keys/"
    )
    pkey_password = fields.EncryptedCharField(
        verbose_name=_("Key Password"), max_length=300, default="", blank=True, null=True
    )
    create_time = models.DateTimeField(_("Created At"), auto_now_add=True)
    update_time = models.DateTimeField(_("Updated At"), auto_now=True)

    def __str__(self):
        return self.tunnel_name

    def short_pkey(self):
        if len(str(self.pkey)) > 20:
            return "{}...".format(str(self.pkey)[0:19])
        else:
            return str(self.pkey)

    class Meta:
        managed = True
        db_table = "ssh_tunnel"
        verbose_name = _("Tunnel Configuration")
        verbose_name_plural = _("Tunnel Configuration")


class Instance(models.Model, PasswordMixin):
    """
    各个线上实例配置
    """

    instance_name = models.CharField(_("Instance Name"), max_length=50, unique=True)
    type = models.CharField(
        _("Instance Type"), max_length=6, choices=(("master", _("Master")), ("slave", _("Replica")))
    )
    db_type = models.CharField(_("Database Type"), max_length=20, choices=DB_TYPE_CHOICES)
    mode = models.CharField(
        _("Run Mode"),
        max_length=10,
        default="",
        blank=True,
        choices=(("standalone", _("Standalone")), ("cluster", _("Cluster"))),
    )
    host = models.CharField(_("Instance Host"), max_length=200)
    port = models.IntegerField(_("Port"), default=0)
    user = fields.EncryptedCharField(
        verbose_name=_("Username"), max_length=200, default="", blank=True
    )
    password = fields.EncryptedCharField(
        verbose_name=_("Password"), max_length=300, default="", blank=True
    )
    is_ssl = models.BooleanField(_("Enable SSL"), default=False)
    verify_ssl = models.BooleanField(_("Verify Server SSL Certificate"), default=True)
    db_name = models.CharField(_("Database"), max_length=64, default="", blank=True)
    show_db_name_regex = models.CharField(
        _("Visible Database Regex"),
        max_length=1024,
        default="",
        blank=True,
        help_text=_("Regex. Example: ^(test_db|dmp_db|za.*)$. Redis example: ^(0|4|6|11|12|13)$"),
    )
    denied_db_name_regex = models.CharField(
        _("Hidden Database Regex"),
        max_length=1024,
        default="",
        blank=True,
        help_text=_("Regex. Hidden rules take priority over visible rules."),
    )

    charset = models.CharField(_("Charset"), max_length=20, default="", blank=True)
    service_name = models.CharField(
        "Oracle service name", max_length=50, null=True, blank=True
    )
    sid = models.CharField("Oracle sid", max_length=50, null=True, blank=True)
    resource_group = models.ManyToManyField(
        ResourceGroup, verbose_name=_("Resource Group"), blank=True
    )
    instance_tag = models.ManyToManyField(
        InstanceTag, verbose_name=_("Instance Tag"), blank=True
    )
    tunnel = models.ForeignKey(
        Tunnel,
        verbose_name=_("Tunnel"),
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        default=None,
    )
    create_time = models.DateTimeField(_("Created At"), auto_now_add=True)
    update_time = models.DateTimeField(_("Updated At"), auto_now=True)

    def __str__(self):
        return self.instance_name

    class Meta:
        managed = True
        db_table = "sql_instance"
        verbose_name = _("Instance Configuration")
        verbose_name_plural = _("Instance Configuration")


SQL_WORKFLOW_CHOICES = (
    ("Workflow Finished", _("Workflow Finished")),
    ("Workflow Aborted", _("Workflow Aborted")),
    ("Manually Reviewing", _("Manually Reviewing")),
    ("Review Passed", _("Review Passed")),
    ("Scheduled", _("Scheduled")),
    ("Queued", _("Queued")),
    ("Executing", _("Executing")),
    ("Auto Review Failed", _("Auto Review Failed")),
    ("Exception", _("Exception")),
)


class WorkflowAuditMixin:
    @property
    def workflow_type(self):
        if isinstance(self, SqlWorkflow):
            return WorkflowType.SQL_REVIEW
        elif isinstance(self, ArchiveConfig):
            return WorkflowType.ARCHIVE
        elif isinstance(self, QueryPrivilegesApply):
            return WorkflowType.QUERY

    @property
    def workflow_pk_field(self):
        if isinstance(self, SqlWorkflow):
            return "id"
        elif isinstance(self, ArchiveConfig):
            return "id"
        elif isinstance(self, QueryPrivilegesApply):
            return "apply_id"

    def get_audit(self) -> Optional["WorkflowAudit"]:
        try:
            return WorkflowAudit.objects.get(
                workflow_type=self.workflow_type,
                workflow_id=getattr(self, self.workflow_pk_field),
            )
        except WorkflowAudit.DoesNotExist:
            return None


class SqlWorkflow(models.Model, WorkflowAuditMixin):
    """
    存放各个SQL上线工单的基础内容
    """

    workflow_name = models.CharField(_("Workflow Name"), max_length=50)
    demand_url = models.CharField(_("Request URL"), max_length=500, blank=True)
    group_id = models.IntegerField(_("Group ID"))
    group_name = models.CharField(_("Group Name"), max_length=100)
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    db_name = models.CharField(_("Database"), max_length=64)
    syntax_type = models.IntegerField(
        _("Workflow Type 0 Unknown, 1 DDL, 2 DML, 3 Offline Export Workflow"),
        choices=((0, _("Other")), (1, "DDL"), (2, "DML"), (3, _("Offline Export Workflow"))),
        default=0,
    )
    is_backup = models.BooleanField(
        _("Backup"),
        choices=(
            (False, _("No")),
            (True, _("Yes")),
        ),
        default=True,
    )
    engineer = models.CharField(_("Initiator"), max_length=30)
    engineer_display = models.CharField(_("Initiator Display Name"), max_length=50, default="")
    status = models.CharField(max_length=50, choices=SQL_WORKFLOW_CHOICES)
    audit_auth_groups = models.CharField(_("Approval Group List"), max_length=255)
    run_date_start = models.DateTimeField(_("Execution Start Time"), null=True, blank=True)
    run_date_end = models.DateTimeField(_("Execution End Time"), null=True, blank=True)
    create_time = models.DateTimeField(_("Created At"), auto_now_add=True)
    finish_time = models.DateTimeField(_("Finished At"), null=True, blank=True)
    is_manual = models.IntegerField(
        _("Native Execution"), choices=((0, _("No")), (1, _("Yes"))), default=0
    )
    is_offline_export = models.IntegerField(
        _("Is Offline Export Workflow"),
        choices=(
            (0, _("No")),
            (1, _("Yes")),
        ),
        default=0,
    )

    # 导出格式
    export_format = models.CharField(
        _("Export Format"),
        max_length=10,
        choices=(
            ("csv", "CSV"),
            ("xlsx", "Excel"),
            ("sql", "SQL"),
            ("json", "JSON"),
            ("xml", "XML"),
        ),
        # default="csv",
        null=True,
        blank=True,
    )

    file_name = models.CharField(
        _("File Name"),
        max_length=255,  # 适当调整最大长度
        null=True,  # 允许为空
        blank=True,  # 允许为空字符串
    )

    def __str__(self):
        return self.workflow_name

    class Meta:
        managed = True
        db_table = "sql_workflow"
        verbose_name = _("SQL Workflow")
        verbose_name_plural = _("SQL Workflow")


class SqlWorkflowContent(models.Model):
    """
    存放各个SQL上线工单的SQL|审核|执行内容
    可定期归档或清理历史数据，也可通过``alter table sql_workflow_content row_format=compressed; ``来进行压缩
    """

    workflow = models.OneToOneField(SqlWorkflow, on_delete=models.CASCADE)
    sql_content = models.TextField(_("SQL Content"))
    review_content = models.TextField(_("Auto Review JSON"))
    execute_result = models.TextField(_("Execution Result JSON"), blank=True)

    def __str__(self):
        return self.workflow.workflow_name

    class Meta:
        managed = True
        db_table = "sql_workflow_content"
        verbose_name = _("SQL Workflow Content")
        verbose_name_plural = _("SQL Workflow Content")


class WorkflowAudit(models.Model):
    """
    工作流审核状态表
    """

    audit_id = models.AutoField(primary_key=True)
    group_id = models.IntegerField(_("Group ID"))
    group_name = models.CharField(_("Group Name"), max_length=100)
    workflow_id = models.BigIntegerField(_("Related Business ID"))
    workflow_type = models.IntegerField(_("Request Type"), choices=WorkflowType.choices)
    workflow_title = models.CharField(_("Request Title"), max_length=50)
    workflow_remark = models.CharField(
        _("Request Remark"), default="", max_length=140, blank=True
    )
    audit_auth_groups = models.CharField(_("Approval Group List"), max_length=255)
    current_audit = models.CharField(_("Current Approval Group"), max_length=20)
    next_audit = models.CharField(_("Next Approval Group"), max_length=20)
    current_status = models.IntegerField(_("Review Status"), choices=WorkflowStatus.choices)
    create_user = models.CharField(_("Requester"), max_length=30)
    create_user_display = models.CharField(_("Requester Display Name"), max_length=50, default="")
    create_time = models.DateTimeField(_("Request Time"), auto_now_add=True)
    sys_time = models.DateTimeField(_("System Time"), auto_now=True)

    def get_workflow(self):
        """尝试从 audit 中取出 workflow"""
        if self.workflow_type == WorkflowType.QUERY:
            return QueryPrivilegesApply.objects.get(apply_id=self.workflow_id)
        elif self.workflow_type == WorkflowType.SQL_REVIEW:
            return SqlWorkflow.objects.get(id=self.workflow_id)
        elif self.workflow_type == WorkflowType.ARCHIVE:
            return ArchiveConfig.objects.get(id=self.workflow_id)
        raise ValueError(_("Unable to get the related workflow"))

    def __int__(self):
        return self.audit_id

    class Meta:
        managed = True
        db_table = "workflow_audit"
        unique_together = ("workflow_id", "workflow_type")
        verbose_name = _("Workflow Audit List")
        verbose_name_plural = _("Workflow Audit List")


class WorkflowAuditDetail(models.Model):
    """
    审批明细表
    TODO
    部分字段与 WorkflowLog 重复, 建议整合到一起)
    """

    audit_detail_id = models.AutoField(primary_key=True)
    audit_id = models.IntegerField(_("Workflow Audit ID"))
    audit_user = models.CharField(_("Reviewer"), max_length=30)
    audit_time = models.DateTimeField(_("Review Time"))
    audit_status = models.IntegerField(_("Review Status"), choices=WorkflowStatus.choices)
    remark = models.CharField(_("Review Remark"), default="", max_length=1000)
    sys_time = models.DateTimeField(_("System Time"), auto_now=True)

    def __int__(self):
        return self.audit_detail_id

    class Meta:
        managed = True
        db_table = "workflow_audit_detail"
        verbose_name = _("Workflow Audit Detail")
        verbose_name_plural = _("Workflow Audit Detail")


class WorkflowAuditSetting(models.Model):
    """
    审批配置表
    """

    audit_setting_id = models.AutoField(primary_key=True)
    group_id = models.IntegerField(_("Group ID"))
    group_name = models.CharField(_("Group Name"), max_length=100)
    workflow_type = models.IntegerField(_("Approval Type"), choices=WorkflowType.choices)
    audit_auth_groups = models.CharField(_("Approval Group List"), max_length=255)
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    def __int__(self):
        return self.audit_setting_id

    class Meta:
        managed = True
        db_table = "workflow_audit_setting"
        unique_together = ("group_id", "workflow_type")
        verbose_name = _("Approval Configuration")
        verbose_name_plural = _("Approval Configuration")


class WorkflowLog(models.Model):
    """
    工作流日志表
    """

    id = models.AutoField(primary_key=True)
    audit_id = models.IntegerField(_("Workflow Audit ID"), db_index=True)
    operation_type = models.SmallIntegerField(
        _("Action Type"), choices=WorkflowAction.choices
    )
    # operation_type_desc 字段实际无意义
    operation_type_desc = models.CharField(_("Action Type Description"), max_length=10)
    operation_info = models.CharField(_("Action Info"), max_length=1000)
    operator = models.CharField(_("Operator"), max_length=30)
    operator_display = models.CharField(_("Operator Display Name"), max_length=50, default="")
    operation_time = models.DateTimeField(auto_now_add=True)

    def __int__(self):
        return self.audit_id

    class Meta:
        managed = True
        db_table = "workflow_log"
        verbose_name = _("Workflow Log")
        verbose_name_plural = _("Workflow Log")


class QueryPrivilegesApply(models.Model, WorkflowAuditMixin):
    """
    查询权限申请记录表
    """

    apply_id = models.AutoField(primary_key=True)
    group_id = models.IntegerField(_("Group ID"))
    group_name = models.CharField(_("Group Name"), max_length=100)
    title = models.CharField(_("Request Title"), max_length=50)
    # TODO user_name display 改为外键
    user_name = models.CharField(_("Requester"), max_length=30)
    user_display = models.CharField(_("Requester Display Name"), max_length=50, default="")
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    db_list = models.TextField(_("Database"), default="")  # 逗号分隔的数据库列表
    table_list = models.TextField(_("Table"), default="")  # 逗号分隔的表列表
    valid_date = models.DateField(_("Valid Time"))
    limit_num = models.IntegerField(_("Row Limit"), default=100)
    priv_type = models.IntegerField(
        _("Privilege Type"),
        choices=(
            (1, "DATABASE"),
            (2, "TABLE"),
        ),
        default=0,
    )
    status = models.IntegerField(_("Review Status"), choices=WorkflowStatus.choices)
    audit_auth_groups = models.CharField(_("Approval Group List"), max_length=255)
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    def __int__(self):
        return self.apply_id

    class Meta:
        managed = True
        db_table = "query_privileges_apply"
        verbose_name = _("Query Privilege Request Records")
        verbose_name_plural = _("Query Privilege Request Records")


class QueryPrivileges(models.Model):
    """
    用户权限关系表
    """

    privilege_id = models.AutoField(primary_key=True)
    user_name = models.CharField(_("Username"), max_length=30)
    user_display = models.CharField(_("Requester Display Name"), max_length=50, default="")
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    db_name = models.CharField(_("Database"), max_length=64, default="")
    table_name = models.CharField(_("Table"), max_length=64, default="")
    valid_date = models.DateField(_("Valid Time"))
    limit_num = models.IntegerField(_("Row Limit"), default=100)
    priv_type = models.IntegerField(
        _("Privilege Type"),
        choices=(
            (1, "DATABASE"),
            (2, "TABLE"),
        ),
        default=0,
    )
    is_deleted = models.IntegerField(_("Deleted"), default=0)
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    def __int__(self):
        return self.privilege_id

    class Meta:
        managed = True
        db_table = "query_privileges"
        indexes = [
            models.Index(fields=["user_name", "instance", "db_name", "table_name"]),
        ]
        verbose_name = _("Query Privilege Records")
        verbose_name_plural = _("Query Privilege Records")


class QueryLog(models.Model):
    """
    记录在线查询sql的日志
    """

    # TODO 改为实例外键
    instance_name = models.CharField(_("Instance Name"), max_length=50)
    db_name = models.CharField(_("Database Name"), max_length=64)
    sqllog = models.TextField(_("Executed Query"))
    effect_row = models.BigIntegerField(_("Returned Rows"))
    cost_time = models.CharField(_("Elapsed Time"), max_length=10, default="")
    # TODO 改为user 外键
    username = models.CharField(_("Operator"), max_length=30)
    user_display = models.CharField(_("Operator Display Name"), max_length=50, default="")
    priv_check = models.BooleanField(
        _("Query Privilege Check"),
        choices=(
            (False, _("Skipped")),
            (True, _("Normal")),
        ),
        default=False,
    )
    hit_rule = models.BooleanField(
        _("Masking Rule Hit"),
        choices=((False, _("Missed/Unknown")), (True, _("Hit"))),
        default=False,
    )
    masking = models.BooleanField(
        _("Query Result Masked"),
        choices=(
            (False, _("No")),
            (True, _("Yes")),
        ),
        default=False,
    )
    favorite = models.BooleanField(
        _("Favorited"),
        choices=(
            (False, _("No")),
            (True, _("Yes")),
        ),
        default=False,
    )
    alias = models.CharField(_("Statement Tag"), max_length=64, default="", blank=True)
    create_time = models.DateTimeField(_("Action Time"), auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = "query_log"
        verbose_name = _("Query Log")
        verbose_name_plural = _("Query Log")


rule_type_choices = (
    (1, _("Mobile Number")),
    (2, _("ID Number")),
    (3, _("Bank Card")),
    (4, _("Email")),
    (5, _("Amount")),
    (6, _("Other")),
    (100, _("Three-part Generic Masking Rule")),
)


class DataMaskingColumns(models.Model):
    """
    脱敏字段配置
    """

    column_id = models.AutoField(_("Field ID"), primary_key=True)
    rule_type = models.IntegerField(
        _("Rule Type"),
        choices=rule_type_choices,
        help_text=_("Three-part generic masking rule: automatically splits a field into three parts by length and masks the middle part."),
    )
    active = models.BooleanField(
        _("Active Status"), choices=((False, _("Inactive")), (True, _("Active")))
    )
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    table_schema = models.CharField(_("Database Name"), max_length=64)
    table_name = models.CharField(_("Table Name"), max_length=64)
    column_name = models.CharField(_("Column Name"), max_length=64)
    column_comment = models.CharField(
        _("Column Description"), max_length=1024, default="", blank=True
    )
    create_time = models.DateTimeField(auto_now_add=True)
    sys_time = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = "data_masking_columns"
        verbose_name = _("Data Masking Field Configuration")
        verbose_name_plural = _("Data Masking Field Configuration")


class DataMaskingRules(models.Model):
    """
    脱敏规则配置
    """

    rule_type = models.IntegerField(_("Rule Type"), choices=rule_type_choices, unique=True)
    rule_regex = models.CharField(
        _("Regular expression used by the masking rule. The expression must include capture groups; hidden groups will be replaced with ****."),
        max_length=255,
    )
    hide_group = models.IntegerField(_("Groups to Mask"))
    rule_desc = models.CharField(_("Rule Description"), max_length=100, default="", blank=True)
    sys_time = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = "data_masking_rules"
        verbose_name = _("Masking Rule Configuration")
        verbose_name_plural = _("Masking Rule Configuration")


class InstanceAccount(models.Model):
    """
    实例账号列表
    """

    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    user = fields.EncryptedCharField(verbose_name=_("Account"), max_length=128)
    host = models.CharField(
        verbose_name=_("Host"), max_length=64
    )  # mysql数据库存储主机信息
    db_name = models.CharField(
        verbose_name=_("Database Name"), max_length=128
    )  # mongo数据库存储数据库名称
    password = fields.EncryptedCharField(
        verbose_name=_("Password"), max_length=128, default="", blank=True
    )
    remark = models.CharField(_("Remark"), max_length=255)
    sys_time = models.DateTimeField(_("System Updated At"), auto_now=True)

    class Meta:
        managed = True
        db_table = "instance_account"
        unique_together = ("instance", "user", "host", "db_name")
        verbose_name = _("Instance Account List")
        verbose_name_plural = _("Instance Account List")


class InstanceDatabase(models.Model):
    """
    实例数据库列表
    """

    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    db_name = models.CharField(_("Database Name"), max_length=128)
    owner = models.CharField(_("Owner"), max_length=50, default="", blank=True)
    owner_display = models.CharField(
        _("Owner Display Name"), max_length=50, default="", blank=True
    )
    remark = models.CharField(_("Remark"), max_length=255, default="", blank=True)
    sys_time = models.DateTimeField(_("System Updated At"), auto_now=True)

    class Meta:
        managed = True
        db_table = "instance_database"
        unique_together = ("instance", "db_name")
        verbose_name = _("Instance Database")
        verbose_name_plural = _("Instance Database List")


class ParamTemplate(models.Model):
    """
    实例参数模板配置
    """

    db_type = models.CharField(_("Database Type"), max_length=20, choices=DB_TYPE_CHOICES)
    variable_name = models.CharField(_("Variable Name"), max_length=64)
    default_value = models.CharField(_("Default Value"), max_length=1024)
    editable = models.BooleanField(_("Editable"), default=False)
    valid_values = models.CharField(
        _("Valid value, range parameter [1-65535], value parameter [ON|OFF]"), max_length=1024, blank=True
    )
    description = models.CharField(_("Description"), max_length=1024, blank=True)
    create_time = models.DateTimeField(_("Created At"), auto_now_add=True)
    sys_time = models.DateTimeField(_("System Updated At"), auto_now=True)

    class Meta:
        managed = True
        db_table = "param_template"
        unique_together = ("db_type", "variable_name")
        verbose_name = _("Instance Parameter Template")
        verbose_name_plural = _("Instance Parameter Template")


class ParamHistory(models.Model):
    """
    可在线修改的动态参数配置
    """

    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    variable_name = models.CharField(_("Variable Name"), max_length=64)
    old_var = models.CharField(_("Old Value"), max_length=1024)
    new_var = models.CharField(_("New Value"), max_length=1024)
    set_sql = models.CharField(_("SQL Statement Executed for Online Change"), max_length=1024)
    user_name = models.CharField(_("Modifier"), max_length=30)
    user_display = models.CharField(_("Modifier Display Name"), max_length=50)
    create_time = models.DateTimeField(_("Modified At"), auto_now_add=True)

    class Meta:
        managed = True
        ordering = ["-create_time"]
        db_table = "param_history"
        verbose_name = _("Instance Parameter History")
        verbose_name_plural = _("Instance Parameter History")


class ArchiveConfig(models.Model, WorkflowAuditMixin):
    """
    归档配置表
    """

    title = models.CharField(_("Archive Configuration Name"), max_length=50)
    resource_group = models.ForeignKey(ResourceGroup, on_delete=models.CASCADE)
    audit_auth_groups = models.CharField(_("Approval Group List"), max_length=255, blank=True)
    src_instance = models.ForeignKey(
        Instance, related_name="src_instance", on_delete=models.CASCADE
    )
    src_db_name = models.CharField(_("Source Database"), max_length=64)
    src_table_name = models.CharField(_("Source Table"), max_length=64)
    dest_instance = models.ForeignKey(
        Instance,
        related_name="dest_instance",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    dest_db_name = models.CharField(_("Target Database"), max_length=64, blank=True, null=True)
    dest_table_name = models.CharField(_("Target Table"), max_length=64, blank=True, null=True)
    condition = models.CharField(_("Archive Condition (WHERE clause)"), max_length=1000)
    mode = models.CharField(
        _("Archive Mode"),
        max_length=10,
        choices=(("file", _("File")), ("dest", _("Another Instance")), ("purge", _("Delete Directly"))),
    )
    no_delete = models.BooleanField(_("Keep Source Data"))
    sleep = models.IntegerField(_("Sleep Seconds After Each Archive Batch"), default=1)
    status = models.IntegerField(
        _("Review Status"), choices=WorkflowStatus.choices, blank=True, default=1
    )
    state = models.BooleanField(_("Enabled"), default=True)
    user_name = models.CharField(_("Requester"), max_length=30, blank=True, default="")
    user_display = models.CharField(
        _("Requester Display Name"), max_length=50, blank=True, default=""
    )
    create_time = models.DateTimeField(_("Created At"), auto_now_add=True)
    last_archive_time = models.DateTimeField(_("Last Archive Time"), blank=True, null=True)
    sys_time = models.DateTimeField(_("System Updated At"), auto_now=True)

    class Meta:
        managed = True
        db_table = "archive_config"
        verbose_name = _("Archive Configuration")
        verbose_name_plural = _("Archive Configuration")


class ArchiveLog(models.Model):
    """
    归档日志表
    """

    archive = models.ForeignKey(ArchiveConfig, on_delete=models.CASCADE)
    cmd = models.CharField(_("Archive Command"), max_length=2000)
    condition = models.CharField(_("Archive Condition (WHERE clause)"), max_length=1000)
    mode = models.CharField(
        _("Archive Mode"),
        max_length=10,
        choices=(("file", _("File")), ("dest", _("Another Instance")), ("purge", _("Delete Directly"))),
    )
    no_delete = models.BooleanField(_("Keep Source Data"))
    sleep = models.IntegerField(_("Sleep Seconds After Each Archive Batch"), default=0)
    select_cnt = models.IntegerField(_("Selected Rows"))
    insert_cnt = models.IntegerField(_("Inserted Rows"))
    delete_cnt = models.IntegerField(_("Deleted Rows"))
    statistics = models.TextField(_("Archive Statistics Log"))
    success = models.BooleanField(_("Archived Successfully"))
    error_info = models.TextField(_("Error Message"))
    start_time = models.DateTimeField(_("Start Time"))
    end_time = models.DateTimeField(_("Finished At"))
    sys_time = models.DateTimeField(_("System Updated At"), auto_now=True)

    class Meta:
        managed = True
        db_table = "archive_log"
        verbose_name = _("Archive Log")
        verbose_name_plural = _("Archive Log")


class Config(models.Model):
    """
    配置信息表
    """

    item = models.CharField(_("Config Item"), max_length=100, unique=True)
    value = fields.EncryptedCharField(verbose_name=_("Config Value"), max_length=500)
    description = models.CharField(_("Description"), max_length=200, default="", blank=True)

    class Meta:
        managed = True
        db_table = "sql_config"
        verbose_name = _("System Configuration")
        verbose_name_plural = _("System Configuration")


# 云服务认证信息配置
class CloudAccessKey(models.Model):
    cloud_type_choices = (("aliyun", "aliyun"),)

    type = models.CharField(max_length=20, default="", choices=cloud_type_choices)
    key_id = models.CharField(max_length=200)
    key_secret = models.CharField(max_length=200)
    remark = models.CharField(max_length=50, default="", blank=True)

    def __init__(self, *args, **kwargs):
        self.c = Crypto()
        super().__init__(*args, **kwargs)

    @property
    def raw_key_id(self):
        """返回明文信息"""
        return self.c.decrypt(self.key_id)

    @property
    def raw_key_secret(self):
        """返回明文信息"""
        return self.c.decrypt(self.key_secret)

    def save(self, *args, **kwargs):
        self.key_id = self.c.encrypt(self.key_id)
        self.key_secret = self.c.encrypt(self.key_secret)
        super(CloudAccessKey, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.type}({self.remark})"

    class Meta:
        managed = True
        db_table = "cloud_access_key"
        verbose_name = _("Cloud Access Credentials")
        verbose_name_plural = _("Cloud Access Credentials")


class AliyunRdsConfig(models.Model):
    """
    阿里云rds配置信息
    """

    instance = models.OneToOneField(Instance, on_delete=models.CASCADE)
    rds_dbinstanceid = models.CharField(_("Alibaba Cloud RDS Instance ID"), max_length=100)
    ak = models.ForeignKey(
        CloudAccessKey, verbose_name=_("AK Configuration for the RDS Instance"), on_delete=models.CASCADE
    )
    is_enable = models.BooleanField(_("Enabled"), default=False)

    def __int__(self):
        return self.rds_dbinstanceid

    class Meta:
        managed = True
        db_table = "aliyun_rds_config"
        verbose_name = _("Alibaba Cloud RDS Configuration")
        verbose_name_plural = _("Alibaba Cloud RDS Configuration")


class Permission(models.Model):
    """
    自定义业务权限
    """

    class Meta:
        managed = True
        permissions = (
            ("menu_dashboard", _("Dashboard Menu")),
            ("menu_sqlcheck", _("SQL Review Menu")),
            ("menu_sqlworkflow", _("SQL Deployment Menu")),
            ("menu_sqlanalyze", _("SQL Analysis Menu")),
            ("menu_query", _("SQL Query Menu")),
            ("menu_sqlquery", _("Online Query Menu")),
            ("menu_queryapplylist", _("Privilege Management Menu")),
            ("menu_sqloptimize", _("SQL Optimization Menu")),
            ("menu_sqladvisor", _("Optimization Tools Menu")),
            ("menu_slowquery", _("Slow Query Log Menu")),
            ("menu_instance", _("Instance Management Menu")),
            ("menu_instance_list", _("Instance List Menu")),
            ("menu_dbdiagnostic", _("Session Management Menu")),
            ("menu_database", _("Database Management Menu")),
            ("menu_instance_account", _("Instance Account Management Menu")),
            ("menu_param", _("Parameter Configuration Menu")),
            ("menu_param_compare", _("Parameter Comparison Menu")),
            ("menu_data_dictionary", _("Data Dictionary Menu")),
            ("menu_tools", _("Tools & Plugins Menu")),
            ("menu_archive", _("Data Archive Menu")),
            ("menu_my2sql", _("My2SQL Menu")),
            ("menu_schemasync", _("SchemaSync Menu")),
            ("menu_system", _("System Management Menu")),
            ("menu_document", _("Documentation Menu")),
            ("menu_openapi", _("OpenAPI Menu")),
            ("sql_submit", _("Submit SQL Deployment Request")),
            ("sql_review", _("Review SQL Deployment Request")),
            ("sql_execute_for_resource_group", _("Execute SQL Deployment Request (Resource Group Scope)")),
            ("sql_execute", _("Execute SQL Deployment Request (Own Requests Only)")),
            ("sql_analyze", _("Run SQL Analysis")),
            ("optimize_sqladvisor", _("Run SQLAdvisor")),
            ("optimize_sqltuning", _("Run SQLTuning")),
            ("optimize_soar", _("Run SOAR")),
            ("query_applypriv", _("Submit Query Privilege Request")),
            ("query_mgtpriv", _("Manage Query Privileges")),
            ("query_review", _("Review Query Privilege Request")),
            ("query_submit", _("Submit SQL Query")),
            ("query_all_instances", _("Can Query All Instances")),
            ("query_resource_group_instance", _("Can Query All Instances in the Resource Group")),
            ("process_view", _("View Sessions")),
            ("process_kill", _("Kill Sessions")),
            ("tablespace_view", _("View Tablespace")),
            ("trx_view", _("View Transactions")),
            ("trxandlocks_view", _("View Locks")),
            ("instance_account_manage", _("Manage Instance Accounts")),
            ("param_view", _("View Instance Parameters")),
            ("param_edit", _("Modify Instance Parameters")),
            ("data_dictionary_export", _("Export Data Dictionary")),
            ("archive_apply", _("Submit Archive Request")),
            ("archive_review", _("Review Archive Request")),
            ("archive_mgt", _("Manage Archive Requests")),
            ("audit_user", _("Audit Permission")),
            ("query_download", _("Online Query Download Permission")),
            ("offline_download", _("Offline Download Permission")),
            ("menu_sqlexportworkflow", _("Data Export Menu")),
            ("sqlexport_submit", _("Submit Data Export")),
        )


class SlowQuery(models.Model):
    """
    SlowQuery
    """

    checksum = models.CharField(max_length=32, primary_key=True)
    fingerprint = models.TextField()
    sample = models.TextField()
    first_seen = models.DateTimeField(blank=True, null=True)
    last_seen = models.DateTimeField(blank=True, null=True, db_index=True)
    reviewed_by = models.CharField(max_length=20, blank=True, null=True)
    reviewed_on = models.DateTimeField(blank=True, null=True)
    comments = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "mysql_slow_query_review"
        verbose_name = _("Slow Query Statistics")
        verbose_name_plural = _("Slow Query Statistics")


class SlowQueryHistory(models.Model):
    """
    SlowQueryHistory
    """

    hostname_max = models.CharField(max_length=64, null=False)
    client_max = models.CharField(max_length=64, null=True)
    user_max = models.CharField(max_length=64, null=False)
    db_max = models.CharField(max_length=64, null=True, default=None)
    bytes_max = models.CharField(max_length=64, null=True)
    checksum = models.ForeignKey(
        SlowQuery,
        db_constraint=False,
        to_field="checksum",
        db_column="checksum",
        on_delete=models.CASCADE,
    )
    sample = models.TextField()
    ts_min = models.DateTimeField(db_index=True)
    ts_max = models.DateTimeField()
    ts_cnt = models.FloatField(blank=True, null=True)
    query_time_sum = models.FloatField(
        db_column="Query_time_sum", blank=True, null=True
    )
    query_time_min = models.FloatField(
        db_column="Query_time_min", blank=True, null=True
    )
    query_time_max = models.FloatField(
        db_column="Query_time_max", blank=True, null=True
    )
    query_time_pct_95 = models.FloatField(
        db_column="Query_time_pct_95", blank=True, null=True
    )
    query_time_stddev = models.FloatField(
        db_column="Query_time_stddev", blank=True, null=True
    )
    query_time_median = models.FloatField(
        db_column="Query_time_median", blank=True, null=True
    )
    lock_time_sum = models.FloatField(db_column="Lock_time_sum", blank=True, null=True)
    lock_time_min = models.FloatField(db_column="Lock_time_min", blank=True, null=True)
    lock_time_max = models.FloatField(db_column="Lock_time_max", blank=True, null=True)
    lock_time_pct_95 = models.FloatField(
        db_column="Lock_time_pct_95", blank=True, null=True
    )
    lock_time_stddev = models.FloatField(
        db_column="Lock_time_stddev", blank=True, null=True
    )
    lock_time_median = models.FloatField(
        db_column="Lock_time_median", blank=True, null=True
    )
    rows_sent_sum = models.FloatField(db_column="Rows_sent_sum", blank=True, null=True)
    rows_sent_min = models.FloatField(db_column="Rows_sent_min", blank=True, null=True)
    rows_sent_max = models.FloatField(db_column="Rows_sent_max", blank=True, null=True)
    rows_sent_pct_95 = models.FloatField(
        db_column="Rows_sent_pct_95", blank=True, null=True
    )
    rows_sent_stddev = models.FloatField(
        db_column="Rows_sent_stddev", blank=True, null=True
    )
    rows_sent_median = models.FloatField(
        db_column="Rows_sent_median", blank=True, null=True
    )
    rows_examined_sum = models.FloatField(
        db_column="Rows_examined_sum", blank=True, null=True
    )
    rows_examined_min = models.FloatField(
        db_column="Rows_examined_min", blank=True, null=True
    )
    rows_examined_max = models.FloatField(
        db_column="Rows_examined_max", blank=True, null=True
    )
    rows_examined_pct_95 = models.FloatField(
        db_column="Rows_examined_pct_95", blank=True, null=True
    )
    rows_examined_stddev = models.FloatField(
        db_column="Rows_examined_stddev", blank=True, null=True
    )
    rows_examined_median = models.FloatField(
        db_column="Rows_examined_median", blank=True, null=True
    )
    rows_affected_sum = models.FloatField(
        db_column="Rows_affected_sum", blank=True, null=True
    )
    rows_affected_min = models.FloatField(
        db_column="Rows_affected_min", blank=True, null=True
    )
    rows_affected_max = models.FloatField(
        db_column="Rows_affected_max", blank=True, null=True
    )
    rows_affected_pct_95 = models.FloatField(
        db_column="Rows_affected_pct_95", blank=True, null=True
    )
    rows_affected_stddev = models.FloatField(
        db_column="Rows_affected_stddev", blank=True, null=True
    )
    rows_affected_median = models.FloatField(
        db_column="Rows_affected_median", blank=True, null=True
    )
    rows_read_sum = models.FloatField(db_column="Rows_read_sum", blank=True, null=True)
    rows_read_min = models.FloatField(db_column="Rows_read_min", blank=True, null=True)
    rows_read_max = models.FloatField(db_column="Rows_read_max", blank=True, null=True)
    rows_read_pct_95 = models.FloatField(
        db_column="Rows_read_pct_95", blank=True, null=True
    )
    rows_read_stddev = models.FloatField(
        db_column="Rows_read_stddev", blank=True, null=True
    )
    rows_read_median = models.FloatField(
        db_column="Rows_read_median", blank=True, null=True
    )
    merge_passes_sum = models.FloatField(
        db_column="Merge_passes_sum", blank=True, null=True
    )
    merge_passes_min = models.FloatField(
        db_column="Merge_passes_min", blank=True, null=True
    )
    merge_passes_max = models.FloatField(
        db_column="Merge_passes_max", blank=True, null=True
    )
    merge_passes_pct_95 = models.FloatField(
        db_column="Merge_passes_pct_95", blank=True, null=True
    )
    merge_passes_stddev = models.FloatField(
        db_column="Merge_passes_stddev", blank=True, null=True
    )
    merge_passes_median = models.FloatField(
        db_column="Merge_passes_median", blank=True, null=True
    )
    innodb_io_r_ops_min = models.FloatField(
        db_column="InnoDB_IO_r_ops_min", blank=True, null=True
    )
    innodb_io_r_ops_max = models.FloatField(
        db_column="InnoDB_IO_r_ops_max", blank=True, null=True
    )
    innodb_io_r_ops_pct_95 = models.FloatField(
        db_column="InnoDB_IO_r_ops_pct_95", blank=True, null=True
    )
    innodb_io_r_ops_stddev = models.FloatField(
        db_column="InnoDB_IO_r_ops_stddev", blank=True, null=True
    )
    innodb_io_r_ops_median = models.FloatField(
        db_column="InnoDB_IO_r_ops_median", blank=True, null=True
    )
    innodb_io_r_bytes_min = models.FloatField(
        db_column="InnoDB_IO_r_bytes_min", blank=True, null=True
    )
    innodb_io_r_bytes_max = models.FloatField(
        db_column="InnoDB_IO_r_bytes_max", blank=True, null=True
    )
    innodb_io_r_bytes_pct_95 = models.FloatField(
        db_column="InnoDB_IO_r_bytes_pct_95", blank=True, null=True
    )
    innodb_io_r_bytes_stddev = models.FloatField(
        db_column="InnoDB_IO_r_bytes_stddev", blank=True, null=True
    )
    innodb_io_r_bytes_median = models.FloatField(
        db_column="InnoDB_IO_r_bytes_median", blank=True, null=True
    )
    innodb_io_r_wait_min = models.FloatField(
        db_column="InnoDB_IO_r_wait_min", blank=True, null=True
    )
    innodb_io_r_wait_max = models.FloatField(
        db_column="InnoDB_IO_r_wait_max", blank=True, null=True
    )
    innodb_io_r_wait_pct_95 = models.FloatField(
        db_column="InnoDB_IO_r_wait_pct_95", blank=True, null=True
    )
    innodb_io_r_wait_stddev = models.FloatField(
        db_column="InnoDB_IO_r_wait_stddev", blank=True, null=True
    )
    innodb_io_r_wait_median = models.FloatField(
        db_column="InnoDB_IO_r_wait_median", blank=True, null=True
    )
    innodb_rec_lock_wait_min = models.FloatField(
        db_column="InnoDB_rec_lock_wait_min", blank=True, null=True
    )
    innodb_rec_lock_wait_max = models.FloatField(
        db_column="InnoDB_rec_lock_wait_max", blank=True, null=True
    )
    innodb_rec_lock_wait_pct_95 = models.FloatField(
        db_column="InnoDB_rec_lock_wait_pct_95", blank=True, null=True
    )
    innodb_rec_lock_wait_stddev = models.FloatField(
        db_column="InnoDB_rec_lock_wait_stddev", blank=True, null=True
    )
    innodb_rec_lock_wait_median = models.FloatField(
        db_column="InnoDB_rec_lock_wait_median", blank=True, null=True
    )
    innodb_queue_wait_min = models.FloatField(
        db_column="InnoDB_queue_wait_min", blank=True, null=True
    )
    innodb_queue_wait_max = models.FloatField(
        db_column="InnoDB_queue_wait_max", blank=True, null=True
    )
    innodb_queue_wait_pct_95 = models.FloatField(
        db_column="InnoDB_queue_wait_pct_95", blank=True, null=True
    )
    innodb_queue_wait_stddev = models.FloatField(
        db_column="InnoDB_queue_wait_stddev", blank=True, null=True
    )
    innodb_queue_wait_median = models.FloatField(
        db_column="InnoDB_queue_wait_median", blank=True, null=True
    )
    innodb_pages_distinct_min = models.FloatField(
        db_column="InnoDB_pages_distinct_min", blank=True, null=True
    )
    innodb_pages_distinct_max = models.FloatField(
        db_column="InnoDB_pages_distinct_max", blank=True, null=True
    )
    innodb_pages_distinct_pct_95 = models.FloatField(
        db_column="InnoDB_pages_distinct_pct_95", blank=True, null=True
    )
    innodb_pages_distinct_stddev = models.FloatField(
        db_column="InnoDB_pages_distinct_stddev", blank=True, null=True
    )
    innodb_pages_distinct_median = models.FloatField(
        db_column="InnoDB_pages_distinct_median", blank=True, null=True
    )
    qc_hit_cnt = models.FloatField(db_column="QC_Hit_cnt", blank=True, null=True)
    qc_hit_sum = models.FloatField(db_column="QC_Hit_sum", blank=True, null=True)
    full_scan_cnt = models.FloatField(db_column="Full_scan_cnt", blank=True, null=True)
    full_scan_sum = models.FloatField(db_column="Full_scan_sum", blank=True, null=True)
    full_join_cnt = models.FloatField(db_column="Full_join_cnt", blank=True, null=True)
    full_join_sum = models.FloatField(db_column="Full_join_sum", blank=True, null=True)
    tmp_table_cnt = models.FloatField(db_column="Tmp_table_cnt", blank=True, null=True)
    tmp_table_sum = models.FloatField(db_column="Tmp_table_sum", blank=True, null=True)
    tmp_table_on_disk_cnt = models.FloatField(
        db_column="Tmp_table_on_disk_cnt", blank=True, null=True
    )
    tmp_table_on_disk_sum = models.FloatField(
        db_column="Tmp_table_on_disk_sum", blank=True, null=True
    )
    filesort_cnt = models.FloatField(db_column="Filesort_cnt", blank=True, null=True)
    filesort_sum = models.FloatField(db_column="Filesort_sum", blank=True, null=True)
    filesort_on_disk_cnt = models.FloatField(
        db_column="Filesort_on_disk_cnt", blank=True, null=True
    )
    filesort_on_disk_sum = models.FloatField(
        db_column="Filesort_on_disk_sum", blank=True, null=True
    )

    class Meta:
        managed = False
        db_table = "mysql_slow_query_review_history"
        unique_together = ("checksum", "ts_min", "ts_max")
        indexes = [
            models.Index(fields=["hostname_max", "ts_min"]),
        ]
        verbose_name = _("Slow Query Details")
        verbose_name_plural = _("Slow Query Details")


class RedisSlowQuery(models.Model):
    """
    Redis慢日志统计
    """

    checksum = models.CharField(max_length=32, primary_key=True)
    fingerprint = models.TextField()
    sample = models.TextField()
    first_seen = models.DateTimeField(blank=True, null=True)
    last_seen = models.DateTimeField(blank=True, null=True, db_index=True)

    class Meta:
        managed = False
        db_table = "redis_slow_query_review"
        verbose_name = _("Redis Slow Query Statistics")
        verbose_name_plural = _("Redis Slow Query Statistics")


class RedisSlowQueryHistory(models.Model):
    """
    Redis慢日志明细
    """

    id = models.AutoField(primary_key=True)
    checksum = models.ForeignKey(
        RedisSlowQuery,
        db_constraint=False,
        to_field="checksum",
        db_column="checksum",
        on_delete=models.CASCADE,
    )
    sample = models.TextField()
    hostname = models.CharField(max_length=64)
    ts_min = models.DateTimeField(db_index=True)
    ts_max = models.DateTimeField()
    cnt = models.IntegerField(default=0)
    duration_sum = models.BigIntegerField(blank=True, null=True)
    duration_min = models.BigIntegerField(blank=True, null=True)
    duration_max = models.BigIntegerField(blank=True, null=True)
    duration_pct_95 = models.BigIntegerField(blank=True, null=True)
    duration_stddev = models.DecimalField(
        max_digits=20, decimal_places=4, blank=True, null=True
    )
    duration_median = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "redis_slow_query_review_history"
        unique_together = ("checksum", "hostname", "ts_min", "ts_max")
        indexes = [
            models.Index(fields=["hostname", "ts_min"]),
        ]
        verbose_name = _("Redis Slow Query Details")
        verbose_name_plural = _("Redis Slow Query Details")


class AuditEntry(models.Model):
    """
    登录审计日志
    """

    user_id = models.IntegerField(_("User ID"))
    user_name = models.CharField(_("User Name"), max_length=30, null=True)
    user_display = models.CharField(_("User Display Name"), max_length=50, null=True)
    action = models.CharField(_("Action"), max_length=255)
    extra_info = models.TextField(_("Extra Info"), null=True)
    action_time = models.DateTimeField(_("Action Time"), auto_now_add=True)

    class Meta:
        managed = True
        db_table = "audit_log"
        verbose_name = _("Audit Log")
        verbose_name_plural = _("Audit Log")

    def __unicode__(self):
        return "{0} - {1} - {2} - {3} - {4}".format(
            self.user_id, self.user_name, self.extra_info, self.action, self.action_time
        )

    def __str__(self):
        return "{0} - {1} - {2} - {3} - {4}".format(
            self.user_id, self.user_name, self.extra_info, self.action, self.action_time
        )
