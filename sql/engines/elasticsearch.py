# -*- coding: UTF-8 -*-
import re, time
import pymongo
import logging
import traceback
import subprocess
import simplejson as json
import datetime
import tempfile

from . import EngineBase
from .models import ResultSet, ReviewSet, ReviewResult
from common.config import SysConfig

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import TransportError


logger = logging.getLogger("default")


class ElasticsearchEngine(EngineBase):
    """Elasticsearch 引擎实现"""

    def __init__(self, instance=None):
        self.db_separator = "__"  # 设置分隔符
        super().__init__(instance=instance)

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

            try:
                # 创建 Elasticsearch 连接,高版本有basic_auth
                self.conn = Elasticsearch(
                    hosts=hosts,
                    http_auth=http_auth,
                    verify_certs=False,  # 关闭证书验证
                )
            except Exception as e:
                raise Exception(f"Elasticsearch 连接建立失败: {str(e)}")
        if not self.conn:
            raise Exception("Elasticsearch 连接无法建立。")
        return self.conn

    def test_connection(self):
        """测试实例链接是否正常"""
        return self.get_all_databases()

    @property
    def name(self):
        return "elasticsearch"

    @property
    def info(self):
        return "Elasticsearch 引擎"

    def get_all_databases(self):
        """获取所有“数据库”名（从索引名提取）,默认提取 __ 前的部分作为数据库名"""
        try:
            self.get_connection()
            # 获取所有的别名，没有别名就是本身。
            indices = self.conn.indices.get_alias(index="*")
            database_names = set()
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
            indices = self.conn.indices.get_alias(index="*")
            tables = set()

            db_mapping = {
                "system_kibana": ".kibana_",
                "system_internal": ".internal.",
                "system": ".",
                "other": "other",
            }
            # 根据分隔符分隔的库名
            if db_name not in db_mapping:
                index_prefix = db_name
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
        result["msg"] += "语句检查，未实现。"
        result["bad_query"] = False
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
            query_string=sql
            # 解析查询字符串
            lines = query_string.splitlines()
            method_line = lines[0].strip()
            query_body = "\n".join(lines[1:]).strip()
            # 如果 query_body 为空，使用默认查询体
            if not query_body:
                query_body = json.dumps({"query": {"match_all": {}}})

            # 确保 query_body 是有效的 JSON
            try:
                json_body = json.loads(query_body)
            except json.JSONDecodeError as json_err:
                raise ValueError(f"{query_body} 无法转为Json格式。{json_err}，")
            
            # 提取方法和路径
            method, path_with_params = method_line.split(maxsplit=1)
            # 确保路径以 '/' 开头
            if not path_with_params.startswith('/'):
                path_with_params = '/' + path_with_params
            
            # 分离路径和查询参数
            path, params_str = path_with_params.split('?', 1) if '?' in path_with_params else (path_with_params, "")
            params = dict(param.split('=') for param in params_str.split('&') if '=' in param)

            # 提取索引名称
            index = path.split('/')[1]

            # 从参数中提取 filter_path
            filter_path = params.get('filter_path', None)

            # 执行搜索查询
            response = self.conn.search(
                index=index,
                body=json_body,
                size=limit_num if limit_num > 0 else 100,  # 使用 limit_num 或默认值 5
                filter_path=filter_path
            )

            # 提取查询结果
            hits = response.get("hits", {}).get("hits", [])
            results = [{'_id': hit.get('_id'), **hit.get('_source', {})} for hit in hits]
            return ResultSet(rows=results)
        except Exception as e:
            raise Exception(f"执行查询时出错: {str(e)}")

    def query_masking(self, db_name=None, sql="", resultset=None):
        """查询结果脱敏"""
        return resultset

    def execute_check(self, db_name=None, sql=""):
        """执行检查（未实现）"""
        return True

    def execute(self, db_name=None, sql="", close_conn=True, parameters=None):
        """执行语句"""
        raise NotImplementedError("execute 方法未为 Elasticsearch 实现。")


