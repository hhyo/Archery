import json
import smtplib
from unittest.mock import patch, Mock, MagicMock, ANY

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from common.config import SysConfig
from common.utils.sendmsg import MailSender
from sql.models import Instance
User = get_user_model()


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
        self.assertEqual(archer_config.sys_config['boolconfig2'], False)
    def test_set_bool_transform(self):
        archer_config = SysConfig()
        archer_config.set('boolconfig3', False)
        self.assertEqual(archer_config.sys_config['boolconfig3'], False)
    def test_get_other_data(self):
        new_config = json.dumps([{'key':'other_config','value':'testvalue'}])
        archer_config = SysConfig()
        archer_config.replace(new_config)
        self.assertEqual(archer_config.sys_config['other_config'], 'testvalue')
    def test_set_other_data(self):
        archer_config = SysConfig()
        archer_config.set('other_config','testvalue3')
        self.assertEqual(archer_config.sys_config['other_config'], 'testvalue3')


class SendMessageTest(TestCase):
    """发送消息测试"""

    def setUp(self):
        archer_config = SysConfig()
        self.smtp_server = 'test_smtp_server'
        self.smtp_user = 'test_smtp_user'
        self.smtp_password = 'some_password'
        self.smtp_port = 1234
        self.smtp_ssl = True
        archer_config.set('mail_smtp_server', self.smtp_server)
        archer_config.set('mail_smtp_user', self.smtp_user)
        archer_config.set('mail_smtp_password', self.smtp_password)
        archer_config.set('mail_smtp_port', self.smtp_port)
        archer_config.set('mail_ssl', self.smtp_ssl)

    def testSenderInit(self):
        sender = MailSender()
        self.assertEqual(sender.MAIL_REVIEW_SMTP_PORT, self.smtp_port)
        archer_config = SysConfig()
        archer_config.set('mail_smtp_port', '')
        sender = MailSender()
        self.assertEqual(sender.MAIL_REVIEW_SMTP_PORT, 465)
        archer_config.set('mail_ssl', False)
        sender = MailSender()
        self.assertEqual(sender.MAIL_REVIEW_SMTP_PORT, 25)

    @patch.object(smtplib.SMTP, '__init__', return_value=None)
    @patch.object(smtplib.SMTP, 'login')
    @patch.object(smtplib.SMTP, 'sendmail')
    @patch.object(smtplib.SMTP, 'quit')
    def testNoPasswordSendMail(self, _quit, sendmail, login, _):
        """无密码测试"""
        some_sub = 'test_subject'
        some_body = 'mail_body'
        some_to = ['mail_to']
        archer_config = SysConfig()
        archer_config.set('mail_ssl', '')

        archer_config.set('mail_smtp_password', '')
        sender2 = MailSender()
        sender2.send_email(some_sub, some_body, some_to)
        login.assert_not_called()

    @patch.object(smtplib.SMTP, '__init__', return_value=None)
    @patch.object(smtplib.SMTP, 'login')
    @patch.object(smtplib.SMTP, 'sendmail')
    @patch.object(smtplib.SMTP, 'quit')
    def testSendMail(self,_quit, sendmail, login, _):
        """有密码测试"""
        some_sub = 'test_subject'
        some_body = 'mail_body'
        some_to = ['mail_to']
        archer_config = SysConfig()
        archer_config.set('mail_ssl', '')
        archer_config.set('mail_smtp_password', self.smtp_password)
        sender = MailSender()
        sender.send_email(some_sub, some_body, some_to)
        login.assert_called_once()
        sendmail.assert_called_with(self.smtp_user, some_to, ANY)
        _quit.assert_called_once()

    @patch.object(smtplib.SMTP, '__init__', return_value=None)
    @patch.object(smtplib.SMTP, 'login')
    @patch.object(smtplib.SMTP, 'sendmail')
    @patch.object(smtplib.SMTP, 'quit')
    def testSSLSendMail(self, _quit, sendmail, login, _):
        """SSL 测试"""
        some_sub = 'test_subject'
        some_body = 'mail_body'
        some_to = ['mail_to']
        archer_config = SysConfig()
        archer_config.set('mail_ssl', True)
        sender = MailSender()
        sender.send_email(some_sub, some_body, some_to)
        sendmail.assert_called_with(self.smtp_user, some_to, ANY)
        _quit.assert_called_once()

    def tearDown(self):
        archer_config = SysConfig()
        archer_config.set('mail_smtp_server', '')
        archer_config.set('mail_smtp_user', '')
        archer_config.set('mail_smtp_password', '')
        archer_config.set('mail_smtp_port', '')
        archer_config.set('mail_ssl', '')


class DingTest(TestCase):

    def setUp(self):
        self.url = 'some_url'
        self.content = 'some_content'

    @patch('requests.post')
    def testDing(self, post):
        sender = MailSender()
        post.return_value.json.return_value = {'errcode': 0}
        with self.assertLogs('default', level='DEBUG') as lg:
            sender.send_ding(self.url, self.content)
            post.assert_called_once_with(url=self.url, json={
                'msgtype': 'text',
                'text': {
                    'content': self.content
                }
            })
            self.assertIn('钉钉推送成功', lg.output[0])
        post.return_value.json.return_value = {'errcode': 1, 'errmsg': 'test_error'}
        with self.assertLogs('default', level='ERROR') as lg:
            sender.send_ding(self.url, self.content)
            self.assertIn('test_error', lg.output[0])

    def tearDown(self):
        pass


