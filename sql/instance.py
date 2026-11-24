# -*- coding: UTF-8 -*-

import logging
import os
import time

import simplejson as json
from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse
from django.views.decorators.cache import cache_page

from common.utils.extend_json_encoder import ExtendJSONEncoder
from common.utils.convert import Convert
from sql.engines import get_engine
from sql.services.resource_service import list_instance_resources
from sql.plugins.schemasync import SchemaSync
from sql.utils.sql_utils import filter_db_list
from .models import Instance, ParamTemplate, ParamHistory

logger = logging.getLogger("default")


GAUSSDB_PARAM_TEMPLATES = [
    {
        "variable_name": "statement_timeout",
        "default_value": "0",
        "editable": True,
        "valid_values": "[0-2147483647]",
        "description": "单条语句最大执行时间，单位毫秒；0 表示不限制。",
    },
    {
        "variable_name": "lockwait_timeout",
        "default_value": "1200000",
        "editable": True,
        "valid_values": "[0-2147483647]",
        "description": "等待锁的超时时间，单位毫秒。",
    },
    {
        "variable_name": "work_mem",
        "default_value": "4MB",
        "editable": True,
        "valid_values": "内存大小，例如 4MB、64MB。",
        "description": "排序、哈希等操作可使用的工作内存。",
    },
    {
        "variable_name": "enable_seqscan",
        "default_value": "on",
        "editable": True,
        "valid_values": "[on|off]",
        "description": "控制优化器是否启用顺序扫描计划。",
    },
    {
        "variable_name": "enable_indexscan",
        "default_value": "on",
        "editable": True,
        "valid_values": "[on|off]",
        "description": "控制优化器是否启用索引扫描计划。",
    },
    {
        "variable_name": "max_connections",
        "default_value": "5000",
        "editable": False,
        "valid_values": "需重启或通过实例参数组维护。",
        "description": "实例最大连接数。",
    },
    {
        "variable_name": "shared_buffers",
        "default_value": "128MB",
        "editable": False,
        "valid_values": "需重启或通过实例参数组维护。",
        "description": "数据库共享缓冲区大小。",
    },
]

