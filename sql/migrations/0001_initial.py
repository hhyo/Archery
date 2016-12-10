# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='engineers',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('username', models.CharField(max_length=50)),
                ('password', models.CharField(max_length=50)),
                ('display', models.CharField(max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name='managers',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('username', models.CharField(max_length=50)),
                ('password', models.CharField(max_length=50)),
                ('display', models.CharField(max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name='master_config',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('cluster_name', models.CharField(max_length=50)),
                ('master_host', models.CharField(max_length=200)),
                ('master_port', models.IntegerField(default=3306)),
                ('master_user', models.CharField(max_length=50)),
                ('master_password', models.CharField(max_length=50)),
                ('create_time', models.DateTimeField(auto_now_add=True)),
                ('update_time', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='workflow',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('workflow_name', models.CharField(max_length=50)),
                ('engineer', models.CharField(max_length=50)),
                ('manager', models.CharField(max_length=50)),
                ('create_time', models.DateTimeField(auto_now_add=True)),
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
