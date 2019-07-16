# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: schemasync.py 
@time: 2019/03/05
"""
__author__ = 'hhyo'

from common.config import SysConfig
from sql.plugins.plugin import Plugin


class SchemaSync(Plugin):

    def __init__(self):
        self.path = SysConfig().get('schemasync')
        self.required_args = []
        self.disable_args = []
        super(Plugin, self).__init__()

    def generate_args2cmd(self, args, shell):
        """
        转换请求参数为命令行
        :param args:
        :param shell:
        :return:
        """
        k_options = ['sync-auto-inc', 'sync-comments']
        kv_options = ['tag', 'output-directory', 'log-directory']
        v_options = ['source', 'target']
        if shell:
            cmd_args = self.path if self.path else ''
            for name, value in args.items():
                if name in k_options and value:
                    cmd_args += f' --{name}'
                elif name in kv_options:
                    cmd_args += f' --{name}={value}'
                elif name in v_options:
                    cmd_args += f' {value}'
        else:
            cmd_args = [self.path]
            for name, value in args.items():
                if name in k_options and value:
                    cmd_args.append(f'--{name}')
                elif name in kv_options:
                    cmd_args.append(f'--{name}')
                    cmd_args.append(f'{value}')
                elif name in ['source', 'target']:
                    cmd_args.append(f'{value}')
        return cmd_args
