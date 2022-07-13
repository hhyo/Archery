import logging
import traceback
import MySQLdb

# import simplejson as json
import json
from django.contrib.auth.decorators import permission_required

from django.http import HttpResponse

from sql.engines import get_engine
from common.utils.extend_json_encoder import ExtendJSONEncoder, ExtendJSONEncoderBytes
from sql.utils.resource_group import user_instances
from .models import AliyunRdsConfig, Instance

from .aliyun_rds import (
    process_status as aliyun_process_status,
    create_kill_session as aliyun_create_kill_session,
    kill_session as aliyun_kill_session,
    sapce_status as aliyun_sapce_status,
)

logger = logging.getLogger("default")

# 问题诊断--进程列表
@permission_required("sql.process_view", raise_exception=True)
def process(request):
    instance_name = request.POST.get("instance_name")
    command_type = request.POST.get("command_type")

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    query_engine = get_engine(instance=instance)
    query_result = None
    if instance.db_type == "mysql":
        # 判断是RDS还是其他实例
        if AliyunRdsConfig.objects.filter(instance=instance, is_enable=True).exists():
            result = aliyun_process_status(request)
        else:
            query_result = query_engine.processlist(command_type)

    elif instance.db_type == "mongo":
        query_result = query_engine.current_op(command_type)
    else:
        result = {
            "status": 1,
            "msg": "暂时不支持{}类型数据库的进程列表查询".format(instance.db_type),
            "data": [],
        }
        return HttpResponse(json.dumps(result), content_type="application/json")

    if query_result:
        if not query_result.error:
            processlist = query_result.to_dict()
            result = {"status": 0, "msg": "ok", "rows": processlist}
        else:
            result = {"status": 1, "msg": query_result.error}

    # 返回查询结果
    # ExtendJSONEncoderBytes 使用json模块，bigint_as_string只支持simplejson
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoderBytes), content_type="application/json"
    )


# 问题诊断--通过线程id构建请求 这里只是用于确定将要kill的线程id还在运行
@permission_required("sql.process_kill", raise_exception=True)
def create_kill_session(request):
    instance_name = request.POST.get("instance_name")
    thread_ids = request.POST.get("ThreadIDs")

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    result = {"status": 0, "msg": "ok", "data": []}
    query_engine = get_engine(instance=instance)
    if instance.db_type == "mysql":
        # 判断是RDS还是其他实例
        if AliyunRdsConfig.objects.filter(instance=instance, is_enable=True).exists():
            result = aliyun_create_kill_session(request)
        else:
            result["data"] = query_engine.get_kill_command(json.loads(thread_ids))
    elif instance.db_type == "mongo":
        kill_command = query_engine.get_kill_command(json.loads(thread_ids))
        result["data"] = kill_command
    else:
        result = {
            "status": 1,
            "msg": "暂时不支持{}类型数据库通过进程id构建请求".format(instance.db_type),
            "data": [],
        }
        return HttpResponse(json.dumps(result), content_type="application/json")
    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


# 问题诊断--终止会话 这里是实际执行kill的操作
@permission_required("sql.process_kill", raise_exception=True)
def kill_session(request):
    instance_name = request.POST.get("instance_name")
    thread_ids = request.POST.get("ThreadIDs")
    result = {"status": 0, "msg": "ok", "data": []}

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    engine = get_engine(instance=instance)
    r = None
    if instance.db_type == "mysql":
        # 判断是RDS还是其他实例
        if AliyunRdsConfig.objects.filter(instance=instance, is_enable=True).exists():
            result = aliyun_kill_session(request)
        else:
            r = engine.kill(json.loads(thread_ids))
    elif instance.db_type == "mongo":
        r = engine.kill_op(json.loads(thread_ids))
    else:
        result = {
            "status": 1,
            "msg": "暂时不支持{}类型数据库终止会话".format(instance.db_type),
            "data": [],
        }
        return HttpResponse(json.dumps(result), content_type="application/json")

    if r and r.error:
        result = {"status": 1, "msg": r.error, "data": []}
    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


# 问题诊断--表空间信息
@permission_required("sql.tablespace_view", raise_exception=True)
def tablesapce(request):
    instance_name = request.POST.get("instance_name")
    offset = int(request.POST.get("offset", 0))
    limit = int(request.POST.get("limit", 14))
    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    query_engine = get_engine(instance=instance)
    if instance.db_type == "mysql":
        # 判断是RDS还是其他实例
        if AliyunRdsConfig.objects.filter(instance=instance, is_enable=True).exists():
            result = aliyun_sapce_status(request)
        else:
            query_result = query_engine.tablesapce(offset, limit)
            r = query_engine.tablesapce_num()
            total = r.rows[0][0]
    else:
        result = {
            "status": 1,
            "msg": "暂时不支持{}类型数据库的表空间信息查询".format(instance.db_type),
            "data": [],
        }
        return HttpResponse(json.dumps(result), content_type="application/json")

    if query_result:
        if not query_result.error:
            table_space = query_result.to_dict()
            result = {"status": 0, "msg": "ok", "rows": table_space, "total": total}
        else:
            result = {"status": 1, "msg": query_result.error}
    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


# 问题诊断--锁等待
@permission_required("sql.trxandlocks_view", raise_exception=True)
def trxandlocks(request):
    instance_name = request.POST.get("instance_name")

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    query_engine = get_engine(instance=instance)
    if instance.db_type == "mysql":
        query_result = query_engine.trxandlocks()

    else:
        result = {
            "status": 1,
            "msg": "暂时不支持{}类型数据库的锁等待查询".format(instance.db_type),
            "data": [],
        }
        return HttpResponse(json.dumps(result), content_type="application/json")

    if not query_result.error:
        trxandlocks = query_result.to_dict()
        result = {"status": 0, "msg": "ok", "rows": trxandlocks}
    else:
        result = {"status": 1, "msg": query_result.error}

    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


# 问题诊断--长事务
@permission_required("sql.trx_view", raise_exception=True)
def innodb_trx(request):
    instance_name = request.POST.get("instance_name")

    try:
        instance = user_instances(request.user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "你所在组未关联该实例", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    query_engine = get_engine(instance=instance)
    if instance.db_type == "mysql":
        query_result = query_engine.get_long_transaction()
    else:
        result = {
            "status": 1,
            "msg": "暂时不支持{}类型数据库的长事务查询".format(instance.db_type),
            "data": [],
        }
        return HttpResponse(json.dumps(result), content_type="application/json")

    if not query_result.error:
        trx = query_result.to_dict()
        result = {"status": 0, "msg": "ok", "rows": trx}
    else:
        result = {"status": 1, "msg": query_result.error}

    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )
