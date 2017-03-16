# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.core.validators
import django.contrib.auth.models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0006_require_contenttypes_0002'),
    ]

    operations = [
        migrations.CreateModel(
            name='users',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('password', models.CharField(verbose_name='password', max_length=128)),
                ('last_login', models.DateTimeField(verbose_name='last login', null=True, blank=True)),
                ('is_superuser', models.BooleanField(verbose_name='superuser status', default=False, help_text='Designates that this user has all permissions without explicitly assigning them.')),
                ('username', models.CharField(verbose_name='username', validators=[django.core.validators.RegexValidator('^[\\w.@+-]+$', 'Enter a valid username. This value may contain only letters, numbers and @/./+/-/_ characters.', 'invalid')], error_messages={'unique': 'A user with that username already exists.'}, max_length=30, help_text='Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only.', unique=True)),
                ('first_name', models.CharField(verbose_name='first name', max_length=30, blank=True)),
                ('last_name', models.CharField(verbose_name='last name', max_length=30, blank=True)),
                ('email', models.EmailField(verbose_name='email address', max_length=254, blank=True)),
                ('is_staff', models.BooleanField(verbose_name='staff status', default=False, help_text='Designates whether the user can log into this admin site.')),
                ('is_active', models.BooleanField(verbose_name='active', default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.')),
                ('date_joined', models.DateTimeField(verbose_name='date joined', default=django.utils.timezone.now)),
                ('display', models.CharField(verbose_name='显示的中文名', max_length=50)),
                ('role', models.CharField(verbose_name='角色', default='工程师', max_length=20, choices=[('工程师', '工程师'), ('审核人', '审核人')])),
                ('groups', models.ManyToManyField(related_name='user_set', verbose_name='groups', to='auth.Group', help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_query_name='user', blank=True)),
                ('user_permissions', models.ManyToManyField(related_name='user_set', verbose_name='user permissions', to='auth.Permission', help_text='Specific permissions for this user.', related_query_name='user', blank=True)),
            ],
            options={
                'verbose_name': '用户配置',
                'verbose_name_plural': '用户配置',
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='master_config',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('cluster_name', models.CharField(verbose_name='集群名称', max_length=50)),
                ('master_host', models.CharField(verbose_name='主库地址', max_length=200)),
                ('master_port', models.IntegerField(verbose_name='主库端口', default=3306)),
                ('master_user', models.CharField(verbose_name='登录主库的用户名', max_length=50)),
                ('master_password', models.CharField(verbose_name='登录主库的密码', max_length=50)),
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(verbose_name='更新时间', auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='workflow',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('workflow_name', models.CharField(verbose_name='工单内容', max_length=50)),
                ('engineer', models.CharField(verbose_name='发起人', max_length=50)),
                ('review_man', models.CharField(verbose_name='审核人', max_length=50)),
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('finish_time', models.DateTimeField(verbose_name='结束时间', null=True, blank=True)),
                ('status', models.CharField(choices=[('已正常结束', '已正常结束'), ('人工终止流程', '人工终止流程'), ('自动审核中', '自动审核中'), ('等待审核人审核', '等待审核人审核'), ('执行中', '执行中'), ('自动审核不通过', '自动审核不通过'), ('执行有异常', '执行有异常')], max_length=50)),
                ('is_backup', models.CharField(verbose_name='是否备份', choices=[('否', '否'), ('是', '是')], max_length=20)),
                ('review_content', models.TextField(verbose_name='自动审核内容的JSON格式')),
                ('cluster_name', models.CharField(verbose_name='集群名称', max_length=50)),
                ('reviewok_time', models.DateTimeField(verbose_name='人工审核通过的时间', null=True, blank=True)),
                ('sql_content', models.TextField(verbose_name='具体sql内容')),
                ('execute_result', models.TextField(verbose_name='执行结果的JSON格式')),
            ],
        ),
    ]
