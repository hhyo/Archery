# -*- coding: UTF-8 -*- 
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

# Register your models here.
from .models import users, master_config, workflow


class master_configAdmin(admin.ModelAdmin):
    list_display = ('id', 'cluster_name', 'master_host', 'master_port', 'master_user', 'master_password', 'create_time', 'update_time')
    search_fields = ['id', 'cluster_name', 'master_host', 'master_port', 'master_user', 'master_password', 'create_time', 'update_time']

class workflowAdmin(admin.ModelAdmin):
    list_display = ('id','workflow_name', 'engineer', 'review_man', 'create_time', 'finish_time', 'status', 'is_backup', 'review_content', 'cluster_name', 'reviewok_time', 'sql_content', 'execute_result')
    search_fields = ['id','workflow_name', 'engineer', 'review_man', 'sql_content']

#创建用户表单重新定义，继承自UserCreationForm
class usersCreationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super(usersCreationForm, self).__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.fields['display'].required = True
        self.fields['role'].required = True

#编辑用户表单重新定义，继承自UserChangeForm
class usersChangeForm(UserChangeForm): 
    def __init__(self, *args, **kwargs):
        super(usersChangeForm, self).__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.fields['display'].required = True        
        self.fields['role'].required = True        

class usersAdmin(UserAdmin):
    def __init__(self, *args, **kwargs):
        super(usersAdmin, self).__init__(*args, **kwargs)
        self.list_display = ('id', 'username', 'display', 'role', 'email', 'password', 'is_superuser', 'is_staff')
        self.search_fields = ('id', 'username', 'display', 'role', 'email')
        self.form = usersChangeForm
        self.add_form = usersCreationForm
        #以上的属性都可以在django源码的UserAdmin类中找到，我们做以覆盖

    def changelist_view(self, request, extra_context=None):  
        #这个方法在源码的admin/options.py文件的ModelAdmin这个类中定义，我们要重新定义它，以达到不同权限的用户，返回的表单内容不同
        if request.user.is_superuser:
            #此字段定义UserChangeForm表单中的具体显示内容，并可以分类显示
            self.fieldsets = (
                              (('认证信息'), {'fields': ('username', 'password')}),
                              (('个人信息'), {'fields': ('display', 'role', 'email')}),
                              (('权限信息'), {'fields': ('is_active', 'is_staff')}),
                              #(('Important dates'), {'fields': ('last_login', 'date_joined')}),
                              )
            #此字段定义UserCreationForm表单中的具体显示内容
            self.add_fieldsets = ((None, {'classes': ('wide',),
                                          'fields': ('username', 'display', 'role', 'email', 'password1', 'password2'),
                                          }),
                                  )
        return super(usersAdmin, self).changelist_view(request, extra_context)


admin.site.register(users, usersAdmin)
admin.site.register(master_config, master_configAdmin)
admin.site.register(workflow, workflowAdmin)
