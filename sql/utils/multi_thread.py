# -*- coding: UTF-8 -*-

__author__ = 'sunnywalden@gmail.com'

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import asyncio

from common.utils.get_logger import get_logger

logger = get_logger()


async def multi_thread(func, tenants, *args):
    """多线程执行多个租户"""

    start = time.perf_counter()
    # with ThreadPoolExecutor(10) as executor:
        # to_do = []
        # for tenant_name in tenants:
        #     args_list = [tenant_name]
        #     args_list.extend(*args)
        #     future = executor.submit(func, *args_list)
        #     to_do.append(future)
    tasks = [asyncio.create_task(func(tenant, *args)) for tenant in tenants]
    await asyncio.gather(*tasks)

        # 获取线程执行结果
        # for future in as_completed(to_do):
        #     res = future.result()
        #
        #     logger.debug('Debug executor result {0}'.format(res))

    end = time.perf_counter()
    # 打印耗时
    logger.info("{0} seconds spent".format(end - start))