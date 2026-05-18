# -*- coding: UTF-8 -*-
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from sql.models import Instance, ResourceGroup, Users, AliyunRdsConfig


class TestSlowQueryReview(TestCase):
    """测试 slowquery_review 视图"""

    def setUp(self):
        self.client = Client()
        self.user = Users.objects.create(
            username="test_user", display="测试用户", is_active=True
        )
        # 赋予慢查菜单权限
        perm = Permission.objects.get(codename="menu_slowquery")
        self.user.user_permissions.add(perm)
        # 赋予查询所有实例权限，简化权限校验
        perm_all = Permission.objects.get(codename="query_all_instances")
        self.user.user_permissions.add(perm_all)
        self.client.force_login(self.user)

        self.instance = Instance.objects.create(
            instance_name="test_mysql",
            type="slave",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="root",
            password="password",
        )

    def tearDown(self):
        Users.objects.all().delete()
        Instance.objects.all().delete()
        ResourceGroup.objects.all().delete()
        AliyunRdsConfig.objects.all().delete()

    def test_instance_not_exist(self):
        """实例不存在时应返回错误"""
        data = {
            "instance_name": "not_exist",
            "StartTime": "2024-01-01",
            "EndTime": "2024-01-02",
            "db_name": "",
            "limit": 10,
            "offset": 0,
        }
        r = self.client.post("/slowquery/review/", data=data)
        self.assertEqual(r.status_code, 200)
        resp = r.json()
        self.assertEqual(resp["status"], 1)
        self.assertEqual(resp["msg"], "实例不存在")

    def test_no_permission(self):
        """用户没有实例权限时应返回错误"""
        self.user.user_permissions.remove(
            Permission.objects.get(codename="query_all_instances")
        )
        data = {
            "instance_name": self.instance.instance_name,
            "StartTime": "2024-01-01",
            "EndTime": "2024-01-02",
            "db_name": "",
            "limit": 10,
            "offset": 0,
        }
        r = self.client.post("/slowquery/review/", data=data)
        self.assertEqual(r.status_code, 200)
        resp = r.json()
        self.assertEqual(resp["status"], 1)
        self.assertEqual(resp["msg"], "你所在组未关联该实例")

    @patch("sql.slowlog.SlowQuery.objects")
    def test_mysql_local(self, mock_slow_query_objects):
        """MySQL本地实例慢查统计"""
        mock_qs = MagicMock()
        mock_slow_query_objects.filter.return_value = mock_qs
        mock_qs.annotate.return_value = mock_qs
        mock_qs.values.return_value = mock_qs
        mock_qs.count.return_value = 1
        mock_qs.order_by.return_value = [
            {
                "SQLText": "SELECT * FROM t",
                "SQLId": "abc123",
                "CreateTime": datetime.now(),
                "DBName": "test_db",
                "QueryTimeAvg": 1.234567,
                "MySQLTotalExecutionCounts": 10,
                "MySQLTotalExecutionTimes": 2.345678,
                "ParseTotalRowCounts": 100,
                "ReturnTotalRowCounts": 10,
                "ParseRowAvg": 10.0,
                "ReturnRowAvg": 1.0,
            }
        ]

        data = {
            "instance_name": self.instance.instance_name,
            "StartTime": "2024-01-01",
            "EndTime": "2024-01-02",
            "db_name": "",
            "limit": 10,
            "offset": 0,
            "search": "",
            "sortName": "MySQLTotalExecutionCounts",
            "sortOrder": "desc",
        }
        r = self.client.post("/slowquery/review/", data=data)
        self.assertEqual(r.status_code, 200)
        resp = json.loads(r.content)
        self.assertEqual(resp["total"], 1)
        self.assertEqual(len(resp["rows"]), 1)
        self.assertEqual(resp["rows"][0]["SQLId"], "abc123")

    @patch("sql.slowlog.get_engine")
    @patch("sql.slowlog.AliyunRdsConfig.objects")
    def test_aliyun_rds(self, mock_rds_config_objects, mock_get_engine):
        """阿里云RDS慢查统计"""
        mock_rds_config_objects.filter.return_value.exists.return_value = True
        mock_engine = MagicMock()
        mock_engine.slowquery_review.return_value = {
            "total": 2,
            "rows": [{"SQLText": "SELECT 1"}],
        }
        mock_get_engine.return_value = mock_engine

        data = {
            "instance_name": self.instance.instance_name,
            "StartTime": "2024-01-01",
            "EndTime": "2024-01-02",
            "db_name": "",
            "limit": 10,
            "offset": 0,
        }
        r = self.client.post("/slowquery/review/", data=data)
        self.assertEqual(r.status_code, 200)
        resp = json.loads(r.content)
        self.assertEqual(resp["total"], 2)
        mock_engine.slowquery_review.assert_called_once()

    @patch("sql.slowlog.get_engine")
    @patch("sql.slowlog.RedisSlowQuery.objects")
    def test_redis(self, mock_redis_slow_query_objects, mock_get_engine):
        """Redis慢查统计"""
        redis_instance = Instance.objects.create(
            instance_name="test_redis",
            type="slave",
            db_type="redis",
            host="127.0.0.1",
            port=6379,
            user="",
            password="",
        )
        mock_engine = MagicMock()
        mock_engine.get_cluster_master_nodes.return_value = ["node1"]
        mock_get_engine.return_value = mock_engine

        mock_qs = MagicMock()
        mock_redis_slow_query_objects.filter.return_value = mock_qs
        mock_qs.annotate.return_value = mock_qs
        mock_qs.values.return_value = mock_qs
        mock_qs.count.return_value = 1
        mock_qs.order_by.return_value = [
            {
                "SQLText": "GET key",
                "SQLId": "redis123",
                "CreateTime": datetime.now(),
                "TotalExecutionCounts": 5,
                "TotalExecutionTimes": 1000000,
                "QueryTimeAvg": 200000.0,
                "DurationPct95": 300000.0,
            }
        ]

        data = {
            "instance_name": redis_instance.instance_name,
            "StartTime": "2024-01-01",
            "EndTime": "2024-01-02",
            "db_name": "",
            "limit": 10,
            "offset": 0,
            "search": "",
            "sortName": "TotalExecutionCounts",
            "sortOrder": "desc",
        }
        r = self.client.post("/slowquery/review/", data=data)
        self.assertEqual(r.status_code, 200)
        resp = json.loads(r.content)
        self.assertEqual(resp["total"], 1)
        self.assertEqual(len(resp["rows"]), 1)


