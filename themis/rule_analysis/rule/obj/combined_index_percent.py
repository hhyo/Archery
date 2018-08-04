# -*- coding: utf-8 -*-


def execute_rule(**kwargs):
    username = kwargs.get("username")
    db_cursor = kwargs.get("db_cursor")
    max_score = kwargs.get("max_score")
    weight = kwargs.get("weight")
    com_idx_percent = kwargs.get("com_idx_percent")
    # sql变量，返回传入用户的组合索引数量和所有索引数量
    sql = """
    SELECT 'COMBINEINDEX',
           COUNT(DISTINCT IC.INDEX_NAME) AS COMBINEINDEXNUMBER
    FROM DBA_IND_COLUMNS IC
    WHERE IC.INDEX_OWNER = '@username@'
      AND IC.COLUMN_POSITION > 1
      UNION ALL
      SELECT 'ALLINDEX',
             COUNT(1)
      FROM DBA_INDEXES I WHERE I.OWNER = '@username@'
    """
    db_cursor.execute(sql.replace("@username@", username))
    records_comindnum_allinnum = db_cursor.fetchall()

    # 取组合索引数量和所有索引数量并赋值给本地变量
    for i in records_comindnum_allinnum:
        if i[0] == 'COMBINEINDEX':
            comind_num = i[1]
        if i[0] == 'ALLINDEX':
            allind_num = i[1]

    # 如果所有索引数量为0，则直接返回，并扣除本规则所有分数。
    if allind_num == 0:
        return [], float("%0.2f" % (max_score))

    # 计算组合索引占比
    comind_percent = (comind_num) * 100 / allind_num

    # 如果组合索引占比小于等于传入最小值，则不扣分，
    # 如果大于则与其做差乘以系数为所扣分，如果所扣分大于最大扣分上限，则返回最大上限值
    if comind_percent <= com_idx_percent:
        scores = 0
    elif (comind_percent - com_idx_percent) * weight > max_score:
        scores = "%0.2f" % float(max_score)
    else:
        scores = "%0.2f" % ((comind_percent - com_idx_percent) * weight)

    # sql变量，返回所有组合索引的表名，索引名，列名和列顺序
    sql = """
        SELECT I.TABLE_NAME,
               I.INDEX_NAME,
               I.COLUMN_NAME,
               I.COLUMN_POSITION
        FROM DBA_IND_COLUMNS I
        JOIN
          (SELECT DISTINCT IC.INDEX_OWNER,
                           IC.INDEX_NAME
           FROM DBA_IND_COLUMNS IC
           WHERE IC.COLUMN_POSITION > 1
             AND IC.INDEX_OWNER = '@username@') A ON I.INDEX_OWNER = A.INDEX_OWNER
        AND I.INDEX_NAME = A.INDEX_NAME
        ORDER BY I.TABLE_NAME,
                 I.INDEX_NAME,
                 I.COLUMN_POSITION
        """
    db_cursor.execute(sql.replace("@username@", username))
    records = db_cursor.fetchall()
    return records, scores
