from django.test import TestCase, Client
from unittest.mock import patch
from sql.models import SqlWorkflow, Instance
from django.contrib.auth import get_user_model
from sql.engines.mysql import MysqlEngine
# Create your tests here.

class WorkflowTest(TestCase):

    def setUp(self):
        User = get_user_model()
        self.u1 = User(username='test_user', display ='中文显示', is_active=True)
        self.u1.save()
        self.u2 = User(username='some_other_user', display ='中文显示2', is_active=True)
        self.u2.save()
        self.u3 = User(username='some_other_user2', display ='中文显示4', is_active=True)
        self.u3.save()
        self.superuser1 = User(username='some_superuser', 
                            display ='中文显示', is_active=True, is_superuser=True)
        self.superuser1.save()
        self.wf1 = SqlWorkflow(
            workflow_name = 'test',
            group_id = 1,
            group_name = 'test_group',
            engineer = 'test_user',
            engineer_display = '中文显示',
            audit_auth_groups = 'test_auth_group',
            status = '等待审核人审核',
            is_backup = '是',
            instance_name = 'test_instance',
            db_name = 'test_db',
            sql_content = 'test_sql_content',
            sql_syntax=1
        )
        self.wf1.save()
        self.wf2 = SqlWorkflow(
            workflow_name = 'test2',
            group_id = 1,
            group_name = 'test_group',
            engineer = 'some_other_user',
            engineer_display = '中文显示2',
            audit_auth_groups = 'test_auth_group',
            status = '等待审核人审核',
            is_backup = '是',
            instance_name = 'test_instance',
            db_name = 'test_db',
            sql_content = 'test_sql_content',
            sql_syntax=1
        )
        self.wf2.save()
    def testWorkflowList(self):
        c = Client()
        # 未登录用户重定向至登录页面
        response = c.get('/api/v1/workflow/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login/')
        # 普通用户登录可以看到自己的工单
        c.force_login(self.u1)
        response = c.get('/api/v1/workflow/')
        r_json = response.json()
        self.assertEqual(1, len(r_json))
        self.assertEqual(self.wf1.workflow_name, r_json[0]['workflow_name'])
        self.assertEqual(self.wf1.engineer, r_json[0]['engineer'])
        c.force_login(self.u2)
        response = c.get('/api/v1/workflow/')
        r_json = response.json()
        self.assertEqual(1, len(r_json))
        self.assertEqual(self.wf2.workflow_name, r_json[0]['workflow_name'])
        self.assertEqual(self.wf2.engineer, r_json[0]['engineer'])
        c.force_login(self.u3)
        response = c.get('/api/v1/workflow/')
        r_json = response.json()
        self.assertEqual(0, len(r_json))
        # 超级用户可以看到所有工单
        c.force_login(self.superuser1)
        response = c.get('/api/v1/workflow/')
        r_json = response.json()
        self.assertEqual(2, len(r_json))
    def testWorkflowDetail(self):
        """详情页测试"""
        # 未登录用户返回302
        c = Client()
        response = c.get('/api/v1/workflow/{}/'.format(self.wf1.id))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login/')
        # 登录用户可以查看自己的工单, 他人工单403
        c.force_login(self.u1)
        response = c.get('/api/v1/workflow/{}/'.format(self.wf1.id))
        self.assertEqual(response.status_code, 200)
        r_json = response.json()
        # 抽查一个字段是否正常
        self.assertEqual(r_json['sql_content'], self.wf1.sql_content)
        response = c.get('/api/v1/workflow/{}/'.format(self.wf2.id))
        self.assertEqual(response.status_code, 403)



    def tearDown(self):
        self.u1.delete()
        self.u2.delete()
        self.u3.delete()
        self.superuser1.delete()
        self.wf1.delete()
        self.wf2.delete()
   
class InstanceTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.u1 = User(username='test_user', display ='中文显示', is_active=True)
        self.u1.save()
        self.u2 = User(username='some_other_user', display ='中文显示2', is_active=True)
        self.u2.save()
        self.u3 = User(username='some_other_user2', display ='中文显示4', is_active=True)
        self.u3.save()
        self.superuser1 = User(username='some_superuser', 
                            display ='中文显示', is_active=True, is_superuser=True)
        self.superuser1.save()
        self.master1 = Instance(instance_name='test_master_instance',type='master', db_type='mysql',
                        host='testhost', port=3306, user='mysql_user', password='mysql_password')
        self.master1.save()
        self.slave1 = Instance(instance_name='test_slave_instance',type='slave', db_type='mysql',
                        host='testhost', port=3306, user='mysql_user', password='mysql_password')
        self.slave1.save()
    def testInstanceList(self):
        """测试实例列表"""
        c = Client()
        # 未登录用户重定向至登录页面
        response = c.get('/api/v1/instance/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login/')
        c.force_login(self.u1)
        r = c.get('/api/v1/instance/')
        r_json = r.json()
        self.assertEqual(len(r_json), 2)
        self.assertNotIn('password', r_json[0])
        self.assertNotIn('raw_password', r_json[0])
    
    def testInstanceDetail(self):
        """测试实例详情页"""
        c = Client()
        r = c.get('/api/v1/instance/{}/'.format(self.master1.id))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/login/')
        c.force_login(self.u1)
        r = c.get('/api/v1/instance/{}/'.format(self.master1.id))
        r_json = r.json()
        self.assertEqual(r_json['instance_name'], self.master1.instance_name)
        self.assertNotIn('password', r_json)
        self.assertNotIn('raw_password', r_json)
    
    def testInstanceDblist(self):
        """测试实例数据库列表"""
        c = Client()
        c.force_login(self.u1)
        mock_db_list = ['tb1','tb2','tb3','tb4']
        with patch.object(MysqlEngine, 'get_all_databases', return_value=mock_db_list) as mock_method:
            r = c.get('/api/v1/instance/{}/db_list/'.format(self.master1.id))
            r_json = r.json()
        self.assertIsInstance(r_json, list)
        self.assertEqual(r_json, mock_db_list)
        
    def testInstanceTableList(self):
        """表列表接口"""
        c = Client()
        c.force_login(self.u1)
        mock_tb_list = ['tb1','tb2','tb3','tb4']
        with patch.object(MysqlEngine, 'get_all_tables', return_value=mock_tb_list) as mock_method:
            r = c.get('/api/v1/instance/{}/table_list/'.format(self.master1.id), {'db_name':'test_db'})
            mock_method.assert_called_once_with('test_db')
        r_json = r.json()
        self.assertIsInstance(r_json, list)
        self.assertEqual(r_json, mock_tb_list)
    
    def testInstanceColumnList(self):
        """表字段列表接口"""
        c = Client()
        c.force_login(self.u1)
        mock_col_list = ['col1','col2','col3','col4']
        with patch.object(MysqlEngine, 'get_all_columns_by_tb', return_value=mock_col_list) as mock_method:
            r = c.get('/api/v1/instance/{}/column_list/'.format(self.master1.id), 
                {'db_name':'test_db', 'table_name':'test_tb'})
            mock_method.assert_called_once_with('test_db','test_tb')
        r_json = r.json()
        self.assertIsInstance(r_json, list)
        self.assertEqual(r_json, mock_col_list)

    def tearDown(self):
        self.u1.delete()
        self.u2.delete()
        self.u3.delete()
        self.superuser1.delete()
        self.master1.delete()
        self.slave1.delete()