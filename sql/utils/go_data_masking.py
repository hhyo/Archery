# -*- coding:utf-8 -*-
import logging

import sqlparse
from sqlparse.tokens import Keyword

from common.config import SysConfig
from sql.engines.goinception import GoInceptionEngine
from sql.models import DataMaskingRules, DataMaskingColumns
import re
import pandas as pd
import traceback

logger = logging.getLogger('default')


# TODO 待优化，没想好

# Inception转为goInception，将archery中数据脱敏的IP和端口指向goInception的
# 不修改整体逻辑，主要修改由goInception返回的结果中关键字，比如db修改为schema
def go_data_masking(instance, db_name, sql, sql_result):
    """脱敏数据"""
    # SQL中关键关键字
    keywords_list = []
    try:
        if SysConfig().get('query_check'):
            # 解析查询语句，禁用部分goInception无法解析关键词，先放着空吧，，，，也许某天用上了，:)
            p = sqlparse.parse(sql)[0]
            for token in p.tokens:
                if token.ttype is Keyword and token.value.upper() in ['']:
                    logger.warning(f'数据脱敏异常，错误信息：不支持该查询语句脱敏！请联系管理员')
                    sql_result.error = '不支持该查询语句脱敏！请联系管理员'
                    sql_result.status = 1
                    return sql_result
                # 设置一个特殊标记，要是还有特殊关键字特殊处理，如果还有其他关键字需要特殊处理再逐步增加
                elif token.ttype is Keyword and token.value.upper() in ['UNION', 'UNION ALL']:
                    keywords_list.append('UNION')

        # 通过Inception获取语法树,并进行解析
        inception_engine = GoInceptionEngine()
        query_tree = inception_engine.query_datamasking(instance=instance, db_name=db_name, sql=sql)

        # 统计需要特殊处理的关键字数量
        keywords_count = {}
        for key in keywords_list:
            keywords_count[key] = keywords_count.get(key, 0) + 1

        # 如果UNION存在，那么调用去重函数
        if keywords_count.get('UNION'):
            query_tree = DelRepeat(query_tree, keywords_count)

        # 分析语法树获取命中脱敏规则的列数据
        table_hit_columns,  hit_columns = analyze_query_tree(query_tree, instance)
        sql_result.mask_rule_hit = True if table_hit_columns or hit_columns else False

    except Exception as msg:
        logger.warning(f'数据脱敏异常，错误信息：{traceback.format_exc()}')
        sql_result.error = str(msg)
        sql_result.status = 1
    else:
        # 存在select * 的查询,遍历column_list,获取命中列的index,添加到hit_columns
        if table_hit_columns and sql_result.rows:
            column_list = sql_result.column_list
            table_hit_column = dict()

            for index, item in enumerate(column_list):
                if item in table_hit_column.keys():
                    hit_columns.append({
                        "column_name": item,
                        "index": index,
                        "rule_type": table_hit_column.get(item)
                    })

        # 对命中规则列hit_columns的数据进行脱敏
        # 获取全部脱敏规则信息，减少循环查询，提升效率
        masking_rules = DataMaskingRules.objects.all()

        if hit_columns and sql_result.rows:
            rows = list(sql_result.rows)
            for column in hit_columns:
                index = column['index']
                for idx, item in enumerate(rows):

                    rows[idx] = list(item)
                    rows[idx][index] = regex(masking_rules, column['rule_type'], rows[idx][index])

                sql_result.rows = rows

            # 脱敏结果
            sql_result.is_masked = True
    return sql_result


