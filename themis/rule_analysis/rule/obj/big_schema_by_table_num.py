# -*- coding: utf-8 -*-


def execute_rule(**kwargs):
    # query username and count from table information_schema
    sql = """
        SELECT '@username@',
               count(*)
        FROM information_schema.tables
        WHERE table_schema='@username@'
        """
    # execute sql
    db_cursor = kwargs.get("db_cursor", None)
    username = kwargs.get("username")
    # weight = kwargs.get("weight", 0)
    max_value = kwargs.get("max_value")
    table_size = kwargs.get("table_size", 0)
    sql = sql.replace("@username@", username)
    db_cursor.execute(sql)
    result = db_cursor.fetchall()

    # computer scores
    if int(result[0][1]) > int(table_size):
        return result, '%0.2f' % float(max_value)
    return result, 0
