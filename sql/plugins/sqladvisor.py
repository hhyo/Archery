# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: sqladvisor.py 
@time: 2019/03/04
"""
__author__ = 'hhyo'

from common.config import SysConfig
from sql.plugins.plugin import Plugin


class SQLAdvisor(Plugin):
    def __init__(self):
        self.path = SysConfig().get('sqladvisor')
        self.required_args = ['q']
        self.disable_args = []
        super(Plugin, self).__init__()

    def generate_args2cmd(self, args, shell):
        """
        转换请求参数为命令行
        :param args:
        :param shell:
        :return:
        """
        if shell:
            cmd_args = self.path if self.path else ''
            for name, value in args.items():
                cmd_args += f' -{name} "{value}"'
        else:
            cmd_args = [self.path]
            for name, value in args.items():
                cmd_args.append(f'-{name}')
                cmd_args.append(f'{value}')
        return cmd_args
