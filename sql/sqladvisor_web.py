# -*- coding: UTF-8 -*-
import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from common.config import SysConfig
from sql.models import Instance
from sql.utils.resource_group import user_instances
from sql.plugins.sqladvisor import SQLAdvisor


# 获取SQLAdvisor的优化结果
@permission_required('sql.optimize_sqladvisor', raise_exception=True)
def optimize_sqladvisor(request):
    sql_content = request.POST.get('sql_content')
    instance_name = request.POST.get('instance_name')
    db_name = request.POST.get('db_name')
    verbose = request.POST.get('verbose', 1)
    result = {'status': 0, 'msg': 'ok', 'data': []}

    # 服务器端参数验证
    if sql_content is None or instance_name is None:
        result['status'] = 1
        result['msg'] = '页面提交参数可能为空'
        return HttpResponse(json.dumps(result), content_type='application/json')

    try:
        user_instances(request.user, 'all').get(instance_name=instance_name)
    except Exception:
        result['status'] = 1
        result['msg'] = '你所在组未关联该实例！'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 检查sqladvisor程序路径
    sqladvisor_path = SysConfig().get('sqladvisor')
    if sqladvisor_path is None:
        result['status'] = 1
        result['msg'] = '请配置SQLAdvisor路径！'
        return HttpResponse(json.dumps(result), content_type='application/json')

    # 取出实例的连接信息
    instance_info = Instance.objects.get(instance_name=instance_name)

    # 提交给sqladvisor获取分析报告
    sqladvisor = SQLAdvisor()
    # 准备参数
    args = {"h": instance_info.host,
            "P": instance_info.port,
            "u": instance_info.user,
            "p": instance_info.raw_password,
            "d": db_name,
            "v": verbose,
            "q": sql_content.strip().replace('"', '\\"').replace('`', '').replace('\n', ' ')
            }

    # 参数检查
    args_check_result = sqladvisor.check_args(args)
    if args_check_result['status'] == 1:
        return HttpResponse(json.dumps(args_check_result), content_type='application/json')
    # 参数转换
    cmd_args = sqladvisor.generate_args2cmd(args, shell=True)
    # 执行命令
    try:
        result['data'] = sqladvisor.execute_cmd(cmd_args, shell=True)
    except RuntimeError as e:
        result['status'] = 1
        result['msg'] = str(e)
    return HttpResponse(json.dumps(result), content_type='application/json')
