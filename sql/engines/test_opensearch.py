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
            "system_internal",
            "system_kibana",
            "test",
        ]
        self.assertEqual(result.rows, expected_result)
