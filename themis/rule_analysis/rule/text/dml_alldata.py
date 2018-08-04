# -*- coding: utf-8 -*-

import re


def execute_rule(**kwargs):
    pat = re.compile('(\s)?((update )|(delete ))')
    pat1 = re.compile(' where ')
    sql = kwargs.get("sql")
    if pat.search(sql) and not pat1.search(sql):
        return True
    return False


if __name__ == "__main__":
    pass
