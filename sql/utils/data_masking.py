# -*- coding:utf-8 -*-
import logging

import sqlparse
from django.forms import model_to_dict
from sqlparse.tokens import Keyword
import pandas as pd

from sql.engines.goinception import GoInceptionEngine
from sql.models import DataMaskingRules, DataMaskingColumns
import re
import traceback

logger = logging.getLogger('default')


def data_masking(instance, db_name, sql, sql_result):
    """脱敏数据"""
    try:
        keywords_count = {}
        # 解析查询语句，判断UNION需要单独处理
        p = sqlparse.parse(sql)[0]
        for token in p.tokens:
            if token.ttype is Keyword and token.value.upper() in ['UNION', 'UNION ALL']:
                keywords_count['UNION'] = keywords_count.get('UNION', 0) + 1
        # 通过goInception获取select list
        inception_engine = GoInceptionEngine()
        select_list = inception_engine.query_data_masking(instance=instance, db_name=db_name, sql=sql)
        # 如果UNION存在，那么调用去重函数
        select_list = del_repeat(select_list, keywords_count) if keywords_count else select_list
        # 分析语法树获取命中脱敏规则的列数据
        hit_columns = analyze_query_tree(select_list, instance)
        sql_result.mask_rule_hit = True if hit_columns else False
        # 对命中规则列hit_columns的数据进行脱敏
        masking_rules = {i.rule_type: model_to_dict(i) for i in DataMaskingRules.objects.all()}
        if hit_columns and sql_result.rows:
            rows = list(sql_result.rows)
            for column in hit_columns:
                index, rule_type = column['index'], column['rule_type']
                masking_rule = masking_rules.get(rule_type)
                if not masking_rule:
                    continue
                for idx, item in enumerate(rows):
                    rows[idx] = list(item)
                    rows[idx][index] = regex(masking_rule, rows[idx][index])
                sql_result.rows = rows
            # 脱敏结果
            sql_result.is_masked = True
    except Exception as msg:
        logger.warning(f'数据脱敏异常，错误信息：{traceback.format_exc()}')
        sql_result.error = str(msg)
        sql_result.status = 1
    return sql_result


def del_repeat(select_list, keywords_count):
    """输入的 data 是inception_engine.query_data_masking的list结果
    去重前
    [{'index': 0, 'field': 'phone', 'type': 'varchar(80)', 'table': 'users', 'schema': 'db1', 'alias': 'phone'}, {'index': 1, 'field': 'phone', 'type': 'varchar(80)', 'table': 'users', 'schema': 'db1', 'alias': 'phone'}]
    去重后
    [{'index': 0, 'field': 'phone', 'type': 'varchar(80)', 'table': 'users', 'schema': 'db1', 'alias': 'phone'}]
    返回同样结构的list.
    keywords_count 关键词出现的次数
    """
    # 先将query_tree转换成表，方便统计
    df = pd.DataFrame(select_list)

    #从原来的库、表、字段去重改为字段
    #result_index = df.groupby(['field', 'table', 'schema']).filter(lambda g: len(g) > 1).to_dict('records')
    result_index = df.groupby(['field']).filter(lambda g: len(g) > 1).to_dict('records')

    # 再统计重复数量
    result_len = len(result_index)
 
    # 再计算取列表前多少的值=重复数量/(union次数+1)
    group_count = int(result_len / (keywords_count['UNION'] + 1))

    result = result_index[:group_count]
    return result


def analyze_query_tree(select_list, instance):
    """解析select list, 返回命中脱敏规则的列信息"""
    # 获取实例全部激活的脱敏字段信息，减少循环查询，提升效率
    masking_columns = {
        f"{i.instance}-{i.table_schema}-{i.table_name}-{i.column_name}": model_to_dict(i) for i in
        DataMaskingColumns.objects.filter(instance=instance, active=True)
    }
    # 遍历select_list 格式化命中的列信息
    hit_columns = []
    for column in select_list:
        table_schema, table, field = column.get('schema'), column.get('table'), column.get('field')
        masking_column = masking_columns.get(f"{instance}-{table_schema}-{table}-{field}")
        if masking_column:
            hit_columns.append({
                "instance_name": instance.instance_name,
                "table_schema": table_schema,
                "table_name": table,
                "column_name": field,
                "rule_type": masking_column['rule_type'],
                "is_hit": True,
                "index": column['index']
            })
    return hit_columns


def regex(masking_rule, value):
    """利用正则表达式脱敏数据"""
    rule_regex = masking_rule['rule_regex']
    hide_group = masking_rule['hide_group']
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
