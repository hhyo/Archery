# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sql', '0002_auto_20161209_1504'),
    ]

    operations = [
        migrations.AddField(
            model_name='users',
            name='role',
            field=models.CharField(default='工程师', choices=[('工程师', '工程师'), ('审核人', '审核人')], max_length=20),
        ),
    ]
