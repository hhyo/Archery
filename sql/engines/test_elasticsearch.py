import json
import unittest
from unittest.mock import patch, Mock
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import TransportError
from sql.engines import ResultSet, ReviewSet
from sql.engines.elasticsearch import ElasticsearchEngine
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
                    {
                        "_id": "1",
                        "_source": {"field1": "value1", "field2": ["val1", "val2"]},
                    },
                    {
                        "_id": "2",
                        "_source": {
                            "field1": {"subfield": "value3"},
                            "field2": "value4",
                        },
                    },
                ]
            }
        }
        mockElasticsearch.return_value = mock_conn

        sql = "GET /test_index/_search"
        result = self.engine.query(sql=sql)
        expected_rows = [
            ("1", "value1", json.dumps(["val1", "val2"])),
            ("2", json.dumps({"subfield": "value3"}), "value4"),
        ]
        self.assertEqual(result.rows, expected_rows)
        self.assertEqual(result.column_list, ["_id", "field1", "field2"])

    @patch("sql.engines.elasticsearch.Elasticsearch")
    def test_query_sql(self, mockElasticsearch):
        """SQL语句测试"""
        mock_conn = Mock()
        mock_response = {
            "columns": [
                {"name": "field1", "type": "text"},
                {"name": "field2", "type": "integer"},
                {"name": "field3", "type": "array"},
            ],
            "rows": [
                ["value1", 10, ["elem1", "elem2"]],
                ["value2", 20, ["elem3", "elem4"]],
            ],
        }
        mock_conn.sql.query.return_value = mock_response
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

    @patch("sql.engines.elasticsearch.Elasticsearch")
    def test_query_cat_indices(self, mock_elasticsearch):
        """test_query_cat_indices"""
        mock_conn = Mock()
        mock_elasticsearch.return_value = mock_conn
        mock_response = Mock()
        mock_response.body = "health status index      uuid                   pri rep docs.count docs.deleted store.size pri.store.size dataset.size\nyellow open   test__index     3yyJqzgHTJqRkKwhT5Fy7w   3   1      34256            0      4.4mb          4.4mb        4.4mb\nyellow open   dmp__iv    fzK3nKcpRNunVr5N6gOSsw   3   1        903            0    527.1kb        527.1kb      527.1kb\n"
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

    @patch("sql.engines.elasticsearch.Elasticsearch")
    def test_get_all_columns_by_tb(self, mock_elasticsearch):
        """测试获取表字段"""

        mock_conn = Mock()
        mock_elasticsearch.return_value = mock_conn

        mock_mapping = {
            "mappings": {
                "properties": {
                    "field1": {"type": "text"},
                    "field2": {"type": "keyword"},
                    "field3": {"type": "integer"},
                }
            }
        }

        mock_conn.indices.get_mapping.return_value = {"test_table": mock_mapping}

        result = self.engine.get_all_columns_by_tb(
            db_name="test_db", tb_name="test_table"
        )

        expected_columns = ["column_name"]
        expected_rows = ["field1", "field2", "field3"]

        self.assertEqual(result.column_list, expected_columns)
        self.assertEqual(result.rows, expected_rows)

    @patch("sql.engines.elasticsearch.Elasticsearch")
    def test_describe_table(self, mock_elasticsearch):
        """测试表结构"""

        mock_conn = Mock()
        mock_elasticsearch.return_value = mock_conn

        mock_mapping = {
            "mappings": {
                "properties": {
                    "field1": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "field2": {"type": "integer"},
                    "field3": {"type": "date"},
                }
            }
        }
        mock_conn.indices.get_mapping.return_value = {"test_table": mock_mapping}

        result = self.engine.describe_table(db_name="test_db", tb_name="test_table")

        expected_columns = ["column_name", "type", "fields"]
        expected_rows = [
            ("field1", "text", json.dumps({"keyword": {"type": "keyword"}})),
            ("field2", "integer", "{}"),
            ("field3", "date", "{}"),
        ]

        # Assertions
        self.assertEqual(result.column_list, expected_columns)
        self.assertEqual(result.rows, expected_rows)

    def test_query_check(self):
        valid_sql = "GET /test_index/_search"
        result = self.engine.query_check(sql=valid_sql)
        self.assertFalse(result["bad_query"])

        invalid_sql = "PUT /test_index/_doc/1"
        result = self.engine.query_check(sql=invalid_sql)
        self.assertTrue(result["bad_query"])

    def test_query_check_valid_select(self):
        """测试有效的 SELECT 语句"""
        valid_select_sql = "SELECT * FROM test_table"
        result = self.engine.query_check(sql=valid_select_sql)
        self.assertFalse(result["bad_query"])
        self.assertEqual(result["filtered_sql"], "SELECT * FROM test_table")

    def test_query_check_valid_select_with_comments(self):
        """测试有注释的 SELECT 语句"""
        valid_select_sql_with_comments = "SELECT * FROM test_table -- 注释"
        result = self.engine.query_check(sql=valid_select_sql_with_comments)
        self.assertFalse(result["bad_query"])
        self.assertEqual(result["filtered_sql"], "SELECT * FROM test_table")

    def test_filter_sql_with_delimiter(self):
            new_engine = self.engine
            sql_without_limit = "select user from usertable;"
            check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=100)
            self.assertEqual(check_result, "select user from usertable limit 100;")

    def test_filter_sql_without_delimiter(self):
        new_engine = self.engine
        sql_without_limit = "select user from usertable"
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=100)
        self.assertEqual(check_result, "select user from usertable limit 100;")

    def test_filter_sql_with_limit(self):
        new_engine = self.engine
        sql_without_limit = "select user from usertable limit 10"
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, "select user from usertable limit 1;")

    def test_filter_sql_with_limit_min(self):
        new_engine = self.engine
        sql_without_limit = "select user from usertable limit 10"
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=100)
        self.assertEqual(check_result, "select user from usertable limit 10;")

    def test_filter_sql_with_limit_offset(self):
        new_engine = self.engine
        sql_without_limit = "select user from usertable limit 10 offset 100"
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, "select user from usertable limit 1 offset 100;")

    def test_filter_sql_with_limit_nn(self):
        new_engine = self.engine
        sql_without_limit = "select user from usertable limit 10, 100"
        check_result = new_engine.filter_sql(sql=sql_without_limit, limit_num=1)
        self.assertEqual(check_result, "select user from usertable limit 10,1;")
