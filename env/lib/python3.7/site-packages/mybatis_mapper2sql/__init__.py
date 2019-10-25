# -*- coding: UTF-8 -*-
"""
mybatis-mapper2sql
----------------------
Generate SQL Statements from the MyBatis3 Mapper XML file
usage:
   >>> import mybatis_mapper2sql
   >>> mapper, xml_raw_text = mybatis_mapper2sql.create_mapper(xml='mybatis_mapper.xml')
   >>> statement = mybatis_mapper2sql.get_statement(mapper)
   >>> print(statement)
"""
from .generate import create_mapper, get_statement, get_child_statement
