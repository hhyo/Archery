# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: pt_archiver.py
@time: 2020/01/10
"""
from common.config import SysConfig
from sql.plugins.plugin import Plugin

__author__ = 'hhyo'


class PtArchiver(Plugin):
    """
    pt-archiver归档数据
    """

    def __init__(self):
        self.path = 'pt-archiver'
        self.required_args = []
        self.disable_args = ['analyze']
        super(Plugin, self).__init__()

    def generate_args2cmd(self, args, shell):
        """
        转换请求参数为命令行
        :param args:
        :param shell:
        :return:
        """
        k_options = ['no-version-check', 'statistics', 'bulk-insert', 'bulk-delete', 'purge', 'no-delete']
        kv_options = ['source', 'dest', 'file', 'where', 'progress', 'charset', 'limit', 'txn-size', 'sleep']
        if shell:
            cmd_args = self.path if self.path else ''
            for name, value in args.items():
                if name in k_options and value:
                    cmd_args += f' --{name}'
                elif name in kv_options:
                    if name == 'where':
                        cmd_args += f' --{name} "{value}"'
                    else:
                        cmd_args += f' --{name} {value}'
        else:
            cmd_args = [self.path]
            for name, value in args.items():
                if name in k_options and value:
                    cmd_args.append(f'--{name}')
                elif name in kv_options:
                    cmd_args.append(f'--{name}')
                    cmd_args.append(f'{value}')
        return cmd_args
