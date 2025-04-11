# -*- coding: UTF-8 -*-
"""
@author: feiazifeiazi
@license: Apache Licence
@file: xx.py
@time: 2024-08-01
"""
__author__ = "feiazifeiazi"

import logging
import os
import re
import traceback
from opensearchpy import OpenSearch
import simplejson as json
import sqlparse

from common.utils.timer import FuncTimer
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
        index: str = None,
        path: str = None,
        params: str = None,
        method: str = None,
        size: int = 100,
        sql: str = None,
        query_body: dict = None,
    ):
        self.index = index if index is not None else ""
        self.path = path if path is not None else ""
        self.method = method if method is not None else ""
        self.params = params
        self.size = size
        self.sql = sql if sql is not None else ""
        self.query_body = query_body if query_body is not None else {}


class ElasticsearchDocument:
    """ES doc对象"""

    def __init__(
        self,
        sql: str = None,
        method: str = None,
        index_name: str = None,
        api_endpoint: str = "",
        doc_id: str = None,
        doc_data_body: str = None,
    ):
        self.sql = sql
        self.method = method.upper() if method is not None else None
        self.index_name = index_name
        self.api_endpoint = api_endpoint.lower() if api_endpoint is not None else ""
        self.doc_id = doc_id
        self.doc_data_body = doc_data_body

    def describe(self) -> str:
        """返回格式化的描述信息"""
        return f"[index_name：{self.index_name}, method：{self.method}, api_endpoint：{self.api_endpoint}, doc_id：{self.doc_id}]"


