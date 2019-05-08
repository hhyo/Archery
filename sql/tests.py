import json
import re
from datetime import timedelta, datetime, date
from unittest.mock import MagicMock, patch, ANY
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, TransactionTestCase

import sql.query_privileges
from common.config import SysConfig
from sql.binlog import binlog2sql_file
from sql.engines.models import ResultSet
from sql.utils.execute_sql import execute_callback
from sql.models import Instance, QueryPrivilegesApply, QueryPrivileges, SqlWorkflow, SqlWorkflowContent, QueryLog, \
    ResourceGroup, ResourceGroupRelations, ParamTemplate

User = get_user_model()


class TestSignUp(TestCase):
    """注册测试"""

    def setUp(self):
        """
        创建默认组给注册关联用户, 打开注册
        """
        archer_config = SysConfig()
        archer_config.set('sign_up_enabled', 'true')
        archer_config.get_all_config()
        self.client = Client()
        Group.objects.create(id=1, name='默认组')

    def tearDown(self):
        SysConfig().replace(json.dumps({}))

    def test_sing_up_not_username(self):
        """
        用户名不能为空
        """
        response = self.client.post('/signup/', data={})
        data = json.loads(response.content)
        content = {'status': 1, 'msg': '用户名和密码不能为空', 'data': None}
        self.assertEqual(data, content)

    def test_sing_up_not_password(self):
        """
        密码不能为空
        """
        response = self.client.post('/signup/', data={'username': 'test'})
        data = json.loads(response.content)
        content = {'status': 1, 'msg': '用户名和密码不能为空', 'data': None}
        self.assertEqual(data, content)

    def test_sing_up_2password(self):
        """
        两次输入密码不一致
        """
        response = self.client.post('/signup/', data={'username': 'test', 'password': '123456', 'password2': '12345'})
        data = json.loads(response.content)
        content = {'status': 1, 'msg': '两次输入密码不一致', 'data': None}
        self.assertEqual(data, content)

    def test_sing_up_duplicate_uesrname(self):
        """
        用户名已存在
        """
        User.objects.create(username='test', password='123456')
        response = self.client.post('/signup/',
                                    data={'username': 'test', 'password': '123456', 'password2': '123456'})
        data = json.loads(response.content)
        content = {'status': 1, 'msg': '用户名已存在', 'data': None}
        self.assertEqual(data, content)

    def test_sing_up(self):
        """
        注册成功
        """
        self.client.post('/signup/',
                         data={'username': 'test', 'password': '123456test',
                               'password2': '123456test', 'display': 'test', 'email': '123@123.com'})
        user = User.objects.get(username='test')
        self.assertTrue(user)


class TestUser(TestCase):
    def setUp(self):
        self.u1 = User(username='test_user', display='中文显示', is_active=True)
        self.u1.save()

    def tearDown(self):
        self.u1.delete()

    def testLogin(self):
        """login 页面测试"""
        c = Client()
        r = c.get('/login/')
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'login.html')
        c.force_login(self.u1)
        # 登录后直接跳首页
        r = c.get('/login/', follow=True)
        self.assertRedirects(r, '/sqlworkflow/')