# KES parameter templates, derived from KEMCC.
KES_PARAM_TEMPLATES = [
    {
        "variable_name": "track_counts",
        "default_value": "on",
        "editable": True,
        "valid_values": "on / off",
        "description": "是否收集表和索引的访问统计信息。",
    },
    {
        "variable_name": "track_sql",
        "default_value": "off",
        "editable": True,
        "valid_values": "on / off",
        "description": "是否开启 SQL 语句级的时间、等待、IO 统计。",
    },
    {
        "variable_name": "track_instance",
        "default_value": "off",
        "editable": True,
        "valid_values": "on / off",
        "description": "是否开启实例级 IO、关键活动、锁统计。",
    },
    {
        "variable_name": "track_wait_timing",
        "default_value": "on",
        "editable": True,
        "valid_values": "on / off",
        "description": "是否累积记录等待事件的等待时间。",
    },
    {
        "variable_name": "track_io_timing",
        "default_value": "off",
        "editable": True,
        "valid_values": "on / off",
        "description": "是否统计 IO 调用耗时，开启会有额外开销。",
    },
    {
        "variable_name": "track_functions",
        "default_value": "none",
        "editable": True,
        "valid_values": "none / pl / all",
        "description": "统计函数调用的方式。",
    },
    {
        "variable_name": "sys_kwr.enable",
        "default_value": "on",
        "editable": True,
        "valid_values": "on / off",
        "description": "是否启用 KWR 性能报告自动采集。",
    },
    {
        "variable_name": "sys_stat_statements.max",
        "default_value": "5000",
        "editable": True,
        "valid_values": "[100-2147483647]",
        "description": "sys_stat_statements 记录的最大语句数。",
    },
    {
        "variable_name": "sys_stat_statements.track",
        "default_value": "top",
        "editable": True,
        "valid_values": "none / top / all",
        "description": "sys_stat_statements 的跟踪级别。",
    },
    {
        "variable_name": "max_connections",
        "default_value": "100",
        "editable": False,
        "valid_values": "[1-262143]，需重启生效",
        "description": "数据库允许的最大并发连接数。",
    },
    {
        "variable_name": "shared_buffers",
        "default_value": "128MB",
        "editable": False,
        "valid_values": "需重启生效",
        "description": "数据库共享缓冲区大小。",
    },
    {
        "variable_name": "work_mem",
        "default_value": "4MB",
        "editable": True,
        "valid_values": "内存大小，例如 4MB、64MB",
        "description": "排序、哈希等操作可使用的工作内存。",
    },
    {
        "variable_name": "maintenance_work_mem",
        "default_value": "64MB",
        "editable": True,
        "valid_values": "内存大小，例如 64MB、256MB",
        "description": "维护操作（VACUUM、CREATE INDEX 等）可使用的内存。",
    },
    {
        "variable_name": "temp_buffers",
        "default_value": "8MB",
        "editable": True,
        "valid_values": "内存大小，例如 8MB、32MB",
        "description": "每个会话可用的临时缓冲区大小。",
    },
    {
        "variable_name": "effective_cache_size",
        "default_value": "4GB",
        "editable": True,
        "valid_values": "内存大小估算值",
        "description": "规划器对操作系统缓存的估算，仅影响代价计算。",
    },
    {
        "variable_name": "huge_pages",
        "default_value": "try",
        "editable": False,
        "valid_values": "try / on / off，需重启生效",
        "description": "是否使用大页内存。",
    },
    {
        "variable_name": "temp_file_limit",
        "default_value": "-1",
        "editable": True,
        "valid_values": "[-1-2147483647]，单位 kB",
        "description": "单个进程可用的临时文件空间上限，-1 不限制。",
    },
    {
        "variable_name": "statement_timeout",
        "default_value": "0",
        "editable": True,
        "valid_values": "[0-2147483647]，单位毫秒",
        "description": "单条语句最大执行时间，0 表示不限制。",
    },
    {
        "variable_name": "lock_timeout",
        "default_value": "0",
        "editable": True,
        "valid_values": "[0-2147483647]，单位毫秒",
        "description": "等待锁的最长时间，0 表示不限制。",
    },
    {
        "variable_name": "idle_in_transaction_session_timeout",
        "default_value": "0",
        "editable": True,
        "valid_values": "[0-2147483647]，单位毫秒",
        "description": "事务空闲超时，超时后断开连接。",
    },
    {
        "variable_name": "deadlock_timeout",
        "default_value": "1s",
        "editable": True,
        "valid_values": "时间值，例如 1s、2s",
        "description": "死锁检测前的等待时间。",
    },
    {
        "variable_name": "max_locks_per_transaction",
        "default_value": "64",
        "editable": False,
        "valid_values": "[10-2147483647]，需重启生效",
        "description": "每个事务可持有的锁数量上限。",
    },
    {
        "variable_name": "log_min_duration_statement",
        "default_value": "-1",
        "editable": True,
        "valid_values": "[-1-2147483647]，单位毫秒",
        "description": "慢 SQL 记录阈值，-1 不记录，0 记录全部。",
    },
    {
        "variable_name": "log_statement",
        "default_value": "none",
        "editable": True,
        "valid_values": "none / ddl / mod / all",
        "description": "记录哪些 SQL 语句。",
    },
    {
        "variable_name": "log_checkpoints",
        "default_value": "on",
        "editable": True,
        "valid_values": "on / off",
        "description": "是否记录检查点活动。",
    },
    {
        "variable_name": "log_lock_waits",
        "default_value": "off",
        "editable": True,
        "valid_values": "on / off",
        "description": "是否记录锁等待超过 deadlock_timeout 的事件。",
    },
    {
        "variable_name": "log_temp_files",
        "default_value": "-1",
        "editable": True,
        "valid_values": "[-1-2147483647]，单位 kB",
        "description": "记录超过指定大小的临时文件使用。",
    },
    {
        "variable_name": "log_autovacuum_min_duration",
        "default_value": "-1",
        "editable": True,
        "valid_values": "[-1-2147483647]，单位毫秒",
        "description": "记录超过指定时长的 autovacuum 操作。",
    },
    {
        "variable_name": "enable_seqscan",
        "default_value": "on",
        "editable": True,
        "valid_values": "on / off",
        "description": "是否允许规划器使用顺序扫描。",
    },
    {
        "variable_name": "enable_indexscan",
        "default_value": "on",
        "editable": True,
        "valid_values": "on / off",
        "description": "是否允许规划器使用索引扫描。",
    },
    {
        "variable_name": "random_page_cost",
        "default_value": "4",
        "editable": True,
        "valid_values": "浮点数，默认 4",
        "description": "随机磁盘页的代价估算。",
    },
    {
        "variable_name": "default_statistics_target",
        "default_value": "100",
        "editable": True,
        "valid_values": "[1-10000]",
        "description": "ANALYZE 采样的统计目标值。",
    },
    {
        "variable_name": "wal_level",
        "default_value": "replica",
        "editable": False,
        "valid_values": "minimal / replica / logical，需重启生效",
        "description": "WAL 记录的详细程度。",
    },
    {
        "variable_name": "wal_buffers",
        "default_value": "16MB",
        "editable": False,
        "valid_values": "需重启生效",
        "description": "WAL 缓冲区大小。",
    },
    {
        "variable_name": "wal_compression",
        "default_value": "off",
        "editable": True,
        "valid_values": "on / off",
        "description": "是否压缩 WAL 中的全页写。",
    },
    {
        "variable_name": "synchronous_commit",
        "default_value": "on",
        "editable": True,
        "valid_values": "on / off / local / remote_write / remote_apply",
        "description": "事务提交的同步级别。",
    },
    {
        "variable_name": "checkpoint_timeout",
        "default_value": "5min",
        "editable": True,
        "valid_values": "时间值，例如 5min、20min",
        "description": "两次检查点之间的最长间隔。",
    },
    {
        "variable_name": "checkpoint_completion_target",
        "default_value": "0.9",
        "editable": True,
        "valid_values": "[0-1]",
        "description": "检查点写盘的平滑系数。",
    },
    {
        "variable_name": "max_wal_size",
        "default_value": "1GB",
        "editable": True,
        "valid_values": "内存/容量值，例如 1GB、64GB",
        "description": "触发检查点的 WAL 最大容量。",
    },
    {
        "variable_name": "min_wal_size",
        "default_value": "80MB",
        "editable": True,
        "valid_values": "内存/容量值",
        "description": "WAL 文件保留的最小容量。",
    },
    {
        "variable_name": "fsync",
        "default_value": "on",
        "editable": False,
        "valid_values": "on / off，需重启生效",
        "description": "是否强制将数据刷写到磁盘。",
    },
]


