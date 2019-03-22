import json
import re
from datetime import timedelta, datetime
from unittest.mock import MagicMock, patch, ANY
from unittest import skip
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission

from django.test import Client, TestCase

from common.config import SysConfig
from sql.engines.models import ResultSet
from sql.engines.mysql import MysqlEngine
from sql import query

from sql.models import Instance, QueryPrivilegesApply, QueryPrivileges, SqlWorkflow, QueryLog, ResourceGroup
from sql.utils.execute_sql import execute_callback

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
        self.slave2 = Instance(instance_name='test_instance_non_mysql', type='slave', db_type='mssql',
                               host='some_host2', port=3306, user='some_user', password='some_password')
        self.slave1.save()
        self.slave2.save()
        archer_user = get_user_model()
        self.superuser1 = archer_user(username='super1', is_superuser=True)
        self.superuser1.save()
        self.u1 = archer_user(username='test_user', display='中文显示', is_active=True)
        self.u1.save()
        self.u2 = archer_user(username='test_user2', display='中文显示', is_active=True)
        self.u2.save()
        self.u3 = archer_user(username='test_user3', display='中文显示', is_active=True)
        self.u3.save()
        sql_query_perm = Permission.objects.get(codename='query_submit')
        self.u2.user_permissions.add(sql_query_perm)
        self.u3.user_permissions.add(sql_query_perm)
        tomorrow = datetime.now() + timedelta(days=1)
        self.query_apply_1 = QueryPrivilegesApply(
            group_id=1,
            group_name='some_group',
            title='some_title',
            user_name='some_user',
            instance=self.slave1,
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
            instance=self.slave1,
            db_list='some_db',
            table_list='some_table,some_tb2',
            limit_num=100,
            valid_date=tomorrow,
            priv_type=2,
            status=0,
            audit_auth_groups='some_audit_group'
        )
        self.query_apply_2.save()
        self.db_priv_for_user3 = QueryPrivileges(
            user_name=self.u3.username,
            user_display=self.u3.display,
            instance=self.slave1,
            db_name='some_db',
            table_name='',
            valid_date=tomorrow,
            limit_num=70,
            priv_type=1)
        self.db_priv_for_user3.save()
        self.table_priv_for_user3 = QueryPrivileges(
            user_name=self.u3.username,
            user_display=self.u3.display,
            instance=self.slave1,
            db_name='another_db',
            table_name='some_table',
            valid_date=tomorrow,
            limit_num=60,
            priv_type=2)
        self.table_priv_for_user3.save()
        self.db_priv_for_user3_another_instance = QueryPrivileges(
            user_name=self.u3.username,
            user_display=self.u3.display,
            instance=self.slave2,
            db_name='some_db_another_instance',
            table_name='',
            valid_date=tomorrow,
            limit_num=50,
            priv_type=1)
        self.db_priv_for_user3_another_instance.save()

    def tearDown(self):
        self.query_apply_1.delete()
        self.query_apply_2.delete()
        QueryPrivileges.objects.all().delete()
        self.u1.delete()
        self.u2.delete()
        self.u3.delete()
        self.superuser1.delete()
        self.slave1.delete()
        self.slave2.delete()
        archer_config = SysConfig()
        archer_config.set('disable_star', False)

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
                limit_num=100)), 0)
        # 工单改为审核成功, 验证工单状态和权限状态
        query.query_audit_call_back(self.query_apply_1.apply_id, 1)
        self.query_apply_1.refresh_from_db()
        self.assertEqual(self.query_apply_1.status, 1)
        for db in self.query_apply_1.db_list.split(','):
            self.assertEqual(len(QueryPrivileges.objects.filter(
                user_name=self.query_apply_1.user_name,
                db_name=db,
                limit_num=100)), 1)
        # 表权限申请测试, 只测试审核成功
        query.query_audit_call_back(self.query_apply_2.apply_id, 1)
        self.query_apply_2.refresh_from_db()
        self.assertEqual(self.query_apply_2.status, 1)
        for tb in self.query_apply_2.table_list.split(','):
            self.assertEqual(len(QueryPrivileges.objects.filter(
                user_name=self.query_apply_2.user_name,
                db_name=self.query_apply_2.db_list,
                table_name=tb,
                limit_num=self.query_apply_2.limit_num)), 1)

    @patch('sql.engines.mysql.MysqlEngine.query')
    @patch('sql.engines.mysql.MysqlEngine.query_masking')
    @patch('sql.query.query_priv_check')
    def testCorrectSQL(self, _priv_check, _query_masking, _query):
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

        _query.return_value = q_result
        _query_masking.return_value = q_result
        _priv_check.return_value = {'status': 0, 'data': {'limit_num': 100, 'priv_check': 1}}
        r = c.post('/query/', data={'instance_name': self.slave1.instance_name,
                                    'sql_content': some_sql,
                                    'db_name': some_db,
                                    'limit_num': some_limit})
        _query.assert_called_once_with(db_name=some_db, sql=some_sql, limit_num=some_limit)
        r_json = r.json()
        self.assertEqual(r_json['data']['rows'], ['value'])
        self.assertEqual(r_json['data']['column_list'], ['some'])

    @patch('sql.engines.mysql.MysqlEngine.query')
    @patch('sql.engines.mysql.MysqlEngine.query_masking')
    @patch('sql.query.query_priv_check')
    def testSQLWithoutLimit(self, _priv_check, _query_masking, _query):
        c = Client()
        some_limit = 100
        sql_without_limit = 'select some from some_table'
        sql_with_limit = 'select some from some_table limit {0};'.format(some_limit)
        some_db = 'some_db'
        c.force_login(self.u2)
        q_result = ResultSet(full_sql=sql_without_limit, rows=['value'])
        q_result.column_list = ['some']
        _query.return_value = q_result
        _query_masking.return_value = q_result
        _priv_check.return_value = {'status': 0, 'data': {'limit_num': 100, 'priv_check': 1}}
        r = c.post('/query/', data={'instance_name': self.slave1.instance_name,
                                    'sql_content': sql_without_limit,
                                    'db_name': some_db,
                                    'limit_num': some_limit})
        _query.assert_called_once_with(db_name=some_db, sql=sql_with_limit, limit_num=some_limit)
        r_json = r.json()
        self.assertEqual(r_json['data']['rows'], ['value'])
        self.assertEqual(r_json['data']['column_list'], ['some'])

        # 带 * 且不带 limit 的sql
        sql_with_star = 'select * from some_table'
        filtered_sql_with_star = 'select * from some_table limit {0};'.format(some_limit)
        _query.reset_mock()
        c.post('/query/', data={'instance_name': self.slave1.instance_name,
                                'sql_content': sql_with_star,
                                'db_name': some_db,
                                'limit_num': some_limit})
        _query.assert_called_once_with(db_name=some_db, sql=filtered_sql_with_star, limit_num=some_limit)

    @patch('sql.query.query_priv_check')
    def testStarOptionOn(self, _priv_check):
        c = Client()
        c.force_login(self.u2)
        some_limit = 100
        sql_with_star = 'select * from some_table'
        some_db = 'some_db'
        _priv_check.return_value = {'status': 0, 'data': {'limit_num': 100, 'priv_check': 1}}
        archer_config = SysConfig()
        archer_config.set('disable_star', True)
        r = c.post('/query/', data={'instance_name': self.slave1.instance_name,
                                    'sql_content': sql_with_star,
                                    'db_name': some_db,
                                    'limit_num': some_limit})
        archer_config.set('disable_star', False)
        r_json = r.json()
        self.assertEqual(1, r_json['status'])

    @patch('sql.query.Masking')
    def test_query_priv_check(self, mock_masking):
        # 超级用户直接返回
        superuser_limit = query.query_priv_check(self.superuser1, self.slave1.instance_name,
                                                 'some_db', 'some_sql', 100)
        self.assertEqual(superuser_limit['status'], 0)
        self.assertEqual(superuser_limit['data']['limit_num'], 100)

        # 无语法树解析，只校验db_name
        limit_without_tree_analyse = query.query_priv_check(self.u3, self.slave2,
                                                            'some_db_another_instance', 'some_sql', 1000)
        self.assertEqual(limit_without_tree_analyse['data']['limit_num'],
                         self.db_priv_for_user3_another_instance.limit_num)

        # 无语法树解析， 无权限的情况
        limit_without_tree_analyse = query.query_priv_check(self.u3, self.slave2,
                                                            'some_db_does_not_exist', 'some_sql', 1000)
        self.assertEqual(limit_without_tree_analyse['status'], 1)
        self.assertIn('some_db_does_not_exist', limit_without_tree_analyse['msg'])

        # 有语法树解析, 有库权限
        mock_masking.return_value.query_table_ref.return_value = {
            'status': 0,
            'data': [{
                'db': 'another_db',
                'table': 'some_table'
            }]}
        limit_with_tree_analyse = query.query_priv_check(self.u3, self.slave1,
                                                         'some_db', 'some_sql', 1000)
        mock_masking.return_value.query_table_ref.assert_called_once()
        self.assertEqual(limit_with_tree_analyse['data']['limit_num'], self.table_priv_for_user3.limit_num)

        # TODO 有语法树解析， 无库权限， 无表权限
        # TODO 有语法树解析， 无库权限， 有表权限


