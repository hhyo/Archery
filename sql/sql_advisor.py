# -*- coding: UTF-8 -*-
import logging
import subprocess
import traceback

import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from common.config import SysConfig
from sql.models import Instance
from sql.utils.resource_group import user_instances

logger = logging.getLogger('default')


# 获取SQLAdvisor的优化结果
@permission_required('sql.optimize_sqladvisor', raise_exception=True)
def sqladvisor(request):
    sql_content = request.POST.get('sql_content')
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    verbose = request.POST.get('verbose')
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # 服务器端参数验证
    if sql_content is None or instance_name is None:
        result['status'] = 1
        result['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(result), content_type='application/json')

    sql_content = sql_content.strip()

    try:
        user_instances(request.user, 'all').get(instance_name=instance_name)
    except Exception:
        result['status'] = 1
        result['msg'] = '你所在组未关联该实例！'
        return HttpResponse(json.dumps(result), content_type='application/json')

    if verbose is None or verbose == '':
        verbose = 1

    # 取出实例的连接信息
    instance_info = Instance.objects.get(instance_name=instance_name)

    # 提交给sqladvisor获取审核结果
    sqladvisor_path = SysConfig().get('sqladvisor')
    sql_content = sql_content.strip().replace('"', '\\"').replace('`', '').replace('\n', ' ')
    try:
        p = subprocess.Popen(sqladvisor_path + ' -h "%s" -P "%s" -u "%s" -p "%s\" -d "%s" -v %s -q "%s"' % (
            str(instance_info.host), str(instance_info.port), str(instance_info.user),
            str(instance_info.raw_password), str(db_name), verbose, sql_content),
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
        stdout, stderr = p.communicate()
        result['data'] = stdout
    except Exception:
        logger.error(traceback.format_exc())
        result['data'] = 'sqladvisor运行报错，请检查日志'
    return HttpResponse(json.dumps(result), content_type='application/json')
