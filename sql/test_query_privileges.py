import json
from datetime import datetime, timedelta, date
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import TestCase, Client
from pytest_django.asserts import assertRedirects

import sql.query_privileges
from common.config import SysConfig
from common.utils.const import WorkflowAction, WorkflowStatus
from sql.models import Instance, ResourceGroup, QueryPrivilegesApply, QueryPrivileges
from sql.tests import User
from sql.utils.workflow_audit import AuditV2


class TestQueryPrivilegesApply(TestCase):
    """测试权限列表、权限管理"""

    def setUp(self):
        self.superuser = User.objects.create(username="super", is_superuser=True)
        self.user = User.objects.create(username="user")
        # 使用 travis.ci 时实例和测试service保持一致
        self.slave = Instance.objects.create(
            instance_name="test_instance",
            type="slave",
            db_type="mysql",
            host=settings.DATABASES["default"]["HOST"],
            port=settings.DATABASES["default"]["PORT"],
            user=settings.DATABASES["default"]["USER"],
            password=settings.DATABASES["default"]["PASSWORD"],
        )
        self.db_name = settings.DATABASES["default"]["TEST"]["NAME"]
        self.sys_config = SysConfig()
        self.client = Client()
        tomorrow = datetime.today() + timedelta(days=1)
        self.group = ResourceGroup.objects.create(group_id=1, group_name="group_name")
        self.query_apply_1 = QueryPrivilegesApply.objects.create(
            group_id=self.group.group_id,
            group_name=self.group.group_name,
            title="some_title1",
            user_name="some_user",
            instance=self.slave,
            db_list="some_db,some_db2",
            limit_num=100,
            valid_date=tomorrow,
            priv_type=1,
            status=0,
            audit_auth_groups="some_audit_group",
        )
        self.query_apply_2 = QueryPrivilegesApply.objects.create(
            group_id=2,
            group_name="some_group2",
            title="some_title2",
            user_name="some_user",
            instance=self.slave,
            db_list="some_db",
            table_list="some_table,some_tb2",
            limit_num=100,
            valid_date=tomorrow,
            priv_type=2,
            status=0,
            audit_auth_groups="some_audit_group",
        )

    def tearDown(self):
        self.superuser.delete()
        self.user.delete()
        Instance.objects.all().delete()
        ResourceGroup.objects.all().delete()
        QueryPrivilegesApply.objects.all().delete()
        QueryPrivileges.objects.all().delete()
        self.sys_config.replace(json.dumps({}))

    def test_query_audit_call_back(self):
        """测试权限申请工单回调"""
        # 工单状态改为审核失败, 验证工单状态
        sql.query_privileges._query_apply_audit_call_back(
            self.query_apply_1.apply_id, 2
        )
        self.query_apply_1.refresh_from_db()
        self.assertEqual(self.query_apply_1.status, 2)
        for db in self.query_apply_1.db_list.split(","):
            self.assertEqual(
                len(
                    QueryPrivileges.objects.filter(
                        user_name=self.query_apply_1.user_name,
                        db_name=db,
                        limit_num=100,
                    )
                ),
                0,
            )
        # 工单改为审核成功, 验证工单状态和权限状态
        sql.query_privileges._query_apply_audit_call_back(
            self.query_apply_1.apply_id, 1
        )
        self.query_apply_1.refresh_from_db()
        self.assertEqual(self.query_apply_1.status, 1)
        for db in self.query_apply_1.db_list.split(","):
            self.assertEqual(
                len(
                    QueryPrivileges.objects.filter(
                        user_name=self.query_apply_1.user_name,
                        db_name=db,
                        limit_num=100,
                    )
                ),
                1,
            )
        # 表权限申请测试, 只测试审核成功
        sql.query_privileges._query_apply_audit_call_back(
            self.query_apply_2.apply_id, 1
        )
        self.query_apply_2.refresh_from_db()
        self.assertEqual(self.query_apply_2.status, 1)
        for tb in self.query_apply_2.table_list.split(","):
            self.assertEqual(
                len(
                    QueryPrivileges.objects.filter(
                        user_name=self.query_apply_2.user_name,
                        db_name=self.query_apply_2.db_list,
                        table_name=tb,
                        limit_num=self.query_apply_2.limit_num,
                    )
                ),
                1,
            )

    def test_query_priv_apply_list_super_with_search(self):
        """
        测试权限申请列表，管理员查看所有用户，并且搜索
        """
        data = {"limit": 14, "offset": 0, "search": "some_title1"}
        self.client.force_login(self.superuser)
        r = self.client.post(path="/query/applylist/", data=data)
        self.assertEqual(json.loads(r.content)["total"], 1)
        keys = list(json.loads(r.content)["rows"][0].keys())
        self.assertListEqual(
            keys,
            [
                "apply_id",
                "title",
                "instance__instance_name",
                "db_list",
                "priv_type",
                "table_list",
                "limit_num",
                "valid_date",
                "user_display",
                "status",
                "create_time",
                "group_name",
            ],
        )

    def test_query_priv_apply_list_with_query_review_perm(self):
        """
        测试权限申请列表，普通用户，拥有sql.query_review权限，在组内
        """
        data = {"limit": 14, "offset": 0, "search": ""}

        menu_queryapplylist = Permission.objects.get(codename="menu_queryapplylist")
        self.user.user_permissions.add(menu_queryapplylist)
        query_review = Permission.objects.get(codename="query_review")
        self.user.user_permissions.add(query_review)
        self.user.resource_group.add(self.group)
        self.client.force_login(self.user)
        r = self.client.post(path="/query/applylist/", data=data)
        self.assertEqual(json.loads(r.content)["total"], 1)
        keys = list(json.loads(r.content)["rows"][0].keys())
        self.assertListEqual(
            keys,
            [
                "apply_id",
                "title",
                "instance__instance_name",
                "db_list",
                "priv_type",
                "table_list",
                "limit_num",
                "valid_date",
                "user_display",
                "status",
                "create_time",
                "group_name",
            ],
        )

    def test_query_priv_apply_list_no_query_review_perm(self):
        """
        测试权限申请列表，普通用户，无sql.query_review权限，在组内
        """
        data = {"limit": 14, "offset": 0, "search": ""}

        menu_queryapplylist = Permission.objects.get(codename="menu_queryapplylist")
        self.user.user_permissions.add(menu_queryapplylist)
        self.user.resource_group.add(self.group)
        self.client.force_login(self.user)
        r = self.client.post(path="/query/applylist/", data=data)
        self.assertEqual(json.loads(r.content), {"total": 0, "rows": []})

    def test_user_query_priv_with_search(self):
        """
        测试权限申请列表，管理员查看所有用户，并且搜索
        """
        data = {"limit": 14, "offset": 0, "search": "user"}
        QueryPrivileges.objects.create(
            user_name=self.user.username,
            user_display="user2",
            instance=self.slave,
            db_name=self.db_name,
            table_name="table_name",
            valid_date=date.today() + timedelta(days=1),
            limit_num=10,
            priv_type=2,
        )
        self.client.force_login(self.superuser)
        r = self.client.post(path="/query/userprivileges/", data=data)
        self.assertEqual(json.loads(r.content)["total"], 1)
        keys = list(json.loads(r.content)["rows"][0].keys())
        self.assertListEqual(
            keys,
            [
                "privilege_id",
                "user_display",
                "instance__instance_name",
                "db_name",
                "priv_type",
                "table_name",
                "limit_num",
                "valid_date",
            ],
        )

    def test_user_query_priv_with_query_mgtpriv(self):
        """
        测试权限申请列表，普通用户，拥有sql.query_mgtpriv权限，在组内
        """
        data = {"limit": 14, "offset": 0, "search": "user"}
        QueryPrivileges.objects.create(
            user_name="some_name",
            user_display="user2",
            instance=self.slave,
            db_name=self.db_name,
            table_name="table_name",
            valid_date=date.today() + timedelta(days=1),
            limit_num=10,
            priv_type=2,
        )
        menu_queryapplylist = Permission.objects.get(codename="menu_queryapplylist")
        self.user.user_permissions.add(menu_queryapplylist)
        query_mgtpriv = Permission.objects.get(codename="query_mgtpriv")
        self.user.user_permissions.add(query_mgtpriv)
        self.user.resource_group.add(self.group)
        self.client.force_login(self.user)
        r = self.client.post(path="/query/userprivileges/", data=data)
        self.assertEqual(json.loads(r.content)["total"], 1)
        keys = list(json.loads(r.content)["rows"][0].keys())
        self.assertListEqual(
            keys,
            [
                "privilege_id",
                "user_display",
                "instance__instance_name",
                "db_name",
                "priv_type",
                "table_name",
                "limit_num",
                "valid_date",
            ],
        )

    def test_user_query_priv_no_query_mgtpriv(self):
        """
        测试权限申请列表，普通用户，没有sql.query_mgtpriv权限，在组内
        """
        data = {"limit": 14, "offset": 0, "search": "user"}
        QueryPrivileges.objects.create(
            user_name="some_name",
            user_display="user2",
            instance=self.slave,
            db_name=self.db_name,
            table_name="table_name",
            valid_date=date.today() + timedelta(days=1),
            limit_num=10,
            priv_type=2,
        )
        menu_queryapplylist = Permission.objects.get(codename="menu_queryapplylist")
        self.user.user_permissions.add(menu_queryapplylist)
        self.user.resource_group.add(self.group)
        self.client.force_login(self.user)
        r = self.client.post(path="/query/userprivileges/", data=data)
        self.assertEqual(json.loads(r.content), {"total": 0, "rows": []})


