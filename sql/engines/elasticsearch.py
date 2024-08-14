# -*- coding: UTF-8 -*-
import logging
import re
import traceback
from opensearchpy import OpenSearch
import simplejson as json
from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult
from common.config import SysConfig
import logging

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import TransportError


logger = logging.getLogger("default")


class QueryParamsSearch:
    def __init__(
        self,
        index: str,
        path: str,
        params: str,
        method: str,
        size: int,
        query_body: dict = None,
    ):
        self.index = index
        self.path = path
        self.params = params
        self.method = method
        self.size = size
        # 确保 query_body 不为 None
        self.query_body = query_body if query_body is not None else {}


class ElasticsearchEngineBase(EngineBase):
    """Elasticsearch、OpenSearch等Search父类实现"""

    def __init__(self, instance=None):
        self.db_separator = "__"  # 设置分隔符
        # 限制只能2种支持的子类
        self.search_name = ["Elasticsearch", "OpenSearch"]
        if self.name not in self.search_name:
            raise ValueError(
                f"Invalid name: {self.name}. Must be one of {self.search_name}."
            )
        super().__init__(instance=instance)

    def get_connection(self, db_name=None):
        """返回一个conn实例"""

    def test_connection(self):
        """测试实例链接是否正常"""
        return self.get_all_databases()

    name: str = "SearchBase"
    info: str = "SearchBase 引擎"

    def get_all_databases(self):
        """获取所有“数据库”名（从索引名提取）,默认提取 __ 前的部分作为数据库名"""
        try:
            self.get_connection()
            # 获取所有的别名，没有别名就是本身。
            indices = self.conn.indices.get_alias(index=self.db_name)
            database_names = set()
            if self.db_name == "*":
                database_names.add("system")  # 系统表名使用的库名
            for index_name in indices.keys():
                if self.db_separator in index_name:
                    db_name = index_name.split(self.db_separator)[0]
                    database_names.add(db_name)
                elif index_name.startswith(".kibana_"):
                    database_names.add("system_kibana")
                elif index_name.startswith(".internal."):
                    database_names.add("system_internal")
            database_names.add("other")  # 表名没有__时，使用的库名
            database_names_sorted = sorted(database_names)
            return ResultSet(rows=database_names_sorted)
        except Exception as e:
            logger.error(f"获取数据库时出错:{e}{traceback.format_exc()}")
            raise Exception(f"获取数据库时出错: {str(e)}")

    def get_all_tables(self, db_name, **kwargs):
        """根据给定的数据库名获取所有相关的表名"""
        try:
            self.get_connection()
            indices = self.conn.indices.get_alias(index=self.db_name)
            tables = set()

            db_mapping = {
                "system_kibana": ".kibana_",
                "system_internal": ".internal.",
                "system": ".",
                "other": "other",
            }
            # 根据分隔符分隔的库名
            if db_name not in db_mapping:
                index_prefix = db_name.rstrip(self.db_separator) + self.db_separator
                tables = [
                    index for index in indices.keys() if index.startswith(index_prefix)
                ]
            else:
                # 处理系统表，和other，循环db_mapping.items() 很难实现。
                for index_name in indices.keys():
                    if index_name.startswith(".kibana_") | index_name.startswith(
                        ".kibana-"
                    ):
                        if db_name == "system_kibana":
                            tables.add(index_name)
                        continue
                    elif index_name.startswith(".internal."):
                        if db_name == "system_internal":
                            tables.add(index_name)
                        continue
                    elif index_name.startswith("."):
                        if db_name == "system":
                            tables.add(index_name)
                        continue
                    elif index_name.startswith(db_name):
                        tables.add(index_name)
                        continue
                    elif self.db_separator in index_name:
                        continue
                    else:
                        if db_name == "other":
                            tables.add(index_name)
            tables_sorted = sorted(tables)
            return ResultSet(rows=tables_sorted)
        except Exception as e:
            raise Exception(f"获取表列表时出错: {str(e)}")

    def get_all_columns_by_tb(self, db_name, tb_name, **kwargs):
        """获取所有字段"""
        result_set = ResultSet(full_sql=f"{tb_name}/_mapping")
        try:
            self.get_connection()
            mapping = self.conn.indices.get_mapping(index=tb_name)
            properties = (
                mapping.get(tb_name, {}).get("mappings", {}).get("properties", None)
            )
            # 返回字段名
            result_set.column_list = ["column_name"]
            if properties is None:
                result_set.rows = [("无")]
            else:
                result_set.rows = list(properties.keys())
            return result_set
        except Exception as e:
            raise Exception(f"获取字段时出错: {str(e)}")

    def describe_table(self, db_name, tb_name, **kwargs):
        """表结构"""
        result_set = ResultSet(full_sql=f"{tb_name}/_mapping")
        try:
            self.get_connection()
            mapping = self.conn.indices.get_mapping(index=tb_name)
            properties = (
                mapping.get(tb_name, {}).get("mappings", {}).get("properties", None)
            )
            # 创建包含字段名、类型和其他信息的列表结构
            result_set.column_list = ["column_name", "type", "fields"]
            if properties is None:
                result_set.rows = [("无", "无", "无")]
            else:
                result_set.rows = [
                    (
                        column,
                        details.get("type"),
                        json.dumps(details.get("fields", {})),
                    )
                    for column, details in properties.items()
                ]
            return result_set
        except Exception as e:
            raise Exception(f"获取字段时出错: {str(e)}")

    def query_check(self, db_name=None, sql=""):
        """语句检查"""
        result = {"msg": "", "bad_query": False, "filtered_sql": sql, "has_star": False}
        # 使用正则表达式去除开头的空白字符和换行符
        tripped_sql = re.sub(r"^\s+", "", sql)
        result["filtered_sql"] = tripped_sql
        lower_sql = tripped_sql.lower()
        # 检查是否以 'get' 或 'select' 开头
        if lower_sql.startswith("get ") or lower_sql.startswith("select "):
            result["msg"] = "语句检查通过。"
            result["bad_query"] = False
        else:
            result["msg"] = (
                "语句检查失败：语句必须以 'get' 或 'select' 开头。示例查询：GET /dmp__iv/_search、select * from dmp__iv limit 10;"
            )
            result["bad_query"] = True
        return result

    def filter_sql(self, sql="", limit_num=0):
        """过滤 SQL 语句"""
        return sql.strip()

    def query(
        self,
        db_name=None,
        sql="",
        limit_num=0,
        close_conn=True,
        parameters=None,
        **kwargs,
    ):
        """执行查询"""
        try:
            result_set = ResultSet(full_sql=sql)

            # 解析查询字符串
            query_params = self.parse_es_select_query_to_query_params(sql, limit_num)
            self.get_connection()
            # 管理查询处理
            if query_params.path.startswith("/_cat/indices"):
                # v这个参数用显示标题，需要加上。
                if "v" not in query_params.params:
                    query_params.params["v"] = "true"
                response = self.conn.cat.indices(
                    index=query_params.index, params=query_params.params
                )
                response_body = ""
                if isinstance(response, str):
                    response_body = response
                else:
                    response_body = response.body
                response_data = self.parse_cat_indices_response(response_body)
                # 如果有数据，设置列名
                if response_data:
                    result_set.column_list = list(response_data[0].keys())
                    result_set.rows = [tuple(row.values()) for row in response_data]
                else:
                    result_set.column_list = []
                    result_set.rows = []
                    result_set.affected_rows = 0
            else:
                # 执行搜索查询
                response = self.conn.search(
                    index=query_params.index,
                    body=query_params.query_body,
                    params=query_params.params,
                )

                # 提取查询结果
                hits = response.get("hits", {}).get("hits", [])
                # 处理查询结果，将列表和字典转换为 JSON 字符串
                rows = []
                for hit in hits:
                    # 获取文档 ID 和 _source 数据
                    doc_id = hit.get("_id")
                    source_data = hit.get("_source", {})

                    # 转换需要转换为 JSON 字符串的字段
                    for key, value in source_data.items():
                        if isinstance(value, (list, dict)):  # 如果字段是列表或字典
                            source_data[key] = json.dumps(value)  # 转换为 JSON 字符串

                    # 构建结果行
                    row = {"_id": doc_id, **source_data}
                    rows.append(row)

                # 如果有结果，获取字段名作为列名
                if rows:
                    first_row = rows[0]
                    column_list = list(first_row.keys())
                else:
                    column_list = []

                # 构建结果集
                result_set.rows = [tuple(row.values()) for row in rows]  # 只获取值
                result_set.column_list = column_list
            result_set.affected_rows = len(result_set.rows)
            return result_set
        except Exception as e:
            raise Exception(f"执行查询时出错: {str(e)}")

    def parse_cat_indices_response(self, response_text):
        """解析cat indices结果"""
        # 将响应文本按行分割
        lines = response_text.strip().splitlines()
        # 获取列标题
        headers = lines[0].strip().split()
        # 解析每一行数据
        indices_info = []
        for line in lines[1:]:
            # 按空格分割，并与标题进行配对
            values = line.strip().split(maxsplit=len(headers) - 1)
            index_info = dict(zip(headers, values))
            indices_info.append(index_info)
        return indices_info

    def parse_es_select_query_to_query_params(
        self, search_query_str: str, limit_num: int
    ) -> QueryParamsSearch:
        """解析 search query 字符串为 QueryParamsSearch 对象"""

        # 解析查询字符串
        lines = search_query_str.splitlines()
        method_line = lines[0].strip()

        query_body = "\n".join(lines[1:]).strip()
        # 如果 query_body 为空，使用默认查询体
        if not query_body:
            query_body = json.dumps({"query": {"match_all": {}}})

        # 确保 query_body 是有效的 JSON
        try:
            json_body = json.loads(query_body)
        except json.JSONDecodeError as json_err:
            raise ValueError(f"query_body：{query_body} 无法转为Json格式。{json_err}，")

        # 提取方法和路径
        method, path_with_params = method_line.split(maxsplit=1)
        # 确保路径以 '/' 开头
        if not path_with_params.startswith("/"):
            path_with_params = "/" + path_with_params

        # 分离路径和查询参数
        path, params_str = (
            path_with_params.split("?", 1)
            if "?" in path_with_params
            else (path_with_params, "")
        )
        params = {}
        if params_str:
            for pair in params_str.split("&"):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                else:
                    key = pair
                    value = ""
                params[key] = value
        index_pattern = ""
        # 判断路径类型并提取索引模式
        if path.startswith("/_cat/indices"):
            # _cat API 路径
            path_parts = path.split("/")
            if len(path_parts) > 3:
                index_pattern = path_parts[3]
            if not index_pattern:
                index_pattern = "*"
        elif "/_search" in path:
            # 默认情况，处理常规索引路径
            # 提取索引名称
            path_parts = path.split("/")
            if len(path_parts) > 1:
                index_pattern = path_parts[1]

        if not index_pattern:
            raise Exception("未找到索引名称。")

        size = limit_num if limit_num > 0 else 100
        # 检查 JSON 中是否已经有 size，如果没有就设置
        if "size" not in json_body:
            json_body["size"] = size

        # 构建 QueryParams 对象
        query_params = QueryParamsSearch(
            index=index_pattern,
            path=path_with_params,
            params=params,
            method=method,
            size=size,
            query_body=json_body,
        )

        return query_params


