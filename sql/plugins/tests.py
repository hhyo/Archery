# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: tests.py 
@time: 2019/03/04
"""
import json
from django.test import Client, TestCase
from unittest.mock import patch, ANY
from django.contrib.auth import get_user_model

from sql.plugins.binglog2sql import Binlog2Sql
from sql.plugins.schemasync import SchemaSync
from sql.plugins.soar import Soar
from sql.plugins.sqladvisor import SQLAdvisor

from common.config import SysConfig

User = get_user_model()

__author__ = 'hhyo'


class TestPlugin(TestCase):
    """
    测试Plugin调用
    """

    @classmethod
    def setUpClass(cls):
        cls.superuser = User(username='super', is_superuser=True)
        cls.superuser.save()
        cls.sys_config = SysConfig()
        cls.client = Client()
        cls.client.force_login(cls.superuser)

    @classmethod
    def tearDownClass(cls):
        cls.superuser.delete()
        cls.sys_config.replace(json.dumps({}))

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
        """
        测试SOAR参数转换
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
        cmd_args = soar.generate_args2cmd(args, False)
        self.assertIsInstance(cmd_args, list)
        cmd_args = soar.generate_args2cmd(args, True)
        self.assertIsInstance(cmd_args, str)

    def test_sql_advisor_generate_args2cmd(self):
        """
        测试sql_advisor参数转换
        :return:
        """
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

    def test_schema_sync_generate_args2cmd(self):
        """
        测试schema_sync参数转换
        :return:
        """
        args = {
            "sync-auto-inc": True,
            "sync-comments": True,
            "tag": 'tag_v',
            "output-directory": '',
            "source": r"mysql://{user}:{pwd}@{host}:{port}/{database}".format(user='root',
                                                                              pwd='123456',
                                                                              host='127.0.0.1',
                                                                              port=3306,
                                                                              database='*'),
            "target": r"mysql://{user}:{pwd}@{host}:{port}/{database}".format(user='root',
                                                                              pwd='123456',
                                                                              host='127.0.0.1',
                                                                              port=3306,
                                                                              database='*')
        }
        self.sys_config.set('schemasync', '/opt/venv4schemasync/bin/schemasync')
        self.sys_config.get_all_config()
        schema_sync = SchemaSync()
        cmd_args = schema_sync.generate_args2cmd(args, False)
        self.assertIsInstance(cmd_args, list)
        cmd_args = schema_sync.generate_args2cmd(args, True)
        self.assertIsInstance(cmd_args, str)

    def test_binlog2ql_generate_args2cmd(self):
        """
        测试binlog2sql参数转换
        :return:
        """
        args = {'conn_options': "-hmysql -uroot -p'123456' -P3306 ",
                'stop_never': False,
                'no-primary-key': False,
                'flashback': True,
                'back-interval': 0,
                'start-file': 'mysql-bin.000043',
                'start-position': 111,
                'stop-file': '',
                'stop-position': '',
                'start-datetime': '',
                'stop-datetime': '',
                'databases': 'account_center',
                'tables': 'ac_apps',
                'only-dml': True,
                'sql-type': 'UPDATE'}
        self.sys_config.set('binlog2sql', '/opt/archery/src/plugins/binlog2sql/binlog2sql.py')
        self.sys_config.get_all_config()
        binlog2sql = Binlog2Sql()
        cmd_args = binlog2sql.generate_args2cmd(args, False)
        self.assertIsInstance(cmd_args, list)
        cmd_args = binlog2sql.generate_args2cmd(args, True)
        self.assertIsInstance(cmd_args, str)

    @patch('sql.plugins.plugin.subprocess')
    def test_execute_cmd(self, mock_subprocess):
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

        mock_subprocess.Popen.return_value.communicate.return_value = ('some_stdout', 'some_stderr')
        stdout, stderr = soar.execute_cmd(cmd_args, True).communicate()
        mock_subprocess.Popen.assert_called_once_with(
            cmd_args,
            shell=True,
            stdout=ANY,
            stderr=ANY,
            universal_newlines=ANY
        )
        self.assertIn('some_stdout', stdout)
        # 异常

        mock_subprocess.Popen.side_effect = Exception('Boom! some exception!')
        with self.assertRaises(RuntimeError):
            soar.execute_cmd(cmd_args, False)


class TestSoar(TestCase):
    """
    测试Soar的拓展方法
    """

    @classmethod
    def setUpClass(cls):
        soar_path = '/opt/archery/src/plugins/soar'  # 修改为本机的soar路径
        cls.superuser = User(username='super', is_superuser=True)
        cls.superuser.save()
        cls.client = Client()
        cls.client.force_login(cls.superuser)
        cls.sys_config = SysConfig()
        cls.sys_config.set('soar', soar_path)
        cls.sys_config.get_all_config()
        cls.soar = Soar()

    @classmethod
    def tearDownClass(cls):
        cls.superuser.delete()
        cls.sys_config.replace(json.dumps({}))

    def test_fingerprint(self):
        """
        测试SQL指纹打印，未断言
        :return:
        """
        sql = """select * from sql_users where id>0 and email<>'';"""
        finger = self.soar.fingerprint(sql)
        # self.assertEqual(finger, 'select * from sql_users where id>? and email<>?\n')

    def test_compress(self):
        """
        测试SQL压缩，未断言
        :return:
        """
        sql = """
        select * 
        from sql_users
        where id>0 and email<>'';
        """
        compress_sql = self.soar.compress(sql)
        # self.assertEqual(compress_sql, "select * from sql_users where id>0 and email<>'';\n")

    def test_pretty(self):
        """
        测试SQL美化，未断言
        :return:
        """
        sql = """select * from sql_users where id>0 and email<>'';"""
        self.soar.pretty(sql)

    def test_remove_comment(self):
        """
        测试去除注释，未断言
        :return:
        """
        sql = """--
                select *
                from sql_users
                where id = 1 -- and email<>''
                -- and username<>''
                # and ;"""
        self.soar.remove_comment(sql)

    def test_rewrite(self):
        """
        测试SQL改写
        :return:
        """
        sql = """update sql_users set username='',id=1 where id>0 and email<>'';"""
        self.soar.rewrite(sql)
        # 异常测试
        with self.assertRaises(RuntimeError):
            self.soar.rewrite(sql, 'unknown')
