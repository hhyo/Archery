# -*- coding: UTF-8 -*-

import MySQLdb
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
from sql.plugins.schemasync import SchemaSync
from sql.utils.sql_utils import filter_db_list
from .models import Instance, ParamTemplate, ParamHistory


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
    try:
        ins = Instance.objects.get(id=instance_id)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "实例不存在", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
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
    try:
        ins = Instance.objects.get(id=instance_id)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "实例不存在", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 修改参数
    engine = get_engine(instance=ins)
    variable_name = engine.escape_string(variable_name)
    variable_value = engine.escape_string(variable_value)
    # 校验是否配置模板
    if not ParamTemplate.objects.filter(variable_name=variable_name).exists():
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

    # 校验实例存在
    try:
        ins1 = Instance.objects.get(id=instance_id1)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "源实例不存在", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    try:
        ins2 = Instance.objects.get(id=instance_id2)
    except Instance.DoesNotExist:
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

    # 获取参数
    try:
        engine1 = get_engine(instance=ins1)
        variables1 = engine1.get_variables()
    except Exception as e:
        result = {"status": 1, "msg": f"获取源实例参数失败：{e}", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    try:
        engine2 = get_engine(instance=ins2)
        variables2 = engine2.get_variables()
    except Exception as e:
        result = {"status": 1, "msg": f"获取目标实例参数失败：{e}", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")

    # 构建 dict {variable_name_lower: value}
    vars1 = {}
    for variable in variables1.rows:
        var_name = str(variable[0]).lower()
        vars1[var_name] = str(variable[1]).strip()

    vars2 = {}
    for variable in variables2.rows:
        var_name = str(variable[0]).lower()
        vars2[var_name] = str(variable[1]).strip()

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
        diff_stdout = str(e)

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
            patch_sql = str(e)
        try:
            with open(revert_sql_file, "r") as f:
                revert_sql = f.read()
        except FileNotFoundError as e:
            revert_sql = str(e)
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
    instance_id = request.GET.get("instance_id")
    instance_name = request.GET.get("instance_name")
    db_name = request.GET.get("db_name", "")
    schema_name = request.GET.get("schema_name", "")
    tb_name = request.GET.get("tb_name", "")

    resource_type = request.GET.get("resource_type")
    if instance_id:
        instance = Instance.objects.get(id=instance_id)
    else:
        try:
            instance = Instance.objects.get(instance_name=instance_name)
        except Instance.DoesNotExist:
            result = {"status": 1, "msg": "实例不存在", "data": []}
            return HttpResponse(json.dumps(result), content_type="application/json")
    result = {"status": 0, "msg": "ok", "data": []}

    try:
        query_engine = get_engine(instance=instance)
        db_name = query_engine.escape_string(db_name)
        schema_name = query_engine.escape_string(schema_name)
        tb_name = query_engine.escape_string(tb_name)
        if resource_type == "database":
            resource = query_engine.get_all_databases()
            resource.rows = filter_db_list(
                db_list=resource.rows,
                db_name_regex=query_engine.instance.show_db_name_regex,
                is_match_regex=True,
            )
            resource.rows = filter_db_list(
                db_list=resource.rows,
                db_name_regex=query_engine.instance.denied_db_name_regex,
                is_match_regex=False,
            )
        elif resource_type == "schema" and db_name:
            resource = query_engine.get_all_schemas(db_name=db_name)
        elif resource_type == "table" and db_name:
            resource = query_engine.get_all_tables(
                db_name=db_name, schema_name=schema_name
            )
        elif resource_type == "column" and db_name and tb_name:
            resource = query_engine.get_all_columns_by_tb(
                db_name=db_name, tb_name=tb_name, schema_name=schema_name
            )
        else:
            raise TypeError("不支持的资源类型或者参数不完整！")
    except Exception as msg:
        result["status"] = 1
        result["msg"] = str(msg)
    else:
        if resource.error:
            result["status"] = 1
            result["msg"] = resource.error
        else:
            result["data"] = resource.rows
    return HttpResponse(json.dumps(result), content_type="application/json")


def describe(request):
    """获取表结构"""
    instance_name = request.POST.get("instance_name")
    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result = {"status": 1, "msg": "实例不存在", "data": []}
        return HttpResponse(json.dumps(result), content_type="application/json")
    db_name = request.POST.get("db_name")
    schema_name = request.POST.get("schema_name")
    tb_name = request.POST.get("tb_name")

    result = {"status": 0, "msg": "ok", "data": []}

    try:
        query_engine = get_engine(instance=instance)
        db_name = query_engine.escape_string(db_name)
        schema_name = query_engine.escape_string(schema_name)
        tb_name = query_engine.escape_string(tb_name)
        query_result = query_engine.describe_table(
            db_name, tb_name, schema_name=schema_name
        )
        result["data"] = query_result.__dict__
    except Exception as msg:
        result["status"] = 1
        result["msg"] = str(msg)
    if result["data"].get("error"):
        result["status"] = 1
        result["msg"] = result["data"]["error"]
    return HttpResponse(json.dumps(result), content_type="application/json")
