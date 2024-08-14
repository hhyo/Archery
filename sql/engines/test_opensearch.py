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

        # 初始化 OpenSearchEngine instance
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

    @patch("sql.engines.elasticsearch.OpenSearch")
    def test_query_cat_indices(self, mock_elasticsearch):
        """test_query_cat_indices
        OpenSearch cat_indices方法返回的str对象
        """
        mock_conn = Mock()
        mock_elasticsearch.return_value = mock_conn
        mock_response = Mock()
        mock_response = "health status index      uuid                   pri rep docs.count docs.deleted store.size pri.store.size dataset.size\nyellow open   test__index     3yyJqzgHTJqRkKwhT5Fy7w   3   1      34256            0      4.4mb          4.4mb        4.4mb\nyellow open   dmp__iv    fzK3nKcpRNunVr5N6gOSsw   3   1        903            0    527.1kb        527.1kb      527.1kb\n"
        mock_conn.cat.indices.return_value = mock_response

        sql = "GET /_cat/indices/*?v&s=docs.count:desc"

        # 执行测试的方法
        result = self.engine.query(sql=sql)

        # 验证结果
        expected_columns = [
            "health",
            "status",
            "index",
            "uuid",
            "pri",
            "rep",
            "docs.count",
            "docs.deleted",
            "store.size",
            "pri.store.size",
            "dataset.size",
        ]
        expected_rows = [
            (
                "yellow",
                "open",
                "test__index",
                "3yyJqzgHTJqRkKwhT5Fy7w",
                "3",
                "1",
                "34256",
                "0",
                "4.4mb",
                "4.4mb",
                "4.4mb",
            ),
            (
                "yellow",
                "open",
                "dmp__iv",
                "fzK3nKcpRNunVr5N6gOSsw",
                "3",
                "1",
                "903",
                "0",
                "527.1kb",
                "527.1kb",
                "527.1kb",
            ),
        ]
        self.assertEqual(result.column_list, expected_columns)
        self.assertEqual(result.rows, expected_rows)
