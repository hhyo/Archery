# -*- coding: UTF-8 -*-
import json
from unittest.mock import patch, MagicMock
import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from sql.engines.models import ResultSet
from sql.models import Instance, SlowQuery, SlowQueryHistory, AliyunRdsConfig

User = get_user_model()


class TestSlowlog(TestCase):
    """测试慢查询日志功能"""

    def setUp(self):
        """初始化测试环境"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="test_user",
            password="test_password",
            display="测试用户",
            is_active=True,
        )
        self.instance = Instance.objects.create(
            instance_name="test_mysql",
            type="master",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="root",
            password="password",
        )

    def tearDown(self):
        """清理测试数据"""
        User.objects.all().delete()
        Instance.objects.all().delete()
        SlowQuery.objects.all().delete()
        SlowQueryHistory.objects.all().delete()
        AliyunRdsConfig.objects.all().delete()

    @patch("sql.slowlog.user_instances")
    def test_slowquery_review_instance_not_found(self, mock_user_instances):
        """测试实例不存在或无权限"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="menu_slowquery",
            name="Can view slowquery",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances to raise exception
        mock_user_instances.return_value.get.side_effect = Instance.DoesNotExist

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:slowquery_review"),
            {
                "instance_name": "test_mysql",
                "StartTime": "2024-01-01",
                "EndTime": "2024-01-07",
                "db_name": "test_db",
                "limit": 10,
                "offset": 0,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("未关联该实例", data["msg"])

    @patch("sql.slowlog.user_instances")
    @patch("sql.slowlog.get_engine")
    @patch("sql.slowlog.AliyunRdsConfig")
    def test_slowquery_review_aliyun_rds(
        self, mock_aliyun_config, mock_get_engine, mock_user_instances
    ):
        """测试阿里云RDS慢查询"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="menu_slowquery",
            name="Can view slowquery",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock AliyunRdsConfig to indicate this is RDS instance
        mock_aliyun_config.objects.filter.return_value.exists.return_value = True

        # Mock query engine
        mock_engine = MagicMock()
        mock_engine.slowquery_review.return_value = {
            "status": 0,
            "msg": "ok",
            "data": {
                "total": 1,
                "rows": [
                    {
                        "SQLText": "SELECT * FROM test_table WHERE id = ?",
                        "MySQLTotalExecutionCounts": 10,
                        "QueryTimeAvg": 2.5,
                    }
                ],
            },
        }
        mock_get_engine.return_value = mock_engine

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:slowquery_review"),
            {
                "instance_name": "test_mysql",
                "StartTime": "2024-01-01",
                "EndTime": "2024-01-07",
                "db_name": "test_db",
                "limit": 10,
                "offset": 0,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 0)

    @patch("sql.slowlog.user_instances")
    @patch("sql.slowlog.AliyunRdsConfig")
    def test_slowquery_review_local_instance(
        self, mock_aliyun_config, mock_user_instances
    ):
        """测试本地实例慢查询"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="menu_slowquery",
            name="Can view slowquery",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock AliyunRdsConfig to indicate this is NOT RDS instance
        mock_aliyun_config.objects.filter.return_value.exists.return_value = False

        # 创建慢查询测试数据
        slow_query = SlowQuery.objects.create(
            checksum="abc123",
            fingerprint="SELECT * FROM test_table WHERE id = ?",
            sample="SELECT * FROM test_table WHERE id = 1",
        )
        SlowQueryHistory.objects.create(
            checksum_id=slow_query.checksum,
            hostname_max=f"{self.instance.host}:{self.instance.port}",
            db_max="test_db",
            ts_min=datetime.datetime(2024, 1, 1),
            ts_max=datetime.datetime(2024, 1, 2),
            ts_cnt=10,
            query_time_sum=25.0,
            rows_examined_sum=1000,
            rows_sent_sum=100,
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:slowquery_review"),
            {
                "instance_name": "test_mysql",
                "StartTime": "2024-01-01",
                "EndTime": "2024-01-07",
                "db_name": "test_db",
                "limit": 10,
                "offset": 0,
                "search": "",
                "sortName": "MySQLTotalExecutionCounts",
                "sortOrder": "desc",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 0)
        self.assertGreaterEqual(data["total"], 1)

    @patch("sql.slowlog.user_instances")
    @patch("sql.slowlog.AliyunRdsConfig")
    def test_slowquery_review_with_search(
        self, mock_aliyun_config, mock_user_instances
    ):
        """测试搜索慢查询"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="menu_slowquery",
            name="Can view slowquery",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock AliyunRdsConfig
        mock_aliyun_config.objects.filter.return_value.exists.return_value = False

        # 创建慢查询测试数据
        slow_query1 = SlowQuery.objects.create(
            checksum="abc123",
            fingerprint="SELECT * FROM users WHERE id = ?",
            sample="SELECT * FROM users WHERE id = 1",
        )
        slow_query2 = SlowQuery.objects.create(
            checksum="def456",
            fingerprint="SELECT * FROM orders WHERE user_id = ?",
            sample="SELECT * FROM orders WHERE user_id = 1",
        )
        
        for sq in [slow_query1, slow_query2]:
            SlowQueryHistory.objects.create(
                checksum_id=sq.checksum,
                hostname_max=f"{self.instance.host}:{self.instance.port}",
                db_max="test_db",
                ts_min=datetime.datetime(2024, 1, 1),
                ts_max=datetime.datetime(2024, 1, 2),
                ts_cnt=10,
                query_time_sum=25.0,
                rows_examined_sum=1000,
                rows_sent_sum=100,
            )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:slowquery_review"),
            {
                "instance_name": "test_mysql",
                "StartTime": "2024-01-01",
                "EndTime": "2024-01-07",
                "db_name": "test_db",
                "limit": 10,
                "offset": 0,
                "search": "users",  # 搜索包含users的SQL
                "sortName": "MySQLTotalExecutionCounts",
                "sortOrder": "desc",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        # 应该只返回包含users的慢查询
        self.assertEqual(data["status"], 0)

    @patch("sql.slowlog.user_instances")
    @patch("sql.slowlog.AliyunRdsConfig")
    def test_slowquery_review_pagination(
        self, mock_aliyun_config, mock_user_instances
    ):
        """测试慢查询分页"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="menu_slowquery",
            name="Can view slowquery",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        # Mock user_instances
        mock_user_instances.return_value.get.return_value = self.instance

        # Mock AliyunRdsConfig
        mock_aliyun_config.objects.filter.return_value.exists.return_value = False

        # 创建多条慢查询测试数据
        for i in range(5):
            slow_query = SlowQuery.objects.create(
                checksum=f"checksum_{i}",
                fingerprint=f"SELECT * FROM table_{i} WHERE id = ?",
                sample=f"SELECT * FROM table_{i} WHERE id = 1",
            )
            SlowQueryHistory.objects.create(
                checksum_id=slow_query.checksum,
                hostname_max=f"{self.instance.host}:{self.instance.port}",
                db_max="test_db",
                ts_min=datetime.datetime(2024, 1, 1),
                ts_max=datetime.datetime(2024, 1, 2),
                ts_cnt=10 + i,
                query_time_sum=25.0 + i,
                rows_examined_sum=1000 + i,
                rows_sent_sum=100 + i,
            )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:slowquery_review"),
            {
                "instance_name": "test_mysql",
                "StartTime": "2024-01-01",
                "EndTime": "2024-01-07",
                "db_name": "test_db",
                "limit": 2,  # 每页2条
                "offset": 0,  # 第一页
                "search": "",
                "sortName": "MySQLTotalExecutionCounts",
                "sortOrder": "desc",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 0)
        self.assertEqual(data["total"], 5)
        self.assertEqual(len(data["rows"]), 2)
