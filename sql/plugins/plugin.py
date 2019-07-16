# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: plugin.py 
@time: 2019/03/04
"""
__author__ = 'hhyo'

import logging
import subprocess
import traceback

logger = logging.getLogger('default')


class Plugin:
    def __init__(self, path):
        self.path = path
        self.required_args = []  # 必须参数
        self.disable_args = []  # 禁用参数

    def check_args(self, args):
        """
        检查请求参数列表
        :return: {'status': 0, 'msg': 'ok', 'data': {}}
        """
        args_check_result = {'status': 0, 'msg': 'ok', 'data': {}}
        # 检查路径
        if self.path is None:
            return {'status': 1, 'msg': '可执行文件路径不能为空！', 'data': {}}
        # 检查禁用参数
        for arg in args.keys():
            if arg in self.disable_args:
                return {'status': 1, 'msg': '{arg}参数已被禁用'.format(arg=arg), 'data': {}}
        # 检查必须参数
        for req_arg in self.required_args:
            if req_arg not in args.keys():
                return {'status': 1, 'msg': '必须指定{arg}参数'.format(arg=req_arg), 'data': {}}
            elif args[req_arg] is None or args[req_arg] == '':
                return {'status': 1, 'msg': '{arg}参数值不能为空'.format(arg=req_arg), 'data': {}}
        return args_check_result

    def generate_args2cmd(self, args, shell):
        """
        将请求参数转换为命令行参数
        :return:
        """

    @staticmethod
    def execute_cmd(cmd_args, shell):
        """
        执行命令并且返回process
        :return:
        """
        try:
            p = subprocess.Popen(cmd_args,
                                 shell=shell,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 universal_newlines=True)
            return p
        except Exception as e:
            logger.error("命令执行失败\n{}".format(traceback.format_exc()))
            raise RuntimeError('命令执行失败，失败原因:%s' % str(e))
