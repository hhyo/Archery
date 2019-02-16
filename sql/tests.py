import json
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.contrib.auth.models import Permission

from common.config import SysConfig
from sql.engines.models import ResultSet
from sql.models import Instance, ResourceGroup, ResourceGroupRelations, SqlWorkflow, QueryLog
from sql.engines.mysql import MysqlEngine
from sql import query

User = get_user_model()


class SignUpTests(TestCase):
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


class UserTest(TestCase):
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
        r = c.get('/login/', follow=False)
        self.assertRedirects(r, '/')


class QueryTest(TestCase):
    def setUp(self):
        self.slave1 = Instance(instance_name='test_slave_instance', type='slave', db_type='mysql',
                               host='testhost', port=3306, user='mysql_user', password='mysql_password')
        self.slave1.save()
        User = get_user_model()
        self.u1 = User(username='test_user', display='中文显示', is_active=True)
        self.u1.save()
        self.u2 = User(username='test_user2', display='中文显示', is_active=True)
        self.u2.save()
        sql_query_perm = Permission.objects.get(codename='query_submit')
        self.u2.user_permissions.add(sql_query_perm)

    def testcorrectSQL(self):
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

        mock_engine = MysqlEngine
        mock_engine.query = MagicMock(return_value=q_result)
        mock_engine.query_masking = MagicMock(return_value=q_result)

        mock_query = query
        mock_query.query_priv_check = MagicMock(return_value={'status': 0, 'data': {'limit_num': 100, 'priv_check': 1}})
        r = c.post('/query/', data={'instance_name': self.slave1.instance_name,
                                    'sql_content': some_sql,
                                    'db_name': some_db,
                                    'limit_num': some_limit})
        mock_engine.query.assert_called_once_with(db_name=some_db, sql=some_sql, limit_num=some_limit)
        r_json = r.json()
        self.assertEqual(r_json['data']['rows'], ['value'])
        self.assertEqual(r_json['data']['column_list'], ['some'])

    def testMasking(self):
        pass

    def tearDown(self):
        self.u1.delete()
        self.u2.delete()
        self.slave1.delete()


class SqlWorkflowListTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.super_user = User.objects.create_user(username='test_user', display='中文显示',
                                                   is_superuser=True, is_active=True, is_staff=True)
        self.client.force_login(self.super_user)
        SqlWorkflow.objects.create(id=1, workflow_name='工单名称1', status='审核通过', group_id=1,
                                   group_name='资源组', sql_syntax=1).save()
        SqlWorkflow.objects.create(id=2, workflow_name='工单名称2', status='等待审核人审核', group_id=1,
                                   group_name='资源组', sql_syntax=1).save()
        SqlWorkflow.objects.all().update(create_time='2019-02-14 00:00:00')

    def tearDown(self):
        self.super_user.delete()
        SqlWorkflow.objects.all().delete()

    def test_all(self):
        """
        获取所有SQL上线工单
        :return:
        """
        _json = {'limit': 14, 'offset': 0, 'navStatus': 'all'}
        r = self.client.post('/sqlworkflow_list/', data=_json)
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertDictEqual(data, {'total': 2, 'rows': [
            {'id': 1, 'workflow_name': '工单名称1', 'engineer_display': '', 'status': '审核通过', 'is_backup': '',
             'create_time': '2019-02-14 00:00:00', 'instance_name': '', 'db_name': '', 'group_name': '资源组',
             'sql_syntax': 1},
            {'id': 2, 'workflow_name': '工单名称2', 'engineer_display': '', 'status': '等待审核人审核', 'is_backup': '',
             'create_time': '2019-02-14 00:00:00', 'instance_name': '', 'db_name': '', 'group_name': '资源组',
             'sql_syntax': 1}]})

    def test_pass(self):
        """
        获取审核通过的SQL上线工单
        :return:
        """
        _json = {'limit': 14, 'offset': 0, 'navStatus': 'pass'}
        r = self.client.post('/sqlworkflow_list/', data=_json)
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertDictEqual(data, {'total': 1, 'rows': [
            {'id': 1, 'workflow_name': '工单名称1', 'engineer_display': '', 'status': '审核通过', 'is_backup': '',
             'create_time': '2019-02-14 00:00:00', 'instance_name': '', 'db_name': '', 'group_name': '资源组',
             'sql_syntax': 1}]})

    def test_wrong_status(self):
        """
        获取不存在的状态
        :return:
        """
        _json = {'limit': 14, 'offset': 0, 'navStatus': 'pass_test'}
        r = self.client.post('/sqlworkflow_list/', data=_json)
        self.assertContains(r, '传入的navStatus参数有误', status_code=200)
