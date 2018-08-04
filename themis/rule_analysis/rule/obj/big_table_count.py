# -*- coding: utf-8 -*-


def execute_rule(**kwargs):
    username = kwargs.get("username")
    db_cursor = kwargs.get("db_cursor")
    tab_phy_size = kwargs.get("tab_phy_size")
    weight = kwargs.get("weight")
    max_score = kwargs.get("max_score")
    sql = """
    SELECT count(*)
    FROM
      (SELECT segment_name,
              u.segment_type,
              sum(bytes) / 1024 / 1024 AS tab_space
       FROM dba_segments u
       WHERE u.segment_type IN ('TABLE',
                                'TABLE PARTITION',
                                'TABLE SUBPARTITION')
         AND u.owner = '@username@'
         AND u.segment_name NOT LIKE '%BIN%'
       GROUP BY u.owner,
                u.segment_name,
                u.segment_type)
    WHERE tab_space >= @tab_phy_size@
    """
    sql = sql.replace("@username@", username).\
        replace("@tab_phy_size@", str(tab_phy_size))
    db_cursor.execute(sql)
    records1 = db_cursor.fetchall()
    sql = """
    SELECT count(*)
    FROM dba_objects t
    WHERE t.owner='@username@'
      AND t.object_type='TABLE'
    """
    db_cursor.execute(sql.replace("@username@", username))
    records2 = db_cursor.fetchall()

    try:
        ratio = float("%0.2f" % float(records1[0][0] / records2[0][0]))
    except ZeroDivisionError:
        ratio = 0
    if ratio >= float(weight):
        scores = max_score
    else:
        scores = 0

    if scores > 0:
        return [[records1[0][0], records2[0][0], ratio]], scores
    else:
        return [], 0
