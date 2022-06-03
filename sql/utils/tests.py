# -*- coding: UTF-8 -*-
"""
@author: hhyo
@license: Apache Licence
@file: tests.py
@time: 2019/03/14
"""

import os
import sys
import os
import django

import datetime
import json
from unittest.mock import patch, MagicMock

from django.conf import settings
from django.contrib.auth.models import Permission, Group
from django.test import TestCase, Client
from django_q.models import Schedule

from common.config import SysConfig
from common.utils.const import WorkflowDict
from sql.engines.models import ReviewResult, ReviewSet
from sql.models import Users, SqlWorkflow, SqlWorkflowContent, Instance, ResourceGroup, \
    WorkflowLog, WorkflowAudit, WorkflowAuditDetail, WorkflowAuditSetting, \
    QueryPrivilegesApply, DataMaskingRules, DataMaskingColumns, InstanceTag, ArchiveConfig
from sql.utils.resource_group import user_groups, user_instances, auth_group_users
from sql.utils.sql_review import is_auto_review, can_execute, can_timingtask, can_cancel, on_correct_time_period
from sql.utils.sql_utils import *
from sql.utils.execute_sql import execute, execute_callback
from sql.utils.tasks import add_sql_schedule, del_schedule, task_info
from sql.utils.workflow_audit import Audit
from sql.utils.data_masking import data_masking, brute_mask, simple_column_mask

