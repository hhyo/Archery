#coding=utf-8
from django.contrib import admin

# Register your models here.
from .models import users, master_config, workflow

class usersAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'display', 'role')
    search_fields = ['id', 'username', 'display', 'role']

class master_configAdmin(admin.ModelAdmin):
    list_display = ('id', 'cluster_name', 'master_host', 'master_port', 'master_user', 'master_password', 'create_time', 'update_time')
    search_fields = ['id', 'cluster_name', 'master_host', 'master_port', 'master_user', 'master_password', 'create_time', 'update_time']

class workflowAdmin(admin.ModelAdmin):
    list_display = ('id','workflow_name', 'engineer', 'review_man', 'create_time', 'finish_time', 'status', 'is_backup', 'review_content', 'cluster_name', 'reviewok_time', 'sql_content', 'execute_result')
    search_fields = ['id','workflow_name', 'engineer', 'review_man', 'create_time', 'finish_time', 'status', 'is_backup', 'review_content', 'cluster_name', 'reviewok_time', 'sql_content', 'execute_result']

admin.site.register(users, usersAdmin)
admin.site.register(master_config, master_configAdmin)
admin.site.register(workflow, workflowAdmin)