def ensure_builtin_param_templates(db_type):
    """补齐内置参数模板，避免新引擎在参数页没有可展示项。"""
    if db_type not in ("gaussdb", "kingbase"):
        return
    templates = GAUSSDB_PARAM_TEMPLATES if db_type == "gaussdb" else KES_PARAM_TEMPLATES
    for param in templates:
        ParamTemplate.objects.get_or_create(
            db_type=db_type,
            variable_name=param["variable_name"],
            defaults={
                "default_value": param["default_value"],
                "editable": param["editable"],
                "valid_values": param["valid_values"],
                "description": param["description"],
            },
        )


@permission_required("sql.menu_instance_list", raise_exception=True)
def lists(request):
    """获取实例列表"""
    limit = int(request.POST.get("limit"))
    offset = int(request.POST.get("offset"))
    type = request.POST.get("type")
    db_type = request.POST.get("db_type")
    tags = request.POST.getlist("tags[]")
    limit = offset + limit
    search = request.POST.get("search", "")
    sortName = str(request.POST.get("sortName"))
    sortOrder = str(request.POST.get("sortOrder")).lower()

    # 组合筛选项
    filter_dict = dict()
    # 过滤搜索
    if search:
        filter_dict["instance_name__icontains"] = search
    # 过滤实例类型
    if type:
        filter_dict["type"] = type
    # 过滤数据库类型
    if db_type:
        filter_dict["db_type"] = db_type

    instances = Instance.objects.filter(**filter_dict)
    # 过滤标签，返回同时包含全部标签的实例，TODO 循环会生成多表JOIN，如果数据量大会存在效率问题
    if tags:
        for tag in tags:
            instances = instances.filter(instance_tag=tag, instance_tag__active=True)

    count = instances.count()
    if sortName == "instance_name":
        instances = instances.order_by(getattr(Convert(sortName, "gbk"), sortOrder)())[
            offset:limit
        ]
    else:
        instances = instances.order_by(
            "-" + sortName if sortOrder == "desc" else sortName
        )[offset:limit]
    instances = instances.values(
        "id", "instance_name", "db_type", "type", "host", "port", "user"
    )

    # QuerySet 序列化
    rows = [row for row in instances]

    result = {"total": count, "rows": rows}
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


