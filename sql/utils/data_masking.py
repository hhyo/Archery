# -*- coding:utf-8 -*-
import logging
import traceback

import sqlparse
from sqlparse.tokens import Keyword

from common.config import SysConfig
from sql.engines.inception import InceptionEngine
from sql.models import DataMaskingRules, DataMaskingColumns
import re

logger = logging.getLogger('default')


# TODO 待优化，没想好

def data_masking(instance, db_name, sql, sql_result):
    """脱敏数据"""
    try:
        if SysConfig().get('query_check'):
            # 解析查询语句，禁用部分Inception无法解析关键词
            p = sqlparse.parse(sql)[0]
            for token in p.tokens:
                if token.ttype is Keyword and token.value.upper() in ['UNION', 'UNION ALL']:
                    logger.warning(f'数据脱敏异常，错误信息：不支持该查询语句脱敏！请联系管理员')
                    sql_result.error = '不支持该查询语句脱敏！请联系管理员'
                    sql_result.status = 1
                    return sql_result
        # 通过inception获取语法树,并进行解析
        inception_engine = InceptionEngine()
        query_tree = inception_engine.query_print(instance=instance, db_name=db_name, sql=sql)
        # 分析语法树获取命中脱敏规则的列数据
        table_hit_columns, hit_columns = analyze_query_tree(query_tree, instance)
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
            for column_info in table_hit_columns:
                table_hit_column[column_info['column_name']] = column_info['rule_type']
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
    old_select_list = query_tree.get('select_list', [])
    table_ref = query_tree.get('table_ref', [])

    # 获取全部激活的脱敏字段信息，减少循环查询，提升效率
    masking_columns = DataMaskingColumns.objects.filter(active=True)

    # 判断语句涉及的表是否存在脱敏字段配置
    hit = False
    for table in table_ref:
        if masking_columns.filter(instance=instance, table_schema=table['db'], table_name=table['table']).exists():
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

        # 判断是否存在不支持脱敏的语法
        for select_item in old_select_list:
            if select_item['type'] not in ('FIELD_ITEM', 'aggregate', 'FUNC_ITEM'):
                raise Exception('不支持该查询语句脱敏！请联系管理员')
            elif select_item['type'] == 'aggregate':
                if select_item['aggregate'].get('type') not in ('FIELD_ITEM', 'INT_ITEM'):
                    raise Exception('不支持该查询语句脱敏！请联系管理员')
            # 增加单列函数的脱敏
            elif select_item['type'] == 'FUNC_ITEM':
                if len(select_item['args']) != 1:
                    raise Exception('不支持该查询语句脱敏！请联系管理员')

        # 处理select_list，为统一的{'type': 'FIELD_ITEM', 'db': 'archery_master', 'table': 'sql_users', 'field': 'email'}格式
        # 获取select信息的规则，如[*],[*,column_a],[column_a,*],[column_a,a.*,column_b],[a.*,column_a,b.*]
        select_index = []
        select_list = []
        for select_item in old_select_list:
            if select_item['type'] == 'FIELD_ITEM':
                select_index.append(select_item['field'])
                select_list.append(select_item)
            elif select_item['type'] == 'aggregate':
                select_index.append(select_item['aggregate'].get('field'))
                select_list.append(select_item['aggregate'])
            elif select_item['type'] == 'FUNC_ITEM':
                select_index.append(select_item['args'][0].get('field'))
                select_list.append(select_item['args'][0])

        if select_index:
            # 如果发现存在field='*',则遍历所有表,找出所有的命中字段
            if '*' in select_index:
                # 涉及表命中的列
                for table in table_ref:
                    hit_columns_info = hit_table(masking_columns, instance, table['db'], table['table'])
                    table_hit_columns.extend(hit_columns_info)
                # 几种不同查询格式
                # [*]
                if re.match(r"^(\*,?)+$", ','.join(select_index)):
                    hit_columns = []
                # [*,column_a]
                elif re.match(r"^(\*,)+(\w,?)+$", ','.join(select_index)):
                    # 找出field不为* 的列信息, 循环判断列是否命中脱敏规则，并增加规则类型和index，index采取后切片
                    for index, item in enumerate(select_list):
                        item['index'] = index - len(select_list)
                        if item.get('field') != '*':
                            columns.append(item)

                # [column_a, *]
                elif re.match(r"^(\w,?)+(\*,?)+$", ','.join(select_index)):
                    # 找出field不为* 的列信息, 循环判断列是否命中脱敏规则，并增加规则类型和index,index采取前切片
                    for index, item in enumerate(select_list):
                        item['index'] = index
                        if item.get('field') != '*':
                            columns.append(item)

                # [column_a,a.*,column_b]
                elif re.match(r"^(\w,?)+(\*,?)+(\w,?)+$", ','.join(select_index)):
                    # 找出field不为* 的列信息, 循环判断列是否命中脱敏规则，并增加规则类型和index,*前面的字段index采取前切片,*后面的字段采取后切片
                    for index, item in enumerate(select_list):
                        item['index'] = index
                        if item.get('field') == '*':
                            first_idx = index
                            break

                    select_list.reverse()
                    for index, item in enumerate(select_list):
                        item['index'] = index
                        if item.get('field') == '*':
                            last_idx = len(select_list) - index - 1
                            break

                    select_list.reverse()
                    for index, item in enumerate(select_list):
                        if item.get('field') != '*' and index < first_idx:
                            item['index'] = index

                        if item.get('field') != '*' and index > last_idx:
                            item['index'] = index - len(select_list)
                        columns.append(item)

                # [a.*, column_a, b.*]
                else:
                    raise Exception('不支持select信息为[a.*, column_a, b.*]格式的查询脱敏！')

            # 没有*的查询，直接遍历查询命中字段，query_tree的列index就是查询语句列的index
            else:
                for index, item in enumerate(select_list):
                    item['index'] = index
                    if item.get('field') != '*':
                        columns.append(item)

        # 格式化命中的列信息
        for column in columns:
            hit_info = hit_column(masking_columns, instance, column.get('db'), column.get('table'),
                                  column.get('field'))
            if hit_info['is_hit']:
                hit_info['index'] = column['index']
                hit_columns.append(hit_info)

    return table_hit_columns, hit_columns


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
    sql_result_column_list = [ c.lower() for c in sql_result.column_list ]
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
                        s_column_name = re.sub(r'^"?\w+"?\."?|\.|"$','',_column_name)
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
                    compiled_r = re.compile(masking_rule.rule_regex, re.I)
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
                            temp_value_list += [ column_data ]
                        rows[i] = tuple(temp_value_list)
                    sql_result.rows = rows
        except Exception as e:
            sql_result.error = str(e)

    return sql_result

