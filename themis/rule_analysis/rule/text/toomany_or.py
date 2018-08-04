# -*- coding: utf-8 -*-


def execute_rule(**kwargs):
    sql = kwargs.get("sql")
    bind_num = kwargs.get("or_num")
    if sql.count(" or ") > bind_num:
        return True
    return False
