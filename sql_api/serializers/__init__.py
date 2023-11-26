# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: __init__.py
@time: 2022/10/22
"""
__author__ = "hhyo"

from rest_framework import serializers


class BaseModelSerializer(serializers.ModelSerializer):
    """BaseModelSerializer，主要是引入过滤和排除字段的方法"""

    def __init__(self, *args, **kwargs):
        """
        ``fields`` 需要保留的字段列表
        ``exclude`` 需要排除的字段列表
        """
        fields = kwargs.pop("fields", None)
        exclude = kwargs.pop("exclude", None)
        super(BaseModelSerializer, self).__init__(*args, **kwargs)

        for field_name in set(self.fields.keys()):
            if not any([fields, exclude]):
                break
            if fields and field_name in fields:
                continue
            if exclude and field_name not in exclude:
                continue
            self.fields.pop(field_name, None)

    @staticmethod
    def setup_eager_loading(queryset):
        """
        Perform necessary eager loading of data.
        https://ses4j.github.io/2015/11/23/optimizing-slow-django-rest-framework-performance/
        """
        pass
