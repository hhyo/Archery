# -*- coding:utf-8 -*-
import logging
import subprocess
import traceback

import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpResponse
from common.config import SysConfig
from common.utils.aes_decryptor import Prpcrypt
from sql.models import Instance
from sql.utils.group import user_instances

logger = logging.getLogger('default')


class Soar(PermissionRequiredMixin):
    permission_required = 'sql.optimize_soar'
    raise_exception = True

    def __init__(self):
        self.soar_path = SysConfig().sys_config.get('soar')
        self.soar_test_dsn = SysConfig().sys_config.get('soar_test_dsn')


# 获取soar的处理结果
@permission_required('sql.optimize_soar', raise_exception=True)
def soar(request):
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    sql = request.POST.get('sql')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # 服务器端参数验证
    if not (instance_name and db_name and sql):
        result['status'] = 1
        result['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(result), content_type='application/json')
    try:
        user_instances(request.user, 'master').get(instance_name=instance_name)
    except Exception:
        result['status'] = 1
        result['msg'] = '你所在组未关联该实例'
        return HttpResponse(json.dumps(result), content_type='application/json')

    sql = sql.strip().replace('"', '\\"').replace('`', '\`').replace('\n', ' ')
    # 目标实例的连接信息
    instance_info = Instance.objects.get(instance_name=instance_name)
    online_dsn = "{user}:{pwd}@{host}:{port}/{db}".format(user=instance_info.user,
                                                          pwd=Prpcrypt().decrypt(instance_info.password),
                                                          host=instance_info.host,
                                                          port=instance_info.port,
                                                          db=db_name)
    # 获取测试实例的连接信息和soar程序路径
    soar_cfg = Soar()
    test_dsn = soar_cfg.soar_test_dsn
    soar_path = soar_cfg.soar_path
    if not (soar_path and test_dsn):
        result['status'] = 1
        result['msg'] = '请配置soar_path和test_dsn！'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 提交给soar获取分析报告
    try:
        p = subprocess.Popen(
            soar_path + ' -allow-online-as-test=false -report-type=markdown' +
            ' -query "{}" -online-dsn "{}" -test-dsn "{}" '.format(sql.strip(), online_dsn, test_dsn),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True,
            universal_newlines=True)
        stdout, stderr = p.communicate()
        result['data'] = stdout
    except Exception:
        logger.error(traceback.format_exc())
        result['data'] = 'soar运行报错，请检查相关日志'
    return HttpResponse(json.dumps(result), content_type='application/json')
