# -*- coding: UTF-8 -*-
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

# Register your models here.
from .models import Users, MasterConfig, SlaveConfig, SqlWorkflow, \
    DataMaskingColumns, DataMaskingRules, AliyunAccessKey, AliyunRdsConfig, SqlGroup, GroupRelations


# 用户管理
@admin.register(Users)
class UsersAdmin(UserAdmin):
    def __init__(self, *args, **kwargs):
        super(UserAdmin, self).__init__(*args, **kwargs)
        self.list_display = ('id', 'username', 'display', 'email', 'is_superuser', 'is_staff', 'is_active')
        self.search_fields = ('id', 'username', 'display', 'email')

    def changelist_view(self, request, extra_context=None):
        # 这个方法在源码的admin/options.py文件的ModelAdmin这个类中定义，我们要重新定义它，以达到不同权限的用户，返回的表单内容不同
        if request.user.is_superuser:
            # 此字段定义UserChangeForm表单中的具体显示内容，并可以分类显示
            self.fieldsets = (
                (('认证信息'), {'fields': ('username', 'password')}),
                (('个人信息'), {'fields': ('display', 'email')}),
                (('权限信息'), {'fields': ('is_superuser', 'is_active', 'is_staff', 'groups', 'user_permissions')}),
                (('其他信息'), {'fields': ('last_login', 'date_joined')}),
            )
            # 此字段定义UserCreationForm表单中的具体显示内容
            self.add_fieldsets = (
                (None, {'fields': ('username', 'display', 'email', 'password1', 'password2'), }),
            )
        return super(UserAdmin, self).changelist_view(request, extra_context)


# 组管理
@admin.register(SqlGroup)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('group_id', 'group_name', 'ding_webhook', 'is_deleted')
    exclude = ('group_parent_id', 'group_sort', 'group_level',)


# 组关系管理
@admin.register(GroupRelations)
class GroupRelationsAdmin(admin.ModelAdmin):
    list_display = ('object_type', 'object_id', 'object_name', 'group_id', 'group_name', 'create_time')


# 主库配置管理
@admin.register(MasterConfig)
class MasterConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'cluster_name', 'master_host', 'master_port', 'master_user', 'create_time')
    search_fields = ['id', 'cluster_name', 'master_host', 'master_port', 'master_user', 'master_password',
                     'create_time', 'update_time']


# 工单管理
@admin.register(SqlWorkflow)
class SqlWorkflowAdmin(admin.ModelAdmin):
    list_display = ('id', 'workflow_name', 'group_id', 'cluster_name', 'engineer', 'create_time', 'status', 'is_backup')
    search_fields = ['id', 'workflow_name', 'engineer', 'review_man', 'sql_content']


# 查询从库配置
@admin.register(SlaveConfig)
class SlaveConfigAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'cluster_name', 'slave_host', 'slave_port', 'slave_user', 'create_time', 'update_time')
    search_fields = ['id', 'cluster_name', 'slave_host', 'slave_port', 'slave_user', 'slave_password', ]


# 脱敏字段页面定义
@admin.register(DataMaskingColumns)
class DataMaskingColumnsAdmin(admin.ModelAdmin):
    list_display = (
        'column_id', 'rule_type', 'active', 'cluster_name', 'table_schema', 'table_name', 'column_name',
        'create_time',)


# 脱敏规则页面定义
@admin.register(DataMaskingRules)
class DataMaskingRulesAdmin(admin.ModelAdmin):
    list_display = (
        'rule_type', 'rule_regex', 'hide_group', 'rule_desc', 'sys_time',)


# 阿里云的认证信息
@admin.register(AliyunAccessKey)
class AliAccessKeyAdmin(admin.ModelAdmin):
    list_display = ('ak', 'secret', 'is_enable', 'remark',)


# 阿里云实例配置信息
@admin.register(AliyunRdsConfig)
class AliRdsConfigAdmin(admin.ModelAdmin):
    list_display = ('cluster_name', 'rds_dbinstanceid',)
