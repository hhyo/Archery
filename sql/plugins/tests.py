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

from sql.plugins.my2sql import My2SQL
from sql.plugins.schemasync import SchemaSync
from sql.plugins.soar import Soar
from sql.plugins.sqladvisor import SQLAdvisor
from sql.plugins.pt_archiver import PtArchiver

from common.config import SysConfig

User = get_user_model()

__author__ = "hhyo"


class TestPlugin(TestCase):
    """
    测试Plugin调用
    """

    @classmethod
    def setUpClass(cls):
        cls.superuser = User(username="super", is_superuser=True)
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
        args = {
            "online-dsn": "",
            "test-dsn": "",
            "allow-online-as-test": "false",
            "report-type": "markdown",
            "query": "select 1;",
        }
        self.sys_config.set("soar", "")
        self.sys_config.get_all_config()
        soar = Soar()
        args_check_result = soar.check_args(args)
        self.assertDictEqual(
            args_check_result, {"status": 1, "msg": "可执行文件路径不能为空！", "data": {}}
        )
        # 路径不为空
        self.sys_config.set("soar", "/opt/archery/src/plugins/soar")
        self.sys_config.get_all_config()
        soar = Soar()
        args_check_result = soar.check_args(args)
        self.assertDictEqual(args_check_result, {"status": 0, "msg": "ok", "data": {}})

    def test_check_args_disable(self):
        """
        测试禁用参数
        :return:
        """
        args = {
            "online-dsn": "",
            "test-dsn": "",
            "allow-online-as-test": "false",
            "report-type": "markdown",
            "query": "select 1;",
        }
        self.sys_config.set("soar", "/opt/archery/src/plugins/soar")
        self.sys_config.get_all_config()
        soar = Soar()
        soar.disable_args = ["allow-online-as-test"]
        args_check_result = soar.check_args(args)
        self.assertDictEqual(
            args_check_result,
            {"status": 1, "msg": "allow-online-as-test参数已被禁用", "data": {}},
        )

    def test_check_args_required(self):
        """
        测试必选参数
        :return:
        """
        args = {
            "online-dsn": "",
            "test-dsn": "",
            "allow-online-as-test": "false",
            "report-type": "markdown",
        }
        self.sys_config.set("soar", "/opt/archery/src/plugins/soar")
        self.sys_config.get_all_config()
        soar = Soar()
        soar.required_args = ["query"]
        args_check_result = soar.check_args(args)
        self.assertDictEqual(
            args_check_result, {"status": 1, "msg": "必须指定query参数", "data": {}}
        )
        args["query"] = ""
        args_check_result = soar.check_args(args)
        self.assertDictEqual(
            args_check_result, {"status": 1, "msg": "query参数值不能为空", "data": {}}
        )

    def test_soar_generate_args2cmd(self):
        """
        测试SOAR参数转换
        :return:
        """
        args = {
            "online-dsn": "",
            "test-dsn": "",
            "allow-online-as-test": "false",
            "report-type": "markdown",
            "query": "select 1;",
        }
        self.sys_config.set("soar", "/opt/archery/src/plugins/soar")
        self.sys_config.get_all_config()
        soar = Soar()
        cmd_args = soar.generate_args2cmd(args)
        self.assertIsInstance(cmd_args, list)

    def test_sql_advisor_generate_args2cmd(self):
        """
        测试sql_advisor参数转换
        :return:
        """
        args = {
            "h": "mysql",
            "P": 3306,
            "u": "root",
            "p": "",
            "d": "archery",
            "v": 1,
            "q": "select 1;",
        }
        self.sys_config.set("sqladvisor", "/opt/archery/src/plugins/SQLAdvisor")
        self.sys_config.get_all_config()
        sql_advisor = SQLAdvisor()
        cmd_args = sql_advisor.generate_args2cmd(args)
        self.assertIsInstance(cmd_args, list)

    def test_schema_sync_generate_args2cmd(self):
        """
        测试schema_sync参数转换
        :return:
        """
        args = {
            "sync-auto-inc": True,
            "sync-comments": True,
            "tag": "tag_v",
            "output-directory": "",
            "source": r"mysql://{user}:{pwd}@{host}:{port}/{database}".format(
                user="root", pwd="123456", host="127.0.0.1", port=3306, database="*"
            ),
            "target": r"mysql://{user}:{pwd}@{host}:{port}/{database}".format(
                user="root", pwd="123456", host="127.0.0.1", port=3306, database="*"
            ),
        }
        self.sys_config.set("schemasync", "/opt/venv4schemasync/bin/schemasync")
        self.sys_config.get_all_config()
        schema_sync = SchemaSync()
        cmd_args = schema_sync.generate_args2cmd(args)
        self.assertIsInstance(cmd_args, list)

    def test_my2sql_generate_args2cmd(self):
        """
        测试my2sql参数转换
        :return:
        """
        args = {
            "conn_options": "-host mysql -user root -password '123456' -port 3306 ",
            "work-type": "2sql",
            "start-file": "mysql-bin.000043",
            "start-pos": 111,
            "stop-file": "",
            "stop-pos": "",
            "start-datetime": "",
            "stop-datetime": "",
            "databases": "account_center",
            "tables": "ac_apps",
            "sql": "update",
            "threads": 1,
            "add-extraInfo": "false",
            "ignore-primaryKey-forInsert": "false",
            "full-columns": "false",
            "do-not-add-prifixDb": "false",
            "file-per-table": "false",
        }
        self.sys_config.set("my2sql", "/opt/archery/src/plugins/my2sql")
        self.sys_config.get_all_config()
        my2sql = My2SQL()
        cmd_args = my2sql.generate_args2cmd(args)
        self.assertIsInstance(cmd_args, list)

    def test_pt_archiver_generate_args2cmd(self):
        """
        测试pt_archiver参数转换
        :return:
        """
        args = {
            "no-version-check": True,
            "source": "",
            "where": "",
            "progress": 5000,
            "statistics": True,
            "charset": "UTF8",
            "limit": 10000,
            "txn-size": 1000,
            "sleep": 1,
        }
        pt_archiver = PtArchiver()
        cmd_args = pt_archiver.generate_args2cmd(args)
        self.assertIsInstance(cmd_args, list)

    @patch("sql.plugins.plugin.subprocess")
    def test_execute_cmd(self, mock_subprocess):
        args = {
            "online-dsn": "",
            "test-dsn": "",
            "allow-online-as-test": "false",
            "report-type": "markdown",
            "query": "select 1;",
        }
        self.sys_config.set("soar", "/opt/archery/src/plugins/soar")
        self.sys_config.get_all_config()
        soar = Soar()
        cmd_args = soar.generate_args2cmd(args)

        mock_subprocess.Popen.return_value.communicate.return_value = (
            "some_stdout",
            "some_stderr",
        )
        stdout, stderr = soar.execute_cmd(cmd_args).communicate()
        mock_subprocess.Popen.assert_called_once_with(
            cmd_args, shell=False, stdout=ANY, stderr=ANY, universal_newlines=ANY
        )
        self.assertIn("some_stdout", stdout)
        # 异常

        mock_subprocess.Popen.side_effect = Exception("Boom! some exception!")
        with self.assertRaises(RuntimeError):
            soar.execute_cmd(cmd_args)