def analyze_query_tree(query_tree, instance):
    """解析query_tree,获取语句信息,并返回命中脱敏规则的列信息"""
    old_select_list = []
    table_ref = []

    for list_i in query_tree:

        old_select_list.append({'field': list_i['field'], 'alias': list_i['alias'], 'schema': list_i['schema'], 'table': list_i['table'], 'index': list_i['index']})
        table_ref.append({'schema': list_i['schema'], 'table': list_i['table']})

    # 获取全部激活的脱敏字段信息，减少循环查询，提升效率
    masking_columns = DataMaskingColumns.objects.filter(active=True)

    # 判断语句涉及的表是否存在脱敏字段配置
    hit = False
    for table in table_ref:
        if masking_columns.filter(instance=instance, table_schema=table['schema'], table_name=table['table']).exists():
            hit = True

    # 不存在脱敏字段则直接跳过规则解析
    if not hit:
        table_hit_columns = []
        hit_columns = []
    else:
        # 遍历select_list
        columns = []
        hit_columns = []  # 命中列
        table_hit_columns = []  # 涉及表命中的列，仅select *需要

        select_index = []
        select_list = []

        for select_item in old_select_list:
            select_index.append(select_item['field'])
            select_list.append(select_item)
        if select_index:

            for table in table_ref:
                hit_columns_info = hit_table(masking_columns, instance, table['schema'], table['table'])
                table_hit_columns.extend(hit_columns_info)

            for index, item in enumerate(select_list):
                if item.get('field') != '*':
                    columns.append(item)
        # 格式化命中的列信息
        for column in columns:
            hit_info = hit_column(masking_columns, instance, column.get('schema'), column.get('table'),
                                  column.get('field'))

            if hit_info['is_hit']:
                hit_info['index'] = column['index']
                hit_columns.append(hit_info)
    return table_hit_columns, hit_columns


def DelRepeat(query_tree, keywords_count):
    """输入的 data 是inception_engine.query_datamasking的list结果，
    去重前
    [{'index': 0, 'field': 'phone', 'type': 'varchar(80)', 'table': 'users', 'schema': 'db1', 'alias': 'phone'}, {'index': 1, 'field': 'phone', 'type': 'varchar(80)', 'table': 'users', 'schema': 'db1', 'alias': 'phone'}]
    去重后
    [{'index': 0, 'field': 'phone', 'type': 'varchar(80)', 'table': 'users', 'schema': 'db1', 'alias': 'phone'}]
    返回同样结构的list.
    keywords_count 关键词出现的次数
    """
    # 先将query_tree转换成表，方便统计
    df = pd.DataFrame(query_tree)
    result_index = df.groupby(['field', 'table', 'schema']).filter(lambda g: len(g) > 1).to_dict('records')
    # 再统计重复数量
    result_len = len(result_index)
    # 再计算取列表前多少的值=重复数量/(union次数+1)
    group_count = int(result_len / (keywords_count['UNION'] + 1))
    result = result_index[:group_count]
    return result


def hit_column(masking_columns, instance, table_schema, table_name, column_name):
    """判断字段是否命中脱敏规则,如果命中则返回脱敏的规则id和规则类型"""

    column_info = masking_columns.filter(instance=instance, table_schema=table_schema,
                                         table_name=table_name, column_name=column_name)

    hit_column_info = {
        "instance_name": instance.instance_name,
        "table_schema": table_schema,
        "table_name": table_name,
        "column_name": column_name,
        "rule_type": 0,
        "is_hit": False
    }

    # 命中规则
    if column_info:
        hit_column_info['rule_type'] = column_info[0].rule_type
        hit_column_info['is_hit'] = True

    return hit_column_info


def hit_table(masking_columns, instance, table_schema, table_name):
    """获取表中所有命中脱敏规则的字段信息，用于select *的查询"""
    columns_info = masking_columns.filter(instance=instance, table_schema=table_schema, table_name=table_name)

    # 命中规则列
    hit_columns_info = []
    for column in columns_info:
        hit_columns_info.append({
            "instance_name": instance.instance_name,
            "table_schema": table_schema,
            "table_name": table_name,
            "is_hit": True,
            "column_name": column.column_name,
            "rule_type": column.rule_type
        })
    return hit_columns_info


def regex(masking_rules, rule_type, value):
    """利用正则表达式脱敏数据"""
    rules_info = masking_rules.get(rule_type=rule_type)

    if rules_info:
        rule_regex = rules_info.rule_regex
        hide_group = rules_info.hide_group
        # 正则匹配必须分组，隐藏的组会使用****代替
        try:
            p = re.compile(rule_regex, re.I)
            m = p.search(str(value))

            masking_str = ''
            for i in range(m.lastindex):
                if i == hide_group - 1:
                    group = '****'
                else:
                    group = m.group(i + 1)
                masking_str = masking_str + group
            return masking_str
        except AttributeError:
            return value
    else:
        return value


