import json
import unittest
from unittest.mock import patch, Mock
from sql.engines import ResultSet, ReviewSet
from sql.engines.elasticsearch import OpenSearchEngine
from sql.models import Instance


class TestOpenSearchEngine(unittest.TestCase):
    def setUp(self):
        # 创建一个模拟的 instance 对象，包含必要的属性
        self.mock_instance = Instance()
        self.mock_instance.host = "localhost"
        self.mock_instance.port = 9200
        self.mock_instance.user = "user"
        self.mock_instance.password = "pass"
        self.mock_instance.is_ssl = True

        # 初始化 OpenSearchEngine
        self.engine = OpenSearchEngine(instance=self.mock_instance)

    @patch("sql.engines.elasticsearch.OpenSearch")
    def test_get_all_databases(self, mockElasticsearch):
        mock_conn = Mock()
        mock_conn.indices.get_alias.return_value = {
            "test__index1": {},
            "test__index2": {},
            ".kibana_2": {},
            ".internal.index": {},
        }
        mockElasticsearch.return_value = mock_conn

        result = self.engine.get_all_databases()
        expected_result = [
            "other",
            "system",
            "test",
        ]
        self.assertEqual(result.rows, expected_result)

    @patch("sql.engines.elasticsearch.OpenSearch")
    def test_query_sql(self, mockElasticsearch):
        """SQL语句测试"""
        mock_conn = Mock()
        mock_response = {
            "schema": [
                {"name": "field1", "type": "text"},
                {"name": "field2", "type": "integer"},
                {"name": "field3", "type": "array"},
            ],
            "datarows": [
                ["value1", 10, ["elem1", "elem2"]],
                ["value2", 20, ["elem3", "elem4"]],
            ],
        }
        mock_conn.transport.perform_request.return_value = mock_response
        mockElasticsearch.return_value = mock_conn

        sql = "SELECT field1, field2, field3 FROM test_index"
        result = self.engine.query(sql=sql, db_name="")
        expected_rows = [
            ["value1", 10, json.dumps(["elem1", "elem2"])],
            ["value2", 20, json.dumps(["elem3", "elem4"])],
        ]
        expected_columns = ["field1", "field2", "field3"]
        self.assertEqual(result.rows, expected_rows)
        self.assertEqual(result.column_list, expected_columns)

    @patch("sql.engines.elasticsearch.OpenSearch")
    def test_security_role(self, mockElasticsearch):
        """测试 _security_role 方法"""
        mock_conn = Mock()
        mockElasticsearch.return_value = mock_conn

        # 模拟 OpenSearch 返回的角色信息
        mock_response = {
            "kibana_user": {
                "reserved": True,
                "hidden": False,
                "description": "Provide the minimum permissions for a kibana user",
                "cluster_permissions": ["cluster_composite_ops"],
                "index_permissions": [
                    {
                        "index_patterns": [".kibana", ".kibana-6", ".kibana_*"],
                        "fls": [],
                        "masked_fields": [],
                        "allowed_actions": ["read", "delete", "manage", "index"],
                    },
                    {
                        "index_patterns": [
                            ".tasks",
                            ".management-beats",
                            "*:.tasks",
                            "*:.management-beats",
                        ],
                        "fls": [],
                        "masked_fields": [],
                        "allowed_actions": ["indices_all"],
                    },
                ],
                "tenant_permissions": [],
                "static": True,
            },
            "all_access": {
                "reserved": True,
                "hidden": False,
                "description": "Allow full access to all indices and all cluster APIs",
                "cluster_permissions": ["*"],
                "index_permissions": [],
                "tenant_permissions": [],
                "static": False,
            },
        }
        mock_conn.transport.perform_request.return_value = mock_response

        sql = "GET /_security/roles"
        result_set = self.engine.query(sql=sql, db_name="")

        expected_columns = [
            "role_name",
            "reserved",
            "hidden",
            "description",
            "cluster_permissions",
            "index_permissions",
            "tenant_permissions",
            "static",
        ]
        expected_rows = [
            [
                "kibana_user",
                True,
                False,
                "Provide the minimum permissions for a kibana user",
                json.dumps(["cluster_composite_ops"]),
                json.dumps(
                    [
                        {
                            "index_patterns": [".kibana", ".kibana-6", ".kibana_*"],
                            "fls": [],
                            "masked_fields": [],
                            "allowed_actions": ["read", "delete", "manage", "index"],
                        },
                        {
                            "index_patterns": [
                                ".tasks",
                                ".management-beats",
                                "*:.tasks",
                                "*:.management-beats",
                            ],
                            "fls": [],
                            "masked_fields": [],
                            "allowed_actions": ["indices_all"],
                        },
                    ]
                ),
                json.dumps([]),
                True,
            ],
            [
                "all_access",
                True,
                False,
                "Allow full access to all indices and all cluster APIs",
                json.dumps(["*"]),
                json.dumps([]),
                json.dumps([]),
                False,
            ],
        ]

        self.assertEqual(result_set.column_list, expected_columns)
        self.assertEqual(result_set.rows, expected_rows)

    @patch("sql.engines.elasticsearch.OpenSearch")
    def test_security_user(self, mockElasticsearch):
        """测试 _security_user 方法"""
        mock_conn = Mock()
        mockElasticsearch.return_value = mock_conn

        # 模拟 OpenSearch 返回的用户信息
        mock_response = {
            "admin": {
                "hash": "abc123hash",
                "reserved": True,
                "hidden": False,
                "backend_roles": ["role1", "role2"],
                "attributes": {"attr1": "value1", "attr2": "value2"},
                "opendistro_security_roles": ["kibana_user", "own_index"],
                "static": True,
            },
            "user2": {
                "hash": "def456hash",
                "reserved": False,
                "hidden": True,
                "backend_roles": ["role3"],
                "attributes": {},
                "opendistro_security_roles": ["alerting_full_access"],
                "static": False,
            },
        }
        mock_conn.transport.perform_request.return_value = mock_response

        sql = "GET /_security/user"
        result_set = self.engine.query(sql=sql, db_name="")

        expected_columns = [
            "user_name",
            "hash",
            "reserved",
            "hidden",
            "backend_roles",
            "attributes",
            "opendistro_security_roles",
            "static",
        ]
        expected_rows = [
            [
                "admin",
                "abc123hash",
                True,
                False,
                json.dumps(["role1", "role2"]),
                json.dumps({"attr1": "value1", "attr2": "value2"}),
                json.dumps(["kibana_user", "own_index"]),
                True,
            ],
            [
                "user2",
                "def456hash",
                False,
                True,
                json.dumps(["role3"]),
                json.dumps({}),
                json.dumps(["alerting_full_access"]),
                False,
            ],
        ]
        self.assertEqual(result_set.column_list, expected_columns)
        self.assertEqual(result_set.rows, expected_rows)