User = Users
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

    def test_get_syntax_type_by_re(self):
        """
        测试语法判断，不使用sqlparse解析,直接正则匹配判断
        :return:
        """
        dml_sql = "select * from users;"
        ddl_sql = "alter table users add id int not null default 0 comment 'id' "
        other_sql = 'show engine innodb status'
        self.assertEqual(get_syntax_type(dml_sql, parser=False, db_type='mysql'), 'DML')
        self.assertEqual(get_syntax_type(ddl_sql, parser=False, db_type='mysql'), 'DDL')
        self.assertIsNone(get_syntax_type(other_sql, parser=False, db_type='mysql'))

    def test_remove_comments(self):
        """
        测试去除SQL注释
        :return:
        """
        sql1 = """   # This comment continues to the end of line
        SELECT 1+1;     # This comment continues to the end of line"""
        sql2 = """-- This comment continues to the end of line
        SELECT 1+1;     -- This comment continues to the end of line"""
        sql3 = """/* this is an in-line comment */
        SELECT 1 /* this is an in-line comment */ + 1;/* this is an in-line comment */"""
        self.assertEqual(remove_comments(sql1, db_type='mysql'),
                         'SELECT 1+1;     # This comment continues to the end of line')
        self.assertEqual(remove_comments(sql2, db_type='mysql'),
                         'SELECT 1+1;     -- This comment continues to the end of line')
        self.assertEqual(remove_comments(sql3, db_type='mysql'),
                         'SELECT 1  + 1;')

    def test_extract_tables_by_sql_parse(self):
        """
        测试表解析
        :return:
        """
        sql = "select * from user.users a join logs.log b on a.id=b.id;"
        self.assertEqual(extract_tables(sql), [{'name': 'users', 'schema': 'user'}, {'name': 'log', 'schema': 'logs'}])

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
            is_backup=True,
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
        self.sys_config.set('auto_review_db_type', 'mysql')
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
        self.sys_config.set('auto_review_db_type', 'mysql')
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

    @patch('sql.engines.get_engine')
    def test_auto_review_true(self, _get_engine):
        """
        测试自动审批通过的判定条件，
        :return:
        """
        # 开启自动审批设置
        self.sys_config.set('auto_review', 'true')
        self.sys_config.set('auto_review_db_type', 'mysql')
        self.sys_config.set('auto_review_regex', '^drop')  # drop语句需要审批
        self.sys_config.set('auto_review_max_update_rows', '2')  # update影响行数大于2需要审批
        self.sys_config.set('auto_review_tag', 'GA')  # 仅GA开启自动审批
        self.sys_config.get_all_config()
        # 修改工单为update，mock返回值，update影响行数=3
        self.wfc1.sql_content = "update table users set email='';"
        self.wfc1.review_content = json.dumps([
            {"id": 1, "stage": "CHECKED", "errlevel": 0, "stagestatus": "Audit completed", "errormessage": "None",
             "sql": "use archer_test", "affected_rows": 0, "sequence": "'0_0_0'", "backup_dbname": "None",
             "execute_time": "0", "sqlsha1": "", "actual_affected_rows": 'null'},
            {"id": 2, "stage": "CHECKED", "errlevel": 0, "stagestatus": "Audit completed", "errormessage": "None",
             "sql": "update table users set email=''", "affected_rows": 1, "sequence": "'0_0_1'",
             "backup_dbname": "mysql_3306_archer_test", "execute_time": "0", "sqlsha1": "",
             "actual_affected_rows": 'null'}])
        self.wfc1.save(update_fields=('sql_content', 'review_content'))
        # 修改工单实例标签
        tag, is_created = InstanceTag.objects.get_or_create(tag_code='GA',
                                                            defaults={'tag_name': '生产环境', 'active': True})
        self.wf1.instance.instance_tag.add(tag)
        r = is_auto_review(self.wfc1.workflow_id)
        self.assertTrue(r)

    @patch('sql.engines.get_engine')
    def test_auto_review_false(self, _get_engine):
        """
        测试自动审批通过的判定条件，
        :return:
        """
        # 开启自动审批设置
        self.sys_config.set('auto_review', 'true')
        self.sys_config.set('auto_review_db_type', '')  # 未配置auto_review_db_type需要审批
        self.sys_config.set('auto_review_regex', '^drop')  # drop语句需要审批
        self.sys_config.set('auto_review_max_update_rows', '2')  # update影响行数大于2需要审批
        self.sys_config.set('auto_review_tag', 'GA')  # 仅GA开启自动审批
        self.sys_config.get_all_config()
        # 修改工单为update，mock返回值，update影响行数=3
        self.wfc1.sql_content = "update table users set email='';"
        self.wfc1.review_content = json.dumps([
            {"id": 1, "stage": "CHECKED", "errlevel": 0, "stagestatus": "Audit completed", "errormessage": "None",
             "sql": "use archer_test", "affected_rows": 0, "sequence": "'0_0_0'", "backup_dbname": "None",
             "execute_time": "0", "sqlsha1": "", "actual_affected_rows": 'null'},
            {"id": 2, "stage": "CHECKED", "errlevel": 0, "stagestatus": "Audit completed", "errormessage": "None",
             "sql": "update table users set email=''", "affected_rows": 1, "sequence": "'0_0_1'",
             "backup_dbname": "mysql_3306_archer_test", "execute_time": "0", "sqlsha1": "",
             "actual_affected_rows": 'null'}])
        self.wfc1.save(update_fields=('sql_content', 'review_content'))
        # 修改工单实例标签
        tag, is_created = InstanceTag.objects.get_or_create(tag_code='GA',
                                                            defaults={'tag_name': '生产环境', 'active': True})
        self.wf1.instance.instance_tag.add(tag)
        r = is_auto_review(self.wfc1.workflow_id)
        self.assertFalse(r)

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
        self.user.resource_group.add(self.group)
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
    def test_can_cancel_true_for_submit_user(self, _can_execute):
        """
        测试是否能取消，审核通过但未执行的工单，提交人可终止
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.status = 'workflow_review_pass'
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=('status', 'engineer'))
        _can_execute.return_value = True
        r = can_cancel(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    def test_on_correct_time_period(self):
        """
        测试验证时间在可执行时间内
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.run_date_start = '2019-06-15 11:10:00'
        self.wf1.run_date_end = '2019-06-15 11:30:00'
        self.wf1.save(update_fields=('run_date_start', 'run_date_end'))
        run_date = datetime.datetime.strptime('2019-06-15 11:15:00', "%Y-%m-%d %H:%M:%S")
        r = on_correct_time_period(self.wf1.id, run_date=run_date)
        self.assertTrue(r)

    def test_not_in_correct_time_period(self):
        """
        测试验证时间不在可执行时间内
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.run_date_start = '2019-06-15 11:10:00'
        self.wf1.run_date_end = '2019-06-15 11:30:00'
        self.wf1.save(update_fields=('run_date_start', 'run_date_end'))
        run_date = datetime.datetime.strptime('2019-06-15 11:45:00', "%Y-%m-%d %H:%M:%S")
        r = on_correct_time_period(self.wf1.id, run_date=run_date)
        self.assertFalse(r)

    @patch('sql.utils.sql_review.datetime')
    def test_now_on_correct_time_period(self, _datetime):
        """
        测试当前时间在可执行时间内
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.run_date_start = '2019-06-15 11:10:00'
        self.wf1.run_date_end = '2019-06-15 11:30:00'
        self.wf1.save(update_fields=('run_date_start', 'run_date_end'))
        _datetime.datetime.now.return_value = datetime.datetime.strptime(
            '2019-06-15 11:15:00', "%Y-%m-%d %H:%M:%S")
        r = on_correct_time_period(self.wf1.id)
        self.assertTrue(r)

    @patch('sql.utils.sql_review.datetime')
    def test_now_not_in_correct_time_period(self, _datetime):
        """
        测试当前时间不在可执行时间内
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.run_date_start = '2019-06-15 11:10:00'
        self.wf1.run_date_end = '2019-06-15 11:30:00'
        self.wf1.save(update_fields=('run_date_start', 'run_date_end'))
        _datetime.datetime.now.return_value = datetime.datetime.strptime(
            '2019-06-15 11:55:00', "%Y-%m-%d %H:%M:%S")
        r = on_correct_time_period(self.wf1.id)
        self.assertFalse(r)


class TestExecuteSql(TestCase):
    def setUp(self):
        self.ins = Instance.objects.create(instance_name='some_ins', type='slave', db_type='mysql',
                                           host='some_host',
                                           port=3306, user='ins_user', password='some_str')
        self.wf = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer_display='',
            audit_auth_groups='some_group',
            create_time=datetime.datetime.now(),
            status='workflow_timingtask',
            is_backup=True,
            instance=self.ins,
            db_name='some_db',
            syntax_type=1
        )
        SqlWorkflowContent.objects.create(workflow=self.wf,
                                          sql_content='some_sql',
                                          execute_result=ReviewSet(rows=[ReviewResult(
                                              id=0,
                                              stage='Execute failed',
                                              errlevel=2,
                                              stagestatus='异常终止',
                                              errormessage='',
                                              sql='执行异常信息',
                                              affected_rows=0,
                                              actual_affected_rows=0,
                                              sequence='0_0_0',
                                              backup_dbname=None,
                                              execute_time=0,
                                              sqlsha1='')]).json())

    def tearDown(self):
        self.ins.delete()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()
        WorkflowLog.objects.all().delete()

    @patch('sql.utils.execute_sql.Audit')
    @patch('sql.engines.mysql.MysqlEngine.execute_workflow')
    @patch('sql.engines.get_engine')
    def test_execute(self, _get_engine, _execute_workflow, _audit):
        _audit.detail_by_workflow_id.return_value.audit_id = 1
        execute(self.wf.id)
        _execute_workflow.assert_called_once()
        _audit.add_log.assert_called_with(
            audit_id=1,
            operation_type=5,
            operation_type_desc='执行工单',
            operation_info='系统定时执行工单',
            operator='',
            operator_display='系统',
        )

    @patch('sql.utils.execute_sql.notify_for_execute')
    @patch('sql.utils.execute_sql.Audit')
    def test_execute_callback_success(self, _audit, _notify):
        # 初始化工单执行返回对象
        self.task_result = MagicMock()
        self.task_result.args = [self.wf.id]
        self.task_result.success = True
        self.task_result.stopped = datetime.datetime.now()
        self.task_result.result.json.return_value = json.dumps([{'id': 1, 'sql': 'some_content'}])
        self.task_result.result.warning = ''
        self.task_result.result.error = ''
        _audit.detail_by_workflow_id.return_value.audit_id = 123
        _audit.add_log.return_value = 'any thing'
        # 先处理为执行中
        self.wf.status = 'workflow_executing'
        self.wf.save(update_fields=['status'])
        execute_callback(self.task_result)
        _audit.detail_by_workflow_id.assert_called_with(workflow_id=self.wf.id, workflow_type=2)
        _audit.add_log.assert_called_with(
            audit_id=123,
            operation_type=6,
            operation_type_desc='执行结束',
            operation_info="执行结果：已正常结束",
            operator='',
            operator_display='系统',
        )
        _notify.assert_called_once()

    @patch('sql.utils.execute_sql.notify_for_execute')
    @patch('sql.utils.execute_sql.Audit')
    def test_execute_callback_failure(self, _audit, _notify):
        # 初始化工单执行返回对象
        self.task_result = MagicMock()
        self.task_result.args = [self.wf.id]
        self.task_result.success = False
        self.task_result.stopped = datetime.datetime.now()
        self.task_result.result = '执行异常'
        _audit.detail_by_workflow_id.return_value.audit_id = 123
        _audit.add_log.return_value = 'any thing'
        # 处理状态为执行中
        self.wf.status = 'workflow_executing'
        self.wf.save(update_fields=['status'])
        execute_callback(self.task_result)
        _audit.detail_by_workflow_id.assert_called_with(workflow_id=self.wf.id, workflow_type=2)
        _audit.add_log.assert_called_with(
            audit_id=123,
            operation_type=6,
            operation_type_desc='执行结束',
            operation_info="执行结果：执行有异常",
            operator='',
            operator_display='系统',
        )
        _notify.assert_called_once()

    @patch('sql.utils.execute_sql.notify_for_execute')
    @patch('sql.utils.execute_sql.Audit')
    def test_execute_callback_failure_no_execute_result(self, _audit, _notify):
        # 初始化工单执行返回对象
        self.task_result = MagicMock()
        self.task_result.args = [self.wf.id]
        self.task_result.success = False
        self.task_result.stopped = datetime.datetime.now()
        self.task_result.result = '执行异常'
        _audit.detail_by_workflow_id.return_value.audit_id = 123
        _audit.add_log.return_value = 'any thing'
        # 删除execute_result、处理为执行中
        self.wf.sqlworkflowcontent.execute_result = ''
        self.wf.sqlworkflowcontent.save()
        self.wf.status = 'workflow_executing'
        self.wf.save(update_fields=['status'])
        execute_callback(self.task_result)
        _audit.detail_by_workflow_id.assert_called_with(workflow_id=self.wf.id, workflow_type=2)
        _audit.add_log.assert_called_with(
            audit_id=123,
            operation_type=6,
            operation_type_desc='执行结束',
            operation_info="执行结果：执行有异常",
            operator='',
            operator_display='系统',
        )
        _notify.assert_called_once()


class TestTasks(TestCase):
    def setUp(self):
        self.Schedule = Schedule.objects.create(name='some_name')

    def tearDown(self):
        Schedule.objects.all().delete()

    @patch('sql.utils.tasks.schedule')
    def test_add_sql_schedule(self, _schedule):
        add_sql_schedule('test', datetime.datetime.now(), 1)
        _schedule.assert_called_once()

    def test_del_schedule(self):
        del_schedule('some_name')
        with self.assertRaises(Schedule.DoesNotExist):
            Schedule.objects.get(name='some_name')

    def test_del_schedule_not_exists(self):
        del_schedule('some_name1')

    def test_task_info(self):
        task_info('some_name')

    def test_task_info_not_exists(self):
        with self.assertRaises(Schedule.DoesNotExist):
            Schedule.objects.get(name='some_name1')


class TestAudit(TestCase):
    def setUp(self):
        self.sys_config = SysConfig()
        self.user = User.objects.create(username='test_user', display='中文显示', is_active=True)
        self.su = User.objects.create(username='s_user', display='中文显示', is_active=True, is_superuser=True)
        tomorrow = datetime.datetime.today() + datetime.timedelta(days=1)
        self.ins = Instance.objects.create(instance_name='some_ins', type='slave', db_type='mysql',
                                           host='some_host',
                                           port=3306, user='ins_user', password='some_str')
        self.res_group = ResourceGroup.objects.create(group_id=1, group_name='group_name')
        self.wf = SqlWorkflow.objects.create(
            workflow_name='some_name',
            group_id=1,
            group_name='g1',
            engineer_display='',
            audit_auth_groups='some_audit_group',
            create_time=datetime.datetime.now(),
            status='workflow_timingtask',
            is_backup=True,
            instance=self.ins,
            db_name='some_db',
            syntax_type=1
        )
        SqlWorkflowContent.objects.create(workflow=self.wf,
                                          sql_content='some_sql',
                                          execute_result='')
        self.query_apply_1 = QueryPrivilegesApply.objects.create(
            group_id=1,
            group_name='some_name',
            title='some_title1',
            user_name='some_user',
            instance=self.ins,
            db_list='some_db,some_db2',
            limit_num=100,
            valid_date=tomorrow,
            priv_type=1,
            status=0,
            audit_auth_groups='some_audit_group'
        )
        self.archive_apply_1 = ArchiveConfig.objects.create(
            title='title',
            resource_group=self.res_group,
            audit_auth_groups='some_audit_group',
            src_instance=self.ins,
            src_db_name='src_db_name',
            src_table_name='src_table_name',
            dest_instance=self.ins,
            dest_db_name='src_db_name',
            dest_table_name='src_table_name',
            condition='1=1',
            mode='file',
            no_delete=True,
            sleep=1,
            status=WorkflowDict.workflow_status['audit_wait'],
            state=False,
            user_name='some_user',
            user_display='display',
        )
        self.audit = WorkflowAudit.objects.create(
            group_id=1,
            group_name='some_group',
            workflow_id=1,
            workflow_type=1,
            workflow_title='申请标题',
            workflow_remark='申请备注',
            audit_auth_groups='1,2,3',
            current_audit='1',
            next_audit='2',
            current_status=0)
        self.wl = WorkflowLog.objects.create(audit_id=self.audit.audit_id,
                                             operation_type=1)

    def tearDown(self):
        self.sys_config.purge()
        User.objects.all().delete()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()
        WorkflowAudit.objects.all().delete()
        WorkflowAuditDetail.objects.all().delete()
        WorkflowAuditSetting.objects.all().delete()
        QueryPrivilegesApply.objects.all().delete()
        WorkflowLog.objects.all().delete()
        ResourceGroup.objects.all().delete()
        ArchiveConfig.objects.all().delete()

    def test_audit_add_query(self):
        """ 测试添加查询审核工单"""
        result = Audit.add(1, self.query_apply_1.apply_id)
        audit_id = result['data']['audit_id']
        workflow_status = result['data']['workflow_status']
        self.assertEqual(workflow_status, WorkflowDict.workflow_status['audit_wait'])
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        # 当前审批
        self.assertEqual(audit_detail.current_audit, 'some_audit_group')
        # 无下级审批
        self.assertEqual(audit_detail.next_audit, '-1')
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).first()
        self.assertEqual(log_info.operation_type, 0)
        self.assertEqual(log_info.operation_type_desc, '提交')
        self.assertIn('等待审批，审批流程：', log_info.operation_info)

    def test_audit_add_sqlreview(self):
        """ 测试添加上线审核工单"""
        result = Audit.add(2, self.wf.id)
        audit_id = result['data']['audit_id']
        workflow_status = result['data']['workflow_status']
        self.assertEqual(workflow_status, WorkflowDict.workflow_status['audit_wait'])
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        # 当前审批
        self.assertEqual(audit_detail.current_audit, 'some_audit_group')
        # 无下级审批
        self.assertEqual(audit_detail.next_audit, '-1')
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).first()
        self.assertEqual(log_info.operation_type, 0)
        self.assertEqual(log_info.operation_type_desc, '提交')
        self.assertIn('等待审批，审批流程：', log_info.operation_info)

    def test_audit_add_archive_review(self):
        """ 测试添加数据归档工单"""
        result = Audit.add(3, self.archive_apply_1.id)
        audit_id = result['data']['audit_id']
        workflow_status = result['data']['workflow_status']
        self.assertEqual(workflow_status, WorkflowDict.workflow_status['audit_wait'])
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        # 当前审批
        self.assertEqual(audit_detail.current_audit, 'some_audit_group')
        # 无下级审批
        self.assertEqual(audit_detail.next_audit, '-1')
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).first()
        self.assertEqual(log_info.operation_type, 0)
        self.assertEqual(log_info.operation_type_desc, '提交')
        self.assertIn('等待审批，审批流程：', log_info.operation_info)

    def test_audit_add_wrong_type(self):
        """ 测试添加不存在的类型"""
        with self.assertRaisesMessage(Exception, '工单类型不存在'):
            Audit.add(4, 1)

    def test_audit_add_settings_not_exists(self):
        """ 测试审批流程未配置"""
        self.wf.audit_auth_groups = ''
        self.wf.save()
        with self.assertRaisesMessage(Exception, '审批流程不能为空，请先配置审批流程'):
            Audit.add(2, self.wf.id)

    def test_audit_add_duplicate(self):
        """测试重复提交"""
        Audit.add(2, self.wf.id)
        with self.assertRaisesMessage(Exception, '该工单当前状态为待审核，请勿重复提交'):
            Audit.add(2, self.wf.id)

    @patch('sql.utils.workflow_audit.is_auto_review', return_value=True)
    def test_audit_add_auto_review(self, _is_auto_review):
        """测试提交自动审核通过"""
        self.sys_config.set('auto_review', 'true')
        result = Audit.add(2, self.wf.id)
        audit_id = result['data']['audit_id']
        workflow_status = result['data']['workflow_status']
        self.assertEqual(workflow_status, WorkflowDict.workflow_status['audit_success'])
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        # 无下级审批
        self.assertEqual(audit_detail.next_audit, '-1')
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).first()
        self.assertEqual(log_info.operation_type, 0)
        self.assertEqual(log_info.operation_type_desc, '提交')
        self.assertEqual(log_info.operation_info, '无需审批，系统直接审核通过')

    def test_audit_add_multiple_audit(self):
        """测试提交多级审核"""
        self.wf.audit_auth_groups = '1,2,3'
        self.wf.save()
        result = Audit.add(2, self.wf.id)
        audit_id = result['data']['audit_id']
        workflow_status = result['data']['workflow_status']
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        self.assertEqual(workflow_status, WorkflowDict.workflow_status['audit_wait'])
        # 存在下级审批
        self.assertEqual(audit_detail.current_audit, '1')
        self.assertEqual(audit_detail.next_audit, '2')
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).first()
        self.assertEqual(log_info.operation_type, 0)
        self.assertEqual(log_info.operation_type_desc, '提交')
        self.assertIn('等待审批，审批流程：', log_info.operation_info)

    def test_audit_success_not_exists_next(self):
        """测试审核通过、无下一级"""
        self.audit.current_audit = '3'
        self.audit.next_audit = '-1'
        self.audit.save()
        result = Audit.audit(self.audit.audit_id,
                             WorkflowDict.workflow_status['audit_success'],
                             self.user.username,
                             '通过')
        audit_id = self.audit.audit_id
        workflow_status = result['data']['workflow_status']
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        self.assertEqual(workflow_status, WorkflowDict.workflow_status['audit_success'])
        # 不存在下级审批
        self.assertEqual(audit_detail.next_audit, '-1')
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).order_by('-id').first()
        self.assertEqual(log_info.operator, self.user.username)
        self.assertEqual(log_info.operator_display, self.user.display)
        self.assertEqual(log_info.operation_type, 1)
        self.assertEqual(log_info.operation_type_desc, '审批通过')
        self.assertEqual(log_info.operation_info, f'审批备注：通过，下级审批：None')

    def test_audit_success_exists_next(self):
        """测试审核通过、存在下一级"""
        self.audit.current_audit = '1'
        self.audit.next_audit = '2'
        self.audit.save()
        result = Audit.audit(self.audit.audit_id,
                             WorkflowDict.workflow_status['audit_success'],
                             self.user.username,
                             '通过')
        audit_id = self.audit.audit_id
        workflow_status = result['data']['workflow_status']
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        self.assertEqual(workflow_status, WorkflowDict.workflow_status['audit_wait'])
        # 存在下级审批
        self.assertEqual(audit_detail.next_audit, '3')
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).order_by('-id').first()
        self.assertEqual(log_info.operator, self.user.username)
        self.assertEqual(log_info.operator_display, self.user.display)
        self.assertEqual(log_info.operation_type, 1)
        self.assertEqual(log_info.operation_type_desc, '审批通过')
        self.assertEqual(log_info.operation_info, f'审批备注：通过，下级审批：2')

    def test_audit_reject(self):
        """测试审核不通过"""
        result = Audit.audit(self.audit.audit_id,
                             WorkflowDict.workflow_status['audit_reject'],
                             self.user.username,
                             '不通过')
        audit_id = self.audit.audit_id
        workflow_status = result['data']['workflow_status']
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        self.assertEqual(workflow_status, WorkflowDict.workflow_status['audit_reject'])
        # 不存在下级审批
        self.assertEqual(audit_detail.next_audit, '-1')
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).order_by('-id').first()
        self.assertEqual(log_info.operator, self.user.username)
        self.assertEqual(log_info.operator_display, self.user.display)
        self.assertEqual(log_info.operation_type, 2)
        self.assertEqual(log_info.operation_type_desc, '审批不通过')
        self.assertEqual(log_info.operation_info, f'审批备注：不通过')

    def test_audit_abort(self):
        """测试取消审批"""
        self.audit.create_user = self.user.username
        self.audit.save()
        result = Audit.audit(self.audit.audit_id,
                             WorkflowDict.workflow_status['audit_abort'],
                             self.user.username,
                             '取消')
        audit_id = self.audit.audit_id
        workflow_status = result['data']['workflow_status']
        audit_detail = WorkflowAudit.objects.get(audit_id=audit_id)
        self.assertEqual(workflow_status, WorkflowDict.workflow_status['audit_abort'])
        # 不存在下级审批
        self.assertEqual(audit_detail.next_audit, '-1')
        # 验证日志
        log_info = WorkflowLog.objects.filter(audit_id=audit_id).order_by('-id').first()
        self.assertEqual(log_info.operator, self.user.username)
        self.assertEqual(log_info.operator_display, self.user.display)
        self.assertEqual(log_info.operation_type, 3)
        self.assertEqual(log_info.operation_type_desc, '审批取消')
        self.assertEqual(log_info.operation_info, f'取消原因：取消')

    def test_audit_wrong_exception(self):
        """测试审核异常的状态"""
        with self.assertRaisesMessage(Exception, '审核异常'):
            Audit.audit(self.audit.audit_id, 10, self.user.username, '')

    def test_audit_success_wrong_status(self):
        """测试审核通过，当前状态不是待审核"""
        self.audit.current_status = 1
        self.audit.save()
        with self.assertRaisesMessage(Exception, '工单不是待审核状态，请返回刷新'):
            Audit.audit(self.audit.audit_id, WorkflowDict.workflow_status['audit_success'], self.user.username, '')

    def test_audit_reject_wrong_status(self):
        """测试审核不通过，当前状态不是待审核"""
        self.audit.current_status = 1
        self.audit.save()
        with self.assertRaisesMessage(Exception, '工单不是待审核状态，请返回刷新'):
            Audit.audit(self.audit.audit_id, WorkflowDict.workflow_status['audit_reject'], self.user.username, '')

    def test_audit_abort_wrong_status(self):
        """测试审核不通过，当前状态不是待审核"""
        self.audit.current_status = 2
        self.audit.save()
        with self.assertRaisesMessage(Exception, '工单不是待审核态/审核通过状态，请返回刷新'):
            Audit.audit(self.audit.audit_id, WorkflowDict.workflow_status['audit_abort'], self.user.username, '')

    @patch('sql.utils.workflow_audit.user_groups', return_value=[])
    def test_todo(self, _user_groups):
        """TODO 测试todo数量,未断言"""
        Audit.todo(self.user)
        Audit.todo(self.su)

    def test_detail(self):
        """测试获取审核信息"""
        result = Audit.detail(self.audit.audit_id)
        self.assertEqual(result, self.audit)
        result = Audit.detail(0)
        self.assertEqual(result, None)

    def test_detail_by_workflow_id(self):
        """测试通过业务id获取审核信息"""
        self.audit.workflow_type = WorkflowDict.workflow_type['sqlreview']
        self.audit.workflow_id = self.wf.id
        self.audit.save()
        result = Audit.detail_by_workflow_id(self.wf.id, WorkflowDict.workflow_type['sqlreview'])
        self.assertEqual(result, self.audit)
        result = Audit.detail_by_workflow_id(0, 0)
        self.assertEqual(result, None)

    def test_settings(self):
        """测试通过组和审核类型，获取审核配置信息"""
        WorkflowAuditSetting.objects.create(workflow_type=1, group_id=1, audit_auth_groups='1,2,3')
        result = Audit.settings(workflow_type=1, group_id=1)
        self.assertEqual(result, '1,2,3')
        result = Audit.settings(0, 0)
        self.assertEqual(result, None)

    def test_change_settings_edit(self):
        """修改配置信息"""
        ws = WorkflowAuditSetting.objects.create(workflow_type=1, group_id=1, audit_auth_groups='1,2,3')
        Audit.change_settings(workflow_type=1, group_id=1, audit_auth_groups='1,2')
        ws = WorkflowAuditSetting.objects.get(audit_setting_id=ws.audit_setting_id)
        self.assertEqual(ws.audit_auth_groups, '1,2')

    def test_change_settings_add(self):
        """添加配置信息"""
        Audit.change_settings(workflow_type=1, group_id=1, audit_auth_groups='1,2')
        ws = WorkflowAuditSetting.objects.get(workflow_type=1, group_id=1)
        self.assertEqual(ws.audit_auth_groups, '1,2')

    @patch('sql.utils.workflow_audit.auth_group_users')
    @patch('sql.utils.workflow_audit.Audit.detail_by_workflow_id')
    def test_can_review_sql_review(self, _detail_by_workflow_id, _auth_group_users):
        """测试判断用户当前是否是可审核上线工单，非管理员拥有权限"""
        sql_review = Permission.objects.get(codename='sql_review')
        self.user.user_permissions.add(sql_review)
        aug = Group.objects.create(name='auth_group')
        _detail_by_workflow_id.return_value.current_audit = aug.id
        _auth_group_users.return_value.filter.exists = True
        self.audit.workflow_type = WorkflowDict.workflow_type['sqlreview']
        self.audit.workflow_id = self.wf.id
        self.audit.save()
        r = Audit.can_review(self.user, self.audit.workflow_id, self.audit.workflow_type)
        self.assertEqual(r, True)

    @patch('sql.utils.workflow_audit.auth_group_users')
    @patch('sql.utils.workflow_audit.Audit.detail_by_workflow_id')
    def test_can_review_query_review(self, _detail_by_workflow_id, _auth_group_users):
        """测试判断用户当前是否是可审核查询工单，非管理员拥有权限"""
        query_review = Permission.objects.get(codename='query_review')
        self.user.user_permissions.add(query_review)
        aug = Group.objects.create(name='auth_group')
        _detail_by_workflow_id.return_value.current_audit = aug.id
        _auth_group_users.return_value.filter.exists = True
        self.audit.workflow_type = WorkflowDict.workflow_type['query']
        self.audit.workflow_id = self.query_apply_1.apply_id
        self.audit.save()
        r = Audit.can_review(self.user, self.audit.workflow_id, self.audit.workflow_type)
        self.assertEqual(r, True)

    @patch('sql.utils.workflow_audit.auth_group_users')
    @patch('sql.utils.workflow_audit.Audit.detail_by_workflow_id')
    def test_can_review_sql_review_super(self, _detail_by_workflow_id, _auth_group_users):
        """测试判断用户当前是否是可审核查询工单，用户是管理员"""
        aug = Group.objects.create(name='auth_group')
        _detail_by_workflow_id.return_value.current_audit = aug.id
        _auth_group_users.return_value.filter.exists = True
        self.audit.workflow_type = WorkflowDict.workflow_type['sqlreview']
        self.audit.workflow_id = self.wf.id
        self.audit.save()
        r = Audit.can_review(self.su, self.audit.workflow_id, self.audit.workflow_type)
        self.assertEqual(r, True)

    @patch('sql.utils.workflow_audit.auth_group_users')
    @patch('sql.utils.workflow_audit.Audit.detail_by_workflow_id')
    def test_can_review_wrong_status(self, _detail_by_workflow_id, _auth_group_users):
        """测试判断用户当前是否是可审核，非待审核工单"""
        aug = Group.objects.create(name='auth_group')
        _detail_by_workflow_id.return_value.current_audit = aug.id
        _auth_group_users.return_value.filter.exists = True
        self.audit.workflow_type = WorkflowDict.workflow_type['sqlreview']
        self.audit.workflow_id = self.wf.id
        self.audit.current_status = WorkflowDict.workflow_status['audit_success']
        self.audit.save()
        r = Audit.can_review(self.user, self.audit.workflow_id, self.audit.workflow_type)
        self.assertEqual(r, False)

    @patch('sql.utils.workflow_audit.auth_group_users')
    @patch('sql.utils.workflow_audit.Audit.detail_by_workflow_id')
    def test_can_review_no_prem(self, _detail_by_workflow_id, _auth_group_users):
        """测试判断用户当前是否是可审核，普通用户无权限"""
        aug = Group.objects.create(name='auth_group')
        _detail_by_workflow_id.return_value.current_audit = aug.id
        _auth_group_users.return_value.filter.exists = True
        self.audit.workflow_type = WorkflowDict.workflow_type['sqlreview']
        self.audit.workflow_id = self.wf.id
        self.audit.save()
        r = Audit.can_review(self.user, self.audit.workflow_id, self.audit.workflow_type)
        self.assertEqual(r, False)

    @patch('sql.utils.workflow_audit.auth_group_users')
    @patch('sql.utils.workflow_audit.Audit.detail_by_workflow_id')
    def test_can_review_no_prem_exception(self, _detail_by_workflow_id, _auth_group_users):
        """测试判断用户当前是否是可审核，权限组不存在"""
        Group.objects.create(name='auth_group')
        _detail_by_workflow_id.side_effect = RuntimeError()
        _auth_group_users.return_value.filter.exists = True
        self.audit.workflow_type = WorkflowDict.workflow_type['sqlreview']
        self.audit.workflow_id = self.wf.id
        self.audit.save()
        with self.assertRaisesMessage(Exception, '当前审批auth_group_id不存在，请检查并清洗历史数据'):
            Audit.can_review(self.user, self.audit.workflow_id, self.audit.workflow_type)

    def test_review_info_no_review(self):
        """测试获取当前工单审批流程和当前审核组，无需审批"""
        self.audit.workflow_type = WorkflowDict.workflow_type['sqlreview']
        self.audit.workflow_id = self.wf.id
        self.audit.audit_auth_groups = ''
        self.audit.current_audit = '-1'
        self.audit.save()
        audit_auth_group, current_audit_auth_group = Audit.review_info(self.audit.workflow_id, self.audit.workflow_type)
        self.assertEqual(audit_auth_group, '无需审批')
        self.assertEqual(current_audit_auth_group, None)

    def test_review_info(self):
        """测试获取当前工单审批流程和当前审核组，无需审批"""
        aug = Group.objects.create(name='DBA')
        self.audit.workflow_type = WorkflowDict.workflow_type['sqlreview']
        self.audit.workflow_id = self.wf.id
        self.audit.audit_auth_groups = str(aug.id)
        self.audit.current_audit = str(aug.id)
        self.audit.save()
        audit_auth_group, current_audit_auth_group = Audit.review_info(self.audit.workflow_id, self.audit.workflow_type)
        self.assertEqual(audit_auth_group, 'DBA')
        self.assertEqual(current_audit_auth_group, 'DBA')

    def test_logs(self):
        """测试获取工单日志"""
        r = Audit.logs(self.audit.audit_id).first()
        self.assertEqual(r, self.wl)


class TestDataMasking(TestCase):
    def setUp(self):
        self.superuser = User.objects.create(username='super', is_superuser=True)
        self.user = User.objects.create(username='user')
        self.ins = Instance.objects.create(instance_name='some_ins', type='slave', db_type='mysql',
                                           host='some_host',
                                           port=3306, user='ins_user', password='some_str')
        self.sys_config = SysConfig()
        self.wf1 = SqlWorkflow.objects.create(
            workflow_name='workflow_name',
            group_id=1,
            group_name='group_name',
            engineer=self.superuser.username,
            engineer_display=self.superuser.display,
            audit_auth_groups='audit_auth_groups',
            create_time=datetime.datetime.now(),
            status='workflow_review_pass',
            is_backup=True,
            instance=self.ins,
            db_name='db_name',
            syntax_type=1,
        )
        DataMaskingRules.objects.create(
            rule_type=1,
            rule_regex='(.{3})(.*)(.{4})',
            hide_group=2)
        DataMaskingColumns.objects.create(
            rule_type=1,
            active=True,
            instance=self.ins,
            table_schema='archer_test',
            table_name='users',
            column_name='phone')

    def tearDown(self):
        User.objects.all().delete()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()
        DataMaskingColumns.objects.all().delete()
        DataMaskingRules.objects.all().delete()

    @patch('sql.utils.data_masking.GoInceptionEngine')
    def test_data_masking_not_hit_rules(self, _inception):
        DataMaskingColumns.objects.all().delete()
        DataMaskingRules.objects.all().delete()
        _inception.return_value.query_data_masking.return_value = [
            {"index": 0, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "phone"}
        ]
        sql = """select phone from users;"""
        rows = (('18888888888',), ('18888888889',), ('18888888810',))
        query_result = ReviewSet(column_list=['phone'], rows=rows, full_sql=sql)
        r = data_masking(self.ins, 'archery', sql, query_result)
        print("test_data_masking_not_hit_rules:", r.rows)
        self.assertEqual(r, query_result)

    @patch('sql.utils.data_masking.GoInceptionEngine')
    def test_data_masking_hit_rules_not_exists_star(self, _inception):
        _inception.return_value.query_data_masking.return_value = [
            {"index": 0, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "phone"}
        ]
        sql = """select phone from users;"""
        rows = (('18888888888',), ('18888888889',), ('18888888810',))
        query_result = ReviewSet(column_list=['phone'], rows=rows, full_sql=sql)
        r = data_masking(self.ins, 'archery', sql, query_result)
        print("test_data_masking_hit_rules_not_exists_star:", r.rows)
        mask_result_rows = [['188****8888', ], ['188****8889', ], ['188****8810', ]]
        self.assertEqual(r.rows, mask_result_rows)

    @patch('sql.utils.data_masking.GoInceptionEngine')
    def test_data_masking_hit_rules_exists_star(self, _inception):
        """[*]"""
        _inception.return_value.query_data_masking.return_value = [
            {"index": 0, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "phone"}
        ]
        sql = """select * from users;"""
        rows = (('18888888888',), ('18888888889',), ('18888888810',))
        query_result = ReviewSet(column_list=['phone'], rows=rows, full_sql=sql)
        r = data_masking(self.ins, 'archery', sql, query_result)
        print("test_data_masking_hit_rules_exists_star:", r.rows)
        mask_result_rows = [['188****8888', ], ['188****8889', ], ['188****8810', ]]
        self.assertEqual(r.rows, mask_result_rows)

    @patch('sql.utils.data_masking.GoInceptionEngine')
    def test_data_masking_hit_rules_star_and_column(self, _inception):
        """[*,column_a]"""
        _inception.return_value.query_data_masking.return_value = [
            {"index": 0, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "phone"},
            {"index": 1, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "phone"},
        ]
        sql = """select *,phone from users;"""
        rows = (('18888888888', '18888888888',),
                ('18888888889', '18888888889',),)
        query_result = ReviewSet(column_list=['phone', 'phone'], rows=rows, full_sql=sql)
        r = data_masking(self.ins, 'archery', sql, query_result)
        print("test_data_masking_hit_rules_star_and_column", r.rows)
        mask_result_rows = [['188****8888', '188****8888', ],
                            ['188****8889', '188****8889', ]]
        self.assertEqual(r.rows, mask_result_rows)

    @patch('sql.utils.data_masking.GoInceptionEngine')
    def test_data_masking_hit_rules_column_and_star(self, _inception):
        """[column_a, *]"""
        _inception.return_value.query_data_masking.return_value = [
            {"index": 0, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "phone"},
            {"index": 1, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "phone"}
        ]
        sql = """select phone,* from users;"""
        rows = (('18888888888', '18888888888',),
                ('18888888889', '18888888889',))
        query_result = ReviewSet(column_list=['phone', 'phone'], rows=rows, full_sql=sql)
        r = data_masking(self.ins, 'archery', sql, query_result)
        print("test_data_masking_hit_rules_column_and_star", r.rows)
        mask_result_rows = [['188****8888', '188****8888', ],
                            ['188****8889', '188****8889', ]]
        self.assertEqual(r.rows, mask_result_rows)

    @patch('sql.utils.data_masking.GoInceptionEngine')
    def test_data_masking_hit_rules_column_and_star_and_column(self, _inception):
        """[column_a,a.*,column_b]"""
        _inception.return_value.query_data_masking.return_value = [
            {"index": 0, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "phone"},
            {"index": 1, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "phone"},
            {"index": 2, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "phone"}
        ]
        sql = """select phone,*,phone from users;"""
        rows = (('18888888888', '18888888888', '18888888888',),
                ('18888888889', '18888888889', '18888888889',))
        query_result = ReviewSet(column_list=['phone', 'phone', 'phone'], rows=rows, full_sql=sql)
        r = data_masking(self.ins, 'archery', sql, query_result)
        print("test_data_masking_hit_rules_column_and_star_and_column", r.rows)
        mask_result_rows = [['188****8888', '188****8888', '188****8888', ],
                            ['188****8889', '188****8889', '188****8889', ]]
        self.assertEqual(r.rows, mask_result_rows)

    @patch('sql.utils.data_masking.GoInceptionEngine')
    def test_data_masking_hit_rules_star_and_column_and_star(self, _inception):
        """[a.*, column_a, b.*]"""
        _inception.return_value.query_data_masking.return_value = [
            {"index": 0, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "phone"},
            {"index": 1, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "phone"},
            {"index": 2, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "phone"}
        ]
        sql = """select a.*,phone,a.* from users a;"""
        rows = (('18888888888', '18888888888', '18888888888',),
                ('18888888889', '18888888889', '18888888889',))
        query_result = ReviewSet(column_list=['phone', 'phone', 'phone'], rows=rows, full_sql=sql)
        r = data_masking(self.ins, 'archery', sql, query_result)
        print("test_data_masking_hit_rules_star_and_column_and_star", r.rows)
        mask_result_rows = [['188****8888', '188****8888', '188****8888', ],
                            ['188****8889', '188****8889', '188****8889', ]]
        self.assertEqual(r.rows, mask_result_rows)

    @patch('sql.utils.data_masking.GoInceptionEngine')
    def test_data_masking_concat_function_support(self, _inception):
        """concat_函数支持"""
        _inception.return_value.query_data_masking.return_value = [
            {"index": 0, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "concat(phone,1)"}
        ]
        sql = """select concat(phone,1) from users;"""
        rows = (('18888888888',), ('18888888889',), ('18888888810',))
        query_result = ReviewSet(column_list=['concat(phone,1)'], rows=rows, full_sql=sql)
        r = data_masking(self.ins, 'archery', sql, query_result)
        mask_result_rows = [['188****8888', ], ['188****8889', ], ['188****8810', ]]
        print("test_data_masking_concat_function_support", r.rows)
        self.assertEqual(r.rows, mask_result_rows)

    @patch('sql.utils.data_masking.GoInceptionEngine')
    def test_data_masking_max_function_support(self, _inception):
        """max_函数支持"""
        _inception.return_value.query_data_masking.return_value = [
            {"index": 0, "field": "phone", "type": "varchar(80)", "table": "users", "schema": "archer_test",
             "alias": "max(phone+1)"}
        ]
        sql = """select max(phone+1) from users;"""
        rows = (('18888888888',), ('18888888889',), ('18888888810',))
        query_result = ReviewSet(column_list=['max(phone+1)'], rows=rows, full_sql=sql)
        mask_result_rows = [['188****8888', ], ['188****8889', ], ['188****8810', ]]
        r = data_masking(self.ins, 'archery', sql, query_result)
        print("test_data_masking_max_function_support", r.rows)
        self.assertEqual(r.rows, mask_result_rows)

    @patch('sql.utils.data_masking.GoInceptionEngine')
    def test_data_masking_union_support_keyword(self, _inception):
        """union关键字"""
        self.sys_config.set('query_check', 'true')
        self.sys_config.get_all_config()
        _inception.return_value.query_data_masking.return_value = [
            {'index': 0, 'field': 'phone', 'type': 'varchar(80)', 'table': 'users', 'schema': 'archer_test',
             'alias': 'phone'},
            {'index': 1, 'field': 'phone', 'type': 'varchar(80)', 'table': 'users', 'schema': 'archer_test',
             'alias': 'phone'}

        ]
        sqls = ["select phone from users union select phone from users;",
                "select phone from users union all select phone from users;"]
        rows = (('18888888888',), ('18888888889',), ('18888888810',))
        mask_result_rows = [['188****8888', ], ['188****8889', ], ['188****8810', ]]
        for sql in sqls:
            query_result = ReviewSet(column_list=['phone'], rows=rows, full_sql=sql)
            r = data_masking(self.ins, 'archery', sql, query_result)
            print("test_data_masking_union_support_keyword", r.rows)
            self.assertEqual(r.rows, mask_result_rows)

    def test_brute_mask(self):
        sql = """select * from users;"""
        rows = (('18888888888',), ('18888888889',), ('18888888810',))
        query_result = ReviewSet(column_list=['phone'], rows=rows, full_sql=sql)
        r = brute_mask(self.ins, query_result)
        mask_result_rows = [('188****8888',), ('188****8889',), ('188****8810',)]
        self.assertEqual(r.rows, mask_result_rows)

    def test_simple_column_mask(self):
        sql = """select * from users;"""
        rows = (('18888888888',), ('18888888889',), ('18888888810',))
        query_result = ReviewSet(column_list=['phone'], rows=rows, full_sql=sql)
        r = simple_column_mask(self.ins, query_result)
        mask_result_rows = [('188****8888',), ('188****8889',), ('188****8810',)]
        self.assertEqual(r.rows, mask_result_rows)


class TestResourceGroup(TestCase):
    def setUp(self):
        self.sys_config = SysConfig()
        self.user = User.objects.create(username='test_user', display='中文显示', is_active=True)
        self.su = User.objects.create(username='s_user', display='中文显示', is_active=True, is_superuser=True)
        self.ins1 = Instance.objects.create(instance_name='some_ins1', type='slave', db_type='mysql',
                                            host='some_host',
                                            port=3306, user='ins_user', password='some_str')
        self.ins2 = Instance.objects.create(instance_name='some_ins2', type='slave', db_type='mysql',
                                            host='some_host',
                                            port=3306, user='ins_user', password='some_str')
        self.rgp1 = ResourceGroup.objects.create(group_name='group1')
        self.rgp2 = ResourceGroup.objects.create(group_name='group2')
        self.agp = Group.objects.create(name='auth_group')

    def tearDown(self):
        self.sys_config.purge()
        User.objects.all().delete()
        Instance.objects.all().delete()
        ResourceGroup.objects.all().delete()
        Group.objects.all().delete()

    def test_user_groups_super(self):
        """获取用户关联资源组列表，超级管理员"""
        groups = user_groups(self.su)
        self.assertEqual(groups.__len__(), 2)
        self.assertIn(self.rgp1, groups)
        self.assertIn(self.rgp2, groups)

    def test_user_groups(self):
        """获取用户关联资源组列表，普通用户"""
        self.user.resource_group.add(self.rgp1)
        groups = user_groups(self.user)
        self.assertEqual(groups.__len__(), 1)
        self.assertIn(self.rgp1, groups)

    def test_user_instances_super(self):
        """获取用户实例列表，超级管理员"""
        self.ins1.resource_group.add(self.rgp1)
        ins = user_instances(self.su)
        self.assertEqual(ins.__len__(), 2)
        self.assertIn(self.ins1, ins)
        self.assertIn(self.ins2, ins)

    def test_user_instances_associated_group(self):
        """获取用户实例列表，普通用户关联资源组"""
        self.user.resource_group.add(self.rgp1)
        self.ins1.resource_group.add(self.rgp1)
        ins = user_instances(self.user)
        self.assertEqual(ins.__len__(), 1)
        self.assertIn(self.ins1, ins)

    def test_user_instances_unassociated_group(self):
        """获取用户实例列表，普通用户未关联资源组"""
        self.ins1.resource_group.add(self.rgp1)
        ins = user_instances(self.user)
        self.assertEqual(ins.__len__(), 0)

    def test_auth_group_users(self):
        """获取资源组内关联指定权限组的用户"""
        # 用户关联权限组
        self.user.groups.add(self.agp)
        # 用户关联资源组
        self.user.resource_group.add(self.rgp1)
        # 获取资源组内关联指定权限组的用户
        users = auth_group_users(auth_group_names=[self.agp.name], group_id=self.rgp1.group_id)
        self.assertIn(self.user, users)
