# -*- coding: UTF-8 -*-
from sql.models import Config


class SysConfig(object):
    def __init__(self):
        # 获取系统配置信息
        all_config = Config.objects.all().values('item', 'value')
        sys_config = {}
        for items in all_config:
            sys_config[items['item']] = items['value']
        self.sys_config = sys_config