class TestQueryPrivilegesCheck(TestCase):
    """测试权限校验"""

    def setUp(self):
        self.superuser = User.objects.create(username='super', is_superuser=True)
        self.user = User.objects.create(username='user')
        # 使用 travis.ci 时实例和测试service保持一致
        self.slave = Instance.objects.create(instance_name='test_instance', type='slave', db_type='mysql',
                                             host=settings.DATABASES['default']['HOST'],
                                             port=settings.DATABASES['default']['PORT'],
                                             user=settings.DATABASES['default']['USER'],
                                             password=settings.DATABASES['default']['PASSWORD'])
        self.db_name = settings.DATABASES['default']['TEST']['NAME']
        self.sys_config = SysConfig()
        self.client = Client()

    def tearDown(self):
        self.superuser.delete()
        self.user.delete()
        Instance.objects.all().delete()
        QueryPrivileges.objects.all().delete()
        self.sys_config.replace(json.dumps({}))

    def test_db_priv_super(self):
        """
        测试超级管理员验证数据库权限
        :return:
        """
        self.sys_config.set('admin_query_limit', '50')
        self.sys_config.get_all_config()
        r = sql.query_privileges._db_priv(user=self.superuser, instance=self.slave, db_name=self.db_name)
        self.assertEqual(r, 50)

    def test_db_priv_user_priv_not_exist(self):
        """
        测试普通用户验证数据库权限，用户无权限
        :return:
        """
        r = sql.query_privileges._db_priv(user=self.user, instance=self.slave, db_name=self.db_name)
        self.assertFalse(r)

    def test_db_priv_user_priv_exist(self):
        """
        测试普通用户验证数据库权限，用户有权限
        :return:
        """
        QueryPrivileges.objects.create(user_name=self.user.username,
                                       instance=self.slave,
                                       db_name=self.db_name,
                                       valid_date=date.today() + timedelta(days=1),
                                       limit_num=10,
                                       priv_type=1)
        r = sql.query_privileges._db_priv(user=self.user, instance=self.slave, db_name=self.db_name)
        self.assertTrue(r)

    def test_tb_priv_super(self):
        """
        测试超级管理员验证表权限
        :return:
        """
        self.sys_config.set('admin_query_limit', '50')
        self.sys_config.get_all_config()
        r = sql.query_privileges._tb_priv(user=self.superuser, instance=self.slave, db_name=self.db_name,
                                          tb_name='table_name')
        self.assertEqual(r, 50)

    def test_tb_priv_user_priv_not_exist(self):
        """
        测试普通用户验证表权限，用户无权限
        :return:
        """
        r = sql.query_privileges._tb_priv(user=self.user, instance=self.slave, db_name=self.db_name,
                                          tb_name='table_name')
        self.assertFalse(r)

    def test_tb_priv_user_priv_exist(self):
        """
        测试普通用户验证表权限，用户有权限
        :return:
        """
        QueryPrivileges.objects.create(user_name=self.user.username,
                                       instance=self.slave,
                                       db_name=self.db_name,
                                       table_name='table_name',
                                       valid_date=date.today() + timedelta(days=1),
                                       limit_num=10,
                                       priv_type=2)
        r = sql.query_privileges._tb_priv(user=self.user, instance=self.slave, db_name=self.db_name,
                                          tb_name='table_name')
        self.assertTrue(r)

    @patch('sql.query_privileges._db_priv')
    def test_priv_limit_from_db(self, __db_priv):
        """
        测试用户获取查询数量限制，通过库名获取
        :return:
        """
        __db_priv.return_value = 10
        r = sql.query_privileges._priv_limit(user=self.user, instance=self.slave, db_name=self.db_name)
        self.assertEqual(r, 10)

    @patch('sql.query_privileges._tb_priv')
    @patch('sql.query_privileges._db_priv')
    def test_priv_limit_from_tb(self, __db_priv, __tb_priv):
        """
        测试用户获取查询数量限制，通过表名获取
        :return:
        """
        __db_priv.return_value = 10
        __tb_priv.return_value = 1
        r = sql.query_privileges._priv_limit(user=self.user, instance=self.slave, db_name=self.db_name, tb_name='test')
        self.assertEqual(r, 1)

    @patch('sql.engines.inception.InceptionEngine.query_print')
    def test_table_ref(self, _query_print):
        """
        测试通过inception获取查询语句的table_ref
        :return:
        """
        _query_print.return_value = {'command': 'select', 'select_list': [{'type': 'FIELD_ITEM', 'field': '*'}],
                                     'table_ref': [{'db': 'archery', 'table': 'sql_users'}],
                                     'limit': {'limit': [{'type': 'INT_ITEM', 'value': '10'}]}}

        r = sql.query_privileges._table_ref('select * from archery.sql_users;', self.slave, self.db_name)
        self.assertListEqual(r, [{'db': 'archery', 'table': 'sql_users'}])

    @patch('sql.engines.inception.InceptionEngine.query_print')
    def test_table_ref_wrong(self, _query_print):
        """
        测试通过inception获取查询语句的table_ref
        :return:
        """
        _query_print.return_value = {'command': 'select', 'select_list': [{'type': 'FIELD_ITEM', 'field': '*'}],
                                     'table_ref': [{'db': '', 'table': '*'}],
                                     'limit': {'limit': [{'type': 'INT_ITEM', 'value': '10'}]}}
        with self.assertRaises(RuntimeError):
            sql.query_privileges._table_ref('select * from archery.sql_users;', self.slave, self.db_name)

    def test_query_priv_check_super(self):
        """
        测试用户权限校验，超级管理员不做校验，直接返回系统配置的limit
        :return:
        """
        r = sql.query_privileges.query_priv_check(user=self.superuser,
                                                  instance=self.slave, db_name=self.db_name,
                                                  sql_content="select * from archery.sql_users;",
                                                  limit_num=100)
        self.assertDictEqual(r, {'status': 0, 'msg': 'ok', 'data': {'priv_check': True, 'limit_num': 100}})

    @patch('sql.query_privileges._table_ref', return_value=[{'db': 'archery', 'table': 'sql_users'}])
    @patch('sql.query_privileges._tb_priv', return_value=False)
    @patch('sql.query_privileges._db_priv', return_value=False)
    def test_query_priv_check_no_priv(self, __db_priv, __tb_priv, __table_ref):
        """
        测试用户权限校验，mysql实例、普通用户 无库表权限，inception语法树正常打印
        :return:
        """
        r = sql.query_privileges.query_priv_check(user=self.user,
                                                  instance=self.slave, db_name=self.db_name,
                                                  sql_content="select * from archery.sql_users;",
                                                  limit_num=100)
        self.assertDictEqual(r, {'status': 1, 'msg': '你无test_archery.sql_users表的查询权限！请先到查询权限管理进行申请',
                                 'data': {'priv_check': True, 'limit_num': 0}})

    @patch('sql.query_privileges._table_ref', return_value=[{'db': 'archery', 'table': 'sql_users'}])
    @patch('sql.query_privileges._tb_priv', return_value=False)
    @patch('sql.query_privileges._db_priv', return_value=1000)
    def test_query_priv_check_db_priv_exist(self, __db_priv, __tb_priv, __table_ref):
        """
        测试用户权限校验，mysql实例、普通用户 有库权限，inception语法树正常打印
        :return:
        """
        r = sql.query_privileges.query_priv_check(user=self.user,
                                                  instance=self.slave, db_name=self.db_name,
                                                  sql_content="select * from archery.sql_users;",
                                                  limit_num=100)
        self.assertDictEqual(r, {'data': {'limit_num': 100, 'priv_check': True}, 'msg': 'ok', 'status': 0})

    @patch('sql.query_privileges._table_ref', return_value=[{'db': 'archery', 'table': 'sql_users'}])
    @patch('sql.query_privileges._tb_priv', return_value=10)
    @patch('sql.query_privileges._db_priv', return_value=False)
    def test_query_priv_check_tb_priv_exist(self, __db_priv, __tb_priv, __table_ref):
        """
        测试用户权限校验，mysql实例、普通用户 ，有表权限，inception语法树正常打印
        :return:
        """
        r = sql.query_privileges.query_priv_check(user=self.user,
                                                  instance=self.slave, db_name=self.db_name,
                                                  sql_content="select * from archery.sql_users;",
                                                  limit_num=100)
        self.assertDictEqual(r, {'data': {'limit_num': 10, 'priv_check': True}, 'msg': 'ok', 'status': 0})

    @patch('sql.query_privileges._table_ref', return_value=RuntimeError())
    @patch('sql.query_privileges._tb_priv', return_value=False)
    @patch('sql.query_privileges._db_priv', return_value=False)
    def test_query_priv_check_table_ref_Exception_and_no_db_priv(self, __db_priv, __tb_priv, __table_ref):
        """
        测试用户权限校验，mysql实例、普通用户 ，inception语法树抛出异常，query_check开启，无库权限
        :return:
        """
        self.sys_config.set('query_check', 'true')
        self.sys_config.get_all_config()
        r = sql.query_privileges.query_priv_check(user=self.user,
                                                  instance=self.slave, db_name=self.db_name,
                                                  sql_content="select * from archery.sql_users;",
                                                  limit_num=100)
        self.assertDictEqual(r, {'status': 1,
                                 'msg': "你无test_archery数据库的查询权限！请先到查询权限管理进行申请",
                                 'data': {'priv_check': True, 'limit_num': 0}})

    @patch('sql.query_privileges._table_ref', return_value=RuntimeError())
    @patch('sql.query_privileges._tb_priv', return_value=False)
    @patch('sql.query_privileges._db_priv', return_value=1000)
    def test_query_priv_check_table_ref_Exception_and_open_query_check(self, __db_priv, __tb_priv, __table_ref):
        """
        测试用户权限校验，mysql实例、普通用户 ，有表权限，inception语法树抛出异常，query_check开启，有库权限
        :return:
        """
        self.sys_config.set('query_check', 'true')
        self.sys_config.get_all_config()
        r = sql.query_privileges.query_priv_check(user=self.user,
                                                  instance=self.slave, db_name=self.db_name,
                                                  sql_content="select * from archery.sql_users;",
                                                  limit_num=100)
        self.assertDictEqual(r, {'status': 1,
                                 'msg': "无法校验查询语句权限，请检查语法是否正确或联系管理员，错误信息：'RuntimeError' object is not iterable",
                                 'data': {'priv_check': True, 'limit_num': 0}})

    @patch('sql.query_privileges._table_ref', return_value=RuntimeError())
    @patch('sql.query_privileges._tb_priv', return_value=False)
    @patch('sql.query_privileges._db_priv', return_value=1000)
    def test_query_priv_check_table_ref_Exception_and_close_query_check(self, __db_priv, __tb_priv, __table_ref):
        """
        测试用户权限校验，mysql实例、普通用户 ，有表权限，inception语法树抛出异常，query_check关闭，有库权限
        :return:
        """
        self.sys_config.set('query_check', 'false')
        self.sys_config.get_all_config()
        r = sql.query_privileges.query_priv_check(user=self.user,
                                                  instance=self.slave, db_name=self.db_name,
                                                  sql_content="select * from archery.sql_users;",
                                                  limit_num=100)
        self.assertDictEqual(r, {'data': {'limit_num': 100, 'priv_check': False}, 'msg': 'ok', 'status': 0})

    @patch('sql.query_privileges._db_priv', return_value=1000)
    def test_query_priv_check_not_mysql_db_priv_exist(self, __db_priv):
        """
        测试用户权限校验，非mysql实例、普通用户 有库权限
        :return:
        """
        mssql_instance = Instance(instance_name='mssql', type='slave', db_type='mssql',
                                  host='some_host', port=3306, user='some_user', password='some_password')
        r = sql.query_privileges.query_priv_check(user=self.user,
                                                  instance=mssql_instance, db_name=self.db_name,
                                                  sql_content="select * from archery.sql_users;",
                                                  limit_num=100)
        self.assertDictEqual(r, {'data': {'limit_num': 100, 'priv_check': True}, 'msg': 'ok', 'status': 0})

    @patch('sql.query_privileges._db_priv', return_value=False)
    def test_query_priv_check_not_mysql_db_priv_not_exist(self, __db_priv):
        """
        测试用户权限校验，非mysql实例、普通用户 无库权限
        :return:
        """
        mssql_instance = Instance(instance_name='mssql', type='slave', db_type='mssql',
                                  host='some_host', port=3306, user='some_user', password='some_password')
        r = sql.query_privileges.query_priv_check(user=self.user,
                                                  instance=mssql_instance, db_name=self.db_name,
                                                  sql_content="select * from archery.sql_users;",
                                                  limit_num=100)
        self.assertDictEqual(r, {'data': {'limit_num': 0, 'priv_check': True},
                                 'msg': '你无test_archery数据库的查询权限！请先到查询权限管理进行申请',
                                 'status': 1})


