# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: sql_utils.py 
@time: 2019/03/13
"""
import xml
import mybatis_mapper2sql
import sqlparse
from sql.utils.extract_tables import extract_tables as extract_tables_by_sqlparse

__author__ = 'hhyo'


def get_syntax_type(sql):
    """
    返回SQL语句类型
    :param sql:
    :return:
    """
    parser = sqlparse.parse(sql)
    syntax_type = None
    if parser:
        statement = sqlparse.parse(sql)[0]
        syntax_type = statement.token_first(skip_cm=True).ttype.__str__()
        if syntax_type == 'Token.Keyword.DDL':
            syntax_type = 'DDL'
        elif syntax_type == 'Token.Keyword.DML':
            syntax_type = 'DML'
    return syntax_type


def extract_tables(sql):
    """
    获取sql语句中的库、表名
    :param sql:
    :return:
    """
    return extract_tables_by_sqlparse(sql)


def generate_sql(text):
    """
    从SQL文本、MyBatis3 Mapper XML file文件中解析出sql 列表
    :param text:
    :return: [{"sql_id": key, "sql": soar.compress(value)}]
    """
    # 尝试XML解析
    try:
        mapper, xml_raw_text = mybatis_mapper2sql.create_mapper(xml_raw_text=text)
        statements = mybatis_mapper2sql.get_statement(mapper, result_type='list')
        rows = []
        # 压缩SQL语句，方便展示
        for statement in statements:
            for key, value in statement.items():
                row = {"sql_id": key, "sql": value}
                rows.append(row)
    except xml.etree.ElementTree.ParseError:
        # 删除注释语句
        text = sqlparse.format(text, strip_comments=True)
        statements = sqlparse.split(text)
        rows = []
        num = 0
        for statement in statements:
            num = num + 1
            row = {"sql_id": num, "sql": statement}
            rows.append(row)
    return rows
