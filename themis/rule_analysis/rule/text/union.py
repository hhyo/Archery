# -*- coding: utf-8 -*-

import re


def execute_rule(**kwargs):
    sql = kwargs.get("sql")
    pat = re.compile(" union ")
    pat_all = re.compile(" union all ")
    if pat.search(sql) and not pat_all.search(sql):
        return True
    return False
