# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: binglog2sql.py 
@time: 2019/03/23
"""
from common.config import SysConfig
from sql.plugins.plugin import Plugin

__author__ = 'hhyo'


class Binlog2Sql(Plugin):

    def __init__(self):
        self.path = SysConfig().get('binlog2sql')
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
        conn_options = ['conn_options']
        parse_mode_options = ['stop-never', 'no-primary-key', 'flashback', 'back-interval']
        range_options = ['start-file', 'start-position', 'stop-file', 'stop-position', 'start-datetime',
                         'stop-datetime']
        filter_options = ['databases', 'tables', 'only-dml', 'sql-type']
        if shell:
            cmd_args = f'python {self.path}' if self.path else ''
            for name, value in args.items():
                if name in conn_options:
                    cmd_args += f' {value}'
                elif name in parse_mode_options and value:
                    cmd_args += f' --{name}'
                elif name in range_options and value:
                    cmd_args += f" --{name}='{value}'"
                elif name in filter_options and value:
                    if name == 'only-dml':
                        cmd_args += f' --{name}'
                    else:
                        cmd_args += f' --{name} {value}'
        else:
            cmd_args = [self.path]
            for name, value in args.items():
                if name in conn_options:
                    cmd_args.append(f'{value}')
                elif name in parse_mode_options:
                    cmd_args.append(f'--{name}')
                elif name in range_options:
                    cmd_args.append(f'--{name}')
                    cmd_args.append(f'{value}')
                elif name in filter_options:
                    cmd_args.append(f'--{name}')
                    cmd_args.append(f'{value}')
        return cmd_args
