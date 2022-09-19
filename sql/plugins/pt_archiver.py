# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: pt_archiver.py
@time: 2020/01/10
"""
from common.config import SysConfig
from sql.plugins.plugin import Plugin

__author__ = "hhyo"


class PtArchiver(Plugin):
    """
    pt-archiver归档数据
    """

    def __init__(self):
        self.path = "pt-archiver"
        self.required_args = []
        self.disable_args = ["analyze"]
        super(Plugin, self).__init__()

    def generate_args2cmd(self, args):
        """
        将请求参数转换为命令行参数
        :return:
        """
        cmd_args = [self.path]
        for arg, value in args.items():
            if not value:
                continue
            cmd_args.append(f"--{arg}")
            if not isinstance(value, bool):
                cmd_args.append(f"{value}")
        return cmd_args
