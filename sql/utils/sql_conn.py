# -*- coding: UTF-8 -*-

__author__ = 'sunnywalden@gmail.com'

import MySQLdb
from DBUtils.PooledDB import PooledDB


def setup_conn(host, port, creator=MySQLdb, charset='utf8', **args):
    """创建数据库连接池"""
    pool = PooledDB(
            creator=creator,
            host=host,
            port=int(port),
            charset=charset,
            **args
        )

    return pool


def shutdown_conn(pool=None):
    """关闭数据库连接池"""
    if pool:
        pool.close()
