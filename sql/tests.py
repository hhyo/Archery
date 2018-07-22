from django.contrib.auth.models import Group
from django.test import TestCase
from django.test import Client
from sql.models import Users


class SignUpTests(TestCase):
    def setUp(self):
        """
        创建默认组给注册关联用户
        """
        self.client = Client()
        Group.objects.create(id=1, name='默认组')

    def test_sing_up_not_username(self):
        """
        用户名不能为空
        """
        response = self.client.post('/signup/', data={})
        self.assertContains(response, '用户名和密码不能为空', status_code=200)

    def test_sing_up_not_password(self):
        """
        密码不能为空
        """
        response = self.client.post('/signup/', data={'username': 'test'})
        self.assertContains(response, '用户名和密码不能为空', status_code=200)

    def test_sing_up_2password(self):
        """
        两次输入密码不一致
        """
        response = self.client.post('/signup/', data={'username': 'test', 'password': '123456', 'password2': '12345'})
        self.assertContains(response, '两次输入密码不一致', status_code=200)

    def test_sing_up_duplicate_uesrname(self):
        """
        用户名已存在
        """
        Users.objects.create(username='test', password='123456')
        response = self.client.post('/signup/',
                                    data={'username': 'test', 'password': '123456', 'password2': '123456'})
        self.assertContains(response, '用户名已存在', status_code=200)

    def test_sing_up(self):
        """
        注册成功
        """
        self.client.post('/signup/',
                         data={'username': 'test', 'password': '123456',
                               'password2': '123456', 'display': 'test', 'email': '123@123.com'})
        user = Users.objects.get(username='test')
        self.assertTrue(user)
