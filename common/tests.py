import json
import smtplib
from unittest.mock import patch, Mock, MagicMock, ANY
import datetime
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from common.config import SysConfig
from common.utils.sendmsg import MsgSender
from sql.engines import EngineBase
from sql.models import Instance, SqlWorkflow, SqlWorkflowContent, QueryLog
from common.utils.chart_dao import ChartDao

User = get_user_model()


class ConfigOpsTests(TestCase):
    def setUp(self):
        pass

    def test_purge(self):
        archer_config = SysConfig()
        archer_config.set('some_key','some_value')
        archer_config.purge()
        self.assertEqual({}, archer_config.sys_config)
        archer_config2 = SysConfig()
        self.assertEqual({}, archer_config2.sys_config)

    def test_replace_configs(self):
        archer_config = SysConfig()
        new_config = json.dumps(
            [{'key': 'numconfig', 'value': 1},
             {'key': 'strconfig', 'value': 'strconfig'},
             {'key': 'boolconfig', 'value': 'false'}])
        archer_config.replace(new_config)
        archer_config.get_all_config()
        expected_config = {
            'numconfig': '1',
            'strconfig': 'strconfig',
            'boolconfig': False
        }
        self.assertEqual(archer_config.sys_config, expected_config)

    def test_get_bool_transform(self):
        bool_config = json.dumps([{'key': 'boolconfig2', 'value': 'false'}])
        archer_config = SysConfig()
        archer_config.replace(bool_config)
        self.assertEqual(archer_config.sys_config['boolconfig2'], False)

    def test_set_bool_transform(self):
        archer_config = SysConfig()
        archer_config.set('boolconfig3', False)
        self.assertEqual(archer_config.sys_config['boolconfig3'], False)

    def test_get_other_data(self):
        new_config = json.dumps([{'key': 'other_config', 'value': 'testvalue'}])
        archer_config = SysConfig()
        archer_config.replace(new_config)
        self.assertEqual(archer_config.sys_config['other_config'], 'testvalue')

    def test_set_other_data(self):
        archer_config = SysConfig()
        archer_config.set('other_config', 'testvalue3')
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
        sender = MsgSender()
        self.assertEqual(sender.MAIL_REVIEW_SMTP_PORT, self.smtp_port)
        archer_config = SysConfig()
        archer_config.set('mail_smtp_port', '')
        sender = MsgSender()
        self.assertEqual(sender.MAIL_REVIEW_SMTP_PORT, 465)
        archer_config.set('mail_ssl', False)
        sender = MsgSender()
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
        sender2 = MsgSender()
        sender2.send_email(some_sub, some_body, some_to)
        login.assert_not_called()

    @patch.object(smtplib.SMTP, '__init__', return_value=None)
    @patch.object(smtplib.SMTP, 'login')
    @patch.object(smtplib.SMTP, 'sendmail')
    @patch.object(smtplib.SMTP, 'quit')
    def testSendMail(self, _quit, sendmail, login, _):
        """有密码测试"""
        some_sub = 'test_subject'
        some_body = 'mail_body'
        some_to = ['mail_to']
        archer_config = SysConfig()
        archer_config.set('mail_ssl', '')
        archer_config.set('mail_smtp_password', self.smtp_password)
        sender = MsgSender()
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
        sender = MsgSender()
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
        sender = MsgSender()
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
    """检查功能测试"""

    def setUp(self):
        self.superuser1 = User(username='test_user', display='中文显示', is_active=True, is_superuser=True,
                               email='XXX@xxx.com')
        self.superuser1.save()
        self.slave1 = Instance(instance_name='some_name', host='some_host', type='slave', db_type='mysql',
                               user='some_user', port=1234, password='some_password')
        self.slave1.save()

    def tearDown(self):
        self.superuser1.delete()

    @patch.object(MsgSender, '__init__', return_value=None)
    @patch.object(MsgSender, 'send_email')
    def testEmailCheck(self, send_email, mailsender):
        """邮箱配置检查"""
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
    @patch('common.check.get_engine', return_value=EngineBase)
    def testInstanceCheck(self, _get_engine, _conn):
        _get_engine.return_value.get_connection = _conn
        c = Client()
        c.force_login(self.superuser1)
        r = c.post('/check/instance/', data={'instance_id': self.slave1.id})
        r_json = r.json()
        self.assertEqual(r_json['status'], 0)

    @patch('pymysql.connect')
    def test_inception_check(self, _conn):
        c = Client()
        c.force_login(self.superuser1)
        data = {
            "inception_host": "inception",
            "inception_port": "6669",
            "inception_remote_backup_host": "mysql",
            "inception_remote_backup_port": 3306,
            "inception_remote_backup_user": "mysql",
            "inception_remote_backup_password": "123456"
        }
        r = c.post('/check/inception/', data=data)
        r_json = r.json()
        self.assertEqual(r_json['status'], 0)

    @patch('pymysql.connect')
    def test_go_inception_check(self, _conn):
        c = Client()
        c.force_login(self.superuser1)
        data = {
            "go_inception_host": "inception",
            "go_inception_port": "6669",
            "inception_remote_backup_host": "mysql",
            "inception_remote_backup_port": 3306,
            "inception_remote_backup_user": "mysql",
            "inception_remote_backup_password": "123456"
        }
        r = c.post('/check/go_inception/', data=data)
        r_json = r.json()
        self.assertEqual(r_json['status'], 0)


