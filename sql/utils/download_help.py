# -*- coding: UTF-8 -*-
import re
def format_value(value, col_type):
    """
    根据字段类型来格式化数据，确保类型正确
    :param value: 字段值
    :param col_type: 字段类型
    :return: 格式化后的值
    """
    if value is None:
        return "NULL"

    if col_type in ["VARCHAR", "TEXT", "CHAR"]:
        return f"'{value}'"  # 字符串加引号
    elif col_type in ["INT", "FLOAT", "DECIMAL"]:
        return str(value)  # 数字不加引号
    elif col_type in ["DATE", "DATETIME"]:
        return f"'{value}'"  # 日期时间加引号
    elif col_type == "BOOLEAN":
        return "TRUE" if value else "FALSE"  # 布尔值
    return f"'{value}'"  # 默认加引号


def generate_insert_sql(table_name, columns, column_types, data, batch_size=10):
    """
    生成 MySQL INSERT 语句，并将数据分批处理
    :param table_name: 表名
    :param columns: 列名列表
    :param column_types: 字段数据类型列表
    :param data: 数据（大元组套小元组）
    :param batch_size: 每个批次插入的数据行数
    :return: 批量 INSERT 语句
    """
    # 确保列名和数据的个数匹配
    if len(columns) != len(data[0]) or len(columns) != len(column_types):
        raise ValueError("列名和数据列数或列数和数据类型不匹配！")

    # 生成列名部分（用反引号包裹）
    column_names = ', '.join([f"`{col}`" for col in columns])

    # 将数据按批次分组，每个批次插入 `batch_size` 行
    batches = [data[i:i + batch_size] for i in range(0, len(data), batch_size)]

    insert_statements = []

    # 生成每个批次的插入语句
    for batch in batches:
        values = []
        for row in batch:
            formatted_values = []
            for i, value in enumerate(row):
                col_type = column_types[i]  # 获取当前列的类型
                formatted_values.append(format_value(value, col_type))  # 根据类型格式化
            values.append(f"({', '.join(formatted_values)})")

        # 将 VALUES 部分合并
        values_str = ', '.join(values)
        insert_sql = f"INSERT INTO `{table_name}` ({column_names}) VALUES {values_str};"
        insert_statements.append(insert_sql)

    # 返回所有批次的插入语句
    return insert_statements

def replace_limit(sql: str, new_limit: int = 5000) -> str:
    """
    将SQL语句中的LIMIT子句替换为指定值

    参数:
    sql (str): 原始SQL语句
    new_limit (int): 要替换的LIMIT值，默认为5000

    返回:
    str: 修改后的SQL语句
    """
    # 正则表达式模式：匹配LIMIT后跟任意数量的空格和非空字符
    pattern = r'\blimit\s+([^,\s]+)(\s*,\s*[^,\s]+)?\b'

    # 使用正则表达式替换LIMIT子句
    # 保留OFFSET部分（如果存在），只替换LIMIT值
    replaced_sql = re.sub(
        pattern,
        f'LIMIT {new_limit}\\2',  # \2 表示保留原有的OFFSET部分
        sql,
        flags=re.IGNORECASE
    )

    return replaced_sql
