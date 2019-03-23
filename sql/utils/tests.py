# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: tests.py 
@time: 2019/03/14
"""
from django.test import TestCase

from sql.utils.extract_tables import TableReference
from sql.utils.sql_utils import *

__author__ = 'hhyo'


class TestSQLUtils(TestCase):
    def test_get_syntax_type(self):
        """
        测试语法判断
        :return:
        """
        dml_sql = "select * from users;"
        ddl_sql = "alter table users add id not null default 0 comment 'id' "
        self.assertEqual(get_syntax_type(dml_sql), 'DML')
        self.assertEqual(get_syntax_type(ddl_sql), 'DDL')

    def test_extract_tables(self):
        """
        测试表解析
        :return:
        """
        sql = "select * from user.users a join logs.log b on a.id=b.id;"
        self.assertEqual(extract_tables(sql),
                         (TableReference(schema='user', name='users', alias='a', is_function=False),
                          TableReference(schema='logs', name='log', alias='b', is_function=False)))

    def test_generate_sql_from_sql(self):
        """
        测试从SQl文本中解析SQL
        :return:
        """
        text = "select * from sql_user;select * from sql_workflow;"
        rows = generate_sql(text)
        self.assertListEqual(rows, [{'sql_id': 1, 'sql': 'select * from sql_user;'},
                                    {'sql_id': 2, 'sql': 'select * from sql_workflow;'}]
                             )

    def test_generate_sql_from_xml(self):
        """
        测试从XML文本中解析SQL
        :return:
        """
        text = """<?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
            <mapper namespace="Test">
            <select id="testParameters">
            SELECT
            name,
            category,
            price
            FROM
            fruits
            WHERE
            category = #{category}
            AND price > ${price}
            </select>
        </mapper>
        """
        rows = generate_sql(text)
        self.assertEqual(rows, [{'sql_id': 'testParameters',
                                 'sql': '\nSELECT name,\n       category,\n       price\nFROM fruits\nWHERE category = ?\n  AND price > ?'}]
                         )
