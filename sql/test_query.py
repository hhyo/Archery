# -*- coding: UTF-8 -*-
import datetime
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Permission
from django.test import Client, TestCase, TransactionTestCase

from common.config import SysConfig
from sql.engines.models import ResultSet
from sql.models import (
    Instance,
    QueryLog,
    ResourceGroup,
    Users,
)
from sql.query import kill_query_conn


class TestQuery(TransactionTestCase):
    """测试 query 视图"""

    def setUp(self):
        self.sys_config = SysConfig()
        self.client = Client()
        self.user = Users.objects.create(
            username="test_user", display="测试用户", is_active=True
        )
        # 添加查询权限
        perm_submit = Permission.objects.get(codename="query_submit")
        perm_menu = Permission.objects.get(codename="menu_sqlquery")
        self.user.user_permissions.add(perm_submit, perm_menu)
        self.client.force_login(self.user)

        self.res_group = ResourceGroup.objects.create(
            group_id=1, group_name="test_group"
        )
        self.instance = Instance.objects.create(
            instance_name="test_ins",
            type="slave",
            db_type="mysql",
            host="some_host",
            port=3306,
            user="ins_user",
            password="some_str",
        )
        self.instance.resource_group.add(self.res_group)
        self.user.resource_group.add(self.res_group)

    def tearDown(self):
        self.sys_config.purge()
        QueryLog.objects.all().delete()

    @patch("sql.query.get_engine")
    @patch("sql.query.query_priv_check")
    @patch("sql.query.del_schedule")
    @patch("sql.query.add_kill_conn_schedule")
    def test_query_normal(
        self, mock_add_schedule, mock_del_schedule, mock_priv_check, mock_get_engine
    ):
        """测试正常查询流程"""
        # 配置 mock
        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "has_star": False,
            "filtered_sql": "select 1",
        }
        mock_engine.filter_sql.return_value = "select 1 limit 100"
        mock_engine.get_connection.return_value = None
        mock_engine.thread_id = 123
        mock_engine.seconds_behind_master = 0
        mock_query_result = ResultSet(
            full_sql="select 1", rows=[[1]], column_list=["1"], affected_rows=1
        )
        mock_query_result.error = None
        mock_query_result.query_time = 0.01
        mock_query_result.mask_rule_hit = False
        mock_query_result.is_masked = False
        mock_engine.query.return_value = mock_query_result
        mock_get_engine.return_value = mock_engine

        mock_priv_check.return_value = {
            "status": 0,
            "msg": "ok",
            "data": {"priv_check": True, "limit_num": 100},
        }

        data = {
            "instance_name": "test_ins",
            "sql_content": "select 1",
            "db_name": "test_db",
            "limit_num": 100,
        }
        r = self.client.post("/query/", data=data)
        self.assertEqual(r.status_code, 200)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 0)
        self.assertEqual(result["msg"], "ok")
        # 验证查询日志已记录
        self.assertTrue(QueryLog.objects.filter(username="test_user").exists())

    def test_query_instance_not_in_group(self):
        """测试查询用户未关联的实例"""
        other_instance = Instance.objects.create(
            instance_name="other_ins",
            type="slave",
            db_type="mysql",
            host="other_host",
            port=3307,
            user="ins_user",
            password="some_str",
        )
        data = {
            "instance_name": "other_ins",
            "sql_content": "select 1",
            "db_name": "test_db",
            "limit_num": 100,
        }
        r = self.client.post("/query/", data=data)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 1)
        self.assertIn("未关联该实例", result["msg"])
        other_instance.delete()

    def test_query_missing_params(self):
        """测试缺少必要参数"""
        data = {
            "instance_name": "test_ins",
            # 缺少 sql_content
            "db_name": "test_db",
            "limit_num": 100,
        }
        r = self.client.post("/query/", data=data)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 1)
        self.assertIn("参数可能为空", result["msg"])

    @patch("sql.query.get_engine")
    def test_query_bad_query(self, mock_get_engine):
        """测试查询语句检查不通过"""
        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": True,
            "msg": "禁止执行该语句",
            "filtered_sql": "",
        }
        mock_get_engine.return_value = mock_engine

        data = {
            "instance_name": "test_ins",
            "sql_content": "drop table t1",
            "db_name": "test_db",
            "limit_num": 100,
        }
        r = self.client.post("/query/", data=data)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 1)
        self.assertIn("禁止执行该语句", result["msg"])

    @patch("sql.query.get_engine")
    def test_query_star_disabled(self, mock_get_engine):
        """测试禁用 * 查询"""
        self.sys_config.set("disable_star", "true")

        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "has_star": True,
            "msg": "禁止使用 * 查询",
            "filtered_sql": "select * from t1",
        }
        mock_get_engine.return_value = mock_engine

        data = {
            "instance_name": "test_ins",
            "sql_content": "select * from t1",
            "db_name": "test_db",
            "limit_num": 100,
        }
        r = self.client.post("/query/", data=data)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 1)
        self.assertIn("禁止使用 * 查询", result["msg"])

    @patch("sql.query.get_engine")
    @patch("sql.query.query_priv_check")
    def test_query_priv_check_failed(self, mock_priv_check, mock_get_engine):
        """测试查询权限校验失败"""
        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "has_star": False,
            "filtered_sql": "select 1",
        }
        mock_get_engine.return_value = mock_engine

        mock_priv_check.return_value = {
            "status": 2,
            "msg": "你无test_db.t1表的查询权限",
            "data": {},
        }

        data = {
            "instance_name": "test_ins",
            "sql_content": "select * from t1",
            "db_name": "test_db",
            "limit_num": 100,
        }
        r = self.client.post("/query/", data=data)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 2)
        self.assertIn("查询权限", result["msg"])

    @patch("sql.query.get_engine")
    @patch("sql.query.query_priv_check")
    @patch("sql.query.del_schedule")
    @patch("sql.query.add_kill_conn_schedule")
    def test_query_with_error(
        self, mock_add_schedule, mock_del_schedule, mock_priv_check, mock_get_engine
    ):
        """测试查询返回错误结果"""
        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "has_star": False,
            "filtered_sql": "select 1",
        }
        mock_engine.filter_sql.return_value = "select 1 limit 100"
        mock_engine.get_connection.return_value = None
        mock_engine.thread_id = 123
        mock_engine.seconds_behind_master = 0
        mock_query_result = ResultSet(
            full_sql="select 1", rows=[], column_list=[], affected_rows=0
        )
        mock_query_result.error = "语法错误"
        mock_query_result.query_time = 0.01
        mock_query_result.mask_rule_hit = False
        mock_query_result.is_masked = False
        mock_engine.query.return_value = mock_query_result
        mock_get_engine.return_value = mock_engine

        mock_priv_check.return_value = {
            "status": 0,
            "msg": "ok",
            "data": {"priv_check": True, "limit_num": 100},
        }

        data = {
            "instance_name": "test_ins",
            "sql_content": "select 1",
            "db_name": "test_db",
            "limit_num": 100,
        }
        r = self.client.post("/query/", data=data)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 1)
        self.assertIn("语法错误", result["msg"])

    @patch("sql.query.get_engine")
    @patch("sql.query.query_priv_check")
    @patch("sql.query.del_schedule")
    @patch("sql.query.add_kill_conn_schedule")
    def test_query_with_data_masking(
        self, mock_add_schedule, mock_del_schedule, mock_priv_check, mock_get_engine
    ):
        """测试数据脱敏正常流程"""
        self.sys_config.set("data_masking", "true")

        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "has_star": False,
            "filtered_sql": "select phone from t1",
        }
        mock_engine.filter_sql.return_value = "select phone from t1 limit 100"
        mock_engine.get_connection.return_value = None
        mock_engine.thread_id = 123
        mock_engine.seconds_behind_master = 0

        mock_query_result = ResultSet(
            full_sql="select phone from t1",
            rows=[["13800138000"]],
            column_list=["phone"],
            affected_rows=1,
        )
        mock_query_result.error = None
        mock_query_result.query_time = 0.01
        mock_query_result.mask_rule_hit = False
        mock_query_result.is_masked = False
        mock_engine.query.return_value = mock_query_result

        mock_masking_result = ResultSet(
            full_sql="select phone from t1",
            rows=[["138****8000"]],
            column_list=["phone"],
            affected_rows=1,
        )
        mock_masking_result.error = None
        mock_masking_result.mask_time = 0.005
        mock_masking_result.mask_rule_hit = True
        mock_masking_result.is_masked = True
        mock_engine.query_masking.return_value = mock_masking_result

        mock_get_engine.return_value = mock_engine

        mock_priv_check.return_value = {
            "status": 0,
            "msg": "ok",
            "data": {"priv_check": True, "limit_num": 100},
        }

        data = {
            "instance_name": "test_ins",
            "sql_content": "select phone from t1",
            "db_name": "test_db",
            "limit_num": 100,
        }
        r = self.client.post("/query/", data=data)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 0)

    @patch("sql.query.get_engine")
    @patch("sql.query.query_priv_check")
    @patch("sql.query.del_schedule")
    @patch("sql.query.add_kill_conn_schedule")
    def test_query_with_data_masking_error_query_check_enabled(
        self, mock_add_schedule, mock_del_schedule, mock_priv_check, mock_get_engine
    ):
        """测试数据脱敏出错且开启query_check时禁止执行"""
        self.sys_config.set("data_masking", "true")
        self.sys_config.set("query_check", "true")

        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "has_star": False,
            "filtered_sql": "select phone from t1",
        }
        mock_engine.filter_sql.return_value = "select phone from t1 limit 100"
        mock_engine.get_connection.return_value = None
        mock_engine.thread_id = 123
        mock_engine.seconds_behind_master = 0

        mock_query_result = ResultSet(
            full_sql="select phone from t1",
            rows=[["13800138000"]],
            column_list=["phone"],
            affected_rows=1,
        )
        mock_query_result.error = None
        mock_query_result.query_time = 0.01
        mock_query_result.mask_rule_hit = False
        mock_query_result.is_masked = False
        mock_engine.query.return_value = mock_query_result

        mock_masking_result = ResultSet()
        mock_masking_result.error = "脱敏规则异常"
        mock_masking_result.mask_time = 0
        mock_masking_result.mask_rule_hit = False
        mock_masking_result.is_masked = False
        mock_engine.query_masking.return_value = mock_masking_result

        mock_get_engine.return_value = mock_engine

        mock_priv_check.return_value = {
            "status": 0,
            "msg": "ok",
            "data": {"priv_check": True, "limit_num": 100},
        }

        data = {
            "instance_name": "test_ins",
            "sql_content": "select phone from t1",
            "db_name": "test_db",
            "limit_num": 100,
        }
        r = self.client.post("/query/", data=data)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 1)
        self.assertIn("数据脱敏异常", result["msg"])

    @patch("sql.query.get_engine")
    @patch("sql.query.query_priv_check")
    @patch("sql.query.del_schedule")
    @patch("sql.query.add_kill_conn_schedule")
    def test_query_with_data_masking_error_query_check_disabled(
        self, mock_add_schedule, mock_del_schedule, mock_priv_check, mock_get_engine
    ):
        """测试数据脱敏出错且关闭query_check时放行"""
        self.sys_config.set("data_masking", "true")
        self.sys_config.set("query_check", "false")

        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "has_star": False,
            "filtered_sql": "select phone from t1",
        }
        mock_engine.filter_sql.return_value = "select phone from t1 limit 100"
        mock_engine.get_connection.return_value = None
        mock_engine.thread_id = 123
        mock_engine.seconds_behind_master = 0

        mock_query_result = ResultSet(
            full_sql="select phone from t1",
            rows=[["13800138000"]],
            column_list=["phone"],
            affected_rows=1,
        )
        mock_query_result.error = None
        mock_query_result.query_time = 0.01
        mock_query_result.mask_rule_hit = False
        mock_query_result.is_masked = False
        mock_engine.query.return_value = mock_query_result

        mock_masking_result = ResultSet()
        mock_masking_result.error = "脱敏规则异常"
        mock_masking_result.mask_time = 0
        mock_masking_result.mask_rule_hit = False
        mock_masking_result.is_masked = False
        mock_engine.query_masking.return_value = mock_masking_result

        mock_get_engine.return_value = mock_engine

        mock_priv_check.return_value = {
            "status": 0,
            "msg": "ok",
            "data": {"priv_check": True, "limit_num": 100},
        }

        data = {
            "instance_name": "test_ins",
            "sql_content": "select phone from t1",
            "db_name": "test_db",
            "limit_num": 100,
        }
        r = self.client.post("/query/", data=data)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 0)

    @patch("sql.query.get_engine")
    @patch("sql.query.query_priv_check")
    @patch("sql.query.del_schedule")
    @patch("sql.query.add_kill_conn_schedule")
    def test_query_exception(
        self, mock_add_schedule, mock_del_schedule, mock_priv_check, mock_get_engine
    ):
        """测试查询过程中抛出异常"""
        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "has_star": False,
            "filtered_sql": "select 1",
        }
        mock_engine.filter_sql.return_value = "select 1 limit 100"
        mock_engine.get_connection.return_value = None
        mock_engine.thread_id = 123
        mock_engine.seconds_behind_master = 0
        mock_engine.query.side_effect = Exception("数据库连接超时")
        mock_get_engine.return_value = mock_engine

        mock_priv_check.return_value = {
            "status": 0,
            "msg": "ok",
            "data": {"priv_check": True, "limit_num": 100},
        }

        data = {
            "instance_name": "test_ins",
            "sql_content": "select 1",
            "db_name": "test_db",
            "limit_num": 100,
        }
        r = self.client.post("/query/", data=data)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 1)
        self.assertIn("查询异常报错", result["msg"])

    @patch("sql.query.get_engine")
    @patch("sql.query.query_priv_check")
    @patch("sql.query.del_schedule")
    @patch("sql.query.add_kill_conn_schedule")
    def test_query_explain_limit_zero(
        self, mock_add_schedule, mock_del_schedule, mock_priv_check, mock_get_engine
    ):
        """测试 explain 语句的 limit_num 为 0"""
        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "has_star": False,
            "filtered_sql": "explain select 1",
        }
        mock_engine.filter_sql.return_value = "explain select 1"
        mock_engine.get_connection.return_value = None
        mock_engine.thread_id = 123
        mock_engine.seconds_behind_master = 0

        mock_query_result = ResultSet(
            full_sql="explain select 1", rows=[], column_list=[], affected_rows=1
        )
        mock_query_result.error = None
        mock_query_result.query_time = 0.01
        mock_query_result.mask_rule_hit = False
        mock_query_result.is_masked = False
        mock_engine.query.return_value = mock_query_result
        mock_get_engine.return_value = mock_engine

        mock_priv_check.return_value = {
            "status": 0,
            "msg": "ok",
            "data": {"priv_check": True, "limit_num": 100},
        }

        data = {
            "instance_name": "test_ins",
            "sql_content": "explain select 1",
            "db_name": "test_db",
            "limit_num": 100,
        }
        r = self.client.post("/query/", data=data)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 0)

    @patch("sql.query.get_engine")
    @patch("sql.query.query_priv_check")
    @patch("sql.query.del_schedule")
    @patch("sql.query.add_kill_conn_schedule")
    def test_query_no_thread_id(
        self, mock_add_schedule, mock_del_schedule, mock_priv_check, mock_get_engine
    ):
        """测试查询时 thread_id 为 None 的情况"""
        mock_engine = MagicMock()
        mock_engine.query_check.return_value = {
            "bad_query": False,
            "has_star": False,
            "filtered_sql": "select 1",
        }
        mock_engine.filter_sql.return_value = "select 1 limit 100"
        mock_engine.get_connection.return_value = None
        mock_engine.thread_id = None
        mock_engine.seconds_behind_master = 0

        mock_query_result = ResultSet(
            full_sql="select 1", rows=[[1]], column_list=["1"], affected_rows=1
        )
        mock_query_result.error = None
        mock_query_result.query_time = 0.01
        mock_query_result.mask_rule_hit = False
        mock_query_result.is_masked = False
        mock_engine.query.return_value = mock_query_result
        mock_get_engine.return_value = mock_engine

        mock_priv_check.return_value = {
            "status": 0,
            "msg": "ok",
            "data": {"priv_check": True, "limit_num": 100},
        }

        data = {
            "instance_name": "test_ins",
            "sql_content": "select 1",
            "db_name": "test_db",
            "limit_num": 100,
        }
        r = self.client.post("/query/", data=data)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 0)
        # thread_id 为 None 时不应该添加 kill schedule
        mock_add_schedule.assert_not_called()


