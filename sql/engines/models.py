# -*- coding: UTF-8 -*-
"""engine 结果集定义"""
import json


class ReviewResult:
    """审核的单条结果"""

    def __init__(self, inception_result=None, **kwargs):
        if inception_result:
            column_list = ['ID', 'stage', 'errlevel', 'stagestatus', 'errormessage', 'SQL', 'Affected_rows', 'sequence',
                           'backup_dbname', 'execute_time', 'sqlsha1']
            self.id = inception_result[0]
            self.stage = inception_result[1]
            self.errlevel = inception_result[2]
            self.stagestatus = inception_result[3]
            self.errormessage = inception_result[4]
            self.sql = inception_result[5]
            self.affected_rows = inception_result[6]
            self.sequence = inception_result[7]
            self.backup_dbname = inception_result[8]
            self.execute_time = inception_result[9]
            self.sqlsha1 = inception_result[10]
            self.actual_affected_rows = None
        else:
            self.id = kwargs.get('id')
            self.stage = kwargs.get('stage')
            self.errlevel = kwargs.get('errlevel')
            self.stagestatus = kwargs.get('stagestatus')
            self.errormessage = kwargs.get('errormessage')
            self.sql = kwargs.get('sql')
            self.affected_rows = kwargs.get('affected_rows')
            self.sequence = kwargs.get('sequence')
            self.backup_dbname = kwargs.get('backup_dbname')
            self.execute_time = kwargs.get('execute_time')
            self.sqlsha1 = kwargs.get('sqlsha1')
            self.actual_affected_rows = kwargs.get('actual_affected_rows')


class ReviewSet:
    """review和执行后的结果集, rows中是review result, 有设定好的字段"""

    def __init__(self, full_sql='', rows=None, status=None,
                 affected_rows=0, column_list=None, **kwargs):
        self.full_sql = full_sql
        self.is_execute = False
        self.checked = None
        self.warning = None
        self.error = None
        self.warning_count = 0  # 检测结果警告数
        self.error_count = 0  # 检测结果错误数
        self.is_critical = False
        self.syntax_type = 0  # 语法类型
        # rows 为普通列表
        if rows is None:
            self.rows = []
        else:
            self.rows = rows
        self.column_list = column_list
        self.status = status
        self.affected_rows = affected_rows

    def json(self):
        tmp_list = []
        for r in self.rows:
            tmp_list += [r.__dict__]
        return json.dumps(tmp_list)

    def to_dict(self):
        tmp_list = []
        for r in self.rows:
            tmp_list += [r.__dict__]
        return tmp_list


class ResultSet:
    """查询的结果集, rows 内只有值, column_list 中的是key"""

    def __init__(self, full_sql='', rows=None, status=None,
                 affected_rows=0, column_list=None, **kwargs):
        self.full_sql = full_sql
        self.is_execute = False
        self.checked = None
        self.is_masked = False
        self.query_time = ''
        self.mask_rule_hit = False
        self.mask_time = ''
        self.warning = None
        self.error = None
        self.is_critical = False
        # rows 为普通列表
        if rows is None:
            self.rows = []
        else:
            self.rows = rows
        self.column_list = column_list if column_list else []
        self.status = status
        self.affected_rows = affected_rows

    def json(self):
        tmp_list = []
        for r in self.rows:
            tmp_list += [dict(zip(self.column_list, r))]
        return json.dumps(tmp_list)

    def to_dict(self):
        tmp_list = []
        for r in self.rows:
            tmp_list += [dict(zip(self.column_list, r))]
        return tmp_list

    def to_sep_dict(self):
        return {'column_list': self.column_list, 'rows': self.rows}


class Node:
    def __init__(self, *args, **kwargs):
        self.original_name = original_name
        self.alias = alias
        self.type = type
        if children:
            self.children = children
        else:
            self.children = []

    def __str__(self):
        return "<Node: {}>".format(original_name)