class GlobalInfoTest(TestCase):
    def setUp(self):
        self.u1 = User(username='test_user', display='中文显示', is_active=True)
        self.u1.save()

    @patch('sql.utils.workflow_audit.Audit.todo')
    def testGlobalInfo(self, todo):
        """测试"""
        c = Client()
        r = c.get('/', follow=True)
        todo.assert_not_called()
        self.assertEqual(r.context['todo'], 0)
        # 已登录用户
        c.force_login(self.u1)
        todo.return_value = 3
        r = c.get('/', follow=True)
        todo.assert_called_once_with(self.u1)
        self.assertEqual(r.context['todo'], 3)
        # 报异常
        todo.side_effect = NameError('some exception')
        r = c.get('/', follow=True)
        self.assertEqual(r.context['todo'], 0)

    def tearDown(self):
        self.u1.delete()

class CheckTest(TestCase):

    def setUp(self):
        self.superuser1 = User(username='test_user', display='中文显示', is_active=True, is_superuser=True,
                               email='XXX@xxx.com')
        self.superuser1.save()
        self.slave1 = Instance(instance_name='some_name', host='some_host', type='slave', db_type='mysql',
                               user='some_user', port=1234, password='some_password')
        self.slave1.save()

    def tearDown(self):
            self.superuser1.delete()

    @patch.object(MailSender, '__init__', return_value=None)
    @patch.object(MailSender, 'send_email')
    def testEmailCheck(self, send_email, mailsender):
        mail_switch = 'true'
        smtp_ssl = 'false'
        smtp_server = 'some_server'
        smtp_port = '1234'
        smtp_user = 'some_user'
        smtp_pass = 'some_pass'
        # 略过superuser校验
        # 未开启mail开关
        mail_switch = 'false'
        c = Client()
        c.force_login(self.superuser1)
        r = c.post('/check/email/', data={
            'mail': mail_switch,
            'mail_ssl': smtp_ssl,
            'mail_smtp_server': smtp_server,
            'mail_smtp_port': smtp_port,
            'mail_smtp_user': smtp_user,
            'mail_smtp_password': smtp_pass
        })
        r_json = r.json()
        self.assertEqual(r_json['status'], 1)
        self.assertEqual(r_json['msg'], '请先开启邮件通知！')
        mail_switch = 'true'
        # 填写非正整数端口号
        smtp_port = '-3'
        r = c.post('/check/email/', data={
            'mail': mail_switch,
            'mail_ssl': smtp_ssl,
            'mail_smtp_server': smtp_server,
            'mail_smtp_port': smtp_port,
            'mail_smtp_user': smtp_user,
            'mail_smtp_password': smtp_pass
        })
        r_json = r.json()
        self.assertEqual(r_json['status'], 1)
        self.assertEqual(r_json['msg'], '端口号只能为正整数')
        smtp_port = '1234'
        # 未填写用户邮箱
        self.superuser1.email = ''
        self.superuser1.save()
        r = c.post('/check/email/', data={
            'mail': mail_switch,
            'mail_ssl': smtp_ssl,
            'mail_smtp_server': smtp_server,
            'mail_smtp_port': smtp_port,
            'mail_smtp_user': smtp_user,
            'mail_smtp_password': smtp_pass
        })
        r_json = r.json()
        self.assertEqual(r_json['status'], 1)
        self.assertEqual(r_json['msg'], '请先完善当前用户邮箱信息！')
        self.superuser1.email = 'XXX@xxx.com'
        self.superuser1.save()
        # 发送失败, 显示traceback
        send_email.return_value = 'some traceback'
        r = c.post('/check/email/', data={
            'mail': mail_switch,
            'mail_ssl': smtp_ssl,
            'mail_smtp_server': smtp_server,
            'mail_smtp_port': smtp_port,
            'mail_smtp_user': smtp_user,
            'mail_smtp_password': smtp_pass
        })
        r_json = r.json()
        self.assertEqual(r_json['status'], 1)
        self.assertIn('some traceback', r_json['msg'])
        send_email.reset_mock()  # 重置``Mock``的调用计数
        mailsender.reset_mock()
        # 发送成功
        send_email.return_value = 'success'
        r = c.post('/check/email/', data={
            'mail': mail_switch,
            'mail_ssl': smtp_ssl,
            'mail_smtp_server': smtp_server,
            'mail_smtp_port': smtp_port,
            'mail_smtp_user': smtp_user,
            'mail_smtp_password': smtp_pass
        })
        r_json = r.json()
        mailsender.assert_called_once_with(server=smtp_server, port=int(smtp_port), user=smtp_user,
                                           password=smtp_pass, ssl=False)
        send_email.called_once_with('Archery 邮件发送测试', 'Archery 邮件发送测试...',
                                                           [self.superuser1.email])
        self.assertEqual(r_json['status'], 0)
        self.assertEqual(r_json['msg'], 'ok')

    @patch('MySQLdb.connect')
    def testInstanceCheck(self, connect):
        cur = MagicMock()
        cur.return_value.execute = MagicMock()
        cur.return_value.close = MagicMock()
        connect.return_value.cursor = cur
        connect.return_value.close = MagicMock()

        c = Client()
        c.force_login(self.superuser1)
        r = c.post('/check/instance/', data={'instance_id': self.slave1.id})
        r_json = r.json()
        self.assertEqual(r_json['status'], 0)
        connect.assert_called_once_with(host=self.slave1.host, port=self.slave1.port,
                                        user=self.slave1.user, passwd=self.slave1.raw_password, charset=ANY)
        cur.assert_called_once()
        cur.return_value.execute.assert_called_once()
        cur.return_value.close.assert_called_once()
        connect.return_value.close.assert_called_once()

        # exception
        cur.return_value.execute.side_effect = NameError('some error')
        r = c.post('/check/instance/', data={'instance_id': self.slave1.id})
        r_json = r.json()
        self.assertEqual(r_json['status'], 1)
        self.assertIn('无法连接实例', r_json['msg'])
        self.assertIn('some error', r_json['msg'])