class TestQueryLog(TransactionTestCase):
    """测试查询日志相关视图"""

    def setUp(self):
        self.client = Client()
        self.user = Users.objects.create(
            username="test_user", display="测试用户", is_active=True
        )
        perm_menu = Permission.objects.get(codename="menu_sqlquery")
        self.user.user_permissions.add(perm_menu)
        self.client.force_login(self.user)

        self.query_log = QueryLog.objects.create(
            username="test_user",
            user_display="测试用户",
            instance_name="test_ins",
            db_name="test_db",
            sqllog="select 1",
            effect_row=1,
            cost_time="0.01",
            priv_check=True,
            hit_rule=False,
            masking=False,
        )

    def tearDown(self):
        QueryLog.objects.all().delete()

    def test_querylog_normal(self):
        """测试普通用户查看自己的查询日志"""
        r = self.client.get("/query/querylog/", {"limit": 10, "offset": 0})
        self.assertEqual(r.status_code, 200)
        result = json.loads(r.content)
        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["rows"][0]["sqllog"], "select 1")

    def test_querylog_filter_by_star(self):
        """测试收藏过滤"""
        # 创建两条日志，一条收藏一条不收藏
        QueryLog.objects.filter(pk=self.query_log.pk).update(favorite=True)
        QueryLog.objects.create(
            username="test_user",
            user_display="测试用户",
            instance_name="test_ins",
            db_name="test_db",
            sqllog="select 2",
            effect_row=1,
            cost_time="0.02",
            favorite=False,
        )
        # star=true 只返回收藏的
        r = self.client.get(
            "/query/querylog/", {"limit": 10, "offset": 0, "star": "true"}
        )
        result = json.loads(r.content)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["rows"][0]["sqllog"], "select 1")

        # star=false 等价于不过滤收藏，返回全部
        r = self.client.get(
            "/query/querylog/", {"limit": 10, "offset": 0, "star": "false"}
        )
        result = json.loads(r.content)
        self.assertEqual(result["total"], 2)

    def test_querylog_filter_by_query_log_id(self):
        """测试按ID过滤"""
        r = self.client.get(
            "/query/querylog/",
            {"limit": 10, "offset": 0, "query_log_id": self.query_log.id},
        )
        result = json.loads(r.content)
        self.assertEqual(result["total"], 1)

        r = self.client.get(
            "/query/querylog/", {"limit": 10, "offset": 0, "query_log_id": 99999}
        )
        result = json.loads(r.content)
        self.assertEqual(result["total"], 0)

    def test_querylog_search(self):
        """测试搜索功能"""
        r = self.client.get(
            "/query/querylog/", {"limit": 10, "offset": 0, "search": "select"}
        )
        result = json.loads(r.content)
        self.assertEqual(result["total"], 1)

        r = self.client.get(
            "/query/querylog/", {"limit": 10, "offset": 0, "search": "不存在的内容"}
        )
        result = json.loads(r.content)
        self.assertEqual(result["total"], 0)

    def test_querylog_date_filter(self):
        """测试日期范围过滤"""
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        r = self.client.get(
            "/query/querylog/",
            {"limit": 10, "offset": 0, "start_date": today, "end_date": today},
        )
        result = json.loads(r.content)
        self.assertEqual(result["total"], 1)

    def test_querylog_normal_user_sees_own_logs(self):
        """测试普通用户只能看到自己的日志"""
        QueryLog.objects.create(
            username="other_user",
            user_display="其他用户",
            instance_name="test_ins",
            db_name="test_db",
            sqllog="select 2",
            effect_row=1,
            cost_time="0.02",
        )
        r = self.client.get("/query/querylog/", {"limit": 10, "offset": 0})
        result = json.loads(r.content)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["rows"][0]["sqllog"], "select 1")

    def test_querylog_audit_superuser(self):
        """测试审计员可以查看全部日志"""
        # 给用户添加审计权限
        perm_audit = Permission.objects.get(codename="audit_user")
        self.user.user_permissions.add(perm_audit)
        # 重新登录以刷新权限缓存
        self.client.force_login(self.user)

        QueryLog.objects.create(
            username="other_user",
            user_display="其他用户",
            instance_name="test_ins",
            db_name="test_db",
            sqllog="select 2",
            effect_row=1,
            cost_time="0.02",
        )
        r = self.client.get("/query/querylog_audit/", {"limit": 10, "offset": 0})
        self.assertEqual(r.status_code, 200)
        result = json.loads(r.content)
        self.assertEqual(result["total"], 2)

    def test_querylog_audit_requires_permission(self):
        """测试审计日志需要 audit_user 权限"""
        # 普通用户无 audit_user 权限
        r = self.client.get("/query/querylog_audit/", {"limit": 10, "offset": 0})
        self.assertEqual(r.status_code, 403)