class TestQueryPrivilegesApply(TestCase):
    """测试权限列表、权限管理"""

    def setUp(self):
        self.superuser = User.objects.create(username='super', is_superuser=True)
        self.user = User.objects.create(username='user')
        # 使用 travis.ci 时实例和测试service保持一致
        self.slave = Instance.objects.create(instance_name='test_instance', type='slave', db_type='mysql',
                                             host=settings.DATABASES['default']['HOST'],
                                             port=settings.DATABASES['default']['PORT'],
                                             user=settings.DATABASES['default']['USER'],
                                             password=settings.DATABASES['default']['PASSWORD'])
        self.db_name = settings.DATABASES['default']['TEST']['NAME']
        self.sys_config = SysConfig()
        self.client = Client()
        tomorrow = datetime.today() + timedelta(days=1)
        self.group = ResourceGroup.objects.create(group_id=1, group_name='group_name')
        self.query_apply_1 = QueryPrivilegesApply.objects.create(
            group_id=self.group.group_id,
            group_name=self.group.group_name,
            title='some_title1',
            user_name='some_user',
            instance=self.slave,
            db_list='some_db,some_db2',
            limit_num=100,
            valid_date=tomorrow,
            priv_type=1,
            status=0,
            audit_auth_groups='some_audit_group'
        )
        self.query_apply_2 = QueryPrivilegesApply.objects.create(
            group_id=2,
            group_name='some_group2',
            title='some_title2',
            user_name='some_user',
            instance=self.slave,
            db_list='some_db',
            table_list='some_table,some_tb2',
            limit_num=100,
            valid_date=tomorrow,
            priv_type=2,
            status=0,
            audit_auth_groups='some_audit_group'
        )

    def tearDown(self):
        self.superuser.delete()
        self.user.delete()
        Instance.objects.all().delete()
        ResourceGroup.objects.all().delete()
        QueryPrivilegesApply.objects.all().delete()
        QueryPrivileges.objects.all().delete()
        self.sys_config.replace(json.dumps({}))

    def test_query_audit_call_back(self):
        """测试权限申请工单回调"""
        # 工单状态改为审核失败, 验证工单状态
        sql.query_privileges._query_apply_audit_call_back(self.query_apply_1.apply_id, 2)
        self.query_apply_1.refresh_from_db()
        self.assertEqual(self.query_apply_1.status, 2)
        for db in self.query_apply_1.db_list.split(','):
            self.assertEqual(len(QueryPrivileges.objects.filter(
                user_name=self.query_apply_1.user_name,
                db_name=db,
                limit_num=100)), 0)
        # 工单改为审核成功, 验证工单状态和权限状态
        sql.query_privileges._query_apply_audit_call_back(self.query_apply_1.apply_id, 1)
        self.query_apply_1.refresh_from_db()
        self.assertEqual(self.query_apply_1.status, 1)
        for db in self.query_apply_1.db_list.split(','):
            self.assertEqual(len(QueryPrivileges.objects.filter(
                user_name=self.query_apply_1.user_name,
                db_name=db,
                limit_num=100)), 1)
        # 表权限申请测试, 只测试审核成功
        sql.query_privileges._query_apply_audit_call_back(self.query_apply_2.apply_id, 1)
        self.query_apply_2.refresh_from_db()
        self.assertEqual(self.query_apply_2.status, 1)
        for tb in self.query_apply_2.table_list.split(','):
            self.assertEqual(len(QueryPrivileges.objects.filter(
                user_name=self.query_apply_2.user_name,
                db_name=self.query_apply_2.db_list,
                table_name=tb,
                limit_num=self.query_apply_2.limit_num)), 1)

    def test_query_priv_apply_list_super_with_search(self):
        """
        测试权限申请列表，管理员查看所有用户，并且搜索
        """
        data = {
            "limit": 14,
            "offset": 0,
            "search": 'some_title1'
        }
        self.client.force_login(self.superuser)
        r = self.client.post(path='/query/applylist/', data=data)
        self.assertEqual(json.loads(r.content)['total'], 1)
        keys = list(json.loads(r.content)['rows'][0].keys())
        self.assertListEqual(keys,
                             ['apply_id', 'title', 'instance__instance_name', 'db_list', 'priv_type', 'table_list',
                              'limit_num', 'valid_date', 'user_display', 'status', 'create_time', 'group_name'])

    def test_query_priv_apply_list_with_query_review_perm(self):
        """
        测试权限申请列表，普通用户，拥有sql.query_review权限，在组内
        """
        data = {
            "limit": 14,
            "offset": 0,
            "search": ''
        }

        menu_queryapplylist = Permission.objects.get(codename='menu_queryapplylist')
        self.user.user_permissions.add(menu_queryapplylist)
        query_review = Permission.objects.get(codename='query_review')
        self.user.user_permissions.add(query_review)
        ResourceGroupRelations.objects.create(object_type=0, object_id=self.user.id, group_id=self.group.group_id)
        self.client.force_login(self.user)
        r = self.client.post(path='/query/applylist/', data=data)
        self.assertEqual(json.loads(r.content)['total'], 1)
        keys = list(json.loads(r.content)['rows'][0].keys())
        self.assertListEqual(keys,
                             ['apply_id', 'title', 'instance__instance_name', 'db_list', 'priv_type', 'table_list',
                              'limit_num', 'valid_date', 'user_display', 'status', 'create_time', 'group_name'])

    def test_query_priv_apply_list_no_query_review_perm(self):
        """
        测试权限申请列表，普通用户，无sql.query_review权限，在组内
        """
        data = {
            "limit": 14,
            "offset": 0,
            "search": ''
        }

        menu_queryapplylist = Permission.objects.get(codename='menu_queryapplylist')
        self.user.user_permissions.add(menu_queryapplylist)
        ResourceGroupRelations.objects.create(object_type=0, object_id=self.user.id, group_id=self.group.group_id)
        self.client.force_login(self.user)
        r = self.client.post(path='/query/applylist/', data=data)
        self.assertEqual(json.loads(r.content), {"total": 0, "rows": []})

    def test_user_query_priv_with_search(self):
        """
        测试权限申请列表，管理员查看所有用户，并且搜索
        """
        data = {
            "limit": 14,
            "offset": 0,
            "search": 'user'
        }
        QueryPrivileges.objects.create(user_name=self.user.username,
                                       user_display='user2',
                                       instance=self.slave,
                                       db_name=self.db_name,
                                       table_name='table_name',
                                       valid_date=date.today() + timedelta(days=1),
                                       limit_num=10,
                                       priv_type=2)
        self.client.force_login(self.superuser)
        r = self.client.post(path='/query/userprivileges/', data=data)
        self.assertEqual(json.loads(r.content)['total'], 1)
        keys = list(json.loads(r.content)['rows'][0].keys())
        self.assertListEqual(keys,
                             ['privilege_id', 'user_display', 'instance__instance_name', 'db_name', 'priv_type',
                              'table_name', 'limit_num', 'valid_date'])

    def test_user_query_priv_with_query_mgtpriv(self):
        """
        测试权限申请列表，普通用户，拥有sql.query_mgtpriv权限，在组内
        """
        data = {
            "limit": 14,
            "offset": 0,
            "search": 'user'
        }
        QueryPrivileges.objects.create(user_name='some_name',
                                       user_display='user2',
                                       instance=self.slave,
                                       db_name=self.db_name,
                                       table_name='table_name',
                                       valid_date=date.today() + timedelta(days=1),
                                       limit_num=10,
                                       priv_type=2)
        menu_queryapplylist = Permission.objects.get(codename='menu_queryapplylist')
        self.user.user_permissions.add(menu_queryapplylist)
        query_mgtpriv = Permission.objects.get(codename='query_mgtpriv')
        self.user.user_permissions.add(query_mgtpriv)
        ResourceGroupRelations.objects.create(object_type=0, object_id=self.user.id, group_id=self.group.group_id)
        self.client.force_login(self.user)
        r = self.client.post(path='/query/userprivileges/', data=data)
        self.assertEqual(json.loads(r.content)['total'], 1)
        keys = list(json.loads(r.content)['rows'][0].keys())
        self.assertListEqual(keys,
                             ['privilege_id', 'user_display', 'instance__instance_name', 'db_name', 'priv_type',
                              'table_name', 'limit_num', 'valid_date'])

    def test_user_query_priv_no_query_mgtpriv(self):
        """
        测试权限申请列表，普通用户，没有sql.query_mgtpriv权限，在组内
        """
        data = {
            "limit": 14,
            "offset": 0,
            "search": 'user'
        }
        QueryPrivileges.objects.create(user_name='some_name',
                                       user_display='user2',
                                       instance=self.slave,
                                       db_name=self.db_name,
                                       table_name='table_name',
                                       valid_date=date.today() + timedelta(days=1),
                                       limit_num=10,
                                       priv_type=2)
        menu_queryapplylist = Permission.objects.get(codename='menu_queryapplylist')
        self.user.user_permissions.add(menu_queryapplylist)
        ResourceGroupRelations.objects.create(object_type=0, object_id=self.user.id, group_id=self.group.group_id)
        self.client.force_login(self.user)
        r = self.client.post(path='/query/userprivileges/', data=data)
        self.assertEqual(json.loads(r.content), {"total": 0, "rows": []})


