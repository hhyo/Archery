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
                break
        else:
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
                if utils.regex_bank_account(d[0]):
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
    sql = """
        SELECT d.table_name,
               d.column_name,
               CASE
                   WHEN d.TABLE_ROWS >@num_row@ THEN 'BIG'
                   ELSE 'SMALL'
               END,
               d.TABLE_ROWS,
               d.column_TYPE,
               b.column_name AS prikey
        FROM
          (SELECT c.table_name,
                  c.column_name,
                  c.column_TYPE,
                  t.TABLE_ROWS
           FROM information_schema.`COLUMNS` c,
                information_schema.`TABLES` t
           WHERE c.COLUMN_TYPE LIKE '%char%'
             AND c.TABLE_SCHEMA='@username@'
             AND c.TABLE_NAME=t.TABLE_NAME
             AND t.`ENGINE`='InnoDB') d
        LEFT OUTER JOIN
          (SELECT TABLE_NAME,
                  COLUMN_NAME
           FROM information_schema.COLUMNS
           WHERE column_key ='PRI'
             AND TABLE_SCHEMA='@username@'
             AND DATA_TYPE LIKE '%int%'
             AND TABLE_NAME IN
               (SELECT a.table_name FROM information_schema.COLUMNS a
                WHERE a.column_key ='PRI'
                  AND a.TABLE_SCHEMA='@username@'
                GROUP BY a.table_name
                HAVING count(1) =1)) b ON d.table_name=b.table_name
        """
    db_cursor = kwargs.get("db_cursor")
    num_row = kwargs.get("num_row")
    username = kwargs.get("username")
    sql = sql.replace("@num_row@", str(num_row)).replace("@username@", username)
    db_cursor.execute(sql)
    results = db_cursor.fetchall()
    table_limit = num_row / 8
    table_name_init = "dba$init_table"
    table_min_init = 0
    table_max_init = 0
    table_section_num = 0
    big_sql = """
    SELECT *
    FROM (
            (SELECT a.{r1}
             FROM {db}.{r0} a
             WHERE {r5}>{table_init0} LIMIT {table_limit})
          UNION ALL
            (SELECT a.{r1}
             FROM {db}.{r0} a
             WHERE {r5}>{table_init1} LIMIT {table_limit})
          UNION ALL
            (SELECT a.{r1}
             FROM {db}.{r0} a
             WHERE {r5}>{table_init2} LIMIT {table_limit})
          UNION ALL
            (SELECT a.{r1}
             FROM {db}.{r0} a
             WHERE {r5}>{table_init3} LIMIT {table_limit})
          UNION ALL
            (SELECT a.{r1}
             FROM {db}.{r0} a
             WHERE {r5}>{table_init4} LIMIT {table_limit})
          UNION ALL
            (SELECT a.{r1}
             FROM {db}.{r0} a
             WHERE {r5}>{table_init5} LIMIT {table_limit})
          UNION ALL
            (SELECT a.{r1}
             FROM {db}.{r0} a
             WHERE {r5}>{table_init6} LIMIT {table_limit})
          UNION ALL
            (SELECT a.{r1}
             FROM {db}.{r0} a
             WHERE {r5}>{table_init7} LIMIT {table_limit})) b
    WHERE trim(b.{r1}) <>''
      AND trim(b.{r1}) <>'0'
    """
    small_sql = """
    SELECT *
    FROM
      (SELECT a.{r1}
       FROM {db}.{r0} a LIMIT {num_row}) b
    WHERE trim(b.{r1}) <>''
      AND trim(b.{r1}) <>'0'
    """
    records = []
    for r in results:
        if r[2] == "BIG":
            if r[5]:
                if r[0] != table_name_init:
                    sql = "select ifNull({tp}({r5}),0) from {db}.{r0}"
                    db_cursor.execute(
                        sql.format(tp="min", r5=r[5], db=username, r0=r[0]))
                    table_min_init = db_cursor.fetchall()[0][0]
                    db_cursor.execute(
                        sql.format(tp="max", r5=r[5], db=username, r0=r[0]))
                    table_max_init = db_cursor.fetchall()[0][0]
                    table_section_num = (table_max_init - table_min_init) / 8
                    table_name_init = r[0]
                table_init1 = str(table_min_init + 1 * table_section_num)
                table_init2 = str(table_min_init + 2 * table_section_num)
                table_init3 = str(table_min_init + 3 * table_section_num)
                table_init4 = str(table_min_init + 4 * table_section_num)
                table_init5 = str(table_min_init + 5 * table_section_num)
                table_init6 = str(table_min_init + 6 * table_section_num)
                table_init7 = str(table_min_init + 7 * table_section_num)
                sql = big_sql.format(r1=r[1], db=username, r0=r[0],
                                     r5=r[5], table_limit=int(table_limit),
                                     table_init0=str(table_min_init),
                                     table_init1=table_init1,
                                     table_init2=table_init2,
                                     table_init3=table_init3,
                                     table_init4=table_init4,
                                     table_init5=table_init5,
                                     table_init6=table_init6,
                                     table_init7=table_init7)
                db_cursor.execute(sql)
        elif r[2] == "SMALL" or not r[5]:
            sql = small_sql.format(
                db=username, r0=r[0], r1=r[1], num_row=num_row)
            db_cursor.execute(sql)
        data = db_cursor.fetchall()
        if data:
            flag_type = parse_data(r[4], data)
            if flag_type:
                records.append((r[0], r[1], r[4], flag_type))
    return records, True
