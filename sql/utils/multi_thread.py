# -*- coding: UTF-8 -*-

import threading


def multi_thread(func, tenants, *args):
    """多线程执行多个租户"""
    threads = []
    for tenant_name in tenants:
        args_list = [tenant_name]
        args_list.extend(*args)
        t = threading.Thread(target=func, args=args_list)
        threads.append(t)
        t.start()

    # 等到所有线程执行完成
    for t in threads:
        t.join()
