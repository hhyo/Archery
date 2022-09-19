# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: sqladvisor.py
@time: 2019/03/04
"""
__author__ = "hhyo"

from common.config import SysConfig
from sql.plugins.plugin import Plugin


class SQLAdvisor(Plugin):
    def __init__(self):
        self.path = SysConfig().get("sqladvisor")
        self.required_args = ["q"]
        self.disable_args = []
        super(Plugin, self).__init__()
