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
