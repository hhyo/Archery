import subprocess

import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse

from common.config import SysConfig
from sql.models import Instance
from sql.utils.group import user_instances
from sql.sql_workflow import prpCryptor


# 获取SQLAdvisor的优化结果
@permission_required('sql.optimize_sqladvisor', raise_exception=True)
def sqladvisorcheck(request):
    sqlContent = request.POST.get('sql_content')
    instance_name = request.POST.get('instance_name')
    dbName = request.POST.get('db_name')
    verbose = request.POST.get('verbose')
    finalResult = {'status': 0, 'msg': 'ok', 'data': []}

    # 服务器端参数验证
    if sqlContent is None or instance_name is None:
        finalResult['status'] = 1
        finalResult['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')

    sqlContent = sqlContent.strip()
    if sqlContent[-1] != ";":
        finalResult['status'] = 1
        finalResult['msg'] = 'SQL语句结尾没有以;结尾，请重新修改并提交！'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')
    try:
        user_instances(request.user, 'master').get(instance_name=instance_name)
    except Exception:
        finalResult['status'] = 1
        finalResult['msg'] = '你所在组未关联该主库！'
        return HttpResponse(json.dumps(finalResult), content_type='application/json')

    if verbose is None or verbose == '':
        verbose = 1

    # 取出主库的连接信息
    instance_info = Instance.objects.get(instance_name=instance_name)

    # 提交给sqladvisor获取审核结果
    sqladvisor_path = SysConfig().sys_config.get('sqladvisor')
    sqlContent = sqlContent.strip().replace('"', '\\"').replace('`', '\`').replace('\n', ' ')
    try:
        p = subprocess.Popen(sqladvisor_path + ' -h "%s" -P "%s" -u "%s" -p "%s\" -d "%s" -v %s -q "%s"' % (
            str(instance_info.host), str(instance_info.port), str(instance_info.user),
            str(prpCryptor.decrypt(instance_info.password), ), str(dbName), verbose, sqlContent),
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
        stdout, stderr = p.communicate()
        finalResult['data'] = stdout
    except Exception:
        finalResult['data'] = 'sqladvisor运行报错，请联系管理员'
    return HttpResponse(json.dumps(finalResult), content_type='application/json')
