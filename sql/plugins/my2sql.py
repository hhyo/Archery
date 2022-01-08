# -*- coding: UTF-8 -*-
from common.config import SysConfig
from sql.plugins.plugin import Plugin
import shlex


class My2SQL(Plugin):

    def __init__(self):
        self.path = SysConfig().get('my2sql')
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
        args_options = ['work-type', 'threads', 'start-file', 'stop-file', 'start-pos',
                        'stop-pos', 'databases', 'tables', 'sql', 'output-dir']
        no_args_options = ['output-toScreen', 'add-extraInfo', 'ignore-primaryKey-forInsert',
                           'full-columns', 'do-not-add-prifixDb', 'file-per-table']
        datetime_options = ['start-datetime', 'stop-datetime']
        if shell:
            cmd_args = f'{shlex.quote(str(self.path))}' if self.path else ''
            for name, value in args.items():
                if name in conn_options:
                    cmd_args += f' {value}'
                elif name in args_options and value:
                    cmd_args += f' -{name} {shlex.quote(str(value))}'
                elif name in datetime_options and value:
                    cmd_args += f" -{name} '{shlex.quote(str(value))}'"
                elif name in no_args_options and value:
                    cmd_args += f' -{name}'
        else:
            cmd_args = [self.path]
            for name, value in args.items():
                if name in conn_options:
                    cmd_args.append(f'{value}')
                elif name in args_options:
                    cmd_args.append(f'-{name}')
                    cmd_args.append(f'{value}')
                elif name in datetime_options:
                    cmd_args.append(f'-{name}')
                    cmd_args.append(f"'{value}'")
                elif name in no_args_options:
                    cmd_args.append(f'-{name}')
        return cmd_args