class ChartTest(TestCase):
    """报表测试"""

    @classmethod
    def setUpClass(cls):
        cls.u1 = User(username='some_user', display='用户1')
        cls.u1.save()
        cls.u2 = User(username='some_other_user', display='用户2')
        cls.u2.save()
        cls.superuser1 = User(username='super1', is_superuser=True)
        cls.superuser1.save()
        cls.now = datetime.datetime.now()
        cls.slave1 = Instance(instance_name='test_slave_instance', type='slave', db_type='mysql',
                              host='testhost', port=3306, user='mysql_user', password='mysql_password')
        cls.slave1.save()
        # 批量创建数据 ddl ,u1 ,g1, yesterday 组, 2 个数据
        ddl_workflow = [SqlWorkflow(
            workflow_name='ddl %s' % i,
            group_id=1,
            group_name='g1',
            engineer=cls.u1.username,
            engineer_display=cls.u1.display,
            audit_auth_groups='some_group',
            create_time=cls.now - datetime.timedelta(days=1),
            status='workflow_finish',
            is_backup=True,
            instance=cls.slave1,
            db_name='some_db',
            syntax_type=1
        ) for i in range(2)]
        # 批量创建数据 dml ,u1 ,g2, the day before yesterday 组, 3 个数据
        dml_workflow = [SqlWorkflow(
            workflow_name='Test %s' % i,
            group_id=2,
            group_name='g2',
            engineer=cls.u2.username,
            engineer_display=cls.u2.display,
            audit_auth_groups='some_group',
            create_time=cls.now - datetime.timedelta(days=2),
            status='workflow_finish',
            is_backup=True,
            instance=cls.slave1,
            db_name='some_db',
            syntax_type=2
        ) for i in range(3)]
        SqlWorkflow.objects.bulk_create(ddl_workflow + dml_workflow)
        # 保存内容数据
        ddl_workflow_content = [SqlWorkflowContent(
            workflow=SqlWorkflow.objects.get(workflow_name='ddl %s' % i),
            sql_content='some_sql',
        ) for i in range(2)]
        dml_workflow_content = [SqlWorkflowContent(
            workflow=SqlWorkflow.objects.get(workflow_name='Test %s' % i),
            sql_content='some_sql',
        ) for i in range(3)]
        SqlWorkflowContent.objects.bulk_create(ddl_workflow_content + dml_workflow_content)

    # query_logs = [QueryLog(
    #    instance_name = 'some_instance',
    #
    # ) for i in range(20)]

    @classmethod
    def tearDownClass(cls):
        SqlWorkflowContent.objects.all().delete()
        SqlWorkflow.objects.all().delete()
        QueryLog.objects.all().delete()
        cls.u1.delete()
        cls.u2.delete()
        cls.superuser1.delete()
        cls.slave1.delete()

    def testGetDateList(self):
        dao = ChartDao()
        end = datetime.date.today()
        begin = end - datetime.timedelta(days=3)
        result = dao.get_date_list(begin, end)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], begin.strftime('%Y-%m-%d'))
        self.assertEqual(result[-1], end.strftime('%Y-%m-%d'))

    def testSyntaxList(self):
        """工单以语法类型分组"""
        dao = ChartDao()
        expected_rows = (('DDL', 2), ('DML', 3))
        result = dao.syntax_type()
        self.assertEqual(result['rows'], expected_rows)

    def testWorkflowByDate(self):
        """TODO 按日分组工单数量统计测试"""
        dao = ChartDao()
        result = dao.workflow_by_date(30)
        self.assertEqual(len(result['rows'][0]), 2)

    def testWorkflowByGroup(self):
        """按组统计测试"""
        dao = ChartDao()
        result = dao.workflow_by_group(30)
        expected_rows = (('g2', 3), ('g1', 2))
        self.assertEqual(result['rows'], expected_rows)

    def testWorkflowByUser(self):
        """按用户统计测试"""
        dao = ChartDao()
        result = dao.workflow_by_user(30)
        expected_rows = ((self.u2.display, 3), (self.u1.display, 2))
        self.assertEqual(result['rows'], expected_rows)

    def testDashboard(self):
        """Dashboard测试"""
        # TODO 这部分测试并没有遵循单元测试, 而是某种集成测试, 直接从响应到结果, 并且只检查状态码
        # TODO 需要具体查看pyecharst有没有被调用, 以及调用的参数
        c = Client()
        c.force_login(self.superuser1)
        r = c.get('/dashboard/')
        self.assertEqual(r.status_code, 200)


class AuthTest(TestCase):

    def setUp(self):
        self.username = 'some_user'
        self.password = 'some_pass'
        self.u1 = User(username=self.username, password=self.password, display='用户1')
        self.u1.save()

    def tearDown(self):
        self.u1.delete()

    def testChallenge(self):
        pass
