from openai import OpenAI
import logging
from common.config import SysConfig
from django.template import Context, Template

logger = logging.getLogger("default")


class OpenaiClient:
    def __init__(self):
        all_config = SysConfig()
        self.base_url = all_config.get("openai_base_url", "")
        self.api_key = all_config.get("openai_api_key", "")
        self.default_chat_model = all_config.get("default_chat_model", "gpt-3.5-turbo")
        self.default_query_template = all_config.get(
            "default_query_template",
            "你是一个熟悉 {{db_type}} 的工程师, 我会给你一些基本信息和要求, 你会生成一个查询语句给我使用, 不要返回任何注释和序号, 仅返回查询语句：{{table_schema}} \n {{user_input}}",
        )
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def request_chat_completion(self, messages, **kwargs):
        """chat_completion"""
        completion = self.client.chat.completions.create(
            model=self.default_chat_model, messages=messages, **kwargs
        )
        return completion

    def generate_sql_by_openai(self, db_type: str, table_schema: str, user_input: str):
        """根据传入的基本信息生成查询语句"""
        template = Template(self.default_query_template)
        current_context = Context(
            dict(db_type=db_type, table_schema=table_schema, user_input=user_input)
        )
        messages = [dict(role="user", content=template.render(current_context))]
        logger.info(messages)
        try:
            res = self.request_chat_completion(messages)
            return res.choices[0].message.content
        except Exception as e:
            raise ValueError(f"请求openai生成查询语句失败: {e}")
        
    def audit_sql(self, messages: str) -> str:
        """
        使用OpenAI模型审核SQL语句
        参数:
            messages (str): 需要AI审核的关于sql的内容
        返回:
            str: 审核结果报告
        """
        if not check_openai_config():
            return "未配置openai_api_key"
        try:
            response = self.client.chat.completions.create(
                model=self.default_chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个 SQL 专家，负责审核 SQL 脚本。你的任务是分析 `UPDATE` 和 `DELETE` 语句以及复杂查询，并根据以下规则提供可操作的建议：\n\n1. **性能优化**：检查是否存在低效查询，例如缺失索引、全表扫描或不必要的连接。\n2. **数据完整性**：确保 `UPDATE` 和 `DELETE` 语句有合适的 `WHERE` 条件，避免意外的大规模更新或删除。\n3. **风险评估**：识别潜在风险，例如锁、死锁或意外的副作用。\n4. **最佳实践**：验证 SQL 是否符合最佳实践，例如明确的列名、正确使用事务和清晰的语法。\n\n你将获得表结构定义以辅助分析。你的建议应具体、可操作，并包含推理过程。请按照以下格式回复：\n\n- **问题**：[描述问题]\n- **影响**：[解释潜在影响]\n- **建议**：[提供可操作的建议]\n\n你只需关注 `UPDATE`、`DELETE` 和复杂查询。"
                    }, {
                        "role": "user", 
                        "content": messages
                    }
                ],
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Ai配置参数错误：{e}"


def check_openai_config():
    """校验openai必需配置openai_api_key是否存在"""
    all_config = SysConfig()
    api_key = all_config.get("openai_api_key")
    if api_key:
        return True
    return False
