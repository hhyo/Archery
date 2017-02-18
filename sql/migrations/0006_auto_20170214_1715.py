# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sql', '0005_auto_20170210_1644'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workflow',
            name='is_backup',
            field=models.CharField(verbose_name='是否备份', max_length=20, choices=[('否', '否'), ('是', '是')]),
        ),
    ]