def brute_mask(instance, sql_result):
    """输入的是一个resultset
    sql_result.full_sql
    sql_result.rows 查询结果列表 List , list内的item为tuple

    返回同样结构的sql_result , error 中写入脱敏时产生的错误.
    """
    # 读取所有关联实例的脱敏规则，去重后应用到结果集，不会按照具体配置的字段匹配
    rule_types = DataMaskingColumns.objects.filter(instance=instance).values_list('rule_type', flat=True).distinct()
    masking_rules = DataMaskingRules.objects.filter(rule_type__in=rule_types)
    for reg in masking_rules:
        compiled_r = re.compile(reg.rule_regex, re.I)
        replace_pattern = r""
        rows = list(sql_result.rows)
        for i in range(1, compiled_r.groups + 1):
            if i == int(reg.hide_group):
                replace_pattern += r"****"
            else:
                replace_pattern += r"\{}".format(i)
        for i in range(len(sql_result.rows)):
            temp_value_list = []
            for j in range(len(sql_result.rows[i])):
                # 进行正则替换
                temp_value_list += [compiled_r.sub(replace_pattern, str(sql_result.rows[i][j]))]
            rows[i] = tuple(temp_value_list)
        sql_result.rows = rows
    return sql_result


def simple_column_mask(instance, sql_result):
    """输入的是一个resultset
    sql_result.full_sql
    sql_result.rows 查询结果列表 List , list内的item为tuple
    sql_result.column_list 查询结果字段列表 List
    返回同样结构的sql_result , error 中写入脱敏时产生的错误.
    """
    # 获取当前实例脱敏字段信息，减少循环查询，提升效率
    masking_columns = DataMaskingColumns.objects.filter(instance=instance, active=True)
    # 转换sql输出字段名为小写, 适配oracle脱敏
    sql_result_column_list = [c.lower() for c in sql_result.column_list]
    if masking_columns:
        try:
            for mc in masking_columns:
                # 脱敏规则字段名
                column_name = mc.column_name.lower()
                # 脱敏规则字段索引信息
                _masking_column_index = []
                if column_name in sql_result_column_list:
                    _masking_column_index.append(sql_result_column_list.index(column_name))
                # 别名字段脱敏处理
                try:
                    for _c in sql_result_column_list:
                        alias_column_regex = r'"?([^\s"]+)"?\s+(as\s+)?"?({})[",\s+]?'.format(re.escape(_c))
                        alias_column_r = re.compile(alias_column_regex, re.I)
                        # 解析原SQL查询别名字段
                        search_data = re.search(alias_column_r, sql_result.full_sql)
                        # 字段名
                        _column_name = search_data.group(1).lower()
                        s_column_name = re.sub(r'^"?\w+"?\."?|\.|"$', '', _column_name)
                        # 别名
                        alias_name = search_data.group(3).lower()
                        # 如果字段名匹配脱敏配置字段,对此字段进行脱敏处理
                        if s_column_name == column_name:
                            _masking_column_index.append(sql_result_column_list.index(alias_name))
                except:
                    pass

                for masking_column_index in _masking_column_index:
                    # 脱敏规则
                    masking_rule = DataMaskingRules.objects.get(rule_type=mc.rule_type)
                    # 脱敏后替换字符串
                    compiled_r = re.compile(masking_rule.rule_regex, re.I | re.S)
                    replace_pattern = r""
                    for i in range(1, compiled_r.groups + 1):
                        if i == int(masking_rule.hide_group):
                            replace_pattern += r"****"
                        else:
                            replace_pattern += r"\{}".format(i)

                    rows = list(sql_result.rows)
                    for i in range(len(sql_result.rows)):
                        temp_value_list = []
                        for j in range(len(sql_result.rows[i])):
                            column_data = sql_result.rows[i][j]
                            if j == masking_column_index:
                                column_data = compiled_r.sub(replace_pattern, str(sql_result.rows[i][j]))
                            temp_value_list += [column_data]
                        rows[i] = tuple(temp_value_list)
                    sql_result.rows = rows
        except Exception as e:
            sql_result.error = str(e)

    return sql_result
