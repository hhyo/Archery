# -*- coding: utf-8 -*-


def execute_rule(**kwargs):
    sql = kwargs.get("sql")
    parm = kwargs.get("num_of_bound_var")
    if sql.count(":") > parm:
        return True
    return False
