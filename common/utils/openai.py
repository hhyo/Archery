from openai import OpenAI
from archery import settings
import logging


logger = logging.getLogger("default")
openai_client = OpenAI(base_url=settings.OPENAI_BASE_URL, api_key=settings.OPENAI_API_KEY)


def request_chat_completion(messages, model=settings.DEFAULT_CHAT_MODEL, **kwargs):
    """openai_client """
    completion = openai_client.chat.completions.create(
        model=model, messages=messages, **kwargs
    )
    return completion


def generate_sql_by_openai(db_type: str, table_schema: str, query_desc: str):
    tips = f'你是一个熟悉 {db_type} 的工程师, 我会给你一些基本信息和要求, 你会生成一个查询语句给我使用, 不要返回任何注释和序号, 仅返回查询语句'
    messages = [dict(role='user', content=f"{tips}: {table_schema}\n{query_desc}")]
    logger.info(messages)
    try:
        res = request_chat_completion(messages)
        return res.choices[0].message.content
    except Exception as e:
        raise ValueError(f"请求openai生成查询语句失败: {e}")
