# -*- coding: UTF-8 -*-
from sql.models import Config
from django.db import connection


class SysConfig(object):
    def __init__(self):
        try:
            # 获取系统配置信息
            all_config = Config.objects.all().values('item', 'value')
            sys_config = {}
            try:
                for items in all_config:
                    sys_config[items['item']] = items['value']
            except Exception:
                # 关闭后重新获取连接，防止超时
                connection.close()
                for items in all_config:
                    sys_config[items['item']] = items['value']
        except Exception:
            self.sys_config = {}
        else:
            self.sys_config = sys_config
