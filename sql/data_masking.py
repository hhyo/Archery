# -*- coding:utf-8 -*-
from .inception import InceptionDao
from .models import DataMaskingRules, DataMaskingColumns
import json
import re

inceptionDao = InceptionDao()


class Masking(object):
    # 脱敏数据
    def data_masking(self, cluster_name, db_name, sql, sql_result):
        result = {'status': 0, 'msg': 'ok', 'data': []}
        # 通过inception获取语法树,并进行解析
        print_info = self.query_tree(sql, cluster_name, db_name)
        if print_info is None:
            result['status'] = 1
            result['msg'] = 'inception返回的结果集为空！可能是SQL语句有语法错误'
        elif print_info['errlevel'] != 0:
            result['status'] = 2
            result['msg'] = 'inception返回异常：\n' + print_info['errmsg']
        else:
            query_tree = print_info['query_tree']
            # 获取集群所属环境,获取命中脱敏规则的列数据
            table_hit_columns, hit_columns = self.analy_query_tree(query_tree, cluster_name)

            # 存在select * 的查询,遍历column_list,获取命中列的index,添加到hit_columns
            if table_hit_columns and sql_result.get('rows'):
                column_list = sql_result['column_list']
                table_hit_column = {}
                for column_info in table_hit_columns:
                    table_hit_column_info = {}
                    rule_type = column_info['rule_type']
                    table_hit_column_info[column_info['column_name']] = rule_type
                    table_hit_column.update(table_hit_column_info)

                for index, item in enumerate(column_list):
                    if item in table_hit_column.keys():
                        column = {}
                        column['column_name'] = item
                        column['index'] = index
                        column['rule_type'] = table_hit_column.get(item)
                        hit_columns.append(column)

            # 对命中规则列hit_columns的数据进行脱敏
            # 获取全部脱敏规则信息，减少循环查询，提升效率
            DataMaskingRulesOb = DataMaskingRules.objects.all()
            if hit_columns and sql_result.get('rows'):
                rows = list(sql_result['rows'])
                for column in hit_columns:
                    index = column['index']
                    for idx, item in enumerate(rows):
                        rows[idx] = list(item)
                        rows[idx][index] = self.regex(DataMaskingRulesOb, column['rule_type'], rows[idx][index])
                    sql_result['rows'] = rows
        return result

    # 通过inception获取语法树
    def query_tree(self, sqlContent, cluster_name, dbName):
        print_info = inceptionDao.query_print(sqlContent, cluster_name, dbName)
        if print_info:
            id = print_info[0][0]
            statement = print_info[0][1]
            # 返回值为非0的情况下，说明是有错的，1表示警告，不影响执行，2表示严重错误，必须修改
            errlevel = print_info[0][2]
            query_tree = print_info[0][3]
            errmsg = print_info[0][4]
            # 提交给inception语法错误的情况
            if errmsg == 'Global environment':
                errlevel = 2
                errmsg = 'Global environment: ' + query_tree
            if errlevel == 0:
                print(json.dumps(json.loads(query_tree), indent=4, sort_keys=False, ensure_ascii=False))
            return {'id': id, 'statement': statement, 'errlevel': errlevel, 'query_tree': query_tree,
                    'errmsg': errmsg}
        else:
            return None

    # 解析语法树，获取语句涉及的表，用于查询权限限制
    def query_table_ref(self, sqlContent, cluster_name, dbName):
        result = {'status': 0, 'msg': 'ok', 'data': []}
        print_info = self.query_tree(sqlContent, cluster_name, dbName)
        if print_info is None:
            result['status'] = 1
            result['msg'] = 'inception返回的结果集为空！可能是SQL语句有语法错误'
        elif print_info['errlevel'] != 0:
            result['status'] = 2
            result['msg'] = 'inception返回异常：\n' + print_info['errmsg']
        else:
            table_ref = json.loads(print_info['query_tree'])['table_ref']
            result['data'] = table_ref
        return result

    # 解析query_tree,获取语句信息,并返回命中脱敏规则的列信息
    def analy_query_tree(self, query_tree, cluster_name):
        query_tree_dict = json.loads(query_tree)
        select_list = query_tree_dict.get('select_list')
        table_ref = query_tree_dict.get('table_ref')

        # 获取全部脱敏字段信息，减少循环查询，提升效率
        DataMaskingColumnsOb = DataMaskingColumns.objects.all()

        # 遍历select_list
        columns = []
        hit_columns = []  # 命中列
        table_hit_columns = []  # 涉及表命中的列

        # 获取select信息的规则，仅处理type为FIELD_ITEM的select信息，如[*],[*,column_a],[column_a,*],[column_a,a.*,column_b],[a.*,column_a,b.*],
        select_index = [select_item['field'] for select_item in select_list if
                        select_item['type'] == 'FIELD_ITEM']

        if select_index:
            # 如果发现存在field='*',则遍历所有表,找出所有的命中字段
            if '*' in select_index:
                for table in table_ref:
                    hit_columns_info = self.hit_table(DataMaskingColumnsOb, cluster_name, table['db'],
                                                      table['table'])
                    table_hit_columns.extend(hit_columns_info)
                # [*]
                if re.match(r"^(\*,?)+$", ','.join(select_index)):
                    hit_columns = []
                # [*,column_a]
                elif re.match(r"^(\*,)+(\w,?)+$", ','.join(select_index)):
                    # 找出field不为* 的列信息, 循环判断列是否命中脱敏规则，并增加规则类型和index,index采取后切片
                    for index, item in enumerate(select_list):
                        if item['type'] == 'FIELD_ITEM':
                            item['index'] = index - len(select_list)
                            if item['field'] != '*':
                                columns.append(item)

                    for column in columns:
                        hit_info = self.hit_column(DataMaskingColumnsOb, cluster_name, column['db'],
                                                   column['table'], column['field'])
                        if hit_info['is_hit']:
                            hit_info['index'] = column['index']
                            hit_columns.append(hit_info)
                # [column_a, *]
                elif re.match(r"^(\w,?)+(\*,?)+$", ','.join(select_index)):
                    # 找出field不为* 的列信息, 循环判断列是否命中脱敏规则，并增加规则类型和index,index采取前切片
                    for index, item in enumerate(select_list):
                        if item['type'] == 'FIELD_ITEM':
                            item['index'] = index
                            if item['field'] != '*':
                                columns.append(item)

                    for column in columns:
                        hit_info = self.hit_column(DataMaskingColumnsOb, cluster_name, column['db'],
                                                   column['table'], column['field'])
                        if hit_info['is_hit']:
                            hit_info['index'] = column['index']
                            hit_columns.append(hit_info)
                # [column_a,a.*,column_b]
                elif re.match(r"^(\w,?)+(\*,?)+(\w,?)+$", ','.join(select_index)):
                    # 找出field不为* 的列信息, 循环判断列是否命中脱敏规则，并增加规则类型和index,*前面的字段index采取前切片,*后面的字段采取后切片
                    for index, item in enumerate(select_list):
                        if item['type'] == 'FIELD_ITEM':
                            item['index'] = index
                            if item['field'] == '*':
                                first_idx = index
                                break

                    select_list.reverse()
                    for index, item in enumerate(select_list):
                        if item['type'] == 'FIELD_ITEM':
                            item['index'] = index
                            if item['field'] == '*':
                                last_idx = len(select_list) - index - 1
                                break

                    select_list.reverse()
                    for index, item in enumerate(select_list):
                        if item['type'] == 'FIELD_ITEM':
                            if item['field'] != '*' and index < first_idx:
                                item['index'] = index
                                columns.append(item)

                            if item['field'] != '*' and index > last_idx:
                                item['index'] = index - len(select_list)
                                columns.append(item)

                    for column in columns:
                        hit_info = self.hit_column(DataMaskingColumnsOb, cluster_name, column['db'],
                                                   column['table'], column['field'])
                        if hit_info['is_hit']:
                            hit_info['index'] = column['index']
                            hit_columns.append(hit_info)

                # [a.*, column_a, b.*]
                else:
                    hit_columns = []
                return table_hit_columns, hit_columns
            # 没有*的查询，直接遍历查询命中字段，query_tree的列index就是查询语句列的index
            else:
                for index, item in enumerate(select_list):
                    if item['type'] == 'FIELD_ITEM':
                        item['index'] = index
                        if item['field'] != '*':
                            columns.append(item)

                for column in columns:
                    hit_info = self.hit_column(DataMaskingColumnsOb, cluster_name, column['db'], column['table'],
                                               column['field'])
                    if hit_info['is_hit']:
                        hit_info['index'] = column['index']
                        hit_columns.append(hit_info)
        return table_hit_columns, hit_columns

    # 判断字段是否命中脱敏规则,如果命中则返回脱敏的规则id和规则类型
    def hit_column(self, DataMaskingColumnsOb, cluster_name, table_schema, table_name, column_name):
        column_info = DataMaskingColumnsOb.filter(cluster_name=cluster_name, table_schema=table_schema,
                                                  table_name=table_name, column_name=column_name, active=1)

        hit_column_info = {}
        hit_column_info['cluster_name'] = cluster_name
        hit_column_info['table_schema'] = table_schema
        hit_column_info['table_name'] = table_name
        hit_column_info['column_name'] = column_name
        hit_column_info['rule_type'] = 0
        hit_column_info['is_hit'] = False

        # 命中规则
        if column_info:
            hit_column_info['rule_type'] = column_info[0].rule_type
            hit_column_info['is_hit'] = True

        return hit_column_info

    # 获取表中所有命中脱敏规则的字段信息
    def hit_table(self, DataMaskingColumnsOb, cluster_name, table_schema, table_name):
        columns_info = DataMaskingColumnsOb.filter(cluster_name=cluster_name, table_schema=table_schema,
                                                   table_name=table_name, active=1)

        # 命中规则
        hit_columns_info = []
        for column in columns_info:
            hit_column_info = {}
            hit_column_info['cluster_name'] = cluster_name
            hit_column_info['table_schema'] = table_schema
            hit_column_info['table_name'] = table_name
            hit_column_info['is_hit'] = True
            hit_column_info['column_name'] = column.column_name
            hit_column_info['rule_type'] = column.rule_type
            hit_columns_info.append(hit_column_info)
        return hit_columns_info

    # 利用正则表达式脱敏数据
    def regex(self, DataMaskingRulesOb, rule_type, str):
        rules_info = DataMaskingRulesOb.get(rule_type=rule_type)
        if rules_info:
            rule_regex = rules_info.rule_regex
            hide_group = rules_info.hide_group
            # 正则匹配必须分组，隐藏的组会使用****代替
            try:
                p = re.compile(rule_regex)
                m = p.search(str)
                masking_str = ''
                for i in range(m.lastindex):
                    if i == hide_group-1:
                        group = '****'
                    else:
                        group = m.group(i+1)
                    masking_str = masking_str + group
                return masking_str
            except Exception:
                return str
        else:
            return str
