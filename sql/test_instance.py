# -*- coding: UTF-8 -*-
import json
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from sql.models import Instance, ParamTemplate, ParamHistory

User = get_user_model()


class TestInstance(TestCase):
    """测试实例管理功能"""

    def setUp(self):
        """初始化测试环境"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="test_user",
            password="test_password",
            display="测试用户",
            is_active=True,
        )
        self.superuser = User.objects.create_superuser(
            username="admin",
            password="admin_password",
            display="管理员",
            is_active=True,
        )

    def tearDown(self):
        """清理测试数据"""
        User.objects.all().delete()
        Instance.objects.all().delete()
        ParamTemplate.objects.all().delete()
        ParamHistory.objects.all().delete()

    def test_instance_lists_success(self):
        """测试成功获取实例列表"""
        # 创建测试实例
        Instance.objects.create(
            instance_name="test_mysql",
            type="master",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="root",
            password="password",
        )
        Instance.objects.create(
            instance_name="test_postgres",
            type="slave",
            db_type="pgsql",
            host="127.0.0.1",
            port=5432,
            user="postgres",
            password="password",
        )

        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="menu_instance_list",
            name="Can view instance list",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:instance_list"),
            {
                "limit": 10,
                "offset": 0,
                "type": "",
                "db_type": "",
                "sortName": "instance_name",
                "sortOrder": "asc",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["rows"]), 2)

    def test_instance_lists_filter_by_type(self):
        """测试按类型过滤实例列表"""
        # 创建测试实例
        Instance.objects.create(
            instance_name="test_master",
            type="master",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="root",
            password="password",
        )
        Instance.objects.create(
            instance_name="test_slave",
            type="slave",
            db_type="mysql",
            host="127.0.0.1",
            port=3307,
            user="root",
            password="password",
        )

        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="menu_instance_list",
            name="Can view instance list",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:instance_list"),
            {
                "limit": 10,
                "offset": 0,
                "type": "master",
                "db_type": "",
                "sortName": "instance_name",
                "sortOrder": "asc",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["rows"][0]["type"], "master")

    def test_instance_lists_filter_by_db_type(self):
        """测试按数据库类型过滤实例列表"""
        # 创建测试实例
        Instance.objects.create(
            instance_name="test_mysql",
            type="master",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="root",
            password="password",
        )
        Instance.objects.create(
            instance_name="test_postgres",
            type="master",
            db_type="pgsql",
            host="127.0.0.1",
            port=5432,
            user="postgres",
            password="password",
        )

        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="menu_instance_list",
            name="Can view instance list",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:instance_list"),
            {
                "limit": 10,
                "offset": 0,
                "type": "",
                "db_type": "mysql",
                "sortName": "instance_name",
                "sortOrder": "asc",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["rows"][0]["db_type"], "mysql")

    def test_instance_lists_search(self):
        """测试搜索实例"""
        # 创建测试实例
        Instance.objects.create(
            instance_name="production_mysql",
            type="master",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="root",
            password="password",
        )
        Instance.objects.create(
            instance_name="development_mysql",
            type="slave",
            db_type="mysql",
            host="127.0.0.1",
            port=3307,
            user="root",
            password="password",
        )

        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="menu_instance_list",
            name="Can view instance list",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:instance_list"),
            {
                "limit": 10,
                "offset": 0,
                "type": "",
                "db_type": "",
                "search": "production",
                "sortName": "instance_name",
                "sortOrder": "asc",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)
        self.assertIn("production", data["rows"][0]["instance_name"])

    def test_instance_lists_pagination(self):
        """测试实例列表分页"""
        # 创建多个测试实例
        for i in range(5):
            Instance.objects.create(
                instance_name=f"test_instance_{i}",
                type="master",
                db_type="mysql",
                host="127.0.0.1",
                port=3306 + i,
                user="root",
                password="password",
            )

        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="menu_instance_list",
            name="Can view instance list",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:instance_list"),
            {
                "limit": 2,
                "offset": 0,
                "type": "",
                "db_type": "",
                "sortName": "instance_name",
                "sortOrder": "asc",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 5)
        self.assertEqual(len(data["rows"]), 2)

    def test_param_list_success(self):
        """测试成功获取实例参数列表"""
        # 创建测试实例
        instance = Instance.objects.create(
            instance_name="test_mysql",
            type="master",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="root",
            password="password",
        )

        # 创建参数模板
        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="max_connections",
            default_value="151",
            valid_values="1-100000",
            description="最大连接数",
            editable=True,
        )
        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="innodb_buffer_pool_size",
            default_value="134217728",
            valid_values="5242880-",
            description="InnoDB缓冲池大小",
            editable=True,
        )

        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="param_view",
            name="Can view params",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:param_list"),
            {
                "instance_id": instance.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 0)

    def test_param_list_instance_not_found(self):
        """测试实例不存在时获取参数列表"""
        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="param_view",
            name="Can view params",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:param_list"),
            {
                "instance_id": 99999,  # 不存在的实例ID
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 1)
        self.assertIn("不存在", data["msg"])

    def test_param_list_search(self):
        """测试搜索实例参数"""
        # 创建测试实例
        instance = Instance.objects.create(
            instance_name="test_mysql",
            type="master",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="root",
            password="password",
        )

        # 创建参数模板
        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="max_connections",
            default_value="151",
            valid_values="1-100000",
            description="最大连接数",
            editable=True,
        )
        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="innodb_buffer_pool_size",
            default_value="134217728",
            valid_values="5242880-",
            description="InnoDB缓冲池大小",
            editable=True,
        )

        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="param_view",
            name="Can view params",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:param_list"),
            {
                "instance_id": instance.id,
                "search": "max_connections",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 0)

    def test_param_list_editable_only(self):
        """测试只获取可编辑参数"""
        # 创建测试实例
        instance = Instance.objects.create(
            instance_name="test_mysql",
            type="master",
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            user="root",
            password="password",
        )

        # 创建参数模板
        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="max_connections",
            default_value="151",
            valid_values="1-100000",
            description="最大连接数",
            editable=True,
        )
        ParamTemplate.objects.create(
            db_type="mysql",
            variable_name="version",
            default_value="8.0.28",
            valid_values="",
            description="数据库版本",
            editable=False,
        )

        # 赋予权限
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Instance)
        permission = Permission.objects.create(
            codename="param_view",
            name="Can view params",
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sql:param_list"),
            {
                "instance_id": instance.id,
                "editable": "true",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], 0)
