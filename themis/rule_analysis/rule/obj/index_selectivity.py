# -*- coding: utf-8 -*-


def execute_rule(**kwargs):
    db_cursor = kwargs.get("db_cursor")
    username = kwargs.get("username")
    selectivity = kwargs.get("selectivity")
    weight = kwargs.get("weight")
    max_score = kwargs.get("max_score")

    sql = """select t.table_name,i.index_name,i.cardinality,t.table_rows,round(i.cardinality/t.table_rows*100,2)
        from information_schema.statistics i,information_schema.tables t
        where i.table_schema=t.table_schema and
            i.table_name=t.table_name and
            i.table_schema='@username@' and
            i.cardinality/t.table_rows*100<@selectivity@"""
    sql = sql.replace("@username@", username).replace("@selectivity@", str(selectivity))
    db_cursor.execute(sql)
    records = db_cursor.fetchall()
    results = [[value[0], value[1], value[2], value[3], float(value[4])] for value in records]
    if (len(records) * weight) > max_score:
        return results, float("%0.2f" % max_score)
    return results, float("%0.2f" % (len(results) * weight))