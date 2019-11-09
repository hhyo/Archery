# -*- coding: UTF-8 -*-

__author__ = 'sunnywalden@gmail.com'

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import asyncio

from common.utils.get_logger import get_logger

logger = get_logger()


async def async_tasks(func, tenants, *args):
    """异步执行多个租户"""

    start = time.perf_counter()
    args_lists = [tuple([tenant, *args]) for tenant in tenants]
    logger.debug("Debug arguments {0}".format(args_lists))
    tasks = [asyncio.create_task(func(*args_list)) for args_list in args_lists]
    await asyncio.gather(*tasks)

    end = time.perf_counter()
    # 打印耗时
    logger.info("{0} seconds spent".format(end - start))
