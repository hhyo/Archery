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
                    cmd_args += f' -{name}="{value}"'
                else:
                    cmd_args += f' -{name}={value}'
        else:
            cmd_args = [self.path]
            for name, value in args.items():
                cmd_args.append(f'-{name}')
                cmd_args.append(f'{value}')
        return cmd_args

    def fingerprint(self, sql):
        """
        输出SQL的指纹
        :param sql:
        :return:
        """
        args = {
            "query": sql.replace('`', ''),
            "report-type": "fingerprint"
        }
        cmd_args = self.generate_args2cmd(args, shell=True)
        return self.execute_cmd(cmd_args=cmd_args, shell=True)

    def compress(self, sql):
        """
        压缩SQL
        :param sql:
        :return:
        """
        args = {
            "query": sql.replace('`', ''),
            "report-type": "compress"
        }
        cmd_args = self.generate_args2cmd(args, shell=True)
        return self.execute_cmd(cmd_args=cmd_args, shell=True)

    def pretty(self, sql):
        """
        美化SQL
        :param sql:
        :return:
        """
        args = {
            "query": sql.replace('`', ''),
            "max-pretty-sql-length": 100000,  # 超出该长度的SQL会转换成指纹输出 (default 1024)
            "report-type": "pretty"
        }
        cmd_args = self.generate_args2cmd(args, shell=True)
        return self.execute_cmd(cmd_args=cmd_args, shell=True)

    def remove_comment(self, sql):
        """
        去除SQL语句中的注释，支持单行多行注释的去除
        :param sql:
        :return:
        """
        args = {
            "query": sql.replace('`', ''),
            "report-type": "remove-comment"
        }
        cmd_args = self.generate_args2cmd(args, shell=True)
        return self.execute_cmd(cmd_args=cmd_args, shell=True)

    def rewrite(self, sql, rewrite_rules=None):
        """
        SQL改写
        :param sql:
        :param rewrite_rules:
        :return:
        """
        rewrite_type_list = ['dml2select', 'star2columns', 'insertcolumns', 'having', 'orderbynull', 'unionall',
                             'or2in', 'dmlorderby', 'distinctstar', 'standard', 'mergealter', 'alwaystrue',
                             'countstar', 'innodb', 'autoincrement', 'intwidth', 'truncate', 'rmparenthesis',
                             'delimiter']
        rewrite_rules = rewrite_rules if rewrite_rules else ['dml2select']
        if set(rewrite_rules).issubset(set(rewrite_type_list)) is False:
            raise RuntimeError(f'不支持的改写规则，仅支持{rewrite_type_list}')
        args = {
            "query": sql.replace('`', ''),
            "report-type": "rewrite",
            "rewrite-rules": ','.join(rewrite_type_list)
        }
        cmd_args = self.generate_args2cmd(args, shell=True)
        return self.execute_cmd(cmd_args=cmd_args, shell=True)

    def query_tree(self, sql):
        """
        语法树打印，包括[ast, tiast, ast-json, tiast-json]
        :param sql:
        :return:
        """
        args = {
            "query": sql.replace('`', ''),
            "report-type": "ast-json"
        }
        cmd_args = self.generate_args2cmd(args, shell=True)
        return self.execute_cmd(cmd_args=cmd_args, shell=True)
