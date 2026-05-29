# -*- coding: UTF-8 -*-

import logging

from common.utils.convert import Convert
from sql.engines import get_engine
from sql.models import Instance
from sql.utils.resource_group import user_instances
from sql.utils.sql_utils import filter_db_list

logger = logging.getLogger("default")


def list_user_accessible_instances(user, type=None, db_type=None, tag_codes=None):
    """返回用户可访问实例列表，结构兼容旧接口。"""
    instances = (
        user_instances(user, type, db_type, tag_codes)
        .order_by(Convert("instance_name", "gbk").asc())
        .values("id", "type", "db_type", "instance_name")
    )
    return {"status": 0, "msg": "ok", "data": [row for row in instances]}


def _resolve_instance_for_user(user, instance_id=None, instance_name=None):
    if instance_id:
        return user_instances(user).get(id=instance_id)
    if instance_name:
        return user_instances(user).get(instance_name=instance_name)
    raise Instance.DoesNotExist


def list_instance_resources(
    user,
    resource_type,
    instance_id=None,
    instance_name=None,
    db_name="",
    schema_name="",
    tb_name="",
):
    """返回实例下资源，结构兼容旧接口。"""
    result = {"status": 0, "msg": "ok", "data": []}
    try:
        instance = _resolve_instance_for_user(
            user=user, instance_id=instance_id, instance_name=instance_name
        )
    except Instance.DoesNotExist:
        result["status"] = 1
        result["msg"] = "实例不存在或无权限"
        return result

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
        return result

    if resource.error:
        result["status"] = 1
        result["msg"] = resource.error
    else:
        result["data"] = resource.rows
    return result


def describe_table_structure(
    user,
    instance_name,
    db_name,
    tb_name,
    schema_name="",
):
    """返回表结构，结构兼容旧 /instance/describetable/ 接口。"""
    result = {"status": 0, "msg": "ok", "data": {}}
    try:
        instance = _resolve_instance_for_user(user=user, instance_name=instance_name)
    except Instance.DoesNotExist:
        result["status"] = 1
        result["msg"] = "实例不存在或无权限"
        return result

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
    return result
