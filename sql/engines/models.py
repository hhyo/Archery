# -*- coding: UTF-8 -*-
"""engine 结果集定义"""
import json


class SqlItem:

    def __init__(self, id=0, statement='', stmt_type='SQL', object_owner='', object_type='', object_name=''):
        '''
        :param id:  SQL序号,从0开始
        :param statement:  SQL Statement
        :param stmt_type:  SQL类型(SQL, PLSQL), 默认为SQL
        :param object_owner: PLSQL Object Owner
        :param object_type: PLSQL Object Type
        :param object_name: PLSQL Object Name
        '''
        self.id = id
        self.statement = statement
        self.stmt_type = stmt_type
        self.object_owner = object_owner
        self.object_type = object_type
        self.object_name = object_name


class ReviewResult:
    """审核的单条结果"""

    def __init__(self, inception_result=None, **kwargs):
        """
        inception的结果列 = ['ID', 'stage', 'errlevel', 'stagestatus', 'errormessage', 'SQL', 'Affected_rows',
                           'sequence','backup_dbname', 'execute_time', 'sqlsha1']
        go_inception的结果列 = ['order_id', 'stage', 'error_level', 'stage_status', 'error_message', 'sql',
                              'affected_rows', 'sequence', 'backup_dbname', 'execute_time', 'sqlsha1', 'backup_time']
        """
        if inception_result:
            self.id = inception_result[0] or 0
            self.stage = inception_result[1] or ''
            self.errlevel = inception_result[2] or 0
            self.stagestatus = inception_result[3] or ''
            self.errormessage = inception_result[4] or ''
            self.sql = inception_result[5] or ''
            self.affected_rows = inception_result[6] or 0
            self.sequence = inception_result[7] or ''
            self.backup_dbname = inception_result[8] or ''
            self.execute_time = inception_result[9] or ''
            self.sqlsha1 = inception_result[10] or ''
            self.backup_time = inception_result[11] if len(inception_result) >= 12 else ''
            self.actual_affected_rows = ''
        else:
            self.id = kwargs.get('id', 0)
            self.stage = kwargs.get('stage', '')
            self.errlevel = kwargs.get('errlevel', 0)
            self.stagestatus = kwargs.get('stagestatus', '')
            self.errormessage = kwargs.get('errormessage', '')
            self.sql = kwargs.get('sql', '')
            self.affected_rows = kwargs.get('affected_rows', 0)
            self.sequence = kwargs.get('sequence', '')
            self.backup_dbname = kwargs.get('backup_dbname', '')
            self.execute_time = kwargs.get('execute_time', '')
            self.sqlsha1 = kwargs.get('sqlsha1', '')
            self.backup_time = kwargs.get('backup_time', '')
            self.actual_affected_rows = kwargs.get('actual_affected_rows', '')

        # 自定义属性
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)


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
        self.rows = rows or []
        self.column_list = column_list
        self.status = status
        self.affected_rows = affected_rows

    def json(self):
        tmp_list = []
        for r in self.rows:
            if isinstance(r, dict):
                tmp_list += [r]
            else:
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
        self.rows = rows or []
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
            if isinstance(r,dict):
                tmp_list += [r]
            else:
                tmp_list += [dict(zip(self.column_list, r))]
        return tmp_list

    def to_sep_dict(self):
        return {'column_list': self.column_list, 'rows': self.rows}