class TestFavorite(TransactionTestCase):
    """测试收藏功能"""

    def setUp(self):
        self.client = Client()
        self.user = Users.objects.create(
            username="test_user", display="测试用户", is_active=True
        )
        perm_menu = Permission.objects.get(codename="menu_sqlquery")
        self.user.user_permissions.add(perm_menu)
        self.client.force_login(self.user)

        self.query_log = QueryLog.objects.create(
            username="test_user",
            user_display="测试用户",
            instance_name="test_ins",
            db_name="test_db",
            sqllog="select 1",
            effect_row=1,
            cost_time="0.01",
        )

    def tearDown(self):
        QueryLog.objects.all().delete()

    def test_favorite_add(self):
        """测试添加收藏"""
        r = self.client.post(
            "/query/favorite/",
            {"query_log_id": self.query_log.id, "star": "true", "alias": "常用查询"},
        )
        self.assertEqual(r.status_code, 200)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 0)
        self.query_log.refresh_from_db()
        self.assertTrue(self.query_log.favorite)
        self.assertEqual(self.query_log.alias, "常用查询")

    def test_favorite_remove(self):
        """测试取消收藏"""
        self.query_log.favorite = True
        self.query_log.alias = "常用查询"
        self.query_log.save(update_fields=["favorite", "alias"])

        r = self.client.post(
            "/query/favorite/",
            {"query_log_id": self.query_log.id, "star": "false", "alias": ""},
        )
        self.assertEqual(r.status_code, 200)
        result = json.loads(r.content)
        self.assertEqual(result["status"], 0)
        self.query_log.refresh_from_db()
        self.assertFalse(self.query_log.favorite)


