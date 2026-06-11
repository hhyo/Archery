# -*- coding: UTF-8 -*-

import datetime
import logging
import re
import time
import traceback

from django.db import close_old_connections, connection

from common.config import SysConfig
from common.utils.timer import FuncTimer
from sql.engines import get_engine
from sql.models import Instance, QueryLog
from sql.query_privileges import query_priv_check
from sql.utils.resource_group import user_instances
from sql.utils.tasks import add_kill_conn_schedule, del_schedule

logger = logging.getLogger("default")


def execute_sql_query(
    user,
    instance_name,
    db_name,
    sql_content,
    limit_num,
    schema_name=None,
    tb_name=None,
):
    """执行 SQL 查询并返回与旧接口一致的响应结构。"""
    result = {"status": 0, "msg": "ok", "data": {}}

    try:
        limit_num = int(limit_num)
    except (TypeError, ValueError):
        result["status"] = 1
        result["msg"] = "limit_num 非法"
        return result

    try:
        instance = user_instances(user).get(instance_name=instance_name)
    except Instance.DoesNotExist:
        result["status"] = 1
        result["msg"] = "你所在组未关联该实例"
        return result

    if None in [sql_content, db_name, instance_name, limit_num]:
        result["status"] = 1
        result["msg"] = "页面提交参数可能为空"
        return result

    priv_check = False
    try:
        config = SysConfig()
        query_engine = get_engine(instance=instance)
        query_check_info = query_engine.query_check(db_name=db_name, sql=sql_content)
        if query_check_info.get("bad_query"):
            result["status"] = 1
            result["msg"] = query_check_info.get("msg")
            return result
        if query_check_info.get("has_star") and config.get("disable_star") is True:
            result["status"] = 1
            result["msg"] = query_check_info.get("msg")
            return result
        sql_content = query_check_info["filtered_sql"]

        priv_check_info = query_priv_check(
            user, instance, db_name, sql_content, limit_num
        )
        if priv_check_info["status"] != 0:
            result["status"] = priv_check_info["status"]
            result["msg"] = priv_check_info["msg"]
            return result
        limit_num = priv_check_info["data"]["limit_num"]
        priv_check = priv_check_info["data"]["priv_check"]

        limit_num = 0 if re.match(r"^explain", sql_content.lower()) else limit_num
        sql_content = query_engine.filter_sql(sql=sql_content, limit_num=limit_num)

        query_engine.get_connection(db_name=db_name)
        thread_id = query_engine.thread_id
        max_execution_time = int(config.get("max_execution_time", 60))
        if thread_id:
            schedule_name = f"query-{time.time()}"
            run_date = datetime.datetime.now() + datetime.timedelta(
                seconds=max_execution_time
            )
            add_kill_conn_schedule(schedule_name, run_date, instance.id, thread_id)
        with FuncTimer() as timer:
            seconds_behind_master = query_engine.seconds_behind_master
            query_result = query_engine.query(
                db_name,
                sql_content,
                limit_num,
                schema_name=schema_name,
                tb_name=tb_name,
                max_execution_time=max_execution_time * 1000,
            )
        query_result.query_time = timer.cost
        if thread_id:
            del_schedule(schedule_name)

        if query_result.error:
            result["status"] = 1
            result["msg"] = query_result.error
        elif config.get("data_masking"):
            try:
                with FuncTimer() as timer:
                    masking_result = query_engine.query_masking(
                        db_name, sql_content, query_result
                    )
                masking_result.mask_time = timer.cost
                if masking_result.error:
                    if config.get("query_check"):
                        result["status"] = 1
                        result["msg"] = f"数据脱敏异常：{masking_result.error}"
                    else:
                        logger.warning(
                            "数据脱敏异常，按照配置放行，查询语句：%s，错误信息：%s",
                            sql_content,
                            masking_result.error,
                        )
                        query_result.error = None
                        result["data"] = query_result.__dict__
                else:
                    result["data"] = masking_result.__dict__
            except Exception as msg:
                logger.error(traceback.format_exc())
                if config.get("query_check"):
                    result["status"] = 1
                    result["msg"] = f"数据脱敏异常，请联系管理员，错误信息：{msg}"
                else:
                    logger.warning(
                        "数据脱敏异常，按照配置放行，查询语句：%s，错误信息：%s",
                        sql_content,
                        msg,
                    )
                    query_result.error = None
                    result["data"] = query_result.__dict__
        else:
            result["data"] = query_result.__dict__

        if not query_result.error:
            result["data"]["seconds_behind_master"] = seconds_behind_master
            if int(limit_num) == 0:
                effect_row = int(query_result.affected_rows)
            else:
                effect_row = min(int(limit_num), int(query_result.affected_rows))
            if connection.connection and not connection.is_usable():
                close_old_connections()
        else:
            effect_row = 0

        QueryLog.objects.create(
            username=user.username,
            user_display=user.display,
            db_name=db_name,
            instance_name=instance.instance_name,
            sqllog=sql_content,
            effect_row=effect_row,
            cost_time=query_result.query_time,
            priv_check=priv_check,
            hit_rule=query_result.mask_rule_hit,
            masking=query_result.is_masked,
        )
    except Exception as e:
        logger.error(
            "查询异常报错，查询语句：%s，错误信息：%s",
            sql_content,
            traceback.format_exc(),
        )
        result["status"] = 1
        result["msg"] = f"查询异常报错，错误信息：{e}"
    return result
