# -*- coding: UTF-8 -*-
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

# Register your models here.
from django.forms import PasswordInput

from .models import Users, Instance, SqlWorkflow, SqlWorkflowContent, QueryLog, DataMaskingColumns, DataMaskingRules, \
    AliyunRdsConfig, CloudAccessKey, ResourceGroup, QueryPrivilegesApply, \
    QueryPrivileges, InstanceAccount, InstanceDatabase, ArchiveConfig, \
    WorkflowAudit, WorkflowLog, ParamTemplate, ParamHistory, InstanceTag, \
    Tunnel, AuditEntry, TwoFactorAuthConfig

from sql.form import TunnelForm, InstanceForm


# 用户管理
@admin.register(Users)
class UsersAdmin(UserAdmin):
    list_display = ('id', 'username', 'display', 'email', 'is_superuser', 'is_staff', 'is_active')
    search_fields = ('id', 'username', 'display', 'email')
    list_display_links = ('id', 'username',)
    ordering = ('id',)
    # 编辑页显示内容
    fieldsets = (
        ('认证信息', {'fields': ('username', 'password')}),
        ('个人信息', {'fields': ('display', 'email', 'ding_user_id', 'wx_user_id', 'feishu_open_id')}),
        ('权限信息', {'fields': ('is_superuser', 'is_active', 'is_staff', 'groups', 'user_permissions')}),
        ('资源组', {'fields': ('resource_group',)}),
        ('其他信息', {'fields': ('date_joined',)}),
    )
    # 添加页显示内容
    add_fieldsets = (
        ('认证信息', {'fields': ('username', 'password1', 'password2')}),
        ('个人信息', {'fields': ('display', 'email', 'ding_user_id', 'wx_user_id', 'feishu_open_id')}),
        ('权限信息', {'fields': ('is_superuser', 'is_active', 'is_staff', 'groups', 'user_permissions')}),
        ('资源组', {'fields': ('resource_group',)}),
    )
    filter_horizontal = ('groups', 'user_permissions', 'resource_group')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'resource_group')


# 用户2fa管理
@admin.register(TwoFactorAuthConfig)
class TwoFactorAuthConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'auth_type', 'secret_key', 'user_id')


# 资源组管理
@admin.register(ResourceGroup)
class ResourceGroupAdmin(admin.ModelAdmin):
    list_display = ('group_id', 'group_name', 'ding_webhook', 'feishu_webhook', 'qywx_webhook', 'is_deleted')
    exclude = ('group_parent_id', 'group_sort', 'group_level',)


# 实例标签配置
@admin.register(InstanceTag)
class InstanceTagAdmin(admin.ModelAdmin):
    list_display = ('id', 'tag_code', 'tag_name', 'active', 'create_time')
    list_display_links = ('id', 'tag_code',)
    fieldsets = (None, {'fields': ('tag_code', 'tag_name', 'active'), }),

    # 不支持修改标签代码
    def get_readonly_fields(self, request, obj=None):
        return ('tag_code',) if obj else ()


# 实例管理
@admin.register(Instance)
class InstanceAdmin(admin.ModelAdmin):
    form = InstanceForm
    list_display = ('id', 'instance_name', 'db_type', 'type', 'host', 'port', 'user', 'create_time')
    search_fields = ['instance_name', 'host', 'port', 'user']
    list_filter = ('db_type', 'type', 'instance_tag')

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'password':
            kwargs['widget'] = PasswordInput(render_value=True)
        return super(InstanceAdmin, self).formfield_for_dbfield(db_field, **kwargs)

    # 阿里云实例关系配置
    class AliRdsConfigInline(admin.TabularInline):
        model = AliyunRdsConfig

    # 实例资源组关联配置
    filter_horizontal = ('resource_group', 'instance_tag',)

    inlines = [AliRdsConfigInline]


# SSH隧道
@admin.register(Tunnel)
class TunnelAdmin(admin.ModelAdmin):
    list_display = ('id', 'tunnel_name', 'host', 'port', 'create_time')
    list_display_links = ('id', 'tunnel_name',)
    search_fields = ('id', 'tunnel_name')
    fieldsets = (
                    None,
                    {'fields': ('tunnel_name', 'host', 'port', 'user', 'password', 'pkey_path', 'pkey_password', 'pkey'), }),
    ordering = ('id',)
    # 添加页显示内容
    add_fieldsets = (
        ('隧道信息', {'fields': ('tunnel_name', 'host', 'port')}),
        ('连接信息', {'fields': ('user', 'password', 'pkey_path', 'pkey_password', 'pkey')}),
    )
    form = TunnelForm

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name in ['password', 'pkey_password']:
            kwargs['widget'] = PasswordInput(render_value=True)
        return super(TunnelAdmin, self).formfield_for_dbfield(db_field, **kwargs)

    # 不支持修改标签代码
    def get_readonly_fields(self, request, obj=None):
        return ('id',) if obj else ()


# SQL工单内容
class SqlWorkflowContentInline(admin.TabularInline):
    model = SqlWorkflowContent


# SQL工单
@admin.register(SqlWorkflow)
class SqlWorkflowAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'workflow_name', 'group_name', 'instance', 'engineer_display', 'create_time', 'status', 'is_backup')
    search_fields = ['id', 'workflow_name', 'engineer_display', 'sqlworkflowcontent__sql_content']
    list_filter = ('group_name', 'instance__instance_name', 'status', 'syntax_type',)
    list_display_links = ('id', 'workflow_name',)
    inlines = [SqlWorkflowContentInline]


