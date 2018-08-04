# -*- coding: utf-8 -*-
from themis.rule_analysis.rule.obj import utils


def parse_data(flag, data):
    l_char = 0
    l_date = 0
    l_phone = 0
    l_fax = 0
    l_num = 0
    l_account = 0
    l_head_0 = 0
    if flag == 'NUMBER':
        for d in data:
            if not utils.regex_date(d[0]):
                l_date = 1
                break
        if l_date == 0:
            return 'DATE'
    else:
        for d in data:
            if utils.regex_char_bar_blackslash(d[0]):
                l_char = 1
                break
            if utils.regex_date_bar_blackslash(d[0]):
                l_num = 1
                if not utils.regex_time(d[0]):
                    l_date = 1
                if not utils.regex_fax(d[0]):
                    l_fax = 1
                if l_date == 1 and l_fax == 1:
                    break
            else:
                if not utils.regex_phone(d[0]):
                    l_phone = 1
                if not utils.regex_date(d[0]):
                    l_date = 1
                if utils.regex_account(d[0]):
                    l_account = 1
                if not utils.regex_fax(d[0]):
                    l_fax = 1
                if utils.regex_head(d[0]):
                    l_head_0 = 1
        if l_date == 0 and l_char == 0:
            return 'DATE'
        if l_date == 1 and l_num == 0 and l_char == 0 and l_phone == 1 \
                and l_account == 1 and l_fax == 1 and l_head_0 == 0:
            return 'NUMBER'
    return None


def execute_rule(**kwargs):
    username = kwargs.get("username")
    sample_threshold = kwargs.get("sample_threshold")
    unrepeat_threshold = kwargs.get("unrepeat_threshold")
    db_cursor = kwargs.get("db_cursor")
    return_num = kwargs.get("return_num")
    sql = """
    SELECT a.table_name,
           a.column_name,
           CASE
               WHEN nvl(b.NUM_ROWS,@sample_threshold@+1)>@sample_threshold@ THEN 'BIG'
               ELSE 'SMALL'
           END,
           nvl(b.NUM_ROWS,@sample_threshold@+1),
           a.data_type
    FROM DBA_TAB_COLS a,
         dba_tables b
    WHERE a.owner=b.OWNER
      AND a.table_name=b.TABLE_NAME
      AND a.owner='@username@'
      AND (a.data_type LIKE '%CHAR%'
           OR a.data_type='NUMBER')
      AND hidden_column='NO'
      AND a.num_distinct>@unrepeat_threshold@
    """
    sql = sql.replace("@username@", username). \
        replace("@sample_threshold@", str(sample_threshold)). \
        replace("@unrepeat_threshold@", str(unrepeat_threshold))
    db_cursor.execute(sql)
    results = db_cursor.fetchall()
    records = []
    for r in results:
        if r[2] == "BIG":
            sample = sample_threshold * 100 / float(r[3])
            sql = """
            SELECT trim('@r1@')
            FROM
              (SELECT *
               FROM
                 (SELECT '@r1@'
                  FROM @username@.@r0@ sample BLOCK (@sample@))
               WHERE trim('@r1@') IS NOT NULL
                 AND trim('@r1@')<>'0')
            WHERE rownum<='@return_num@'
            """
            sql = sql.replace("@r1@", r[1]). \
                replace("@r0@", r[0]). \
                replace("@sample@", str(sample)). \
                replace("@return_num@", str(return_num)). \
                replace("@username@", username)
        elif r[2] == "SMALL":
            sql = """
            SELECT trim('@r1@')
            FROM @username@.@r0@
            WHERE trim('@r1@') IS NOT NULL
              AND trim('@r1@')<>'0'
            """
            sql = sql.replace("@r1@", r[1]). \
                replace("@r0@", r[0]). \
                replace("@username@", username)
        db_cursor.execute(sql)
        data = db_cursor.fetchall()
        if data:
            flag_type = parse_data(r[4], data)
            if flag_type:
                records.append((r[0], r[1], r[4], flag_type))
    return records, True