class TestQuery(TransactionTestCase):
    def setUp(self):
        self.slave1 = Instance(instance_name='test_slave_instance', type='slave', db_type='mysql',
                               host='testhost', port=3306, user='mysql_user', password='mysql_password')
        self.slave2 = Instance(instance_name='test_instance_non_mysql', type='slave', db_type='mssql',
                               host='some_host2', port=3306, user='some_user', password='some_password')
        self.slave1.save()
        self.slave2.save()
        self.superuser1 = User.objects.create(username='super1', is_superuser=True)
        self.u1 = User.objects.create(username='test_user', display='中文显示', is_active=True)
        self.u2 = User.objects.create(username='test_user2', display='中文显示', is_active=True)
        sql_query_perm = Permission.objects.get(codename='query_submit')
        self.u2.user_permissions.add(sql_query_perm)

    def tearDown(self):
        QueryPrivileges.objects.all().delete()
        self.u1.delete()
        self.u2.delete()
        self.superuser1.delete()
        self.slave1.delete()
        self.slave2.delete()
        archer_config = SysConfig()
        archer_config.set('disable_star', False)

    @patch('sql.query.fetch')
    @patch('sql.query.async_task')
    @patch('sql.engines.mysql.MysqlEngine.query')
    @patch('sql.query.query_priv_check')
    def testCorrectSQL(self, _priv_check, _query, _async_task, _fetch):
        c = Client()
        some_sql = 'select some from some_table limit 100;'
        some_db = 'some_db'
        some_limit = 100
        c.force_login(self.u1)
        r = c.post('/query/', data={'instance_name': self.slave1.instance_name,
                                    'sql_content': some_sql,
                                    'db_name': some_db,
                                    'limit_num': some_limit})
        self.assertEqual(r.status_code, 403)
        c.force_login(self.u2)
        q_result = ResultSet(full_sql=some_sql, rows=['value'])
        q_result.column_list = ['some']

        _async_task.return_value = q_result
        _fetch.return_value.result = q_result
        _priv_check.return_value = {'status': 0, 'data': {'limit_num': 100, 'priv_check': True}}
        r = c.post('/query/', data={'instance_name': self.slave1.instance_name,
                                    'sql_content': some_sql,
                                    'db_name': some_db,
                                    'limit_num': some_limit})
        _async_task.assert_called_once_with(_query, db_name=some_db, sql=some_sql, limit_num=some_limit, timeout=60,
                                            cached=60)
        r_json = r.json()
        self.assertEqual(r_json['data']['rows'], ['value'])
        self.assertEqual(r_json['data']['column_list'], ['some'])

    @patch('sql.query.fetch')
    @patch('sql.query.async_task')
    @patch('sql.engines.mysql.MysqlEngine.query')
    @patch('sql.query.query_priv_check')
    def testSQLWithoutLimit(self, _priv_check, _query, _async_task, _fetch):
        c = Client()
        some_limit = 100
        sql_without_limit = 'select some from some_table'
        sql_with_limit = 'select some from some_table limit {0};'.format(some_limit)
        some_db = 'some_db'
        c.force_login(self.u2)
        q_result = ResultSet(full_sql=sql_without_limit, rows=['value'])
        q_result.column_list = ['some']
        _async_task.return_value = q_result
        _fetch.return_value.result = q_result
        _fetch.return_value.time_taken.return_value = 1
        _priv_check.return_value = {'status': 0, 'data': {'limit_num': 100, 'priv_check': True}}
        r = c.post('/query/', data={'instance_name': self.slave1.instance_name,
                                    'sql_content': sql_without_limit,
                                    'db_name': some_db,
                                    'limit_num': some_limit})
        _async_task.assert_called_once_with(_query, db_name=some_db, sql=sql_with_limit, limit_num=some_limit,
                                            timeout=60, cached=60)
        r_json = r.json()
        self.assertEqual(r_json['data']['rows'], ['value'])
        self.assertEqual(r_json['data']['column_list'], ['some'])

        # 带 * 且不带 limit 的sql
        sql_with_star = 'select * from some_table'
        filtered_sql_with_star = 'select * from some_table limit {0};'.format(some_limit)
        _async_task.reset_mock()
        c.post('/query/', data={'instance_name': self.slave1.instance_name,
                                'sql_content': sql_with_star,
                                'db_name': some_db,
                                'limit_num': some_limit})
        _async_task.assert_called_once_with(_query, db_name=some_db, sql=filtered_sql_with_star, limit_num=some_limit,
                                            timeout=60, cached=60)

    @patch('sql.query.query_priv_check')
    def testStarOptionOn(self, _priv_check):
        c = Client()
        c.force_login(self.u2)
        some_limit = 100
        sql_with_star = 'select * from some_table'
        some_db = 'some_db'
        _priv_check.return_value = {'status': 0, 'data': {'limit_num': 100, 'priv_check': True}}
        archer_config = SysConfig()
        archer_config.set('disable_star', True)
        r = c.post('/query/', data={'instance_name': self.slave1.instance_name,
                                    'sql_content': sql_with_star,
                                    'db_name': some_db,
                                    'limit_num': some_limit})
        archer_config.set('disable_star', False)
        r_json = r.json()
        self.assertEqual(1, r_json['status'])


