# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence 
@file: soar.py 
@time: 2019/03/04
"""
__author__ = 'hhyo'

from common.config import SysConfig
from sql.plugins.plugin import Plugin


class Soar(Plugin):

    def __init__(self):
        self.path = SysConfig().get('soar')
        self.required_args = ['query']
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
                if name in ['query', 'online-dsn', 'test-dsn']:
                    cmd_args = cmd_args + ' ' + '-{name}="{value}"'.format(name=str(name), value=str(value))
                else:
                    cmd_args = cmd_args + ' ' + '-{name}={value}'.format(name=str(name), value=str(value))
        else:
            cmd_args = [self.path]
            for name, value in args.items():
                cmd_args.append('-%s' % str(name))
                cmd_args.append('%s' % str(value))
        return cmd_args
