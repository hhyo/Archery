# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: tests.py 
@time: 2019/03/04
"""
import json

from django.test import Client, TestCase
from django.contrib.auth import get_user_model
from sql.plugins.soar import Soar
from sql.plugins.sqladvisor import SQLAdvisor

from common.config import SysConfig

User = get_user_model()

__author__ = 'hhyo'


class TestPlugin(TestCase):
    """
    测试Plugin调用
    """

    def setUp(self):
        self.superuser = User(username='super', is_superuser=True)
        self.superuser.save()
        self.sys_config = SysConfig()
        self.client = Client()
        self.client.force_login(self.superuser)

    def tearDown(self):
        self.superuser.delete()
        self.sys_config.replace(json.dumps({}))

    def test_check_args_path(self):
        """
        测试路径
        :return:
        """
        args = {"online-dsn": '',
                "test-dsn": '',
                "allow-online-as-test": "false",
                "report-type": "markdown",
                "query": "select 1;"
                }
        self.sys_config.set('soar', '')
        self.sys_config.get_all_config()
        soar = Soar()
        args_check_result = soar.check_args(args)
        self.assertDictEqual(args_check_result, {'status': 1, 'msg': '可执行文件路径不能为空！', 'data': {}})
        # 路径不为空
        self.sys_config.set('soar', '/opt/archery/src/plugins/soar')
        self.sys_config.get_all_config()
        soar = Soar()
        args_check_result = soar.check_args(args)
        self.assertDictEqual(args_check_result, {'status': 0, 'msg': 'ok', 'data': {}})

    def test_check_args_disable(self):
        """
        测试禁用参数
        :return:
        """
        args = {"online-dsn": '',
                "test-dsn": '',
                "allow-online-as-test": "false",
                "report-type": "markdown",
                "query": "select 1;"
                }
        self.sys_config.set('soar', '/opt/archery/src/plugins/soar')
        self.sys_config.get_all_config()
        soar = Soar()
        soar.disable_args = ['allow-online-as-test']
        args_check_result = soar.check_args(args)
        self.assertDictEqual(args_check_result, {'status': 1, 'msg': 'allow-online-as-test参数已被禁用', 'data': {}})

    def test_check_args_required(self):
        """
        测试必选参数
        :return:
        """
        args = {"online-dsn": '',
                "test-dsn": '',
                "allow-online-as-test": "false",
                "report-type": "markdown",
                }
        self.sys_config.set('soar', '/opt/archery/src/plugins/soar')
        self.sys_config.get_all_config()
        soar = Soar()
        soar.required_args = ['query']
        args_check_result = soar.check_args(args)
        self.assertDictEqual(args_check_result, {'status': 1, 'msg': '必须指定query参数', 'data': {}})
        args['query'] = ""
        args_check_result = soar.check_args(args)
        self.assertDictEqual(args_check_result, {'status': 1, 'msg': 'query参数值不能为空', 'data': {}})

    def test_soar_generate_args2cmd(self):
        args = {"online-dsn": '',
                "test-dsn": '',
                "allow-online-as-test": "false",
                "report-type": "markdown",
                "query": "select 1;"
                }
        self.sys_config.set('soar', '/opt/archery/src/plugins/soar')
        self.sys_config.get_all_config()
        soar = Soar()
        cmd_args = soar.generate_args2cmd(args, False)
        self.assertIsInstance(cmd_args, list)
        cmd_args = soar.generate_args2cmd(args, True)
        self.assertIsInstance(cmd_args, str)

    def test_sql_advisor_generate_args2cmd(self):
        args = {"h": 'mysql',
                "P": 3306,
                "u": 'root',
                "p": '',
                "d": 'archery',
                "v": 1,
                "q": 'select 1;'
                }
        self.sys_config.set('sqladvisor', '/opt/archery/src/plugins/SQLAdvisor')
        self.sys_config.get_all_config()
        sql_advisor = SQLAdvisor()
        cmd_args = sql_advisor.generate_args2cmd(args, False)
        self.assertIsInstance(cmd_args, list)
        cmd_args = sql_advisor.generate_args2cmd(args, True)
        self.assertIsInstance(cmd_args, str)

    def test_execute_cmd(self):
        args = {"online-dsn": '',
                "test-dsn": '',
                "allow-online-as-test": "false",
                "report-type": "markdown",
                "query": "select 1;"
                }
        self.sys_config.set('soar', '/opt/archery/src/plugins/soar')
        self.sys_config.get_all_config()
        soar = Soar()
        cmd_args = soar.generate_args2cmd(args, True)
        result = soar.execute_cmd(cmd_args, True)
        self.assertTrue('/opt/archery/src/plugins/soar' in result)
        # 异常
        with self.assertRaises(RuntimeError):
            soar.execute_cmd(cmd_args, False)
