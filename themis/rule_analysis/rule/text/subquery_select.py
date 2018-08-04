# -*- coding: utf-8 -*-


def execute_rule(**kwargs):
    sql = kwargs.get("sql")
    m = 0
    n = 0
    sql_content = []
    sqlbegin = 0
    sqlend = 0
    str_len = len(sql)
    for k in range(str_len):
        if sql[k] == "(":
            m = m + 1
        if sql[k] == ")":
            m = m - 1
        if sql[k: k + 6] == "select" and m == 0:
            sqlbegin = k + 7
            n = n + 1
        if sql[k: k + 4] == "from" and m == 0:
            sqlend = k - 1
            sql_content.append(sql[sqlbegin:sqlend])
    for value in sql_content:
        if "select" in value:
            return True
    return False
