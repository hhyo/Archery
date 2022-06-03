from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from rest_framework.test import APITestCase
from rest_framework import status
from common.config import SysConfig
from sql.models import ResourceGroup, Instance, AliyunRdsConfig, CloudAccessKey, Tunnel, \
    SqlWorkflow, SqlWorkflowContent, WorkflowAudit, WorkflowLog, InstanceTag, WorkflowAuditSetting, \
    TwoFactorAuthConfig
import json

User = get_user_model()


class InfoTest(TestCase):
    def setUp(self) -> None:
        self.superuser = User.objects.create(username='super', is_superuser=True)
        self.client.force_login(self.superuser)

    def tearDown(self) -> None:
        self.superuser.delete()

    def test_info_api(self):
        r = self.client.get('/api/info')
        r_json = r.json()
        self.assertIsInstance(r_json['archery']['version'], str)

    def test_debug_api(self):
        r = self.client.get('/api/debug')
        r_json = r.json()
        self.assertIsInstance(r_json['archery']['version'], str)


class TestUser(APITestCase):
    """测试用户相关接口"""

    def setUp(self):
        self.user = User(username='test_user', display='测试用户', is_active=True)
        self.user.set_password('test_password')
        self.user.save()
        self.group = Group.objects.create(id=1, name='DBA')
        self.res_group = ResourceGroup.objects.create(group_id=1, group_name='test')
        r = self.client.post('/api/auth/token/', {'username': 'test_user', 'password': 'test_password'}, format='json')
        self.token = r.data['access']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        SysConfig().set('api_user_whitelist', self.user.id)

    def tearDown(self):
        self.user.delete()
        self.group.delete()
        self.res_group.delete()
        SysConfig().purge()

    def test_user_not_in_whitelist(self):
        """测试api用户白名单参数"""
        SysConfig().set('api_user_whitelist', '')
        r = self.client.get('/api/v1/user/', format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertDictEqual(r.json(), {'detail': '您没有执行该操作的权限。'})

    def test_get_user_list(self):
        """测试获取用户清单"""
        r = self.client.get('/api/v1/user/', format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['count'], 1)

    def test_create_user(self):
        """测试创建用户"""
        json_data = {
            'username': 'test_user2',
            'password': 'test_password2',
            'display': '测试用户2'
        }
        r = self.client.post('/api/v1/user/', json_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()['username'], 'test_user2')

    def test_update_user(self):
        """测试更新用户"""
        json_data = {
            'display': '更新中文名'
        }
        r = self.client.put(f'/api/v1/user/{self.user.id}/', json_data, format='json')
        user = User.objects.get(pk=self.user.id)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(user.display, '更新中文名')

    def test_delete_user(self):
        """测试删除用户"""
        json_data = {
            'username': 'test_user2',
            'password': 'test_password2',
            'display': '测试用户2'
        }
        r1 = self.client.post('/api/v1/user/', json_data, format='json')
        r2 = self.client.delete(f'/api/v1/user/{r1.json()["id"]}/', format='json')
        self.assertEqual(r2.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(User.objects.filter(username='test_user2').count(), 0)

    def test_get_user_group_list(self):
        """测试获取用户组清单"""
        r = self.client.get('/api/v1/user/group/', format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['count'], 1)

    def test_create_user_group(self):
        """测试创建用户组"""
        json_data = {
            'name': 'RD'
        }
        r = self.client.post('/api/v1/user/group/', json_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()['name'], 'RD')

    def test_update_user_group(self):
        """测试更新用户组"""
        json_data = {
            'name': '更新用户组名称'
        }
        r = self.client.put(f'/api/v1/user/group/{self.group.id}/', json_data, format='json')
        group = Group.objects.get(pk=self.group.id)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(group.name, '更新用户组名称')

    def test_delete_user_group(self):
        """测试删除用户组"""
        r = self.client.delete(f'/api/v1/user/group/{self.group.id}/', format='json')
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Group.objects.filter(name='DBA').count(), 0)

    def test_get_resource_group_list(self):
        """测试获取资源组清单"""
        r = self.client.get('/api/v1/user/resourcegroup/', format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['count'], 1)

    def test_create_resource_group(self):
        """测试创建资源组"""
        json_data = {
            'group_name': 'prod',
            'ding_webhook': 'https://oapi.dingtalk.com/robot/send?access_token=123'
        }
        r = self.client.post('/api/v1/user/resourcegroup/', json_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()['group_name'], 'prod')

    def test_update_resource_group(self):
        """测试更新资源组"""
        json_data = {
            'group_name': '更新资源组名称'
        }
        r = self.client.put(f'/api/v1/user/resourcegroup/{self.res_group.group_id}/', json_data, format='json')
        group = ResourceGroup.objects.get(pk=self.res_group.group_id)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(group.group_name, '更新资源组名称')

    def test_delete_resource_group(self):
        """测试删除资源组"""
        r = self.client.delete(f'/api/v1/user/resourcegroup/{self.res_group.group_id}/', format='json')
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Group.objects.filter(name='test').count(), 0)

    def test_user_auth(self):
        """测试用户认证校验"""
        json_data = {
            "engineer": "test_user",
            "password": "test_password"
        }
        r = self.client.post(f'/api/v1/user/auth/', json_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json(), {'status': 0, 'msg': '认证成功'})

    def test_2fa_config(self):
        """测试用户配置2fa"""
        json_data = {
            "engineer": "test_user",
            "auth_type": "disabled"
        }
        r = self.client.post(f'/api/v1/user/2fa/', json_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(TwoFactorAuthConfig.objects.count(), 0)

    def test_2fa_save(self):
        """测试用户保存2fa配置"""
        json_data = {
            "engineer": "test_user",
            "auth_type": "totp",
            "key": "ZUGRIJZP6H7LIOAL4LH5JA4GSXXT3WOK"
        }
        r = self.client.post(f'/api/v1/user/2fa/save/', json_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(TwoFactorAuthConfig.objects.count(), 1)

    def test_2fa_verify(self):
        """测试2fa验证码校验"""
        json_data = {
            "engineer": "test_user",
            "otp": 123456,
            "key": "ZUGRIJZP6H7LIOAL4LH5JA4GSXXT3WOK",
            "auth_type": "totp"
        }
        r = self.client.post(f'/api/v1/user/2fa/verify/', json_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['status'], 1)


class TestInstance(APITestCase):
    """测试实例相关接口"""

    def setUp(self):
        self.user = User(username='test_user', display='测试用户', is_active=True)
        self.user.set_password('test_password')
        self.user.save()
        self.ins = Instance.objects.create(instance_name='some_ins', type='slave', db_type='mysql',
                                           host='some_host', port=3306, user='ins_user', password='some_str')
        self.ak = CloudAccessKey.objects.create(type='aliyun', key_id='abc', key_secret='abc')
        self.rds = AliyunRdsConfig.objects.create(rds_dbinstanceid='abc', ak_id=self.ak.id, instance=self.ins)
        self.tunnel = Tunnel.objects.create(tunnel_name='one_tunnel', host='one_host', port=22)
        r = self.client.post('/api/auth/token/', {'username': 'test_user', 'password': 'test_password'}, format='json')
        self.token = r.data['access']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        SysConfig().set('api_user_whitelist', self.user.id)

    def tearDown(self):
        self.user.delete()
        Instance.objects.all().delete()
        AliyunRdsConfig.objects.all().delete()
        CloudAccessKey.objects.all().delete()
        Tunnel.objects.all().delete()
        SysConfig().purge()

    def test_get_instance_list(self):
        """测试获取实例清单"""
        r = self.client.get('/api/v1/instance/', format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['count'], 1)

    def test_create_instance(self):
        """测试创建实例"""
        json_data = {
            'instance_name': 'test_ins',
            'type': 'master',
            'db_type': 'mysql',
            'host': 'some_host',
            'port': 3306
        }
        r = self.client.post('/api/v1/instance/', json_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()['instance_name'], 'test_ins')

    def test_update_instance(self):
        """测试更新实例"""
        json_data = {
            'instance_name': '更新实例名称'
        }
        r = self.client.put(f'/api/v1/instance/{self.ins.id}/', json_data, format='json')
        ins = Instance.objects.get(pk=self.ins.id)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(ins.instance_name, '更新实例名称')

    def test_delete_instance(self):
        """测试删除实例"""
        r = self.client.delete(f'/api/v1/instance/{self.ins.id}/', format='json')
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Instance.objects.filter(instance_name='some_ins').count(), 0)

    def test_get_aliyunrds_list(self):
        """测试获取aliyunrds清单"""
        r = self.client.get('/api/v1/instance/rds/', format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['count'], 1)

    def test_create_aliyunrds(self):
        """测试创建aliyunrds"""
        ins = Instance.objects.create(instance_name='another_ins', type='slave', db_type='mysql',
                                      host='another_host', port=3306)
        json_data = {
            "rds_dbinstanceid": "bbc",
            "is_enable": True,
            "instance": ins.id,
            "ak": {
                "type": "aliyun",
                "key_id": "bbc",
                "key_secret": "bbc",
                "remark": "bbc"
            }
        }
        r = self.client.post('/api/v1/instance/rds/', json_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()['rds_dbinstanceid'], 'bbc')

    def test_get_tunnel_list(self):
        """测试获取隧道清单"""
        r = self.client.get('/api/v1/instance/tunnel/', format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['count'], 1)

    def test_create_tunnel(self):
        """测试创建隧道"""
        json_data = {
            "tunnel_name": "tunnel_test",
            "host": "one_host",
            "port": 22
        }
        r = self.client.post('/api/v1/instance/tunnel/', json_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()['tunnel_name'], 'tunnel_test')


class TestWorkflow(APITestCase):
    """测试工单相关接口"""

    def setUp(self):
        self.now = datetime.now()
        self.group = Group.objects.create(id=1, name='DBA')
        self.res_group = ResourceGroup.objects.create(group_id=1, group_name='test')
        self.ins_tag = InstanceTag.objects.create(tag_code='can_write', active=1)
        self.wfs = WorkflowAuditSetting.objects.create(group_id=self.res_group.group_id,
                                                       workflow_type=2, audit_auth_groups=self.group.id)
        can_execute_permission = Permission.objects.get(codename='sql_execute')
        can_execute_resource_permission = Permission.objects.get(codename='sql_execute_for_resource_group')
        can_review_permission = Permission.objects.get(codename='sql_review')
        self.user = User(username='test_user', display='测试用户', is_active=True)
        self.user.set_password('test_password')
        self.user.save()
        self.user.user_permissions.add(can_execute_permission, can_execute_resource_permission, can_review_permission)
        self.user.groups.add(self.group.id)
        self.user.resource_group.add(self.res_group.group_id)
        self.ins = Instance.objects.create(instance_name='some_ins', type='slave', db_type='redis',
                                           host='some_host', port=6379, user='ins_user', password='some_str')
        self.ins.resource_group.add(self.res_group.group_id)
        self.ins.instance_tag.add(self.ins_tag.id)
        self.wf1 = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer=self.user.username,
            engineer_display=self.user.display,
            audit_auth_groups='1',
            create_time=self.now - timedelta(days=1),
            status='workflow_manreviewing',
            is_backup=False,
            instance=self.ins,
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
        self.audit1 = WorkflowAudit.objects.create(
            group_id=1,
            group_name='some_group',
            workflow_id=self.wf1.id,
            workflow_type=2,
            workflow_title='申请标题',
            workflow_remark='申请备注',
            audit_auth_groups='1',
            current_audit='1',
            next_audit='-1',
            current_status=0)
        self.wl = WorkflowLog.objects.create(audit_id=self.audit1.audit_id,
                                             operation_type=1)
        r = self.client.post('/api/auth/token/', {'username': 'test_user', 'password': 'test_password'}, format='json')
        self.token = r.data['access']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        SysConfig().set('api_user_whitelist', self.user.id)

    def tearDown(self):
        self.user.delete()
        self.group.delete()
        self.res_group.delete()
        SqlWorkflowContent.objects.all().delete()
        SqlWorkflow.objects.all().delete()
        WorkflowAudit.objects.all().delete()
        WorkflowLog.objects.all().delete()

    def test_get_sql_workflow_list(self):
        """测试获取SQL上线工单列表"""
        r = self.client.get('/api/v1/workflow/', format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['count'], 1)

    def test_get_audit_list(self):
        """测试获取待审核工单列表"""
        json_data = {
            "engineer": "test_user"
        }
        r = self.client.post('/api/v1/workflow/auditlist/', json_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['count'], 1)

    def test_get_workflow_log_list(self):
        """测试获工单日志"""
        json_data = {
            "workflow_id": self.wf1.id,
            "workflow_type": self.audit1.workflow_type
        }
        r = self.client.post('/api/v1/workflow/log/', json_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()['count'], 1)

    def test_submit_workflow(self):
        """测试提交SQL上线工单"""
        json_data = {
            "workflow": {
              "workflow_name": "上线工单1",
              "demand_url": "test",
              "group_id": 1,
              "db_name": "test_db",
              "engineer": self.user.username,
              "instance": self.ins.id
            },
            "sql_content": "alter table abc add column note varchar(64);"
        }
        r = self.client.post('/api/v1/workflow/', json_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()['workflow']['workflow_name'], '上线工单1')

    def test_audit_workflow(self):
        """测试审核工单"""
        json_data = {
            "engineer": self.user.username,
            "workflow_id": self.wf1.id,
            "audit_remark": "取消",
            "workflow_type": self.audit1.workflow_type,
            "audit_type": "cancel"
        }
        r = self.client.post('/api/v1/workflow/audit/', json_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json(), {'msg': 'canceled'})

    def test_execute_workflow(self):
        """测试执行工单"""
        # 先审核
        audit_data = {
            "engineer": self.user.username,
            "workflow_id": self.wf1.id,
            "audit_remark": "通过",
            "workflow_type": self.audit1.workflow_type,
            "audit_type": "pass"
        }
        self.client.post('/api/v1/workflow/audit/', audit_data, format='json')
        # 再执行
        execute_data = {
            "engineer": self.user.username,
            "workflow_id": self.wf1.id,
            "workflow_type": self.audit1.workflow_type,
            "mode": "manual"
        }
        r = self.client.post('/api/v1/workflow/execute/', execute_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json(), {'msg': '开始执行，执行结果请到工单详情页查看'})
