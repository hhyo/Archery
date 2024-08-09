import unittest
from unittest.mock import patch, Mock
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import TransportError
from sql.engines import ResultSet, ReviewSet
from sql.engines.elasticsearch import ElasticsearchEngine, QueryParamsEs
from sql.models import Instance


class TestElasticsearchEngine(unittest.TestCase):
    def setUp(self):
        # 创建一个模拟的 instance 对象，包含必要的属性
        self.mock_instance = Instance()
        self.mock_instance.host = "localhost"
        self.mock_instance.port = 9200
        self.mock_instance.user = "user"
        self.mock_instance.password = "pass"
        self.mock_instance.is_ssl = True

        # 初始化 ElasticsearchEngine，传入模拟的 instance
        self.engine = ElasticsearchEngine(instance=self.mock_instance)

    @patch("sql.engines.elasticsearch.Elasticsearch")
    def test_get_all_databases(self, mockElasticsearch):
        mock_conn = Mock()
        mock_conn.indices.get_alias.return_value = {
            "test__index1": {},
            "test__index2": {},
            ".kibana_1": {},
            ".internal.index": {},
        }
        mockElasticsearch.return_value = mock_conn

        result = self.engine.get_all_databases()
        expected_result = [
            "other",
            "system",
            "system_internal",
            "system_kibana",
            "test",
        ]
        self.assertEqual(result.rows, expected_result)

    @patch("sql.engines.elasticsearch.Elasticsearch")
    def test_get_all_tables(self, mockElasticsearch):
        mock_conn = Mock()
        mock_conn.indices.get_alias.return_value = {
            "test__index1": {},
            "test__index2": {},
            "other_index": {},
            ".kibana_1": {},
        }
        mockElasticsearch.return_value = mock_conn

        # Test specific database
        result = self.engine.get_all_tables(db_name="test")
        self.assertEqual(result.rows, ["test__index1", "test__index2"])

        # Test system_kibana
        result = self.engine.get_all_tables(db_name="system_kibana")
        self.assertEqual(result.rows, [".kibana_1"])

    @patch("sql.engines.elasticsearch.Elasticsearch")
    def test_query(self, mockElasticsearch):
        mock_conn = Mock()
        mock_conn.search.return_value = {
            "hits": {
                "hits": [
                    {"_id": "1", "_source": {"field1": "value1", "field2": "value2"}},
                    {"_id": "2", "_source": {"field1": "value3", "field2": "value4"}},
                ]
            }
        }
        mockElasticsearch.return_value = mock_conn

        sql = "GET /test_index/_search"
        result = self.engine.query(sql=sql)
        expected_rows = [("1", "value1", "value2"), ("2", "value3", "value4")]
        self.assertEqual(result.rows, expected_rows)
        self.assertEqual(result.column_list, ["_id", "field1", "field2"])

    def test_query_check(self):
        valid_sql = "GET /test_index/_search"
        result = self.engine.query_check(sql=valid_sql)
        self.assertFalse(result["bad_query"])

        invalid_sql = "PUT /test_index/_doc/1"
        result = self.engine.query_check(sql=invalid_sql)
        self.assertTrue(result["bad_query"])
