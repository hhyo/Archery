# -*- coding: UTF-8 -*-

__author__ = 'sunnywalden@gmail.com'

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import asyncio

from common.utils.get_logger import get_logger

logger = get_logger()


def multi_thread(func, tenants, *args):
    """多线程执行多个租户"""

    start = time.perf_counter()
    args_lists = [tuple([tenant, *args]) for tenant in tenants]
    with ThreadPoolExecutor() as executor:
        to_do = []
        for args_list in args_lists:
        #     args_list = [tenant_name]
        #     args_list.extend(*args)
            future = executor.submit(func, *args_list)
            to_do.append(future)

        # 获取线程执行结果
        for future in as_completed(to_do):
            res = future.result()

            logger.debug('Debug executor result {0}'.format(res))

    end = time.perf_counter()
    # 打印耗时
    logger.info("{0} seconds spent".format(end - start))