class ElasticsearchEngine(ElasticsearchEngineBase):
    """Elasticsearch 引擎实现"""

    def __init__(self, instance=None):
        super().__init__(instance=instance)

    name: str = "Elasticsearch"
    info: str = "Elasticsearch 引擎"

    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        if self.instance:
            scheme = "https" if self.is_ssl else "http"
            hosts = [
                {
                    "host": self.host,
                    "port": self.port,
                    "scheme": scheme,
                    "use_ssl": self.is_ssl,
                }
            ]
            http_auth = (
                (self.user, self.password) if self.user and self.password else None
            )
            self.db_name = (self.db_name or "") + "*"
            try:
                # 创建 Elasticsearch 连接,高版本有basic_auth
                self.conn = Elasticsearch(
                    hosts=hosts,
                    http_auth=http_auth,
                    verify_certs=True,  # 需要证书验证
                )
            except Exception as e:
                raise Exception(f"Elasticsearch 连接建立失败: {str(e)}")
        if not self.conn:
            raise Exception("Elasticsearch 连接无法建立。")
        return self.conn




class OpenSearchEngine(ElasticsearchEngineBase):
    """OpenSearch 引擎实现"""

    def __init__(self, instance=None):
        super().__init__(instance=instance)

    name: str = "OpenSearch"
    info: str = "OpenSearch 引擎"

    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        if self.instance:
            scheme = "https" if self.is_ssl else "http"
            hosts = [
                {
                    "host": self.host,
                    "port": self.port,
                    "scheme": scheme,
                    "use_ssl": self.is_ssl,
                }
            ]
            http_auth = (
                (self.user, self.password) if self.user and self.password else None
            )
            self.db_name = (self.db_name or "") + "*"

            try:
                # 创建 OpenSearch 连接
                self.conn = OpenSearch(
                    hosts=hosts,
                    http_auth=http_auth,
                    verify_certs=True,  # 开启证书验证
                )
            except Exception as e:
                raise Exception(f"OpenSearch 连接建立失败: {str(e)}")
        if not self.conn:
            raise Exception("OpenSearch 连接无法建立。")
        return self.conn
