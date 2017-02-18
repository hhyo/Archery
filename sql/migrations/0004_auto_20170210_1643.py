# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sql', '0003_auto_20170210_1640'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workflow',
            name='finish_time',
            field=models.DateTimeField(verbose_name='结束时间', null=True, blank=True),
        ),
    ]
