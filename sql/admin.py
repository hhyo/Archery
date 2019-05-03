# -*- coding: UTF-8 -*-
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

# Register your models here.
from .models import Users, Instance, SqlWorkflow, SqlWorkflowContent, QueryLog, DataMaskingColumns, DataMaskingRules, \
    AliyunAccessKey, AliyunRdsConfig, ResourceGroup, ResourceGroupRelations, QueryPrivilegesApply, QueryPrivileges, \
    WorkflowAudit, WorkflowLog, ParamTemplate, ParamHistory, InstanceTag, InstanceTagRelations


# 用户管理
@admin.register(Users)
class UsersAdmin(UserAdmin):
    list_display = ('id', 'username', 'display', 'email', 'is_superuser', 'is_staff', 'is_active')
    search_fields = ('id', 'username', 'display', 'email')
    list_display_links = ('id', 'username',)
    ordering = ('id',)
    # 编辑页显示内容
    fieldsets = (
        (('认证信息',), {'fields': ('username', 'password')}),
        (('个人信息',), {'fields': ('display', 'email')}),
        (('权限信息',), {'fields': ('is_superuser', 'is_active', 'is_staff', 'groups', 'user_permissions')}),
        (('其他信息',), {'fields': ('last_login', 'date_joined')}),
    )
    # 添加页显示内容
    add_fieldsets = (None, {'fields': ('username', 'display', 'email', 'password1', 'password2'), }),


# 资源组管理
@admin.register(ResourceGroup)
class ResourceGroupAdmin(admin.ModelAdmin):
    list_display = ('group_id', 'group_name', 'ding_webhook', 'is_deleted')
    exclude = ('group_parent_id', 'group_sort', 'group_level',)


# 资源组关系管理
@admin.register(ResourceGroupRelations)
class ResourceGroupRelationsAdmin(admin.ModelAdmin):
    list_display = ('object_type', 'object_id', 'object_name', 'group_id', 'group_name', 'create_time')


# 实例标签配置
@admin.register(InstanceTag)
class InstanceTagAdmin(admin.ModelAdmin):
    list_display = ('id', 'tag_code', 'tag_name', 'active', 'create_time')
    list_display_links = ('id', 'tag_code',)


# 实例标签关系配置
@admin.register(InstanceTagRelations)
class InstanceTagRelationsAdmin(admin.ModelAdmin):
    list_display = ('instance', 'instance_tag', 'active', 'create_time')
    list_filter = ('instance', 'instance_tag', 'active')


# 实例管理
@admin.register(Instance)
class InstanceAdmin(admin.ModelAdmin):
    list_display = ('id', 'instance_name', 'db_type', 'type', 'host', 'port', 'user', 'create_time')
    search_fields = ['instance_name', 'host', 'port', 'user']
    list_filter = ('db_type', 'type')

    # 阿里云实例关系配置
    class AliRdsConfigInline(admin.TabularInline):
        model = AliyunRdsConfig

    # 实例标签关系配置
    class InstanceTagRelationsInline(admin.TabularInline):
        model = InstanceTagRelations

    inlines = [InstanceTagRelationsInline, AliRdsConfigInline]


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
    search_fields = ['user_display', 'instance__instance_name', 'db_list', 'tb_list']
    list_filter = ('user_display', 'group_name', 'instance')


# 脱敏字段页面定义
@admin.register(DataMaskingColumns)
class DataMaskingColumnsAdmin(admin.ModelAdmin):
    list_display = (
        'column_id', 'rule_type', 'active', 'instance', 'table_schema', 'table_name', 'column_name',
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


# 实例参数配置表
@admin.register(ParamTemplate)
class ParamTemplateAdmin(admin.ModelAdmin):
    list_display = ('db_type', 'variable_name', 'default_value', 'editable', 'valid_values')
    search_fields = ('variable_name',)
    list_filter = ('db_type', 'editable')


# 实例参数修改历史
@admin.register(ParamHistory)
class ParamHistoryAdmin(admin.ModelAdmin):
    list_display = ('instance', 'variable_name', 'old_var', 'new_var', 'user_display', 'create_time')
    search_fields = ('variable_name',)
    list_filter = ('instance', 'user_display')


# 阿里云的认证信息
@admin.register(AliyunAccessKey)
class AliAccessKeyAdmin(admin.ModelAdmin):
    list_display = ('ak', 'secret', 'is_enable', 'remark',)
    search_fields = ['ak']


# 阿里云实例配置信息
@admin.register(AliyunRdsConfig)
class AliRdsConfigAdmin(admin.ModelAdmin):
    list_display = ('instance', 'rds_dbinstanceid', 'is_enable')
    search_fields = ['instance__instance_name', 'rds_dbinstanceid']