class TestKillQueryConn(TestCase):
    """测试终止查询会话"""

    @patch("sql.query.get_engine")
    def test_kill_query_conn(self, mock_get_engine):
        """测试终止查询连接"""
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        instance = Instance.objects.create(
            instance_name="test_ins",
            type="slave",
            db_type="mysql",
            host="some_host",
            port=3306,
            user="ins_user",
            password="some_str",
        )
        kill_query_conn(instance.id, 123)
        mock_engine.kill_connection.assert_called_once_with(123)
        instance.delete()


class TestGenerateSql(TransactionTestCase):
    """测试 AI 生成 SQL"""

    def setUp(self):
        self.client = Client()
        self.user = Users.objects.create(
            username="test_user", display="测试用户", is_active=True
        )
        perm_menu = Permission.objects.get(codename="menu_sqlquery")
        self.user.user_permissions.add(perm_menu)
        self.client.force_login(self.user)

        self.instance = Instance.objects.create(
            instance_name="test_ins",
            type="slave",
            db_type="mysql",
            host="some_host",
            port=3306,
            user="ins_user",
            password="some_str",
        )

    def tearDown(self):
        Instance.objects.filter(instance_name="test_ins").delete()

    def test_generate_sql_missing_params(self):
        """测试缺少必要参数"""
        r = self.client.post("/query/generate_sql/", {"query_desc": "test"})
        result = json.loads(r.content)
        self.assertEqual(result["status"], 1)
        self.assertIn("不存在", result["msg"])

    @patch("sql.query.OpenaiClient")
    @patch("sql.query.get_engine")
    def test_generate_sql_normal(self, mock_get_engine, mock_openai_cls):
        """测试正常生成 SQL"""
        mock_engine = MagicMock()
        mock_result = ResultSet(
            full_sql="",
            rows=[["CREATE TABLE t1 (id INT)"]],
            column_list=["table_create"],
        )
        mock_result.rows = [["CREATE TABLE t1 (id INT)"]]
        mock_engine.describe_table.return_value = mock_result
        mock_get_engine.return_value = mock_engine

        mock_openai = MagicMock()
        mock_openai.generate_sql_by_openai.return_value = (
            "SELECT * FROM t1 WHERE id = 1"
        )
        mock_openai_cls.return_value = mock_openai

        r = self.client.post(
            "/query/generate_sql/",
            {
                "query_desc": "查询id为1的记录",
                "db_type": "mysql",
                "instance_name": "test_ins",
                "db_name": "test_db",
                "tb_name_list[]": "t1",
            },
        )
        result = json.loads(r.content)
        self.assertEqual(result["status"], 0)
        self.assertEqual(result["data"], "SELECT * FROM t1 WHERE id = 1")

    @patch("sql.query.OpenaiClient")
    @patch("sql.query.get_engine")
    def test_generate_sql_exception(self, mock_get_engine, mock_openai_cls):
        """测试生成 SQL 抛出异常"""
        mock_engine = MagicMock()
        mock_result = ResultSet(full_sql="", rows=[], column_list=[])
        mock_engine.describe_table.return_value = mock_result
        mock_get_engine.return_value = mock_engine

        mock_openai = MagicMock()
        mock_openai.generate_sql_by_openai.side_effect = Exception("API 调用失败")
        mock_openai_cls.return_value = mock_openai

        r = self.client.post(
            "/query/generate_sql/",
            {
                "query_desc": "查询id为1的记录",
                "db_type": "mysql",
                "instance_name": "test_ins",
                "db_name": "test_db",
                "tb_name_list[]": "t1",
            },
        )
        result = json.loads(r.content)
        self.assertEqual(result["status"], 1)
        self.assertIn("API 调用失败", result["msg"])

    def test_generate_sql_instance_not_exist(self):
        """测试实例不存在"""
        r = self.client.post(
            "/query/generate_sql/",
            {
                "query_desc": "查询id为1的记录",
                "db_type": "mysql",
                "instance_name": "not_exist_ins",
                "db_name": "test_db",
            },
        )
        result = json.loads(r.content)
        self.assertEqual(result["status"], 1)
        self.assertIn("实例不存在", result["msg"])


class TestCheckOpenai(TransactionTestCase):
    """测试 OpenAI 配置校验"""

    def setUp(self):
        self.client = Client()
        self.user = Users.objects.create(
            username="test_user", display="测试用户", is_active=True
        )
        self.client.force_login(self.user)

    def tearDown(self):
        self.user.delete()

    @patch("sql.query.check_openai_config")
    def test_check_openai_config_exists(self, mock_check):
        """测试 OpenAI 配置存在"""
        mock_check.return_value = True
        r = self.client.get("/check/openai/")
        result = json.loads(r.content)
        self.assertEqual(result["status"], 0)
        self.assertTrue(result["data"])

    @patch("sql.query.check_openai_config")
    def test_check_openai_config_not_exists(self, mock_check):
        """测试 OpenAI 配置不存在"""
        mock_check.return_value = False
        r = self.client.get("/check/openai/")
        result = json.loads(r.content)
        self.assertEqual(result["status"], 1)
        self.assertIn("缺少配置", result["msg"])
        self.assertFalse(result["data"])
