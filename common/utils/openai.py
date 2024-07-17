from openai import OpenAI
import logging
from common.config import SysConfig

logger = logging.getLogger("default")


class OpenaiClient:
    def __init__(self):
        all_config = SysConfig()
        self.base_url = all_config.get("openai_base_url", "")
        self.api_key = all_config.get("openai_api_key", "")
        self.default_chat_model = all_config.get("default_chat_model", "")
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def request_chat_completion(self, messages, **kwargs):
        """chat_completion"""
        completion = self.client.chat.completions.create(
            model=self.default_chat_model, messages=messages, **kwargs
        )
        return completion

    def generate_sql_by_openai(self, prompt: str, table_schema: str, query_desc: str):
        """根据传入的基本信息生成查询语句"""
        messages = [
            dict(role="user", content=f"{prompt}: {table_schema}\n{query_desc}")
        ]
        logger.info(messages)
        try:
            res = self.request_chat_completion(messages)
            return res.choices[0].message.content
        except Exception as e:
            raise ValueError(f"请求openai生成查询语句失败: {e}")


def check_openai_config():
    """校验openai所需配置是否存在"""
    all_config = SysConfig()
    base_url = all_config.get("openai_base_url")
    api_key = all_config.get("openai_api_key")
    default_chat_model = all_config.get("default_chat_model")
    if base_url and api_key and default_chat_model:
        return True
    return False
