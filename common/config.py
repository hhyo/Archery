# -*- coding: UTF-8 -*-
import logging
import traceback

import simplejson as json
from django.http import HttpResponse

from common.utils.permission import superuser_required
from sql.models import Config
from django.db import transaction

logger = logging.getLogger('default')


class SysConfig(object):
    def __init__(self):
        self.sys_config = {}
        self.get_all_config()

    def get_all_config(self):
        try:
            # 获取系统配置信息
            all_config = Config.objects.all().values('item', 'value')
            sys_config = {}
            for items in all_config:
                if items['value'] in ('true', 'True'):
                    items['value'] = True
                elif items['value'] in ('false', 'False'):
                    items['value'] = False
                sys_config[items['item']] = items['value']
            self.sys_config = sys_config
        except Exception as m:
            logger.error(f"获取系统配置信息失败:{m}{traceback.format_exc()}")
            self.sys_config = {}

    def get(self, key, default_value=None):
        value = self.sys_config.get(key, default_value)
        # 是字符串的话, 如果是空, 或者全是空格, 返回默认值
        if isinstance(value, str) and value.strip() == '':
            return default_value
        return value

    def set(self, key, value):
        if value is True:
            db_value = 'true'
        elif value is False:
            db_value = 'false'
        else:
            db_value = value
        obj, created = Config.objects.update_or_create(item=key, defaults={"value": db_value})
        if created:
            self.sys_config.update({key: value})

    def replace(self, configs):
        result = {'status': 0, 'msg': 'ok', 'data': []}
        # 清空并替换
        try:
            with transaction.atomic():
                self.purge()
                Config.objects.bulk_create(
                    [Config(item=items['key'].strip(),
                            value=str(items['value']).strip()) for items in json.loads(configs)])
        except Exception as e:
            logger.error(traceback.format_exc())
            result['status'] = 1
            result['msg'] = str(e)
        finally:
            self.get_all_config()
        return result

    def purge(self):
        """清除所有配置, 供测试以及replace方法使用"""
        try:
            with transaction.atomic():
                Config.objects.all().delete()
                self.sys_config = {}
        except Exception as m:
            logger.error(f"删除缓存失败:{m}{traceback.format_exc()}")


# 修改系统配置
@superuser_required
def change_config(request):
    configs = request.POST.get('configs')
    archer_config = SysConfig()
    result = archer_config.replace(configs)
    # 返回结果
    return HttpResponse(json.dumps(result), content_type='application/json')