class TestQueryPrivilegesCheck(TestCase):
    """测试权限校验"""

    def setUp(self):
        self.superuser = User.objects.create(username="super", is_superuser=True)
        self.user_can_query_all = User.objects.create(username="normaluser")
        query_all_instance_perm = Permission.objects.get(codename="query_all_instances")
        self.user_can_query_all.user_permissions.add(query_all_instance_perm)
        self.user = User.objects.create(username="user")
        # 使用 travis.ci 时实例和测试service保持一致
        self.slave = Instance.objects.create(
            instance_name="test_instance",
            type="slave",
            db_type="mysql",
            host=settings.DATABASES["default"]["HOST"],
            port=settings.DATABASES["default"]["PORT"],
            user=settings.DATABASES["default"]["USER"],
            password=settings.DATABASES["default"]["PASSWORD"],
        )
        self.db_name = settings.DATABASES["default"]["TEST"]["NAME"]
        self.sys_config = SysConfig()
        self.client = Client()

    def tearDown(self):
        self.superuser.delete()
        self.user.delete()
        Instance.objects.all().delete()
        QueryPrivileges.objects.all().delete()
        self.sys_config.replace(json.dumps({}))

    def test_db_priv_super(self):
        """
        测试超级管理员验证数据库权限
        :return:
        """
        self.sys_config.set("admin_query_limit", "50")
        self.sys_config.get_all_config()
        r = sql.query_privileges._db_priv(
            user=self.superuser, instance=self.slave, db_name=self.db_name
        )
        self.assertEqual(r, 50)

    def test_db_priv_user_priv_not_exist(self):
        """
        测试普通用户验证数据库权限，用户无权限
        :return:
        """
        r = sql.query_privileges._db_priv(
            user=self.user, instance=self.slave, db_name=self.db_name
        )
        self.assertFalse(r)

    def test_db_priv_user_priv_exist(self):
        """
        测试普通用户验证数据库权限，用户有权限
        :return:
        """
        QueryPrivileges.objects.create(
            user_name=self.user.username,
            instance=self.slave,
            db_name=self.db_name,
            valid_date=date.today() + timedelta(days=1),
            limit_num=10,
            priv_type=1,
        )
        r = sql.query_privileges._db_priv(
            user=self.user, instance=self.slave, db_name=self.db_name
        )
        self.assertTrue(r)

    def test_tb_priv_super(self):
        """
        测试超级管理员验证表权限
        :return:
        """
        self.sys_config.set("admin_query_limit", "50")
        self.sys_config.get_all_config()
        r = sql.query_privileges._tb_priv(
            user=self.superuser,
            instance=self.slave,
            db_name=self.db_name,
            tb_name="table_name",
        )
        self.assertEqual(r, 50)

    def test_tb_priv_user_priv_not_exist(self):
        """
        测试普通用户验证表权限，用户无权限
        :return:
        """
        r = sql.query_privileges._tb_priv(
            user=self.user,
            instance=self.slave,
            db_name=self.db_name,
            tb_name="table_name",
        )
        self.assertFalse(r)

    def test_tb_priv_user_priv_exist(self):
        """
        测试普通用户验证表权限，用户有权限
        :return:
        """
        QueryPrivileges.objects.create(
            user_name=self.user.username,
            instance=self.slave,
            db_name=self.db_name,
            table_name="table_name",
            valid_date=date.today() + timedelta(days=1),
            limit_num=10,
            priv_type=2,
        )
        r = sql.query_privileges._tb_priv(
            user=self.user,
            instance=self.slave,
            db_name=self.db_name,
            tb_name="table_name",
        )
        self.assertTrue(r)

    @patch("sql.query_privileges._db_priv")
    def test_priv_limit_from_db(self, __db_priv):
        """
        测试用户获取查询数量限制，通过库名获取
        :return:
        """
        __db_priv.return_value = 10
        r = sql.query_privileges._priv_limit(
            user=self.user, instance=self.slave, db_name=self.db_name
        )
        self.assertEqual(r, 10)

    @patch("sql.query_privileges._tb_priv")
    @patch("sql.query_privileges._db_priv")
    def test_priv_limit_from_tb(self, __db_priv, __tb_priv):
        """
        测试用户获取查询数量限制，通过表名获取
        :return:
        """
        __db_priv.return_value = 10
        __tb_priv.return_value = 1
        r = sql.query_privileges._priv_limit(
            user=self.user, instance=self.slave, db_name=self.db_name, tb_name="test"
        )
        self.assertEqual(r, 1)

    @patch("sql.engines.goinception.GoInceptionEngine.query_print")
    def test_table_ref(self, _query_print):
        """
        测试通过goInception获取查询语句的table_ref
        :return:
        """
        _query_print.return_value = {
            "id": 2,
            "statement": "select * from sql_users limit 100",
            "errlevel": 0,
            "query_tree": '{"text":"select * from sql_users limit 100","resultFields":null,"SQLCache":true,"CalcFoundRows":false,"StraightJoin":false,"Priority":0,"Distinct":false,"From":{"text":"","TableRefs":{"text":"","resultFields":null,"Left":{"text":"","Source":{"text":"","resultFields":null,"Schema":{"O":"","L":""},"Name":{"O":"sql_users","L":"sql_users"},"DBInfo":null,"TableInfo":null,"IndexHints":null},"AsName":{"O":"","L":""}},"Right":null,"Tp":0,"On":null,"Using":null,"NaturalJoin":false,"StraightJoin":false}},"Where":null,"Fields":{"text":"","Fields":[{"text":"","Offset":33,"WildCard":{"text":"","Table":{"O":"","L":""},"Schema":{"O":"","L":""}},"Expr":null,"AsName":{"O":"","L":""},"Auxiliary":false}]},"GroupBy":null,"Having":null,"OrderBy":null,"Limit":{"text":"","Count":{"text":"","k":2,"collation":0,"decimal":0,"length":0,"i":100,"b":null,"x":null,"Type":{"Tp":8,"Flag":160,"Flen":3,"Decimal":0,"Charset":"binary","Collate":"binary","Elems":null},"flag":0,"projectionOffset":-1},"Offset":null},"LockTp":0,"TableHints":null,"IsAfterUnionDistinct":false,"IsInBraces":false}',
            "errmsg": None,
        }
        r = sql.query_privileges._table_ref(
            "select * from sql_users limit 100;", self.slave, self.db_name
        )
        self.assertListEqual(r, [{"schema": "test_archery", "name": "sql_users"}])

    @patch("sql.engines.goinception.GoInceptionEngine.query_print")
    def test_table_ref_wrong(self, _query_print):
        """
        测试通过goInception获取查询语句的table_ref
        :return:
        """
        _query_print.side_effect = RuntimeError("语法错误")
        with self.assertRaises(RuntimeError):
            sql.query_privileges._table_ref(
                "select * from archery.sql_users;", self.slave, self.db_name
            )

    def test_query_priv_check_super(self):
        """
        测试用户权限校验，超级管理员不做校验，直接返回系统配置的limit
        :return:
        """
        r = sql.query_privileges.query_priv_check(
            user=self.superuser,
            instance=self.slave,
            db_name=self.db_name,
            sql_content="select * from archery.sql_users;",
            limit_num=100,
        )
        self.assertDictEqual(
            r,
            {"status": 0, "msg": "ok", "data": {"priv_check": True, "limit_num": 100}},
        )
        r = sql.query_privileges.query_priv_check(
            user=self.user_can_query_all,
            instance=self.slave,
            db_name=self.db_name,
            sql_content="select * from archery.sql_users;",
            limit_num=100,
        )
        self.assertDictEqual(
            r,
            {"status": 0, "msg": "ok", "data": {"priv_check": True, "limit_num": 100}},
        )

    def test_query_priv_check_explain_or_show_create(self):
        """测试用户权限校验，explain和show create不做校验"""
        r = sql.query_privileges.query_priv_check(
            user=self.user,
            instance=self.slave,
            db_name=self.db_name,
            sql_content="show create table archery.sql_users;",
            limit_num=100,
        )
        self.assertTrue(r)

    @patch(
        "sql.query_privileges._table_ref",
        return_value=[{"schema": "archery", "name": "sql_users"}],
    )
    @patch("sql.query_privileges._tb_priv", return_value=False)
    @patch("sql.query_privileges._db_priv", return_value=False)
    def test_query_priv_check_no_priv(self, __db_priv, __tb_priv, __table_ref):
        """
        测试用户权限校验，mysql实例、普通用户 无库表权限，inception语法树正常打印
        :return:
        """
        r = sql.query_privileges.query_priv_check(
            user=self.user,
            instance=self.slave,
            db_name=self.db_name,
            sql_content="select * from archery.sql_users;",
            limit_num=100,
        )
        self.assertDictEqual(
            r,
            {
                "status": 2,
                "msg": "你无archery.sql_users表的查询权限！请先到查询权限管理进行申请",
                "data": {"priv_check": True, "limit_num": 0},
            },
        )

    @patch(
        "sql.query_privileges._table_ref",
        return_value=[{"schema": "archery", "name": "sql_users"}],
    )
    @patch("sql.query_privileges._tb_priv", return_value=False)
    @patch("sql.query_privileges._db_priv", return_value=1000)
    def test_query_priv_check_db_priv_exist(self, __db_priv, __tb_priv, __table_ref):
        """
        测试用户权限校验，mysql实例、普通用户 有库权限，inception语法树正常打印
        :return:
        """
        r = sql.query_privileges.query_priv_check(
            user=self.user,
            instance=self.slave,
            db_name=self.db_name,
            sql_content="select * from archery.sql_users;",
            limit_num=100,
        )
        self.assertDictEqual(
            r,
            {"data": {"limit_num": 100, "priv_check": True}, "msg": "ok", "status": 0},
        )

    @patch(
        "sql.query_privileges._table_ref",
        return_value=[{"schema": "archery", "name": "sql_users"}],
    )
    @patch("sql.query_privileges._tb_priv", return_value=10)
    @patch("sql.query_privileges._db_priv", return_value=False)
    def test_query_priv_check_tb_priv_exist(self, __db_priv, __tb_priv, __table_ref):
        """
        测试用户权限校验，mysql实例、普通用户 ，有表权限，inception语法树正常打印
        :return:
        """
        r = sql.query_privileges.query_priv_check(
            user=self.user,
            instance=self.slave,
            db_name=self.db_name,
            sql_content="select * from archery.sql_users;",
            limit_num=100,
        )
        self.assertDictEqual(
            r, {"data": {"limit_num": 10, "priv_check": True}, "msg": "ok", "status": 0}
        )

    @patch("sql.query_privileges._table_ref")
    @patch("sql.query_privileges._tb_priv", return_value=False)
    @patch("sql.query_privileges._db_priv", return_value=False)
    def test_query_priv_check_table_ref_Exception_and_no_db_priv(
        self, __db_priv, __tb_priv, __table_ref
    ):
        """
        测试用户权限校验，mysql实例、普通用户 ，inception语法树抛出异常
        :return:
        """
        __table_ref.side_effect = RuntimeError("语法错误")
        self.sys_config.get_all_config()
        r = sql.query_privileges.query_priv_check(
            user=self.user,
            instance=self.slave,
            db_name=self.db_name,
            sql_content="select * from archery.sql_users;",
            limit_num=100,
        )
        self.assertDictEqual(
            r,
            {
                "status": 1,
                "msg": "无法校验查询语句权限，请联系管理员，错误信息：语法错误",
                "data": {"priv_check": True, "limit_num": 0},
            },
        )

    @patch("sql.query_privileges._db_priv", return_value=1000)
    def test_query_priv_check_not_mysql_db_priv_exist(self, __db_priv):
        """
        测试用户权限校验，非mysql实例、普通用户 有库权限
        :return:
        """
        mssql_instance = Instance(
            instance_name="mssql",
            type="slave",
            db_type="mssql",
            host="some_host",
            port=3306,
            user="some_user",
            password="some_str",
        )
        r = sql.query_privileges.query_priv_check(
            user=self.user,
            instance=mssql_instance,
            db_name=self.db_name,
            sql_content="select * from archery.sql_users;",
            limit_num=100,
        )
        self.assertDictEqual(
            r,
            {"data": {"limit_num": 100, "priv_check": True}, "msg": "ok", "status": 0},
        )

    @patch("sql.query_privileges._db_priv", return_value=False)
    def test_query_priv_check_not_mysql_db_priv_not_exist(self, __db_priv):
        """
        测试用户权限校验，非mysql实例、普通用户 无库权限
        :return:
        """
        mssql_instance = Instance(
            instance_name="mssql",
            type="slave",
            db_type="oracle",
            host="some_host",
            port=3306,
            user="some_user",
            password="some_str",
        )
        r = sql.query_privileges.query_priv_check(
            user=self.user,
            instance=mssql_instance,
            db_name=self.db_name,
            sql_content="select * from archery.sql_users;",
            limit_num=100,
        )
        self.assertDictEqual(
            r,
            {
                "data": {"limit_num": 0, "priv_check": True},
                "msg": "你无archery数据库的查询权限！请先到查询权限管理进行申请",
                "status": 2,
            },
        )


def test_query_privilege_audit(
    sql_query_apply, resource_group, super_user, client, fake_generate_audit_setting
):
    client.force_login(super_user)
    auditor = AuditV2(workflow=sql_query_apply)
    auditor.create_audit()
    response = client.post(
        "/query/privaudit/",
        data={
            "apply_id": sql_query_apply.apply_id,
            "audit_status": WorkflowAction.PASS,
            "audit_remark": "test",
        },
    )
    assertRedirects(
        response,
        fetch_redirect_response=False,
        expected_url=f"/queryapplydetail/{sql_query_apply.apply_id}/",
    )
    sql_query_apply.refresh_from_db()
    assert sql_query_apply.status == WorkflowStatus.PASSED
