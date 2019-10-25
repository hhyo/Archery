# -*- coding: UTF-8 -*-
import re
import sqlparse
from .convert import query_types, convert_children, convert_cdata
import xml.etree.ElementTree as ET


def create_mapper(xml=None, xml_raw_text=None):
    """
    Parse XML files
    Get mybatis mapper
    :return:
    """
    if xml_raw_text is None:
        with open(xml, "r") as f:
            xml_raw_text = f.read()
    mapper = {}
    raw_text = __replace_cdata(xml_raw_text)
    root = ET.fromstring(raw_text)
    for child in root:
        if child.tag in query_types:
            child_id = child.attrib.get('id')
            mapper[child_id] = child
    return mapper, xml_raw_text


def get_statement(mybatis_mapper, result_type='raw', **kwargs):
    """
    Get SQL Statements from Mapper
    :param mybatis_mapper:
    :param kwargs: sqlparse format kwargs /native: parse follow the native rules
    :param result_type: raw|list
    :return:
    """
    # format kwargs
    kwargs = kwargs if kwargs else {'reindent': True, 'strip_comments': True}
    # result_type
    if result_type == 'list':
        statement = []
        for child_id, child in mybatis_mapper.items():
            if child.tag not in ['sql']:
                child_statement = dict()
                child_statement[child_id] = get_child_statement(mybatis_mapper, child_id=child_id, **kwargs)
                statement.append(child_statement)
        return statement
    elif result_type == 'raw':
        statement = ''
        for child_id, child in mybatis_mapper.items():
            if child.tag not in ['sql']:
                statement += get_child_statement(mybatis_mapper, child_id=child_id, **kwargs) + ';'
        return sqlparse.format(statement, **kwargs)
    else:
        raise RuntimeError('Invalid value for sql_type: raw|list')


def get_child_statement(mybatis_mapper, child_id, **kwargs):
    """
    Get SQL Statement By child_id
    Formatting of SQL Statements
    :return:
    """
    # format kwargs
    kwargs = kwargs if kwargs else {'reindent': True, 'strip_comments': True}
    # get sql
    statement = ''
    child = mybatis_mapper.get(child_id)
    statement += convert_children(mybatis_mapper, child, **kwargs)
    # The child element has children
    for next_child in child:
        statement += convert_children(mybatis_mapper, next_child, **kwargs)
    return sqlparse.format(statement, **kwargs)


def __replace_cdata(raw_text):
    """
    Replace CDATA String
    :param raw_text:
    :return:
    """
    cdata_regex = '(<!\[CDATA\[)([\s\S]*?)(\]\]>)'
    pattern = re.compile(cdata_regex)
    match = pattern.search(raw_text)
    if match:
        cdata_text = match.group(2)
        cdata_text = convert_cdata(cdata_text, reverse=True)
        raw_text = raw_text.replace(match.group(), cdata_text)
    return raw_text
