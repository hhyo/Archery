# -*- coding: utf-8 -*-


def execute_rule(**kwargs):
    db_cursor = kwargs.get("db_cursor")
    data_len_ratio = kwargs.get("data_len_ratio")
    username = kwargs.get("username")
    sql = """
    SELECT CASE userenv('language')
               WHEN 'SIMPLIFIED CHINESE_CHINA.AL32UTF8' THEN 3
               WHEN 'AMERICAN_AMERICA.AL32UTF8' THEN 3
               WHEN 'SIMPLIFIED CHINESE_CHINA.ZHS16GBK' THEN 4
               WHEN 'AMERICAN_AMERICA.ZHS16GBK' THEN 4
               WHEN 'SIMPLIFIED CHINESE_CHINA.UTF8' THEN 3
           END
    FROM dual
    """
    db_cursor.execute(sql)
    v_len = db_cursor.fetchall()
    sql = """
    SELECT t.table_name,
           a.col_sum,
           t.avg_row_len
    FROM dba_tables t,

      (SELECT TABLE_NAME,
              sum(LENGTH) col_sum
       FROM
         (SELECT TABLE_NAME,
                 data_length,
                 COLUMN_NAME,
                 sum(CASE data_type
                         WHEN 'VARCHAR2' THEN round(data_length / @v_len@, 2)
                         WHEN 'VARCHAR' THEN round(data_length / @v_len@, 2)
                         ELSE data_length
                     END) LENGTH
          FROM dba_tab_cols
          WHERE OWNER='@username@'
          GROUP BY TABLE_NAME,
                   data_length,
                   COLUMN_NAME) t
       GROUP BY TABLE_NAME) a
    WHERE t.owner='@username@'
      AND t.table_name = a.table_name
      AND t.avg_row_len / a.col_sum < @data_len_ratio@
    """
    sql = sql.replace("@v_len@", str(v_len[0][0])).\
        replace("@username@", username).\
        replace("@data_len_ratio@", str(data_len_ratio))
    db_cursor.execute(sql)
    records = db_cursor.fetchall()
    return records, True
