# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('django_q', '0002_auto_20150630_1624'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='failure',
            options={'verbose_name_plural': 'Failed tasks', 'verbose_name': 'Failed task'},
        ),
        migrations.AlterModelOptions(
            name='schedule',
            options={'verbose_name_plural': 'Scheduled tasks', 'ordering': ['next_run'], 'verbose_name': 'Scheduled task'},
        ),
        migrations.AlterModelOptions(
            name='success',
            options={'verbose_name_plural': 'Successful tasks', 'verbose_name': 'Successful task'},
        ),
        migrations.AlterField(
            model_name='task',
            name='id',
            field=models.CharField(max_length=32, primary_key=True, editable=False, serialize=False),
        ),
    ]
