# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: tests.py 
@time: 2019/03/14
"""
import datetime
import json
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, Client

from common.config import SysConfig
from sql.models import SqlWorkflow, SqlWorkflowContent, Instance, ResourceGroup, ResourceGroupRelations
from sql.utils.extract_tables import TableReference
from sql.utils.sql_review import is_auto_review, can_execute, can_timingtask, can_cancel
from sql.utils.sql_utils import *

User = get_user_model()
__author__ = 'hhyo'


class TestSQLUtils(TestCase):
    def test_get_syntax_type(self):
        """
        测试语法判断
        :return:
        """
        dml_sql = "select * from users;"
        ddl_sql = "alter table users add id not null default 0 comment 'id' "
        self.assertEqual(get_syntax_type(dml_sql), 'DML')
        self.assertEqual(get_syntax_type(ddl_sql), 'DDL')

    def test_extract_tables(self):
        """
        测试表解析
        :return:
        """
        sql = "select * from user.users a join logs.log b on a.id=b.id;"
        self.assertEqual(extract_tables(sql),
                         (TableReference(schema='user', name='users', alias='a', is_function=False),
                          TableReference(schema='logs', name='log', alias='b', is_function=False)))

    def test_generate_sql_from_sql(self):
        """
        测试从SQl文本中解析SQL
        :return:
        """
        text = "select * from sql_user;select * from sql_workflow;"
        rows = generate_sql(text)
        self.assertListEqual(rows, [{'sql_id': 1, 'sql': 'select * from sql_user;'},
                                    {'sql_id': 2, 'sql': 'select * from sql_workflow;'}]
                             )

    def test_generate_sql_from_xml(self):
        """
        测试从XML文本中解析SQL
        :return:
        """
        text = """<?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
            <mapper namespace="Test">
            <select id="testParameters">
            SELECT
            name,
            category,
            price
            FROM
            fruits
            WHERE
            category = #{category}
            AND price > ${price}
            </select>
        </mapper>
        """
        rows = generate_sql(text)
        self.assertEqual(rows, [{'sql_id': 'testParameters',
                                 'sql': '\nSELECT name,\n       category,\n       price\nFROM fruits\nWHERE category = ?\n  AND price > ?'}]
                         )


class TestSQLReview(TestCase):
    """
    测试sql review内的方法
    """

    def setUp(self):
        self.superuser = User.objects.create(username='super', is_superuser=True)
        self.user = User.objects.create(username='user')
        # 使用 travis.ci 时实例和测试service保持一致
        self.master = Instance(instance_name='test_instance', type='master', db_type='mysql',
                               host=settings.DATABASES['default']['HOST'],
                               port=settings.DATABASES['default']['PORT'],
                               user=settings.DATABASES['default']['USER'],
                               password=settings.DATABASES['default']['PASSWORD'])
        self.master.save()
        self.sys_config = SysConfig()
        self.client = Client()
        self.group = ResourceGroup.objects.create(group_id=1, group_name='group_name')
        self.wf1 = SqlWorkflow.objects.create(
            workflow_name='workflow_name',
            group_id=self.group.group_id,
            group_name=self.group.group_name,
            engineer=self.superuser.username,
            engineer_display=self.superuser.display,
            audit_auth_groups='audit_auth_groups',
            create_time=datetime.datetime.now(),
            status='workflow_review_pass',
            is_backup='是',
            instance=self.master,
            db_name='db_name',
            syntax_type=1,
        )
        self.wfc1 = SqlWorkflowContent.objects.create(
            workflow=self.wf1,
            sql_content='some_sql',
            execute_result=''
        )

    def tearDown(self):
        self.wf1.delete()
        self.group.delete()
        self.superuser.delete()
        self.user.delete()
        self.master.delete()
        self.sys_config.replace(json.dumps({}))

    @patch('sql.engines.get_engine')
    def test_auto_review_hit_review_regex(self, _get_engine, ):
        """
        测试自动审批通过的判定条件，命中判断正则
        :return:
        """
        # 开启自动审批设置
        self.sys_config.set('auto_review', 'true')
        self.sys_config.set('auto_review_regex', '^drop')  # drop语句需要审批
        self.sys_config.set('auto_review_max_update_rows', '50')  # update影响行数大于50需要审批
        self.sys_config.get_all_config()
        # 修改工单为drop
        self.wfc1.sql_content = "drop table users;"
        self.wfc1.save(update_fields=('sql_content',))
        r = is_auto_review(self.wfc1.workflow_id)
        self.assertFalse(r)

    @patch('sql.engines.mysql.MysqlEngine.execute_check')
    @patch('sql.engines.get_engine')
    def test_auto_review_gt_max_update_rows(self, _get_engine, _execute_check):
        """
        测试自动审批通过的判定条件，影响行数大于auto_review_max_update_rows
        :return:
        """
        # 开启自动审批设置
        self.sys_config.set('auto_review', 'true')
        self.sys_config.set('auto_review_regex', '^drop')  # drop语句需要审批
        self.sys_config.set('auto_review_max_update_rows', '2')  # update影响行数大于2需要审批
        self.sys_config.get_all_config()
        # 修改工单为update
        self.wfc1.sql_content = "update table users set email='';"
        self.wfc1.save(update_fields=('sql_content',))
        # mock返回值，update影响行数=3
        _execute_check.return_value.to_dict.return_value = [
            {"id": 1, "stage": "CHECKED", "errlevel": 0, "stagestatus": "Audit completed", "errormessage": "None",
             "sql": "use archer_test", "affected_rows": 0, "sequence": "'0_0_0'", "backup_dbname": "None",
             "execute_time": "0", "sqlsha1": "", "actual_affected_rows": 'null'},
            {"id": 2, "stage": "CHECKED", "errlevel": 0, "stagestatus": "Audit completed", "errormessage": "None",
             "sql": "update table users set email=''", "affected_rows": 3, "sequence": "'0_0_1'",
             "backup_dbname": "mysql_3306_archer_test", "execute_time": "0", "sqlsha1": "",
             "actual_affected_rows": 'null'}]
        r = is_auto_review(self.wfc1.workflow_id)
        self.assertFalse(r)

    @patch('sql.engines.mysql.MysqlEngine.execute_check')
    @patch('sql.engines.get_engine')
    def test_auto_review_true(self, _get_engine, _execute_check):
        """
        测试自动审批通过的判定条件，
        :return:
        """
        # 开启自动审批设置
        self.sys_config.set('auto_review', 'true')
        self.sys_config.set('auto_review_regex', '^drop')  # drop语句需要审批
        self.sys_config.set('auto_review_max_update_rows', '2')  # update影响行数大于2需要审批
        self.sys_config.get_all_config()
        # 修改工单为update
        self.wfc1.sql_content = "update table users set email='';"
        self.wfc1.save(update_fields=('sql_content',))
        # mock返回值，update影响行数=3
        _execute_check.return_value.to_dict.return_value = [
            {"id": 1, "stage": "CHECKED", "errlevel": 0, "stagestatus": "Audit completed", "errormessage": "None",
             "sql": "use archer_test", "affected_rows": 0, "sequence": "'0_0_0'", "backup_dbname": "None",
             "execute_time": "0", "sqlsha1": "", "actual_affected_rows": 'null'},
            {"id": 2, "stage": "CHECKED", "errlevel": 0, "stagestatus": "Audit completed", "errormessage": "None",
             "sql": "update table users set email=''", "affected_rows": 1, "sequence": "'0_0_1'",
             "backup_dbname": "mysql_3306_archer_test", "execute_time": "0", "sqlsha1": "",
             "actual_affected_rows": 'null'}]
        r = is_auto_review(self.wfc1.workflow_id)
        self.assertTrue(r)

    def test_can_execute_for_resource_group(self, ):
        """
        测试是否能执行的判定条件,登录用户有资源组粒度执行权限，并且为组内用户
        :return:
        """
        # 修改工单为workflow_review_pass，登录用户有资源组粒度执行权限，并且为组内用户
        self.wf1.status = 'workflow_review_pass'
        self.wf1.save(update_fields=('status',))
        sql_execute_for_resource_group = Permission.objects.get(codename='sql_execute_for_resource_group')
        self.user.user_permissions.add(sql_execute_for_resource_group)
        ResourceGroupRelations.objects.create(object_type=0, object_id=self.user.id, group_id=self.group.group_id)
        r = can_execute(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    def test_can_execute_true(self, ):
        """
        测试是否能执行的判定条件,当前登录用户为提交人，并且有执行权限,工单状态为审核通过
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人，并且有执行权限
        self.wf1.status = 'workflow_review_pass'
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=('status', 'engineer'))
        sql_execute = Permission.objects.get(codename='sql_execute')
        self.user.user_permissions.add(sql_execute)
        r = can_execute(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    def test_can_execute_workflow_timing_task(self, ):
        """
        测试是否能执行的判定条件,当前登录用户为提交人，并且有执行权限,工单状态为定时执行
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人，并且有执行权限
        self.wf1.status = 'workflow_timingtask'
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=('status', 'engineer'))
        sql_execute = Permission.objects.get(codename='sql_execute')
        self.user.user_permissions.add(sql_execute)
        r = can_execute(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    def test_can_execute_false_no_permission(self, ):
        """
        当前登录用户为提交人，但是没有执行权限
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人，并且有执行权限
        self.wf1.status = 'workflow_timingtask'
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=('status', 'engineer'))
        r = can_execute(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertFalse(r)

    def test_can_execute_false_not_in_group(self, ):
        """
        当前登录用户为提交人，有资源组粒度执行权限，但是不是组内用户
        :return:
        """
        # 修改工单为workflow_review_pass，有资源组粒度执行权限，但是不是组内用户
        self.wf1.status = 'workflow_review_pass'
        self.wf1.save(update_fields=('status',))
        sql_execute_for_resource_group = Permission.objects.get(codename='sql_execute_for_resource_group')
        self.user.user_permissions.add(sql_execute_for_resource_group)
        r = can_execute(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertFalse(r)

    def test_can_execute_false_wrong_status(self, ):
        """
        当前登录用户为提交人，前登录用户为提交人，并且有执行权限,但是工单状态为待审核
        :return:
        """
        # 修改工单为workflow_manreviewing，当前登录用户为提交人，并且有执行权限, 但是工单状态为待审核
        self.wf1.status = 'workflow_manreviewing'
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=('status', 'engineer'))
        sql_execute = Permission.objects.get(codename='sql_execute')
        self.user.user_permissions.add(sql_execute)
        r = can_execute(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertFalse(r)

    def test_can_timingtask_true(self, ):
        """
        测试是否能定时执行的判定条件,当前登录用户为提交人，并且有执行权限,工单状态为审核通过
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人，并且有执行权限
        self.wf1.status = 'workflow_review_pass'
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=('status', 'engineer'))
        sql_execute = Permission.objects.get(codename='sql_execute')
        self.user.user_permissions.add(sql_execute)
        r = can_timingtask(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    def test_can_timingtask_false(self, ):
        """
        测试是否能定时执行的判定条件,当前登录有执行权限,工单状态为审核通过，但用户不是提交人
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人，并且有执行权限
        self.wf1.status = 'workflow_review_pass'
        self.wf1.engineer = self.superuser.username
        self.wf1.save(update_fields=('status', 'engineer'))
        sql_execute = Permission.objects.get(codename='sql_execute')
        self.user.user_permissions.add(sql_execute)
        r = can_timingtask(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertFalse(r)

    @patch('sql.utils.workflow_audit.Audit.can_review')
    def test_can_cancel_true_for_apply_user(self, _can_review):
        """
        测试是否能取消，审核中的工单，提交人可终止
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.status = 'workflow_manreviewing'
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=('status', 'engineer'))
        _can_review.return_value = False
        r = can_cancel(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    @patch('sql.utils.workflow_audit.Audit.can_review')
    def test_can_cancel_true_for_audit_user(self, _can_review):
        """
        测试是否能取消，审核中的工单，审核人可终止
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.status = 'workflow_manreviewing'
        self.wf1.engineer = self.superuser.username
        self.wf1.save(update_fields=('status', 'engineer'))
        _can_review.return_value = True
        r = can_cancel(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    @patch('sql.utils.sql_review.can_execute')
    def test_can_cancel_true_for_execute_user(self, _can_execute):
        """
        测试是否能取消，审核通过但未执行的工单，有执行权限的用户终止
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.status = 'workflow_review_pass'
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=('status', 'engineer'))
        _can_execute.return_value = True
        r = can_cancel(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    @patch('sql.utils.sql_review.can_execute')
    def test_can_cancel_false(self, _can_execute):
        """
        测试是否能取消，审核通过但未执行的工单，无执行权限的用户无法终止
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.status = 'workflow_review_pass'
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=('status', 'engineer'))
        _can_execute.return_value = False
        r = can_cancel(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertFalse(r)