class TestSlowQueryReviewHistory(TestCase):
    """测试 slowquery_review_history 视图"""

    def setUp(self):
        self.client = Client()
        self.user = Users.objects.create(
            username="test_user", display="测试用户", is_active=True
        )
        perm = Permission.objects.get(codename="menu_slowquery")
        self.user.user_permissions.add(perm)
        perm_all = Permission.objects.get(codename="query_all_instances")
        self.user.user_permissions.add(perm_all)
        self.client.force_login(self.user)

        self.instance = Instance.objects.create(
            instance_name="test_mysql",
            type="slave",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="root",
            password="password",
        )

    def tearDown(self):
        Users.objects.all().delete()
        Instance.objects.all().delete()
        ResourceGroup.objects.all().delete()
        AliyunRdsConfig.objects.all().delete()

    def test_instance_not_exist(self):
        """实例不存在时应返回错误"""
        data = {
            "instance_name": "not_exist",
            "StartTime": "2024-01-01",
            "EndTime": "2024-01-02",
            "db_name": "",
            "SQLId": "",
            "limit": 10,
            "offset": 0,
        }
        r = self.client.post("/slowquery/review_history/", data=data)
        self.assertEqual(r.status_code, 200)
        resp = r.json()
        self.assertEqual(resp["status"], 1)
        self.assertEqual(resp["msg"], "实例不存在")

    def test_no_permission(self):
        """用户没有实例权限时应返回错误"""
        self.user.user_permissions.remove(
            Permission.objects.get(codename="query_all_instances")
        )
        data = {
            "instance_name": self.instance.instance_name,
            "StartTime": "2024-01-01",
            "EndTime": "2024-01-02",
            "db_name": "",
            "SQLId": "",
            "limit": 10,
            "offset": 0,
        }
        r = self.client.post("/slowquery/review_history/", data=data)
        self.assertEqual(r.status_code, 200)
        resp = r.json()
        self.assertEqual(resp["status"], 1)
        self.assertEqual(resp["msg"], "你所在组未关联该实例")

    @patch("sql.slowlog.SlowQueryHistory.objects")
    def test_mysql_local(self, mock_slow_query_history_objects):
        """MySQL本地实例慢查明细"""
        mock_qs = MagicMock()
        mock_slow_query_history_objects.filter.return_value = mock_qs
        mock_qs.annotate.return_value = mock_qs
        mock_qs.count.return_value = 1
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__.return_value = mock_qs
        mock_qs.values.return_value = [
            {
                "ExecutionStartTime": datetime.now(),
                "DBName": "test_db",
                "HostAddress": "'user'@'localhost'",
                "SQLText": "SELECT * FROM t",
                "TotalExecutionCounts": 5,
                "QueryTimePct95": 1.234567,
                "QueryTimes": 2.345678,
                "LockTimes": 0.5,
                "ParseRowCounts": 100,
                "ReturnRowCounts": 10,
            }
        ]

        data = {
            "instance_name": self.instance.instance_name,
            "StartTime": "2024-01-01",
            "EndTime": "2024-01-02",
            "db_name": "",
            "SQLId": "",
            "limit": 10,
            "offset": 0,
            "search": "",
            "sortName": "ExecutionStartTime",
            "sortOrder": "desc",
        }
        r = self.client.post("/slowquery/review_history/", data=data)
        self.assertEqual(r.status_code, 200)
        resp = json.loads(r.content)
        self.assertEqual(resp["total"], 1)
        self.assertEqual(len(resp["rows"]), 1)
        self.assertEqual(resp["rows"][0]["DBName"], "test_db")

    @patch("sql.slowlog.get_engine")
    @patch("sql.slowlog.AliyunRdsConfig.objects")
    def test_aliyun_rds(self, mock_rds_config_objects, mock_get_engine):
        """阿里云RDS慢查明细"""
        mock_rds_config_objects.filter.return_value.exists.return_value = True
        mock_engine = MagicMock()
        mock_engine.slowquery_review_history.return_value = {
            "total": 2,
            "rows": [{"SQLText": "SELECT 1"}],
        }
        mock_get_engine.return_value = mock_engine

        data = {
            "instance_name": self.instance.instance_name,
            "StartTime": "2024-01-01",
            "EndTime": "2024-01-02",
            "db_name": "",
            "SQLId": "",
            "limit": 10,
            "offset": 0,
        }
        r = self.client.post("/slowquery/review_history/", data=data)
        self.assertEqual(r.status_code, 200)
        resp = json.loads(r.content)
        self.assertEqual(resp["total"], 2)
        mock_engine.slowquery_review_history.assert_called_once()

    @patch("sql.slowlog.get_engine")
    @patch("sql.slowlog.RedisSlowQueryHistory.objects")
    def test_redis(self, mock_redis_history_objects, mock_get_engine):
        """Redis慢查明细"""
        redis_instance = Instance.objects.create(
            instance_name="test_redis",
            type="slave",
            db_type="redis",
            host="127.0.0.1",
            port=6379,
            user="",
            password="",
        )
        mock_engine = MagicMock()
        mock_engine.get_cluster_master_nodes.return_value = ["node1"]
        mock_get_engine.return_value = mock_engine

        mock_qs = MagicMock()
        mock_redis_history_objects.filter.return_value = mock_qs
        mock_qs.annotate.return_value = mock_qs
        mock_qs.count.return_value = 1
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__.return_value = mock_qs
        mock_qs.values.return_value = [
            {
                "ExecutionStartTime": datetime.now(),
                "SQLText": "GET key",
                "TotalExecutionCounts": 5,
                "QueryTimePct95": 100000.0,
                "QueryTimes": 500000,
                "HostName": "node1",
            }
        ]

        data = {
            "instance_name": redis_instance.instance_name,
            "StartTime": "2024-01-01",
            "EndTime": "2024-01-02",
            "db_name": "",
            "SQLId": "",
            "limit": 10,
            "offset": 0,
            "search": "",
            "sortName": "ExecutionStartTime",
            "sortOrder": "desc",
        }
        r = self.client.post("/slowquery/review_history/", data=data)
        self.assertEqual(r.status_code, 200)
        resp = json.loads(r.content)
        self.assertEqual(resp["total"], 1)
        self.assertEqual(len(resp["rows"]), 1)


