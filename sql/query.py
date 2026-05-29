# -*- coding: UTF-8 -*-
import datetime
import logging
import re
import time
import traceback

import simplejson as json
from django.contrib.auth.decorators import permission_required
from django.db import connection, close_old_connections
from django.db.models import Q
from django.http import HttpResponse
from common.config import SysConfig
from common.utils.extend_json_encoder import ExtendJSONEncoder, ExtendJSONEncoderFTime
from common.utils.openai import OpenaiClient, check_openai_config
from common.utils.timer import FuncTimer
from sql.query_privileges import query_priv_check
from sql.utils.resource_group import user_instances
from sql.utils.tasks import add_kill_conn_schedule, del_schedule
from .models import QueryLog, Instance
from sql.engines import get_engine
from sql.services.querylog_service import list_query_logs, update_favorite
from sql.services.sqlquery_service import execute_sql_query

logger = logging.getLogger("default")


@permission_required("sql.query_submit", raise_exception=True)
def query(request):
    """
    获取SQL查询结果
    :param request:
    :return:
    """
    result = execute_sql_query(
        user=request.user,
        instance_name=request.POST.get("instance_name"),
        db_name=request.POST.get("db_name"),
        sql_content=request.POST.get("sql_content"),
        limit_num=request.POST.get("limit_num", 0),
        schema_name=request.POST.get("schema_name", None),
        tb_name=request.POST.get("tb_name"),
    )
    # 返回查询结果
    try:
        return HttpResponse(
            json.dumps(
                result,
                use_decimal=False,
                cls=ExtendJSONEncoderFTime,
                bigint_as_string=True,
            ),
            content_type="application/json",
        )
    # 虽然能正常返回，但是依然会乱码
    except UnicodeDecodeError:
        return HttpResponse(
            json.dumps(result, default=str, bigint_as_string=True, encoding="latin1"),
            content_type="application/json",
        )


@permission_required("sql.menu_sqlquery", raise_exception=True)
def querylog(request):
    return _querylog(request)


@permission_required("sql.audit_user", raise_exception=True)
def querylog_audit(request):
    return _querylog(request)


def _querylog(request):
    """
    获取sql查询记录
    :param request:
    :return:
    """
    result = list_query_logs(
        user=request.user,
        limit=int(request.GET.get("limit", 0)),
        offset=int(request.GET.get("offset", 0)),
        star=request.GET.get("star") == "true",
        query_log_id=request.GET.get("query_log_id"),
        search=request.GET.get("search", ""),
        start_date=request.GET.get("start_date", ""),
        end_date=request.GET.get("end_date", ""),
    )
    # 返回查询结果
    return HttpResponse(
        json.dumps(result, cls=ExtendJSONEncoder, bigint_as_string=True),
        content_type="application/json",
    )


@permission_required("sql.menu_sqlquery", raise_exception=True)
def favorite(request):
    """
    收藏查询记录，并且设置别名
    :param request:
    :return:
    """
    result = update_favorite(
        user=request.user,
        query_log_id=request.POST.get("query_log_id"),
        star=request.POST.get("star") == "true",
        alias=request.POST.get("alias"),
    )
    # 返回查询结果
    return HttpResponse(json.dumps(result), content_type="application/json")


def kill_query_conn(instance_id, thread_id):
    """终止查询会话，用于schedule调用"""
    instance = Instance.objects.get(pk=instance_id)
    query_engine = get_engine(instance)
    query_engine.kill_connection(thread_id)


@permission_required("sql.menu_sqlquery", raise_exception=True)
def generate_sql(request):
    """
    利用AI生成查询SQL, 传入数据基本结构和查询描述
    :param request:
    :return:
    """
    query_desc = request.POST.get("query_desc")
    db_type = request.POST.get("db_type")
    if not query_desc or not db_type:
        return HttpResponse(
            json.dumps({"status": 1, "msg": "query_desc or db_type不存在", "data": []}),
            content_type="application/json",
        )

    instance_name = request.POST.get("instance_name")
    try:
        instance = Instance.objects.get(instance_name=instance_name)
    except Instance.DoesNotExist:
        return HttpResponse(
            json.dumps({"status": 1, "msg": "实例不存在", "data": []}),
            content_type="application/json",
        )
    db_name = request.POST.get("db_name")
    schema_name = request.POST.get("schema_name")
    tb_name = request.POST.get("tb_name")

    result = {"status": 0, "msg": "ok", "data": ""}
    try:
        query_engine = get_engine(instance=instance)
        query_result = query_engine.describe_table(
            db_name, tb_name, schema_name=schema_name
        )
        openai_client = OpenaiClient()
        # 有些不存在表结构, 例如 redis
        if len(query_result.rows) != 0:
            result["data"] = openai_client.generate_sql_by_openai(
                db_type, query_result.rows[0][-1], query_desc
            )
        else:
            result["data"] = openai_client.generate_sql_by_openai(
                db_type, "", query_desc
            )
    except Exception as msg:
        result["status"] = 1
        result["msg"] = str(msg)
    return HttpResponse(json.dumps(result), content_type="application/json")


def check_openai(request):
    """
    校验openai配置是否存在
    :param request:
    :return:
    """
    config_validate = check_openai_config()
    if not config_validate:
        return HttpResponse(
            json.dumps(
                {
                    "status": 1,
                    "msg": "openai 缺少配置, 必需配置[openai_base_url, openai_api_key, default_chat_model]",
                    "data": False,
                }
            ),
            content_type="application/json",
        )

    return HttpResponse(
        json.dumps({"status": 0, "msg": "ok", "data": True}),
        content_type="application/json",
    )
