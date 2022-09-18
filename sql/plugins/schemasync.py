# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: schemasync.py
@time: 2019/03/05
"""
__author__ = "hhyo"

from sql.plugins.plugin import Plugin


class SchemaSync(Plugin):
    def __init__(self):
        self.path = "schemasync"
        self.required_args = []
        self.disable_args = []
        super(Plugin, self).__init__()

    def generate_args2cmd(self, args):
        """
        将请求参数转换为命令行参数
        :return:
        """
        cmd_args = [self.path]
        v_options = ["source", "target"]
        for arg, value in args.items():
            if not value:
                continue
            if arg in v_options:
                cmd_args.append(f"{value}")
                continue
            cmd_args.append(f"--{arg}")
            if not isinstance(value, bool):
                cmd_args.append(f"{value}")
        return cmd_args
