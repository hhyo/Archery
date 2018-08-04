# -*- coding: utf-8 -*-


def execute_rule(**kwargs):
    sql = kwargs.get("sql")
    str_len = len(sql)
    m = 0
    n = 0
    sql_content = []
    for k in range(str_len):
        if sql[k] == "(":
            m = m + 1
        if sql[k] == ")":
            m = m - 1
        if sql[k: k + 4] == "from" and m == 0:
            sqlbegin = k + 5
            n = n + 1
        if (sql[k: k + 5] == "where" or sql[k: k + 6] == "having" and m == 0):
            sqlend = k - 1
            n = n - 1
            sql_content.append(sql[sqlbegin: sqlend])
        if k == str_len - 1 and n > 0 and m == 0:
            sqlend = k - 1
            sql_content.append(sql[sqlbegin: sqlend])
    for value in sql_content:
        if "select " in value:
            return True
    return False

if __name__ == "__main__":
    sql = """ """
    kwargs = {"sql": sql}
    flag = execute_rule(kwargs)