class TestSlowQueryReport(TestCase):
    """测试 report 视图"""

    def setUp(self):
        self.client = Client()
        self.user = Users.objects.create(
            username="test_user", display="测试用户", is_active=True
        )
        self.client.force_login(self.user)
        self.instance = Instance.objects.create(
            instance_name="test_mysql",
            type="slave",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="root",
            password="password",
        )

    def tearDown(self):
        Users.objects.all().delete()
        Instance.objects.all().delete()

    @patch("sql.slowlog.ChartDao")
    def test_report_mysql(self, mock_chart_dao_class):
        """MySQL慢查历史趋势"""
        mock_chart_dao = MagicMock()
        mock_chart_dao_class.return_value = mock_chart_dao
        mock_chart_dao.slow_query_review_history_by_cnt.return_value = {
            "rows": [(10, "2024-01-01"), (20, "2024-01-02")]
        }
        mock_chart_dao.slow_query_review_history_by_pct_95_time.return_value = {
            "rows": [(0.5, "2024-01-01"), (1.2, "2024-01-02")]
        }

        r = self.client.get(
            "/slowquery/report/",
            {"checksum": "abc123", "instance_name": self.instance.instance_name},
        )
        self.assertEqual(r.status_code, 200)
        resp = r.json()
        self.assertEqual(resp["status"], 0)
        self.assertIn("data", resp)
        mock_chart_dao.slow_query_review_history_by_cnt.assert_called_once_with(
            "abc123"
        )

    @patch("sql.slowlog.ChartDao")
    @patch("sql.slowlog.get_engine")
    def test_report_redis(self, mock_get_engine, mock_chart_dao_class):
        """Redis慢查历史趋势"""
        redis_instance = Instance.objects.create(
            instance_name="test_redis",
            type="slave",
            db_type="redis",
            host="127.0.0.1",
            port=6379,
            user="",
            password="",
        )
        mock_engine = MagicMock()
        mock_engine.get_cluster_master_nodes.return_value = ["node1", "node2"]
        mock_get_engine.return_value = mock_engine

        mock_chart_dao = MagicMock()
        mock_chart_dao_class.return_value = mock_chart_dao
        mock_chart_dao.redis_slow_query_review_history_by_cnt.return_value = {
            "rows": [(5, "2024-01-01")]
        }
        mock_chart_dao.redis_slow_query_review_history_by_pct_95_time.return_value = {
            "rows": [(100000, "2024-01-01")]
        }

        r = self.client.get(
            "/slowquery/report/",
            {"checksum": "redis123", "instance_name": redis_instance.instance_name},
        )
        self.assertEqual(r.status_code, 200)
        resp = r.json()
        self.assertEqual(resp["status"], 0)
        mock_chart_dao.redis_slow_query_review_history_by_cnt.assert_called_once_with(
            "redis123", ["node1", "node2"]
        )

    @patch("sql.slowlog.ChartDao")
    def test_report_no_instance(self, mock_chart_dao_class):
        """无实例参数时使用MySQL默认逻辑"""
        mock_chart_dao = MagicMock()
        mock_chart_dao_class.return_value = mock_chart_dao
        mock_chart_dao.slow_query_review_history_by_cnt.return_value = {
            "rows": [(10, "2024-01-01")]
        }
        mock_chart_dao.slow_query_review_history_by_pct_95_time.return_value = {
            "rows": [(0.5, "2024-01-01")]
        }

        r = self.client.get("/slowquery/report/", {"checksum": "abc123"})
        self.assertEqual(r.status_code, 200)
        resp = r.json()
        self.assertEqual(resp["status"], 0)
        mock_chart_dao.slow_query_review_history_by_cnt.assert_called_once_with(
            "abc123"
        )
