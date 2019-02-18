import json
from datetime import timedelta, datetime
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission

from django.test import Client, TestCase

from common.config import SysConfig
from sql import query
from sql.engines.models import ResultSet
from sql.engines.mysql import MysqlEngine
from sql import query

from sql.models import Instance, QueryPrivilegesApply, QueryPrivileges, SqlWorkflow

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
        tomorrow = datetime.now() + timedelta(days=1)
        self.query_apply_1 = QueryPrivilegesApply(
            group_id=1,
            group_name='some_group',
            title='some_title',
            user_name='some_user',
            instance_name='some_ins',
            db_list='some_db,some_db2',
            limit_num=100,
            valid_date=tomorrow,
            priv_type=1,
            status=0,
            audit_auth_groups='some_audit_group'
        )
        self.query_apply_1.save()
        self.query_apply_2 = QueryPrivilegesApply(
            group_id=1,
            group_name='some_group',
            title='some_title',
            user_name='some_user',
            instance_name='some_ins',
            db_list='some_db',
            table_list='some_table,some_tb2',
            limit_num=100,
            valid_date=tomorrow,
            priv_type=2,
            status=0,
            audit_auth_groups='some_audit_group'
        )
        self.query_apply_2.save()

    def tearDown(self):
        self.u1.delete()
        self.u2.delete()
        self.slave1.delete()
        self.query_apply_1.delete()
        QueryPrivileges.objects.all().delete()

    def testQueryAuditCallback(self):
        """测试权限申请工单回调"""
        # 工单状态改为审核失败, 验证工单状态
        query.query_audit_call_back(self.query_apply_1.apply_id, 2)
        self.query_apply_1.refresh_from_db()
        self.assertEqual(self.query_apply_1.status, 2)
        for db in self.query_apply_1.db_list.split(','):
            self.assertEqual(len(QueryPrivileges.objects.filter(
                user_name=self.query_apply_1.user_name,
                db_name=db,
                limit_num=100)),0)
        # 工单改为审核成功, 验证工单状态和权限状态
        query.query_audit_call_back(self.query_apply_1.apply_id, 1)
        self.query_apply_1.refresh_from_db()
        self.assertEqual(self.query_apply_1.status, 1)
        for db in self.query_apply_1.db_list.split(','):
            self.assertEqual(len(QueryPrivileges.objects.filter(
                user_name=self.query_apply_1.user_name,
                db_name=db,
                limit_num=100)),1)
        # 表权限申请测试, 只测试审核成功
        query.query_audit_call_back(self.query_apply_2.apply_id, 1)
        self.query_apply_2.refresh_from_db()
        self.assertEqual(self.query_apply_2.status, 1)
        for tb in self.query_apply_2.table_list.split(','):
            self.assertEqual(len(QueryPrivileges.objects.filter(
                user_name=self.query_apply_2.user_name,
                db_name=self.query_apply_2.db_list,
                table_name=tb,
                limit_num=self.query_apply_2.limit_num)),1)

    def testCorrectSQL(self):
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




