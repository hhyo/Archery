# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('django_q', '0004_auto_20150710_1043'),
    ]

    operations = [
        migrations.AddField(
            model_name='schedule',
            name='name',
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='task',
            name='group',
            field=models.CharField(max_length=100, null=True, editable=False),
        ),
    ]
