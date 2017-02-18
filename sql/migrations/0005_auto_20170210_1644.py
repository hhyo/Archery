# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sql', '0004_auto_20170210_1643'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workflow',
            name='reviewok_time',
            field=models.DateTimeField(null=True, verbose_name='人工审核通过的时间', blank=True),
        ),
    ]
