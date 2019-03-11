# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: tests.py 
@time: 2019/03/11
"""
from django.conf import settings
from django.test import TestCase
from prompt_toolkit.completion import Completion
from sql.completer import get_comp_engine

from sql.models import Instance

__author__ = 'hhyo'


class TestCompleter(TestCase):
    @classmethod
    def setUpClass(cls):
        """
        初始化补全引擎
        :return:
        """
        # 使用 travis.ci 时实例和测试service保持一致
        cls.master = Instance(instance_name='test_instance', type='master', db_type='mysql',
                              host=settings.DATABASES['default']['HOST'],
                              port=settings.DATABASES['default']['PORT'],
                              user=settings.DATABASES['default']['USER'],
                              password=settings.DATABASES['default']['PASSWORD'])
        cls.master.save()
        cls.comp_engine = get_comp_engine(instance=cls.master, db_name=settings.DATABASES['default']['TEST']['NAME'])
        # 等待completion_refresher刷新完成
        while cls.comp_engine.completion_refresher.is_refreshing():
            import time
            time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        """
        :return:
        """
        cls.master.delete()
        cls.comp_engine.refresh_completions(reset=True)

    def test_table_names_after_from(self):
        text = 'SELECT * FROM '
        position = len('SELECT * FROM ')
        self.comp_engine.get_completions(text=text, cursor_position=position)

    def test_suggested_column_names(self):
        text = 'SELECT  FROM sql_users'
        position = len('SELECT ')
        self.comp_engine.get_completions(text=text, cursor_position=position)

    def test_function_name_completion(self):
        text = 'SELECT MA'
        position = len('SELECT MA')
        result = self.comp_engine.get_completions(text=text, cursor_position=position)
        self.comp_engine.convert2ace_js(result)
        self.assertListEqual(result, [Completion(text='MAX', start_position=-2),
                                      Completion(text='MASTER', start_position=-2)])
