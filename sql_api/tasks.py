import sqlglot

from sql.engines import get_engine
from sql.models import SqlWorkflowContent, SqlWorkflowAIResult
from common.utils.openai import OpenaiClient


def extract_table_names(sql):
    """根据sql内容获取涉及的表名"""
    tables = set()
    for stmt in sqlglot.parse(sql):
        for table in stmt.find_all(sqlglot.exp.Table):
            tables.add(table.name)
    return list(tables)


def get_table_fields(db_name, sql_content, instance):
    """根据sql内容获取数据库中涉及的表结构"""
    check_engine = get_engine(instance=instance)
    table_metas = {}
    # 获取涉及的表
    tables = extract_table_names(sql_content)
    for table in tables:
        meta = check_engine.get_table_desc_data(db_name=db_name, tb_name=table)
        table_metas[table] = meta
    return table_metas


def get_top10_sql(sql: str):
    """根据sql内容前10条风险较大的sql"""
    # 解析所有 SQL 语句
    parsed_statements = sqlglot.parse(sql)
    # 提取前十条非 INSERT SQL 语句
    non_insert_sql = []
    insert_sql = []
    for sql in parsed_statements:
        if not isinstance(sql, sqlglot.exp.Insert):
            non_insert_sql.append(sql.sql())
        else:
            insert_sql.append(sql.sql())
        if len(non_insert_sql) == 10:
            break
    if len(non_insert_sql) < 10:
        if len(insert_sql) >= (10 - len(non_insert_sql)):
            non_insert_sql += insert_sql[:10 - len(non_insert_sql)]
        else:
            non_insert_sql += insert_sql
    return ';'.join(non_insert_sql)


def send_ai(workflow_id: int, db_name: str, instance: int) -> str:
    """
    使用OpenAI模型审核SQL语句, 供 async_task 调用
    :param workflow_id: 用来获取需要审核的sql内容
    :param db_name: 所涉及的数据库名
    :param instance: 所涉及的数据库名
    :return:
    """
    sql = SqlWorkflowContent.objects.get(workflow_id=workflow_id).sql_content
    # 获取前10条sql
    sql = get_top10_sql(sql)
    # 获取表结构数据
    table_metas = get_table_fields(db_name=db_name, sql_content=sql, instance=instance)
    messages = f"""以下是表结构：{table_metas}。
请审核以下 SQL：{sql}。
    """
    # 调用OpenAI接口
    data = OpenaiClient().audit_sql(messages)
    # 保存结果
    tips = "如果SQL脚本超过10条SQL语句，我们只取危险性更大的前10条进行分析。"
    data = tips + "\n" + data
    SqlWorkflowAIResult.objects.create(workflow_id=workflow_id, data=data)
    return data
