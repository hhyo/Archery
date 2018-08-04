# -*- coding: utf-8 -*-


def execute_rule(**kwargs):
    db_cursor = kwargs.get("db_cursor")
    username = kwargs.get("username")
    table_size = kwargs.get("table_size")
    weight = kwargs.get("weight")
    max_score = kwargs.get("max_score")
    sql = """select table_name,round(data_length/1024/1024/1024,2)
        from information_schema.tables
        where table_schema='@username@'
        and CREATE_OPTIONS<>'partitioned'
        and round(data_length/1024/1024/1024,2)>@table_size@
        union all
        select concat(table_name,':',partition_name),round(data_length/1024/1024/1024,2)
        from information_schema.partitions
        where table_schema='@username@'
        and table_name not in (select table_name from information_schema.tables where table_schema='@username@' and CREATE_OPTIONS<>'partitioned')
        and round(data_length/1024/1024/1024,2)>@table_size@"""
    sql = sql.replace("@username@", username).replace("@table_size@", str(table_size))
    db_cursor.execute(sql)
    records = db_cursor.fetchall()
    results = [[value[0], float(value[1])] for value in records]
    if (len(records) * weight) > max_score:
        return results, float("%0.2f" % max_score)
    return results, float("%0.2f" % (len(results) * weight))
