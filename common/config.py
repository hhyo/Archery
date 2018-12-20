# -*- coding: UTF-8 -*-
import logging
import traceback

import simplejson as json
from django.http import HttpResponse

from common.utils.permission import superuser_required
from sql.models import Config
from django.db import transaction
from django.core.cache import cache

logger = logging.getLogger('default')


class SysConfig(object):
    def __init__(self, *args, **kwargs):
        self.get_all_config()
    def get_all_config(self):
        if cache.get('sys_config'):
            self.sys_config = cache.get('sys_config')
        else:
            try:
                # 获取系统配置信息
                all_config = Config.objects.all().values('item', 'value')
                sys_config = {}
                for items in all_config:
                    if items['value'] == 'true':
                        items['value'] = True
                    elif items['value'] == 'false':
                        items['value'] = False
                    else:
                        pass
                    sys_config[items['item']] = items['value']
                self.sys_config = sys_config
                # 增加缓存
                cache.add('sys_config', self.sys_config, timeout=None)
            except Exception:
                self.sys_config = {}
    def get(self, key, default_value=None):
        value =  self.sys_config.get(key,default_value)
        if value == 'false' or value == 'False':
            return False
        if value == 'true' or value == 'True':
            return True
        return value

    def set(self, key, value):
        if value == True:
            value = 'true'
        elif value == False:
            value = 'false'
        cache.delete('sys_config')
        config_item, created = Config.objects.get_or_create(item = key)
        config_item.value = value
        config_item.save()
    def replace(self, configs):
        result = {'status': 0, 'msg': 'ok', 'data': []}

        # 清空并替换
        try:
            with transaction.atomic():
                Config.objects.all().delete()
                Config.objects.bulk_create(
                    [Config(item=items['key'], value=items['value']) for items in json.loads(configs)])
        except Exception as e:
            logger.error(traceback.format_exc())
            result['status'] = 1
            result['msg'] = str(e)
        else:
            # 删除并更新缓存
            cache.delete('sys_config')
            SysConfig()
        return result

# 修改系统配置
@superuser_required
def changeconfig(request):
    configs = request.POST.get('configs')
    archer_config = SysConfig()
    result = archer_config.replace(configs)
    # 返回结果
    return HttpResponse(json.dumps(result), content_type='application/json')
