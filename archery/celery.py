#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/9/3 8:56
# @Author  : sky
# @File    : celery.py
# @Description : celery
import os
from celery import Celery
#加载配置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'archery.settings')
#创建celery app
app = Celery('archery')
app.config_from_object('django.conf:settings', namespace='CELERY')
#自动发现项目中的tasks
app.autodiscover_tasks()

#定时任务
app.conf.beat_schedule = {}