# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='master_config',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('cluster_name', models.CharField(verbose_name='集群名称', max_length=50)),
                ('master_host', models.CharField(verbose_name='主库地址', max_length=200)),
                ('master_port', models.IntegerField(default=3306, verbose_name='主库端口')),
                ('master_user', models.CharField(verbose_name='登录主库的用户名', max_length=50)),
                ('master_password', models.CharField(verbose_name='登录主库的密码', max_length=50)),
                ('create_time', models.DateTimeField(verbose_name='创建时间', auto_now_add=True)),
                ('update_time', models.DateTimeField(verbose_name='更新时间', auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='users',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('username', models.CharField(verbose_name='用户名', max_length=50)),
                ('password', models.CharField(verbose_name='密码', max_length=50)),
                ('display', models.CharField(verbose_name='显示的中文名', max_length=50)),
                ('role', models.CharField(default='工程师', verbose_name='角色', choices=[('工程师', '工程师'), ('审核人', '审核人')], max_length=20)),
            ],
        ),
        migrations.CreateModel(
            name='workflow',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('workflow_name', models.CharField(verbose_name='工单内容', max_length=50)),
                ('engineer', models.CharField(verbose_name='发起人', max_length=50)),
                ('review_man', models.CharField(verbose_name='审核人', max_length=50)),
                ('create_time', models.DateTimeField(verbose_name='创建时间', auto_now_add=True)),
                ('finish_time', models.DateTimeField()),
                ('status', models.CharField(choices=[('已正常结束', '已正常结束'), ('人工终止流程', '人工终止流程'), ('等待审核人审核', '等待审核人审核'), ('执行中', '执行中'), ('自动审核不通过', '自动审核不通过'), ('执行有异常', '执行有异常')], max_length=50)),
                ('is_backup', models.IntegerField(choices=[(0, 0), (1, 1)])),
                ('review_content', models.TextField()),
                ('cluster_name', models.CharField(max_length=50)),
                ('reviewok_time', models.DateTimeField()),
                ('sql_content', models.TextField()),
                ('execute_result', models.TextField()),
            ],
        ),
    ]
