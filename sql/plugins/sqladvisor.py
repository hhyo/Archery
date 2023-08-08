# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: sqladvisor.py
@time: 2019/03/04
"""
__author__ = "hhyo"

import re

from common.config import SysConfig
from sql.plugins.plugin import Plugin


class SQLAdvisor(Plugin):
    def __init__(self):
        self.path = SysConfig().get("sqladvisor")
        self.required_args = ["q"]
        self.disable_args = []
        super(Plugin, self).__init__()

    def check_args(self, args):
        result = super().check_args(args)
        if result["status"] != 0:
            return result
        db_name = args.get("d")
        if not db_name:
            return result
        # 防止 db_name 注入
        db_pattern = r"[a-zA-Z0-9-_]+"
        if not re.match(db_pattern, db_name):
            return {
                "status": 1,
                "msg": f"illegal db_name, only {db_pattern} is allowed",
                "data": {},
            }
        if db_name.startswith("-"):
            return {
                "status": 1,
                "msg": f"illegal db_name, leading character - is not allowed",
                "data": {},
            }
        return result
