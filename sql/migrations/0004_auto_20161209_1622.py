# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sql', '0003_users_role'),
    ]

    operations = [
        migrations.RenameField(
            model_name='workflow',
            old_name='manager',
            new_name='review_man',
        ),
    ]
