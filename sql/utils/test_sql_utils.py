# -*- coding: UTF-8 -*-
"""
@author: hhyo
@license: Apache Licence
@file: tests.py
@time: 2019/03/14

"""

from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from sql.utils.sql_utils import *


__author__ = "hhyo"


class TestSQLUtils(TestCase):
    def test_get_syntax_type(self):
        """
        测试语法判断
        :return:
        """
        dml_sql = "select * from users;"
        ddl_sql = "alter table users add id not null default 0 comment 'id' "
        self.assertEqual(get_syntax_type(dml_sql), "DML")
        self.assertEqual(get_syntax_type(ddl_sql), "DDL")

    def test_get_syntax_type_by_re(self):
        """
        测试语法判断，不使用sqlparse解析,直接正则匹配判断
        :return:
        """
        dml_sql = "select * from users;"
        ddl_sql = "alter table users add id int not null default 0 comment 'id' "
        other_sql = "show engine innodb status"
        self.assertEqual(get_syntax_type(dml_sql, parser=False, db_type="mysql"), "DML")
        self.assertEqual(get_syntax_type(ddl_sql, parser=False, db_type="mysql"), "DDL")
        self.assertIsNone(get_syntax_type(other_sql, parser=False, db_type="mysql"))

    def test_remove_comments(self):
        """
        测试去除SQL注释
        :return:
        """
        sql1 = """   # This comment continues to the end of line
        SELECT 1+1;     # This comment continues to the end of line"""
        sql2 = """-- This comment continues to the end of line
        SELECT 1+1;     -- This comment continues to the end of line"""
        sql3 = """/* this is an in-line comment */
        SELECT 1 /* this is an in-line comment */ + 1;/* this is an in-line comment */"""
        self.assertEqual(
            remove_comments(sql1, db_type="mysql"),
            "SELECT 1+1;     # This comment continues to the end of line",
        )
        self.assertEqual(
            remove_comments(sql2, db_type="mysql"),
            "SELECT 1+1;     -- This comment continues to the end of line",
        )
        self.assertEqual(remove_comments(sql3, db_type="mysql"), "SELECT 1  + 1;")

    def test_extract_tables_by_sql_parse(self):
        """
        测试表解析
        :return:
        """
        sql = "select * from user.users a join logs.log b on a.id=b.id;"
        self.assertEqual(
            extract_tables(sql),
            [{"name": "users", "schema": "user"}, {"name": "log", "schema": "logs"}],
        )

    def test_generate_sql_from_sql(self):
        """
        测试从SQl文本中解析SQL
        :return:
        """
        text = "select * from sql_user;select * from sql_workflow;"
        rows = generate_sql(text)
        self.assertListEqual(
            rows,
            [
                {"sql_id": 1, "sql": "select * from sql_user;"},
                {"sql_id": 2, "sql": "select * from sql_workflow;"},
            ],
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
        self.assertEqual(
            rows,
            [
                {
                    "sql_id": "testParameters",
                    "sql": "\nSELECT name,\n       category,\n       price\nFROM fruits\nWHERE category = ?\n  AND price > ?",
                }
            ],
        )

    def test_get_full_sqlitem_list_anonymous_plsql(self):
        """
        测试SQL文本中plsql可执行块（匿名块）自动分割
        :return:
        """
        text = """
declare
    v_rowcount integer;
begin
    select count(1) into v_rowcount  from user_tables
      where table_name = upper('test2'); --账户特定关系人信息历史表
    if v_rowcount = 0 then
        execute IMMEDIATE '
        create table test2
        (
        vc_bfcyid           int,           --受益人信息唯一标志ID
        vc_specperid        VARCHAR2(100)  --特定关系人信息唯一标志ID
        )
        ';
        execute IMMEDIATE '
        CREATE index Idx_test2_1 ON test2(VC_BFCYID)
        ';
    end if;
end;
/

BEGIN
    insert into test2 values(1,'qq1');
    commit;
END;
/
"""
        lists = get_full_sqlitem_list(text, "db")
        rows = [
            SqlItem(
                id=0,
                statement="""declare
    v_rowcount integer;
begin
    select count(1) into v_rowcount  from user_tables
      where table_name = upper('test2'); --账户特定关系人信息历史表
    if v_rowcount = 0 then
        execute IMMEDIATE '
        create table test2
        (
        vc_bfcyid           int,           --受益人信息唯一标志ID
        vc_specperid        VARCHAR2(100)  --特定关系人信息唯一标志ID
        )
        ';
        execute IMMEDIATE '
        CREATE index Idx_test2_1 ON test2(VC_BFCYID)
        ';
    end if;
end;""",
                stmt_type="PLSQL",
                object_owner="db",
                object_type="ANONYMOUS",
                object_name="ANONYMOUS",
            ),
            SqlItem(
                id=0,
                statement="""BEGIN
    insert into test2 values(1,'qq1');
    commit;
END;""",
                stmt_type="PLSQL",
                object_owner="db",
                object_type="ANONYMOUS",
                object_name="ANONYMOUS",
            ),
        ]
        self.assertIsInstance(lists[0], SqlItem)
        self.assertIsInstance(lists[1], SqlItem)
        self.assertEqual(lists[0].__dict__, rows[0].__dict__)
        self.assertEqual(lists[1].__dict__, rows[1].__dict__)

    def test_get_full_sqlitem_list_plsql(self):
        """
        测试SQL文本中plsql对象定义语句（存储过程、函数等）自动分割
        :return:
        """
        text = """
create or replace procedure INSERTUSER
(id IN NUMBER,
name IN VARCHAR2)
is
begin
    insert into user1 values(id,name);
end;
/

create or replace function annual_income(name1 varchar2)
return number is
annual_salary number(7,2);
begin
    select sal*12+nvl(comm,0) into annual_salary from emp where lower(ename)=lower(name1);
return annual_salary;
end;
/
"""
        lists = get_full_sqlitem_list(text, "db")
        rows = [
            SqlItem(
                id=0,
                statement="""create or replace procedure INSERTUSER
(id IN NUMBER,
name IN VARCHAR2)
is
begin
    insert into user1 values(id,name);
end;""",
                stmt_type="PLSQL",
                object_owner="db",
                object_type="PROCEDURE",
                object_name="INSERTUSER",
            ),
            SqlItem(
                id=0,
                statement="""create or replace function annual_income(name1 varchar2)
return number is
annual_salary number(7,2);
begin
    select sal*12+nvl(comm,0) into annual_salary from emp where lower(ename)=lower(name1);
return annual_salary;
end;""",
                stmt_type="PLSQL",
                object_owner="db",
                object_type="FUNCTION",
                object_name="ANNUAL_INCOME",
            ),
        ]
        self.assertIsInstance(lists[0], SqlItem)
        self.assertIsInstance(lists[1], SqlItem)
        self.assertEqual(lists[0].__dict__, rows[0].__dict__)
        self.assertEqual(lists[1].__dict__, rows[1].__dict__)

    def test_get_full_sqlitem_list_sql_after_plsql(self):
        """
        测试SQL文本中plsql后面普通SQL语句以;自动分割
        :return:
        """
        text = """
create or replace procedure INSERTUSER
(id IN NUMBER,
name IN VARCHAR2)
is
begin
    insert into user1 values(id,name);
end;
/
update user_account set created=sysdate where account_no=1; 
create table user(
    id int,
    uname varchar(100),
    age int
);
"""
        sql1 = "update user_account set created=sysdate where account_no=1;"
        sql2 = """create table user(
    id int,
    uname varchar(100),
    age int
);"""
        lists = get_full_sqlitem_list(text, "db")
        rows = [
            SqlItem(
                id=0,
                statement=sqlparse.format(
                    sql1, strip_comments=True, reindent=True, keyword_case="lower"
                ),
                stmt_type="SQL",
                object_owner="",
                object_type="",
                object_name="",
            ),
            SqlItem(
                id=0,
                statement=sqlparse.format(
                    sql2, strip_comments=True, reindent=True, keyword_case="lower"
                ),
                stmt_type="SQL",
                object_owner="",
                object_type="",
                object_name="",
            ),
        ]
        self.assertIsInstance(lists[1], SqlItem)
        self.assertIsInstance(lists[2], SqlItem)
        self.assertEqual(lists[1].__dict__, rows[0].__dict__)
        self.assertEqual(lists[2].__dict__, rows[1].__dict__)

    def test_get_full_sqlitem_list_sql(self):
        """
        测试普通SQL（不包含plsql执行块和plsql对象定义块）文本，以;符号进行SQL语句分割
        :return:
        """
        text = """
update user_account set created=sysdate where account_no=1; 
create table user(
    id int,
    uname varchar(100),
    age int
);
"""
        sql1 = "update user_account set created=sysdate where account_no=1;"
        sql2 = """create table user(
    id int,
    uname varchar(100),
    age int
);"""
        lists = get_full_sqlitem_list(text, "db")
        rows = [
            SqlItem(
                id=0,
                statement=sqlparse.format(
                    sql1, strip_comments=True, reindent=True, keyword_case="lower"
                ),
                stmt_type="SQL",
                object_owner="",
                object_type="",
                object_name="",
            ),
            SqlItem(
                id=0,
                statement=sqlparse.format(
                    sql2, strip_comments=True, reindent=True, keyword_case="lower"
                ),
                stmt_type="SQL",
                object_owner="",
                object_type="",
                object_name="",
            ),
        ]
        self.assertIsInstance(lists[0], SqlItem)
        self.assertIsInstance(lists[1], SqlItem)
        self.assertEqual(lists[0].__dict__, rows[0].__dict__)
        self.assertEqual(lists[1].__dict__, rows[1].__dict__)

    def test_filter_with_string_list_match_regex(self):
        """
        测试：当 db_list 是字符串列表时，且正则表达式匹配的情况。
        """
        db_list = ["a_db", "b_db", "test_db", "prod_db"]
        regex = r".*_db$"  # 以 "_db" 结尾的数据库名称
        result = filter_db_list(db_list, regex, is_match_regex=True)
        self.assertEqual(result, ["a_db", "b_db", "test_db", "prod_db"])  # 所有应该匹配

    def test_filter_with_string_list_not_match_regex(self):
        """
        测试：当 db_list 是字符串列表时，且正则表达式不匹配的情况。
        """
        db_list = ["a_db", "b_db", "test_db", "prod_db", "invalid"]
        regex = r".*_db$"
        result = filter_db_list(db_list, regex, is_match_regex=False)
        self.assertEqual(result, ["invalid"])  # 仅 "invalid" 不匹配正则

    def test_filter_with_dict_list_match_regex(self):
        """
        测试：当 db_list 是字典列表时，且根据指定键进行匹配正则表达式。
        """
        db_list = [
            {"value": "0", "text": "0(11)"},
            {"value": "2", "text": "2(33)"},
            {"value": "4", "text": "4(3111)"},
            {"value": "11", "text": "11(3)"},
            {"value": "44", "text": "44(3)"},
        ]
        regex = r"^(0|4|6|11|12|13)$"  # 匹配 0, 4, 6, 11, 12, 13 的正则
        result = filter_db_list(db_list, regex, is_match_regex=True, key="value")

        # 期望返回匹配的字典项
        expected_result = [
            {"value": "0", "text": "0(11)"},
            {"value": "4", "text": "4(3111)"},
            {"value": "11", "text": "11(3)"},
        ]

        self.assertEqual(result, expected_result)  # 验证返回结果是否符合预期

    def test_filter_with_dict_list_not_match_regex(self):
        """
        测试：当 db_list 是字典列表时，且根据指定键不匹配正则表达式。
        """
        db_list = [
            {"value": "a_db"},
            {"value": "b_db"},
            {"value": "prod_db"},
            {"value": "invalid"},
        ]
        regex = r".*_db$"
        result = filter_db_list(db_list, regex, is_match_regex=False, key="value")
        self.assertEqual(result, [{"value": "invalid"}])

    def test_filter_without_regex(self):
        """
        测试：当没有提供正则表达式时，函数应返回原始的 db_list。
        """
        db_list = ["a_db", "b_db", "invalid"]
        result = filter_db_list(db_list, "", is_match_regex=True)
        self.assertEqual(result, db_list)  # 没有正则，应该返回原始列表

    def test_invalid_regex(self):
        """
        测试：提供无效正则表达式时，函数应抛出 ValueError 异常。
        """
        db_list = ["a_db", "b_db"]
        regex = r"[unclosed_bracket"
        with self.assertRaises(ValueError):
            filter_db_list(db_list, regex, is_match_regex=True)

    def test_filter_with_match_and_not_match(self):
        """
        测试：使用不同的正则分别测试匹配和不匹配的情况。
        """
        db_list = ["test_db", "dmp_db", "za_db", "invalid_db", "prod_db", "no_match"]

        # 匹配正则：以 "test_db", "dmp_db", 或 "za" 开头的数据库名称
        match_regex = r"^(test_db|dmp_db|za.*)$"

        # 不匹配正则：以 "_db" 结尾的数据库名称
        not_match_regex = r".*_db$"

        # 测试匹配正则的情况
        match_result = filter_db_list(db_list, match_regex, is_match_regex=True)
        self.assertEqual(
            match_result, ["test_db", "dmp_db", "za_db"]
        )  # 仅匹配 test_db, dmp_db, za_db

        # 测试不匹配正则的情况
        not_match_result = filter_db_list(
            db_list, not_match_regex, is_match_regex=False
        )
        self.assertEqual(
            not_match_result, ["no_match"]
        )  # 仅 no_match 不符合 "_db$" 规则
