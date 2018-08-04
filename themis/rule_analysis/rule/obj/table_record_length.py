# -*- coding: utf-8 -*-


def f_get_byte_length(data_type, character_octet_length, numeric_precision, numeric_scale):
    case_data_type = {
        'tinyint': 1,
        'smallint': 2,
        'mediumint': 3,
        'int': 4,
        'integer': 4,
        'bigint': 8,
        'float': 4,
        'double': 8,
        'decimal': (numeric_precision + 2 if numeric_precision > numeric_scale else numeric_scale + 2),
        'date': 3,
        'time': 3,
        'year': 1,
        'datetime': 8,
        'timestamp': 8,
        'char': character_octet_length,
        'varchar': character_octet_length,
        'tinyblob': character_octet_length,
        'tinytext': character_octet_length,
        'blob': character_octet_length,
        'text': character_octet_length,
        'mediumblob': character_octet_length,
        'mediumtext': character_octet_length,
        'longblob': character_octet_length,
        'longtext': character_octet_length,
        'enum': character_octet_length,
        'set': character_octet_length
    }
    return case_data_type.get(data_type, 0)


def execute_rule(**kwargs):
    db_cursor = kwargs.get("db_cursor")
    record_length = kwargs.get("record_length")
    username = kwargs.get("username")
    return_tabs = []
    sql = """SELECT table_name,avg_row_length
        FROM information_schema.tables
        WHERE table_schema = '@username@'"""
    sql = sql.replace("@username@", username)
    db_cursor.execute(sql)
    cur_tables = db_cursor.fetchall()
    for rec_tab in cur_tables:
        table_name = rec_tab[0]
        sql = """
            select column_name,data_type,character_octet_length,ifnull(numeric_precision,-1),ifnull(numeric_scale,-1)
            from information_schema.columns
            where table_schema='@username@' and
            table_name='@table_name@'
            """
        sql = sql.replace("@table_name@", table_name).replace("@username@", username)
        db_cursor.execute(sql)
        cur_columns = db_cursor.fetchall()

        tmp_column_length = 0
        for rec_col in cur_columns:
            data_type = rec_col[1]
            character_octet_length = rec_col[2]
            numeric_precision = rec_col[3]
            numeric_scale = rec_col[4]
            if tmp_column_length:
                tmp_column_length = tmp_column_length + f_get_byte_length(data_type, character_octet_length, numeric_precision, numeric_scale)

        if tmp_column_length > int(record_length):
            return_tabs.append([rec_tab[0], rec_tab[1], tmp_column_length])
    return return_tabs, True
