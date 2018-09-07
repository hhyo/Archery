# -*- coding: UTF-8 -*-
import simplejson as json
from django.http import HttpResponse

from common.utils.permission import superuser_required
from sql.models import Config
from django.db import connection, transaction


class SysConfig(object):
    def __init__(self):
        try:
            # 获取系统配置信息
            all_config = Config.objects.all().values('item', 'value')
            sys_config = {}
            try:
                for items in all_config:
                    sys_config[items['item']] = items['value'].strip()
            except Exception:
                # 关闭后重新获取连接，防止超时
                connection.close()
                for items in all_config:
                    sys_config[items['item']] = items['value'].strip()
        except Exception:
            self.sys_config = {}
        else:
            self.sys_config = sys_config


# 修改系统配置
@superuser_required
def changeconfig(request):
    configs = request.POST.get('configs')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # 清空并替换
    try:
        with transaction.atomic():
            Config.objects.all().delete()
            Config.objects.bulk_create(
                [Config(item=items['key'], value=items['value']) for items in json.loads(configs)])
    except Exception as e:
        result['status'] = 1
        result['msg'] = str(e)

    # 返回结果
    return HttpResponse(json.dumps(result), content_type='application/json')