class TestWorkflowView(TransactionTestCase):

    def setUp(self):
        self.now = datetime.now()
        can_view_permission = Permission.objects.get(codename='menu_sqlworkflow')
        can_execute_permission = Permission.objects.get(codename='sql_execute')
        can_execute_resource_permission = Permission.objects.get(codename='sql_execute_for_resource_group')
        self.u1 = User(username='some_user', display='用户1')
        self.u1.save()
        self.u1.user_permissions.add(can_view_permission)
        self.u2 = User(username='some_user2', display='用户2')
        self.u2.save()
        self.u2.user_permissions.add(can_view_permission)
        self.u3 = User(username='some_user3', display='用户3')
        self.u3.save()
        self.u3.user_permissions.add(can_view_permission)
        self.executor1 = User(username='some_executor', display='执行者')
        self.executor1.save()
        self.executor1.user_permissions.add(can_view_permission, can_execute_permission, can_execute_resource_permission)
        self.superuser1 = User(username='super1', is_superuser=True)
        self.superuser1.save()
        self.master1 = Instance(instance_name='test_master_instance', type='master', db_type='mysql',
                                host='testhost', port=3306, user='mysql_user', password='mysql_password')
        self.master1.save()
        self.wf1 = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer=self.u1.username,
            engineer_display=self.u1.display,
            audit_auth_groups='some_group',
            create_time=self.now - timedelta(days=1),
            status='workflow_finish',
            is_backup=True,
            instance=self.master1,
            db_name='some_db',
            syntax_type=1,
        )
        self.wfc1 = SqlWorkflowContent.objects.create(
            workflow=self.wf1,
            sql_content='some_sql',
            execute_result=json.dumps([{
                'id': 1,
                'sql': 'some_content'
            }])
        )
        self.wf2 = SqlWorkflow.objects.create(
            workflow_name='some_name2',
            group_id=1,
            group_name='g1',
            engineer=self.u2.username,
            engineer_display=self.u2.display,
            audit_auth_groups='some_group',
            create_time=self.now - timedelta(days=1),
            status='workflow_manreviewing',
            is_backup=True,
            instance=self.master1,
            db_name='some_db',
            syntax_type=1
        )
        self.wfc2 = SqlWorkflowContent.objects.create(
            workflow=self.wf2,
            sql_content='some_sql',
            execute_result=json.dumps([{
                'id': 1,
                'sql': 'some_content'
            }])
        )
        self.resource_group1 = ResourceGroup(
            group_name='some_group'
        )
        self.resource_group1.save()

    def tearDown(self):
        SqlWorkflowContent.objects.all().delete()
        SqlWorkflow.objects.all().delete()
        self.master1.delete()
        self.u1.delete()
        self.superuser1.delete()
        self.resource_group1.delete()

    def testWorkflowStatus(self):
        c = Client(header={})
        c.force_login(self.u1)
        r = c.post('/getWorkflowStatus/', {'workflow_id': self.wf1.id})
        r_json = r.json()
        self.assertEqual(r_json['status'], 'workflow_finish')

    @patch('sql.utils.workflow_audit.Audit.logs')
    @patch('sql.utils.workflow_audit.Audit.detail_by_workflow_id')
    @patch('sql.utils.workflow_audit.Audit.review_info')
    @patch('sql.utils.workflow_audit.Audit.can_review')
    def testWorkflowDetailView(self, _can_review, _review_info, _detail_by_id, _logs):
        _review_info.return_value = ('some_auth_group', 'current_auth_group')
        _can_review.return_value = False
        _detail_by_id.return_value.audit_id = 123
        _logs.return_value.latest('id').operation_info = ''
        c = Client()
        c.force_login(self.u1)
        r = c.get('/detail/{}/'.format(self.wf1.id))
        expected_status_display = r"""id="workflow_detail_disaply">已正常结束"""
        self.assertContains(r, expected_status_display)
        exepcted_status = r"""id="workflow_detail_status">workflow_finish"""
        self.assertContains(r, exepcted_status)

    def testWorkflowListView(self):
        c = Client()
        c.force_login(self.superuser1)
        r = c.post('/sqlworkflow_list/', {'limit': 10, 'offset': 0, 'navStatus': 'all'})
        r_json = r.json()
        self.assertEqual(r_json['total'], 2)
        # 列表按创建时间倒序排列, 第二个是wf1 , 是已正常结束
        self.assertEqual(r_json['rows'][1]['status'], 'workflow_finish')

        # u1拿到u1的
        c.force_login(self.u1)
        r = c.post('/sqlworkflow_list/', {'limit': 10, 'offset': 0, 'navStatus': 'all'})
        r_json = r.json()
        self.assertEqual(r_json['total'], 1)
        self.assertEqual(r_json['rows'][0]['id'], self.wf1.id)

        # u3拿到None
        c.force_login(self.u3)
        r = c.post('/sqlworkflow_list/', {'limit': 10, 'offset': 0, 'navStatus': 'all'})
        r_json = r.json()
        self.assertEqual(r_json['total'], 0)

    @patch('sql.utils.workflow_audit.Audit.detail_by_workflow_id')
    @patch('sql.utils.workflow_audit.Audit.audit')
    @patch('sql.utils.workflow_audit.Audit.can_review')
    def testWorkflowPassedView(self, _can_review, _audit, _detail_by_id):
        c = Client()
        c.force_login(self.superuser1)
        r = c.post('/passed/')
        self.assertContains(r, 'workflow_id参数为空.')
        _can_review.return_value = False
        r = c.post('/passed/', {'workflow_id': self.wf1.id})
        self.assertContains(r, '你无权操作当前工单！')
        _can_review.return_value = True
        _detail_by_id.return_value.audit_id = 123
        _audit.return_value = {
            "data": {
                "workflow_status": 1  # TODO 改为audit_success
            }
        }
        r = c.post('/passed/', data={'workflow_id': self.wf1.id, 'audit_remark': 'some_audit'}, follow=False)
        self.assertRedirects(r, '/detail/{}/'.format(self.wf1.id), fetch_redirect_response=False)
        self.wf1.refresh_from_db()
        self.assertEqual(self.wf1.status, 'workflow_review_pass')

    @patch('sql.sql_workflow.Audit.add_log')
    @patch('sql.sql_workflow.Audit.detail_by_workflow_id')
    @patch('sql.sql_workflow.can_execute')
    def test_workflow_execute(self, mock_can_excute, mock_detail_by_id, mock_add_log):
        c = Client()
        c.force_login(self.executor1)
        r = c.post('/execute/')
        self.assertContains(r, 'workflow_id参数为空.')
        mock_can_excute.return_value = False
        r = c.post('/execute/', data={'workflow_id': self.wf2.id})
        self.assertContains(r, '你无权操作当前工单！')
        mock_can_excute.return_value = True
        mock_detail_by_id = 123
        r = c.post('/execute/', data={'workflow_id': self.wf2.id, 'mode': 'manual'})
        self.wf2.refresh_from_db()
        self.assertEqual('workflow_finish_manual', self.wf2.status)

    @patch('sql.sql_workflow.Audit.add_log')
    @patch('sql.sql_workflow.Audit.detail_by_workflow_id')
    @patch('sql.sql_workflow.Audit.audit')
    # patch view里的can_cancel 而不是原始位置的can_cancel ,因为在调用时, 已经 import 了真的 can_cancel ,会导致mock失效
    # 在import 静态函数时需要注意这一点, 动态对象因为每次都会重新生成,也可以 mock 原函数/方法/对象
    # 参见 : https://docs.python.org/3/library/unittest.mock.html#where-to-patch
    @patch('sql.sql_workflow.can_cancel')
    def testWorkflowCancelView(self, _can_cancel, _audit, _detail_by_id, _add_log):
        c = Client()
        c.force_login(self.u2)
        r = c.post('/cancel/')
        self.assertContains(r, 'workflow_id参数为空.')
        r = c.post('/cancel/', data={'workflow_id': self.wf2.id})
        self.assertContains(r, '终止原因不能为空')
        _can_cancel.return_value = False
        r = c.post('/cancel/', data={'workflow_id': self.wf2.id, 'cancel_remark': 'some_reason'})
        self.assertContains(r, '你无权操作当前工单！')
        _can_cancel.return_value = True
        _detail_by_id = 123
        r = c.post('/cancel/', data={'workflow_id': self.wf2.id, 'cancel_remark': 'some_reason'})
        self.wf2.refresh_from_db()
        self.assertEqual('workflow_abort', self.wf2.status)

    @patch('sql.sql_workflow.async_task')
    @patch('sql.sql_workflow.Audit')
    @patch('sql.sql_workflow.get_engine')
    @patch('sql.sql_workflow.user_instances')
    def test_workflow_auto_review_view(self, mock_user_instances, mock_get_engine, mock_audit, mock_async_task):
        c = Client()
        c.force_login(self.superuser1)
        request_data = {
            'sql_content': "update some_db set some_key=\'some value\';",
            'workflow_name': 'some_title',
            'group_name': self.resource_group1.group_name,
            'group_id': self.resource_group1.group_id,
            'instance_name': self.master1.instance_name,
            'db_name': 'some_db',
            'is_backup': True,
            'notify_users': ''
        }
        mock_user_instances.return_value.get.return_value = None
        mock_get_engine.return_value.execute_check.return_value.warning_count = 0
        mock_get_engine.return_value.execute_check.return_value.error_count = 0
        mock_get_engine.return_value.execute_check.return_value.syntax_type = 0
        mock_get_engine.return_value.execute_check.return_value.rows = []
        mock_get_engine.return_value.execute_check.return_value.json.return_value = json.dumps([{
            "id": 1,
            "stage": "CHECKED",
            "errlevel": 0,
            "stagestatus": "Audit completed",
            "errormessage": "None", "sql": "use thirdservice_db", "affected_rows": 0,
            "sequence": "'0_0_0'", "backup_dbname": "None", "execute_time": "0", "sqlsha1": "",
            "actual_affected_rows": None}])
        mock_audit.settings.return_value = 'some_group,another_group'
        mock_audit.add.return_value = None
        mock_async_task.return_value = None
        r = c.post('/autoreview/', data=request_data, follow=False)
        self.assertIn('detail', r.url)
        workflow_id = int(re.search(r'\/detail\/(\d+)\/', r.url).groups()[0])
        self.assertEqual(request_data['workflow_name'], SqlWorkflow.objects.get(id=workflow_id).workflow_name)


