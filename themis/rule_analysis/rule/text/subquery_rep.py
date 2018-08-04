# -*- coding: utf-8 -*-


def execute_rule(**kwargs):
    sql = kwargs.get("sql")
    str_len = len(sql)
    k = 0
    left_bracket = []
    sql_content = []
    subquery = []
    for k in range(str_len):
        if sql[k] == "(":
            left_bracket.append(k)
        if sql[k] == ")":
            start = left_bracket.pop() + 1
            stop = k - 1
            sql_content.append(sql[start:stop])
    for value in sql_content:
        if "select" in value and value not in subquery:
            subquery.append(value)
        elif "select" in value and value in subquery:
            return True
    return False
