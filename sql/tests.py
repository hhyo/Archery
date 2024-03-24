import json
from datetime import timedelta, datetime
from unittest.mock import MagicMock, patch, ANY, Mock
from django.conf import settings
from django.db import connection
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, TransactionTestCase

from common.config import SysConfig
from common.utils.const import WorkflowStatus, WorkflowType
from sql.binlog import my2sql_file
from sql.engines.models import ResultSet
from sql.utils.execute_sql import execute_callback
from sql.query import kill_query_conn
from sql.models import (
    Users,
    Instance,
    QueryPrivilegesApply,
    QueryPrivileges,
    SqlWorkflow,
    SqlWorkflowContent,
    ResourceGroup,
    ParamTemplate,
    WorkflowAudit,
    QueryLog,
    WorkflowLog,
)
from sql.utils.workflow_audit import AuditException

User = Users


class PickableMock(Mock):
    def __reduce__(self):
        return (Mock, ())


class TestView(TransactionTestCase):
    """测试view视图"""

    def setUp(self):
        """
        准备用户和配置
        """
        self.sys_config = SysConfig()
        self.client = Client()
        self.superuser = User.objects.create(username="super", is_superuser=True)
        self.client.force_login(self.superuser)
        self.ins = Instance.objects.create(
            instance_name="some_ins",
            type="slave",
            db_type="mysql",
            host="some_host",
            port=3306,
            user="ins_user",
            password="some_str",
        )
        self.res_group = ResourceGroup.objects.create(
            group_id=1, group_name="group_name"
        )
        self.wf = SqlWorkflow.objects.create(
            workflow_name="some_name",
            group_id=1,
            group_name="g1",
            engineer_display="",
            audit_auth_groups="some_audit_group",
            status="workflow_finish",
            is_backup=True,
            instance=self.ins,
            db_name="some_db",
            syntax_type=1,
        )
        SqlWorkflowContent.objects.create(
            workflow=self.wf, sql_content="some_sql", execute_result=""
        )
        self.query_apply = QueryPrivilegesApply.objects.create(
            group_id=1,
            group_name="some_name",
            title="some_title1",
            user_name="some_user",
            instance=self.ins,
            db_list="some_db,some_db2",
            limit_num=100,
            valid_date="2020-01-1",
            priv_type=1,
            status=0,
            audit_auth_groups="some_audit_group",
        )
        self.audit = WorkflowAudit.objects.create(
            group_id=1,
            group_name="some_group",
            workflow_id=1,
            workflow_type=1,
            workflow_title="申请标题",
            workflow_remark="申请备注",
            audit_auth_groups="1,2,3",
            current_audit="1",
            next_audit="2",
            current_status=0,
        )
        self.wl = WorkflowLog.objects.create(
            audit_id=self.audit.audit_id, operation_type=1
        )
        # 慢查询建表
        with connection.cursor() as cursor:
            with open("src/init_sql/mysql_slow_query_review.sql") as fp:
                content = fp.read()
                cursor.execute(content)

    def tearDown(self):
        self.sys_config.purge()
        User.objects.all().delete()
        SqlWorkflow.objects.all().delete()
        SqlWorkflowContent.objects.all().delete()
        WorkflowAudit.objects.all().delete()
        WorkflowLog.objects.all().delete()
        QueryPrivilegesApply.objects.all().delete()
        ResourceGroup.objects.all().delete()
        with connection.cursor() as cursor:
            cursor.execute(
                "DROP table mysql_slow_query_review,mysql_slow_query_review_history"
            )

    def test_index(self):
        """测试index页面"""
        data = {}
        r = self.client.get("/index/", data=data)
        self.assertRedirects(r, f"/sqlworkflow/", fetch_redirect_response=False)

    def test_dashboard(self):
        """测试dashboard页面"""
        data = {}
        r = self.client.get("/dashboard/", data=data)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "SQL上线工单")

    def test_sqlworkflow(self):
        """测试sqlworkflow页面"""
        data = {}
        r = self.client.get("/sqlworkflow/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_submitsql(self):
        """测试submitsql页面"""
        data = {}
        r = self.client.get("/submitsql/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_rollback(self):
        """测试rollback页面"""
        data = {"workflow_id": self.wf.id}
        r = self.client.get("/rollback/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_sqlanalyze(self):
        """测试sqlanalyze页面"""
        data = {}
        r = self.client.get("/sqlanalyze/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_sqlquery(self):
        """测试sqlquery页面"""
        data = {}
        r = self.client.get("/sqlquery/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_queryapplylist(self):
        """测试queryapplylist页面"""
        data = {}
        r = self.client.get("/queryapplylist/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_queryuserprivileges(self):
        """测试queryuserprivileges页面"""
        data = {}
        r = self.client.get(f"/queryuserprivileges/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_sqladvisor(self):
        """测试sqladvisor页面"""
        data = {}
        r = self.client.get(f"/sqladvisor/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_slowquery(self):
        """测试slowquery页面"""
        data = {}
        r = self.client.get(f"/slowquery/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_instance(self):
        """测试instance页面"""
        data = {}
        r = self.client.get(f"/instance/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_instanceaccount(self):
        """测试instanceaccount页面"""
        data = {}
        r = self.client.get(f"/instanceaccount/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_database(self):
        """测试database页面"""
        data = {}
        r = self.client.get(f"/database/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_dbdiagnostic(self):
        """测试dbdiagnostic页面"""
        data = {}
        r = self.client.get(f"/dbdiagnostic/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_instanceparam(self):
        """测试instance_param页面"""
        data = {}
        r = self.client.get(f"/instanceparam/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_my2sql(self):
        """测试my2sql页面"""
        data = {}
        r = self.client.get(f"/my2sql/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_schemasync(self):
        """测试schemasync页面"""
        data = {}
        r = self.client.get(f"/schemasync/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_archive(self):
        """测试archive页面"""
        data = {}
        r = self.client.get(f"/archive/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_config(self):
        """测试config页面"""
        data = {}
        r = self.client.get(f"/config/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_group(self):
        """测试group页面"""
        data = {}
        r = self.client.get(f"/group/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_audit(self):
        """测试audit页面"""
        data = {}
        r = self.client.get(f"/audit/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_audit_sqlquery(self):
        """测试audit_sqlquery页面"""
        data = {}
        r = self.client.get(f"/audit_sqlquery/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_audit_sqlworkflow(self):
        """测试audit_sqlworkflow页面"""
        data = {}
        r = self.client.get(f"/audit_sqlworkflow/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_groupmgmt(self):
        """测试groupmgmt页面"""
        data = {}
        r = self.client.get(f"/grouprelations/{self.res_group.group_id}/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_workflows(self):
        """测试workflows页面"""
        data = {}
        r = self.client.get(f"/workflow/", data=data)
        self.assertEqual(r.status_code, 200)

    def test_workflowsdetail(self):
        """测试workflows页面"""
        data = {}
        r = self.client.get(f"/workflow/{self.audit.audit_id}/", data=data)
        self.assertRedirects(r, f"/queryapplydetail/1/", fetch_redirect_response=False)

    def test_dbaprinciples(self):
        """测试workflows页面"""
        data = {}
        r = self.client.get(f"/dbaprinciples/", data=data)
        self.assertEqual(r.status_code, 200)


class TestSignUp(TestCase):
    """注册测试"""

    def setUp(self):
        """
        创建默认组给注册关联用户, 打开注册
        """
        archer_config = SysConfig()
        archer_config.set("sign_up_enabled", "true")
        archer_config.get_all_config()
        self.client = Client()
        Group.objects.create(id=1, name="默认组")

    def tearDown(self):
        SysConfig().purge()
        Group.objects.all().delete()
        User.objects.all().delete()

    def test_sing_up_not_username(self):
        """
        用户名不能为空
        """
        response = self.client.post("/signup/", data={})
        data = json.loads(response.content)
        content = {"status": 1, "msg": "用户名和密码不能为空", "data": None}
        self.assertEqual(data, content)

    def test_sing_up_not_password(self):
        """
        密码不能为空
        """
        response = self.client.post("/signup/", data={"username": "test"})
        data = json.loads(response.content)
        content = {"status": 1, "msg": "用户名和密码不能为空", "data": None}
        self.assertEqual(data, content)

    def test_sing_up_not_display(self):
        """
        中文名不能为空
        """
        response = self.client.post(
            "/signup/",
            data={
                "username": "test",
                "password": "123456test",
                "password2": "123456test",
                "display": "",
                "email": "123@123.com",
            },
        )
        data = json.loads(response.content)
        content = {"status": 1, "msg": "请填写中文名", "data": None}
        self.assertEqual(data, content)

    def test_sing_up_2password(self):
        """
        两次输入密码不一致
        """
        response = self.client.post(
            "/signup/",
            data={"username": "test", "password": "123456", "password2": "12345"},
        )
        data = json.loads(response.content)
        content = {"status": 1, "msg": "两次输入密码不一致", "data": None}
        self.assertEqual(data, content)

    def test_sing_up_duplicate_uesrname(self):
        """
        用户名已存在
        """
        User.objects.create(username="test", password="123456")
        response = self.client.post(
            "/signup/",
            data={"username": "test", "password": "123456", "password2": "123456"},
        )
        data = json.loads(response.content)
        content = {"status": 1, "msg": "用户名已存在", "data": None}
        self.assertEqual(data, content)

    def test_sing_up_invalid(self):
        """
        密码无效
        """
        self.client.post(
            "/signup/",
            data={
                "username": "test",
                "password": "123456",
                "password2": "123456test",
                "display": "test",
                "email": "123@123.com",
            },
        )
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(username="test")

    @patch("common.auth.init_user")
    def test_sing_up_valid(self, mock_init):
        """
        正常注册
        """
        self.client.post(
            "/signup/",
            data={
                "username": "test",
                "password": "123456test",
                "password2": "123456test",
                "display": "test",
                "email": "123@123.com",
            },
        )
        user = User.objects.get(username="test")
        self.assertTrue(user)
        # 注册后登录
        r = self.client.post(
            "/authenticate/",
            data={"username": "test", "password": "123456test"},
            follow=False,
        )
        r_json = r.json()
        self.assertEqual(0, r_json["status"])
        # 只允许初始化用户一次
        mock_init.assert_called_once()


class TestUser(TestCase):
    def setUp(self):
        self.u1 = User(username="test_user", display="中文显示", is_active=True)
        self.u1.set_password("test_password")
        self.u1.save()

    def tearDown(self):
        self.u1.delete()

    @patch("common.auth.init_user")
    def testLogin(self, mock_init):
        """login 页面测试"""
        r = self.client.get("/login/")
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "login.html")
        r = self.client.post(
            "/authenticate/",
            data={"username": "test_user", "password": "test_password"},
        )
        r_json = r.json()
        self.assertEqual(0, r_json["status"])
        # 登录后直接跳首页
        r = self.client.get("/login/", follow=True)
        self.assertRedirects(r, "/sqlworkflow/")
        # init 只调用一次
        mock_init.assert_called_once()

    def test_out_ranged_failed_login_count(self):
        # 正常保存
        self.u1.failed_login_count = 64
        self.u1.save()
        self.u1.refresh_from_db()
        self.assertEqual(64, self.u1.failed_login_count)
        # 超过127视为127
        self.u1.failed_login_count = 256
        self.u1.save()
        self.u1.refresh_from_db()
        self.assertEqual(127, self.u1.failed_login_count)
        # 小于0视为0
        self.u1.failed_login_count = -1
        self.u1.save()
        self.u1.refresh_from_db()
        self.assertEqual(0, self.u1.failed_login_count)


class TestQuery(TransactionTestCase):
    def setUp(self):
        self.slave1 = Instance(
            instance_name="test_slave_instance",
            type="slave",
            db_type="mysql",
            host="testhost",
            port=3306,
            user="mysql_user",
            password="mysql_password",
        )
        self.slave2 = Instance(
            instance_name="test_instance_non_mysql",
            type="slave",
            db_type="mssql",
            host="some_host2",
            port=3306,
            user="some_user",
            password="some_str",
        )
        self.slave1.save()
        self.slave2.save()
        self.superuser1 = User.objects.create(username="super1", is_superuser=True)
        self.u1 = User.objects.create(
            username="test_user", display="中文显示", is_active=True
        )
        self.u2 = User.objects.create(
            username="test_user2", display="中文显示", is_active=True
        )
        self.query_log = QueryLog.objects.create(
            instance_name=self.slave1.instance_name,
            db_name="some_db",
            sqllog="select 1;",
            effect_row=10,
            cost_time=1,
            username=self.superuser1.username,
        )
        sql_query_perm = Permission.objects.get(codename="query_submit")
        self.u2.user_permissions.add(sql_query_perm)

    def tearDown(self):
        QueryPrivileges.objects.all().delete()
        QueryLog.objects.all().delete()
        self.u1.delete()
        self.u2.delete()
        self.superuser1.delete()
        self.slave1.delete()
        self.slave2.delete()
        archer_config = SysConfig()
        archer_config.set("disable_star", False)

    @patch("sql.query.user_instances")
    @patch("sql.query.get_engine")
    @patch("sql.query.query_priv_check")
    def testCorrectSQL(self, _priv_check, _get_engine, _user_instances):
        c = Client()
        some_sql = "select some from some_table limit 100;"
        some_db = "some_db"
        some_limit = 100
        c.force_login(self.u1)
        r = c.post(
            "/query/",
            data={
                "instance_name": self.slave1.instance_name,
                "sql_content": some_sql,
                "db_name": some_db,
                "limit_num": some_limit,
            },
        )
        self.assertEqual(r.status_code, 403)
        c.force_login(self.u2)
        q_result = ResultSet(full_sql=some_sql, rows=["value"])
        q_result.column_list = ["some"]
        _get_engine.return_value.query_check.return_value = {
            "msg": "",
            "bad_query": False,
            "filtered_sql": some_sql,
            "has_star": False,
        }
        _get_engine.return_value.filter_sql.return_value = some_sql
        _get_engine.return_value.query.return_value = q_result
        _get_engine.return_value.seconds_behind_master = 100
        _priv_check.return_value = {
            "status": 0,
            "data": {"limit_num": 100, "priv_check": True},
        }
        _user_instances.return_value.get.return_value = self.slave1
        r = c.post(
            "/query/",
            data={
                "instance_name": self.slave1.instance_name,
                "sql_content": some_sql,
                "db_name": some_db,
                "limit_num": some_limit,
            },
        )
        _get_engine.return_value.query.assert_called_once_with(
            some_db,
            some_sql,
            some_limit,
            schema_name=None,
            tb_name=None,
            max_execution_time=60000,
        )
        r_json = r.json()
        self.assertEqual(r_json["data"]["rows"], ["value"])
        self.assertEqual(r_json["data"]["column_list"], ["some"])
        self.assertEqual(r_json["data"]["seconds_behind_master"], 100)

    @patch("sql.query.user_instances")
    @patch("sql.query.get_engine")
    @patch("sql.query.query_priv_check")
    def testSQLWithoutLimit(self, _priv_check, _get_engine, _user_instances):
        c = Client()
        some_limit = 100
        sql_without_limit = "select some from some_table"
        sql_with_limit = "select some from some_table limit {0};".format(some_limit)
        some_db = "some_db"
        c.force_login(self.u2)
        q_result = ResultSet(full_sql=sql_without_limit, rows=["value"])
        q_result.column_list = ["some"]
        _get_engine.return_value.query_check.return_value = {
            "msg": "",
            "bad_query": False,
            "filtered_sql": sql_without_limit,
            "has_star": False,
        }
        _get_engine.return_value.filter_sql.return_value = sql_with_limit
        _get_engine.return_value.query.return_value = q_result
        _priv_check.return_value = {
            "status": 0,
            "data": {"limit_num": 100, "priv_check": True},
        }
        _user_instances.return_value.get.return_value = self.slave1
        r = c.post(
            "/query/",
            data={
                "instance_name": self.slave1.instance_name,
                "sql_content": sql_without_limit,
                "db_name": some_db,
                "limit_num": some_limit,
            },
        )
        _get_engine.return_value.query.assert_called_once_with(
            some_db,
            sql_with_limit,
            some_limit,
            schema_name=None,
            tb_name=None,
            max_execution_time=60000,
        )
        r_json = r.json()
        self.assertEqual(r_json["data"]["rows"], ["value"])
        self.assertEqual(r_json["data"]["column_list"], ["some"])

    @patch("sql.query.query_priv_check")
    def testStarOptionOn(self, _priv_check):
        c = Client()
        c.force_login(self.u2)
        some_limit = 100
        sql_with_star = "select * from some_table"
        some_db = "some_db"
        _priv_check.return_value = {
            "status": 0,
            "data": {"limit_num": 100, "priv_check": True},
        }
        archer_config = SysConfig()
        archer_config.set("disable_star", True)
        r = c.post(
            "/query/",
            data={
                "instance_name": self.slave1.instance_name,
                "sql_content": sql_with_star,
                "db_name": some_db,
                "limit_num": some_limit,
            },
        )
        archer_config.set("disable_star", False)
        r_json = r.json()
        self.assertEqual(1, r_json["status"])

    @patch("sql.query.get_engine")
    def test_kill_query_conn(self, _get_engine):
        kill_query_conn(self.slave1.id, 10)
        _get_engine.return_value.kill_connection.return_value = ResultSet()

    def test_query_log(self):
        """测试获取查询历史"""
        c = Client()
        c.force_login(self.superuser1)
        QueryLog(id=self.query_log.id, favorite=True, alias="test_a").save(
            update_fields=["favorite", "alias"]
        )
        data = {
            "star": "true",
            "query_log_id": self.query_log.id,
            "limit": 14,
            "offset": 0,
        }
        r = c.get("/query/querylog/", data=data)
        self.assertEqual(r.json()["total"], 1)

    def test_star(self):
        """测试查询语句收藏"""
        c = Client()
        c.force_login(self.superuser1)
        r = c.post(
            "/query/favorite/",
            data={
                "query_log_id": self.query_log.id,
                "star": "true",
                "alias": "test_alias",
            },
        )
        query_log = QueryLog.objects.get(id=self.query_log.id)
        self.assertTrue(query_log.favorite)
        self.assertEqual(query_log.alias, "test_alias")

    def test_un_star(self):
        """测试查询语句取消收藏"""
        c = Client()
        c.force_login(self.superuser1)
        r = c.post(
            "/query/favorite/",
            data={"query_log_id": self.query_log.id, "star": "false", "alias": ""},
        )
        r_json = r.json()
        query_log = QueryLog.objects.get(id=self.query_log.id)
        self.assertFalse(query_log.favorite)
        self.assertEqual(query_log.alias, "")


class TestWorkflowView(TransactionTestCase):
    def setUp(self):
        self.now = datetime.now()
        can_view_permission = Permission.objects.get(codename="menu_sqlworkflow")
        can_execute_permission = Permission.objects.get(codename="sql_execute")
        can_execute_resource_permission = Permission.objects.get(
            codename="sql_execute_for_resource_group"
        )
        self.u1 = User(username="some_user", display="用户1")
        self.u1.save()
        self.u1.user_permissions.add(can_view_permission)
        self.u2 = User(username="some_user2", display="用户2")
        self.u2.save()
        self.u2.user_permissions.add(can_view_permission)
        self.u3 = User(username="some_user3", display="用户3")
        self.u3.save()
        self.u3.user_permissions.add(can_view_permission)
        self.executor1 = User(username="some_executor", display="执行者")
        self.executor1.save()
        self.executor1.user_permissions.add(
            can_view_permission, can_execute_permission, can_execute_resource_permission
        )
        self.superuser1 = User(username="super1", is_superuser=True)
        self.superuser1.save()
        self.master1 = Instance(
            instance_name="test_master_instance",
            type="master",
            db_type="mysql",
            host="testhost",
            port=3306,
            user="mysql_user",
            password="mysql_password",
        )
        self.master1.save()
        self.wf1 = SqlWorkflow.objects.create(
            workflow_name="some_name",
            group_id=1,
            group_name="g1",
            engineer=self.u1.username,
            engineer_display=self.u1.display,
            audit_auth_groups="some_group",
            create_time=self.now - timedelta(days=1),
            status="workflow_finish",
            is_backup=True,
            instance=self.master1,
            db_name="some_db",
            syntax_type=1,
        )
        self.wfc1 = SqlWorkflowContent.objects.create(
            workflow=self.wf1,
            sql_content="some_sql",
            execute_result=json.dumps([{"id": 1, "sql": "some_content"}]),
        )
        self.wf2 = SqlWorkflow.objects.create(
            workflow_name="some_name2",
            group_id=1,
            group_name="g1",
            engineer=self.u2.username,
            engineer_display=self.u2.display,
            audit_auth_groups="some_group",
            create_time=self.now - timedelta(days=1),
            status="workflow_manreviewing",
            is_backup=True,
            instance=self.master1,
            db_name="some_db",
            syntax_type=1,
        )
        self.audit_flow = WorkflowAudit.objects.create(
            group_id=1,
            group_name="g1",
            workflow_id=self.wf2.id,
            workflow_type=WorkflowType.SQL_REVIEW,
            workflow_title="123",
            audit_auth_groups="123",
            current_audit="",
            next_audit="",
            current_status=WorkflowStatus.WAITING,
            create_user="",
            create_user_display="",
        )
        self.wfc2 = SqlWorkflowContent.objects.create(
            workflow=self.wf2,
            sql_content="some_sql",
            execute_result=json.dumps([{"id": 1, "sql": "some_content"}]),
        )
        self.resource_group1 = ResourceGroup(group_name="some_group")
        self.resource_group1.save()

    def tearDown(self):
        SqlWorkflowContent.objects.all().delete()
        SqlWorkflow.objects.all().delete()
        self.master1.delete()
        self.u1.delete()
        self.superuser1.delete()
        self.resource_group1.delete()
        SysConfig().purge()

    def testWorkflowStatus(self):
        """测试获取工单状态"""
        c = Client(header={})
        c.force_login(self.u1)
        r = c.post("/getWorkflowStatus/", {"workflow_id": self.wf1.id})
        r_json = r.json()
        self.assertEqual(r_json["status"], "workflow_finish")

    @patch("sql.utils.workflow_audit.Audit.can_review")
    def test_alter_run_date_no_perm(self, _can_review):
        """测试修改可执行时间，无权限"""
        sql_review = Permission.objects.get(codename="sql_review")
        self.u1.user_permissions.add(sql_review)
        _can_review.return_value = False
        c = Client()
        c.force_login(self.u1)
        data = {"workflow_id": self.wf1.id}
        r = c.post("/alter_run_date/", data=data)
        self.assertContains(r, "你无权操作当前工单")

    @patch("sql.utils.workflow_audit.Audit.can_review")
    def test_alter_run_date(self, _can_review):
        """测试修改可执行时间，有权限"""
        sql_review = Permission.objects.get(codename="sql_review")
        self.u1.user_permissions.add(sql_review)
        _can_review.return_value = True
        c = Client()
        c.force_login(self.u1)
        data = {"workflow_id": self.wf1.id}
        r = c.post("/alter_run_date/", data=data)
        self.assertRedirects(
            r, f"/detail/{self.wf1.id}/", fetch_redirect_response=False
        )

    def testWorkflowListView(self):
        """测试工单列表"""
        c = Client()
        c.force_login(self.superuser1)
        r = c.post("/sqlworkflow_list/", {"limit": 10, "offset": 0, "navStatus": ""})
        r_json = r.json()
        self.assertEqual(r_json["total"], 2)
        # 列表按创建时间倒序排列, 第二个是wf1 , 是已正常结束
        self.assertEqual(r_json["rows"][1]["status"], "workflow_finish")

        # u1拿到u1的
        c.force_login(self.u1)
        r = c.post("/sqlworkflow_list/", {"limit": 10, "offset": 0, "navStatus": ""})
        r_json = r.json()
        self.assertEqual(r_json["total"], 1)
        self.assertEqual(r_json["rows"][0]["id"], self.wf1.id)

        # u3拿到None
        c.force_login(self.u3)
        r = c.post("/sqlworkflow_list/", {"limit": 10, "offset": 0, "navStatus": ""})
        r_json = r.json()
        self.assertEqual(r_json["total"], 0)

    def testWorkflowListViewFilter(self):
        """测试工单列表筛选"""
        c = Client()
        c.force_login(self.superuser1)
        # 工单状态
        r = c.post(
            "/sqlworkflow_list/",
            {"limit": 10, "offset": 0, "navStatus": "workflow_finish"},
        )
        r_json = r.json()
        self.assertEqual(r_json["total"], 1)
        # 列表按创建时间倒序排列
        self.assertEqual(r_json["rows"][0]["status"], "workflow_finish")

        # 实例
        r = c.post(
            "/sqlworkflow_list/",
            {"limit": 10, "offset": 0, "instance_id": self.wf1.instance_id},
        )
        r_json = r.json()
        self.assertEqual(r_json["total"], 2)
        # 列表按创建时间倒序排列, 第二个是wf1
        self.assertEqual(r_json["rows"][1]["workflow_name"], self.wf1.workflow_name)

        # 资源组
        r = c.post(
            "/sqlworkflow_list/",
            {"limit": 10, "offset": 0, "resource_group_id": self.wf1.group_id},
        )
        r_json = r.json()
        self.assertEqual(r_json["total"], 2)
        # 列表按创建时间倒序排列, 第二个是wf1
        self.assertEqual(r_json["rows"][1]["workflow_name"], self.wf1.workflow_name)

        # 时间
        start_date = datetime.strftime(self.now, "%Y-%m-%d")
        end_date = datetime.strftime(self.now, "%Y-%m-%d")
        r = c.post(
            "/sqlworkflow_list/",
            {"limit": 10, "offset": 0, "start_date": start_date, "end_date": end_date},
        )
        r_json = r.json()
        self.assertEqual(r_json["total"], 2)

    @patch("sql.notify.auto_notify")
    @patch("sql.utils.workflow_audit.AuditV2.operate")
    def testWorkflowPassedView(self, mock_operate, _):
        """测试审核工单"""
        c = Client()
        c.force_login(self.superuser1)
        r = c.post("/passed/")
        self.assertContains(r, "workflow_id参数为空.")
        mock_operate.side_effect = AuditException("mock audit failed")
        r = c.post("/passed/", {"workflow_id": self.wf2.id})
        self.assertContains(r, "mock audit failed")
        mock_operate.reset_mock(side_effect=True)
        mock_operate.return_value = None
        # 因为 operate 被 mock 了, 为了测试审批流通过, 这里把审批流手动设置为通过, 仅 测试 view 层的逻辑
        # audit operate 的测试由其他测试覆盖
        self.audit_flow.current_status = WorkflowStatus.PASSED
        self.audit_flow.save()
        r = c.post(
            "/passed/",
            data={"workflow_id": self.wf2.id, "audit_remark": "some_audit"},
            follow=False,
        )
        self.assertRedirects(
            r, "/detail/{}/".format(self.wf2.id), fetch_redirect_response=False
        )
        self.wf2.refresh_from_db()
        self.assertEqual(self.wf2.status, "workflow_review_pass")

    @patch("sql.sql_workflow.notify_for_execute")
    @patch("sql.sql_workflow.Audit.add_log")
    @patch("sql.sql_workflow.Audit.detail_by_workflow_id")
    @patch("sql.sql_workflow.can_execute")
    def test_workflow_execute(self, mock_can_excute, _, _1, _2):
        """测试工单执行"""
        c = Client()
        c.force_login(self.executor1)
        r = c.post("/execute/")
        self.assertContains(r, "workflow_id参数为空.")
        mock_can_excute.return_value = False
        r = c.post("/execute/", data={"workflow_id": self.wf2.id})
        self.assertContains(r, "你无权操作当前工单！")
        mock_can_excute.return_value = True
        r = c.post("/execute/", data={"workflow_id": self.wf2.id, "mode": "manual"})
        self.wf2.refresh_from_db()
        self.assertEqual("workflow_finish", self.wf2.status)

    @patch("sql.sql_workflow.Audit.add_log")
    @patch("sql.notify.auto_notify")
    @patch("sql.utils.workflow_audit.AuditV2.operate")
    # patch view里的can_cancel 而不是原始位置的can_cancel ,因为在调用时, 已经 import 了真的 can_cancel ,会导致mock失效
    # 在import 静态函数时需要注意这一点, 动态对象因为每次都会重新生成,也可以 mock 原函数/方法/对象
    # 参见 : https://docs.python.org/3/library/unittest.mock.html#where-to-patch
    @patch("sql.sql_workflow.can_cancel")
    def testWorkflowCancelView(
        self, _can_cancel, mock_audit_operate, mock_notify, _add_log
    ):
        """测试工单驳回、取消"""
        c = Client()
        c.force_login(self.u2)
        r = c.post("/cancel/")
        self.assertContains(r, "workflow_id参数为空.")
        r = c.post("/cancel/", data={"workflow_id": self.wf2.id})
        self.assertContains(r, "终止原因不能为空")
        _can_cancel.return_value = False
        mock_audit_operate.return_value = None
        r = c.post(
            "/cancel/",
            data={"workflow_id": self.wf2.id, "cancel_remark": "some_reason"},
        )
        self.assertContains(r, "你无权操作当前工单！")
        _can_cancel.return_value = True
        _detail_by_id = 123
        c.post(
            "/cancel/",
            data={"workflow_id": self.wf2.id, "cancel_remark": "some_reason"},
        )
        self.wf2.refresh_from_db()
        self.assertEqual("workflow_abort", self.wf2.status)

    @patch("sql.sql_workflow.get_engine")
    def test_osc_control(self, _get_engine):
        """测试MySQL工单osc控制"""
        c = Client()
        c.force_login(self.superuser1)
        request_data = {
            "workflow_id": self.wf1.id,
            "sqlsha1": "sqlsha1",
            "command": "get",
        }
        _get_engine.return_value.osc_control.return_value = ResultSet()
        r = c.post("/inception/osc_control/", data=request_data, follow=False)
        self.assertDictEqual(
            json.loads(r.content), {"total": 0, "rows": [], "msg": None}
        )

    @patch("sql.sql_workflow.get_engine")
    def test_osc_control_exception(self, _get_engine):
        """测试MySQL工单OSC控制异常"""
        c = Client()
        c.force_login(self.superuser1)
        request_data = {
            "workflow_id": self.wf1.id,
            "sqlsha1": "sqlsha1",
            "command": "get",
        }
        _get_engine.return_value.osc_control.side_effect = RuntimeError("RuntimeError")
        r = c.post("/inception/osc_control/", data=request_data, follow=False)
        self.assertDictEqual(
            json.loads(r.content), {"total": 0, "rows": [], "msg": "RuntimeError"}
        )


class TestOptimize(TestCase):
    """
    测试SQL优化
    """

    def setUp(self):
        self.superuser = User(username="super", is_superuser=True)
        self.superuser.save()
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
        self.client.force_login(self.superuser)

    def tearDown(self):
        self.superuser.delete()
        self.master.delete()
        self.sys_config.replace(json.dumps({}))

    @patch("sql.plugins.plugin.subprocess")
    def test_sqladvisor(self, _subprocess):
        """
        测试SQLAdvisor报告
        :return:
        """
        _subprocess.Popen.return_value.communicate.return_value = (
            "some_stdout",
            "some_stderr",
        )
        r = self.client.post(path="/slowquery/optimize_sqladvisor/")
        self.assertEqual(
            json.loads(r.content),
            {"status": 1, "msg": "页面提交参数可能为空", "data": []},
        )
        r = self.client.post(
            path="/slowquery/optimize_sqladvisor/",
            data={"sql_content": "select 1;", "instance_name": "test_instance"},
        )
        self.assertEqual(
            json.loads(r.content),
            {"status": 1, "msg": "请配置SQLAdvisor路径！", "data": []},
        )
        self.sys_config.set("sqladvisor", "/opt/archery/src/plugins/sqladvisor")
        self.sys_config.get_all_config()
        r = self.client.post(
            path="/slowquery/optimize_sqladvisor/",
            data={"sql_content": "select 1;", "instance_name": "test_instance"},
        )
        self.assertEqual(json.loads(r.content)["status"], 0)

        # test db_name
        r = self.client.post(
            path="/slowquery/optimize_sqladvisor/",
            data={
                "sql_content": "select 1;",
                "instance_name": "test_instance",
                "db_name": "--help",
            },
        )
        self.assertEqual(json.loads(r.content)["status"], 1)
        r = self.client.post(
            path="/slowquery/optimize_sqladvisor/",
            data={
                "sql_content": "select 1;",
                "instance_name": "test_instance",
                "db_name": ";drop table",
            },
        )
        self.assertEqual(json.loads(r.content)["status"], 1)

    @patch("sql.plugins.plugin.subprocess")
    def test_soar(self, _subprocess):
        """
        测试SOAR报告
        :return:
        """
        _subprocess.Popen.return_value.communicate.return_value = (
            "some_stdout",
            "some_stderr",
        )
        r = self.client.post(path="/slowquery/optimize_soar/")
        self.assertEqual(
            json.loads(r.content),
            {"status": 1, "msg": "页面提交参数可能为空", "data": []},
        )
        r = self.client.post(
            path="/slowquery/optimize_soar/",
            data={
                "sql": "select 1;",
                "instance_name": "test_instance",
                "db_name": "mysql",
            },
        )
        self.assertEqual(
            json.loads(r.content),
            {"status": 1, "msg": "请配置soar_path和test_dsn！", "data": []},
        )
        self.sys_config.set("soar", "/opt/archery/src/plugins/soar")
        self.sys_config.set("soar_test_dsn", "root:@127.0.0.1:3306/information_schema")
        self.sys_config.get_all_config()
        r = self.client.post(
            path="/slowquery/optimize_soar/",
            data={
                "sql": "select 1;",
                "instance_name": "test_instance",
                "db_name": "mysql",
            },
        )
        self.assertEqual(json.loads(r.content)["status"], 0)

    def test_tuning(self):
        """
        测试SQLTuning报告
        :return:
        """
        data = {
            "sql_content": "select * from test_archery.sql_users;",
            "instance_name": "test_instance",
            "db_name": settings.DATABASES["default"]["TEST"]["NAME"],
        }
        data["instance_name"] = "test_instancex"
        r = self.client.post(path="/slowquery/optimize_sqltuning/", data=data)
        self.assertEqual(
            json.loads(r.content),
            {"status": 1, "msg": "你所在组未关联该实例！", "data": []},
        )

        # 获取sys_parm
        data["instance_name"] = "test_instance"
        data["option[]"] = "sys_parm"
        r = self.client.post(path="/slowquery/optimize_sqltuning/", data=data)
        self.assertListEqual(
            list(json.loads(r.content)["data"].keys()),
            ["basic_information", "sys_parameter", "optimizer_switch", "sqltext"],
        )

        # 获取sql_plan
        data["option[]"] = "sql_plan"
        r = self.client.post(path="/slowquery/optimize_sqltuning/", data=data)
        self.assertListEqual(
            list(json.loads(r.content)["data"].keys()),
            ["optimizer_rewrite_sql", "plan", "sqltext"],
        )

        # 获取obj_stat
        data["option[]"] = "obj_stat"
        r = self.client.post(path="/slowquery/optimize_sqltuning/", data=data)
        self.assertListEqual(
            list(json.loads(r.content)["data"].keys()), ["object_statistics", "sqltext"]
        )

        # 获取sql_profile
        data["option[]"] = "sql_profile"
        r = self.client.post(path="/slowquery/optimize_sqltuning/", data=data)
        self.assertListEqual(
            list(json.loads(r.content)["data"].keys()), ["session_status", "sqltext"]
        )


class TestSchemaSync(TestCase):
    """
    测试SchemaSync
    """

    def setUp(self):
        self.superuser = User(username="super", is_superuser=True)
        self.superuser.save()
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
        data = {
            "instance_name": "test_instance",
            "db_name": "test",
            "target_instance_name": "test_instance",
            "target_db_name": "test",
            "sync_auto_inc": True,
            "sync_comments": False,
        }
        r = self.client.post(path="/instance/schemasync/", data=data)
        self.assertEqual(json.loads(r.content)["status"], 0)


class TestAsync(TestCase):
    def setUp(self):
        self.now = datetime.now()
        self.u1 = User(username="some_user", display="用户1")
        self.u1.save()
        self.master1 = Instance(
            instance_name="test_master_instance",
            type="master",
            db_type="mysql",
            host="testhost",
            port=3306,
            user="mysql_user",
            password="mysql_password",
        )
        self.master1.save()
        self.wf1 = SqlWorkflow.objects.create(
            workflow_name="some_name2",
            group_id=1,
            group_name="g1",
            engineer=self.u1.username,
            engineer_display=self.u1.display,
            audit_auth_groups="some_group",
            create_time=self.now - timedelta(days=1),
            status="workflow_executing",
            is_backup=True,
            instance=self.master1,
            db_name="some_db",
            syntax_type=1,
        )
        self.wfc1 = SqlWorkflowContent.objects.create(
            workflow=self.wf1, sql_content="some_sql", execute_result=""
        )
        # 初始化工单执行返回对象
        self.task_result = MagicMock()
        self.task_result.args = [self.wf1.id]
        self.task_result.success = True
        self.task_result.stopped = self.now
        self.task_result.result.json.return_value = json.dumps(
            [{"id": 1, "sql": "some_content"}]
        )
        self.task_result.result.warning = ""
        self.task_result.result.error = ""

    def tearDown(self):
        self.wf1.delete()
        self.u1.delete()
        self.task_result = None
        self.master1.delete()

    @patch("sql.utils.execute_sql.notify_for_execute")
    @patch("sql.utils.execute_sql.Audit")
    def test_call_back(self, mock_audit, mock_notify):
        mock_audit.detail_by_workflow_id.return_value.audit_id = 123
        mock_audit.add_log.return_value = "any thing"
        execute_callback(self.task_result)
        mock_audit.detail_by_workflow_id.assert_called_with(
            workflow_id=self.wf1.id, workflow_type=ANY
        )
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
        self.superuser = User(username="super", is_superuser=True)
        self.superuser.save()
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
        self.sys_config.set("soar", "/opt/archery/src/plugins/soar")
        r = self.client.post(path="/sql_analyze/generate/", data={})
        self.assertEqual(json.loads(r.content), {"rows": [], "total": 0})

    def test_generate_text_not_None(self):
        """
        测试解析SQL，text不为空
        :return:
        """
        self.sys_config.set("soar", "/opt/archery/src/plugins/soar")
        text = "select * from sql_user;select * from sql_workflow;"
        r = self.client.post(path="/sql_analyze/generate/", data={"text": text})
        self.assertEqual(
            json.loads(r.content),
            {
                "total": 2,
                "rows": [
                    {"sql_id": 1, "sql": "select * from sql_user;"},
                    {"sql_id": 2, "sql": "select * from sql_workflow;"},
                ],
            },
        )

    def test_analyze_text_None(self):
        """
        测试分析SQL，text为空
        :return:
        """
        r = self.client.post(path="/sql_analyze/analyze/", data={})
        self.assertEqual(json.loads(r.content), {"rows": [], "total": 0})

    @patch("sql.plugins.plugin.subprocess")
    def test_analyze_text_not_None(self, _subprocess):
        """
        测试分析SQL，text不为空
        :return:
        """
        _subprocess.Popen.return_value.communicate.return_value = (
            "some_stdout",
            "some_stderr",
        )
        self.sys_config.set("soar", "/opt/archery/src/plugins/soar")
        text = "select * from sql_user;select * from sql_workflow;"
        instance_name = self.master.instance_name
        db_name = settings.DATABASES["default"]["TEST"]["NAME"]
        r = self.client.post(
            path="/sql_analyze/analyze/",
            data={"text": text, "instance_name": instance_name, "db_name": db_name},
        )
        self.assertListEqual(
            list(json.loads(r.content)["rows"][0].keys()), ["sql_id", "sql", "report"]
        )

    @patch("sql.sql_analyze.Path")
    @patch("sql.plugins.plugin.subprocess")
    def test_analyze_text_evil(self, _subprocess, mock_path):
        """
        测试分析SQL，text不为空
        :return:
        """
        _subprocess.Popen.return_value.communicate.return_value = (
            "some_stdout",
            "some_stderr",
        )
        mock_path.return_value.exists.return_value = True
        self.sys_config.set("soar", "/opt/archery/src/plugins/soar")
        text = "/etc/passwd"
        instance_name = self.master.instance_name
        db_name = settings.DATABASES["default"]["TEST"]["NAME"]
        r = self.client.post(
            path="/sql_analyze/analyze/",
            data={"text": text, "instance_name": instance_name, "db_name": db_name},
        )
        self.assertEqual(r.json()["msg"], "SQL 语句不合法")


class TestBinLog(TestCase):
    """
    测试Binlog相关
    """

    def setUp(self):
        self.superuser = User(username="super", is_superuser=True)
        self.superuser.save()
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
        self.client.force_login(self.superuser)

    def tearDown(self):
        self.superuser.delete()
        self.master.delete()
        self.sys_config.replace(json.dumps({}))

    def test_binlog_list_instance_not_exist(self):
        """
        测试获取binlog列表，实例不存在
        :return:
        """
        data = {"instance_name": "some_instance"}
        r = self.client.post(path="/binlog/list/", data=data)
        self.assertEqual(
            json.loads(r.content), {"status": 1, "msg": "实例不存在", "data": []}
        )

    def test_binlog_list_instance(self):
        """
        测试获取binlog列表，实例存在
        :return:
        """
        data = {"instance_name": "test_instance"}
        r = self.client.post(path="/binlog/list/", data=data)
        # self.assertEqual(json.loads(r.content).get('status'), 1)

    def test_my2sql_path_not_exist(self):
        """
        测试获取解析binlog，path未设置
        :return:
        """
        data = {
            "instance_name": "test_instance",
            "save_sql": "false",
            "rollback": "2sql",
            "num": "",
            "threads": 1,
            "extra_info": "false",
            "ignore_primary_key": "false",
            "full_columns": "false",
            "no_db_prefix": "false",
            "file_per_table": "false",
            "start_file": "mysql-bin.000045",
            "start_pos": "",
            "end_file": "mysql-bin.000045",
            "end_pos": "",
            "stop_time": "",
            "start_time": "",
            "only_schemas": "",
            "sql_type": "",
        }
        r = self.client.post(path="/binlog/my2sql/", data=data)
        self.assertEqual(
            json.loads(r.content),
            {"status": 1, "msg": "可执行文件路径不能为空！", "data": {}},
        )

    @patch("sql.plugins.plugin.subprocess")
    def test_my2sql(self, _subprocess):
        """
        测试获取解析binlog，path设置
        :param _subprocess:
        :return:
        """
        self.sys_config.set("my2sql", "/opt/archery/src/plugins/my2sql")
        self.sys_config.get_all_config()
        data = {
            "instance_name": "test_instance",
            "save_sql": "1",
            "rollback": "2sql",
            "num": "1",
            "threads": 1,
            "extra_info": "false",
            "ignore_primary_key": "false",
            "full_columns": "false",
            "no_db_prefix": "false",
            "file_per_table": "false",
            "start_file": "mysql-bin.000045",
            "start_pos": "",
            "end_file": "mysql-bin.000046",
            "end_pos": "",
            "stop_time": "",
            "start_time": "",
            "only_schemas": "",
            "sql_type": "",
        }
        r = self.client.post(path="/binlog/my2sql/", data=data)
        self.assertEqual(json.loads(r.content), {"status": 0, "msg": "ok", "data": []})

    @patch("builtins.open")
    @patch("sql.plugins.plugin.subprocess")
    def test_my2sql_file(self, _open, _subprocess):
        """
        测试保存文件
        :param _subprocess:
        :return:
        """
        _subprocess.Popen.return_value.communicate.return_value = (
            "some_stdout",
            "some_stderr",
        )
        self.sys_config.set("my2sql", "/opt/archery/src/plugins/my2sql")
        args = {
            "instance_name": "test_instance",
            "save_sql": "1",
            "rollback": "2sql",
            "num": "1",
            "threads": 1,
            "add-extraInfo": "false",
            "ignore-primaryKey-forInsert": "false",
            "full-columns": "false",
            "do-not-add-prifixDb": "false",
            "file-per-table": "false",
            "start-file": "mysql-bin.000045",
            "start-pos": "",
            "stop-file": "mysql-bin.000045",
            "stop-pos": "",
            "stop-datetime": "",
            "start-datetime": "",
            "databases": "",
            "sql": "",
            "instance": self.master,
        }
        r = my2sql_file(args=args, user=self.superuser)
        self.assertEqual(self.superuser, r[0])

    def test_del_binlog_instance_not_exist(self):
        """
        测试删除binlog，实例不存在
        :return:
        """
        data = {
            "instance_id": 0,
            "binlog": "mysql-bin.000001",
        }
        r = self.client.post(path="/binlog/del_log/", data=data)
        self.assertEqual(
            json.loads(r.content), {"status": 1, "msg": "实例不存在", "data": []}
        )

    def test_del_binlog_binlog_not_exist(self):
        """
        测试删除binlog，实例存在,binlog 不存在
        :return:
        """
        data = {"instance_id": self.master.id, "binlog": ""}
        r = self.client.post(path="/binlog/del_log/", data=data)
        self.assertEqual(
            json.loads(r.content),
            {"status": 1, "msg": "Error:未选择binlog！", "data": ""},
        )

    @patch("sql.engines.mysql.MysqlEngine.query")
    @patch("sql.engines.get_engine")
    def test_del_binlog(self, _get_engine, _query):
        """
        测试删除binlog
        :return:
        """
        data = {"instance_id": self.master.id, "binlog": "mysql-bin.000001"}
        _query.return_value = ResultSet(full_sql="select 1")
        r = self.client.post(path="/binlog/del_log/", data=data)
        self.assertEqual(
            json.loads(r.content), {"status": 0, "msg": "清理成功", "data": ""}
        )

    @patch("sql.engines.mysql.MysqlEngine.query")
    @patch("sql.engines.get_engine")
    def test_del_binlog_wrong(self, _get_engine, _query):
        """
        测试删除binlog
        :return:
        """
        data = {"instance_id": self.master.id, "binlog": "mysql-bin.000001"}
        _query.return_value = ResultSet(full_sql="select 1")
        _query.return_value.error = "清理失败"
        r = self.client.post(path="/binlog/del_log/", data=data)
        self.assertEqual(
            json.loads(r.content),
            {"status": 2, "msg": "清理失败,Error:清理失败", "data": ""},
        )


class TestParam(TestCase):
    """
    测试实例参数修改
    """

    def setUp(self):
        self.superuser = User(username="super", is_superuser=True)
        self.superuser.save()
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
        self.client = Client()
        self.client.force_login(self.superuser)

    def tearDown(self):
        self.superuser.delete()
        self.master.delete()
        ParamTemplate.objects.all().delete()

    def test_param_list_instance_not_exist(self):
        """
        测试获取参数列表，实例不存在
        :return:
        """
        data = {"instance_id": 0}
        r = self.client.post(path="/param/list/", data=data)
        self.assertEqual(
            json.loads(r.content), {"status": 1, "msg": "实例不存在", "data": []}
        )

    @patch("sql.engines.mysql.MysqlEngine.get_variables")
    @patch("sql.engines.get_engine")
    def test_param_list_instance_exist(self, _get_engine, _get_variables):
        """
        测试获取参数列表，实例存在
        :return:
        """
        data = {"instance_id": self.master.id, "editable": True}
        r = self.client.post(path="/param/list/", data=data)
        self.assertIsInstance(json.loads(r.content), list)

    def test_param_history(self):
        """
        测试获取参数修改历史
        :return:
        """
        data = {
            "instance_id": self.master.id,
            "search": "binlog",
            "limit": 14,
            "offset": 0,
        }
        r = self.client.post(path="/param/history/", data=data)
        self.assertEqual(json.loads(r.content), {"rows": [], "total": 0})

    @patch("sql.engines.mysql.MysqlEngine.set_variable")
    @patch("sql.engines.mysql.MysqlEngine.get_variables")
    @patch("sql.engines.get_engine")
    def test_param_edit_variable_not_config(
        self, _get_engine, _get_variables, _set_variable
    ):
        """
        测试参数修改，参数未在模板配置
        :return:
        """
        data = {
            "instance_id": self.master.id,
            "variable_name": "1",
            "runtime_value": "false",
        }
        r = self.client.post(path="/param/edit/", data=data)
        self.assertEqual(
            json.loads(r.content),
            {"data": [], "msg": "请先在参数模板中配置该参数！", "status": 1},
        )

    @patch("sql.engines.mysql.MysqlEngine.set_variable")
    @patch("sql.engines.mysql.MysqlEngine.get_variables")
    @patch("sql.engines.get_engine")
    def test_param_edit_variable_not_change(
        self, _get_engine, _get_variables, _set_variable
    ):
        """
        测试参数修改，已在参数模板配置，但是值无变化
        :return:
        """
        _get_variables.return_value.rows = (("binlog_format", "ROW"),)
        _set_variable.return_value.error = None
        _set_variable.return_value.full_sql = "set global binlog_format='STATEMENT';"

        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="binlog_format",
            default_value="ROW",
            editable=True,
        )
        data = {
            "instance_id": self.master.id,
            "variable_name": "binlog_format",
            "runtime_value": "ROW",
        }
        r = self.client.post(path="/param/edit/", data=data)
        self.assertEqual(
            json.loads(r.content),
            {"status": 1, "msg": "参数值与实际运行值一致，未调整！", "data": []},
        )

    @patch("sql.engines.mysql.MysqlEngine.set_variable")
    @patch("sql.engines.mysql.MysqlEngine.get_variables")
    @patch("sql.engines.get_engine")
    def test_param_edit_variable_change(
        self, _get_engine, _get_variables, _set_variable
    ):
        """
        测试参数修改，已在参数模板配置，且值有变化
        :return:
        """
        _get_variables.return_value.rows = (("binlog_format", "ROW"),)
        _set_variable.return_value.error = None
        _set_variable.return_value.full_sql = "set global binlog_format='STATEMENT';"

        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="binlog_format",
            default_value="ROW",
            editable=True,
        )
        data = {
            "instance_id": self.master.id,
            "variable_name": "binlog_format",
            "runtime_value": "STATEMENT",
        }
        r = self.client.post(path="/param/edit/", data=data)
        self.assertEqual(
            json.loads(r.content),
            {"status": 0, "msg": "修改成功，请手动持久化到配置文件！", "data": []},
        )

    @patch("sql.engines.mysql.MysqlEngine.set_variable")
    @patch("sql.engines.mysql.MysqlEngine.get_variables")
    @patch("sql.engines.get_engine")
    def test_param_edit_variable_error(
        self, _get_engine, _get_variables, _set_variable
    ):
        """
        测试参数修改，已在参数模板配置，修改抛错
        :return:
        """
        _get_variables.return_value.rows = (("binlog_format", "ROW"),)
        _set_variable.return_value.error = "修改报错"
        _set_variable.return_value.full_sql = "set global binlog_format='STATEMENT';"

        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="binlog_format",
            default_value="ROW",
            editable=True,
        )
        data = {
            "instance_id": self.master.id,
            "variable_name": "binlog_format",
            "runtime_value": "STATEMENT",
        }
        r = self.client.post(path="/param/edit/", data=data)
        self.assertEqual(
            json.loads(r.content),
            {"status": 1, "msg": "设置错误，错误信息：修改报错", "data": []},
        )


class TestDataDictionary(TestCase):
    """
    测试数据字典
    """

    def setUp(self):
        self.sys_config = SysConfig()
        self.su = User.objects.create(
            username="s_user", display="中文显示", is_active=True, is_superuser=True
        )
        self.u1 = User.objects.create(
            username="user1", display="中文显示", is_active=True
        )
        self.client = Client()
        self.client.force_login(self.su)
        # 使用 travis.ci 时实例和测试service保持一致
        self.ins = Instance.objects.create(
            instance_name="test_instance",
            type="slave",
            db_type="mysql",
            host=settings.DATABASES["default"]["HOST"],
            port=settings.DATABASES["default"]["PORT"],
            user=settings.DATABASES["default"]["USER"],
            password=settings.DATABASES["default"]["PASSWORD"],
        )
        self.db_name = settings.DATABASES["default"]["TEST"]["NAME"]

    def tearDown(self):
        self.sys_config.purge()
        Instance.objects.all().delete()
        User.objects.all().delete()

    def test_data_dictionary_view(self):
        """
        测试访问数据字典页面
        :return:
        """
        r = self.client.get(path="/data_dictionary/")
        self.assertEqual(r.status_code, 200)

    @patch("sql.data_dictionary.get_engine")
    def test_table_list(self, _get_engine):
        """
        测试获取表清单
        :return:
        """
        _get_engine.return_value.get_group_tables_by_db.return_value = {
            "t": [["test1", "测试表1"], ["test2", "测试表2"]]
        }
        data = {
            "instance_name": self.ins.instance_name,
            "db_name": self.db_name,
            "db_type": "mysql",
        }
        r = self.client.get(path="/data_dictionary/table_list/", data=data)
        self.assertEqual(r.status_code, 200)
        self.assertDictEqual(
            json.loads(r.content),
            {"data": {"t": [["test1", "测试表1"], ["test2", "测试表2"]]}, "status": 0},
        )

    def test_table_list_not_param(self):
        """
        测试获取表清单，参数不完整
        :return:
        """
        data = {"instance_name": "not exist ins", "db_type": "mysql"}
        r = self.client.get(path="/data_dictionary/table_list/", data=data)
        self.assertEqual(r.status_code, 200)
        self.assertDictEqual(json.loads(r.content), {"msg": "非法调用！", "status": 1})

    def test_table_list_instance_does_not_exist(self):
        """
        测试获取表清单，实例不存在
        :return:
        """
        data = {
            "instance_name": "not exist ins",
            "db_name": self.db_name,
            "db_type": "mysql",
        }
        r = self.client.get(path="/data_dictionary/table_list/", data=data)
        self.assertEqual(r.status_code, 200)
        self.assertDictEqual(
            json.loads(r.content), {"msg": "Instance.DoesNotExist", "status": 1}
        )

    @patch("sql.data_dictionary.get_engine")
    def test_table_list_exception(self, _get_engine):
        """
        测试获取表清单，异常
        :return:
        """
        _get_engine.side_effect = RuntimeError("test error")
        data = {
            "instance_name": self.ins.instance_name,
            "db_name": self.db_name,
            "db_type": "mysql",
        }
        r = self.client.get(path="/data_dictionary/table_list/", data=data)
        self.assertEqual(r.status_code, 200)
        self.assertDictEqual(json.loads(r.content), {"msg": "test error", "status": 1})

    @patch("sql.data_dictionary.get_engine")
    def test_table_info(self, _get_engine):
        """
        测试获取表信息
        :return:
        """
        _get_engine.return_value.query.return_value = ResultSet(
            rows=(("test1", "测试表1"), ("test2", "测试表2"))
        )
        data = {
            "instance_name": self.ins.instance_name,
            "db_name": self.db_name,
            "tb_name": "sql_instance",
            "db_type": "mysql",
        }
        r = self.client.get(path="/data_dictionary/table_info/", data=data)
        self.assertEqual(r.status_code, 200)
        self.assertListEqual(
            list(json.loads(r.content)["data"].keys()),
            ["meta_data", "desc", "index", "create_sql"],
        )

    def test_table_info_not_param(self):
        """
        测试获取表清单，参数不完整
        :return:
        """
        data = {
            "instance_name": "not exist ins",
        }
        r = self.client.get(path="/data_dictionary/table_info/", data=data)
        self.assertEqual(r.status_code, 200)
        self.assertDictEqual(json.loads(r.content), {"msg": "非法调用！", "status": 1})

    def test_table_info_instance_does_not_exist(self):
        """
        测试获取表清单，实例不存在
        :return:
        """
        data = {
            "instance_name": "not exist ins",
            "db_name": self.db_name,
            "tb_name": "sql_instance",
            "db_type": "mysql",
        }
        r = self.client.get(path="/data_dictionary/table_info/", data=data)
        self.assertEqual(r.status_code, 200)
        self.assertDictEqual(
            json.loads(r.content), {"msg": "Instance.DoesNotExist", "status": 1}
        )

    @patch("sql.data_dictionary.get_engine")
    def test_table_info_exception(self, _get_engine):
        """
        测试获取表清单，异常
        :return:
        """
        _get_engine.side_effect = RuntimeError("test error")
        data = {
            "instance_name": self.ins.instance_name,
            "db_name": self.db_name,
            "tb_name": "sql_instance",
            "db_type": "mysql",
        }
        r = self.client.get(path="/data_dictionary/table_info/", data=data)
        self.assertEqual(r.status_code, 200)
        self.assertDictEqual(json.loads(r.content), {"msg": "test error", "status": 1})

    def test_export_instance_does_not_exist(self):
        """
        测试导出实例不存在
        :return:
        """
        data = {
            "instance_name": "not_exist",
            "db_name": self.db_name,
            "db_type": "mysql",
        }
        r = self.client.get(path="/data_dictionary/export/", data=data)
        self.assertDictEqual(
            json.loads(r.content),
            {"data": [], "msg": "你所在组未关联该实例！", "status": 1},
        )

    @patch("sql.data_dictionary.user_instances")
    @patch("sql.data_dictionary.get_engine")
    def test_export_ins_no_perm(self, _get_engine, _user_instances):
        """
        测试导出实例无权限
        :return:
        """
        self.client.force_login(self.u1)
        data_dictionary_export = Permission.objects.get(
            codename="data_dictionary_export"
        )
        self.u1.user_permissions.add(data_dictionary_export)
        _user_instances.return_value.get.return_value = self.ins
        data = {"instance_name": self.ins.instance_name, "db_type": "mysql"}
        r = self.client.get(path="/data_dictionary/export/", data=data)
        self.assertDictEqual(
            json.loads(r.content),
            {"status": 1, "msg": f"仅管理员可以导出整个实例的字典信息！", "data": []},
        )

    @patch("sql.data_dictionary.get_engine")
    def test_export_db(self, _get_engine):
        """
        测试导出
        :return:
        """

        def dummy(s):
            return s

        _get_engine.return_value.escape_string = dummy
        _get_engine.return_value.get_all_databases.return_value.rows.return_value = (
            ResultSet(rows=(("test1",), ("test2",)))
        )
        _get_engine.return_value.query.return_value = ResultSet(
            rows=(
                {
                    "TABLE_CATALOG": "def",
                    "TABLE_SCHEMA": "archer",
                    "TABLE_NAME": "aliyun_rds_config",
                    "TABLE_TYPE": "BASE TABLE",
                    "ENGINE": "InnoDB",
                    "VERSION": 10,
                    "ROW_FORMAT": "Dynamic",
                    "TABLE_ROWS": 0,
                    "AVG_ROW_LENGTH": 0,
                    "DATA_LENGTH": 16384,
                    "MAX_DATA_LENGTH": 0,
                    "INDEX_LENGTH": 32768,
                    "DATA_FREE": 0,
                    "AUTO_INCREMENT": 1,
                    "CREATE_TIME": datetime(2019, 5, 28, 9, 25, 41),
                    "UPDATE_TIME": None,
                    "CHECK_TIME": None,
                    "TABLE_COLLATION": "utf8_general_ci",
                    "CHECKSUM": None,
                    "CREATE_OPTIONS": "",
                    "TABLE_COMMENT": "",
                },
                {
                    "TABLE_CATALOG": "def",
                    "TABLE_SCHEMA": "archer",
                    "TABLE_NAME": "auth_group",
                    "TABLE_TYPE": "BASE TABLE",
                    "ENGINE": "InnoDB",
                    "VERSION": 10,
                    "ROW_FORMAT": "Dynamic",
                    "TABLE_ROWS": 8,
                    "AVG_ROW_LENGTH": 2048,
                    "DATA_LENGTH": 16384,
                    "MAX_DATA_LENGTH": 0,
                    "INDEX_LENGTH": 16384,
                    "DATA_FREE": 0,
                    "AUTO_INCREMENT": 9,
                    "CREATE_TIME": datetime(2019, 5, 28, 9, 4, 11),
                    "UPDATE_TIME": None,
                    "CHECK_TIME": None,
                    "TABLE_COLLATION": "utf8_general_ci",
                    "CHECKSUM": None,
                    "CREATE_OPTIONS": "",
                    "TABLE_COMMENT": "",
                },
            )
        )
        data = {
            "instance_name": self.ins.instance_name,
            "db_name": self.db_name,
            "db_type": "mysql",
        }
        r = self.client.get(path="/data_dictionary/export/", data=data)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.streaming)

        # 测试恶意请求
        data = {
            "instance_name": self.ins.instance_name,
            "db_name": "/../../../etc/passwd",
            "db_type": "mysql",
        }
        r = self.client.get(path="/data_dictionary/export/", data=data)
        self.assertEqual(r.json()["status"], 1)

    @patch("sql.data_dictionary.get_engine")
    def test_export_instance(self, _get_engine):
        """
        测试导出
        :return:
        """

        def dummy(s):
            return s

        _get_engine.return_value.escape_string = dummy
        _get_engine.return_value.get_all_databases.return_value.rows.return_value = (
            ResultSet(rows=(("test1",), ("test2",)))
        )
        _get_engine.return_value.query.return_value = ResultSet(
            rows=(
                {
                    "TABLE_CATALOG": "def",
                    "TABLE_SCHEMA": "archer",
                    "TABLE_NAME": "aliyun_rds_config",
                    "TABLE_TYPE": "BASE TABLE",
                    "ENGINE": "InnoDB",
                    "VERSION": 10,
                    "ROW_FORMAT": "Dynamic",
                    "TABLE_ROWS": 0,
                    "AVG_ROW_LENGTH": 0,
                    "DATA_LENGTH": 16384,
                    "MAX_DATA_LENGTH": 0,
                    "INDEX_LENGTH": 32768,
                    "DATA_FREE": 0,
                    "AUTO_INCREMENT": 1,
                    "CREATE_TIME": datetime(2019, 5, 28, 9, 25, 41),
                    "UPDATE_TIME": None,
                    "CHECK_TIME": None,
                    "TABLE_COLLATION": "utf8_general_ci",
                    "CHECKSUM": None,
                    "CREATE_OPTIONS": "",
                    "TABLE_COMMENT": "",
                },
                {
                    "TABLE_CATALOG": "def",
                    "TABLE_SCHEMA": "archer",
                    "TABLE_NAME": "auth_group",
                    "TABLE_TYPE": "BASE TABLE",
                    "ENGINE": "InnoDB",
                    "VERSION": 10,
                    "ROW_FORMAT": "Dynamic",
                    "TABLE_ROWS": 8,
                    "AVG_ROW_LENGTH": 2048,
                    "DATA_LENGTH": 16384,
                    "MAX_DATA_LENGTH": 0,
                    "INDEX_LENGTH": 16384,
                    "DATA_FREE": 0,
                    "AUTO_INCREMENT": 9,
                    "CREATE_TIME": datetime(2019, 5, 28, 9, 4, 11),
                    "UPDATE_TIME": None,
                    "CHECK_TIME": None,
                    "TABLE_COLLATION": "utf8_general_ci",
                    "CHECKSUM": None,
                    "CREATE_OPTIONS": "",
                    "TABLE_COMMENT": "",
                },
            )
        )
        data = {"instance_name": self.ins.instance_name, "db_type": "mysql"}
        r = self.client.get(path="/data_dictionary/export/", data=data)
        self.assertEqual(r.status_code, 200)
        self.assertDictEqual(
            json.loads(r.content),
            {
                "data": [],
                "msg": "实例test_instance数据字典导出成功，请到downloads目录下载！",
                "status": 0,
            },
        )
        # 测试恶意请求
        data = {
            "instance_name": self.ins.instance_name,
            "db_name": "/../../../etc/passwd",
            "db_type": "mysql",
        }
        r = self.client.get(path="/data_dictionary/export/", data=data)
        self.assertEqual(r.json()["status"], 1)

    @patch("sql.data_dictionary.get_engine")
    def test_oracle_export_instance(self, _get_engine):
        """
        oracle元数据测试导出
        :return:
        """
        _get_engine.return_value.get_all_databases.return_value.rows.return_value = (
            ResultSet(rows=(("test1",), ("test2",)))
        )
        _get_engine.return_value.query.return_value = ResultSet(
            rows=(
                {
                    "TABLE_NAME": "aliyun_rds_config",
                    "TABLE_COMMENTS": "TABLE",
                    "COLUMN_NAME": "t1",
                    "data_type": "varcher2(20)",
                    "DATA_DEFAULT": "Dynamic",
                    "NULLABLE": "Y",
                    "INDEX_NAME": "SYS_01",
                    "COMMENTS": "SYS_01",
                },
                {
                    "TABLE_NAME": "auth_group",
                    "TABLE_COMMENTS": "TABLE",
                    "COLUMN_NAME": "t1",
                    "data_type": "varcher2(20)",
                    "DATA_DEFAULT": "Dynamic",
                    "NULLABLE": "N",
                    "INDEX_NAME": "SYS_01",
                    "COMMENTS": "SYS_01",
                },
            )
        )
        data = {"instance_name": self.ins.instance_name, "db_type": "oracle"}
        r = self.client.get(path="/data_dictionary/export/", data=data)

        print(r.status_code)
        print("oracle_test_export_instance")
        self.assertEqual(r.status_code, 200)
        self.assertDictEqual(
            json.loads(r.content),
            {
                "data": [],
                "msg": "实例test_instance数据字典导出成功，请到downloads目录下载！",
                "status": 0,
            },
        )