class TestOptimize(TestCase):
    """
    测试SQL优化
    """

    def setUp(self):
        self.superuser = User(username='super', is_superuser=True)
        self.superuser.save()
        # 使用 travis.ci 时实例和测试service保持一致
        self.master = Instance(instance_name='test_instance', type='master', db_type='mysql',
                               host=settings.DATABASES['default']['HOST'],
                               port=settings.DATABASES['default']['PORT'],
                               user=settings.DATABASES['default']['USER'],
                               password=settings.DATABASES['default']['PASSWORD'])
        self.master.save()
        self.sys_config = SysConfig()
        self.client = Client()
        self.client.force_login(self.superuser)

    def tearDown(self):
        self.superuser.delete()
        self.master.delete()
        self.sys_config.replace(json.dumps({}))

    def test_sqladvisor(self):
        """
        测试SQLAdvisor报告
        :return:
        """
        r = self.client.post(path='/slowquery/optimize_sqladvisor/')
        self.assertEqual(json.loads(r.content), {'status': 1, 'msg': '页面提交参数可能为空', 'data': []})
        r = self.client.post(path='/slowquery/optimize_sqladvisor/',
                             data={"sql_content": "select 1;", "instance_name": "test_instance"})
        self.assertEqual(json.loads(r.content), {'status': 1, 'msg': '请配置SQLAdvisor路径！', 'data': []})
        self.sys_config.set('sqladvisor', '/opt/archery/src/plugins/sqladvisor')
        self.sys_config.get_all_config()
        r = self.client.post(path='/slowquery/optimize_sqladvisor/',
                             data={"sql_content": "select 1;", "instance_name": "test_instance"})
        self.assertEqual(json.loads(r.content)['status'], 0)

    def test_soar(self):
        """
        测试SOAR报告
        :return:
        """
        r = self.client.post(path='/slowquery/optimize_soar/')
        self.assertEqual(json.loads(r.content), {'status': 1, 'msg': '页面提交参数可能为空', 'data': []})
        r = self.client.post(path='/slowquery/optimize_soar/',
                             data={"sql": "select 1;", "instance_name": "test_instance", "db_name": "mysql"})
        self.assertEqual(json.loads(r.content), {'status': 1, 'msg': '请配置soar_path和test_dsn！', 'data': []})
        self.sys_config.set('soar', '/opt/archery/src/plugins/soar')
        self.sys_config.set('soar_test_dsn', 'root:@127.0.0.1:3306/information_schema')
        self.sys_config.get_all_config()
        r = self.client.post(path='/slowquery/optimize_soar/',
                             data={"sql": "select 1;", "instance_name": "test_instance", "db_name": "mysql"})
        self.assertEqual(json.loads(r.content)['status'], 0)

    def test_tuning(self):
        """
        测试SQLTuning报告
        :return:
        """
        data = {"sql_content": "select * from test_archery.sql_users;",
                "instance_name": "test_instance",
                "db_name": settings.DATABASES['default']['TEST']['NAME']
                }
        r = self.client.post(path='/slowquery/optimize_sqltuning/')
        self.assertEqual(json.loads(r.content), {'status': 1, 'msg': '实例不存在', 'data': []})

        # 获取sys_parm
        data['option[]'] = 'sys_parm'
        r = self.client.post(path='/slowquery/optimize_sqltuning/', data=data)
        self.assertListEqual(list(json.loads(r.content)['data'].keys()),
                             ['basic_information', 'sys_parameter', 'optimizer_switch', 'sqltext'])

        # 获取sql_plan
        data['option[]'] = 'sql_plan'
        r = self.client.post(path='/slowquery/optimize_sqltuning/', data=data)
        self.assertListEqual(list(json.loads(r.content)['data'].keys()),
                             ['optimizer_rewrite_sql', 'plan', 'sqltext'])

        # 获取obj_stat
        data['option[]'] = 'obj_stat'
        r = self.client.post(path='/slowquery/optimize_sqltuning/', data=data)
        self.assertListEqual(list(json.loads(r.content)['data'].keys()),
                             ['object_statistics', 'sqltext'])

        # 获取sql_profile
        data['option[]'] = 'sql_profile'
        r = self.client.post(path='/slowquery/optimize_sqltuning/', data=data)
        self.assertListEqual(list(json.loads(r.content)['data'].keys()), ['session_status', 'sqltext'])


class TestSchemaSync(TestCase):
    """
    测试SchemaSync
    """

    def setUp(self):
        self.superuser = User(username='super', is_superuser=True)
        self.superuser.save()
        # 使用 travis.ci 时实例和测试service保持一致
        self.master = Instance(instance_name='test_instance', type='master', db_type='mysql',
                               host=settings.DATABASES['default']['HOST'],
                               port=settings.DATABASES['default']['PORT'],
                               user=settings.DATABASES['default']['USER'],
                               password=settings.DATABASES['default']['PASSWORD'])
        self.master.save()
        self.sys_config = SysConfig()
        self.client = Client()
        self.client.force_login(self.superuser)

    def tearDown(self):
        self.superuser.delete()
        self.master.delete()
        self.sys_config.replace(json.dumps({}))

    def test_schema_sync(self):
        """
        测试SchemaSync
        :return:
        """
        data = {"instance_name": "test_instance",
                "db_name": "*",
                "target_instance_name": "test_instance",
                "target_db_name": "*",
                "sync_auto_inc": True,
                "sync_comments": False}
        r = self.client.post(path='/instance/schemasync/', data=data)
        self.assertEqual(json.loads(r.content)['status'], 1)
        self.assertEqual(json.loads(r.content)['msg'], '请配置SchemaSync路径！')
        self.sys_config.set('schemasync', '/opt/venv4schemasync/bin/schemasync')
        self.sys_config.get_all_config()
        r = self.client.post(path='/instance/schemasync/', data=data)
        self.assertEqual(json.loads(r.content)['status'], 0)


