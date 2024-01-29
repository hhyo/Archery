# -*- coding: UTF-8 -*-
""" 
@author: hhyo
@license: Apache Licence
@file: instance_database.py
@time: 2019/09/19
"""
import MySQLdb

import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse, HttpResponse
from django_redis import get_redis_connection

from common.utils.extend_json_encoder import ExtendJSONEncoder
from sql.engines import get_engine, ResultSet
from sql.models import Instance, InstanceDatabase, Users
from sql.utils.resource_group import user_instances

__author__ = "hhyo"


@permission_required("sql.menu_database", raise_exception=True)
def databases(request):
    """获取实例数据库列表"""
    instance_id = request.POST.get("instance_id")
    saved = True if request.POST.get("saved") == "true" else False  # 平台是否保存

    if not instance_id:
        return JsonResponse({"status": 0, "msg": "", "data": []})

    try:
        instance = user_instances(request.user, db_type=["mysql", "mongo"]).get(
            id=instance_id
        )
    except Instance.DoesNotExist:
        return JsonResponse({"status": 1, "msg": "你所在组未关联该实例", "data": []})

    # 获取已录入数据库
    cnf_dbs = dict()
    for db in InstanceDatabase.objects.filter(instance=instance).values(
        "id", "db_name", "owner", "owner_display", "remark"
    ):
        db["saved"] = True
        cnf_dbs[f"{db['db_name']}"] = db

    query_engine = get_engine(instance=instance)
    query_result = query_engine.get_all_databases_summary()
    if not query_result.error:
        # 获取数据库关联用户信息
        rows = []
        for row in query_result.rows:
            if row["db_name"] in cnf_dbs.keys():
                row = dict(row, **cnf_dbs[row["db_name"]])
            rows.append(row)
        if saved:
            rows = [row for row in rows if row["saved"]]
        result = {"status": 0, "msg": "ok", "rows": rows}
    else:
        result = {"status": 1, "msg": query_result.error}

    # 关闭连接
    query_engine.close()
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


@permission_required("sql.menu_database", raise_exception=True)
def create(request):
    """创建数据库"""
    instance_id = request.POST.get("instance_id", 0)
    db_name = request.POST.get("db_name")
    owner = request.POST.get("owner", "")
    remark = request.POST.get("remark", "")

    if not all([db_name]):
        return JsonResponse(
            {"status": 1, "msg": "参数不完整，请确认后提交", "data": []}
        )

    try:
        instance = user_instances(request.user, db_type=["mysql", "mongo"]).get(
            id=instance_id
        )
    except Instance.DoesNotExist:
        return JsonResponse({"status": 1, "msg": "你所在组未关联该实例", "data": []})

    try:
        owner_display = Users.objects.get(username=owner).display
    except Users.DoesNotExist:
        return JsonResponse({"status": 1, "msg": "负责人不存在", "data": []})

    engine = get_engine(instance=instance)
    if instance.db_type == "mysql":
        # escape
        db_name = engine.escape_string(db_name)
        exec_result = engine.execute(
            db_name="information_schema", sql=f"create database {db_name};"
        )
    elif instance.db_type == "mongo":
        exec_result = ResultSet()
        try:
            conn = engine.get_connection()
            db = conn[db_name]
            db.create_collection(
                name=f"archery-{db_name}"
            )  # mongo创建数据库，需要数据库存在数据才会显示数据库名称，这里创建一个archery-{db_name}的集合
        except Exception as e:
            exec_result.error = f"创建数据库失败, 错误信息：{str(e)}"

    # 关闭连接
    engine.close()
    if exec_result.error:
        return JsonResponse({"status": 1, "msg": exec_result.error})
    # 保存到数据库
    else:
        InstanceDatabase.objects.create(
            instance=instance,
            db_name=db_name,
            owner=owner,
            owner_display=owner_display,
            remark=remark,
        )
        # 清空实例资源缓存
        r = get_redis_connection("default")
        for key in r.scan_iter(match="*insRes*", count=2000):
            r.delete(key)

    return JsonResponse({"status": 0, "msg": "", "data": []})


@permission_required("sql.menu_database", raise_exception=True)
def edit(request):
    """编辑/录入数据库"""
    instance_id = request.POST.get("instance_id", 0)
    db_name = request.POST.get("db_name")
    owner = request.POST.get("owner", "")
    remark = request.POST.get("remark", "")

    if not all([db_name]):
        return JsonResponse(
            {"status": 1, "msg": "参数不完整，请确认后提交", "data": []}
        )

    try:
        instance = user_instances(request.user, db_type=["mysql", "mongo"]).get(
            id=instance_id
        )
    except Instance.DoesNotExist:
        return JsonResponse({"status": 1, "msg": "你所在组未关联该实例", "data": []})

    try:
        owner_display = Users.objects.get(username=owner).display
    except Users.DoesNotExist:
        return JsonResponse({"status": 1, "msg": "负责人不存在", "data": []})

    # 更新或者录入信息
    InstanceDatabase.objects.update_or_create(
        instance=instance,
        db_name=db_name,
        defaults={"owner": owner, "owner_display": owner_display, "remark": remark},
    )
    return JsonResponse({"status": 0, "msg": "", "data": []})
