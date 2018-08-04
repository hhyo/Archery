# -*- coding: utf-8 -*-


def execute_rule(**kwargs):
    sql = kwargs.get("sql")
    subquery = []
    str_len = len(sql)
    sql_content = []
    sqlbegin = 0
    sqlend = 0
    m = 0
    n = 0
    for k in range(str_len):
        if sql[k] == "(":
            m = m + 1
        if sql[k] == ")":
            m = m - 1
        if sql[k: k + 5] == "where" and m == 0:
            sqlbegin = k + 6
            n = n + 1
        if sql[k: k + 6] == "having" and n != 0 and m == 0:
            sqlend = k - 1
            n = n - 1
            sql_content.append(sql[sqlbegin:sqlend])
        if k == str_len - 1 and n > 0 and m == 0:
            sqlend = k - 1
            sql_content.append(sql[sqlbegin:sqlend])
    for value in sql_content:
        if "select" in value:
            return True
    return False