class WorkflowViewTest(TestCase):

    def setUp(self):
        self.now = datetime.now()
        self.u1 = User(username='some_user', display='用户1')
        self.u1.save()
        self.superuser1 = User(username='super1', is_superuser=True)
        self.superuser1.save()
        self.wf1 = SqlWorkflow(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer=self.u1.username,
            engineer_display=self.u1.display,
            audit_auth_groups='some_group',
            create_time=self.now - timedelta(days=1),
            status='workflow_finish',
            is_backup='是',
            instance_name='some_instance',
            db_name='some_db',
            sql_content='some_sql',
            sql_syntax=1,
            execute_result=json.dumps([{
                'id':1,
                'sql':'some_content'
            }])
        )
        self.wf1.save()
        self.wf2 = SqlWorkflow(
            workflow_name='some_name2',
            group_id=1,
            group_name='g1',
            engineer=self.u1.username,
            engineer_display=self.u1.display,
            audit_auth_groups='some_group',
            create_time=self.now - timedelta(days=1),
            status='workflow_manreviewing',
            is_backup='是',
            instance_name='some_instance',
            db_name='some_db',
            sql_content='some_sql',
            sql_syntax=1,
            execute_result=json.dumps([{
                'id': 1,
                'sql': 'some_content'
            }])
        )
        self.wf2.save()

    def tearDown(self):
        self.u1.delete()
        self.superuser1.delete()
        self.wf1.delete()
        self.wf2.delete()

    def testWorkflowStatus(self):
        c = Client(header={})
        c.force_login(self.u1)
        r = c.post('/getWorkflowStatus/', {'workflow_id': self.wf1.id})
        r_json = r.json()
        self.assertEqual(r_json['status'], '已正常结束')

    @patch('sql.utils.workflow_audit.Audit.review_info')
    @patch('sql.utils.workflow_audit.Audit.can_review')
    def testWorkflowDetailView(self, _can_review, _review_info):
        _review_info.return_value = ('some_auth_group', 'current_auth_group')
        _can_review.return_value = False
        c = Client()
        c.force_login(self.u1)
        r = c.get('/detail/{}/'.format(self.wf1.id))
        expected_status = r"""id="workflow_detail_status">已正常结束"""
        self.assertContains(r, expected_status)

    def testWorkflowListView(self):
        c = Client()
        c.force_login(self.superuser1)
        r = c.post('/sqlworkflow_list/', {'limit': 10, 'offset': 0, 'navStatus': 'all'})
        r_json = r.json()
        self.assertEqual(r_json['total'], 2)
        # 列表按创建时间倒序排列, 第二个是wf1 , 是已正常结束
        self.assertEqual(r_json['rows'][1]['status'], '已正常结束')

    @patch('sql.utils.workflow_audit.Audit.detail_by_workflow_id')
    @patch('sql.utils.workflow_audit.Audit.audit')
    @patch('sql.utils.workflow_audit.Audit.can_review')
    def testWorkflowPassedView(self, _can_review, _audit, _detail_by_id):
        c = Client()
        c.force_login(self.superuser1)
        r = c.post('/passed/')
        self.assertContains(r, 'workflow_id参数为空.')
        _can_review.return_value = False
        r = c.post('/passed/',{'workflow_id':self.wf1.id})
        self.assertContains(r, '你无权操作当前工单！')
        _can_review.return_value = True
        _detail_by_id.return_value.audit_id = 123
        _audit.return_value = {
            "data":{
                "workflow_status": 1  # TODO 改为audit_success
            }
        }
        r = c.post('/passed/', data={'workflow_id': self.wf1.id, 'audit_remark': 'some_audit'}, follow=False)
        self.assertRedirects(r, '/detail/{}/'.format(self.wf1.id), fetch_redirect_response=False)
        self.wf1.refresh_from_db()
        self.assertEqual(self.wf1.status, 'workflow_review_pass')
        self.assertEqual(self.wf1.audit_remark, 'some_audit')

    @patch('sql.sql_workflow.Audit.add_log')
    @patch('sql.sql_workflow.Audit.detail_by_workflow_id')
    @patch('sql.sql_workflow.Audit.audit')
    # patch view里的can_cancel 而不是原始位置的can_cancel ,因为在调用时, 已经 import 了真的 can_cancel ,会导致mock失效
    # 在import 静态函数时需要注意这一点, 动态对象因为每次都会重新生成,也可以 mock 原函数/方法/对象
    # 参见 : https://docs.python.org/3/library/unittest.mock.html#where-to-patch
    @patch('sql.sql_workflow.can_cancel')
    def testWorkflowCancelView(self, _can_cancel, _audit, _detail_by_id, _add_log):
        c = Client()
        c.force_login(self.u1)
        r = c.post('/cancel/')
        self.assertContains(r, 'workflow_id参数为空.')
        r = c.post('/cancel/', data={'workflow_id': self.wf2.id})
        self.assertContains(r, '终止原因不能为空')
        _can_cancel.return_value = False
        r = c.post('/cancel/', data={'workflow_id': self.wf2.id, 'cancel_remark':'some_reason'})
        self.assertContains(r, '你无权操作当前工单！')
        _can_cancel.return_value = True
        _detail_by_id = 123
        r = c.post('/cancel/', data={'workflow_id': self.wf2.id, 'cancel_remark': 'some_reason'})
        self.wf2.refresh_from_db()
        self.assertEqual('workflow_abort', self.wf2.status)