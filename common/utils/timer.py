# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: timer.py 
@time: 2019/05/15
"""
import datetime

__author__ = 'hhyo'


class FuncTimer(object):
    """
    获取执行时间的上下文管理器
    """

    def __init__(self):
        self.start = None
        self.end = None
        self.cost = 0

    def __enter__(self):
        self.start = datetime.datetime.now()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end = datetime.datetime.now()
        self.cost = (self.end - self.start).total_seconds()
