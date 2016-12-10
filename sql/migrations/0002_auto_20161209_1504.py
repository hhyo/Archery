# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sql', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='managers',
            new_name='users',
        ),
        migrations.DeleteModel(
            name='engineers',
        ),
    ]
