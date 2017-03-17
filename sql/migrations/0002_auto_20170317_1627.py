# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sql', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='master_config',
            options={'verbose_name': '主库地址', 'verbose_name_plural': '主库地址'},
        ),
        migrations.AlterModelOptions(
            name='workflow',
            options={'verbose_name': '工单管理', 'verbose_name_plural': '工单管理'},
        ),
        migrations.AlterField(
            model_name='master_config',
            name='master_password',
            field=models.CharField(verbose_name='登录主库的密码', max_length=300),
        ),
        migrations.AlterField(
            model_name='master_config',
            name='master_user',
            field=models.CharField(verbose_name='登录主库的用户名', max_length=100),
        ),
    ]
