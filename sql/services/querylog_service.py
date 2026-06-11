# -*- coding: UTF-8 -*-

import datetime

from django.db.models import Q

from sql.models import QueryLog


def list_query_logs(
    user,
    limit=0,
    offset=0,
    star=False,
    query_log_id=None,
    search="",
    start_date="",
    end_date="",
):
    """返回历史查询数据，结构兼容 bootstrap-table。"""
    limit = offset + limit
    limit = limit if limit else None

    filter_dict = {}
    if star:
        filter_dict["favorite"] = True
    if query_log_id:
        filter_dict["id"] = query_log_id

    if not (user.is_superuser or user.has_perm("sql.audit_user")):
        filter_dict["username"] = user.username

    if start_date and end_date:
        end_date = datetime.datetime.strptime(
            end_date, "%Y-%m-%d"
        ) + datetime.timedelta(days=1)
        filter_dict["create_time__range"] = (start_date, end_date)

    sql_log = QueryLog.objects.filter(**filter_dict)
    sql_log = sql_log.filter(
        Q(sqllog__icontains=search)
        | Q(user_display__icontains=search)
        | Q(alias__icontains=search)
    )
    rows = [
        row
        for row in sql_log.order_by("-id")[offset:limit].values(
            "id",
            "instance_name",
            "db_name",
            "sqllog",
            "effect_row",
            "cost_time",
            "user_display",
            "favorite",
            "alias",
            "create_time",
        )
    ]
    return {"total": sql_log.count(), "rows": rows}


def update_favorite(user, query_log_id, star, alias):
    """更新收藏状态，普通用户只能修改自己的记录。"""
    query_set = QueryLog.objects.filter(id=query_log_id)
    if not (user.is_superuser or user.has_perm("sql.audit_user")):
        query_set = query_set.filter(username=user.username)

    if not query_set.exists():
        return {"status": 1, "msg": "查询记录不存在或无权限"}

    query_set.update(favorite=star, alias=alias)
    return {"status": 0, "msg": "ok"}