@permission_required("sql.param_view", raise_exception=True)
def param_list(request):
    """
    获取实例参数列表
    :param request:
    :return:
    """
    instance_id = request.POST.get("instance_id")
    editable = True if request.POST.get("editable") else False
    search = request.POST.get("search", "")
    # 校验实例ID格式
    try:
        int(instance_id)
    except (TypeError, ValueError) as e:
        logger.error(f"实例ID不合法：{instance_id}，异常详情：{e}")
        result = {"status": 1, "msg": "实例ID不合法", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    try:
        ins = Instance.objects.get(id=instance_id)
    except Instance.DoesNotExist as e:
        logger.error(f"实例不存在：{instance_id}，异常详情：{e}")
        result = {"status": 1, "msg": "实例不存在", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    ensure_builtin_param_templates(ins.db_type)
    # 获取已配置参数列表
    cnf_params = dict()
    for param in ParamTemplate.objects.filter(
        db_type=ins.db_type, variable_name__contains=search
    ).values(
        "id",
        "variable_name",
        "default_value",
        "valid_values",
        "description",
        "editable",
    ):
        param["variable_name"] = param["variable_name"].lower()
        cnf_params[param["variable_name"]] = param
    # 获取实例参数列表
    engine = get_engine(instance=ins)
    ins_variables = engine.get_variables()
    # 处理结果
    rows = list()
    for variable in ins_variables.rows:
        variable_name = variable[0].lower()
        row = {
            "variable_name": variable_name,
            "runtime_value": variable[1],
            "editable": False,
        }
        if variable_name in cnf_params.keys():
            row = dict(row, **cnf_params[variable_name])
        rows.append(row)
    # 过滤参数
    if editable:
        rows = [row for row in rows if row["editable"]]
    else:
        rows = [row for row in rows if not row["editable"]]
    return HttpResponse(
        json.dumps(rows, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


@permission_required("sql.param_view", raise_exception=True)
def param_history(request):
    """实例参数修改历史"""
    limit = int(request.POST.get("limit"))
    offset = int(request.POST.get("offset"))
    limit = offset + limit
    instance_id = request.POST.get("instance_id")
    search = request.POST.get("search", "")
    phs = ParamHistory.objects.filter(instance__id=instance_id)
    # 过滤搜索条件
    if search:
        phs = ParamHistory.objects.filter(variable_name__contains=search)
    count = phs.count()
    phs = phs[offset:limit].values(
        "instance__instance_name",
        "variable_name",
        "old_var",
        "new_var",
        "user_display",
        "create_time",
    )
    # QuerySet 序列化
    rows = [row for row in phs]

    result = {"total": count, "rows": rows}
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


@permission_required("sql.param_edit", raise_exception=True)
def param_edit(request):
    user = request.user
    instance_id = request.POST.get("instance_id")
    variable_name = request.POST.get("variable_name")
    variable_value = request.POST.get("runtime_value")
    # 校验实例ID格式
    try:
        int(instance_id)
    except (TypeError, ValueError) as e:
        logger.error(f"实例ID不合法：{instance_id}，异常详情：{e}")
        result = {"status": 1, "msg": "实例ID不合法", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    try:
        ins = Instance.objects.get(id=instance_id)
    except Instance.DoesNotExist as e:
        logger.error(f"实例不存在：{instance_id}，异常详情：{e}")
        result = {"status": 1, "msg": "实例不存在", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 修改参数
    engine = get_engine(instance=ins)
    variable_name = engine.escape_string(variable_name)
    variable_value = engine.escape_string(variable_value)
    ensure_builtin_param_templates(ins.db_type)
    # 校验是否配置模板（需匹配 db_type 且 editable=True）
    param_template = ParamTemplate.objects.filter(
        db_type=ins.db_type, variable_name=variable_name, editable=True
    ).first()
    if not param_template:
        result = {"status": 1, "msg": "请先在参数模板中配置该参数！", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    # 获取当前运行参数值
    runtime_value = engine.get_variables(variables=[variable_name]).rows[0][1]
    if variable_value == runtime_value:
        result = {"status": 1, "msg": "参数值与实际运行值一致，未调整！", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    set_result = engine.set_variable(
        variable_name=variable_name, variable_value=variable_value
    )
    if set_result.error:
        result = {
            "status": 1,
            "msg": f"设置错误，错误信息：{set_result.error}",
            "data": [],
        }
        return HttpResponse(json.dumps(result), content_type="application/json")
    # 修改成功的保存修改记录
    else:
        ParamHistory.objects.create(
            instance=ins,
            variable_name=variable_name,
            old_var=runtime_value,
            new_var=variable_value,
            set_sql=set_result.full_sql,
            user_name=user.username,
            user_display=user.display,
        )
        result = {"status": 0, "msg": "修改成功，请手动持久化到配置文件！", "data": []}
    return HttpResponse(json.dumps(result), content_type="application/json")


@permission_required("sql.param_view", raise_exception=True)
def param_compare(request):
    """对比两个实例的参数差异"""
    instance_id1 = request.POST.get("instance_id1")
    instance_id2 = request.POST.get("instance_id2")
    diff_only = request.POST.get("diff_only", "true") == "true"

    # 校验实例ID格式
    for iid, label in [(instance_id1, "源实例ID"), (instance_id2, "目标实例ID")]:
        try:
            int(iid)
        except (TypeError, ValueError) as e:
            logger.error(f"{label}不合法：{iid}，异常详情：{e}")
            result = {"status": 1, "msg": f"{label}不合法", "data": []}
            return HttpResponse(json.dumps(result), content_type="application/json")

    # 校验实例存在
    try:
        ins1 = Instance.objects.get(id=instance_id1)
    except Instance.DoesNotExist as e:
        logger.error(f"源实例不存在：{instance_id1}，异常详情：{e}")
        result = {"status": 1, "msg": "源实例不存在", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    try:
        ins2 = Instance.objects.get(id=instance_id2)
    except Instance.DoesNotExist as e:
        logger.error(f"目标实例不存在：{instance_id2}，异常详情：{e}")
        result = {"status": 1, "msg": "目标实例不存在", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 校验同类型
    if ins1.db_type != ins2.db_type:
        result = {
            "status": 1,
            "msg": "两个实例的数据库类型不一致，无法对比",
            "data": [],
        }
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 校验引擎支持参数对比（mysql / goinception / gaussdb / kingbase 实现了 get_variables）
    _variable_supported_db_types = {"mysql", "goinception", "gaussdb", "kingbase"}
    if ins1.db_type not in _variable_supported_db_types:
        result = {
            "status": 1,
            "msg": f"{ins1.db_type} 引擎不支持参数对比功能",
            "data": [],
        }
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 获取参数
    try:
        engine1 = get_engine(instance=ins1)
        variables1 = engine1.get_variables()
    except Exception as e:
        logger.error(f"获取源实例参数失败，异常详情：{e}")
        result = {"status": 1, "msg": "获取源实例参数失败，请联系管理员", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    if variables1.error:
        logger.error(f"获取源实例参数失败，异常详情：{variables1.error}")
        result = {"status": 1, "msg": "获取源实例参数失败，请联系管理员", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    try:
        engine2 = get_engine(instance=ins2)
        variables2 = engine2.get_variables()
    except Exception as e:
        logger.error(f"获取目标实例参数失败，异常详情：{e}")
        result = {"status": 1, "msg": "获取目标实例参数失败，请联系管理员", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    if variables2.error:
        logger.error(f"获取目标实例参数失败，异常详情：{variables2.error}")
        result = {"status": 1, "msg": "获取目标实例参数失败，请联系管理员", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 构建 dict {variable_name_lower: value}（保留原始值，不 strip，以便检测空白差异）
    vars1 = {}
    for variable in variables1.rows:
        var_name = str(variable[0]).lower()
        vars1[var_name] = str(variable[1])

    vars2 = {}
    for variable in variables2.rows:
        var_name = str(variable[0]).lower()
        vars2[var_name] = str(variable[1])

    # 获取参数模板补充描述
    cnf_params = dict()
    for param in ParamTemplate.objects.filter(db_type=ins1.db_type).values(
        "variable_name", "default_value", "description"
    ):
        cnf_params[param["variable_name"].lower()] = param

    # 遍历并集，逐项对比
    all_keys = set(vars1.keys()) | set(vars2.keys())
    rows = []
    same_count = 0
    diff_count = 0
    for key in sorted(all_keys):
        val1 = vars1.get(key)
        val2 = vars2.get(key)

        if val1 is not None and val2 is not None:
            # 双方都有
            if val1 == val2:
                diff_type = "一致"
                same_count += 1
            else:
                diff_type = "值不同"
                diff_count += 1
        elif val1 is not None:
            diff_type = "仅源实例存在"
            diff_count += 1
        else:
            diff_type = "仅目标实例存在"
            diff_count += 1

        # diff_only 过滤
        if diff_only and diff_type == "一致":
            continue

        row = {
            "variable_name": key,
            "instance1_value": val1 if val1 is not None else "-",
            "instance2_value": val2 if val2 is not None else "-",
            "diff_type": diff_type,
            "description": "",
            "default_value": "",
        }
        # 补充参数模板信息
        if key in cnf_params:
            row["description"] = cnf_params[key].get("description", "")
            row["default_value"] = cnf_params[key].get("default_value", "")
        rows.append(row)

    result = {
        "status": 0,
        "msg": "ok",
        "data": {
            "rows": rows,
            "total": len(all_keys),
            "same_count": same_count,
            "diff_count": diff_count,
            "instance1_name": ins1.instance_name,
            "instance2_name": ins2.instance_name,
        },
    }
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


@permission_required("sql.menu_schemasync", raise_exception=True)
def schemasync(request):
    """对比实例schema信息"""
    instance_name = request.POST.get("instance_name")
    db_name = request.POST.get("db_name")
    target_instance_name = request.POST.get("target_instance_name")
    target_db_name = request.POST.get("target_db_name")
    sync_auto_inc = True if request.POST.get("sync_auto_inc") == "true" else False
    sync_comments = True if request.POST.get("sync_comments") == "true" else False
    result = {
        "status": 0,
        "msg": "ok",
        "data": {"diff_stdout": "", "patch_stdout": "", "revert_stdout": ""},
    }

    # 循环对比全部数据库
    if db_name == "all" or target_db_name == "all":
        db_name = "*"
        target_db_name = "*"

    # 取出该实例的连接方式
    instance = Instance.objects.get(instance_name=instance_name)
    target_instance = Instance.objects.get(instance_name=target_instance_name)

    # 提交给SchemaSync获取对比结果
    schema_sync = SchemaSync()
    # 准备参数
    tag = int(time.time())
    output_directory = os.path.join(settings.BASE_DIR, "downloads/schemasync/")
    os.makedirs(output_directory, exist_ok=True)

    username, password = instance.get_username_password()
    target_username, target_password = target_instance.get_username_password()

    args = {
        "sync-auto-inc": sync_auto_inc,
        "sync-comments": sync_comments,
        "charset": "utf8mb4",
        "tag": tag,
        "output-directory": output_directory,
        "source": f"mysql://{username}:{password}@{instance.host}:{instance.port}/{db_name}",
        "target": f"mysql://{target_username}:{target_password}@{target_instance.host}:{target_instance.port}/{target_db_name}",
    }
    # 参数检查
    args_check_result = schema_sync.check_args(args)
    if args_check_result["status"] == 1:
        return HttpResponse(
            json.dumps(args_check_result), content_type="application/json"
        )
    # 参数转换
    cmd_args = schema_sync.generate_args2cmd(args)
    # 执行命令
    try:
        stdout, stderr = schema_sync.execute_cmd(cmd_args).communicate()
        diff_stdout = f"{stdout}{stderr}"
    except RuntimeError as e:
        logger.error(f"schemasync执行命令失败，异常详情：{e}")
        diff_stdout = "执行对比命令失败，请联系管理员"

    # 非全部数据库对比可以读取对比结果并在前端展示
    if db_name != "*":
        date = time.strftime("%Y%m%d", time.localtime())
        patch_sql_file = "%s%s_%s.%s.patch.sql" % (
            output_directory,
            target_db_name,
            tag,
            date,
        )
        revert_sql_file = "%s%s_%s.%s.revert.sql" % (
            output_directory,
            target_db_name,
            tag,
            date,
        )
        try:
            with open(patch_sql_file, "r") as f:
                patch_sql = f.read()
        except FileNotFoundError as e:
            logger.error(f"schemasync读取patch文件失败，异常详情：{e}")
            patch_sql = "读取对比结果文件失败，请联系管理员"
        try:
            with open(revert_sql_file, "r") as f:
                revert_sql = f.read()
        except FileNotFoundError as e:
            logger.error(f"schemasync读取revert文件失败，异常详情：{e}")
            revert_sql = "读取对比结果文件失败，请联系管理员"
        result["data"] = {
            "diff_stdout": diff_stdout,
            "patch_stdout": patch_sql,
            "revert_stdout": revert_sql,
        }
    else:
        result["data"] = {
            "diff_stdout": diff_stdout,
            "patch_stdout": "",
            "revert_stdout": "",
        }

    return HttpResponse(json.dumps(result), content_type="application/json")


@cache_page(60 * 5, key_prefix="insRes")
def instance_resource(request):
    """
    获取实例内的资源信息，database、schema、table、column
    :param request:
    :return:
    """
    result = list_instance_resources(
        user=request.user,
        resource_type=request.GET.get("resource_type"),
        instance_id=request.GET.get("instance_id"),
        instance_name=request.GET.get("instance_name"),
        db_name=request.GET.get("db_name", ""),
        schema_name=request.GET.get("schema_name", ""),
        tb_name=request.GET.get("tb_name", ""),
    )
    return HttpResponse(json.dumps(result), content_type="application/json")
