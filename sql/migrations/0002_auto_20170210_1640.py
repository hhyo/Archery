# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sql', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='master_config',
            name='cluster_name',
            field=models.CharField(max_length=50, verbose_name=b'\xe9\x9b\x86\xe7\xbe\xa4\xe5\x90\x8d\xe7\xa7\xb0'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='master_config',
            name='create_time',
            field=models.DateTimeField(auto_now_add=True, verbose_name=b'\xe5\x88\x9b\xe5\xbb\xba\xe6\x97\xb6\xe9\x97\xb4'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='master_config',
            name='master_host',
            field=models.CharField(max_length=200, verbose_name=b'\xe4\xb8\xbb\xe5\xba\x93\xe5\x9c\xb0\xe5\x9d\x80'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='master_config',
            name='master_password',
            field=models.CharField(max_length=50, verbose_name=b'\xe7\x99\xbb\xe5\xbd\x95\xe4\xb8\xbb\xe5\xba\x93\xe7\x9a\x84\xe5\xaf\x86\xe7\xa0\x81'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='master_config',
            name='master_port',
            field=models.IntegerField(default=3306, verbose_name=b'\xe4\xb8\xbb\xe5\xba\x93\xe7\xab\xaf\xe5\x8f\xa3'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='master_config',
            name='master_user',
            field=models.CharField(max_length=50, verbose_name=b'\xe7\x99\xbb\xe5\xbd\x95\xe4\xb8\xbb\xe5\xba\x93\xe7\x9a\x84\xe7\x94\xa8\xe6\x88\xb7\xe5\x90\x8d'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='master_config',
            name='update_time',
            field=models.DateTimeField(auto_now=True, verbose_name=b'\xe6\x9b\xb4\xe6\x96\xb0\xe6\x97\xb6\xe9\x97\xb4'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='users',
            name='display',
            field=models.CharField(max_length=50, verbose_name=b'\xe6\x98\xbe\xe7\xa4\xba\xe7\x9a\x84\xe4\xb8\xad\xe6\x96\x87\xe5\x90\x8d'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='users',
            name='password',
            field=models.CharField(max_length=50, verbose_name=b'\xe5\xaf\x86\xe7\xa0\x81'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='users',
            name='role',
            field=models.CharField(default=b'\xe5\xb7\xa5\xe7\xa8\x8b\xe5\xb8\x88', max_length=20, verbose_name=b'\xe8\xa7\x92\xe8\x89\xb2', choices=[(b'\xe5\xb7\xa5\xe7\xa8\x8b\xe5\xb8\x88', b'\xe5\xb7\xa5\xe7\xa8\x8b\xe5\xb8\x88'), (b'\xe5\xae\xa1\xe6\xa0\xb8\xe4\xba\xba', b'\xe5\xae\xa1\xe6\xa0\xb8\xe4\xba\xba')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='users',
            name='username',
            field=models.CharField(max_length=50, verbose_name=b'\xe7\x94\xa8\xe6\x88\xb7\xe5\x90\x8d'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='workflow',
            name='cluster_name',
            field=models.CharField(max_length=50, verbose_name=b'\xe9\x9b\x86\xe7\xbe\xa4\xe5\x90\x8d\xe7\xa7\xb0'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='workflow',
            name='create_time',
            field=models.DateTimeField(auto_now_add=True, verbose_name=b'\xe5\x88\x9b\xe5\xbb\xba\xe6\x97\xb6\xe9\x97\xb4'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='workflow',
            name='engineer',
            field=models.CharField(max_length=50, verbose_name=b'\xe5\x8f\x91\xe8\xb5\xb7\xe4\xba\xba'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='workflow',
            name='execute_result',
            field=models.TextField(verbose_name=b'\xe6\x89\xa7\xe8\xa1\x8c\xe7\xbb\x93\xe6\x9e\x9c\xe7\x9a\x84JSON\xe6\xa0\xbc\xe5\xbc\x8f'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='workflow',
            name='finish_time',
            field=models.DateTimeField(verbose_name=b'\xe7\xbb\x93\xe6\x9d\x9f\xe6\x97\xb6\xe9\x97\xb4', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='workflow',
            name='is_backup',
            field=models.IntegerField(verbose_name=b'\xe6\x98\xaf\xe5\x90\xa6\xe5\xa4\x87\xe4\xbb\xbd\xef\xbc\x8c0\xe4\xb8\xba\xe5\x90\xa6\xef\xbc\x8c1\xe4\xb8\xba\xe6\x98\xaf', choices=[(0, 0), (1, 1)]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='workflow',
            name='review_content',
            field=models.TextField(verbose_name=b'\xe8\x87\xaa\xe5\x8a\xa8\xe5\xae\xa1\xe6\xa0\xb8\xe5\x86\x85\xe5\xae\xb9\xe7\x9a\x84JSON\xe6\xa0\xbc\xe5\xbc\x8f'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='workflow',
            name='review_man',
            field=models.CharField(max_length=50, verbose_name=b'\xe5\xae\xa1\xe6\xa0\xb8\xe4\xba\xba'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='workflow',
            name='reviewok_time',
            field=models.DateTimeField(verbose_name=b'\xe4\xba\xba\xe5\xb7\xa5\xe5\xae\xa1\xe6\xa0\xb8\xe9\x80\x9a\xe8\xbf\x87\xe7\x9a\x84\xe6\x97\xb6\xe9\x97\xb4'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='workflow',
            name='sql_content',
            field=models.TextField(verbose_name=b'\xe5\x85\xb7\xe4\xbd\x93sql\xe5\x86\x85\xe5\xae\xb9'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='workflow',
            name='status',
            field=models.CharField(max_length=50, choices=[(b'\xe5\xb7\xb2\xe6\xad\xa3\xe5\xb8\xb8\xe7\xbb\x93\xe6\x9d\x9f', b'\xe5\xb7\xb2\xe6\xad\xa3\xe5\xb8\xb8\xe7\xbb\x93\xe6\x9d\x9f'), (b'\xe4\xba\xba\xe5\xb7\xa5\xe7\xbb\x88\xe6\xad\xa2\xe6\xb5\x81\xe7\xa8\x8b', b'\xe4\xba\xba\xe5\xb7\xa5\xe7\xbb\x88\xe6\xad\xa2\xe6\xb5\x81\xe7\xa8\x8b'), (b'\xe8\x87\xaa\xe5\x8a\xa8\xe5\xae\xa1\xe6\xa0\xb8\xe4\xb8\xad', b'\xe8\x87\xaa\xe5\x8a\xa8\xe5\xae\xa1\xe6\xa0\xb8\xe4\xb8\xad'), (b'\xe7\xad\x89\xe5\xbe\x85\xe5\xae\xa1\xe6\xa0\xb8\xe4\xba\xba\xe5\xae\xa1\xe6\xa0\xb8', b'\xe7\xad\x89\xe5\xbe\x85\xe5\xae\xa1\xe6\xa0\xb8\xe4\xba\xba\xe5\xae\xa1\xe6\xa0\xb8'), (b'\xe6\x89\xa7\xe8\xa1\x8c\xe4\xb8\xad', b'\xe6\x89\xa7\xe8\xa1\x8c\xe4\xb8\xad'), (b'\xe8\x87\xaa\xe5\x8a\xa8\xe5\xae\xa1\xe6\xa0\xb8\xe4\xb8\x8d\xe9\x80\x9a\xe8\xbf\x87', b'\xe8\x87\xaa\xe5\x8a\xa8\xe5\xae\xa1\xe6\xa0\xb8\xe4\xb8\x8d\xe9\x80\x9a\xe8\xbf\x87'), (b'\xe6\x89\xa7\xe8\xa1\x8c\xe6\x9c\x89\xe5\xbc\x82\xe5\xb8\xb8', b'\xe6\x89\xa7\xe8\xa1\x8c\xe6\x9c\x89\xe5\xbc\x82\xe5\xb8\xb8')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='workflow',
            name='workflow_name',
            field=models.CharField(max_length=50, verbose_name=b'\xe5\xb7\xa5\xe5\x8d\x95\xe5\x86\x85\xe5\xae\xb9'),
            preserve_default=True,
        ),
    ]
