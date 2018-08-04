# -*- coding: utf-8 -*-


def execute_rule(**kwargs):
    sql = kwargs.get("sql")
    in_list_num = kwargs.get("in_list_num")
    str_len = len(sql)
    sql_content = []
    k = 0
    find_in = 0
    for k in range(str_len):
        if sql[k - 1: k + 2] == " in" and \
                (sql[k + 2] == "(" or sql[k + 3] == "("):
            find_in = k
        if sql[k] == ")" and find_in != 0:
            if "select" not in sql[find_in: k + 1]:
                sql_content.append(sql[find_in: k + 1])
            find_in = 0
    for value in sql_content:
        if value.count(",") > in_list_num:
            return True
    return False