class TestAsync(TestCase):

    def setUp(self):
        self.now = datetime.now()
        self.u1 = User(username='some_user', display='用户1')
        self.u1.save()
        self.master1 = Instance(instance_name='test_master_instance', type='master', db_type='mysql',
                                host='testhost', port=3306, user='mysql_user', password='mysql_password')
        self.master1.save()
        self.wf1 = SqlWorkflow.objects.create(
            workflow_name='some_name2',
            group_id=1,
            group_name='g1',
            engineer=self.u1.username,
            engineer_display=self.u1.display,
            audit_auth_groups='some_group',
            create_time=self.now - timedelta(days=1),
            status='workflow_executing',
            is_backup=True,
            instance=self.master1,
            db_name='some_db',
            syntax_type=1,
        )
        self.wfc1 = SqlWorkflowContent.objects.create(
            workflow=self.wf1,
            sql_content='some_sql',
            execute_result=''
        )
        # 初始化工单执行返回对象
        self.task_result = MagicMock()
        self.task_result.args = [self.wf1.id]
        self.task_result.success = True
        self.task_result.stopped = self.now
        self.task_result.result.json.return_value = json.dumps([{
            'id': 1,
            'sql': 'some_content'}])
        self.task_result.result.warning = ''
        self.task_result.result.error = ''

    def tearDown(self):
        self.wf1.delete()
        self.u1.delete()
        self.task_result = None
        self.master1.delete()

    @patch('sql.utils.execute_sql.notify_for_execute')
    @patch('sql.utils.execute_sql.Audit')
    def test_call_back(self, mock_audit, mock_notify):
        mock_audit.detail_by_workflow_id.return_value.audit_id = 123
        mock_audit.add_log.return_value = 'any thing'
        execute_callback(self.task_result)
        mock_audit.detail_by_workflow_id.assert_called_with(workflow_id=self.wf1.id, workflow_type=ANY)
        mock_audit.add_log.assert_called_with(
            audit_id=123,
            operation_type=ANY,
            operation_type_desc=ANY,
            operation_info="执行结果：已正常结束",
            operator=ANY,
            operator_display=ANY,
        )
        mock_notify.assert_called_once()


class TestSQLAnalyze(TestCase):
    """
    测试SQL分析
    """

    def setUp(self):
        self.superuser = User(username='super', is_superuser=True)
        self.superuser.save()
        # 使用 travis.ci 时实例和测试service保持一致
        self.master = Instance(instance_name='test_instance', type='master', db_type='mysql',
                               host=settings.DATABASES['default']['HOST'],
                               port=settings.DATABASES['default']['PORT'],
                               user=settings.DATABASES['default']['USER'],
                               password=settings.DATABASES['default']['PASSWORD'])
        self.master.save()
        self.sys_config = SysConfig()
        self.client = Client()
        self.client.force_login(self.superuser)

    def tearDown(self):
        self.superuser.delete()
        self.master.delete()
        self.sys_config.replace(json.dumps({}))

    def test_generate_text_None(self):
        """
        测试解析SQL，text为空
        :return:
        """
        r = self.client.post(path='/sql_analyze/generate/', data={})
        self.assertEqual(json.loads(r.content), {'rows': [], 'total': 0})

    def test_generate_text_not_None(self):
        """
        测试解析SQL，text不为空
        :return:
        """
        text = "select * from sql_user;select * from sql_workflow;"
        r = self.client.post(path='/sql_analyze/generate/', data={"text": text})
        self.assertEqual(json.loads(r.content),
                         {"total": 2, "rows": [{"sql_id": 1, "sql": "select * from sql_user;"},
                                               {"sql_id": 2, "sql": "select * from sql_workflow;"}]}
                         )

    def test_analyze_text_None(self):
        """
        测试分析SQL，text为空
        :return:
        """
        r = self.client.post(path='/sql_analyze/analyze/', data={})
        self.assertEqual(json.loads(r.content), {'rows': [], 'total': 0})

    def test_analyze_text_not_None(self):
        """
        测试分析SQL，text不为空
        :return:
        """
        text = "select * from sql_user;select * from sql_workflow;"
        instance_name = self.master.instance_name
        db_name = settings.DATABASES['default']['TEST']['NAME']
        r = self.client.post(path='/sql_analyze/analyze/',
                             data={"text": text, "instance_name": instance_name, "db_name": db_name})
        self.assertListEqual(list(json.loads(r.content)['rows'][0].keys()), ['sql_id', 'sql', 'report'])


class TestBinLog(TestCase):
    """
    测试Binlog相关
    """

    def setUp(self):
        self.superuser = User(username='super', is_superuser=True)
        self.superuser.save()
        # 使用 travis.ci 时实例和测试service保持一致
        self.master = Instance(instance_name='test_instance', type='master', db_type='mysql',
                               host=settings.DATABASES['default']['HOST'],
                               port=settings.DATABASES['default']['PORT'],
                               user=settings.DATABASES['default']['USER'],
                               password=settings.DATABASES['default']['PASSWORD'])
        self.master.save()
        self.sys_config = SysConfig()
        self.client = Client()
        self.client.force_login(self.superuser)

    def tearDown(self):
        self.superuser.delete()
        self.master.delete()
        self.sys_config.replace(json.dumps({}))

    def test_binlog_list_instance_not_exist(self):
        """
        测试获取binlog列表，实例不存在
        :return:
        """
        data = {
            "instance_name": 'some_instance'
        }
        r = self.client.post(path='/binlog/list/', data=data)
        self.assertEqual(json.loads(r.content), {'status': 1, 'msg': '实例不存在', 'data': []})

    def test_binlog_list_instance(self):
        """
        测试获取binlog列表，实例存在
        :return:
        """
        data = {
            "instance_name": 'test_instance'
        }
        r = self.client.post(path='/binlog/list/', data=data)
        self.assertEqual(json.loads(r.content).get('status'), 0)

    def test_binlog2sql_path_not_exist(self):
        """
        测试获取解析binlog，path未设置
        :return:
        """
        data = {"instance_name": "test_instance",
                "save_sql": "false",
                "no_pk": "false",
                "flashback": "false",
                "back_interval": "",
                "num": "",
                "start_file": "mysql-bin.000045",
                "start_pos": "",
                "end_file": "",
                "end_pos": "",
                "stop_time": "",
                "start_time": "",
                "only_schemas": "",
                "only_dml": "true",
                "sql_type": ""}
        r = self.client.post(path='/binlog/binlog2sql/', data=data)
        self.assertEqual(json.loads(r.content), {'status': 1, 'msg': '可执行文件路径不能为空！', 'data': {}})

    @patch('sql.plugins.plugin.subprocess')
    def test_binlog2sql(self, _subprocess):
        """
        测试获取解析binlog，path设置
        :param _subprocess:
        :return:
        """
        self.sys_config.set('binlog2sql', '/opt/binlog2sql')
        self.sys_config.get_all_config()
        data = {"instance_name": "test_instance",
                "save_sql": "1",
                "no_pk": "false",
                "flashback": "false",
                "back_interval": "",
                "num": "1",
                "start_file": "mysql-bin.000045",
                "start_pos": "",
                "end_file": "",
                "end_pos": "",
                "stop_time": "",
                "start_time": "",
                "only_schemas": "",
                "only_dml": "true",
                "sql_type": ""}
        r = self.client.post(path='/binlog/binlog2sql/', data=data)
        self.assertEqual(json.loads(r.content), {"status": 0, "msg": "ok", "data": [{"sql": {}, "binlog_info": {}}]})

    @patch('builtins.iter')
    @patch('sql.plugins.plugin.subprocess')
    def test_binlog2sql_file(self, _subprocess, _iter):
        """
        测试保存文件
        :param _subprocess:
        :return:
        """
        args = {"instance_name": "test_instance",
                "save_sql": "1",
                "no_pk": "false",
                "flashback": "false",
                "back_interval": "",
                "num": "1",
                "start_file": "",
                "start_pos": "",
                "end_file": "",
                "end_pos": "",
                "stop_time": "",
                "start_time": "",
                "only_schemas": "",
                "only_dml": "true",
                "sql_type": "",
                "instance": self.master}
        _subprocess.Popen.return_value.stdout.return_value.readline.return_value = 'sql'
        _iter.return_value = ''
        r = binlog2sql_file(args=args, user=self.superuser)
        self.assertEqual(self.superuser, r[0])

    def test_del_binlog_instance_not_exist(self):
        """
        测试删除binlog，实例不存在
        :return:
        """
        data = {
            "instance_id": 0,
            "binlog": "mysql-bin.000001",
        }
        r = self.client.post(path='/binlog/del_log/', data=data)
        self.assertEqual(json.loads(r.content), {'status': 1, 'msg': '实例不存在', 'data': []})

    def test_del_binlog_binlog_not_exist(self):
        """
        测试删除binlog，实例存在,binlog 不存在
        :return:
        """
        data = {
            "instance_id": self.master.id,
            "binlog": ''
        }
        r = self.client.post(path='/binlog/del_log/', data=data)
        self.assertEqual(json.loads(r.content), {'status': 1, 'msg': 'Error:未选择binlog！', 'data': ''})

    @patch('sql.engines.mysql.MysqlEngine.query')
    @patch('sql.engines.get_engine')
    def test_del_binlog(self, _get_engine, _query):
        """
        测试删除binlog
        :return:
        """
        data = {
            "instance_id": self.master.id,
            "binlog": "mysql-bin.000001"
        }
        _query.return_value = ResultSet(full_sql='select 1')
        r = self.client.post(path='/binlog/del_log/', data=data)
        self.assertEqual(json.loads(r.content), {'status': 0, 'msg': '清理成功', 'data': ''})

    @patch('sql.engines.mysql.MysqlEngine.query')
    @patch('sql.engines.get_engine')
    def test_del_binlog_wrong(self, _get_engine, _query):
        """
        测试删除binlog
        :return:
        """
        data = {
            "instance_id": self.master.id,
            "binlog": "mysql-bin.000001"
        }
        _query.return_value = ResultSet(full_sql='select 1')
        _query.return_value.error = '清理失败'
        r = self.client.post(path='/binlog/del_log/', data=data)
        self.assertEqual(json.loads(r.content), {'status': 2, 'msg': '清理失败,Error:清理失败', 'data': ''})


