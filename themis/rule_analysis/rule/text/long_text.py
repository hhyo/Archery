# -*- coding: utf-8 -*-


def execute_rule(**kwargs):
    sql = kwargs.get("sql")
    sql_length = kwargs.get("char_num")
    if len(sql) > sql_length:
        return True
    return False


if __name__ == "__main__":
    pass
