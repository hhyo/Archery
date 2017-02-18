# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sql', '0002_auto_20170210_1640'),
    ]

    operations = [
        migrations.AlterField(
            model_name='master_config',
            name='cluster_name',
            field=models.CharField(max_length=50, verbose_name='集群名称'),
        ),
        migrations.AlterField(
            model_name='master_config',
            name='create_time',
            field=models.DateTimeField(verbose_name='创建时间', auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='master_config',
            name='master_host',
            field=models.CharField(max_length=200, verbose_name='主库地址'),
        ),
        migrations.AlterField(
            model_name='master_config',
            name='master_password',
            field=models.CharField(max_length=50, verbose_name='登录主库的密码'),
        ),
        migrations.AlterField(
            model_name='master_config',
            name='master_port',
            field=models.IntegerField(default=3306, verbose_name='主库端口'),
        ),
        migrations.AlterField(
            model_name='master_config',
            name='master_user',
            field=models.CharField(max_length=50, verbose_name='登录主库的用户名'),
        ),
        migrations.AlterField(
            model_name='master_config',
            name='update_time',
            field=models.DateTimeField(verbose_name='更新时间', auto_now=True),
        ),
        migrations.AlterField(
            model_name='users',
            name='display',
            field=models.CharField(max_length=50, verbose_name='显示的中文名'),
        ),
        migrations.AlterField(
            model_name='users',
            name='password',
            field=models.CharField(max_length=50, verbose_name='密码'),
        ),
        migrations.AlterField(
            model_name='users',
            name='role',
            field=models.CharField(default='工程师', choices=[('工程师', '工程师'), ('审核人', '审核人')], max_length=20, verbose_name='角色'),
        ),
        migrations.AlterField(
            model_name='users',
            name='username',
            field=models.CharField(max_length=50, verbose_name='用户名'),
        ),
        migrations.AlterField(
            model_name='workflow',
            name='cluster_name',
            field=models.CharField(max_length=50, verbose_name='集群名称'),
        ),
        migrations.AlterField(
            model_name='workflow',
            name='create_time',
            field=models.DateTimeField(verbose_name='创建时间', auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='workflow',
            name='engineer',
            field=models.CharField(max_length=50, verbose_name='发起人'),
        ),
        migrations.AlterField(
            model_name='workflow',
            name='execute_result',
            field=models.TextField(verbose_name='执行结果的JSON格式'),
        ),
        migrations.AlterField(
            model_name='workflow',
            name='finish_time',
            field=models.DateTimeField(blank=True, verbose_name='结束时间'),
        ),
        migrations.AlterField(
            model_name='workflow',
            name='is_backup',
            field=models.IntegerField(choices=[(0, 0), (1, 1)], verbose_name='是否备份，0为否，1为是'),
        ),
        migrations.AlterField(
            model_name='workflow',
            name='review_content',
            field=models.TextField(verbose_name='自动审核内容的JSON格式'),
        ),
        migrations.AlterField(
            model_name='workflow',
            name='review_man',
            field=models.CharField(max_length=50, verbose_name='审核人'),
        ),
        migrations.AlterField(
            model_name='workflow',
            name='reviewok_time',
            field=models.DateTimeField(verbose_name='人工审核通过的时间'),
        ),
        migrations.AlterField(
            model_name='workflow',
            name='sql_content',
            field=models.TextField(verbose_name='具体sql内容'),
        ),
        migrations.AlterField(
            model_name='workflow',
            name='status',
            field=models.CharField(choices=[('已正常结束', '已正常结束'), ('人工终止流程', '人工终止流程'), ('自动审核中', '自动审核中'), ('等待审核人审核', '等待审核人审核'), ('执行中', '执行中'), ('自动审核不通过', '自动审核不通过'), ('执行有异常', '执行有异常')], max_length=50),
        ),
        migrations.AlterField(
            model_name='workflow',
            name='workflow_name',
            field=models.CharField(max_length=50, verbose_name='工单内容'),
        ),
    ]
