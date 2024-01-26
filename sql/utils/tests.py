# -*- coding: UTF-8 -*-
"""
@author: hhyo
@license: Apache Licence
@file: tests.py
@time: 2019/03/14
"""

import datetime
import json
from unittest.mock import patch, MagicMock

from django.conf import settings
from django.contrib.auth.models import Permission, Group
from django.test import TestCase, Client
from django_q.models import Schedule

from common.config import SysConfig
from sql.engines.models import ReviewResult, ReviewSet
from sql.models import (
    Users,
    SqlWorkflow,
    SqlWorkflowContent,
    Instance,
    ResourceGroup,
    WorkflowLog,
    DataMaskingRules,
    DataMaskingColumns,
    InstanceTag,
)
from sql.utils.resource_group import user_groups, user_instances, auth_group_users
from sql.utils.sql_review import (
    can_execute,
    can_timingtask,
    can_cancel,
    on_correct_time_period,
)
from sql.utils.sql_utils import *
from sql.utils.execute_sql import execute, execute_callback
from sql.utils.tasks import add_sql_schedule, del_schedule, task_info
from sql.utils.data_masking import data_masking, brute_mask, simple_column_mask

User = Users
__author__ = "hhyo"


class TestSQLUtils(TestCase):
    def test_get_syntax_type(self):
        """
        测试语法判断
        :return:
        """
        dml_sql = "select * from users;"
        ddl_sql = "alter table users add id not null default 0 comment 'id' "
        self.assertEqual(get_syntax_type(dml_sql), "DML")
        self.assertEqual(get_syntax_type(ddl_sql), "DDL")

    def test_get_syntax_type_by_re(self):
        """
        测试语法判断，不使用sqlparse解析,直接正则匹配判断
        :return:
        """
        dml_sql = "select * from users;"
        ddl_sql = "alter table users add id int not null default 0 comment 'id' "
        other_sql = "show engine innodb status"
        self.assertEqual(get_syntax_type(dml_sql, parser=False, db_type="mysql"), "DML")
        self.assertEqual(get_syntax_type(ddl_sql, parser=False, db_type="mysql"), "DDL")
        self.assertIsNone(get_syntax_type(other_sql, parser=False, db_type="mysql"))

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
        self.assertEqual(
            remove_comments(sql1, db_type="mysql"),
            "SELECT 1+1;     # This comment continues to the end of line",
        )
        self.assertEqual(
            remove_comments(sql2, db_type="mysql"),
            "SELECT 1+1;     -- This comment continues to the end of line",
        )
        self.assertEqual(remove_comments(sql3, db_type="mysql"), "SELECT 1  + 1;")

    def test_extract_tables_by_sql_parse(self):
        """
        测试表解析
        :return:
        """
        sql = "select * from user.users a join logs.log b on a.id=b.id;"
        self.assertEqual(
            extract_tables(sql),
            [{"name": "users", "schema": "user"}, {"name": "log", "schema": "logs"}],
        )

    def test_generate_sql_from_sql(self):
        """
        测试从SQl文本中解析SQL
        :return:
        """
        text = "select * from sql_user;select * from sql_workflow;"
        rows = generate_sql(text)
        self.assertListEqual(
            rows,
            [
                {"sql_id": 1, "sql": "select * from sql_user;"},
                {"sql_id": 2, "sql": "select * from sql_workflow;"},
            ],
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
        self.assertEqual(
            rows,
            [
                {
                    "sql_id": "testParameters",
                    "sql": "\nSELECT name,\n       category,\n       price\nFROM fruits\nWHERE category = ?\n  AND price > ?",
                }
            ],
        )

    def test_get_full_sqlitem_list_anonymous_plsql(self):
        """
        测试SQL文本中plsql可执行块（匿名块）自动分割
        :return:
        """
        text = """
declare
    v_rowcount integer;
begin
    select count(1) into v_rowcount  from user_tables
      where table_name = upper('test2'); --账户特定关系人信息历史表
    if v_rowcount = 0 then
        execute IMMEDIATE '
        create table test2
        (
        vc_bfcyid           int,           --受益人信息唯一标志ID
        vc_specperid        VARCHAR2(100)  --特定关系人信息唯一标志ID
        )
        ';
        execute IMMEDIATE '
        CREATE index Idx_test2_1 ON test2(VC_BFCYID)
        ';
    end if;
end;
/

BEGIN
    insert into test2 values(1,'qq1');
    commit;
END;
/
"""
        lists = get_full_sqlitem_list(text, "db")
        rows = [
            SqlItem(
                id=0,
                statement="""declare
    v_rowcount integer;
begin
    select count(1) into v_rowcount  from user_tables
      where table_name = upper('test2'); --账户特定关系人信息历史表
    if v_rowcount = 0 then
        execute IMMEDIATE '
        create table test2
        (
        vc_bfcyid           int,           --受益人信息唯一标志ID
        vc_specperid        VARCHAR2(100)  --特定关系人信息唯一标志ID
        )
        ';
        execute IMMEDIATE '
        CREATE index Idx_test2_1 ON test2(VC_BFCYID)
        ';
    end if;
end;""",
                stmt_type="PLSQL",
                object_owner="db",
                object_type="ANONYMOUS",
                object_name="ANONYMOUS",
            ),
            SqlItem(
                id=0,
                statement="""BEGIN
    insert into test2 values(1,'qq1');
    commit;
END;""",
                stmt_type="PLSQL",
                object_owner="db",
                object_type="ANONYMOUS",
                object_name="ANONYMOUS",
            ),
        ]
        self.assertIsInstance(lists[0], SqlItem)
        self.assertIsInstance(lists[1], SqlItem)
        self.assertEqual(lists[0].__dict__, rows[0].__dict__)
        self.assertEqual(lists[1].__dict__, rows[1].__dict__)

    def test_get_full_sqlitem_list_plsql(self):
        """
        测试SQL文本中plsql对象定义语句（存储过程、函数等）自动分割
        :return:
        """
        text = """
create or replace procedure INSERTUSER
(id IN NUMBER,
name IN VARCHAR2)
is
begin
    insert into user1 values(id,name);
end;
/

create or replace function annual_income(name1 varchar2)
return number is
annual_salary number(7,2);
begin
    select sal*12+nvl(comm,0) into annual_salary from emp where lower(ename)=lower(name1);
return annual_salary;
end;
/
"""
        lists = get_full_sqlitem_list(text, "db")
        rows = [
            SqlItem(
                id=0,
                statement="""create or replace procedure INSERTUSER
(id IN NUMBER,
name IN VARCHAR2)
is
begin
    insert into user1 values(id,name);
end;""",
                stmt_type="PLSQL",
                object_owner="db",
                object_type="PROCEDURE",
                object_name="INSERTUSER",
            ),
            SqlItem(
                id=0,
                statement="""create or replace function annual_income(name1 varchar2)
return number is
annual_salary number(7,2);
begin
    select sal*12+nvl(comm,0) into annual_salary from emp where lower(ename)=lower(name1);
return annual_salary;
end;""",
                stmt_type="PLSQL",
                object_owner="db",
                object_type="FUNCTION",
                object_name="ANNUAL_INCOME",
            ),
        ]
        self.assertIsInstance(lists[0], SqlItem)
        self.assertIsInstance(lists[1], SqlItem)
        self.assertEqual(lists[0].__dict__, rows[0].__dict__)
        self.assertEqual(lists[1].__dict__, rows[1].__dict__)

    def test_get_full_sqlitem_list_sql_after_plsql(self):
        """
        测试SQL文本中plsql后面普通SQL语句以;自动分割
        :return:
        """
        text = """
create or replace procedure INSERTUSER
(id IN NUMBER,
name IN VARCHAR2)
is
begin
    insert into user1 values(id,name);
end;
/
update user_account set created=sysdate where account_no=1; 
create table user(
    id int,
    uname varchar(100),
    age int
);
"""
        sql1 = "update user_account set created=sysdate where account_no=1;"
        sql2 = """create table user(
    id int,
    uname varchar(100),
    age int
);"""
        lists = get_full_sqlitem_list(text, "db")
        rows = [
            SqlItem(
                id=0,
                statement=sqlparse.format(
                    sql1, strip_comments=True, reindent=True, keyword_case="lower"
                ),
                stmt_type="SQL",
                object_owner="",
                object_type="",
                object_name="",
            ),
            SqlItem(
                id=0,
                statement=sqlparse.format(
                    sql2, strip_comments=True, reindent=True, keyword_case="lower"
                ),
                stmt_type="SQL",
                object_owner="",
                object_type="",
                object_name="",
            ),
        ]
        self.assertIsInstance(lists[1], SqlItem)
        self.assertIsInstance(lists[2], SqlItem)
        self.assertEqual(lists[1].__dict__, rows[0].__dict__)
        self.assertEqual(lists[2].__dict__, rows[1].__dict__)

    def test_get_full_sqlitem_list_sql(self):
        """
        测试普通SQL（不包含plsql执行块和plsql对象定义块）文本，以;符号进行SQL语句分割
        :return:
        """
        text = """
update user_account set created=sysdate where account_no=1; 
create table user(
    id int,
    uname varchar(100),
    age int
);
"""
        sql1 = "update user_account set created=sysdate where account_no=1;"
        sql2 = """create table user(
    id int,
    uname varchar(100),
    age int
);"""
        lists = get_full_sqlitem_list(text, "db")
        rows = [
            SqlItem(
                id=0,
                statement=sqlparse.format(
                    sql1, strip_comments=True, reindent=True, keyword_case="lower"
                ),
                stmt_type="SQL",
                object_owner="",
                object_type="",
                object_name="",
            ),
            SqlItem(
                id=0,
                statement=sqlparse.format(
                    sql2, strip_comments=True, reindent=True, keyword_case="lower"
                ),
                stmt_type="SQL",
                object_owner="",
                object_type="",
                object_name="",
            ),
        ]
        self.assertIsInstance(lists[0], SqlItem)
        self.assertIsInstance(lists[1], SqlItem)
        self.assertEqual(lists[0].__dict__, rows[0].__dict__)
        self.assertEqual(lists[1].__dict__, rows[1].__dict__)


class TestSQLReview(TestCase):
    """
    测试sql review内的方法
    """

    def setUp(self):
        self.superuser = User.objects.create(username="super", is_superuser=True)
        self.user = User.objects.create(username="user")
        # 使用 travis.ci 时实例和测试service保持一致
        self.master = Instance(
            instance_name="test_instance",
            type="master",
            db_type="mysql",
            host=settings.DATABASES["default"]["HOST"],
            port=settings.DATABASES["default"]["PORT"],
            user=settings.DATABASES["default"]["USER"],
            password=settings.DATABASES["default"]["PASSWORD"],
        )
        self.master.save()
        self.sys_config = SysConfig()
        self.client = Client()
        self.group = ResourceGroup.objects.create(group_id=1, group_name="group_name")
        self.wf1 = SqlWorkflow.objects.create(
            workflow_name="workflow_name",
            group_id=self.group.group_id,
            group_name=self.group.group_name,
            engineer=self.superuser.username,
            engineer_display=self.superuser.display,
            audit_auth_groups="audit_auth_groups",
            create_time=datetime.datetime.now(),
            status="workflow_review_pass",
            is_backup=True,
            instance=self.master,
            db_name="db_name",
            syntax_type=1,
        )
        self.wfc1 = SqlWorkflowContent.objects.create(
            workflow=self.wf1, sql_content="some_sql", execute_result=""
        )

    def tearDown(self):
        self.wf1.delete()
        self.group.delete()
        self.superuser.delete()
        self.user.delete()
        self.master.delete()
        self.sys_config.replace(json.dumps({}))

    def test_can_execute_for_resource_group(
        self,
    ):
        """
        测试是否能执行的判定条件,登录用户有资源组粒度执行权限，并且为组内用户
        :return:
        """
        # 修改工单为workflow_review_pass，登录用户有资源组粒度执行权限，并且为组内用户
        self.wf1.status = "workflow_review_pass"
        self.wf1.save(update_fields=("status",))
        sql_execute_for_resource_group = Permission.objects.get(
            codename="sql_execute_for_resource_group"
        )
        self.user.user_permissions.add(sql_execute_for_resource_group)
        self.user.resource_group.add(self.group)
        r = can_execute(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    def test_can_execute_true(
        self,
    ):
        """
        测试是否能执行的判定条件,当前登录用户为提交人，并且有执行权限,工单状态为审核通过
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人，并且有执行权限
        self.wf1.status = "workflow_review_pass"
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=("status", "engineer"))
        sql_execute = Permission.objects.get(codename="sql_execute")
        self.user.user_permissions.add(sql_execute)
        r = can_execute(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    def test_can_execute_workflow_timing_task(
        self,
    ):
        """
        测试是否能执行的判定条件,当前登录用户为提交人，并且有执行权限,工单状态为定时执行
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人，并且有执行权限
        self.wf1.status = "workflow_timingtask"
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=("status", "engineer"))
        sql_execute = Permission.objects.get(codename="sql_execute")
        self.user.user_permissions.add(sql_execute)
        r = can_execute(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    def test_can_execute_false_no_permission(
        self,
    ):
        """
        当前登录用户为提交人，但是没有执行权限
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人，并且有执行权限
        self.wf1.status = "workflow_timingtask"
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=("status", "engineer"))
        r = can_execute(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertFalse(r)

    def test_can_execute_false_not_in_group(
        self,
    ):
        """
        当前登录用户为提交人，有资源组粒度执行权限，但是不是组内用户
        :return:
        """
        # 修改工单为workflow_review_pass，有资源组粒度执行权限，但是不是组内用户
        self.wf1.status = "workflow_review_pass"
        self.wf1.save(update_fields=("status",))
        sql_execute_for_resource_group = Permission.objects.get(
            codename="sql_execute_for_resource_group"
        )
        self.user.user_permissions.add(sql_execute_for_resource_group)
        r = can_execute(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertFalse(r)

    def test_can_execute_false_wrong_status(
        self,
    ):
        """
        当前登录用户为提交人，前登录用户为提交人，并且有执行权限,但是工单状态为待审核
        :return:
        """
        # 修改工单为workflow_manreviewing，当前登录用户为提交人，并且有执行权限, 但是工单状态为待审核
        self.wf1.status = "workflow_manreviewing"
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=("status", "engineer"))
        sql_execute = Permission.objects.get(codename="sql_execute")
        self.user.user_permissions.add(sql_execute)
        r = can_execute(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertFalse(r)

    def test_can_timingtask_true(
        self,
    ):
        """
        测试是否能定时执行的判定条件,当前登录用户为提交人，并且有执行权限,工单状态为审核通过
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人，并且有执行权限
        self.wf1.status = "workflow_review_pass"
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=("status", "engineer"))
        sql_execute = Permission.objects.get(codename="sql_execute")
        self.user.user_permissions.add(sql_execute)
        r = can_timingtask(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    def test_can_timingtask_false(
        self,
    ):
        """
        测试是否能定时执行的判定条件,当前登录有执行权限,工单状态为审核通过，但用户不是提交人
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人，并且有执行权限
        self.wf1.status = "workflow_review_pass"
        self.wf1.engineer = self.superuser.username
        self.wf1.save(update_fields=("status", "engineer"))
        sql_execute = Permission.objects.get(codename="sql_execute")
        self.user.user_permissions.add(sql_execute)
        r = can_timingtask(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertFalse(r)

    @patch("sql.utils.workflow_audit.Audit.can_review")
    def test_can_cancel_true_for_apply_user(self, _can_review):
        """
        测试是否能取消，审核中的工单，提交人可终止
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.status = "workflow_manreviewing"
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=("status", "engineer"))
        _can_review.return_value = False
        r = can_cancel(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    @patch("sql.utils.workflow_audit.Audit.can_review")
    def test_can_cancel_true_for_audit_user(self, _can_review):
        """
        测试是否能取消，审核中的工单，审核人可终止
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.status = "workflow_manreviewing"
        self.wf1.engineer = self.superuser.username
        self.wf1.save(update_fields=("status", "engineer"))
        _can_review.return_value = True
        r = can_cancel(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    @patch("sql.utils.sql_review.can_execute")
    def test_can_cancel_true_for_execute_user(self, _can_execute):
        """
        测试是否能取消，审核通过但未执行的工单，有执行权限的用户终止
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.status = "workflow_review_pass"
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=("status", "engineer"))
        _can_execute.return_value = True
        r = can_cancel(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    @patch("sql.utils.sql_review.can_execute")
    def test_can_cancel_true_for_submit_user(self, _can_execute):
        """
        测试是否能取消，审核通过但未执行的工单，提交人可终止
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.status = "workflow_review_pass"
        self.wf1.engineer = self.user.username
        self.wf1.save(update_fields=("status", "engineer"))
        _can_execute.return_value = True
        r = can_cancel(user=self.user, workflow_id=self.wfc1.workflow_id)
        self.assertTrue(r)

    def test_on_correct_time_period(self):
        """
        测试验证时间在可执行时间内
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.run_date_start = "2019-06-15 11:10:00"
        self.wf1.run_date_end = "2019-06-15 11:30:00"
        self.wf1.save(update_fields=("run_date_start", "run_date_end"))
        run_date = datetime.datetime.strptime(
            "2019-06-15 11:15:00", "%Y-%m-%d %H:%M:%S"
        )
        r = on_correct_time_period(self.wf1.id, run_date=run_date)
        self.assertTrue(r)

    def test_not_in_correct_time_period(self):
        """
        测试验证时间不在可执行时间内
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.run_date_start = "2019-06-15 11:10:00"
        self.wf1.run_date_end = "2019-06-15 11:30:00"
        self.wf1.save(update_fields=("run_date_start", "run_date_end"))
        run_date = datetime.datetime.strptime(
            "2019-06-15 11:45:00", "%Y-%m-%d %H:%M:%S"
        )
        r = on_correct_time_period(self.wf1.id, run_date=run_date)
        self.assertFalse(r)

    @patch("sql.utils.sql_review.datetime")
    def test_now_on_correct_time_period(self, _datetime):
        """
        测试当前时间在可执行时间内
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.run_date_start = "2019-06-15 11:10:00"
        self.wf1.run_date_end = "2019-06-15 11:30:00"
        self.wf1.save(update_fields=("run_date_start", "run_date_end"))
        _datetime.datetime.now.return_value = datetime.datetime.strptime(
            "2019-06-15 11:15:00", "%Y-%m-%d %H:%M:%S"
        )
        r = on_correct_time_period(self.wf1.id)
        self.assertTrue(r)

    @patch("sql.utils.sql_review.datetime")
    def test_now_not_in_correct_time_period(self, _datetime):
        """
        测试当前时间不在可执行时间内
        :return:
        """
        # 修改工单为workflow_review_pass，当前登录用户为提交人
        self.wf1.run_date_start = "2019-06-15 11:10:00"
        self.wf1.run_date_end = "2019-06-15 11:30:00"
        self.wf1.save(update_fields=("run_date_start", "run_date_end"))
        _datetime.datetime.now.return_value = datetime.datetime.strptime(
            "2019-06-15 11:55:00", "%Y-%m-%d %H:%M:%S"
        )
        r = on_correct_time_period(self.wf1.id)
        self.assertFalse(r)


class TestExecuteSql(TestCase):
    def setUp(self):
        self.ins = Instance.objects.create(
            instance_name="some_ins",
            type="slave",
            db_type="mysql",
            host="some_host",
            port=3306,
            user="ins_user",
            password="some_str",
        )
        self.wf = SqlWorkflow.objects.create(
            workflow_name="some_name",
            group_id=1,
            group_name="g1",
            engineer_display="",
            audit_auth_groups="some_group",
            create_time=datetime.datetime.now(),
            status="workflow_timingtask",
            is_backup=True,
            instance=self.ins,
            db_name="some_db",
            syntax_type=1,
        )
        SqlWorkflowContent.objects.create(
            workflow=self.wf,
            sql_content="some_sql",
            execute_result=ReviewSet(
                rows=[
                    ReviewResult(
                        id=0,
                        stage="Execute failed",
                        errlevel=2,
                        stagestatus="异常终止",
                        errormessage="",
                        sql="执行异常信息",
                        affected_rows=0,
                        actual_affected_rows=0,
                        sequence="0_0_0",
                        backup_dbname=None,
                        execute_time=0,
                        sqlsha1="",
                    )
                ]
            ).json(),
        )

    def tearDown(self):
        self.ins.delete()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()
        WorkflowLog.objects.all().delete()

    @patch("sql.utils.execute_sql.Audit")
    @patch("sql.engines.mysql.MysqlEngine.execute_workflow")
    @patch("sql.engines.get_engine")
    def test_execute(self, _get_engine, _execute_workflow, _audit):
        _audit.detail_by_workflow_id.return_value.audit_id = 1
        execute(self.wf.id)
        _execute_workflow.assert_called_once()
        _audit.add_log.assert_called_with(
            audit_id=1,
            operation_type=5,
            operation_type_desc="执行工单",
            operation_info="系统定时执行工单",
            operator="",
            operator_display="系统",
        )

    @patch("sql.utils.execute_sql.notify_for_execute")
    @patch("sql.utils.execute_sql.Audit")
    def test_execute_callback_success(self, _audit, _notify):
        # 初始化工单执行返回对象
        self.task_result = MagicMock()
        self.task_result.args = [self.wf.id]
        self.task_result.success = True
        self.task_result.stopped = datetime.datetime.now()
        self.task_result.result.json.return_value = json.dumps(
            [{"id": 1, "sql": "some_content"}]
        )
        self.task_result.result.warning = ""
        self.task_result.result.error = ""
        _audit.detail_by_workflow_id.return_value.audit_id = 123
        _audit.add_log.return_value = "any thing"
        # 先处理为执行中
        self.wf.status = "workflow_executing"
        self.wf.save(update_fields=["status"])
        execute_callback(self.task_result)
        _audit.detail_by_workflow_id.assert_called_with(
            workflow_id=self.wf.id, workflow_type=2
        )
        _audit.add_log.assert_called_with(
            audit_id=123,
            operation_type=6,
            operation_type_desc="执行结束",
            operation_info="执行结果：已正常结束",
            operator="",
            operator_display="系统",
        )
        _notify.assert_called_once()

    @patch("sql.utils.execute_sql.notify_for_execute")
    @patch("sql.utils.execute_sql.Audit")
    def test_execute_callback_failure(self, _audit, _notify):
        # 初始化工单执行返回对象
        self.task_result = MagicMock()
        self.task_result.args = [self.wf.id]
        self.task_result.success = False
        self.task_result.stopped = datetime.datetime.now()
        self.task_result.result = "执行异常"
        _audit.detail_by_workflow_id.return_value.audit_id = 123
        _audit.add_log.return_value = "any thing"
        # 处理状态为执行中
        self.wf.status = "workflow_executing"
        self.wf.save(update_fields=["status"])
        execute_callback(self.task_result)
        _audit.detail_by_workflow_id.assert_called_with(
            workflow_id=self.wf.id, workflow_type=2
        )
        _audit.add_log.assert_called_with(
            audit_id=123,
            operation_type=6,
            operation_type_desc="执行结束",
            operation_info="执行结果：执行有异常",
            operator="",
            operator_display="系统",
        )
        _notify.assert_called_once()

    @patch("sql.utils.execute_sql.notify_for_execute")
    @patch("sql.utils.execute_sql.Audit")
    def test_execute_callback_failure_no_execute_result(self, _audit, _notify):
        # 初始化工单执行返回对象
        self.task_result = MagicMock()
        self.task_result.args = [self.wf.id]
        self.task_result.success = False
        self.task_result.stopped = datetime.datetime.now()
        self.task_result.result = "执行异常"
        _audit.detail_by_workflow_id.return_value.audit_id = 123
        _audit.add_log.return_value = "any thing"
        # 删除execute_result、处理为执行中
        self.wf.sqlworkflowcontent.execute_result = ""
        self.wf.sqlworkflowcontent.save()
        self.wf.status = "workflow_executing"
        self.wf.save(update_fields=["status"])
        execute_callback(self.task_result)
        _audit.detail_by_workflow_id.assert_called_with(
            workflow_id=self.wf.id, workflow_type=2
        )
        _audit.add_log.assert_called_with(
            audit_id=123,
            operation_type=6,
            operation_type_desc="执行结束",
            operation_info="执行结果：执行有异常",
            operator="",
            operator_display="系统",
        )
        _notify.assert_called_once()


class TestTasks(TestCase):
    def setUp(self):
        self.Schedule = Schedule.objects.create(name="some_name")

    def tearDown(self):
        Schedule.objects.all().delete()

    @patch("sql.utils.tasks.schedule")
    def test_add_sql_schedule(self, _schedule):
        add_sql_schedule("test", datetime.datetime.now(), 1)
        _schedule.assert_called_once()

    def test_del_schedule(self):
        del_schedule("some_name")
        with self.assertRaises(Schedule.DoesNotExist):
            Schedule.objects.get(name="some_name")

    def test_del_schedule_not_exists(self):
        del_schedule("some_name1")

    def test_task_info(self):
        task_info("some_name")

    def test_task_info_not_exists(self):
        with self.assertRaises(Schedule.DoesNotExist):
            Schedule.objects.get(name="some_name1")


class TestDataMasking(TestCase):
    def setUp(self):
        self.superuser = User.objects.create(username="super", is_superuser=True)
        self.user = User.objects.create(username="user")
        self.ins = Instance.objects.create(
            instance_name="some_ins",
            type="slave",
            db_type="mysql",
            host="some_host",
            port=3306,
            user="ins_user",
            password="some_str",
        )
        self.sys_config = SysConfig()
        self.wf1 = SqlWorkflow.objects.create(
            workflow_name="workflow_name",
            group_id=1,
            group_name="group_name",
            engineer=self.superuser.username,
            engineer_display=self.superuser.display,
            audit_auth_groups="audit_auth_groups",
            create_time=datetime.datetime.now(),
            status="workflow_review_pass",
            is_backup=True,
            instance=self.ins,
            db_name="db_name",
            syntax_type=1,
        )
        DataMaskingRules.objects.create(
            rule_type=1, rule_regex="(.{3})(.*)(.{4})", hide_group=2
        )
        DataMaskingColumns.objects.create(
            rule_type=1,
            active=True,
            instance=self.ins,
            table_schema="archer_test",
            table_name="users",
            column_name="phone",
        )

    def tearDown(self):
        User.objects.all().delete()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()
        DataMaskingColumns.objects.all().delete()
        DataMaskingRules.objects.all().delete()

    @patch("sql.utils.data_masking.GoInceptionEngine")
    def test_data_masking_not_hit_rules(self, _inception):
        DataMaskingColumns.objects.all().delete()
        DataMaskingRules.objects.all().delete()
        _inception.return_value.query_data_masking.return_value = [
            {
                "index": 0,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            }
        ]
        sql = """select phone from users;"""
        rows = (("18888888888",), ("18888888889",), ("18888888810",))
        query_result = ReviewSet(column_list=["phone"], rows=rows, full_sql=sql)
        r = data_masking(self.ins, "archery", sql, query_result)
        print("test_data_masking_not_hit_rules:", r.rows)
        self.assertEqual(r, query_result)

    @patch("sql.utils.data_masking.GoInceptionEngine")
    def test_data_masking_hit_rules_not_exists_star(self, _inception):
        _inception.return_value.query_data_masking.return_value = [
            {
                "index": 0,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            }
        ]
        sql = """select phone from users;"""
        rows = (("18888888888",), ("18888888889",), ("18888888810",))
        query_result = ReviewSet(column_list=["phone"], rows=rows, full_sql=sql)
        r = data_masking(self.ins, "archery", sql, query_result)
        print("test_data_masking_hit_rules_not_exists_star:", r.rows)
        mask_result_rows = [
            [
                "188****8888",
            ],
            [
                "188****8889",
            ],
            [
                "188****8810",
            ],
        ]
        self.assertEqual(r.rows, mask_result_rows)

    @patch("sql.utils.data_masking.GoInceptionEngine")
    def test_data_masking_hit_rules_exists_star(self, _inception):
        """[*]"""
        _inception.return_value.query_data_masking.return_value = [
            {
                "index": 0,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            }
        ]
        sql = """select * from users;"""
        rows = (("18888888888",), ("18888888889",), ("18888888810",))
        query_result = ReviewSet(column_list=["phone"], rows=rows, full_sql=sql)
        r = data_masking(self.ins, "archery", sql, query_result)
        print("test_data_masking_hit_rules_exists_star:", r.rows)
        mask_result_rows = [
            [
                "188****8888",
            ],
            [
                "188****8889",
            ],
            [
                "188****8810",
            ],
        ]
        self.assertEqual(r.rows, mask_result_rows)

    @patch("sql.utils.data_masking.GoInceptionEngine")
    def test_data_masking_hit_rules_star_and_column(self, _inception):
        """[*,column_a]"""
        _inception.return_value.query_data_masking.return_value = [
            {
                "index": 0,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            },
            {
                "index": 1,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            },
        ]
        sql = """select *,phone from users;"""
        rows = (
            (
                "18888888888",
                "18888888888",
            ),
            (
                "18888888889",
                "18888888889",
            ),
        )
        query_result = ReviewSet(
            column_list=["phone", "phone"], rows=rows, full_sql=sql
        )
        r = data_masking(self.ins, "archery", sql, query_result)
        print("test_data_masking_hit_rules_star_and_column", r.rows)
        mask_result_rows = [
            [
                "188****8888",
                "188****8888",
            ],
            [
                "188****8889",
                "188****8889",
            ],
        ]
        self.assertEqual(r.rows, mask_result_rows)

    @patch("sql.utils.data_masking.GoInceptionEngine")
    def test_data_masking_hit_rules_column_and_star(self, _inception):
        """[column_a, *]"""
        _inception.return_value.query_data_masking.return_value = [
            {
                "index": 0,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            },
            {
                "index": 1,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            },
        ]
        sql = """select phone,* from users;"""
        rows = (
            (
                "18888888888",
                "18888888888",
            ),
            (
                "18888888889",
                "18888888889",
            ),
        )
        query_result = ReviewSet(
            column_list=["phone", "phone"], rows=rows, full_sql=sql
        )
        r = data_masking(self.ins, "archery", sql, query_result)
        print("test_data_masking_hit_rules_column_and_star", r.rows)
        mask_result_rows = [
            [
                "188****8888",
                "188****8888",
            ],
            [
                "188****8889",
                "188****8889",
            ],
        ]
        self.assertEqual(r.rows, mask_result_rows)

    @patch("sql.utils.data_masking.GoInceptionEngine")
    def test_data_masking_hit_rules_column_and_star_and_column(self, _inception):
        """[column_a,a.*,column_b]"""
        _inception.return_value.query_data_masking.return_value = [
            {
                "index": 0,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            },
            {
                "index": 1,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            },
            {
                "index": 2,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            },
        ]
        sql = """select phone,*,phone from users;"""
        rows = (
            (
                "18888888888",
                "18888888888",
                "18888888888",
            ),
            (
                "18888888889",
                "18888888889",
                "18888888889",
            ),
        )
        query_result = ReviewSet(
            column_list=["phone", "phone", "phone"], rows=rows, full_sql=sql
        )
        r = data_masking(self.ins, "archery", sql, query_result)
        print("test_data_masking_hit_rules_column_and_star_and_column", r.rows)
        mask_result_rows = [
            [
                "188****8888",
                "188****8888",
                "188****8888",
            ],
            [
                "188****8889",
                "188****8889",
                "188****8889",
            ],
        ]
        self.assertEqual(r.rows, mask_result_rows)

    @patch("sql.utils.data_masking.GoInceptionEngine")
    def test_data_masking_hit_rules_star_and_column_and_star(self, _inception):
        """[a.*, column_a, b.*]"""
        _inception.return_value.query_data_masking.return_value = [
            {
                "index": 0,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            },
            {
                "index": 1,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            },
            {
                "index": 2,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            },
        ]
        sql = """select a.*,phone,a.* from users a;"""
        rows = (
            (
                "18888888888",
                "18888888888",
                "18888888888",
            ),
            (
                "18888888889",
                "18888888889",
                "18888888889",
            ),
        )
        query_result = ReviewSet(
            column_list=["phone", "phone", "phone"], rows=rows, full_sql=sql
        )
        r = data_masking(self.ins, "archery", sql, query_result)
        print("test_data_masking_hit_rules_star_and_column_and_star", r.rows)
        mask_result_rows = [
            [
                "188****8888",
                "188****8888",
                "188****8888",
            ],
            [
                "188****8889",
                "188****8889",
                "188****8889",
            ],
        ]
        self.assertEqual(r.rows, mask_result_rows)

    @patch("sql.utils.data_masking.GoInceptionEngine")
    def test_data_masking_concat_function_support(self, _inception):
        """concat_函数支持"""
        _inception.return_value.query_data_masking.return_value = [
            {
                "index": 0,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "concat(phone,1)",
            }
        ]
        sql = """select concat(phone,1) from users;"""
        rows = (("18888888888",), ("18888888889",), ("18888888810",))
        query_result = ReviewSet(
            column_list=["concat(phone,1)"], rows=rows, full_sql=sql
        )
        r = data_masking(self.ins, "archery", sql, query_result)
        mask_result_rows = [
            [
                "188****8888",
            ],
            [
                "188****8889",
            ],
            [
                "188****8810",
            ],
        ]
        print("test_data_masking_concat_function_support", r.rows)
        self.assertEqual(r.rows, mask_result_rows)

    @patch("sql.utils.data_masking.GoInceptionEngine")
    def test_data_masking_max_function_support(self, _inception):
        """max_函数支持"""
        _inception.return_value.query_data_masking.return_value = [
            {
                "index": 0,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "max(phone+1)",
            }
        ]
        sql = """select max(phone+1) from users;"""
        rows = (("18888888888",), ("18888888889",), ("18888888810",))
        query_result = ReviewSet(column_list=["max(phone+1)"], rows=rows, full_sql=sql)
        mask_result_rows = [
            [
                "188****8888",
            ],
            [
                "188****8889",
            ],
            [
                "188****8810",
            ],
        ]
        r = data_masking(self.ins, "archery", sql, query_result)
        print("test_data_masking_max_function_support", r.rows)
        self.assertEqual(r.rows, mask_result_rows)

    @patch("sql.utils.data_masking.GoInceptionEngine")
    def test_data_masking_union_support_keyword(self, _inception):
        """union关键字"""
        self.sys_config.set("query_check", "true")
        self.sys_config.get_all_config()
        _inception.return_value.query_data_masking.return_value = [
            {
                "index": 0,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            },
            {
                "index": 1,
                "field": "phone",
                "type": "varchar(80)",
                "table": "users",
                "schema": "archer_test",
                "alias": "phone",
            },
        ]
        sqls = [
            "select phone from users union select phone from users;",
            "select phone from users union all select phone from users;",
        ]
        rows = (("18888888888",), ("18888888889",), ("18888888810",))
        mask_result_rows = [
            [
                "188****8888",
            ],
            [
                "188****8889",
            ],
            [
                "188****8810",
            ],
        ]
        for sql in sqls:
            query_result = ReviewSet(column_list=["phone"], rows=rows, full_sql=sql)
            r = data_masking(self.ins, "archery", sql, query_result)
            print("test_data_masking_union_support_keyword", r.rows)
            self.assertEqual(r.rows, mask_result_rows)

    def test_brute_mask(self):
        sql = """select * from users;"""
        rows = (("18888888888",), ("18888888889",), ("18888888810",))
        query_result = ReviewSet(column_list=["phone"], rows=rows, full_sql=sql)
        r = brute_mask(self.ins, query_result)
        mask_result_rows = [("188****8888",), ("188****8889",), ("188****8810",)]
        self.assertEqual(r.rows, mask_result_rows)

    def test_simple_column_mask(self):
        sql = """select * from users;"""
        rows = (("18888888888",), ("18888888889",), ("18888888810",))
        query_result = ReviewSet(column_list=["phone"], rows=rows, full_sql=sql)
        r = simple_column_mask(self.ins, query_result)
        mask_result_rows = [("188****8888",), ("188****8889",), ("188****8810",)]
        self.assertEqual(r.rows, mask_result_rows)


class TestResourceGroup(TestCase):
    def setUp(self):
        self.sys_config = SysConfig()
        self.user = User.objects.create(
            username="test_user", display="中文显示", is_active=True
        )
        self.su = User.objects.create(
            username="s_user", display="中文显示", is_active=True, is_superuser=True
        )
        self.ins1 = Instance.objects.create(
            instance_name="some_ins1",
            type="slave",
            db_type="mysql",
            host="some_host",
            port=3306,
            user="ins_user",
            password="some_str",
        )
        self.ins2 = Instance.objects.create(
            instance_name="some_ins2",
            type="slave",
            db_type="mysql",
            host="some_host",
            port=3306,
            user="ins_user",
            password="some_str",
        )
        self.rgp1 = ResourceGroup.objects.create(group_name="group1")
        self.rgp2 = ResourceGroup.objects.create(group_name="group2")
        self.agp = Group.objects.create(name="auth_group")

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
        users = auth_group_users(
            auth_group_names=[self.agp.name], group_id=self.rgp1.group_id
        )
        self.assertIn(self.user, users)