class TestSoar(TestCase):
    """
    测试Soar的拓展方法
    """

    @classmethod
    def setUpClass(cls):
        soar_path = "/opt/archery/src/plugins/soar"  # 修改为本机的soar路径
        cls.superuser = User(username="super", is_superuser=True)
        cls.superuser.save()
        cls.client = Client()
        cls.client.force_login(cls.superuser)
        cls.sys_config = SysConfig()
        cls.sys_config.set("soar", soar_path)
        cls.sys_config.get_all_config()
        cls.soar = Soar()

    @classmethod
    def tearDownClass(cls):
        cls.superuser.delete()
        cls.sys_config.replace(json.dumps({}))

    @patch("sql.plugins.plugin.subprocess")
    def test_fingerprint(self, _subprocess):
        """
        测试SQL指纹打印，未断言
        :return:
        """
        sql = """select * from sql_users where id>0 and email<>'';"""
        self.soar.fingerprint(sql)

    @patch("sql.plugins.plugin.subprocess")
    def test_compress(self, _subprocess):
        """
        测试SQL压缩，未断言
        :return:
        """
        sql = """
        select * 
        from sql_users
        where id>0 and email<>'';
        """
        self.soar.compress(sql)

    @patch("sql.plugins.plugin.subprocess")
    def test_pretty(self, _subprocess):
        """
        测试SQL美化，未断言
        :return:
        """
        sql = """select * from sql_users where id>0 and email<>'';"""
        self.soar.pretty(sql)

    @patch("sql.plugins.plugin.subprocess")
    def test_remove_comment(self, _subprocess):
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

    @patch("sql.plugins.plugin.subprocess")
    def test_rewrite(self, _subprocess):
        """
        测试SQL改写
        :return:
        """
        sql = """update sql_users set username='',id=1 where id>0 and email<>'';"""
        self.soar.rewrite(sql)
        # 异常测试
        with self.assertRaises(RuntimeError):
            self.soar.rewrite(sql, "unknown")
