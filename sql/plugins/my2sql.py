# -*- coding: UTF-8 -*-
from common.config import SysConfig
from sql.plugins.plugin import Plugin


class My2SQL(Plugin):
    def __init__(self):
        self.path = SysConfig().get("my2sql")
        self.required_args = []
        self.disable_args = []
        super(Plugin, self).__init__()
