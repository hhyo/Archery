# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: mysql.py 
@time: 2019/03/09
"""
import threading

import mycli.sqlcompleter as completer
from prompt_toolkit.document import Document
from mycli.completion_refresher import CompletionRefresher
from mycli.sqlexecute import SQLExecute
from . import Completer

__author__ = 'hhyo'


class MysqlComEngine(Completer):
    def __init__(self, instance=None, db_name=None):
        self.instance = instance
        self.db_name = db_name
        self.completion_refresher = CompletionRefresher()
        self.completer = completer.SQLCompleter(smart_completion=True)
        self._completer_lock = threading.Lock()
        self.sql_execute = self._get_sql_execute()
        self.refresh_completions()

    def _get_sql_execute(self):
        """
        初始化数据库执行连接
        :return:
        """
        return SQLExecute(self.db_name, self.instance.user, self.instance.raw_password, self.instance.host,
                          int(self.instance.port),
                          socket='', charset=self.instance.charset or 'utf8mb4',
                          local_infile='', ssl='', ssh_user='', ssh_host='', ssh_port='',
                          ssh_password='', ssh_key_filename=''
                          )

    def refresh_completions(self, reset=False):
        """
        刷新completer对象元数据
        :param reset:
        :return:
        """
        if reset:
            with self._completer_lock:
                self.completer.reset_completions()
        self.completion_refresher.refresh(self.sql_execute, self._on_completions_refreshed)
        return [(None, None, None, 'Auto-completion refresh started in the background.')]

    def _on_completions_refreshed(self, new_completer):
        """
        刷新completer对象回调函数，替换对象
        :param new_completer:
        :return:
        """
        with self._completer_lock:
            self.completer = new_completer

    def get_completions(self, text, cursor_position):
        """
        获取补全提示
        :param text:
        :param cursor_position:
        :return:
        """
        with self._completer_lock:
            return self.completer.get_completions(
                Document(text=text, cursor_position=cursor_position), None)
