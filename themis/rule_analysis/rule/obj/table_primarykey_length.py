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
        'logngblob': character_octet_length,
        'longtext': character_octet_length,
        'enum': character_octet_length,
        'set': character_octet_length
    }
    return case_data_type.get(data_type)


def execute_rule(**kwargs):
    db_cursor = kwargs.get("db_cursor")
    primarykey_length = kwargs.get("primarykey_length")
    username = kwargs.get("username")
    return_tabs = []
    sql = """select table_name,group_concat(column_name)
        from information_schema.statistics
        where table_schema='@username@' and index_name='PRIMARY'
        group by table_name"""
    sql = sql.replace("@username@", username)
    db_cursor.execute(sql)
    cur_tables = db_cursor.fetchall()
    for rec_tab in cur_tables:
        table_name = rec_tab[0]
        primarykey_columns = rec_tab[1]
        tmp_column_length = 0
        tmp_column_data_type = ""
        tmp_column_list = ""
        for rec_col in primarykey_columns.split(",")[::-1]:
            sql = """select data_type,character_octet_length,ifnull(numeric_precision,-1),ifnull(numeric_scale,-1)
                from information_schema.columns
                where table_schema='@username@' and
                table_name='@table_name@' and
                column_name = '@rec_col@'"""
            sql = sql.replace("@table_name@", table_name).replace("@rec_col@", rec_col).replace("@username@", username)
            cur_column = db_cursor.fetchall()
            tmp_column_list = tmp_column_list + rec_col + ","
            if cur_column:
                data_type = cur_column[0][0]
                character_octet_length = cur_column[0][1]
                numeric_precision = cur_column[0][2]
                numeric_scale = cur_column[0][3]
                tmp_column_length = tmp_column_length + f_get_byte_length(data_type, character_octet_length, numeric_precision, numeric_scale)
                tmp_column_data_type = tmp_column_data_type + data_type + ','
        if tmp_column_length > primarykey_length:
            return_tabs.append([table_name, tmp_column_list[0:-1], tmp_column_data_type[0:-1], tmp_column_length])
    return return_tabs, True