class WorkflowViewTest(TestCase):

    def setUp(self):
        self.now = datetime.now()
        can_view_permission = Permission.objects.get(codename='menu_sqlworkflow')
        self.u1 = User(username='some_user', display='用户1')
        self.u1.save()
        self.u1.user_permissions.add(can_view_permission)
        self.u2 = User(username='some_user2', display='用户2')
        self.u2.save()
        self.u2.user_permissions.add(can_view_permission)
        self.u3 = User(username='some_user3', display='用户3')
        self.u3.save()
        self.u3.user_permissions.add(can_view_permission)
        self.superuser1 = User(username='super1', is_superuser=True)
        self.superuser1.save()
        self.master1 = Instance(instance_name='test_master_instance', type='master', db_type='mysql',
                               host='testhost', port=3306, user='mysql_user', password='mysql_password')
        self.master1.save()
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
            instance=self.master1,
            db_name='some_db',
            sql_content='some_sql',
            syntax_type=1,
            execute_result=json.dumps([{
                'id': 1,
                'sql': 'some_content'
            }])
        )
        self.wf1.save()
        self.wf2 = SqlWorkflow(
            workflow_name='some_name2',
            group_id=1,
            group_name='g1',
            engineer=self.u2.username,
            engineer_display=self.u2.display,
            audit_auth_groups='some_group',
            create_time=self.now - timedelta(days=1),
            status='workflow_manreviewing',
            is_backup='是',
            instance=self.master1,
            db_name='some_db',
            sql_content='some_sql',
            syntax_type=1,
            execute_result=json.dumps([{
                'id': 1,
                'sql': 'some_content'
            }])
        )
        self.wf2.save()
        self.resource_group1 = ResourceGroup(
            group_name='some_group'
        )
        self.resource_group1.save()

    def tearDown(self):
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

    @patch('sql.utils.workflow_audit.Audit.review_info')
    @patch('sql.utils.workflow_audit.Audit.can_review')
    def testWorkflowDetailView(self, _can_review, _review_info):
        _review_info.return_value = ('some_auth_group', 'current_auth_group')
        _can_review.return_value = False
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
        self.assertEqual(r_json['total'],1)
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
            'is_backup': '是',
            'notify_users': ''
        }
        mock_user_instances.return_value.get.return_value = None
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


class AsyncTest(TestCase):

    def setUp(self):
        self.now = datetime.now()
        self.u1 = User(username='some_user', display='用户1')
        self.u1.save()
        self.master1 = Instance(instance_name='test_master_instance', type='master', db_type='mysql',
                               host='testhost', port=3306, user='mysql_user', password='mysql_password')
        self.master1.save()
        self.wf1 = SqlWorkflow(
            workflow_name='some_name2',
            group_id=1,
            group_name='g1',
            engineer=self.u1.username,
            engineer_display=self.u1.display,
            audit_auth_groups='some_group',
            create_time=self.now - timedelta(days=1),
            status='workflow_executing',
            is_backup='是',
            instance=self.master1,
            db_name='some_db',
            sql_content='some_sql',
            syntax_type=1,
            execute_result=''
        )
        self.wf1.save()
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

