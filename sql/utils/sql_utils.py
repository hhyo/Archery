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
from moz_sql_parser import parse
from moz_sql_parser.sql_parser import join_keywords, keywords
from sql.utils.extract_tables import extract_tables as extract_tables_by_sql_parse

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


def extract_tables(sql, _type=None):
    """
    获取sql语句中的库、表名，指名select语句通过moz_sql_parser获取，其他语句通过sqlparse获取
    :param sql:
    :param _type:
    :return:
    """
    if _type == 'select':
        tables = list()
        _extract_tables_by_moz(parse(sql), tables=tables)
    else:
        tables = list()
        for i in extract_tables_by_sql_parse(sql):
            tables.append({
                "schema": i.schema,
                "name": i.name,
            })
    return tables


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


def _extract_tables_by_moz(moz_parser_dict, tables=None, parent_keyword=None, is_alias=False):
    parent_keyword = parent_keyword
    if isinstance(moz_parser_dict, dict):
        for k in moz_parser_dict.keys():
            parent_keyword = k if k in list(keywords) else parent_keyword
            is_alias = True if k == 'name' else False
            _extract_tables_by_moz(moz_parser_dict[k], tables, parent_keyword, is_alias)
    elif isinstance(moz_parser_dict, list):
        for i in moz_parser_dict:
            _extract_tables_by_moz(i, tables, parent_keyword)
    elif not is_alias:
        if parent_keyword in list(join_keywords) or parent_keyword in ['from']:
            try:
                schema = moz_parser_dict.split('.')[0]
                name = moz_parser_dict.split('.')[1]
            except IndexError:
                schema = None
                name = moz_parser_dict
            tables.append({
                "schema": schema,
                "name": name,
            })
