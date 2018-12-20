import json

from django.contrib.auth.models import Group
from django.test import TestCase
from django.test import Client
from sql.models import Users
from common.config import SysConfig

class SignUpTests(TestCase):
    def setUp(self):
        """
        创建默认组给注册关联用户, 打开注册
        """
        archer_config = SysConfig()
        archer_config.set('sign_up_enabled','true')
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
        self.assertEquals(data, content)

    def test_sing_up_not_password(self):
        """
        密码不能为空
        """
        response = self.client.post('/signup/', data={'username': 'test'})
        data = json.loads(response.content)
        content = {'status': 1, 'msg': '用户名和密码不能为空', 'data': None}
        self.assertEquals(data, content)

    def test_sing_up_2password(self):
        """
        两次输入密码不一致
        """
        response = self.client.post('/signup/', data={'username': 'test', 'password': '123456', 'password2': '12345'})
        data = json.loads(response.content)
        content = {'status': 1, 'msg': '两次输入密码不一致', 'data': None}
        self.assertEquals(data, content)

    def test_sing_up_duplicate_uesrname(self):
        """
        用户名已存在
        """
        Users.objects.create(username='test', password='123456')
        response = self.client.post('/signup/',
                                    data={'username': 'test', 'password': '123456', 'password2': '123456'})
        data = json.loads(response.content)
        content = {'status': 1, 'msg': '用户名已存在', 'data': None}
        self.assertEquals(data, content)

    def test_sing_up(self):
        """
        注册成功
        """
        self.client.post('/signup/',
                         data={'username': 'test', 'password': '123456test',
                               'password2': '123456test', 'display': 'test', 'email': '123@123.com'})
        user = Users.objects.get(username='test')
        self.assertTrue(user)


class ConfigOpsTests(TestCase):
    def setUp(self):
        pass
    def test_replace_configs(self):
        archer_config = SysConfig()
        new_config = json.dumps(
            [{'key': 'numconfig','value': 1},
            {'key':'strconfig','value':'strconfig'}, 
            {'key':'boolconfig','value':'false'}])
        archer_config.replace(new_config)
        archer_config.get_all_config()
        expected_config = {
            'numconfig': '1',
            'strconfig': 'strconfig',
            'boolconfig': False
            }
        self.assertEqual(archer_config.sys_config,expected_config)
    def test_get_bool_transform(self):
        bool_config = json.dumps([{'key':'boolconfig2','value':'false'}])
        archer_config = SysConfig()
        archer_config.replace(bool_config)
        archer_config.get_all_config()
        self.assertEqual(archer_config.sys_config['boolconfig2'], False)
    def test_set_bool_transform(self):
        archer_config = SysConfig()
        archer_config.set('boolconfig3', False)
        archer_config.get_all_config()
        self.assertEqual(archer_config.sys_config['boolconfig3'], False)
    def test_get_other_data(self):
        new_config = json.dumps([{'key':'other_config','value':'testvalue'}])
        archer_config = SysConfig()
        archer_config.replace(new_config)
        archer_config.get_all_config()
        self.assertEqual(archer_config.sys_config['other_config'], 'testvalue')
    def test_set_other_data(self):
        archer_config = SysConfig()
        archer_config.set('other_config','testvalue3')
        archer_config.get_all_config()
        self.assertEqual(archer_config.sys_config['other_config'], 'testvalue3')