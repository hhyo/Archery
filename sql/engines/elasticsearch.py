# -*- coding: UTF-8 -*-

import logging
from sql.engines.elastic_search_engine_base import ElasticsearchEngineBase
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import TransportError


logger = logging.getLogger("default")


class ElasticsearchEngine(ElasticsearchEngineBase):
    """Elasticsearch 引擎实现"""

    def __init__(self, instance=None):
        # self.db_separator = "__"  # 设置分隔符
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