# SQL查询日志
@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = (
        'instance_name', 'db_name', 'sqllog', 'effect_row', 'cost_time', 'user_display', 'create_time')
    search_fields = ['sqllog', 'user_display']
    list_filter = ('instance_name', 'db_name', 'user_display', 'priv_check', 'hit_rule', 'masking',)


# 查询权限列表
@admin.register(QueryPrivileges)
class QueryPrivilegesAdmin(admin.ModelAdmin):
    list_display = ('privilege_id', 'user_display', 'instance', 'db_name', 'table_name',
                    'valid_date', 'limit_num', 'create_time')
    search_fields = ['user_display', 'instance__instance_name']
    list_filter = ('user_display', 'instance', 'db_name', 'table_name',)


# 查询权限申请记录
@admin.register(QueryPrivilegesApply)
class QueryPrivilegesApplyAdmin(admin.ModelAdmin):
    list_display = ('apply_id', 'user_display', 'group_name', 'instance', 'valid_date', 'limit_num', 'create_time')
    search_fields = ['user_display', 'instance__instance_name', 'db_list', 'table_list']
    list_filter = ('user_display', 'group_name', 'instance')


# 脱敏字段页面定义
@admin.register(DataMaskingColumns)
class DataMaskingColumnsAdmin(admin.ModelAdmin):
    list_display = (
        'column_id', 'rule_type', 'active', 'instance', 'table_schema', 'table_name', 'column_name', 'column_comment',
        'create_time',)
    search_fields = ['table_name', 'column_name']
    list_filter = ('rule_type', 'active', 'instance__instance_name')


# 脱敏规则页面定义
@admin.register(DataMaskingRules)
class DataMaskingRulesAdmin(admin.ModelAdmin):
    list_display = (
        'rule_type', 'rule_regex', 'hide_group', 'rule_desc', 'sys_time',)


# 工作流审批列表
@admin.register(WorkflowAudit)
class WorkflowAuditAdmin(admin.ModelAdmin):
    list_display = (
        'workflow_title', 'group_name', 'workflow_type', 'current_status', 'create_user_display', 'create_time')
    search_fields = ['workflow_title', 'create_user_display']
    list_filter = ('create_user_display', 'group_name', 'workflow_type', 'current_status')


# 工作流日志表
@admin.register(WorkflowLog)
class WorkflowLogAdmin(admin.ModelAdmin):
    list_display = (
        'operation_type_desc', 'operation_info', 'operator_display', 'operation_time',)
    list_filter = ('operation_type_desc', 'operator_display')


# 实例数据库列表
@admin.register(InstanceDatabase)
class InstanceDatabaseAdmin(admin.ModelAdmin):
    list_display = ('db_name', 'owner_display', 'instance', 'remark')
    search_fields = ('db_name',)
    list_filter = ('instance', 'owner_display')
    list_display_links = ('db_name',)

    # 仅支持修改备注
    def get_readonly_fields(self, request, obj=None):
        return ('instance', 'owner', 'owner_display') if obj else ()


# 实例用户列表
@admin.register(InstanceAccount)
class InstanceAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'host', 'password', 'instance', 'remark')
    search_fields = ('user', 'host')
    list_filter = ('instance', 'host')
    list_display_links = ('user',)

    # 仅支持修改备注
    def get_readonly_fields(self, request, obj=None):
        return ('user', 'host', 'instance',) if obj else ()


# 实例参数配置表
@admin.register(ParamTemplate)
class ParamTemplateAdmin(admin.ModelAdmin):
    list_display = ('variable_name', 'db_type', 'default_value', 'editable', 'valid_values')
    search_fields = ('variable_name',)
    list_filter = ('db_type', 'editable')
    list_display_links = ('variable_name',)


# 实例参数修改历史
@admin.register(ParamHistory)
class ParamHistoryAdmin(admin.ModelAdmin):
    list_display = ('variable_name', 'instance', 'old_var', 'new_var', 'user_display', 'create_time')
    search_fields = ('variable_name',)
    list_filter = ('instance', 'user_display')


# 归档配置
@admin.register(ArchiveConfig)
class ArchiveConfigAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'src_instance', 'src_db_name', 'src_table_name',
        'dest_instance', 'dest_db_name', 'dest_table_name',
        'mode', 'no_delete', 'status', 'state', 'user_display', 'create_time', 'resource_group')
    search_fields = ('title', 'src_table_name')
    list_display_links = ('id', 'title')
    list_filter = ('src_instance', 'src_db_name', 'mode', 'no_delete', 'state')
    # 编辑页显示内容
    fields = ('title', 'resource_group', 'src_instance', 'src_db_name', 'src_table_name',
              'dest_instance', 'dest_db_name', 'dest_table_name',
              'mode', 'condition', 'sleep', 'no_delete', 'state', 'user_name', 'user_display')


# 云服务认证信息配置
@admin.register(CloudAccessKey)
class CloudAccessKeyAdmin(admin.ModelAdmin):
    list_display = ('type', 'key_id', 'key_secret', 'remark')


# 登录审计日志
@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'user_name', 'user_display', 'action', 'extra_info', 'action_time')
    list_filter = ('user_id', 'user_name', 'user_display', 'action', 'extra_info')

