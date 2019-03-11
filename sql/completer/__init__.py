# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: completion_engines.py
@time: 2019/03/09
"""

__author__ = 'hhyo'


class Completer:
    @property
    def name(self):
        """返回engine名称"""
        return 'Completer engine'

    @property
    def info(self):
        """返回引擎简介"""
        return 'Base Completer engine'

    def _get_sql_execute(self):
        """
        初始化数据库执行连接
        :return:
        """

    def refresh_completions(self, reset=False):
        """
        刷新completer对象元数据
        :param reset:
        :return:
        """

    def _on_completions_refreshed(self, new_completer):
        """
        刷新completer对象回调函数，替换对象
        :param new_completer:
        :return:
        """

    def get_completions(self, text, cursor_position):
        """
        获取补全提示
        :param text:
        :param cursor_position:
        :return:
        """

    @staticmethod
    def convert2ace_js(completions):
        """
        转换completions为ace.js所需要的补全列表格式[{"caption":,"meta":,"name":,"value":,"score":]
        caption ：字幕，也就是展示在列表中的内容
        meta ：展示类型
        name ：名称
        value ：值
        score ：分数，越大的排在越上面
        :return:
        """
        ace_completions = []
        for completion in completions:
            comp = dict()
            comp["caption"] = completion.display
            comp["meta"] = completion.display_meta
            comp["name"] = ''
            comp["value"] = ''
            comp["score"] = completion.start_position
            ace_completions.append(comp)
        return ace_completions


def get_comp_engine(instance=None, db_name=None):
    """获取SQL补全engine"""
    if instance.db_type == 'mysql':
        from .mysql import MysqlComEngine
        return MysqlComEngine(instance=instance, db_name=db_name)