class TestParam(TransactionTestCase):
    """
    测试实例参数修改
    """

    def setUp(self):
        self.superuser = User(username='super', is_superuser=True)
        self.superuser.save()
        # 使用 travis.ci 时实例和测试service保持一致
        self.master = Instance(instance_name='test_instance', type='master', db_type='mysql',
                               host=settings.DATABASES['default']['HOST'],
                               port=settings.DATABASES['default']['PORT'],
                               user=settings.DATABASES['default']['USER'],
                               password=settings.DATABASES['default']['PASSWORD'])
        self.master.save()
        self.client = Client()
        self.client.force_login(self.superuser)

    def tearDown(self):
        self.superuser.delete()
        self.master.delete()
        ParamTemplate.objects.all().delete()

    def test_param_list_instance_not_exist(self):
        """
        测试获取参数列表，实例不存在
        :return:
        """
        data = {
            "instance_id": 0
        }
        r = self.client.post(path='/param/list/', data=data)
        self.assertEqual(json.loads(r.content), {'status': 1, 'msg': '实例不存在', 'data': []})

    @patch('sql.engines.mysql.MysqlEngine.get_variables')
    @patch('sql.engines.get_engine')
    def test_param_list_instance_exist(self, _get_engine, _get_variables):
        """
        测试获取参数列表，实例存在
        :return:
        """
        data = {
            "instance_id": self.master.id,
            "editable": True
        }
        r = self.client.post(path='/param/list/', data=data)
        self.assertIsInstance(json.loads(r.content), list)

    def test_param_history(self):
        """
        测试获取参数修改历史
        :return:
        """
        data = {"instance_id": self.master.id,
                "search": "binlog",
                "limit": 14,
                "offset": 0}
        r = self.client.post(path='/param/history/', data=data)
        self.assertEqual(json.loads(r.content), {'rows': [], 'total': 0})

    @patch('sql.engines.mysql.MysqlEngine.set_variable')
    @patch('sql.engines.mysql.MysqlEngine.get_variables')
    @patch('sql.engines.get_engine')
    def test_param_edit_variable_not_config(self, _get_engine, _get_variables, _set_variable):
        """
        测试参数修改，参数未在模板配置
        :return:
        """
        data = {"instance_id": self.master.id,
                "variable_name": "1",
                "variable_value": "false"}
        r = self.client.post(path='/param/edit/', data=data)
        self.assertEqual(json.loads(r.content), {'data': [], 'msg': '请先在参数模板中配置该参数！', 'status': 1})

    @patch('sql.engines.mysql.MysqlEngine.set_variable')
    @patch('sql.engines.mysql.MysqlEngine.get_variables')
    @patch('sql.engines.get_engine')
    def test_param_edit_variable_not_change(self, _get_engine, _get_variables, _set_variable):
        """
        测试参数修改，已在参数模板配置，但是值无变化
        :return:
        """
        _get_variables.return_value.rows = (('binlog_format', 'ROW'),)
        _set_variable.return_value.error = None
        _set_variable.return_value.full_sql = "set global binlog_format='STATEMENT';"

        ParamTemplate.objects.create(db_type='mysql',
                                     variable_name='binlog_format',
                                     default_value='ROW',
                                     editable=True)
        data = {"instance_id": self.master.id,
                "variable_name": "binlog_format",
                "runtime_value": "ROW"}
        r = self.client.post(path='/param/edit/', data=data)
        self.assertEqual(json.loads(r.content), {'status': 1, 'msg': '参数值与实际运行值一致，未调整！', 'data': []})

    @patch('sql.engines.mysql.MysqlEngine.set_variable')
    @patch('sql.engines.mysql.MysqlEngine.get_variables')
    @patch('sql.engines.get_engine')
    def test_param_edit_variable_change(self, _get_engine, _get_variables, _set_variable):
        """
        测试参数修改，已在参数模板配置，且值有变化
        :return:
        """
        _get_variables.return_value.rows = (('binlog_format', 'ROW'),)
        _set_variable.return_value.error = None
        _set_variable.return_value.full_sql = "set global binlog_format='STATEMENT';"

        ParamTemplate.objects.create(db_type='mysql',
                                     variable_name='binlog_format',
                                     default_value='ROW',
                                     editable=True)
        data = {"instance_id": self.master.id,
                "variable_name": "binlog_format",
                "runtime_value": "STATEMENT"}
        r = self.client.post(path='/param/edit/', data=data)
        self.assertEqual(json.loads(r.content), {'status': 0, 'msg': '修改成功，请手动持久化到配置文件！', 'data': []})

    @patch('sql.engines.mysql.MysqlEngine.set_variable')
    @patch('sql.engines.mysql.MysqlEngine.get_variables')
    @patch('sql.engines.get_engine')
    def test_param_edit_variable_error(self, _get_engine, _get_variables, _set_variable):
        """
        测试参数修改，已在参数模板配置，修改抛错
        :return:
        """
        _get_variables.return_value.rows = (('binlog_format', 'ROW'),)
        _set_variable.return_value.error = '修改报错'
        _set_variable.return_value.full_sql = "set global binlog_format='STATEMENT';"

        ParamTemplate.objects.create(db_type='mysql',
                                     variable_name='binlog_format',
                                     default_value='ROW',
                                     editable=True)
        data = {"instance_id": self.master.id,
                "variable_name": "binlog_format",
                "runtime_value": "STATEMENT"}
        r = self.client.post(path='/param/edit/', data=data)
        self.assertEqual(json.loads(r.content), {'status': 1, 'msg': '设置错误，错误信息：修改报错', 'data': []})