class ElasticsearchEngineBase(EngineBase):
    """
    Elasticsearch、OpenSearch等Search父类实现
    如果2者方法差异不大，可以在父类用if else实现。如果差异大，建议在子类实现。
    """

    def __init__(self, instance=None):
        self.conn = None  # type: Elasticsearch  # 使用类型注释来显式提示类型
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
            database_names.add("system")  # 系统表名使用的库名
            for index_name in indices.keys():
                if self.db_separator in index_name:
                    db_name = index_name.split(self.db_separator)[0]
                    database_names.add(db_name)
            database_names.add("other")  # 表名没有__时，使用的库名
            database_names_sorted = sorted(database_names)
            return ResultSet(rows=database_names_sorted)
        except Exception as e:
            logger.error(f"获取数据库时出错:{e}{traceback.format_exc()}")
            raise Exception(f"获取数据库时出错: {str(e)}")

    def get_all_tables(self, db_name, **kwargs):
        """根据给定的数据库名获取所有相关的表名
        以点开头的表名，不返回。此为系统表，官方不让查询了。
        """
        try:
            self.get_connection()
            indices = self.conn.indices.get_alias(index=self.db_name)
            tables = set()

            db_mapping = {
                "system": "",
                "other": "",
            }
            # 根据分隔符分隔的库名
            if db_name not in db_mapping:
                index_prefix = db_name.rstrip(self.db_separator) + self.db_separator
                tables = [
                    index for index in indices.keys() if index.startswith(index_prefix)
                ]
            else:
                # 处理系统表，和other
                if db_name == "system":
                    # 将系统的API作为表名
                    tables.add("/_cat/indices/" + self.db_name)
                    tables.add("/_cat/nodes")
                    tables.add("/_security/role")
                    tables.add("/_security/user")

                for index_name in indices.keys():
                    if index_name.startswith("."):
                        # if db_name == "system":
                        #     tables.add(index_name)
                        continue
                    elif index_name.startswith(db_name):
                        tables.add(index_name)
                        if db_name == "system":
                            tables.add("/_cat/indices/" + db_name)
                        continue
                    elif self.db_separator in index_name:
                        separator_db_name = index_name.split(self.db_separator)[0]
                        if db_name == "system":
                            tables.add("/_cat/indices/" + separator_db_name)
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
        if tb_name.startswith(("/", "_")):
            return result_set
        else:
            try:
                self.get_connection()
                mapping = self.conn.indices.get_mapping(index=tb_name)
                properties = (
                    mapping.get(tb_name, {}).get("mappings", {}).get("properties", None)
                )
                # 返回字段名
                result_set.column_list = ["column_name"]
                if properties is None:
                    result_set.rows = ["无"]
                else:
                    result_set.rows = list(properties.keys())
                return result_set
            except Exception as e:
                raise Exception(f"获取字段时出错: {str(e)}")

    def describe_table(self, db_name, tb_name, **kwargs):
        """表结构"""
        result_set = ResultSet(full_sql=f"{tb_name}/_mapping")
        if tb_name.startswith(("/", "_")):
            return result_set
        else:
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
        result = {
            "msg": "语句检查通过。",
            "bad_query": False,
            "filtered_sql": sql,
            "has_star": False,
        }
        sql = sql.rstrip(";").strip()
        result["filtered_sql"] = sql
        # 检查是否以 'get' 或 'select' 开头
        if re.match(r"^get", sql, re.I):
            pass
        elif re.match(r"^select", sql, re.I):
            try:
                sql = sqlparse.format(sql, strip_comments=True)
                sql = sqlparse.split(sql)[0]
                result["filtered_sql"] = sql.strip()
            except IndexError:
                result["bad_query"] = True
                result["msg"] = "没有有效的SQL语句。"
        else:
            result["msg"] = (
                "语句检查失败：语句必须以 'get' 或 'select' 开头。示例查询：GET /dmp__iv/_search、select * from dmp__iv limit 10;"
            )
            result["bad_query"] = True
        return result

    def filter_sql(self, sql="", limit_num=0):
        """过滤 SQL 语句。
        对查询sql增加limit限制,limit n 或 limit n,n 或 limit n offset n统一改写成limit n
        此方法SQL部分的逻辑copy的mysql实现。
        """
        #
        sql = sql.rstrip(";").strip()
        if re.match(r"^get", sql, re.I):
            pass
        elif re.match(r"^select", sql, re.I):
            # LIMIT N
            limit_n = re.compile(r"limit\s+(\d+)\s*$", re.I)
            # LIMIT M OFFSET N
            limit_offset = re.compile(r"limit\s+(\d+)\s+offset\s+(\d+)\s*$", re.I)
            # LIMIT M,N
            offset_comma_limit = re.compile(r"limit\s+(\d+)\s*,\s*(\d+)\s*$", re.I)
            if limit_n.search(sql):
                sql_limit = limit_n.search(sql).group(1)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = limit_n.sub(f"limit {limit_num};", sql)
            elif limit_offset.search(sql):
                sql_limit = limit_offset.search(sql).group(1)
                sql_offset = limit_offset.search(sql).group(2)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = limit_offset.sub(f"limit {limit_num} offset {sql_offset};", sql)
            elif offset_comma_limit.search(sql):
                sql_offset = offset_comma_limit.search(sql).group(1)
                sql_limit = offset_comma_limit.search(sql).group(2)
                limit_num = min(int(limit_num), int(sql_limit))
                sql = offset_comma_limit.sub(f"limit {sql_offset},{limit_num};", sql)
            else:
                sql = f"{sql} limit {limit_num};"
        else:
            sql = f"{sql};"
        return sql

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
                # v这个参数用显示标题，需要加上。 opensearch 需要字符串的true
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
            elif query_params.path.startswith("/_security/role"):
                result_set = self._security_role(sql, query_params)
            elif query_params.path.startswith("/_security/user"):
                result_set = self._security_user(sql, query_params)
            elif query_params.sql and self.name == "Elasticsearch":
                query_body = {"query": query_params.sql}
                response = self.conn.sql.query(body=query_body)
                # 提取列名和行数据
                columns = response.get("columns", [])
                rows = response.get("rows", [])
                # 获取字段名作为列名
                column_list = [col["name"] for col in columns]

                # 处理查询结果，将列表和字典转换为 JSON 字符串。列名可能是重复的。
                formatted_rows = []
                for row in rows:
                    # 创建字典，将列名和对应的行值关联
                    formatted_row = []
                    for col_name, value in zip(column_list, row):
                        # 如果字段是列表或字典，将其转换为 JSON 字符串
                        if isinstance(value, (list, dict)):
                            formatted_row.append(json.dumps(value))
                        else:
                            formatted_row.append(value)
                    formatted_rows.append(formatted_row)
                # 构建结果集
                result_set.rows = formatted_rows
                result_set.column_list = column_list
            elif query_params.sql and self.name == "OpenSearch":
                query_body = {"query": query_params.sql}
                response = self.conn.transport.perform_request(
                    method="POST", url="/_opendistro/_sql", body=query_body
                )
                # 提取列名和行数据
                columns = response.get("schema", [])
                rows = response.get("datarows", [])
                # 获取字段名作为列名
                column_list = [col["name"] for col in columns]

                # 处理查询结果，将列表和字典转换为 JSON 字符串。列名可能是重复的。
                formatted_rows = []
                for row in rows:
                    # 创建字典，将列名和对应的行值关联
                    formatted_row = []
                    for col_name, value in zip(column_list, row):
                        # 如果字段是列表或字典，将其转换为 JSON 字符串
                        if isinstance(value, (list, dict)):
                            formatted_row.append(json.dumps(value))
                        else:
                            formatted_row.append(value)
                    formatted_rows.append(formatted_row)
                # 构建结果集
                result_set.rows = formatted_rows
                result_set.column_list = column_list
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
                all_search_keys = {}  # 用于收集所有字段的集合
                all_search_keys["_id"] = None
                for hit in hits:
                    # 获取文档 ID 和 _source 数据
                    doc_id = hit.get("_id")
                    source_data = hit.get("_source", {})

                    # 转换需要转换为 JSON 字符串的字段
                    for key, value in source_data.items():
                        all_search_keys[key] = None  # 收集所有字段名
                        if isinstance(value, (list, dict)):  # 如果字段是列表或字典
                            source_data[key] = json.dumps(value)  # 转换为 JSON 字符串

                    # 构建结果行
                    row = {"_id": doc_id, **source_data}
                    rows.append(row)

                column_list = list(all_search_keys.keys())
                # 构建结果集
                result_set.rows = []
                for row in rows:
                    # 按照 column_list 的顺序填充每一行
                    result_row = tuple(row.get(key, None) for key in column_list)
                    result_set.rows.append(result_row)
                result_set.column_list = column_list
            result_set.affected_rows = len(result_set.rows)
            return result_set
        except Exception as e:
            raise Exception(f"执行查询时出错: {str(e)}")

    def _security_role(self, sql, query_params: QueryParamsSearch):
        """角色查询方法。请子类实现。"""

    def _security_user(self, sql, query_params: QueryParamsSearch):
        """用户查询方法。请子类实现。"""

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

        query_params = QueryParamsSearch()
        sql = search_query_str.rstrip(";").strip()
        if re.match(r"^get", sql, re.I):
            # 解析查询字符串
            lines = sql.splitlines()
            method_line = lines[0].strip()

            query_body = "\n".join(lines[1:]).strip()
            # 如果 query_body 为空，使用默认查询体
            if not query_body:
                query_body = json.dumps({"query": {"match_all": {}}})

            # 确保 query_body 是有效的 JSON
            try:
                json_body = json.loads(query_body)
            except json.JSONDecodeError as json_err:
                raise ValueError(
                    f"无法转为Json格式。{json_err}。query_body：{query_body}。"
                )

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
            elif path.startswith("/_security/role"):
                path_parts = path.split("/")
                index_pattern = "*"
            elif path.startswith("/_security/user"):
                path_parts = path.split("/")
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
        elif re.match(r"^select", sql, re.I):
            query_params = QueryParamsSearch(sql=sql)
        return query_params

    def execute_check(self, db_name=None, sql=""):
        """上线单执行前的检查
        #PUT只有索引名，没有api-endpoint时, 解释为创建索引，需要包含mappings或settings。
        #PUT有索引名，有_doc，没有Id，错误写法，必须要写Id。

        #post 有索引名, 没有_doc，错误写法。报错。
        #post 有索引，有_doc,  有或没有id 均可。
        #post 有索引，api-endpoint=_search时，这是查询，报错。

        #delete 有索引，没有_doc，解释为删除表。 archery禁止此操作,需要报错。
        #delete 有索引，有_doc，没有id，删除必须包含id，需要报错。

        # api-endpoint为_update时，只能post，不能put，错误写法，报错。
        # api-endpoint为_update_by_query时，只能post，不能put，错误写法，报错。
        """
        check_result = ReviewSet(full_sql=sql)
        rowid = 1
        documents = self.__split_sql(sql)
        for doc in documents:
            is_pass = False
            doc_desc = doc.describe()
            if re.match(r"^get|^select", doc.sql, re.I):
                result = ReviewResult(
                    id=rowid,
                    errlevel=2,
                    stagestatus="驳回不支持语句",
                    errormessage="仅支持PUT,POST,DELETE等API方法，GET,SELECT查询语句请使用SQL查询功能！",
                    sql=doc.sql,
                )
            elif re.match(r"^#", doc.sql, re.I):
                result = ReviewResult(
                    id=rowid,
                    errlevel=0,
                    stagestatus="Audit completed",
                    errormessage="此为注释信息。",
                    sql=doc.sql,
                    affected_rows=0,
                    execute_time=0,
                )
            elif not doc.index_name:
                result = ReviewResult(
                    id=rowid,
                    errlevel=2,
                    stagestatus="驳回不支持语句",
                    errormessage=f"请求必须包含索引名称或无法解析。解析结果：{doc_desc}",
                    sql=doc.sql,
                )
            elif doc.method == "DELETE":
                if not doc.doc_id:
                    result = ReviewResult(
                        id=rowid,
                        errlevel=2,
                        stagestatus="驳回不支持语句",
                        errormessage="删除操作必须包含id条件。",
                        sql=doc.sql,
                    )
                else:
                    if is_pass == False:
                        is_pass = True
            elif not doc.api_endpoint:
                if doc.method == "PUT":
                    if not doc.doc_data_body or (
                        "mappings" in doc.doc_data_body
                        or "settings" in doc.doc_data_body
                    ):
                        result = ReviewResult(
                            id=rowid,
                            errlevel=0,
                            stagestatus="Audit completed",
                            errormessage=f"审核通过。解析结果：创建表：[index_name：{doc.index_name}]",
                            sql=doc.sql,
                        )
                    else:
                        result = ReviewResult(
                            id=rowid,
                            errlevel=2,
                            stagestatus="驳回不支持语句",
                            errormessage="PUT请求创建索引时请求体可以为空或需要包含mappings或settings。",
                            sql=doc.sql,
                        )
                elif doc.method == "POST":
                    result = ReviewResult(
                        id=rowid,
                        errlevel=2,
                        stagestatus="驳回不支持语句",
                        errormessage=f"POST请求必须指定API端点，例如_doc。解析结果：{doc_desc}",
                        sql=doc.sql,
                    )
                else:
                    result = ReviewResult(
                        id=rowid,
                        errlevel=2,
                        stagestatus="驳回不支持语句",
                        errormessage=f"不支持此操作。解析结果：{doc_desc}",
                        sql=doc.sql,
                        affected_rows=0,
                        execute_time=0,
                    )
            elif doc.api_endpoint == "_doc":
                if doc.method == "PUT":
                    if not doc.doc_id:
                        result = ReviewResult(
                            id=rowid,
                            errlevel=2,
                            stagestatus="驳回不支持语句",
                            errormessage="PUT请求必须包含文档Id。",
                            sql=doc.sql,
                        )
                    else:
                        if is_pass == False:
                            is_pass = True
                elif doc.method == "POST":
                    if is_pass == False:
                        is_pass = True
                else:
                    result = ReviewResult(
                        id=rowid,
                        errlevel=2,
                        stagestatus="驳回不支持语句",
                        errormessage=f"不支持此操作。解析结果：{doc_desc}",
                        sql=doc.sql,
                        affected_rows=0,
                        execute_time=0,
                    )
            elif doc.api_endpoint == "_search":
                result = ReviewResult(
                    id=rowid,
                    errlevel=2,
                    stagestatus="驳回不支持语句",
                    errormessage="_search属于查询方法。",
                    sql=doc.sql,
                )
            elif doc.api_endpoint == "_update":
                if doc.method == "POST":
                    if not doc.doc_id:
                        result = ReviewResult(
                            id=rowid,
                            errlevel=2,
                            stagestatus="驳回不支持语句",
                            errormessage=f"POST请求{doc.api_endpoint}时必须包含文档Id。",
                            sql=doc.sql,
                        )
                    else:
                        if is_pass == False:
                            is_pass = True
                else:
                    result = ReviewResult(
                        id=rowid,
                        errlevel=2,
                        stagestatus="驳回不支持语句",
                        errormessage=f"不支持此操作，{doc.api_endpoint}需要使用POST方法。解析结果：{doc_desc}",
                        sql=doc.sql,
                        affected_rows=0,
                        execute_time=0,
                    )
            elif doc.api_endpoint == "_update_by_query":
                if doc.method == "POST":
                    if is_pass == False:
                        is_pass = True
                else:
                    result = ReviewResult(
                        id=rowid,
                        errlevel=2,
                        stagestatus="驳回不支持语句",
                        errormessage=f"不支持此操作，{doc.api_endpoint}需要使用POST方法。解析结果：{doc_desc}",
                        sql=doc.sql,
                        affected_rows=0,
                        execute_time=0,
                    )
            elif doc.api_endpoint not in ["", "_doc", "_update_by_query", "_update"]:
                result = ReviewResult(
                    id=rowid,
                    errlevel=2,
                    stagestatus="驳回不支持语句",
                    errormessage="API操作端点(API Endpoint)仅支持: 空, _doc、_update、_update_by_query。",
                    sql=doc.sql,
                )
            else:
                result = ReviewResult(
                    id=rowid,
                    errlevel=2,
                    stagestatus="驳回不支持语句",
                    errormessage=f"不支持此操作。解析结果：{doc_desc}",
                    sql=doc.sql,
                    affected_rows=0,
                    execute_time=0,
                )
            # 通用的，通过审核
            if is_pass:
                result = ReviewResult(
                    id=rowid,
                    errlevel=0,
                    stagestatus="Audit completed",
                    errormessage=f"审核通过。解析结果：{doc_desc}",
                    sql=doc.sql,
                    affected_rows=0,
                    execute_time=0,
                )

            check_result.rows.append(result)
            rowid += 1
        # 统计警告和错误数量
        for r in check_result.rows:
            if r.errlevel == 1:
                check_result.warning_count += 1
            if r.errlevel == 2:
                check_result.error_count += 1
        return check_result

    def execute_workflow(self, workflow):
        """执行上线单，返回Review set"""
        sql = workflow.sqlworkflowcontent.sql_content
        docs = self.__split_sql(sql)
        execute_result = ReviewSet(full_sql=sql)
        line = 0
        try:
            conn = self.get_connection(db_name=workflow.db_name)
            for doc in docs:
                line += 1
                if re.match(r"^#", doc.sql, re.I):
                    execute_result.rows.append(
                        ReviewResult(
                            id=line,
                            errlevel=0,
                            stagestatus="Execute Successfully",
                            errormessage="注释信息不需要执行。",
                            sql=doc.sql,
                            affected_rows=0,
                            execute_time=0,
                        )
                    )
                elif doc.method == "DELETE":
                    reviewResult = self.__delete_data(conn, doc)
                    reviewResult.id = line
                    execute_result.rows.append(reviewResult)
                elif doc.api_endpoint == "":
                    # 创建索引
                    reviewResult = self.__create_index(conn, doc)
                    reviewResult.id = line
                    execute_result.rows.append(reviewResult)
                elif doc.api_endpoint == "_update":
                    reviewResult = self.__update(conn, doc)
                    reviewResult.id = line
                    execute_result.rows.append(reviewResult)
                elif doc.api_endpoint == "_update_by_query":
                    reviewResult = self.__update_by_query(conn, doc)
                    reviewResult.id = line
                    execute_result.rows.append(reviewResult)
                elif doc.api_endpoint == "_doc":
                    reviewResult = self.__add_or_update(conn, doc)
                    reviewResult.id = line
                    execute_result.rows.append(reviewResult)
                else:
                    raise Exception(f"不支持的API类型：{doc.api_endpoint}")
        except Exception as e:
            logger.warning(
                f"ES命令执行报错，语句：{doc.sql}， 错误信息：{traceback.format_exc()}"
            )
            # 追加当前报错语句信息到执行结果中
            execute_result.error = str(e)
            execute_result.rows.append(
                ReviewResult(
                    id=line,
                    errlevel=2,
                    stagestatus="Execute Failed",
                    errormessage=f"异常信息：{e}",
                    sql=doc.sql,
                    affected_rows=0,
                    execute_time=0,
                )
            )
        if execute_result.error:
            # 如果失败, 将剩下的部分加入结果集
            for doc in docs[line:]:
                line += 1
                execute_result.rows.append(
                    ReviewResult(
                        id=line,
                        errlevel=0,
                        stagestatus="Audit completed",
                        errormessage=f"前序语句失败, 未执行",
                        sql=doc.sql,
                        affected_rows=0,
                        execute_time=0,
                    )
                )
        return execute_result

    def __update(self, conn, doc):
        """ES的  update方法"""
        errlevel = 0
        with FuncTimer() as t:
            try:
                response = conn.update(
                    index=doc.index_name,
                    id=doc.doc_id,
                    body=doc.doc_data_body,
                )
                successful_count = response.get("_shards", {}).get("successful", None)
                response_str = str(response)
            except Exception as e:
                error_message = str(e)
                if "NotFoundError" in error_message:
                    response_str = "document missing: " + error_message
                    successful_count = 0
                    errlevel = 1
                else:
                    raise
        return ReviewResult(
            errlevel=errlevel,
            stagestatus="Execute Successfully",
            errormessage=response_str,
            sql=doc.sql,
            affected_rows=successful_count,
            execute_time=t.cost,
        )

    def __add_or_update(self, conn, doc):
        """ES的 add_or_update方法"""
        with FuncTimer() as t:
            if doc.api_endpoint == "_doc":
                response = conn.index(
                    index=doc.index_name,
                    id=doc.doc_id,
                    body=doc.doc_data_body,
                )
            else:
                raise Exception(f"不支持的API类型：{doc.api_endpoint}")

            successful_count = response.get("_shards", {}).get("successful", None)
            response_str = str(response)
        return ReviewResult(
            errlevel=0,
            stagestatus="Execute Successfully",
            errormessage=response_str,
            sql=doc.sql,
            affected_rows=successful_count,
            execute_time=t.cost,
        )

    def __update_by_query(self, conn, doc):
        """ES的 update_by_query方法"""
        errlevel = 0
        with FuncTimer() as t:
            try:
                response = conn.update_by_query(
                    index=doc.index_name, body=doc.doc_data_body
                )
                successful_count = response.get("total", 0)
                response_str = str(response)
            except Exception as e:
                raise e
        return ReviewResult(
            errlevel=errlevel,
            stagestatus="Execute Successfully",
            errormessage=response_str,
            sql=doc.sql,
            affected_rows=successful_count,
            execute_time=t.cost,
        )

    def __create_index(self, conn, doc):
        """ES的 创建索引方法"""
        errlevel = 0
        with FuncTimer() as t:
            try:
                response = conn.indices.create(
                    index=doc.index_name, body=doc.doc_data_body
                )
                successful_count = 0
                response_str = str(response)
            except Exception as e:
                error_message = str(e)
                if "already_exists" in error_message:
                    response_str = "index already exists: " + error_message
                    successful_count = 0
                    errlevel = 1
                else:
                    raise

        return ReviewResult(
            errlevel=errlevel,
            stagestatus="Execute Successfully",
            errormessage=response_str,
            sql=doc.sql,
            affected_rows=successful_count,
            execute_time=t.cost,
        )

    def __delete_data(self, conn, doc):
        """
        数据删除
        """
        errlevel = 0
        if not doc.doc_id:
            response_str = "删除操作必须包含id条件。"
            successful_count = 0
        with FuncTimer() as t:
            try:
                response = conn.delete(index=doc.index_name, id=doc.doc_id)
                successful_count = response.get("_shards", {}).get("successful", None)
                response_str = str(response)
            except Exception as e:
                error_message = str(e)
                if "NotFoundError" in error_message:
                    response_str = "Document not found: " + error_message
                    successful_count = 0
                    errlevel = 1
                else:
                    raise
        return ReviewResult(
            errlevel=errlevel,
            stagestatus="Execute Successfully",
            errormessage=response_str,
            sql=doc.sql,
            affected_rows=successful_count,
            execute_time=t.cost,
        )

    def __get_document_from_sql(self, sql):
        """
        解析输入的SQL，提取索引、文档 ID 和文档数据，返回 ElasticsearchDocument 实例。
        """
        result = ElasticsearchDocument(sql=sql)
        if re.match(r"^POST |^PUT |^DELETE ", sql, re.I):

            # 提取方法和路径
            method, path_with_params = sql.split(maxsplit=1)
            if path_with_params.startswith("{"):
                # 如果是{ 开头，说明没有路径部分。
                return result
            # 确保路径以 '/' 开头
            if not path_with_params.startswith("/"):
                path_with_params = "/" + path_with_params

            parts = path_with_params.split(maxsplit=1)
            path = parts[0]  # 获取路径部分
            doc_data_body = parts[1].strip() if len(parts) > 1 else None

            path_parts = path.split("/")
            # 提取各个部分
            index_name = path_parts[1] if len(path_parts) > 1 else None
            api_endpoint = path_parts[2] if len(path_parts) > 2 else None
            doc_id = path_parts[3] if len(path_parts) > 3 else None
            doc_data_json = None
            if doc_data_body:
                try:
                    doc_data_json = json.loads(doc_data_body)
                except json.JSONDecodeError as json_err:
                    raise ValueError(
                        f"无法转为Json格式。{json_err}。doc_data_body：{doc_data_body}。"
                    )
            result = ElasticsearchDocument(
                sql=sql,
                method=method,
                index_name=index_name,
                api_endpoint=api_endpoint,
                doc_id=doc_id,
                doc_data_body=doc_data_json,
            )
        return result

    def __split_sql(self, sql):
        """
        解析输入的多行命令字符串，将其分割为独立的命令列表，解析为documents对象返回
        """
        lines = sql.strip().splitlines()
        commands = []
        current_command = []
        brace_level = 0

        for line in lines:
            stripped_line = line.strip()

            if not stripped_line:
                continue
            if stripped_line.startswith("#"):
                continue

            brace_level += stripped_line.count("{")
            brace_level -= stripped_line.count("}")

            # 将当前行加入当前命令
            current_command.append(stripped_line)

            if brace_level == 0 and current_command:
                commands.append(os.linesep.join(current_command))
                current_command = []

        merged_commands = []
        for command in commands:
            # 如果当前命令以 { 开头，合并到前一个命令
            if command.startswith("{") and merged_commands:
                # 合并当前命令到上一个命令
                merged_commands[-1] += os.linesep + command
            else:
                # 如果不是以 { 开头，则直接添加到结果中
                merged_commands.append(command)

        # 创建 ElasticsearchDocument 实例列表
        documents = []
        for command in merged_commands:
            doc = self.__get_document_from_sql(command)
            if doc:
                documents.append(doc)
        return documents


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
            scheme = "https" if self.instance.is_ssl else "http"
            hosts = [
                {
                    "host": self.host,
                    "port": self.port,
                    "scheme": scheme,
                    "use_ssl": self.instance.is_ssl,
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
                    verify_certs=self.instance.verify_ssl,  # 需要证书验证
                )
            except Exception as e:
                raise Exception(f"Elasticsearch 连接建立失败: {str(e)}")
        if not self.conn:
            raise Exception("Elasticsearch 连接无法建立。")
        return self.conn

    def _security_role(self, sql, query_params: QueryParamsSearch):
        """TODO 角色查询方法。"""
        raise NotImplementedError("此方法暂未实现。")

    def _security_user(self, sql, query_params: QueryParamsSearch):
        """TODO 用户查询方法。"""
        raise NotImplementedError("此方法暂未实现。")


class OpenSearchEngine(ElasticsearchEngineBase):
    """OpenSearch 引擎实现"""

    def __init__(self, instance=None):
        self.conn = None  # type: OpenSearch  # 使用类型注释来显式提示类型
        super().__init__(instance=instance)

    name: str = "OpenSearch"
    info: str = "OpenSearch 引擎"

    def get_connection(self, db_name=None):
        if self.conn:
            return self.conn
        if self.instance:
            scheme = "https" if self.instance.is_ssl else "http"
            hosts = [
                {
                    "host": self.host,
                    "port": self.port,
                    "scheme": scheme,
                    "use_ssl": self.instance.is_ssl,
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
                    verify_certs=self.instance.verify_ssl,  # 开启证书验证
                )
            except Exception as e:
                raise Exception(f"OpenSearch 连接建立失败: {str(e)}")
        if not self.conn:
            raise Exception("OpenSearch 连接无法建立。")
        return self.conn

    def _security_role(self, sql, query_params: QueryParamsSearch):
        """角色查询方法。"""
        result_set = ResultSet(full_sql=sql)
        url = "/_opendistro/_security/api/roles"
        try:
            body = {}
            # "/_security/role"
            response = self.conn.transport.perform_request("GET", url, body=body)
            response_body = response
            if response and isinstance(response_body, (dict)):
                # 获取第一个角色的信息，动态生成 column_list
                first_role_info = next(iter(response.values()), {})
                column_list = ["role_name"] + list(first_role_info.keys())
                formatted_rows = []

                for role_name, role_info in response.items():
                    row = [role_name]
                    for column in first_role_info.keys():
                        value = role_info.get(column, None)
                        # 检查值的类型，如果是 list 或 dict，转换为 JSON 字符串
                        if isinstance(value, (list, dict)):
                            row.append(json.dumps(value))
                        else:
                            row.append(value)
                    formatted_rows.append(row)
                result_set.rows = formatted_rows
                result_set.column_list = column_list
        except Exception as e:
            raise Exception(f"执行查询时出错: {str(e)}")
        return result_set

    def _security_user(self, sql, query_params: QueryParamsSearch):
        """用户查询方法。"""
        result_set = ResultSet(full_sql=sql)
        url = "/_opendistro/_security/api/user"
        try:
            body = {}
            # "/_security/role"
            response = self.conn.transport.perform_request("GET", url, body=body)
            response_body = response
            if response and isinstance(response_body, (dict)):
                # 获取第一个角色的信息，动态生成 column_list
                first_role_info = next(iter(response.values()), {})
                column_list = ["user_name"] + list(first_role_info.keys())
                formatted_rows = []

                for role_name, role_info in response.items():
                    row = [role_name]
                    for column in first_role_info.keys():
                        value = role_info.get(column, None)
                        # 检查值的类型，如果是 list 或 dict，转换为 JSON 字符串
                        if isinstance(value, (list, dict)):
                            row.append(json.dumps(value))
                        else:
                            row.append(value)
                    formatted_rows.append(row)
                result_set.rows = formatted_rows
                result_set.column_list = column_list
        except Exception as e:
            raise Exception(f"执行查询时出错: {str(e)}")
        return result_set
