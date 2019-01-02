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
        # 优先获取缓存数据
        try:
            sys_config = cache.get('sys_config')
        except Exception:
            sys_config = None
            logger.error(traceback.format_exc())

        # 缓存获取失败从数据库获取并且更新缓存
        if sys_config:
            self.sys_config = sys_config
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
                    sys_config[items['item']] = items['value']
                self.sys_config = sys_config
                # 增加缓存
                try:
                    cache.add('sys_config', self.sys_config, timeout=None)
                except Exception:
                    logger.error(traceback.format_exc())
            except Exception:
                self.sys_config = {}

    def get(self, key, default_value=None):
        value = self.sys_config.get(key, default_value)
        if value == 'false' or value == 'False':
            return False
        if value == 'true' or value == 'True':
            return True
        if value.strip() == '':
            return default_value
        return value

    def set(self, key, value):
        if value is True:
            value = 'true'
        elif value is False:
            value = 'false'
        # 删除并更新缓存
        try:
            cache.delete('sys_config')
        except Exception:
            logger.error(traceback.format_exc())
        finally:
            self.get_all_config()
        config_item, created = Config.objects.get_or_create(item=key)
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
            try:
                cache.delete('sys_config')
            except Exception:
                logger.error(traceback.format_exc())
            finally:
                self.get_all_config()
        return result


# 修改系统配置
@superuser_required
def changeconfig(request):
    configs = request.POST.get('configs')
    archer_config = SysConfig()
    result = archer_config.replace(configs)
    # 返回结果
    return HttpResponse(json.dumps(result), content_type='application/json')
