# -*- coding: UTF-8 -*-
""" 
@author: hhyo 
@license: Apache Licence 
@file: tests.py 
@time: 2019/03/14
"""
from django.test import TestCase
from sql.utils.sql_utils import *

__author__ = 'hhyo'


class TestSQLUtils(TestCase):
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
