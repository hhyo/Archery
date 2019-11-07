# -*- coding: UTF-8 -*-
# author: sunnywalden@gmail.com

import MySQLdb
from DBUtils.PooledDB import PooledDB, SharedDBConnection


def setup_conn(host, port, creator=MySQLdb, **args):
    """创建数据库连接池"""
    pool = PooledDB(
            creator=creator,
            host=host,
            port=int(port),
            **args
        )

    return pool


def shutdown_conn(pool=None):
    """关闭数据库连接池"""
    if pool:
        pool.close()
